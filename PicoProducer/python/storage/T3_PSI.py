# Author: Izaak Neutelings (May 2020)
"""Storage element of the PSI T3 (uberftp/gfal commands when not mounted).

Public API:
  T3_PSI(path, verb, ensure, **kwargs)
"""

# ===== Imports =====
import os
from TauFW.PicoProducer.storage.base import StorageSystem

__all__ = ['T3_PSI']


# ===== Public API =====

class T3_PSI(StorageSystem):
  
  def __init__(self,path,verb=0,ensure=False,**kwargs):
    """T3 SE on PSI."""
    super(T3_PSI,self).__init__(path,verb=verb,ensure=False,**kwargs)
    if not self.mounted: # EOS is mounted on lxplus
      self.lscmd   = 'uberftp -ls'
      self.lsurl   = 'gsiftp://t3se01.psi.ch/'
      self.rmcmd   = 'uberftp -rm'
      self.rmurl   = 'gsiftp://t3se01.psi.ch/'
      self.mkdrcmd = "LD_LIBRARY_PATH='' PYTHONPATH='' gfal-mkdir -p"
      self.mkdrurl = 'gsiftp://t3se01.psi.ch/'
      self.cpcmd   = 'xrdcp -f'
      self.cpurl   = "root://t3dcachedb03.psi.ch/"
    self.fileurl = "root://t3dcachedb03.psi.ch/"
    self.tmpdir  = os.path.join('/scratch/',os.environ.get('USER','TauFW')) # BUGS S05: was os.path(...)
    if ensure:
      self.ensuredir(self.path)
    
    # uberftp -rm  gsiftp://t3se01.psi.ch/pnfs/psi.ch/cms//trivcat/store/user/username/directory
    # gfal-rm -r --force root://t3dcachedb03.psi.ch//pnfs/psi.ch/cms/trivcat/store/username/directory
    # uberftp t3se01.psi.ch 'rm -r /pnfs/psi.ch/cms/trivcat/store/user/username/directory'
  
