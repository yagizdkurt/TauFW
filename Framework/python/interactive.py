# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Framework adapters for the Utilities menu navigation.

Discovery, path resolution, record access, validation, and CLI dispatch belong
here. Presentation and screen transitions live in TauFW.Utilities.Menu.
"""
import json
import os
import socket
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
from TauFW.Framework.run_lock import read_lock
from TauFW.Utilities.Menu import ConsoleUI, MenuNavigation
from TauFW.Utilities.Process import EventReader, EventWriter, OperationStore

CHECKOUT = Path(__file__).resolve().parents[2]
OPERATIONS_DIR = CHECKOUT / ".artifacts" / "menu" / "operations"  # what runs behind the menu (git-ignored)
TAUFW_SCRIPT = CHECKOUT / "Framework" / "scripts" / "taufw.py"


class _Operations:
    """Supply Framework operations without owning screens or navigation."""

    # =========================================================================
    # ================================= SETUP =================================

    def __init__(self, commands, launch_dir=None, recipes_dir=None, operations_dir=None):
        self.commands = commands
        self.launch_dir = Path(launch_dir or os.getcwd()).resolve()
        self.recipes_dir = Path(recipes_dir or ANALYSES_DIR)
        self.store = OperationStore(operations_dir or OPERATIONS_DIR)

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
        root = CHECKOUT
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

    def start_tests(self, family, cases, title=None, expected=()):
        """Start Tests/run.py behind the menu; return its TauFW.Utilities.Process.Operation (its output and its
        events, Tests/support/events.py, are in its directory under .artifacts/menu/operations/). title and
        expected (the case ids shown as waiting) are kept with it, for its screen in a later menu. One test run
        at a time: RuntimeError while one runs (Tests/run.py and its logs are shared). The oldest records are
        removed first (OperationStore.prune)."""
        if family not in ("all", "checks", "normal", "bbb", "environment"):
            raise ValueError("Unknown automated test family: %s" % family)
        if cases and family in ("all", "environment"):
            raise ValueError("This action does not accept selected cases.")
        running = self.store.running("tests")
        if running:
            raise RuntimeError("Tests are already running (%s, started on %s); open Tests to follow them."
                               % (running[0].title, running[0].host))
        root, runner = self._test_runner()
        command = [sys.executable, "-B", str(runner), family]
        if family == "bbb":
            command.append("check")
        for case in cases:
            command.extend(["--case", case])
        self.store.prune("tests", keep=4)  # with the new one: the last five
        return self.store.start("tests", title or family, command, str(root),
                                data=dict(family=family, cases=list(cases), expected=list(expected)))

    def tests_operation(self):
        """The last test run (an Operation), or None; also when the records cannot be read."""
        try:
            return self.store.latest("tests")
        except OSError:
            return None

    # =========================================================================
    # ========================= RUNS BEHIND THE MENU ==========================

    def start_run(self, recipe):
        """`taufw.py start RECIPE --wait` behind the menu (to the end: DONE, FAILED, or until it is stopped);
        return its Operation (kind "run"). Its data: run_id (the recipe's name until the run directory exists),
        run_dir (empty until then: the screen takes both from the `run` event) and the recipe's stages."""
        loaded = Recipe.load(str(recipe))
        stages = [dict(id=stage.id, type=stage.stage, state="NEW", message="", info=[]) for stage in loaded.stages]
        return self._start_run(loaded.name, ["start", str(recipe), "--wait"],
                               dict(run_id=loaded.name, run_dir="", stages=stages))

    def advance_run(self, record, wait=True, take_lock=False):
        """`taufw.py advance RUN_DIR` behind the menu, with --wait (to the end) or once; take_lock: take over
        the lock of a lost advance (--take-lock). The earlier advances of the run count as seen."""
        for operation in self._run_operations_of(record.run_dir):
            operation.mark_seen()
        argv = ["advance", record.run_dir] + (["--wait"] if wait else []) + (["--take-lock"] if take_lock else [])
        stages = [dict(id=stage.get("id"), type=stage.get("stage"), state=record.stage(stage.get("id")).state,
                       message=record.stage(stage.get("id")).message, info=[])
                  for stage in record.recipe.get("stages", ())]
        return self._start_run(record.run_id, argv, dict(run_id=record.run_id, run_dir=record.run_dir,
                                                          stages=stages))

    def run_operations(self):
        """The advances to show in the main menu: those running now, and those that ended and were not seen."""
        try:
            return [operation for operation in self.store.all("run") if operation.running or not operation.seen]
        except OSError:
            return []

    def run_operation(self, run_dir):
        """The advance of this run that runs behind the menu now (any menu, any machine), or None."""
        running = [operation for operation in self._run_operations_of(run_dir) if operation.running]
        return running[0] if running else None

    def run_advances(self, run_dirs):
        """The newest advance (an Operation) or None per run directory: the run list shows them."""
        try:
            operations = self.store.all("run")
        except OSError:
            operations = []
        newest = {}
        for operation in operations:  # newest first
            newest.setdefault(_run_dir_of(operation), operation)
        return [newest.get(str(Path(run_dir).resolve())) for run_dir in run_dirs]

    @staticmethod
    def run_lock(run_dir):
        """The advance lock of a run (read_lock: host, pid, since, quiet, lost; local: held on this machine), or
        None. A lost lock of this machine is taken over by the advance itself, without asking."""
        lock = read_lock(run_dir)
        if lock is not None:
            lock["local"] = lock.get("host") == socket.gethostname()
        return lock

    @staticmethod
    def mark_seen(operation):
        operation.mark_seen()

    def needs_grid_proxy(self, recipe=None, record=None):
        """Whether starting the recipe, or advancing the run, may submit jobs (a production stage that is not
        finished): the batch jobs read their input with the grid proxy, and taufw.py behind the menu cannot
        ask for the certificate password."""
        if record is not None:
            return any(stage.get("stage") == "production" and
                       record.stage(stage.get("id")).state not in ("DONE", "FAILED", "NOT_IMPLEMENTED")
                       for stage in record.recipe.get("stages", ()))
        return Recipe.load(str(recipe)).first("production") is not None

    def _start_run(self, title, argv, data):
        """taufw.py with argv as a run operation: a stop goes to taufw.py alone (it lets a job submission finish)
        and never escalates."""
        self.store.prune("run", keep=4)  # with the new one: the last five
        return self.store.start("run", title, [sys.executable, "-B", str(TAUFW_SCRIPT)] + argv,
                                str(self.launch_dir), data=data, escalate=False, signal="command")

    def _run_operations_of(self, run_dir):
        try:
            operations = self.store.all("run")
        except OSError:
            return []
        run_dir = str(Path(run_dir).resolve())
        return [operation for operation in operations if _run_dir_of(operation) == run_dir]

    def running_operations(self):
        """Everything that runs behind the menu now (Operations)."""
        try:
            return self.store.running()
        except OSError:
            return []

    @staticmethod
    def stop_operation(operation):
        operation.cancel()

    def execute(self, command, **values):
        args = dict(verbose=0, wait=False, poll=DEFAULT_POLL_SECONDS, run_root=None, local=False, maxevts=100,
                    take_lock=False,
                    events=EventWriter(None))  # in the menu's own process: no events (taufw.py main sets them)
        args.update(values)
        return self.commands[command](Namespace(**args))


def _run_dir_of(operation):
    """The run directory of an advance: from its data, or (a start) from its `run` event."""
    run_dir = operation.data.get("run_dir")
    if not run_dir:
        try:
            run_dir = next((event.get("run_dir") for event in EventReader(operation.events_path).read()
                            if event.get("kind") == "run"), "")
        except OSError:
            run_dir = ""
    return str(Path(run_dir).resolve()) if run_dir else ""


# =============================================================================
# ================================== LAUNCH ===================================


def Menu(commands, ui, launch_dir=None, recipes_dir=None, operations_dir=None):
    """Build navigation with Framework callbacks, preserving the constructor API. operations_dir: where the
    operations behind the menu are kept (default: OPERATIONS_DIR)."""
    return MenuNavigation(ui, _Operations(commands, launch_dir, recipes_dir, operations_dir))


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
