# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""The settings TauFW reads from the user config, and the text of a new file (create() in manage.py).

SETTINGS lists every setting: its dotted key, its kind (checked by setting_problems()) and the comment written above
it in a new file. A new file writes a value for every setting create() could guess or take over (manage.py), and the
others as comment lines (not set: the reader uses its own default). To add a setting, add it here and to its
reader (Framework/python/_internal/user_settings.py for the Framework). Raise VERSION when the format changes, not
when a setting is added.
"""
import json
from collections import namedtuple

HEADER_KEY = "taufw_user"  # the header mapping: version, reviewed
VERSION = 1                # the format of the file

Setting = namedtuple("Setting", "key kind example comment")

# kind: 'run_root' an absolute directory, nothing expanded (as run_root in a recipe); 'pattern' a non-empty
# directory pattern ($ERA, $CHANNEL, ... filled by PicoProducer); 'directory' a non-empty directory; 'text' any
# string; 'count' a whole number from 1; 'boolean' true or false.
SETTINGS = (
    Setting("notifications", "boolean", True,
            "terminal bells for completed operations and errors; false disables them (default: true)"),
    Setting("open_menu_on_start", "boolean", True,
            "source taufw.sh opens the menu; false: it only activates TauFW (default: true)"),
    Setting("runs.run_root", "run_root", "/afs/cern.ch/work/u/user/taufw_runs",
            "where your runs go when the recipe has no run_root and you give no --run-root"),
    Setting("production.batch", "text", "HTCondor", "the batch system: HTCondor, SLURM, ..."),
    Setting("production.queue", "text", "workday", "the queue (HTCondor: job flavour), when the recipe gives none"),
    Setting("production.batchopts", "text", "", "extra batch options, when the recipe gives none"),
    Setting("production.outdir", "pattern", "/eos/user/u/user/taufw/output/$ERA/$CHANNEL/$SAMPLE",
            "the output of the jobs, before the merge"),
    Setting("production.nanodir", "pattern", "/eos/user/u/user/taufw/samples/nano/$ERA/$DAS",
            "the output of skim jobs"),
    Setting("production.tmpskimdir", "directory", "/tmp/user", "a temporary directory of skim jobs"),
    Setting("production.ncores", "count", 4,
            "processes that count events and check files at once, when the recipe gives none"),
    Setting("production.hadd.cmd", "text", "python3 haddnano.py", "another command to merge the files"),
    Setting("production.hadd.maxopenfiles", "count", 500, "files the merge opens at once"),
)


# =============================================================================
# ==== New file ====

def default_text(values=None, sources=()):
    """The YAML text of a new user config: its header (reviewed: false), then every setting of SETTINGS, with the
    value of `values` ({dotted key: value}) or as a comment line. sources: lines on where the values came from."""
    values = values or {}
    lines = HEAD.splitlines() + ["# %s" % (source) for source in sources] + [
        "",
        "%s:" % (HEADER_KEY),
        "  version: %d           # the format of this file (set by TauFW, do not change)" % (VERSION),
        "  reviewed: false      # true: you checked this file",
    ]
    opened = ()  # the sections written so far, e.g. ('production', 'hadd')
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
        lines.append("%s# %s" % (indent, setting.comment))
        if setting.key in values:
            lines.append("%s%s: %s" % (indent, name, _yaml(values[setting.key])))
        else:
            lines.append("%s# %s: %s" % (indent, name, _yaml(setting.example)))
    return "\n".join(lines) + "\n"


HEAD = """\
# TauFW user configuration: your personal and machine settings.
#
# Made by the setup (or `taufw userconfig`). Git ignores this file and nothing overwrites it.
# Check the values below, then set reviewed to true: until then, taufw check, plan and start warn.
# A line that starts with # is not set: TauFW uses its own default. Remove the # to set it.
# Your own sections (e.g. mystudy:) are kept: read them with TauFW.Utilities.UserConfig."""


# =============================================================================
# ==== Helpers ====

def _yaml(value):
    """A value as YAML: strings quoted (JSON strings are valid YAML), numbers as they are."""
    return json.dumps(value)
