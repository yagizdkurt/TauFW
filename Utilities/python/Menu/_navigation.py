"""Menu navigation independent of Framework, files, and batch operations.

The injected operations object supplies launch_dir, recipes(), runs(),
resolve_path(value), load_run(path), can_advance(record), validate_poll(value),
and execute(command, **values). Records expose run_id, run_dir, and state;
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
            action, index = self.ui.select_recipe([p.name for p in recipes])
            if action == "back":
                return
            if action == "manual":
                value = self.ui.recipe_path(self.operations.launch_dir)
                if not value:
                    continue
                path = self.operations.resolve_path(value)
            else:
                path = str(recipes[index])
            if not self._execute("plan", recipe=path):
                continue
            if self.ui.confirm_recipe(path) == "start":
                if self._execute("start", recipe=path):
                    return

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

    # =========================================================================
    # ============================ MAIN NAVIGATION ============================

    def run(self):
        actions = {"start": self.start, "continue": self.continue_run,
                   "inspect": self.inspect, "help": self.ui.help}
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

