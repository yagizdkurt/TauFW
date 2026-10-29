"""Terminal-only bells and once-per-result menu notifications, without real audio."""
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import checkout  # noqa: F401
from TauFW.Utilities.Internal import Notifications
from TauFW.Utilities.UserConfig import load, manage


class Terminal(io.StringIO):
    def isatty(self):
        return True


class NotificationTests(unittest.TestCase):
    def test_config_controls_terminal_bells_and_validates_boolean(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "UserConfig.yaml"
            manage.create(path, values={"notifications": False})
            self.assertIs(load(path).get("notifications"), False)
            self.assertEqual(manage.setting_problems(load(path), "notifications"), [])
            with mock.patch.dict(os.environ, {manage.ENVVAR: str(path)}):
                terminal = Terminal()
                self.assertFalse(Notifications.bell(terminal))
                self.assertEqual(terminal.getvalue(), "")
                path.write_text(path.read_text().replace("notifications: false", "notifications: true"))
                self.assertTrue(Notifications.bell(terminal))
                self.assertEqual(terminal.getvalue(), "\a")
                path.write_text(path.read_text().replace("notifications: true", 'notifications: "false"'))
                self.assertIn("must be true or false", manage.setting_problems(load(path))[0])

    def test_default_enabled_but_logs_broken_config_and_closed_terminal_stay_silent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "UserConfig.yaml"
            with mock.patch.dict(os.environ, {manage.ENVVAR: str(path)}):
                terminal, log = Terminal(), io.StringIO()
                self.assertTrue(Notifications.bell(terminal))  # missing config: enabled
                self.assertFalse(Notifications.bell(log))
                self.assertEqual(log.getvalue(), "")
                terminal.close()
                self.assertFalse(Notifications.bell(terminal))
                path.write_text("invalid: [")
                self.assertFalse(Notifications.bell(Terminal()))

    def test_menu_notifies_once_for_new_results_and_ignores_history_waiting_and_cancel(self):
        with tempfile.TemporaryDirectory() as directory:
            events = Path(directory) / "events.jsonl"
            events.write_text(json.dumps({"kind": "run_state", "state": "WAITING"}) + "\n")
            def operation(name, state="RUNNING", kind="tests"):
                item = SimpleNamespace(path=name, kind=kind, events_path=str(events), value=state)
                item.state = lambda: item.value
                return item
            old = operation("old", "DONE")
            test = operation("test")
            waiting = operation("waiting", kind="run")
            cancelled = operation("cancelled")
            watcher = Notifications.OperationNotifications(directory)
            items = [old, test, waiting, cancelled]
            with mock.patch.object(watcher.store, "all", return_value=items), \
                    mock.patch.object(Notifications, "bell") as bell:
                watcher.poll(initial=True)
                watcher.poll()
                bell.assert_not_called()
                test.value = "FAILED"
                watcher.poll()
                watcher.poll()
                bell.assert_called_once()
                waiting.value, cancelled.value = "DONE", "STOPPED"
                watcher.poll()
                self.assertEqual(bell.call_count, 1)
                items.append(operation("fast", "DONE"))  # finishes between two polls
                watcher.poll()
                watcher.poll()
                self.assertEqual(bell.call_count, 2)
                events.write_text(json.dumps({"kind": "run_state", "state": "DONE"}) + "\n")
                items.append(operation("recipe", "DONE", "run"))
                watcher.poll()
                watcher.poll()
                self.assertEqual(bell.call_count, 3)


if __name__ == "__main__":
    unittest.main()
