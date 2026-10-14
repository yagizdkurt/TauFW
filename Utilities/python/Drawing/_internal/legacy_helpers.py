# Author: Izaak Neutelings (May 2020)
# Copied to Utilities by Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Small helpers the drawing code used from TauFW.common.tools.utils and .string, copied verbatim.

Utilities must not import TauFW.common. The functions are byte for byte the old ones, so the drawing code behaves
the same; they are not public API.
"""
# ===== LEGACY, CLEAN UP LATER =====
# Fold into the drawing modules when they are restyled (or into Utilities once common/tools/utils.py moves).
import re


def isnumber(obj):
  """Check if object is float or int."""
  return isinstance(obj,(float,int))
  
  

def islist(arg):
  """Check if argument is a list or tuple."""
  return isinstance(arg,(list,tuple))
  
  

def ensurelist(arg,nonzero=False):
  """Ensure argument is a list, if it is not already a tuple or list."""
  if isinstance(arg,set):
    arg = list(arg)
  if not islist(arg):
    arg = [ ] if (nonzero and not arg) else [arg]
  elif nonzero:
    arg = [a for a in arg if a]
  return arg
  
  

def unpacklistargs(args):
  """Unpack arguments from function's *args, e.g. 
    unpacklistargs([1,2]) = [1,2]
    unpacklistargs([(1,2)]) = [1,2]
  Works as long as expected args are not lists or tuples.
  """
  if len(args)==1 and islist(args[0]):
    args = args[0]
  if isinstance(args,tuple): # convert tuple to list
    args = list(args)
  return args
  
  

def quotestrs(strings):
  """Make summation of quoted strings."""
  return ", ".join(repr(s) for s in strings if s)
  
  

def repkey(string,**kwargs):
  """Replace keys with '$'."""
  for key, value in sorted(kwargs.items(),key=lambda x: -len(x[0])):
    if '${'+key in string: # BASH variable expansions
      matches = re.findall(r"\$\{%s:(\d*):(\d+)\}"%(key),string)
      for a, b in matches:
        substr = value[int(a or 0):int(b)]
        string = re.sub(r"\$\{%s:%s:%s\}"%(key,a,b),substr,string)
    string = string.replace('$'+key,str(value))
  return string
  
  
