"""Plotter API ControlPlots (CL §24, S4): Plotter/draw.py commands as a user types them, the plots they are expected
to write (the names of TauFW.Plotter.controlplots.plot_name), the plots artifact (no ROOT)."""
import os
import shutil
import tempfile
import unittest
from unittest import mock

import checkout  # noqa: F401  (must precede the TauFW imports)
from TauFW.Plotter.api import ControlPlots, HistFileInput, PlotsRequest
from TauFW.Plotter.controlplots import plot_name
from TauFW.Utilities.Process import ProcessRunner

MUTAU = {"kind": "control_histograms", "era": "2025", "config": "setup_mutau.yml", "channel": "mutau", "tag": "",
         "file": "/run/stages/hists/hists/2025/mutau.root"}  # an artifact of the Histogrammer's ControlHists


class ControlPlotsTests(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="taufw-plotter-")
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.plotter_dir = os.path.join(self.base, "Plotter")
        self.hists = os.path.join(self.base, "hists", "2025")
        os.makedirs(self.hists)
        for channel in ("mutau", "mumu"):
            open(os.path.join(self.hists, "%s.root" % (channel)), "w").close()
        self.calls, self.cwds = [], []
        self.write = True
        self.plotter = ControlPlots(basedir=self.plotter_dir, python="python3",
                                    runner=ProcessRunner(execute=self.execute), find_module=lambda m: True)

    def execute(self, argv, cwd, stream, timeout, env):
        """draw.py writes plots/<era>/<var>_<channel short>-<selection>-<era><tag>.png (two variables here)."""
        self.calls.append(argv)
        self.cwds.append(cwd)
        if self.write:
            channel = os.path.basename(argv[2])[:-5]  # the fixtures' files: <channel>.root, era 2025, no tag
            name = plot_name(channel, "baseline", "2025", os.path.join(cwd, "plots", "2025"))
            os.makedirs(os.path.join(cwd, "plots", "2025"), exist_ok=True)
            for variable in ("m_vis", "pt_1"):
                open(name.replace("$VAR", variable).replace("$TAG", "") + ".png", "w").close()
        return 0

    def item(self, channel, tag="", path=None):
        return HistFileInput(path=path or os.path.join(self.hists, "%s.root" % (channel)), era="2025",
                             channel=channel, config="setup_%s.yml" % (channel), tag=tag)

    def test_commands(self):
        request = PlotsRequest(files=[self.item("mutau", tag="_v1"), self.item("mumu")], fraction=True, pdf=True,
                               text="test")
        plan = self.plotter.plan(request)
        mutau, mumu = (os.path.join(self.hists, "%s.root" % (c)) for c in ("mutau", "mumu"))
        self.assertEqual([c.argv for c in plan.commands], [
            ("python3", "draw.py", mutau, "-F", "-p", "-T", "test"),
            ("python3", "draw.py", mumu, "-F", "-p", "-T", "test")])
        self.assertEqual([c.label for c in plan.commands], ["controlplots mutau 2025", "controlplots mumu 2025"])
        self.assertEqual(plan.commands[0].cwd, self.plotter_dir)
        self.assertEqual([c.expects for c in plan.commands],  # fillhists.py's names: <var>_mt-<sel>-2025<tag>.png
                         [("plots/2025/*_mt-*-2025_v1.png",), ("plots/2025/*_mm-*-2025.png",)])
        self.assertEqual(plan.notes, ())
        minimal = self.plotter.plan(PlotsRequest(files=[self.item("mutau")]))
        self.assertEqual(minimal.commands[0].argv, ("python3", "draw.py", mutau))

    def test_make_counts_plots(self):
        report = self.plotter.make(PlotsRequest(files=[self.item("mutau"), self.item("mumu")]),
                                   os.path.join(self.base, "logs"))
        self.assertTrue(report.ok)
        plots = os.path.join(self.plotter_dir, "plots", "2025")
        self.assertEqual(report.artifacts, (
            {"kind": "plots", "era": "2025", "config": "setup_mutau.yml", "channel": "mutau", "directory": plots,
             "nfiles": 2},
            {"kind": "plots", "era": "2025", "config": "setup_mumu.yml", "channel": "mumu", "directory": plots,
             "nfiles": 2}))

    def test_no_plots_is_a_failure(self):
        self.write = False
        report = self.plotter.make(PlotsRequest(files=[self.item("mutau")]), os.path.join(self.base, "logs"))
        self.assertFalse(report.ok)
        self.assertEqual(report.failed.missing, ("plots/2025/*_mt-*-2025.png",))

    def test_output_directory(self):
        outdir = os.path.join(self.base, "run", "stages", "plots")
        request = PlotsRequest(files=[self.item("mutau"), self.item("mumu")], outdir=outdir)
        plan = self.plotter.plan(request)
        self.assertEqual(plan.commands[0].argv,  # the script and the file as absolute paths: it runs in outdir
                         ("python3", os.path.join(self.plotter_dir, "draw.py"),
                          os.path.join(self.hists, "mutau.root")))
        self.assertEqual({plan.cwd} | {c.cwd for c in plan.commands}, {outdir})
        self.assertEqual(plan.artifacts[0]["directory"], os.path.join(outdir, "plots", "2025"))
        report = self.plotter.make(request, os.path.join(self.base, "logs"))  # makes outdir
        self.assertTrue(report.ok)
        self.assertEqual(self.cwds, [outdir, outdir])
        self.assertEqual([a["nfiles"] for a in report.artifacts], [2, 2])
        self.assertFalse(os.path.exists(os.path.join(self.plotter_dir, "plots")))  # nothing written in Plotter/

    def test_same_plot_names_note(self):
        copy = os.path.join(self.base, "copy.root")
        notes = self.plotter.plan(PlotsRequest(files=[self.item("mutau"), self.item("mutau", path=copy),
                                                      self.item("mutau", tag="_x", path=copy)])).notes
        self.assertEqual(len(notes), 1)  # the third has another tag, so other names
        self.assertIn("files %s, %s give the same plot names" % (os.path.join(self.hists, "mutau.root"), copy),
                      notes[0])

    def test_preflight(self):
        outdir = os.path.join(self.base, "out")
        planned = HistFileInput(path="<run_dir>/stages/hists/hists/2025/mutau.root", era="2025", channel="mutau")
        missing = os.path.join(self.hists, "etau.root")
        with mock.patch.dict(os.environ, {"CMSSW_BASE": "/cmssw"}):
            self.assertEqual(self.plotter.preflight(PlotsRequest(files=[self.item("mutau"), planned],
                                                                 outdir=outdir)), ())
            self.assertEqual(self.plotter.preflight(PlotsRequest(files=[self.item("etau")])),
                             ("control-histogram file %s not found" % (missing),))
            os.makedirs(outdir)
            open(os.path.join(outdir, "leftover.png"), "w").close()  # an interrupted attempt
            problems = self.plotter.preflight(PlotsRequest(files=[self.item("mutau")], outdir=outdir))
        self.assertEqual(problems, ("output directory %s is not empty (an interrupted attempt?): remove it, or start "
                                    "a new run" % (outdir),))
        with mock.patch.dict(os.environ, {}, clear=True):
            plotter = ControlPlots(basedir=self.plotter_dir, find_module=lambda m: False)
            self.assertEqual(plotter.preflight(PlotsRequest(files=[self.item("mutau")])),
                             ("CMSSW_BASE is not set (run cmsenv first)", "python cannot import ROOT"))

    def test_requests(self):
        self.assertEqual(HistFileInput.from_artifact(MUTAU),
                         HistFileInput(path="/run/stages/hists/hists/2025/mutau.root", era="2025", channel="mutau",
                                       config="setup_mutau.yml"))
        with self.assertRaises(ValueError):
            HistFileInput.from_artifact(dict(MUTAU, kind="plots"))
        with self.assertRaises(ValueError):
            HistFileInput(path="", era="2025", channel="mutau")
        request = self.plotter.request(files=[dict(path="a.root", era=2025, channel="mumu")])  # dicts are converted
        self.assertEqual(request.files, (HistFileInput(path="a.root", era="2025", channel="mumu"),))
        with self.assertRaises(ValueError):
            PlotsRequest(files=[])
        for option in ("eras", "variables", "samples"):  # what is filled is the Histogrammer's request
            with self.assertRaises(TypeError):
                self.plotter.request(files=[self.item("mutau")], **{option: ["x"]})

    def test_default_basedir(self):
        with mock.patch.dict(os.environ, {"CMSSW_BASE": "/cmssw"}):
            self.assertEqual(ControlPlots().basedir, os.path.abspath(os.path.join("/cmssw", "src", "TauFW", "Plotter")))
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(ControlPlots().basedir, str(checkout.BASEDIR))


if __name__ == "__main__":
    unittest.main()
