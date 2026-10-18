"""The Histogrammer's control-histogram writer (TauFW.Histogrammer.controlhists), without ROOT: what is taken from
a stack (copies of its histograms, the selection, the variable's drawing attributes) and the file metadata. A
stand-in ROOT module records the directory switch around Clone. With ROOT, the BBB case plotter.stack checks the
whole path (fill, write, read, draw) against the canvases locked with plot.py."""
import sys
import types
from unittest import mock
import unittest

import checkout  # noqa: F401  (must precede the TauFW imports)
from TauFW.Histogrammer import controlhists
from TauFW.Histogrammer.controlhists import DRAWING_ATTRIBUTES, stack_entry, write_control_hists


class FakeHist:
    def __init__(self, name):
        self.name, self.directory, self.copies = name, "Rint:/", []

    def GetName(self):
        return self.name

    def Clone(self, name):
        copy = FakeHist(name)
        copy.cloned_with_add_directory = FAKE_ROOT.TH1.status
        self.copies.append(copy)
        return copy

    def SetDirectory(self, directory):
        self.directory = directory


class FakeTH1:
    status = True

    @classmethod
    def AddDirectoryStatus(cls):
        return cls.status

    @classmethod
    def AddDirectory(cls, status):
        cls.status = status


FAKE_ROOT = types.SimpleNamespace(TH1=FakeTH1)


class Variable:
    def __init__(self):
        for index, name in enumerate(DRAWING_ATTRIBUTES):
            setattr(self, name, "value %d" % (index))
        self.filename, self.unused = "mvis", "not a drawing attribute"


class StackEntryTests(unittest.TestCase):
    def test_copies_selection_and_drawing_attributes(self):
        stack = types.SimpleNamespace(datahist=FakeHist("data"), exphists=[FakeHist("ZTT"), FakeHist("TT")],
                                      sighists=[])
        selection = types.SimpleNamespace(filename="baseline", title="Baseline", selection="q_1*q_2<0")
        with mock.patch.dict(sys.modules, {"ROOT": FAKE_ROOT}):
            entry = stack_entry(stack, Variable(), selection)
        self.assertEqual(entry.path, "baseline/mvis")
        self.assertEqual({group: [h.GetName() for h in hists] for group, hists in entry.groups.items()},
                         {"data": ["data"], "exp": ["ZTT", "TT"], "sig": []})
        for original, copy in zip([stack.datahist] + stack.exphists, entry.histograms()):
            self.assertEqual(original.copies, [copy])           # copies, not the originals (draw() changes those)
            self.assertEqual(copy.directory, 0)                 # detached: SetDirectory(0)
            self.assertFalse(copy.cloned_with_add_directory)    # never added to ROOT's current directory
            self.assertEqual(original.directory, "Rint:/")      # the original is untouched
        self.assertTrue(FakeTH1.status)                         # the switch is restored
        self.assertEqual(entry.meta["selection"], {"name": "baseline", "title": "Baseline", "cut": "q_1*q_2<0"})
        self.assertEqual(list(entry.meta["variable"]), list(DRAWING_ATTRIBUTES))  # exactly these, in this order

    def test_no_data(self):
        stack = types.SimpleNamespace(datahist=None, exphists=[], sighists=[FakeHist("signal")])
        selection = types.SimpleNamespace(filename="sr", title="SR", selection="1")
        with mock.patch.dict(sys.modules, {"ROOT": FAKE_ROOT}):
            entry = stack_entry(stack, Variable(), selection)
        self.assertEqual(entry.groups["data"], [])
        self.assertEqual([h.GetName() for h in entry.groups["sig"]], ["signal"])


class WriteTests(unittest.TestCase):
    def test_file_metadata(self):
        with mock.patch.object(controlhists, "write_histfile", side_effect=lambda path, entries, meta: meta) as write:
            meta = write_control_hists("hists/2025/mutau_v1.root", ["entry"], channel="mutau", era=2025, tag="_v1")
        self.assertEqual(meta, {"contract": "taufw.control_histograms", "version": 1, "channel": "mutau",
                                "era": "2025", "tag": "_v1"})
        self.assertEqual(write.call_args[0][:2], ("hists/2025/mutau_v1.root", ["entry"]))

    def test_same_contract_as_the_plotter(self):
        """The Plotter reads what the Histogrammer writes: the two copies of the contract constants agree."""
        import ast
        from pathlib import Path
        source = (Path(checkout.REPO) / "Plotter" / "python" / "controlplots.py").read_text(encoding="utf-8")
        values = {node.targets[0].id: ast.literal_eval(node.value) for node in ast.parse(source).body
                  if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                  and node.targets[0].id in ("CONTRACT", "VERSION", "DRAWING_ATTRIBUTES")}
        self.assertEqual(values, {"CONTRACT": controlhists.CONTRACT, "VERSION": controlhists.VERSION,
                                  "DRAWING_ATTRIBUTES": DRAWING_ATTRIBUTES})


if __name__ == "__main__":
    unittest.main()
