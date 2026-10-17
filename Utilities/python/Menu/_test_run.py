# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""The screen that follows a test run while Tests/run.py works behind the menu.

The run is a TauFW.Utilities.Process.Operation (its supervisor runs
Tests/run.py): its events (Tests/support/events.py) build a TestRun, its
output log is the "Output" view, and every case log is read only while that
case is on screen:

    process.events ─▶ TestRun.feed() ─▶ Cases list + Details (focused case)
    process.output ─────────────────▶ Output view (L)
    case log       ─────────────────▶ Details / Case log view (Enter)
    process.state() ────────────────▶ RUNNING, STOPPING, PASSED, FAILED, STOPPED or LOST (+ "on <host>")

The screen draws ten times a second and never waits for the run. Leaving it
(Esc) never stops the run: it goes on behind the menu, which shows its state
(test_summary) and opens this screen again. S or Ctrl-C asks, then stops it.
No Framework imports belong here; _menu.py imports this module only when a
test run is shown (FastSetup imports Menu before TauFW is built).
"""
import re
import time

from ._menu import _clock
from ..Process import EventReader, LogTail
from ..Process._operations import ACTIVE, DONE, FAILED, LOST, RUNNING, STOPPED, STOPPING

__all__ = ["TestRun", "follow_tests", "test_summary"]


# =============================================================================
# ================================= CONSTANTS =================================


FRAME = 0.1           # seconds between frames
CASE_LOG_LINES = 400  # lines of a case log kept on screen
MESSAGES = 50         # warnings and errors kept
MARKERS = {"WAIT": "[    ]", "RUN": "[ RUN]", "PASS": "[PASS]", "FAIL": "[FAIL]", "SKIP": "[SKIP]",
           "STOP": "[STOP]"}
ROLES = {"RUN": "accent", "PASS": "good", "FAIL": "error", "SKIP": "waiting", "STOP": "warning"}
STATES = {RUNNING: ("RUNNING", "accent"), STOPPING: ("STOPPING", "warning"), DONE: ("PASSED", "good"),
          FAILED: ("FAILED", "error"), STOPPED: ("STOPPED", "warning"), LOST: ("LOST", "warning")}
LOST_TEXT = ("The run gave no sign of life for minutes: its login session ended or its machine restarted. "
             "Its cases did not finish; start the tests again.")
CONTROL = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|[\x00-\x08\x0b-\x1f\x7f]")


# =============================================================================
# ================================= TEST RUN ==================================


class TestRun:
    """What the screen knows about a test run, from its events. cases: key ->
    dict(id, suite, label, group, status, started, seconds, exit, log, details),
    in the order they were expected or started; messages: (role, text).

    expected: case ids (one family), or [suite, id] pairs ("all": the same id
    may be in two suites, e.g. plotter.unroll in normal and bbb). With pairs a
    case is keyed and labelled "suite: id", and its events find it through the
    suite that runs (the `suite` event)."""

    def feed(self, events):
        for event in events:
            handler = getattr(self, "_on_" + event["kind"], None)
            if handler:
                handler(event)

    def finish(self, returncode, lost=False):
        """The run ended (lost: it was lost, see LOST_TEXT): a case still running was stopped with it."""
        for case in self.cases.values():
            if case["status"] == "RUN":
                case["status"] = "STOP"
        if lost:
            self._message("warning", LOST_TEXT)
        elif returncode and not self.summaries and not self.cases:
            self.messages.append(("error", "Tests/run.py ended with exit code %s; see Output (L)." % returncode))

    def counts(self):
        statuses = [case["status"] for case in self.cases.values()]
        return {status: statuses.count(status) for status in MARKERS}

    # =========================================================================
    # ================================= EVENTS ================================

    def _on_suite(self, event):
        self.suites.append(event.get("name", ""))

    def _on_case_start(self, event):
        case = self._case(event["id"], self.suites[-1] if self.suites else None)
        case.update(status="RUN", group=event.get("group", ""), started=event.get("t"), log=event.get("log"))

    def _on_case_end(self, event):
        case = self._case(event["id"], self.suites[-1] if self.suites else None)
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

    def _case(self, name, suite=None):
        key = "%s: %s" % (suite, name) if self.paired and suite else name
        if key not in self.cases and name in self.cases:
            key = name  # expected without a suite
        if key not in self.cases:
            self.cases[key] = dict(id=name, suite=suite, label=key, group="", status="WAIT", started=None,
                                   seconds=None, exit="", log=None, details=[])
        return self.cases[key]

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
        self.paired = any(not isinstance(item, str) for item in expected)
        for item in expected:
            if isinstance(item, str):
                self._case(item)
            else:
                self._case(item[1], item[0])


# =============================================================================
# ================================== SCREEN ===================================


def follow_tests(ui, screen, title, process, expected=()):
    """Draw the run until the user leaves; the run goes on behind the menu.
    Return its exit code, None while it runs (or once it was lost)."""
    ui._setup(screen)
    screen.timeout(int(FRAME * 1000))
    run = TestRun(expected)
    view = _View()
    while True:
        try:
            state = process.state()  # before reading: then every event of an ended run is read
            if process.events is not None:
                run.feed(process.events.read())
            process.output.read()
            if state not in ACTIVE and not view.finished:
                run.finish(process.returncode, lost=state == LOST)
                view.finished = True
            _draw(ui, screen, title, process, run, view, state)
            key = screen.getch()
        except KeyboardInterrupt:
            key = 3
        if _key(ui, key, process, run, view, state):
            return process.returncode


def test_summary(operation):
    """(text, role) of a test run for the menus: "Running 12/40", "Failed: 3", "Done", "Stopping", "Stopped",
    "Lost"; role: a style name of ConsoleUI."""
    state = operation.state()
    run = TestRun(operation.data.get("expected", ()))
    run.feed(EventReader(operation.events_path).read())  # a reader of its own: the screen's stays at the top
    counts = run.counts()
    if state == RUNNING:
        done = counts["PASS"] + counts["FAIL"] + counts["SKIP"]
        text = "Running %d/%d" % (done, len(run.cases)) if run.cases else "Running"
    elif state == FAILED:
        text = "Failed: %d" % counts["FAIL"] if counts["FAIL"] else "Failed"
    else:
        text = state.capitalize()
    return text, STATES[state][1]


class _View:
    """Where the user is on the screen."""

    def __init__(self):
        self.mode = "cases"     # cases | case | output
        self.focus = 0
        self.offset = None      # first line of a log view; None: follow the end
        self.end = 0            # the first line of the last page of the log view
        self.page = 1           # lines of the log view
        self.confirm = False    # "stop the tests?" is asked
        self.finished = False
        self.tails = {}         # case log path -> LogTail


# =============================================================================
# ================================== DRAWING ==================================


def _draw(ui, screen, title, process, run, view, state):
    screen.erase()
    height, width = screen.getmaxyx()
    ui._header(screen, title)
    text, role = _state(process, state)
    counts = run.counts()
    done = counts["PASS"] + counts["FAIL"] + counts["SKIP"]
    summary = "%s | %s | %d/%d done, %d passed, %d failed, %d skipped" % (
        text, _clock(process.elapsed()), done, len(run.cases), counts["PASS"], counts["FAIL"], counts["SKIP"])
    column = width - len(summary) - 2
    row = 1 if column > len(title) + 3 else 2  # no room next to the title: on the free line below it
    ui._line(screen, row, max(1, column) if row == 1 else 1, summary, color=ui.styles.get(role, 0))
    if height < 12 or width < 40:
        ui._line(screen, 3, 1, "Enlarge terminal (at least 40 x 12).")
    elif view.mode == "output" or not run.cases:
        lines = list(process.output.lines) + ([process.output.partial] if process.output.partial else [])
        _log(ui, screen, view, "Output of Tests/run.py", lines, height, width)
    elif view.mode == "case":
        case = _focused(run, view)
        _log(ui, screen, view, "Log: %s" % case["label"], _case_lines(view, case), height, width)
    else:
        _cases(ui, screen, run, view, height, width)
    ui._footer(screen, _footer(run, view, state))
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
        label = "%s %s" % (MARKERS[case["status"]], case["label"])
        time_text = _case_time(case)
        line = label[:max(1, columns - len(time_text) - 1)].ljust(max(1, columns - len(time_text))) + time_text
        ui._line(screen, row + index - first, left, line[:columns], index == view.focus,
                 ui.styles.get(ROLES.get(case["status"]), 0))
    case = cases[view.focus]
    details = ui._panel(screen, top + list_height, 1, height - top - list_height - 3, width - 2,
                        "Details: %s" % case["label"])
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


def _footer(run, view, state):
    if view.confirm:
        return "Stop the tests? Y Yes | N No"
    stop = " | S Stop" if state == RUNNING else ""
    back = " | Esc Back (keeps running)" if state in ACTIVE else " | Esc Back"
    if state == STOPPING:
        return "Stopping the tests..." + back
    if view.mode != "cases" or not run.cases:
        return "Up/Down/PgUp/PgDn Scroll | End Follow" + stop + back
    return "Up/Down Case | Enter Case log | L Output" + stop + back


def _state(process, state):
    """(text, role) of the state line; a run started on another machine says where it runs."""
    text, role = STATES[state]
    if state in ACTIVE and getattr(process, "remote", False):
        text = "%s on %s" % (text, process.host)
    return text, role


# =============================================================================
# ==================================== KEYS ===================================


def _key(ui, key, process, run, view, state):
    """Handle one key; True: leave the screen (the run goes on)."""
    curses = ui.curses
    if view.confirm:
        if key in (ord("y"), ord("Y")):
            view.confirm = False
            process.cancel()
        elif key in (ord("n"), ord("N"), 27):
            view.confirm = False
        return False
    if key in (3, ord("s"), ord("S")):
        view.confirm = state == RUNNING
    elif key == 27:
        if view.mode != "cases" and run.cases:
            view.mode, view.offset = "cases", None
        else:
            return True
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


def _printable(text):
    """A line curses can draw: no color codes or control characters, tabs as spaces."""
    return CONTROL.sub("", str(text)).expandtabs(4)
