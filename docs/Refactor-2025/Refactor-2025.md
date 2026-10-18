# Refactor-2025: change log

**Author:** Yagizhan Dinckurt (yagizdkurt), October 2026
**Branch:** `Refactor-2025`
**Last updated:** 2026-10-18

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
| 12 | [Shared code moved to Utilities](#12-shared-code-moved-to-utilities) |
| 13 | [Import-boundary test and coupling inventory](#13-import-boundary-test-and-coupling-inventory) |
| 14 | [Fitter imports drawing helpers from their own home](#14-fitter-imports-drawing-helpers-from-their-own-home) |
| 15 | [Framework: explicit stage ids, inputs and recipe validation](#15-framework-explicit-stage-ids-inputs-and-recipe-validation) |
| 16 | [Framework: run directory with logs/ and stages/, stage manifests](#16-framework-run-directory-with-logs-and-stages-stage-manifests) |
| 17 | [Framework: Plotter and Fitter outputs in the run directory](#17-framework-plotter-and-fitter-outputs-in-the-run-directory) |
| 18 | [Framework: tuples as an input, production writes into the run, run_root](#18-framework-tuples-as-an-input-production-writes-into-the-run-run_root) |
| 19 | [Framework: inputs from another run's stage directory, repeated stages](#19-framework-inputs-from-another-runs-stage-directory-repeated-stages) |
| 20 | [Menu: commands run beside the screen; the test screen; Framework events](#20-menu-commands-run-beside-the-screen-the-test-screen-framework-events) |
| 21 | [Configs: config templates with an id, a version and a lock](#21-configs-config-templates-with-an-id-a-version-and-a-lock) |
| 22 | [Sample lists as data: the sample model](#22-sample-lists-as-data-the-sample-model) |
| 23 | [Menu: operations run behind the menu](#23-menu-operations-run-behind-the-menu) |
| 24 | [Plotter becomes Histogrammer; a clean Plotter is extracted](#24-plotter-becomes-histogrammer-a-clean-plotter-is-extracted) |

The reference environment for all of this is `CMSSW_14_1_0_pre4` (Python 3.9, ROOT 6.30).

**How to read the checks.** Every step was checked on Windows with `python Tests/run.py checks` (the unit suites;
`check_root` needs ROOT and `check_import_boundaries` fails on the known coupling debt, so neither passes there).
The "lxplus" lines give the checks that need ROOT. "`bbb check` N/N without re-lock" means every BBB regression case
gave exactly its locked output. Import-boundary totals are written as occurrences / file-module pairs / files.
IDs such as L17, F25, K07, P08 or S17 are entries of the BUGS registers of Histogrammer, Fitter, Framework and
PicoProducer.

---

## 1. Test migration and BBB regression tests

**Date:** 2026-10-12
**Commits:** `949ce56` (Test Migration 1), `bc1e28c`, `9b4b407`, `875ba88`, `905eac8`, `28b8c57`,
`dd0fb9e`, `0f36771`, `646d28f`, `9f9d510` (Lock BBB baselines), `ef80e40` (Re-lock BBB baselines)
**Details:** [Tests/README.md](../../Tests/README.md), [Tests/LEGACY_BROKEN_CASES.md](../../Tests/LEGACY_BROKEN_CASES.md)

### What changed

- **Tests moved to top-level `Tests/`.** Moved 38 test files unchanged.
  [Tests/migration.json](../../Tests/migration.json) records original paths and content hashes.
- **A test runner, `Tests/run.py`.** Each test runs in a fresh process and temporary source workspace.
  [Tests/inventory.json](../../Tests/inventory.json) classifies 37 cases: 26 local (run by `normal`),
  7 opt-in integration, 2 legacy and 2 broken. Missing dependencies produce SKIP.
- **BBB: exact regression tests** (`Tests/BBB/`). Added 13 cases using fixed ROOT fixtures,
  recording histogram/tree structure, values and errors. Floating-point values are compared by exact bytes,
  without tolerance. Coverage includes:
  - common: table/loading-bar text, chunking and formatting;
  - Plotter: selections, weighted 1D/2D histograms, merging/splitting, DY stitching, QCD OS/SS, unrolling;
  - PicoProducer: tree writer schema, NanoAODTools bookkeeping, scale-factor lookup;
  - Fitter: shape naming, negative-bin sanitation, adaptive rebinning.

  `python3 Tests/run.py bbb lock` runs each case twice and rejects non-repeatable baselines.
  `python3 Tests/run.py bbb check` compares against [committed baselines](../../Tests/BBB/baselines/)
  and reports the exact changed field. Baselines were locked on Linux in `CMSSW_14_1_0_pre4`
  and re-locked (`ef80e40`) with CMSSW-provided packages.
- **Harness self-checks:** added offline checks (`Tests/check_harness.py`) and ROOT checks
  confirming that deliberate output changes are detected (`Tests/check_root.py`).
- **References updated:** removed the `test` channel from the PicoProducer default config and
  `config_example.json`; `TestModule` is now imported as `Tests.PicoProducer.analysis.TestModule`.

### Fixes found while running the tests

- `Plotter/python/plot/Stack.py` (`49dc76f`): nonzero integer `ratio` values now create one lower panel,
  fixing a crash for `ratio=3` and an empty panel for `ratio=2`.
- `Plotter/python/plot/utils.py` (`a9c18d8`): `gethistratio` now accepts a `TGraph` denominator
  (e.g. a data graph after `dividebybinsize`).
- `PicoProducer/python/processors/skimjob.py` (`0f36771`): the Run 2 JME import is now done only when
  `--jec`/`--jec-sys` is used. Run 3 users can rely on CMSSW's built-in NanoAODTools without installing the
  standalone repository.

### Why

Establish regression baselines before refactoring, keep test artifacts outside production packages,
and distinguish runnable tests from existing broken or legacy cases. BBB verifies that the covered outputs
remain unchanged. Intentional output changes require an explicit `bbb lock --replace`, reviewed in Git.

---

## 2. FastSetup script

**Date:** 2026-10-12
**Commit:** `41c7c0e`
**Details:** [docs/FastSetup.md](../FastSetup.md)

### What changed

- Added root [setup.sh](../../setup.sh), backed by `Utilities/FastSetup.sh`. From a fresh clone, run `source setup.sh`.
  It creates `CMSSW_14_1_0_pre4`, detects EL8/EL9 for `SCRAM_ARCH`, moves TauFW into the release's `src/`,
  installs TauIDSFs, HTT lepton efficiencies, Combine `v10.6.1` and CombineHarvester `v3.1.0`, and builds.
- Options: `--cmssw-dir`, `--jobs`, `--run2-jme` (standalone NanoAODTools for Run 2 JEC/JER), `--help`.
- Reuses existing checkouts, backs up HTT before replacement, and supports resuming failed installations.
- README installation instructions now offer automatic and manual setup.

### Why

Automates a multi-step installation and standardizes the reference environment used for BBB tests.
Standalone NanoAODTools remains opt-in for Run 2 JEC/JER workflows.

---

## 3. Removal of legacy Python 2 scripts

**Date:** 2026-10-12
**Commit:** `ab5e7a2`

### What changed

Deleted 27 Python 2-only scripts (6523 lines) after checking imports and shell-script calls.
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

**Date:** 2026-10-12
**Commit:** `65ed36b`
**Details:** [Utilities/README.md](../../Utilities/README.md), [Utilities/IOInventory.md](../../Utilities/IOInventory.md)

### What changed

- Added `TauFW.Utilities` with two independent interfaces:
  - **`CLI`**: verbosity, stderr warnings/errors, headers, tables, progress and prompts.
  - **`FileIO`**: local files and explicit XRootD/GFAL URLs, common data formats, directory operations,
    ROOT file ownership and `hadd`. Overwrites require `overwrite=True`; external commands use argument lists
    without a shell and have timeouts.
- Added an I/O inventory mapping existing terminal/file operations to `CLI`/`FileIO` methods.
- Added offline unit tests with mocked remote/ROOT operations; the test runner includes Utilities in its workspaces.

**No existing framework code used these packages at this point.** This commit only added them; §12 moves code onto them.

### Why

Provide shared, tested I/O implementations with explicit remote paths, safe writes and ROOT ownership,
replacing duplicated helpers incrementally. Each later migration can be reviewed separately and checked
against the existing BBB baselines for unchanged covered outputs.

---

## 5. PicoProducer cleanup: command-level BBB tests and bug register

**Date:** 2026-10-12
**Details:** [Tests/README.md](../../Tests/README.md#picoproducer-command-cases-black-box),
[docs/PicoProducer/BUGS.md](../PicoProducer/BUGS.md)

### What changed

- Added five command-level BBB cases: `pico.config`, `pico.run`, `pico.jobs`, `pico.merge`, `pico.workers`.
  They run `pico.py` and workers in fresh processes with fixed configuration/catalogs, synthetic NanoAOD
  and a fake scheduler. Snapshots cover config edits/recovery, chunking and option merging, status/resubmission,
  merge/cleanup gates, worker outputs and remaining files.
- Added a bug register with 60+ defects, their locations, severity, BBB coverage and planned fixes.

### Why

Existing PicoProducer baselines covered tree writing, bookkeeping and scale factors, leaving command workflows
unprotected. Testing public commands and normalizing internal script paths keeps coverage useful when modules move.
Some baselines deliberately record registered bugs; fixes require explicit, reviewable baseline changes.
Still open: a `ModuleTauPair` channel case before the analysis/corrections cleanup (TODO §5).

---

## 6. PicoProducer cleanup: settings, datasets, storage, batch and jobs packages

**Date:** 2026-10-12
**Details:** [docs/PicoProducer/BUGS.md](../PicoProducer/BUGS.md)

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

Fixed: S01 (SGE array submission; **not tested on an SGE site**), S02–S15 (batch lookup, adapter construction,
storage commands and merges, sample type detection, event totals, `Embedded` spelling with `Embdedded` kept as an
alias), P16 (private config attributes), P17 (fresh-install eras), P18 (`getconfig(write=False)`: only the CLI
rewrites the config). **Won't fix:** S16 (NAF users select `pico.py set batch HTCondor_NAF`). Details and output
impact per bug: [BUGS.md](../PicoProducer/BUGS.md).

**Only P17 changes a BBB baseline** (`pico.config`, `fresh.values.eras`).

### File-name correction and validation

Eight case-only module renames were missing from Git, causing Linux import failures. Fixed in `ae0d9bf`.
Do case-only renames on Linux with `git mv`, or verify tracked spelling on Windows with `git ls-files`.
After the correction, lxplus BBB showed only the intended P17 difference; the other 17 cases passed.
Re-lock `c2d8296` changed only `pico.config.json` and `manifest.json`.

---

## 7. PicoProducer cleanup: job pipelines

**Date:** 2026-10-13
**Details:** [docs/PicoProducer/BUGS.md](../PicoProducer/BUGS.md), [API](../PicoProducer/API.md)

### A. Job pipelines

Split `pico/job.py` and `pico/run.py` into the `jobs/` package (`worker_command`, `request` with `JobRequest`,
`planner`, `pipeline`, `reporting`, `jobconfig`, `status`, `merge`, `local`), used by the public API (§8) and
the Framework. Configuration is passed explicitly instead of read from the global `CONFIG`; planning
(`iter_plans(..., materialize=False)`) writes nothing; the CLI keeps argument handling and prompts. Status classifiers
work on a copy of `chunkdict`, and `ChunkStatus.mergeable` (nothing pending or to resubmit) is the merge/cleanup gate
unless forced.

**Validation:** worker options and 280 submit/resubmit/status/merge/local-run scenarios (verbosity 0–3) matched the
old code (`3c401cd`) in output, files and external calls; the only difference was the exception type of P02's
existing prompt crash.

### B. Bug fixes

- **Crashes, no BBB change:** P01 (Python 2 `err.message`), P02 (submission prompt), P03 (`.json.gz` job configs),
  P07 (comparison instead of assignment).
- **Behavior, no BBB change:** P04 (`--checkqueue 1`), P05 (no matching samples), P06 (`maxevts` splitting), P11
  (failed local workers reported), P19 (cleanup only after a valid merge; `MergeResult.invalid`), P20 (prompt
  answers), P21 (unexpected event counts warned), P22 (status creates no directories), P23 (cleaning one tag keeps
  the others).
- **Module options, BBB re-locked:** P08 (precedence channel < sample < user `-E`), P09 (resubmission does not grow
  the options), P10 (no default `-m -1` for local runs). `pico.run` and `pico.jobs` were re-locked on lxplus; they
  differ only in option order, the removed `-m -1` and the verbose labels `chopts`/`useropts`
  ([exact differences](../PicoProducer/BUGS.md#p08-p09-p10-module-options-and-run--m)).

---

## 8. PicoProducer cleanup: public API, command line, workers

**Date:** 2026-10-13
**Details:** [API](../PicoProducer/API.md), [I/O contract](../PicoProducer/IO.md),
[bugs](../PicoProducer/BUGS.md)

### A. API, CLI and workers

- **`api/`:** `PicoProducer` (`plan`, `iter_plan`, `submit`, `resubmit`, `status`, `merge`, `clean`, `run_local`)
  with frozen, JSON-serializable result records. `PicoProducer.from_config(config, reporter, basedir)` accepts the
  default config, a path, a dict or a `Config` without writing it; `plan()` writes nothing.
- **`cli/`** replaces `pico/` and calls the API; `scripts/pico.py` is a thin entry point. `settings/store.py`
  `loadconfig(path)` loads read-only. The Framework uses only the public API, and BBB drives the same CLI → API path.
- **`processors/` is renamed `workers/`.**
- Limitations: file operations temporarily enter the PicoProducer directory (**not thread-safe**); reporting is silent
  by default (`ConsoleReporter` for terminal output).

**Validation:** 296 job scenarios and 30 CLI command lines matched the old output, files, calls and exit codes.

### User migration and compatibility

Private imports change from `TauFW.PicoProducer.processors` to `TauFW.PicoProducer.workers`; config channels need no
change, and `pico.py resubmit` rewrites old job lists to `workers/`. Deprecated `processors/` import aliases
(`FutureWarning`) and script forwarders keep external scripts and old job lists working
([README](../../PicoProducer/python/processors/README.md)). **Removal:** delete `processors/` and
`Tests/PicoProducer/compat/` once no pre-2026-10-13 job lists remain in use.

### B. Command-line and worker fixes

Fixed: P12 (workers use `--opts`, not argparse prefix matching), P13–P14 (install dispatch, `cmssw` spelling), W02
(picojob description). **Won't fix:** P15 (status/merge/cleanup omit submission options), W01 (skim workers ignore
`-E/--opts`). P12's `--opt` → `--opts` is the only further difference in `pico.run`/`pico.jobs` (re-locked in §7).

---

## 9. Framework: the TauFW orchestrator

**Date:** 2026-10-13
**Details:** [Framework/README.md](../../Framework/README.md)

Added `TauFW.Framework` to run recipe-based pipelines with persisted state, replacing manually chained
PicoProducer, Plotter and Fitter commands.

### What changed

- **Framework:** `plan`, `start`, `advance`, `run`, `status` build stage requests and decide when to wait,
  resubmit or continue. Construction is read-only; waiting is explicit (`advance(wait=True)`).
- **Stages:** shared `Stage`/`StageOutcome` contracts and states NEW → SUBMITTED → WAITING → MERGING → DONE,
  plus FAILED/NOT_IMPLEMENTED. Production uses only the public PicoProducer API; pure `decide_next` selects
  wait/resubmit/merge/fail with `max_tries`.
- **Run record:** `taufw_runs/<name>_<time>/run.json` (schema 1) stores the recipe/config snapshot and each stage's
  state, attempts, requests, submissions, status, artifacts and history. Saved atomically after every stage step.
  (The layout changed in §16.)
- **Reporting:** terminal output and `run.log` share Framework/PicoProducer messages; silent reporting is supported.
- **CLI:** `taufw.py plan RECIPE [--local -m N]`, `start RECIPE [--run-root DIR] [--wait --poll S]`,
  `advance RUN_DIR [--wait --poll S]`, `status RUN_DIR`; all delegate to Framework.
- **API boundary:** `PicoProducer.request(**fields)` builds requests without internal imports; PicoProducer loads
  only when constructing a production stage. Recipes are documented in the [analysis guide](../../Analyses/README.md).

### Tests

- 21 offline Framework tests cover stage transitions/retries, merge failures, exception recording, read-only
  status, persistence, recipe validation and CLI behavior.
- New lxplus BBB case `framework.production` records plan/status, run-state snapshots, resubmission, merged tuples
  and cleanup.

---

## 10. Framework: plots, histograms and fit stages

**Date:** 2026-10-13
**Details:** [Framework](../../Framework/README.md), [Fitter bugs](../Fitter/BUGS.md), [Histogrammer (former Plotter) bugs](../Histogrammer/BUGS.md)

Connected control plots and the combined TES+TauID workflow through public APIs wrapping existing scripts.
Later internal cleanup can preserve these APIs without changing Framework.

### What changed

- **Utilities.Process:** sequential commands without a shell, per-command logs and stop on failure.
  Success requires exit 0 and fresh expected outputs, catching ignored nested failures and stale files.
- **Fitter.api.TauESID:** plan/make/preflight shapes (`run_inputs.sh`) and plan/run/preflight fits
  (`run_workflow_zmm.sh`, option 3); parses fit values. A control-plots API wraps `plot.py` (split in two in §24).
- **Stage context:** run directory and upstream artifacts flow between stages and plans. Preflight problems
  leave stages NEW for retry; local stages advance to DONE/FAILED, recording command exit codes/durations
  and showing failure log tails. Fit working points come from the recipe or histogram artifacts.
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
| F07 | Read rebinned files from their actual output location (confirmed on lxplus 2026-10-17). |
| L01 | Correct misspelled DeepTau branches in `plot.py`. |

Off-path F08–F10 and L02 were registered only.

### Tests

Offline tests cover command parity with existing scripts, process failures/stale outputs, preflight,
fit values and stage/artifact behavior. BBB `framework.production` was re-locked; the other 18 cases were
unchanged. Local script stages are outside BBB coverage.

**Still open:** a full VTight/Tight `taufw.py start` run of `Analyses/tes_id_2025` compared with the shell drivers
in a clean copy (TODO §1). The fit part on the same shapes was compared in §17.

---

## 11. Framework: analysis bundles and Python steps

**Date:** 2026-10-13
**Details:** [Analyses](../../Analyses/README.md), [Framework](../../Framework/README.md)

Bundles collect analysis configs in one directory; Python recipe steps add custom logic without a new stage class.

### What changed

- **Bundles:** recipes moved from `Framework/recipes/` to `Analyses/<name>/`, alongside configs and `steps/`.
  Commands accept a bundle directory; `taufw.py init NAME [--from RECIPE] [--root DIR]` creates one,
  copying referenced module configs without name collisions.
- **Paths:** bundle files replace module configs as whole files, without merging. Other relative paths retain
  module resolution; paths above the bundle stay outside it. Plans show each input's source.
- **Run isolation:** `start` copies the bundle to `<run dir>/bundle/` (50 MB limit; hidden files, caches and runs
  excluded). Stages read the copy, so later source edits do not affect the run. Loose recipes copy referenced files
  only. `run.json` gains `bundle` metadata while retaining schema 1 and compatibility with older records.
- **Python steps:** `stage: python` specifies `file`, `function` (default `run`), `options`, `timeout` and optional `id`.
  Each runs in a separate process with bundle/upstream context and returns a message/artifacts. Preflight checks
  the function without importing it; failures show log tails.
- **Config propagation:** APIs pass `$TAUFW_PICO_CONFIG` to scripts. Loading is read-only; a missing configured file
  is an error, and unset behavior is unchanged. Shared `CommandPlan`/`RunReport` records moved to Utilities.Process,
  with existing API exports retained.

**Limitation:** PicoProducer's sample catalogs are not bundled; it resolves its own.

### Tests

Offline tests cover path resolution, isolated copies, old records, stage ids, initialization and real Python steps
passing artifacts or failing. BBB `framework.production` changes on purpose for bundle/config metadata; PicoProducer
cases stay unchanged.

---

## 12. Shared code moved to Utilities

Moves from `common` and Plotter into shared Utilities packages. The rule for all of them: Utilities does not import
`TauFW.common`, callers are updated and the old module is deleted (or keeps only what is not moved), and the output
stays the same; old output quirks are kept in a block marked `# ===== LEGACY, CLEAN UP LATER =====` and listed in
[TODO.md](TODO.md) for a later commit with an explicit output change.

### Parallel processes and the loading bar

**Date:** 2026-10-13
**Details:** [Utilities](../../Utilities/README.md) (Terminal I/O, Parallel Python calls)

| Old | New |
|---|---|
| `TauFW.common.tools.parallel.MultiProcessor(max=...)` | `TauFW.Utilities.Process.ParallelProcessor(max_parallel=...)` |
| `TauFW.common.tools.LoadingBar.LoadingBar(pre=...)` | `CLI.loading_bar(steps, prefix=...)`; advance with `count(message="", steps=1)` |
| `TauFW.common.math_helper` exports | Import `sqrt`, `log10`, `ceil`, `floor` from Python `math` |

Parallel processing retains queue limits, pipe results, `kwret` merging, serial mode and `close()`; loading bars keep
their terminal bytes. Removed: the unused import-time multiprocessing manager (which broke spawn), unused `Thread`
demos, and `LoadingBar.update()`/`message()`. Integer-step counting previously crashed on a tuple operation; use
`count(steps=n)` (no in-repo caller used the broken form).

### Numeric helpers

**Date:** 2026-10-13
**Details:** [Utilities/README.md](../../Utilities/README.md#numeric-helpers)

`common/python/tools/math.py` became `TauFW.Utilities.Math` (`Math/_math.py`): same results for the same inputs.

| Old (`TauFW.common.tools.math`) | New (`TauFW.Utilities.Math`) | Notes |
|---|---|---|
| `frange(start, end, step, scale)` | `float_range(start, end, step, scale)` | Same values (an `int` start stays `int`). |
| `partition(mylist, nparts, nmax)` | `partition(items, parts, max_size)` | Neither given raises `ValueError` (was `IOError`). |
| `partition_by_max(mylist, nmax)` | `partition_by_sum(values, maximum)` | Sorts a copy, not the caller's list. |
| `columnize(oldlist, ncol)` | `columnize(items, columns)` | Same order. |
| `magnitude(x)`, `reldiff(x, y)` | `magnitude(x)`, `relative_difference(x, y)` | Unchanged. |
| `scalevec(a, b, r, log)` | `scale_vector(start, end, ratio, log)` | Log-mode `assert`s are `ValueError`s with the same messages. |
| `sqrt, log10, ceil, floor` | standard `math` module | |

Dropped without callers: `ceil2digit` (raised `NameError`: `log` was never imported) and `round2digit`.

### Printf-style table

**Date:** 2026-10-13
**Details:** [Utilities/README.md](../../Utilities/README.md#terminal-io) (`CLI.table`)

`common/python/tools/Table.py` became `CLI.table(...)`, returning a `Table` (`Utilities/python/CLI/_internal/table.py`);
every line is byte for byte what the old class wrote. Kept as legacy: the four constructor forms told apart by
argument types, the header always underlined with raw ANSI codes, the old `LOG.warning` text and the debug lines.

| Old | New |
|---|---|
| `LOG.table(*formats, verb=0, level=0, pre=">>> ", ul=True)` | `CLI(verbosity=verb, prefix=pre).table(*formats, minimum_verbosity=level, underline=ul)` |
| `Table.printheader(*titles, post="")` | `print_header(*titles, suffix="")` |
| `Table.printrow(*values)` / `Table.printtable()` | `print_row(*values)` / `print_rows()` |
| `Table.header(...)`, `Table.row(...)`, `str(table)` | unchanged |
| `LOG.tableheader()`, `LOG.row()` | removed (no callers) |

The import cycle between `Table.py` and `log.py` is gone. One caller quirk is kept and listed in TODO: the
`TGraph`/`TGraph` ratio table in `Plotter/python/plot/utils.py` prints its rows with `print_header`.

### Drawing library

**Date:** 2026-10-14

Plotter's drawing code moved to `TauFW.Utilities.Drawing`, so Fitter and PicoProducer can draw without importing the
Plotter. The code moved as it was (`git mv`; function bodies unchanged, Plotter's 2-space style kept, only imports
changed); modernizing it is a TODO item ("Drawing library").

| Old | New |
|---|---|
| `Plotter/python/plot/{Plot,Plot2D,Stack,Ratio,CMSStyle}.py` | `Utilities/python/Drawing/` (same names) |
| `Plotter/python/plot/utils.py` | `Drawing/hist_tools.py` |
| `Plotter/python/sample/SampleStyle.py` | `Drawing/SampleStyle.py` (owns `Logger('Sample')`) |
| Label helpers of `Plotter/python/plot/string.py` (`makelatex`, `maketitle`, `makehistname`, ...) | `Drawing/labels.py`; `string.py` imports them back |
| `LOG = Logger('Plot')` | `TauFW.Utilities.Drawing.LOG`, the same single object for the drawing code and the Plotter |
| `TauFW.common.tools.log` and a few `common` helpers | verbatim copies in `Drawing/_internal/legacy_log.py`, `legacy_helpers.py` |

The output stays the same because there is one logger object and one module object per stateful module (`CMSStyle`,
`SampleStyle`, `hist_tools` with its `TGraph` and `TNamed.__repr__` patches), each imported from one place only. The
library recognizes the Plotter's `Variable` by duck typing (`hist_tools._is_variable`) instead of importing it;
`Plot` no longer re-exports `Variable`/`Var`. About 55 callers changed their imports only.

### ROOT expression helpers

**Date:** 2026-10-14

The helpers of `Plotter/python/plot/string.py` that know only ROOT's C++ syntax (`getselstr`, `joinweights`,
`joincuts`, `replacepattern`, `cleanbool`, private `doubleboolrexp`) moved verbatim to the new package
`TauFW.Utilities.Expressions`, so that the Fitter builds cuts without the Plotter (`Fitter/python/plot/datacard.py`).
They import no ROOT; the package is named by its job, not by a dependency. `string.py` imports the five public names
back for its star-importers; the helpers that know pico branch names (`shift`, `invertcharge`, ...) stay there.
Registered, not fixed: [Histogrammer BUGS](../Histogrammer/BUGS.md) L05 (`joinweights` with weight `0`), L06
(`replacepattern` applies only the last pattern), L07 (`joincuts` does not bracket `(x)||y`).

---

## 13. Import-boundary test and coupling inventory

**Date:** 2026-10-14

Added standard-library `Tests/check_import_boundaries.py`: stages cannot import each other; Framework may
import stage APIs; shared libraries remain available. Nested, parent-module and unresolved implicit imports
are checked; legacy directories and Tests are excluded. Python 2 imports are recovered separately.

The JSON inventory records known coupling and parse exemptions. **Known violations still fail**, as do stale
entries and import-recovery errors, so the check measures isolation progress without hiding existing debt.

Registered with the test runner; the repository check fails on known debt as intended (today's totals: §25).
Production code and baselines are unchanged.

---

## 14. Fitter imports drawing helpers from their own home

**Date:** 2026-10-14

Fitter files now import helpers directly, preserving the same objects while avoiding unnecessary Plotter setup.

| Files | Direct import |
|---|---|
| `Fitter/TauES_ID/{plot2DScan_MultiDimFit,plotParabola_POI_region,plotPostFitScan_POI}.py` | `TauFW.Utilities.Drawing.CMSStyle` |
| `Fitter/python/plot/postfit_TES.py` | Drawing's `CMSStyle`; `setera` still comes from Plotter |

`postfit_TES.py` retains its Plotter dependency because `setera` updates both CMS text and sample normalization globals.
Only imports changed; the decoupled files left the boundary inventory.

---

## 15. Framework: explicit stage ids, inputs and recipe validation

**Date:** 2026-10-14
**Details:** [Analyses](../../Analyses/README.md) "File format and validation", [Framework](../../Framework/README.md)

First step of the recipe IO work: the recipe, not the Framework, says which stage reads which stage's output, and every
problem of a recipe is shown at once. Run behaviour is unchanged otherwise.

### What changed

- **Every stage has `stage`, `id` and `inputs`, and may have `description`.** `id` is required for every stage and any
  stage may have any id (the old rules "a built-in stage's id is its name" and "a python step's id defaults to its file
  name" are gone). `description` is free text, shown by `plan` and the menu, used for nothing else.
- **Inputs:** each stage type declares its input slots and the kinds of data it makes (`Stage.inputs`, `Stage.outputs`:
  plots/histograms `tuples`, fit `shapes`, python any names). `inputs` connects every slot to the id of an earlier stage
  that makes that kind, or to `null` (not from this run: the tuples in `$PICODIR`, the shapes already in `Fitter/`); a
  stage without slots writes `inputs: null`; `{}` is an error. A stage's context now holds only the artifacts of the
  stages its inputs name (`StageContext.inputs`, `input_artifacts(slot)`); before, every earlier `DONE` stage was
  visible. The fit finds its points through `inputs.shapes`, plots/histograms record the tuples of `inputs.tuples`.
  Python steps get `ctx.inputs` and `ctx.input(name, kind)`.
- **Validation collects every problem.** `Recipe.parse()` returns `Issue`s (location + message); `Recipe.load()` /
  `from_dict()` raise one `RecipeError` that lists them all (its `.issues`). `validation.check_recipe()` adds the files a
  recipe names (`pico.config`, absolute paths, python step files) and never raises. `taufw.py check RECIPE` prints the
  problems (exit 1); `taufw.py` prints a `RecipeError` without a traceback. The menu checks every recipe when the list
  opens: a recipe with problems is red, and its preview lists the problems above the stage cards (which now show the
  stage type and description). Unknown options of one stage are reported together.
- **Bundles:** `example_mutau`, `tes_id_2025` (and `steps/fit_summary.py`, which uses `ctx.input('fit')`) follow the new
  format. `Analyses/example_broken/` is a deliberately invalid recipe that demonstrates the four kinds of problems.

### Tests

New unit cases (`Tests/Framework/test_validation.py` and the menu tests): every input error, duplicate ids, a stage
that does not see an unnamed earlier stage, a python step without inputs, `taufw.py check`, broken recipes red in the
menu, the bundled analyses valid. The recipe of the BBB case `framework.production` (`Tests/BBB/cases.py`) gets `id:
production` and `inputs: null`; its output changes on purpose: the `plan` lines (`=== Stage production (production)
===` and a new `Inputs: none` line) and the recipe in the recorded `run.json` (`id`, `inputs` keys).

---

## 16. Framework: run directory with logs/ and stages/, stage manifests

**Date:** 2026-10-15
**Details:** [Framework](../../Framework/README.md) "Run directory", [Analyses](../../Analyses/README.md) "Outputs and logs"

Second step of the recipe IO work: a stage's directory in the run now holds only what the stage makes, so the
next step can run the Plotter and Fitter scripts inside it (§17).

### What changed

- **Layout:** `taufw_runs/<run>/logs/<id>/` holds the Framework's files of a stage (command logs `NN_<label>.log`, a
  python step's `context.json` and `result.json`); `taufw_runs/<run>/stages/<id>/` holds its output (a python step's
  own files, `ctx.stage_dir`) and nothing else. Before, both were `taufw_runs/<run>/<id>/`. `StageContext.stage_dir()`
  is the output directory, the new `StageContext.log_dir()` the log directory. Directories are made when a stage runs.
- **Ids:** stage directories live under `stages/`, so an id cannot clash with `run.json`, `run.log`, `bundle/` or
  `logs/`; only `.` and `..` are refused.
- **Manifest:** when a stage becomes `DONE`, the Framework writes `stages/<id>/manifest.json`
  (`{manifest: 1, run_id, stage_id, stage, description, inputs, finished, artifacts}`), before `run.json` is saved.
  It is a copy of the stage's record, so a stage directory describes itself (for a later input that names another
  run's stage directory, §19); `run.json` stays the source of truth. A failed stage has none.
- **`run.json` schema 2:** the recipe format of §15 and this layout. A run directory of schema 1 is refused when it is
  loaded (no conversion: there are no runs to keep).

### Tests

New unit cases: log and output directories of every stage, the manifest content of a DONE stage and its absence for
a failed one, a python step's files split between `logs/` and `stages/`, the id `..` refused, schema 1 refused. BBB
`framework.production` records `run.json`, so `"schema": 2` adds to the §15 difference.

---

## 17. Framework: Plotter and Fitter outputs in the run directory

**Date:** 2026-10-15
**Status:** checked on lxplus 2026-10-15
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
  `<outdir>/<era>/`), with absolute script, config and `$TAUFW_PICO_CONFIG` paths; inner directories stay relative
  because several scripts derive one from another with `str.replace` (Fitter BUGS F18). Preflight refuses a non-empty
  output directory and a relative `picodir`.
- **Scripts** (defaults unchanged): new output options in `makecombinedfitTES_SF.py` and `make_tid_2025.py`, and paths
  found from `__file__` instead of the working directory (L11, F14–F16); full list in
  [scripts_arg_changes.md](scripts_arg_changes.md).
- **Artifacts** are paths inside the stage directories: plots count only this run's files (L08–L10), the fit no longer
  lists other taggers' corrections (F22) and lists the combined TES + ID file.
- **`null` inputs:** a stage lists the slots that may be `null` and what it means (`Stage.null_inputs`); elsewhere
  `null` is a recipe error. The fit's `{shapes: null}` (the shapes in `Fitter/`) is a documented temporary exception.

### Tests

New unit cases for the commands, working directories, artifacts and preflight problems with an output directory.
lxplus (2025 tuples of the TauFW group area): the plots equal those of `plot.py` in `Plotter/` and nothing is written
to `Plotter/` or `Fitter/`; `bbb check` 20/20 unchanged. For VTight/Tight the shell scripts with the new code give the
baseline's fit parameters and corrections exactly; the Framework's shapes equal the baseline's up to 1e-13
(multithreaded RDataFrame), and on the same shapes the Framework fit and the shell scripts agree exactly. Two runs of
shapes + fit from the same tuples can differ by a grid step in the fitted POIs (TODO §6).

---

## 18. Framework: tuples as an input, production writes into the run, run_root

**Date:** 2026-10-17
**Status:** done; the end-to-end production check passed on lxplus
**Details:** [Framework](../../Framework/README.md) "Concepts" and "Run directory", [Analyses](../../Analyses/README.md)
"Where the runs go (`run_root`)", [scripts_arg_changes.md](scripts_arg_changes.md) "Tuple location", Framework BUGS
K04, K05, K07, PicoProducer BUGS S17, Histogrammer BUGS L12

The Framework, not the global `$PICODIR`, decides where the pico tuples are read and written, and everything is
visible in the recipe.

### Recipe warnings and `run_root`

- **Warnings:** a recipe can have warnings besides its problems (it runs, but should change). `check` prints them and
  exits 0; `plan`, `start` and the menu preview show them; the recipe is not red.
- **`run_root`** (top-level key): the parent directory of the runs; `start --run-root` takes precedence; without both,
  `taufw_runs/` in the working directory with a warning. It must be absolute, not a URL, and outside the bundle; `~`
  and `$VARIABLES` are expanded with a warning. `plan` and `start` print the directory and where it comes from.
- **Write check:** before `start` with a run root and before every `advance`, the Framework writes and removes a small
  file there; on failure `RunDirectoryError` and nothing is started or moved.
- The menu's "Continue an existing run" also lists the runs in the `run_root` of every recipe in `Analyses/`.

### `--tuples` for the scripts and the APIs

- `getsampleset(..., tuples=PATTERN)`, `plot.py --tuples` and `createinputsTES.py --tuples`: the tuple directory
  pattern (`$ERA`, `$GROUP`) instead of `$PICODIR` from the PicoProducer configuration. Without it, unchanged.
- `PlotsRequest.tuples`, `ShapesRequest.tuples`: with a pattern every command gets `--tuples`, no
  `$TAUFW_PICO_CONFIG`, and preflight checks the pattern instead of the configuration (unknown `$KEYS` such as `$DAS`
  are refused).

### Production writes into the run

- PicoProducer: `JobRequest.tupledir` (never set by `pico.py`) makes `merge` write to
  `<tupledir>/$ERA/$GROUP/<sample>_<channel><tag>.root`; `PicoProducer.tuple_pattern(request)` returns where `merge`
  writes.
- Framework: in a run, production's `tupledir` is its stage directory, and every tuple artifact gets `pattern`
  (`<run_dir>/stages/<id>/$ERA/$GROUP`). `Stage.planned_artifacts` lets later stages see that pattern in a plan.
  `kind` on tuple artifacts is still missing (K04).

### Plots and histograms read the tuples their input names

- `{tuples: {external: <pattern>}}` names tuples made outside TauFW (absolute, not a URL; `check` reports a missing
  directory).
- `LocalStage.tuples_pattern(context)`: the external pattern or the production artifacts' `pattern`, passed to the
  APIs as `tuples=`. Preflight checks that the tuple files or the external directory exist. `null` is unchanged
  (`$PICODIR`). `plan` shows `Inputs: tuples <- external <pattern>`.
- `Analyses/tes_id_2025` names the TauFW group's 2025 tuples with `{external: ...}`. K03 is fixed.

### Checked

- New lxplus tests `Tests/Plotter/testTupleLocation.py` and `Tests/PicoProducer/testTupleDir.py`.
- lxplus (2026-10-17): `check`/`plan` of `tes_id_2025` as expected; plots with `{external: ...}` made the same 8 plots
  as the §17 check; a read-only `--run-root` stopped before anything was made. BBB `framework.production` now
  snapshots the merged tuples in `stages/production/` and masks the run ID; re-locked (only this case changed; the
  merged tuples are byte-identical), then `bbb check` 20/20.
- **End to end:** a production of one sample (`DYto2TautoMuTauh_M-50`, 2022_postEE, mutau, 4 jobs) followed by plots
  (`{tuples: production}`). The jobs need a grid proxy the schedd can read: one in `/tmp` gets them held, one on AFS
  (`voms-proxy-init --voms cms --out ~/private/x509up`, `export X509_USER_PROXY=...`) works. The chunks were merged into
  `<run_dir>/stages/production/2022_postEE/DY/...` and the pattern recorded; plots read inside the run, not `$PICODIR`.
  Registered on the way: PicoProducer S17 (spurious "DAS path ... has wrong format" warning), Framework K07 (`status`
  shows a stale message next to the live job table).

### Fix on the way: Histogrammer L13, Fitter F25

An exception to "no bug fixes until the refactor is finished", in its own commit: the Plotter and Fitter APIs used
`importlib.util.find_spec('ROOT')`, which raises once CMSSW's ROOT is imported, so every recipe with production before
plots or histograms crashed in `plan`. The lookup now counts an already imported module as found. No output changes.

---

## 19. Framework: inputs from another run's stage directory, repeated stages

**Date:** 2026-10-17
**Status:** checked on lxplus
**Details:** [Analyses](../../Analyses/README.md) "File format and validation" (stage order, "Inputs from another
run"), "Outputs and logs", "Troubleshooting"; [Framework](../../Framework/README.md) "Run directory"; TODO §6
"Revise: one rule for the paths in a recipe"

The last part of the recipe IO work (§15-§18): a stage may read the output of another,
finished run, and the built-in stages may repeat.

### Repeated stages, no fixed order

`plots`, `histograms` and `fit` may appear any number of times, each with its own id. The stages run in the order of
the recipe; the only order rule is that an input names a stage written above it. `production` stays at most once (its
job files are outside the run, and a run has one `pico.config`; TODO §6). `ORDER` (`stages/__init__.py`) only lists
the known stages in messages.

### Inputs from another run: `{path: <stage directory>}`

- **Recipe:** any input slot may be `{path: <run_root>/<run>/stages/<id>}`: absolute, not a URL, not inside the bundle;
  `~` and `$VARIABLES` are not expanded (unifying the path rules is TODO §6).
- **Manifest format 2** (`python/manifest.py`): adds `stage_dir` and `sources`. `read_stage_dir` refuses a missing
  directory, a missing manifest (stage not `DONE`), a format 1 manifest, and a moved or copied directory. A module
  directory such as `Fitter/` is not accepted.
- **Checks:** the source stage must make the kind of data the slot takes. `check` and the menu report every problem
  at once; `plan` shows it as a note; `advance` stops the stage like a preflight problem.
- **Framework:** artifacts come from the source's manifest, never from its `run.json`, and nothing is written to the
  source. The stages use them as if they came from a stage of the run (fit points and shape directories, `--tuples`,
  `ctx.input()`).
- **Provenance:** `StageRecord.sources` (`path`, `run_id`, `stage_id`, `stage`, `finished`, `manifest_sha256`), also
  in the reader's manifest. **`run.json` schema 3** (schema 2 runs are refused). `plan` shows
  `Inputs: shapes <- <dir> (run <id>, stage <id> (<type>), finished <time>)`.
- **Fitter API:** with `outdir`, a non-empty `shapes_dirs` must name every point (`ValueError`); `{shapes: null}` stays
  for old recipes only.

### Checked

- New unit cases (`test_manifest.py`; repeated stages, `{path}` rules, a fit, plots and a python step reading
  another run, provenance).
- lxplus (2026-10-17): `bbb check` 19 cases unchanged; `framework.production` differed only in `schema` 2 → 3 and
  `sources`, and was re-locked.
- **Fit on another run's shapes** (the §17 run, manifest converted to format 2): the 13 commands equal the §17 fit's;
  the fit parameter files and JSON corrections are byte-identical, the `tau_sf/*.root` files have the same content;
  the source directory is unchanged; `sources.shapes.manifest_sha256` matches `sha256sum` of the source manifest.
- **Repeated stages:** two plots stages (`-V m_vis`, `-V pt_1`) each wrote their own plots in their own directory.
- **Refused:** one `check` listed all four problems: a missing directory, `Fitter/`, a `cp -r` copy, and a plots
  directory given to a fit.
- **Tuples from another run** (the §18 production run): `check` and `plan` pass and give the right `--tuples` pattern.

---

## 20. Menu: commands run beside the screen; the test screen; Framework events

**Date:** 2026-10-17
**Status:** Windows tests pass; lxplus check in TODO §1 "Test screen on lxplus"

The menu should work like a program: an operation must not print into the terminal or block the screen. A long
operation therefore runs as its own process (the existing CLI command, unchanged) with stdin `/dev/null`, stdout and
stderr in a log file, and its progress as events in a second file; the screen follows both files. Only this keeps the
screen intact: ROOT and C++ write to the file descriptor, which no Python redirection catches.

### Infrastructure (`TauFW.Utilities.Process`)

- `_events.py`: one JSON object per line, `{"t": <unix time>, "kind": ...}`, in the file named by `$TAUFW_EVENTS`.
  `EventWriter` opens and closes the file per event (AFS shows changes only after a close); `EventReader` and
  `LogTail` read incrementally, survive truncation, handle `\r` progress bars and split UTF-8, and keep memory bounded.
- `_background.py`: `BackgroundProcess`, for commands that live only as long as their screen (the menu's tests and
  runs use the supervised operations of §23).

### Tests report events; the test screen

- `Tests/run.py` and `Tests/BBB/runner.py` emit `suite`, `case_start`, `case_end`, `summary`, `warning`, `error`
  (`Tests/support/events.py` repeats the protocol so the runner works without TauFW; a test checks both sides agree).
  Without `$TAUFW_EVENTS` the terminal output is unchanged.
- The test screen: the cases with `[PASS]/[FAIL]/[SKIP]/[ RUN]`, times and counts, the focused case's details and
  live log, Enter for the whole case log, L for the runner output. It replaces the in-terminal test run.

### Framework events (`EventReporter`)

`taufw.py` reports what it does as events, so a run screen can follow a `start`/`advance` started beside it. Nothing
reads them yet; the terminal output and `run.log` do not change (checked byte for byte).

- `Reporter.event(kind, **fields)` is ignored by default; `EventReporter(reporter, writer)` passes every call on and
  also writes headers, messages, warnings, tables and events. Events: `run`, `stage_step`, `stage_state`, `run_state`,
  `wait`, `progress` (every command of plots, histograms, fit and python), `error`; listed in `reporting.py`.
- `taufw.py` reads `$TAUFW_EVENTS` once and removes it from the environment, so stage commands and batch jobs never see
  it. BBB `framework.*` runs without it.

Open: the run screens (TODO §6 "Menu as a program").

---

## 21. Configs: config templates with an id, a version and a lock

**Date:** 2026-10-17
**Status:** Windows tests pass; nothing to check on lxplus (no ROOT, no BBB case)
**Details:** [Configs/README.md](../../Configs/README.md)

Analysts should not have to enter the module directories: everything an analysis can change is a copy in its bundle,
and the modules' templates for those copies live in `Configs/<Module>/`. Every template starts with a `taufw_config`
header (`id`, `version`, `schema`, `description`) that the copy keeps, so a later change of the template (e.g. a
corrected cross section) does not go unnoticed. This section built the infrastructure only; the first templates came
with §22.

- **`TauFW.Framework.configs`:** `scan` finds the templates and their problems (id must start with the module
  directory in lower case, unique); `content_hash` hashes the parsed values without the header, so comments and layout
  do not count; `update` keeps `Configs/configs.lock` (`<id> <version> <sha256>`), raising the version of a changed
  template (rewriting only that number) and refusing to write while a template has a problem or a lowered version;
  `copy_warnings` reports bundle copies whose template is newer, gone, or older than the copy.
- **Framework and CLI:** the copy warnings appear in `check`, `plan`, `start` and the menu (a warning only: an old copy
  kept on purpose is allowed). `taufw.py configs` lists the templates; `taufw.py configs update` (maintainers) raises
  versions and rewrites the lock.
- **Tests:** `Tests/Framework/test_configs.py` (no ROOT); two tests read the checkout's `Configs/`: the lock must be up
  to date, and every template must be readable by its module's reader (`READERS`).

---

## 22. Sample lists as data: the sample model

**Date:** 2026-10-17
**Status:** verified on lxplus 2026-10-17 (details in TODO §1)
**Details:** [scripts_arg_changes.md](scripts_arg_changes.md) "Sample model files", [Histogrammer BUGS](../Histogrammer/BUGS.md) L14-L16

The recipe must say which samples an analysis reads; until now `Plotter/config/samples_v15.py` decided it out of sight
(MC cross sections, data datasets, weights, stitching, joining and splitting, per era). Its samples became templates
(§21), one per era, that an analysis copies into its bundle; they are in `Configs/Histogrammer/samples/` since §24.
**No physics or data change:** every sample set built from a template gets exactly the calls the old function makes,
and a test proves it.

- **Recorder and BBB case:** `Tests/Plotter/sample_model/recorder.py` records every call of a sample-set function
  (8 eras × 6 channels × 7 caller options = 336 cases). BBB case `plotter.sample_model` was locked on lxplus with the
  old code, then switched to the model with no difference.
- **Templates:** `export.py` wrote `v15_<era>.yml` for the 8 eras from the recorded calls (nothing typed by hand,
  each file read back and compared); cross sections are cross section × k-factor as `samples_v15.py` computed them.
- **The model:** `Plotter/python/sample/model.py` (`load_sample_model`, `pick`, `sample_names`, `getsampleset`):
  the generic part of `samples_v15.getsampleset` copied as it is, the era part read from the model. A unit test checks
  all 336 cases against the old function. Registered: L14 (`DM` split `NameError`, kept), L15, L16 (era `2526` with
  tautau/emu).
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

lxplus: `bbb check` 21/21 and `Tests/run.py checks` after the switch; a plots + histograms run of `tes_id_2025` with
`samples:` against the same stages without it gave 57 byte-identical PNGs and equal shapes (up to multithreaded
RDataFrame noise; `data_obs` bit-identical); `plan` of `example_mutau_long` lists 25 samples.

---

## 23. Menu: operations run behind the menu

**Date:** 2026-10-17
**Status:** Windows tests pass; lxplus check in TODO §1 "Tests behind the menu on lxplus"

Leaving a screen must never kill what it shows: tests (now) and runs (next) go on behind the menu, which shows their
state ("Tests (Running 12/40)", "Tests (Failed: 3)") and opens their screen again. In §20 the menu was the commands'
parent; now a supervisor runs them and keeps everything in files.

### Decisions (2026-10-17)

- Esc never stops an operation; S or Ctrl-C asks, then stops it. Quitting the menu while something runs warns: C stay,
  S stop all and quit, Q quit and leave it running.
- Running on after the login session ends is not a goal (lxplus may kill processes at logout); such an operation is
  shown as **Lost**. One test run at a time. The last five records of a kind are kept.
- For runs (later): a lock in `Framework.advance`, refused while held on another machine and taken over only on
  request when Lost; a stop never kills job submission halfway (`escalate=False`); `plan`/`status`/`check` move
  beside the screen.

### Supervised operations (`Utilities/python/Process/`)

- `_supervisor.py` (standard library only): starts the command in its own process group, writes `heartbeat.json`,
  reacts to the files `stop` and `kill`, and writes `exit.json` at the end. A stop is a file, so any menu can stop an
  operation, also from another lxplus machine (AFS). JSON files are written atomically.
- `_operations.py`: `OperationStore` starts, lists and prunes operations under `<root>/<kind>-<time>/`; `Operation`
  reads their files and gives `state()`: DONE / FAILED / STOPPED from `exit.json`, else RUNNING / STOPPING, or LOST
  when the heartbeat is older than 120 s or the supervisor is gone.

### The menu

- Operations live in `<checkout>/.artifacts/menu/operations` (git-ignored). Starting tests while a run is running is
  refused, naming the host.
- The main menu labels Tests with the last run's state; Tests reopens the live screen while a run runs, otherwise the
  Tests menu starts with "Last run: <title> (<state>)". Exit goes through the quit warning.
- The test screen follows an `Operation`; a run started on another machine shows "RUNNING on <host>", a Lost run
  explains why.
- "Run all automated tests" (found on lxplus 2026-10-18): the total is now known from the start, and a case in two
  families is labelled "suite: id" ("normal: plotter.unroll", "bbb: plotter.unroll").

### UI preview (2026-10-18)

Tests > **UI preview (mock screens)** shows every menu screen with made-up data, so a screen can be looked at (and
its design discussed) without a run: Left/Right switch screens, R shows the current one again (a made-up run starts
over), Esc on a screen leaves the preview; any other answer shows the same screen again with the answer in the bar on
the last line. `Utilities/python/Menu/_preview.py`: the screens are the real `ConsoleUI` methods, drawn in one curses
session (the preview's curses stand-in hands its screen to each screen's `wrapper()`); a made-up test run is an
`Operation` whose events, output and case logs a script writes while the screen reads them (running, failed, on
another machine, lost; S stops it). Nothing is started and nothing is written outside a temporary directory. It is
not a test family; `Tests/Utilities/test_preview.py` checks that every scenario draws, the keys, and the made-up
runs. The run screens (TODO §6 "Menu as a program") are added to it as they are designed, before they are wired to
Start and Continue.

### Shared operation screen (2026-10-18)

The test screen is split: `Utilities/python/Menu/_operation_screen.py` holds the layout and keys of a screen
that follows an operation (state line, list + Details + the focused item's log, Output view, stop question, Esc keeps
it running); a model (`ScreenModel`) supplies the items and the words. `_test_run.py` keeps only `TestRun`, now the
model of the test screen (cases, "Stop the tests?", PASSED for DONE), `follow_tests` and `test_summary`. The run
screen will be a second model. The model lives in the Menu, not in the Framework: it reads only the events (plain
JSON), so the Menu still imports no Framework module; the Framework will supply the stages of `run.json` as plain
data when the screen is wired. Checked: the test screen draws the same, character for character, before and after
the split; `Tests/Utilities/test_operation_screen.py` (new) drives the core with a model that is not about tests.

### Run screen, in the preview only (2026-10-18)

`Utilities/python/Menu/_run_screen.py`: `RunProgress`, the second model of the operation screen, and
`ConsoleUI.run_progress(title, operation)`. Not wired to Start and Continue (that waits for the run lock, TODO §6). It
starts from the stages as `run.json` had them (`operation.data`: run_id, run_dir, stages as plain data, which the
Framework will supply) and follows the §20 events: a stage row is marker, id and state (`running 3/7 mumu 2025` while
a step works), Details the state, message, the local commands (`progress`) and, with Keep checking, "Next check in
07:12" (`wait`); the log is the focused stage's last command log (needs the planned `log` of `progress`). Beside the
list, a box shows the focused stage's facts ("Info: plots": type, config, inputs, channels, output, ...; on a narrow
terminal at the top of the Details instead); the Framework will choose them per stage type at the wiring, the preview
makes them up. The state line says what became of the run (COMPLETE, WAITING FOR JOBS, FAILED, BLOCKED, STOPPED,
LOST), and once the advance ended a result card sits above the list: run complete (start and end time), waiting for
jobs, failed at <stage> (its message, with the log path), stopped during <stage> (n/N commands finished), lost; each
with the full run directory. Three hooks were added to the core for it (the test screen does not use them; it draws
the same): `current()`, the stage the focus follows until the user moves it, `card()` and `info(item)`.

The preview gained seven screens: an advance (live, about 40 s, ends complete), Keep checking with jobs running
(live; the countdown and a check every 15 s), and the result cards (complete, waiting for jobs after Advance once,
failed, stopped, lost). Its made-up operations now write their events with the time of their script, so an ended
run shows real durations. `Tests/Utilities/test_run_screen.py` (new): stages from data and events, rows, Details,
the countdown, every card and state line, the console screen.

### Runs in the menus, in the preview only (2026-10-18)

The menu screens for advances behind the menu, not wired yet (`Framework/python/interactive.py` does not pass
them): `main_menu(runs=...)` shows one advance as a line of its own below Continue, "Run tes_2025 (3/5 plots, 5/7)",
"(1/5 ntuples, waiting for jobs)", "(Failed at plots)", "(Lost - Continue to resume)" (action `run`), several as
"Runs (1 active, 1 ended)" (action `runs`, red if one failed or was lost) with `active_runs()` to choose one;
`select_run(summaries, advances=...)` adds "| advancing: 3/5 plots, 5/7" to the row of a run that advances;
`run_lock(run_id, lock)` explains a held run lock ("An advance of this run is already running on <host> since ...
(pid ...)", Esc) or offers to take over a lost one (T). `run_summary(operation)` (`_run_screen.py`) is the text of
an advance for these menus and for the quit warning. All of these screens are in the preview.

Left for the wiring (with the run lock, TODO §6): which runs the menu passes (running advances, and ended ones until
their card was seen once: a `seen` file in the operation directory), the `run`/`runs` actions, Continue on an
advancing run opening its screen, and the lock record that `run_lock()` shows.

### Operation screens: a TauFW badge in the corner (2026-10-18)

The test and run screens draw a small framed wordmark on rows 0-2 instead of "TauFW V0.0": `+-------+` /
`| TauFW |` / `+-V0.0--+` (`banner.BADGE`, wider for a longer version). The title moves beside it (column 12), the
state line stays on the right of row 1, and one too long for it goes to row 2 beside the badge (was column 1). The
panels still start on row 3, so no screen loses a line; no width rule (9 columns fit every terminal the screen
accepts). `_header(..., badge=True)` draws it; the other menu screens keep the plain header for now. Colors: frame
`accent`, TauFW purple and bold, the version gold (256-color 135 and 178, else magenta and yellow: on an 8-color
terminal the version shares the `warning` yellow); new roles `brand` and `version`, pairs 9 and 10. Only the TauFW
name: no CERN or CMS name or logo. The UI preview frames differ from before on rows 0-2 of the operation screens
only.

### Checked

`Tests/Utilities/test_operations.py` (new): supervisor exit codes, heartbeat, stop, kill, SIGTERM, every state, a real
start; the menu tests follow the new behavior. End to end on Windows: a test run through the supervisor, a refused
second start, a second menu that found it and followed its label to the end. Not checked here: process groups and
signals, curses on a real terminal (TODO §1).

---

## 24. Plotter becomes Histogrammer; a clean Plotter is extracted

**Date:** 2026-10-18
**Status:** done. S0-S4 checked on lxplus (BBB 22/22 without re-lock after every step, real plots identical).

After the drawing moved to `TauFW.Utilities.Drawing` (§12), almost everything left in `Plotter/` produces
histograms: the sample model, normalisation, stitching, the RDataFrame filling, the variable/selection language and
the QCD method. "Plotter" therefore names the module after the one thing it no longer does. The plan: rename the
module to `Histogrammer/` (`plot.py` -> `fillhists.py`, `python/plot/` -> `python/spec/`), keep the old import paths
and the old `plot.py` command as documented compatibility (TODO §8), move its configs to `Configs/Histogrammer/`, and
then extract a small, clean Plotter that draws from a histogram file written by the Histogrammer. **No physics or
data change:** the filling code is moved, not edited, and every step is proven by BBB without re-lock.

### Result

What the analysis code looks like after §24:

```text
pico tuples ──▶ Histogrammer ─────────────▶ hists/<era>/<channel><tag>.root ──▶ Plotter ──────▶ PNG
                fillhists.py --hists          contract                             draw.py
                [--no-draw]: samples,         taufw.control_histograms             draws only
                normalisation, QCD, filling
Framework:      controlhists                  the file is the artifact             controlplots
                (API ControlHists)                                                 (API ControlPlots)
```

- **Proof that nothing changed:** BBB 22/22 without re-lock after S1, S2, S3, S4 (the new case `plotter.stack`,
  locked with the old code in S0, covers plot.py's path and, since S3, the path through the file); real 2025 data:
  the renamed `fillhists.py` and the old `plot.py` give the same PNGs (S1), `--hists` changes no plot and `draw.py`
  draws the same ones (S3: 31 mutau, 19 mumu), the two Framework stages give the PNGs of the old one-step stage
  (S4, reference taken before the change), the file is the same with and without drawing (within the run-to-run
  noise of the multithreaded fill, 1e-13), `taufw.py plan` of `tes_id_2025` unchanged by the stage rename (S4a).
- **Coupling** (`check_import_boundaries`): 30 / 28 / 26 throughout, 0 new pairs. The Plotter imports only
  `TauFW.Utilities` (apart from the 13 compat aliases); the Histogrammer and the Plotter never import each other.
- **Kept on purpose, deleted at the migration point (TODO §8):** the 13 alias modules of the old `TauFW.Plotter.*`
  names, both legacy `plot.py`, `RENAMED_IDS` of `configs.py`, `stages.RETIRED`, `fillhists.py` drawing by default.
- **Registered, not fixed:** Histogrammer BUGS L17 (`m_ll` of the mumu variables), Framework BUGS K08 (the run-root
  message), the flaky `test_background` and the IOInventory generator (TODO §7).
- **Next:** the TES shapes leave the Fitter for the Histogrammer (§25).

### Lock and tools (S0)

- BBB case `plotter.stack` (new, locked with the old code): `plot.py`'s path from samples to drawn stacks (era
  state, the QCD method, drawing), which no case covered. It records the samples, the histograms of each stack, the
  17 attributes the drawing reads from the variable and the drawn canvas.
- `Tests/tools/move_check.py` (new, ROOT-free): compares moved files with their old version in git; a changed line
  must be an import or match an `--allow` pattern, and the functions/classes whose AST differs are listed (AST, not
  bytecode).
- `Tests/tools/roundtrip_spike.py` (new, lxplus, one-off): draws the BBB fixtures (A) from memory as today, (B) after
  writing the histograms to a ROOT file and reading them back, (C) from the file with a plain object holding only the
  drawing attributes instead of the Variable; compares the drawn canvases and the PNG bytes. It checks the two
  assumptions of the extraction before it is designed.

Checked (lxplus, 2026-10-18): the new case was locked (22 cases) and the spike gave 12/12 SAME.

### The rename (S1)

**Date:** 2026-10-18, Windows; checked on lxplus (below).

- `git mv Plotter Histogrammer`; in it `plot.py` -> `fillhists.py` (fills, and until S4 also draws, exactly as
  before; only its header comment, the usage lines and `prog` in `-h` changed), `python/plot/` -> `python/spec/`
  (`Variable`, `Selection`, `Context`, `string`), `MultiDraw.py`/`.cxx` -> `python/sample/` (a filling engine).
  `docs/Plotter/BUGS.md` -> `docs/Histogrammer/BUGS.md` (same IDs).
- Inside the moved code only these lines changed: the `TauFW.Plotter.*` imports, the two `GLOB` imports of the
  module state, the package of the method modules (`ensuremodule(method,'Histogrammer.methods')`), and docstrings
  that name paths. `Tests/tools/move_check.py` over the 25 moved Python files: every changed line is an import or
  one of those lines.
- The Framework uses `TauFW.Histogrammer.api` (no alias for the old API name: only the Framework used it); recipes,
  stage names and `run.json` are unchanged by this step.
- **Backward compatibility (TODO §8):** a new `Plotter/` holds the 13 old module names
  (`python/sample/*`, `python/plot/*`, `python/methods/QCD_OSSS.py`). Each is
  `import <new module> as _module; sys.modules[__name__] = _module`: the old name is the very same module object,
  so `setera` through either name changes the same era and luminosity (a star re-export would freeze them). No alias
  for `TauFW.Plotter.plot.datacard` (it would repair `Fitter/MuTauFR/createinputs.py`). `Plotter/plot.py` and
  `Histogrammer/plot.py` print the new command (same arguments, path relative to the working directory) and exit
  with status 2; they run nothing. `Plotter/README.md` describes the coming drawing-only Plotter and its rules.
- Paths: the 6 Fitter `createinputs*.py` find `config.samples*` in `Histogrammer/`, `Fitter/Zpt` loads
  `Histogrammer/python/macros/Unroll.cxx`, `Fitter/HighPT` writes and reads `Histogrammer/data/ff_HighPT/`;
  `Utilities.Paths` gets `HISTOGRAMMER_ROOT`/`HISTOGRAMMER_DATA_DIR` (the `PLOTTER_*` names stay); `FastSetup.sh`
  also verifies `TauFW.Histogrammer`; `.gitignore` ignores `Histogrammer/plots`. `Configs/Plotter/` is unchanged
  (moved in S2).
- Import boundaries: `Histogrammer` is a stage of `Tests/check_import_boundaries.py` (a new detector test: the
  Histogrammer and the Plotter never import each other, the Framework may import only `TauFW.Histogrammer.api`,
  the Fitter not the Histogrammer). The 13 aliases are new allowlist entries, removed at the migration point; the
  6 Fitter `config.samples*` imports now count as Fitter -> Histogrammer (the same debt at a new address, removed in
  §25). Totals 30 / 28 / 26 (17 / 15 / 13 before + the 13 aliases), 0 new pairs. **No cross-stage import was removed
  by this step**; it prepares §25.
- Tests: the Plotter unit tests moved to `Tests/Histogrammer/`; a new compat suite checks that each alias is the
  very same module object as its new name. BBB cases changed only their import lines and paths; their names stay
  `plotter.*`. The old scripts in `Tests/Plotter/` keep the old names, so they exercise the aliases.

Checked (lxplus, 2026-10-18): `bbb check` 22/22 without re-lock; `checks`; the old scripts `plotter.unroll`,
`plotter.samples` through the aliases; `fillhists.py` against the old `plot.py` on the 2025 tuples (mutau, two
variables): the 4 PNG files byte-identical, the logs equal except the ACLiC line of `mapDecayModes.C` in its new
directory and the timing; `Plotter/plot.py` prints the new command and exits with 2.

### Configs to Configs/Histogrammer/ (S2)

**Date:** 2026-10-18, Windows; the lxplus checks are in TODO §1.

The Plotter's config templates belong to the Histogrammer (they say which samples to fill and which selections), and
a template's id must start with its module directory (§21). The new Plotter has no user config: drawing needs
only command-line options and the histogram file.

- `git mv Configs/Plotter Configs/Histogrammer`: 8 sample model templates (`samples/v15_<era>.yml`) and 7 channel
  setups (`setups/setup_<channel>.yml`). In each header only the id changed (`plotter.*` -> `histogrammer.*`; a setup's
  description now says `fillhists.py`), and the comments that name paths. `taufw.py configs update`: the 15 new ids
  are locked with version 1 and **the same content hashes** as before (the values are unchanged); the 15 old ids left
  the lock. The bundle copies (`Analyses/tes_id_2025/`: `v15_2025.yml`, `setup_mutau.yml`, `setup_mumu.yml`;
  `Analyses/example_mutau_long/`: `v15_2022_postEE.yml`, `setup_mutau.yml`) got the new ids.
- **Backward compatibility (TODO §8):** `RENAMED_IDS` and `renamed_id()` in `Framework/python/configs.py`. A copy whose
  id is a renamed one (an analyst's bundle made before S2) is compared with the renamed template; `check`, `plan` and
  `start` warn "copy of plotter.X, which was renamed histogrammer.X (...): change the id in the copy's taufw_config
  header" (and still warn when the template is newer), instead of "not in Configs/ any more".
- Paths: `fillhists.py`, `plot_postfit*.py`, `plot_v10.py`, the API and `export.py` read and write the new
  directory. The BBB case `plotter.sample_model` reads the templates from there (its payload does not contain the
  path).

Checked (lxplus, 2026-10-18): `bbb check` 22/22 without re-lock; `checks`; `taufw.py configs` lists the 15
`histogrammer.*` templates (lock ok); `check`/`plan` of the two bundles without copy warnings; a copy of
`tes_id_2025` with the old ids gets exactly the three rename warnings; `fillhists.py -c mutau` with the moved setup
and sample file gives the 4 reference PNG files byte for byte.

### The histogram file and draw.py (S3)

**Date:** 2026-10-18, Windows; the lxplus checks are in TODO §1. Rule of this step: **nothing that exists changes**;
everything new is opt-in, and its output is compared with the old one.

The Histogrammer can now write the histograms it fills to a file, and the new Plotter draws the control plots from
that file, giving the same plots. The S0 spike showed both assumptions (a ROOT file round trip and the 17 drawing
attributes in place of the Variable) give byte-identical canvases and PNG files.

- `TauFW.Utilities.HistFile` (new): `write_histfile`, `read_histfile`, `HistFileEntry`, `HistFile`. Ordered groups of
  histograms plus JSON metadata in one ROOT file (a `taufw_histfile` JSON header in the file and in each entry
  directory, every histogram under its own name). Writing checks everything first and leaves ROOT's current
  directory as it was; reading returns detached copies. The shared format lets the two modules exchange histograms
  without importing each other.
- `TauFW.Histogrammer.controlhists` (new): `stack_entry(stack, variable, selection)` copies a stack's histograms
  **as filled** (right after `getstack`, before `draw()` changes them; the copy is never added to ROOT's current
  directory, so it cannot displace the original) with the selection and the 17 drawing attributes of the variable;
  `write_control_hists` writes them (contract `taufw.control_histograms` version 1,
  [docs/contracts/control-histograms.md](../contracts/control-histograms.md)).
- `Histogrammer/fillhists.py --hists` (new option): also writes `hists/<era>/<channel><tag>.root`. Without the
  option nothing changes: the only edits to existing lines are the new keyword `histfile=None` of `plot()` and its
  docstring and the argument passed to it; the copies are taken before the unchanged draw calls.
- The new Plotter's first code: `TauFW.Plotter.controlplots` (`read_control_hists`, `draw_control_plots`,
  `make_stack`, `draw_stack`, `plot_name`, `plot_text`, `DrawingVariable`) and `Plotter/draw.py FILE [...]
  [-o OUTDIR] [-F] [-p] [-T TEXT] [-v]`. The plot file names and texts follow plot.py's rules character for
  character (a test compares them with plot.py's two lines); the CMS label is set from the file's era. It imports only
  `TauFW.Utilities`.
- BBB `plotter.stack` now fills, writes the file, reads it and draws with the Plotter's code; its payload must equal
  the S0 lock (canvases, histograms, drawing attributes, file names). New unit suites cover the histogram file, the
  copies taken by the Histogrammer and the Plotter's names and texts.
- Not changed: `plot_postfit*.py`, `plot_v10.py` and the tutorial keep filling and drawing in one script (TODO §6);
  the Framework (S4).

Checked (lxplus, 2026-10-18): `bbb check` 22/22 without re-lock; on real data `--hists` changes no plot and
`draw.py` draws the same ones (mutau 31, mumu 19; mumu without `m_ll`, which fails with and without `--hists`: L17).
Fixed on the way: the HistFile writer wrote entries into the parent directory (ROOT's `mkdir("a/b")` returns `a`).

### The histograms stage becomes shapes (S4a)

**Date:** 2026-10-18, Windows. Rule of S4: recipes and Framework stages have no users yet, so they take the clean
design without a compatibility layer; commands run by hand keep their behaviour.

Every stage is now named after what it makes. The stage that runs `createinputsTES.py` made `kind: shapes` but was
called `histograms`, and S4 adds a second stage that fills histograms (the control histograms): two names with
"histograms" in them would not say which is which. Rename only; the commands and the shapes are the same.

- `Framework/python/stages/histograms.py` -> `stages/shapes.py` (`git mv`); `HistogramStage` -> `ShapesStage`,
  `HistogramSpec` -> `ShapesSpec`, stage name `shapes`; `STAGES`, `ORDER`, `Framework.from_recipe`, the docstrings
  of the Framework, `taufw.py` and the stage messages ("connect inputs.shapes to a shapes stage", "run the shapes
  stage first" of the Fitter API).
- New `TauFW.Framework.stages.RETIRED` (old name -> what replaces it): a recipe that still writes
  `stage: histograms` fails the check with `stage 'histograms' no longer exists: renamed 'shapes' (CL §24)`; it runs
  nothing. **Runs started before this change** (their `run.json` names `histograms`) can no longer be continued or
  shown with `status`/`advance`; start them again.
- `Analyses/tes_id_2025/recipe.yml`: `stage: shapes`, `id: shapes` (its directory in a run is now
  `stages/shapes/`), `fit` reads `inputs: {shapes: shapes}`.

Checked (lxplus, 2026-10-18): `taufw.py plan Analyses/tes_id_2025` before and after (shapes, fit and python
part): every command, input and directory equal once `histograms` reads `shapes`; only the width of the table's
separator line differs (it was computed from the longer old paths).

### Control plots as two Framework stages (S4)

**Date:** 2026-10-18, Windows. The Framework now makes control plots in two stages, each through the API of its own
module, and carries the control-histogram file between them; the Histogrammer never draws in a run, the Plotter never
fills, and neither imports the other.

```text
tuples ──[controlhists: Histogrammer API, fillhists.py --hists --no-draw]──▶ hists/<era>/<channel><tag>.root
       ──[controlplots: Plotter API, draw.py]──▶ plots/<era>/*.png   (the same files as fillhists.py draws)
```

- `Histogrammer/fillhists.py --no-draw` (new, only with `--hists`, else an error): writes the file, draws nothing,
  makes no `plots/` directory; `-F`/`-p`/`-T` are then ignored with a warning. Without it nothing changes: a command
  typed by hand fills and draws as before (the default changes at the migration point, TODO §8). The copies in the
  file are taken before drawing (S3), so the file is the same with and without drawing.
- Histogrammer API: `ControlPlots` -> `ControlHists`, `PlotsRequest` -> `HistsRequest` (`git mv
  api/control_plots.py api/control_hists.py`), renamed in place (no shim: only the Framework used it). The command
  ends in `--hists --no-draw`, the drawing options are gone (they are the Plotter's), the command is labelled
  `controlhists <channel> <era>` and expects `hists/<era>/<channel><tag>.root`; the artifact is
  `{kind: control_histograms, era, config, channel, tag, file}`. The sample functions are unchanged (they also serve
  the shapes stage).
- Plotter API (new, `Plotter/python/api/`): `ControlPlots`, `PlotsRequest(files, fraction, pdf, text, timeout,
  outdir)`, `HistFileInput(path, era, channel, config, tag)` (`from_artifact` takes the Histogrammer's artifact). One
  `draw.py FILE [-F] [-p] [-T TEXT]` per file, labelled `controlplots <channel> <era>`; it expects the plot names of
  `TauFW.Plotter.controlplots.plot_name`; artifact `{kind: plots, era, config, channel, directory, nfiles}`, the form
  of the old plots stage. It imports only `TauFW.Utilities` and the Plotter; no ROOT.
- Framework: `stages/plots.py` -> `stages/controlhists.py` (`ControlHistsStage`, `ControlHistsSpec`: eras, configs,
  variables, selections, serial, notauidsf, tag, timeout, samples; outputs `control_histograms`), new
  `stages/controlplots.py` (`ControlPlotsStage`, `ControlPlotsSpec`: fraction, pdf, text, timeout; input slot
  `hists <- control_histograms`, never null; outputs `plots`). It draws every file of its input (in a plan the
  planned files `<run_dir>/stages/<id>/hists/...`); an input from another run (`{path: ...}`) works through the
  general mechanism. `STAGES`, `ORDER` (production, controlhists, controlplots, shapes, fit),
  `Framework.from_recipe(..., histogrammer=, plotter=)` (`plotter` was the Histogrammer's API until now), the
  `samples_api` of the shapes stage is `ControlHists`. **The one-step `plots` stage is removed** (no recipe users
  yet): `stage: plots` fails the check with "control plots are two stages now: controlhists (tuples
  -> histogram files) and controlplots (files -> plots)" (`stages.RETIRED`). Runs started before this change cannot
  be continued.
- Bundles: `tes_id_2025`, `example_mutau_long` (`controlhists` id `hists`, `controlplots` id `plots`, so the plots
  stay in `stages/plots/plots/<era>/`), `example_broken` (its error 3 now names `controlhists`).
- Boundary: no new import edge (Framework -> `TauFW.Plotter.api` is an API); `Tests/Histogrammer/compat` now allows
  `TauFW.Plotter.api` as long as it imports nothing of the Histogrammer (it is the new Plotter's own API, not an
  alias of the old one).
- Tests: a new suite for the Plotter API, the Histogrammer API test follows the rename, the Framework tests use a
  fake Histogrammer and a fake Plotter; `Tests/tools/compare_histfiles.py` compares two histogram files entry by
  entry (for the lxplus check).
- Not changed: the legacy `plot.py` messages (`fillhists.py` is still one command), the BBB cases, the old variants
  (`plot_postfit*`, `plot_v10`, tutorial).

Checked (lxplus, 2026-10-18): `bbb check` 22/22 without re-lock. Against a reference taken with the old one-step
`plots` stage on a copy of `tes_id_2025`, the two stages give every PNG equal (31 mutau, 19 mumu). The file of
`--hists --no-draw` equals that of `--hists` within the run-to-run noise of the multithreaded fill (~1e-13).
`.gitignore` needed `!Plotter/python/api/__init__.py`, else the API would not import on lxplus.

### Review fixes of §24

**Date:** 2026-10-18, Windows, after the split. A code review of `8a3531a..e713f16` (rename, aliases, config ids,
histogram file, stages, tests, docs) found nothing broken; these fixes of what the split itself introduced. No filling
or drawing code changed; a file that was written before is written the same.

- **Two `__init__.py` lost in S1:** `Plotter/config/__init__.py` (empty) and `Plotter/python/plot/__init__.py`
  (`moddir`) were tracked although `.gitignore` ignores `__init__.py`; `git mv` put them under ignored names, so in a
  clone `config` became a namespace package (merged with every `config/` directory on `sys.path`, e.g. the
  YAML-only `Fitter/TauES/config/` next to the Fitter scripts). `.gitignore` now whitelists
  `Histogrammer/config/__init__.py` and `Histogrammer/python/spec/__init__.py`, and both are tracked again, as before
  §24.
- `TauFW.Utilities.HistFile` refuses on writing what it could not read back: `taufw_histfile` as any part of an
  entry path (it was checked only as the whole path), a histogram whose name is also the directory of another entry
  (`baseline` holding `m_vis` next to the entry `baseline/m_vis`), an object that is not a histogram (a TGraph could
  be written but not read detached). Reading a header without its keys raises `HistFileError` instead of `KeyError`.
- `TauFW.Plotter.controlplots.read_control_hists`: missing metadata (`channel`, `era`, `tag`, an entry's
  `selection`/`variable`, the selection's `name`/`title`/`cut`) raises `ControlHistsError` naming it.
- `TauFW.Histogrammer.controlhists.write_control_hists`: two variables with the same file name in one selection are
  refused with both names (before, the HistFile writer refused the duplicate entry path with a less direct message;
  the plain `fillhists.py` overwrites the first PNG, unchanged).
- Tests: the refusals above; a run whose `run.json` names a retired stage (`plots`, `histograms`) is refused by
  `Framework.from_record` with the recipe error that `taufw.py status`/`advance` print.

Checked (lxplus): `bbb check` 22/22 without re-lock, `checks`.

## 25. TES shapes leave the Fitter for the Histogrammer (in progress)

**Date:** 2026-10-18
**Status:** H0 (lock `f3079fa`), H1, H2 and H3 (`63f299c`) done and checked on lxplus; H4 (real-data comparison) to
come.

The next step of the module isolation: the code that fills the TES/ID input histograms
(`Fitter/TauES/createinputsTES.py`, `Fitter/python/plot/datacard.py`, `rebinning.py`) imports nothing of the fit;
it moves to the Histogrammer, the Framework's `shapes` stage gets a Histogrammer API, and the four maintained channel
configs move to `Configs/Fitter/tes_id/`. Decisions: one config per channel with a written key contract, its keys
grouped under banners by reader; the code goes to `Histogrammer/python/shapes/{inputs,rebinning}.py` and the scripts
to `Histogrammer/shapes/<Variant>/`; a `TESShapes` API, recipe unchanged; run scripts keep their working directory,
legacy stubs at the old script paths print the new command; recipes naming the old config paths fail with a
message, no name map; `Fitter/MuTauFR/createinputs.py` stays; what is out of scope is listed in TODO §0. Same method
as before: lock with the old code first, move byte for byte, prove equality.

### Lock and contract (H0)

- BBB case `histogrammer.tes_inputs` (new, locked on lxplus with the old script): runs `createinputsTES.py` end to
  end in its own interpreter, on fixture tuples of a mini sample model (with TES and LTF variation tuples) and a mini
  config that uses every config feature the script reads (regions, binning, TES points, shape and `lnN`
  systematics). It records the shape file, the rebinned file and the names of the PNG files, never the script's
  output text. The fixture rows are written 100 times per tuple so that every region has events (a first lock
  attempt with the bare 16 rows found L22). Not covered: the working-point substitution (no `idDeepTau*` branches).
- `docs/contracts/tes-shapes.md` (new): the shape file name (today defined in four places), what is inside and what
  the fit reads, the config keys each side reads, the variation tuples.
- Bugs registered, not fixed: Histogrammer BUGS L18-L21 (`createinputsTES.py`: control plots only with
  `systematics`, `varprocs` only for mutau/mumu, shape files never recreated, rebinning of the first observable only;
  they go to the Histogrammer with the script in H1), L22-L24 (`rebinning` stops on a
  region without a bin under 30 % relative error, its error accumulation, the doubled tag in the plot names), Fitter
  BUGS F26 (option 6 reads `tidRegions`).

### The move (H1)

**Date:** 2026-10-18, Windows; the lxplus checks are in TODO §1 (after the H0 lock).

- `git mv` (bodies unchanged): `Fitter/python/plot/datacard.py` -> `Histogrammer/python/shapes/inputs.py`
  (`TauFW.Histogrammer.shapes.inputs`), `Fitter/python/plot/rebinning.py` -> `Histogrammer/python/shapes/rebinning.py`,
  `Fitter/TauES/createinputsTES.py` -> `Histogrammer/shapes/TauES/`, `Fitter/{ETauFR,HighPT,paper,tutorial}/createinputs.py`
  -> `Histogrammer/shapes/<Variant>/`. Changed lines: the import of the writer and of `rebinning`, and in
  `createinputsTES.py` the `sys.path` line that finds `Histogrammer/` from `__file__` (now two directories up).
  `Tests/tools/move_check.py` over the seven files: only those lines, no function or class whose AST differs (HighPT:
  Python 2, line diff only). New package `__init__.py`, whitelisted in `.gitignore`.
- **Working directories unchanged:** `Fitter/run_inputs.sh`, `run_inputs_2526.sh`, `run_inputs_pnet.sh` call
  `python3 ../Histogrammer/shapes/TauES/createinputsTES.py` from `Fitter/`, so the shapes still land in
  `Fitter/input_pt_less_region/` where `run_workflow_zmm*.sh` reads them; the variants run from `Fitter/<Variant>/`,
  where their `sys.path` lines and configs are relative to.
- **Backward compatibility (TODO §8):** the five old paths are LEGACY stubs (as the legacy `plot.py` of §24): they
  print the new command with the same arguments, relative to the working directory, and exit with status 2; they
  import and run nothing. No alias for `TauFW.Fitter.plot.datacard`/`.rebinning`: it would be a Fitter -> Histogrammer
  import. `Fitter/MuTauFR/createinputs.py` stays.
- Until H3 the Fitter API ran the moved script by path (no import).
- BBB: `_tes_inputs_script()` names the new path; `fitter.shapes`/`fitter.rebin` import `TauFW.Histogrammer.shapes`.
  The payloads must equal the lock (no re-lock).
- Import boundaries: the five `config.samples*` entries of the moved scripts left the allowlist (they now import the
  Histogrammer's own `config/`), the HighPT unparseable entry follows the file. `check_import_boundaries.py` now also
  looks for an implicit `config.*`/`plot.*`/`sample.*` module in the importing module's own directory (a script in
  `Histogrammer/shapes/TauES/` importing `Histogrammer/config/samples_v15.py` is not a cross-stage import; a detector
  test covers it, and an import that is found nowhere is still reported). Totals 25 / 23 / 21 (30 / 28 / 26 before),
  0 new pairs: Fitter -> Histogrammer 6 -> 1 (MuTauFR's), Fitter -> Plotter unchanged (9 / 8 / 7).
- Tests: a new compat test checks that the stubs import nothing, print the new command and exit with 2.

Checked (lxplus, 2026-10-18): after `scram b` the new package imports; `bbb check` 23/23 without re-lock (the
case runs the moved script, `fitter.shapes`/`fitter.rebin` import `TauFW.Histogrammer.shapes`: the same payloads as
the lock taken with the old code); `checks` 14/15 (`check_import_boundaries`: known debt, 25 / 23 / 21, 0 new
pairs); the old path prints the new command and exits with 2; `taufw.py plan Analyses/tes_id_2025` runs
`Histogrammer/shapes/TauES/createinputsTES.py`. The lock commit (`f3079fa`) comes after the H1 commit in the
history, so the old code was run once more against it: the three cases of the moved code 3/3 the same.
What the case does not cover (accepted): `ZL`/`TTL`, so the content of the
LTF shape systematics, are zero in every region of the fixture (no opposite-sign event with `genmatch_2` 1-4 passes
the baseline); the LTF variation files are read. The real-shape comparison of H4 covers them; TODO §7 notes the
extension for the next legitimate re-lock.

### Channel configs to Configs/ (H2)

**Date:** 2026-10-18, Windows; the lxplus checks are in TODO §1.

- `git mv` the four maintained configs to `Configs/Fitter/tes_id/`: `config_coarse_TT.yml`, `config_coarse_PNet.yml`,
  `config_coarse_UParT.yml` (from `Fitter/TauES_ID/config/`), `FitSetup_mumu.yml` (from `Fitter/TauES/config/`).
  File names kept; ids `fitter.tes_id_coarse_tt`, `fitter.tes_id_coarse_pnet`, `fitter.tes_id_coarse_upart`,
  `fitter.tes_id_mumu` (ids are lower case, `configs.py`), version 1, locked (`configs.lock`).
- **Values unchanged:** each file got the `taufw_config` header, and its top-level keys are grouped under four
  banners by reader: both read / Histogrammer only / Fitter only / not read (`fitSpecs`). The YAML anchor
  `&region_list` moved from `plottingOrder` (now `*region_list`, Fitter group) to `observables.m_vis.fitRegions`
  (shared group, where it is first used). `yaml.safe_load` of every new file without the header equals the old
  file's (checked for all four); comments moved with their keys. The bundle copies of `tes_id_2025` were byte copies
  of the old templates and are now byte copies of the new ones.
- **`Configs/` templates in recipes:** a path option starting with `Configs/` that is not a
  bundle file names a template; the Framework resolves it against the TauFW directory and gives the stage's API the
  absolute path (`bundle.py`, kind `template`, shown by `plan`). The same rule for every stage, so after H3 the
  Histogrammer reads a Fitter template without knowing `Fitter/`. `taufw.py init --from` copies the templates a
  recipe names into the new bundle; `check` reports a template that does not exist.
- **No recipe compat:** `stages.MOVED_CONFIGS` maps the four old module paths to their templates; a recipe naming
  an old path fails (in `check`, `plan` and `start`, a Recipe error) with "... moved to Configs/Fitter/tes_id/... (CL
  §25): name the template, or a copy of it in the bundle". A bundle file with that relative path is the bundle's.
- Defaults: `DEFAULT_CONFIGS` of the `shapes` and `fit` stages are the two templates. Commands run by hand: the run
  scripts (`run_inputs*.sh`, `run_workflow_zmm*.sh`) and the default `-c` of `plot2DScan_MultiDimFit.py` and
  `makecombinedfitTES_SF_postfit_corrTES.py` name `../Configs/Fitter/tes_id/...` (the same files from `Fitter/`); a
  hand-typed old path is "file not found" (`scripts_arg_changes.md`). The fit scripts only open the path and pass it
  on (no output name is derived from it), so the outputs do not change.
- Contract test: `READERS['fitter.tes_id_']` in `Tests/Framework/test_configs.py` (`read_tes_id`): every
  template has the keys its two readers take without a default (channel, tag, baselineCuts, samples.filename/join/
  data, observables with binning and fit regions that exist, processes, systematics with their fields, regions with
  definition and title, TES variations with values and processes); a mutated copy is refused.
- Tests: template resolution in bundles (a bundle file wins, `init` copies a template), the missing-template and
  moved-path errors, the default configs.

Checked (lxplus, 2026-10-18): `bbb check` 23/23 without re-lock; `checks` 14/15 (known import debt); `taufw.py
configs` lists the four `fitter.tes_id_*` templates, lock ok; `taufw.py plan Analyses/tes_id_2025` unchanged by the
pull (`diff` empty).

### TES shapes API to the Histogrammer (H3)

**Date:** 2026-10-18, Windows; the lxplus checks are in TODO §1. Decisions: D3 (plan 16 §13), and E1, E2 of this step
(user, 2026-10-18, both option a).

- New `Histogrammer/python/api/tes_shapes.py`: `TESShapes` with `plan_shapes`, `make_shapes`, `preflight_shapes`,
  `shapes_request`, `config_file`, `pico_config_source`: the shapes half of the Fitter API (`TauESID`), moved with
  the same command building (the `run_inputs.sh` order, labels, `-s`, `--tuples`, `--samples`, `$TAUFW_PICO_CONFIG`),
  the same shape file names (`_shape_files`, the contract rule) and the same artifacts; the script is its own module's
  `shapes/TauES/createinputsTES.py` (no `../Histogrammer` path). It reuses `ControlHists`' module helpers
  (`_pico_env`, `_module_exists`, `_default_basedir`, `_read_yaml`). Configs are relative to `Histogrammer/` or
  absolute (`../Configs/...` names the same templates as from `Fitter/`).
- `ShapesRequest` moved to `Histogrammer/python/api/types.py` (same fields); exported from `TauFW.Histogrammer.api`.
- **`outdir` is required (E1, user: option a):** a `ShapesRequest` without it is a `ValueError` naming the two ways
  (the Framework's stage directory, or `Fitter/run_inputs.sh` by hand). So the Histogrammer never writes into or names
  `Fitter/`, and the "without an output directory, relative script and configs" branch is gone. By hand nothing
  changes: `run_inputs.sh` still runs the script from `Fitter/`. What is lost: making shapes into `Fitter/` from
  Python through the API (only the README example did).
- `Fitter/python/api/tes_id.py` keeps only the fit: the shapes pipelines, `_shape_command`, `_shape_files` and
  `SHAPES_SCRIPT` are deleted; `INPUTS`, `_wp_dir` and the preflight glob stay (the fit reads by the contract).
  Fitter `types.py` keeps `FitRequest`. No shim (only the Framework used the shapes half). `grep Histogrammer
  Fitter/python` finds nothing.
- Framework: `Framework.from_recipe(..., tes_shapes=None)` (and `from_record`) builds `ShapesStage(TESShapes(),
  samples_api=ControlHists())`, so each stage talks to one module's API; `fitter` is the fit stage's only.
- **Module-relative configs of the shapes stage (E2, user: option a):** `ShapesSpec._no_module_paths = ('configs',)`;
  `recipe.py` `_check_module_paths` makes such a path a Recipe error in `check`, `plan` and `start`: "<path> is not a
  file of the bundle or a Configs/ template: copy it into the bundle (or give an absolute path)". The old paths of
  `stages.MOVED_CONFIGS` keep their own message. The fit stage still takes module paths (the Fitter API resolves them
  against `Fitter/`). No recipe in the repository is affected (`tes_id_2025` names bundle copies).
- Tests: the shapes tests of `Tests/Fitter/api/test_tes_id.py` moved to `Tests/Histogrammer/api/test_tes_shapes.py`
  (suite `unit.histogrammer.api`; with `outdir`, the commands of `run_inputs.sh` with absolute script and configs, and
  the new `outdir` error); the Fitter file keeps the fit tests and checks that no shapes method is left;
  `Tests/Framework/fakes.py` `FakeTESShapes` (the shapes methods of `FakeFitter`); `test_bundle.py`: the E2 error, a
  plain recipe file with an absolute config, recipes without a bundle use a template.
- Equality: the plan of the `tes_id_2025` shapes request (bundle configs, sample file, tuple pattern, output directory)
  from the old `TauESID.plan_shapes` (HEAD) and the new `TESShapes.plan_shapes` is the same (commands, argv, working
  directory, expected files, environment, artifacts; JSON `diff` empty, Windows).
- Docs: READMEs (Histogrammer API section and old names, Fitter API section, Framework stage diagram, Analyses
  `shapes` stage and path rule), the contract (where `_shape_files` is), the docstrings of the `shapes` stage, the
  Fitter and Histogrammer API packages, `validation.py`; IOInventory rows; TODO §1, §8.

Checked (Windows): `python Tests/run.py checks`: 13 of 15 suites pass (`unit.histogrammer.api` 23 tests,
`unit.fitter.api` 14, `unit.framework`); `check_import_boundaries` unchanged (25 / 23 / 21, 0 new pairs: the
Framework imports `TauFW.Histogrammer.api` as before), `check_root` needs ROOT.

Checked (lxplus, 2026-10-18): `bbb check` 23/23 without re-lock; `checks` 14/15 (known import debt, 25 / 23 / 21);
`taufw.py plan Analyses/tes_id_2025` the same before H3 (`1e4eb77`), after it (`63f299c`) and at `e64dfe5` (`diff`
empty, 77 lines; the shapes stage runs `Histogrammer/shapes/TauES/createinputsTES.py`); `grep -rn Histogrammer
Fitter/python` finds nothing.

### Real-data comparison (H4, in progress)

- `Tests/tools/compare_shapefiles.py DIR_A DIR_B [--rtol] [--atol]` (new): two output directories of
  `createinputsTES.py` (stage directories, or `Fitter/` after `run_inputs.sh`): the same file names on both sides
  (the run's `manifest.json` skipped; PNG and other files by name), each `.root` file as the BBB case
  `histogrammer.tes_inputs` sees it (`_tes_file_snapshot`: directories and keys by name, cycle and class, histograms in
  full, TNamed titles, TCanvas/TStyle by key and class), keys matched by name; the summary gives per histogram family
  (nominal, TES points, LTF `shape_mTauFake`, JTF `shape_jTauFake`) the count, how many have content and the largest
  relative difference, so the LTF shapes that the BBB fixture leaves empty (TODO §7) are seen to be compared. The
  logic is ROOT-free and tested (`Tests/tools/test_compare_shapefiles.py`, suite `unit.tools`).
- Plan (lxplus, TODO §1): one run of a shapes-only recipe with the code before H1 (`0c611f4`, a second CMSSW area:
  a `git worktree` cannot run it, the old script imports `TauFW.Fitter.plot.datacard`, which the area's `TauFW`
  package no longer has) and two with HEAD (their difference is the noise of the multithreaded fill; the script is
  byte-identical, so the noise is the same for both codes); the same tuples, configs and sample file for all three.
