# Author: Yagizhan Dinckurt (October 2026)
"""Local stages: stages that run their module's scripts on this machine and finish in one advance() call.

The plots, histograms and fit stages all work the same way. Their module API (Plotter, Fitter) turns a request
into a list of commands, runs them one after the other and reports what they made. This base class does the
part that is the same for all three:

    advance():  NEW ─▶ preflight ─┬─ problems ─▶ PreflightError (the stage stays NEW; fix it, advance again)
                                  └─ ready ────▶ run the commands ─┬─ all ok ─▶ DONE   (artifacts)
                                                                  └─ failed ─▶ FAILED (log tail, log path)
    plan():     the module's CommandPlan, with the preflight problems added to its notes

A subclass sets `name` and `Spec`, and implements:
    request(spec, context)          -> the module request (raise ValueError if the stage cannot run)
    plan_commands(request)          -> CommandPlan
    preflight(request, context)     -> tuple of problems (empty: ready)
    execute(request, logdir, progress) -> RunReport
`reads_tuples = True` makes the stage warn when the run's PicoProducer config is not the one the scripts read
$PICODIR from, and record the production tuples as its inputs.

Public API:
  LocalStage, LOG_TAIL
"""
import os
from collections import deque
from dataclasses import replace

from TauFW.Framework.stages.base import Stage, StageState, StageOutcome, StageContext, PreflightError

__all__ = ['LocalStage', 'LOG_TAIL']


# =============================================================================
# ================================= CONSTANTS =================================


LOG_TAIL = 20  # lines of the failed command's log shown in the terminal


class LocalStage(Stage):
    """Base class of the stages that run scripts locally; see the module docstring.
    api: the module API object (a Fitter TauESID or a Plotter ControlPlots, or a fake one in the tests)."""
    reads_tuples = False

    # =========================================================================
    # =============================== PIPELINES ===============================

    def advance(self, spec, stage_record, reporter, context=None):
        """NEW: run all commands (see the table at the top of this file). Other states: nothing to do."""
        context = context or StageContext()
        state = StageState(stage_record.state)
        if state is not StageState.NEW:
            return StageOutcome(state, "nothing to do (%s)" % (state.value))
        try:
            request = self.request(spec, context)
        except ValueError as error:
            return StageOutcome(StageState.FAILED, str(error), 'failed')
        problems = self.preflight(request, context)
        if problems:
            raise PreflightError("; ".join(problems))
        self._check_pico_config(context, reporter)
        report = self.execute(request, context.stage_dir(self.name), self._progress(reporter))
        status = {'commands': [result.to_dict() for result in report.results]}
        if self.reads_tuples and context.artifacts('production'):
            status['inputs'] = [artifact.get('path') for artifact in context.artifacts('production')]
        if not report.ok:
            return self._failed(report, status, reporter)
        message = "%d command(s), %d artifact(s)" % (len(report.results), len(report.artifacts))
        return StageOutcome(StageState.DONE, message, 'done', status=status, artifacts=tuple(report.artifacts))

    def plan(self, spec, context=None):
        """The commands that advance() would run (nothing runs). Preflight problems are added to the notes.
        Raises PreflightError if the stage cannot be planned (e.g. no working points)."""
        context = context or StageContext()
        try:
            request = self.request(spec, context)
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

    def pico_config_source(self):
        """The PicoProducer config the module's scripts read $PICODIR from (None: unknown)."""
        return getattr(self.api, 'pico_config_source', None)

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

    def _progress(self, reporter):
        """progress(index, total, command, result) for the runner: one line per command start and end."""
        def progress(index, total, command, result):
            if result is None:
                reporter.message("[%s] %d/%d %s ..." % (self.name, index, total, command.label))
            else:
                reporter.message("[%s] %d/%d %s %s (%.0f s)" % (self.name, index, total, command.label,
                                                               "ok" if result.ok else "FAILED", result.seconds))
        return progress

    def _check_pico_config(self, context, reporter):
        """Warn when the scripts read $PICODIR from another PicoProducer config than the run uses."""
        source = self.pico_config_source()
        if not (self.reads_tuples and context.pico_config and source):
            return
        if os.path.abspath(context.pico_config) != os.path.abspath(source):
            reporter.warning("The %s scripts read $PICODIR from %s, not from the run's PicoProducer config %s"
                             % (self.name, source, context.pico_config))

    # =========================================================================
    # ============================= CONSTRUCTION ==============================

    def __init__(self, api):
        self.api = api


def _tail(path, lines=LOG_TAIL):
    try:
        with open(path, encoding='utf-8', errors='replace') as stream:
            return ''.join(deque(stream, maxlen=lines)).rstrip()
    except OSError as error:
        return "(cannot read the log: %s)" % (error)
