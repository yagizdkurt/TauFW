# Author: Izaak Neutelings (April 2020)
"""pico.py run: run a channel's worker locally on a few files (quick checks and tests); a thin command over
jobs/local.py.

Public API:
  main_run(args)
"""

# ===== Imports =====
from TauFW.PicoProducer.jobs.local import iter_local_runs, execute_run
from TauFW.PicoProducer.jobs.reporting import ConsoleReporter
from TauFW.PicoProducer.jobs.request import JobRequest
from TauFW.PicoProducer.pico.common import CONFIG, LOG


# ===== Commands =====

def main_run(args):
  """Run given module locally."""
  if args.verbosity>=1:
    print(">>> main_run", args)
  request  = JobRequest.from_args(args)
  reporter = ConsoleReporter(LOG)
  failed   = [ ]
  for run in iter_local_runs(CONFIG,request,reporter):
    if execute_run(run,reporter,dryrun=request.dryrun):
      failed.append(run)
  if failed: # BUGS P11: worker failures were not reported
    LOG.warn("%d local run(s) failed: %s"%(len(failed),', '.join(r.sample.name if r.sample else r.channel for r in failed)))
