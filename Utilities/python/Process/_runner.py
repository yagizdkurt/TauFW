"""Run external commands one after the other, each with its own log file.

A Command names what to run (argv), where (cwd) and which files it must
produce (expects). The runner writes everything the command prints to a log
file and checks afterwards that every expected file exists and was written
by this command (modified after it started). Many existing analysis scripts
ignore the exit codes of the tools they call, so a zero exit code alone is
not trusted.

    commands ─▶ run_all(commands, logdir) ─▶ CommandResult per command
                  │                            (stops at the first failure)
                  └─ run(command, log): header ─▶ process ─▶ footer + output check
"""
import glob
import os
import re
import shlex
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Callable, Iterable, Mapping, Optional, Tuple

__all__ = ["Command", "CommandResult", "CommandPlan", "RunReport", "ProcessRunner"]


# =============================================================================
# ================================= CONSTANTS =================================


FRESHNESS = 2.0   # seconds of clock difference allowed when checking outputs
TIMEOUT_EXIT = -1   # returncode of a command stopped by its timeout
NOT_FOUND_EXIT = 127   # returncode of a command whose program does not exist


# =============================================================================
# ================================= RECORDS ===================================


@dataclass(frozen=True)
class Command:
    """One command: label (short name), argv, working directory, expected
    outputs (glob patterns, relative to cwd), an optional timeout and extra
    environment variables (on top of the runner's)."""
    label: str
    argv: Tuple[str, ...]
    cwd: str
    expects: Tuple[str, ...] = ()
    timeout: Optional[float] = None
    env: Tuple[Tuple[str, str], ...] = ()

    def shell(self) -> str:
        """The command as one line that a shell would accept."""
        return " ".join(shlex.quote(argument) for argument in self.argv)


@dataclass(frozen=True)
class CommandResult:
    """What one command did. ok: exit code 0 and every expected output
    written by this command (missing lists the patterns that were not)."""
    label: str
    argv: Tuple[str, ...]
    cwd: str
    log: str
    returncode: int
    started: float
    seconds: float
    missing: Tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.missing

    def to_dict(self) -> dict:
        data = asdict(self)
        data["argv"] = list(self.argv)
        data["missing"] = list(self.missing)
        data["ok"] = self.ok
        return data


@dataclass(frozen=True)
class CommandPlan:
    """What would run: the commands, all with the same working directory,
    the artifacts they would make, and notes (problems found while planning)."""
    cwd: str
    commands: Tuple[Command, ...]
    artifacts: Tuple[dict, ...] = ()
    notes: Tuple[str, ...] = ()


@dataclass(frozen=True)
class RunReport:
    """What ran: one CommandResult per command that ran (the run stops at
    the first failure), out of `total`, and the artifacts that were made."""
    results: Tuple[CommandResult, ...]
    total: int
    artifacts: Tuple[dict, ...] = ()

    @property
    def ok(self) -> bool:
        return len(self.results) == self.total and all(result.ok for result in self.results)

    @property
    def failed(self) -> Optional[CommandResult]:
        """The CommandResult that stopped the run, or None."""
        return next((result for result in self.results if not result.ok), None)


# =============================================================================
# ================================== RUNNER ===================================


Progress = Callable[[int, int, Command, Optional[CommandResult]], None]


class ProcessRunner:
    """Runs Commands; see the module docstring.

    Pipelines:    run_all(commands, logdir, progress) -> results, stops at the first failure
                  run(command, log)                   -> CommandResult
    Construction: ProcessRunner(execute, clock, env)
    """

    # =========================================================================
    # =============================== PIPELINES ===============================

    def run_all(self, commands: Iterable[Command], logdir: str,
                progress: Optional[Progress] = None) -> Tuple[CommandResult, ...]:
        """Run the commands in order, logging to logdir/NN_<label>.log, and
        stop after the first one that is not ok. progress(index, total,
        command, result) is called before (result None) and after each
        command."""
        commands = tuple(commands)
        os.makedirs(logdir, exist_ok=True)
        results = []
        for index, command in enumerate(commands, 1):
            if progress:
                progress(index, len(commands), command, None)
            log = os.path.join(logdir, "%02d_%s.log" % (index, _safe(command.label)))
            result = self.run(command, log)
            results.append(result)
            if progress:
                progress(index, len(commands), command, result)
            if not result.ok:
                break
        return tuple(results)

    def run(self, command: Command, log: str) -> CommandResult:
        """Run one command; its output (stdout and stderr) goes to `log`."""
        started = self.clock()
        with open(log, "w", encoding="utf-8") as stream:
            stream.write("# %s\n# cwd:     %s\n# command: %s\n# started: %s\n\n"
                         % (command.label, command.cwd, command.shell(), _time(started)))
            stream.flush()
            returncode = self.execute(command.argv, command.cwd, stream, command.timeout,
                                      self._environment(command))
        seconds = self.clock() - started
        missing = self._missing(command, started) if returncode == 0 else ()
        with open(log, "a", encoding="utf-8") as stream:
            stream.write("\n# exit code %s after %.0f s\n" % (returncode, seconds))
            for pattern in missing:
                stream.write("# missing output: %s\n" % pattern)
        return CommandResult(label=command.label, argv=tuple(command.argv), cwd=command.cwd, log=log,
                             returncode=returncode, started=started, seconds=seconds, missing=missing)

    # =========================================================================
    # ================================ HELPERS ================================

    def _missing(self, command: Command, started: float) -> Tuple[str, ...]:
        """The expected outputs that no file written by this command matches."""
        oldest = started - FRESHNESS
        missing = []
        for pattern in command.expects:
            paths = glob.glob(os.path.join(command.cwd, pattern))
            if not any(os.path.getmtime(path) >= oldest for path in paths):
                missing.append(pattern)
        return tuple(missing)

    def _environment(self, command: Command) -> dict:
        environment = dict(os.environ)
        environment.update(self.env)
        environment.update(dict(command.env))
        environment["PYTHONUNBUFFERED"] = "1"   # keep the log in order
        return environment

    # =========================================================================
    # ============================= CONSTRUCTION ==============================

    def __init__(self, execute: Optional[Callable] = None, clock: Callable[[], float] = time.time,
                 env: Optional[Mapping[str, str]] = None) -> None:
        """execute(argv, cwd, stream, timeout, env) -> returncode runs one
        process (tests pass a fake); env: extra environment variables.
        Construction starts nothing and writes nothing."""
        self.execute = execute or _execute
        self.clock = clock
        self.env = dict(env or {})

    def __repr__(self) -> str:
        return "<ProcessRunner>"


# =============================================================================
# ================================ FUNCTIONS ==================================


def _execute(argv, cwd, stream, timeout, env) -> int:
    """Run argv in cwd, writing stdout and stderr to the open file stream."""
    try:
        return subprocess.run(list(argv), cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                              stdin=subprocess.DEVNULL, env=env, timeout=timeout, check=False).returncode
    except subprocess.TimeoutExpired:
        stream.write("\n# stopped: no exit after the timeout of %s s\n" % timeout)
        return TIMEOUT_EXIT
    except FileNotFoundError as error:
        stream.write("\n# cannot start: %s\n" % error)
        return NOT_FOUND_EXIT


def _safe(label: str) -> str:
    """A label as part of a file name."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", label).strip("_") or "command"


def _time(seconds: float) -> str:
    return datetime.fromtimestamp(seconds).strftime("%Y-%m-%d %H:%M:%S")
