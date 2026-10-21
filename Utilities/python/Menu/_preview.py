# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""UI preview (Tests > UI preview): every menu screen with made-up data, to look at them without a run.

The screens are the real ConsoleUI methods; only their data is made up. A
made-up test run is an Operation whose files (events, output, case logs) a
script writes while the screen reads them, so it moves like a real one:

    SCENARIOS[i].show(ui, directory) ─▶ the real screen ─▶ _Screen: Left/Right other screen, R again,
                                                                      the preview bar on the last line
    _MockOperation.state() ─▶ writes the scripted events and lines that are due ─▶ the screen reads the files

Every screen draws on the preview's one curses screen: _Curses.wrapper()
hands it over instead of opening a new one. A screen left with Esc leaves the
preview; any other answer shows the same screen again, with the answer in the
bar. Nothing is started and nothing is written outside a temporary directory,
removed when the preview closes. It is not a test family: the unit tests only
check that every scenario draws. No Framework imports belong here; _menu.py
imports this module only when the preview opens (see ConsoleUI.test_run()).
"""
import collections
import json
import os
import socket
import tempfile
import time

from ._menu import ConsoleUI
from .setup_menu import COMPONENTS
from ..Process._operations import DONE, FAILED, LOST, RUNNING, STOPPED, STOPPING, Operation

__all__ = ["preview", "SCENARIOS"]


# =============================================================================
# ================================= CONSTANTS =================================


STOP_TAKES = 1.5         # seconds a made-up run takes to stop
REMOTE_HOST = "lxplus812.cern.ch"
Scenario = collections.namedtuple("Scenario", "group name show")


# =============================================================================
# ================================= PREVIEW ===================================


def preview(curses, screen):
    """Show the scenarios on `screen` until one is left with Esc (or Ctrl-C)."""
    with tempfile.TemporaryDirectory(prefix="taufw-preview-") as root:
        proxy = _Screen(screen, curses)
        ui = ConsoleUI(_Curses(curses, proxy))
        index, note, shown = 0, "", 0
        while True:
            scenario = SCENARIOS[index]
            shown += 1
            proxy.bar = _bar(index, scenario, note)
            proxy.last = None
            try:
                answer = scenario.show(ui, os.path.join(root, str(shown)))
            except _Switch as switch:
                index, note = (index + switch.step) % len(SCENARIOS), ""
                continue
            except KeyboardInterrupt:
                return
            if proxy.last == 27:
                return
            note = "answered %r" % (answer,)


def _bar(index, scenario, note):
    text = " UI preview %d/%d  %s: %s  | Left/Right Screen | R Again | Esc Leave" % (
        index + 1, len(SCENARIOS), scenario.group, scenario.name)
    return text + ("  [%s]" % note if note else "")


class _Switch(Exception):
    """Show another scenario (step -1 or 1) or the same one again (0)."""

    def __init__(self, step):
        super().__init__(step)
        self.step = step


class _Screen:
    """The curses screen of the screens in the preview: Left/Right and R switch scenarios, every frame gets the
    preview bar on its last line (the screens leave it free), and the last key is kept (Esc leaves)."""

    def getch(self):
        return self._key(self.screen.getch())

    def get_wch(self):
        return self._key(self.screen.get_wch(), typed=True)

    def refresh(self):
        height, width = self.screen.getmaxyx()
        try:
            self.screen.addnstr(height - 1, 0, self.bar.ljust(width), width - 1, self.curses.A_REVERSE)
        except self.curses.error:
            pass  # A resize may have happened between size and draw.
        self.screen.refresh()

    def _key(self, key, typed=False):
        if key in (self.curses.KEY_LEFT, self.curses.KEY_RIGHT):
            raise _Switch(-1 if key == self.curses.KEY_LEFT else 1)
        if not typed and key in (ord("r"), ord("R")):  # an input field takes R as a letter
            raise _Switch(0)
        self.last = 27 if key in (27, "\x1b") else key
        return key

    def __getattr__(self, name):
        return getattr(self.screen, name)

    def __init__(self, screen, curses):
        self.screen = screen
        self.curses = curses
        self.bar = ""
        self.last = None


class _Curses:
    """The curses module for the screens in the preview: wrapper() draws on the preview's screen."""

    def wrapper(self, action):
        self._screen.timeout(-1)  # a screen that follows a run waits only a frame for a key
        return action(self._screen)

    def __getattr__(self, name):
        return getattr(self._curses, name)

    def __init__(self, curses, screen):
        self._curses = curses
        self._screen = screen


# =============================================================================
# =========================== MADE-UP OPERATIONS ==============================


class _MockOperation(Operation):
    """A made-up operation behind the menu (a test run, an advance): an Operation (TauFW.Utilities.Process) whose
    files a script writes while a screen reads them. script: (seconds after the start, what) in order; what: an
    event dict (a "log" field names a file of the directory), ("output", line) or ("log", name, line). ago: it
    started that many seconds ago (the script up to then is written at once); end: DONE, FAILED, STOPPED or LOST
    once the script is done, RUNNING: it never ends. S (stop) stops it after STOP_TAKES seconds."""

    def state(self):
        if self.poll() is not None:
            return STOPPED if self.stopped else (DONE if self.returncode == 0 else FAILED)
        if self._gone:
            return LOST
        return STOPPING if self.cancelled else RUNNING

    def poll(self):
        self._play()
        return self.returncode

    @property
    def cancelled(self):
        return self._stop is not None

    def cancel(self):
        if self.poll() is None and self._stop is None:
            self._stop = self.clock()

    kill = cancel

    @property
    def remote(self):
        return self._remote

    # =========================================================================
    # ================================ HELPERS ================================

    def _play(self):
        if self.returncode is not None or self._gone:
            return
        now = self.clock()
        while self._script and self._script[0][0] <= now - self.started:
            self._at, what = self._script.pop(0)
            self._write(what)
        if self._stop is not None and now - self._stop >= STOP_TAKES:
            self._write(("output", "KeyboardInterrupt: stopped from the menu."))
            self.returncode, self.stopped, self.finished = 130, True, now
        elif not self._script:
            if self._end == LOST:
                self._gone = True
            elif self._end == STOPPED:
                self.returncode, self.stopped, self.finished = 130, True, self.started + self._at
            elif self._end != RUNNING:
                self.returncode, self.finished = (0 if self._end == DONE else 1), self.started + self._at

    def _write(self, what):
        if isinstance(what, dict):
            fields = dict(what)
            if fields.get("log"):
                fields["log"] = self._path(fields["log"])
            fields.update(t=self.started + self._at)  # when the script says, also for what is written at once
            with open(self.events_path, "a", encoding="utf-8") as stream:
                stream.write(json.dumps(fields) + "\n")
            return
        path = self.output_path if what[0] == "output" else self._path(what[1])
        with open(path, "a", encoding="utf-8") as stream:
            stream.write(what[-1] + "\n")

    # =========================================================================
    # ============================= CONSTRUCTION ==============================

    def __init__(self, directory, kind, title, data, script, end=DONE, ago=0.0, remote=False, clock=time.time):
        os.makedirs(directory)
        record = dict(kind=kind, title=title, data=data, started=clock() - ago,
                      host=REMOTE_HOST if remote else socket.gethostname())
        super().__init__(directory, record, clock=clock)
        self._script = list(script)
        self._end = end
        self._remote = remote
        self._stop = None
        self._gone = False
        self._at = 0.0
        open(self.output_path, "a").close()
        self._play()


# id, group (file), seconds, log lines
NORMAL_CASES = (
    ("utilities.parallel", "Tests/Utilities/test_process.py", 2.5,
     ["Ran 14 tests in 2.311s", "OK"]),
    ("framework.recipe_check", "Tests/Framework/test_recipe.py", 3.0,
     ["Checking recipes/tes_2025.yml", "5 stages, 0 problems, 1 warning", "OK"]),
    ("histogrammer.shapes", "Histogrammer/shapes/run_shapes.py", 6.0,
     ["Processing mutau 2025: 41 samples", "Processing etau 2025: 39 samples",
      "Writing histograms/mutau_2025.root", "Writing histograms/etau_2025.root"]),
    ("plotter.unroll", "Plotter/test/plot_unroll.py", 5.0,
     ["Info in <TCanvas::Print>: png file plots/unroll_mvis_pt.png has been created",
      "Info in <TCanvas::Print>: pdf file plots/unroll_mvis_pt.pdf has been created"]),
    ("plotter.stack", "Plotter/test/plot_stack.py", 4.0,
     ["Info in <TCanvas::Print>: png file plots/stack_m_vis.png has been created",
      "Warning in <TH1F::Divide>: some bins of the denominator are empty"]),
    ("fitter.datacards", "Fitter/test/datacards.py", 4.5,
     ["Writing datacards/mutau_2025_DM0.txt", "Writing datacards/mutau_2025_DM1.txt", "12 datacards written"]),
    ("fitter.tes_id", "Fitter/test/tes_id.py", 3.5,
     ["Fit tes_DM0: tes = 0.987 +0.008 -0.009", "Fit tes_DM1: tes = 1.003 +0.006 -0.006"]),
)
FAILURE_LOG = ["Traceback (most recent call last):",
               '  File "Fitter/test/datacards.py", line 88, in <module>',
               "    write_cards(shapes, channel)",
               '  File "Fitter/python/api/datacards.py", line 141, in write_cards',
               "    raise KeyError(name)",
               "KeyError: 'ZTT_DM10'"]
FAILURE_DETAILS = ["histograms/mutau_2025.root: ZTT_DM10 is missing",
                   "expected 24 shapes, found 23"]


def _test_script(skip=None, fail=None, stop_after=None):
    """The script of a normal test run (see _MockOperation): skip, fail: a case id that skips or fails;
    stop_after: the script ends with the case of that index running."""
    steps = [(0.0, dict(kind="suite", name="normal", total=len(NORMAL_CASES))),
             (0.0, ("output", "Running %d normal tests (quiet; logs under .artifacts/tests/normal)"
                    % len(NORMAL_CASES)))]
    at, counts = 0.5, dict(PASS=0, FAIL=0, SKIP=0)
    for index, (name, group, seconds, lines) in enumerate(NORMAL_CASES):
        log = name + ".log"
        status = "SKIP" if name == skip else "FAIL" if name == fail else "PASS"
        if status == "SKIP":
            lines, seconds = ["SKIP: Combine is not installed (FastSetup: Combine + CombineHarvester)"], 0.4
        elif status == "FAIL":
            lines = lines[:1] + FAILURE_LOG
        steps.append((at, dict(kind="case_start", id=name, group=group, log=log)))
        for number, line in enumerate(lines, 1):
            steps.append((at + seconds * number / (len(lines) + 1), ("log", log, line)))
        if stop_after == index:
            return steps
        at += seconds
        counts[status] += 1
        steps.append((at, dict(kind="case_end", id=name, status=status, seconds=seconds, log=log,
                               exit="exit 1" if status == "FAIL" else "",
                               details=FAILURE_DETAILS if status == "FAIL" else [])))
        if status == "FAIL":
            steps.append((at, ("output", "FAIL %s (exit 1); log: %s" % (name, log))))
        at += 0.3
    steps.append((at, dict(kind="summary", name="normal", passed=counts["PASS"], failed=counts["FAIL"],
                           skipped=counts["SKIP"], interrupted=False, seconds=at)))
    steps.append((at, ("output", "%d passed, %d failed, %d skipped in %.1fs"
                       % (counts["PASS"], counts["FAIL"], counts["SKIP"], at))))
    return steps


def _tests(directory, kind="running", **options):
    """A made-up normal test run: running (live; ends PASSED), failed (ended), remote (live, another
    machine) or lost."""
    expected = [name for name, _, _, _ in NORMAL_CASES]
    if kind == "failed":
        script = _test_script(skip="fitter.tes_id", fail="fitter.datacards")
        options = dict(dict(end=FAILED, ago=60.0), **options)
    elif kind == "lost":
        script = _test_script(stop_after=3)
        options = dict(dict(end=LOST, ago=900.0), **options)
    else:
        script = _test_script(skip="fitter.tes_id")
        options = dict(dict(remote=kind == "remote"), **options)
    return _MockOperation(directory, "tests", "Normal tests", dict(expected=expected), script, **options)


RUN_ID = "tes_2025"
RUN_DIR = "/eos/user/u/username/taufw_runs/tes_2025_20261018-140211"
RUN_STAGES = (("ntuples", "production"), ("histograms", "histogrammer"), ("plots", "plotter"), ("fit", "fitter"),
              ("results", "local"))
PLOTS = [("etau", "2025"), ("mutau", "2025"), ("mumu", "2025"), ("etau", "2024"), ("mutau", "2024"),
         ("mumu", "2024"), ("tautau", "2025")]
# stage -> (label, seconds, log lines) of its local commands
RUN_COMMANDS = {
    "plots": [("%s %s" % pair, 3.0, ["Info in <TCanvas::Print>: png file %s_%s_m_vis.png has been created" % pair,
                                     "Info in <TCanvas::Print>: png file %s_%s_pt_1.png has been created" % pair])
              for pair in PLOTS],
    "fit": [("tes_DM%d" % mode, 4.0, ["combine -M MultiDimFit datacards/tes_DM%d.txt" % mode,
                                      "tes = %.3f +0.008 -0.009" % (0.99 + 0.005 * mode)]) for mode in (0, 1, 10)],
    "results": [("summary table", 1.5, ["Writing results/tes_summary.tex"])],
}
FAILED_COMMAND = ("mumu 2025", ["Error in <TFile::TFile>: file histograms/mumu_2025.root does not exist",
                                "ValueError: no histogram m_vis for mumu 2025"])


# stage -> its facts, as the Framework will supply them (made up: the real fields are chosen at the wiring)
RUN_INFO = {
    "ntuples": [("Config", "configs/pico_2025.yml"), ("Era", "2025"), ("Channels", "mutau etau"),
                ("Samples", "41 (852 jobs)"), ("Storage", "/eos/user/u/username/samples/nano_2025"), ("Attempt", "1")],
    "histograms": [("Config", "Histogrammer/shapes/tes_2025.yml"), ("Input", "ntuples"),
                   ("Variables", "m_vis pt_1 m_2"), ("Output", "stages/histograms/")],
    "plots": [("Config", "Plotter/config/plots_2025.yml"), ("Input", "histograms"),
              ("Channels", "etau mutau mumu tautau"), ("Years", "2024 2025"), ("Output", "stages/plots/")],
    "fit": [("Config", "Fitter/TauES/config_tes_2025.yml"), ("Input", "histograms"), ("Decay modes", "DM0 DM1 DM10"),
            ("POI", "tes"), ("Output", "stages/fit/")],
    "results": [("Command", "Fitter/TauES/summary.py"), ("Input", "fit"), ("Output", "stages/results/")],
}


def _run_data(states):
    return dict(run_id=RUN_ID, run_dir=RUN_DIR,
                stages=[dict(id=name, type=kind, state=states.get(name, "NEW"), message="",
                             info=[list(fact) for fact in RUN_INFO[name]])
                        for name, kind in RUN_STAGES])


def _advance_script(stages, fail=None, stop=None):
    """The script of an advance (see _MockOperation) of local stages: fail: the label of the plots command that
    fails; stop: the script ends with the plots command of that index running."""
    steps = [(0.0, dict(kind="run", run_id=RUN_ID, run_dir=RUN_DIR)),
             (0.0, ("output", ">>> Advancing run %s" % RUN_ID))]
    at = 0.5
    for name in stages:
        steps += [(at, dict(kind="stage_step", stage=name, type=dict(RUN_STAGES)[name], state="NEW")),
                  (at, ("output", ">>> Stage %s (NEW)" % name))]
        commands = RUN_COMMANDS[name]
        for index, (label, seconds, lines) in enumerate(commands, 1):
            log = "%s_%s.log" % (name, label.replace(" ", "_"))
            failed = name == "plots" and label == fail
            lines = FAILED_COMMAND[1] if failed else lines
            steps += [(at, dict(kind="progress", stage=name, index=index, total=len(commands), label=label,
                                status="run", log=log)),
                      (at, ("output", "[%s] %d/%d %s ..." % (name, index, len(commands), label)))]
            steps += [(at + seconds * number / (len(lines) + 1), ("log", log, line))
                      for number, line in enumerate(lines, 1)]
            if name == "plots" and stop == index:
                return steps
            at += seconds
            outcome = "FAILED" if failed else "ok"
            steps += [(at, dict(kind="progress", stage=name, index=index, total=len(commands), label=label,
                                status=outcome.lower(), seconds=seconds, log=log)),
                      (at, ("output", "[%s] %d/%d %s %s (%.0f s)" % (name, index, len(commands), label, outcome,
                                                                    seconds)))]
            if failed:
                message = "%s: exit code 1; log: %s/logs/plots/%s" % (label, RUN_DIR, log)
                return steps + [(at, dict(kind="warning", text="Command %r failed (exit code 1)." % label)),
                                (at, dict(kind="stage_state", stage=name, state="FAILED", message=message)),
                                (at, dict(kind="run_state", run_id=RUN_ID, state="FAILED")),
                                (at, ("output", "Run %s: FAILED" % RUN_ID))]
        steps += [(at, dict(kind="stage_state", stage=name, state="DONE",
                            message="%d command(s) ran" % len(commands))),
                  (at, ("output", "Stage %s: DONE" % name))]
        at += 0.5
    return steps + [(at, dict(kind="run_state", run_id=RUN_ID, state="DONE")),
                    (at, ("output", "Run %s: DONE" % RUN_ID))]


def _jobs_script(checks=4, poll=15.0, wait=True, first=0):
    """An advance of a production stage whose jobs run: a check every `poll` seconds (wait: with --wait)."""
    steps, at = [(0.0, dict(kind="run", run_id=RUN_ID, run_dir=RUN_DIR))], 0.5
    for check in range(first, first + checks):
        done = 270 * check
        before, after = ("NEW", "SUBMITTED") if check == 0 else ("WAITING", "WAITING")
        message = ("852 jobs submitted in 41 samples" if check == 0 else
                   "jobs: %d done, %d running, %d idle" % (done, 852 - done - 12, 12))
        steps += [(at, dict(kind="stage_step", stage="ntuples", type="production", state=before)),
                  (at, ("output", ">>> Stage ntuples (%s)" % before)),
                  (at + 1.0, dict(kind="stage_state", stage="ntuples", state=after, message=message)),
                  (at + 1.0, ("output", "Stage ntuples: %s - %s" % (after, message))),
                  (at + 1.0, dict(kind="run_state", run_id=RUN_ID, state="WAITING"))]
        if wait:
            steps += [(at + 1.0, dict(kind="wait", seconds=poll)),
                      (at + 1.0, ("output", "Waiting %d s before the next check..." % poll))]
        at += 1.0 + poll
    return steps


def _advance(directory, kind="advancing", run_id=None, **options):
    """A made-up advance of RUN_ID: advancing (live; ends complete), jobs (live, Advance to the end), complete,
    waiting (an Advance once that ended), failed, stopped or lost."""
    local = ("plots", "fit", "results")
    data = _run_data(dict(ntuples="DONE", histograms="DONE"))
    if kind == "jobs":
        data, script, end = _run_data({}), _jobs_script(), RUNNING
    elif kind == "waiting":
        data, script, end = _run_data(dict(ntuples="WAITING")), _jobs_script(checks=1, wait=False, first=3), DONE
    elif kind == "failed":
        script, end = _advance_script(local, fail=FAILED_COMMAND[0]), FAILED
    elif kind in ("stopped", "lost"):
        script, end = _advance_script(local, stop=4), STOPPED if kind == "stopped" else LOST
    else:
        script, end = _advance_script(local), DONE
    options = dict(dict(end=end, ago=0.0 if kind in ("advancing", "jobs") else 3600.0), **options)
    if run_id:
        data["run_id"] = run_id
    return _MockOperation(directory, "run", "Run %s" % data["run_id"], data, script, **options)


# =============================================================================
# ============================= MADE-UP SCREENS ===============================


TEST_ITEMS = [dict(id=name, description="Runs %s and checks that it exits cleanly." % group,
                   dependencies=["ROOT"] if "Plotter" in group or "Histogrammer" in group else [])
              for name, group, _, _ in NORMAL_CASES]
STAGES = [("ntuples", "production", "NanoAOD skims on HTCondor"),
          ("histograms", "histogrammer", "Shapes per channel and year"),
          ("plots", "plotter", "Control plots"),
          ("fit", "fitter", "TES fit per decay mode"),
          ("results", "local", "Summary tables")]
RECIPES = [dict(name="tes_2025.yml", stages=STAGES,
                notes=["ntuples: 852 jobs in 41 samples; the first advance submits them."]),
           dict(name="etau_fr_2024.yml", stages=STAGES[:3],
                warnings=["plots: `lumi` is not set; the 2024 default (109.1/fb) is used."]),
           dict(name="broken_example.yml", stages=STAGES[1:2],
                problems=["histograms: input `ntuples` is not produced by an earlier stage."])]
RUNS = [("tes_2025", "WAITING", "2026-10-18 14:02"), ("etau_fr_2024", "DONE", "2026-10-15 09:41"),
        ("mutau_2024", "FAILED", "2026-10-12 17:20"), ("copied_by_hand", None, None)]


def _recipes(ui, directory):
    return ui.select_recipe([view["name"] for view in RECIPES], preview=lambda index: RECIPES[index],
                            broken=[bool(view.get("problems")) for view in RECIPES],
                            warnings=[bool(view.get("warnings")) for view in RECIPES])


def _review(ui, directory):
    review = dict(RECIPES[0], path="/afs/cern.ch/user/u/username/TauFW/recipes/tes_2025.yml")
    return ui.confirm_recipe("recipes/tes_2025.yml", review=review, position={})


def _runs(directory, *kinds):
    """Made-up advances of different runs (kind, or (kind, run_id, ago)), each in a directory of its own."""
    operations = []
    for index, kind in enumerate(kinds):
        kind, run_id, ago = kind if isinstance(kind, tuple) else (kind, None, None)
        options = dict(ago=ago) if ago is not None else {}
        operations.append(_advance(os.path.join(directory, str(index)), kind, run_id=run_id, **options))
    return operations


LOCK = dict(host=REMOTE_HOST, pid=23411, since="2026-10-18 14:02")


def _run(kind, **options):
    def show(ui, directory):
        operation = _advance(directory, kind, **options)
        return ui.run_progress(operation.title, operation)
    return show


def _test_run(kind, **options):
    def show(ui, directory):
        operation = _tests(directory, kind, **options)
        return ui.test_run(operation.title, operation, operation.data["expected"])
    return show


SCENARIOS = [
    Scenario("Main menu", "idle", lambda ui, directory: ui.main_menu(proxy_valid=True)),
    Scenario("Main menu", "tests running, no grid proxy",
             lambda ui, directory: ui.main_menu(tests=_tests(directory, ago=12.0))),
    Scenario("Start a run", "select a recipe", _recipes),
    Scenario("Start a run", "review", _review),
    Scenario("Main menu", "a run advancing",
             lambda ui, directory: ui.main_menu(True, runs=_runs(directory, ("advancing", None, 14.0)))),
    Scenario("Main menu", "a run waiting for jobs",
             lambda ui, directory: ui.main_menu(True, runs=_runs(directory, ("jobs", None, 8.0)))),
    Scenario("Main menu", "a run failed (until its card is seen)",
             lambda ui, directory: ui.main_menu(True, runs=_runs(directory, "failed"))),
    Scenario("Main menu", "a run lost", lambda ui, directory: ui.main_menu(True, runs=_runs(directory, "lost"))),
    Scenario("Main menu", "two runs, one failed",
             lambda ui, directory: ui.main_menu(True, runs=_runs(directory, ("jobs", None, 8.0),
                                                                 ("failed", "etau_fr_2024", None)))),
    Scenario("Runs", "behind the menu",
             lambda ui, directory: ui.active_runs(_runs(directory, ("advancing", None, 14.0),
                                                        ("jobs", "etau_fr_2024", 8.0),
                                                        ("failed", "mutau_2024", None)))),
    Scenario("Continue", "select a run (one advancing)",
             lambda ui, directory: ui.select_run(RUNS, advances=_runs(directory, ("advancing", None, 14.0))
                                                 + [None] * (len(RUNS) - 1))),
    Scenario("Continue", "actions", lambda ui, directory: ui.continue_actions("tes_2025")),
    Scenario("Start / Continue", "grid proxy needed", lambda ui, directory: ui.grid_proxy_needed()),
    Scenario("Continue", "run that cannot advance", lambda ui, directory: ui.terminal_run_actions("DONE")),
    Scenario("Inspect", "status actions", lambda ui, directory: ui.status_actions("tes_2025")),
    Scenario("Tests", "menu, last run failed",
             lambda ui, directory: ui.tests_menu(last=_tests(directory, "failed"))),
    Scenario("Tests", "family", lambda ui, directory: ui.test_family("Normal tests")),
    Scenario("Tests", "choose tests", lambda ui, directory: ui.test_selection("Normal tests", TEST_ITEMS)),
    Scenario("Tests", "review", lambda ui, directory: ui.test_selection("Review / Normal tests", TEST_ITEMS,
                                                                        review=True)),
    Scenario("Test run", "running (ends passed)", _test_run("running")),
    Scenario("Test run", "failed", _test_run("failed")),
    Scenario("Test run", "on another machine", _test_run("remote", ago=4.0)),
    Scenario("Test run", "lost", _test_run("lost")),
    Scenario("Run", "advancing (ends complete)", _run("advancing")),
    Scenario("Run", "waiting for jobs, Advance to the end", _run("jobs")),
    Scenario("Run result", "complete", _run("complete")),
    Scenario("Run result", "waiting for jobs (Advance once)", _run("waiting")),
    Scenario("Run result", "failed", _run("failed")),
    Scenario("Run result", "stopped", _run("stopped")),
    Scenario("Run result", "lost", _run("lost")),
    Scenario("Run lock", "an advance runs elsewhere",
             lambda ui, directory: ui.run_lock("tes_2025", dict(LOCK, quiet=12.0))),
    Scenario("Run lock", "the advance is lost, take over",
             lambda ui, directory: ui.run_lock("tes_2025", dict(LOCK, quiet=420.0, lost=True))),
    Scenario("Quit", "while tests run", lambda ui, directory: ui.quit_running([_tests(directory, ago=12.0)])),
    Scenario("Quit", "while tests and a run run",
             lambda ui, directory: ui.quit_running([_tests(os.path.join(directory, "tests"), ago=12.0)]
                                                   + _runs(directory, ("jobs", None, 8.0)))),
    Scenario("Help", "topics", lambda ui, directory: ui.help()),
    Scenario("FastSetup", "installer checklist",
             lambda ui, directory: ui.setup_checklist(COMPONENTS, ["tauidsfs", "combine"])),
]
