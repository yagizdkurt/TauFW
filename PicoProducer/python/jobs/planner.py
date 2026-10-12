# Author: Izaak Neutelings (April 2020)
"""Plan the jobs of one sample: names, directories, settings, chunk numbers and worker command lines.

Everything here is a pure calculation: nothing is read from or written to disk, nothing is printed and nobody is
asked. jobs/pipeline.py does the I/O around it (creating directories, listing files, writing the job list).

Inputs:  the configuration, a JobRequest, a Sample, era/channel, the channel's WorkerSpec, and file chunks.
Outputs: SampleLayout (names, directories and settings of a sample's next (re)submission try),
         chunk numbers and job-list command lines.

Public API:
  sample_layout(config, request, sample, era, channel, extrachopts)   -> SampleLayout
  assign_chunks(fchunks, chunkdict, layout, worker, era, channel, request, tmpdir)
                                                                      -> (chunks, chunkdict, commands)
  cfg_globs(jobdirformat, era, channel, tag, group)                   glob of existing job configs
  SampleLayout                                                        record (at the bottom of this file)
"""

# ===== Imports =====
import os
from dataclasses import dataclass
from typing import Optional
from TauFW.common.tools.log import Logger
from TauFW.common.tools.string import repkey
from TauFW.PicoProducer.jobs.chunking import evtsplitexp
from TauFW.PicoProducer.jobs.worker_command import job_command, WorkerOptions

__all__ = ['sample_layout', 'assign_chunks', 'cfg_globs', 'SampleLayout']


# ===== Constants =====
LOG        = Logger()
CFGPATTERN = "config/jobconfig_$CHANNEL$TAG_try[0-9]*.json" # job configs of all tries, relative to the job dir


# ===== Planning =====

def sample_layout(config,request,sample,era,channel,extrachopts):
  """Names, directories and settings of the next (re)submission try of a sample.
  Precedence for nfilesperjob and maxevts: user (request) > sample > configuration. On resubmission without
  user values, the previous try's values are reused."""
  resubmit      = request.resubmit
  nfilesperjob  = request.nfilesperjob
  maxevts       = request.maxevts
  skim          = 'skim' in channel.lower()
  subtry        = sample.subtry+1 if resubmit else 1
  jobids        = sample.jobcfg.get('jobids',[ ])
  queue         = request.queue or sample.jobcfg.get('queue',None)
  prefetch      = sample.jobcfg.get('prefetch',request.prefetch) or request.prefetch # if resubmit: reuse old setting, or override by user
  postfix       = "_%s%s"%(channel,request.tag)
  jobtag        = "%s_try%d"%(postfix,subtry)
  jobname       = "%s%s_%s%s"%(sample.name,postfix,era,"_try%d"%subtry if subtry>1 else "")
  extraopts     = extrachopts[:] # extra options for module (for this channel & sample)
  if sample.extraopts:
    extraopts   = sample.extraopts + extraopts # allow overwrite from command line
  nfilesperjob_ = nfilesperjob if nfilesperjob>0 else sample.nfilesperjob if sample.nfilesperjob>0 else config.nfilesperjob # priority: USER > SAMPLE > CONFIG
  maxevts_      = maxevts if maxevts!=None else sample.maxevts if sample.maxevts<=0 else config.maxevtsperjob # BUGS P06; priority: USER > SAMPLE > CONFIG
  if request.split_nfpj>1: # divide nfilesperjob by split_nfpj
    nfilesperjob_ = int(max(1,nfilesperjob_/float(request.split_nfpj)))
  elif resubmit and (maxevts==None or maxevts<=0): # reuse previous maxevts settings if maxevts not set by user
    maxevts_    = sample.jobcfg.get('maxevts',maxevts_)
    if nfilesperjob<=0: # reuse previous nfilesperjob settings if nfilesperjob not set by user
      nfilesperjob_ = sample.jobcfg.get('nfilesperjob',nfilesperjob_)
  daspath       = sample.paths[0].strip('/')
  keys          = dict(ERA=era,CHANNEL=channel,TAG=request.tag,SAMPLE=sample.name,DAS=daspath,PATH=daspath,GROUP=sample.group)
  outdir        = repkey(config.nanodir if skim else config.outdir,**keys)
  jobdir        = _expandvars(repkey(config.jobdir,**keys))
  cfgdir        = _expandvars(os.path.join(jobdir,"config"))
  logdir        = _expandvars(os.path.join(jobdir,"log"))
  return SampleLayout(
    subtry=subtry, jobids=jobids, queue=queue, prefetch=prefetch, dtype=sample.dtype,
    postfix=postfix, jobtag=jobtag, jobname=jobname, extraopts=extraopts,
    nfilesperjob=nfilesperjob_, maxevts=maxevts_,
    outdir=outdir, jobdir=jobdir, cfgdir=cfgdir, logdir=logdir,
    cfgname="%s/jobconfig%s.json"%(cfgdir,jobtag),
    joblist='%s/jobarglist%s.txt'%(cfgdir,jobtag),
  )


def assign_chunks(fchunks,chunkdict,layout,worker,era,channel,request,tmpdir):
  """Number the new chunks and build one worker command line per chunk.
  Chunk numbers already used in chunkdict (good chunks of earlier tries) are skipped, so a resubmission can
  use a different number of files per job. Returns (new chunk numbers, updated copy of chunkdict,
  [(chunk number, command line), ...])."""
  skim      = 'skim' in channel.lower()
  chunkdict = dict(chunkdict) # do not modify the caller's dictionary
  chunks    = [ ] # chunk indices
  commands  = [ ]
  ichunk    = 0
  for fchunk in fchunks:
    while ichunk in chunkdict:
      ichunk += 1 # allows for different nfilesperjob on resubmission
    jobfiles, firstevt, maxevts = _chunk_inputs(fchunk)
    filetag  = layout.postfix
    if not skim:
      filetag += "_%d"%(ichunk)
    elif firstevt>=0:
      filetag += "_%d"%(firstevt/maxevts)
    jobcmd = job_command(WorkerOptions(processor=worker.processor,procopts=worker.procopts,era=era,skim=skim,
                                       channel=channel,module=worker.module,dtype=layout.dtype,filetag=filetag,
                                       outdir=layout.outdir,tmpdir=tmpdir,prefetch=layout.prefetch,
                                       preselect=request.preselect,firstevt=firstevt,maxevts=maxevts,
                                       testrun=request.testrun,extraopts=layout.extraopts,infiles=jobfiles))
    commands.append((ichunk,jobcmd))
    chunkdict[ichunk] = fchunk
    chunks.append(ichunk)
  return chunks, chunkdict, commands


def cfg_globs(jobdirformat,era,channel,tag,group=None):
  """Glob patterns of a channel's job directories and of all their job configs (all samples and tries).
  With group=None the $GROUP key is left as it is (as on resubmission); status passes group='*'."""
  keys = dict(ERA=era,SAMPLE='*',CHANNEL=channel,TAG=tag)
  if group is not None:
    keys['GROUP'] = group
  jobdir_ = repkey(jobdirformat,**keys)
  jobcfgs = repkey(os.path.join(jobdir_,CFGPATTERN),**keys)
  return jobdir_, jobcfgs


# ===== Records =====

@dataclass(frozen=True)
class SampleLayout:
  """Names, directories and settings of one (re)submission try of a sample.
  jobids is the sample's own list of earlier job IDs (shared, not copied), as in its job config."""
  subtry:       int            # try number: 1 for the first submission
  jobids:       list           # job IDs of earlier tries
  queue:        Optional[str]
  prefetch:     bool
  dtype:        str
  postfix:      str            # _$CHANNEL$TAG
  jobtag:       str            # _$CHANNEL$TAG_try$N
  jobname:      str
  extraopts:    list           # module options: sample, user (-E), channel
  nfilesperjob: int
  maxevts:      int            # >1: split by events
  outdir:       str            # job output (storage)
  jobdir:       str            # job configs and logs
  cfgdir:       str
  logdir:       str
  cfgname:      str            # job config JSON
  joblist:      str            # job list: one worker command line per chunk


# ===== Helpers =====

def _chunk_inputs(fchunk):
  """Input files, first event and maximum number of events of a chunk.
  An event-split chunk is one 'fname:firstevt:maxevts' entry; otherwise the chunk is a list of whole files."""
  evtmatch = evtsplitexp.match(fchunk[0]) # $fname:$firstevt:$maxevts
  if evtmatch:
    LOG.insist(len(fchunk)==1,"Chunks of event-split files can only have one input file: %s"%(fchunk))
    return [evtmatch.group(1)], int(evtmatch.group(2)), int(evtmatch.group(3))
  return fchunk, -1, -1 # whole files; do not limit number of events


def _expandvars(path):
  """Expand environment variables, as ensuredir does for the directories it creates."""
  return os.path.expandvars(path) if path and '$' in path else path

