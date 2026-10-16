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

PRODUCTION = {"stage": "production", "id": "production", "inputs": None, "eras": ["2025"], "channels": ["mutau"],
              "samples": ["DY*"]}
PLOTS = {"stage": "plots", "id": "plots", "inputs": {"tuples": None}, "eras": [2025], "configs": ["mutau", "mumu"],
         "variables": ["m_vis"]}
HISTOGRAMS = {"stage": "histograms", "id": "histograms", "inputs": {"tuples": None}, "eras": [2025],
              "jet_wps": ["VTight", "Tight"], "ele_wps": ["Tight"]}
FIT = {"stage": "fit", "id": "fit", "inputs": {"shapes": None}, "steps": ["fit", "corrections"]}
TT, MM = "TauES_ID/config/config_coarse_TT.yml", "TauES/config/FitSetup_mumu.yml"


def recipe(*stages):
    return Recipe.from_dict({"name": "tes", "pico": {"config": None}, "stages": list(stages)}, source="t.yml")


def connected(stage, **inputs):
    """The stage with its input slots connected to these stage ids."""
    return dict(stage, inputs=inputs)


PIPELINE = (PRODUCTION, connected(PLOTS, tuples="production"), connected(HISTOGRAMS, tuples="production"),
            connected(FIT, shapes="histograms"))


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
        fw = self.framework(*PIPELINE)
        record = fw.start(run_root=self.root)
        self.assertEqual(record.state, "WAITING")
        self.assertEqual(self.plotter.calls, [])  # nothing local runs before production is DONE
        record = fw.advance(record)
        self.assertEqual(record.state, "DONE")
        self.assertEqual([record.stage(s).state for s in ("plots", "histograms", "fit")], ["DONE"] * 3)
        # each stage logs to <run_dir>/logs/<stage id>, and gets a manifest in <run_dir>/stages/<stage id> when DONE
        logs = os.path.join(record.run_dir, "logs")
        self.assertEqual(self.plotter.logdirs, [os.path.join(logs, "plots")])
        # the Framework decides where a stage writes: its scripts run in <run_dir>/stages/<stage id>
        self.assertEqual(self.plotter.call("make")[0]["outdir"], os.path.join(record.run_dir, "stages", "plots"))
        self.assertEqual(self.fitter.logdirs, [os.path.join(logs, "histograms"), os.path.join(logs, "fit")])
        self.assertEqual(sorted(os.listdir(os.path.join(record.run_dir, "stages"))),
                         ["fit", "histograms", "plots", "production"])
        with open(os.path.join(record.run_dir, "stages", "histograms", "manifest.json")) as stream:
            manifest = json.load(stream)
        self.assertEqual({key: manifest[key] for key in ("manifest", "run_id", "stage_id", "stage", "inputs")},
                         {"manifest": 1, "run_id": record.run_id, "stage_id": "histograms", "stage": "histograms",
                          "inputs": {"tuples": "production"}})
        self.assertEqual(manifest["artifacts"], record.stage("histograms").artifacts)
        production_dir = os.path.join(record.run_dir, "stages", "production")  # the tuples, below <era>/<group>
        self.assertEqual(sorted(os.listdir(production_dir)), ["2018", "manifest.json"])
        dy = os.path.join(production_dir, "2018", "DY", "DY_mutau.root")
        # plots and histograms read the production stage's tuples, through the pattern on its artifacts
        pattern = os.path.join(production_dir, "$ERA", "$GROUP")
        self.assertEqual(self.plotter.call("make")[0]["tuples"], pattern)
        self.assertIsNone(self.plotter.call("make")[0]["pico_config"])
        self.assertEqual(self.fitter.call("make_shapes")[0]["tuples"], pattern)
        self.assertEqual(record.stage("plots").last_status["tuples"], pattern)
        # the histograms record the production tuples as inputs, and their shapes as artifacts
        histograms = record.stage("histograms")
        self.assertEqual(histograms.last_status["inputs"], [dy])
        self.assertEqual(len(histograms.artifacts), 4)  # 2 jet WPs x 1 ele WP x 2 configs
        self.assertEqual(histograms.request["eras"], ["2025"])
        # the fit points come from the shapes of both configs
        fit_request = self.fitter.call("fit")[0]
        self.assertIs(self.fitter.call("preflight_fit")[1], False)  # the shapes come from the histograms stage
        self.assertEqual(fit_request["points"], (("2025", "VTight", "Tight"), ("2025", "Tight", "Tight")))
        self.assertEqual(fit_request["steps"], ("fit", "corrections"))
        # the Framework gives each stage its directory, and the fit the directory of each point's shapes
        stages = os.path.join(record.run_dir, "stages")
        self.assertEqual(self.fitter.call("make_shapes")[0]["outdir"], os.path.join(stages, "histograms"))
        self.assertEqual(fit_request["outdir"], os.path.join(stages, "fit"))
        self.assertEqual(fit_request["shapes_dirs"], (("2025", "VTight", "Tight", "/fit"),
                                                      ("2025", "Tight", "Tight", "/fit")))
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
        record = self.framework(HISTOGRAMS, connected(FIT, shapes="histograms")).start(run_root=self.root)
        stage = record.stage("histograms")
        self.assertEqual(stage.state, "FAILED")
        self.assertEqual(record.state, "FAILED")
        self.assertIn("shapes 2025 Tight Tight", stage.message)
        self.assertIn("exit code 2", stage.message)
        self.assertIn(os.path.join(record.run_dir, "logs", "histograms"), stage.message)
        self.assertFalse(os.path.exists(os.path.join(record.run_dir, "stages", "histograms")))  # FAILED: no manifest
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
        self.assertIs(self.fitter.call("preflight_fit")[1], True)  # shapes: null: check the shapes on disk
        self.assertEqual(self.fitter.call("fit")[0]["points"],
                         (("2025", "Medium", "VVLoose"), ("2025", "Tight", "VVLoose")))
        self.assertEqual(self.fitter.call("fit")[0]["shapes_dirs"], ())  # null: the scripts read Fitter/

    def test_fit_point_without_shapes_in_the_input_stage_fails(self):
        fit = connected(dict(FIT, eras=["2025"], jet_wps=["Loose"], ele_wps=["Tight"]), shapes="histograms")
        record = self.framework(HISTOGRAMS, fit).start(run_root=self.root)
        self.assertEqual(record.stage("fit").state, "FAILED")
        self.assertIn("no shapes of 2025 Loose/Tight in stage 'histograms'", record.stage("fit").message)
        self.assertNotIn("fit", self.fitter.names())

    def test_fit_needs_shapes_of_both_configs(self):
        histograms = dict(HISTOGRAMS, configs=[TT])  # no mumu shapes
        record = self.framework(histograms, connected(FIT, shapes="histograms")).start(run_root=self.root)
        self.assertEqual(record.stage("histograms").state, "DONE")
        self.assertEqual(record.stage("fit").state, "FAILED")


class RecoveryTests(LocalStageTestCase):
    def test_reload_keeps_completed_stages_and_passes_saved_artifacts_downstream(self):
        # Stop at histograms preflight after production and plots genuinely finish.
        self.fitter.problems = ("combine is not on PATH",)
        fw = self.framework(*PIPELINE)
        record = fw.advance(fw.start(run_root=self.root))
        loaded = RunRecord.load(record.run_dir)
        self.assertEqual([s.state for s in loaded.stages], ["DONE", "DONE", "NEW", "NEW"])
        upstream = loaded.to_dict()["stages"][:2]
        dy = os.path.join(record.run_dir, "stages", "production", "2018", "DY", "DY_mutau.root")
        self.assertEqual(loaded.stage("production").artifacts[0]["path"], dy)

        pico = fakes.FakePicoProducer()
        plotter = fakes.FakePlotter()
        fitter = fakes.FakeFitter()
        resumed = Framework.from_record(loaded, pico=pico, plotter=plotter, fitter=fitter,
                                        reporter=SilentReporter())
        resumed.clock = Clock()
        record = resumed.advance(loaded)
        saved = RunRecord.load(record.run_dir)
        self.assertEqual(saved.state, "DONE")
        self.assertEqual(saved.to_dict()["stages"][:2], upstream)
        self.assertEqual(pico.calls, [])
        self.assertEqual(plotter.calls, [])
        self.assertEqual(saved.stage("histograms").last_status["inputs"], [dy])
        self.assertEqual(len(saved.stage("histograms").artifacts), 4)
        self.assertEqual(fitter.call("fit")[0]["points"],
                         (("2025", "VTight", "Tight"), ("2025", "Tight", "Tight")))
        self.assertIs(fitter.call("preflight_fit")[1], False)  # uses the upstream shapes

        # Reload the now-complete multi-stage run with another set of fresh services.
        pico, plotter, fitter = fakes.FakePicoProducer(), fakes.FakePlotter(), fakes.FakeFitter()
        completed_stages = saved.to_dict()["stages"]
        completed = Framework.from_record(saved, pico=pico, plotter=plotter, fitter=fitter,
                                          reporter=SilentReporter())
        completed.advance(saved)
        self.assertEqual([pico.calls, plotter.calls, fitter.calls], [[], [], []])
        self.assertEqual(RunRecord.load(saved.run_dir).to_dict()["stages"], completed_stages)


class PlanTests(LocalStageTestCase):
    def test_plan_passes_planned_artifacts_forward(self):
        self.fitter.problems = ("combine is not on PATH",)
        plan = self.framework(HISTOGRAMS, connected(FIT, shapes="histograms")).plan()
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


class TupleInputTests(LocalStageTestCase):
    """Where plots and histograms read their tuples: the pattern of the production stage their input names,
    {external: <pattern>}, or (null, old recipes) $PICODIR of the PicoProducer configuration."""

    def external(self, stage, pattern):
        return dict(stage, inputs={"tuples": {"external": pattern}})

    def test_external_pattern(self):
        os.makedirs(os.path.join(self.root, "tuples", "2025"))
        pattern = os.path.join(self.root, "tuples", "$ERA", "$GROUP")
        fw = self.framework(self.external(PLOTS, pattern), self.external(HISTOGRAMS, pattern))
        self.assertEqual(fw.recipe.stage("plots").connections, {"tuples": None})
        self.assertEqual(fw.recipe.stage("plots").external, {"tuples": pattern})
        record = fw.start(run_root=os.path.join(self.root, "runs"))
        self.assertEqual([record.stage(s).state for s in ("plots", "histograms")], ["DONE", "DONE"])
        request = self.plotter.call("make")[0]
        self.assertEqual((request["tuples"], request["pico_config"]), (pattern, None))
        self.assertEqual(self.fitter.call("make_shapes")[0]["tuples"], pattern)
        self.assertEqual(record.stage("plots").last_status["tuples"], pattern)
        self.assertNotIn("inputs", record.stage("plots").last_status)  # no tuple files are known
        self.assertEqual(record.recipe["stages"][0]["inputs"], {"tuples": {"external": pattern}})  # as written

    def test_external_directory_must_exist(self):
        pattern = os.path.join(self.root, "missing", "$ERA", "$GROUP")
        record = self.framework(self.external(PLOTS, pattern)).start(run_root=os.path.join(self.root, "runs"))
        stage = record.stage("plots")
        self.assertEqual(stage.state, "NEW")
        self.assertEqual(stage.message, "not ready: tuple directory %s (of {external: %s}) not found"
                         % (os.path.join(self.root, "missing"), pattern))
        self.assertNotIn("make", self.plotter.names())

    def test_null_reads_the_pico_configuration(self):
        record = self.framework(PLOTS).start(run_root=self.root)
        request = self.plotter.call("make")[0]
        self.assertIsNone(request["tuples"])
        self.assertIn("pico_config", request)
        self.assertNotIn("tuples", record.stage("plots").last_status)

    def test_plan_gives_the_planned_pattern(self):
        plan = self.framework(PRODUCTION, connected(PLOTS, tuples="production")).plan()
        self.assertEqual(self.plotter.call("plan")[0]["tuples"],
                         os.path.join("<run_dir>", "stages", "production", "$ERA", "$GROUP"))
        self.assertEqual(plan.stages[1].plan.notes, ())  # no problem with the planned pattern

    def test_pattern_problems(self):
        stage = PlotStage(self.plotter)

        def context(*artifacts):
            return StageContext(inputs={"tuples": "production"}, upstream={"production": artifacts})

        self.assertEqual(stage.tuples_pattern(context()), (None, ()))  # nothing planned yet
        self.assertEqual(stage.tuples_pattern(context({"path": "x"}, {"path": "y"}))[1],
                         ("the tuples of stage 'production' do not record where they are (made before the Framework "
                          "chose their place, CL §18); start a new run, or name them with "
                          "{external: <pattern>}",))
        self.assertIn("are in several places", stage.tuples_pattern(context({"pattern": "/a/$ERA"},
                                                                            {"pattern": "/b/$ERA"}))[1][0])
        here = os.path.join(self.root, "DY_mutau.root")
        open(here, "w").close()
        missing = os.path.join(self.root, "TT_mutau.root")
        problems = stage.input_problems(context({"pattern": "/p/$ERA", "path": here},
                                                {"pattern": "/p/$ERA", "path": missing}))
        self.assertEqual(problems, ("1 tuple file(s) of stage 'production' not found, e.g. %s" % (missing),))
        self.assertEqual(stage.input_problems(context({"pattern": "/p/$ERA", "path": missing}), files=False), ())

    def test_fixed_directory(self):
        from TauFW.Framework.stages.local import fixed_directory
        self.assertEqual(fixed_directory("/eos/tes/TES_variations/$ERA/$GROUP"), "/eos/tes/TES_variations")
        self.assertEqual(fixed_directory("/eos/tes/tuples_$ERA/$GROUP"), "/eos/tes")
        self.assertEqual(fixed_directory("/eos/tes"), "/eos/tes")


class ContextTests(LocalStageTestCase):
    def test_only_done_upstream_stages_are_passed(self):
        plots = connected(PLOTS, tuples="production")
        fw = self.framework(PRODUCTION, plots)
        record = fw.start(run_root=self.root)  # production SUBMITTED
        context = fw._context(record, recipe(PRODUCTION, plots).stage("plots"))
        self.assertEqual(context.upstream, {})
        self.assertEqual(context.run_dir, record.run_dir)
        record = fw.advance(record)
        context = fw._context(record, recipe(PRODUCTION, plots).stage("plots"))
        self.assertEqual([a["path"] for a in context.artifacts("production")],
                         [os.path.join(record.run_dir, "stages", "production", "2018", "DY", "DY_mutau.root")])
        self.assertEqual(context.input_artifacts("tuples"), context.artifacts("production"))
        self.assertEqual(context.artifacts(kind="shapes"), ())

    def test_a_stage_sees_only_the_stages_its_inputs_name(self):
        fw = self.framework(PRODUCTION, PLOTS)  # plots: tuples null, although the recipe has a production stage
        record = fw.advance(fw.start(run_root=self.root))
        self.assertEqual(record.stage("production").state, "DONE")
        context = fw._context(record, fw.recipe.stage("plots"))
        self.assertEqual((context.upstream, context.input_artifacts("tuples")), ({}, ()))
        self.assertNotIn("inputs", record.stage("plots").last_status)  # no production tuples recorded

    def test_output_dir_in_a_plan(self):  # no run yet: a placeholder, as for python steps
        self.framework(PLOTS).plan()
        self.assertEqual(self.plotter.call("plan")[0]["outdir"], os.path.join("<run_dir>", "stages", "plots"))

    def test_stage_dir(self):
        context = StageContext(run_dir="runs/x", stage_id="plots")
        self.assertEqual(context.stage_dir("fit"), os.path.join("runs/x", "stages", "fit"))
        self.assertEqual(context.stage_dir(), os.path.join("runs/x", "stages", "plots"))
        self.assertEqual(context.log_dir(), os.path.join("runs/x", "logs", "plots"))


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
        fit = recipe({"stage": "fit", "id": "fit", "inputs": {"shapes": None}}).stage("fit").spec
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
            json.dump({"name": "tes", "stages": [HISTOGRAMS, connected(FIT, shapes="histograms")]}, stream)
        self.fitter.problems = ("combine is not on PATH",)
        real = Framework.from_recipe
        self.cli.Framework.from_recipe = lambda r, reporter=None, **kw: real(r, reporter=reporter,
                                                                              fitter=self.fitter)
        try:
            self.assertEqual(self.cli.main(["plan", path]), 0)
        finally:
            self.cli.Framework.from_recipe = real
        tables = [text for kind, text in self.reporter.messages if kind == "table"]
        self.assertIn("['option', 'file', 'from']", tables[0])  # the files the stage reads come first
        self.assertIn("['configs', 'TauES_ID/config/config_coarse_TT.yml', 'module']", tables[0])
        commands = [text for text in tables if "['#', 'step', 'command']" in text]
        self.assertIn("shapes 2025 VTight Tight", commands[0])
        self.assertIn("Working directory: /repo/Fitter", [t for k, t in self.reporter.messages])
        self.assertIn("combine is not on PATH", self.warnings())
        messages = [t for k, t in self.reporter.messages if k == "message"]
        self.assertIn("Inputs: shapes <- histograms", messages)
        self.assertIn("Inputs: tuples <- outside this run (the tuples in $PICODIR of the run's PicoProducer "
                      "config)", messages)
        path = os.path.join(self.root, "external.json")
        os.makedirs(os.path.join(self.root, "tuples"))
        pattern = os.path.join(self.root, "tuples", "$ERA", "$GROUP")
        with open(path, "w") as stream:
            json.dump({"name": "tes", "stages": [dict(PLOTS, inputs={"tuples": {"external": pattern}})]}, stream)
        self.cli.Framework.from_recipe = lambda r, reporter=None, **kw: real(r, reporter=reporter,
                                                                              plotter=self.plotter)
        try:
            self.assertEqual(self.cli.main(["plan", path]), 0)
        finally:
            self.cli.Framework.from_recipe = real
        self.assertIn("Inputs: tuples <- external %s" % (pattern),
                      [t for k, t in self.reporter.messages if k == "message"])

    def test_check_lists_every_problem(self):
        path = os.path.join(self.root, "r.json")
        with open(path, "w") as stream:
            json.dump({"name": "tes", "stages": [dict(HISTOGRAMS, id="a/b"), dict(FIT, inputs=None)]}, stream)
        self.assertEqual(self.cli.main(["check", path]), 1)
        self.assertEqual(self.warnings(), [
            "Warning: run_root: not set: the runs go to taufw_runs/ in the directory taufw.py is started from. "
            "Set run_root: <absolute directory> in the recipe, or start with --run-root",
            "Recipe tes: 2 problem(s)",
            "  stages[0] (histograms).id: must be a word of letters, digits, '_', '.' or '-' (got 'a/b')",
            "  stages[1] (fit).inputs: fit reads shapes: write inputs: {shapes: <stage id or null>}"])
        self.assertEqual(self.cli.main(["plan", path]), 1)  # an invalid recipe: the problems, no traceback
        self.assertIn("r.json: 2 problems", self.warnings()[-1])
        with open(path, "w") as stream:
            json.dump({"name": "tes", "stages": [HISTOGRAMS]}, stream)
        self.assertEqual(self.cli.main(["check", path]), 0)

    def test_command_line_shows_python3_and_environment(self):
        import sys
        from TauFW.Utilities.Process import Command
        command = Command("plots", (sys.executable, "plot.py", "-S", "a b"), "/repo/Plotter")
        self.assertEqual(self.cli._command_line(command), "python3 plot.py -S 'a b'")
        command = Command("plots", (sys.executable, "plot.py"), "/repo/Plotter",
                          env=(("TAUFW_PICO_CONFIG", "/b/pico.json"),))
        self.assertEqual(self.cli._command_line(command), "TAUFW_PICO_CONFIG=/b/pico.json python3 plot.py")

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
