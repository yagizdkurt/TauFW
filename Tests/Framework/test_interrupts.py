"""Ctrl-C during a step that may submit jobs waits until run.json records it (interrupts.py, Framework)."""
import os
import shutil
import signal
import tempfile
import unittest

import checkout  # noqa: F401  (must precede TauFW imports)
import fakes
from TauFW.Framework import RunRecord, SilentReporter
from TauFW.Framework._internal.runtime.interrupts import deferred_interrupt
from TauFW.Framework._internal.runtime.run_lock import LOCK_NAME
from test_framework import framework


def ctrl_c(times=1):
    for _ in range(times):
        signal.raise_signal(signal.SIGINT)


class DeferredInterruptTests(unittest.TestCase):
    def setUp(self):
        self.reporter = SilentReporter()
        self.before = signal.getsignal(signal.SIGINT)

    def warnings(self):
        return [text for kind, text in self.reporter.messages if kind == "warning"]

    def test_one_ctrl_c_waits_for_the_end_of_the_block(self):
        done = []
        with self.assertRaises(KeyboardInterrupt):
            with deferred_interrupt(self.reporter, "Stage production"):
                ctrl_c()
                done.append("rest of the step")
        self.assertEqual(done, ["rest of the step"])
        self.assertEqual(self.warnings(), ["Stage production: stopping once run.json records this step "
                                           "(Ctrl-C again to force)"])
        self.assertIs(signal.getsignal(signal.SIGINT), self.before)

    def test_a_second_ctrl_c_stops_at_once(self):
        done = []
        with self.assertRaises(KeyboardInterrupt):
            with deferred_interrupt(self.reporter, "Stage production"):
                ctrl_c(2)
                done.append("rest of the step")
        self.assertEqual(done, [])
        self.assertIs(signal.getsignal(signal.SIGINT), self.before)

    def test_without_ctrl_c_nothing_changes(self):
        with deferred_interrupt(self.reporter, "Stage production"):
            pass
        self.assertEqual(self.warnings(), [])


class FrameworkInterruptTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="taufw-test-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def test_a_submission_cut_by_ctrl_c_is_still_recorded(self):
        pico = fakes.FakePicoProducer(statuses=[fakes.pending("DY")])
        submit = pico.submit
        pico.submit = lambda request: ctrl_c() or submit(request)  # Ctrl-C while condor takes the jobs
        fw = framework(pico)
        with self.assertRaises(KeyboardInterrupt):
            fw.start(run_root=self.root)
        (name,) = os.listdir(self.root)
        run_dir = os.path.join(self.root, name)
        self.assertEqual(RunRecord.load(run_dir).stage("production").state, "SUBMITTED")  # no second submission
        self.assertFalse(os.path.exists(os.path.join(run_dir, LOCK_NAME)))
        self.assertIn("Stage production: stopping once run.json records this step (Ctrl-C again to force)",
                      [text for kind, text in fw.reporter.messages if kind == "warning"])

    def test_a_merge_stops_at_once(self):
        pico = fakes.FakePicoProducer(statuses=[fakes.complete("DY", "TT")])
        record = framework(pico).start(run_root=self.root)  # submitted; the next advance checks, then merges
        merged = []
        pico.merge = lambda *a, **k: ctrl_c() or merged.append(a)
        with self.assertRaises(KeyboardInterrupt):
            framework(pico).advance(record)
        self.assertEqual(merged, [])  # not waited for
        self.assertEqual(RunRecord.load(record.run_dir).stage("production").state, "MERGING")
        self.assertFalse(os.path.exists(os.path.join(record.run_dir, LOCK_NAME)))


if __name__ == "__main__":
    unittest.main()
