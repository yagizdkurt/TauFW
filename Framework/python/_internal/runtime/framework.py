# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""TauFW Framework: the single entry point that runs an analysis pipeline from a recipe.

Purpose:  run the stages of an analysis (production -> shapes -> fit) one after the other. The Framework
          gives each stage its options from the recipe, keeps the run's state in run.json, and decides whether
          to wait for the batch system or to move on. What a stage really does stays in its own package (the
          production stage, for example, calls the PicoProducer API).
Inputs:   a recipe (a Recipe, an analysis bundle directory, or a .yml/.json file) and the files it names.
Outputs:  a run directory <run_root>/<name>_<YYYYmmdd-HHMMSS>/ (run_root: the recipe's, default taufw_runs/)
          with run.json (the state), run.log (the messages), bundle/ (a copy of the bundle files the run uses,
          and recipe.yml: the run's own recipe), recipes/ (a copy of every version of it), logs/<stage id>/ (the Framework's files of each stage) and stages/<stage id>/ (what the stage makes,
          and its manifest.json once it is DONE; production: its merged pico tuples,
          <era>/<group>/<sample>_<channel>.root, with their pattern on the artifacts).

Pipeline map:

    recipe ─▶ plan() ─▶ start() ─▶ advance() ─▶ … ─▶ advance() ─▶ DONE
                 │          │            │
              RunPlan   RunRecord     RunRecord (saved after every stage step)

    stage order: the order of the recipe, e.g. production ─▶ controlhists ─▶ controlplots ─▶ shapes ─▶ fit (a
                 recipe may leave stages out, and repeat any stage but production); python steps (a Python file of
                 the bundle) too. production runs on the batch system (PicoProducer API); controlhists,
                 controlplots, shapes and fit run their module's scripts locally (Histogrammer, Plotter and Fitter
                 APIs), python steps run step_runner.py; these finish inside one advance() call.
    run model:   stepwise. start() and advance() move the run as far as they can (until a stage waits for the
                 batch system, fails, is not ready or is not implemented), save run.json and return.
                 advance(wait=True) repeats this every `poll` seconds until the run no longer waits.
    stop point:  until=<stage id> (start, advance, rerun, run; `--until`, `--next` in taufw.py) stops the call once
                 that stage is DONE, also when it was DONE before; the run is then PAUSED (RunState). A run that
                 an advance works on now is RUNNING (run_state: read from its advance lock, never from run.json).
                 until=NEXT_STAGE: the first stage that is not DONE (rerun: its start), once the run's recipe is
                 read.
    run recipe:  <run_dir>/bundle/recipe.yml is the run's own recipe (run_recipe.py, CL §55): every advance and
                 rerun reads it first, and takes a change after its checks (edit rules, `taufw check`, samples;
                 a problem is a RecipeError and nothing moves): run.json recipe and recipe_changed, a copy in
                 recipes/recipe_<N>.yml; an added stage is NEW; a removed one is archived to logs/<id>/attempt<N>/
                 and its record moved to run.json removed; a changed stage that is DONE is kept (only recorded).
    stage data:  every stage gets a StageContext: the run directory (logs: <run_dir>/logs/<stage id>/, output:
                 <run_dir>/stages/<stage id>/),
                 its inputs (slot -> stage id, from the recipe) and the artifacts of those stages once they are
                 DONE (production's tuples, the shapes stage's shapes), the run's PicoProducer config and the
                 bundle directory its path options are resolved against. A stage never sees the artifacts of a
                 stage its inputs do not name.
    other runs:  an input may name the stage directory of another run ({path: <dir>}): its artifacts come from
                 the directory's manifest.json (manifest.py; never from that run's run.json), and nothing is
                 written there. A directory that cannot be read (no manifest, moved, wrong kind) is a note in
                 plan() and stops the stage in advance() like a preflight problem (it stays NEW). What was read is
                 recorded in the stage's `sources` (run.json and its own manifest).
    one advance: advance() holds the run's advance lock (run_lock.py: <run_dir>/advance.lock, not in run.json)
                 while it works and waits; a second advance of the run is refused (RunLockError), also from another
                 machine, until the lock is released or lost (then taken over: see run_lock.py).
    bundle:      start() copies the bundle files the recipe uses to <run_dir>/bundle/; the run reads them from
                 there, so later edits of the bundle never change a run (see bundle.py; the run's recipe.yml is
                 not one of these files). Every advance compares
                 that copy with its start: a change is warned about once and recorded (run.json bundle.changed;
                 the manifests of the stages that run after it: bundle_changed), CL §44.
    rerun:       rerun(record, <id>) (taufw rerun, CL §55; it replaced retry): <id> and every stage after it in
                 recipe order go back to NEW (what each left goes to logs/<id>/attempt<N>/, recorded in its
                 `attempts`), then the run advances: <id> and the stages after it run again, those before it do
                 not. Without <id>: the FAILED stage (a FAILED stage stops the run; advance() never moves it). The
                 start must come after production (it cannot run twice yet), except production FAILED after
                 max_tries: it goes on WAITING with max_tries more tries, nothing moved (CL §48).
                 plan_rerun(): what a rerun would do, nothing written (`--dry-run`).
    samples:     plan() and start() compare the samples a production stage makes with those its readers' sample
                 model files ask for (samples.py): plan() lists the problems, start() refuses them (RecipeError).

Public API:
  Framework.from_recipe(recipe_or_path, reporter, pico, fitter, histogrammer, plotter, tes_shapes) /
  from_record(record, ...)
  plan, start, advance, rerun, run, status    pipelines
  plan_rerun(record, stage_id) -> RerunPlan   what rerun() would do (`taufw rerun --dry-run`)
  make_bundle(target)                         a new analysis bundle with copies of the module configs used
  load_run(run_dir)                           the RunRecord of a run directory
  failed_stage(record), retryable_stage(record)   the FAILED stage of a run; the one rerun() without a stage id
                                              starts from (None if it cannot)
  next_stage(record)                          the first stage that is not DONE (`--next`)
  run_state(record), live_state(state, lock)  the RunState with RUNNING while an advance holds the run's lock
  RerunError                                  rerun() cannot start there
  StopPointError                              until= names no stage of the run
  NEXT_STAGE                                  until= for the next stage (`--next` of advance and rerun)
  check_writable(directory, what)             write and remove a small file (RunDirectoryError if it fails)
  RunPlan, RunSummary, StageSummary, RerunPlan   records (bottom of this file)
"""
import os, json, re, shutil, time
from contextlib import nullcontext
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Mapping, Optional, Tuple
from TauFW.Framework._internal.defaults import (DEFAULT_RUN_ROOT, RUN_LOG_NAME, DEFAULT_POLL_SECONDS, BUNDLE_DIR_NAME,
                                                LOGS_DIR_NAME, timestamp, default_file_io)
from TauFW.Framework._internal.recipes.bundle import (path_rows, snapshot, make_bundle, source_files, bundle_hashes,
                                                      bundle_changes, hashes_digest)
from TauFW.Framework._internal.runtime.manifest import write_manifest, ManifestError
from TauFW.Framework._internal.recipes.recipe import Recipe, RecipeError, Issue
from TauFW.Framework._internal.recipes.samples import sample_issues
from TauFW.Framework._internal.runtime.run_record import RunRecord, RunState, StageRecord
from TauFW.Framework._internal.runtime.run_recipe import (write_run_recipe, read_run_recipe, run_recipe_file,
                                                          recipe_copy, recipe_changes, edit_problems, changes_text,
                                                          saved_dict)
from TauFW.Framework._internal.runtime.run_lock import RunLock, RunLockError, read_lock
from TauFW.Framework._internal.runtime.interrupts import deferred_interrupt
from TauFW.Framework._internal import user_settings
from TauFW.Framework._internal.runtime.reporting import FrameworkReporter
from TauFW.Framework._internal.recipes.validation import read_source
from TauFW.Framework.stages import (STAGES, StageState, StageContext, StageNotImplemented, PreflightError,
                                    ProductionStage, ControlHistsStage, ControlPlotsStage, ShapesStage, FitStage,
                                    PythonStage)

__all__ = ['Framework', 'RunPlan', 'StagePlan', 'RunSummary', 'StageSummary', 'load_run', 'check_writable',
           'failed_stage', 'retryable_stage', 'next_stage', 'run_state', 'live_state', 'RunDirectoryError',
           'RerunError', 'RerunPlan', 'StopPointError', 'RunLockError', 'RUN_LOG_NAME', 'DEFAULT_RUN_ROOT',
           'NEXT_STAGE']


# =============================================================================
# ================================= CONSTANTS =================================


NEXT_STAGE = ':next'  # until= for the first stage that is not DONE (rerun: its start); never a stage id
MAX_STEPS = 8  # most steps one stage may take in one advance() call (a safety net against a stage that never settles)
ATTEMPT_DIR = 'attempt%d'              # logs/<id>/attempt<N>/: an earlier attempt, moved there by a rerun (CL §55)
ATTEMPT_NAME = re.compile(r'attempt\d+$')
ATTEMPT_STAGE_DIR = 'stage'            # logs/<id>/attempt<N>/stage/: what the attempt left in stages/<id>/


class Framework:
    """Runs the stages of one recipe.

    Pipelines:      plan(recipe=None)                         -> RunPlan     changes nothing
                    start(recipe=None, run_root=None, until)  -> RunRecord   new run directory, then advance()
                    advance(record, wait, poll, take_lock, until) -> RunRecord   step the stages in order; saves run.json
                    retry(record, wait, poll, take_lock, until)   -> RunRecord   the FAILED stage NEW again, then advance
                    run(recipe=None, run_root, wait, poll, until) -> RunRecord   start(), then advance() while waiting
                    status(record)                            -> RunSummary  read-only: saved and live state
                    make_bundle(target, name)                 -> paths       new bundle from this recipe
    Stage dispatch: _advance_stages, _advance_stage, _apply, _write_manifest, _stage_for
    Construction:   from_recipe(recipe_or_path, reporter, pico, fitter, histogrammer, plotter, tes_shapes);
                    from_record(...);
                    Framework(recipe, stages, reporter, files, sleep, clock)

    Naming used below: a `stage_spec` is one stage of the recipe (a StageSpec: its name, id and options), and a
    `stage_record` is the saved state of that stage in run.json (a StageRecord, named by the stage id). Stage
    objects, records and upstream artifacts are all keyed by the stage id.
    """

    # =========================================================================
    # =============================== PIPELINES ===============================

    def plan(self, recipe=None, deep=True):
        """What each stage would do, without changing anything. Placeholder stages are listed as not implemented.
        Each stage sees the artifacts that its input stages plan to make (e.g. the fit sees the planned shapes),
        so the plan of a whole recipe is complete before anything runs. deep=False leaves out the checks that open
        data files (StageContext.deep; the stages with Stage.deep_checks)."""
        recipe = recipe or self.recipe
        plans, planned = [], {}
        for stage_spec in recipe.stages:
            sources, found, problems = _read_sources(stage_spec)
            context = StageContext(upstream={**_inputs_of(stage_spec, planned), **found},
                                   inputs=_input_keys(stage_spec), external=stage_spec.external, sources=sources,
                                   pico_config=recipe.pico_config_path, bundle_dir=recipe.bundle_dir,
                                   stage_id=stage_spec.id, deep=deep)
            paths = path_rows(stage_spec.spec, recipe.bundle_dir)
            if problems:  # an input from another run that cannot be read: nothing to plan with
                plans.append(StagePlan(stage=stage_spec.id, plan=None, note="; ".join(problems), paths=paths,
                                       sources=sources))
                continue
            try:
                stage = self._stage_for(stage_spec.id)
                stage_plan = stage.plan(stage_spec.spec, context)
                plans.append(StagePlan(stage=stage_spec.id, plan=stage_plan, paths=paths, sources=sources))
                planned[stage_spec.id] = (stage.planned_artifacts(stage_spec.spec, stage_plan, context)
                                          if hasattr(stage, 'planned_artifacts') else
                                          tuple(getattr(stage_plan, 'artifacts', ()) or ()))
            except (StageNotImplemented, PreflightError) as err:  # placeholder, or cannot be planned yet
                plans.append(StagePlan(stage=stage_spec.id, plan=None, note=str(err), paths=paths,
                                       sources=sources))
        problems, warnings = self._sample_issues(recipe)
        return RunPlan(name=recipe.name, stages=tuple(plans), pico_config=recipe.pico_config_path,
                       bundle_dir=recipe.bundle_dir, sample_problems=tuple(problems),
                       sample_warnings=tuple(warnings))

    def start(self, recipe=None, run_root=None, until=None):
        """Create the run directory, copy the bundle files and write run.json, then call advance() once (until: as
        in advance(); StopPointError before anything is made if it names no stage of the recipe).
        run_root: the parent of the run directory; it takes precedence over the recipe's run_root, then comes
        runs.run_root of the user config (user_settings.py), and without any of them it is taufw_runs/ (in the
        working directory). A run_root that is given (here or in the recipe) is
        first tried with a small file written and removed: if that fails, RunDirectoryError and nothing is made.
        Side effects: creates <run_root>/<name>_<time>/ with run.json, run.log and bundle/, and runs the first
        stage steps (the production stage, for example, submits its jobs)."""
        recipe = recipe or self.recipe
        _check_until(until, [stage_spec.id for stage_spec in recipe.stages], recipe.name)
        problems, warnings = self._sample_issues(recipe)
        if problems:  # before anything is made: production would not make what the readers ask for
            raise RecipeError(recipe.source, problems)
        for warning in warnings:
            self.reporter.warning(str(warning))
        run_root = run_root or recipe.run_root or user_settings.run_root()
        if run_root:
            check_writable(run_root, "run root")
        record = RunRecord.create(recipe, run_root or DEFAULT_RUN_ROOT, pico_config=self._pico_config(recipe),
                                  now=self.clock())
        if recipe.bundle_dir:  # first: a bundle that is too large stops here, before the run directory exists
            record.bundle = snapshot(recipe, os.path.join(record.run_dir, BUNDLE_DIR_NAME))
        self.files.make_directory(record.run_dir)
        write_run_recipe(recipe, record.run_dir, self.files)
        self.reporter.attach_log(os.path.join(record.run_dir, RUN_LOG_NAME))
        self.reporter.header("TauFW run %s" % (record.run_id))
        self.reporter.message("Run directory: %s" % (record.run_dir))
        record.save(self.files)
        return self.advance(record, until=until)

    def advance(self, record, wait=False, poll=DEFAULT_POLL_SECONDS, take_lock=False, until=None):
        """Step the stages in order until one waits for the batch system, fails or is not implemented. run.json is
        saved after every step. With wait=True, this is repeated every `poll` seconds while the run is waiting.
        until: a stage id: stop once that stage is DONE (at once if it is DONE already); the run is then PAUSED.
        StopPointError (before the lock is taken) if it names no stage of the run. NEXT_STAGE: the first stage
        that is not DONE, after the run's recipe is read (none: the run is DONE, nothing to stop after).
        The run directory is first tried with a small file written and removed (RunDirectoryError if that fails,
        e.g. an expired AFS token), before any stage moves. The run's advance lock is held throughout
        (run_lock.py): RunLockError if another advance holds it; take_lock=True takes over a lost lock of another
        machine (a lost lock of this machine, whose process is gone, is always taken over).
        Before the stages move, the run's own recipe (bundle/recipe.yml) is read and an edit of it taken
        (_take_run_recipe, CL §55; RecipeError if it is refused, and nothing moves), and the run's bundle copy is
        compared with its start (_check_bundle, CL §44).
        Side effects: whatever the stages do (production: submit, resubmit, merge); run.json and run.log;
        <run_dir>/advance.lock while it runs."""
        return self._locked(record, wait, poll, take_lock, until=until)

    def rerun(self, record, stage_id=None, wait=False, poll=DEFAULT_POLL_SECONDS, take_lock=False, until=None):
        """Run stage `stage_id` and every stage after it in recipe order again, then go on like advance() (CL §55,
        replacing retry, CL §44): each of them that left something (logs/<id>/, stages/<id>/) has it moved to
        logs/<id>/attempt<N>/ (N: the next free number) and goes back to NEW; the attempt is recorded in its
        `attempts` (run.json: reason failed|rerun, the start, its state and message, the archive, the recipe
        version and the bundle copy's changes since the start). The stages before it are not touched.
        stage_id None: the FAILED stage. Production FAILED after max_tries goes on WAITING with the max_tries of
        its retry_fields() more tries, nothing moved (CL §48). RerunError (nothing changed) for another start of
        production or before it, a FAILED stage before the start, a stage that cannot run again, or no stage.
        until: as in advance() (NEXT_STAGE: the start only); not a stage before the start (StopPointError).
        The run's recipe is read first (an edit is taken, as in advance()); lock, wait, poll and side effects as
        in advance()."""
        return self._locked(record, wait, poll, take_lock, rerun=True, start=stage_id, until=until)

    def plan_rerun(self, record, stage_id=None):
        """What rerun(record, stage_id) would do now, nothing written and no lock taken (`taufw rerun --dry-run`):
        a RerunPlan. Raises what rerun() would: RecipeError for an edit of the run's recipe that it refuses,
        RerunError."""
        recipe, changes = self._pending_recipe(record)
        start, production, rows = _rerun_rows(record, recipe or self._recipe_of(record), stage_id)
        return RerunPlan(run_id=record.run_id, start=start, production=production, rows=tuple(rows),
                         recipe_changes=changes, bundle_changed=self._bundle_changed(record),
                         lock=read_lock(record.run_dir))

    def _locked(self, record, wait, poll, take_lock, rerun=False, start=None, until=None):
        """advance() or rerun(): check the stop point and the run directory, take the run's advance lock, read the
        run's recipe, then work."""
        _check_until(until, self._stage_ids(record), record.run_id)
        check_writable(record.run_dir, "run directory")
        with RunLock(record.run_dir, take=take_lock) as lock:
            if lock.taken is not None:
                taken = lock.taken
                why = ("its process is gone" if taken.get('gone') else
                       "no sign of life for %.0f s" % (taken.get('quiet', 0)))
                self.reporter.warning("Took over the advance lock of pid %s on %s (since %s, %s)"
                                      % (taken.get('pid'), taken.get('host'), taken.get('since'), why))
            self.reporter.attach_log(os.path.join(record.run_dir, RUN_LOG_NAME))
            done = self._take_run_recipe(record, warn=not rerun)
            if rerun:
                start, production, rows = _rerun_rows(record, self._recipe_of(record), start)
                for stage_id in set(done) - {row['stage'] for row in rows}:  # the rerun does not run them again
                    self._warn_old_options(record, stage_id)
                ids = [stage_record.name for stage_record in record.stages]
                until = start if until == NEXT_STAGE else until
                if until is not None and ids.index(until) < ids.index(start):
                    raise StopPointError("stage %r comes before %r, where the rerun starts: stop at %s or after it"
                                         % (until, start, start))
                self._rerun(record, start, production, rows)
            if until == NEXT_STAGE:
                until = next_stage(record)
                if until is None:
                    self.reporter.message("Run %s: every stage is DONE, there is no next stage" % (record.run_id))
            return self._advance(record, wait, poll, lock, until)

    def _advance(self, record, wait, poll, lock, until=None):
        """advance() while the lock is held."""
        self.reporter.attach_log(os.path.join(record.run_dir, RUN_LOG_NAME))
        self.reporter.event('run', run_id=record.run_id, run_dir=record.run_dir)
        while True:
            self._take_run_recipe(record)
            self._check_bundle(record)
            stopped = self._advance_stages(record, lock, until)
            record.save(self.files)
            if stopped:
                self.reporter.message("Stopped after stage %s (--until)" % (until))
            self.reporter.message("Run %s: %s" % (record.run_id, record.state))
            self.reporter.event('run_state', run_id=record.run_id, state=RunState(record.state).value)
            if not (wait and record.state == RunState.WAITING):
                return record
            self.reporter.message("Waiting %s s before the next check..." % (poll))
            self.reporter.event('wait', seconds=poll)
            self.sleep(poll)

    def run(self, recipe=None, run_root=None, wait=False, poll=DEFAULT_POLL_SECONDS, until=None):
        """start(), and with wait=True keep advancing until the run no longer waits (until: as in advance())."""
        record = self.start(recipe, run_root, until=until)
        if wait and record.state == RunState.WAITING:
            record = self.advance(record, wait=True, poll=poll, until=until)
        return record

    def status(self, record):
        """The saved state of every stage, plus its live status if the stage can check it (production: the
        PicoProducer status of the jobs). Read-only: nothing is saved or submitted."""
        summaries = []
        for stage_spec in self._recipe_of(record).stages:
            stage_record = record.stage(stage_spec.id)
            try:
                live = self._stage_for(stage_spec.id).status(stage_spec.spec, stage_record)
            except StageNotImplemented:
                live = None
            summaries.append(StageSummary(stage=stage_spec.id, state=stage_record.state,
                                          attempt=stage_record.attempt, message=stage_record.message, live=live))
        return RunSummary(run_id=record.run_id, state=record.state, run_dir=record.run_dir, stages=tuple(summaries))

    def make_bundle(self, target, name=None):
        """Write a new analysis bundle at `target` from this recipe: recipe.yml, the recipe's own files (every file
        of its bundle, at the same relative paths), copies of the Configs/ templates and channel setups its stages
        use (next to recipe.yml) with the recipe pointing at them, and steps/example.py.
        name: the new recipe's name (default: the bundle directory's name). Returns the copied config paths.
        Raises BundleError if `target` exists."""
        sources = {}
        for stage_spec in self.recipe.stages:
            stage = self._stage_for(stage_spec.id)
            for option, value, resolved, where in path_rows(stage_spec.spec, self.recipe.bundle_dir):
                found = (resolved if where == 'template' else
                         stage.config_file(value) if where == 'channel' and hasattr(stage, 'config_file') else None)
                if found and os.path.isfile(found):
                    sources[(stage_spec.id, option, value)] = (stage.group, found)
        data = self.recipe.to_dict()
        data['name'] = name or os.path.basename(os.path.abspath(target))
        extra = source_files(self.recipe) if self.recipe.bundle_dir else {}
        return make_bundle(data, sources, target, self.files, extra=extra)

    # =========================================================================
    # ============================ STAGE DISPATCH =============================

    def _advance_stages(self, record, lock=None, until=None):
        """Advance the stages in recipe order, and stop where the run cannot go further for now, or once the stage
        `until` is DONE. Returns True only when it stopped there.

        A stage may take several steps in one call (for example MERGING -> DONE, then the next stage starts).
        For each stage, in order:
          - DONE:                     go on with the next stage.
          - FAILED, NOT_IMPLEMENTED:  stop; advance() never moves this stage again (retry() moves a FAILED stage
                                      first, CL §44, §48).
          - waiting for jobs:         take one step (a status check). If the stage still waits, stop: advance()
                                      must be called again later.
          - not ready (PreflightError): stop; the stage keeps its state, the reason is in its message and
                                      history, and advance() can be called again once it is fixed.
          - otherwise:                take a step and look again.
        A stage that has not settled after MAX_STEPS steps also stops the call (a safety net).
        run.json is saved after every step, so a crash never loses a step that was done.
        lock: the RunLock of advance(); before every step, RunLockError if another advance took it over.
        A step that may submit jobs (Stage.submits) and the save of run.json after it are not cut by Ctrl-C
        (interrupts.py); other steps stop at once (a local command is ended by the runner).
        """
        for stage_spec in self._recipe_of(record).stages:
            stage_record = record.stage(stage_spec.id)
            for step in range(MAX_STEPS):
                if lock is not None:
                    lock.check()
                state = StageState(stage_record.state)
                if state is StageState.DONE:
                    if stage_spec.id == until:
                        return True  # the stop point (--until, --next): the later stages wait for the next advance
                    break  # this stage is finished: continue with the next stage
                if state.terminal:
                    return  # FAILED or NOT_IMPLEMENTED: the later stages cannot start
                if step > 0 and state.waiting:
                    return  # already checked once in this call: come back later
                submits = getattr(self._stage_for(stage_spec.id), 'submits', None)
                guard = (deferred_interrupt(self.reporter, "Stage %s" % (stage_spec.id))
                         if submits and submits(stage_record) else nullcontext())
                with guard:
                    try:
                        outcome = self._advance_stage(stage_spec, stage_record, self._context(record, stage_spec))
                    except PreflightError:
                        record.save(self.files)  # not ready: the reason is in the stage's message and history
                        return
                    except Exception:
                        record.save(self.files)  # keep the error in the stage's history; the state is unchanged
                        raise
                    self._apply(stage_record, outcome)
                    if outcome.state is StageState.DONE:  # first the manifest: a crash before run.json is saved
                        self._write_manifest(record, stage_spec, stage_record)  # only repeats the stage
                    record.save(self.files)
                if outcome.state.waiting:
                    return  # the stage now waits for the batch system: come back later
            else:
                return  # MAX_STEPS reached without settling: stop here
        return False

    def _advance_stage(self, stage_spec, stage_record, context):
        """One step of one stage. If the stage raises an error, the error is written to the stage's history (the
        state is not changed) and raised again. A PreflightError (environment not ready, or an input from another
        run that cannot be read) also becomes the stage's message. The sources of the step are recorded first."""
        stage = self._stage_for(stage_spec.id)
        if stage_record.request is None and hasattr(stage_spec.spec, 'request_dict'):  # saved once, for run.json:
            fields = getattr(stage, 'request_fields', None)  # production: with the user config's defaults
            stage_record.request = fields(stage_spec.spec) if fields else stage_spec.spec.request_dict()
        self.reporter.header("Stage %s (%s)" % (stage_spec.id, stage_record.state))
        self.reporter.event('stage_step', stage=stage_spec.id, type=stage_spec.stage, state=stage_record.state)
        try:
            problems = _read_sources(stage_spec)[2]
            if problems:
                raise PreflightError("; ".join(problems))
            stage_record.sources = _jsonable(dict(context.sources))  # what this step reads (every step)
            return stage.advance(stage_spec.spec, stage_record, self.reporter, context)
        except PreflightError as err:
            stage_record.message = "not ready: %s" % (err)
            stage_record.log('preflight', str(err), time=self._now())
            self.reporter.warning("Stage %s is not ready: %s" % (stage_spec.id, err))
            raise
        except Exception as err:
            stage_record.log('error', "%s: %s" % (type(err).__name__, err), time=self._now())
            self.reporter.warning("Stage %s raised %s: %s" % (stage_spec.id, type(err).__name__, err))
            raise

    def _apply(self, stage_record, outcome):
        """Copy a StageOutcome into the stage's record. Values are stored as they read back from run.json
        (lists, not tuples), so a record looks the same before and after saving."""
        stage_record.state = outcome.state.value
        stage_record.message = outcome.message
        if outcome.attempt is not None:
            stage_record.attempt = outcome.attempt
        if outcome.submission is not None:
            stage_record.submissions.append(_jsonable(outcome.submission))
        if outcome.status is not None:
            stage_record.last_status = _jsonable(outcome.status)
        if outcome.artifacts:
            stage_record.artifacts = _jsonable(list(outcome.artifacts))
        stage_record.log(outcome.event or outcome.state.value.lower(), outcome.message, time=self._now())
        report = self.reporter.warning if outcome.state is StageState.FAILED else self.reporter.message
        report("Stage %s: %s%s" % (stage_record.name, outcome.state.value,
                                   " - " + outcome.message if outcome.message else ""))
        self.reporter.event('stage_state', stage=stage_record.name, state=outcome.state.value,
                            message=outcome.message)

    def _write_manifest(self, record, stage_spec, stage_record):
        """<run_dir>/stages/<id>/manifest.json of a stage that is DONE (see manifest.py): which stage of which run
        made the directory, from which inputs, where it was written, and its artifacts."""
        write_manifest(self.files, StageContext(run_dir=record.run_dir).stage_dir(stage_spec.id), record.run_id,
                       stage_spec, stage_record.sources, stage_record.artifacts, self._now(),
                       bundle_changed=bool(record.bundle.get('changed')))

    # =========================================================================
    # ==================== RERUN, RUN RECIPE AND BUNDLE CHECK =================

    def _rerun(self, record, start, production, rows):
        """rerun() under the lock, with _rerun_rows() of the run: production after max_tries goes on as its
        retry_state() and retry_fields() say (nothing moved; CL §48); otherwise every row that left something or
        is not NEW has it archived (_archive_attempt) and goes back to NEW: its message, artifacts, last status,
        request and sources are cleared (the history keeps them). Each gets an `attempts` entry; run.json is
        saved."""
        now, changed = self._now(), self._bundle_changed(record)
        version = len(record.recipe_changed)
        for row in rows:
            stage_id = row['stage']
            stage_record = record.stage(stage_id)
            if row['state'] == StageState.NEW and row['archive'] is None:
                continue  # never ran: nothing to keep
            entry = {'time': now, 'attempt': row['attempt'], 'reason': 'failed' if row['state'] == StageState.FAILED
                     else 'rerun', 'from': start, 'state': row['state'], 'message': stage_record.message,
                     'archive': None, 'recipe_version': version, 'bundle_changed': changed}
            if production:
                stage, stage_spec = self._stage_for(stage_id), self._recipe_of(record).stage(stage_id)
                fields = stage.retry_fields(stage_spec.spec, stage_record)
                stage_record.attempts.append(dict(entry, **fields))
                stage_record.state = StageState.WAITING.value
                what = "kept in place; %s" % (", ".join("%s now %s" % item for item in fields.items()))
            else:
                if row['archive'] is not None:
                    context = StageContext(run_dir=record.run_dir, stage_id=stage_id)
                    _archive_attempt(context.log_dir(), context.stage_dir(), row['attempt'])
                    entry['archive'] = row['archive']
                stage_record.attempts.append(entry)
                stage_record.state = StageState.NEW.value
                stage_record.request = None
                stage_record.sources = {}
                what = "moved to %s" % (row['archive']) if row['archive'] else "nothing to move"
            stage_record.message = ""
            stage_record.artifacts = []
            stage_record.last_status = None
            stage_record.log('rerun', "rerun from %s: attempt %d (%s) %s" % (start, row['attempt'], row['state'], what),
                             time=now)
            self.reporter.message("Stage %s: rerun from %s; attempt %d (%s) %s"
                                  % (stage_id, start, row['attempt'], row['state'], what))
            self.reporter.event('stage_state', stage=stage_id, state=stage_record.state, message="rerun")
        record.save(self.files)

    def _bundle_changed(self, record):
        """The bundle copy's changes since the start (bundle_changes), or None for a run without hashes."""
        start = record.bundle.get('sha256')
        return (bundle_changes(start, bundle_hashes(os.path.join(record.run_dir, BUNDLE_DIR_NAME)))
                if start is not None else None)

    def _take_run_recipe(self, record, warn=True):
        """Read the run's own recipe (<run_dir>/bundle/recipe.yml, run_recipe.py) and, if it is not the one in
        run.json, check it and take it (CL §55): the edit rules, every check of `taufw check` and the samples check
        (RecipeError listing the problems; nothing is changed). Taken: the stage records follow the new order (an
        added stage NEW; a removed one archived, _remove_stage); a changed stage that is not DONE runs with its
        new options (its request is saved again), one that is DONE keeps its state and output and is warned
        about (warn=False: the caller does, rerun); run.json recipe and recipe_changed, and a copy
        recipes/recipe_<N>.yml. A run without the file (started before CL §55) keeps its run.json recipe.
        Returns the ids of the changed stages that stay DONE."""
        recipe, changes = self._pending_recipe(record, warn=True)
        if recipe is None:
            return []
        new, path = saved_dict(recipe), run_recipe_file(record.run_dir)
        version, now = len(record.recipe_changed) + 1, self._now()
        self.files.make_directory(os.path.dirname(recipe_copy(record.run_dir, version)))
        self.files.copy_file(path, recipe_copy(record.run_dir, version), overwrite=True)
        kept = {stage_record.name: stage_record for stage_record in record.stages}
        for stage_id, change in changes.items():
            if change == 'removed':
                self._remove_stage(record, kept.pop(stage_id), version, now)
        done = [stage_id for stage_id, change in changes.items()
                if change == 'changed' and kept[stage_id].state == StageState.DONE]
        stages = []
        for stage_spec in recipe.stages:
            stage_record = kept.get(stage_spec.id)
            if stage_record is None:
                stage_record = StageRecord(name=stage_spec.id)
                stage_record.log('added', "added in recipe version %d" % (version), time=now)
            elif stage_spec.id in done:
                stage_record.log('recipe', "changed in recipe version %d; DONE with its old options" % (version),
                                 time=now)
            elif changes.get(stage_spec.id) == 'changed':
                stage_record.request = None  # saved again at its next step, with the new options
                stage_record.log('recipe', "changed in recipe version %d" % (version), time=now)
            stages.append(stage_record)
        record.stages = stages
        record.recipe = new
        record.recipe_changed.append({'time': now, 'version': version, 'stages': changes, 'done': done})
        self.recipe = recipe
        record.save(self.files)
        self.reporter.message("The recipe of run %s changed (version %d, %s): %s"
                              % (record.run_id, version, os.path.relpath(recipe_copy(record.run_dir, version),
                                                                         record.run_dir),
                                 changes_text(changes) or "no stage changed"))
        for stage_id in done if warn else ():
            self._warn_old_options(record, stage_id)
        return done

    def _warn_old_options(self, record, stage_id):
        self.reporter.warning("Stage %s is DONE with its old options: the stages after it read that output. To run "
                              "it with the new ones: taufw rerun %s %s" % (stage_id, record.run_dir, stage_id))

    def _pending_recipe(self, record, warn=False):
        """(Recipe, changes) of the run's recipe file if it is not the run.json recipe and passes every check
        (_take_run_recipe), (None, None) if there is nothing to take. Writes nothing. RecipeError for a problem.
        warn: report the samples check's warnings."""
        recipe, issues = read_run_recipe(record, full=False)
        if (recipe is None and not issues) or (recipe is not None and saved_dict(recipe) == record.recipe):
            return None, None
        path = run_recipe_file(record.run_dir)
        recipe, issues = read_run_recipe(record)
        if issues:
            raise RecipeError(path, list(issues))
        new = saved_dict(recipe)
        changes = recipe_changes(record.recipe, new)
        problems = edit_problems(record.recipe, new, changes)
        if problems:
            raise RecipeError(path, problems)
        self.stages.update(_build_stages([stage_spec for stage_spec in recipe.stages
                                          if stage_spec.id not in self.stages], recipe, self.reporter, self.apis))
        problems, warnings = self._sample_issues(recipe)
        if problems:
            raise RecipeError(path, problems)
        for warning in warnings if warn else ():
            self.reporter.warning(str(warning))
        return recipe, changes

    def _remove_stage(self, record, stage_record, version, now):
        """A stage that a change of the run's recipe removed: what it left (logs/<id>/, stages/<id>/) is moved to
        logs/<id>/attempt<N>/ (N: the next free number), and its record goes to run.json removed."""
        context = StageContext(run_dir=record.run_dir, stage_id=stage_record.name)
        log_dir, stage_dir = context.log_dir(), context.stage_dir()
        archive = None
        if _left_behind(log_dir, stage_dir):
            archive = os.path.relpath(_archive_attempt(log_dir, stage_dir, _next_attempt(log_dir)), record.run_dir)
        stage_record.log('removed', "removed in recipe version %d%s"
                         % (version, "; moved to %s" % (archive) if archive else ""), time=now)
        record.removed.append(_jsonable(dict(asdict(stage_record),
                                             removed={'time': now, 'version': version, 'archive': archive})))
        self.reporter.message("Stage %s: removed from the recipe%s" % (stage_record.name,
                                                                         "; moved to %s" % (archive) if archive else ""))

    def _stage_ids(self, record):
        """The stage ids of a run, as its next advance sees them: those of its recipe file if it can be read
        (its change is checked later), else those of run.json."""
        recipe, _ = read_run_recipe(record, full=False)
        return [stage_spec.id for stage_spec in (recipe or self._recipe_of(record)).stages]

    def _check_bundle(self, record):
        """Compare the run's bundle copy with its hashes from the start (run.json bundle.sha256). A change not seen
        before is warned about once and added to bundle.changed: the run is not clean any more (run_record.py).
        A run without hashes (no bundle files, or started before CL §44) is not checked."""
        start = record.bundle.get('sha256')
        if start is None:
            return
        now = bundle_hashes(os.path.join(record.run_dir, BUNDLE_DIR_NAME))
        changed = record.bundle.get('changed', [])
        digest = hashes_digest(now)
        if digest == (changed[-1]['digest'] if changed else hashes_digest(start)):
            return  # the same copy as at the start, or as at the last change: already said
        files = bundle_changes(start, now)
        record.bundle['changed'] = changed + [{'time': self._now(), 'files': files, 'digest': digest}]
        record.save(self.files)
        self.reporter.warning("The bundle copy of run %s is not the one it started with (%s): the stages that run "
                              "from now on read it as it is; run.json says so (bundle.changed), and so do the "
                              "manifests of those stages" % (record.run_id, _changes_text(files)))

    def _context(self, record, stage_spec):
        """The StageContext of one stage: the run directory, its inputs and the artifacts of those of its input
        stages that are DONE, and of the other runs' stage directories it names (those that can be read; the
        others stop the stage in _advance_stage), the run's PicoProducer config and bundle copy."""
        recipe = self._recipe_of(record)
        done = {}
        for earlier in recipe.stages:
            if earlier.id == stage_spec.id:
                break
            earlier_record = record.stage(earlier.id)
            if StageState(earlier_record.state) is StageState.DONE:
                done[earlier.id] = tuple(earlier_record.artifacts)
        sources, found, _ = _read_sources(stage_spec)
        return StageContext(run_dir=record.run_dir, upstream={**_inputs_of(stage_spec, done), **found},
                            inputs=_input_keys(stage_spec), external=stage_spec.external, sources=sources,
                            pico_config=recipe.pico_config_path or (record.pico_config or {}).get('path'),
                            bundle_dir=recipe.bundle_dir, stage_id=stage_spec.id)

    def _stage_for(self, stage_id):
        """The Stage object for a stage id."""
        if stage_id not in self.stages:
            raise KeyError("No stage %r in this Framework (stages: %s)" % (stage_id, ', '.join(self.stages)))
        return self.stages[stage_id]

    def _sample_issues(self, recipe):
        """(problems, warnings) of samples.py. If the comparison cannot be made (e.g. a catalog cannot be read), one
        warning says so: the stages report the cause themselves."""
        try:
            return sample_issues(recipe, self._stage_for)
        except Exception as error:
            return [], [Issue("samples", "the samples of production and its readers were not compared: %s"
                              % (error))]

    def _recipe_of(self, record):
        """The recipe saved in a run record, with the run's copy of the bundle. A run always continues with the
        recipe and bundle files it started with, even if they were changed since."""
        return _run_recipe(record)

    def _pico_config(self, recipe):
        """The path and a snapshot (copy) of the PicoProducer configuration of the production stage, for run.json.
        If there is no production stage, or its PicoProducer has no loaded configuration (e.g. a fake one in the
        tests), the path from the recipe is used and the snapshot is None."""
        production = recipe.first('production')
        stage = self.stages.get(production.id) if production else None
        config = getattr(getattr(stage, 'pico', None), 'config', None)
        record = {'path': getattr(config, '_path', recipe.pico_config_path),
                  'snapshot': dict(getattr(config, '_dict', {})) or None}
        settings = getattr(stage, 'settings', None)
        if settings and settings.used:  # only then: a run without them records what it did before
            record['user_config'] = {'path': str(settings.path), 'settings': list(settings.used)}
        return record

    def _now(self):
        return timestamp(self.clock())

    # =========================================================================
    # ======================= CONSTRUCTION & LIFECYCLE ========================

    @classmethod
    def from_recipe(cls, recipe, reporter=None, pico=None, fitter=None, histogrammer=None, plotter=None,
                    runner=None, tes_shapes=None):
        """recipe: a Recipe, or the path of a recipe file or analysis bundle directory.
        pico:    the PicoProducer to use (default: one built from the recipe's pico.config, reporting through the
                 Framework's reporter).
        fitter:  the Fitter API of the fit stage (default: TauFW.Fitter.api.TauESID()).
        histogrammer: the API of the controlhists stage, which also reads the sample files of the shapes stage
                 (default: TauFW.Histogrammer.api.ControlHists(); CL §21).
        plotter: the API of the controlplots stage (default: TauFW.Plotter.api.ControlPlots(); CL §21 S4).
        runner:  the ProcessRunner of the python steps (default: new).
        tes_shapes: the API of the shapes stage (default: TauFW.Histogrammer.api.TESShapes(); the Fitter's until
                 CL §22 H3).
        Only the APIs of the stages in the recipe are built (a stage that an edit of the run's recipe adds gets
        them later, _take_run_recipe). Only reads files."""
        if isinstance(recipe, str):
            recipe = Recipe.load(recipe)
        reporter = reporter or FrameworkReporter()
        apis = dict(pico=pico, fitter=fitter, histogrammer=histogrammer, plotter=plotter, runner=runner,
                    tes_shapes=tes_shapes)
        framework = cls(recipe, _build_stages(recipe.stages, recipe, reporter, apis), reporter=reporter)
        framework.apis = apis
        return framework

    @classmethod
    def from_record(cls, record, reporter=None, pico=None, fitter=None, histogrammer=None, plotter=None,
                    runner=None, tes_shapes=None):
        """A Framework that continues a run, with the recipe saved in its run.json and the run's bundle copy."""
        return cls.from_recipe(_run_recipe(record), reporter=reporter, pico=pico, fitter=fitter,
                               histogrammer=histogrammer, plotter=plotter, runner=runner, tes_shapes=tes_shapes)

    def __init__(self, recipe, stages, reporter=None, files=None, sleep=None, clock=None):
        """All services can be passed in (the tests pass fakes). Creating a Framework never writes, submits or
        changes the working directory.
        stages: stage name -> Stage object. files: a FileIO. sleep: like time.sleep. clock: like datetime.now."""
        self.recipe = recipe
        self.stages = dict(stages)
        self.reporter = reporter or FrameworkReporter()
        self.files = files or default_file_io()
        self.sleep = sleep or time.sleep
        self.clock = clock or datetime.now
        self.apis = {}  # the module APIs of from_recipe(), for the stages an edit of a run's recipe adds

    def close(self):
        """Nothing is held open; kept for `with Framework.from_recipe(...) as fw:`."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def __repr__(self):
        return "<Framework %r: %s>" % (self.recipe.name, ' -> '.join(s.stage for s in self.recipe.stages))


# =============================================================================
# ================================== RECORDS ==================================


@dataclass(frozen=True)
class StagePlan:
    """plan() of one stage: the stage's own plan object (production: a JobPlan), or None with a note.
    stage: the stage id; paths: (option, value as written, resolved path, 'bundle'|'template'|'channel'|'absolute' (bundle.where));
    sources: input slot -> the manifest summary of the other run's stage directory it names (those read)."""
    stage:   str
    plan:    object
    note:    str = ""
    paths:   Tuple[Tuple[str, str, str, str], ...] = ()
    sources: Mapping[str, dict] = field(default_factory=dict)


@dataclass(frozen=True)
class RunPlan:
    """plan() of a whole recipe: one StagePlan per stage, the PicoProducer config path and the bundle directory;
    sample_problems / sample_warnings: the comparison of samples.py (Issues; start() refuses the problems)."""
    name:        str
    stages:      Tuple[StagePlan, ...]
    pico_config: Optional[str] = None
    bundle_dir:  Optional[str] = None
    sample_problems: Tuple[object, ...] = ()
    sample_warnings: Tuple[object, ...] = ()


@dataclass(frozen=True)
class RerunPlan:
    """plan_rerun(): what a rerun would do. start: the stage it starts from; production: production after
    max_tries (CL §48: WAITING again, nothing moved); rows: one dict per stage from the start on, {stage, state,
    attempt (its N), archive (logs/<id>/attempt<N>, relative to the run directory; None: nothing to move)};
    recipe_changes: the edit of the run's recipe the rerun takes first (recipe_changes(); None: none);
    bundle_changed: the bundle copy's changes since the start (None: not known); lock: the advance lock if one is
    held (read_lock)."""
    run_id:         str
    start:          str
    production:     bool
    rows:           Tuple[dict, ...]
    recipe_changes: Optional[dict] = None
    bundle_changed: Optional[dict] = None
    lock:           Optional[dict] = None


@dataclass(frozen=True)
class StageSummary:
    """status() of one stage: saved state, attempt and message; live: the stage's live status (or None)."""
    stage:   str
    state:   str
    attempt: int
    message: str
    live:    Optional[object] = None


@dataclass(frozen=True)
class RunSummary:
    """status() of a run: its overall RunState and one StageSummary per stage."""
    run_id:  str
    state:   str
    run_dir: str
    stages:  Tuple[StageSummary, ...]


# =============================================================================
# ================================== HELPERS ==================================


def load_run(run_dir):
    """The RunRecord of a run directory."""
    return RunRecord.load(run_dir)


def failed_stage(record):
    """(id, stage name) of the FAILED stage of a run (the first in recipe order), or None."""
    for stage in record.recipe.get('stages', ()):
        if record.stage(stage['id']).state == StageState.FAILED:
            return stage['id'], stage['stage']
    return None


def next_stage(record):
    """The id of the first stage of a run (recipe order) that is not DONE, or None if all are: what `--next` stops
    after."""
    for stage in record.recipe.get('stages', ()):
        if record.stage(stage['id']).state != StageState.DONE:
            return stage['id']
    return None


def live_state(state, lock):
    """The RunState of a run whose stages give `state` (RunRecord.state) and whose advance lock is `lock`
    (read_lock: None when no advance holds it): RUNNING when a lock that is not lost is held on a run that is NEW or
    PAUSED (a local stage stays NEW while it works); otherwise `state`. A WAITING run that an advance polls stays
    WAITING."""
    if state in (RunState.NEW, RunState.PAUSED) and lock is not None and not lock.get('lost'):
        return RunState.RUNNING
    return RunState(state)


def run_state(record):
    """The live RunState of a run: live_state() of its stages and of its advance lock (a file read)."""
    return live_state(record.state, read_lock(record.run_dir))


def retryable_stage(record):
    """(id, stage name) of the FAILED stage that rerun() without a stage id would start from, or None: no failed
    stage, or one that cannot run again (Stage.retry_state: e.g. production other than after max_tries)."""
    failed = failed_stage(record)
    stage_class = STAGES.get(failed[1]) if failed else None
    return failed if stage_class and stage_class.retry_state(record.stage(failed[0])) is not None else None


class RunDirectoryError(OSError):
    """The run root or run directory cannot be written (see check_writable)."""


class RerunError(ValueError):
    """rerun() cannot start there; the message says why."""


class StopPointError(ValueError):
    """until= (--until) names no stage of the run."""


def _check_until(until, stage_ids, name):
    """StopPointError if `until` is given and is not one of the stage ids of the run (or recipe) `name` (nor
    NEXT_STAGE)."""
    if until is not None and until != NEXT_STAGE and until not in stage_ids:
        raise StopPointError("%s has no stage %r to stop after (stages: %s)" % (name, until, ", ".join(stage_ids)))


def check_writable(directory, what):
    """Write and remove a small file in `directory`, or, if it does not exist yet, in its nearest existing parent
    (where it would be made); nothing is left behind. It shows that the directory can be written now, not that
    there is space for what the run will write. Raises RunDirectoryError."""
    existing = os.path.abspath(directory)
    while not os.path.isdir(existing) and os.path.dirname(existing) != existing:
        existing = os.path.dirname(existing)
    probe = os.path.join(existing, ".taufw_write_test_%d" % (os.getpid()))
    try:
        with open(probe, 'w') as stream:
            stream.write("TauFW write test\n")
        os.remove(probe)
    except OSError as err:
        raise RunDirectoryError("cannot write in the %s %s: %s. Choose another directory (run_root in the recipe, "
                                "or --run-root), or check your permissions (on lxplus: kinit; aklog)"
                                % (what, directory, err)) from err


def _run_recipe(record):
    """The recipe saved in run.json, resolved against the run's bundle copy (<run_dir>/bundle)."""
    return Recipe.from_dict(record.recipe, source=record.run_id,
                            bundle_dir=os.path.join(record.run_dir, BUNDLE_DIR_NAME))


def _inputs_of(stage_spec, artifacts):
    """The artifacts (stage id -> artifacts) of the stages a stage's inputs name, among those given."""
    return {stage_id: artifacts[stage_id] for stage_id in stage_spec.connections.values()
            if stage_id is not None and stage_id in artifacts}


def _input_keys(stage_spec):
    """input slot -> the key of its artifacts in StageContext.upstream: the stage id, or the directory of a
    {path: <dir>} input (None: null or external). Never None for a {path} input: a stage that saw None would take
    the slot for null (the fit would read Fitter/)."""
    return {**stage_spec.connections, **stage_spec.paths}


def _read_sources(stage_spec):
    """(sources, artifacts, problems) of a stage's {path: <dir>} inputs: slot -> manifest summary, directory ->
    artifacts, and one problem per directory that cannot be read (validation.read_source)."""
    sources, artifacts, problems = {}, {}, []
    for slot, path in stage_spec.paths.items():
        try:
            source = read_source(stage_spec, slot, path)
        except ManifestError as error:
            problems.append("inputs.%s: %s" % (slot, error))
            continue
        sources[slot] = source.summary()
        artifacts[path] = source.artifacts
    return sources, artifacts, problems


def _build_stages(stage_specs, recipe, reporter, apis):
    """stage id -> Stage object for some stages of a recipe. apis: the module APIs to use (pico, fitter,
    histogrammer, plotter, runner, tes_shapes; None: built here, and kept in apis for the next stages)."""
    stages = {}
    for stage_spec in stage_specs:
        name, stage_id = stage_spec.stage, stage_spec.id
        if name == 'production':
            settings = user_settings.production_settings()
            stages[stage_id] = ProductionStage(apis.get('pico') or _picoproducer(recipe, reporter, settings.overrides),
                                               settings)
        elif name == 'controlhists':
            apis['histogrammer'] = apis.get('histogrammer') or _histogrammer()
            stages[stage_id] = ControlHistsStage(apis['histogrammer'])
        elif name == 'controlplots':
            apis['plotter'] = apis.get('plotter') or _plotter()
            stages[stage_id] = ControlPlotsStage(apis['plotter'])
        elif name == 'shapes':
            apis['tes_shapes'] = apis.get('tes_shapes') or _tes_shapes()
            apis['histogrammer'] = apis.get('histogrammer') or _histogrammer()
            stages[stage_id] = ShapesStage(apis['tes_shapes'], samples_api=apis['histogrammer'])
        elif name == 'fit':
            apis['fitter'] = apis.get('fitter') or _fitter()
            stages[stage_id] = FitStage(apis['fitter'])
        elif name == 'python':
            stages[stage_id] = PythonStage(runner=apis.get('runner'))
        else:
            stages[stage_id] = STAGES[name]()
    return stages


def _rerun_rows(record, recipe, stage_id):
    """(start, production, rows) of a rerun of a run whose stages are those of `recipe` (a stage the record does
    not have yet is NEW): see rerun() and RerunPlan. Reads the run directory only. RerunError."""
    states = {stage_record.name: stage_record for stage_record in record.stages}
    specs = list(recipe.stages)
    ids = [stage_spec.id for stage_spec in specs]
    state = {stage_id: (states[stage_id].state if stage_id in states else StageState.NEW.value) for stage_id in ids}
    if stage_id is None:
        failed = [found for found in ids if state[found] == StageState.FAILED]
        if not failed:
            raise RerunError("Run %s has no failed stage (it is %s): name the stage to rerun from: taufw rerun %s "
                             "<id> (stages: %s)" % (record.run_id, record.state, record.run_dir, ", ".join(ids)))
        stage_id = failed[0]
    if stage_id not in ids:
        raise RerunError("Run %s has no stage %r to rerun from (stages: %s)" % (record.run_id, stage_id,
                                                                               ", ".join(ids)))
    index = ids.index(stage_id)
    for earlier in ids[:index]:
        if state[earlier] == StageState.FAILED:
            raise RerunError("Stage %s, before %s, is FAILED: rerun from it: taufw rerun %s %s"
                             % (earlier, stage_id, record.run_dir, earlier))
    production = next((i for i, stage_spec in enumerate(specs) if stage_spec.stage == 'production'), None)
    new_run = ("start a new run; it can reuse the finished stages of this one through {path: %s}"
               % (StageContext(run_dir=record.run_dir).stage_dir('<id>')))
    if production is not None and index <= production:
        stage_record = states.get(stage_id)
        if (index == production and stage_record is not None and state[stage_id] == StageState.FAILED
                and STAGES['production'].retry_state(stage_record) is not None):
            return stage_id, True, [{'stage': stage_id, 'state': state[stage_id], 'attempt':
                                     len(stage_record.attempts) + 1, 'archive': None}]
        why = ("production can run again only after its chunks failed max_tries times; it is %s%s"
               % (state[stage_id], " (%s)" % (stage_record.message) if stage_record and stage_record.message else "")
               if index == production else "it comes before production stage %s, which cannot run twice yet"
               % (ids[production]))
        raise RerunError("Stage %s (%s) cannot run again in this run: %s. To change it, %s"
                         % (stage_id, specs[index].stage, why, new_run))
    if not STAGES[specs[index].stage].retryable:
        raise RerunError("Stage %s (%s) cannot run again: %s" % (stage_id, specs[index].stage, new_run))
    rows = []
    for stage_spec in specs[index:]:
        context = StageContext(run_dir=record.run_dir, stage_id=stage_spec.id)
        attempt = _next_attempt(context.log_dir())
        left = _left_behind(context.log_dir(), context.stage_dir())
        rows.append({'stage': stage_spec.id, 'state': state[stage_spec.id], 'attempt': attempt,
                     'archive': os.path.join(LOGS_DIR_NAME, stage_spec.id, ATTEMPT_DIR % (attempt)) if left else None})
    return stage_id, False, rows


def _left_behind(log_dir, stage_dir):
    """Whether a stage left something to archive: its output directory, or files in its log directory besides the
    archives of earlier attempts."""
    return os.path.isdir(stage_dir) or (os.path.isdir(log_dir) and any(not ATTEMPT_NAME.match(name)
                                                                       for name in os.listdir(log_dir)))


def _next_attempt(log_dir):
    """The next free N of logs/<id>/attempt<N>/ (1 if there is none)."""
    numbers = [int(name[len('attempt'):]) for name in (os.listdir(log_dir) if os.path.isdir(log_dir) else ())
               if ATTEMPT_NAME.match(name)]
    return max(numbers, default=0) + 1


def _archive_attempt(log_dir, stage_dir, attempt):
    """Move what a failed attempt of a stage left to <log_dir>/attempt<N>/: the files of its log directory (not
    the archives of earlier attempts) and its output directory, as stage/. The stage then starts again in an empty
    output directory (the module APIs refuse a non-empty one). Returns the archive directory; RerunError if it
    exists already."""
    archive = os.path.join(log_dir, ATTEMPT_DIR % (attempt))
    if os.path.exists(archive):
        raise RerunError("%s exists already: choose another attempt number" % (archive))
    os.makedirs(archive)
    for name in sorted(os.listdir(log_dir)):
        if not ATTEMPT_NAME.match(name):
            shutil.move(os.path.join(log_dir, name), os.path.join(archive, name))
    if os.path.isdir(stage_dir):
        shutil.move(stage_dir, os.path.join(archive, ATTEMPT_STAGE_DIR))
    return archive


def _changes_text(files):
    """'sf/tauid.json added, steps/x.py changed' (a bundle_changes()); a copy that is back to its start says so."""
    return ", ".join("%s %s" % (path, change) for path, change in files.items()) or "changed and changed back"


def _jsonable(value):
    """The value as it reads back from JSON (tuples become lists)."""
    return json.loads(json.dumps(value))


def _picoproducer(recipe, reporter, overrides=None):
    """The PicoProducer of a recipe, its configuration with the keys the user config replaces (overrides,
    user_settings.py). It is imported only here, so the Framework can be imported (and tested) without
    PicoProducer and ROOT."""
    from TauFW.PicoProducer.api import PicoProducer
    return PicoProducer.from_config(recipe.pico_config_path, reporter=reporter.pico_reporter('production'),
                                    overrides=overrides)


def _fitter():
    """The Fitter API of the fit stage (imported only here; it does not import ROOT)."""
    from TauFW.Fitter.api import TauESID
    return TauESID()


def _histogrammer():
    """The API of the controlhists stage and the reader of the shapes stage's sample files: the Histogrammer's
    ControlHists (CL §21; imported only here; it does not import ROOT)."""
    from TauFW.Histogrammer.api import ControlHists
    return ControlHists()


def _tes_shapes():
    """The API of the shapes stage: the Histogrammer's TESShapes (CL §22 H3; imported only here; it does not import
    ROOT)."""
    from TauFW.Histogrammer.api import TESShapes
    return TESShapes()


def _plotter():
    """The API of the controlplots stage: the Plotter's ControlPlots (CL §21 S4; imported only here; it does not
    import ROOT)."""
    from TauFW.Plotter.api import ControlPlots
    return ControlPlots()
