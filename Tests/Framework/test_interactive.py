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
from TauFW.Framework.interfaces.interactive import Menu, run_menu
from TauFW.Framework.interfaces import interactive
from TauFW.Utilities.Menu import ConsoleUI


class FakeUI(ConsoleUI):
    """Use production screen adapters with scripted terminal input."""
    def __init__(self, choices=(), prompts=()):
        super().__init__(None)
        self.choices = iter(choices)
        self.prompts = iter(prompts)
        self.screens = []
        self.messages = []  # (title, text) of each panel over the screen (errors)
        self.outputs = []  # (title, argv after taufw.py, refresh) of each command shown
        self.output_answers = iter(())  # what command_output answers ("back" once these are used)

    def choose(self, title, choices, welcome=None, **layout):
        self.screens.append((title, choices))
        return next(self.choices)

    def prompt(self, title, default=""):
        return next(self.prompts)

    def message(self, title, lines, role=None):
        lines = [(lines, role)] if isinstance(lines, str) else lines
        self.messages.append((title, " ".join(text for text, _ in lines)))

    def help(self):
        pass

    def select_recipe(self, names, preview=None, broken=None, warnings=None, examples=False, **layout):
        self.broken = broken
        return super().select_recipe(names, examples=examples)

    def confirm_recipe(self, path, review=None, position=None):
        self.review = review
        return super().confirm_recipe(path)

    def run_progress(self, title, process):
        self.screens.append((title, process))

    def command_output(self, title, process, refresh=False):
        self.outputs.append((title, process.argv, refresh))
        return next(self.output_answers, "back")


# A small valid recipe: shapes of tuples made outside the run (a directory that exists, as the check wants), then the
# fit of those shapes (inputs are never null, CL §37).
SHAPES = {"stage": "shapes", "id": "shapes", "eras": [2025], "jet_wps": ["Tight"], "ele_wps": ["Tight"],
          "inputs": {"tuples": {"external": os.path.join(os.path.dirname(os.path.abspath(__file__)), "$ERA", "$GROUP")}}}
FIT = {"stage": "fit", "id": "fit", "inputs": {"shapes": "shapes"}}
STAGES = [SHAPES, FIT]


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
        patcher = mock.patch("TauFW.Framework.interfaces.interactive.Framework.from_recipe")
        self.framework = patcher.start()
        self.addCleanup(patcher.stop)
        self.framework.return_value.plan.return_value = mock.Mock(stages=())
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
        self.assertEqual(reference, interactive.CHECKOUT / "Docs/Manual/1-GettingStarted/UserConfig.md")
        self.assertIn("# Your user config", reference.read_text(encoding="utf-8"))
        path = self.root / "personal.yaml"
        with mock.patch.dict(os.environ, {"TAUFW_USER_CONFIG": str(path)}):
            self.assertEqual(operations.user_config_path(), path)
            self.assertIn("reviewed: false", path.read_text())
            path.write_text("broken existing file", encoding="utf-8")
            self.assertEqual(operations.user_config_path(), path)
            self.assertEqual(path.read_text(), "broken existing file")  # still opens so it can be repaired

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
        from TauFW.Utilities.Editor._file import Document
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

    def test_recipe_error_allows_another_selection(self):
        self.recipe_file(self.root / "bad.yml")
        self.recipe_file(self.root / "good.yml")
        self.framework.side_effect = [ValueError("invalid recipe"), self.framework.return_value]
        ui = FakeUI([1, 1, 2, 3], ["bad.yml", "good.yml"])  # ... Back of the review, Back
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.menu(ui).start()
        self.assertEqual(output.getvalue(), "")  # nothing printed over the screen
        self.assertEqual(ui.messages, [("Error", "ValueError: invalid recipe")])
        self.assertEqual(self.framework.call_count, 2)
        self.assertEqual(self.started, [])  # no plan, no start

    def test_run_order_and_advance_to_the_end_behind_the_menu(self):
        self.record("old", day=1)
        newest = self.record("new", day=2)
        ui = FakeUI([0, 0])
        self.menu(ui).continue_run()
        self.assertIn(newest.run_id + " | WAITING", ui.screens[0][1][0])
        (argv, options), = self.started
        self.assertEqual(argv, ["advance", newest.run_dir, "--wait"])
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

    def test_advance_once(self):
        record = self.record()
        self.menu(FakeUI([0, 1])).continue_run()
        self.assertEqual([argv for argv, _ in self.started], [["advance", record.run_dir]])

    def test_terminal_runs_offer_inspection_without_advancing(self):
        for state, title in (("DONE", "DONE"), ("FAILED", "Run failed at fit"), ("NOT_IMPLEMENTED", "BLOCKED")):
            with self.subTest(state=state):
                record = self.record(state=state)
                retry = state == "FAILED"  # CL §44: a failed fit can be retried: Retry fit comes first
                ui = FakeUI([0, 1, 2, None] if retry else [0, 0, 1, None])
                self.menu(ui).continue_run()
                self.assertIn(title, ui.screens[1][0])
                self.assertEqual(ui.outputs, [("Run status: " + record.run_id, ["status", record.run_dir], True)])
        self.assertEqual([argv[0] for argv, _ in self.started], ["status"] * 3)  # never an advance

    def test_retry_of_a_failed_run(self):
        """CL §44: Continue on a FAILED run whose stage can be retried runs `taufw.py retry RUN --wait`."""
        record = self.record(state="FAILED")
        ui = FakeUI([0, 0])
        self.menu(ui).continue_run()
        self.assertEqual([argv for argv, _ in self.started], [["retry", record.run_dir, "--wait"]])
        self.assertEqual(ui.screens[1][1][0], "Retry fit")
        self.assertEqual(self.started[0][1]["data"]["stages"][1]["state"], "FAILED")
        self.assertEqual(ui.screens[-1][0], "Run " + record.run_id)

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
        ui = FakeUI([0, 0])
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

    def test_plan_and_status_run_behind_the_menu(self):
        operations = self.menu(FakeUI()).operations
        record = self.record()
        operations.start_command("status", record.run_dir)
        recipe = self.recipe_file(self.root / "p.json")
        operations.start_command("plan", str(recipe))
        (status, options), (plan, _) = self.started
        self.assertEqual((status, plan), (["status", record.run_dir], ["plan", str(recipe)]))
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

    def test_back_from_continue_goes_back_to_the_picker(self):
        self.record()
        ui = FakeUI([0, 2, None])
        self.menu(ui).continue_run()
        self.assertTrue(ui.screens[1][0].startswith("Continue:"))
        self.assertEqual(ui.screens[2][0], "Select an existing run")
        self.assertEqual(self.started, [])

    def eos(self):
        """The tuples of tes_id_2025 are on EOS; here (e.g. Windows) /eos/... counts as existing."""
        isdir = os.path.isdir
        patcher = mock.patch("TauFW.Framework.recipes.validation.os.path.isdir",
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
        self.assertEqual([argv for argv, _ in self.started], [["start", str(recipes_dir / "tes_id_2025"), "--wait"]])

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
                         [["start", str(examples_dir / "cmsdas26_ztt"), "--wait"]])

    def test_dispatch_uses_semantic_actions_without_screen_positions(self):
        ui = mock.Mock()
        ui.main_menu.side_effect = ["start", "exit"]
        ui.select_recipe.return_value = ("manual", None)
        ui.recipe_path.return_value = "custom.yml"
        ui.confirm_recipe.return_value = "start"
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
        self.assertEqual(view["stages"], (("prepare", "python", ""), ("hists", "controlhists", ""),
                                          ("check", "python", "look at the hists"), ("shapes", "shapes", ""),
                                          ("fit", "fit", ""),
                                          ("report", "python", "")))
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
        self.assertEqual(view["stages"], (("fit", "fit", ""),))  # the stages that could be read

    def test_review_reloads_recipe_and_preserves_nonfatal_notes_silently(self):
        path = self.recipe_file(self.recipes / "test.json", name="before")
        operations = self.menu(FakeUI()).operations
        self.assertEqual(operations.recipe_preview(path)["name"], "before")
        self.recipe_file(path, name="after")

        def build(recipe, reporter):
            reporter.warning("configuration warning")
            self.assertEqual(recipe.name, "after")
            return mock.Mock(plan=mock.Mock(return_value=mock.Mock(stages=[
                mock.Mock(stage="fit", note="environment unavailable", plan=None),
                mock.Mock(stage="hists", note="", plan=mock.Mock(notes=("missing ROOT",)))
            ])))

        self.framework.side_effect = build
        before = path.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            review = operations.prepare_review(path)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(review["name"], "after")
        self.assertEqual(review["notes"], ("fit: environment unavailable", "hists: missing ROOT",
                                          "configuration warning"))
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse((self.root / "taufw_runs").exists())

    def test_detailed_plan_returns_to_review_before_launch(self):
        path = self.recipe_file(self.recipes / "test.json")
        ui = mock.Mock()
        ui.select_recipe.return_value = ("select", 0)
        ui.confirm_recipe.side_effect = ["plan", "start"]
        self.menu(ui).start()
        self.assertEqual(ui.confirm_recipe.call_count, 2)
        first, second = ui.confirm_recipe.call_args_list
        self.assertIs(first.kwargs["position"], second.kwargs["position"])
        self.assertIs(first.kwargs["review"], second.kwargs["review"])
        self.assertEqual(self.framework.call_count, 1)
        self.assertEqual([argv for argv, _ in self.started], [["plan", str(path)], ["start", str(path), "--wait"]])
        self.assertEqual(ui.command_output.call_args.args[0], "Plan: test")
        self.assertEqual(ui.command_output.call_args.kwargs, dict(refresh=False))
        ui.operation_error.assert_not_called()

    def test_invalid_selected_recipe_never_plans_or_starts(self):
        (self.recipes / "broken.json").write_text("{}")
        ui = FakeUI([1, 4])  # broken.json, then Back
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.menu(ui).start()
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(len(ui.messages), 1)
        self.assertIn("RecipeError", ui.messages[0][1])
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
        with mock.patch("TauFW.Framework.interfaces.interactive.run_menu", return_value=0) as launch:
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
