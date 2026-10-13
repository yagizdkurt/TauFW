"""Local stages (plots, histograms, fit) and the stage context, driven by fake module APIs (no ROOT, no scripts)."""
import importlib.util
import json
import os
import shutil
import tempfile
import unittest

import checkout  # noqa: F401  (must precede TauFW imports)
import fakes
from TauFW.Framework import Framework, Recipe, RecipeError, RunRecord, SilentReporter
from TauFW.Framework.stages import (ProductionStage, PlotStage, HistogramStage, FitStage, StageContext,
                                    PreflightError)
from test_framework import Clock

PRODUCTION = {"stage": "production", "eras": ["2025"], "channels": ["mutau"], "samples": ["DY*"]}
PLOTS = {"stage": "plots", "eras": [2025], "configs": ["mutau", "mumu"], "variables": ["m_vis"]}
HISTOGRAMS = {"stage": "histograms", "eras": [2025], "jet_wps": ["VTight", "Tight"], "ele_wps": ["Tight"]}
FIT = {"stage": "fit", "steps": ["fit", "corrections"]}
TT, MM = "TauES_ID/config/config_coarse_TT.yml", "TauES/config/FitSetup_mumu.yml"


def recipe(*stages):
    return Recipe.from_dict({"name": "tes", "pico": {"config": None}, "stages": list(stages)}, source="t.yml")


class LocalStageTestCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="taufw-test-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.pico = fakes.FakePicoProducer(samples=("DY",), statuses=[fakes.complete("DY")])
        self.plotter = fakes.FakePlotter()
        self.fitter = fakes.FakeFitter()
        self.reporter = SilentReporter()

    def framework(self, *stages):
        built = {"production": ProductionStage(self.pico), "plots": PlotStage(self.plotter),
                 "histograms": HistogramStage(self.fitter), "fit": FitStage(self.fitter)}
        return Framework(recipe(*stages), built, reporter=self.reporter, sleep=lambda s: None, clock=Clock())

    def warnings(self):
        return [text for kind, text in self.reporter.messages if kind == "warning"]


class PipelineTests(LocalStageTestCase):
    def test_whole_pipeline_runs_after_production(self):
        fw = self.framework(PRODUCTION, PLOTS, HISTOGRAMS, FIT)
        record = fw.start(run_root=self.root)
        self.assertEqual(record.state, "WAITING")
        self.assertEqual(self.plotter.calls, [])  # nothing local runs before production is DONE
        record = fw.advance(record)
        self.assertEqual(record.state, "DONE")
        self.assertEqual([record.stage(s).state for s in ("plots", "histograms", "fit")], ["DONE"] * 3)
        # each stage logs to <run_dir>/<stage>
        self.assertEqual(self.plotter.logdirs, [os.path.join(record.run_dir, "plots")])
        self.assertEqual(self.fitter.logdirs, [os.path.join(record.run_dir, "histograms"),
                                               os.path.join(record.run_dir, "fit")])
        # the histograms record the production tuples as inputs, and their shapes as artifacts
        histograms = record.stage("histograms")
        self.assertEqual(histograms.last_status["inputs"], ["/pico/DY_mutau.root"])
        self.assertEqual(len(histograms.artifacts), 4)  # 2 jet WPs x 1 ele WP x 2 configs
        self.assertEqual(histograms.request["eras"], ["2025"])
        # the fit points come from the shapes of both configs
        fit_request = self.fitter.call("fit")[0]
        self.assertIs(self.fitter.call("preflight_fit")[1], False)  # the shapes come from the histograms stage
        self.assertEqual(fit_request["points"], (("2025", "VTight", "Tight"), ("2025", "Tight", "Tight")))
        self.assertEqual(fit_request["steps"], ("fit", "corrections"))
        self.assertEqual(len(record.stage("fit").last_status["commands"]), 2)
        # status shows the fitted values, read from run.json
        live = fw.status(record).stages[3].live
        self.assertEqual([(v["jet_wp"], v["poi"], v["value"]) for v in live],
                         [("VTight", "tes", 0.98), ("Tight", "tes", 0.98)])

    def test_progress_lines(self):
        fw = self.framework(PLOTS)
        fw.start(run_root=self.root)
        messages = [text for kind, text in self.reporter.messages if kind == "message"]
        self.assertIn("[plots] 1/2 plots mutau 2025 ...", messages)
        self.assertIn("[plots] 2/2 plots mumu 2025 ok (1 s)", messages)

    def test_failed_command_fails_the_stage(self):
        self.fitter.fail = "shapes 2025 Tight Tight %s" % (TT)
        record = self.framework(HISTOGRAMS, FIT).start(run_root=self.root)
        stage = record.stage("histograms")
        self.assertEqual(stage.state, "FAILED")
        self.assertEqual(record.state, "FAILED")
        self.assertIn("shapes 2025 Tight Tight", stage.message)
        self.assertIn("exit code 2", stage.message)
        self.assertIn(os.path.join(record.run_dir, "histograms"), stage.message)
        self.assertEqual(len(stage.last_status["commands"]), 3)  # stopped at the failed command
        self.assertEqual(stage.artifacts, [])
        self.assertEqual(record.stage("fit").state, "NEW")
        self.assertNotIn("fit", self.fitter.names())
        warning = next(w for w in self.warnings() if "Last lines" in w)
        self.assertIn("line 29", warning)  # the end of the log
        self.assertNotIn("line 9\n", warning)  # only the last 20 lines

    def test_preflight_problem_leaves_the_stage_new(self):
        self.plotter.problems = ("CMSSW_BASE is not set (run cmsenv first)",)
        fw = self.framework(PLOTS)
        record = fw.start(run_root=self.root)
        stage = RunRecord.load(record.run_dir).stage("plots")
        self.assertEqual(stage.state, "NEW")
        self.assertEqual(stage.message, "not ready: CMSSW_BASE is not set (run cmsenv first)")
        self.assertEqual(stage.history[-1]["event"], "preflight")
        self.assertNotIn("make", self.plotter.names())
        self.assertIn("plots is not ready", self.warnings()[-1])
        self.plotter.problems = ()  # fixed: advance again
        record = fw.advance(record)
        self.assertEqual(record.stage("plots").state, "DONE")

    def test_fit_without_points_fails(self):
        record = self.framework(FIT).start(run_root=self.root)
        self.assertEqual(record.stage("fit").state, "FAILED")
        self.assertIn("no working points", record.stage("fit").message)

    def test_fit_points_from_the_recipe(self):
        fit = dict(FIT, eras=["2025"], jet_wps=["Medium", "Tight"], ele_wps=["VVLoose"])
        self.framework(fit).start(run_root=self.root)
        self.assertIs(self.fitter.call("preflight_fit")[1], True)  # no histograms stage: check the shapes on disk
        self.assertEqual(self.fitter.call("fit")[0]["points"],
                         (("2025", "Medium", "VVLoose"), ("2025", "Tight", "VVLoose")))

    def test_fit_needs_shapes_of_both_configs(self):
        histograms = dict(HISTOGRAMS, configs=[TT])  # no mumu shapes
        record = self.framework(histograms, FIT).start(run_root=self.root)
        self.assertEqual(record.stage("histograms").state, "DONE")
        self.assertEqual(record.stage("fit").state, "FAILED")


class PlanTests(LocalStageTestCase):
    def test_plan_passes_planned_artifacts_forward(self):
        self.fitter.problems = ("combine is not on PATH",)
        plan = self.framework(HISTOGRAMS, FIT).plan()
        shapes, fit = plan.stages
        self.assertEqual(len(shapes.plan.commands), 4)
        self.assertEqual([c.label for c in fit.plan.commands], ["fit 2025 VTight Tight", "fit 2025 Tight Tight"])
        self.assertEqual(fit.plan.notes, ("combine is not on PATH",))  # preflight problems become notes
        self.assertNotIn("fit", self.fitter.names())  # nothing ran
        self.assertNotIn("make_shapes", self.fitter.names())

    def test_unplannable_stage_has_a_note(self):
        plan = self.framework(FIT).plan()
        self.assertIsNone(plan.stages[0].plan)
        self.assertIn("no working points", plan.stages[0].note)

    def test_stage_plan_raises_preflight_error_directly(self):
        with self.assertRaises(PreflightError):
            FitStage(self.fitter).plan(recipe(FIT).stage("fit").spec, StageContext())


class ContextTests(LocalStageTestCase):
    def test_only_done_upstream_stages_are_passed(self):
        fw = self.framework(PRODUCTION, PLOTS)
        record = fw.start(run_root=self.root)  # production SUBMITTED
        context = fw._context(record, recipe(PRODUCTION, PLOTS).stage("plots"))
        self.assertEqual(context.upstream, {})
        self.assertEqual(context.run_dir, record.run_dir)
        record = fw.advance(record)
        context = fw._context(record, recipe(PRODUCTION, PLOTS).stage("plots"))
        self.assertEqual([a["path"] for a in context.artifacts("production")], ["/pico/DY_mutau.root"])
        self.assertEqual(context.artifacts(kind="shapes"), ())

    def test_stage_dir(self):
        self.assertEqual(StageContext(run_dir="runs/x").stage_dir("fit"), os.path.join("runs/x", "fit"))


class SpecTests(unittest.TestCase):
    def error(self, *stages):
        with self.assertRaises(RecipeError) as context:
            recipe(*stages)
        return str(context.exception)

    def test_specs(self):
        spec = recipe(HISTOGRAMS).stage("histograms").spec
        self.assertEqual(spec.eras, ("2025",))  # numbers from YAML become strings
        self.assertEqual(spec.configs, (TT, MM))  # default: the configs of run_inputs.sh
        self.assertEqual(recipe(dict(PLOTS, configs="mutau")).stage("plots").spec.configs, ("mutau",))
        fit = recipe({"stage": "fit"}).stage("fit").spec
        self.assertEqual(fit.steps, ("fit", "postfit", "plots", "corrections", "summary"))
        self.assertTrue(fit.impacts)

    def test_spec_errors(self):
        self.assertIn("missing required option 'eras'", self.error({"stage": "plots"}))
        self.assertIn("jet_wps must not be empty", self.error(dict(HISTOGRAMS, jet_wps=[])))
        self.assertIn("give both jet_wps and ele_wps", self.error({"stage": "fit", "jet_wps": ["Tight"]}))
        self.assertIn("unknown step 'scan'", self.error({"stage": "fit", "steps": ["fit", "scan"]}))
        self.assertIn("unknown option 'variable'", self.error({"stage": "plots", "eras": [2025], "variable": []}))


class CommandLineTests(LocalStageTestCase):
    def setUp(self):
        super().setUp()
        spec = importlib.util.spec_from_file_location("taufw_cli", str(checkout.TAUFW_SCRIPT))
        self.cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.cli)
        self.cli.FrameworkReporter = lambda verbosity=0: self.reporter

    def test_plan_shows_commands_and_notes(self):
        path = os.path.join(self.root, "r.json")
        with open(path, "w") as stream:
            json.dump({"name": "tes", "stages": [HISTOGRAMS, FIT]}, stream)
        self.fitter.problems = ("combine is not on PATH",)
        real = Framework.from_recipe
        self.cli.Framework.from_recipe = lambda r, reporter=None, **kw: real(r, reporter=reporter,
                                                                              fitter=self.fitter)
        try:
            self.assertEqual(self.cli.main(["plan", path]), 0)
        finally:
            self.cli.Framework.from_recipe = real
        tables = [text for kind, text in self.reporter.messages if kind == "table"]
        self.assertIn("['#', 'step', 'command']", tables[0])
        self.assertIn("shapes 2025 VTight Tight", tables[0])
        self.assertIn("Working directory: /repo/Fitter", [t for k, t in self.reporter.messages])
        self.assertIn("combine is not on PATH", self.warnings())

    def test_command_line_shows_python3(self):
        import sys
        self.assertEqual(self.cli._command_line((sys.executable, "plot.py", "-S", "a b")), "python3 plot.py -S 'a b'")


if __name__ == "__main__":
    unittest.main()
