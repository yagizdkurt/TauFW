"""Recipe validation (validation.py): every problem of a recipe file, the files it names included."""
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

import checkout
from TauFW.Framework import check_recipe

FIT = {"stage": "fit", "id": "fit", "inputs": {"shapes": None}}
STEP = {"stage": "python", "id": "check", "inputs": None, "file": "steps/check.py"}


class CheckRecipeTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="taufw-test-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.bundle = os.path.join(self.root, "tes")

    def write(self, relative, text):
        path = os.path.join(self.bundle, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as stream:
            stream.write(text)
        return path

    def check(self, *stages, pico=None, name="tes"):
        self.write("recipe.yml", json.dumps({"name": name, "pico": {"config": pico}, "stages": list(stages)}))
        return check_recipe(self.bundle)

    def messages(self, check):
        return [str(issue) for issue in check.issues]

    def check_root(self, run_root):
        self.write("recipe.yml", json.dumps({"name": "tes", "run_root": run_root, "stages": [FIT]}))
        return check_recipe(self.bundle)

    def test_run_root(self):
        check = self.check_root("/afs/cern.ch/work/u/user/taufw_runs")  # absolute on lxplus (also on Windows)
        self.assertEqual((self.messages(check), check.warnings), ([], ()))
        self.assertEqual(check.recipe.run_root_dir, "/afs/cern.ch/work/u/user/taufw_runs")
        self.assertEqual(check.recipe.to_dict()["run_root"], "/afs/cern.ch/work/u/user/taufw_runs")
        for value in (None, "missing"):  # not set: a warning, not a problem
            with self.subTest(run_root=value):
                if value is None:
                    check = self.check_root(None)
                else:
                    check = self.check(FIT)
                self.assertTrue(check.ok)
                self.assertEqual([str(w) for w in check.warnings], [
                    "run_root: not set: the runs go to taufw_runs/ in the directory taufw.py is started from. "
                    "Set run_root: <absolute directory> in the recipe, or start with --run-root"])
                self.assertIsNone(check.recipe.run_root)
                self.assertNotIn("run_root", check.recipe.to_dict())

    def test_run_root_with_variables_is_expanded_with_a_warning(self):
        with mock.patch.dict(os.environ, {"TAUFW_TEST_ROOT": self.root}):
            check = self.check_root("$TAUFW_TEST_ROOT/runs")
            self.assertTrue(check.ok)
            expanded = self.root + "/runs"
            self.assertEqual(check.recipe.run_root_dir, expanded)
            self.assertEqual(check.recipe.run_root, "$TAUFW_TEST_ROOT/runs")  # as written (saved in run.json)
            self.assertEqual([str(w) for w in check.warnings], [
                "run_root: $TAUFW_TEST_ROOT/runs is expanded where taufw.py runs (here: %s); someone else, or "
                "another machine, gets another directory" % (expanded)])
        check = self.check_root("~/taufw_runs")
        self.assertTrue(check.ok)
        self.assertEqual(check.recipe.run_root_dir, os.path.expanduser("~/taufw_runs"))
        self.assertIn("is expanded where taufw.py runs", str(check.warnings[0]))

    def test_external_tuples(self):
        os.makedirs(os.path.join(self.root, "tuples", "2025"))
        pattern = os.path.join(self.root, "tuples", "$ERA", "$GROUP")
        plots = {"stage": "plots", "id": "plots", "inputs": {"tuples": {"external": pattern}}, "eras": [2025]}
        check = self.check(plots)
        self.assertEqual(self.messages(check), [])
        self.assertEqual(check.recipe.stage("plots").external, {"tuples": pattern})
        missing = os.path.join(self.root, "missing", "$ERA")
        check = self.check(dict(plots, inputs={"tuples": {"external": missing}}))
        self.assertEqual(self.messages(check), ["stages[0] (plots).inputs.tuples: tuple directory %s not found "
                                                "(external: %s)" % (os.path.join(self.root, "missing"), missing)])
        where = "stages[0] (plots).inputs.tuples: "
        for value, message in (
                ({"external": "tuples/$ERA"}, "external must be an absolute directory pattern (got tuples/$ERA; ~ "
                                              "and $VARIABLES at the start are not expanded)"),
                ({"external": "$PICODIR/$ERA"}, "external must be an absolute directory pattern (got "
                                                "$PICODIR/$ERA; ~ and $VARIABLES at the start are not expanded)"),
                ({"external": "root://eoscms.cern.ch//eos/x/$ERA"},
                 "external must be a directory on a mounted file system, not a URL (got "
                 "root://eoscms.cern.ch//eos/x/$ERA)"),
                ({"external": ""}, "external must be an absolute directory pattern, e.g. /eos/.../$ERA/$GROUP "
                                   "(got '')"),
                ({"external": pattern, "path": "x"}, "a mapping is {external: <absolute pattern>} (got keys "
                                                     "external, path)"),
                ({"path": "x"}, "a mapping is {external: <absolute pattern>} (got keys path)")):
            with self.subTest(value=value):
                self.assertEqual(self.messages(self.check(dict(plots, inputs={"tuples": value}))),
                                 [where + message])
        self.assertEqual(self.messages(self.check(dict(FIT, inputs={"shapes": {"external": pattern}}))),
                         ["stages[0] (fit).inputs.shapes: {external: ...} is only for a tuples input (plots, "
                          "histograms); name an earlier stage"])
        step = dict(STEP, inputs={"tuples": {"external": pattern}})
        self.write("steps/check.py", "def run(ctx):\n    pass\n")
        self.assertIn("{external: ...} is only for a tuples input", self.messages(self.check(step))[0])

    def test_run_root_problems(self):
        inside = os.path.join(self.bundle, "runs")
        cases = [
            ("runs", "run_root: must be an absolute path (got runs)"),
            ("", "run_root: must be an absolute directory, e.g. run_root: /afs/cern.ch/work/u/user/taufw_runs "
                 "(got '')"),
            (5, "run_root: must be an absolute directory, e.g. run_root: /afs/cern.ch/work/u/user/taufw_runs "
                "(got 5)"),
            ("root://eosuser.cern.ch//eos/user/u/user/runs",
             "run_root: must be a directory on a mounted file system, not a URL "
             "(got root://eosuser.cern.ch//eos/user/u/user/runs)"),
            ("$TAUFW_UNDEFINED_VARIABLE/runs",
             "run_root: $TAUFW_UNDEFINED_VARIABLE/runs: undefined environment variable "
             "(expanded: $TAUFW_UNDEFINED_VARIABLE/runs)"),
            (inside, "run_root: %s is inside the bundle %s: every run copies its bundle, so it would copy the "
                     "earlier runs too. Choose a directory outside the bundle" % (inside, self.bundle)),
            (self.bundle, "run_root: %s is inside the bundle %s: every run copies its bundle, so it would copy the "
                          "earlier runs too. Choose a directory outside the bundle" % (self.bundle, self.bundle)),
        ]
        for value, message in cases:
            with self.subTest(run_root=value):
                check = self.check_root(value)
                self.assertEqual(self.messages(check), [message])
                self.assertEqual(check.warnings, ())  # a run_root that is a problem gets no warning
                self.assertIsNone(check.recipe)
        check = self.check_root(os.path.join(self.root, "tes_runs"))  # next to the bundle, not inside it
        self.assertTrue(check.ok)

    def test_the_bundled_analyses_have_no_problems(self):
        for bundle in ("example_mutau", "tes_id_2025"):
            with self.subTest(bundle=bundle):
                check = check_recipe(os.path.join(checkout.REPO, "Analyses", bundle))
                # the tuples of tes_id_2025 are on EOS: missing on a machine without it (e.g. Windows)
                messages = [m for m in self.messages(check) if not (" tuple directory /eos/" in m
                                                                    and not os.path.isdir("/eos/cms"))]
                self.assertEqual(messages, [])
                self.assertEqual(check.ok, len(messages) == len(check.issues))
                if check.ok:
                    self.assertIsNotNone(check.recipe)

    def test_valid_recipe(self):
        self.write("steps/check.py", "def run(ctx):\n    pass\n")
        check = self.check(FIT, dict(STEP, description="look", inputs={"fit": "fit"}))
        self.assertTrue(check.ok)
        self.assertEqual(check.name, "tes")
        self.assertEqual(check.stages, (("fit", "fit", ""), ("check", "python", "look")))
        self.assertEqual(check.recipe.stage("check").connections, {"fit": "fit"})

    def test_files_the_recipe_names(self):
        absolute = os.path.join(self.root, "missing_tt.yml")
        check = self.check(dict(FIT, config=absolute, config_mumu="TauES/config/FitSetup_mumu.yml"), STEP,
                           pico="pico.json")
        self.assertEqual(self.messages(check), [
            "pico.config: file not found: %s" % (os.path.join(self.bundle, "pico.json")),
            "stages[0] (fit).config: file not found: %s" % (absolute),  # a module path is the module's to check
            "stages[1] (python).file: steps/check.py is not a file of the bundle (%s)" % (self.bundle)])
        self.assertIsNone(check.recipe)

    def test_structure_and_files_together(self):
        """A wrong stage does not hide the problems of the others."""
        check = self.check({"stage": "fit", "inputs": {"shapes": None}}, STEP, name="a b")
        self.assertEqual(self.messages(check), [
            "name: must be a word of letters, digits, '_', '.' or '-' (got 'a b')",
            "stages[0] (fit): missing 'id' (every stage needs a unique id, e.g. id: fit)",
            "stages[1] (python).file: steps/check.py is not a file of the bundle (%s)" % (self.bundle)])
        self.assertEqual(check.name, "a b")  # the name as written, even if it is not allowed
        self.assertEqual(check.stages, (("check", "python", ""),))

    def test_unreadable_files(self):
        self.write("recipe.yml", "name: [unclosed\n")
        check = check_recipe(self.bundle)
        self.assertFalse(check.ok)
        self.assertIn("cannot read", self.messages(check)[0])
        check = check_recipe(self.write("notes.txt", "x"))
        self.assertEqual(self.messages(check), ["a recipe must be a bundle directory or a .yml, .yaml or .json file"])
        self.write("empty/recipe.yml", "")
        check = check_recipe(os.path.join(self.bundle, "empty"))
        self.assertEqual(self.messages(check), ["a recipe is a mapping with keys name, run_root, pico, stages"])


if __name__ == "__main__":
    unittest.main()
