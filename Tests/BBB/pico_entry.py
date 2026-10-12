"""Child-process entry: run one PicoProducer script against an already prepared mirror.

Each invocation is a fresh interpreter, like a user typing the command in a shell, so module-level
state (the cached configuration, imported sample lists) never leaks between commands.
Usage: python pico_entry.py MIRROR SCRIPT [ARGUMENTS...]
"""
from pathlib import Path
import runpy
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "support"))
from bootstrap import attach  # noqa: E402


def main():
    mirror, script = sys.argv[1], sys.argv[2]
    attach(mirror)
    import ROOT
    ROOT.PyConfig.IgnoreCommandLineOptions = True
    ROOT.gROOT.SetBatch(True)
    sys.argv = [script] + sys.argv[3:]
    sys.path.insert(0, str(Path(script).parent))
    runpy.run_path(script, run_name="__main__")


if __name__ == "__main__":
    main()
