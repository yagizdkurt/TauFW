# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Manage the user config file: make it, and report its state. For the tools that look after the file (FastSetup's
setup_tools.py, taufw.py, the menu), not for analysis scripts: those only read it (TauFW.Utilities.UserConfig).

    from TauFW.Utilities.UserConfig import manage

    manage.create()            # FastSetup, `taufw.py userconfig`: a new file if there is none
    for warning in manage.check():
        print(warning)         # taufw.py check, plan, start: one line each

Inputs:  the user config file (through load()).
Outputs: a new user config file (create(), never over an existing one); one-line warnings (check()).
"""
from pathlib import Path

if __name__.startswith("TauFW."):
    from ..FIO import FileIO
else:  # FastSetup imports this package as UserConfig (Utilities/python on sys.path), before cmsenv
    from FIO import FileIO
from ._config import (FILE_NAME, ENVVAR, DEFAULT_PATH, CREATE_COMMAND, UserConfigError,
                      location, load)
from ._template import default_text

__all__ = ["FILE_NAME", "ENVVAR", "DEFAULT_PATH", "CREATE_COMMAND", "create", "check"]


# =============================================================================
# ==== State ====

def check(config=None):
    """One-line warnings for the commands that run an analysis (taufw.py check, plan, start): no file, a file that
    cannot be read, or one not reviewed yet. Never raises: the commands go on."""
    try:
        config = config or load()
    except UserConfigError as error:
        return [str(error)]
    if not config.exists:
        return ["No user config %s: create it with `%s`" % (config.path, CREATE_COMMAND)]
    if not config.reviewed:
        return ["User config %s is not reviewed yet: check its values, then set reviewed: true" % (config.path)]
    return []


# =============================================================================
# ==== Creation ====

def create(path=None, files=None):
    """Write a new user config to `path` (default: location()) if there is none. Returns True if it was written,
    False if a file was there already (it is never changed)."""
    path = Path(path) if path else location()
    files = files or FileIO()
    if files.exists(path):
        return False
    files.write_text(path, default_text())  # exclusive: never replaces a file made in the meantime
    return True
