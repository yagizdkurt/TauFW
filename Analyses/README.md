# TauFW analyses

An analysis is one directory, an **analysis bundle**, that holds everything the
analysis reads:

```text
Analyses/tes_id_2025/
  recipe.yml                which stages to run, and their options
  setup_mutau.yml           config files that replace the modules' own configs
  config_coarse_TT.yml
  steps/fit_summary.py      the analysis's own Python steps
```

Every path in the recipe is relative to the directory of `recipe.yml`. The
layout inside it is up to you: the bundled examples keep their configs next to
`recipe.yml` and their Python steps in `steps/`, but subdirectories work too.

The recipe describes the pipeline: which stages to run, which samples and eras
to use, and the options for each stage. The Framework reads it, checks its
structure, and calls the public PicoProducer, Plotter, and Fitter APIs, and the
analysis's own Python steps. A recipe can produce new pico tuples or start from
existing tuples or fit shapes. Copy or send the directory to hand over the whole
analysis.

This is the analysis authoring and usage reference. For the Framework's state
machine, Python API, and run-record internals, see the
[Framework README](../Framework/README.md).

- [Bundled analyses](#bundled-analyses)
- [Writing your first analysis](#writing-your-first-analysis)
- [File format and validation](#file-format-and-validation)
- [Paths and configuration](#paths-and-configuration)
- [Stage options](#stage-options)
- [Python steps](#python-steps)
- [Choosing fit working points and steps](#choosing-fit-working-points-and-steps)
- [Planning, starting, and continuing a run](#planning-starting-and-continuing-a-run)
- [Outputs and logs](#outputs-and-logs)
- [Troubleshooting](#troubleshooting)
- [Current limitations](#current-limitations)

## Bundled analyses

| Bundle | Pipeline | Inputs and purpose |
| --- | --- | --- |
| [example_mutau](example_mutau/recipe.yml) | `production` → `plots` | Produce `2022_postEE` mutau tuples for sample names matching `DY*` or `TT*`, then make control plots. |
| [example_broken](example_broken/recipe.yml) | (invalid on purpose) | A demonstration of the validation: `taufw.py check Analyses/example_broken` lists its four problems; the menu shows it in red. Do not fix it. |
| [tes_id_2025](tes_id_2025/recipe.yml) | `plots` → `histograms` → `fit` → `fit_summary` (python) | Use existing 2025 tuples for the combined tau energy scale (TES) and tau ID scale factor fit, with the Z→μμ control region; DeepTau VSjet `VTight`, VSe `Tight`; then a table of the fitted values. |

Each bundle carries copies of the Plotter and Fitter configs it uses, next to
its `recipe.yml`. The examples still need the corresponding sample catalog,
tuple files, and PicoProducer configuration in your environment; they are not
self-contained input datasets (see [Current limitations](#current-limitations)).

The optional interactive menu lists the bundles in this directory (directories
with a `recipe.yml`) and loose `.yml`, `.yaml`, and `.json` recipe files.
Recipes elsewhere work too: select another path in the menu or pass the path to
the command line.

## Writing your first analysis

Make a bundle with `taufw.py init`:

```bash
python3 taufw.py init my_mutau                          # Analyses/my_mutau/ with an example Python step
python3 taufw.py init my_tes --from Analyses/tes_id_2025  # a copy of a bundle or recipe file, with copies of
                                                        # the module configs it uses next to recipe.yml
```

`init --from` copies every Plotter or Fitter config the recipe takes from its
module next to the new `recipe.yml` (a name that is taken becomes
`plotter_<name>` or `fitter_<name>`) and points the new recipe at the copies, so
you can edit them without touching the modules. Comments of the
source recipe are not kept.

For production alone, `Analyses/my_mutau/recipe.yml` could be:

```yaml
name: my_mutau_2022_postEE
pico:
  config: null
stages:
  - stage: production
    id: production
    description: mutau tuples of the DY and ttbar samples   # optional
    inputs: null              # production reads no other stage's output
    eras: [2022_postEE]
    channels: [mutau]
    samples: ["DY*", "TT*"]
    max_tries: 3
    merge:
      clean: false
      force: false
```

This selects the matching samples from the configured catalog, submits their
NanoAOD processing jobs, checks and resubmits failed chunks as needed, then
merges successful output into pico tuples. An empty `samples: []` means no sample
name restriction; it does not mean "run no samples."

To make control plots after production, append this entry under the same
`stages:` list:

```yaml
  - stage: plots
    id: plots
    inputs: {tuples: production}   # the tuples of the stage with id production
    eras: [2022_postEE]
    configs: [mutau]
    variables: [m_vis, pt_1, pt_2]
    selections: [baseline]
```

Each stage has its own options. Setting `eras` on production does not set the
eras for plots or histograms. Likewise, production `channels: [mutau]` and plot
`configs: [mutau]` belong to different packages and serve different purposes.

For plots of tuples you already have, omit the production entry and write
`inputs: {tuples: null}` (null: the tuples already in `$PICODIR`). For
shape creation and a fit on existing tuples, use
[tes_id_2025](tes_id_2025/recipe.yml). For a fit on existing shapes, use the
explicit working-point example [below](#choosing-fit-working-points-and-steps).

## File format and validation

A bundle's recipe is its `recipe.yml`; the commands take the bundle directory
(`taufw.py plan Analyses/tes_id_2025`). A loose recipe file works too:
recipes accept `.yml`, `.yaml`, or `.json`. YAML is convenient for comments; JSON
uses the same mappings, lists, and values, without comments. Use YAML booleans
`true`/`false`, `null` for optional unset values, and lists for collections. Quote
glob patterns such as `"DY*"` and `"*Muon*"`, and prefer quoted numeric eras such
as `"2025"` consistently across stages.

Only these top-level keys are supported:

| Key | Required/default | Meaning |
| --- | --- | --- |
| `name` | Required | Non-empty string containing only ASCII letters, digits, `_`, `.`, and `-`. Used as the run-directory prefix, independently of the recipe filename. |
| `pico` | Optional | Mapping with only `config`; omitting it uses PicoProducer's default configuration. |
| `pico.config` | `null` | PicoProducer configuration file path. See the path rules below. |
| `stages` | Required | Non-empty list of stage mappings. Each entry needs `stage`, `id` and `inputs`, may have `description`, and has that stage's options. |

The built-in stages must appear in this order:

```text
production → plots → histograms → fit
```

Any non-empty subset is allowed, but a built-in stage may occur only once. For
example, `histograms` followed by `fit` is valid, while `fit` followed by
`histograms`, or two separate `production` entries, is invalid. Put multiple
eras, channels, configs, or working points in a single stage's lists. Use
separate recipes when you need independent production settings.

[Python steps](#python-steps) (`stage: python`) are not part of this order: they
may appear anywhere, any number of times.

Every stage has these keys besides its options:

| Key | Required | Meaning |
| --- | --- | --- |
| `stage` | Yes | The stage type: `production`, `plots`, `histograms`, `fit`, `python`. |
| `id` | Yes | The stage's name in the run: its record in `run.json`, its directories `taufw_runs/<run>/stages/<id>/` (output) and `logs/<id>/`, and what `inputs:` refer to. Unique; letters, digits, `_`, `.`, `-` (not `.` or `..`). Any stage may have any id (`id: shapes_tight`). |
| `inputs` | Yes | Which earlier stage's output the stage reads (see the table below). Never left out and never `{}`: a stage without inputs says `inputs: null`. |
| `description` | No | Free text, shown by `plan` and in the menu. Nothing depends on it. |

`inputs` connects each **input slot** of the stage to the id of an earlier stage
that makes that kind of data, or to `null` when the data does not come from this
run. Nothing is connected implicitly: a stage sees only the artifacts of the
stages its inputs name.

| Stage | `inputs` | `null` means | Makes |
| --- | --- | --- | --- |
| `production` | `null` (no slots) | - | `tuples` |
| `plots` | `{tuples: <id or null>}` | the tuples already in `$PICODIR` of `pico.config` | `plots` |
| `histograms` | `{tuples: <id or null>}` | the same | `shapes` |
| `fit` | `{shapes: <id or null>}` | the shapes already in `Fitter/input_pt_less_region/` (made before) | `fit`, `corrections` |
| `python` | `null`, or `{<any name>: <id>, ...}` | no inputs (a named input must name a stage) | anything |

Stage options sit directly beside these keys; there is no `options:` wrapper.
`split` and `merge` are nested mappings inside `production`.

```yaml
stages:
  - stage: production
    id: production
    inputs: null
    eras: ["2025"]
    channels: [mutau]
    split:
      nfilesperjob: 2
      maxevts: null
```

Unknown keys, missing required stage options, missing or duplicate ids,
missing or wrong inputs, duplicate or out-of-order stages, and the
stage-specific value checks are reported before execution, **all of them at
once**. Each problem names its location:

```text
my_mutau.yml: 2 problems
  stages[0] (production): unknown option 'samplez' ...
  stages[1] (plots).inputs.tuples: no stage 'prodution' in the recipe
```

`taufw.py check <bundle>` lists every problem without running anything, and
also checks the files the recipe names: `pico.config`, absolute paths and python
step files (configs a module resolves, such as `TauES_ID/config/...`, are checked
by `plan`). It exits with 1 if there is a problem. The menu runs the same check:
a recipe with problems is red in the list and its preview lists them; it cannot
be started. [example_broken](example_broken/recipe.yml) shows what this looks like.

Validation does not establish that every input exists, that a physics
setup is suitable, or that batch submission will work. `plan` also checks local
stage prerequisites and displays problems as warnings where a command plan can
still be built. Review both the commands and warnings before starting.

## Paths and configuration

The path options of the stages (`plots.configs`, `histograms.configs`,
`fit.config`, `fit.config_mumu`, a python step's `file`) and `pico.config`
follow one rule:

| Value | Resolution | `plan` shows |
| --- | --- | --- |
| Absolute path | Used as is. | `absolute` |
| Relative path of a file in the bundle | That bundle file, e.g. `config_coarse_TT.yml` next to `recipe.yml`. | `bundle` |
| Any other relative path | Unchanged: the module resolves it as before, relative to `Fitter/` (e.g. `TauES_ID/config/config_coarse_TT.yml`) or `Plotter/` (e.g. `config/setup_mutau.yml`). | `module` |
| `plots.configs` channel name | `mutau` selects `Plotter/config/setup_mutau.yml`. | `module` |

A bundle file **replaces** the module's config as a whole: the script reads the
bundle's copy instead, nothing is merged. `taufw.py plan` lists every file each
stage reads and where it comes from, so check it after changing a path.

Other paths:

| Value | Resolution |
| --- | --- |
| CLI recipe/bundle path, run-directory path, `--run-root` | Relative to the directory where you launch `taufw.py`. |
| Relative `pico.config` | A file of the bundle (the recipe's directory), e.g. `pico.json`; a path above it (`../`) is made absolute when the recipe is loaded and is not copied into runs. |
| Plotter/Fitter outputs | Written in the package directories, regardless of `--run-root`. |

**A run reads its own copy of the bundle.** `start` copies the bundle (every
file of the directory, without hidden files, `__pycache__` and `taufw_runs/`) to
`taufw_runs/<run>/bundle/`, and all stages of that run read the copy. Editing a
bundle file after `start` does not change the run, just as editing the recipe
does not. Keep data files outside the bundle: a bundle above 50 MB is refused.
For a loose recipe file outside a bundle, only the files its options name are
copied.

`config: null` uses PicoProducer's normal default
`PicoProducer/config/config.json`. That configuration supplies sample catalogs,
channels, storage paths, and batch defaults; recipes select and override job
settings rather than defining those catalogs themselves. See the
[PicoProducer documentation](../PicoProducer/README.md) and
[public API](../docs/PicoProducer/API.md). A bundle may carry its own copy:

```yaml
pico:
  config: pico.json   # a file of this bundle
```

**The local stages read the tuples through the run's PicoProducer
configuration.** The Plotter and histogram scripts find tuples through
`$PICODIR`. The Framework passes the run's configuration to every command (and
python step) as `$TAUFW_PICO_CONFIG`, which PicoProducer's `getconfig()` reads
instead of `PicoProducer/config/config.json` (read-only; a missing file is an
error). `plan` shows the variable in front of each command. A production output
tag does not automatically become a plotting input tag; check the configs when
selecting tagged or variation tuples.

## Stage options

The tables list every currently supported recipe option. Defaults apply when
an option is omitted. `null` has the meaning described for each option; do not
use it as a replacement for a required list or a boolean.

### `production`

Runs the public PicoProducer job API: plan, submit, check, resubmit, and merge.
Required `eras` and `channels` must be non-empty and match the PicoProducer
configuration. Use lists even for a single selection.

| Option | Default | Meaning |
| --- | --- | --- |
| `eras` | Required | Eras in the PicoProducer configuration. |
| `channels` | Required | Configured processing channels/modules. |
| `samples` | `[]` | Sample-name glob patterns to include; empty means no name filter. |
| `vetoes` | `[]` | Sample-name glob patterns to exclude. |
| `dtypes` | `[mc, data, embed]` | Sample types to process. |
| `dasfilters` | `[]` | DAS dataset-path glob patterns to include. |
| `dasvetoes` | `[]` | DAS dataset-path glob patterns to exclude. |
| `tag` | `""` | Extra job/output-name tag; a leading `_` is added if absent. |
| `extraopts` | `[]` | Module options as `KEY=VALUE` strings; precedence is channel options < sample options < these overrides. |
| `split.nfilesperjob` | `null` | Files per job; unset falls back to the sample setting, then configuration. |
| `split.maxevts` | `null` | Events per job; values greater than 1 enable event splitting. Unset uses sample/configuration settings. |
| `queue` | `null` | Batch queue, such as HTCondor job flavour; unset uses configuration. |
| `time` | `null` | Maximum batch run time passed to PicoProducer. |
| `batchopts` | `null` | Extra batch options passed to PicoProducer. |
| `prefetch` | `false` | Copy input files before processing. |
| `preselect` | `null` | Skim preselection expression. |
| `dasfiles` | `false` | Get input-file lists from DAS. |
| `checkdas` | `false` | Check DAS event counts during status checking. |
| `checkevts` | `true` | Validate output event counts during status checking. |
| `checkexpevts` | `null` | Whether to compare output to expected event counts; unset delegates to PicoProducer's policy. |
| `ncores` | `4` | Parallel workers for output validation. |
| `verbosity` | `0` | PicoProducer request verbosity. |
| `max_tries` | `3` | Total submission attempts, including the first; must be at least 1. |
| `merge.clean` | `false` | Remove job files and job output after a validated merge. |
| `merge.force` | `false` | Pass force to PicoProducer's merge operation, allowing incomplete samples at merge time. |

`max_tries: 3` permits the initial submission and two resubmissions. While any
chunks are queued or running, production waits; it resubmits failed or missing
chunks after no chunks remain pending. Once all chunks succeed, it merges each
sample and records the resulting tuple. No matching samples fails the stage.

`merge.force` does not bypass this retry policy: the Framework still waits for
completion before entering its merge step. It is not a recipe switch to skip
failed jobs immediately. `merge.clean` performs actual cleanup, so enable it
when you intend to remove the intermediate job files after validation.

### `plots`

Runs `Plotter/plot.py` locally, once per config and era, through
`TauFW.Plotter.api.ControlPlots`. This is the pipeline's control-plot stage;
the `plots` entry in `fit.steps` instead makes plots of fit results.

| Option | Default | Meaning |
| --- | --- | --- |
| `eras` | Required | Non-empty eras; forwarded as `plot.py -y`. |
| `configs` | `[mutau]` | Non-empty channel names, bundle files, or setup `.yml` paths relative to `Plotter/`; `-c`. |
| `variables` | `[]` | Variable glob filters; `-V`. Empty selects all variables defined by the script. |
| `selections` | `[]` | Selection glob filters; `-S`. Empty includes baseline and the setup's regions. |
| `serial` | `false` | Serial processing; `-s`. |
| `fraction` | `false` | Fraction stack in the ratio plot; `-F`. |
| `pdf` | `false` | Also save PDF files; `-p`. |
| `notauidsf` | `false` | Remove DeepTau ID scale factors; `-r`. |
| `tag` | `""` | Plot tag; `-t`. |
| `text` | `""` | Additional plot text; `-T`. |
| `timeout` | `null` | Seconds allowed per command; unset means no time limit. |

Plots are written under `Plotter/plots/<era>/`. The run records one artifact
per channel setup and era, including the directory and matching file count.
The selected setup controls the physics samples and regions; a production
sample filter does not automatically restrict the Plotter's sample collection.

### `histograms`

Creates the input shapes for the combined TES + tau ID fit. It wraps the
`Fitter/run_inputs.sh` workflow via `TauFW.Fitter.api.TauESID.make_shapes`, running
`TauES/createinputsTES.py` locally for every era, jet WP, electron WP, and config.

| Option | Default | Meaning |
| --- | --- | --- |
| `eras` | Required | Non-empty eras; `-y`. |
| `jet_wps` | Required | Non-empty DeepTau VSjet working points, for example `[VTight]`; `-j`. |
| `ele_wps` | Required | Non-empty DeepTau VSe working points, for example `[Tight]`; `-e`. |
| `configs` | `[TauES_ID/config/config_coarse_TT.yml, TauES/config/FitSetup_mumu.yml]` | Non-empty configs (bundle files, or relative to `Fitter/`): by default the mutau fit and mumu control region. |
| `serial` | `false` | Serial shape creation; `-s`. |
| `timeout` | `null` | Seconds per shape-creation command; unset means no time limit. |

The lists form a Cartesian product. Two eras, two jet WPs, one electron WP,
and two configs produce eight shape-creation commands. Each command can write
multiple shape files according to its config's observables.

Shapes go under
`Fitter/input_pt_less_region/againstjet_<J>/againstelectron_<E>/`.
The fit configs define the observables, regions, processes, and systematic
variations. Required TES, lepton-to-tau fake (LTF), and jet-to-tau fake (JTF)
variation tuples must already be available; this stage does not produce them.

### `fit`

Runs the combined TES + tau ID workflow represented by
`Fitter/run_workflow_zmm.sh`, through `TauFW.Fitter.api.TauESID.fit`. The wrapped
variant is option 3: a two-dimensional scan of `tes` and `tid_SF` by decay mode
and transverse-momentum region, with the Z→μμ control region.

| Option | Default | Meaning |
| --- | --- | --- |
| `config` | `TauES_ID/config/config_coarse_TT.yml` | Mutau fit config (a bundle file, or relative to `Fitter/`). |
| `config_mumu` | `TauES/config/FitSetup_mumu.yml` | Mumu control-region config (a bundle file, or relative to `Fitter/`). |
| `eras` | `[]` | Eras to fit; when inferring points, empty allows every upstream era. |
| `jet_wps` | `[]` | VSjet working points; empty together with `ele_wps` means infer points from this run's histogram artifacts. |
| `ele_wps` | `[]` | VSe working points; supply both WP lists or leave both empty. |
| `steps` | `[fit, postfit, plots, corrections, summary]` | Non-empty selection of workflow steps, described below. |
| `impacts` | `true` | Include impact calculations in the `postfit` step; these can be slow. |
| `timeout` | `null` | Seconds per command, not per working point or entire stage. |

### `python`

Runs a Python file of the bundle as a step; see [Python steps](#python-steps).

| Option | Default | Meaning |
| --- | --- | --- |
| `file` | Required | The step file: a bundle file such as `steps/fit_summary.py` (or an absolute path). |
| `function` | `run` | The function to call, defined at the top level of the file. |
| `options` | `{}` | Any mapping; the step gets it as `ctx.options`. Must be writable as JSON. |
| `timeout` | `null` | Seconds for the step; unset means no time limit. |

## Python steps

A python step runs a function of a Python file in the bundle, in its own Python
process, after the stages before it. It can read the artifacts of the stages
its inputs name, write its own files, and return artifacts for the stages after
it.

```yaml
  - stage: python
    id: fit_summary
    inputs: {fit: fit}        # the input 'fit' is the stage with id fit
    file: steps/fit_summary.py
    options: {pois: [tes, tid_SF]}
```

```python
# steps/fit_summary.py
def run(ctx):
    fits = ctx.input('fit', kind='fit')              # the artifacts of the stage connected to 'fit'
    path = os.path.join(ctx.stage_dir, 'summary.txt')
    ...                                              # write the table
    ctx.log("wrote %s" % path)
    return {'message': "%d points" % len(fits), 'artifacts': [{'kind': 'table', 'path': path}]}
```

The function gets one argument, `ctx`:

| Attribute | Meaning |
| --- | --- |
| `ctx.options` | The step's `options:` (a dict). |
| `ctx.input(name, kind=None)` | Artifacts of the stage connected to the input `name`, optionally of one `kind`. An input the recipe does not give is an error. |
| `ctx.artifacts(stage=None, kind=None)` | Artifacts of the input stages by stage id (or all of them), optionally of one `kind`. |
| `ctx.inputs` | The step's inputs: name → stage id. |
| `ctx.stage_dir` | `taufw_runs/<run>/stages/<id>/`, for the step's own files (exists); nothing else is written there except the stage's `manifest.json` when it is done. |
| `ctx.path(relative)` | A file of the run's bundle copy, e.g. `ctx.path('config_coarse_TT.yml')`. |
| `ctx.log(message)` | One line in the step's log. |
| `ctx.run_dir`, `ctx.bundle_dir`, `ctx.stage_id`, `ctx.pico_config`, `ctx.upstream` | The run directory, the bundle copy, the step's id, the run's PicoProducer config (also `$TAUFW_PICO_CONFIG`), the artifacts of the input stages. |

The return value is `None`, a list of artifacts (dicts), or
`{'message': ..., 'artifacts': [...]}`. The message becomes the stage's message;
the artifacts are saved in `run.json` and passed to the later stages. Everything
must be writable as JSON.

How a step runs:

- `Framework/python/step_runner.py` runs it with the same Python as
  `taufw.py`, in the run's bundle copy as working directory. The step's
  directory comes first on `sys.path`, so it can import the files next to it.
  The step runner itself needs only the standard library; a step that uses
  TauFW or ROOT imports them itself (after `cmsenv`).
- Before it runs, `plan` and `advance` check that the file exists, that it
  defines the function (without importing it), and that the options can be
  written as JSON. A problem leaves the step `NEW`, like any preflight problem.
- Its output goes to `taufw_runs/<run>/logs/<id>/01_<id>.log`, next to
  `context.json` (what the step was given) and `result.json` (what it
  returned). An exception, or a return value that is not valid, makes the step
  `FAILED` with the traceback in the log.

## Choosing fit working points and steps

There are two ways to select fit points:

1. **Infer them from this run's histograms.** Connect `inputs: {shapes: <histograms id>}`
   and leave `jet_wps` and `ele_wps` empty. A point is selected only if the input shape artifacts contain both
   `config` and `config_mumu` for that era and WP pair. `eras: []` accepts all
   upstream eras; a non-empty `eras` filters them. Config values must match the
   histogram artifact config values, so update both stages if you change configs.
2. **Specify a grid.** Set both WP lists. The fit uses
   `eras × jet_wps × ele_wps`. If `eras` is empty, it takes eras from upstream
   histogram artifacts. For a fit-only recipe, supply eras explicitly because
   there are no upstream artifacts to infer them from.

Inference uses artifacts of the stage `inputs.shapes` names in the same run, not a search
of arbitrary shape files already on disk or another run's `run.json`. If no
points can be selected, planning reports the problem and starting the fit fails.

A complete fit-only recipe for existing shapes is:

```yaml
name: tes_id_2025_existing_shapes
stages:
  - stage: fit
    id: fit
    inputs: {shapes: null}    # the shapes already in Fitter/
    eras: ["2025"]
    jet_wps: [VTight]
    ele_wps: [Tight]
    config: TauES_ID/config/config_coarse_TT.yml
    config_mumu: TauES/config/FitSetup_mumu.yml
    steps: [fit, postfit, plots, corrections, summary]
    impacts: false
```

Fit steps execute in the order below, regardless of their order in `steps`:

| Step | Work performed |
| --- | --- |
| `fit` | Create mumu datacards and run the combined MultiDimFit scan. |
| `postfit` | Run FitDiagnostics and make post-fit shapes; include impacts when enabled. |
| `plots` | Make post-fit plots, combine plot outputs, and plot measurements. |
| `corrections` | Export ROOT and JSON correction files with `createroot_TES.py`. |
| `summary` | Once per selected era after the WP loop: make grids, merge JSON corrections, plot NLL profiles, and produce the combined TES + ID result. |

Selecting a later step does not automatically run its prerequisites. For
example, `steps: [corrections, summary]` requires the earlier fit results to
already exist on disk. This can be used in a new recipe/run to process existing
results. The summary scripts use working points found on disk, so their scope
can exceed the WP lists in this recipe.

## Planning, starting, and continuing a run

Set up the Linux CMS/CMSSW environment first (see
[installation](../README.md#installation) and
[FastSetup](../docs/FastSetup.md)). After `cmsenv` and `scram b`, `taufw.py`
is available on `PATH`; from the repository root you can also use
`python3 taufw.py`. Fits require ROOT, the Combine tools, and CombineHarvester
for the fit step. Local-stage preflight reports missing prerequisites.

From the repository root:

```bash
# Inspect selected samples/jobs, the files each stage reads and the local-stage
# commands. Nothing executes.
python3 taufw.py plan Analyses/example_mutau

# Create a run and execute every stage that can proceed now.
python3 taufw.py start Analyses/example_mutau
```

`start` prints the actual run directory. Use that directory for further commands:

```bash
python3 taufw.py status taufw_runs/mutau_2022_postEE_20261013-120000
python3 taufw.py advance taufw_runs/mutau_2022_postEE_20261013-120000

# Repeated checks while waiting for batch jobs (default interval: 600 seconds).
python3 taufw.py advance taufw_runs/mutau_2022_postEE_20261013-120000 --wait --poll 900
```

The example timestamp above is illustrative; substitute the path printed by
your `start` command. `--wait` and `--poll` also work on `start`.
`start --run-root /path/to/runs` changes where run records and command logs live.
`status` reads recorded and live state without submitting jobs or saving changes.
CLI `-v`/`--verbose [N]` controls reporter verbosity; production `verbosity` is
a separate recipe option passed in the PicoProducer request.

**`plan --local` executes a small production test.** Unlike ordinary `plan`, it
runs locally on one input file from the first matching sample for each era and
channel, with 100 events by default:

```bash
python3 taufw.py plan Analyses/example_mutau --local -m 50
```

It creates no Framework run record, does not execute the later stages, and needs
a `production` entry. It can write local processing output. It does not test
every matching sample.

Running `python3 taufw.py` without arguments in an interactive Linux terminal
opens the optional console menu. It can select recipes, show a plan before
starting, continue saved runs, and inspect status. See the
[Framework quick start](../Framework/README.md#quick-start) for menu controls.

Production normally submits and returns while waiting for jobs. Once it
finishes, an `advance` can merge tuples and start all following local stages in
the same call. Plots, histograms, fit, and python step commands run sequentially on the
current machine and can keep a single `start` or `advance` busy for hours even
without `--wait`; that flag controls batch polling, not local execution.

The recipe is saved into the run record and the bundle is copied into the run
directory. Editing the source YAML or a bundle file later does not change an
existing run: `advance` uses the saved recipe and the run's bundle copy. Start a
new run to apply changes. Completed stages are skipped, and a `FAILED` run is
final.

## Outputs and logs

Each run has its own record and logs:

```text
taufw_runs/<name>_<YYYYmmdd-HHMMSS>/
  run.json
  run.log
  bundle/                     the run's copy of the bundle (what the stages read)
  logs/<stage id>/            the command logs NN_<label>.log; a python step: also context.json, result.json
  stages/<stage id>/          the stage's output: a python step's own files, and manifest.json when DONE
```

A stage's directories are made when it runs; `stages/<id>/manifest.json`
exists only for a stage that finished (`DONE`): it names the run, the stage,
its inputs and its artifacts. `run.log` contains
Framework messages; each command log contains its working directory, command
line, output, exit code, duration, and any missing expected outputs.
`run.json` stores the recipe, configuration snapshot, the list of copied bundle
files, stage state, submission attempts, artifacts, history, and local command
results.

| Stage | Output location | Recorded artifacts |
| --- | --- | --- |
| `production` | PicoProducer's configured tuple paths | Merged tuple path, sample/group, era, channel, tag, data type, event count, tree, cutflow. |
| `plots` | `Plotter/plots/<era>/` | `kind: plots`, era, config, channel, directory, matching file count. |
| `histograms` | `Fitter/input_pt_less_region/againstjet_<J>/againstelectron_<E>/` | `kind: shapes`, path, era, channel, config, WP pair, observable. |
| `fit` | Fitter's `output_*`, `postfit_*`, plot directories, and `tau_sf/` | `kind: fit` per point, output/postfit directories, fitted values, correction paths; `kind: corrections` per era when summary runs. |
| `python` | `taufw_runs/<run>/stages/<id>/` (`ctx.stage_dir`) | What the step returns. |

Fit values include the region, parameter of interest, central value, and lower
and upper interval limits, parsed from `FitparameterValues_*.txt`.
`taufw.py status` displays them as a table.

A local command succeeds only when its exit code is zero and its expected
outputs were written after it started. An old output file alone is insufficient.
This catches failures inside scripts that do not propagate a nested tool's
exit code. The first failed command stops the local stage, and the Framework
prints the last 20 lines of its log.

## Troubleshooting

| Symptom | What to check or do |
| --- | --- |
| A recipe is red in the menu, or `RecipeError` | Run `taufw.py check <bundle>`: it lists every problem with its location. |
| Unknown key or missing required option | Check indentation and the option tables. Put options beside `stage`; use `split`/`merge` mappings only under production. |
| Missing `id` or `inputs` | Every stage needs both. A stage without inputs says `inputs: null`; a slot whose data was made before this run says `null` (`inputs: {tuples: null}`). |
| `no stage 'x' in the recipe` / `comes after this one` / `makes ..., not ...` | An input names a stage **id** (not a type or description) of an **earlier** stage that makes that kind of data (fit `shapes` ← a histograms stage). |
| Invalid stage order or duplicate stage | Keep the supported order and combine selections into the stage's lists, or use separate recipes. Every stage needs its own unique `id`. |
| A config change has no effect | Run `plan` and check the `from` column: `module` means the file is not in the bundle (typo in the path), so the module's own config is used. |
| Python step `NEW` with "no top-level function" | Define `def run(ctx):` at the top level of the file, or set `function:`. |
| Python step `FAILED` | Read `taufw_runs/<run>/logs/<id>/01_<id>.log` for the traceback; `context.json` next to it shows what the step was given. |
| No samples match production | Inspect `plan`, configured era/channel catalogs, sample/DAS filters, vetoes, and `dtypes`. |
| Production stays `WAITING` | Inspect live job status; pending/running chunks delay resubmission of failed chunks. Continue with `advance`, or use `--wait`. |
| Production fails after the allowed tries | Inspect PicoProducer job logs and fix the cause. The failed run cannot be restarted by editing its recipe; start a new run with the corrected setup. |
| Local stage stays `NEW` with a preflight message | Fix the named missing environment/tool/config/input, then call `advance` on the same run. |
| No working points to fit | Connect `inputs: {shapes: <histograms id>}` to a histograms stage with both matching configs, or explicitly set eras and both WP lists for existing shapes (`shapes: null`). |
| Plots/histograms read unexpected or missing tuples | Check `$PICODIR` in the run's PicoProducer configuration (`pico.config`, shown by `plan`), channel/setup naming, tags, and required variation tuples. |
| Exit code zero but the local stage fails | Read the command log for missing/stale expected outputs and nested ROOT/Combine failures. |
| Editing YAML or a bundle file does not affect `advance` | The run uses the recipe stored in `run.json` and its bundle copy; start a new run to use edited settings. |

Preflight problems leave a local stage `NEW`, so they can be fixed and retried
in the same run. A command failure leaves it `FAILED`, which is terminal. An
exception such as an unavailable scheduler is recorded without changing the
stage state; retry `advance` after fixing the external problem. The CLI returns
exit code 1 for a failed run; use status/messages to distinguish completion from
an unfinished run.

## Current limitations

- Plotter and Fitter outputs are shared between runs in the same package
  directories. Concurrent runs can clash and later runs can overwrite earlier
  outputs. Run records contain paths, not independent copies of those results;
  `--run-root` does not isolate them.
- The sample lists are not part of a bundle yet: `plot.py` and
  `createinputsTES.py` import `Plotter/config/samples_v15.py`, and the
  PicoProducer configuration names its own sample catalogs
  (`PicoProducer/samples/samples_<era>.py`).
- TES, LTF, and JTF variation tuples need their own PicoProducer channels (for
  example `mutau_TES0p950`) and currently their own production runs. A nominal
  production stage alone does not prepare all histogram inputs.
- Local stages do not resume partway through their commands. A failed stage is
  final; Ctrl+C can leave a local stage `NEW` with partial output, and advancing
  again reruns that stage. Interrupting the CLI does not cancel submitted batch
  jobs; keep the saved run directory for continuation.
- The wrapped fit supports the uncorrelated DeepTau option-3 workflow. `corrTES`,
  `fullcorr`, PNet, and UParT variants are not exposed as recipe options.
- Summary scripts consider working points already on disk, including outputs
  from other runs. Review the output area before producing a summary.
