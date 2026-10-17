# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Public process API: external commands with log files and output checks,
Python functions run in parallel processes, and commands that run beside a
screen (their events and output followed from files)."""

from ._parallel import ParallelProcessor
from ._runner import Command, CommandResult, CommandPlan, RunReport, ProcessRunner
from ._outdir import output_dir_problems, tuple_pattern_problems
from ._events import EVENTS_ENV, EventWriter, EventReader, LogTail
from ._background import BackgroundProcess

__all__ = ["Command", "CommandResult", "CommandPlan", "RunReport", "ProcessRunner", "ParallelProcessor",
           "output_dir_problems", "tuple_pattern_problems", "EVENTS_ENV", "EventWriter", "EventReader", "LogTail",
           "BackgroundProcess"]
