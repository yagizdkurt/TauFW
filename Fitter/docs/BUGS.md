# Fitter bug register

Defects found while connecting the TES + tau ID fit to the TauFW Framework (Part G, October 2026, branch
`Refactor-2025`). They were found by reading the source of the wrapped workflow: `run_inputs.sh`,
`run_workflow_zmm.sh` and the scripts they call. A bug is fixed when the **Fix** column names the part that fixed it.

Policy (same as [PicoProducer/docs/BUGS.md](../../PicoProducer/docs/BUGS.md)): bugs on the path the Framework runs
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
