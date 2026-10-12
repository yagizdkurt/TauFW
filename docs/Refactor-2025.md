# Refactor-2025: change log

**Author:** Yagizhan Dinckurt ([@yagizdkurt](https://github.com/yagizdkurt))
**Branch:** `Refactor-2025`
**Last updated:** 2026-10-13

This document records the changes made on the `Refactor-2025` branch: what changed and why.
Sections are in the order the work was done. Each lists the relevant commits.

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
  `-q` gives a compact one-line-per-case view with logs kept under `Tests/.artifacts/logs/`.
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
**Details:** [docs/FastSetup.md](FastSetup.md)

### What changed

- New [FastSetup.sh](../FastSetup.sh) at the repository root. From a fresh clone:

  ```bash
  git clone https://github.com/cms-tau-pog/TauFW TauFW
  cd TauFW
  bash FastSetup.sh
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
[PicoProducer/docs/BUGS.md](../PicoProducer/docs/BUGS.md)

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
- **`PicoProducer/docs/BUGS.md`** lists 60+ defects with location, severity, BBB coverage and the part in which
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
[PicoProducer/docs/BUGS.md](../PicoProducer/docs/BUGS.md)

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
**Details:** [PicoProducer/docs/BUGS.md](../PicoProducer/docs/BUGS.md)

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
| `TauFW.common.tools.parallel` | `TauFW.Plotter.plot.MultiThread` | `MultiProcessor`, `Thread`. Producer validation no longer imports Plotter (architecture finding A03) |

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
| `from TauFW.Plotter.plot.MultiThread import MultiProcessor` | `from TauFW.common.tools.parallel import MultiProcessor` |
| A custom batch system class in `batch/<Name>.py` | Add it to `SYSTEMS` in `batch/factory.py`, and put its template in `batch/templates/` |

`config/config.json` keys and values do not change; `batch` still names the batch system class.

### B. Bug fixes

All defects registered for Part 3 in [BUGS.md](../PicoProducer/docs/BUGS.md) are fixed together in one commit,
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
| S15 | Producer validation imported Plotter's `MultiProcessor`. | Fixed in A (`TauFW.common.tools.parallel`). | Nobody. |
| S16 | `HTCondor_NAF` can never be guessed from the host name. | **Won't fix.** The commented-out branch tested `'etp'`, which the KIT branch already matches, so it could never have worked. NAF users set it explicitly: `pico.py set batch HTCondor_NAF`. | Nobody. |

#### Configuration

| ID | Before | After | Who notices |
|---|---|---|---|
| P16 | `Config.__setattr__` looked up `key in self._dict[key]`, so setting a private attribute such as `CONFIG._path` raised `KeyError`. | `key in self._dict`. | Nobody in the repository. |
| P17 | A fresh installation's default eras pointed to `samples_2016.py`, `samples_2017.py` and `samples_2018.py`, which do not exist. `config/config_example.json` pointed to the missing `samples_UL2016.py` and `tutorial/samples_2022_postEE.py`. | Defaults are the top-level catalogs that exist: `UL2016_preVFP`, `UL2016_postVFP`, `UL2017`, `UL2018`, `2022_preEE`, `2022_postEE`, `2023C`, `2023D`, `2024`, `2025`. The example config is corrected. | Fresh installations only; an existing `config/config.json` keeps its own eras. **BBB `pico.config` changes (`fresh.values.eras`).** Origin (catalogs deleted in `c663833`, 2024), symptom and the exact baseline difference: [BUGS.md details](../PicoProducer/docs/BUGS.md#p17-default-eras-pointed-to-deleted-catalogs). |
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
