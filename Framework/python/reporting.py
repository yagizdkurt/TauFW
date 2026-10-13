#Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
# Author: Yagizhan Dinckurt (October 2026)
"""Where the Framework sends its messages: to the terminal and the run's run.log, or nowhere.

No code in framework.py or stages/ prints. It calls a reporter instead, so the caller decides where the
messages go:

  Reporter                        the interface every reporter provides (header, message, warning, table, ...)
  FrameworkReporter(cli, files)   prints to the terminal (TauFW.Utilities CLI) and, once attach_log() names a
                                  file, also writes a plain-text copy to run.log
  SilentReporter()                prints nothing and keeps the messages in .messages (for tests and library use)

pico_reporter(stage) wraps a reporter so that PicoProducer can use it. PicoProducer's messages then go to the same
terminal and run.log, tagged with the stage name.

Public API:
  Reporter, SilentReporter, FrameworkReporter
"""
import re
from TauFW.Framework.defaults import default_file_io

__all__ = ['Reporter', 'SilentReporter', 'FrameworkReporter']


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

    # =========================================================================
    # ================================ HELPERS ================================

    def _record(self, kind, text):
        self.messages.append((kind, text))

    def __init__(self):
        self.messages = []


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
