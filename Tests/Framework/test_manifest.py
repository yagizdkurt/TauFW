"""Stage manifests (manifest.py): format 2 written by a DONE stage, and read back as the source of an input that
names another run's stage directory (no ROOT, no scripts)."""
import hashlib
import json
import os
import shutil
import tempfile
import unittest

import checkout  # noqa: F401  (must precede TauFW imports)
from TauFW.Framework import Recipe
from TauFW.Framework.defaults import default_file_io
from TauFW.Framework.manifest import write_manifest, read_stage_dir, ManifestError, MANIFEST_FORMAT

SHAPES = [{"kind": "shapes", "path": "/x/a.root", "era": "2025", "jet_wp": "VTight", "ele_wp": "Tight",
           "config": "tt.yml"}]


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="taufw-test-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.stage_spec = Recipe.from_dict({"name": "x", "stages": [
            {"stage": "histograms", "id": "hist", "description": "shapes", "inputs": {"tuples": None},
             "eras": [2025], "jet_wps": ["VTight"], "ele_wps": ["Tight"]}]}).stage("hist")
        self.directory = os.path.join(self.root, "run_1", "stages", "hist")

    def write(self, directory=None, sources=None):
        write_manifest(default_file_io(), directory or self.directory, "run_1", self.stage_spec, sources or {},
                       SHAPES, "2026-10-17 12:00:00")
        return os.path.join(directory or self.directory, "manifest.json")

    def error(self, path):
        with self.assertRaises(ManifestError) as context:
            read_stage_dir(path)
        return str(context.exception)

    def test_write_and_read(self):
        path = self.write(sources={"tuples": {"path": "/a/stages/production"}})
        with open(path) as stream:
            data = json.load(stream)
        self.assertEqual(data, {"manifest": MANIFEST_FORMAT, "run_id": "run_1", "stage_id": "hist",
                                "stage": "histograms", "description": "shapes", "inputs": {"tuples": None},
                                "sources": {"tuples": {"path": "/a/stages/production"}},
                                "stage_dir": self.directory, "finished": "2026-10-17 12:00:00",
                                "artifacts": SHAPES})
        stage_dir = read_stage_dir(self.directory)
        with open(path, "rb") as stream:
            sha256 = hashlib.sha256(stream.read()).hexdigest()
        self.assertEqual(stage_dir.artifacts, tuple(SHAPES))
        self.assertEqual(stage_dir.summary(), {"path": self.directory, "run_id": "run_1", "stage_id": "hist",
                                               "stage": "histograms", "finished": "2026-10-17 12:00:00",
                                               "manifest_sha256": sha256})

    def test_refused(self):
        self.assertEqual(self.error(self.directory), "no such directory: %s" % (self.directory))
        os.makedirs(self.directory)
        self.assertIn("has no manifest.json: its stage has not finished", self.error(self.directory))
        path = os.path.join(self.directory, "manifest.json")
        with open(path, "w") as stream:
            stream.write("{not json")
        self.assertIn("cannot read %s" % (path), self.error(self.directory))
        with open(path, "w") as stream:  # a manifest of R2/R3 (format 1): no conversion
            json.dump({"manifest": 1, "run_id": "run_1", "stage_id": "hist", "stage": "histograms",
                       "finished": "x", "artifacts": []}, stream)
        self.assertIn("has manifest format 1, expected 2", self.error(self.directory))
        with open(path, "w") as stream:
            json.dump({"manifest": 2, "run_id": "run_1"}, stream)
        self.assertIn("missing stage_id, stage, stage_dir, finished, artifacts", self.error(self.directory))

    def test_moved_or_copied_directory_is_refused(self):
        self.write()
        copy = os.path.join(self.root, "copy", "stages", "hist")
        shutil.copytree(self.directory, copy)
        self.assertEqual(self.error(copy), "%s was moved or copied from %s: its artifacts name the files there"
                         % (copy, self.directory))
        self.assertEqual(read_stage_dir(self.directory + os.sep).stage_id, "hist")  # same place, other spelling


if __name__ == "__main__":
    unittest.main()
