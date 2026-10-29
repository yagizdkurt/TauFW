# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""The screen of a read-only command behind the menu (`taufw.py plan`, `taufw.py status`): its plain output.

The command is a TauFW.Utilities.Internal.Operations.Operation (its supervisor runs it, so
a slow command, e.g. a status that asks HTCondor, never stops the menu from
drawing); the screen is the operation screen (_operation_screen.py) with
CommandOutput as its model, which has no items: only the Output view.

    process.output  ─▶ Output view (Up/Down/PgUp/PgDn, End follows the end)
    process.state() ─▶ READING STATUS (READING PLAN), STOPPING, FAILED, STOPPED or LOST | time | the command
                       (+ its exit code); once it is done, only the time and the command

The state line is the command's, not the run's: a status that says RUNNING
while it reads a DONE run looked like the run's state. So it reads, then says
nothing; the run's state is in the output.

Leaving it (Esc) stops a command that still runs, without a question (it only
reads: nothing is lost); S stops it and stays. Nothing of it stays behind the
menu. With refresh, R runs the command again once it ended. No Framework
imports belong here (see _test_run.py).
"""
from ._operation_screen import ScreenModel, follow
from ..Operations._operations import DONE, RUNNING

__all__ = ["CommandOutput", "follow_command"]


# =============================================================================
# ================================= CONSTANTS =================================


READING = {"status": ("READING STATUS", "Reading the run status..."),  # command: (state line, empty Output view)
           "plan": ("READING PLAN", "Reading the plan...")}


# =============================================================================
# ================================== MODEL ====================================


class CommandOutput(ScreenModel):
    """A command's output and nothing else. command: its words on the state line (`taufw.py status`); name: the
    command (status, plan), for the state while it reads (READING)."""

    output_title = "Output"
    stopping = "Stopping..."
    leave_stops = True

    def __init__(self, command, refresh=False, name=""):
        super().__init__()
        self.command = command
        self.name = name
        reading, self.empty = READING.get(name, ("RUNNING", self.empty))
        self.states = dict(ScreenModel.states, **{RUNNING: (reading, "accent"), DONE: ("", "good")})
        self.returncode = None
        if refresh:
            self.actions = (("R", "Refresh", "refresh"),)

    def finish(self, returncode, lost=False, state=None):
        self.returncode = returncode
        if self.name == "status":
            self.empty = "No status output."

    def summary(self):
        return self.command + (" (exit %s)" % self.returncode if self.returncode not in (None, 0) else "")

    def loading(self, state):
        return self.name == "status" and state == RUNNING


# =============================================================================
# ================================== SCREEN ===================================


def follow_command(ui, screen, title, process, refresh=False):
    """Draw the command's output until the user leaves (a command that still runs is stopped then).
    Return "refresh" (R once it ended, with refresh) or "back"."""
    name = process.data.get("command", "")
    model = CommandOutput("taufw.py %s" % name, refresh, name)
    follow(ui, screen, title, process, model)
    return model.answer or "back"
