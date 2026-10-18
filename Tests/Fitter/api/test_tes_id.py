"""Fitter API: the commands equal those of run_inputs.sh and run_workflow_zmm.sh; outputs are checked (no ROOT)."""
import glob
import os
import shlex
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

import checkout  # noqa: F401  (must precede TauFW imports)
from TauFW.Fitter.api import TauESID, ShapesRequest, FitRequest, FIT_STEPS, read_fit_values
from TauFW.Utilities.Process import ProcessRunner

TT, MM = "TauES_ID/config/config_coarse_TT.yml", "TauES/config/FitSetup_mumu.yml"
IN = "input_pt_less_region/againstjet_VTight/againstelectron_Tight"
OUT = "output_pt_less_region/againstjet_VTight/againstelectron_Tight"
PLOTS = "plots_pt_less_region/againstjet_VTight/againstelectron_Tight"
MMCARD = OUT + "/2025/ztt_mm_m_vis-baseline_mumu-2025-13TeV.txt"
REGIONS = ["DM0_pt1", "DM0_pt2", "DM0_pt3", "DM1_pt1", "DM1_pt2", "DM1_pt3", "DM10_pt1", "DM10_pt2", "DM10_pt3",
           "DM11_pt1", "DM11_pt2", "DM11_pt3"]

# Fitter/run_inputs.sh, one working point pair
RUN_INPUTS = [
    "python3 ../Histogrammer/shapes/TauES/createinputsTES.py -y 2025 -c %s -j VTight -e Tight" % (TT),
    "python3 ../Histogrammer/shapes/TauES/createinputsTES.py -y 2025 -c %s -j VTight -e Tight" % (MM),
]
# Fitter/run_workflow_zmm.sh, one working point pair, then the summary
RUN_WORKFLOW = [
    "python3 TauES_ID/harvestDatacards_zmm.py -y 2025 -c %s -i %s/ -o %s/2025/" % (MM, IN, OUT),
    "python3 TauES_ID/makecombinedfitTES_SF.py -y 2025 -c %s -i %s/ -o 3 --mumu_datacard_file %s" % (TT, IN, MMCARD),
    "python3 TauES_ID/makecombinedfitTES_SF_postfit.py -y 2025 -c %s --indir %s/ -o 3 --mumu_input_file %s "
    "-cmm %s --jet_wp VTight --ele_wp Tight --impacts" % (TT, OUT, MMCARD, MM),
    "python3 python/plot/runpostfit.py -c %s -j VTight -e Tight -y 2025 --include-cr" % (TT),
    "python3 pre_post_plot_combiner.py --scan_dir %s/2025/ --jet_wp VTight --ele_wp Tight" % (PLOTS),
    "python3 plot_measurements.py --jet_wp VTight --ele_wp Tight --year 2025",
    "python3 createroot_TES.py -c %s -j VTight -e Tight -f root -y 2025" % (TT),
    "python3 createroot_TES.py -c %s -j VTight -e Tight -f json -y 2025" % (TT),
    "python3 make_scan_grid.py --root plots_pt_less_region",
    "python3 make_measurements_grid.py",
    "python3 merge_tau_jsons.py --type both -o tau_sf/TauCorrections_2025.json -y 2025",
    "python3 plot1D_NLL_profiles.py --year 2025",
    "python3 make_tid_2025.py -y 2025",
]

VALUES = """tes_DM0_pt1: 0.987000
tes_DM0_pt1_1sigma_low: 0.981000
tes_DM0_pt1_1sigma_high: 0.993000
tid_SF_DM0_pt1: 0.912000
CMS_eff_m: 0.120000
"""


class FakeExecute:
    """Runs nothing; writes one file for every expected output pattern (and fit values), records the commands."""

    def __init__(self, fail=None, write=True):
        self.calls, self.fail, self.write = [], fail, write

    def __call__(self, argv, cwd, stream, timeout, env):
        self.calls.append((tuple(argv), cwd))
        if self.fail and self.fail in argv:
            return 1
        return 0

    def outputs(self, fitter, command):
        if not self.write:
            return
        for pattern in command.expects:
            path = os.path.join(command.cwd, pattern.replace("*", "x"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as stream:
                stream.write(VALUES if "FitparameterValues" in path else "")


class TauESIDTestCase(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="taufw-fitter-")
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.fitter_dir = os.path.join(self.base, "Fitter")
        for config in (TT, MM):
            os.makedirs(os.path.dirname(os.path.join(self.fitter_dir, config)), exist_ok=True)
            shutil.copy(os.path.join(str(checkout.BASEDIR), config), os.path.join(self.fitter_dir, config))
        self.execute = FakeExecute()
        self.tools = {"combine", "text2workspace.py", "combineCards.py", "PostFitShapesFromWorkspace",
                      "combineTool.py", "plotImpacts.py"}
        self.modules = {"ROOT", "CombineHarvester"}
        self.fitter = self.make()

    def make(self):
        fitter = TauESID(basedir=self.fitter_dir, python="python3", which=lambda t: t in self.tools and "/bin/" + t,
                         find_module=lambda m: m in self.modules)
        execute = self.execute

        def run(argv, cwd, stream, timeout, env):  # write the expected outputs of the command that runs
            code = execute(argv, cwd, stream, timeout, env)
            if code == 0:
                command = next(c for c in self.planned if tuple(c.argv) == tuple(argv))
                execute.outputs(fitter, command)
            return code

        fitter.runner = ProcessRunner(execute=run)
        return fitter

    def lines(self, commands):
        return [command.shell() for command in commands]

    def shapes(self, **fields):
        return ShapesRequest(**dict(dict(eras=[2025], configs=[TT, MM], jet_wps=["VTight"], ele_wps=["Tight"]),
                                    **fields))

    def fit_request(self, **fields):
        return FitRequest(**dict(dict(points=[("2025", "VTight", "Tight")], config=TT, config_mumu=MM), **fields))


class ShapesTests(TauESIDTestCase):
    def test_commands_equal_run_inputs(self):
        plan = self.fitter.plan_shapes(self.shapes())
        self.assertEqual(self.lines(plan.commands), RUN_INPUTS)
        self.assertEqual({c.cwd for c in plan.commands}, {self.fitter_dir})
        self.assertEqual(plan.commands[0].expects, (IN + "/ztt_mt_tes_m_vis.inputs-2025-13TeV_mutau.root",))
        self.assertEqual(plan.commands[1].expects, (IN + "/ztt_mm_tes_m_vis.inputs-2025-13TeV_mumu.root",))
        self.assertEqual([(a["channel"], a["config"]) for a in plan.artifacts], [("mutau", TT), ("mumu", MM)])
        self.assertEqual(plan.notes, ())
        self.assertEqual(self.lines(self.fitter.plan_shapes(self.shapes(serial=True)).commands)[0],
                         RUN_INPUTS[0] + " -s")

    def test_loop_order(self):
        plan = self.fitter.plan_shapes(self.shapes(jet_wps=["Medium", "Tight"], ele_wps=["VVLoose", "Tight"]))
        self.assertEqual([c.label for c in plan.commands][:3],
                         ["shapes 2025 Medium VVLoose mutau", "shapes 2025 Medium VVLoose mumu",
                          "shapes 2025 Medium Tight mutau"])
        self.assertEqual(len(plan.commands), 8)

    def test_make_shapes(self):
        request = self.shapes()
        self.planned = self.fitter.plan_shapes(request).commands
        logdir = os.path.join(self.base, "logs")
        report = self.fitter.make_shapes(request, logdir)
        self.assertTrue(report.ok)
        self.assertEqual(len(report.artifacts), 2)
        self.assertTrue(all(os.path.isfile(a["path"]) for a in report.artifacts))
        self.assertEqual(sorted(os.listdir(logdir)), ["01_shapes_2025_VTight_Tight_mutau.log",
                                                      "02_shapes_2025_VTight_Tight_mumu.log"])

    def test_missing_output_fails_although_exit_code_is_zero(self):
        self.execute.write = False  # like a script whose combine/ROOT step failed inside os.system
        request = self.shapes()
        self.planned = self.fitter.plan_shapes(request).commands
        report = self.fitter.make_shapes(request, os.path.join(self.base, "logs"))
        self.assertFalse(report.ok)
        self.assertEqual(len(report.results), 1)  # stopped at the first command
        self.assertEqual(report.failed.missing, (IN + "/ztt_mt_tes_m_vis.inputs-2025-13TeV_mutau.root",))
        self.assertEqual(report.artifacts, ())

    def test_missing_config_is_a_note_and_a_preflight_problem(self):
        plan = self.fitter.plan_shapes(self.shapes(configs=["nope.yml"]))
        self.assertIn("config nope.yml not found", plan.notes[0])
        self.assertEqual(plan.artifacts, ())
        problems = self.fitter.preflight_shapes(self.shapes(configs=["nope.yml"]))
        self.assertTrue(any("config nope.yml not found" in p for p in problems))

    def test_default_module_lookup(self):  # BUGS F25: find_spec raises for an imported module without __spec__
        imported = types.ModuleType("taufw_test_imported")
        imported.__spec__ = None  # like CMSSW's ROOT once PicoProducer imported it
        with mock.patch.dict(sys.modules, {"taufw_test_imported": imported, "taufw_test_blocked": None}):
            lookup = TauESID(basedir=self.base).find_module
            self.assertTrue(lookup("taufw_test_imported"))
            self.assertFalse(lookup("taufw_test_blocked"))
            self.assertFalse(lookup("taufw_test_missing"))
            self.assertFalse(lookup("taufw_test_missing.sub"))
            self.assertTrue(lookup("json"))

    def test_preflight_environment(self):
        self.modules = set()
        problems = " | ".join(self.fitter.preflight_shapes(self.shapes()))
        self.assertIn("python cannot import ROOT", problems)
        self.assertIn("PicoProducer configuration", problems)  # no PicoProducer next to the temporary Fitter


    def test_pico_config_reaches_every_command(self):
        request = self.shapes(pico_config="/run/bundle/pico.json")
        self.assertTrue(all(c.env == (("TAUFW_PICO_CONFIG", "/run/bundle/pico.json"),)
                            for c in self.fitter.plan_shapes(request).commands))
        self.assertIn("no PicoProducer configuration /run/bundle/pico.json",
                      " ".join(self.fitter.preflight_shapes(request)))
        fit = self.fitter.fit_request(points=[("2025", "VTight", "Tight")], config=TT, config_mumu=MM,
                                      pico_config="/run/bundle/pico.json")
        self.assertTrue(all(c.env for c in self.fitter.plan_fit(fit).commands))
        self.assertEqual(self.fitter.plan_shapes(self.shapes()).commands[0].env, ())
        self.assertEqual(self.fitter.config_file(TT), os.path.join(self.fitter_dir, os.path.normpath(TT)))


    def test_tuple_pattern(self):
        pattern = "/eos/cms/store/group/phys_tau/TauFW/pico2024/TES_variations/$ERA/$GROUP"
        request = self.shapes(tuples=pattern, pico_config="/run/bundle/pico.json")
        commands = self.fitter.plan_shapes(request).commands
        self.assertEqual(self.lines(commands), [line + " --tuples '%s'" % (pattern) for line in RUN_INPUTS])
        self.assertTrue(all(c.env == () for c in commands))  # the PicoProducer configuration is not used
        self.assertNotIn("PicoProducer configuration", " ".join(self.fitter.preflight_shapes(request)))
        self.assertIn("has $DAS, which the scripts do not fill",
                      " ".join(self.fitter.preflight_shapes(self.shapes(tuples="/eos/x/$DAS"))))
        outdir = os.path.join(self.base, "out")
        self.assertIn("tuple pattern 'pico/$ERA' is relative",
                      " ".join(self.fitter.preflight_shapes(self.shapes(tuples="pico/$ERA", outdir=outdir))))
        fit = self.fit_request(pico_config="/run/bundle/pico.json")  # the fit reads no tuples: unchanged
        self.assertTrue(all(c.env for c in self.fitter.plan_fit(fit).commands))

    def test_shapes_in_output_directory(self):
        outdir = os.path.join(self.base, "run", "stages", "shapes")
        request = self.shapes(outdir=outdir, pico_config="pico.json")
        plan = self.fitter.plan_shapes(request)
        script = os.path.normpath(os.path.join(self.fitter_dir, "..", "Histogrammer", "shapes", "TauES",
                                               "createinputsTES.py"))  # moved in CL §25 (H1)
        self.assertEqual(plan.commands[0].argv[:6], ("python3", script,
                                                     "-y", "2025", "-c", os.path.join(self.fitter_dir, os.path.normpath(TT))))
        self.assertEqual({plan.cwd} | {c.cwd for c in plan.commands}, {outdir})
        self.assertEqual(plan.commands[0].expects, (IN + "/ztt_mt_tes_m_vis.inputs-2025-13TeV_mutau.root",))
        self.assertEqual(plan.commands[0].env, (("TAUFW_PICO_CONFIG", os.path.abspath("pico.json")),))
        self.planned = plan.commands
        report = self.fitter.make_shapes(request, os.path.join(self.base, "logs"))  # makes outdir
        self.assertTrue(report.ok, report.failed)
        self.assertEqual(report.artifacts[0]["path"],
                         os.path.join(outdir, os.path.normpath(IN), "ztt_mt_tes_m_vis.inputs-2025-13TeV_mutau.root"))
        self.assertTrue(all(os.path.isfile(a["path"]) for a in report.artifacts))
        self.assertFalse(os.path.exists(os.path.join(self.fitter_dir, "input_pt_less_region")))
        self.assertIn("output directory %s is not empty" % (outdir), " ".join(self.fitter.preflight_shapes(request)))
        placeholder = os.path.join("<run_dir>", "stages", "shapes")  # a plan before the run exists: kept as given
        self.assertEqual(self.fitter.plan_shapes(self.shapes(outdir=placeholder)).cwd, placeholder)


class ShapesSampleFilesTests(TauESIDTestCase):  # CL §22: sample model files, --samples
    def test_samples_option(self):
        samples = (os.path.join(self.base, "v15_2025.yml"),)
        commands = self.fitter.plan_shapes(self.shapes(samples=samples)).commands
        self.assertEqual(self.lines(commands), [line + " --samples " + shlex.quote(samples[0]) for line in RUN_INPUTS])
        self.assertNotIn("--samples", self.fitter.plan_shapes(self.shapes()).commands[0].argv)
        self.assertIn("sample file %s not found" % (samples[0]),
                      self.fitter.preflight_shapes(self.shapes(samples=samples)))
        open(samples[0], "w").close()
        self.assertNotIn("sample file %s not found" % (samples[0]),
                         self.fitter.preflight_shapes(self.shapes(samples=samples)))


class FitTests(TauESIDTestCase):
    def test_commands_equal_run_workflow(self):
        plan = self.fitter.plan_fit(self.fit_request())
        self.assertEqual(self.lines(plan.commands), RUN_WORKFLOW)
        self.assertEqual(plan.notes, ())
        multidimfit = plan.commands[1].expects
        self.assertEqual(len(multidimfit), 2 * len(REGIONS))
        self.assertIn(OUT + "/2025/higgsCombine.mt_m_vis-DM0_pt1_mutau_DeepTau-2025-13TeV.MultiDimFit.mH90.root",
                      multidimfit)
        self.assertIn(OUT + "/2025/FitparameterValues__mutau_DeepTau_2025-13TeV_DM11_pt3.txt", multidimfit)
        self.assertEqual(plan.commands[0].expects, (MMCARD,))
        self.assertEqual([a["kind"] for a in plan.artifacts], ["fit", "corrections", "corrections"])
        self.assertEqual([a.get("combined") for a in plan.artifacts[1:]], [None, True])  # merged JSON, make_tid
        self.assertEqual(plan.commands[-1].expects, ("data/tau/TauCorrections_2025_with_uncorrelated_systs.json",))

    def test_steps_and_impacts(self):
        plan = self.fitter.plan_fit(self.fit_request(steps=["corrections", "fit"], impacts=False))
        self.assertEqual(self.lines(plan.commands), RUN_WORKFLOW[0:2] + RUN_WORKFLOW[6:8])
        plan = self.fitter.plan_fit(self.fit_request(steps=["postfit"], impacts=False))
        self.assertEqual(self.lines(plan.commands), [RUN_WORKFLOW[2].replace(" --impacts", "")])
        with self.assertRaises(ValueError):
            self.fit_request(steps=["scan"])
        with self.assertRaises(ValueError):
            self.fit_request(points=[])

    def test_summary_once_per_era(self):
        request = self.fit_request(points=[("2025", "VTight", "Tight"), ("2025", "Medium", "Tight")])
        labels = [c.label for c in self.fitter.plan_fit(request).commands]
        self.assertEqual(len([l for l in labels if l.startswith("summary merge json")]), 1)
        self.assertEqual(len(labels), 2 * 8 + 5)

    def test_fit_reads_values_and_corrections(self):
        request = self.fit_request(steps=["fit", "corrections"])
        self.planned = self.fitter.plan_fit(request).commands
        report = self.fitter.fit(request, os.path.join(self.base, "logs"))
        self.assertTrue(report.ok, report.failed)
        fit = report.artifacts[0]
        self.assertEqual(fit["values"][:2], [
            {"region": "DM0_pt1", "poi": "tes", "value": 0.987, "low": 0.981, "high": 0.993},
            {"region": "DM0_pt1", "poi": "tid_SF", "value": 0.912, "low": None, "high": None}])
        self.assertEqual([os.path.basename(p) for p in fit["corrections"]],  # DeepTau files only (BUGS F22)
                         ["x_SF_dm_DeepTaux_2025_VSjetVTight_VSeleTight.json",
                          "x_SF_dm_DeepTaux_2025_VSjetVTight_VSeleTight.root"])

    def test_failed_command_stops_the_fit(self):
        self.execute.fail = "TauES_ID/makecombinedfitTES_SF.py"
        request = self.fit_request()
        self.planned = self.fitter.plan_fit(request).commands
        report = self.fitter.fit(request, os.path.join(self.base, "logs"))
        self.assertFalse(report.ok)
        self.assertEqual([r.label for r in report.results],
                         ["fit datacards mumu 2025 VTight Tight", "fit multidimfit 2025 VTight Tight"])
        self.assertEqual(report.failed.returncode, 1)
        self.assertEqual(report.artifacts, ())

    def test_preflight(self):
        self.assertEqual(self.fitter.preflight_fit(self.fit_request(steps=["corrections"])),
                         () if "CMSSW_BASE" in os.environ else ("CMSSW_BASE is not set (run cmsenv first)",))
        self.tools = {"combine"}
        self.modules = {"ROOT"}
        problems = " | ".join(self.fitter.preflight_fit(self.fit_request()))
        self.assertIn("not on PATH: text2workspace.py, combineCards.py, PostFitShapesFromWorkspace, combineTool.py, "
                      "plotImpacts.py", problems)
        self.assertIn("cannot import CombineHarvester", problems)
        self.assertIn("no shapes for 2025 VTight/Tight", problems)
        self.assertNotIn("no shapes", " | ".join(self.fitter.preflight_fit(self.fit_request(), check_shapes=False)))
        os.makedirs(os.path.join(self.fitter_dir, IN))
        open(os.path.join(self.fitter_dir, IN, "ztt_mt_tes_m_vis.inputs-2025-13TeV_mutau.root"), "w").close()
        self.assertNotIn("no shapes", " | ".join(self.fitter.preflight_fit(self.fit_request())))


    def test_fit_in_output_directory(self):
        outdir = os.path.join(self.base, "run", "stages", "fit")
        shapes = os.path.join(self.base, "run", "stages", "shapes", "shapes_VTight_Tight")
        request = self.fit_request(outdir=outdir, shapes_dirs=[("2025", "VTight", "Tight", shapes)])
        plan = self.fitter.plan_fit(request)
        era = os.path.join(outdir, "2025")
        self.assertEqual(plan.cwd, outdir)
        self.assertEqual({c.cwd for c in plan.commands}, {era})  # one era: its own directory
        argv = {c.label.split(" 2025")[0]: c.argv for c in plan.commands}
        self.assertEqual(argv["fit datacards mumu"][1:],
                         (os.path.join(self.fitter_dir, "TauES_ID", "harvestDatacards_zmm.py"), "-y", "2025",
                          "-c", os.path.join(self.fitter_dir, os.path.normpath(MM)), "-i", shapes + "/",
                          "-o", OUT + "/2025/"))
        self.assertEqual(argv["fit multidimfit"][-8:],  # the shapes are elsewhere: the outputs are given
                         ("-o", "3", "--mumu_datacard_file", MMCARD, "--output_dir", OUT + "/2025",
                          "--plot_dir", PLOTS + "/2025"))
        self.assertEqual(argv["postfit fitdiagnostics"][6:8], ("--indir", OUT + "/"))  # relative: str.replace
        self.assertEqual(argv["summary measurements grid"][2:], ("--dir", "Measurements"))
        self.assertEqual(argv["summary tes and id"][2:],
                         ("-y", "2025", "--sf-dir", "tau_sf", "--out",
                          "data/tau/TauCorrections_2025_with_uncorrelated_systs.json"))
        self.assertTrue(all(os.path.isabs(a[1]) for a in argv.values()))  # every script by its absolute path
        self.assertEqual(plan.artifacts[0]["output_dir"], os.path.join(era, os.path.normpath(OUT), "2025"))
        self.assertEqual(plan.artifacts[1]["path"], os.path.join(era, "tau_sf", "TauCorrections_2025.json"))
        request = self.fit_request(outdir=outdir, shapes_dirs=[("2025", "VTight", "Tight", shapes)],
                                   steps=["fit", "corrections"])
        self.planned = self.fitter.plan_fit(request).commands
        report = self.fitter.fit(request, os.path.join(self.base, "logs"))  # makes <outdir>/2025
        self.assertTrue(report.ok, report.failed)
        self.assertEqual(len(report.artifacts[0]["values"]), 2)
        self.assertTrue(all(p.startswith(os.path.join(era, "tau_sf")) for p in report.artifacts[0]["corrections"]))
        self.assertFalse(os.path.exists(os.path.join(self.fitter_dir, "output_pt_less_region")))

    def test_fit_output_directory_per_era_and_shapes_outside_the_run(self):
        outdir = os.path.join(self.base, "fit")
        request = self.fit_request(points=[("2025", "VTight", "Tight"), ("2024", "VTight", "Tight")], outdir=outdir)
        plan = self.fitter.plan_fit(request)
        self.assertEqual(list(dict.fromkeys(c.cwd for c in plan.commands)),
                         [os.path.join(outdir, "2025"), os.path.join(outdir, "2024")])
        mumu = next(c for c in plan.commands if c.label.startswith("fit datacards mumu"))
        self.assertEqual(mumu.argv[mumu.argv.index("-i") + 1],  # no shapes_dirs: Fitter/'s shapes (null input)
                         os.path.join(self.fitter_dir, os.path.normpath(IN)) + "/")
        os.makedirs(outdir)
        open(os.path.join(outdir, "stale.root"), "w").close()
        self.assertIn("output directory %s is not empty" % (outdir),
                      " | ".join(self.fitter.preflight_fit(request, check_shapes=False)))
        with self.assertRaises(ValueError):
            self.fit_request(shapes_dirs=[("2025", "VTight", "Tight")])

    def test_shapes_dirs_with_outdir_name_every_point_or_none(self):
        """R4 (S11): with an output directory a point is never read from Fitter/ while the others come from
        elsewhere; an empty list (the Framework's null shapes input) still reads Fitter/."""
        points = [("2025", "VTight", "Tight"), ("2025", "Tight", "Tight")]
        outdir = os.path.join(self.base, "fit")
        with self.assertRaises(ValueError) as context:
            self.fit_request(points=points, outdir=outdir, shapes_dirs=[("2025", "VTight", "Tight", "/s/vt")])
        self.assertEqual(str(context.exception), "FitRequest: shapes_dirs names no directory for 2025 Tight/Tight "
                                                 "(with outdir it names every point, or none)")
        self.assertEqual(self.fit_request(points=points, outdir=outdir).shapes_dirs, ())
        complete = [("2025", "VTight", "Tight", "/s/vt"), ("2025", "Tight", "Tight", "/s/t")]
        self.assertEqual(len(self.fit_request(points=points, outdir=outdir, shapes_dirs=complete).shapes_dirs), 2)
        self.fit_request(points=points, shapes_dirs=complete[:1])  # no outdir (standalone): unchanged


class ResultsTests(unittest.TestCase):
    def test_read_fit_values(self):
        self.assertEqual(read_fit_values(VALUES, "DM0_pt1"), [
            {"region": "DM0_pt1", "poi": "tes", "value": 0.987, "low": 0.981, "high": 0.993},
            {"region": "DM0_pt1", "poi": "tid_SF", "value": 0.912, "low": None, "high": None}])
        self.assertEqual(read_fit_values("garbage\nx: y\n", "DM0_pt1"), [])

    def test_fit_steps(self):
        self.assertEqual(FIT_STEPS, ("fit", "postfit", "plots", "corrections", "summary"))


if __name__ == "__main__":
    unittest.main()
