# Author: Yagizhan Dinckurt (October 2026)
"""Production stage: NanoAOD -> pico tuples on the batch system, through the public PicoProducer API.

# ===== Pipeline =====  (ProductionStage.advance, one step per call)

    NEW        ─▶ plan + submit                        ─▶ SUBMITTED   (attempt 1)
    SUBMITTED  ─┐
    WAITING    ─┴▶ status ─▶ decide_next():  wait      ─▶ WAITING
                                             resubmit  ─▶ SUBMITTED   (attempt + 1)
                                             merge     ─▶ MERGING
                                             fail      ─▶ FAILED
    MERGING    ─▶ merge(clean=merge.clean)             ─▶ DONE        (TupleArtifact per sample)

Policy comes from the recipe: max_tries (default 3), merge.clean (default false), merge.force (default false).
decide_next() is pure, so the policy is unit-tested without a batch system.

Inputs:  ProductionSpec (recipe options), the stage's record (state, attempt), a PicoProducer.
Outputs: StageOutcome; through PicoProducer: job files, batch jobs, merged tuples.

Public API:
  ProductionStage(pico)                  the stage
  ProductionSpec, SplitSpec, MergeSpec   recipe options
  decide_next(counts, attempt, max_tries) -> (Action, reason)
  Action, StatusCounts, counts(status)
"""

# ===== Imports =====
from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple, Optional, Tuple
from TauFW.Framework.stages.base import Stage, StageState, StageOutcome

__all__ = ['ProductionStage', 'ProductionSpec', 'SplitSpec', 'MergeSpec', 'decide_next', 'Action', 'StatusCounts',
           'counts']


# ===== Decisions (pure) =====

class Action(str, Enum):
  WAIT     = 'wait'
  RESUBMIT = 'resubmit'
  MERGE    = 'merge'
  FAIL     = 'fail'


class StatusCounts(NamedTuple):
  """The numbers decide_next() needs from a StageStatus."""
  nsamples: int  # samples with a job config
  npending: int  # chunks queued or running
  nfailed:  int  # chunks to resubmit (failed or missing)
  complete: bool # every sample can be merged


def decide_next(counts,attempt,max_tries):
  """What to do after a status check. Returns (Action, reason).
    no samples                      -> FAIL      (no job configs: nothing was submitted)
    complete                        -> MERGE
    chunks pending                  -> WAIT      (resubmit failed chunks only when nothing runs any more)
    failed, attempt < max_tries     -> RESUBMIT
    failed, attempt >= max_tries    -> FAIL
  """
  if counts.nsamples==0:
    return Action.FAIL, "no job configs found for the requested samples"
  if counts.complete:
    return Action.MERGE, "all chunks succeeded"
  if counts.npending>0:
    return Action.WAIT, "%d chunk(s) pending or running"%(counts.npending)
  if counts.nfailed>0 and attempt<max_tries:
    return Action.RESUBMIT, "%d chunk(s) failed or missing; resubmitting (try %d of %d)"%(counts.nfailed,attempt+1,max_tries)
  if counts.nfailed>0:
    return Action.FAIL, "%d chunk(s) still failed or missing after %d tries"%(counts.nfailed,attempt)
  return Action.WAIT, "waiting for the job output"


def counts(status):
  """StatusCounts of a PicoProducer StageStatus."""
  return StatusCounts(nsamples=len(status.samples),npending=status.npending,nfailed=status.nfailed,
                      complete=status.complete)


# ===== Stage =====

class ProductionStage(Stage):
  """Produce pico tuples with PicoProducer. pico: a PicoProducer, or any object with the same methods
  (request, plan, submit, resubmit, status, merge, run_local)."""
  name = 'production'

  # ===== Pipeline =====

  def advance(self,spec,record,reporter):
    """One step from record.state (see the module docstring)."""
    state   = StageState(record.state)
    request = self.request(spec)
    if state is StageState.NEW:
      return self._submit(request)
    if state.waiting:
      return self._check(spec,record,request)
    if state is StageState.MERGING:
      return self._merge(spec,request)
    return StageOutcome(state,"nothing to do (%s)"%(state.value))

  def plan(self,spec):
    """JobPlan of the first submission (nothing is written)."""
    return self.pico.plan(self.request(spec))

  def status(self,spec,record):
    """Live StageStatus (read-only), or None before the first submission."""
    if StageState(record.state) is StageState.NEW:
      return None
    return self.pico.status(self.request(spec))

  def run_local(self,spec,maxevts=100,nfiles=1):
    """Quick local test of the first sample per era and channel (no run record)."""
    return self.pico.run_local(self.request(spec,maxevts=maxevts,nfiles=nfiles,nsamples=1))

  # ===== Steps =====

  def _submit(self,request):
    plan = self.pico.plan(request)
    if not plan.samples:
      return StageOutcome(StageState.FAILED,"no samples match the request","failed")
    submission = self.pico.submit(request)
    message    = "submitted %d of %d sample(s)"%(submission.nsubmitted,len(plan.samples))
    return StageOutcome(StageState.SUBMITTED,message,"submitted",attempt=1,submission=submission.to_dict())

  def _check(self,spec,record,request):
    status = self.pico.status(request)
    action, reason = decide_next(counts(status),record.attempt,spec.max_tries)
    sdict  = status.to_dict()
    if action is Action.WAIT:
      return StageOutcome(StageState.WAITING,reason,"waiting",status=sdict)
    if action is Action.RESUBMIT:
      submission = self.pico.resubmit(request)
      return StageOutcome(StageState.SUBMITTED,reason,"resubmitted",attempt=record.attempt+1,
                          submission=submission.to_dict(),status=sdict)
    if action is Action.MERGE:
      return StageOutcome(StageState.MERGING,reason,"complete",status=sdict)
    return StageOutcome(StageState.FAILED,reason,"failed",status=sdict)

  def _merge(self,spec,request):
    report    = self.pico.merge(request,clean=spec.merge.clean,force=spec.merge.force)
    artifacts = tuple(a.to_dict() for a in report.artifacts)
    if report.invalid:
      reasons = "; ".join("%s: %s"%(name,reason) for name, reason in report.invalid)
      return StageOutcome(StageState.FAILED,"merged tuple(s) failed validation: %s"%(reasons),"failed",artifacts=artifacts)
    if report.refused:
      return StageOutcome(StageState.WAITING,"merge refused for %s; checking again"%(', '.join(report.refused)),
                          "refused",artifacts=artifacts)
    return StageOutcome(StageState.DONE,"merged %d tuple(s)"%(len(artifacts)),"merged",artifacts=artifacts)

  # ===== Construction =====

  def request(self,spec,**overrides):
    """The PicoProducer request of a spec."""
    return self.pico.request(**dict(spec.request_dict(),**overrides))

  def __init__(self,pico):
    self.pico = pico


# ===== Recipe options =====

@dataclass(frozen=True)
class SplitSpec:
  """How to split samples into jobs: files per job, or events per job (None: sample, then configuration)."""
  nfilesperjob: Optional[int] = None
  maxevts:      Optional[int] = None


@dataclass(frozen=True)
class MergeSpec:
  """clean: remove job files and job output after a validated merge; force: merge incomplete samples too."""
  clean: bool = False
  force: bool = False


@dataclass(frozen=True)
class ProductionSpec:
  """Recipe options of a production stage (see Framework/README.md)."""
  eras:         Tuple[str, ...]
  channels:     Tuple[str, ...]
  samples:      Tuple[str, ...] = ()        # glob patterns of sample names
  vetoes:       Tuple[str, ...] = ()
  dtypes:       Tuple[str, ...] = ('mc','data','embed')
  dasfilters:   Tuple[str, ...] = ()
  dasvetoes:    Tuple[str, ...] = ()
  tag:          str = ""
  extraopts:    Tuple[str, ...] = ()        # KEY=VALUE module options
  split:        SplitSpec = field(default_factory=SplitSpec)
  queue:        Optional[str] = None
  time:         Optional[str] = None
  batchopts:    Optional[str] = None
  prefetch:     bool = False
  preselect:    Optional[str] = None
  dasfiles:     bool = False
  checkdas:     bool = False
  checkevts:    bool = True
  checkexpevts: Optional[bool] = None
  ncores:       int = 4
  verbosity:    int = 0
  max_tries:    int = 3
  merge:        MergeSpec = field(default_factory=MergeSpec)
  _nested = {'split': SplitSpec, 'merge': MergeSpec}

  def __post_init__(self):
    for key in ('eras','channels'):
      value = getattr(self,key)
      if isinstance(value,str):
        object.__setattr__(self,key,(value,))
      if not getattr(self,key):
        raise ValueError("production: '%s' must not be empty"%(key))
    if self.max_tries<1:
      raise ValueError("production: 'max_tries' must be at least 1")

  def request_dict(self):
    """Fields of PicoProducer's JobRequest. The tag gets its leading '_' as in pico.py."""
    tag = self.tag if not self.tag or self.tag.startswith('_') else '_'+self.tag
    return dict(
      eras=list(self.eras), channels=list(self.channels), tag=tag, dtypes=list(self.dtypes),
      samples=list(self.samples), vetoes=list(self.vetoes), dasfilters=list(self.dasfilters),
      dasvetoes=list(self.dasvetoes), extraopts=list(self.extraopts), prefetch=self.prefetch,
      preselect=self.preselect, nfilesperjob=self.split.nfilesperjob or -1, maxevts=self.split.maxevts,
      dasfiles=self.dasfiles, queue=self.queue, time=self.time, batchopts=self.batchopts,
      checkdas=self.checkdas, checkevts=self.checkevts, checkexpevts=self.checkexpevts, ncores=self.ncores,
      verbosity=self.verbosity,
    )

ProductionStage.Spec = ProductionSpec
