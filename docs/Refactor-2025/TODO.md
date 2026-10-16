# Refactor-2025: still to do

# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
**Last updated:** 2026-10-14

Everything the `Refactor-2025` branch has left open: checks that need lxplus, the rest of the `common` → `Utilities`
move, old output kept on purpose, open bugs, and planned next steps. The [change log](Refactor-2025.md) ("CL §N")
records what was done; this file records what was not. Tick an item when it is done and note the commit or changelog
section, or delete it.

Items marked **(verify)** may already be done; check before working on them.

## 1. Checks to run on lxplus


- [ ] **Confirm import-boundary reporting on lxplus:** `python3 Tests/run.py checks --case check_import_boundaries`.
      Nonzero status is expected while coupling remains; compare the debt report, do not rebaseline or fix production
      code to make this validation pass. Detector-only command: `python3 Tests/check_import_boundaries.py DetectorTests -q`. (CL §13)
- [ ] **Fitter scripts after the import change:** with `cmsenv`, `python3 -c "import TauFW.Fitter.plot.rebinning,
      TauFW.Fitter.plot.postfit_TES"` and `python3 plotParabola_POI_region.py -h` (in `Fitter/TauES_ID/`) must import
      without error. (CL §14)
- [ ] **BBB check after the expression helpers move:** `python3 Tests/run.py bbb check`, the `plotter.*` cases must
      pass unchanged (no re-lock); `python3 -c "import TauFW.Fitter.plot.datacard"` with `cmsenv`. (CL §12)
- [x] Lock the new `drawing.canvas` case before the drawing code moves (locked 2026-10-14: 19 same, 1 added). (CL §12)
- [ ] **BBB check after the drawing move.** `python3 Tests/run.py bbb check`: every case, `drawing.canvas` included,
      must pass with no difference; no re-lock. Then `python3 Tests/run.py normal` (the `Tests/Plotter` scripts import
      the new paths) and, by eye, one `Plotter/plot.py` run and one Fitter postfit plot. (CL §12)
- [ ] **BBB check after §12.** `python3 Tests/run.py bbb check`; nothing should change (ParallelProcessor/loading
      bar, `Utilities.Math`, `CLI.table`). No re-lock. The `3d09ea6` lock may already include §12 **(verify)**.
      (CL §12)
- [ ] **ParallelProcessor parallel tests** in `Tests/Utilities/test_process.py` (start order, queue, `kwret` through the
      pipe): they need the `fork` start method, so they only run on Linux. (CL §12)
- [ ] **PicoProducer with `ncores>=2`**: one run through `iterevts`/`itervalid` (fork with nested functions).
- [ ] **Framework, TES/ID bundle:** `taufw.py plan Analyses/tes_id_2025`, then a VTight/Tight `taufw.py start` run
      compared with `run_inputs.sh` + `run_workflow_zmm.sh` in a clean copy (`FitparameterValues__mutau_*`,
      `tau_sf/*VSjetVTight_VSeleTight*`). (CL §10 "Tests", §11)
- [ ] **Confirm F07:** the rebinned control plots appear in `plots/rebinning/`. ([Fitter BUGS](../Fitter/BUGS.md) F07)
- [ ] **Runner validation:** `bbb check`, `bbb check -v`, `bbb lock --replace`, then `git diff --exit-code`
      on `Tests/BBB/baselines/` **(verify)**. (quiet-runner changelog section removed)
- [ ] `python3 Tests/run.py normal` after the Plotter legacy move **(verify)**. (Plotter legacy cleanup; changelog section removed)
- [ ] **Manual smoke runs:** `pico.py run -c mutau -y 2022_postEE -m 100`, `pico.py submit ... --dry`,
      `taufw.py plan` on `Analyses/example_mutau`, and one small real `taufw.py start` + `advance` until DONE on
      HTCondor. Check by eye that the status loading bar with 15+ outputs looks unchanged **(verify)**.
- [ ] SGE adapter (S01) has never run on an SGE site; nice to have. ([PicoProducer BUGS](../PicoProducer/BUGS.md) S01)

## 2. Moving `common/python/tools/` into `TauFW.Utilities`

Done: `parallel`, `LoadingBar` (§12), `math` (§12), `Table` (§12). Rules for the rest:

- re-implement in Utilities style (no file move), same logic, update every caller, delete the old module, no shims;
- terminal output byte for byte the same; old quirks go in a `LEGACY, CLEAN UP LATER` (or
  `BACKWARD COMPATIBILITY, CLEANUP`) section;
- record golden output from the old code before deleting it, and run the BBB `common.*` cases locally;
- deleting a `Tests/` script also means updating `Tests/inventory.json`, `Tests/migration.json` (+ the count in
  `check_harness.py`), `Tests/LEGACY_BROKEN_CASES.md` and `Tests/README.md`; editing a moved test needs an
  `edited` note in `migration.json`;
- `Utilities/IOInventory.md` has hand edits (author line, `Legacy/OldAnalysis/` rows, which the generator misses while
  `Legacy/OldAnalysis/` is untracked): patch it by hand, or move those edits into `_audit_io.py` first.

| Module | Importers (approx.) | Obstacles |
|---|---|---|
| `string.py` | ~15 direct | `utils.py` star-imports it, and `Plotter/python/sample/utils.py` and `PicoProducer/python/analysis/utils.py` re-export it again (the drawing library has its own copies of `quotestrs` and `repkey` in `Utilities/python/Drawing/_internal/`): `repkey` is used in ~48 files, `getyear` in ~21. Trace every star-import chain. Best done together with `utils.py`. |
| `utils.py` | ~23 | `execute` (`shell=True`, architecture finding A05) should map onto `Utilities.Process.ProcessRunner`; used by `batch/base.py`, `datasets/das.py`, `jobs/merge.py`, `storage/base.py`. Untangle from `string.py` first. |
| `file.py` | ~32 | `ensuredir` is in ~76 files. Maps onto `FileIO`. Imports `log` and `utils`; `past.builtins`; `ensuremodule` is the channel loader's dynamic import. |
| `root.py` | ~21 | ROOT (`ensureTFile` in ~29 files, `gethist`, `loadmacro`); maps onto `FileIO` ROOT methods. `rootname()` has no callers. |
| `log.py` | ~41 | The core of what is left; do it last. `past.builtins.long`. |
| `RDataFrame.py` | 2 (Plotter) | Plotter/ROOT only: belongs in Plotter, not Utilities. Import-time side effects (`gInterpreter.Declare`, `RDF` patches, thread settings; A01/A09). |

## 3. Old output kept on purpose (clean up later)

Each changes logs, so do each in its own commit, with a BBB re-lock where a baseline records it
(`common.formatting` records the table and the loading bar).

**`CLI.table`** — `Utilities/python/CLI/_internal/table.py`, section `LEGACY, CLEAN UP LATER` (CL §12):

- [ ] The header is always underlined with raw ANSI codes, even when stdout is a file; use the CLI's
      terminal/color detection.
- [ ] Four constructor forms told apart by argument types (`(row_format)`, `(header_format, row_format)`, `(ncols)`,
      `(ncols, colwidth)`); only the two format forms are used. Replace with explicit keyword arguments.
- [ ] The two warnings (wrong number of header titles, unrecognized arguments) print the old `LOG.warning` bytes on
      stdout with a fixed `">>> "`; use `CLI.print_warning` (stderr).
- [ ] The two `>>> headerformat=...` debug lines at verbosity ≥ `minimum_verbosity + 3`.
- [ ] `Utilities/python/Drawing/hist_tools.py:435` (was `Plotter/python/plot/utils.py:422`): the `TGraph`/`TGraph` ratio table prints its data rows with `print_header`
      (all columns as `%s`); it should be `print_row`. Kept as it was (`printheader`).
- [ ] Too few header titles raise `TypeError` from `%` after the warning.
- [ ] Consider merging `CLI.table` with `CLI.print_table` once the old output may change.

**Loading bar** — `Utilities/python/CLI/_internal/loading_bar.py`, `BACKWARD COMPATIBILITY, CLEANUP` (CL §12):

- [ ] Replace the `\b` backspace redraws (e.g. `CLI.update_progress` with `\r`).

**ParallelProcessor** — `Utilities/python/Process/_parallel.py`, `BACKWARD COMPATIBILITY, CLEANUP` (CL §12):

- [ ] Verbose messages still name the old classes (`MultiProcessor.start`, `ReturnProcess.join`, ...), and `close()`
      always prints; route through a CLI instance.
- [ ] Nested target functions need the `fork` start method; Python 3.14 changes the Linux default. Nice to have.

**Drawing library** — `Utilities/python/Drawing/`, moved as it was from the Plotter (CL §12). Each item changes the
`drawing.canvas` baseline unless noted; re-lock after each:

- [ ] Restyle to the Utilities style (4-space indent, banners, layout rule) and split `Plot.py` (1376 lines); no
      output change, so `bbb check` must still pass.
- [ ] Import side effects: ROOT batch mode, `TNamed.__repr__` and the `TGraph.SetOption/GetOption` patch (`hist_tools.py`), the TDR style
      applied when `Plot` is imported. Make them explicit calls.
- [ ] `CMSStyle` holds the lumi/era/energy tables per era (analysis data in a style module); move them to
      configuration (a recipe or a data file).
- [ ] `SampleStyle` holds the process color/title tables of the TauFW analyses; make them data passed in by the
      caller (an analysis bundle), with `grouphists` taking the colors explicitly.
- [ ] `_internal/legacy_log.py` (old `Logger`) and `_internal/legacy_helpers.py` duplicate `TauFW.common`; replace the
      logger with `CLI` once output may change (or merge when `common/tools/log.py` moves).
- [ ] Unused helpers: `sumhists` (bug L03), `ensurepoisson`, `getbinedges`, `havesamebins`, `reducehist2d`.
- [ ] `Plotter/python/plot/string.py` re-exports the label helpers of `labels.py` for its star-importers
      (`Variable.py`, `Sample.py`, `Selection.py`); import them explicitly there.
- [ ] `PicoProducer/utils/compare{Nano,Pico}.py` (Python 2) still import the Plotter's `Variable`; give them a plain
      string axis or move them to `Legacy/OldAnalysis/`. Not on any production path.

**Quirks frozen in BBB baselines** (PicoProducer plan):

- [ ] Stitch log in `Plotter/python/sample/utils.py` (~lines 403, 451) is missing its `f` prefix.
- [ ] `workers/picojob.py:74` cuts the `-i` list to `nfiles` (the range case reads only `nano_A`).

## 4. Open bugs

**PicoProducer** ([BUGS.md](../PicoProducer/BUGS.md)), planned for Part 6 (§5 below), none fixed yet:

- [ ] Analysis modules: A01, A02, A03, A04, A05, A06, A07, A08 (cosmetic), A09, A10, A12 (latent), A14.
- [ ] Corrections: C01, C02 (cosmetic), C03, C04, C05, C06, C07, C08, C09 (latent), C11 (layering), C12, C13 (latent).
- [ ] **Blocking for Part 6:** a `pico.channel_tau_pair` BBB case based on `ModuleTauPair` (larger synthetic NanoAOD
      plus jsonpog/TauIDSFs payloads). Every A/C fix must be checked against it.
- Legacy-only entries A11, A13, C10, W03 and the archived A01 copies moved to
  [Legacy/Bugs.md](../../Legacy/Bugs.md#picoproducer). Won't fix in maintained code: P15, S16, W01.

**Fitter** ([BUGS.md](../Fitter/BUGS.md)), registered only, options 4–6 of the workflow:

- [ ] F08: `merge_datacards_regions` called with 7 arguments, takes 6 (crash).
- [ ] F09: `hasattr` on a dict is always false, so the Zmm card is never added (latent).
- [ ] F10: the combined card is written to `output_{era}/` (wrong).

**Plotter** ([BUGS.md](../Plotter/BUGS.md)):

- [ ] L02: `fname=` vs `file=` (`config/samples_v15.py:285` vs `python/sample/utils.py:29`); needs a test with tuples.
- [ ] L03: `sumhists` adds to an undefined `sighist` (now `Utilities/python/Drawing/hist_tools.py`); the fix changes
      the `drawing.canvas` baseline (`$.tools.sumhists`), so re-lock.
- [ ] L04: `estimatelen` with several arguments raises `TypeError` (now `Utilities/python/Drawing/labels.py`).
- [ ] L12: `getmcsample` ignores its `pico=` keyword (`python/sample/utils.py:119-120`; no callers, latent).

**Framework** ([BUGS.md](../Framework/BUGS.md)), registered only:

- [ ] K01: a moved or copied run reads the artifacts of its `DONE` stages at the old location (latent).
- [ ] K02: a crash between `manifest.json` and `run.json` leaves the stage `NEW` with a non-empty output directory
      (latent).
- [x] K03: the `tuples` input slot selects no data; the scripts read `$PICODIR` (design limit). Fixed by CL §18 step 6.
- [ ] K04: production's tuple artifacts have no `kind`, so a filter by `kind='tuples'` finds none (latent).
- [ ] K05: on Windows (Python 3.13) `/afs/...` is not absolute for `os.path.isabs`; an lxplus `pico.config` is joined to the bundle directory (latent, Windows only).

**Jobs/workers audit follow-ups** ([JobsWorkersAudit.md](JobsWorkersAudit.md) §7; none needed for correctness):

- [ ] Add D1–D4 to the "Output impact" column of P09, P06, P22, P19 in PicoProducer BUGS.md.
- [ ] D1: should resubmit warn when the channel options differ from the job config?
- [ ] D4: clearer message for `haddclean -f` / `hadd -r -f`.
- [ ] D5: old log tag `storage.utils.getstorage` in `PicoProducer/python/storage/factory.py:51`.
- [ ] `getsamples` (`datasets/catalog.py:28`) should take the configuration as an argument, so
      `PicoProducer.from_config` uses its own `eras`.

## 5. PicoProducer: Parts 6 and 7

Parts 1–5 are done (CL §5–§8; the Part 2 changelog section was removed).

- [ ] **Part 6, `analysis/` and `corrections/`** (blocked by the tau-pair BBB case): split `analysis/utils.py` into
      `helpers/`; channels and writers into folders; one path per tool (the archived A13 leak is tracked in
      [Legacy/Bugs.md](../../Legacy/Bugs.md#picoproducer)); the maintained A and C bugs; move `hasbit` so corrections no longer import analysis (C11); last, and only if BBB stays
      identical, pass writer schema options instead of a live module object.
- [ ] **Part 7, callers and docs:** Plotter/Fitter/Tau_Trigger_SF imports, READMEs, shell scripts,
      `config_example.json`, the TauES_ID helper scripts; a migration guide for users' `config.json` (old to new
      channel strings).
- [ ] Absolute configured and job-config paths (changes `pico.jobs` baselines; the reason the API is not
      thread-safe, see [API.md](../PicoProducer/API.md) "Known limitations").
- [ ] Lower-level messages (catalogs, storage, DAS, event counting) still bypass the reporter; workers still read the
      global config through `picojob.py -c`. (API.md)
- [ ] `batch/base.py:32` builds the submit template path from the working directory; take it from the package path.
- [ ] Remove the compatibility layer `PicoProducer/python/processors/` and `Tests/PicoProducer/compat/` once no job
      lists from before 2026-10-13 are in use. (CL §8 "User migration and compatibility")
- [ ] `pico.py install` is a stub (`cli/install.py`: site guess, config defaults, symlinks). Nice to have.
- [ ] TODO comments: `batch/base.py:54`, `jobs/jobconfig.py:90` (compare job configs to avoid
      mixing jobs), `jobs/merge.py:86`, `jobs/pipeline.py:130`, `jobs/status.py:419`, `workers/Bookkeeper.py:39`,
      `corrections/BTagTool.py:131,139,148`.

## 6. Framework

Next-work proposals (not designed in detail yet):

- [ ] A: tuple-manifest preflight.
- [ ] B: replace `os.system` with checked calls in the Fitter scripts.
- [ ] C: one output base per run. Plotter and Fitter outputs are shared between runs and overwritten; `--run-root`
      does not isolate them, and the summary scripts pick up working points of other runs. Agreed design (2026-10-14):
      a stage's output is `<run_dir>/stages/<stage_id>/` (logs in `<run_dir>/logs/<stage_id>/`, a `manifest.json` per
      stage), the scripts run with that directory as working directory, and the Framework gives each input slot
      (CL §15) the artifacts of the stage it names. R2 (layout `logs/<id>/` + `stages/<id>/`, manifests) is done
      (CL §16). R3 is implemented (CL §17): no links or copies; the Framework gives each API its output
      directory and inputs (from the input stages' artifacts), the scripts run in the output directory (the fit
      per era); the script options this needs: [scripts_arg_changes.md](scripts_arg_changes.md); checked on lxplus
      against the shell scripts (Plotter, histograms, fit) and `bbb check`. **Open:** the bugs that change the shell
      output (Fitter BUGS F11, F13, F19, F20, F24, F12's script side), each in its own commit, after the refactor is
      finished (no bug fixing before that). Comparisons of fit
      results need a tolerance: shapes made twice from the same tuples differ by 1e-13 (multithreaded RDataFrame),
      which moves the fitted POIs by up to one grid step and flat nuisance parameters a lot. Later: an input may also be a path (another run's stage directory), which also removes the fit's temporary
      `{shapes: null}` exception (the shapes in `Fitter/`); a built-in stage may repeat.
- [ ] **Production stage at most once per recipe (look at again later).** R4 (planned) lets `plots`, `histograms`
      and `fit` appear any number of times and drops the fixed stage order (the inputs already require that a
      stage reads only earlier stages). `production` keeps the old rule "at most once", on purpose:
      - *Why we want to remove it:* one rule for all stages; one recipe could, for example, produce the nominal
        tuples and the TES/LTF/JTF variation tuples (item F) with different settings in two stages.
      - *Why it cannot be removed yet:* (1) production's job files are not in the run: since CL §18 step 5 the
        merged tuples go to `stages/<id>/`, but the job configs, logs and job output stay in `PicoProducer/output/`
        (`jobdir`, `outdir`), keyed by era, channel, sample and tag, not by stage id, so two production stages of
        one run share (and may overwrite) the same jobs.
        (2) Since CL §18 step 6 the `tuples` slot selects the tuples (the pattern of the production stage it
        names), but one slot names one stage, while histograms read the nominal and the variation tuples together
        (from one directory): two production stages (nominal, variations) cannot feed one histograms stage.
        (3) The run has one PicoProducer
        configuration (`pico.config`); `Framework._pico_config` and `taufw.py plan --local` take the first
        production stage (`recipe.first('production')`).
      - *What would make it possible:* the job files in the stage's directory (jobdir/outdir per stage), a
        PicoProducer configuration per production stage, and list-valued input slots (or one directory for the
        tuples of several production stages). Until then one production stage takes several eras and channels in
        its lists, and separate production settings need separate recipes.
- [ ] **Warning for `null` inputs** (separate session). `null` in a recipe's inputs (e.g. `tuples: null`) is accepted
      only so that old recipes keep working; the standard Framework usage names every input explicitly. `check`,
      `plan` and the menu should warn when a recipe uses it.
- [ ] D: condor for the local stages, and resume. Local stages cannot resume partway; Ctrl+C leaves a stage `NEW`
      with partial output.
- [ ] E: a weights stage.
- [ ] F: variation production (TES/LTF/JTF tuples need their own channels and production runs).

Other limitations ([Analyses/README.md](../../Analyses/README.md) "Current limitations"; CL §10, §11):

- [ ] Sample lists are not part of a bundle (`plot.py`, `createinputsTES.py` import `samples_v15`); needs e.g. a
      `$TAUFW_SAMPLES` hook.
- [ ] Only the uncorrelated DeepTau option-3 fit is wrapped (no corrTES, fullcorr, PNet, UParT).
- [ ] Trigger stage (was out of scope).
- [ ] Plotter and Fitter are wrapped as they are; clean them up behind the same APIs.

## 7. Tests

- Excluded broken cases `pico.sample` and `plotter.rdataframe`: defects and recorded evidence moved to
  [Legacy/Bugs.md](../../Legacy/Bugs.md#excluded-broken-test-and-demonstration-scripts).
- [ ] `Tests/PicoProducer/testSFs.py` still imports the legacy `MuonSFs_ROOT`. Nice to have.
- [ ] Utilities menu tests depend on the terminal and colors (quiet-runner changelog section removed); the later menu commits may have fixed this
      **(verify)**.

## 8. Legacy code and architecture

- [ ] Python 2 scripts kept for migration (CL §3): high priority `Fitter/ETauFR/writedatacard.py` (its
      `prefitFR.json` is read by `text2wp.py`), `Fitter/Zpt/utils.py`, `Fitter/Zpt/config/samples.py` (imported by
      `measureZpt*.py`, `validateZpt.py`); normal `Fitter/HighPT/createinputs.py`,
      `PicoProducer/utils/{checkEvents,convertGENSIM,getDASParents}.py`.
- [ ] Stale references to removed scripts: `Fitter/TauID/README.md:57-58` (`plotfit.py`, `plotfit_dm.py`),
      `Fitter/ETauFR/README.md:63` (`paper/plotpostfit.py`).
- [ ] Missing imports: `Fitter/MuTauFR/createinputs.py:11` (`TauFW.Plotter.plot.datacard`); Tau_Trigger_SF imports
      `TauFW.TriggerSF.Common` (`createTurnOn_multi.py`, `fitTurnOn_multi.py`, `Common/*.py`); its README's command line
      does not match the scripts.
- [ ] Duplicate definitions: two `replace()` in `Plotter/python/sample/SampleSet.py` (163, 436; the general one is
      shadowed); two `ensureDirectory` in `Fitter/TauES_ID/plot2DScan_MultiDimFit.py` (28, 33).
- [ ] Helpers without callers: `_read_profile` (`Fitter/plot1D_NLL_profiles.py`), `plot_scan_correlations`
      (`plot2DScan_MultiDimFit.py`), `rootname` (`common/tools/root.py`), `ensurepoisson` (`Utilities/python/Drawing/hist_tools.py`),
      Tau_Trigger_SF helpers, `analysis/Run3_DEV`.
- [ ] Plotter import-time side effects: `gROOT.SetBatch` in `sample/utils.py`, the `SampleSet.QCD_OSSS` monkey-patch
      (`methods/QCD_OSSS.py`), the RDataFrame setup (A01/A09). Plotter still imports
      `TauFW.PicoProducer.settings.getconfig` (A03).
- [ ] Remaining architecture findings A02, A07, A08, A11, A12, A14 and roadmap steps 4–7 (`LocalR/architecture/`,
      local only).
- [ ] Use Utilities (`FileIO`, `CLI`) at the I/O sites listed in [IOInventory.md](../../Utilities/IOInventory.md);
      today only the Framework, the Fitter/Plotter APIs and three PicoProducer files use them.
- Archived defects and external-payload constraints are tracked in
  [Legacy/Bugs.md](../../Legacy/Bugs.md#one-off-analysis-archives); fix only if revived
  ([LegacyCode.md](../LegacyCode.md)).

## 9. Docs

- [ ] Changelog sections for commits that have none **(verify)**: `b61700f` (`sample_monitor.py` deleted), `e8400fc`
      (`runTESvar.py`, `runShapevar.py` deleted), `cd735b6` (`getTESvariations.py`, `nanoV10branch.txt`, TESvar shell
      scripts), `623a040`/`d801879` (`Legacy/OldAnalysis/` by year), `d5db827` (`LegacyCode.md`, `HowToCodeGood.md`),
      `749dfb3`/`b8309cb` (console menu).
- [ ] Changelog §11 onwards have no `---` separators. Cosmetic.
- [ ] The PicoProducer foundations cleanup moved the forks and generator studies to `PicoProducer/python/legacy/`; several are now in
      `Legacy/OldAnalysis/` (A11, W03). Add a note if wanted.
