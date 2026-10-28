# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Work the menu does before a screen asks for it: what Start and Continue list.

    MenuNavigation.run() ─▶ prefetch.add(key, job) ─▶ a thread of its own runs the jobs, one at a time, in order
    a screen ─▶ operations.kept_...() (what a job left) ─▶ a row is drawn, or "checking..." until its job ran

The jobs leave their results with the operations (the adapter keeps them and
knows when they are stale); this module only runs them. The thread is a
daemon: quitting the menu never waits for it. It runs while the menu waits for
a key (curses releases the GIL in getch), so the user rarely notices it.
Without a thread (threaded=False: the unit tests, a caller without one) a job
runs at once in the caller. No Framework imports belong here.
"""
import collections
import threading

__all__ = ["Prefetch"]


class Prefetch:
    """Jobs (functions without arguments) run one at a time by a daemon thread; a key is queued once until its job
    ended. An error of a job is dropped: the screen that needs the result asks again (and shows the error)."""

    def add(self, key, job):
        """Queue job under key unless that key is queued or running."""
        with self._lock:
            if key in self._keys:
                return
            self._keys.add(key)
            self._jobs.append((key, job))
            if self.threaded and self._thread is None:
                self._thread = threading.Thread(target=self._work, name="taufw-menu-prefetch", daemon=True)
                self._thread.start()
        if not self.threaded:
            self._work()

    def busy(self, key):
        """Its job is queued or running."""
        with self._lock:
            return key in self._keys

    def wait(self, timeout=None):
        """Until every queued job ended (the unit tests); False if the timeout came first."""
        with self._lock:
            return self._idle.wait_for(lambda: not self._keys, timeout)

    # =========================================================================
    # ================================ HELPERS ================================

    def _work(self):
        while True:
            with self._lock:
                if not self._jobs:
                    self._thread = None
                    self._idle.notify_all()
                    return
                key, job = self._jobs.popleft()
            try:
                job()
            except Exception:
                pass  # the screen asks again and shows what went wrong
            finally:
                with self._lock:
                    self._keys.discard(key)

    # =========================================================================
    # ============================= CONSTRUCTION ==============================

    def __init__(self, threaded=True):
        self.threaded = threaded
        self._lock = threading.Lock()
        self._idle = threading.Condition(self._lock)
        self._jobs = collections.deque()
        self._keys = set()
        self._thread = None

    def __repr__(self):
        return "<Prefetch %d queued>" % len(self._keys)
