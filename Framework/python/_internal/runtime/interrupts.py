# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Ctrl-C that waits for a step the batch system must not lose.

A production step may submit or resubmit jobs. Cut after the batch system took
the jobs but before run.json records them, the next advance submits them again
(duplicate jobs and output). Framework._advance_stages runs such a step (and
the save of run.json after it) inside deferred_interrupt():

    with deferred_interrupt(reporter, "Stage production"):
        ... step, run.json ...

The first SIGINT inside the block only prints a warning; KeyboardInterrupt is
raised when the block ends. A second SIGINT raises it at once (the user forces
the stop). Outside such a block Ctrl-C stops at once, as before.

What it protects: the Python side. The menu's stop signals taufw.py alone (the
supervisor's signal="command"), so the batch commands themselves are never
signalled. A Ctrl-C typed in a terminal also reaches the commands taufw.py runs
(condor_submit, in the same process group): those can still end early.
"""
import signal
import threading
from contextlib import contextmanager

__all__ = ['deferred_interrupt']


@contextmanager
def deferred_interrupt(reporter, what):
    """Hold SIGINT back until the block ends (see the module docstring). `what` starts the warning line. Outside the
    main thread (where signal handlers cannot be set) the block runs as it is."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    pending = []

    def handler(number, frame):
        if pending:
            raise KeyboardInterrupt  # the second Ctrl-C: stop now
        pending.append(number)
        reporter.warning("%s: stopping once run.json records this step (Ctrl-C again to force)" % (what))

    previous = signal.signal(signal.SIGINT, handler)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous if previous is not None else signal.default_int_handler)
    if pending:
        raise KeyboardInterrupt
