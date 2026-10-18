# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
# Framework

The single entry point of TauFW: run an analysis pipeline from an analysis bundle (`Analyses/<name>/`: a recipe,
the config files it uses and its own Python steps). The Framework coordinates; each stage's work stays in its package
and is reached through that package's public API.

```
bundle ─▶ plan() ─▶ start() ─▶ advance() ─▶ … ─▶ advance() ─▶ DONE
             │          │            │
          RunPlan   RunRecord     RunRecord (run.json, saved after every stage step)

stages:   production ──────▶ controlhists ────▶ controlplots ──▶ shapes ──────────▶ fit
          PicoProducer API   Histogrammer API    Plotter API      Fitter API         Fitter API
          batch, stepwise    fillhists.py        draw.py, local   createinputsTES    run_workflow_zmm.sh steps,
                             --hists --no-draw,                   local              local
                             local
          python steps (a Python file of the bundle, step_runner.py, local) may be anywhere in between
```

For bundles, recipe structure, path rules and Python steps, see the [analysis guide](../Analyses/README.md).

After `cmsenv` and `scram b`, the package is importable as `TauFW.Framework` and `taufw.py` is on the `PATH`.

## Concepts

The words below are used everywhere in the code and in this README.

| Term | Meaning | In the code |
|---|---|---|
| **analysis bundle** | A directory `Analyses/<name>/` with `recipe.yml`, the config files the recipe uses and its Python steps; every path is relative to the directory of `recipe.yml`. A stage's path option that names a bundle file uses it instead of the module's config. A run copies the bundle to `<run dir>/bundle/` and reads only that copy. | `bundle.py` |
| **recipe** | A YAML file that says what to run: a name, the PicoProducer configuration and a list of stages with their options. You write it; the Framework checks it before anything runs. | `Recipe` (`recipe.py`) |
| **stage** | One step of the analysis: `production` (NanoAOD → pico tuples), `controlhists` (the histograms of the control plots, in a file), `controlplots` (the control plots drawn from that file), `shapes` (fit input shapes), `fit` (TES + tau ID fit), `python` (a Python file of the bundle). Each stage calls the API of its own package. | `Stage` subclasses (`stages/`) |
| **stage id** | The name of a stage in a run, required for every stage (`id:`): `run.json` records, the stage's directories (`stages/<id>/`, `logs/<id>/`) and upstream artifacts are keyed by it, and `inputs:` refer to it. Unique; letters, digits, `_`, `.`, `-` (not `.` or `..`). Any stage may have any id. | `StageSpec.id` |
| **inputs** | Required for every stage: which earlier stage's output each input slot reads (`inputs: {shapes: shapes}`), or `null` for a stage without slots. A slot is connected to the id of an earlier stage that makes that kind of data; a `tuples` slot may name tuples made outside TauFW (`{external: <pattern>}`); `null` is for old recipes only (the tuples in `$PICODIR`, the shapes already in `Fitter/`). Nothing is connected implicitly. | `Stage.inputs`, `Stage.outputs`, `StageSpec.inputs` |
| **description** | Optional free text of a stage, shown by `plan` and in the menu; nothing depends on it. | `StageSpec.description` |
| **validation** | Every problem of a recipe at once (structure, ids, inputs, order, the files it names), before anything runs: `taufw.py check`, the menu's recipe list (red) and preview. `Recipe.load` raises one `RecipeError` that lists all of them. A **warning** (e.g. no `run_root`) is not a problem: the recipe runs; `check`, `plan`, `start` and the menu preview show it. | `check_recipe` (`validation.py`), `Recipe.parse`, `recipe_warnings` |
| **local stage** | A stage that runs commands on this machine, one after the other, and finishes in one `advance` (`controlhists`, `controlplots`, `shapes`, `fit`: the package's scripts; `python`: the step runner). | `LocalStage` (`stages/local.py`) |
| **stage context** | What a stage may know about its run: the run directory (for its logs), its inputs and the artifacts of those input stages that are `DONE`, the run's PicoProducer config and its bundle copy. | `StageContext` (`stages/base.py`) |
| **preflight** | The check, before a local stage runs, that its environment is ready (`cmsenv`, ROOT, `combine`, configs). A problem leaves the stage `NEW`. | `PreflightError` |
| **spec** | The options of one stage after checking, as a typed, read-only object. For example, `ProductionSpec` holds `eras`, `channels`, `max_tries`, ... | `ProductionSpec`, ... |
| **stage spec** | One entry of the recipe's `stages:` list: the stage type, id, inputs, description and spec. | `StageSpec` (`recipe.py`) |
| **run** | One execution of a recipe. Each run gets its own directory, `<run_root>/<name>_<time>/` (`run_root` from the recipe or `--run-root`, default `taufw_runs/`). | `RunRecord.create` |
| **run record** | The saved state of a run, `run.json`. It is updated after every step, so a run can be continued later, even from another session. | `RunRecord` (`run_record.py`) |
| **stage record** | The part of `run.json` that belongs to one stage: its state, attempt, submissions, last status, artifacts and history. | `StageRecord` |
| **step** | One call of `Stage.advance()`: it moves a stage from one state to the next (for example `NEW` → `SUBMITTED`). | `StageOutcome` |
| **stage state** | Where one stage is: `NEW`, `SUBMITTED`, `WAITING`, `MERGING`, `DONE`, `FAILED`, `NOT_IMPLEMENTED`. | `StageState` (`stages/base.py`) |
| **run state** | Where the whole run is, computed from the stage states: `NEW`, `RUNNING`, `WAITING`, `DONE`, `FAILED`, `BLOCKED`. | `RunState` (`run_record.py`) |
| **advance** | "Do whatever can be done now": take steps until a stage waits for the batch system, fails or is not implemented. | `Framework.advance` |
| **chunk** | One batch job of a sample. A sample with many files is split into several chunks. | PicoProducer |
| **attempt** | How many times the production stage has submitted its jobs (first submission + resubmissions), limited by `max_tries`. | `StageRecord.attempt` |
| **artifact** | A result of a stage that the next stage can use. Production: one merged pico tuple per sample; shapes: one shape file per config and working point; fit: the fitted values per working point. | `StageRecord.artifacts` |
| **reporter** | The object that receives every message. It prints to the terminal and `run.log`, or keeps the messages silently (in tests). | `reporting.py` |

### Where to start reading the code

1. [Analyses/README.md](../Analyses/README.md) and the bundled analyses: what a user writes.
2. `python/stages/base.py`: the stage contract, the stage states and the stage context (short).
3. `python/framework.py`: `start` → `advance` → `_advance_stages`, the loop that drives the stages.
4. `python/stages/production.py`: the batch stage; `decide_next` holds its policy.
5. `python/stages/local.py`: the local stages (preflight, run the commands, DONE or FAILED); `controlhists.py`,
   `controlplots.py`, `shapes.py` and `fit.py` only map their options to the Histogrammer, Plotter and Fitter APIs; `python_step.py` runs a
   bundle's Python file through `step_runner.py`.
6. `python/recipe.py` and `python/validation.py`: what a valid recipe is, and the checks of the files it names.
7. `python/bundle.py`: the path rule (bundle file, `Configs/` template or module config) and the run's bundle copy.
8. `python/run_record.py`: what is written to `run.json`, and how the run state is computed.
9. `scripts/taufw.py`: the command line, which only calls the `Framework`.

## Quick start

From the TauFW repository root, use `python3 taufw.py` (or `python3 taufw.py --help`).
This root launcher delegates to `Framework/scripts/taufw.py` and uses the same
CMSSW environment as the installed command.

Run `taufw.py` without arguments in an interactive Linux terminal to open the
optional console menu (Python's standard-library `curses`; no extra dependency).
Use Up/Down to move, Enter to select, and Esc to go back or exit the main menu.

- **Start a new run** lists the analysis bundles in `Analyses/` or accepts another path, displays
  the selected recipe's pipeline, then offers to start the run. The picker always uses two equal-width
  panels: a recipe table on the left and numbered stage boxes connected by downward arrows on the right.
  Up/Down changes the recipe; Page Up/Page Down scrolls its pipeline. At least 64 columns and 12 rows
  are required; smaller terminals show a resize message and Esc still returns to the main menu.
  The preview follows the recipe's actual stage order, including custom Python steps, without planning jobs.
  Every recipe is checked when the list opens (`validation.py`): a recipe with problems is red in the list, and its
  preview lists every problem above the stages it could read. Such a recipe cannot be started.
  Selecting a recipe reloads it and prepares its read-only plan silently before showing the review screen,
  including any nonfatal planning notes. **View detailed plan** displays the existing textual plan and
  returns to the same review after Enter. **Start run** launches the run; **Back** returns to the picker.
- **Continue an existing run** lists saved runs in `taufw_runs/` and in the
  `run_root` of every recipe in `Analyses/` (newest first)
  or accepts another run directory. Choose one advance or repeated checking;
  polling defaults to 600 seconds. Terminal runs offer status inspection instead.
- **Inspect run status** shows the existing read-only status output, with Refresh
  and Back actions.
- **Tests** runs the automated tests behind the menu, on a live test screen ([Tests/README.md](../Tests/README.md)
  "Interactive testing menu"). Leaving the screen never stops them: the main menu shows their state, e.g.
  **Tests (Running 12/40)** or **Tests (Failed: 3)**, and Tests opens the running run's screen again.
- **Grid Certificate** checks the existing proxy at startup and whenever the main
  menu reopens. A green tick means valid; yellow **Warning: Proxy Failed!** means
  missing, expired, or unable to check. Select it to create or renew a CMS proxy
  with your certificate password. Startup does not prompt for a password.
- **Help** displays FAQ topics with explanations on the right; Page Up/Down
  scrolls the explanation.
- **Exit** closes the menu. While something runs behind it (tests), it asks first: **C** stay, **S** stop it
  all and quit, **Q** quit and leave it running (only while the login session lasts; see Tests/README.md).

Typed relative paths and the default run root are relative to the launch
directory. Operations print their normal output outside the menu; press Enter
to return afterward. Ctrl+C returns to the menu without cancelling submitted
batch jobs. Resume using the saved run record. Existing CLI subcommands and
explicit `--help` keep working without curses or an interactive terminal.

Menu presentation lives in `Utilities/python/Menu/`: `_menu.py` owns rendering,
wording, screen choices, and terminal lifecycle; `_navigation.py` owns screen
transitions, back behavior, refresh loops, and operation feedback; `faq.py` owns
help content.
`_test_run.py` is the test screen. What runs behind the menu is an operation
(`Utilities/python/Process/_operations.py`, `_supervisor.py`): a directory under `.artifacts/menu/operations/`
that a supervisor process fills while it runs the command, and that any menu reads again (CL §23).
`python/interactive.py` keeps recipe/run discovery, validation, record access,
read-only recipe previews and plan preparation, test runs (`start_tests`, `tests_operation`), and command
dispatch. Recipe previews (with their problems)
are made once per picker visit; Framework objects stay in the adapter. UI screens use ASCII frames, cyan accents,
selection markers, and a shared keyboard-controls footer. Colors are optional and all status labels
remain readable without them. Entry screens retain the adaptive TauFW artwork.
UI screens return named actions so layout and label
and navigation changes stay in Utilities. Source section banners document both sides of this
boundary.

```bash
taufw.py check   Analyses/example_mutau_short                  # every problem of the recipe; nothing is written
taufw.py check   Analyses/example_broken                       # a deliberately broken recipe: 4 problems, exit 1
taufw.py plan    Analyses/example_mutau_short                  # each stage's plan and files; nothing is written
taufw.py plan    Analyses/example_mutau_short --local          # quick local test: 100 events of one file per sample
taufw.py start   Analyses/example_mutau_short                  # creates taufw_runs/<name>_<time>/, submits the jobs
taufw.py advance taufw_runs/mutau_2022_postEE_short_20261013-120000  # check; resubmit failed chunks; merge when complete
taufw.py status  taufw_runs/mutau_2022_postEE_short_20261013-120000  # recorded and live state (read-only)
taufw.py advance taufw_runs/... --wait --poll 900              # keep advancing every 15 minutes until done
taufw.py plan    Analyses/tes_id_2025                          # the commands of the hists, plots, shapes, fit and python steps
taufw.py init    my_tes --from Analyses/tes_id_2025            # new bundle Analyses/my_tes/: a copy of its files
```

The same from Python:
```python
from TauFW.Framework import Framework, load_run

fw     = Framework.from_recipe("Analyses/example_mutau_short")   # a bundle directory or a recipe file
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

The local stages (`controlhists`, `controlplots`, `shapes`, `fit`, `python`) take one step, `NEW` → `DONE` or `FAILED`:

| Situation | Result |
|---|---|
| preflight finds a problem (no `cmsenv`, ROOT or `combine` missing, a config file missing, no shapes for the fit; a python step's file or function missing) | the stage stays `NEW`; the problem is its message and in its history; fix it and run `advance` again |
| every command exits with 0 **and** writes its expected outputs | `DONE`, with the artifacts |
| a command exits with another code, or does not write an expected output | `FAILED`; the message names the command, the exit code or the missing output, and the log; the last 20 log lines are printed |

Each command's output goes to `<run dir>/logs/<stage id>/NN_<label>.log`, and `run.json` lists every command with its exit
code and duration (`last_status.commands`). The expected outputs must be written by the command itself (modified
after it started): the Fitter scripts run `combine` through `os.system` and exit with 0 even when it fails, so
neither the exit code nor an old file is trusted.

A stage that is not implemented yet (none at the moment) reports `NOT_IMPLEMENTED`; the run then stops in state
`BLOCKED`, and the earlier stages keep their results.

Run states (`RunState`): `NEW`, `RUNNING` (e.g. a local stage is not ready yet), `WAITING` (a stage waits for jobs),
`DONE`, `FAILED` (a stage failed), `BLOCKED` (stopped at a stage that is not implemented). `DONE`, `FAILED` and
`BLOCKED` are final: advancing again changes nothing. `taufw.py` exits with 1 if the run failed.

If a stage raises an error (for example, the batch system cannot be reached), the error is recorded in the stage's
history, the state is unchanged, and the command fails; run `advance` again when the problem is solved.

Plots and shapes give their scripts the tuples their input names as `--tuples <pattern>`: the pattern on the
artifacts of the production stage (`LocalStage.tuples_pattern`), or the recipe's `{external: <pattern>}`; preflight
checks that the production tuple files, or the directory of the external pattern, exist. Only with `null` (old
recipes), and for the fit and python steps, the run's PicoProducer configuration is passed as `$TAUFW_PICO_CONFIG`
(PicoProducer's `getconfig()` reads it instead of `PicoProducer/config/config.json`); with `null` the scripts find the
tuples through its `$PICODIR`.

## Recipe reference

See [Analyses/README.md](../Analyses/README.md) for bundles, recipe authoring, all
stage options and defaults, path rules, Python steps, examples, commands,
troubleshooting, and current workflow limitations.

## Run directory

The run directory is in the recipe's `run_root` (`start --run-root` takes precedence; default `taufw_runs/` in the
working directory; see [Analyses/README.md](../Analyses/README.md#where-the-runs-go-run_root)).

```
<run_root>/<name>_<YYYYmmdd-HHMMSS>/
  run.json    the run record (below)
  run.log     plain-text copy of the messages of every start/advance
  bundle/     the run's copy of the bundle: the stages read their bundle files from here, never from the source
  logs/<stage id>/
              the Framework's files of a stage: one log per command of the local stages, NN_<label>.log (header
              with cwd and command line, the command's output, footer with exit code, duration and missing
              outputs); a python step also has context.json (its input) and result.json (its output)
  stages/<stage id>/
              the stage's output and nothing else, and manifest.json once the stage is DONE. The scripts of the
              controlhists, controlplots, shapes and fit stages run in it (the fit: in stages/<id>/<era>/), so
              their control-histogram files, plots, shapes and fit results are here; a python step's own files (ctx.stage_dir); production's merged tuples,
              <era>/<group>/<sample>_<channel><tag>.root (JobRequest.tupledir; PicoProducer's layout), with the
              pattern .../stages/<id>/$ERA/$GROUP on every tuple artifact. Its job files stay in PicoProducer/output/.
```

The Framework decides where a stage writes: it gives each module API the stage's directory as its output directory
(`LocalStage.output_dir`) and the inputs the recipe connects (the artifacts of the input stages, e.g. the fit gets
the directory of each point's shapes from the shapes artifacts). The API only uses them; there are no links or
copies. Before the scripts start, the API refuses an output directory that is not empty (an interrupted attempt;
remove it or start a new run), a relative tuple pattern, or a PicoProducer configuration with a relative `picodir`.

`manifest.json` (`python/manifest.py`) is written when a stage becomes `DONE` (never for a failed stage), before
`run.json` is saved: `{"manifest": 2, "run_id", "stage_id", "stage", "description", "inputs", "sources", "stage_dir",
"finished", "artifacts"}`. It is a copy of the stage's record, so that a stage directory describes itself; `run.json`
stays the source of truth. `stage_dir` is where it was written (absolute).

A manifest is also the contract for an input of another run: `inputs: {shapes: {path: <run_dir>/stages/<id>}}`
([Analyses/README.md](../Analyses/README.md#inputs-from-another-run)). The reader takes the artifacts from the
manifest, never from the other run's `run.json`, and writes nothing there. `read_stage_dir` refuses a directory
without a manifest (not `DONE`), a manifest of another format (format 1, before R4: no conversion), and a directory
that is not its `stage_dir` (moved or copied: its artifacts name files of the old place); `validation.read_source`
adds the kind check (the source's stage must make the kind of data the slot takes). `check`, `plan` and `advance`
use the same functions, so the messages are the same; in `advance` a problem stops the stage like a preflight
problem (it stays `NEW`). Inside the Framework the slot is keyed by the directory (`StageContext.inputs` and
`upstream`), so the stages use these artifacts like those of a stage of the run. What was read is the stage's
`sources`: slot -> `{path, run_id, stage_id, stage, finished, manifest_sha256}`, in `run.json` (written at every step
of the stage) and in the reader's manifest.

`run.json` (schema 3; a run directory of another schema is refused):
```json
{"schema": 3, "run_id": "...", "created": "...", "updated": "...",
 "recipe": {"name": "...", "pico": {"config": null}, "stages": [...]},
 "pico_config": {"path": ".../config/config.json", "snapshot": {...}},
 "bundle": {"source": ".../Analyses/tes_id_2025", "files": ["recipe.yml", "config_coarse_TT.yml", ...]},
 "stages": [{"name": "production", "state": "WAITING", "attempt": 2, "message": "...",
             "request": {...}, "sources": {}, "submissions": [...], "last_status": {...}, "artifacts": [...],
             "history": [{"time": "...", "event": "resubmitted", "state": "SUBMITTED", "detail": "..."}]}]}
```
- A run always continues with the recipe stored in `run.json` and its `bundle/` copy, not with the current files.
- A stage record's `name` is the stage id. `bundle` is `{}` for a loose recipe file without bundle files.
- `run.json` is written to a temporary file and renamed, so it is never half written.
- The production stage's source of truth stays with PicoProducer (its job configs under `PicoProducer/output/`);
  `run.json` holds the requests, summaries and artifacts.
- Artifacts of the production stage are PicoProducer `TupleArtifact`s: `path`, `sample`, `group`, `era`,
  `channel`, `tag`, `dtype`, `nevents`, `tree`, `cutflow`.

## Package layout

| File | Contents |
|---|---|
| `python/framework.py` | `Framework`: `plan`, `start`, `advance`, `run`, `status`, `make_bundle`; stage dispatch; construction (`from_recipe`, `from_record`) |
| `python/recipe.py` | `Recipe`, `StageSpec`, `Issue`, `RecipeError`: load and validate recipes (a bundle directory or a file): structure, stage ids, inputs (stage ids, `{path}`, `{external}`), at most one production; every problem at once |
| `python/validation.py` | `check_recipe`, `RecipeCheck`: everything `recipe.py` checks plus the files a recipe names (and the stage directories of `{path}` inputs, `read_source`), without raising (`taufw.py check`, the menu) |
| `python/manifest.py` | `write_manifest`, `read_stage_dir`, `StageDir`, `ManifestError`: the stage manifests (format 2) |
| `python/bundle.py` | the path rule (bundle file, `Configs/` template, module config, absolute), the run's bundle copy, new bundles (`taufw.py init`) |
| `python/samples.py` | `sample_issues`: before a run, the samples a production stage makes (PicoProducer's catalogs) vs those its readers' `samples` files ask for (Histogrammer API); `plan` lists, `start` refuses the problems |
| `python/configs.py` | the config templates of `Configs/`: headers (`taufw_config`: id, version, schema), `configs.lock`, `update` (`taufw.py configs update`), the warnings for old copies in a bundle |
| `python/step_runner.py` | runs a python step in its own process (standard library only): `context.json` → `run(ctx)` → `result.json` |
| `python/run_record.py` | `RunRecord`, `RunState`, `StageRecord`: `run.json`, crash-safe save |
| `python/reporting.py` | `Reporter` (interface), `FrameworkReporter` (terminal + `run.log`), `SilentReporter`, `EventReporter` (also writes events for the menu, `$TAUFW_EVENTS`); adapter for PicoProducer's messages |
| `python/defaults.py` | shared defaults: `taufw_runs`, `run.json`, `run.log`, `recipe.yml`, `bundle/`, `logs/`, `stages/`, `manifest.json`, `Analyses/`, `Configs/`, the polling interval (600 s), the time format |
| `python/interactive.py` | the Framework side of the console menu (recipe/run discovery, dispatch to the commands) |
| `python/stages/base.py` | the stage contract: `Stage`, `StageState`, `StageOutcome`, `StageContext`, `StageNotImplemented`, `PreflightError` |
| `python/stages/production.py` | `ProductionStage` and the pure `decide_next` policy |
| `python/stages/local.py` | `LocalStage`: preflight, run the commands, `DONE` or `FAILED` (log tail) |
| `python/stages/controlhists.py`, `controlplots.py`, `shapes.py`, `fit.py` | the local stages and their specs (`fit.py` also picks the working points) |
| `python/stages/python_step.py` | `PythonStage`, `PythonSpec`: a bundle's Python file as a recipe step |
| `scripts/taufw.py` | the command line (no logic: argparse → `Framework`) |

The analyses live outside this package, in `Analyses/` at the repository root: `Analyses/README.md` (authoring and
usage reference), `Analyses/example_mutau_short/` (a small production), `Analyses/example_mutau_long/` (a full production with data, then control plots) and `Analyses/tes_id_2025/` (the TES +
tau ID fit on existing tuples: control histograms and plots, shapes, fit, and a Python summary step).

Dependencies point one way: `Framework → PicoProducer.api, Histogrammer.api, Plotter.api, Fitter.api` (the
Histogrammer is the former Plotter; the new Plotter only draws, changelog §24). No other package imports the
Framework, and the stages never import each other: the Framework carries the control-histogram files from the
Histogrammer to the Plotter. The Framework imports each API only when its stage is built, and the module APIs never import
ROOT (they run the scripts as separate processes, through `TauFW.Utilities.Process`), so recipes, run records and the
stage logic can be tested without ROOT.

## Tests

`python3 Tests/run.py all` runs the automated suites quietly; use `all -v` for full output.
BBB check/lock also default to quiet output; see the [test runner instructions](../Tests/README.md#output-quiet-by-default).

- `python -m unittest discover -s Tests/Framework` (any Python 3.9+, no ROOT): the state machine with a fake
  PicoProducer (submit, wait, resubmit until `max_tries`, merge, not-implemented stages, errors), `decide_next`,
  `run.json` round trip and crash-safe save, recipe validation, and `taufw.py`; the local stages with fake
  Histogrammer, Plotter and Fitter APIs (`test_stages.py`: the whole pipeline, repeated stages, preflight, failures, fit
  points, planned artifacts, inputs from another run, controlplots drawing the files of controlhists); bundles (`test_bundle.py`: the path rule, stage ids, `{path}` inputs, the
  run's bundle copy, `taufw.py init`); manifests (`test_manifest.py`); recipe checks with files
  (`test_validation.py`); python steps (`test_python_step.py`: real step files run by `step_runner.py`).
- `Tests/Fitter/api`, `Tests/Histogrammer/api`, `Tests/Plotter/api`: the commands of the APIs equal those of
  `run_inputs.sh`, `run_workflow_zmm.sh`, `fillhists.py` and `draw.py`, and outputs are checked (fake process runner, no ROOT).
- BBB case `framework.production` (lxplus): `taufw.py plan/start/advance/status` against the fake HTCondor of the
  PicoProducer BBB harness, with a resubmission and a merge; snapshots the normalized `run.json` and the merged tuples.
