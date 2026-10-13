# Author: Izaak Neutelings (April 2020)
"""Build the command line of a worker (picojob.py / skimjob.py) for one job or one local run.

Every place that starts a worker builds its command here: `pico.py submit/resubmit` writes one line per job
chunk into the job list, and `pico.py run` executes one line per sample. Both use the same option model
(WorkerOptions) and differ only in the formatter:

  job_command(opts)   batch job: --copydir to storage, -t without quotes, '-i FILES' always last
  run_command(opts)   local run: -o to a local directory, quoted -t, '-i FILES' before -p/--opt

The two flag orders are kept exactly as they were, because job lists and the `run` "Executing:" line are part
of the BBB baselines (pico.jobs, pico.run).

Module options (KEY=VALUE, passed with --opt) come from three places. The worker applies them in order, so a
later value of the same key wins: channel table < sample (catalog `opts`) < user (`-E`). module_options() builds
that list; a resubmission reuses the options of the previous try (resubmit_options).

Inputs:  the configuration's channel table, a channel name, extra module options, and per-job settings.
Outputs: WorkerSpec (which module and processor a channel uses) and command strings.
         Nothing is written; the only filesystem access is the check that the processor file exists.

Public API:
  resolve_worker(config, channel, extraopts, procdir)  channel -> WorkerSpec(module, processor, procopts, chopts, useropts)
  module_options(worker, sampleopts)                   channel, sample and user options, in precedence order
  resubmit_options(previous, worker)                   options of a resubmission
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

__all__ = ['resolve_worker', 'module_options', 'resubmit_options', 'job_command', 'run_command', 'WorkerSpec', 'WorkerOptions']


# ===== Constants =====
LOG     = Logger()
PYTHON  = "python3"           # interpreter of the worker
PROCDIR = "python/workers"    # workers, relative to PicoProducer/ (the working directory of pico.py)


# ===== Pipeline: channel -> worker -> command line =====

def resolve_worker(config,channel,extraopts,procdir=PROCDIR):
  """Find the module and processor of a channel in the configuration's channel table.
  Skim channels:     "PROCESSOR [--FLAG[=VALUE] ...]"  -> processor with its own options, no module.
  Analysis channels: "MODULE [KEY=VALUE ...]"          -> picojob.py running MODULE; the KEY=VALUE pairs are
                                                          the channel's module options (chopts).
  extraopts are the user's module options (-E).
  The processor path is made absolute against the current working directory (PicoProducer/).
  Raises AssertionError for an unknown channel and IOError for a missing processor file."""
  LOG.insist(channel in config.channels,"Channel '%s' not found in the configuration file. Available: %s"%(channel,config.channels))
  module      = config.channels[channel]
  procopts    = "" # extra options for processor
  chopts      = [ ] # module options of the channel
  if 'skim' in channel.lower():
    parts     = module.split(' ') # "PROCESSOR [--FLAG[=VALUE] ...]"
    processor = parts[0]
    procopts  = ' '.join(parts[1:])
  else:
    parts     = module.split(' ') # "MODULE [KEY=VALUE ...]"
    processor = "picojob.py"
    module    = parts[0]
    ensuremodule(module) # sanity check
    chopts    = parts[1:]
  procpath  = os.path.join(procdir,processor)
  if not os.path.isfile(procpath):
    LOG.throw(IOError,"Processor '%s' does not exist in '%s'..."%(processor,procpath))
  processor = os.path.abspath(procpath)
  return WorkerSpec(module,processor,procopts,chopts,list(extraopts))


def module_options(worker,sampleopts=()):
  """Module options in precedence order (the worker lets a later KEY win): channel < sample < user.
  BUGS P08: the user's options used to come before the channel's, so the channel won."""
  return list(worker.chopts)+list(sampleopts or ())+list(worker.useropts)


def resubmit_options(previous,worker):
  """Module options of a resubmission: those of the previous try (already merged), then any new user options.
  BUGS P09: the merged options were merged again with the channel and user options, so they grew every try."""
  previous = list(previous or ())
  return previous+[o for o in worker.useropts if o not in previous]


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
  if opts.maxevts is not None and opts.maxevts>0: # BUGS P10: was 'if opts.maxevts:', true for the default -1
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
  """What a channel runs. Unpacks as (module, processor, procopts, chopts, useropts)."""
  module:    str  # analysis module (e.g. 'ModuleMuTau'), or the raw channel string for skims
  processor: str  # absolute path of the worker script
  procopts:  str  # options of the processor itself (skims only)
  chopts:    list # module options of the channel table (KEY=VALUE)
  useropts:  list # module options of the user (-E)


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
  maxevts:   Optional[int] = -1       # events per chunk (job) or per file (run); passed only if >0
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

