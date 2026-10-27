"""Menu screens without a real terminal or Framework imports."""
import contextlib
import io
import itertools
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import checkout
from TauFW.Utilities.Menu import ConsoleUI, MenuNavigation, Prefetch


def idle_operations():
    """Mock operations with nothing behind the menu: no test run, no run, nothing running; no lock, no grid
    proxy needed."""
    operations = mock.Mock()
    operations.tests_operation.return_value = None
    operations.running_operations.return_value = []
    operations.run_operations.return_value = []
    operations.run_operation.return_value = None
    operations.run_advances.side_effect = lambda run_dirs: [None] * len(run_dirs)
    operations.run_lock.return_value = None
    operations.needs_grid_proxy.return_value = False
    operations.run_directories.return_value = []
    operations.kept_recipe_preview.side_effect = lambda path: operations.recipe_preview(path)  # read at once
    operations.kept_run_row.side_effect = lambda run_dir: operations.run_row(run_dir)
    return operations


class FakeOperation:
    """A test run behind the menu (TauFW.Utilities.Process.Operation stand-in) with its events in a file; each
    one is an operation of its own (path: the menus keep what they read per path)."""
    kind = "tests"
    numbers = itertools.count()

    def __init__(self, directory, state="RUNNING", events="", expected=("a", "b"), remote=False):
        self.path = str(Path(directory) / ("tests-%d" % next(self.numbers)))
        self.events_path = str(Path(directory) / "events.jsonl")
        Path(self.events_path).write_text(events)
        self._state = state
        self.title = "Normal tests"
        self.data = dict(expected=list(expected))
        self.host = "lxplus812.cern.ch"
        self.remote = remote

    def state(self):
        return self._state

    @property
    def running(self):
        return self._state in ("RUNNING", "STOPPING")

    def elapsed(self):
        return 75.0


class ScreenTests(unittest.TestCase):
    """Exercise actual screen key handling and wrapper lifetime with a fake terminal."""
    def test_install_returns_to_the_same_menu_without_an_extra_prompt(self):
        for outcome in (0, 130, ValueError("installer failed")):
            with self.subTest(outcome=outcome):
                keys = [1002] * 5 + [10] + ([10] if isinstance(outcome, Exception) else []) + [27]
                curses, screen = self.curses(keys)
                ui, operations = ConsoleUI(curses), idle_operations()
                if isinstance(outcome, Exception):
                    operations.install_components.side_effect = outcome
                else:
                    operations.install_components.return_value = outcome
                with mock.patch("builtins.input") as enter:
                    self.assertEqual(ui.session(MenuNavigation(ui, operations).run), 0)
                operations.install_components.assert_called_once_with()
                enter.assert_not_called()
                curses.wrapper.assert_called_once()
                curses.endwin.assert_called_once()
                curses.reset_prog_mode.assert_called_once()
                self.assertIn("> Install components", [call.args[2] for call in screen.addnstr.call_args_list])

    def test_user_config_action_passes_the_active_file_and_validator_to_the_editor(self):
        ui, operations = mock.Mock(), idle_operations()
        ui.main_menu.side_effect = ["user_config", "exit"]
        operations.user_config_path.return_value = "/work/personal.yaml"
        self.assertEqual(MenuNavigation(ui, operations).run(), 0)
        ui.edit_file.assert_called_once_with("/work/personal.yaml", operations.validate_user_config)
        ui.operation_error.assert_not_called()

    def test_editor_failures_stay_in_the_menu_and_do_not_reopen_the_session(self):
        from TauFW.Utilities.Editor import EditResult

        class CursesError(Exception):
            pass

        for outcome in (EditResult(error="broken editor"), RuntimeError("editor draw failed"),
                        CursesError("editor terminal failed")):
            with self.subTest(outcome=outcome):
                curses, screen = self.curses([1002] * 4 + [10, 10, 27])
                curses.error = CursesError
                ui, operations = ConsoleUI(curses), idle_operations()
                with mock.patch("TauFW.Utilities.Editor.edit_file") as editor:
                    if isinstance(outcome, Exception):
                        editor.side_effect = outcome
                    else:
                        editor.return_value = outcome
                    self.assertEqual(ui.session(MenuNavigation(ui, operations).run), 0)
                curses.wrapper.assert_called_once()
                editor.assert_called_once()
                drawn = [call.args[2] for call in screen.addnstr.call_args_list]
                self.assertIn(" Error ", drawn)
                self.assertTrue(any("Editor:" in line for line in drawn))

    def test_editor_import_failure_is_local_to_the_action(self):
        import builtins
        original = builtins.__import__

        def unavailable(name, *args, **kwargs):
            if name == "Editor":
                raise ImportError("Editor unavailable")
            return original(name, *args, **kwargs)

        curses, _ = self.curses([27])
        ui = ConsoleUI(curses)
        with mock.patch("builtins.__import__", side_effect=unavailable):
            self.assertEqual(ui.main_menu(), "exit")  # opening the menu does not import Editor
            with self.assertRaisesRegex(RuntimeError, "Editor unavailable"):
                ui.edit_file("unused")

    def test_editor_receives_existing_branding_and_styles_without_owning_the_palette(self):
        from TauFW.Utilities.Editor import EditResult
        from TauFW.Utilities.Menu.banner import BADGE, VERSION
        for color in (False, True):
            with self.subTest(color=color):
                curses, screen = self.curses([])
                screen.getmaxyx.return_value = (50, 100)
                curses.A_DIM, curses.COLOR_MAGENTA, curses.COLOR_YELLOW = 64, 5, 3
                ui = ConsoleUI(curses)
                with mock.patch.object(ui, "colors_enabled", return_value=color), \
                        mock.patch("TauFW.Utilities.Editor.edit_file", return_value=EditResult()) as editor:
                    self.assertFalse(ui.edit_file("personal.yaml"))
                appearance = editor.call_args.kwargs["appearance"]
                self.assertEqual(appearance["banner"], BADGE)
                self.assertNotIn("large_banner", appearance)
                self.assertIn((2, 2, VERSION, "version"), appearance["banner_spans"])
                for role in ("accent", "brand", "version", "good", "warning", "error"):
                    self.assertEqual(appearance["styles"][role], ui.styles[role])
                self.assertEqual(bool(appearance["styles"]["accent"]), color)
                self.assertIsNot(appearance["styles"], ui.styles)

    def test_grid_certificate_status_label_and_color(self):
        ui = ConsoleUI(mock.Mock())
        for valid, label, role in ((True, "Grid Certificate  \u2713", "good"),
                                   (False, "Grid Certificate  Warning: Proxy Failed!", "warning")):
            with self.subTest(valid=valid), mock.patch.object(ui, "choose", return_value=3) as choose:
                self.assertEqual(ui.main_menu(proxy_valid=valid), "grid_certificate")
                self.assertEqual(choose.call_args.args[1][3], label)
                self.assertEqual(choose.call_args.kwargs["row_colors"][3], role)

    def test_grid_certificate_asks_the_password_in_a_panel_and_refreshes_after_renewal(self):
        """The password from the panel goes to renew_grid_proxy; a voms-proxy-init without -pwstdin (None) asks
        on the plain terminal; the result is a panel, an error too; the next main menu asks again."""
        for outcome in ((True, "Done"), (False, "wrong pass phrase"), (None, "Unknown option -pwstdin"),
                        KeyboardInterrupt(), RuntimeError("VOMS unavailable")):
            with self.subTest(outcome=outcome):
                ui, operations = mock.Mock(), idle_operations()
                ui.main_menu.side_effect = ["grid_certificate", "exit"]
                ui.grid_password.return_value = "secret"
                ui.in_terminal.return_value = 0
                valid = outcome[0] is not False if isinstance(outcome, tuple) else False
                operations.grid_proxy_valid.side_effect = [False, valid]
                if isinstance(outcome, BaseException):
                    operations.renew_grid_proxy.side_effect = outcome
                else:
                    operations.renew_grid_proxy.return_value = outcome
                self.assertEqual(MenuNavigation(ui, operations).run(), 0)
                self.assertEqual(ui.main_menu.call_args_list,
                                 [mock.call(proxy_valid=False, tests=None, runs=[], live=False),
                                  mock.call(proxy_valid=valid, tests=None, runs=[], live=False)])
                operations.renew_grid_proxy.assert_called_once_with("secret")
                ui.notice.assert_called_once()  # "Renewing..." while voms-proxy-init works
                if isinstance(outcome, tuple) and outcome[0] is None:
                    ui.in_terminal.assert_called_once_with(operations.renew_grid_proxy_in_terminal)
                    ui.grid_result.assert_called_once_with(True, "")
                elif isinstance(outcome, tuple):
                    ui.in_terminal.assert_not_called()
                    ui.grid_result.assert_called_once_with(*outcome)
                else:
                    ui.grid_result.assert_not_called()
                self.assertEqual(ui.operation_error.called, isinstance(outcome, RuntimeError))
        ui, operations = mock.Mock(), idle_operations()
        ui.main_menu.side_effect = ["grid_certificate", "exit"]
        ui.grid_password.return_value = None  # Esc in the panel
        self.assertEqual(MenuNavigation(ui, operations).run(), 0)
        operations.renew_grid_proxy.assert_not_called()
        ui.grid_result.assert_not_called()
        ui, operations = mock.Mock(), idle_operations()
        ui.main_menu.return_value = "exit"
        self.assertEqual(MenuNavigation(ui, operations).run(), 0)
        operations.grid_proxy_valid.assert_called_once_with()
        operations.renew_grid_proxy.assert_not_called()

    def test_the_main_menu_is_live_while_something_runs_behind_it(self):
        ui, operations = mock.Mock(), idle_operations()
        running, ended = mock.Mock(running=True), mock.Mock(running=False)
        operations.tests_operation.side_effect = [running, running, ended]
        ui.main_menu.side_effect = ["refresh", "refresh", "exit"]
        self.assertEqual(MenuNavigation(ui, operations).run(), 0)
        self.assertEqual([call.kwargs["live"] for call in ui.main_menu.call_args_list], [True, True, False])
        self.assertEqual(operations.tests_operation.call_count, 3)  # each draw asks again
        curses, screen = self.curses([1002, -1, 1002, -1, 10])
        ui = ConsoleUI(curses)
        tests = mock.Mock(kind="command", state=mock.Mock(return_value="RUNNING"))
        self.assertEqual(ui.main_menu(live=True), "refresh")  # no key in LIVE_EVERY s: draw it again
        screen.timeout.assert_called_with(2000)
        self.assertEqual(ui.main_menu(live=True, tests=tests), "refresh")
        self.assertEqual(ui.main_menu(), "inspect")  # the selected line stayed through the redraws
        curses, screen = self.curses([-1, 10])
        self.assertEqual(ConsoleUI(curses).main_menu(), "start")  # not live: no key is no answer

    def test_rows_still_read_say_so_and_the_list_draws_again(self):
        curses, screen = self.curses([1002, -1, 10])
        ui = ConsoleUI(curses)
        screen.getmaxyx.return_value = (24, 90)
        position = {}
        self.assertEqual(ui.select_recipe(["a", "b"], lambda i: dict(name="b", hint="Checking the recipe..."),
                                          broken=[False, False], checking=[False, True], position=position,
                                          live=True), ("refresh", None))
        screen.timeout.assert_called_with(500)
        drawn = [call.args[2] for call in screen.addnstr.call_args_list]
        self.assertTrue(any(line.startswith("> b  checking...") for line in drawn))
        self.assertEqual(ui.select_recipe(["a", "b"], lambda i: dict(name="b"), position=position), ("select", 1))
        curses, screen = self.curses([-1, 27])
        ui = ConsoleUI(curses)
        self.assertEqual(ui.select_run([("a_1", "DONE", "today"), ("b_2", None, None)], loading=[False, True],
                                       live=True), ("refresh", None))
        drawn = [call.args[2] for call in screen.addnstr.call_args_list]
        self.assertTrue(any("b_2 | loading..." in line for line in drawn))
        self.assertFalse(any("UNREADABLE" in line for line in drawn))
        self.assertEqual(ui.select_run([("a_1", "DONE", "today")]), ("back", None))

    def test_prefetch_runs_each_key_once_and_in_order(self):
        done = []
        prefetch = Prefetch(threaded=False)
        prefetch.add("a", lambda: done.append("a") or prefetch.add("b", lambda: done.append("b")))
        prefetch.add("c", lambda: 1 / 0)  # an error is dropped
        self.assertEqual(done, ["a", "b"])
        self.assertFalse(prefetch.busy("c"))
        import threading
        gate, prefetch = threading.Event(), Prefetch()
        prefetch.add("slow", gate.wait)
        prefetch.add("slow", lambda: done.append("again"))  # queued or running: not again
        prefetch.add("next", lambda: done.append("next"))
        self.assertTrue(prefetch.busy("slow"))
        gate.set()
        self.assertTrue(prefetch.wait(10))
        self.assertEqual(done, ["a", "b", "next"])

    def test_one_session_for_every_screen_and_errors_in_a_panel(self):
        curses, screen = self.curses([10, 27, 10])
        ui = ConsoleUI(curses)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            result = ui.session(lambda: (ui.choose("A", ["x", "y"]), ui.choose("B", ["x"]),
                                         ui.operation_error(RuntimeError("Tests are already running"))))
        self.assertEqual(result, (0, None, None))
        curses.wrapper.assert_called_once()  # one curses session for all screens
        self.assertIsNone(ui.screen)
        self.assertEqual(output.getvalue(), "")  # nothing printed over the screen
        drawn = [call.args[2] for call in screen.addnstr.call_args_list]
        self.assertIn(" Error ", drawn)
        self.assertIn("RuntimeError: Tests are already running", drawn)
        self.assertIn("Enter OK", drawn)
        curses, screen = self.curses([ord("x"), 1002, 27])
        ConsoleUI(curses).unreadable_run(OSError("no run.json"))  # outside a session: its own
        drawn = [call.args[2] for call in screen.addnstr.call_args_list]
        self.assertIn(" Cannot read run ", drawn)
        self.assertEqual(screen.getch.call_count, 3)  # x and Down do not close it

    def test_the_grid_password_panel_shows_stars_and_the_result(self):
        curses, screen = self.curses([])
        screen.get_wch.side_effect = list("pw") + ["\x7f", "x", "\n"]
        ui = ConsoleUI(curses)
        self.assertEqual(ui.grid_password(), "px")
        drawn = [call.args[2] for call in screen.addnstr.call_args_list]
        self.assertIn("Certificate password: **", drawn)
        self.assertFalse(any("pw" in line or "px" in line for line in drawn))  # never shown
        for keys in (["\x1b"], ["\n"], [KeyboardInterrupt()]):  # Esc, Enter on nothing, Ctrl-C
            screen.get_wch.side_effect = keys
            self.assertIsNone(ui.grid_password())
        curses, screen = self.curses([10, 10])
        screen.getmaxyx.return_value = (30, 100)  # the whole result (a small terminal scrolls it)
        ui = ConsoleUI(curses)
        ui.grid_result(True)
        ui.grid_result(False, "line 1\nError: wrong pass phrase\n")
        drawn = [call.args[2] for call in screen.addnstr.call_args_list]
        self.assertIn("Grid proxy active.", drawn)
        self.assertTrue(any(line.startswith("Proxy Failed!") for line in drawn))
        self.assertIn("Error: wrong pass phrase", drawn)

    def test_in_terminal_leaves_the_screen_and_comes_back(self):
        curses, screen = self.curses([])
        ui = ConsoleUI(curses)
        self.assertEqual(ui.in_terminal(lambda: 3), 3)  # outside a session: just runs
        curses.endwin.assert_not_called()
        with mock.patch("builtins.input", return_value="") as enter:
            self.assertEqual(ui.session(lambda: ui.in_terminal(lambda: 7)), 7)
        enter.assert_called_once()
        curses.def_prog_mode.assert_called_once_with()
        curses.endwin.assert_called_once_with()
        curses.reset_prog_mode.assert_called_once_with()
        screen.refresh.assert_called()

    def curses(self, keys):
        screen = mock.Mock()
        screen.getmaxyx.return_value = (12, 65)
        screen.getch.side_effect = keys
        curses = mock.Mock()
        curses.error = RuntimeError
        curses.A_REVERSE, curses.A_BOLD, curses.COLORS = 256, 128, 8
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

    def test_testing_navigation_selection_review_and_the_test_screen(self):
        item = dict(id="example", description="Local example", dependencies=[])
        for outcome in (0, 1, KeyboardInterrupt(), RuntimeError("screen failed")):
            with self.subTest(outcome=outcome):
                ui, operations = mock.Mock(), idle_operations()
                ui.main_menu.side_effect = ["tests", "exit"]
                ui.tests_menu.side_effect = ["normal", "back"]
                ui.test_family.return_value = "choose"
                ui.test_selection.side_effect = [["example"], ["example"]]
                operations.test_catalog.return_value = {"normal": [item]}
                if isinstance(outcome, BaseException):
                    ui.test_run.side_effect = outcome
                else:
                    ui.test_run.return_value = outcome
                process = operations.start_tests.return_value
                process.configure_mock(title="Normal tests", data={"expected": ["example"]}, running=False)
                self.assertEqual(MenuNavigation(ui, operations).run(), 0)
                operations.start_tests.assert_called_once_with("normal", ["example"], "Normal tests", ["example"])
                ui.test_run.assert_called_once_with("Normal tests", process, ["example"])
                process.cancel.assert_not_called()  # the screen never stops a run
                self.assertEqual(ui.test_selection.call_args_list[-1],
                                 mock.call("Review / Normal tests", [item], review=True))
                self.assertEqual(ui.operation_error.call_count, 1 if isinstance(outcome, RuntimeError) else 0)
        ui, operations = mock.Mock(), idle_operations()
        ui.tests_menu.side_effect = ["normal", "back"]
        ui.test_family.return_value = "all"
        ui.test_selection.return_value = ["example"]
        operations.test_catalog.return_value = {"normal": [item]}
        operations.start_tests.side_effect = RuntimeError("Cannot find Tests/run.py")
        MenuNavigation(ui, operations).tests()
        ui.test_run.assert_not_called()
        ui.operation_error.assert_called_once()

    def test_testing_back_empty_selection_and_catalog_failure_do_not_execute(self):
        item = dict(id="example", description="Local example", dependencies=[])
        for action, selection in (("back", None), ("choose", []), ("all", None)):
            ui, operations = mock.Mock(), idle_operations()
            ui.tests_menu.side_effect = ["normal", "back"]
            ui.test_family.return_value = action
            ui.test_selection.return_value = selection
            operations.test_catalog.return_value = {"normal": [item]}
            MenuNavigation(ui, operations).tests()
            operations.start_tests.assert_not_called()
        ui, operations = mock.Mock(), idle_operations()
        ui.tests_menu.side_effect = ["all", "back"]
        operations.test_catalog.side_effect = RuntimeError("Cannot load test choices")
        MenuNavigation(ui, operations).tests()
        operations.start_tests.assert_not_called()
        ui.operation_error.assert_called_once()

    def test_a_running_test_run_opens_its_screen_and_stays_behind_the_menu(self):
        with tempfile.TemporaryDirectory() as directory:
            running = FakeOperation(directory)
            ui, operations = mock.Mock(), idle_operations()
            operations.tests_operation.return_value = running
            ui.main_menu.side_effect = ["tests", "exit"]
            ui.quit_running.return_value = "quit"
            operations.running_operations.return_value = [running]
            self.assertEqual(MenuNavigation(ui, operations).run(), 0)
            ui.test_run.assert_called_once_with("Normal tests", running, ["a", "b"])
            ui.tests_menu.assert_not_called()  # one test run at a time: Tests is its screen
            operations.start_tests.assert_not_called()
            self.assertIs(ui.main_menu.call_args.kwargs["tests"], running)
            # it ended while its screen was open: the Tests menu follows, with the last run on top
            ended = FakeOperation(directory)
            ui, operations = mock.Mock(), idle_operations()
            operations.tests_operation.side_effect = [ended, ended, ended]
            ui.test_run.side_effect = lambda *args: setattr(ended, "_state", "FAILED")
            ui.tests_menu.side_effect = ["last", "back"]
            MenuNavigation(ui, operations).tests()
            self.assertEqual(ui.test_run.call_count, 2)  # its screen, then again from "Last run"
            self.assertEqual(ui.tests_menu.call_args_list, [mock.call(last=ended)] * 2)

    def test_quitting_with_operations_behind_the_menu(self):
        with tempfile.TemporaryDirectory() as directory:
            running = FakeOperation(directory)
            for choice, menus, stopped in (("cancel", 2, False), ("stop", 1, True), ("quit", 1, False)):
                with self.subTest(choice=choice):
                    ui, operations = mock.Mock(), idle_operations()
                    ui.main_menu.return_value = "exit"
                    ui.quit_running.side_effect = [choice, "quit"]
                    operations.running_operations.return_value = [running]
                    self.assertEqual(MenuNavigation(ui, operations).run(), 0)
                    self.assertEqual(ui.main_menu.call_count, menus)  # cancel: back to the main menu
                    ui.quit_running.assert_called_with([running])
                    self.assertEqual(operations.stop_operation.call_args_list,
                                     [mock.call(running)] if stopped else [])
            ui, operations = mock.Mock(), idle_operations()
            ui.main_menu.return_value = "exit"
            self.assertEqual(MenuNavigation(ui, operations).run(), 0)
            ui.quit_running.assert_not_called()  # nothing runs: no question

    def test_tests_label_last_run_and_quit_screen(self):
        events = "".join('{"kind": "case_end", "id": "%s", "status": "%s"}\n' % pair
                         for pair in (("a", "PASS"), ("b", "FAIL")))
        with tempfile.TemporaryDirectory() as directory:
            ui = ConsoleUI(mock.Mock())
            for state, text, role in (("RUNNING", "Running 2/2", "accent"), ("FAILED", "Failed: 1", "error"),
                                      ("DONE", "Done", "good"), ("STOPPING", "Stopping", "warning"),
                                      ("STOPPED", "Stopped", "warning"), ("LOST", "Lost", "warning")):
                operation = FakeOperation(directory, state, events)
                with self.subTest(state=state), mock.patch.object(ui, "choose", return_value=6) as choose:
                    self.assertEqual(ui.main_menu(tests=operation), "tests")
                    self.assertEqual(choose.call_args.args[1][6], "Tests (%s)" % text)
                    self.assertEqual(choose.call_args.kwargs["row_colors"][6], role)
            with mock.patch.object(ui, "choose", return_value=6) as choose:
                ui.main_menu()
                self.assertEqual((choose.call_args.args[1][6], choose.call_args.kwargs["row_colors"][6]),
                                 ("Tests", None))
            operation = FakeOperation(directory, "FAILED", events)
            with mock.patch.object(ui, "choose", side_effect=[0, 1]) as choose:
                self.assertEqual(ui.tests_menu(last=operation), "last")
                self.assertEqual(choose.call_args.args[1][0], "Last run: Normal tests (Failed: 1)")
                self.assertEqual(ui.tests_menu(), "checks")
            self.assertEqual(FakeOperation(directory, "RUNNING", "", expected=()).state(), "RUNNING")
            with mock.patch.object(ui, "choose", return_value=6) as choose:
                ui.main_menu(tests=FakeOperation(directory, "RUNNING", "", expected=()))
                self.assertEqual(choose.call_args.args[1][6], "Tests (Running)")  # no cases known yet
            remote = FakeOperation(directory, "RUNNING", events, remote=True)
            for keys, choice in (([ord("x"), ord("q")], "quit"), ([ord("S")], "stop"), ([27], "cancel"),
                                 ([10], "cancel"), ([KeyboardInterrupt()], "cancel")):
                curses, screen = self.curses(keys)
                screen.getmaxyx.return_value = (30, 100)  # the whole warning in the panel
                self.assertEqual(ConsoleUI(curses).quit_running([remote]), choice)
            drawn = [call.args[2] for call in screen.addnstr.call_args_list]
            self.assertIn(" Still running: quit TauFW? ", drawn)  # a panel over the main menu
            self.assertIn("Normal tests: Running 2/2  01:15 on lxplus812.cern.ch", drawn)
            self.assertIn("C Cancel (stay) | S Stop all and quit | Q Quit anyway", drawn)
            self.assertTrue(any("closing the SSH" in line for line in drawn))

    def test_a_menu_line_reads_only_the_new_events_and_none_once_ended(self):
        event = '{"kind": "case_end", "id": "%s", "status": "%s"}\n'
        with tempfile.TemporaryDirectory() as directory:
            ui, operation = ConsoleUI(mock.Mock()), FakeOperation(directory, "RUNNING", event % ("a", "PASS"))

            def label():
                with mock.patch.object(ui, "choose", return_value=6) as choose:
                    ui.main_menu(tests=operation)
                return choose.call_args.args[1][6]
            self.assertEqual(label(), "Tests (Running 1/2)")
            reader = ui._summaries[operation.path]["events"]
            with open(operation.events_path, "a") as stream:
                stream.write(event % ("b", "FAIL"))
            self.assertEqual(label(), "Tests (Running 2/2)")
            self.assertIs(ui._summaries[operation.path]["events"], reader)  # the same reader: the new line only
            operation._state = "FAILED"
            self.assertEqual(label(), "Tests (Failed: 1)")
            with mock.patch.object(reader, "read") as read:
                self.assertEqual(label(), "Tests (Failed: 1)")
            read.assert_not_called()  # ended: its events are not read again

    def test_all_and_environment_review_before_running(self):
        for family in ("all", "environment"):
            ui, operations = mock.Mock(), idle_operations()
            ui.tests_menu.side_effect = [family, "back"]
            operations.test_catalog.return_value = {
                name: [dict(id=name, description=name, dependencies=[])]
                for name in ("checks", "normal", "bbb")}
            ui.test_selection.return_value = ["reviewed"]
            operations.start_tests.return_value.configure_mock(data={"expected": []}, running=False)
            MenuNavigation(ui, operations).tests()
            expected = [[name, name] for name in ("checks", "normal", "bbb")] if family == "all" else []
            operations.start_tests.assert_called_once_with(family, [], mock.ANY, expected)  # all: the total at once
            ui.test_run.assert_called_once_with(mock.ANY, operations.start_tests.return_value, [])
            self.assertTrue(ui.test_selection.call_args.kwargs["review"])
            if family == "all":
                self.assertEqual([item["id"] for item in ui.test_selection.call_args.args[1]],
                                 ["checks", "normal", "bbb"])
            else:
                operations.test_catalog.assert_not_called()
            ui.operation_error.assert_not_called()

    def test_entry_banners_welcome_text_and_compact_layout(self):
        from TauFW.Utilities.Menu.banner import FULL
        for installer in (False, True):
            with self.subTest(installer=installer):
                curses, screen = self.curses([27])
                screen.getmaxyx.return_value = (43, 80)
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
                self.assertTrue(all(call.args[0] < 41 for call in calls[:-1]))
        from TauFW.Utilities.Menu.banner import BOXED
        for dimensions in ((31, 80), (32, 80), (32, 65)):
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

    def test_checklist_cancel_button_returns_without_starting(self):
        for keys in ([1002, 1002, 10], [1001, 32]):
            with self.subTest(keys=keys):
                curses, screen = self.curses(keys)
                self.assertIsNone(ConsoleUI(curses).setup_checklist([("first", "First")], ["first"]))
                self.assertIn("[ Cancel ]", [call.args[2] for call in screen.addnstr.call_args_list])

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

    def runs_menu(self, **lock):
        """Mocks for Continue on one WAITING run; lock: its advance lock (none without)."""
        ui, operations = mock.Mock(), idle_operations()
        operations.run_directories.return_value = ["runs/example"]
        operations.run_row.return_value = ("today", "runs/example", ("example", "WAITING", "today"))
        record = mock.Mock(run_id="example", run_dir="runs/example", state="WAITING")
        operations.load_run.return_value = record
        operations.can_advance.return_value = True
        operations.run_lock.return_value = dict(lock) if lock else None
        operations.advance_run.return_value = mock.Mock(running=False, data=dict(run_id="example"))
        ui.select_run.side_effect = [("select", 0), ("back", None)]
        ui.continue_actions.return_value = "wait"
        return ui, operations, record

    def test_navigation_uses_injected_operations(self):
        ui, operations, record = self.runs_menu()
        operations.recipes.return_value = [Path("recipes/example.yml")]
        started = mock.Mock(running=True, data=dict(run_id="example", run_dir=""))
        operations.start_run.return_value = started
        ui.main_menu.side_effect = ["start", "continue", "exit"]
        ui.select_recipe.return_value = ("select", 0)
        ui.confirm_recipe.return_value = "start"
        self.assertEqual(MenuNavigation(ui, operations).run(), 0)
        operations.start_run.assert_called_once_with(str(Path("recipes/example.yml")))
        operations.advance_run.assert_called_once_with(record, wait=True, take_lock=False)
        advanced = operations.advance_run.return_value
        self.assertEqual(ui.run_progress.call_args_list, [mock.call("Run example", started),
                                                          mock.call("Run example", advanced)])
        operations.mark_seen.assert_called_once_with(advanced)  # it ended; the started one still runs
        operations.start_command.assert_not_called()  # no plan or status was asked for
        self.assertEqual(ui.select_run.call_args.kwargs["advances"], [None])
        operations.load_run.assert_called_once_with("runs/example")
        operations.can_advance.assert_called_once_with(record)
        operations.prepare_review.assert_called_once_with(str(Path("recipes/example.yml")))
        ui.operation_error.assert_not_called()

    def test_plan_and_status_are_shown_on_the_command_screen(self):
        ui, operations, record = self.runs_menu()
        operations.recipes.return_value = [Path("recipes/example.yml")]
        operations.prepare_review.return_value = dict(name="example")
        ui.main_menu.side_effect = ["start", "inspect", "exit"]
        ui.select_recipe.side_effect = [("select", 0), ("back", None)]
        ui.confirm_recipe.side_effect = ["plan", "back"]
        ui.command_output.side_effect = ["back", "refresh", "refresh", "back"]
        self.assertEqual(MenuNavigation(ui, operations).run(), 0)
        path = str(Path("recipes/example.yml"))
        self.assertEqual(operations.start_command.call_args_list,
                         [mock.call("plan", path)] + [mock.call("status", "runs/example")] * 3)
        titles = [(call.args[0], call.kwargs) for call in ui.command_output.call_args_list]
        self.assertEqual(titles, [("Plan: example", dict(refresh=False))] +
                         [("Run status: example", dict(refresh=True))] * 3)  # R twice
        ui.operation_error.assert_not_called()
        operations.start_command.side_effect = OSError("AFS is not writable")  # the screen never opens
        MenuNavigation(ui, operations).inspect(record)
        ui.operation_error.assert_called_once()

    def test_continue_on_an_advancing_run_opens_its_screen(self):
        ui, operations, record = self.runs_menu()
        advancing = mock.Mock(running=True, data=dict(run_id="example"))
        operations.run_operation.return_value = advancing
        MenuNavigation(ui, operations).continue_run()
        ui.run_progress.assert_called_once_with("Run example", advancing)
        operations.advance_run.assert_not_called()
        ui.continue_actions.assert_not_called()
        operations.mark_seen.assert_not_called()

    def test_continue_once_and_the_run_lock(self):
        ui, operations, record = self.runs_menu()
        ui.continue_actions.return_value = "advance"
        MenuNavigation(ui, operations).continue_run()
        operations.advance_run.assert_called_once_with(record, wait=False, take_lock=False)
        live = dict(host="lxplus999", pid=1, since="14:02", quiet=10, lost=False, local=False)
        for lock, choice, take in ((live, "back", None), (dict(live, lost=True), "take", True),
                                   (dict(live, lost=True, local=True), None, False)):
            with self.subTest(lock=lock):
                ui, operations, record = self.runs_menu(**lock)
                ui.run_lock.return_value = choice
                MenuNavigation(ui, operations).continue_run()
                if choice is None:  # lost on this machine: the advance takes it over without asking
                    ui.run_lock.assert_not_called()
                else:
                    ui.run_lock.assert_called_once_with("example", lock)
                if take is None:
                    operations.advance_run.assert_not_called()
                else:
                    operations.advance_run.assert_called_once_with(record, wait=True, take_lock=take)

    def test_a_run_that_may_submit_needs_a_valid_grid_proxy(self):
        for answers, valid, started in ((["back"], [False], False), (["renew"], [False, True], True),
                                        (["renew", "back"], [False, False], False)):
            with self.subTest(answers=answers, valid=valid):
                ui, operations, record = self.runs_menu()
                operations.needs_grid_proxy.return_value = True
                operations.grid_proxy_valid.side_effect = valid
                ui.grid_proxy_needed.side_effect = answers
                ui.continue_actions.side_effect = ["wait", "back"]
                MenuNavigation(ui, operations).continue_run()
                operations.needs_grid_proxy.assert_called_with(record=record)
                self.assertEqual(operations.renew_grid_proxy.call_count, answers.count("renew"))
                self.assertEqual(operations.advance_run.called, started)
                self.assertTrue(all(call == mock.call(fresh=True)  # never a kept answer before a run
                                    for call in operations.grid_proxy_valid.call_args_list))

    def test_the_main_menu_run_line_follows_the_runs(self):
        ui, operations = mock.Mock(), idle_operations()
        one, two = (mock.Mock(running=True, data=dict(run_id=name)) for name in ("tes", "etau"))
        operations.run_operations.side_effect = [[one], [one], [one, two], [one, two], [one, two], [one, two]]
        ui.main_menu.side_effect = ["run", "runs", "exit"]
        ui.active_runs.side_effect = [("select", 1), ("back", None)]
        self.assertEqual(MenuNavigation(ui, operations).run(), 0)
        self.assertEqual(ui.main_menu.call_args_list[0].kwargs["runs"], [one])
        self.assertEqual(ui.run_progress.call_args_list, [mock.call("Run tes", one), mock.call("Run etau", two)])

    def test_semantic_screen_actions_and_cancellation(self):
        ui = ConsoleUI(mock.Mock())
        cases = [
            (ui.main_menu, (), ["start", "continue", "inspect", "grid_certificate", "user_config", "install",
                                "tests", "help", "exit"]),
            (ui.tests_menu, (), ["all", "checks", "normal", "bbb", "environment", "preview", "back"]),
            (ui.test_family, ("Normal",), ["all", "choose", "back"]),
            (ui.confirm_recipe, ("example.yml",), ["start", "plan", "back"]),
            (ui.terminal_run_actions, ("DONE",), ["inspect", "back"]),
            (ui.continue_actions, ("run",), ["wait", "advance", "back"]),
            (ui.grid_proxy_needed, (), ["renew", "back"]),
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
        self.assertEqual(prompt.call_args_list, [
            mock.call("Recipe path (relative to launch)"),
            mock.call("Run directory (relative to launch)"),
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
assert menu.__all__ == ['ConsoleUI', 'MenuNavigation', 'Prefetch']
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
                for given, delay in ((None, "25"), ("100", "100")):  # Esc answers at once; the user's delay is kept
                    with mock.patch.dict(os.environ, {} if given is None else {"ESCDELAY": given}):
                        if given is None:
                            os.environ.pop("ESCDELAY", None)
                        ui = ConsoleUI.open(mock.Mock())
                        self.assertEqual(os.environ["ESCDELAY"], delay)
                        with mock.patch.object(ui, "colors_enabled", return_value=False):
                            ui._setup(mock.Mock())
                        curses.set_escdelay.assert_called_with(int(delay))
                self.assertIs(ui.curses, curses)
                curses.setupterm.reset_mock()
                ConsoleUI.open(mock.Mock())
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
        self.assertNotIn("Python step", text)
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

    def test_start_lists_at_once_and_fills_in_the_checks_as_they_come(self):
        """A check that is not read yet: "checking..." and a live list, its job asked for once; the next draw
        shows it; the focus stays."""
        ui, operations = mock.Mock(), idle_operations()
        operations.recipes.return_value = [Path("a.yml"), Path("b.yml")]
        kept = {"a.yml": dict(name="a")}
        operations.kept_recipe_preview.side_effect = lambda path: kept.get(str(path))
        prefetch = mock.Mock()
        drawn = []

        def select(names, preview, broken, warnings, checking, position, live):
            drawn.append((list(checking), live, preview(1).get("hint"), dict(position)))
            if len(drawn) == 1:
                position["selected"] = 1
                kept["b.yml"] = dict(name="b", problems=("x",))  # the job of b came meanwhile
                return "refresh", None
            return "back", None
        ui.select_recipe.side_effect = select
        MenuNavigation(ui, operations, prefetch=prefetch).start()
        self.assertEqual(drawn, [([False, True], True, "Checking the recipe...", {}),
                                 ([False, False], False, None, {"selected": 1})])
        (key, job), = [call.args for call in prefetch.add.call_args_list]
        self.assertEqual(key, ("recipe", "b.yml"))
        job()
        operations.recipe_preview.assert_called_once_with(Path("b.yml"))

    def test_continue_lists_at_once_and_fills_in_the_runs_as_they_come(self):
        ui, operations = mock.Mock(), idle_operations()
        operations.run_directories.return_value = ["runs/a_1", "runs/b_2", "runs/c_3"]
        kept = {"runs/a_1": ("2026-10-01", "runs/a_1", ("a_1", "DONE", "today"))}
        operations.kept_run_row.side_effect = lambda run_dir: kept.get(run_dir)
        drawn = []

        def select(summaries, advances, loading, position, live):
            drawn.append((list(summaries), list(loading), live, dict(position)))
            if len(drawn) == 1:
                position["selected"] = 2  # runs/b_2 (loading, after the read ones)
                kept["runs/b_2"] = ("2026-10-02", "runs/b_2", ("b_2", "WAITING", "today"))
                kept["runs/c_3"] = ("2026-10-03", "runs/c_3", ("c_3", "FAILED", "today"))
                return "refresh", None
            return "back", None
        ui.select_run.side_effect = select
        self.assertIsNone(MenuNavigation(ui, operations, prefetch=mock.Mock()).continue_run())
        self.assertEqual(drawn[0][:3], ([("a_1", "DONE", "today"), ("c_3", None, None), ("b_2", None, None)],
                                        [False, True, True], True))
        self.assertEqual(drawn[1][:3], ([("c_3", "FAILED", "today"), ("b_2", "WAITING", "today"),
                                         ("a_1", "DONE", "today")], [False, False, False], False))
        self.assertEqual(drawn[1][3], {"selected": 1})  # b_2 stayed selected while the rows moved

    def test_a_running_run_that_no_advance_works_on_is_paused(self):
        dirs = ["runs/r"]
        for advance, lock, shown in ((mock.Mock(running=True), None, "RUNNING"),   # behind the menu now
                                     (None, dict(lost=False), "RUNNING"),          # from the CLI: a live lock
                                     (None, dict(lost=True), "PAUSED"),
                                     (mock.Mock(running=False), None, "PAUSED")):  # the advance stopped
            with self.subTest(shown=shown, lock=lock):
                ui, operations = mock.Mock(), idle_operations()
                operations.run_directories.return_value = dirs
                operations.run_row.return_value = ("today", dirs[0], ("r", "RUNNING", "today"))
                operations.run_advances.side_effect = lambda run_dirs: [advance]
                operations.run_lock.return_value = lock
                ui.select_run.return_value = ("back", None)
                MenuNavigation(ui, operations, prefetch=mock.Mock()).continue_run()
                self.assertEqual(ui.select_run.call_args.args[0], [("r", shown, "today")])
        operations.run_row.return_value = ("today", dirs[0], ("w", "WAITING", "today"))
        operations.run_lock.reset_mock()
        MenuNavigation(ui, operations, prefetch=mock.Mock()).continue_run()
        self.assertEqual(ui.select_run.call_args.args[0], [("w", "WAITING", "today")])  # only RUNNING changes
        operations.run_lock.assert_not_called()

    def test_the_menu_reads_the_lists_ahead(self):
        ui, operations = mock.Mock(), idle_operations()
        operations.recipes.return_value = [Path("a.yml")]
        operations.run_directories.return_value = ["runs/a_1"]
        ui.main_menu.side_effect = ["exit"]
        prefetch = Prefetch(threaded=True)
        MenuNavigation(ui, operations, prefetch=prefetch).run()
        self.assertTrue(prefetch.wait(10))
        operations.recipe_preview.assert_called_once_with(Path("a.yml"))
        operations.run_row.assert_called_once_with("runs/a_1")

    def test_picker_preview_cache_and_exception_recovery(self):
        ui, operations = mock.Mock(), idle_operations()
        operations.recipes.return_value = [Path("good.yml"), Path("bad.yml"), Path("wrong.yml")]
        operations.recipe_preview.side_effect = [dict(name="good", warnings=("run_root: not set",)),
                                                 dict(name="bad.yml", error="bad recipe"),  # the adapter's view
                                                 dict(name="wrong", problems=("stages[0] (fit): missing 'id'",),
                                                      warnings=("run_root: not set",))]

        def select(names, preview, broken, warnings, checking, position, live):
            self.assertEqual((checking, live), ([False] * 3, False))  # every check was read: not live
            self.assertEqual(preview(0), preview(0))
            self.assertEqual(preview(1), preview(1))
            self.assertEqual(preview(1)["error"], "bad recipe")
            self.assertEqual(broken, [False, True, True])  # every recipe is checked first, to mark it in the list
            self.assertEqual(warnings, [True, False, True])
            return "back", None

        ui.select_recipe.side_effect = select
        MenuNavigation(ui, operations).start()
        self.assertEqual(operations.recipe_preview.call_count, 3)
        operations.prepare_review.assert_not_called()
        operations.start_command.assert_not_called()

    def test_problems_and_descriptions_in_the_pipeline(self):
        ui = ConsoleUI(mock.Mock())
        view = dict(name="broken", stages=(("prod", "production", "mutau tuples"), ("summary", "python", "")),
                    problems=("pico.config: file not found: x.json", "stages[2] (fit): missing 'id'"))
        lines = ui._pipeline_lines(view, 40)
        text = "\n".join(lines)
        self.assertIn("2 problem(s):", text)
        self.assertIn("- pico.config: file not found: x.json", text)
        self.assertLess(text.index("problem(s)"), text.index("1. prod"))  # the problems come first
        cards = [line.strip()[2:-2].strip() for line in lines if line.strip().startswith("| ")]
        self.assertEqual(cards, ["1. prod", "mutau tuples", "2. summary", ""])

    def test_warnings_in_the_pipeline(self):
        ui = ConsoleUI(mock.Mock())
        view = dict(name="ok", stages=(("prod", "production", ""),), warnings=("run_root: not set",))
        lines = ui._pipeline_lines(view, 40)
        self.assertEqual(lines[lines.index("1 warning(s):") + 1], "- run_root: not set")
        text = "|".join(lines)
        self.assertLess(text.index("warning(s)"), text.index("1. prod"))
        view["problems"] = ("stages[0]: missing 'id'",)
        text = "|".join(ui._pipeline_lines(view, 40))
        self.assertLess(text.index("problem(s)"), text.index("warning(s)"))

    def test_recipe_list_colors_prioritize_errors_over_warnings(self):
        ui = ConsoleUI(mock.Mock())
        with mock.patch.object(ui, "_pipeline_choice", return_value=None) as choice:
            self.assertEqual(ui.select_recipe(["a", "b"], lambda i: {}, broken=[False, True]), ("back", None))
        self.assertEqual(choice.call_args.kwargs["row_colors"], [None, "error", None, None])
        with mock.patch.object(ui, "_pipeline_choice", return_value=None) as choice:
            ui.select_recipe(["ok", "warning", "error", "both"], lambda i: {},
                             broken=[False, False, True, True], warnings=[False, True, False, True])
        self.assertEqual(choice.call_args.kwargs["row_colors"],
                         [None, "warning", "error", "error", None, None])

    def test_warning_colors_survive_errors_wrapping_and_scrolling(self):
        for problems in ({}, {"problems": ("stages[0]: missing 'id'",)}, {"error": "invalid recipe"}):
            with self.subTest(problems=problems):
                curses, screen = self.curses([])
                ui = ConsoleUI(curses)
                with mock.patch.object(ui, "colors_enabled", return_value=True):
                    ui._setup(screen)
                self.assertEqual(ui.styles["warning"], curses.color_pair(8))
                view = dict(name="analysis", warnings=("run_root: not set, choose a run directory",), **problems)
                colors = []
                lines = ui._pipeline_lines(view, 24, colors=colors)
                self.assertEqual(len(lines), len(colors))
                self.assertEqual(colors[0], "error" if problems else "warning")
                start = lines.index("1 warning(s):")
                end = lines.index("", start)
                self.assertGreater(end - start, 2)  # warning wraps onto multiple lines
                self.assertEqual(colors[start:end], ["warning"] * (end - start))
                ui._viewport(screen, (1, 1, end - start + 1, 24), lines, start, line_colors=colors)
                for call in screen.addnstr.call_args_list[:end - start]:
                    self.assertEqual(call.args[4], ui.styles["warning"])

    def test_badge_colors_purple_and_gold_on_256_colors_else_magenta_and_yellow(self):
        for colors, brand, version in ((256, 135, 178), (8, 5, 3)):
            with self.subTest(colors=colors):
                curses, screen = self.curses([])
                curses.COLORS, curses.COLOR_MAGENTA, curses.COLOR_YELLOW = colors, 5, 3
                ui = ConsoleUI(curses)
                with mock.patch.object(ui, "colors_enabled", return_value=True):
                    ui._setup(screen)
                pairs = {call.args[0]: call.args[1] for call in curses.init_pair.call_args_list}
                self.assertEqual((pairs[9], pairs[10]), (brand, version))
                self.assertEqual(ui.styles["brand"], 9 * 512 | 128)  # bold
                self.assertEqual(ui.styles["version"], 10 * 512)

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
