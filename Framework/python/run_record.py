# Author: Yagizhan Dinckurt (October 2026)
"""Run record: the persisted state of one run, taufw_runs/<name>_<YYYYmmdd-HHMMSS>/run.json.

    {"schema": 1, "run_id": "...", "created": "...", "updated": "...",
     "recipe": {...}, "pico_config": {"path": "...", "snapshot": {...}},
     "stages": [{"name": "production", "state": "WAITING", "attempt": 2, "message": "...",
                 "request": {...}, "submissions": [...], "last_status": {...}, "artifacts": [...],
                 "history": [{"time": "...", "event": "submitted", "state": "SUBMITTED", "detail": "..."}]}]}

The record holds references and summaries. The source of truth for the jobs stays with each stage's package
(production: PicoProducer's job configs), so a lost record can be rebuilt from them.

save() is crash-safe: it writes run.json.tmp and renames it over run.json (os.replace), so run.json is always
either the old or the new complete file.

Inputs:  run.json (load), or a recipe (create).
Outputs: run.json in the run directory.

Public API:
  RunRecord.create(recipe, run_root, pico_config, now) / RunRecord.load(run_dir) / record.save()
  RunRecord.state      overall state: DONE, FAILED, WAITING, BLOCKED (a placeholder stage), RUNNING, NEW
  StageRecord          one stage's state, attempt, request, submissions, last status, artifacts, history
"""

# ===== Imports =====
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional

__all__ = ['RunRecord', 'StageRecord', 'RUN_RECORD_NAME', 'SCHEMA']


# ===== Constants =====
RUN_RECORD_NAME = "run.json"
SCHEMA          = 1
TIMEFORMAT      = "%Y-%m-%d %H:%M:%S"


# ===== Records =====

@dataclass
class StageRecord:
  """Persisted state of one stage."""
  name:        str
  state:       str = 'NEW'
  attempt:     int = 0
  message:     str = ""
  request:     Optional[dict] = None
  submissions: List[dict] = field(default_factory=list)
  last_status: Optional[dict] = None
  artifacts:   List[dict] = field(default_factory=list)
  history:     List[dict] = field(default_factory=list)

  def log(self,event,detail="",time=None):
    """Append a history entry."""
    self.history.append({'time': time or _now(), 'event': event, 'state': self.state, 'detail': detail})


@dataclass
class RunRecord:
  """Persisted state of a run. run_dir is where run.json lives (not stored in the file)."""
  run_id:      str
  created:     str
  updated:     str
  recipe:      dict
  pico_config: dict
  stages:      List[StageRecord]
  schema:      int = SCHEMA
  run_dir:     str = ""

  # ===== State =====

  @property
  def state(self):
    """Overall state: FAILED (a stage failed), DONE (all done), WAITING (a stage waits for jobs),
    BLOCKED (stopped at a placeholder stage), NEW (nothing started), otherwise RUNNING."""
    states = [s.state for s in self.stages]
    if 'FAILED' in states:
      return 'FAILED'
    if all(s=='DONE' for s in states):
      return 'DONE'
    if any(s in ('SUBMITTED','WAITING') for s in states):
      return 'WAITING'
    if 'NOT_IMPLEMENTED' in states:
      return 'BLOCKED'
    if all(s=='NEW' for s in states):
      return 'NEW'
    return 'RUNNING'

  def stage(self,name):
    """The StageRecord of a stage."""
    for record in self.stages:
      if record.name==name:
        return record
    raise KeyError("Run %s has no stage %r"%(self.run_id,name))

  @property
  def path(self):
    return os.path.join(self.run_dir,RUN_RECORD_NAME)

  # ===== Persistence =====

  def save(self,files=None,now=None):
    """Write run.json atomically (temporary file + os.replace) and update the 'updated' time."""
    files = files or _fileio()
    self.updated = now or _now()
    tmpname = self.path+".tmp"
    files.write_json(tmpname,self.to_dict(),overwrite=True)
    os.replace(tmpname,self.path)
    return self.path

  @classmethod
  def load(cls,run_dir,files=None):
    """Read run.json from a run directory (or the path of run.json itself)."""
    files   = files or _fileio()
    path    = run_dir if run_dir.endswith(RUN_RECORD_NAME) else os.path.join(run_dir,RUN_RECORD_NAME)
    record  = cls.from_dict(files.read_json(path))
    record.run_dir = os.path.dirname(os.path.abspath(path))
    return record

  # ===== Construction =====

  @classmethod
  def create(cls,recipe,run_root,pico_config=None,now=None):
    """A new record for a recipe: one NEW StageRecord per stage. The run directory is
    <run_root>/<name>_<YYYYmmdd-HHMMSS> (with a -2, -3, ... suffix if it exists); it is not created here."""
    now    = now or datetime.now()
    run_id = "%s_%s"%(recipe.name,now.strftime("%Y%m%d-%H%M%S"))
    base, i = run_id, 1
    while os.path.exists(os.path.join(run_root,run_id)):
      i += 1
      run_id = "%s-%d"%(base,i)
    stamp  = now.strftime(TIMEFORMAT)
    return cls(run_id=run_id,created=stamp,updated=stamp,recipe=recipe.to_dict(),
               pico_config=pico_config or {'path': recipe.pico_config,'snapshot': None},
               stages=[StageRecord(name=s.stage) for s in recipe.stages],
               run_dir=os.path.join(os.path.abspath(run_root),run_id))

  @classmethod
  def from_dict(cls,data):
    if data.get('schema')!=SCHEMA:
      raise ValueError("Unsupported run.json schema %r (expected %s)"%(data.get('schema'),SCHEMA))
    stages = [StageRecord(**s) for s in data['stages']]
    return cls(run_id=data['run_id'],created=data['created'],updated=data['updated'],recipe=data['recipe'],
               pico_config=data['pico_config'],stages=stages,schema=data['schema'])

  def to_dict(self):
    data = asdict(self)
    data.pop('run_dir')
    return {key: data[key] for key in ('schema','run_id','created','updated','recipe','pico_config','stages')}

  def __repr__(self):
    return "<RunRecord %s: %s>"%(self.run_id,self.state)


# ===== Helpers =====

def _now():
  return datetime.now().strftime(TIMEFORMAT)


def _fileio():
  from TauFW.Utilities.FIO import FileIO
  return FileIO()
