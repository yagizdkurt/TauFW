# Author: Yagizhan Dinckurt (October 2026)
"""The stage contract: what every stage of a pipeline (production, histograms, fit, ...) must provide.

A stage is one step of the analysis, for example "produce pico tuples". The Framework calls the stage, and the
stage calls the API of its own package (the production stage calls PicoProducer). A stage never sleeps, never
waits in a loop for the batch system and never writes run.json. It only returns a StageOutcome that describes
what it did, and the Framework writes that into the run record.

The states of one stage:

    batch stage (production):
    NEW ─▶ SUBMITTED ─▶ WAITING ─▶ MERGING ─▶ DONE
              ▲  │         │
              └──┴─────────┘ (resubmission)          FAILED, NOT_IMPLEMENTED: final

    local stage (plots, histograms, fit):  NEW ─▶ DONE or FAILED, in one advance() call

A stage also gets a StageContext: the run directory (for its log files), the artifacts of the stages before it
(so the histograms stage knows which tuples production made and the fit stage which shapes exist), and the bundle
directory that its path options are resolved against (see bundle.py).

Public API:
  StageState           the states above
  StageOutcome         the result of one advance() call
  StageContext         what a stage may know about its run: run directory, artifacts of earlier stages
  Stage                base class: plan(spec, context), advance(spec, stage_record, reporter, context),
                       status(spec, stage_record)
  StageNotImplemented  raised by placeholder stages
  PreflightError       raised by a stage whose environment is not ready (the stage stays NEW)
  SpecError            invalid stage options in a recipe
  spec_from_dict       turns the options written in a recipe into a stage's Spec
  as_strings, spec_to_dict   small helpers for Spec classes
"""
from dataclasses import asdict, dataclass, field, fields, MISSING
from enum import Enum
import os
from typing import Mapping, Optional, Tuple

__all__ = ['StageState', 'StageOutcome', 'StageContext', 'Stage', 'StageNotImplemented', 'PreflightError',
           'SpecError', 'spec_from_dict', 'as_strings', 'spec_to_dict']


# =============================================================================
# ================================== STATES ===================================


class StageState(str, Enum):
    """State of one stage in a run. The values are the strings written to run.json."""
    NEW             = 'NEW'             # nothing done yet
    SUBMITTED       = 'SUBMITTED'       # jobs were (re)submitted; wait before checking them
    WAITING         = 'WAITING'         # jobs are pending or running
    MERGING         = 'MERGING'         # all jobs succeeded; their outputs are ready to be merged
    DONE            = 'DONE'            # finished; the results (artifacts) are recorded
    FAILED          = 'FAILED'          # gave up; the message says why
    NOT_IMPLEMENTED = 'NOT_IMPLEMENTED' # placeholder stage that cannot run yet

    @property
    def terminal(self):
        """True if the state is final: advancing the stage again cannot change it."""
        return self in (StageState.DONE, StageState.FAILED, StageState.NOT_IMPLEMENTED)

    @property
    def waiting(self):
        """True if the stage waits for the batch system: advance it again later."""
        return self in (StageState.SUBMITTED, StageState.WAITING)


# =============================================================================
# ================================== OUTCOME ==================================


@dataclass(frozen=True)
class StageOutcome:
    """What one advance() call of a stage did.

    The Framework copies it into the stage's record in run.json: the state and message always, the attempt if it
    is given, and it adds the submission, the status and the artifacts if they are given.
    """
    state:      StageState
    message:    str = ""
    event:      str = ""                # short keyword for the history, e.g. 'submitted', 'resubmitted', 'merged'
    attempt:    Optional[int] = None    # new attempt number (for production: the submission try)
    submission: Optional[dict] = None   # Submission.to_dict() of a (re)submission
    status:     Optional[dict] = None   # StageStatus.to_dict() of a status check
    artifacts:  Tuple[dict, ...] = ()   # the results, as dicts (for production: TupleArtifact.to_dict())


# =============================================================================
# ================================== CONTEXT ==================================


@dataclass(frozen=True)
class StageContext:
    """What a stage may know about its run, besides its own options and record.

    run_dir:     the run directory; a stage writes its log files to stage_dir(stage_id)
    upstream:    stage id -> artifacts (dicts) of the stages before this one. In advance() these are the
                 recorded artifacts of DONE stages; in plan() the artifacts the earlier stages plan to make.
    pico_config: the PicoProducer configuration of the run (path), or None (PicoProducer's default)
    bundle_dir:  the bundle directory the path options are resolved against (a run: its copy, <run_dir>/bundle)
    stage_id:    the id of the stage this context is for (a built-in stage: its name)
    """
    run_dir:     str = ""
    upstream:    Mapping[str, Tuple[dict, ...]] = field(default_factory=dict)
    pico_config: Optional[str] = None
    bundle_dir:  Optional[str] = None
    stage_id:    str = ""

    def artifacts(self, stage=None, kind=None):
        """The upstream artifacts of one stage id (or of all stages), optionally only those of one kind."""
        stages = [stage] if stage else list(self.upstream)
        return tuple(artifact for name in stages for artifact in self.upstream.get(name, ())
                     if kind is None or artifact.get('kind') == kind)

    def stage_dir(self, name=None):
        """The directory for the files (logs) of one stage: <run_dir>/<id> (default: this context's stage)."""
        return os.path.join(self.run_dir, name or self.stage_id)


# =============================================================================
# =================================== STAGE ===================================


class Stage:
    """Base class of all stages. A subclass sets `name` and `Spec`, and implements plan, advance and status.

    plan(spec, context)                             -> object        preview of what advance() would do;
                                                                     changes nothing
    advance(spec, stage_record, reporter, context)  -> StageOutcome  one step, starting from stage_record.state;
                                                                     never sleeps or loops
    status(spec, stage_record)                      -> object        live status, read-only (None if there is
                                                                     nothing to check)

    `spec` is always the stage's Spec: the validated options of the stage from the recipe (for example a
    ProductionSpec). `stage_record` is the StageRecord of this stage in run.json. `context` is a StageContext
    (None: an empty one). A plan object may have an `artifacts` attribute (dicts): the Framework passes them to
    the plans of the later stages as their upstream artifacts.
    """
    name = None  # the stage's name, as written in recipes ('stage:')
    Spec = None  # frozen dataclass with the stage's recipe options; built by spec_from_dict()

    @classmethod
    def default_id(cls, spec):
        """The stage's id in a run when the recipe gives none: its name (a python step: its file name)."""
        return cls.name

    def plan(self, spec, context=None):
        raise StageNotImplemented(self.name)

    def advance(self, spec, stage_record, reporter, context=None):
        raise StageNotImplemented(self.name)

    def status(self, spec, stage_record):
        return None

    def __repr__(self):
        return "<%s %r>" % (self.__class__.__name__, self.name)


# =============================================================================
# ================================== ERRORS ===================================


class StageNotImplemented(NotImplementedError):
    """Raised by a placeholder stage: its contract is declared, but its package has no API yet."""

    def __init__(self, name, reason=""):
        super().__init__("Stage %r is not implemented yet%s" % (name, ": " + reason if reason else ""))
        self.stage = name


class PreflightError(RuntimeError):
    """The environment of a stage is not ready (for example `combine` is not on PATH). Nothing was run: the stage
    stays NEW, the error is written to its history, and advance() can be called again once it is fixed."""


class SpecError(ValueError):
    """Invalid stage options in a recipe; the message names the wrong key."""


# =============================================================================
# =============================== SPEC HELPERS ================================


def spec_from_dict(cls, data, where="stage"):
    """Build a stage's Spec dataclass `cls` from the options written in a recipe.

    - An unknown key or a missing required key raises SpecError, which names the key.
    - Lists become tuples, because a Spec is frozen and must be hashable.
    - A Spec can have nested option groups (for example `split:` and `merge:` in production). It lists them in a
      class attribute `_nested = {'option name': NestedSpecClass}`, and those dicts are built recursively.
    - A Spec lists its path options (config files, a step's file) in a class attribute `_paths = ('name', ...)`.
      They are kept as written; the stage resolves them against the bundle (bundle.resolve_spec).
    `where` says where the options come from, for the error messages (e.g. "recipe.yml: stages[0] (production)").
    """
    if not isinstance(data, dict):
        raise SpecError("%s: expected a mapping of options, got %r" % (where, data))
    known = {f.name: f for f in fields(cls)}
    unknown = [k for k in data if k not in known]
    if unknown:
        raise SpecError("%s: unknown option %r (known: %s)" % (where, unknown[0], ', '.join(sorted(known))))
    values = {}
    for name, value in data.items():
        if isinstance(value, list):
            value = tuple(value)
        elif isinstance(value, dict) and hasattr(cls, '_nested') and name in cls._nested:
            value = spec_from_dict(cls._nested[name], value, "%s.%s" % (where, name))
        values[name] = value
    try:
        return cls(**values)
    except ValueError as err:  # rejected by the Spec's own checks (__post_init__)
        raise SpecError("%s: %s" % (where, err))
    except TypeError as err:  # a required option is missing
        missing = [f.name for f in fields(cls)
                   if f.name not in values and f.default is MISSING and f.default_factory is MISSING]
        raise SpecError("%s: missing required option %r" % (where, missing[0] if missing else str(err)))


def as_strings(values):
    """A single value or a list, as a tuple of strings (YAML may give numbers, e.g. eras: [2025])."""
    if isinstance(values, (str, int, float)):
        values = (values,)
    return tuple(str(value) for value in values or ())


def spec_to_dict(spec):
    """A Spec as a JSON-ready dict (tuples become lists), e.g. for the request saved in run.json."""
    return {key: list(value) if isinstance(value, tuple) else value for key, value in asdict(spec).items()}
