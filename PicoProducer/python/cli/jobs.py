# Author: Izaak Neutelings (April 2020)
"""pico.py run / submit / resubmit / status / hadd / haddclean / clean: clients of the public API.

Each command turns its arguments into a JobRequest and calls one PicoProducer method with a ConsoleReporter,
which prints the familiar pico.py output. The only logic kept here is the --prompt dialog (_Prompt).

Public API:
  main_run(args)      run
  main_submit(args)   submit, resubmit
  main_status(args)   status, hadd, haddclean, clean
"""

# ===== Imports =====
from TauFW.PicoProducer.api import PicoProducer, JobRequest, ConsoleReporter
from TauFW.PicoProducer.cli.common import CONFIG, LOG


# ===== Commands =====

def main_run(args):
  """Run given module locally."""
  if args.verbosity>=1:
    print(">>> main_run", args)
  _producer().run_local(JobRequest.from_args(args))


def main_submit(args):
  """Submit or resubmit jobs to the batch system."""
  if args.verbosity>=1:
    print(">>> main_submit", args)
  request = JobRequest.from_args(args) # resubmit=True for 'pico.py resubmit'
  prompt  = _Prompt() if args.prompt else None # ask user confirmation
  if args.verbosity>=1:
    print(">>> preparejobs", args)
  _producer().submit(request,on_existing=prompt and prompt.existing,confirm=prompt and prompt.submit)


def main_status(args):
  """Check status of jobs (succesful/pending/failed/missing), or hadd/clean job output."""
  if args.verbosity>=1:
    print(">>> main_status", args)
  request = JobRequest.from_args(args)
  pico    = _producer()
  if args.subcommand=='clean':
    pico.clean(request)
  elif args.subcommand in ['hadd','haddclean']:
    pico.merge(request,clean=getattr(args,'cleanup',False),haddcmd=args.haddcmd,maxopenfiles=args.maxopenfiles,
               action=args.subcommand)
  else:
    pico.status(request,showlogs=args.showlogs)


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

def _producer():
  """The API object of pico.py: the CLI's configuration, terminal output."""
  return PicoProducer(CONFIG,reporter=ConsoleReporter(LOG))
