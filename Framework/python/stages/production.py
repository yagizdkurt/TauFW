# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Production stage: turn NanoAOD into pico tuples on the batch system, through the public PicoProducer API.

Each call of ProductionStage.advance() takes one step, starting from the state saved in run.json:

    NEW        ─▶ plan + submit                        ─▶ SUBMITTED   (attempt 1)
    SUBMITTED  ─┐
    WAITING    ─┴▶ status ─▶ decide_next():  wait      ─▶ WAITING
                                             resubmit  ─▶ SUBMITTED   (attempt + 1)
                                             merge     ─▶ MERGING
                                             fail      ─▶ FAILED
    MERGING    ─▶ merge(clean=merge.clean)             ─▶ DONE        (one TupleArtifact per sample, kind 'tuples')

Where the tuples go is the Framework's choice, not the PicoProducer configuration's: the stage's directory
<run_dir>/stages/<id>/ (JobRequest.tupledir). Below it PicoProducer chooses the layout ($ERA/$GROUP/<sample>_<channel>
<tag>.root) and tells it (PicoProducer.tuple_pattern); every tuple artifact records it as `pattern`, which the stages
that read the tuples are given. The job files stay in PicoProducer's job directories (jobdir and outdir of the
configuration).

The policy is set in the recipe: max_tries (default 3), merge.clean (default false), merge.force (default false).
decide_next() only looks at numbers and changes nothing, so the policy is tested without a batch system.

Inputs:  ProductionSpec (the recipe options), the stage's record (state, attempt), a PicoProducer.
Outputs: a StageOutcome. Through PicoProducer: job files, batch jobs, and the merged tuples in <run_dir>/stages/<id>/.

Public API:
  ProductionStage(pico)                  the stage
  ProductionSpec, SplitSpec, MergeSpec   recipe options
  decide_next(counts, attempt, max_tries) -> (Action, reason)
  Action, StatusCounts, counts(status)
"""
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple, Optional, Tuple
from TauFW.Framework.stages.base import Stage, StageState, StageOutcome, StageContext

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
    inputs = {}              # reads NanoAOD (the samples of the PicoProducer config), no stage's output
    outputs = ('tuples',)
    # Spec = ProductionSpec: set at the bottom of this file, because ProductionSpec is defined below this class.

    # =========================================================================
    # =============================== PIPELINE ================================

    def advance(self, spec, stage_record, reporter, context=None):
        """One step, starting from stage_record.state (see the table at the top of this file). The context gives
        where the tuples go (the stage's directory); PicoProducer keeps its own job directories."""
        state = StageState(stage_record.state)
        request = self.request(spec, context)
        if state is StageState.NEW:
            return self._submit(request)
        if state.waiting:
            return self._check(spec, stage_record, request)
        if state is StageState.MERGING:
            return self._merge(spec, request)
        return StageOutcome(state, "nothing to do (%s)" % (state.value))

    def plan(self, spec, context=None):
        """The JobPlan of the first submission (nothing is written)."""
        return self.pico.plan(self.request(spec, context))

    def produced_samples(self, spec, context=None):
        """(era, channel, sample name) of the tuples a first submission makes, from PicoProducer's sample catalogs
        only (no storage or DAS): for the comparison with the samples the readers ask for (samples.py)."""
        return self.pico.sample_names(self.request(spec, context))

    def planned_artifacts(self, spec, plan, context=None):
        """What the later stages see of the tuples before they exist: one artifact of kind 'tuples' with their
        pattern, <stage dir>/$ERA/$GROUP (in a plan before the run exists, under the placeholder
        '<run_dir>/stages/<id>')."""
        context = context or StageContext()
        if context.run_dir:
            pattern = self.pico.tuple_pattern(self.request(spec, context))
        else:  # the layout PicoProducer publishes; tuple_pattern() would make the placeholder absolute
            placeholder = StageContext(run_dir='<run_dir>', stage_id=context.stage_id or self.name).stage_dir()
            pattern = os.path.join(placeholder, *self.pico.TUPLE_LAYOUT.split('/'))
        return ({'kind': self.outputs[0], 'pattern': pattern},)

    def submits(self, stage_record):
        """NEW submits; SUBMITTED and WAITING may resubmit. MERGING does not (a cut merge is merged again)."""
        state = StageState(stage_record.state)
        return state is StageState.NEW or state.waiting

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
        pattern = self.pico.tuple_pattern(request)  # where they were written: what the readers are given
        artifacts = tuple(dict(a.to_dict(), pattern=pattern) for a in report.artifacts)
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

    def request(self, spec, context=None, **overrides):
        """The PicoProducer request (JobRequest) built from request_fields(), with optional overrides. With a run
        (context.run_dir), the tuples go to the stage's directory (tupledir, absolute)."""
        fields = dict(self.request_fields(spec), **overrides)
        if context is not None and context.run_dir:
            fields['tupledir'] = os.path.abspath(context.stage_dir())
        return self.pico.request(**fields)

    def request_fields(self, spec):
        """The request fields of the recipe options (what run.json records as the stage's request): a field the
        recipe leaves unset (None: queue, batchopts, ncores) takes the stage's default (the user config,
        user_settings.py); ncores in neither is DEFAULT_NCORES."""
        fields = spec.request_dict()
        for field_name, value in self.defaults.items():
            if fields.get(field_name) is None:
                fields[field_name] = value
        if fields.get('ncores') is None:
            fields['ncores'] = DEFAULT_NCORES
        return fields

    def __init__(self, pico, settings=None):
        """settings: the user config's settings of the stage (user_settings.ProductionSettings): its defaults are
        the request fields for the options the recipe leaves unset ({'queue': 'workday', ...})."""
        self.pico = pico
        self.settings = settings
        self.defaults = dict(settings.defaults) if settings else {}


# =============================================================================
# ============================== RECIPE OPTIONS ===============================


DEFAULT_NCORES = 4  # files checked at once (JobRequest.ncores), without ncores in the recipe or the user config


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
    ncores:       Optional[int] = None     # None: the user config's production.ncores, else DEFAULT_NCORES
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
