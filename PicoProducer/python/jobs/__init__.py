"""Production jobs: how input files are split into job chunks and how job configs are read back.

Session 4 of the cleanup moves the rest of the job lifecycle (planning, status, merging) here.

Public API:
  evtsplitexp, chunkify_by_evts   event-based chunking of input files
  getcfgsamples                   samples (with job state) from job config JSON files
"""
from TauFW.PicoProducer.jobs.chunking import evtsplitexp, chunkify_by_evts
from TauFW.PicoProducer.jobs.jobconfig import getcfgsamples

__all__ = ['evtsplitexp', 'chunkify_by_evts', 'getcfgsamples']
