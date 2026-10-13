# Author: Yagizhan Dinckurt (October 2026)
"""Where the job lifecycle reports progress: the console (pico.py) or nowhere (library callers).

The job functions in jobs/ never print directly. They call a reporter, which the caller chooses:

  ConsoleReporter()   pico.py: the exact output pico.py always had (header, sample names, warnings, ...)
  Reporter()          silent: every method does nothing; progress bars are inert

Inputs:  messages from the job functions.
Outputs: terminal output (ConsoleReporter only).

Messages printed by lower-level code (sample catalogs, storage listing, event counting) still go to the terminal
directly; they are not routed through the reporter yet.

Public API:
  Reporter           silent base class; defines the reporter interface
  ConsoleReporter    prints like pico.py always did
"""

# ===== Imports =====
from TauFW.common.tools.log import Logger, bold
from TauFW.common.tools.LoadingBar import LoadingBar
from TauFW.PicoProducer.datasets.catalog import print_no_samples

__all__ = ['Reporter', 'ConsoleReporter']


# ===== Reporters =====

class Reporter(object):
  """Silent reporter. Subclasses override the methods they want to show."""

  def header(self,title):
    """Section title, e.g. 'era, channel'."""

  def sample(self,name,paths=()):
    """A sample being processed: its name, then each of the given (DAS) paths."""

  def line(self,text=""):
    """One line of text, printed as given ('' gives an empty line)."""

  def warning(self,text):
    """A warning; the caller continues."""

  def no_samples(self,dtype=[],filter=[],veto=[],channel=[],jobdir="",jobcfgs=""):
    """Explain why no samples were selected."""

  def progress(self,*args,**kwargs):
    """A progress bar with LoadingBar's arguments. Returns an object with count()."""
    return _NullBar()


class ConsoleReporter(Reporter):
  """Prints to the terminal, byte for byte as pico.py did before the jobs/ split."""

  def header(self,title):
    self.log.header(title)

  def sample(self,name,paths=()):
    print(">>> %s"%(bold(name)))
    for path in paths:
      print(">>> %s"%(bold(path)))

  def line(self,text=""):
    print(text)

  def warning(self,text):
    self.log.warn(text)

  def no_samples(self,dtype=[],filter=[],veto=[],channel=[],jobdir="",jobcfgs=""):
    print_no_samples(dtype,filter,veto,channel,jobdir,jobcfgs)

  def progress(self,*args,**kwargs):
    return LoadingBar(*args,**kwargs)

  # ===== Construction =====

  def __init__(self,log=None):
    self.log = log or Logger()


# ===== Helpers =====

class _NullBar(object):
  """Progress bar that shows nothing."""
  def count(self,*args,**kwargs):
    pass

