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
from TauFW.Utilities.UserConfig import manage
from TauFW.Utilities.UserConfig import _guesses

REVIEWED = "taufw_user:\n  version: 1\n  reviewed: true\n"


class UserConfigTests(unittest.TestCase):
    def test_reading_and_managing_are_separate(self):
        """Scripts see only the reading side; making the file and its warnings are in UserConfig.manage."""
        self.assertEqual(sorted(UserConfig.__all__), ["Config", "UserConfigError", "load", "location"])
        for name in ("create", "check"):
            self.assertFalse(hasattr(UserConfig, name))
            self.assertTrue(callable(getattr(manage, name)))
        self.assertIs(manage.location, UserConfig.location)  # one location for both

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
            os.environ.pop(manage.ENVVAR, None)
            self.assertEqual(UserConfig.location(), checkout.SOURCE.parents[1] / "Analyses" / "UserConfig.yaml")
            os.environ[manage.ENVVAR] = str(self.path)
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
        self.assertIn(manage.CREATE_COMMAND, str(error.exception))
        self.assertEqual(manage.check(config),
                         ["No user config %s: create it with `taufw userconfig`" % (self.path)])

    def test_create_writes_once_and_never_overwrites(self):
        self.assertTrue(manage.create(self.path, values={}))
        text = self.path.read_text(encoding="utf-8")
        config = UserConfig.load(self.path)
        self.assertTrue(config.exists)
        self.assertEqual((config.version, config.reviewed), (1, False))
        self.assertEqual([s.key for s in manage.SETTINGS if config.get(s.key) is not None],
                         [s.key for s in manage.SETTINGS if s.written])  # the others are commented
        self.assertEqual(manage.check(config),
                         ["User config %s is not reviewed yet: check its values, then set reviewed: true"
                          % (self.path)])
        self.write(text.replace("reviewed: false", "reviewed: true"))
        self.assertFalse(manage.create(self.path))
        self.assertIn("reviewed: true", self.path.read_text(encoding="utf-8"))  # kept
        self.assertEqual(manage.check(UserConfig.load(self.path)), [])

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
        with mock.patch.dict(os.environ, {manage.ENVVAR: str(self.path)}):
            (warning,) = manage.check()
        self.assertIn("not a YAML mapping", warning)

    def test_lxplus_guesses_keep_eos_tidy_and_need_the_afs_work_area(self):
        """The job output goes to a taufw/ directory of the EOS area; run_root only if the AFS work area exists."""
        missing = self.root / "no-config.json"
        with mock.patch.object(_guesses.os.path, "isdir", return_value=True):
            values, sources = _guesses.new_values(host="lxplus961.cern.ch", user="jdoe", pico_config=missing)
        self.assertEqual(values, {
            "production.batch": "HTCondor",
            "production.outdir": "/eos/user/j/jdoe/taufw/output/$ERA/$CHANNEL/$SAMPLE",
            "production.nanodir": "/eos/user/j/jdoe/taufw/samples/nano/$ERA/$DAS",
            "runs.run_root": "/afs/cern.ch/work/j/jdoe/taufw_runs"})
        self.assertEqual(sources, ["Guessed for lxplus (user jdoe)."])
        with mock.patch.object(_guesses.os.path, "isdir", return_value=False):
            values, _ = _guesses.new_values(host="lxplus961.cern.ch", user="jdoe", pico_config=missing)
        self.assertNotIn("runs.run_root", values)
        self.assertEqual(_guesses.new_values(host="mylaptop", user="jdoe", pico_config=missing), ({}, []))

    def test_an_existing_picoproducer_config_wins_over_the_guesses(self):
        pico = self.root / "config.json"
        pico.write_text('{"outdir": "/eos/user/j/jdoe/mine/$ERA/$CHANNEL/$SAMPLE", "queue": "", "ncores": 8, '
                        '"maxopenfiles": 500, "batch": "HTCondor", "eras": {"2018": "x.py"}}', encoding="utf-8")
        with mock.patch.object(_guesses.os.path, "isdir", return_value=False):
            values, sources = _guesses.new_values(host="lxplus961.cern.ch", user="jdoe", pico_config=pico)
        self.assertEqual(values["production.outdir"], "/eos/user/j/jdoe/mine/$ERA/$CHANNEL/$SAMPLE")
        self.assertEqual(values["production.nanodir"], "/eos/user/j/jdoe/taufw/samples/nano/$ERA/$DAS")  # guessed
        self.assertEqual((values["production.ncores"], values["production.hadd.maxopenfiles"]), (8, 500))
        self.assertNotIn("production.queue", values)  # empty: not taken over
        self.assertEqual(sources[1], "Taken from %s: production.batch, production.hadd.maxopenfiles, "
                                     "production.ncores, production.outdir." % (pico))
        pico.write_text("not json", encoding="utf-8")
        self.assertEqual(_guesses.new_values(host="x", user="jdoe", pico_config=pico), ({}, []))

    def test_a_new_file_reads_back_what_was_written(self):
        values = {"runs.run_root": "/afs/cern.ch/work/j/jdoe/taufw_runs", "production.queue": "workday",
                  "production.outdir": "/eos/user/j/jdoe/taufw/output/$ERA/$CHANNEL/$SAMPLE",
                  "production.hadd.maxopenfiles": 100}
        self.assertTrue(manage.create(self.path, values=values, sources=["Guessed for lxplus (user jdoe)."]))
        text = self.path.read_text(encoding="utf-8")
        self.assertIn("# Guessed for lxplus (user jdoe).", text)
        self.assertIn('  # batchopts: ""', text)  # not set: a comment line with an example
        self.assertIn("notifications: true  # Set false to remove sound notifications.\nopen_menu_on_start: true\n", text)
        config = UserConfig.load(self.path)
        for setting in manage.SETTINGS:
            expected = values.get(setting.key, setting.example if setting.written else None)
            self.assertEqual(config.get(setting.key), expected, setting.key)
        self.assertEqual(manage.setting_problems(config), [])

    def test_wrong_settings_are_named_with_their_key(self):
        self.write(REVIEWED + "runs:\n  run_root: ~/runs\nproduction:\n  outdir: 5\n  nanodir: ' '\n"
                   "  ncores: 0\n  queue: workday\n  hadd:\n    maxopenfiles: true\nmystudy:\n  x: 5\n")
        config = UserConfig.load(self.path)
        self.assertEqual(manage.setting_problems(config), [
            "runs.run_root: must be an absolute directory (got '~/runs')",
            "production.outdir: must be text (got 5)",
            "production.nanodir: must not be empty (got ' ')",
            "production.ncores: must be a whole number from 1 (got 0)",
            "production.hadd.maxopenfiles: must be a whole number from 1 (got True)"])
        self.assertEqual(len(manage.setting_problems(config, "production")), 4)
        self.assertEqual(manage.check(config)[0], "%s: runs.run_root: must be an absolute directory (got '~/runs')"
                         % (self.path))
        self.write(REVIEWED + "runs:\n  run_root: /afs/$USER/runs\n")
        self.assertIn("nothing is expanded", manage.setting_problems(UserConfig.load(self.path))[0])

    def test_importable_before_cmsenv_as_a_top_level_package(self):
        """FastSetup imports it with Utilities/python on sys.path and no TauFW package."""
        code = ("import sys; sys.path.insert(0, sys.argv[1]); from UserConfig import manage; "
                "print(manage.create(sys.argv[2]), manage.create(sys.argv[2]))")
        result = subprocess.run([sys.executable, "-c", code, str(checkout.SOURCE), str(self.path)],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stdout.strip(), "True False")
        self.assertIn("reviewed: false", self.path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
