"""The advance lock of a run directory (run_lock.py), Framework.advance with it, and taufw.py advance --take-lock."""
import importlib.util
import json
import os
import shutil
import socket
import tempfile
import time
import unittest
from unittest import mock

import checkout  # noqa: F401  (must precede TauFW imports)
import fakes
from TauFW.Framework import RunRecord, RunLockError, SilentReporter, read_lock
from TauFW.Framework.runtime import run_lock
from TauFW.Framework.runtime.run_lock import LOCK_NAME, LOST_AFTER, RunLock
from test_framework import framework


def foreign(directory, host="lxplus999.cern.ch", pid=4711, quiet=0.0):
    """A lock of another advance, with its last sign of life `quiet` seconds ago."""
    path = os.path.join(directory, LOCK_NAME)
    with open(path, "w") as stream:
        json.dump(dict(host=host, pid=pid, since="2026-10-21 14:02:00", t=time.time() - quiet), stream)
    return path


def text(path):
    with open(path) as stream:
        return stream.read()


def until(condition, seconds=5.0):
    end = time.time() + seconds
    while time.time() < end:
        if condition():
            return True
        time.sleep(0.01)
    return False


class LockTestCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="taufw-test-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.path = os.path.join(self.root, LOCK_NAME)


class RunLockTests(LockTestCase):
    def test_held_while_in_the_block_and_removed_after(self):
        with RunLock(self.root) as lock:
            held = read_lock(self.root)
            self.assertEqual((held["host"], held["pid"]), (socket.gethostname(), os.getpid()))
            self.assertFalse(held["lost"])
            self.assertIsNone(lock.taken)
        self.assertFalse(os.path.exists(self.path))
        self.assertIsNone(read_lock(self.root))

    def test_a_second_lock_is_refused(self):
        with RunLock(self.root):
            with self.assertRaises(RunLockError) as caught:
                RunLock(self.root).acquire()
        self.assertFalse(caught.exception.lost)
        self.assertIn("pid %d" % (os.getpid()), str(caught.exception))

    def test_a_live_lock_of_another_machine_is_never_taken(self):
        foreign(self.root, quiet=10)
        with self.assertRaises(RunLockError) as caught:
            RunLock(self.root, take=True).acquire()
        self.assertIn("lxplus999.cern.ch since 2026-10-21 14:02:00 (pid 4711)", str(caught.exception))
        self.assertFalse(caught.exception.lost)

    def test_a_lost_lock_of_another_machine_is_taken_only_when_asked(self):
        foreign(self.root, quiet=LOST_AFTER + 30)
        with self.assertRaises(RunLockError) as caught:
            RunLock(self.root).acquire()
        self.assertTrue(caught.exception.lost)
        self.assertIn("it is lost", str(caught.exception))
        with RunLock(self.root, take=True) as lock:
            self.assertEqual(lock.taken["pid"], 4711)
            self.assertEqual(read_lock(self.root)["pid"], os.getpid())
        self.assertFalse(os.path.exists(self.path))

    def test_a_lock_of_this_machine_whose_process_is_gone_is_taken_at_once(self):
        foreign(self.root, host=socket.gethostname(), pid=999999, quiet=1)
        with mock.patch.object(run_lock, "_alive", side_effect=lambda pid: pid != 999999):
            with RunLock(self.root) as lock:
                self.assertEqual(lock.taken["pid"], 999999)

    def test_the_takeover_says_why(self):
        pico = fakes.FakePicoProducer(statuses=[fakes.complete("DY", "TT")])
        for host, quiet, why in ((socket.gethostname(), 1, "its process is gone"),
                                 (socket.gethostname(), LOST_AFTER + 30, "its process is gone"),  # the surer reason
                                 ("lxplus999.cern.ch", LOST_AFTER + 30, "no sign of life for 150 s")):
            with self.subTest(why=why, host=host):
                record = framework(pico).start(run_root=tempfile.mkdtemp(dir=self.root))
                foreign(record.run_dir, host=host, pid=999999, quiet=quiet)
                fw = framework(pico)
                with mock.patch.object(run_lock, "_alive", side_effect=lambda pid: pid != 999999):
                    fw.advance(record, take_lock=True)
                warnings = [text for kind, text in fw.reporter.messages if kind == "warning"]
                self.assertIn("Took over the advance lock of pid 999999 on %s (since 2026-10-21 14:02:00, %s)"
                              % (host, why), warnings)

    def test_a_half_written_lock_goes_by_the_file_time(self):
        open(self.path, "w").close()
        old = time.time() - LOST_AFTER - 30
        os.utime(self.path, (old, old))
        lock = read_lock(self.root)
        self.assertEqual(lock["host"], "?")
        self.assertTrue(lock["lost"])
        with RunLock(self.root, take=True) as taken:
            self.assertEqual(taken.taken["host"], "?")

    def test_the_heartbeat_renews_the_time(self):
        with RunLock(self.root, heartbeat=0.01):
            first = read_lock(self.root)["t"]
            self.assertTrue(until(lambda: (read_lock(self.root) or {}).get("t", first) > first))

    def test_check_raises_once_the_lock_was_taken_over(self):
        with RunLock(self.root, heartbeat=0.01) as lock:
            lock.check()
            foreign(self.root)
            self.assertTrue(until(lambda: lock._stolen is not None))
            with self.assertRaises(RunLockError):
                lock.check()
        self.assertEqual(read_lock(self.root)["pid"], 4711)  # the new holder's lock stays


class AdvanceLockTests(LockTestCase):
    def started(self, pico):
        record = framework(pico).start(run_root=self.root)
        return record, os.path.join(record.run_dir, LOCK_NAME)

    def test_advance_holds_the_lock_and_releases_it(self):
        pico = fakes.FakePicoProducer(statuses=[fakes.pending("DY"), fakes.complete("DY", "TT")])
        seen = []
        original = pico.status
        pico.status = lambda *a, **k: seen.append(read_lock(record.run_dir)) or original(*a, **k)
        record, path = self.started(pico)
        framework(pico).advance(record, wait=True)
        self.assertTrue(seen and all(lock and lock["pid"] == os.getpid() for lock in seen))
        self.assertFalse(os.path.exists(path))

    def test_advance_is_refused_while_another_advance_holds_the_run(self):
        pico = fakes.FakePicoProducer(statuses=[fakes.complete("DY", "TT")])
        record, path = self.started(pico)
        foreign(record.run_dir)
        before = text(record.path)
        with self.assertRaises(RunLockError):
            framework(pico).advance(record)
        self.assertEqual(text(record.path), before)  # nothing moved
        self.assertEqual(read_lock(record.run_dir)["pid"], 4711)

    def test_an_error_in_a_stage_releases_the_lock(self):
        pico = fakes.FakePicoProducer(statuses=[fakes.pending("DY")])
        record, path = self.started(pico)
        pico.status = mock.Mock(side_effect=RuntimeError("condor_q timed out"))
        with self.assertRaises(RuntimeError):
            framework(pico).advance(record)
        self.assertFalse(os.path.exists(path))

    def test_take_lock_takes_a_lost_lock_and_says_so(self):
        pico = fakes.FakePicoProducer(statuses=[fakes.complete("DY", "TT")])
        record, path = self.started(pico)
        foreign(record.run_dir, quiet=LOST_AFTER + 30)
        fw = framework(pico)
        record = fw.advance(record, take_lock=True)
        self.assertEqual(record.state, "DONE")
        warnings = [text for kind, text in fw.reporter.messages if kind == "warning"]
        self.assertTrue(any(text.startswith("Took over the advance lock of pid 4711 on lxplus999.cern.ch")
                            for text in warnings))


class CommandLineLockTests(LockTestCase):
    def setUp(self):
        super().setUp()
        spec = importlib.util.spec_from_file_location("taufw_cli", str(checkout.TAUFW_SCRIPT))
        self.cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.cli)
        self.reporter = SilentReporter()
        self.cli.FrameworkReporter = lambda verbosity=0: self.reporter
        pico = fakes.FakePicoProducer(statuses=[fakes.complete("DY", "TT")])
        self.record = framework(pico).start(run_root=self.root)
        real = self.cli.Framework.from_record
        patcher = mock.patch.object(self.cli.Framework, "from_record",
                                    side_effect=lambda r, reporter=None, **kw: real(r, reporter=reporter, pico=pico))
        patcher.start()
        self.addCleanup(patcher.stop)

    def lines(self, kind):
        return [text for k, text in self.reporter.messages if k == kind]

    def test_a_held_run_is_refused_with_one_line(self):
        foreign(self.record.run_dir, quiet=10)
        self.assertEqual(self.cli.main(["advance", self.record.run_dir, "--take-lock"]), 1)
        self.assertEqual(len(self.lines("warning")), 1)
        self.assertTrue(self.lines("warning")[0].startswith("Cannot advance run %s: the run is being advanced on "
                                                            "lxplus999.cern.ch" % (self.record.run_id)))
        self.assertNotIn("--take-lock", " ".join(self.lines("message")))

    def test_a_lost_lock_names_take_lock_and_take_lock_continues(self):
        foreign(self.record.run_dir, quiet=LOST_AFTER + 30)
        self.assertEqual(self.cli.main(["advance", self.record.run_dir]), 1)
        self.assertIn("Take it over with: taufw.py advance %s --take-lock" % (self.record.run_dir),
                      self.lines("message"))
        self.assertEqual(self.cli.main(["advance", self.record.run_dir, "--take-lock"]), 0)
        self.assertEqual(RunRecord.load(self.record.run_dir).state, "DONE")
        self.assertIsNone(read_lock(self.record.run_dir))


if __name__ == "__main__":
    unittest.main()
