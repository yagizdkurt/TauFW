"""The stages of a pipeline. A recipe lists stages by name; STAGES maps each name to its class.

  production   NanoAOD -> pico tuples (PicoProducer API)            implemented
  histograms   pico tuples -> shapes (future Plotter API)           placeholder: NOT_IMPLEMENTED
  fit          shapes -> fit results (future Fitter API)            placeholder: NOT_IMPLEMENTED

To add a stage: write a Stage subclass with a Spec (see stages/base.py), add it to STAGES, and put its name in
ORDER at the place where it runs.

Public API:
  STAGES, ORDER      name -> Stage class; the order in which stages may appear in a recipe
  Stage, StageState, StageOutcome, StageNotImplemented, SpecError (from stages/base.py)
"""
from TauFW.Framework.stages.base import Stage, StageState, StageOutcome, StageNotImplemented, SpecError, spec_from_dict
from TauFW.Framework.stages.production import ProductionStage, ProductionSpec, decide_next, Action
from TauFW.Framework.stages.histograms import HistogramStage, HistogramSpec
from TauFW.Framework.stages.fit import FitStage, FitSpec

STAGES = {
    'production': ProductionStage,
    'histograms': HistogramStage,
    'fit':        FitStage,
}
ORDER = ('production', 'histograms', 'fit')

__all__ = ['STAGES', 'ORDER', 'Stage', 'StageState', 'StageOutcome', 'StageNotImplemented', 'SpecError',
           'spec_from_dict', 'ProductionStage', 'ProductionSpec', 'decide_next', 'Action',
           'HistogramStage', 'HistogramSpec', 'FitStage', 'FitSpec']
