# Author: Izaak Neutelings (May 2020)
"""Read, repair and persist the global configuration in PicoProducer/config/config.json.

Inputs:  config/config.json and its backup config/config.json.bkp (both optional).
Outputs: a cached Config; missing keys are restored from the backup or the defaults.
         Only getconfig(write=True) -- used by pico.py -- creates or rewrites the file; library callers
         (workers, Plotter, scripts) get the repaired values in memory and leave the file untouched.
         If $TAUFW_PICO_CONFIG is set (the TauFW Framework sets it for the scripts of a run), getconfig()
         reads that file instead, never writes it, and raises IOError if it does not exist.

Public API:
  getconfig(verb, refresh, write)   load the configuration once (cached); write=True creates/repairs the file
  loadconfig(path, verb)            load a configuration file without caching or writing (public API, tests)
  setdefaultconfig(verb)            overwrite the configuration file with the defaults
"""

# ===== Imports =====
import os, json
from collections import OrderedDict
from TauFW.PicoProducer import basedir
from TauFW.common.tools.file import ensuredir
from TauFW.common.tools.log import Logger
from TauFW.PicoProducer.settings.defaults import getdefaultconfig
from TauFW.PicoProducer.settings.model import Config

__all__ = ['getconfig', 'loadconfig', 'setdefaultconfig']


# ===== Constants =====
LOG    = Logger('GLOB')
CONFIG = None # cache of the loaded configuration
ENVVAR = 'TAUFW_PICO_CONFIG' # path of a configuration file that replaces config/config.json (read-only)


# ===== Public API =====

def getconfig(verb=0,refresh=False,write=False):
  """Get configuration from JSON file. With write=True, create or repair the file (BUGS P18:
  before, every read could write it, e.g. from a batch worker or Plotter)."""
  global CONFIG
  cfgdefaults = getdefaultconfig(verb=verb)
  if CONFIG and not refresh:
    return CONFIG
  if os.environ.get(ENVVAR): # configuration chosen by the caller (e.g. a TauFW Framework run): read-only
    CONFIG = loadconfig(os.environ[ENVVAR],verb=verb)
    return CONFIG
  
  # SETTING
  cfgdir   = ensuredir(basedir,"config") if write else os.path.join(basedir,"config")
  cfgname  = os.path.join(cfgdir,"config.json")
  bkpname  = os.path.join(cfgdir,"config.json.bkp") # back up to recover config if reset
  cfgdict  = cfgdefaults.copy()
  rqdstrs  = [k for k,v in cfgdefaults.items() if isinstance(v,str)] # required string type
  rqddicts = [k for k,v in cfgdefaults.items() if isinstance(v,dict)] # required dictionary type
  
  # GET CONFIG
  if os.path.isfile(cfgname):
    with open(cfgname,'r') as file:
      cfgdict = json.load(file,object_pairs_hook=OrderedDict)
    nmiss = len([0 for k in cfgdefaults.keys() if k not in cfgdict]) # count missing keys
    if nmiss>=5 and os.path.isfile(bkpname): # recover reset config file
      print(">>> Config file may have been reset. Opening backup %s..."%(bkpname))
      with open(bkpname,'r') as file:
        bkpcfgdict = json.load(file,object_pairs_hook=OrderedDict)
      for key in bkpcfgdict.keys(): # check for missing keys
        if key not in cfgdict:
          LOG.warning("Key '%s' not set in config file %s. Setting to backup %r"%(key,os.path.relpath(cfgname),bkpcfgdict[key]))
          cfgdict[key] = bkpcfgdict[key]
          nmiss += 1
    if nmiss>0:
      for key in cfgdefaults.keys(): # check for missing keys
        if key not in cfgdict:
          LOG.warning("Key '%s' not set in config file %s. Setting to default %r"%(key,os.path.relpath(cfgname),cfgdefaults[key]))
          cfgdict[key] = cfgdefaults[key]
          nmiss += 1
      if write:
        print(">>> Saving updated keys...")
        with open(cfgname,'w') as file:
          json.dump(cfgdict,file,indent=2)
  elif write:
    LOG.color("Config file '%s' does not exist in %s. Creating with defaults..."%(cfgname,cfgdir),c='green')
    with open(cfgname,'w') as file:
      json.dump(cfgdict,file,indent=2)
  else:
    LOG.warning("Config file '%s' does not exist. Using defaults (run pico.py to create it)..."%(cfgname))
  
  # SANITY CHECKS - format of values for required keys
  for key in rqdstrs:
    assert key in cfgdict, "Required key '%s' not found in the configuration file..."%(key)
    assert isinstance(cfgdict[key],str),\
      "Required value for '%s' must be a string or unicode! Instead is of type %s: %r"%(key,type(cfgdict[key]),key)
  for key in rqddicts:
    assert key in cfgdict, "Required key '%s' not found in the configuration file..."%(key)
    assert isinstance(cfgdict[key],dict),\
      "Required value for '%s' must be a dictionary! Instead is of type %s: %r"%(key,type(cfgdict[key]),cfgdict[key])
  
  # RETURN
  if verb>=1:
    print('-'*80)
    print(">>> Reading config JSON file '%s'"%cfgname)
    for key, value in cfgdict.items():
      print(">>> %-13s = %s"%(key,value))
    print('-'*80)
  
  CONFIG = Config(cfgdict,cfgname)
  return CONFIG
  

def loadconfig(path=None,verb=0):
  """Load a configuration without caching it and without writing any file.
  path: a JSON file (default: config/config.json); missing keys get their default value, in memory only.
  Raises IOError if an explicitly given path does not exist; without a path and without config/config.json,
  the defaults are used (with a warning), as getconfig() does."""
  cfgdefaults = getdefaultconfig(verb=verb)
  cfgname     = path or os.path.join(basedir,"config","config.json")
  cfgdict     = cfgdefaults.copy()
  if os.path.isfile(cfgname):
    with open(cfgname,'r') as file:
      cfgdict = json.load(file,object_pairs_hook=OrderedDict)
    for key in cfgdefaults.keys(): # missing keys
      if key not in cfgdict:
        if verb>=1:
          LOG.warning("Key '%s' not set in config file %s. Using default %r"%(key,cfgname,cfgdefaults[key]))
        cfgdict[key] = cfgdefaults[key]
  elif path:
    raise IOError("Config file %r does not exist"%(path))
  else:
    LOG.warning("Config file '%s' does not exist. Using defaults (run pico.py to create it)..."%(cfgname))
  for key, value in cfgdefaults.items(): # required types
    if isinstance(value,(str,dict)):
      assert isinstance(cfgdict.get(key),type(value)),        "Required value for '%s' must be of type %s! Instead is %r"%(key,type(value).__name__,cfgdict.get(key))
  return Config(cfgdict,cfgname)


def setdefaultconfig(verb=0):
  """Set configuration to default values."""
  global CONFIG
  cfgdefaults = getdefaultconfig(verb=verb)
  cfgdir  = ensuredir(basedir,"config")
  cfgname = os.path.join(cfgdir,"config.json")
  cfgdict = cfgdefaults.copy()
  if os.path.isfile(cfgname):
    LOG.warning("Config file '%s' already exists. Overwriting with defaults..."%(cfgname))
  CONFIG  = Config(cfgdict,cfgname)
  CONFIG.write(backup=False,verb=verb)
  return CONFIG
  
