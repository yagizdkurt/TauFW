"""The user config (TauFW.Utilities.UserConfig): where it is, reading, creating, and the one-line warnings."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import checkout  # noqa: F401  (must precede TauFW.Utilities imports)
from TauFW.Utilities import UserConfig

REVIEWED = "taufw_user:\n  version: 1\n  reviewed: true\n"


class UserConfigTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / "UserConfig.yaml"

    def write(self, text):
        self.path.write_text(text, encoding="utf-8")
        return self.path

    def test_location_is_the_checkouts_analyses_or_the_environment(self):
        with mock.patch.dict(os.environ):
            os.environ.pop(UserConfig.ENVVAR, None)
            self.assertEqual(UserConfig.location(), checkout.SOURCE.parents[1] / "Analyses" / "UserConfig.yaml")
            os.environ[UserConfig.ENVVAR] = str(self.path)
            self.assertEqual(UserConfig.location(), self.path)

    def test_missing_file_gives_defaults_and_names_the_create_command(self):
        config = UserConfig.load(self.path)
        self.assertFalse(config.exists)
        self.assertFalse(config.reviewed)
        self.assertIsNone(config.version)
        self.assertIsNone(config.get("runs.run_root"))
        self.assertEqual(config.get("runs.run_root", "/x"), "/x")
        with self.assertRaises(UserConfig.UserConfigError) as error:
            config.require("runs.run_root")
        self.assertIn(str(self.path), str(error.exception))
        self.assertIn("'runs.run_root'", str(error.exception))
        self.assertIn(UserConfig.CREATE_COMMAND, str(error.exception))
        self.assertEqual(UserConfig.check(config),
                         ["No user config %s: create it with `python3 taufw.py userconfig`" % (self.path)])

    def test_create_writes_once_and_never_overwrites(self):
        self.assertTrue(UserConfig.create(self.path))
        text = self.path.read_text(encoding="utf-8")
        config = UserConfig.load(self.path)
        self.assertTrue(config.exists)
        self.assertEqual((config.version, config.reviewed, config.values), (1, False, {}))
        self.assertEqual(UserConfig.check(config),
                         ["User config %s is not reviewed yet: check its values, then set reviewed: true" % (self.path)])
        self.write(text.replace("reviewed: false", "reviewed: true"))
        self.assertFalse(UserConfig.create(self.path))
        self.assertIn("reviewed: true", self.path.read_text(encoding="utf-8"))  # kept
        self.assertEqual(UserConfig.check(UserConfig.load(self.path)), [])

    def test_dotted_keys_sections_and_values(self):
        self.write(REVIEWED + "runs:\n  run_root: /afs/x\nproduction:\n  hadd: {maxopenfiles: 500}\n")
        config = UserConfig.load(self.path)
        self.assertEqual(config.get("runs.run_root"), "/afs/x")
        self.assertEqual(config.require("production.hadd.maxopenfiles"), 500)
        self.assertIsNone(config.get("runs.run_root.deeper"))
        self.assertEqual(config.section("runs"), {"run_root": "/afs/x"})
        self.assertEqual(config.section("nothing"), {})
        self.assertEqual(sorted(config.values), ["production", "runs"])  # the header is not a setting
        config.section("runs")["run_root"] = "/changed"
        self.assertEqual(config.get("runs.run_root"), "/afs/x")  # copies

    def test_broken_files_name_the_file_and_the_problem(self):
        cases = [("- a list\n", "not a YAML mapping"),
                 ("runs: {}\n", "no taufw_user header"),
                 ("taufw_user:\n  version: 2\n  reviewed: true\n", "taufw_user.version must be a whole number"),
                 ("taufw_user:\n  version: true\n  reviewed: true\n", "taufw_user.version must be a whole number"),
                 ("taufw_user:\n  version: 1\n  reviewed: yes please\n", "taufw_user.reviewed must be true or false"),
                 ("taufw_user: [\n", "cannot be read")]
        for text, problem in cases:
            with self.subTest(text=text):
                self.write(text)
                with self.assertRaises(UserConfig.UserConfigError) as error:
                    UserConfig.load(self.path)
                self.assertTrue(str(error.exception).startswith(str(self.path) + ": "), str(error.exception))
                self.assertIn(problem, str(error.exception))

    def test_check_never_raises(self):
        self.write("- a list\n")
        with mock.patch.dict(os.environ, {UserConfig.ENVVAR: str(self.path)}):
            (warning,) = UserConfig.check()
        self.assertIn("not a YAML mapping", warning)

    def test_importable_before_cmsenv_as_a_top_level_package(self):
        """FastSetup imports it with Utilities/python on sys.path and no TauFW package."""
        code = ("import sys; sys.path.insert(0, sys.argv[1]); import UserConfig; "
                "print(UserConfig.create(sys.argv[2]), UserConfig.create(sys.argv[2]))")
        result = subprocess.run([sys.executable, "-c", code, str(checkout.SOURCE), str(self.path)],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stdout.strip(), "True False")
        self.assertIn("reviewed: false", self.path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
