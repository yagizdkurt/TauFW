# -*- coding: utf-8 -*-
# Author: Izaak Neutelings (2017)
# Moved from TauFW.Plotter.plot.string by Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Selection and weight expressions of ROOT (TTree::Draw, RDataFrame Filter/Define): join cuts with '&&', multiply
weights, replace weight factors, clean doubled boolean operators.

Moved verbatim from TauFW.Plotter.plot.string; the helpers that know pico branch names (shift, shiftjme,
invertcharge, ...) stayed there, and the Plotter imports these names from here. Plain string functions: ROOT is not
imported. LOG is the drawing library's logger, the same object as before for every caller.
"""
import re
from TauFW.Utilities.Drawing import LOG


def getselstr(string,**kwargs):
  """Make sure returned object is a string."""
  if hasattr(string,"selection"): #isinstance(selection,Selection):
    return string.selection
  return string
  


def joinweights(*wargs,**kwargs):
  """Join weight strings multiplicatively."""
  verbosity = LOG.getverbosity(kwargs)
  weights   = [ ] # filtered list of weights (ignore empty strings)
  for weight in wargs:
    if weight and isinstance(weight,str): # strings
      weights.append(weight)
    elif isinstance(weight,(int,float)): # numbers
      if weight!=1: # ignore 1 as it should not contribute
        weights.append(str(weight)) # convert to string
      if weight==0 and len(wargs)>=1:
        LOG.warn("joinweights: One weight is 0, other weights: %r"%(weight,wargs))
    elif weight: # unrecognized object ?
      LOG.warn("joinweights: Ignoring %r (type %r) because it is not a string or number?"%(weight,type(weight)))
  if weights: # one or more nonzero weights
    totweight = "*".join(weights) # combine weights into one string with multiplication '*'
    totweight = totweight.replace('*/','/')
  else: # empty weight
    totweight = "" # total weight
  return totweight
  

def joincuts(*cuts,**kwargs):
  """Joins selection strings and apply weight if needed."""
  verbosity = LOG.getverbosity(kwargs)
  cuts      = [c for c in cuts if c and isinstance(c,str)]
  weight    = kwargs.get('weight', False)
  if any('||' in c and not ('(' in c and ')' in c) for c in cuts):
    LOG.warn('joincuts: Be careful with those "or" statements in %s! Not sure how to join...'%(cuts,))
    for i, cut in enumerate(cuts):
      if '||' in cut and not ('(' in cut and ')' in cut):
        cuts[i] = "(%s)"%(cut)
  if weight:
    string = re.sub("\(.+\)","",weight)
    if any(c in string for c in '=<>+-&|'):
      weight = "(%s)"%(weight)
  if cuts:
    cuts = " && ".join(cuts)
    if weight:
      string = re.sub("\(.+\)","",cuts)
      cuts   = "(%s)*%s"%(cuts,weight)
  elif weight:
    cuts = weight
  else:
    cuts = ""
  #print cuts
  return cuts
  

def replacepattern(oldstr,patterns):
  """Replace pattern in string of (multiplicative weights).
  E.g: replacepattern("wgt1*wgt2*10",('wgt1','newwgt1')) = "newwgt1*wgt2*10"
  """
  if not patterns:
    return oldstr
  if isinstance(patterns[0],str):
    patterns = [patterns] # ensure list of patterns of the form (str oldpat,str newpat) or (str oldpat,str newpat,bool regexp)
  for patargs in patterns:
    if len(patargs)==3:
      oldpat, newpat, regexp = patargs[:3]
    elif len(patargs)==2:
      oldpat, newpat, regexp = patargs[0], patargs[1], False # default
    else:
      raise IOError("replacepattern: Pattern must be of form (str oldpat,str newpat) or (str oldpat,str newpat,bool regexp)... Got oldstr=%r, patargs=%r"%(oldstr,patargs))
    if regexp: # substitution with regular expression
      newstr = re.sub(oldpat,newpat,oldstr)
    else: # simple substitution
      newstr = oldstr.replace(oldpat,newpat)
    newstr = newstr.replace("**","*").strip('*') # for multiplicative weights
    #LOG.verb('replacepattern: Replacing weight: %r -> %r'%(oldstr,newstr,verbosity,3))
  return newstr
  

doubleboolrexp = re.compile(r"(?:&&|\|\|) *(?:&&|\|\|)")
def cleanbool(string):
  """Clean boolean operators."""
  return doubleboolrexp.sub(r"&&",string).strip(' ').strip('&').strip(' ')
