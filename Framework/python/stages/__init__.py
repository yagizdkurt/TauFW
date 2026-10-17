# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""The stages of a pipeline. A recipe lists stages by name; STAGES maps each name to its class.

  production   NanoAOD -> pico tuples                    PicoProducer API, batch system (stepwise)
  plots        pico tuples -> control plots              Histogrammer API (fillhists.py), local
  histograms   pico tuples -> shapes of the TES+ID fit    Fitter API (createinputsTES.py), local
  fit          shapes -> fit results, correction files   Fitter API (run_workflow_zmm.sh steps), local
  python       a Python file of the analysis bundle      step_runner.py in its own process, local

A recipe may leave stages out (e.g. only histograms and fit, on tuples made before), and runs its stages in the order
they are written; an input names an earlier stage. Any stage may appear any number of times, each with its own id,
except production (at most once, see recipe.py).
Each stage declares its input slots and the kinds of data it makes (Stage.inputs, Stage.outputs):

  production   inputs: none                outputs: tuples
  plots        inputs: tuples <- tuples    outputs: plots
  histograms   inputs: tuples <- tuples    outputs: shapes
  fit          inputs: shapes <- shapes    outputs: fit, corrections
  python       inputs: any names           outputs: any

To add a stage: write a Stage subclass with a Spec, its inputs and outputs (see stages/base.py; stages/local.py
for a stage that runs scripts), add it to STAGES (and to ORDER if it is a built-in pipeline stage), and build it
in Framework.from_recipe.

Public API:
  STAGES, ORDER      name -> Stage class; the built-in pipeline stages in their usual order (used to list the
                     known stages in messages; a recipe may write them in any order)
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
