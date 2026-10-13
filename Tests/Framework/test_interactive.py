"""Menu navigation and dispatch without a real terminal, ROOT, or batch jobs."""
import contextlib
import importlib.util
import io
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

import checkout
from TauFW.Framework import Recipe, RunRecord
from TauFW.Framework.interactive import Menu, run_menu
from TauFW.Utilities.Menu import ConsoleUI


class FakeUI(ConsoleUI):
    """Use production screen adapters with scripted terminal input."""
    def __init__(self, choices=(), prompts=()):
        self.choices = iter(choices)
        self.prompts = iter(prompts)
        self.screens = []
        self.pauses = 0

    def choose(self, title, choices, welcome=None):
        self.screens.append((title, choices))
        return next(self.choices)

    def prompt(self, title, default=""):
        return next(self.prompts)

    def pause(self):
        self.pauses += 1

    def help(self):
        pass


class MenuTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.recipes = self.root / "recipes"
        self.recipes.mkdir()
        self.commands = {name: mock.Mock(return_value=0)
                         for name in ("plan", "start", "advance", "status")}

    def menu(self, ui):
        return Menu(self.commands, ui, self.root, self.recipes)

    def record(self, name="test", state="WAITING", day=1):
        recipe = Recipe.from_dict({"name": name, "stages": [{"stage": "fit"}]})
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
        order = []
        for name in ("plan", "start"):
            self.commands[name].side_effect = lambda args, name=name: order.append(name) or 0
        self.menu(ui).start()
        self.assertEqual(ui.screens[0][1][:3], ["a.json", "b.yml", "c_bundle"])
        self.assertEqual(order, ["plan", "start"])
        args = self.commands["start"].call_args.args[0]
        self.assertEqual(args.recipe, str(self.root / "custom.yml"))
        self.assertFalse(args.wait)
        self.assertIsNone(args.run_root)
        self.assertEqual(ui.pauses, 2)

    def test_recipe_error_allows_another_selection(self):
        self.commands["plan"].side_effect = [ValueError("invalid recipe"), 0]
        ui = FakeUI([0, 0, 1, 1], ["bad.yml", "good.yml"])
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.menu(ui).start()
        self.assertIn("invalid recipe", output.getvalue())
        self.assertEqual(self.commands["plan"].call_count, 2)
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
        ui = FakeUI([1, 0, 1, 4], ["600"])
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

    def test_default_recipes_are_the_analysis_bundles(self):
        ui = FakeUI([0, 0])
        menu = Menu(self.commands, ui, launch_dir=self.root)
        self.assertEqual(menu.operations.recipes_dir, checkout.REPO / "Analyses")
        expected = sorted(path.name for path in menu.operations.recipes_dir.iterdir()
                          if (path / "recipe.yml").is_file())
        self.assertIn("tes_id_2025", expected)
        self.assertTrue(expected)
        menu.start()
        self.assertEqual(ui.screens[0][1][:-2], expected)
        self.assertEqual(self.commands["start"].call_args.args[0].recipe,
                         str(menu.operations.recipes_dir / expected[0]))

    def test_dispatch_uses_semantic_actions_without_screen_positions(self):
        ui = mock.Mock()
        ui.main_menu.side_effect = ["start", "exit"]
        ui.select_recipe.return_value = ("manual", None)
        ui.recipe_path.return_value = "custom.yml"
        ui.confirm_recipe.return_value = "start"
        self.assertEqual(self.menu(ui).run(), 0)
        self.commands["start"].assert_called_once()
        ui.choose.assert_not_called()
        ui.prompt.assert_not_called()

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
