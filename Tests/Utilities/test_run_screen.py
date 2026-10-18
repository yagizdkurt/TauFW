"""The run screen's model: stages from run.json data and the Framework's events, its words, the result card."""
import unittest
from unittest import mock

import checkout  # noqa: F401  (must precede TauFW.Utilities imports)
from TauFW.Utilities.Menu import ConsoleUI
from TauFW.Utilities.Menu._run_screen import RunProgress, LOST_TEXT

T = 1000.0
DATA = dict(run_id="tes_2025", run_dir="/eos/runs/tes_2025",
            stages=[dict(id="ntuples", type="production", state="DONE", message=""),
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
            self.assertEqual(text, "[ RUN] plots    plotter     running 2/2 mumu 2025")
            self.assertEqual((time_text, role), ("00:05", "accent"))
            self.assertEqual(run.summary(), "stage 2/3 plots | 2/2 mumu 2025")
            self.assertEqual(run.details(plot), ["Type: plotter", "State: running 2/2 mumu 2025 for 00:05",
                                                 "Commands:", "  [ ok ] 1/2 etau 2025  3.0s",
                                                 "  [ RUN] 2/2 mumu 2025  00:02"])
        self.assertEqual(run.log(plot), "/l/mumu.log")
        self.assertIsNone(run.card())  # not ended
        self.assertEqual(run.states["RUNNING"], ("RUNNING", "accent"))

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


if __name__ == "__main__":
    unittest.main()
