"""compare_fitresults.py: result files by relative path, parameters by name, tolerances per kind (TODO §1)."""
import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest

from compare_fitresults import Comparison, files_of, main, read_values

VALUES = "output_pt_less_region/againstjet_VTight/againstelectron_Tight/2025/" \
         "FitparameterValues__mutau_DeepTau_2025-13TeV_DM0_pt1.txt"
CORRECTION = "tau_sf/TauES_SF_dm_DeepTau2018v2p5_2025_VSjetVTight_VSeleTight.json"


def values_text(tes=0.987, nuisance=0.1):
    """A FitparameterValues file of one region, as makecombinedfitTES_SF.py writes it."""
    return ("tes_DM0_pt1: %.6f\ntes_DM0_pt1_1sigma_low: 0.981000\ntes_DM0_pt1_1sigma_high: 0.993000\n"
            "tid_SF_DM0_pt1: 0.912000\nlumi_13TeV: %.6f\n" % (tes, nuisance))


def correction(sf=0.95):
    return {"schema_version": 2, "corrections": [{"name": "tau_energy_scale", "data": {"content": [sf, 1.0]}}]}


class ComparisonTests(unittest.TestCase):
    def test_read_values(self):
        self.assertEqual(read_values("tes_DM0_pt1: 0.987\nno separator\nnote: n/a\n"),
                         {"tes_DM0_pt1": 0.987, "note": "n/a"})

    def test_pois_and_nuisances_have_their_own_tolerance(self):
        a, b = read_values(values_text()), read_values(values_text(tes=0.989, nuisance=0.4))
        result = Comparison()
        result.values(a, b, "f")
        self.assertEqual(result.found, ["f: lumi_13TeV = 0.1 in A, 0.4 in B", "f: tes_DM0_pt1 = 0.987 in A, 0.989 in B"])
        self.assertAlmostEqual(result.largest["poi"], 0.002)
        self.assertAlmostEqual(result.largest["nuisance"], 0.3)
        result = Comparison(poi_atol=0.0025, pois_only=True)  # one grid step, nuisances left out
        result.values(a, b, "f")
        self.assertEqual(result.found, [])
        self.assertEqual(result.largest["nuisance"], 0.0)

    def test_parameters_by_name(self):
        result = Comparison()
        result.values({"tes_DM0_pt1": 1.0}, {"tes_DM0_pt1": 1.0, "tid_SF_DM0_pt1": 0.9}, "f")
        self.assertEqual(result.found, ["f: tid_SF_DM0_pt1 only in B"])

    def test_json_tree(self):
        result = Comparison()
        result.json(correction(), correction(0.95 + 1e-9), "c.json")
        self.assertEqual(len(result.found), 1)
        self.assertIn("c.json/corrections[0]/data/content[0]", result.found[0])
        result = Comparison(rtol=1e-6)
        result.json(correction(), correction(0.95 + 1e-9), "c.json")
        self.assertEqual(result.found, [])
        result = Comparison()
        result.json({"a": [1, 2]}, {"a": [1], "b": "x"}, "c.json")
        self.assertEqual(result.found, ["c.json/a: 2 values in A, 1 in B", "c.json/b: only in B"])


class MainTests(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="taufw-fit-compare-")
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)

    def result_dir(self, name, files):
        directory = os.path.join(self.base, name)
        for relative, text in files.items():
            path = os.path.join(directory, relative)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as stream:
                stream.write(text)
        return directory

    def main(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(list(argv))
        return code, out.getvalue()

    def test_directories(self):
        common = {CORRECTION: json.dumps(correction()), "tau_sf/x.root": "", "step1.log": "a log",
                  "plots_pt_less_region/x.png": ""}
        a = self.result_dir("a", dict(common, **{VALUES: values_text()}))
        b = self.result_dir("b", dict(common, **{VALUES: values_text(tes=0.989)}))
        self.assertEqual(files_of(a), {VALUES: "values", CORRECTION: "json", "tau_sf/x.root": "root"})  # others ignored
        code, text = self.main(a, b)
        self.assertEqual(code, 1)
        self.assertIn("DIFF: 1 difference(s):", text)
        self.assertIn("on both sides: 1 FitparameterValues, 1 JSON, 1 ROOT (by name only)", text)
        code, text = self.main(a, b, "--poi-atol", "0.002")
        self.assertEqual(code, 0, text)
        self.assertIn("SAME (within the tolerances)", text)
        os.remove(os.path.join(b, "tau_sf/x.root"))
        code, text = self.main(a, b, "--poi-atol", "0.002")
        self.assertEqual(code, 1)
        self.assertIn("tau_sf/x.root: only in A", text)

    def test_same(self):
        a = self.result_dir("a", {VALUES: values_text()})
        b = self.result_dir("b", {VALUES: values_text()})
        code, text = self.main(a, b)
        self.assertEqual(code, 0)
        self.assertTrue(text.rstrip().endswith("SAME"))

    def test_nothing_to_compare_is_a_failure(self):
        a, b = self.result_dir("a", {"x.png": ""}), self.result_dir("b", {"x.png": ""})
        self.assertEqual(self.main(a, b)[0], 1)


if __name__ == "__main__":
    unittest.main()
