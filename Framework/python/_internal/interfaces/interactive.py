# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Framework adapters for the menu navigation (_internal/menu).

Discovery, path resolution, record access, validation, and CLI dispatch belong
here. Presentation and screen transitions live in TauFW.Framework._internal.menu. Every
command runs behind the menu as taufw.py (OperationStore): start/advance/rerun
(kind "run"), status (kind "command", read only) and the tests; the
menu's own process reads recipes, run.json, check_recipe and a dry plan (the plan screen). The
User Config action creates a missing config and opens the independent Editor.

Iterative runs (CL §55 step 4): Continue's pickers (stage_choices: a dry rerun of every stage), Edit run config
and the Start screen's E (run_files / analysis_files, file_text, the validators of a save, rerun_suggestion after
it) and History (run_history, attempt_log) get plain data from here; the menu imports no Framework module.
Install components opens FastSetup on the terminal and returns to the menu when it closes.

What Start and Continue list (a recipe's check, a run's row) is kept with the
signature of the files it was read from (path, inode, mtime, size: a stat
each), so a list reads again only what changed; the menu reads them ahead in
a thread of its own (Menu/_prefetch.py) and asks kept_recipe_preview() and
kept_run_row().
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

from TauFW.Framework._internal.defaults import (ANALYSES_DIR, BUNDLE_DIR_NAME, CONFIGS_DIR, DEFAULT_RUN_ROOT,
                                                EXAMPLES_DIR_NAME, RECIPE_NAME, RUN_RECORD_NAME, STAGES_DIR_NAME,
                                                TIME_FORMAT)
from TauFW.Framework._internal.runtime.run_record import RunRecord, RunState
from TauFW.Framework._internal.recipes.recipe import Recipe, RecipeError, read_recipe
from TauFW.Framework._internal.recipes.validation import check_recipe, check_recipe_data
from TauFW.Framework._internal.recipes.analysis import analysis_name_problem, create_analysis
from TauFW.Framework._internal.recipes.bundle import bundle_changes, bundle_hashes, path_rows
from TauFW.Framework._internal.runtime.framework import (Framework, RerunError, next_stage, retryable_stage,
                                                         _run_recipe)
from TauFW.Framework._internal.runtime.run_recipe import (read_run_recipe, recipe_changes, edit_problems,
                                                          pending_change, saved_dict, changes_text, RECIPE_COPY,
                                                          RECIPES_DIR_NAME)
from TauFW.Framework._internal.runtime.reporting import SilentReporter
from TauFW.Framework._internal.runtime.plan_text import command_line, inputs_line, run_root_line
from TauFW.Framework._internal.runtime.run_lock import read_lock
from TauFW.Framework.stages.production import ProductionSpec
from TauFW.Framework._internal.version import VersionChecker
from TauFW.Framework._internal.menu import ConsoleUI, MenuNavigation, Prefetch
from TauFW.Utilities import UserConfig
from TauFW.Utilities.UserConfig import manage as user_config
from TauFW.Framework._internal.user_settings import run_root_or_none as user_run_root
from TauFW.Framework._internal.operations import LOST, EventReader, OperationStore

CHECKOUT = Path(__file__).resolve().parents[4]
OPERATIONS_DIR = CHECKOUT / ".artifacts" / "menu" / "operations"  # what runs behind the menu (git-ignored)
TAUFW_SCRIPT = CHECKOUT / "Framework" / "scripts" / "taufw.py"
PROXY_MARGIN = 60  # seconds a proxy must still be valid for (voms-proxy-info --valid 0:01 before)
PROXY_INIT_TIMEOUT = 120  # seconds voms-proxy-init may take (it asks the VOMS server)
PLAN_CHECK_TIMEOUT = 180  # seconds the plan screen's file checks may take (_PlanCheck), then Start opens
PLAN_CHECK_MODULE = "TauFW.Framework._internal.interfaces.plan_check"
USER_CONFIG_NAME = user_config.FILE_NAME
TEXT_SUFFIXES = (".yml", ".yaml", ".json", ".py", ".txt", ".md", ".sh", ".C", ".h")  # the files Edit lists
PREVIEW_LINES = 2000  # lines of a file the file screen shows (file_text)
LOG_LINES = 200       # last lines of each log file of an earlier attempt (attempt_log)


class _Operations:
    """Supply Framework operations without owning screens or navigation."""

    # =========================================================================
    # ================================= SETUP =================================

    def __init__(self, launch_dir=None, recipes_dir=None, operations_dir=None):
        self.launch_dir = Path(launch_dir or os.getcwd()).resolve()
        self.recipes_dir = Path(recipes_dir or ANALYSES_DIR)
        self.store = OperationStore(operations_dir or OPERATIONS_DIR)
        self._proxy = None  # (valid, until, proxy file): the last answer of voms-proxy-info (grid_proxy_valid)
        self._kept = {}     # (what, path) -> (signature of its files, value): previews, run roots, run rows
        self._versions = VersionChecker()  # metadata/cache only; HTTP starts when the menu asks for status

    def version_status(self):
        """Plain version data; a due network check runs behind the menu, never in the UI thread."""
        return self._versions.status()

    def resolve_path(self, value):
        path = Path(value).expanduser()
        return str((path if path.is_absolute() else self.launch_dir / path).resolve())

    @staticmethod
    def user_config_path():
        """The active config, including $TAUFW_USER_CONFIG; a missing file gets the usual template."""
        path = UserConfig.location().resolve()
        user_config.create(path)
        return path

    @staticmethod
    def user_config_reference():
        """The editor's help of this checkout, also when the config lives elsewhere."""
        return CHECKOUT / "Docs" / "Develop" / "InProgramMDs" / "UserConfig.md"

    @staticmethod
    def validate_user_config(draft_path):
        """Reuse the normal YAML/header/value checks; reviewed: false is allowed while editing."""
        return user_config.setting_problems(UserConfig.load(draft_path))

    @staticmethod
    def user_config_reviewed():
        """Whether the active config exists and says reviewed: true; a file that cannot be read is not reviewed."""
        try:
            return UserConfig.load().reviewed is True
        except UserConfig.UserConfigError:
            return False

    @staticmethod
    def install_components():
        """Reuse the installer's checklist and progress screen in this checkout's release area."""
        script = CHECKOUT / "Utilities" / "FastSetup.sh"
        result = subprocess.run(["bash", str(script)], cwd=str(CHECKOUT))
        if result.returncode not in (0, 130):
            raise RuntimeError("Installation failed (exit status %d). Reopen Install components to retry; "
                               "see the installation log for details." % result.returncode)
        return result.returncode

    # =========================================================================
    # =============================== DISCOVERY ===============================

    def recipes(self):
        """The analysis bundles (directories with a recipe.yml) and loose recipe files in the recipes directory;
        the user config (Analyses/UserConfig.yaml) is not a recipe. The examples (Analyses/Examples/) are not
        listed here: examples() lists them."""
        return _recipes_in(self.recipes_dir)

    def examples(self):
        """The example analyses in Analyses/Examples/, listed under [Examples] of the recipe list."""
        return _recipes_in(self.recipes_dir / EXAMPLES_DIR_NAME)

    def create_analysis(self, name):
        """Create a draft in the same root that the recipe picker discovers."""
        return create_analysis(self.recipes_dir, name)

    def check_analysis_name(self, name):
        """The line under the name field of Create a new analysis, at every key: (True, the folder it makes) or
        (False, why it cannot be made)."""
        if not name:
            return False, "Letters, digits, _ . - : it names the folder and the recipe."
        problem = analysis_name_problem(self.recipes_dir, name)
        return (False, problem) if problem else (True, "Creates %s/%s/" % (self.recipes_dir.name, name))

    def check_recipe_path(self, value):
        """The line under the path field of Enter a recipe path: (True, the recipe found) or (False, why not)."""
        if not value:
            return False, "A bundle directory (with recipe.yml) or a .yml, .yaml or .json recipe file."
        path = Path(self.resolve_path(value))
        if path.is_dir():
            return ((True, "Bundle %s" % path) if (path / RECIPE_NAME).is_file() else
                    (False, "%s has no %s." % (path, RECIPE_NAME)))
        if path.is_file():
            return ((True, "Recipe %s" % path) if path.suffix in (".yml", ".yaml", ".json") else
                    (False, "%s is not a .yml, .yaml or .json file." % path))
        return False, "%s does not exist." % path

    def check_run_path(self, value):
        """The line under the path field of Enter another run directory: (True, the run) or (False, why not)."""
        if not value:
            return False, "A run directory: the one with run.json."
        path = Path(self.resolve_path(value))
        if (path / RUN_RECORD_NAME).is_file():
            return True, "Run %s" % path
        return False, ("%s has no %s: not a run directory." % (path, RUN_RECORD_NAME) if path.is_dir() else
                       "%s does not exist." % path)

    def recipe_preview(self, path):
        """Check the recipe (validation.py) without constructing stage APIs: its stages and every problem; a
        recipe that cannot be checked: its name and the error. Kept until a file of it changes (kept_recipe_preview;
        also a template of Configs/, its copies are compared with them)."""
        signature = _recipe_signature(path)
        try:
            check = check_recipe(str(path), allow_draft=True)
            view = dict(name=check.name, path=str(path), shown=_shown(path), draft=check.draft,
                        stages=tuple(stage + (reads,) for stage, reads in zip(check.stages, check.reads)),
                        problems=tuple(str(issue) for issue in check.issues),
                        warnings=tuple(str(warning) for warning in check.warnings))
        except Exception as error:
            view = dict(name=Path(path).name, error=str(error))
        self._kept[("preview", str(path))] = (signature, view)
        return view

    def kept_recipe_preview(self, path):
        """The preview of the recipe as recipe_preview() left it, if no file of it changed since; else None."""
        return self._kept_value("preview", path, _recipe_signature)

    def prepare_plan(self, path, quick=False):
        """The plan screen's data: check the recipe, then dry-plan it without terminal output or writes (as
        `taufw.py plan` does). A recipe with problems, or one that cannot be planned, still has its stages and its
        errors (the screen shows them; it cannot start). Plain data: the menu never sees Framework objects.
        quick: without the checks that open data files (Framework.plan deep=False); the stages that have them say
        checking=True, and check_plan() makes the whole plan behind the screen.
        dict(name, path, overview (lines), errors, warnings, stages: dict(id, type, description, reads, inputs,
        files: (option, file, from), note (why it is not planned), samples: (era, channel, sample, files, chunks,
        try, conflict), jobs, cwd, subdirs, steps: (label, command line), notes))"""
        check = check_recipe(str(path))
        stages = [dict(id=stage_id, type=kind, description=description, reads=reads, inputs="", files=(),
                       note="", samples=None, jobs=0, cwd="", subdirs=(), steps=None, notes=())
                  for (stage_id, kind, description), reads in zip(check.stages, check.reads)]
        view = dict(name=check.name, path=str(path), overview=["Recipe: %s" % _shown(path)], stages=stages,
                    errors=[str(issue) for issue in check.issues], warnings=[str(issue) for issue in check.warnings])
        if not view["errors"]:
            reporter = SilentReporter()
            try:
                framework = Framework.from_recipe(Recipe.load(str(path)), reporter=reporter)
                plan = framework.plan(deep=not quick)
            except Exception as error:
                view["errors"].append("Cannot plan the recipe: %s" % error)
            else:
                _fill_plan(view, framework, plan)
                view["warnings"] += [message for kind, message in reporter.messages if kind == "warning"]
                if quick:
                    for stage in stages:
                        stage["checking"] = (stage["steps"] is not None
                                             and getattr(framework.stages[stage["id"]], "deep_checks", False) is True)
        if view["errors"]:
            for stage in stages:
                stage["note"] = "Cannot be planned until the errors are fixed."
        return view

    def check_plan(self, path, view):
        """The whole plan of a quick one (prepare_plan quick=True) made behind the plan screen, in a process of its
        own (_PlanCheck): ROOT stays out of the menu, and the menu never waits. None if no stage is checking."""
        if not any(stage.get("checking") for stage in view.get("stages", ())):
            return None
        return _PlanCheck(self.resolve_path(path), view, self.launch_dir)

    def run_roots(self):
        """Where runs are looked for: taufw_runs/ in the launch directory, runs.run_root of the user config, and the
        run_root of every recipe in the recipes directory and its examples (also of a recipe with problems, if its
        run_root can be read)."""
        roots = [self.launch_dir / DEFAULT_RUN_ROOT]
        if user_run_root():
            roots.append(Path(user_run_root()))
        for path in self.recipes() + self.examples():
            value = self._kept_value("root", path, _file_signature)
            if value is None:
                value = self._run_root_of(path)
            if value:
                roots.append(Path(value))
        return list(dict.fromkeys(root.resolve() if root.is_absolute() else self.launch_dir / root
                                  for root in roots))

    def run_directories(self):
        """The run directories (with a run.json) in the run roots, and those of the advances behind the menu (a run
        of a recipe outside the recipes directory, or started with another run root)."""
        directories = []
        for root in self.run_roots():
            if root.is_dir():
                directories.extend(directory for directory in root.iterdir() if directory.is_dir())
        try:
            directories.extend(Path(run_dir) for run_dir in map(_run_dir_of, self.store.all("run")) if run_dir)
        except OSError:
            pass  # the operations cannot be read: the run roots only
        return [str(directory) for directory in dict.fromkeys(directory.resolve() for directory in directories)
                if (directory / RUN_RECORD_NAME).is_file()]

    def run_row(self, run_dir):
        """(created, run_dir, (run_id, state, updated)) of a run; state None: its run.json cannot be read. Kept
        until run.json changes (kept_run_row)."""
        signature = _file_signature(Path(run_dir) / RUN_RECORD_NAME)
        try:
            record = self.load_run(str(run_dir))
            row = (record.created, str(run_dir), (record.run_id, record.state, record.updated))
        except Exception:
            row = ("", str(run_dir), (Path(run_dir).name, None, None))
        self._kept[("run", str(run_dir))] = (signature, row)
        return row

    def kept_run_row(self, run_dir):
        """The row of the run as run_row() left it, if its run.json did not change since; else None."""
        return self._kept_value("run", run_dir, lambda path: _file_signature(Path(path) / RUN_RECORD_NAME))

    def run_preview(self, run_dir):
        """Plain saved details for the selected run; called by the menu's preview worker, never by curses."""
        record = self.load_run(run_dir)
        advancing = self.run_operation(run_dir)
        try:
            pending = pending_change(record)
        except Exception as error:  # an unreadable file: the advance says the same
            pending = "bundle/recipe.yml cannot be read: %s" % (error)
        types = {stage.get("id"): stage.get("stage") for stage in record.recipe.get("stages", ())}
        can_advance = self.can_advance(record)
        return dict(run_id=record.run_id, run_dir=record.run_dir, state=str(record.state), updated=record.updated,
                    stages=[dict(id=stage.name, type=types.get(stage.name, ""), state=str(stage.state),
                                 message=stage.message, attempts=len(stage.attempts)) for stage in record.stages],
                    can_advance=can_advance, retry=self.retry_info(record), next=next_stage(record) if can_advance
                    else None, pending=pending, lock=self.run_lock(run_dir), advancing=advancing is not None)

    def runs(self):
        """The rows of every run (run_directories), newest first."""
        rows = [self.kept_run_row(run_dir) or self.run_row(run_dir) for run_dir in self.run_directories()]
        return sorted(rows, key=lambda row: (row[0], row[1]), reverse=True)

    def _run_root_of(self, path):
        """The run_root a recipe names, or "" (none, or it cannot be read: its problems are shown with the
        recipe); kept until the recipe file changes."""
        signature, value = _file_signature(path), ""
        try:
            data = read_recipe(str(path))[0]
            found = data.get('run_root') if isinstance(data, dict) else None
            value = found if isinstance(found, str) and found.strip() else ""
        except Exception:
            pass
        self._kept[("root", str(path))] = (signature, value)
        return value

    def _kept_value(self, what, path, signature_of):
        kept = self._kept.get((what, str(path)))
        if kept is None or kept[0] != signature_of(path):
            return None
        return kept[1]

    # =========================================================================
    # ========================== VALIDATION AND DISPATCH ======================

    @staticmethod
    def load_run(path):
        return RunRecord.load(path)

    @staticmethod
    def can_advance(record):
        return not RunState(record.state).finished

    def grid_proxy_valid(self, fresh=False):
        """Whether the grid proxy is valid for PROXY_MARGIN seconds more; quiet, never prompts. Every main menu
        draw asks: the answer of voms-proxy-info (up to 5 s) is kept until the proxy expires or its file changes
        (renewed in another terminal: mtime and size); fresh: ask voms-proxy-info again (before a run that may
        submit jobs, after a renewal)."""
        now, proxy_file = time.time(), _proxy_file()
        if not fresh and self._proxy is not None:
            valid, until, known_file = self._proxy
            if known_file == proxy_file and (not valid or now < until):
                return valid
        try:
            result = subprocess.run(["voms-proxy-info", "--timeleft"], stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, text=True, timeout=5)
            left = int(result.stdout.split()[-1]) if result.returncode == 0 else 0  # after any warning
        except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
            left = 0
        valid = left > PROXY_MARGIN
        self._proxy = (valid, now + left - PROXY_MARGIN, proxy_file)
        return valid

    def renew_grid_proxy(self, password):
        """`voms-proxy-init -voms cms -pwstdin`, the certificate password on its stdin (never in its argv, a file
        or a log). Return (valid, output): valid is None when this voms-proxy-init cannot read the password from
        stdin (its output names -pwstdin): then renew_grid_proxy_in_terminal()."""
        try:
            result = subprocess.run(["voms-proxy-init", "-voms", "cms", "-pwstdin"], input=password + "\n",
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                    timeout=PROXY_INIT_TIMEOUT)
        except OSError as error:
            raise RuntimeError("Cannot initialize the grid proxy; check that VOMS tools are available: %s"
                               % error) from error
        except subprocess.TimeoutExpired:
            return False, "voms-proxy-init did not answer within %d s." % PROXY_INIT_TIMEOUT
        output = result.stdout.strip()
        if result.returncode and "pwstdin" in output.lower():
            return None, output
        return result.returncode == 0 and self.grid_proxy_valid(fresh=True), output

    def renew_grid_proxy_in_terminal(self):
        """Let VOMS read the certificate password directly from the terminal (ConsoleUI.in_terminal)."""
        print("Enter your grid certificate password when prompted.")
        try:
            result = subprocess.run(["voms-proxy-init", "-voms", "cms"])
        except OSError as error:
            raise RuntimeError("Cannot initialize the grid proxy; check that VOMS tools are available: %s"
                               % error) from error
        valid = result.returncode == 0 and self.grid_proxy_valid(fresh=True)
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
        """Start Tests/run.py behind the menu; return its Framework._internal.operations.Operation (its output and its
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
        """`taufw.py start RECIPE` behind the menu (to the end: DONE, FAILED, or until it is stopped);
        return its Operation (kind "run"). Its data: run_id (the recipe's name until the run directory exists),
        run_dir (empty until then: the screen takes both from the `run` event) and the recipe's stages."""
        loaded = Recipe.load(str(recipe))
        stages = [dict(id=stage["id"], type=stage["stage"], state="NEW", message="", info=_stage_info(stage))
                  for stage in loaded.to_dict()["stages"]]
        return self._start_run(loaded.name, ["start", str(recipe)],
                               dict(run_id=loaded.name, run_dir="", stages=stages))

    def advance_run(self, record, next_only=False, take_lock=False, until=None):
        """`taufw.py advance RUN_DIR` behind the menu: to the end (waiting for the jobs), with next_only only the
        next stage (--next), or until a stage (--until ID; the run is then PAUSED); take_lock: take over the lock of
        a lost advance (--take-lock). The earlier advances of the run count as seen."""
        argv = (["advance", record.run_dir] + (["--next"] if next_only else []) +
                (["--until", until] if until else []) + (["--take-lock"] if take_lock else []))
        return self._run_of(record, argv)

    def rerun_run(self, record, stage_id=None, next_only=False, take_lock=False):
        """`taufw.py rerun RUN_DIR [ID]` behind the menu: the stage (default: the failed one) and every stage after
        it again, then to the end, or with next_only that stage only (--next) (CL §44, §55); take_lock: take over
        the lock of a lost advance (--take-lock)."""
        argv = (["rerun", record.run_dir] + ([stage_id] if stage_id else []) + (["--next"] if next_only else []) +
                (["--take-lock"] if take_lock else []))
        return self._run_of(record, argv)

    @staticmethod
    def retry_info(record):
        """What the menu shows before a retry of a FAILED run, as plain data: dict(stage, type, message, changed),
        changed: the bundle copy's changes since the start ({path: added|changed|removed}; None: not known); a
        production stage also tries: (tries made, the limit after the retry) (CL §48). None if the run has no
        stage that can be retried (no failed stage, or one whose retry_state refuses it)."""
        found = retryable_stage(record)
        if found is None:
            return None
        start = record.bundle.get("sha256")
        changed = (bundle_changes(start, bundle_hashes(os.path.join(record.run_dir, BUNDLE_DIR_NAME)))
                   if start is not None else None)
        saved = record.stage(found[0])
        info = dict(stage=found[0], type=found[1], message=saved.message, changed=changed)
        if found[1] == "production":  # the limit retry_fields() will write: max_tries more tries
            options = next(stage for stage in record.recipe.get("stages", ()) if stage.get("id") == found[0])
            info["tries"] = (saved.attempt, saved.attempt + options.get("max_tries", ProductionSpec.max_tries))
        return info

    def _run_of(self, record, argv):
        """taufw.py argv (advance or retry) of a run behind the menu, with the run's stages as run.json has them,
        and how long the finished and failed ones took in the earlier advances (_earlier_time). The earlier advances
        of the run count as seen."""
        for operation in self._run_operations_of(record.run_dir):
            operation.mark_seen()
        stages = []
        for stage in record.recipe.get("stages", ()):
            saved = record.stage(stage.get("id"))
            info = (_stage_info(stage) + ([["Attempt", str(saved.attempt)]] if saved.attempt else []) +
                    ([["Earlier attempts", str(len(saved.attempts))]] if saved.attempts else []))
            stages.append(dict(id=stage.get("id"), type=stage.get("stage"), state=saved.state, message=saved.message,
                               info=info, **_earlier_time(saved)))
        return self._start_run(record.run_id, argv, dict(run_id=record.run_id, run_dir=record.run_dir,
                                                          stages=stages))

    def run_operations(self):
        """The advances to show in the main menu: those running now, those that ended and were not seen, and a
        lost one until its run goes on (a newer advance of the run) or ends (run.json finished; e.g. advanced
        from the CLI)."""
        try:
            operations = self.store.all("run")
        except OSError:
            return []
        shown, later = [], set()
        for operation in operations:  # newest first
            run_dir = _run_dir_of(operation)
            if operation.running or not operation.seen:
                shown.append(operation)
            elif operation.state() == LOST and run_dir not in later and not self._finished(run_dir):
                shown.append(operation)
            later.add(run_dir)
        return shown

    def _finished(self, run_dir):
        try:
            return RunState(self.load_run(run_dir).state).finished
        except Exception:
            return False  # no run directory yet, or unreadable: the lost advance stays listed

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

    # =========================================================================
    # ======================== ITERATIVE RUNS (CL §55) ========================

    def stage_choices(self, record):
        """What Continue's stage pickers show (Rerun from..., Advance until...), as plain data: dict(run_id,
        next (the first stage that is not DONE, or None), pending (pending_change, or None), error (the run's
        edited recipe would be refused: why; nothing can be chosen), stages). A stage: dict(id, type, state,
        attempts, plan (a dry rerun from it: dict(rows, kept, recipe_changes, bundle_changed, production); None:
        it cannot start a rerun), why (then: the reason), tag (its short form: fixed, blocked or cannot), until
        (True: Advance until can stop there: the next stage or one after it)). The stages are those of the run's
        recipe as its next advance sees it (an edit that passes its checks)."""
        record = self.load_run(record.run_dir)
        view = dict(run_id=record.run_id, next=next_stage(record), pending=None, error=None, stages=[])
        try:
            view["pending"] = pending_change(record)
            plans = Framework.from_record(record, reporter=SilentReporter()).plan_reruns(record)
        except RecipeError as error:
            view["error"] = str(error)
            plans = [(stage.name, None) for stage in record.stages]
        saved = {stage.name: stage for stage in record.stages}
        types = {stage.get("id"): stage.get("stage") for stage in record.recipe.get("stages", ())}
        ids = [stage_id for stage_id, _ in plans]
        nexts = [stage_id for stage_id in ids if stage_id not in saved or saved[stage_id].state != "DONE"]
        first = ids.index(nexts[0]) if nexts else len(ids)
        for index, (stage_id, plan) in enumerate(plans):
            stage = saved.get(stage_id)
            row = dict(id=stage_id, type=types.get(stage_id, ""),
                       state=stage.state if stage else "NEW", attempts=len(stage.attempts) if stage else 0,
                       plan=None, why=None, tag=None, until=view["error"] is None and index >= first)
            if isinstance(plan, RerunError):
                row["why"] = str(plan)
                row["tag"] = ("fixed" if "cannot run again in this run" in row["why"] else
                              "blocked" if "is FAILED: rerun from it" in row["why"] else "cannot")
            elif plan is not None:
                row["plan"] = dict(rows=[dict(item) for item in plan.rows], kept=ids[:ids.index(plan.start)],
                                   recipe_changes=plan.recipe_changes, bundle_changed=plan.bundle_changed,
                                   production=plan.production)
            view["stages"].append(row)
        recipe = _edited_recipe(record)
        for row in view["stages"]:
            row["type"] = row["type"] or (recipe.stage(row["id"]).stage if recipe and recipe.stage(row["id"]) else "")
        return view

    def run_files(self, record):
        """The files of Edit run config, as plain data: the run's recipe (bundle/recipe.yml) first, then the text
        files of its bundle copy (TEXT_SUFFIXES). A file: dict(path (relative to bundle/), file (absolute), recipe
        (True for the recipe), read_by ([stage ids]: the path options naming it), state ("" or what changed:
        "edited, not taken yet", "edited since the start", "added since the start"))."""
        record = self.load_run(record.run_dir)
        bundle = os.path.join(record.run_dir, BUNDLE_DIR_NAME)
        recipe_file = os.path.join(bundle, RECIPE_NAME)
        try:
            pending = pending_change(record)
        except Exception:
            pending = "unreadable"
        start = record.bundle.get("sha256")
        changes = bundle_changes(start, bundle_hashes(bundle)) if start is not None else {}
        listed = [dict(path=RECIPE_NAME, file=recipe_file, recipe=True, read_by=[],
                       state="edited, not taken yet" if pending else "")] if os.path.isfile(recipe_file) else []
        states = {"changed": "edited since the start", "added": "added since the start"}
        return listed + _text_files(bundle, _run_recipe(record), lambda path: states.get(changes.get(path), ""))

    def analysis_files(self, path):
        """The files the Start screen's E lists for an analysis bundle (Analyses/<name>/), as run_files does (the
        state is always "")."""
        directory = Path(path)
        directory = directory if directory.is_dir() else directory.parent
        try:
            recipe = Recipe.load(str(directory))
        except Exception:
            recipe = None  # a broken recipe: no read_by
        listed = [dict(path=RECIPE_NAME, file=str(directory / RECIPE_NAME), recipe=True, read_by=[], state="")]
        return listed + _text_files(str(directory), recipe, lambda relative: "")

    @staticmethod
    def file_text(path):
        """The first PREVIEW_LINES lines of a text file, for the file screen's preview (tabs as spaces)."""
        try:
            with open(path, encoding="utf-8", errors="replace") as stream:
                lines = [line.rstrip("\n").expandtabs(4) for _, line in zip(range(PREVIEW_LINES), stream)]
        except OSError as error:
            return ["Cannot read %s: %s" % (path, error)]
        return lines or ["(empty file)"]

    def run_file_validator(self, record, relative):
        """The editor's check before it saves a file of Edit run config: refused while an advance holds the run's
        lock (S15); the run's recipe also passes every check of `taufw check` and the run's edit rules (the
        samples check is the next advance's). Returns validate(draft_path) -> problems or None."""
        run_dir = record.run_dir

        def validate(draft):
            lock = read_lock(run_dir)
            if lock is not None:
                return ["An advance works on this run now (pid %s on %s): save once it ends; your edits stay here."
                        % (lock.get("pid", "?"), lock.get("host", "?"))]
            if relative != RECIPE_NAME:
                return None
            loaded = self.load_run(run_dir)
            recipe, issues = read_run_recipe(loaded, path=str(draft))
            if issues:
                return [str(issue) for issue in issues]
            return [str(issue) for issue in edit_problems(loaded.recipe, saved_dict(recipe))] or None
        return validate

    @staticmethod
    def analysis_validator(path, relative):
        """The editor's check before it saves a file of an analysis bundle: its recipe.yml passes `taufw check`
        (its warnings do not stop a save; a draft without stages is allowed); the other files are not checked."""
        def validate(draft):
            if relative != RECIPE_NAME:
                return None
            data, source, directory = read_recipe(str(draft))
            check = check_recipe_data(data, "%s/%s" % (os.path.basename(directory), RECIPE_NAME), directory, str(draft),
                                      allow_draft=True)  # a new analysis may stay without stages
            return [str(issue) for issue in check.issues] or None
        return validate

    def rerun_suggestion(self, record, relative):
        """After a save of Edit run config: dict(stage, text) of the first stage (recipe order) the change concerns
        that is DONE and can start a rerun, or None. The recipe: a changed stage (recipe_changes); another file: a
        stage whose path options name it."""
        record = self.load_run(record.run_dir)
        saved = {stage.name: stage for stage in record.stages}
        if relative == RECIPE_NAME:
            recipe, issues = read_run_recipe(record, full=False)
            if recipe is None or issues:
                return None
            changes = recipe_changes(record.recipe, saved_dict(recipe))
            touched = [stage_id for stage_id, change in changes.items() if change == "changed"]
            what = "You changed %%s in %s" % (RECIPE_NAME)
        else:
            recipe = _run_recipe(record)
            touched = [stage_spec.id for stage_spec in recipe.stages
                       if relative in _bundle_paths(stage_spec, recipe.bundle_dir)]
            what = "%s is read by %%s" % (relative)
        done = [stage_id for stage_id in touched if stage_id in saved and saved[stage_id].state == "DONE"]
        if not done:
            return None
        try:
            plans = dict(Framework.from_record(record, reporter=SilentReporter()).plan_reruns(record))
        except RecipeError:
            return None
        for stage_id in done:
            if not isinstance(plans.get(stage_id), RerunError) and plans.get(stage_id) is not None:
                return dict(stage=stage_id, text="%s; it is DONE with the old %s. To use the new ones, %s and the "
                            "stages after it run again." % (what % (stage_id), "options" if relative == RECIPE_NAME
                                                             else "file", stage_id))
        return None

    def run_history(self, record):
        """What History shows, as plain data: dict(run_id, versions, stages, removed). versions: the run's recipe
        versions, dict(version, time, text, done, file); stages: dict(id, type, state, message, time (of its last
        history entry), attempts: [dict(attempt, reason, from, state, time, message, archive)], newest first);
        removed: the stages an edit removed, dict(id, type, state, time, archive)."""
        record = self.load_run(record.run_dir)

        def copy(version):
            relative = os.path.join(RECIPES_DIR_NAME, RECIPE_COPY % (version))
            return relative if os.path.isfile(os.path.join(record.run_dir, relative)) else None

        versions = [dict(version=0, time=record.created, text="start", done=[], file=copy(0))]
        versions += [dict(version=change.get("version"), time=change.get("time", ""),
                          text=changes_text(change.get("stages", {})) or "no stage changed",
                          done=list(change.get("done", ())), file=copy(change.get("version")))
                     for change in record.recipe_changed]
        types = {stage.get("id"): stage.get("stage") for stage in record.recipe.get("stages", ())}
        stages = [dict(id=stage.name, type=types.get(stage.name, ""), state=stage.state, message=stage.message,
                       time=stage.history[-1].get("time", "") if stage.history else "",
                       attempts=[dict(attempt=entry.get("attempt"), reason=entry.get("reason", "failed"),
                                      start=entry.get("from") or "", state=entry.get("state") or "",
                                      time=entry.get("time", ""), message=entry.get("message") or "",
                                      archive=entry.get("archive")) for entry in reversed(stage.attempts)])
                  for stage in record.stages]
        removed = [dict(id=entry.get("name"), state=entry.get("state"), time=entry.get("removed", {}).get("time", ""),
                        archive=entry.get("removed", {}).get("archive")) for entry in record.removed]
        return dict(run_id=record.run_id, versions=versions, stages=stages, removed=removed)

    @staticmethod
    def attempt_log(record, archive):
        """The last LOG_LINES lines of each log file of an earlier attempt (archive: relative to the run directory,
        logs/<id>/attempt<N>), each after a line with its name; or why there are none."""
        directory = os.path.join(record.run_dir, archive or "")
        if not archive or not os.path.isdir(directory):
            return ["Nothing was kept for this attempt (production keeps its job files in place)." if not archive
                    else "%s does not exist any more." % (archive)]
        lines = []
        for name in sorted(os.listdir(directory)):
            if not name.endswith(".log"):
                continue
            with open(os.path.join(directory, name), encoding="utf-8", errors="replace") as stream:
                tail = stream.read().splitlines()[-LOG_LINES:]
            lines += ["== %s ==" % (name)] + [line.expandtabs(4) for line in tail] + [""]
        return lines or ["No log files in %s (its output is in %s)." % (archive, os.path.join(archive, "stage"))]

    def needs_grid_proxy(self, recipe=None, record=None):
        """Whether starting the recipe, or advancing the run, may submit jobs (a production stage that is not
        finished, or a FAILED one that a retry resubmits, CL §48): the batch jobs read their input with the grid
        proxy, and taufw.py behind the menu cannot ask for the certificate password."""
        if record is not None:
            retry = retryable_stage(record)
            return (retry is not None and retry[1] == "production") or any(
                stage.get("stage") == "production" and
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
        """Everything that runs behind the menu now (Operations); a read-only command is stopped by its screen
        and is not counted."""
        try:
            return [operation for operation in self.store.running() if operation.kind != "command"]
        except OSError:
            return []

    @staticmethod
    def stop_operation(operation):
        operation.cancel()

    # =========================================================================
    # ======================= READ-ONLY COMMANDS ON SCREEN ====================

    def start_command(self, command, target):
        """`taufw.py status RUN_DIR` behind the menu; return its Operation (kind "command", data: command,
        target). Its screen shows the plain output and stops it when it is left (a status with production asks
        HTCondor, which may take seconds; the menu keeps drawing)."""
        if command != "status":
            raise ValueError("Not a read-only command: %s" % command)
        self.store.prune("command", keep=4)  # with the new one: the last five
        return self.store.start("command", "%s %s" % (command, Path(target).name),
                                [sys.executable, "-B", str(TAUFW_SCRIPT), command, str(target)],
                                str(self.launch_dir), data=dict(command=command, target=str(target)))


class _PlanCheck:
    """`python -m plan_check <recipe> <file>`: the whole plan (prepare_plan) of a recipe whose quick plan the screen
    shows, written as JSON. poll(): None while it runs, then once the view that replaces the quick one; if the process
    failed or took longer than PLAN_CHECK_TIMEOUT, the quick one without checking stages and with a warning (Start
    opens: a run checks every stage again when it starts it). cancel(): stop it (the screen was left)."""

    def __init__(self, path, view, launch_dir, timeout=PLAN_CHECK_TIMEOUT):
        self.view, self.timeout, self.started = view, timeout, time.monotonic()
        self.answered = False  # poll() gave its view: later calls give None
        self.directory = tempfile.mkdtemp(prefix="taufw-plan-")
        self.output = os.path.join(self.directory, "plan.json")
        with open(os.path.join(self.directory, "log"), "w") as log:  # its own session: no Ctrl+C, no resize
            self.process = subprocess.Popen([sys.executable, "-B", "-m", PLAN_CHECK_MODULE, path, self.output],
                                            cwd=str(launch_dir), stdin=subprocess.DEVNULL, stdout=log,
                                            stderr=subprocess.STDOUT, start_new_session=True)

    def poll(self):
        if self.answered:
            return None
        if self.process.poll() is None:
            if time.monotonic() - self.started < self.timeout:
                return None
            self.cancel()
            self.answered = True
            return self._failed("they did not finish in %d s" % self.timeout)
        try:
            with open(self.output) as stream:
                view = json.load(stream)
        except (OSError, ValueError):
            view = None
        reason = None if view is not None else "exit code %s%s" % (self.process.returncode, self._last_line())
        self.cancel()
        self.answered = True
        return view if view is not None else self._failed(reason)

    def cancel(self):
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait()
        shutil.rmtree(self.directory, ignore_errors=True)

    def _last_line(self):
        try:
            with open(os.path.join(self.directory, "log")) as stream:
                lines = [line.strip() for line in stream if line.strip()]
        except OSError:
            return ""
        return ": %s" % lines[-1] if lines else ""

    def _failed(self, reason):
        view = dict(self.view, warnings=list(self.view.get("warnings", ())) + [
            "The tuple file checks did not run (%s); a run checks them when it starts the stage." % reason])
        view["stages"] = [dict(stage, checking=False) for stage in self.view.get("stages", ())]
        return view


def _fill_plan(view, framework, plan):
    """The overview and each stage's details of a plan (Framework.plan), as `taufw.py plan` shows them."""
    recipe = framework.recipe
    if plan.bundle_dir:
        view["overview"] = ["Bundle: %s" % _shown(plan.bundle_dir)]
    view["overview"].append("Run root: %s" % run_root_line(recipe))
    production = recipe.first('production')
    if production:  # only production reads it (CL §37)
        settings = getattr(framework.stages[production.id], 'settings', None)
        used = "; from your user config: %s" % (", ".join(settings.used)) if settings and settings.used else ""
        view["overview"].append("PicoProducer config: %s%s"
                                % (plan.pico_config or "PicoProducer/config/config.json (default)", used))
    for stage, stage_plan in zip(view["stages"], plan.stages):
        stage_spec = recipe.stage(stage_plan.stage)
        stage["inputs"] = inputs_line(stage_spec, framework.stages[stage_spec.id], stage_plan.sources)
        stage["files"] = tuple((option, resolved, where) for option, _, resolved, where in stage_plan.paths)
        details = stage_plan.plan
        if details is None:  # placeholder, or an input from another run that cannot be read
            stage["note"] = stage_plan.note or "Not planned."
        elif hasattr(details, 'samples'):  # production: a PicoProducer JobPlan
            stage["samples"] = tuple((s.era, s.channel, s.name, s.nfiles, s.nchunks, s.subtry,
                                      "yes" if s.conflict else "") for s in details.samples)
            stage["jobs"] = details.nchunks
        elif hasattr(details, 'commands'):  # controlhists, controlplots, shapes, fit, python: local
            stage["cwd"] = details.cwd
            stage["subdirs"] = tuple(dict.fromkeys(os.path.relpath(command.cwd, details.cwd)
                                                   for command in details.commands
                                                   if getattr(command, 'cwd', details.cwd) != details.cwd))
            stage["steps"] = tuple((command.label, command_line(command)) for command in details.commands)
            stage["notes"] = tuple(details.notes)
        else:
            stage["notes"] = (repr(details),)
        if stage_plan.note and details is not None:
            stage["notes"] = (stage_plan.note,) + tuple(stage["notes"])
    jobs = sum(stage["jobs"] for stage in view["stages"])
    commands = sum(len(stage["steps"] or ()) for stage in view["stages"])
    view["overview"] += ["", "%d stage(s), %d job(s), %d command(s)" % (len(view["stages"]), jobs, commands)]
    view["warnings"] += [str(warning) for warning in plan.sample_warnings]
    view["errors"] += [str(problem) for problem in plan.sample_problems]


def _shown(path):
    """A path inside the checkout relative to it (shorter on a screen), any other path as it is."""
    try:
        return str(Path(path).resolve().relative_to(CHECKOUT))
    except ValueError:
        return str(path)


def _recipes_in(directory):
    """The analysis bundles (directories with a recipe.yml) and loose recipe files of a directory, by name; the
    user config is not a recipe. A directory without a recipe.yml (e.g. Examples/) is not listed."""
    directory = Path(directory)
    if not directory.is_dir():
        return []
    return sorted((p for p in directory.iterdir()
                   if (p.is_dir() and (p / RECIPE_NAME).is_file())
                   or (p.is_file() and p.suffix in (".yml", ".yaml", ".json") and p.name != USER_CONFIG_NAME)),
                  key=lambda p: p.name)


def _file_signature(path):
    """(inode, mtime, size) of a file, None without one: a file written again (run.json is replaced) has another."""
    try:
        status = os.stat(str(path))
    except OSError:
        return None
    return status.st_ino, status.st_mtime_ns, status.st_size


def _recipe_signature(path):
    """The signature of every file a recipe's check reads: the recipe file, or every file of its bundle, the
    templates of Configs/ (its copies are compared with them) and the user config (its run_root and production
    settings). Hidden files and directories are skipped."""
    path = Path(path)
    files = _tree(path) if path.is_dir() else [path]
    return tuple((str(file), _file_signature(file))
                 for file in files + _tree(Path(CONFIGS_DIR)) + [UserConfig.location()])


def _tree(directory):
    """Every file under a directory, sorted, without hidden files and directories."""
    found = []
    for parent, directories, names in os.walk(str(directory)):
        directories[:] = sorted(name for name in directories if not name.startswith('.'))
        found.extend(Path(parent) / name for name in sorted(names) if not name.startswith('.'))
    return found


def _proxy_file():
    """(mtime, size) of the grid proxy file ($X509_USER_PROXY, else /tmp/x509up_u<uid>), or None without one."""
    path = os.environ.get("X509_USER_PROXY") or "/tmp/x509up_u%s" % (os.getuid() if hasattr(os, "getuid") else "")
    try:
        status = os.stat(path)
    except OSError:
        return None
    return status.st_mtime_ns, status.st_size


def _text_files(directory, recipe, state_of):
    """The text files of a bundle directory (bundle_hashes' files, TEXT_SUFFIXES; not recipe.yml) as run_files
    lists them; recipe (or None): which stages read each one."""
    found = []
    for relative in sorted(bundle_hashes(directory)):
        if not relative.endswith(TEXT_SUFFIXES):
            continue
        readers = [stage_spec.id for stage_spec in (recipe.stages if recipe else ())
                   if relative in _bundle_paths(stage_spec, recipe.bundle_dir)]
        found.append(dict(path=relative, file=os.path.join(directory, relative), recipe=False, read_by=readers,
                          state=state_of(relative)))
    return found


def _bundle_paths(stage_spec, bundle_dir):
    """The bundle files (relative paths) a stage's path options name."""
    return {os.path.normpath(value) for _, value, _, where in path_rows(stage_spec.spec, bundle_dir)
            if where == 'bundle'}


def _edited_recipe(record):
    """The run's recipe file as a Recipe if it can be parsed (else None): the type of a stage an edit added."""
    try:
        return read_run_recipe(record, full=False)[0]
    except Exception:
        return None


def _stage_info(stage):
    """The facts of a stage for the box next to the run screen's stage list: its options as written in the
    recipe (config files, eras, channels, ...), its inputs and its output directory; [label, value] pairs."""
    facts = []
    for key, value in stage.items():
        if key in ("stage", "id", "description", "inputs") or value in (None, "", [], {}):
            continue
        facts.append([key.replace("_", " ").capitalize(), _fact(value)])
    inputs = stage.get("inputs") or {}
    if inputs:
        facts.append(["Inputs", ", ".join("%s: %s" % (slot, _fact(source)) if source != slot else str(slot)
                                          for slot, source in inputs.items())])
    facts.append(["Output", "%s/%s/" % (STAGES_DIR_NAME, stage.get("id"))])
    return facts


def _earlier_time(saved):
    """How long a DONE or FAILED stage took in the earlier advances of its run, as run.json recorded it, for the
    run screen: dict(seconds, commands, log), {} if nothing is recorded (or the stage did not finish).
    A local stage: its commands (last_status.commands: label, seconds, ok, log); seconds is their sum. Another stage
    (production): the time from its first to its last history entry (with the waits for the jobs)."""
    if saved.state not in ("DONE", "FAILED"):
        return {}
    commands = [command for command in (saved.last_status or {}).get("commands") or ()
                if isinstance(command, dict) and isinstance(command.get("seconds"), (int, float))]
    if commands:
        return dict(seconds=float(sum(command["seconds"] for command in commands)),
                    commands=[dict(label=command.get("label", ""), seconds=float(command["seconds"]),
                                   status="ok" if command.get("ok") else "failed", log=command.get("log"))
                              for command in commands],
                    log=commands[-1].get("log"))
    times = []
    for entry in saved.history:
        try:
            times.append(datetime.strptime(entry.get("time", ""), TIME_FORMAT))
        except (TypeError, ValueError):
            pass
    if len(times) < 2:
        return {}
    return dict(seconds=(times[-1] - times[0]).total_seconds())


def _fact(value):
    """A recipe value as one line: lists joined by spaces, mappings as `key: value`."""
    if isinstance(value, dict):
        return ", ".join("%s: %s" % (key, _fact(item)) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return " ".join(_fact(item) for item in value)
    return str(value)


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


def Menu(ui, launch_dir=None, recipes_dir=None, operations_dir=None, prefetch=None):
    """Build navigation with Framework callbacks. operations_dir: where the operations behind the menu are kept
    (default: OPERATIONS_DIR). prefetch: what reads the lists ahead (Menu/_prefetch.py; default: at once, in the
    caller)."""
    return MenuNavigation(ui, _Operations(launch_dir, recipes_dir, operations_dir), prefetch=prefetch)


def run_menu(parser):
    """Open the terminal UI (every command runs behind it as taufw.py); return a CLI exit code."""
    ui = ConsoleUI.open(parser)
    if ui is None:
        return 1
    try:
        # one curses session: nothing is printed between two screens; the lists are read ahead by a thread
        from TauFW.Framework._internal.notifications import OperationNotifications
        menu = Menu(ui, prefetch=Prefetch())
        with OperationNotifications(menu.operations.store.root):
            return ui.session(menu.run)
    except Exception as error:
        if not ui.is_terminal_error(error):
            raise
        ui.terminal_failure(error, parser)
        return 1
