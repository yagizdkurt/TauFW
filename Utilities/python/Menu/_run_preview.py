# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Read-only run previews. All file/process access happens in one daemon worker, never in curses.

Only the latest focus is requested. A slow read or a command started after the user moved away cannot
replace the new preview. Closing requests cancellation without joining the worker or waiting for a process.
"""
import threading
import time

from ..Process._operations import ACTIVE


class RunPreview:
    delay = 0.25

    def __init__(self, operations, mode, listing=None, threaded=True, clock=time.monotonic):
        self.operations, self.mode, self.clock = operations, mode, clock
        self.listing, self.threaded = listing, threaded
        self._condition = threading.Condition()
        self._target = None
        self._revision = 0
        self._due = 0
        self._closed = False
        self._thread = None
        self._kept = {}
        self._catalog = None
        self._catalog_error = None

    def _start(self):
        if self._thread is None and not self._closed:
            self._thread = threading.Thread(target=self._work, name="taufw-run-preview", daemon=True)
            self._thread.start()

    def catalog(self):
        """Discovery and lock/advance reads also stay off the terminal thread."""
        if not self.threaded:
            return self.listing(), None
        with self._condition:
            self._start()
            return self._catalog, self._catalog_error

    def view(self, target, refresh=False):
        """Return plain kept data immediately, and request the newly focused run after a short debounce."""
        with self._condition:
            if target != self._target or refresh:
                self._target = target
                self._revision += 1
                self._due = self.clock() + self.delay
                self._condition.notify_all()
            if target is not None:
                self._start()
            view = dict(self._kept.get(target, {}))
            view["loading"] = target is not None and view.get("revision") != self._revision
            return view

    def close(self):
        with self._condition:
            self._closed = True
            self._condition.notify_all()

    @staticmethod
    def _cancel(process):
        try:
            process.cancel()
        except FileNotFoundError:
            pass  # another menu may already have pruned the ended command's directory

    def _current(self, target, revision):
        with self._condition:
            return not self._closed and (target, revision) == (self._target, self._revision)

    def _publish(self, target, revision, **values):
        with self._condition:
            if not self._closed and (target, revision) == (self._target, self._revision):
                self._kept[target] = dict(self._kept.get(target, {}), revision=revision, **values)
                self._condition.notify_all()

    def _work(self):
        process, handled, next_catalog = None, None, 0
        try:
            while True:
                with self._condition:
                    if self._closed:
                        return
                    target, revision, due = self._target, self._revision, self._due
                request = (target, revision)
                if self.listing is not None and self.clock() >= next_catalog:
                    try:
                        catalog = self.listing()
                        with self._condition:
                            self._catalog, self._catalog_error = catalog, None
                    except Exception as error:
                        with self._condition:
                            self._catalog_error = str(error)
                    next_catalog = self.clock() + 0.5
                    if not self._current(*request):
                        continue
                if request != handled:
                    if process is not None:
                        self._cancel(process)
                        process = None
                    if target is not None and self.clock() >= due:
                        handled = request
                        try:
                            view = self.operations.run_preview(target)
                            if not self._current(*request):
                                continue
                            self._publish(*request, **view, error=None, reading=self.mode == "inspect")
                            if self.mode == "inspect":
                                process = self.operations.start_command("status", target)
                                if not self._current(*request):
                                    continue  # next turn cancels it, including a late start after close
                        except Exception as error:
                            self._publish(*request, error=str(error), reading=False)
                if process is not None and self._current(*request):
                    try:
                        state = process.state()
                        process.output.read()
                        lines = tuple(process.output.lines)
                        if process.output.partial:
                            lines += (process.output.partial,)
                        values = dict(reading=state in ACTIVE, command_state=state, elapsed=process.elapsed())
                        if lines or state not in ACTIVE:
                            values["output"] = lines  # retain the previous result while a refresh starts
                        self._publish(*request, **values)
                        if state not in ACTIVE:
                            process = None
                    except Exception as error:
                        self._cancel(process)
                        process = None
                        self._publish(*request, error=str(error), reading=False)
                with self._condition:
                    if not self._closed and request == (self._target, self._revision):
                        self._condition.wait(0.1)
        finally:
            if process is not None:
                self._cancel(process)
