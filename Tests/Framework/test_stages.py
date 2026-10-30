"""Local stages (controlhists, controlplots, shapes, fit) and the stage context, driven by fake module APIs (no ROOT, no scripts)."""
import importlib.util
import json
import os
import shutil
import tempfile
import unittest

import checkout  # noqa: F401  (must precede TauFW imports)
import fakes
import hashlib
from TauFW.Framework import Framework, Recipe, RecipeError, RunRecord, SilentReporter
from TauFW.Framework._internal.recipes.bundle import resolve
from TauFW.Framework._internal.runtime.plan_text import command_line, inputs_line, inputs_short
from TauFW.Framework.stages import (ProductionStage, ControlHistsStage, ControlPlotsStage, ShapesStage, FitStage,
                                    StageContext,
                                    PreflightError)
from test_framework import Clock

PRODUCTION = {"stage": "production", "id": "production", "inputs": None, "eras": ["2025"], "channels": ["mutau"],
              "samples": ["DY*"]}
HISTS = {"stage": "controlhists", "id": "hists", "inputs": {"tuples": fakes.EXTERNAL}, "eras": [2025], "configs": ["mutau", "mumu"],
         "variables": ["m_vis"]}
SHAPES = {"stage": "shapes", "id": "shapes", "inputs": {"tuples": fakes.EXTERNAL}, "eras": [2025],
              "jet_wps": ["VTight", "Tight"], "ele_wps": ["Tight"]}
PLOTS = {"stage": "controlplots", "id": "plots", "inputs": {"hists": "hists"}, "pdf": True}
FIT = {"stage": "fit", "id": "fit", "inputs": {"shapes": "shapes"}, "steps": ["fit", "corrections"]}
TT, MM = "Configs/Fitter/tes_id/config_coarse_TT.yml", "Configs/Fitter/tes_id/FitSetup_mumu.yml"  # templates (CL §22)


def recipe(*stages):
    return Recipe.from_dict({"name": "tes", "pico": {"config": None}, "stages": list(stages)}, source="t.yml")


def connected(stage, **inputs):
    """The stage with its input slots connected to these stage ids."""
    return dict(stage, inputs=inputs)


PIPELINE = (PRODUCTION, connected(HISTS, tuples="production"), connected(SHAPES, tuples="production"),
            connected(FIT, shapes="shapes"))


class LocalStageTestCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="taufw-test-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.pico = fakes.FakePicoProducer(samples=("DY",), statuses=[fakes.complete("DY")])
        self.histogrammer = fakes.FakeHistogrammer()
        self.plotter = fakes.FakePlotter()
        self.fitter = fakes.FakeFitter()
        self.tes_shapes = fakes.FakeTESShapes()
        self.reporter = SilentReporter()

    def framework(self, *stages):
        built = {"production": ProductionStage(self.pico), "controlhists": ControlHistsStage(self.histogrammer),
                 "controlplots": ControlPlotsStage(self.plotter),
                 "shapes": ShapesStage(self.tes_shapes), "fit": FitStage(self.fitter)}
        stages = recipe(*stages)  # the stage objects by type: a repeated stage shares its module API
        return Framework(stages, {s.id: built[s.stage] for s in stages.stages}, reporter=self.reporter,
                         sleep=lambda s: None, clock=Clock())

    def warnings(self):
        return [text for kind, text in self.reporter.messages if kind == "warning"]


class PipelineTests(LocalStageTestCase):
    def test_whole_pipeline_runs_after_production(self):
        fw = self.framework(*PIPELINE)
        record = fw.start(run_root=self.root)
        self.assertEqual(record.state, "WAITING")
        self.assertEqual(self.histogrammer.calls, [])  # nothing local runs before production is DONE
        record = fw.advance(record)
        self.assertEqual(record.state, "DONE")
        self.assertEqual([record.stage(s).state for s in ("hists", "shapes", "fit")], ["DONE"] * 3)
        # each stage logs to <run_dir>/logs/<stage id>, and gets a manifest in <run_dir>/stages/<stage id> when DONE
        logs = os.path.join(record.run_dir, "logs")
        self.assertEqual(self.histogrammer.logdirs, [os.path.join(logs, "hists")])
        # the Framework decides where a stage writes: its scripts run in <run_dir>/stages/<stage id>
        self.assertEqual(self.histogrammer.call("make")[0]["outdir"], os.path.join(record.run_dir, "stages", "hists"))
        self.assertEqual(self.tes_shapes.logdirs, [os.path.join(logs, "shapes")])
        self.assertEqual(self.fitter.logdirs, [os.path.join(logs, "fit")])
        self.assertEqual(sorted(os.listdir(os.path.join(record.run_dir, "stages"))),
                         ["fit", "hists", "production", "shapes"])
        with open(os.path.join(record.run_dir, "stages", "shapes", "manifest.json")) as stream:
            manifest = json.load(stream)
        self.assertEqual({key: manifest[key] for key in ("manifest", "run_id", "stage_id", "stage", "inputs",
                                                         "sources", "stage_dir")},
                         {"manifest": 2, "run_id": record.run_id, "stage_id": "shapes", "stage": "shapes",
                          "inputs": {"tuples": "production"}, "sources": {},
                          "stage_dir": os.path.join(os.path.abspath(record.run_dir), "stages", "shapes")})
        self.assertEqual(manifest["artifacts"], record.stage("shapes").artifacts)
        production_dir = os.path.join(record.run_dir, "stages", "production")  # the tuples, below <era>/<group>
        self.assertEqual(sorted(os.listdir(production_dir)), ["2018", "manifest.json"])
        dy = os.path.join(production_dir, "2018", "DY", "DY_mutau.root")
        # hists and shapes read the production stage's tuples, through the pattern on its artifacts
        pattern = os.path.join(production_dir, "$ERA", "$GROUP")
        self.assertEqual(self.histogrammer.call("make")[0]["tuples"], pattern)
        self.assertNotIn("pico_config", self.histogrammer.call("make")[0])  # CL §37
        self.assertEqual(self.tes_shapes.call("make_shapes")[0]["tuples"], pattern)
        self.assertEqual(record.stage("hists").last_status["tuples"], pattern)
        # the shapes stage records the production tuples as inputs, and its shape files as artifacts
        histograms = record.stage("shapes")
        self.assertEqual(histograms.last_status["inputs"], [dy])
        self.assertEqual(len(histograms.artifacts), 4)  # 2 jet WPs x 1 ele WP x 2 configs
        self.assertEqual(histograms.request["eras"], ["2025"])
        # the fit points come from the shapes of both configs
        fit_request = self.fitter.call("fit")[0]
        self.assertIs(self.fitter.call("preflight_fit")[1], False)  # the shapes come from the shapes stage
        self.assertEqual(fit_request["points"], (("2025", "VTight", "Tight"), ("2025", "Tight", "Tight")))
        self.assertEqual(fit_request["steps"], ("fit", "corrections"))
        # the Framework gives each stage its directory, and the fit the directory of each point's shapes
        stages = os.path.join(record.run_dir, "stages")
        self.assertEqual(self.tes_shapes.call("make_shapes")[0]["outdir"], os.path.join(stages, "shapes"))
        self.assertEqual(fit_request["outdir"], os.path.join(stages, "fit"))
        self.assertEqual(fit_request["shapes_dirs"], (("2025", "VTight", "Tight", "/fit"),
                                                      ("2025", "Tight", "Tight", "/fit")))
        self.assertEqual(len(record.stage("fit").last_status["commands"]), 2)
        # status shows the fitted values, read from run.json
        live = fw.status(record).stages[3].live
        self.assertEqual([(v["jet_wp"], v["poi"], v["value"]) for v in live],
                         [("VTight", "tes", 0.98), ("Tight", "tes", 0.98)])

    def test_repeated_stages_run_in_their_own_directories(self):
        """R4: two shapes stages and two fits (each fit reads its own shapes), two hists, in any order."""
        hist_vt = dict(SHAPES, id="hist_vt", jet_wps=["VTight"])
        hist_t = dict(SHAPES, id="hist_t", jet_wps=["Tight"])
        stages = (hist_vt, connected(dict(FIT, id="fit_vt"), shapes="hist_vt"), hist_t,
                  connected(dict(FIT, id="fit_t"), shapes="hist_t"),
                  dict(HISTS, id="hists_mvis"), dict(HISTS, id="hists_pt", variables=["pt_1"]))
        record = self.framework(*stages).start(run_root=self.root)
        self.assertEqual(record.state, "DONE")
        directories = os.path.join(record.run_dir, "stages")
        self.assertEqual(sorted(os.listdir(directories)), ["fit_t", "fit_vt", "hist_t", "hist_vt", "hists_mvis",
                                                           "hists_pt"])
        self.assertEqual([request["outdir"] for request, in [c[1:] for c in self.fitter.calls if c[0] == "fit"]],
                         [os.path.join(directories, "fit_vt"), os.path.join(directories, "fit_t")])
        self.assertEqual([request["points"] for request, in [c[1:] for c in self.fitter.calls if c[0] == "fit"]],
                         [(("2025", "VTight", "Tight"),), (("2025", "Tight", "Tight"),)])
        self.assertEqual([request["variables"] for request, in [c[1:] for c in self.histogrammer.calls if c[0] == "make"]],
                         [["m_vis"], ["pt_1"]])
        for stage_id in ("fit_vt", "fit_t", "hists_mvis", "hists_pt"):
            self.assertTrue(os.path.isfile(os.path.join(directories, stage_id, "manifest.json")))

    def test_progress_lines(self):
        fw = self.framework(HISTS)
        fw.start(run_root=self.root)
        messages = [text for kind, text in self.reporter.messages if kind == "message"]
        self.assertIn("[hists] 1/2 controlhists mutau 2025 ...", messages)
        self.assertIn("[hists] 2/2 controlhists mumu 2025 ok (1 s)", messages)

    def test_progress_events(self):
        fw = self.framework(HISTS)
        fw.start(run_root=self.root)
        progress = [fields for kind, fields in self.reporter.events if kind == "progress"]
        self.assertEqual([(p["index"], p["total"], p["label"], p["status"]) for p in progress],
                         [(1, 2, "controlhists mutau 2025", "run"), (1, 2, "controlhists mutau 2025", "ok"),
                          (2, 2, "controlhists mumu 2025", "run"), (2, 2, "controlhists mumu 2025", "ok")])
        self.assertEqual({p["stage"] for p in progress}, {"hists"})
        self.assertNotIn("seconds", progress[0])
        self.assertIn("seconds", progress[1])
        self.assertEqual([os.path.basename(p["log"]) for p in progress], ["01.log", "01.log", "02.log", "02.log"])

    def test_failed_command_fails_the_stage(self):
        self.tes_shapes.fail = "shapes 2025 Tight Tight %s" % (resolve(TT, None))  # the API gets the template's path
        record = self.framework(SHAPES, connected(FIT, shapes="shapes")).start(run_root=self.root)
        stage = record.stage("shapes")
        self.assertEqual(stage.state, "FAILED")
        self.assertEqual(record.state, "FAILED")
        self.assertIn("shapes 2025 Tight Tight", stage.message)
        self.assertIn("exit code 2", stage.message)
        self.assertIn(os.path.join(record.run_dir, "logs", "shapes"), stage.message)
        self.assertFalse(os.path.exists(os.path.join(record.run_dir, "stages", "shapes")))  # FAILED: no manifest
        self.assertEqual(len(stage.last_status["commands"]), 3)  # stopped at the failed command
        self.assertEqual(stage.artifacts, [])
        self.assertEqual(record.stage("fit").state, "NEW")
        self.assertNotIn("fit", self.fitter.names())
        warning = next(w for w in self.warnings() if "Last lines" in w)
        self.assertIn("line 29", warning)  # the end of the log
        self.assertNotIn("line 9\n", warning)  # only the last 20 lines

    def test_preflight_problem_leaves_the_stage_new(self):
        self.histogrammer.problems = ("CMSSW_BASE is not set (run cmsenv first)",)
        fw = self.framework(HISTS)
        record = fw.start(run_root=self.root)
        stage = RunRecord.load(record.run_dir).stage("hists")
        self.assertEqual(stage.state, "NEW")
        self.assertEqual(stage.message, "not ready: CMSSW_BASE is not set (run cmsenv first)")
        self.assertEqual(stage.history[-1]["event"], "preflight")
        self.assertNotIn("make", self.histogrammer.names())
        self.assertIn("hists is not ready", self.warnings()[-1])
        self.histogrammer.problems = ()  # fixed: advance again
        record = fw.advance(record)
        self.assertEqual(record.stage("hists").state, "DONE")

    def test_fit_without_points_fails(self):  # no point has the shapes of both configs
        record = self.framework(dict(SHAPES, configs=[TT]), FIT).start(run_root=self.root)
        self.assertEqual(record.stage("fit").state, "FAILED")
        self.assertIn("no working points", record.stage("fit").message)

    def test_fit_points_from_the_recipe(self):
        fit = dict(FIT, eras=["2025"], jet_wps=["Tight"], ele_wps=["Tight"])
        self.framework(SHAPES, fit).start(run_root=self.root)
        self.assertIs(self.fitter.call("preflight_fit")[1], False)  # shapes of this run: not checked on disk
        self.assertEqual(self.fitter.call("fit")[0]["points"], (("2025", "Tight", "Tight"),))
        self.assertEqual(self.fitter.call("fit")[0]["shapes_dirs"], (("2025", "Tight", "Tight", "/fit"),))

    def test_fit_point_without_shapes_in_the_input_stage_fails(self):
        fit = connected(dict(FIT, eras=["2025"], jet_wps=["Loose"], ele_wps=["Tight"]), shapes="shapes")
        record = self.framework(SHAPES, fit).start(run_root=self.root)
        self.assertEqual(record.stage("fit").state, "FAILED")
        self.assertIn("no shapes of 2025 Loose/Tight in stage 'shapes'", record.stage("fit").message)
        self.assertNotIn("fit", self.fitter.names())

    def test_fit_needs_shapes_of_both_configs(self):
        histograms = dict(SHAPES, configs=[TT])  # no mumu shapes
        record = self.framework(histograms, connected(FIT, shapes="shapes")).start(run_root=self.root)
        self.assertEqual(record.stage("shapes").state, "DONE")
        self.assertEqual(record.stage("fit").state, "FAILED")


class RecoveryTests(LocalStageTestCase):
    def test_reload_keeps_completed_stages_and_passes_saved_artifacts_downstream(self):
        # Stop at shapes preflight after production and hists genuinely finish.
        self.tes_shapes.problems = ("CMSSW_BASE is not set",)
        fw = self.framework(*PIPELINE)
        record = fw.advance(fw.start(run_root=self.root))
        loaded = RunRecord.load(record.run_dir)
        self.assertEqual([s.state for s in loaded.stages], ["DONE", "DONE", "NEW", "NEW"])
        upstream = loaded.to_dict()["stages"][:2]
        dy = os.path.join(record.run_dir, "stages", "production", "2018", "DY", "DY_mutau.root")
        self.assertEqual(loaded.stage("production").artifacts[0]["path"], dy)

        pico = fakes.FakePicoProducer()
        histogrammer = fakes.FakeHistogrammer()
        fitter, tes_shapes = fakes.FakeFitter(), fakes.FakeTESShapes()
        resumed = Framework.from_record(loaded, pico=pico, histogrammer=histogrammer, fitter=fitter,
                                        tes_shapes=tes_shapes, reporter=SilentReporter())
        resumed.clock = Clock()
        record = resumed.advance(loaded)
        saved = RunRecord.load(record.run_dir)
        self.assertEqual(saved.state, "DONE")
        self.assertEqual(saved.to_dict()["stages"][:2], upstream)
        self.assertEqual(pico.calls, [])
        self.assertEqual(histogrammer.calls, [])
        self.assertEqual(saved.stage("shapes").last_status["inputs"], [dy])
        self.assertEqual(len(saved.stage("shapes").artifacts), 4)
        self.assertEqual(fitter.call("fit")[0]["points"],
                         (("2025", "VTight", "Tight"), ("2025", "Tight", "Tight")))
        self.assertIs(fitter.call("preflight_fit")[1], False)  # uses the upstream shapes

        # Reload the now-complete multi-stage run with another set of fresh services.
        pico, histogrammer, fitter = fakes.FakePicoProducer(), fakes.FakeHistogrammer(), fakes.FakeFitter()
        tes_shapes = fakes.FakeTESShapes()
        completed_stages = saved.to_dict()["stages"]
        completed = Framework.from_record(saved, pico=pico, histogrammer=histogrammer, fitter=fitter,
                                          tes_shapes=tes_shapes, reporter=SilentReporter())
        completed.advance(saved)
        self.assertEqual([pico.calls, histogrammer.calls, fitter.calls, tes_shapes.calls], [[], [], [], []])
        self.assertEqual(RunRecord.load(saved.run_dir).to_dict()["stages"], completed_stages)


class PlanTests(LocalStageTestCase):
    def test_plan_passes_planned_artifacts_forward(self):
        self.fitter.problems = ("combine is not on PATH",)
        plan = self.framework(SHAPES, connected(FIT, shapes="shapes")).plan()
        shapes, fit = plan.stages
        self.assertEqual(len(shapes.plan.commands), 4)
        self.assertEqual([c.label for c in fit.plan.commands], ["fit 2025 VTight Tight", "fit 2025 Tight Tight"])
        self.assertEqual(fit.plan.notes, ("combine is not on PATH",))  # preflight problems become notes
        self.assertNotIn("fit", self.fitter.names())  # nothing ran
        self.assertNotIn("make_shapes", self.tes_shapes.names())

    def test_unplannable_stage_has_a_note(self):
        plan = self.framework(dict(SHAPES, configs=[TT]), FIT).plan()
        self.assertIsNone(plan.stages[1].plan)
        self.assertIn("no working points", plan.stages[1].note)

    def test_stage_plan_raises_preflight_error_directly(self):
        with self.assertRaises(PreflightError):
            FitStage(self.fitter).plan(recipe(SHAPES, FIT).stage("fit").spec, StageContext())


class TupleInputTests(LocalStageTestCase):
    """Where hists and shapes read their tuples: the pattern of the production stage their input names,
    {external: <pattern>} or {path: ...}; never null (CL §37)."""

    def external(self, stage, pattern):
        return dict(stage, inputs={"tuples": {"external": pattern}})

    def test_external_pattern(self):
        os.makedirs(os.path.join(self.root, "tuples", "2025"))
        pattern = os.path.join(self.root, "tuples", "$ERA", "$GROUP")
        fw = self.framework(self.external(HISTS, pattern), self.external(SHAPES, pattern))
        self.assertEqual(fw.recipe.stage("hists").connections, {"tuples": None})
        self.assertEqual(fw.recipe.stage("hists").external, {"tuples": pattern})
        record = fw.start(run_root=os.path.join(self.root, "runs"))
        self.assertEqual([record.stage(s).state for s in ("hists", "shapes")], ["DONE", "DONE"])
        request = self.histogrammer.call("make")[0]
        self.assertEqual(request["tuples"], pattern)
        self.assertNotIn("pico_config", request)  # CL §37
        self.assertEqual(self.tes_shapes.call("make_shapes")[0]["tuples"], pattern)
        self.assertEqual(record.stage("hists").last_status["tuples"], pattern)
        self.assertNotIn("inputs", record.stage("hists").last_status)  # no tuple files are known
        self.assertEqual(record.recipe["stages"][0]["inputs"], {"tuples": {"external": pattern}})  # as written

    def test_external_directory_must_exist(self):
        pattern = os.path.join(self.root, "missing", "$ERA", "$GROUP")
        record = self.framework(self.external(HISTS, pattern)).start(run_root=os.path.join(self.root, "runs"))
        stage = record.stage("hists")
        self.assertEqual(stage.state, "NEW")
        self.assertEqual(stage.message, "not ready: tuple directory %s (of {external: %s}) not found"
                         % (os.path.join(self.root, "missing"), pattern))
        self.assertNotIn("make", self.histogrammer.names())

    def test_null_is_a_recipe_error(self):  # CL §37: inputs are given, never found
        for stage, slot, meant in ((HISTS, "tuples", "$PICODIR"), (SHAPES, "tuples", "$PICODIR"),
                                   (dict(FIT, eras=["2025"], jet_wps=["Tight"], ele_wps=["Tight"]), "shapes",
                                    "Fitter/input_pt_less_region/")):
            with self.assertRaises(RecipeError) as raised:
                recipe(dict(stage, inputs={slot: None}))
            message = str(raised.exception)
            self.assertIn("inputs.%s: null (" % (slot), message)
            self.assertIn(meant, message)
            self.assertIn("is no longer read, inputs are given (CL §37)", message)
            self.assertIn("{external: /eos/.../$ERA/$GROUP}" if slot == "tuples" else "a shapes stage", message)

    def test_plan_gives_the_planned_pattern(self):
        plan = self.framework(PRODUCTION, connected(HISTS, tuples="production")).plan()
        self.assertEqual(self.histogrammer.call("plan")[0]["tuples"],
                         os.path.join("<run_dir>", "stages", "production", "$ERA", "$GROUP"))
        self.assertEqual(plan.stages[1].plan.notes, ())  # no problem with the planned pattern

    def test_a_quick_plan_leaves_out_the_checks_that_open_tuple_files(self):  # the menu's plan screen
        fw = self.framework(PRODUCTION, connected(HISTS, tuples="production"), connected(SHAPES, tuples="production"))
        fw.plan(deep=False)
        fw.plan()
        self.assertEqual(self.histogrammer.branches, [False, True])
        self.assertEqual(self.tes_shapes.branches, [False, True])
        self.assertEqual([stage.deep_checks for stage in fw.stages.values()], [False, True, True])

    def test_pattern_problems(self):
        stage = ControlHistsStage(self.histogrammer)

        def context(*artifacts):
            return StageContext(inputs={"tuples": "production"}, upstream={"production": artifacts})

        self.assertEqual(stage.tuples_pattern(context()), ("<production>/$ERA/$GROUP", ()))  # nothing planned yet
        self.assertEqual(stage.tuples_pattern(StageContext()), (None, ()))  # no input
        # CL §36: records without a kind (made before) are refused; only kind 'tuples' is read
        self.assertEqual(stage.tuples_pattern(context({"pattern": "/p/$ERA", "path": "x"}))[1],
                         ("the tuples of stage 'production' were recorded before their records had a kind (CL §36); "
                          "start a new run, or name them with {external: <pattern>}",))
        self.assertEqual(stage.tuples_pattern(context({"kind": "tuples", "pattern": "/p/$ERA"},
                                                      {"kind": "other", "pattern": "/q/$ERA"})), ("/p/$ERA", ()))
        self.assertEqual(stage.tuples_pattern(context({"kind": "other", "pattern": "/q/$ERA"})), (None, ()))
        self.assertEqual(stage.tuples_pattern(context({"kind": "tuples", "path": "x"},
                                                      {"kind": "tuples", "path": "y"}))[1],
                         ("the tuples of stage 'production' do not record where they are (made before the Framework "
                          "chose their place, CL §16); start a new run, or name them with "
                          "{external: <pattern>}",))
        several = context({"kind": "tuples", "pattern": "/a/$ERA"}, {"kind": "tuples", "pattern": "/b/$ERA"})
        self.assertIn("are in several places", stage.tuples_pattern(several)[1][0])
        here = os.path.join(self.root, "DY_mutau.root")
        open(here, "w").close()
        missing = os.path.join(self.root, "TT_mutau.root")
        problems = stage.input_problems(context({"kind": "tuples", "pattern": "/p/$ERA", "path": here},
                                                {"kind": "tuples", "pattern": "/p/$ERA", "path": missing}))
        self.assertEqual(problems, ("1 tuple file(s) of stage 'production' not found, e.g. %s" % (missing),))
        self.assertEqual(stage.input_problems(context({"kind": "tuples", "pattern": "/p/$ERA", "path": missing}),
                                              files=False), ())

    def test_fixed_directory(self):
        from TauFW.Framework.stages.local import fixed_directory
        self.assertEqual(fixed_directory("/eos/tes/TES_variations/$ERA/$GROUP"), "/eos/tes/TES_variations")
        self.assertEqual(fixed_directory("/eos/tes/tuples_$ERA/$GROUP"), "/eos/tes")
        self.assertEqual(fixed_directory("/eos/tes"), "/eos/tes")


class PathInputTests(LocalStageTestCase):
    """R4: an input that names another run's stage directory ({path: <dir>}): the artifacts come from its
    manifest, nothing is written there, and run.json and the reader's manifest record the source."""

    def source_run(self, *stages):
        fw = self.framework(*stages)
        record = fw.start(run_root=os.path.join(self.root, "source"))
        if record.state == "WAITING":  # production: the jobs are complete at the next check
            record = fw.advance(record)
        self.assertEqual(record.state, "DONE")
        return record

    def snapshot(self, directory):
        return sorted((os.path.relpath(os.path.join(d, f), directory), os.stat(os.path.join(d, f)).st_mtime_ns)
                      for d, _, files in os.walk(directory) for f in files)

    def test_fit_reads_the_shapes_of_another_run(self):
        source = os.path.join(self.source_run(SHAPES).run_dir, "stages", "shapes")
        before = self.snapshot(source)
        with open(os.path.join(source, "manifest.json"), "rb") as stream:
            sha256 = hashlib.sha256(stream.read()).hexdigest()
        fit = dict(FIT, inputs={"shapes": {"path": source}})
        fw = self.framework(fit)
        plan = fw.plan().stages[0]
        self.assertEqual(plan.plan.commands[0].label, "fit 2025 VTight Tight")  # the points of the source's shapes
        self.assertEqual(plan.sources["shapes"]["stage_id"], "shapes")
        record = fw.start(run_root=os.path.join(self.root, "reader"))
        self.assertEqual(record.state, "DONE", record.stage("fit").message)
        request = self.fitter.call("fit")[0]
        self.assertEqual(request["points"], (("2025", "VTight", "Tight"), ("2025", "Tight", "Tight")))
        self.assertEqual(request["shapes_dirs"], (("2025", "VTight", "Tight", "/fit"),
                                                  ("2025", "Tight", "Tight", "/fit")))
        self.assertIs(self.fitter.call("preflight_fit")[1], True)  # from another run: the files are checked
        with open(os.path.join(source, "manifest.json")) as stream:
            source_manifest = json.load(stream)
        expected = {"shapes": {"path": source, "run_id": source_manifest["run_id"], "stage_id": "shapes",
                               "stage": "shapes", "finished": source_manifest["finished"],
                               "manifest_sha256": sha256}}
        self.assertEqual(record.stage("fit").sources, expected)
        self.assertEqual(RunRecord.load(record.run_dir).stage("fit").sources, expected)
        with open(os.path.join(record.run_dir, "stages", "fit", "manifest.json")) as stream:
            manifest = json.load(stream)
        self.assertEqual((manifest["inputs"], manifest["sources"]), ({"shapes": {"path": source}}, expected))
        self.assertEqual(self.snapshot(source), before)  # nothing written in the source

    def test_unreadable_source_leaves_the_stage_new(self):
        source = os.path.join(self.source_run(SHAPES).run_dir, "stages", "shapes")
        fit = dict(FIT, inputs={"shapes": {"path": source}})
        os.rename(os.path.join(source, "manifest.json"), os.path.join(source, "manifest.moved"))
        fw = self.framework(fit)
        self.assertIn("inputs.shapes: %s has no manifest.json" % (source), fw.plan().stages[0].note)
        record = fw.start(run_root=os.path.join(self.root, "reader"))
        self.assertEqual(record.stage("fit").state, "NEW")
        self.assertIn("not ready: inputs.shapes: %s has no manifest.json" % (source), record.stage("fit").message)
        self.assertEqual(record.stage("fit").history[-1]["event"], "preflight")
        self.assertNotIn("fit", self.fitter.names())
        os.rename(os.path.join(source, "manifest.moved"), os.path.join(source, "manifest.json"))  # fixed
        record = fw.advance(record)
        self.assertEqual(record.stage("fit").state, "DONE")
        self.assertEqual(record.stage("fit").sources["shapes"]["path"], source)

    def test_plots_read_the_tuples_of_another_run(self):
        source = os.path.join(self.source_run(PRODUCTION).run_dir, "stages", "production")
        plots = dict(HISTS, inputs={"tuples": {"path": source}})
        record = self.framework(plots).start(run_root=os.path.join(self.root, "reader"))
        self.assertEqual(record.state, "DONE", record.stage("hists").message)
        pattern = os.path.join(source, "$ERA", "$GROUP")
        self.assertEqual(self.histogrammer.call("make")[0]["tuples"], pattern)
        self.assertNotIn("pico_config", self.histogrammer.call("make")[0])  # CL §37
        self.assertEqual(record.stage("hists").last_status["tuples"], pattern)
        self.assertEqual(record.stage("hists").sources["tuples"]["stage"], "production")

    def test_wrong_kind_is_refused(self):
        source = os.path.join(self.source_run(HISTS).run_dir, "stages", "hists")
        fw = self.framework(dict(FIT, inputs={"shapes": {"path": source}}))
        self.assertIn("is stage 'hists' (controlhists) of run", fw.plan().stages[0].note)
        self.assertIn("it makes control_histograms, not shapes", fw.plan().stages[0].note)

    def test_no_sources_is_an_empty_record(self):
        record = self.framework(SHAPES).start(run_root=self.root)
        self.assertEqual(record.stage("shapes").sources, {})


class ControlPlotsTests(LocalStageTestCase):
    """CL §21 S4: controlplots draws the files of the controlhists stage its input names (the Plotter API)."""

    def test_draws_the_files_of_its_input(self):
        record = self.framework(HISTS, PLOTS).start(run_root=self.root)
        self.assertEqual(record.state, "DONE", record.stage("plots").message)
        stages = os.path.join(record.run_dir, "stages")
        hists = os.path.join(stages, "hists", "hists", "2025")
        request = self.plotter.call("make")[0]
        self.assertEqual(request["files"], [
            {"path": os.path.join(hists, "mutau.root"), "era": "2025", "channel": "mutau", "config": "mutau", "tag": ""},
            {"path": os.path.join(hists, "mumu.root"), "era": "2025", "channel": "mumu", "config": "mumu", "tag": ""}])
        self.assertEqual((request["outdir"], request["pdf"], request["fraction"], request["text"]),
                         (os.path.join(stages, "plots"), True, False, ""))
        self.assertNotIn("pdf", self.histogrammer.call("make")[0])  # a drawing option is not the Histogrammer's
        plots = record.stage("plots")
        self.assertEqual([(a["kind"], a["channel"], a["directory"]) for a in plots.artifacts],
                         [("plots", "mutau", os.path.join(stages, "plots", "plots", "2025")),
                          ("plots", "mumu", os.path.join(stages, "plots", "plots", "2025"))])
        self.assertEqual(plots.request, {"fraction": False, "pdf": True, "text": "", "timeout": None})
        self.assertEqual(self.plotter.logdirs, [os.path.join(record.run_dir, "logs", "plots")])

    def test_plan_before_the_files_exist(self):
        plan = self.framework(HISTS, PLOTS).plan()
        self.assertEqual([c.label for c in plan.stages[1].plan.commands],
                         ["controlplots mutau 2025", "controlplots mumu 2025"])
        self.assertEqual(self.plotter.call("plan")[0]["files"][0]["path"],  # the planned file of the stage above
                         os.path.join("<run_dir>", "stages", "hists", "hists", "2025", "mutau.root"))

    def test_input_must_be_control_histograms(self):
        with self.assertRaises(RecipeError) as caught:
            recipe(HISTS, dict(PLOTS, inputs={"hists": None}))
        self.assertIn("inputs.hists: must name an earlier stage that makes control_histograms (null is not "
                      "allowed for this input)", str(caught.exception))
        with self.assertRaises(RecipeError) as caught:
            recipe(SHAPES, dict(PLOTS, inputs={"hists": "shapes"}))
        self.assertIn("stage 'shapes' (shapes) makes shapes, not control_histograms", str(caught.exception))
        with self.assertRaises(RecipeError) as caught:
            recipe(dict(PLOTS, inputs={"hists": {"external": "/eos/x/$ERA/$GROUP"}}))
        self.assertIn("{external: ...} is only for a tuples input", str(caught.exception))
        with self.assertRaises(RecipeError) as caught:
            recipe(dict(HISTS, pdf=True))  # drawing options are the controlplots stage's (plan 18 §14 K7)
        self.assertIn("unknown option 'pdf'", str(caught.exception))

    def test_files_of_another_run(self):
        source = os.path.join(PathInputTests.source_run(self, HISTS).run_dir, "stages", "hists")
        record = self.framework(dict(PLOTS, inputs={"hists": {"path": source}})).start(run_root=self.root)
        self.assertEqual(record.state, "DONE", record.stage("plots").message)
        self.assertEqual([f["path"] for f in self.plotter.call("make")[0]["files"]],
                         [os.path.join(source, "hists", "2025", "%s.root" % (c)) for c in ("mutau", "mumu")])


class ContextTests(LocalStageTestCase):
    def test_only_done_upstream_stages_are_passed(self):
        plots = connected(HISTS, tuples="production")
        fw = self.framework(PRODUCTION, plots)
        record = fw.start(run_root=self.root)  # production SUBMITTED
        context = fw._context(record, recipe(PRODUCTION, plots).stage("hists"))
        self.assertEqual(context.upstream, {})
        self.assertEqual(context.run_dir, record.run_dir)
        record = fw.advance(record)
        context = fw._context(record, recipe(PRODUCTION, plots).stage("hists"))
        self.assertEqual([a["path"] for a in context.artifacts("production")],
                         [os.path.join(record.run_dir, "stages", "production", "2018", "DY", "DY_mutau.root")])
        self.assertEqual(context.input_artifacts("tuples"), context.artifacts("production"))
        self.assertEqual(context.artifacts(kind="shapes"), ())

    def test_a_stage_sees_only_the_stages_its_inputs_name(self):
        fw = self.framework(PRODUCTION, HISTS)  # hists: external tuples, although the recipe has a production stage
        record = fw.advance(fw.start(run_root=self.root))
        self.assertEqual(record.stage("production").state, "DONE")
        context = fw._context(record, fw.recipe.stage("hists"))
        self.assertEqual((context.upstream, context.input_artifacts("tuples")), ({}, ()))
        self.assertNotIn("inputs", record.stage("hists").last_status)  # no production tuples recorded

    def test_output_dir_in_a_plan(self):  # no run yet: a placeholder, as for python steps
        self.framework(HISTS).plan()
        self.assertEqual(self.histogrammer.call("plan")[0]["outdir"], os.path.join("<run_dir>", "stages", "hists"))

    def test_stage_dir(self):
        context = StageContext(run_dir="runs/x", stage_id="hists")
        self.assertEqual(context.stage_dir("fit"), os.path.join("runs/x", "stages", "fit"))
        self.assertEqual(context.stage_dir(), os.path.join("runs/x", "stages", "hists"))
        self.assertEqual(context.log_dir(), os.path.join("runs/x", "logs", "hists"))


class SpecTests(unittest.TestCase):
    def error(self, *stages):
        with self.assertRaises(RecipeError) as context:
            recipe(*stages)
        return str(context.exception)

    def test_specs(self):
        spec = recipe(SHAPES).stage("shapes").spec
        self.assertEqual(spec.eras, ("2025",))  # numbers from YAML become strings
        self.assertEqual(spec.configs, (TT, MM))  # default: the configs of run_inputs.sh
        self.assertEqual(recipe(dict(HISTS, configs="mutau")).stage("hists").spec.configs, ("mutau",))
        fit = recipe(SHAPES, {"stage": "fit", "id": "fit", "inputs": {"shapes": "shapes"}}).stage("fit").spec
        self.assertEqual(fit.steps, ("fit", "postfit", "plots", "corrections", "summary"))
        self.assertTrue(fit.impacts)

    def test_spec_errors(self):
        self.assertIn("missing required option 'eras'", self.error({"stage": "controlhists"}))
        self.assertIn("jet_wps must not be empty", self.error(dict(SHAPES, jet_wps=[])))
        self.assertIn("give both jet_wps and ele_wps", self.error({"stage": "fit", "jet_wps": ["Tight"]}))
        self.assertIn("unknown step 'scan'", self.error({"stage": "fit", "steps": ["fit", "scan"]}))
        self.assertIn("unknown option 'variable'", self.error({"stage": "controlhists", "eras": [2025], "variable": []}))


class CommandLineTests(LocalStageTestCase):
    def setUp(self):
        super().setUp()
        checkout.reviewed_user_config(self)  # taufw.py's output does not depend on the checkout's user config
        spec = importlib.util.spec_from_file_location("taufw_cli", str(checkout.TAUFW_SCRIPT))
        self.cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.cli)
        self.cli.FrameworkReporter = lambda verbosity=0: self.reporter

    def test_plan_shows_commands_and_notes(self):
        path = os.path.join(self.root, "r.json")
        with open(path, "w") as stream:
            json.dump({"name": "tes", "stages": [SHAPES, connected(FIT, shapes="shapes")]}, stream)
        self.fitter.problems = ("combine is not on PATH",)
        real = Framework.from_recipe
        self.cli.Framework.from_recipe = lambda r, reporter=None, **kw: real(r, reporter=reporter,
                                                                              fitter=self.fitter,
                                                                              tes_shapes=self.tes_shapes,
                                                                              histogrammer=self.histogrammer)
        try:
            self.assertEqual(self.cli.main(["plan", path]), 0)
        finally:
            self.cli.Framework.from_recipe = real
        tables = [text for kind, text in self.reporter.messages if kind == "table"]
        self.assertIn("['option', 'file', 'from']", tables[0])  # the files the stage reads come first
        self.assertIn(repr(['configs', resolve(TT, None), 'template']), tables[0])  # a Configs/ template (CL §22)
        commands = [text for text in tables if "['#', 'step', 'command']" in text]
        self.assertIn("shapes 2025 VTight Tight", commands[0])
        self.assertIn("Working directory: /repo/Fitter", [t for k, t in self.reporter.messages])
        self.assertIn("combine is not on PATH", self.warnings())
        messages = [t for k, t in self.reporter.messages if k == "message"]
        self.assertIn("Inputs: shapes <- shapes", messages)
        self.assertIn("Inputs: tuples <- external %s" % (fakes.TUPLES), messages)
        self.assertFalse([m for m in messages if m.startswith("PicoProducer config:")])  # no production (CL §37)
        path = os.path.join(self.root, "external.json")
        os.makedirs(os.path.join(self.root, "tuples"))
        pattern = os.path.join(self.root, "tuples", "$ERA", "$GROUP")
        with open(path, "w") as stream:
            json.dump({"name": "tes", "stages": [dict(HISTS, inputs={"tuples": {"external": pattern}})]}, stream)
        self.cli.Framework.from_recipe = lambda r, reporter=None, **kw: real(r, reporter=reporter,
                                                                              histogrammer=self.histogrammer)
        try:
            self.assertEqual(self.cli.main(["plan", path]), 0)
        finally:
            self.cli.Framework.from_recipe = real
        self.assertIn("Inputs: tuples <- external %s" % (pattern),
                      [t for k, t in self.reporter.messages if k == "message"])

    def test_inputs_line_of_another_runs_stage(self):
        source = {"run_id": "tes_20261015-120000", "stage_id": "shapes", "stage": "shapes",
                  "finished": "2026-10-15 14:02:11"}
        stage_spec = recipe(dict(FIT, inputs={"shapes": {"path": "/afs/runs/x/stages/shapes"}})).stage("fit")
        self.assertEqual(inputs_line(stage_spec, FitStage(self.fitter), {"shapes": source}),
                         "shapes <- /afs/runs/x/stages/shapes (run tes_20261015-120000, stage shapes "
                         "(shapes), finished 2026-10-15 14:02:11)")
        self.assertEqual(inputs_line(stage_spec, FitStage(self.fitter), {}),
                         "shapes <- /afs/runs/x/stages/shapes")  # cannot be read: the note says why

    def test_inputs_short_names_each_source_once(self):
        stage_spec = recipe(dict(FIT, inputs={"shapes": {"path": "/afs/runs/x/stages/shapes"}})).stage("fit")
        self.assertEqual(inputs_short(stage_spec), "other run")
        from TauFW.Framework._internal.recipes.recipe import StageSpec
        stage_spec = StageSpec("python", "summary", None, inputs={"a": "fit", "b": "fit", "c": None,
                                                                  "d": {"external": "/eos/x/*.root"}})
        self.assertEqual(inputs_short(stage_spec), "fit, outside, external")
        self.assertEqual(inputs_short(StageSpec("python", "summary", None, inputs=None)), "-")

    def test_check_lists_every_problem(self):
        path = os.path.join(self.root, "r.json")
        with open(path, "w") as stream:
            json.dump({"name": "tes", "stages": [dict(SHAPES, id="a/b"), dict(FIT, inputs=None)]}, stream)
        self.assertEqual(self.cli.main(["check", path]), 1)
        self.assertEqual(self.warnings(), [
            "run_root: not set: the runs go to taufw_runs/ in the directory taufw.py is started from. "
            "Set run_root: <absolute directory> in the recipe, or start with --run-root",
            "Recipe tes: 2 problem(s)",
            "  stages[0] (shapes).id: must be a word of letters, digits, '_', '.' or '-' (got 'a/b')",
            "  stages[1] (fit).inputs: fit reads shapes: write inputs: {shapes: <stage id, {path: <stage "
             "directory>}>}"])
        self.assertEqual(self.cli.main(["plan", path]), 1)  # an invalid recipe: the problems, no traceback
        self.assertIn("r.json: 2 problems", self.warnings()[-1])
        with open(path, "w") as stream:
            json.dump({"name": "tes", "stages": [SHAPES]}, stream)
        self.assertEqual(self.cli.main(["check", path]), 0)

    def test_command_line_shows_python3_and_environment(self):
        import sys
        from TauFW.Utilities.Process import Command
        command = Command("hists", (sys.executable, "plot.py", "-S", "a b"), "/repo/Plotter")
        self.assertEqual(command_line(command), "python3 plot.py -S 'a b'")
        command = Command("hists", (sys.executable, "plot.py"), "/repo/Plotter",
                          env=(("TAUFW_PICO_CONFIG", "/b/pico.json"),))
        self.assertEqual(command_line(command), "TAUFW_PICO_CONFIG=/b/pico.json python3 plot.py")

    def test_commands_in_subdirectories_are_named(self):  # the fit: the scripts of each era run in <stage>/<era>
        from TauFW.Utilities.Process import Command, CommandPlan
        base = os.path.join("<run_dir>", "stages", "fit")
        plan = CommandPlan(base, tuple(Command("fit %s" % era, ("python3", "x.py"), os.path.join(base, era))
                                       for era in ("2025", "2024")))
        self.cli._show_commands(self.reporter, plan)
        self.assertIn("Commands run in: 2025, 2024 (relative to the working directory)",
                      [text for kind, text in self.reporter.messages if kind == "message"])


if __name__ == "__main__":
    unittest.main()


class FitLabelTests(unittest.TestCase):  # CL §27: the normalisation of the input shapes, for the fit's CMS label
    def labels(self, artifacts, points=(("2025", "VTight", "Tight"),)):
        from types import SimpleNamespace
        from TauFW.Framework.stages.fit import FitStage
        context = SimpleNamespace(input_artifacts=lambda name, kind=None: list(artifacts),
                                  input_name=lambda name: "stage shapes")
        return FitStage.labels(FitStage.__new__(FitStage), points, context)

    def test_labels(self):
        shape = {"kind": "shapes", "era": "2025", "lumi": 110.18, "cme": 13.6}
        self.assertEqual(self.labels([shape, dict(shape, config="mumu")]), (("2025", 110.18, 13.6),))
        self.assertEqual(self.labels([dict(shape, lumi=None)]), ())  # shapes without a sample model
        self.assertEqual(self.labels([{"kind": "shapes", "era": "2025"}]), ())  # old artifacts
        self.assertEqual(self.labels([dict(shape, era="2024")]), ())
        with self.assertRaisesRegex(ValueError, "different luminosities"):
            self.labels([shape, dict(shape, lumi=100.0)])
