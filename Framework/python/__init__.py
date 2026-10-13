"""TauFW Framework: run analysis pipelines (production -> histograms -> fit) from a recipe.

    from TauFW.Framework import Framework
    fw     = Framework.from_recipe("Framework/recipes/example_mutau.yml")
    plan   = fw.plan()                    # nothing written or submitted
    record = fw.start()                   # taufw_runs/<name>_<time>/run.json; submits the production jobs
    record = fw.advance(record)           # later: check, resubmit or merge; next stages
    print(fw.status(record))

Command line: Framework/scripts/taufw.py (plan, start, advance, status). See Framework/README.md.

Public API:
  Framework, load_run, RunPlan, RunSummary      the orchestrator (framework.py)
  Recipe, StageSpec, RecipeError                recipes (recipe.py)
  RunRecord, StageRecord                        run.json (run_record.py)
  StageState, StageOutcome, STAGES              the stage contract (stages/)
  FrameworkReporter, SilentReporter             reporting (reporting.py)
"""
from TauFW.Framework.recipe import Recipe, StageSpec, RecipeError
from TauFW.Framework.run_record import RunRecord, StageRecord
from TauFW.Framework.stages import STAGES, StageState, StageOutcome
from TauFW.Framework.reporting import FrameworkReporter, SilentReporter
from TauFW.Framework.framework import Framework, load_run, RunPlan, RunSummary

__all__ = ['Framework', 'load_run', 'RunPlan', 'RunSummary', 'Recipe', 'StageSpec', 'RecipeError',
           'RunRecord', 'StageRecord', 'STAGES', 'StageState', 'StageOutcome', 'FrameworkReporter', 'SilentReporter']
