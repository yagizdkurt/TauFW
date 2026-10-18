"""Analysis bundles: the path rule, stage ids, the run's bundle copy, the PicoProducer config of the scripts and
taufw.py init, driven by fake module APIs (no ROOT, no scripts)."""
import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

import checkout  # noqa: F401  (must precede TauFW imports)
import fakes
from TauFW.Framework import Framework, Recipe, RecipeError, RunRecord, SilentReporter
from TauFW.Framework.bundle import resolve, where, bundle_files, BundleError
from TauFW.Framework.stages import PlotStage, ShapesStage, FitStage
from test_framework import Clock

SHAPES = {"stage": "shapes", "id": "shapes", "inputs": {"tuples": None}, "eras": [2025],
              "jet_wps": ["VTight"], "ele_wps": ["Tight"], "configs": ["tt.yml", "mm.yml"]}
FIT = {"stage": "fit", "id": "fit", "inputs": {"shapes": "shapes"}, "config": "tt.yml", "config_mumu": "mm.yml",
       "steps": ["fit"]}
PLOTS = {"stage": "plots", "id": "plots", "inputs": {"tuples": None}, "eras": [2025],
         "configs": ["mutau", "setup_mumu.yml"]}
STEP = {"stage": "python", "id": "check", "inputs": None, "file": "steps/check.py"}


class BundleTestCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="taufw-test-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.bundle = os.path.join(self.root, "Analyses", "tes")
        for path in ("tt.yml", "mm.yml", "setup_mumu.yml",
                     "pico.json"):
            self.write(path, "original %s\n" % (path))
        self.plotter = fakes.FakePlotter()
        self.fitter = fakes.FakeFitter()
        self.reporter = SilentReporter()

    def write(self, relative, text, base=None):
        path = os.path.join(base or self.bundle, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as stream:
            stream.write(text)
        return path

    def recipe(self, *stages, pico=None):
        self.write("recipe.yml", json.dumps({"name": "tes", "pico": {"config": pico}, "stages": list(stages)}))
        return Recipe.load(self.bundle)

    def framework(self, recipe):
        stages = {"plots": PlotStage(self.plotter), "shapes": ShapesStage(self.fitter),
                  "fit": FitStage(self.fitter)}
        return Framework(recipe, {s.id: stages[s.id] for s in recipe.stages}, reporter=self.reporter,
                         sleep=lambda s: None, clock=Clock())


class PathRuleTests(BundleTestCase):
    def test_bundle_module_absolute(self):
        self.assertEqual(where("tt.yml", self.bundle), "bundle")
        self.assertEqual(resolve("tt.yml", self.bundle),
                         os.path.normpath(os.path.join(self.bundle, "tt.yml")))
        self.assertEqual(where("TauES/config/FitSetup_mumu.yml", self.bundle), "module")  # not in the bundle
        self.assertEqual(resolve("TauES/config/FitSetup_mumu.yml", self.bundle), "TauES/config/FitSetup_mumu.yml")
        self.assertEqual(resolve("mutau", self.bundle), "mutau")  # a Plotter channel name
        absolute = os.path.join(self.root, "x.yml")
        self.assertEqual((where(absolute, self.bundle), resolve(absolute, self.bundle)), ("absolute", absolute))
        self.write("sub/dir/x.yml", "x")  # any layout inside the bundle works
        self.assertEqual(where("sub/dir/x.yml", self.bundle), "bundle")
        self.assertEqual(where("sub", self.bundle), "module")  # a directory is not a bundle file
        outside = self.write("outside.yml", "x", base=self.root)  # exists, but above the bundle
        self.assertEqual(where(os.path.join("..", "..", "outside.yml"), self.bundle), "module")
        self.assertTrue(os.path.isfile(outside))
        self.assertEqual(resolve("tt.yml", None), "tt.yml")  # no bundle

    def test_plan_resolves_against_the_bundle(self):
        fw = self.framework(self.recipe(PLOTS, SHAPES, FIT, pico="pico.json"))
        plan = fw.plan()
        self.assertEqual(plan.bundle_dir, self.bundle)
        self.assertEqual(plan.pico_config, os.path.join(self.bundle, "pico.json"))
        plots = plan.stages[0]
        self.assertEqual([(row[1], row[3]) for row in plots.paths],
                         [("mutau", "module"), ("setup_mumu.yml", "bundle")])
        tt = os.path.normpath(os.path.join(self.bundle, "tt.yml"))
        request = self.fitter.call("plan_shapes")[0]
        self.assertEqual(request["configs"][0], tt)
        self.assertEqual(request["pico_config"], plan.pico_config)
        self.assertEqual(self.fitter.call("plan_fit")[0]["config"], tt)
        # the fit finds its points in the planned shapes of the same (resolved) configs
        self.assertEqual(self.fitter.call("plan_fit")[0]["points"], (("2025", "VTight", "Tight"),))

    def test_bundle_files(self):
        recipe = self.recipe(PLOTS, SHAPES, FIT, pico="pico.json")
        self.assertEqual(bundle_files(recipe), tuple(os.path.normpath(p) for p in (
            "pico.json", "setup_mumu.yml", "tt.yml",
            "mm.yml")))


class RunSnapshotTests(BundleTestCase):
    def test_run_reads_its_copy_of_the_bundle(self):
        recipe = self.recipe(SHAPES, pico="pico.json")
        self.fitter.problems = ("not ready",)  # stays NEW: the run is continued below, after the edit
        record = self.framework(recipe).start(run_root=os.path.join(self.root, "runs"))
        copy = os.path.join(record.run_dir, "bundle")
        self.assertEqual(record.bundle["source"], self.bundle)
        self.assertEqual(sorted(record.bundle["files"]), sorted(os.path.normpath(p) for p in (  # the whole bundle
            "pico.json", "tt.yml", "mm.yml", "setup_mumu.yml",
            "recipe.yml")))
        self.write("tt.yml", "edited after the start\n")
        self.fitter.problems = ()
        loaded = RunRecord.load(record.run_dir)
        record = Framework.from_record(loaded, reporter=self.reporter, fitter=self.fitter).advance(loaded)
        self.assertEqual(record.stage("shapes").state, "DONE")
        request = self.fitter.call("make_shapes")[0]
        self.assertEqual(request["configs"][0], os.path.join(copy, os.path.normpath("tt.yml")))
        self.assertEqual(request["pico_config"], os.path.join(copy, "pico.json"))
        with open(request["configs"][0]) as stream:
            self.assertEqual(stream.read(), "original tt.yml\n")
        # run.json keeps the recipe as written
        self.assertEqual(loaded.recipe["stages"][0]["configs"], SHAPES["configs"])

    def test_snapshot_skips_caches_and_refuses_large_bundles(self):
        self.write("steps/__pycache__/x.pyc", "cache")
        self.write(".git/config", "hidden")
        self.write("taufw_runs/old/run.json", "{}")
        recipe = self.recipe(SHAPES)
        record = self.framework(recipe).start(run_root=os.path.join(self.root, "runs"))
        self.assertFalse([f for f in record.bundle["files"] if "pycache" in f or ".git" in f or "taufw_runs" in f])
        with mock.patch("TauFW.Framework.bundle.MAX_BUNDLE_BYTES", 10):
            with self.assertRaises(BundleError):
                self.framework(recipe).start(run_root=os.path.join(self.root, "big"))
        self.assertFalse(os.path.exists(os.path.join(self.root, "big")))  # nothing was created

    def test_pico_config_above_the_bundle_stays_outside_the_run(self):
        pico = self.write("PicoProducer/config/config.json", "{}", base=self.root)
        recipe = self.recipe(SHAPES, pico="../../PicoProducer/config/config.json")
        self.assertEqual(recipe.pico_config, os.path.normpath(pico))  # made absolute when loaded
        record = self.framework(recipe).start(run_root=os.path.join(self.root, "runs"))
        self.assertFalse([f for f in record.bundle["files"] if f.startswith("..")])
        self.assertEqual(self.fitter.call("make_shapes")[0]["pico_config"], os.path.normpath(pico))

    def test_old_run_json_without_bundle(self):
        recipe = self.recipe(SHAPES)
        record = self.framework(recipe).start(run_root=os.path.join(self.root, "runs"))
        with open(record.path) as stream:
            data = json.load(stream)
        del data["bundle"]
        with open(record.path, "w") as stream:
            json.dump(data, stream)
        self.assertEqual(RunRecord.load(record.run_dir).bundle, {})

    def test_recipe_file_without_bundle_files(self):
        path = self.write("plain.json", json.dumps({"name": "plain", "stages": [
            dict(SHAPES, configs=["TauES_ID/config/config_coarse_TT.yml"])]}), base=self.root)
        record = self.framework(Recipe.load(path)).start(run_root=os.path.join(self.root, "runs"))
        self.assertEqual(record.bundle["files"], [])
        self.assertEqual(self.fitter.call("make_shapes")[0]["configs"], ["TauES_ID/config/config_coarse_TT.yml"])


class StageIdTests(BundleTestCase):
    def error(self, *stages):
        with self.assertRaises(RecipeError) as context:
            Recipe.from_dict({"name": "x", "stages": list(stages)}, source="r.yml")
        return str(context.exception)

    def test_python_steps_anywhere_with_ids(self):
        histograms = dict(SHAPES, id="shapes_tight", description="the Tight working points")
        recipe = Recipe.from_dict({"name": "x", "stages": [
            STEP, histograms, dict(STEP, id="check_again", inputs={"shapes": "shapes_tight"}),
            dict(FIT, inputs={"shapes": "shapes_tight"}),
            dict(STEP, id="summary", file="steps/summary.py", inputs={"fit": "fit", "shapes": "shapes_tight"})]})
        self.assertEqual([s.id for s in recipe.stages], ["check", "shapes_tight", "check_again", "fit", "summary"])
        self.assertEqual(recipe.stage("check_again").stage, "python")
        self.assertEqual(recipe.first("shapes").id, "shapes_tight")  # a built-in stage may have any id
        self.assertEqual(recipe.stage("shapes_tight").description, "the Tight working points")
        self.assertEqual(recipe.stage("summary").connections, {"fit": "fit", "shapes": "shapes_tight"})
        self.assertEqual(recipe.stage("check").connections, {})
        data = recipe.to_dict()
        self.assertEqual(list(data["stages"][1])[:4], ["stage", "id", "description", "inputs"])
        self.assertNotIn("description", data["stages"][0])  # optional: written only if given
        self.assertIsNone(data["stages"][0]["inputs"])
        self.assertEqual(Recipe.from_dict(data).to_dict(), data)

    def test_id_errors(self):
        self.assertIn("stages[1] (python).id: 'check' is already the id of stages[0]", self.error(STEP, STEP))
        self.assertIn("stages[0] (python): missing 'id'", self.error({"stage": "python", "inputs": None,
                                                                     "file": "steps/check.py"}))
        self.assertIn("stages[0] (python).id: must be a word", self.error(dict(STEP, id="a b")))
        self.assertIn("stages[0] (python).id: '..' is not allowed (it names a directory)",
                      self.error(dict(STEP, id="..")))
        recipe = Recipe.from_dict({"name": "x", "stages": [dict(STEP, id="bundle"), dict(STEP, id="logs")]})
        self.assertEqual([s.id for s in recipe.stages], ["bundle", "logs"])  # stages/<id>: no clash in the run
        recipe = Recipe.from_dict({"name": "x", "stages": [dict(FIT, inputs={"shapes": None}), STEP, SHAPES]})
        self.assertEqual([s.stage for s in recipe.stages], ["fit", "python", "shapes"])  # no fixed order (R4)
        self.assertIn("unknown stage 'pyhton' (known: production, plots, shapes, fit, python)",
                      self.error({"stage": "pyhton"}))
        self.assertIn("stages[0]: stage 'histograms' no longer exists: renamed 'shapes' (CL §24)",
                      self.error(dict(SHAPES, stage="histograms")))  # the name before CL §24 (S4a)
        self.assertIn("file must be a .py file", self.error(dict(STEP, file="steps/check.sh")))
        self.assertIn("missing required option 'file'", self.error({"stage": "python", "id": "x", "inputs": None}))
        self.assertIn("description: must be text", self.error(dict(STEP, description=["a"])))

    def test_input_errors(self):
        production = {"stage": "production", "id": "production", "inputs": None, "eras": [2025],
                      "channels": ["mutau"]}
        message = self.error(
            dict(production, inputs={"tuples": None}),                          # production reads nothing
            dict(SHAPES, inputs={"tuples": "production", "shapes": None}),  # unknown slot
            dict(FIT, inputs={"shapes": "production"}),                         # wrong kind of data
            dict(STEP, inputs={}),                                              # empty: write null
            dict(STEP, id="late", inputs={"x": "later", "y": None, "z": "late", "w": "nowhere"}),
            dict(STEP, id="later"))
        self.assertIn("r.yml: 8 problems", message)
        for text in ("stages[0] (production).inputs: production reads no other stage's output: write inputs: null",
                     "stages[1] (shapes).inputs.shapes: unknown input (shapes has: tuples)",
                     "stages[2] (fit).inputs.shapes: stage 'production' (production) makes tuples, not shapes",
                     "stages[3] (python).inputs: is empty: write inputs: null",
                     "stages[4] (python).inputs.y: must name an earlier stage",
                     "stages[4] (python).inputs.x: stage 'later' comes after this one",
                     "stages[4] (python).inputs.z: a stage cannot read its own output",
                     "stages[4] (python).inputs.w: no stage 'nowhere' in the recipe"):
            self.assertIn(text, message)
        self.assertIn("stages[0] (fit).inputs: missing (write inputs: {shapes: <stage id, {path: <stage directory>} or "
                      "null>})",
                      self.error({"stage": "fit", "id": "fit"}))
        self.assertIn("stages[0] (fit).inputs.shapes: missing (the id of an earlier stage, or null)",
                      self.error({"stage": "fit", "id": "fit", "inputs": {"shape": None}}))
        self.assertIn("stages[0] (plots).inputs: plots reads tuples: write inputs: {tuples: <stage id, {path: <stage "
                      "directory>}, {external: <pattern>} or null>}",
                      self.error(dict(PLOTS, inputs=None)))

    def test_null_only_where_the_stage_allows_it(self):
        self.assertEqual(Recipe.from_dict({"name": "x", "stages": [dict(FIT, inputs={"shapes": None})]})
                         .stages[0].inputs, {"shapes": None})  # the fit's temporary exception
        with mock.patch.object(FitStage, "null_inputs", {}):  # a slot that must name a stage
            self.assertIn("stages[0] (fit).inputs.shapes: must name an earlier stage that makes shapes (null is "
                          "not allowed for this input)", self.error(dict(FIT, inputs={"shapes": None})))
            self.assertIn("stages[0] (fit).inputs: missing (write inputs: {shapes: <stage id, {path: <stage "
                          "directory>}>})",
                          self.error({"stage": "fit", "id": "fit"}))
            self.assertIn("stages[0] (fit).inputs.shapes: missing (the id of an earlier stage)",
                          self.error({"stage": "fit", "id": "fit", "inputs": {"shape": None}}))

    def test_path_inputs(self):
        """R4: {path: <stage directory>} names another run's stage directory: absolute, as written, any slot."""
        source = os.path.join(self.root, "runs", "r1", "stages", "shapes")
        fit = dict(FIT, inputs={"shapes": {"path": source}})
        step = dict(STEP, inputs={"fit": {"path": source}, "shapes": "shapes"})
        recipe = Recipe.from_dict({"name": "x", "stages": [SHAPES, fit, step]})
        self.assertEqual(recipe.stage("fit").inputs, {"shapes": {"path": source}})
        self.assertEqual(recipe.stage("fit").connections, {"shapes": None})  # not a stage of this run
        self.assertEqual(recipe.stage("fit").paths, {"shapes": source})
        self.assertEqual(recipe.stage("check").paths, {"fit": source})
        self.assertEqual(Recipe.from_dict(recipe.to_dict()), recipe)  # as written, also in run.json
        self.assertEqual(Recipe.from_dict(recipe.to_dict(), bundle_dir=os.path.join(self.root, "run", "bundle"))
                         .stage("fit").paths, {"shapes": source})
        tuples = dict(PLOTS, inputs={"tuples": {"path": os.path.join(self.root, "runs", "r1", "stages", "prod")}})
        self.assertEqual(Recipe.from_dict({"name": "x", "stages": [tuples]}).stage("plots").connections,
                         {"tuples": None})
        where = "stages[0] (fit).inputs.shapes: "
        for value, message in (
                ("../runs/r1/stages/shapes", "path must be absolute (got ../runs/r1/stages/shapes; "
                                                 "relative paths are not allowed, and ~ and $VARIABLES are not "
                                                 "expanded)"),
                ("~/taufw_runs/r1/stages/shapes", "path must be absolute (got ~/taufw_runs/r1/stages/shapes; "
                                                      "relative paths are not allowed, and ~ and $VARIABLES are "
                                                      "not expanded)"),
                ("$HOME/r1", "path must be absolute (got $HOME/r1; relative paths are not allowed, and ~ and "
                             "$VARIABLES are not expanded)"),
                ("root://eosuser.cern.ch//eos/r1", "path must be a directory on a mounted file system, not a URL "
                                                   "(got root://eosuser.cern.ch//eos/r1)"),
                ("", "path must be the absolute stage directory of another run, e.g. "
                     "/afs/.../taufw_runs/<run>/stages/shapes (got '')"),
                (1, "path must be the absolute stage directory of another run, e.g. "
                    "/afs/.../taufw_runs/<run>/stages/shapes (got 1)")):
            with self.subTest(value=value):
                self.assertEqual(self.error(dict(FIT, inputs={"shapes": {"path": value}})),
                                 "r.yml: " + where + message)
        self.assertEqual(self.error(dict(FIT, inputs={"shapes": {"dir": source}})),
                         "r.yml: " + where + "a mapping is {path: <stage directory>} (got keys dir)")
        self.assertEqual(self.error(dict(FIT, inputs={"shapes": {"path": source, "run": "r1"}})),
                         "r.yml: " + where + "a mapping is {path: <stage directory>} (got keys path, run)")

    def test_path_input_inside_the_bundle(self):
        inside = os.path.join(self.bundle, "old_run", "stages", "shapes")
        fit = dict(FIT, inputs={"shapes": {"path": inside}})
        with self.assertRaises(RecipeError) as context:
            self.recipe(fit)
        self.assertEqual(str(context.exception), "tes/recipe.yml: stages[0] (fit).inputs.shapes: %s is inside the "
                         "bundle %s: an input names another run's stage directory, and data is never part of a "
                         "bundle" % (inside, self.bundle))
        loose = self.write("loose.yml", json.dumps({"name": "x", "stages": [fit]}), base=self.root)
        self.assertEqual(Recipe.load(loose).stage("fit").paths, {"shapes": inside})  # not a bundle: allowed


class MakeBundleTests(BundleTestCase):
    def setUp(self):
        super().setUp()
        self.modules = os.path.join(self.root, "modules")
        self.fitter.basedir = os.path.join(self.modules, "Fitter")
        self.plotter.basedir = os.path.join(self.modules, "Plotter")
        for path in ("Fitter/TauES_ID/config/config_coarse_TT.yml", "Fitter/TauES/config/FitSetup_mumu.yml",
                     "Plotter/mutau"):
            self.write(path, "module %s\n" % (path), base=self.modules)

    def test_make_bundle_copies_the_module_configs(self):
        source = self.write("old.json", json.dumps({"name": "old", "stages": [
            dict(PLOTS, configs=["mutau"]),
            dict(SHAPES, configs=["TauES_ID/config/config_coarse_TT.yml", "TauES/config/FitSetup_mumu.yml"]),
            {"stage": "fit", "id": "fit", "inputs": {"shapes": "shapes"},
             "config": "TauES_ID/config/config_coarse_TT.yml",
             "config_mumu": "TauES/config/FitSetup_mumu.yml"}]}), base=self.root)
        target = os.path.join(self.root, "Analyses", "new_one")
        copied = self.framework(Recipe.load(source)).make_bundle(target)
        self.assertEqual(copied, ("FitSetup_mumu.yml", "config_coarse_TT.yml",
                                  "mutau"))
        recipe = Recipe.load(target)
        self.assertEqual(recipe.name, "new_one")
        self.assertEqual(recipe.stage("fit").options["config"], "config_coarse_TT.yml")
        self.assertEqual(recipe.stage("shapes").options["configs"],
                         ["config_coarse_TT.yml", "FitSetup_mumu.yml"])
        self.assertEqual(set(bundle_files(recipe)), {os.path.normpath(p) for p in copied})
        with open(os.path.join(target, "config_coarse_TT.yml")) as stream:
            self.assertEqual(stream.read(), "module Fitter/TauES_ID/config/config_coarse_TT.yml\n")
        self.assertTrue(os.path.isfile(os.path.join(target, "steps", "example.py")))
        with self.assertRaises(BundleError):
            self.framework(Recipe.load(source)).make_bundle(target)

    def test_make_bundle_copies_the_source_bundle(self):  # its own files too, e.g. copies of Configs/ templates
        self.write("steps/check.py", "def run(ctx):\n    pass\n")
        self.write("samples/v15_2025.yml", "taufw_config: {}\n")
        self.write("__pycache__/x.pyc", "")
        source = self.recipe(dict(PLOTS, configs=["mutau", "setup_mumu.yml"]), pico="pico.json")  # steps/: files
        target = os.path.join(self.root, "Analyses", "copy")
        copied = self.framework(source).make_bundle(target)
        self.assertEqual(sorted(copied), sorted(os.path.normpath(path) for path in [
            "mm.yml", "mutau", "pico.json", "samples/v15_2025.yml", "setup_mumu.yml", "steps/check.py", "tt.yml"]))
        recipe = Recipe.load(target)
        self.assertEqual(recipe.stage("plots").options["configs"], ["mutau", "setup_mumu.yml"])
        self.assertEqual(where("setup_mumu.yml", target), "bundle")
        self.assertEqual(recipe.pico_config, "pico.json")
        self.assertFalse(os.path.exists(os.path.join(target, "__pycache__")))
        self.assertFalse(os.path.exists(os.path.join(target, "steps", "example.py")))  # the source has steps
        with open(os.path.join(target, "setup_mumu.yml")) as stream:
            self.assertEqual(stream.read(), "original setup_mumu.yml\n")

    def test_copied_names_do_not_clash(self):
        from TauFW.Framework.bundle import _free_name
        taken = []
        for group, source in (("fitter", "/m/Fitter/A/cfg.yml"), ("plotter", "/m/Plotter/cfg.yml"),
                              ("fitter", "/m/Fitter/B/cfg.yml"), ("fitter", "/m/Fitter/A2/x/cfg.yml"),
                              ("fitter", "/m/Fitter/recipe.yml")):
            taken.append(_free_name(taken, group, source))
        self.assertEqual(taken, ["cfg.yml", "plotter_cfg.yml", "fitter_cfg.yml", "fitter_x_cfg.yml",
                                 "fitter_recipe.yml"])  # never recipe.yml

    def test_init_command(self):
        spec = importlib.util.spec_from_file_location("taufw_cli", str(checkout.TAUFW_SCRIPT))
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        cli.FrameworkReporter = lambda verbosity=0: self.reporter
        root = os.path.join(self.root, "Analyses")
        self.assertEqual(cli.main(["init", "fresh", "--root", root]), 0)
        recipe = Recipe.load(os.path.join(root, "fresh"))
        self.assertEqual((recipe.name, [s.id for s in recipe.stages]), ("fresh", ["example"]))
        self.assertEqual(where("steps/example.py", recipe.bundle_dir), "bundle")
        self.assertEqual(cli.main(["init", "fresh", "--root", root]), 1)  # exists
        self.assertEqual(cli.main(["init", "bad name", "--root", root]), 1)
        self.assertFalse(os.path.exists(os.path.join(root, "bad name")))


if __name__ == "__main__":
    unittest.main()
