# PicoProducer/python

| Package | Contents |
|---|---|
| [`api/`](api) | the public API: `PicoProducer` (plan, submit, status, resubmit, merge, run_local) and its records; see [docs/PicoProducer/API.md](../../docs/PicoProducer/API.md) |
| [`analysis/`](analysis) | analysis modules run on nanoAOD (event selection, reconstruction) and their tree writers |
| [`batch/`](batch) | batch systems (HTCondor, SLURM, SGE): submit task lists, query the queue; submit templates |
| [`corrections/`](corrections) | corrections: energy scales, weights, scale factors, ... |
| [`datasets/`](datasets) | samples (`MC`, `Data`, `Embedded`) and the catalogs that list them |
| [`jobs/`](jobs) | the job lifecycle: local runs, planning and (re)submitting batch jobs, status checks, merging (hadd) and cleanup |
| [`cli/`](cli) | the command line [`pico.py`](../scripts/pico.py): parser, dispatch, configuration commands, and job commands that call the API |
| [`workers/`](workers) | the workers run by local runs and batch jobs (`picojob.py`, `skimjob.py`, `Bookkeeper`), formerly `processors/` |
| [`processors/`](processors) | **deprecated** compatibility layer: forwards the old `processors` imports and scripts to `workers/` (see its README) |
| [`settings/`](settings) | the global configuration `config/config.json`: model, defaults and loading |
| [`storage/`](storage) | storage systems (local, EOS, T2/T3 sites): listing, copying, merging; job-output validation |
| [`legacy/`](legacy) | unmaintained code kept for reference, importable as `TauFW.PicoProducer.legacy.*` |

How `pico.py` uses them (the job commands go through the same API as any Python caller):
```
pico.py run        -> cli/jobs.py -> api PicoProducer.run_local -> jobs/local.py    (iter_local_runs -> execute_run)
pico.py submit     -> cli/jobs.py -> api PicoProducer.submit    -> jobs/pipeline.py (iter_plans -> submit_plan -> record_submission)
pico.py status     -> cli/jobs.py -> api PicoProducer.status    -> jobs/pipeline.py (iter_submitted) -> jobs/status.py (check_sample)
pico.py hadd/clean -> cli/jobs.py -> api PicoProducer.merge     -> jobs/pipeline.py (iter_submitted) -> jobs/merge.py  (merge_sample)
pico.py list/get/set/... -> cli/config.py -> settings/, datasets/
```
