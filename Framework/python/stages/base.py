# Author: Yagizhan Dinckurt (October 2026)
"""The stage contract: what every stage of a pipeline (production, histograms, fit, ...) must provide.

A stage is one step of the analysis, for example "produce pico tuples". The Framework calls the stage, and the
stage calls the API of its own package (the production stage calls PicoProducer). A stage never sleeps, never
waits in a loop for the batch system and never writes run.json. It only returns a StageOutcome that describes
what it did, and the Framework writes that into the run record.

The states of one stage:

    NEW ─▶ SUBMITTED ─▶ WAITING ─▶ MERGING ─▶ DONE
              ▲  │         │
              └──┴─────────┘ (resubmission)          FAILED, NOT_IMPLEMENTED: final

Public API:
  StageState           the states above
  StageOutcome         the result of one advance() call
  Stage                base class: plan(spec), advance(spec, stage_record, reporter), status(spec, stage_record)
  StageNotImplemented  raised by placeholder stages
  SpecError            invalid stage options in a recipe
  spec_from_dict       turns the options written in a recipe into a stage's Spec
"""
from dataclasses import dataclass, fields, MISSING
from enum import Enum
from typing import Optional, Tuple

__all__ = ['StageState', 'StageOutcome', 'Stage', 'StageNotImplemented', 'SpecError', 'spec_from_dict']


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
# =================================== STAGE ===================================


class Stage:
    """Base class of all stages. A subclass sets `name` and `Spec`, and implements plan, advance and status.

    plan(spec)                             -> object        preview of what advance() would do; changes nothing
    advance(spec, stage_record, reporter)  -> StageOutcome  one step, starting from stage_record.state;
                                                            never sleeps or loops
    status(spec, stage_record)             -> object        live status, read-only (None if there is nothing to check)

    `spec` is always the stage's Spec: the validated options of the stage from the recipe (for example a
    ProductionSpec). `stage_record` is the StageRecord of this stage in run.json.
    """
    name = None  # the stage's name, as written in recipes and run.json
    Spec = None  # frozen dataclass with the stage's recipe options; built by spec_from_dict()

    def plan(self, spec):
        raise StageNotImplemented(self.name)

    def advance(self, spec, stage_record, reporter):
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
