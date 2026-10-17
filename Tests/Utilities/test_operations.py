"""Operations behind the menu: the supervisor, the operation directory, the states and the store."""
import json
import os
import signal
import socket
import sys
import tempfile
import time
import unittest
from unittest import mock

import checkout  # noqa: F401  (must precede TauFW.Utilities imports)
from TauFW.Utilities.Process import EVENTS_ENV, Operation, OperationStore
from TauFW.Utilities.Process import _operations, _supervisor
from TauFW.Utilities.Process._operations import DONE, FAILED, LOST, RUNNING, STOPPED, STOPPING

EMIT = ("import json, os\n"
        "with open(os.environ['%s'], 'a') as stream:\n"
        "    stream.write(json.dumps({'kind': 'case_end', 'id': 'a'}) + '\\n')\n" % EVENTS_ENV)


def wait(operation, seconds=30):
    deadline = time.time() + seconds
    while operation.running and time.time() < deadline:
        time.sleep(0.05)
    return operation.state()


class Clock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now


class FakeChild:
    """subprocess.Popen stand-in for the command: poll() returns the scripted statuses (the last repeats)."""
    pid = 4321

    def __init__(self, *statuses):
        self.statuses = list(statuses)

    def poll(self):
        return self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]


class OperationTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = os.path.join(self.temporary.name, "operations")
        self.store = OperationStore(self.root)

    def record(self, name="tests-1", **fields):
        """An operation directory written by hand (no supervisor)."""
        path = os.path.join(self.root, name)
        os.makedirs(path)
        record = dict(dict(kind="tests", title="Normal tests", argv=["x"], cwd=".", data={"expected": ["a"]},
                           host=socket.gethostname(), started=1000.0, heartbeat=5.0, escalate=True), **fields)
        _supervisor.write_json(os.path.join(path, "operation.json"), record)
        return path

    def write(self, path, name, data):
        _supervisor.write_json(os.path.join(path, name), data)


class SupervisorTests(OperationTestCase):
    """supervise() with a fake command, a fake clock and the stop/kill files."""

    def run_supervisor(self, child, escalate=True, files=(), terminated=()):
        path = self.record("tests-%d" % len(os.listdir(self.root)) if os.path.isdir(self.root) else "tests-0",
                           escalate=escalate)
        clock, signals = Clock(), []
        steps = {round(t / _supervisor.TICK): name for t, name in files}

        def sleep(seconds):
            clock.now += seconds
            name = steps.get(round((clock.now - 1000.0) / _supervisor.TICK))
            if name:
                open(os.path.join(path, name), "w").close()
        with mock.patch.object(_supervisor, "_signal", lambda process, number: signals.append(number)):
            code = _supervisor.supervise(path, popen=lambda *a, **k: child, clock=clock, sleep=sleep,
                                         terminated=terminated)
        with open(os.path.join(path, "exit.json")) as stream:
            return code, json.load(stream), signals, path

    def test_exit_code_heartbeat_and_exit_file(self):
        code, end, signals, path = self.run_supervisor(FakeChild(None, None, 3))
        self.assertEqual((code, end["returncode"], end["stopped"], signals), (3, 3, False, []))
        with open(os.path.join(path, "heartbeat.json")) as stream:
            beat = json.load(stream)
        self.assertEqual((beat["host"], beat["pid"], beat["child"]), (socket.gethostname(), os.getpid(), 4321))
        self.assertEqual(self.run_supervisor(FakeChild(None, -9))[0], 137)  # killed by signal 9

    def test_stop_escalates_and_a_stopped_failure_is_130(self):
        statuses = [None] * int(10 / _supervisor.TICK) + [-15]
        code, end, signals, _ = self.run_supervisor(FakeChild(*statuses), files=[(1.0, "stop")])
        self.assertEqual(signals, [signal.SIGINT, signal.SIGTERM, _supervisor.SIGKILL])
        self.assertEqual((code, end["stopped"]), (130, True))
        code, end, signals, _ = self.run_supervisor(FakeChild(*statuses), escalate=False, files=[(1.0, "stop")])
        self.assertEqual(signals, [signal.SIGINT])  # a run is never killed without the kill file
        code, end, signals, _ = self.run_supervisor(FakeChild(None, None, 0), files=[(0.2, "stop")])
        self.assertEqual((code, end["stopped"]), (0, True))  # it still succeeded

    def test_kill_file_and_sigterm_of_the_supervisor(self):
        statuses = [None] * 10 + [-9]
        _, _, signals, _ = self.run_supervisor(FakeChild(*statuses), escalate=False, files=[(0.4, "kill")])
        self.assertEqual(signals, [_supervisor.SIGKILL])
        _, end, signals, _ = self.run_supervisor(FakeChild(None, None, -2), terminated=[signal.SIGTERM])
        self.assertEqual((signals[0], end["stopped"], end["returncode"]), (signal.SIGINT, True, 130))

    def test_command_that_cannot_start(self):
        path = self.record()

        def fail(*args, **kwargs):
            raise FileNotFoundError("no such file: x")
        self.assertEqual(_supervisor.supervise(path, popen=fail), 127)
        operation = Operation.load(path)
        self.assertEqual((operation.state(), operation.returncode), (FAILED, 127))
        self.assertIn("Cannot start x", operation.output.read()[0])


class StateTests(OperationTestCase):
    def operation(self, path, now=1010.0, process=None):
        operation = Operation.load(path, clock=Clock(now))
        operation.process = process
        return operation

    def test_running_stopping_and_the_ends(self):
        path = self.record()
        self.write(path, "heartbeat.json", dict(host=socket.gethostname(), pid=None, t=1008.0))
        operation = self.operation(path)
        self.assertEqual((operation.state(), operation.running, operation.poll()), (RUNNING, True, None))
        self.assertEqual((operation.title, operation.data, operation.remote), ("Normal tests", {"expected": ["a"]},
                                                                                False))
        self.assertEqual(operation.elapsed(), 10.0)
        operation.cancel()
        self.assertEqual((operation.state(), operation.cancelled), (STOPPING, True))
        for end, state in ((dict(returncode=0, stopped=False), DONE), (dict(returncode=2, stopped=False), FAILED),
                           (dict(returncode=130, stopped=True), STOPPED)):
            self.write(path, "exit.json", dict(end, finished=1004.0))
            operation = self.operation(path)
            self.assertEqual((operation.state(), operation.running), (state, False))
            self.assertEqual(operation.elapsed(), 4.0)
        operation.cancel()  # an ended operation is not asked to stop
        self.assertFalse(os.path.exists(os.path.join(path, "kill")))

    def test_lost_without_a_heartbeat_or_without_its_supervisor(self):
        path = self.record()
        self.assertEqual(self.operation(path, now=1100.0).state(), RUNNING)  # just started: no heartbeat yet
        self.assertEqual(self.operation(path, now=1000.0 + _operations.LOST_AFTER + 1).state(), LOST)
        self.write(path, "heartbeat.json", dict(host="lxplus812.cern.ch", pid=1, t=1200.0))
        operation = self.operation(path, now=1250.0)
        self.assertEqual(operation.state(), RUNNING)  # another machine: only the heartbeat tells
        operation = self.operation(path, now=1250.0, process=mock.Mock(**{"poll.return_value": 1}))
        self.assertEqual(operation.state(), LOST)  # the supervisor this menu started ended without exit.json
        if os.name == "posix":
            self.write(path, "heartbeat.json", dict(host=socket.gethostname(), pid=2 ** 22 + 12345, t=1200.0))
            self.assertEqual(self.operation(path, now=1250.0).state(), LOST)  # its process is gone here

    def test_remote_and_unreadable_directories(self):
        path = self.record(host="lxplus812.cern.ch")
        self.assertTrue(Operation.load(path).remote)
        os.makedirs(os.path.join(self.root, "tests-broken"))
        with self.assertRaises(ValueError):
            Operation.load(os.path.join(self.root, "tests-broken"))
        self.assertEqual([operation.path for operation in self.store.all()], [path])


class StoreTests(OperationTestCase):
    def test_start_runs_the_command_beside_the_caller(self):
        code = "import os, sys, time\nprint('out')\nprint(os.environ.get('EXTRA'))\n" + EMIT + "time.sleep(0.5)\nsys.exit(3)\n"
        operation = self.store.start("tests", "Normal tests", [sys.executable, "-c", code], self.temporary.name,
                                     data={"expected": ["a"]}, env={"EXTRA": "x"}, heartbeat=0.1)
        self.assertEqual(wait(operation), FAILED)
        self.assertEqual(operation.returncode, 3)
        self.assertEqual(operation.output.read(), ["out", "x"])
        self.assertEqual(operation.events.read(), [{"kind": "case_end", "id": "a"}])
        self.assertTrue(os.path.isfile(os.path.join(operation.path, "heartbeat.json")))
        again = self.store.latest("tests")  # found again from its files, by any menu
        self.assertEqual((again.path, again.state(), again.title, again.data), (operation.path, FAILED,
                                                                              "Normal tests", {"expected": ["a"]}))
        self.assertEqual(again.events.read(), [{"kind": "case_end", "id": "a"}])  # a new object reads from the top
        self.assertEqual(self.store.running(), [])

    def test_start_options(self):
        calls = []
        popen = lambda argv, **kwargs: calls.append((argv, kwargs)) or mock.Mock(**{"poll.return_value": None})  # noqa
        with mock.patch.dict(os.environ, {EVENTS_ENV: "outer.jsonl"}):
            operation = self.store.start("tests", "T", ["cmd"], "/work", escalate=False, popen=popen)
        argv, kwargs = calls[0]
        self.assertEqual(argv, [sys.executable, "-B", _operations.SUPERVISOR, operation.path])
        self.assertTrue(kwargs["start_new_session"])
        self.assertEqual(kwargs["env"][EVENTS_ENV], os.path.join(operation.path, "events.jsonl"))
        self.assertEqual(operation.record["escalate"], False)
        self.assertEqual(os.path.basename(operation.path)[:6], "tests-")
        second = self.store.start("tests", "T", ["cmd"], "/work", popen=popen)
        self.assertNotEqual(second.path, operation.path)  # same second: a new directory all the same

    def test_kinds_order_running_and_prune(self):
        paths = [self.record("tests-%d" % index, started=1000.0 + index) for index in range(8)]
        for path in paths[:7]:
            self.write(path, "exit.json", dict(returncode=0, stopped=False, finished=2000.0))
        self.record("runs-1", kind="runs", started=5000.0)
        store = OperationStore(self.root, clock=Clock(1010.0))
        self.assertEqual([o.path for o in store.all("tests")], paths[::-1])
        self.assertEqual(store.latest("tests").path, paths[7])
        self.assertEqual([o.kind for o in store.all()][0], "runs")
        self.assertEqual([o.path for o in store.running("tests")], [paths[7]])
        store.prune("tests", keep=0)  # the running one stays
        self.assertEqual(sorted(os.listdir(self.root)), ["runs-1", "tests-7"])
        for index in range(3):
            self.write(self.record("tests-old%d" % index, started=900.0 + index), "exit.json",
                       dict(returncode=1, stopped=False, finished=950.0))
        store.prune("tests", keep=2)
        self.assertEqual(sorted(os.listdir(self.root)), ["runs-1", "tests-7", "tests-old2"])
        self.assertEqual(OperationStore(os.path.join(self.root, "missing")).all(), [])


@unittest.skipUnless(os.name == "posix", "process groups and signals: lxplus")
class RealStopTests(OperationTestCase):
    def test_stop_reaches_the_command_and_its_children(self):
        code = "import subprocess, sys, time\nsubprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\ntime.sleep(60)\n"
        operation = self.store.start("tests", "T", [sys.executable, "-c", code], self.temporary.name, heartbeat=0.1)
        time.sleep(1.0)
        self.assertEqual(operation.state(), RUNNING)
        operation.cancel()
        self.assertEqual(wait(operation, 20), STOPPED)
        self.assertEqual(operation.returncode, 130)

    def test_a_command_that_ignores_sigint_is_terminated(self):
        code = "import signal, time\nsignal.signal(signal.SIGINT, signal.SIG_IGN)\ntime.sleep(60)\n"
        operation = self.store.start("tests", "T", [sys.executable, "-c", code], self.temporary.name, heartbeat=0.1)
        time.sleep(1.0)
        Operation.load(operation.path).cancel()  # from another menu: only the file
        self.assertEqual(wait(operation, 20), STOPPED)


if __name__ == "__main__":
    unittest.main()
