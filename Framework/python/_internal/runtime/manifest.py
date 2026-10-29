# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Stage manifests: <run_dir>/stages/<id>/manifest.json, written when a stage is DONE.

    {"manifest": 2, "run_id": "...", "stage_id": "shapes", "stage": "shapes", "description": "...",
     "inputs": {...}, "sources": {...}, "stage_dir": "/abs/.../stages/shapes", "finished": "...",
     "bundle_changed": false, "artifacts": [...]}

A manifest is a copy of the stage's record in run.json (run.json stays the source of truth), so that the directory
describes itself: which stage of which run made it, from which inputs, and what it holds. Only a DONE stage has one.
It is also the contract for an input that names this directory from another run ({path: <stage directory>} in a
recipe): the reader takes the artifacts from the manifest and never reads the other run's run.json.

    stage_dir:  where the manifest was written (absolute). Its artifacts name files there, so a directory that was
                moved or copied (stage_dir is not where it is read) is refused: its artifacts would name the files
                of the old place.
    sources:    the inputs read from other runs' stage directories: slot -> StageDir.summary() of the source.
    bundle_changed: true if the run's bundle copy had been changed (since the run started) when this stage ran
                (CL §44; see run.json bundle.changed). Manifests written before CL §44 do not have it.

Format 2 (R4, CL §17). A manifest of another format is refused (there is no conversion).

Inputs:  a DONE stage's record (write); a stage directory (read).
Outputs: manifest.json (write); a StageDir (read).

Public API:
  write_manifest(files, directory, run_id, stage_spec, sources, artifacts, finished, bundle_changed)
  read_stage_dir(path) -> StageDir     raises ManifestError
  StageDir, ManifestError, MANIFEST_FORMAT
"""
import hashlib
import json
import os
from dataclasses import dataclass
from typing import Tuple

from TauFW.Framework.defaults import MANIFEST_NAME

__all__ = ['write_manifest', 'read_stage_dir', 'StageDir', 'ManifestError', 'MANIFEST_FORMAT']


# =============================================================================
# ================================= CONSTANTS =================================


MANIFEST_FORMAT = 2  # version of the manifest.json layout
KEYS = ('manifest', 'run_id', 'stage_id', 'stage', 'stage_dir', 'finished', 'artifacts')  # what a reader needs


# =============================================================================
# ================================== RECORDS ==================================


@dataclass(frozen=True)
class StageDir:
    """A finished stage directory, as its manifest describes it.
    path: the directory as given (absolute); sha256: of the manifest file, so a later change of it is seen."""
    path:      str
    run_id:    str
    stage_id:  str
    stage:     str
    finished:  str
    artifacts: Tuple[dict, ...]
    sha256:    str

    def summary(self):
        """What a reader records about its source (run.json `sources`, the reader's manifest)."""
        return {'path': self.path, 'run_id': self.run_id, 'stage_id': self.stage_id, 'stage': self.stage,
                'finished': self.finished, 'manifest_sha256': self.sha256}


class ManifestError(ValueError):
    """A directory that cannot be read as a finished stage directory; the message says why."""


# =============================================================================
# ================================= PIPELINES =================================


def write_manifest(files, directory, run_id, stage_spec, sources, artifacts, finished, bundle_changed=False):
    """Write <directory>/manifest.json of a DONE stage (format 2). directory: the stage's output directory
    (made if needed); stage_spec: its StageSpec; sources: slot -> StageDir.summary() of the inputs read from other
    runs ({} if none); bundle_changed: the run's bundle copy was changed before the stage ran (run.json
    bundle.changed, CL §44). files: a TauFW.Utilities FileIO."""
    files.make_directory(directory)
    files.write_json(os.path.join(directory, MANIFEST_NAME), {
        'manifest': MANIFEST_FORMAT, 'run_id': run_id, 'stage_id': stage_spec.id, 'stage': stage_spec.stage,
        'description': stage_spec.description, 'inputs': stage_spec.inputs, 'sources': sources,
        'stage_dir': os.path.abspath(directory), 'finished': finished, 'bundle_changed': bool(bundle_changed),
        'artifacts': artifacts}, overwrite=True)


def read_stage_dir(path):
    """The StageDir of a finished stage directory (an absolute path). Raises ManifestError if the directory does
    not exist, has no manifest (the stage has not finished), its manifest cannot be read or has another format, or
    the directory was moved or copied (the manifest was written somewhere else)."""
    if not os.path.isdir(path):
        raise ManifestError("no such directory: %s" % (path))
    manifest = os.path.join(path, MANIFEST_NAME)
    if not os.path.isfile(manifest):
        raise ManifestError("%s has no %s: its stage has not finished, or it is not the stage directory of a TauFW "
                            "run (<run_dir>/stages/<id>)" % (path, MANIFEST_NAME))
    try:
        with open(manifest, 'rb') as stream:
            raw = stream.read()
        data = json.loads(raw.decode('utf-8'))
    except (OSError, ValueError) as error:
        raise ManifestError("cannot read %s: %s" % (manifest, error))
    if not isinstance(data, dict) or data.get('manifest') != MANIFEST_FORMAT:
        found = data.get('manifest') if isinstance(data, dict) else None
        raise ManifestError("%s has manifest format %r, expected %d (written before R4; start a new run of that "
                            "stage)" % (manifest, found, MANIFEST_FORMAT))
    missing = [key for key in KEYS if key not in data]
    if missing:
        raise ManifestError("%s: missing %s" % (manifest, ', '.join(missing)))
    if not _same_place(path, data['stage_dir']):
        raise ManifestError("%s was moved or copied from %s: its artifacts name the files there"
                            % (path, data['stage_dir']))
    return StageDir(path=path, run_id=data['run_id'], stage_id=data['stage_id'], stage=data['stage'],
                    finished=data['finished'], artifacts=tuple(data['artifacts'] or ()),
                    sha256=hashlib.sha256(raw).hexdigest())


# =============================================================================
# ================================== HELPERS ==================================


def _same_place(path, stage_dir):
    """True if both name the same directory (links resolved)."""
    return os.path.normcase(os.path.realpath(path)) == os.path.normcase(os.path.realpath(stage_dir))
