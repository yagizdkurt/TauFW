# Author: Izaak Neutelings (May 2020)
# Moved to TauFW.Utilities (CL §50): ensuredir -> FileIO().make_directory, ensurefile -> FileIO().require_file,
# rmfile -> FileIO().remove_file; getline and ensureinit went to their only callers; writetemplate and expandfiles
# (no callers) were deleted. ensuremodule stays here until it is looked at (TODO.md section 2); ensurefile only for it.
from __future__ import print_function # for python3 compatibility
import os
import importlib, traceback
from TauFW.common.tools.log import LOG
basedir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))


def ensurefile(*paths,**kwargs):
  """Ensure file exists.
  If more than one path is given, it is joined into one."""
  fatal = kwargs.get('fatal',True)
  path = os.path.join(*paths)
  if not os.path.isfile(path):
    if fatal:
      raise IOError("Did not find file %s."%(path))
    else:
      print(">>> Warning! Did not find file %s."%(path))
    #path = None
  return path


def ensuremodule(modname,package):
  """Ensure Sample method exists in python/methods.
  E.g. module = ensuremodule(modname,"PicoProducer.analysis")"""
  # TODO: absolute path
  modfile  = ensurefile(basedir,package.replace('.','/python/',1),"%s.py"%(modname.replace('.','/')))
  modpath  = "TauFW.%s.%s"%(package,modname) #modfile.replace('.py','').replace('/','.')
  modclass = modname.split('.')[-1]
  try:
    module = importlib.import_module(modpath)
  except Exception as err:
    print(traceback.format_exc())
    LOG.throw(ImportError,"Importing module '%s' failed. Please check %s! cwd=%r"%(modpath,modfile,os.getcwd()))
  if not hasattr(module,modclass):
    LOG.throw(IOError,"Module '%s' in %s does not have a module named '%s'!"%(module,modfile,modname))
  return module

