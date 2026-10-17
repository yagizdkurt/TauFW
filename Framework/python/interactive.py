# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Framework adapters for the Utilities menu navigation.

Discovery, path resolution, record access, validation, and CLI dispatch belong
here. Presentation and screen transitions live in TauFW.Utilities.Menu.
"""
import json
import os
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

from TauFW.Framework.defaults import (ANALYSES_DIR, DEFAULT_POLL_SECONDS, DEFAULT_RUN_ROOT, RECIPE_NAME,
                                      RUN_RECORD_NAME)
from TauFW.Framework.run_record import RunRecord, RunState
from TauFW.Framework.recipe import Recipe, read_recipe, run_root_dir
from TauFW.Framework.validation import check_recipe
from TauFW.Framework.framework import Framework
from TauFW.Framework.reporting import SilentReporter
from TauFW.Utilities.Menu import ConsoleUI, MenuNavigation
from TauFW.Utilities.Process import BackgroundProcess


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
                    stages=tuple((stage.id, stage.stage, stage.description) for stage in recipe.stages),
                    notes=(), problems=(), warnings=tuple(str(warning) for warning in recipe.warnings))

    def recipe_preview(self, path):
        """Check the recipe (validation.py) without constructing stage APIs: its stages and every problem."""
        check = check_recipe(str(path))
        return dict(name=check.name, path=str(path), stages=check.stages, notes=(),
                    problems=tuple(str(issue) for issue in check.issues),
                    warnings=tuple(str(warning) for warning in check.warnings))

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

    def run_roots(self):
        """Where runs are looked for: taufw_runs/ in the launch directory, and the run_root of every recipe in the
        recipes directory (also of a recipe with problems, if its run_root can be read)."""
        roots = [self.launch_dir / DEFAULT_RUN_ROOT]
        for path in self.recipes():
            try:
                data = read_recipe(str(path))[0]
                value = data.get('run_root') if isinstance(data, dict) else None
                if isinstance(value, str) and value.strip():
                    roots.append(Path(run_root_dir(value)))
            except Exception:
                continue  # an unreadable recipe: its problems are shown with the recipe
        return list(dict.fromkeys(root.resolve() if root.is_absolute() else self.launch_dir / root
                                  for root in roots))

    def runs(self):
        runs = []
        for root in self.run_roots():
            if not root.is_dir():
                continue
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

    @staticmethod
    def grid_proxy_valid():
        """Check the existing proxy quietly; never prompt during menu startup."""
        try:
            result = subprocess.run(["voms-proxy-info", "--exists", "--valid", "0:01"],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def renew_grid_proxy(self):
        """Let VOMS read the certificate password directly from the terminal."""
        print("Enter your grid certificate password when prompted.")
        try:
            result = subprocess.run(["voms-proxy-init", "-voms", "cms"])
        except OSError as error:
            raise RuntimeError("Cannot initialize the grid proxy; check that VOMS tools are available: %s"
                               % error) from error
        valid = result.returncode == 0 and self.grid_proxy_valid()
        print("Grid proxy active." if valid else
              "Proxy Failed! Check your grid certificate and password, then retry Grid Certificate.")
        return 0 if valid else 1

    @staticmethod
    def _test_runner():
        root = Path(__file__).resolve().parents[2]
        runner = root / "Tests" / "run.py"
        if not runner.is_file():
            raise RuntimeError("Cannot find Tests/run.py in %s. Open the menu from a complete TauFW checkout." % root)
        return root, runner

    def test_catalog(self):
        root, runner = self._test_runner()
        result = subprocess.run([sys.executable, "-B", str(runner), "catalog"],
                                cwd=str(root), capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError("Cannot load test choices. Check Tests/run.py catalog:\n" + result.stderr.strip())
        try:
            catalog = json.loads(result.stdout)
            for family in ("checks", "normal", "bbb"):
                if not isinstance(catalog[family], list):
                    raise ValueError("Invalid test family")
                for case in catalog[family]:
                    if not isinstance(case["id"], str) or not isinstance(case["description"], str):
                        raise ValueError("Invalid test metadata")
                    if not isinstance(case["dependencies"], list):
                        raise ValueError("Invalid dependency metadata")
            return catalog
        except (ValueError, KeyError, TypeError) as error:
            raise RuntimeError("Invalid test catalog from Tests/run.py; check the checkout: %s" % error) from error

    def start_tests(self, family, cases):
        """Start Tests/run.py beside the menu; return the running BackgroundProcess. Its output and its events
        (Tests/support/events.py) go to Tests/.artifacts/logs/menu/; the test screen follows them."""
        if family not in ("all", "checks", "normal", "bbb", "environment"):
            raise ValueError("Unknown automated test family: %s" % family)
        if cases and family in ("all", "environment"):
            raise ValueError("This action does not accept selected cases.")
        root, runner = self._test_runner()
        command = [sys.executable, "-B", str(runner), family]
        if family == "bbb":
            command.append("check")
        for case in cases:
            command.extend(["--case", case])
        logs = root / "Tests" / ".artifacts" / "logs" / "menu"
        return BackgroundProcess.start(command, str(root), str(logs / "output.log"),
                                       events=str(logs / "events.jsonl"))

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
