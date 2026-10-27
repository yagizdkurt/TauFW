"""The Framework's settings from the user config (Framework/python/user_settings.py): run_root and a production
stage's PicoProducer settings, their precedence, and how check, plan and start show them (CL §41)."""
import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

import checkout  # noqa: F401  (must precede TauFW imports)
import fakes
from TauFW.Framework import Framework, Recipe, SilentReporter, check_recipe, user_settings
from TauFW.Framework.recipes.recipe import recipe_warnings
from TauFW.Framework.stages import ProductionStage
from TauFW.Utilities import UserConfig
from test_framework import RECIPE, Clock

HEADER = "taufw_user:\n  version: 1\n  reviewed: true\n"
SETTINGS = HEADER + """\
runs:
  run_root: {root}/user_runs
production:
  batch: HTCondor
  queue: workday
  outdir: /eos/user/j/jdoe/taufw/output/$ERA/$CHANNEL/$SAMPLE
  ncores: 8
  hadd:
    maxopenfiles: 100
mystudy:
  plotdir: /eos/user/j/jdoe/www
"""


class UserSettingsTestCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="taufw-test-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.path = os.path.join(self.root, "UserConfig.yaml")
        patcher = mock.patch.dict(os.environ, {"TAUFW_USER_CONFIG": self.path})
        patcher.start()
        self.addCleanup(patcher.stop)

    def user_config(self, text):
        with open(self.path, "w") as stream:
            stream.write(text.format(root=self.root.replace("\\", "/")))

    def framework(self, pico, recipe=None):
        recipe = Recipe.from_dict(json.loads(json.dumps(recipe or RECIPE)), source="test.yml")
        stages = {"production": ProductionStage(pico, user_settings.production_settings())}
        return Framework(recipe, stages, reporter=SilentReporter(), sleep=lambda s: None, clock=Clock())


class ProductionSettingsTests(UserSettingsTestCase):
    def test_the_settings_map_to_the_picoproducer_configuration_and_the_request(self):
        self.user_config(SETTINGS)
        settings = user_settings.production_settings()
        self.assertEqual(settings.overrides, {'batch': "HTCondor", 'maxopenfiles': 100,
                                              'outdir': "/eos/user/j/jdoe/taufw/output/$ERA/$CHANNEL/$SAMPLE"})
        self.assertEqual(settings.defaults, {'queue': "workday", 'ncores': 8})
        self.assertEqual(settings.used, ("production.batch", "production.hadd.maxopenfiles", "production.ncores",
                                         "production.outdir", "production.queue"))
        self.assertEqual(str(settings.path), self.path)

    def test_without_a_file_nothing_is_set(self):
        settings = user_settings.production_settings()
        self.assertEqual((settings.overrides, settings.defaults, settings.used), ({}, {}, ()))
        self.assertIsNone(user_settings.run_root())

    def test_the_recipe_wins_over_the_user_config(self):
        self.user_config(SETTINGS)
        stage = ProductionStage(fakes.FakePicoProducer(), user_settings.production_settings())
        spec = Recipe.from_dict(json.loads(json.dumps(RECIPE))).stages[0].spec
        request = stage.request(spec)
        self.assertEqual((request['queue'], request['ncores'], request['batchopts']), ("workday", 8, None))
        recipe = json.loads(json.dumps(RECIPE))
        recipe["stages"][0].update(queue="espresso", ncores=2)
        request = stage.request(Recipe.from_dict(recipe).stages[0].spec)
        self.assertEqual((request['queue'], request['ncores']), ("espresso", 2))

    def test_without_ncores_anywhere_the_default_is_used(self):
        spec = Recipe.from_dict(json.loads(json.dumps(RECIPE))).stages[0].spec
        request = ProductionStage(fakes.FakePicoProducer()).request(spec)
        self.assertEqual(request['ncores'], 4)  # as before CL §41 (and in run.json: BBB framework.production)
        self.assertIsNone(request['queue'])

    def test_a_wrong_production_setting_stops_where_it_is_used(self):
        self.user_config(HEADER + "production:\n  outdir: 5\n")
        with self.assertRaises(UserConfig.UserConfigError) as error:
            user_settings.production_settings()
        self.assertIn("production.outdir: must be text (got 5)", str(error.exception))
        self.assertEqual(user_settings.production_problems(),
                         ["%s: production.outdir: must be text (got 5)" % (self.path)])

    def test_the_run_record_names_the_settings_used(self):
        self.user_config(SETTINGS)
        pico = fakes.FakePicoProducer(statuses=[fakes.pending("DY", "TT")])
        record = self.framework(pico).start(run_root=self.root)
        self.assertEqual(record.pico_config['user_config'],
                         {'path': self.path, 'settings': list(user_settings.production_settings().used)})
        submitted = [request for name, request in pico.calls if name == "submit"][0]
        self.assertEqual((submitted['queue'], submitted['ncores']), ("workday", 8))
        recorded = record.stage("production").request  # run.json: what was used, not only the recipe
        self.assertEqual((recorded['queue'], recorded['ncores']), ("workday", 8))

    def test_without_settings_the_run_record_is_unchanged(self):
        self.user_config(HEADER)
        record = self.framework(fakes.FakePicoProducer(statuses=[fakes.pending("DY")])).start(run_root=self.root)
        self.assertNotIn('user_config', record.pico_config)
        self.assertEqual((record.stage("production").request['ncores'], record.stage("production").request['queue']),
                         (4, None))


class RunRootTests(UserSettingsTestCase):
    def test_start_uses_the_user_config_after_the_command_line_and_the_recipe(self):
        self.user_config(SETTINGS)
        user_runs = os.path.join(self.root, "user_runs")
        record = self.framework(fakes.FakePicoProducer(statuses=[fakes.pending("DY")])).start()
        self.assertEqual(os.path.dirname(record.run_dir), os.path.abspath(user_runs))
        recipe = dict(json.loads(json.dumps(RECIPE)), run_root=os.path.join(self.root, "recipe_runs"))
        record = self.framework(fakes.FakePicoProducer(statuses=[fakes.pending("DY")]), recipe).start()
        self.assertEqual(os.path.dirname(record.run_dir), os.path.join(self.root, "recipe_runs"))
        record = self.framework(fakes.FakePicoProducer(statuses=[fakes.pending("DY")]), recipe).start(
            run_root=os.path.join(self.root, "given"))
        self.assertEqual(os.path.dirname(record.run_dir), os.path.join(self.root, "given"))

    def test_no_run_root_warning_with_the_user_configs(self):
        self.assertEqual([w.where for w in recipe_warnings(RECIPE)], ["run_root"])
        self.user_config(SETTINGS)
        self.assertEqual(recipe_warnings(RECIPE), [])

    def test_a_wrong_run_root_stops_start_but_not_the_warnings(self):
        self.user_config(HEADER + "runs:\n  run_root: ~/runs\n")
        self.assertEqual([w.where for w in recipe_warnings(RECIPE)], ["run_root"])  # as without one
        with self.assertRaises(UserConfig.UserConfigError):
            self.framework(fakes.FakePicoProducer(statuses=[fakes.pending("DY")])).start()


class CheckAndCommandLineTests(UserSettingsTestCase):
    def setUp(self):
        super().setUp()
        spec = importlib.util.spec_from_file_location("taufw_cli", str(checkout.TAUFW_SCRIPT))
        self.cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.cli)
        self.reporter = SilentReporter()
        self.cli.FrameworkReporter = lambda verbosity=0: self.reporter
        self.recipe = os.path.join(self.root, "r.json")
        with open(self.recipe, "w") as stream:
            json.dump(RECIPE, stream)

    def test_a_wrong_production_setting_is_a_problem_of_a_production_recipe_only(self):
        self.user_config(HEADER + "production:\n  ncores: 0\n")
        check = check_recipe(self.recipe)
        self.assertEqual([(i.where, i.message) for i in check.issues],
                         [("user config", "%s: production.ncores: must be a whole number from 1 (got 0)"
                           % (self.path))])
        python_only = os.path.join(self.root, "p.json")
        with open(python_only, "w") as stream:
            json.dump({"name": "p", "stages": [{"stage": "python", "id": "s", "inputs": None, "file": "s.py"}]},
                      stream)
        open(os.path.join(self.root, "s.py"), "w").close()
        self.assertEqual(check_recipe(python_only).issues, ())
        self.assertEqual(self.cli.main(["check", self.recipe]), 1)

    def test_plan_names_the_settings_and_the_run_root(self):
        self.user_config(SETTINGS)
        pico = fakes.FakePicoProducer()
        real = Framework.from_recipe
        with mock.patch.object(self.cli.Framework, "from_recipe",
                               side_effect=lambda r, reporter=None, **kw: real(r, reporter=reporter, pico=pico)):
            self.assertEqual(self.cli.main(["plan", self.recipe]), 0)
        messages = [text for kind, text in self.reporter.messages if kind == "message"]
        self.assertIn("Run root: %s/user_runs (user config)" % (self.root.replace("\\", "/")), messages)
        self.assertIn("PicoProducer config: PicoProducer/config/config.json (default); from your user config: "
                      "production.batch, production.hadd.maxopenfiles, production.ncores, production.outdir, "
                      "production.queue", messages)
        self.assertEqual([text for kind, text in self.reporter.messages if kind == "warning"], [])

    def test_a_wrong_setting_ends_plan_in_one_line(self):
        self.user_config(HEADER + "production:\n  outdir: 5\n")
        pico = fakes.FakePicoProducer()
        real = Framework.from_recipe
        with mock.patch.object(self.cli.Framework, "from_recipe",
                               side_effect=lambda r, reporter=None, **kw: real(r, reporter=reporter, pico=pico)):
            self.assertEqual(self.cli.main(["plan", self.recipe]), 1)  # no traceback
        self.assertIn("%s: production.outdir: must be text (got 5)" % (self.path),
                      [text for kind, text in self.reporter.messages if kind == "warning"])


if __name__ == "__main__":
    unittest.main()
