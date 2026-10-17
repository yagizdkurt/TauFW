# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""The screen that follows a test run while Tests/run.py works beside it.

The run is a TauFW.Utilities.Process.BackgroundProcess: its events
(Tests/support/events.py) build a TestRun, its output log is the "Output"
view, and every case log is read only while that case is on screen:

    process.events ─▶ TestRun.feed() ─▶ Cases list + Details (focused case)
    process.output ─────────────────▶ Output view (L)
    case log       ─────────────────▶ Details / Case log view (Enter)

The screen draws ten times a second and never waits for the run. Leaving it
while the run works asks first and stops the run: tests are not left running
behind the menu. No Framework imports belong here; _menu.py imports this module only
when the screen is shown (FastSetup imports Menu before TauFW is built).
"""
import re
import time

from ..Process import LogTail

__all__ = ["TestRun", "follow_tests"]


# =============================================================================
# ================================= CONSTANTS =================================


FRAME = 0.1           # seconds between frames
CASE_LOG_LINES = 400  # lines of a case log kept on screen
MESSAGES = 50         # warnings and errors kept
MARKERS = {"WAIT": "[    ]", "RUN": "[ RUN]", "PASS": "[PASS]", "FAIL": "[FAIL]", "SKIP": "[SKIP]",
           "STOP": "[STOP]"}
ROLES = {"RUN": "accent", "PASS": "good", "FAIL": "error", "SKIP": "waiting", "STOP": "warning"}
CONTROL = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|[\x00-\x08\x0b-\x1f\x7f]")


# =============================================================================
# ================================= TEST RUN ==================================


class TestRun:
    """What the screen knows about a test run, from its events. cases: id ->
    dict(id, group, status, started, seconds, exit, log, details), in the
    order they were expected or started; messages: (role, text)."""

    def feed(self, events):
        for event in events:
            handler = getattr(self, "_on_" + event["kind"], None)
            if handler:
                handler(event)

    def finish(self, returncode):
        """The run ended: a case still running was stopped with it."""
        for case in self.cases.values():
            if case["status"] == "RUN":
                case["status"] = "STOP"
        if returncode and not self.summaries and not self.cases:
            self.messages.append(("error", "Tests/run.py ended with exit code %s; see Output (L)." % returncode))

    def counts(self):
        statuses = [case["status"] for case in self.cases.values()]
        return {status: statuses.count(status) for status in MARKERS}

    # =========================================================================
    # ================================= EVENTS ================================

    def _on_suite(self, event):
        self.suites.append(event.get("name", ""))

    def _on_case_start(self, event):
        case = self._case(event["id"])
        case.update(status="RUN", group=event.get("group", ""), started=event.get("t"), log=event.get("log"))

    def _on_case_end(self, event):
        case = self._case(event["id"])
        case.update(status=event.get("status", "FAIL"), seconds=event.get("seconds"), exit=event.get("exit", ""),
                    log=event.get("log") or case["log"], details=list(event.get("details") or ()))

    def _on_summary(self, event):
        self.summaries.append(event)

    def _on_warning(self, event):
        self._message("warning", event.get("message", ""))

    def _on_error(self, event):
        self._message("error", event.get("message", ""))

    # =========================================================================
    # ================================ HELPERS ================================

    def _case(self, name):
        if name not in self.cases:
            self.cases[name] = dict(id=name, group="", status="WAIT", started=None, seconds=None, exit="",
                                    log=None, details=[])
        return self.cases[name]

    def _message(self, role, text):
        self.messages.append((role, text))
        del self.messages[:-MESSAGES]

    # =========================================================================
    # ============================= CONSTRUCTION ==============================

    def __init__(self, expected=()):
        """expected: the case ids the run will report, shown as waiting until they start."""
        self.cases = {}
        self.suites = []
        self.summaries = []
        self.messages = []
        for name in expected:
            self._case(name)


# =============================================================================
# ================================== SCREEN ===================================


def follow_tests(ui, screen, title, process, expected=()):
    """Draw the run until the user leaves (only once it ended: leaving a
    running run stops it first); return its exit code."""
    ui._setup(screen)
    screen.timeout(int(FRAME * 1000))
    run = TestRun(expected)
    view = _View()
    while True:
        try:
            ended = process.poll() is not None  # before reading: then every event of an ended run is read
            if process.events is not None:
                run.feed(process.events.read())
            process.output.read()
            if ended and not view.finished:
                run.finish(process.returncode)
                view.finished = True
                if view.leave:
                    return process.returncode
            _draw(ui, screen, title, process, run, view)
            key = screen.getch()
        except KeyboardInterrupt:
            key = 3
        if _key(ui, key, process, run, view):
            return process.returncode


class _View:
    """Where the user is on the screen."""

    def __init__(self):
        self.mode = "cases"     # cases | case | output
        self.focus = 0
        self.offset = None      # first line of a log view; None: follow the end
        self.end = 0            # the first line of the last page of the log view
        self.page = 1           # lines of the log view
        self.confirm = False    # "stop the tests and go back?" is asked
        self.leave = False      # go back once the stopped run ended
        self.finished = False
        self.tails = {}         # case log path -> LogTail


# =============================================================================
# ================================== DRAWING ==================================


def _draw(ui, screen, title, process, run, view):
    screen.erase()
    height, width = screen.getmaxyx()
    ui._header(screen, title)
    state, role = _state(process, run)
    counts = run.counts()
    done = counts["PASS"] + counts["FAIL"] + counts["SKIP"]
    summary = "%s | %s | %d/%d done, %d passed, %d failed, %d skipped" % (
        state, _clock(process.elapsed()), done, len(run.cases), counts["PASS"], counts["FAIL"], counts["SKIP"])
    ui._line(screen, 1, max(1, width - len(summary) - 2), summary, color=ui.styles.get(role, 0))
    if height < 12 or width < 40:
        ui._line(screen, 3, 1, "Enlarge terminal (at least 40 x 12).")
    elif view.mode == "output" or not run.cases:
        lines = list(process.output.lines) + ([process.output.partial] if process.output.partial else [])
        _log(ui, screen, view, "Output of Tests/run.py", lines, height, width)
    elif view.mode == "case":
        case = _focused(run, view)
        _log(ui, screen, view, "Log: %s" % case["id"], _case_lines(view, case), height, width)
    else:
        _cases(ui, screen, run, view, height, width)
    ui._footer(screen, _footer(process, run, view))
    screen.refresh()


def _cases(ui, screen, run, view, height, width):
    top = 3
    for role, text in run.messages[-2:]:
        ui._line(screen, top, 1, ("! " + _printable(text))[:width - 2], color=ui.styles.get(role, 0))
        top += 1
    list_height = max(4, (height - top - 3) // 2)
    rect = ui._panel(screen, top, 1, list_height, width - 2, "Cases")
    row, left, rows, columns = rect
    cases = list(run.cases.values())
    view.focus = min(view.focus, len(cases) - 1)
    first = max(0, view.focus - rows + 1)
    for index, case in enumerate(cases[first:first + rows], first):
        label = "%s %s" % (MARKERS[case["status"]], case["id"])
        time_text = _case_time(case)
        line = label[:max(1, columns - len(time_text) - 1)].ljust(max(1, columns - len(time_text))) + time_text
        ui._line(screen, row + index - first, left, line[:columns], index == view.focus,
                 ui.styles.get(ROLES.get(case["status"]), 0))
    case = cases[view.focus]
    details = ui._panel(screen, top + list_height, 1, height - top - list_height - 3, width - 2,
                        "Details: %s" % case["id"])
    lines = [_case_state(case)] + [_printable(line) for line in case["details"]]
    log = _case_lines(view, case)
    if log:
        lines += ["--- last lines of the log ---"] + log[-max(1, details[2]):]
    ui._viewport(screen, details, [part for line in lines for part in ui._wrap(line, details[3])][-details[2]:], 0)


def _log(ui, screen, view, title, lines, height, width):
    """A scrollable log that follows its end until the user scrolls up."""
    rect = ui._panel(screen, 3, 1, height - 6, width - 2, title)
    lines = [part for line in lines for part in ui._wrap(_printable(line), rect[3])] or ["(no output yet)"]
    view.page = max(1, rect[2] - (1 if len(lines) > rect[2] else 0))
    view.end = max(0, len(lines) - view.page)
    if view.offset is not None and view.offset >= view.end:
        view.offset = None  # scrolled back to the end: follow it again
    ui._viewport(screen, rect, lines, view.end if view.offset is None else view.offset)


def _footer(process, run, view):
    if view.confirm:
        return "Stop the tests and go back? Y Yes | N No"
    if process.returncode is None and process.cancelled:
        return "Stopping the tests..."
    stop = "" if process.returncode is not None else " | S Stop"
    if view.mode != "cases" or not run.cases:
        return "Up/Down/PgUp/PgDn Scroll | End Follow" + stop + " | Esc Back"
    return "Up/Down Case | Enter Case log | L Output" + stop + " | Esc Back"


def _state(process, run):
    if process.returncode is None:
        return ("STOPPING", "warning") if process.cancelled else ("RUNNING", "accent")
    if process.cancelled:
        return "STOPPED", "warning"
    return ("PASSED", "good") if process.returncode == 0 else ("FAILED", "error")


# =============================================================================
# ==================================== KEYS ===================================


def _key(ui, key, process, run, view):
    """Handle one key; True: leave the screen."""
    curses = ui.curses
    if view.confirm:
        if key in (ord("y"), ord("Y")):
            view.confirm, view.leave = False, True
            process.cancel()
        elif key in (ord("n"), ord("N"), 27):
            view.confirm = False
        return False
    if key in (3, ord("s"), ord("S")):
        process.cancel()
    elif key == 27:
        if view.mode != "cases" and run.cases:
            view.mode, view.offset = "cases", None
        elif process.returncode is not None:
            return True
        else:
            view.confirm = True
    elif key in (ord("l"), ord("L")):
        view.mode, view.offset = ("cases" if view.mode == "output" else "output"), None
    elif view.mode == "cases" and run.cases:
        if key in (curses.KEY_UP, curses.KEY_DOWN):
            view.focus = (view.focus + (1 if key == curses.KEY_DOWN else -1)) % len(run.cases)
        elif key in (10, 13, curses.KEY_ENTER):
            view.mode, view.offset = "case", None
    else:
        step = {curses.KEY_UP: -1, curses.KEY_DOWN: 1, curses.KEY_PPAGE: -view.page, curses.KEY_NPAGE: view.page}
        if key in step:
            view.offset = max(0, (view.end if view.offset is None else view.offset) + step[key])
        elif key == getattr(curses, "KEY_END", None):
            view.offset = None
    return False


# =============================================================================
# ================================ HELPERS ====================================


def _focused(run, view):
    return list(run.cases.values())[min(view.focus, len(run.cases) - 1)]


def _case_lines(view, case):
    """The case log as far as it was written (read only while it is on screen)."""
    path = case["log"]
    if not path:
        return []
    tail = view.tails.get(path)
    if tail is None:
        tail = view.tails[path] = LogTail(path, CASE_LOG_LINES)
    tail.read()
    return [_printable(line) for line in tail.lines] + ([_printable(tail.partial)] if tail.partial else [])


def _case_state(case):
    if case["status"] == "WAIT":
        return "Waiting to start."
    if case["status"] == "RUN":
        return "Running for %s." % _case_time(case)
    if case["status"] == "STOP":
        return "Stopped with the run."
    return "%s after %s%s" % (case["status"], _case_time(case), " (%s)" % case["exit"] if case["exit"] else "")


def _case_time(case):
    if case["status"] == "RUN" and case["started"]:
        return _clock(time.time() - case["started"])
    if case["seconds"] is not None:
        return "%.1fs" % case["seconds"] if case["seconds"] < 60 else _clock(case["seconds"])
    return ""


def _clock(seconds):
    minutes, seconds = divmod(int(max(0, seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    return "%d:%02d:%02d" % (hours, minutes, seconds) if hours else "%02d:%02d" % (minutes, seconds)


def _printable(text):
    """A line curses can draw: no color codes or control characters, tabs as spaces."""
    return CONTROL.sub("", str(text)).expandtabs(4)
