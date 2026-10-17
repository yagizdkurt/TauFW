"""Plotter API: plot.py commands as a user types them; plots are checked (no ROOT)."""
import os
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

import checkout  # noqa: F401  (must precede TauFW imports)
from TauFW.Plotter.api import ControlPlots, PlotsRequest
from TauFW.Utilities.Process import ProcessRunner


class ControlPlotsTests(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="taufw-plotter-")
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.plotter_dir = os.path.join(self.base, "Plotter")
        os.makedirs(os.path.join(self.plotter_dir, "config"))
        for channel in ("mutau", "mumu"):
            shutil.copy(os.path.join(str(checkout.BASEDIR), "config", "setup_%s.yml" % channel),
                        os.path.join(self.plotter_dir, "config"))
        self.calls = []
        self.cwds = []
        self.write = True
        self.plotter = ControlPlots(basedir=self.plotter_dir, python="python3",
                                    runner=ProcessRunner(execute=self.execute), find_module=lambda m: True)

    def execute(self, argv, cwd, stream, timeout, env):
        self.calls.append(argv)
        self.cwds.append(cwd)
        if self.write:  # plot.py writes plots/<era>/<var>_<channel>-<selection>-<era><tag>.png
            config = os.path.basename(argv[argv.index("-c") + 1])  # a channel name, or the setup file's path
            era, channel = argv[argv.index("-y") + 1], {"mutau": "mt", "mumu": "mm"}[config[6:-4] if
                                                                                      config.endswith(".yml") else config]
            os.makedirs(os.path.join(cwd, "plots", era), exist_ok=True)
            for variable in ("m_vis", "pt_1"):
                open(os.path.join(cwd, "plots", era, "%s_%s-baseline-%s.png" % (variable, channel, era)), "w").close()
        return 0

    def test_commands(self):
        request = PlotsRequest(eras=[2025], configs=["mutau", "mumu"], variables=["m_vis", "pt_*"], pdf=True,
                               selections=["baseline"], tag="_v1", text="test")
        plan = self.plotter.plan(request)
        self.assertEqual([c.shell() for c in plan.commands], [
            "python3 plot.py -y 2025 -c mutau -V m_vis 'pt_*' -S baseline -p -t _v1 -T test",
            "python3 plot.py -y 2025 -c mumu -V m_vis 'pt_*' -S baseline -p -t _v1 -T test"])
        self.assertEqual(plan.commands[0].cwd, self.plotter_dir)
        self.assertEqual(plan.commands[0].expects, ("plots/2025/*_mt-*-2025_v1.png",))
        self.assertEqual(plan.notes, ())
        minimal = self.plotter.plan(PlotsRequest(eras="2025"))
        self.assertEqual([c.shell() for c in minimal.commands], ["python3 plot.py -y 2025 -c mutau"])

    def test_make_counts_plots(self):
        report = self.plotter.make(PlotsRequest(eras=["2025"], configs=["mutau", "mumu"]),
                                   os.path.join(self.base, "logs"))
        self.assertTrue(report.ok)
        self.assertEqual([(a["channel"], a["nfiles"]) for a in report.artifacts], [("mutau", 2), ("mumu", 2)])

    def test_no_plots_is_a_failure(self):
        self.write = False
        report = self.plotter.make(PlotsRequest(eras=["2025"]), os.path.join(self.base, "logs"))
        self.assertFalse(report.ok)
        self.assertEqual(report.failed.missing, ("plots/2025/*_mt-*-2025.png",))

    def test_missing_setup(self):
        request = PlotsRequest(eras=["2025"], configs=["etau", "config/other.yml"])
        self.assertEqual(self.plotter.plan(request).notes,
                         ("channel setup config/setup_etau.yml not found in %s" % (self.plotter_dir),
                          "channel setup config/other.yml not found in %s" % (self.plotter_dir)))
        problems = self.plotter.preflight(request)
        self.assertIn("channel setup config/setup_etau.yml not found in %s" % (self.plotter_dir), problems)

    def test_pico_config_and_absolute_setup(self):
        setup = os.path.join(self.base, "bundle", "setup_mutau.yml")  # a setup outside Plotter/ (a bundle file)
        os.makedirs(os.path.dirname(setup))
        shutil.copy(os.path.join(self.plotter_dir, "config", "setup_mutau.yml"), setup)
        request = PlotsRequest(eras=["2025"], configs=[setup], pico_config="/run/bundle/pico.json")
        plan = self.plotter.plan(request)
        self.assertEqual(plan.notes, ())
        self.assertEqual(plan.commands[0].env, (("TAUFW_PICO_CONFIG", "/run/bundle/pico.json"),))
        self.assertEqual(plan.artifacts[0]["channel"], "mutau")
        self.assertEqual(self.plotter.pico_config_source(request), "/run/bundle/pico.json")
        self.assertIn("no PicoProducer configuration /run/bundle/pico.json", " ".join(self.plotter.preflight(request)))
        self.assertEqual(self.plotter.plan(PlotsRequest(eras=["2025"])).commands[0].env, ())
        self.assertEqual(self.plotter.config_file("mutau"),
                         os.path.join(self.plotter_dir, "config", "setup_mutau.yml"))
        self.assertEqual(self.plotter.config_file(setup), setup)

    def test_output_directory(self):
        outdir = os.path.join(self.base, "run", "stages", "plots")
        pico = os.path.join(self.base, "pico.json")
        request = PlotsRequest(eras=["2025"], configs=["mutau", "mumu"], outdir=outdir, pico_config=pico)
        plan = self.plotter.plan(request)
        setup = os.path.join(self.plotter_dir, "config", "setup_mutau.yml")
        self.assertEqual(plan.commands[0].argv,  # plot.py and the setup as absolute paths: plot.py runs in outdir
                         ("python3", os.path.join(self.plotter_dir, "plot.py"), "-y", "2025", "-c", setup))
        self.assertEqual({plan.cwd} | {c.cwd for c in plan.commands}, {outdir})
        self.assertEqual(plan.commands[0].env, (("TAUFW_PICO_CONFIG", pico),))
        self.assertEqual(plan.artifacts[0]["directory"], os.path.join(outdir, "plots", "2025"))
        report = self.plotter.make(request, os.path.join(self.base, "logs"))  # makes outdir
        self.assertTrue(report.ok)
        self.assertEqual(self.cwds, [outdir, outdir])
        self.assertEqual([a["nfiles"] for a in report.artifacts], [2, 2])
        self.assertFalse(os.path.exists(os.path.join(self.plotter_dir, "plots")))  # nothing written in Plotter/

    def test_nfiles_counts_only_this_run(self):  # BUGS L09: Plotter/plots/ is shared by all runs
        old = os.path.join(self.plotter_dir, "plots", "2025")
        os.makedirs(old)
        open(os.path.join(old, "eta_1_mt-baseline-2025.png"), "w").close()  # a plot of an earlier run
        request = PlotsRequest(eras=["2025"], outdir=os.path.join(self.base, "out"))
        self.assertEqual([a["nfiles"] for a in self.plotter.make(request, os.path.join(self.base, "logs")).artifacts],
                         [2])

    def test_setup_tag(self):  # BUGS L08: plot.py names its files with the setup's tag plus -t
        setup = os.path.join(self.plotter_dir, "config", "setup_mutau.yml")
        with open(setup) as stream:
            text = stream.read()
        with open(setup, "w") as stream:
            stream.write(text.replace('tag: ""', 'tag: "_inc"'))
        plan = self.plotter.plan(PlotsRequest(eras=["2025"], tag="_v1"))
        self.assertEqual(plan.commands[0].expects, ("plots/2025/*_mt-*-2025_inc_v1.png",))

    def test_same_file_names_note(self):  # BUGS L10
        other = os.path.join(self.plotter_dir, "config", "setup_mutau_copy.yml")
        shutil.copy(os.path.join(self.plotter_dir, "config", "setup_mutau.yml"), other)
        notes = self.plotter.plan(PlotsRequest(eras=["2025"], configs=["mutau", other, "mumu"])).notes
        self.assertEqual(len(notes), 1)
        self.assertIn("configs mutau, %s write the same file names" % (other), notes[0])

    def test_output_directory_problems(self):
        outdir = os.path.join(self.base, "out")
        pico = os.path.join(self.base, "pico.json")
        with open(pico, "w") as stream:
            stream.write('{"picodir": "analysis/$ERA/$GROUP"}')
        request = PlotsRequest(eras=["2025"], outdir=outdir, pico_config=pico)
        problems = " ".join(self.plotter.preflight(request))
        self.assertIn("picodir 'analysis/$ERA/$GROUP' of %s is relative" % (pico), problems)
        self.assertNotIn("not empty", problems)
        os.makedirs(outdir)
        open(os.path.join(outdir, "leftover.png"), "w").close()  # an interrupted attempt
        with open(pico, "w") as stream:
            stream.write('{"picodir": "/eos/user/x/analysis/$ERA/$GROUP"}')
        problems = " ".join(self.plotter.preflight(request))
        self.assertIn("output directory %s is not empty" % (outdir), problems)
        self.assertNotIn("picodir", problems)
        self.assertNotIn("not empty", " ".join(self.plotter.preflight(PlotsRequest(eras=["2025"]))))

    def test_tuple_pattern(self):
        pattern = "/eos/cms/store/group/phys_tau/TauFW/pico2024/TES_variations/$ERA/$GROUP"
        request = PlotsRequest(eras=["2025"], tuples=pattern, pico_config="/run/bundle/pico.json",
                               outdir=os.path.join(self.base, "out"))
        command = self.plotter.plan(request).commands[0]
        self.assertEqual(command.argv[-2:], ("--tuples", pattern))
        self.assertEqual(command.env, ())  # the PicoProducer configuration is not used
        with mock.patch.dict(os.environ, {"CMSSW_BASE": "/cmssw"}):  # only the tuple checks below
            self.assertEqual(self.plotter.preflight(request), ())  # nor checked
            problems = self.plotter.preflight(PlotsRequest(eras=["2025"], tuples="/eos/x/$ERA/$DAS"))
            self.assertEqual(problems, ("tuple pattern /eos/x/$ERA/$DAS has $DAS, which the scripts do not fill "
                                        "(they fill $ERA, $GROUP, $SAMPLE, $CHANNEL, $TAG)",))
            problems = self.plotter.preflight(PlotsRequest(eras=["2025"], tuples="pico/$ERA/$GROUP",
                                                           outdir=os.path.join(self.base, "out")))
        self.assertEqual(problems, ("tuple pattern 'pico/$ERA/$GROUP' is relative: the scripts would look for the "
                                    "tuples relative to %s" % (os.path.join(self.base, "out")),))
        self.assertNotIn("--tuples", self.plotter.plan(PlotsRequest(eras=["2025"])).commands[0].argv)

    def test_default_module_lookup(self):  # BUGS L13: find_spec raises for an imported module without __spec__
        imported = types.ModuleType("taufw_test_imported")
        imported.__spec__ = None  # like CMSSW's ROOT once PicoProducer imported it
        with mock.patch.dict(sys.modules, {"taufw_test_imported": imported, "taufw_test_blocked": None}):
            lookup = ControlPlots(basedir=self.base).find_module
            self.assertTrue(lookup("taufw_test_imported"))
            self.assertFalse(lookup("taufw_test_blocked"))
            self.assertFalse(lookup("taufw_test_missing"))
            self.assertFalse(lookup("taufw_test_missing.sub"))
            self.assertTrue(lookup("json"))

    def test_request_checks(self):
        with self.assertRaises(ValueError):
            PlotsRequest(eras=[])
        self.assertEqual(self.plotter.request(eras=[2025]).eras, ("2025",))
        with self.assertRaises(TypeError):
            self.plotter.request(eras=[2025], variable=["x"])


if __name__ == "__main__":
    unittest.main()
