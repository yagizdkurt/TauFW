"""Storage systems: where input NanoAOD and job output live, and how to list, copy, merge and remove files.

Public API:
  getstorage(path, **kwargs)        adapter for a path (Local, EOS, T2_DESY, T2_PSI, T3_PSI, GridKA_NRG)
  StorageSystem, Local              adapter base class and local filesystem
  getnevents, isvalid, itervalid    event counting and job-output validation
  LOG                               shared 'Storage' logger
Sample lists live in TauFW.PicoProducer.datasets; `storage/Sample.py` only re-exports them for old catalogs.
"""
from TauFW.PicoProducer.storage.log import LOG
from TauFW.PicoProducer.storage.base import StorageSystem, Local
from TauFW.PicoProducer.storage.factory import getstorage
from TauFW.PicoProducer.storage.validation import getnevents, isvalid, itervalid, iterevts

__all__ = ['LOG', 'StorageSystem', 'Local', 'getstorage', 'getnevents', 'isvalid', 'itervalid', 'iterevts']
