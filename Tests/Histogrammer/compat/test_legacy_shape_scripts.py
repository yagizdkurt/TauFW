"""The old paths of the shape scripts (CL §25, H1): each is a LEGACY stub that imports nothing of TauFW, runs nothing,
prints the command of the moved script (same arguments, from the same working directory) and exits with status 2;
and the moved script exists there. ROOT-free.
"""
import ast
import io
import os
from contextlib import redirect_stderr
from pathlib import Path
import runpy
import shlex
import sys
import unittest

REPO = Path(__file__).resolve().parents[3]

# old path -> new path (plan 16 D2, D4; MuTauFR stays, D11)
STUBS = {"Fitter/TauES/createinputsTES.py": "Histogrammer/shapes/TauES/createinputsTES.py"}
STUBS.update({"Fitter/%s/createinputs.py" % name: "Histogrammer/shapes/%s/createinputs.py" % name
              for name in ("ETauFR", "HighPT", "paper", "tutorial")})


def imported(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module)
    return names


class LegacyShapeScriptTests(unittest.TestCase):
    def test_stubs_import_nothing_of_taufw(self):
        for old, new in STUBS.items():
            with self.subTest(old=old):
                self.assertEqual(imported(REPO / old), {"os", "shlex", "sys"})
                self.assertTrue((REPO / new).is_file(), new)

    def test_stub_prints_the_new_command_and_exits_2(self):
        for old, new in STUBS.items():
            with self.subTest(old=old):
                cwd = (REPO / old).parent  # where the old script was run from: Fitter/<Variant>/ (TauES: Fitter/)
                if old.startswith("Fitter/TauES/"):
                    cwd = REPO / "Fitter"
                stub = runpy.run_path(str(REPO / old), run_name="stub")
                stderr = io.StringIO()
                with redirect_stderr(stderr):
                    status = stub["main"](["-y", "2025", "-c", "a b.yml"])
                self.assertEqual(status, 2)
                expected = os.path.relpath(REPO / new, os.getcwd())
                self.assertIn("LEGACY: %s moved to the Histogrammer" % (old), stderr.getvalue())
                self.assertIn("    python3 %s -y 2025 -c 'a b.yml'" % (shlex.quote(expected)), stderr.getvalue())
                command = stub["new_commands"](["-y", "2025"], str(cwd))
                self.assertEqual(command.split()[1], shlex.quote(os.path.relpath(REPO / new, cwd)))

    def test_mutau_fr_is_not_moved(self):
        """D11: Fitter/MuTauFR/createinputs.py stays (its broken TauFW.Plotter.plot.datacard import, TODO §8)."""
        self.assertIn("TauFW.Plotter.plot.datacard", imported(REPO / "Fitter/MuTauFR/createinputs.py"))
        self.assertFalse((REPO / "Histogrammer/shapes/MuTauFR").exists())


if __name__ == "__main__":
    sys.exit(unittest.main())
