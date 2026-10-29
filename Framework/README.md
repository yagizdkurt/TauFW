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
          PicoProducer API   Histogrammer API    Plotter API      Histogrammer API   Fitter API
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
| **analysis bundle** | A directory `Analyses/<name>/` with `recipe.yml`, the config files the recipe uses and its Python steps; every path is relative to the directory of `recipe.yml`. A stage's path option names a bundle file, a `Configs/` template, an absolute file or (controlhists) a channel name; no module directory is searched (CL §38). A run copies the bundle to `<run dir>/bundle/` and reads only that copy. | `bundle.py` |
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
| **run** | One execution of a recipe. Each run gets its own directory, `<run_root>/<name>_<time>/` (`run_root` from `--run-root`, else the recipe, else `runs.run_root` of the user config, default `taufw_runs/`). | `RunRecord.create` |
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
3. `python/_internal/runtime/framework.py`: `start` → `advance` → `_advance_stages`, the loop that drives the stages.
4. `python/stages/production.py`: the batch stage; `decide_next` holds its policy.
5. `python/stages/local.py`: the local stages (preflight, run the commands, DONE or FAILED); `controlhists.py`,
   `controlplots.py`, `shapes.py` and `fit.py` only map their options to the Histogrammer, Plotter and Fitter APIs; `python_step.py` runs a
   bundle's Python file through `_internal/runtime/step_runner.py`.
6. `python/_internal/recipes/recipe.py` and `python/_internal/recipes/validation.py`: what a valid recipe is, and the checks of the files it names.
7. `python/_internal/recipes/bundle.py`: the path rule (absolute, bundle file or above it, `Configs/` template, channel name; CL §38) and the run's bundle copy.
8. `python/_internal/runtime/run_record.py`: what is written to `run.json`, and how the run state is computed.
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
  **[Create a new run]** is always the first row. It asks for an analysis name and creates
  `Analyses/<name>/recipe.yml` from the empty template, then selects the new **Draft**. Existing paths
  are never overwritten; Esc cancels. A draft has `stages: []` and cannot be planned or started until
  stages are added. **E** on an analysis opens the Run editor entry point; its screen is coming next.
  The preview follows the recipe's actual stage order, including custom Python steps, without planning jobs.
  Every recipe is checked when the list opens (`validation.py`): a recipe with problems is red in the list, and its
  preview lists every problem above the stages it could read. Such a recipe cannot be started.
  Selecting a recipe reloads it and prepares its read-only plan silently before showing the review screen,
  including any nonfatal planning notes. **View detailed plan** displays the existing textual plan and
  returns to the same review after Enter. **Start run** launches the run; **Back** returns to the picker.
- **Continue an existing run** lists saved runs in `taufw_runs/`, in `runs.run_root` of the user config and
  in the `run_root` of every recipe in `Analyses/` (newest first)
  or accepts another run directory. Choose one advance or repeated checking;
  polling defaults to 600 seconds. Terminal runs offer status inspection instead.
  The list shows a `RUNNING` run that no advance works on now (none behind the menu, no live advance lock) as
  `PAUSED`: it goes on with the next advance. `run.json` and `taufw.py status` still say `RUNNING`.
- **Inspect run status** shows the existing read-only status output, with Refresh
  and Back actions. Its state line is the command's: `READING STATUS` while it reads, then only the time; the run's
  state is in the output.
  At **120 columns by 18 rows** or more, Continue and Inspect keep the run list on the left and show the
  selected run's actions/stages or status on the right. Discovery and previews load in the background;
  a small ASCII decay marks loading. Up/Down changes runs, PgUp/PgDn scrolls details, and R refreshes them.
  In Continue, Enter/Tab focuses the actions and Enter runs the chosen action; Esc returns to the list.
  In Inspect, Enter opens status full screen. Smaller terminals keep the list/Enter flow. A status query
  starts only after the selection settles for 250 ms; changing runs or leaving stops the old query.
- **Tests** runs the automated tests behind the menu, on a live test screen ([Tests/README.md](../Tests/README.md)
  "Interactive testing menu"). Leaving the screen never stops them: the main menu shows their state, e.g.
  **Tests (Running 12/40)** or **Tests (Failed: 3)**, and Tests opens the running run's screen again.
- **Grid Certificate** checks the existing proxy at startup and whenever the main
  menu reopens. A green tick means valid; yellow **Warning: Proxy Failed!** means
  missing, expired, or unable to check. Select it to create or renew a CMS proxy
  with your certificate password. Startup does not prompt for a password.
- **Install components** opens the existing installer checklist and progress screen.
  Choose optional components, then **Start install**, or use **Cancel** / Esc to return.
  Closing the result screen returns to the main menu.
- **Help** displays FAQ topics with explanations on the right; Page Up/Down
  scrolls the explanation.
- **Exit** closes the menu. While something runs behind it (tests), it asks first: **C** stay, **S** stop it
  all and quit, **Q** quit and leave it running (only while the login session lasts; see Tests/README.md).

Typed relative paths and the default run root are relative to the launch
directory. Operations print their normal output outside the menu; press Enter
to return afterward. Ctrl+C returns to the menu without cancelling submitted
batch jobs. Resume using the saved run record. Existing CLI subcommands and
explicit `--help` keep working without curses or an interactive terminal.

Menu presentation lives in `Framework/python/_internal/menu/`: `_menu.py` owns rendering,
wording, screen choices, and terminal lifecycle; `_navigation.py` owns screen
transitions, back behavior, refresh loops, and operation feedback; `faq.py` owns
help content.
`_test_run.py` is the test screen. What runs behind the menu is an operation
(`Framework/python/_internal/operations/_operations.py`, `_supervisor.py`): a directory under `.artifacts/menu/operations/`
that a supervisor process fills while it runs the command, and that any menu reads again (CL §18).
`python/_internal/interfaces/interactive.py` keeps recipe/run discovery, validation, record access,
read-only recipe previews and plan preparation, test runs (`start_tests`, `tests_operation`), and command
dispatch. Recipe previews (with their problems)
are made once per picker visit; Framework objects stay in the adapter. UI screens use ASCII frames, cyan accents,
selection markers, and a shared keyboard-controls footer. Colors are optional and all status labels
remain readable without them. Entry screens retain the adaptive TauFW artwork.
UI screens return named actions so layout and label
and navigation changes stay in Utilities. Source section banners document both sides of this
boundary.

```bash
taufw.py check   Analyses/Examples/mutau_short                  # every problem of the recipe; nothing is written
taufw.py check   Analyses/Examples/broken                       # a deliberately broken recipe: 4 problems, exit 1
taufw.py plan    Analyses/Examples/mutau_short                  # each stage's plan and files; nothing is written
taufw.py plan    Analyses/Examples/mutau_short --local          # quick local test: 100 events of one file per sample
taufw.py start   Analyses/Examples/mutau_short                  # creates taufw_runs/<name>_<time>/, submits the jobs
taufw.py advance taufw_runs/mutau_2022_postEE_short_20261013-120000  # check; resubmit failed chunks; merge when complete
taufw.py status  taufw_runs/mutau_2022_postEE_short_20261013-120000  # recorded and live state (read-only)
taufw.py advance taufw_runs/... --wait --poll 900              # keep advancing every 15 minutes until done
taufw.py retry   taufw_runs/...                                # a FAILED local stage again (cause fixed), then go on
taufw.py plan    Analyses/tes_id_2025                          # the commands of the hists, plots, shapes, fit and python steps
taufw.py init    my_tes --from Analyses/tes_id_2025            # new bundle Analyses/my_tes/: a copy of its files
```

The same from Python:
```python
from TauFW.Framework import Framework, load_run

fw     = Framework.from_recipe("Analyses/Examples/mutau_short")   # a bundle directory or a recipe file
record = fw.start()                         # RunRecord; record.state == 'WAITING'
# ... later, maybe in another session:
record = load_run(record.run_dir)
record = Framework.from_record(record).advance(record)
print(record.state, record.stage('production').artifacts)
```

## TauFW versions and update notices

`python/_internal/version.json` is the single source of the installed TauFW
version. Its `update_manifest_url` currently reads the same file from
`yagizdkurt/TauFW`, branch `Refactor-2025`, on GitHub. To change the repository,
branch, or hosting service, change that HTTPS raw-JSON URL in the manifest;
GitLab raw-file URLs work with the same checker. The remote file's source URL
is never followed recursively. Publish the manifest together with the code it
describes; pushing code without changing the version produces no new notice.

TauFW uses its own **X.Y.Z** version policy:

| Number | Meaning |
| --- | --- |
| X | Incompatible changes. |
| Y | Compatible, stable changes. |
| Z | Beta/nonstable changes within that major/minor version. |

Only the first two numbers determine whether to announce a newer version.
`1.1.0` to `1.1.1` produces no notice; `1.1.0` to `1.2.3` does, and shows
the complete `1.2.3` version even though its last number is nonzero. Versions
are compared numerically, so `0.10.0` is newer than `0.9.9`. This policy is
distinct from Semantic Versioning's patch-release meaning. It does not change
the separate run schema, stage manifest format, or config template versions.

The main menu reads local metadata immediately and checks remotely in a
Framework-owned daemon thread. A passive notice appears when a newer version
is found; there is no update button, code download, or automatic checkout
change. Results are cached per user under `$XDG_CACHE_HOME/taufw/` (default
`~/.cache/taufw/`) for 24 hours; failed checks retry after one hour. Returning
to the menu starts a due check; an untouched idle menu does not poll forever.
Unreachable sources or invalid manifests show **Version check unavailable**
without blocking analyses. Previously known updates are retained and labeled
when a recheck fails or the cached answer is stale. A readonly cache only
disables persistence. The HTTPS request has a three-second socket timeout and
a 64 KiB response limit; opening or leaving the menu never waits for it.

```bash
taufw.py version                   # installed version only; no network or cache writes
taufw.py version --check           # explicitly refresh the remote manifest; no code download
export TAUFW_NO_VERSION_CHECK=1    # disable remote checks, including version --check
```

Importing the Framework and running `check`, `plan`, `start`, `advance`, or
`status` does not trigger a version request. Python callers can use
`TauFW.Framework.current_version()` or `VersionChecker().check()` explicitly.
The first published manifest must be pushed before its remote check can
succeed; until then a missing remote file is an ordinary unavailable check.

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
| the stage is `FAILED` and its cause is fixed | `taufw.py retry <run dir>` (menu: Continue > Retry): the failed attempt moves to `logs/<stage id>/attempt<N>/`, the stage is `NEW` again, then the run goes on like `advance`; the finished stages do not run again; `run.json` records the retry in the stage's `retries` (CL §44) |

Each command's output goes to `<run dir>/logs/<stage id>/NN_<label>.log`, and `run.json` lists every command with its exit
code and duration (`last_status.commands`). The expected outputs must be written by the command itself (modified
after it started): the Fitter scripts run `combine` through `os.system` and exit with 0 even when it fails, so
neither the exit code nor an old file is trusted.

A stage that is not implemented yet (none at the moment) reports `NOT_IMPLEMENTED`; the run then stops in state
`BLOCKED`, and the earlier stages keep their results.

Run states (`RunState`): `NEW`, `RUNNING` (e.g. a local stage is not ready yet), `WAITING` (a stage waits for jobs),
`DONE`, `FAILED` (a stage failed), `BLOCKED` (stopped at a stage that is not implemented). `DONE`, `FAILED` and
`BLOCKED` are final: advancing again changes nothing (a `FAILED` local stage can be retried, above; a `FAILED`
production stage too, when its chunks still failed after `max_tries`: `taufw.py retry` gives it `max_tries` more
tries, resubmits only the failed chunks and moves nothing; its other failures need a new run, CL §48). `taufw.py`
exits with 1 if the run failed.

The run's bundle copy (`<run dir>/bundle/`) is checked at every `advance` and `retry`: `start` records the sha256 of
its files (`run.json` `bundle.sha256`), and a change (a file added, edited or removed, e.g. a fix before a retry) is
warned about once and recorded in `bundle.changed`. Such a run is not clean: the manifests of the stages that ran
after the change say `bundle_changed: true` (CL §44).

If a stage raises an error (for example, the batch system cannot be reached), the error is recorded in the stage's
history, the state is unchanged, and the command fails; run `advance` again when the problem is solved.

Plots and shapes give their scripts the tuples their input names as `--tuples <pattern>`: the pattern on the
artifacts of the production stage (`LocalStage.tuples_pattern`), or the recipe's `{external: <pattern>}`; preflight
checks that the production tuple files, or the directory of the external pattern, exist. The module APIs never get
the PicoProducer configuration (CL §37: no `pico_config` in their requests, no `$TAUFW_PICO_CONFIG`); a tuples input
is never `null` (a recipe error, CL §37). Python steps get the run's configuration as `ctx.pico_config` only (no
environment variable); `pico.config` is allowed only in a recipe with a production stage.

## Recipe reference

See [Analyses/README.md](../Analyses/README.md) for bundles, recipe authoring, all
stage options and defaults, path rules, Python steps, examples, commands,
troubleshooting, and current workflow limitations.

## Run directory

The run directory is in the recipe's `run_root` (`start --run-root` takes precedence; without both, `runs.run_root`
of the user config; default `taufw_runs/` in the working directory; see
[Analyses/README.md](../Analyses/README.md#where-the-runs-go-run_root)).

## User config

`Analyses/UserConfig.yaml` (or the file `$TAUFW_USER_CONFIG` names) holds the personal settings of the user: made by
FastSetup or `taufw.py userconfig`, ignored by git, read with `TauFW.Utilities.UserConfig` (changelog §40, §41).
The Framework reads it in `python/_internal/user_settings.py`, the same way as a user's script, and always after the command
line and the recipe:

| Setting | Used for | Precedence |
| --- | --- | --- |
| `runs.run_root` | where `start` makes the run | `--run-root` > recipe `run_root` > user config > `taufw_runs/` |
| `production.batch`, `outdir`, `nanodir`, `tmpskimdir`, `hadd.cmd`, `hadd.maxopenfiles` | keys `batch`, `outdir`, `nanodir`, `tmpskimdir`, `haddcmd`, `maxopenfiles` of the production stage's PicoProducer configuration (in memory, `PicoProducer.from_config(overrides=)`) | user config > `pico.config` / `config.json` |
| `production.queue`, `batchopts`, `ncores` | the production request, when the recipe does not set the option | recipe > user config > PicoProducer's default |

`plan` names them (`Run root: ... (user config)`, `PicoProducer config: ...; from your user config: ...`), and
`run.json` records the settings used in `pico_config.user_config`. `check`, `plan` and `start` show the user
config's warnings in one line each (no file, not reviewed, a wrong value); a wrong production setting is a problem
of a recipe with a production stage, and stops `plan` and `start`. Standalone `pico.py` does not read the user
config (it keeps `config.json`).

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

`manifest.json` (`python/_internal/runtime/manifest.py`) is written when a stage becomes `DONE` (never for a failed stage), before
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
 "pico_config": {"path": ".../config/config.json", "snapshot": {...},
                 "user_config": {"path": ".../Analyses/UserConfig.yaml", "settings": ["production.outdir", ...]}},
 "bundle": {"source": ".../Analyses/tes_id_2025", "files": ["recipe.yml", "config_coarse_TT.yml", ...]},
 "stages": [{"name": "production", "state": "WAITING", "attempt": 2, "message": "...",
             "request": {...}, "sources": {}, "submissions": [...], "last_status": {...}, "artifacts": [...],
             "history": [{"time": "...", "event": "resubmitted", "state": "SUBMITTED", "detail": "..."}]}]}
```
- A run always continues with the recipe stored in `run.json` and its `bundle/` copy, not with the current files.
  The PicoProducer configuration and the user config are read again at every `advance` (TODO: use the snapshot).
- `pico_config.user_config` is there only when the user config gave a production setting; `snapshot` already has
  its values.
- A stage record's `name` is the stage id. `bundle` is `{}` for a loose recipe file without bundle files.
- `run.json` is written to a temporary file and renamed, so it is never half written.
- The production stage's source of truth stays with PicoProducer (its job configs under `PicoProducer/output/`);
  `run.json` holds the requests, summaries and artifacts.
- Artifacts of the production stage are PicoProducer `TupleArtifact`s with the stage's `pattern` added: `kind`
  (`tuples`), `path`, `sample`, `group`, `era`, `channel`, `tag`, `dtype`, `nevents`, `sumw`, `tree`, `cutflow`
  (fields: [Docs/Develop/contracts/pico-tuples.md](../Docs/Develop/contracts/pico-tuples.md#production-record)). The controlhists and
  shapes stages read only artifacts of kind `tuples`; a production run from before CL §36 (no `kind`), named with
  `{path: ...}`, is refused with a message.

## Package layout

```
Framework/python/
  __init__.py     the public API: from TauFW.Framework import Framework, Recipe, ...
  stages/         the stage contract (base.py) and the stages
  _internal/      the Framework's inside, not for analysis code (CL §52):
    runtime/      execution and saved run state
    recipes/      recipe models, validation, bundles and config templates
    interfaces/   the Framework side of the menu
    defaults.py, user_settings.py, version.py (+ version.json, empty_recipe.yml, setup_manifest.json)
    menu/ editor/ installer/ operations/ notifications.py   TauFW's own tools (_internal/README.md)
```

Use the public imports, `from TauFW.Framework import Framework, Recipe, ...`. Inside the Framework, modules import
each other by their package paths, for example `TauFW.Framework._internal.recipes.recipe`. No stage and no
Utilities package imports anything of `TauFW.Framework` (`Tests/check_import_boundaries.py`). Future recipe
creation/editing logic belongs in `_internal/recipes/`; the terminal widgets stay in `_internal/menu/` and
`_internal/editor/` ([_internal/README.md](python/_internal/README.md)), with Framework callbacks supplied through
`_internal/interfaces/`.

| File | Contents |
|---|---|
| `python/_internal/runtime/framework.py` | `Framework`: `plan`, `start`, `advance`, `retry`, `run`, `status`, `make_bundle`; stage dispatch; construction (`from_recipe`, `from_record`) |
| `python/_internal/recipes/recipe.py` | `Recipe`, `StageSpec`, `Issue`, `RecipeError`: load and validate recipes (a bundle directory or a file): structure, stage ids, inputs (stage ids, `{path}`, `{external}`), at most one production; every problem at once |
| `python/_internal/recipes/validation.py` | `check_recipe`, `RecipeCheck`: everything `recipe.py` checks plus the files a recipe names (and the stage directories of `{path}` inputs, `read_source`), without raising (`taufw.py check`, the menu) |
| `python/_internal/runtime/manifest.py` | `write_manifest`, `read_stage_dir`, `StageDir`, `ManifestError`: the stage manifests (format 2) |
| `python/_internal/recipes/bundle.py` | the path rule (absolute, bundle file, outside the bundle, `Configs/` template, channel name; `is_absolute`), the run's bundle copy, new bundles (`taufw.py init`) |
| `python/_internal/recipes/samples.py` | `sample_issues`: before a run, the samples a production stage makes (PicoProducer's catalogs) vs those its readers' `samples` files ask for (Histogrammer API); `plan` lists, `start` refuses the problems |
| `python/_internal/recipes/configs.py` | the config templates of `Configs/`: headers (`taufw_config`: id, version, schema), `configs.lock`, `update` (`taufw.py configs update`), the warnings for old copies in a bundle |
| `python/_internal/runtime/step_runner.py` | runs a python step in its own process (standard library only): `context.json` → `run(ctx)` → `result.json` |
| `python/_internal/runtime/run_record.py` | `RunRecord`, `RunState`, `StageRecord`: `run.json`, crash-safe save |
| `python/_internal/runtime/run_lock.py` | the advance lock, lost-lock detection and takeover |
| `python/_internal/runtime/interrupts.py` | deferred interruption while a submission finishes |
| `python/_internal/runtime/reporting.py` | `Reporter` (interface), `FrameworkReporter` (terminal + `run.log`), `SilentReporter`, `EventReporter` (also writes events for the menu, `$TAUFW_EVENTS`); adapter for PicoProducer's messages |
| `python/_internal/defaults.py` | shared defaults: `taufw_runs`, `run.json`, `run.log`, `recipe.yml`, `bundle/`, `logs/`, `stages/`, `manifest.json`, `Analyses/`, `Configs/`, the polling interval (600 s), the time format |
| `python/_internal/interfaces/interactive.py` | the Framework side of the console menu (recipe/run discovery, dispatch to the commands) |
| `python/stages/base.py` | the stage contract: `Stage`, `StageState`, `StageOutcome`, `StageContext`, `StageNotImplemented`, `PreflightError` |
| `python/stages/production.py` | `ProductionStage` and the pure `decide_next` policy |
| `python/stages/local.py` | `LocalStage`: preflight, run the commands, `DONE` or `FAILED` (log tail) |
| `python/stages/controlhists.py`, `controlplots.py`, `shapes.py`, `fit.py` | the local stages and their specs (`fit.py` also picks the working points) |
| `python/stages/python_step.py` | `PythonStage`, `PythonSpec`: a bundle's Python file as a recipe step |
| `scripts/taufw.py` | the command line (no logic: argparse → `Framework`) |

The analyses live outside this package, in `Analyses/` at the repository root: `Analyses/README.md` (authoring and
usage reference), `Analyses/Examples/mutau_short/` (a small production), `Analyses/Examples/mutau_long/` (a full production with data, then control plots) and `Analyses/tes_id_2025/` (the TES +
tau ID fit on existing tuples: control histograms and plots, shapes, fit, and a Python summary step).

Dependencies point one way: `Framework → PicoProducer.api, Histogrammer.api, Plotter.api, Fitter.api` (the
Histogrammer is the former Plotter; the new Plotter only draws, changelog §21). No other package imports the
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
