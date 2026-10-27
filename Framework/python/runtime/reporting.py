# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Where the Framework sends its messages: to the terminal and the run's run.log, or nowhere.

No code in framework.py or stages/ prints. It calls a reporter instead, so the caller decides where the
messages go:

  Reporter                        the interface every reporter provides (header, message, warning, table, ...)
  FrameworkReporter(cli, files)   prints to the terminal (TauFW.Utilities CLI) and, once attach_log() names a
                                  file, also writes a plain-text copy to run.log
  SilentReporter()                prints nothing and keeps the messages in .messages (for tests and library use)
  EventReporter(reporter, writer) passes everything on to `reporter` unchanged, and also writes it as events
                                  (TauFW.Utilities.Process.EventWriter) for the menu's screens

pico_reporter(stage) wraps a reporter so that PicoProducer can use it. PicoProducer's messages then go to the same
terminal and run.log, tagged with the stage name.

Besides the messages, the Framework reports what it does as events: reporter.event(kind, **fields). Only an
EventReporter writes them; the other reporters ignore them (SilentReporter keeps them in .events), so the terminal
output never changes. The kinds (the menu follows a command started beside its screen through them):

  run         run_id, run_dir                     advance() starts on this run
  stage_step  stage, type, state                  one step of a stage starts (its state before the step)
  stage_state stage, state, message               the stage's state after the step
  progress    stage, index, total, label, status  a local command starts (status "run") or ends ("ok"/"failed",
              [seconds]                           with seconds)
  run_state   run_id, state                       the run's state after advancing
  wait        seconds                             advance(wait=True) sleeps before the next check
  error       message                             taufw.py stops on a recipe or run directory problem
An EventReporter also writes header, message and warning (text) and table (headers, rows) events.

Public API:
  Reporter, SilentReporter, FrameworkReporter, EventReporter
"""
import re
from TauFW.Framework.defaults import default_file_io

__all__ = ['Reporter', 'SilentReporter', 'FrameworkReporter', 'EventReporter']


# =============================================================================
# ================================= CONSTANTS =================================


ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")  # terminal color codes, removed in run.log


# =============================================================================
# ================================= REPORTERS =================================


class Reporter:
    """The interface of a reporter. Subclasses implement header, message, warning and table."""

    def header(self, title):
        """A section title."""
        raise NotImplementedError

    def message(self, text):
        """A normal message."""
        raise NotImplementedError

    def warning(self, text):
        """A warning or an error."""
        raise NotImplementedError

    def table(self, headers, rows):
        """A table; returns the rows as lists."""
        raise NotImplementedError

    def raw(self, text):
        """A line that is already formatted (PicoProducer's output carries its own '>>> ' prefixes).
        By default it is reported as a normal message."""
        self.message(text)

    def attach_log(self, path):
        """From now on, also write the messages to this run.log. By default there is no log file."""

    def event(self, kind, **fields):
        """What the Framework does, for a screen (see the kinds above). By default it is ignored."""

    def pico_reporter(self, stage):
        """A PicoProducer reporter that forwards to this reporter, tagged with the stage name."""
        return _PicoAdapter(self, stage)


class SilentReporter(Reporter):
    """Reports nothing; every message is kept in self.messages as (kind, text)."""

    def header(self, title):
        self._record('header', title)

    def message(self, text):
        self._record('message', text)

    def warning(self, text):
        self._record('warning', text)

    def table(self, headers, rows):
        rows = [list(r) for r in rows]
        self._record('table', "%s %s" % (list(headers), rows))
        return rows

    def event(self, kind, **fields):
        self.events.append((kind, fields))

    # =========================================================================
    # ================================ HELPERS ================================

    def _record(self, kind, text):
        self.messages.append((kind, text))

    def __init__(self):
        self.messages = []
        self.events = []  # (kind, fields)


class FrameworkReporter(Reporter):
    """Prints to the terminal through TauFW.Utilities.CLI, and writes a plain-text copy to run.log once
    attach_log() is called."""

    def header(self, title):
        self.cli.print_header(title)
        self._log("=== %s ===" % (title))

    def message(self, text):
        self.cli.print_message(text)
        self._log(">>> " + text)

    def warning(self, text):
        self.cli.print_warning(text)
        self._log("WARNING: " + text)

    def table(self, headers, rows):
        rows = [list(r) for r in rows]
        self.cli.print_table(headers, rows)
        self._log("\n".join(" | ".join(str(c) for c in row) for row in [list(headers)] + rows))
        return rows

    def raw(self, text):
        self.rawcli.print_message(text)
        self._log(text)

    def attach_log(self, path):
        self.logpath = path

    # =========================================================================
    # ================================ HELPERS ================================

    def _log(self, text):
        """Append a line to run.log, without terminal colors (only after attach_log())."""
        if self.logpath:
            self.files.append_text(self.logpath, ANSI.sub("", text) + "\n")

    def __init__(self, cli=None, files=None, verbosity=0):
        from TauFW.Utilities.CLI import CLI
        self.cli = cli or CLI(verbosity=verbosity)
        self.rawcli = CLI(verbosity=verbosity, prefix="")  # prints lines without adding a '>>> ' prefix
        self.files = files or default_file_io()
        self.logpath = None
        self.messages = []  # kept for callers that read .messages; the terminal reporter adds nothing to it


class EventReporter(Reporter):
    """Passes every call on to another reporter (its output does not change), and writes the messages and the
    Framework's events to an events file through writer.emit(kind, **fields) (TauFW.Utilities.Process.EventWriter).
    PicoProducer's own lines (raw) are not events: they stay in the output only."""

    def header(self, title):
        self.reporter.header(title)
        self.writer.emit('header', text=title)

    def message(self, text):
        self.reporter.message(text)
        self.writer.emit('message', text=text)

    def warning(self, text):
        self.reporter.warning(text)
        self.writer.emit('warning', text=text)

    def table(self, headers, rows):
        rows = self.reporter.table(headers, rows)
        self.writer.emit('table', headers=[str(h) for h in headers], rows=[[str(c) for c in row] for row in rows])
        return rows

    def raw(self, text):
        self.reporter.raw(text)

    def attach_log(self, path):
        self.reporter.attach_log(path)

    def event(self, kind, **fields):
        self.reporter.event(kind, **fields)
        self.writer.emit(kind, **fields)

    @property
    def messages(self):
        return self.reporter.messages

    def __init__(self, reporter, writer):
        self.reporter = reporter
        self.writer = writer


# =============================================================================
# =========================== PICOPRODUCER ADAPTER ============================


class _PicoAdapter:
    """PicoProducer's reporter interface (header, sample, line, warning, no_samples, progress) on top of a
    Framework reporter."""

    def header(self, title):
        self.reporter.header("[%s] %s" % (self.stage, title))

    def sample(self, name, paths=()):
        for text in (name,) + tuple(paths):
            self.reporter.raw(">>> %s" % (text))

    def line(self, text=""):
        self.reporter.raw(text)

    def warning(self, text):
        self.reporter.warning("[%s] %s" % (self.stage, text))

    def no_samples(self, dtype=[], filter=[], veto=[], channel=[], jobdir="", jobcfgs=""):
        self.reporter.warning("[%s] no samples found (dtypes=%s, filters=%s, vetoes=%s, channels=%s)" % (
                              self.stage, list(dtype), list(filter), list(veto), list(channel)))

    def progress(self, *args, **kwargs):
        """PicoProducer shows progress bars; the Framework does not, so it gets a bar that does nothing."""
        return _NullBar()

    def __init__(self, reporter, stage):
        self.reporter = reporter
        self.stage = stage


class _NullBar:
    """A progress bar that does nothing."""

    def count(self, *args, **kwargs):
        pass
