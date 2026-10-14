# Refactor-2025: change log

# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
**Branch:** `Refactor-2025`
**Last updated:** 2026-10-13

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
| 9 | [PicoProducer cleanup, Part 4: jobs package](#9-picoproducer-cleanup-part-4-jobs-package) |
| 10 | [PicoProducer cleanup, Part 5: public API, command line, workers](#10-picoproducer-cleanup-part-5-public-api-command-line-workers) |
| 11 | [Framework: the TauFW orchestrator (Part F)](#11-framework-the-taufw-orchestrator-part-f) |
| 12 | [Framework: plots, histograms and fit stages (Part G)](#12-framework-plots-histograms-and-fit-stages-part-g) |
| 13 | [Test runner: quiet defaults and BBB lock logs](#13-test-runner-quiet-defaults-and-bbb-lock-logs) |
| 14 | [Framework: analysis bundles and Python steps (Part H)](#14-framework-analysis-bundles-and-python-steps-part-h) |
| 15 | [common tools moved to Utilities: parallel processes and the loading bar](#15-common-tools-moved-to-utilities-parallel-processes-and-the-loading-bar) |
| 16 | [common tools moved to Utilities: numeric helpers](#16-common-tools-moved-to-utilities-numeric-helpers) |
| 17 | [common tools moved to Utilities: the printf-style table](#17-common-tools-moved-to-utilities-the-printf-style-table) |

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
Producer validation no longer imports Plotter's parallel helper (moved to Utilities in §15).

### Migration for users

| Old | Replacement |
|---|---|
| `TauFW.PicoProducer.storage.Sample` | `TauFW.PicoProducer.datasets`; the old module remains a compatibility re-export for private catalogs |
| `TauFW.PicoProducer.tools.config` | `TauFW.PicoProducer.settings` |
| `storage.utils.getstorage / isvalid / getsamples` | `storage.getstorage / isvalid`; `datasets.getsamples` |
| `batch.utils.getbatch` | `batch.getbatch` |
| `TauFW.Plotter.plot.MultiThread.MultiProcessor(max=...)` | `TauFW.Utilities.Process.ParallelProcessor(max_parallel=...)` (§15) |
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

## 9. PicoProducer cleanup, Part 4: jobs package

**Date:** 2026-10-13
**Details:** [docs/PicoProducer/BUGS.md](../PicoProducer/BUGS.md)

Part 4 splits `pico/job.py` and `pico/run.py` into the `jobs/` package: one worker command builder, pure
planning and status functions, and a merge step with a validated cleanup gate. These are the pieces the public
PicoProducer API (Part 5) and the `Framework` orchestrator build on. The restructuring steps (A1-A5) do not
change behavior: all `pico.*` BBB cases must pass unchanged. Bug fixes follow in their own commits (B).

### A1. One worker command builder

The command line of a worker (`picojob.py`/`skimjob.py`) was built twice: once for batch jobs
(`pico/job.py`, one line per chunk in the job list) and once for local runs (`pico/run.py`, the
"Executing:" line). Both now come from `jobs/worker_command.py`:

| Function | Replaces | Output |
|---|---|---|
| `resolve_worker(config, channel, extraopts)` | `pico.run.getmodule` (removed) | `WorkerSpec(module, processor, procopts, extrachopts)`; takes the configuration as an argument instead of the global `CONFIG` |
| `job_command(WorkerOptions)` | the command block in `preparejobs` | one job-list line |
| `run_command(WorkerOptions)` | the command block in `main_run` | the local run command |

`WorkerOptions` is a single option record; each formatter keeps its own flag order, because both strings are
part of the BBB baselines (`pico.jobs`, `pico.run`). The known differences between the two (BUGS P10:
`run` passes `-m` whenever `maxevts` is set, including `-1`) are kept and fixed in B.

**Check:** a comparison script ran the old and new builders over 8064 option combinations (skim/analysis,
processor options, tmpdir, prefetch, preselection, event ranges, test runs, extra options, single/multiple input
files): all strings are identical. `resolve_worker` gives the same result and errors as `getmodule`.

### A2. Submission pipeline: planner, pipeline, reporter, request

`preparejobs` (a 320-line generator in `pico/job.py`) and the submit loop of `main_submit` are split by
responsibility:

| Module | Contents |
|---|---|
| `jobs/request.py` | `JobRequest`: all settings of a (re)submission in one record, built by `pico.py` with `JobRequest.from_args(args)`. The job functions no longer read the argparse namespace |
| `jobs/planner.py` | pure planning: `sample_layout` (try number, job name, option precedence, output/job/config/log directories, job config and job list names) and `assign_chunks` (chunk numbers and worker command lines). No file access, no output |
| `jobs/pipeline.py` | `iter_plans` (sample selection, input files, chunking, directories, job list; yields one `SamplePlan` per sample), `submit_plan`, `record_submission` |
| `jobs/reporting.py` | `Reporter` (silent) and `ConsoleReporter` (prints exactly what `pico.py` printed). The pipeline reports through it instead of printing |
| `jobs/jobconfig.py` | `JOBCFG_KEYS` (the job config keys in file order), `make_jobcfg`, `write_jobcfg` |
| `jobs/status.py` | `checkchunks`, moved unchanged except that it takes the configuration as an argument; A3 restructures it |

- **Explicit configuration.** The pipeline, planner and status functions take the configuration as an argument
  instead of importing the global `CONFIG`.
- **No writes in planning mode.** `iter_plans(..., materialize=False)` creates no directories and writes no job
  list. `pico.py submit` uses `materialize=True`: directories, the output directory and the job list are created at
  the same points as before.
- **Prompts are callables.** The `--prompt` questions (existing job config, confirm submission) moved to a small
  `_Prompt` class in `pico/job.py`; the pipeline only receives the answers. Answering `all` still stops all
  further questions.
- `chunkify_by_evts` takes an optional `progress` factory, so a silent caller can suppress its progress bar.
- `pico/job.py` keeps `main_submit` (about 15 lines) and `main_status`; `preparejobs` and `checkchunks` are gone.

**Known bugs kept as they are** (marked `# BUGS <ID>`, fixed in B): P01, P02 (the `--prompt` dialog for an
existing job config still crashes, now with `NameError` instead of `TypeError`/`UnboundLocalError`), P03, P04, P05,
P06. **New:** P20, the answers of that dialog are inverted (`y` skips, `n` submits), found while moving it.

**Check:** a comparison harness ran the old (`3c401cd`) and new `main_submit`/`main_status` side by side on
Windows, with ROOT, the sample catalog, storage, the batch system and the queue replaced by fakes:
152 scenarios (verbosity 0-3 each): file and event splitting, test runs, user/sample/config `nfilesperjob` and
`maxevts`, option merging, skims with prefetch/preselection/tmpdir, dry runs, empty samples, existing job configs
with and without `--force`, `--prompt` answers, resubmission with good/pending/corrupt/missing chunks and `--split`,
and `status` (with log lookup, and for all eras/channels). The terminal output, the job lists, the job configs
(without `time`) and the scheduler calls are identical. The only difference is the exception type of P02.

### A3. Job status: observations and classifiers

`checkchunks` (a 400-line function) is now `jobs/status.py`:

| Part | Responsibility |
|---|---|
| `check_sample(sample, config, reporter, ...)` | the pipeline for one sample: expected events (job config or DAS), the batch queue, the storage listing and file validation, then the summary and the log files of failed chunks. Returns a `ChunkStatus` |
| `_SkimClassifier`, `_TreeClassifier` | assign pending jobs and output files to chunks and decide which chunks are good, pending, failed or missing, and which input files to resubmit. They do not access files, storage or the batch queue; `check_sample` feeds them the observations in the original order (for trees, only outputs of non-pending chunks are validated, as before) |
| `ChunkStatus` | chunk numbers per state, processed and expected events, the files to resubmit and the chunks to keep. `mergeable` is the condition for `hadd`/cleanup (nothing to resubmit, nothing pending) |
| `format_summary(status)` | the `SUCCESS/PEND/FAIL/MISS` lines |

- All output goes through the reporter, including the progress bar (`reporter.progress`).
- `check_sample` no longer modifies the sample's job config: the classifiers work on a copy of its `chunkdict`,
  and the expected number of events is returned (`status.nexpected`) instead of being written into
  `sample.jobcfg['nevents']`. Resubmission and `main_status` use the returned values.
- `pipeline.iter_plans` (resubmission) and `pico/job.py` `main_status` call `check_sample`.

**New bugs found:** P21 (`status --checkexpevts` is ignored) and P22 (checking the status creates the output
directory). Both are kept as they are and fixed in B.

**Check:** the A2 comparison harness was extended with progress bars (15 or more outputs, skims and trees),
`--checkexpevts`, `--skipevts`, log lookup with log files, and pending jobs for skims and trees: 184 scenarios
(verbosity 0-3), compared with the code before Part 4A-2 (`3c401cd`). Output, job lists, job configs and
scheduler calls are identical; the only difference is still the exception type of P02.

### A4. Merge and cleanup

The `hadd`/`haddclean`/`clean` branch of `main_status` is now `jobs/merge.py`:

| Part | Responsibility |
|---|---|
| `merge_sample(sample, config, action, era, channel, tag, reporter, ...)` | the pipeline for one sample: merge target, `check_sample`, the gate, `storage.hadd`, then cleanup. Returns a `MergeResult` (`refused`, `merged`, the rm commands, `outpath`) |
| `merge_target(sample, picodir, era, channel, tag)` | pure: the storage directory and file name of the merged tuple, and the glob patterns of the sample's job outputs, job configs and logs (`MergeTarget`) |
| `merge_gate(status, force)` | pure: merge or clean only if no chunk needs to be resubmitted (`status.mergeable`), unless forced |
| `cleanup_commands(target, count)` | pure: the rm commands; `count(pattern)` is the only observation (the number of files matching a glob) |

- `main_status` calls `merge_sample` for `hadd`, `haddclean` and `clean`; a refused merge still skips the blank
  line after the sample, as before.
- The verbose output goes through the reporter.

**New bug found:** P23. The "other jobs in the same job directory" test of the cleanup is always true, so cleaning
one tag removes the job configs and logs of every other tag in that directory. Kept as it is and fixed in B.

**Check:** the comparison harness got a fake `hadd` and `rm` (which really removes files) and 13 merge scenarios
(verbosity 0-3 each): `hadd` with complete and incomplete samples, `--force`, `haddclean`, `clean`, `hadd -r`, dry
runs, two tags in one job directory, foreign files in the output directory, skim channels, `--maxopenfiles` and
`--skipevts`. Output, scheduler and hadd calls, rm commands and the remaining files are identical to `3c401cd`.

### A5. `pico/` as thin command functions

`pico/job.py` and `pico/run.py` keep only what belongs to the command line: building a `JobRequest` from the
arguments, choosing the reporter, the `--prompt` dialog, and streaming the `jobs/` pipelines.

| Command | Before | Now |
|---|---|---|
| `pico.py run` | `pico/run.py` `main_run` (150 lines) | `jobs/local.py`: `iter_local_runs` (sample selection, files, worker command; yields a `LocalRun`) and `execute_run`. `main_run` is 6 lines |
| `pico.py status`, `hadd`, `haddclean`, `clean` | the era/channel/sample loop in `main_status` | `jobs/pipeline.py` `iter_submitted(config, request, reporter, action)` yields the samples of existing job configs; `main_status` calls `check_sample` or `merge_sample` for each |

- `JobRequest` has four new fields for local runs: `outdir`, `infiles`, `nfiles`, `nsamples`.
- The job-config glob of `main_status` is now `planner.cfg_globs(..., group='*')`; the patterns are the same.
- READMEs: `PicoProducer/python/README.md` (all packages, and which `jobs/` pipeline each `pico.py` command uses)
  and `pico/README.md`. The BUGS.md locations of P01-P12 point to the new modules. `Utilities/IOInventory.md` is
  regenerated.

**Check:** the comparison harness got 11 local-run scenarios (verbosity 0-3 each): sample filters, `-S`/`-n`,
user input files, skims with preselection, no matching samples, dry runs, no era/channel, sample and user
options, `-m`/`-p`/`-t`, data-only selection. All 280 scenarios (submit, resubmit, status, merge, run) give
identical output, files, scheduler, hadd, rm and shell calls compared with `3c401cd`.

### B1. Crash fixes without output change (P01, P02, P03, P07)

| Bug | Fix |
|---|---|
| P01 | `err.message` (Python 2) in two `except IOError` handlers (`jobs/pipeline.py` event chunking, `pico/config.py` `write`): now `str(err)`. The handlers print the error instead of raising `AttributeError` |
| P02 | `submit --prompt` with an existing job config: the question `">>> Submit anyway? [y/n] "%(nchunks)` used an undefined name and had no placeholder. It is now a plain string, so the dialog works (see P20 in B2 for its answers) |
| P03 | `write_jobcfg` for `.json.gz` names: `gzip` imported, and `json.dump(jobcfg,file,indent=2)` instead of `file.write(json.dump(jobcfg),indent=2)`. A written file reads back with `Sample.loadjson` |
| P07 | `check_sample`: `checkexpevts==False` (a comparison) is now the assignment it was meant to be. `None` and `False` both disable the comparison, so the output is the same |

**Check:** no BBB case reaches these paths, so all baselines are unchanged. In the comparison harness only the
`--prompt` scenario with an existing job config changes: it now asks instead of crashing. A `.json.gz` job config
written by `write_jobcfg` reads back correctly.

### B2. Behavior fixes without BBB change (P04, P05, P06, P11, P19, P20, P21, P22, P23)

| Bug | Fix | What users see |
|---|---|---|
| P04 | `--checkqueue 1` ("check once"): `jobs is None` instead of `jobs!=None`, in `iter_plans` and `main_status` | the queue is queried once and pending jobs are found; before, the queue was not checked at all |
| P05 | `found = len(samples)>0` | `submit` with no matching sample says so |
| P06 | the sample's `maxevts` is used when positive | per-sample event splitting works; samples without it use `maxevtsperjob` from the configuration |
| P11 | `execute_run` uses `subprocess.call` and returns the exit code | `pico.py run` warns about each failed worker and lists them at the end |
| P19 | `merge.validated(nevents, status)`: before cleanup after `haddclean`/`hadd -r`, the merged tuple must be readable and, with event counting, hold the processed events of the good chunks | a corrupt or incomplete merge keeps the job output (warning); `MergeResult.invalid` gives the reason |
| P20 | `--prompt` on an existing job config: `y`/`f` submit, `n` skips | the dialog does what the answer says |
| P21 | the status-only branch passes `checkexpevts` | `status` warns about unexpected event counts by default for analysis channels, like `hadd` and `resubmit` |
| P22 | `check_sample` opens the output directory without creating it | `status` and the coming read-only API calls do not write to storage |
| P23 | cleanup removes the whole job directory only if all its job configs belong to the sample | cleaning one tag keeps the job configs, job lists and logs of the other tags in the same directory |

**Check:** BBB unchanged: no case reaches these paths, or the result is the same (`pico.merge` merges valid tuples,
one job per directory; `pico.jobs` keeps only the summary lines of `status`). The comparison harness against the
B1 commit changes exactly in the affected scenarios: the `--prompt` dialog, `status` (event-count warnings,
pending jobs found with `--checkqueue 1`), cleanup with two tags in one directory, failing local runs, and a
merged tuple with the wrong number of events (job output kept).

### B3. Module options and `run -m` (P08, P09, P10), with re-locked baselines

| Bug | Fix |
|---|---|
| P08 | Module options are applied in the order channel table < sample (`opts` in the catalog) < user (`-E`); a later value of the same key wins in the worker. `resolve_worker` returns the channel's options (`WorkerSpec.chopts`) and the user's (`useropts`) separately; `module_options(worker, sampleopts)` joins them |
| P09 | A resubmission reuses the options of the previous try (already merged) and appends only new user options (`resubmit_options`); they no longer grow with every retry |
| P10 | `pico.py run` passes `-m` only for a positive number of events (the default `-1` added `-m -1` to every command) |

Verbose output (`-v`) shows `chopts` and `useropts` instead of `extrachopts`.

**Baselines:** `pico.run` and `pico.jobs` change on purpose and are re-locked on lxplus
(`python3 Tests/run.py bbb lock --replace`); see [BUGS.md](../PicoProducer/BUGS.md#p08-p09-p10-module-options-and-run--m)
for the exact differences. All other cases are unchanged. In the comparison harness the only differences against
the B2 commit are the option order, the missing `-m -1` and the verbose labels.

---

## 10. PicoProducer cleanup, Part 5: public API, command line, workers

**Date:** 2026-10-13
**Details:** [docs/PicoProducer/API.md](../PicoProducer/API.md), [docs/PicoProducer/IO.md](../PicoProducer/IO.md),
[docs/PicoProducer/BUGS.md](../PicoProducer/BUGS.md)

Part 5 gives PicoProducer a public Python API, makes `pico.py` a client of it, and renames `processors/` to
`workers/`. The `Framework` orchestrator (section 11) uses only this API. The restructuring steps (A1-A3) do not
change behavior; the bug fixes of the command line follow in B.

### A1. Public API: `api/`

| Module | Contents |
|---|---|
| `api/producer.py` | `class PicoProducer`: `plan`, `submit`, `resubmit`, `status`, `merge`, `clean`, `run_local`, and `iter_plan` (stream). Each method's docstring lists its side effects. `PicoProducer.from_config(config, reporter, basedir)` takes `None` (config/config.json), a path, a dict or a `Config`, and never writes the configuration |
| `api/types.py` | frozen result records with `to_dict()`/`from_dict()`: `JobPlan`/`PlannedSample`, `Submission`/`SubmittedSample`, `StageStatus`/`SampleStatus` (`complete` = the merge gate), `MergeReport`/`TupleArtifact`, `LocalResult`. The request is the existing `JobRequest` (`request_to_dict`/`request_from_dict`) |
| `settings/store.py` | `loadconfig(path)`: reads a configuration without caching and without writing (missing keys get defaults in memory) |

- `plan()` writes nothing: it runs the submission pipeline with `materialize=False`; a sample whose job config
  already exists is planned with `conflict=True`.
- Methods that touch files run inside the PicoProducer directory (the configured paths are relative to it) and
  restore the working directory afterwards. This is not thread-safe; [API.md](../PicoProducer/API.md)
  documents it.
- Messages go to the reporter given at construction: silent by default, `ConsoleReporter` for terminal output.

### A2. Command line: `cli/`, thin `pico.py`

`pico/` is gone. Its contents moved to `cli/`, and the job commands now call the API:

| Before | Now |
|---|---|
| `scripts/pico.py` (260 lines: parser, dispatch, `install`) | `scripts/pico.py` (30 lines): change directory, load the configuration, `parse_args(build_parser(CONFIG))`, `dispatch(args)` |
| parser in `scripts/pico.py` | `cli/parser.py`: `build_parser(config)`, `parse_args(parser, argv)` (abbreviations, tag prefix) |
| `if/elif` chain of subcommands | `cli/__init__.py`: `COMMANDS` table (`subcommand -> module:function`, imported on use) and `dispatch` |
| `pico/job.py`, `pico/run.py` | `cli/jobs.py`: `main_run` -> `PicoProducer.run_local`, `main_submit` -> `submit`/`resubmit`, `main_status` -> `status`/`merge`/`clean`; the `--prompt` dialog |
| `pico/config.py`, `pico/common.py` | `cli/config.py`, `cli/common.py` (moved; imports updated) |
| `main_install` in `scripts/pico.py` | `cli/install.py` |

So there is one code path: BBB drives `pico.py`, and `pico.py` drives the API.

**Check:** the comparison harness (296 scenarios: submit, resubmit, status, hadd/haddclean/clean, run, at
verbosity 0-3) gives identical output, files and calls through `cli/jobs.py` and the API as through the old
`pico/` functions. `scripts/pico.py` itself was compared on 30 command lines (every `-h`, no arguments,
abbreviations, `list`, `install`, `channel`/`rm`/`set` edits, an unknown subcommand): identical output and exit codes.

### A3. `processors/` renamed to `workers/`

`PicoProducer/python/processors/` (`picojob.py`, `skimjob.py`, `Bookkeeper.py`, the `keep_and_drop_*.txt` branch
selections) is now `PicoProducer/python/workers/` (`git mv`), importable as `TauFW.PicoProducer.workers`. The
rename itself added no compatibility module (hard-break rule); one was added afterwards, see A5. Updated callers: `jobs/worker_command.py` (`PROCDIR`), `cli/config.py`
(`pico.py channel` checks the skim script there), `analysis/SumWeights.py`, the two `legacy/analysis` generator
modules, the HTCondor submit template comment, `Tests/BBB/cases.py` (`pico.bookkeeper`),
`Tests/BBB/pico_harness.py` (`pico.workers`), `Tests/PicoProducer/processors/testBookkeeper.py` (marked `edited` in
`Tests/migration.json`), `Utilities/_audit_io.py`, the CMSDAS 2020 preselection notes and the READMEs.

**For users:** a private script that imports `TauFW.PicoProducer.processors` should import
`TauFW.PicoProducer.workers`; the old name still works with a warning (A5). Job lists written before this change name
`python/processors/picojob.py`; they still run through the forwarders of A5, and `pico.py resubmit` rewrites them
with `python/workers/`. Channels in `config/config.json` name only the script (`skimjob.py`), so they need no change.

**Check:** BBB normalizes worker paths to `<pico>/picojob.py`, so no baseline changes. The comparison harness is
unchanged (296 scenarios), and `Tests/check_harness.py` passes.

### A4. Documentation

- [docs/PicoProducer/API.md](../PicoProducer/API.md): usage, the pipeline, each method with its side effects
  and `pico.py` equivalent, construction, the records, known limitations (working directory and thread safety,
  messages of lower-level code, workers reading the global configuration).
- [docs/PicoProducer/IO.md](../PicoProducer/IO.md): the files each step reads and writes, the job config keys,
  the merged tuple.
- `Utilities/IOInventory.md` regenerated.

**Check:** a smoke test drove `PicoProducer` directly with a silent reporter (fake catalog, storage and batch
system): `plan` writes nothing and restores the working directory, `submit` → `status` → `merge(clean=True)` returns
the expected artifacts and removes the job output, and every record survives a JSON round trip
(`to_dict`/`from_dict`).

### A5. Compatibility layer for `processors/`

An exception to the hard-break rule, at the user's request: the rename in A3 broke private scripts and job lists
outside the repository, which in-repo caller updates cannot reach. `PicoProducer/python/processors/` is back as a
deprecated layer with no worker code ([README](../PicoProducer/python/processors/README.md)):

- `__init__.py` re-exports `TauFW.PicoProducer.workers` and `processors/Bookkeeper.py` puts the
  `workers.Bookkeeper` module object into `sys.modules` under the old name (same classes, so `isinstance` holds).
  Both raise a `FutureWarning` naming the replacement; `FutureWarning` is shown by default, `DeprecationWarning`
  is not.
- `picojob.py` and `skimjob.py` forward to `workers/` with `runpy` (same arguments, `__main__`, `sys.argv[0]`,
  output and exit status) after one notice on stderr. They load their helper `_forward.py` as a sibling file, so
  they work even where the package is not installed in `$CMSSW_BASE/python`.

`pico.py resubmit` already rebuilds the job list from the job config (`jobs/pipeline.py`), so the forwarders matter
only for jobs queued before the update, job-list lines run by hand and task files submitted without `pico.py`.
Nothing in the repository uses the layer, so no output changes. **Removal:** delete the directory and
`Tests/PicoProducer/compat/` once no job lists from before 2026-10-13 are in use.

**Check:** `python -m unittest discover -s Tests/PicoProducer/compat` (any Python 3.9+, no ROOT; 10 tests): the
shim runs against a fake `workers/` package (import aliases, warnings, forwarded arguments and exit status, a missing
worker) and is checked against the checkout (every file `processors/` had is covered, every shim has a worker).

### B. Command-line and worker fixes (P12, P13, P14, P15, W01, W02), with re-locked baselines

| Bug | Fix |
|---|---|
| P12 | Worker commands pass `--opts` (the workers' `-E/--opts`) instead of `--opt`, which only worked through argparse's prefix matching |
| P13 | `install` is an entry of the `cli.COMMANDS` table, so `pico.py install` no longer also prints "subcommand 'install' not implemented!" |
| P14 | `pico.py install` accepts `cmssw` (was misspelled `cmmsw`) |
| P15 | Won't fix, documented in `cli.parser.build_parser`: `status`/`hadd`/`clean` do not take the submission options, and `hadd` reuses `-m` for `--maxopenfiles` |
| W01 | Won't fix: `skimjob.py` accepts `-E/--opts` and ignores them, so every worker takes the same command line |
| W02 | `picojob.py`'s description line no longer repeats skimjob's |

BUGS.md locations now point to `cli/`, `api/` and `workers/`.

**Baselines:** `pico.run` and `pico.jobs` change again (`--opt` → `--opts`) and are re-locked together with B3 of
Part 4: `python3 Tests/run.py bbb lock --replace` after checking that the differences are only the option order
(P08/P09), `-m -1` (P10) and `--opts` (P12). The comparison harness against the A4 commit differs only in `--opts`;
`pico.py install` was checked by hand.

---

## 11. Framework: the TauFW orchestrator (Part F)

**Date:** 2026-10-13
**Details:** [Framework/README.md](../../Framework/README.md)

TauFW had no single entry point: users chained `pico.py`, Plotter scripts and Fitter drivers by hand, and the
production state lived only in PicoProducer's job configs. The new top-level package `Framework` (importable as
`TauFW.Framework`) runs an analysis pipeline from a recipe, step by step, with a persisted run record.

### What changed

- **`Framework` class** (`Framework/python/framework.py`): `plan`, `start`, `advance`, `run`, `status`. It builds
  each stage's request from the recipe, keeps `run.json`, and decides whether to wait, resubmit or move on. It
  never prints (reporter), never sleeps unless asked (`advance(wait=True)`), and construction reads files only.
- **Stages** (`Framework/python/stages/`): the contract (`Stage`, `StageState`: `NEW → SUBMITTED → WAITING →
  MERGING → DONE`, plus `FAILED` and `NOT_IMPLEMENTED`; `StageOutcome`). `ProductionStage` uses only the public
  PicoProducer API (`request`, `plan`, `submit`, `resubmit`, `status`, `merge`, `run_local`); its policy is the pure
  function `decide_next` (wait / resubmit / merge / fail, with `max_tries`). `histograms` and `fit` are
  placeholders with declared contracts (`HistogramSpec`/`ShapeArtifact`, `FitSpec`/`FitResult`).
- **Recipes** (`recipe.py`): see the [analysis guide](../../Analyses/README.md) (moved from `Framework/recipes/` in section 14).
- **Run record** (`run_record.py`): `taufw_runs/<name>_<time>/run.json` (schema 1) with the recipe, the
  PicoProducer configuration snapshot, and per stage: state, attempt, request, submissions, last status, artifacts
  and history. Saved after every stage step, atomically (temporary file + `os.replace`).
- **Reporting** (`reporting.py`): `FrameworkReporter` (TauFW.Utilities CLI + plain-text `run.log`) and
  `SilentReporter`; PicoProducer's messages are routed to the same terminal and log.
- **Command line** `Framework/scripts/taufw.py`: `plan RECIPE [--local -m N]`, `start RECIPE [--run-root DIR]
  [--wait --poll S]`, `advance RUN_DIR [--wait --poll S]`, `status RUN_DIR`. No logic: each command calls the
  Framework.
- **PicoProducer API:** `PicoProducer.request(**fields)` builds a `JobRequest`, so the Framework never imports
  PicoProducer internals (and imports PicoProducer only when a production stage is built).
- **Repository:** `.gitignore` keeps `Framework/python/**/__init__.py` and ignores `taufw_runs/`;
  `Tests/support/bootstrap.py` mirrors `Framework`; the root README has a "Running a pipeline" section.

### Tests

- `Tests/Framework/` (unittest, any Python 3.9+, no ROOT): a fake PicoProducer drives the state machine
  (start → waiting; failed chunks resubmitted until `max_tries` → `FAILED`; complete → merge → `DONE` with artifacts;
  invalid or refused merges; no samples; placeholder stage → `BLOCKED` without losing the production results;
  `--wait` loop; an exception is recorded and the state kept; `status` is read-only), the `decide_next` truth table,
  `run.json` round trip, crash-safe save and unique run directories, recipe validation, and `taufw.py` commands and
  parser. 21 tests: `python -m unittest discover -s Tests/Framework`.
- BBB case `framework.production` (lxplus): `taufw.py plan`, `start`, `advance` (a missing chunk is resubmitted),
  `advance` (merge with cleanup; the `histograms` placeholder blocks), `status`, against the fake HTCondor of the
  PicoProducer harness. It snapshots the plan and status output, the normalized `run.json` after each step, the
  merged tuples and the remaining files. It is new, so it is added with the next lock
  (`python3 Tests/run.py bbb lock --replace`, together with the intended changes of `pico.run` and `pico.jobs`).
- On Windows, an integration run of the real `Framework` with the real `PicoProducer` API (fake catalog, storage and
  scheduler) went through submit → resubmit → merge → `BLOCKED` with the expected artifacts and `run.log`.

---

## 12. Framework: plots, histograms and fit stages (Part G)

**Date:** 2026-10-13
**Details:** [Framework/README.md](../../Framework/README.md), [docs/Fitter/BUGS.md](../Fitter/BUGS.md),
[docs/Plotter/BUGS.md](../Plotter/BUGS.md)

After Part F only the production stage ran; `histograms` and `fit` were placeholders. To have a working framework
to test now, the Framework is connected to the Plotter and Fitter **as they are**: their existing scripts are run
with the arguments analysts use today, behind small public APIs. The modules are cleaned up later behind the same
APIs, without changing the Framework. The wrapped workflow is the combined TES + TauID fit (`Fitter/run_inputs.sh`
and `Fitter/run_workflow_zmm.sh`, option 3), plus control plots with `Plotter/plot.py`.

### What changed

- **`TauFW.Utilities.Process`** (new): `Command`, `CommandResult`, `ProcessRunner`. Runs commands one after the
  other without a shell, one log file per command, and stops at the first failure. A command is ok only if it exits
  with 0 **and** writes every expected output (modified after it started): the Fitter scripts run `combine` through
  `os.system` and ignore its exit code, and their output folders are shared by all runs.
- **`TauFW.Fitter.api`** (new, `Fitter/python/api/`): `TauESID` with `plan_shapes`/`make_shapes`/`preflight_shapes`
  (= `run_inputs.sh`) and `plan_fit`/`fit`/`preflight_fit` (= `run_workflow_zmm.sh`: datacards, MultiDimFit,
  FitDiagnostics and post-fit shapes, plots, correction files, and once per era the summary). The commands are
  pure data (tested against the shell scripts word for word); `read_fit_values` parses `FitparameterValues_*.txt`.
- **`TauFW.Plotter.api`** (new, `Plotter/python/api/`): `ControlPlots` with `plan`/`make`/`preflight` around
  `plot.py`.
- **Stage context** (`Framework/python/stages/base.py`): every stage now gets a `StageContext` (run directory,
  artifacts of the `DONE` stages before it); signatures are `plan(spec, context)` and
  `advance(spec, stage_record, reporter, context)`. `plan()` passes the planned artifacts forward, so the fit plan
  already shows the working points of the histograms plan. `PreflightError`: an environment that is not ready
  (no `cmsenv`, `combine` missing, ...) leaves the stage `NEW` with the reason as its message.
- **Local stages** (`stages/local.py`, `plots.py`, `histograms.py`, `fit.py`): `NEW → DONE` or `FAILED` in one
  `advance`. Logs go to `<run dir>/<stage>/NN_<label>.log`; `run.json` lists every command with exit code and
  duration; a failure prints the last 20 log lines. The fit takes its working points from the recipe or from the
  shapes of the histograms stage. Stage order: `production, plots, histograms, fit`; any subset is allowed.
- **`taufw.py`:** `plan` shows the commands of the local stages as a table, with preflight problems as warnings;
  `status` shows the fitted values; every unfinished run gets the "Continue with" hint.
- **Recipes:** see the [bundled analyses](../../Analyses/README.md#bundled-analyses)
  for the current examples (moved to `Analyses/` in section 14).
- **Repository:** `.gitignore` keeps `Fitter/python/api/__init__.py` and `Plotter/python/api/__init__.py`; the menu
  help (`Utilities/python/Menu/faq.py`) describes the stages; "Public API" sections in the Fitter and Plotter
  READMEs.

### Bugs fixed on the wrapped path

New registers `docs/Fitter/BUGS.md` and `docs/Plotter/BUGS.md` (same policy as PicoProducer; `# BUGS <ID>` at the
changed lines).

| ID | Fix |
| --- | --- |
| F01 | `run_workflow_zmm.sh`: `merge_tau_jsons.py -y $YEAR` (the default 2024 made the 2025 merge find nothing) |
| F02 | `run_workflow_zmm.sh`: `make_tid_2025.py -y $YEAR` |
| F03 | `run_inputs.sh` (and `_2526`, `_pnet`): the mutau exit status is read right after its pipe; a mumu failure counts too |
| F04 | `makecombinedfitTES_SF.py`: the dead `input_file` lookup and the required-but-unused `--input_file` are removed; callers updated |
| F05 | `makecombinedfitTES_SF.py`: no 1-sigma interval no longer raises `TypeError` (the parameter file is written) |
| F06 | `makecombinedfitTES_SF_postfit.py`: `--impacts` / `--impacts-parallel` are honored; `run_workflow_zmm.sh` passes `--impacts` |
| F07 | `createinputsTES.py`: the rebinned file is read where `rebinning.py` writes it (to confirm on lxplus) |
| L01 | `plot.py`: misspelled DeepTau branch names (`VSVjet`, `VSVSe`) |

Registered only (off the path): F08-F10 (options 4-6 of `makecombinedfitTES_SF.py`), L02 (`fname=` vs `file=` in
the Plotter sample builders).

### Known limitations

See the analysis guide's [current limitations](../../Analyses/README.md#current-limitations).

### Tests

- `Tests/Utilities/test_process.py` (10): logs, exit codes, expected and stale outputs, timeout, missing program,
  stop at the first failure.
- `Tests/Fitter/api` (14), `Tests/Plotter/api` (5): the API commands equal `run_inputs.sh`, `run_workflow_zmm.sh`
  and `plot.py` command lines; missing outputs fail although the exit code is 0; preflight; fit values.
- `Tests/Framework/test_stages.py` (16): the whole pipeline after production with fake APIs, preflight leaves the
  stage `NEW` and a later `advance` continues, a failed command fails the stage (log tail), fit points from the
  recipe or the shapes, planned artifacts, spec validation, `taufw.py plan`. `test_framework.py` updated for the new
  signatures. `Tests/run.py` runs the two new API suites with the unit checks.
- BBB `framework.production`: its recipe no longer has the histograms placeholder (the local stages run scripts and
  are not part of BBB). Its snapshot changes on purpose (the plan has no histograms stage, the run ends `DONE`
  instead of `BLOCKED`): re-locked on lxplus with `python3 Tests/run.py bbb lock --replace` (the lock always captures the whole suite; the
  other 18 cases were unchanged).
- On lxplus (to do): `taufw.py plan Analyses/tes_id_2025` (was `Framework/recipes/tes_id_2025.yml`), then a
  VTight/Tight run compared with the
  shell scripts in a clean copy (`FitparameterValues__mutau_*`, `tau_sf/*VSjetVTight_VSeleTight*`).

## 13. Test runner: quiet defaults and BBB lock logs

**Date:** 2026-10-13

`normal`, `integration`, `all`, and `bbb check`/`lock` now capture worker output by default.
`-v`/`--verbose` streams full output, including every suite under `all`; the old quiet flags are removed.
`--tail N` applies in the default mode (80 lines; 0 means all) and is rejected with verbose output.

Quiet lock prints one P/F letter per case on one line, captures both fresh runs in
`Tests/.artifacts/logs/bbb/<case>.run1.log` and `<case>.run2.log`, and keeps the LOCK SUMMARY.
Failed cases show their reasons and both log tails with paths. Lock still rejects `--case` and publishes
only when the whole suite succeeds and every snapshot is repeatable. Baselines and physics code are unchanged.
`check_harness.py` keeps its own unittest `-q`/`-v` CLI.

Validation on Windows: all 27 offline harness checks pass; `bbb diff` reports 19 unchanged baselines.
`python -m unittest discover -s Tests/Utilities -p "test_*.py"` runs 60 tests but exposes existing
terminal/color-dependent menu checks (unchanged from HEAD). On lxplus with Python 3.9 in
`CMSSW_14_1_0_pre4`, run from the checkout:

```bash
python3 Tests/run.py bbb check
python3 Tests/run.py bbb check -v
python3 Tests/run.py bbb lock --replace
git status --short -- Tests/BBB/baselines/
git diff --exit-code -- Tests/BBB/baselines/
```

Both checks must pass; replacement must leave the baseline status empty and the diff exit zero.

## 14. Framework: analysis bundles and Python steps (Part H)

**Date:** 2026-10-13
**Details:** [Analyses/README.md](../../Analyses/README.md), [Framework/README.md](../../Framework/README.md)

Two needs: the configs of an analysis were spread over `Fitter/`, `Plotter/` and `PicoProducer/config/`, and custom
logic needed a new stage class. Now one directory holds a whole analysis, and a recipe step can be a Python file.

### What changed

- **Analysis bundles** (`Analyses/<name>/`: `recipe.yml`, the configs next to it, `steps/`; every path is relative
  to the directory of `recipe.yml`). The commands take the directory
  (`taufw.py plan Analyses/tes_id_2025`). `Framework/recipes/` moved to `Analyses/` (`example_mutau/`,
  `tes_id_2025/`, `README.md`); no copy is left behind. Both bundles carry copies of the Plotter and Fitter configs
  they use.
- **Path rule** (`Framework/python/bundle.py`): a stage's path option (`plots.configs`, `histograms.configs`,
  `fit.config`, `fit.config_mumu`, a python step's `file`; listed in each Spec's `_paths`) that names a file of the
  bundle uses that file **instead of** the module's config (whole file, no merging). Any other relative path is
  resolved by the module as before, so existing recipes keep working. `taufw.py plan` lists every file each stage
  reads and where it comes from (`bundle`, `module`, `absolute`). A relative path above the bundle (`../`) is never a
  bundle file. The relative `pico.config` is a bundle file (one above the bundle is made absolute, as before); the
  recipe keeps it as written (it was made absolute before).
- **Run copy of the bundle:** `start` copies the bundle (whole directory without hidden files, `__pycache__` and
  `taufw_runs/`; at most 50 MB) to `<run dir>/bundle/`, and every stage of the run reads the copy. A loose recipe
  file copies only the files its options name. `run.json` has a new `bundle` key (`{source, files}`; `{}` when
  reading older records, so the schema stays 1).
- **Python steps** (`stage: python`, `stages/python_step.py`, `step_runner.py`): `file`, `function` (`run`),
  `options`, `timeout`, optional `id`. The step runs in its own Python process (standard library only), in the run's
  bundle copy; it gets a `ctx` (options, upstream artifacts, its directory, bundle files, log) and returns a message
  and artifacts, which later stages see. Preflight checks the file, the function (with `ast`, nothing imported) and
  the options. A failure leaves the log tail as for the other local stages.
- **Stage ids:** python steps may be anywhere and any number of times, so stages are keyed by an id (built-in
  stages: their name; python steps: `id:` or the file name). `run.json` stage records, log directories and
  upstream artifacts use the id. The built-in stages keep their order and stay unique.
- **The run's PicoProducer config reaches the scripts:** `getconfig()` reads `$TAUFW_PICO_CONFIG` when it is set
  (read-only; a missing file is an error); unset, nothing changes. `Command` (Utilities.Process) has an `env` field.
  `PlotsRequest`, `ShapesRequest` and `FitRequest` have `pico_config`; the APIs set the variable on their commands,
  and preflight checks that file. The old warning that the scripts read the default config is removed.
- **`CommandPlan`, `RunReport`** moved from the identical copies in `Fitter/python/api/types.py` and
  `Plotter/python/api/types.py` to `TauFW.Utilities.Process` (callers updated; the APIs still export them).
  `config_file(config)` added to `ControlPlots` and `TauESID`.
- **`taufw.py init NAME [--from RECIPE] [--root DIR]`:** a new bundle; `--from` copies the module configs the recipe
  uses next to the new `recipe.yml` (a taken name becomes `<plotter|fitter>_<name>`) and points the recipe at the
  copies. The console menu lists the
  bundles in `Analyses/`.

### Known limitations

The sample lists are not part of a bundle yet: `plot.py` and `createinputsTES.py` import
`Plotter/config/samples_v15.py`, and the PicoProducer configuration names its own sample catalogs.

### Tests

- `Tests/Framework/test_bundle.py` (13): the path rule (paths above the bundle stay outside it; any layout inside it), `plan` paths,
  stage ids and their errors, the run's bundle copy (later edits do not reach a started run; caches and runs are
  skipped; a large bundle is refused before anything is written), old `run.json` without `bundle`, `make_bundle`,
  `taufw.py init` (copied names never clash).
- `Tests/Framework/test_python_step.py` (6): real step files run by `step_runner.py`: two steps passing artifacts
  (sibling import, bundle file, `$TAUFW_PICO_CONFIG`), an exception, a result that is not JSON, preflight, plan.
- Updated: `test_framework.py`, `test_stages.py`, `test_interactive.py`; `Tests/Utilities/test_process.py`
  (command environment), `Tests/Fitter/api`, `Tests/Plotter/api` (`pico_config`, `config_file`).
- BBB `framework.production` changes on purpose: `run.json` has the `bundle` key and `plan` prints the bundle and
  PicoProducer config lines. Re-lock on lxplus with `python3 Tests/run.py bbb lock --replace` once the other cases
  pass unchanged; `$TAUFW_PICO_CONFIG` is unset there, so the PicoProducer cases must not change.

## 15. common tools moved to Utilities: parallel processes and the loading bar

**Date:** 2026-10-13
**Details:** [Utilities/README.md](../../Utilities/README.md) (Terminal I/O, Parallel Python calls)

`common/python/` still holds the old shared helpers. The ones with few users were re-implemented in
`TauFW.Utilities` (Utilities style: one entry point per package, flow first, construction last, no import-time side
effects, no imports of `TauFW.common`) and their callers updated; the old modules are deleted. The logic is the same,
and the terminal output is byte for byte the same. The old output formats sit in a separate
`# ===== BACKWARD COMPATIBILITY, CLEANUP =====` section of each new module, so they can be modernized later in their
own commit (with a BBB re-lock where a baseline records them).

### What moved

| Old | New | Notes |
|---|---|---|
| `TauFW.common.tools.parallel.MultiProcessor` | `TauFW.Utilities.Process.ParallelProcessor` (`Process/_parallel.py`) | Same queue (`max_parallel`, was `max`), pipe return, `kwret` merge, serial mode (`parallel=False`) and `close()`. The return values are sent by module-level functions instead of a bound method, so the processor itself is no longer pickled into each child. The verbose messages keep their old text. |
| `TauFW.common.tools.LoadingBar.LoadingBar` | `CLI.loading_bar(steps, **options)` returning `LoadingBar` (`CLI/_internal/loading_bar.py`) | Same characters on stdout (the CLI's output stream), including the backspace redraws. Options: `width`, `counter`, `remove`, `symbol`, `prefix` (was `pre`; default: the CLI prefix, `>>> `), `append`, `message`. `count(message="", steps=1)`. |
| `TauFW.common.math_helper` | removed | It only re-exported `sqrt, log10, ceil, floor` from `math`; `common/tools/math.py` imports them from `math` directly. |

### Dropped

- **The import-time `multiprocessing.Manager()`** of `common/tools/parallel.py`: importing the module started a server
  process that nothing used (and broke every child process under the `spawn` start method).
- **The `Thread` class** (a `Process` that printed its result): only `Tests/Plotter/testMultiThread.py` used it, in demo
  functions that were commented out of its `main`. Those functions and the helper they alone used are removed.
- **`LoadingBar.update()` / `message()` as public methods:** only the Python 2 demo `Tests/common/testLoadingBar.py`
  called `message()`. The drawing is now private.
- **`Tests/common/testLoadingBar.py`** (Python 2 `print` statements; the runner listed it as `legacy`, never run):
  replaced by unit tests. Its records are removed from `Tests/inventory.json`, `Tests/migration.json` (38 → 37
  files, `check_harness.py` updated), `Tests/LEGACY_BROKEN_CASES.md` and `Tests/README.md`.

### Bug fixed

`LoadingBar.count(n)` with an integer step called `args.remove(i)` on a tuple and raised `AttributeError`. The new
`count(message, steps)` takes the number of steps as a keyword. No caller in the repository passed an integer, so no
output changes.

### Callers updated

- `PicoProducer/python/storage/validation.py` (`itervalid`, `iterevts`): `ParallelProcessor(max_parallel=ncores)`.
- `PicoProducer/python/datasets/sample.py`, `jobs/chunking.py`: `CLI().loading_bar(...)`, created when the bar is
  needed (never at module level, so redirected stdout is honored).
- `PicoProducer/python/jobs/reporting.py`: `Reporter.progress(steps, **options)` takes `CLI.loading_bar`'s arguments;
  `ConsoleReporter` returns `CLI().loading_bar(...)`. `jobs/status.py` passes `prefix=` instead of `pre=`.
- Dead imports removed: `MultiProcessor` in `Plotter/python/sample/SampleSet.py` and `MergedSample.py`, `LoadingBar`
  in `SampleSet.py`.
- `Tests/BBB/cases.py` (`common.formatting`), `Tests/Plotter/testMultiThread.py`, and the legacy script
  `Plotter/Legacy/plot_compare_nano.py` (import only).
- `Utilities/IOInventory.md` regenerated (it also picks up earlier, unrelated file moves).

### Tests

- `Tests/Utilities/test_cli.py`: the loading bar must write exactly the bytes the old class wrote, for seven cases
  recorded from it before it was deleted (default, over-counting, counter, append, messages, symbol and newline,
  remove); the CLI prefix default; `count(steps=...)` and `done`. Before the deletion the new bar was also compared
  with the old one on 4000 random cases (all identical).
- `Tests/Utilities/test_process.py`: `ParallelProcessor` serial calls, `kwret` dict/list merge, `close()`; the parallel
  cases (start order, the queue, `kwret` through the pipe) need the `fork` start method and run on Linux (lxplus).
  On Windows the parallel path was checked separately under `spawn`.
- BBB: no baseline changes are expected (`common.formatting` writes the same bytes). Check on lxplus with
  `python3 Tests/run.py bbb check`; no re-lock.

## 16. common tools moved to Utilities: numeric helpers

**Date:** 2026-10-13
**Details:** [Utilities/README.md](../../Utilities/README.md#numeric-helpers)

`common/python/tools/math.py` was re-implemented as the new package `TauFW.Utilities.Math` (`Math/_math.py`), in
the same way as §15: Utilities style, no imports of `TauFW.common`, every caller updated, the old module deleted.
The functions print nothing, so there is no BACKWARD COMPATIBILITY section; the rule here is the same results for the
same inputs.

### What moved

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

### Dropped

- **`ceil2digit`**: no callers, and it called `log`, which the module never imported (`NameError` on any nonzero input).
- **`round2digit`**: no callers; `Plotter/python/sample/Sample.py` imported it without using it.

### Callers updated

- `PicoProducer/python/jobs/chunking.py`: `partition_by_sum`, `ceil` from `math`.
- `PicoProducer/python/storage/validation.py` (`itervalid`, `iterevts`): `partition`.
- `Plotter/python/plot/Plot.py`: `magnitude`, `columnize`, `scale_vector`; `ceil`, `log10` from `math`.
- `Plotter/python/sample/Sample.py`: `relative_difference`.
- `Fitter/Zpt/validateZpt.py` and the legacy script `Legacy/OldAnalysis/YearIndependent/plot_GENSIM.py`: `float_range`.
- `Fitter/Zpt/measureZpt.py`: unused `scalevec` import removed.
- `Tests/BBB/cases.py` (`common.chunking`), `Tests/PicoProducer/testEventBased.py` (its `Tests/migration.json`
  `edited` note updated).
- `Utilities/IOInventory.md`: the deleted module and the shifted `chunking.py` lines (edited by hand, not regenerated).

### Tests

- `Tests/Utilities/test_math.py`: every function against results recorded from the old module before it was deleted,
  including the empty and edge cases and the input-not-changed check. Before the deletion the new functions were also
  compared with the old ones on 4000 random rounds (all identical).
- BBB: `common.chunking` was run locally against its baseline (identical output). No baseline changes are expected;
  check on lxplus with `python3 Tests/run.py bbb check`; no re-lock.

## 17. common tools moved to Utilities: the printf-style table

**Date:** 2026-10-13
**Details:** [Utilities/README.md](../../Utilities/README.md#terminal-io) (`CLI.table`); open items in [TODO.md](TODO.md)

`common/python/tools/Table.py` was re-implemented as `CLI.table(...)`, returning a `Table`
(`Utilities/python/CLI/_internal/table.py`), in the same way as the loading bar in §15. No logic changed: every line is
byte for byte what the old class wrote, and the callers' tables print in the same cases as before. The old quirks are
kept in a section with a new banner, `# ===== LEGACY, CLEAN UP LATER =====`: the four constructor forms told apart by
argument types, the header always underlined with raw ANSI codes (even into a file), the old `LOG.warning` text for
the two warnings, and the two debug lines at high verbosity. They are listed in [TODO.md](TODO.md) for a later commit
with a BBB re-lock.

### What moved

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

### Callers updated

- `Plotter/python/plot/utils.py`: six tables (`printhist`, the ratio and error tables), most at `minimum_verbosity=3`.
  `printhist(**kwargs)` maps its `verb`, `pre`, `level` and `ul` keywords as `LOG.table` did. The table in the
  `TGraph`/`TGraph` ratio branch prints its rows with `print_header` (it did with `printheader` before); kept as is and
  listed in [TODO.md](TODO.md).
- `Plotter/python/sample/HistSet.py` (four tables), `Fitter/python/plot/datacard.py` (`createinputs` event table).
- `common/python/tools/log.py`: `Logger.table`, `tableheader`, `row` and the `Table` import removed.
- `Tests/BBB/cases.py` (`common.formatting`), `Tests/Plotter/testRDataFrame_Sample.py`, `Tests/Plotter/testStack.py`,
  `Tests/PicoProducer/testSFs.py` (`edited` notes in `Tests/migration.json`).
- `Utilities/_audit_io.py` counts `print_header`/`print_row`/`print_rows` as terminal output, like the old names.
  `Utilities/IOInventory.md`: the rows of the changed files and the totals, edited by hand (not regenerated).

### Dropped

- **`Tests/common/testTable.py`** (case `common.table`, Python 2 `print` statements, listed as `legacy` and never run):
  replaced by unit tests. Its records are removed from `Tests/inventory.json`, `Tests/migration.json` (37 → 36 files,
  `check_harness.py` updated), `Tests/LEGACY_BROKEN_CASES.md` and `Tests/README.md`. It was the only caller of
  `printhist(verb=...)`.

### Tests

- `Tests/Utilities/test_cli.py` (`TableTests`): 21 cases recorded from the old class before it was deleted (both format
  forms, the integer forms, short and extra rows, `%r`, `%%` and `%05d` columns, both warnings and the exception for too
  few titles, verbosity gating and the debug lines, no prefix/underline, `suffix`, `save`, `print_rows`, `str`); the
  underline when redirected; silent construction. Before the deletion the new table was also compared with the old one
  on 3000 random tables (formats, row lengths, verbosities, prefixes; all identical).
- BBB: `common.formatting` and `common.chunking` were run locally against their baselines (identical output). No baseline
  changes are expected; check on lxplus with `python3 Tests/run.py bbb check`; no re-lock.

## 18. Drawing library moves to Utilities: BBB safety net first

**Date:** 2026-10-14
**Plan:** the Plotter's drawing code (`Plot`, `Plot2D`, `Stack`, `Ratio`, `CMSStyle`, `SampleStyle`, the histogram
helpers of `plot/utils.py` and the label helpers of `plot/string.py`) moves to `TauFW.Utilities.Drawing`, so that the
Fitter and PicoProducer can draw without importing the Plotter (target architecture: pipeline stages never import
each other; shared libraries may be imported by all). The move must not change any output, and nothing recorded what
the drawing code draws: the `plotter.*` cases cover histogram filling only. So the work is split in two steps:

1. **(this step)** a new BBB case, `drawing.canvas`, is added and locked on lxplus with the code *before* the move;
2. the move itself (next step), after which `bbb check` must pass with no difference.

### The `drawing.canvas` case

`Tests/BBB/cases.py` (`drawing_canvas` and its helpers; the code under test is imported in one place,
`_drawing_modules()`, the only part that changes with the move). It builds fixed synthetic histograms and graphs (no
files, no random numbers) and records:

- the canvases of seven plots: a `Plot` comparison with ratio, error band, normalization, legend and text; a `Plot`
  with variable binning and log y; a `Plot` with `drawbins` lines and labels; a `Stack` with data, three backgrounds, signal, ratio and error band;
  a `Stack` with the fraction panel; a `Plot` of two `TGraphAsymmErrors`; a `Plot2D`. A canvas is recorded as the
  tree of pads and primitives with class, name, title, draw option, line/fill/marker/text attributes, pad margins,
  log/grid/tick flags and user ranges, axis titles, ranges and sizes, histogram contents and errors, stack members,
  graph points, legend entries, text and line coordinates;
- the results of the histogram helpers (`normalize`, `grouphists` with the default `SampleStyle` color,
  `gethistratio`, `getgraphratio`, `geterrorband`, `dividebybinsize`, `addoverflow`, `capoff`, `resetrange`,
  `getconstanthist`, `getbinning`, `resetedges`, `havesamebins`, `getbinedges`, `getTGraphRange`, `sumhists`,
  `ensurepoisson`, `normalizebins`);
- `CMSStyle` texts for three era settings, `SampleStyle` colors and titles (including misses), the label helpers
  (`makelatex`, `maketitle`, `makehistname`, `makefilename`, `estimatelen`, `match`);
- the global `gStyle` settings before and after drawing (`CMSStyle.setTDRStyle` runs when `Plot` is imported);
- everything printed at `LOG.verbosity = 3`, with object addresses replaced by `0x?` and the module path of the
  drawing code by `<drawing>.`; the names of the saved png/pdf files (not their bytes).

A scenario that raises records the exception type and message instead, so the lock does not depend on every scenario
working. The first lock on lxplus showed four such scenarios. Two were wrong calls in the case and were changed to
match the real callers: `drawbins` needs a plot with `ymin`/`ymax` (as in `Fitter/Zpt/measureZpt.py`), and
`normalizebins` needs a stack that has been drawn (as in the `Ratio` fraction panel). Two are real latent bugs in
code without callers that reaches them, registered as [Plotter BUGS](../Plotter/BUGS.md) L03 (`sumhists` adds to an
undefined `sighist`; its `NameError` stays recorded until it is fixed after the move) and L04 (`estimatelen` with
several arguments; the case now passes one list, like `Plot.drawlegend`). `Tests/BBB/snapshot.py` gained `drawn_snapshot`, `primitives_snapshot` and `style_snapshot` for this.

### Lock (done)

`bbb check` refuses to run while the case list differs from the lock, and `lock` captures the whole suite. So:
`python3 Tests/run.py bbb lock --replace`, then `python3 Tests/run.py bbb diff`, which must show only the new
`drawing.canvas` baseline and no change to any other case. Done on lxplus on 2026-10-14 (19 same, 1 added); the only
recorded exception is `$.tools.sumhists` (L03).

### The move

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

### Callers updated

About 55 files, imports only: the Plotter (`sample/`, `plot/Variable|Selection|Context|string`, `plot.py`,
`plot_postfit*.py`, `plot_v10.py`, `tutorial/`, `Legacy/`, `python/legacy/`), the Fitter (`python/plot/`,
`createinputs*`, `Zpt/`, `tutorial/`, `ETauFR/Plotter/`, `plot_measurements.py`), PicoProducer
(`utils/compare{Nano,Pico}.py`, `data/pileup/getPileupProfiles.py`), `Legacy/OldAnalysis/`, `Tests/Plotter/` (16 scripts,
`edited` notes in `Tests/migration.json`) and the BBB case (`_drawing_modules()` only).
`Utilities/IOInventory.md`: the rows of the 7 moved files are gone (the audit does not scan Utilities), and line
numbers of the touched callers are updated; merged into the hand-edited file, not regenerated.

### Checks on Windows (no ROOT)

Every Plotter, Fitter and drawing module was imported against a stand-in ROOT module before and after the move, and
the names each module defines were compared, functions by their parsed source. All Plotter modules (`sample/*`,
`plot/Variable|Selection|Context|string|MultiDraw`, `methods/QCD_OSSS`) and the Fitter modules define exactly the same
names with the same code as before. The drawing modules differ only as intended (no `Variable`, `Var`,
`ensuredir`, `ensureTFile`, `Logger`, `moddir`; the `_is_variable` checks). Three Fitter modules that failed to import
before still fail the same way (`correlation.py`: Python 2 `xrange`; `runpostfit.py`; `ETauFR/zttmodels.py` needs
Combine). Every `from M import name` and `M.attribute` in the repository (813) names something that exists. The
compile failures among the touched files are the four Python 2 scripts already listed in TODO.md section 8
(`Fitter/HighPT/createinputs.py`, `Fitter/Zpt/utils.py`, `PicoProducer/utils/compare{Nano,Pico}.py`).
`check_harness.py` passes.

### First `bbb check`: the repr of ROOT objects

The first `bbb check` on lxplus failed `drawing.canvas` in 12 verbose stdout lines only: ROOT objects printed as
`<cppyy.gbl.TH1D object at 0x...>` instead of `<TH1D('t_DY','t_DY') at 0x...>`. `TauFW.common.tools.root` replaces
`TNamed.__repr__` when it is imported, and the old `plot/utils.py` imported it (for `ensureTFile`, unused there). The
drawing library no longer imports `common`, so `hist_tools.py` now sets the same `TNamed.__repr__` itself, in its
`LEGACY, CLEAN UP LATER` block. The canvases, styles and helper results were already identical.

### To do on lxplus

`python3 Tests/run.py bbb check`: every case must pass unchanged, `drawing.canvas` included (no re-lock). Its case
imports only the drawing library, not the Plotter's sample code as the old `SampleStyle` import did, so a pass also
shows that the drawing code no longer depends on that import. Then `python3 Tests/run.py normal`.


## 19. Import-boundary test and coupling inventory

**Date:** 2026-10-14

Roadmap step 1 is implemented in `Tests/check_import_boundaries.py`, using the Python standard library only.
Stages (PicoProducer, Plotter, Fitter) cannot import one another. Framework can import exactly the stage API
modules; libraries remain available to everyone. Tau_Trigger_SF has no registered TauFW package layout here.
AST traversal includes function-level imports and parent-module forms. Implicit `config.*`, `plot.*`, and
`sample.*` imports without a matching local module are reported too. Legacy directories and Tests are excluded.

The adjacent JSON inventory contains one reason/roadmap entry per existing file/module pair plus separate
unparseable-file exemptions. **Known violations still fail**: this is an isolation progress check, not a green
baseline. Fixed violations with leftover entries fail as stale; parse exemptions also become stale when their
file becomes parseable. Python 2 parse failures are reported separately and their complete import statements
are recovered using tokenize and parsed with AST. Recovery failures are never suppressed by exemptions.

Re-measured after the drawing move (including recovered Python 2 imports):

| Coupling | Occurrences | File/module pairs | Files |
|---|---|---|---|
| Fitter -> Plotter | 20 | 19 | 17 |
| PicoProducer -> Plotter | 2 | 2 | 2 |
| Plotter -> PicoProducer | 2 | 1 | 1 |
| Total | 24 | 22 | 20 |

Nine existing files fail full-file parsing. There are no new/stale entries or import-recovery errors in the
seeded inventory. Framework's three API imports in one file are allowed and are not counted as violations.

`Tests/run.py` registers `check_import_boundaries` alongside the offline checks; checks/all and the testing
menu obtain it through the existing catalog, status output and logging. No production source changed.

Windows validation: 10 detector self-tests pass, and all 28 existing offline harness checks pass. The targeted
runner command reports FAIL/exit 1 with the known debt as intended; catalog metadata includes the new check
without ROOT imports. No full normal or BBB suite ran, and no baselines were changed. Targeted lxplus
confirmation remains in TODO §1.

Potential simple follow-ups, recorded only: `Fitter/MuTauFR/createinputs.py:11` imports the removed Plotter
datacard path (the Fitter helper exists); `Fitter/python/plot/rebinning.py:5` imports `ensuredir` through Plotter
instead of its home in `TauFW.common.tools.file`; postfit helpers import `CMSStyle`/`setera` through sample utilities
even though Drawing now owns CMSStyle (check the setera behavior before replacing it). The two PicoProducer
comparison utilities still use Plotter Variable and could be migrated or archived. None were fixed here.

## 20. Fitter imports drawing helpers from their own home

**Date:** 2026-10-14

Five Fitter files imported `CMSStyle` or `ensuredir` through `TauFW.Plotter.sample.utils`, which only re-exports
them. They now import them from where they live; imports only, nothing else changed.

| File | Before | After |
|---|---|---|
| `Fitter/TauES_ID/plot2DScan_MultiDimFit.py` | `from TauFW.Plotter.sample.utils import CMSStyle` | `import TauFW.Utilities.Drawing.CMSStyle as CMSStyle` |
| `Fitter/TauES_ID/plotParabola_POI_region.py` | same | same |
| `Fitter/TauES_ID/plotPostFitScan_POI.py` | same | same |
| `Fitter/python/plot/rebinning.py` | `from TauFW.Plotter.sample.utils import ensuredir` | `from TauFW.common.tools.file import ensuredir` |
| `Fitter/python/plot/postfit_TES.py` | `... import CMSStyle, setera` | `CMSStyle` as above; `setera` still from the Plotter |

The names are the same objects as before (`sample/utils.py` binds `TauFW.Utilities.Drawing.CMSStyle` and
`TauFW.common.tools.file.ensuredir`). What the scripts no longer get is the side effect of importing the Plotter's
sample code (`Variable`, `Sample`, `SampleSet`, and through `ResultDict` the RDataFrame setup in
`common/tools/RDataFrame.py`). None of it affects their output: the three `TauES_ID` scripts set `gROOT.SetBatch(True)`
themselves, `rebinning.py` draws nothing, and no Plotter module prints or changes global ROOT state on import beyond
batch mode and object reprs. `postfit_TES.py` still imports `setera`, so it keeps the full import; `setera` sets both
the CMS lumi text and the sample globals used for normalization and is split in a later step.

### Tests

All five files parse; every `CMSStyle.*` attribute they use exists in `TauFW.Utilities.Drawing.CMSStyle`.
`Tests/check_import_boundaries.py` reported the four fully decoupled files as stale; their entries are removed from
`Tests/import_boundary_allowlist.json` (22 -> 18 pairs). Fitter -> Plotter is now 16 occurrences / 15 pairs / 13
files; no new or stale entries. Not run on lxplus yet (TODO §1).

## 21. ROOT expression helpers move to `TauFW.Utilities.Expressions`

**Date:** 2026-10-14

`Plotter/python/plot/string.py` held three kinds of helpers: label helpers (moved to `Drawing/labels.py` in §18),
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

Three latent bugs found while recording the old results are registered, not fixed: [Plotter BUGS](../Plotter/BUGS.md)
L05 (`joinweights` with a weight `0` raises `TypeError`), L06 (`replacepattern` applies only the last of several
patterns), L07 (`joincuts` does not bracket `(x)||y`).

### Tests

- Before the move: the old functions were run on 41 fixed inputs (results and warnings recorded). After the move the
  new module gives the same 41 results; every moved definition has the same AST as before, and the remaining
  `string.py` definitions are unchanged.
- `Tests/Utilities/test_expressions.py` (new, 8 tests) pins those results, the latent bugs included; the Utilities unit
  tests pass (99, 2 skipped). Imported on Windows with ROOT blocked: `TauFW.Utilities.Expressions` and
  `TauFW.Plotter.plot.string` load, and `string.py` exposes the same function objects.
- `check_harness.py` passes. `check_import_boundaries.py`: the `datacard.py` entry was reported stale and is removed
  (18 -> 17 pairs); Fitter -> Plotter is 15 occurrences / 14 pairs / 12 files; no new or stale entries.
- The `plotter.*` BBB cases reach these functions through `Selection` and `Sample`; no baseline change is expected.
  Not run on lxplus yet (TODO §1).

## 22. PicoProducer comparison scripts removed

**Date:** 2026-10-14 (commit `d05d5cf`, by the user)

`PicoProducer/utils/compareNano.py` and `comparePico.py` were deleted. They filled and drew histograms with the
Plotter's `Variable` (`gethist`, `drawcmd`, `draw`): plotting work inside PicoProducer, and the last PicoProducer ->
Plotter imports. Both were Python 2 (`print` statements), unparseable under Python 3, and called by nothing; comparing
pico outputs between versions is what the BBB cases do.

Follow-up cleanup: their two entries and two parse exemptions are removed from `Tests/import_boundary_allowlist.json`
(reported stale); their sections from `PicoProducer/utils/README.md`; their rows from `Utilities/IOInventory.md`; their
names from the Python 2 list in TODO §8. Coupling now: PicoProducer -> Plotter 0; Fitter -> Plotter 12 files / 14
pairs; Plotter -> PicoProducer 1 file (`getconfig`, A03). `docs/Refactor-2025/dependencies/old-evidence.md` keeps its
references as a record of the old state.

## Root legacy archive consolidation

**Date:** 2026-10-14

- `LegacyAnalyses/` moved to `Legacy/OldAnalysis/`.
- `Fitter/Legacy/` and `Plotter/Legacy/` moved to `Legacy/Fitter/` and `Legacy/Plotter/`, preserving internal structure.
- Component `python/legacy/` packages remain in place to preserve imports.
- Archive documentation, inventories, school links and command examples now use the new locations.
- Archived source and configuration bytes are unchanged; existing runtime defects remain.
