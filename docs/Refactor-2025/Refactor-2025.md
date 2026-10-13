# Refactor-2025: change log

# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
**Branch:** `Refactor-2025`
**Last updated:** 2026-10-13

This document records the changes made on the `Refactor-2025` branch: what changed and why.
Sections are in the order the work was done. Each lists the relevant commits.
What is still open is listed in [TODO.md](TODO.md).

| # | Change | Date |
| --- | --- | --- |
| 1 | [Test migration and BBB regression tests](#1-test-migration-and-bbb-regression-tests) | 2026-10-12 |
| 2 | [FastSetup script](#2-fastsetup-script) | 2026-10-12 |
| 3 | [Removal of legacy Python 2 scripts](#3-removal-of-legacy-python-2-scripts) | 2026-10-12 |
| 4 | [Utilities package for future development](#4-utilities-package-for-future-development) | 2026-10-12 |
| 5 | [PicoProducer cleanup, Part 1: command-level BBB tests and bug register](#5-picoproducer-cleanup-part-1-command-level-bbb-tests-and-bug-register) | 2026-10-12 |
| 6 | [PicoProducer cleanup, Part 2: legacy area, explicit imports, no import-time side effects](#6-picoproducer-cleanup-part-2-legacy-area-explicit-imports-no-import-time-side-effects) | 2026-10-12 |
| 7 | [PicoProducer cleanup, Part 3: settings, datasets, storage, batch and jobs packages](#7-picoproducer-cleanup-part-3-settings-datasets-storage-batch-and-jobs-packages) | 2026-10-12 |
| 8 | [Fitter cleanup: legacy area](#8-fitter-cleanup-legacy-area) | 2026-10-13 |
| 9 | [PicoProducer cleanup, Part 4: jobs package](#9-picoproducer-cleanup-part-4-jobs-package) | 2026-10-13 |
| 9 | [Plotter cleanup: legacy area](#9-plotter-cleanup-legacy-area) | 2026-10-13 |
| 10 | [PicoProducer cleanup, Part 5: public API, command line, workers](#10-picoproducer-cleanup-part-5-public-api-command-line-workers) | 2026-10-13 |
| 11 | [Framework: the TauFW orchestrator (Part F)](#11-framework-the-taufw-orchestrator-part-f) | 2026-10-13 |
| 12 | [Framework: plots, histograms and fit stages (Part G)](#12-framework-plots-histograms-and-fit-stages-part-g) | 2026-10-13 |
| 13 | [Test runner: quiet defaults and BBB lock logs](#13-test-runner-quiet-defaults-and-bbb-lock-logs) | 2026-10-13 |
| 14 | [Framework: analysis bundles and Python steps (Part H)](#14-framework-analysis-bundles-and-python-steps-part-h) | 2026-10-13 |
| 15 | [common tools moved to Utilities: parallel processes and the loading bar](#15-common-tools-moved-to-utilities-parallel-processes-and-the-loading-bar) | 2026-10-13 |
| 16 | [common tools moved to Utilities: numeric helpers](#16-common-tools-moved-to-utilities-numeric-helpers) | 2026-10-13 |
| 17 | [common tools moved to Utilities: the printf-style table](#17-common-tools-moved-to-utilities-the-printf-style-table) | 2026-10-13 |

The reference environment for all of this is `CMSSW_14_1_0_pre4` (Python 3.9, ROOT 6.30).

---

## 1. Test migration and BBB regression tests

**Date:** 2026-10-12
**Commits:** `949ce56` (Test Migration 1), `bc1e28c`, `9b4b407`, `875ba88`, `905eac8`, `28b8c57`,
`dd0fb9e`, `0f36771`, `646d28f`, `9f9d510` (Lock BBB baselines), `ef80e40` (Re-lock BBB baselines)
**Details:** [Tests/README.md](../Tests/README.md), [Tests/LEGACY_BROKEN_CASES.md](../Tests/LEGACY_BROKEN_CASES.md)

### What changed

- **Tests moved to a top-level `Tests/` directory.** All 38 test files that lived inside the packages
  (`common/test/`, `Plotter/test/`, `PicoProducer/test/`, and `PicoProducer/python/analysis/TestModule.py`)
  were moved to `Tests/common/`, `Tests/Plotter/` and `Tests/PicoProducer/`. Their contents were not changed.
  [Tests/migration.json](../Tests/migration.json) records each original path and its content hash, so it can be
  checked that nothing was rewritten during the move.
- **A test runner, `Tests/run.py`.** Each test script runs in its own process and temporary workspace,
  using a fresh copy of the source, so tests cannot write into the checkout or reuse stale compiled libraries.
  [Tests/inventory.json](../Tests/inventory.json) classifies the 37 cases:

  | Group | Cases | Run by `python3 Tests/run.py normal`? |
  | --- | ---: | --- |
  | `local` | 26 | Yes |
  | `integration` | 7 | No; select explicitly with their original arguments (e.g. DAS, batch, real datasets) |
  | `legacy` | 2 | No; Python 2 syntax (`common.table`, `common.loadingbar`) |
  | `broken` | 2 | No; existing defects (`pico.sample`, `plotter.rdataframe`) |

  A case whose dependency (ROOT, NumPy, NanoAODTools, ...) is missing is reported as SKIP.
  Output is quiet by default, with logs kept under `Tests/.artifacts/logs/`; `-v`/`--verbose` streams full output.
- **BBB: exact regression tests** (`Tests/BBB/`). 13 cases build small, real ROOT trees and histograms from fixed
  fixtures ([Tests/fixtures/events.json](../Tests/fixtures/events.json)), run them through the framework, and
  snapshot the outputs: object names and classes, directory structure, axes, bin contents and errors, branch
  types and order, entry values. Floating-point values are stored as their exact IEEE bytes, so there is no
  tolerance. The cases cover:
  - common: table/loading-bar text, chunking and formatting;
  - Plotter: selections, weighted 1D/2D histograms, merging/splitting, DY stitching, QCD OS/SS, unrolling;
  - PicoProducer: tree writer schema, NanoAODTools bookkeeping, scale-factor lookup;
  - Fitter: shape naming, negative-bin sanitation, adaptive rebinning.

  `python3 Tests/run.py bbb lock` runs every case twice and refuses to write a baseline if the runs differ.
  `python3 Tests/run.py bbb check` compares against the committed baselines in
  [Tests/BBB/baselines/](../Tests/BBB/baselines/) and reports the exact field that changed.
  The baselines were locked in `CMSSW_14_1_0_pre4` on Linux (Python 3.9.14, ROOT 6.30/07, NumPy 1.24.3; recorded in
  each baseline) and re-locked (`ef80e40`) with the CMSSW-provided packages.
- **Harness self-checks:** `Tests/check_harness.py` (offline: hashes, Python 3.9 syntax, selection, lock/check
  mechanics) and `Tests/check_root.py` (lxplus: verifies that deliberate output changes are detected).
- **References updated** to the new locations: the `test` channel was removed from the PicoProducer default
  config and `config_example.json` (`TestModule` is now imported as `Tests.PicoProducer.analysis.TestModule`),
  and docstrings in `Plotter/python/sample/utils.py` point to `Tests/Plotter/testUnpacking.py`.

### Fixes found while running the tests

- `Plotter/python/plot/Stack.py` (`49dc76f`): an integer `ratio` was also used as the number of lower panels,
  so `ratio=3` crashed `setcanvas` and `ratio=2` added an empty panel. A nonzero integer now gives one panel,
  as in `Plot.draw`.
- `Plotter/python/plot/utils.py` (`a9c18d8`): `gethistratio` now accepts a `TGraph` denominator
  (e.g. a data graph after `dividebybinsize`).
- `PicoProducer/python/processors/skimjob.py` (`0f36771`): the Run 2 JME import is now done only when
  `--jec`/`--jec-sys` is used. Run 3 users can rely on CMSSW's built-in NanoAODTools without installing the
  standalone repository.

### Why

- **A safety net before refactoring.** The upcoming refactors will touch shared code in Plotter, PicoProducer and
  Fitter. The BBB baselines were committed *before* any production code is changed, so any refactor can be checked
  with `bbb check`: if the outputs are byte-identical, the refactor did not change the physics results.
  An intentional output change must be locked again explicitly (`bbb lock --replace`) and is visible in the Git diff.
- **Tests did not belong inside the packages.** Test scripts and their ROOT input file were mixed with the
  production code, `TestModule` was loadable as a production channel, and tests wrote plots and configs into
  the checkout. A separate `Tests/` tree with isolated workspaces keeps the packages clean and the runs repeatable.
- **Knowing which tests actually work.** Previously there was no way to run all tests at once or to know which ones
  were already broken. The inventory makes that explicit: broken and legacy scripts are documented in
  [LEGACY_BROKEN_CASES.md](../Tests/LEGACY_BROKEN_CASES.md) instead of failing silently, and the hashes prove
  those defects existed before the move.

---

## 2. FastSetup script

**Date:** 2026-10-12
**Commit:** `41c7c0e`
**Details:** [docs/FastSetup.md](../FastSetup.md)

### What changed

- New [setup.sh](../../setup.sh) entry point at the repository root, with the installer in `Utilities/FastSetup.sh`. From a fresh clone:

  ```bash
  git clone https://github.com/cms-tau-pog/TauFW TauFW
  cd TauFW
  source setup.sh
  ```

  It creates `CMSSW_14_1_0_pre4` (detecting EL8/EL9 for `SCRAM_ARCH`), moves the checkout to
  `CMSSW_14_1_0_pre4/src/TauFW`, installs TauIDSFs, the HTT lepton efficiencies, Combine `v10.6.1` and
  CombineHarvester `v3.1.0`, and builds.
- Options: `--cmssw-dir`, `--jobs`, `--run2-jme` (standalone NanoAODTools, only for Run 2 JEC/JER workflows), `--help`.
- It never overwrites or deletes existing work: existing checkouts are reused (with a warning if they are not
  at the tested tag), the HTT directory is backed up before being replaced, and a cross-filesystem move removes the
  original only after the copy is complete. A failed run prints the exact command to resume; completed steps are skipped.
- The [README](../README.md) installation section is split into **Automatic** (FastSetup) and **Manual** (the
  previous step-by-step instructions, unchanged in content).

### Why

- The manual installation has many steps (release, architecture, TauFW, TauIDSFs, HTT efficiencies, Combine,
  CombineHarvester, build) and several version pins that are easy to get wrong. One command gives every new user,
  and the test environment, the same reference setup.
- The BBB baselines from section 1 are only meaningful if everyone runs them in the same software stack.
  FastSetup produces exactly the environment they were locked in.
- Run 3 users should not need the standalone NanoAODTools; it is now opt-in (`--run2-jme`), matching the lazy
  import in `skimjob.py`.

---

## 3. Removal of legacy Python 2 scripts

**Date:** 2026-10-12
**Commit:** `ab5e7a2`

### What changed

27 scripts that only parse under Python 2 (print statements, `raise X, "msg"`) were deleted (6523 lines):

| Directory | Removed files | Python 3 replacement |
| --- | --- | --- |
| `Fitter/MuTauFR` | `compare.py`, `plotpostfit.py`, `writedatacard_{2016,2017,2018,UL2016_postVFP,UL2016_preVFP,UL2017,UL2018_withJEC}.py` | `compare.py` is a copy of combine's `diffNuisances.py`; `plotpostfit.py` is a near-copy of `paper/plotpostfit.py`. The seven per-era datacard copies were unused. |
| `Fitter/ETauFR` | `compare.py`, `writedatacard2.py` | `diffNuisances.py`; `writedatacard.py` (newer, kept) |
| `Fitter/TauID` | `createinputs.py`, `createinputs_simple.py`, `createinputs_v10_2p5.py`, `plotfit.py`, `plotfit_dm.py` | `paper/createinputs.py`, `TauES/createinputsTES.py`; `plot_measurements.py` / `make_tid_2025.py` |
| `Fitter/TauES` | `checkShapes_TES.py`, `createinputsTESPlots.py`, `makeTESfit.py`, `plotParabola_TES.py`, `plotPostFitScan_TES.py` | `createinputsTES.py`; the TauES_ID scripts (`makecombinedfitTES_SF*.py`, `plotParabola_POI_region.py`, `plotPostFitScan_POI.py`) |
| `Fitter/paper` | `plotpostfit.py`, `writecards.py` | `ETauFR/Plotter/plotpostfit.py` (partly); frozen 2021 paper workflow, kept in Git history |
| `Fitter/scripts` | `histedit.py` | None needed: an abandoned copy of the `pico.py` skeleton |
| `PicoProducer/utils` | `convertGENSIM_mutau.py`, `pickEvents.py`, `printNanoAOD.py` | One-off check; CMSSW's `edmPickEvents.py`; `rootls -t` / `Events->Print()` |

### Why

- **They cannot run.** Every one of these files fails with a `SyntaxError` in the reference Python 3.9 environment.
  Several also use `ROOT.Double` (removed in ROOT 6.22) or import shared TauFW modules that now use Python 3-only
  syntax, so even a Python 2 release would not run them.
- **They have replacements or are unused.** Each file was checked for code imports and shell-script calls.
  Only files with a working Python 3 counterpart, or with no remaining use, were removed.
  Scripts that are still used and have no replacement were **kept** for migration (see below).
- **They get in the way of the refactor.** Dead code shows up in searches, audits and the I/O inventory (section 4),
  and makes it look like more code depends on the shared modules than actually does. Nothing is lost: all
  files remain in the Git history.

### Still to do

- **Python 2 scripts kept for migration to Python 3:**
  `Fitter/ETauFR/writedatacard.py` (active, high priority), `Fitter/Zpt/utils.py` and `Fitter/Zpt/config/samples.py`
  (imported by `measureZpt*.py`, high priority), `Fitter/HighPT/createinputs.py`,
  `PicoProducer/utils/{checkEvents,compareNano,comparePico,convertGENSIM,getDASParents}.py`.
  (`Fitter/scripts/{plotBiasTest,plotChannelCompatibility}.py` were unused and moved to `Fitter/Legacy/` in section 8.)
- **References to removed scripts that still need cleaning up:**
  `Fitter/TauID/README.md` (`plotfit*.py`) and the link to `paper/plotpostfit.py` in `Fitter/ETauFR/README.md`.
  (`Fitter/TauES/doTES.sh`, `Fitter/ETauFR/Fitting.sh` and `Fitter/paper/postfit.sh` were moved to `Fitter/Legacy/` in section 8.)

---

## 4. Utilities package for future development

**Date:** 2026-10-12
**Commit:** `65ed36b`
**Details:** [Utilities/README.md](../Utilities/README.md), [Utilities/IOInventory.md](../Utilities/IOInventory.md)

### What changed

- New package `Utilities/` (exposed as `TauFW.Utilities` after `scram b`), with two independent classes:
  - **`CLI`** (`Utilities/python/CLI/`): terminal output with verbosity levels, warnings/errors on stderr,
    headers, aligned tables, a progress bar that behaves correctly when output is redirected, and input prompts/confirmation.
  - **`FileIO`** (`Utilities/python/FIO/`): one interface for local files and explicit remote URLs
    (`root://` via XRootD, `gsiftp://`/`srm://` via GFAL). Text, bytes, lines, JSON, YAML, CSV (with transparent
    `.gz`), templates, directory operations, ROOT file handling with correct ownership (context-managed `TFile`,
    detached histogram clones) and `hadd` merging. Writes refuse to overwrite unless `overwrite=True` is passed;
    external commands use argument lists (no shell) with a timeout.
- [Utilities/IOInventory.md](../Utilities/IOInventory.md), generated by `python Utilities/_audit_io.py`: a static
  scan of 432 source files in common, PicoProducer, Plotter, Fitter and Tau_Trigger_SF that lists every terminal and
  file I/O site and the `CLI`/`FileIO` method it would map to.
- Unit tests in `Tests/Utilities/` (`test_cli.py`, `test_file_io.py`, `test_remote_root.py`), using temporary files
  and mocked remote/ROOT operations, so they run without CMSSW:
  `python -m unittest discover -s Tests/Utilities -v`.
- `.gitignore` exception for `Utilities/python/**/__init__.py` (these files hold the public exports), and the test
  runner now mirrors `Utilities` into its workspaces.

**No existing framework code uses these packages yet.** This commit only adds them.

### Why

- **Terminal and file I/O are duplicated across the framework.** Each package has its own printing, logging,
  loading bars, file helpers and storage-system wrappers (the inventory found I/O in 356 of 432 files).
  Behaviour differs between them, for example in how remote paths are guessed or whether files are overwritten.
  A single, tested implementation makes later changes in one place instead of dozens.
- **Safe defaults.** No silent overwrites, no guessing of user/host/site from paths, no shell string commands,
  explicit timeouts, and ROOT objects that do not dangle after their file is closed. These are common sources of
  bugs in batch workflows.
- **Adding before connecting.** The packages and the inventory come first so that each framework module can be
  migrated in a separate, reviewable step. Because the BBB baselines (section 1) are already locked, every such
  migration can be verified to leave the outputs unchanged.

---

## 5. PicoProducer cleanup, Part 1: command-level BBB tests and bug register

**Date:** 2026-10-12
**Details:** [Tests/README.md](../Tests/README.md#picoproducer-command-cases-black-box),
[docs/PicoProducer/BUGS.md](../PicoProducer/BUGS.md)

This is the first step of a multi-part PicoProducer cleanup. The planned order is:

1. tests and bug register (this part);
2. foundations and `legacy/`;
3. settings, datasets, storage and batch;
4. `jobs/`;
5. workers, CLI and a public `api.py`;
6. analysis and corrections;
7. callers and docs.

Ground rules for the cleanup:
- **Folders and names:** they may change. All in-repo callers are updated, and no compatibility shims are kept.
- **Bugs:** each one is fixed in its own documented commit.
- **Physics output:** it must stay the same. BBB proves this.

### What changed

- **Five new BBB cases** (`pico.config`, `pico.run`, `pico.jobs`, `pico.merge`, `pico.workers`) test PicoProducer
  from the outside. They run `pico.py` and the job workers in fresh child processes with:
  - a fixed configuration;
  - a test sample catalog over Local storage;
  - synthetic NanoAOD;
  - fake `condor_submit`/`condor_q`.

  They snapshot what the commands produce:
  - config JSON and its backup, job configs and task lists;
  - scheduler command lines and status summaries;
  - `run --dry` command lines, merged tuples, worker outputs, and the files left after cleanup.

  Together they cover:
  - config creation, backup recovery, `channel`/`era`/`set`/`rm`;
  - file- and event-based chunking, `-E`/sample/channel option merging, skipping existing job configs;
  - good/corrupt/pending/missing chunk classification, resubmission, the hadd refusal gate, `hadd`/`haddclean`/`clean`;
  - `picojob.py` (`ModuleMuTauSimple`, ranges, `--opt`, copy to storage) and `skimjob.py` (preselection with `Bookkeeper`, ranges).
- **New test files:**
  - `Tests/BBB/pico_harness.py`: the workspace, fixtures, fake scheduler and normalization.
  - `Tests/BBB/pico_entry.py`: the child-process entry.
  - `Tests/support/bootstrap.py`: gains `attach()`, so a child process can reuse a prepared mirror without copying it.
- **`docs/PicoProducer/BUGS.md`** lists 60+ defects with location, severity, BBB coverage and the part in which
  each will be fixed. Examples:
  - Run 2 `ModuleMuTau`/`ETau`/`TauTau`/`EMu` crash at `getlepvetoes` (missing `era`);
  - `SGE`/`T2_PSI`/`T3_PSI` cannot be constructed;
  - channel options override user `-E` options;
  - `haddclean` cleanup is not gated on a validated merge.

### Why

- **The old baselines did not cover the refactor.** The existing PicoProducer BBB cases cover only
  `TreeProducer`, `Bookkeeper` and `ScaleFactorTool`. The cleanup rewrites configuration, job planning, status and
  merging, and none of that was protected.
- **Testing through the commands keeps the baselines valid.** The cases call the commands, not internal
  functions. Package-internal script paths are normalized to their file names, so baselines stay valid while
  modules move. A changed command line, job config, option order or output still fails.
- **Some baselines record buggy behavior on purpose.** Each such case is marked in BUGS.md. When a bug is fixed,
  the baseline change is explicit and reviewable.

### Still to do

- Lock the new baselines on lxplus: `python3 Tests/run.py bbb lock --replace`. In the Git diff, check that the 13
  existing baseline files are unchanged.
- Before part 6, add a `ModuleTauPair`-based channel case. It needs a larger synthetic NanoAOD and the
  jsonpog/TauIDSFs payloads.

---

## 6. PicoProducer cleanup, Part 2: legacy area, explicit imports, no import-time side effects

**Date:** 2026-10-12
**Details:** [PicoProducer/python/legacy/README.md](../PicoProducer/python/legacy/README.md),
[docs/PicoProducer/BUGS.md](../PicoProducer/BUGS.md)

**None of these changes alters behavior.** Every changed file was checked statically: it parses as Python 3.9,
and `pyflakes` shows that no name lost its definition.

### What changed

1. **`legacy/` area.** 23 unmaintained or forked files moved to `PicoProducer/python/legacy/` (with `git mv`,
   so their history follows them). The README lists each file's origin, last change and reason. The files:
   - the `MuTauFakeRate` and `puppiMET` forks of `ModuleTauPair`;
   - the `JetTauFakeRate` producers;
   - `ModuleMuTau_nanoV10_DeepTau2p1`, `TauES/ModuleMuTau`, `CheckMuTrigger`, `StitchEffs`;
   - the generator studies (`GenFilterMuTau`, `GenMatcher`, `LQ`, `gmin2`);
   - `BeamSpotTool`, `METCorrectionTool`, `PreFireTool`, `MuonSFs_ROOT`, `dumpGen`;
   - the Python 2 launcher `pico2.py`, renamed `pico2.sh` because it is a shell script and `scram b` would try
     to compile it.

   References were updated in the README, the JetToTauFR README, the processors README, `pico.py`'s
   import-error message and `Tests/PicoProducer/testSFs.py` (recorded in `Tests/migration.json`). Legacy files
   are not maintained, not tested and not runnable through `pico.py`. The CMSDAS2020 tutorial module stays
   because `docs/CMSDAS2020` links to it.
2. **Tracked packages.** `analysis/`, `corrections/`, `storage/`, `pico/`, `tools/` and `legacy/` now have
   tracked `__init__.py` files that describe each package. `.gitignore` has an exception for
   `PicoProducer/python/**/__init__.py`, like the one for `Utilities`.
3. **No working-directory change on import.** `pico/common.py` no longer calls `os.chdir`. `scripts/pico.py`
   changes to `PicoProducer/` explicitly at startup, at the same point in the import sequence as before, then
   loads the configuration. The redundant second `chdir` before dispatch was removed.
4. **Explicit imports.** Every `from ... import *` outside `legacy/` was replaced: 22 analysis modules and the
   four `pico` command modules. A small static resolver (pyflakes plus a simulation of each module's namespace)
   found, for each name, which wildcard supplied it at runtime and the module that actually defines it. So the
   new imports bind the same objects as before, including `datadir`: every maintained module still sees the
   base `TauFW.PicoProducer.datadir`. The replacement imports keep the original import order.
5. **Python 2 leftovers removed** (17 files):
   - `past.builtins` replaced by `str`, `unicode` likewise (`past.builtins.basestring` also matched `bytes`;
     none of these values can be bytes);
   - `from __future__ import print_function`;
   - the `raw_input` shim;
   - `"python2" if ... else "python3"` (now `python3`);
   - the no-op `__metaclass__ = type`.

   `BatchSystem`'s `__metaclass__ = ABCMeta` stays until part 3, because making it effective is a behavior
   change (BUGS S03).

### Why

- **Dead code makes cleanup harder.** Legacy code and its wildcard-import chains made searches, audits and
  refactoring decisions harder. Moving it out (not deleting it) makes the maintained surface explicit.
- **Wildcard imports hid where names come from.** A module's dependencies were invisible, and the `datadir`
  rebinding leaked between modules (BUGS A13). Explicit imports make each file readable on its own and allow
  safe moves in later parts.
- **Importing should not change process state** (architecture finding A01). The working directory is now an
  explicit decision of the CLI entry point.

### Bugs

- **No bug was fixed in this part.** A11, C10 and W03 are only moved to `legacy/`.
- **One new bug was found** while resolving names: A14, an undefined `fes` in `ETauFakeRate/ModuleETau.py`.

### Check

Run `python3 Tests/run.py bbb check` on lxplus. All 18 cases must pass unchanged.

---

## 7. PicoProducer cleanup, Part 3: settings, datasets, storage, batch and jobs packages

**Date:** 2026-10-12
**Details:** [docs/PicoProducer/BUGS.md](../PicoProducer/BUGS.md)

### A. Restructuring (no behavior change)

Package layout under `PicoProducer/python/`. Every module has a docstring (purpose, inputs, outputs, public API),
`# ===== ... =====` sections and `__all__`; each package's `__init__.py` exports its public API.

| New module | Old location | Contents |
|---|---|---|
| `settings/defaults.py` | `tools/config.py`, `storage/utils.py`, `batch/utils.py` | `DTYPES`, `user`, `host`, site guesses (`guess_sedir`, `guess_tmpdirs`, `guess_batch`), `getdefaultconfig` |
| `settings/model.py` | `tools/config.py` | `Config` |
| `settings/store.py` | `tools/config.py` | `getconfig`, `setdefaultconfig` |
| `datasets/sample.py` | `storage/Sample.py` | `Sample`, `MC`, `Data`, `Embdedded` |
| `datasets/catalog.py` | `storage/utils.py` | `getsamples`, `print_no_samples` |
| `datasets/das.py` | `storage/das.py` | `dasgoclient`, `getdasfiles`, `getdasnevents`, ... |
| `storage/log.py` | `storage/utils.py` | the shared `'Storage'` logger (`pico.py -v` sets its verbosity) |
| `storage/factory.py` | `storage/utils.py` | `getstorage` |
| `storage/validation.py` | `storage/utils.py` | `getnevents`, `isvalid`, `itervalid`, `iterevts` |
| `storage/base.py`, `eos.py`, `t2_desy.py`, `t2_psi.py`, `t3_psi.py`, `gridka_nrg.py` | `StorageSystem.py`, `EOS.py`, ... | storage adapters (class names unchanged) |
| `batch/base.py` | `batch/BatchSystem.py` | `BatchSystem`, `JobList`, `Job` |
| `batch/htcondor.py`, `batch/slurm.py`, `batch/sge.py` | `HTCondor*.py`, `SLURM*.py`, `SGE.py` | adapters; the 7-line site subclasses now sit next to their base class |
| `batch/factory.py` | `batch/utils.py` | `getbatch`, with an explicit `SYSTEMS` registry instead of importing a module by name |
| `batch/templates/` | `batch/submit_*` | submit templates (`.sub` files now point to `python/batch/templates/submit_HTCondor.sh`) |
| `jobs/chunking.py` | `batch/utils.py` | `evtsplitexp`, `chunkify_by_evts` |
| `jobs/jobconfig.py` | `batch/utils.py` | `getcfgsamples` |
| `TauFW.common.tools.parallel` | `TauFW.Plotter.plot.MultiThread` | `MultiProcessor`, `Thread`. Producer validation no longer imports Plotter (architecture finding A03). Since §15: `TauFW.Utilities.Process.ParallelProcessor` |

Side effects that moved:
- **`sys.path.append(basedir)`** used to run when `tools/config.py` was imported. It is now in
  `datasets.catalog.getsamples`, the only code that needs it, to import `samples.<catalog>`.
- **Config defaults** no longer import the storage and batch modules (and ROOT through them), because the site
  guesses now live in `settings/defaults.py`.

Callers updated: `pico.py`, the `pico/` commands, both workers, Plotter (`sample/utils.py`, `MergedSample`,
`SampleSet`, `plot_compare_nano.py`), `data/pileup/getPileupProfiles.py`, `scripts/`, `utils/`, the tests
(`Tests/migration.json` records the edits), the BBB harness, the 46 sample catalogs in the repository, and the
docs that link to the templates.

### Migration for users

| You have | Change it to |
|---|---|
| A sample catalog with `from TauFW.PicoProducer.storage.Sample import MC as M, Data as D` | `from TauFW.PicoProducer.datasets import MC as M, Data as D`. **The old line still works:** `storage/Sample.py` is kept as a documented re-export, the only compatibility shim of this cleanup, because private catalogs outside the repository use it |
| `import TauFW.PicoProducer.tools.config as GLOB; GLOB.getconfig()` | `from TauFW.PicoProducer.settings import getconfig; getconfig()` |
| `from TauFW.PicoProducer.storage.utils import getstorage / getsamples / isvalid` | `from TauFW.PicoProducer.storage import getstorage, isvalid`; `from TauFW.PicoProducer.datasets import getsamples` |
| `from TauFW.PicoProducer.batch.utils import getbatch` | `from TauFW.PicoProducer.batch import getbatch` |
| `from TauFW.Plotter.plot.MultiThread import MultiProcessor` | `from TauFW.Utilities.Process import ParallelProcessor` (§15; `max=` is now `max_parallel=`) |
| A custom batch system class in `batch/<Name>.py` | Add it to `SYSTEMS` in `batch/factory.py`, and put its template in `batch/templates/` |

`config/config.json` keys and values do not change; `batch` still names the batch system class.

### B. Bug fixes

All defects registered for Part 3 in [BUGS.md](../PicoProducer/BUGS.md) are fixed together in one commit,
after the restructuring in A. Each changed line carries a `# BUGS <ID>` comment, and each BUGS.md row now
gives the fix and its output impact.

**Only one of these fixes changes a BBB baseline: P17.** The case `pico.config` records the default eras of a
fresh installation, so it has to be re-locked. All other fixes are on paths that BBB does not exercise (other
sites, other batch systems, error paths) or do not change any value.

#### Batch systems

| ID | Before | After | Who notices |
|---|---|---|---|
| S01 | `batch/sge.py` was a copy of the HTCondor adapter with the class name `HTCondor`, so selecting `SGE` always failed, and the code would have called `condor_submit`. | A real SGE adapter: `qsub -t 1-N` array jobs (N defaults to the number of lines in the task list, because `pico.py submit` only passes an array size for SLURM), `-N` name, `-q` queue, `-l h_rt` time limit, `-o` log, and `qstat -u $USER` parsing that expands pending task ranges (`1-10:1`). Registered as `SGE` in `batch.factory.SYSTEMS`. | SGE sites. **Not run on an SGE site** (none available); please report problems. |
| S02 | `getbatch({'batch': ...})` raised `NameError` (`arg[batch]`). | `arg['batch']`. | Callers that pass a dict (none in the repository). |
| S03 | `__metaclass__ = ABCMeta` (Python 2 syntax) did nothing, so a subclass missing `submit`/`status`/`jobs` was only discovered when called. | `class BatchSystem(object,metaclass=ABCMeta)`: an incomplete subclass fails when it is created. Every adapter in the repository implements all three. | Authors of new batch adapters. |
| S04 | Regex and replacement strings such as `"(\d+)"` were not raw strings: `SyntaxWarning` since Python 3.12, a `SyntaxError` in a future Python. Same in `skimjob.py` (`'\$'`) and `pico/config.py` (`'/\,...'`). | Raw strings, or an explicitly escaped backslash. The string values are byte-for-byte the same. | Nobody, apart from the missing warnings. |

#### Storage systems

| ID | Before | After | Who notices |
|---|---|---|---|
| S05 | `T2_PSI`/`T3_PSI` could not be created: `os.path('/scratch/', ...)` raised `TypeError` (and `T2_PSI` did not import `os`). | `os.path.join('/scratch/', $USER)`. | PSI users: both adapters work again. |
| S06 | `EOS(..., eos=True)` assigned `"eos rm"` to the *list* command, so listing deleted nothing but failed, and removal used the generic command. | `rmcmd = "eos rm -r"`; listing keeps `eos ls`. | Only explicit `eos=True` users (`pico.py` does not use it). |
| S07 | `hadd` with `$PATH` glob sources and a file URL raised `NameError: isglob` (generic adapter and `T2_DESY`). | `isglob` is imported. | Remote-storage merges with glob sources. |
| S08 | `StorageSystem.cd()` raised `UnboundLocalError` when the storage is not mounted. | Returns `None`, as `os.chdir` does. | Nobody in the repository calls it. |
| S09 | GridKA: `rm` ran `xrdfs ... ls` (nothing was removed); `hadd` joined source paths without spaces, so multi-file merges got one invalid path. | `xrdfs ... rm`; one space after each source. | GridKA/KIT users: cleanup and multi-file merges work. |

#### Datasets

| ID | Before | After | Who notices |
|---|---|---|---|
| S10 | A leftover `dtype = 'mc' # TODO: remove` forced every `Sample(...)` without `dtype` to be MC, discarding the detection just above it. | Detection is restored: `Embed` in the path gives 'embed', a `/Run20xx` path gives 'data', otherwise 'mc' (the previous result). Whenever the detected type is not 'mc', a **warning** names the sample, the type and the path, and suggests `dtype=...` or `MC`/`Data`/`Embedded`. | Catalogs that use plain `Sample(...)` for data or embedded samples: they now get the right type (the JSON certification mask and data/MC-specific processing). **All catalogs in the repository use `MC`/`Data` and are unaffected.** |
| S11 | `loadfiles`: after warning that the stored `nevents` differs from the sum in the file list, `self.nevents == nevents` (a comparison) kept the stored value. | The sum of the per-file counts is used, as the warning implies. | Samples with an explicit `nevents=` that disagrees with their `:NEVTS` file list. |
| S12 | The `loadfiles` docstring came after a statement. | Docstring first. | Nobody (documentation tools only). |
| S13 | Class name typo `Embdedded`. | `Embedded`. The old name survives only in the compatibility re-export `storage/Sample.py` (`Embdedded = Embedded`), so old catalogs keep working. | Nobody. |
| S14 | `getsamples(..., moddict={})`: a mutable default shared between all calls acted as a hidden cache. | `moddict=None` creates a fresh dictionary; `pico.py run/submit` pass their own, as before. Python's module cache still avoids importing a catalog twice. | Nobody. |
| S15 | Producer validation imported Plotter's `MultiProcessor`. | Fixed in A (`TauFW.common.tools.parallel`; since §15 `TauFW.Utilities.Process.ParallelProcessor`). | Nobody. |
| S16 | `HTCondor_NAF` can never be guessed from the host name. | **Won't fix.** The commented-out branch tested `'etp'`, which the KIT branch already matches, so it could never have worked. NAF users set it explicitly: `pico.py set batch HTCondor_NAF`. | Nobody. |

#### Configuration

| ID | Before | After | Who notices |
|---|---|---|---|
| P16 | `Config.__setattr__` looked up `key in self._dict[key]`, so setting a private attribute such as `CONFIG._path` raised `KeyError`. | `key in self._dict`. | Nobody in the repository. |
| P17 | A fresh installation's default eras pointed to `samples_2016.py`, `samples_2017.py` and `samples_2018.py`, which do not exist. `config/config_example.json` pointed to the missing `samples_UL2016.py` and `tutorial/samples_2022_postEE.py`. | Defaults are the top-level catalogs that exist: `UL2016_preVFP`, `UL2016_postVFP`, `UL2017`, `UL2018`, `2022_preEE`, `2022_postEE`, `2023C`, `2023D`, `2024`, `2025`. The example config is corrected. | Fresh installations only; an existing `config/config.json` keeps its own eras. **BBB `pico.config` changes (`fresh.values.eras`).** Origin (catalogs deleted in `c663833`, 2024), symptom and the exact baseline difference: [BUGS.md details](../PicoProducer/BUGS.md#p17-default-eras-pointed-to-deleted-catalogs). |
| P18 | Every `getconfig()` call could create or rewrite `config/config.json`: from `pico.py`, but also from a batch worker (`picojob.py -c`), from Plotter resolving `$PICODIR`, or from a script. | `getconfig(write=False)` by default: missing keys are repaired in memory, and a missing file gives a warning plus the defaults. Only the CLI (`pico/common.py`) passes `write=True`, so `pico.py` creates and repairs the file exactly as before. | Workers, Plotter and scripts no longer write files in `PicoProducer/config/`. |

#### File-name case correction for A

The commit of A recorded eight renamed modules under their old capitalized names: `batch/HTCondor.py`,
`SGE.py`, `SLURM.py`, `storage/EOS.py`, `GridKA_NRG.py`, `T2_DESY.py`, `T2_PSI.py` and `T3_PSI.py`. The code
imports `batch.htcondor`, `storage.eos` and so on. Windows file systems ignore case (`core.ignorecase=true`), so
this was invisible on Windows, but a Linux checkout of A cannot import these modules (`bbb check` on lxplus:
`ModuleNotFoundError: No module named 'TauFW.PicoProducer.batch.htcondor'` in `pico.jobs` and `pico.merge`).

A first rename staged on Windows was lost again when B was committed (`d8046af`), because Windows Git treats both
spellings as the same file. The rename was therefore done on lxplus, where file names are case-sensitive, in
commit `ae0d9bf` ("Fix file-name case of 8 PicoProducer modules"). It renames the files to `htcondor.py`,
`sge.py`, `slurm.py`, `eos.py`, `gridka_nrg.py`, `t2_desy.py`, `t2_psi.py` and `t3_psi.py`. A scan of all
tracked paths finds no other case mismatch.

**Rule from now on:** do case-only renames on Linux (`git mv`), or check them on Windows with `git ls-files`
before committing.

**Result:** after `ae0d9bf`, `bbb check` on lxplus showed only the intended P17 difference
(`pico.config`, `fresh.values.eras`); the other 17 cases passed. The baseline was re-locked in `c2d8296`
(only `pico.config.json` and `manifest.json` changed).

---

## 8. Fitter cleanup: legacy area

**Date:** 2026-10-13
**Details:** [Fitter/Legacy/README.md](../Fitter/Legacy/README.md)

### What changed

- 32 broken, superseded or unused files were moved with `git mv` to `Fitter/Legacy/`, keeping their path relative
  to `Fitter/` (e.g. `TauES/doTES.sh` → `Legacy/TauES/doTES.sh`). Nothing was deleted.
  - Fitter root: `createJSON_TES.py`, `run_createroot_TES.py`, `run_workflow.sh`.
  - `TauES/`: `doTES.sh`, `harvestDatacards_TES.py`, `run_createinputsTES.py`, `config/defaultFitSetupTES_mutau_v10_2p5.yml`,
    `correctionlib/{tau_createJSONsTauES,tau_tes}.py`.
  - `TauES_ID/`: `saveSFs_root_JSON.py`, `printParamWorkspace.py`, `WriteSFsFit.py`, `shape_syt.py`,
    `run_makecombinedfitTES_SF.py`, `plot2DParabola_FitDiagnostics.py`,
    `config/Default_FitSetupTES_mutau_DM_{pt,mt40_JetM_muVT}.yml`.
  - `scripts/`: `plotBiasTest.py`, `plotChannelCompatibility.py`, `pulls.py`, `project_bins.py`.
  - `ETauFR/`: `Fitting.sh`, `runAll.sh`, `doImpacts.sh`, `doImpacts2.sh`, `doFitPlots.sh`, `text2wp.sh`,
    `Plotter/{PlotShapes.C,FastPlot.sh}`.
  - `HighPT/combine_logger.out`, `TauID/takeZmu.py`, `paper/postfit.sh`.
- `Fitter/python/models/TagAndProbeModel.py` → `Fitter/python/legacy/models/TagAndProbeModel.py`
  (still importable as `TauFW.Fitter.legacy.models.TagAndProbeModel`).
- READMEs updated: new `Fitter/Legacy/README.md` (reason and replacement for each file); `Fitter/README.md` (workflow
  index, legacy link); `Fitter/TauES/README.md` (the TES-only fit is now legacy; points to the combined TES+ID fit);
  `Fitter/ETauFR/README.md` (old flow and deprecated plotters moved).
- Two stale usage comments fixed: `Fitter/createroot_TES.py` (referred to `createJSON_TES.py`) and
  `Fitter/run_workflow_zmm.sh` (referred to `run_workflow.sh`).
- `Utilities/IOInventory.md` regenerated. The diff also contains path changes from sections 6 and 7, which had not
  been regenerated yet.

### Why

- **Scope.** The active Fitter pipeline is `run_inputs*.sh` → `run_workflow_zmm*.sh` (TauES + TauES_ID, the root
  scripts and `python/plot`). The other measurements (ETauFR, HighPT, MuTauFR, TauID, Zpt, paper, tutorial) stay in
  place; only the dead files inside them moved.
- **Criteria.** A file moved only if it was broken (SyntaxError, missing import, or calling a removed script),
  superseded by a script the active pipeline uses, junk output, or referenced only by other legacy files.
  Documented entry points stay, even if no script calls them (e.g. `TauES_ID/makefit_PODAS23.py` for
  `docs/CMSPODAS23`, and `TauES/correctionlib/utils.py`, which `tau_tid_2024.py` → `make_tid_2025.py` uses).
- **Same reason as section 3.** Dead code shows up in searches and in the I/O inventory, and makes the live
  workflow harder to see.

### Check

- `git grep -w` for each moved file: no live script, shell driver, config or Python import refers to an old path.
- All remaining `Fitter/**/*.py` parse in Python 3, except the known Python 2 files listed in section 3.
  All remaining `Fitter/**/*.sh` pass `bash -n`.
- The BBB Fitter cases (`fitter.shapes`, `fitter.rebin`) import only `TauFW.Fitter.plot.{datacard,rebinning}`,
  which did not move.

---

## 9. Plotter cleanup: legacy area

**Date:** 2026-10-13
**Details:** [Plotter/Legacy/README.md](../Plotter/Legacy/README.md)

### What changed

- 39 unused, outdated or one-off files were moved with `git mv` into two legacy areas. Nothing was deleted.
  - **`Plotter/Legacy/`** for scripts and configs, keeping their path relative to `Plotter/`
    (e.g. `config/samples_v10.py` → `Legacy/config/samples_v10.py`):
    - top-level scripts: `plot2D.py`, `plot_compare.py`, `plot_compare_nano.py`, `plot_differential.py`,
      `plot_stitching.py`, `plot_GENSIM.py`, `plot_CMSPODAS23.py`, `plots_and_histograms_CMSDAS2020.py`,
      `fromTCanvasToHist.py`, `plot_mvis_uncorr_corr.py`;
    - `utils/plot_decayLengths.py`, `utils/tmux.sh` (`utils/` no longer exists);
    - `config/`: `samples_Summer24.py`, `samples_Summer24v15.py`, `samples_v10.py`, `setup_mutau_PODAS.yml`,
      `setup_mutau_v10_2p5.yml`.
  - **`Plotter/python/legacy/`** for modules and ROOT macros from `Plotter/python/`, keeping their path relative to
    `python/` (e.g. `methods/JetToTau_MisID.py` → `legacy/methods/JetToTau_MisID.py`):
    - `corrections/`: the whole `JetToTauFR/` tree (Python 2) and `g-2/`, plus `lepEff.C`, `leptonTauFake.C`,
      `zptweight.C`;
    - `macros/mapGenMatch.C`; `methods/`: `JetToTau_MisID.py`, `ScaleVariations.py`, `QCD.C`.
- The `python/legacy/` modules stay importable as `TauFW.Plotter.legacy.*`, like `TauFW.PicoProducer.legacy` and
  `TauFW.Fitter.legacy`. Their imports of each other were changed from `TauFW.Plotter.corrections.JetToTauFR...` to
  `TauFW.Plotter.legacy.corrections.JetToTauFR...`. `SampleSet` only finds `method=` names in
  `TauFW.Plotter.methods`, so `JetToTauFR/plot_forTauFR.py` now imports `TauFW.Plotter.legacy.methods.JetToTau_MisID`
  explicitly before using `method='JetToTau_MisID'`. None of these modules was imported by maintained code.
- References updated: the CMSDAS2020 and CMSPODAS23 school pages in `docs/` now link to the `Legacy/` copies
  (command examples become `./Legacy/plots_and_histograms_CMSDAS2020.py`); two relative links in the moved
  JetToTauFR README; a link to `Legacy/` in `Plotter/README.md`. New `Plotter/Legacy/README.md` lists the reason for
  each file (both areas); `Plotter/python/legacy/README.md` points to it.
- `Utilities/IOInventory.md` regenerated (only the Plotter paths changed).

### Why

- **Scope.** The maintained Plotter is the `python/plot` and `python/sample` library, `plot.py` with
  `config/samples_v15.py`, the active `setup_*.yml` channel configs, the tutorial, and the macros and methods that
  scripts, Fitter or the tests use. Everything else was Run 2 / DeepTau2017 scripts, school material, one-off
  studies, orphan sample catalogs and unreferenced ROOT macros.
- **Criteria.** A file moved only if no maintained script, Fitter or PicoProducer code, test, BBB case or shell
  driver uses it (checked for imports, `loadmacro`/`.L` paths, `method=` names and `-c` config defaults).
  Old-looking files that are still used stayed: `config/samples.py`, `samples_HighPT.py`, `samples_v12.py` with
  `plot_v10.py` and `plot_postfit*.py`, the macros loaded by `Tests/Plotter/testMacros.py`, `Unroll.cxx` and
  `setup_tautau.yml`.
- **Same reason as sections 3, 6 and 8.** Dead code shows up in searches and in the I/O inventory, and makes the
  live framework harder to see.

### Check

- `git grep` for each moved file: the only remaining mentions are history in this change log and commented-out code.
- The kept entry points (`plot.py`, `plot_v10.py`, `plot_postfit*.py`, `tutorial/plot.py`) and the Fitter
  `createinputs*.py` scripts import only configs, macros and methods that did not move.
- The test mirror copies only `Plotter/python/`, and no test or BBB case uses a moved file.
  `python Tests/check_harness.py` passes. Run `python3 Tests/run.py bbb check` and `python3 Tests/run.py normal` on
  lxplus: the results must be unchanged.

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
- `Fitter/Zpt/validateZpt.py` and the legacy script `LegacyAnalyses/YearIndependent/plot_GENSIM.py`: `float_range`.
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

### To do on lxplus

`bbb check` refuses to run while the case list differs from the lock, and `lock` captures the whole suite. So:
`python3 Tests/run.py bbb lock --replace`, then `python3 Tests/run.py bbb diff`, which must show only the new
`drawing.canvas` baseline and no change to any other case. Commit the new baseline before the move.
