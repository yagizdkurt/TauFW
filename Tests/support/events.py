"""Events for the TauFW menu's test screen, written to the file named by $TAUFW_EVENTS.

The protocol of TauFW.Utilities.Process (_events.py): one JSON object per line, {"t": <unix time>, "kind": ...}.
It is repeated here so that Tests/run.py keeps running without the TauFW package (e.g. before `scram b`);
Tests/Framework/test_events.py checks that both sides agree. Without $TAUFW_EVENTS nothing is written, and a
failed write never fails a test run. The kinds:

  suite       name, total                       a runner starts (checks, normal, bbb)
  case_start  id, group, log
  case_end    id, status (PASS/FAIL/SKIP), seconds, exit, log, details (BBB differences)
  summary     name, passed, failed, skipped, interrupted, seconds
  warning     message                           e.g. ~/.local packages shadowing CMSSW
  error       message                           the run could not start (bad selection, no BBB lock, ...)
"""
import json
import os
import time

ENV = "TAUFW_EVENTS"


def emit(kind, **fields):
    path = os.environ.get(ENV)
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as stream:  # closed after every event: AFS shows it only then
            stream.write(json.dumps(dict(fields, t=time.time(), kind=kind), default=str) + "\n")
    except OSError:
        pass


def worker_environment(env):
    """A test worker's environment without the events file: only the runner reports to the screen."""
    env.pop(ENV, None)
    return env
