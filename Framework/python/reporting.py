# Author: Yagizhan Dinckurt (October 2026)
"""Where the Framework reports: the terminal (TauFW.Utilities CLI) and the run's run.log, or nowhere.

Nothing in framework.py or stages/ prints. They call a reporter:

  FrameworkReporter(cli, files)   terminal + plain-text run.log (once attach_log() names it)
  SilentReporter()                nothing (tests, library callers); keeps the messages in .messages

pico_reporter(stage) adapts a reporter to the PicoProducer reporter interface (header, sample, line, warning,
no_samples, progress), so PicoProducer's messages go to the same terminal and run.log, tagged with the stage.

Public API:
  SilentReporter, FrameworkReporter
"""

# ===== Imports =====
import re

__all__ = ['SilentReporter', 'FrameworkReporter']


# ===== Constants =====
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]") # terminal colors, removed in run.log


# ===== Reporters =====

class SilentReporter(object):
  """Reports nothing; every message is kept in self.messages as (kind, text)."""

  def header(self,title):
    self._record('header',title)

  def message(self,text):
    self._record('message',text)

  def warning(self,text):
    self._record('warning',text)

  def table(self,headers,rows):
    rows = [list(r) for r in rows]
    self._record('table',"%s %s"%(list(headers),rows))
    return rows

  def attach_log(self,path):
    """Also write to this run.log from now on (FrameworkReporter only)."""

  def pico_reporter(self,stage):
    """A PicoProducer reporter that forwards to this reporter, tagged with the stage name."""
    return _PicoAdapter(self,stage)

  # ===== Helpers =====

  def _record(self,kind,text):
    self.messages.append((kind,text))

  def __init__(self):
    self.messages = [ ]


class FrameworkReporter(SilentReporter):
  """Terminal output through TauFW.Utilities.CLI, and a plain-text copy in run.log once attach_log() is called."""

  def header(self,title):
    self.cli.print_header(title)
    self._log("=== %s ==="%(title))

  def message(self,text):
    self.cli.print_message(text)
    self._log(">>> "+text)

  def warning(self,text):
    self.cli.print_warning(text)
    self._log("WARNING: "+text)

  def table(self,headers,rows):
    rows = [list(r) for r in rows]
    self.cli.print_table(headers,rows)
    self._log("\n".join(" | ".join(str(c) for c in row) for row in [list(headers)]+rows))
    return rows

  def attach_log(self,path):
    self.logpath = path

  def raw(self,text):
    """A line as given (PicoProducer's output already carries its '>>> ' prefixes)."""
    self.rawcli.print_message(text)
    self._log(text)

  # ===== Helpers =====

  def _log(self,text):
    if self.logpath:
      self.files.append_text(self.logpath,ANSI.sub("",text)+"\n")

  def __init__(self,cli=None,files=None,verbosity=0):
    super(FrameworkReporter,self).__init__()
    from TauFW.Utilities.CLI import CLI
    from TauFW.Utilities.FIO import FileIO
    self.cli     = cli or CLI(verbosity=verbosity)
    self.rawcli  = CLI(verbosity=verbosity,prefix="")
    self.files   = files or FileIO()
    self.logpath = None


# ===== PicoProducer adapter =====

class _PicoAdapter(object):
  """PicoProducer's reporter interface on top of a Framework reporter."""

  def header(self,title):
    self.reporter.header("[%s] %s"%(self.stage,title))

  def sample(self,name,paths=()):
    for text in (name,)+tuple(paths):
      self._line(">>> %s"%(text))

  def line(self,text=""):
    self._line(text)

  def warning(self,text):
    self.reporter.warning("[%s] %s"%(self.stage,text))

  def no_samples(self,dtype=[],filter=[],veto=[],channel=[],jobdir="",jobcfgs=""):
    self.reporter.warning("[%s] no samples found (dtypes=%s, filters=%s, vetoes=%s, channels=%s)"%(
                          self.stage,list(dtype),list(filter),list(veto),list(channel)))

  def progress(self,*args,**kwargs):
    return _NullBar()

  def _line(self,text):
    if hasattr(self.reporter,'raw'):
      self.reporter.raw(text)
    else:
      self.reporter.message(text)

  def __init__(self,reporter,stage):
    self.reporter = reporter
    self.stage    = stage


class _NullBar(object):
  def count(self,*args,**kwargs):
    pass
