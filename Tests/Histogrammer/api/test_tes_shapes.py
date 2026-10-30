"""Histogrammer API TESShapes (the shapes half of the Fitter API until CL §22 H3): the createinputsTES.py commands of
run_inputs.sh, run in the request's output directory; the shape files are checked (no ROOT)."""
import os
import shlex
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

import checkout  # noqa: F401  (must precede TauFW imports)
from TauFW.Histogrammer.api import TESShapes, ShapesRequest
from TauFW.Histogrammer.sample import model as sample_model
from TauFW.Utilities.Process import ProcessRunner

TT, MM = "../Configs/Fitter/tes_id/config_coarse_TT.yml", "../Configs/Fitter/tes_id/FitSetup_mumu.yml"  # as run_inputs.sh (CL §22)
IN = "input_pt_less_region/againstjet_VTight/againstelectron_Tight"

# Fitter/run_inputs.sh, one working point pair; the API gives the script and the configs as absolute paths
RUN_INPUTS = [
    "python3 %(script)s -y 2025 -c %(tt)s -j VTight -e Tight",
    "python3 %(script)s -y 2025 -c %(mm)s -j VTight -e Tight",
]


TUPLES = "/eos/tuples/$ERA/$GROUP"  # every request names its tuples (CL §37)
TUPLES_ARG = " --tuples " + shlex.quote(TUPLES)


class TESShapesTestCase(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="taufw-shapes-")
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.histogrammer_dir = os.path.join(self.base, "Histogrammer")
        os.makedirs(self.histogrammer_dir)
        for config in (TT, MM):  # the templates next to Histogrammer/, as in TauFW
            os.makedirs(os.path.dirname(os.path.join(self.histogrammer_dir, config)), exist_ok=True)
            shutil.copy(os.path.join(str(checkout.REPO), "Configs", "Fitter", "tes_id", os.path.basename(config)),
                        os.path.join(self.histogrammer_dir, config))
        self.outdir = os.path.join(self.base, "run", "stages", "shapes")
        self.modules = {"ROOT"}
        self.write = True
        self.calls = []
        self.shapes = TESShapes(basedir=self.histogrammer_dir, python="python3",
                                runner=ProcessRunner(execute=self.execute), find_module=lambda m: m in self.modules,
                                read_branches=lambda path: None)  # the branch check: its own test
        self.script = os.path.join(self.histogrammer_dir, "shapes", "TauES", "createinputsTES.py")
        self.paths = {"script": self.script, "tt": os.path.normpath(os.path.join(self.histogrammer_dir, TT)),
                      "mm": os.path.normpath(os.path.join(self.histogrammer_dir, MM))}

    def execute(self, argv, cwd, stream, timeout, env):  # writes the expected files of the command that runs
        self.calls.append((tuple(argv), cwd))
        if self.write:
            command = next(c for c in self.planned if tuple(c.argv) == tuple(argv))
            for path in command.expects:
                os.makedirs(os.path.dirname(os.path.join(cwd, path)), exist_ok=True)
                open(os.path.join(cwd, path), "w").close()
        return 0

    def request(self, **fields):
        return ShapesRequest(**dict(dict(eras=[2025], configs=[TT, MM], jet_wps=["VTight"], ele_wps=["Tight"],
                                         outdir=self.outdir, tuples=TUPLES), **fields))

    def lines(self, commands):
        return [command.shell() for command in commands]

    def run_inputs(self, suffix=""):
        return [line % {key: shlex.quote(path) for key, path in self.paths.items()} + suffix for line in RUN_INPUTS]


class ShapesTests(TESShapesTestCase):
    def test_commands_equal_run_inputs(self):
        plan = self.shapes.plan_shapes(self.request())
        self.assertEqual(self.lines(plan.commands), self.run_inputs(TUPLES_ARG))
        self.assertEqual({plan.cwd} | {c.cwd for c in plan.commands}, {self.outdir})
        self.assertEqual(plan.commands[0].expects, (IN + "/ztt_mt_tes_m_vis.inputs-2025-13TeV_mutau.root",))
        self.assertEqual(plan.commands[1].expects, (IN + "/ztt_mm_tes_m_vis.inputs-2025-13TeV_mumu.root",))
        self.assertEqual([(a["channel"], a["config"]) for a in plan.artifacts], [("mutau", TT), ("mumu", MM)])
        self.assertEqual(plan.notes, ())
        self.assertEqual(self.lines(self.shapes.plan_shapes(self.request(serial=True)).commands)[0],
                         self.run_inputs(" -s" + TUPLES_ARG)[0])

    def test_outdir_is_required(self):  # CL §22 H3, E1: the Histogrammer never writes into Fitter/
        with self.assertRaises(ValueError) as context:
            ShapesRequest(eras=[2025], configs=[TT], jet_wps=["VTight"], ele_wps=["Tight"], tuples=TUPLES)
        self.assertIn("outdir is required", str(context.exception))
        with self.assertRaises(TypeError):  # unknown fields are an error
            self.shapes.shapes_request(eras=[2025], configs=[TT], jet_wps=["VTight"], ele_wps=["Tight"],
                                       outdir=self.outdir, nope=1)

    def test_loop_order(self):
        plan = self.shapes.plan_shapes(self.request(jet_wps=["Medium", "Tight"], ele_wps=["VVLoose", "Tight"]))
        self.assertEqual([c.label for c in plan.commands][:3],
                         ["shapes 2025 Medium VVLoose mutau", "shapes 2025 Medium VVLoose mumu",
                          "shapes 2025 Medium Tight mutau"])
        self.assertEqual(len(plan.commands), 8)

    def test_make_shapes(self):
        request = self.request()
        plan = self.shapes.plan_shapes(request)
        self.assertEqual(plan.commands[0].env, ())  # no $TAUFW_PICO_CONFIG (CL §37)
        self.planned = plan.commands
        logdir = os.path.join(self.base, "logs")
        report = self.shapes.make_shapes(request, logdir)  # makes outdir
        self.assertTrue(report.ok, report.failed)
        self.assertEqual(len(report.artifacts), 2)
        self.assertEqual(report.artifacts[0]["path"],
                         os.path.join(self.outdir, os.path.normpath(IN), "ztt_mt_tes_m_vis.inputs-2025-13TeV_mutau.root"))
        self.assertTrue(all(os.path.isfile(a["path"]) for a in report.artifacts))
        self.assertEqual(sorted(os.listdir(logdir)), ["01_shapes_2025_VTight_Tight_mutau.log",
                                                      "02_shapes_2025_VTight_Tight_mumu.log"])
        self.assertFalse(os.path.exists(os.path.join(self.histogrammer_dir, "input_pt_less_region")))
        self.assertIn("output directory %s is not empty" % (self.outdir),
                      " ".join(self.shapes.preflight_shapes(request)))
        placeholder = os.path.join("<run_dir>", "stages", "shapes")  # a plan before the run exists: kept as given
        self.assertEqual(self.shapes.plan_shapes(self.request(outdir=placeholder)).cwd, placeholder)

    def test_missing_output_fails_although_exit_code_is_zero(self):
        self.write = False  # like a script whose ROOT step failed without a nonzero exit code
        request = self.request()
        self.planned = self.shapes.plan_shapes(request).commands
        report = self.shapes.make_shapes(request, os.path.join(self.base, "logs"))
        self.assertFalse(report.ok)
        self.assertEqual(len(report.results), 1)  # stopped at the first command
        self.assertEqual(report.failed.missing, (IN + "/ztt_mt_tes_m_vis.inputs-2025-13TeV_mutau.root",))
        self.assertEqual(report.artifacts, ())

    def test_missing_config_is_a_note_and_a_preflight_problem(self):
        plan = self.shapes.plan_shapes(self.request(configs=["nope.yml"]))
        self.assertIn("config nope.yml not found", plan.notes[0])
        self.assertEqual(plan.artifacts, ())
        problems = self.shapes.preflight_shapes(self.request(configs=["nope.yml"]))
        self.assertTrue(any("config nope.yml not found" in p for p in problems))
        self.assertEqual(self.shapes.config_file(TT), self.paths["tt"])

    def test_default_module_lookup(self):  # find_spec raises for an imported module without __spec__
        imported = types.ModuleType("taufw_test_imported")
        imported.__spec__ = None  # like CMSSW's ROOT once PicoProducer imported it
        with mock.patch.dict(sys.modules, {"taufw_test_imported": imported, "taufw_test_blocked": None}):
            lookup = TESShapes(basedir=self.base).find_module
            self.assertTrue(lookup("taufw_test_imported"))
            self.assertFalse(lookup("taufw_test_blocked"))
            self.assertFalse(lookup("taufw_test_missing.sub"))

    def test_preflight_environment(self):
        self.modules = set()
        problems = " | ".join(self.shapes.preflight_shapes(self.request()))
        self.assertIn("python cannot import ROOT", problems)
        self.assertNotIn("PicoProducer configuration", problems)  # never read (CL §37)
        self.assertTrue(all(c.env == () for c in self.shapes.plan_shapes(self.request()).commands))

    def test_tuple_pattern(self):
        pattern = "/eos/cms/store/group/phys_tau/TauFW/pico2024/TES_variations/$ERA/$GROUP"
        request = self.request(tuples=pattern)
        commands = self.shapes.plan_shapes(request).commands
        self.assertEqual(self.lines(commands), self.run_inputs(" --tuples '%s'" % (pattern)))
        self.assertTrue(all(c.env == () for c in commands))  # no PicoProducer configuration
        for tuples in (None, ""):  # given, never found (CL §37)
            with self.assertRaises(ValueError) as raised:
                self.request(tuples=tuples)
            self.assertIn("tuples is required", str(raised.exception))
        with self.assertRaises(TypeError):  # the field is gone
            self.request(pico_config="/run/bundle/pico.json")
        self.assertIn("has $DAS, which the scripts do not fill",
                      " ".join(self.shapes.preflight_shapes(self.request(tuples="/eos/x/$DAS"))))
        self.assertIn("tuple pattern 'pico/$ERA' is relative",
                      " ".join(self.shapes.preflight_shapes(self.request(tuples="pico/$ERA"))))


class ShapesSampleFilesTests(TESShapesTestCase):  # CL §20: sample model files, --samples
    def test_artifacts_carry_the_normalisation(self):  # CL §27: the fit labels its plots with them
        samples = (os.path.join(self.base, "v15_2025.yml"),)
        shutil.copy(os.path.join(str(checkout.REPO), "Analyses", "tes_id_2025", "v15_2025.yml"), samples[0])
        artifacts = self.shapes.plan_shapes(self.request(samples=samples)).artifacts
        self.assertEqual({(a['lumi'], a['cme']) for a in artifacts}, {(110.18, 13.6)})
        self.assertEqual({(a['lumi'], a['cme']) for a in self.shapes.plan_shapes(self.request()).artifacts},
                         {(None, None)})  # no sample files: the fit keeps CMSStyle's tables
        missing = (os.path.join(self.base, "missing.yml"),)
        self.assertEqual({a['lumi'] for a in self.shapes.plan_shapes(self.request(samples=missing)).artifacts},
                         {None})  # the preflight says why

    def test_samples_option(self):
        samples = (os.path.join(self.base, "v15_2025.yml"),)
        commands = self.shapes.plan_shapes(self.request(samples=samples)).commands
        self.assertEqual(self.lines(commands), self.run_inputs(TUPLES_ARG + " --samples " + shlex.quote(samples[0])))
        self.assertNotIn("--samples", self.shapes.plan_shapes(self.request()).commands[0].argv)
        self.assertIn("sample file %s not found" % (samples[0]),
                      self.shapes.preflight_shapes(self.request(samples=samples)))
        open(samples[0], "w").close()
        self.assertNotIn("sample file %s not found" % (samples[0]),
                         self.shapes.preflight_shapes(self.request(samples=samples)))


class ShapesVariationTests(TESShapesTestCase):  # §3 A: the variation tuples before the start
    def setUp(self):
        super().setUp()
        self.samples = (os.path.join(self.base, "v15_2025.yml"),)
        shutil.copy(os.path.join(str(checkout.REPO), "Analyses", "tes_id_2025", "v15_2025.yml"), self.samples[0])
        self.tuples = os.path.join(self.base, "pico", "$ERA", "$GROUP")
        self.files = []  # every variation tuple of the mutau config (the mumu config has none)
        for row in sample_model.load_sample_model(self.samples[0]).mc:
            directory = os.path.join(self.base, "pico", "2025", row['group'])
            os.makedirs(directory, exist_ok=True)
            tags = ["_TES0p950", "_TES0p960", "_TES0p970", "_TES0p980", "_TES0p990", "_TES1p010", "_TES1p020",
                    "_TES1p030", "_TES1p040", "_TES1p050"] if row['group'] == 'DY' else []
            tags += ["_LTF1p030", "_LTF0p970"] if row['group'] in ('DY', 'TT') else []
            tags += ["_JTF1p100", "_JTF0p900"] if row['group'] in ('DY', 'TT', 'WJ') else []
            for tag in tags:
                self.files.append(os.path.join(directory, "%s_mutau%s.root" % (row['name'], tag)))
                open(self.files[-1], "w").close()

    def problems(self, **fields):
        return self.shapes.variation_problems(self.request(**dict(dict(tuples=self.tuples, samples=self.samples),
                                                                   **fields)))

    def test_all_there(self):
        self.assertEqual(len(self.files), 144)
        self.assertEqual(self.problems(), ())

    def test_one_missing_is_a_preflight_problem(self):
        missing = os.path.join(self.base, "pico", "2025", "TT", "TTtoLNu2Q_mutau_LTF1p030.root")
        os.remove(missing)
        self.assertEqual(self.problems(), ("1 of 144 variation tuple file(s) of config %s, era 2025, not found "
                                           "(_LTF1p030: 1): %s" % (TT, missing),))
        request = self.request(tuples=self.tuples, samples=self.samples)
        self.assertIn(self.problems()[0], self.shapes.preflight_shapes(request))

    def test_many_missing_are_counted_by_tag(self):
        for path in self.files:
            if "_TES" in path or "_JTF0p900" in path:
                os.remove(path)
        problem, = self.problems()
        self.assertTrue(problem.startswith("105 of 144 variation tuple file(s)"), problem)
        self.assertIn("(_TES0p950: 9, _TES0p960: 9,", problem)
        self.assertIn("_TES1p050: 9, _JTF0p900: 15)", problem)
        self.assertTrue(problem.endswith(", ..."), problem)
        self.assertEqual(problem.count(".root"), 5)

    def test_branches_of_the_nominal_tuples(self):  # CL §35: removeSFs not needed, $VSJET and split cuts read
        from TauFW.Histogrammer.sample import branches
        for row in sample_model.load_sample_model(self.samples[0]).mc:
            open(os.path.join(self.base, "pico", "2025", row['group'], "%s_mutau.root" % (row['name'])), "w").close()
        read = []
        self.shapes.read_branches = lambda path: read.append(path) or (
            {"genmatch_2", "m_vis", "dm_2", "pt_2"} if "_mutau" in path else None)
        problems = self.shapes.branch_problems(self.request(tuples=self.tuples, samples=self.samples))
        self.assertEqual(len(read), len(sample_model.load_sample_model(self.samples[0]).mc))  # mumu: no files
        self.assertEqual(len(problems), 3)  # DY (+ zptweight_nnlo), TT (+ ttptweight), the others
        self.assertEqual(sum(int(p.split()[0]) for p in problems), len(read))
        text = " ".join(problems)
        self.assertNotIn("idweight_2,", text)  # the config's removeSFs
        for name in ("idDeepTau2018v2p5VSjet_2", "puweight_2025_69p2_v3", "zptweight_nnlo", "ttptweight",
                     "ltfweight_2"):
            self.assertIn(name, text)
        self.assertTrue(problems[0].startswith("9 tuple file(s) of %s, era 2025" % (TT)), problems[0])
        preflight = self.shapes.preflight_shapes(self.request(tuples=self.tuples, samples=self.samples))
        self.assertTrue(set(problems) <= set(preflight))
        read.clear()
        quick = self.shapes.preflight_shapes(self.request(tuples=self.tuples, samples=self.samples), branches=False)
        self.assertEqual(read, [])  # the menu's quick plan: no tuple file is opened
        self.assertFalse(set(problems) & set(quick))
        with open(os.path.join(str(checkout.REPO), "Configs", "Fitter", "tes_id", "config_coarse_PNet.yml")) as stream:
            pnet = __import__("yaml").safe_load(stream)
        self.assertIn("rawPNetVSjet_2", branches.setup_branches(pnet))  # put in at $VSJET
        self.assertNotIn("VSJET", branches.setup_branches(pnet))
        self.assertIn("genmatch_2", branches.setup_branches(pnet))
        self.assertNotIn("genmatch_2", branches.setup_branches(pnet, mc=False))

    def test_not_checked(self):  # as the nominal tuples: a plan's placeholder, no sample files (a pattern is required)
        for path in self.files:
            os.remove(path)
        self.assertEqual(self.problems(tuples="<run_dir>/stages/production/$ERA/$GROUP"), ())
        self.assertEqual(self.problems(samples=()), ())
        self.assertEqual(self.problems(samples=(os.path.join(self.base, "missing.yml"),)), ())  # its own problem
        self.assertEqual(self.problems(eras=[2024]), ())  # no sample file for the era: samples_problems says so
        self.assertEqual(len(self.problems()), 1)


if __name__ == "__main__":
    unittest.main()
