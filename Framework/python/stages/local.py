# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Local stages: stages that run their module's scripts on this machine and finish in one advance() call.

The plots, histograms, fit and python stages all work the same way. Their module API (Histogrammer, Fitter; the step
runner for python) turns a request into a list of commands, runs them one after the other and reports what they
made. This base class does the part that is the same for all of them:

    advance():  NEW ─▶ preflight ─┬─ problems ─▶ PreflightError (the stage stays NEW; fix it, advance again)
                                  └─ ready ────▶ run the commands ─┬─ all ok ─▶ DONE   (artifacts)
                                                                  └─ failed ─▶ FAILED (log tail, log path)
    plan():     the module's CommandPlan, with the preflight problems added to its notes

A subclass sets `name` and `Spec`, and implements:
    request(spec, context)          -> the module request (raise ValueError if the stage cannot run); `spec` has
                                       its path options resolved against the bundle already (bundle.py), and
                                       context.pico_config is the run's PicoProducer config for the scripts
    plan_commands(request)          -> CommandPlan
    preflight(request, context)     -> tuple of problems (empty: ready)
    execute(request, logdir, progress) -> RunReport
    summary(report)                 -> the stage's message when it is DONE (default: counts)
    config_file(value)              -> the module file of a path option (for taufw.py init; default: None)
    requested_samples(spec, context) -> [(era, channel, MC names, data pattern)] of its sample model files
                                       (`samples` option; default: none), see samples.py
A stage with a `tuples` input slot reads the tuples its input names (tuples_pattern): the pattern recorded on the
artifacts of the production stage it names (of this run, or of another run: {path: <run_dir>/stages/<id>}), or the
recipe's {external: <pattern>}; with `null` (old recipes) none,
and the scripts read $PICODIR of the PicoProducer configuration as before. The pattern, and the tuple paths of a
production stage, are recorded in the stage's last_status; input_problems() are added to the preflight.

The scripts of a stage run in its output directory, output_dir(context) = <run_dir>/stages/<id>/ (the Framework
decides where; the module API only uses it). Before a run exists (plan), it is the placeholder
'<run_dir>/stages/<id>'.

Public API:
  LocalStage, LOG_TAIL
  fixed_directory(pattern)   the part of a directory pattern before its first $KEY
"""
import os
from collections import deque
from dataclasses import replace

from TauFW.Framework.bundle import resolve_spec
from TauFW.Framework.stages.base import Stage, StageState, StageOutcome, StageContext, PreflightError

__all__ = ['LocalStage', 'LOG_TAIL', 'fixed_directory']


# =============================================================================
# ================================= CONSTANTS =================================


LOG_TAIL = 20  # lines of the failed command's log shown in the terminal


class LocalStage(Stage):
    """Base class of the stages that run scripts locally; see the module docstring.
    api: the module API object (a Fitter TauESID or a Histogrammer ControlPlots, or a fake one in the tests)."""

    # =========================================================================
    # =============================== PIPELINES ===============================

    def advance(self, spec, stage_record, reporter, context=None):
        """NEW: run all commands (see the table at the top of this file). Other states: nothing to do."""
        context = context or StageContext()
        state = StageState(stage_record.state)
        if state is not StageState.NEW:
            return StageOutcome(state, "nothing to do (%s)" % (state.value))
        try:
            request = self.request(resolve_spec(spec, context.bundle_dir), context)
        except ValueError as error:
            return StageOutcome(StageState.FAILED, str(error), 'failed')
        problems = tuple(self.input_problems(context, files=True)) + tuple(self.preflight(request, context))
        if problems:
            raise PreflightError("; ".join(problems))
        stage_id = context.stage_id or self.name
        report = self.execute(request, context.log_dir(stage_id), self._progress(reporter, stage_id))
        status = {'commands': [result.to_dict() for result in report.results]}
        if context.input_artifacts('tuples'):
            status['inputs'] = [artifact.get('path') for artifact in context.input_artifacts('tuples')]
        if 'tuples' in (self.inputs or {}) and self.tuples_pattern(context)[0]:
            status['tuples'] = self.tuples_pattern(context)[0]
        if not report.ok:
            return self._failed(report, status, reporter)
        return StageOutcome(StageState.DONE, self.summary(report), 'done', status=status,
                            artifacts=tuple(report.artifacts))

    def plan(self, spec, context=None):
        """The commands that advance() would run (nothing runs). Preflight problems are added to the notes.
        Raises PreflightError if the stage cannot be planned (e.g. no working points)."""
        context = context or StageContext()
        try:
            request = self.request(resolve_spec(spec, context.bundle_dir), context)
        except ValueError as error:
            raise PreflightError(str(error))
        plan = self.plan_commands(request)
        return replace(plan, notes=tuple(plan.notes) + tuple(self.input_problems(context, files=False))
                       + tuple(self.preflight(request, context)))

    # =========================================================================
    # ============================ SUBCLASS HOOKS =============================

    def request(self, spec, context):
        raise NotImplementedError

    def plan_commands(self, request):
        raise NotImplementedError

    def preflight(self, request, context):
        raise NotImplementedError

    def execute(self, request, logdir, progress):
        raise NotImplementedError

    def summary(self, report):
        return "%d command(s), %d artifact(s)" % (len(report.results), len(report.artifacts))

    def config_file(self, value):
        return None

    def requested_samples(self, spec, context):
        """(era, channel, MC sample names, data pattern) the stage reads, from its `samples` option (sample model
        files, read through the Histogrammer API `samples_api`); [] without the option (the module's own tables)."""
        files = getattr(spec, 'samples', ())
        if not files or not hasattr(self.samples_api, 'sample_names'):
            return []
        resolved = resolve_spec(spec, context.bundle_dir)
        pairs = dict.fromkeys((artifact['era'], artifact['channel'])
                              for artifact in self.plan_commands(self.request(resolved, context)).artifacts)
        return [(era, channel) + tuple(self.samples_api.sample_names(resolved.samples, era, channel))
                for era, channel in pairs]

    # =========================================================================
    # ================================ INPUTS =================================

    def tuples_pattern(self, context, slot='tuples'):
        """(pattern or None, problems): where the stage's tuples are, as a directory pattern ($ERA, $GROUP).
          {external: <pattern>}  -> that pattern
          a production stage     -> the pattern recorded on its tuple artifacts (in a plan: the planned one);
                                    none yet (not planned) -> None. Also another run's ({path: ...}, its
                                    manifest's artifacts).
          null                   -> None (the scripts read $PICODIR of the PicoProducer configuration)"""
        if slot in context.external:
            return context.external[slot], ()
        stage_id = context.inputs.get(slot)
        artifacts = context.input_artifacts(slot)
        if not stage_id or not artifacts:
            return None, ()
        patterns = list(dict.fromkeys(artifact.get('pattern') for artifact in artifacts))
        if None in patterns:
            return None, ("the tuples of %s do not record where they are (made before the Framework chose "
                          "their place, CL §18); start a new run, or name them with {external: <pattern>}"
                          % (context.input_name(slot)),)
        if len(patterns) > 1:
            return None, ("the tuples of %s are in several places (%s)" % (context.input_name(slot),
                                                                         ', '.join(patterns)),)
        return patterns[0], ()

    def input_problems(self, context, files=True):
        """Problems of the stage's tuples input (empty: none, or no such slot). files: also check that the tuple
        files of a production stage exist, and the fixed part of an external pattern (before its first $)."""
        if 'tuples' not in (self.inputs or {}):
            return ()
        pattern, problems = self.tuples_pattern(context)
        if problems or not files:
            return problems
        missing = [artifact['path'] for artifact in context.input_artifacts('tuples')
                   if artifact.get('path') and '://' not in artifact['path'] and not os.path.exists(artifact['path'])]
        if missing:
            return ("%d tuple file(s) of %s not found, e.g. %s"
                    % (len(missing), context.input_name('tuples'), missing[0]),)
        if 'tuples' in context.external:
            directory = fixed_directory(pattern)
            if not os.path.isdir(directory):
                return ("tuple directory %s (of {external: %s}) not found" % (directory, pattern),)
        return ()

    # =========================================================================
    # ================================ HELPERS ================================

    def output_dir(self, context):
        """The directory the stage's scripts run in and write to: <run_dir>/stages/<id> (absolute); in a plan
        before the run exists, the placeholder '<run_dir>/stages/<id>'."""
        stage_id = context.stage_id or self.name
        if context.run_dir:
            return os.path.abspath(context.stage_dir(stage_id))
        return StageContext(run_dir='<run_dir>', stage_id=stage_id).stage_dir()

    def _failed(self, report, status, reporter):
        """FAILED: show the end of the failed command's log, and say where the full log is."""
        failed = report.failed
        if failed is None:  # stopped without a failed command (should not happen)
            return StageOutcome(StageState.FAILED, "%d of %d command(s) ran" % (len(report.results), report.total),
                                'failed', status=status)
        reasons = []
        if failed.returncode != 0:
            reasons.append("exit code %s" % (failed.returncode))
        if failed.missing:
            reasons.append("missing output: %s" % (', '.join(failed.missing)))
        message = "%s: %s; log: %s" % (failed.label, '; '.join(reasons), failed.log)
        reporter.warning("Command %r failed (%s). Last lines of %s:\n%s"
                         % (failed.label, '; '.join(reasons), failed.log, _tail(failed.log)))
        return StageOutcome(StageState.FAILED, message, 'failed', status=status)

    def _progress(self, reporter, stage_id):
        """progress(index, total, command, result) for the runner: one line and one progress event per command
        start and end."""
        def progress(index, total, command, result):
            if result is None:
                reporter.message("[%s] %d/%d %s ..." % (stage_id, index, total, command.label))
                reporter.event('progress', stage=stage_id, index=index, total=total, label=command.label,
                               status="run")
            else:
                reporter.message("[%s] %d/%d %s %s (%.0f s)" % (stage_id, index, total, command.label,
                                                               "ok" if result.ok else "FAILED", result.seconds))
                reporter.event('progress', stage=stage_id, index=index, total=total, label=command.label,
                               status="ok" if result.ok else "failed", seconds=result.seconds)
        return progress

    # =========================================================================
    # ============================= CONSTRUCTION ==============================

    def __init__(self, api, samples_api=None):
        """api: the module API object (None for a stage without one, e.g. python).
        samples_api: what reads the sample model files of the `samples` option (a Histogrammer ControlPlots: the
        format is the Histogrammer's); None: the stage's own api."""
        self.api = api
        self.samples_api = samples_api or api


def fixed_directory(pattern):
    """The part of a directory pattern before its first $KEY, e.g. /eos/.../TES_variations for
    /eos/.../TES_variations/$ERA/$GROUP."""
    if '$' not in pattern:
        return pattern
    head = pattern.split('$', 1)[0]
    if head.endswith(('/', os.sep)):  # .../TES_variations/$ERA -> .../TES_variations
        return head.rstrip('/' + os.sep) or head
    return os.path.dirname(head)      # .../tuples_$ERA -> ...


def _tail(path, lines=LOG_TAIL):
    try:
        with open(path, encoding='utf-8', errors='replace') as stream:
            return ''.join(deque(stream, maxlen=lines)).rstrip()
    except OSError as error:
        return "(cannot read the log: %s)" % (error)
