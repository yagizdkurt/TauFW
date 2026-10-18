"""The Plotter's control plots (TauFW.Plotter.controlplots), without ROOT: the file names and texts are plot.py's,
the file's contract is checked, and the drawing variable carries exactly the drawing attributes. The drawing itself
is checked with ROOT by the BBB case plotter.stack (the canvases locked with plot.py drawing from memory)."""
from unittest import mock
import unittest

import checkout  # noqa: F401  (must precede the TauFW imports)
from TauFW.Plotter import controlplots
from TauFW.Plotter.controlplots import (ControlHistsError, DrawingVariable, DRAWING_ATTRIBUTES, plot_name,
                                        plot_text, read_control_hists)
from TauFW.Utilities.HistFile import HistFile, HistFileEntry

ATTRIBUTES = {"filename": "mvis", "title": "m_{vis} [GeV]", "xmin": 0, "xmax": 200.0, "ymin": None, "ymax": None,
              "rmin": None, "rmax": None, "ratiorange": None, "binlabels": [], "logx": False, "logy": True,
              "ymargin": 1.6, "logyrange": None, "position": "LL;y=0.88", "ncols": 2, "dividebins": False}


def plotpy_name_and_text(outdir, channel, selection_filename, selection_title, era, extratext):
    """The two lines of Histogrammer/fillhists.py (Plotter/plot.py before CL §24), copied as they are."""
    fname  = "%s/$VAR_%s-%s-%s$TAG"%(outdir,channel.replace('mu','m').replace('tau','t'),selection_filename,era)
    text   = "%s: %s"%(channel.replace('mu',"#mu").replace('tau',"#tau_{h}"),selection_title)
    if extratext:
      text += ("" if '\n' in extratext[:3] else ", ") + extratext
    return fname, text


class PresentationTests(unittest.TestCase):
    def test_names_and_texts_are_plotpys(self):
        for channel in ("mutau", "etau", "tautau", "mumu", "emu", "ee"):
            for title in ("baseline", "h^{#pm}#pi^{0}"):
                for extratext in ("", "test", "\n2nd line", "a\nb"):
                    expected = plotpy_name_and_text("plots/2025", channel, "dm1", title, "2025", extratext)
                    self.assertEqual((plot_name(channel, "dm1", "2025", "plots/2025"),
                                      plot_text(channel, title, extratext)), expected)


class FileTests(unittest.TestCase):
    def content(self, **meta):
        file_meta = dict({"contract": "taufw.control_histograms", "version": 1, "channel": "mutau", "era": "2025",
                          "tag": "_v1"}, **meta)
        entry = HistFileEntry("baseline/mvis", {"data": ["d"], "exp": ["ztt", "tt"], "sig": []},
                              {"selection": {"name": "baseline", "title": "Baseline", "cut": "q_1*q_2<0"},
                               "variable": ATTRIBUTES})
        return HistFile(file_meta, (entry,))

    def read(self, content):
        with mock.patch.object(controlplots, "read_histfile", return_value=content):
            return read_control_hists("file.root")

    def test_read(self):
        hists = self.read(self.content())
        self.assertEqual((hists.channel, hists.era, hists.tag), ("mutau", "2025", "_v1"))
        entry, = hists.entries
        self.assertEqual((entry.selection_name, entry.selection_title, entry.selection_cut),
                         ("baseline", "Baseline", "q_1*q_2<0"))
        self.assertEqual((entry.data, entry.exp, entry.sig, entry.hists), ("d", ["ztt", "tt"], [], ["d", "ztt", "tt"]))
        self.assertEqual({name: getattr(entry.variable, name) for name in DRAWING_ATTRIBUTES}, ATTRIBUTES)

    def test_other_contract_or_version_is_refused(self):
        for meta in ({"contract": "something.else"}, {"version": 2}):
            with self.assertRaises(ControlHistsError):
                self.read(self.content(**meta))

    def test_missing_metadata_is_refused(self):
        content = self.content()
        del content.meta["tag"]
        with self.assertRaises(ControlHistsError) as context:
            self.read(content)
        self.assertIn("no tag", str(context.exception))
        for drop in ("selection", "variable"):
            content = self.content()
            del content.entries[0].meta[drop]
            with self.assertRaises(ControlHistsError) as context:
                self.read(content)
            self.assertIn("entry baseline/mvis: no %s" % (drop), str(context.exception))
        content = self.content()
        del content.entries[0].meta["selection"]["cut"]
        with self.assertRaises(ControlHistsError):
            self.read(content)

    def test_drawing_variable(self):
        variable = DrawingVariable(ATTRIBUTES)
        self.assertTrue(all(hasattr(variable, name) for name in ("getedge", "dividebins", "binlabels")))  # a variable
        with self.assertRaises(ControlHistsError):
            variable.getedge(1)
        with self.assertRaises(ControlHistsError):  # an attribute missing in the file
            DrawingVariable({name: value for name, value in ATTRIBUTES.items() if name != "logy"})


if __name__ == "__main__":
    unittest.main()
