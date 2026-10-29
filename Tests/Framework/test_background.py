"""Commands that run beside a screen: output to a log, events to a file, exit codes, cancelling."""
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

import checkout  # noqa: F401  (must precede TauFW.Utilities imports)
from TauFW.Utilities.Internal.Operations import EVENTS_ENV, BackgroundProcess
from TauFW.Utilities.Internal.Operations import _background

EMIT = ("import json, os\n"
        "with open(os.environ['%s'], 'a') as stream:\n"
        "    stream.write(json.dumps({'kind': 'case_end', 'id': 'a'}) + '\\n')\n" % EVENTS_ENV)


def wait(process, seconds=20):
    deadline = time.monotonic() + seconds
    while process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.02)
    return process.returncode


class FakeProcess:
    """subprocess.Popen stand-in: poll() returns the scripted statuses one by one."""
    pid = 4321

    def __init__(self, *statuses):
        self.statuses = list(statuses)

    def poll(self):
        return self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]

    def wait(self):
        return self.statuses[-1]


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class BackgroundProcessTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = self.temporary.name
        self.log = os.path.join(self.directory, "logs", "output.log")
        self.events = os.path.join(self.directory, "logs", "events.jsonl")

    def start(self, code, **options):
        return BackgroundProcess.start([sys.executable, "-c", code], self.directory, self.log, **options)

    def test_output_goes_to_the_log_and_events_to_their_file(self):
        code = ("import os, sys\nprint('out')\nprint('err', file=sys.stderr)\n"
                "print(os.environ.get('PYTHONUNBUFFERED'), os.environ.get('EXTRA'))\n" + EMIT)
        process = self.start(code, events=self.events, env={"EXTRA": "x"})
        self.assertEqual(wait(process), 0)
        self.assertFalse(process.running)
        self.assertEqual(process.output.read(), ["out", "err", "1 x"])
        self.assertEqual(process.events.read(), [{"kind": "case_end", "id": "a"}])
        self.assertGreaterEqual(process.elapsed(), 0)
        self.assertEqual(process.elapsed(), process.elapsed())  # frozen once it ended

    def test_files_start_empty_and_events_never_leak_into_a_command_without_them(self):
        os.makedirs(os.path.dirname(self.events))
        for path in (self.log, self.events):
            with open(path, "w") as stream:
                stream.write('{"kind": "stale"}\n')
        process = self.start("pass", events=self.events)
        wait(process)
        self.assertEqual(process.events.read(), [])
        self.assertEqual(process.output.read(), [])
        with mock.patch.dict(os.environ, {EVENTS_ENV: self.events}):
            process = self.start("import os; print(os.environ.get('%s'))" % EVENTS_ENV)
        wait(process)
        self.assertIsNone(process.events)
        self.assertEqual(process.output.read(), ["None"])

    def test_launch_options(self):
        popen = mock.Mock(return_value=FakeProcess(0))
        BackgroundProcess.start(["tool", "--flag"], self.directory, self.log, popen=popen)
        args, options = popen.call_args
        self.assertEqual(args, (["tool", "--flag"],))
        self.assertEqual(options["cwd"], self.directory)
        self.assertEqual(options["stdin"], _background.subprocess.DEVNULL)
        self.assertEqual(options["stderr"], _background.subprocess.STDOUT)
        self.assertTrue(options["start_new_session"])
        self.assertEqual(options["stdout"].name, self.log)

    def test_exit_codes(self):
        self.assertEqual(wait(self.start("raise SystemExit(3)")), 3)
        for status, expected in ((-9, 137), (5, 5), (0, 0)):
            process = BackgroundProcess(FakeProcess(status), ["x"], self.directory, self.log)
            self.assertEqual(process.poll(), expected)

    def test_cancel_escalates_to_the_whole_group(self):
        clock = Clock()
        process = BackgroundProcess(FakeProcess(None), ["x"], self.directory, self.log, clock=clock)
        with mock.patch.object(_background.os, "killpg", create=True) as kill, \
                mock.patch.object(_background.signal, "SIGKILL", 9, create=True), \
                mock.patch.object(_background.signal, "SIGTERM", 15, create=True):
            process.cancel()
            process.cancel()  # once is enough
            for now in (101.0, 103.0, 104.0, 108.0, 109.0):
                clock.now = now
                self.assertIsNone(process.poll())
        self.assertTrue(process.cancelled)
        self.assertEqual([call.args for call in kill.call_args_list],
                         [(4321, _background.signal.SIGINT), (4321, 15), (4321, 9)])

    def test_cancelled_run_reports_the_stop_unless_it_succeeded(self):
        for status, expected in ((-2, _background.STOP_EXIT), (1, _background.STOP_EXIT), (0, 0)):
            process = BackgroundProcess(FakeProcess(None, status), ["x"], self.directory, self.log)
            with mock.patch.object(_background.os, "killpg", create=True):
                process.cancel()
            self.assertEqual(process.poll(), expected)
        process = BackgroundProcess(FakeProcess(0), ["x"], self.directory, self.log)
        with mock.patch.object(_background.os, "killpg", create=True) as kill:
            process.cancel()  # already ended: nothing to stop
        kill.assert_not_called()

    def test_close_stops_a_running_command(self):
        clock = Clock()
        fake = FakeProcess(None)
        process = BackgroundProcess(fake, ["x"], self.directory, self.log, clock=clock)

        def sleep(seconds):
            clock.now += 1.0

        with mock.patch.object(_background.os, "killpg", create=True) as kill, \
                mock.patch.object(_background.signal, "SIGKILL", 9, create=True), \
                mock.patch.object(_background.signal, "SIGTERM", 15, create=True), \
                mock.patch.object(_background.time, "sleep", side_effect=sleep), \
                mock.patch.object(fake, "wait", side_effect=lambda: fake.statuses.__setitem__(0, -9)):
            process.close()
        self.assertEqual([call.args[1] for call in kill.call_args_list][:3], [_background.signal.SIGINT, 15, 9])
        self.assertEqual(process.returncode, _background.STOP_EXIT)

    @unittest.skipUnless(os.name == "posix", "process groups and signals are POSIX (lxplus)")
    def test_cancel_stops_a_real_command_and_its_children(self):
        code = ("import subprocess, sys, time\n"
                "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
                "print('started', flush=True)\ntime.sleep(60)\n")
        process = self.start(code)
        deadline = time.monotonic() + 10
        while not process.output.read() and time.monotonic() < deadline:
            time.sleep(0.02)
        process.cancel()
        self.assertEqual(wait(process), _background.STOP_EXIT)
        # the orphaned child can stay in the group for a moment until it is reaped: wait for it, with a deadline
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                os.killpg(process.process.pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.02)
        with self.assertRaises(ProcessLookupError):
            os.killpg(process.process.pid, 0)  # the whole group is gone


if __name__ == "__main__":
    unittest.main()
