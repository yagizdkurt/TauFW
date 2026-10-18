"""The operation screen takes its items and words from its model (the test screen is one model, test_test_run.py)."""
import os
import tempfile
import unittest
from unittest import mock

import checkout  # noqa: F401  (must precede TauFW.Utilities imports)
from TauFW.Utilities.Menu import ConsoleUI
from TauFW.Utilities.Menu._operation_screen import ScreenModel, follow, printable
from TauFW.Utilities.Process import LogTail

UP, DOWN, ENTER = 1001, 1002, 1003


class Stages(ScreenModel):
    """A model that is not about tests: items from `stage` events."""
    list_title = "Stages"
    item = "Stage"
    output_title = "Output of advance"
    stop_question = "Stop the advance?"
    states = dict(ScreenModel.states, DONE=("COMPLETE", "good"))

    def __init__(self, log):
        super().__init__()
        self.stages = []
        self.path = log
        self.ended = None

    def feed(self, events):
        self.stages += [event["name"] for event in events]

    def finish(self, returncode, lost=False, state=None):
        self.ended = (returncode, lost)

    def items(self):
        return self.stages

    def row(self, stage):
        return "> " + stage, "1s", "good"

    def details(self, stage):
        return ["stage %s\x1b[31m" % stage]

    def log(self, stage):
        return self.path if stage == "plots" else None

    def summary(self):
        return "%d stage(s)" % len(self.stages)

    def info(self, stage):
        return ("Info: %s" % stage, [("Config", "plots_2025.yml"), ("Output", "a very long output directory name")])


class Process:
    def __init__(self, output, states):
        self.states = list(states)
        self.events = mock.Mock(read=mock.Mock(side_effect=[[dict(name="ntuples"), dict(name="plots")]] + [[]] * 20))
        self.output = LogTail(output)
        self.returncode = None
        self.remote = False
        self.cancel = mock.Mock()

    def state(self):
        state = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        self.returncode = 0 if state == "DONE" else None
        return state

    def elapsed(self):
        return 61.0


class OperationScreenTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.output = os.path.join(directory.name, "output.log")
        self.log = os.path.join(directory.name, "plots.log")
        with open(self.log, "w") as stream:
            stream.write("Info in <TCanvas::Print>: png file a.png has been created\n")
        open(self.output, "w").close()

    def screen(self, keys, size=(24, 90)):
        screen = mock.Mock()
        screen.getmaxyx.return_value = size
        screen.getch.side_effect = keys
        curses = mock.Mock(KEY_UP=UP, KEY_DOWN=DOWN, KEY_ENTER=ENTER, KEY_NPAGE=1004, KEY_PPAGE=1005, KEY_END=1007,
                           A_REVERSE=256)
        curses.error = RuntimeError
        return ConsoleUI(curses), screen

    def test_items_words_and_states_come_from_the_model(self):
        ui, screen = self.screen([-1, DOWN, ord("s"), ord("y"), 10, 27, 27])
        process = Process(self.output, ["RUNNING", "RUNNING", "RUNNING", "RUNNING", "DONE"])
        model = Stages(self.log)
        self.assertEqual(follow(ui, screen, "Runs / tes_2025", process, model), 0)
        drawn = [call.args[2] for call in screen.addnstr.call_args_list]
        self.assertTrue(any(" Stages " in line for line in drawn))
        self.assertTrue(any(line.startswith("> ntuples") for line in drawn))
        self.assertIn("Up/Down Stage | Enter Stage log | L Output | S Stop | Esc Back (keeps running)", drawn)
        self.assertIn("Stop the advance? Y Yes | N No", drawn)
        self.assertTrue(any("RUNNING | 01:01 | 2 stage(s)" in line for line in drawn))
        self.assertTrue(any("COMPLETE | 01:01 | 2 stage(s)" in line for line in drawn))
        self.assertTrue(any(" Details: plots " in line for line in drawn))
        self.assertTrue(any(" Log: plots " in line for line in drawn))
        self.assertIn("stage plots", drawn)  # details are made printable
        self.assertTrue(any("png file a.png" in line for line in drawn))  # the focused item's log
        process.cancel.assert_called_once_with()
        self.assertEqual(model.ended, (0, False))  # finish() once the operation ended

    def test_the_info_box_beside_the_list_or_on_top_of_the_details(self):
        for size, beside in (((24, 120), True), ((24, 90), False)):
            with self.subTest(size=size):
                ui, screen = self.screen([-1, 27], size=size)
                follow(ui, screen, "Runs / tes_2025", Process(self.output, ["RUNNING"]), Stages(self.log))
                calls = [call.args for call in screen.addnstr.call_args_list]
                drawn = [args[2] for args in calls]
                self.assertEqual(any(" Info: ntuples " in line for line in drawn), beside)
                fact = [args for args in calls if args[2].startswith("Config")]
                self.assertTrue(fact)
                if beside:
                    self.assertEqual(fact[0][1], 120 - 1 - 36 + 2)  # inside the box right of the list
                    self.assertIn("Output  a very long output", drawn)  # wrapped under its value
                    self.assertIn("        directory name", drawn)
                else:
                    self.assertEqual(fact[0][1], 3)  # the first line of the Details
                    self.assertIn("Output  a very long output directory name", drawn)

    def test_printable(self):
        self.assertEqual(printable("\x1b[1ma\tb\x07"), "a   b")


if __name__ == "__main__":
    unittest.main()
