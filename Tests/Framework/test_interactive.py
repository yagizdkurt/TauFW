"""Menu navigation and dispatch without a real terminal, ROOT, or batch jobs."""
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from types import SimpleNamespace

import checkout
from TauFW.Framework import Recipe, RunRecord
from TauFW.Framework.interactive import Menu, run_menu
from TauFW.Framework import interactive
from TauFW.Utilities.Menu import ConsoleUI


class FakeUI(ConsoleUI):
    """Use production screen adapters with scripted terminal input."""
    def __init__(self, choices=(), prompts=()):
        self.choices = iter(choices)
        self.prompts = iter(prompts)
        self.screens = []
        self.pauses = 0

    def choose(self, title, choices, welcome=None, **layout):
        self.screens.append((title, choices))
        return next(self.choices)

    def prompt(self, title, default=""):
        return next(self.prompts)

    def pause(self):
        self.pauses += 1

    def help(self):
        pass

    def select_recipe(self, names, preview=None, broken=None, warnings=None):
        self.broken = broken
        return super().select_recipe(names)

    def confirm_recipe(self, path, review=None, position=None):
        self.review = review
        return super().confirm_recipe(path)


FIT = {"stage": "fit", "id": "fit", "inputs": {"shapes": None}}


class MenuTests(unittest.TestCase):
    def test_test_adapter_uses_checkout_current_python_and_quiet_arguments(self):
        operations = self.menu(FakeUI()).operations
        for family, cases, suffix in (("all", [], ["all"]),
                                      ("checks", ["unit.utilities"], ["checks", "--case", "unit.utilities"]),
                                      ("normal", [], ["normal"]),
                                      ("bbb", ["plotter.unroll"], ["bbb", "check", "--case", "plotter.unroll"]),
                                      ("environment", [], ["environment"])):
            with mock.patch.object(interactive.subprocess, "Popen") as launch, \
                    contextlib.redirect_stdout(io.StringIO()):
                launch.return_value.wait.return_value = 1
                self.assertEqual(operations.execute_tests(family, cases), 1)
            self.assertEqual(launch.call_args.args[0],
                             [sys.executable, "-B", str(checkout.REPO / "Tests/run.py")] + suffix)
            self.assertEqual(launch.call_args.kwargs["cwd"], str(checkout.REPO))
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
        with mock.patch.object(interactive, "__file__", str(self.root / "Framework/python/interactive.py")):
            with self.assertRaisesRegex(RuntimeError, "complete TauFW checkout"):
                operations.test_catalog()

    def test_test_interrupt_stops_process_group_and_waits(self):
        operations = self.menu(FakeUI()).operations
        process = mock.Mock(pid=123, wait=mock.Mock(side_effect=[KeyboardInterrupt(), 130]))
        posix = SimpleNamespace(name="posix", killpg=mock.Mock())
        with mock.patch.object(interactive, "os", posix), \
                mock.patch.object(interactive.subprocess, "Popen", return_value=process):
            with self.assertRaises(KeyboardInterrupt):
                operations.execute_tests("normal", [])
        posix.killpg.assert_called_once_with(123, interactive.signal.SIGINT)
        self.assertEqual(process.wait.call_args_list, [mock.call(), mock.call(timeout=5)])
        process.wait.side_effect = [KeyboardInterrupt(), interactive.subprocess.TimeoutExpired("tests", 5), -9]
        posix.killpg.reset_mock()
        with mock.patch.object(interactive, "os", posix), \
                mock.patch.object(interactive.signal, "SIGKILL", 9, create=True), \
                mock.patch.object(interactive.subprocess, "Popen", return_value=process):
            with self.assertRaises(KeyboardInterrupt):
                operations.execute_tests("normal", [])
        self.assertEqual(posix.killpg.call_args_list, [mock.call(123, interactive.signal.SIGINT),
                                                     mock.call(123, 9)])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.recipes = self.root / "recipes"
        self.recipes.mkdir()
        self.commands = {name: mock.Mock(return_value=0)
                         for name in ("plan", "start", "advance", "status")}
        patcher = mock.patch("TauFW.Framework.interactive.Framework.from_recipe")
        self.framework = patcher.start()
        self.addCleanup(patcher.stop)
        self.framework.return_value.plan.return_value = mock.Mock(stages=())

    def menu(self, ui):
        return Menu(self.commands, ui, self.root, self.recipes)

    def recipe_file(self, path, name="test", stages=None):
        path.write_text(json.dumps(dict(name=name, stages=stages or [FIT])),
                        encoding="utf-8")
        return path

    def record(self, name="test", state="WAITING", day=1):
        recipe = Recipe.from_dict({"name": name, "stages": [FIT]})
        record = RunRecord.create(recipe, str(self.root / "taufw_runs"),
                                  now=datetime(2026, 10, day))
        Path(record.run_dir).mkdir(parents=True)
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
        ui = FakeUI([3, 0], ["custom.yml"])
        self.recipe_file(self.root / "custom.yml")
        order = []
        planned = self.framework.return_value
        self.framework.side_effect = lambda *args, **values: order.append("prepare") or planned
        self.commands["start"].side_effect = lambda args: order.append("start") or 0
        self.menu(ui).start()
        self.assertEqual(ui.screens[0][1][:3], ["a.json", "b.yml", "c_bundle"])
        self.assertEqual(order, ["prepare", "start"])
        self.commands["plan"].assert_not_called()
        args = self.commands["start"].call_args.args[0]
        self.assertEqual(args.recipe, str(self.root / "custom.yml"))
        self.assertFalse(args.wait)
        self.assertIsNone(args.run_root)
        self.assertEqual(ui.pauses, 1)

    def test_recipe_error_allows_another_selection(self):
        self.recipe_file(self.root / "bad.yml")
        self.recipe_file(self.root / "good.yml")
        self.framework.side_effect = [ValueError("invalid recipe"), self.framework.return_value]
        ui = FakeUI([0, 0, 2, 1], ["bad.yml", "good.yml"])
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.menu(ui).start()
        self.assertIn("invalid recipe", output.getvalue())
        self.assertEqual(self.framework.call_count, 2)
        self.commands["plan"].assert_not_called()
        self.commands["start"].assert_not_called()

    def test_run_order_and_polling_validation(self):
        self.record("old", day=1)
        newest = self.record("new", day=2)
        ui = FakeUI([0, 1], ["0", "bad", "30"])
        with contextlib.redirect_stdout(io.StringIO()):
            self.menu(ui).continue_run()
        self.assertIn(newest.run_id + " | WAITING", ui.screens[0][1][0])
        args = self.commands["advance"].call_args.args[0]
        self.assertEqual((args.run_dir, args.wait, args.poll), (newest.run_dir, True, 30))

    def test_one_advance_and_poll_default(self):
        self.record()
        self.menu(FakeUI([0, 0])).continue_run()
        self.assertFalse(self.commands["advance"].call_args.args[0].wait)
        self.menu(FakeUI([0, 1], ["600"])).continue_run()
        self.assertEqual(self.commands["advance"].call_args.args[0].poll, 600)

    def test_terminal_runs_offer_inspection_without_advancing(self):
        for state in ("DONE", "FAILED", "NOT_IMPLEMENTED"):
            with self.subTest(state=state):
                record = self.record(state=state)
                ui = FakeUI([0, 0, 1, 1, None])
                self.menu(ui).continue_run()
                self.assertIn(record.state, ui.screens[1][0])
        self.commands["advance"].assert_not_called()
        self.assertEqual(self.commands["status"].call_count, 3)

    def test_inspect_refreshes_and_does_not_write(self):
        record = self.record()
        before = Path(record.path).read_bytes()
        self.menu(FakeUI([0, 0, 1, 2])).inspect()
        self.assertEqual(self.commands["status"].call_count, 2)
        self.assertEqual(Path(record.path).read_bytes(), before)

    def test_empty_picker_and_unreadable_run_recovery(self):
        ui = FakeUI([0, 1], ["missing"])
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertIsNone(self.menu(ui)._pick_run())
        self.assertIn("Cannot read run", output.getvalue())
        self.assertEqual(ui.screens[0][1], ["Enter another run directory", "Back"])

    def test_interrupted_operation_returns_to_main_menu(self):
        self.record()
        self.commands["advance"].side_effect = KeyboardInterrupt
        ui = FakeUI([1, 0, 1, 5], ["600"])
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(self.menu(ui).run(), 0)
        self.assertIn("not cancelled", output.getvalue())
        self.assertEqual(ui.screens[-1][0], "TauFW")

    def test_escape_from_poll_prompt_goes_back_to_continue_then_picker(self):
        self.record()
        ui = FakeUI([0, 1, None, None], [None])
        self.menu(ui).continue_run()
        self.assertTrue(ui.screens[2][0].startswith("Continue:"))
        self.assertEqual(ui.screens[3][0], "Select an existing run")
        self.commands["advance"].assert_not_called()

    def eos(self):
        """The tuples of tes_id_2025 are on EOS; here (e.g. Windows) /eos/... counts as existing."""
        isdir = os.path.isdir
        patcher = mock.patch("TauFW.Framework.validation.os.path.isdir",
                             side_effect=lambda path: str(path).startswith("/eos/") or isdir(path))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_default_recipes_are_the_analysis_bundles(self):
        self.eos()
        recipes_dir = checkout.REPO / "Analyses"
        expected = sorted(path.name for path in recipes_dir.iterdir() if (path / "recipe.yml").is_file())
        self.assertIn("tes_id_2025", expected)
        ui = FakeUI([expected.index("tes_id_2025"), 0])
        menu = Menu(self.commands, ui, launch_dir=self.root)
        self.assertEqual(menu.operations.recipes_dir, recipes_dir)
        menu.start()
        self.assertEqual(ui.screens[0][1][:-2], expected)
        self.assertEqual(ui.broken, [name == "example_broken" for name in expected])  # the validation demo
        self.assertEqual(self.commands["start"].call_args.args[0].recipe, str(recipes_dir / "tes_id_2025"))

    def test_dispatch_uses_semantic_actions_without_screen_positions(self):
        ui = mock.Mock()
        ui.main_menu.side_effect = ["start", "exit"]
        ui.select_recipe.return_value = ("manual", None)
        ui.recipe_path.return_value = "custom.yml"
        ui.confirm_recipe.return_value = "start"
        self.recipe_file(self.root / "custom.yml")
        self.assertEqual(self.menu(ui).run(), 0)
        self.commands["start"].assert_called_once()
        ui.choose.assert_not_called()
        ui.prompt.assert_not_called()

    def test_bundled_previews_use_recipe_order_without_planning(self):
        self.eos()
        operations = self.menu(FakeUI()).operations
        expected = {
            "example_mutau": (("production", "production"), ("plots", "plots")),
            "tes_id_2025": (("plots", "plots"), ("histograms", "histograms"),
                            ("fit", "fit"), ("fit_summary", "python")),
        }
        for bundle, stages in expected.items():
            with self.subTest(bundle=bundle):
                view = operations.recipe_preview(checkout.REPO / "Analyses" / bundle)
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
            {"stage": "plots", "id": "plots", "inputs": {"tuples": None}, "eras": [2025]},
            {"stage": "python", "id": "check", "description": "look at the plots", "inputs": {"plots": "plots"},
             "file": "steps/check.py"},
            FIT,
            {"stage": "python", "id": "report", "inputs": {"fit": "fit"}, "file": "steps/report.py"},
        ])
        view = self.menu(FakeUI()).operations.recipe_preview(path)
        self.assertEqual(view["stages"], (("prepare", "python", ""), ("plots", "plots", ""),
                                          ("check", "python", "look at the plots"), ("fit", "fit", ""),
                                          ("report", "python", "")))
        self.assertEqual(view["problems"], ())
        self.framework.assert_not_called()

    def test_runs_of_the_recipes_run_roots_are_listed(self):
        elsewhere = self.root / "elsewhere"
        (self.recipes / "a.json").write_text(json.dumps(dict(name="a", run_root=str(elsewhere), stages=[FIT])),
                                             encoding="utf-8")
        (self.recipes / "b.json").write_text(json.dumps(dict(name="b", run_root=str(elsewhere), stages=[FIT])),
                                             encoding="utf-8")  # the same root: listed once
        (self.recipes / "c.json").write_text("{not json", encoding="utf-8")  # unreadable: skipped
        here = self.record("here", day=1)
        recipe = Recipe.from_dict({"name": "there", "stages": [FIT]})
        there = RunRecord.create(recipe, str(elsewhere), now=datetime(2026, 10, 2))
        Path(there.run_dir).mkdir(parents=True)
        there.save(now="2026-10-02 00:00:00")
        operations = self.menu(FakeUI()).operations
        self.assertEqual(operations.run_roots(), [(self.root / "taufw_runs").resolve(), elsewhere.resolve()])
        self.assertEqual([row[1] for row in operations.runs()], [there.run_dir, here.run_dir])

    def test_recipe_warnings_are_shown_but_do_not_break(self):
        self.recipe_file(self.recipes / "a.json")  # no run_root
        ui = FakeUI([2])  # Back
        self.menu(ui).start()
        self.assertEqual(ui.broken, [False])
        view = self.menu(FakeUI()).operations.recipe_preview(self.recipes / "a.json")
        self.assertEqual(view["problems"], ())
        self.assertEqual(len(view["warnings"]), 1)
        self.assertTrue(view["warnings"][0].startswith("run_root: not set"))

    def test_broken_recipes_are_marked_and_list_every_problem(self):
        self.recipe_file(self.recipes / "a_good.json")
        self.recipe_file(self.recipes / "b_bad.json", stages=[
            {"stage": "histograms", "inputs": {"tuples": None}, "eras": [2025], "jet_wps": ["Tight"],
             "ele_wps": ["Tight"]},
            {"stage": "fit", "id": "fit", "inputs": {"shapes": "histo"}},
        ])
        ui = FakeUI([3])  # Back
        self.menu(ui).start()
        self.assertEqual(ui.broken, [False, True])
        view = self.menu(FakeUI()).operations.recipe_preview(self.recipes / "b_bad.json")
        self.assertEqual(view["problems"], ("stages[0] (histograms): missing 'id' (every stage needs a unique id, "
                                            "e.g. id: histograms)",
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
                mock.Mock(stage="plots", note="", plan=mock.Mock(notes=("missing ROOT",)))
            ])))

        self.framework.side_effect = build
        before = path.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            review = operations.prepare_review(path)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(review["name"], "after")
        self.assertEqual(review["notes"], ("fit: environment unavailable", "plots: missing ROOT",
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
        self.assertEqual(self.commands["plan"].call_args.args[0].recipe, str(path))
        self.assertEqual(self.commands["start"].call_args.args[0].recipe, str(path))
        self.assertEqual(ui.pause.call_count, 2)

    def test_invalid_selected_recipe_never_plans_or_starts(self):
        (self.recipes / "broken.json").write_text("{}")
        ui = FakeUI([0, 2])
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.menu(ui).start()
        self.assertIn("RecipeError", output.getvalue())
        self.framework.assert_not_called()
        self.commands["start"].assert_not_called()
        self.assertEqual(ui.pauses, 1)

    def test_terminal_failure_returns_cli_fallback(self):
        curses = mock.Mock()
        curses.error = RuntimeError
        ui = ConsoleUI(curses)
        parser = mock.Mock()
        with mock.patch.object(ConsoleUI, "open", return_value=ui), \
                mock.patch.object(ui, "main_menu", side_effect=RuntimeError("terminal closed")), \
                contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(run_menu(self.commands, parser), 1)
        self.assertIn("Cannot open the TauFW terminal menu: terminal closed", output.getvalue())
        parser.print_help.assert_called_once()

    def test_no_argument_routing_and_explicit_help(self):
        spec = importlib.util.spec_from_file_location("menu_cli", checkout.TAUFW_SCRIPT)
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        with mock.patch("TauFW.Framework.interactive.run_menu", return_value=0) as launch:
            self.assertEqual(cli.main([]), 0)
            launch.assert_called_once()
            launch.reset_mock()
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as error:
                cli.main(["--help"])
            self.assertEqual(error.exception.code, 0)
            launch.assert_not_called()
        parser = mock.Mock()
        with mock.patch("sys.stdin.isatty", return_value=False), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(run_menu({}, parser), 1)
        parser.print_help.assert_called_once()


if __name__ == "__main__":
    unittest.main()
