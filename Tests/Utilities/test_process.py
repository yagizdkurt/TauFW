"""External command runner: logs, exit codes, expected outputs, timeouts."""

import os
import sys
import tempfile
import time
import unittest

import checkout  # noqa: F401  (must precede TauFW.Utilities imports)
from TauFW.Utilities.Process import Command, ProcessRunner


def python(code):
    return (sys.executable, "-c", code)


class ProcessRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = self.temporary.name
        self.runner = ProcessRunner()

    def tearDown(self):
        self.temporary.cleanup()

    def log(self, name="run.log"):
        return os.path.join(self.directory, name)

    def test_output_and_exit_code_are_logged(self):
        command = Command("hello", python("import sys; print('out'); print('err', file=sys.stderr)"),
                          self.directory)
        result = self.runner.run(command, self.log())
        self.assertTrue(result.ok)
        self.assertEqual(result.returncode, 0)
        with open(result.log) as stream:
            text = stream.read()
        self.assertIn("# hello", text)
        self.assertIn("out", text)
        self.assertIn("err", text)
        self.assertIn("# exit code 0", text)

    def test_nonzero_exit_is_not_ok(self):
        result = self.runner.run(Command("fail", python("raise SystemExit(3)"), self.directory), self.log())
        self.assertFalse(result.ok)
        self.assertEqual(result.returncode, 3)

    def test_expected_output_written_by_the_command(self):
        command = Command("write", python("open('out.root', 'w').write('x')"), self.directory,
                          expects=("*.root",))
        result = self.runner.run(command, self.log())
        self.assertTrue(result.ok, result)

    def test_missing_expected_output(self):
        command = Command("nothing", python("pass"), self.directory, expects=("out.root",))
        result = self.runner.run(command, self.log())
        self.assertFalse(result.ok)
        self.assertEqual(result.missing, ("out.root",))
        with open(result.log) as stream:
            self.assertIn("# missing output: out.root", stream.read())

    def test_stale_output_from_an_earlier_run_does_not_count(self):
        stale = os.path.join(self.directory, "out.root")
        open(stale, "w").close()
        old = time.time() - 3600
        os.utime(stale, (old, old))
        command = Command("nothing", python("pass"), self.directory, expects=("out.root",))
        self.assertEqual(self.runner.run(command, self.log()).missing, ("out.root",))

    def test_timeout(self):
        command = Command("slow", python("import time; time.sleep(30)"), self.directory, timeout=0.5)
        result = self.runner.run(command, self.log())
        self.assertEqual(result.returncode, -1)
        with open(result.log) as stream:
            self.assertIn("timeout", stream.read())

    def test_missing_program(self):
        command = Command("missing", ("taufw-no-such-program",), self.directory)
        self.assertEqual(self.runner.run(command, self.log()).returncode, 127)

    def test_run_all_stops_at_first_failure_and_numbers_logs(self):
        commands = [Command("first step", python("pass"), self.directory),
                    Command("second", python("raise SystemExit(1)"), self.directory),
                    Command("third", python("pass"), self.directory)]
        events = []
        logdir = os.path.join(self.directory, "logs")
        results = self.runner.run_all(commands, logdir,
                                      progress=lambda i, n, c, r: events.append((i, n, c.label, r is None)))
        self.assertEqual([r.label for r in results], ["first step", "second"])
        self.assertEqual(sorted(os.listdir(logdir)), ["01_first_step.log", "02_second.log"])
        self.assertEqual(events, [(1, 3, "first step", True), (1, 3, "first step", False),
                                  (2, 3, "second", True), (2, 3, "second", False)])

    def test_injected_execute_and_environment(self):
        seen = {}

        def execute(argv, cwd, stream, timeout, env):
            seen.update(argv=argv, cwd=cwd, timeout=timeout, extra=env.get("TAUFW_TEST"),
                        unbuffered=env.get("PYTHONUNBUFFERED"))
            stream.write("fake\n")
            return 0

        runner = ProcessRunner(execute=execute, env={"TAUFW_TEST": "1"})
        result = runner.run(Command("fake", ("prog", "a b"), "/work", timeout=5), self.log())
        self.assertTrue(result.ok)
        self.assertEqual(seen, {"argv": ("prog", "a b"), "cwd": "/work", "timeout": 5, "extra": "1",
                                "unbuffered": "1"})
        self.assertEqual(result.to_dict()["argv"], ["prog", "a b"])
        self.assertIs(result.to_dict()["ok"], True)

    def test_command_environment_on_top_of_the_runner(self):
        seen = {}

        def execute(argv, cwd, stream, timeout, env):
            seen.update(runner=env.get("TAUFW_TEST"), command=env.get("TAUFW_PICO_CONFIG"))
            return 0

        runner = ProcessRunner(execute=execute, env={"TAUFW_TEST": "1", "TAUFW_PICO_CONFIG": "/runner.json"})
        runner.run(Command("fake", ("prog",), "/work", env=(("TAUFW_PICO_CONFIG", "/run/pico.json"),)), self.log())
        self.assertEqual(seen, {"runner": "1", "command": "/run/pico.json"})

    def test_shell_line_quotes_arguments(self):
        self.assertEqual(Command("x", ("python3", "plot.py", "-S", "a && b"), ".").shell(),
                         "python3 plot.py -S 'a && b'")


if __name__ == "__main__":
    unittest.main()
