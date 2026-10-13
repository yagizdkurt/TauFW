"""Framework adapters for the Utilities menu navigation.

Discovery, path resolution, record access, validation, and CLI dispatch belong
here. Presentation and screen transitions live in TauFW.Utilities.Menu.
"""
import os
from argparse import Namespace
from pathlib import Path

from TauFW.Framework.defaults import (ANALYSES_DIR, DEFAULT_POLL_SECONDS, DEFAULT_RUN_ROOT, RECIPE_NAME,
                                      RUN_RECORD_NAME)
from TauFW.Framework.run_record import RunRecord, RunState
from TauFW.Framework.recipe import Recipe
from TauFW.Framework.framework import Framework
from TauFW.Framework.reporting import SilentReporter
from TauFW.Utilities.Menu import ConsoleUI, MenuNavigation


class _Operations:
    """Supply Framework operations without owning screens or navigation."""

    # =========================================================================
    # ================================= SETUP =================================

    def __init__(self, commands, launch_dir=None, recipes_dir=None):
        self.commands = commands
        self.launch_dir = Path(launch_dir or os.getcwd()).resolve()
        self.recipes_dir = Path(recipes_dir or ANALYSES_DIR)

    def resolve_path(self, value):
        path = Path(value).expanduser()
        return str((path if path.is_absolute() else self.launch_dir / path).resolve())

    # =========================================================================
    # =============================== DISCOVERY ===============================

    def recipes(self):
        """The analysis bundles (directories with a recipe.yml) and loose recipe files in the recipes directory."""
        return sorted((p for p in self.recipes_dir.iterdir()
                       if (p.is_dir() and (p / RECIPE_NAME).is_file())
                       or (p.is_file() and p.suffix in (".yml", ".yaml", ".json"))),
                      key=lambda p: p.name) if self.recipes_dir.is_dir() else []

    @staticmethod
    def _recipe_view(recipe, path):
        """Plain presentation data; Utilities never needs Framework objects."""
        return dict(name=recipe.name, path=str(path),
                    stages=tuple((stage.id, stage.stage) for stage in recipe.stages), notes=())

    def recipe_preview(self, path):
        """Read recipe metadata only, without constructing stage APIs."""
        return self._recipe_view(Recipe.load(str(path)), path)

    def prepare_review(self, path):
        """Reload and dry-plan the selected recipe without terminal output or writes."""
        recipe = Recipe.load(str(path))
        reporter = SilentReporter()
        plan = Framework.from_recipe(recipe, reporter=reporter).plan()
        view = self._recipe_view(recipe, path)
        notes = []
        for stage in plan.stages:
            if stage.note:
                notes.append("%s: %s" % (stage.stage, stage.note))
            notes.extend("%s: %s" % (stage.stage, note)
                         for note in getattr(stage.plan, "notes", ()))
        notes.extend(message for kind, message in reporter.messages if kind == "warning")
        view["notes"] = tuple(notes)
        return view

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
