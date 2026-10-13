"""Pre-install checklist entry point. Writes component IDs; never installs tools.

Run by FastSetup.sh directly from the checkout before cmsenv or scram b.
"""
import sys
from argparse import ArgumentParser
from pathlib import Path

if __package__:
    from ._menu import ConsoleUI
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from Menu import ConsoleUI

# =============================================================================
# ============================== SETUP COMPONENTS =============================

COMPONENTS = (
    ("tauidsfs", "TauIDSFs"),
    ("htt", "HTT lepton efficiencies"),
    ("combine", "Combine + CombineHarvester"),
    ("run2-jme", "Standalone NanoAODTools (Run 2 JEC/JER)"),
)


def main(argv=None):
    parser = ArgumentParser(description="Choose FastSetup components without installing them.")
    parser.add_argument("--output", required=True, help="File for selected component IDs.")
    parser.add_argument("--selected", nargs="*", choices=[name for name, _ in COMPONENTS], default=[])
    args = parser.parse_args(argv)
    ui = ConsoleUI.open(parser)
    if ui is None:
        return 1
    try:
        selected = ui.setup_checklist(COMPONENTS, args.selected)
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        if not ui.is_terminal_error(error):
            raise
        ui.terminal_failure(error, parser)
        return 1
    if selected is None:
        return 130
    Path(args.output).write_text("".join(name + "\n" for name in selected), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
