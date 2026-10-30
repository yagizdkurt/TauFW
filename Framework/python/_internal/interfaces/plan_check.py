# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""The whole plan of a recipe for the menu's plan screen, made in a process of its own (interactive._PlanCheck).

    python -m TauFW.Framework._internal.interfaces.plan_check <recipe> <output.json>

The plan screen opens with a quick plan (without the checks that open data files: the tuples' branches, slow on
EOS) and starts this; when <output.json> is there (written whole, then renamed), its view replaces the quick one.
ROOT, which those checks load, so stays out of the menu's process.
"""
import json
import os
import sys


def main(argv=None):
    path, output = (sys.argv[1:] if argv is None else argv)[:2]
    from TauFW.Framework._internal.interfaces.interactive import _Operations
    view = _Operations().prepare_plan(path)
    with open(output + ".part", "w") as stream:
        json.dump(view, stream)
    os.replace(output + ".part", output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
