"""Python steps: real step files run by step_runner.py in their own process (standard library only, no ROOT)."""
import json
import os
import shutil
import sys
import tempfile
import textwrap
import unittest

import checkout  # noqa: F401  (must precede TauFW imports)
from TauFW.Framework import Framework, Recipe, RunRecord, SilentReporter
from TauFW.Framework.stages import PythonStage, StageContext
from TauFW.Framework.step_runner import _result
from test_framework import Clock

MAKE = '''
import os

def run(ctx):
    path = os.path.join(ctx.stage_dir, "numbers.txt")
    with open(path, "w") as stream:
        stream.write(" ".join(str(n) for n in range(ctx.options["n"])))
    ctx.log("wrote %s" % path)
    return {"message": "made %d numbers" % ctx.options["n"],
            "artifacts": [{"kind": "numbers", "path": path, "n": ctx.options["n"]}]}
'''

USE = '''
import os
from helper import double   # a file next to the step

def run(ctx):
    numbers = ctx.artifacts("make", kind="numbers")
    with open(numbers[0]["path"]) as stream:
        total = sum(int(n) for n in stream.read().split())
    with open(ctx.path("configs/scale.txt")) as stream:   # a bundle file
        scale = int(stream.read())
    return [{"kind": "sum", "value": double(total) * scale, "cwd": os.getcwd(),
             "pico": os.environ.get("TAUFW_PICO_CONFIG"), "ctx_pico": ctx.pico_config}]
'''


class PythonStepTestCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="taufw-test-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.bundle = os.path.join(self.root, "tes")
        self.reporter = SilentReporter()
        self.write("steps/make.py", MAKE)
        self.write("steps/use.py", USE)
        self.write("steps/helper.py", "def double(x):\n    return 2 * x\n")
        self.write("configs/scale.txt", "10")
        self.write("configs/pico.json", "{}")

    def write(self, relative, text):
        path = os.path.join(self.bundle, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as stream:
            stream.write(textwrap.dedent(text))
        return path

    def start(self, *stages, pico=None):
        self.write("recipe.yml", json.dumps({"name": "steps", "pico": {"config": pico}, "stages": list(stages)}))
        recipe = Recipe.load(self.bundle)
        stages = {s.id: PythonStage() for s in recipe.stages}
        fw = Framework(recipe, stages, reporter=self.reporter, sleep=lambda s: None, clock=Clock())
        return fw.start(run_root=os.path.join(self.root, "runs"))


class PythonStepTests(PythonStepTestCase):
    def test_two_steps_pass_artifacts(self):
        record = self.start({"stage": "python", "id": "make", "file": "steps/make.py", "options": {"n": 5}},
                            {"stage": "python", "file": "steps/use.py"}, pico="configs/pico.json")
        self.assertEqual(record.state, "DONE", record.stage("use").message)
        make, use = record.stage("make"), record.stage("use")
        self.assertEqual(make.message, "made 5 numbers")
        self.assertEqual(make.artifacts[0]["n"], 5)
        copy = os.path.join(record.run_dir, "bundle")
        value = use.artifacts[0]
        self.assertEqual(value["value"], 2 * (0 + 1 + 2 + 3 + 4) * 10)
        self.assertEqual(os.path.realpath(value["cwd"]), os.path.realpath(copy))  # runs in the run's bundle copy
        self.assertEqual(value["pico"], os.path.join(copy, "configs", "pico.json"))
        self.assertEqual(value["ctx_pico"], value["pico"])
        self.assertEqual(use.message, "1 command(s), 1 artifact(s)")  # no message returned
        stage_dir = os.path.join(record.run_dir, "make")
        for name in ("context.json", "result.json", "numbers.txt", "01_make.log"):
            self.assertTrue(os.path.isfile(os.path.join(stage_dir, name)), name)
        with open(os.path.join(stage_dir, "01_make.log")) as stream:
            self.assertIn("[make] wrote", stream.read())
        self.assertEqual(sorted(record.bundle["files"]), sorted(os.path.normpath(p) for p in (  # the whole bundle
            "configs/pico.json", "configs/scale.txt", "recipe.yml", "steps/helper.py", "steps/make.py",
            "steps/use.py")))
        loaded = RunRecord.load(record.run_dir)
        self.assertEqual([s.name for s in loaded.stages], ["make", "use"])  # stage records are named by id
        self.assertNotIn("id", loaded.recipe["stages"][0])  # 'make' is the default id of steps/make.py

    def test_exception_fails_the_step_with_the_log(self):
        self.write("steps/bad.py", "def run(ctx):\n    raise KeyError('no such thing')\n")
        record = self.start({"stage": "python", "file": "steps/bad.py"},
                            {"stage": "python", "file": "steps/make.py", "options": {"n": 1}})
        bad = record.stage("bad")
        self.assertEqual((record.state, bad.state, record.stage("make").state), ("FAILED", "FAILED", "NEW"))
        self.assertIn("exit code 1", bad.message)
        warnings = " ".join(text for kind, text in self.reporter.messages if kind == "warning")
        self.assertIn("KeyError: 'no such thing'", warnings)  # the end of the log is shown

    def test_result_that_is_not_json_fails(self):
        self.write("steps/odd.py", "def run(ctx):\n    return [{'kind': 'x', 'value': object()}]\n")
        record = self.start({"stage": "python", "file": "steps/odd.py"})
        self.assertEqual(record.stage("odd").state, "FAILED")
        with open(os.path.join(record.run_dir, "odd", "01_odd.log")) as stream:
            self.assertIn("cannot be written as JSON", stream.read())

    def test_preflight_keeps_the_step_new(self):
        self.write("steps/nofunc.py", "def main(ctx):\n    return None\n")
        record = self.start({"stage": "python", "file": "steps/nofunc.py"})
        self.assertEqual(record.stage("nofunc").state, "NEW")
        self.assertIn("has no top-level function 'run'", record.stage("nofunc").message)
        self.assertFalse(os.path.exists(os.path.join(record.run_dir, "nofunc", "context.json")))  # nothing ran
        record = self.start({"stage": "python", "file": "steps/nofunc.py", "function": "main"})
        self.assertEqual(record.state, "DONE")
        record = self.start({"stage": "python", "file": "steps/missing.py"})
        self.assertIn("step file", record.stage("missing").message)
        self.assertIn("not found", record.stage("missing").message)

    def test_plan_shows_the_runner_command(self):
        recipe = Recipe.from_dict({"name": "x", "stages": [{"stage": "python", "file": "steps/make.py"}]},
                                  bundle_dir=self.bundle)
        plan = PythonStage().plan(recipe.stages[0].spec, StageContext(bundle_dir=self.bundle, stage_id="make"))
        command = plan.commands[0]
        self.assertEqual(command.argv[0], sys.executable)
        self.assertTrue(command.argv[1].endswith("step_runner.py"))
        self.assertEqual(command.argv[2], os.path.join("<run_dir>", "make", "context.json"))
        self.assertEqual(command.cwd, self.bundle)
        self.assertEqual(plan.notes, ())


class ResultTests(unittest.TestCase):
    def test_forms(self):
        self.assertEqual(_result(None), {"message": "", "artifacts": []})
        self.assertEqual(_result([{"kind": "a"}]), {"message": "", "artifacts": [{"kind": "a"}]})
        self.assertEqual(_result({"message": "ok"}), {"message": "ok", "artifacts": []})
        for bad in ("text", [1], {"artifact": []}, {"artifacts": [{"x": {1, 2}}]}):
            with self.assertRaises(ValueError):
                _result(bad)


if __name__ == "__main__":
    unittest.main()
