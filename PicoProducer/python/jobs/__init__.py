"""Production jobs: worker command lines, how input files are split into job chunks, and job configs.

Part 4 of the cleanup moves the rest of the job lifecycle (planning, status, merging) here.

Public API:
  resolve_worker, job_command, run_command   worker (picojob.py/skimjob.py) of a channel and its command line
  WorkerSpec, WorkerOptions                  records used by the command builders
  evtsplitexp, chunkify_by_evts              event-based chunking of input files
  getcfgsamples                              samples (with job state) from job config JSON files
"""
from TauFW.PicoProducer.jobs.worker_command import resolve_worker, job_command, run_command, WorkerSpec, WorkerOptions
from TauFW.PicoProducer.jobs.chunking import evtsplitexp, chunkify_by_evts
from TauFW.PicoProducer.jobs.jobconfig import getcfgsamples

__all__ = ['resolve_worker', 'job_command', 'run_command', 'WorkerSpec', 'WorkerOptions',
           'evtsplitexp', 'chunkify_by_evts', 'getcfgsamples']
