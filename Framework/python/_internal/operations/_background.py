# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Run a command beside a screen: it never writes to the terminal and the
screen never waits for it.

The command gets its own session (process group), reads nothing (stdin is
/dev/null) and writes stdout and stderr straight to a log file, not to a pipe
that the screen would have to drain. A screen calls poll() and reads .events
and .output (_events.py) as often as it draws, and cancel() to stop it:

    start(argv, cwd, log, events) ─▶ poll() ... poll() -> exit code
                                       │  after cancel(): SIGINT, after TERM_AFTER s SIGTERM,
                                       │  after KILL_AFTER s SIGKILL (to the whole group)
                                       └─ .events.read(), .output.read(): once more after the exit

The exit code: the command's own, 128+N when signal N killed it, STOP_EXIT
when it was cancelled and did not succeed. Ctrl-C in the terminal reaches only
the screen, which decides whether to cancel().
"""
import os
import signal
import subprocess
import time
from typing import Callable, Mapping, Optional, Sequence

from ._events import EVENTS_ENV, EventReader, LogTail

__all__ = ["BackgroundProcess"]


# =============================================================================
# ================================= CONSTANTS =================================


STOP_EXIT = 130     # exit code of a cancelled command (as after Ctrl-C)
TERM_AFTER = 3.0    # seconds after cancel() before SIGTERM
KILL_AFTER = 8.0    # seconds after cancel() before SIGKILL


# =============================================================================
# ============================ BACKGROUND PROCESS =============================


class BackgroundProcess:
    """A running command; see the module docstring.

    Pipelines:    start(argv, cwd, log, events, env) -> BackgroundProcess
                  poll() -> exit code or None, cancel(), close()
    State:        running, cancelled, returncode, elapsed(), events (EventReader or None), output (LogTail)
    """

    # =========================================================================
    # =============================== PIPELINES ===============================

    @classmethod
    def start(cls, argv: Sequence[str], cwd: str, log: str, events: Optional[str] = None,
              env: Optional[Mapping[str, str]] = None, maxlines: int = 2000,
              popen: Callable = subprocess.Popen, clock: Callable[[], float] = time.monotonic):
        """Start argv in cwd; its output goes to `log` and, with `events`, its
        events to that file ($TAUFW_EVENTS). Both files start empty."""
        environment = dict(os.environ)
        environment.update(env or {})
        environment["PYTHONUNBUFFERED"] = "1"   # the log follows the command as it runs
        environment.pop(EVENTS_ENV, None)       # never the events file of a command that started this one
        for path in filter(None, (log, events)):
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        if events:
            open(events, "w").close()
            environment[EVENTS_ENV] = events
        with open(log, "wb") as stream:
            process = popen(list(argv), cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
                            stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        return cls(process, argv, cwd, log, events, maxlines, clock)

    def poll(self) -> Optional[int]:
        """The exit code once the command ended, else None; sends the next
        signal of a cancel() that is due."""
        if self.returncode is None:
            self._escalate()
            status = self.process.poll()
            if status is not None:
                self.finished = self.clock()
                if self.cancelled and status != 0:
                    self.returncode = STOP_EXIT
                else:
                    self.returncode = status if status >= 0 else 128 - status
        return self.returncode

    def cancel(self) -> None:
        """Ask the command to stop (SIGINT to its group); poll() escalates."""
        if self.running and not self.cancelled:
            self.cancelled = True
            self.cancel_at = self.clock()
            self._signal(signal.SIGINT)

    def close(self) -> None:
        """Stop the command if it still runs and wait for it (a screen that
        fails or quits leaves nothing behind)."""
        if self.poll() is not None:
            return
        self.cancel()
        deadline = self.clock() + KILL_AFTER + 1
        while self.poll() is None and self.clock() < deadline:
            time.sleep(0.05)
        if self.returncode is None:
            self._signal(signal.SIGKILL)
            self.process.wait()
            self.poll()

    @property
    def running(self) -> bool:
        return self.poll() is None

    def elapsed(self) -> float:
        """Seconds since the start, until the end once it ended."""
        return (self.finished if self.finished is not None else self.clock()) - self.started

    # =========================================================================
    # ================================ HELPERS ================================

    def _escalate(self) -> None:
        if self.cancel_at is None:
            return
        waited = self.clock() - self.cancel_at
        if waited >= KILL_AFTER and self.cancel_level < 2:
            self._signal(signal.SIGKILL)
            self.cancel_level = 2
        elif waited >= TERM_AFTER and self.cancel_level < 1:
            self._signal(signal.SIGTERM)
            self.cancel_level = 1

    def _signal(self, number) -> None:
        try:
            os.killpg(self.process.pid, number)
        except ProcessLookupError:
            pass  # it ended just before

    # =========================================================================
    # ============================= CONSTRUCTION ==============================

    def __init__(self, process, argv, cwd, log, events=None, maxlines=2000, clock=time.monotonic):
        """Wraps a started subprocess.Popen; use start()."""
        self.process = process
        self.argv = tuple(argv)
        self.cwd = cwd
        self.log = log
        self.clock = clock
        self.started = clock()
        self.finished = None
        self.returncode = None
        self.cancelled = False
        self.cancel_at = None
        self.cancel_level = 0
        self.events = EventReader(events) if events else None
        self.output = LogTail(log, maxlines)

    def __repr__(self) -> str:
        return "<BackgroundProcess %s>" % (" ".join(self.argv),)
