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
from TauFW.Framework._internal.recipes.bundle import bundle_hashes
from TauFW.Framework._internal.runtime.framework import (retryable_stage, next_stage, live_state, run_state,
                                                         StopPointError)
from TauFW.Framework._internal.runtime.run_lock import read_lock
from TauFW.Framework.stages import PythonStage, StageContext, PreflightError
from TauFW.Framework._internal.runtime.step_runner import _result
from test_framework import Clock


def load_cli(test):
    """taufw.py as a module (as CommandLineTests loads it), with a reviewed user config and silent output."""
    import importlib.util
    checkout.reviewed_user_config(test)
    spec = importlib.util.spec_from_file_location("taufw_cli", str(checkout.TAUFW_SCRIPT))
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    cli.FrameworkReporter = lambda verbosity=0: SilentReporter()
    return cli

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
            "configs/pico.json", "configs/scale.txt", "steps/helper.py", "steps/make.py",
            "steps/use.py")))  # not recipe.yml: the run's own recipe, outside the hashes (CL §55)
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


class StopPointTests(PythonStepTestCase):
    """Plan 24 step 1: until= (--until, --next) stops a run after a stage; it is then PAUSED."""

    def framework(self, *stages):
        self.write("recipe.yml", json.dumps({"name": "steps", "pico": {"config": None}, "stages": list(stages)}))
        recipe = Recipe.load(self.bundle)
        return Framework(recipe, {s.id: PythonStage() for s in recipe.stages}, reporter=self.reporter,
                         sleep=lambda s: None, clock=Clock())

    def three(self):
        return self.framework(step("make", options={"n": 3}), step("use", inputs={"numbers": "make"}),
                              step("last", file="steps/make.py", options={"n": 1}))

    def test_a_run_stops_after_the_stage_and_goes_on_later(self):
        record = self.three().start(run_root=os.path.join(self.root, "runs"), until="make")
        self.assertEqual([s.state for s in record.stages], ["DONE", "NEW", "NEW"])
        self.assertEqual((record.state, next_stage(record)), ("PAUSED", "use"))
        self.assertIn(("message", "Stopped after stage make (--until)"), self.reporter.messages)
        history = list(record.stage("make").history)
        fw = Framework.from_record(RunRecord.load(record.run_dir), reporter=self.reporter)
        record = fw.advance(RunRecord.load(record.run_dir), until="make")  # DONE already: stops at once
        self.assertEqual(([s.state for s in record.stages], record.stage("make").history), (["DONE", "NEW", "NEW"],
                                                                                           history))
        record = fw.advance(record, until="use")
        self.assertEqual([s.state for s in record.stages], ["DONE", "DONE", "NEW"])
        record = fw.advance(record)  # no stop point: to the end
        self.assertEqual((record.state, next_stage(record)), ("DONE", None))

    def test_an_unknown_stop_point_changes_nothing(self):
        fw, runs = self.three(), os.path.join(self.root, "runs")
        with self.assertRaises(StopPointError) as context:
            fw.start(run_root=runs, until="fit")
        self.assertIn("has no stage 'fit' to stop after (stages: make, use, last)", str(context.exception))
        self.assertFalse(os.path.exists(runs))
        record = fw.start(run_root=runs, until="make")
        with self.assertRaises(StopPointError):
            Framework.from_record(record, reporter=self.reporter).advance(record, until="fit")
        self.assertEqual([s.state for s in RunRecord.load(record.run_dir).stages], ["DONE", "NEW", "NEW"])
        self.assertIsNone(read_lock(record.run_dir))

    def test_next_on_the_command_line(self):
        cli = load_cli(self)
        record = self.three().start(run_root=os.path.join(self.root, "runs"), until="make")
        self.assertEqual(cli.main(["advance", record.run_dir, "--next"]), 0)
        self.assertEqual([s.state for s in RunRecord.load(record.run_dir).stages], ["DONE", "DONE", "NEW"])
        self.assertEqual(cli.main(["advance", record.run_dir, "--until", "nope"]), 1)
        self.assertEqual(cli.main(["advance", record.run_dir]), 0)
        self.assertEqual(RunRecord.load(record.run_dir).state, "DONE")
        self.assertEqual(cli.main(["advance", record.run_dir, "--next"]), 0)  # nothing left: says so

    def test_live_state(self):
        live, lost = dict(lost=False), dict(lost=True)
        for state, lock, shown in (("PAUSED", None, "PAUSED"), ("PAUSED", live, "RUNNING"), ("PAUSED", lost, "PAUSED"),
                                   ("NEW", live, "RUNNING"), ("WAITING", live, "WAITING"), ("DONE", live, "DONE"),
                                   ("FAILED", None, "FAILED")):
            self.assertEqual(live_state(state, lock), shown, (state, lock))
        record = self.three().start(run_root=os.path.join(self.root, "runs"), until="make")
        self.assertEqual(run_state(record), "PAUSED")  # no advance holds the lock now


class RunRecipeTests(PythonStepTestCase):
    """Plan 24 step 2 (CL §55): <run_dir>/bundle/recipe.yml is the run's own recipe; every advance takes its edits."""
    framework, three = StopPointTests.framework, StopPointTests.three

    def started(self, until="make"):
        return self.three().start(run_root=os.path.join(self.root, "runs"), until=until)

    def edit(self, record, change):
        """Change the run's recipe file (JSON, as the tests write it) with change(data)."""
        path = os.path.join(record.run_dir, "bundle", "recipe.yml")
        with open(path) as stream:
            data = json.load(stream)
        change(data)
        with open(path, "w") as stream:
            json.dump(data, stream)
        return path

    def advance(self, record, **options):
        loaded = RunRecord.load(record.run_dir)
        return Framework.from_record(loaded, reporter=self.reporter).advance(loaded, **options)

    def warnings(self, text):
        return [message for kind, message in self.reporter.messages if kind == "warning" and text in message]

    def test_the_run_starts_with_a_copy_of_the_recipe_file(self):
        self.write("recipe.yml", "# my comment\n" + json.dumps({"name": "steps", "stages": [step("make", options={
            "n": 2})]}))
        record = Framework(Recipe.load(self.bundle), {"make": PythonStage()}, reporter=self.reporter,
                           clock=Clock()).start(run_root=os.path.join(self.root, "runs"))
        for path in (("bundle", "recipe.yml"), ("recipes", "recipe_0.yml")):
            with open(os.path.join(record.run_dir, *path)) as stream:
                self.assertTrue(stream.read().startswith("# my comment\n"), path)  # the text, comments kept
        saved = self.read_run(record)
        self.assertNotIn("recipe.yml", saved["bundle"]["files"])
        self.assertNotIn("recipe.yml", saved["bundle"]["sha256"])
        self.assertEqual([key for key in ("recipe_changed", "removed") if key in saved], [])  # never changed
        recipe = Recipe.from_dict({"name": "code", "stages": [step("make", options={"n": 1})]}, bundle_dir=self.bundle)
        record = Framework(recipe, {"make": PythonStage()}, reporter=self.reporter,
                           clock=Clock()).start(run_root=os.path.join(self.root, "runs"))
        self.assertEqual(self.advance(record).recipe_changed, [])  # a Recipe made in code: its dict, read back the same

    def read_run(self, record):
        with open(record.path) as stream:
            return json.load(stream)

    def test_a_new_stage_runs_with_its_new_options(self):
        record = self.started()
        self.edit(record, lambda data: data["stages"][2]["options"].update(n=4))
        record = self.advance(record)
        self.assertEqual(record.state, "DONE")
        self.assertEqual(record.stage("last").artifacts[0]["n"], 4)
        self.assertEqual([(c["version"], c["stages"], c["done"]) for c in record.recipe_changed],
                         [(1, {"last": "changed"}, [])])
        self.assertEqual(record.recipe["stages"][2]["options"], {"n": 4})
        self.assertTrue(os.path.isfile(os.path.join(record.run_dir, "recipes", "recipe_1.yml")))
        self.assertIn("recipe", [h["event"] for h in record.stage("last").history])
        self.assertEqual(self.warnings("bundle copy"), [])  # recipe.yml is not a bundle file
        self.assertIn(("message", "The recipe of run %s changed (version 1, %s): last changed"
                       % (record.run_id, os.path.join("recipes", "recipe_1.yml"))), self.reporter.messages)
        self.assertEqual(self.advance(record).recipe_changed, record.recipe_changed)  # taken once

    def test_a_done_stage_is_only_recorded(self):
        record = self.started()
        made = list(record.stage("make").artifacts)
        self.edit(record, lambda data: data["stages"][0]["options"].update(n=9))
        record = self.advance(record, until="use")
        self.assertEqual([s.state for s in record.stages], ["DONE", "DONE", "NEW"])
        self.assertEqual(record.stage("make").artifacts, made)  # kept: made with n=3
        self.assertEqual(record.recipe_changed[0]["done"], ["make"])
        self.assertEqual(len(self.warnings("Stage make is DONE with its old options")), 1)
        self.assertIn("taufw rerun %s make" % (record.run_dir), self.warnings("old options")[0])

    def test_added_and_removed_stages(self):
        record = self.started(until="use")
        self.edit(record, lambda data: data["stages"].__setitem__(1, step("extra", file="steps/make.py",
                                                                          options={"n": 2})))
        record = self.advance(record)
        self.assertEqual(([s.name for s in record.stages], record.state), (["make", "extra", "last"], "DONE"))
        self.assertEqual(record.recipe_changed[0]["stages"], {"extra": "added", "use": "removed"})
        removed = record.removed[0]
        archive = os.path.join("logs", "use", "attempt1")
        self.assertEqual((removed["name"], removed["state"], removed["removed"]["archive"]), ("use", "DONE", archive))
        self.assertEqual(sorted(os.listdir(os.path.join(record.run_dir, archive))),
                         ["01_use.log", "context.json", "result.json", "stage"])
        self.assertFalse(os.path.exists(os.path.join(record.run_dir, "stages", "use")))
        self.assertEqual(self.read_run(record)["removed"][0]["name"], "use")
        self.edit(record, lambda data: data["stages"].insert(1, step("use", inputs={"numbers": "make"})))
        record = self.advance(record)  # the id again: a new record, the next attempt number
        self.assertEqual((record.stage("use").state, len(record.removed)), ("DONE", 1))
        self.edit(record, lambda data: data["stages"].pop(1))
        record = self.advance(record)
        self.assertEqual([r["removed"]["archive"] for r in record.removed], [archive, os.path.join("logs", "use",
                                                                                                    "attempt2")])

    def test_a_refused_edit_changes_nothing(self):
        record = self.started()
        saved = self.read_run(record)
        for change, text in (
                (lambda data: data["stages"].pop(0), "no stage 'make' in the recipe"),  # use reads it: the checks of taufw check
                (lambda data: data.update(name="other"), "name: cannot change in a run"),
                (lambda data: data["stages"][2].update(file="steps/nope.py"), "is not a file of the bundle")):
            path = self.edit(record, change)
            with self.assertRaises(RecipeError) as context:
                self.advance(record)
            self.assertIn(text, str(context.exception))
            self.assertEqual(self.read_run(record)["stages"], saved["stages"])
            self.assertNotIn("recipe_changed", self.read_run(record))
            self.assertIsNone(read_lock(record.run_dir))
            shutil.copy(os.path.join(record.run_dir, "recipes", "recipe_0.yml"), path)  # undone

    def test_next_and_status_see_the_edited_recipe(self):
        cli = load_cli(self)
        record = self.started()
        self.edit(record, lambda data: data["stages"].pop(1))  # use, the next stage, is removed
        from TauFW.Framework._internal.runtime.run_recipe import pending_change
        self.assertEqual(pending_change(RunRecord.load(record.run_dir)),
                         "%s was edited (use removed): the next advance takes it" % (os.path.join("bundle",
                                                                                                  "recipe.yml")))
        self.assertEqual(cli.main(["status", record.run_dir]), 0)
        self.assertEqual(cli.main(["advance", record.run_dir, "--next"]), 0)  # the next stage of the new recipe
        record = RunRecord.load(record.run_dir)
        self.assertEqual(([s.name for s in record.stages], record.state), (["make", "last"], "DONE"))
        self.assertIsNone(pending_change(record))
        self.edit(record, lambda data: data.update(name="other"))
        self.assertIn("the next advance refuses it (name: cannot change", pending_change(record))
        self.assertEqual(cli.main(["advance", record.run_dir]), 1)

    def test_a_run_without_the_file_keeps_its_recipe(self):
        record = self.started()
        os.remove(os.path.join(record.run_dir, "bundle", "recipe.yml"))  # a run started before CL §55
        record = self.advance(record)
        self.assertEqual((record.state, record.recipe_changed), ("DONE", []))

    def test_edit_rules(self):
        from TauFW.Framework._internal.runtime.run_recipe import edit_problems, recipe_changes
        production = {"stage": "production", "id": "production", "inputs": None, "eras": ["2018"]}
        hists = {"stage": "controlhists", "id": "hists", "inputs": {"tuples": "production"}}
        plots = {"stage": "controlplots", "id": "plots", "inputs": {"hists": "hists"}}
        prep = step("prep")
        old = {"name": "x", "pico": {"config": None}, "stages": [prep, production, hists, plots]}

        def problems(**changes):
            new = json.loads(json.dumps(old))
            new.update(changes)
            return [str(issue) for issue in edit_problems(old, new)]

        self.assertEqual(problems(stages=[prep, production, plots, hists]), [])  # after production: free
        self.assertEqual(problems(stages=[prep, production, dict(hists, eras=["2022"])]), [])
        self.assertEqual(recipe_changes(old, dict(old, stages=[prep, production, plots, hists])),
                         {"plots": "moved", "hists": "moved"})
        for stages, text in (([prep, dict(production, eras=["2022"]), hists, plots], "Undo: production changed"),
                             ([dict(prep, options={"a": 1}), production, hists, plots], "Undo: prep changed"),
                             ([production, prep, hists, plots], "Undo: prep moved, production moved"),
                             ([step("new"), prep, production, hists], "Undo: new added"),
                             ([prep, hists, plots], "Undo: production removed")):
            found = problems(stages=stages)
            self.assertEqual(len(found), 1, found)
            self.assertIn("stages: stage 'production' (production) and the stages before it cannot change", found[0])
            self.assertIn(text, found[0])
        self.assertIn("stage 'hists' is a controlhists stage in this run: a stage of another type needs another id",
                      problems(stages=[prep, production, dict(hists, stage="shapes"), plots])[0])
        self.assertIn("pico.config: cannot change in a run with a production stage",
                      problems(pico={"config": "pico.json"})[0])
        self.assertIn("run_root: cannot change in a run", problems(run_root="/afs/x")[0])
        self.assertIn("a run without a production stage cannot get one",
                      edit_problems(dict(old, stages=[prep]), dict(old, stages=[prep, production]))[0].message)


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
