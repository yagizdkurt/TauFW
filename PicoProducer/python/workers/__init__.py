# Author: Izaak Neutelings (May 2020)
import os
from TauFW.PicoProducer import basedir, datadir
from TauFW.Utilities.FIO import FileIO
moddir = os.path.dirname(__file__)
#basedir = os.path.dirname(os.path.dirname(os.path.dirname(moddir)))
#datadir = os.path.join(basedir,'data')


# ===== BACKWARD COMPATIBILITY, CLEANUP =====
# Delete at the migration point (Docs/Develop/Refactor-2025/TODO.md section 8, CL §50). Only for scripts outside the
# repository that import ensuredir from here (or from TauFW.PicoProducer.processors); the workers use
# FileIO().make_directory.
def ensuredir(*paths,**kwargs):
  """The old TauFW.common.tools.file.ensuredir: join the paths, make the directory and return it ('' stays '').
  The old keyword arguments (verb, empty) are ignored."""
  path = os.path.join(*paths)
  return FileIO().make_directory(path) if path else path
