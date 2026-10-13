# Author: Yagizhan Dinckurt (October 2026)
"""Production stage: turn NanoAOD into pico tuples on the batch system, through the public PicoProducer API.

Each call of ProductionStage.advance() takes one step, starting from the state saved in run.json:

    NEW        ─▶ plan + submit                        ─▶ SUBMITTED   (attempt 1)
    SUBMITTED  ─┐
    WAITING    ─┴▶ status ─▶ decide_next():  wait      ─▶ WAITING
                                             resubmit  ─▶ SUBMITTED   (attempt + 1)
                                             merge     ─▶ MERGING
                                             fail      ─▶ FAILED
    MERGING    ─▶ merge(clean=merge.clean)             ─▶ DONE        (one TupleArtifact per sample)

The policy is set in the recipe: max_tries (default 3), merge.clean (default false), merge.force (default false).
decide_next() only looks at numbers and changes nothing, so the policy is tested without a batch system.

Inputs:  ProductionSpec (the recipe options), the stage's record (state, attempt), a PicoProducer.
Outputs: a StageOutcome. Through PicoProducer: job files, batch jobs and merged tuples.

Public API:
  ProductionStage(pico)                  the stage
  ProductionSpec, SplitSpec, MergeSpec   recipe options
  decide_next(counts, attempt, max_tries) -> (Action, reason)
  Action, StatusCounts, counts(status)
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple, Optional, Tuple
from TauFW.Framework.stages.base import Stage, StageState, StageOutcome

__all__ = ['ProductionStage', 'ProductionSpec', 'SplitSpec', 'MergeSpec', 'decide_next', 'Action', 'StatusCounts',
           'counts']


# =============================================================================
# ================================= DECISIONS =================================


class Action(str, Enum):
    """What the production stage does after checking its jobs."""
    WAIT     = 'wait'
    RESUBMIT = 'resubmit'
    MERGE    = 'merge'
    FAIL     = 'fail'


class StatusCounts(NamedTuple):
    """The numbers decide_next() needs from a PicoProducer StageStatus."""
    nsamples: int   # samples that have a job config
    npending: int   # chunks (jobs) queued or running
    nfailed:  int   # chunks to resubmit (failed or missing output)
    complete: bool  # every sample can be merged


def decide_next(counts, attempt, max_tries):
    """What to do after a status check. Returns (Action, reason); changes nothing.
      no samples                      -> FAIL      (no job configs: nothing was submitted)
      complete                        -> MERGE
      chunks pending                  -> WAIT      (failed chunks are resubmitted only when nothing runs any more)
      failed, attempt < max_tries     -> RESUBMIT
      failed, attempt >= max_tries    -> FAIL
    """
    if counts.nsamples == 0:
        return Action.FAIL, "no job configs found for the requested samples"
    if counts.complete:
        return Action.MERGE, "all chunks succeeded"
    if counts.npending > 0:
        return Action.WAIT, "%d chunk(s) pending or running" % (counts.npending)
    if counts.nfailed > 0 and attempt < max_tries:
        return Action.RESUBMIT, "%d chunk(s) failed or missing; resubmitting (try %d of %d)" % (
            counts.nfailed, attempt + 1, max_tries)
    if counts.nfailed > 0:
        return Action.FAIL, "%d chunk(s) still failed or missing after %d tries" % (counts.nfailed, attempt)
    return Action.WAIT, "waiting for the job output"


def counts(status):
    """The StatusCounts of a PicoProducer StageStatus."""
    return StatusCounts(nsamples=len(status.samples), npending=status.npending, nfailed=status.nfailed,
                        complete=status.complete)


# =============================================================================
# =================================== STAGE ===================================


class ProductionStage(Stage):
    """Produces pico tuples with PicoProducer.

    pico: a PicoProducer, or any object with the same methods (request, plan, submit, resubmit, status, merge,
    run_local); the tests pass a fake one.
    """
    name = 'production'
    # Spec = ProductionSpec: set at the bottom of this file, because ProductionSpec is defined below this class.

    # =========================================================================
    # =============================== PIPELINE ================================

    def advance(self, spec, stage_record, reporter):
        """One step, starting from stage_record.state (see the table at the top of this file)."""
        state = StageState(stage_record.state)
        request = self.request(spec)
        if state is StageState.NEW:
            return self._submit(request)
        if state.waiting:
            return self._check(spec, stage_record, request)
        if state is StageState.MERGING:
            return self._merge(spec, request)
        return StageOutcome(state, "nothing to do (%s)" % (state.value))

    def plan(self, spec):
        """The JobPlan of the first submission (nothing is written)."""
        return self.pico.plan(self.request(spec))

    def status(self, spec, stage_record):
        """The live StageStatus of the jobs (read-only), or None before the first submission."""
        if StageState(stage_record.state) is StageState.NEW:
            return None
        return self.pico.status(self.request(spec))

    def run_local(self, spec, maxevts=100, nfiles=1):
        """Quick local test on the first sample of every era and channel (no run record)."""
        return self.pico.run_local(self.request(spec, maxevts=maxevts, nfiles=nfiles, nsamples=1))

    # =========================================================================
    # ================================= STEPS =================================

    def _submit(self, request):
        """NEW: submit the jobs of every matching sample."""
        plan = self.pico.plan(request)
        if not plan.samples:
            return StageOutcome(StageState.FAILED, "no samples match the request", "failed")
        submission = self.pico.submit(request)
        message = "submitted %d of %d sample(s)" % (submission.nsubmitted, len(plan.samples))
        return StageOutcome(StageState.SUBMITTED, message, "submitted", attempt=1, submission=submission.to_dict())

    def _check(self, spec, stage_record, request):
        """SUBMITTED or WAITING: check the jobs, then wait, resubmit, merge or fail (see decide_next)."""
        status = self.pico.status(request)
        action, reason = decide_next(counts(status), stage_record.attempt, spec.max_tries)
        status_dict = status.to_dict()
        if action is Action.WAIT:
            return StageOutcome(StageState.WAITING, reason, "waiting", status=status_dict)
        if action is Action.RESUBMIT:
            submission = self.pico.resubmit(request)
            return StageOutcome(StageState.SUBMITTED, reason, "resubmitted", attempt=stage_record.attempt + 1,
                                submission=submission.to_dict(), status=status_dict)
        if action is Action.MERGE:
            return StageOutcome(StageState.MERGING, reason, "complete", status=status_dict)
        return StageOutcome(StageState.FAILED, reason, "failed", status=status_dict)

    def _merge(self, spec, request):
        """MERGING: merge the job outputs of each sample into one tuple, and record the tuples as artifacts."""
        report = self.pico.merge(request, clean=spec.merge.clean, force=spec.merge.force)
        artifacts = tuple(a.to_dict() for a in report.artifacts)
        if report.invalid:
            reasons = "; ".join("%s: %s" % (name, reason) for name, reason in report.invalid)
            return StageOutcome(StageState.FAILED, "merged tuple(s) failed validation: %s" % (reasons), "failed",
                                artifacts=artifacts)
        if report.refused:
            refused = ', '.join(report.refused)
            return StageOutcome(StageState.WAITING, "merge refused for %s; checking again" % (refused), "refused",
                                artifacts=artifacts)
        return StageOutcome(StageState.DONE, "merged %d tuple(s)" % (len(artifacts)), "merged", artifacts=artifacts)

    # =========================================================================
    # ============================= CONSTRUCTION ==============================

    def request(self, spec, **overrides):
        """The PicoProducer request (JobRequest) built from the recipe options, with optional overrides."""
        return self.pico.request(**dict(spec.request_dict(), **overrides))

    def __init__(self, pico):
        self.pico = pico


# =============================================================================
# ============================== RECIPE OPTIONS ===============================


@dataclass(frozen=True)
class SplitSpec:
    """How samples are split into jobs: files per job, or events per job (None: the sample's setting, then the
    configuration's)."""
    nfilesperjob: Optional[int] = None
    maxevts:      Optional[int] = None


@dataclass(frozen=True)
class MergeSpec:
    """clean: remove the job files and job output after a validated merge.
    force: also merge samples with failed or missing chunks."""
    clean: bool = False
    force: bool = False


@dataclass(frozen=True)
class ProductionSpec:
    """The recipe options of a production stage (all are explained in Framework/README.md)."""
    eras:         Tuple[str, ...]
    channels:     Tuple[str, ...]
    samples:      Tuple[str, ...] = ()        # glob patterns of sample names
    vetoes:       Tuple[str, ...] = ()
    dtypes:       Tuple[str, ...] = ('mc', 'data', 'embed')
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
    _nested = {'split': SplitSpec, 'merge': MergeSpec}  # option groups, read by spec_from_dict()

    def __post_init__(self):
        """Accept a single era or channel as a string, and reject empty or impossible values."""
        for key in ('eras', 'channels'):
            value = getattr(self, key)
            if isinstance(value, str):
                object.__setattr__(self, key, (value,))
            if not getattr(self, key):
                raise ValueError("production: '%s' must not be empty" % (key))
        if self.max_tries < 1:
            raise ValueError("production: 'max_tries' must be at least 1")

    def request_dict(self):
        """The fields of PicoProducer's JobRequest. The tag gets a leading '_', as in pico.py."""
        tag = self.tag if not self.tag or self.tag.startswith('_') else '_' + self.tag
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
