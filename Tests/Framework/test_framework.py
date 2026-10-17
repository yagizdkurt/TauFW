"""Framework state machine, run record, recipes and taufw.py, driven by a fake PicoProducer (no ROOT, no batch)."""
import importlib.util
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta
from unittest import mock

import checkout  # noqa: F401  (must precede TauFW imports)
import fakes
from TauFW.Framework import (Framework, Recipe, RecipeError, RunRecord, SilentReporter, StageState,
                             RunDirectoryError, EventReporter, FrameworkReporter)
from TauFW.Utilities.Process import EVENTS_ENV, EventReader, EventWriter
from TauFW.Framework.stages import ProductionStage, StageOutcome, decide_next, Action
from TauFW.Framework.stages.production import StatusCounts

RECIPE = {
    "name": "test_mutau",
    "pico": {"config": None},
    "stages": [
        {"stage": "production", "id": "production", "inputs": None, "eras": ["2018"], "channels": ["mutau"],
         "samples": ["DY*", "TT*"], "tag": "t1", "max_tries": 2, "split": {"nfilesperjob": 2}, "merge": {"clean": True}},
    ],
}


class Clock:
    """Deterministic clock: one second per call."""

    def __init__(self):
        self.now = datetime(2026, 10, 13, 12, 0, 0)

    def __call__(self):
        self.now += timedelta(seconds=1)
        return self.now


class NotImplementedStage:
    """A stub stage that cannot run, like a future placeholder stage."""
    name = 'plots'

    def plan(self, spec, context=None):
        from TauFW.Framework.stages import StageNotImplemented
        raise StageNotImplemented(self.name, "no API yet")

    def advance(self, spec, stage_record, reporter, context=None):
        return StageOutcome(StageState.NOT_IMPLEMENTED, "no API yet", "not_implemented")

    def status(self, spec, stage_record):
        return None


def framework(pico, recipe=None, stages=None):
    recipe = Recipe.from_dict(json.loads(json.dumps(recipe or RECIPE)), source="test.yml")
    stages = dict({"production": ProductionStage(pico)}, **(stages or {}))
    return Framework(recipe, stages, reporter=SilentReporter(), sleep=lambda s: None, clock=Clock())


class FrameworkTestCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="taufw-test-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)


class StateMachineTests(FrameworkTestCase):
    def test_start_submits_and_waits(self):
        pico = fakes.FakePicoProducer(statuses=[fakes.pending("DY", "TT")])
        record = framework(pico).start(run_root=self.root)
        stage = record.stage("production")
        self.assertEqual(stage.state, "SUBMITTED")
        self.assertEqual(stage.attempt, 1)
        self.assertEqual(record.state, "WAITING")
        self.assertEqual(pico.names(), ["plan", "submit"])
        self.assertEqual(stage.submissions, [{"jobids": [1001, 1002]}])
        self.assertEqual(stage.request["tag"], "_t1")
        self.assertEqual(stage.request["nfilesperjob"], 2)
        self.assertTrue(os.path.isfile(os.path.join(record.run_dir, "run.json")))
        self.assertEqual(os.path.basename(record.run_dir), "test_mutau_20261013-120001")
        # advance while jobs are pending: one status check, no resubmission
        record = framework(pico).advance(record)
        self.assertEqual(record.stage("production").state, "WAITING")
        self.assertEqual(pico.names(), ["plan", "submit", "status"])

    def test_failed_chunks_resubmit_until_max_tries(self):
        pico = fakes.FakePicoProducer(statuses=[fakes.failed("DY")])
        fw = framework(pico)
        record = fw.start(run_root=self.root)
        record = fw.advance(record)  # attempt 1 failed -> resubmit (attempt 2)
        self.assertEqual(record.stage("production").state, "SUBMITTED")
        self.assertEqual(record.stage("production").attempt, 2)
        record = fw.advance(record)  # attempt 2 failed, max_tries=2 -> FAILED
        stage = record.stage("production")
        self.assertEqual(stage.state, "FAILED")
        self.assertIn("after 2 tries", stage.message)
        self.assertEqual(record.state, "FAILED")
        self.assertEqual(pico.names(), ["plan", "submit", "status", "resubmit", "status"])
        self.assertEqual([h["event"] for h in stage.history], ["submitted", "resubmitted", "failed"])
        record = fw.advance(record)  # terminal: nothing more is called
        self.assertEqual(pico.names(), ["plan", "submit", "status", "resubmit", "status"])

    def test_complete_merges_and_records_artifacts(self):
        pico = fakes.FakePicoProducer(statuses=[fakes.complete("DY", "TT")])
        fw = framework(pico)
        record = fw.advance(fw.start(run_root=self.root))
        stage = record.stage("production")
        self.assertEqual(stage.state, "DONE")
        self.assertEqual(record.state, "DONE")
        self.assertEqual(pico.names(), ["plan", "submit", "status", "merge"])
        self.assertEqual(pico.calls[-1][2:], (True, False))  # merge.clean from the recipe, force default
        self.assertEqual([a["sample"] for a in stage.artifacts], ["DY", "TT"])
        self.assertEqual([h["event"] for h in stage.history], ["submitted", "complete", "merged"])

    def test_invalid_merge_fails_and_refused_merge_waits(self):
        report = fakes.MergeReport(invalid=(("DY", "the merged file is missing or corrupt"),))
        pico = fakes.FakePicoProducer(statuses=[fakes.complete("DY")], merge_report=report)
        record = framework(pico).advance(framework(pico).start(run_root=self.root))
        self.assertEqual(record.stage("production").state, "FAILED")
        self.assertIn("DY: the merged file is missing", record.stage("production").message)
        pico = fakes.FakePicoProducer(statuses=[fakes.complete("DY")], merge_report=fakes.MergeReport(refused=("DY",)))
        record = framework(pico).advance(framework(pico).start(run_root=self.root))
        self.assertEqual(record.stage("production").state, "WAITING")

    def test_no_samples_fails_without_submitting(self):
        pico = fakes.FakePicoProducer(samples=(), statuses=[fakes.Status()])
        record = framework(pico).start(run_root=self.root)
        self.assertEqual(record.stage("production").state, "FAILED")
        self.assertEqual(pico.names(), ["plan"])

    def test_placeholder_stage_does_not_break_production(self):
        pico = fakes.FakePicoProducer(statuses=[fakes.complete("DY", "TT")])
        recipe = dict(RECIPE, stages=RECIPE["stages"] + [{"stage": "plots", "id": "plots",
                                                          "inputs": {"tuples": "production"}, "eras": ["2018"]}])
        fw = framework(pico, recipe, stages={"plots": NotImplementedStage()})
        record = fw.advance(fw.start(run_root=self.root))
        self.assertEqual(record.stage("production").state, "DONE")
        self.assertEqual(record.stage("plots").state, "NOT_IMPLEMENTED")
        self.assertEqual(record.state, "BLOCKED")
        self.assertEqual(len(record.stage("production").artifacts), 2)
        plan = fw.plan()
        self.assertIsNone(plan.stages[1].plan)
        self.assertIn("not implemented", plan.stages[1].note)

    def test_wait_loops_until_done(self):
        pico = fakes.FakePicoProducer(statuses=[fakes.pending("DY"), fakes.pending("DY"), fakes.complete("DY")])
        sleeps = []
        fw = framework(pico)
        fw.sleep = sleeps.append
        record = fw.run(run_root=self.root, wait=True, poll=7)
        self.assertEqual(record.state, "DONE")
        self.assertEqual(sleeps, [7, 7])
        self.assertEqual(pico.names(), ["plan", "submit", "status", "status", "status", "merge"])

    def test_events_follow_the_run(self):
        pico = fakes.FakePicoProducer(statuses=[fakes.pending("DY"), fakes.complete("DY")])
        fw = framework(pico)
        record = fw.run(run_root=self.root, wait=True, poll=7)
        events = fw.reporter.events
        self.assertEqual(events[0], ("run", {"run_id": record.run_id, "run_dir": record.run_dir}))
        self.assertEqual([kind for kind, _ in events],
                         ["run", "stage_step", "stage_state", "run_state",  # start(): submit
                          "run", "stage_step", "stage_state", "run_state", "wait",  # advance(wait=True): pending
                          "stage_step", "stage_state", "stage_step", "stage_state", "run_state"])  # merge, done
        self.assertEqual(events[1], ("stage_step", {"stage": "production", "type": "production", "state": "NEW"}))
        self.assertEqual([fields["state"] for kind, fields in events if kind == "run_state"],
                         ["WAITING", "WAITING", "DONE"])
        self.assertEqual(events[8], ("wait", {"seconds": 7}))
        self.assertEqual(events[-2], ("stage_state", {"stage": "production", "state": "DONE",
                                                      "message": "merged 2 tuple(s)"}))

    def test_stage_exception_is_recorded_and_raised(self):
        pico = fakes.FakePicoProducer(statuses=[fakes.pending("DY")])
        fw = framework(pico)
        record = fw.start(run_root=self.root)
        pico.status = mock.Mock(side_effect=RuntimeError("condor_q timed out"))
        with self.assertRaises(RuntimeError):
            fw.advance(record)
        stage = RunRecord.load(record.run_dir).stage("production")
        self.assertEqual(stage.state, "SUBMITTED")  # unchanged: advance can simply be retried
        self.assertEqual(stage.history[-1]["event"], "error")
        self.assertIn("condor_q timed out", stage.history[-1]["detail"])

    def test_status_is_read_only(self):
        pico = fakes.FakePicoProducer(statuses=[fakes.pending("DY")])
        fw = framework(pico)
        record = fw.start(run_root=self.root)
        before = open(record.path).read()
        summary = fw.status(record)
        self.assertEqual(summary.state, "WAITING")
        self.assertEqual(summary.stages[0].live.npending, 1)
        self.assertEqual(open(record.path).read(), before)
        self.assertNotIn("resubmit", pico.names())


class RecoveryTests(FrameworkTestCase):
    def resume(self, run_dir, pico):
        record = RunRecord.load(run_dir)
        fw = Framework.from_record(record, pico=pico, reporter=SilentReporter())
        fw.clock = Clock()
        return fw.advance(record)

    def test_reload_pending_jobs_does_not_submit_again(self):
        original = fakes.FakePicoProducer(statuses=[fakes.pending("DY", "TT")])
        record = framework(original).start(run_root=self.root)
        saved = RunRecord.load(record.run_dir).stage("production")
        for _ in range(2):
            # Each continuation has no in-memory state from the previous Framework or API.
            fresh = fakes.FakePicoProducer(statuses=[fakes.pending("DY", "TT")])
            record = self.resume(record.run_dir, fresh)
            self.assertEqual(fresh.names(), ["status"])
            self.assertEqual(record.state, "WAITING")
            stage = RunRecord.load(record.run_dir).stage("production")
            self.assertEqual(stage.state, "WAITING")
            self.assertEqual(stage.attempt, 1)
            self.assertEqual(stage.submissions, saved.submissions)
            self.assertEqual(stage.request, saved.request)
        self.assertEqual(original.names(), ["plan", "submit"])

    def test_reload_preserves_retry_count_and_stops_at_limit(self):
        original = fakes.FakePicoProducer(statuses=[fakes.pending("DY", "TT")])
        record = framework(original).start(run_root=self.root)
        submissions = RunRecord.load(record.run_dir).stage("production").submissions
        retry = fakes.FakePicoProducer(statuses=[fakes.failed("DY")], jobid=1002)
        record = self.resume(record.run_dir, retry)
        self.assertEqual(retry.names(), ["status", "resubmit"])
        stage = RunRecord.load(record.run_dir).stage("production")
        self.assertEqual((stage.state, stage.attempt), ("SUBMITTED", 2))
        self.assertEqual(stage.submissions, submissions + [{"jobids": [1003, 1004]}])

        exhausted = fakes.FakePicoProducer(statuses=[fakes.failed("DY")])
        record = self.resume(record.run_dir, exhausted)
        self.assertEqual(exhausted.names(), ["status"])
        stage = RunRecord.load(record.run_dir).stage("production")
        self.assertEqual((record.state, stage.state, stage.attempt), ("FAILED", "FAILED", 2))
        self.assertIn("after 2 tries", stage.message)
        self.assertEqual([event["event"] for event in stage.history], ["submitted", "resubmitted", "failed"])
        self.assertEqual(stage.submissions, submissions + [{"jobids": [1003, 1004]}])

    def test_reload_completed_run_performs_no_api_work(self):
        original = fakes.FakePicoProducer(statuses=[fakes.complete("DY", "TT")])
        fw = framework(original)
        record = fw.advance(fw.start(run_root=self.root))
        saved = RunRecord.load(record.run_dir).to_dict()
        self.assertEqual(record.state, "DONE")
        fresh = fakes.FakePicoProducer()
        record = self.resume(record.run_dir, fresh)
        self.assertEqual(record.state, "DONE")
        self.assertEqual(fresh.calls, [])
        self.assertEqual(RunRecord.load(record.run_dir).to_dict()["stages"], saved["stages"])


class ProductionTuplesTests(FrameworkTestCase):
    """The tuples go to the production stage's directory in the run, and their pattern is on the artifacts."""

    def test_tuples_in_the_stage_directory(self):
        pico = fakes.FakePicoProducer(statuses=[fakes.complete("DY", "TT")])
        fw = framework(pico)
        record = fw.advance(fw.start(run_root=self.root))
        stage_dir = os.path.join(record.run_dir, "stages", "production")
        requests = [call[1] for call in pico.calls]
        self.assertTrue(all(request["tupledir"] == stage_dir for request in requests))  # plan, submit, ...
        pattern = os.path.join(stage_dir, "$ERA", "$GROUP")
        stage = record.stage("production")
        self.assertEqual([(a["sample"], a["pattern"]) for a in stage.artifacts], [("DY", pattern), ("TT", pattern)])
        with open(os.path.join(stage_dir, "manifest.json")) as stream:
            self.assertEqual([a["pattern"] for a in json.load(stream)["artifacts"]], [pattern, pattern])
        self.assertNotIn("tupledir", stage.request)  # run.json keeps the recipe's request, as before

    def test_plan_and_status_without_a_run(self):
        pico = fakes.FakePicoProducer()
        fw = framework(pico)
        plan = fw.plan()
        self.assertNotIn("tupledir", pico.calls[0][1])  # no run yet: nothing to put there
        stage = fw.stages["production"]
        self.assertEqual(stage.planned_artifacts(fw.recipe.stage("production").spec, plan.stages[0].plan),
                         ({"pattern": os.path.join("<run_dir>", "stages", "production", "$ERA", "$GROUP")},))
        self.assertNotIn("tupledir", stage.request(fw.recipe.stage("production").spec))  # status, run_local

    def test_later_stages_see_the_planned_pattern(self):
        seen = []

        class Reader(NotImplementedStage):
            name = 'python'

            def plan(self, spec, context=None):
                seen.append(context.artifacts("production"))
                return super().plan(spec, context)

        recipe = dict(RECIPE, stages=RECIPE["stages"] + [
            {"stage": "python", "id": "look", "inputs": {"tuples": "production"}, "file": "look.py"}])
        framework(fakes.FakePicoProducer(), recipe, stages={"look": Reader()}).plan()
        self.assertEqual(seen, [({"pattern": os.path.join("<run_dir>", "stages", "production", "$ERA",
                                                          "$GROUP")},)])


class RunRootTests(FrameworkTestCase):
    def runs(self, directory):
        return [name for name in os.listdir(directory) if name.startswith("test_mutau_")]

    def test_recipe_run_root_and_precedence(self):
        recipe_root = os.path.join(self.root, "recipe_runs")
        recipe = dict(RECIPE, run_root=recipe_root)
        record = framework(fakes.FakePicoProducer(statuses=[fakes.pending("DY")]), recipe).start()
        self.assertEqual(os.path.dirname(record.run_dir), recipe_root)  # the recipe's run_root
        self.assertEqual(record.recipe["run_root"], recipe_root)  # run.json keeps it as written
        given = os.path.join(self.root, "given")
        record = framework(fakes.FakePicoProducer(statuses=[fakes.pending("DY")]), recipe).start(run_root=given)
        self.assertEqual(os.path.dirname(record.run_dir), given)  # start(run_root) takes precedence
        self.assertEqual(len(self.runs(recipe_root)), 1)
        here = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, here)
        record = framework(fakes.FakePicoProducer(statuses=[fakes.pending("DY")])).start()  # neither: taufw_runs/
        self.assertEqual(os.path.dirname(record.run_dir), os.path.join(os.path.realpath(self.root), "taufw_runs"))

    def test_write_check_leaves_nothing_behind(self):
        root = os.path.join(self.root, "a", "b")  # made by the run, below the directory that is tried
        record = framework(fakes.FakePicoProducer(statuses=[fakes.pending("DY")])).start(run_root=root)
        self.assertEqual(os.listdir(self.root), ["a"])
        for directory in (self.root, root, record.run_dir):
            self.assertFalse([n for n in os.listdir(directory) if n.startswith(".taufw_write_test")])

    def test_run_root_that_cannot_be_written_stops_before_anything(self):
        pico = fakes.FakePicoProducer(statuses=[fakes.pending("DY")])
        root = os.path.join(self.root, "runs")
        with mock.patch("TauFW.Framework.framework.open", side_effect=PermissionError("Permission denied"),
                        create=True):
            with self.assertRaises(RunDirectoryError) as context:
                framework(pico).start(run_root=root)
        self.assertIn("cannot write in the run root %s: Permission denied" % (root), str(context.exception))
        self.assertIn("kinit; aklog", str(context.exception))
        self.assertFalse(os.path.exists(root))  # no run directory, no run.json
        self.assertEqual(pico.calls, [])  # nothing submitted

    def test_advance_tries_the_run_directory_first(self):
        pico = fakes.FakePicoProducer(statuses=[fakes.pending("DY"), fakes.complete("DY", "TT")])
        fw = framework(pico)
        record = fw.start(run_root=self.root)
        with open(record.path, "rb") as stream:
            before = stream.read()
        calls = len(pico.calls)
        with mock.patch("TauFW.Framework.framework.open", side_effect=PermissionError("Permission denied"),
                        create=True):
            with self.assertRaises(RunDirectoryError) as context:
                fw.advance(record)
        self.assertIn("cannot write in the run directory %s" % (record.run_dir), str(context.exception))
        with open(record.path, "rb") as stream:
            self.assertEqual(stream.read(), before)  # nothing moved
        self.assertEqual(len(pico.calls), calls)


class DecisionTests(unittest.TestCase):
    def test_decide_next_truth_table(self):
        cases = [
            # nsamples, npending, nfailed, complete, attempt, max_tries -> action
            ((0, 0, 0, False), 1, 3, Action.FAIL),
            ((2, 0, 0, True), 1, 3, Action.MERGE),
            ((2, 3, 0, False), 1, 3, Action.WAIT),
            ((2, 3, 2, False), 3, 3, Action.WAIT),     # still running: wait before giving up
            ((2, 0, 2, False), 1, 3, Action.RESUBMIT),
            ((2, 0, 2, False), 2, 3, Action.RESUBMIT),
            ((2, 0, 2, False), 3, 3, Action.FAIL),
            ((2, 0, 0, False), 1, 3, Action.WAIT),     # nothing to judge yet
        ]
        for counts, attempt, max_tries, expected in cases:
            action, reason = decide_next(StatusCounts(*counts), attempt, max_tries)
            self.assertEqual(action, expected, (counts, attempt, max_tries, reason))
            self.assertTrue(reason)

    def test_stage_states(self):
        self.assertTrue(StageState.DONE.terminal and StageState.FAILED.terminal and StageState.NOT_IMPLEMENTED.terminal)
        self.assertTrue(StageState.SUBMITTED.waiting and StageState.WAITING.waiting)
        self.assertFalse(StageState.MERGING.waiting or StageState.MERGING.terminal)


class RunRecordTests(FrameworkTestCase):
    def test_round_trip(self):
        pico = fakes.FakePicoProducer(statuses=[fakes.complete("DY", "TT")])
        fw = framework(pico)
        record = fw.advance(fw.start(run_root=self.root))
        loaded = RunRecord.load(record.run_dir)
        self.assertEqual(loaded.to_dict(), record.to_dict())
        self.assertEqual(loaded.run_dir, record.run_dir)
        self.assertEqual(Recipe.from_dict(loaded.recipe).to_dict(), Recipe.from_dict(RECIPE).to_dict())
        data = json.load(open(record.path))
        self.assertEqual(list(data), ["schema", "run_id", "created", "updated", "recipe", "pico_config", "bundle",
                                      "stages"])

    def test_save_is_crash_safe(self):
        pico = fakes.FakePicoProducer(statuses=[fakes.pending("DY")])
        record = framework(pico).start(run_root=self.root)
        before = open(record.path).read()
        record.stage("production").state = "DONE"
        with mock.patch("os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                record.save()
        self.assertEqual(open(record.path).read(), before)  # old complete file is intact

    def test_unique_run_directories(self):
        recipe = Recipe.from_dict(RECIPE)
        now = datetime(2026, 10, 13, 12, 0, 0)
        first = RunRecord.create(recipe, self.root, now=now)
        os.makedirs(first.run_dir)
        second = RunRecord.create(recipe, self.root, now=now)
        self.assertEqual(os.path.basename(second.run_dir), os.path.basename(first.run_dir) + "-2")

    def test_unknown_schema(self):
        with self.assertRaises(ValueError):
            RunRecord.from_dict({"schema": 99})
        with self.assertRaisesRegex(ValueError, "schema 1 .expected 3"):  # before ids, inputs and stages/<id>
            RunRecord.from_dict({"schema": 1})
        with self.assertRaisesRegex(ValueError, "schema 2 .expected 3"):  # before sources (R4)
            RunRecord.from_dict({"schema": 2})


class RecipeTests(FrameworkTestCase):
    def error(self, data):
        with self.assertRaises(RecipeError) as context:
            Recipe.from_dict(data, source="r.yml")
        return str(context.exception)

    def test_valid_recipe(self):
        recipe = Recipe.from_dict(RECIPE)
        spec = recipe.stage("production").spec
        self.assertEqual(spec.eras, ("2018",))
        self.assertEqual(spec.split.nfilesperjob, 2)
        self.assertTrue(spec.merge.clean)
        self.assertEqual(spec.max_tries, 2)
        self.assertEqual(Recipe.from_dict(recipe.to_dict()).to_dict(), recipe.to_dict())

    def test_errors_name_the_key(self):
        self.assertIn("unknown key 'stagez'", self.error({"name": "x", "stagez": []}))
        self.assertIn("stages: must be a non-empty list", self.error({"name": "x", "stages": []}))
        self.assertIn("unknown stage 'trigger'", self.error({"name": "x", "stages": [{"stage": "trigger"}]}))
        self.assertIn("unknown option 'samplez'", self.error(
            {"name": "x", "stages": [{"stage": "production", "eras": ["2018"], "channels": ["mutau"], "samplez": []}]}))
        self.assertIn("missing required option 'channels'", self.error(
            {"name": "x", "stages": [{"stage": "production", "eras": ["2018"]}]}))
        self.assertIn("stages[0] (production).merge: unknown option 'cleanup'", self.error(
            {"name": "x", "stages": [{"stage": "production", "eras": ["2018"], "channels": ["mutau"],
                                      "merge": {"cleanup": True}}]}))
        self.assertIn("'max_tries' must be at least 1", self.error(
            {"name": "x", "stages": [{"stage": "production", "eras": ["2018"], "channels": ["mutau"], "max_tries": 0}]}))
        self.assertIn("name: must be a word", self.error({"name": "a b", "stages": [{"stage": "fit"}]}))
        self.assertIn("unknown key 'cfg'", self.error({"name": "x", "pico": {"cfg": 1}, "stages": [{"stage": "fit"}]}))

    def test_stage_order_and_duplicates(self):
        histograms = {"stage": "histograms", "id": "histograms", "inputs": {"tuples": None}, "eras": [2025],
                      "jet_wps": ["Tight"], "ele_wps": ["Tight"]}
        fit = {"stage": "fit", "id": "fit", "inputs": {"shapes": "histograms"}}
        # R4: no fixed order; a fit above the histograms it reads is an input problem
        self.assertEqual(self.error({"name": "x", "stages": [fit, histograms]}),
                         "r.yml: stages[0] (fit).inputs.shapes: stage 'histograms' comes after this one; an input "
                         "names an earlier stage")
        null_fit = {"stage": "fit", "id": "fit", "inputs": {"shapes": None}}
        recipe = Recipe.from_dict({"name": "x", "stages": [null_fit, dict(null_fit, id="fit2")]})  # repeated stage
        self.assertEqual([s.id for s in recipe.stages], ["fit", "fit2"])
        self.assertIn("stages[1] (fit).id: 'fit' is already the id of stages[0]",
                      self.error({"name": "x", "stages": [null_fit, null_fit]}))
        production = RECIPE["stages"][0]
        self.assertEqual(self.error({"name": "x", "stages": [production, dict(production, id="production2")]}),
                         "r.yml: stages[1] (production): a recipe has at most one production stage (put several "
                         "eras and channels in its lists, or use separate recipes)")

    def test_stages_in_any_order_and_repeated(self):
        """R4: histograms A, fit A, histograms B, fit B; plots after the fit; production anywhere."""
        histograms = {"stage": "histograms", "inputs": {"tuples": None}, "eras": [2025], "ele_wps": ["Tight"]}
        recipe = Recipe.from_dict({"name": "x", "stages": [
            dict(histograms, id="hist_vt", jet_wps=["VTight"]),
            {"stage": "fit", "id": "fit_vt", "inputs": {"shapes": "hist_vt"}},
            dict(histograms, id="hist_t", jet_wps=["Tight"]),
            {"stage": "fit", "id": "fit_t", "inputs": {"shapes": "hist_t"}},
            {"stage": "plots", "id": "plots", "inputs": {"tuples": None}, "eras": [2025]},
            dict(RECIPE["stages"][0], id="production")]})
        self.assertEqual([s.stage for s in recipe.stages],
                         ["histograms", "fit", "histograms", "fit", "plots", "production"])
        self.assertEqual(recipe.stage("fit_t").connections, {"shapes": "hist_t"})

    def test_load_bundle_example_and_relative_config(self):
        example = os.path.join(checkout.REPO, "Analyses", "example_mutau")
        recipe = Recipe.load(example)  # a bundle directory: its recipe.yml
        self.assertEqual([s.stage for s in recipe.stages], ["production", "plots"])
        self.assertIsNone(recipe.pico_config)
        self.assertEqual(recipe.bundle_dir, example)
        self.assertEqual(recipe.source, "example_mutau/recipe.yml")
        path = os.path.join(self.root, "r.json")
        with open(path, "w") as stream:
            json.dump(dict(RECIPE, pico={"config": "cfg/config.json"}), stream)
        loaded = Recipe.load(path)
        self.assertEqual(loaded.pico_config, "cfg/config.json")  # as written (saved in run.json)
        self.assertEqual(loaded.pico_config_path, os.path.join(self.root, "cfg", "config.json"))
        with self.assertRaises(RecipeError):
            Recipe.load(os.path.join(self.root, "recipe.txt"))


class ReporterTests(FrameworkTestCase):
    def setUp(self):
        super().setUp()
        self.path = os.path.join(self.root, "events.jsonl")

    def test_event_reporter_passes_everything_on_and_writes_events(self):
        inner = SilentReporter()
        reporter = EventReporter(inner, EventWriter(self.path))
        reporter.header("Stage plots (NEW)")
        reporter.message("[plots] 1/2 plots ...")
        reporter.warning("not ready")
        self.assertEqual(reporter.table(["a", "b"], [(1, None)]), [[1, None]])
        reporter.raw(">>> a PicoProducer line")
        reporter.pico_reporter("production").warning("no proxy")
        reporter.event("progress", stage="plots", index=1, total=2, label="plots", status="run")
        self.assertIs(reporter.messages, inner.messages)
        self.assertEqual([kind for kind, _ in inner.messages],
                         ["header", "message", "warning", "table", "message", "warning"])  # raw: a message
        self.assertEqual(inner.events, [("progress", dict(stage="plots", index=1, total=2, label="plots",
                                                          status="run"))])
        events = [{k: v for k, v in e.items() if k != "t"} for e in EventReader(self.path).read()]
        self.assertEqual(events, [
            {"kind": "header", "text": "Stage plots (NEW)"},
            {"kind": "message", "text": "[plots] 1/2 plots ..."},
            {"kind": "warning", "text": "not ready"},
            {"kind": "table", "headers": ["a", "b"], "rows": [["1", "None"]]},
            {"kind": "warning", "text": "[production] no proxy"},  # raw lines stay in the output only
            {"kind": "progress", "stage": "plots", "index": 1, "total": 2, "label": "plots", "status": "run"}])

    def test_terminal_output_and_run_log_do_not_change(self):
        def report(reporter):
            reporter.attach_log(os.path.join(self.root, "%d.log" % (len(os.listdir(self.root)))))
            reporter.header("TauFW run x")
            reporter.message("Run directory: here")
            reporter.warning("careful")
            reporter.table(["stage", "state"], [("plots", "DONE")])
            reporter.raw(">>> raw")
            reporter.event("run_state", run_id="x", state="DONE")
        outputs = []
        for wrap in (lambda r: r, lambda r: EventReporter(r, EventWriter(self.path))):
            stream = io.StringIO()
            with redirect_stdout(stream), redirect_stderr(stream):  # warnings go to stderr
                report(wrap(FrameworkReporter()))
            outputs.append(stream.getvalue())
        self.assertIn("careful", outputs[0])
        self.assertEqual(outputs[0], outputs[1])
        logs = sorted(f for f in os.listdir(self.root) if f.endswith(".log"))
        with open(os.path.join(self.root, logs[0])) as first, open(os.path.join(self.root, logs[1])) as second:
            self.assertEqual(first.read(), second.read())
        self.assertEqual(len(EventReader(self.path).read()), 5)


class CommandLineTests(FrameworkTestCase):
    def setUp(self):
        super().setUp()
        spec = importlib.util.spec_from_file_location("taufw_cli", str(checkout.TAUFW_SCRIPT))
        self.cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.cli)
        self.cli.FrameworkReporter = lambda verbosity=0: SilentReporter()

    def test_start_and_advance_map_to_the_framework(self):
        pico = fakes.FakePicoProducer(statuses=[fakes.pending("DY"), fakes.complete("DY", "TT")])
        recipe = os.path.join(self.root, "r.json")
        with open(recipe, "w") as stream:
            json.dump(RECIPE, stream)
        real = Framework.from_recipe
        with mock.patch.object(self.cli.Framework, "from_recipe",
                               side_effect=lambda r, reporter=None, fake=pico, **kw: real(r, reporter=reporter, pico=fake)):
            self.assertEqual(self.cli.main(["start", recipe, "--run-root", self.root]), 0)
            runs = os.listdir(self.root)
            run_dir = os.path.join(self.root, [r for r in runs if r.startswith("test_mutau_")][0])
            self.assertEqual(RunRecord.load(run_dir).state, "WAITING")
            self.assertEqual(self.cli.main(["advance", run_dir]), 0)  # pending
            self.assertEqual(self.cli.main(["advance", run_dir, "--wait", "--poll", "0"]), 0)
            self.assertEqual(RunRecord.load(run_dir).state, "DONE")
            self.assertEqual(self.cli.main(["status", run_dir]), 0)
            self.assertEqual(self.cli.main(["plan", recipe]), 0)

    def test_check_plan_and_start_show_the_run_root(self):
        reporter = SilentReporter()
        self.cli.FrameworkReporter = lambda verbosity=0: reporter
        pico = fakes.FakePicoProducer(statuses=[fakes.pending("DY")])
        recipe = os.path.join(self.root, "r.json")
        with open(recipe, "w") as stream:
            json.dump(RECIPE, stream)  # no run_root
        real = Framework.from_recipe
        warning = ("run_root: not set: the runs go to taufw_runs/ in the directory taufw.py is started "
                   "from, and production stage 'production' writes its merged tuples into the run directory (often "
                   "tens of GB). On lxplus that is your AFS space: the home directory holds only a few GB, and a "
                   "full quota stops the run midway. Set run_root: <absolute directory with enough space> in the "
                   "recipe (e.g. under /afs/cern.ch/work/), or start with --run-root")
        with mock.patch.object(self.cli.Framework, "from_recipe",
                               side_effect=lambda r, reporter=None, fake=pico, **kw: real(r, reporter=reporter, pico=fake)):
            self.assertEqual(self.cli.main(["check", recipe]), 0)  # a warning is not a problem
            self.assertEqual([t for k, t in reporter.messages if k == "warning"], [warning])
            reporter.messages.clear()
            self.assertEqual(self.cli.main(["plan", recipe]), 0)
            self.assertIn(warning, [t for k, t in reporter.messages if k == "warning"])
            self.assertIn("Run root: %s (default: no run_root in the recipe)" % (os.path.abspath("taufw_runs")),
                          [t for k, t in reporter.messages if k == "message"])
            reporter.messages.clear()
            self.assertEqual(self.cli.main(["start", recipe, "--run-root", self.root]), 0)
            self.assertNotIn(warning, [t for k, t in reporter.messages if k == "warning"])  # --run-root chose
            self.assertIn("Run root: %s (--run-root)" % (self.root), [t for k, t in reporter.messages])
            with open(recipe, "w") as stream:
                json.dump(dict(RECIPE, run_root=os.path.join(self.root, "runs")), stream)
            reporter.messages.clear()
            self.assertEqual(self.cli.main(["check", recipe]), 0)
            self.assertEqual([t for k, t in reporter.messages if k == "warning"], [])
            self.assertEqual(self.cli.main(["plan", recipe]), 0)
            self.assertIn("Run root: %s (recipe)" % (os.path.join(self.root, "runs")),
                          [t for k, t in reporter.messages if k == "message"])
            with mock.patch("TauFW.Framework.framework.open", side_effect=PermissionError("Permission denied"),
                            create=True):
                self.assertEqual(self.cli.main(["start", recipe]), 1)  # the reason, no traceback
            self.assertIn("cannot write in the run root", [t for k, t in reporter.messages if k == "warning"][-1])

    def test_events_from_the_environment(self):
        pico = fakes.FakePicoProducer(statuses=[fakes.pending("DY")])
        recipe = os.path.join(self.root, "r.json")
        with open(recipe, "w") as stream:
            json.dump(RECIPE, stream)
        path = os.path.join(self.root, "events.jsonl")
        real = Framework.from_recipe
        seen = []
        with mock.patch.object(self.cli.Framework, "from_recipe",
                               side_effect=lambda r, reporter=None, fake=pico, **kw: real(r, reporter=reporter, pico=fake)), \
             mock.patch.dict(os.environ, {EVENTS_ENV: path}):
            pico.submit = mock.Mock(side_effect=lambda *a, **k: seen.append(os.environ.get(EVENTS_ENV)) or
                                    fakes.FakePicoProducer.submit(pico, *a, **k))
            self.assertEqual(self.cli.main(["start", recipe, "--run-root", self.root]), 0)
            self.assertNotIn(EVENTS_ENV, os.environ)  # removed before any stage runs a command
        self.assertEqual(seen, [None])
        events = EventReader(path).read()
        kinds = [event["kind"] for event in events]
        self.assertEqual(kinds[kinds.index("run"):kinds.index("run") + 3], ["run", "header", "stage_step"])
        self.assertIn({"kind": "message", "text": "Run root: %s (--run-root)" % (self.root)},
                      [{k: v for k, v in e.items() if k != "t"} for e in events])
        self.assertEqual([e["state"] for e in events if e["kind"] == "run_state"], ["WAITING"])

    def test_error_event_and_nothing_without_the_variable(self):
        path = os.path.join(self.root, "events.jsonl")
        invalid = os.path.join(self.root, "invalid.json")
        with open(invalid, "w") as stream:
            json.dump({"name": "invalid"}, stream)  # no stages
        with mock.patch.dict(os.environ, {EVENTS_ENV: path}):
            self.assertEqual(self.cli.main(["plan", invalid]), 1)
        errors = [event for event in EventReader(path).read() if event["kind"] == "error"]
        self.assertEqual(len(errors), 1)
        self.assertIn("stages", errors[0]["message"])
        os.remove(path)
        with mock.patch.dict(os.environ):
            os.environ.pop(EVENTS_ENV, None)
            self.assertEqual(self.cli.main(["plan", invalid]), 1)
        self.assertFalse(os.path.exists(path))

    def test_parser(self):
        parser = self.cli.build_parser()
        args = parser.parse_args(["start", "r.yml", "--run-root", "runs", "--wait", "--poll", "30"])
        self.assertEqual((args.command, args.recipe, args.run_root, args.wait, args.poll), ("start", "r.yml", "runs", True, 30))
        args = parser.parse_args(["plan", "r.yml", "--local", "-m", "50"])
        self.assertEqual((args.local, args.maxevts), (True, 50))
        args = parser.parse_args(["advance", "runs/x"])
        self.assertEqual((args.run_dir, args.wait, args.poll), ("runs/x", False, 600))
        with self.assertRaises(SystemExit):
            parser.parse_args([])


if __name__ == "__main__":
    unittest.main()
