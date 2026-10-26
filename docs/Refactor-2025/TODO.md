# Refactor-2025: still to do

# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
**Last updated:** 2026-10-26

Everything the `Refactor-2025` branch has left open: checks that need lxplus, the rest of the `common` → `Utilities`
move, old output kept on purpose, open bugs, and planned next steps. The [change log](Refactor-2025.md) ("CL §N")
records what was done; this file records what was not. Tick an item when it is done and note the commit or changelog
section, or delete it.

Items marked **(verify)** may already be done; check before working on them.

## 0. Custom (Special)
- Stagese delete folder tarzı bir şey eklensin de analiz yapılırken silinmesi gereken dosyalar pipeline içinde stage olrak silinebilsin veya movelanabilsin.
- **Left out of step 2 (plan 16 D7, user 2026-10-18: look at them when the refactor work is done):**
  (1) done in CL §25 (2026-10-19): the four postfit scripts call `CMSStyle.setCMSEra` (lxplus check in §1). (2) `Fitter/Zpt` (`compareZpt.py`, `Zpt/config/samples.py`, Python 2 parts): a
  Histogrammer-like measurement inside the Fitter. (3) A shape-contract module both sides read (step 3 of
  `LocalR/architecture/13`; today the contract is a doc, `docs/contracts/tes-shapes.md`). (4) `FitRequest.pico_config`:
  the fit should not need a PicoProducer config once the shapes are made elsewhere. (5) `Fitter/MuTauFR/createinputs.py`
  (D11): broken import, repair or Legacy (workflow owner).
- **2025 weight branches added after production (plan 22; group answer 2026-10-26):** the 2025/2026 analysis uses
  2024 MC; `puweight_2025_*`, `puweight_2026_69p2`, `puweight_2025_2026_69p2`, `trigweight_2025`,
  `idisoweight_1_2025`, `idisoweight_2_2025` were added to the tuples by `Legacy/OldAnalysis/2025-2026/
  add_pileup_weights.py` and `Legacy/OldAnalysis/2025/add_muon_weights.py` (analysis specific). In the pico tuple
  contract as the "analysis add-on" (CL §35). Open, write-up
  [docs/issues/2025-tuple-weight-branches.md](../issues/2025-tuple-weight-branches.md): which script version made
  `puweight_2025_69p2_v3` (the copy here writes `_v2`); `MC_PileUp_2025.root` into `PicoProducer/data/pileup/`;
  variation and 2026 files processed?; muon SFs read by etau/ee/emu; the 2025 names in `weights.other` of the eras
  before 2025 (known debt in the contract test). Later: the two scripts as a weights step (inputs from the recipe),
  then the add-on list of `Tests/contracts/test_pico_tuples.py` becomes production.
- **Known debt of the pico tuple contract (CL §35):** `setup_tautau.yml` reads `idMedium_1/_2` (muon IDs, not in
  tautau tuples); `setup_etau_inclusive.yml` reads PNet branches `TreeProducerETau` does not write; `ModuleETau`,
  `ModuleTauTau`, `ModuleEMu` have no cutflow bins 18-23 but `ModuleTauPair.fillhists` fills them for DY files.
  Fix (with the setup owners / PicoProducer Part 6), then remove the rows in `KNOWN_DEBT` /
  `MODULES_WITHOUT_STITCH_BINS`.
- **Faster histogram filling (group chat 2026-10-21, look at later):** filling the control histograms from the
  inclusive pico tuples takes ~40 min although multithreading is on (`min(64,os.cpu_count())` in
  `common/python/tools/RDataFrame.py:82`; master has 8). `Run3_DEV/ModuleETau_Inclusive.py` has no tau ID cut, the
  tight cuts come only in the setup `baselineCuts`. First check `tree.Print("clusters")` on the slowest sample (one
  big hadd'ed file with few clusters cannot be split over threads). Two ideas:
  (1) **Skim step** between the common pico tuple and the histograms (nano → common loose pico → user skim, e.g.
  VSe, VSmu, VSjet >= 1 and only the needed branches → histograms → plots). The `preselect` option of
  `Sample.getrdframe` is only an RDataFrame `Filter` and still reads the whole file. The skim must copy the
  `cutflow` histogram unchanged (nevents in bin 1, sumw in bin 17, `Sample.setnevents`), or the lumi-xsec
  normalization breaks.
  (2) **Skip hadd** (`PicoProducer/python/jobs/merge.py`) and let RDataFrame read the job outputs directly (better
  parallel over files). Needs: the completeness check that today gates hadd (`merge.py` step 3), the `cutflow`
  summed over all files for the normalization, and no mixing of outputs from different job settings.

## 1. Checks to run on lxplus


- [ ] **Review fixes of CL §21: nothing may change.** After `git pull` (and `scram b -j4`), in `TauFW/`:
      `git ls-files Histogrammer/config/__init__.py Histogrammer/python/spec/__init__.py` lists both;
      `python3 Tests/run.py bbb check` (22/22, **no re-lock**: `plotter.stack` writes and reads the histogram file
      through the stricter checks); `python3 Tests/run.py checks` (with ROOT `test_histfile.py` also runs the header
      test).
- [ ] **Bug fixes of 2026-10-18:** `python3 Tests/Utilities/test_background.py` five times in a row and once inside
      `python3 Tests/run.py checks` (the flaky cancel test, §7); `taufw.py plan Analyses/no_such_recipe` prints one
      line, no traceback (Framework BUGS K06).
- [ ] **Confirm import-boundary reporting on lxplus:** `python3 Tests/run.py checks --case check_import_boundaries`.
      Nonzero status is expected while coupling remains; compare the debt report, do not rebaseline or fix production
      code to make this validation pass. Detector-only command: `python3 Tests/check_import_boundaries.py DetectorTests -q`. (CL §12)
- [ ] **Fitter scripts after the import change:** with `cmsenv`, `python3 -c "import TauFW.Histogrammer.shapes.rebinning,
      TauFW.Fitter.plot.postfit_TES"` (`rebinning` moved in CL §22) and `python3 plotParabola_POI_region.py -h` (in `Fitter/TauES_ID/`) must import
      without error. (CL §4)
- [ ] **BBB check after the expression helpers move:** `python3 Tests/run.py bbb check`, the `plotter.*` cases must
      pass unchanged (no re-lock); `python3 -c "import TauFW.Histogrammer.shapes.inputs"` (the former `TauFW.Fitter.plot.datacard`, CL §22) with `cmsenv`. (CL §4)
- [ ] **BBB check after the drawing move.** `python3 Tests/run.py bbb check`: every case, `drawing.canvas` included,
      must pass with no difference; no re-lock. Then `python3 Tests/run.py normal` (the `Tests/Plotter` scripts import
      the new paths) and, by eye, one `Plotter/plot.py` run and one Fitter postfit plot. (CL §4)
- [ ] **BBB check after §4.** `python3 Tests/run.py bbb check`; nothing should change (ParallelProcessor/loading
      bar, `Utilities.Math`, `CLI.table`). No re-lock. The `3d09ea6` lock may already include §4 **(verify)**.
      (CL §4)
- [ ] **ParallelProcessor parallel tests** in `Tests/Utilities/test_process.py` (start order, queue, `kwret` through the
      pipe): they need the `fork` start method, so they only run on Linux. (CL §4)
- [ ] **PicoProducer with `ncores>=2`**: one run through `iterevts`/`itervalid` (fork with nested functions).
- [ ] **Framework, TES/ID bundle:** `taufw.py plan Analyses/tes_id_2025`, then a VTight/Tight `taufw.py start` run
      compared with `run_inputs.sh` + `run_workflow_zmm.sh` in a clean copy (`FitparameterValues__mutau_*`,
      `tau_sf/*VSjetVTight_VSeleTight*`). (CL §10 "Tests", §11) Procedure (2026-10-19):
      (1) `python3 taufw.py start Analyses/tes_id_2025 --run-root <AFS work dir>` (hours; `status` at the end shows
      the values, `stages/fit_summary/summary.txt` the values and the correction files); (2) in a clean copy of the
      same commit, `cd Fitter && ./run_inputs.sh` and the VTight/Tight point of `run_workflow_zmm.sh` (its
      `J_VALUES`/`E_VALUES` cut to `VTight`/`Tight` there, since `run_inputs.sh` makes only that point; the shell
      scripts read the tuples from `picodir` of `PicoProducer/config/config.json`: set it to the recipe's tuple
      pattern); (3) `python3 Tests/tools/compare_fitresults.py <copy>/Fitter <run_dir>/stages/fit/2025`
      (FitparameterValues by parameter, the correction JSON files, the ROOT files by name). Separate shape fills
      move a POI by up to one grid step (TODO §6 C): if it is not SAME, rerun with `--poi-atol <grid step>
      --pois-only`, and compare the shapes themselves with `compare_shapefiles.py --rtol 1e-12` as in CL §22 H4.
- [ ] **Runner validation:** `bbb check`, `bbb check -v`, `bbb lock --replace`, then `git diff --exit-code`
      on `Tests/BBB/baselines/` **(verify)**. (quiet-runner changelog section removed)
- [ ] `python3 Tests/run.py normal` after the Plotter legacy move **(verify)**. (Plotter legacy cleanup; changelog section removed)
- [ ] **Manual smoke runs:** `pico.py run -c mutau -y 2022_postEE -m 100`, `pico.py submit ... --dry`,
      `taufw.py plan` on `Analyses/example_mutau_short`, and one small real `taufw.py start` + `advance` until DONE on
      HTCondor. Check by eye that the status loading bar with 15+ outputs looks unchanged **(verify)**.
- [ ] **Plots on a production run's tuples (R4, CL §17):** `{tuples: {path: <a production run>/stages/production}}`
      runs to the end (only `check` and `plan` were checked; possible since the sample list is in the recipe, CL §20).
- [ ] **Test screen on lxplus (CL §18):** `python3 Tests/run.py checks` (all but `check_import_boundaries` pass), then
      in the menu (`taufw.py`): Tests > Normal tests > Run entire family: the cases fill in live, a running case's log
      grows in Details, Enter/L/End work, no line is printed over the screen. Stop a BBB check with S and with Esc + Y:
      the run ends within seconds and `ps -u $USER` shows no left-over worker. `Tests/Utilities/test_background.py`
      runs the real process-group test there (skipped on Windows). Framework events (§18): `python3 Tests/run.py bbb check`
      for the `framework.*` cases passes unchanged; then `TAUFW_EVENTS=/tmp/$USER-ev.jsonl taufw.py advance <a run
      with a local stage>` prints the same and the file holds run, stage_step, progress, stage_state, run_state.
- [ ] **Run lock and safe stop on lxplus (CL §28):** `python3 Tests/run.py bbb check --case framework.production`
      passes without re-lock. Two terminals on different nodes: `taufw.py advance <run> --wait` in one, `advance` in
      the other is refused with host and pid; Ctrl-C in the first, then the second runs. Kill the first with
      `kill -9` on its node: `advance` on the same node takes over at once; from another node it is refused until
      120 s passed, then names `--take-lock`, which continues. Ctrl-C while `start` submits: the warning line, the
      run.json says SUBMITTED, a second `advance` does not submit again. Ctrl-C during a local stage: stops at once,
      no command left in `ps -u $USER`. Done 2026-10-21 on lxplus983: `Tests/run.py all` and the lock refusal and
      takeover with a fake lock file (live: refused also with `--take-lock`; lost elsewhere: hint, then taken;
      this machine, dead pid: taken at once; the file removed each time) on a DONE run. Left: BBB, two nodes, Ctrl-C.
- [ ] **Runs behind the menu on lxplus (CL §29):** done 2026-10-21 with a two-step python recipe on lxplus983 and
      lxplus939: Start, Esc, the main menu line; the CLI advance and the menu of the other node (same live screen);
      stop (failed first: the supervisor's SIG_IGN, fixed); Continue resumes; a killed advance taken over at once on
      its machine. Left after the fixes of that day: the info box, the quit warning, a Run complete card, the "Advance
      lost" screen from another node, the job tests (grid proxy screen, stop during a submission). Original list: in the menu, Start a short recipe: the run screen opens, Esc
      leaves it running, the main menu shows "Run <name> (...)"; it opens the screen again; after the end the card
      once, then the line is gone. Continue a WAITING run with "Advance to the end": live screen, next check
      countdown; Continue the same run from a second terminal on another node: it opens the same screen, no second
      advance. Stop (S) while production submits: the run stops after the submission (run.json SUBMITTED, no
      duplicate jobs in `condor_q`). Log out while a run advances, log in on another node: the line says Lost;
      Continue shows the lock screen after 2 min, T takes over. A production recipe without a grid proxy: the
      "Grid proxy needed" screen. Quit with a run behind the menu: the warning text.
- [ ] **Plan and status behind the menu on lxplus (CL §30):** in the menu, Start > a recipe > View detailed plan:
      the plan scrolls (PgUp/PgDn, End), Esc returns to the review; a production recipe's plan with a long sample
      table (wrapped lines readable?). Inspect a WAITING production run: the screen draws at once, the output comes
      when `condor_q` answers; Esc before that stops it (`ps -u $USER`: no `taufw.py status` left); R refreshes once
      it ended. Continue on a DONE run > Inspect status: the same screen. No line is printed over the screen.
- [ ] **Menu speed on lxplus (CL §31):** after `cmsenv`, from the repo root, three draws' data in a row (the first
      is the old cost: the proxy and every record read; the next two the new):

      ```sh
      python3 - <<'EOF'
      import time
      from TauFW.Framework.interactive import _Operations
      from TauFW.Utilities.Menu import ConsoleUI
      operations, ui = _Operations(), ConsoleUI(None)
      for draw in range(3):
          start = time.time(); operations.grid_proxy_valid(); proxy = time.time()
          shown = [operations.tests_operation()] + operations.run_operations()
          [ui._operation_summary(operation) for operation in shown if operation]
          print("draw %d: proxy %.2f s, records %.2f s" % (draw + 1, proxy - start, time.time() - proxy))
      EOF
      ```

      Check that `voms-proxy-info --timeleft` prints the seconds (the menu shows the ✓ with a valid proxy). In the
      menu: the main menu returns at once from a screen; `voms-proxy-destroy` in another terminal: the next draw
      shows "Proxy Failed!"; `voms-proxy-init -voms cms` there: ✓ again; Start a production recipe without a proxy:
      the "Grid proxy needed" screen (a fresh check). A test run that ends while the main menu is shown: the next
      draw shows "Tests (Done)".
- [ ] **One curses session on lxplus (CL §32):** `python3 taufw.py`: going from screen to screen (Start, a
      recipe, Back, Tests, Help, Esc) never shows the shell. An error in a panel: Tests > Normal tests twice from two
      terminals ("Tests are already running"), Continue > Enter another run directory > a wrong path ("Cannot read
      run"). Grid Certificate: the password panel (only `*`), a wrong password ("Proxy Failed!" and the voms
      lines), the right one ("Grid proxy active.", the ✓ on the main menu); check `voms-proxy-init -voms cms
      -pwstdin` works on lxplus (else the menu leaves the screen and voms asks: check that path too). Tests running:
      the main menu label moves every 2 s without a key, Up/Down keeps working; after the end it stops moving. S on a
      test run: the panel, N, S, Y; while it stops K: the Kill now panel, Y ends it (STOPPED). Quit while tests run:
      the panel over the main menu. A small terminal (80 x 24 and smaller): the panels fit, a long text scrolls.
- [ ] **Start and Esc speed on lxplus (CL §33):** in the menu, Start a new run opens the recipe list at once (the
      first time after a `Configs/` change a little slower); Esc leaves every screen at once; arrow keys still work
      (also over a slow SSH connection: an arrow key must not act as Esc). FastSetup's checklist: Esc at once.
- [ ] **Pico tuple contract on lxplus (CL §35):** `python3 Tests/run.py checks --case unit.contracts` passes; the
      weight branches of one mumu and one etau tuple of the campaign (`.../pico2024/TES_variations/2025/DY/`, branch
      names containing `weight`) answer the issue's open points 3-4 (`idisoweight_2_2025` in mumu? muon SFs in
      etau?).
- [ ] **Lists read ahead on lxplus (CL §34):** open the menu and press Start at once: the list opens at once,
      recipes still checked say "checking..." and fill in within seconds (colours, Pipeline), Up/Down works
      meanwhile; wait a few seconds, then Start: everything is there at once. Edit a recipe in another terminal:
      the next Start says "checking..." for that one only. Continue and Inspect: the same with "loading..." rows;
      the selected run stays selected while rows come. Quit right after opening the menu: no wait.
- [ ] **Tests behind the menu on lxplus (CL §18):** `python3 Tests/Utilities/test_operations.py` (the two real
      stop tests run there). In the menu: Tests > Normal tests > Run entire family, Esc at once: the main menu shows
      "Tests (Running n/N)"; Tests opens the live screen again; after the end "Tests (Done)" or "(Failed: n)" and
      "Last run: ..." in the Tests menu. Start a second run while one runs: refused. Exit while it runs: the warning;
      C stays; Q quits, `ps -u $USER` shows `_supervisor.py` and the tests still running, and `taufw.py` opened
      again (same and another lxplus node) shows them; S stops them within seconds (no left-over worker). Log out
      while a run is going, log in: "Tests (Lost)" after at most two minutes (or the run finished, if lxplus let it
      live). S on the screen asks first, and stops.
- [ ] SGE adapter (S01) has never run on an SGE site; nice to have. ([PicoProducer BUGS](../PicoProducer/BUGS.md) S01)

## 2. Moving `common/python/tools/` into `TauFW.Utilities`

Done: `parallel`, `LoadingBar` (§4), `math` (§4), `Table` (§4). Rules for the rest:

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

**`CLI.table`** — `Utilities/python/CLI/_internal/table.py`, section `LEGACY, CLEAN UP LATER` (CL §4):

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

**Loading bar** — `Utilities/python/CLI/_internal/loading_bar.py`, `BACKWARD COMPATIBILITY, CLEANUP` (CL §4):

- [ ] Replace the `\b` backspace redraws (e.g. `CLI.update_progress` with `\r`).

**ParallelProcessor** — `Utilities/python/Process/_parallel.py`, `BACKWARD COMPATIBILITY, CLEANUP` (CL §4):

- [ ] Verbose messages still name the old classes (`MultiProcessor.start`, `ReturnProcess.join`, ...), and `close()`
      always prints; route through a CLI instance.
- [ ] Nested target functions need the `fork` start method; Python 3.14 changes the Linux default. Nice to have.

**Drawing library** — `Utilities/python/Drawing/`, moved as it was from the Plotter (CL §4). Each item changes the
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
- [ ] `Histogrammer/python/spec/string.py` (`Plotter/python/plot/string.py` before CL §21) re-exports the label helpers of `labels.py` for its star-importers
      (`Variable.py`, `Sample.py`, `Selection.py`); import them explicitly there.
- [ ] `PicoProducer/utils/compare{Nano,Pico}.py` (Python 2) still import the Plotter's `Variable`; give them a plain
      string axis or move them to `Legacy/OldAnalysis/`. Not on any production path.

**Quirks frozen in BBB baselines** (PicoProducer plan):

- [ ] Stitch log in `Histogrammer/python/sample/utils.py` (~lines 403, 451) is missing its `f` prefix.
- [ ] `workers/picojob.py:74` cuts the `-i` list to `nfiles` (the range case reads only `nano_A`).

## 4. Open bugs

**PicoProducer** ([BUGS.md](../PicoProducer/BUGS.md)), planned for Part 6 (§5 below), none fixed yet:

- [ ] Analysis modules: A01, A02, A03, A04, A05, A06, A07, A08 (cosmetic), A09, A10, A12 (latent), A14.
- [ ] Corrections: C01, C02 (cosmetic), C03, C04, C05, C06, C07, C08, C09 (latent), C11 (layering), C12, C13 (latent).
- [ ] **Blocking for Part 6:** a `pico.channel_tau_pair` BBB case based on `ModuleTauPair` (larger synthetic NanoAOD
      plus jsonpog/TauIDSFs payloads). Every A/C fix must be checked against it.
- Legacy-only entries A11, A13, C10, W03 and the archived A01 copies moved to
  [Legacy/Bugs.md](../../Legacy/Bugs.md#picoproducer). Won't fix in maintained code: P15, S16, W01.
- [ ] S17: `Sample.loadjson` drops `store`, so private-storage samples with short paths warn "DAS path ... has wrong
      format" on every `status`/resubmit (message only; seen on lxplus, CL §16).

**Fitter** ([BUGS.md](../Fitter/BUGS.md)), registered only, options 4–6 of the workflow:

- [ ] F08: `merge_datacards_regions` called with 7 arguments, takes 6 (crash).
- [ ] F09: `hasattr` on a dict is always false, so the Zmm card is never added (latent).
- [ ] F10: the combined card is written to `output_{era}/` (wrong).
- [ ] F26: option 6 reads `tidRegions`, the configs have `tid_SFRegions` (latent; CL §22).

**Histogrammer** (the former Plotter, CL §21; [BUGS.md](../Histogrammer/BUGS.md)):

- [ ] L02: `fname=` vs `file=` (`config/samples_v15.py:285` vs `python/sample/utils.py:29`); needs a test with tuples.
- [ ] L03: `sumhists` adds to an undefined `sighist` (now `Utilities/python/Drawing/hist_tools.py`); the fix changes
      the `drawing.canvas` baseline (`$.tools.sumhists`), so re-lock.
- [ ] L04: `estimatelen` with several arguments raises `TypeError` (now `Utilities/python/Drawing/labels.py`).
- [ ] L14: split `DM` in `samples_v15.py` (and the sample model, kept on purpose) uses the undefined `samples`.
- [ ] L15: electron data `else:` without assignment in `samples_v15.py` (unreachable for its eras).
- [ ] L16: era `2526` with tautau/emu: `getyear('2526')` is a text, the `%d` data pattern raises.
- [ ] L17: no `m_ll` alias for the mumu variables of `fillhists.py` (crash with `-c mumu`; CL §21).
- [ ] L18-L21 (`createinputsTES.py`, Histogrammer after step 2 H1; CL §22): control plots only with `systematics`
      (latent), `varprocs` only for mutau/mumu (latent), shape files never recreated, so a rerun keeps old
      histograms (wrong, standalone reruns), rebinning of the first observable only (latent).
- [ ] L22-L24 (`rebinning.py`, `createinputsTES.py`; CL §22): `rebinning` stops on a region without a bin under 30 %
      relative error (crash, sparse regions), its error accumulation grows instead of shrinking (wrong, rebinned
      plots only), the control-plot names repeat the tag (cosmetic).
- [ ] L12: `getmcsample` ignores its `pico=` keyword (`python/sample/utils.py:119-120`; no callers, latent).

**Framework** ([BUGS.md](../Framework/BUGS.md)), registered only:

- [ ] K01: a moved or copied run reads the artifacts of its `DONE` stages at the old location (latent).
- [ ] K02: a crash between `manifest.json` and `run.json` leaves the stage `NEW` with a non-empty output directory
      (latent).
- [ ] K04: production's tuple artifacts have no `kind`, so a filter by `kind='tuples'` finds none (latent).
- [ ] K05: on Windows (Python 3.13) `/afs/...` is not absolute for `os.path.isabs`; an lxplus `pico.config` is joined to the bundle directory (latent, Windows only).
- [ ] K07: `taufw.py status` shows the last `advance`'s message ("... failed or missing; resubmitting") next to a live
      job table that says complete; reads as a contradiction (message only; seen on lxplus, CL §16).

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

- [ ] **Half-done job submission (production).** If the process dies (SIGKILL: logout, a lost SSH connection, a
      restarted machine) after condor accepted the jobs but before `run.json` records them, `run.json` still says
      "nothing submitted" and the next `advance` submits everything again (duplicate jobs, duplicate output, quota).
      Ctrl-C will be safe (the menu's run stop waits for the submission, CL §18), SIGKILL never is; plain CLI runs
      have the same risk today. Fix in the production stage: record "submitting" in `run.json` before the submit;
      an `advance` that finds it without a submission stops and asks for a `condor_q` check. Not part of the menu
      work (user, 2026-10-17).
- [ ] **Menu as a program, next steps** (CL §18, §18; decisions in §23): (1) `advance` lock in the run
      directory (O_EXCL file: pid, host, time; also the CLI; refused while held on another machine; taken over on
      request when its operation is Lost) and a safe stop in `taufw.py` (SIGINT waits for a job submission to finish
      and for `run.json`, a local command is stopped at once); (2) the run screen: the test screen split into a
      shared core (layout + model) and the test model, the run model on the Framework side, the log path in the
      `progress` event (`run_all` computes it after `progress(..., None)`), start/advance as operations
      (`escalate=False`); (3) `plan`/`status`/`check` beside the screen (output-only view, Esc stops them);
      (4) one curses session for the whole menu, live labels, errors on screen instead of print + Enter, and a
      small panel over the current screen (`_modal()`) for the quit warning (now a full screen), errors such as
      "Tests are already running", and confirmations (stop, kill now) (user, 2026-10-18: deferred to this step).
      Run screen design (user, 2026-10-18): Start/Continue in the menu run `advance --wait` behind the menu (to the
      end: DONE or FAILED; "Advance once" only as a secondary action); a Lost run resumes with Continue (lock
      takeover). The list shows stages (marker, id, type, state, time), Details by state (local commands from
      `progress`, the wait countdown, the error), the log of the selected stage; the list comes from `run.json`, the
      events only update the live part. A run that ends shows a result card (complete / failed / stopped / lost,
      full run dir path). Main menu: a line per active run like Tests, "Run <id> (3/5 plots)", "Runs (2 active)";
      a finished run keeps its line ("Done", "Failed at plots") until its card is opened once (a `seen` file in the
      operation dir). Order: first a UI preview at the bottom of the Tests menu (mock screens, ←→ between them,
      the real screen functions with fake operations; no process, no files under `.artifacts/`; not a test family;
      unit tests only check that each scenario draws), then the shared core, then the run screens in the preview,
      wired to Start/Continue only after (1). Done 2026-10-18: the UI preview and the shared core (CL §18); the run
      model stays in the Menu (K2 revised: events only, Framework supplies the `run.json` stages as data). Done
      2026-10-18: the run screen and its result cards in the preview (`_run_screen.py`, CL §18), and the main
      menu run line, the runs chooser, the run list label and the lock screens (CL §18 "Runs in the menus").
      Done 2026-10-21: (1) and the log path in `progress` (CL §28); the wiring of Start/Continue, the run lines,
      the `seen` file, Continue on an advancing run and the lock screen (CL §29); the info box with each stage's
      recipe options (first version, CL §29). Done 2026-10-21: step (3) for plan and status (CL §30; the plain
      output, Esc stops; no `check`: the lists show the problems). Done 2026-10-21: menu speed (CL §31: the proxy
      answer kept until it expires or its file changes, fresh before a run; ended operations and their events read
      once). Done 2026-10-21: step (4) (CL §32: one curses session, panels for errors, the quit warning and the
      stop question, K Kill now while it stops, the grid password in the menu with `-pwstdin`, the main menu live
      every 2 s). Left: a choice of fields per stage type if the options are too much.

Next-work proposals (not designed in detail yet):

- [ ] A: tuple-manifest preflight. Partly done (CL §16 step 6): the preflight of plots and histograms checks that
      the production tuple files exist, or the directory of an `{external: ...}` pattern. Open: which files an
      external pattern must hold (needs the sample list in the recipe).
- [ ] B: replace `os.system` with checked calls in the Fitter scripts.
- [ ] C: one output base per run. Plotter and Fitter outputs are shared between runs and overwritten; `--run-root`
      does not isolate them, and the summary scripts pick up working points of other runs. Agreed design (2026-10-14):
      a stage's output is `<run_dir>/stages/<stage_id>/` (logs in `<run_dir>/logs/<stage_id>/`, a `manifest.json` per
      stage), the scripts run with that directory as working directory, and the Framework gives each input slot
      (CL §13) the artifacts of the stage it names. R2 (layout `logs/<id>/` + `stages/<id>/`, manifests) is done
      (CL §14). R3 is implemented (CL §15): no links or copies; the Framework gives each API its output
      directory and inputs (from the input stages' artifacts), the scripts run in the output directory (the fit
      per era); the script options this needs: [scripts_arg_changes.md](scripts_arg_changes.md); checked on lxplus
      against the shell scripts (Plotter, histograms, fit) and `bbb check`. **Open:** the bugs that change the shell
      output (Fitter BUGS F11, F13, F19, F20, F24, F12's script side), each in its own commit, after the refactor is
      finished (no bug fixing before that). Comparisons of fit
      results need a tolerance: shapes made twice from the same tuples differ by 1e-13 (multithreaded RDataFrame),
      which moves the fitted POIs by up to one grid step and flat nuisance parameters a lot. R4 (CL §17): an input may
      name another run's stage directory (`{path: ...}`, read through its manifest), and plots, histograms and fit
      may repeat. The fit's `{shapes: null}` stays for old recipes (warning item below).
- [ ] **Production stage at most once per recipe (look at again later).** R4 (CL §17) lets `plots`, `histograms`
      and `fit` appear any number of times and drops the fixed stage order (the inputs already require that a
      stage reads only earlier stages). `production` keeps the old rule "at most once", on purpose:
      - *Why we want to remove it:* one rule for all stages; one recipe could, for example, produce the nominal
        tuples and the TES/LTF/JTF variation tuples (item F) with different settings in two stages.
      - *Why it cannot be removed yet:* (1) production's job files are not in the run: since CL §16 step 5 the
        merged tuples go to `stages/<id>/`, but the job configs, logs and job output stay in `PicoProducer/output/`
        (`jobdir`, `outdir`), keyed by era, channel, sample and tag, not by stage id, so two production stages of
        one run share (and may overwrite) the same jobs.
        (2) Since CL §16 step 6 the `tuples` slot selects the tuples (the pattern of the production stage it
        names), but one slot names one stage, while histograms read the nominal and the variation tuples together
        (from one directory): two production stages (nominal, variations) cannot feed one shapes stage
        (the `histograms` stage until CL §21, S4a).
        (3) The run has one PicoProducer
        configuration (`pico.config`); `Framework._pico_config` and `taufw.py plan --local` take the first
        production stage (`recipe.first('production')`).
      - *What would make it possible:* the job files in the stage's directory (jobdir/outdir per stage), a
        PicoProducer configuration per production stage, and list-valued input slots (or one directory for the
        tuples of several production stages). Until then one production stage takes several eras and channels in
        its lists, and separate production settings need separate recipes.
- [ ] **Warning for `null` inputs** (separate session). `null` in a recipe's inputs (e.g. `tuples: null`) is accepted
      only so that old recipes keep working; the standard Framework usage names every input explicitly. `check`,
      `plan` and the menu should warn when a recipe uses it. The warning machinery exists (`recipe_warnings`,
      CL §16 step 1). Same session: warn when a production stage has a non-empty `tag`, since the readers look for
      `<sample>_<channel>.root` (the tag does not reach them).
- [ ] **Revise: one rule for the paths in a recipe** (separate session). A recipe has several path rules today:
      stage path options and `pico.config` (relative: the bundle file if it exists, else the module resolves it;
      `pico.config` above the bundle is made absolute when loaded), `run_root` (absolute; `~` and `$VARIABLES`
      expanded where `taufw.py` runs, with a warning), `{external: <pattern>}` (absolute only, nothing expanded) and,
      from R4, `{path: <stage directory>}` (absolute only for now, decided 2026-10-17; relative to the recipe's
      directory was the first plan). The absolute test also differs: `_is_absolute` (posixpath or os.path) in
      `recipe.py`, `os.path.isabs` elsewhere ([Framework BUGS](../Framework/BUGS.md) K05). Decide one rule (what is
      relative to what, what is expanded, where it is checked), apply it to every path key and document it in
      `Analyses/README.md` "Paths and configuration".
- [ ] **Production job files in the run.** The merged tuples are in `stages/<id>/` (CL §16), but the job configs, logs
      and job output still go to `jobdir`/`outdir` of the PicoProducer configuration (`PicoProducer/output/`), shared
      by every run with the same era, channel and tag. Needs PicoProducer to take them from the request, like
      `JobRequest.tupledir`. A prerequisite for production repeating (item above).
- [ ] **Grid proxy check before production submits (idea).** The HTCondor template has `use_x509userproxy = true`;
      without a valid proxy every job is held ("reading from file /tmp/x509up_u<uid>: No such file", seen on
      lxplus 2026-10-17) and a held job looks "missing" to the status check, so `advance` resubmits it and spends
      the tries. The production stage's preflight (or PicoProducer's `plan`/`submit`) could check
      `voms-proxy-info --exists --valid H:M` (or the `$X509_USER_PROXY` file) and stop with a clear message; on lxplus
      the proxy belongs on AFS (`voms-proxy-init --voms cms --out ~/private/x509up`, `export X509_USER_PROXY=...`),
      since the schedd cannot read the `/tmp` of the login node. Related: held jobs could be reported as held, not
      missing.
- [ ] **EOS as `run_root`.** Accepted by the validator but not tested: the local stages (combine with many small
      files, ACLiC builds, `run.json` rewritten after every step, `run.log` appends) on EOS FUSE, and the merge of
      production there (the storage factory picks its EOS class for `/eos/` paths). Until then the documented home
      of the runs is AFS (`/afs/cern.ch/work/...`).
- [ ] D: condor for the local stages, and resume. Local stages cannot resume partway; Ctrl+C leaves a stage `NEW`
      with partial output.
- [ ] E: a weights stage.
- [ ] F: variation production (TES/LTF/JTF tuples need their own channels and production runs).

Other limitations ([Analyses/README.md](../../Analyses/README.md) "Current limitations"; CL §10, §11):

- [ ] **Config templates (CL §19), open points.**
      - Acknowledging an old copy: `taufw.py check` warns as long as a bundle copy is older than its template in
        `Configs/`, also when the analysis keeps the old version on purpose (e.g. to reproduce a published result).
        For now a plain warning (user, 2026-10-17); if it becomes noise, a recipe key that accepts a named
        id/version.
      - Moving the existing module configs to `Configs/`. Decided (user, 2026-10-17): each module's YAML configs
        move when the step that touches them is done, not in one separate move:
        `Plotter/config/setup_*.yml` at the end of the sample-model step (**done**, CL §20 S7:
        `Configs/Plotter/setups/`; `Plotter/tutorial/config/` stays with the tutorial, whose samples are Python); the Fitter fit configs (`Fitter/TauES/config/`, `Fitter/TauES_ID/config/`) inside the step that moves
        histogram filling out of the Fitter (`config_coarse_TT.yml` is likely split there, so it moves once); the
        PicoProducer sample lists (`PicoProducer/samples/*.py`, Python) when they become data. Python configs and
        `PicoProducer/config/` (internal, user/machine settings) never move. For every move: a `taufw_config`
        header; the reader must ignore that key; the default paths of the scripts (`plot.py`
        `config/setup_%s.yml`, `createinputsTES.py`), the `run_*.sh` scripts, the API path resolution ("relative to
        Plotter/ or Fitter/"), the bundle path rule (`module`), `taufw.py init --from`, docs and BBB cases name the
        old paths (20-32 files per directory); the copies already in `Analyses/*/` have no header and need one.
      - Optional: a git pre-commit hook that runs `taufw.py configs update`, so the lock never needs a test failure
        to be noticed (hooks are per clone: needs a setup step).
      - The menu does not list the templates yet (`taufw.py configs` does).
- [ ] Only the uncorrelated DeepTau option-3 fit is wrapped (no corrTES, fullcorr, PNet, UParT).
- [ ] Trigger stage (was out of scope).
- [ ] Plotter and Fitter are wrapped as they are; clean them up behind the same APIs.

- [ ] **Old fill-and-draw variants (CL §21, S3 decision: left as they are):** `Histogrammer/plot_postfit.py`,
      `plot_postfit_shift.py` (2024, `samples_v12`, TES shifts per decay mode hard-coded), `plot_v10.py` (v10 tuples;
      in `Fitter/TauES_ID/README.md:115`) still fill and draw in one script (they work through the old names). Decide:
      Legacy (with their config and macro paths) if nobody uses them, else the two-step form (`--hists`, `draw.py`).
      `Histogrammer/tutorial/` becomes an example of the two steps after S4.
- [ ] **Control plots, later (CL §21 S4 decisions, plan 18 §14):** `controlplots` draws every file of its input
      (no era/channel filter); one file cannot be drawn again with another tag (the tag is in the file); external
      control-histogram files (`{external: <file>}`) are not an input (`{path: <run_dir>/stages/<id>}` of another
      run works through the general mechanism and is tested with fakes only).
- [ ] **Variable list as a template (CL §21 observation):** the variables users actually edit are Python code inside
      `Plotter/plot.py` (`:44-95`, later `Histogrammer/fillhists.py`); a `Configs/Histogrammer/` template for them is a
      new feature (not part of the rename/extraction).

## 7. Tests

- Excluded broken cases `pico.sample` and `plotter.rdataframe`: defects and recorded evidence moved to
  [Legacy/Bugs.md](../../Legacy/Bugs.md#excluded-broken-test-and-demonstration-scripts).
- [ ] `Tests/PicoProducer/testSFs.py` still imports the legacy `MuonSFs_ROOT`. Nice to have.
- [ ] BBB `histogrammer.tes_inputs` (CL §22): `ZL`/`TTL`, so the content of the LTF shape systematics, are zero in every
      region (no opposite-sign fixture event with `genmatch_2` 1-4 passes the baseline); the LTF variation files are
      read, their filled content is not covered (user decision 2026-10-18: accepted; real data covered it in step 2 H4,
      CL §22: 96 LTF histograms with content, the same as the old code within the noise).
      When the case is re-locked anyway (migration point, or a bug fix that changes it), also cycle `genmatch_2` in
      `_tes_events`.
- [ ] Utilities menu tests depend on the terminal and colors (quiet-runner changelog section removed); the later menu commits may have fixed this
      **(verify)**.
- [ ] **`Utilities/IOInventory.md` and its generator disagree (seen in CL §21 S4):** `python Utilities/_audit_io.py`
      writes a much smaller file than the committed one (no author line; 349 instead of 425 files, the Legacy rows
      gone). The rows were edited by hand since. Find which scope the committed file was made with, then regenerate.

## 8. Legacy code and architecture

- [ ] **Backward compatibility to delete at the migration point:** `Histogrammer/config/samples_v15.py` (was
      `Plotter/config/`) stays for recipes and commands without `samples:` / `--samples` (CL §20, decision D4: no
      warning for now). When it goes, the BBB case `plotter.sample_model` keeps the reference (it runs the model with
      the templates).
- [ ] **At the migration point, with `samples_v15.py` (CL §26, §27): the luminosity of the normalisation has one
      source.** Until then two: the sample model's `lumi` (the new path) and `CMSStyle.lumi_dict`, which `setera`
      still uses when no lumi is given (`Histogrammer/python/sample/utils.py:148`, the old path) and which the fit
      scripts use without `--lumi`. Then: `setera` without a lumi becomes an error (or takes the model's only);
      `CMSStyle.lumi_dict` stays a label default only (or goes); the test `test_template_lumi_is_the_table_value` and
      `table_lumi`/`without_model_lumi` of the sample-model tests go (they compare the templates with the table); the
      fit scripts' `--lumi`/`--cme` become required when run by the Framework. Before that point, a new lumi value
      (brilcalc) goes into the template and the table together in one commit, with the `plotter.sample_model` re-lock
      as a physics change in the CL, or the equality test fails (plan 22 K6, user 2026-10-19).
- [ ] **Backward compatibility to delete at the migration point (CL §21, Plotter -> Histogrammer):** the 13 alias
      modules in `Plotter/python/{sample,plot,methods}/` (and their 13 entries in
      `Tests/import_boundary_allowlist.json`, `Tests/Histogrammer/compat/`), the legacy `Plotter/plot.py` and
      `Histogrammer/plot.py`. Callers of the old names left today: Fitter 8 files (`setera` in the postfit scripts,
      `Zpt`, `ETauFR/Plotter/plotpostfit.py`: not histogram filling, so not step 2 of 13 either; their own items,
      16 D7: a `TauFW.Utilities.Drawing` era setter, Zpt), Legacy 19 files (they break then; Legacy policy), the old scripts in `Tests/Plotter/` (retarget or retire them first). The BBB case
      names `plotter.*` can be renamed at the same point (one re-lock). Also `RENAMED_IDS` in
      `Framework/python/configs.py` (bundle copies with the ids `plotter.samples_*` / `plotter.setup_*` from before
      S2) and its test `test_copy_with_the_id_from_before_a_rename`. Also `PLOTTER_ROOT`/`PLOTTER_DATA_DIR` of
      `TauFW.Utilities.Paths` (no caller in the repository; `Plotter/data` does not exist since CL §21, the data is
      in `HISTOGRAMMER_DATA_DIR`): delete them, or keep `PLOTTER_ROOT` for the new Plotter (review of CL §21).
- [ ] **Backward compatibility to delete at the migration point (CL §22, TES shapes to the Histogrammer):** the five
      LEGACY stubs at the old script paths (`Fitter/TauES/createinputsTES.py`,
      `Fitter/{ETauFR,HighPT,paper,tutorial}/createinputs.py`; they print the new command and exit with 2) and their
      test `Tests/Histogrammer/compat/test_legacy_shape_scripts.py`.
- [ ] **At the migration point, after S4 (CL §21):** `fillhists.py` still draws by default (commands typed by hand
      keep their result, user rule of S4); then drawing leaves it (`--hists --no-draw` becomes the default, the
      legacy `plot.py` texts show the two commands). Remove `stages.RETIRED` (the messages for `plots` and
      `histograms` in old recipes) and `stages.MOVED_CONFIGS` (the message for the old paths of the TES/ID configs,
      CL §22 H2) and decide whether `controlplots` is renamed `plots` (one recipe change).

- [ ] Python 2 scripts kept for migration (CL §3): high priority `Fitter/ETauFR/writedatacard.py` (its
      `prefitFR.json` is read by `text2wp.py`), `Fitter/Zpt/utils.py`, `Fitter/Zpt/config/samples.py` (imported by
      `measureZpt*.py`, `validateZpt.py`); normal `Histogrammer/shapes/HighPT/createinputs.py` (`Fitter/HighPT/` until CL §22),
      `PicoProducer/utils/{checkEvents,convertGENSIM,getDASParents}.py`.
- [ ] Stale references to removed scripts: `Fitter/TauID/README.md:57-58` (`plotfit.py`, `plotfit_dm.py`),
      `Fitter/ETauFR/README.md:63` (`paper/plotpostfit.py`).
- [ ] Missing imports: `Fitter/MuTauFR/createinputs.py:11` (`TauFW.Plotter.plot.datacard`); Tau_Trigger_SF imports
      `TauFW.TriggerSF.Common` (`createTurnOn_multi.py`, `fitTurnOn_multi.py`, `Common/*.py`); its README's command line
      does not match the scripts.
- [ ] Duplicate definitions: two `replace()` in `Histogrammer/python/sample/SampleSet.py` (163, 436; the general one is
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

- [ ] Stale before CL §21 (found in its review, 2026-10-18; not changed then): (the `Analyses/README.md:304` example
      `config/setup_mutau.yml` was replaced when that row was rewritten for templates, CL §22 H2) the item
      "`PicoProducer/utils/compare{Nano,Pico}.py`" of §3
      names files that are no longer in the repository; `Tests/README.md` (import boundaries) quotes the totals of
      2026-10-14 (24 / 22 / 20), today 30 / 28 / 26 (CL §21).
- [ ] Changelog sections for commits that have none **(verify)**: `b61700f` (`sample_monitor.py` deleted), `e8400fc`
      (`runTESvar.py`, `runShapevar.py` deleted), `cd735b6` (`getTESvariations.py`, `nanoV10branch.txt`, TESvar shell
      scripts), `623a040`/`d801879` (`Legacy/OldAnalysis/` by year), `d5db827` (`LegacyCode.md`, `HowToCodeGood.md`),
      `749dfb3`/`b8309cb` (console menu).
- [ ] Changelog §11 onwards have no `---` separators. Cosmetic.
- [ ] The PicoProducer foundations cleanup moved the forks and generator studies to `PicoProducer/python/legacy/`; several are now in
      `Legacy/OldAnalysis/` (A11, W03). Add a note if wanted.
