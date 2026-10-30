"""Menu navigation and dispatch without a real terminal, ROOT, or batch jobs."""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from types import SimpleNamespace

import checkout
from TauFW.Framework import Recipe, RunRecord
from TauFW.Framework._internal.interfaces.interactive import Menu, run_menu
from TauFW.Framework._internal.interfaces import interactive
from TauFW.Framework._internal.menu import ConsoleUI


class FakeUI(ConsoleUI):
    """Use production screen adapters with scripted terminal input."""
    def __init__(self, choices=(), prompts=()):
        super().__init__(None)
        self.choices = iter(choices)
        self.prompts = iter(prompts)
        self.screens = []
        self.messages = []  # (title, text) of each panel over the screen (errors)
        self.outputs = []  # (title, argv after taufw.py, refresh) of each command shown
        self.plans = []  # the view of each plan screen shown
        self.output_answers = iter(())  # what command_output answers ("back" once these are used)
        self.choice_views = []  # the view of each stage picker shown
        self.checks = []  # what the text panel's check said of each value typed
        self.edits = []  # (title, path, validate) of each file the editor opened

    def choose(self, title, choices, welcome=None, **layout):
        self.screens.append((title, choices))
        return next(self.choices)

    def prompt(self, title, default=""):
        return next(self.prompts)

    def ask_text(self, title, lines, label, check=None, default="", action="Accept"):
        """The text panel: the next prompt, after the check's answer for it is kept (checks)."""
        value = next(self.prompts)
        self.checks.append(check(value) if check and value is not None else None)
        return value

    def message(self, title, lines, role=None):
        lines = [(lines, role)] if isinstance(lines, str) else lines
        self.messages.append((title, " ".join(text for text, _ in lines)))

    def help(self):
        pass

    def select_recipe(self, names, preview=None, broken=None, warnings=None, examples=False, **layout):
        self.broken = broken
        return super().select_recipe(names, examples=examples)

    def recipe_plan(self, title, view, position=None, update=None):
        """The plan screen: the next choice is 0 Start run, 1 E (edit) or 2 Esc (back)."""
        self.plans.append(view)
        self.screens.append((title, ["Start run", "Edit", "Back"]))
        return ("start", "edit", "back")[next(self.choices)]

    def run_progress(self, title, process):
        self.screens.append((title, process))

    def command_output(self, title, process, refresh=False):
        self.outputs.append((title, process.argv, refresh))
        return next(self.output_answers, "back")

    def stage_choice(self, title, view, mode, position=None):
        """The stage picker: the next choice is the index of the stage picked, or None (back)."""
        self.screens.append((title, [row["id"] for row in view["stages"]]))
        self.choice_views.append(view)
        index = next(self.choices)
        return ("back", None) if index is None else ("pick", view["stages"][index]["id"])

    def ask(self, title, lines, choices):
        self.screens.append((title, choices))
        return next(self.choices)

    def run_files(self, title, files, read, position=None):
        self.screens.append((title, [item["path"] for item in files]))
        index = next(self.choices)
        return ("back", None) if index is None else ("edit", index)

    def run_history(self, title, view, read_log, position=None):
        self.screens.append((title, view))

    def edit_file(self, path, validate=None, *, title="Text editor", reference=None):
        self.edits.append((title, path, validate))
        return True


# A small valid recipe: shapes of tuples made outside the run (a directory that exists, as the check wants), then the
# fit of those shapes (inputs are never null, CL §37).
SHAPES = {"stage": "shapes", "id": "shapes", "eras": [2025], "jet_wps": ["Tight"], "ele_wps": ["Tight"],
          "inputs": {"tuples": {"external": os.path.join(os.path.dirname(os.path.abspath(__file__)), "$ERA", "$GROUP")}}}
FIT = {"stage": "fit", "id": "fit", "inputs": {"shapes": "shapes"}}
STAGES = [SHAPES, FIT]


def _plan_reruns(record):
    """Framework.plan_reruns of a run without an edited recipe: _rerun_rows of each stage (no module APIs)."""
    from TauFW.Framework._internal.runtime.framework import _rerun_rows, _run_recipe, RerunError, RerunPlan
    recipe, found = _run_recipe(record), []
    for stage_spec in recipe.stages:
        try:
            start, production, rows = _rerun_rows(record, recipe, stage_spec.id)
        except RerunError as error:
            found.append((stage_spec.id, error))
            continue
        found.append((stage_spec.id, RerunPlan(run_id=record.run_id, start=start, production=production,
                                               rows=tuple(rows))))
    return found


class MenuTests(unittest.TestCase):
    def test_install_opens_fastsetup_without_starting_another_main_menu(self):
        operations = self.menu(FakeUI()).operations
        for status in (0, 130, 7):
            with self.subTest(status=status), \
                    mock.patch.object(interactive.subprocess, "run",
                                      return_value=SimpleNamespace(returncode=status)) as install:
                if status == 7:
                    with self.assertRaisesRegex(RuntimeError, "Installation failed.*7"):
                        operations.install_components()
                else:
                    self.assertEqual(operations.install_components(), status)
                install.assert_called_once_with(
                    ["bash", str(interactive.CHECKOUT / "Utilities" / "FastSetup.sh")],
                    cwd=str(interactive.CHECKOUT))

    def test_grid_proxy_check_is_quiet_and_handles_unavailable_tools(self):
        operations = self.menu(FakeUI()).operations
        for status, left, valid in ((0, "43190\n", True), (0, "30\n", False), (0, "0\n", False),
                                    (1, "", False), (0, "Proxy not found", False)):
            with mock.patch.object(interactive.subprocess, "run",
                                   return_value=SimpleNamespace(returncode=status, stdout=left)) as check:
                self.assertEqual(operations.grid_proxy_valid(fresh=True), valid)
                check.assert_called_once_with(["voms-proxy-info", "--timeleft"], stdout=subprocess.PIPE,
                                              stderr=subprocess.DEVNULL, text=True, timeout=5)
        for error in (FileNotFoundError(), subprocess.TimeoutExpired("voms-proxy-info", 5)):
            with mock.patch.object(interactive.subprocess, "run", side_effect=error):
                self.assertFalse(operations.grid_proxy_valid(fresh=True))

    def test_grid_proxy_answer_is_kept_until_it_expires_or_the_proxy_file_changes(self):
        operations = self.menu(FakeUI()).operations
        clock, proxy = [1000.0], [(1, 100)]

        def ask(left):
            with mock.patch.object(interactive.time, "time", side_effect=lambda: clock[0]), \
                    mock.patch.object(interactive, "_proxy_file", side_effect=lambda: proxy[0]), \
                    mock.patch.object(interactive.subprocess, "run",
                                      return_value=SimpleNamespace(returncode=0, stdout="%d\n" % left)) as check:
                return operations.grid_proxy_valid(), check.call_count

        self.assertEqual(ask(600), (True, 1))     # the first draw asks voms-proxy-info
        self.assertEqual(ask(600), (True, 0))     # the next draws do not
        clock[0] += 539
        self.assertEqual(ask(0), (True, 0))       # valid for PROXY_MARGIN s more
        clock[0] += 1
        self.assertEqual(ask(0), (False, 1))      # expired: asked again
        self.assertEqual(ask(43200), (False, 0))  # an invalid answer is kept while the file is the same
        proxy[0] = (2, 100)
        self.assertEqual(ask(43200), (True, 1))   # renewed in another terminal
        proxy[0] = None
        self.assertEqual(ask(0), (False, 1))      # removed (voms-proxy-destroy)
        with mock.patch.object(interactive.subprocess, "run",
                               return_value=SimpleNamespace(returncode=0, stdout="43200\n")) as check, \
                mock.patch.object(interactive, "_proxy_file", return_value=None):
            self.assertTrue(operations.grid_proxy_valid(fresh=True))  # before a run, after a renewal
            check.assert_called_once_with(["voms-proxy-info", "--timeleft"], stdout=subprocess.PIPE,
                                          stderr=subprocess.DEVNULL, text=True, timeout=5)

    def test_grid_proxy_renewal_gets_the_password_on_stdin(self):
        operations = self.menu(FakeUI()).operations
        for status, output, valid, expected in ((0, "Creating proxy .... Done\n", True, True),
                                                (0, "Done\n", False, False),  # voms says done, the proxy is not
                                                (1, "Error: wrong pass phrase\n", True, False),
                                                (1, "Unknown option: -pwstdin\n", True, None)):
            with mock.patch.object(interactive.subprocess, "run",
                                   return_value=SimpleNamespace(returncode=status, stdout=output)) as renew, \
                    mock.patch.object(operations, "grid_proxy_valid", return_value=valid) as check, \
                    contextlib.redirect_stdout(io.StringIO()) as printed:
                self.assertEqual(operations.renew_grid_proxy("secret"), (expected, output.strip()))
            renew.assert_called_once_with(["voms-proxy-init", "-voms", "cms", "-pwstdin"], input="secret\n",
                                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                          timeout=interactive.PROXY_INIT_TIMEOUT)
            self.assertEqual(printed.getvalue(), "")  # nothing over the screen
            if status == 0:
                check.assert_called_once_with(fresh=True)
        with mock.patch.object(interactive.subprocess, "run",
                               side_effect=subprocess.TimeoutExpired("voms-proxy-init", 120)):
            self.assertEqual(operations.renew_grid_proxy("secret"),
                             (False, "voms-proxy-init did not answer within 120 s."))
        with mock.patch.object(interactive.subprocess, "run", side_effect=FileNotFoundError()):
            with self.assertRaisesRegex(RuntimeError, "VOMS tools"):
                operations.renew_grid_proxy("secret")

    def test_grid_proxy_renewal_in_the_terminal_checks_result(self):
        operations = self.menu(FakeUI()).operations
        for status, valid in ((0, True), (0, False), (1, False)):
            with mock.patch.object(interactive.subprocess, "run",
                                   return_value=SimpleNamespace(returncode=status)) as renew, \
                    mock.patch.object(operations, "grid_proxy_valid", return_value=valid), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(operations.renew_grid_proxy_in_terminal(), 0 if valid else 1)
                renew.assert_called_once_with(["voms-proxy-init", "-voms", "cms"])
            self.assertIn("Grid proxy active." if valid else "Proxy Failed!", output.getvalue())
        with mock.patch.object(interactive.subprocess, "run", side_effect=FileNotFoundError()), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "VOMS tools"):
                operations.renew_grid_proxy_in_terminal()

    def test_test_adapter_uses_checkout_current_python_and_quiet_arguments(self):
        operations = self.menu(FakeUI()).operations
        for family, cases, suffix in (("all", [], ["all"]),
                                      ("checks", ["unit.utilities"], ["checks", "--case", "unit.utilities"]),
                                      ("normal", [], ["normal"]),
                                      ("bbb", ["plotter.unroll"], ["bbb", "check", "--case", "plotter.unroll"]),
                                      ("environment", [], ["environment"])):
            with mock.patch.object(operations.store, "start") as launch:
                self.assertIs(operations.start_tests(family, cases, "Title", ["a"]), launch.return_value)
            self.assertEqual(launch.call_args.args, ("tests", "Title", [sys.executable, "-B",
                                                                         str(checkout.REPO / "Tests/run.py")]
                                                     + suffix, str(checkout.REPO)))
            self.assertEqual(launch.call_args.kwargs, dict(data=dict(family=family, cases=cases, expected=["a"])))
        self.assertEqual(operations.store.root, str(self.root / "operations"))
        self.assertEqual(interactive.OPERATIONS_DIR, checkout.REPO / ".artifacts" / "menu" / "operations")
        for family, cases in (("unknown", []), ("all", ["example"]), ("environment", ["example"])):
            with mock.patch.object(operations.store, "start") as launch:
                with self.assertRaises(ValueError):
                    operations.start_tests(family, cases)
            launch.assert_not_called()
        running = mock.Mock(title="Normal tests", host="lxplus812")
        with mock.patch.object(operations.store, "running", return_value=[running]), \
                mock.patch.object(operations.store, "start") as launch:
            with self.assertRaisesRegex(RuntimeError, "already running .Normal tests, started on lxplus812"):
                operations.start_tests("normal", [])  # one test run at a time
        launch.assert_not_called()
        self.assertIsNone(operations.tests_operation())
        self.assertEqual(operations.running_operations(), [])
        with mock.patch.object(operations.store, "latest", side_effect=PermissionError("AFS token")):
            self.assertIsNone(operations.tests_operation())  # the main menu still opens
        operation = mock.Mock()
        operations.stop_operation(operation)
        operation.cancel.assert_called_once_with()
        metadata = {family: [dict(id="example", description="Example", dependencies=[])]
                    for family in ("normal", "checks", "bbb")}
        with mock.patch.object(interactive.subprocess, "run", return_value=mock.Mock(
                returncode=0, stdout=json.dumps(metadata))) as catalog:
            self.assertEqual(operations.test_catalog(), metadata)
        self.assertEqual(catalog.call_args.args[0][-1], "catalog")
        self.assertEqual(catalog.call_args.kwargs["cwd"], str(checkout.REPO))
        for result in (mock.Mock(returncode=1, stderr="missing inventory"),
                       mock.Mock(returncode=0, stdout="invalid JSON")):
            with mock.patch.object(interactive.subprocess, "run", return_value=result):
                with self.assertRaises(RuntimeError):
                    operations.test_catalog()
        with mock.patch.object(interactive, "CHECKOUT", self.root):
            with self.assertRaisesRegex(RuntimeError, "complete TauFW checkout"):
                operations.test_catalog()

    def operation(self, name, run_dir="", seen=False, ended=True, events=(), started=1.0, lost=False):
        """An advance record in the operations directory: ended (exit.json), running (a fresh heartbeat) or lost
        (an old heartbeat of another machine)."""
        path = self.root / "operations" / name
        path.mkdir(parents=True)
        (path / "operation.json").write_text(json.dumps(dict(kind="run", title=name, argv=[], started=started,
                                                             host="here", data=dict(run_id=name, run_dir=run_dir))))
        (path / "events.jsonl").write_text("".join(json.dumps(event) + "\n" for event in events))
        if ended:
            (path / "exit.json").write_text(json.dumps(dict(returncode=0, stopped=False, finished=2.0)))
        else:
            (path / "heartbeat.json").write_text(json.dumps(dict(host="elsewhere", pid=1, t=1.0 if lost else 9e9)))
        if seen:
            (path / "seen").touch()
        return path

    def test_runs_behind_the_menu(self):
        operations = self.menu(FakeUI()).operations
        record = self.record()
        self.operation("run-1", run_dir=record.run_dir, seen=True)
        self.operation("run-2", events=[dict(kind="run", run_id=record.run_id, run_dir=record.run_dir)])
        self.operation("run-3", run_dir=str(self.root / "other"), ended=False)
        self.assertEqual(sorted(o.title for o in operations.run_operations()), ["run-2", "run-3"])  # unseen, running
        self.assertIsNone(operations.run_operation(record.run_dir))  # none of its advances runs now
        self.assertEqual(operations.run_operation(str(self.root / "other")).title, "run-3")
        newest = operations.run_advances([record.run_dir, str(self.root / "none")])
        self.assertEqual([o and o.title for o in newest], ["run-2", None])  # the start: its run_dir from the event
        operations.advance_run(record)
        self.assertEqual(sorted(o.title for o in operations.run_operations()), ["run-3"])  # earlier ones now seen
        self.assertIsNone(operations.run_lock(record.run_dir))
        (Path(record.run_dir) / "advance.lock").write_text(json.dumps(dict(host="elsewhere", pid=1, since="x",
                                                                          t=1.0)))
        lock = operations.run_lock(record.run_dir)
        self.assertEqual((lock["host"], lock["lost"], lock["local"]), ("elsewhere", True, False))

    def test_a_lost_advance_stays_listed_until_its_run_goes_on(self):
        operations = self.menu(FakeUI()).operations
        record = self.record()
        self.operation("run-1", run_dir=record.run_dir, seen=True, ended=False, lost=True)
        self.assertEqual([o.title for o in operations.run_operations()], ["run-1"])  # its card was seen: listed
        self.operation("run-2", run_dir=record.run_dir, seen=True, started=2.0)
        self.assertEqual(operations.run_operations(), [])  # a newer advance of the run (Continue) took over
        other = self.record("other", day=2)
        self.operation("run-3", run_dir=other.run_dir, seen=True, ended=False, lost=True, started=3.0)
        other.stage("fit").state = "DONE"
        other.save()
        self.assertEqual(operations.run_operations(), [])  # the run ended meanwhile (e.g. from the CLI)

    def test_kept_previews_and_rows_last_until_their_files_change(self):
        operations = self.menu(FakeUI()).operations
        path = self.recipe_file(self.recipes / "kept.json", name="before")
        self.assertIsNone(operations.kept_recipe_preview(path))  # never read
        self.assertEqual(operations.recipe_preview(path)["name"], "before")
        self.assertEqual(operations.kept_recipe_preview(path)["name"], "before")
        self.recipe_file(path, name="after_a_change")
        self.assertIsNone(operations.kept_recipe_preview(path))  # changed: read again
        path.write_text("{")
        self.assertTrue(operations.recipe_preview(path)["problems"])  # an unreadable recipe: its problem, kept too
        self.assertTrue(operations.kept_recipe_preview(path)["problems"])
        with mock.patch.object(interactive, "check_recipe", side_effect=RuntimeError("cannot check")):
            self.assertEqual(operations.recipe_preview(path), dict(name="kept.json", error="cannot check"))
        record = self.record()
        self.assertIsNone(operations.kept_run_row(record.run_dir))
        self.assertEqual(operations.run_row(record.run_dir)[2][:2], (record.run_id, "WAITING"))
        self.assertEqual(operations.kept_run_row(record.run_dir)[2][1], "WAITING")
        record.stage("fit").state = "DONE"
        record.save()  # run.json replaced: another inode
        self.assertIsNone(operations.kept_run_row(record.run_dir))
        self.assertEqual([row[2][1] for row in operations.runs()], ["DONE"])
        self.assertEqual(operations.run_directories(), [str(Path(record.run_dir).resolve())])

    def test_continue_lists_the_runs_of_the_advances_behind_the_menu(self):
        operations = self.menu(FakeUI()).operations
        inside = self.record()  # in taufw_runs/ of the launch directory
        recipe = Recipe.from_dict({"name": "elsewhere", "stages": STAGES})
        outside = RunRecord.create(recipe, str(self.root / "my_runs"), now=datetime(2026, 10, 3))
        Path(outside.run_dir).mkdir(parents=True)
        outside.save()
        self.assertEqual([row[2][0] for row in operations.runs()], [inside.run_id])
        self.operation("run-1", run_dir=outside.run_dir)
        self.operation("run-2", run_dir=inside.run_dir)
        self.assertEqual([row[2][0] for row in operations.runs()], [outside.run_id, inside.run_id])  # once each

    def test_the_facts_of_a_stage_for_the_info_box(self):
        stage = {"stage": "production", "id": "ntuples", "description": "tuples", "inputs": None,
                 "eras": ["2022_postEE", "2023C"], "channels": ["mutau"], "samples": ["DY*", "TT*"], "tag": "",
                 "max_tries": 3, "merge": {"clean": True}}
        self.assertEqual(interactive._stage_info(stage), [
            ["Eras", "2022_postEE 2023C"], ["Channels", "mutau"], ["Samples", "DY* TT*"], ["Max tries", "3"],
            ["Merge", "clean: True"], ["Output", "stages/ntuples/"]])
        plots = {"stage": "controlplots", "id": "plots", "inputs": {"histograms": "hists"},
                 "config": "plots_mutau.yml"}
        self.assertEqual(interactive._stage_info(plots), [["Config", "plots_mutau.yml"],
                                                          ["Inputs", "histograms: hists"], ["Output", "stages/plots/"]])

    def test_grid_proxy_is_needed_while_production_may_submit(self):
        operations = self.menu(FakeUI()).operations
        production = {"stage": "production", "id": "ntuples", "inputs": None, "eras": ["2018"],
                      "channels": ["mutau"], "samples": ["DY"]}
        self.assertTrue(operations.needs_grid_proxy(recipe=self.recipe_file(self.root / "p.json",
                                                                            stages=[production])))
        self.assertFalse(operations.needs_grid_proxy(recipe=self.recipe_file(self.root / "f.json")))
        recipe = Recipe.from_dict({"name": "p", "stages": [production] + STAGES})
        record = RunRecord.create(recipe, str(self.root / "taufw_runs"), now=datetime(2026, 10, 1))
        for state, needed in (("NEW", True), ("WAITING", True), ("MERGING", True), ("DONE", False)):
            record.stage("ntuples").state = state
            self.assertEqual(operations.needs_grid_proxy(record=record), needed)
        stage = record.stage("ntuples")  # CL §48: FAILED after max_tries: a retry resubmits; a failed merge: no
        stage.state, stage.attempt = "FAILED", 3
        stage.last_status = {"samples": [{"name": "DY", "pending": [], "failed": [1], "missing": []}]}
        for before, needed in (("WAITING", True), ("MERGING", False)):
            stage.history = [{"event": "x", "state": before}, {"event": "failed", "state": "FAILED"}]
            self.assertEqual(operations.needs_grid_proxy(record=record), needed, before)

    def test_retry_info_of_a_production_stage_gives_its_tries(self):
        """CL §48: after max_tries, retry_info says how many tries a retry allows; a failed merge: no retry."""
        production = {"stage": "production", "id": "ntuples", "inputs": None, "eras": ["2018"],
                      "channels": ["mutau"], "samples": ["DY"], "max_tries": 2}
        record = RunRecord.create(Recipe.from_dict({"name": "p", "stages": [production]}),
                                  str(self.root / "taufw_runs"), now=datetime(2026, 10, 1))
        stage = record.stage("ntuples")
        stage.state, stage.attempt, stage.message = "FAILED", 2, "1 chunk(s) still failed or missing after 2 tries"
        stage.last_status = {"samples": [{"name": "DY", "pending": [], "failed": [], "missing": [0]}]}
        stage.history = [{"event": "resubmitted", "state": "SUBMITTED"}, {"event": "failed", "state": "FAILED"}]
        self.assertEqual(interactive._Operations.retry_info(record),
                         dict(stage="ntuples", type="production", message=stage.message, changed=None, tries=(2, 4)))
        stage.attempts = [{"attempt": 1, "max_tries": 4}]  # retried once and failed again after 4: up to 6
        stage.attempt = 4
        self.assertEqual(interactive._Operations.retry_info(record)["tries"], (4, 6))
        stage.history[-2]["state"] = "MERGING"
        self.assertIsNone(interactive._Operations.retry_info(record))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.recipes = self.root / "recipes"
        self.recipes.mkdir()
        versions = mock.patch.object(interactive, 'VersionChecker')
        self.versions = versions.start().return_value
        self.versions.status.return_value = None  # unrelated menu tests never access the network or user cache
        self.addCleanup(versions.stop)
        patcher = mock.patch("TauFW.Framework._internal.interfaces.interactive.Framework.from_recipe")
        self.framework = patcher.start()
        self.addCleanup(patcher.stop)
        self.framework.return_value.plan.return_value = SimpleNamespace(
            stages=(), bundle_dir=None, pico_config=None, sample_problems=(), sample_warnings=())
        self.framework.return_value.recipe.first.return_value = None  # no production stage
        self.framework.return_value.plan_reruns.side_effect = _plan_reruns  # the real rule, without stage APIs
        self.started = []  # (argv after taufw.py, keyword arguments) of each run started behind the menu
        launch = mock.patch.object(interactive.OperationStore, "start", autospec=True,
                                   side_effect=lambda store, kind, title, argv, cwd, **kw:
                                   self.started.append((argv[3:], dict(kw, kind=kind, title=title, cwd=cwd)))
                                   or mock.Mock(running=False, title=title, data=kw.get("data", {}),
                                                argv=argv[3:]))
        launch.start()
        self.addCleanup(launch.stop)

    def menu(self, ui):
        return Menu(ui, self.root, self.recipes, self.root / "operations")

    def test_version_adapter_passes_only_the_framework_checkers_presentation_data(self):
        view = dict(installed='0.1.0', latest='0.2.3', status='available', checking=False,
                    available=True, error=None, stale=False)
        self.versions.status.return_value = view
        self.assertIs(self.menu(FakeUI()).operations.version_status(), view)
        self.versions.status.assert_called_once_with()

    def test_user_config_editor_opens_the_override_and_reuses_config_validation(self):
        from TauFW.Utilities.UserConfig import UserConfigError
        operations = self.menu(FakeUI()).operations
        reference = operations.user_config_reference()
        self.assertEqual(reference, interactive.CHECKOUT / "Docs/Develop/InProgramMDs/UserConfig.md")
        self.assertIn("# User config", reference.read_text(encoding="utf-8"))
        path = self.root / "personal.yaml"
        with mock.patch.dict(os.environ, {"TAUFW_USER_CONFIG": str(path)}):
            self.assertEqual(operations.user_config_path(), path)
            self.assertIn("reviewed: false", path.read_text())
            path.write_text("broken existing file", encoding="utf-8")
            self.assertEqual(operations.user_config_path(), path)
            self.assertEqual(path.read_text(), "broken existing file")  # still opens so it can be repaired
            self.assertFalse(operations.user_config_reviewed())  # cannot be read: not reviewed
            path.write_text("taufw_user:\n  version: 1\n  reviewed: true\n", encoding="utf-8")
            self.assertTrue(operations.user_config_reviewed())
            path.unlink()
            self.assertFalse(operations.user_config_reviewed())  # no file

        draft = self.root / "draft.yaml"
        header = "taufw_user:\n  version: 1\n  reviewed: false\n"
        draft.write_text(header + "custom: {key: value}\n", encoding="utf-8")
        self.assertEqual(operations.validate_user_config(draft), [])
        draft.write_text(header + "production: {ncores: 0}\n", encoding="utf-8")
        self.assertIn("production.ncores", operations.validate_user_config(draft)[0])
        for invalid in ("taufw_user: [", "production: {}\n"):
            draft.write_text(invalid, encoding="utf-8")
            with self.assertRaises(UserConfigError):
                operations.validate_user_config(draft)

    def test_editor_save_refreshes_recipe_previews_and_run_root_without_restarting(self):
        from TauFW.Framework._internal.editor._file import Document
        operations = self.menu(FakeUI()).operations
        path, recipe = self.root / "personal.yaml", self.recipes / "example.yml"
        self.recipe_file(recipe)
        header = "taufw_user:\n  version: 1\n  reviewed: true\n"
        path.write_text(header, encoding="utf-8")
        check = SimpleNamespace(name="test", stages=(), issues=(), warnings=())
        run_root = self.root / "new_runs"
        with mock.patch.dict(os.environ, {"TAUFW_USER_CONFIG": str(path)}), \
                mock.patch.object(interactive, "check_recipe", return_value=check):
            preview = operations.recipe_preview(recipe)
            self.assertEqual(operations.kept_recipe_preview(recipe), preview)
            document = Document(path)
            document.save(header + "runs:\n  run_root: %s\n" % json.dumps(str(run_root)),
                          operations.validate_user_config)
            self.assertIsNone(operations.kept_recipe_preview(recipe))
            self.assertIn(run_root, operations.run_roots())

    def test_the_user_config_is_not_a_recipe(self):
        """Analyses/UserConfig.yaml sits beside the bundles and loose recipe files, but is never listed (CL §40)."""
        (self.recipes / "bundle").mkdir()
        self.recipe_file(self.recipes / "bundle" / "recipe.yml")
        self.recipe_file(self.recipes / "loose.yml")
        (self.recipes / "UserConfig.yaml").write_text("taufw_user:\n  version: 1\n  reviewed: false\n",
                                                     encoding="utf-8")
        names = [path.name for path in self.menu(FakeUI()).operations.recipes()]
        self.assertIn("bundle", names)
        self.assertIn("loose.yml", names)
        self.assertNotIn("UserConfig.yaml", names)

    def recipe_file(self, path, name="test", stages=None):
        path.write_text(json.dumps(dict(name=name, stages=stages or STAGES)),
                        encoding="utf-8")
        return path

    def record(self, name="test", state="WAITING", day=1):
        recipe = Recipe.from_dict({"name": name, "stages": STAGES})
        record = RunRecord.create(recipe, str(self.root / "taufw_runs"),
                                  now=datetime(2026, 10, day))
        Path(record.run_dir).mkdir(parents=True)
        record.stage("shapes").state = "DONE"  # the run's state is the fit's
        record.stage("fit").state = state
        record.save(now=datetime(2026, 10, day).strftime("%Y-%m-%d %H:%M:%S"))
        return record

    def test_start_previews_before_submission_and_resolves_typed_path(self):
        (self.recipes / "b.yml").touch()
        (self.recipes / "a.json").touch()
        (self.recipes / "ignore.txt").touch()
        (self.recipes / "c_bundle").mkdir()
        (self.recipes / "c_bundle" / "recipe.yml").touch()
        (self.recipes / "d_not_a_bundle").mkdir()
        ui = FakeUI([4, 0], ["custom.yml"])
        self.recipe_file(self.root / "custom.yml")
        order = []
        planned = self.framework.return_value
        self.framework.side_effect = lambda *args, **values: order.append("prepare") or planned
        menu = self.menu(ui)
        menu.operations.start_run = mock.Mock(side_effect=lambda path: order.append("start") or mock.Mock(
            running=True, title="test", data=dict(run_id="test")))
        menu.start()
        self.assertEqual(ui.screens[0][1][:4], ["[Create a new run]", "a.json", "b.yml", "c_bundle"])
        self.assertEqual(order, ["prepare", "start"])
        self.assertEqual(self.started, [])  # start_run is mocked; no plan ran
        menu.operations.start_run.assert_called_once_with(str(self.root / "custom.yml"))
        self.assertEqual(ui.screens[-1][0], "Run test")
        self.assertEqual(ui.messages, [])

    def test_a_recipe_that_cannot_be_planned_shows_why_on_its_plan_screen(self):
        self.recipe_file(self.root / "bad.yml")
        self.recipe_file(self.root / "good.yml")
        self.framework.side_effect = [ValueError("invalid recipe"), self.framework.return_value]
        ui = FakeUI([1, 2, 1, 2, 3], ["bad.yml", "good.yml"])  # each: the path, Back of its plan; Back
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.menu(ui).start()
        self.assertEqual(output.getvalue(), "")  # nothing printed over the screen
        self.assertEqual(ui.messages, [])
        bad, good = ui.plans
        self.assertEqual(bad["errors"], ["Cannot plan the recipe: invalid recipe"])
        self.assertEqual([stage["note"] for stage in bad["stages"]],
                         ["Cannot be planned until the errors are fixed."] * 2)
        self.assertEqual(good["errors"], [])
        self.assertEqual(self.framework.call_count, 2)
        self.assertEqual(self.started, [])  # no plan, no start

    def test_run_order_and_advance_to_the_end_behind_the_menu(self):
        self.record("old", day=1)
        newest = self.record("new", day=2)
        ui = FakeUI([0, 0])
        self.menu(ui).continue_run()
        self.assertIn(newest.run_id + " | WAITING", ui.screens[0][1][0])
        (argv, options), = self.started
        self.assertEqual(argv, ["advance", newest.run_dir])  # waits for the jobs by default
        self.assertEqual((options["kind"], options["title"], options["escalate"], options["signal"]),
                         ("run", newest.run_id, False, "command"))
        self.assertEqual(options["data"], dict(run_id=newest.run_id, run_dir=newest.run_dir, stages=[
            dict(id="shapes", type="shapes", state="DONE", message="",
                 info=[["Eras", "2025"], ["Jet wps", "Tight"], ["Ele wps", "Tight"],
                       ["Inputs", "tuples: external: " + SHAPES["inputs"]["tuples"]["external"]],
                       ["Output", "stages/shapes/"]]),
            dict(id="fit", type="fit", state="WAITING", message="", info=[["Inputs", "shapes"],
                                                                         ["Output", "stages/fit/"]])]))
        self.assertEqual(ui.screens[-1][0], "Run " + newest.run_id)

    def test_next_stage_only(self):
        record = self.record()
        self.menu(FakeUI([0, 1])).continue_run()
        self.assertEqual([argv for argv, _ in self.started], [["advance", record.run_dir, "--next"]])

    def test_finished_runs_offer_rerun_edit_history_and_inspection(self):
        """CL §55 step 4: a DONE, FAILED or BLOCKED run cannot advance; its actions are Rerun (failed), Rerun
        from..., Edit run config, History and Inspect status."""
        for state, title, actions in (
                ("DONE", "(DONE)", ["Rerun from...", "Edit run config", "History", "Inspect status", "Back"]),
                ("FAILED", "(FAILED)", ["Rerun fit (failed)", "Rerun from...", "Edit run config", "History",
                                        "Inspect status", "Back"]),
                ("NOT_IMPLEMENTED", "(BLOCKED)", ["Rerun from...", "Edit run config", "History", "Inspect status",
                                                 "Back"])):
            with self.subTest(state=state):
                record = self.record(state=state)
                ui = FakeUI([0, actions.index("Inspect status"), None])
                self.menu(ui).continue_run()
                self.assertIn(title, ui.screens[1][0])
                self.assertEqual(ui.screens[1][1], actions)
                self.assertEqual(ui.outputs, [("Run status: " + record.run_id, ["status", record.run_dir], True)])
        self.assertEqual([argv[0] for argv, _ in self.started], ["status"] * 3)  # never an advance

    def test_rerun_of_a_failed_run(self):
        """CL §44, §55: Rerun fit (failed) goes to the confirm panel at once, then `taufw.py rerun RUN fit`."""
        record = self.record(state="FAILED")
        ui = FakeUI([0, 0, 0])
        self.menu(ui).continue_run()
        self.assertEqual([argv for argv, _ in self.started], [["rerun", record.run_dir, "fit"]])
        self.assertEqual(ui.screens[1][1][0], "Rerun fit (failed)")
        self.assertEqual(ui.screens[2], ("Rerun from fit?", ["Rerun fit", "Cancel"]))
        self.assertEqual(self.started[0][1]["data"]["stages"][1]["state"], "FAILED")
        self.assertEqual(ui.screens[-1][0], "Run " + record.run_id)

    def test_rerun_from_a_stage_of_a_done_run(self):
        """CL §55 step 4: Rerun from... lists the stages with a dry rerun of each; the confirm panel's "only" runs
        `taufw.py rerun RUN shapes --next`."""
        record = self.record(state="DONE")
        ui = FakeUI([0, 0, 0, 1])  # the run, Rerun from..., shapes, Rerun shapes only
        self.menu(ui).continue_run()
        view = ui.choice_views[0]
        self.assertEqual([row["id"] for row in view["stages"]], ["shapes", "fit"])
        shapes = view["stages"][0]
        self.assertEqual([(row["stage"], row["state"], row["archive"]) for row in shapes["plan"]["rows"]],
                         [("shapes", "DONE", None), ("fit", "DONE", None)])  # nothing was left in the test's run
        self.assertEqual((shapes["plan"]["kept"], shapes["until"]), ([], False))
        self.assertEqual(ui.screens[3], ("Rerun from shapes?", ["Rerun to the end", "Rerun shapes only (the others "
                                                                "wait)", "Cancel"]))
        self.assertEqual([argv for argv, _ in self.started], [["rerun", record.run_dir, "shapes", "--next"]])

    def test_advance_until_a_stage(self):
        record = self.record(state="WAITING")
        record.stage("fit").state = "NEW"
        record.save()
        ui = FakeUI([0, 2, 1])  # the run, Advance until..., fit
        self.menu(ui).continue_run()
        self.assertEqual([row["until"] for row in ui.choice_views[0]["stages"]], [False, True])
        self.assertEqual([argv for argv, _ in self.started], [["advance", record.run_dir, "--until", "fit"]])

    def test_edit_run_config_lists_the_run_files_and_checks_its_recipe(self):
        """CL §55 step 4: the run's recipe first, then its bundle files; the recipe's validator refuses an edit of
        the run's rules and is refused while an advance holds the lock; History shows the versions."""
        record = self.record(state="DONE")
        bundle = Path(record.run_dir) / "bundle"
        (bundle / "steps").mkdir(parents=True)
        (bundle / "recipe.yml").write_text(json.dumps(record.recipe), encoding="utf-8")
        (bundle / "steps" / "x.py").write_text("print(1)\n", encoding="utf-8")
        (bundle / "data.root").write_text("not text", encoding="utf-8")
        ui = FakeUI([0, 1, 0, None, None])  # the run, Edit run config, recipe.yml (the editor), back, back
        menu = self.menu(ui)
        menu.continue_run()
        self.assertEqual(ui.screens[2], ("Edit run config / " + record.run_id, ["recipe.yml", os.path.join("steps", "x.py")]))
        (title, path, validate), = ui.edits
        self.assertEqual((title, path), ("Edit run config / %s / recipe.yml" % record.run_id, str(bundle / "recipe.yml")))
        draft = bundle / ".recipe.yml.draft"
        draft.write_text(json.dumps(dict(record.recipe, name="other")), encoding="utf-8")
        self.assertIn("name: cannot change in a run", validate(draft)[0])
        draft.write_text(json.dumps(record.recipe), encoding="utf-8")
        self.assertIsNone(validate(draft))
        with mock.patch.object(interactive, "read_lock", return_value=dict(pid=5, host="lxplus1")):
            self.assertIn("An advance works on this run now (pid 5 on lxplus1)", validate(draft)[0])
        operations = menu.operations
        self.assertEqual(operations.file_text(str(bundle / "steps" / "x.py")), ["print(1)"])
        history = operations.run_history(record)
        self.assertEqual([item["text"] for item in history["versions"]], ["start"])
        self.assertEqual([stage["id"] for stage in history["stages"]], ["shapes", "fit"])

    def test_the_run_screen_gets_the_times_of_the_earlier_advances(self):
        """Continue and Retry: how long the DONE and FAILED stages took, from run.json (commands of a local stage;
        the history of a stage without commands, e.g. production); nothing for a stage that did not finish."""
        record = self.record(state="FAILED")
        record.stage("shapes").last_status = {"commands": [
            {"label": "mutau", "seconds": 61.5, "ok": True, "log": "/r/logs/shapes/01_mutau.log"},
            {"label": "mumu", "seconds": 20.0, "ok": True, "log": "/r/logs/shapes/02_mumu.log"}]}
        record.stage("fit").history = [{"time": "2026-10-01 10:00:00", "event": "submitted"},
                                       {"time": "2026-10-02 12:30:05", "event": "failed"}]
        record.save()
        ui = FakeUI([0, 0, 0])  # the run, Rerun fit (failed), Rerun fit
        self.menu(ui).continue_run()
        shapes, fit = self.started[0][1]["data"]["stages"]
        self.assertEqual({key: shapes[key] for key in ("seconds", "commands", "log")}, dict(
            seconds=81.5, log="/r/logs/shapes/02_mumu.log",
            commands=[dict(label="mutau", seconds=61.5, status="ok", log="/r/logs/shapes/01_mutau.log"),
                      dict(label="mumu", seconds=20.0, status="ok", log="/r/logs/shapes/02_mumu.log")]))
        self.assertEqual((fit["seconds"], "commands" in fit), (26 * 3600 + 30 * 60 + 5.0, False))
        waiting = self.record("other", state="WAITING", day=3)
        waiting.stage("fit").history = list(record.stage("fit").history)
        waiting.save()
        self.started.clear()
        self.menu(FakeUI([0, 0])).continue_run()
        self.assertNotIn("seconds", self.started[0][1]["data"]["stages"][1])  # still running: no time yet

    def test_inspect_refreshes_and_does_not_write(self):
        record = self.record()
        before = Path(record.path).read_bytes()
        ui = FakeUI([0, 2])
        ui.output_answers = iter(["refresh", "back"])
        self.menu(ui).inspect()
        self.assertEqual([argv for argv, _ in self.started], [["status", record.run_dir]] * 2)  # R ran it again
        self.assertEqual(Path(record.path).read_bytes(), before)
        self.assertEqual(ui.messages, [])

    def test_saved_run_preview_is_plain_data_and_does_not_change_the_run(self):
        record = self.record()
        before = Path(record.path).read_bytes()
        operations = self.menu(FakeUI()).operations
        with mock.patch.object(operations, "run_operation", return_value=None), \
                mock.patch.object(operations, "run_lock", return_value=None):
            view = operations.run_preview(record.run_dir)
        self.assertEqual((view["run_id"], view["state"], view["can_advance"]),
                         (record.run_id, "WAITING", True))
        self.assertEqual([stage["id"] for stage in view["stages"]], [stage.name for stage in record.stages])
        self.assertIsNone(view["retry"])
        self.assertFalse(view["advancing"])
        self.assertEqual(Path(record.path).read_bytes(), before)
        self.assertEqual(self.started, [])

    def test_status_runs_behind_the_menu_and_plan_does_not(self):
        operations = self.menu(FakeUI()).operations
        record = self.record()
        operations.start_command("status", record.run_dir)
        recipe = self.recipe_file(self.root / "p.json")
        with self.assertRaises(ValueError):  # the plan screen plans in the menu's own process
            operations.start_command("plan", str(recipe))
        (status, options), = self.started
        self.assertEqual(status, ["status", record.run_dir])
        self.assertEqual((options["kind"], options["title"], options["cwd"], options["data"]),
                         ("command", "status " + Path(record.run_dir).name, str(self.root),
                          dict(command="status", target=record.run_dir)))
        with self.assertRaises(ValueError):
            operations.start_command("advance", record.run_dir)  # only what reads
        running = [mock.Mock(kind="command"), mock.Mock(kind="run")]
        with mock.patch.object(operations.store, "running", return_value=running):
            self.assertEqual(operations.running_operations(), running[1:])  # its screen stops a command

    def test_empty_picker_and_unreadable_run_recovery(self):
        ui = FakeUI([0, 1], ["missing"])
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertIsNone(self.menu(ui)._pick_run())
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(ui.messages[0][0], "Cannot read run")
        self.assertEqual(ui.screens[0][1], ["Enter another run directory", "Back"])

    def test_interrupted_operation_returns_to_main_menu(self):
        self.record()
        menu = self.menu(FakeUI([1, 0, 1, 8]))
        menu.operations.advance_run = mock.Mock(side_effect=KeyboardInterrupt)
        self.assertEqual(menu.run(), 0)
        menu.operations.advance_run.assert_called_once()
        self.assertEqual(menu.ui.screens[-1][0], "TauFW")

    def test_the_text_panel_checks_names_and_paths(self):
        """What the text panel says under its field as the user types: a new analysis' name, a recipe, a run."""
        operations = self.menu(FakeUI()).operations
        self.recipe_file(self.recipes / "taken.yml")
        (self.recipes / "taken").mkdir()
        self.assertEqual(operations.check_analysis_name("new_one"), (True, "Creates recipes/new_one/"))
        for name, words in (("", "Letters, digits"), ("a b", "must be a word"), ("taken", "already exists"),
                            ("x.", "end with a dot")):
            ok, text = operations.check_analysis_name(name)
            self.assertFalse(ok, name)
            self.assertIn(words, text)
        record = self.record()
        recipe = self.recipe_file(self.root / "loose.json")
        for value, ok, words in (("loose.json", True, "Recipe "), ("recipes", False, "has no recipe.yml"),
                                 ("nothing.yml", False, "does not exist"), ("", False, "bundle directory")):
            self.assertEqual(operations.check_recipe_path(value)[0], ok, value)
            self.assertIn(words, operations.check_recipe_path(value)[1])
        self.assertEqual(operations.check_run_path(record.run_dir), (True, "Run " + str(Path(record.run_dir))))
        self.assertIn("not a run directory", operations.check_run_path(str(self.root))[1])
        self.assertIn("does not exist", operations.check_run_path("missing")[1])
        self.assertTrue(recipe.is_file())

    def test_back_from_continue_goes_back_to_the_picker(self):
        self.record()
        ui = FakeUI([0, 7, None])  # Back: the last of the 8 actions of a WAITING run
        self.menu(ui).continue_run()
        self.assertTrue(ui.screens[1][0].startswith("Continue:"))
        self.assertEqual(ui.screens[2][0], "Select an existing run")
        self.assertEqual(self.started, [])

    def eos(self):
        """The tuples of tes_id_2025 are on EOS; here (e.g. Windows) /eos/... counts as existing."""
        isdir = os.path.isdir
        patcher = mock.patch("TauFW.Framework._internal.recipes.validation.os.path.isdir",
                             side_effect=lambda path: str(path).startswith("/eos/") or isdir(path))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_default_recipes_are_the_analysis_bundles(self):
        self.eos()
        recipes_dir = checkout.REPO / "Analyses"
        expected = sorted(path.name for path in recipes_dir.iterdir() if (path / "recipe.yml").is_file())
        self.assertIn("tes_id_2025", expected)
        self.assertNotIn("Examples", expected)  # the examples have their own list
        ui = FakeUI([expected.index("tes_id_2025") + 1, 0])
        menu = Menu(ui, launch_dir=self.root, operations_dir=self.root / "operations")
        self.assertEqual(menu.operations.recipes_dir, recipes_dir)
        menu.start()
        self.assertEqual(ui.screens[0][1][1:-3], expected)
        self.assertEqual(ui.screens[0][1][-3:], ["Enter another recipe path", "[Examples]", "Back"])
        self.assertEqual([argv for argv, _ in self.started], [["start", str(recipes_dir / "tes_id_2025")]])

    def test_examples_are_listed_under_examples(self):
        """[Examples] (the row above Back) opens the list of Analyses/Examples/; the validation demo is red there."""
        self.eos()
        examples_dir = checkout.REPO / "Analyses" / "Examples"
        expected = sorted(path.name for path in examples_dir.iterdir() if (path / "recipe.yml").is_file())
        self.assertEqual(expected, ["broken", "cmsdas26_ztt", "mutau_long", "mutau_short"])
        recipes = sorted(path.name for path in (checkout.REPO / "Analyses").iterdir() if (path / "recipe.yml").is_file())
        ui = FakeUI([len(recipes) + 2, expected.index("cmsdas26_ztt"), 0])  # [Examples], cmsdas26_ztt, Start run
        menu = Menu(ui, launch_dir=self.root, operations_dir=self.root / "operations")
        self.assertEqual([path.name for path in menu.operations.examples()], expected)
        menu.start()
        self.assertEqual(ui.screens[1][1], expected + ["Back"])  # no create action, no other path
        self.assertEqual(ui.broken, [name == "broken" for name in expected])  # the validation demo
        self.assertEqual([argv for argv, _ in self.started],
                         [["start", str(examples_dir / "cmsdas26_ztt")]])

    def test_dispatch_uses_semantic_actions_without_screen_positions(self):
        ui = mock.Mock()
        ui.main_menu.side_effect = ["start", "exit"]
        ui.select_recipe.return_value = ("manual", None)
        ui.recipe_path.return_value = "custom.yml"
        ui.recipe_plan.return_value = "start"
        self.recipe_file(self.root / "custom.yml")
        self.assertEqual(self.menu(ui).run(), 0)
        self.assertEqual([argv[0] for argv, _ in self.started], ["start"])
        ui.choose.assert_not_called()
        ui.prompt.assert_not_called()

    def test_bundled_previews_use_recipe_order_without_planning(self):
        self.eos()
        operations = self.menu(FakeUI()).operations
        expected = {
            "Examples/mutau_short": (("production", "production"),),
            "Examples/mutau_long": (("production", "production"), ("hists", "controlhists"), ("plots", "controlplots")),
            "tes_id_2025": (("hists", "controlhists"), ("plots", "controlplots"), ("shapes", "shapes"),
                            ("fit", "fit"), ("fit_summary", "python")),
        }
        for bundle, stages in expected.items():
            with self.subTest(bundle=bundle):
                view = operations.recipe_preview(checkout.REPO.joinpath("Analyses", *bundle.split("/")))
                self.assertEqual(tuple(stage[:2] for stage in view["stages"]), stages)
                self.assertEqual(view["problems"], ())
                self.assertTrue(all(stage[2] for stage in view["stages"]))  # the bundles describe every stage
        self.framework.assert_not_called()
        self.assertFalse((self.root / "taufw_runs").exists())

    def test_multiple_python_steps_keep_their_ids_and_descriptions(self):
        steps = self.recipes / "steps"
        steps.mkdir()
        for name in ("prep", "check", "report"):
            (steps / (name + ".py")).write_text("def run(ctx):\n    pass\n")
        path = self.recipe_file(self.recipes / "custom.json", stages=[
            {"stage": "python", "id": "prepare", "inputs": None, "file": "steps/prep.py"},
            {"stage": "controlhists", "id": "hists", "inputs": SHAPES["inputs"], "eras": [2025]},
            {"stage": "python", "id": "check", "description": "look at the hists", "inputs": {"hists": "hists"},
             "file": "steps/check.py"},
            SHAPES,
            FIT,
            {"stage": "python", "id": "report", "inputs": {"fit": "fit"}, "file": "steps/report.py"},
        ])
        view = self.menu(FakeUI()).operations.recipe_preview(path)
        reads = [stage[3] for stage in view["stages"]]
        self.assertEqual([stage[:3] for stage in view["stages"]],
                         [("prepare", "python", ""), ("hists", "controlhists", ""),
                          ("check", "python", "look at the hists"), ("shapes", "shapes", ""), ("fit", "fit", ""),
                          ("report", "python", "")])
        self.assertEqual((reads[0], reads[2], reads[5]), ("-", "hists", "fit"))  # the Input column
        self.assertEqual(view["problems"], ())
        self.framework.assert_not_called()

    def test_runs_of_the_recipes_run_roots_are_listed(self):
        elsewhere = self.root / "elsewhere"
        (self.recipes / "a.json").write_text(json.dumps(dict(name="a", run_root=str(elsewhere), stages=STAGES)),
                                             encoding="utf-8")
        (self.recipes / "b.json").write_text(json.dumps(dict(name="b", run_root=str(elsewhere), stages=STAGES)),
                                             encoding="utf-8")  # the same root: listed once
        (self.recipes / "c.json").write_text("{not json", encoding="utf-8")  # unreadable: skipped
        here = self.record("here", day=1)
        recipe = Recipe.from_dict({"name": "there", "stages": STAGES})
        there = RunRecord.create(recipe, str(elsewhere), now=datetime(2026, 10, 2))
        Path(there.run_dir).mkdir(parents=True)
        there.save(now="2026-10-02 00:00:00")
        operations = self.menu(FakeUI()).operations
        self.assertEqual(operations.run_roots(), [(self.root / "taufw_runs").resolve(), elsewhere.resolve()])
        self.assertEqual([row[1] for row in operations.runs()], [there.run_dir, here.run_dir])

    def test_recipe_warnings_are_shown_but_do_not_break(self):
        self.recipe_file(self.recipes / "a.json")  # no run_root
        ui = FakeUI([4])  # Back
        self.menu(ui).start()
        self.assertEqual(ui.broken, [False])
        view = self.menu(FakeUI()).operations.recipe_preview(self.recipes / "a.json")
        self.assertEqual(view["problems"], ())
        self.assertEqual(len(view["warnings"]), 1)
        self.assertTrue(view["warnings"][0].startswith("run_root: not set"))

    def test_broken_recipes_are_marked_and_list_every_problem(self):
        self.recipe_file(self.recipes / "a_good.json")
        self.recipe_file(self.recipes / "b_bad.json", stages=[
            {"stage": "shapes", "inputs": SHAPES["inputs"], "eras": [2025], "jet_wps": ["Tight"],
             "ele_wps": ["Tight"]},
            {"stage": "fit", "id": "fit", "inputs": {"shapes": "histo"}},
        ])
        ui = FakeUI([5])  # Back
        self.menu(ui).start()
        self.assertEqual(ui.broken, [False, True])
        view = self.menu(FakeUI()).operations.recipe_preview(self.recipes / "b_bad.json")
        self.assertEqual(view["problems"], ("stages[0] (shapes): missing 'id' (every stage needs a unique id, "
                                            "e.g. id: shapes)",
                                            "stages[1] (fit).inputs.shapes: no stage 'histo' in the recipe"))
        self.assertEqual(view["stages"], (("fit", "fit", "", "histo"),))  # the stages that could be read

    def test_the_plan_reloads_the_recipe_and_keeps_every_detail_silently(self):
        from TauFW.Utilities.Process import Command, CommandPlan
        path = self.recipe_file(self.recipes / "test.json", name="before")
        operations = self.menu(FakeUI()).operations
        self.assertEqual(operations.recipe_preview(path)["name"], "before")
        self.recipe_file(path, name="after")
        commands = CommandPlan(cwd="/runs/x/stages/fit", commands=(
            Command("DM0", (sys.executable, "fit.py", "-d", "0"), "/runs/x/stages/fit/2025"),),
            notes=("missing ROOT",))

        def build(recipe, reporter):
            reporter.warning("configuration warning")
            self.assertEqual(recipe.name, "after")
            plan = SimpleNamespace(bundle_dir=None, pico_config=None, sample_problems=(), sample_warnings=(),
                                   stages=[SimpleNamespace(stage="shapes", note="environment unavailable",
                                                           plan=None, paths=(), sources={}),
                                           SimpleNamespace(stage="fit", note="", plan=commands, paths=(),
                                                           sources={})])
            stage = SimpleNamespace(null_inputs={})
            return SimpleNamespace(recipe=recipe, stages=dict(shapes=stage, fit=stage), plan=lambda deep=True: plan)

        self.framework.side_effect = build
        before = path.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            plan = operations.prepare_plan(path)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(plan["name"], "after")
        self.assertEqual(plan["errors"], [])
        self.assertIn("configuration warning", plan["warnings"])
        shapes, fit = plan["stages"]
        self.assertEqual((shapes["note"], shapes["steps"]), ("environment unavailable", None))
        self.assertEqual((fit["inputs"], fit["reads"]), ("shapes <- shapes", "shapes"))
        self.assertEqual((fit["cwd"], fit["subdirs"], fit["notes"]), ("/runs/x/stages/fit", ("2025",),
                                                                    ("missing ROOT",)))
        self.assertEqual(fit["steps"], (("DM0", "python3 fit.py -d 0"),))
        self.assertEqual(plan["overview"][-1], "2 stage(s), 0 job(s), 1 command(s)")
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse((self.root / "taufw_runs").exists())

    def test_a_quick_plan_says_which_stages_check_behind_the_screen(self):
        from TauFW.Utilities.Process import Command, CommandPlan
        path = self.recipe_file(self.recipes / "test.json")
        operations = self.menu(FakeUI()).operations
        commands = CommandPlan(cwd="/runs/x", commands=(Command("one", (sys.executable, "x.py"), "/runs/x"),))
        asked = []

        def build(recipe, reporter):
            plan = SimpleNamespace(bundle_dir=None, pico_config=None, sample_problems=(), sample_warnings=(),
                                   stages=[SimpleNamespace(stage=stage, note="", plan=commands, paths=(), sources={})
                                           for stage in ("shapes", "fit")])
            stages = dict(shapes=SimpleNamespace(null_inputs={}, deep_checks=True), fit=SimpleNamespace(null_inputs={}))
            return SimpleNamespace(recipe=recipe, stages=stages, plan=lambda deep=True: asked.append(deep) or plan)

        self.framework.side_effect = build
        view = operations.prepare_plan(path, quick=True)
        self.assertEqual([stage["checking"] for stage in view["stages"]], [True, False])
        self.assertIsNone(operations.check_plan(path, operations.prepare_plan(path)))  # nothing to check
        self.assertEqual(asked, [False, True])
        self.assertNotIn("checking", operations.prepare_plan(path)["stages"][0])

    def test_the_whole_plan_is_made_in_a_process_of_its_own(self):
        view = dict(name="quick", warnings=["one"], stages=[dict(id="shapes", checking=True)])
        made = []

        class Process:
            def __init__(self, argv, cwd, stdin, stdout, stderr, start_new_session):
                made.append(self)
                self.argv, self.cwd, self.session, self.returncode, self.killed = argv, cwd, start_new_session, None, 0
                stdout.write("Traceback\nImportError: no ROOT\n")

            def poll(self):
                return self.returncode

            def kill(self):
                self.killed += 1
                self.returncode = -9

            def wait(self):
                return self.returncode

        with mock.patch.object(interactive.subprocess, "Popen", Process):
            check = interactive._PlanCheck("/a/recipe.yml", view, "/launch")
            process = made[0]
            self.assertEqual(process.argv[1:4], ["-B", "-m", interactive.PLAN_CHECK_MODULE])
            self.assertEqual(process.argv[4], "/a/recipe.yml")
            self.assertEqual((process.cwd, process.session), ("/launch", True))  # no Ctrl+C, no resize signal
            self.assertIsNone(check.poll())  # it runs
            with open(process.argv[5], "w") as stream:
                json.dump(dict(name="whole", stages=[dict(id="shapes", notes=["lacks a branch"])]), stream)
            process.returncode = 0
            self.assertEqual(check.poll(), dict(name="whole", stages=[dict(id="shapes", notes=["lacks a branch"])]))
            self.assertIsNone(check.poll())  # answered once
            self.assertFalse(os.path.exists(check.directory))

            check = interactive._PlanCheck("/a/recipe.yml", view, "/launch")
            made[-1].returncode = 1  # it failed: the quick plan, Start opens, the reason as a warning
            failed = check.poll()
            self.assertEqual([stage["checking"] for stage in failed["stages"]], [False])
            self.assertEqual(failed["warnings"][0], "one")
            self.assertIn("did not run (exit code 1: ImportError: no ROOT)", failed["warnings"][1])
            self.assertTrue(view["stages"][0]["checking"])  # the quick view itself is not changed

            check = interactive._PlanCheck("/a/recipe.yml", view, "/launch", timeout=0)
            self.assertIn("did not finish in 0 s", check.poll()["warnings"][1])
            self.assertEqual(made[-1].killed, 1)
            check = interactive._PlanCheck("/a/recipe.yml", view, "/launch")
            check.cancel()  # the screen was left
            self.assertEqual(made[-1].killed, 1)
            self.assertFalse(os.path.exists(check.directory))

    def test_the_process_writes_the_whole_plan(self):
        from TauFW.Framework._internal.interfaces import plan_check
        output = str(self.root / "plan.json")
        with mock.patch.object(interactive, "_Operations") as operations:
            operations.return_value.prepare_plan.return_value = dict(name="whole", stages=[dict(id="a", files=())])
            self.assertEqual(plan_check.main(["/a/recipe.yml", output]), 0)
        operations.return_value.prepare_plan.assert_called_once_with("/a/recipe.yml")  # the whole plan
        with open(output) as stream:
            self.assertEqual(json.load(stream), dict(name="whole", stages=[dict(id="a", files=[])]))
        self.assertFalse(os.path.exists(output + ".part"))

    def test_the_plan_screen_opens_at_once_and_plans_once(self):
        path = self.recipe_file(self.recipes / "test.json")
        ui = mock.Mock()
        ui.select_recipe.return_value = ("select", 0)
        ui.recipe_plan.return_value = "start"
        self.menu(ui).start()
        self.assertEqual(ui.recipe_plan.call_args.args[0], "Start a new run / test")
        self.assertEqual(self.framework.call_count, 1)
        self.assertEqual([argv for argv, _ in self.started], [["start", str(path)]])
        ui.command_output.assert_not_called()
        ui.operation_error.assert_not_called()

    def test_invalid_selected_recipe_never_plans_or_starts(self):
        (self.recipes / "broken.json").write_text("{}")
        ui = FakeUI([1, 2, 4])  # broken.json, Back of its plan, then Back
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.menu(ui).start()
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(ui.messages, [])
        self.assertTrue(ui.plans[0]["errors"])  # the problems are on the plan screen
        self.framework.assert_not_called()
        self.assertEqual(self.started, [])

    def test_terminal_failure_returns_cli_fallback(self):
        curses = mock.Mock()
        curses.error = RuntimeError
        curses.wrapper.side_effect = lambda action: action(mock.Mock())  # the menu's one session
        ui = ConsoleUI(curses)
        parser = mock.Mock()
        with mock.patch.object(ConsoleUI, "open", return_value=ui), \
                mock.patch.object(ui, "main_menu", side_effect=RuntimeError("terminal closed")), \
                contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(run_menu(parser), 1)
        self.assertIn("Cannot open the TauFW terminal menu: terminal closed", output.getvalue())
        parser.print_help.assert_called_once()

    def test_no_argument_routing_and_explicit_help(self):
        spec = importlib.util.spec_from_file_location("menu_cli", checkout.TAUFW_SCRIPT)
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        with mock.patch("TauFW.Framework._internal.interfaces.interactive.run_menu", return_value=0) as launch:
            self.assertEqual(cli.main([]), 0)
            launch.assert_called_once()
            launch.reset_mock()
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as error:
                cli.main(["--help"])
            self.assertEqual(error.exception.code, 0)
            launch.assert_not_called()
        parser = mock.Mock()
        with mock.patch("sys.stdin.isatty", return_value=False), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(run_menu(parser), 1)
        parser.print_help.assert_called_once()


if __name__ == "__main__":
    unittest.main()
