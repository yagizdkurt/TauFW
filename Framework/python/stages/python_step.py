# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Python stage: a Python file of the analysis bundle as a recipe step.

    - stage: python
      id: fit_summary             # unique in the recipe
      inputs: {fit: fit}          # input name -> id of an earlier stage (any names); null: no inputs
      file: steps/fit_summary.py  # a bundle file (or an absolute path)
      function: run               # default: run
      options: {min_points: 1}    # any mapping; the step gets it as ctx.options
      timeout: null               # seconds; null: no limit

    def run(ctx):                 # in steps/fit_summary.py
        fits = ctx.input('fit', kind='fit')
        return {'message': "%d points" % len(fits), 'artifacts': [{'kind': 'table', 'path': ...}]}

A python step may appear anywhere in a recipe and any number of times (each with its own id). It runs after the
stages before it, in its own Python process (step_runner.py), in the bundle directory:

    advance(): NEW ─▶ preflight ─▶ <run_dir>/logs/<id>/context.json ─▶ python3 step_runner.py context.json
                                                                        │  log: <run_dir>/logs/<id>/01_<id>.log
                                   DONE (message, artifacts) ◀─ ok ─────┴─ fails ─▶ FAILED (log tail)

    inputs:   the artifacts of the stages its inputs name (ctx.input, ctx.artifacts), the step's options, the
              bundle files
    outputs:  what the function returns: a message and artifacts (dicts), saved in run.json; the step's own
              files belong in ctx.stage_dir (<run_dir>/stages/<id>/); context.json, result.json and the log are
              the Framework's and go to <run_dir>/logs/<id>/
    preflight: the file exists, it defines the function (checked with ast: nothing is imported), the options
              can be written as JSON

Public API:
  PythonStage(runner, python), PythonSpec, StepRequest, STEP_RUNNER
"""
import ast
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Optional

from TauFW.Utilities.Process import Command, CommandPlan, ProcessRunner, RunReport
from TauFW.Framework.stages.base import StageContext, spec_to_dict
from TauFW.Framework.stages.local import LocalStage

__all__ = ['PythonStage', 'PythonSpec', 'StepRequest', 'STEP_RUNNER']


# =============================================================================
# ================================= CONSTANTS =================================


STEP_RUNNER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'step_runner.py')
CONTEXT_NAME = 'context.json'  # written to the step's log directory before it runs
RESULT_NAME = 'result.json'    # written there by the step runner when the step succeeded


# =============================================================================
# =================================== STAGE ===================================


class PythonStage(LocalStage):
    """A Python step, run by step_runner.py in its own process.
    runner: a TauFW.Utilities.Process.ProcessRunner (default: new); python: the Python of the step (default:
    this one)."""
    name = 'python'
    inputs = None    # any input names, connected to any earlier stages
    outputs = None   # whatever the step returns
    # Spec = PythonSpec: set at the bottom of this file.

    def request(self, spec, context):
        """The StepRequest: the resolved step file and everything context.json needs."""
        stage_id = context.stage_id
        if not stage_id:
            raise ValueError("a python step needs its stage id (the recipe's 'id')")
        if context.run_dir:
            stage_dir = os.path.abspath(context.stage_dir(stage_id))
            log_dir = os.path.abspath(context.log_dir(stage_id))
        else:  # plan() before the run exists
            placeholder = StageContext(run_dir='<run_dir>', stage_id=stage_id)
            stage_dir, log_dir = placeholder.stage_dir(), placeholder.log_dir()
        return StepRequest(stage_id=stage_id, file=os.path.abspath(spec.file), function=spec.function,
                           options=dict(spec.options), timeout=spec.timeout, run_dir=context.run_dir,
                           stage_dir=stage_dir, log_dir=log_dir, bundle_dir=context.bundle_dir or os.path.dirname(
                               os.path.abspath(spec.file)),
                           upstream={key: list(value) for key, value in context.upstream.items()},
                           inputs=dict(context.inputs), pico_config=context.pico_config)

    def plan_commands(self, request):
        """One command: the step runner on the step's context.json, in the bundle directory."""
        command = Command(request.stage_id, (self.python, STEP_RUNNER, request.context_file), request.bundle_dir,
                          expects=(request.result_file,), timeout=request.timeout,
                          env=(('TAUFW_PICO_CONFIG', request.pico_config),) if request.pico_config else ())
        return CommandPlan(cwd=request.bundle_dir, commands=(command,))

    def preflight(self, request, context):
        problems = []
        if not os.path.isfile(request.file):
            return ("step file %s not found" % (request.file),)
        try:
            with open(request.file, encoding='utf-8') as stream:
                tree = ast.parse(stream.read(), request.file)
        except (SyntaxError, ValueError, OSError) as error:
            return ("cannot read step file %s: %s" % (request.file, error),)
        if not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == request.function
                   for node in tree.body):
            problems.append("step file %s has no top-level function %r" % (request.file, request.function))
        try:
            json.dumps(request.options)
        except (TypeError, ValueError) as error:
            problems.append("the options of step %r cannot be written as JSON: %s" % (request.stage_id, error))
        return tuple(problems)

    def execute(self, request, logdir, progress):
        """Write context.json, run the step, read result.json. Raises RuntimeError if the step succeeded but its
        result.json cannot be read (the step runner always writes a valid one)."""
        os.makedirs(request.stage_dir, exist_ok=True)
        os.makedirs(request.log_dir, exist_ok=True)
        with open(request.context_file, 'w', encoding='utf-8') as stream:
            json.dump(request.context_dict(), stream, indent=2)
        plan = self.plan_commands(request)
        results = self.runner.run_all(plan.commands, logdir, progress)
        report = RunReport(results=results, total=len(plan.commands))
        if not report.ok:
            return report
        try:
            with open(request.result_file, encoding='utf-8') as stream:
                result = json.load(stream)
        except (OSError, ValueError) as error:
            raise RuntimeError("cannot read the result of step %r: %s" % (request.stage_id, error))
        return StepReport(results=report.results, total=report.total, artifacts=tuple(result['artifacts']),
                          message=result['message'])

    def summary(self, report):
        return getattr(report, 'message', "") or super().summary(report)

    # =========================================================================
    # ============================= CONSTRUCTION ==============================

    def __init__(self, runner=None, python=None):
        super().__init__(api=None)
        self.runner = runner or ProcessRunner()
        self.python = python or sys.executable


# =============================================================================
# ================================= CONTRACT ==================================


@dataclass(frozen=True)
class PythonSpec:
    """Recipe options: the step file (a bundle file or an absolute path), the function to call (default: run),
    the step's options (any mapping) and a timeout in seconds (None: no limit)."""
    file:     str
    function: str = 'run'
    options:  dict = field(default_factory=dict)
    timeout:  Optional[float] = None

    def __post_init__(self):
        if not isinstance(self.file, str) or not self.file.endswith('.py'):
            raise ValueError("file must be a .py file (got %r)" % (self.file,))
        if not isinstance(self.function, str) or not self.function.isidentifier():
            raise ValueError("function must be a Python name (got %r)" % (self.function,))
        if self.options is None:
            object.__setattr__(self, 'options', {})
        if not isinstance(self.options, dict):
            raise ValueError("options must be a mapping (got %r)" % (self.options,))

    def request_dict(self):
        """The options (saved in run.json)."""
        return spec_to_dict(self)


@dataclass(frozen=True)
class StepRequest:
    """One run of a step: what context.json holds, plus the timeout."""
    stage_id:    str
    file:        str
    function:    str
    options:     dict
    timeout:     Optional[float]
    run_dir:     str
    stage_dir:   str
    log_dir:     str
    bundle_dir:  str
    upstream:    dict
    inputs:      dict = field(default_factory=dict)
    pico_config: Optional[str] = None

    @property
    def context_file(self):
        return os.path.join(self.log_dir, CONTEXT_NAME)

    @property
    def result_file(self):
        return os.path.join(self.log_dir, RESULT_NAME)

    def context_dict(self):
        """The content of context.json (see step_runner.py)."""
        return {'stage_id': self.stage_id, 'file': self.file, 'function': self.function, 'options': self.options,
                'run_dir': self.run_dir, 'stage_dir': self.stage_dir, 'bundle_dir': self.bundle_dir,
                'upstream': self.upstream, 'inputs': self.inputs, 'pico_config': self.pico_config,
                'result': self.result_file}


@dataclass(frozen=True)
class StepReport(RunReport):
    """The RunReport of a step, with the message the step returned."""
    message: str = ""


PythonSpec._paths = ('file',)  # resolved against the bundle (bundle.py)
PythonStage.Spec = PythonSpec
