# Framework

The single entry point of TauFW: run an analysis pipeline from a recipe file. The Framework coordinates; each
stage's work stays in its package and is reached through that package's public API.

```
recipe ─▶ plan() ─▶ start() ─▶ advance() ─▶ … ─▶ advance() ─▶ DONE
             │          │            │
          RunPlan   RunRecord     RunRecord (run.json, saved after every stage step)

stages:   production ─▶ histograms ─▶ fit
          (PicoProducer API)  (placeholder)  (placeholder)
```

After `cmsenv` and `scram b`, the package is importable as `TauFW.Framework` and `taufw.py` is on the `PATH`.

## Quick start

```bash
taufw.py plan    Framework/recipes/example_mutau.yml           # each stage's plan; nothing is written
taufw.py plan    Framework/recipes/example_mutau.yml --local   # quick local test: 100 events of one file per sample
taufw.py start   Framework/recipes/example_mutau.yml           # creates taufw_runs/<name>_<time>/, submits the jobs
taufw.py advance taufw_runs/mutau_2022_postEE_20261013-120000  # check; resubmit failed chunks; merge when complete
taufw.py status  taufw_runs/mutau_2022_postEE_20261013-120000  # recorded and live state (read-only)
taufw.py advance taufw_runs/... --wait --poll 900              # keep advancing every 15 minutes until done
```

The same from Python:
```python
from TauFW.Framework import Framework, load_run

fw     = Framework.from_recipe("Framework/recipes/example_mutau.yml")
record = fw.start()                         # RunRecord; record.state == 'WAITING'
# ... later, maybe in another session:
record = load_run(record.run_dir)
record = Framework.from_record(record).advance(record)
print(record.state, record.stage('production').artifacts)
```

## Run model

The run is **stepwise**. `start` and `advance` move the run as far as they can, save `run.json` and return; they
never sleep unless asked with `--wait`. One `advance`:

1. goes through the stages in recipe order, skipping the ones that are `DONE`;
2. lets the current stage take steps until it waits for the batch system, fails, or finishes (then the next stage
   starts in the same call);
3. saves `run.json` after every step, and appends messages to `run.log`.

The production stage:

| State | `advance` does | Next state |
|---|---|---|
| `NEW` | plan the jobs (fail if no sample matches), submit them | `SUBMITTED` (attempt 1) |
| `SUBMITTED`, `WAITING` | check the jobs (`PicoProducer.status`), then decide (`decide_next`): | |
| | all chunks succeeded | `MERGING` |
| | chunks pending or running | `WAITING` |
| | chunks failed or missing, attempt < `max_tries` | resubmit them: `SUBMITTED` (attempt + 1) |
| | chunks failed or missing, attempt = `max_tries` | `FAILED` |
| `MERGING` | merge (`hadd`) each sample into one tuple; with `merge.clean`, remove the job files after the merged tuple is validated | `DONE`, with one artifact per sample |

Placeholder stages (`histograms`, `fit`) report `NOT_IMPLEMENTED`; the run then stops in state `BLOCKED`, and the
earlier stages keep their results.

Run states: `NEW`, `RUNNING`, `WAITING` (a stage waits for jobs), `DONE`, `FAILED` (a stage failed), `BLOCKED` (stopped
at a placeholder stage). `taufw.py` exits with 1 if the run failed.

If a stage raises an error (for example, the batch system cannot be reached), the error is recorded in the stage's
history, the state is unchanged, and the command fails; run `advance` again when the problem is solved.

## Recipe reference

A recipe is a YAML file (JSON is accepted too). Unknown keys are errors that name the key.

```yaml
name: mutau_2022_postEE         # letters, digits, '_', '.', '-'; the run directory is <name>_<YYYYmmdd-HHMMSS>
pico:
  config: null                  # PicoProducer configuration; null: PicoProducer/config/config.json
                                # (a relative path is relative to the recipe file)
stages:                         # in the order production, histograms, fit; each at most once
  - stage: production
    ...
```

### `production`

| Option | Default | Meaning |
|---|---|---|
| `eras`, `channels` | required | eras and channels as defined in the PicoProducer configuration |
| `samples`, `vetoes` | `[]` | glob patterns of sample names to include / exclude |
| `dtypes` | `[mc, data, embed]` | sample types |
| `dasfilters`, `dasvetoes` | `[]` | glob patterns of DAS paths |
| `tag` | `""` | extra tag in job and output names (a leading `_` is added) |
| `extraopts` | `[]` | `KEY=VALUE` module options; precedence: channel table < sample < these |
| `split.nfilesperjob`, `split.maxevts` | `null` | files or events per job (`null`: sample, then configuration) |
| `queue`, `time`, `batchopts` | `null` | batch queue (HTCondor job flavour), maximum run time, extra batch options |
| `prefetch`, `preselect`, `dasfiles` | `false`, `null`, `false` | copy inputs first; skim preselection; take files from DAS |
| `checkdas`, `checkevts`, `checkexpevts`, `ncores` | `false`, `true`, `null`, `4` | status checks: DAS event count, validate outputs, compare to expected events, parallel validation |
| `max_tries` | `3` | submissions (first + resubmissions) before failed chunks fail the stage |
| `merge.clean` | `false` | remove the job files and job output after a validated merge |
| `merge.force` | `false` | merge samples with failed or missing chunks too |
| `verbosity` | `0` | PicoProducer verbosity |

### `histograms`, `fit` (placeholders)

Accepted so that recipes can describe the whole analysis; they report `NOT_IMPLEMENTED` until the Plotter and the
Fitter have public APIs. Declared options: `histograms`: `variables`, `selections`, `outfile`, `method`;
`fit`: `observable`, `model`, `pois`. Their contracts (inputs, outputs) are documented in `python/stages/`.

## Run directory

```
taufw_runs/<name>_<YYYYmmdd-HHMMSS>/
  run.json    the run record (below)
  run.log     plain-text copy of the messages of every start/advance
```

`run.json` (schema 1):
```json
{"schema": 1, "run_id": "...", "created": "...", "updated": "...",
 "recipe": {"name": "...", "pico": {"config": null}, "stages": [...]},
 "pico_config": {"path": ".../config/config.json", "snapshot": {...}},
 "stages": [{"name": "production", "state": "WAITING", "attempt": 2, "message": "...",
             "request": {...}, "submissions": [...], "last_status": {...}, "artifacts": [...],
             "history": [{"time": "...", "event": "resubmitted", "state": "SUBMITTED", "detail": "..."}]}]}
```
- A run always continues with the recipe stored in `run.json`, not with the current recipe file.
- `run.json` is written to a temporary file and renamed, so it is never half written.
- The production stage's source of truth stays with PicoProducer (its job configs under `PicoProducer/output/`);
  `run.json` holds the requests, summaries and artifacts.
- Artifacts of the production stage are PicoProducer `TupleArtifact`s: `path`, `sample`, `group`, `era`,
  `channel`, `tag`, `dtype`, `nevents`, `tree`, `cutflow`.

## Package layout

| File | Contents |
|---|---|
| `python/framework.py` | `Framework`: `plan`, `start`, `advance`, `run`, `status`; stage dispatch; construction (`from_recipe`, `from_record`) |
| `python/recipe.py` | `Recipe`, `StageSpec`, `RecipeError`: load and validate recipes |
| `python/run_record.py` | `RunRecord`, `StageRecord`: `run.json`, crash-safe save |
| `python/reporting.py` | `FrameworkReporter` (terminal + `run.log`), `SilentReporter`; adapter for PicoProducer's messages |
| `python/stages/base.py` | the stage contract: `Stage`, `StageState`, `StageOutcome`, `StageNotImplemented` |
| `python/stages/production.py` | `ProductionStage` and the pure `decide_next` policy |
| `python/stages/histograms.py`, `fit.py` | placeholders with declared contracts |
| `scripts/taufw.py` | the command line (no logic: argparse → `Framework`) |
| `recipes/example_mutau.yml` | documented example recipe |

Dependencies point one way: `Framework → PicoProducer.api` (later also Plotter/Fitter APIs). No other package
imports the Framework. The Framework imports PicoProducer only when a production stage is built, so recipes,
run records and the stage logic can be tested without ROOT.

## Tests

- `python -m unittest discover -s Tests/Framework` (any Python 3.9+, no ROOT): the state machine with a fake
  PicoProducer (submit, wait, resubmit until `max_tries`, merge, placeholder stages, errors), `decide_next`,
  `run.json` round trip and crash-safe save, recipe validation, and `taufw.py`.
- BBB case `framework.production` (lxplus): `taufw.py plan/start/advance/status` against the fake HTCondor of the
  PicoProducer BBB harness, with a resubmission and a merge; snapshots the normalized `run.json` and the merged tuples.
