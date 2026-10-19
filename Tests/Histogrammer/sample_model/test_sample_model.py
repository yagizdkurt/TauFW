"""The sample model (TauFW.Histogrammer.sample.model) against Histogrammer/config/samples_v15.py: for every era,
channel kind and caller option of recorder.py, the new getsampleset with the template
Configs/Histogrammer/samples/v15_<era>.yml must make exactly the core calls the old one makes (same arguments, same order). Where the old one raises, the new one must
raise too, after the same calls (the message may differ). No ROOT: the recorder's stub utils module.
Also the reader: format problems, pick() by era, sample_names()."""
import glob
import os
import shutil
import tempfile
import unittest

import checkout
import recorder
from TauFW.Histogrammer.sample import model

TEMPLATES = sorted(glob.glob(str(checkout.REPO / "Configs" / "Histogrammer" / "samples" / "v15_*.yml")))
table_lumi = recorder.table_lumi


def without_model_lumi(calls):
    """The calls with the model's setera(..., lumi=) argument removed, after checking that it is the value setera
    looked up itself before (so the samples are normalised as before); a different value stays a difference."""
    result = []
    for call in calls:
        if call[0] == 'setera' and 'lumi' in call[2]:
            era = call[1][0]
            if call[2]['lumi'] != table_lumi(era):
                return calls
            call = [call[0], call[1], {key: value for key, value in call[2].items() if key != 'lumi'}]
        result.append(call)
    return result


def compare(old, new):
    """None if the calls are equal (both raising after the same calls counts as equal), else a description."""
    if old and old[-1][0] == 'raised':
        if not new or new[-1][0] != 'raised':
            return "the old function raised %s, the new one did not" % (old[-1][1:],)
        old, new = old[:-1], new[:-1]
    if old == new:
        return None
    for index, (a, b) in enumerate(zip(old, new)):
        if a != b:
            return "call %d differs:\n  old %r\n  new %r" % (index, a, b)
    return "%d calls (old) vs %d (new)" % (len(old), len(new))


class EqualityTests(unittest.TestCase):
    def test_templates_exist_for_every_era(self):
        self.assertEqual(sorted(model.load_sample_model(path).era for path in TEMPLATES), sorted(recorder.ERAS))

    def test_same_core_calls(self):
        with recorder.stub_utils() as utils:
            old = recorder.load_samples_v15()
            old_grid = recorder.record_grid(old.getsampleset, recorder.old_targets(old))
            models = {era: model.pick(TEMPLATES, era) for era in recorder.ERAS}
            new_grid = recorder.record_grid(
                lambda channel, era, **kwargs: model.getsampleset(channel, era, models[era], **kwargs),
                recorder.model_targets(utils))
        self.assertEqual(sorted(old_grid), sorted(new_grid))
        raised = 0
        for key in sorted(old_grid):
            with self.subTest(case=key):
                self.assertIsNone(compare(old_grid[key], without_model_lumi(new_grid[key])))
            raised += old_grid[key][-1][0] == 'raised'
        self.assertLess(raised, len(old_grid) // 4, "most cases must build a sample set, not raise")

    def test_template_lumi_is_the_table_value(self):  # CL §26: the model's lumi replaces the lookup in setera
        for path in TEMPLATES:
            sample_model = model.load_sample_model(path)
            with self.subTest(era=sample_model.era):
                self.assertEqual(sample_model.lumi, table_lumi(sample_model.era))
                with recorder.stub_utils() as utils:
                    calls = recorder.record(lambda c, e, **k: model.getsampleset(c, e, sample_model, **k),
                                            recorder.model_targets(utils), 'mutau', sample_model.era)
                self.assertEqual(calls[0], ['setera', [sample_model.era], {'lumi': sample_model.lumi,
                                                                           'cme': sample_model.cme}])

    def test_samples_keyword_of_samples_v15(self):
        """samples_v15.getsampleset(..., samples=[templates]) hands over to the model (what plot.py --samples and
        createinputsTES.py --samples do): the same calls as its own tables."""
        with recorder.stub_utils() as utils:
            old = recorder.load_samples_v15()
            targets = recorder.old_targets(old) + recorder.model_targets(utils)
            own = recorder.record_grid(old.getsampleset, targets)
            files = {model.load_sample_model(path).era: [path] for path in TEMPLATES}  # one file: fast
            handed = recorder.record_grid(lambda c, e, **k: old.getsampleset(c, e, samples=files[e], **k), targets)
        for key in sorted(own):
            with self.subTest(case=key):
                self.assertIsNone(compare(own[key], without_model_lumi(handed[key])))

    def test_the_caller_join_list_is_changed_as_before(self):
        with recorder.stub_utils() as utils:
            old = recorder.load_samples_v15()
            joins = [['VV', 'Top'], ['VV', 'Top']]
            recorder.record(lambda c, e, **k: old.getsampleset(c, e, join=joins[0], **k), recorder.old_targets(old),
                            'mutau', '2025', split=['TT'])
            recorder.record(lambda c, e, **k: model.getsampleset(c, e, model.pick(TEMPLATES, e), join=joins[1], **k),
                            recorder.model_targets(utils), 'mutau', '2025', split=['TT'])
        self.assertEqual(joins[0], ['VV', 'TT', 'ST'])
        self.assertEqual(joins[0], joins[1])


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="taufw-test-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        with open([path for path in TEMPLATES if path.endswith("v15_2025.yml")][0]) as stream:
            self.text = stream.read()

    def write(self, name, text):
        path = os.path.join(self.root, name)
        with open(path, "w") as stream:
            stream.write(text)
        return path

    def test_pick_by_era(self):
        self.assertEqual(model.pick(TEMPLATES, '2022_postEE').era, '2022_postEE')
        with self.assertRaisesRegex(model.SampleModelError, "no sample file"):
            model.pick(TEMPLATES, 'UL2018')
        twice = self.write("copy.yml", self.text)
        with self.assertRaisesRegex(model.SampleModelError, "2 sample file"):
            model.pick(TEMPLATES + [twice], '2025')

    def test_sample_names(self):
        sample_model = model.pick(TEMPLATES, '2025')
        names, data = model.sample_names(sample_model, 'mutau')
        self.assertEqual((names[0], len(names), data), ("DYto2Mu_Bin-MLL-10to50", 29, "Muon*Run2025*"))
        self.assertIsNone(model.sample_names(sample_model, 'xyz')[1])

    def test_format_problems(self):
        cases = [("era: \"2025\"", "era: 2025", "era must be a text"),
                 ("cme: 13.6", "cme: high", "cme must be a positive number"),
                 ("lumi: 110.18", "lumi: 0", "lumi must be a positive number"),
                 ("\nlumi: 110.18", "\nlumen: 110.18", "missing key(s) lumi"),
                 ("schema: 2", "schema: 1", "schema 1 had no lumi"),
                 ("xsec: 6744.0, extraweight: dyweight", "xsec: 6744.0, extraweight: zweight",
                  "extraweight 'zweight' is not a key"),
                 ("  muon:", "  muons:", "data must map channel kinds"),
                 ("schema: 2", "schema: 3", "schema is 3"),
                 ("stitch: []", "stitch: []\nlumen: 1", "unknown key(s) lumen")]
        for old, new, message in cases:
            with self.subTest(message=message):
                self.assertIn(old, self.text)
                path = self.write("bad.yml", self.text.replace(old, new, 1))
                with self.assertRaises(model.SampleModelError) as caught:
                    model.load_sample_model(path)
                self.assertTrue(any(message in problem for problem in caught.exception.problems),
                                caught.exception.problems)


if __name__ == "__main__":
    unittest.main()
