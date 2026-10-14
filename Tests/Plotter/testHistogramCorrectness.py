"""Hand-calculated checks of the production Sample histogram API, using real ROOT."""
from array import array
from pathlib import Path
import tempfile
import unittest

import ROOT
from TauFW.Plotter.sample.utils import Sample
from TauFW.Plotter.plot.Selection import Selection
from TauFW.Plotter.plot.Variable import Variable


# Include exact lower/internal/upper edges, signed weights, and a zero weight.
EVENTS = ((-1, 2), (0, 1), (0.5, -1), (1, 2), (1.5, 0),
          (2, -0.5), (2.5, 1.5), (3, 3), (4, -1))


class HistogramCorrectnessTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='taufw-histogram-')
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / 'events.root'
        output = ROOT.TFile.Open(str(path), 'RECREATE')
        self.assertTrue(output and not output.IsZombie())
        try:
            tree = ROOT.TTree('tree', 'tree')
            value, weight = array('d', [0]), array('d', [0])
            tree.Branch('value', value, 'value/D')
            tree.Branch('weight', weight, 'weight/D')
            for value[0], weight[0] in EVENTS:
                tree.Fill()
            cutflow = ROOT.TH1D('cutflow', 'cutflow', 25, 0, 25)
            cutflow.SetBinContent(1, 9)
            cutflow.SetBinContent(17, 7)  # hand-summed generator weights
            output.Write()
        finally:
            output.Close()
        # 1 fb^-1 * 0.014 pb * 1000 / 7 generator weights = normalization 2.
        self.sample = Sample('Toy', str(path), 0.014, lumi=1.0, weight='weight', color=ROOT.kBlack)

    def check_histogram(self, variable, contents, variances, edges, normalize=False, selection='true'):
        hist = self.sample.gethist(variable, Selection('selected', selection),
                                   nthreads=1, norm=normalize, blind=False)
        self.assertIsNotNone(hist)
        self.assertEqual(hist.GetNbinsX(), len(edges) - 1)
        self.assertEqual(len(contents), hist.GetNbinsX() + 2)
        self.assertEqual(len(variances), len(contents))
        self.assertEqual([hist.GetXaxis().GetBinLowEdge(i) for i in range(1, len(edges) + 1)], edges)
        for index, (content, variance) in enumerate(zip(contents, variances)):
            with self.subTest(bin=index):  # includes both flow bins
                self.assertAlmostEqual(hist.GetBinContent(index), content, places=12)
                self.assertAlmostEqual(hist.GetBinError(index) ** 2, variance, places=12)

    def test_fixed_bins_signed_weights_and_flow(self):
        # bins: underflow, [0,1), [1,2), [2,3), overflow
        self.check_histogram(Variable('value', 3, 0, 3),
                             [2, 0, 2, 1, 2], [4, 2, 4, 2.5, 10], [0, 1, 2, 3])

    def test_variable_bins_and_exact_edges(self):
        # Merging the final two fixed bins gives sum(w)=3 and sum(w^2)=6.5.
        self.check_histogram(Variable('value', [0, 1, 3]),
                             [2, 0, 3, 2], [4, 2, 6.5, 10], [0, 1, 3])

    def test_normalization_scales_contents_and_squared_errors(self):
        self.assertEqual(self.sample.nevents, 9)
        self.assertEqual(self.sample.sumweights, 7)
        self.assertAlmostEqual(self.sample.norm, 2, places=12)
        self.check_histogram(Variable('value', 3, 0, 3),
                             [4, 0, 4, 2, 4], [16, 8, 16, 10, 40], [0, 1, 2, 3], normalize=True)

    def test_empty_selection_has_zero_contents_and_errors(self):
        for binning, edges, zeros in (((3, 0, 3), [0, 1, 2, 3], [0] * 5),
                                      (([0, 1, 3],), [0, 1, 3], [0] * 4)):
            with self.subTest(edges=edges):
                self.check_histogram(Variable('value', *binning), zeros, zeros, edges,
                                     normalize=True, selection='value > 100')


if __name__ == '__main__':
    unittest.main()
