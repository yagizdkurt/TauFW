# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""TauFW Framework: the single entry point that runs an analysis pipeline from a recipe.

Purpose:  run the stages of an analysis (production -> histograms -> fit) one after the other. The Framework
          gives each stage its options from the recipe, keeps the run's state in run.json, and decides whether
          to wait for the batch system or to move on. What a stage really does stays in its own package (the
          production stage, for example, calls the PicoProducer API).
Inputs:   a recipe (a Recipe, an analysis bundle directory, or a .yml/.json file) and the files it names.
Outputs:  a run directory taufw_runs/<name>_<YYYYmmdd-HHMMSS>/ with run.json (the state), run.log (the messages)
          and bundle/ (a copy of the bundle files the run uses), plus what the stages produce (for production:
          merged pico tuples, listed in run.json).

Pipeline map:

    recipe ─▶ plan() ─▶ start() ─▶ advance() ─▶ … ─▶ advance() ─▶ DONE
                 │          │            │
              RunPlan   RunRecord     RunRecord (saved after every stage step)

    stage order: production ─▶ plots ─▶ histograms ─▶ fit   (a recipe may leave stages out)
                 python steps (a Python file of the bundle) may be anywhere in between, any number of times.
                 production runs on the batch system (PicoProducer API); plots, histograms and fit run their
                 module's scripts locally (Plotter and Fitter APIs), python steps run step_runner.py; these
                 finish inside one advance() call.
    run model:   stepwise. start() and advance() move the run as far as they can (until a stage waits for the
                 batch system, fails, is not ready or is not implemented), save run.json and return.
                 advance(wait=True) repeats this every `poll` seconds until the run no longer waits.
    stage data:  every stage gets a StageContext: the run directory (its logs go to <run_dir>/<stage id>/),
                 the artifacts of the DONE stages before it (production's tuples, the histograms' shapes), the
                 run's PicoProducer config and the bundle directory its path options are resolved against.
    bundle:      start() copies the bundle files the recipe uses to <run_dir>/bundle/; the run reads them from
                 there, so later edits of the bundle never change a run (see bundle.py).

Public API:
  Framework.from_recipe(recipe_or_path, reporter, pico, fitter, plotter) / Framework.from_record(record, ...)
  plan, start, advance, run, status           pipelines
  make_bundle(target)                         a new analysis bundle with copies of the module configs used
  load_run(run_dir)                           the RunRecord of a run directory
  RunPlan, RunSummary, StageSummary           records (bottom of this file)
"""
import os, json, time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple
from TauFW.Framework.defaults import (DEFAULT_RUN_ROOT, RUN_LOG_NAME, DEFAULT_POLL_SECONDS, BUNDLE_DIR_NAME,
                                      timestamp, default_file_io)
from TauFW.Framework.bundle import path_rows, snapshot, make_bundle
from TauFW.Framework.recipe import Recipe
from TauFW.Framework.run_record import RunRecord, RunState
from TauFW.Framework.reporting import FrameworkReporter
from TauFW.Framework.stages import (STAGES, StageState, StageContext, StageNotImplemented, PreflightError,
                                    ProductionStage, PlotStage, HistogramStage, FitStage, PythonStage)

__all__ = ['Framework', 'RunPlan', 'StagePlan', 'RunSummary', 'StageSummary', 'load_run',
           'RUN_LOG_NAME', 'DEFAULT_RUN_ROOT']


# =============================================================================
# ================================= CONSTANTS =================================


MAX_STEPS = 8  # most steps one stage may take in one advance() call (a safety net against a stage that never settles)


class Framework:
    """Runs the stages of one recipe.

    Pipelines:      plan(recipe=None)                         -> RunPlan     changes nothing
                    start(recipe=None, run_root=None)         -> RunRecord   new run directory, then advance()
                    advance(record, wait=False, poll=600)     -> RunRecord   step the stages in order; saves run.json
                    run(recipe=None, run_root, wait, poll)    -> RunRecord   start(), then advance() while waiting
                    status(record)                            -> RunSummary  read-only: saved and live state
                    make_bundle(target, name)                 -> paths       new bundle from this recipe
    Stage dispatch: _advance_stages, _advance_stage, _apply, _stage_for
    Construction:   from_recipe(recipe_or_path, reporter, pico, fitter, plotter); from_record(record, ...);
                    Framework(recipe, stages, reporter, files, sleep, clock)

    Naming used below: a `stage_spec` is one stage of the recipe (a StageSpec: its name, id and options), and a
    `stage_record` is the saved state of that stage in run.json (a StageRecord, named by the stage id). Stage
    objects, records and upstream artifacts are all keyed by the stage id.
    """

    # =========================================================================
    # =============================== PIPELINES ===============================

    def plan(self, recipe=None):
        """What each stage would do, without changing anything. Placeholder stages are listed as not implemented.
        Each stage sees the artifacts that the stages before it plan to make (e.g. the fit sees the planned
        shapes), so the plan of a whole recipe is complete before anything runs."""
        recipe = recipe or self.recipe
        plans, planned = [], {}
        for stage_spec in recipe.stages:
            context = StageContext(upstream=dict(planned), pico_config=recipe.pico_config_path,
                                   bundle_dir=recipe.bundle_dir, stage_id=stage_spec.id)
            paths = path_rows(stage_spec.spec, recipe.bundle_dir)
            try:
                stage_plan = self._stage_for(stage_spec.id).plan(stage_spec.spec, context)
                plans.append(StagePlan(stage=stage_spec.id, plan=stage_plan, paths=paths))
                planned[stage_spec.id] = tuple(getattr(stage_plan, 'artifacts', ()) or ())
            except (StageNotImplemented, PreflightError) as err:  # placeholder, or cannot be planned yet
                plans.append(StagePlan(stage=stage_spec.id, plan=None, note=str(err), paths=paths))
        return RunPlan(name=recipe.name, stages=tuple(plans), pico_config=recipe.pico_config_path,
                       bundle_dir=recipe.bundle_dir)

    def start(self, recipe=None, run_root=None):
        """Create the run directory, copy the bundle files and write run.json, then call advance() once.
        Side effects: creates <run_root>/<name>_<time>/ with run.json, run.log and bundle/, and runs the first
        stage steps (the production stage, for example, submits its jobs)."""
        recipe = recipe or self.recipe
        record = RunRecord.create(recipe, run_root or DEFAULT_RUN_ROOT, pico_config=self._pico_config(recipe),
                                  now=self.clock())
        if recipe.bundle_dir:  # first: a bundle that is too large stops here, before the run directory exists
            record.bundle = snapshot(recipe, os.path.join(record.run_dir, BUNDLE_DIR_NAME))
        self.files.make_directory(record.run_dir)
        self.reporter.attach_log(os.path.join(record.run_dir, RUN_LOG_NAME))
        self.reporter.header("TauFW run %s" % (record.run_id))
        self.reporter.message("Run directory: %s" % (record.run_dir))
        record.save(self.files)
        return self.advance(record)

    def advance(self, record, wait=False, poll=DEFAULT_POLL_SECONDS):
        """Step the stages in order until one waits for the batch system, fails or is not implemented. run.json is
        saved after every step. With wait=True, this is repeated every `poll` seconds while the run is waiting.
        Side effects: whatever the stages do (production: submit, resubmit, merge); run.json and run.log."""
        self.reporter.attach_log(os.path.join(record.run_dir, RUN_LOG_NAME))
        while True:
            self._advance_stages(record)
            record.save(self.files)
            self.reporter.message("Run %s: %s" % (record.run_id, record.state))
            if not (wait and record.state == RunState.WAITING):
                return record
            self.reporter.message("Waiting %s s before the next check..." % (poll))
            self.sleep(poll)

    def run(self, recipe=None, run_root=None, wait=False, poll=DEFAULT_POLL_SECONDS):
        """start(), and with wait=True keep advancing until the run no longer waits."""
        record = self.start(recipe, run_root)
        if wait and record.state == RunState.WAITING:
            record = self.advance(record, wait=True, poll=poll)
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
        """Write a new analysis bundle at `target` from this recipe: recipe.yml, copies of the module configs its
        stages use (next to recipe.yml) with the recipe pointing at them, and steps/example.py.
        name: the new recipe's name (default: the bundle directory's name). Returns the copied config paths.
        Raises BundleError if `target` exists."""
        sources = {}
        for stage_spec in self.recipe.stages:
            stage = self._stage_for(stage_spec.id)
            for option, value, _, where in path_rows(stage_spec.spec, self.recipe.bundle_dir):
                found = stage.config_file(value) if where == 'module' and hasattr(stage, 'config_file') else None
                if found and os.path.isfile(found):
                    sources[(stage_spec.id, option, value)] = (stage.group, found)
        data = self.recipe.to_dict()
        data['name'] = name or os.path.basename(os.path.abspath(target))
        return make_bundle(data, sources, target, self.files)

    # =========================================================================
    # ============================ STAGE DISPATCH =============================

    def _advance_stages(self, record):
        """Advance the stages in recipe order, and stop where the run cannot go further for now.

        A stage may take several steps in one call (for example MERGING -> DONE, then the next stage starts).
        For each stage, in order:
          - DONE:                     go on with the next stage.
          - FAILED, NOT_IMPLEMENTED:  stop; this stage can never move again.
          - waiting for jobs:         take one step (a status check). If the stage still waits, stop: advance()
                                      must be called again later.
          - not ready (PreflightError): stop; the stage keeps its state, the reason is in its message and
                                      history, and advance() can be called again once it is fixed.
          - otherwise:                take a step and look again.
        A stage that has not settled after MAX_STEPS steps also stops the call (a safety net).
        run.json is saved after every step, so a crash never loses a step that was done.
        """
        for stage_spec in self._recipe_of(record).stages:
            stage_record = record.stage(stage_spec.id)
            for step in range(MAX_STEPS):
                state = StageState(stage_record.state)
                if state is StageState.DONE:
                    break  # this stage is finished: continue with the next stage
                if state.terminal:
                    return  # FAILED or NOT_IMPLEMENTED: the later stages cannot start
                if step > 0 and state.waiting:
                    return  # already checked once in this call: come back later
                try:
                    outcome = self._advance_stage(stage_spec, stage_record, self._context(record, stage_spec))
                except PreflightError:
                    record.save(self.files)  # not ready: the reason is in the stage's message and history
                    return
                except Exception:
                    record.save(self.files)  # keep the error in the stage's history; the state is unchanged
                    raise
                self._apply(stage_record, outcome)
                record.save(self.files)
                if outcome.state.waiting:
                    return  # the stage now waits for the batch system: come back later
            else:
                return  # MAX_STEPS reached without settling: stop here

    def _advance_stage(self, stage_spec, stage_record, context):
        """One step of one stage. If the stage raises an error, the error is written to the stage's history (the
        state is not changed) and raised again. A PreflightError (environment not ready) also becomes the stage's
        message."""
        stage = self._stage_for(stage_spec.id)
        if stage_record.request is None and hasattr(stage_spec.spec, 'request_dict'):
            stage_record.request = stage_spec.spec.request_dict()  # save the request once, for run.json
        self.reporter.header("Stage %s (%s)" % (stage_spec.id, stage_record.state))
        try:
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

    def _context(self, record, stage_spec):
        """The StageContext of one stage: the run directory, the artifacts of the DONE stages before it, the run's
        PicoProducer config and bundle copy."""
        recipe = self._recipe_of(record)
        upstream = {}
        for earlier in recipe.stages:
            if earlier.id == stage_spec.id:
                break
            earlier_record = record.stage(earlier.id)
            if StageState(earlier_record.state) is StageState.DONE:
                upstream[earlier.id] = tuple(earlier_record.artifacts)
        return StageContext(run_dir=record.run_dir, upstream=upstream,
                            pico_config=recipe.pico_config_path or (record.pico_config or {}).get('path'),
                            bundle_dir=recipe.bundle_dir, stage_id=stage_spec.id)

    def _stage_for(self, stage_id):
        """The Stage object for a stage id."""
        if stage_id not in self.stages:
            raise KeyError("No stage %r in this Framework (stages: %s)" % (stage_id, ', '.join(self.stages)))
        return self.stages[stage_id]

    def _recipe_of(self, record):
        """The recipe saved in a run record, with the run's copy of the bundle. A run always continues with the
        recipe and bundle files it started with, even if they were changed since."""
        return _run_recipe(record)

    def _pico_config(self, recipe):
        """The path and a snapshot (copy) of the PicoProducer configuration of the production stage, for run.json.
        If there is no production stage, or its PicoProducer has no loaded configuration (e.g. a fake one in the
        tests), the path from the recipe is used and the snapshot is None."""
        stage = self.stages.get('production')
        config = getattr(getattr(stage, 'pico', None), 'config', None)
        return {'path': getattr(config, '_path', recipe.pico_config_path),
                'snapshot': dict(getattr(config, '_dict', {})) or None}

    def _now(self):
        return timestamp(self.clock())

    # =========================================================================
    # ======================= CONSTRUCTION & LIFECYCLE ========================

    @classmethod
    def from_recipe(cls, recipe, reporter=None, pico=None, fitter=None, plotter=None, runner=None):
        """recipe: a Recipe, or the path of a recipe file or analysis bundle directory.
        pico:    the PicoProducer to use (default: one built from the recipe's pico.config, reporting through the
                 Framework's reporter).
        fitter:  the Fitter API of the histograms and fit stages (default: TauFW.Fitter.api.TauESID()).
        plotter: the Plotter API of the plots stage (default: TauFW.Plotter.api.ControlPlots()).
        runner:  the ProcessRunner of the python steps (default: new).
        Only the APIs of the stages in the recipe are built. Only reads files."""
        if isinstance(recipe, str):
            recipe = Recipe.load(recipe)
        reporter = reporter or FrameworkReporter()
        stages = {}
        for stage_spec in recipe.stages:
            name, stage_id = stage_spec.stage, stage_spec.id
            if name == 'production':
                stages[stage_id] = ProductionStage(pico or _picoproducer(recipe, reporter))
            elif name == 'plots':
                stages[stage_id] = PlotStage(plotter or _plotter())
            elif name in ('histograms', 'fit'):
                fitter = fitter or _fitter()
                stages[stage_id] = HistogramStage(fitter) if name == 'histograms' else FitStage(fitter)
            elif name == 'python':
                stages[stage_id] = PythonStage(runner=runner)
            else:
                stages[stage_id] = STAGES[name]()
        return cls(recipe, stages, reporter=reporter)

    @classmethod
    def from_record(cls, record, reporter=None, pico=None, fitter=None, plotter=None, runner=None):
        """A Framework that continues a run, with the recipe saved in its run.json and the run's bundle copy."""
        return cls.from_recipe(_run_recipe(record), reporter=reporter, pico=pico, fitter=fitter, plotter=plotter,
                               runner=runner)

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
    stage: the stage id; paths: (option, value as written, resolved path, 'bundle'|'module'|'absolute')."""
    stage: str
    plan:  object
    note:  str = ""
    paths: Tuple[Tuple[str, str, str, str], ...] = ()


@dataclass(frozen=True)
class RunPlan:
    """plan() of a whole recipe: one StagePlan per stage, the PicoProducer config path and the bundle directory."""
    name:        str
    stages:      Tuple[StagePlan, ...]
    pico_config: Optional[str] = None
    bundle_dir:  Optional[str] = None


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


def _run_recipe(record):
    """The recipe saved in run.json, resolved against the run's bundle copy (<run_dir>/bundle)."""
    return Recipe.from_dict(record.recipe, source=record.run_id,
                            bundle_dir=os.path.join(record.run_dir, BUNDLE_DIR_NAME))


def _jsonable(value):
    """The value as it reads back from JSON (tuples become lists)."""
    return json.loads(json.dumps(value))


def _picoproducer(recipe, reporter):
    """The PicoProducer of a recipe. It is imported only here, so the Framework can be imported (and tested)
    without PicoProducer and ROOT."""
    from TauFW.PicoProducer.api import PicoProducer
    return PicoProducer.from_config(recipe.pico_config_path, reporter=reporter.pico_reporter('production'))


def _fitter():
    """The Fitter API of the histograms and fit stages (imported only here; it does not import ROOT)."""
    from TauFW.Fitter.api import TauESID
    return TauESID()


def _plotter():
    """The Plotter API of the plots stage (imported only here; it does not import ROOT)."""
    from TauFW.Plotter.api import ControlPlots
    return ControlPlots()
