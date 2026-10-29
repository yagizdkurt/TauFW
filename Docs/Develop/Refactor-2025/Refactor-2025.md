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
**Details:** [Tests/README.md](../../../Tests/README.md), [Tests/LEGACY_BROKEN_CASES.md](../../../Tests/LEGACY_BROKEN_CASES.md)
**Tests/Validation:** [ValidationAndTests.md:19](ValidationAndTests.md#1-test-migration-and-bbb-regression-tests)

### What changed

- **Tests moved to top-level `Tests/`.** Moved 38 test files unchanged.
  [Tests/migration.json](../../../Tests/migration.json) records original paths and content hashes.
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
**Details:** [Docs/Guide/FastSetup.md](../../Guide/FastSetup.md)
**Tests/Validation:** [ValidationAndTests.md:42](ValidationAndTests.md#2-fastsetup-script)

### What & Why

- Added [setup.sh](../../../setup.sh) that automates installation and standardizes the ref env used for BBB tests.

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
**Details:** [Utilities/README.md](../../../Utilities/README.md), [Utilities/IOInventory.md](../../../Utilities/IOInventory.md)
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
them; pico-specific helpers stay there. Existing defects L05–L07 remain in [Histogrammer BUGS](../Bugs.md#histogrammer).

### Fitter imports drawing helpers from their own home

`Fitter/TauES_ID/{plot2DScan_MultiDimFit,plotParabola_POI_region,plotPostFitScan_POI}.py` and
`Fitter/python/plot/postfit_TES.py` import Drawing's `CMSStyle` directly. `postfit_TES.py` still takes `setera` from
Plotter because it updates both CMS text and sample normalization globals; the other files left the boundary inventory.

---

## 5. PicoProducer cleanup: command-level BBB tests and bug register

**Date:** 2026-10-12
**Details:** [Tests/README.md](../../../Tests/README.md#picoproducer-command-cases-black-box),
[Docs/Develop/Bugs.md#picoproducer](../Bugs.md#picoproducer)
**Tests/Validation:** [ValidationAndTests.md:60](ValidationAndTests.md#5-picoproducer-cleanup-command-level-bbb-tests-and-bug-register)

### What changed

- Added five command-level BBB cases: `pico.config`, `pico.run`, `pico.jobs`, `pico.merge`, `pico.workers`.
- Added a bug register with 60+ defects, their locations, severity, BBB coverage and planned fixes.

### Why

Protect command workflows during module moves; earlier baselines covered only lower-level operations.

---

## 6. PicoProducer cleanup: settings, datasets, storage, batch and jobs packages

**Date:** 2026-10-12
**Details:** [Docs/Develop/Bugs.md#picoproducer](../Bugs.md#picoproducer)
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
impact per bug: [Bugs.md](../Bugs.md#picoproducer).

### File-name correction

Eight case-only module renames were missing from Git, causing Linux import failures. Fixed in `ae0d9bf`.
Do case-only renames on Linux with `git mv`, or verify tracked spelling on Windows with `git ls-files`.

---

## 7. PicoProducer cleanup: job pipelines

**Date:** 2026-10-13
**Details:** [Docs/Develop/Bugs.md#picoproducer](../Bugs.md#picoproducer), [API](../../Guide/PicoProducer/API.md)
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
**Details:** [API](../../Guide/PicoProducer/API.md), [I/O contract](../../Guide/PicoProducer/IO.md),
[bugs](../Bugs.md#picoproducer)
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
([README](../../../PicoProducer/python/processors/README.md)). **Removal:** delete `processors/` and
`Tests/PicoProducer/compat/` once no pre-2026-10-13 job lists remain in use.

### B. Command-line and worker fixes

Fixed: P12 (workers use `--opts`, not argparse prefix matching), P13–P14 (install dispatch, `cmssw` spelling), W02
(picojob description). **Won't fix:** P15 (status/merge/cleanup omit submission options), W01 (skim workers ignore
`-E/--opts`).

---

## 9. Framework: the TauFW orchestrator

**Date:** 2026-10-13
**Details:** [Framework/README.md](../../../Framework/README.md)
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
  Recipes are documented in the [analysis guide](../../../Analyses/README.md).

---

## 10. Framework: plots, histograms and fit stages

**Date:** 2026-10-13
**Details:** [Framework](../../../Framework/README.md), [Fitter bugs](../Bugs.md#fitter), [Histogrammer (former Plotter) bugs](../Bugs.md#histogrammer)
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
  [bundled analyses](../../../Analyses/README.md#bundled-analyses) and
  [current limitations](../../../Analyses/README.md#current-limitations).

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
**Details:** [Analyses](../../../Analyses/README.md), [Framework](../../../Framework/README.md)
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
**Details:** [Analyses](../../../Analyses/README.md) "File format and validation", [Framework](../../../Framework/README.md)
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
**Details:** [Framework](../../../Framework/README.md) "Run directory", [Analyses](../../../Analyses/README.md) "Outputs and logs"
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

**Details:** [Framework](../../../Framework/README.md) "Run directory", [Analyses](../../../Analyses/README.md) "Stage
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
**Details:** [Framework](../../../Framework/README.md) "Concepts" and "Run directory", [Analyses](../../../Analyses/README.md)
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

**Details:** [Analyses](../../../Analyses/README.md) "File format and validation" (stage order, "Inputs from another
run"), "Outputs and logs", "Troubleshooting"; [Framework](../../../Framework/README.md) "Run directory"; TODO §6
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
**Status:** done
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
**Details:** [Configs/README.md](../../../Configs/README.md)
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

**Details:** [scripts_arg_changes.md](scripts_arg_changes.md) "Sample model files", [Histogrammer BUGS](../Bugs.md#histogrammer) L14-L16

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
| `docs/Plotter/BUGS.md` | `Docs/Develop/Bugs.md#histogrammer` (same IDs) |

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

Registered, not fixed: [Histogrammer BUGS](../Bugs.md#histogrammer) L18–L24 and [Fitter BUGS](../Bugs.md#fitter) F26.
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
**Status:** done
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

---

## 29. Start and Continue run behind the menu

**Date:** 2026-10-21
**Status:** done
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#29-start-and-continue-run-behind-the-menu)

The wiring of the run screens (TODO §6 "Menu as a program", parts 4a-4c); decisions of the user, 2026-10-21. Before:
Start and Continue ran `taufw.py start`/`advance` inside the menu's own process: with "Keep checking" the menu was
blocked for hours, printed plain terminal output and the run ended with the screen. After: they run as operations
behind the menu (CL §18), like the tests, and the run screen follows them.

- **Start** (`_Operations.start_run`): `taufw.py start RECIPE --wait` (to the end), the screen opens at once. The
  stages come from the recipe; the run id and directory from the `run` event once the run directory exists.
- **Continue** (`advance_run`): "Advance to the end" (`advance --wait`, default 600 s between checks; the poll
  prompt is gone) or "Advance once" (`advance`). The stages and their states come from `run.json`. A run that an
  advance works on now (any menu, any machine) opens its screen instead of a second advance.
- **Run operations:** `kind="run"`, `signal="command"` (a stop reaches taufw.py alone, which finishes a job
  submission first, CL §28), `escalate=False`; the last five records are kept.
- **Main menu and run list:** a line per advance that runs or ended unseen ("Run tes_2025 (3/5 plots)", "Runs (2
  active)"); the run list shows each run's newest advance. A finished advance stays listed until its result card was
  shown once (`seen` file in the operation directory, `Operation.mark_seen`); starting a new advance of a run marks
  the older ones seen.
- **Run lock** (`run_lock(run_dir)`, `read_lock` + `local`): a run whose lock another advance holds shows the lock
  screen; a lost lock of another machine can be taken over there (`advance --take-lock`); a lost lock of this
  machine is taken over by the advance itself without a screen.
- **Grid proxy:** a recipe with a production stage, or a run whose production stage is not finished, needs a valid
  proxy before it starts (the jobs read their input with it, and taufw.py behind the menu cannot ask for the
  password): the "Grid proxy needed" screen offers the renewal.
- **Quit warning:** says what happens to runs at logout (Lost; Continue resumes, at once from this machine, after 2
  minutes with Take over from another), that Stop all lets a job submission finish.
- **Fix found on lxplus (2026-10-21):** a run stopped with S stayed STOPPING: the supervisor ignored SIGINT with
  `SIG_IGN`, which the command inherits, and Python then never raises KeyboardInterrupt; the test runs stopped only
  through the SIGTERM escalation, which runs do not have. The supervisor now catches SIGINT with a handler that does
  nothing (reset at exec), so taufw.py and Tests/run.py get the stop as Ctrl-C
  (`RealStopTests.test_a_run_stop_is_a_keyboardinterrupt_in_the_command`, lxplus only).
- **From the lxplus menu tests (2026-10-21):** an operation that exits 0 is DONE also when its stop came too late
  (it was STOPPED); a lost advance stays in the main menu until a newer advance of its run starts or its run ends,
  not only until its card is seen; Continue also lists the runs of the advances behind the menu (a recipe outside
  `Analyses/`, another run root); a stage that runs one command is not counted ("1/2 slow", not "1/2 slow, 1/1"),
  several are "3/5 plots, 5/7 commands"; the stopped and lost cards mention submitted jobs only for runs with a
  production stage; the take-over warning says "its process is gone" whenever that is known (`read_lock` `gone`).
- **Info box (part 4d, first version):** the box next to the stage list shows each stage's options as written in the
  recipe (config, eras, channels, file, ...), its inputs, its output directory (`stages/<id>/`) and, on Continue,
  the attempt (`interactive._stage_info`). Without facts the screen has no box, which is why the live screen looked
  different from the preview before. Fields per stage type can still be chosen later.
- Removed: `poll_interval`, `invalid_poll_interval` (UI), `validate_poll` (adapter), the "polling interval" preview
  screen; added the "grid proxy needed" preview screen. Plan and status still run in the menu's process (TODO §6
  step 3). The info box next to the stage list stays empty until its fields are chosen (part 4d).

## 30. Plan and status run behind the menu, their output on a screen

**Date:** 2026-10-21
**Status:** done
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#30-plan-and-status-run-behind-the-menu-their-output-on-a-screen)

TODO §6 "Menu as a program", step (3); decisions of the user, 2026-10-21: the plain output in a scrollable screen
(option a, not a designed status screen), Esc stops a running command without a question, no `check` in the menu
(the recipe and run lists already show the problems). Before: "View detailed plan" and "Inspect run status" ran
`cmd_plan`/`cmd_status` in the menu's own process (`_execute`): plain terminal text over the curses screen, then
"Press Enter"; a status with production asks HTCondor, so the menu froze for seconds. After: they run as
operations behind the menu, like the tests and runs (CL §18), and a screen shows their output.

- **Adapter** (`_Operations.start_command(command, target)`): `taufw.py plan RECIPE` or `taufw.py status RUN_DIR`
  as an operation of `kind="command"` (data: command, target; the default stop: SIGINT to the group, then
  escalation; both only read), the last five records kept. `running_operations()` leaves them out: the screen
  stops them, so they never count as running behind the menu (no main-menu line, no quit warning).
- **Screen** (`Menu/_command_screen.py`, `ConsoleUI.command_output(title, process, refresh)`): the operation screen
  with the model `CommandOutput`, which has no items, so only the Output view (Up/Down/PgUp/PgDn, End follows the
  end; colour codes removed; long lines wrap). State line: "RUNNING | 00:04 | taufw.py status", "(exit 1)" after a
  failure. Esc stops a command that still runs and leaves; S stops it and stays (no question); with `refresh`
  (status) R runs it again once it ended. `ScreenModel` got `leave_stops` and `actions` (keys that leave once the
  operation ended, with `model.answer`); the test and run screens are unchanged.
- **Navigation:** the review's "View detailed plan" opens "Plan: <recipe>", Inspect opens "Run status: <run id>"
  with R Refresh, also from Continue on a run that cannot advance. An error before the screen opens (e.g. the
  operations directory is not writable) is printed with "Press Enter" as before (step 4).
- Removed: `_Operations.execute` and the `commands` argument of `Menu`/`run_menu` (`taufw.py` calls
  `run_menu(build_parser())`): nothing runs in the menu's process any more. `MenuNavigation._execute`,
  `ConsoleUI.status_actions` (the Refresh/Back screen) and `ConsoleUI.interrupted_operation`. The CLI is unchanged.
- **UI preview:** "detailed plan (taufw.py plan behind the menu)" and "run status, HTCondor answers after 4 s"
  replace "status actions". In the preview R shows the screen again, so Refresh is tried in the real menu.

## 31. The main menu draws without voms-proxy-info and without re-reading ended operations

**Date:** 2026-10-21
**Status:** done
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#31-the-main-menu-draws-without-voms-proxy-info-and-without-re-reading-ended-operations)

TODO §6 "Menu as a program", menu speed (user, 2026-10-21: approach A and B). Before: every main-menu draw (each
return from a screen) ran `voms-proxy-info --exists --valid 0:01` (up to 5 s) and read the operation records from
AFS: `operation.json` of every record (`latest` loaded all of a kind), `exit.json`/`seen`/`stop` of each, and the
whole `events.jsonl` of every operation with a line (thousands of lines after "All tests"). Counted for 5 test and
5 run records with one advance running: one process and about 25-30 file reads per draw. After: no process, and
only the files of the running advance (`exit.json`, `stop`, the heartbeat at most once a second, the new event
lines).

- **Grid proxy** (`_Operations.grid_proxy_valid(fresh=False)`): `voms-proxy-info --timeleft` (the last token of
  its output: seconds); valid with more than `PROXY_MARGIN` (60 s, as `--valid 0:01` before). The answer is kept
  until the proxy expires (the clock, no process) or the proxy file changes (`$X509_USER_PROXY`, else
  `/tmp/x509up_u<uid>`: mtime and size; renewed or destroyed in another terminal); an invalid answer is kept until
  the file changes. `fresh=True` asks again: `_grid_ready` before a run that may submit jobs (never a kept answer)
  and after `renew_grid_proxy`. The main menu calls it as before.
- **Operation records** (`OperationStore`): `operation.json` is read once per directory (it never changes); the
  next `Operation` of a directory gets what the last one knew that never changes again (`_carry`: the end from
  `exit.json`, the `seen` mark once true, the supervisor this menu started), so an ended and seen operation reads
  no file. `all()` still lists the directory (new and pruned records) and returns new `Operation`s, their readers
  at the top of the files (a screen shows the whole log). `Operation.seen` is kept once true; `mark_seen` sets it.
- **Menu lines** (`summary_model` in `_operation_screen.py`; `test_summary`/`run_summary(operation, kept=None)`):
  `ConsoleUI` keeps per operation directory the line's model and its own `EventReader`, so a draw reads only the
  events added since the last one, and none once the operation ended (then it reads past `READ_LIMIT` once).
  Without `kept` the summaries read from the top as before.
- Not changed: the run list of Continue/Inspect (`runs()` reads every `run.json`), the `run.json` of a lost
  advance in the main menu (`_finished`, rare). Step (4), one curses session, comes next.

## 32. One curses session for the menu, panels over the screen, the grid password in the menu

**Date:** 2026-10-21
**Status:** done
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#32-one-curses-session-for-the-menu-panels-over-the-screen-the-grid-password-in-the-menu)

TODO §6 "Menu as a program", step (4); decisions of the user, 2026-10-21: the grid certificate password in a field
of the menu (option b; the plain terminal only as a fallback), a "Kill now" key while an operation stops, and a
live main menu every 2 s while something runs behind it. Before: every screen opened its own `curses.wrapper`, so
the shell showed between two screens; errors were printed (`operation_error`) and waited for "Press Enter"
(`pause`, `unreadable_run`); the quit warning was a screen of its own; the stop question was the footer;
`voms-proxy-init` asked for the password on the terminal; the main menu showed the states as they were when it was
drawn.

- **One session** (`ConsoleUI.session(function)`, `ConsoleUI._run(draw)`): `run_menu` runs the menu in one
  `curses.wrapper`; every screen draws on its screen (`self.screen`). Outside a session (FastSetup's checklist, the
  unit tests) a screen opens its own as before. `_setup` sets `timeout(-1)`: a screen after a live one waits for a
  key. `in_terminal(function)` leaves the screen for a program that asks on the terminal (`def_prog_mode`,
  `endwin`, then "Press Enter" and `reset_prog_mode`).
- **Panels** (`_modal(title, lines, footer, answer)` waits for a key, `_overlay` only draws): a frame in the middle
  of the current screen (at most `MODAL_WIDTH` 76 columns), the rows it covers cleared, a long text scrolls
  (Up/Down/PgUp/PgDn, "Lines a-b/n"). `message(title, lines)` (Enter OK), `operation_error(error)` ("Error",
  "RuntimeError: Tests are already running ..."), `unreadable_run`, `notice` (draws, waits for nothing). The quit
  warning ("Still running: quit TauFW?", C/S/Q) is a panel over the main menu. `pause()` is removed; the
  navigation no longer calls it after an error.
- **Operation screen:** the stop question ("Stop the tests?", Y/N) is a panel over the live screen (it keeps
  drawing). While an operation stops (STOPPING, not a read-only command) the footer offers "K Kill now"; K asks in a
  panel (`ScreenModel.kill_warning`; the run: "taufw.py ends at once: a job submission in progress may be left half
  done. Check condor_q, then Continue the run."; the tests: "Tests/run.py and the case it runs end at once."), Y
  calls `Operation.kill()` (the `kill` file: the supervisor kills the group). A question that ended meanwhile goes
  away.
- **Grid certificate** (`MenuNavigation.grid_certificate`): `ui.grid_password()` (a panel, the password shown as
  `*`, Esc or an empty Enter cancels), `ui.notice("Renewing the grid proxy ...")`,
  `_Operations.renew_grid_proxy(password)` runs `voms-proxy-init -voms cms -pwstdin` with the password on its stdin
  (never in argv, a file or a log; `PROXY_INIT_TIMEOUT` 120 s) and returns (valid, output); valid is None when its
  output names `-pwstdin` after a failure: then `ui.in_terminal(renew_grid_proxy_in_terminal)` (the old
  terminal prompt). `ui.grid_result(valid, output)`: "Grid proxy active." or "Proxy Failed! ..." with the last
  lines of the output.
- **Live main menu:** `MenuNavigation.run` passes `live` (the last test run or an advance runs);
  `main_menu(live=True)` waits `LIVE_EVERY` (2 s) for a key, then answers "refresh" and is drawn again with the new
  states (CL §31 keeps a draw cheap); the selected line stays (by its action). `choose` got `position` and `live`.
- **Help:** the "Tests" topic no longer says "Press Enter after output to return" (a test run goes on behind the
  menu; S/Ctrl+C asks, K kills while it stops); "Grid Certificate" describes the password panel.
- **UI preview:** "Panel: an error over the screen", "Grid Certificate: password (typed as *)", "Grid Certificate:
  renewal failed"; the quit scenarios show the new panel.

## 33. Start a new run and Esc answer at once

**Date:** 2026-10-22
**Status:** done
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#33-start-a-new-run-and-esc-answer-at-once)

Found by the user after CL §32: "Start a new run" took long to open, and Esc was slow on every screen.

- **Start:** the recipe list checks every recipe (`check_recipe`), and each check's `recipe_warnings` called
  `configs.copy_warnings`, which scanned the whole `Configs/` directory again: every template read, parsed and
  hashed. With the 4 recipes of `Analyses/`: 7 scans, 133 template reads, 93 % of the time (Windows, local disk:
  0.57 s; AFS is much slower). Now `configs._templates` keeps the scan while no file of the directory changed (its
  path, mtime and size: one stat per file); with a FileIO of the caller it scans as before. Windows: 0.18 s for the
  first list (one scan), 0.08 s after. The CLI's output is unchanged.
- **Esc:** curses waits `ESCDELAY` ms (default 1000) after Esc for the rest of a key sequence (an arrow key is
  Esc + `[A`). `ConsoleUI.open` sets `ESCDELAY` to `ESC_DELAY` (25 ms) unless the user set it, and `_setup` calls
  `curses.set_escdelay` (Python 3.9+). The menu and FastSetup's checklist both open through `ConsoleUI.open`.

## 34. Start and Continue/Inspect read their lists ahead, and open at once

**Date:** 2026-10-22
**Status:** done
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#34-start-and-continueinspect-read-their-lists-ahead-and-open-at-once)

After CL §33 the first Start of a menu still read every recipe's check before the list opened, and Continue/Inspect
read every `run.json`. Decisions of the user, 2026-10-22: A + C (a thread reads the lists ahead from the menu's
start, and a list opens at once with the rows that are still read marked), Continue/Inspect included. Not done
(proposed, not chosen): a separate process (B), a cache on disk across menu sessions (D).

- **Read ahead** (`Menu/_prefetch.py` `Prefetch`): jobs run one at a time by a daemon thread (quitting never waits;
  it works while the menu waits for a key: curses releases the GIL in `getch`), a key is queued once until its job
  ended, an error is dropped (the screen asks again and shows it). `threaded=False` (the default of
  `MenuNavigation`, the unit tests) runs a job at once in the caller. `run_menu` passes a threaded one
  (`Menu(ui, prefetch=Prefetch())`). `MenuNavigation.run` queues every recipe's check, then every run's row.
- **Kept with the signature of their files** (`_Operations`): `recipe_preview(path)` keeps its view (also the view of
  a recipe that cannot be checked: its error, before in the navigation) with the signature (path, inode, mtime,
  size) of the recipe file or every file of its bundle and of `Configs/`; `kept_recipe_preview(path)` gives it
  while the signature is the same, else None. `run_row(run_dir)` / `kept_run_row(run_dir)` the same for a run's
  row with its `run.json` (replaced on every save: another inode). `run_roots()` keeps each recipe's `run_root` by
  the recipe file; `run_directories()` names the runs, `runs()` gives the rows (kept or read). Nothing is ever
  stale: a list asks the kept value, which a changed file drops.
- **Lists** (`MenuNavigation.start`, `_pick_run`): a row without a kept value asks for its job and shows
  "checking..." (a recipe: Pipeline "Checking the recipe...") or "loading..." (a run, after the read ones, its
  directory name); while one is missing the list waits `LIST_EVERY` (0.5 s) for a key, then draws again
  (`select_recipe(checking=, position=, live=)`, `select_run(loading=, position=, live=)`, `_pipeline_choice(live=)`
  answer "refresh"). The focus stays: on the recipe by its position, on the run by its directory (the rows move as
  they come). Enter on a recipe still checked opens its review at once (`prepare_review` reads it anyway), Enter on
  a run still loading loads it (`load_run`).
- Windows, the 4 recipes of `Analyses/`: the read-ahead 0.19 s after the menu opened; then the recipe list's data
  0.004 s (the stats of the signatures).
- **UI preview:** "Start a run: recipes still checked", "Continue: runs still loading".

## 35. The pico tuple contract (PicoProducer -> Histogrammer)

**Date:** 2026-10-26
**Status:** done
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#35-the-pico-tuple-contract-picoproducer---histogrammer)

**Details:** `LocalR/architecture/22-data-contracts-plan.md` (C2, decisions K5; 2026-10-26: a first version now,
extended later), [pico-tuples contract](../contracts/pico-tuples.md),
[2025 weight branches](../issues/2025-tuple-weight-branches.md)

The last stage boundary without a written contract: the Histogrammer read `sumw` from cutflow bin 17, the DY
stitching from bins 17-23, and the configs named branches, all by convention; a changed cut index or a misspelt
branch showed up as a wrong normalisation or an error hours into a run. The 2025 weight branches looked like
an unexplained external dependency; the group's answer (2026-10-26): 2024 MC for the 2025/2026 data, pileup and
muon SF branches added afterwards by two scripts in `Legacy/OldAnalysis` (analysis specific).

- **Contract page** `Docs/Develop/contracts/pico-tuples.md`: file name and layout, tree `tree`, cutflow `cutflow` and its
  bins (1 nevents, 16, 17 sumw, 18-23 DY stitching) with their readers, the rule that a skim or any post-processing
  must carry the cutflow over unchanged, the channel -> tree producer table, which config fields name branches,
  variation tuples (`dotight`, `dosys`), the 2025 analysis add-on (branch, script, files, inputs) and the known debt.
- **Test** `Tests/contracts/test_pico_tuples.py` (no ROOT, both sides read as text, nothing imported; new check suite
  `unit.contracts` in `Tests/run.py`): names and file name on both sides; the `addcut` indices of every channel module
  against the bins `Sample` and the stitching read and against the cuts `ModuleTauPair.fillhists` fills; the
  channel modules' tree producer; every branch of the setups, the TES/ID configs and the sample models (`Configs/`
  and the bundle copies) written by the channel's tree producer, or in the add-on (eras 2025, 2026, 2526; muon SFs
  for mutau/mumu), or in `KNOWN_DEBT`; the add-on list against the branch names in the two scripts. The debt lists
  must match exactly, so a fix fails the test until its row is removed.
- **Found by the test, left as known debt** (no behaviour change; TODO §0): `weights.other` of every era and the
  campaign eras' etau/ee/emu weights read the muon SF add-on (also before 2025, where no tuple has them);
  `setup_tautau.yml` reads `idMedium_1/_2`; `setup_etau_inclusive.yml` reads PNet branches `TreeProducerETau` does not
  write; `ModuleETau`, `ModuleTauTau`, `ModuleEMu` declare no bins 18-23 but are filled them for DY files.
- **Preflight on the files** (`Histogrammer/python/sample/branches.py`, `ControlHists.branch_problems`,
  `TESShapes.branch_problems`, both in their preflight; constructor option `read_branches`): with a tuple pattern,
  sample files and ROOT, every existing nominal tuple file's branch list (header only) against what the setup and the
  sample model read (MC: cuts, split cuts, weight and extra weight, without `removeSFs` and the SFs of `-r`; data:
  cuts). A missing branch stops `plan`/`start` instead of failing hours into a run. Without ROOT (Windows) nothing is
  checked; a file that cannot be read is left to the other checks.
- **Write-up** moved to `Docs/Develop/issues/2025-tuple-weight-branches.md` (the TODO link pointed there) and rewritten with
  the answer; five points stay open (`_v3`, the MC pileup profile, which files, electron channels, older eras).
- `Legacy/OldAnalysis/2025-2026/add_pileup_weights.py`: banner and inventory row say 2024 MC (was "2025 MC").
- Not covered yet: the variables defined in Python (`fillhists.py`, plotting scripts), weights given on the command
  line, the branches of the variation tuples.

## 36. The production record: kind and sum of weights on the tuple artifacts

**Date:** 2026-10-26
**Status:** done
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#36-the-production-record-kind-and-sum-of-weights-on-the-tuple-artifacts)

**Details:** `LocalR/architecture/22-data-contracts-plan.md` (C3, decision K4; user decisions 2026-10-26 below),
[pico tuple contract, "Production record"](../contracts/pico-tuples.md#production-record), Framework BUGS K04

A production stage records each merged tuple as a `TupleArtifact` in `run.json` and its `manifest.json`. Two things
were missing. The record had no `kind`, unlike the artifacts of every other stage (`control_histograms`, `shapes`,
`fit`), so a filter by kind found nothing: `ctx.input('tuples', kind='tuples')` in a python step returned an empty
list (BUGS K04). And the normalisation of a tuple (cutflow bin 17) was only in the file, not in the record of what
the run produced.

Before / after (one record of `run.json`):

```
before: {"path": ".../DY/DYto2Tau_..._mutau.root", "sample": ..., "nevents": 1234567.0, "tree": "tree",
         "cutflow": "cutflow", "pattern": ".../stages/production/$ERA/$GROUP"}
after:  {"path": ..., "nevents": 1234567.0, "sumw": 9.87e11, "tree": "tree", "cutflow": "cutflow",
         "kind": "tuples", "pattern": ...}
```

Decisions of the user (2026-10-26):
1. `sumw` is read from the merged file right after `hadd` (not summed over the job outputs): the file the readers
   use, already opened by the merge's validation.
2. The readers select by kind: only records of kind `tuples`; a record without a kind (a production run before this
   section, named with `inputs.tuples: {path: ...}`) is refused with a message, as the runs before CL §16 are.
3. Data tuples get the raw bin 17 too (events with a primary vertex; documented as not a normalisation).
4. The merge records `sumw` only; it does not refuse a merged MC tuple with `sumw <= 0`.

- **PicoProducer** (`storage/validation.py` `cutflow_bin(fname, bin)`; `jobs/merge.py` `SUMW_BIN = 17`,
  `MergeResult.sumw`, read after `hadd` unless dry run, also when the validation fails; `api/types.py`
  `TupleArtifact.sumw` (None: not read) and `kind = "tuples"`; `api/producer.py` passes it on). What `pico.py` prints
  and does is unchanged; the tuple files are unchanged.
- **Framework** (`stages/production.py`: the planned record is `{kind: tuples, pattern}`; `stages/local.py`:
  `LocalStage.tuple_artifacts(context, slot)` = the input's artifacts of the slot's kind, used by `tuples_pattern`,
  `input_problems` and `last_status.inputs`; records without a kind are a problem).
- **Docs**: the contract's "Production record" section (every field, the readers, the refusal); PicoProducer
  `API.md`, `IO.md`; `Framework/README.md`; BUGS K04 fixed.
- **BBB** `framework.production` records `run.json` after the merge: its two tuple records gain `"sumw"` and
  `"kind": "tuples"`; nothing else should change (the tuple files, the plan and status output, the other cases).
  Re-lock of this case only, to be approved by the user after `bbb check` on lxplus shows exactly this difference.

## 37. Inputs are given, never found

**Date:** 2026-10-26
**Status:** done
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#37-inputs-are-given-never-found)

**Details:** `LocalR/architecture/archive/23-given-inputs-plan.md` (ModuleIsolationFinalizations §3 D; decisions of the
user 2026-10-26: K1-K5, K7 as proposed, K6 postponed, K8 the path rule of D4)

The Histogrammer still finds its tuples itself when it is not given them: `getsampleset` reads `picodir` of the
PicoProducer configuration (A03), and the APIs set `$TAUFW_PICO_CONFIG` for it. The steps of this section remove
that from the library, the APIs and the recipes; the scripts keep the old default (opt-in rule) until the
migration point.

- **D0, the old default locked first.** No BBB case ran a script without `--tuples`. New case
  `histogrammer.tes_inputs_picodir` (`Tests/BBB/cases.py`): the fixture of `histogrammer.tes_inputs`, run through
  `createinputsTES.py` without `--tuples`, the tuples found through a PicoProducer configuration in
  `$TAUFW_PICO_CONFIG` whose only key is `picodir` (the same pattern). Both cases share `_tes_inputs_run`; the
  existing case is unchanged except that the script no longer inherits a `$TAUFW_PICO_CONFIG` of the caller (with
  `--tuples` it was never read). Locked on lxplus with the code before D1, so D1 must pass it without a re-lock.
- **D1, the Histogrammer library takes the tuples.** `TauFW.Histogrammer.sample.utils.getsampleset` no longer imports
  PicoProducer: a file pattern with `$PICODIR` and no `tuples=` is a `ValueError` ("no tuple pattern ... give
  tuples=..."). The scripts keep their old default through a new LEGACY helper,
  `TauFW.Histogrammer.sample.tupledir.script_default_tuples()`: `picodir` of `$TAUFW_PICO_CONFIG`, else
  `PicoProducer/config/config.json`, read as JSON (no PicoProducer import; decisions K1, K2). Called, only when no
  `--tuples` is given, by `fillhists.py`, `shapes/TauES/createinputsTES.py`, and (which have no `--tuples`)
  `plot_postfit.py`, `plot_postfit_shift.py`, `plot_v10.py`, `shapes/{ETauFR,HighPT,paper,tutorial}/createinputs.py`,
  `tutorial/plot.py`. Behaviour of the scripts is unchanged except when there is no configuration file or no
  `picodir` in it: before, `getconfig` used its built-in default directory (usually without tuples, so every sample
  "Did not find ..."); now one error naming `--tuples`. The backup `config.json.bkp` is not read.
  Before / after, a command typed by hand: `python3 fillhists.py -c mutau -y 2025` reads the same files; a user's own
  `getsampleset(..., fname="$PICODIR/...")` without `tuples=` now raises.
  Not changed (K6, done in CL §39): `getmcsample` keeps its `getconfig` call, so Histogrammer -> PicoProducer is 1 / 1 / 1 (was
  2 / 1 / 1; totals 20 / 19 / 17), its allowlist reason says so. Not adapted, already not runnable: `Fitter/Zpt`
  (its `config/samples.py` is Python 2), `Fitter/MuTauFR/createinputs.py` (broken import); the integration demos
  `Tests/Plotter/plotPico.py`, `WstarplotPico.py` (byte-locked relocated copies, `Tests/migration.json`) now need
  a `tuples=` and raise without it.
  The APIs still set `$TAUFW_PICO_CONFIG` for a request without tuples (D2 removes it); the helper reads it, so that
  path keeps working until then.
- **D2, the APIs take the tuples, never a PicoProducer configuration.** `HistsRequest` and `ShapesRequest`
  (Histogrammer): `pico_config` removed (an unknown field, so `TypeError`), `tuples` required (`ValueError`
  "tuples is required ..."); every command gets `--tuples`, none gets `$TAUFW_PICO_CONFIG`; the preflight no
  longer looks for a PicoProducer configuration ("no PicoProducer configuration ..." is gone).
  `ControlHists.pico_config_source`, `TESShapes.pico_config_source` and `_pico_env` removed. `FitRequest.pico_config`,
  `TauESID.pico_config_source` and its `_pico_env` removed: the fit scripts never read it (finalizations B4, TODO §0
  item 4). `TauFW.Utilities.Process.output_dir_problems(outdir, tuples=None)`: the `pico_config` parameter and the
  relative-`picodir` check are gone. Framework: `controlhists`, `shapes`, `fit` no longer pass `pico_config`;
  `LocalStage.tuples_pattern` gives the placeholder `<id>/$ERA/$GROUP` for a production input that has no
  (planned) record yet, as in the sample comparison of a plan (`samples.py`), where the request used to be made with
  `tuples=None`; the APIs do not check a `<...>` pattern. A tuples input `null` now gives a request without tuples,
  which the API refuses (D3 makes it a recipe error with its own message).
  Before / after (`taufw.py plan`, a fit command): `TAUFW_PICO_CONFIG=/run/bundle/pico.json python3
  harvestDatacards_zmm.py ...` -> `python3 harvestDatacards_zmm.py ...`; a controlhists command with tuples is
  unchanged.
- **D3, the recipe gives every input.** No slot may be `null` (`null_inputs = {}` for `controlhists`, `shapes`,
  `fit`); the issue says what `null` meant and what to write (`recipe.RETIRED_NULL`, `_null_message`):
  `stages[1] (controlhists).inputs.tuples: null (the tuples in $PICODIR of the PicoProducer configuration) is no
  longer read, inputs are given (CL §37): name a production stage, {external: /eos/.../$ERA/$GROUP} or {path:
  <run_dir>/stages/<id>}`; the fit's `shapes: null` (the shapes in `Fitter/input_pt_less_region/`, the "temporary
  exception" of CL §17) the same, naming a shapes stage or `{path: ...}`. A run whose saved recipe has a null input
  is refused with the same message when it is continued. `pico.config` other than null in a recipe without a
  production stage is an error (decision K5); `taufw.py plan` prints the "PicoProducer config:" line only for a
  recipe with a production stage. Python steps: no `$TAUFW_PICO_CONFIG` in their command, `ctx.pico_config` stays
  (K4). New warning (TODO §6): a production stage with a `tag` whose tuples another stage reads (the readers look
  for `<sample>_<channel>.root`). No shipped recipe changes: the four of `Analyses/` name every input and have
  `pico.config: null` (`example_broken` keeps its four intended errors). BBB `framework.production` has a production
  stage without a tag: its `plan` output is unchanged.
  Before / after (`taufw.py check` of an old recipe): `inputs: {tuples: null}` was valid (the scripts got
  `$TAUFW_PICO_CONFIG`) -> the error above; `pico: {config: pico.json}` with only a fit stage was valid -> "pico.config:
  only a production stage reads the PicoProducer configuration, and this recipe has none: ...".

## 38. One rule for the paths in a recipe

**Date:** 2026-10-27
**Status:** done
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#38-one-rule-for-the-paths-in-a-recipe)

**Details:** `LocalR/architecture/archive/23-given-inputs-plan.md` §4 (step D4 of "inputs are given, never found",
ModuleIsolationFinalizations §3 D). Decisions of the user (2026-10-26/27): 8a no module fallback for files; 8b `../`
allowed, the user's responsibility; 8c option A, nothing expanded in a recipe; 8d one test for "absolute"; the two
Fitter default configs stay where they are (documented, removable at the migration point); the Fitter API's
`config_file` removed.

Until now a relative path option that was not a bundle file was handed to the module unchanged, which read it
relative to its own directory (`Fitter/`, `Histogrammer/`): a recipe could read a module file without naming where it
was. `run_root` had `~` and `$VARIABLES` expanded where `taufw.py` ran (with a warning); `{path: ...}` and
`{external: ...}` expanded nothing; `pico.config: ../x` alone was made absolute; and the absolute test was
`os.path.isabs` in some places and posixpath-or-os.path in others (Framework BUGS K05).

- **One rule for every file key** (`configs`, `samples`, `config`, `config_mumu`, `file`, `pico.config`;
  `bundle.where`): absolute -> as written; relative -> the recipe's directory + path: a bundle file (copied into the
  run with the bundle), or above it (`../x`: `outside`, made absolute by `Recipe.load()` and by `check_recipe`, so a
  run, which reads its recipe against its own bundle copy, reads the file where it is; not copied); `Configs/...` not
  in the bundle -> the template; for an option in the Spec's `_channel_paths` (only `controlhists.configs`) a name
  without `/` and `.yml` -> the channel's setup (`channel`). Anything else is `missing`, a recipe error (load, check,
  plan, start, continue): `stages[2] (fit).config: TauES/config/defaultFitSetupTES_mutau.yml is not a file of the
  bundle (<dir>), a Configs/ template or an absolute path: copy it into the bundle, or give its absolute path (no
  module directory is searched, CL §38)`. The old module paths of configs that became templates keep their message
  naming the template (`MOVED_CONFIGS`). One check, `recipe._check_paths`, replaces `_check_moved_configs`,
  `_check_module_paths` and the shapes-only `ShapesSpec._no_module_paths`; `validation._file_issues` no longer
  reports a module path of a python step or a `samples` file itself (the recipe error does).
- **Data locations** (`run_root`, `{external: ...}`, `{path: ...}`): absolute, nothing expanded. `run_root: ~/runs`
  or `$HOME/runs` is a problem: "nothing is expanded in a recipe (another user or machine would get another
  directory, CL §38): write the absolute directory, or give --run-root on the command line (the shell expands it
  there)". `recipe.run_root_dir`, `Recipe.run_root_dir` and the "is expanded where taufw.py runs" warning are gone;
  `plan` prints `<run_root> (recipe)`.
- **One absolute test** `bundle.is_absolute` (posixpath or os.path) in `bundle.where`, `recipe.py`
  (`_pico_config_path`, `_path_problem`, `_external_problem`, `_check_run_root`) and `validation.py` (K05 fixed).
- **`taufw.py init --from`** copies the templates and channel setups a recipe names (`where == 'channel'` asks the
  controlhists stage for the setup file); the `config_file` wrappers of the shapes and fit stages are gone, and so is
  `TauESID.config_file` of the Fitter API (only `init` called it; the API still reads relative configs against
  `Fitter/` itself, `_path`). The Histogrammer APIs' `config_file` stays (their commands use it).
- **The two Fitter defaults** `Fitter/TauES/config/defaultFitSetupTES_mutau.yml` and `defaultFitSetup_mumu.yml` stay
  where they are: they are the `-c` defaults of the old standalone TauES scripts (`makeTESfit.py`,
  `plotParabola_TES.py`, `checkShapes_TES.py`, `harvestDatacards_*`), not templates. A recipe no longer reads them by
  their module path; the fit stage's own defaults are the templates `Configs/Fitter/tes_id/config_coarse_TT.yml` and
  `FitSetup_mumu.yml` (the same content as `defaultFitSetup_mumu.yml` plus the `taufw_config` header). They may go
  with the old scripts at the migration point (TODO §8).
- Scripts, module APIs and BBB are not touched: a command typed by hand with `-c TauES/config/...` is unchanged.
  The four `Analyses/` recipes use no module path and no `~`/`$` (only their comments said that `run_root` is
  expanded); `example_broken`'s fourth error now comes from the recipe check with the new wording.
  Before / after (`taufw.py check`):

  ```
  fit: {config: TauES/config/defaultFitSetupTES_mutau.yml}   Fitter/TauES/config/... read  ->  the error above
  shapes: {configs: [../shared/tt.yml, ...]}                 handed to the module as ../shared/tt.yml (wrong
                                                             place)  ->  <recipe dir>/../shared/tt.yml, absolute
  pico: {config: ../pico.json}                               made absolute  ->  the same, by the general rule
  run_root: ~/work/taufw_runs                                expanded + warning  ->  error, use --run-root
  run_root: /afs/cern.ch/work/u/user/runs                    unchanged
  controlhists: {configs: [mutau]}                           unchanged (plan shows `channel`, was `module`)
  ```

## 39. `getmcsample` takes the tuples instead of reading the PicoProducer configuration

**Date:** 2026-10-27
**Status:** done
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#39-getmcsample-takes-the-tuples-instead-of-reading-the-picoproducer-configuration)

**Details:** decision K6 of `LocalR/architecture/archive/23-given-inputs-plan.md` (user, 2026-10-27), revised the
same day after feedback of the group; the last step of "inputs are given, never found" (ModuleIsolationFinalizations
§3 D).

`getmcsample(group, sample, title, xsec, channel, era, tag)` of `TauFW.Histogrammer.sample.utils` (old name
`TauFW.Plotter.sample.utils`) built one MC sample from `$PICODIR/$SAMPLE_$CHANNEL$TAG.root` and filled `$PICODIR`
from `picodir` of the PicoProducer configuration (`getconfig`, A03): the last Histogrammer -> PicoProducer import.
Its `pico=` keyword was read and cleared on the next line (Histogrammer BUGS L12). In the repository only two
archived scripts call it: `Legacy/OldAnalysis/2016-2018/plot_compare.py` (2 calls) and
`Legacy/OldAnalysis/2018/plot_stitching.py` (5 calls, 4 more commented out); no maintained code, test, BBB case or
recipe. It stays in the library anyway: it is a helper for users' own quick MC studies (a set of `Sample` objects,
`gethist`, a `Plot`, all in one script, outside the repository). Only its `getconfig` call breaks a boundary, and it
is fixed the way CL §37 fixed `getsampleset`.

- `getmcsample(group, sample, title, xsec, channel, era, tag="", verb=0, **kwargs)` takes a new keyword `tuples=`:
  the directory pattern put in for `$PICODIR` (as in `getsampleset`, it may contain `$ERA`, `$GROUP`, ...). A
  pattern with `$PICODIR` and no `tuples=` raises `ValueError` naming `tuples=`; the PicoProducer configuration is
  never read. A full `fname=` pattern without `$PICODIR` needs no `tuples=`. The rest (`fname`, `user`/`$USER`,
  `tag`, the "Did not find" print, `verb`) is unchanged. The `pico=` keyword (always ignored, L12) is gone.
- The two Legacy scripts get their own copy of the old function below their imports (the same code, `repkey`
  imported inside it, a docstring saying where it came from) and no longer import it from the library. The copies
  keep reading `picodir` of the PicoProducer configuration, so the scripts behave as before; the two lines of L12
  (`picodir = kwargs.get('pico', "")`, `picodir = ""`) are dropped, which changes nothing since `picodir` was always
  `""` there. When `Legacy/OldAnalysis/` is deleted, the copies go with it. The import-boundary check skips
  `Legacy/`.
- Histogrammer -> PicoProducer: 1 / 1 / 1 -> none; totals 20 / 19 / 17 -> 19 / 18 / 16. Its allowlist entry is
  removed (a stale entry would fail the test). L12 is closed.
- New test `Tests/Plotter/testScriptFlow.py` (`plotter.script_flow`, ROOT): `MC` -> `gethist` -> `Plot` -> `draw`
  -> `saveas` in one script, so the one-script study stays supported. The module boundaries are between the
  stages' packages, not inside a user's script: it may use the Histogrammer's samples and the drawing library
  (`TauFW.Utilities.Drawing`) together.
- Before / after:

  ```python
  # before: $PICODIR came from the PicoProducer configuration
  getmcsample('DY', "DYJetsToLL_M-50", "DYJetsToLL", 1., channel, era)
  # after
  getmcsample('DY', "DYJetsToLL_M-50", "DYJetsToLL", 1., channel, era, tuples="/eos/.../$ERA/$GROUP")
  getmcsample('DY', "DYJetsToLL_M-50", "DYJetsToLL", 1., channel, era)   # ValueError: give tuples=...
  ```

  `python3 plot_stitching.py` (Legacy, with its old Run 2 tuples) reads the same files.


## 40. The user config: infrastructure (`Analyses/UserConfig.yaml`, `TauFW.Utilities.UserConfig`)

**Date:** 2026-10-27
**Status:** done (infrastructure only: which settings the file holds is not decided yet)
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#40-the-user-config-infrastructure-analysesuserconfigyaml-taufwutilitiesuserconfig)

**Details:** group discussion of 2026-10-27 (Izaak Neutelings, Hagop Awedikian): one personal configuration instead of
`PicoProducer/config/config.json`, whose personal changes kept being committed and overwritten. User decisions: the
file is `Analyses/UserConfig.yaml` (YAML, for comments), made by the setup and ignored by git; a file not reviewed
yet gets a one-line warning, nothing more; scripts keep `config.json` (compat), recipes and stages take the user
config once it holds settings; its code lives in `Utilities/python/UserConfig/`.

- **`TauFW.Utilities.UserConfig`** (new package, standard library only; reading needs PyYAML), in two parts (user,
  2026-10-27: what scripts use apart from what the tools use):
  - **Reading, for everyone** (`UserConfig`, `_config.py`): `location()` (`$TAUFW_USER_CONFIG` if set, else
    `Analyses/UserConfig.yaml` of the checkout), `load(path)` -> `Config` (`get("runs.run_root", default)`,
    `require(key)`, `section(name)`, `values`, `exists`, `reviewed`, `version`; a missing file is an empty `Config`,
    a broken one a `UserConfigError` naming the file). TauFW's own readers of a setting use the same `load()` as a
    user's script, so both see the same value.
  - **Managing the file** (`UserConfig.manage`, `manage.py`), for FastSetup, taufw.py and the menu: `create(path)`
    (writes the new file, never over an existing one), `check()` (the one-line warnings: no file, not reviewed, a
    broken file; never raises) and the constants (`FILE_NAME`, `ENVVAR`, `DEFAULT_PATH`, `CREATE_COMMAND`). Not
    named after the Framework: FastSetup uses it too, and Utilities does not know the Framework.

  The new file has only its header:

  ```yaml
  taufw_user:
    version: 1           # the format of this file (set by TauFW, do not change)
    reviewed: false      # true: you checked this file
  ```

  A setting is added in `_template.py` (its docstring says how). The same package is importable before `cmsenv` as
  a top-level package (`import UserConfig` with `Utilities/python` on `sys.path`), as FastSetup does.
- **Made by the setup:** `FastSetup.sh` runs `create_user_config` after `verify_install` (in the installed checkout,
  after the move): `setup_tools.py userconfig --path ${TAUFW_USER_CONFIG:-$repo_dir/Analyses/UserConfig.yaml}`
  prints `Created ...` or `Kept ...`; a failure is a setup warning, not an error. The summary gets a line
  `User config  <path> (review it)`. For checkouts installed before: `python3 taufw.py userconfig` (new command:
  makes the file if there is none, prints its path and its warnings).
- **taufw.py:** `check`, `plan` and `start` show `manage.check()` as warnings, one line each, e.g.
  `User config /afs/.../Analyses/UserConfig.yaml is not reviewed yet: check its values, then set reviewed: true`.
  The recipe still runs; the exit code does not change.
- **Not a recipe:** the menu listed every loose `.yml`/`.yaml`/`.json` file of `Analyses/` as a recipe, so the user
  config would have been a red, broken entry; `interactive._Operations.recipes()` skips `UserConfig.yaml`.
- **Not a template:** the file is not in `Configs/` (`configs.py` checks every YAML there for a `taufw_config`
  header). `.gitignore`: `Analyses/UserConfig.yaml` (`*.json` is ignored anyway, a YAML file is not).
- **Tests stay independent of the checkout's file:** the BBB workspace (`Tests/BBB/pico_harness.py`) and the
  `taufw.py` tests (`checkout.reviewed_user_config`) point `$TAUFW_USER_CONFIG` at a reviewed file of their
  temporary directory, so the output of `taufw.py plan` (BBB `framework.production`) does not change: no re-lock.
- Nothing reads a setting yet; PicoProducer, Histogrammer, Fitter and the scripts are unchanged.

## 41. The user config's settings: run_root and the production settings

**Date:** 2026-10-27
**Status:** done
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#41-the-user-configs-settings-run_root-and-the-production-settings)

**Details:** proposal to the group (2026-10-27) and user decisions the same day: the recipe wins over the user
config; a new file takes over the values of an existing `PicoProducer/config/config.json`; a change of the user
config between `start` and `advance` is a TODO; the job output of the lxplus guesses goes to a `taufw/` directory
of the EOS area. Found while checking the PicoProducer API: a recipe's production never read `queue`, `batchopts`
and `ncores` of the PicoProducer configuration (only `pico.py` takes them, as argparse defaults), so the user config
gives them as request defaults, not as configuration keys. `storage.base` (first proposal) and `picodir` are not
settings: the first would not move the directories made from it, the second is not read by recipes.

- **Settings** (`Utilities/python/UserConfig/_template.py`, `SETTINGS`): `runs.run_root`; `production.batch`,
  `queue`, `batchopts`, `outdir`, `nanodir`, `tmpskimdir`, `ncores`, `hadd.cmd`, `hadd.maxopenfiles`. Each has a
  kind, checked by `manage.setting_problems(config, section)`: `run_root` absolute with nothing expanded (the
  recipe's rule), the directories non-empty text, `ncores` and `maxopenfiles` whole numbers from 1. Other keys and
  sections stay the user's.
- **A new file** (`manage.create()`, `_guesses.py`): on lxplus `batch: HTCondor`,
  `outdir: /eos/user/<u>/<user>/taufw/output/$ERA/$CHANNEL/$SAMPLE`,
  `nanodir: /eos/user/<u>/<user>/taufw/samples/nano/$ERA/$DAS`, and `run_root: /afs/cern.ch/work/<u>/<user>/taufw_runs`
  if that work area exists. The non-empty values of an existing `PicoProducer/config/config.json` win over the
  guesses (read as JSON: Utilities never imports PicoProducer). Every other setting is a comment line with an
  example; a comment line at the top says where the values came from. Elsewhere nothing is guessed.
- **Precedence** (`Framework/python/user_settings.py`, the Framework's only reader; it uses `UserConfig.load()`):
  - `run_root`: `--run-root` > recipe > `runs.run_root` > `taufw_runs/`. `Framework.start` takes it; the
    recipe's "run_root: not set" warning is not given when the user config has one; `plan`/`start` print
    `Run root: <dir> (user config)`; the menu also lists the runs of that directory.
  - `batch`, `outdir`, `nanodir`, `tmpskimdir`, `hadd.cmd` (-> `haddcmd`), `hadd.maxopenfiles`
    (-> `maxopenfiles`): replace those keys of the PicoProducer configuration (`config.json` or `pico.config`), in
    memory, through the new `PicoProducer.from_config(..., overrides=)`.
  - `queue`, `batchopts`, `ncores`: request defaults of the production stage (`ProductionStage(pico, settings)`),
    used when the recipe leaves the option unset. `ProductionSpec.ncores` defaults to `None` (was 4); with neither,
    `DEFAULT_NCORES` (4), as before. `ProductionStage.request_fields(spec)` gives these fields, and the stage's
    `request` in `run.json` is now this effective request, not only the recipe's options (first BBB check on lxplus
    showed `request.ncores: int -> None` while it recorded `request_dict()`; with the effective fields the record of a
    run without user config settings is the same as before, so no re-lock).
- **Shown and recorded:** `plan` prints `PicoProducer config: <path>; from your user config: <dotted keys>`;
  `run.json` gets `pico_config.user_config = {path, settings}`, only when a setting was used (a run without
  settings writes what it wrote before).
- **Wrong values:** `manage.check()` lists them as warnings (every command). For a recipe with a production stage,
  `check_recipe` adds them as problems (`user config`), so `check` fails and the menu shows the recipe red;
  `plan`/`start` stop with a `UserConfigError` in one line (taufw.py catches it). A wrong `run_root` stops `start`;
  the warnings and `plan` treat it as not set. The menu's recipe previews include the user config in their file
  signature, so they are read again after it changes.
- **Unchanged:** `pico.py` and the scripts (they read `config.json` only); the run_root warning and the
  `(default: no run_root in the recipe)` line keep their text (BBB `framework.production` records them).
- **Tests:** every test of `Tests/Framework` runs with a neutral user config (`checkout.py` sets
  `$TAUFW_USER_CONFIG` to a reviewed file without settings), so a developer's own file changes nothing.

## 42. The menu's run status says READING STATUS, and a stopped run is PAUSED

**Date:** 2026-10-27
**Status:** done (lxplus check open: [TODO.md](TODO.md) section 1)
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#42-the-menus-run-status-says-reading-status-and-a-stopped-run-is-paused)

**Details:** two reports from the menu (user, 2026-10-27). (1) Inspect run status of a DONE run first showed
`RUNNING` and `(no output yet)`, then `DONE | 00:01 | taufw.py status`: the state line was the state of the
`taufw.py status` command, not of the run. (2) A run whose advance was stopped between two stages
(`slow: DONE`, `second: NEW`) stayed `RUNNING` in the run list for days: `RunRecord.state` is computed from the
stages, and `RUNNING` is its last rule ("half done"), not "an advance works on it". Options discussed: B1 (only the
menu says `PAUSED`) and B2 (split the state in the Framework); the user chose B1 for now, B2 is a TODO
([TODO.md](TODO.md) section 6).

- **Command screen** (`Utilities/python/Menu/_command_screen.py`): while the command runs the state line says
  `READING STATUS` (`taufw.py status`) or `READING PLAN` (`taufw.py plan`), and the empty Output view says
  `Reading the run status...` / `Reading the plan...`. Once it is done the state is left out:
  `00:01 | taufw.py status`. STOPPING, FAILED (with the exit code), STOPPED and LOST stay.
- **Operation screen** (`_operation_screen.py`): `ScreenModel.empty`, the line of an empty Output or log view
  (`(no output yet)` by default); the state line leaves out empty parts.
- **Run list** (`_navigation.py`, `MenuNavigation._summary`): a `RUNNING` run is shown as `PAUSED` (yellow, like
  `WAITING`) unless an advance behind the menu runs now or a live `advance.lock` is held (an advance from the CLI).
  Only the list: `run.json`, `taufw.py status`, `RunState` and Continue are unchanged. The UI preview lists a
  PAUSED run.

## 43. A channel setup can leave out the QCD estimate (`qcd: false`)

**Date:** 2026-10-27
**Status:** done (lxplus check open: [TODO.md](TODO.md) section 1)
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#43-a-channel-setup-can-leave-out-the-qcd-estimate-qcd-false)

**Details:** `fillhists.py` always added the OS/SS QCD estimate (`QCD_OSSS`) to every stack. The CMSDAS26 long
exercise, redone as `Analyses/CDTest`, has none in the mumu channel (`qcd.method: null` of its `cmsdas_mumu.yml`).

- **`Histogrammer/fillhists.py`** (`plot()`): a channel setup with `qcd: false` fills the stacks without a data-driven
  method (`SampleSet.getstack(method=None)`). Without the key (every existing setup) or with any other value:
  `QCD_OSSS`, as before. Only fillhists.py reads the key; the TES/ID fit configs and `createinputsTES.py` are unchanged.
- **Contract** ([control-histograms.md](../contracts/control-histograms.md)): the `exp` group has no QCD histogram
  for such a setup. `Plotter/draw.py` draws what the file holds and needs no change.
- **Unchanged:** the templates in `Configs/Histogrammer/setups/` (no key, so no re-lock), the API and the
  `controlhists` stage (the key is in the setup file they pass on), every BBB baseline.

## 44. Retry of a failed local stage; the bundle copy is checked at every advance

**Date:** 2026-10-27
**Status:** done (lxplus check open: [TODO.md](TODO.md) section 1)
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#44-retry-of-a-failed-local-stage-the-bundle-copy-is-checked-at-every-advance)

**Why:** a FAILED stage made the whole run final. In the CDTest run (13 stages), stage 6 (`sf_tauid`, a python
step) failed because `sf/*.json` had not reached lxplus (the `*.json` rule of `.gitignore`). The file was put into
the run's bundle copy, but Continue said "cannot continue", and the 5 finished stages (about 28 minutes) had to run
again in a new run. No code, doc or changelog entry gave a reason for "final"; only the effect was written down
(`stages/base.py`, `BackwardCompatibility.md` 9.3, CL §24). The workaround (a new run reusing finished stages through
`{path: <run>/stages/<id>}`) does not help there: the later CDTest stages take no input from the earlier ones. A
stage that is not ready (a `PreflightError`) already stays NEW and can be continued once fixed; the same missing file
found while the step runs made the run final.

**What changed:**

- **`taufw.py retry RUN_DIR [--wait [--poll S]] [--take-lock]`** (`Framework.retry`): the FAILED stage is set NEW
  again, then the run goes on like `advance`. The finished stages do not run again. `advance` and Continue are
  unchanged: they never move a FAILED stage, so a retry is always asked for explicitly.
  - Only the local stages (`controlhists`, `controlplots`, `shapes`, `fit`, `python`: `Stage.retryable`, set by
    `LocalStage`) can be retried. A FAILED production stage is refused (`RetryError`: "cannot be retried yet: start
    a new run"); its rule (back to WAITING with more tries, MERGING after a failed merge) is in [TODO.md](TODO.md)
    section 6. NOT_IMPLEMENTED stays final.
  - What the failed attempt left is moved, not deleted: `logs/<id>/*` -> `logs/<id>/attempt<N>/`, `stages/<id>/` ->
    `logs/<id>/attempt<N>/stage/`. The retry starts in an empty output directory (the module APIs refuse a
    non-empty one, `Utilities/python/Process/_outdir.py`). Every retry has its own `attempt<N>`; there is no limit.
  - `run.json`: the stage's `retries` gets one entry per retry: `time`, `attempt`, `message` (why it failed),
    `archive` (`logs/<id>/attempt<N>`), `bundle_changed` (the bundle copy's changes since the start; `null` for a
    run without hashes). The stage's message, artifacts and last status are cleared; its history keeps them and
    gets a `retry` event. A stage that was never retried has no `retries` key (run.json as before).
  - `taufw.py advance`/`start` of a FAILED run name the command: "Once the cause is fixed, run stage X again with:
    taufw.py retry RUN_DIR" (local stages only).
- **The bundle copy is checked at every advance** (`Framework._check_bundle`, `bundle.bundle_hashes`):
  - `start` records the sha256 of every file of `<run>/bundle/` (`run.json` `bundle.sha256`; only when the run has
    bundle files, so a run without them, like the BBB production run, writes the same run.json as before).
  - Every advance (also each poll of `--wait`, and a retry) hashes the copy again. A change that was not seen yet
    (added, changed or removed files) is warned about once and added to `bundle.changed`: `{time, files: {path:
    added|changed|removed} since the start, digest}`. The same copy again: no warning. Another change: one more
    entry. A copy changed back to its start is one more entry with `files: {}` (the stages in between read the
    other version).
  - A run with `bundle.changed` is not clean. Each stage manifest says whether the copy had changed when the stage
    ran: `manifest.json` `bundle_changed: true|false` (written for every DONE stage from now on; manifests of
    earlier runs do not have it; the manifest format stays 2).
  - Runs started before this change (no `bundle.sha256`) are not checked; their retries record `bundle_changed:
    null`. All runs will be new runs at the release, so there is no migration.
- **Menu:** Continue on a FAILED run whose stage can be retried shows "Run failed at <stage>" with `Retry <stage>`
  (first), `Inspect status`, `Back`. Retry's description gives the failure, the bundle copy's changes and where the
  failed attempt goes. Retry runs `taufw.py retry RUN_DIR --wait` behind the menu, like "Advance to the end"
  (`_Operations.retry_run`, `retry_info`). A FAILED production run keeps the old dialog. The run screen's result card
  says "Fix the cause, then Continue offers Retry <stage>: the finished stages are kept." (production: "A failed
  production stage is final: start a new run."). The FAQ "Retries" entry says the same.
- **Docs:** `Docs/Guide/2-Tutorials/01-FirstProduction.md` (a FAILED stage), `BackwardCompatibility.md` 9.3, the
  comment of `Analyses/tes_id_2025/recipe.yml`.

**Decisions (with the user, 2026-10-27):** an explicit retry (b), not Continue resetting the stage (a) and not only a
"new run from this run" helper (c); local stages first, production later (TODO); the bundle check at every advance,
warned once per change, with a key in run.json and in the manifests; failed attempts archived in
`logs/<id>/attempt<N>/`; no retry limit; no hashes, no check for older runs. The preflight check of the files a
python step needs (`requires:`, so a missing file keeps the step NEW before it runs) is in [TODO.md](TODO.md)
section 6.

**Unchanged:** `StageState.terminal`, `RunState.finished` and `advance()` (a FAILED stage still stops the run), the
production stage and its `max_tries`, the run.json schema (3) and the manifest format (2), every BBB baseline
(`framework.production` has no bundle files and no retry, so its run.json is the same).

## 45. A read-only Markdown reference beside the terminal editor

**Date:** 2026-10-27
**Status:** done (real-terminal check open: [TODO.md](TODO.md) section 1)
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#45-a-read-only-markdown-reference-beside-the-terminal-editor)

Modify User Config opens its YAML beside `Docs/Guide/1-GettingStarted/UserConfig.md`. Each pane keeps its own
position. F5 switches focus; arrows and Page Up/Down act on that pane. F4 hides/opens the reference. At 110 columns
or more, the editor/reference use about 60/40 of the width; smaller terminals show one pane at a time (F5 switches).
F2 saves the YAML from either pane, Tab indents only while editing, and leaving still asks about unsaved changes.

- `Editor.edit_file(..., reference=path)` and `ConsoleUI.edit_file(..., title=..., reference=...)` work for other
  edited files and references too. Framework supplies the manual's checkout path independently of the config's
  location or the launch directory. Editor does not import Menu, Framework or UserConfig.
- `Editor/_reference.py` reads a UTF-8 file once, renders Markdown headings, prose, lists, links, fenced code and
  pipe tables, and owns its viewport without curses. Tables become labelled fields; code retains indentation
  and scrolls horizontally. Other constructs remain readable source. A missing/unreadable reference stays an
  error in its pane and does not stop editing/saving. `_text.py` shares display-cell clipping and wrapping.
- `_screen.py` handles layout, focus, resizing and key routing. Reference typing/deletion cannot change either
  file; save errors and unsaved-change dialogs consume keys before the panes. Cursor visibility is restored.
- The editor README, user-config manual and menu FAQ document the controls. No new dependencies or file-format changes.

## 46. Continue and Retry show how long the finished stages took

**Date:** 2026-10-27
**Status:** done (lxplus check open: [TODO.md](TODO.md) section 1)
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#46-continue-and-retry-show-how-long-the-finished-stages-took)

**Why:** the run screen of Continue (and of Retry, CL §44) listed the stages finished in an earlier advance without a
time: a run whose first five stages took 28 minutes showed them as `[DONE]` with an empty time column. `run.json`
already records the times, so nothing new is written.

- **`Framework/python/interactive.py`** (`_earlier_time`, used by `_run_of` for `advance_run` and `retry_run`): for
  every DONE or FAILED stage, the run screen's data gets `seconds`, `commands` and `log` from run.json:
  - a local stage (`controlhists`, `controlplots`, `shapes`, `fit`, `python`): its commands
    (`last_status.commands`: label, seconds, ok, log); `seconds` is their sum, `log` the last command's log;
  - a stage without commands (production): the time from its first to its last `history` entry, i.e. with the
    waits for the jobs (no commands).
  A stage that did not finish (NEW, SUBMITTED, WAITING, MERGING) gets nothing.
- **`Utilities/python/Menu/_run_screen.py`** (`RunProgress`): such a stage shows its time in the stage list, "Took
  <time> in an earlier advance." in its Details, its commands with their times and states, and its last command's
  log. Once the stage takes a step again (a retried stage), its time and commands start from zero (`earlier`).
  `Menu/_preview.py`: the made-up run shows earlier times for `ntuples` and `histograms`.
- **Unchanged:** run.json, the events, `taufw.py`, a run started from the menu (all stages NEW), every BBB baseline.

## 47. The example analyses move to Analyses/Examples/, listed under [Examples] in the menu

**Date:** 2026-10-27
**Status:** done (lxplus check open: [TODO.md](TODO.md) section 1)
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#47-the-example-analyses-move-to-analysesexamples-listed-under-examples-in-the-menu)

**Why:** the menu's recipe list showed the examples (`example_mutau_short`, `example_mutau_long`, `example_broken`)
next to the real analyses, and the CMSDAS26 port (`Analyses/CDTest`, CL §43, §44) was to stay as one more example.
With every new example the list grows, and a user's own analyses get lost among them.

- **Moved** (`git mv`, contents unchanged unless said): `Analyses/example_mutau_short` -> `Analyses/Examples/mutau_short`,
  `example_mutau_long` -> `Examples/mutau_long`, `example_broken` -> `Examples/broken`, `CDTest` ->
  `Examples/cmsdas26_ztt` (its recipe `name:` is now `cmsdas26_ztt`, so its runs are `cmsdas26_ztt_<time>`; the
  other recipe names are unchanged). The `.gitignore` exceptions of the CMSDAS26 bundle follow it.
- **Framework** (`defaults.py` `EXAMPLES_DIR_NAME = "Examples"`, `interfaces/interactive.py`): `recipes()` lists the
  recipes directory as before; `Examples/` has no `recipe.yml`, so it is not one of them. `examples()` lists
  `Analyses/Examples/` the same way. `run_roots()` also reads the `run_root` of the examples. Nothing else looks at
  the directory: `check`, `plan`, `start` take a path as before (`taufw.py plan Analyses/Examples/mutau_short`).
- **Menu** (`Utilities/python/Menu/_menu.py` `select_recipe`, `_navigation.py` `_pick_recipe`): the recipe list ends
  with `Enter another recipe path`, **`[Examples]`** (accent color), `Back`. `[Examples]` opens the same screen with
  the examples (title "Start a new run / Examples"), without the create action and the other-path row, only `Back`
  (to the recipe list). An example starts like any recipe; after the start the menu returns to the main menu. The
  examples are checked ahead with the recipes (`_read_ahead`). "Create a new run" still creates `Analyses/<name>/`;
  the name `Examples` is taken by the directory (the usual "already exists").
- **An empty line between what you choose and the menu's own rows:** in the recipe list after `[Create a new run]`
  and before `Enter another recipe path`; in the examples list before `Back`; in the run list (Continue, Inspect)
  before `Enter another run directory`. `_pipeline_choice` takes `separators` like `choose`. The run list used to
  leave an empty line between every two rows when the terminal had room; with the separator its runs are one per
  line, as in the recipe list.
- **Docs:** `Analyses/README.md` (a table of the analyses and one of the examples), `Framework/README.md`,
  `Framework/python/__init__.py`, `taufw.py`, the Manual (`FirstSession.md`: the examples have their own list;
  `UserConfig.md`, `01-FirstProduction.md`: the new paths), `contracts/pico-tuples.md`, the comments of the
  example recipes. The outputs pasted in the Manual changed only in their paths; they are pasted again from lxplus
  with the check of TODO section 1. Earlier changelog, TODO_Done and validation entries keep the old names (they
  describe what was done then).
- **Unchanged:** the recipe format, `check`/`plan`/`start`/`advance`, run.json, every BBB baseline (no case uses
  the examples).

## 48. Retry of a production stage that failed after max_tries; the menu's retry asks for the lock and the proxy

**Date:** 2026-10-28
**Status:** done (lxplus check open: [TODO.md](TODO.md) section 1)
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#48-retry-of-a-production-stage-that-failed-after-max_tries-the-menus-retry-asks-for-the-lock-and-the-proxy)

**Why:** CL §44 left production out: a production stage whose chunks still failed after `max_tries` made the run
final, and the finished jobs (often hours on condor) could only be reused by a new run. Its retry was the open item
of [TODO.md](TODO.md) section 6.

**What changed:**

- **The stage decides (`stages/base.py`):** `Stage.retry_state(stage_record)` (a classmethod: the menu asks before any
  stage is built) gives the state a retry sets the FAILED stage to, or None (it cannot be retried); the default is
  NEW for the stages with `retryable` (the local stages, as in CL §44). `Stage.retry_fields(spec, stage_record)`
  gives what the retry adds to the stage's retries entry (none by default). `retryable_stage(record)` and
  `Framework.retry` ask these; `retryable` stays the flag of the local stages.
- **Production (`stages/production.py`):** `retry_state` is WAITING only after `max_tries` (`tries_used_up`: the
  stage was SUBMITTED or WAITING before FAILED, and the saved status has failed or missing chunks and none pending;
  read from run.json, so it also works for runs started before this change). `retry_fields` gives
  `{max_tries: <tries made> + <recipe max_tries>}`: 3 tries made with `max_tries: 3` allow up to 6 ("resubmitting
  (try 4 of 6)"). `_check` takes the limit of the last retry (`max_tries(spec, stage_record)`). The next check after
  the retry resubmits the failed chunks (PicoProducer's own next try). Every retry raises the limit again; there is no
  retry limit.
  - Refused (`RetryError`, "cannot be retried (<why>): start a new run"): no samples (FAILED from NEW), no job configs
    (no samples in the status), a merged tuple that failed validation (FAILED from MERGING). A re-merge after a
    failed validation is in [TODO.md](TODO.md) section 6: with `merge.clean` the valid samples' job files are gone,
    so a merge again would record only the invalid ones.
- **Framework (`runtime/framework.py`):** `_retry_failed` sets the state the stage gives. Only a stage that starts
  again from NEW has its failed attempt moved to `logs/<id>/attempt<N>/`; a production retry moves nothing (the job
  files, the merged tuples and `stages/<id>/` stay) and its entry has `archive: null`. The retries entry gets the
  stage's fields (production: `max_tries`). The history's `retry` detail and the run.log line say what was raised
  ("failed attempt 1 kept in place; max_tries now 6").
- **`taufw.py`:** a FAILED run whose production can be retried ends with "To resubmit the failed chunks of stage X
  with more tries, run: taufw.py retry RUN_DIR".
- **Menu:**
  - `retry_info` gives a production stage `tries` (made, limit after the retry); Continue > `Retry production` says
    "Resubmit the failed chunks of production with 3 more tries (up to try 6) ... The job files and merged tuples stay
    where they are."; the run list's details show "Tries: 3 made; a retry allows up to 6".
  - `needs_grid_proxy` counts a FAILED production that a retry resubmits, and a retry checks the proxy like an
    advance (it was not checked before a retry at all).
  - **A retry shows a locked run like an advance** (`_navigation.py` `_take_lock`, used by both): a held lock: back;
    a lost lock of another machine can be taken over (`retry_run(record, take_lock)`: `--take-lock`). Before, a
    retry of a locked run ended in taufw.py with RunLockError and no way to take a lost lock over.
  - The run screen's card of a failed production stage: "If its chunks still failed after max_tries, Continue offers
    Retry <stage> (more tries); other production failures need a new run." The FAQ "Retries" entry says the same.
    `_preview.py`: a scenario "failed production: retry with more tries".
- **Docs:** `Framework/README.md`, `Docs/Guide/2-Tutorials/01-FirstProduction.md`, `BackwardCompatibility.md` 9.3,
  `run_record.py` (the retries keys).

**Decisions (with the user, 2026-10-28):** each retry gives `max_tries` more tries (A1, not one more each time);
only the failure after `max_tries` for now, the failed merge stays refused (B2); the menu's lock dialog for a retry
in the same change (C).

**Unchanged:** `advance()` (a FAILED stage still stops the run), `decide_next`, the local stages' retry (CL §44: NEW,
archived), the run.json schema (3; `max_tries` and `archive: null` only in retries entries, which only a retry
writes), every BBB baseline (`framework.production` never fails, so its run.json is the same).

## 49. Recipes name the setup components they need; the menu warns if the installation did not select one

**Date:** 2026-10-28
**Status:** done (lxplus check open: [TODO.md](TODO.md) section 1)
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#49-recipes-name-the-setup-components-they-need-the-menu-warns-if-the-installation-did-not-select-one)

**Why:** the installer offers optional components (TauIDSFs, HTT efficiencies, Combine + CombineHarvester,
standalone NanoAODTools), but the selection was not kept anywhere, and a recipe did not say what it needs. A recipe
with a fit (or a python step that runs combine) on an installation without Combine was found out only when that stage
ran: it stopped "not ready" in the middle of the pipeline.

**What changed:**

- **Setup manifest (`Utilities/FastSetup.sh`, `Utilities/python/Installer`):** at the end of a successful
  installation (after the verification), FastSetup.sh writes the selected components to
  `Framework/python/_internal/setup_manifest.json` of the installed checkout (`setup_tools.py manifest`):
  `{"schema_version": 1, "components": ["tauidsfs", "htt", "combine"]}`. Every installation replaces it (also
  Install components of the menu, which runs FastSetup.sh). Not tracked (`*.json` of .gitignore). A write failure is
  a setup warning, not an error. `COMPONENTS` (ID, label) moved from `Menu/setup_menu.py` to `Installer`
  (`setup_menu`, `setup_runner` import it); `write_setup_manifest` / `read_setup_manifest` (None: no file or not a
  manifest).
- **Stages (`stages/base.py`, `stages/fit.py`):** `Stage.requires`: the components a stage type always needs; the
  fit stage: `('combine',)`. The other stage types need none of their own (production depends on the channel module
  of the PicoProducer config, which the recipe does not know: declared, not derived).
- **Recipes (`recipes/recipe.py`):** a stage may have `requires: [combine, ...]` (a stage key, like `description`;
  not an option): the components the recipe adds for that stage, e.g. a python step that runs combine. An unknown ID
  or a value that is not a list is a recipe problem. `StageSpec.requires` (as written, saved in run.json's recipe
  copy) and `StageSpec.needs` (the type's and the recipe's).
- **Warning (`recipe_warnings`):** for every stage that needs a component the manifest does not list:
  `stages[3] (fit): needs Combine + CombineHarvester, which was not selected when TauFW was installed: choose
  "Install components" in the menu and select it`. A warning, not a problem: the recipe can still start (the fit's
  preflight still stops it if combine is missing). Without a manifest (installed before this change, or not with
  FastSetup.sh, or the unit tests) nothing is checked. So it shows wherever the recipe warnings show: the recipe list
  of the menu (yellow), its preview, `taufw.py check`, `plan`, `start`.
- **Examples:** `cmsdas26_ztt` step `xsec_fit` (python, runs combine): `requires: [combine]`. `tes_id_2025` needs
  nothing written (its fit stage needs combine by itself).

**Decisions (with the user, 2026-10-28):** the selection is recorded by the installer (not looked up on disk);
production's TauIDSFs/HTT needs are only declared; no manifest: no check; the python steps declare theirs with
`requires:`, the classic stages in code.

**Unchanged:** the setup record (`.git/taufw-setup-state`, `taufw-setup-v1`), the preflight checks, the run.json schema
(the recipe copy has `requires` only if the recipe has it), every BBB baseline (no manifest in the BBB checkout, and
no BBB recipe has a fit or `requires`).

## 50. `common.tools.file` to FileIO: ensuredir, ensurefile, rmfile, getline, ensureinit

**Date:** 2026-10-28
**Status:** done (lxplus check open: [TODO.md](TODO.md) section 1)
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#50-commontoolsfile-to-fileio-ensuredir-ensurefile-rmfile-getline-ensureinit)

**Why:** the next step of moving `common/python/tools/` into `TauFW.Utilities` (TODO.md section 2). The file helpers
map onto `FileIO`, which already does the same work (and remote paths); keeping both meant two sets of rules for
the same thing. The user asked for cleanup first: old quirks go when no BBB case records them (none records the
output of these helpers), and each function was decided one by one.

**What changed:**

- **FileIO (`Utilities/python/FIO/_file_io.py`):** `make_directory` returns the location (it returned None; no
  caller used the value). New `require_file(location) -> str`: the location, or `FileNotFoundError` /
  `IsADirectoryError` (the public face of the internal `_require`). Tests in `Tests/Utilities/test_file_io.py`.
- **`ensuredir` (86 calls, 56 files in the Fitter, Histogrammer, PicoProducer and `Tests/`)** ->
  `FileIO().make_directory(path)`. The three calls with several parts use `os.path.join`. Dropped: `$VAR` expansion
  (no caller), the `>>> Making directory` message (one caller, `storage/base.py`), `empty=` (no caller), and the
  "Failed to make directory" print that went on (now an exception). An empty path raises in FileIO, so the two
  places where it can be empty keep the old no-op with an `if`: `createinputs(outdir="")`
  (`Histogrammer/python/shapes/inputs.py`) and the T2_DESY `tmpdir = ''` of `StorageSystem.hadd`. The analysis
  configs (`Histogrammer/config/samples*.py`, `Fitter/Zpt/config/samples.py`) no longer import `ensuredir`; the
  scripts that got it through `from config.samples import *` import FileIO themselves. Side effect:
  `Fitter/python/plot/correlation.py` called `ensuredir` without importing it (NameError); it works now.
- **`ensuredir` aliases for scripts outside the repository (BACKWARD COMPATIBILITY, CLEANUP; user decision):**
  `TauFW.Histogrammer.sample.utils` (also `TauFW.Plotter.sample.utils`) and `TauFW.PicoProducer.workers` (also
  `TauFW.PicoProducer.processors`) keep a small `ensuredir(*paths)`: join, `FileIO().make_directory`, return the
  path (`''` stays `''`; `verb`/`empty` ignored). Nothing in the repository uses them; delete at the migration point
  (TODO.md section 8, [BackwardCompatibility.md](BackwardCompatibility.md) section 5.5).
- **`ensurefile` (3 callers: `cli/config.py`, `corrections/era_config.py`, `datasets/catalog.py`)** ->
  `FileIO().require_file(os.path.join(...))`; the unused `fatal=False` warning mode is gone.
- **`rmfile`** -> `FileIO().remove_file(path, missing_ok=True)` (`storage/base.py`, `workers/picojob.py`,
  `workers/skimjob.py`). Bug W03 fixed: `skimjob.py` passed the outputs as one space-separated string, so with more
  than one input file per job nothing was removed; it now removes each file of `outflist`.
- **`getline`** -> `jobs/status.py` reads the job list once (`FileIO().read_lines`, lazily, only for SGE/SLURM) and
  takes line `taskid-1`, instead of opening and scanning the file for every queued job. No trailing newline (the
  regexes do not see it); a task number beyond the list is an `IndexError` instead of a silent `''`.
- **`ensureinit`** -> a small helper in `PicoProducer/python/cli/config.py` (its only user) with `FileIO`; same
  message; the generated comment reads `# Generated by pico.py ...` (was `# Generatedby pico.py ...`).
- **`writetemplate`, `expandfiles`:** deleted (no callers; `FileIO.write_template` / `expand_paths` exist).
- **`ensuremodule` stays in `common/python/tools/file.py`** with the `ensurefile` it calls, unchanged (user: needs
  more research; TODO.md section 2 has what was found). So `file.py` is not deleted yet; its other functions and the
  `past.builtins`, `utils` and `shutil`/`glob`/`re` imports are gone.
- **Bookkeeping:** `Tests/migration.json` `edited` notes for the 16 moved test scripts that were changed;
  `Utilities/IOInventory.md` rows of the changed files regenerated with `_audit_io.py`'s own row code and spliced in
  (the hand edits kept); W03 in [Bugs.md](../Bugs.md).

**Decisions (with the user, 2026-10-28):** `file.py` before `string.py`/`utils.py` (no new package, nothing in BBB);
`make_directory` returns the path (not a new `ensure_directory`, not two-line callers); `require_file` in FileIO;
`ensuremodule` untouched; the small helpers as above; the hub aliases kept and documented for the migration point.

**Unchanged:** every BBB baseline (none records these helpers' output); the files with their own `ensuredir`
(`Fitter/{ETauFR,TauES}/correctionlib/utils.py` and `tau_tid_2024.py`, which uses the TauES one,
`PicoProducer/utils/convertGENSIM.py`, `Tau_Trigger_SF`, `Tests/Plotter/testCMSStyle.py`/`testTLaTeX.py`,
`Tests/PicoProducer/compat/test_processors_compat.py`); the storage method `StorageSystem.ensuredir` (remote, a
different thing); Legacy (gets `ensuredir` from the Plotter alias).

## 51. Utilities: TauFW's own tools move to `Utilities/python/Internal`

**Date:** 2026-10-28
**Status:** done (lxplus check open: [TODO.md](TODO.md) section 1)
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#51-utilities-taufws-own-tools-move-to-utilitiespythoninternal)

**Why:** `Utilities/python` mixed two kinds of packages: libraries for analysis code and the stages (CLI, FIO, Math,
Drawing, ...) and TauFW's own tools that only the Framework uses (the menu, the editor, the installer, the
operations behind the menu). Someone opening the folder could not tell which ones were theirs. Measured before the
move: nothing outside the Framework, Utilities and `Tests/` imported Menu, Editor, Installer or the operation half
of Process.

**What changed:**

- **Moved (`git mv`, contents unchanged apart from imports):** `Menu/`, `Editor/`, `Installer/` ->
  `Utilities/python/Internal/`; `Process/_events.py`, `_background.py`, `_operations.py`, `_supervisor.py` ->
  `Utilities/python/Internal/Operations/` (`_supervisor.py` runs by its path, so it stays next to `_operations.py`).
  Imports: `TauFW.Utilities.Internal.Menu`, `.Editor`, `.Installer`, `.Operations`.
- **`TauFW.Utilities.Process`** keeps `Command`, `CommandResult`, `CommandPlan`, `RunReport`, `ProcessRunner`,
  `ParallelProcessor`, `output_dir_problems`, `tuple_pattern_problems`. `EVENTS_ENV`, `EventWriter`, `EventReader`,
  `LogTail`, `BackgroundProcess`, `Operation`, `OperationStore` and the states are exported by
  `TauFW.Utilities.Internal.Operations`. No aliases at the old names (user decision): no script or stage used them.
- **`UserConfig` stays public and whole** (user decision): `load()` is for everyone; `manage` stays a module of it.
- **Before `cmsenv`:** FastSetup runs `Utilities/python/Internal/Installer/setup_runner.py` and `setup_tools.py`
  (`Utilities/FastSetup.sh`, two paths). The scripts still put their parent folder (now `Internal/`) on `sys.path`,
  so Menu and Installer import each other as before; `setup_tools.py userconfig` adds `Utilities/python` as well, for
  UserConfig.
- **Callers:** the Framework (`interfaces/interactive.py`, `recipes/recipe.py`, `runtime/reporting.py`,
  `scripts/taufw.py`, a comment in `stages/base.py`), `Tests/run.py`, `Tests/Setup/*`, and the Utilities and Framework
  unit tests (imports and `mock.patch` targets).
- **Import boundary:** `Tests/check_import_boundaries.py` fails when a stage or a public Utilities package imports
  `TauFW.Utilities.Internal` (`from TauFW.Utilities import Internal` included); the Framework and Internal itself
  may. Relative imports are not checked (as before). Detector test `test_utilities_internal_is_framework_only`.
- **Docs:** `Utilities/README.md` says which packages are for analysis code and which are Internal; the menu, editor,
  installer and operations sections moved to the new `Utilities/python/Internal/README.md`. `Framework/README.md`
  and `Internal/Editor/README.md` paths updated. Earlier changelog sections and audits keep the old paths (history).

**Note for existing checkouts:** after `git pull`, run
`find Utilities/python -name __pycache__ -prune -exec rm -rf {} +`. A leftover `Utilities/python/Menu/__pycache__/`
makes `TauFW.Utilities.Menu` an empty namespace package, so an old import fails with "cannot import name" instead of
"No module named".

**Unchanged:** every BBB baseline (nothing that writes output changed); the stages, analysis scripts and the public
Utilities packages; the menu's behaviour.

## 52. The Framework's inside moves to `Framework/python/_internal`, with TauFW's own tools from Utilities

**Date:** 2026-10-29
**Status:** done (lxplus check open: [TODO.md](TODO.md) section 1)
**Tests/Validation:** [ValidationAndTests.md](ValidationAndTests.md#52-the-frameworks-inside-moves-to-frameworkpython_internal-with-taufws-own-tools-from-utilities)

**Why:** someone opening `Framework/python` saw the runtime, the recipes, the menu adapter, defaults and settings
side by side with the public API and the stages, and could not tell what is theirs. Measured before the move:
nothing outside the Framework and `Tests/` imported a Framework submodule (analyses talk to it through recipes and
step files only). The tools §51 had put in `Utilities/python/Internal` (menu, editor, installer, operations,
notifications) were used by the Framework only, and the installer already wrote its manifest into
`Framework/python/_internal/`. With them in the Framework, `Utilities/python` holds only libraries for analysis code.
User decisions (2026-10-29): move Utilities/Internal; everything of the Framework except `__init__.py` and `stages/`
goes into `_internal`; lower-case folder names; no aliases at the old paths; tests follow the code.

**What changed:**

- **Moved (`git mv`, contents unchanged apart from imports and file-relative paths):**
  - `Framework/python/{runtime,recipes,interfaces}/`, `defaults.py`, `user_settings.py`, `version.py` ->
    `Framework/python/_internal/`. `version.json` and `empty_recipe.yml` were there already, and FastSetup's
    `setup_manifest.json` stays at the same path.
  - `Utilities/python/Internal/{Menu,Editor,Installer,Operations}/` -> `Framework/python/_internal/{menu,editor,
    installer,operations}/`, `Notifications.py` -> `_internal/notifications.py`, `Internal/__init__.py` and
    `README.md` -> `_internal/`. `Utilities/python/Internal` no longer exists.
  - Imports: `TauFW.Framework.runtime.framework` -> `TauFW.Framework._internal.runtime.framework` (and so on);
    `TauFW.Utilities.Internal.Menu` -> `TauFW.Framework._internal.menu` (`.editor`, `.installer`, `.operations`,
    `.notifications`). No aliases at the old names (user decision): nothing outside the Framework used them.
- **Unchanged for users:** `from TauFW.Framework import Framework, Recipe, ...` (the public API of `__init__.py`),
  `python3 taufw.py`, recipes and step files. `Framework/python/stages/` stays visible: the stage contract.
- **File-relative paths:** `defaults.ANALYSES_DIR`/`SETUP_MANIFEST`, `version.MANIFEST_PATH`,
  `analysis.EMPTY_RECIPE`, `interactive.CHECKOUT` (one level deeper) and `python_step.STEP_RUNNER`
  (`stages/../_internal/runtime/step_runner.py`). `_supervisor.py` stays next to `_operations.py`.
- **Before `cmsenv`:** FastSetup runs `Framework/python/_internal/installer/setup_runner.py` and `setup_tools.py`
  (`Utilities/FastSetup.sh`, two paths; `Tests/run.py` and `Tests/Setup/*` likewise). They put `_internal/` on
  `sys.path` and import `menu`, `installer` and `notifications` as top-level packages; `setup_runner.py`,
  `setup_menu.py` and `setup_tools.py userconfig` add `<checkout>/Utilities/python` for UserConfig.
  `setup_menu.py` run by its path had failed since the notifications commit (`import UserConfig` without
  `Utilities/python` on the path); it adds it now too.
- **Import boundary:** the rule of §51 (stages and public Utilities never import `Utilities.Internal`) becomes a
  wider one: no package but the Framework imports `TauFW.Framework` at all (`_internal` included).
  `Tests/check_import_boundaries.py` `test_framework_is_imported_by_the_framework_only`; 0 violations today.
- **Tests:** `Tests/Utilities/test_{background,editor,events,menu,notifications,operation_screen,operations,preview,
  run_picker,run_screen,test_run}.py` -> `Tests/Framework/` (they now use its `checkout.py`). `test_menu`'s
  "the menu imports no Framework module" test stubs the package `TauFW.Framework` (its `__init__` would load the
  runtime) and allows only the menu's siblings; `test_editor` imports `editor` standalone from `_internal/`.
- **Docs:** `Framework/README.md` (reading order, package layout, file table), `_internal/README.md` (what is
  inside, the tools' sections with the new names), `Framework/python/__init__.py` and `_internal/__init__.py`
  docstrings, `Utilities/README.md`, `Analyses/README.md`, Bugs.md K01-K08, the header of `Configs/configs.lock`
  (the comment `taufw.py configs update` writes). Earlier changelog sections and audits keep the old paths (history).

**Note for existing checkouts:** after `git pull`, run
`find Framework/python Utilities/python -name __pycache__ -prune -exec rm -rf {} +` and `scram b`. A leftover
`__pycache__/` in an old folder makes it an empty namespace package, so an old import fails with "cannot import
name" instead of "No module named".

**Unchanged:** every BBB baseline (nothing that writes output changed); the stages, analysis scripts, the Utilities
libraries and the example recipes (`taufw.py check`/`plan` of every bundle in `Analyses/` print the same before and
after); the menu's behaviour.
