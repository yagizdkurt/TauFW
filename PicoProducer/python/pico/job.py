#! /usr/bin/env python
# Author: Izaak Neutelings (April 2020)
"""pico.py submit / resubmit / status / hadd / haddclean / clean: thin command functions over jobs/.

Each command builds a JobRequest from its arguments and streams the jobs/ pipelines sample by sample, so the
output of planning, submitting, checking and merging stays interleaved per sample. The prompts of --prompt are
the only logic kept here (_Prompt, at the bottom).

Public API:
  main_submit(args)   submit, resubmit
  main_status(args)   status, hadd, haddclean, clean
"""

# ===== Imports =====
from TauFW.PicoProducer.batch.factory import getbatch
from TauFW.PicoProducer.jobs.merge import merge_sample, MERGE_ACTIONS
from TauFW.PicoProducer.jobs.pipeline import iter_plans, submit_plan, record_submission, iter_submitted
from TauFW.PicoProducer.jobs.reporting import ConsoleReporter
from TauFW.PicoProducer.jobs.request import JobRequest
from TauFW.PicoProducer.jobs.status import check_sample
from TauFW.PicoProducer.pico.common import CONFIG, LOG


# ===== Commands =====

def main_submit(args):
  """Submit or resubmit jobs to the batch system."""
  if args.verbosity>=1:
    print(">>> main_submit", args)
  request  = JobRequest.from_args(args)
  batch    = getbatch(CONFIG,verb=request.verbosity+1)
  reporter = ConsoleReporter(LOG)
  prompt   = _Prompt() if args.prompt else None # ask user confirmation
  if args.verbosity>=1:
    print(">>> preparejobs", args)
  plans    = iter_plans(CONFIG,request,reporter,on_existing=prompt and prompt.existing)
  for plan in plans:
    jobid  = submit_plan(batch,plan,request,reporter,confirm=prompt and prompt.submit)
    record_submission(plan,jobid,reporter,request.verbosity)


def main_status(args):
  """Check status of jobs (succesful/pending/failed/missing), or hadd/clean job output."""
  if args.verbosity>=1:
    print(">>> main_status", args)
  action    = args.subcommand
  request   = JobRequest.from_args(args)
  reporter  = ConsoleReporter(LOG)
  verbosity = request.verbosity
  jobs      = None
  for era, channel, sample in iter_submitted(CONFIG,request,reporter,action):

    # CHECK JOBS ONLY ONCE
    if request.checkqueue==1 and jobs!=None: # BUGS P04: never true
      batch = getbatch(CONFIG,verb=verbosity)
      jobs  = batch.jobs(verb=verbosity-1)

    # HADD or CLEAN
    if action in MERGE_ACTIONS:
      hadd   = 'hadd' in action
      result = merge_sample(sample,CONFIG,action,era,channel,request.tag,reporter,
                            clean=getattr(args,'cleanup',False),force=request.force,
                            haddcmd=args.haddcmd if hadd else "",maxopenfiles=args.maxopenfiles if hadd else 0,
                            jobs=jobs,checkqueue=request.checkqueue,checkevts=request.checkevts,
                            checkexpevts=request.checkexpevts,das=request.checkdas,ncores=request.ncores,
                            dryrun=request.dryrun,verb=verbosity)
      if result.refused:
        continue

    # ONLY CHECK STATUS
    else:
      if verbosity>=1:
        _report_jobcfg(reporter,sample)
      check_sample(sample,CONFIG,reporter,channel=channel,tag=request.tag,jobs=jobs,showlogs=args.showlogs,
                   checkqueue=request.checkqueue,checkevts=request.checkevts,das=request.checkdas,
                   ncores=request.ncores,verb=verbosity) # BUGS P21: checkexpevts is not passed

    reporter.line('')


# ===== Prompts =====

class _Prompt(object):
  """Questions of `pico.py submit --prompt`. Answering 'all' at a submission stops all further questions."""

  def existing(self,cfgname):
    """A sample's job config already exists: 'yes', 'no' or 'force' (and stop asking); None if not asking."""
    if not self.active:
      return None
    LOG.warn("Job configuration %r already exists and might cause conflicting job output!"%(cfgname))
    while True:
      submit = input(">>> Submit anyway? [y/n] ") # BUGS P02: was formatted with an undefined nchunks
      if 'f' in submit.lower(): # submit this job, and stop asking
        print(">>> Force all.")
        return 'force'
      elif 'y' in submit.lower(): # submit this job
        print(">>> Continue submission...")
        return 'yes'
      elif 'n' in submit.lower(): # do not submit this job
        print(">>> Not submitting.")
        return 'no'
      else:
        print(">>> '%s' is not a valid answer, please choose y/n."%submit)

  def submit(self,nchunks):
    """Submit nchunks jobs? Returns True or False; 'q'/'exit' quits pico.py."""
    if not self.active:
      return True
    while True:
      submit = input(">>> Do you want to submit %d jobs to the batch system? [y/n] "%(nchunks))
      if any(s in submit.lower() for s in ['q','exit']): # quit this script
        print(">>> Quitting...")
        exit(0)
      elif any(s in submit.lower() for s in ['f','all']):
        print(">>> Force submission...")
        submit = 'y'
        self.active = False # stop asking for next samples
      if 'y' in submit.lower(): # submit this job
        return True
      elif 'n' in submit.lower(): # do not submit this job
        print(">>> Not submitting.")
        return False
      else:
        print(">>> '%s' is not a valid answer, please choose y/n."%submit)

  def __init__(self):
    self.active = True


# ===== Helpers =====

def _report_jobcfg(reporter,sample):
  """Verbose output before a status check."""
  jobcfg = sample.jobcfg
  reporter.line(">>> Checking job status for '%s'"%(sample.name))
  reporter.line(">>> %-12s = %r"%('cfgname',jobcfg['config']))
  reporter.line(">>> %-12s = %r"%('jobdir',jobcfg['jobdir']))
  reporter.line(">>> %-12s = %r"%('outdir',jobcfg['outdir']))
  reporter.line(">>> %-12s = %r"%('logdir',jobcfg['logdir']))
