# Author: Izaak Neutelings (April 2020)
"""Build the command line of a worker (picojob.py / skimjob.py) for one job or one local run.

Every place that starts a worker builds its command here: `pico.py submit/resubmit` writes one line per job
chunk into the job list, and `pico.py run` executes one line per sample. Both use the same option model
(WorkerOptions) and differ only in the formatter:

  job_command(opts)   batch job: --copydir to storage, -t without quotes, '-i FILES' always last
  run_command(opts)   local run: -o to a local directory, quoted -t, '-i FILES' before -p/--opt

The two flag orders are kept exactly as they were, because job lists and the `run` "Executing:" line are part
of the BBB baselines (pico.jobs, pico.run).

Inputs:  the configuration's channel table, a channel name, extra module options, and per-job settings.
Outputs: WorkerSpec (which module and processor a channel uses) and command strings.
         Nothing is written; the only filesystem access is the check that the processor file exists.

Public API:
  resolve_worker(config, channel, extraopts, procdir)  channel -> WorkerSpec(module, processor, procopts, extrachopts)
  job_command(opts)                                    WorkerOptions -> batch job command line
  run_command(opts)                                    WorkerOptions -> local run command line
  WorkerSpec, WorkerOptions                            records (at the bottom of this file)
"""

# ===== Imports =====
import os
from dataclasses import dataclass
from typing import NamedTuple, Optional, Tuple
from TauFW.common.tools.log import Logger
from TauFW.PicoProducer.analysis.utils import ensuremodule

__all__ = ['resolve_worker', 'job_command', 'run_command', 'WorkerSpec', 'WorkerOptions']


# ===== Constants =====
LOG     = Logger()
PYTHON  = "python3"           # interpreter of the worker
PROCDIR = "python/processors" # processors, relative to PicoProducer/ (the working directory of pico.py)


# ===== Pipeline: channel -> worker -> command line =====

def resolve_worker(config,channel,extraopts,procdir=PROCDIR):
  """Find the module and processor of a channel in the configuration's channel table.
  Skim channels:     "PROCESSOR [--FLAG[=VALUE] ...]"  -> processor with its own options, no module.
  Analysis channels: "MODULE [KEY=VALUE ...]"          -> picojob.py running MODULE; KEY=VALUE pairs are
                                                          appended to the extra module options.
  The processor path is made absolute against the current working directory (PicoProducer/).
  Raises AssertionError for an unknown channel and IOError for a missing processor file."""
  LOG.insist(channel in config.channels,"Channel '%s' not found in the configuration file. Available: %s"%(channel,config.channels))
  module      = config.channels[channel]
  procopts    = "" # extra options for processor
  extrachopts = extraopts[:] # extra options for module (per channel)
  if 'skim' in channel.lower():
    parts     = module.split(' ') # "PROCESSOR [--FLAG[=VALUE] ...]"
    processor = parts[0]
    procopts  = ' '.join(parts[1:])
  else:
    parts     = module.split(' ') # "MODULE [KEY=VALUE ...]"
    processor = "picojob.py"
    module    = parts[0]
    ensuremodule(module) # sanity check
    extrachopts.extend(parts[1:])
  procpath  = os.path.join(procdir,processor)
  if not os.path.isfile(procpath):
    LOG.throw(IOError,"Processor '%s' does not exist in '%s'..."%(processor,procpath))
  processor = os.path.abspath(procpath)
  return WorkerSpec(module,processor,procopts,extrachopts)


def job_command(opts):
  """Command line of one batch job (one line of the job list)."""
  cmd = "%s %s"%(PYTHON,opts.processor)
  if opts.procopts:
    cmd += " %s"%(opts.procopts)
  if opts.skim:
    cmd += " -y %s -d '%s' -t %s --copydir %s"%(opts.era,opts.dtype,opts.filetag,opts.outdir)
    if opts.tmpdir:
      cmd += " -o %s"%(opts.tmpdir) # temporary file for job output before copying
  else:
    cmd += " -y %s -d %r -c %s -M %s --copydir %s -t %s"%(opts.era,opts.dtype,opts.channel,opts.module,opts.outdir,opts.filetag)
  if opts.prefetch:
    cmd += " -p"
  if opts.preselect and opts.skim:
    cmd += " --preselect '%s'"%(opts.preselect)
  if opts.firstevt>=0:
    cmd += " --firstevt %d"%(opts.firstevt) # start at this entry (for event-based splitting)
  if opts.testrun: # override maxevts
    cmd += " -m %d"%(opts.testrun) # process a limited amount of events for test jobs
  elif opts.maxevts>0:
    cmd += " -m %d"%(opts.maxevts) # process a limited amount of events for event-based splitting
  if opts.extraopts:
    cmd += _opt_flag(opts.extraopts)
  cmd += " -i %s"%(' '.join(opts.infiles)) # add last
  return cmd


def run_command(opts):
  """Command line of one local run (`pico.py run`)."""
  cmd = "%s %s"%(PYTHON,opts.processor)
  if opts.procopts:
    cmd += " %s"%(opts.procopts)
  if opts.skim:
    cmd += " -y %s -o %s"%(opts.era,opts.outdir)
    if opts.preselect:
      cmd += " --preselect '%s'"%(opts.preselect)
  else: # analysis
    cmd += " -y %s -c %s -M %s -o %s"%(opts.era,opts.channel,opts.module,opts.outdir)
  if opts.dtype:
    cmd += " -d %r"%(opts.dtype)
  if opts.filetag:
    cmd += " -t %r"%(opts.filetag) # postfix
  if opts.maxevts:
    cmd += " -m %s"%(opts.maxevts)
  if opts.infiles:
    cmd += " -i %s"%(' '.join(opts.infiles))
  if opts.prefetch:
    cmd += " -p"
  if opts.extraopts:
    cmd += _opt_flag(opts.extraopts)
  return cmd


# ===== Records =====

class WorkerSpec(NamedTuple):
  """What a channel runs. Unpacks as (module, processor, procopts, extrachopts)."""
  module:      str  # analysis module (e.g. 'ModuleMuTau'), or the raw channel string for skims
  processor:   str  # absolute path of the worker script
  procopts:    str  # options of the processor itself (skims only)
  extrachopts: list # extra module options: user options, then the channel's KEY=VALUE pairs


@dataclass(frozen=True)
class WorkerOptions:
  """Settings of one worker invocation. Each formatter reads only the fields it uses."""
  processor: str
  era:       str
  outdir:    str                      # job: storage directory (--copydir); run: local output directory (-o)
  skim:      bool          = False
  channel:   Optional[str] = None
  module:    Optional[str] = None
  procopts:  str           = ""
  dtype:     Optional[str] = None
  filetag:   Optional[str] = None
  tmpdir:    Optional[str] = None     # job only: local directory for the output before copying
  prefetch:  bool          = False
  preselect: Optional[str] = None
  firstevt:  int           = -1       # job only: first entry (event-based splitting)
  maxevts:   object        = -1       # job: events per chunk (>0); run: any truthy value is passed as given
  testrun:   int           = 0        # job only: overrides maxevts for test jobs
  extraopts: Tuple[str,...] = ()
  infiles:   Tuple[str,...] = ()

  def __post_init__(self):
    object.__setattr__(self,'extraopts',tuple(self.extraopts or ()))
    object.__setattr__(self,'infiles',tuple(self.infiles or ()))


# ===== Helpers =====

def _opt_flag(extraopts):
  """'--opt' flag with each option single-quoted."""
  return " --opt '%s'"%("' '".join(extraopts))

