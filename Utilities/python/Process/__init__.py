# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Public process API: external commands with log files and output checks,
Python functions run in parallel processes, commands that run beside a screen
(their events and output followed from files), and operations that run behind
the menu (a supervisor keeps them going when the screen or the menu is left)."""

from ._parallel import ParallelProcessor
from ._runner import Command, CommandResult, CommandPlan, RunReport, ProcessRunner
from ._outdir import output_dir_problems, tuple_pattern_problems
from ._events import EVENTS_ENV, EventWriter, EventReader, LogTail
from ._background import BackgroundProcess
from ._operations import Operation, OperationStore, RUNNING, STOPPING, DONE, FAILED, STOPPED, LOST

__all__ = ["Command", "CommandResult", "CommandPlan", "RunReport", "ProcessRunner", "ParallelProcessor",
           "output_dir_problems", "tuple_pattern_problems", "EVENTS_ENV", "EventWriter", "EventReader", "LogTail",
           "BackgroundProcess", "Operation", "OperationStore", "RUNNING", "STOPPING", "DONE", "FAILED", "STOPPED",
           "LOST"]
