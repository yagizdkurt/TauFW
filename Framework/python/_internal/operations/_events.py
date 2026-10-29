# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Events and output of a command that runs beside a screen, read from files.

A command started by BackgroundProcess writes two files that the screen
(another process) follows while the command runs:

    command                                    screen
    EventWriter.emit(kind, **fields) ─▶ events file ─▶ EventReader.read() -> new events
    stdout / stderr (ROOT included) ──▶ output log  ─▶ LogTail.read()     -> new lines

An event is one JSON object per line: {"t": <unix time>, "kind": <name>, ...}.
The kinds belong to the command that writes them (Tests/run.py: suite,
case_start, case_end, summary, warning, error); a reader returns every kind,
so a newer command never breaks an older screen. The command learns the path
of its events file from $TAUFW_EVENTS (EVENTS_ENV); without it nothing is
written.

The writer opens, appends and closes the file for every event: AFS shows a
change to other machines only after the file is closed. Both readers continue
where they stopped, keep an unfinished last line for the next read, read at
most READ_LIMIT bytes per call (a burst of output cannot stall the screen) and
start again from the top when the file was truncated.
"""
import codecs
import json
import os
import re
import time
from collections import deque
from typing import List, Optional

__all__ = ["EVENTS_ENV", "EventWriter", "EventReader", "LogTail"]


# =============================================================================
# ================================= CONSTANTS =================================


EVENTS_ENV = "TAUFW_EVENTS"   # the environment variable naming the events file
READ_LIMIT = 1 << 20          # bytes read per call at most
LINE_LIMIT = 1 << 16          # characters of a line without an end kept at most
NEWLINE = re.compile(r"\r\n|\r|\n")


# =============================================================================
# ================================== WRITER ===================================


class EventWriter:
    """Appends events to a file; with path None it writes nothing. A failed
    write is ignored: events never stop the command that reports them."""

    def emit(self, kind: str, **fields) -> None:
        if not self.path:
            return
        event = dict(fields, t=time.time(), kind=kind)
        try:
            with open(self.path, "a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, default=str) + "\n")
        except OSError:
            pass

    # =========================================================================
    # ============================= CONSTRUCTION ==============================

    @classmethod
    def from_environment(cls, environ=None) -> "EventWriter":
        """The writer of the file named by $TAUFW_EVENTS (none: writes nothing)."""
        return cls((os.environ if environ is None else environ).get(EVENTS_ENV) or None)

    def __init__(self, path: Optional[str]) -> None:
        self.path = path

    def __repr__(self) -> str:
        return "<EventWriter %s>" % (self.path,)


# =============================================================================
# ================================== READERS ==================================


class _Follower:
    """Reads what was added to a file since the last call."""

    def _new_bytes(self) -> bytes:
        """The bytes added since the last call; b"" if there are none or the
        file does not exist (yet). A file shorter than before was truncated:
        reset() and read it from the top."""
        try:
            with open(self.path, "rb") as stream:
                stream.seek(0, os.SEEK_END)
                if stream.tell() < self.offset:
                    self.reset()
                stream.seek(self.offset)
                data = stream.read(READ_LIMIT)
        except OSError:
            return b""
        self.offset += len(data)
        return data

    def reset(self) -> None:
        self.offset = 0

    def __init__(self, path: str) -> None:
        self.path = path
        self.offset = 0

    def __repr__(self) -> str:
        return "<%s %s>" % (type(self).__name__, self.path)


class EventReader(_Follower):
    """Follows an events file; read() returns the events (dicts) added since
    the last call. A line that is not a JSON object with a "kind" is skipped."""

    def read(self) -> List[dict]:
        self.pending += self._new_bytes()
        *lines, self.pending = self.pending.split(b"\n")
        events = []
        for line in lines:
            try:
                event = json.loads(line.decode("utf-8", "replace"))
            except ValueError:
                continue
            if isinstance(event, dict) and isinstance(event.get("kind"), str):
                events.append(event)
        return events

    def reset(self) -> None:
        super().reset()
        self.pending = b""

    def __init__(self, path: str) -> None:
        super().__init__(path)
        self.pending = b""


class LogTail(_Follower):
    """Follows a text log and keeps its last `maxlines` lines in .lines.
    read() returns the lines finished since the last call; .partial is the
    line still being written (e.g. a progress bar redrawn with \\r)."""

    def read(self) -> List[str]:
        text = self.partial + self.decoder.decode(self._new_bytes())
        held = ""
        if text.endswith("\r"):  # may be the first half of \r\n
            text, held = text[:-1], "\r"
        *lines, partial = NEWLINE.split(text)
        if len(partial) > LINE_LIMIT:
            lines.append(partial)
            partial = ""
        self.partial = partial + held
        self.lines.extend(lines)
        return lines

    def reset(self) -> None:
        super().reset()
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self.partial = ""
        self.lines.clear()

    def __init__(self, path: str, maxlines: int = 2000) -> None:
        self.lines = deque(maxlen=maxlines)
        super().__init__(path)
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self.partial = ""
