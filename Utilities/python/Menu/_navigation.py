# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Menu navigation independent of Framework, files, and batch operations.

The injected operations object supplies launch_dir, recipes(), runs(),
resolve_path(value), load_run(path), can_advance(record), validate_poll(value),
recipe_preview(path), prepare_review(path), and execute(command, **values).
Recipe views contain name, path, ordered (stage id, type, description) triples, notes, and problems (a recipe with
problems is shown in red and cannot start).
Records expose run_id, run_dir, and state;
run rows are (created, path, (run_id, state, updated)). Only operations reads
files, validates values, or invokes commands. This class owns screen transitions.
"""
from ._menu import ConsoleUI


class MenuNavigation:
    """Navigate the user journey using a UI and caller-supplied operations."""

    # =========================================================================
    # ================================= SETUP =================================

    def __init__(self, ui, operations):
        self.ui = ui
        self.operations = operations

    # =========================================================================
    # ============================ OPERATION FEEDBACK =========================

    def _execute(self, command, **values):
        try:
            result = self.operations.execute(command, **values)
        except KeyboardInterrupt:
            self.ui.interrupted_operation()
            return False
        except Exception as error:
            self.ui.operation_error(error)
            return False
        finally:
            self.ui.pause()
        return result in (None, 0)

    # =========================================================================
    # =========================== RECIPE NAVIGATION ===========================

    def start(self):
        while True:
            recipes = self.operations.recipes()
            previews = [self._preview(path) for path in recipes]  # all at once: the list marks broken recipes
            broken = [bool(view.get("error") or view.get("problems")) for view in previews]
            action, index = self.ui.select_recipe([p.name for p in recipes], preview=lambda i: previews[i],
                                                  broken=broken)
            if action == "back":
                return
            if action == "manual":
                value = self.ui.recipe_path(self.operations.launch_dir)
                if not value:
                    continue
                path = self.operations.resolve_path(value)
            else:
                path = str(recipes[index])
            try:
                review = self.operations.prepare_review(path)
            except KeyboardInterrupt:
                return
            except Exception as error:
                self.ui.operation_error(error)
                self.ui.pause()
                continue
            position = {}
            while True:
                action = self.ui.confirm_recipe(path, review=review, position=position)
                if action == "back":
                    break
                if action == "plan":
                    self._execute("plan", recipe=path)
                elif action == "start":
                    if self._execute("start", recipe=path):
                        return
                    break

    def _preview(self, path):
        try:
            return self.operations.recipe_preview(str(path))
        except Exception as error:
            return dict(name=path.name, error=str(error))

    # =========================================================================
    # ============================= RUN NAVIGATION ============================

    def _pick_run(self):
        while True:
            runs = self.operations.runs()
            action, index = self.ui.select_run([r[2] for r in runs])
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
                return self.operations.load_run(path)
            except Exception as error:
                self.ui.unreadable_run(error)

    def inspect(self, record=None):
        if record is not None:
            return self._inspect_record(record)
        while True:
            record = self._pick_run()
            if record is None:
                return
            self._inspect_record(record)

    def _inspect_record(self, record):
        while True:
            self._execute("status", run_dir=record.run_dir)
            if self.ui.status_actions(record.run_id) != "refresh":
                return

    def continue_run(self):
        while True:
            record = self._pick_run()
            if record is None:
                return
            while True:
                if not self.operations.can_advance(record):
                    if self.ui.terminal_run_actions(record.state) == "inspect":
                        self.inspect(record)
                        continue
                    break
                action = self.ui.continue_actions(record.run_id)
                if action == "back":
                    break
                poll = self._poll_interval() if action == "wait" else 600
                if poll is None:
                    continue
                self._execute("advance", run_dir=record.run_dir, wait=action == "wait", poll=poll)
                return

    def _poll_interval(self):
        while True:
            value = self.ui.poll_interval()
            if value is None:
                return None
            try:
                return self.operations.validate_poll(value)
            except ValueError:
                pass
            self.ui.invalid_poll_interval()

    def tests(self):
        """Browse caller-supplied metadata and run only automated actions."""
        titles = {"checks": "Unit and harness checks", "normal": "Normal tests",
                  "bbb": "BBB regression checks", "all": "All automated tests",
                  "environment": "Check environment"}
        while True:
            try:
                family = self.ui.tests_menu()
                if family == "back":
                    return
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
                try:
                    self.operations.execute_tests(family, selected)
                except KeyboardInterrupt:
                    self.ui.interrupted_tests()
                except Exception as error:
                    if isinstance(self.ui, ConsoleUI) and self.ui.is_terminal_error(error):
                        raise
                    self.ui.operation_error(error)
                finally:
                    self.ui.pause()
            except KeyboardInterrupt:
                continue
            except Exception as error:
                if isinstance(self.ui, ConsoleUI) and self.ui.is_terminal_error(error):
                    raise
                self.ui.operation_error(error)
                self.ui.pause()

    # =========================================================================
    # ============================ MAIN NAVIGATION ============================

    def run(self):
        actions = {"start": self.start, "continue": self.continue_run,
                   "inspect": self.inspect, "tests": self.tests, "help": self.ui.help}
        while True:
            try:
                action = self.ui.main_menu()
                if action == "exit":
                    return 0
                actions[action]()
            except KeyboardInterrupt:
                continue
            except Exception as error:
                if isinstance(self.ui, ConsoleUI) and self.ui.is_terminal_error(error):
                    raise  # Terminal failures cannot be recovered by drawing another menu.
                self.ui.operation_error(error)
                self.ui.pause()

