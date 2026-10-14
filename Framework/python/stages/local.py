# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Local stages: stages that run their module's scripts on this machine and finish in one advance() call.

The plots, histograms, fit and python stages all work the same way. Their module API (Plotter, Fitter; the step
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
A stage with a `tuples` input slot records the tuples of the stage connected to it as its inputs.

Public API:
  LocalStage, LOG_TAIL
"""
from collections import deque
from dataclasses import replace

from TauFW.Framework.bundle import resolve_spec
from TauFW.Framework.stages.base import Stage, StageState, StageOutcome, StageContext, PreflightError

__all__ = ['LocalStage', 'LOG_TAIL']


# =============================================================================
# ================================= CONSTANTS =================================


LOG_TAIL = 20  # lines of the failed command's log shown in the terminal


class LocalStage(Stage):
    """Base class of the stages that run scripts locally; see the module docstring.
    api: the module API object (a Fitter TauESID or a Plotter ControlPlots, or a fake one in the tests)."""

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
        problems = self.preflight(request, context)
        if problems:
            raise PreflightError("; ".join(problems))
        stage_id = context.stage_id or self.name
        report = self.execute(request, context.stage_dir(stage_id), self._progress(reporter, stage_id))
        status = {'commands': [result.to_dict() for result in report.results]}
        if context.input_artifacts('tuples'):
            status['inputs'] = [artifact.get('path') for artifact in context.input_artifacts('tuples')]
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
        return replace(plan, notes=tuple(plan.notes) + tuple(self.preflight(request, context)))

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

    # =========================================================================
    # ================================ HELPERS ================================

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
        """progress(index, total, command, result) for the runner: one line per command start and end."""
        def progress(index, total, command, result):
            if result is None:
                reporter.message("[%s] %d/%d %s ..." % (stage_id, index, total, command.label))
            else:
                reporter.message("[%s] %d/%d %s %s (%.0f s)" % (stage_id, index, total, command.label,
                                                               "ok" if result.ok else "FAILED", result.seconds))
        return progress

    # =========================================================================
    # ============================= CONSTRUCTION ==============================

    def __init__(self, api):
        """api: the module API object (None for a stage without one, e.g. python)."""
        self.api = api


def _tail(path, lines=LOG_TAIL):
    try:
        with open(path, encoding='utf-8', errors='replace') as stream:
            return ''.join(deque(stream, maxlen=lines)).rstrip()
    except OSError as error:
        return "(cannot read the log: %s)" % (error)
