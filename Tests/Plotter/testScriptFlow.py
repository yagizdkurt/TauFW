"""A study in one Python script: Sample -> gethist -> Plot -> saveas, with no recipe and no histogram file in between
(CL §39). The module boundaries are between the stages' packages; a user's script may use the Histogrammer's samples
and the drawing library (TauFW.Utilities.Drawing) together. Real ROOT, a tiny local tuple."""
from array import array
import os
import tempfile
import unittest

import ROOT
from TauFW.Plotter.sample.utils import MC
from TauFW.Plotter.plot.Selection import Selection
from TauFW.Plotter.plot.Variable import Variable
from TauFW.Utilities.Drawing.Plot import Plot


def write_tuple(path):
    """A pico tuple with four events and the cutflow histogram the samples read."""
    output = ROOT.TFile.Open(path, 'RECREATE')
    try:
        tree = ROOT.TTree('tree', 'tree')
        value = array('d', [0])
        tree.Branch('value', value, 'value/D')
        for value[0] in (0.5, 1.5, 1.5, 2.5):
            tree.Fill()
        cutflow = ROOT.TH1D('cutflow', 'cutflow', 25, 0, 25)
        cutflow.SetBinContent(1, 4)
        cutflow.SetBinContent(17, 4)  # sum of generator weights
        output.Write()
    finally:
        output.Close()


class ScriptFlowTests(unittest.TestCase):
    def test_sample_to_plot_in_one_script(self):
        temporary = tempfile.TemporaryDirectory(prefix='taufw-script-')
        self.addCleanup(temporary.cleanup)
        tuple_ = os.path.join(temporary.name, 'DYJets_mumu.root')
        write_tuple(tuple_)

        var = Variable('value', 3, 0, 3)
        cut = Selection('all', 'true')
        sample = MC('DYJets', "Drell-Yan", tuple_, 1.0, lumi=1.0)
        hist = sample.gethist(var, cut, nthreads=1, norm=False, blind=False)
        self.assertEqual([hist.GetBinContent(i) for i in range(1, 4)], [1, 2, 1])

        plot = Plot(var, hist)
        plot.draw()
        fname = os.path.join(temporary.name, 'plot.png')
        plot.saveas(fname)
        plot.close()
        self.assertTrue(os.path.isfile(fname))


if __name__ == '__main__':
    unittest.main()
