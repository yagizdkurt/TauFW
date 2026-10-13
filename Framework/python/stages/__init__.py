# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""The stages of a pipeline. A recipe lists stages by name; STAGES maps each name to its class.

  production   NanoAOD -> pico tuples                    PicoProducer API, batch system (stepwise)
  plots        pico tuples -> control plots              Plotter API (plot.py), local
  histograms   pico tuples -> shapes of the TES+ID fit    Fitter API (createinputsTES.py), local
  fit          shapes -> fit results, correction files   Fitter API (run_workflow_zmm.sh steps), local
  python       a Python file of the analysis bundle      step_runner.py in its own process, local

A recipe may leave stages out (e.g. only histograms and fit, on tuples made before), but keeps the built-in stages
in the order of ORDER, each at most once. Python steps are not in ORDER: they may be anywhere, any number of times.

To add a stage: write a Stage subclass with a Spec (see stages/base.py; stages/local.py for a stage that runs
scripts), add it to STAGES, put its name in ORDER at the place where it runs (or leave it out of ORDER for a
stage that may be anywhere), and build it in Framework.from_recipe.

Public API:
  STAGES, ORDER      name -> Stage class; the order in which the built-in stages may appear in a recipe
  Stage, StageState, StageOutcome, StageContext, StageNotImplemented, PreflightError, SpecError (stages/base.py)
"""
from TauFW.Framework.stages.base import (Stage, StageState, StageOutcome, StageContext, StageNotImplemented,
                                         PreflightError, SpecError, spec_from_dict)
from TauFW.Framework.stages.production import ProductionStage, ProductionSpec, decide_next, Action
from TauFW.Framework.stages.plots import PlotStage, PlotSpec
from TauFW.Framework.stages.histograms import HistogramStage, HistogramSpec
from TauFW.Framework.stages.fit import FitStage, FitSpec
from TauFW.Framework.stages.python_step import PythonStage, PythonSpec

STAGES = {
    'production': ProductionStage,
    'plots':      PlotStage,
    'histograms': HistogramStage,
    'fit':        FitStage,
    'python':     PythonStage,
}
ORDER = ('production', 'plots', 'histograms', 'fit')

__all__ = ['STAGES', 'ORDER', 'Stage', 'StageState', 'StageOutcome', 'StageContext', 'StageNotImplemented',
           'PreflightError', 'SpecError', 'spec_from_dict', 'ProductionStage', 'ProductionSpec', 'decide_next',
           'Action', 'PlotStage', 'PlotSpec', 'HistogramStage', 'HistogramSpec', 'FitStage', 'FitSpec',
           'PythonStage', 'PythonSpec']
