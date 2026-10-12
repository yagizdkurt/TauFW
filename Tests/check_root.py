#!/usr/bin/env python3
"""Small lxplus-only checks using real ROOT artifacts, without creating baselines."""
from array import array
from pathlib import Path
import sys
import tempfile
import unittest

from BBB.snapshot import canonical_bytes, exact, file_snapshot
from support.bootstrap import configure_root, dependencies, prepare
from support.fixtures import write_tree


class RootChecks(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="taufw-snapshot-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)

    def snapshot(self, path):
        return canonical_bytes(exact(file_snapshot(path)))

    def test_container_metadata_does_not_change_snapshot(self):
        self.assertEqual(self.snapshot(write_tree(self.path / "first.root")),
                         self.snapshot(write_tree(self.path / "second.root")))

    def test_changed_histogram_value_and_name_fail_exact_comparison(self):
        import ROOT
        path = write_tree(self.path / "values.root")
        original = self.snapshot(path)
        source = ROOT.TFile.Open(str(path), "UPDATE")
        hist = source.Get("cutflow")
        hist.SetBinContent(1, hist.GetBinContent(1) + 0.0000000001)
        hist.Write("cutflow", ROOT.TH1.kOverwrite)
        source.Close()
        self.assertNotEqual(original, self.snapshot(path))
        before_rename = self.snapshot(path)
        source = ROOT.TFile.Open(str(path), "UPDATE")
        hist = source.Get("cutflow")
        hist.SetName("renamed_cutflow")
        hist.Write("cutflow", ROOT.TH1.kOverwrite)
        source.Close()
        self.assertNotEqual(before_rename, self.snapshot(path))

    def tiny_tree(self, name, dtype):
        import ROOT
        output = ROOT.TFile.Open(str(self.path / name), "RECREATE")
        tree = ROOT.TTree("tree", "tree")
        address = array({"l": "Q", "L": "q", "D": "d"}[dtype], [2 ** 53 + 17])
        tree.Branch("event", address, "event/" + dtype)
        tree.Fill()
        output.Write()
        output.Close()
        return self.path / name

    def test_branch_type_and_large_integer_are_preserved(self):
        integer = self.tiny_tree("integer.root", "l")
        floating = self.tiny_tree("floating.root", "D")
        snapshot = file_snapshot(integer)
        self.assertEqual(snapshot[0]["object"]["entries"][0][0], 2 ** 53 + 17)
        self.assertNotEqual(self.snapshot(integer), self.snapshot(floating))

    def test_schema_change_fails_with_identical_integer_values(self):
        unsigned = self.tiny_tree("unsigned.root", "l")
        signed = self.tiny_tree("signed.root", "L")
        left, right = file_snapshot(unsigned), file_snapshot(signed)
        self.assertEqual(left[0]["object"]["entries"], right[0]["object"]["entries"])
        self.assertNotEqual(left[0]["object"]["branches"][0]["type"], right[0]["object"]["branches"][0]["type"])
        self.assertNotEqual(self.snapshot(unsigned), self.snapshot(signed))


def main():
    try:
        dependencies(["ROOT", "numpy", "past"])
        with tempfile.TemporaryDirectory(prefix="taufw-root-check-") as directory:
            prepare(directory)
            configure_root(directory, single_thread=True)
            result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RootChecks))
            return 0 if result.wasSuccessful() else 1
    except (RuntimeError, OSError) as error:
        print("ERROR: %s" % error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
