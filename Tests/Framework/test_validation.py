"""Recipe validation (validation.py): every problem of a recipe file, the files it names included."""
import json
import os
import shutil
import tempfile
import unittest

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

    def test_the_bundled_analyses_have_no_problems(self):
        for bundle in ("example_mutau", "tes_id_2025"):
            with self.subTest(bundle=bundle):
                check = check_recipe(os.path.join(checkout.REPO, "Analyses", bundle))
                self.assertEqual(self.messages(check), [])
                self.assertTrue(check.ok)
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
        self.assertEqual(self.messages(check), ["a recipe is a mapping with keys name, pico, stages"])


if __name__ == "__main__":
    unittest.main()
