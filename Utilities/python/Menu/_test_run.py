# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""The screen that follows a test run while Tests/run.py works behind the menu.

The run is a TauFW.Utilities.Process.Operation (its supervisor runs
Tests/run.py); the screen is the operation screen (_operation_screen.py) with
TestRun as its model: the events (Tests/support/events.py) build the cases,
the output log is the "Output" view, and every case log is read only while
that case is on screen:

    process.events ─▶ TestRun.feed() ─▶ Cases list + Details (focused case)
    process.output ─────────────────▶ Output view (L)
    case log       ─────────────────▶ Details / Case log view (Enter)
    process.state() ────────────────▶ RUNNING, STOPPING, PASSED, FAILED, STOPPED or LOST (+ "on <host>")

Leaving it (Esc) never stops the run: it goes on behind the menu, which shows
its state (test_summary) and opens this screen again. S or Ctrl-C asks, then
stops it. No Framework imports belong here; _menu.py imports this module only
when a test run is shown (FastSetup imports Menu before TauFW is built).
"""
import time

from ._menu import _clock
from ._operation_screen import ScreenModel, follow
from ..Process import EventReader
from ..Process._operations import DONE, FAILED, LOST, RUNNING, STOPPED, STOPPING

__all__ = ["TestRun", "follow_tests", "test_summary"]


# =============================================================================
# ================================= CONSTANTS =================================


MESSAGES = 50         # warnings and errors kept
MARKERS = {"WAIT": "[    ]", "RUN": "[ RUN]", "PASS": "[PASS]", "FAIL": "[FAIL]", "SKIP": "[SKIP]",
           "STOP": "[STOP]"}
ROLES = {"RUN": "accent", "PASS": "good", "FAIL": "error", "SKIP": "waiting", "STOP": "warning"}
STATES = {RUNNING: ("RUNNING", "accent"), STOPPING: ("STOPPING", "warning"), DONE: ("PASSED", "good"),
          FAILED: ("FAILED", "error"), STOPPED: ("STOPPED", "warning"), LOST: ("LOST", "warning")}
LOST_TEXT = ("The run gave no sign of life for minutes: its login session ended or its machine restarted. "
             "Its cases did not finish; start the tests again.")


# =============================================================================
# ================================= TEST RUN ==================================


class TestRun(ScreenModel):
    """What the screen knows about a test run, from its events. cases: key ->
    dict(id, suite, label, group, status, started, seconds, exit, log, details),
    in the order they were expected or started; messages: (role, text). As the
    model of the operation screen, its items are the cases.

    expected: case ids (one family), or [suite, id] pairs ("all": the same id
    may be in two suites, e.g. plotter.unroll in normal and bbb). With pairs a
    case is keyed and labelled "suite: id", and its events find it through the
    suite that runs (the `suite` event)."""

    def feed(self, events):
        for event in events:
            handler = getattr(self, "_on_" + event["kind"], None)
            if handler:
                handler(event)

    def finish(self, returncode, lost=False, state=None):
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
    # ============================ SCREEN MODEL ===============================

    list_title = "Cases"
    item = "Case"
    output_title = "Output of Tests/run.py"
    stop_question = "Stop the tests?"
    stopping = "Stopping the tests..."
    states = STATES

    def items(self):
        return list(self.cases.values())

    def label(self, case):
        return case["label"]

    def row(self, case):
        return "%s %s" % (MARKERS[case["status"]], case["label"]), _case_time(case), ROLES.get(case["status"])

    def details(self, case):
        return [_case_state(case)] + list(case["details"])

    def log(self, case):
        return case["log"]

    def summary(self):
        counts = self.counts()
        done = counts["PASS"] + counts["FAIL"] + counts["SKIP"]
        return "%d/%d done, %d passed, %d failed, %d skipped" % (
            done, len(self.cases), counts["PASS"], counts["FAIL"], counts["SKIP"])

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
        super().__init__()
        self.cases = {}
        self.suites = []
        self.summaries = []
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
    return follow(ui, screen, title, process, TestRun(expected))


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


# =============================================================================
# ================================ HELPERS ====================================


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
