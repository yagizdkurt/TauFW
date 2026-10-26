# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Records of the public PicoProducer API: what a caller asks for and what each call returns.

All records are frozen dataclasses with to_dict() / from_dict(), so a caller (e.g. the TauFW Framework) can store
them as JSON and read them back. They are built from the job configs that PicoProducer writes anyway; the job
configs stay the source of truth for the state of the jobs.

  JobRequest        what to produce (eras, channels, samples, splitting, batch and check options); the same record
                    the jobs/ package uses (see jobs/request.py), re-exported here
  JobPlan           plan(): PlannedSample per sample (no files written, nothing submitted)
  Submission        submit()/resubmit(): SubmittedSample per sample
  StageStatus       status(): SampleStatus per sample; `complete` when every sample can be merged
  MergeReport       merge()/clean(): TupleArtifact per merged sample, and the samples that were refused
  LocalResult       run_local(): one worker run and its exit code
  TupleArtifact     one merged pico tuple (kind 'tuples'): path, sample, era, channel, tag, data type, events,
                    sum of weights; the production record of docs/contracts/pico-tuples.md

Public API: the records above.
"""

# ===== Imports =====
from dataclasses import dataclass, fields, asdict
from typing import ClassVar, Optional, Tuple
from TauFW.PicoProducer.jobs.request import JobRequest

__all__ = ['JobRequest', 'PlannedSample', 'JobPlan', 'SubmittedSample', 'Submission', 'SampleStatus', 'StageStatus',
           'TupleArtifact', 'MergeReport', 'LocalResult', 'request_to_dict', 'request_from_dict']


# ===== Record base =====

class _Record(object):
  """to_dict()/from_dict() for the records below (implemented at the bottom of this file).
  _nested maps a field to the record type of its items."""
  _nested: ClassVar[dict] = { }

  def to_dict(self):
    return _to_dict(self)

  @classmethod
  def from_dict(cls,data):
    return _from_dict(cls,data)


# ===== Planning and submission =====

@dataclass(frozen=True)
class PlannedSample(_Record):
  """The planned (re)submission of one sample: names, directories, chunks and the worker commands.
  conflict: a job config of this try already exists (submitting would overwrite it, see JobRequest.force)."""
  era:      str
  channel:  str
  name:     str
  group:    str
  dtype:    str
  paths:    Tuple[str, ...]
  subtry:   int
  jobname:  str
  cfgname:  str
  joblist:  str
  outdir:   str
  nfiles:   int
  nchunks:  int
  nevents:  int
  commands: Tuple[str, ...] = ()
  conflict: bool = False


@dataclass(frozen=True)
class JobPlan(_Record):
  """plan(): one PlannedSample per selected sample, in the order they would be submitted."""
  request: JobRequest
  samples: Tuple[PlannedSample, ...] = ()
  _nested = {'samples': PlannedSample}

  @property
  def nchunks(self):
    return sum(s.nchunks for s in self.samples)

  @property
  def conflicts(self):
    return tuple(s for s in self.samples if s.conflict)


@dataclass(frozen=True)
class SubmittedSample(_Record):
  """One sample of a (re)submission. state: 'submitted', 'dry' (dry run), 'declined' (confirm() said no) or
  'empty' (no chunks to submit). jobid is the batch job (cluster) ID, if submitted."""
  era:     str
  channel: str
  name:    str
  cfgname: str
  subtry:  int
  nchunks: int
  state:   str
  jobid:   Optional[int] = None


@dataclass(frozen=True)
class Submission(_Record):
  """submit()/resubmit(): one SubmittedSample per planned sample (skipped samples are not listed)."""
  samples: Tuple[SubmittedSample, ...] = ()
  _nested = {'samples': SubmittedSample}

  @property
  def jobids(self):
    return tuple(s.jobid for s in self.samples if s.jobid is not None)

  @property
  def nsubmitted(self):
    return sum(1 for s in self.samples if s.state=='submitted')


# ===== Status =====

@dataclass(frozen=True)
class SampleStatus(_Record):
  """Chunk states of a sample's last try. complete: nothing pending and nothing to resubmit (can be merged)."""
  era:         str
  channel:     str
  name:        str
  group:       str
  dtype:       str
  cfgname:     str
  subtry:      int
  nchunks:     int
  good:        Tuple[int, ...] = ()
  pending:     Tuple[int, ...] = ()
  failed:      Tuple[int, ...] = ()
  missing:     Tuple[int, ...] = ()
  nprocevents: int = 0
  nexpected:   int = 0
  complete:    bool = False


@dataclass(frozen=True)
class StageStatus(_Record):
  """status(): one SampleStatus per sample with a job config."""
  samples: Tuple[SampleStatus, ...] = ()
  _nested = {'samples': SampleStatus}

  @property
  def complete(self):
    """Every sample can be merged (and there is at least one)."""
    return bool(self.samples) and all(s.complete for s in self.samples)

  @property
  def npending(self):
    return sum(len(s.pending) for s in self.samples)

  @property
  def nfailed(self):
    """Chunks to resubmit: failed (corrupt output) and missing."""
    return sum(len(s.failed)+len(s.missing) for s in self.samples)


# ===== Merging and local runs =====

@dataclass(frozen=True)
class TupleArtifact(_Record):
  """One merged pico tuple: the production record of docs/contracts/pico-tuples.md ("Production record").
  nevents: processed events (cutflow bin 1 summed over the job outputs; 0 if not counted).
  sumw:    cutflow bin 17 of the merged file (MC: sum of genWeight with nTrueInt>0, the normalisation; data: the
           events with a primary vertex); None if it could not be read.
  kind:    'tuples', what the readers select by (the Framework's input slots, ctx.input(..., kind='tuples'))."""
  path:    str
  sample:  str
  group:   str
  era:     str
  channel: str
  tag:     str
  dtype:   str
  nevents: float = 0
  sumw:    Optional[float] = None
  tree:    str = "tree"
  cutflow: str = "cutflow"
  kind:    str = "tuples"


@dataclass(frozen=True)
class MergeReport(_Record):
  """merge()/clean(): artifacts of the merged samples; refused: samples with chunks still to (re)submit;
  invalid: (sample, reason) for merged tuples that failed validation (their job output was kept)."""
  artifacts: Tuple[TupleArtifact, ...] = ()
  refused:   Tuple[str, ...] = ()
  invalid:   Tuple[Tuple[str, str], ...] = ()
  cleaned:   Tuple[str, ...] = ()
  _nested = {'artifacts': TupleArtifact}


@dataclass(frozen=True)
class LocalResult(_Record):
  """run_local(): one worker run. sample is None for runs on user input files; exitcode is 0 in a dry run."""
  era:      str
  channel:  str
  sample:   Optional[str]
  command:  str
  exitcode: int = 0


# ===== Serialization =====

def request_to_dict(request):
  """JobRequest -> dict."""
  return asdict(request)


def request_from_dict(data):
  """dict -> JobRequest; unknown keys are an error."""
  known   = {f.name for f in fields(JobRequest)}
  unknown = sorted(set(data)-known)
  if unknown:
    raise KeyError("Unknown JobRequest fields: %s"%(', '.join(unknown)))
  return JobRequest(**{k: (list(v) if isinstance(v,tuple) else v) for k, v in data.items()})


def _to_dict(record):
  """Plain dict (lists for tuples), ready for JSON; a JobRequest field becomes a dict."""
  return asdict(record)


def _from_dict(cls,data):
  """Rebuild a record from to_dict() output: lists become tuples, nested records and the request are rebuilt."""
  values = { }
  for f in fields(cls):
    if f.name not in data:
      continue
    value = data[f.name]
    if f.name in cls._nested:
      value = tuple(_from_dict(cls._nested[f.name],v) for v in value)
    elif f.name=='request':
      value = request_from_dict(value)
    elif isinstance(value,list):
      value = tuple(tuple(v) if isinstance(v,list) else v for v in value)
    values[f.name] = value
  return cls(**values)
