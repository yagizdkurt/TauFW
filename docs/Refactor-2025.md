# Refactor-2025: change log

**Author:** Yagizhan Dinckurt ([@yagizdkurt](https://github.com/yagizdkurt))
**Branch:** `Refactor-2025`
**Last updated:** 2026-10-12

This document records the changes made on the `Refactor-2025` branch: what changed and why.
Sections are in the order the work was done. Each lists the relevant commits.

| # | Change | Date |
| --- | --- | --- |
| 1 | [Test migration and BBB regression tests](#1-test-migration-and-bbb-regression-tests) | 2026-10-12 |
| 2 | [FastSetup script](#2-fastsetup-script) | 2026-10-12 |
| 3 | [Removal of legacy Python 2 scripts](#3-removal-of-legacy-python-2-scripts) | 2026-10-12 |
| 4 | [Utilities package for future development](#4-utilities-package-for-future-development) | 2026-10-12 |
| 5 | [PicoProducer cleanup, session 1: command-level BBB tests and bug register](#5-picoproducer-cleanup-session-1-command-level-bbb-tests-and-bug-register) | 2026-10-12 |
| 6 | [PicoProducer cleanup, session 2: legacy area, explicit imports, no import-time side effects](#6-picoproducer-cleanup-session-2-legacy-area-explicit-imports-no-import-time-side-effects) | 2026-10-12 |

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
  `PicoProducer/utils/{checkEvents,compareNano,comparePico,convertGENSIM,getDASParents}.py`,
  `Fitter/scripts/{plotBiasTest,plotChannelCompatibility}.py`.
- **References to removed scripts that still need cleaning up:**
  `Fitter/TauES/doTES.sh` (legacy TES-only workflow), `Fitter/ETauFR/Fitting.sh` (calls `compare.py`; use
  `diffNuisances.py`), `Fitter/TauID/README.md` (`plotfit*.py`), `Fitter/paper/postfit.sh` (`writecards.py`),
  and the link to `paper/plotpostfit.py` in `Fitter/ETauFR/README.md`.

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

## 5. PicoProducer cleanup, session 1: command-level BBB tests and bug register

**Date:** 2026-10-12
**Details:** [Tests/README.md](../Tests/README.md#picoproducer-command-cases-black-box),
[PicoProducer/docs/BUGS.md](../PicoProducer/docs/BUGS.md)

This is the first step of a multi-session PicoProducer cleanup. The planned order is:

1. tests and bug register (this session);
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
- **`PicoProducer/docs/BUGS.md`** lists 60+ defects with location, severity, BBB coverage and the session in which
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
- Before session 6, add a `ModuleTauPair`-based channel case. It needs a larger synthetic NanoAOD and the
  jsonpog/TauIDSFs payloads.

---

## 6. PicoProducer cleanup, session 2: legacy area, explicit imports, no import-time side effects

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

   `BatchSystem`'s `__metaclass__ = ABCMeta` stays until session 3, because making it effective is a behavior
   change (BUGS S03).

### Why

- **Dead code makes cleanup harder.** Legacy code and its wildcard-import chains made searches, audits and
  refactoring decisions harder. Moving it out (not deleting it) makes the maintained surface explicit.
- **Wildcard imports hid where names come from.** A module's dependencies were invisible, and the `datadir`
  rebinding leaked between modules (BUGS A13). Explicit imports make each file readable on its own and allow
  safe moves in later sessions.
- **Importing should not change process state** (architecture finding A01). The working directory is now an
  explicit decision of the CLI entry point.

### Bugs

- **No bug was fixed in this session.** A11, C10 and W03 are only moved to `legacy/`.
- **One new bug was found** while resolving names: A14, an undefined `fes` in `ETauFakeRate/ModuleETau.py`.

### Check

Run `python3 Tests/run.py bbb check` on lxplus. All 18 cases must pass unchanged.

