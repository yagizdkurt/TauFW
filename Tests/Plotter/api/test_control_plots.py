"""Plotter API: plot.py commands as a user types them; plots are checked (no ROOT)."""
import os
import shutil
import tempfile
import unittest

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
        self.write = True
        self.plotter = ControlPlots(basedir=self.plotter_dir, python="python3",
                                    runner=ProcessRunner(execute=self.execute), find_module=lambda m: True)

    def execute(self, argv, cwd, stream, timeout, env):
        self.calls.append(argv)
        if self.write:  # plot.py writes plots/<era>/<var>_<channel>-<selection>-<era><tag>.png
            era, channel = argv[argv.index("-y") + 1], {"mutau": "mt", "mumu": "mm"}[argv[argv.index("-c") + 1]]
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

    def test_request_checks(self):
        with self.assertRaises(ValueError):
            PlotsRequest(eras=[])
        self.assertEqual(self.plotter.request(eras=[2025]).eras, ("2025",))
        with self.assertRaises(TypeError):
            self.plotter.request(eras=[2025], variable=["x"])


if __name__ == "__main__":
    unittest.main()
