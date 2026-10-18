"""compare_shapefiles.py without ROOT: file lists, keys by name, tolerances, the histogram families (CL §25, H4)."""
import contextlib
import io
import os
import shutil
import struct
import tempfile
import unittest

from compare_shapefiles import Comparison, family, files_of, keyed, main


def hist(name, contents, errors=None):
    """A histogram as the BBB snapshot has it (contents as exact float64, the rest plain)."""
    return {"class": "TH1D", "name": name, "title": name,
            "contents": [{"float64": struct.pack("<d", value).hex()} for value in contents],
            "errors": list(errors if errors is not None else [0.1] * len(contents)), "entries": 10.0}


def entry(key, value=None, cls="TH1D", cycle=1, objects=None):
    result = {"key": key, "cycle": cycle, "class": cls}
    if objects is not None:
        result["objects"] = objects
    elif cls.startswith("TH1"):
        result["histogram"] = value
    return result


def shape_file(scale=1.0, ltf=(0.0, 4.0), extra=()):
    """A shape file of one region: nominal ZL, a TES point, an LTF shape, a canvas (key and class only)."""
    return [entry("DM0_pt1", cls="TDirectoryFile", objects=[
        entry("ZL", hist("ZL", [0.0, 2.0 * scale, 3.0])),
        entry("ZTT_TES0.950", hist("ZTT_TES0.950", [1.0, 5.0])),
        entry("ZL_shape_mTauFake_DM0_pt1Up", hist("ZL_shape_mTauFake_DM0_pt1Up", list(ltf))),
    ] + list(extra)), entry("stack_DM0_pt1", cls="TCanvas")]


class ComparisonTests(unittest.TestCase):
    def compare(self, a, b, rtol=0.0, atol=0.0):
        result = Comparison(rtol, atol)
        result.compare(keyed(a), keyed(b), "f.root")
        return result

    def test_same(self):
        result = self.compare(shape_file(), shape_file())
        self.assertEqual(result.found, [])
        self.assertEqual(result.families, {"nominal": [1, 1, 0.0], "TES": [1, 1, 0.0], "LTF": [1, 1, 0.0]})

    def test_tolerance_and_largest_difference_per_family(self):
        a, b = shape_file(), shape_file(scale=1.0 + 1e-13)
        result = self.compare(a, b)
        self.assertEqual(result.found, ["f.root/DM0_pt1;1/objects/ZL;1#histogram/contents[1]: 2.0 in A, %r in B"
                                        % (2.0 * (1.0 + 1e-13))])
        self.assertAlmostEqual(result.families["nominal"][2], 1e-13, delta=1e-15)
        self.assertEqual(result.families["LTF"][2], 0.0)
        self.assertEqual(self.compare(a, b, rtol=1e-12).found, [])
        self.assertEqual(self.compare(shape_file(ltf=(0.0, 4.0)), shape_file(ltf=(1e-18, 4.0)), atol=1e-15).found, [])
        self.assertEqual(len(self.compare(shape_file(ltf=(0.0, 4.0)), shape_file(ltf=(1e-18, 4.0)), rtol=1e-12).found),
                         1)  # 0 against 1e-18 is a relative difference of 1: only atol accepts it

    def test_keys_by_name(self):
        extra = [entry("TTL", hist("TTL", [1.0]))]
        result = self.compare(shape_file(extra=extra), shape_file())
        self.assertEqual(result.found, ["f.root/DM0_pt1;1/objects/TTL;1: only in A"])  # named, nothing shifts
        canvas = shape_file()
        canvas[1]["class"] = "TPad"
        self.assertEqual(self.compare(shape_file(), canvas).found, ["f.root/stack_DM0_pt1;1/class: 'TCanvas' in A, "
                                                                    "'TPad' in B"])

    def test_empty_ltf_is_counted(self):  # the BBB gap (TODO §7): the summary shows whether LTF has content
        result = self.compare(shape_file(ltf=(0.0, 0.0)), shape_file(ltf=(0.0, 0.0)))
        self.assertEqual(result.families["LTF"], [1, 0, 0.0])

    def test_family(self):
        self.assertEqual([family(n) for n in ("ZTT", "ZTT_TES1.030", "ZL_shape_mTauFake_DM0_pt1Down",
                                              "W_shape_jTauFake_DM1_pt2Up", "data_obs")],
                         ["nominal", "TES", "LTF", "JTF", "nominal"])


class MainTests(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="taufw-shapes-compare-")
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.snapshots = {}

    def run_dir(self, name, files):
        directory = os.path.join(self.base, name)
        for relative, snapshot in files.items():
            path = os.path.join(directory, relative)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w").close()
            self.snapshots[path] = snapshot
        return directory

    def main(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(list(argv), read=lambda path: keyed(self.snapshots[path]))
        return code, out.getvalue()

    def test_directories(self):
        shapes = "input_pt_less_region/againstjet_VTight/againstelectron_Tight/ztt_mt_tes_m_vis.inputs-2025-13TeV_mutau.root"
        a = self.run_dir("a", {shapes: shape_file(), "manifest.json": None, "input_pt_less_region/plots/x.png": None})
        b = self.run_dir("b", {shapes: shape_file(scale=1.0 + 1e-13), "manifest.json": None,
                               "input_pt_less_region/plots/x.png": None})
        self.assertEqual(files_of(a), [shapes, "input_pt_less_region/plots/x.png"])  # sorted; manifest.json skipped
        code, text = self.main(a, b)
        self.assertEqual(code, 1)
        self.assertIn("DIFF: 1 difference(s):", text)
        code, text = self.main(a, b, "--rtol", "1e-12")
        self.assertEqual(code, 0)
        self.assertIn("SAME (within rtol 1e-12, atol 0)", text)
        self.assertIn(">>> LTF         1 histograms,     1 with content", text)
        os.remove(os.path.join(b, "input_pt_less_region/plots/x.png"))
        code, text = self.main(a, b, "--rtol", "1e-12")
        self.assertEqual(code, 1)
        self.assertIn("input_pt_less_region/plots/x.png: only in A", text)

    def test_nothing_to_compare_is_a_failure(self):
        a, b = self.run_dir("a", {"x.png": None}), self.run_dir("b", {"x.png": None})
        self.assertEqual(self.main(a, b)[0], 1)


if __name__ == "__main__":
    unittest.main()
