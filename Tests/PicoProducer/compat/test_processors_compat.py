"""Backward-compatibility layer PicoProducer/python/processors/ (renamed to workers/ in Part 5).

Run with any Python 3.9+, no ROOT or CMSSW needed:  python -m unittest discover -s Tests/PicoProducer/compat

The shim files are copied from the checkout into a temporary TauFW tree whose workers/ package is a small fake,
so these tests check the forwarding itself (imports, arguments, exit status, warnings), not the physics.
"""
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import warnings

REPO      = Path(__file__).resolve().parents[3]
SHIMDIR   = REPO / "PicoProducer" / "python" / "processors"
WORKDIR   = REPO / "PicoProducer" / "python" / "workers"
OLD_FILES = ("__init__.py", "Bookkeeper.py", "picojob.py", "skimjob.py") # what processors/ had at the rename
SCRIPTS   = ("picojob.py", "skimjob.py")

# ===== Fake workers package =====

FAKE_WORKERS_INIT = """\
import os
moddir = os.path.dirname(__file__)
def ensuredir(path):
  return path
"""

FAKE_BOOKKEEPER = """\
class Bookkeeper:
  pass
"""

# Records how it was started into $COMPAT_REPORT, then exits with $COMPAT_EXIT.
FAKE_SCRIPT = """\
import json, os, sys
with open(os.environ['COMPAT_REPORT'],'w') as report:
  json.dump({'argv': sys.argv, 'name': __name__, 'file': __file__, 'path0': sys.path[0]}, report)
print("fake worker ran")
sys.exit(int(os.environ.get('COMPAT_EXIT','0')))
"""


def write(path, text=""):
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(text)


class CompatTestCase(unittest.TestCase):
  """Temporary tree <root>/TauFW/PicoProducer/{processors (real shim), workers (fake)}."""

  def setUp(self):
    self.root = Path(tempfile.mkdtemp(prefix="taufw-compat-"))
    self.addCleanup(shutil.rmtree, str(self.root), ignore_errors=True)
    pico = self.root / "TauFW" / "PicoProducer"
    write(self.root / "TauFW" / "__init__.py")
    write(pico / "__init__.py")
    shutil.copytree(str(SHIMDIR), str(pico / "processors"), ignore=shutil.ignore_patterns("__pycache__"))
    self.workers = pico / "workers"
    write(self.workers / "__init__.py", FAKE_WORKERS_INIT)
    write(self.workers / "Bookkeeper.py", FAKE_BOOKKEEPER)
    for script in SCRIPTS:
      write(self.workers / script, FAKE_SCRIPT)
    self.processors = pico / "processors"


class ImportAliasTests(CompatTestCase):

  def setUp(self):
    super().setUp()
    self.saved = {k: v for k, v in sys.modules.items() if k == "TauFW" or k.startswith("TauFW.")}
    for name in self.saved:
      del sys.modules[name]
    sys.path.insert(0, str(self.root))
    self.addCleanup(self.restore)

  def restore(self):
    sys.path.remove(str(self.root))
    for name in [k for k in sys.modules if k == "TauFW" or k.startswith("TauFW.")]:
      del sys.modules[name]
    sys.modules.update(self.saved)

  def test_package_reexports_workers_with_warning(self):
    with warnings.catch_warnings(record=True) as caught:
      warnings.simplefilter("always")
      processors = importlib.import_module("TauFW.PicoProducer.processors")
    workers = importlib.import_module("TauFW.PicoProducer.workers")
    self.assertEqual(processors.moddir, workers.moddir)
    self.assertIs(processors.ensuredir, workers.ensuredir)
    messages = [str(w.message) for w in caught if issubclass(w.category, FutureWarning)]
    self.assertTrue(any("TauFW.PicoProducer.workers" in m for m in messages), messages)

  def test_warning_points_at_the_importer(self):
    with warnings.catch_warnings(record=True) as caught:
      warnings.simplefilter("always")
      importlib.import_module("TauFW.PicoProducer.processors")
    files = [w.filename for w in caught if issubclass(w.category, FutureWarning)]
    self.assertTrue(files)
    self.assertNotIn("processors", files[0])

  def test_bookkeeper_is_the_workers_module(self):
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      from TauFW.PicoProducer.processors.Bookkeeper import Bookkeeper as old
      import TauFW.PicoProducer.processors.Bookkeeper as oldmodule
    from TauFW.PicoProducer.workers.Bookkeeper import Bookkeeper as new
    import TauFW.PicoProducer.workers.Bookkeeper as newmodule
    self.assertIs(old, new)
    self.assertIs(oldmodule, newmodule)

  def test_warnings_can_be_made_errors(self):
    with warnings.catch_warnings():
      warnings.simplefilter("error", FutureWarning)
      with self.assertRaises(FutureWarning):
        importlib.import_module("TauFW.PicoProducer.processors")


class ScriptForwarderTests(CompatTestCase):

  def run_script(self, script, args, exitcode=0):
    report = self.root / "report.json"
    env = dict(os.environ, COMPAT_REPORT=str(report), COMPAT_EXIT=str(exitcode))
    env.pop("PYTHONPATH", None)  # the forwarder must not need TauFW on the path
    result = subprocess.run([sys.executable, str(self.processors / script)] + args, cwd=str(self.root),
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    data = json.loads(report.read_text()) if report.exists() else None
    return result, data

  def test_scripts_forward_arguments_unchanged(self):
    args = ["-i", "a.root", "b.root", "-o", "out dir", "-E", "opt=1", "-v", "2"]
    for script in SCRIPTS:
      with self.subTest(script=script):
        result, data = self.run_script(script, args)
        self.assertEqual(result.returncode, 0, result.stderr)
        target = os.path.realpath(str(self.workers / script))
        self.assertEqual(data["argv"], [target] + args)
        self.assertEqual(data["name"], "__main__")
        self.assertEqual(os.path.realpath(data["file"]), target)
        self.assertEqual(os.path.realpath(data["path0"]), os.path.dirname(target))
        self.assertIn("fake worker ran", result.stdout)
        self.assertIn("python/processors/%s is deprecated" % script, result.stderr)
        self.assertNotIn("deprecated", result.stdout)  # the notice must not mix into the worker's output

  def test_exit_status_is_the_workers(self):
    result, _ = self.run_script("picojob.py", [], exitcode=7)
    self.assertEqual(result.returncode, 7)

  def test_missing_worker_fails_clearly(self):
    (self.workers / "skimjob.py").unlink()
    result, data = self.run_script("skimjob.py", [])
    self.assertNotEqual(result.returncode, 0)
    self.assertIsNone(data)
    self.assertIn("does not exist", result.stderr)


class CheckoutConsistencyTests(unittest.TestCase):
  """The shim in the checkout covers what processors/ had, and only forwards to files that exist."""

  def test_every_old_file_has_a_shim(self):
    for name in OLD_FILES:
      self.assertTrue((SHIMDIR / name).is_file(), name)

  def test_every_shim_has_a_worker(self):
    for path in SHIMDIR.glob("*.py"):
      if path.name.startswith("_"):
        continue
      self.assertTrue((WORKDIR / path.name).is_file(), "%s has no workers/%s" % (path.name, path.name))

  def test_no_worker_code_in_the_shim(self):
    for path in SHIMDIR.glob("*.py"):
      self.assertLess(len(path.read_text().splitlines()), 60, "%s should only forward" % path.name)


if __name__ == "__main__":
  unittest.main()
