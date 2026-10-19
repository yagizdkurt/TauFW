# Refactor-2025: done

# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
**Last updated:** 2026-10-19

Completed TODO points, kept under their original headings and in their original order.

## 0. Custom (Special)

- **Variation tuples in preflight (plan 16 D8):** done in CL §23 (2026-10-19): the shapes preflight names every
  variation tuple of the configs (`TESShapes.variation_problems`); lxplus checks in §1.

## 1. Checks to run on lxplus

- [x] **BBB lock with `histogrammer.tes_inputs` (CL §22, H0).** Done 2026-10-18 on lxplus with the old script
      (`f3079fa`): the first attempt stopped in the old `rebinning` (sparse fixture, BUGS L22; fixed in the case,
      `0c611f4`); then the case alone exit 0 (14 s), `lock --replace` 23 cases, `bbb diff` 22 same + 1 added, `bbb check`
      twice 23/23. The 22 others were `same` in both attempts, so the review fixes of CL §21 changed nothing.
- [x] **Shape scripts moved to the Histogrammer (CL §22, H1).** Done 2026-10-18 on lxplus after `scram b`: the new
      package imports; `bbb check` 23/23 without re-lock (`histogrammer.tes_inputs` with the moved script,
      `fitter.shapes`/`fitter.rebin` with `TauFW.Histogrammer.shapes`); `checks` 14/15 (`check_import_boundaries` known
      debt, 25 / 23 / 21, 0 new pairs); the old path prints the new command and exits with 2; `taufw.py plan
      Analyses/tes_id_2025` runs `Histogrammer/shapes/TauES/createinputsTES.py`.
- [x] **The lock describes the code before the move (CL §22, H0/H1).** Done 2026-10-18 on lxplus: the old code
      (`0c611f4`, in a `git worktree`, the case running `Fitter/TauES/createinputsTES.py`) against the lock:
      `bbb check --case histogrammer.tes_inputs --case fitter.shapes --case fitter.rebin` 3 checked, 0 failed.
- [x] **Channel configs to `Configs/Fitter/tes_id/` (CL §22, H2).** Done 2026-10-18 on lxplus: `bbb check` 23/23
      without re-lock; `checks` 14/15 (`check_import_boundaries` known debt, 25 / 23 / 21, 0 new pairs); `taufw.py
      configs` 19 templates, the four `fitter.tes_id_*` with `lock ok`; `taufw.py plan Analyses/tes_id_2025` before
      and after the pull: no difference. The refusal of an old config path in a recipe is checked by the unit test
      `test_templates_and_moved_configs` only.
- [x] **TES shapes API to the Histogrammer (CL §22, H3).** Done 2026-10-18 on lxplus (`63f299c`): `bbb check` 23/23
      without re-lock; `checks` 14/15 (`check_import_boundaries` known debt, 25 / 23 / 21, 0 new pairs); `python3
      taufw.py plan Analyses/tes_id_2025` (77 lines) the same at `1e4eb77` (before H3), `63f299c` and `e64dfe5`;
      `grep -rn Histogrammer Fitter/python` nothing. (`taufw.py` is not on PATH on lxplus: `python3 taufw.py` in
      `TauFW/`.)
- [x] **TES shapes on real data, old code against new (CL §22, H4).** Done 2026-10-19 on lxplus: the shapes-only
      recipe `~/h4/shapes.yml` (tuples, configs, sample file of `tes_id_2025`) with the code before H1 (`0c611f4`, a
      second CMSSW area) and twice with HEAD: old against new 43 files, every key the same, 775 histograms SAME within
      1e-12 (largest 5e-13; LTF 96 histograms with content); new against new (the noise) largest 1.07e-12. `check`/
      `plan` of `tes_id_2025` and `example_mutau_long`: no problems.
- [x] **Variation tuples in the shapes preflight (CL §23).** Done 2026-10-19 on lxplus: `check_variation_files.py`
      SAME 144 (mutau) and SAME 0 (mumu) against the real `SampleSet`; `check`/`plan` of `tes_id_2025` no variation
      problem; a shapes-only copy on a symlink mirror without `TT/TTtoLNu2Q_mutau_LTF1p030.root`: `plan` warns "1 of
      144 ... (_LTF1p030: 1): <that file>", `start` leaves the stage NEW ("Stage shapes is not ready: ...", no command
      run); `check` does not run stage preflights (recipe only), so it says nothing; `checks` 14/15
      (`check_import_boundaries` known debt, 25 / 23 / 21, 0 new pairs).
- [x] **CL §25-§27 (postfit era via CMSStyle; lumi in the sample model and the control-histogram file; fit plot
      labels, explicit sample lumi).** Done 2026-10-19 on lxplus (`74d8e68` -> `4afa0bd`): reference run of a
      `hists` + `plots` copy of `tes_id_2025` with the old code (`~/c1/old`), then the pull; `check_setera.py` SAME (28
      cases); `bbb check`: only `plotter.sample_model` (lumi) and `histogrammer.tes_inputs` failed, the latter because
      its own mini sample model had no `lumi` (fixed in `3268066`, then it passed without re-lock); re-lock of the whole
      suite (`lock` takes no `--case`): `bbb diff` 22 same / 1 changed, only `plotter.sample_model.json` and
      `manifest.json` changed, 658 `lumi` fields (each the old table value of its era), without them the baseline is
      identical, committed `4afa0bd`; `bbb check` 23/23. Real data: every PNG of the new run equal to the old (`cmp`),
      both files `version 2, lumi 110.18, cme 13.6`; `taufw.py configs` the eight samples templates at version 2, lock
      ok; `plan` of `tes_id_2025`: 4 fit commands with `--lumi 110.18 --cme 13.6`; the seven fit scripts list
      `--lumi`; postfit imports ok; `checks` 14/15 (known import debt 21 / 19 / 17, 0 new pairs). Open from §27: the
      fit plots themselves on the next fit run (TODO §1 "Framework, TES/ID bundle").
- [x] **Done on lxplus** (details in the changelog sections):
  - CL §21 S0/S1 (2026-10-18): `plotter.stack` locked (22 cases); `roundtrip_spike.py` 12/12 SAME; `fillhists.py`
    equals the old `plot.py` (4 PNG byte-identical); the legacy `Plotter/plot.py` prints the new command, exit 2.
  - CL §21 S2: `Configs/Histogrammer/` (15 templates), `bbb check` 22/22; a copy with the old ids gets the three
    "renamed ... change the id" warnings.
  - CL §21 S3: `--hists` and `draw.py` change no plot (mutau 31/31, mumu 19/19 with 18 variables, since `m_ll` has
    no branch, BUGS L17); the logs were not compared line by line.
  - CL §21 S4a: `taufw.py plan tes_id_2025` gives the same commands after `histograms` -> `shapes`.
  - CL §21 S4: `controlhists` + `controlplots` give every PNG of the old `plots` stage (`~/s4ref`). **Noise:**
    `--no-draw` vs fill-and-draw differ by 4.6e-13 relative, the same as two runs of the old path (1.9e-13,
    6.5e-13): run-to-run noise of the multithreaded fill. Timing: mutau fill 388 s, drawing 5 s per file.
  - CL §20: `plotter.sample_model` locked with the old code, switched with no difference; `example_mutau_long` plans
    25 samples / 478 jobs; S7 setups read from `Configs/`; S6 sample model end to end: 57 PNG identical, shapes
    within 6.6e-14 (MC) and 1.6e-13 (derived `QCD`, subtraction), the RDataFrame noise of CL §15.
  - CL §17 (R4): the six checks passed; only `framework.production` re-locked (`"schema": 3`, `"sources"`).
  - CL §16: production and run-local tuple routing; Fitter F07 confirmed (rebinned plots made, status 0).
  - CL §4: `drawing.canvas` locked 2026-10-14.

## 2. Moving `common/python/tools/` into `TauFW.Utilities`

## 3. Old output kept on purpose (clean up later)

## 4. Open bugs

**PicoProducer** ([BUGS.md](../PicoProducer/BUGS.md)), planned for Part 6 (§5 below), none fixed yet:

**Fitter** ([BUGS.md](../Fitter/BUGS.md)), registered only, options 4–6 of the workflow:

- [x] F25: fixed ROOT detection when ROOT is already imported. (CL §16)

**Histogrammer** (the former Plotter, CL §21; [BUGS.md](../Histogrammer/BUGS.md)):

- [x] L13: fixed ROOT detection for production + plots planning and advancement. (CL §16)

**Framework** ([BUGS.md](../Framework/BUGS.md)), registered only:

- [x] K03: `tuples` inputs now select the production stage outputs. (CL §16 step 6)
- [x] K06: `taufw.py plan`/`start` with a recipe path that does not exist ends with a traceback, not one line (`taufw.py check` reports it). Fixed 2026-10-18 (`Recipe.load`).

## 5. PicoProducer: Parts 6 and 7

## 6. Framework

- [x] Sample lists are part of a bundle (CL §20, plan LocalR/architecture/14): templates, model, `--samples`, recipe
      option `samples`. Still apart: the production side's catalogs (`PicoProducer/samples/*.py`). `example_mutau` is
      split into `example_mutau_short` (production only) and `example_mutau_long` (data + 22 MC, then plots). Note:
      `samples_v15.py` has `DYto2TautoMuTauh_M-50` commented out (`:182`, `:215`): the recipe's list must name the
      produced sample.

## 7. Tests

- [x] **Flaky `Tests/Utilities/test_background.py` `test_cancel_stops_a_real_command_and_its_children` (CL §18):**
      fixed 2026-10-18: the test checked the process group at once, while the orphaned child can stay in it until it
      is reaped; it now waits for the group to go (5 s deadline). Confirm on lxplus (§1).

## 8. Legacy code and architecture

## 9. Docs

