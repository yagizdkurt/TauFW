"""Variation tuples (TauFW.Histogrammer.sample.variations): which samples createinputsTES.py reads from a shifted tuple
file, replayed on names without ROOT (the real SampleSet: Tests/tools/check_variation_files.py on lxplus)."""
import copy
import unittest

import yaml

import checkout
from TauFW.Histogrammer.sample import model
from TauFW.Histogrammer.sample.variations import variations

BUNDLE = checkout.REPO / "Analyses" / "tes_id_2025"
TES_ID = checkout.REPO / "Configs" / "Fitter" / "tes_id"
SAMPLES = checkout.REPO / "Configs" / "Histogrammer" / "samples"


def read(path):
    with open(str(path)) as stream:
        return yaml.safe_load(stream)


class VariationTests(unittest.TestCase):
    def setUp(self):
        self.setup = read(BUNDLE / "config_coarse_TT.yml")
        self.model = model.load_sample_model(str(BUNDLE / "v15_2025.yml"))

    def groups(self, variation):
        return sorted(set(group for group, _ in variation.samples))

    def test_tes_id_2025(self):  # 10 TES points (ZTT), LTF (ZL, TTL), JTF (ZJ, TTJ, W): 144 files
        found = variations(self.setup, self.model, '2025')
        tags = [v.tag for v in found]
        self.assertEqual(tags, ['_TES0p950', '_TES0p960', '_TES0p970', '_TES0p980', '_TES0p990', '_TES1p010',
                                '_TES1p020', '_TES1p030', '_TES1p040', '_TES1p050',
                                '_LTF1p030', '_LTF0p970', '_JTF1p100', '_JTF0p900'])
        self.assertEqual([v.label for v in found[-4:]], ['LTF Up', 'LTF Down', 'JTF Up', 'JTF Down'])
        self.assertEqual(found[0].label, 'TES 0.950')
        self.assertTrue(all(self.groups(v) == ['DY'] and len(v.samples) == 9 for v in found[:10]))
        self.assertTrue(all(self.groups(v) == ['DY', 'TT'] and len(v.samples) == 12 for v in found[10:12]))
        self.assertTrue(all(self.groups(v) == ['DY', 'TT', 'WJ'] and len(v.samples) == 15 for v in found[12:]))
        self.assertEqual(sum(len(v.samples) for v in found), 144)
        self.assertEqual(found[0].samples[0], ('DY', 'DYto2Mu_Bin-MLL-10to50'))  # model order

    def test_mumu_has_none(self):  # no TES points, only lnN systematics
        self.assertEqual(variations(read(BUNDLE / "FitSetup_mumu.yml"), self.model, '2025'), ())

    def test_every_template_with_every_sample_file(self):
        for config in sorted(TES_ID.glob("*.yml")):
            for samples in sorted(SAMPLES.glob("v15_*.yml")):
                sample_model = model.load_sample_model(str(samples))
                found = variations(read(config), sample_model, sample_model.era)
                for variation in found:
                    self.assertTrue(variation.samples, (config.name, samples.name, variation.tag))

    def test_tes_value_format(self):  # ("_TES%.3f"%v).replace(".","p")
        self.setup['TESvariations']['values'] = [0.95, 1, 1.0025]
        self.assertEqual([v.tag for v in variations(self.setup, self.model, '2025')][:3],
                         ['_TES0p950', '_TES1p000', '_TES1p002'])

    def test_systematics_without_files(self):  # weights only, lnN, an empty sampleAppend: the nominal files
        systematics = self.setup['systematics']
        systematics['shape_dy'] = {'effect': 'shape', 'processes': ['ZTT'], 'name': 'shape_dy_$BIN', 'title': 'dy',
                                   'variations': ['Up', 'Down'], 'nomWeight': 'zptweight_nnlo',
                                   'altWeights': ['1', '1']}
        systematics['LTF']['sampleAppend'] = ['_LTF1p030', '']
        del self.setup['TESvariations']
        self.assertEqual([v.tag for v in variations(self.setup, self.model, '2025')],
                         ['_LTF1p030', '_JTF1p100', '_JTF0p900'])

    def test_substring_match_without_joins(self):  # "W" matches every name with a W when VV and ST are not joined
        self.setup['samples']['join'] = ['TT']
        jtf = dict((v.tag, v) for v in variations(self.setup, self.model, '2025'))['_JTF1p100']
        self.assertIn(('VV', 'WWto4Q'), jtf.samples)
        self.assertIn(('VV', 'WZ'), jtf.samples)
        self.assertIn(('ST', 'TWminustoLNu2Q'), jtf.samples)
        self.assertNotIn(('VV', 'ZZto4L'), jtf.samples)
        self.assertNotIn(('ST', 'TBbarQ_t-channel'), jtf.samples)
        self.assertEqual(self.groups(jtf), ['DY', 'ST', 'TT', 'VV', 'WJ'])

    def test_split_and_rename(self):
        setup = copy.deepcopy(self.setup)
        del setup['samples']['rename']  # WJ keeps its name: "W" still matches it
        self.assertIn('WJ', self.groups(variations(setup, self.model, '2025')[-1]))
        setup['samples']['split'] = {}  # no ZTT part: the TES points shift nothing
        self.assertEqual(variations(setup, self.model, '2025')[0].samples, ())
        setup['samples']['split'] = {'DY': [['ZTT', 'Z -> tautau', 'genmatch_2==5']]}  # a title of its own
        setup['TESvariations']['processes'] = ['tautau']
        self.assertEqual(self.groups(variations(setup, self.model, '2025')[0]), ['DY'])

    def test_stitch(self):  # 2022_postEE: W*LNu*Jets* stitched into WJ, renamed W, shifted by JTF
        stitched = model.load_sample_model(str(SAMPLES / "v15_2022_postEE.yml"))
        jtf = variations(self.setup, stitched, '2022_postEE')[-1]
        wjets = [(row['group'], row['name']) for row in stitched.mc if row['group'] == 'WJ']
        self.assertEqual(len(wjets), 5)
        self.assertTrue(all(name in jtf.samples for name in wjets))


if __name__ == "__main__":
    unittest.main()
