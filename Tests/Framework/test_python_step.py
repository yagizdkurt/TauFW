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
from TauFW.Framework.stages import PythonStage, StageContext, PreflightError
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
    numbers = ctx.input("numbers", kind="numbers")   # inputs: {numbers: make}
    assert numbers == ctx.artifacts("make", kind="numbers")
    with open(numbers[0]["path"]) as stream:
        total = sum(int(n) for n in stream.read().split())
    with open(ctx.path("configs/scale.txt")) as stream:   # a bundle file
        scale = int(stream.read())
    return [{"kind": "sum", "value": double(total) * scale, "cwd": os.getcwd(),
             "pico": os.environ.get("TAUFW_PICO_CONFIG"), "ctx_pico": ctx.pico_config}]
'''


READ = '''
def run(ctx):
    numbers = ctx.input("numbers", kind="numbers")   # inputs: {numbers: {path: <another run>/stages/make}}
    with open(numbers[0]["path"]) as stream:
        total = sum(int(n) for n in stream.read().split())
    return [{"kind": "sum", "value": total, "input": ctx.inputs["numbers"], "keys": list(ctx.upstream)}]
'''


def step(name, **options):
    """A python step of steps/<name>.py with the id <name> and no inputs (unless given)."""
    return dict({"stage": "python", "id": name, "inputs": None, "file": "steps/%s.py" % (name)}, **options)


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
        record = self.start(step("make", options={"n": 5}), step("use", inputs={"numbers": "make"}),
                            pico="configs/pico.json")
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
        stage_dir = os.path.join(record.run_dir, "stages", "make")  # the step's own files and the manifest only
        log_dir = os.path.join(record.run_dir, "logs", "make")      # the Framework's files
        self.assertEqual(sorted(os.listdir(stage_dir)), ["manifest.json", "numbers.txt"])
        self.assertEqual(sorted(os.listdir(log_dir)), ["01_make.log", "context.json", "result.json"])
        with open(os.path.join(log_dir, "01_make.log")) as stream:
            self.assertIn("[make] wrote", stream.read())
        with open(os.path.join(stage_dir, "manifest.json")) as stream:
            manifest = json.load(stream)
        self.assertEqual((manifest["stage_id"], manifest["stage"], manifest["inputs"], manifest["artifacts"]),
                         ("make", "python", None, make.artifacts))
        self.assertEqual(sorted(record.bundle["files"]), sorted(os.path.normpath(p) for p in (  # the whole bundle
            "configs/pico.json", "configs/scale.txt", "recipe.yml", "steps/helper.py", "steps/make.py",
            "steps/use.py")))
        loaded = RunRecord.load(record.run_dir)
        self.assertEqual([s.name for s in loaded.stages], ["make", "use"])  # stage records are named by id
        self.assertEqual(loaded.recipe["stages"][1]["inputs"], {"numbers": "make"})
        with open(os.path.join(record.run_dir, "logs", "use", "context.json")) as stream:
            context = json.load(stream)
        self.assertEqual((context["inputs"], list(context["upstream"])), ({"numbers": "make"}, ["make"]))

    def test_a_step_reads_another_runs_stage(self):
        """R4: ctx.input() of an input that names another run's stage directory."""
        source = os.path.join(self.start(step("make", options={"n": 4})).run_dir, "stages", "make")
        self.write("steps/read.py", READ)
        record = self.start(step("read", inputs={"numbers": {"path": source}}))
        self.assertEqual(record.state, "DONE", record.stage("read").message)
        self.assertEqual(record.stage("read").artifacts[0], {"kind": "sum", "value": 0 + 1 + 2 + 3,
                                                             "input": source, "keys": [source]})
        self.assertEqual(record.stage("read").sources["numbers"]["stage"], "python")

    def test_a_step_without_inputs_sees_no_artifacts(self):
        self.write("steps/look.py", "def run(ctx):\n    return {'message': '%d' % len(ctx.artifacts())}\n")
        record = self.start(step("make", options={"n": 2}), step("look"))
        self.assertEqual(record.stage("look").message, "0")  # make ran before, but look does not name it
        self.write("steps/ask.py", "def run(ctx):\n    ctx.input('numbers')\n")
        record = self.start(step("ask"))
        self.assertEqual(record.stage("ask").state, "FAILED")
        self.assertFalse(os.path.exists(os.path.join(record.run_dir, "stages", "ask", "manifest.json")))  # FAILED
        with open(os.path.join(record.run_dir, "logs", "ask", "01_ask.log")) as stream:
            self.assertIn("step 'ask' has no input 'numbers' (inputs: none)", stream.read())

    def test_exception_fails_the_step_with_the_log(self):
        self.write("steps/bad.py", "def run(ctx):\n    raise KeyError('no such thing')\n")
        record = self.start(step("bad"), step("make", options={"n": 1}))
        bad = record.stage("bad")
        self.assertEqual((record.state, bad.state, record.stage("make").state), ("FAILED", "FAILED", "NEW"))
        self.assertIn("exit code 1", bad.message)
        warnings = " ".join(text for kind, text in self.reporter.messages if kind == "warning")
        self.assertIn("KeyError: 'no such thing'", warnings)  # the end of the log is shown

    def test_result_that_is_not_json_fails(self):
        self.write("steps/odd.py", "def run(ctx):\n    return [{'kind': 'x', 'value': object()}]\n")
        record = self.start(step("odd"))
        self.assertEqual(record.stage("odd").state, "FAILED")
        with open(os.path.join(record.run_dir, "logs", "odd", "01_odd.log")) as stream:
            self.assertIn("cannot be written as JSON", stream.read())

    def test_preflight_keeps_the_step_new(self):
        self.write("steps/nofunc.py", "def main(ctx):\n    return None\n")
        record = self.start(step("nofunc"))
        self.assertEqual(record.stage("nofunc").state, "NEW")
        self.assertIn("has no top-level function 'run'", record.stage("nofunc").message)
        self.assertFalse(os.path.exists(os.path.join(record.run_dir, "nofunc", "context.json")))  # nothing ran
        record = self.start(step("nofunc", function="main"))
        self.assertEqual(record.state, "DONE")
        record = self.start(step("missing"))
        self.assertIn("step file", record.stage("missing").message)
        self.assertIn("not found", record.stage("missing").message)

    def test_plan_shows_the_runner_command(self):
        recipe = Recipe.from_dict({"name": "x", "stages": [step("make")]}, bundle_dir=self.bundle)
        plan = PythonStage().plan(recipe.stages[0].spec, StageContext(bundle_dir=self.bundle, stage_id="make"))
        command = plan.commands[0]
        self.assertEqual(command.argv[0], sys.executable)
        self.assertTrue(command.argv[1].endswith("step_runner.py"))
        self.assertEqual(command.argv[2], os.path.join("<run_dir>", "logs", "make", "context.json"))
        self.assertEqual(command.cwd, self.bundle)
        self.assertEqual(plan.notes, ())
        with self.assertRaises(PreflightError):  # the id is the step's directory: it is required
            PythonStage().plan(recipe.stages[0].spec, StageContext(bundle_dir=self.bundle))


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
