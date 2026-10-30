# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Run record: the saved state of one run, in taufw_runs/<name>_<YYYYmmdd-HHMMSS>/run.json.

    {"schema": 2, "run_id": "...", "created": "...", "updated": "...",
     "recipe": {...}, "pico_config": {"path": "...", "snapshot": {...}},
     "bundle": {"source": "/.../Analyses/tes_id_2025", "files": ["config_coarse_TT.yml", ...]},
     "stages": [{"name": "production", "state": "WAITING", "attempt": 2, "message": "...",
                 "request": {...}, "sources": {}, "submissions": [...], "last_status": {...}, "artifacts": [...],
                 "history": [{"time": "...", "event": "submitted", "state": "SUBMITTED", "detail": "..."}]}]}

A stage record's "name" is the stage's id. "sources" says which other runs' stage directories the stage read
({path: <dir>} inputs): slot -> {path, run_id, stage_id, stage, finished, manifest_sha256}, written at every step of
the stage (so a DONE or FAILED stage keeps what it read); {} for a stage without such inputs. "bundle" lists the
bundle files copied to <run_dir>/bundle/ when the run started (empty for a run without bundle files).

Retries and bundle changes (CL §44); these keys are only written when they have something to say:
  stage "retries":  one entry per `taufw.py retry` of the stage: {time, attempt (1: the first failed attempt),
                    message (why it failed), archive (where its logs and output were moved, relative to the run
                    directory: logs/<id>/attempt<N>; null: nothing moved, production), bundle_changed (the bundle
                    copy's changes since the start, as in "changed"; null: not known); production also
                    max_tries (the raised limit of tries, CL §48)}
  bundle "sha256":  {relative path: sha256} of the bundle copy when the run started (only with bundle files)
  bundle "changed": one entry per change of the bundle copy that an advance saw (it warns once per change):
                    {time, files: {path: added|changed|removed} since the start, digest (bundle.hashes_digest)}. A
                    run with this key is not clean: its stages did not all read the same bundle. The stages that
                    became DONE after a change say so in their manifest (bundle_changed: true).

The run's own recipe (CL §55, run_recipe.py): "recipe" is the version of <run_dir>/bundle/recipe.yml the stages run
with; an advance that finds the file changed checks it and takes it. These keys are only written when they have
something to say:
  "recipe_changed": one entry per change taken: {time, version (N: a copy is recipes/recipe_<N>.yml; 0 is the
                    start), stages: {id: added|removed|changed|moved}, done: [ids of changed stages that stay DONE
                    with their old options]}
  "removed":        the records of the stages a change removed, as in "stages", each with removed: {time, version,
                    archive (where its logs and output were moved, relative to the run directory; null: none)}. They
                    are not part of the run's state.

Schema 3 (2026-10-17, R4): StageRecord.sources, and manifest format 2 (manifest.py). Schema 2 (2026-10-14):
required stage ids and inputs in the recipe, the run directory with logs/<id>/ and stages/<id>/. Runs of another
schema are refused when loaded (there is no conversion).

The record holds references and summaries only. The real state of the jobs stays with each stage's package (for
production: PicoProducer's job configs), so a lost record can be rebuilt from them.

save() is crash-safe: it writes run.json.tmp first and then renames it to run.json (os.replace). run.json is
therefore always either the old or the new complete file, never a half-written one.

Inputs:  run.json (load), or a recipe (create).
Outputs: run.json in the run directory.

Public API:
  RunRecord.create(recipe, run_root, pico_config, now) / RunRecord.load(run_dir) / record.save()
  RunRecord.state      overall state of the run, a RunState
  RunState             NEW, PAUSED, WAITING, DONE, FAILED, BLOCKED (from the stages); RUNNING (live: run_state)
  StageRecord          one stage's state, attempt, request, sources, submissions, last status, artifacts,
                       history, retries
"""
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import List, Optional
from TauFW.Framework._internal.defaults import RUN_RECORD_NAME, timestamp, default_file_io
from TauFW.Framework.stages.base import StageState

__all__ = ['RunRecord', 'RunState', 'StageRecord', 'RUN_RECORD_NAME', 'SCHEMA']


# =============================================================================
# ================================= CONSTANTS =================================


SCHEMA = 3  # version of the run.json and run directory layout; increase it when the layout changes


# =============================================================================
# ================================== STATES ===================================


class RunState(str, Enum):
    """Overall state of a run, computed from the states of its stages (see RunRecord.state), except RUNNING: an
    advance holds the run's lock now (framework.run_state reads it; never computed from the stages alone).
    It is a str, so it compares equal to the plain strings ('WAITING', ...) and prints as one."""
    NEW     = 'NEW'      # no stage has started
    PAUSED  = 'PAUSED'   # a stage started, none waits, failed or is blocked: advance it again (e.g. after --until)
    RUNNING = 'RUNNING'  # an advance works on it now (live state, framework.run_state)
    WAITING = 'WAITING'  # a stage waits for batch jobs: advance again later
    DONE    = 'DONE'     # every stage is done
    FAILED  = 'FAILED'   # a stage failed
    BLOCKED = 'BLOCKED'  # stopped at a placeholder stage that is not implemented yet

    @property
    def finished(self):
        """True if advancing the run again cannot change it (a FAILED run may still be retried: taufw.py retry,
        CL §44)."""
        return self in (RunState.DONE, RunState.FAILED, RunState.BLOCKED)

    def __str__(self):
        return self.value


# =============================================================================
# ================================== RECORDS ==================================


@dataclass
class StageRecord:
    """The saved state of one stage. `name` is the stage's id; `state` is a StageState value (a plain string, as
    in run.json)."""
    name:        str
    state:       str = 'NEW'
    attempt:     int = 0
    message:     str = ""
    request:     Optional[dict] = None
    sources:     dict = field(default_factory=dict)
    submissions: List[dict] = field(default_factory=list)
    last_status: Optional[dict] = None
    artifacts:   List[dict] = field(default_factory=list)
    history:     List[dict] = field(default_factory=list)
    retries:     List[dict] = field(default_factory=list)

    def log(self, event, detail="", time=None):
        """Add an entry to the stage's history."""
        self.history.append({'time': time or timestamp(), 'event': event, 'state': self.state, 'detail': detail})


@dataclass
class RunRecord:
    """The saved state of a run. run_dir is the directory of run.json (it is not written into the file)."""
    run_id:      str
    created:     str
    updated:     str
    recipe:      dict
    pico_config: dict
    stages:      List[StageRecord]
    schema:      int = SCHEMA
    run_dir:     str = ""
    bundle:      dict = field(default_factory=dict)
    recipe_changed: List[dict] = field(default_factory=list)
    removed:     List[dict] = field(default_factory=list)

    # =========================================================================
    # ================================= STATE =================================

    @property
    def state(self):
        """The overall RunState, computed from the stage states. The first rule that matches wins:
        a stage FAILED -> FAILED; all stages DONE -> DONE; a stage waits for jobs -> WAITING;
        a placeholder stage was reached -> BLOCKED; nothing started -> NEW; otherwise PAUSED (never RUNNING: whether
        an advance works on the run is in its lock, framework.run_state)."""
        states = [s.state for s in self.stages]
        if StageState.FAILED in states:
            return RunState.FAILED
        if all(s == StageState.DONE for s in states):
            return RunState.DONE
        if any(s in (StageState.SUBMITTED, StageState.WAITING) for s in states):
            return RunState.WAITING
        if StageState.NOT_IMPLEMENTED in states:
            return RunState.BLOCKED
        if all(s == StageState.NEW for s in states):
            return RunState.NEW
        return RunState.PAUSED

    def stage(self, name):
        """The StageRecord of a stage id."""
        for stage_record in self.stages:
            if stage_record.name == name:
                return stage_record
        raise KeyError("Run %s has no stage %r" % (self.run_id, name))

    @property
    def path(self):
        """The path of run.json."""
        return os.path.join(self.run_dir, RUN_RECORD_NAME)

    # =========================================================================
    # ============================== PERSISTENCE ==============================

    def save(self, files=None, now=None):
        """Write run.json crash-safely (temporary file, then os.replace) and set the 'updated' time."""
        files = files or default_file_io()
        self.updated = now or timestamp()
        tmpname = self.path + ".tmp"
        files.write_json(tmpname, self.to_dict(), overwrite=True)
        os.replace(tmpname, self.path)
        return self.path

    @classmethod
    def load(cls, run_dir, files=None):
        """Read run.json from a run directory (or from the path of run.json itself)."""
        files = files or default_file_io()
        path = run_dir if run_dir.endswith(RUN_RECORD_NAME) else os.path.join(run_dir, RUN_RECORD_NAME)
        record = cls.from_dict(files.read_json(path))
        record.run_dir = os.path.dirname(os.path.abspath(path))
        return record

    # =========================================================================
    # ============================= CONSTRUCTION ==============================

    @classmethod
    def create(cls, recipe, run_root, pico_config=None, now=None):
        """A new record for a recipe, with one NEW StageRecord per stage.
        The run directory is <run_root>/<name>_<YYYYmmdd-HHMMSS>, with a -2, -3, ... suffix if that directory
        exists already. The directory itself is not created here."""
        now = now or datetime.now()
        run_id = "%s_%s" % (recipe.name, now.strftime("%Y%m%d-%H%M%S"))
        base, i = run_id, 1
        while os.path.exists(os.path.join(run_root, run_id)):
            i += 1
            run_id = "%s-%d" % (base, i)
        stamp = timestamp(now)
        return cls(run_id=run_id, created=stamp, updated=stamp, recipe=recipe.to_dict(),
                   pico_config=pico_config or {'path': recipe.pico_config, 'snapshot': None},
                   stages=[StageRecord(name=s.id) for s in recipe.stages],
                   run_dir=os.path.join(os.path.abspath(run_root), run_id))

    @classmethod
    def from_dict(cls, data):
        if data.get('schema') != SCHEMA:
            raise ValueError("Unsupported run.json schema %r (expected %s)" % (data.get('schema'), SCHEMA))
        stages = [StageRecord(**s) for s in data['stages']]
        return cls(run_id=data['run_id'], created=data['created'], updated=data['updated'], recipe=data['recipe'],
                   pico_config=data['pico_config'], stages=stages, schema=data['schema'],
                   bundle=data.get('bundle') or {}, recipe_changed=data.get('recipe_changed') or [],
                   removed=data.get('removed') or [])

    def to_dict(self):
        data = asdict(self)
        data.pop('run_dir')
        for stage in data['stages']:  # a stage that was never retried is written as before CL §44
            if not stage['retries']:
                stage.pop('retries')
        return {key: data[key] for key in ('schema', 'run_id', 'created', 'updated', 'recipe', 'recipe_changed',
                                           'pico_config', 'bundle', 'stages', 'removed')
                if data[key] or key not in ('recipe_changed', 'removed')}  # a recipe never changed: as before

    def __repr__(self):
        return "<RunRecord %s: %s>" % (self.run_id, self.state)
