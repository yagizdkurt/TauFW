# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Manage the user config file: make it, check its settings, and report its state. For the tools that look after
the file and read TauFW's settings (FastSetup's setup_tools.py, taufw.py, the Framework, the menu), not for
analysis scripts: those only read it (TauFW.Utilities.UserConfig).

    from TauFW.Utilities.UserConfig import manage

    manage.create()            # FastSetup, `taufw.py userconfig`: a new file if there is none
    for warning in manage.check():
        print(warning)         # taufw.py check, plan, start: one line each
    manage.setting_problems(config, "production")   # what is wrong with TauFW's settings of a section

Inputs:  the user config file (through load()); for a new file the host and PicoProducer/config/config.json.
Outputs: a new user config file (create(), never over an existing one); problems and one-line warnings.
"""
import os
from pathlib import Path
import posixpath

if __name__.startswith("TauFW."):
    from ..FIO import FileIO
else:  # FastSetup imports this package as UserConfig (Utilities/python on sys.path), before cmsenv
    from FIO import FileIO
from ._config import (FILE_NAME, ENVVAR, DEFAULT_PATH, CREATE_COMMAND, UserConfigError,
                      location, load)
from ._guesses import new_values
from ._template import SETTINGS, default_text

__all__ = ["FILE_NAME", "ENVVAR", "DEFAULT_PATH", "CREATE_COMMAND", "SETTINGS", "create", "check",
           "setting_problems"]


# =============================================================================
# ==== State ====

def check(config=None):
    """One-line warnings for the commands that run an analysis (taufw.py check, plan, start): no file, a file that
    cannot be read, a setting of TauFW with a wrong value, or a file not reviewed yet. Never raises: the commands
    go on (the readers of a wrong setting stop where they use it)."""
    try:
        config = config or load()
    except UserConfigError as error:
        return [str(error)]
    if not config.exists:
        return ["No user config %s: create it with `%s`" % (config.path, CREATE_COMMAND)]
    warnings = ["%s: %s" % (config.path, problem) for problem in setting_problems(config)]
    if not config.reviewed:
        warnings.append("User config %s is not reviewed yet: check its values, then set reviewed: true"
                        % (config.path))
    return warnings


def setting_problems(config, section=None):
    """What is wrong with the settings of SETTINGS that the file sets (all, or those of one top-level section):
    one line each, starting with the dotted key. A setting that is not set is never a problem."""
    problems = []
    for setting in SETTINGS:
        if section and setting.key != section and not setting.key.startswith(section + "."):
            continue
        missing = object()
        value = config.get(setting.key, missing)
        if value is not missing:
            problem = _kind_problem(setting.kind, value)
            if problem:
                problems.append("%s: %s (got %r)" % (setting.key, problem, value))
    return problems


# =============================================================================
# ==== Creation ====

def create(path=None, files=None, values=None, sources=()):
    """Write a new user config to `path` (default: location()) if there is none. Returns True if it was written,
    False if a file was there already (it is never changed).
    values/sources: the settings to write and where they came from (default: guessed for this host, or taken from
    the PicoProducer configuration, _guesses.py); the other settings are written as comment lines."""
    path = Path(path) if path else location()
    files = files or FileIO()
    if files.exists(path):
        return False
    if values is None:
        values, sources = new_values()
    files.write_text(path, default_text(values, sources))  # exclusive: never replaces a file made in the meantime
    return True


# =============================================================================
# ==== Helpers ====

def _kind_problem(kind, value):
    """What is wrong with a value of a kind of SETTINGS (None if nothing)."""
    if kind == "boolean":
        return None if isinstance(value, bool) else "must be true or false"
    if kind == "count":
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            return "must be a whole number from 1"
        return None
    if not isinstance(value, str):
        return "must be text"
    if kind in ("pattern", "directory") and not value.strip():
        return "must not be empty"
    if kind == "run_root":
        if not (posixpath.isabs(value) or os.path.isabs(value)):  # as run_root in a recipe (Framework bundle.py)
            return "must be an absolute directory"
        if "$" in value or "~" in value:
            return "nothing is expanded: write the directory without ~ or $VARIABLES"
    return None
