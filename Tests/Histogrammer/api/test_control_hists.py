"""Histogrammer API ControlHists (the former Plotter API ControlPlots, CL §21): fillhists.py --hists --no-draw
commands as a user types them; the control-histogram files are checked (no ROOT)."""
import os
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

import checkout  # noqa: F401  (must precede TauFW imports)
from TauFW.Histogrammer.api import ControlHists, HistsRequest
from TauFW.Utilities.Process import ProcessRunner


class ControlHistsTests(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="taufw-histogrammer-")
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.histogrammer_dir = os.path.join(self.base, "Histogrammer")
        os.makedirs(os.path.join(self.histogrammer_dir, "config"))
        self.setups = os.path.join(self.base, "Configs", "Histogrammer", "setups")  # next to Histogrammer/, as in TauFW
        os.makedirs(self.setups)
        for channel in ("mutau", "mumu"):
            shutil.copy(os.path.join(str(checkout.REPO), "Configs", "Histogrammer", "setups", "setup_%s.yml" % channel),
                        self.setups)
        self.calls = []
        self.cwds = []
        self.write = True
        self.histogrammer = ControlHists(basedir=self.histogrammer_dir, python="python3",
                                    runner=ProcessRunner(execute=self.execute), find_module=lambda m: True)

    def execute(self, argv, cwd, stream, timeout, env):
        self.calls.append(argv)
        self.cwds.append(cwd)
        if self.write:  # fillhists.py --hists writes hists/<era>/<channel><tag>.root (the fixtures' setups: no tag)
            config = os.path.basename(argv[argv.index("-c") + 1])  # a channel name, or the setup file's path
            era, channel = argv[argv.index("-y") + 1], config[6:-4] if config.endswith(".yml") else config
            tag = argv[argv.index("-t") + 1] if "-t" in argv else ""
            os.makedirs(os.path.join(cwd, "hists", era), exist_ok=True)
            open(os.path.join(cwd, "hists", era, "%s%s.root" % (channel, tag)), "w").close()
        return 0

    def test_commands(self):
        request = HistsRequest(eras=[2025], configs=["mutau", "mumu"], variables=["m_vis", "pt_*"], serial=True,
                               selections=["baseline"], tag="_v1", notauidsf=True)
        plan = self.histogrammer.plan(request)
        self.assertEqual([c.shell() for c in plan.commands], [
            "python3 fillhists.py -y 2025 -c mutau -V m_vis 'pt_*' -S baseline -s -r -t _v1 --hists --no-draw",
            "python3 fillhists.py -y 2025 -c mumu -V m_vis 'pt_*' -S baseline -s -r -t _v1 --hists --no-draw"])
        self.assertEqual([c.label for c in plan.commands], ["controlhists mutau 2025", "controlhists mumu 2025"])
        self.assertEqual(plan.commands[0].cwd, self.histogrammer_dir)
        self.assertEqual(plan.commands[0].expects, ("hists/2025/mutau_v1.root",))
        self.assertEqual(plan.notes, ())
        minimal = self.histogrammer.plan(HistsRequest(eras="2025"))
        self.assertEqual([c.shell() for c in minimal.commands],
                         ["python3 fillhists.py -y 2025 -c mutau --hists --no-draw"])

    def test_make_lists_the_files(self):
        report = self.histogrammer.make(HistsRequest(eras=["2025"], configs=["mutau", "mumu"]),
                                   os.path.join(self.base, "logs"))
        self.assertTrue(report.ok)
        hists = os.path.join(self.histogrammer_dir, "hists", "2025")
        self.assertEqual(report.artifacts, (
            {"kind": "control_histograms", "era": "2025", "config": "mutau", "channel": "mutau", "tag": "",
             "file": os.path.join(hists, "mutau.root")},
            {"kind": "control_histograms", "era": "2025", "config": "mumu", "channel": "mumu", "tag": "",
             "file": os.path.join(hists, "mumu.root")}))

    def test_no_file_is_a_failure(self):
        self.write = False
        report = self.histogrammer.make(HistsRequest(eras=["2025"]), os.path.join(self.base, "logs"))
        self.assertFalse(report.ok)
        self.assertEqual(report.failed.missing, ("hists/2025/mutau.root",))

    def test_missing_setup(self):
        request = HistsRequest(eras=["2025"], configs=["etau", "config/other.yml"])
        etau = os.path.join(self.setups, "setup_etau.yml")
        self.assertEqual(self.histogrammer.plan(request).notes,
                         ("channel setup %s not found" % (etau),
                          "channel setup %s not found" % (os.path.join(self.histogrammer_dir, "config", "other.yml"))))
        problems = self.histogrammer.preflight(request)
        self.assertIn("channel setup %s not found" % (etau), problems)

    def test_pico_config_and_absolute_setup(self):
        setup = os.path.join(self.base, "bundle", "setup_mutau.yml")  # a setup outside Histogrammer/ (a bundle file)
        os.makedirs(os.path.dirname(setup))
        shutil.copy(os.path.join(self.setups, "setup_mutau.yml"), setup)
        request = HistsRequest(eras=["2025"], configs=[setup], pico_config="/run/bundle/pico.json")
        plan = self.histogrammer.plan(request)
        self.assertEqual(plan.notes, ())
        self.assertEqual(plan.commands[0].env, (("TAUFW_PICO_CONFIG", "/run/bundle/pico.json"),))
        self.assertEqual(plan.artifacts[0]["channel"], "mutau")
        self.assertEqual(self.histogrammer.pico_config_source(request), "/run/bundle/pico.json")
        self.assertIn("no PicoProducer configuration /run/bundle/pico.json", " ".join(self.histogrammer.preflight(request)))
        self.assertEqual(self.histogrammer.plan(HistsRequest(eras=["2025"])).commands[0].env, ())
        self.assertEqual(self.histogrammer.config_file("mutau"),
                         os.path.join(self.setups, "setup_mutau.yml"))
        self.assertEqual(self.histogrammer.config_file(setup), setup)

    def test_output_directory(self):
        outdir = os.path.join(self.base, "run", "stages", "hists")
        pico = os.path.join(self.base, "pico.json")
        request = HistsRequest(eras=["2025"], configs=["mutau", "mumu"], outdir=outdir, pico_config=pico)
        plan = self.histogrammer.plan(request)
        setup = os.path.join(self.setups, "setup_mutau.yml")
        self.assertEqual(plan.commands[0].argv,  # the script and the setup as absolute paths: it runs in outdir
                         ("python3", os.path.join(self.histogrammer_dir, "fillhists.py"), "-y", "2025", "-c", setup,
                          "--hists", "--no-draw"))
        self.assertEqual({plan.cwd} | {c.cwd for c in plan.commands}, {outdir})
        self.assertEqual(plan.commands[0].env, (("TAUFW_PICO_CONFIG", pico),))
        self.assertEqual(plan.artifacts[0]["file"], os.path.join(outdir, "hists", "2025", "mutau.root"))
        report = self.histogrammer.make(request, os.path.join(self.base, "logs"))  # makes outdir
        self.assertTrue(report.ok)
        self.assertEqual(self.cwds, [outdir, outdir])
        self.assertEqual([a["file"] for a in report.artifacts], [os.path.join(outdir, "hists", "2025", "mutau.root"),
                                                                 os.path.join(outdir, "hists", "2025", "mumu.root")])
        self.assertFalse(os.path.exists(os.path.join(self.histogrammer_dir, "hists")))  # nothing written in Histogrammer/

    def test_setup_tag(self):  # BUGS L08: fillhists.py names its files with the setup's tag plus -t
        setup = os.path.join(self.setups, "setup_mutau.yml")
        with open(setup) as stream:
            text = stream.read()
        with open(setup, "w") as stream:
            stream.write(text.replace('tag: ""', 'tag: "_inc"'))
        plan = self.histogrammer.plan(HistsRequest(eras=["2025"], tag="_v1"))
        self.assertEqual(plan.commands[0].expects, ("hists/2025/mutau_inc_v1.root",))
        self.assertEqual((plan.artifacts[0]["tag"], os.path.basename(plan.artifacts[0]["file"])),
                         ("_inc_v1", "mutau_inc_v1.root"))

    def test_same_file_names_note(self):  # BUGS L10
        other = os.path.join(self.setups, "setup_mutau_copy.yml")
        shutil.copy(os.path.join(self.setups, "setup_mutau.yml"), other)
        notes = self.histogrammer.plan(HistsRequest(eras=["2025"], configs=["mutau", other, "mumu"])).notes
        self.assertEqual(len(notes), 1)
        self.assertIn("configs mutau, %s write the same file names" % (other), notes[0])

    def test_output_directory_problems(self):
        outdir = os.path.join(self.base, "out")
        pico = os.path.join(self.base, "pico.json")
        with open(pico, "w") as stream:
            stream.write('{"picodir": "analysis/$ERA/$GROUP"}')
        request = HistsRequest(eras=["2025"], outdir=outdir, pico_config=pico)
        problems = " ".join(self.histogrammer.preflight(request))
        self.assertIn("picodir 'analysis/$ERA/$GROUP' of %s is relative" % (pico), problems)
        self.assertNotIn("not empty", problems)
        os.makedirs(outdir)
        open(os.path.join(outdir, "leftover.root"), "w").close()  # an interrupted attempt
        with open(pico, "w") as stream:
            stream.write('{"picodir": "/eos/user/x/analysis/$ERA/$GROUP"}')
        problems = " ".join(self.histogrammer.preflight(request))
        self.assertIn("output directory %s is not empty" % (outdir), problems)
        self.assertNotIn("picodir", problems)
        self.assertNotIn("not empty", " ".join(self.histogrammer.preflight(HistsRequest(eras=["2025"]))))

    def test_tuple_pattern(self):
        pattern = "/eos/cms/store/group/phys_tau/TauFW/pico2024/TES_variations/$ERA/$GROUP"
        request = HistsRequest(eras=["2025"], tuples=pattern, pico_config="/run/bundle/pico.json",
                               outdir=os.path.join(self.base, "out"))
        command = self.histogrammer.plan(request).commands[0]
        self.assertEqual(command.argv[-4:-2], ("--tuples", pattern))
        self.assertEqual(command.env, ())  # the PicoProducer configuration is not used
        with mock.patch.dict(os.environ, {"CMSSW_BASE": "/cmssw"}):  # only the tuple checks below
            self.assertEqual(self.histogrammer.preflight(request), ())  # nor checked
            problems = self.histogrammer.preflight(HistsRequest(eras=["2025"], tuples="/eos/x/$ERA/$DAS"))
            self.assertEqual(problems, ("tuple pattern /eos/x/$ERA/$DAS has $DAS, which the scripts do not fill "
                                        "(they fill $ERA, $GROUP, $SAMPLE, $CHANNEL, $TAG)",))
            problems = self.histogrammer.preflight(HistsRequest(eras=["2025"], tuples="pico/$ERA/$GROUP",
                                                           outdir=os.path.join(self.base, "out")))
        self.assertEqual(problems, ("tuple pattern 'pico/$ERA/$GROUP' is relative: the scripts would look for the "
                                    "tuples relative to %s" % (os.path.join(self.base, "out")),))
        self.assertNotIn("--tuples", self.histogrammer.plan(HistsRequest(eras=["2025"])).commands[0].argv)

    def test_sample_files(self):  # CL §20: sample model files, --samples
        templates = os.path.join(str(checkout.REPO), "Configs", "Histogrammer", "samples")
        samples = (os.path.join(templates, "v15_2025.yml"), os.path.join(templates, "v15_2024.yml"))
        outdir = os.path.join(self.base, "out")
        command = self.histogrammer.plan(HistsRequest(eras=["2025"], samples=samples, outdir=outdir)).commands[0]
        self.assertEqual(command.argv[-5:-2], ("--samples",) + samples)
        self.assertNotIn("--samples", self.histogrammer.plan(HistsRequest(eras=["2025"])).commands[0].argv)
        self.assertEqual(self.histogrammer.sample_names(samples, "2025", "mutau")[1], "Muon*Run2025*")
        self.assertEqual(self.histogrammer.samples_problems(samples, ["2025", "2024"]), ())
        problems = self.histogrammer.samples_problems(samples, ["2025", "2023C"])
        self.assertEqual(len(problems), 1)
        self.assertIn("no sample file(s) for era '2023C'", problems[0])
        self.assertIn("not found", self.histogrammer.samples_problems(("/no/such.yml",), ["2025"])[0])
        # the tuple files of the requested samples: every MC file and the data pattern
        tuples = os.path.join(self.base, "tuples", "$ERA", "$GROUP")
        names, data = self.histogrammer.sample_names(samples, "2025", "mumu")
        sample_model = __import__("TauFW.Histogrammer.sample.model", fromlist=["pick"])
        for row in sample_model.pick(samples, "2025").mc:
            directory = os.path.join(self.base, "tuples", "2025", row["group"])
            os.makedirs(directory, exist_ok=True)
            open(os.path.join(directory, "%s_mumu.root" % (row["name"])), "w").close()
        problems = self.histogrammer.sample_file_problems(samples, ["2025"], ["mumu"], tuples)
        self.assertEqual(len(problems), 1)
        self.assertIn("1 tuple file(s)", problems[0])  # the data
        os.makedirs(os.path.join(self.base, "tuples", "2025", "Data"))
        open(os.path.join(self.base, "tuples", "2025", "Data", "Muon0_Run2025C_mumu.root"), "w").close()
        self.assertEqual(self.histogrammer.sample_file_problems(samples, ["2025"], ["mumu", "mumu"], tuples), ())
        os.remove(os.path.join(self.base, "tuples", "2025", "DY", "%s_mumu.root" % (names[0])))
        with mock.patch.dict(os.environ, {"CMSSW_BASE": "/cmssw"}):
            problems = self.histogrammer.preflight(HistsRequest(eras=["2025"], configs=["mumu"], samples=samples,
                                                           tuples=tuples, outdir=outdir))
        self.assertEqual(len(problems), 1)
        self.assertIn(names[0], problems[0])

    def test_default_module_lookup(self):  # BUGS L13: find_spec raises for an imported module without __spec__
        imported = types.ModuleType("taufw_test_imported")
        imported.__spec__ = None  # like CMSSW's ROOT once PicoProducer imported it
        with mock.patch.dict(sys.modules, {"taufw_test_imported": imported, "taufw_test_blocked": None}):
            lookup = ControlHists(basedir=self.base).find_module
            self.assertTrue(lookup("taufw_test_imported"))
            self.assertFalse(lookup("taufw_test_blocked"))
            self.assertFalse(lookup("taufw_test_missing"))
            self.assertFalse(lookup("taufw_test_missing.sub"))
            self.assertTrue(lookup("json"))

    def test_request_checks(self):
        with self.assertRaises(ValueError):
            HistsRequest(eras=[])
        self.assertEqual(self.histogrammer.request(eras=[2025]).eras, ("2025",))
        with self.assertRaises(TypeError):
            self.histogrammer.request(eras=[2025], variable=["x"])
        for option in ("fraction", "pdf", "text"):  # drawing options: the Plotter's PlotsRequest (CL §21 S4)
            with self.assertRaises(TypeError):
                self.histogrammer.request(eras=[2025], **{option: True})


if __name__ == "__main__":
    unittest.main()
