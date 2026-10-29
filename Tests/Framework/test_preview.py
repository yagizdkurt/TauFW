"""The UI preview (Tests > UI preview): every scenario draws, Left/Right/R switch them, made-up runs move."""
import os
import tempfile
import unittest
from unittest import mock

import checkout  # noqa: F401  (must precede TauFW.Utilities imports)
from TauFW.Framework._internal.menu import ConsoleUI, MenuNavigation
from TauFW.Framework._internal.menu import _preview
from TauFW.Framework._internal.menu._preview import SCENARIOS, Scenario, _tests

LEFT, RIGHT = 1010, 1011


class Clock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now


def fake_curses(keys, typed=("\x1b",), size=(24, 90)):
    screen = mock.Mock()
    screen.getmaxyx.return_value = size
    screen.getch.side_effect = keys
    screen.get_wch.side_effect = list(typed)
    curses = mock.Mock()
    curses.error = RuntimeError
    curses.A_REVERSE = 256
    curses.color_pair.side_effect = lambda pair: pair * 512
    for name, value in (("KEY_UP", 1001), ("KEY_DOWN", 1002), ("KEY_ENTER", 1003), ("KEY_NPAGE", 1004),
                        ("KEY_PPAGE", 1005), ("KEY_END", 1007), ("KEY_BACKSPACE", 1006), ("KEY_LEFT", LEFT),
                        ("KEY_RIGHT", RIGHT)):
        setattr(curses, name, value)
    curses.wrapper.side_effect = lambda action: action(screen)
    return curses, screen


def drawn(screen):
    return [call.args[2] for call in screen.addnstr.call_args_list]


class PreviewTests(unittest.TestCase):
    def test_every_scenario_draws_and_esc_leaves(self):
        for index, scenario in enumerate(SCENARIOS):
            with self.subTest(scenario="%s: %s" % (scenario.group, scenario.name)):
                curses, screen = fake_curses([-1, -1, 27])
                with mock.patch.object(_preview, "SCENARIOS", [scenario]):
                    ConsoleUI(curses).preview()
                lines = drawn(screen)
                self.assertTrue(any("UI preview 1/1  %s: %s" % (scenario.group, scenario.name) in line
                                    for line in lines))
                self.assertGreater(len(lines), 3)  # the screen drew more than the bar
                curses.wrapper.assert_called_once()  # one curses session for all screens

    def test_left_right_and_r_switch_screens_and_an_answer_shows_it_again(self):
        shown = []

        def scenario(number):
            def show(ui, directory):
                shown.append(number)
                return ui.choose("Screen %d" % number, ["only"])
            return Scenario("Group", "screen %d" % number, show)

        curses, screen = fake_curses([RIGHT, RIGHT, RIGHT, LEFT, ord("r"), 10, 27])
        with mock.patch.object(_preview, "SCENARIOS", [scenario(0), scenario(1), scenario(2)]):
            ConsoleUI(curses).preview()
        self.assertEqual(shown, [0, 1, 2, 0, 2, 2, 2])  # wraps around; R and an answer show it again
        self.assertTrue(any("[answered 0]" in line for line in drawn(screen)))

    def test_ctrl_c_leaves_the_preview(self):
        curses, screen = fake_curses([KeyboardInterrupt()])
        with mock.patch.object(_preview, "SCENARIOS", SCENARIOS[:1]):
            ConsoleUI(curses).preview()

    def test_the_tests_menu_opens_it(self):
        ui, operations = mock.Mock(), mock.Mock()
        operations.tests_operation.return_value = None
        ui.tests_menu.side_effect = ["preview", "back"]
        MenuNavigation(ui, operations).tests()
        ui.preview.assert_called_once_with()
        operations.start_tests.assert_not_called()


class MockOperationTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.count = 0

    def directory(self):
        self.count += 1
        return os.path.join(self.root.name, str(self.count))

    def test_a_running_run_plays_its_script_and_passes(self):
        clock = Clock()
        operation = _tests(self.directory(), clock=clock)
        self.assertEqual(operation.state(), "RUNNING")
        self.assertEqual([event["kind"] for event in operation.events.read()], ["suite"])
        clock.now += 8.0
        self.assertEqual(operation.state(), "RUNNING")
        kinds = [event["kind"] for event in operation.events.read()]
        self.assertIn("case_end", kinds)
        clock.now += 60.0
        self.assertEqual(operation.state(), "DONE")
        events = operation.events.read()
        self.assertEqual(events[-1]["kind"], "summary")
        self.assertTrue(os.path.isfile(next(e["log"] for e in events if e["kind"] == "case_start")))
        self.assertFalse(operation.remote)

    def test_stop_failed_lost_and_remote(self):
        clock = Clock()
        operation = _tests(self.directory(), clock=clock)
        operation.cancel()
        self.assertEqual(operation.state(), "STOPPING")
        clock.now += 2.0
        self.assertEqual((operation.state(), operation.returncode), ("STOPPED", 130))
        failed = _tests(self.directory(), "failed", clock=clock)
        self.assertEqual(failed.state(), "FAILED")
        self.assertLess(failed.elapsed(), 60.0)  # it ended when its script did, not now
        self.assertIn("FAIL", [event.get("status") for event in failed.events.read()])
        self.assertEqual(_tests(self.directory(), "lost", clock=clock).state(), "LOST")
        remote = _tests(self.directory(), "remote", clock=clock)
        self.assertTrue(remote.remote)
        self.assertEqual(remote.host, "lxplus812.cern.ch")


if __name__ == "__main__":
    unittest.main()
