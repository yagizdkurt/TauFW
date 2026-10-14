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
| F07 | `TauES/createinputsTES.py` (control plots after rebinning) | The rebinned file is read from `<outbase>/rebinning/`, but `python/plot/rebinning.py` writes it next to the input file (`<outbase>/againstjet_<J>/againstelectron_<E>/rebinning/`), so the rebinned control plots open a file that does not exist (the shapes themselves are written before this) | wrong | Part G: the path of `rebinning.py` is used. **To confirm on lxplus** that the rebinned control plots appear in `plots/rebinning/` | rebinned control plots are made; before, the script failed or plotted an empty file after the shapes were written |
| F08 | `TauES_ID/makecombinedfitTES_SF.py` `run_combined_fit` | `merge_datacards_regions` is called with 7 arguments (with `mumu_input_file`) but takes 6 | crash (options 4-6) | registered only (option 3 does not reach it) | |
| F09 | `TauES_ID/makecombinedfitTES_SF.py` `merge_datacards_regions` | `hasattr(setup, 'mumu_datacard_file')` on the setup dict is always false, so the Zmm card is never added | latent (options 4-6) | registered only | |
| F10 | `TauES_ID/makecombinedfitTES_SF.py` `merge_datacards_regions` | the combined card is written to `output_{era}/` instead of the output directory | wrong (options 4-6) | registered only | |

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
