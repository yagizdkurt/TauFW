# Author: Izaak Neutelings (May 2020)
"""The configuration container returned by settings.getconfig.

Config wraps the ordered dictionary read from config/config.json. Values can be read as attributes
(CONFIG.eras) or items (CONFIG['eras']); write() persists it, optionally with a .bkp backup.

Public API:
  Config(cfgdict, path)    dict-like configuration with load(), write(), get(), pop(), keys(), items()
"""

# ===== Imports =====
import json
from collections import OrderedDict
from TauFW.common.tools.log import Logger

__all__ = ['Config']


# ===== Constants =====
LOG = Logger('GLOB')


# ===== Public API =====

class Config(object):
  
  def __init__(self,cfgdict={ },path="config.json"):
    """Container class for a global configuration."""
    self._dict = cfgdict
    self._path    = path
    for key in list(self._dict.keys()):
      if isinstance(self._dict[key],str):
        self._dict[str(key)] = str(self._dict[key]) # convert unicode to str
      elif isinstance(self._dict[key],dict):
        for subkey in list(self._dict[key].keys()):
          item = self._dict[key][subkey]
          if isinstance(item,str):
            item = str(item)
          self._dict[str(key)].pop(subkey,None)
          self._dict[str(key)][str(subkey)] = item # convert unicode to str
      elif isinstance(key,str):
        self._dict[str(key)] = self._dict[key] # convert unicode to str
  
  def __str__(self):
    return str(self._dict)
  
  def __getattr__(self,key):
    if key in self.__dict__:
      val = self.__dict__[key]
    elif (key.startswith('__') and key.endswith('__')) or key not in self._dict:
      raise AttributeError("Did not find '%s'"%(key))
    else:
      val = self._dict[key]
    return val
  
  def __getitem__(self,key):
    return self._dict[key]
  
  def __setattr__(self,key,val):
    if key in self.__dict__:
      self.__dict__[key] = val
      if key in self._dict[key]:
        self._dict[key] = val
    elif (key.startswith('__') and key.endswith('__')):
      raise AttributeError("Did not find '%s'"%(key))
    elif key.startswith('_'):
      self.__dict__[key] = val
    else:
      self._dict[key] = val # cache
    return val
  
  def __setitem__(self,key,val):
    self._dict[key] = val
    return val
  
  def __iter__(self):
    return iter(self._dict)
  
  def iteritems(self):
    for x in self._dict.items():
      yield x
  
  def items(self):
    for x in self._dict.items():
      yield x
  
  def __len__(self):
    return len(self._dict)
  
  def __contains__(self, item):
    return item in self._dict
  
  def load(self,path=None):
    if path==None:
      path = self._path
    else:
      self._path = path
    with open(path,'r') as infile:
      self._dict = json.load(infile,object_pairs_hook=OrderedDict)
    return self._dict
  
  def keys(self,*args,**kwargs):
    return self._dict.keys(*args,**kwargs)
  
  def get(self,*args,**kwargs):
    return self._dict.get(*args,**kwargs)
  
  def pop(self,*args,**kwargs):
    return self._dict.pop(*args,**kwargs)
  
  def write(self,path=None,backup=False,verb=0):
    if path==None:
      path = self._path
    LOG.verb(">>> Config.write: Writing %r (backup=%r)"%(path,backup),verb,3)
    with open(path,'w') as outfile:
      json.dump(self._dict,outfile,indent=2)
    if backup: # backup to recover if config was reset
      pathbkp = path+'.bkp'
      LOG.verb(">>> Config.write: Making back up in %r"%(pathbkp),verb,2)
      with open(pathbkp,'w') as outfile:
        json.dump(self._dict,outfile,indent=2)
    return path
  
