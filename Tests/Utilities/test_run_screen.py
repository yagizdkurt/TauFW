"""The run screen's model: stages from run.json data and the Framework's events, its words, the result card."""
import os
import tempfile
import unittest
from unittest import mock

import checkout  # noqa: F401  (must precede TauFW.Utilities imports)
from TauFW.Utilities.Menu import ConsoleUI
from TauFW.Utilities.Menu._preview import _advance
from TauFW.Utilities.Menu._run_screen import RunProgress, LOST_TEXT, run_summary

T = 1000.0
DATA = dict(run_id="tes_2025", run_dir="/eos/runs/tes_2025",
            stages=[dict(id="ntuples", type="production", state="DONE", message="",
                         info=[["Config", "pico_2025.yml"], ["Samples", "41"]]),
                    dict(id="plots", type="plotter", state="NEW", message=""),
                    dict(id="fit", type="fitter", state="NEW", message="")])


def event(kind, t=T, **fields):
    return dict(fields, kind=kind, t=t)


def plots(*more):
    return [event("run", run_id="tes_2025", run_dir="/eos/runs/tes_2025"),
            event("stage_step", stage="plots", type="plotter", state="NEW"),
            event("progress", stage="plots", index=1, total=2, label="etau 2025", status="run", log="/l/etau.log"),
            event("progress", T + 3, stage="plots", index=1, total=2, label="etau 2025", status="ok", seconds=3.0,
                  log="/l/etau.log"),
            event("progress", T + 3, stage="plots", index=2, total=2, label="mumu 2025", status="run",
                  log="/l/mumu.log")] + list(more)


class RunProgressTests(unittest.TestCase):
    def test_stages_from_data_then_a_step_with_local_commands(self):
        run = RunProgress(DATA)
        self.assertEqual([stage["state"] for stage in run.items()], ["DONE", "NEW", "NEW"])
        self.assertEqual(run.current(), 1)  # the first stage that is not DONE
        run.feed(plots())
        plot = run.items()[1]
        self.assertEqual(plot["state"], "RUN")
        with mock.patch("time.time", return_value=T + 5):
            text, time_text, role = run.row(plot)
            self.assertEqual(text, "[ RUN] plots    running 2/2 mumu 2025")
            self.assertEqual((time_text, role), ("00:05", "accent"))
            self.assertEqual(run.summary(), "stage 2/3 plots | 2/2 mumu 2025")
            self.assertEqual(run.details(plot), ["Type: plotter", "State: running 2/2 mumu 2025 for 00:05",
                                                 "Commands:", "  [ ok ] 1/2 etau 2025  3.0s",
                                                 "  [ RUN] 2/2 mumu 2025  00:02"])
        self.assertEqual(run.log(plot), "/l/mumu.log")
        self.assertIsNone(run.card())  # not ended
        self.assertEqual(run.states["RUNNING"], ("RUNNING", "accent"))

    def test_a_stage_with_one_command_is_not_counted(self):
        """A python step runs one command: "running", not "running 1/1 slow"; the header and the menus say only
        the stage."""
        run = RunProgress(dict(run_id="menutest", stages=[dict(id="slow", type="python"),
                                                          dict(id="second", type="python")]))
        run.feed([event("stage_step", stage="slow", type="python", state="NEW"),
                  event("progress", stage="slow", index=1, total=1, label="slow", status="run")])
        slow = run.items()[0]
        with mock.patch("time.time", return_value=T + 5):
            self.assertEqual(run.row(slow)[0], "[ RUN] slow    running")
            self.assertEqual(run.summary(), "stage 1/2 slow")
        run.finish(130, state="STOPPED")
        self.assertEqual(run.card()[1][1][0], "Finished stages are kept. Continue resumes from slow.")

    def test_the_facts_of_a_stage(self):
        run = RunProgress(DATA)
        self.assertEqual(run.info(run.items()[0]), ("Info: ntuples", [("Type", "production"),
                                                                      ("Config", "pico_2025.yml"), ("Samples", "41")]))
        self.assertNotIn("Type: production", run.details(run.items()[0]))  # in the box
        self.assertIsNone(run.info(run.items()[1]))  # none supplied: no box

    def test_waiting_for_jobs_counts_down_to_the_next_check(self):
        run = RunProgress(dict(DATA, stages=[dict(id="ntuples", type="production", state="NEW")]))
        run.feed([event("stage_step", stage="ntuples", type="production", state="NEW"),
                  event("stage_state", T + 2, stage="ntuples", state="SUBMITTED", message="852 jobs submitted"),
                  event("run_state", T + 2, run_id="tes_2025", state="WAITING"),
                  event("wait", T + 2, seconds=600)])
        stage = run.items()[0]
        with mock.patch("time.time", return_value=T + 62):
            self.assertEqual(run.summary(), "waiting for jobs | next check in 09:00")
            self.assertIn("Next check in 09:00 (every 10 min).", run.details(stage))
        self.assertEqual(run.row(stage)[1:], ("2.0s", "waiting"))
        run.feed([event("stage_step", T + 602, stage="ntuples", type="production", state="SUBMITTED")])
        self.assertIsNone(run.next_check)  # checking again

    def test_result_cards(self):
        cases = [
            (plots(event("stage_state", T + 6, stage="plots", state="DONE", message="2 command(s) ran"),
                   event("stage_step", T + 6, stage="fit", type="fitter", state="NEW"),
                   event("stage_state", T + 9, stage="fit", state="DONE", message=""),
                   event("run_state", T + 9, run_id="tes_2025", state="DONE")), 0, "DONE",
             "Run complete", "COMPLETE"),
            (plots(event("progress", T + 5, stage="plots", index=2, total=2, label="mumu 2025", status="failed",
                         seconds=2.0),
                   event("stage_state", T + 5, stage="plots", state="FAILED", message="mumu 2025: exit code 1"),
                   event("run_state", T + 5, run_id="tes_2025", state="FAILED")), 1, "FAILED",
             "Failed at plots", "FAILED"),
            (plots(), 130, "STOPPED", "Stopped", "STOPPED"),
            (plots(), None, "LOST", "Lost", "LOST"),
            ([event("stage_step", stage="plots", type="plotter", state="NEW"),
              event("stage_state", stage="plots", state="WAITING", message="jobs: 3 running"),
              event("run_state", run_id="tes_2025", state="WAITING")], 0, "DONE", "Waiting for jobs",
             "WAITING FOR JOBS"),
            ([event("stage_step", stage="plots", type="plotter", state="NEW")], 2, "FAILED", "Failed", "FAILED"),
        ]
        for events, code, state, title, line in cases:
            with self.subTest(title=title):
                run = RunProgress(DATA)
                run.feed(events)
                run.finish(code, lost=state == "LOST", state=state)
                card = run.card()
                self.assertEqual(card[0], title)
                self.assertEqual(card[1][-1], ("Run dir: /eos/runs/tes_2025", None))  # the full path
                self.assertEqual(run.states[state][0], line)
                self.assertNotIn("RUN", [stage["state"] for stage in run.items()])

    def test_stopped_and_lost_cards_say_where(self):
        run = RunProgress(DATA)
        run.feed(plots())
        run.finish(130, state="STOPPED")
        self.assertEqual(run.card()[1][0], ("Stopped during plots (1/2 commands finished).", "warning"))
        self.assertEqual(run.items()[1]["state"], "STOP")
        self.assertEqual(run.items()[1]["seconds"], 3.0)  # at work until the last event
        run = RunProgress(DATA)
        run.finish(None, lost=True, state="LOST")
        self.assertEqual(run.card()[1][0], (LOST_TEXT, "warning"))
        self.assertEqual(run.messages, [])  # the card says it

    def test_warnings_errors_and_unknown_stages(self):
        run = RunProgress()
        run.feed([event("warning", text="Command 'x' failed"), event("error", message="no run.json"),
                  event("stage_step", stage="extra", type="local", state="NEW"), event("unknown")])
        self.assertEqual(run.messages, [("warning", "Command 'x' failed"), ("error", "no run.json")])
        self.assertEqual([stage["id"] for stage in run.items()], ["extra"])

    def test_the_console_screen_follows_a_run(self):
        curses = mock.Mock(KEY_UP=1001, KEY_DOWN=1002, KEY_ENTER=1003, KEY_NPAGE=1004, KEY_PPAGE=1005,
                           KEY_END=1007, A_REVERSE=256)
        curses.error = RuntimeError
        screen = mock.Mock()
        screen.getmaxyx.return_value = (24, 90)
        screen.getch.side_effect = [27]
        curses.wrapper.side_effect = lambda action: action(screen)
        process = mock.Mock(data=DATA, returncode=None, remote=False, events=mock.Mock(read=lambda: plots()),
                            output=mock.Mock(lines=[], partial=""), state=lambda: "RUNNING", elapsed=lambda: 9.0)
        self.assertIsNone(ConsoleUI(curses).run_progress("Runs / tes_2025", process))
        drawn = [call.args[2] for call in screen.addnstr.call_args_list]
        self.assertTrue(any(" Stages " in line for line in drawn))
        self.assertIn("Up/Down Stage | Enter Stage log | L Output | S Stop | Esc Back (keeps running)", drawn)



def fake_curses(keys):
    curses = mock.Mock(KEY_UP=1001, KEY_DOWN=1002, KEY_ENTER=1003, A_REVERSE=256)
    curses.error = RuntimeError
    screen = mock.Mock()
    screen.getmaxyx.return_value = (24, 90)
    screen.getch.side_effect = keys
    curses.wrapper.side_effect = lambda action: action(screen)
    return curses, screen


class RunLabelTests(unittest.TestCase):
    """The menus' words for advances behind the menu (made-up advances of the UI preview)."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root, self.count = directory.name, 0

    def advance(self, kind="advancing", **options):
        self.count += 1
        return _advance(os.path.join(self.root, str(self.count)), kind, **options)

    def test_run_summary_of_every_state(self):
        cases = [(self.advance(ago=14.0), ("3/5 plots, 5/7 commands", "waiting")),
                 (self.advance("jobs", ago=8.0), ("1/5 ntuples, waiting for jobs", "waiting")),
                 (self.advance("complete"), ("Done", "good")),
                 (self.advance("waiting"), ("Waiting for jobs", "waiting")),
                 (self.advance("failed"), ("Failed at plots", "error")),
                 (self.advance("stopped"), ("Stopped at plots", "warning")),
                 (self.advance("lost"), ("Lost - Continue to resume", "error"))]
        for operation, expected in cases:
            with self.subTest(expected=expected[0]):
                self.assertEqual(run_summary(operation), expected)
        stopping = self.advance()
        stopping.cancel()
        self.assertEqual(run_summary(stopping), ("Stopping", "warning"))

    def test_main_menu_run_line(self):
        # found by its label, not its place: the menu order may change
        def run_row(choices):
            return next((index for index, choice in enumerate(choices) if choice.startswith("Run")), None)

        def run_line():
            choices = choose.call_args.args[1]
            row = run_row(choices)
            return choices[row], choose.call_args.kwargs["row_colors"][row]

        ui = ConsoleUI(mock.Mock())
        with mock.patch.object(ui, "choose", side_effect=lambda title, choices, **_: run_row(choices) or 0) as choose:
            ui.main_menu()
            plain = choose.call_args.args[1]
            self.assertIsNone(run_row(plain))  # no run: no line
            self.assertEqual(ui.main_menu(runs=[self.advance("failed")]), "run")
            self.assertEqual(run_line(), ("Run tes_2025 (Failed at plots)", "error"))
            choices = list(choose.call_args.args[1])
            del choices[run_row(choices)]
            self.assertEqual(choices, plain)  # the other lines keep their order
            self.assertEqual(ui.main_menu(runs=[self.advance("jobs", ago=8.0), self.advance("complete")]), "runs")
            self.assertEqual(run_line(), ("Runs (1 active, 1 ended)", "waiting"))
            ui.main_menu(runs=[self.advance(ago=1.0), self.advance("lost")])
            self.assertEqual(run_line(), ("Runs (1 active, 1 ended)", "error"))

    def test_runs_chooser_and_the_run_list_marks_an_advance(self):
        operations = [self.advance(ago=14.0), self.advance("failed", run_id="mutau_2024")]
        curses, screen = fake_curses([1002, 10, 27])
        self.assertEqual(ConsoleUI(curses).active_runs(operations), ("select", 1))
        drawn = [call.args[2] for call in screen.addnstr.call_args_list]
        self.assertTrue(any("tes_2025: 3/5 plots, 5/7 commands  00:14" in line for line in drawn))
        self.assertTrue(any("mutau_2024: Failed at plots" in line for line in drawn))
        self.assertEqual(ConsoleUI(curses).active_runs(operations), ("back", None))
        ui = ConsoleUI(mock.Mock())
        with mock.patch.object(ui, "choose", return_value=0) as choose:
            ui.select_run([("tes_2025", "WAITING", "today"), ("old", "DONE", "today")],
                          advances=[operations[0], None])
            self.assertEqual(choose.call_args.args[1][:2], ["tes_2025 | WAITING | updated today | advancing: "
                                                            "3/5 plots, 5/7 commands",
                                                            "old      | DONE    | updated today"])
            self.assertEqual(choose.call_args.kwargs["row_colors"][:2], ["waiting", "good"])

    def test_run_lock_screens(self):
        lock = dict(host="lxplus812.cern.ch", pid=23411, since="14:02", quiet=12.0)
        for keys, lost, answer in (([ord("t"), 27], False, "back"), ([ord("x"), ord("T")], True, "take"),
                                   ([10], True, "back"), ([KeyboardInterrupt()], True, "back")):
            with self.subTest(keys=keys, lost=lost):
                curses, screen = fake_curses(keys)
                self.assertEqual(ConsoleUI(curses).run_lock("tes_2025", dict(lock, lost=lost)), answer)
        drawn = [call.args[2] for call in screen.addnstr.call_args_list]
        self.assertIn("T Take over | Esc Back", drawn)
        self.assertIn("gave no sign of life for 00:12.", " ".join(drawn))


if __name__ == "__main__":
    unittest.main()
