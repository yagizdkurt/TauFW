# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""The values of a new user config (create() in manage.py): guessed from the host, or taken over from the
PicoProducer configuration a user already has.

Only lxplus is guessed (TauFW runs there): the EOS and AFS areas of the user. Elsewhere nothing is guessed, and the
readers keep their own defaults. An existing PicoProducer/config/config.json wins over a guess, so a directory a
user chose there stays the same for the recipes (it is read as a JSON file; this package never imports
PicoProducer).
"""
import getpass
import json
import os
import platform

if __name__.startswith("TauFW."):
    from ..Paths import PICO_PRODUCER_ROOT, afs_work, eos_user
else:  # FastSetup imports this package as UserConfig (Utilities/python on sys.path), before cmsenv
    from Paths import PICO_PRODUCER_ROOT, afs_work, eos_user

PICO_CONFIG = PICO_PRODUCER_ROOT / "config" / "config.json"
PICO_KEYS = {  # key of the PicoProducer configuration -> setting of the user config
    'batch': "production.batch", 'queue': "production.queue", 'batchopts': "production.batchopts",
    'outdir': "production.outdir", 'nanodir': "production.nanodir", 'tmpskimdir': "production.tmpskimdir",
    'ncores': "production.ncores", 'haddcmd': "production.hadd.cmd", 'maxopenfiles': "production.hadd.maxopenfiles",
}


# =============================================================================
# ==== Values ====

def new_values(host=None, user=None, pico_config=PICO_CONFIG):
    """({dotted key: value}, [source lines]) for a new user config: the lxplus guesses, then the values of the
    PicoProducer configuration over them. An empty value of the configuration is not taken over."""
    host = platform.node() if host is None else host
    user = user or getpass.getuser()
    values, sources = {}, []
    if 'lxplus' in host:
        values.update(_lxplus(user))
        sources.append("Guessed for lxplus (user %s)." % (user))
    taken = _from_pico_config(pico_config)
    if taken:
        values.update(taken)
        sources.append("Taken from %s: %s." % (pico_config, ", ".join(sorted(taken))))
    return values, sources


# =============================================================================
# ==== Helpers ====

def _lxplus(user):
    """The guesses for lxplus: the job output in a taufw/ directory of the user's EOS area (not spread over its top),
    and the runs in the AFS work area if it exists (not everyone has one; a run root that does not exist would stop
    `start`)."""
    eos = eos_user(user)
    values = {
        "production.batch": "HTCondor",
        "production.outdir": eos + "/taufw/output/$ERA/$CHANNEL/$SAMPLE",
        "production.nanodir": eos + "/taufw/samples/nano/$ERA/$DAS",
    }
    work = afs_work(user)
    if os.path.isdir(work):
        values["runs.run_root"] = work + "/taufw_runs"
    return values


def _from_pico_config(path):
    """The settings found in the PicoProducer configuration file (none if it does not exist or cannot be read)."""
    try:
        with open(str(path)) as stream:
            config = json.load(stream)
    except (OSError, ValueError):
        return {}
    if not isinstance(config, dict):
        return {}
    taken = {}
    for key, setting in PICO_KEYS.items():
        value = config.get(key)
        if isinstance(value, str) and value or isinstance(value, int) and not isinstance(value, bool) and value > 0:
            taken[setting] = value
    return taken
