# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Framework adapters for the Utilities menu navigation.

Discovery, path resolution, record access, validation, and CLI dispatch belong
here. Presentation and screen transitions live in TauFW.Utilities.Menu. Every
command runs behind the menu as taufw.py (OperationStore): start/advance/retry
(kind "run"), plan/status (kind "command", read only) and the tests; the
menu's own process reads recipes, run.json, check_recipe and a dry plan. The
User Config action creates a missing config and opens the independent Editor.
Install components opens FastSetup on the terminal and returns to the menu when it closes.

What Start and Continue list (a recipe's check, a run's row) is kept with the
signature of the files it was read from (path, inode, mtime, size: a stat
each), so a list reads again only what changed; the menu reads them ahead in
a thread of its own (Menu/_prefetch.py) and asks kept_recipe_preview() and
kept_run_row().
"""
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from TauFW.Framework.defaults import (ANALYSES_DIR, BUNDLE_DIR_NAME, CONFIGS_DIR, DEFAULT_RUN_ROOT, EXAMPLES_DIR_NAME,
                                      RECIPE_NAME, RUN_RECORD_NAME, STAGES_DIR_NAME, TIME_FORMAT)
from TauFW.Framework.runtime.run_record import RunRecord, RunState
from TauFW.Framework.recipes.recipe import Recipe, read_recipe
from TauFW.Framework.recipes.validation import check_recipe
from TauFW.Framework.recipes.analysis import create_analysis
from TauFW.Framework.recipes.bundle import bundle_changes, bundle_hashes
from TauFW.Framework.runtime.framework import Framework, retryable_stage
from TauFW.Framework.runtime.reporting import SilentReporter
from TauFW.Framework.runtime.run_lock import read_lock
from TauFW.Framework.stages.production import ProductionSpec
from TauFW.Framework.version import VersionChecker
from TauFW.Utilities.Menu import ConsoleUI, MenuNavigation, Prefetch
from TauFW.Utilities import UserConfig
from TauFW.Utilities.UserConfig import manage as user_config
from TauFW.Framework.user_settings import run_root_or_none as user_run_root
from TauFW.Utilities.Process import LOST, EventReader, OperationStore

CHECKOUT = Path(__file__).resolve().parents[3]
OPERATIONS_DIR = CHECKOUT / ".artifacts" / "menu" / "operations"  # what runs behind the menu (git-ignored)
TAUFW_SCRIPT = CHECKOUT / "Framework" / "scripts" / "taufw.py"
PROXY_MARGIN = 60  # seconds a proxy must still be valid for (voms-proxy-info --valid 0:01 before)
PROXY_INIT_TIMEOUT = 120  # seconds voms-proxy-init may take (it asks the VOMS server)
USER_CONFIG_NAME = user_config.FILE_NAME


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
        """The manual of this checkout, also when the config lives elsewhere."""
        return CHECKOUT / "Docs" / "Manual" / "1-GettingStarted" / "UserConfig.md"

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

    @staticmethod
    def _recipe_view(recipe, path):
        """Plain presentation data; Utilities never needs Framework objects."""
        return dict(name=recipe.name, path=str(path),
                    stages=tuple((stage.id, stage.stage, stage.description) for stage in recipe.stages),
                    notes=(), problems=(), warnings=tuple(str(warning) for warning in recipe.warnings))

    def recipe_preview(self, path):
        """Check the recipe (validation.py) without constructing stage APIs: its stages and every problem; a
        recipe that cannot be checked: its name and the error. Kept until a file of it changes (kept_recipe_preview;
        also a template of Configs/, its copies are compared with them)."""
        signature = _recipe_signature(path)
        try:
            check = check_recipe(str(path), allow_draft=True)
            view = dict(name=check.name, path=str(path), stages=check.stages, notes=(),
                        draft=check.draft,
                        problems=tuple(str(issue) for issue in check.issues),
                        warnings=tuple(str(warning) for warning in check.warnings))
        except Exception as error:
            view = dict(name=Path(path).name, error=str(error))
        self._kept[("preview", str(path))] = (signature, view)
        return view

    def kept_recipe_preview(self, path):
        """The preview of the recipe as recipe_preview() left it, if no file of it changed since; else None."""
        return self._kept_value("preview", path, _recipe_signature)

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
        return dict(run_id=record.run_id, run_dir=record.run_dir, state=str(record.state), updated=record.updated,
                    stages=[dict(id=stage.name, state=str(stage.state), message=stage.message)
                            for stage in record.stages],
                    can_advance=self.can_advance(record), retry=self.retry_info(record),
                    lock=self.run_lock(run_dir), advancing=advancing is not None)

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
        stages = [dict(id=stage["id"], type=stage["stage"], state="NEW", message="", info=_stage_info(stage))
                  for stage in loaded.to_dict()["stages"]]
        return self._start_run(loaded.name, ["start", str(recipe), "--wait"],
                               dict(run_id=loaded.name, run_dir="", stages=stages))

    def advance_run(self, record, wait=True, take_lock=False):
        """`taufw.py advance RUN_DIR` behind the menu, with --wait (to the end) or once; take_lock: take over
        the lock of a lost advance (--take-lock). The earlier advances of the run count as seen."""
        argv = ["advance", record.run_dir] + (["--wait"] if wait else []) + (["--take-lock"] if take_lock else [])
        return self._run_of(record, argv)

    def retry_run(self, record, take_lock=False):
        """`taufw.py retry RUN_DIR --wait` behind the menu: the failed stage again, then to the end (CL §44);
        take_lock: take over the lock of a lost advance (--take-lock)."""
        return self._run_of(record, ["retry", record.run_dir, "--wait"] + (["--take-lock"] if take_lock else []))

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
            info = _stage_info(stage) + ([["Attempt", str(saved.attempt)]] if saved.attempt else [])
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
        """`taufw.py plan RECIPE` or `taufw.py status RUN_DIR` behind the menu; return its Operation (kind
        "command", data: command, target). Its screen shows the plain output and stops it when it is left (a
        status with production asks HTCondor, which may take seconds; the menu keeps drawing)."""
        if command not in ("plan", "status"):
            raise ValueError("Not a read-only command: %s" % command)
        self.store.prune("command", keep=4)  # with the new one: the last five
        return self.store.start("command", "%s %s" % (command, Path(target).name),
                                [sys.executable, "-B", str(TAUFW_SCRIPT), command, str(target)],
                                str(self.launch_dir), data=dict(command=command, target=str(target)))


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
        return ui.session(Menu(ui, prefetch=Prefetch()).run)
    except Exception as error:
        if not ui.is_terminal_error(error):
            raise
        ui.terminal_failure(error, parser)
        return 1
