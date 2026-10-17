"""The test screen: run state from events, and keys on a fake terminal with a scripted run behind the menu."""
import os
import tempfile
import unittest
from unittest import mock

import checkout  # noqa: F401  (must precede TauFW.Utilities imports)
from TauFW.Utilities.Menu import ConsoleUI
from TauFW.Utilities.Menu._test_run import TestRun, follow_tests, MESSAGES, LOST_TEXT
from TauFW.Utilities.Process import LogTail

UP, DOWN, ENTER, NPAGE, PPAGE, END = 1001, 1002, 1003, 1004, 1005, 1007


def start(name, log=None, t=None):
    return dict(kind="case_start", id=name, group="file.py", log=log, t=t)


def end(name, status, **fields):
    return dict(dict(kind="case_end", id=name, status=status, seconds=1.25, exit="", log=None), **fields)


class FakeRun:
    """An Operation stand-in: poll() returns the scripted codes (the last repeats), events.read() the
    scripted batches (then nothing); lost: it never ends, it is LOST."""

    def __init__(self, output, codes=(0,), batches=(), lost=False, remote=False):
        self.codes = list(codes)
        self.batches = list(batches)
        self.events = mock.Mock(read=lambda: self.batches.pop(0) if self.batches else [])
        self.output = LogTail(output)
        self.returncode = None
        self.cancelled = False
        self.lost = lost
        self.remote = remote
        self.host = "lxplus812.cern.ch"

    def state(self):
        if self.lost:
            return "LOST"
        if self.poll() is None:
            return "STOPPING" if self.cancelled else "RUNNING"
        if self.cancelled:
            return "STOPPED"
        return "DONE" if self.returncode == 0 else "FAILED"

    def poll(self):
        if self.returncode is None:
            self.returncode = self.codes.pop(0) if len(self.codes) > 1 else self.codes[0]
            if self.cancelled and self.returncode is None and not self.codes:
                self.returncode = 130
        return self.returncode

    def cancel(self):
        if self.returncode is None:
            self.cancelled = True
            self.codes = [130]

    def elapsed(self):
        return 75.0


class TestRunStateTests(unittest.TestCase):
    def test_expected_cases_wait_then_run_and_end(self):
        run = TestRun(["a", "b"])
        self.assertEqual([case["status"] for case in run.cases.values()], ["WAIT", "WAIT"])
        run.feed([dict(kind="suite", name="normal", total=2), start("a", "a.log", 10.0)])
        self.assertEqual((run.cases["a"]["status"], run.cases["a"]["log"]), ("RUN", "a.log"))
        run.feed([end("a", "FAIL", exit="exit 1", details=["diff"]), start("c"), dict(kind="unknown")])
        self.assertEqual(list(run.cases), ["a", "b", "c"])  # an unexpected case is added at the end
        self.assertEqual((run.cases["a"]["exit"], run.cases["a"]["details"], run.cases["a"]["log"]),
                         ("exit 1", ["diff"], "a.log"))  # the log of case_start is kept
        self.assertEqual(run.suites, ["normal"])
        counts = run.counts()
        self.assertEqual((counts["FAIL"], counts["WAIT"], counts["RUN"]), (1, 1, 1))
        run.finish(130)
        self.assertEqual(run.cases["c"]["status"], "STOP")
        self.assertEqual(run.messages, [])

    def test_messages_and_a_run_that_reported_nothing(self):
        run = TestRun()
        run.feed([dict(kind="warning", message="shadowing")] * (MESSAGES + 5) + [dict(kind="error", message="bad")])
        self.assertEqual(len(run.messages), MESSAGES)
        self.assertEqual(run.messages[-1], ("error", "bad"))
        run.finish(2)
        self.assertIn("exit code 2", run.messages[-1][1])
        quiet = TestRun()
        quiet.finish(0)
        self.assertEqual(quiet.messages, [])


class TestScreenTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = self.write("output.log", "")

    def write(self, name, text):
        path = os.path.join(self.temporary.name, name)
        with open(path, "w") as stream:
            stream.write(text)
        return path

    def curses(self, keys, size=(24, 90)):
        screen = mock.Mock()
        screen.getmaxyx.return_value = size
        screen.getch.side_effect = keys
        curses = mock.Mock()
        curses.error = RuntimeError
        curses.A_REVERSE = 256
        curses.color_pair.side_effect = lambda pair: pair * 512
        for name, value in (("KEY_UP", UP), ("KEY_DOWN", DOWN), ("KEY_ENTER", ENTER), ("KEY_NPAGE", NPAGE),
                            ("KEY_PPAGE", PPAGE), ("KEY_END", END)):
            setattr(curses, name, value)
        curses.wrapper.side_effect = lambda action: action(screen)
        return curses, screen

    @staticmethod
    def drawn(screen, since=0):
        return [call.args[2] for call in screen.addnstr.call_args_list[since:]]

    def test_cases_details_case_log_output_and_leaving_an_ended_run(self):
        log = self.write("b.log", "early\n\x1b[31mboom\x1b[0m\tline\n")
        with open(self.output, "w") as stream:
            stream.write("runner output\n")
        run = FakeRun(self.output, codes=(1,), batches=[[start("a"), end("a", "PASS"), start("b", log),
                                                         end("b", "FAIL", exit="exit 1", log=log)]])
        curses, screen = self.curses([-1, DOWN, ENTER, 27, ord("l"), 27, 27])
        self.assertEqual(ConsoleUI(curses).test_run("Normal tests", run, ["a", "b"]), 1)
        drawn = self.drawn(screen)
        self.assertTrue(any(line.startswith("[PASS] a") and line.rstrip().endswith("1.2s") for line in drawn))
        self.assertTrue(any(line.startswith("[FAIL] b") for line in drawn))
        self.assertIn("FAILED | 01:15 | 2/2 done, 1 passed, 1 failed, 0 skipped", drawn)
        self.assertIn("FAIL after 1.2s (exit 1)", drawn)
        self.assertIn("PASS after 1.2s", drawn)
        self.assertIn("boom    line", drawn)  # color codes removed, tab expanded
        self.assertIn(" Log: b ", drawn)
        self.assertIn("runner output", drawn)
        self.assertFalse(run.cancelled)
        screen.timeout.assert_called_once_with(100)

    def test_leaving_a_running_run_leaves_it_running(self):
        run = FakeRun(self.output, codes=(None,), batches=[[start("a")]])
        curses, screen = self.curses([-1, 27])
        self.assertIsNone(ConsoleUI(curses).test_run("Tests", run, ["a", "b"]))
        self.assertFalse(run.cancelled)
        drawn = self.drawn(screen)
        self.assertIn("Up/Down Case | Enter Case log | L Output | S Stop | Esc Back (keeps running)", drawn)
        self.assertTrue(any(line.startswith("RUNNING | 01:15 | 0/2 done") for line in drawn))

    def test_stop_key_and_ctrl_c_ask_then_stop_and_stay(self):
        for key in (ord("s"), KeyboardInterrupt()):
            with self.subTest(key=key):
                run = FakeRun(self.output, codes=(None,))
                curses, screen = self.curses([key, ord("n"), key, ord("y"), -1, 27])
                self.assertEqual(ConsoleUI(curses).test_run("Tests", run, ["a"]), 130)
                self.assertTrue(run.cancelled)
                drawn = self.drawn(screen)
                self.assertIn("Stop the tests? Y Yes | N No", drawn)
                self.assertTrue(any(line.startswith("STOPPED") for line in drawn))
                self.assertTrue(any(line.startswith("[    ] a") for line in drawn))  # "a" never started
                self.assertEqual(screen.getch.call_count, 6)  # stayed until Esc
        run = FakeRun(self.output, codes=(0,))
        curses, screen = self.curses([ord("s"), 27])
        ConsoleUI(curses).test_run("Tests", run, ["a"])
        self.assertNotIn("Stop the tests? Y Yes | N No", self.drawn(screen))  # an ended run is not stopped

    def test_a_lost_run_and_a_run_on_another_machine(self):
        run = FakeRun(self.output, codes=(None,), batches=[[start("a")]], lost=True)
        curses, screen = self.curses([-1, 27])
        self.assertIsNone(ConsoleUI(curses).test_run("Tests", run, ["a"]))
        drawn = self.drawn(screen)
        self.assertTrue(any(line.startswith("LOST") for line in drawn))
        self.assertTrue(any(line.startswith("[STOP] a") for line in drawn))
        self.assertTrue(any(line.startswith("! " + LOST_TEXT[:40]) for line in drawn))
        run = FakeRun(self.output, codes=(None,), remote=True)
        curses, screen = self.curses([27])
        ConsoleUI(curses).test_run("Tests / Normal tests", run, ["a"])
        drawn = self.drawn(screen)
        self.assertTrue(any(line.startswith("RUNNING on lxplus812.cern.ch | ") for line in drawn))
        self.assertIn("Up/Down Case | Enter Case log | L Output | S Stop | Esc Back (keeps running)", drawn)
        summary = [call.args for call in screen.addnstr.call_args_list if call.args[2].startswith("RUNNING on")]
        self.assertEqual(summary[0][:2], (2, 1))  # too long for the title's line: below it

    def test_a_run_without_cases_shows_its_output_and_scrolls(self):
        with open(self.output, "w") as stream:
            stream.write("".join("line %d\n" % index for index in range(100)))
        run = FakeRun(self.output, codes=(0,))
        curses, screen = self.curses([-1, PPAGE, -1, END, -1, 27])
        frames = []
        screen.refresh.side_effect = lambda: frames.append(self.drawn(screen, sum(map(len, frames))))
        self.assertEqual(ConsoleUI(curses).test_run("Check environment", run), 0)
        self.assertIn(" Output of Tests/run.py ", frames[0])
        follow, scrolled, held, again = frames[1], frames[2], frames[3], frames[4]
        self.assertIn("line 99", follow)  # follows the end
        self.assertNotIn("line 99", scrolled)  # one page up
        self.assertEqual(scrolled, held)  # stays there while the log is read again
        self.assertIn("line 99", again)  # End follows again

    def test_small_terminal(self):
        run = FakeRun(self.output, codes=(0,))
        curses, screen = self.curses([27], size=(10, 30))
        ConsoleUI(curses).test_run("Tests", run)
        self.assertIn("Enlarge terminal (at least 40 x 12).", self.drawn(screen))


if __name__ == "__main__":
    unittest.main()
