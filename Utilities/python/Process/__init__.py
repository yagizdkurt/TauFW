"""Public process API: external commands with log files and output checks,
and Python functions run in parallel processes."""

from ._parallel import ParallelProcessor
from ._runner import Command, CommandResult, CommandPlan, RunReport, ProcessRunner

__all__ = ["Command", "CommandResult", "CommandPlan", "RunReport", "ProcessRunner", "ParallelProcessor"]
