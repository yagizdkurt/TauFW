# PicoProducer/python/processors (deprecated)

`processors/` was renamed to [`workers/`](../workers) on 2026-10-13 (PicoProducer cleanup Part 5, see
[Docs/Develop/Refactor-2025/Refactor-2025.md](../../../Docs/Develop/Refactor-2025/Refactor-2025.md#a3-processors-renamed-to-workers)). This directory is a
**temporary compatibility layer** so code and job lists from before the rename keep working. It contains no worker
code: everything here forwards to `workers/` and prints a deprecation warning.

**New code must use `workers/`.** Nothing in TauFW uses this directory.

## What still works

| Old usage | Now runs | Warning |
|---|---|---|
| `import TauFW.PicoProducer.processors` | Re-exports `TauFW.PicoProducer.workers` (`moddir`, `ensuredir`, ...) | `FutureWarning` |
| `from TauFW.PicoProducer.processors.Bookkeeper import Bookkeeper` | The same module object as `workers.Bookkeeper` | `FutureWarning` |
| `python3 python/processors/picojob.py <args>` (old job lists) | `python/workers/picojob.py <args>` | stderr line |
| `python3 python/processors/skimjob.py <args>` (old job lists) | `python/workers/skimjob.py <args>` | stderr line |

`moddir` still points to `workers/`, where the `keep_and_drop_*.txt` branch selections are. Those files aren't
duplicated here. A hard-coded path `python/processors/keep_and_drop_*.txt` must be changed to `python/workers/`.

## Files

| File | Role |
|---|---|
| [`__init__.py`](__init__.py) | Package alias: re-exports `workers`, warns on import; defines `OLD`, `NEW` and `deprecated()` for the files below |
| [`Bookkeeper.py`](Bookkeeper.py) | Module alias: puts `workers.Bookkeeper` into `sys.modules` under the old name |
| [`_forward.py`](_forward.py) | Standard-library helper that runs `workers/<script>` as `__main__` with the same arguments |
| [`picojob.py`](picojob.py), [`skimjob.py`](skimjob.py) | Script forwarders for job lists written before the rename |

The script forwarders import `_forward` as a sibling file, not through the package. They work wherever the worker
itself works, even if this package isn't installed in `$CMSSW_BASE/python`. The import aliases need a `scram b`
after updating the checkout, like any new Python package in CMSSW.

## Old job lists

`pico.py resubmit` rebuilds the job list from the job config, so resubmitted jobs use `python/workers/` without
this layer. The forwarders are needed only for:

- jobs that were queued or running when the checkout was updated (the batch script reads the job list at runtime)
- lines of an old `jobarglist*.txt` run by hand
- task files submitted directly with `condor_submit`/`sbatch`, bypassing `pico.py`

## Migrating

```diff
-from TauFW.PicoProducer.processors import moddir
+from TauFW.PicoProducer.workers import moddir
-from TauFW.PicoProducer.processors.Bookkeeper import Bookkeeper
+from TauFW.PicoProducer.workers.Bookkeeper import Bookkeeper
```

To find remaining uses, turn the warnings into errors: `python3 -W error::FutureWarning yourscript.py`.

## Removal

Delete this directory after all job lists from before 2026-10-13 have finished or been resubmitted, and record the
removal in `Docs/Develop/Refactor-2025/Refactor-2025.md`. The tests in
[`Tests/PicoProducer/compat/`](../../../Tests/PicoProducer/compat) go with it.
