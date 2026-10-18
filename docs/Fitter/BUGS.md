# Fitter bug register

Defects in retired workflows are tracked separately in [Legacy/Bugs.md](../../Legacy/Bugs.md).
Latent defects in maintained modules and workflow options remain here.

Defects found while connecting the TES + tau ID fit to the TauFW Framework (Part G, October 2026, branch
`Refactor-2025`). They were found by reading the source of the wrapped workflow: `run_inputs.sh`,
`run_workflow_zmm.sh` and the scripts they call. A bug is fixed when the **Fix** column names the part that fixed it.

Policy (same as [docs/PicoProducer/BUGS.md](../PicoProducer/BUGS.md)): bugs on the path the Framework runs
are fixed and recorded here, with `# BUGS <ID>` comments at the changed lines. Bugs off that path are registered
only. The Fitter has no BBB case, so **Output impact** describes the change for a user of the scripts.

**Severity:**
- **crash:** raises an exception on a reachable path.
- **wrong:** silently produces a wrong result or does the wrong thing.
- **latent:** the code is wrong but nothing reaches it today.

## TES + tau ID workflow (option 3)

| ID | Location | Symptom | Severity | Fix | Output impact |
|---|---|---|---|---|---|
| F01 | `run_workflow_zmm.sh` (merge step) | `merge_tau_jsons.py` is called without `-y`; its default year is `2024` and it filters the input files by year (`merge_tau_jsons.py:208`), so the 2025 merge finds no correction files | wrong | Part G: `-y $YEAR` | `tau_sf/TauCorrections_2025.json` now contains the 2025 corrections (it was empty or held 2024 ones) |
| F02 | `run_workflow_zmm.sh` (last step) | `make_tid_2025.py` is called without `-y`; its default `2025` is right only for 2025 | wrong for other years | Part G: `-y $YEAR` | none for `YEAR=2025` |
| F03 | `run_inputs.sh` (also `run_inputs_2526.sh`, `run_inputs_pnet.sh`) | `STATUS=${PIPESTATUS[0]}` is read after the *unpiped* mumu command, so a failure of the mutau command is ignored (and in `run_inputs_pnet.sh` a mumu failure is ignored) | wrong | Part G: the mutau status is read right after its pipe; a mumu failure counts too | a failed working point is reported and skipped, as the script intended |
| F04 | `TauES_ID/makecombinedfitTES_SF.py` `generate_datacards_mutau`, argument parser | `--input_file` is required but never used: the function looks for `input_file` in `locals()`/`globals()` right after setting it to `None`, so the branch that would pass it on is dead (and `harvestDatacards_TES_idSF_MCStat.py` has no such option, so it would crash) | latent | Part G: the dead branch and the option are removed; callers updated (`run_workflow_zmm.sh`, `Legacy/run_workflow.sh`) | none (the datacards always came from `-i`); `--input_file` is now an unknown option |
| F05 | `TauES_ID/makecombinedfitTES_SF.py` `run_combined_fit` (option 3, parameter file) | If no grid point lies within 1 sigma, `tes_low`/`tid_low` are `None` and `f"{None:.6f}"` raises `TypeError`, so `FitparameterValues_*.txt` is not written and the later steps of that region fail | crash | Part G: the 1-sigma lines are written only when the interval exists | the parameter file exists for every fitted region; regions without an interval have no `_1sigma_low/high` lines (the post-fit step already skips missing lines) |
| F06 | `TauES_ID/makecombinedfitTES_SF_postfit.py` (option 3) | `--impacts` and `--impacts-parallel` are parsed but ignored: the impacts always run (slow) with `--parallel 8` | wrong | Part G: impacts run only with `--impacts`, with `--parallel <--impacts-parallel>`; `run_workflow_zmm.sh` passes `--impacts`, so its output is unchanged | without `--impacts` no `impacts/`, `impacts_*.json` are made |
| F07 | `TauES/createinputsTES.py` (control plots after rebinning) | The rebinned file is read from `<outbase>/rebinning/`, but `python/plot/rebinning.py` writes it next to the input file (`<outbase>/againstjet_<J>/againstelectron_<E>/rebinning/`), so the rebinned control plots open a file that does not exist (the shapes themselves are written before this) | wrong | Part G: the path of `rebinning.py` is used. confirmed on lxplus 2026-10-17: the rebinned control plots appear in `<outbase>/againstjet_<J>/againstelectron_<E>/plots/rebinning/` | rebinned control plots are made; before, the script failed or plotted an empty file after the shapes were written |
| F08 | `TauES_ID/makecombinedfitTES_SF.py` `run_combined_fit` | `merge_datacards_regions` is called with 7 arguments (with `mumu_input_file`) but takes 6 | crash (options 4-6) | registered only (option 3 does not reach it) | |
| F09 | `TauES_ID/makecombinedfitTES_SF.py` `merge_datacards_regions` | `hasattr(setup, 'mumu_datacard_file')` on the setup dict is always false, so the Zmm card is never added | latent (options 4-6) | registered only | |
| F10 | `TauES_ID/makecombinedfitTES_SF.py` `merge_datacards_regions` | the combined card is written to `output_{era}/` instead of the output directory | wrong (options 4-6) | registered only | |
| F26 | `TauES_ID/makecombinedfitTES_SF.py:505` `run_combined_fit` (option 6) | reads `setup['tidRegions']`, but the configs name the key `tid_SFRegions` (the key `harvestDatacards_TES_idSF_MCStat.py` and `plotParabola_POI_region.py` read), so option 6 raises `KeyError` | latent (option 6; the workflow runs option 3) | registered only (plan 16 §8, CL §25) | none |

## Paths and working directory (R3 inventory)

Found while preparing R3 (October 2026): the Framework will run the scripts with the stage's output directory
(`taufw_runs/<run>/stages/<id>/`) as working directory instead of `Fitter/`, so every path that depends on the
working directory or on the module directory was read. **R3** in the Fix column: fixed by R3 without changing what
the shell scripts produce. **After R3**: on the Framework path, but the fix changes the output of the shell scripts,
so it comes in its own commit after the shell/Framework comparison of R3.

| ID | Location | Symptom | Severity | Fix | Output impact |
|---|---|---|---|---|---|
| F11 | `TauES_ID/makecombinedfitTES_SF.py` (end of `run_combined_fit`, lines ~512-515) | `mv higgsCombine*root`, `mv *.root` and `mv *.png` move every such file of the working directory into the output directory of the current working point. The post-fit step leaves `higgsCombine.<label>.FitDiagnostics.mH90.root` and the impact fits `higgsCombine_*Fit_Test*.root` in the working directory, so the fit of the **next** working point moves them into its own output directory | wrong | registered only; after R3 | |
| F12 | `TauES_ID/makecombinedfitTES_SF_postfit.py` (`FitDiagnosticsValues/`, lines ~366-367) -> `plot_measurements.py` (line ~384) | `FitDiagnosticsValues/VSjet<J>_VSele<E>/` has no era, so with two eras in one working directory the measurement plots of one era show the post-fit values of the other. `impacts/`, `impacts_<r>.json`, `output_plots/`, `combined_pre_post/` and `Measurements/` have no era either | wrong | registered only; R3 runs each era in its own directory, which avoids it; script fix after R3 | |
| F13 | `TauES_ID/makecombinedfitTES_SF.py` `merge_datacards_ZmmCR` (line ~158), `TauES_ID/makecombinedfitTES_SF_postfit.py` (line ~69) | the combined card `ztt_mt_m_vis-<region>_zmmCR.txt` has no config tag, so two configs fitted into the same working point directory overwrite each other's card | latent | registered only; after R3 | |
| F14 | `TauES_ID/harvestDatacards_zmm.py` `harvest` / `main` (lines ~32, ~208) | without `-o`, `main` passes `outdir=None` explicitly, so the default `output_pt_less_region/<year>` of `kwargs.get` never applies and the cards are written with an output directory `None` | crash (standalone use) | R3 (CL §17), checked on lxplus: the default applies again | none for the callers, which always pass `-o` |
| F15 | `TauES_ID/makecombinedfitTES_SF.py` (lines ~90, ~544) | the datacard script and the 2D scan plotter are started as `python3 TauES_ID/<script>.py`, relative to the working directory, through `os.system`, whose exit code is ignored. Outside `Fitter/` both fail with "can't open file" and the fit goes on without new cards or scan plots | wrong (outside `Fitter/`) | R3 (CL §17), checked on lxplus: paths from `__file__`; exit codes: TODO §6 B | none in `Fitter/` |
| F16 | `TauES/createinputsTES.py` (line 8) | `sys.path.append("../Plotter/")` is relative to the working directory; outside `Fitter/` `from config.samples_v15 import *` raises `ModuleNotFoundError` | crash (outside `Fitter/`) | R3 (CL §17), checked on lxplus: path from `__file__` | none in `Fitter/` |
| F17 | `make_tid_2025.py` (`SF_DIR`, line 19) | the per-working-point correction files are always read from `Fitter/tau_sf/` (the module directory), with no option, while `createroot_TES.py` writes them to `tau_sf/` of the working directory | wrong (outside `Fitter/`) | R3 (CL §17), checked on lxplus: `--sf-dir` (default unchanged) | none in `Fitter/` |
| F18 | `TauES_ID/makecombinedfitTES_SF.py` (lines ~178, ~574), `TauES_ID/harvestDatacards_TES_idSF_MCStat.py` (line ~59), `TauES_ID/plot2DScan_MultiDimFit.py` (lines ~602, ~999, ~1276), `TauES_ID/makecombinedfitTES_SF_postfit.py` (lines ~92, ~266) | output directories are derived from input directories with `str.replace('input', 'output')`, `('output', 'plots')`, `('output', 'postfit')` and `('postfit', 'output')` on the **whole** path. `plot2DScan_MultiDimFit.py` already gets an absolute path (`os.path.abspath` in `makecombinedfitTES_SF.py`), so any `output` elsewhere in that path (a user or run directory) sends the scan plots to a different, newly created tree | latent | partly, R3 (CL §17), checked on lxplus: with `--output_dir`/`--plot_dir`/`--outdir` (the Framework always passes them) the derivation is not used; without them it stays | |
| F19 | `createroot_TES.py` (lines ~197-206, ~460-464, ~545-548) | if no `FitparameterValues_*` file is found, the correction files are written with every scale factor 1.0, and the script exits 0 | wrong | registered only; after R3 | |
| F20 | `merge_tau_jsons.py` (lines ~148-150, ~212), `plot_measurements.py` (lines ~711-713) | when nothing is found the scripts print a message and exit 0 without writing their output | wrong | registered only; after R3 | |
| F21 | `make_measurements_grid.py` (`--dir`, line ~50) vs `plot_measurements.py` (line ~707) | the grid reads `Measurements/` next to the script (module directory), `plot_measurements.py` writes it in the working directory; consistent only when the working directory is `Fitter/` | latent | R3 (CL §17), checked on lxplus: the API passes `--dir` | |
| F22 | `python/api/tes_id.py` `_correction_glob` | `tau_sf/*_<era>_VSjet<J>_VSele<E>.<form>` also matches the files of other taggers (PNet, UParT), so they are listed in the fit artifact | wrong (artifact list) | R3 (CL §17), checked on lxplus: the glob is `tau_sf/*_SF_dm_DeepTau*_<era>_VSjet<J>_VSele<E>.<form>` | the fit artifact lists only DeepTau files |
| F23 | `python/plot/runpostfit.py` (line ~45) | the post-fit file name has `__mutau_` hard-coded instead of the config's tag, so a config with another tag fails to open its post-fit shapes | latent | registered only | |
| F24 | `tau_tid_2024.py` `makecorr_tid` (lines ~395-421), through `make_tid_2025.py` | if no per-working-point file is found, `makecorr_tid` takes its "test format with dummy values" branch (Loose/Medium, SF 1.0 +- 0.2) instead of failing; what it writes then is not yet checked on lxplus | wrong | registered only; after R3 | |
| F25 | `python/api/tes_id.py` `TauESID.__init__` (default `find_module`), used by `preflight_shapes` and `preflight_fit` (`_environment`, CombineHarvester check) | the same as Plotter L13: `importlib.util.find_spec('ROOT')` raises `ValueError: ROOT.__spec__ is None` when CMSSW's ROOT is already imported in the process (e.g. after a production stage, or after the plots stage's own checks). The histograms and fit stages then raise at preflight | crash | CL §18 (exception to the no-fix rule: it blocked every recipe with production and plots on lxplus): `_module_exists`, a module already imported counts as found | none: the preflight answers instead of raising |

## How old

Open bugs only; fixed ones are left out.

- **F08** The 7-argument call has been broken since commit `f0f75f3` (2025-10-24, "2D fit"). That commit added
  `mumu_input_file` support (a new optional argument of `merge_datacards_ZmmCR` and `mumu_input_file = kwargs.get(...)`
  in `run_combined_fit`), and added `mumu_input_file` to the `merge_datacards_regions(...)` call without changing that
  function's 6-argument signature. `f66a886` (2025-12-04) then passed `mumu_input_file=args.mumu_datacard_file` from
  `main`, still without fixing the signature. Options 4-6 have raised `TypeError` ever since. Nobody noticed because
  every driver (`run_workflow*.sh`, `api/tes_id.py`) runs option 3 only.
- **F09** The `hasattr(setup, 'mumu_datacard_file')` check has been broken since the day it was written: commit
  `5a08f58` (2025-09-26, "2D parabola"). That commit replaced the old `if str(config_mumu) != 'None':` Zmm-CR branch
  (left behind as a comment) with this check, and set `setup['mumu_datacard_file']` in `main`. `setup` is a dict
  loaded from YAML, so `hasattr` on a key is always false and the Zmm card was never added. Nobody noticed because
  only options 4-6 reach this code, and since `f0f75f3` they crash first (F08).
- **F10** The `output_{era}/` path is older than the output-directory option. It goes back to the first commit of
  the folder, `2c8819e` (2022-11-09, "TauES_ID folder containing code to to do the combined fit of TES and ID SF"),
  and became `merge_datacards_regions` in `6dc9a0a` (2023-07-06, "update of the combined fit script, option to
  include Zmm CR"). Back then everything used `output_{era}`, so it was correct. It became wrong with `9ebb7a0`
  (2024-06-19, "introduce input and output directory separate for different wps of against jet and against
  electron"), which made `run_combined_fit` read `{output_dir}/{datacardfile}.txt` but left this function writing to
  `output_<era>/`. `5a08f58` (2025-09-26) moved the regions-only card to `output_dir` but kept the combined card in
  `output_{era}/`. Nobody noticed because the line sits behind the always-false F09 check, and options 4-6 crash
  first anyway (F08).
- **F11** `9ebb7a0` (2024-06-19, "introduce input and output directory separate for different wps of against jet and
  against electron") added the `mv` lines when the output directory per working point came in. The stray files they
  now pick up came later: `FitDiagnostics` and the impacts in the working directory with the post-fit script of
  `5a08f58` (2025-09-26, "2D parabola") and `7360158` (2025-10-03, "Fitter upgrade 2D").
- **F12** `FitDiagnosticsValues/VSjet<J>_VSele<E>/` was introduced in `f66a886` (2025-12-04, "Full Fitter +
  Plotter, ..."), already without the era. Every driver runs one era at a time in `Fitter/`, so it never showed.
- **F13** The `_zmmCR` card name is from `6dc9a0a` (2023-07-06, "update of the combined fit script, option to include
  Zmm CR"), when there was one config.
- **F14** `outdir=args.output_dir` is from `9ebb7a0` (2024-06-19); every caller since passes `-o`.
- **F15** The relative `TauES_ID/harvestDatacards_TES_idSF...` call is in the first commit of the folder, `2c8819e`
  (2022-11-09); the `python3 TauES_ID/plot2DScan_MultiDimFit.py` call came with `7360158` (2025-10-03). Correct as
  long as everything runs in `Fitter/`.
- **F16** `sys.path.append("../Plotter/")` came with `007966c` (2022-01-14, "Some local changes and bug fixes (?)
  ..."); correct as long as the script runs in `Fitter/`.
- **F17** `SF_DIR` next to the script is from `7589a86` (2026-05-19, "1D plotting and corrlib file maker"), which
  also brought the dummy branch of F24.
- **F18** `input_dir.replace('input', 'output')` is from `9ebb7a0` (2024-06-19); `indir.replace('output', 'plots')`
  and `fit_outdir.replace("output", "postfit")` from `5a08f58` (2025-09-26); `param_file.replace("postfit",
  "output")` from `7360158` (2025-10-03). All assume a relative path whose only `input`/`output` is the first
  component.
- **F19** The glob of `FitparameterValues_*_DeepTau_*` with its 1.0 default came with `feb8ebd` (2025-12-05, "update
  to new file structure").
- **F20** `plot_measurements.py`'s "No measurements found!" return is from `aa0b1a1` (2025-10-29, "plotter").
- **F21** `make_measurements_grid.py` came with `7a2875c` (2026-05-15, "Refactor workflow scripts and add grid
  generation ..."), with the module directory as default.
- **F22** `_correction_glob` came with the Fitter API, `c27abb7` (2026-10-13, Part G).
- **F23** `__mutau_` is from `27f31c6` (2025-10-20, "postfit Zmm plots").
- **F24** see F17: `7589a86` (2026-05-19).
- **F26** `tidRegions` came with option 6, `6dc9a0a` (2023-07-06); found in the step-2 planning (plan 16, CL §25).
