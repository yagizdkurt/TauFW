# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""The user config: personal and machine settings of one TauFW user, in Analyses/UserConfig.yaml.

    from TauFW.Utilities import UserConfig

    config = UserConfig.load()                    # Analyses/UserConfig.yaml, or the file $TAUFW_USER_CONFIG names
    run_root = config.get("runs.run_root")        # None if the key (or the file) is missing
    run_root = config.require("runs.run_root")    # UserConfigError naming the file and the key if missing

The file is made by FastSetup or `python3 taufw.py userconfig` (create()), ignored by git, and never overwritten.
check() gives the one-line warnings taufw.py check, plan and start show: no file, or not reviewed yet. Which settings
the file holds is not decided yet: the new file has only its header (_template.py says how to add one).

Importing needs only the standard library (reading needs PyYAML); FastSetup imports this package before cmsenv.
"""

from ._userconfig import (FILE_NAME, ENVVAR, DEFAULT_PATH, CREATE_COMMAND, Config, UserConfigError,
                          location, load, check, create)

__all__ = ["FILE_NAME", "ENVVAR", "DEFAULT_PATH", "CREATE_COMMAND", "Config", "UserConfigError",
           "location", "load", "check", "create"]
