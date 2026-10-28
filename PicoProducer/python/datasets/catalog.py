# Author: Izaak Neutelings (May 2020)
"""Load sample lists ("catalogs") and select samples from them.

Inputs:  the era -> catalog mapping in the global configuration, and catalog modules under
         PicoProducer/samples/ that define a list `samples` of Sample objects.
Outputs: filtered lists of Sample objects.

Public API:
  getsamples(era, channel, tag, dtype, filter, veto, dasfilter, dasveto, moddict, split, verb)
  print_no_samples(dtype, filter, veto, channel, jobdir, jobcfgs)   explain why nothing was selected
"""

# ===== Imports =====
import os, sys, glob
import importlib
from fnmatch import fnmatch
from TauFW.PicoProducer import basedir
from TauFW.common.tools.string import repkey, quotestrs
from TauFW.PicoProducer.settings.store import getconfig
from TauFW.PicoProducer.storage.log import LOG
from TauFW.Utilities.FIO import FileIO

__all__ = ['getsamples', 'print_no_samples']


# ===== Public API =====

def getsamples(era,channel="",tag="",dtype=[],filter=[],veto=[],dasfilter=[],dasveto=[],moddict=None,split=False,verb=0):
  """Help function to get samples from a sample list and filter if needed.
  Pass a dictionary as moddict to reuse imported catalog modules between calls."""
  if moddict is None: # BUGS S14: was a shared mutable default 'moddict={}'
    moddict = { }
  CONFIG   = getconfig(verb=verb)
  if basedir not in sys.path: # catalogs are imported as samples.<...> from PicoProducer/
    sys.path.append(basedir)
  filters  = filter  if not filter  or isinstance(filter,list)  else [filter]
  vetoes   = veto    if not veto    or isinstance(veto,list)    else [veto]
  dasveto  = dasveto if not dasveto or isinstance(dasveto,list) else [dasveto]
  dtypes   = dtype   if not dtype   or isinstance(dtype,list)   else [dtype]
  sampfile = FileIO().require_file(os.path.join("samples",repkey(CONFIG.eras[era],ERA=era,CHANNEL=channel,TAG=tag)))
  samppath = sampfile.replace('.py','').replace('/','.')
  LOG.verb("datasets.catalog.getsamples: sampfile=%r"%(sampfile),verb,1)
  LOG.verb("datasets.catalog.getsamples: samppath=%r"%(samppath),verb,3)
  if samppath not in moddict:
    moddict[samppath] = importlib.import_module(samppath) # cache; save time by loading once
  if not hasattr(moddict[samppath],'samples'):
    LOG.throw(IOError,"Module '%s' must have a list of Sample objects called 'samples'!"%(samppath))
  samplelist = moddict[samppath].samples
  samples    = [ ]
  sampledict = { } # ensure for unique names
  LOG.verb("datasets.catalog.getsamples: samplelist=%r"%(samplelist),verb,3)
  for sample in samplelist:
    if filters and not sample.match(filters,verb=verb): continue
    if vetoes and sample.match(vetoes,verb=verb): continue
    if dtypes and sample.dtype not in dtypes: continue
    if channel and sample.channels and not any(fnmatch(channel,c) for c in sample.channels): continue
    if sample.name in sampledict:
      LOG.throw(IOError,"Sample short names should be unique. Found two samples '%s'!\n\t%s\n\t%s"%(
                        sample.name,','.join(sampledict[sample.name].paths),','.join(sample.paths)))
    if dasfilter or dasveto:
      sample = sample.filterpath(filter=dasfilter,veto=dasveto,copy=True,verb=verb)
      if len(sample.paths)==0: continue
    if (split or 'skim' in channel) and sample.dosplit: # split samples with multiple DAS dataset paths, and submit as separate jobs
      for subsample in sample.split():
        samples.append(subsample) # keep correspondence sample to one sample in DAS
    else:
      samples.append(sample)
    sampledict[sample.name] = sample
  return samples
  

def print_no_samples(dtype=[],filter=[],veto=[],channel=[],jobdir="",jobcfgs=""):
  """Help function to print that no samples were found."""
  if jobdir and not glob.glob(jobdir): #os.path.exists(jobdir):
    print(">>> Job output directory %s does not exist!"%(jobdir))
  elif jobcfgs and not glob.glob(jobcfgs):
    print(">>> Did not find any job config files %s!"%(jobcfgs))
  else:
    string = ">>> Did not find any samples"
    if filter or veto or (dtype and len(dtype)<3):
      strings = [ ]
      if filter:
        strings.append("filter%s %s"%('s' if len(filter)>1 else "",quotestrs(filter)))
      if veto:
        strings.append("veto%s %s"%('es' if len(veto)>1 else "",quotestrs(veto)))
      if dtype and len(dtype)<3:
        strings.append("data type%s %s"%('s' if len(dtype)>1 else "",quotestrs(dtype)))
      if channel:
        strings.append("channel%s %s"%('s' if len(channel)>1 else "",quotestrs(channel)))
      string += " with "+', '.join(strings)
    print(string)
  print('')
  
