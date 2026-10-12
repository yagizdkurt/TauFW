"""Batch systems: submit job task lists and query the queue.

Public API:
  getbatch(arg, verb)     adapter for a batch system name (HTCondor, HTCondor_<site>, SLURM, SLURM_UCL)
  SYSTEMS                 registry of available batch systems
  BatchSystem, Job, JobList
Submit templates (the scripts that run one task on a worker node) live in batch/templates/.
"""
from TauFW.PicoProducer.batch.base import BatchSystem, JobList, Job
from TauFW.PicoProducer.batch.factory import SYSTEMS, getbatch

__all__ = ['BatchSystem', 'JobList', 'Job', 'SYSTEMS', 'getbatch']
