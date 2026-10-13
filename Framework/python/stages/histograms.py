# Author: Yagizhan Dinckurt (October 2026)
"""Histogram stage (placeholder): pico tuples -> histograms (shapes), through a future Plotter API.

The stage does not run yet. Its contract is declared already, so that recipes can name the stage today and a
Plotter API can be plugged in later without changing the Framework:

    inputs:   the TupleArtifacts of the production stage (path, sample, group, era, channel, tag, dtype, nevents)
    options:  HistogramSpec (variables, selections, output file)
    outputs:  one ShapeArtifact per (era, channel): a ROOT file with one histogram per process, variable and
              selection

Until the Plotter has a public API, advance() returns NOT_IMPLEMENTED and plan() raises StageNotImplemented.
The stages before it are not affected.

Public API:
  HistogramStage, HistogramSpec, ShapeArtifact
"""
from dataclasses import dataclass
from typing import Tuple
from TauFW.Framework.stages.base import Stage, StageState, StageOutcome, StageNotImplemented

__all__ = ['HistogramStage', 'HistogramSpec', 'ShapeArtifact']


# =============================================================================
# =================================== STAGE ===================================


class HistogramStage(Stage):
    """Placeholder: declares the contract and does nothing."""
    name = 'histograms'
    # Spec = HistogramSpec: set at the bottom of this file.

    def advance(self, spec, stage_record, reporter):
        return StageOutcome(StageState.NOT_IMPLEMENTED, "the histogram stage needs a Plotter API (not implemented yet)",
                            "not_implemented")

    def plan(self, spec):
        raise StageNotImplemented(self.name, "the Plotter has no public API yet")


# =============================================================================
# ================================= CONTRACT ==================================


@dataclass(frozen=True)
class HistogramSpec:
    """Recipe options: variables ('name' or 'name(nbins,min,max)'), selections ('name: cut'), output file pattern."""
    variables:  Tuple[str, ...] = ()
    selections: Tuple[str, ...] = ()
    outfile:    str = "shapes_$ERA_$CHANNEL.root"
    method:     str = ""   # background method, e.g. 'QCD_OSSS'


@dataclass(frozen=True)
class ShapeArtifact:
    """One shape file: the histograms per process, variable and selection of one era and channel."""
    path:       str
    era:        str
    channel:    str
    variables:  Tuple[str, ...] = ()
    selections: Tuple[str, ...] = ()


HistogramStage.Spec = HistogramSpec
