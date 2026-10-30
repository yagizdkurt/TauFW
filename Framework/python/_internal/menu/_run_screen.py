# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""The screen that follows an advance of a run while taufw.py works behind the menu.

Start and Continue open it (interactive.py starts the advance behind the
menu); the UI preview shows it with made-up runs. The operation runs
`taufw.py advance [--next]` (or `start`); its Framework events
(Framework/python/_internal/runtime/reporting.py) build a RunProgress, the model of the
operation screen (_operation_screen.py):

    operation.data["stages"] ─▶ RunProgress: the stages as run.json had them when the advance started
    process.events ──────────▶ feed() ─▶ Stages list + Details (state, message, commands, next check) + the log
                                         of the focused stage's last command
    process.output ──────────────────▶ Output view (L)
    process.state() + run_state ─────▶ the state line, then the result card once it ended:
                                       complete / waiting for jobs / failed / blocked / stopped / lost

operation.data: run_id, run_dir and stages, [dict(id, type, state, message,
info, [seconds, commands, log])] in recipe order (the Framework supplies them
from run.json as plain data); info: [label, value] pairs of the stage's facts
(its config, inputs, output, ...), shown in a box next to the list (the
Framework chooses them per stage type; the preview makes them up). seconds,
commands ([dict(label, seconds, status, log)]) and log: how long a finished or
failed stage took in the earlier advances, shown as they were until the stage
takes a step again (a retry starts its time anew). The events it reads:

  run          run_id, run_dir                    stage_step  stage, type, state (before the step)
  stage_state  stage, state, message              run_state   run_id, state
  progress     stage, index, total, label, status (run, ok, failed), [seconds], [log]
  wait         seconds                            warning     text            error  message

The `log` of a progress event is the path of the command's log file (the
runner's, set before the command starts). The model lives in the Menu, not in the Framework: it reads
only events, so the Menu imports no Framework module.
"""
import time

from ._menu import _clock
from ._operation_screen import ScreenModel, follow, summary_model
from ..operations._operations import DONE, FAILED, LOST, RUNNING, STOPPED, STOPPING

__all__ = ["RunProgress", "follow_run", "run_summary"]


# =============================================================================
# ================================= CONSTANTS =================================


MESSAGES = 50         # warnings and errors kept
JOBS = ("SUBMITTED", "WAITING")
MARKERS = {"NEW": "[    ]", "RUN": "[ RUN]", "SUBMITTED": "[JOBS]", "WAITING": "[JOBS]", "MERGING": "[MRGE]",
           "DONE": "[DONE]", "FAILED": "[FAIL]", "NOT_IMPLEMENTED": "[ N/A]", "STOP": "[STOP]"}
ROLES = {"RUN": "accent", "SUBMITTED": "waiting", "WAITING": "waiting", "MERGING": "accent", "DONE": "good",
         "FAILED": "error", "NOT_IMPLEMENTED": "warning", "STOP": "warning"}
COMMANDS = {"run": "[ RUN]", "ok": "[ ok ]", "failed": "[FAIL]"}
ENDED = {"DONE": ("COMPLETE", "good"), "WAITING": ("WAITING FOR JOBS", "waiting"), "FAILED": ("FAILED", "error"),
         "BLOCKED": ("BLOCKED", "warning"), "PAUSED": ("PAUSED", "waiting")}
LOST_TEXT = ("The advance gave no sign of life for minutes: its login session ended or its machine restarted.")


# =============================================================================
# ================================ RUN PROGRESS ===============================


class RunProgress(ScreenModel):
    """What the screen knows about a run while it advances, from its events (see the module docstring). stages:
    id -> dict(id, type, state, message, started, seconds, commands, log, info, earlier) in recipe order; state is a
    run.json stage state, RUN while a step works, STOP once the advance stopped during it; commands: index ->
    dict(index, total, label, status, started, seconds, log); earlier: seconds and commands are those of the earlier
    advances (from operation.data)."""

    list_title = "Stages"
    item = "Stage"
    output_title = "Output of taufw.py"
    stop_question = "Stop the advance? A job submission in progress is finished first."
    stopping = "Stopping the advance (a job submission in progress is finished first)..."
    kill_warning = ("taufw.py ends at once: a job submission in progress may be left half done. Check condor_q, "
                    "then Continue the run.")

    def feed(self, events):
        for event in events:
            handler = getattr(self, "_on_" + event["kind"], None)
            if handler:
                handler(event)

    def finish(self, returncode, lost=False, state=None):
        """The advance ended (state: the operation's state): a step still at work stopped with it."""
        self.ended = state or (LOST if lost else DONE if returncode == 0 else FAILED)
        self.returncode = returncode
        self.finished = self.last
        for stage in self.stages.values():
            if stage["state"] == "RUN":
                stage["state"] = "STOP"
            for item in [stage] + list(stage["commands"].values()):
                if item["started"]:  # at work until the last sign of life (unknown: no time)
                    if self.last and self.last > item["started"]:
                        item["seconds"] = (item["seconds"] or 0.0) + self.last - item["started"]
                    item["started"] = None
            for command in stage["commands"].values():
                if command["status"] == "run":
                    command["status"] = "stopped"

    @property
    def states(self):
        """The state line: an advance that ended says what became of the run (run_state)."""
        ended = ENDED.get(self.run_state, ("ENDED", "good"))
        return {RUNNING: ("RUNNING", "accent"), STOPPING: ("STOPPING", "warning"), DONE: ended,
                FAILED: ("FAILED", "error"), STOPPED: ("STOPPED", "warning"), LOST: ("LOST", "warning")}

    # =========================================================================
    # ============================ SCREEN MODEL ===============================

    def items(self):
        return list(self.stages.values())

    def label(self, stage):
        return stage["id"]

    def row(self, stage):
        width = max(len(name) for name in self.stages)
        text = "%s %s  %s" % (MARKERS.get(stage["state"], "[    ]"), stage["id"].ljust(width), self._state_text(stage))
        return text, _time(stage, "started", "seconds"), ROLES.get(stage["state"])

    def details(self, stage):
        lines = [] if stage["info"] else ["Type: %s" % stage["type"]]  # else the first fact of info()
        lines.append("State: %s" % self._state_text(stage, long=True))
        if stage["earlier"]:
            lines.append("Took %s in an earlier advance." % _time(stage, "started", "seconds"))
        if stage["message"]:
            lines.append("Message: %s" % stage["message"])
        if stage["state"] in JOBS and self.next_check and self.ended is None:
            lines.append("Next check in %s (every %s)." % (_clock(self.next_check - time.time()),
                                                           _seconds(self.poll)))
        if stage["commands"]:
            lines.append("Commands:")
            for command in stage["commands"].values():
                lines.append("  %s %d/%d %s  %s" % (COMMANDS.get(command["status"], "[STOP]"), command["index"],
                                                    command["total"], command["label"],
                                                    _time(command, "started", "seconds")))
        return lines

    def log(self, stage):
        return stage["log"]

    def info(self, stage):
        return ("Info: %s" % stage["id"], [("Type", stage["type"])] + stage["info"]) if stage["info"] else None

    def summary(self):
        done = sum(stage["state"] == "DONE" for stage in self.stages.values())
        stage = self._working()
        if stage is not None and stage["state"] == "RUN":
            index = list(self.stages).index(stage["id"]) + 1
            command = _running(stage)
            return "stage %d/%d %s%s" % (index, len(self.stages), stage["id"],
                                         " | %d/%d %s" % (command["index"], command["total"], command["label"])
                                         if _several(command) else "")
        if self.next_check and self.ended is None:
            return "waiting for jobs | next check in %s" % _clock(self.next_check - time.time())
        return "%d/%d stages done" % (done, len(self.stages))

    def current(self):
        stage = self._working()
        return None if stage is None else list(self.stages).index(stage["id"])

    def card(self):
        """The result card once the advance ended."""
        if self.ended is None:
            return None
        where = ("Run dir: %s" % self.run_dir, None) if self.run_dir else ("Run: %s" % self.run_id, None)
        stage = self._working()
        name = stage["id"] if stage else ""
        kept = "Finished stages and submitted jobs are kept" if self._jobs() else "Finished stages are kept"
        if self.ended == LOST:
            return "Lost", [(LOST_TEXT, "warning"),
                            ("%s; Continue resumes the run (after taking over its run lock)." % kept, None), where]
        if self.ended == STOPPED:
            done = [command for command in (stage["commands"].values() if stage else ()) if command["status"] == "ok"]
            during = ("Stopped during %s (%d/%d commands finished)." % (name, len(done), _total(stage))
                      if stage and stage["commands"] else "Stopped during %s." % name if stage else "Stopped.")
            return "Stopped", [(during, "warning"),
                               ("%s. Continue resumes from %s." % (kept, name)
                                if stage else "Continue resumes the run.", None), where]
        if self.run_state == "DONE":
            return "Run complete", [("All %d stages done.   started %s, finished %s" % (
                len(self.stages), _hour(self.started), _hour(self.finished)), "good"), where]
        if self.run_state == "WAITING":
            return "Waiting for jobs", [("Stage %s: %s" % (name, stage["message"] or "jobs are running"), "waiting"),
                                        ("Nothing more to do now: Continue later, or Advance to the end to follow it.",
                                         None), where]
        if self.run_state == "BLOCKED":
            return "Blocked at %s" % name, [("Stage %s is not implemented yet." % name, "warning"), where]
        if self.run_state == "PAUSED" and stage is not None and stage["message"].startswith("not ready"):
            return "Not ready at %s" % name, [(stage["message"], "warning"),
                                              ("Fix it, then Continue: the finished stages are kept.", None), where]
        if self.run_state == "PAUSED":
            last = _last_done(self.stages)
            return "Paused", [("Stopped after %s; %s is next." % (last, name) if last else "%s is next." % name,
                               "waiting"),
                              ("Look at its output, then Continue (Next stage only, or to the end).", None), where]
        if stage is not None and stage["state"] == "FAILED":
            then = ("If its chunks still failed after max_tries, Continue offers Retry %s (more tries); other "
                    "production failures need a new run." % name if stage["type"] == "production" else
                    "Fix the cause, then Continue offers Retry %s: the finished stages are kept." % name)
            return "Failed at %s" % name, [(stage["message"] or "The stage failed.", "error"), (then, None), where]
        return "Failed", [("taufw.py ended with exit code %s; see Output (L)." % self.returncode, "error"), where]

    # =========================================================================
    # ================================= EVENTS ================================

    def _on_run(self, event):
        self.run_id = event.get("run_id", self.run_id)
        self.run_dir = event.get("run_dir", self.run_dir)
        self._seen(event)

    def _on_stage_step(self, event):
        stage = self._stage(event["stage"], event.get("type"))
        if stage["earlier"]:  # a retried stage: its time and commands start again
            stage.update(seconds=None, commands={}, log=None, earlier=False)
        stage.update(state="RUN", started=event.get("t"))
        self.next_check = None
        self._seen(event)

    def _on_stage_state(self, event):
        stage = self._stage(event["stage"])
        if stage["started"] and event.get("t"):
            stage["seconds"] = (stage["seconds"] or 0.0) + event["t"] - stage["started"]
        stage.update(state=event.get("state", "FAILED"), message=event.get("message") or "", started=None)
        self._seen(event)

    def _on_progress(self, event):
        stage = self._stage(event["stage"])
        command = stage["commands"].setdefault(event["index"], dict(index=event["index"], total=event["total"],
                                                                    label=event.get("label", ""), started=None,
                                                                    seconds=None, log=None))
        command.update(status=event.get("status", "run"), log=event.get("log") or command["log"])
        if command["status"] == "run":
            command["started"] = event.get("t")
        else:
            command.update(seconds=event.get("seconds"), started=None)
        stage["log"] = command["log"] or stage["log"]
        self._seen(event)

    def _on_run_state(self, event):
        self.run_state = event.get("state")
        self._seen(event)

    def _on_wait(self, event):
        self.poll = float(event.get("seconds", 0))
        self.next_check = (event.get("t") or time.time()) + self.poll
        self._seen(event)

    def _on_warning(self, event):
        self._message("warning", event.get("text", ""))

    def _on_error(self, event):
        self._message("error", event.get("message", ""))

    # =========================================================================
    # ================================ HELPERS ================================

    def _stage(self, name, kind=None):
        if name not in self.stages:
            self.stages[name] = dict(id=name, type=kind or "", state="NEW", message="", started=None, seconds=None,
                                     commands={}, log=None, info=[], earlier=False)
        elif kind:
            self.stages[name]["type"] = kind
        return self.stages[name]

    def _jobs(self):
        """Whether the run has a stage that submits batch jobs (production)."""
        return any(stage["type"] == "production" for stage in self.stages.values())

    def _working(self):
        """The stage the advance works on, waits for, failed or stopped at: the first that is not DONE."""
        for stage in self.stages.values():
            if stage["state"] != "DONE":
                return stage
        return None

    def _state_text(self, stage, long=False):
        if stage["state"] == "RUN":
            command = _running(stage)
            text = "running" + (" %d/%d %s" % (command["index"], command["total"], command["label"])
                                if _several(command) else "")
            return "%s for %s" % (text, _time(stage, "started", "seconds")) if long else text
        if stage["state"] == "STOP":
            return "stopped with the advance"
        return stage["state"]

    def _seen(self, event):
        if event.get("t"):
            self.started = self.started or event["t"]
            self.last = event["t"]

    def _message(self, role, text):
        self.messages.append((role, text))
        del self.messages[:-MESSAGES]

    # =========================================================================
    # ============================= CONSTRUCTION ==============================

    def __init__(self, data=None):
        """data: operation.data (run_id, run_dir, stages; see the module docstring)."""
        super().__init__()
        data = data or {}
        self.run_id = data.get("run_id", "")
        self.run_dir = data.get("run_dir", "")
        self.stages = {}
        for stage in data.get("stages", ()):
            commands = stage.get("commands") or ()
            self._stage(stage["id"], stage.get("type")).update(
                state=stage.get("state") or "NEW", message=stage.get("message") or "",
                info=[tuple(fact) for fact in stage.get("info", ())], seconds=stage.get("seconds"),
                earlier=stage.get("seconds") is not None, log=stage.get("log"),
                commands={index: dict(index=index, total=len(commands), label=command.get("label", ""),
                                      status=command.get("status", "ok"), started=None,
                                      seconds=command.get("seconds"), log=command.get("log"))
                          for index, command in enumerate(commands, 1)})
        self.run_state = None
        self.next_check = None
        self.poll = 0.0
        self.started = None
        self.last = None
        self.finished = None
        self.ended = None
        self.returncode = None


# =============================================================================
# ================================== SCREEN ===================================


def follow_run(ui, screen, title, process):
    """Draw the advance until the user leaves; it goes on behind the menu.
    Return its exit code, None while it runs (or once it was lost)."""
    return follow(ui, screen, title, process, RunProgress(process.data))


def run_summary(operation, kept=None):
    """(text, role) of an advance for the menus: "3/5 plots, 5/7 commands" (the commands only when the stage runs
    several), "1/5 ntuples, waiting for jobs", "Stopping",
    "Done", "Waiting for jobs", "Blocked at fit", "Failed at plots", "Stopped at plots", "Lost - Continue to
    resume"; role: a style name of ConsoleUI. kept: see
    summary_model (the menus keep one per operation: only the new events are read)."""
    state = operation.state()
    run = summary_model(operation, state, lambda: RunProgress(operation.data), kept)
    stage = run._working()
    name = stage["id"] if stage else ""
    if state == RUNNING:
        if stage is None:
            return "Running", "waiting"
        position = "%d/%d %s" % (list(run.stages).index(name) + 1, len(run.stages), name)
        command = _running(stage)
        if _several(command):
            return "%s, %d/%d commands" % (position, command["index"], command["total"]), "waiting"
        return position + (", waiting for jobs" if stage["state"] in JOBS else ""), "waiting"
    if state == STOPPING:
        return "Stopping", "warning"
    if state == LOST:
        return "Lost - Continue to resume", "error"
    if state == STOPPED:
        return ("Stopped at %s" % name if stage else "Stopped"), "warning"
    if state == DONE and run.run_state == "WAITING":
        return "Waiting for jobs", "waiting"
    if state == DONE and run.run_state == "BLOCKED":
        return "Blocked at %s" % name, "warning"
    if state == DONE and run.run_state == "PAUSED":
        return ("Paused at %s" % name if stage else "Paused"), "waiting"
    if state == DONE:
        return "Done", "good"
    return ("Failed at %s" % name if stage and stage["state"] == "FAILED" else "Failed"), "error"


# =============================================================================
# ================================ HELPERS ====================================


def _last_done(stages):
    """The id of the last DONE stage before the first one that is not DONE, or None."""
    last = None
    for stage in stages.values():
        if stage["state"] != "DONE":
            break
        last = stage["id"]
    return last


def _running(stage):
    running = [command for command in stage["commands"].values() if command["status"] == "run"]
    return running[-1] if running else None


def _several(command):
    """A running command of a stage that runs more than one: worth counting."""
    return command is not None and command["total"] > 1


def _total(stage):
    return max([command["total"] for command in stage["commands"].values()] or [0])


def _time(item, started, seconds):
    if item.get(started):
        return _clock(time.time() - item[started])
    if item.get(seconds) is not None:
        return "%.1fs" % item[seconds] if item[seconds] < 60 else _clock(item[seconds])
    return ""


def _seconds(value):
    return "%d s" % value if value < 120 else "%d min" % (value // 60)


def _hour(t):
    return time.strftime("%H:%M", time.localtime(t)) if t else "-"
