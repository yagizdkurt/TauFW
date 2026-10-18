"""The old Plotter module names (CL §24): every shim in Plotter/python/ is exactly the alias of its new module.

  ShimFileTests       ROOT-free: the shim files, their targets and the shim list of the plan (13 names)
  AliasMechanismTests ROOT-free: the alias pattern on a throw-away package (same object, shared module state)
  RealModuleTests     with ROOT and the TauFW package (lxplus, after `scram b`): old name is new module
"""
import ast
import importlib
from pathlib import Path
import sys
import tempfile
import textwrap
import unittest

REPO = Path(__file__).resolve().parents[3]
SHIM_DIR = REPO / "Plotter" / "python"

# old module name -> new module name (LocalR/architecture/18 §3)
SHIMS = {"TauFW.Plotter.sample.%s" % name: "TauFW.Histogrammer.sample.%s" % name
         for name in ("HistSet", "MergedSample", "ResultDict", "Sample", "SampleSet", "utils", "model")}
SHIMS.update({"TauFW.Plotter.plot.%s" % name: "TauFW.Histogrammer.spec.%s" % name
              for name in ("Context", "Selection", "string", "Variable")})
SHIMS["TauFW.Plotter.plot.MultiDraw"] = "TauFW.Histogrammer.sample.MultiDraw"
SHIMS["TauFW.Plotter.methods.QCD_OSSS"] = "TauFW.Histogrammer.methods.QCD_OSSS"


def shim_file(old):
    return SHIM_DIR.joinpath(*old.split(".")[2:]).with_suffix(".py")


def module_file(new):
    return REPO.joinpath(new.split(".")[1], "python", *new.split(".")[2:]).with_suffix(".py")


def alias_target(path):
    """The module a shim file aliases, or None if the file is not exactly: docstring, `import sys`,
    `import <module> as _module`, `sys.modules[__name__] = _module`."""
    body = ast.parse(path.read_text(encoding="utf-8")).body
    if len(body) != 4 or not isinstance(body[0], ast.Expr) or not isinstance(body[0].value, ast.Constant):
        return None
    if ast.dump(body[1]) != ast.dump(ast.parse("import sys").body[0]):
        return None
    if not (isinstance(body[2], ast.Import) and len(body[2].names) == 1 and body[2].names[0].asname == "_module"):
        return None
    if ast.dump(body[3]) != ast.dump(ast.parse("sys.modules[__name__] = _module").body[0]):
        return None
    return body[2].names[0].name


class ShimFileTests(unittest.TestCase):
    def test_every_shim_aliases_its_new_module(self):
        for old, new in SHIMS.items():
            with self.subTest(old=old):
                self.assertEqual(alias_target(shim_file(old)), new)
                self.assertTrue(module_file(new).is_file(), module_file(new))

    def test_no_other_code_in_the_old_package(self):
        """The old subpackages of Plotter/python/ (sample, plot, methods) hold only the shims; the new Plotter's own
        code lives beside them (e.g. controlplots.py, CL §24 S3)."""
        found = {path for sub in ("sample", "plot", "methods") for path in (SHIM_DIR / sub).rglob("*.py")
                 if "__pycache__" not in path.parts}
        self.assertEqual(found, {shim_file(old) for old in SHIMS})

    def test_no_shim_for_removed_or_broken_names(self):
        self.assertFalse((SHIM_DIR / "plot" / "datacard.py").exists())  # would repair Fitter/MuTauFR (TODO §8)
        # no TauFW.Plotter.api (only the Framework used it); a checkout may keep an untracked api/__pycache__/
        self.assertEqual(list((SHIM_DIR / "api").glob("*.py")), [])


class AliasMechanismTests(unittest.TestCase):
    """The pattern itself, on a throw-away package `fakepkg` (new.py holds state, old.py is a shim)."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        package = Path(self.directory.name) / "fakepkg"
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "new.py").write_text(textwrap.dedent("""\
            lumi = -1
            def setera(value):
                global lumi
                lumi = value
            class Sample(object):
                pass
            """), encoding="utf-8")
        (package / "old.py").write_text(shim_file("TauFW.Plotter.sample.utils").read_text(encoding="utf-8")
                                        .replace("TauFW.Histogrammer.sample.utils", "fakepkg.new"), encoding="utf-8")
        sys.path.insert(0, self.directory.name)

    def tearDown(self):
        sys.path.remove(self.directory.name)
        for name in ("fakepkg", "fakepkg.new", "fakepkg.old"):
            sys.modules.pop(name, None)
        self.directory.cleanup()

    def test_same_module_object_and_shared_state(self):
        import fakepkg.old as old
        import fakepkg.new as new
        self.assertIs(old, new)
        from fakepkg.old import setera, Sample
        setera(59.7)                       # through the old name ...
        self.assertEqual(new.lumi, 59.7)   # ... the state of the new module changes
        self.assertIs(Sample, new.Sample)
        self.assertIs(sys.modules["fakepkg"].old, new)  # attribute of the package as well


class RealModuleTests(unittest.TestCase):
    def setUp(self):
        try:
            import ROOT  # noqa: F401
            import TauFW.Histogrammer.sample.utils  # noqa: F401
        except ImportError as error:
            self.skipTest("needs ROOT and the TauFW package (lxplus, cmsenv, scram b): %s" % error)

    def test_old_names_are_the_new_modules(self):
        for old, new in SHIMS.items():
            with self.subTest(old=old):
                self.assertIs(importlib.import_module(old), importlib.import_module(new))

    def test_setera_through_the_old_name(self):
        old = importlib.import_module("TauFW.Plotter.sample.utils")
        new = importlib.import_module("TauFW.Histogrammer.sample.utils")
        old.setera(2018)
        self.assertEqual((new.era, new.lumi), ("2018", 59.7))  # setera stores the era as text


if __name__ == "__main__":
    unittest.main()
