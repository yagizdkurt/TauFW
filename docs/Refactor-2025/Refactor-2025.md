# Refactor-2025: change log

**Author:** Yagizhan Dinckurt (yagizdkurt), October 2026
**Branch:** `Refactor-2025`
**Last updated:** 2026-10-19

This document records the changes made on the `Refactor-2025` branch: what changed and why.
What is still open is listed in [TODO.md](TODO.md). Other documents cite its sections as "CL §N" (or "changelog §N").

| # | Change |
| --- | --- |
| 1 | [Test migration and BBB regression tests](#1-test-migration-and-bbb-regression-tests) |
| 2 | [FastSetup script](#2-fastsetup-script) |
| 3 | [Removal of legacy Python 2 scripts](#3-removal-of-legacy-python-2-scripts) |
| 4 | [Utilities package for future development](#4-utilities-package-for-future-development) |
| 5 | [PicoProducer cleanup: command-level BBB tests and bug register](#5-picoproducer-cleanup-command-level-bbb-tests-and-bug-register) |
| 6 | [PicoProducer cleanup: settings, datasets, storage, batch and jobs packages](#6-picoproducer-cleanup-settings-datasets-storage-batch-and-jobs-packages) |
| 7 | [PicoProducer cleanup: job pipelines](#7-picoproducer-cleanup-job-pipelines) |
| 8 | [PicoProducer cleanup: public API, command line, workers](#8-picoproducer-cleanup-public-api-command-line-workers) |
| 9 | [Framework: the TauFW orchestrator](#9-framework-the-taufw-orchestrator) |
| 10 | [Framework: plots, histograms and fit stages](#10-framework-plots-histograms-and-fit-stages) |
| 11 | [Framework: analysis bundles and Python steps](#11-framework-analysis-bundles-and-python-steps) |
| 12 | [Import-boundary test and coupling inventory](#12-import-boundary-test-and-coupling-inventory) |
| 13 | [Framework: explicit stage ids, inputs and recipe validation](#13-framework-explicit-stage-ids-inputs-and-recipe-validation) |
| 14 | [Framework: run directory with logs/ and stages/, stage manifests](#14-framework-run-directory-with-logs-and-stages-stage-manifests) |
| 15 | [Framework: Plotter and Fitter outputs in the run directory](#15-framework-plotter-and-fitter-outputs-in-the-run-directory) |
| 16 | [Framework: tuples as an input, production writes into the run, run_root](#16-framework-tuples-as-an-input-production-writes-into-the-run-run_root) |
| 17 | [Framework: inputs from another run's stage directory, repeated stages](#17-framework-inputs-from-another-runs-stage-directory-repeated-stages) |
| 18 | [Menu and UI](#18-menu-and-ui) |
| 19 | [Configs: config templates with an id, a version and a lock](#19-configs-config-templates-with-an-id-a-version-and-a-lock) |
| 20 | [Sample lists as data: the sample model](#20-sample-lists-as-data-the-sample-model) |
| 21 | [Plotter becomes Histogrammer; a clean Plotter is extracted](#21-plotter-becomes-histogrammer-a-clean-plotter-is-extracted) |
| 22 | [TES shapes leave the Fitter for the Histogrammer](#22-tes-shapes-leave-the-fitter-for-the-histogrammer) |
| 23 | [Variation tuples in the shapes preflight](#23-variation-tuples-in-the-shapes-preflight) |
| 24 | [Review of the tes_id_2025 bundle: fit-result comparison, result files in the summary](#24-review-of-the-tes_id_2025-bundle-fit-result-comparison-result-files-in-the-summary) |
| 25 | [Postfit scripts set the era through CMSStyle (no Plotter import)](#25-postfit-scripts-set-the-era-through-cmsstyle-no-plotter-import) |
| 26 | [The luminosity of the normalisation in the sample model and the control-histogram file](#26-the-luminosity-of-the-normalisation-in-the-sample-model-and-the-control-histogram-file) |
| 27 | [The fit plots show the luminosity of the normalisation; explicit lumi on the samples](#27-the-fit-plots-show-the-luminosity-of-the-normalisation-explicit-lumi-on-the-samples) |

The reference environment for all of this is `CMSSW_14_1_0_pre4` (Python 3.9, ROOT 6.30).

IDs such as L17, F25, K07, P08 or S17 are entries of the BUGS registers of Histogrammer, Fitter, Framework and
PicoProducer.

---

## 1. Test migration and BBB regression tests

**Date:** 2026-10-12
**Commits:** `949ce56` (Test Migration 1), `bc1e28c`, `9b4b407`, `875ba88`, `905eac8`, `28b8c57`,
`dd0fb9e`, `0f36771`, `646d28f`, `9f9d510` (Lock BBB baselines), `ef80e40` (Re-lock BBB baselines)
**Details:** [Tests/README.md](../../Tests/README.md), [Tests/LEGACY_BROKEN_CASES.md](../../Tests/LEGACY_BROKEN_CASES.md)
**Tests/Validation:** [ValidationAndTests.md:19](ValidationAndTests.md#1-test-migration-and-bbb-regression-tests)

### What changed

- **Tests moved to top-level `Tests/`.** Moved 38 test files unchanged.
  [Tests/migration.json](../../Tests/migration.json) records original paths and content hashes.
- **A test runner, `Tests/run.py`.** Each test runs in a fresh process and temporary source workspace.
- **BBB:** added 13 exact regression cases using fixed ROOT fixtures.
- **Harness self-checks:** added offline checks (`Tests/check_harness.py`) and ROOT checks
  confirming that deliberate output changes are detected (`Tests/check_root.py`).
- **References updated:** removed the `test` channel from the PicoProducer default config and
  `config_example.json`; `TestModule` is now imported as `Tests.PicoProducer.analysis.TestModule`.

### Related fixes

- `Plotter/python/plot/Stack.py` (`49dc76f`): nonzero integer `ratio` values now create one lower panel,
  fixing a crash for `ratio=3` and an empty panel for `ratio=2`.
- `Plotter/python/plot/utils.py` (`a9c18d8`): `gethistratio` now accepts a `TGraph` denominator
  (e.g. a data graph after `dividebybinsize`).
- `PicoProducer/python/processors/skimjob.py` (`0f36771`): the Run 2 JME import is now done only when
  `--jec`/`--jec-sys` is used. Run 3 users can rely on CMSSW's built-in NanoAODTools without installing the
  standalone repository.

### Why

Establish regression baselines before refactoring, keep test artifacts outside production packages,
and distinguish runnable tests from existing broken or legacy cases.

---

## 2. FastSetup script

**Date:** 2026-10-12
**Commit:** `41c7c0e`
**Details:** [docs/FastSetup.md](../FastSetup.md)
**Tests/Validation:** [ValidationAndTests.md:42](ValidationAndTests.md#2-fastsetup-script)

### What & Why

- Added [setup.sh](../../setup.sh) that automates installation and standardizes the ref env used for BBB tests.

---

## 3. Removal of legacy Python 2 scripts

**Date:** 2026-10-12
**Commit:** `ab5e7a2`
**Tests/Validation:** [ValidationAndTests.md:48](ValidationAndTests.md#3-removal-of-legacy-python-2-scripts)

### What changed

Deleted 27 Python 2-only scripts (6523 lines).
Removed files had replacements or no remaining use; used scripts without replacements were kept for migration.

| Area | Removed code / alternatives |
| --- | --- |
| `Fitter/MuTauFR`, `ETauFR` | Duplicate nuisance/postfit scripts and unused datacard variants; use `diffNuisances.py` or the retained measurement scripts. |
| `Fitter/TauID`, `TauES` | Old input/fit/scan scripts; alternatives include `createinputsTES.py`, the TauES_ID workflow and `make_tid_2025.py`. |
| `Fitter/paper`, `scripts` | Frozen paper scripts and abandoned `histedit.py`; retained in Git history. |
| `PicoProducer/utils` | `convertGENSIM_mutau.py`, `pickEvents.py`, `printNanoAOD.py`; alternatives include `edmPickEvents.py` and ROOT inspection tools. |

### Why

These scripts fail in the reference Python 3.9 environment and obscure live dependencies in searches and audits.
All deleted files remain in Git history. The Python 3 migration of the retained scripts is tracked in
[TODO.md](TODO.md).

---

## 4. Utilities package for future development

**Dates:** 2026-10-12 to 2026-10-14
**Initial commit:** `65ed36b`
**Details:** [Utilities/README.md](../../Utilities/README.md), [Utilities/IOInventory.md](../../Utilities/IOInventory.md)
**Tests/Validation:** [ValidationAndTests.md:54](ValidationAndTests.md#4-utilities-package-for-future-development)

### The package: CLI and FileIO

Added shared I/O interfaces to replace duplicated helpers: `CLI` handles terminal output and prompts; `FileIO`
handles local files, explicit XRootD/GFAL URLs, common formats, directory operations, ROOT ownership and `hadd`.
Overwrites require `overwrite=True`; external commands use argument lists without a shell and have timeouts.
An I/O inventory maps existing operations to these interfaces.

### Shared code moved to Utilities

Code moved from `common` and Plotter without changing covered outputs. Callers use the new locations; old modules
are deleted or retain only unmoved code. Utilities does not import `TauFW.common`. Preserved output quirks are marked
as LEGACY and tracked in [TODO.md](TODO.md) for a later explicit output change.

#### Parallel processes and the loading bar

| Old | New |
|---|---|
| `TauFW.common.tools.parallel.MultiProcessor(max=...)` | `TauFW.Utilities.Process.ParallelProcessor(max_parallel=...)` |
| `TauFW.common.tools.LoadingBar.LoadingBar(pre=...)` | `CLI.loading_bar(steps, prefix=...)`; advance with `count(message="", steps=1)` |

Parallel processing keeps its queue/result behavior and serial mode; loading bars keep their terminal bytes.
Removed the unused import-time manager that broke spawn, `Thread` demos and `LoadingBar.update()`/`message()`.
Integer-step counting now works through `count(steps=n)`.

#### Numeric helpers

`common/python/tools/math.py` became `TauFW.Utilities.Math`; renames and behavior changes are noted below.

| Old (`TauFW.common.tools.math`) | New (`TauFW.Utilities.Math`) | Notes |
|---|---|---|
| `frange(start, end, step, scale)` | `float_range(start, end, step, scale)` | Same values (an `int` start stays `int`). |
| `partition(mylist, nparts, nmax)` | `partition(items, parts, max_size)` | Neither given raises `ValueError` (was `IOError`). |
| `partition_by_max(mylist, nmax)` | `partition_by_sum(values, maximum)` | Sorts a copy, not the caller's list. |
| `columnize(oldlist, ncol)` | `columnize(items, columns)` | Same order. |
| `magnitude(x)`, `reldiff(x, y)` | `magnitude(x)`, `relative_difference(x, y)` | Unchanged. |
| `scalevec(a, b, r, log)` | `scale_vector(start, end, ratio, log)` | Log-mode `assert`s are `ValueError`s with the same messages. |
| `sqrt, log10, ceil, floor` | standard `math` module | |

Dropped without callers: `ceil2digit` and `round2digit`. The `common.math_helper` exports also use standard `math`.

#### Printf-style table

`common/python/tools/Table.py` became `CLI.table(...)`, returning a `Table` with byte-identical output.
The `Table.py` / `log.py` import cycle is gone; preserved formatting quirks are tracked in TODO.

| Old | New |
|---|---|
| `LOG.table(*formats, verb=0, level=0, pre=">>> ", ul=True)` | `CLI(verbosity=verb, prefix=pre).table(*formats, minimum_verbosity=level, underline=ul)` |
| `Table.printheader(*titles, post="")` | `print_header(*titles, suffix="")` |
| `Table.printrow(*values)` / `Table.printtable()` | `print_row(*values)` / `print_rows()` |
| `Table.header(...)`, `Table.row(...)`, `str(table)` | unchanged |
| `LOG.tableheader()`, `LOG.row()` | removed (no callers) |

#### Drawing library

Plotter's drawing code moved unchanged to `TauFW.Utilities.Drawing`, so Fitter and PicoProducer can draw without
importing the Plotter. Modernizing the implementation remains in TODO.

| Old | New |
|---|---|
| `Plotter/python/plot/{Plot,Plot2D,Stack,Ratio,CMSStyle}.py` | `Utilities/python/Drawing/` (same names) |
| `Plotter/python/plot/utils.py` | `Drawing/hist_tools.py` |
| `Plotter/python/sample/SampleStyle.py` | `Drawing/SampleStyle.py` (owns `Logger('Sample')`) |
| Label helpers of `Plotter/python/plot/string.py` (`makelatex`, `maketitle`, `makehistname`, ...) | `Drawing/labels.py`; `string.py` imports them back |
| `LOG = Logger('Plot')` | `TauFW.Utilities.Drawing.LOG`, the same single object for the drawing code and the Plotter |
| `TauFW.common.tools.log` and a few `common` helpers | verbatim copies in `Drawing/_internal/legacy_log.py`, `legacy_helpers.py` |

Stateful drawing modules and loggers keep a single shared instance. The library accepts Plotter's `Variable` by
duck typing; `Plot` no longer re-exports `Variable`/`Var`.

#### ROOT expression helpers

`getselstr`, `joinweights`, `joincuts`, `replacepattern` and `cleanbool` moved unchanged from Plotter's `string.py`
to `TauFW.Utilities.Expressions` (no ROOT import), so Fitter can build cuts without Plotter. `string.py` re-exports
them; pico-specific helpers stay there. Existing defects L05–L07 remain in [Histogrammer BUGS](../Histogrammer/BUGS.md).

### Fitter imports drawing helpers from their own home

`Fitter/TauES_ID/{plot2DScan_MultiDimFit,plotParabola_POI_region,plotPostFitScan_POI}.py` and
`Fitter/python/plot/postfit_TES.py` import Drawing's `CMSStyle` directly. `postfit_TES.py` still takes `setera` from
Plotter because it updates both CMS text and sample normalization globals; the other files left the boundary inventory.

---

## 5. PicoProducer cleanup: command-level BBB tests and bug register

**Date:** 2026-10-12
**Details:** [Tests/README.md](../../Tests/README.md#picoproducer-command-cases-black-box),
[docs/PicoProducer/BUGS.md](../PicoProducer/BUGS.md)
**Tests/Validation:** [ValidationAndTests.md:60](ValidationAndTests.md#5-picoproducer-cleanup-command-level-bbb-tests-and-bug-register)

### What changed

- Added five command-level BBB cases: `pico.config`, `pico.run`, `pico.jobs`, `pico.merge`, `pico.workers`.
- Added a bug register with 60+ defects, their locations, severity, BBB coverage and planned fixes.

### Why

Protect command workflows during module moves; earlier baselines covered only lower-level operations.

---

## 6. PicoProducer cleanup: settings, datasets, storage, batch and jobs packages

**Date:** 2026-10-12
**Details:** [docs/PicoProducer/BUGS.md](../PicoProducer/BUGS.md)
**Tests/Validation:** [ValidationAndTests.md:74](ValidationAndTests.md#6-picoproducer-cleanup-settings-datasets-storage-batch-and-jobs-packages)

### A. Restructuring (no behavior change)

Split configuration into `settings/`, samples/catalogs/DAS into `datasets/`, storage adapters and validation
into `storage/`, schedulers/templates into `batch/`, and chunking/job configs into `jobs/`. Packages expose explicit
public APIs; in-repo callers and 46 sample catalogs were updated. Config defaults no longer import storage, batch or
ROOT; catalog path setup occurs only when loading samples. Config keys and values are unchanged.

| Old | Replacement |
|---|---|
| `TauFW.PicoProducer.storage.Sample` | `TauFW.PicoProducer.datasets` (the old module remains a re-export for private catalogs) |
| `TauFW.PicoProducer.tools.config` | `TauFW.PicoProducer.settings` |
| `storage.utils.getstorage / isvalid / getsamples` | `storage.getstorage / isvalid`; `datasets.getsamples` |
| `batch.utils.getbatch` | `batch.getbatch` |
| Custom `batch/<Name>.py` adapter | Register in `batch/factory.py`'s `SYSTEMS`; put templates in `batch/templates/` |

### B. Bug fixes

Fixed: S01 (SGE array submission), S02–S15 (batch lookup, adapter construction,
storage commands and merges, sample type detection, event totals, `Embedded` spelling with `Embdedded` kept as an
alias), P16 (private config attributes), P17 (fresh-install eras), P18 (`getconfig(write=False)`: only the CLI
rewrites the config). **Won't fix:** S16 (NAF users select `pico.py set batch HTCondor_NAF`). Details and output
impact per bug: [BUGS.md](../PicoProducer/BUGS.md).

### File-name correction

Eight case-only module renames were missing from Git, causing Linux import failures. Fixed in `ae0d9bf`.
Do case-only renames on Linux with `git mv`, or verify tracked spelling on Windows with `git ls-files`.

---

## 7. PicoProducer cleanup: job pipelines

**Date:** 2026-10-13
**Details:** [docs/PicoProducer/BUGS.md](../PicoProducer/BUGS.md), [API](../PicoProducer/API.md)
**Tests/Validation:** [ValidationAndTests.md:87](ValidationAndTests.md#7-picoproducer-cleanup-job-pipelines)

### A. Job pipelines

Split `pico/job.py` and `pico/run.py` into the `jobs/` package (`worker_command`, `request` with `JobRequest`,
`planner`, `pipeline`, `reporting`, `jobconfig`, `status`, `merge`, `local`), used by the public API (§8) and
the Framework. Configuration is passed explicitly instead of read from the global `CONFIG`; planning
(`iter_plans(..., materialize=False)`) writes nothing; the CLI keeps argument handling and prompts. Status classifiers
work on a copy of `chunkdict`, and `ChunkStatus.mergeable` (nothing pending or to resubmit) is the merge/cleanup gate
unless forced.

### B. Bug fixes

- **Crashes:** P01 (Python 2 `err.message`), P02 (submission prompt), P03 (`.json.gz` job configs),
  P07 (comparison instead of assignment).
- **Behavior:** P04 (`--checkqueue 1`), P05 (no matching samples), P06 (`maxevts` splitting), P11
  (failed local workers reported), P19 (cleanup only after a valid merge; `MergeResult.invalid`), P20 (prompt
  answers), P21 (unexpected event counts warned), P22 (status creates no directories), P23 (cleaning one tag keeps
  the others).
- **Module options:** P08 (precedence channel < sample < user `-E`), P09 (resubmission does not grow
  the options), P10 (no default `-m -1` for local runs).

---

## 8. PicoProducer cleanup: public API, command line, workers

**Date:** 2026-10-13
**Details:** [API](../PicoProducer/API.md), [I/O contract](../PicoProducer/IO.md),
[bugs](../PicoProducer/BUGS.md)
**Tests/Validation:** [ValidationAndTests.md:104](ValidationAndTests.md#8-picoproducer-cleanup-public-api-command-line-workers)

### A. API, CLI and workers

- **`api/`:** `PicoProducer` (`plan`, `iter_plan`, `submit`, `resubmit`, `status`, `merge`, `clean`, `run_local`)
  with frozen, JSON-serializable result records. `PicoProducer.from_config(config, reporter, basedir)` accepts the
  default config, a path, a dict or a `Config` without writing it; `plan()` writes nothing.
- **`cli/`** replaces `pico/` and calls the API; `scripts/pico.py` is a thin entry point. `settings/store.py`
  `loadconfig(path)` loads read-only. The Framework uses only the public API.
- **`processors/` is renamed `workers/`.**
- Limitations: file operations temporarily enter the PicoProducer directory (**not thread-safe**); reporting is silent
  by default (`ConsoleReporter` for terminal output).

### User migration and compatibility

Private imports change from `TauFW.PicoProducer.processors` to `TauFW.PicoProducer.workers`; config channels need no
change, and `pico.py resubmit` rewrites old job lists to `workers/`. Deprecated `processors/` import aliases
(`FutureWarning`) and script forwarders keep external scripts and old job lists working
([README](../../PicoProducer/python/processors/README.md)). **Removal:** delete `processors/` and
`Tests/PicoProducer/compat/` once no pre-2026-10-13 job lists remain in use.

### B. Command-line and worker fixes

Fixed: P12 (workers use `--opts`, not argparse prefix matching), P13–P14 (install dispatch, `cmssw` spelling), W02
(picojob description). **Won't fix:** P15 (status/merge/cleanup omit submission options), W01 (skim workers ignore
`-E/--opts`).

---

## 9. Framework: the TauFW orchestrator

**Date:** 2026-10-13
**Details:** [Framework/README.md](../../Framework/README.md)
**Tests/Validation:** [ValidationAndTests.md:114](ValidationAndTests.md#9-framework-the-taufw-orchestrator)

Added `TauFW.Framework` to run recipe-based pipelines with persisted state, replacing manually chained
PicoProducer, Plotter and Fitter commands.

### What changed

- **Framework:** `plan`, `start`, `advance`, `run`, `status` build stage requests and decide when to wait,
  resubmit or continue. Construction is read-only; waiting is explicit (`advance(wait=True)`).
- **Stages:** shared `Stage`/`StageOutcome` contracts and states NEW → SUBMITTED → WAITING → MERGING → DONE,
  plus FAILED/NOT_IMPLEMENTED. Production uses only the public PicoProducer API, with bounded retries.
- **Run record:** `run.json` stores the recipe/config snapshot, stage state and history, saved atomically after
  every stage step. The run directory and record format were extended in §14 and §17.
- **Reporting:** terminal output and `run.log` share Framework/PicoProducer messages; silent reporting is supported.
- **CLI:** `taufw.py plan RECIPE [--local -m N]`, `start RECIPE [--run-root DIR] [--wait --poll S]`,
  `advance RUN_DIR [--wait --poll S]`, `status RUN_DIR`; all delegate to Framework.
- **API boundary:** requests use the public PicoProducer API, loaded only for a production stage.
  Recipes are documented in the [analysis guide](../../Analyses/README.md).

---

## 10. Framework: plots, histograms and fit stages

**Date:** 2026-10-13
**Details:** [Framework](../../Framework/README.md), [Fitter bugs](../Fitter/BUGS.md), [Histogrammer (former Plotter) bugs](../Histogrammer/BUGS.md)
**Tests/Validation:** [ValidationAndTests.md:121](ValidationAndTests.md#10-framework-plots-histograms-and-fit-stages)

Connected control plots and the combined TES+TauID workflow through public APIs wrapping existing scripts.
Later internal cleanup can preserve these APIs without changing Framework.

### What changed

- **Utilities.Process:** sequential commands without a shell, per-command logs and stop on failure.
  Success requires exit 0 and fresh expected outputs, catching ignored nested failures and stale files.
- **Fitter.api.TauESID:** plan/make/preflight shapes (`run_inputs.sh`) and plan/run/preflight fits
  (`run_workflow_zmm.sh`, option 3); parses fit values. A control-plots API wraps `plot.py` (split in two in §21).
- **Stage context:** run directory and upstream artifacts flow between stages and plans. Preflight problems
  leave stages NEW for retry; local stages record DONE/FAILED and show failure log tails. Fit working points come
  from the recipe or histogram artifacts.
- **CLI:** plans show commands/preflight warnings; status shows fit values. See
  [bundled analyses](../../Analyses/README.md#bundled-analyses) and
  [current limitations](../../Analyses/README.md#current-limitations).

### Bugs fixed on the wrapped path

| ID | Fix |
|---|---|
| F01–F02 | Pass the requested year to JSON merging and ID correction generation. |
| F03 | Input drivers propagate mutau and mumu failures. |
| F04 | Remove the unused required `--input_file` argument and lookup; update callers. |
| F05 | Missing 1-sigma intervals no longer crash parameter-file writing. |
| F06 | Honor impacts options and pass `--impacts` from the workflow driver. |
| F07 | Read rebinned files from their actual output location. |
| L01 | Correct misspelled DeepTau branches in `plot.py`. |

Off-path F08–F10 and L02 were registered only.

---

## 11. Framework: analysis bundles and Python steps

**Date:** 2026-10-13
**Details:** [Analyses](../../Analyses/README.md), [Framework](../../Framework/README.md)
**Tests/Validation:** [ValidationAndTests.md:133](ValidationAndTests.md#11-framework-analysis-bundles-and-python-steps)

Bundles collect analysis configs in one directory; Python recipe steps add custom logic without a new stage class.

### What changed

- **Bundles:** recipes moved from `Framework/recipes/` to `Analyses/<name>/`, alongside configs and `steps/`.
  Commands accept a bundle directory; `taufw.py init NAME [--from RECIPE] [--root DIR]` creates one,
  copying referenced module configs without name collisions.
- **Paths:** bundle files replace module configs as whole files, without merging. Other relative paths retain
  module resolution; paths above the bundle stay outside it. Plans show each input's source.
- **Run isolation:** `start` copies the bundle to `<run dir>/bundle/` (50 MB limit; hidden files, caches and runs
  excluded). Later source edits do not affect the run. Loose recipes copy referenced files only.
- **Python steps:** `stage: python` specifies `file`, `function` (default `run`), `options`, `timeout` and optional `id`.
  Each runs in a separate process with bundle/upstream context and returns a message/artifacts. Preflight checks
  the function without importing it; failures show log tails.
- **Config propagation:** APIs pass `$TAUFW_PICO_CONFIG` to scripts. Loading is read-only; a missing configured file
  is an error. Shared command/result records moved to Utilities.Process, with existing API exports retained.

**Limitation:** PicoProducer's sample catalogs are not bundled; it resolves its own.

---

## 12. Import-boundary test and coupling inventory

**Date:** 2026-10-14
**Tests/Validation:** [ValidationAndTests.md:140](ValidationAndTests.md#12-import-boundary-test-and-coupling-inventory)

Added standard-library `Tests/check_import_boundaries.py`: stages cannot import each other; Framework may
import stage APIs; shared libraries remain available. Nested, parent-module and unresolved implicit imports
are checked; legacy directories and Tests are excluded. Python 2 imports are recovered separately.

The JSON inventory records known coupling and parse exemptions. **Known violations still fail**, as do stale
entries and import-recovery errors, so the check measures isolation progress without hiding existing debt.

Registered with the test runner. Production code is unchanged.

---

## 13. Framework: explicit stage ids, inputs and recipe validation

**Date:** 2026-10-14
**Details:** [Analyses](../../Analyses/README.md) "File format and validation", [Framework](../../Framework/README.md)
**Tests/Validation:** [ValidationAndTests.md:147](ValidationAndTests.md#13-framework-explicit-stage-ids-inputs-and-recipe-validation)

First step of the recipe IO work: the recipe, not the Framework, says which stage reads which stage's output, and every
problem of a recipe is shown at once. Run behaviour is unchanged otherwise.

### What changed

- **Every stage has `stage`, `id` and `inputs`, and may have `description`.** `id` is required for every stage and any
  stage may have any id. `description` is display text for `plan` and the menu.
- **Inputs:** each slot names an earlier stage producing the required data kind, or `null` for a supported external
  default (`$PICODIR` tuples or shapes in `Fitter/`). A stage without slots writes `inputs: null`; `{}` is an error.
  A stage now sees only its named inputs, rather than every earlier DONE stage. Python steps get `ctx.inputs` and
  `ctx.input(name, kind)`.
- **Validation collects every problem**, including unknown options and referenced files. `taufw.py check RECIPE`
  prints them and exits 1; recipe errors appear without a traceback in the CLI and are also shown by the menu.
- **Bundles** follow the new format; `Analyses/example_broken/` demonstrates invalid recipes.

---

## 14. Framework: run directory with logs/ and stages/, stage manifests

**Date:** 2026-10-15
**Details:** [Framework](../../Framework/README.md) "Run directory", [Analyses](../../Analyses/README.md) "Outputs and logs"
**Tests/Validation:** [ValidationAndTests.md:154](ValidationAndTests.md#14-framework-run-directory-with-logs-and-stages-stage-manifests)

Second step of the recipe IO work: a stage's directory in the run now holds only what the stage makes, so the
next step can run the Plotter and Fitter scripts inside it (§15).

### What changed

- **Layout:** `taufw_runs/<run>/logs/<id>/` holds the Framework's files of a stage (command logs `NN_<label>.log`, a
  python step's `context.json` and `result.json`); `taufw_runs/<run>/stages/<id>/` holds its output (a python step's
  own files, `ctx.stage_dir`). Previously both were `taufw_runs/<run>/<id>/`.
- **Ids:** stage directories live under `stages/`, so an id cannot clash with `run.json`, `run.log`, `bundle/` or
  `logs/`; only `.` and `..` are refused.
- **Manifest:** a DONE stage gets `stages/<id>/manifest.json`, describing its inputs and artifacts for reuse (§17).
  `run.json` stays the source of truth; failed stages have no manifest.
- **`run.json` schema 2:** the recipe format of §13 and this layout. A run directory of schema 1 is refused when it is
  loaded, without conversion.

---

## 15. Framework: Plotter and Fitter outputs in the run directory

**Date:** 2026-10-15
**Tests/Validation:** [ValidationAndTests.md:161](ValidationAndTests.md#15-framework-plotter-and-fitter-outputs-in-the-run-directory)

**Details:** [Framework](../../Framework/README.md) "Run directory", [Analyses](../../Analyses/README.md) "Stage
options" and "Outputs and logs", [scripts_arg_changes.md](scripts_arg_changes.md), Fitter BUGS F11-F24, Histogrammer
BUGS L08-L11

Third step of the recipe IO work: the plots, shapes and fit results of a run go to its stage directories, so runs no
longer overwrite each other in `Plotter/` and `Fitter/`, and the summary scripts no longer pick up the working points
of other runs.

### What changed

- **The Framework decides where a stage writes:** `LocalStage.output_dir(context)` = `<run_dir>/stages/<id>/`, passed
  to the module APIs as `outdir`. The fit also gets `shapes_dirs`, the shapes directory of each point, from its input
  stage's artifacts (a point without shapes there fails the stage before anything runs). No links, no copies.
- **Module APIs** (`PlotsRequest`, `ShapesRequest`, `FitRequest`: `outdir`; `FitRequest.shapes_dirs`). Without `outdir`
  the commands are exactly those of the shell scripts. With it the scripts run in the output directory (the fit in
  `<outdir>/<era>/`), with absolute script/config paths. Preflight refuses a non-empty output directory and a relative
  `picodir`. Shapes later requires `outdir` (§22 H3).
- **Scripts** (defaults unchanged): new output options in `makecombinedfitTES_SF.py` and `make_tid_2025.py`, and paths
  found from `__file__` instead of the working directory (L11, F14–F16); full list in
  [scripts_arg_changes.md](scripts_arg_changes.md).
- **Artifacts** are paths inside the stage directories: plots count only this run's files (L08–L10), the fit no longer
  lists other taggers' corrections (F22) and lists the combined TES + ID file.
- **`null` inputs:** a stage lists the slots that may be `null` and what it means (`Stage.null_inputs`); elsewhere
  `null` is a recipe error. The fit's `{shapes: null}` (the shapes in `Fitter/`) is a documented temporary exception.

---

## 16. Framework: tuples as an input, production writes into the run, run_root

**Date:** 2026-10-17
**Status:** done
**Details:** [Framework](../../Framework/README.md) "Concepts" and "Run directory", [Analyses](../../Analyses/README.md)
"Where the runs go (`run_root`)", [scripts_arg_changes.md](scripts_arg_changes.md) "Tuple location", Framework BUGS
K04, K05, K07, PicoProducer BUGS S17, Histogrammer BUGS L12
**Tests/Validation:** [ValidationAndTests.md:172](ValidationAndTests.md#16-framework-tuples-as-an-input-production-writes-into-the-run-run_root)

The Framework, not the global `$PICODIR`, decides where the pico tuples are read and written, and everything is
visible in the recipe.

### Recipe warnings and `run_root`

- **Warnings:** a recipe can have warnings besides its problems (it runs, but should change). `check` prints them and
  exits 0; `plan`, `start` and the menu show them.
- **`run_root`** (top-level key): the parent directory of the runs; `start --run-root` takes precedence; without both,
  `taufw_runs/` in the working directory with a warning. It must be absolute, not a URL, and outside the bundle; `~`
  and `$VARIABLES` are expanded with a warning. `plan` and `start` print the directory and where it comes from.
- **Write check:** before `start` with a run root and before every `advance`, the Framework writes and removes a small
  file there; on failure `RunDirectoryError` and nothing is started or moved.

### `--tuples` for the scripts and the APIs

- `getsampleset(..., tuples=PATTERN)`, `plot.py --tuples` and `createinputsTES.py --tuples`: the tuple directory
  pattern (`$ERA`, `$GROUP`) instead of `$PICODIR` from the PicoProducer configuration. Without it, unchanged.
- `PlotsRequest.tuples`, `ShapesRequest.tuples`: with a pattern every command gets `--tuples`, no
  `$TAUFW_PICO_CONFIG`, and preflight checks the pattern instead of the configuration (unknown `$KEYS` such as `$DAS`
  are refused).

### Production writes into the run

- PicoProducer: `JobRequest.tupledir` (never set by `pico.py`) makes `merge` write to
  `<tupledir>/$ERA/$GROUP/<sample>_<channel><tag>.root`.
- Framework: in a run, production's `tupledir` is its stage directory, and every tuple artifact gets `pattern`
  (`<run_dir>/stages/<id>/$ERA/$GROUP`), also visible in plans. `kind` on tuple artifacts is still missing (K04).

### Plots and histograms read the tuples their input names

- `{tuples: {external: <pattern>}}` names tuples made outside TauFW (absolute, not a URL; `check` reports a missing
  directory).
- The input pattern is passed to the APIs as `tuples=`; preflight checks its files or directory. `null` still uses
  `$PICODIR`, and `plan` displays the source.
- `Analyses/tes_id_2025` names the TauFW group's 2025 tuples with `{external: ...}`. K03 is fixed.

### Fix on the way: Histogrammer L13, Fitter F25

Fixed `plan` crashing when production precedes plots or histograms: ROOT detection now accepts an already imported
module, avoiding CMSSW's `find_spec('ROOT')` failure. This separate bug-fix commit changes no output.

---

## 17. Framework: inputs from another run's stage directory, repeated stages

**Date:** 2026-10-17
**Tests/Validation:** [ValidationAndTests.md:183](ValidationAndTests.md#17-framework-inputs-from-another-runs-stage-directory-repeated-stages)

**Details:** [Analyses](../../Analyses/README.md) "File format and validation" (stage order, "Inputs from another
run"), "Outputs and logs", "Troubleshooting"; [Framework](../../Framework/README.md) "Run directory"; TODO §6
"Revise: one rule for the paths in a recipe"

The last part of the recipe IO work (§13–§16): a stage may read the output of another,
finished run, and the built-in stages may repeat.

### Repeated stages, no fixed order

`plots`, `histograms` and `fit` may appear any number of times, each with its own id. The stages run in the order of
the recipe; the only order rule is that an input names a stage written above it. `production` stays at most once (its
job files are outside the run, and a run has one `pico.config`; TODO §6). Stage names later change in §21.

### Inputs from another run: `{path: <stage directory>}`

- **Recipe:** any input slot may be `{path: <run_root>/<run>/stages/<id>}`: absolute, not a URL, not inside the bundle;
  `~` and `$VARIABLES` are not expanded (unifying the path rules is TODO §6).
- **Manifest format 2:** adds the stage directory and sources. Missing or old manifests, moved/copied stage
  directories and module directories such as `Fitter/` are refused.
- **Checks:** the source stage must make the kind of data the slot takes. `check` and the menu report every problem
  at once; `plan` shows it as a note; `advance` stops the stage like a preflight problem.
- **Framework:** artifacts come from the source manifest and work like same-run inputs; the source is never modified.
- **Provenance:** the reader's run and manifest record the source path, run/stage identity, finish time and manifest
  hash; plans also identify the source. **`run.json` schema 3** refuses schema 2 runs.
- **Fitter API:** with `outdir`, a non-empty `shapes_dirs` must name every point (`ValueError`); `{shapes: null}` stays
  for old recipes only.

---

## 18. Menu and UI

**Dates:** 2026-10-17 to 2026-10-18
**Status:** the test screen and the operations behind the menu are in use; the run screens exist only in the UI
preview until the run lock lands (TODO §6 "Menu as a program").
**Tests/Validation:** [ValidationAndTests.md:194](ValidationAndTests.md#18-menu-and-ui)

The menu works like a program: a long operation (tests now, runs later) never prints into the terminal or blocks the
screen, and leaving a screen does not stop it.

- **Operations behind the menu** (`TauFW.Utilities.Process`): the existing CLI command runs as its own process under
  a small supervisor (standard library only), with stdin `/dev/null` and its output in a log file (ROOT and C++ write
  to the file descriptor, which no Python redirection catches). The supervisor writes a heartbeat and the exit status
  to files and stops the command when a `stop` or `kill` file appears, so any menu, also on another lxplus machine
  (AFS), can follow or stop it. `Operation.state()` gives DONE, FAILED, STOPPED, RUNNING, STOPPING, or LOST when the
  heartbeat is too old (lxplus may kill processes at logout). Esc leaves an operation running; stopping it or quitting
  the menu while something runs asks first. One test run at a time.
- **Progress as events:** one JSON object per line in the file named by `$TAUFW_EVENTS`. `Tests/run.py` and the BBB
  runner report their cases this way, `taufw.py` its runs, stages and commands (`EventReporter`). Without the
  variable the terminal output and `run.log` are unchanged; `taufw.py` removes it from the
  environment, so stage commands and batch jobs never see it.
- **Screens:** the test screen and the run screen share one core (`Utilities/python/Menu/_operation_screen.py`); the
  Menu imports no Framework module. Tests > UI preview shows every screen with made-up data.
- The recipe list shows each recipe's problems and warnings (§13, §16); "Continue an existing run" also lists the
  runs in every recipe's `run_root` (§16).

---

## 19. Configs: config templates with an id, a version and a lock

**Date:** 2026-10-17
**Status:** done
**Details:** [Configs/README.md](../../Configs/README.md)
**Tests/Validation:** [ValidationAndTests.md:206](ValidationAndTests.md#19-configs-config-templates-with-an-id-a-version-and-a-lock)

Analysts should not have to enter the module directories: everything an analysis can change is a copy in its bundle,
and the modules' templates for those copies live in `Configs/<Module>/`. Every template starts with a `taufw_config`
header (`id`, `version`, `schema`, `description`) that the copy keeps, so a later change of the template (e.g. a
corrected cross section) does not go unnoticed. This section built the infrastructure only; the first templates came
with §20.

- **`TauFW.Framework.configs`:** `scan` finds the templates and their problems (id must start with the module
  directory in lower case, unique); `content_hash` hashes the parsed values without the header, so comments and layout
  do not count; `update` keeps `Configs/configs.lock` (`<id> <version> <sha256>`), raising the version of a changed
  template (rewriting only that number) and refusing to write while a template has a problem or a lowered version;
  `copy_warnings` reports bundle copies whose template is newer, gone, or older than the copy.
- **Framework and CLI:** the copy warnings appear in `check`, `plan`, `start` and the menu (a warning only: an old copy
  kept on purpose is allowed). `taufw.py configs` lists the templates; `taufw.py configs update` (maintainers) raises
  versions and rewrites the lock.

---

## 20. Sample lists as data: the sample model

**Date:** 2026-10-17
**Tests/Validation:** [ValidationAndTests.md:215](ValidationAndTests.md#20-sample-lists-as-data-the-sample-model)

**Details:** [scripts_arg_changes.md](scripts_arg_changes.md) "Sample model files", [Histogrammer BUGS](../Histogrammer/BUGS.md) L14-L16

The recipe must say which samples an analysis reads; until now `Plotter/config/samples_v15.py` decided it out of sight
(MC cross sections, data datasets, weights, stitching, joining and splitting, per era). Its samples became templates
(§19), one per era, that an analysis copies into its bundle; they are in `Configs/Histogrammer/samples/` since §21.
**No physics or data change:** every sample set built from a template gets exactly the calls the old function makes.

- **Templates:** `export.py` wrote `v15_<era>.yml` for the 8 eras from recorded calls (nothing typed by hand);
  cross sections are cross section × k-factor as `samples_v15.py` computed them.
- **The model:** `Plotter/python/sample/model.py` (`load_sample_model`, `pick`, `sample_names`, `getsampleset`):
  the generic part of `samples_v15.getsampleset` copied as it is, the era part read from the model.
  Registered: L14 (`DM` split `NameError`, kept), L15, L16 (era `2526` with tautau/emu).
- **Scripts:** `samples_v15.getsampleset(..., samples=[files])` returns the model's sample set (marked BACKWARD
  COMPATIBILITY); `plot.py --samples` and `createinputsTES.py --samples` pass it on.
- **APIs:** `PlotsRequest.samples`, `ShapesRequest.samples`; `ControlPlots.sample_names`, `samples_problems`,
  `sample_file_problems` for preflight; `PicoProducer.sample_names(request)` lists what a production would make.
- **Framework and recipes:** `plots` and `histograms` take the option `samples` (bundle files or absolute paths).
  `TauFW.Framework.samples.sample_issues`: a requested sample that the recipe's production does not make is a problem,
  a produced sample nobody reads is a warning; `plan` shows them and `start` refuses problems.
  `Analyses/tes_id_2025` uses a copy of `v15_2025.yml`. `Analyses/example_mutau` was split in two:
  `example_mutau_short` is production only, and `example_mutau_long` produces data and the 22 MC samples of its sample
  file and then makes the plots.
- **Channel setups:** `Plotter/config/setup_*.yml` (7 files) became templates with headers (today in
  `Configs/Histogrammer/setups/`). `plot.py` and the postfit scripts read a channel name's setup from
  there, and so does the API.
- **`taufw.py init --from`** now copies every file of the source bundle (setup copies, sample files, Python steps), so
  the new bundle has every file its recipe names.

---

## 21. Plotter becomes Histogrammer; a clean Plotter is extracted

**Date:** 2026-10-18
**Status:** done
**Details:** [command migration](scripts_arg_changes.md#plotter-becomes-histogrammer-changelog-21-s1),
[histogram contract](../contracts/control-histograms.md)
**Tests/Validation:** [ValidationAndTests.md:233](ValidationAndTests.md#21-plotter-becomes-histogrammer-a-clean-plotter-is-extracted)

After drawing moved to Utilities (§4), the old Plotter mainly filled histograms: samples, normalisation, stitching,
RDataFrame, selections and QCD. It became `Histogrammer/`; a new Plotter draws from its histogram files.
The filling code moved without physics or data changes.

### Result

```text
pico tuples ──▶ Histogrammer ─────────────▶ hists/<era>/<channel><tag>.root ──▶ Plotter ──────▶ PNG
                fillhists.py --hists          contract                             draw.py
                [--no-draw]: samples,         taufw.control_histograms             draws only
                normalisation, QCD, filling
Framework:      controlhists                  the file is the artifact             controlplots
                (API ControlHists)                                                 (API ControlPlots)
```

Outside the compatibility aliases, Plotter imports only Utilities; Histogrammer and Plotter never import each other.

### The rename (S1)

| Old | New |
|---|---|
| `Plotter/` | `Histogrammer/` |
| `Plotter/plot.py` | `Histogrammer/fillhists.py` |
| `python/plot/` (`Variable`, `Selection`, `Context`, `string`) | `python/spec/` |
| `MultiDraw.py` / `.cxx` | `python/sample/` |
| `docs/Plotter/BUGS.md` | `docs/Histogrammer/BUGS.md` (same IDs) |

Only imports, module/path references and command help changed in the moved code. Framework uses the Histogrammer
API.

- **Old imports:** 13 alias modules in the new `Plotter/` preserve the same module objects, including shared era
  and luminosity state. No alias was added for the already broken `TauFW.Plotter.plot.datacard` import.
- **Old commands:** `Plotter/plot.py` and `Histogrammer/plot.py` print the new command with the same arguments
  and exit 2; they execute nothing.
- Fitter's config, macro and data paths now point to Histogrammer. Utilities exposes `HISTOGRAMMER_ROOT` and
  `HISTOGRAMMER_DATA_DIR`; the old `PLOTTER_*` names remain. Full path changes are in the command migration guide.

### Configs to Configs/Histogrammer/ (S2)

Moved 8 sample templates and 7 channel setups from `Configs/Plotter/` to `Configs/Histogrammer/`.
Their ids changed from `plotter.*` to `histogrammer.*`; values, version 1 and content hashes stayed the same.
Repository bundle copies and config readers use the new locations. The new Plotter needs no separate user config.

Old bundle ids still resolve to the renamed templates through `RENAMED_IDS`; `check`, `plan` and `start` warn
to update the copy's header, while preserving normal version warnings.

### The histogram file and draw.py (S3)

- `TauFW.Utilities.HistFile` provides a shared ROOT histogram/JSON format. Writing validates it; reading returns
  detached copies. The modules exchange files without importing each other.
- `TauFW.Histogrammer.controlhists` writes stacks **as filled, before drawing modifies them**, with selection
  and variable metadata, under contract `taufw.control_histograms` version 1.
- `fillhists.py --hists` also writes `hists/<era>/<channel><tag>.root`. Without this option its behavior is unchanged.
- New `Plotter/draw.py FILE [...] [-o OUTDIR] [-F] [-p] [-T TEXT] [-v]` draws those files with the old plot names,
  texts and CMS labels. Its implementation imports only Utilities.

### The histograms stage becomes shapes (S4a)

Renamed `stage: histograms` to `stage: shapes` (`HistogramStage` → `ShapesStage`): this stage makes TES input
shapes, distinct from control histograms. Commands and outputs are unchanged.

Old recipe names fail validation through `stages.RETIRED`. Runs whose records name `histograms` cannot be shown
or continued with `status`/`advance`; start them again. `tes_id_2025` now uses `id: shapes` and
`inputs: {shapes: shapes}` for the fit.

### Control plots as two Framework stages (S4)

- **`controlhists`:** Histogrammer's `ControlHists` / `HistsRequest` replace its old `ControlPlots` / `PlotsRequest`
  without aliases. It runs `fillhists.py --hists --no-draw`, producing `control_histograms` file artifacts.
- **`controlplots`:** the new Plotter API (`ControlPlots`, `PlotsRequest`, `HistFileInput`) draws each input file.
  Its required `hists` slot takes `control_histograms` and cannot be null; it produces `plots` artifacts.
  It accepts drawing options (`fraction`, `pdf`, `text`, `timeout`) and supports another run's input through `{path}`.
- **CLI:** `--no-draw` requires `--hists`, makes no plots directory, and warns that `-F`/`-p`/`-T` are ignored.
  Hand-run `fillhists.py` still fills and draws by default; changing that default is tracked in TODO §8.
- **Migration:** `stage: plots` is removed and fails validation with instructions to use the two stages.
  Runs naming the old stage cannot be continued. Bundles use `controlhists` id `hists` and `controlplots` id `plots`,
  retaining the plots under `stages/plots/plots/<era>/`.

`plot_postfit*`, `plot_v10` and the tutorial still fill and draw in one script (TODO §6). Compatibility aliases,
legacy commands, config-id mappings and retired-stage messages are temporary (TODO §8).

### Review fixes of §21

- Restored the moved `__init__.py` files and Git ignore exceptions so packages import correctly in fresh clones.
- HistFile rejects reserved/conflicting paths and non-histogram objects, and reports malformed headers clearly.
- The control-histogram reader reports missing metadata; the writer reports duplicate variable file names.

## 22. TES shapes leave the Fitter for the Histogrammer

**Dates:** 2026-10-18 to 2026-10-19
**Status:** done
**Details:** [TES shapes contract](../contracts/tes-shapes.md),
[command migration](scripts_arg_changes.md#tes-shapes-move-to-the-histogrammer-changelog-22-h1)
**Tests/Validation:** [ValidationAndTests.md:269](ValidationAndTests.md#22-tes-shapes-leave-the-fitter-for-the-histogrammer)

TES/ID input filling moved from Fitter to Histogrammer. Framework's `shapes` stage now uses Histogrammer's
`TESShapes` API; the four maintained channel configs live in `Configs/Fitter/tes_id/`, shared with the fit.

### Result

```text
pico tuples ──▶ Histogrammer ──▶ TES/ID shape files ──▶ Fitter
                createinputsTES.py   contract: tes-shapes.md   run_workflow_zmm.sh
Framework:      shapes (TESShapes)                            fit (TauESID)
Shared configs: Configs/Fitter/tes_id/
```

Fitter's Python API no longer names Histogrammer paths; stages share files and channel configs.

### File and config contract (H0)

Wrote the file/config contract shared by filling and fitting.

### The move (H1)

Moved the filling code with function bodies unchanged:

| Old | New |
|---|---|
| `Fitter/python/plot/datacard.py` | `Histogrammer/python/shapes/inputs.py` |
| `Fitter/python/plot/rebinning.py` | `Histogrammer/python/shapes/rebinning.py` |
| `Fitter/TauES/createinputsTES.py` | `Histogrammer/shapes/TauES/createinputsTES.py` |
| `Fitter/{ETauFR,HighPT,paper,tutorial}/createinputs.py` | `Histogrammer/shapes/<Variant>/createinputs.py` |

- **Working directories:** `Fitter/run_inputs*.sh` calls the new script from `Fitter/`; shapes still land in
  `Fitter/input_pt_less_region/`. Variants still run from `Fitter/<Variant>/`.
- **Compatibility:** five old script paths print the new command with the same arguments and exit 2, importing
  and executing nothing. No aliases for `TauFW.Fitter.plot.datacard` / `.rebinning`;
  `Fitter/MuTauFR/createinputs.py` stays.
- The boundary detector now recognizes module-local implicit imports without hiding unresolved ones.

### Channel configs to Configs/ (H2)

Moved `config_coarse_TT.yml`, `config_coarse_PNet.yml`, `config_coarse_UParT.yml` from `Fitter/TauES_ID/config/`
and `FitSetup_mumu.yml` from `Fitter/TauES/config/` to `Configs/Fitter/tes_id/`. Added locked version-1
`fitter.tes_id_*` headers and grouped keys by reader; parsed values and repository bundle copies stay equivalent.

- **Recipes:** `Configs/...` paths resolve against TauFW and reach APIs as absolute paths; a bundle file wins.
  `taufw.py init --from` copies referenced templates, and `check` reports missing ones.
- **Old paths:** recipes naming the four old module paths fail `check`, `plan` and `start` with the new location
  (`stages.MOVED_CONFIGS`). Hand-typed old script config paths give file-not-found; there is no fallback.
- Run scripts and the shapes/fit defaults use the new templates.

### TES shapes API to the Histogrammer (H3)

- `TESShapes` and `ShapesRequest` moved to `TauFW.Histogrammer.api`, preserving planning, making and preflight
  methods, commands, shape names and artifacts. Fitter's `TauESID` keeps only the fit; no API shim is retained.
- **`outdir` is required:** omitting it raises `ValueError`. The shapes API no longer writes implicitly into
  `Fitter/`; hand-run `Fitter/run_inputs.sh` keeps its working directory and behavior.
- Framework's shapes stage uses `TESShapes`, with `ControlHists` for samples; the fit stage uses only Fitter's API.
- Shapes configs must be bundle files, `Configs/` templates or absolute paths. Other module-relative paths fail
  recipe validation with migration advice. Fit configs still accept paths relative to `Fitter/`.

Registered, not fixed: [Histogrammer BUGS](../Histogrammer/BUGS.md) L18–L24 and [Fitter BUGS](../Fitter/BUGS.md) F26.
The five legacy stubs and `stages.MOVED_CONFIGS` remain until the migration point (TODO §8).

## 23. Variation tuples in the shapes preflight

**Date:** 2026-10-19
**Tests/Validation:** [ValidationAndTests.md:310](ValidationAndTests.md#23-variation-tuples-in-the-shapes-preflight)

**Details:** [TES shapes contract](../contracts/tes-shapes.md#variation-tuples-input-of-the-writer),
`LocalR/architecture/ModuleIsolationFinalizations.md` §3 A (plan 16 D8)

`createinputsTES.py` opens the variation tuples (`_TES0p950`, `sampleAppend`: `_LTF1p030`, `_JTF0p900`, ...) only
after the nominal histograms; a missing one failed hours into a run (`Sample.appendfilename` -> `setnevents`). The
`shapes` preflight checked only the nominal `<sample>_<channel>.root`. Now it names every variation file first.

- New `Histogrammer/python/sample/variations.py` (ROOT-free): `variations(setup, model, era)` replays what the script
  does to the sample set on names: the model's stitching and joins (`model.getsampleset` with `split=[]` and the
  config's `samples.join`), the config's `samples.split` and `samples.rename`, then `SampleSet.shift(..., split=True)`
  for each TES value and each shape systematic with a non-empty `sampleAppend`. Matching is the sample code's own
  (`TauFW.Utilities.Drawing.labels.match`: glob, substring, any term), so `"W"` also takes `WWto*` or `ST tW` when
  VV/ST are not joined, as the script does. Labels: every name and the sample model's titles; the SampleStyle titles
  of merged and split samples need ROOT and are not used (a process found only through such a title is missed: no
  false alarm, the run fails late as before). Systematics with weights only (`altWeights`) read the nominal files.
- `TESShapes.variation_problems(request)`, called by `preflight_shapes`: per config and era, the files
  (`_tuple_file` + the tag before `.root`, as `appendfilename`) that are missing, as one problem: "105 of 144
  variation tuple file(s) of config config_coarse_TT.yml, era 2025, not found (_TES0p950: 9, ...): <5 paths>, ...".
  Only with a tuple pattern (not a plan placeholder) and sample model files, as the nominal check; an unreadable
  config or sample file is left to the other checks. `check`/`plan` show it as a note before a run; in a run the
  shapes stage stops in its preflight before any command (after the stages before it, which take minutes, not the
  hours of the shapes). The script itself is unchanged (run by hand it still fails late; user decision 2026-10-19).
- `tes_id_2025` (mutau, 2025): 144 files: TES 10 x 9 (DY, through `ZTT`), LTF 2 x 12 (DY + TT: `ZL`, `TTL`),
  JTF 2 x 15 (DY + TT + WJ: `ZJ`, `TTJ`, `W`); the mumu config has none.

## 24. Review of the tes_id_2025 bundle: fit-result comparison, result files in the summary

**Date:** 2026-10-19
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#24-review-of-the-tes_id_2025-bundle-fit-result-comparison-result-files-in-the-summary)

**Details:** TODO §1 "Framework, TES/ID bundle"

A review of `Analyses/tes_id_2025` as the way to run the TES + tau ID measurement today. The bundle is complete,
not a placeholder: its copies of the five configs are the `Configs/` templates byte for byte, and `plan` gives the
commands of `run_inputs.sh` (VTight/Tight, mutau and mumu) and of `run_workflow_zmm.sh` for that point (13 fit
commands, the five summary scripts included). What was missing is the tool for the one open check, the whole run
against the shell drivers, and a pointer to the results. Physics and the stages are unchanged.

- New `Tests/tools/compare_fitresults.py` (no ROOT): compares two fit result trees by relative path (the shell
  drivers' `Fitter/` and a run's `stages/fit/<era>/` have the same layout): `FitparameterValues_*.txt` parameter by
  parameter (parameters of interest with their own absolute tolerance `--poi-atol`, e.g. one grid step;
  `--pois-only` leaves the nuisance parameters out), the correction JSON files of `tau_sf/` and `data/tau/` value by
  value (`--rtol`/`--atol`), the `tau_sf/*.root` files by name. Test: `Tests/tools/test_compare_fitresults.py`.
- `tes_id_2025/steps/fit_summary.py`: `summary.txt` also lists the correction files of the fit (per point and the
  era files of the summary step, a missing one marked), the results to copy to their final place.
- `tes_id_2025/recipe.yml` (comments only): the commands as on lxplus (`python3 taufw.py`, `check`, `start
  --run-root`), where the results are, and how to continue after a failed stage (a new run reusing the finished
  stages through `{path: ...}`).
- `Analyses/README.md`: a section reference left from before the renumbering (§25 H3 -> §22 H3).

## 25. Postfit scripts set the era through CMSStyle (no Plotter import)

**Date:** 2026-10-19
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#25-postfit-scripts-set-the-era-through-cmsstyle-no-plotter-import)

**Details:** `LocalR/architecture/ModuleIsolationFinalizations.md` §3 B1 (plan 16 D7, TODO §0 (1))

The four postfit scripts imported `TauFW.Plotter.sample.utils` (the alias of `TauFW.Histogrammer.sample.utils`) only
for `setera(era)`. Of what `setera` does, only `CMSStyle.setCMSEra(str(era), **kwargs)` reaches the drawing (the
era/lumi text); the Histogrammer's own `era`/`lumi`/`cme` are read by the samples, which these scripts do not use.

- `Fitter/python/plot/postfit.py`: `CMSStyle.setCMSEra(era)`; `Fitter/tutorial/plotpostfit.py`,
  `Fitter/ETauFR/Plotter/plotpostfit.py`: `CMSStyle.setCMSEra(era,extra="")` (the same keyword `setera` passed on).
- `Fitter/python/plot/postfit_TES.py`: the `setera(era)` block is deleted, not replaced: the function calls
  `CMSStyle.setCMSEra(era, cms="CMS", extra="Preliminary")` a few lines later, which sets all three texts again.
- Lost: `setera`'s warning for an era without a luminosity (log only; the text then has no lumi either way). The
  `gROOT.SetBatch(True)` of the old import still happens: the scripts import `Stack`/`Plot`/`hist_tools`.
- User decisions (2026-10-19): `CMSStyle.setCMSEra` directly, no new era setter in `Utilities.Drawing`; proof by a
  text comparison on lxplus, no postfit PNG comparison.
- `Tests/import_boundary_allowlist.json`: the four entries removed. Coupling 25 / 23 / 21 -> 21 / 19 / 17, Fitter ->
  Plotter 9 / 8 / 7 -> 5 / 4 / 3 (left: `Zpt`, `MuTauFR`, B2/B3).
- `Tests/tools/check_setera.py` (lxplus, ROOT): for every era of `CMSStyle.lumi_dict`, a number, an unknown era and
  the `extra=""` call, the same starting style, then `setera` and `setCMSEra`: `cmsText`, `extraText`, `lumiText`
  compared.

## 26. The luminosity of the normalisation in the sample model and the control-histogram file

**Date:** 2026-10-19
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#26-the-luminosity-of-the-normalisation-in-the-sample-model-and-the-control-histogram-file)

**Details:** `LocalR/architecture/22-data-contracts-plan.md` (C1, decisions K1-K3, K5),
[control-histograms contract](../contracts/control-histograms.md), `Histogrammer/python/sample/model.py`

The MC is normalised with `lumi x xsec / sumw`. Until now `setera(era)` took `lumi` from `CMSStyle.lumi_dict`, a table
in the drawing library that also makes the CMS label; changing a luminosity meant editing drawing code, outside the
versioned configs, and no output recorded which value was used. The Plotter recomputed the label from the same table.

- **Sample model schema 2** (`model.py`): `lumi` [/fb] is required (a positive number, as `cme` now); `getsampleset`
  calls `setera(era, lumi=model.lumi, cme=model.cme)`. A schema-1 file is refused: "schema 1 had no lumi: copy the
  template ... again, or add lumi: ... and set schema: 2".
- **Templates** `Configs/Histogrammer/samples/v15_*.yml` (8) and the bundle copies (`tes_id_2025/v15_2025.yml`,
  `example_mutau_long/v15_2022_postEE.yml`): `lumi:` with the value `setera` looked up before (`lumi_dict[era]`, else
  of the year), `schema: 2`, version 1 -> 2 (`configs.update`, lock). `export.py` writes the line (from the table) and
  reproduces the eight templates (only the header version differs).
- **Control histograms version 2**: the file metadata has `lumi` and `cme`, the values the samples were normalised
  with (`fillhists.py` passes the Histogrammer's `GLOB.lumi`, `GLOB.cme` after `setera`); `draw.py` labels with
  `setCMSEra(era, lumi=, cme=)`. Version 1 is refused with a message (decision K3: no compatibility; run
  controlhists again).
- Without a sample model (`samples_v15.py`, commands without `--samples`) nothing changes: `setera(era, cme=13.6)`
  looks the luminosity up in the table, and that value goes to the file.
- **Physics:** the same numbers (every template value equals the table lookup, checked by a test), so the same
  normalisation and the same labels. BBB `plotter.sample_model` records the arguments of `setera` and gains `lumi=`:
  re-lock of that case only, approved by the user (K2); `plotter.stack` and `histogrammer.tes_inputs` must pass
  without re-lock. The case `plotter.stack` passes `lumi`/`cme` to the writer (its locked canvases do not include the
  file metadata). The case `histogrammer.tes_inputs` writes its own mini sample model: it got `lumi: 110.18` (the table value of 2025, so the same normalisation); missed at first, found by `bbb check` on lxplus (2026-10-19), fixed before any re-lock.

## 27. The fit plots show the luminosity of the normalisation; explicit lumi on the samples

**Date:** 2026-10-19
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#27-the-fit-plots-show-the-luminosity-of-the-normalisation-explicit-lumi-on-the-samples)

**Details:** `LocalR/architecture/22-data-contracts-plan.md` (C1, after CL §26),
[command changes](scripts_arg_changes.md#cms-label-of-the-fit-plots-changelog-27)

After CL §26 the control plots showed the luminosity the histograms were normalised with, but the fit plots (postfit,
NLL parabolas, scans, measurements) still read `CMSStyle.lumi_dict`: with a bundle lumi other than the table's, the
fit would use one value and its plots show another. Two smaller points from the same review: two scripts wrote a
fixed "109 fb^-1" for an era missing from the table, and the samples took their lumi from a module global that
`setera` must have set before they were built.

- **Shapes artifacts** (`TESShapes`): `lumi`, `cme` of the era's sample model (`None` without sample files). The
  `fit` stage turns them into `FitRequest.labels` `(era, lumi, cme)` (`FitStage.labels`; different values for one era
  are an error); shapes without them (no sample model, old runs) give none.
- **Fitter API**: with a label for the era, `makecombinedfitTES_SF.py`, `makecombinedfitTES_SF_postfit.py`,
  `runpostfit.py` and `plot_measurements.py` get `--lumi <value> --cme <value>`.
- **Scripts** (opt-in options; without them nothing changes): `--lumi`/`--cme` in `plotParabola_POI_region.py`,
  `plotPostFitScan_POI.py` (`setCMSEra(year, lumi=, cme=)`), `plot2DScan_MultiDimFit.py`, `plot_measurements.py`
  (their own text), `runpostfit.py` -> `postfit_TES.drawpostfit(..., lumi=, cme=)`; the two `makecombinedfit` scripts
  pass them on to the plot scripts they start.
- **Fixed 109**: `plot_measurements.py` `lumi_label` and `plot2DScan_MultiDimFit.py` `lumi_text` show no luminosity
  for an era that has none (only the energy), as `CMSStyle.getCMSLumiText` does; for the eras of the table the text is
  unchanged.
- **Explicit lumi on the samples** (`model.getsampleset`): `lumi=model.lumi` goes to the core `getsampleset`, so every
  sample gets it as an argument instead of copying the module global (`Sample.py:65`); the global is still set (for
  the label of in-process plots and the old path). `fillhists.py` writes to the control-histogram file the lumi the
  samples carry (`controlhists.normalisation_lumi`, an error if they differ), no longer the global.
- **BBB**: `plotter.sample_model` gains `lumi` also in the core `getsampleset` call (the same value); still covered by
  the approval of plan 22 K2 (only `lumi` differs). The fit scripts have no BBB case (they need combine).

---

## 28. One advance per run, a safe stop, the command log in the progress events

**Date:** 2026-10-21
**Status:** done on Windows (unit tests); lxplus check in TODO §1 "Run lock and safe stop on lxplus"
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#28-one-advance-per-run-a-safe-stop-the-command-log-in-the-progress-events)

Part 1 of the run wiring of the menu (TODO §6 "Menu as a program"): what the menu needs from the Framework before
Start/Continue can run behind it. The CLI keeps its commands and its output; two cases change on purpose (user,
2026-10-21): a second advance of a run is refused, and Ctrl-C during a job submission waits for it.

- **Advance lock** (`Framework/python/run_lock.py`): `Framework.advance` holds `<run_dir>/advance.lock` (`host`,
  `pid`, `since`, `t`; made with `O_EXCL`, no `flock` on AFS/EOS) while it works and waits; a thread renews `t` every
  5 s, the file is removed at the end (also after an error). Before (two terminals, or two lxplus nodes): both
  advances submit, resubmit and merge the same jobs. After: the second one gets `Cannot advance run <id>: the run is
  being advanced on lxplus801 since 2026-10-21 14:02:00 (pid 4711)` and exit code 1. A lock is lost after 120 s
  without a sign of life, or at once when its process is gone on this machine; a lost lock of this machine is taken
  over without asking, one of another machine with `taufw.py advance RUN_DIR --take-lock` (the refusal names it). A
  live lock is never taken; an advance whose lock was taken over stops before its next step (`RunLockError`).
  `read_lock(run_dir)` gives the lock with `quiet` and `lost` (for the menu's `run_lock()` screen). Not in `run.json`.
- **Safe stop** (`Framework/python/interrupts.py`, `Stage.submits`): a production step that may submit or resubmit
  (from NEW, SUBMITTED, WAITING) and the save of `run.json` after it run with SIGINT held back: the first Ctrl-C prints
  `Stage production: stopping once run.json records this step (Ctrl-C again to force)` and stops after the save, a
  second one stops at once. Every other step (merge, the local stages, the `--wait` sleep) stops at once as before;
  a local command is ended by `subprocess.run`. In a terminal the Ctrl-C also reaches `condor_submit` itself (same
  process group): only the Python side is protected there.
- **Supervisor** (`Utilities/python/Process/_supervisor.py`, `OperationStore.start(signal=)`): `signal: "command"`
  sends a stop's SIGINT to the command alone (taufw.py), not to its process group, so a run stopped from the menu
  never cuts `condor_submit`. The default stays `"group"` (tests); the `kill` file and the escalation still end the
  group.
- **Command log in the progress events** (`ProcessRunner.run_all`, `stages/local.py`): the progress callback gets a
  fifth argument, the command's log path (now chosen before the command starts), and the `progress` events carry it
  as `log`; the run screen shows that log. The printed progress lines are unchanged.
- **BBB:** `framework.production` is unchanged by design: the lock is outside `run.json` and the compared trees, and is
  gone when `advance` ends; `status` is unchanged.
