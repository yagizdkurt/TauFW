"""getsampleset(tuples=...): the directory of the tuples comes from the caller (plot.py and createinputsTES.py
--tuples), not from $PICODIR of the PicoProducer configuration. Without it the library refuses $PICODIR (CL §37); the
scripts' old default is TauFW.Histogrammer.sample.tupledir. Real ROOT, tiny local tuples."""
import json
from array import array
import os
import tempfile
import unittest
from unittest import mock

import ROOT
from TauFW.Plotter.sample.utils import getsampleset
from TauFW.Histogrammer.sample.tupledir import ENVVAR, script_default_tuples

TUPLES = ('2025/DY/DYJets_mumu.root', '2025/DY/DYJets_mumu_TES0p950.root',
          '2025/Data/SingleMuon_Run2025C_mumu.root', '2025/Data/SingleMuon_Run2025D_mumu.root')


def write_tuple(path):
    """A pico tuple with one event: a tree and the cutflow histogram the samples read."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    output = ROOT.TFile.Open(path, 'RECREATE')
    try:
        tree = ROOT.TTree('tree', 'tree')
        value = array('d', [1.0])
        tree.Branch('value', value, 'value/D')
        tree.Fill()
        cutflow = ROOT.TH1D('cutflow', 'cutflow', 25, 0, 25)
        cutflow.SetBinContent(1, 1)
        cutflow.SetBinContent(17, 1)  # sum of generator weights
        output.Write()
    finally:
        output.Close()


class TupleLocationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='taufw-tuples-')
        self.addCleanup(temporary.cleanup)
        self.root = os.path.join(temporary.name, 'tuples')
        for relative in TUPLES:
            write_tuple(os.path.join(self.root, relative))
        self.pattern = os.path.join(self.root, '$ERA', '$GROUP')

    def path(self, relative):
        return os.path.join(self.root, relative)

    def sampleset(self, **kwargs):
        return getsampleset(('Data', "SingleMuon_Run2025*"), [('DY', "DYJets", "Drell-Yan", 1.0)],
                            channel='mumu', era='2025', lumi=1.0, **kwargs)

    def check_files(self, sampleset):
        self.assertEqual([s.filename for s in sampleset.expsamples], [self.path('2025/DY/DYJets_mumu.root')])
        self.assertEqual(sorted(s.filename for s in sampleset.datasample.samples),  # the data glob, merged
                         [self.path('2025/Data/SingleMuon_Run2025C_mumu.root'),
                          self.path('2025/Data/SingleMuon_Run2025D_mumu.root')])

    def test_tuples_instead_of_the_configuration(self):
        with mock.patch('TauFW.PicoProducer.settings.getconfig') as getconfig:
            sampleset = self.sampleset(tuples=self.pattern)
        getconfig.assert_not_called()  # the PicoProducer configuration is not read
        self.check_files(sampleset)

    def test_variation_in_the_same_directory(self):
        shifted = self.sampleset(tuples=self.pattern).shift('DY', "_TES0p950")
        self.assertEqual([s.filename for s in shifted.expsamples], [self.path('2025/DY/DYJets_mumu_TES0p950.root')])

    def test_no_tuples_is_refused(self):
        with mock.patch('TauFW.PicoProducer.settings.getconfig') as getconfig:
            with self.assertRaises(ValueError):
                self.sampleset()
        getconfig.assert_not_called()  # given, never found (CL §37)

    def test_script_default_reads_picodir_of_the_configuration(self):
        config = os.path.join(self.root, 'pico.json')
        with open(config, 'w') as stream:
            json.dump({'picodir': self.pattern}, stream)
        with mock.patch.dict(os.environ, {ENVVAR: config}):
            sampleset = self.sampleset(tuples=script_default_tuples())
        self.check_files(sampleset)


if __name__ == '__main__':
    unittest.main()
