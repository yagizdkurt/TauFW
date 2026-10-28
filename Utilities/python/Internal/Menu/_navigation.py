# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Menu navigation independent of Framework, files, and batch operations.

The injected operations object supplies launch_dir, recipes(), examples() (the example analyses, listed apart
under [Examples] of the recipe list), resolve_path(value), load_run(path),
can_advance(record), prepare_review(path), and start_command(command, target), which starts a read-only command
(`plan` of a recipe, `status` of a run directory) behind the menu and returns its Operation (kind "command"; its
screen, ConsoleUI.command_output, stops it when it is left).
Recipe views contain name, path, ordered (stage id, type, description) triples, notes, problems (a recipe with
problems is shown in red and cannot start) and warnings (yellow; the recipe can still start).
Records expose run_id, run_dir, and state;
run rows are (created, path, (run_id, state, updated)). The lists of Start and Continue/Inspect are read ahead:
recipe_preview(path) and run_row(run_dir) compute and keep (in a Prefetch job, from the menu's start on),
kept_recipe_preview(path) and kept_run_row(run_dir) give what was kept while its files did not change (else None:
the row says "checking..." and the list draws itself again until it came), run_directories() names the runs.
Only operations reads
files, validates values, or invokes commands. Grid callbacks are grid_proxy_valid(fresh=False)
(the main menu may get a kept answer; fresh before a run), renew_grid_proxy(password) -> (valid, output), valid
None when voms-proxy-init cannot read the password from stdin, and renew_grid_proxy_in_terminal() (it asks on the
plain terminal, ConsoleUI.in_terminal). Test callbacks are test_catalog(), start_tests(family, cases, title, expected), which
returns the TauFW.Utilities.Process.Operation that the test screen follows, and tests_operation(), the last test
run (or None). Run callbacks: start_run(recipe), advance_run(record, wait, take_lock) and retry_run(record, take_lock)
(the failed stage of a FAILED run again, then to the end) start taufw.py behind the menu and return its Operation
(kind "run"); retry_info(record) is what a retry would do (dict(stage, type, message, changed[, tries]), or None: no
retry); run_operations() (the advances for the main menu), run_operation(run_dir)
(the advance of a run that runs now), run_advances(run_dirs) (for the run list), run_lock(run_dir) (its advance lock
or None), mark_seen(operation), needs_grid_proxy(recipe=, record=). running_operations() lists what runs behind the
menu, stop_operation(operation) stops one.
User config callbacks: user_config_path() creates the file if missing and names
it; user_config_reference() names its Markdown manual in the checkout;
validate_user_config(draft_path) checks a candidate file before the editor saves it; user_config_reviewed()
is False while the file is missing or not reviewed yet (the main menu asks for it).
create_analysis(name) creates an empty analysis in the recipe root and returns its path. Recipe views mark
well-formed empty recipes with draft=True; they can be listed and edited, but cannot start.
The independent Editor owns file editing and saving; navigation only opens it.
install_components() opens the existing interactive installer on the terminal and returns when it closes.
version_status() returns plain installed/latest/status/checking/available/stale data; only the caller checks
versions. While it is checking, the main menu also uses its existing live refresh.
The Tests menu also opens the UI preview (ConsoleUI.preview(), made-up screens; no operations are used).
Operations run behind the menu: leaving a screen or quitting never stops them (quitting warns first).
While one runs, the main menu draws itself again every 2 s (ConsoleUI.main_menu(live=True)). An error is shown
in a panel over the current screen (ui.operation_error). This class owns screen transitions.
"""
from ._menu import ConsoleUI
from ._prefetch import Prefetch
from ._run_preview import RunPreview


class MenuNavigation:
    """Navigate the user journey using a UI and caller-supplied operations."""

    # =========================================================================
    # ================================= SETUP =================================

    def __init__(self, ui, operations, prefetch=None):
        """prefetch: what reads the lists ahead (a Prefetch with its thread: the menu); default: each read at once,
        in the caller."""
        self.ui = ui
        self.operations = operations
        self.prefetch = prefetch if prefetch is not None else Prefetch(threaded=False)

    def _read_ahead(self):
        """Read what Start and Continue/Inspect list, behind the main menu: every recipe's check, then every run."""
        self.prefetch.add("recipes", lambda: [self._ask_preview(path) for path in self.operations.recipes()])
        self.prefetch.add("examples", lambda: [self._ask_preview(path) for path in self.operations.examples()])
        self.prefetch.add("runs", lambda: [self._ask_row(run_dir) for run_dir in self.operations.run_directories()])

    def _ask_preview(self, path):
        self.prefetch.add(("recipe", str(path)), lambda: self.operations.recipe_preview(path))

    def _ask_row(self, run_dir):
        self.prefetch.add(("run", str(run_dir)), lambda: self.operations.run_row(run_dir))

    # =========================================================================
    # ============================ OPERATION FEEDBACK =========================

    def _command(self, title, command, target, refresh=False):
        """Run a read-only command behind the menu and show its output; with refresh, R runs it again."""
        try:
            while self.ui.command_output(title, self.operations.start_command(command, target),
                                         refresh=refresh) == "refresh":
                pass
        except KeyboardInterrupt:
            pass
        except Exception as error:
            if isinstance(self.ui, ConsoleUI) and self.ui.is_terminal_error(error):
                raise
            self.ui.operation_error(error)

    # =========================================================================
    # =========================== RECIPE NAVIGATION ===========================

    def start(self):
        """The recipe list opens at once: a recipe whose check is not read yet says "checking..." and the list
        draws itself again until every check came (read ahead from the menu's start, see _read_ahead)."""
        self._pick_recipe()

    def _pick_recipe(self, examples=False):
        """The recipe list, or with examples the list of the example analyses ([Examples] of the recipe list, the
        same screen without the create action). True once a run was started: back to the main menu."""
        position, created = {}, None
        while True:
            recipes = self.operations.examples() if examples else self.operations.recipes()
            if created is not None:
                for index, path in enumerate(recipes):
                    if path.resolve() == created.resolve():
                        position.update(selected=index + 1, offset=0)  # the create action is the first row
                        break
                created = None
            previews = [self._kept_preview(path) for path in recipes]
            checking = [view is None for view in previews]
            previews = [view if view is not None else dict(name=path.name, hint="Checking the recipe...")
                        for path, view in zip(recipes, previews)]
            broken = [bool(view.get("error") or view.get("problems")) for view in previews]
            warnings = [bool(view.get("warnings")) for view in previews]
            action, index = self.ui.select_recipe([p.name for p in recipes], preview=lambda i: previews[i],
                                                  broken=broken, warnings=warnings, checking=checking,
                                                  position=position, live=any(checking),
                                                  drafts=[bool(view.get("draft")) for view in previews],
                                                  **(dict(examples=True) if examples else {}))
            if action == "refresh":
                continue  # a check came
            if action == "back":
                return False
            if action == "examples":
                if self._pick_recipe(examples=True):
                    return True
                continue
            if action == "create":
                created = self._create_analysis()
                continue
            if action == "manual":
                value = self.ui.recipe_path(self.operations.launch_dir)
                if not value:
                    continue
                path = self.operations.resolve_path(value)
            else:
                path = str(recipes[index])
            if action == "edit":
                self.edit_analysis(path)
                continue
            try:
                view = self.operations.recipe_preview(path) if action == "manual" else previews[index]
                if view.get("draft"):
                    self.ui.message("Analysis draft", "No stages configured. Press E for Run editor.")
                    continue
                review = self.operations.prepare_review(path)
            except KeyboardInterrupt:
                return False
            except Exception as error:
                self.ui.operation_error(error)
                continue
            review_position = {}
            while True:
                action = self.ui.confirm_recipe(path, review=review, position=review_position)
                if action == "back":
                    break
                if action == "plan":
                    self._command("Plan: %s" % (review.get("name") or path), "plan", path)
                elif action == "start":
                    if not self._grid_ready(self.operations.needs_grid_proxy(recipe=path)):
                        continue
                    self._follow_run(self.operations.start_run(path))
                    return True

    def _create_analysis(self):
        """Ask again after an error, keeping the name. Cancellation never creates a file."""
        value = ""
        while True:
            value = self.ui.analysis_name(default=value)
            if value is None:
                return None
            try:
                path = self.operations.create_analysis(value)
            except Exception as error:
                self.ui.operation_error(error)
                continue
            self.ui.message("Analysis created", "Analysis created: %s\nPress E for Run editor." % path, "good")
            return path

    def edit_analysis(self, path):
        """Run editor entry point; its screen is designed in the next step."""
        self.ui.message("Run editor", "Run editor will be added in the next step.\nAnalysis: %s" % path)

    def _kept_preview(self, path):
        """The kept check of a recipe, or None while it is read (asked for here if it is not)."""
        view = self.operations.kept_recipe_preview(path)
        if view is None:
            self._ask_preview(path)
            view = self.operations.kept_recipe_preview(path)  # read at once without a thread
        return view

    # =========================================================================
    # ============================= RUN NAVIGATION ============================

    def _run_listing(self, kept):
        """Discover/read list data in the browser worker (or immediately for a caller without threads)."""
        rows, loading = [], []
        for run_dir in self.operations.run_directories():
            row = self._kept_row(run_dir)
            (rows if row is not None else loading).append(row or ("", run_dir, None))
        rows = sorted(rows, key=lambda row: (row[0], row[1]), reverse=True)
        runs = rows + sorted(loading, key=lambda row: row[1], reverse=True)
        advances = self.operations.run_advances([row[1] for row in runs])
        summaries = [self._summary(row, advance) for row, advance in zip(runs, advances)]
        # Summary reads consume operation events too; keep those reads in this worker.
        advance_labels = [(self.ui._operation_summary(advance, kept), advance.running) if advance is not None else None
                          for advance in advances]
        return runs, advances, summaries, advance_labels

    def _pick_run(self, mode="inspect"):
        """The run list opens at once: a run whose run.json is not read yet says "loading..." (after the others)
        and the list draws itself again until every row came; the selected run stays selected."""
        position, focus, kept = {}, None, {}
        browser = RunPreview(self.operations, mode, listing=lambda: self._run_listing(kept),
                             threaded=self.prefetch.threaded is True)
        try:
            while True:
                catalog, error = browser.catalog()
                if error:
                    self.ui.operation_error(RuntimeError(error))
                    return None
                runs, advances, summaries, advance_labels = catalog or ([], [], [], [])
                paths = [row[1] for row in runs]
                if focus in paths:
                    position["selected"] = paths.index(focus)
                action, index = self.ui.select_run(summaries, advances=advances,
                        loading=[row[2] is None for row in runs], position=position,
                        live=browser.threaded or any(row[2] is None for row in runs),
                        preview=lambda i, refresh=False: browser.view(paths[i] if i is not None else None, refresh),
                        mode=mode, finding=catalog is None, advance_labels=advance_labels)
                selected = position.get("selected", 0)
                focus = paths[selected] if selected < len(paths) else None
                if action == "refresh":
                    continue
                if action == "back":
                    return None
                if action == "manual":
                    value = self.ui.run_path(self.operations.launch_dir)
                    if not value:
                        continue
                    path = self.operations.resolve_path(value)
                else:
                    path = runs[index][1]
                try:
                    return self.operations.load_run(path), action
                except Exception as error:
                    self.ui.unreadable_run(error)
        finally:
            browser.close()

    def _summary(self, row, advance):
        """(run_id, state, updated) of a run row. A RUNNING run (run.json: a stage started, none waits) that no
        advance works on now (none behind the menu, no live run lock: advanced from the CLI) is PAUSED: it waits
        for the next advance. Only the list says so; run.json and `taufw.py status` still say RUNNING (see
        Docs/Develop/Refactor-2025/TODO.md)."""
        if row[2] is None:
            return _name(row[1]), None, None
        run_id, state, updated = row[2]
        if state == "RUNNING" and not (advance is not None and advance.running):
            lock = self.operations.run_lock(row[1])
            if lock is None or lock.get("lost"):
                state = "PAUSED"
        return run_id, state, updated

    def _kept_row(self, run_dir):
        """The kept row of a run, or None while its run.json is read (asked for here if it is not)."""
        row = self.operations.kept_run_row(run_dir)
        if row is None:
            self._ask_row(run_dir)
            row = self.operations.kept_run_row(run_dir)  # read at once without a thread
        return row

    def inspect(self, record=None):
        if record is not None:
            return self._inspect_record(record)
        while True:
            picked = self._pick_run()
            if picked is None:
                return
            record, _ = picked
            self._inspect_record(record)

    def _inspect_record(self, record):
        self._command("Run status: %s" % record.run_id, "status", record.run_dir, refresh=True)

    def continue_run(self):
        """Pick a run and advance it behind the menu: to the end (taufw.py advance --wait) or once. A run that an
        advance works on now opens its screen; one whose lock another advance holds shows the lock (a lost one
        may be taken over)."""
        while True:
            picked = self._pick_run("continue")
            if picked is None:
                return
            record, chosen = picked
            if chosen == "inspect":
                self._inspect_record(record)
                continue
            while True:
                advancing = self.operations.run_operation(record.run_dir)
                if advancing is not None:
                    self._follow_run(advancing)
                    return
                if not self.operations.can_advance(record):
                    retry = self.operations.retry_info(record)
                    action = "retry" if chosen == "retry" and retry else \
                        self.ui.terminal_run_actions(record.state, retry=retry)
                    chosen = None
                    if action == "inspect":
                        self.inspect(record)
                        continue
                    if action != "retry":
                        break
                    take_lock = self._take_lock(record)  # a retry takes the run's lock too
                    if take_lock is None:
                        break
                    if not self._grid_ready(self.operations.needs_grid_proxy(record=record)):  # production resubmits
                        continue
                    # the failed stage again, then to the end (CL §44; production after max_tries: CL §48)
                    self._follow_run(self.operations.retry_run(record, take_lock=take_lock))
                    return
                take_lock = self._take_lock(record)
                if take_lock is None:
                    break
                action = chosen if chosen in ("wait", "advance") else self.ui.continue_actions(record.run_id)
                chosen = None
                if action == "back":
                    break
                if not self._grid_ready(self.operations.needs_grid_proxy(record=record)):
                    continue
                self._follow_run(self.operations.advance_run(record, wait=action == "wait", take_lock=take_lock))
                return

    def _take_lock(self, record):
        """Before an advance or a retry: False (no lock, or a lost one of this machine, which taufw.py takes over
        itself), True (the user takes over a lost lock: --take-lock), None (locked: back)."""
        lock = self.operations.run_lock(record.run_dir)
        if lock is None or (lock.get("lost") and lock.get("local")):
            return False
        return True if self.ui.run_lock(record.run_id, lock) == "take" else None

    def _follow_run(self, operation):
        """Show an advance; once it ended, its result was seen (the main menu stops listing it)."""
        self.ui.run_progress("Run %s" % (operation.data.get("run_id") or operation.title), operation)
        if not operation.running:
            self.operations.mark_seen(operation)

    def follow_runs(self):
        """The main menu's run line: one advance opens at once, more are chosen first."""
        while True:
            runs = self.operations.run_operations()
            if not runs:
                return
            if len(runs) == 1:
                return self._follow_run(runs[0])
            action, index = self.ui.active_runs(runs)
            if action == "back":
                return
            self._follow_run(runs[index])

    def _grid_ready(self, needed):
        """Whether a run may start: no grid proxy is needed, or it is valid (renewed here if the user agrees)."""
        while needed and not self.operations.grid_proxy_valid(fresh=True):  # never a kept answer before a run
            if self.ui.grid_proxy_needed() != "renew":
                return False
            self.grid_certificate()
        return True

    def tests(self):
        """Browse caller-supplied metadata and run only automated actions. One test run at a time: while one
        runs (also from another menu), Tests opens its screen; the screen's Esc leaves it running and returns to
        the main menu, which shows its state."""
        titles = {"checks": "Unit and harness checks", "normal": "Normal tests",
                  "bbb": "BBB regression checks", "all": "All automated tests",
                  "environment": "Check environment"}
        while True:
            try:
                last = self.operations.tests_operation()
                if last is not None and last.running:
                    if self._follow_tests(last):
                        return
                    continue
                family = self.ui.tests_menu(last=last)
                if family == "back":
                    return
                if family == "last":
                    self._follow_tests(last)
                    continue
                if family == "preview":
                    self.ui.preview()  # made-up screens: nothing runs
                    continue
                if family == "environment":
                    items = [dict(id="environment", description="Advisory CMSSW Python package-origin check; "
                                  "no tests run and no packages are changed.", dependencies=[])]
                    selected = []
                else:
                    catalog = self.operations.test_catalog()
                    items = ([item for name in ("checks", "normal", "bbb") for item in catalog[name]]
                             if family == "all" else catalog[family])
                    selected = []
                    if family != "all":
                        action = self.ui.test_family(titles[family])
                        if action == "back":
                            continue
                        if action == "choose":
                            selected = self.ui.test_selection(titles[family], items)
                            if not selected:
                                continue
                            items = [item for item in items if item["id"] in selected]
                if not items:
                    raise ValueError("No automated tests available in this family.")
                if self.ui.test_selection("Review / " + titles[family], items, review=True) is None:
                    continue
                # "all": [family, id] pairs (an id may be in two families); the environment check runs no cases.
                if family == "all":
                    expected = [[name, item["id"]] for name in ("checks", "normal", "bbb") for item in catalog[name]]
                else:
                    expected = [] if family == "environment" else [item["id"] for item in items]
                operation = self.operations.start_tests(family, selected, titles[family], expected)
                if self._follow_tests(operation):
                    return
            except KeyboardInterrupt:
                continue
            except Exception as error:
                if isinstance(self.ui, ConsoleUI) and self.ui.is_terminal_error(error):
                    raise
                self.ui.operation_error(error)

    def _follow_tests(self, operation):
        """Show a test run; True if it still runs when the screen is left (back to the main menu)."""
        self.ui.test_run(operation.title, operation, operation.data.get("expected", []))
        return operation.running

    # =========================================================================
    # ============================ MAIN NAVIGATION ============================

    def _may_quit(self):
        """Whether the menu may close: nothing runs behind it, or the user chose to quit anyway or to stop it
        all first (the stop is asked for; the supervisors stop the commands after the menu closed)."""
        running = self.operations.running_operations()
        if not running:
            return True
        choice = self.ui.quit_running(running)
        if choice == "stop":
            for operation in running:
                self.operations.stop_operation(operation)
        return choice in ("stop", "quit")

    def grid_certificate(self):
        """Renew the grid proxy: the password typed in the menu goes to voms-proxy-init on its stdin; a
        voms-proxy-init that cannot read it there asks on the plain terminal instead."""
        password = self.ui.grid_password()
        if password is None:
            return
        try:
            self.ui.notice("Grid Certificate", "Renewing the grid proxy (voms-proxy-init -voms cms)...")
            valid, output = self.operations.renew_grid_proxy(password)
            password = None
            if valid is None:
                valid = self.ui.in_terminal(self.operations.renew_grid_proxy_in_terminal) == 0
                output = ""
        except KeyboardInterrupt:
            return  # The next main-menu check refreshes the status after cancellation.
        except Exception as error:
            if isinstance(self.ui, ConsoleUI) and self.ui.is_terminal_error(error):
                raise
            self.ui.operation_error(error)
            return
        self.ui.grid_result(valid, output)

    def user_config(self):
        self.ui.edit_file(self.operations.user_config_path(), self.operations.validate_user_config,
                          title="Modify User Config", reference=self.operations.user_config_reference())

    def install(self):
        self.ui.in_terminal(self.operations.install_components, pause=False)

    def run(self):
        self._read_ahead()
        actions = {"start": self.start, "continue": self.continue_run, "run": self.follow_runs,
                   "runs": self.follow_runs, "inspect": self.inspect, "tests": self.tests,
                   "grid_certificate": self.grid_certificate, "user_config": self.user_config, "install": self.install,
                   "help": self.ui.help}
        while True:
            try:
                tests, runs = self.operations.tests_operation(), self.operations.run_operations()
                version = self.operations.version_status()
                live = ((tests is not None and tests.running) or any(operation.running for operation in runs)
                        or bool(version and version['checking']))
                action = self.ui.main_menu(proxy_valid=self.operations.grid_proxy_valid(), tests=tests, runs=runs,
                                           live=live, version=version,
                                           config_reviewed=self.operations.user_config_reviewed())
                if action == "refresh":
                    continue  # live: the new states
                if action == "exit":
                    if self._may_quit():
                        return 0
                    continue
                actions[action]()
            except KeyboardInterrupt:
                continue
            except Exception as error:
                if isinstance(self.ui, ConsoleUI) and self.ui.is_terminal_error(error):
                    raise  # Terminal failures cannot be recovered by drawing another menu.
                self.ui.operation_error(error)


def _name(path):
    """The last part of a run directory: its name until its run.json is read."""
    return str(path).replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
