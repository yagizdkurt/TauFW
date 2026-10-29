# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""TauFW Framework: run analysis pipelines (production -> controlhists -> controlplots -> shapes -> fit) from a
recipe.

    from TauFW.Framework import Framework
    fw     = Framework.from_recipe("Analyses/Examples/mutau_short")   # an analysis bundle (or a recipe file)
    plan   = fw.plan()                    # changes nothing: shows what would be done
    record = fw.start()                   # <run_root>/<name>_<time>/run.json; submits the production jobs
    record = fw.advance(record)           # later: check, resubmit or merge; then the local stages (controlhists, ...)
    print(fw.status(record))

Command line: Framework/scripts/taufw.py (check, plan, start, advance, retry, status, init). New here? Read Framework/README.md
first; analyses (recipe, configs, Python steps) live in Analyses/<name>/ (Analyses/README.md).

Public API:
  Framework, load_run, RunPlan, RunSummary      the orchestrator (_internal/runtime/framework.py)
  RunDirectoryError                             a run root or run directory that cannot be written
  RetryError                                    Framework.retry() cannot run the failed stage again (CL §44)
  Recipe, StageSpec, Issue, RecipeError         recipes (_internal/recipes/recipe.py)
  check_recipe, RecipeCheck                     every problem of a recipe file, files included (_internal/recipes/validation.py)
  RunRecord, RunState, StageRecord              run.json (_internal/runtime/run_record.py)
  StageState, StageOutcome, STAGES              the stage contract (stages/); controlhists, controlplots,
                                                shapes and fit call the Histogrammer, Plotter and Fitter APIs
                                                (TauFW.Histogrammer.api, TauFW.Plotter.api, TauFW.Fitter.api)
  Reporter, FrameworkReporter, SilentReporter,  reporting (_internal/runtime/reporting.py); EventReporter also
  EventReporter                                 writes events for the menu's screens
  current_version, VersionChecker                local release metadata and explicit/advisory update checks

Everything else is under _internal/ (the Framework's inside, CL §52); the stages are in stages/.
"""
from TauFW.Framework._internal.recipes.recipe import Recipe, StageSpec, Issue, RecipeError
from TauFW.Framework._internal.recipes.validation import check_recipe, RecipeCheck
from TauFW.Framework._internal.runtime.run_record import RunRecord, RunState, StageRecord
from TauFW.Framework.stages import STAGES, StageState, StageOutcome
from TauFW.Framework._internal.runtime.reporting import Reporter, FrameworkReporter, SilentReporter, EventReporter
from TauFW.Framework._internal.runtime.framework import (Framework, load_run, RunPlan, RunSummary, RunDirectoryError,
                                                         RetryError)
from TauFW.Framework._internal.runtime.run_lock import RunLockError, read_lock
from TauFW.Framework._internal.version import current_version, VersionChecker

__all__ = ['Framework', 'load_run', 'RunPlan', 'RunSummary', 'RunDirectoryError', 'RetryError', 'RunLockError',
           'read_lock',
           'Recipe', 'StageSpec', 'Issue', 'RecipeError',
           'check_recipe', 'RecipeCheck',
           'RunRecord', 'RunState', 'StageRecord', 'STAGES', 'StageState', 'StageOutcome',
           'Reporter', 'FrameworkReporter', 'SilentReporter', 'EventReporter', 'current_version', 'VersionChecker']
