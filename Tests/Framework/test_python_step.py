"""Python steps: real step files run by step_runner.py in their own process (standard library only, no ROOT)."""
import json
import os
import shutil
import sys
import tempfile
import textwrap
import unittest

import checkout  # noqa: F401  (must precede TauFW imports)
from TauFW.Framework import Framework, Recipe, RecipeError, RetryError, RunRecord, SilentReporter
from TauFW.Framework.bundle import bundle_hashes
from TauFW.Framework.framework import retryable_stage
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


NEED = '''
import os

def run(ctx):
    if not os.path.isfile(ctx.path("sf/tauid.json")):   # the CDTest case: a file that did not reach the bundle
        with open(os.path.join(ctx.stage_dir, "partial.txt"), "w") as stream:
            stream.write("half done")
        raise IOError("no sf/tauid.json")
    with open(ctx.path("sf/tauid.json")) as stream:
        return {"message": "read %s" % stream.read()}
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
        record = self.start(step("make", options={"n": 5}), step("use", inputs={"numbers": "make"}))
        self.assertEqual(record.state, "DONE", record.stage("use").message)
        make, use = record.stage("make"), record.stage("use")
        self.assertEqual(make.message, "made 5 numbers")
        self.assertEqual(make.artifacts[0]["n"], 5)
        copy = os.path.join(record.run_dir, "bundle")
        value = use.artifacts[0]
        self.assertEqual(value["value"], 2 * (0 + 1 + 2 + 3 + 4) * 10)
        self.assertEqual(os.path.realpath(value["cwd"]), os.path.realpath(copy))  # runs in the run's bundle copy
        self.assertEqual((value["pico"], value["ctx_pico"]), (None, None))  # no pico.config without production
        spec = Recipe.from_dict(record.recipe, bundle_dir=copy).stage("use").spec
        request = PythonStage().request(spec, StageContext(stage_id="use", pico_config="/p.json"))
        self.assertEqual(request.pico_config, "/p.json")  # ctx.pico_config: the run's, given (CL §37 K4)
        self.assertEqual(PythonStage().plan_commands(request).commands[0].env, ())  # no $TAUFW_PICO_CONFIG
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
        with self.assertRaises(RecipeError) as context:  # a missing step file is a recipe error (CL §38)
            self.start(step("missing"))
        self.assertIn("(python).file: steps/missing.py is not a file of the bundle", str(context.exception))

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


class RetryTests(PythonStepTestCase):
    """CL §44: taufw.py retry of a FAILED local stage, and the bundle check of every advance."""

    def continued(self, record):
        """A Framework that continues the run, as taufw.py does (from run.json and the bundle copy)."""
        loaded = RunRecord.load(record.run_dir)
        return Framework.from_record(loaded, reporter=self.reporter), loaded

    def bundle_warnings(self):
        return [text for kind, text in self.reporter.messages if kind == "warning" and "bundle copy" in text]

    def read_json(self, *parts):
        with open(os.path.join(*parts)) as stream:
            return json.load(stream)

    def test_retry_runs_the_failed_step_again_and_keeps_the_finished(self):
        self.write("steps/need.py", NEED)
        record = self.start(step("make", options={"n": 3}), step("need"), step("after", file="steps/make.py",
                                                                              options={"n": 1}))
        self.assertEqual([s.state for s in record.stages], ["DONE", "FAILED", "NEW"])
        self.assertEqual(retryable_stage(record), ("need", "python"))
        made = os.path.join(record.run_dir, "stages", "make", "numbers.txt")
        made_time, make_history = os.path.getmtime(made), list(record.stage("make").history)
        failure = record.stage("need").message
        copy = os.path.join(record.run_dir, "bundle")
        self.write("sf/tauid.json", "{}")  # the source bundle: the run never sees it
        fw, loaded = self.continued(record)
        self.assertEqual(fw.advance(loaded).stage("need").state, "FAILED")  # advance never moves a FAILED stage
        self.assertEqual(self.bundle_warnings(), [])
        os.makedirs(os.path.join(copy, "sf"))
        with open(os.path.join(copy, "sf", "tauid.json"), "w") as stream:  # the fix: in the run's bundle copy
            stream.write("{}")
        fw, loaded = self.continued(record)
        record = fw.retry(loaded)
        self.assertEqual(record.state, "DONE", record.stage("need").message)
        need = record.stage("need")
        self.assertEqual(need.message, "read {}")
        self.assertEqual((record.stage("make").history, os.path.getmtime(made)), (make_history, made_time))
        self.assertEqual([h["event"] for h in need.history], ["failed", "retry", "done"])
        archive = os.path.join("logs", "need", "attempt1")
        tauid = os.path.normpath("sf/tauid.json")
        self.assertEqual(len(need.retries), 1)
        self.assertEqual({key: need.retries[0][key] for key in ("attempt", "message", "archive", "bundle_changed")},
                         {"attempt": 1, "message": failure, "archive": archive, "bundle_changed": {tauid: "added"}})
        # the failed attempt is kept: its logs and what it left in stages/need/; the retry starts empty
        logs = os.path.join(record.run_dir, "logs", "need")
        self.assertEqual(sorted(os.listdir(os.path.join(record.run_dir, archive))),
                         ["01_need.log", "context.json", "stage"])
        with open(os.path.join(record.run_dir, archive, "01_need.log")) as stream:
            self.assertIn("no sf/tauid.json", stream.read())
        self.assertEqual(os.listdir(os.path.join(record.run_dir, archive, "stage")), ["partial.txt"])
        self.assertEqual(sorted(os.listdir(logs)), ["01_need.log", "attempt1", "context.json", "result.json"])
        self.assertEqual(sorted(os.listdir(os.path.join(record.run_dir, "stages", "need"))), ["manifest.json"])
        # the run is not clean: warned once, in run.json, and in the manifests of the stages that ran after it
        self.assertEqual(len(self.bundle_warnings()), 1)
        self.assertIn("sf/tauid.json added".replace("/", os.sep), self.bundle_warnings()[0])
        saved = self.read_json(record.run_dir, "run.json")
        self.assertEqual([entry["files"] for entry in saved["bundle"]["changed"]], [{tauid: "added"}])
        self.assertEqual(saved["stages"][1]["retries"], need.retries)
        self.assertNotIn("retries", saved["stages"][0])  # never retried: written as before
        manifests = {stage: self.read_json(record.run_dir, "stages", stage, "manifest.json")["bundle_changed"]
                     for stage in ("make", "need", "after")}
        self.assertEqual(manifests, {"make": False, "need": True, "after": True})
        with self.assertRaises(RetryError) as context:  # DONE: nothing to retry
            self.continued(record)[0].retry(RunRecord.load(record.run_dir))
        self.assertIn("has no failed stage (it is DONE)", str(context.exception))

    def test_every_retry_is_archived_on_its_own(self):
        self.write("steps/need.py", NEED)
        record = self.start(step("need"))
        for attempt in (1, 2):
            fw, loaded = self.continued(record)
            record = fw.retry(loaded)  # nothing fixed: it fails again
            self.assertEqual(record.stage("need").state, "FAILED")
            self.assertEqual([r["attempt"] for r in record.stage("need").retries], list(range(1, attempt + 1)))
        logs = os.path.join(record.run_dir, "logs", "need")
        self.assertEqual(sorted(os.listdir(logs)), ["01_need.log", "attempt1", "attempt2", "context.json"])
        for attempt in ("attempt1", "attempt2"):  # earlier attempts stay where they are, each with its own output
            self.assertEqual(sorted(os.listdir(os.path.join(logs, attempt))), ["01_need.log", "context.json", "stage"])
        self.assertEqual(os.listdir(os.path.join(record.run_dir, "stages", "need")), ["partial.txt"])  # the last one
        self.assertEqual([r["bundle_changed"] for r in record.stage("need").retries], [{}, {}])  # nothing changed
        self.assertEqual(self.bundle_warnings(), [])
        self.assertNotIn("changed", record.bundle)

    def test_a_bundle_change_is_warned_once_per_change(self):
        self.write("steps/nofunc.py", "def main(ctx):\n    return None\n")
        record = self.start(step("nofunc"))  # not ready (no run()): stays NEW, so the run can be advanced again
        self.assertEqual(record.bundle["sha256"], bundle_hashes(os.path.join(record.run_dir, "bundle")))
        scale = os.path.join(record.run_dir, "bundle", "configs", "scale.txt")
        for edit, expected in ((None, 0), ("20", 1), (None, 1), ("10", 2), ("remove", 3), (None, 3)):
            if edit == "remove":
                os.remove(scale)
            elif edit:
                with open(scale, "w") as stream:
                    stream.write(edit)
            fw, loaded = self.continued(record)
            record = fw.advance(loaded)
            self.assertEqual(len(self.bundle_warnings()), expected, edit)
        name = os.path.normpath("configs/scale.txt")
        self.assertEqual([entry["files"] for entry in record.bundle["changed"]],
                         [{name: "changed"}, {}, {name: "removed"}])  # since the start; back as it was: {}
        self.assertIn("changed and changed back", self.bundle_warnings()[1])

    def test_a_run_without_bundle_hashes_is_not_checked(self):
        self.write("steps/need.py", NEED)
        record = self.start(step("need"))
        with open(record.path) as stream:
            data = json.load(stream)
        del data["bundle"]["sha256"]  # a run started before CL §44
        with open(record.path, "w") as stream:
            json.dump(data, stream)
        os.makedirs(os.path.join(record.run_dir, "bundle", "sf"))
        with open(os.path.join(record.run_dir, "bundle", "sf", "tauid.json"), "w") as stream:
            stream.write("{}")
        fw, loaded = self.continued(record)
        record = fw.retry(loaded)
        self.assertEqual(record.state, "DONE")
        self.assertIsNone(record.stage("need").retries[0]["bundle_changed"])  # not known
        self.assertEqual(self.bundle_warnings(), [])
        self.assertNotIn("changed", record.bundle)


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
