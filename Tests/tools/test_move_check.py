"""Tests of Tests/tools/move_check.py (ROOT-free)."""
import unittest

from move_check import changed_lines, compare, differing_units

OLD = '''import os
from TauFW.Plotter.sample.utils import LOG

class Sample(object):
  def gethist(self):
    import TauFW.Plotter.sample.utils as GLOB
    return GLOB.lumi

def load(method):
  ensuremodule(method,'Plotter.methods')
'''


class MoveCheckTests(unittest.TestCase):
    def test_identical_file(self):
        report = compare(OLD, OLD)
        self.assertTrue(report.ok)
        self.assertEqual((report.changed, report.units), ([], []))

    def test_import_lines_are_allowed(self):
        new = OLD.replace("TauFW.Plotter.", "TauFW.Histogrammer.")
        report = compare(OLD, new)
        self.assertTrue(report.ok)
        self.assertEqual(len(report.changed), 2)
        self.assertEqual(report.units, ["<module>", "Sample", "Sample.gethist"])  # where the imports are

    def test_other_changes_fail_unless_allowed(self):
        new = OLD.replace("'Plotter.methods'", "'Histogrammer.methods'")
        self.assertFalse(compare(OLD, new).ok)
        self.assertEqual(compare(OLD, new).disallowed, [("  ensuremodule(method,'Plotter.methods')",
                                                         "  ensuremodule(method,'Histogrammer.methods')")])
        self.assertTrue(compare(OLD, new, allow=[r"\.methods'"]).ok)
        self.assertEqual(compare(OLD, new).units, ["load"])

    def test_logic_change_fails(self):
        report = compare(OLD, OLD.replace("return GLOB.lumi", "return 2*GLOB.lumi"))
        self.assertFalse(report.ok)
        self.assertEqual(report.units, ["Sample", "Sample.gethist"])

    def test_added_and_removed_lines_and_line_endings(self):
        self.assertEqual(changed_lines("a\nb\n", "a\r\nb\r\n"), [])
        self.assertEqual(changed_lines("a\nb\n", "a\n"), [("b", "")])
        self.assertEqual(changed_lines("a\n", "a\nimport os\n"), [("", "import os")])
        self.assertTrue(compare("a = 1\n", "a = 1\nimport os\n").ok)
        self.assertFalse(compare("a = 1\n", "a = 1\nb = 2\n").ok)

    def test_units_added_removed_and_python2(self):
        self.assertEqual(differing_units("def f(): pass\n", "def g(): pass\n"), ["-f", "+g"])
        report = compare('print "old"\n', 'print "old"\nimport os\n')
        self.assertTrue(report.ok)
        self.assertIn("AST not compared", report.note)


if __name__ == '__main__':
    unittest.main()
