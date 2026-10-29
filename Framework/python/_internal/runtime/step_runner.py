# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Step runner: runs the function of a recipe's Python step in its own process.

    python3 step_runner.py <run_dir>/logs/<id>/context.json

The python stage (stages/python_step.py) writes context.json and runs this file as a separate process, in the
bundle directory, with the stage's log as stdout. This file only uses the standard library, so a step runs even
where the TauFW packages cannot be imported; a step that needs them imports them itself.

    context.json ─▶ load the step file ─▶ function(ctx) ─▶ check the result ─▶ result.json, exit 0
                                              │ raises: traceback in the log, exit 1
                                              └ bad result (not JSON, not artifacts): message in the log, exit 1

context.json: {stage_id, file, function, options, run_dir, stage_dir, bundle_dir, upstream, inputs, pico_config,
               result}
result.json:  {message: str, artifacts: [dict, ...]}

What the step function gets (StepContext) and may return is described in StepContext and in _result below.

Public API:
  StepContext, main(argv)
"""
import importlib.util
import json
import os
import sys
import traceback

__all__ = ['StepContext', 'main']


# =============================================================================
# ================================= PIPELINE ==================================


def main(argv=None):
    """Run the step of a context.json; returns the exit code (0: result.json written)."""
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: step_runner.py CONTEXT_JSON")
        return 2
    with open(argv[0], encoding='utf-8') as stream:
        data = json.load(stream)
    context = StepContext(data)
    function = _function(data['file'], data['function'])
    try:
        value = function(context)
    except Exception:
        traceback.print_exc()
        print("Step %r failed: %s raised an exception (traceback above)" % (context.stage_id, data['function']))
        return 1
    try:
        result = _result(value)
    except ValueError as error:
        print("Step %r failed: %s" % (context.stage_id, error))
        return 1
    with open(data['result'], 'w', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print("Step %r done: %s" % (context.stage_id, result['message'] or "%d artifact(s)" % len(result['artifacts'])))
    return 0


# =============================================================================
# ================================== CONTEXT ==================================


class StepContext:
    """What a step function gets as its only argument.

    options:     the step's `options:` from the recipe (a dict)
    stage_id:    the step's id
    stage_dir:   the directory for the step's own files, <run_dir>/stages/<id> (exists)
    run_dir:     the run directory
    bundle_dir:  the bundle directory of the run (its copy of the bundle files); also the working directory
    pico_config: the run's PicoProducer configuration (a recipe with a production stage), or None
    inputs:      input name -> stage id, as connected in the recipe's `inputs:` (for {path: <dir>}: that directory)
    upstream:    stage id (or directory) -> artifacts (dicts) of the stages the inputs name
    input(name, kind=None):           artifacts of the stage connected to an input, optionally of one kind
    artifacts(stage=None, kind=None): upstream artifacts of one stage id (or all), optionally of one kind
    path(relative):  a path in the bundle directory
    log(message):    print one line to the step's log
    """

    def input(self, name, kind=None):
        if name not in self.inputs:
            raise KeyError("step %r has no input %r (inputs: %s)" % (self.stage_id, name,
                                                                    ', '.join(self.inputs) or 'none'))
        return self.artifacts(self.inputs[name], kind)

    def artifacts(self, stage=None, kind=None):
        stages = [stage] if stage else list(self.upstream)
        return [artifact for name in stages for artifact in self.upstream.get(name, ())
                if kind is None or artifact.get('kind') == kind]

    def path(self, relative):
        return os.path.join(self.bundle_dir, relative)

    def log(self, message):
        print("[%s] %s" % (self.stage_id, message), flush=True)

    # =========================================================================
    # ============================= CONSTRUCTION ==============================

    def __init__(self, data):
        self.options = dict(data.get('options') or {})
        self.stage_id = data['stage_id']
        self.stage_dir = data['stage_dir']
        self.run_dir = data.get('run_dir', "")
        self.bundle_dir = data.get('bundle_dir') or os.getcwd()
        self.pico_config = data.get('pico_config')
        self.upstream = dict(data.get('upstream') or {})
        self.inputs = dict(data.get('inputs') or {})
        os.makedirs(self.stage_dir, exist_ok=True)

    def __repr__(self):
        return "<StepContext %r>" % (self.stage_id)


# =============================================================================
# ================================== HELPERS ==================================


def _function(path, name):
    """The step function of a file. The file's directory comes first on sys.path, so a step can import the
    other files next to it; this runner's directory is removed from it (it holds the Framework's modules)."""
    here = os.path.dirname(os.path.abspath(__file__))
    sys.dont_write_bytecode = True  # no __pycache__ in the run's copy of the bundle
    sys.path[:] =[entry for entry in sys.path if os.path.abspath(entry or os.curdir) != here]
    sys.path.insert(0, os.path.dirname(os.path.abspath(path)))
    spec = importlib.util.spec_from_file_location("taufw_step", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["taufw_step"] = module
    spec.loader.exec_module(module)
    function = getattr(module, name, None)
    if not callable(function):
        raise SystemExit("Step file %s has no function %r" % (path, name))
    return function


def _result(value):
    """The step's return value as result.json: None -> no artifacts; a list -> the artifacts; a dict with
    'message' and/or 'artifacts'. Every artifact must be a dict, and everything must be JSON."""
    if value is None:
        value = {}
    elif isinstance(value, (list, tuple)):
        value = {'artifacts': list(value)}
    if not isinstance(value, dict):
        raise ValueError("the step returned %s; return None, a list of artifacts or a dict" % (type(value).__name__))
    unknown = [key for key in value if key not in ('message', 'artifacts')]
    if unknown:
        raise ValueError("unknown key %r in the step's result (known: message, artifacts)" % (unknown[0]))
    artifacts = list(value.get('artifacts') or [])
    if not all(isinstance(artifact, dict) for artifact in artifacts):
        raise ValueError("every artifact must be a dict, e.g. {'kind': 'table', 'path': ...}")
    result = {'message': str(value.get('message') or ""), 'artifacts': artifacts}
    try:
        json.dumps(result)
    except (TypeError, ValueError) as error:
        raise ValueError("the step's result cannot be written as JSON: %s" % (error))
    return result


# =============================================================================
# =================================== MAIN ====================================


if __name__ == "__main__":
    sys.exit(main())
