#!/usr/bin/env python3
# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""LEGACY command: Plotter/plot.py was renamed to Histogrammer/fillhists.py (CL §21).

This script used to fill and draw the control plots. That code is now Histogrammer/fillhists.py, with the same
options. This stub runs nothing: it prints the command to type instead (the same arguments, from the same working
directory, so relative paths keep working) and exits with status 2.

    python3 plot.py -y 2025 -c mutau      ->  LEGACY message with: python3 ../Histogrammer/fillhists.py -y 2025 -c mutau

Deleted at the migration point (Docs/Develop/Refactor-2025/TODO.md §8); see Plotter/README.md.
"""
import os
import shlex
import sys

OLD_SCRIPT  = "Plotter/plot.py"
NEW_SCRIPTS = (("Histogrammer", "fillhists.py"),)  # the new command(s), relative to the TauFW directory
EXIT_STATUS = 2                                    # as for a usage error: nothing ran

MESSAGE = """\
LEGACY: %s was renamed (changelog §21). Run instead, with the same options:

%s

Nothing was run. This message replaces the old script until the migration point (see Plotter/README.md)."""


def new_commands(argv, cwd):
    """The command lines to type instead of `plot.py ARGV`, as seen from the working directory `cwd`."""
    taufw = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    commands = []
    for parts in NEW_SCRIPTS:
        script = os.path.join(taufw, *parts)
        try:
            script = os.path.relpath(script, cwd)
        except ValueError:  # another drive (Windows): keep the absolute path
            pass
        commands.append("    python3 " + " ".join(shlex.quote(arg) for arg in [script] + list(argv)))
    return "\n".join(commands)


def main(argv):
    print(MESSAGE % (OLD_SCRIPT, new_commands(argv, os.getcwd())), file=sys.stderr)
    return EXIT_STATUS


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
