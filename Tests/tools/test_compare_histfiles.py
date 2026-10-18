"""compare_histfiles.py without ROOT: what counts as a difference of two snapshots (CL §21, S4)."""
import struct
import unittest

from compare_histfiles import differences, numbers_differ


class CompareTests(unittest.TestCase):
    def compare(self, a, b, rtol=0.0):
        found, largest = [], [0.0]
        differences(a, b, "file", rtol, found, largest)
        return found, largest[0]

    def test_exact_and_tolerance(self):
        self.assertFalse(numbers_differ(1.0, 1.0, 0))
        self.assertFalse(numbers_differ(float("nan"), float("nan"), 0))
        self.assertTrue(numbers_differ(1.0, 1.0 + 1e-14, 0))  # exact by default
        self.assertFalse(numbers_differ(1.0, 1.0 + 1e-14, 1e-12))
        self.assertTrue(numbers_differ(1.0, 1.001, 1e-12))
        self.assertTrue(numbers_differ("mt", "mm", 1e-12))  # text is never "close"

    def test_nested_snapshots(self):
        a = {"meta": {"era": "2025"}, "entries": [{"path": "baseline/m_vis", "contents": [1.0, 2.0]}]}
        self.assertEqual(self.compare(a, a), ([], 0.0))
        b = {"meta": {"era": "2025"}, "entries": [{"path": "baseline/m_vis", "contents": [1.0, 2.0 + 2e-14]}]}
        found, largest = self.compare(a, b)
        self.assertEqual(found, ["file.entries[0].contents[1]: 2.0 in A, %r in B" % (2.0 + 2e-14)])
        self.assertAlmostEqual(largest, 1e-14, delta=1e-15)
        self.assertEqual(self.compare(a, b, rtol=1e-12)[0], [])
        # the BBB snapshot stores floats exactly, as hex ({"float64": ...}): compared as numbers, so rtol applies
        exact = {"contents": [{"float64": struct.pack("<d", 2.0).hex()}]}
        close = {"contents": [{"float64": struct.pack("<d", 2.0 + 4e-14).hex()}]}
        self.assertEqual(len(self.compare(exact, close)[0]), 1)
        self.assertEqual(self.compare(exact, close, rtol=1e-12)[0], [])
        found, _ = self.compare(a, {"meta": {}, "entries": []})
        self.assertEqual(found, ["file.entries: 1 values in A, 0 in B", "file.meta.era: only in A"])


if __name__ == "__main__":
    unittest.main()
