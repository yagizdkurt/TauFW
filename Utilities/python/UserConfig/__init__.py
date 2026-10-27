# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""The user config: personal and machine settings of one TauFW user, in Analyses/UserConfig.yaml.

Reading, for everyone (analysis scripts and TauFW itself read the same way, so they see the same values):

    from TauFW.Utilities import UserConfig

    config = UserConfig.load()                    # Analyses/UserConfig.yaml, or the file $TAUFW_USER_CONFIG names
    run_root = config.get("runs.run_root")        # None if the key (or the file) is missing
    run_root = config.require("runs.run_root")    # UserConfigError naming the file and the key if missing
    UserConfig.location()                         # where the file is

Managing the file (make it, report its state) is in UserConfig.manage, for FastSetup, taufw.py and the menu.
The file is ignored by git and never overwritten. Which settings it holds is not decided yet: the new file has only
its header (_template.py says how to add a setting).

Importing needs only the standard library (reading needs PyYAML); FastSetup imports this package before cmsenv.
"""

from ._config import Config, UserConfigError, location, load

__all__ = ["Config", "UserConfigError", "location", "load"]
