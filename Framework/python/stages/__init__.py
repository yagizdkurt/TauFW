# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""The stages of a pipeline. A recipe lists stages by name; STAGES maps each name to its class.

  production   NanoAOD -> pico tuples                    PicoProducer API, batch system (stepwise)
  plots        pico tuples -> control plots              Histogrammer API (fillhists.py), local
  shapes       pico tuples -> shapes of the TES+ID fit    Fitter API (createinputsTES.py), local
  fit          shapes -> fit results, correction files   Fitter API (run_workflow_zmm.sh steps), local
  python       a Python file of the analysis bundle      step_runner.py in its own process, local

A recipe may leave stages out (e.g. only shapes and fit, on tuples made before), and runs its stages in the order
they are written; an input names an earlier stage. Any stage may appear any number of times, each with its own id,
except production (at most once, see recipe.py).
Each stage declares its input slots and the kinds of data it makes (Stage.inputs, Stage.outputs):

  production   inputs: none                outputs: tuples
  plots        inputs: tuples <- tuples    outputs: plots
  shapes       inputs: tuples <- tuples    outputs: shapes
  fit          inputs: shapes <- shapes    outputs: fit, corrections
  python       inputs: any names           outputs: any

To add a stage: write a Stage subclass with a Spec, its inputs and outputs (see stages/base.py; stages/local.py
for a stage that runs scripts), add it to STAGES (and to ORDER if it is a built-in pipeline stage), and build it
in Framework.from_recipe.

Public API:
  STAGES, ORDER      name -> Stage class; the built-in pipeline stages in their usual order (used to list the
                     known stages in messages; a recipe may write them in any order)
  RETIRED            old stage name -> what replaces it (for the message of a recipe that still names it)
  Stage, StageState, StageOutcome, StageContext, StageNotImplemented, PreflightError, SpecError (stages/base.py)
"""
from TauFW.Framework.stages.base import (Stage, StageState, StageOutcome, StageContext, StageNotImplemented,
                                         PreflightError, SpecError, spec_from_dict)
from TauFW.Framework.stages.production import ProductionStage, ProductionSpec, decide_next, Action
from TauFW.Framework.stages.plots import PlotStage, PlotSpec
from TauFW.Framework.stages.shapes import ShapesStage, ShapesSpec
from TauFW.Framework.stages.fit import FitStage, FitSpec
from TauFW.Framework.stages.python_step import PythonStage, PythonSpec

STAGES = {
    'production': ProductionStage,
    'plots':      PlotStage,
    'shapes':     ShapesStage,
    'fit':        FitStage,
    'python':     PythonStage,
}
ORDER = ('production', 'plots', 'shapes', 'fit')
# Stage names that no longer exist -> what to write instead (the recipe check says so; nothing runs them).
RETIRED = {
    'histograms': "renamed 'shapes' (CL §24)",
}

__all__ = ['STAGES', 'ORDER', 'RETIRED', 'Stage', 'StageState', 'StageOutcome', 'StageContext',
           'StageNotImplemented', 'PreflightError', 'SpecError', 'spec_from_dict', 'ProductionStage', 'ProductionSpec',
           'decide_next', 'Action', 'PlotStage', 'PlotSpec', 'ShapesStage', 'ShapesSpec', 'FitStage', 'FitSpec',
           'PythonStage', 'PythonSpec']
