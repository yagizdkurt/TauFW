# Author: Izaak Neutelings (May 2020)
"""Read job configuration JSON files back into samples (for status, resubmission, hadd and cleanup).

Inputs:  a glob pattern of job config files, e.g. output/$ERA/$CHANNEL/*/config/jobconfig_$CHANNEL$TAG_try*.json
Outputs: one Sample per (name, DAS paths, channel), from its latest (re)submission try.

Public API:
  getcfgsamples(jobcfgnames, filter, veto, dtype, verb)
"""

# ===== Imports =====
import glob
from TauFW.PicoProducer.datasets.sample import Sample

__all__ = ['getcfgsamples']


# ===== Public API =====

def getcfgsamples(jobcfgnames,filter=[ ],veto=[ ],dtype=[ ],verb=0):
  """Help function to get samples from a job configuration file.
  Return list of Sample objects."""
  filters = filter if isinstance(filter,list) else [filter]
  vetoes  = veto   if isinstance(veto,list)   else [veto]
  dtypes  = dtype  if isinstance(dtype,list)  else [dtype]
  jobcfgs = glob.glob(jobcfgnames)
  
  samples = [ ]
  if verb>=2:
    if jobcfgs:
      print(">>> getcfgsamples: Found job config:")
    else:
      print(">>> getcfgsamples: Found NO job configs %s"%(jobcfgnames))
  for cfgname in sorted(jobcfgs):
    if verb>=2:
      print(">>>   %s"%(cfgname))
    sample = Sample.loadjson(cfgname)
    if filters and not sample.match(filters,verb): continue
    if vetoes and sample.match(vetoes,verb): continue
    if sample.dtype not in dtypes: continue
    for i, osample in enumerate(samples):
      if sample.name!=osample.name: continue
      if sample.paths!=osample.paths: continue
      if sample.channels[0] not in osample.channels: continue
      if sample.subtry>osample.subtry: # ensure last job (re)submission
        #TODO: compare sample.jobcfg['config'] and osample.jobcfg['config'] to avoid mixing different jobs
        samples[samples.index(osample)] = sample # replace
      break
    else: # if no break
      samples.append(sample)
  return samples
  
