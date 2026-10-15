# Script option changes for per-run output directories (R3)

**Status:** implemented (October 2026, CL §17 of [Refactor-2025.md](Refactor-2025.md)); the lxplus comparison
with the shell scripts (below) is pending.

Since R3 the Framework runs the Plotter and Fitter scripts with the stage's output directory
(`taufw_runs/<run>/stages/<id>/`, for the fit `<...>/stages/<id>/<era>/`) as working directory. The Framework gives
the API the output directory and the inputs (taken from the artifacts of the input stages); the API passes them to
the scripts. There are no links or copies.

## Rules

- What a script reads or writes **relative to its working directory** belongs to the stage's own directory and
  needs no option.
- An option is added only where a script
  1. reads from outside the stage: another stage's output (the shapes) or its own module directory;
  2. derives an output directory from an input directory (`str.replace('input', 'output')`): the input now lives in
     another stage, so the output would go there;
  3. runs `str.replace` on an absolute path (any `output` elsewhere in the path moves the output).
- New options are long options only (`-o` already means "option" in some scripts), default `None`. With the
  default the script behaves exactly as before, so the shell scripts (`run_inputs.sh`, `run_workflow_zmm.sh`) and
  standalone use do not change. When the option is given, the old derivation is not used at all.
- These are refactorings, not bug fixes. The bugs they make harmless are referenced by ID
  ([Fitter BUGS](../Fitter/BUGS.md), [Plotter BUGS](../Plotter/BUGS.md)); `# BUGS <ID>` comments mark only real fixes.

## New options

| Script | Option | Default (unchanged behaviour) | Why (rule) | Passed by | Status |
|---|---|---|---|---|---|
| `Fitter/TauES_ID/makecombinedfitTES_SF.py` | `--output_dir DIR` | `input_dir.replace('input', 'output')` + era | 2 (F18) | `api/tes_id.py` fit step | done |
| | `--plot_dir DIR` | `output_dir.replace('output', 'plots')` in `plot2DScan_MultiDimFit.py` | 3 (F18) | same | done |
| | (passes them on) | `harvestDatacards_TES_idSF_MCStat.py --output_dir`, `plot2DScan_MultiDimFit.py --outdir` | | | done |
| `Fitter/TauES_ID/harvestDatacards_TES_idSF_MCStat.py` | `--output_dir DIR` | `input_dir.replace('input', 'output')/<era>` | 2 (F18) | `makecombinedfitTES_SF.py` | done |
| `Fitter/TauES_ID/plot2DScan_MultiDimFit.py` | `--outdir DIR` | `indir.replace('output', 'plots')` | 3 (F18) | `makecombinedfitTES_SF.py` | done |
| `Fitter/make_tid_2025.py` | `--sf-dir DIR` | `<module dir>/tau_sf` | 1 (F17) | `api/tes_id.py` summary step | done |

## Existing options the API starts to pass

| Script | Option and value | Why |
|---|---|---|
| `Fitter/TauES_ID/harvestDatacards_zmm.py` | `-i <shape directory from the shapes artifacts>` (absolute) | rule 1 |
| `Fitter/make_measurements_grid.py` | `--dir Measurements` (relative to the working directory) | rule 1 (F21) |
| `Fitter/make_tid_2025.py` | `--out data/tau/TauCorrections_<era>_with_uncorrelated_systs.json` | rule 1 |

The API passes all of these only with an output directory; without one it runs the scripts exactly as the shell
scripts do. With one it also gives every script and config as an absolute path, keeps the directories inside the
working directory relative (`--indir`, `--scan_dir`, `--root`, `-o tau_sf/...`, as in the shell script), and makes
`make_tid_2025.py --out` its directory first (it no longer makes `data/tau/` next to itself when `--out` is given).

## Path fixes (no option)

| Script | Change | Bug |
|---|---|---|
| `Plotter/plot.py` | `mapDecayModes.C` found from `__file__` | L11 |
| `Fitter/TauES/createinputsTES.py` | `../Plotter` found from `__file__` | F16 |
| `Fitter/TauES_ID/makecombinedfitTES_SF.py` | the two `python3 TauES_ID/<script>.py` calls use the script's own directory | F15 |
| `Fitter/TauES_ID/harvestDatacards_zmm.py` | without `-o`, the default output directory applies again | F14 |

## Scripts that need nothing

They run in the stage's directory and only use paths inside it: `Plotter/plot.py` (`plots/<era>/`),
`TauES/createinputsTES.py` (`input_pt_less_region/...`), `makecombinedfitTES_SF_postfit.py` (`--indir` relative),
`python/plot/runpostfit.py`, `pre_post_plot_combiner.py`, `plot_measurements.py`, `createroot_TES.py`,
`make_scan_grid.py`, `merge_tau_jsons.py`, `plot1D_NLL_profiles.py`.

## Verification on lxplus

For every changed script: the shell scripts run with the defaults before and after the change give the same
files, and the Framework run gives the same results as the shell scripts. Results are recorded here per step.
