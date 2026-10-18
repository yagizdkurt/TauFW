"""Histogram files (TauFW.Utilities.HistFile): what is refused before anything is written (no ROOT), and with ROOT
the round trip: every histogram attribute, the order and the metadata come back as written."""
import os
import tempfile
import unittest

import checkout  # noqa: F401  (must precede TauFW.Utilities imports)
from TauFW.Utilities.HistFile import HistFileEntry, HistFileError, read_histfile, write_histfile


class Named:
    """A stand-in for a histogram before anything is written: only its name is used."""

    def __init__(self, name):
        self.name = name

    def GetName(self):
        return self.name


def root_available():
    try:
        import ROOT  # noqa: F401
        return True
    except ImportError:
        return False


class RefusedTests(unittest.TestCase):
    """Invalid entries are refused before ROOT is used, so nothing is written."""

    def refused(self, entries, meta=None, message=""):
        with self.assertRaises(HistFileError) as context:
            write_histfile(os.path.join(tempfile.gettempdir(), "never_written.root"), entries, meta)
        self.assertIn(message, str(context.exception))

    def test_paths(self):
        for path in ("", "/baseline", "baseline/", "a//b", "taufw_histfile", None):
            self.refused([HistFileEntry(path, {})], message="invalid entry path")
        self.refused([HistFileEntry("a", {}), HistFileEntry("a", {})], message="used twice")
        self.refused(["a"], message="must be a HistFileEntry")

    def test_names(self):
        self.refused([HistFileEntry("a", {"exp": [Named("h"), Named("h")]})], message="used twice")
        self.refused([HistFileEntry("a", {"exp": [Named("a/b")]})], message="invalid histogram name")
        self.refused([HistFileEntry("a", {"": [Named("h")]})], message="invalid group name")

    def test_metadata_must_be_plain_json(self):
        self.refused([], meta={"x": float("nan")}, message="not plain JSON")
        self.refused([], meta={"x": object()}, message="not plain JSON")
        self.refused([HistFileEntry("a", {}, {1: "integer key"})], message="does not read back equal")


@unittest.skipUnless(root_available(), "needs ROOT (lxplus)")
class RoundTripTests(unittest.TestCase):
    def test_everything_comes_back(self):
        import ROOT
        ROOT.TH1.AddDirectory(False)
        hists = []
        for name, color in (("data", 1), ("ZTT", 801), ("TT", 600)):
            hist = ROOT.TH1D(name, "title of " + name, 4, 0, 4)
            for index, value in enumerate((1.5, 2.25, 0.0, 7.125), start=1):
                hist.Fill(index - 0.5, value)
            hist.SetFillColor(color)
            hist.SetLineStyle(2)
            hists.append(hist)
        meta = {"era": "2025", "tags": ["a", 1, 2.5, True, None]}
        entries = [HistFileEntry("baseline/m_vis", {"data": hists[:1], "exp": [hists[2], hists[1]], "sig": []},
                                 {"title": "m_{vis}", "ymin": None, "ratiorange": 0.5}),
                   HistFileEntry("highpt/m_vis", {"exp": hists[1:]}, {})]
        before = ROOT.gDirectory.GetPath()
        with tempfile.TemporaryDirectory() as directory:
            path = write_histfile(os.path.join(directory, "sub", "file.root"), entries, meta)
            self.assertEqual(ROOT.gDirectory.GetPath(), before)
            content = read_histfile(path)
            self.assertEqual(ROOT.gDirectory.GetPath(), before)
        self.assertEqual(content.meta, meta)  # read after the file is gone: the copies are detached
        self.assertEqual([entry.path for entry in content.entries], ["baseline/m_vis", "highpt/m_vis"])
        first = content.entry("baseline/m_vis")
        self.assertEqual(first.meta, entries[0].meta)
        self.assertEqual({group: [h.GetName() for h in hs] for group, hs in first.groups.items()},
                         {"data": ["data"], "exp": ["TT", "ZTT"], "sig": []})  # the written order, not the keys'
        for read, written in zip(first.histograms(), [hists[0], hists[2], hists[1]]):
            self.assertEqual(read.GetTitle(), written.GetTitle())
            self.assertEqual((read.GetFillColor(), read.GetLineStyle()), (written.GetFillColor(), 2))
            self.assertEqual(read.GetEntries(), written.GetEntries())
            self.assertEqual([read.GetBinContent(i) for i in range(6)], [written.GetBinContent(i) for i in range(6)])
            self.assertEqual([read.GetBinError(i) for i in range(6)], [written.GetBinError(i) for i in range(6)])
            self.assertIsNone(read.GetDirectory())

    def test_not_a_histfile(self):
        import ROOT
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "plain.root")
            handle = ROOT.TFile.Open(path, "RECREATE")
            handle.Close()
            with self.assertRaises(HistFileError):
                read_histfile(path)


if __name__ == "__main__":
    unittest.main()
