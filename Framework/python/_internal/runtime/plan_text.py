# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""The words of a plan, the same for `taufw.py plan` and the menu's plan screen.

  run_root_line(recipe, given)        where the runs go, and why (--run-root, recipe, user config, default)
  inputs_line(stage_spec, stage, ...) a stage's inputs in full ('shapes <- fit, ...')
  inputs_short(stage_spec)            a stage's inputs in a few words, for a table ('fit, plots', '-')
  command_line(command)               a local command as it would be typed (with its environment variables)
"""
import os
import shlex
import sys

from TauFW.Framework._internal.defaults import DEFAULT_RUN_ROOT
from TauFW.Framework._internal import user_settings

__all__ = ["run_root_line", "inputs_line", "inputs_short", "command_line"]


def run_root_line(recipe, given=None):
    """Where the runs go, and why: --run-root, the recipe's run_root (absolute, nothing expanded), the user
    config's runs.run_root, or the default."""
    if given:
        return "%s (--run-root)" % (os.path.abspath(given))
    if recipe.run_root:
        return "%s (recipe)" % (recipe.run_root)
    from_user = user_settings.run_root_or_none()
    if from_user:
        return "%s (user config)" % (from_user)
    return "%s (default: no run_root in the recipe)" % (os.path.abspath(DEFAULT_RUN_ROOT))


def inputs_line(stage_spec, stage, sources=None):
    """The stage's inputs as written: 'none', or 'slot <- stage id', 'slot <- <directory> (run, stage, finished)'
    (another run's stage directory; sources: what its manifest says, see StagePlan.sources), 'slot <- external
    <pattern>' (data made outside TauFW), or for null 'slot <- outside this run (what null means for the slot,
    Stage.null_inputs)'."""
    if stage_spec.inputs is None:
        return "none"
    return ", ".join("%s <- %s" % (slot, _input_text(slot, value, stage, sources or {}))
                     for slot, value in stage_spec.inputs.items())


def _input_text(slot, value, stage, sources):
    if isinstance(value, dict) and 'path' in value:
        source = sources.get(slot)
        if source is None:  # cannot be read: the stage's note says why
            return value['path']
        return "%s (run %s, stage %s (%s), finished %s)" % (value['path'], source['run_id'], source['stage_id'],
                                                            source['stage'], source['finished'])
    if isinstance(value, dict):
        return "external %s" % (value['external'])
    return value or "outside this run (%s)" % (stage.null_inputs.get(slot, '?'))


def inputs_short(stage_spec):
    """The stage's inputs in a few words: the stage ids it reads, 'other run' ({path: ...}), 'external'
    ({external: ...}), 'outside' (null); '-' for none. Each once, in the recipe's order."""
    words = []
    for value in (stage_spec.inputs or {}).values():
        if isinstance(value, dict):
            words.append("other run" if 'path' in value else "external")
        else:
            words.append(value or "outside")
    return ", ".join(dict.fromkeys(words)) or "-"


def command_line(command):
    """A command line with its extra environment variables, with this Python shown as python3."""
    env = ["%s=%s" % (key, shlex.quote(value)) for key, value in getattr(command, 'env', ())]
    argv = [shlex.quote("python3" if i == 0 and a == sys.executable else a) for i, a in enumerate(command.argv)]
    return " ".join(env + argv)
