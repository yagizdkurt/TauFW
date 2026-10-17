"""Sample model files in recipes (CL §22): the `samples` option of plots and histograms (validation), and the
comparison of what production makes with what its readers ask for (samples.py: plan lists, start refuses)."""
import json
import os
import shutil
import tempfile
import unittest

import checkout
import fakes
from TauFW.Framework import Framework, RecipeError, check_recipe
from TauFW.Histogrammer.api import ControlPlots
from TauFW.Histogrammer.sample.model import pick

TEMPLATES = checkout.REPO / "Configs" / "Plotter" / "samples"
PRODUCTION = {"stage": "production", "id": "production", "inputs": None, "eras": [2025], "channels": ["mutau"]}
PLOTS = {"stage": "plots", "id": "plots", "inputs": {"tuples": "production"}, "eras": [2025], "configs": ["mutau"],
         "samples": ["samples_2025.yml"]}
MC = [row["name"] for row in pick([str(TEMPLATES / "v15_2025.yml")], "2025").mc]


class Pico(fakes.FakePicoProducer):
    """A PicoProducer that makes these (era, channel, sample) tuples."""

    def __init__(self, made):
        super().__init__(samples=tuple(name for _, _, name in made))
        self.made = tuple(made)

    def sample_names(self, request):
        return self.made


def made(*names, data=("Muon_Run2025C",)):
    return [("2025", "mutau", name) for name in list(names) + list(data)]


class SamplesTestCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="taufw-test-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.bundle = os.path.join(self.root, "tes")
        os.makedirs(self.bundle)
        shutil.copy(str(TEMPLATES / "v15_2025.yml"), os.path.join(self.bundle, "samples_2025.yml"))

    def write_recipe(self, *stages):
        with open(os.path.join(self.bundle, "recipe.yml"), "w") as stream:
            json.dump({"name": "tes", "pico": {"config": None}, "stages": list(stages)}, stream)
        return self.bundle

    def framework(self, made_samples, *stages):
        plotter = ControlPlots(basedir=str(checkout.REPO / "Histogrammer"), find_module=lambda name: True)
        return Framework.from_recipe(self.write_recipe(*stages), pico=Pico(made_samples), plotter=plotter)


class ValidationTests(SamplesTestCase):
    def test_bundle_copy_is_valid(self):
        self.assertTrue(check_recipe(self.write_recipe(PRODUCTION, PLOTS)).ok)

    def test_module_path_is_refused(self):
        check = check_recipe(self.write_recipe(PRODUCTION, dict(PLOTS, samples=["config/samples_v15_2025.yml"])))
        self.assertIn("stages[1] (plots).samples: config/samples_v15_2025.yml is not a file of the bundle (%s)"
                      % (self.bundle), [str(issue) for issue in check.issues])

    def test_an_era_without_a_file(self):
        check = check_recipe(self.write_recipe(PRODUCTION, dict(PLOTS, eras=[2025, 2024])))
        self.assertFalse(check.ok)
        self.assertIn("no sample file(s) for era '2024'", " ".join(str(issue) for issue in check.issues))

    def test_a_broken_copy(self):
        with open(os.path.join(self.bundle, "samples_2025.yml"), "a") as stream:
            stream.write("lumi: 1\n")
        check = check_recipe(self.write_recipe(PRODUCTION, PLOTS))
        self.assertIn("unknown key(s) lumi", " ".join(str(issue) for issue in check.issues))


class ComparisonTests(SamplesTestCase):
    def test_production_makes_what_the_reader_asks_for(self):
        plan = self.framework(made(*MC), PRODUCTION, PLOTS).plan()
        self.assertEqual((plan.sample_problems, plan.sample_warnings), ((), ()))

    def test_missing_mc_sample_and_data(self):
        fw = self.framework(made(*MC[1:], data=()), PRODUCTION, PLOTS)
        problems = [str(issue) for issue in fw.plan().sample_problems]
        self.assertEqual(len(problems), 2)
        self.assertIn("1 MC sample(s) of 2025 mutau are not made by production stage 'production': %s" % (MC[0]),
                      problems[0])
        self.assertIn("no data sample of 2025 mutau made by production stage 'production' matches 'Muon*Run2025*'",
                      problems[1])
        with self.assertRaises(RecipeError):  # start refuses before anything is made
            fw.start(run_root=os.path.join(self.root, "runs"))
        self.assertFalse(os.path.exists(os.path.join(self.root, "runs")))

    def test_unread_sample_is_a_warning(self):
        plan = self.framework(made(*MC + ["DYto2TautoMuTauh_M-50"]), PRODUCTION, PLOTS).plan()
        self.assertEqual(plan.sample_problems, ())
        self.assertEqual(len(plan.sample_warnings), 1)
        self.assertIn("1 sample(s) that no reader asks for: 2025 mutau DYto2TautoMuTauh_M-50",
                      str(plan.sample_warnings[0]))

    def test_readers_without_samples_are_not_compared(self):
        old = dict(PLOTS, id="old_plots")
        old.pop("samples")
        plan = self.framework(made("DY"), PRODUCTION, old).plan()
        self.assertEqual((plan.sample_problems, plan.sample_warnings), ((), ()))
        plan = self.framework(made(*MC + ["extra"]), PRODUCTION, PLOTS, old).plan()
        self.assertEqual(plan.sample_warnings, ())  # old_plots may read "extra" through samples_v15.py


if __name__ == "__main__":
    unittest.main()
