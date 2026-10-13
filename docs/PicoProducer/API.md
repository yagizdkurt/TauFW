# PicoProducer public API

`TauFW.PicoProducer.api` runs the production of pico tuples (NanoAOD → analysis tuples) from Python. `pico.py`
uses the same API for its job commands, so the API and the command line behave the same.

```python
from TauFW.PicoProducer.api import PicoProducer, JobRequest, ConsoleReporter

pico    = PicoProducer.from_config(reporter=ConsoleReporter())   # config/config.json; omit reporter for silence
request = JobRequest(eras=['2022_postEE'], channels=['mutau'], samples=['DY*', 'TT*'])

plan = pico.plan(request)                 # JobPlan: what would be submitted; nothing is written
pico.submit(request)                      # Submission: job IDs per sample
status = pico.status(request)             # StageStatus: good/pending/failed/missing chunks per sample
if status.nfailed:
    pico.resubmit(request)                # failed and missing chunks, as a new try
if status.complete:
    report = pico.merge(request, clean=True)    # MergeReport: one TupleArtifact per merged sample
    for tuple_ in report.artifacts:
        print(tuple_.path, tuple_.nevents)
```

## Pipeline

```
JobRequest ─▶ plan() ─▶ submit() ─▶ status() ─┬─▶ resubmit() ─▶ status() ─▶ …
              JobPlan   Submission  StageStatus│
                                               └─▶ merge(clean=True) ─▶ MergeReport ─▶ TupleArtifact per sample
run_local(): a quick local test of a channel on a few files, without the batch system
```

| Method | Returns | Side effects | `pico.py` equivalent |
|---|---|---|---|
| `plan(request)` | `JobPlan` | none: reads sample catalogs, storage listings or DAS; on resubmission the queue and the job output. Samples with an existing job config get `conflict=True` | `submit --dry` without the files |
| `iter_plan(request)` | `PlannedSample`, one at a time | as `plan` | |
| `submit(request, on_existing=None, confirm=None)` | `Submission` | creates the job, config and log directories, the output directory and the job list; submits (not with `request.dryrun`); writes the job config after a successful submission | `submit` |
| `resubmit(request, ...)` | `Submission` | as `submit`, for the failed and missing chunks of each sample's last try | `resubmit` |
| `status(request, showlogs=0)` | `StageStatus` | none: queries the batch queue, lists and validates the job output | `status` |
| `merge(request, clean=False, force=None, haddcmd=None, maxopenfiles=None)` | `MergeReport` | creates the storage directory (`picodir`) and writes the merged tuples; with `clean`, removes the job files and job output after the merged tuple is validated | `hadd` / `haddclean` |
| `clean(request, force=None)` | `MergeReport` | removes the job files and job output | `clean` |
| `run_local(request)` | `(LocalResult, ...)` | runs the workers locally (not with `request.dryrun`); they write to `request.outdir` | `run` |
| `request(**fields)` (static) | `JobRequest` | none; unknown fields raise `KeyError`. Lets callers build requests without importing `jobs/` | |

- `on_existing(cfgname)` is called when a sample's job config already exists and `request.force` is not set: return
  `'yes'` (submit), `'no'` (skip), `'force'` (submit this and all further samples), or `None` (skip with a warning,
  the default).
- `confirm(nchunks) -> bool` is called before each submission.
- `merge` and `clean` refuse samples that still have pending, failed or missing chunks (`MergeReport.refused`),
  unless `force=True` (default: `request.force`).
- With `clean`, the merged tuple must be readable and, with event counting (`request.checkevts`), hold the events of
  the job output; otherwise the job output is kept and the sample is listed in `MergeReport.invalid`.

## Construction

```python
PicoProducer.from_config(config=None, reporter=None, basedir=None)
```
- `config`: `None` (`PicoProducer/config/config.json`), a path to a JSON file, a dict, or a `Config`. The file is
  read with `settings.loadconfig`: missing keys get their defaults in memory, nothing is written and nothing is cached.
- `reporter`: where messages go. `Reporter()` (default) is silent; `ConsoleReporter()` prints what `pico.py` prints.
  Both are in `TauFW.PicoProducer.jobs.reporting`.
- `basedir`: the PicoProducer directory (default: the package's). All relative paths of the configuration
  (`output/$ERA/...`, `samples/`, `python/workers/`) are relative to it.

Construction reads the configuration only. It does not create files and does not change the working directory.

## Records (`api/types.py`)

All records are frozen dataclasses with `to_dict()` and `from_dict()`, so they can be stored as JSON.

| Record | Fields |
|---|---|
| `JobRequest` | what to produce. Selection: `eras`, `channels`, `samples`, `vetoes`, `dtypes`, `dasfilters`, `dasvetoes`, `tag`. Module and splitting: `extraopts`, `prefetch`, `preselect`, `nfilesperjob`, `maxevts`, `split_nfpj`, `testrun`, `tmpdir`, `dasfiles`. Local runs: `outdir`, `infiles`, `nfiles`, `nsamples`. Batch: `queue`, `time`, `batchopts`, `force`, `dryrun`. Checks: `checkdas`, `checkqueue`, `checkevts`, `checkexpevts`, `ncores`, `verbosity`. `request_to_dict`/`request_from_dict` convert it |
| `JobPlan` | `request`, `samples` (`PlannedSample`); `nchunks`, `conflicts` |
| `PlannedSample` | `era`, `channel`, `name`, `group`, `dtype`, `paths`, `subtry`, `jobname`, `cfgname`, `joblist`, `outdir`, `nfiles`, `nchunks`, `nevents`, `commands` (one worker command per chunk), `conflict` |
| `Submission` | `samples` (`SubmittedSample`); `jobids`, `nsubmitted` |
| `SubmittedSample` | `era`, `channel`, `name`, `cfgname`, `subtry`, `nchunks`, `state` (`submitted`, `dry`, `declined`, `empty`), `jobid` |
| `StageStatus` | `samples` (`SampleStatus`); `complete` (every sample can be merged), `npending`, `nfailed` |
| `SampleStatus` | `era`, `channel`, `name`, `group`, `dtype`, `cfgname`, `subtry`, `nchunks`, `good`, `pending`, `failed`, `missing` (chunk numbers), `nprocevents`, `nexpected`, `complete` |
| `MergeReport` | `artifacts` (`TupleArtifact`), `refused` (sample names), `invalid` (`(sample, reason)`), `cleaned` (sample names) |
| `TupleArtifact` | `path`, `sample`, `group`, `era`, `channel`, `tag`, `dtype`, `nevents`, `tree` (`"tree"`), `cutflow` (`"cutflow"`) |
| `LocalResult` | `era`, `channel`, `sample` (or `None` for user files), `command`, `exitcode` |

The job configs (`output/<era>/<channel>/<sample>/config/jobconfig_<channel><tag>_try<N>.json`) remain the record of
every submission; `status`, `resubmit`, `merge` and `clean` read them. The API records are summaries that can be
rebuilt from them.

## Known limitations

- **Working directory.** Methods that touch files change into `basedir` for the duration of the call and restore the
  previous directory afterwards, even on errors (`iter_plan` only while a sample is being planned). The working
  directory is per process, so **the API is not thread-safe**: do not call it from several threads at once. The
  reason is that the configured paths and the paths stored in the job configs are relative to `PicoProducer/`.
  Making them absolute would change every job config (and the `pico.jobs` BBB baselines), so it is left for a later,
  separate step.
- **Messages of lower-level code.** Sample catalogs, storage listings, DAS queries and event counting still print
  some messages directly instead of through the reporter.
- **Workers read the global configuration.** `picojob.py -c CHANNEL` looks up the module in `config/config.json`
  (`getconfig()`, read only). Jobs and local runs always pass `-M MODULE`, so the API's configuration is the one used.
- **Interactive input.** None in the API: the `--prompt` dialog of `pico.py` is implemented in `cli/jobs.py` and
  passed in as `on_existing`/`confirm`.

## Where the code is

| Layer | Modules |
|---|---|
| API | `api/producer.py` (`PicoProducer`), `api/types.py` (records) |
| Job lifecycle | `jobs/pipeline.py` (`iter_plans`, `submit_plan`, `record_submission`, `iter_submitted`), `jobs/planner.py`, `jobs/status.py`, `jobs/merge.py`, `jobs/local.py`, `jobs/worker_command.py`, `jobs/jobconfig.py`, `jobs/chunking.py`, `jobs/reporting.py`, `jobs/request.py` |
| Command line | `scripts/pico.py`, `cli/` (parser, dispatch, `cli/jobs.py` calls the API) |
| Services | `settings/` (configuration), `datasets/` (samples), `storage/`, `batch/`, `workers/` (`picojob.py`, `skimjob.py`) |

See [IO.md](IO.md) for the files each step reads and writes.
