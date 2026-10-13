#!/usr/bin/env python3
"""Launch the Framework CLI from the TauFW repository root.

Usage (after setting up the CMSSW environment):
    python3 taufw.py                                         # interactive menu
    python3 taufw.py --help                                  # available commands
    python3 taufw.py plan Framework/recipes/example_mutau.yml # preview a pipeline

Commands and menu behavior live in Framework/scripts/taufw.py.
This launcher forwards arguments and preserves the CLI's exit code.
Relative recipe and run paths remain relative to your working directory.
"""

# =============================================================================
# ================================= IMPORTS ===================================
# =============================================================================

from pathlib import Path
import runpy


# =============================================================================
# ================================= LAUNCHER ==================================
# =============================================================================

def main():
    """Locate the CLI beside this file and execute its normal entry point."""
    repository_root = Path(__file__).resolve().parent
    cli_path = repository_root / "Framework" / "scripts" / "taufw.py"

    # Run the existing CLI as a script: it owns argument parsing and sys.exit().
    runpy.run_path(str(cli_path), run_name="__main__")


# =============================================================================
# ================================ ENTRY POINT ================================
# =============================================================================

if __name__ == "__main__":
    main()
