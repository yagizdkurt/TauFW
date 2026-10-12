# Author: Yagizhan Dinckurt (October 2026)
"""What to produce: the settings of one (re)submission, status check or merge, in one record.

pico.py fills a JobRequest from its command-line arguments; the job functions read only this record (and the
configuration), never the argparse namespace. Part 5 exposes the same record in the public API.

Inputs:  values from the caller (pico.py arguments, or a Python caller).
Outputs: JobRequest.

List-valued fields stay lists (not tuples): the sample selection functions test `isinstance(x, list)`, and
verbose output prints them as lists.

Public API:
  JobRequest            the record
  JobRequest.from_args  build it from a pico.py argparse namespace
"""

# ===== Imports =====
from dataclasses import dataclass, field
from typing import List, Optional

__all__ = ['JobRequest']


# ===== Record =====

@dataclass(frozen=True)
class JobRequest:
  """Settings of one job operation. Defaults are the pico.py defaults."""

  # What: eras, channels and sample selection
  eras:         List[str] = field(default_factory=list)
  channels:     List[str] = field(default_factory=list)
  tag:          str       = ""             # extra tag for job and output names, starts with '_'
  dtypes:       List[str] = field(default_factory=list) # only these sample types ('data','mc','embed')
  samples:      List[str] = field(default_factory=list) # only samples matching these glob patterns
  vetoes:       List[str] = field(default_factory=list) # exclude samples matching these glob patterns
  dasfilters:   List[str] = field(default_factory=list) # only these DAS paths (glob patterns)
  dasvetoes:    List[str] = field(default_factory=list) # exclude these DAS paths (glob patterns)

  # How: module options and job splitting
  extraopts:    List[str] = field(default_factory=list) # extra KEY=VALUE options for the module
  prefetch:     bool      = False          # copy input files to the worker first
  preselect:    Optional[str] = None       # preselection string for skims
  nfilesperjob: int       = -1             # files per job (<=0: sample, then configuration)
  maxevts:      Optional[int] = None       # events per job; split by events if >1 (None: sample/configuration)
  split_nfpj:   int       = 1              # divide nfilesperjob by this factor (resubmission of failed chunks)
  testrun:      int       = 0              # test jobs: at most 2 samples, 4 files, 4 chunks, this many events
  tmpdir:       Optional[str] = None       # skims: local directory for the output before copying
  dasfiles:     bool      = False          # take input files from DAS instead of local storage

  # Batch system
  resubmit:     bool      = False          # resubmit failed/missing chunks of existing job configs
  queue:        Optional[str] = None       # queue (job flavour for HTCondor)
  time:         Optional[str] = None       # maximum run time
  batchopts:    Optional[str] = None       # extra options for the batch system
  force:        bool      = False          # submit even if a job config exists
  dryrun:       bool      = False          # prepare everything but do not submit

  # Status checks
  checkdas:     bool      = False          # compare processed events to the number of events in DAS
  checkqueue:   int       = -1             # 0: no queue check, 1: check once, -1: check per sample
  checkevts:    bool      = True           # validate output files and count events
  checkexpevts: Optional[bool] = None      # compare processed to expected events (None: analysis jobs only)
  ncores:       int       = 4              # validate output files in parallel
  verbosity:    int       = 0

  # ===== Construction =====

  @classmethod
  def from_args(cls,args,**overrides):
    """Build from a pico.py argparse namespace. Fields the subcommand does not define keep their defaults."""
    values = { }
    for name in cls.__dataclass_fields__:
      if name=='samples' and hasattr(args,'samples'):
        values[name] = args.samples
      elif name=='resubmit':
        values[name] = getattr(args,'subcommand',None)=='resubmit'
      elif hasattr(args,name):
        values[name] = getattr(args,name)
    values.update(overrides)
    return cls(**values)

