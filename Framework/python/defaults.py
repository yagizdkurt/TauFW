# Author: Yagizhan Dinckurt (October 2026)
"""Shared defaults of the Framework: file names, the run and bundle directories, timing and the time format.

Every other module takes these values from here, so a default is changed in one place only.
"""
import os
from datetime import datetime

__all__ = ['DEFAULT_RUN_ROOT', 'RUN_RECORD_NAME', 'RUN_LOG_NAME', 'DEFAULT_POLL_SECONDS', 'TIME_FORMAT',
           'RECIPE_NAME', 'BUNDLE_DIR_NAME', 'ANALYSES_DIR', 'timestamp', 'default_file_io']


# =============================================================================
# ================================= CONSTANTS =================================


DEFAULT_RUN_ROOT     = "taufw_runs"         # parent directory of all run directories
RUN_RECORD_NAME      = "run.json"           # the saved state of a run, inside its run directory
RUN_LOG_NAME         = "run.log"            # plain-text copy of the messages, inside its run directory
DEFAULT_POLL_SECONDS = 600                  # seconds between two checks with --wait
TIME_FORMAT          = "%Y-%m-%d %H:%M:%S"  # times written to run.json
RECIPE_NAME          = "recipe.yml"         # the recipe inside an analysis bundle directory
BUNDLE_DIR_NAME      = "bundle"             # copy of the bundle files a run uses, inside its run directory
ANALYSES_DIR         = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
                       os.path.realpath(__file__)))), "Analyses")  # the analysis bundles of this checkout


# =============================================================================
# ================================== HELPERS ==================================


def timestamp(moment=None):
    """The time as written to run.json (default: now)."""
    return (moment or datetime.now()).strftime(TIME_FORMAT)


def default_file_io():
    """A new TauFW.Utilities FileIO, used to read and write files when the caller passes none.
    It is imported here, on first use, so importing the Framework stays light."""
    from TauFW.Utilities.FIO import FileIO
    return FileIO()
