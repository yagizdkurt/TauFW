# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""The advance lock of a run directory: one advance moves a run at a time.

Two advances of one run (a second terminal, another lxplus node, the menu and
the CLI) would both submit, resubmit or merge the same jobs. Framework.advance
holds this lock while it works (also while it waits with --wait):

    with RunLock(run_dir, take=False) as lock:     RunLockError if another advance holds it
        ... lock.check() ...                       RunLockError if it was taken over meanwhile

<run_dir>/advance.lock  {host, pid, since, t}: made with O_EXCL (no flock: it
does not work across machines on AFS/EOS), rewritten by a thread every
HEARTBEAT s (t: the time of the last sign of life), removed at the end. It is
not part of run.json: a run that no advance holds looks as before.

A lock is LOST when no sign of life came for LOST_AFTER s, or at once when its
process is gone on this machine. A lost lock is taken over: at once when it is
of this machine (its process is gone), with take=True (`advance --take-lock`)
when it is of another machine (it may be a slow file system, not a dead
advance: the user decides). A live lock is never taken.

read_lock(run_dir) -> the lock as a dict with quiet (s since the last sign of
life), gone (its process is gone on this machine) and lost, or None: what a
menu or `status` shows. Standard library only.
"""
import json
import os
import socket
import threading
import time
from datetime import datetime

from TauFW.Framework.defaults import TIME_FORMAT

__all__ = ['RunLock', 'RunLockError', 'read_lock', 'LOCK_NAME', 'HEARTBEAT', 'LOST_AFTER']


# =============================================================================
# ================================= CONSTANTS =================================


LOCK_NAME  = "advance.lock"  # inside the run directory
HEARTBEAT  = 5.0             # seconds between two signs of life of the holder
LOST_AFTER = 120.0           # seconds without a sign of life before a lock is LOST


# =============================================================================
# ================================= RUN LOCK ==================================


class RunLockError(RuntimeError):
    """The run is advanced by another process (lock: read_lock's dict; lost: it may be taken with take=True)."""

    def __init__(self, message, lock=None):
        super().__init__(message)
        self.lock = lock or {}
        self.lost = bool(self.lock.get('lost'))


class RunLock:
    """The lock of one run directory, held between acquire() and release() (or in a `with` block).
    taken: the lock that was taken over at acquire() (read_lock's dict), else None."""

    def __init__(self, run_dir, take=False, clock=time.time, heartbeat=HEARTBEAT):
        self.path = os.path.join(run_dir, LOCK_NAME)
        self.take = take
        self.clock = clock
        self.heartbeat = heartbeat
        self.taken = None
        self._mine = None
        self._stolen = None
        self._stop = threading.Event()
        self._thread = None

    def acquire(self):
        """Create the lock file, or take over a lost lock (see the module docstring); start the heartbeat."""
        record = dict(host=socket.gethostname(), pid=os.getpid(), since=_since(self.clock()), t=self.clock())
        for _ in range(3):  # more tries after a lost lock was moved away
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                lock = read_lock(os.path.dirname(self.path), clock=self.clock)
                if lock is None:
                    continue  # released meanwhile
                if not self._may_take(lock):
                    raise RunLockError(_held(lock), lock)
                self._move_away(lock)
                self.taken = lock
                continue
            with os.fdopen(descriptor, 'w') as stream:
                json.dump(record, stream)
            self._mine = (record['host'], record['pid'], record['since'])
            self._thread = threading.Thread(target=self._beat, name="advance lock", daemon=True)
            self._thread.start()
            return self
        raise RunLockError("cannot create %s: another advance took it at the same time" % (self.path))

    def check(self):
        """Raise RunLockError if the lock was taken over by another advance since acquire()."""
        if self._stolen is not None:
            raise RunLockError("the run was taken over by another advance: %s" % (_held(self._stolen)),
                               self._stolen)

    def release(self):
        """Stop the heartbeat and remove the lock file if it is still this one."""
        if self._thread is None:
            return
        self._stop.set()
        self._thread.join()
        self._thread = None
        if self._is_mine(_read(self.path)):
            try:
                os.remove(self.path)
            except FileNotFoundError:
                pass

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc):
        self.release()
        return False

    def __repr__(self):
        return "<RunLock %s%s>" % (self.path, " held" if self._thread else "")

    # =========================================================================
    # ================================ HELPERS ================================

    def _may_take(self, lock):
        """A lost lock of this machine (its process is gone) always; a lost lock of another machine with take."""
        if not lock['lost']:
            return False
        return self.take or (lock.get('host') == socket.gethostname() and not _alive(lock.get('pid')))

    def _move_away(self, lock):
        """Rename the lost lock to a name of its own, so that the O_EXCL create decides between two takers."""
        try:
            os.replace(self.path, "%s.lost.%s.%s" % (self.path, socket.gethostname(), os.getpid()))
        except FileNotFoundError:
            pass  # another taker moved it first

    def _beat(self):
        """Rewrite t every `heartbeat` seconds while the lock is this one; stop when it is not any more."""
        while not self._stop.wait(self.heartbeat):
            current = _read(self.path)
            if not self._is_mine(current):
                self._stolen = _view(current or {}, self.clock())
                return
            current['t'] = self.clock()
            _write(self.path, current)

    def _is_mine(self, record):
        return bool(record) and (record.get('host'), record.get('pid'), record.get('since')) == self._mine


# =============================================================================
# ================================= FUNCTIONS =================================


def read_lock(run_dir, clock=time.time):
    """The lock of a run directory: dict(host, pid, since, t, quiet, lost), or None when no advance holds it."""
    path = os.path.join(run_dir, LOCK_NAME)
    record = _read(path)
    if record is None:  # no lock, or half written by a holder that died between the create and the write
        try:
            modified = os.path.getmtime(path)
        except OSError:
            return None
        record = dict(host='?', pid=None, since=_since(modified), t=modified)
    return _view(record, clock())


def _view(record, now):
    lock = dict(record)
    lock['quiet'] = max(0.0, now - float(lock.get('t', 0)))
    lock['gone'] = lock.get('host') == socket.gethostname() and not _alive(lock.get('pid'))
    lock['lost'] = lock['quiet'] > LOST_AFTER or lock['gone']
    return lock


def _held(lock):
    text = "the run is being advanced on %s since %s (pid %s)" % (lock.get('host', '?'), lock.get('since', '?'),
                                                                lock.get('pid', '?'))
    if lock.get('lost'):
        text += "; no sign of life for %.0f s: it is lost" % (lock.get('quiet', 0))
    return text


def _since(seconds):
    return datetime.fromtimestamp(seconds).strftime(TIME_FORMAT)


def _read(path):
    try:
        with open(path) as stream:
            return json.load(stream)
    except (OSError, ValueError):
        return None  # missing, or half written (read_lock then goes by the file's time)


def _write(path, data):
    """Write to a temporary name and rename: a reader never sees half a lock."""
    temporary = "%s.%d.tmp" % (path, os.getpid())
    with open(temporary, 'w') as stream:
        json.dump(data, stream)
    os.replace(temporary, path)


def _alive(pid):
    """Whether a process of this machine exists (POSIX; elsewhere, and without a pid: assumed alive). The same
    test as TauFW.Utilities.Process (_operations._alive)."""
    if os.name != 'posix' or not isinstance(pid, int):
        return True  # os.kill(pid, 0) would end the process on Windows
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
