# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Commands that run beside a screen (their events and output followed from
files), and operations that run behind the menu (a supervisor keeps them going
when the screen or the menu is left). Used by the Framework and the menu only."""

from ._events import EVENTS_ENV, EventWriter, EventReader, LogTail
from ._background import BackgroundProcess
from ._operations import Operation, OperationStore, RUNNING, STOPPING, DONE, FAILED, STOPPED, LOST

__all__ = ["EVENTS_ENV", "EventWriter", "EventReader", "LogTail", "BackgroundProcess", "Operation", "OperationStore",
           "RUNNING", "STOPPING", "DONE", "FAILED", "STOPPED", "LOST"]
