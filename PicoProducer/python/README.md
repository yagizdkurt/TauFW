# PicoProducer/python

| Package | Contents |
|---|---|
| [`analysis/`](analysis) | analysis modules run on nanoAOD (event selection, reconstruction) and their tree writers |
| [`batch/`](batch) | batch systems (HTCondor, SLURM, SGE): submit task lists, query the queue; submit templates |
| [`corrections/`](corrections) | corrections: energy scales, weights, scale factors, ... |
| [`datasets/`](datasets) | samples (`MC`, `Data`, `Embedded`) and the catalogs that list them |
| [`jobs/`](jobs) | the job lifecycle: local runs, planning and (re)submitting batch jobs, status checks, merging (hadd) and cleanup |
| [`pico/`](pico) | the command functions behind [`pico.py`](../scripts/pico.py) (thin layers over `jobs/` and `settings/`) |
| [`processors/`](processors) | the workers run by local runs and batch jobs (`picojob.py`, `skimjob.py`) |
| [`settings/`](settings) | the global configuration `config/config.json`: model, defaults and loading |
| [`storage/`](storage) | storage systems (local, EOS, T2/T3 sites): listing, copying, merging; job-output validation |
| [`legacy/`](legacy) | unmaintained code kept for reference, importable as `TauFW.PicoProducer.legacy.*` |

How `pico.py` uses them:
```
pico.py run        -> pico/run.py  -> jobs/local.py     (iter_local_runs -> execute_run)
pico.py submit     -> pico/job.py  -> jobs/pipeline.py  (iter_plans -> submit_plan -> record_submission)
pico.py status     -> pico/job.py  -> jobs/pipeline.py  (iter_submitted) -> jobs/status.py (check_sample)
pico.py hadd/clean -> pico/job.py  -> jobs/pipeline.py  (iter_submitted) -> jobs/merge.py  (merge_sample)
pico.py list/get/set/... -> pico/config.py -> settings/, datasets/
```
