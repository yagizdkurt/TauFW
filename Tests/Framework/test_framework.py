"""Framework state machine, run record, recipes and taufw.py, driven by a fake PicoProducer (no ROOT, no batch)."""
import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest import mock

import checkout  # noqa: F401  (must precede TauFW imports)
import fakes
from TauFW.Framework import Framework, Recipe, RecipeError, RunRecord, SilentReporter, StageState
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
        self.assertIn("must be in the order", self.error(
            {"name": "x", "stages": [{"stage": "fit"}, {"stage": "histograms", "eras": [2025], "jet_wps": ["Tight"],
                                                         "ele_wps": ["Tight"]}]}))
        fit = {"stage": "fit", "id": "fit", "inputs": {"shapes": None}}
        self.assertIn("stages[1] (fit): a recipe has at most one fit stage",
                      self.error({"name": "x", "stages": [fit, dict(fit, id="fit2")]}))
        self.assertIn("stages[1] (fit).id: 'fit' is already the id of stages[0]",
                      self.error({"name": "x", "stages": [fit, fit]}))

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
