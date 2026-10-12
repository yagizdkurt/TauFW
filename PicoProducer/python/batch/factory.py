# Author: Izaak Neutelings (May 2020)
"""Select the batch system adapter by name.

Inputs:  a batch system name (e.g. the 'batch' key of the global configuration).
Outputs: an instance of the registered BatchSystem subclass.

Public API:
  SYSTEMS               registry: batch system name -> class
  getbatch(arg, verb)   adapter instance for a name, a Config, or a dict with a 'batch' key
"""

# ===== Imports =====
from TauFW.PicoProducer.batch.htcondor import HTCondor, HTCondor_CMG, HTCondor_DESY, HTCondor_KIT, HTCondor_NAF
from TauFW.PicoProducer.batch.slurm import SLURM, SLURM_UCL
from TauFW.PicoProducer.batch.sge import SGE

__all__ = ['SYSTEMS', 'getbatch']


# ===== Constants =====
# The class name is also the batch system name in the configuration and selects its submit template.
SYSTEMS = { cls.__name__: cls for cls in (HTCondor, HTCondor_CMG, HTCondor_DESY, HTCondor_KIT, HTCondor_NAF,
                                          SLURM, SLURM_UCL, SGE) }


# ===== Public API =====

def getbatch(arg,verb=0):
  """Get BatchSystem (subclass) instance and check if it exists."""
  if isinstance(arg,str):
    system = arg
  elif hasattr(arg,'batch'):
    system = arg.batch
  elif isinstance(arg,dict) and 'batch' in arg:
    system = arg['batch'] # BUGS S02: was arg[batch] (NameError)
  else:
    raise IOError("Did not recognize argument",arg)
  assert system in SYSTEMS, "Did not find batch system '%s'. Available: %s"%(system,', '.join(SYSTEMS))
  batch   = SYSTEMS[system](verb=verb)
  return batch
  
