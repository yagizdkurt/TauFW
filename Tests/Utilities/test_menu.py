"""Menu screens without a real terminal or Framework imports."""
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
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
        curses.A_REVERSE = 256
        curses.COLOR_BLACK, curses.COLOR_GREEN, curses.COLOR_RED, curses.COLOR_CYAN = 0, 2, 1, 6
        curses.color_pair.side_effect = lambda pair: pair * 512
        for name, value in (("KEY_UP", 1001), ("KEY_DOWN", 1002), ("KEY_ENTER", 1003),
                            ("KEY_NPAGE", 1004), ("KEY_PPAGE", 1005), ("KEY_BACKSPACE", 1006)):
            setattr(curses, name, value)
        curses.wrapper.side_effect = lambda action: action(screen)
        return curses, screen

    def test_test_checkboxes_require_selection_and_review_restores_terminal(self):
        items = [dict(id="example", description="Local example", dependencies=["ROOT"])]
        # Empty Run is refused, Enter on an item does not toggle it, Space does.
        curses, screen = self.curses([10, 1002, 10, 32, 1001, 10])
        ui = ConsoleUI(curses)
        self.assertEqual(ui.test_selection("Tests", items), ["example"])
        curses.beep.assert_called_once()
        curses.wrapper.assert_called_once()
        self.assertIn("Dependencies: ROOT", [call.args[2] for call in screen.addnstr.call_args_list])
        for keys in ([27], [1002, 1002, 10]):
            curses, _ = self.curses(keys)
            self.assertIsNone(ConsoleUI(curses).test_selection("Tests", items))
        curses, _ = self.curses([32, 10])
        self.assertEqual(ConsoleUI(curses).test_selection("Review", items, review=True), ["example"])

    def test_testing_navigation_selection_review_and_recovery(self):
        item = dict(id="example", description="Local example", dependencies=[])
        for outcome in (0, 1, KeyboardInterrupt(), RuntimeError("failed")):
            with self.subTest(outcome=outcome):
                ui, operations = mock.Mock(), mock.Mock()
                ui.main_menu.side_effect = ["tests", "exit"]
                ui.tests_menu.side_effect = ["normal", "back"]
                ui.test_family.return_value = "choose"
                ui.test_selection.side_effect = [["example"], ["example"]]
                operations.test_catalog.return_value = {"normal": [item]}
                if isinstance(outcome, BaseException):
                    operations.execute_tests.side_effect = outcome
                else:
                    operations.execute_tests.return_value = outcome
                self.assertEqual(MenuNavigation(ui, operations).run(), 0)
                operations.execute_tests.assert_called_once_with("normal", ["example"])
                self.assertEqual(ui.test_selection.call_args_list[-1],
                                 mock.call("Review / Normal tests", [item], review=True))
                ui.pause.assert_called_once()
                if isinstance(outcome, KeyboardInterrupt):
                    ui.interrupted_tests.assert_called_once()

    def test_testing_back_empty_selection_and_catalog_failure_do_not_execute(self):
        item = dict(id="example", description="Local example", dependencies=[])
        for action, selection in (("back", None), ("choose", []), ("all", None)):
            ui, operations = mock.Mock(), mock.Mock()
            ui.tests_menu.side_effect = ["normal", "back"]
            ui.test_family.return_value = action
            ui.test_selection.return_value = selection
            operations.test_catalog.return_value = {"normal": [item]}
            MenuNavigation(ui, operations).tests()
            operations.execute_tests.assert_not_called()
        ui, operations = mock.Mock(), mock.Mock()
        ui.tests_menu.side_effect = ["all", "back"]
        operations.test_catalog.side_effect = RuntimeError("Cannot load test choices")
        MenuNavigation(ui, operations).tests()
        operations.execute_tests.assert_not_called()
        ui.operation_error.assert_called_once()
        ui.pause.assert_called_once()

    def test_all_and_environment_review_before_running(self):
        for family in ("all", "environment"):
            ui, operations = mock.Mock(), mock.Mock()
            ui.tests_menu.side_effect = [family, "back"]
            operations.test_catalog.return_value = {
                name: [dict(id=name, description=name, dependencies=[])]
                for name in ("checks", "normal", "bbb")}
            ui.test_selection.return_value = ["reviewed"]
            MenuNavigation(ui, operations).tests()
            operations.execute_tests.assert_called_once_with(family, [])
            self.assertTrue(ui.test_selection.call_args.kwargs["review"])
            if family == "all":
                self.assertEqual([item["id"] for item in ui.test_selection.call_args.args[1]],
                                 ["checks", "normal", "bbb"])
            else:
                operations.test_catalog.assert_not_called()
            ui.pause.assert_called_once()

    def test_entry_banners_welcome_text_and_compact_layout(self):
        from TauFW.Utilities.Menu.banner import FULL
        for installer in (False, True):
            with self.subTest(installer=installer):
                curses, screen = self.curses([27])
                screen.getmaxyx.return_value = (40, 80)
                ui = ConsoleUI(curses)
                if installer:
                    ui.setup_checklist([("combine", "Combine")], ["combine"])
                    welcome = "Welcome to TauFW fast installer!"
                else:
                    ui.main_menu()
                    welcome = "Welcome to TauFW!"
                calls = screen.addnstr.call_args_list
                drawn = [call.args[2] for call in calls]
                self.assertEqual(drawn[:len(FULL)], list(FULL))
                self.assertIn(welcome, drawn)
                self.assertIn("Tau analysis framework", drawn[len(FULL) - 4])
                self.assertIn("V0.0", drawn[len(FULL) - 3])
                self.assertTrue(all(call.args[0] < 38 for call in calls[:-1]))
        from TauFW.Utilities.Menu.banner import BOXED
        for dimensions in ((28, 80), (30, 80), (30, 65)):
            with self.subTest(dimensions=dimensions):
                curses, screen = self.curses([27])
                screen.getmaxyx.return_value = dimensions
                ConsoleUI(curses).main_menu()
                drawn = [call.args[2] for call in screen.addnstr.call_args_list]
                self.assertEqual(drawn[:len(BOXED)], list(BOXED))
                self.assertIn("> Start a new run", drawn)
        curses, screen = self.curses([27])
        screen.getmaxyx.return_value = (12, 40)
        curses.has_colors.return_value = False
        ConsoleUI(curses).main_menu()
        drawn = [call.args[2] for call in screen.addnstr.call_args_list]
        self.assertIn("TauFW V0.0", drawn)
        self.assertIn("Welcome to TauFW!", drawn)
        self.assertIn("> Start a new run", drawn)
        self.assertFalse(any(line.startswith("****") for line in drawn))

    def test_interaction_colors_preserve_banner_text_and_logo(self):
        from TauFW.Utilities.Menu.banner import FULL, INTERACTIONS
        self.assertTrue(all(line.isascii() for line in FULL))
        for enabled in (True, False):
            with self.subTest(colors=enabled):
                curses, screen = self.curses([])
                screen.getmaxyx.return_value = (34, 80)
                curses.COLOR_MAGENTA, curses.COLOR_YELLOW, curses.A_BOLD = 5, 3, 128
                ui = ConsoleUI(curses)
                with mock.patch.object(ui, "colors_enabled", return_value=enabled):
                    ui._entry_header(screen, "Welcome", 5)
                calls = screen.addnstr.call_args_list
                self.assertEqual([call.args[2] for call in calls[:len(FULL)]], list(FULL))
                overlays = calls[len(FULL):-1]
                if enabled:
                    self.assertEqual(len(overlays), len(INTERACTIONS))
                    styles = {}
                    for call, (row, column, text, role) in zip(overlays, INTERACTIONS):
                        self.assertEqual(call.args[:3], (row, column, text))
                        self.assertEqual(FULL[row][column:column + len(text)], text)
                        styles[role] = call.args[4]
                        if 7 <= row <= 11:
                            self.assertLessEqual(column + len(text), 26)
                    self.assertEqual(len(set(styles.values())), 4)
                else:
                    self.assertEqual(overlays, [])
                    curses.start_color.assert_not_called()

    def test_checklist_toggles_only_and_starts_from_button(self):
        curses, screen = self.curses([32, 10, 1002, 13, 1002, 10])
        ui = ConsoleUI(curses)
        with mock.patch.object(ui, "colors_enabled", return_value=True):  # not a terminal under Tests/run.py
            self.assertEqual(ui.setup_checklist([("first", "First"), ("second", "Second")], ["first"]),
                             ["first", "second"])
        curses.wrapper.assert_called_once()
        drawn = screen.addnstr.call_args_list
        self.assertTrue(any(call.args[2] == "[ Start install ]" for call in drawn))
        self.assertTrue(any(call.args[2] == "[x] First" and call.args[4] & 512 for call in drawn))
        self.assertTrue(any(call.args[2] == "[ ] Second" and call.args[4] & 1024 for call in drawn))

    def test_checklist_cancel_empty_selection_and_no_color(self):
        curses, screen = self.curses([27])
        curses.has_colors.return_value = False
        ui = ConsoleUI(curses)
        self.assertIsNone(ui.setup_checklist([("first", "First")], ["first"]))
        curses.start_color.assert_not_called()
        screen.getch.side_effect = [32, 1002, 32]
        self.assertEqual(ui.setup_checklist([("first", "First")], ["first"]), [])
        # A color-capable terminal can still reject initialization.
        curses.has_colors.return_value = True
        curses.start_color.side_effect = RuntimeError("no colors")
        screen.getch.side_effect = [1002, 10]
        self.assertEqual(ui.setup_checklist([("first", "First")], ["first"]), ["first"])

    def test_checklist_can_share_an_existing_terminal_session(self):
        curses, screen = self.curses([1002, 10])
        self.assertEqual(ConsoleUI(curses).setup_checklist(
            [("first", "First")], ["first"], screen=screen), ["first"])
        curses.wrapper.assert_not_called()

    def test_setup_launcher_writes_selection_only_after_start(self):
        from TauFW.Utilities.Menu import setup_menu
        ui = mock.Mock()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "selection"
            with mock.patch.object(ConsoleUI, "open", return_value=ui):
                ui.setup_checklist.return_value = None
                self.assertEqual(setup_menu.main(["--output", str(output)]), 130)
                self.assertFalse(output.exists())
                ui.setup_checklist.return_value = ["combine", "run2-jme"]
                self.assertEqual(setup_menu.main(["--output", str(output), "--selected", "combine"]), 0)
                self.assertEqual(output.read_text(), "combine\nrun2-jme\n")
                ui.setup_checklist.side_effect = KeyboardInterrupt
                output.unlink()
                self.assertEqual(setup_menu.main(["--output", str(output)]), 130)
                self.assertFalse(output.exists())

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
            mock.call("start", recipe=str(Path("recipes/example.yml"))),
            mock.call("advance", run_dir="runs/example", wait=True, poll=30),
        ])
        operations.load_run.assert_called_once_with("runs/example")
        operations.can_advance.assert_called_once_with(record)
        self.assertEqual(operations.validate_poll.call_args_list, [mock.call("bad"), mock.call("30")])
        ui.invalid_poll_interval.assert_called_once()
        operations.prepare_review.assert_called_once_with(str(Path("recipes/example.yml")))
        self.assertEqual(ui.pause.call_count, 2)

    def test_semantic_screen_actions_and_cancellation(self):
        ui = ConsoleUI(mock.Mock())
        cases = [
            (ui.main_menu, (), ["start", "continue", "inspect", "tests", "help", "exit"]),
            (ui.tests_menu, (), ["all", "checks", "normal", "bbb", "environment", "back"]),
            (ui.test_family, ("Normal",), ["all", "choose", "back"]),
            (ui.confirm_recipe, ("example.yml",), ["start", "plan", "back"]),
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
        self.assertTrue(any("An analysis is a" in line for line in drawn))

    def rendered_terminal(self, keys, dimensions=(24, 100)):
        """Capture terminal cells, including clipping and frame boundaries."""
        curses, screen = self.curses(keys)
        screen.getmaxyx.return_value = dimensions
        cells, frames = {}, []

        def add(y, x, value, count, style):
            height, width = screen.getmaxyx()
            self.assertTrue(0 <= y < height - 1 and 0 <= x < width - 1)
            self.assertLessEqual(x + min(len(value), count), width - 1)
            for offset, character in enumerate(value[:count]):
                cells[y, x + offset] = character

        def refresh():
            height, width = screen.getmaxyx()
            frames.append(["".join(cells.get((y, x), " ") for x in range(width))
                           for y in range(height)])

        screen.erase.side_effect = cells.clear
        screen.addnstr.side_effect = add
        screen.refresh.side_effect = refresh
        return ConsoleUI(curses), screen, frames

    def test_picker_equal_columns_and_vertical_cards_at_supported_sizes(self):
        for dimensions in ((12, 64), (24, 80), (36, 121)):
            with self.subTest(dimensions=dimensions):
                ui, screen, frames = self.rendered_terminal([27], dimensions)
                preview = dict(name="example", stages=(("production", "production", ""),
                                                       ("plots", "plots", "")))
                self.assertEqual(ui.select_recipe(["example"], lambda index: preview), ("back", None))
                width = dimensions[1]
                panel_width = (width - 1) // 2
                left = (width - (2 * panel_width - 1)) // 2
                divider = left + panel_width - 1
                for row in range(4, dimensions[0] - 4):
                    self.assertEqual(frames[0][row][left], "|")
                    self.assertEqual(frames[0][row][divider], "|")
                    self.assertEqual(frames[0][row][left + 2 * panel_width - 2], "|")
                self.assertIn("Recipe: example", "\n".join(frames[0]))
                self.assertIn("1. production", "\n".join(frames[0]))
                if dimensions[0] >= 24:
                    self.assertIn("2. plots", "\n".join(frames[0]))
                    self.assertIn("v", [line.strip() for line in ui._pipeline_lines(preview, 30)])

    def test_picker_updates_errors_and_special_row_hints(self):
        ui, screen, frames = self.rendered_terminal([1002, 1002, 1002, 27])
        preview = mock.Mock(side_effect=[dict(name="good", stages=(("plots", "plots", ""),)),
                                         dict(name="bad", error="invalid recipe")])
        self.assertEqual(ui.select_recipe(["good", "bad"], preview), ("back", None))
        self.assertEqual(preview.call_args_list, [mock.call(0), mock.call(1)])
        self.assertIn("Cannot preview: invalid recipe", "\n".join(frames[1]))
        self.assertIn("Enter a recipe file", "\n".join(frames[2]))
        self.assertIn("Return to the main menu.", "\n".join(frames[3]))

    def test_pipeline_scroll_wrap_and_reset_on_recipe_change(self):
        ui, screen, frames = self.rendered_terminal([1004] * 12 + [1002, 27], (18, 64))
        long_id = "very_long_custom_python_stage_identifier"
        stages = (("production", "production", ""), (long_id, "python", ""), ("fit", "fit", ""))
        view = dict(name="first", stages=stages)
        other = dict(name="second", stages=(("plots", "plots", ""),))
        ui.select_recipe(["first", "second"], lambda index: (view, other)[index])
        text = "\n".join(line for frame in frames for line in frame)
        self.assertIn("Python step", text)
        self.assertIn("3. fit", text)
        self.assertIn("Recipe: second", "\n".join(frames[-1]))
        wrapped = ui._pipeline_lines(view, 20)
        self.assertTrue(all(len(line) <= 20 for line in wrapped))
        self.assertIn(long_id, "".join(line[2:-2].strip() for line in wrapped if line.startswith("| ")))

    def test_resize_message_ignores_selection_and_preserves_focus(self):
        ui, screen, frames = self.rendered_terminal([], (24, 80))
        events = iter(((1002, (11, 63)), (10, (24, 80)), (10, (24, 80))))

        def key():
            value, dimensions = next(events)
            screen.getmaxyx.return_value = dimensions
            return value

        screen.getch.side_effect = key
        preview = mock.Mock(return_value=dict(name="recipe", stages=(("fit", "fit", ""),)))
        self.assertEqual(ui.select_recipe(["first", "second"], preview), ("select", 1))
        self.assertIn("Enlarge terminal", "\n".join(frames[1]))
        self.assertEqual(preview.call_args_list, [mock.call(0), mock.call(1)])
        self.assertIn("> second", "\n".join(frames[2]))

    def test_review_preserves_position_after_detailed_plan(self):
        ui, screen, frames = self.rendered_terminal([1004, 1002, 10], (18, 80))
        review = dict(name="analysis", path="Analyses/analysis", stages=(("fit", "fit", ""),),
                      notes=("fit: environment is not ready",))
        position = {}
        self.assertEqual(ui.confirm_recipe("analysis", review, position), "plan")
        self.assertEqual(position["selected"], 1)
        self.assertGreater(position["offset"], 0)
        screen.getch.side_effect = [1002, 10]
        self.assertEqual(ui.confirm_recipe("analysis", review, position), "back")
        text = "\n".join(line for frame in frames for line in frame)
        self.assertIn("Path: Analyses/analysis", text)
        self.assertIn("Planning notes:", text)

    def test_picker_preview_cache_and_exception_recovery(self):
        ui, operations = mock.Mock(), mock.Mock()
        operations.recipes.return_value = [Path("good.yml"), Path("bad.yml"), Path("wrong.yml")]
        operations.recipe_preview.side_effect = [dict(name="good"), ValueError("bad recipe"),
                                                 dict(name="wrong", problems=("stages[0] (fit): missing 'id'",))]

        def select(names, preview, broken):
            self.assertEqual(preview(0), preview(0))
            self.assertEqual(preview(1), preview(1))
            self.assertEqual(preview(1)["error"], "bad recipe")
            self.assertEqual(broken, [False, True, True])  # every recipe is checked first, to mark it in the list
            return "back", None

        ui.select_recipe.side_effect = select
        MenuNavigation(ui, operations).start()
        self.assertEqual(operations.recipe_preview.call_count, 3)
        operations.prepare_review.assert_not_called()
        operations.execute.assert_not_called()

    def test_problems_and_descriptions_in_the_pipeline(self):
        ui = ConsoleUI(mock.Mock())
        view = dict(name="broken", stages=(("prod", "production", "mutau tuples"), ("summary", "python", "")),
                    problems=("pico.config: file not found: x.json", "stages[2] (fit): missing 'id'"))
        lines = ui._pipeline_lines(view, 40)
        text = "\n".join(lines)
        self.assertIn("2 problem(s):", text)
        self.assertIn("- pico.config: file not found: x.json", text)
        self.assertLess(text.index("problem(s)"), text.index("1. prod"))  # the problems come first
        cards = [line[2:-2].strip() for line in lines if line.startswith(" ") and "|" in line]
        self.assertIn("production", " ".join(cards))  # the stage type under the id
        self.assertIn("mutau tuples", " ".join(cards))
        self.assertIn("Python step", " ".join(cards))

    def test_broken_recipes_are_red_in_the_list(self):
        ui = ConsoleUI(mock.Mock())
        with mock.patch.object(ui, "_pipeline_choice", return_value=None) as choice:
            self.assertEqual(ui.select_recipe(["a", "b"], lambda i: {}, broken=[False, True]), ("back", None))
        self.assertEqual(choice.call_args.kwargs["row_colors"], [None, "error", None, None])

    def test_framed_screens_without_color_and_with_color_failure(self):
        for fail in (False, True):
            with self.subTest(color_failure=fail):
                ui, screen, frames = self.rendered_terminal([27])
                if fail:
                    ui.curses.start_color.side_effect = ui.curses.error("unsupported")
                else:
                    ui.curses.has_colors.return_value = False
                with mock.patch.object(ui, "colors_enabled", return_value=True):
                    ui.choose("Menu", ["First", "Second"])
                self.assertIn(" Menu ", "\n".join(frames[0]))
                self.assertIn("> First", "\n".join(frames[0]))
                self.assertEqual(set(ui.styles.values()), {0})

    def test_run_status_columns_and_roles_include_long_unreadable_names(self):
        ui = ConsoleUI(mock.Mock())
        summaries = [("short", "DONE", "today"), ("a" * 50, None, None),
                     ("failed", "FAILED", "today"), ("waiting", "WAITING", "today")]
        with mock.patch.object(ui, "choose", return_value=None) as choose:
            self.assertEqual(ui.select_run(summaries), ("back", None))
        labels = choose.call_args.args[1][:4]
        self.assertEqual(len({label.index("|") for label in labels}), 1)
        self.assertIn("... | UNREADABLE", labels[1])
        self.assertEqual(choose.call_args.kwargs["row_colors"][:4],
                         ["good", "error", "error", "waiting"])


if __name__ == "__main__":
    unittest.main()
