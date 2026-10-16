# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""PicoProducer: the public API for producing pico tuples (NanoAOD -> analysis tuples) on a batch system.

One object, one configuration, explicit calls. Every call takes a JobRequest (what to produce) and returns a
record from api/types.py. Messages go to the reporter given at construction (silent by default); `pico.py` passes
a ConsoleReporter and gets the familiar terminal output, because it uses this class too.

Pipeline (one production stage):

    JobRequest ─▶ plan() ─▶ submit() ─▶ status() ─┬─▶ resubmit() ─▶ status() ─▶ …
                  JobPlan   Submission  StageStatus│
                                                   └─▶ merge(clean=True) ─▶ MergeReport (TupleArtifact per sample)
    run_local(): quick test of a channel on a few files, without the batch system

Side effects of each call are listed in its docstring. Calls that touch files run inside the PicoProducer
directory (all configured paths are relative to it): the working directory is changed for the duration of the
call and always restored. That makes the API not thread-safe; see docs/PicoProducer/API.md.

Inputs:  a configuration (config/config.json, another JSON file, a dict or a Config), JobRequests.
Outputs: job directories, job lists and job configs (output/...), batch jobs, merged tuples in storage (picodir
         of the configuration, or <request.tupledir>/$ERA/$GROUP: see tuple_pattern); the records of api/types.py.

Public API:
  PicoProducer.from_config(config, reporter, basedir)
  plan, submit, resubmit, status, merge, clean, run_local    pipelines
  iter_plan                                                  plan() as a stream, one PlannedSample at a time
  request(**fields)                                          build a JobRequest
  tuple_pattern(request)                                     where merge() writes the tuples
"""

# ===== Imports =====
import os
from contextlib import contextmanager
from dataclasses import replace
from TauFW.PicoProducer import basedir as BASEDIR
from TauFW.PicoProducer.batch.factory import getbatch
from TauFW.PicoProducer.settings.model import Config
from TauFW.PicoProducer.settings.store import loadconfig
from TauFW.PicoProducer.jobs.reporting import Reporter
from TauFW.PicoProducer.jobs.pipeline import iter_plans, submit_plan, record_submission, iter_submitted
from TauFW.PicoProducer.jobs.status import check_sample
from TauFW.PicoProducer.jobs.merge import merge_sample, MERGE_ACTIONS, TUPLE_LAYOUT
from TauFW.PicoProducer.jobs.local import iter_local_runs, execute_run
from TauFW.PicoProducer.api.types import (JobPlan, PlannedSample, Submission, SubmittedSample, StageStatus,
                                          SampleStatus, MergeReport, TupleArtifact, LocalResult, request_from_dict)

__all__ = ['PicoProducer']


class PicoProducer(object):
  """Production of pico tuples with one configuration.

  Pipelines:     plan(request)                         -> JobPlan        reads only
                 submit(request, on_existing, confirm)  -> Submission     writes job files, submits
                 resubmit(request, ...)                 -> Submission     failed/missing chunks of the last try
                 status(request, showlogs)              -> StageStatus    reads only
                 merge(request, clean, force, ...)      -> MergeReport    hadd into storage (+ cleanup)
                 clean(request, force)                  -> MergeReport    remove job files and job output
                 run_local(request)                     -> (LocalResult,) runs workers locally
  Streams:       iter_plan(request)                     -> PlannedSample, one at a time
  Requests:      request(**fields)                      -> JobRequest (unknown fields are an error)
                 tuple_pattern(request)                 -> str            where merge() writes the tuples
  Construction:  from_config(config, reporter, basedir); PicoProducer(config, reporter, basedir)
  """

  # ===== Pipelines =====

  def plan(self,request):
    """What submit() would do, without writing or submitting anything.
    Side effects: none (reads sample catalogs, storage listings or DAS; on resubmission, the queue and the job
    output to find the chunks to resubmit). A sample whose job config already exists is planned with
    conflict=True."""
    return JobPlan(request=request,samples=tuple(self.iter_plan(request)))

  def submit(self,request,on_existing=None,confirm=None):
    """Plan and submit the jobs of every selected sample, one sample at a time.
    on_existing(cfgname) -> 'yes'/'no'/'force'/None decides about a sample whose job config exists (default:
    skip it with a warning, unless request.force); confirm(nchunks) -> bool is asked before each submission.
    Side effects: creates job/config/log directories, the output directory and the job list; submits to the
    batch system (not with request.dryrun); writes the job config after a successful submission."""
    batch   = getbatch(self.config,verb=request.verbosity+1)
    samples = [ ]
    with self._workdir():
      for plan in iter_plans(self.config,request,self.reporter,on_existing=on_existing):
        jobid = submit_plan(batch,plan,request,self.reporter,confirm=confirm)
        record_submission(plan,jobid,self.reporter,request.verbosity)
        samples.append(_submitted(plan,jobid,request))
    return Submission(samples=tuple(samples))

  def resubmit(self,request,on_existing=None,confirm=None):
    """Resubmit the failed and missing chunks of each sample's last try (a new try, with its own job config).
    Side effects: as submit(); checks the status (queue, job output) first."""
    return self.submit(replace(request,resubmit=True),on_existing=on_existing,confirm=confirm)

  def status(self,request,showlogs=0):
    """Status of the chunks of each sample's last try (good, pending, failed, missing).
    showlogs: report the log files of failed/missing chunks (number, or -1 for all).
    Side effects: none (queries the batch queue, lists and validates the job output)."""
    samples = [ ]
    jobs    = None
    with self._workdir():
      for era, channel, sample in iter_submitted(self.config,request,self.reporter,'status'):
        jobs = self._queue_once(request,jobs)
        if request.verbosity>=1:
          _report_jobcfg(self.reporter,sample)
        status = check_sample(sample,self.config,self.reporter,channel=channel,tag=request.tag,jobs=jobs,
                              showlogs=showlogs,checkqueue=request.checkqueue,checkevts=request.checkevts,
                              das=request.checkdas,checkexpevts=request.checkexpevts,ncores=request.ncores,
                              verb=request.verbosity)
        samples.append(_sample_status(era,channel,sample,status))
        self.reporter.line('')
    return StageStatus(samples=tuple(samples))

  def merge(self,request,clean=False,force=None,haddcmd=None,maxopenfiles=None,action=None):
    """Merge (hadd) the job output of each complete sample into one tuple in storage (tuple_pattern(request):
    <request.tupledir>/$ERA/$GROUP, or picodir of the configuration).
    clean: afterwards remove the job files and job output, once the merged tuple is validated;
    force: also merge samples with failed, missing or pending chunks (default: request.force);
    haddcmd/maxopenfiles: default from the configuration; action: label in messages ('hadd' or 'haddclean',
    default from clean).
    Side effects: creates the storage directory, writes the merged tuples, removes job files if clean
    (nothing is executed with request.dryrun)."""
    action = action or ('haddclean' if clean else 'hadd')
    return self._merge(request,action,clean=clean,force=force,haddcmd=haddcmd,maxopenfiles=maxopenfiles)

  def clean(self,request,force=None):
    """Remove the job files and job output of each complete sample (force: also incomplete ones).
    Side effects: removes job directories or files (not with request.dryrun)."""
    return self._merge(request,'clean',force=force)

  def run_local(self,request):
    """Run the worker of each selected sample locally on its first request.nfiles files (or on request.infiles).
    Side effects: runs the workers (not with request.dryrun), which write to request.outdir."""
    results = [ ]
    with self._workdir():
      for run in iter_local_runs(self.config,request,self.reporter):
        exitcode = execute_run(run,self.reporter,dryrun=request.dryrun)
        results.append(LocalResult(era=run.era,channel=run.channel,sample=run.sample.name if run.sample else None,
                                   command=run.command,exitcode=exitcode))
    failed = [r for r in results if r.exitcode]
    if failed: # BUGS P11: worker failures were not reported
      self.reporter.warning("%d local run(s) failed: %s"%(len(failed),', '.join(r.sample or r.channel for r in failed)))
    return tuple(results)

  # ===== Streams =====

  def iter_plan(self,request):
    """plan() one sample at a time: yields PlannedSample. The working directory is the PicoProducer directory
    only while a sample is planned, not while the caller handles it."""
    plans = iter_plans(self.config,request,self.reporter,on_existing=_plan_anyway,materialize=False)
    yield from self._scoped(_planned(plan) for plan in plans) # _planned checks the job config inside the directory

  # ===== Requests =====

  @staticmethod
  def request(**fields):
    """A JobRequest from keyword fields; unknown fields raise KeyError. Lets callers (e.g. the Framework) build
    requests without importing the jobs package."""
    return request_from_dict(fields)

  def tuple_pattern(self,request):
    """Where merge() writes the tuples, as a pattern with $ERA, $GROUP (and whatever else picodir uses):
    <request.tupledir>/$ERA/$GROUP (TUPLE_LAYOUT, tupledir made absolute), or else picodir of the configuration,
    made absolute against the PicoProducer directory if it is relative (merge runs there); a picodir that starts
    with '$' or is a URL is returned as it is. Reads nothing."""
    if request.tupledir:
      return os.path.join(os.path.abspath(request.tupledir),*TUPLE_LAYOUT.split('/'))
    picodir = self.config.picodir
    if picodir.startswith('$') or '://' in picodir or os.path.isabs(picodir):
      return picodir
    return os.path.normpath(os.path.join(self.basedir,picodir))

  # ===== Steps =====

  def _merge(self,request,action,clean=False,force=None,haddcmd=None,maxopenfiles=None):
    """hadd, haddclean or clean every sample with a job config."""
    assert action in MERGE_ACTIONS, "Unknown merge action %r"%(action)
    hadd         = 'hadd' in action
    force        = request.force if force is None else force
    haddcmd      = (self.config.haddcmd if haddcmd is None else haddcmd) if hadd else ""
    maxopenfiles = (self.config.maxopenfiles if maxopenfiles is None else maxopenfiles) if hadd else 0
    artifacts, refused, invalid, cleaned = [ ], [ ], [ ], [ ]
    jobs = None
    picodir = self.tuple_pattern(request) if request.tupledir else None # None: merge_sample uses the configuration's
    with self._workdir():
      for era, channel, sample in iter_submitted(self.config,request,self.reporter,action):
        jobs   = self._queue_once(request,jobs)
        result = merge_sample(sample,self.config,action,era,channel,request.tag,self.reporter,clean=clean,
                              force=force,haddcmd=haddcmd,maxopenfiles=maxopenfiles,jobs=jobs,
                              checkqueue=request.checkqueue,checkevts=request.checkevts,
                              checkexpevts=request.checkexpevts,das=request.checkdas,ncores=request.ncores,
                              dryrun=request.dryrun,verb=request.verbosity,picodir=picodir)
        if result.refused:
          refused.append(sample.name)
          continue
        if result.merged and not request.dryrun:
          artifacts.append(_artifact(era,channel,request.tag,sample,result))
        if result.invalid:
          invalid.append((sample.name,result.invalid))
        if result.rmcmds and not request.dryrun:
          cleaned.append(sample.name)
        self.reporter.line('')
    return MergeReport(artifacts=tuple(artifacts),refused=tuple(refused),invalid=tuple(invalid),cleaned=tuple(cleaned))

  def _queue_once(self,request,jobs):
    """--checkqueue 1: query the batch queue once, for all samples."""
    if request.checkqueue==1 and jobs is None: # BUGS P04: was 'jobs!=None' (never true)
      batch = getbatch(self.config,verb=request.verbosity)
      jobs  = batch.jobs(verb=request.verbosity-1)
    return jobs

  # ===== Working directory =====

  @contextmanager
  def _workdir(self):
    """Run inside the PicoProducer directory (configured paths are relative to it); always restored."""
    cwd = os.getcwd()
    os.chdir(self.basedir)
    try:
      yield
    finally:
      os.chdir(cwd)

  def _scoped(self,iterator):
    """Advance an iterator inside the PicoProducer directory, but yield its items outside of it."""
    while True:
      with self._workdir():
        try:
          item = next(iterator)
        except StopIteration:
          return
      yield item

  # ===== Construction =====

  @classmethod
  def from_config(cls,config=None,reporter=None,basedir=None):
    """config: None (config/config.json), a path to a JSON file, a dict, or a Config.
    Reads the configuration only: never writes it, never changes the working directory."""
    if config is None or isinstance(config,str):
      config = loadconfig(config)
    elif isinstance(config,dict):
      config = Config(dict(config),"<dict>")
    return cls(config,reporter=reporter,basedir=basedir)

  def __init__(self,config,reporter=None,basedir=None):
    self.config   = config
    self.reporter = reporter or Reporter()
    self.basedir  = os.path.abspath(basedir or BASEDIR)

  def __repr__(self):
    return "<PicoProducer(config=%r, basedir=%r)>"%(getattr(self.config,'_path',None),self.basedir)


# ===== Conversions to API records =====

def _plan_anyway(cfgname):
  """plan(): plan a sample even if its job config exists (PlannedSample.conflict records it)."""
  return 'yes'


def _planned(plan):
  jobcfg = plan.jobcfg
  return PlannedSample(era=plan.era,channel=plan.channel,name=jobcfg['name'],group=jobcfg['group'],
                       dtype=jobcfg['dtype'],paths=tuple(jobcfg['paths']),subtry=jobcfg['try'],
                       jobname=jobcfg['jobname'],cfgname=jobcfg['cfgname'],joblist=jobcfg['joblist'],
                       outdir=jobcfg['outdir'],nfiles=jobcfg['nfiles'],nchunks=jobcfg['nchunks'],
                       nevents=jobcfg['nevents'],commands=tuple(cmd for _, cmd in plan.commands),
                       conflict=os.path.isfile(jobcfg['cfgname']))


def _submitted(plan,jobid,request):
  jobcfg = plan.jobcfg
  if jobcfg['nchunks']<=0:
    state = 'empty'
  elif jobid is not None:
    state = 'submitted'
  elif request.dryrun:
    state = 'dry'
  else:
    state = 'declined'
  return SubmittedSample(era=plan.era,channel=plan.channel,name=jobcfg['name'],cfgname=jobcfg['cfgname'],
                         subtry=jobcfg['try'],nchunks=jobcfg['nchunks'],state=state,jobid=jobid)


def _sample_status(era,channel,sample,status):
  return SampleStatus(era=era,channel=channel,name=sample.name,group=sample.group,dtype=sample.dtype,
                      cfgname=sample.jobcfg['config'],subtry=sample.subtry,nchunks=status.nchunks,
                      good=tuple(status.good),pending=tuple(status.pending),failed=tuple(status.failed),
                      missing=tuple(status.missing),nprocevents=status.nprocevents,nexpected=status.nexpected,
                      complete=status.mergeable)


def _artifact(era,channel,tag,sample,result):
  return TupleArtifact(path=result.outpath,sample=sample.name,group=sample.group,era=era,channel=channel,tag=tag,
                       dtype=sample.dtype,nevents=result.status.nprocevents)


def _report_jobcfg(reporter,sample):
  """Verbose output before a status check."""
  jobcfg = sample.jobcfg
  reporter.line(">>> Checking job status for '%s'"%(sample.name))
  reporter.line(">>> %-12s = %r"%('cfgname',jobcfg['config']))
  reporter.line(">>> %-12s = %r"%('jobdir',jobcfg['jobdir']))
  reporter.line(">>> %-12s = %r"%('outdir',jobcfg['outdir']))
  reporter.line(">>> %-12s = %r"%('logdir',jobcfg['logdir']))
