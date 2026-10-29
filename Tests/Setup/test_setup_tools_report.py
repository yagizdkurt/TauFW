"""CL §54: `setup_tools.py report`, the Python part of `source taufw.sh --check`, run by its path as taufw.sh runs it
(before cmsenv works too): one ROLE<TAB>TEXT line each for the components, the Python packages and the user config."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / "Framework/python/_internal/installer/setup_tools.py"


class ReportTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="taufw-report-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.manifest = self.root / "setup_manifest.json"
        self.user_config = self.root / "UserConfig.yaml"

    def tools(self, *arguments):
        result = subprocess.run([sys.executable, "-B", str(TOOLS)] + list(arguments), capture_output=True, text=True,
                                encoding="utf-8", env=dict(os.environ, TAUFW_USER_CONFIG=str(self.user_config),
                                                           PYTHONIOENCODING="utf-8"))
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def report(self):
        lines = [line.split("\t", 1) for line in self.tools("report", "--manifest", str(self.manifest)).splitlines()]
        for role, _ in lines:
            self.assertIn(role, ("success", "warning", "failure"))
        return lines

    def test_an_older_installation_without_a_user_config(self):
        lines = self.report()
        self.assertEqual(lines[0][0], "warning")
        self.assertIn("Components: not recorded", lines[0][1])
        self.assertIn(["warning", "No user config %s: create it with `taufw userconfig`" % (self.user_config)], lines)

    def test_a_recorded_installation_with_a_reviewed_user_config(self):
        self.tools("manifest", "--path", str(self.manifest), "tauidsfs", "combine")
        self.user_config.write_text("taufw_user:\n  version: 1\n  reviewed: true\n", encoding="utf-8")
        lines = self.report()
        self.assertEqual(lines[0], ["success", "Components: TauIDSFs, Combine + CombineHarvester"])
        self.assertIn(["success", "User config: %s" % (self.user_config)], lines)
        self.assertFalse([line for line in lines if line[0] == "failure"])

    def test_no_optional_component(self):
        self.tools("manifest", "--path", str(self.manifest))
        self.assertEqual(self.report()[0], ["success", "Components: none of the optional ones"])


if __name__ == "__main__":
    unittest.main()
