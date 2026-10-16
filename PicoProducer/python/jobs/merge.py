# Author: Izaak Neutelings (April 2020)
"""Merge a sample's job output into one pico tuple (hadd), and clean up its job files.

  merge_sample()           the pipeline for one sample (pico.py hadd / haddclean / clean):
    1. target              where the merged tuple goes and which job files belong to the sample (merge_target)
    2. status              check_sample() on the last (re)submission try
    3. gate                merge or clean only if every chunk succeeded, unless forced (merge_gate)
    4. hadd                storage.hadd(job outputs -> <picodir>/<sample>_<channel><tag>.root); picodir is the
                           configuration's, or the one the caller gives (merge_sample(picodir=...))
    5. validate            before cleaning after a merge: the merged tuple must be readable and hold the events
                           of the job output (validated)
    6. clean               remove the job directory, or only this sample's files (cleanup_commands)

merge_target, merge_gate, validated and cleanup_commands are pure: they read no files and change nothing.
merge_sample does the observations (storage, status, globbing) and the actions (hadd, rm) in the same order as
before, so the output of pico.py is unchanged.

Inputs:  a Sample loaded from its job config (getcfgsamples), the configuration, the batch queue (via check_sample).
Outputs: the merged tuple in storage (picodir); removed job directories/files; MergeResult; messages through the
         reporter.

Public API:
  merge_sample(sample, config, action, era, channel, tag, reporter, **options)  -> MergeResult
  TUPLE_LAYOUT                                                                  where the tuples go below a tupledir
  merge_target(sample, picodir, era, channel, tag)                              -> MergeTarget
  merge_gate(status, force)                                                     -> bool
  validated(nevents, status)                                                    -> (ok, reason)
  cleanup_commands(target, count)                                               -> CleanupPlan
  MergeTarget, CleanupPlan, MergeResult                                         records (bottom of this file)
"""

# ===== Imports =====
import os, glob
from dataclasses import dataclass
from typing import Optional, Tuple
from TauFW.common.tools.utils import execute
from TauFW.common.tools.string import repkey, lreplace
from TauFW.PicoProducer.jobs.reporting import Reporter
from TauFW.PicoProducer.jobs.status import check_sample, ChunkStatus
from TauFW.PicoProducer.storage.factory import getstorage
from TauFW.PicoProducer.storage.validation import isvalid

__all__ = ['merge_sample', 'merge_target', 'merge_gate', 'validated', 'cleanup_commands',
           'MergeTarget', 'CleanupPlan', 'MergeResult', 'MERGE_ACTIONS', 'TUPLE_LAYOUT']


# ===== Constants =====
MERGE_ACTIONS = ('hadd', 'haddclean', 'clean') # pico.py subcommands handled here
TUPLE_LAYOUT  = "$ERA/$GROUP" # below a directory the caller gives (JobRequest.tupledir), the merged tuples go to
                              # <tupledir>/<era>/<group>/<sample>_<channel><tag>.root


# ===== Pipeline =====

def merge_sample(sample,config,action,era,channel,tag,reporter=None,clean=False,force=False,haddcmd="",
                 maxopenfiles=0,jobs=None,checkqueue=-1,checkevts=True,checkexpevts=False,das=False,ncores=4,
                 dryrun=False,verb=0,picodir=None):
  """Merge ('hadd'), merge and clean ('haddclean'), or only clean ('clean') a sample's job output.
  clean: also clean after 'hadd' (pico.py hadd -r); force: ignore failed/missing chunks;
  haddcmd/maxopenfiles: hadd command and its -n option; jobs/checkqueue/checkevts/checkexpevts/das/ncores:
  passed to check_sample; dryrun: print the hadd and rm commands without executing them;
  picodir: where the merged tuple goes (with $ERA, $GROUP, ...; None: picodir of the configuration).
  Side effects: creates the storage directory (picodir), runs hadd and rm unless dryrun."""
  assert action in MERGE_ACTIONS, "merge_sample: action must be one of %s, got %r"%(MERGE_ACTIONS,action)
  reporter  = reporter or Reporter()
  verbosity = verb
  cmdverb   = max(1,verbosity)
  hadd      = action in ['hadd','haddclean']
  cleanup   = action=='clean' or (action=='hadd' and clean) or action=='haddclean'

  # 1. TARGET
  target  = merge_target(sample,picodir or config.picodir,era,channel,tag)
  storage = getstorage(target.storedir,ensure=True,haddcmd=haddcmd,verb=verbosity)
  if verbosity>=1:
    _report_target(reporter,action,sample,target)

  # 2. STATUS
  status = check_sample(sample,config,reporter,channel=channel,tag=tag,jobs=jobs,checkqueue=checkqueue,
                        checkevts=checkevts,das=das,checkexpevts=checkexpevts,ncores=ncores,verb=verbosity)

  # 3. GATE: only clean or hadd if all jobs were successful
  if not merge_gate(status,force):
    reporter.warning("Cannot %s job output because %d chunks need to be resubmitted..."%(action,len(status.resubfiles))+
                     " Please use -f or --force to %s anyway.\n"%(action))
    return MergeResult(target=target,status=status,refused=True)

  # 4. HADD
  haddout = None
  if hadd:
    haddout = storage.hadd(target.infiles,target.outfile,dry=dryrun,verb=cmdverb,maxopenfiles=maxopenfiles)
    # TODO: add option to print out cutflow for outfile

  # 5. VALIDATE the merged tuple before removing its inputs
  if hadd and cleanup and not dryrun: # BUGS P19: cleanup was gated only on the exit code of hadd
    ok, reason = validated(isvalid(storage.file(target.outfile)),status)
    if not ok:
      reporter.warning("Not removing the job output of %r: %s"%(sample.name,reason))
      return MergeResult(target=target,status=status,merged=True,haddout=haddout,invalid=reason)

  # 6. CLEAN UP
  rmcmds = ()
  if cleanup:
    plan = cleanup_commands(target,lambda pattern: len(glob.glob(pattern)))
    if verbosity>=2:
      reporter.line(">>> %-12s = %s"%('cfgfiles',target.cfgfiles))
      if not plan.whole:
        reporter.line(">>> %-12s = %s"%('rmfileset',list(target.filesets)))
    rmcmds = plan.commands
    for rmcmd in rmcmds:
      if verbosity>=1:
        rmcmd = lreplace(rmcmd,'rm',"rm -v",1)
      execute(rmcmd,dry=dryrun,verb=cmdverb)

  return MergeResult(target=target,status=status,merged=hadd,haddout=haddout,rmcmds=tuple(rmcmds))


# ===== Decisions (pure) =====

def merge_target(sample,picodir,era,channel,tag):
  """Where the merged tuple goes (picodir with $ERA, $CHANNEL, $TAG, $SAMPLE, $DAS, $GROUP) and the glob patterns
  of the sample's job outputs, job configs and logs (from its job config)."""
  jobcfg   = sample.jobcfg
  postfix  = jobcfg['postfix']
  outdir   = jobcfg['outdir'] # job output directory
  cfgdir   = jobcfg['cfgdir'] # job configuration directory
  logdir   = jobcfg['logdir'] # job log directory
  storedir = repkey(picodir,ERA=era,CHANNEL=channel,TAG=tag,SAMPLE=sample.name,
                            DAS=sample.paths[0].strip('/'),GROUP=sample.group)
  return MergeTarget(
    cfgname  = jobcfg['config'],
    jobdir   = jobcfg['jobdir'],
    cfgdir   = cfgdir,
    logdir   = logdir,
    outdir   = outdir,
    storedir = storedir,
    outfile  = "%s_%s%s.root"%(sample.name,channel,tag),
    infiles  = os.path.join(outdir,"*%s_[0-9]*.root"%(postfix)),
    cfgfiles = os.path.join(cfgdir,"job*%s_try[0-9]*.*"%(postfix)),
    logfiles = os.path.join(logdir,"*%s*.*.log"%(postfix)),
  )


def merge_gate(status,force=False):
  """Merge or clean only if no chunk needs to be resubmitted, unless forced."""
  return status.mergeable or force


def validated(nevents,status):
  """Can the merged tuple replace the job output? nevents is isvalid() of the merged file (cutflow bin 1, or -1 if
  it is missing or corrupt). With event counting (checkevts), it must equal the processed events of the good
  chunks. Returns (ok, reason)."""
  if nevents<0:
    return False, "the merged file is missing or corrupt"
  nproc = status.nprocevents
  if status.checkevts and nproc>0 and abs(nevents-nproc)>1e-6*nproc:
    return False, "the merged file has %s events, the job output %s"%(nevents,nproc)
  return True, ""


def cleanup_commands(target,count):
  """The rm commands that clean up a merged sample. count(pattern) gives the number of files matching a glob.
  If no other job shares the job directory, remove it whole (and the output directory, if separate and not
  shared); otherwise remove only this sample's job outputs, job configs and logs."""
  allcfgs = os.path.join(target.cfgdir,"job*_try[0-9]*.*")
  rmcmds  = [ ]
  if count(allcfgs)<=count(target.cfgfiles): # no other jobs in same directory; BUGS P23: was '>=' (always true)
    rmcmds.append("rm -r %s"%(target.jobdir)) # remove whole job directory
    if target.outdir!=target.jobdir and count(target.infiles)>=count(os.path.join(target.outdir,"*.root")): # check for other jobs in same directory
      rmcmds.append("rm -r %s"%(target.outdir)) # remove whole output directory with ROOT output files
    return CleanupPlan(commands=tuple(rmcmds),whole=True)
  rmfiles = [f for f in target.filesets if count(f)>0] # only remove files related to this job (era/channel/sample)
  if rmfiles:
    rmcmds.append("rm %s"%(' '.join(rmfiles)))
  return CleanupPlan(commands=tuple(rmcmds),whole=False)


# ===== Reporting =====

def _report_target(reporter,action,sample,target):
  reporter.line(">>> %sing job output for '%s'"%(action.capitalize(),sample.name))
  reporter.line(">>> %-12s = %r"%('cfgname',target.cfgname))
  reporter.line(">>> %-12s = %r"%('jobdir',target.jobdir))
  reporter.line(">>> %-12s = %r"%('cfgdir',target.cfgdir))
  reporter.line(">>> %-12s = %r"%('outdir',target.outdir))
  reporter.line(">>> %-12s = %r"%('storedir',target.storedir))
  reporter.line(">>> %-12s = %s"%('infiles',target.infiles))
  if action in ['hadd','haddclean']:
    reporter.line(">>> %-12s = %r"%('outfile',target.outfile))


# ===== Records =====

@dataclass(frozen=True)
class MergeTarget:
  """Paths of one sample's merge: job directories (from its job config), glob patterns of its job files, and the
  merged tuple (outfile, relative to storedir)."""
  cfgname:  str
  jobdir:   str
  cfgdir:   str
  logdir:   str
  outdir:   str
  storedir: str
  outfile:  str
  infiles:  str # job outputs:  <outdir>/*<postfix>_[0-9]*.root
  cfgfiles: str # job configs:  <cfgdir>/job*<postfix>_try[0-9]*.*
  logfiles: str # job logs:     <logdir>/*<postfix>*.*.log

  @property
  def filesets(self):
    """The glob patterns removed when the job directory is shared with other samples."""
    return (self.infiles,self.cfgfiles,self.logfiles)


@dataclass(frozen=True)
class CleanupPlan:
  """rm commands; whole: the whole job (and output) directory is removed, not only this sample's files."""
  commands: Tuple[str, ...]
  whole:    bool


@dataclass(frozen=True)
class MergeResult:
  """Outcome of merge_sample. refused: the gate failed (nothing merged or removed); invalid: why the merged tuple
  failed validation (the job output was kept)."""
  target:  MergeTarget
  status:  ChunkStatus
  refused: bool = False
  invalid: str  = ""
  merged:  bool = False         # hadd ran (or was printed, in a dry run)
  haddout: Optional[str] = None # output of the hadd command
  rmcmds:  Tuple[str, ...] = () # rm commands (before 'rm -v' for verbosity>=1)

  @property
  def outpath(self):
    """The merged tuple: storedir/outfile."""
    return os.path.join(self.target.storedir,self.target.outfile)
