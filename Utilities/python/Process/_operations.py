# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Operations that run behind the TauFW menu: started, followed, stopped and
found again from files, by any menu, later, on any machine that sees them.

    OperationStore(root).start(kind, title, argv, cwd)
        ─▶ <root>/<kind>-<time>/operation.json ─▶ _supervisor.py ─▶ the command
    OperationStore(root).latest(kind), .running(), .all()  ─▶ Operation ─▶ state(), events, output, cancel()

The menu never runs the command itself: the supervisor (_supervisor.py) does,
in a session of its own. So leaving a screen or quitting the menu never stops
an operation, its exit code is kept without the menu, and stopping it is a
file (`stop`) that the supervisor reads. An operation directory:

  operation.json  kind, title, argv, cwd, data (what its screen needs), host, user, started, heartbeat, escalate,
                  signal
  output.log      stdout and stderr of the command
  events.jsonl    its events ($TAUFW_EVENTS, _events.py)
  heartbeat.json  host, pid, t: written by the supervisor every `heartbeat` seconds
  exit.json       returncode, stopped, finished: the command ended
  stop, kill      written by a menu: stop the command (SIGINT, then escalates), kill it now
  seen            written by a menu once its result was shown (a menu lists an ended operation until then)
  supervisor.log  what the supervisor itself printed (empty unless it failed)

The state, from these files:

  exit.json:     DONE (exit 0), FAILED, or STOPPED (the stop was asked for)
  no exit.json:  RUNNING, or STOPPING once `stop` exists; LOST when no heartbeat came for LOST_AFTER s, or at once
                 when the supervisor's process is gone on this machine (the login session ended, the machine
                 restarted, ...). Running on after the login session ends is not a goal: such an operation is LOST.

OperationStore.prune(kind) keeps the newest records of a kind (never one that
runs). One operation of a kind at a time is the caller's rule (running()).
"""
import getpass
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from typing import Callable, List, Mapping, Optional, Sequence

from ._events import EVENTS_ENV, EventReader, LogTail
from ._supervisor import (EXIT_FILE, HEARTBEAT_FILE, KILL_FILE, OPERATION_FILE, OUTPUT_FILE, STOP_FILE,
                          write_json)

__all__ = ["Operation", "OperationStore", "RUNNING", "STOPPING", "DONE", "FAILED", "STOPPED", "LOST"]


# =============================================================================
# ================================= CONSTANTS =================================


RUNNING, STOPPING, DONE, FAILED, STOPPED, LOST = "RUNNING", "STOPPING", "DONE", "FAILED", "STOPPED", "LOST"
ACTIVE = (RUNNING, STOPPING)
EVENTS_FILE = "events.jsonl"
SEEN_FILE = "seen"
SUPERVISOR_LOG = "supervisor.log"
SUPERVISOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_supervisor.py")
HEARTBEAT = 5.0      # seconds between two heartbeats of the supervisor
LOST_AFTER = 120.0   # seconds without a heartbeat before an operation is LOST
CHECK_EVERY = 1.0    # seconds between two reads of the heartbeat by one Operation
KEEP = 5             # records of a kind that prune() keeps


# =============================================================================
# ================================= OPERATION =================================


class Operation:
    """One operation directory (see the module docstring). A screen follows it
    like a running command: poll(), returncode, cancelled, cancel(), elapsed(),
    events (EventReader), output (LogTail); state() says where it is.
    The readers start at the top of the files for every new Operation object."""

    def state(self) -> str:
        """RUNNING, STOPPING, DONE, FAILED, STOPPED or LOST (see the module docstring)."""
        if self.poll() is not None:
            return STOPPED if self.stopped else (DONE if self.returncode == 0 else FAILED)
        if self._lost():
            return LOST
        return STOPPING if self.cancelled else RUNNING

    @property
    def running(self) -> bool:
        return self.state() in ACTIVE

    def poll(self) -> Optional[int]:
        """The exit code once the command ended (exit.json), else None."""
        if self.returncode is None:
            if self.process is not None:
                self.process.poll()  # started by this menu: collect the supervisor once it ended
            end = _read_json(self._path(EXIT_FILE))
            if end is not None:
                self.returncode = end.get("returncode")
                self.stopped = bool(end.get("stopped"))
                self.finished = end.get("finished")
        return self.returncode

    @property
    def cancelled(self) -> bool:
        """A stop was asked for (by any menu)."""
        return os.path.exists(self._path(STOP_FILE))

    def cancel(self) -> None:
        """Ask the supervisor to stop the command (SIGINT, then SIGTERM and SIGKILL with escalate)."""
        self._touch(STOP_FILE)

    def kill(self) -> None:
        """Ask the supervisor to kill the command at once."""
        self._touch(KILL_FILE)

    @property
    def seen(self) -> bool:
        """Its result was shown once (mark_seen)."""
        return os.path.exists(self._path(SEEN_FILE))

    def mark_seen(self) -> None:
        """Record that its result was shown; only once it ended (a running operation is never seen)."""
        if not self.running:
            with open(self._path(SEEN_FILE), "w"):
                pass

    def elapsed(self) -> float:
        """Seconds since the start, until the end once it ended."""
        self.poll()
        return max(0.0, (self.finished if self.finished is not None else self.clock()) - self.started)

    @property
    def remote(self) -> bool:
        """Started on another machine (it can be followed and stopped, its process not be checked)."""
        return self.host != socket.gethostname()

    # =========================================================================
    # ================================ HELPERS ================================

    def _lost(self) -> bool:
        now = self.clock()
        if self._checked is not None and now - self._checked < CHECK_EVERY:
            return self._was_lost
        self._checked = now
        beat = _read_json(self._path(HEARTBEAT_FILE)) or {}
        lost = now - float(beat.get("t", self.started)) > LOST_AFTER
        if not lost and beat.get("host") == socket.gethostname() and not _alive(beat.get("pid")):
            lost = self.poll() is None  # it may have ended between the two reads
        if not lost and self.process is not None and self.process.poll() is not None:
            lost = self.poll() is None  # the supervisor this menu started is gone without an exit.json
        self._was_lost = lost
        return lost

    def _touch(self, name):
        if self.poll() is None:
            with open(self._path(name), "w"):
                pass

    def _path(self, name):
        return os.path.join(self.path, name)

    # =========================================================================
    # ============================= CONSTRUCTION ==============================

    @classmethod
    def load(cls, path, clock: Callable[[], float] = time.time) -> "Operation":
        """The operation of a directory; ValueError if it has no readable operation.json."""
        record = _read_json(os.path.join(path, OPERATION_FILE))
        if not isinstance(record, dict) or "kind" not in record:
            raise ValueError("Not an operation directory: %s" % path)
        return cls(path, record, clock=clock)

    def __init__(self, path, record, process=None, clock=time.time, maxlines=2000):
        """Use OperationStore.start() or Operation.load(). process: the supervisor's Popen when this menu
        started it."""
        self.path = path
        self.record = record
        self.kind = record["kind"]
        self.title = record.get("title") or self.kind
        self.data = record.get("data") or {}
        self.argv = tuple(record.get("argv", ()))
        self.host = record.get("host", "")
        self.started = float(record.get("started", 0))
        self.process = process
        self.clock = clock
        self.returncode = None
        self.stopped = False
        self.finished = None
        self._checked = None
        self._was_lost = False
        self.events_path = self._path(EVENTS_FILE)
        self.output_path = self._path(OUTPUT_FILE)
        self.events = EventReader(self.events_path)
        self.output = LogTail(self.output_path, maxlines)

    def __repr__(self) -> str:
        return "<Operation %s>" % (self.path,)


# =============================================================================
# ================================== STORE ====================================


class OperationStore:
    """The operation directories under `root` (see the module docstring).

    Pipelines:    start(kind, title, argv, cwd, data, env, escalate) -> Operation
    Queries:      all(kind=None) newest first, latest(kind), running(kind=None)
    Cleanup:      prune(kind, keep)
    """

    def start(self, kind: str, title: str, argv: Sequence[str], cwd: str, data: Optional[Mapping] = None,
              env: Optional[Mapping[str, str]] = None, escalate: bool = True, signal: str = "group",
              heartbeat: float = HEARTBEAT, popen: Callable = subprocess.Popen) -> Operation:
        """A new operation directory, and its supervisor started beside the caller. The command gets the
        caller's environment (with env), $TAUFW_EVENTS naming its events file and unbuffered Python output.
        escalate: a stop goes on to SIGTERM and SIGKILL (False: SIGINT only; kill() remains).
        signal: where a stop's SIGINT goes: "group" (the command and everything it started) or "command" (the
        command alone, which then ends what it started itself: taufw.py lets a job submission finish)."""
        path = self._new_directory(kind)
        record = dict(kind=kind, title=title, argv=list(argv), cwd=cwd, data=dict(data or {}),
                      host=socket.gethostname(), user=_user(), started=self.clock(), heartbeat=heartbeat,
                      escalate=escalate, signal=signal)
        for name in (EVENTS_FILE, OUTPUT_FILE):
            open(os.path.join(path, name), "w").close()
        write_json(os.path.join(path, OPERATION_FILE), record)
        environment = dict(os.environ)
        environment.update(env or {})
        environment["PYTHONUNBUFFERED"] = "1"
        environment[EVENTS_ENV] = os.path.join(path, EVENTS_FILE)
        with open(os.path.join(path, SUPERVISOR_LOG), "wb") as log:
            process = popen([sys.executable, "-B", SUPERVISOR, path], cwd=cwd, env=environment,
                            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                            start_new_session=True)
        return Operation(path, record, process=process, clock=self.clock)

    def all(self, kind: Optional[str] = None) -> List[Operation]:
        """Every readable operation (of a kind), newest first."""
        if not os.path.isdir(self.root):
            return []
        operations = []
        for name in os.listdir(self.root):
            if kind is not None and not name.startswith(kind + "-"):
                continue
            try:
                operation = Operation.load(os.path.join(self.root, name), clock=self.clock)
            except (OSError, ValueError):
                continue  # half made, or not an operation
            if kind is None or operation.kind == kind:
                operations.append(operation)
        return sorted(operations, key=lambda operation: (operation.started, operation.path), reverse=True)

    def latest(self, kind: str) -> Optional[Operation]:
        operations = self.all(kind)
        return operations[0] if operations else None

    def running(self, kind: Optional[str] = None) -> List[Operation]:
        """The operations that run or stop now (not LOST)."""
        return [operation for operation in self.all(kind) if operation.running]

    def prune(self, kind: str, keep: int = KEEP) -> None:
        """Remove the records of a kind beyond the newest `keep`; one that still runs is kept."""
        for operation in self.all(kind)[keep:]:
            if not operation.running:
                shutil.rmtree(operation.path, ignore_errors=True)

    # =========================================================================
    # ================================ HELPERS ================================

    def _new_directory(self, kind):
        os.makedirs(self.root, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(self.clock()))
        for number in range(1, 1000):
            path = os.path.join(self.root, "%s-%s%s" % (kind, stamp, "" if number == 1 else "-%d" % number))
            try:
                os.mkdir(path)
                return path
            except FileExistsError:
                continue
        raise RuntimeError("Cannot make a new operation directory in %s" % self.root)

    # =========================================================================
    # ============================= CONSTRUCTION ==============================

    def __init__(self, root: str, clock: Callable[[], float] = time.time) -> None:
        self.root = str(root)
        self.clock = clock

    def __repr__(self) -> str:
        return "<OperationStore %s>" % (self.root,)


# =============================================================================
# ================================== HELPERS ==================================


def _read_json(path):
    try:
        with open(path) as stream:
            return json.load(stream)
    except (OSError, ValueError):
        return None


def _alive(pid):
    """Whether a process of this machine exists (POSIX; elsewhere, and without a pid: assumed alive)."""
    if os.name != "posix" or not isinstance(pid, int):
        return True  # os.kill(pid, 0) would end the process on Windows
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True  # it exists, owned by someone else
    return True


def _user():
    try:
        return getpass.getuser()
    except Exception:
        return ""
