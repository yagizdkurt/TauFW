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
    "setup_runner", REPO / "Framework/python/_internal/installer/setup_runner.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class RunnerTests(unittest.TestCase):
    def test_missing_curses_uses_text_selection_and_preserves_options(self):
        with patch.dict(sys.modules, {"curses": None}), \
                patch.object(runner.sys, "platform", "linux"), \
                patch.object(runner.sys.stdin, "isatty", return_value=True), \
                patch.object(runner.sys.stdout, "isatty", return_value=True), \
                patch("builtins.input", side_effect=["invalid", "", "no", "yes", "", "yes"]), \
                patch("builtins.print"), patch.object(runner.ArgumentParser, "print_help"), \
                patch.object(runner.subprocess, "call", return_value=0) as launch, \
                patch.object(runner, "bell") as bell:
            runner.main(["--script", "/clone with spaces/Utilities/FastSetup.sh",
                         "--selected", "tauidsfs", "htt", "--",
                         "--jobs", "7", "--cmssw-dir", "/release with spaces", "--skip-combine"])
        bell.assert_called_once_with()
        launch.assert_called_once_with(["bash", "/clone with spaces/Utilities/FastSetup.sh",
                                               "--jobs", "7", "--cmssw-dir", "/release with spaces",
                                               "--non-interactive", "--skip-htt"])

    def test_text_selection_cancellation_never_installs(self):
        for answers in (["", "", "", "", "no"], [EOFError], [KeyboardInterrupt]):
            with self.subTest(answers=answers), \
                    patch.object(runner.ConsoleUI, "open", return_value=None), \
                    patch.object(runner.sys.stdin, "isatty", return_value=True), \
                    patch.object(runner.sys.stdout, "isatty", return_value=True), \
                    patch("builtins.input", side_effect=answers), patch("builtins.print"), \
                    patch.object(runner.subprocess, "call") as launch:
                self.assertEqual(runner.main(["--script", "/clone/Utilities/FastSetup.sh"]), 130)
                launch.assert_not_called()

    def test_screen_initialization_failure_uses_text_before_starting_worker(self):
        ui = Mock()
        ui.curses.wrapper.side_effect = RuntimeError("terminal unavailable")
        with patch.object(runner.ConsoleUI, "open", return_value=ui), \
                patch.object(runner, "text_setup", return_value=130) as fallback, \
                patch.object(runner, "Worker") as launch, patch("builtins.print"):
            self.assertEqual(runner.main(["--script", "/clone/Utilities/FastSetup.sh"]), 130)
        fallback.assert_called_once()
        launch.assert_not_called()

    def test_text_fallback_without_terminal_does_not_prompt_or_install(self):
        with patch.object(runner.ConsoleUI, "open", return_value=None), \
                patch.object(runner.sys.stdin, "isatty", return_value=False), \
                patch("builtins.input") as prompt, patch("builtins.print"), \
                patch.object(runner.os, "execvp") as launch:
            self.assertEqual(runner.main(["--script", "/clone/Utilities/FastSetup.sh"]), 1)
        prompt.assert_not_called()
        launch.assert_not_called()

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
        worker.feed_events(b"retry\0bash /moved/Utilities/FastSetup.sh --non-interactive\0")
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
        with patch.object(runner.time, "sleep"), patch.object(runner, "bell") as bell:
            self.assertEqual(runner.progress(ui, screen, worker), 7)
        bell.assert_called_once_with()  # resizing and waiting for Enter must not repeat the bell
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
            self.assertEqual(runner.main(["--script", "/clone/Utilities/FastSetup.sh", "--selected",
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
            self.assertEqual(runner.main(["--script", "/clone/Utilities/FastSetup.sh"]), 130)
        launch.assert_not_called()

    def test_ui_failure_closes_worker_and_prints_recovery(self):
        ui, worker = Mock(), Mock()
        ui.setup_checklist.return_value = []
        ui.curses.wrapper.side_effect = lambda action: action(Mock())
        worker.result.return_value = "Setup cancelled\nbash /moved/Utilities/FastSetup.sh"
        with patch.object(runner.ConsoleUI, "open", return_value=ui), \
                patch.object(runner, "Worker", return_value=worker), \
                patch.object(runner, "progress", side_effect=RuntimeError("terminal lost")), \
                patch("builtins.print") as output:
            self.assertEqual(runner.main(["--script", "/clone/Utilities/FastSetup.sh"]), 1)
        worker.close.assert_called_once()
        self.assertTrue(any("/moved/" in str(call) for call in output.call_args_list))


    def test_success_summary_has_one_heading_and_one_warning(self):
        worker = self.state()
        worker.returncode, worker.cancelled = 0, False
        worker.log_path = "/tmp/installation.log"
        worker.summary = "[OK] Setup complete\n\nOptional components\n  None selected\nOriginal checkout retained at: /original"
        worker.diagnostics = ["existing checkout differs"]
        result = worker.result()
        self.assertEqual(result.count("Setup complete"), 1)
        self.assertEqual(result.count("existing checkout differs"), 1)
        self.assertIn("Installation log: /tmp/installation.log", result)
        notices = worker.completion_notices()
        self.assertNotIn("Setup complete", notices)
        self.assertIn("Original checkout retained at: /original", notices)

    def test_color_and_unicode_fallbacks(self):
        with patch.dict(os.environ, {"LC_ALL": "C", "TERM": "xterm", "NO_COLOR": ""}), \
                patch.object(runner.sys.stdout, "isatty", return_value=True):
            self.assertTrue(runner.colors_enabled())
            self.assertEqual(runner.presentation("[OK] Setup complete"), ("[OK] Setup complete", "success"))
            self.assertEqual(runner.presentation("  TauIDSFs: Not selected")[1], "skipped")
            with patch.dict(os.environ, {"NO_COLOR": "1"}):
                self.assertFalse(runner.colors_enabled())
                self.assertEqual(runner.screen_palette(Mock()), {})
            with patch.dict(os.environ, {"TERM": "dumb"}):
                self.assertFalse(runner.colors_enabled())
        with patch.object(runner.sys.stdout, "isatty", return_value=False):
            self.assertFalse(runner.colors_enabled())
        with patch.object(runner, "unicode_enabled", return_value=True):
            self.assertEqual(runner.presentation("[OK] Setup complete")[0], "? Setup complete")
            self.assertEqual(runner.presentation("[FAIL] Setup failed")[0], "? Setup failed")

    def test_terminal_colors_only_when_enabled(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled), \
                    patch.object(runner, "colors_enabled", return_value=enabled), \
                    patch.object(runner, "unicode_enabled", return_value=False), patch("builtins.print") as output:
                runner.print_terminal("[OK] Setup complete\n  None selected")
                rendered = "\n".join(call.args[0] for call in output.call_args_list)
                self.assertEqual("\x1b[" in rendered, enabled)

    def test_wrapper_success_hands_off_log_without_replaying_summary(self):
        ui, screen = Mock(), Mock()
        ui.setup_checklist.return_value = []
        ui.curses.wrapper.side_effect = lambda action: action(screen)
        worker = Mock(log_path="/tmp/retained log.log")
        worker.completion_notices.return_value = "[!] warning\nOriginal checkout retained at: /original"
        with tempfile.TemporaryDirectory() as directory:
            handoff = str(Path(directory) / "result")
            with patch.dict(os.environ, {"FASTSETUP_RESULT_FILE": handoff}), \
                    patch.object(runner.ConsoleUI, "open", return_value=ui), \
                    patch.object(runner, "Worker", return_value=worker), \
                    patch.object(runner, "progress", return_value=0), \
                    patch.object(runner, "print_terminal") as output:
                self.assertEqual(runner.main(["--script", "/clone/Utilities/FastSetup.sh"]), 0)
            self.assertEqual(Path(handoff + ".log-path").read_text(), "/tmp/retained log.log\n")
            worker.result.assert_not_called()
            output.assert_called_once_with(worker.completion_notices.return_value)

    def test_wrapper_footer_on_narrow_screen(self):
        ui, screen = self.ui([10])
        screen.getmaxyx.side_effect = None
        screen.getmaxyx.return_value = (8, 28)
        worker = Mock(started=time.monotonic(), finished=time.monotonic(), returncode=0, lines=[])
        worker.result.return_value = "[OK] Setup complete\n" + "/long/check/out/" * 8
        with patch.dict(os.environ, {"FASTSETUP_RESULT_FILE": "/tmp/result"}), \
                patch.object(runner.time, "sleep"), patch.object(runner, "unicode_enabled", return_value=False):
            self.assertEqual(runner.progress(ui, screen, worker), 0)
        lines = [call.args[3] for call in ui._line.call_args_list]
        self.assertIn("L View log | Enter Activate", lines)
        self.assertIn("[OK] Setup complete", lines)


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
