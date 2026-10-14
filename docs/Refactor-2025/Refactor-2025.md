# Refactor-2025: change log

# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
**Branch:** `Refactor-2025`
**Last updated:** 2026-10-14

This document records the changes made on the `Refactor-2025` branch: what changed and why.
What is still open is listed in [TODO.md](TODO.md).

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
| 15 | [Framework: explicit stage ids, inputs and recipe validation](#15-framework-explicit-stage-ids-inputs-and-recipe-validation) |

The reference environment for all of this is `CMSSW_14_1_0_pre4` (Python 3.9, ROOT 6.30).

---

## 1. Test migration and BBB regression tests

**Date:** 2026-10-12
**Commits:** `949ce56` (Test Migration 1), `bc1e28c`, `9b4b407`, `875ba88`, `905eac8`, `28b8c57`,
`dd0fb9e`, `0f36771`, `646d28f`, `9f9d510` (Lock BBB baselines), `ef80e40` (Re-lock BBB baselines)
**Details:** [Tests/README.md](../Tests/README.md), [Tests/LEGACY_BROKEN_CASES.md](../Tests/LEGACY_BROKEN_CASES.md)

### What changed

- **Tests moved to top-level `Tests/`.** Moved 38 test files unchanged.
  [Tests/migration.json](../Tests/migration.json) records original paths and content hashes.
- **A test runner, `Tests/run.py`.** Each test runs in a fresh process and temporary source workspace.
  [Tests/inventory.json](../Tests/inventory.json) classifies 37 cases: 26 local (run by `normal`),
  7 opt-in integration, 2 legacy and 2 broken. Missing dependencies produce SKIP.
- **BBB: exact regression tests** (`Tests/BBB/`). Added 13 cases using fixed ROOT fixtures,
  recording histogram/tree structure, values and errors. Floating-point values are compared by exact bytes,
  without tolerance. Coverage includes:
  - common: table/loading-bar text, chunking and formatting;
  - Plotter: selections, weighted 1D/2D histograms, merging/splitting, DY stitching, QCD OS/SS, unrolling;
  - PicoProducer: tree writer schema, NanoAODTools bookkeeping, scale-factor lookup;
  - Fitter: shape naming, negative-bin sanitation, adaptive rebinning.

  `python3 Tests/run.py bbb lock` runs each case twice and rejects non-repeatable baselines.
  `python3 Tests/run.py bbb check` compares against [committed baselines](../Tests/BBB/baselines/)
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
**Details:** [Utilities/README.md](../Utilities/README.md), [Utilities/IOInventory.md](../Utilities/IOInventory.md)

### What changed

- Added `TauFW.Utilities` with two independent interfaces:
  - **`CLI`**: verbosity, stderr warnings/errors, headers, tables, progress and prompts.
  - **`FileIO`**: local files and explicit XRootD/GFAL URLs, common data formats, directory operations,
    ROOT file ownership and `hadd`. Overwrites require `overwrite=True`; external commands use argument lists
    without a shell and have timeouts.
- Added an I/O inventory mapping existing terminal/file operations to `CLI`/`FileIO` methods.
- Added offline unit tests with mocked remote/ROOT operations; the test runner includes Utilities in its workspaces.

**No existing framework code uses these packages yet.** This commit only adds them.

### Why

Provide shared, tested I/O implementations with explicit remote paths, safe writes and ROOT ownership,
replacing duplicated helpers incrementally. Each later migration can be reviewed separately and checked
against the existing BBB baselines for unchanged covered outputs.

---

## 5. PicoProducer cleanup, Part 1: command-level BBB tests and bug register

**Date:** 2026-10-12
**Details:** [Tests/README.md](../Tests/README.md#picoproducer-command-cases-black-box),
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

### Still to do

- Lock the new cases on lxplus with `python3 Tests/run.py bbb lock --replace`, confirming the 13 existing baselines are unchanged.
- Before the analysis/corrections cleanup, add a `ModuleTauPair` channel case with larger synthetic NanoAOD
  and jsonpog/TauIDSFs payloads.

---

## 6. PicoProducer cleanup, Part 3: settings, datasets, storage, batch and jobs packages

**Date:** 2026-10-12
**Details:** [docs/PicoProducer/BUGS.md](../PicoProducer/BUGS.md)

### A. Restructuring (no behavior change)

Split configuration into `settings/`, samples/catalogs/DAS into `datasets/`, storage adapters and validation
into `storage/`, schedulers/templates into `batch/`, and chunking/job configs into `jobs/`.
Packages expose explicit public APIs; in-repo callers and 46 sample catalogs were updated.

Config defaults no longer import storage, batch or ROOT; catalog path setup occurs only when loading samples.
Producer validation no longer imports Plotter's parallel helper (moved to Utilities in §12).

### Migration for users

| Old | Replacement |
|---|---|
| `TauFW.PicoProducer.storage.Sample` | `TauFW.PicoProducer.datasets`; the old module remains a compatibility re-export for private catalogs |
| `TauFW.PicoProducer.tools.config` | `TauFW.PicoProducer.settings` |
| `storage.utils.getstorage / isvalid / getsamples` | `storage.getstorage / isvalid`; `datasets.getsamples` |
| `batch.utils.getbatch` | `batch.getbatch` |
| `TauFW.Plotter.plot.MultiThread.MultiProcessor(max=...)` | `TauFW.Utilities.Process.ParallelProcessor(max_parallel=...)` (§12) |
| Custom `batch/<Name>.py` adapter | Register in `batch/factory.py`'s `SYSTEMS`; put templates in `batch/templates/` |

The restructuring preserves config keys and values; `batch` still names the adapter class.

### B. Bug fixes

Fixes followed restructuring; [BUGS.md](../PicoProducer/BUGS.md) records individual details and output impacts.

| ID | Fix / user impact |
|---|---|
| S01 | Implemented SGE array submission and queue parsing. **Not tested on an SGE site.** |
| S02–S04 | Repaired dict-based batch lookup, enforced abstract adapter methods, and corrected string escapes without changing their values. |
| S05–S06 | Repaired PSI adapter construction and EOS listing/removal command assignment. |
| S07–S09 | Fixed glob-source merges, unmounted storage `cd()`, and GridKA removal/multi-file merging. |
| S10 | Restored sample type detection with warnings for detected data/embedded samples. In-repo catalogs use explicit MC/Data classes and are unaffected. |
| S11 | File-list event totals now replace conflicting stored counts, as the warning indicates. |
| S12–S14 | Corrected docstring placement and `Embedded` spelling; removed a mutable catalog-cache default. `Embdedded` remains an alias in `storage/Sample.py`. |
| S15 | Removed validation's Plotter dependency in A. |
| S16 | **Won't fix:** NAF users must select `pico.py set batch HTCondor_NAF` explicitly. |
| P16 | Private config attribute assignment no longer raises `KeyError`. |
| P17 | Fresh-install defaults and example config now name existing era catalogs; existing configs retain their eras. |
| P18 | `getconfig(write=False)` repairs defaults in memory. Only the CLI requests persistent writes; workers, Plotter and scripts no longer rewrite the config. |

**Only P17 changes a BBB baseline:** `pico.config`, `fresh.values.eras`. Other fixes are outside BBB coverage
or preserve recorded values.

### File-name correction and validation

Eight case-only module renames were missing from Git, causing Linux import failures. Fixed in `ae0d9bf`.
Do case-only renames on Linux with `git mv`, or verify tracked spelling on Windows with `git ls-files`.

After the correction, lxplus BBB showed only the intended P17 difference; the other 17 cases passed.
Re-lock `c2d8296` changed only `pico.config.json` and `manifest.json`.

---

## 7. PicoProducer cleanup, Part 4: jobs package

**Date:** 2026-10-13
**Details:** [docs/PicoProducer/BUGS.md](../PicoProducer/BUGS.md)

Split `pico/job.py` and `pico/run.py` into job pipelines for the public PicoProducer API and Framework.
Restructuring (A) preserves behavior; bug fixes follow separately (B).

### A. Job pipelines

| Module | Responsibility |
|---|---|
| `jobs/worker_command.py` | `resolve_worker`, `job_command`, `run_command`: shared worker options with separate local/batch flag ordering |
| `jobs/request.py` | `JobRequest`: submission/local-run settings, independent of argparse |
| `jobs/planner.py` | Pure sample layout, chunk assignment and job-config glob planning |
| `jobs/pipeline.py` | `iter_plans`, `submit_plan`, `record_submission`, `iter_submitted`: sample selection, materialization, submission and existing-job iteration |
| `jobs/reporting.py` | Silent `Reporter` or `ConsoleReporter`, including progress |
| `jobs/jobconfig.py` | Ordered config keys, config construction and writing |
| `jobs/status.py` | `check_sample`: observes queue/storage/events; pure skim/tree classifiers produce `ChunkStatus` and resubmission inputs |
| `jobs/merge.py` | `merge_sample`: target, status gate, merge and cleanup; returns `MergeResult` |
| `jobs/local.py` | `iter_local_runs` and `execute_run` for local workers |

- Configuration is passed explicitly rather than read from global `CONFIG`.
- `iter_plans(..., materialize=False)` creates no directories or job lists; CLI submission materializes them.
- CLI functions retain argument handling, reporter selection and prompts; pipelines receive prompt answers.
- Status classifiers work on a copy of `chunkdict`; expected events return in `status.nexpected` rather than
  modifying the sample's job config. Tree validation still excludes pending chunks.
- `ChunkStatus.mergeable` requires nothing pending or needing resubmission. Merge/cleanup uses this gate unless forced;
  target and cleanup-command planning are separate from storage operations.

**Validation:** 8064 worker-option combinations matched the old command builders. A Windows comparison harness
against `3c401cd` covered 280 submit/resubmit/status/merge/local-run scenarios at verbosity 0–3, with matching
output, files and external calls (job-config timestamps excluded). The only restructuring difference was P02's
existing prompt crash exception type. Newly found P20–P23 were preserved until the fixes below.

### B1. Crash fixes without BBB change (P01, P02, P03, P07)

| Bug | Fix |
|---|---|
| P01 | Error handlers use `str(err)` instead of Python 2's `err.message`, reporting errors instead of crashing. |
| P02 | Fixed the existing-job-config submission prompt's invalid formatting/undefined name. |
| P03 | Fixed gzip imports and JSON writing for `.json.gz` job configs; written configs read back correctly. |
| P07 | Replaced a mistaken comparison with assignment when disabling expected-event checks; output is unchanged. |

No BBB case reaches these paths. Targeted checks verified the repaired prompt and gzip round trip.

### B2. Behavior fixes without BBB change (P04, P05, P06, P11, P19–P23)

| Bug | User-visible result |
|---|---|
| P04 | `--checkqueue 1` queries the queue once and detects pending jobs. |
| P05 | Submission reports when no samples match. |
| P06 | Event splitting honors positive sample `maxevts`, otherwise using configured `maxevtsperjob`. |
| P11 | Local runs report failed worker exit codes and list failures at the end. |
| P19 | Cleanup after `haddclean`/`hadd -r` requires a readable merged tuple and, when counting events, the processed total of good chunks. Invalid merges warn and retain job outputs; `MergeResult.invalid` records why. |
| P20 | Existing-config prompts submit on `y`/`f` and skip on `n`. |
| P21 | Analysis-channel status warns about unexpected event counts by default, matching merge/resubmission checks. |
| P22 | Status checks no longer create storage output directories. |
| P23 | Whole-directory cleanup requires every job config to belong to the sample; cleaning one tag preserves other tags' configs, lists and logs. |

BBB baselines stayed unchanged because these paths are untested or produce the same recorded results.
Targeted comparisons changed only affected scenarios, including failed workers, pending jobs, invalid merges
and cleanup with multiple tags.

### B3. Module options and `run -m` (P08, P09, P10), with re-locked baselines

| Bug | Fix |
|---|---|
| P08 | Option precedence is channel < sample < user (`-E`); later values win. Channel/user options are resolved separately and joined with sample options. |
| P09 | Resubmission reuses merged options and appends only new user options, preventing growth on every retry. |
| P10 | Local runs pass `-m` only for positive event limits, removing the default `-m -1`. |

Verbose output shows `chopts`/`useropts` instead of `extrachopts`.
`pico.run` and `pico.jobs` intentionally change and are re-locked on lxplus with `bbb lock --replace`;
all other cases remain unchanged. Comparisons differ only in option order, removal of `-m -1` and verbose labels.
See [exact baseline differences](../PicoProducer/BUGS.md#p08-p09-p10-module-options-and-run--m).

---

## 8. PicoProducer cleanup, Part 5: public API, command line, workers

**Date:** 2026-10-13
**Details:** [API](../PicoProducer/API.md), [I/O contract](../PicoProducer/IO.md),
[bugs](../PicoProducer/BUGS.md)

Added a public Python API, made `pico.py` its client, and renamed `processors/` to `workers/`.
Framework uses only the public API. Restructuring preserves behavior; command/worker fixes follow separately.

### A. API, CLI and workers

| Component | Responsibility |
|---|---|
| `api/producer.py` | `PicoProducer`: `plan`, `iter_plan`, `submit`, `resubmit`, `status`, `merge`, `clean`, `run_local` |
| `api/types.py` | Frozen plan/submission/status/merge/local result records with JSON round trips; requests use `JobRequest` |
| `settings/store.py` | `loadconfig(path)`: uncached, read-only loading with defaults repaired in memory |
| `cli/` | Replaces `pico/`: parser, lazy command dispatch, config/install commands and job commands calling the API |
| `scripts/pico.py` | Thin entry point: directory/config setup, parsing and dispatch |
| `workers/` | Renamed worker scripts, Bookkeeper and branch-selection files; callers updated |

- `PicoProducer.from_config(config, reporter, basedir)` accepts the default config, a path, dict or `Config`,
  without writing it. `plan()` writes nothing and marks existing job configs with `conflict=True`.
- File operations temporarily enter the PicoProducer directory and restore it afterwards; **not thread-safe**.
- Reporting is silent by default; `ConsoleReporter` supplies terminal output. Status `complete` uses the merge gate.
- BBB drives the same CLI → API path used by users. API/I/O documentation records side effects and limitations.

**Validation:** 296 job scenarios at verbosity 0–3 matched old output/files/calls; 30 CLI command lines matched
output and exit codes. Direct API checks covered read-only planning, directory restoration, submit/status/merge
artifacts, cleanup and record serialization. Worker-path normalization avoided BBB changes; the harness passed.

### User migration and compatibility

Private imports should change from `TauFW.PicoProducer.processors` to `TauFW.PicoProducer.workers`.
Config channels name worker scripts only and need no change; `pico.py resubmit` rewrites old job lists to `workers/`.

At the user's request, deprecated `processors/` aliases and script forwarders preserve external scripts and old
job lists ([README](../PicoProducer/python/processors/README.md)):

- Import aliases preserve the same Bookkeeper module/classes and emit `FutureWarning` with the replacement.
- Script forwarders preserve arguments, execution context, output and exit status, adding a notice on stderr.
  They also work when the package is not installed in `$CMSSW_BASE/python`.

No in-repo caller uses this layer. **Removal:** delete `processors/` and `Tests/PicoProducer/compat/` once no
pre-2026-10-13 job lists remain in use. Ten offline tests cover aliases, warnings, forwarding and shim coverage.

### B. Command-line and worker fixes

| Bug | Fix / retained behavior |
|---|---|
| P12 | Worker commands use `--opts` rather than relying on argparse prefix matching for `--opt`. |
| P13 | Install dispatch no longer also reports the command as unimplemented. |
| P14 | Install accepts `cmssw`, correcting `cmmsw`. |
| P15 | **Won't fix:** status/merge/cleanup omit submission options; `hadd -m` means `--maxopenfiles`. |
| W01 | **Won't fix:** skim workers accept but ignore `-E/--opts`, keeping a common worker command line. |
| W02 | Corrected picojob's copied skimjob description. |

**Baselines:** `pico.run`/`pico.jobs` were re-locked on lxplus with Part 4 B3. Reviewed differences are only
P08/P09 option order, P10 removal of `-m -1`, and P12 `--opt` → `--opts`. Comparisons against the restructuring
changed only `--opts`; install was checked manually.

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
- **Reporting:** terminal output and `run.log` share Framework/PicoProducer messages; silent reporting is supported.
- **CLI:** `taufw.py plan RECIPE [--local -m N]`, `start RECIPE [--run-root DIR] [--wait --poll S]`,
  `advance RUN_DIR [--wait --poll S]`, `status RUN_DIR`; all delegate to Framework.
- **API boundary:** `PicoProducer.request(**fields)` builds requests without internal imports; PicoProducer loads
  only when constructing a production stage. Recipes are documented in the [analysis guide](../../Analyses/README.md).

### Tests

- 21 offline Framework tests cover stage transitions/retries, merge failures, placeholder blocking, exception
  recording, read-only status, persistence, recipe validation and CLI behavior.
- New lxplus BBB `framework.production` records plan/status, run-state snapshots, resubmission, merged tuples
  and cleanup. Added with the next `bbb lock --replace`, alongside intended `pico.run`/`pico.jobs` changes.
- A Windows integration with real Framework/PicoProducer APIs and fake storage/scheduling reached
  submit → resubmit → merge → BLOCKED at the placeholder, preserving artifacts and `run.log`.

---

## 10. Framework: plots, histograms and fit stages (Part G)

**Date:** 2026-10-13
**Details:** [Framework](../../Framework/README.md), [Fitter bugs](../Fitter/BUGS.md), [Plotter bugs](../Plotter/BUGS.md)

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
  production, plots, histograms, fit; subsets are allowed. See [bundled analyses](../../Analyses/README.md#bundled-analyses)
  and [current limitations](../../Analyses/README.md#current-limitations).

### Bugs fixed on the wrapped path

| ID | Fix |
|---|---|
| F01–F02 | Pass the requested year to JSON merging and ID correction generation. |
| F03 | Input drivers propagate mutau and mumu failures. |
| F04 | Remove the unused required `--input_file` argument and lookup; update callers. |
| F05 | Missing 1-sigma intervals no longer crash parameter-file writing. |
| F06 | Honor impacts options and pass `--impacts` from the workflow driver. |
| F07 | Read rebinned files from their actual output location; lxplus confirmation pending. |
| L01 | Correct misspelled DeepTau branches in `plot.py`. |

Off-path F08–F10 and L02 were registered only.

### Tests

Offline tests cover command parity with existing scripts, process failures/stale outputs, preflight,
fit values and stage/artifact behavior. BBB `framework.production` was re-locked to end DONE rather than
at a placeholder; the other 18 cases were unchanged. Local script stages are outside BBB coverage.

**Pending on lxplus:** plan `Analyses/tes_id_2025`, then compare a VTight/Tight run against shell drivers
in a clean copy, including fit parameter and correction outputs (TODO §1).

---

## 11. Framework: analysis bundles and Python steps (Part H)

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
  the function without importing it; failures show log tails. Multiple steps use unique ids; built-in stages
  remain ordered and unique.
- **Config propagation:** APIs pass `$TAUFW_PICO_CONFIG` to scripts. Loading is read-only; a missing configured file
  is an error, and unset behavior is unchanged. Shared `CommandPlan`/`RunReport` records moved to Utilities.Process,
  with existing API exports retained.

**Limitation:** sample catalogs are not bundled yet; Plotter/Fitter and PicoProducer still resolve their own catalogs.

### Tests

Offline tests cover path resolution, isolated copies, old records, stage ids, initialization and real Python steps
passing artifacts or failing. BBB `framework.production` intentionally changes for bundle/config metadata;
re-lock on lxplus only after other cases pass unchanged. PicoProducer cases must remain unchanged.

---

## 12. Shared code moved to Utilities

Moves from common and Plotter into shared Utilities packages, grouped here with their migration details.

### Parallel processes and the loading bar

**Date:** 2026-10-13
**Details:** [Utilities](../../Utilities/README.md) (Terminal I/O, Parallel Python calls)

Re-implemented helpers in Utilities, updated callers and deleted old modules, preserving logic and terminal bytes.
Utilities does not import `TauFW.common`; old output quirks remain isolated for later cleanup.

#### Migration

| Old | New |
|---|---|
| `TauFW.common.tools.parallel.MultiProcessor(max=...)` | `TauFW.Utilities.Process.ParallelProcessor(max_parallel=...)` |
| `TauFW.common.tools.LoadingBar.LoadingBar(pre=...)` | `CLI.loading_bar(steps, prefix=...)`; advance with `count(message="", steps=1)` |
| `TauFW.common.math_helper` exports | Import `sqrt`, `log10`, `ceil`, `floor` from Python `math` |

Parallel processing retains queue limits, pipe results, `kwret` merging, serial mode and `close()`.
Loading bars retain output characters and formatting options; callers create them when needed to honor redirected stdout.

#### Removals and fix

Removed the unused import-time multiprocessing manager (which broke spawn), unused `Thread` demos,
and public `LoadingBar.update()`/`message()` methods.

Integer-step counting previously crashed on a tuple operation; use `count(steps=n)`.
No in-repo caller used the broken form, so outputs are unchanged.

### Numeric helpers

**Date:** 2026-10-13
**Details:** [Utilities/README.md](../../Utilities/README.md#numeric-helpers)

`common/python/tools/math.py` was re-implemented as the new package `TauFW.Utilities.Math` (`Math/_math.py`), in
the same way as §12: Utilities style, no imports of `TauFW.common`, every caller updated, the old module deleted.
The functions print nothing, so there is no BACKWARD COMPATIBILITY section; the rule here is the same results for the
same inputs.

#### What moved

| Old (`TauFW.common.tools.math`) | New (`TauFW.Utilities.Math`) | Notes |
|---|---|---|
| `frange(start, end, step, scale)` | `float_range(start, end, step, scale)` | Same values, including the first value kept as given (an `int` start stays `int`). |
| `partition(mylist, nparts, nmax)` | `partition(items, parts, max_size)` | Neither given now raises `ValueError` (was `IOError`), same message. |
| `partition_by_max(mylist, nmax)` | `partition_by_sum(values, maximum)` | Same groups. It sorts a copy; the old function sorted the caller's list in place (no caller used the list afterwards). |
| `columnize(oldlist, ncol)` | `columnize(items, columns)` | Same order. The `assert len(parts)>0` could never fail and is gone. |
| `magnitude(x)` | `magnitude(x)` | Unchanged. |
| `scalevec(a, b, r, log)` | `scale_vector(start, end, ratio, log)` | The two log-mode `assert`s are `ValueError`s with the same messages (they no longer vanish under `python -O`). |
| `reldiff(x, y)` | `relative_difference(x, y)` | Unchanged. |
| `sqrt, log10, ceil, floor` (re-exported from `math`) | standard `math` module | Callers that imported `ceil`/`log10` from here import them from `math`. |

#### Dropped

- **`ceil2digit`**: no callers, and it called `log`, which the module never imported (`NameError` on any nonzero input).
- **`round2digit`**: no callers; `Plotter/python/sample/Sample.py` imported it without using it.

#### Callers updated

- `PicoProducer/python/jobs/chunking.py`: `partition_by_sum`, `ceil` from `math`.
- `PicoProducer/python/storage/validation.py` (`itervalid`, `iterevts`): `partition`.
- `Plotter/python/plot/Plot.py`: `magnitude`, `columnize`, `scale_vector`; `ceil`, `log10` from `math`.
- `Plotter/python/sample/Sample.py`: `relative_difference`.
- `Fitter/Zpt/validateZpt.py` and the legacy script `Legacy/OldAnalysis/YearIndependent/plot_GENSIM.py`: `float_range`.
- `Fitter/Zpt/measureZpt.py`: unused `scalevec` import removed.
- `Utilities/IOInventory.md`: the deleted module and the shifted `chunking.py` lines (edited by hand, not regenerated).

### Printf-style table

**Date:** 2026-10-13
**Details:** [Utilities/README.md](../../Utilities/README.md#terminal-io) (`CLI.table`); open items in [TODO.md](TODO.md)

`common/python/tools/Table.py` was re-implemented as `CLI.table(...)`, returning a `Table`
(`Utilities/python/CLI/_internal/table.py`), in the same way as the loading bar in §12. No logic changed: every line is
byte for byte what the old class wrote, and the callers' tables print in the same cases as before. The old quirks are
kept in a section with a new banner, `# ===== LEGACY, CLEAN UP LATER =====`: the four constructor forms told apart by
argument types, the header always underlined with raw ANSI codes (even into a file), the old `LOG.warning` text for
the two warnings, and the two debug lines at high verbosity. They are listed in [TODO.md](TODO.md) for a later commit
with an explicit output change.

#### What moved

| Old | New | Notes |
|---|---|---|
| `LOG.table(*formats, verb=0, level=0, pre=">>> ", ul=True)` | `CLI(verbosity=verb, prefix=pre).table(*formats, minimum_verbosity=level, underline=ul)` | `CLI()` is created where the table is made, so a redirected stdout is honored. Formats as before: `(row_format)`, `(header_format, row_format)`, `(ncols)`, `(ncols, colwidth)`. |
| `Table.printheader(*titles, post="")` | `print_header(*titles, suffix="")` | |
| `Table.printrow(*values)` | `print_row(*values)` | Fewer values: only the first columns; extra values: appended with spaces. |
| `Table.printtable()` | `print_rows()` | Prints the lines kept with `save=True`. |
| `Table.header(...)`, `Table.row(...)`, `str(table)` | unchanged | `save=True` kept. |
| `LOG.tableheader()`, `LOG.row()` | removed | No callers. |

`Table.py` and `log.py` imported each other (`log.py` imported `Table` at its end, `Table.py` imported `LOG` at its
end). The table no longer needs `LOG`: its two warnings write the old `LOG.warning` bytes themselves.

#### Callers updated

- `Plotter/python/plot/utils.py`: six tables (`printhist`, the ratio and error tables), most at `minimum_verbosity=3`.
  `printhist(**kwargs)` maps its `verb`, `pre`, `level` and `ul` keywords as `LOG.table` did. The table in the
  `TGraph`/`TGraph` ratio branch prints its rows with `print_header` (it did with `printheader` before); kept as is and
  listed in [TODO.md](TODO.md).
- `Plotter/python/sample/HistSet.py` (four tables), `Fitter/python/plot/datacard.py` (`createinputs` event table).
- `common/python/tools/log.py`: `Logger.table`, `tableheader`, `row` and the `Table` import removed.
- `Utilities/_audit_io.py` counts `print_header`/`print_row`/`print_rows` as terminal output, like the old names.
  `Utilities/IOInventory.md`: the rows of the changed files and the totals, edited by hand (not regenerated).

### Drawing library

**Date:** 2026-10-14
Moved Plotter's drawing code to `TauFW.Utilities.Drawing` so Fitter and PicoProducer can draw without
importing Plotter. Pipeline stages share libraries instead of importing each other.

#### The move

`Utilities/python/Drawing/` (`TauFW.Utilities.Drawing`). The code moved as it was: function bodies are unchanged and
keep the Plotter's 2-space style; only imports changed, plus the `Variable` checks below. Modernizing it is listed in
[TODO.md](TODO.md) ("Drawing library").

| Old | New | Notes |
|---|---|---|
| `Plotter/python/plot/{Plot,Plot2D,Stack,Ratio,CMSStyle}.py` | `Utilities/python/Drawing/` (same names) | `git mv` |
| `Plotter/python/plot/utils.py` | `Utilities/python/Drawing/hist_tools.py` | `git mv`; `LOG` now comes from the package |
| `Plotter/python/sample/SampleStyle.py` | `Utilities/python/Drawing/SampleStyle.py` | `git mv`; owns the `Logger('Sample')` object |
| `Plotter/python/plot/string.py`, lines up to `match` | `Utilities/python/Drawing/labels.py` | `var_dict`, `makelatex`, `maketitle`, `makehistname`, `makefilename`, `getobjname`, `estimatelen`, `match`; copied byte for byte. `getselstr` and the selection helpers (`joincuts`, `invertcharge`, `shift`, `filtervars`, ...) stay in `string.py`, which imports the label names back for its star-importers |
| `LOG = Logger('Plot')` in `plot/utils.py` | `TauFW.Utilities.Drawing.LOG` | the same single object for the drawing code and the Plotter |
| `TauFW.common.tools.log` (`color`, `underline`, `header`, `Logger`) | `Drawing/_internal/legacy_log.py` | verbatim copy (Utilities must not import `common`); only `past.builtins.long` is gone, the same as `int` on Python 3 |
| `isnumber`, `islist`, `ensurelist`, `unpacklistargs`, `quotestrs`, `repkey` from `common` | `Drawing/_internal/legacy_helpers.py` | verbatim copies, generated from the `common` sources |

How the output stays the same:

- **One logger object, as before.** The Plotter's `Variable`, `Selection`, `Context` and `string` take `LOG` from
  `TauFW.Utilities.Drawing`, and `Plotter/python/sample/utils.py` takes its `LOG` from `SampleStyle`, so scripts that
  set `PLOG.verbosity`/`LOG.verbosity` still set it for all the code that printed through those objects.
- **One module object per stateful module.** `CMSStyle` (lumi text), `SampleStyle` (color tables) and `hist_tools`
  (the `TGraph` patch) are imported from one place only; no old import path is left in the repository.
- **`Variable` by duck typing.** The library does not import the Plotter. `Plot` and `Plot2D` used
  `isinstance(x, Variable)` (5 places); they now call `hist_tools._is_variable(x)`: true for an object with `getedge`,
  `dividebins` and `binlabels`, which only the Plotter's `Variable` has. `Plot` no longer re-exports `Variable`/`Var`;
  the 4 callers import them from `TauFW.Plotter.plot.Variable`.
- Names the drawing modules no longer re-export, and where their callers get them now: `ensuredir`
  (`TauFW.common.tools.file`), `ensureTFile`, `Logger`, `moddir` (no caller used them through the drawing modules).

#### Callers updated

About 55 files, imports only: the Plotter (`sample/`, `plot/Variable|Selection|Context|string`, `plot.py`,
`plot_postfit*.py`, `plot_v10.py`, `tutorial/`, `Legacy/`, `python/legacy/`), the Fitter (`python/plot/`,
`createinputs*`, `Zpt/`, `tutorial/`, `ETauFR/Plotter/`, `plot_measurements.py`), PicoProducer
(`utils/compare{Nano,Pico}.py`, `data/pileup/getPileupProfiles.py`) and `Legacy/OldAnalysis/`.
`Utilities/IOInventory.md`: the rows of the 7 moved files are gone (the audit does not scan Utilities), and line
numbers of the touched callers are updated; merged into the hand-edited file, not regenerated.

Drawing's `hist_tools.py` preserves the previous `TNamed.__repr__` patch in its legacy block,
keeping printed ROOT object representations unchanged without importing common.

### ROOT expression helpers

**Date:** 2026-10-14

`Plotter/python/plot/string.py` held three kinds of helpers: label helpers (moved to `Drawing/labels.py` in §12),
helpers that know pico branch names (`shift`, `undoshift`, `shiftjme`, `invertcharge`, `filtervars`), and helpers for
ROOT selection and weight expressions that know only the C++ syntax. The last group moves to a new package, so that
the Fitter can build cuts without importing the Plotter (`Fitter/python/plot/datacard.py` imported `joincuts` from it).

Not `Utilities/Root`: Utilities packages are named by their job, not by a dependency; ROOT file IO already belongs to
FIO; and these helpers do not import ROOT. Not the future Utilities string module either (TODO §2): those helpers treat
text as text, these know ROOT's syntax.

| Old (`TauFW.Plotter.plot.string`) | New |
|---|---|
| `getselstr`, `joinweights`, `joincuts`, `replacepattern`, `doubleboolrexp`, `cleanbool` | `Utilities/python/Expressions/_expressions.py`, moved verbatim (2-space style kept) |
| | `Utilities/python/Expressions/__init__.py` exports the five functions (`doubleboolrexp` stays private) |

`plot/string.py` imports the five names back, as it does for the label helpers, so its star-importers (`Variable`,
`Selection`, `Sample`, `MergedSample`, `config/samples*.py`) see the same objects. `doubleboolrexp` is no longer in its
namespace; nothing in the repository used it (legacy code included). `LOG` is still the drawing logger
(`TauFW.Utilities.Drawing.LOG`; its package `__init__` does not import ROOT), so warnings are unchanged.

Callers updated: `Fitter/python/plot/datacard.py:15` (`from TauFW.Utilities.Expressions import joincuts`).
`Utilities/IOInventory.md`: the `string.py` row (regenerated before and after in a scratch copy, the one changed row
replaced in the hand-edited file). `Utilities/README.md`: new section "ROOT selection and weight expressions".

Three latent bugs are registered, not fixed: [Plotter BUGS](../Plotter/BUGS.md)
L05 (`joinweights` with a weight `0` raises `TypeError`), L06 (`replacepattern` applies only the last of several
patterns), L07 (`joincuts` does not bracket `(x)||y`).

### Tests

Tests have been implemented.

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

## 15. Framework: explicit stage ids, inputs and recipe validation

**Date:** 2026-10-14
**Details:** [Analyses](../../Analyses/README.md) "File format and validation", [Framework](../../Framework/README.md)

First step of the recipe IO work: the recipe, not the Framework, says which stage reads which stage's output, and every
problem of a recipe is shown at once. Run behaviour is unchanged otherwise (outputs still go to the module directories;
per-run output directories are the next step, TODO §6 C).

### What changed

- **Every stage has `stage`, `id` and `inputs`, and may have `description`.** `id` is required for every stage and any
  stage may have any id (the old rules "a built-in stage's id is its name" and "a python step's id defaults to its file
  name" are gone). Ids that the run directory uses are reserved (`bundle`, `logs`, `run.json`, `run.log`;
  `defaults.RESERVED_STAGE_IDS`). `description` is free text, shown by `plan` and the menu, used for nothing else.
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
`framework.production` (`Tests/BBB/cases.py`) gets `id: production` and `inputs: null`; its `plan` output changes on
purpose (`=== Stage production (production) ===` and a new `Inputs: none` line): re-lock on lxplus once every other
case passes unchanged.
