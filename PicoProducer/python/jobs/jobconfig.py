# Author: Izaak Neutelings (May 2020)
"""Job configuration JSON files: the record of one (re)submission try of a sample.

A job config is written after a successful submission and read back for status, resubmission, hadd and cleanup.
Its keys and their order (JOBCFG_KEYS) are part of the BBB baselines (pico.jobs); do not change them without
a re-lock.

Inputs:  job config fields (writing); a glob pattern of job config files, e.g.
         output/$ERA/$CHANNEL/*/config/jobconfig_$CHANNEL$TAG_try*.json (reading).
Outputs: job config files; one Sample per (name, DAS paths, channel), from its latest (re)submission try.

Public API:
  JOBCFG_KEYS                                        the keys of a job config, in file order
  make_jobcfg(time, **fields)                        -> OrderedDict in file order
  write_jobcfg(jobcfg, cfgname)                      write a job config (JSON, or gzipped JSON for *.json.gz)
  getcfgsamples(jobcfgnames, filter, veto, dtype, verb)
"""

# ===== Imports =====
import glob, json, gzip
from collections import OrderedDict
from TauFW.PicoProducer.datasets.sample import Sample

__all__ = ['JOBCFG_KEYS', 'make_jobcfg', 'write_jobcfg', 'getcfgsamples']


# ===== Constants =====
JOBCFG_KEYS = (
  'time',
  'group',   'paths',   'name',    'nevents',
  'dtype',   'channel', 'module',  'extraopts',
  'jobname', 'jobtag',  'tag',     'postfix',
  'try',     'queue',   'jobids',  'prefetch',
  'outdir',  'jobdir',  'cfgdir',  'logdir',
  'cfgname', 'joblist', 'maxevts',
  'nfiles',  'files',   'nfilesperjob',
  'nchunks', 'chunks',  'chunkdict',
  'filenevts',
)


# ===== Writing =====

def make_jobcfg(time,**fields):
  """Job config with the keys in file order. All keys of JOBCFG_KEYS except 'time' must be given."""
  missing = [k for k in JOBCFG_KEYS[1:] if k not in fields]
  unknown = [k for k in fields if k not in JOBCFG_KEYS]
  assert not missing and not unknown, "make_jobcfg: missing keys %s, unknown keys %s"%(missing,unknown)
  return OrderedDict([('time',time)]+[(k,fields[k]) for k in JOBCFG_KEYS[1:]])


def write_jobcfg(jobcfg,cfgname):
  """Write a job config to cfgname (overwrites)."""
  if cfgname.endswith(".json.gz"):
    with gzip.open(cfgname,'wt') as file: # BUGS P03: gzip was not imported, and json.dump was misused
      json.dump(jobcfg,file,indent=2)
  else:
    with open(cfgname,'w') as file:
      json.dump(jobcfg,file,indent=2)


# ===== Reading =====

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

