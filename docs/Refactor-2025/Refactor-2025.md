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
| 16 | [Framework: run directory with logs/ and stages/, stage manifests](#16-framework-run-directory-with-logs-and-stages-stage-manifests) |

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
**Details:** [Framework](../../Framework/README.md), [Fitter bugs](../Fitter/BUGS.md), [Plotter bugs](../Histogrammer/BUGS.md)

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

Three latent bugs are registered, not fixed: [Plotter BUGS](../Histogrammer/BUGS.md)
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
recorded `run.json` (`id`, `inputs` keys). Re-lock on lxplus once every other case passes unchanged.

---

## 16. Framework: run directory with logs/ and stages/, stage manifests

**Date:** 2026-10-15
**Details:** [Framework](../../Framework/README.md) "Run directory", [Analyses](../../Analyses/README.md) "Outputs and logs"

Second step of the recipe IO work (R2): a stage's directory in the run now holds only what the stage makes, so the
next step can run the Plotter and Fitter scripts inside it (TODO §6 C).

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
`framework.production` records `run.json`, so `"schema": 2` adds to the §15 difference: one re-lock for both.

---

## 17. Framework: Plotter and Fitter outputs in the run directory (R3)

**Date:** 2026-10-15
**Details:** [Framework](../../Framework/README.md) "Run directory", [Analyses](../../Analyses/README.md) "Stage
options" and "Outputs and logs", [scripts_arg_changes.md](scripts_arg_changes.md), Fitter BUGS F11-F24, Plotter
BUGS L08-L11

Third step of the recipe IO work: the plots, shapes and fit results of a run go to its stage directories, so runs
no longer overwrite each other in `Plotter/` and `Fitter/`, and the summary scripts no longer pick up the working
points of other runs. Plan and inventory of what the scripts read and write: `LocalR/architecture/10-r3-plan.md`.

### What changed

- **The Framework decides where a stage writes.** `LocalStage.output_dir(context)` is `<run_dir>/stages/<id>/`
  (absolute; `'<run_dir>/stages/<id>'` in a plan). The plots, histograms and fit stages pass it to their module API
  as `outdir`; the fit also gets `shapes_dirs`, the directory of each point's shapes, from the shapes artifacts of
  its input stage (a recipe point without shapes there fails the stage before anything runs). There are no links
  and no copies. `taufw.py plan` shows `Commands run in: <era>` for the fit.
- **Module APIs** (`PlotsRequest`, `ShapesRequest`, `FitRequest`: new `outdir`; `FitRequest.shapes_dirs`). Without
  `outdir` the commands are exactly those of the shell scripts, in `Plotter/` and `Fitter/` (the existing API tests
  are unchanged). With it the scripts run there (the fit in `<outdir>/<era>/`, because several of its outputs have
  no era in their names), scripts and configs are given as absolute paths, `$TAUFW_PICO_CONFIG` is absolute, the
  directories inside the working directory stay relative as in the shell scripts (several scripts derive one from
  another with `str.replace` on the whole path, Fitter BUGS F18), and a few options keep every output inside it
  ([scripts_arg_changes.md](scripts_arg_changes.md)). Preflight refuses a non-empty output directory (an
  interrupted attempt) and a relative `picodir` (`TauFW.Utilities.Process.output_dir_problems`).
- **Scripts** (defaults unchanged): `makecombinedfitTES_SF.py --output_dir --plot_dir` (passed on as
  `harvestDatacards_TES_idSF_MCStat.py --output_dir` and `plot2DScan_MultiDimFit.py --outdir`),
  `make_tid_2025.py --sf-dir`; paths found from `__file__`: `plot.py` macro (L11), `createinputsTES.py` sample
  config (F16), the two sub-scripts of `makecombinedfitTES_SF.py` (F15); `harvestDatacards_zmm.py` default output
  directory (F14).
- **Artifacts:** paths inside the stage directories. Plots: `nfiles` counts only this run's plots, with the setup's
  tag (L08, L09); `plan` notes two setups that write the same file names (L10). Fit: the correction files of other
  taggers are no longer listed (F22); with the summary step, a second `corrections` artifact per era for the
  combined TES + ID file of `make_tid_2025.py` (`combined: true`); expected outputs added for
  `plot_measurements.py` and `make_tid_2025.py`.
- **Input slots and null:** a stage lists the slots that may be `null` and what `null` means
  (`Stage.null_inputs`); `null` elsewhere is a recipe error, and `plan` shows the meaning. The fit's
  `{shapes: null}` (the shapes in `Fitter/`) is a documented temporary exception.

### Tests

On Windows: Framework 94, Plotter API 11, Fitter API 18, Utilities process 17 pass. New cases: the commands, working
directories, artifacts and preflight problems with an output directory (both APIs), two eras in two directories, a
point without shapes in the input stage, null shapes reading `Fitter/`, a slot that does not allow null, the
output-directory check. On lxplus (2026-10-15, the 2025 tuples of the TauFW group area): the Plotter part passes
(the same plots as `plot.py` in `Plotter/` before and after the change, `dm_2_label` drawn outside `Plotter/`,
`nfiles` equal to the files, nothing in `Plotter/plots/`), and `bbb check` passes unchanged (20 cases). The Fitter
part passes for VTight/Tight: the shell scripts with the new code and their defaults give the baseline's
`FitparameterValues__mutau_*` and correction files exactly; the Framework's shapes equal the baseline's up to 1e-13
(multithreaded RDataFrame); on the same shapes the Framework fit and the shell scripts give identical fit values and
correction files; nothing is written to `Fitter/` or `Plotter/`. Two runs of shapes + fit from the same tuples can
differ by a grid step in the fitted POIs (the fit amplifies the 1e-13 differences; TODO §6 C). Details in
[scripts_arg_changes.md](scripts_arg_changes.md).

## 18. Framework: tuples as an input, production writes into the run, run_root

**Date:** 2026-10-17 (steps 1-8 done; the end-to-end production check passed on lxplus, TODO §1)
**Details:** [Framework](../../Framework/README.md) "Concepts" and "Run directory", [Analyses](../../Analyses/README.md)
"Where the runs go (`run_root`)", [scripts_arg_changes.md](scripts_arg_changes.md) "Tuple location", Framework BUGS
K04, K05, K07, PicoProducer BUGS S17, Plotter BUGS L12

The Framework, not the global `$PICODIR`, decides where the pico tuples are read and written, and everything is
visible in the recipe. Plan, decisions D1-D13 and steps: `LocalR/architecture/12-tuples-plan.md`.

### Step 1: recipe warnings and `run_root`

- **Warnings.** A recipe can have warnings besides its problems: what it should change, though it runs
  (`recipe_warnings`, `Recipe.warnings`, `RecipeCheck.warnings`). `taufw.py check` prints them and still exits 0;
  `plan` and `start` print them first (`start --run-root` skips the `run_root` ones); the menu preview lists them
  under the problems, and the recipe is not red.
- **`run_root`** (new top-level key): the parent directory of the runs. `start --run-root` takes precedence; without
  both the runs go to `taufw_runs/` in the working directory, as before, with a warning. It must be absolute (also
  `/afs/...` on Windows, K05) and not a URL; `~` and `$VARIABLES` are expanded where `taufw.py` runs, with a
  warning (an undefined variable is a problem); it must be outside the bundle directory, which every run copies.
  `plan` and `start` print the directory they use and where it comes from. `run.json` keeps it as written.
- **Write check.** Before `start` with a given run root (recipe or `--run-root`), and before every `advance`, the
  Framework writes and removes a small file in the run root (in its nearest existing parent if it does not exist yet)
  or in the run directory; if that fails, `RunDirectoryError` and nothing is started or moved (`taufw.py` prints
  the reason, exit 1).
- **Menu:** "Continue an existing run" also lists the runs in the `run_root` of every recipe in `Analyses/`.
- The example recipes explain `run_root` in a comment and leave it unset (they warn).

Tests (Windows): Framework 104 (new: run_root accepted, expanded, refused in seven ways, not set; precedence and
default; write check at start and advance, nothing left behind; `check`/`plan`/`start` output; menu run roots and
warnings), Utilities menu 28 (warnings in the preview). Plotter API and Fitter API unchanged.

### Step 2: `--tuples` for the scripts

- `getsampleset(..., tuples=PATTERN)` (`Plotter/python/sample/utils.py`): the directory pattern of the tuples
  (`$ERA`, `$GROUP`) instead of `$PICODIR` of the PicoProducer configuration, which is then not read. Without it,
  unchanged.
- `plot.py --tuples PATTERN` and `createinputsTES.py --tuples PATTERN` pass it on; without the option both behave as
  before (shell scripts, standalone use). The APIs do not pass it yet (step 3).
- New test `Tests/Plotter/testTupleLocation.py` (ROOT, lxplus): MC, the merged data glob and a variation are found in
  the given directory without reading the configuration; the default still reads it. Listed in
  `Tests/inventory.json` and `check_harness.py`.
- `Analyses/README.md`: the statements that Plotter/Fitter outputs are shared between runs, that `--run-root` does
  not isolate them, that an interrupted stage simply reruns and that the summary picks up other runs' working
  points were left over from before R3 (CL §17) and are corrected.

### Step 3: `tuples` in the Plotter and Fitter APIs

- `PlotsRequest.tuples`, `ShapesRequest.tuples` (default `None`: unchanged). With a pattern every `plot.py` /
  `createinputsTES.py` command gets `--tuples PATTERN`, no `$TAUFW_PICO_CONFIG`, and preflight does not look for a
  PicoProducer configuration. `FitRequest` has no field: the fit reads no tuples.
- Preflight of a pattern (`TauFW.Utilities.Process`): `output_dir_problems(outdir, pico_config, tuples=)` checks the
  pattern instead of the configuration's `picodir` (relative: a problem); `tuple_pattern_problems(tuples)` refuses
  `$KEYS` the scripts do not fill (e.g. `$DAS`).

Tests (Windows): Plotter API 12, Fitter API 19, Utilities 104 (2 skipped), Framework 104; the existing API tests are
unchanged. `Tests/Plotter/testTupleLocation.py` passes on lxplus.

### Step 4: PicoProducer writes where the request says

- `JobRequest.tupledir` (default `None`; `pico.py` never sets it): `merge` writes the tuples to
  `<tupledir>/$ERA/$GROUP/<sample>_<channel><tag>.root` instead of `picodir` of the configuration. The layout below
  the directory is PicoProducer's (`TUPLE_LAYOUT = "$ERA/$GROUP"` in `jobs/merge.py`); the caller gives only the
  directory.
- `PicoProducer.tuple_pattern(request)`: where `merge` writes, as a pattern with `$ERA`, `$GROUP` (the tupledir
  layout, absolute; or the configuration's `picodir`, made absolute against the PicoProducer directory if relative).
  Reads nothing. The Framework will record it on the tuple artifacts (step 5).
- `merge_sample(..., picodir=None)`: the pattern to merge into (None: the configuration's, as before).
- `pico.py` and the `pico.*` BBB cases are unchanged; `docs/PicoProducer/API.md` lists the field and the method.
- New test `Tests/PicoProducer/testTupleDir.py` (lxplus; no batch system, no files): `tuple_pattern` for a
  tupledir and for absolute, relative, `$` and URL picodirs; `merge_target` below a tupledir; `merge_sample` merges
  into the given pattern, else into the configuration's.

### Step 5: production writes its tuples into the run

- `ProductionStage.request(spec, context)` sets `tupledir` to the stage's directory `<run_dir>/stages/<id>/`
  (absolute) whenever there is a run; the merged tuples go to `<era>/<group>/<sample>_<channel><tag>.root` below it.
  `plan` (no run yet), `status` and `plan --local` set nothing. `run.json` keeps the recipe's request as before.
- Every tuple artifact (`run.json`, `manifest.json`) gets `pattern`: `PicoProducer.tuple_pattern(request)`, i.e.
  `<run_dir>/stages/<id>/$ERA/$GROUP`. `kind` is still missing (K04, not fixed).
- `Stage.planned_artifacts(spec, plan, context)`: what the later stages see in a plan (default: the plan's
  `artifacts`). Production gives one `{pattern: '<run_dir>/stages/<id>/$ERA/$GROUP'}`, from the layout PicoProducer
  publishes (`PicoProducer.TUPLE_LAYOUT`).
- The `run_root` warning of a recipe with a production stage says that its tuples fill the run directory.
- Not yet connected: plots and histograms still read `$PICODIR` (step 6), so a production stage followed by plots
  in one run reads the wrong place until then. A run started before this step merges into the stage directory too.
- BBB `framework.production` changes (tuple paths in the run, `pattern`): re-lock.

Tests (Windows): Framework 107 (new: tupledir in every request of a run and none without, artifacts and manifest with
the pattern, planned pattern seen by a later stage, production warning text).

### Step 6: plots and histograms read the tuples their input names

- A `tuples` input may name tuples made outside TauFW: `{tuples: {external: <pattern>}}` (absolute, not a URL, no
  `~` or `$VARIABLE` at the start; only for tuples slots). `StageSpec.external` holds the patterns,
  `StageSpec.connections` gives `None` for them (the graph checks are unchanged), `StageContext.external` passes
  them to the stage. `check` reports a missing directory (the pattern's part before its first `$`).
- `LocalStage.tuples_pattern(context)`: the external pattern, or the one `pattern` on the artifacts of the production
  stage the input names (in a plan: the planned `<run_dir>/stages/<id>/$ERA/$GROUP`); artifacts without a pattern (a
  production finished before step 5) or with several are a preflight problem. `null` gives none.
- Plots and histograms pass it to their API (`tuples=`, so the scripts get `--tuples`) and then no
  `pico_config`; preflight (`input_problems`) checks that the production tuple files exist, or the external
  directory. `last_status` records `tuples` (the pattern). `null` is unchanged (old recipes: `$PICODIR` of the
  PicoProducer configuration, `$TAUFW_PICO_CONFIG`).
- `taufw.py plan`: `Inputs: tuples <- external <pattern>`; the commands show `--tuples`. The plan's placeholder
  pattern (`<run_dir>/...`) is not a "relative pattern" problem (`TauFW.Utilities.Process.output_dir_problems`).
- `Analyses/tes_id_2025` names the TauFW group's 2025 tuples with `{external: ...}` (one YAML anchor, two inputs).
- K03 is fixed. The TODO item "production at most once" is updated: its remaining reasons are the shared job files,
  the run's single PicoProducer configuration, and a slot that names one stage.

Tests (Windows): Framework 114 (new: external accepted and refused in eight ways, `check` of its directory, the
pattern reaching both APIs without `pico_config`, a missing external directory leaving the stage NEW, `null`
unchanged, the planned pattern in a plan, artifacts without or with several patterns, missing tuple files,
`fixed_directory`, the `Inputs:` line; the production tuples now exist in the fake run), Utilities 104.

On lxplus (2026-10-17): `check` and `plan` of tes_id_2025 as expected (`--tuples` with the external pattern, no
`$TAUFW_PICO_CONFIG` for plots and histograms). `plan` of example_mutau stops in the plots preflight: the APIs' module
lookup `importlib.util.find_spec('ROOT')` raises when production has already imported CMSSW's ROOT (Plotter BUGS L13,
Fitter BUGS F25; registered, older than this work). The warnings were printed as "Warning: Warning: ..." (fixed).
The plots run with `{external: ...}` (mutau 284 s, mumu 1133 s) made the same 8 plots as the R3 check and recorded
the pattern; a read-only `--run-root` stopped before anything was made. BBB `framework.production`: the case now
snapshots the merged tuples in `stages/production/` and masks the run ID (part of the tuple paths) in `run.json`;
re-locked on lxplus: only this case changed (tuple paths, `pattern`, the manifest next to the tuples, the
`run_root` lines of `plan`; the merged tuples are byte-identical), then `bbb check` 20/20.

End to end on lxplus (2026-10-17, TODO §1): `~/tuples_test/prod.yml`, a production of one sample
(`DYto2TautoMuTauh_M-50`, 2022_postEE, mutau, 4 jobs, `max_tries: 2`, `merge.clean: true`) followed by plots
(`{tuples: production}`, mutau, `m_vis`, baseline), run `prod_test_20261017-023321`. The first 4 jobs were held
for lack of a grid proxy ("reading from file /tmp/x509up_u<uid>: No such file"): the HTCondor template asks for one
(`use_x509userproxy = true`) and the schedd cannot read the `/tmp` of the login node. The Framework saw the held
jobs as missing, so that try was spent. With the proxy on AFS (`voms-proxy-init --voms cms --out
~/private/x509up`, `export X509_USER_PROXY=...`) and the held cluster removed (`condor_rm`), `advance` resubmitted
them (try 2 of 2) at 02:44; they ran 161-255 s each (exit code 0) and were done before 02:52. The next `advance`
merged the 4 chunks from the configuration's EOS outdir with `hadd` into
`<run_dir>/stages/production/2022_postEE/DY/DYto2TautoMuTauh_M-50_mutau.root` (16 MB, written 02:56), removed the
chunks, and recorded one `pattern`, `<run_dir>/stages/production/$ERA/$GROUP`. Plots passed preflight, and
`plot.py --tuples` stopped after 4 s at the first sample that was not produced,
`<run_dir>/stages/production/2022_postEE/DY/DYto2L-4Jets_MLL-50_mutau.root`: inside the run, not `$PICODIR`, as
intended. The run ends FAILED by design until the sample list is part of the recipe (TODO §6; `samples_v15.py`
has the produced sample commented out). Found on the way, registered only: PicoProducer BUGS S17 (`loadjson` drops
`store`, so a spurious "DAS path ... has wrong format" warning on every `status`/resubmit), Framework BUGS K07
(`status` shows the last `advance`'s message next to a live job table that says complete); a proxy check before
production submits is an idea in TODO §6.

### Fix on the way: Plotter L13, Fitter F25

An exception to "no bug fixes until the refactor is finished", in its own commit: the Plotter and Fitter APIs asked
`importlib.util.find_spec('ROOT')` whether ROOT can be imported, which raises `ValueError` once CMSSW's ROOT is
imported in the process (its `__spec__` is None). Every recipe with a production stage before plots or histograms
crashed in `taufw.py plan` and in the preflight of a run. The default lookup is now `_module_exists`: a module that
is already imported counts as found (a blocked one, `None` in `sys.modules`, does not); otherwise `find_spec`, and a
missing parent package means not found. No output changes.

Tests (Windows): Plotter API 13, Fitter API 20 (an imported module without `__spec__`, a blocked one, a missing one
and a missing parent package).

### What is left (TODO)

- TODO §1: production end to end in the run passed (above); plots after a production in the run finish only once the
  sample list is part of the recipe.
- TODO §6: the `null` warning (and the production `tag` warning), production job files in the run, EOS as
  `run_root`, the sample list in the recipe, a grid proxy check before production submits; R4 next.

## 19. Framework: inputs from another run's stage directory, repeated stages (R4)

**Date:** 2026-10-17 (Windows tests pass; checked on lxplus, TODO §1 "R4 on lxplus")
**Details:** [Analyses](../../Analyses/README.md) "File format and validation" (stage order, "Inputs from another
run"), "Outputs and logs", "Troubleshooting"; [Framework](../../Framework/README.md) "Run directory"; TODO §6
"Revise: one rule for the paths in a recipe"

The last part of the recipe IO work (R1-R3, CL §15-17; tuple locations, CL §18): a stage may read the output of
another, finished run, and the built-in stages may repeat. Plan and decisions: `LocalR/architecture/11-r4-plan.md`
(§9, §11).

### Repeated stages, no fixed order

- `plots`, `histograms` and `fit` may appear any number of times, each with its own id (e.g. a histograms + fit
  pair per set of working points). The fixed order production -> plots -> histograms -> fit is no longer a rule:
  the stages run in the order of the recipe (the user's choice), and the only order rule is that an input names a
  stage written above it. `production` stays at most once (its job files are outside the run, and a run has one
  `pico.config`; TODO §6). Nothing else needed a change: artifacts, directories, run.json, the menu and `status`
  were already keyed by stage id, and since R3 every stage writes in its own `stages/<id>/`.
- `ORDER` (`stages/__init__.py`) is kept only to list the known stages in messages.

### Inputs from another run: `{path: <stage directory>}`

- **Recipe.** Any input slot (python steps included) may be `{path: <run_root>/<run>/stages/<id>}`. The value is
  kept as written and must be absolute: relative paths are refused, `~` and `$VARIABLES` are not expanded (unlike
  `run_root`), URLs are refused, and a path inside the bundle is refused (data is never part of a bundle). The rules
  of the paths in a recipe are to be unified in a later session (TODO §6). `StageSpec.paths` gives slot -> directory;
  `connections` still gives only stage ids.
- **Manifest format 2** (`python/manifest.py`, new; the writer moved from `framework.py`): adds `stage_dir` (where it
  was written, absolute) and `sources`. `read_stage_dir` returns a `StageDir` or raises `ManifestError`: no directory,
  no manifest (the stage is not `DONE`), unreadable JSON, another format (format 1 manifests of earlier runs are
  refused, no conversion), missing keys, or a directory that is not its `stage_dir` (moved or copied: its artifacts
  name the files of the old place). Only a manifest-backed (`DONE`) directory is accepted; a module directory such
  as `Fitter/` is not.
- **Checks.** `validation.read_source` adds the kind rule (the source's stage must make the kind of data the slot
  takes; a python step as source or reader is not checked). `taufw.py check` and the menu report every problem at
  once; `plan` shows it as the stage's note; in `advance` it stops the stage like a preflight problem (`NEW`, message
  and history), checked in `_advance_stage` so that the message is kept.
- **Framework.** The artifacts come from the manifest, never from the other run's `run.json`, and nothing is written
  to or copied from the source. Inside the Framework the slot is keyed by the directory (`StageContext.inputs` and
  `upstream`), so the stages use the artifacts as those of a stage of the run: the fit's points and shape
  directories, the production pattern for `--tuples`, `ctx.input()` of a python step. (A slot left as `None` would
  have looked like `null`, and the fit would have read `Fitter/`.) New `StageContext.sources`, `StagePlan.sources`,
  `StageContext.input_name` (messages name the directory).
- **Provenance.** `StageRecord.sources` (slot -> `{path, run_id, stage_id, stage, finished, manifest_sha256}`),
  written at every step of the stage, so a `DONE` or `FAILED` stage keeps what it read; `{}` without such inputs. The
  reader's own manifest has the same `sources`. **run.json schema 3** (schema 2 runs are refused).
- **`taufw.py plan`:** `Inputs: shapes <- <dir> (run <id>, stage <id> (<type>), finished <time>)`.
- **Fit.** The shapes on disk are checked in the preflight also for a `{path}` input (as for `null`). The fit's
  `{shapes: null}` stays, for old recipes only (a warning is a TODO §6 item).
- **Fitter API.** `FitRequest`: with `outdir`, a non-empty `shapes_dirs` must name every point (`ValueError`
  otherwise); empty still reads `Fitter/` (the Framework's `null`). Without `outdir` (standalone, shell) nothing
  changes. This is a safety rule: the Framework already refuses a point without shapes.

Tests (Windows): Framework 131 (repeated stages and order; `test_manifest.py`; `{path}` syntax and the bundle
rule; `check` of missing, unfinished, copied and wrong-kind directories; a fit, plots and a python step reading
another run; an unreadable source leaves the stage `NEW` and runs once it is fixed; the source is not touched;
`sources` in run.json and the manifest; schema 2 refused; the `Inputs:` line), Fitter API 21, Plotter API 13,
Utilities 107.

On lxplus (2026-10-17):
- `bbb check`: 19 cases unchanged; `framework.production` differed only in `schema` (2 -> 3) and the new `sources`
  of its stage record (started, resubmitted, done), so it was re-locked (`framework.production.json` and the BBB
  `manifest.json`, one line each). `check` and `plan` of `Analyses/tes_id_2025` as before.
- **Fit on another run's shapes.** Source: the R3 run `r3_fit_20261016-142346` (`~/r3_test`), whose
  `stages/histograms/manifest.json` (format 1) was turned into format 2 by a test script that adds only `manifest`,
  `sources` and `stage_dir` (original kept outside the run; the diff shows only these three keys). A fit-only recipe
  `{shapes: {path: <R3 run>/stages/histograms}}` with the R3 fit's options (defaults): `check` without problems;
  `plan` shows `shapes <- <dir> (run r3_fit_20261016-142346, stage histograms (histograms), finished 2026-10-16
  17:53:30)` and no preflight note; its 13 commands equal those in the R3 fit's command logs (only the interpreter's
  spelling differs: `python3` against its resolved path). Run `r4b_fit_20261017-133018`: DONE in about 15 min
  (multidimfit 203 s, fitdiagnostics 656 s). The 12 `FitparameterValues__mutau_*` files and the JSON corrections
  (`tau_sf/*.json`, the merged and the combined JSON) are byte-identical to the R3 fit's; the two `tau_sf/*.root`
  files differ in bytes only (ROOT's header), their 12 objects each have the same content. The source directory is
  unchanged (its 44 files, sizes and modification times before and after). `run.json` has schema 3 and
  `sources.shapes` with the run, stage, finish time and `manifest_sha256` equal to `sha256sum` of the source
  manifest; the fit's own manifest is format 2 with its `stage_dir` and the same `sources`.
- **Repeated stages:** a recipe with two plots stages (`plots_mvis`: `-V m_vis`, `plots_pt`: `-V pt_1`; 2025 mutau,
  `{external}` tuples), run `r4_two_plots_20261017-134232`: both DONE, each in its own directory with its own plots
  (`mvis_*` in `stages/plots_mvis/plots/2025/`, `pt_1_*` and `jpt_1_*` in `stages/plots_pt/plots/2025/`; plot.py's
  `-V` matches by pattern, as in the shell).
- **Refused:** one `check` of a recipe with four fits listed all four problems: a missing directory, `Fitter/` (no
  manifest), a `cp -r` copy of the R3 histograms directory ("was moved or copied from ..."), and the R3 plots
  directory (manifest converted for the test, then restored) for a fit ("it makes plots, not shapes").
- **Tuples from another run:** the CL §18 production run `prod_test_20261017-023321` (its manifest converted the
  same way, then restored): `check` of a plots recipe with `{tuples: {path: <run>/stages/production}}` without
  problems; `plan` shows the source on the `Inputs:` line and gives `plot.py --tuples
  '<run>/stages/production/$ERA/$GROUP'`. Running it waits for the sample list in the recipe (TODO §6).

### What is left (TODO)

- TODO §1: plots on another run's tuples finishing awaits the sample list in the recipe.
- TODO §6: one rule for the paths in a recipe; the `null` warning; production repeating; the sample list next.


## 20. Menu: commands run beside the screen; the test screen

**Date:** 2026-10-17 (Windows tests pass; lxplus check in TODO §1 "Test screen on lxplus")

The menu should work like a program: an operation must not print into the terminal or block the screen. So a long
operation runs as its own process (the existing CLI command, unchanged) beside the screen: same machine, user,
environment and working directory, but stdin is `/dev/null`, stdout and stderr go to a log file, and the command
reports its progress as events in a second file. The screen follows both files. Only this keeps the screen intact:
ROOT and C++ write to the file descriptor, which no Python redirection catches. This section builds that
infrastructure and moves the tests onto it; the run screens (start, advance, status) come later.

### Infrastructure (`TauFW.Utilities.Process`)

- `_events.py` (new): the event protocol, one JSON object per line `{"t": <unix time>, "kind": ...}`. `EventWriter`
  opens, appends and closes the file per event (AFS shows a change to other machines only after a close).
  `EventReader` and `LogTail` continue where they stopped, keep an unfinished last line, read at most 1 MB per call
  and start again after a truncation; `LogTail` keeps at most `maxlines` lines (no memory growth on long runs) and
  handles `\r` progress bars and UTF-8 split between reads. The file is named by `$TAUFW_EVENTS`.
- `_background.py` (new): `BackgroundProcess.start(argv, cwd, log, events, env)`: its own session (process group),
  output straight into the log (no pipe that could fill and block the command), `poll()`, `cancel()` (SIGINT to the
  group, SIGTERM after 3 s, SIGKILL after 8 s), `close()` (a failing screen leaves nothing running). Exit code: the
  command's, 128+N after signal N, 130 when cancelled. `$TAUFW_EVENTS` of the caller never reaches a command started
  without events.

### Tests report events

- `Tests/support/events.py` (new): the same protocol, repeated so that `Tests/run.py` keeps running without the TauFW
  package; `Tests/Utilities/test_events.py` checks that both sides agree. Kinds: `suite`, `case_start` (with the log
  path, so a running case can be followed), `case_end` (status, seconds, exit, log, BBB differences), `summary`,
  `warning` (package shadowing), `error` (the run could not start).
- `Tests/run.py` (`execute_scripts`, `main`) and `Tests/BBB/runner.py` (check) emit them. Without `$TAUFW_EVENTS`
  nothing changes: the terminal output is the same. Test workers never inherit the variable.

### The test screen

- `Utilities/python/Menu/_test_run.py` (new): `TestRun` (the state, from the events) and the screen: the cases with
  `[PASS]/[FAIL]/[SKIP]/[ RUN]/[    ]`, time, counts and elapsed time; the focused case's details (BBB differences)
  and the end of its log, live while it runs; Enter for the whole case log, L for the output of `Tests/run.py`; logs
  follow their end until scrolled up (End follows again). Ten frames a second; the screen never waits for the run.
- Leaving a running run asks, then stops it (tests are never left running behind the menu); S or Ctrl-C stops it and
  stays. Ctrl-C reaches only the screen, the tests run in their own process group.
- `interactive.py`: `execute_tests` (in-terminal run, `Press Enter`) is replaced by `start_tests`, which returns the
  `BackgroundProcess`; logs in `Tests/.artifacts/logs/menu/` (`output.log`, `events.jsonl`). `MenuNavigation.tests()`
  shows `ConsoleUI.test_run()` and always closes the process. `ConsoleUI.interrupted_tests` is gone.
- `_menu.py` imports the screen only when it is shown: FastSetup imports `Menu` on its own before TauFW is built
  (caught by `unit.setup`).

### What is left

- The run screens: `EventReporter` + `taufw.py` events (stage, progress, wait; done in §22), `start`/`advance`
  detached with a run lock that records the host (lxplus logins land on different machines), `status`/`plan`/`prepare_review` beside the
  screen, one curses session for the whole menu, errors shown on screen instead of printed.

## 21. Configs: config templates with an id, a version and a lock

**Date:** 2026-10-17 (Windows tests pass; nothing to check on lxplus: no ROOT, no BBB case)

Analysts should not have to enter the module directories. Everything an analysis can change is a copy in its bundle;
the modules' templates for those copies now have one home, `Configs/<Module>/` at the repository root, and the config
directories inside the modules stay internal (maintainers edit them; users only through the modules' own commands).
A copy must say where it came from, so that a later change of the template (e.g. a corrected cross section) does not
go unnoticed: every template starts with a `taufw_config` header (`id`, `version`, `schema`, `description`), and the
copy keeps it. Rules for analysts and maintainers: [Configs/README.md](../../Configs/README.md).

This section builds the infrastructure only. `Configs/` holds no template yet: the first ones are the sample model
files of the next work (sample lists as data). The existing module configs are not moved (open, TODO §6).

### `TauFW.Framework.configs` (new)

- `scan(directory)`: the templates of `Configs/` and their problems: only `.yml`/`.yaml` templates (plus `README.md`
  and `configs.lock`), each in `Configs/<Module>/`, with a valid header written as a block, an id that starts with
  the module directory in lower case (`plotter.samples_v15_2025`), unique.
- `content_hash(data)`: sha256 of the parsed values without the header, so comments, layout and key order do not
  count; `schema` (format) and `version` (content) are separate numbers.
- `lock_changes()` / `update()`: `Configs/configs.lock` holds `<id> <version> <sha256>` per template. `update` locks new
  templates, raises the version of a template whose values changed (only the number in its file is rewritten, every
  other byte and the line endings stay), keeps a version raised by hand, drops removed templates, and writes nothing
  while a template has a problem or a version was lowered.
- `copy_warnings(bundle_dir)`: the bundle files with a `taufw_config` header whose template has a newer version, is
  gone, or is older than the copy (an edited header); also copies with an invalid header.

### Framework and command line

- `recipe_warnings(data, bundle_dir)` adds the copy warnings for a bundle (`Recipe.parse`, `check_recipe`), so
  `taufw.py check`, `plan`, `start` and the menu preview show them. A warning only: an old copy kept on purpose is
  allowed (a way to acknowledge it is a TODO item).
- `taufw.py configs`: the templates (id, version, file, lock state, description); `taufw.py configs update`
  (maintainers): raise the versions and rewrite the lock.
- `defaults.CONFIGS_DIR`: `Configs/` next to `Analyses/`.

### Tests

`Tests/Framework/test_configs.py` (21 tests, under a second, no ROOT): headers, hashing, every `update` case (new,
changed with CRLF kept, comment-only change, raised by hand, lowered, removed, problems), the copy warnings and
`check_recipe`. Two tests read this checkout's `Configs/`: the lock must be up to date (else: run
`taufw.py configs update`), and every template must be readable by its module's reader (`READERS` in the test; the
first template brings its reader). Framework tests: 151.


## 22. Framework: events for the menu (EventReporter)

**Date:** 2026-10-17 (Windows tests pass; lxplus check in TODO §1 "Test screen on lxplus")

Stage 0 of the menu program (§20) for the Framework: `taufw.py` reports what it does as events, so a run screen can
follow a `start`/`advance` started beside it the way the test screen follows `Tests/run.py`. Nothing reads these
events yet; the run screens come next. The terminal output and `run.log` do not change.

- `reporting.py`: `Reporter.event(kind, **fields)`, ignored by default (`FrameworkReporter` prints nothing new;
  `SilentReporter` keeps them in `.events` for the tests). `EventReporter(reporter, writer)` passes every call on to
  `reporter` unchanged and also writes header, message, warning, table and the events through an `EventWriter`
  (§20). PicoProducer's own lines (`raw`) stay in the output only.
- The events: `run` (run_id, run_dir) when `advance()` starts, `stage_step` (stage, type, state before the step),
  `stage_state` (stage, state, message after it), `run_state` (run_id, state), `wait` (seconds) before
  `advance --wait` sleeps; `LocalStage._progress`: `progress` (stage, index, total, label, status `run`/`ok`/
  `failed`, seconds at the end) for every command of plots, histograms, fit and python; `taufw.py`: `error` (message)
  on a recipe or run directory problem. The list is in the docstring of `reporting.py`.
- `taufw.py`: `main` reads `$TAUFW_EVENTS` once and removes it from the environment (the commands the stages run, and
  the batch jobs they submit, never see it); every command takes its reporter from `_reporter(args)`: the terminal
  reporter, inside an `EventReporter` when the variable was set. `interactive.py` runs the commands in the menu's own
  process without events.
- Checked: `taufw.py check`/`plan`/`configs` print byte for byte the same with and without `$TAUFW_EVENTS` (Windows,
  five commands); `Tests/Framework`: the event order of a waiting run, the progress events, `EventReporter` (same
  terminal output and `run.log` as without it), `taufw.py start` with the variable (removed before a stage submits)
  and the `error` event. BBB (`framework.*`) runs without the variable, so it still checks the plain output.

## 22. Sample lists as data: the sample model

**Date:** 2026-10-17 (S0-S5 on Windows; BBB `plotter.sample_model` locked on lxplus with the old code). **Verified
on lxplus 2026-10-17:** `bbb check` 21/21 and `Tests/run.py checks` after the switch; a plots + histograms run of
`tes_id_2025` with `samples:` against the same stages without it (57 PNG byte-identical; shapes equal up to the
multithreaded RDataFrame noise, `data_obs` bit-identical); S7 (`plot.py -c mutau` with the setups in `Configs/`,
`init --from`); `plan` of `example_mutau_long` (25 samples). Details in TODO §1. (This is the second §22: the menu
events section above has the same number.) Plan: LocalR/architecture/14.

The recipe must say which samples an analysis reads; until now `Plotter/config/samples_v15.py` decided it out of
sight (the MC table with cross sections, the data datasets, the MC weights, stitching, joining and splitting, per
era). Its samples become templates in `Configs/Plotter/samples/` (CL §21), one per era, that an analysis copies into
its bundle. **No physics or data change:** every SampleSet built from a template gets exactly the calls the old
function makes, and a test proves it.

### Recorder and BBB case (S0)

- `Tests/Plotter/sample_model/recorder.py`: runs a sample-set function with recording stand-ins for the core
  (`setera`, the core `getsampleset`, the SampleSet's `stitch`, `join`, `split`, `printtable`) and returns every call
  with its arguments, in order. On Windows with a ROOT-free stub of `TauFW.Plotter.sample.utils` (the pure helpers
  are the real ones), on lxplus with the real module. The grid: 8 eras x 6 channels (one per channel kind) x 7 caller
  options (what `plot.py` and `createinputsTES.py` pass, and every other option the function reads) = 336 cases.
- BBB case `plotter.sample_model`: the grid of the real module, **to be locked on lxplus with the old code**. Its
  function `_sample_model_function` is the only line that changes when the case moves to the model (after the lock).
  A call that raises is recorded as `raised` only (the message may differ, see L16).

### Templates (S1)

- `Tests/Plotter/sample_model/export.py` wrote `Configs/Plotter/samples/v15_<era>.yml` for the 8 eras
  `samples_v15.py` supports (`2022_preEE`, `2022_postEE`, `2023C`, `2023D`, `2024`, `2025`, `2026`, `2526`) from
  the recorded calls: nothing typed by hand; every file is read back and compared value by value (types too) before
  it is written. Cross sections are the values `samples_v15.py` computed (cross section times k-factor).
- `Configs/configs.lock`: the 8 templates at version 1.

### The model (S2)

- `Plotter/python/sample/model.py` (`TauFW.Plotter.sample.model`): `load_sample_model` (YAML only, every format problem
  at once), `pick(paths, era)`, `sample_names(model, channel)` (MC names and data pattern, no ROOT), and
  `getsampleset(channel, era, model, **kwargs)`: the generic part of `samples_v15.getsampleset` copied as it is
  (caller options, joins, genmatch split, table, its odd behaviour included), the era part read from the model. Not
  copied: the debug print of the data dataset for `2022_preEE` muon channels (terminal output only; each era is now
  its own file).
- `Tests/Plotter/sample_model/test_sample_model.py` (new unit suite `unit.plotter.sample_model`, no ROOT, < 1 s):
  for all 336 cases the old and the new function make the same calls (where the old one raises, the new one raises
  after the same calls); a changed cross section in a template fails it (checked). Also the reader: `pick`,
  `sample_names`, format problems. `Tests/Framework/test_configs.py` reads every template with `load_sample_model`.
- Plotter BUGS L14 (`DM` split: `NameError`), L15 (electron data `else` without assignment, unreachable for the
  supported eras), L16 (era `2526` with tautau/emu: `TypeError`) registered; the model keeps L14 and raises for L16.

### The BBB case moves to the model

After the lock (21 cases, `plotter.sample_model` added, the other 20 the same), `_sample_model_function` runs the
model with the templates. On Windows (stub utils) the snapshot of the case before and after is byte for byte the same;
`bbb check` on lxplus must show no difference.

### Scripts (S3)

- `Plotter/config/samples_v15.py` `getsampleset`: one change at the top, marked BACKWARD COMPATIBILITY: with
  `samples=[files]` it returns the model's sample set for the era's file; without it, its own tables as before. The
  keyword is read into `samplefiles` (not `samples`: L14 needs that name to stay undefined).
- `plot.py --samples FILE ...`, `createinputsTES.py --samples FILE ...` pass it on
  ([scripts_arg_changes.md](scripts_arg_changes.md)). The Fitter imports nothing new: the option goes through
  `config.samples_v15`, the import it already has (known debt).
- Test: `samples_v15.getsampleset(..., samples=...)` makes the same calls as its own tables, all 336 cases.

### APIs (S4)

- `PlotsRequest.samples`, `ShapesRequest.samples`: `--samples` on every command (absolute with an output directory).
- `ControlPlots.sample_names(files, era, channel)`, `samples_problems(files, eras)` (unreadable file, an era without
  exactly one file), `sample_file_problems(files, eras, channels, tuples)` (requested MC tuples and the data pattern
  in the tuple directory); `preflight` uses them (not for the '<run_dir>' placeholder of a plan). The Fitter API only
  checks that the files exist: their content is the Plotter's.
- `PicoProducer.sample_names(request)`: (era, channel, sample) of a first submission, from the sample catalogs only,
  selected as `iter_plans` selects them.

### Framework and recipes (S5)

- `plots` and `histograms` get the option `samples` (a path option: bundle files or absolute; a module path is a
  problem). `check` reads the files through the Plotter API: readable, one per era. The histograms stage gets the
  Plotter API as `samples_api` for its preflight.
- `TauFW.Framework.samples.sample_issues` (new): for a reader with `samples` whose tuples come from a production stage
  of the recipe, a requested MC sample production does not make, or a data pattern that matches nothing it makes, is
  a problem; a sample made but read by nobody is a warning (only when every reader of that production has
  `samples`). `RunPlan.sample_problems` / `sample_warnings`; `taufw.py plan` shows them (exit 1 with problems);
  `start` raises `RecipeError` before anything is made.
- `Analyses/tes_id_2025`: `v15_2025.yml` (a copy of the template, unchanged) for plots and histograms.
- `Analyses/example_mutau` split in two (user decision): its production made `DY*` and `TT*` only, but the plots
  need data and every background. Before CL §18 this did not show, because the plots read the full tuple set of
  `$PICODIR` and not the production's output; since CL §18 its plots stage could not run. Now
  `example_mutau_short` is production only, and `example_mutau_long` produces the data and the 22 MC samples of
  its `v15_2022_postEE.yml` copy (exact names; the vetoes keep the tribosons out, since a name without `*` matches
  as a prefix) and then makes the plots; `plan` compares the two lists.
- Tests: `Tests/Framework/test_samples.py` (validation, comparison, start refuses), Plotter and Fitter API tests.

### Channel setups to Configs (S7)

- `Plotter/config/setup_*.yml` (7 files) moved (`git mv`) to `Configs/Plotter/setups/`, each with a `taufw_config`
  header (`plotter.setup_<name>`, version 1), locked. The scripts read only named keys (`channel`, `baselineCuts`,
  `regions`, `tag`, `scaleFactors`), so the header changes nothing. The bundle copies (`tes_id_2025` mutau and
  mumu, `example_mutau_long` mutau) were identical to the templates and got the same header.
- `plot.py`, `plot_postfit.py`, `plot_postfit_shift.py`, `plot_v10.py`: a channel name reads the setup from
  `Configs/Plotter/setups/` (from the script's directory); defaults are channel names. The Plotter API resolves a
  channel name the same way. `Plotter/config/` keeps the Python sample configs (`samples*.py`).
- `READERS` of `Tests/Framework/test_configs.py`: `plotter.setup_` (yaml, with `channel` and `baselineCuts`).

### `taufw.py init --from` copies the source bundle's own files

`init --from` copied only the configs a recipe takes from the modules; the source bundle's own files (its setup and
fit config copies, its sample files, its Python steps) were not copied, so `init new --from Analyses/tes_id_2025` made
a recipe that named files the new bundle did not have. Now `Framework.make_bundle` copies every file of the source
bundle to the same relative path (`bundle.source_files`: as a run copies a bundle, without `recipe.yml`, caches and
runs; a loose recipe file: the files its options name), so copies of `Configs/` templates keep their header and the
recipe's values stay valid. `steps/example.py` is written only when the source has no `steps/`. Test:
`test_make_bundle_copies_the_source_bundle`.


## 23. Menu: operations run behind the menu; tests keep running when the screen is left

**Date:** 2026-10-17 (Windows tests pass; lxplus check in TODO §1 "Tests behind the menu on lxplus")

Leaving a screen must never kill what it shows (user, 2026-10-17): tests (here) and runs (next) go on behind the
menu, the menu shows their state ("Tests (Running 12/40)", "Tests (Failed: 3)") and opens their screen again.
§20 started commands beside the screen, but the menu was their parent: it stopped them when the screen was left,
and their exit code lived only in the menu's process. Now a supervisor runs them and keeps everything in files.

### Decisions (user, 2026-10-17)

- Leaving a screen (Esc) never stops the operation; S (or Ctrl-C) asks, then stops it.
- Running on after the login session ends is **not a goal**, and is not measured: lxplus may kill a user's
  processes at logout, and the AFS token goes too. Such an operation is shown as **Lost** (D1).
- One test run at a time (D2): `Tests/run.py`, its logs and BBB are shared.
- The last five records of a kind are kept (D4).
- Quitting the menu while something runs gives a clear warning: C stay (default, also Esc and Enter), S stop it
  all and quit, Q quit and leave it running (only while the login session lasts; a run killed while it submits
  jobs may need a manual condor_q check).
- For runs (later): the lock is in `Framework.advance` (also the CLI), refused while it is held on another machine,
  taken over only on request when its operation is Lost (D3); a stop never kills job submission halfway (no
  automatic SIGTERM/SIGKILL for runs, `escalate=False`). The shared screen (K1: the whole layout plus a model; K2:
  the run model on the Framework side) comes with the run screen; `setup_runner` stays as it is (K5);
  `plan`/`status`/`check` move beside the screen with an output-only view (K4).

### The operation (`Utilities/python/Process/`)

- `_supervisor.py` (new; standard library only, run by its path, so it works where TauFW is not built):
  `python3 -B _supervisor.py <dir>` reads `operation.json`, starts the command in its own process group (output to
  `output.log`), writes `heartbeat.json` {host, pid, child, t} every `heartbeat` s, reacts to the files `stop`
  (SIGINT, then with `escalate` SIGTERM after 3 s and SIGKILL after 8 s) and `kill` (SIGKILL), and writes
  `exit.json` {returncode, stopped, finished} at the end (130 when stopped and not successful, 128+N after signal
  N, 127 when the command cannot start). It ignores SIGINT and SIGHUP (the terminal is not its own); SIGTERM to it
  (e.g. a logout) counts as a stop. JSON files are written under a temporary name and renamed (never half a file).
  A stop is a file, so any menu can stop an operation, also from another lxplus machine (AFS).
- `_operations.py` (new): `OperationStore(root)`: `start(kind, title, argv, cwd, data, env, escalate, heartbeat)`
  makes `<root>/<kind>-<time>/` (a new name when two start in one second), writes `operation.json` (kind, title,
  argv, cwd, `data` for its screen, host, user, started, heartbeat, escalate), empty `events.jsonl`/`output.log`,
  and starts the supervisor in a session of its own with `$TAUFW_EVENTS` and `PYTHONUNBUFFERED=1`; `all(kind)`
  (newest first; unreadable directories are skipped), `latest(kind)`, `running(kind)`, `prune(kind, keep)` (never an
  operation that runs). `Operation`: the interface the test screen used from `BackgroundProcess` (`poll()`,
  `returncode`, `cancelled`, `cancel()`, `elapsed()`, `events`, `output`) plus `state()`, `running`, `kill()`,
  `remote`, `host`, `title`, `data`. Every new `Operation` object reads its files from the top.
- `state()`: `exit.json` -> DONE / FAILED / STOPPED; else RUNNING (STOPPING once `stop` exists), or LOST when the
  last heartbeat (or the start) is older than `LOST_AFTER` = 120 s, or at once when the heartbeat's host is this
  machine and its pid is gone, or the supervisor this menu started ended without `exit.json`. The heartbeat is
  read at most once a second per object (the screen draws ten times a second, on AFS). Wall-clock times (`t`) are
  compared across machines; lxplus clocks are synchronised.
- `BackgroundProcess` (§20) stays: the menu no longer uses it; it is the form for a command that should live only
  as long as its screen (K4 may use it).

### The menu

- `interactive.py`: `OPERATIONS_DIR` = `<checkout>/.artifacts/menu/operations` (git-ignored: `.gitignore` gets
  `.artifacts/`); `Menu(..., operations_dir=None)`. `start_tests(family, cases, title, expected)` refuses while a
  test run is running ("Tests are already running (..., started on <host>)"), prunes to the last four, and starts
  `Tests/run.py` through `OperationStore` with `data` = family, cases, expected (for its screen in a later menu).
  `tests_operation()` (the last test run, None when the records cannot be read: the main menu still opens),
  `running_operations()`, `stop_operation(operation)`. `CHECKOUT` replaces the `__file__` arithmetic.
- `_navigation.py`: the main menu gets `tests=` the last test run. `tests()`: while one runs, Tests opens its screen
  (no family menu); after the screen, back to the main menu if it still runs, else the Tests menu, which starts
  with "Last run: <title> (<state>)" (`last`). The `finally: process.close()` of §20 is gone. Exit (and Esc in the
  main menu) goes through `_may_quit()`: nothing runs -> quit; else `ui.quit_running(...)`: cancel -> stay, stop ->
  `stop_operation` for each, then quit, quit -> quit.
- `_menu.py`: `main_menu(proxy_valid, tests)` labels Tests with the run's state (role colors: running cyan, done
  green, failed red, stopping/stopped/lost yellow); `tests_menu(last)`; `quit_running(operations)` (the list with
  state, time and "on <host>", the warning, C/S/Q); `_operation_summary`; `_clock` (moved here from
  `_test_run.py`). Labels are computed when a menu is drawn: a menu waiting for a key does not change by itself
  until the menu redraws (a live update comes with the single curses session).
- `_test_run.py`: the screen follows an `Operation` through `state()`. Esc leaves at once (the run goes on; footer
  "Esc Back (keeps running)"); S or Ctrl-C asks "Stop the tests? Y Yes | N No" (only while it runs); states
  RUNNING / STOPPING / PASSED / FAILED / STOPPED / LOST, "RUNNING on <host>" for a run started on another machine;
  a LOST run marks its running case STOP and explains why (`LOST_TEXT`). The state line moves below the title when
  both do not fit on one line. `test_summary(operation)` gives the menus "Running 12/40", "Failed: 3", "Done", ...
- "Run all automated tests" (found on lxplus, 2026-10-18): the cases were not known in advance, so the total grew
  with every case ("n/n+1"), and `plotter.unroll` (in normal and in BBB) shared one row. Now `expected` holds
  `[family, id]` pairs for all three families: the total is right from the start, and `TestRun` keys and labels
  such cases "suite: id" ("normal: plotter.unroll", "bbb: plotter.unroll"), finding them through the `suite` event
  of the runner that runs. One family: plain ids, as before.

### Checked

- `Tests/Utilities/test_operations.py` (new, 12 tests): the supervisor with a fake command and clock (exit codes,
  heartbeat, stop with and without escalation, kill, SIGTERM, a command that cannot start); the states from files
  (RUNNING, STOPPING, DONE, FAILED, STOPPED, LOST by an old heartbeat, by a gone supervisor; another machine); a
  real start (Windows too): output, `$TAUFW_EVENTS`, exit code 3, found again by a new object; `start` options;
  ordering, `running`, `prune`. Two real stop tests (process groups) run on lxplus only.
- `test_test_run.py`, `test_menu.py`, `Tests/Framework/test_interactive.py` follow the new behavior (leaving keeps
  the run, stop asks, reattach, last run, quit warning, labels).
- End to end on Windows: the menu's `start_tests` ran `Tests/run.py checks` (2 cases) through the supervisor; a
  second start was refused; a second `_Operations` (another menu) found it and its label went Running 0/2 -> 1/2 ->
  2/2 -> Failed: 1 (`check_import_boundaries` fails by design). `Tests/run.py checks`: only the two known failures.
- Not checked here: process groups and signals (Windows), curses on a real terminal. TODO §1.

## 24. Plotter becomes Histogrammer; a clean Plotter is extracted (in progress)

**Date:** 2026-10-18 (S0 on Windows; the lxplus lock and the round-trip check are in TODO §1). Plan:
LocalR/architecture/18.

After the drawing moved to `TauFW.Utilities.Drawing` (CL §18), almost everything left in `Plotter/` produces
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
- Not checked here: the new case and the spike need ROOT (TODO §1).

### The rename (S1)

**Date:** 2026-10-18, Windows; the lxplus checks are in TODO §1 (BBB without re-lock, old names, real plots).

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
  (S2).
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
