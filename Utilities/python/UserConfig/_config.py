# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Read the user config: Analyses/UserConfig.yaml of this checkout, or the file $TAUFW_USER_CONFIG names.

The reading side, for everyone (users' scripts and TauFW alike): one way to read, so both see the same values.
Making the file and reporting its state are in manage.py.

Inputs:  the user config file (YAML, optional).
Outputs: Config (read-only values). Nothing is written.
"""
import os
from pathlib import Path

if __name__.startswith("TauFW."):
    from ..FIO import FileIO
    from ..Paths import TAUFW_ROOT
else:  # FastSetup imports this package as UserConfig (Utilities/python on sys.path), before cmsenv
    from FIO import FileIO
    from Paths import TAUFW_ROOT
from ._template import HEADER_KEY, VERSION

FILE_NAME = "UserConfig.yaml"
ENVVAR = "TAUFW_USER_CONFIG"  # another file instead of Analyses/UserConfig.yaml (e.g. one for several checkouts)
DEFAULT_PATH = TAUFW_ROOT / "Analyses" / FILE_NAME
CREATE_COMMAND = "python3 taufw.py userconfig"


class UserConfigError(Exception):
    """The user config cannot be read, or a required key is missing; the message names the file."""


# =============================================================================
# ==== Reading ====

def location():
    """The user config file: $TAUFW_USER_CONFIG if set (as given, nothing expanded), else Analyses/UserConfig.yaml."""
    return Path(os.environ.get(ENVVAR) or DEFAULT_PATH)


def load(path=None, files=None):
    """The user config (Config) of `path` (default: location()). A missing file gives an empty Config
    (exists False). Raises UserConfigError if the file is not a YAML mapping with a valid taufw_user header."""
    path = Path(path) if path else location()
    files = files or FileIO()
    if not files.exists(path):
        return Config(path, None)
    try:
        data = files.read_yaml(path)
    except Exception as error:  # OSError, yaml.YAMLError, no PyYAML: shown with the file's name
        raise UserConfigError("%s: cannot be read: %s" % (path, error))
    problem = _header_problem(data)
    if problem:
        raise UserConfigError("%s: %s (a new file: delete this one, then `%s`)" % (path, problem, CREATE_COMMAND))
    return Config(path, data)


# =============================================================================
# ==== Config ====

class Config:
    """The values of one user config, read-only. Keys of nested sections are joined with dots:
    config.get("runs.run_root") is the run_root key of the runs section.

        path      the file
        exists    False: there is no file (every get gives its default)
        version   the format of the file (taufw_user.version), None without a file
        reviewed  taufw_user.reviewed (False without a file)
    """

    def get(self, key, default=None):
        """The value of a dotted key, or `default` if a part of it is missing."""
        value = self._values
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                return default
            value = value[part]
        return value

    def require(self, key):
        """The value of a dotted key; raises UserConfigError naming the file and the key if it is missing."""
        missing = object()
        value = self.get(key, missing)
        if value is missing:
            raise UserConfigError("%s: no %r: add it to your user config%s"
                                  % (self.path, key, "" if self.exists else " (create it with `%s`)" % CREATE_COMMAND))
        return value

    def section(self, name):
        """A copy of one top-level section (a mapping), {} if there is none."""
        value = self._values.get(name)
        return dict(value) if isinstance(value, dict) else {}

    @property
    def values(self):
        """A copy of every setting (the header excluded)."""
        return dict(self._values)

    # ===== Construction =====

    def __init__(self, path, data):
        """data: the mapping read from the file (checked by load()), or None without a file."""
        self.path = Path(path)
        self.exists = data is not None
        header = (data or {}).get(HEADER_KEY, {})
        self.version = header.get("version")
        self.reviewed = header.get("reviewed", False)
        self._values = {key: value for key, value in (data or {}).items() if key != HEADER_KEY}

    def __repr__(self):
        return "<UserConfig.Config %s%s>" % (self.path, "" if self.exists else " (no file)")


# =============================================================================
# ==== Helpers ====

def _header_problem(data):
    """What is wrong with the file's mapping and its taufw_user header (None if nothing)."""
    if not isinstance(data, dict):
        return "not a YAML mapping"
    header = data.get(HEADER_KEY)
    if not isinstance(header, dict):
        return "no %s header" % (HEADER_KEY)
    version = header.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or not 1 <= version <= VERSION:
        return "%s.version must be a whole number from 1 to %d (got %r)" % (HEADER_KEY, VERSION, version)
    if not isinstance(header.get("reviewed"), bool):
        return "%s.reviewed must be true or false (got %r)" % (HEADER_KEY, header.get("reviewed"))
    return None
