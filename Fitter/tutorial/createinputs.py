#!/usr/bin/env python3
# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""LEGACY command: Fitter/tutorial/createinputs.py moved to Histogrammer/shapes/tutorial/createinputs.py (CL §22).

The script fills histograms and writes the input shapes of a fit; it imports nothing of the fit, so it moved to
the Histogrammer (step 2 of the isolation work). This stub runs nothing: it prints the command to type instead (the
same arguments, from the same working directory, so relative paths keep working and the shapes land where they did)
and exits with status 2.

    cd Fitter/tutorial; python3 createinputs.py -y 2018 ...
        ->  LEGACY message with: python3 ../../Histogrammer/shapes/tutorial/createinputs.py -y 2018 ...

Deleted at the migration point (docs/Refactor-2025/TODO.md §8); see Histogrammer/README.md.
"""
import os
import shlex
import sys

OLD_SCRIPT  = "Fitter/tutorial/createinputs.py"
NEW_SCRIPTS = (("Histogrammer", "shapes", "tutorial", "createinputs.py"),)  # the new command, from the TauFW directory
EXIT_STATUS = 2  # as for a usage error: nothing ran

MESSAGE = """\
LEGACY: %s moved to the Histogrammer (changelog §22). Run instead, with the same options and from the same
directory:

%s

Nothing was run. This message replaces the old script until the migration point (see Histogrammer/README.md)."""


def new_commands(argv, cwd):
    """The command line to type instead of this script with ARGV, as seen from the working directory `cwd`."""
    taufw = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
