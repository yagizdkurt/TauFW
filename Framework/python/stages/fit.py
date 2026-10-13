# Author: Yagizhan Dinckurt (October 2026)
"""Fit stage (placeholder): shapes -> datacards -> fit results, through a future Fitter API.

Declared contract:

    inputs:   the ShapeArtifacts of the histogram stage
    options:  FitSpec (observable, model, parameters of interest)
    outputs:  FitResult: datacard and fit output paths, best-fit values of the parameters of interest

Until the Fitter has a public API, advance() reports NOT_IMPLEMENTED and plan() raises StageNotImplemented.

Public API:
  FitStage, FitSpec, FitResult
"""

# ===== Imports =====
from dataclasses import dataclass
from typing import Tuple
from TauFW.Framework.stages.base import Stage, StageState, StageOutcome, StageNotImplemented

__all__ = ['FitStage', 'FitSpec', 'FitResult']


# ===== Stage =====

class FitStage(Stage):
  """Placeholder: declares the contract, does nothing."""
  name = 'fit'

  def advance(self,spec,record,reporter):
    return StageOutcome(StageState.NOT_IMPLEMENTED,"the fit stage needs a Fitter API (not implemented yet)",
                        "not_implemented")

  def plan(self,spec):
    raise StageNotImplemented(self.name,"the Fitter has no public API yet")


# ===== Contract =====

@dataclass(frozen=True)
class FitSpec:
  """Recipe options: the fitted observable, the model (e.g. 'tes', 'tid') and the parameters of interest."""
  observable: str = ""
  model:      str = ""
  pois:       Tuple[str, ...] = ()


@dataclass(frozen=True)
class FitResult:
  """Datacard and fit output, with the best-fit value (and uncertainty) of each parameter of interest."""
  datacard: str
  output:   str
  values:   Tuple[Tuple[str, float, float], ...] = ()   # (poi, value, error)

FitStage.Spec = FitSpec
