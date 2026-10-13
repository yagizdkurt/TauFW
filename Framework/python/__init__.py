"""TauFW Framework: run analysis pipelines (production -> histograms -> fit) from a recipe.

    from TauFW.Framework import Framework
    fw     = Framework.from_recipe("Framework/recipes/example_mutau.yml")
    plan   = fw.plan()                    # changes nothing: shows what would be done
    record = fw.start()                   # taufw_runs/<name>_<time>/run.json; submits the production jobs
    record = fw.advance(record)           # later: check, resubmit or merge; then the next stages
    print(fw.status(record))

Command line: Framework/scripts/taufw.py (plan, start, advance, status). New here? Read Framework/README.md first.

Public API:
  Framework, load_run, RunPlan, RunSummary      the orchestrator (framework.py)
  Recipe, StageSpec, RecipeError                recipes (recipe.py)
  RunRecord, RunState, StageRecord              run.json (run_record.py)
  StageState, StageOutcome, STAGES              the stage contract (stages/)
  Reporter, FrameworkReporter, SilentReporter   reporting (reporting.py)
"""
from TauFW.Framework.recipe import Recipe, StageSpec, RecipeError
from TauFW.Framework.run_record import RunRecord, RunState, StageRecord
from TauFW.Framework.stages import STAGES, StageState, StageOutcome
from TauFW.Framework.reporting import Reporter, FrameworkReporter, SilentReporter
from TauFW.Framework.framework import Framework, load_run, RunPlan, RunSummary

__all__ = ['Framework', 'load_run', 'RunPlan', 'RunSummary', 'Recipe', 'StageSpec', 'RecipeError',
           'RunRecord', 'RunState', 'StageRecord', 'STAGES', 'StageState', 'StageOutcome',
           'Reporter', 'FrameworkReporter', 'SilentReporter']
