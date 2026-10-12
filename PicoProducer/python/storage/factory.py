# Author: Izaak Neutelings (May 2020)
"""Select the storage system adapter for a path.

Inputs:  a directory path (local, EOS, PSI/DESY/GridKA dCache, ...).
Outputs: an instance of the matching StorageSystem subclass (Local if nothing else matches).

Public API:
  getstorage(path, **kwargs)   storage adapter for this path; kwargs are passed to its constructor
"""

# ===== Imports =====
import os
from TauFW.PicoProducer.settings.defaults import host
from TauFW.PicoProducer.storage.log import LOG

__all__ = ['getstorage']


# ===== Public API =====

def getstorage(path,**kwargs):
  """Guess the storage system based on the path."""
  verb = kwargs.get('verb',0)
  if path.startswith('/eos/'):
    from TauFW.PicoProducer.storage.eos import EOS
    storage = EOS(path,**kwargs)
  #elif path.startswith('/castor/'):
  #  storage = Castor(path,**kwargs)
  elif path.startswith('/pnfs/psi.ch/'):
    from TauFW.PicoProducer.storage.t3_psi import T3_PSI
    storage = T3_PSI(path,**kwargs)
  elif path.startswith('/pnfs/desy.de/'):
    from TauFW.PicoProducer.storage.t2_desy import T2_DESY
    storage = T2_DESY(path,**kwargs)
  elif path.startswith("/store/user") and ("etp" in host and "ekp" in host):
    from TauFW.PicoProducer.storage.gridka_nrg import GridKA_NRG
    storage = GridKA_NRG(path,**kwargs)
  elif path.startswith('/pnfs/lcg.cscs.ch/'):
    from TauFW.PicoProducer.storage.t2_psi import T2_PSI
    storage = T2_PSI(path,**kwargs)
  #elif path.startswith('/pnfs/iihe/'):
  #  return T2_IIHE(path,**kwargs)
  else:
    from TauFW.PicoProducer.storage.base import Local
    storage = Local(path,**kwargs)
    if not os.path.exists(path):
      LOG.warning("Could not find storage directory %r. Make sure it exists and is mounted. "%(path)+\
                  "If it is a special system, you need to subclass StorageSystem, see "
                  "https://github.com/cms-tau-pog/TauFW/tree/master/PicoProducer#Storage-system")
  if verb>=2:
    print(">>> storage.utils.getstorage(%r), %r"%(path,storage))
  return storage
  
