# Author: Yagizhan Dinckurt (October 2026)
"""The stage contract: what every stage of a pipeline (production, histograms, fit, ...) provides.

A stage owns one step of the analysis. The Framework calls it; the stage calls its own package's API
(production: PicoProducer). A stage never sleeps, never loops on a scheduler and never writes the run record:
it returns a StageOutcome, and the Framework records it.

    state machine of one stage:

        NEW ─▶ SUBMITTED ─▶ WAITING ─▶ MERGING ─▶ DONE
                  ▲  │         │
                  └──┴─────────┘ (resubmission)          FAILED, NOT_IMPLEMENTED: terminal

Public API:
  StageState           the states above
  StageOutcome         the result of one advance() call
  Stage                base class: plan(spec), advance(spec, record, reporter), status(spec, record)
  StageNotImplemented  raised by placeholder stages
  SpecError            invalid stage options in a recipe
"""

# ===== Imports =====
from dataclasses import dataclass, fields, MISSING
from enum import Enum
from typing import Optional, Tuple

__all__ = ['StageState', 'StageOutcome', 'Stage', 'StageNotImplemented', 'SpecError', 'spec_from_dict']


# ===== States =====

class StageState(str, Enum):
  """State of one stage in a run. Values are the strings stored in run.json."""
  NEW             = 'NEW'             # nothing done yet
  SUBMITTED       = 'SUBMITTED'       # jobs were (re)submitted; wait before checking
  WAITING         = 'WAITING'         # jobs are pending or running
  MERGING         = 'MERGING'         # all jobs succeeded; outputs are ready to be merged
  DONE            = 'DONE'            # artifacts are recorded
  FAILED          = 'FAILED'          # gave up (message says why)
  NOT_IMPLEMENTED = 'NOT_IMPLEMENTED' # placeholder stage

  @property
  def terminal(self):
    """No further advance() can change it."""
    return self in (StageState.DONE, StageState.FAILED, StageState.NOT_IMPLEMENTED)

  @property
  def waiting(self):
    """The stage waits for the batch system: advance again later."""
    return self in (StageState.SUBMITTED, StageState.WAITING)


# ===== Outcome =====

@dataclass(frozen=True)
class StageOutcome:
  """What one advance() did. The Framework applies it to the stage's record:
  state (always), message (history), attempt (if given), and appends submission/status/artifacts."""
  state:      StageState
  message:    str = ""
  event:      str = ""                # short history keyword, e.g. 'submitted', 'resubmitted', 'merged'
  attempt:    Optional[int] = None    # new attempt number (production: submission try)
  submission: Optional[dict] = None   # Submission.to_dict() of a (re)submission
  status:     Optional[dict] = None   # StageStatus.to_dict() of a status check
  artifacts:  Tuple[dict, ...] = ()   # artifact dicts (production: TupleArtifact.to_dict())


# ===== Stage =====

class Stage(object):
  """Base class of a stage. Subclasses set `name` and `Spec`, and implement plan/advance/status.

  plan(spec)                      -> object        side-effect free preview of what advance() would do
  advance(spec, record, reporter) -> StageOutcome  one step from record.state; never sleeps or loops
  status(spec, record)            -> object        read-only live status (None if nothing to check)
  """
  name = None  # key in recipes and run.json
  Spec = None  # frozen dataclass of the stage's recipe options (see spec_from_dict)

  def plan(self,spec):
    raise StageNotImplemented(self.name)

  def advance(self,spec,record,reporter):
    raise StageNotImplemented(self.name)

  def status(self,spec,record):
    return None

  def __repr__(self):
    return "<%s %r>"%(self.__class__.__name__,self.name)


# ===== Errors =====

class StageNotImplemented(NotImplementedError):
  """A placeholder stage: its contract is declared, its package has no API yet."""

  def __init__(self,name,reason=""):
    super(StageNotImplemented,self).__init__("Stage %r is not implemented yet%s"%(name,": "+reason if reason else ""))
    self.stage = name


class SpecError(ValueError):
  """Invalid stage options; the message names the offending key."""


# ===== Spec helpers =====

def spec_from_dict(cls,data,where="stage"):
  """Build a stage Spec dataclass from recipe options. Unknown keys and missing required keys are errors that
  name the key; list values become tuples (specs are frozen and hashable)."""
  if not isinstance(data,dict):
    raise SpecError("%s: expected a mapping of options, got %r"%(where,data))
  known   = {f.name: f for f in fields(cls)}
  unknown = [k for k in data if k not in known]
  if unknown:
    raise SpecError("%s: unknown option %r (known: %s)"%(where,unknown[0],', '.join(sorted(known))))
  values = { }
  for name, value in data.items():
    if isinstance(value,list):
      value = tuple(value)
    elif isinstance(value,dict) and hasattr(cls,'_nested') and name in cls._nested:
      value = spec_from_dict(cls._nested[name],value,"%s.%s"%(where,name))
    values[name] = value
  try:
    return cls(**values)
  except ValueError as err: # rejected by the Spec's own checks
    raise SpecError("%s: %s"%(where,err))
  except TypeError as err: # missing required fields
    missing = [f.name for f in fields(cls) if f.name not in values and f.default is MISSING and f.default_factory is MISSING]
    raise SpecError("%s: missing required option %r"%(where,missing[0] if missing else str(err)))

