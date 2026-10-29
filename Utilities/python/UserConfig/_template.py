# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""The settings TauFW reads from the user config, and the text of a new file (create() in manage.py).

SETTINGS lists every setting: its dotted key, its kind (checked by setting_problems()) and an example value. A new
file writes a value for every setting create() could guess or take over (manage.py), and the others as comment lines
with the example (not set: the reader uses its own default). A setting with `written` is always written, with its
example as the value. Settings under HEADER_KEY are written into the header. What each setting does is explained in
Docs/Develop/InProgramMDs/UserConfig.md (shown beside the editor), not in the file. To add a setting, add it here,
there and to its reader (Framework/python/_internal/user_settings.py for the Framework). Raise VERSION when the
format changes, not when a setting is added.
"""
import json
from collections import namedtuple

HEADER_KEY = "taufw_user"  # the header mapping: version, reviewed, and the settings of TauFW itself
VERSION = 1                # the format of the file

Setting = namedtuple("Setting", "key kind example written", defaults=(False,))

# kind: 'run_root' an absolute directory, nothing expanded (as run_root in a recipe); 'pattern' a non-empty
# directory pattern ($ERA, $CHANNEL, ... filled by PicoProducer); 'directory' a non-empty directory; 'text' any
# string; 'count' a whole number from 1; 'boolean' true or false.
SETTINGS = (
    Setting("taufw_user.notifications", "boolean", True, written=True),
    Setting("taufw_user.open_menu_on_start", "boolean", True, written=True),
    Setting("runs.run_root", "run_root", "/afs/cern.ch/work/u/user/taufw_runs"),
    Setting("production.batch", "text", "HTCondor"),
    Setting("production.queue", "text", "workday"),
    Setting("production.batchopts", "text", ""),
    Setting("production.outdir", "pattern", "/eos/user/u/user/taufw/output/$ERA/$CHANNEL/$SAMPLE"),
    Setting("production.nanodir", "pattern", "/eos/user/u/user/taufw/samples/nano/$ERA/$DAS"),
    Setting("production.tmpskimdir", "directory", "/tmp/user"),
    Setting("production.ncores", "count", 4),
    Setting("production.hadd.cmd", "text", "python3 haddnano.py"),
    Setting("production.hadd.maxopenfiles", "count", 500),
)


# =============================================================================
# ==== New file ====

def default_text(values=None):
    """The YAML text of a new user config: its header (reviewed: false), then every setting of SETTINGS, with the
    value of `values` ({dotted key: value}) or as a comment line."""
    values = values or {}
    lines = [
        "%s:" % (HEADER_KEY),
        "  version: %d  # Do Not Change!" % (VERSION),
        "  reviewed: false  # set true!",
    ]
    opened = (HEADER_KEY,)  # the sections written so far, e.g. ('production', 'hadd')
    for setting in SETTINGS:
        *sections, name = setting.key.split(".")
        common = 0
        while common < min(len(opened), len(sections)) and opened[common] == sections[common]:
            common += 1
        for depth in range(common, len(sections)):
            if depth == 0:
                lines.append("")
            lines.append("  " * depth + "%s:" % (sections[depth]))
        opened = tuple(sections)
        indent = "  " * len(sections)
        if setting.key in values or setting.written:
            lines.append("%s%s: %s" % (indent, name, _yaml(values.get(setting.key, setting.example))))
        else:
            lines.append("%s# %s: %s" % (indent, name, _yaml(setting.example)))
    return "\n".join(lines) + "\n"


# =============================================================================
# ==== Helpers ====

def _yaml(value):
    """A value as YAML: strings quoted (JSON strings are valid YAML), numbers as they are."""
    return json.dumps(value)
