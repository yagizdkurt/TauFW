# Author: Yagizhan Dinckurt (October 2026)
"""TauFW Framework: the single entry point that runs analysis pipelines from a recipe.

Purpose:  coordinate the stages of an analysis (production -> histograms -> fit). The Framework builds each
          stage's request from the recipe, keeps a persisted run record, and decides whether to wait, resubmit
          or move on. The stages' details stay in their packages (production: the PicoProducer API).
Inputs:   a recipe (Recipe or a .yml/.json file), the PicoProducer configuration it names.
Outputs:  a run directory taufw_runs/<name>_<YYYYmmdd-HHMMSS>/ with run.json (state) and run.log (messages);
          the stages' artifacts (production: merged pico tuples, recorded as TupleArtifacts in run.json).

Pipeline map:

    recipe ─▶ plan() ─▶ start() ─▶ advance() ─▶ … ─▶ advance() ─▶ DONE
                 │          │            │
              RunPlan   RunRecord     RunRecord (saved after every stage step)

    stage order: production ─▶ histograms (placeholder) ─▶ fit (placeholder)
    run model:   stepwise. start()/advance() move the run as far as they can (until a stage waits for the batch
                 system, fails, or is not implemented), save run.json and return. advance(wait=True) repeats
                 every `poll` seconds until the run stops waiting.

Public API:
  Framework.from_recipe(recipe_or_path, reporter) / Framework.from_record(record, reporter)
  plan, start, advance, run, status           pipelines
  load_run(run_dir)                           the RunRecord of a run directory
  RunPlan, RunSummary, StageSummary           records (bottom of this file)
"""

# ===== Imports =====
import os, json, time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple
from TauFW.Framework.recipe import Recipe
from TauFW.Framework.run_record import RunRecord
from TauFW.Framework.reporting import FrameworkReporter
from TauFW.Framework.stages import STAGES, StageState, StageNotImplemented, ProductionStage

__all__ = ['Framework', 'RunPlan', 'StagePlan', 'RunSummary', 'StageSummary', 'load_run',
           'RUN_LOG_NAME', 'DEFAULT_RUN_ROOT']


# ===== Constants =====
RUN_LOG_NAME     = "run.log"
DEFAULT_RUN_ROOT = "taufw_runs"
MAX_STEPS        = 8 # stage steps per advance() call (guards against a stage that never settles)


class Framework(object):
  """Runs the stages of one recipe.

  Pipelines:      plan(recipe=None)                         -> RunPlan     no side effects
                  start(recipe=None, run_root=None)         -> RunRecord   new run directory, then advance()
                  advance(record, wait=False, poll=600)     -> RunRecord   step the stages in order; saves run.json
                  run(recipe=None, run_root, wait, poll)    -> RunRecord   start(), then advance() while waiting
                  status(record)                            -> RunSummary  read-only: recorded + live state
  Stage dispatch: _advance_stages, _advance_stage, _apply, _stage_for
  Construction:   from_recipe(recipe_or_path, reporter, pico); from_record(record, reporter, pico);
                  Framework(recipe, stages, reporter, files, sleep, clock)
  """

  # ===== Pipelines =====

  def plan(self,recipe=None):
    """What each stage would do, without side effects. Placeholder stages are listed as not implemented."""
    recipe = recipe or self.recipe
    plans  = [ ]
    for spec in recipe.stages:
      try:
        plans.append(StagePlan(stage=spec.stage,plan=self._stage_for(spec.stage).plan(spec.spec)))
      except StageNotImplemented as err:
        plans.append(StagePlan(stage=spec.stage,plan=None,note=str(err)))
    return RunPlan(name=recipe.name,stages=tuple(plans))

  def start(self,recipe=None,run_root=None):
    """Create the run directory and run.json, then advance() once.
    Side effects: creates <run_root>/<name>_<time>/ with run.json and run.log; whatever the first stage step does
    (production: submits jobs)."""
    recipe = recipe or self.recipe
    record = RunRecord.create(recipe,run_root or DEFAULT_RUN_ROOT,pico_config=self._pico_config(recipe),
                              now=self.clock())
    self.files.make_directory(record.run_dir)
    self.reporter.attach_log(os.path.join(record.run_dir,RUN_LOG_NAME))
    self.reporter.header("TauFW run %s"%(record.run_id))
    self.reporter.message("Run directory: %s"%(record.run_dir))
    record.save(self.files)
    return self.advance(record)

  def advance(self,record,wait=False,poll=600):
    """Step each stage in order until one waits for the batch system, fails or is not implemented; save run.json
    after every step. With wait=True, repeat every `poll` seconds while the run is waiting.
    Side effects: the stages' (production: submit, resubmit, merge); run.json and run.log."""
    self.reporter.attach_log(os.path.join(record.run_dir,RUN_LOG_NAME))
    while True:
      self._advance_stages(record)
      record.save(self.files)
      self.reporter.message("Run %s: %s"%(record.run_id,record.state))
      if not (wait and record.state=='WAITING'):
        return record
      self.reporter.message("Waiting %s s before the next check..."%(poll))
      self.sleep(poll)

  def run(self,recipe=None,run_root=None,wait=False,poll=600):
    """start(), and with wait=True keep advancing until the run stops waiting."""
    record = self.start(recipe,run_root)
    if wait and record.state=='WAITING':
      record = self.advance(record,wait=True,poll=poll)
    return record

  def status(self,record):
    """Recorded state of every stage, plus its live status where the stage can check it (production: the
    PicoProducer status of the jobs). Read-only: nothing is saved or submitted."""
    summaries = [ ]
    for spec in self._recipe_of(record).stages:
      srec = record.stage(spec.stage)
      try:
        live = self._stage_for(spec.stage).status(spec.spec,srec)
      except StageNotImplemented:
        live = None
      summaries.append(StageSummary(stage=spec.stage,state=srec.state,attempt=srec.attempt,message=srec.message,
                                    live=live))
    return RunSummary(run_id=record.run_id,state=record.state,run_dir=record.run_dir,stages=tuple(summaries))

  # ===== Stage dispatch =====

  def _advance_stages(self,record):
    """Advance the stages in recipe order; stop at the first one that waits, fails or is not implemented."""
    for spec in self._recipe_of(record).stages:
      srec = record.stage(spec.stage)
      for step in range(MAX_STEPS):
        state = StageState(srec.state)
        if state is StageState.DONE:
          break # next stage
        if state.terminal or (step>0 and state.waiting):
          return
        try:
          outcome = self._advance_stage(spec,srec)
        except Exception:
          record.save(self.files) # keep the error in the stage's history; the state is unchanged
          raise
        self._apply(srec,outcome)
        record.save(self.files)
        if outcome.state.waiting:
          return
      else:
        return

  def _advance_stage(self,spec,srec):
    """One step of one stage. An exception is recorded in the stage's history (state unchanged) and re-raised."""
    stage = self._stage_for(spec.stage)
    if srec.request is None and hasattr(spec.spec,'request_dict'):
      srec.request = spec.spec.request_dict()
    self.reporter.header("Stage %s (%s)"%(spec.stage,srec.state))
    try:
      return stage.advance(spec.spec,srec,self.reporter)
    except Exception as err:
      srec.log('error',"%s: %s"%(type(err).__name__,err),time=self._now())
      self.reporter.warning("Stage %s raised %s: %s"%(spec.stage,type(err).__name__,err))
      raise

  def _apply(self,srec,outcome):
    """Record an outcome in a stage record (dicts as they read back from run.json: lists, not tuples)."""
    srec.state   = outcome.state.value
    srec.message = outcome.message
    if outcome.attempt is not None:
      srec.attempt = outcome.attempt
    if outcome.submission is not None:
      srec.submissions.append(_jsonable(outcome.submission))
    if outcome.status is not None:
      srec.last_status = _jsonable(outcome.status)
    if outcome.artifacts:
      srec.artifacts = _jsonable(list(outcome.artifacts))
    srec.log(outcome.event or outcome.state.value.lower(),outcome.message,time=self._now())
    report = self.reporter.warning if outcome.state is StageState.FAILED else self.reporter.message
    report("Stage %s: %s%s"%(srec.name,outcome.state.value," - "+outcome.message if outcome.message else ""))

  def _stage_for(self,name):
    if name not in self.stages:
      raise KeyError("No stage %r in this Framework (stages: %s)"%(name,', '.join(self.stages)))
    return self.stages[name]

  def _recipe_of(self,record):
    """The recipe stored in a run record (a run always continues with the recipe it started with)."""
    return Recipe.from_dict(record.recipe,source=record.run_id)

  def _pico_config(self,recipe):
    """Path and snapshot of the production stage's PicoProducer configuration, for run.json."""
    stage  = self.stages.get('production')
    config = getattr(getattr(stage,'pico',None),'config',None)
    return {'path': getattr(config,'_path',recipe.pico_config),
            'snapshot': dict(getattr(config,'_dict',{ })) or None}

  def _now(self):
    return self.clock().strftime("%Y-%m-%d %H:%M:%S")

  # ===== Construction & lifecycle =====

  @classmethod
  def from_recipe(cls,recipe,reporter=None,pico=None):
    """recipe: a Recipe or the path of a recipe file. pico: the PicoProducer to use (default: built from the
    recipe's pico.config, reporting through the Framework's reporter). Reads files only."""
    if isinstance(recipe,str):
      recipe = Recipe.load(recipe)
    reporter = reporter or FrameworkReporter()
    stages   = { }
    for spec in recipe.stages:
      if spec.stage=='production':
        stages['production'] = ProductionStage(pico or _picoproducer(recipe,reporter))
      else:
        stages[spec.stage] = STAGES[spec.stage]()
    return cls(recipe,stages,reporter=reporter)

  @classmethod
  def from_record(cls,record,reporter=None,pico=None):
    """A Framework for continuing a run, with the recipe stored in its run.json."""
    return cls.from_recipe(Recipe.from_dict(record.recipe,source=record.run_id),reporter=reporter,pico=pico)

  def __init__(self,recipe,stages,reporter=None,files=None,sleep=None,clock=None):
    """Explicit services; construction never writes, submits or changes the working directory."""
    self.recipe   = recipe
    self.stages   = dict(stages)
    self.reporter = reporter or FrameworkReporter()
    self.files    = files or _fileio()
    self.sleep    = sleep or time.sleep
    self.clock    = clock or datetime.now

  def close(self):
    """Nothing is held open; kept for `with Framework.from_recipe(...) as fw:`."""

  def __enter__(self):
    return self

  def __exit__(self,*exc):
    self.close()
    return False

  def __repr__(self):
    return "<Framework %r: %s>"%(self.recipe.name,' -> '.join(s.stage for s in self.recipe.stages))


# ===== Records =====

@dataclass(frozen=True)
class StagePlan:
  """plan() of one stage: the stage's own plan object (production: JobPlan), or None with a note."""
  stage: str
  plan:  object
  note:  str = ""


@dataclass(frozen=True)
class RunPlan:
  name:   str
  stages: Tuple[StagePlan, ...]


@dataclass(frozen=True)
class StageSummary:
  """status() of one stage: recorded state, attempt and message; live: the stage's live status (or None)."""
  stage:   str
  state:   str
  attempt: int
  message: str
  live:    Optional[object] = None


@dataclass(frozen=True)
class RunSummary:
  run_id:  str
  state:   str
  run_dir: str
  stages:  Tuple[StageSummary, ...]


# ===== Helpers =====

def load_run(run_dir):
  """The RunRecord of a run directory."""
  return RunRecord.load(run_dir)


def _jsonable(value):
  """The value as it reads back from JSON (tuples become lists)."""
  return json.loads(json.dumps(value))


def _picoproducer(recipe,reporter):
  """The PicoProducer of a recipe, imported on first use (the Framework imports without PicoProducer)."""
  from TauFW.PicoProducer.api import PicoProducer
  return PicoProducer.from_config(recipe.pico_config,reporter=reporter.pico_reporter('production'))


def _fileio():
  from TauFW.Utilities.FIO import FileIO
  return FileIO()
