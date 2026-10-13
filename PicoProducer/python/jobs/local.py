# Author: Izaak Neutelings (April 2020)
"""Local runs: run a channel's worker (picojob.py/skimjob.py) on a few input files, for quick checks and tests.

  iter_local_runs()     for each era, channel and sample: select the samples (or take the user's input files),
                        take their first files, build the worker command, and yield one LocalRun
     -> execute_run()   print the command and run it (unless dry)

Planning writes nothing: no job directories, no job configs. The worker writes its output to request.outdir.

Inputs:  the configuration, a JobRequest (eras, channels, sample selection, outdir, infiles, nfiles, nsamples,
         maxevts, extraopts, prefetch, preselect, dasfiles), a reporter.
Outputs: LocalRun per sample (or one per channel for user input files); the worker's output files.

Public API:
  iter_local_runs(config, request, reporter)   -> iterator of LocalRun
  execute_run(run, reporter, dryrun)           print and execute the worker command -> exit code
  LocalRun                                     record (at the bottom of this file)
"""

# ===== Imports =====
import subprocess
from dataclasses import dataclass
from typing import Optional
from TauFW.common.tools.log import Logger, bold
from TauFW.PicoProducer.datasets.catalog import getsamples
from TauFW.PicoProducer.jobs.reporting import Reporter
from TauFW.PicoProducer.jobs.worker_command import resolve_worker, run_command, WorkerOptions

__all__ = ['iter_local_runs', 'execute_run', 'LocalRun']


# ===== Constants =====
LOG = Logger()


# ===== Pipeline =====

def iter_local_runs(config,request,reporter=None):
  """Plan the local runs of every selected sample, one LocalRun at a time.
  With request.infiles, run once per era and channel on those files, without a sample."""
  reporter   = reporter or Reporter()
  tag        = request.tag
  dtypes     = request.dtypes
  filters    = request.samples or [None]
  vetoes     = request.vetoes
  userfiles  = request.infiles
  verbosity  = request.verbosity

  # LOOP over ERAS
  if not request.eras:
    reporter.line(">>> Please specify a valid era (-y).")
  if not request.channels:
    reporter.line(">>> Please specify a valid channel (-c).")
  for era in request.eras:
    moddict = { } # save time by loading samples and get their files only once

    # LOOP over CHANNELS
    for channel in request.channels:
      reporter.header("%s, %s"%(era,channel))

      # MODULE & PROCESSOR
      skim = 'skim' in channel.lower()
      module, processor, procopts, extrachopts = resolve_worker(config,channel,request.extraopts)
      if verbosity>=1:
        reporter.line('-'*80)
        reporter.line(">>> Running %r"%(channel))
        for key, value in (('channel',channel),('module',module),('processor',processor),('procopts',procopts),
                           ('extrachopts',extrachopts),('prefetch',request.prefetch),('preselect',request.preselect)):
          reporter.line(_kv(key,value))
        reporter.line(_ks('filters',filters))
        reporter.line(_ks('vetoes',vetoes))
        reporter.line(_kv('dtypes',dtypes))
        reporter.line(_kv('userfiles',userfiles))
        reporter.line(_kv('outdir',request.outdir))

      # SAMPLES
      samples = _select_samples(config,request,era,channel,filters,moddict,reporter)
      if verbosity>=1:
        reporter.line(_kv('samples',samples))
        reporter.line('-'*80)

      # LOOP over SAMPLES
      for sample in samples:
        if sample:
          reporter.sample(sample.name,sample.paths if verbosity>=1 else ())

        # SETTINGS
        dtype      = None
        extraopts_ = extrachopts[:] # extra options for module (for this channel & sample)
        if sample:
          filetag  = "_%s_%s_%s%s"%(channel,era,sample.name,tag)
          if sample.extraopts:
            extraopts_ = sample.extraopts + extraopts_ # allow overwrite from command line
        else:
          filetag  = "_%s_%s%s"%(channel,era,tag)
        if verbosity>=1:
          reporter.line(_ks('sample',sample))
          reporter.line(_kv('filetag',filetag)) # postfix
          reporter.line(_ks('extraopts',extraopts_))

        # GET FILES
        infiles = [ ]
        if userfiles:
          infiles = userfiles[:]
        elif sample:
          infiles = sample.getfiles(das=request.dasfiles,verb=verbosity)
          dtype   = sample.dtype
          if request.nfiles>0:
            infiles = infiles[:request.nfiles]
          if verbosity==1:
            reporter.line(_kv('dtype',dtype))
            reporter.line(_ks('nfiles',len(infiles)))
            reporter.line(">>> %-12s = [ "%('infiles'))
            for file in infiles:
              reporter.line(">>>   %r"%file)
            reporter.line(">>> ]")

        # COMMAND
        command = run_command(WorkerOptions(processor=processor,procopts=procopts,era=era,skim=skim,
                                            channel=channel,module=module,outdir=request.outdir,
                                            preselect=request.preselect,dtype=dtype,filetag=filetag,
                                            maxevts=request.maxevts,infiles=infiles,prefetch=request.prefetch,
                                            extraopts=extraopts_))

        # YIELD
        yield LocalRun(era=era,channel=channel,sample=sample,command=command)
        reporter.line('')


def execute_run(run,reporter=None,dryrun=False):
  """Print the worker command and run it in a shell (not in a dry run).
  Returns the worker's exit code (0 in a dry run); a failure is reported as a warning."""
  reporter = reporter or Reporter()
  reporter.line(">>> Executing: "+bold(run.command))
  if dryrun:
    return 0
  retcode = subprocess.call(run.command,shell=True) # BUGS P11: was os.system, exit code ignored
  if retcode:
    reporter.warning("Local run failed with exit code %s: %s"%(retcode,run.command))
  return retcode


# ===== Sample selection =====

def _select_samples(config,request,era,channel,filters,moddict,reporter):
  """The samples of one era and channel: one filter at a time, without duplicates, at most nsamples per filter.
  Returns [None] if there are none (or the user gave input files)."""
  verbosity = request.verbosity
  vetoes    = request.vetoes
  dtypes    = request.dtypes
  samples   = [ ]
  for filter in filters:
    filters_ = [filter] if filter else [ ]
    if verbosity>=2:
      reporter.line(">>> Checking filters=%s, vetoes=%s, dtypes=%s..."%(filters_,vetoes,dtypes))
    if not request.infiles and (filters_ or vetoes or dtypes):
      LOG.insist(era in config.eras,"Era '%s' not found in the configuration file. Available: %s"%(era,config.eras))
      samples_ = getsamples(era,channel=channel,tag=request.tag,dtype=dtypes,filter=filters_,veto=vetoes,
                            dasfilter=request.dasfilters,dasveto=request.dasvetoes,moddict=moddict,verb=verbosity)
      for sample in samples_[:]:
        if sample in samples: # avoid duplicates
          samples_.remove(sample)
      if request.nsamples>0: # limit number of samples to maximum nsamples
        samples_ = samples_[:request.nsamples]
      samples.extend(samples_)
  if not samples:
    samples = [None]
    if not request.infiles and (filters_ or vetoes or dtypes):
      reporter.no_samples(dtypes,filters_,vetoes,[channel])
  return samples


# ===== Records =====

@dataclass(frozen=True)
class LocalRun:
  """One local worker run; sample is None when running on the user's input files."""
  era:     str
  channel: str
  sample:  Optional[object]
  command: str


# ===== Helpers =====

def _kv(key,value):
  """Verbose line 'key = repr(value)'."""
  return ">>> %-12s = %r"%(key,value)


def _ks(key,value):
  """Verbose line 'key = str(value)'."""
  return ">>> %-12s = %s"%(key,value)
