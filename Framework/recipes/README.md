# TauFW recipes

A recipe describes one analysis pipeline: which stages to run, which samples and
eras to use, and the options for each stage. The Framework reads the file, checks
its structure, and calls the public PicoProducer, Plotter, and Fitter APIs. A
recipe can produce new pico tuples or start from existing tuples or fit shapes.

This is the recipe authoring and usage reference. For the Framework's state
machine, Python API, and run-record internals, see the
[Framework README](../README.md).

- [Bundled recipes](#bundled-recipes)
- [Writing your first recipe](#writing-your-first-recipe)
- [File format and validation](#file-format-and-validation)
- [Paths and configuration](#paths-and-configuration)
- [Stage options](#stage-options)
- [Choosing fit working points and steps](#choosing-fit-working-points-and-steps)
- [Planning, starting, and continuing a run](#planning-starting-and-continuing-a-run)
- [Outputs and logs](#outputs-and-logs)
- [Troubleshooting](#troubleshooting)
- [Current limitations](#current-limitations)

## Bundled recipes

| File | Pipeline | Inputs and purpose |
| --- | --- | --- |
| [example_mutau.yml](example_mutau.yml) | `production` → `plots` | Produce `2022_postEE` mutau tuples for sample names matching `DY*` or `TT*`, then make control plots. |
| [tes_id_2025.yml](tes_id_2025.yml) | `plots` → `histograms` → `fit` | Use existing 2025 tuples for the combined tau energy scale (TES) and tau ID scale factor fit, with the Z→μμ control region; DeepTau VSjet `VTight`, VSe `Tight`. |

Copy the closest example and adjust it for your analysis. The examples require
the corresponding sample catalog, channel definitions, tuple files, and physics
configs in your environment; they are not self-contained input datasets.

The optional interactive menu discovers `.yml`, `.yaml`, and `.json` files in
this directory. Recipes elsewhere work too: select another path in the menu or
pass the path to the command line.

## Writing your first recipe

For production alone, save a file such as `Framework/recipes/my_mutau.yml`:

```yaml
name: my_mutau_2022_postEE
pico:
  config: null
stages:
  - stage: production
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
    eras: [2022_postEE]
    configs: [mutau]
    variables: [m_vis, pt_1, pt_2]
    selections: [baseline]
```

Each stage has its own options. Setting `eras` on production does not set the
eras for plots or histograms. Likewise, production `channels: [mutau]` and plot
`configs: [mutau]` belong to different packages and serve different purposes.

For plots of tuples you already have, omit the production entry entirely. For
shape creation and a fit on existing tuples, use
[tes_id_2025.yml](tes_id_2025.yml). For a fit on existing shapes, use the explicit
working-point example [below](#choosing-fit-working-points-and-steps).

## File format and validation

Recipes accept `.yml`, `.yaml`, or `.json`. YAML is convenient for comments; JSON
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
| `stages` | Required | Non-empty list of stage mappings. Each entry needs a `stage` name and that stage's options. |

The available stages must appear in this order:

```text
production → plots → histograms → fit
```

Any non-empty subset is allowed, but a stage may occur only once. For example,
`histograms` followed by `fit` is valid, while `fit` followed by `histograms`, or
two separate `production` entries, is invalid. Put multiple eras, channels,
configs, or working points in a single stage's lists. Use separate recipes when
you need independent production settings.

Stage options sit directly beside `stage`; there is no `options:` wrapper.
`split` and `merge` are nested mappings inside `production`.

```yaml
stages:
  - stage: production
    eras: ["2025"]
    channels: [mutau]
    split:
      nfilesperjob: 2
      maxevts: null
```

Unknown keys, missing required stage options, duplicate or out-of-order stages,
and the stage-specific value checks are reported before execution. Errors name
the recipe and offending location, for example:

```text
my_mutau.yml: stages[0] (production): unknown option 'samplez' ...
```

Schema validation does not establish that every input exists, that a physics
setup is suitable, or that batch submission will work. `plan` also checks local
stage prerequisites and displays problems as warnings where a command plan can
still be built. Review both the commands and warnings before starting.

## Paths and configuration

Different paths have different bases:

| Value | Resolution |
| --- | --- |
| CLI recipe path, run-directory path, `--run-root` | Relative to the directory where you launch `taufw.py`. |
| Non-null relative `pico.config` | Relative to the recipe file's directory; made absolute when the file is loaded. |
| `plots.configs` channel name | `mutau` selects `Plotter/config/setup_mutau.yml`. |
| `plots.configs` file path | Relative to `Plotter/`, for example `config/setup_mutau.yml`. |
| `histograms.configs`, `fit.config`, `fit.config_mumu` | Relative to `Fitter/`, for example `TauES_ID/config/config_coarse_TT.yml`. |
| Plotter/Fitter outputs | Written in the package directories, regardless of `--run-root`. |

For a recipe in this directory, an explicit production configuration would be:

```yaml
pico:
  config: ../../PicoProducer/config/config.json
```

`config: null` uses PicoProducer's normal default
`PicoProducer/config/config.json`. That configuration supplies sample catalogs,
channels, storage paths, and batch defaults; recipes select and override job
settings rather than defining those catalogs themselves. See the
[PicoProducer documentation](../../PicoProducer/README.md) and
[public API](../../PicoProducer/docs/API.md).

**Tuple lookup in local stages currently uses the default configuration.**
The Plotter and histogram scripts find tuples through `$PICODIR` from
`PicoProducer/config/config.json`. They do not switch to a custom `pico.config`
or take the production artifact paths as their file inputs. The Framework
records upstream tuples and warns about a differing configuration, but you must
ensure the scripts' default configuration points to the intended tuples. A
production output tag also does not automatically become a plotting input tag;
check the package configs when selecting tagged or variation tuples.

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
| `configs` | `[mutau]` | Non-empty channel names or setup `.yml` paths relative to `Plotter/`; `-c`. |
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
| `configs` | `[TauES_ID/config/config_coarse_TT.yml, TauES/config/FitSetup_mumu.yml]` | Non-empty configs relative to `Fitter/`: by default the mutau fit and mumu control region. |
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
| `config` | `TauES_ID/config/config_coarse_TT.yml` | Mutau fit config, relative to `Fitter/`. |
| `config_mumu` | `TauES/config/FitSetup_mumu.yml` | Mumu control-region config, relative to `Fitter/`. |
| `eras` | `[]` | Eras to fit; when inferring points, empty allows every upstream era. |
| `jet_wps` | `[]` | VSjet working points; empty together with `ele_wps` means infer points from this run's histogram artifacts. |
| `ele_wps` | `[]` | VSe working points; supply both WP lists or leave both empty. |
| `steps` | `[fit, postfit, plots, corrections, summary]` | Non-empty selection of workflow steps, described below. |
| `impacts` | `true` | Include impact calculations in the `postfit` step; these can be slow. |
| `timeout` | `null` | Seconds per command, not per working point or entire stage. |

## Choosing fit working points and steps

There are two ways to select fit points:

1. **Infer them from this run's histograms.** Leave `jet_wps` and `ele_wps`
   empty. A point is selected only if upstream shape artifacts contain both
   `config` and `config_mumu` for that era and WP pair. `eras: []` accepts all
   upstream eras; a non-empty `eras` filters them. Config values must match the
   histogram artifact config values, so update both stages if you change configs.
2. **Specify a grid.** Set both WP lists. The fit uses
   `eras × jet_wps × ele_wps`. If `eras` is empty, it takes eras from upstream
   histogram artifacts. For a fit-only recipe, supply eras explicitly because
   there are no upstream artifacts to infer them from.

Inference uses artifacts of the `histograms` stage in the same run, not a search
of arbitrary shape files already on disk or another run's `run.json`. If no
points can be selected, planning reports the problem and starting the fit fails.

A complete fit-only recipe for existing shapes is:

```yaml
name: tes_id_2025_existing_shapes
stages:
  - stage: fit
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
[installation](../../README.md#installation) and
[FastSetup](../../docs/FastSetup.md)). After `cmsenv` and `scram b`, `taufw.py`
is available on `PATH`; from the repository root you can also use
`python3 taufw.py`. Fits require ROOT, the Combine tools, and CombineHarvester
for the fit step. Local-stage preflight reports missing prerequisites.

From the repository root:

```bash
# Inspect selected samples/jobs and local-stage commands. Nothing executes.
python3 taufw.py plan Framework/recipes/example_mutau.yml

# Create a run and execute every stage that can proceed now.
python3 taufw.py start Framework/recipes/example_mutau.yml
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
python3 taufw.py plan Framework/recipes/example_mutau.yml --local -m 50
```

It creates no Framework run record, does not execute the later stages, and needs
a `production` entry. It can write local processing output. It does not test
every matching sample.

Running `python3 taufw.py` without arguments in an interactive Linux terminal
opens the optional console menu. It can select recipes, show a plan before
starting, continue saved runs, and inspect status. See the
[Framework quick start](../README.md#quick-start) for menu controls.

Production normally submits and returns while waiting for jobs. Once it
finishes, an `advance` can merge tuples and start all following local stages in
the same call. Plots, histograms, and fit commands run sequentially on the
current machine and can keep a single `start` or `advance` busy for hours even
without `--wait`; that flag controls batch polling, not local execution.

The recipe is saved into the run record. Editing the source YAML later does
not change an existing run: `advance` uses the saved recipe. Start a new run to
apply recipe changes. Completed stages are skipped, and a `FAILED` run is final.

## Outputs and logs

Each run has its own record and logs:

```text
taufw_runs/<name>_<YYYYmmdd-HHMMSS>/
  run.json
  run.log
  plots/NN_<label>.log
  histograms/NN_<label>.log
  fit/NN_<label>.log
```

Only the selected local stages create their log directories. `run.log` contains
Framework messages; each command log contains its working directory, command
line, output, exit code, duration, and any missing expected outputs.
`run.json` stores the recipe, configuration snapshot, stage state, submission
attempts, artifacts, history, and local command results.

| Stage | Output location | Recorded artifacts |
| --- | --- | --- |
| `production` | PicoProducer's configured tuple paths | Merged tuple path, sample/group, era, channel, tag, data type, event count, tree, cutflow. |
| `plots` | `Plotter/plots/<era>/` | `kind: plots`, era, config, channel, directory, matching file count. |
| `histograms` | `Fitter/input_pt_less_region/againstjet_<J>/againstelectron_<E>/` | `kind: shapes`, path, era, channel, config, WP pair, observable. |
| `fit` | Fitter's `output_*`, `postfit_*`, plot directories, and `tau_sf/` | `kind: fit` per point, output/postfit directories, fitted values, correction paths; `kind: corrections` per era when summary runs. |

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
| Unknown key or missing required option | Check indentation and the option tables. Put options beside `stage`; use `split`/`merge` mappings only under production. |
| Invalid stage order or duplicate stage | Keep the supported order and combine selections into the stage's lists, or use separate recipes. |
| No samples match production | Inspect `plan`, configured era/channel catalogs, sample/DAS filters, vetoes, and `dtypes`. |
| Production stays `WAITING` | Inspect live job status; pending/running chunks delay resubmission of failed chunks. Continue with `advance`, or use `--wait`. |
| Production fails after the allowed tries | Inspect PicoProducer job logs and fix the cause. The failed run cannot be restarted by editing its recipe; start a new run with the corrected setup. |
| Local stage stays `NEW` with a preflight message | Fix the named missing environment/tool/config/input, then call `advance` on the same run. |
| No working points to fit | Add a histograms stage with both matching configs, or explicitly set eras and both WP lists for existing shapes. |
| Plots/histograms read unexpected or missing tuples | Check `$PICODIR` in the default PicoProducer configuration, channel/setup naming, tags, and required variation tuples. |
| Exit code zero but the local stage fails | Read the command log for missing/stale expected outputs and nested ROOT/Combine failures. |
| Editing YAML does not affect `advance` | The run uses the recipe stored in `run.json`; start a new run to use edited settings. |

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
- Local scripts use `$PICODIR` from the default PicoProducer configuration, even
  when production uses another `pico.config`.
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
