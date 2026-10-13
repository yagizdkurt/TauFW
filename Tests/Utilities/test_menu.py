"""Menu screens without a real terminal or Framework imports."""
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

import checkout
from TauFW.Utilities.Menu import ConsoleUI, MenuNavigation


class ScreenTests(unittest.TestCase):
    """Exercise actual screen key handling and wrapper lifetime with a fake terminal."""
    def curses(self, keys):
        screen = mock.Mock()
        screen.getmaxyx.return_value = (12, 65)
        screen.getch.side_effect = keys
        curses = mock.Mock()
        curses.error = RuntimeError
        for name, value in (("KEY_UP", 1001), ("KEY_DOWN", 1002), ("KEY_ENTER", 1003),
                            ("KEY_NPAGE", 1004), ("KEY_PPAGE", 1005), ("KEY_BACKSPACE", 1006)):
            setattr(curses, name, value)
        curses.wrapper.side_effect = lambda action: action(screen)
        return curses, screen

    def test_navigation_uses_injected_operations(self):
        ui = mock.Mock()
        operations = mock.Mock()
        operations.execute.return_value = 0
        operations.recipes.return_value = [Path("recipes/example.yml")]
        operations.runs.return_value = [("today", "runs/example", ("example", "WAITING", "today"))]
        record = mock.Mock(run_id="example", run_dir="runs/example", state="WAITING")
        operations.load_run.return_value = record
        operations.can_advance.return_value = True
        operations.validate_poll.side_effect = [ValueError("invalid"), 30]
        ui.main_menu.side_effect = ["start", "continue", "exit"]
        ui.select_recipe.return_value = ("select", 0)
        ui.confirm_recipe.return_value = "start"
        ui.select_run.return_value = ("select", 0)
        ui.continue_actions.return_value = "wait"
        ui.poll_interval.side_effect = ["bad", "30"]
        self.assertEqual(MenuNavigation(ui, operations).run(), 0)
        self.assertEqual(operations.execute.call_args_list, [
            mock.call("plan", recipe=str(Path("recipes/example.yml"))),
            mock.call("start", recipe=str(Path("recipes/example.yml"))),
            mock.call("advance", run_dir="runs/example", wait=True, poll=30),
        ])
        operations.load_run.assert_called_once_with("runs/example")
        operations.can_advance.assert_called_once_with(record)
        self.assertEqual(operations.validate_poll.call_args_list, [mock.call("bad"), mock.call("30")])
        ui.invalid_poll_interval.assert_called_once()
        self.assertEqual(ui.pause.call_count, 3)

    def test_semantic_screen_actions_and_cancellation(self):
        ui = ConsoleUI(mock.Mock())
        cases = [
            (ui.main_menu, (), ["start", "continue", "inspect", "help", "exit"]),
            (ui.confirm_recipe, ("example.yml",), ["start", "back"]),
            (ui.status_actions, ("run",), ["refresh", "back"]),
            (ui.terminal_run_actions, ("DONE",), ["inspect", "back"]),
            (ui.continue_actions, ("run",), ["advance", "wait", "back"]),
            (ui.select_recipe, (["example.yml"],),
             [("select", 0), ("manual", None), ("back", None)]),
            (ui.select_run, ([("run", "WAITING", "today")],),
             [("select", 0), ("manual", None), ("back", None)]),
        ]
        for method, args, expected in cases:
            with self.subTest(screen=method.__name__):
                with mock.patch.object(ui, "choose", side_effect=list(range(len(expected))) + [None]):
                    self.assertEqual([method(*args) for _ in expected], expected)
                    self.assertEqual(method(*args), expected[-1])

    def test_unreadable_run_format_and_prompt_defaults(self):
        ui = ConsoleUI(mock.Mock())
        with mock.patch.object(ui, "choose", return_value=None) as choose:
            ui.select_run([("broken", None, None)])
        self.assertEqual(choose.call_args.args[1],
                         ["broken | UNREADABLE", "Enter another run directory", "Back"])
        with mock.patch.object(ui, "prompt", return_value=None) as prompt:
            self.assertIsNone(ui.recipe_path("launch"))
            self.assertIsNone(ui.run_path("launch"))
            self.assertIsNone(ui.poll_interval())
        self.assertEqual(prompt.call_args_list, [
            mock.call("Recipe path (relative to launch)"),
            mock.call("Run directory (relative to launch)"),
            mock.call("Polling interval in seconds", "600"),
        ])

    def test_import_is_silent_without_framework_or_curses(self):
        script = """
import sys
sys.modules['curses'] = None
sys.modules['TauFW.Framework'] = None
sys.path.insert(0, %r)
import checkout
from TauFW.Utilities.Menu import ConsoleUI, MenuNavigation
import TauFW.Utilities.Menu as menu
assert menu.__all__ == ['ConsoleUI', 'MenuNavigation']
assert not any(name.startswith('TauFW.Framework.') for name in sys.modules)
assert sys.modules['curses'] is None
ConsoleUI(None)
""" % str(Path(__file__).resolve().parent)
        result = subprocess.run([sys.executable, "-B", "-c", script],
                                capture_output=True, text=True, check=True)
        self.assertEqual((result.stdout, result.stderr), ("", ""))

    def test_terminal_open_and_initialization_failures(self):
        curses = mock.Mock()
        curses.error = RuntimeError
        with mock.patch("sys.platform", "linux"), \
                mock.patch("sys.stdin.isatty", return_value=True), \
                mock.patch("sys.stdout.isatty", return_value=True):
            with mock.patch.dict(sys.modules, {"curses": curses}):
                ui = ConsoleUI.open(mock.Mock())
                self.assertIs(ui.curses, curses)
                curses.setupterm.assert_called_once()
                for error, expected in [(OSError("unsupported"), "requires curses"),
                                        (RuntimeError("setup failed"), "Cannot initialize")]:
                    with self.subTest(error=error):
                        curses.setupterm.side_effect = error
                        parser = mock.Mock()
                        with contextlib.redirect_stderr(io.StringIO()) as output:
                            self.assertIsNone(ConsoleUI.open(parser))
                        self.assertIn(expected, output.getvalue())
                        parser.print_help.assert_called_once()
            with mock.patch.dict(sys.modules, {"curses": None}):
                parser = mock.Mock()
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertIsNone(ConsoleUI.open(parser))
                parser.print_help.assert_called_once()

    def test_arrows_enter_escape_and_typed_path(self):
        curses, screen = self.curses([1002, 10, 27])
        ui = ConsoleUI(curses)
        self.assertEqual(ui.choose("Menu", ["First", "Second"]), 1)
        self.assertIsNone(ui.choose("Menu", ["First"]))
        screen.get_wch.side_effect = ["a", "x", 1006, ".", "y", "m", "l", "\n"]
        self.assertEqual(ui.prompt("Path"), "a.yml")
        self.assertEqual(curses.wrapper.call_count, 3)

    def test_help_topics_and_scrolling(self):
        curses, screen = self.curses([1002, 1004, 1005, 27])
        ConsoleUI(curses).help()
        drawn = [call.args[2] for call in screen.addnstr.call_args_list]
        self.assertTrue(any("Recipes are YAML" in line for line in drawn))


if __name__ == "__main__":
    unittest.main()
