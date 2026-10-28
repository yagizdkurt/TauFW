"""Offline package-origin checks; never import NumPy or require CMSSW."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "python_environment", REPO / "Utilities/python/Internal/Installer/_python_environment.py")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class PythonEnvironmentTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.home = self.root / "home"
        self.local = self.home / ".local/lib/python/site-packages"
        self.cms = self.root / "cvmfs/cms/site-packages"
        self.local.mkdir(parents=True)
        self.cms.mkdir(parents=True)
        self.paths = list(helper.sys.path)
        for context in (
                patch.object(helper.Path, "home", return_value=self.home),
                patch.object(helper, "CVMFS_ROOT", self.root / "cvmfs"),
                patch.object(helper.sys, "path", [str(self.local), str(self.cms)] + helper.sys.path),
                patch.dict(helper.os.environ, {"CMSSW_BASE": "/release"}, clear=True)):
            context.start()
            self.addCleanup(context.stop)

    def package(self, module="fixture_numpy", distribution="fixture-numpy", bundled=True, top_level=False):
        (self.local / module).mkdir()
        (self.local / module / "__init__.py").write_text("raise RuntimeError('must not import')\n")
        info = self.local / (distribution.replace("-", "_") + "-1.0.dist-info")
        info.mkdir()
        (info / "METADATA").write_text("Name: %s\nVersion: 1.0\n" % distribution)
        (info / "RECORD").write_text("%s/__init__.py,,\n" % module)
        if top_level:
            (info / "top_level.txt").write_text(module + "\n")
        if bundled:
            (self.cms / module).mkdir()
            (self.cms / module / "__init__.py").write_text("raise RuntimeError('must not import')\n")

    def test_shadowed_wheel_reports_both_paths_and_pip_distribution(self):
        self.package(distribution="fixture-pip-name")
        warnings = helper.python_environment_warnings()
        self.assertEqual(len(warnings), 1)
        self.assertIn(str(self.local / "fixture_numpy/__init__.py"), warnings[0])
        self.assertIn(str(self.cms / "fixture_numpy/__init__.py"), warnings[0])
        self.assertIn("pip3 uninstall fixture-pip-name", warnings[0])

    def test_unrelated_user_package_is_allowed(self):
        self.package(bundled=False)
        self.assertEqual(helper.python_environment_warnings(), [])

    def test_cvmfs_import_wins_without_warning(self):
        self.package(top_level=True)
        with patch.object(helper.sys, "path", [str(self.cms), str(self.local)] + self.paths):
            self.assertEqual(helper.python_environment_warnings(), [])

    def test_disabled_user_site_and_non_cmssw_runtime_are_quiet(self):
        self.package()
        with patch.object(helper.sys, "path", [str(self.cms)] + self.paths):
            self.assertEqual(helper.python_environment_warnings(), [])
        with patch.dict(helper.os.environ, {}, clear=True):
            self.assertEqual(helper.python_environment_warnings(), [])

    def test_non_cvmfs_fallback_is_not_a_cmssw_package(self):
        self.package()
        with patch.object(helper, "CVMFS_ROOT", self.root / "other"):
            self.assertEqual(helper.python_environment_warnings(), [])


if __name__ == "__main__":
    unittest.main()
