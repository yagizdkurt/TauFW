# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""The screen of a read-only command behind the menu (`taufw.py plan`, `taufw.py status`): its plain output.

The command is a TauFW.Utilities.Process.Operation (its supervisor runs it, so
a slow command, e.g. a status that asks HTCondor, never stops the menu from
drawing); the screen is the operation screen (_operation_screen.py) with
CommandOutput as its model, which has no items: only the Output view.

    process.output  ─▶ Output view (Up/Down/PgUp/PgDn, End follows the end)
    process.state() ─▶ RUNNING, STOPPING, DONE, FAILED, STOPPED or LOST | time | the command (+ its exit code)

Leaving it (Esc) stops a command that still runs, without a question (it only
reads: nothing is lost); S stops it and stays. Nothing of it stays behind the
menu. With refresh, R runs the command again once it ended. No Framework
imports belong here (see _test_run.py).
"""
from ._operation_screen import ScreenModel, follow

__all__ = ["CommandOutput", "follow_command"]


# =============================================================================
# ================================== MODEL ====================================


class CommandOutput(ScreenModel):
    """A command's output and nothing else. command: its words on the state line (`taufw.py status`)."""

    output_title = "Output"
    stopping = "Stopping..."
    leave_stops = True

    def __init__(self, command, refresh=False):
        super().__init__()
        self.command = command
        self.returncode = None
        if refresh:
            self.actions = (("R", "Refresh", "refresh"),)

    def finish(self, returncode, lost=False, state=None):
        self.returncode = returncode

    def summary(self):
        return self.command + (" (exit %s)" % self.returncode if self.returncode not in (None, 0) else "")


# =============================================================================
# ================================== SCREEN ===================================


def follow_command(ui, screen, title, process, refresh=False):
    """Draw the command's output until the user leaves (a command that still runs is stopped then).
    Return "refresh" (R once it ended, with refresh) or "back"."""
    model = CommandOutput("taufw.py %s" % process.data.get("command", ""), refresh)
    follow(ui, screen, title, process, model)
    return model.answer or "back"
