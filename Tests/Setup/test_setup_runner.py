"""Focused progress/supervision tests without CMS software or network access."""
import codecs
import importlib.util
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "setup_runner", REPO / "Utilities/python/Installer/setup_runner.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class RunnerTests(unittest.TestCase):
    def state(self):
        worker = runner.Worker.__new__(runner.Worker)
        worker.stage = None
        worker.completed = set()
        worker.activity = ""
        worker.latest = ""
        worker.diagnostics = []
        worker.lines = []
        worker.summary = worker.retry = ""
        worker.pending_output = ""
        worker.pending_events = b""
        worker.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        return worker

    def test_selection_replaces_flags_preserving_paths_and_jobs(self):
        arguments = runner.worker_arguments(
            ["--cmssw-dir", "/release with spaces", "--jobs=7", "--skip-combine", "--run2-jme"],
            ["combine"])
        self.assertEqual(arguments, ["--cmssw-dir", "/release with spaces", "--jobs=7",
                                     "--non-interactive", "--skip-tauidsfs", "--skip-htt"])
        self.assertIn("--run2-jme", runner.worker_arguments([], ["run2-jme"]))

    def test_partial_events_and_output_diagnostics(self):
        worker = self.state()
        worker.feed_events(b"stage\0Preflight\0stage\0Build\0warning\0WARNING: architecture")
        worker.feed_events(b" mismatch\0")
        worker.feed_output(b"progress 1\rprogress 2\r\n\x1b[31mWARNING: architecture mismatch\x1b[0m\n")
        worker.feed_output(b">> Compiling python3 modules src/TauFW/Plotter/python\n")
        self.assertEqual(worker.stage, "Build")
        self.assertEqual(worker.completed, {"Preflight"})
        self.assertEqual(worker.activity, "Compiling Python modules")
        self.assertEqual(worker.diagnostics, ["WARNING: architecture mismatch"])
        self.assertEqual(worker.lines[:2], ["progress 1", "progress 2"])
        worker.feed_events(b"retry\0bash /moved/FastSetup.sh --non-interactive\0")
        self.assertIn("/moved/", worker.retry)
        worker.feed_output(b"fatal: last unterminated message", final=True)
        self.assertIn("fatal: last unterminated message", worker.diagnostics)

    def ui(self, keys):
        ui, screen = Mock(), Mock()
        ui.curses.KEY_ENTER = 1001
        ui.curses.KEY_UP, ui.curses.KEY_DOWN = 1002, 1003
        ui.curses.KEY_PPAGE, ui.curses.KEY_NPAGE = 1004, 1005
        screen.getmaxyx.side_effect = [(20, 70), (8, 24), (20, 70), (20, 70)]
        screen.getch.side_effect = keys
        return ui, screen

    def test_log_resize_and_wait_for_enter_keep_pumping(self):
        ui, screen = self.ui([ord("l"), 1002, ord("l"), 10])
        worker = Mock(started=time.monotonic(), finished=time.monotonic(),
                      returncode=7, lines=["detail"] * 30)
        worker.result.return_value = "Setup failed\nretry command"
        with patch.object(runner.time, "sleep"):
            self.assertEqual(runner.progress(ui, screen, worker), 7)
        self.assertEqual(worker.pump.call_count, 4)
        self.assertEqual(screen.refresh.call_count, 4)

    def test_ctrl_c_then_success_enter(self):
        ui, screen = self.ui([3, 10])
        worker = Mock(started=time.monotonic(), finished=None, returncode=None,
                      completed=set(), stage="Build", activity="Building", latest="line", diagnostics=[])
        def cancel():
            worker.returncode = 130
            worker.finished = time.monotonic()
        worker.cancel.side_effect = cancel
        worker.result.return_value = "Setup cancelled"
        with patch.object(runner.time, "sleep"):
            self.assertEqual(runner.progress(ui, screen, worker), 130)
        worker.cancel.assert_called_once()

    def test_one_wrapper_from_checklist_through_completion(self):
        ui, screen = Mock(), Mock()
        ui.setup_checklist.return_value = ["combine"]
        ui.curses.wrapper.side_effect = lambda action: action(screen)
        worker = Mock()
        worker.result.return_value = "Setup complete"
        with patch.object(runner.ConsoleUI, "open", return_value=ui), \
                patch.object(runner, "Worker", return_value=worker) as launch, \
                patch.object(runner, "progress", return_value=0) as progress, \
                patch("builtins.print"):
            self.assertEqual(runner.main(["--script", "/clone/FastSetup.sh", "--selected",
                                          "tauidsfs", "--", "--jobs=4"]), 0)
        ui.curses.wrapper.assert_called_once()
        self.assertIs(ui.setup_checklist.call_args.kwargs["screen"], screen)
        self.assertIs(progress.call_args.args[1], screen)
        self.assertIn("--skip-tauidsfs", launch.call_args.args[1])
        worker.close.assert_called_once()

    def test_cancel_checklist_does_not_launch_worker(self):
        ui = Mock()
        ui.setup_checklist.return_value = None
        ui.curses.wrapper.side_effect = lambda action: action(Mock())
        with patch.object(runner.ConsoleUI, "open", return_value=ui), \
                patch.object(runner, "Worker") as launch, patch("builtins.print"):
            self.assertEqual(runner.main(["--script", "/clone/FastSetup.sh"]), 130)
        launch.assert_not_called()

    def test_ui_failure_closes_worker_and_prints_recovery(self):
        ui, worker = Mock(), Mock()
        ui.setup_checklist.return_value = []
        ui.curses.wrapper.side_effect = lambda action: action(Mock())
        worker.result.return_value = "Setup cancelled\nbash /moved/FastSetup.sh"
        with patch.object(runner.ConsoleUI, "open", return_value=ui), \
                patch.object(runner, "Worker", return_value=worker), \
                patch.object(runner, "progress", side_effect=RuntimeError("terminal lost")), \
                patch("builtins.print") as output:
            self.assertEqual(runner.main(["--script", "/clone/FastSetup.sh"]), 1)
        worker.close.assert_called_once()
        self.assertTrue(any("/moved/" in str(call) for call in output.call_args_list))


@unittest.skipUnless(sys.platform.startswith("linux"), "POSIX process groups/pipes require Linux")
class WorkerProcessTests(unittest.TestCase):
    def finish(self, worker):
        deadline = time.monotonic() + 12
        while worker.returncode is None and time.monotonic() < deadline:
            worker.pump()
            time.sleep(0.01)
        self.assertIsNotNone(worker.returncode)

    def test_worker_move_and_failure_preserve_log_and_events(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "clone"
            source.mkdir()
            script = source / "setup.sh"
            script.write_text('''#!/bin/bash
printf 'stage\\0Build\\0' >&"$FASTSETUP_EVENT_FD"
mv -- "$(dirname "$0")" "$(dirname "$0")-moved"
printf '>> Compiling python3 modules src/TauFW/Plotter/python\\n'
printf 'WARNING: architecture\\n' >&2
printf 'retry\\0bash moved/setup.sh\\0' >&"$FASTSETUP_EVENT_FD"
exit 7
''')
            worker = runner.Worker(script, [])
            self.addCleanup(worker.close)
            self.finish(worker)
            self.assertEqual(worker.returncode, 7)
            self.assertIn("moved/", worker.retry)
            self.assertIn("WARNING: architecture", Path(worker.log_path).read_text())
            self.assertFalse(source.exists())
            Path(worker.log_path).unlink()

    def test_cancellation_signals_child_and_runs_shell_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "setup.sh"
            marker = Path(directory) / "cleaned"
            script.write_text('''#!/bin/bash
trap 'touch "$1"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
sleep 60 &
echo "$!"
wait
''')
            worker = runner.Worker(script, [str(marker)])
            self.addCleanup(worker.close)
            deadline = time.monotonic() + 2
            while not worker.lines and time.monotonic() < deadline:
                worker.pump()
                time.sleep(0.01)
            worker.cancel()
            self.finish(worker)
            self.assertEqual(worker.returncode, 130)
            self.assertTrue(marker.exists())
            Path(worker.log_path).unlink()


if __name__ == "__main__":
    unittest.main()
