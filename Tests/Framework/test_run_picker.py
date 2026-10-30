"""Run browsing stays responsive while saved records or live status are slow."""
import threading
import unittest
from types import SimpleNamespace
from unittest import mock

import checkout  # noqa: F401
from TauFW.Framework._internal.menu import ConsoleUI
from TauFW.Framework._internal.menu._run_preview import RunPreview


class RunPickerTests(unittest.TestCase):
    summaries = [("tes_2025", "WAITING", "today"), ("mutau_2024", "DONE", "yesterday")]

    def terminal(self, keys, size=(24, 140)):
        screen = mock.Mock()
        screen.getmaxyx.return_value = size
        screen.getch.side_effect = keys
        curses = mock.Mock(KEY_UP=1001, KEY_DOWN=1002, KEY_ENTER=1003, KEY_NPAGE=1004, KEY_PPAGE=1005,
                           KEY_LEFT=1006, KEY_RIGHT=1007, A_REVERSE=256, A_BOLD=128)
        curses.error = RuntimeError
        curses.wrapper.side_effect = lambda draw: draw(screen)
        return ConsoleUI(curses), screen

    def test_loading_does_not_capture_run_navigation_or_escape(self):
        ui, screen = self.terminal([1002, -1, 1001, 27])
        preview = mock.Mock(return_value=dict(loading=True))
        with mock.patch("TauFW.Framework._internal.menu._loading.time.monotonic", return_value=0.6):
            self.assertEqual(ui.select_run(self.summaries, preview=preview), ("back", None))
        self.assertEqual([call.args[0] for call in preview.call_args_list], [0, 1, 1, 0])
        drawn = [call.args[2] for call in screen.addnstr.call_args_list]
        self.assertIn(" Runs ", drawn)
        self.assertIn(" Run status ", drawn)
        self.assertIn("H ----*", drawn)

    def test_continue_enter_focuses_actions_before_it_can_advance(self):
        ui, screen = self.terminal([10, 1002, 10])
        preview = mock.Mock(return_value=dict(run_id="tes_2025", state="WAITING", can_advance=True,
                                             stages=[dict(id="ntuples", state="WAITING")]))
        self.assertEqual(ui.select_run(self.summaries, preview=preview, mode="continue"), ("next", 0))
        self.assertEqual(screen.getch.call_count, 3)
        self.assertTrue(any(call.args[2] == "> Next stage only" for call in screen.addnstr.call_args_list))

    def test_resize_keeps_run_and_status_scroll_and_narrow_enter_selects(self):
        ui, screen = self.terminal([])
        keys = iter([(1004, (24, 90)), (-1, (24, 140)), (10, (24, 140))])

        def key():
            value, size = next(keys)
            screen.getmaxyx.return_value = size
            return value

        screen.getch.side_effect = key
        view = dict(run_id="tes_2025", state="WAITING", output=["line %d" % n for n in range(100)])
        preview, position = mock.Mock(side_effect=lambda target: view if target is not None else {}), {}
        self.assertEqual(ui.select_run(self.summaries, preview=preview, position=position), ("select", 0))
        self.assertEqual([call.args[0] for call in preview.call_args_list], [0, None, 0])
        self.assertGreater(position["offset"], 0)
        ui, screen = self.terminal([1002, 10], size=(24, 90))
        preview = mock.Mock(return_value={})
        self.assertEqual(ui.select_run(self.summaries, preview=preview, mode="continue"), ("select", 1))
        self.assertEqual([call.args[0] for call in preview.call_args_list], [None, None])


class RunPreviewTests(unittest.TestCase):
    def browser(self, operations, **options):
        browser = RunPreview(operations, "inspect", **options)
        browser.delay = 0
        self.addCleanup(browser.close)
        return browser

    def join(self, browser):
        browser.close()
        browser._thread.join(2)
        self.assertFalse(browser._thread.is_alive())

    def test_slow_old_status_cannot_replace_new_run_and_is_cancelled(self):
        entered, release, newer = threading.Event(), threading.Event(), threading.Event()
        self.addCleanup(release.set)

        def read_old():
            entered.set()
            self.assertTrue(release.wait(2))

        old = mock.Mock(output=SimpleNamespace(read=read_old, lines=["old status"], partial=""))
        new = mock.Mock(output=SimpleNamespace(read=newer.set, lines=["new status"], partial=""))
        old.state.return_value = new.state.return_value = "RUNNING"
        operations = mock.Mock()
        operations.run_preview.side_effect = lambda target: dict(run_id=target, state="WAITING")
        operations.start_command.side_effect = [old, new]
        browser = self.browser(operations)
        browser.view("old")
        self.assertTrue(entered.wait(2))
        self.assertNotIn("run_id", browser.view("new"))  # returns while the old worker read is still blocked
        release.set()
        self.assertTrue(newer.wait(2))
        with browser._condition:
            self.assertTrue(browser._condition.wait_for(
                lambda: browser._kept.get("new", {}).get("output") == ("new status",), timeout=2))
        self.join(browser)
        old.cancel.assert_called_once_with()
        new.cancel.assert_called_once_with()
        self.assertEqual(browser.view("new")["output"], ("new status",))

    def test_close_during_command_start_cancels_the_late_process(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        process = mock.Mock()

        def start(*args):
            entered.set()
            self.assertTrue(release.wait(2))
            return process

        operations = mock.Mock()
        operations.run_preview.return_value = dict(run_id="r", state="DONE")
        operations.start_command.side_effect = start
        browser = self.browser(operations)
        browser.view("r")
        self.assertTrue(entered.wait(2))
        browser.close()
        release.set()
        self.join(browser)
        process.cancel.assert_called_once_with()
        process.output.read.assert_not_called()

    def test_slow_discovery_does_not_block_focus_or_leaving(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)

        def listing():
            entered.set()
            self.assertTrue(release.wait(2))
            return [], [], []

        operations = mock.Mock()
        browser = self.browser(operations, listing=listing)
        self.assertEqual(browser.catalog(), (None, None))
        self.assertTrue(entered.wait(2))
        self.assertTrue(browser.view("r")["loading"])
        browser.close()
        release.set()
        self.join(browser)
        operations.run_preview.assert_not_called()
        operations.start_command.assert_not_called()

    def test_debounce_skips_intermediate_runs_and_refresh_keeps_old_output(self):
        clock = [0.0]
        first = mock.Mock(output=SimpleNamespace(read=lambda: None, lines=["kept status"], partial=""))
        first.state.return_value = "DONE"
        second = mock.Mock(output=SimpleNamespace(read=lambda: None, lines=[], partial=""))
        second.state.return_value = "RUNNING"
        operations = mock.Mock()
        operations.run_preview.side_effect = lambda target: dict(run_id=target, state="WAITING")
        operations.start_command.side_effect = [first, second]
        browser = self.browser(operations, clock=lambda: clock[0])
        browser.delay = 0.25
        browser.view("passed over")
        browser.view("selected")
        clock[0] = 1.0
        with browser._condition:
            browser._condition.notify_all()
            self.assertTrue(browser._condition.wait_for(
                lambda: browser._kept.get("selected", {}).get("output") == ("kept status",), timeout=2))
        operations.start_command.assert_called_once_with("status", "selected")
        self.assertEqual(browser.view("selected", refresh=True)["output"], ("kept status",))
        clock[0] = 2.0
        with browser._condition:
            browser._condition.notify_all()
            self.assertTrue(browser._condition.wait_for(
                lambda: browser._kept.get("selected", {}).get("revision") == browser._revision and
                        browser._kept["selected"].get("reading"), timeout=2))
        self.assertEqual(browser.view("selected")["output"], ("kept status",))
        self.join(browser)
        second.cancel.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
