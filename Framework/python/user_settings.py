# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""The Framework's settings from the user config (TauFW.Utilities.UserConfig): the default run root, and the
personal settings of a production stage.

Precedence: the command line and the recipe come first, then the user config, then the module's own default
(run_root: taufw_runs/; PicoProducer: its configuration, PicoProducer/config/config.json or pico.config). The file
is read the same way as by a user's script (UserConfig.load). A setting with a wrong value raises UserConfigError
where it is used; manage.check() lists it beforehand as a warning.

Inputs:  the user config file (optional).
Outputs: values only; nothing is written.
"""
from collections import namedtuple

from TauFW.Utilities import UserConfig
from TauFW.Utilities.UserConfig import manage

__all__ = ['run_root', 'run_root_or_none', 'production_settings', 'production_problems', 'ProductionSettings',
           'PICO_CONFIG_KEYS', 'REQUEST_KEYS']

PICO_CONFIG_KEYS = {  # setting -> key of the PicoProducer configuration it replaces
    "production.batch": 'batch', "production.outdir": 'outdir', "production.nanodir": 'nanodir',
    "production.tmpskimdir": 'tmpskimdir', "production.hadd.cmd": 'haddcmd',
    "production.hadd.maxopenfiles": 'maxopenfiles',
}
# overrides: keys of the PicoProducer configuration the user config replaces; defaults: request fields it gives when
# the recipe gives none; used: the dotted keys of the settings used (sorted); path: the user config file.
ProductionSettings = namedtuple("ProductionSettings", "overrides defaults used path")

REQUEST_KEYS = {  # setting -> field of the production request it gives when the recipe gives none
    "production.queue": 'queue', "production.batchopts": 'batchopts', "production.ncores": 'ncores',
}


# =============================================================================
# ================================= READING ===================================


def run_root(config=None):
    """The user config's runs.run_root, or None if it is not set. Raises UserConfigError if it is wrong."""
    config = config or UserConfig.load()
    _raise_problems(config, "runs")
    return config.get("runs.run_root")


def run_root_or_none():
    """run_root(), or None if the user config cannot be read or its run_root is wrong (where a problem must not
    stop anything, e.g. a recipe's warnings; manage.check() reports it)."""
    try:
        return run_root()
    except UserConfig.UserConfigError:
        return None


def production_settings(config=None):
    """The user config's settings of a production stage (ProductionSettings). Raises UserConfigError if a
    production setting is wrong."""
    config = config or UserConfig.load()
    _raise_problems(config, "production")
    overrides, defaults, used = {}, {}, []
    for setting, key in PICO_CONFIG_KEYS.items():
        value = config.get(setting)
        if value is not None:
            overrides[key] = value
            used.append(setting)
    for setting, field in REQUEST_KEYS.items():
        value = config.get(setting)
        if value is not None:
            defaults[field] = value
            used.append(setting)
    return ProductionSettings(overrides, defaults, tuple(sorted(used)), config.path)


def production_problems():
    """The problems of the user config for a production stage: it cannot be read, or a production setting is
    wrong (one line each, naming the file). A missing file is not a problem: PicoProducer's defaults are used."""
    try:
        config = UserConfig.load()
    except UserConfig.UserConfigError as error:
        return [str(error)]
    return ["%s: %s" % (config.path, problem) for problem in manage.setting_problems(config, "production")]


# =============================================================================
# ================================= HELPERS ===================================


def _raise_problems(config, section):
    problems = manage.setting_problems(config, section)
    if problems:
        raise UserConfig.UserConfigError("%s: %s" % (config.path, "; ".join(problems)))
