"""Analysis draft creation and discovery without a terminal or stage execution."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import checkout
from TauFW.Framework._internal.interfaces.interactive import _Operations
from TauFW.Framework._internal.recipes import analysis
from TauFW.Framework._internal.recipes.recipe import Recipe, RecipeError, read_recipe
from TauFW.Framework._internal.recipes.validation import check_recipe


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.analyses = self.root / "Analyses"

    def test_created_analysis_is_listed_as_a_draft_and_cannot_run(self):
        operations = _Operations(recipes_dir=self.analyses, operations_dir=self.root / "operations")
        for name in ("my_analysis", "true", "123"):
            with self.subTest(name=name):
                path = operations.create_analysis(name)
                self.assertEqual(path, self.analyses / name)
                self.assertEqual([p.name for p in path.iterdir()], ["recipe.yml"])
                self.assertEqual(read_recipe(str(path))[0], {"name": name, "stages": []})
                self.assertIn(path, operations.recipes())
                view = operations.recipe_preview(path)
                self.assertTrue(view["draft"])
                self.assertEqual((view["problems"], view["warnings"]), ((), ()))
                self.assertEqual(operations.kept_recipe_preview(path), view)
                check = check_recipe(str(path), allow_draft=True)
                self.assertFalse(check.ok)
                self.assertIsNone(check.recipe)
                self.assertFalse(check_recipe(str(path)).ok)
                with self.assertRaises(RecipeError):
                    Recipe.load(str(path))

    def test_invalid_names_and_existing_paths_are_unchanged(self):
        for name in ("", "bad name", ".", "..", "../escape", "a/b", "a\\b", "bad\n", "trailing."):
            with self.subTest(name=name), self.assertRaises(ValueError):
                analysis.create_analysis(self.analyses, name)
        self.assertFalse(self.analyses.exists())
        path = analysis.create_analysis(self.analyses, "existing")
        original = (path / "recipe.yml").read_bytes()
        with self.assertRaises(FileExistsError):
            analysis.create_analysis(self.analyses, "existing")
        self.assertEqual((path / "recipe.yml").read_bytes(), original)
        occupied = self.analyses / "occupied"
        occupied.write_text("keep me", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            analysis.create_analysis(self.analyses, "occupied")
        self.assertEqual(occupied.read_text(encoding="utf-8"), "keep me")

    def test_failed_write_removes_only_the_new_draft(self):
        existing = analysis.create_analysis(self.analyses, "existing")
        original = (existing / "recipe.yml").read_bytes()
        with mock.patch.object(analysis.os, "replace", side_effect=OSError("cannot publish")):
            with self.assertRaisesRegex(OSError, "cannot publish"):
                analysis.create_analysis(self.analyses, "failed")
        self.assertEqual(list(self.analyses.iterdir()), [existing])
        self.assertEqual((existing / "recipe.yml").read_bytes(), original)

    def test_draft_inspection_keeps_other_errors_and_refreshes_after_editing(self):
        operations = _Operations(recipes_dir=self.analyses, operations_dir=self.root / "operations")
        path = operations.create_analysis("draft")
        operations.recipe_preview(path)
        for data in ({"name": "bad name", "stages": []}, {"name": "draft", "stages": [], "unknown": True},
                     {"name": "draft"}, {"name": "draft", "stages": None},
                     {"name": "draft", "stages": [], "pico": {"config": "missing.json"}}):
            with self.subTest(data=data):
                (path / "recipe.yml").write_text(json.dumps(data), encoding="utf-8")
                check = check_recipe(str(path), allow_draft=True)
                self.assertFalse(check.draft)
                self.assertTrue(check.issues)
        (path / "example.py").write_text("def run(ctx):\n    pass\n", encoding="utf-8")
        data = {"name": "draft", "stages": [{"stage": "python", "id": "example", "inputs": None,
                                                "file": "example.py"}]}
        (path / "recipe.yml").write_text(json.dumps(data), encoding="utf-8")
        self.assertIsNone(operations.kept_recipe_preview(path))
        view = operations.recipe_preview(path)
        self.assertFalse(view["draft"])
        self.assertEqual(view["problems"], ())
        self.assertTrue(check_recipe(str(path)).ok)


if __name__ == "__main__":
    unittest.main()
