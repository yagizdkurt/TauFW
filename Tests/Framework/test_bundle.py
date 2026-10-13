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
from TauFW.Framework.stages import PlotStage, HistogramStage, FitStage
from test_framework import Clock

HISTOGRAMS = {"stage": "histograms", "eras": [2025], "jet_wps": ["VTight"], "ele_wps": ["Tight"],
              "configs": ["tt.yml", "mm.yml"]}
FIT = {"stage": "fit", "config": "tt.yml", "config_mumu": "mm.yml",
       "steps": ["fit"]}
PLOTS = {"stage": "plots", "eras": [2025], "configs": ["mutau", "setup_mumu.yml"]}


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
        stages = {"plots": PlotStage(self.plotter), "histograms": HistogramStage(self.fitter),
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
        fw = self.framework(self.recipe(PLOTS, HISTOGRAMS, FIT, pico="pico.json"))
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
        recipe = self.recipe(PLOTS, HISTOGRAMS, FIT, pico="pico.json")
        self.assertEqual(bundle_files(recipe), tuple(os.path.normpath(p) for p in (
            "pico.json", "setup_mumu.yml", "tt.yml",
            "mm.yml")))


class RunSnapshotTests(BundleTestCase):
    def test_run_reads_its_copy_of_the_bundle(self):
        recipe = self.recipe(HISTOGRAMS, pico="pico.json")
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
        self.assertEqual(record.stage("histograms").state, "DONE")
        request = self.fitter.call("make_shapes")[0]
        self.assertEqual(request["configs"][0], os.path.join(copy, os.path.normpath("tt.yml")))
        self.assertEqual(request["pico_config"], os.path.join(copy, "pico.json"))
        with open(request["configs"][0]) as stream:
            self.assertEqual(stream.read(), "original tt.yml\n")
        # run.json keeps the recipe as written
        self.assertEqual(loaded.recipe["stages"][0]["configs"], HISTOGRAMS["configs"])

    def test_snapshot_skips_caches_and_refuses_large_bundles(self):
        self.write("steps/__pycache__/x.pyc", "cache")
        self.write(".git/config", "hidden")
        self.write("taufw_runs/old/run.json", "{}")
        recipe = self.recipe(HISTOGRAMS)
        record = self.framework(recipe).start(run_root=os.path.join(self.root, "runs"))
        self.assertFalse([f for f in record.bundle["files"] if "pycache" in f or ".git" in f or "taufw_runs" in f])
        with mock.patch("TauFW.Framework.bundle.MAX_BUNDLE_BYTES", 10):
            with self.assertRaises(BundleError):
                self.framework(recipe).start(run_root=os.path.join(self.root, "big"))
        self.assertFalse(os.path.exists(os.path.join(self.root, "big")))  # nothing was created

    def test_pico_config_above_the_bundle_stays_outside_the_run(self):
        pico = self.write("PicoProducer/config/config.json", "{}", base=self.root)
        recipe = self.recipe(HISTOGRAMS, pico="../../PicoProducer/config/config.json")
        self.assertEqual(recipe.pico_config, os.path.normpath(pico))  # made absolute when loaded
        record = self.framework(recipe).start(run_root=os.path.join(self.root, "runs"))
        self.assertFalse([f for f in record.bundle["files"] if f.startswith("..")])
        self.assertEqual(self.fitter.call("make_shapes")[0]["pico_config"], os.path.normpath(pico))

    def test_old_run_json_without_bundle(self):
        recipe = self.recipe(HISTOGRAMS)
        record = self.framework(recipe).start(run_root=os.path.join(self.root, "runs"))
        with open(record.path) as stream:
            data = json.load(stream)
        del data["bundle"]
        with open(record.path, "w") as stream:
            json.dump(data, stream)
        self.assertEqual(RunRecord.load(record.run_dir).bundle, {})

    def test_recipe_file_without_bundle_files(self):
        path = self.write("plain.json", json.dumps({"name": "plain", "stages": [
            dict(HISTOGRAMS, configs=["TauES_ID/config/config_coarse_TT.yml"])]}), base=self.root)
        record = self.framework(Recipe.load(path)).start(run_root=os.path.join(self.root, "runs"))
        self.assertEqual(record.bundle["files"], [])
        self.assertEqual(self.fitter.call("make_shapes")[0]["configs"], ["TauES_ID/config/config_coarse_TT.yml"])


class StageIdTests(BundleTestCase):
    def error(self, *stages):
        with self.assertRaises(RecipeError) as context:
            Recipe.from_dict({"name": "x", "stages": list(stages)}, source="r.yml")
        return str(context.exception)

    def test_python_steps_anywhere_with_ids(self):
        step = {"stage": "python", "file": "steps/check.py"}
        recipe = Recipe.from_dict({"name": "x", "stages": [
            step, HISTOGRAMS, dict(step, id="check_again"), FIT, dict(step, file="steps/summary.py")]})
        self.assertEqual([s.id for s in recipe.stages], ["check", "histograms", "check_again", "fit", "summary"])
        self.assertEqual(recipe.stage("check_again").stage, "python")
        data = recipe.to_dict()
        self.assertNotIn("id", data["stages"][0])  # the default id is not written
        self.assertEqual(data["stages"][2]["id"], "check_again")
        self.assertEqual(Recipe.from_dict(data).to_dict(), data)

    def test_id_errors(self):
        step = {"stage": "python", "file": "steps/check.py"}
        self.assertIn("appears more than once", self.error(step, dict(step)))
        self.assertIn("is the name of a stage", self.error(dict(step, id="fit")))
        self.assertIn("cannot have another id", self.error(dict(HISTOGRAMS, id="shapes")))
        self.assertIn("'id' must be a word", self.error(dict(step, id="a b")))
        self.assertIn("must be in the order", self.error(FIT, step, HISTOGRAMS))
        self.assertIn("unknown stage 'pyhton' (known: production, plots, histograms, fit, python)",
                      self.error({"stage": "pyhton"}))
        self.assertIn("file must be a .py file", self.error({"stage": "python", "file": "steps/check.sh"}))
        self.assertIn("missing required option 'file'", self.error({"stage": "python"}))


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
            {"stage": "plots", "eras": [2025], "configs": ["mutau"]},
            {"stage": "histograms", "eras": [2025], "jet_wps": ["VTight"], "ele_wps": ["Tight"],
             "configs": ["TauES_ID/config/config_coarse_TT.yml", "TauES/config/FitSetup_mumu.yml"]},
            {"stage": "fit", "config": "TauES_ID/config/config_coarse_TT.yml",
             "config_mumu": "TauES/config/FitSetup_mumu.yml"}]}), base=self.root)
        target = os.path.join(self.root, "Analyses", "new_one")
        copied = self.framework(Recipe.load(source)).make_bundle(target)
        self.assertEqual(copied, ("FitSetup_mumu.yml", "config_coarse_TT.yml",
                                  "mutau"))
        recipe = Recipe.load(target)
        self.assertEqual(recipe.name, "new_one")
        self.assertEqual(recipe.stage("fit").options["config"], "config_coarse_TT.yml")
        self.assertEqual(recipe.stage("histograms").options["configs"],
                         ["config_coarse_TT.yml", "FitSetup_mumu.yml"])
        self.assertEqual(set(bundle_files(recipe)), {os.path.normpath(p) for p in copied})
        with open(os.path.join(target, "config_coarse_TT.yml")) as stream:
            self.assertEqual(stream.read(), "module Fitter/TauES_ID/config/config_coarse_TT.yml\n")
        self.assertTrue(os.path.isfile(os.path.join(target, "steps", "example.py")))
        with self.assertRaises(BundleError):
            self.framework(Recipe.load(source)).make_bundle(target)

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
