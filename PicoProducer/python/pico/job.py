#! /usr/bin/env python
# Author: Izaak Neutelings (April 2020)
import os, re, glob
from TauFW.common.tools.utils import execute
from TauFW.common.tools.string import repkey, lreplace
from TauFW.PicoProducer.batch.factory import getbatch
from TauFW.PicoProducer.jobs.jobconfig import getcfgsamples
from TauFW.PicoProducer.jobs.pipeline import iter_plans, submit_plan, record_submission
from TauFW.PicoProducer.jobs.reporting import ConsoleReporter
from TauFW.PicoProducer.jobs.request import JobRequest
from TauFW.PicoProducer.jobs.status import check_sample
from TauFW.PicoProducer.storage.factory import getstorage
from TauFW.PicoProducer.datasets.catalog import print_no_samples
from TauFW.common.tools.log import bold
from TauFW.PicoProducer.pico.common import CONFIG, LOG

##################
#   (RE)SUBMIT   #
##################

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
  

class _Prompt(object):
  """Questions of `pico.py submit --prompt`. Answering 'all' at a submission stops all further questions."""
  
  def __init__(self):
    self.active = True
  
  def existing(self,cfgname):
    """A sample's job config already exists: 'yes', 'no' or 'force' (and stop asking); None if not asking."""
    if not self.active:
      return None
    LOG.warn("Job configuration %r already exists and might cause conflicting job output!"%(cfgname))
    while True:
      submit = input(">>> Submit anyway? [y/n] "%(nchunks)) # BUGS P02: nchunks is undefined here
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
  


############################
#   STATUS, HADD & CLEAN   #
############################

def main_status(args):
  """Check status of jobs (succesful/pending/failed/missing), or hadd job output."""
  if args.verbosity>=1:
    print(">>> main_status", args)
  
  # SETTING
  eras           = args.eras         # eras to loop over and run
  channels       = args.channels     # channels to loop over and run
  tag            = args.tag
  checkdas       = args.checkdas     # check number of events from DAS
  checkqueue     = args.checkqueue   # check queue of batch system for pending jobs
  checkevts      = args.checkevts    # validate output file & count events (slow, default)
  checkexpevts   = args.checkexpevts # compare actual to expected number of processed events
  dtypes         = args.dtypes       # filter (only include) these sample types ('data','mc','embed')
  filters        = args.samples      # filter (only include) these samples (glob patterns)
  dasfilters     = args.dasfilters   # filter (only include) these das paths (glob patterns)
  vetoes         = args.vetoes       # exclude these sample (glob patterns)
  dasvetoes      = args.dasvetoes    # exclude these DAS paths (glob patterns)
  force          = args.force
  subcmd         = args.subcommand
  cleanup        = subcmd=='clean' or (subcmd=='hadd' and args.cleanup) or subcmd=='haddclean'
  haddcmd        = ""
  maxopenfiles   = 0
  if 'hadd' in subcmd:
    haddcmd      = args.haddcmd      # alternative hadd command, e.g. haddnano.py
    maxopenfiles = args.maxopenfiles # maximum number of files opened during hadd, via -n option
  dryrun         = args.dryrun       # run through routine without actually executing hadd, rm, ...
  ncores         = args.ncores       # number of cores; validate output files in parallel
  verbosity      = args.verbosity
  cmdverb        = max(1,verbosity)
  outdirformat   = CONFIG.outdir
  jobdirformat   = CONFIG.jobdir
  storedirformat = CONFIG.picodir
  jobs           = None
  reporter       = ConsoleReporter(LOG)
  if subcmd not in ['hadd','clean','haddclean']:
    if not channels:
      channels = ['*']
    if not eras:
      eras     = ['*']
  
  # LOOP over ERAS
  for era in eras:
    
    # LOOP over CHANNELS
    for channel in channels:
      LOG.header("%s, %s"%(era,channel))
      
      # GET SAMPLES
      jobdir_ = repkey(jobdirformat,ERA=era,SAMPLE='*',GROUP='*',CHANNEL=channel,TAG=tag)
      jobcfgs = repkey(os.path.join(jobdir_,"config/jobconfig_$CHANNEL$TAG_try[0-9]*.json"),
                       ERA=era,SAMPLE='*',GROUP='*',CHANNEL=channel,TAG=tag) # get ALL job configs
      if verbosity>=1:
        print(">>> %-12s = %s"%('cwd',os.getcwd()))
        print(">>> %-12s = %s"%('jobdir',jobdir_))
        print(">>> %-12s = %s"%('jobcfgs',jobcfgs))
        print(">>> %-12s = %s"%('filters',filters))
        print(">>> %-12s = %s"%('vetoes',vetoes))
        print(">>> %-12s = %s"%('dtypes',dtypes))
      samples = getcfgsamples(jobcfgs,filter=filters,veto=vetoes,dtype=dtypes,verb=verbosity)
      if verbosity>=2:
        print(">>> Found samples: "+", ".join(repr(s.name) for s in samples))
      if subcmd in ['hadd','haddclean'] and 'skim' in channel.lower():
        LOG.warn("Hadding into one file not available for skimming...")
        print('')
        continue
      
      # SAMPLE over SAMPLES
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
        print(">>> %s"%(bold(sample.name)))
        for path in sample.paths:
          print(">>> %s"%(bold(path)))
        
        # CHECK JOBS ONLY ONCE
        if checkqueue==1 and jobs!=None:
          batch = getbatch(CONFIG,verb=verbosity)
          jobs  = batch.jobs(verb=verbosity-1)
        
        # HADD or CLEAN
        if subcmd in ['hadd','haddclean','clean']:
          cfgname  = sample.jobcfg['config'] # config file
          jobdir   = sample.jobcfg['jobdir'] # job directory
          cfgdir   = sample.jobcfg['cfgdir'] # job configuration directory
          logdir   = sample.jobcfg['logdir'] # job log directory
          outdir   = sample.jobcfg['outdir'] # job output directory
          postfix  = sample.jobcfg['postfix']
          storedir = repkey(storedirformat,ERA=era,CHANNEL=channel_,TAG=tag,SAMPLE=sample.name,
                                           DAS=sample.paths[0].strip('/'),GROUP=sample.group)
          storage  = getstorage(storedir,ensure=True,haddcmd=haddcmd,verb=verbosity)
          outfile  = "%s_%s%s.root"%(sample.name,channel_,tag)
          infiles  = os.path.join(outdir,"*%s_[0-9]*.root"%(postfix))
          cfgfiles = os.path.join(cfgdir,"job*%s_try[0-9]*.*"%(postfix))
          logfiles = os.path.join(logdir,"*%s*.*.log"%(postfix))
          if verbosity>=1:
            print(">>> %sing job output for '%s'"%(subcmd.capitalize(),sample.name))
            print(">>> %-12s = %r"%('cfgname',cfgname))
            print(">>> %-12s = %r"%('jobdir',jobdir))
            print(">>> %-12s = %r"%('cfgdir',cfgdir))
            print(">>> %-12s = %r"%('outdir',outdir))
            print(">>> %-12s = %r"%('storedir',storedir))
            print(">>> %-12s = %s"%('infiles',infiles))
            if subcmd in ['hadd','haddclean']:
              print(">>> %-12s = %r"%('outfile',outfile))
          status = check_sample(sample,CONFIG,reporter,channel=channel_,tag=tag,jobs=jobs,checkqueue=checkqueue,checkevts=checkevts,
                                das=checkdas,checkexpevts=checkexpevts,ncores=ncores,verb=verbosity)
          if not status.mergeable and not force: # only clean or hadd if all jobs were successful
            LOG.warn("Cannot %s job output because %d chunks need to be resubmitted..."%(subcmd,len(status.resubfiles))+
                     " Please use -f or --force to %s anyway.\n"%(subcmd))
            continue
          
          if subcmd in ['hadd','haddclean']:
            haddout = storage.hadd(infiles,outfile,dry=dryrun,verb=cmdverb,maxopenfiles=maxopenfiles)
            # TODO: add option to print out cutflow for outfile
          
          # CLEAN UP
          # TODO: check if hadd was succesful with isvalid
          if cleanup:
            allcfgs = os.path.join(cfgdir,"job*_try[0-9]*.*")
            rmcmds  = [ ]
            if len(glob.glob(allcfgs))>=len(glob.glob(cfgfiles)): # check for other jobs in same directory
              if verbosity>=2:
                print(">>> %-12s = %s"%('cfgfiles',cfgfiles))
              rmcmds.append("rm -r %s"%(jobdir)) # remove whole job directory
              if outdir!=jobdir and len(glob.glob(infiles))>=len(glob.glob(os.path.join(outdir,"*.root"))): # check for other jobs in same directory
                rmcmds.append("rm -r %s"%(outdir)) # remove whole output directory with ROOT output files
            else: # only remove files related to this job (era/channel/sample)
              rmfiles   = [ ]
              rmfileset = [infiles,cfgfiles,logfiles]
              for files in rmfileset:
                if len(glob.glob(files))>0:
                  rmfiles.append(files)
              if verbosity>=2:
                print(">>> %-12s = %s"%('cfgfiles',cfgfiles))
                print(">>> %-12s = %s"%('rmfileset',rmfileset))
              if rmfiles:
                rmcmds.append("rm %s"%(' '.join(rmfiles)))
            for rmcmd in rmcmds:
              if verbosity>=1:
                rmcmd = lreplace(rmcmd,'rm',"rm -v",1)
              execute(rmcmd,dry=dryrun,verb=cmdverb)
        
        # ONLY CHECK STATUS
        else:
          showlogs = args.showlogs # print log files of failed jobs
          cfgname  = sample.jobcfg['config'] # config file
          jobdir   = sample.jobcfg['jobdir']
          outdir   = sample.jobcfg['outdir']
          logdir   = sample.jobcfg['logdir']
          if verbosity>=1:
            print(">>> Checking job status for '%s'"%(sample.name))
            print(">>> %-12s = %r"%('cfgname',cfgname))
            print(">>> %-12s = %r"%('jobdir',jobdir))
            print(">>> %-12s = %r"%('outdir',outdir))
            print(">>> %-12s = %r"%('logdir',logdir))
          check_sample(sample,CONFIG,reporter,channel=channel_,tag=tag,jobs=jobs,showlogs=showlogs,checkqueue=checkqueue,
                       checkevts=checkevts,das=checkdas,ncores=ncores,verb=verbosity)
        
        print('')
      
      if not found:
        print_no_samples(dtypes,filters,vetoes,[channel],jobdir_,jobcfgs)


