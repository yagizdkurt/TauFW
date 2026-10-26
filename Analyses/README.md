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
structure, and calls the public PicoProducer, Histogrammer, and Fitter APIs, and the
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
| [example_mutau_short](example_mutau_short/recipe.yml) | `production` | Produce `2022_postEE` mutau tuples for sample names matching `DY*` or `TT*`: a quick production example (no plots: a few MC samples without data are not enough for them). |
| [example_mutau_long](example_mutau_long/recipe.yml) | `production` → `controlhists` → `controlplots` | Produce every `2022_postEE` mutau tuple the control plots read (data and the 22 MC samples of its `v15_2022_postEE.yml`), then the plots; `plan` checks that production makes every sample the plots ask for. A full production: tens of GB, hours of batch jobs. |
| [example_broken](example_broken/recipe.yml) | (invalid on purpose) | A demonstration of the validation: `taufw.py check Analyses/example_broken` lists its four problems; the menu shows it in red. Do not fix it. |
| [tes_id_2025](tes_id_2025/recipe.yml) | `controlhists` → `controlplots` → `shapes` → `fit` → `fit_summary` (python) | Use existing 2025 tuples for the combined tau energy scale (TES) and tau ID scale factor fit, with the Z→μμ control region; DeepTau VSjet `VTight`, VSe `Tight`; then a table of the fitted values. |

Each bundle carries copies of the Histogrammer and Fitter configs it uses, next to
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

`init --from` copies every file of the source bundle (its configs, its copies
of `Configs/` templates with their `taufw_config` header, its Python steps) to
the same place in the new bundle, and every Histogrammer or Fitter config the recipe
takes from its module next to the new `recipe.yml` (a name that is taken
becomes `plotter_<name>` or `fitter_<name>`), pointing the new recipe at those
copies, so you can edit them without touching the modules. From a loose recipe
file, only the files its options name are copied. Comments of the source recipe
are not kept.

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

To make control plots after production, append these two entries under the
same `stages:` list. The Histogrammer fills the histograms and writes them to a
file; the Plotter draws that file:

```yaml
  - stage: controlhists
    id: hists
    inputs: {tuples: production}   # the tuples of the stage with id production
    eras: [2022_postEE]
    configs: [mutau]
    variables: [m_vis, pt_1, pt_2]
    selections: [baseline]
  - stage: controlplots
    id: plots
    inputs: {hists: hists}         # the control-histogram files of the stage with id hists
```

Each stage has its own options. Setting `eras` on production does not set the
eras for controlhists or shapes. Likewise, production `channels: [mutau]` and
controlhists `configs: [mutau]` belong to different packages and serve different
purposes. What is filled (eras, setups, variables, selections, samples, tag) is
an option of `controlhists`; what only changes the picture (`fraction`, `pdf`,
`text`) is an option of `controlplots`.

Until changelog §21 (S4) one stage, `plots`, filled and drew in one script; a
recipe that still writes `stage: plots` (or `stage: histograms`, now `shapes`)
fails the check with a message naming the new stages.

For plots of tuples you already have, omit the production entry and name
them: `inputs: {tuples: {external: /eos/.../$ERA/$GROUP}}` (see
[Tuples made outside TauFW](#tuples-made-outside-taufw)). For
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
| `run_root` | Optional, with a warning | The parent directory of the runs: a run is `<run_root>/<name>_<time>/`. See [Where the runs go](#where-the-runs-go-run_root). |
| `pico` | Optional | Mapping with only `config`; omitting it uses PicoProducer's default configuration. |
| `pico.config` | `null` | PicoProducer configuration file path. See the path rules below. |
| `stages` | Required | Non-empty list of stage mappings. Each entry needs `stage`, `id` and `inputs`, may have `description`, and has that stage's options. |

The stages run in the order they are written; the order is your choice. The
usual one is:

```text
production → controlhists → controlplots → shapes → fit
```

The only order rule comes from `inputs`: a stage reads only stages written above
it (a `fit` above the `shapes` it reads is an error). Any non-empty subset is
allowed, and `controlhists`, `controlplots`, `shapes`, `fit` and [Python steps](#python-steps) may
appear any number of times, each with its own `id` (for example a `shapes`
and a `fit` for one set of working points, then another pair for a second set).
`production` may appear at most once: its job files are outside the run and a run
has one `pico.config`. Put several eras and channels in its lists, or use
separate recipes for independent production settings.

The Framework advances the stages one after the other and stops at a stage that
waits (production's batch jobs); the stages written after it wait too.

Every stage has these keys besides its options:

| Key | Required | Meaning |
| --- | --- | --- |
| `stage` | Yes | The stage type: `production`, `controlhists`, `controlplots`, `shapes`, `fit`, `python`. |
| `id` | Yes | The stage's name in the run: its record in `run.json`, its directories `taufw_runs/<run>/stages/<id>/` (output) and `logs/<id>/`, and what `inputs:` refer to. Unique; letters, digits, `_`, `.`, `-` (not `.` or `..`). Any stage may have any id (`id: shapes_tight`). |
| `inputs` | Yes | Which earlier stage's output the stage reads (see the table below). Never left out and never `{}`: a stage without inputs says `inputs: null`. |
| `description` | No | Free text, shown by `plan` and in the menu. Nothing depends on it. |

`inputs` connects each **input slot** of the stage to the id of an earlier stage
that makes that kind of data, or to the stage directory of another run
(`{path: <directory>}`, see [Inputs from another run](#inputs-from-another-run));
a `tuples` slot may also name tuples made outside TauFW (`{external: <pattern>}`).
Nothing is connected implicitly: a stage sees only the artifacts of what its
inputs name.

A slot may be `null` only if its stage allows it (`Stage.null_inputs` in
`Framework/python/stages/`, which also says what `null` means for the slot);
`null` anywhere else is a recipe error. `null` is kept only so that old recipes
keep working (the module then finds its data as it did without the Framework);
a new recipe names every input. `taufw.py plan` shows each input on the
`Inputs:` line, e.g. `tuples <- production`, `shapes <- /afs/.../stages/shapes
(run ..., stage shapes (shapes), finished ...)`, `tuples <- external /eos/...`
or `tuples <- outside this run (the tuples in $PICODIR ...)`.

| Stage | `inputs` | `null` means (old recipes) | Makes |
| --- | --- | --- | --- |
| `production` | `null` (no slots) | - | `tuples` |
| `controlhists` | `{tuples: <id, {path: ...}, {external: <pattern>} or null>}` | the tuples in `$PICODIR` of `pico.config` | `control_histograms` |
| `controlplots` | `{hists: <id or {path: ...}>}` | not allowed (control-histogram files have no default place) | `plots` |
| `shapes` | `{tuples: <id, {path: ...}, {external: <pattern>} or null>}` | the same | `shapes` |
| `fit` | `{shapes: <id, {path: ...} or null>}` | **temporary exception:** the shapes already in `Fitter/input_pt_less_region/`, made outside the Framework | `fit`, `corrections` |
| `python` | `null`, or `{<any name>: <id or {path: ...}>, ...}` | no inputs (a named input must name a stage or a directory; `null` is not allowed) | anything |

The fit's `null` is the only place where a stage reads a module directory
instead of the output of a stage. It is kept for old recipes only (a warning is
planned, TODO §6); a new recipe names a shapes stage of the same recipe, or
the shapes stage directory of another run (`{shapes: {path: ...}}`).

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
missing or wrong inputs, a second production stage, and the
stage-specific value checks are reported before execution, **all of them at
once**. Each problem names its location:

```text
my_mutau.yml: 2 problems
  stages[0] (production): unknown option 'samplez' ...
  stages[1] (controlhists).inputs.tuples: no stage 'prodution' in the recipe
```

`taufw.py check <bundle>` lists every problem without running anything, and
also checks the files the recipe names: `pico.config`, absolute paths, python
step files, and the stage directories of
[inputs from another run](#inputs-from-another-run) (configs a module resolves,
such as `TauES_ID/config/...`, are checked by `plan`). It exits with 1 if there is a problem. The menu runs the same check:
a recipe with problems is red in the list and its preview lists them; it cannot
be started. [example_broken](example_broken/recipe.yml) shows what this looks like.

Validation does not establish that every input exists, that a physics
setup is suitable, or that batch submission will work. `plan` also checks local
stage prerequisites and displays problems as warnings where a command plan can
still be built. Review both the commands and warnings before starting.

### Inputs from another run

An input may name the stage directory of another, finished run instead of a
stage of this recipe, for example a fit on the shapes of an earlier run, without
running the shapes stage (hours) again:

```yaml
  - stage: fit
    id: fit
    inputs: {shapes: {path: /afs/cern.ch/work/u/user/taufw_runs/tes_id_2025_20261015-120000/stages/shapes}}
```

- The value is `<run_root>/<run>/stages/<id>`: the directory of a stage that is
  `DONE`, with its `manifest.json`. The artifacts come from that manifest (never
  from the other run's `run.json`), and the stage works as with an input of the
  same run: the fit's points and shape directories, the `--tuples` pattern of a
  production stage for controlhists and shapes, the files of a controlhists
  stage for controlplots, `ctx.input()` of a python step.
- The path must be absolute. A relative path is refused, and `~` and
  `$VARIABLES` are not expanded (unlike `run_root`). It must not point inside the
  bundle: data is never part of a bundle. (The rules of all paths in a recipe
  are to be unified later, TODO §6.)
- `taufw.py check`, `plan` and the menu check the directory: it exists, has a
  manifest of format 2 (runs started before this feature have format 1 and are
  refused: run that stage again), was not moved or copied (the manifest records
  where it was written, and its artifacts name files there), and its stage makes
  the kind of data the slot takes (a plots directory cannot feed a fit). A
  problem found when the stage starts leaves it `NEW`, like a preflight problem.
- Nothing is written to or copied from the source directory; it is read in
  place (a production directory can hold tens of GB of tuples). The fit checks
  that the shape files exist before it runs.
- What was read is recorded: `plan` shows it on the `Inputs:` line, and the
  stage's `sources` in `run.json` and in its own `manifest.json` hold the
  directory, run, stage, finish time and the SHA-256 of the source manifest.
- A recipe with `{path: ...}` inputs is tied to the file system that holds the
  source (lxplus); if the source run is moved or removed, the recipe no longer
  passes `check`.

## Paths and configuration

The path options of the stages (`controlhists.configs`, `shapes.configs`,
`fit.config`, `fit.config_mumu`, a python step's `file`) and `pico.config`
follow one rule:

| Value | Resolution | `plan` shows |
| --- | --- | --- |
| Absolute path | Used as is. | `absolute` |
| Relative path of a file in the bundle | That bundle file, e.g. `config_coarse_TT.yml` next to `recipe.yml`. | `bundle` |
| `Configs/...`, not a bundle file | The template in `TauFW/Configs/` (changelog §22), e.g. `Configs/Fitter/tes_id/config_coarse_TT.yml`; the stage's module gets its absolute path. | `template` |
| Any other relative path | Unchanged: the module resolves it as before, relative to `Fitter/` (e.g. the fit's `TauES/config/defaultFitSetupTES_mutau.yml`) or `Histogrammer/`. The old module paths of configs that became templates (`TauES_ID/config/config_coarse_TT.yml`, ...) fail the check with the template's name; the `shapes` stage's `configs` take no module path at all (changelog §22 H3). | `module` |
| `controlhists.configs` channel name | `mutau` selects `Configs/Histogrammer/setups/setup_mutau.yml` (the template; a bundle copy is better: `taufw.py init --from` makes one). | `module` |

A bundle file **replaces** the module's config as a whole: the script reads the
bundle's copy instead, nothing is merged. `taufw.py plan` lists every file each
stage reads and where it comes from, so check it after changing a path.

### Config templates (`Configs/`)

The templates of the module configs an analysis may copy are in `Configs/<Module>/` at the repository root
(`taufw.py configs` lists them). Copy one next to `recipe.yml`, name the copy in the recipe and edit its values,
never its `taufw_config` header: it records the template's id and version, and `check`, `plan` and `start` warn
when the template has a newer version than your copy. Rules: [Configs/README.md](../Configs/README.md).

Other paths:

| Value | Resolution |
| --- | --- |
| CLI recipe/bundle path, run-directory path, `--run-root` | Relative to the directory where you launch `taufw.py`. |
| `run_root` | Absolute; `~` and `$VARIABLES` are expanded where `taufw.py` runs. See [Where the runs go](#where-the-runs-go-run_root). |
| `{path: ...}` input | Absolute only; nothing is expanded; not inside the bundle. See [Inputs from another run](#inputs-from-another-run). |
| Relative `pico.config` | A file of the bundle (the recipe's directory), e.g. `pico.json`; a path above it (`../`) is made absolute when the recipe is loaded and is not copied into runs. |
| Histogrammer/Fitter outputs | In the run: `<run_root>/<run>/stages/<id>/` (see [Outputs and logs](#outputs-and-logs)); nothing is written to `Histogrammer/` or `Fitter/`. Production's merged tuples too: `stages/<id>/<era>/<group>/`, not `$PICODIR` of the PicoProducer configuration. |

### Where the runs go (`run_root`)

```yaml
name: tes_id_2025
run_root: /afs/cern.ch/work/u/user/taufw_runs
```

- A run is `<run_root>/<name>_<YYYYmmdd-HHMMSS>/`. `start --run-root DIR` takes
  precedence over the recipe; without both, the runs go to `taufw_runs/` in the
  directory where you launch `taufw.py`.
- Without `run_root` (or with `run_root: null`) the recipe is valid, but
  `check`, `plan`, `start` and the menu warn. Runs can be large; on lxplus the
  default place is usually your AFS area, and the home directory's quota is
  small. A full quota stops a run midway. Choose a directory with enough space
  (e.g. under `/afs/cern.ch/work/`).
- The value must be an absolute path on a mounted file system: a URL
  (`root://...`) and a relative path are problems. `~` and `$VARIABLES` (e.g.
  `$HOME/taufw_runs`) are expanded where `taufw.py` runs, with a warning, since
  someone else or another machine gets another directory; an undefined variable
  is a problem. `plan` and `start` print the directory they use.
- It must be outside the bundle directory: every run copies its bundle, so a
  run root inside it would copy the earlier runs too (for a loose recipe file,
  whose directory is not copied, this does not apply).
- A production stage writes its merged tuples into the run directory (often
  tens of GB); its warning without `run_root` says so.
- Before a run starts, and before every `advance`, `taufw.py` writes and removes
  a small file in the run root (or in the run directory). If that fails
  (permissions, an expired AFS token: `kinit; aklog`), nothing is started or
  moved. It shows that the directory can be written, not that there is space
  for what the run will write.
- EOS as `run_root` is not tested yet.

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
[public API](../Docs/Manual/PicoProducer/API.md). A bundle may carry its own copy:

```yaml
pico:
  config: pico.json   # a file of this bundle
```

### Where the tuples are

**Production writes its tuples into the run:**
`<run_root>/<run>/stages/<id>/<era>/<group>/<sample>_<channel><tag>.root`, not
to `$PICODIR` of the PicoProducer configuration, so they need the space of
[`run_root`](#where-the-runs-go-run_root). Every tuple artifact records where
they are as a pattern, `.../stages/<id>/$ERA/$GROUP`.

**Controlhists and shapes read the tuples their input names.** The Framework gives
the scripts the pattern as `--tuples <pattern>` (`fillhists.py`,
`createinputsTES.py`): with `{tuples: <production id>}` the pattern on that
stage's artifacts (in `plan`: `<run_dir>/stages/<id>/$ERA/$GROUP`), with
`{tuples: {external: <pattern>}}` that pattern. The PicoProducer configuration
is never used for the tuples (since CL §37 the commands get no `$TAUFW_PICO_CONFIG`).
Before a stage runs, its preflight checks that the production tuple files exist,
or that the directory of an external pattern exists. A production output tag
does not reach the readers: they look for `<sample>_<channel>.root`.

#### Tuples made outside TauFW

```yaml
  - stage: controlhists
    id: hists
    inputs:
      tuples: {external: /eos/cms/store/group/phys_tau/TauFW/pico2024/TES_variations/$ERA/$GROUP}
```

- The pattern is an absolute directory with `$ERA` and `$GROUP`; the files in it
  are `<sample>_<channel>.root` (the data a glob of sample names), the TES/LTF/JTF
  variations `<sample>_<channel>_<shift>.root` in the same directory. The scripts
  fill only `$ERA`, `$GROUP`, `$SAMPLE`, `$CHANNEL`, `$TAG`; a pattern with
  another key (e.g. `$DAS`) is refused before the stage runs.
- Not allowed: a relative path, a URL (`root://...`), `~` or a `$VARIABLE` at the
  start. `check` reports a missing directory (the part of the pattern before the
  first `$`).
- To name the same tuples in several stages, use a YAML anchor and alias, as in
  [tes_id_2025](tes_id_2025/recipe.yml).
- Which samples are read is decided by the `samples` option (next section);
  without it, by the tables of `Histogrammer/config/samples_v15.py`.

### Which samples

The `samples` option of `controlhists` and `shapes` names the sample model files:
for every era, which MC samples are read (with their cross sections, titles and
extra weights), which data datasets, the MC weight of each channel kind, and
how samples are stitched and joined. Copy the file of each era from
`Configs/Histogrammer/samples/` (`taufw.py configs` lists them) next to `recipe.yml`
and name the copies; edit the values of your copy (never its `taufw_config`
header, see [Config templates](#config-templates-configs)). The templates were
exported from `Histogrammer/config/samples_v15.py` and give exactly the same sample
sets (checked by `Tests/Histogrammer/sample_model`).

```yaml
  - stage: controlhists
    inputs: {tuples: production}
    eras: [2025]
    samples: &samples [v15_2025.yml]    # one file per era
  - stage: shapes
    samples: *samples
```

- `check`: the files are bundle files (or absolute), can be read, and there is
  exactly one per era of the stage.
- `plan` and `start`, when the stage reads the tuples of a production stage of
  the same recipe: every MC sample the files ask for must be made by
  production (era and channel), and the data pattern must match a sample it
  makes; otherwise `plan` lists the problem and `start` refuses the recipe. A
  sample production makes that no reader asks for is a warning.
- Preflight, with a tuple directory (`{external: ...}` or production's): every
  requested MC tuple and at least one data tuple must exist.
- Without `samples:` the scripts use the tables of `samples_v15.py`, as before
  (kept for old recipes; nothing is compared).

**`null` (old recipes):** no longer read (CL §37): the tuples are given, never
found through `$PICODIR` of the PicoProducer configuration. The stage cannot be
planned; name a production stage, `{external: <pattern>}` or `{path: ...}`.

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

### `controlhists`

The first half of the control plots. Runs `Histogrammer/fillhists.py --hists --no-draw` (the former
`Plotter/plot.py`, changelog §21) locally, once per config and era, through
`TauFW.Histogrammer.api.ControlHists`: it fills the data/MC stacks of every variable and selection and writes
them, with what the drawing needs, to one control-histogram file
([contract](../Docs/Develop/contracts/control-histograms.md)); it draws nothing. The `controlplots` stage draws them.

| Option | Default | Meaning |
| --- | --- | --- |
| `eras` | Required | Non-empty eras; forwarded as `fillhists.py -y`. |
| `configs` | `[mutau]` | Non-empty channel names, bundle files, or setup `.yml` paths relative to `Histogrammer/`; `-c`. |
| `variables` | `[]` | Variable glob filters; `-V`. Empty selects all variables defined by the script. |
| `selections` | `[]` | Selection glob filters; `-S`. Empty includes baseline and the setup's regions. |
| `serial` | `false` | Serial processing; `-s`. |
| `notauidsf` | `false` | Remove DeepTau ID scale factors; `-r`. |
| `tag` | `""` | Tag of the file and of the plot names; `-t`. |
| `timeout` | `null` | Seconds allowed per command; unset means no time limit. |
| `samples` | `[]` | Sample model files of the bundle (or absolute), one per era: copies of `Configs/Histogrammer/samples/v15_<era>.yml` (MC table, data, MC weights, stitching); `--samples`. Empty: the tables of `Histogrammer/config/samples_v15.py` (old recipes). See [Which samples](#which-samples). |

`fillhists.py` runs in the stage's directory, so the files are written to
`taufw_runs/<run>/stages/<id>/hists/<era>/<channel><tag>.root` (nothing is written
to `Histogrammer/`). The run records one `control_histograms` artifact per channel
setup and era (era, config, channel, tag, file). File names carry the setup's
`tag` plus `tag` of the stage; two setups with the same channel and tag (e.g.
`setup_mutau.yml` and `setup_mutau_inclusive.yml`) write the same file, and
`plan` says so.
The selected setup controls the physics samples and regions; a production
sample filter does not automatically restrict the Histogrammer's sample collection.

### `controlplots`

The second half of the control plots. Runs `Plotter/draw.py` locally, once per file of the `controlhists`
stage its input names, through `TauFW.Plotter.api.ControlPlots`. The plots get the names and texts
`fillhists.py` gives its own plots (`<variable>_<channel short>-<selection>-<era><tag>.png`), so the same
options give the same files as filling and drawing in one `fillhists.py` run. This is the pipeline's
control-plot stage; the `plots` entry in `fit.steps` instead makes plots of fit results.

```yaml
  - stage: controlplots
    id: plots
    inputs: {hists: hists}   # a controlhists stage above, or {path: <run_dir>/stages/<id>} of another run
    pdf: true
```

| Option | Default | Meaning |
| --- | --- | --- |
| `fraction` | `false` | Fraction stack in the ratio plot; `draw.py -F`. |
| `pdf` | `false` | Also save PDF files; `-p`. |
| `text` | `""` | Additional plot text; `-T`. |
| `timeout` | `null` | Seconds allowed per command; unset means no time limit. |

There is nothing to choose about what is drawn: eras, channels, variables, selections and the tag are in
the files. `draw.py` runs in the stage's directory, so the plots are written under
`taufw_runs/<run>/stages/<id>/plots/<era>/`. The run records one `plots` artifact per file (era, config,
channel, directory, the number of plots it made), the same form as the former `plots` stage.

### `shapes`

Creates the input shapes for the combined TES + tau ID fit. It wraps the
`Fitter/run_inputs.sh` workflow via `TauFW.Histogrammer.api.TESShapes.make_shapes` (the Fitter API's until changelog
§22 H3), running `Histogrammer/shapes/TauES/createinputsTES.py` locally for every era, jet WP, electron WP, and
config. The `fit` stage reads the files by the contract [Docs/Develop/contracts/tes-shapes.md](../Docs/Develop/contracts/tes-shapes.md).

| Option | Default | Meaning |
| --- | --- | --- |
| `eras` | Required | Non-empty eras; `-y`. |
| `jet_wps` | Required | Non-empty DeepTau VSjet working points, for example `[VTight]`; `-j`. |
| `ele_wps` | Required | Non-empty DeepTau VSe working points, for example `[Tight]`; `-e`. |
| `configs` | `[Configs/Fitter/tes_id/config_coarse_TT.yml, Configs/Fitter/tes_id/FitSetup_mumu.yml]` | Non-empty configs (bundle files, `Configs/` templates or absolute): by default the mutau fit and mumu control region. A module-relative path (e.g. `TauES/config/...`) fails the check: the stage's API is the Histogrammer's, the configs were Fitter files (changelog §22 H3); copy the file into the bundle. |
| `serial` | `false` | Serial shape creation; `-s`. |
| `timeout` | `null` | Seconds per shape-creation command; unset means no time limit. |
| `samples` | `[]` | Sample model files of the bundle (or absolute), one per era: copies of `Configs/Histogrammer/samples/v15_<era>.yml` (MC table, data, MC weights, stitching); `--samples`. Empty: the tables of `Histogrammer/config/samples_v15.py` (old recipes). See [Which samples](#which-samples). |

The lists form a Cartesian product. Two eras, two jet WPs, one electron WP,
and two configs produce eight shape-creation commands. Each command can write
multiple shape files according to its config's observables.

The scripts run in the stage's directory, so the shapes go under
`taufw_runs/<run>/stages/<id>/input_pt_less_region/againstjet_<J>/againstelectron_<E>/`
(nothing is written to `Fitter/`).
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
| `config` | `Configs/Fitter/tes_id/config_coarse_TT.yml` | Mutau fit config (a bundle file, a `Configs/` template, or relative to `Fitter/`). |
| `config_mumu` | `Configs/Fitter/tes_id/FitSetup_mumu.yml` | Mumu control-region config (a bundle file, a `Configs/` template, or relative to `Fitter/`). |
| `eras` | `[]` | Eras to fit; when inferring points, empty allows every upstream era. |
| `jet_wps` | `[]` | VSjet working points; empty together with `ele_wps` means infer points from the input's histogram artifacts. |
| `ele_wps` | `[]` | VSe working points; supply both WP lists or leave both empty. |
| `steps` | `[fit, postfit, plots, corrections, summary]` | Non-empty selection of workflow steps, described below. |
| `impacts` | `true` | Include impact calculations in the `postfit` step; these can be slow. |
| `timeout` | `null` | Seconds per command, not per working point or entire stage. |

The fit reads each point's shapes from the directory recorded in the shapes
artifacts of the shapes stage that `inputs.shapes` names; a point of the
recipe without shapes there makes the stage fail before anything runs. The
shapes stage may be one of another run (`{shapes: {path: ...}}`, see
[Inputs from another run](#inputs-from-another-run)). With
`inputs: {shapes: null}` (old recipes only, see above) it reads
`Fitter/input_pt_less_region/`. The scripts of one era run in
`taufw_runs/<run>/stages/<id>/<era>/`, because several of their outputs
(`FitDiagnosticsValues/`, `impacts/`, `output_plots/`, `Measurements/`) have no
era in their names; everything the fit writes is there, including `tau_sf/`
and the combined `data/tau/TauCorrections_<era>_with_uncorrelated_systs.json`.
Copying the correction files to their final place is not done by the
Framework. The few script options this needs are listed in
[Docs/Develop/Refactor-2025/scripts_arg_changes.md](../Docs/Develop/Refactor-2025/scripts_arg_changes.md).

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
| `ctx.input(name, kind=None)` | Artifacts of the stage connected to the input `name` (also another run's, `{path: ...}`), optionally of one `kind`. An input the recipe does not give is an error. |
| `ctx.artifacts(stage=None, kind=None)` | Artifacts of the input stages by stage id (or all of them), optionally of one `kind`. |
| `ctx.inputs` | The step's inputs: name → stage id (for `{path: ...}`: the directory). |
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

1. **Infer them from the input shapes.** Connect `inputs: {shapes: <shapes id>}` (or `{path: ...}`)
   and leave `jet_wps` and `ele_wps` empty. A point is selected only if the input shape artifacts contain both
   `config` and `config_mumu` for that era and WP pair. `eras: []` accepts all
   upstream eras; a non-empty `eras` filters them. Config values must match the
   histogram artifact config values, so update both stages if you change configs.
2. **Specify a grid.** Set both WP lists. The fit uses
   `eras × jet_wps × ele_wps`. If `eras` is empty, it takes eras from upstream
   histogram artifacts. With `shapes: null` (old recipes), supply eras
   explicitly because there are no upstream artifacts to infer them from.

Inference uses the artifacts of what `inputs.shapes` names (a stage of this
recipe, or another run's stage directory through its manifest), never a search
of shape files on disk. If no points can be selected, planning reports the
problem and starting the fit fails.

A complete fit-only recipe on the shapes of an earlier run is:

```yaml
name: tes_id_2025_fit_only
stages:
  - stage: fit
    id: fit
    inputs: {shapes: {path: /afs/cern.ch/work/u/user/taufw_runs/tes_id_2025_20261015-120000/stages/shapes}}
    eras: ["2025"]
    jet_wps: [VTight]
    ele_wps: [Tight]
    config: Configs/Fitter/tes_id/config_coarse_TT.yml
    config_mumu: Configs/Fitter/tes_id/FitSetup_mumu.yml
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
[FastSetup](../Docs/Manual/FastSetup.md)). After `cmsenv` and `scram b`, `taufw.py`
is available on `PATH`; from the repository root you can also use
`python3 taufw.py`. Fits require ROOT, the Combine tools, and CombineHarvester
for the fit step. Local-stage preflight reports missing prerequisites.

From the repository root:

```bash
# Inspect selected samples/jobs, the files each stage reads and the local-stage
# commands. Nothing executes.
python3 taufw.py plan Analyses/example_mutau_short

# Create a run and execute every stage that can proceed now.
python3 taufw.py start Analyses/example_mutau_short
```

`start` prints the actual run directory. Use that directory for further commands:

```bash
python3 taufw.py status taufw_runs/mutau_2022_postEE_short_20261013-120000
python3 taufw.py advance taufw_runs/mutau_2022_postEE_short_20261013-120000

# Repeated checks while waiting for batch jobs (default interval: 600 seconds).
python3 taufw.py advance taufw_runs/mutau_2022_postEE_short_20261013-120000 --wait --poll 900
```

The example timestamp above is illustrative; substitute the path printed by
your `start` command. `--wait` and `--poll` also work on `start`.
`start --run-root /path/to/runs` puts the run there instead of the recipe's
[`run_root`](#where-the-runs-go-run_root).
`status` reads recorded and live state without submitting jobs or saving changes.
CLI `-v`/`--verbose [N]` controls reporter verbosity; production `verbosity` is
a separate recipe option passed in the PicoProducer request.

**`plan --local` executes a small production test.** Unlike ordinary `plan`, it
runs locally on one input file from the first matching sample for each era and
channel, with 100 events by default:

```bash
python3 taufw.py plan Analyses/example_mutau_short --local -m 50
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
the same call. Plots, shapes, fit, and python step commands run sequentially on the
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
its inputs, the other runs' stage directories it read (`sources`), where it was
written (`stage_dir`) and its artifacts. Another run reads it when an input names
this directory ([Inputs from another run](#inputs-from-another-run)). `run.log` contains
Framework messages; each command log contains its working directory, command
line, output, exit code, duration, and any missing expected outputs.
`run.json` stores the recipe, configuration snapshot, the list of copied bundle
files, stage state, the sources read from other runs, submission attempts,
artifacts, history, and local command results.

| Stage | Output location | Recorded artifacts |
| --- | --- | --- |
| `production` | `taufw_runs/<run>/stages/<id>/<era>/<group>/` | Merged tuple path, sample/group, era, channel, tag, data type, event count, tree, cutflow, and `pattern` (`.../stages/<id>/$ERA/$GROUP`, where the readers look). |
| `controlhists` | `taufw_runs/<run>/stages/<id>/hists/<era>/<channel><tag>.root` | `kind: control_histograms`, era, config, channel, tag, file. |
| `controlplots` | `taufw_runs/<run>/stages/<id>/plots/<era>/` | `kind: plots`, era, config, channel, directory, matching file count. |
| `shapes` | `taufw_runs/<run>/stages/<id>/input_pt_less_region/againstjet_<J>/againstelectron_<E>/` | `kind: shapes`, path, era, channel, config, WP pair, observable. |
| `fit` | `taufw_runs/<run>/stages/<id>/<era>/` (`output_*`, `postfit_*`, plot directories, `tau_sf/`, `data/tau/`) | `kind: fit` per point, output/postfit directories, fitted values, correction paths; when summary runs, two `kind: corrections` per era: the merged JSON, and the combined TES + ID file (`combined: true`). |
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
| `Warning: run_root: not set` | The recipe runs, in `taufw_runs/` where you launch `taufw.py`. Set [`run_root`](#where-the-runs-go-run_root) to a directory with enough space. |
| `cannot write in the run root` / `run directory` | The directory cannot be written: check its permissions and your AFS token (`kinit; aklog`), or choose another `run_root` / `--run-root`. Nothing was started or moved. |
| Unknown key or missing required option | Check indentation and the option tables. Put options beside `stage`; use `split`/`merge` mappings only under production. |
| Missing `id` or `inputs` | Every stage needs both. A stage without inputs says `inputs: null`; tuples made outside TauFW are named with `{tuples: {external: <pattern>}}`. |
| `no stage 'x' in the recipe` / `comes after this one` / `makes ..., not ...` | An input names a stage **id** (not a type or description) of an **earlier** stage that makes that kind of data (fit `shapes` ← a shapes stage). |
| `comes after this one` / duplicate id / second production stage | An input names a stage written below it: move that stage up. Every stage needs its own unique `id`. Put all production eras and channels in one production stage, or use separate recipes. |
| `has no manifest.json` | The `{path: ...}` directory is not a finished stage directory: its stage is not `DONE`, or it is not `<run_root>/<run>/stages/<id>` (e.g. `Fitter/`). |
| `has manifest format 1, expected 2` | The source run was started before inputs from other runs existed; run that stage again in a new run. |
| `was moved or copied from` | The source directory is not where its manifest was written, so its artifacts name files elsewhere. Use the original directory. |
| `it makes control_histograms, not shapes` | The `{path: ...}` directory belongs to a stage that makes another kind of data than the slot takes. |
| A config change has no effect | Run `plan` and check the `from` column: `module` means the file is not in the bundle (typo in the path), so the module's own config is used. |
| Python step `NEW` with "no top-level function" | Define `def run(ctx):` at the top level of the file, or set `function:`. |
| Python step `FAILED` | Read `taufw_runs/<run>/logs/<id>/01_<id>.log` for the traceback; `context.json` next to it shows what the step was given. |
| No samples match production | Inspect `plan`, configured era/channel catalogs, sample/DAS filters, vetoes, and `dtypes`. |
| Production stays `WAITING` | Inspect live job status; pending/running chunks delay resubmission of failed chunks. Continue with `advance`, or use `--wait`. |
| Production fails after the allowed tries | Inspect PicoProducer job logs and fix the cause. The failed run cannot be restarted by editing its recipe; start a new run with the corrected setup. |
| Local stage stays `NEW` with a preflight message | Fix the named missing environment/tool/config/input, then call `advance` on the same run. |
| No working points to fit | Connect `inputs: {shapes: <shapes id or {path: ...}>}` to a shapes stage with both matching configs, or explicitly set eras and both WP lists (needed with `shapes: null`). |
| Plots/shapes read unexpected or missing tuples | Check the `Inputs:` line and the `--tuples` pattern of the commands in `plan` (with `null`: `$PICODIR` in the run's PicoProducer configuration), then channel/setup naming, tags, and required variation tuples. |
| `the tuples of stage 'production' do not record where they are` | The run's production finished before the Framework chose the tuples' place (CL §16). Start a new run, or name the tuples with `{external: <pattern>}`. |
| `tuple directory ... not found` | The fixed part of an `{external: ...}` pattern does not exist on this machine (EOS not mounted, a typo). |
| Exit code zero but the local stage fails | Read the command log for missing/stale expected outputs and nested ROOT/Combine failures. |
| Editing YAML or a bundle file does not affect `advance` | The run uses the recipe stored in `run.json` and its bundle copy; start a new run to use edited settings. |

Preflight problems leave a local stage `NEW`, so they can be fixed and retried
in the same run. A command failure leaves it `FAILED`, which is terminal. An
exception such as an unavailable scheduler is recorded without changing the
stage state; retry `advance` after fixing the external problem. The CLI returns
exit code 1 for a failed run; use status/messages to distinguish completion from
an unfinished run.

## Current limitations

- A recipe with [inputs from another run](#inputs-from-another-run) is tied to
  that file system, and a run directory (its own or a source) cannot be moved:
  the recorded artifacts keep their absolute paths (a moved source is refused;
  a moved run of its own is not detected, Framework BUGS K01).
- Production's job files are not in the run: they go to `PicoProducer/output/`
  (`jobdir` and `outdir` of the PicoProducer configuration), so two runs with
  the same era, channel and tag share them. Its merged tuples are in the run.
- The production side of the samples is not part of a bundle yet: the
  PicoProducer configuration names its own sample catalogs
  (`PicoProducer/samples/samples_<era>.py`). The readers' samples are (the
  `samples` option).
- TES, LTF, and JTF variation tuples need their own PicoProducer channels (for
  example `mutau_TES0p950`) and currently their own production runs. A nominal
  production stage alone does not prepare all histogram inputs.
- Local stages do not resume partway through their commands. A failed stage is
  final; Ctrl+C can leave a local stage `NEW` with partial output in
  `stages/<id>/`, and the next `advance` stops in preflight ("output directory
  ... is not empty") until you remove that directory; then it reruns the stage.
  Interrupting the CLI does not cancel submitted batch jobs; keep the saved run
  directory for continuation.
- The wrapped fit supports the uncorrelated DeepTau option-3 workflow. `corrTES`,
  `fullcorr`, PNet, and UParT variants are not exposed as recipe options.
