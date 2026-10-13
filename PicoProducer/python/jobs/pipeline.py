# Author: Izaak Neutelings (April 2020)
"""Job pipelines: select samples, plan their jobs, submit them and record the submission; find submitted samples.

  iter_plans()          for each era, channel and sample: find input files, split them into chunks, plan the
                        job names/directories/command lines, and yield one SamplePlan
     -> submit_plan()   submit a plan's job list to the batch system
     -> record_submission()  write the job config JSON (only after a successful submission)

  iter_submitted()      for each era, channel and sample with a job config: yield (era, channel, sample)
                        for status, hadd, haddclean and clean (jobs/status.py, jobs/merge.py)

The pure calculations live in jobs/planner.py and jobs/worker_command.py; this module does the I/O around them,
in the same order as the old pico/job.py, so the output of pico.py is unchanged:
  - it reads sample catalogs, storage file lists, event counts and (on resubmission) the job status;
  - with materialize=True (pico.py submit) it creates the job directories and the output directory and writes
    the job list at the points where pico/job.py did; with materialize=False it writes nothing;
  - it reports through a reporter (jobs/reporting.py); interactive questions are callables from the caller.

iter_plans is a generator: the caller submits each sample before the next one is planned, and the output of
planning and submitting stays interleaved per sample.

Inputs:  the configuration, a JobRequest, a reporter, a batch system.
Outputs: SamplePlan per sample; job directories, job lists and job configs (materialize=True); submitted jobs.

Public API:
  iter_plans(config, request, reporter, on_existing, materialize)   -> iterator of SamplePlan
  submit_plan(batch, plan, request, reporter, confirm)              -> job ID or None
  record_submission(plan, jobid, reporter, verbosity)               append the job ID, write the job config
  iter_submitted(config, request, reporter, action)                 -> iterator of (era, channel, sample)
  SamplePlan                                                        record (at the bottom of this file)
"""

# ===== Imports =====
import os, re, glob
from datetime import datetime
from dataclasses import dataclass
from TauFW.common.tools.file import ensuredir
from TauFW.common.tools.utils import chunkify
from TauFW.common.tools.log import Logger
from TauFW.PicoProducer.batch.factory import getbatch
from TauFW.PicoProducer.datasets.catalog import getsamples
from TauFW.PicoProducer.storage.factory import getstorage
from TauFW.PicoProducer.jobs.chunking import chunkify_by_evts
from TauFW.PicoProducer.jobs.jobconfig import make_jobcfg, write_jobcfg, getcfgsamples
from TauFW.PicoProducer.jobs.planner import sample_layout, assign_chunks, cfg_globs
from TauFW.PicoProducer.jobs.reporting import Reporter
from TauFW.PicoProducer.jobs.status import check_sample
from TauFW.PicoProducer.jobs.worker_command import resolve_worker

__all__ = ['iter_plans', 'submit_plan', 'record_submission', 'iter_submitted', 'SamplePlan']


# ===== Constants =====
LOG = Logger()


# ===== Pipeline =====

def iter_plans(config,request,reporter=None,on_existing=None,materialize=True):
  """Plan the (re)submission of every selected sample, one SamplePlan at a time.
  on_existing(cfgname) is asked when a sample's job config already exists (without --force):
    'yes' / 'no' / 'force' (yes, and stop asking), or None to skip the sample with a warning.
    Without on_existing the sample is skipped with a warning."""
  reporter     = reporter or Reporter()
  resubmit     = request.resubmit
  tag          = request.tag
  dtypes       = request.dtypes
  filters      = request.samples
  vetoes       = request.vetoes
  testrun      = request.testrun
  tmpdir       = request.tmpdir or config.get('tmpskimdir',None) # temporary dir for creating skimmed file before copying to outdir
  force        = request.force # may be switched on by on_existing
  verbosity    = request.verbosity
  jobs         = None

  # LOOP over ERAS
  for era in request.eras:
    moddict = { } # save time by loading samples and get their file list only once

    # LOOP over CHANNELS
    for channel in request.channels:
      reporter.header("%s, %s"%(era,channel))

      # MODULE & PROCESSOR
      worker = resolve_worker(config,channel,request.extraopts)
      if verbosity>=1:
        reporter.line('-'*80)
        reporter.line(_kv('channel',channel))
        reporter.line(_kv('processor',worker.processor))
        reporter.line(_kv('module',worker.module))
        reporter.line(_kv('procopts',worker.procopts))
        reporter.line(_kv('extrachopts',worker.extrachopts))
        reporter.line(_ks('filters',filters))
        reporter.line(_ks('vetoes',vetoes))
        reporter.line(_kv('dtypes',dtypes))

      # GET SAMPLES
      jobdir_ = ""
      jobcfgs = ""
      if resubmit: # get samples from existing job config files
        jobdir_, jobcfgs = cfg_globs(config.jobdir,era,channel,tag)
        if verbosity>=2:
          reporter.line(_ks('cwd',os.getcwd()))
          reporter.line(_ks('jobcfgs',jobcfgs))
        samples = getcfgsamples(jobcfgs,filter=filters,veto=vetoes,dtype=dtypes,verb=verbosity)
      else: # get samples from sample list
        LOG.insist(era in config.eras,"Era '%s' not found in the configuration file. Available: %s"%(era,config.eras))
        samples = getsamples(era,channel=channel,tag=tag,dtype=dtypes,filter=filters,veto=vetoes,
                             dasfilter=request.dasfilters,dasveto=request.dasvetoes,moddict=moddict,verb=verbosity)
      if verbosity>=2:
        reporter.line(">>> Found samples: "+", ".join(repr(s.name) for s in samples))
      if testrun:
        samples = samples[:2] # run at most two samples

      # LOOP over SAMPLES
      found  = len(samples)>=0 # BUGS P05: always true
      failed = [ ] # failed samples
      for sample in samples:
        reporter.sample(sample.name,sample.paths)

        # DIRECTORIES
        layout = sample_layout(config,request,sample,era,channel,worker.extrachopts)
        if materialize:
          _make_jobdirs(layout)
        _report_layout(reporter,sample,layout,worker,request,tmpdir,verbosity)

        # CHECKS
        if os.path.isfile(layout.cfgname):
          # TODO: check for running jobs ?
          skip = False
          if force:
            reporter.warning("Job configuration %r already exists and will be overwritten! "%(layout.cfgname)+
                             "Please beware of conflicting job output!")
          else:
            answer = on_existing(layout.cfgname) if on_existing else None
            if answer is None:
              skip = True
              reporter.warning("Job configuration %r already exists and might cause conflicting job output! "%(layout.cfgname)+
                               "To submit anyway, please use the --force flag")
            elif answer=='force': # submit this job, and stop asking
              force = True; skip = True
            elif answer=='yes': # BUGS P20: 'yes' skips the sample, 'no' submits it
              skip = True
          if skip: # do not submit this job
            failed.append(sample)
            reporter.line("")
            continue
        if not resubmit: # check for existing jobss
          cfgpattern = re.sub(r"(?<=try)\d+(?=.json(?:\.gz)?$)",r"*",layout.cfgname)
          cfgnames   = [f for f in glob.glob(cfgpattern) if not f.endswith("_try1.json")]
          if cfgnames:
            reporter.warning("Job configurations for resubmission already exists! This can cause conflicting job output! "+
              "If you are sure you want to submit from scratch, please remove these files:\n>>>   "+"\n>>>   ".join(cfgnames))
        if materialize:
          getstorage(layout.outdir,verb=verbosity,ensure=True) # create the output directory

        # GET FILES
        nevents = 0
        if resubmit: # resubmission
          if request.checkqueue==1 and jobs!=None: # BUGS P04: never true; check jobs only once to speed up performance
            batch = getbatch(config,verb=verbosity)
            jobs  = batch.jobs(verb=verbosity-1)
          status  = check_sample(sample,config,reporter,channel=channel,tag=tag,jobs=jobs,checkqueue=request.checkqueue,
                                 checkevts=request.checkevts,checkexpevts=request.checkexpevts,
                                 das=request.checkdas,ncores=request.ncores,verb=verbosity)
          infiles   = status.resubfiles # input files of failed and missing chunks
          chunkdict = status.chunkdict  # chunks that are done
          nevents   = status.nexpected
        else: # first-time submission
          infiles = sample.getfiles(das=request.dasfiles,verb=verbosity-1)
          if request.checkdas:
            nevents = sample.getnevents(verb=verbosity-1)
          chunkdict = { }
        if testrun:
          infiles = infiles[:4] # only run four files per sample
        _report_files(reporter,layout,infiles,verbosity)

        # CHUNKS - partition/split list of input files
        infiles.sort() # to have consistent order with resubmission
        maxevts      = layout.maxevts
        nfilesperjob = layout.nfilesperjob
        if maxevts>1: # split jobs by number of events (max. maxevts events per job)
          if verbosity>=1:
            reporter.line(">>> Preparing jobs with chunks split by number of events...")
          try: # list of file chunks split by events; adds the 'fname:firstevt:maxevts' entries to infiles
            ntot, fchunks = chunkify_by_evts(infiles,maxevts,evtdict=sample.filenevts,verb=verbosity,progress=reporter.progress)
            if nevents<=0 and not resubmit:
              nevents = ntot
          except IOError as err: # capture if opening files fail
            reporter.line("IOError: "+err.message) # BUGS P01: err.message does not exist in Python 3
            reporter.warning("Skipping submission...")
            failed.append(sample)
            reporter.line("")
            continue # ignore this submission
          if testrun:
            fchunks = fchunks[:4]
        else: # split jobs by number of files (max. nfilesperjob files per job)
          if verbosity>=1:
            reporter.line(">>> Preparing jobs with chunks split by number of files (nfilesperjob_=%r)..."%(nfilesperjob))
          if nfilesperjob<1:
            reporter.warning("preparejobs: nfilesperjob_=%r<1 ! (user: %r, sample: %r, config: %r) Setting to 1..."%(
                             nfilesperjob,request.nfilesperjob,sample.nfilesperjob,config.nfilesperjob))
            nfilesperjob = 1
          fchunks = chunkify(infiles,nfilesperjob) # list of file chunks split by number of files
        nfiles  = len(infiles)
        nchunks = len(fchunks)
        if verbosity>=1:
          reporter.line(_ks('nchunks',nchunks))
        if verbosity>=2:
          reporter.line(_ks('nevents',nevents))
          reporter.line('-'*80)

        # JOB LIST with arguments per job
        chunks, chunkdict, commands = assign_chunks(fchunks,chunkdict,layout,worker,era,channel,request,tmpdir)
        if materialize:
          _write_joblist(reporter,layout.joblist,commands,verbosity)

        # JOB CONFIG
        jobcfg = make_jobcfg(str(datetime.now()),
          group=sample.group,      paths=sample.paths,     name=sample.name,       nevents=nevents,
          dtype=layout.dtype,      channel=channel,        module=worker.module,   extraopts=layout.extraopts,
          jobname=layout.jobname,  jobtag=layout.jobtag,   tag=tag,                postfix=layout.postfix,
          queue=layout.queue,      jobids=layout.jobids,   prefetch=layout.prefetch, outdir=layout.outdir,
          jobdir=layout.jobdir,    cfgdir=layout.cfgdir,   logdir=layout.logdir,   cfgname=layout.cfgname,
          joblist=layout.joblist,  maxevts=maxevts,        nfiles=nfiles,          files=infiles,
          nfilesperjob=nfilesperjob, nchunks=nchunks,      chunks=chunks,          chunkdict=chunkdict,
          filenevts=sample.filenevts, **{'try': layout.subtry})

        # YIELD
        yield SamplePlan(era=era,channel=channel,sample=sample,commands=commands,jobcfg=jobcfg)
        reporter.line('')

      if not found:
        reporter.no_samples(dtypes,filters,vetoes,[channel],jobdir_,jobcfgs)
      elif failed and len(failed)!=len(samples):
        reporter.line(">>> %d/%d samples failed: %s\n"%(len(failed),len(samples),', '.join(s.name for s in failed)))


def submit_plan(batch,plan,request,reporter=None,confirm=None):
  """Submit the job list of a plan. confirm(nchunks) -> bool is asked first, if given.
  Returns the job ID, or None if nothing was submitted."""
  reporter = reporter or Reporter()
  jobcfg   = plan.jobcfg
  jobdir   = jobcfg['jobdir']
  logdir   = jobcfg['logdir']
  joblist  = jobcfg['joblist'] # text file with list of tasks to be executed per job
  jobname  = jobcfg['jobname']
  nchunks  = jobcfg['nchunks']
  jkwargs  = { # key-word arguments for batch.submit
    'name': jobname, 'opt': request.batchopts, 'dry': request.dryrun,
    'short': (request.testrun>0), 'queue': jobcfg['queue'], 'time': request.time
  }
  if nchunks<=0:
    reporter.line(">>>   Nothing to %ssubmit!"%('re' if request.resubmit else ''))
    return None
  if 'HTCondor' in batch.system:
    appcmds = ["initialdir=%s"%(jobdir),
               "mylogfile='log/%s.$(ClusterId).$(ProcId).log'"%(jobname)]
    jkwargs.update({ 'app': appcmds })
  elif 'SLURM' in batch.system:
    logfile = os.path.join(logdir,"%x.%A.%a.log") # $JOBNAME.o$JOBID.$TASKID.log
    jkwargs.update({ 'log': logfile, 'array': nchunks })
  if confirm and not confirm(nchunks): # ask user confirmation before submitting
    return None
  return batch.submit(batch.script,taskfile=joblist,**jkwargs)


def record_submission(plan,jobid,reporter=None,verbosity=0):
  """After a successful submission: add the job ID to the plan's job config and write it."""
  reporter = reporter or Reporter()
  if jobid!=None:
    plan.jobcfg['jobids'].append(jobid)
    if verbosity>=1:
      reporter.line(">>> Creating config file '%s'..."%(plan.jobcfg['cfgname']))
    write_jobcfg(plan.jobcfg,plan.jobcfg['cfgname'])


def iter_submitted(config,request,reporter=None,action='status'):
  """The samples of existing job configs (their last try), for action 'status', 'hadd', 'haddclean' or 'clean'.
  Yields (era, channel, sample) after reporting the sample; with channel '*' the channel comes from the job config
  name. Without eras or channels, 'status' looks at all of them; 'hadd'/'haddclean' skip skim channels."""
  reporter  = reporter or Reporter()
  tag       = request.tag
  dtypes    = request.dtypes
  filters   = request.samples
  vetoes    = request.vetoes
  verbosity = request.verbosity
  eras      = request.eras
  channels  = request.channels
  if action not in ['hadd','clean','haddclean']:
    if not channels:
      channels = ['*']
    if not eras:
      eras     = ['*']

  # LOOP over ERAS
  for era in eras:

    # LOOP over CHANNELS
    for channel in channels:
      reporter.header("%s, %s"%(era,channel))

      # GET SAMPLES
      jobdir_, jobcfgs = cfg_globs(config.jobdir,era,channel,tag,group='*') # get ALL job configs
      if verbosity>=1:
        reporter.line(_ks('cwd',os.getcwd()))
        reporter.line(_ks('jobdir',jobdir_))
        reporter.line(_ks('jobcfgs',jobcfgs))
        reporter.line(_ks('filters',filters))
        reporter.line(_ks('vetoes',vetoes))
        reporter.line(_ks('dtypes',dtypes))
      samples = getcfgsamples(jobcfgs,filter=filters,veto=vetoes,dtype=dtypes,verb=verbosity)
      if verbosity>=2:
        reporter.line(">>> Found samples: "+", ".join(repr(s.name) for s in samples))
      if action in ['hadd','haddclean'] and 'skim' in channel.lower():
        reporter.warning("Hadding into one file not available for skimming...")
        reporter.line('')
        continue

      # LOOP over SAMPLES
      found = False
      for sample in samples:
        channel_ = channel
        if channel=='*': # grab channel from job config name
          matches = re.findall(r"config/jobconfig_(\w+)%s_try\d+.json(?:\.gz)?"%(tag),sample.jobcfg['config'])
          if matches:
            channel_ = matches[0]
        elif sample.channels and channel_ not in sample.channels:
          continue
        found = True
        reporter.sample(sample.name,sample.paths)
        yield era, channel_, sample

      if not found:
        reporter.no_samples(dtypes,filters,vetoes,[channel],jobdir_,jobcfgs)


# ===== Records =====

@dataclass
class SamplePlan:
  """The planned (re)submission of one sample.
  jobcfg is the job config that record_submission writes; commands are the job-list lines (chunk, command)."""
  era:      str
  channel:  str
  sample:   object
  commands: list
  jobcfg:   dict


# ===== Helpers =====

def _make_jobdirs(layout):
  """Create the job, config and log directories."""
  ensuredir(layout.jobdir)
  ensuredir(layout.cfgdir)
  ensuredir(layout.logdir)


def _write_joblist(reporter,joblist,commands,verbosity):
  """Write the job list: one worker command line per chunk. Nothing is written without chunks."""
  if verbosity>=1:
    reporter.line(">>> Creating job list %s..."%(joblist))
  if commands:
    with open(joblist,'w') as listfile:
      for ichunk, jobcmd in commands:
        if verbosity>=1:
          reporter.line(">>> chunk=%d, jobcmd=%r"%(ichunk,jobcmd))
        listfile.write(jobcmd+'\n')


def _report_layout(reporter,sample,layout,worker,request,tmpdir,verbosity):
  """Verbose output of a sample's job settings."""
  if verbosity==1:
    reporter.line(_ks('cfgname',layout.cfgname))
    reporter.line(_ks('joblist',layout.joblist))
  elif verbosity>=2:
    reporter.line('-'*80)
    reporter.line(">>> Preparing job %ssubmission for '%s'"%("re" if request.resubmit else "",sample.name))
    reporter.line(_kv('processor',worker.processor))
    reporter.line(_kv('dtype',layout.dtype))
    reporter.line(_kv('jobname',layout.jobname))
    reporter.line(_kv('jobtag',layout.jobtag))
    reporter.line(_kv('postfix',layout.postfix))
    reporter.line(_kv('outdir',layout.outdir))
    reporter.line(_kv('extraopts',layout.extraopts))
    reporter.line(_kv('prefetch',layout.prefetch))
    reporter.line(_kv('preselect',request.preselect))
    reporter.line(_kv('cfgdir',layout.cfgdir))
    reporter.line(_kv('logdir',layout.logdir))
    reporter.line(_kv('tmpdir',tmpdir))
    reporter.line(_kv('cfgname',layout.cfgname))
    reporter.line(_kv('joblist',layout.joblist))
    reporter.line(_ks('try',layout.subtry))
    reporter.line(_kv('jobids',layout.jobids))
    reporter.line(_kv('queue',layout.queue))


def _report_files(reporter,layout,infiles,verbosity):
  """Verbose output of a sample's splitting settings and input files."""
  if verbosity>=1:
    reporter.line(_ks('maxevts',layout.maxevts))
    reporter.line(_ks('nfilesperjob',layout.nfilesperjob))
    reporter.line(_ks('nfiles',len(infiles)))
  if verbosity>=2:
    reporter.line(">>> %-12s = [ "%('infiles'))
    for file in infiles:
      reporter.line(">>>   %r"%file)
    reporter.line(">>> ]")


def _kv(key,value):
  """Verbose line 'key = repr(value)'."""
  return ">>> %-12s = %r"%(key,value)


def _ks(key,value):
  """Verbose line 'key = str(value)'."""
  return ">>> %-12s = %s"%(key,value)

