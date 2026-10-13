"""Run Python functions in parallel processes and collect what they return.

Moved from TauFW.common.tools.parallel.MultiProcessor (2026); same queueing
and return logic. Each call runs in its own multiprocessing.Process and sends
its return value back through a one-way Pipe. At most `max_parallel` calls
run at once (< 1: no limit); later ones wait in a queue and start while the
results are collected.

    start(target, args) ──▶ Process running now, or queued (max_parallel)
          ...                    │
    for handle in processor ─────┴─▶ handle.join() ─▶ return value of target
                                     (then the next queued process starts)

With parallel=False, start() calls the target at once and join() returns its
result, so callers can switch to serial running without other changes.
The target must be picklable for the 'spawn' start method (Windows, macOS);
with 'fork' (Linux up to Python 3.13) a nested function works too.
"""
from multiprocessing import Pipe, Process
from typing import Any, Callable, Iterator, Optional

__all__ = ["ParallelProcessor"]


class ParallelProcessor:
    """Starts functions in parallel processes; see the module docstring.

    Pipelines:    start(target, args, kwargs, name, ...) -> runs or queues one call
                  iter(processor) -> one handle per call, in start order;
                                     handle.join() returns the call's result
                  close()         -> closes the finished processes
    Construction: ParallelProcessor(name, max_parallel, verbose)
    """

    # =========================================================================
    # =============================== PIPELINES ===============================

    def start(self, target: Callable, args: Any = (), kwargs: Optional[dict] = None,
              name: Optional[str] = None, verbose: bool = False, parallel: bool = True,
              kwret: Optional[str] = None) -> None:
        """Run target(*args, **kwargs) in a new process (or queue it), or right
        now with parallel=False. A non-tuple args is one argument. kwret names a
        keyword argument whose final value is also returned ("by reference"):
        join merges it into the dict or list passed to join under that name."""
        verbose = self.verbose or verbose
        kwargs = {} if kwargs is None else kwargs
        if not isinstance(args, tuple):
            args = (args,)
        if not parallel:
            call = _SerialCall(target, name, args, kwargs, kwret)
            self.procs.append((call, None, call.start(), kwret))
            return
        endout, endin = Pipe(False)
        if kwret:
            process = Process(target=_send_result_with_kwret, name=name,
                              args=(endin, target, kwret) + args, kwargs=kwargs)
        else:
            process = Process(target=_send_result, name=name, args=(endin, target) + args,
                              kwargs=kwargs)
        if verbose:
            _print_start(endin, target, args, kwargs, kwret, self.max_parallel)
        if self.max_parallel < 1 or len(self.procs) < self.max_parallel:
            process.start()
        else:
            self.waiting.append(process)
        self.procs.append((process, endin, endout, kwret))

    def __iter__(self) -> Iterator["_ProcessHandle"]:
        """One handle per started call, in order. After each handle is
        consumed, the oldest queued process starts."""
        for index, (process, endin, endout, kwret) in enumerate(self.procs):
            if self.verbose:
                _print_iteration(index, process, endin, endout)
            yield _ProcessHandle(process, endout, kwret, verbose=self.verbose)
            if self.max_parallel >= 1 and self.waiting:
                self.waiting.pop(0).start()

    def close(self) -> None:
        """Close and forget every parallel process (they must have finished);
        serial calls are kept."""
        for record in self.procs[:]:
            process = record[0]
            if isinstance(process, Process):
                _print_close(process)
                process.close()
                self.procs.remove(record)

    # =========================================================================
    # ============================= CONSTRUCTION ==============================

    def __init__(self, name: str = "nameless", max_parallel: int = -1,
                 verbose: bool = False) -> None:
        """max_parallel: most calls running at once (< 1: no limit).
        Construction starts nothing."""
        self.name = name
        self.max_parallel = max_parallel
        self.verbose = verbose
        # (process or _SerialCall, sending end, receiving end or serial result, kwret)
        self.procs = []
        self.waiting = []   # parallel processes not started yet, oldest first

    def __repr__(self) -> str:
        return "<ParallelProcessor %r: %d calls>" % (self.name, len(self.procs))


# =============================================================================
# ================================== HANDLES ==================================


class _ProcessHandle:
    """One started call; join() waits for it and returns its result."""

    def join(self, *args, **kwargs) -> Any:
        """Wait for the call (args: Process.join's timeout) and return its
        result. If the call has a kwret and kwargs passes that name, the
        returned keyword value is merged into kwargs[kwret] (dict: update,
        list: extend). kwargs 'verbose' overrides the handle's verbosity."""
        verbose = kwargs.get("verbose", self.verbose)
        if isinstance(self.process, Process):
            if verbose:
                _print_join(self.name, args, serial=False)
            self.process.join(*args)
            if self.kwret in kwargs:
                result, kwret_value = self.endout.recv()
                _merge(kwargs[self.kwret], kwret_value, self.kwret)
                return result
            return self.endout.recv()
        if verbose:
            _print_join(self.name, args, serial=True)
        if self.kwret in kwargs:
            _merge(kwargs[self.kwret], self.process.kwargs[self.kwret], self.kwret)
        return self.endout

    def __init__(self, process, endout, kwret: Optional[str], verbose: bool = False) -> None:
        """endout: the pipe's receiving end, or the result of a serial call."""
        self.name = process.name
        self.process = process
        self.endout = endout
        self.kwret = kwret
        self.verbose = verbose


class _SerialCall:
    """A call that runs in this process when started (parallel=False)."""

    def start(self) -> Any:
        return self.target(*self.args, **self.kwargs)

    def __init__(self, target: Callable, name: Optional[str], args: tuple, kwargs: dict,
                 kwret: Optional[str] = None) -> None:
        self.name = name
        self.target = target
        self.args = args
        self.kwargs = kwargs
        self.kwret = kwret


# =============================================================================
# ================================ FUNCTIONS ==================================


def _send_result(endin, target, *args, **kwargs) -> None:
    """Run in the child process: send target's return value to the pipe."""
    endin.send(target(*args, **kwargs))


def _send_result_with_kwret(endin, target, kwret, *args, **kwargs) -> None:
    """Like _send_result, plus the final value of keyword argument kwret."""
    endin.send((target(*args, **kwargs), kwargs[kwret]))


def _merge(destination, value, kwret: str) -> None:
    """Merge a returned keyword value into the caller's dict or list."""
    if isinstance(value, dict):
        destination.update(value)
    elif isinstance(value, list):
        destination.extend(value)
    else:
        _print_merge_warning(kwret, value)


# =============================================================================
# ===================== BACKWARD COMPATIBILITY, CLEANUP =======================
# Messages with the exact text of the old MultiProcessor (old class names
# included), so verbose logs stay comparable. Modernize them (e.g. through a
# CLI instance passed to the constructor) in their own commit. close() always
# printed its line, whatever the verbosity.


def _print_start(endin, target, args, kwargs, kwret, max_parallel) -> None:
    print(">>> MultiProcessor.start: endin=%r, target=%r, args=%r, kwargs=%r, kwret=%r, max=%s" % (
        endin, target, args, kwargs, kwret, max_parallel))


def _print_iteration(index, process, endin, endout) -> None:
    print(">>> MultiProcessor.__iter__: i=%s, process=%r, endin=%r, endout=%s, " % (
        index, process, endin, endout))


def _print_join(name, args, serial: bool) -> None:
    if serial:
        print(">>> ReturnProcess.join: name=%r (serial), args=%s" % (name, args))
    else:
        print(">>> ReturnProcess.join: name=%r, args=%s" % (name, args))


def _print_close(process) -> None:
    print(">>> Close process", process)


def _print_merge_warning(kwret, value) -> None:
    print("Warning! MultiThread.ReturnProcess.join: No implementation for keyword return value '%s' of type %s..." % (
        kwret, type(value)))
