# Refactor-2025: change log

**Author:** Yagizhan Dinckurt (yagizdkurt), October 2026
**Branch:** `Refactor-2025`
**Last updated:** 2026-10-18

This document records the changes made on the `Refactor-2025` branch: what changed and why.
What is still open is listed in [TODO.md](TODO.md). Other documents cite its sections as "CL §N" (or "changelog §N").
Plans named `LocalR/architecture/...` are local, Git-ignored notes; the decisions needed to read a section are
restated in it.

| # | Change |
| --- | --- |
| 1 | [Test migration and BBB regression tests](#1-test-migration-and-bbb-regression-tests) |
| 2 | [FastSetup script](#2-fastsetup-script) |
| 3 | [Removal of legacy Python 2 scripts](#3-removal-of-legacy-python-2-scripts) |
| 4 | [Utilities package for future development](#4-utilities-package-for-future-development) |
| 5 | [PicoProducer cleanup, Part 1: command-level BBB tests and bug register](#5-picoproducer-cleanup-part-1-command-level-bbb-tests-and-bug-register) |
| 6 | [PicoProducer cleanup, Part 3: settings, datasets, storage, batch and jobs packages](#6-picoproducer-cleanup-part-3-settings-datasets-storage-batch-and-jobs-packages) |
| 7 | [PicoProducer cleanup, Part 4: jobs package](#7-picoproducer-cleanup-part-4-jobs-package) |
| 8 | [PicoProducer cleanup, Part 5: public API, command line, workers](#8-picoproducer-cleanup-part-5-public-api-command-line-workers) |
| 9 | [Framework: the TauFW orchestrator (Part F)](#9-framework-the-taufw-orchestrator-part-f) |
| 10 | [Framework: plots, histograms and fit stages (Part G)](#10-framework-plots-histograms-and-fit-stages-part-g) |
| 11 | [Framework: analysis bundles and Python steps (Part H)](#11-framework-analysis-bundles-and-python-steps-part-h) |
| 12 | [Shared code moved to Utilities](#12-shared-code-moved-to-utilities) |
| 13 | [Import-boundary test and coupling inventory](#13-import-boundary-test-and-coupling-inventory) |
| 14 | [Fitter imports drawing helpers from their own home](#14-fitter-imports-drawing-helpers-from-their-own-home) |
| 15 | [Framework: explicit stage ids, inputs and recipe validation (R1)](#15-framework-explicit-stage-ids-inputs-and-recipe-validation-r1) |
| 16 | [Framework: run directory with logs/ and stages/, stage manifests (R2)](#16-framework-run-directory-with-logs-and-stages-stage-manifests-r2) |
| 17 | [Framework: Plotter and Fitter outputs in the run directory (R3)](#17-framework-plotter-and-fitter-outputs-in-the-run-directory-r3) |
| 18 | [Framework: tuples as an input, production writes into the run, run_root](#18-framework-tuples-as-an-input-production-writes-into-the-run-run_root) |
| 19 | [Framework: inputs from another run's stage directory, repeated stages (R4)](#19-framework-inputs-from-another-runs-stage-directory-repeated-stages-r4) |
| 20 | [Menu: commands run beside the screen; the test screen; Framework events](#20-menu-commands-run-beside-the-screen-the-test-screen-framework-events) |
| 21 | [Configs: config templates with an id, a version and a lock](#21-configs-config-templates-with-an-id-a-version-and-a-lock) |
| 22 | [Sample lists as data: the sample model](#22-sample-lists-as-data-the-sample-model) |
| 23 | [Menu: operations run behind the menu](#23-menu-operations-run-behind-the-menu) |
| 24 | [Plotter becomes Histogrammer; a clean Plotter is extracted](#24-plotter-becomes-histogrammer-a-clean-plotter-is-extracted) |

The reference environment for all of this is `CMSSW_14_1_0_pre4` (Python 3.9, ROOT 6.30).

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
All deleted files remain in Git history.

### Still to do

Python 3 migration and stale README references are tracked in [TODO.md](TODO.md).
Priority migrations include `Fitter/ETauFR/writedatacard.py` and the Zpt helpers imported by `measureZpt*.py`.
Later sections record subsequent archival and removal of other retained scripts.

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

## 5. PicoProducer cleanup, Part 1: command-level BBB tests and bug register

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

The five cases were locked on lxplus together with the 13 existing ones (§6, re-lock `c2d8296`). Still open: a
`ModuleTauPair` channel case before the analysis/corrections cleanup (TODO §5, "Blocking for Part 6").

---

## 6. PicoProducer cleanup, Part 3: settings, datasets, storage, batch and jobs packages

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
| `TauFW.Plotter.plot.MultiThread.MultiProcessor(max=...)` | `TauFW.Utilities.Process.ParallelProcessor(max_parallel=...)` (§12) |
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

## 7. PicoProducer cleanup, Part 4: jobs package

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

## 8. PicoProducer cleanup, Part 5: public API, command line, workers

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
`-E/--opts`). `pico.run`/`pico.jobs` were re-locked with Part 4's P08–P10; the only further difference is P12's
`--opt` → `--opts`.

---

## 9. Framework: the TauFW orchestrator (Part F)

**Date:** 2026-10-13
**Details:** [Framework/README.md](../../Framework/README.md)

Added `TauFW.Framework` to run recipe-based pipelines with persisted state, replacing manually chained
PicoProducer, Plotter and Fitter commands.

### What changed

- **Framework:** `plan`, `start`, `advance`, `run`, `status` build stage requests and decide when to wait,
  resubmit or continue. Construction is read-only; waiting is explicit (`advance(wait=True)`).
- **Stages:** shared `Stage`/`StageOutcome` contracts and states NEW → SUBMITTED → WAITING → MERGING → DONE,
  plus FAILED/NOT_IMPLEMENTED. Production uses only the public PicoProducer API; pure `decide_next` selects
  wait/resubmit/merge/fail with `max_tries`. Histograms and fit initially have placeholder contracts (implemented in §10).
- **Run record:** `taufw_runs/<name>_<time>/run.json` (schema 1) stores the recipe/config snapshot and each stage's
  state, attempts, requests, submissions, status, artifacts and history. Saved atomically after every stage step.
  (The layout changed in §16, the schema in §16 and §19.)
- **Reporting:** terminal output and `run.log` share Framework/PicoProducer messages; silent reporting is supported.
- **CLI:** `taufw.py plan RECIPE [--local -m N]`, `start RECIPE [--run-root DIR] [--wait --poll S]`,
  `advance RUN_DIR [--wait --poll S]`, `status RUN_DIR`; all delegate to Framework.
- **API boundary:** `PicoProducer.request(**fields)` builds requests without internal imports; PicoProducer loads
  only when constructing a production stage. Recipes are documented in the [analysis guide](../../Analyses/README.md).

### Tests

- 21 offline Framework tests cover stage transitions/retries, merge failures, placeholder blocking, exception
  recording, read-only status, persistence, recipe validation and CLI behavior.
- New lxplus BBB case `framework.production` records plan/status, run-state snapshots, resubmission, merged tuples
  and cleanup.
- A Windows integration with real Framework/PicoProducer APIs and fake storage/scheduling reached
  submit → resubmit → merge → BLOCKED at the placeholder, preserving artifacts and `run.log`.

---

## 10. Framework: plots, histograms and fit stages (Part G)

**Date:** 2026-10-13
**Details:** [Framework](../../Framework/README.md), [Fitter bugs](../Fitter/BUGS.md), [Histogrammer (former Plotter) bugs](../Histogrammer/BUGS.md)

Connected control plots and the combined TES+TauID workflow through public APIs wrapping existing scripts.
Later internal cleanup can preserve these APIs without changing Framework.

### What changed

- **Utilities.Process:** sequential commands without a shell, per-command logs and stop on failure.
  Success requires exit 0 and fresh expected outputs, catching ignored nested failures and stale files.
- **Fitter.api.TauESID:** plan/make/preflight shapes (`run_inputs.sh`) and plan/run/preflight fits
  (`run_workflow_zmm.sh`, option 3); parses fit values. **Plotter.api.ControlPlots** wraps `plot.py`.
- **Stage context:** run directory and upstream artifacts flow between stages and plans. Preflight problems
  leave stages NEW for retry; local stages advance to DONE/FAILED, recording command exit codes/durations
  and showing failure log tails. Fit working points come from the recipe or histogram artifacts.
- **CLI:** plans show commands/preflight warnings; status shows fit values. Built-in stage order is
  production, plots, histograms, fit; subsets are allowed (the fixed order was dropped in §19). See
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
fit values and stage/artifact behavior. BBB `framework.production` was re-locked to end DONE rather than
at a placeholder; the other 18 cases were unchanged. Local script stages are outside BBB coverage.

**Still open:** a full VTight/Tight `taufw.py start` run of `Analyses/tes_id_2025` compared with the shell drivers
in a clean copy (TODO §1). The fit part on the same shapes was compared in §17.

---

## 11. Framework: analysis bundles and Python steps (Part H)

**Date:** 2026-10-13
**Details:** [Analyses](../../Analyses/README.md), [Framework](../../Framework/README.md)

Bundles collect analysis configs in one directory; Python recipe steps add custom logic without a new stage class.

### What changed

- **Bundles:** recipes moved from `Framework/recipes/` to `Analyses/<name>/`, alongside configs and `steps/`.
  Commands accept a bundle directory; `taufw.py init NAME [--from RECIPE] [--root DIR]` creates one,
  copying referenced module configs without name collisions (§22: also the source bundle's own files).
- **Paths:** bundle files replace module configs as whole files, without merging. Other relative paths retain
  module resolution; paths above the bundle stay outside it. Plans show each input's source.
- **Run isolation:** `start` copies the bundle to `<run dir>/bundle/` (50 MB limit; hidden files, caches and runs
  excluded). Stages read the copy, so later source edits do not affect the run. Loose recipes copy referenced files
  only. `run.json` gains `bundle` metadata while retaining schema 1 and compatibility with older records.
- **Python steps:** `stage: python` specifies `file`, `function` (default `run`), `options`, `timeout` and optional `id`.
  Each runs in a separate process with bundle/upstream context and returns a message/artifacts. Preflight checks
  the function without importing it; failures show log tails. Multiple steps use unique ids; built-in stages
  remain ordered and unique. (Since §15 every stage has a required id; since §19 built-in stages may repeat.)
- **Config propagation:** APIs pass `$TAUFW_PICO_CONFIG` to scripts. Loading is read-only; a missing configured file
  is an error, and unset behavior is unchanged. Shared `CommandPlan`/`RunReport` records moved to Utilities.Process,
  with existing API exports retained.

**Limitation:** sample catalogs are not bundled; Plotter/Fitter and PicoProducer resolve their own catalogs. (The
Plotter's sample lists became bundle files in §22; PicoProducer's catalogs are still its own.)

### Tests

Offline tests cover path resolution, isolated copies, old records, stage ids, initialization and real Python steps
passing artifacts or failing. BBB `framework.production` changes on purpose for bundle/config metadata; PicoProducer
cases stay unchanged. (Its current baseline is the one re-locked in §19.)

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

After the Drawing move: 24 import occurrences / 22 file-module pairs across 20 files (Fitter → Plotter: 19 pairs;
PicoProducer → Plotter: 2; Plotter → PicoProducer: 1). Nine files fail full parsing; no new/stale entries or recovery errors.

Registered with the test runner. Ten detector tests and 28 harness checks pass; the repository check fails on
known debt as intended. Production code and baselines are unchanged; lxplus confirmation remains in TODO §1.

---

## 14. Fitter imports drawing helpers from their own home

**Date:** 2026-10-14

Five Fitter files now import helpers directly, preserving the same objects while avoiding unnecessary Plotter setup.

| Files | Direct import |
|---|---|
| `Fitter/TauES_ID/{plot2DScan_MultiDimFit,plotParabola_POI_region,plotPostFitScan_POI}.py` | `TauFW.Utilities.Drawing.CMSStyle` |
| `Fitter/python/plot/rebinning.py` | `TauFW.common.tools.file.ensuredir` |
| `Fitter/python/plot/postfit_TES.py` | Drawing's `CMSStyle`; `setera` still comes from Plotter |

`postfit_TES.py` retains its Plotter dependency because `setera` updates both CMS text and sample normalization globals.
Only imports changed.

### Tests

Parsing and helper attributes checked; four decoupled files removed from the boundary inventory (22 → 18 pairs).
Fitter → Plotter is now 16 occurrences / 15 pairs / 13 files, with no new/stale entries.
lxplus validation remains pending in TODO §1.

---

## 15. Framework: explicit stage ids, inputs and recipe validation (R1)

**Date:** 2026-10-14
**Details:** [Analyses](../../Analyses/README.md) "File format and validation", [Framework](../../Framework/README.md)

First step of the recipe IO work: the recipe, not the Framework, says which stage reads which stage's output, and every
problem of a recipe is shown at once. Run behaviour is unchanged otherwise (outputs still go to the module directories;
per-run output directories come in §16 and §17).

### What changed

- **Every stage has `stage`, `id` and `inputs`, and may have `description`.** `id` is required for every stage and any
  stage may have any id (the old rules "a built-in stage's id is its name" and "a python step's id defaults to its file
  name" are gone). Ids that the run directory used were reserved at first (`bundle`, `logs`, `run.json`, `run.log`);
  §16 removed that rule. `description` is free text, shown by `plan` and the menu, used for nothing else.
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

Framework unit tests (now 90, with `Tests/Framework/test_validation.py`) and the menu tests (27) pass on Windows. New
cases: every input error, reserved and duplicate ids, a stage that does not see an unnamed earlier stage, a python step
without inputs, `taufw.py check`, broken recipes red in the menu, the bundled analyses valid. The recipe of the BBB case
`framework.production` (`Tests/BBB/cases.py`) gets `id: production` and `inputs: null`; its output changes on
purpose: the `plan` lines (`=== Stage production (production) ===` and a new `Inputs: none` line) and the recipe in the
recorded `run.json` (`id`, `inputs` keys). (Its current baseline is the one re-locked in §19.)

---

## 16. Framework: run directory with logs/ and stages/, stage manifests (R2)

**Date:** 2026-10-15
**Details:** [Framework](../../Framework/README.md) "Run directory", [Analyses](../../Analyses/README.md) "Outputs and logs"

Second step of the recipe IO work (R2): a stage's directory in the run now holds only what the stage makes, so the
next step can run the Plotter and Fitter scripts inside it (§17).

### What changed

- **Layout:** `taufw_runs/<run>/logs/<id>/` holds the Framework's files of a stage (command logs `NN_<label>.log`, a
  python step's `context.json` and `result.json`); `taufw_runs/<run>/stages/<id>/` holds its output (a python step's
  own files, `ctx.stage_dir`) and nothing else. Before, both were `taufw_runs/<run>/<id>/`. `StageContext.stage_dir()`
  is the output directory, the new `StageContext.log_dir()` the log directory. Directories are made when a stage runs.
- **Ids:** stage directories live under `stages/`, so an id can no longer clash with `run.json`, `run.log`, `bundle/`
  or `logs/`: the reserved ids of §15 are gone (`defaults.RESERVED_STAGE_IDS` removed); only `.` and `..` are refused.
- **Manifest:** when a stage becomes `DONE`, the Framework writes `stages/<id>/manifest.json`
  (`{manifest: 1, run_id, stage_id, stage, description, inputs, finished, artifacts}`), before `run.json` is saved.
  It is a copy of the stage's record, so a stage directory describes itself (for a later input that names another
  run's stage directory); `run.json` stays the source of truth, and the Framework does not read manifests yet. A
  failed stage has none. Production's directory holds only its manifest (its tuples stay in PicoProducer's storage);
  plots, histograms and fit hold only theirs until their outputs move (R3).
- **`run.json` schema 2:** the recipe format of §15 and this layout. A run directory of schema 1 is refused when it is
  loaded (no conversion: there are no runs to keep).

### Tests

Framework unit tests (90) pass on Windows: log and output directories of every stage, the manifest content of a DONE
stage and its absence for a failed one, production's directory with only the manifest, a python step's files split
between `logs/` and `stages/`, ids `bundle`/`logs` now allowed and `..` refused, schema 1 refused. BBB
`framework.production` records `run.json`, so `"schema": 2` adds to the §15 difference (current baseline: §19).

---

## 17. Framework: Plotter and Fitter outputs in the run directory (R3)

**Date:** 2026-10-15
**Status:** checked on lxplus 2026-10-15
**Details:** [Framework](../../Framework/README.md) "Run directory", [Analyses](../../Analyses/README.md) "Stage
options" and "Outputs and logs", [scripts_arg_changes.md](scripts_arg_changes.md), Fitter BUGS F11-F24, Histogrammer
BUGS L08-L11

Third step of the recipe IO work: the plots, shapes and fit results of a run go to its stage directories, so runs no
longer overwrite each other in `Plotter/` and `Fitter/`, and the summary scripts no longer pick up the working points
of other runs. Plan: `LocalR/architecture/archive/10-r3-plan.md`.

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

Windows: Framework, Plotter API, Fitter API and Utilities process tests pass, with new cases for the commands,
working directories, artifacts and preflight problems with an output directory.
lxplus (2025 tuples of the TauFW group area): the plots equal those of `plot.py` in `Plotter/` and nothing is written
to `Plotter/` or `Fitter/`; `bbb check` 20/20 unchanged. For VTight/Tight the shell scripts with the new code give the
baseline's fit parameters and corrections exactly; the Framework's shapes equal the baseline's up to 1e-13
(multithreaded RDataFrame), and on the same shapes the Framework fit and the shell scripts agree exactly. Two runs of
shapes + fit from the same tuples can differ by a grid step in the fitted POIs (TODO §6).

---

## 18. Framework: tuples as an input, production writes into the run, run_root

**Date:** 2026-10-17
**Status:** steps 1-8 done; the end-to-end production check passed on lxplus (TODO §1)
**Details:** [Framework](../../Framework/README.md) "Concepts" and "Run directory", [Analyses](../../Analyses/README.md)
"Where the runs go (`run_root`)", [scripts_arg_changes.md](scripts_arg_changes.md) "Tuple location", Framework BUGS
K04, K05, K07, PicoProducer BUGS S17, Histogrammer BUGS L12

The Framework, not the global `$PICODIR`, decides where the pico tuples are read and written, and everything is
visible in the recipe. Plan, decisions D1-D13 and steps: `LocalR/architecture/archive/12-tuples-plan.md`.

### Step 1: recipe warnings and `run_root`

- **Warnings:** a recipe can have warnings besides its problems (it runs, but should change). `check` prints them and
  exits 0; `plan`, `start` and the menu preview show them; the recipe is not red.
- **`run_root`** (top-level key): the parent directory of the runs; `start --run-root` takes precedence; without both,
  `taufw_runs/` in the working directory with a warning. It must be absolute, not a URL, and outside the bundle; `~`
  and `$VARIABLES` are expanded with a warning. `plan` and `start` print the directory and where it comes from.
- **Write check:** before `start` with a run root and before every `advance`, the Framework writes and removes a small
  file there; on failure `RunDirectoryError` and nothing is started or moved.
- The menu's "Continue an existing run" also lists the runs in the `run_root` of every recipe in `Analyses/`.

### Steps 2-3: `--tuples` for the scripts and the APIs

- `getsampleset(..., tuples=PATTERN)`, `plot.py --tuples` and `createinputsTES.py --tuples`: the tuple directory
  pattern (`$ERA`, `$GROUP`) instead of `$PICODIR` from the PicoProducer configuration. Without it, unchanged.
- `PlotsRequest.tuples`, `ShapesRequest.tuples`: with a pattern every command gets `--tuples`, no
  `$TAUFW_PICO_CONFIG`, and preflight checks the pattern instead of the configuration (unknown `$KEYS` such as `$DAS`
  are refused).
- New lxplus test `Tests/Plotter/testTupleLocation.py`.

### Steps 4-5: production writes into the run

- PicoProducer: `JobRequest.tupledir` (never set by `pico.py`) makes `merge` write to
  `<tupledir>/$ERA/$GROUP/<sample>_<channel><tag>.root`; `PicoProducer.tuple_pattern(request)` returns where `merge`
  writes. New lxplus test `Tests/PicoProducer/testTupleDir.py`.
- Framework: in a run, production's `tupledir` is its stage directory, and every tuple artifact gets `pattern`
  (`<run_dir>/stages/<id>/$ERA/$GROUP`). `Stage.planned_artifacts` lets later stages see that pattern in a plan.
  `kind` on tuple artifacts is still missing (K04).

### Step 6: plots and histograms read the tuples their input names

- `{tuples: {external: <pattern>}}` names tuples made outside TauFW (absolute, not a URL; `check` reports a missing
  directory).
- `LocalStage.tuples_pattern(context)`: the external pattern or the production artifacts' `pattern`, passed to the
  APIs as `tuples=`. Preflight checks that the tuple files or the external directory exist. `null` is unchanged
  (`$PICODIR`). `plan` shows `Inputs: tuples <- external <pattern>`.
- `Analyses/tes_id_2025` names the TauFW group's 2025 tuples with `{external: ...}`. K03 is fixed.

### Steps 7-8: bundles, documentation and lxplus

- Bundles and READMEs follow the new keys; `Analyses/README.md` no longer says that Plotter/Fitter outputs are shared
  between runs (left over from before §17).
- lxplus (2026-10-17): `check`/`plan` of `tes_id_2025` as expected; plots with `{external: ...}` made the same 8 plots
  as the §17 check; a read-only `--run-root` stopped before anything was made. BBB `framework.production` now
  snapshots the merged tuples in `stages/production/` and masks the run ID; re-locked (only this case changed; the
  merged tuples are byte-identical), then `bbb check` 20/20.
- **End to end:** a production of one sample (`DYto2TautoMuTauh_M-50`, 2022_postEE, mutau, 4 jobs) followed by plots
  (`{tuples: production}`). The jobs need a grid proxy readable by the schedd: with `/tmp/x509up_u<uid>` they were held
  and that try was spent; with the proxy on AFS (`voms-proxy-init --voms cms --out ~/private/x509up`,
  `export X509_USER_PROXY=...`) the resubmission ran. The chunks were merged into
  `<run_dir>/stages/production/2022_postEE/DY/...` and the pattern recorded; plots read inside the run, not `$PICODIR`,
  and stopped, as expected, at the first sample that was not produced (fixed in §22 by the sample list in the recipe).
  Registered on the way: PicoProducer S17 (spurious "DAS path ... has wrong format" warning), Framework K07 (`status`
  shows a stale message next to the live job table).

### Fix on the way: Histogrammer L13, Fitter F25

An exception to "no bug fixes until the refactor is finished", in its own commit: the Plotter and Fitter APIs used
`importlib.util.find_spec('ROOT')`, which raises once CMSSW's ROOT is imported, so every recipe with production before
plots or histograms crashed in `plan`. The lookup now counts an already imported module as found. No output changes.

---

## 19. Framework: inputs from another run's stage directory, repeated stages (R4)

**Date:** 2026-10-17
**Status:** Windows tests pass; checked on lxplus (TODO §1 "R4 on lxplus")
**Details:** [Analyses](../../Analyses/README.md) "File format and validation" (stage order, "Inputs from another
run"), "Outputs and logs", "Troubleshooting"; [Framework](../../Framework/README.md) "Run directory"; TODO §6
"Revise: one rule for the paths in a recipe"

The last part of the recipe IO work (R1-R3, §15-17; tuple locations, §18): a stage may read the output of another,
finished run, and the built-in stages may repeat. Plan and decisions: `LocalR/architecture/archive/11-r4-plan.md`.

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

- Windows: Framework, Fitter API, Plotter API and Utilities tests pass (new `test_manifest.py`; repeated stages,
  `{path}` rules, a fit, plots and a python step reading another run, provenance).
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
- `_background.py`: `BackgroundProcess` runs a command in its own process group with output straight into the log;
  `cancel()` sends SIGINT, then SIGTERM after 3 s, SIGKILL after 8 s. (Since §23 the menu uses supervised operations
  instead; `BackgroundProcess` remains for commands that live only as long as their screen.)

### Tests report events; the test screen

- `Tests/run.py` and `Tests/BBB/runner.py` emit `suite`, `case_start`, `case_end`, `summary`, `warning`, `error`
  (`Tests/support/events.py` repeats the protocol so the runner works without TauFW; a test checks both sides agree).
  Without `$TAUFW_EVENTS` the terminal output is unchanged.
- `Utilities/python/Menu/_test_run.py`: the cases with `[PASS]/[FAIL]/[SKIP]/[ RUN]`, times and counts, the focused
  case's details and live log, Enter for the whole case log, L for the runner output; ten frames a second.
- `interactive.py`: `start_tests` replaces the in-terminal `execute_tests`.

### Framework events (`EventReporter`)

`taufw.py` reports what it does as events, so a run screen can follow a `start`/`advance` started beside it. Nothing
reads them yet; the terminal output and `run.log` do not change (checked byte for byte).

- `Reporter.event(kind, **fields)` is ignored by default; `EventReporter(reporter, writer)` passes every call on and
  also writes headers, messages, warnings, tables and events. Events: `run`, `stage_step`, `stage_state`, `run_state`,
  `wait`, `progress` (every command of plots, histograms, fit and python), `error`; listed in `reporting.py`.
- `taufw.py` reads `$TAUFW_EVENTS` once and removes it from the environment, so stage commands and batch jobs never see
  it. BBB `framework.*` runs without it.

### What is left

The run screens: `start`/`advance` detached with a run lock that records the host, `status`/`plan` beside the screen,
one curses session for the whole menu, errors on screen instead of printed (TODO §6 "Menu as a program").

---

## 21. Configs: config templates with an id, a version and a lock

**Date:** 2026-10-17
**Status:** Windows tests pass; nothing to check on lxplus (no ROOT, no BBB case)
**Details:** [Configs/README.md](../../Configs/README.md)

Analysts should not have to enter the module directories: everything an analysis can change is a copy in its bundle,
and the modules' templates for those copies live in `Configs/<Module>/`. Every template starts with a `taufw_config`
header (`id`, `version`, `schema`, `description`) that the copy keeps, so a later change of the template (e.g. a
corrected cross section) does not go unnoticed. This section built the infrastructure only; the first templates came
with §22 (in `Configs/Plotter/`, moved to `Configs/Histogrammer/` with `histogrammer.*` ids in §24 S2).

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
(MC cross sections, data datasets, weights, stitching, joining and splitting, per era). Its samples became templates in
`Configs/Plotter/samples/` (§21; `Configs/Histogrammer/samples/` since §24 S2), one per era, that an analysis copies
into its bundle. **No physics or data change:** every sample set built from a template gets exactly the calls the old
function makes, and a test proves it. Plan: `LocalR/architecture/archive/14-sample-model-plan.md`.

- **S0, recorder and BBB case:** `Tests/Plotter/sample_model/recorder.py` records every call of a sample-set function
  (8 eras × 6 channels × 7 caller options = 336 cases). BBB case `plotter.sample_model` was locked on lxplus with the
  old code, then switched to the model with no difference.
- **S1, templates:** `export.py` wrote `v15_<era>.yml` for the 8 eras from the recorded calls (nothing typed by hand,
  each file read back and compared); cross sections are cross section × k-factor as `samples_v15.py` computed them.
- **S2, the model:** `Plotter/python/sample/model.py` (`load_sample_model`, `pick`, `sample_names`, `getsampleset`):
  the generic part of `samples_v15.getsampleset` copied as it is, the era part read from the model. A unit test checks
  all 336 cases against the old function. Registered: L14 (`DM` split `NameError`, kept), L15, L16 (era `2526` with
  tautau/emu).
- **S3, scripts:** `samples_v15.getsampleset(..., samples=[files])` returns the model's sample set (marked BACKWARD
  COMPATIBILITY); `plot.py --samples` and `createinputsTES.py --samples` pass it on.
- **S4, APIs:** `PlotsRequest.samples`, `ShapesRequest.samples`; `ControlPlots.sample_names`, `samples_problems`,
  `sample_file_problems` for preflight; `PicoProducer.sample_names(request)` lists what a production would make.
- **S5, Framework and recipes:** `plots` and `histograms` take the option `samples` (bundle files or absolute paths).
  `TauFW.Framework.samples.sample_issues`: a requested sample that the recipe's production does not make is a problem,
  a produced sample nobody reads is a warning; `plan` shows them and `start` refuses problems.
  `Analyses/tes_id_2025` uses a copy of `v15_2025.yml`. `Analyses/example_mutau` was split in two, by decision of the
  author: its production made only `DY*` and `TT*`, which the plots could not use since §18; now
  `example_mutau_short` is production only, and `example_mutau_long` produces data and the 22 MC samples of its sample
  file and then makes the plots.
- **S7, channel setups:** `Plotter/config/setup_*.yml` (7 files) moved to `Configs/Plotter/setups/` with headers
  (`Configs/Histogrammer/setups/` since §24 S2). `plot.py` and the postfit scripts read a channel name's setup from
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
  shown as **Lost** (D1). One test run at a time (D2). The last five records of a kind are kept (D4).
- For runs (later): a lock in `Framework.advance`, refused while held on another machine and taken over only on
  request when Lost (D3); a stop never kills job submission halfway (`escalate=False`). The shared screen comes with
  the run screen (K1, K2); `setup_runner` stays (K5); `plan`/`status`/`check` move beside the screen (K4).

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

### Checked

`Tests/Utilities/test_operations.py` (new): supervisor exit codes, heartbeat, stop, kill, SIGTERM, every state, a real
start; the menu tests follow the new behavior. End to end on Windows: a test run through the supervisor, a refused
second start, a second menu that found it and followed its label to the end. Not checked here: process groups and
signals, curses on a real terminal (TODO §1).

---

## 24. Plotter becomes Histogrammer; a clean Plotter is extracted

**Date:** 2026-10-18
**Status:** done. S0-S4 checked on lxplus (BBB 22/22 without re-lock after every step, real plots identical); see
[Result](#result-of-24) at the end.
Plan: `LocalR/architecture/archive/18-histogrammer-split-plan.md`.

After the drawing moved to `TauFW.Utilities.Drawing` (§12), almost everything left in `Plotter/` produces
histograms: the sample model, normalisation, stitching, the RDataFrame filling, the variable/selection language and
the QCD method. "Plotter" therefore names the module after the one thing it no longer does. The plan: rename the
module to `Histogrammer/` (`plot.py` -> `fillhists.py`, `python/plot/` -> `python/spec/`), keep the old import paths
and the old `plot.py` command as documented compatibility (TODO §8), move its configs to `Configs/Histogrammer/`, and
then extract a small, clean Plotter that draws from a histogram file written by the Histogrammer. **No physics or
data change:** the filling code is moved, not edited, and every step is proven by BBB without re-lock.

### Lock and tools (S0)

- BBB case `plotter.stack` (new, to be locked on lxplus with the old code): `plot.py`'s path from samples to drawn
  stacks, which no case covered: `setera(2018)` without an explicit lumi on the samples (the module global read
  through `GLOB`), `getstack(..., method='QCD_OSSS')` (the method module loaded by name), `draw`, `drawlegend`,
  `drawtext`, `saveas`; it records the sample table, the sample states, and per stack the histograms, the 17
  attributes the drawing reads from the variable and the drawn canvas. Only `_stack_modules()` changes when the code
  moves (S1) and when the drawing reads the histogram file (S3).
- `Tests/tools/move_check.py` (new, ROOT-free): compares moved files with their old version in git; a changed line
  must be an import or match an `--allow` pattern, and the functions/classes whose AST differs are listed (AST, not
  bytecode). Unit tests `Tests/tools/test_move_check.py`, suite `unit.tools` in `Tests/run.py checks`.
- `Tests/tools/roundtrip_spike.py` (new, lxplus, one-off): draws the BBB fixtures (A) from memory as today, (B) after
  writing the histograms to a ROOT file and reading them back, (C) from the file with a plain object holding only the
  drawing attributes instead of the Variable; compares the drawn canvases and the PNG bytes. It checks the two
  assumptions of the extraction before it is designed.

### Checked

- Windows: `python Tests/run.py checks`: `unit.tools` passes (6 tests); only the known failures (`check_root`: no
  ROOT on Windows; `check_import_boundaries`: known debt, 0 new pairs). `cases.py` parses with Python 3.9 syntax.
- lxplus (2026-10-18): the new case was locked (22 cases) and the spike gave 12/12 SAME (TODO §1).

### The rename (S1)

**Date:** 2026-10-18, Windows; checked on lxplus (below).

- `git mv Plotter Histogrammer`; in it `plot.py` -> `fillhists.py` (fills, and until S4 also draws, exactly as
  before; only its header comment, the usage lines and `prog` in `-h` changed), `python/plot/` -> `python/spec/`
  (`Variable`, `Selection`, `Context`, `string`), `MultiDraw.py`/`.cxx` -> `python/sample/` (a filling engine).
  `docs/Plotter/BUGS.md` -> `docs/Histogrammer/BUGS.md` (same IDs).
- Inside the moved code only these lines changed: the `TauFW.Plotter.*` imports, the two `GLOB` imports of the
  module state (`Sample.py:31`, `SampleSet.py:106`), the package of the method modules (`SampleSet.py:286`,
  `ensuremodule(method,'Histogrammer.methods')`), and docstrings that name paths. `Tests/tools/move_check.py` over
  the 25 moved Python files: every changed line is an import or one of those lines (commented-out old imports were
  left as they were).
- `api/control_plots.py`: the script is one constant (`SCRIPT = 'fillhists.py'`), the default `basedir` is
  `$CMSSW_BASE/src/TauFW/Histogrammer`; messages and docstrings name the Histogrammer. The Framework's plots stage,
  its sample checks and `validation.py` use `TauFW.Histogrammer.api` (no old `TauFW.Plotter.api` name is kept: only
  the Framework used it). Recipes, stage names and `run.json` are unchanged.
- **Backward compatibility (TODO §8):** a new `Plotter/` holds the 13 old module names
  (`python/sample/*`, `python/plot/*`, `python/methods/QCD_OSSS.py`). Each is
  `import <new module> as _module; sys.modules[__name__] = _module`: the old name is the very same module object,
  so `setera` through either name changes the same era and luminosity (a star re-export would freeze them). No alias
  for `TauFW.Plotter.plot.datacard` (it would repair `Fitter/MuTauFR/createinputs.py:11`). `Plotter/plot.py` and
  `Histogrammer/plot.py` print the new command (same arguments, path relative to the working directory) and exit
  with status 2; they run nothing. `Plotter/README.md` describes the coming drawing-only Plotter and its rules.
- Paths: the 6 Fitter `createinputs*.py` find `config.samples*` in `Histogrammer/`, `Fitter/Zpt` loads
  `Histogrammer/python/macros/Unroll.cxx`, `Fitter/HighPT` writes and reads `Histogrammer/data/ff_HighPT/`;
  `Utilities.Paths` gets `HISTOGRAMMER_ROOT`/`HISTOGRAMMER_DATA_DIR` (the `PLOTTER_*` names stay); `FastSetup.sh`
  also verifies `TauFW.Histogrammer`; `.gitignore` ignores `Histogrammer/plots`. `Configs/Plotter/` is unchanged
  (moved in S2).
- Import boundaries: `Histogrammer` is a stage of `Tests/check_import_boundaries.py` (a new detector test: the
  Histogrammer and the Plotter never import each other, the Framework may import only `TauFW.Histogrammer.api`,
  the Fitter not the Histogrammer). Allowlist: 13 new entries for the aliases (end: migration point), the A03 entry
  now in `Histogrammer/python/sample/utils.py`; the 6 Fitter `config.samples*` entries keep their keys but now count
  as Fitter -> Histogrammer (the same debt at a new address; step 2 removes it). Totals 30 / 28 / 26 (17 / 15 / 13
  before + the 13 aliases), 0 new pairs. **No cross-stage import was removed by this step**; it prepares step 2.
- Tests: `Tests/Plotter/{api,sample_model}` -> `Tests/Histogrammer/` (suites `unit.histogrammer.api`,
  `unit.histogrammer.sample_model`), new `Tests/Histogrammer/compat/test_compat_paths.py` (`unit.histogrammer.compat`:
  each alias file is exactly the alias of its module, the pattern shares state on a throw-away package, and with
  ROOT the old and new names are one object). BBB cases: only import lines, `_stack_modules`, the Unroll path and the
  `_DRAWING_MODULE` normaliser (old and new paths map to the same text) changed; the case names stay `plotter.*`.
  The old scripts in `Tests/Plotter/` keep the old names (they exercise the aliases); their inventory `package` is
  now `Histogrammer` (they load macros from `python/macros/` of the working directory). `Tests/support/bootstrap.py`
  copies `Histogrammer` too.
- Docs: READMEs (root, `Histogrammer/`, new `Plotter/`, Framework, Analyses, Tests, Utilities, Fitter `TauES_ID`
  and `Zpt`), `Utilities/IOInventory.md` (the Histogrammer and Plotter sections regenerated by `_audit_io.py`, which
  now scans `Histogrammer/` too; the rest of the file unchanged), `scripts_arg_changes.md` (old -> new table), TODO §1
  and §8, recipe comments.

Checked (Windows): `python Tests/run.py checks`: all unit suites pass (Framework 166, `unit.histogrammer.api` 14,
`unit.histogrammer.compat` 6 with 2 skipped for ROOT, `unit.tools`, `check_harness`); `check_import_boundaries`
fails as designed with 0 new pairs, `check_root` needs ROOT.

Checked (lxplus, 2026-10-18): `bbb check` 22/22 without re-lock; `checks` (one fix: the compat test now ignores an
untracked `Plotter/python/api/__pycache__/` left by `git pull`); the old scripts `plotter.unroll`, `plotter.samples`
through the aliases; `fillhists.py` against the old `plot.py` on the 2025 tuples (`-c mutau -V m_vis pt_1 -S
baseline`): the 4 PNG files byte-identical, the logs equal except the ACLiC line of `mapDecayModes.C` in its new
directory and the timing; `Plotter/plot.py` prints the new command and exits with 2. S0's `roundtrip_spike.py`:
12/12 SAME, so a Plotter drawing from a histogram file with only the 17 drawing attributes is feasible (S3).

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
  header" (and still warn when the template is newer), instead of "not in Configs/ any more". New test
  `test_copy_with_the_id_from_before_a_rename`.
- Paths: `fillhists.py`, `plot_postfit*.py`, `plot_v10.py` (`SETUPS`), the API (`SETUPS`, channel names), the help
  texts, the docstrings of the Framework, Fitter and Histogrammer, the tests (`READERS` keys `histogrammer.samples_`,
  `histogrammer.setup_`), `export.py` (writes the new id and paths), READMEs (`Configs/` explains the rename),
  `scripts_arg_changes.md`, recipe comments. The BBB case `plotter.sample_model` reads the templates from the new
  directory (its payload does not contain the path).

Checked (Windows): `python Tests/run.py checks`: all unit suites pass (`unit.framework` with the bundle checks: the
copies match their templates, no warning; `test_configs.py` 22 tests, 1 of them new); `check_import_boundaries` unchanged
(30 / 28 / 26, 0 new pairs).

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
  the S0 lock (canvases, histograms, drawing attributes, file names). Tests (no ROOT): `Tests/Utilities/test_histfile.py`
  (refusals; the round trip with ROOT), `Tests/Histogrammer/controlhists` (copies, detachment, metadata, the same
  contract constants as the Plotter), `Tests/Plotter/draw` (names and texts equal plot.py's, the contract check, the
  drawing variable); suites `unit.histogrammer.controlhists`, `unit.plotter.draw`.
- Not changed (decided with the user): `plot_postfit*.py`, `plot_v10.py` and the tutorial keep filling and drawing
  in one script (TODO §6: Legacy or two steps later); the Framework (S4).
- Docs: the contract page (start of `docs/contracts/`), READMEs (Plotter, Histogrammer, Utilities, Tests),
  `scripts_arg_changes.md`, IOInventory rows, TODO §1 and §6.

Checked (Windows): `python Tests/run.py checks`: 12 of 14 suites pass, the two new ones included;
`check_import_boundaries` unchanged (30 / 28 / 26, 0 new pairs: the Plotter imports only Utilities), `check_root`
needs ROOT. Not checked here: anything with ROOT (BBB, the round trip, real plots: TODO §1).

Checked (lxplus, 2026-10-18): `bbb check` 22/22 without re-lock (`plotter.stack` through the file gives the
canvases locked from memory in S0); the HistFile round trip passes with ROOT. Real data (2025 tuples, baseline):
mutau all variables, `--hists` changes no plot (31/31 identical PNGs) and `draw.py` draws the same 31; mumu stops at
`m_ll` with and without `--hists` alike (BUGS L17, a bug of the variable list, registered, not fixed), so mumu was
checked with its 18 other variables: 19/19 and 19/19. Found on the way and fixed (committed): the HistFile writer
wrote entries into the parent directory, because ROOT's `mkdir("a/b")` returns `a`.

### The histograms stage becomes shapes (S4a)

**Date:** 2026-10-18, Windows. Decisions of S4 with the user: plan 18 §14. Rule (user): recipes and Framework stages
have no users yet, so they take the clean design without a compatibility layer; commands run by hand keep their
behaviour.

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
  `stages/shapes/`), `fit` reads `inputs: {shapes: shapes}`. READMEs (Framework, Analyses), `docs/PicoProducer/API.md`.
- Tests: the Framework tests and `Tests/Fitter/api/test_tes_id.py` name the stage `shapes` (only strings, comments
  and the two class names changed); new assertion for the retired name in `test_bundle.py`.
- Not changed: earlier sections of this changelog, `CPPMigration.md`, `scripts_arg_changes.md`, the BUGS tables and
  the hardcoded-paths inventory, which describe what was there at their time.

Checked (Windows): `python Tests/run.py checks`: 12 of 14 suites pass as before (`unit.framework` included);
`check_import_boundaries` unchanged (30 / 28 / 26, 0 new pairs), `check_root` needs ROOT.

Checked (lxplus, 2026-10-18): `taufw.py plan Analyses/tes_id_2025` before and after (shapes, fit and python
part): every command, input and directory equal once `histograms` reads `shapes`; only the width of the table's
separator line differs (it was computed from the longer old paths).

### Control plots as two Framework stages (S4)

**Date:** 2026-10-18, Windows. Decisions with the user: plan 18 §14 (K1-K11). The Framework now makes control
plots in two stages, each through the API of its own module, and carries the control-histogram file between them;
the Histogrammer never draws in a run, the Plotter never fills, and neither imports the other.

```text
tuples ──[controlhists: Histogrammer API, fillhists.py --hists --no-draw]──▶ hists/<era>/<channel><tag>.root
       ──[controlplots: Plotter API, draw.py]──▶ plots/<era>/*.png   (the same files as fillhists.py draws)
```

- `Histogrammer/fillhists.py --no-draw` (new, only with `--hists`, else an error): writes the file, draws nothing,
  makes no `plots/` directory; `-F`/`-p`/`-T` are then ignored with a warning. Without it nothing changes: a command
  typed by hand fills and draws as before (user rule: plain commands keep their result; the default changes at the
  migration point, TODO §8). The copies in the file are taken before drawing (S3), so the file is the same with and
  without drawing (checked on lxplus, TODO §1).
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
  yet, user decision): `stage: plots` fails the check with "control plots are two stages now: controlhists (tuples
  -> histogram files) and controlplots (files -> plots)" (`stages.RETIRED`). Runs started before this change cannot
  be continued.
- Bundles: `tes_id_2025`, `example_mutau_long` (`controlhists` id `hists`, `controlplots` id `plots`, so the plots
  stay in `stages/plots/plots/<era>/`), `example_broken` (its error 3 now names `controlhists`).
- Boundary: no new import edge (Framework -> `TauFW.Plotter.api` is an API); `Tests/Histogrammer/compat` now allows
  `TauFW.Plotter.api` as long as it imports nothing of the Histogrammer (it is the new Plotter's own API, not an
  alias of the old one).
- Tests: `Tests/Plotter/api` (new suite `unit.plotter.api`: commands, expected names, artifacts, preflight with a
  planned file), `Tests/Histogrammer/api/test_control_hists.py` (the renamed test: `--hists --no-draw`, the file
  artifact, no drawing options), Framework tests with a fake Histogrammer and a fake Plotter (new
  `ControlPlotsTests`: the files of the input, a plan before the files exist, the input kind, `{path}` of another
  run; the retired name), `Tests/tools/compare_histfiles.py` + test (two histogram files entry by entry, for the
  lxplus check).
- Not changed: the legacy `plot.py` messages (`fillhists.py` is still one command, K6), the BBB cases, the old
  variants (`plot_postfit*`, `plot_v10`, tutorial).
- Docs: READMEs (Framework, Analyses, Histogrammer, Plotter, Tests), the contract page, `scripts_arg_changes.md`,
  IOInventory rows (by hand: `python Utilities/_audit_io.py` regenerates a much smaller file than the committed one,
  so it was not rerun), TODO §1 (lxplus), §6 (later), §8 (migration point).

Checked (Windows): `python Tests/run.py checks`: 13 of 15 suites pass (`unit.plotter.api` new, `unit.framework`,
`unit.histogrammer.api`, `unit.histogrammer.compat`, `unit.tools` included); `check_import_boundaries` unchanged
(30 / 28 / 26, 0 new pairs), `check_root` needs ROOT.

Checked (lxplus, 2026-10-18): `bbb check` 22/22 without re-lock. The reference was taken with the code before this
change: the old `plots` stage on a copy of `tes_id_2025` (mutau all variables, mumu the 18 variables of the S3 check,
baseline). The same bundle as `controlhists` + `controlplots`: every PNG equal (`cmp`: 31/31 mutau, 19/19 mumu), the
`controlhists` directory holds only the files. The file of `--hists --no-draw` equals that of `--hists`
(`compare_histfiles.py`, SAME within 1e-12); the last bits (largest relative difference 4.6e-13) are run-to-run noise
of the multithreaded fill: running the old path again differs by 1.9e-13 from the first run. Filling mutau took
388 s, drawing it 5 s. A fix on the way: `compare_histfiles.py` first compared the exact floats of the BBB snapshot
as text, so its tolerance did not apply to bin contents (fixed, with a test). `.gitignore` needed
`!Plotter/python/api/__init__.py` (every other `__init__.py` is ignored); without it the API would not import on
lxplus.

### Result of §24

What the analysis code looks like now:

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
- **Next:** step 2 of `LocalR/architecture/13` (the TES shapes leave the Fitter for the Histogrammer, plan 16, revised
  after this section); its first step locks a new BBB case, which needs the 22 cases above unchanged.

### Review fixes of §24

**Date:** 2026-10-18, Windows, after S5. A code review of `8a3531a..e713f16` (rename, aliases, config ids, histogram
file, stages, tests, docs) found nothing broken; these fixes of what the split itself introduced. No filling or
drawing code changed; a file that was written before is written the same.

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
- Tests: the refusals above (`Tests/Utilities/test_histfile.py`, with ROOT the header without keys;
  `Tests/Plotter/draw`, `Tests/Histogrammer/controlhists`); a run whose `run.json` names a retired stage (`plots`,
  `histograms`) is refused by `Framework.from_record` with the recipe error that `taufw.py status`/`advance` print
  (`test_framework.py`); the Utilities import ban also names `Histogrammer`; the bundle test's fake Histogrammer
  directory is called `Histogrammer`.
- Docs: `Histogrammer/README.md` (where the API runs the script), `stages/shapes.py` docstring, IOInventory rows of
  `fillhists.py` and `controlplots.py` (line numbers, the `--hists` file), TODO paths of the renamed files, TODO §8
  (`PLOTTER_ROOT`/`PLOTTER_DATA_DIR`), TODO §9 (three docs that were stale before §24).

Checked (Windows): `python Tests/run.py checks`. On lxplus: `bbb check` 22/22 without re-lock, `checks` (TODO §1).
