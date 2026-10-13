# Author: Yagizhan Dinckurt (October 2026)
"""Histogram stage (placeholder): pico tuples -> histograms/shapes, through a future Plotter API.

The contract is declared so that recipes can already name the stage and a later Plotter API can be plugged in
without changing the Framework:

    inputs:   the TupleArtifacts of the production stage (path, sample, group, era, channel, tag, dtype, nevents)
    options:  HistogramSpec (variables, selections, output file)
    outputs:  ShapeArtifact per (era, channel): a ROOT file with one histogram per process, variable and selection

Until the Plotter is cleaned up (it has no public API yet), advance() reports NOT_IMPLEMENTED and plan() raises
StageNotImplemented. Earlier stages are not affected.

Public API:
  HistogramStage, HistogramSpec, ShapeArtifact
"""

# ===== Imports =====
from dataclasses import dataclass
from typing import Tuple
from TauFW.Framework.stages.base import Stage, StageState, StageOutcome, StageNotImplemented

__all__ = ['HistogramStage', 'HistogramSpec', 'ShapeArtifact']


# ===== Stage =====

class HistogramStage(Stage):
  """Placeholder: declares the contract, does nothing."""
  name = 'histograms'

  def advance(self,spec,record,reporter):
    return StageOutcome(StageState.NOT_IMPLEMENTED,"the histogram stage needs a Plotter API (not implemented yet)",
                        "not_implemented")

  def plan(self,spec):
    raise StageNotImplemented(self.name,"the Plotter has no public API yet")


# ===== Contract =====

@dataclass(frozen=True)
class HistogramSpec:
  """Recipe options: variables ('name' or 'name(nbins,min,max)'), selections ('name: cut'), output file pattern."""
  variables:  Tuple[str, ...] = ()
  selections: Tuple[str, ...] = ()
  outfile:    str = "shapes_$ERA_$CHANNEL.root"
  method:     str = ""   # background method, e.g. 'QCD_OSSS'


@dataclass(frozen=True)
class ShapeArtifact:
  """One shape file: histograms per process, variable and selection for one era and channel."""
  path:       str
  era:        str
  channel:    str
  variables:  Tuple[str, ...] = ()
  selections: Tuple[str, ...] = ()

HistogramStage.Spec = HistogramSpec
