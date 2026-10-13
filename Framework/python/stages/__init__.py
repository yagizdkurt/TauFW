"""The stages of a pipeline. A recipe lists stages by name; STAGES maps each name to its class.

  production   NanoAOD -> pico tuples                    PicoProducer API, batch system (stepwise)
  plots        pico tuples -> control plots              Plotter API (plot.py), local
  histograms   pico tuples -> shapes of the TES+ID fit    Fitter API (createinputsTES.py), local
  fit          shapes -> fit results, correction files   Fitter API (run_workflow_zmm.sh steps), local

A recipe may leave stages out (e.g. only histograms and fit, on tuples made before), but keeps this order.

To add a stage: write a Stage subclass with a Spec (see stages/base.py; stages/local.py for a stage that runs
scripts), add it to STAGES, put its name in ORDER at the place where it runs, and build it in
Framework.from_recipe.

Public API:
  STAGES, ORDER      name -> Stage class; the order in which stages may appear in a recipe
  Stage, StageState, StageOutcome, StageContext, StageNotImplemented, PreflightError, SpecError (stages/base.py)
"""
from TauFW.Framework.stages.base import (Stage, StageState, StageOutcome, StageContext, StageNotImplemented,
                                         PreflightError, SpecError, spec_from_dict)
from TauFW.Framework.stages.production import ProductionStage, ProductionSpec, decide_next, Action
from TauFW.Framework.stages.plots import PlotStage, PlotSpec
from TauFW.Framework.stages.histograms import HistogramStage, HistogramSpec
from TauFW.Framework.stages.fit import FitStage, FitSpec

STAGES = {
    'production': ProductionStage,
    'plots':      PlotStage,
    'histograms': HistogramStage,
    'fit':        FitStage,
}
ORDER = ('production', 'plots', 'histograms', 'fit')

__all__ = ['STAGES', 'ORDER', 'Stage', 'StageState', 'StageOutcome', 'StageContext', 'StageNotImplemented',
           'PreflightError', 'SpecError', 'spec_from_dict', 'ProductionStage', 'ProductionSpec', 'decide_next',
           'Action', 'PlotStage', 'PlotSpec', 'HistogramStage', 'HistogramSpec', 'FitStage', 'FitSpec']
