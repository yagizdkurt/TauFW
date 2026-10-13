"""Framework adapters for the Utilities menu navigation.

Discovery, path resolution, record access, validation, and CLI dispatch belong
here. Presentation and screen transitions live in TauFW.Utilities.Menu.
"""
import os
from argparse import Namespace
from pathlib import Path

from TauFW.Framework.defaults import DEFAULT_POLL_SECONDS, DEFAULT_RUN_ROOT, RUN_RECORD_NAME
from TauFW.Framework.run_record import RunRecord, RunState
from TauFW.Utilities.Menu import ConsoleUI, MenuNavigation


class _Operations:
    """Supply Framework operations without owning screens or navigation."""

    # =========================================================================
    # ================================= SETUP =================================

    def __init__(self, commands, launch_dir=None, recipes_dir=None):
        self.commands = commands
        self.launch_dir = Path(launch_dir or os.getcwd()).resolve()
        self.recipes_dir = Path(recipes_dir or Path(__file__).resolve().parents[1] / "recipes")

    def resolve_path(self, value):
        path = Path(value).expanduser()
        return str((path if path.is_absolute() else self.launch_dir / path).resolve())

    # =========================================================================
    # =============================== DISCOVERY ===============================

    def recipes(self):
        return sorted((p for p in self.recipes_dir.iterdir()
                       if p.is_file() and p.suffix in (".yml", ".yaml", ".json")),
                      key=lambda p: p.name) if self.recipes_dir.is_dir() else []

    def runs(self):
        root = self.launch_dir / DEFAULT_RUN_ROOT
        runs = []
        if root.is_dir():
            for directory in root.iterdir():
                if directory.is_dir() and (directory / RUN_RECORD_NAME).is_file():
                    try:
                        record = self.load_run(str(directory))
                        runs.append((record.created, str(directory),
                                     (record.run_id, record.state, record.updated)))
                    except Exception:
                        runs.append(("", str(directory), (directory.name, None, None)))
        return sorted(runs, key=lambda row: (row[0], row[1]), reverse=True)

    # =========================================================================
    # ========================== VALIDATION AND DISPATCH ======================

    @staticmethod
    def load_run(path):
        return RunRecord.load(path)

    @staticmethod
    def can_advance(record):
        return not RunState(record.state).finished

    @staticmethod
    def validate_poll(value):
        poll = int(value)
        if poll <= 0:
            raise ValueError("Polling interval must be positive.")
        return poll

    def execute(self, command, **values):
        args = dict(verbose=0, wait=False, poll=DEFAULT_POLL_SECONDS, run_root=None, local=False, maxevts=100)
        args.update(values)
        return self.commands[command](Namespace(**args))


# =============================================================================
# ================================== LAUNCH ===================================


def Menu(commands, ui, launch_dir=None, recipes_dir=None):
    """Build navigation with Framework callbacks, preserving the constructor API."""
    return MenuNavigation(ui, _Operations(commands, launch_dir, recipes_dir))


def run_menu(commands, parser):
    """Connect the terminal UI to existing CLI handlers; return a CLI exit code."""
    ui = ConsoleUI.open(parser)
    if ui is None:
        return 1
    try:
        return Menu(commands, ui).run()
    except Exception as error:
        if not ui.is_terminal_error(error):
            raise
        ui.terminal_failure(error, parser)
        return 1
