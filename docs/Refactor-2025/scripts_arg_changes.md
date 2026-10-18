# Script option changes for per-run output directories (R3)

**Status:** implemented and checked on lxplus against the shell scripts (October 2026, CL §17 of
[Refactor-2025.md](Refactor-2025.md); results below).

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
  ([Fitter BUGS](../Fitter/BUGS.md), [Histogrammer BUGS](../Histogrammer/BUGS.md) (the former Plotter BUGS)); `# BUGS <ID>` comments mark only real fixes.

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
Tuples: `/eos/cms/store/group/phys_tau/TauFW/pico2024/TES_variations/$ERA/$GROUP` (2025, mutau and mumu, with the
TES/LTF/JTF variations). Baseline commit: `f951dc0` (the last one with the scripts unchanged).

- **Plotter (2026-10-15):** `plot.py -y 2025 -c mutau|mumu -V m_vis pt_2 -S baseline` in `Plotter/`: the same 8 files
  before and after (mutau rerun only; the macro is loaded for tau channels only). Framework run of a plots stage with
  `variables: [m_vis, pt_2, dm_2_label]`: the same files in `stages/plots/plots/2025/` plus
  `dm_2_label_mt-baseline-2025.png` (`mapRecoDM`, so the macro loads outside `Plotter/`, L11); `nfiles` 5 (mutau) and
  4 (mumu) equal the files; nothing written to `Plotter/plots/`; no errors in the logs. `bbb check`: 20 cases, 0
  failed.
- **Fitter (2026-10-15/16), VTight/Tight, 2025:**
  - Baseline at `f951dc0`: `run_inputs.sh` (2 h 48 min) and `run_workflow_zmm.sh` restricted to VTight/Tight (18 min).
  - New code, shell scripts with the defaults, on the baseline shapes: all 12 `FitparameterValues__mutau_*`, the two
    `tau_sf/*VSjetVTight_VSeleTight*.json`, `tau_sf/TauCorrections_2025.json` and
    `data/tau/TauCorrections_2025_with_uncorrelated_systs.json` identical to the baseline.
  - Framework run (histograms + fit, `inputs: {shapes: histograms}`): every command ok. The shapes equal the baseline
    up to a relative 1e-13 (RDataFrame with 16 threads adds weighted histograms in a different order on every run;
    unweighted ones such as `data_obs` are identical), and the tuples did not change in between.
  - The fit is very sensitive to that: the fitted POIs move by at most one grid step (0.00125 in tes), most only in
    the 4th-6th decimal, while nuisance parameters along flat directions move a lot. So the Framework fit was also
    compared with the shell scripts run on the **Framework's** shapes: all 12 `FitparameterValues__mutau_*` and the
    merged and combined JSONs are identical. The fit commands of the API do what the shell script does.
  - Isolation: nothing written to `Fitter/` or `Plotter/`; nothing in the histograms stage changed after its
    manifest (the fit reads the shapes in place); `stages/fit/` holds `2025/` and `manifest.json`; the impacts of
    DM11_pt2 failed in the baseline (initial fit did not converge, `combineTool.py` traceback inside `os.system`,
    the script still exits 0) and succeeded in the Framework run, again because of the 1e-13 shape differences.

## Tuple location (CL §18)

**Status:** steps 2, 3 and 6 of the tuple-location work (`LocalR/architecture/archive/12-tuples-plan.md`): the options
exist, the APIs pass them (`PlotsRequest.tuples`, `ShapesRequest.tuples`) and the Framework gives them (plots and
histograms: the pattern of the production stage their input names, or `{external: <pattern>}`).
`Tests/Plotter/testTupleLocation.py` passes on lxplus.

The scripts found the tuples through `$PICODIR` of the PicoProducer configuration (`$TAUFW_PICO_CONFIG` or
`PicoProducer/config/config.json`). With these options the caller gives the directory instead (rule 1: the tuples
are another stage's output, or made outside TauFW). The file names inside it stay the library's convention:
`<sample>_<channel>.root`, the data a glob of sample names, the variations `<sample>_<channel>_<shift>.root` in the
same directory.

| Script / function | Option | Default (unchanged behaviour) | Status |
|---|---|---|---|
| `Plotter/python/sample/utils.py` `getsampleset` | `tuples=PATTERN` (keyword) | `$PICODIR` of the PicoProducer configuration (`getconfig()['picodir']`) | done |
| `Plotter/plot.py` | `--tuples PATTERN` | same (passes `tuples=None`) | done |
| `Fitter/TauES/createinputsTES.py` | `--tuples PATTERN` | same | done |

- `PATTERN` is a directory pattern with `$ERA` and `$GROUP`, e.g.
  `--tuples '/eos/cms/store/group/phys_tau/TauFW/pico2024/TES_variations/$ERA/$GROUP'` (single quotes: the shell
  must not expand the `$`).
- With the option, the PicoProducer configuration is not read at all (no `TauFW.PicoProducer` import there).
  The APIs then pass no `$TAUFW_PICO_CONFIG` and do not check the configuration; their preflight refuses a
  relative pattern (with an output directory) and `$KEYS` other than `$ERA`, `$GROUP`, `$SAMPLE`, `$CHANNEL`,
  `$TAG`, e.g. `$DAS`, which only PicoProducer fills (`TauFW.Utilities.Process.tuple_pattern_problems`).
- Not through `fname` / the YAML `samples.filename`: those are ignored today (Plotter BUGS L02), and stay so.
- Every sample config that passes `**kwargs` on to `getsampleset` (`samples_v15.py`, `samples.py`, ...) supports
  the keyword without a change. `getmcsample` (L12) is not changed.
- Test: `Tests/Plotter/testTupleLocation.py` (ROOT; tiny local tuples: MC, merged data glob, a variation, and the
  default through a mocked configuration).

## Sample model files (CL §22)

**Status:** steps S3-S5 of the sample model (`LocalR/architecture/archive/14-sample-model-plan.md`): the options exist, the
APIs pass them (`PlotsRequest.samples`, `ShapesRequest.samples`) and the Framework gives them (the `samples` option of
plots and histograms).

The scripts took their samples (MC table, cross sections, data datasets, MC weights, stitching, joins) from the
tables of `Plotter/config/samples_v15.py`. With this option the caller names sample model files instead: YAML
templates of `Configs/Plotter/samples/` (one per era, exported from those tables), or a bundle's copy. The file whose
`era` is the era of the run is used; none or two for an era is an error.

| Script / function | Option | Default (unchanged behaviour) | Status |
|---|---|---|---|
| `Plotter/config/samples_v15.py` `getsampleset` | `samples=[FILE, ...]` (keyword) | its own tables | done |
| `Plotter/plot.py` | `--samples FILE [FILE ...]` | same (passes `samples=None`) | done |
| `Fitter/TauES/createinputsTES.py` | `--samples FILE [FILE ...]` | same | done |

- With the option, the SampleSet gets exactly the calls the tables would make for the same era
  (`Tests/Plotter/sample_model`, BBB `plotter.sample_model`), except the debug print of the data dataset for
  `2022_preEE` muon channels.
- `createinputsTES.py` keeps importing `config.samples_v15` (known import debt): the option goes through that
  function, so the Fitter imports nothing new.

## Channel setups in Configs (CL §22, S7)

The channel setups moved from `Plotter/config/setup_<channel>.yml` to `Configs/Plotter/setups/setup_<channel>.yml`
(config templates with a `taufw_config` header; the scripts ignore that key).

| Script | Change |
|---|---|
| `Plotter/plot.py`, `plot_postfit.py`, `plot_postfit_shift.py`, `plot_v10.py` | `-c <channel>` reads `Configs/Plotter/setups/setup_<channel>.yml` (found from the script's own directory, not the working directory); the default `-c` is the channel name (`mutau_inclusive` for `plot.py`, `mutau` for the others), the same file as before |
| `TauFW.Plotter.api.ControlPlots` | a channel name resolves to the same file; the "not found" messages give the absolute path |

- Not kept: `-c config/setup_mutau.yml` (an explicit path to the old place) no longer exists. Use the channel name
  (`-c mutau`) or the new path. `Plotter/tutorial/` keeps its own `config/setup_mutau.yml`.

## Plotter becomes Histogrammer (changelog §24, S1)

The module directory `Plotter/` is now `Histogrammer/`; a new `Plotter/` keeps the old names working until the
migration point (TODO §8). Options, defaults and outputs of every script are unchanged.

| Before | Now | Old name |
|---|---|---|
| `python3 Plotter/plot.py ARGS` | `python3 Histogrammer/fillhists.py ARGS` (same options; `prog` in `-h` is `fillhists`) | `Plotter/plot.py` and `Histogrammer/plot.py` print the new command and exit with status 2 (nothing runs) |
| `Plotter/plot_postfit.py`, `plot_postfit_shift.py`, `plot_v10.py`, `tutorial/plot.py` | the same names in `Histogrammer/` | none |
| `TauFW.Plotter.sample.*`, `.plot.*`, `.methods.*` | `TauFW.Histogrammer.sample.*`, `.spec.*` (`MultiDraw`: `.sample.MultiDraw`), `.methods.*` | alias modules in `Plotter/python/` (same module objects) |
| `TauFW.Plotter.api` | `TauFW.Histogrammer.api` | none (only the Framework used it) |
| `sys.path.append(".../Plotter")` + `from config.samples* import *` | `.../Histogrammer` (the 6 Fitter `createinputs*.py` are updated) | none |
| `Plotter/python/macros/*.C`, `Unroll.cxx`, `python/corrections/*.C` | `Histogrammer/python/...` (`Fitter/Zpt` updated) | none |
| `$CMSSW_BASE/src/TauFW/Plotter/data/ff_HighPT/` (written and read by `Fitter/HighPT`) | `.../Histogrammer/data/ff_HighPT/` | none |
| `docs/Plotter/BUGS.md` | `docs/Histogrammer/BUGS.md` (same IDs) | none |

### Configs (S2)

| Before | Now | Old name |
|---|---|---|
| `Configs/Plotter/samples/v15_<era>.yml` (id `plotter.samples_v15_<era>`) | `Configs/Histogrammer/samples/` (id `histogrammer.samples_v15_<era>`; values and versions unchanged) | a bundle copy with the old id is compared with the renamed template and gets a warning to change its `id` line |
| `Configs/Plotter/setups/setup_<channel>.yml` (id `plotter.setup_<channel>`) | `Configs/Histogrammer/setups/` (id `histogrammer.setup_<channel>`) | same |
| `fillhists.py -c <channel>`, the API and the Framework resolve a channel name to `Configs/Plotter/setups/` | `Configs/Histogrammer/setups/setup_<channel>.yml` | none |

### Histogram file and draw.py (S3)

| Script | Change | Default (unchanged behaviour) |
|---|---|---|
| `Histogrammer/fillhists.py` | new option `--hists`: also writes the filled histograms of every plot to `hists/<era>/<channel><tag>.root` ([contract](../contracts/control-histograms.md)), copied before they are drawn | without it nothing changes (no file, the same plots and log) |
| `Plotter/draw.py` (new) | `draw.py FILE [FILE ...] [-o OUTDIR] [-F] [-p] [-T TEXT] [-v]`: draws the plots of such files, with the file names and texts of `fillhists.py` | `-o plots/$ERA` |

### Framework stages controlhists and controlplots (S4)

| Script / recipe | Change | Default (unchanged behaviour) |
|---|---|---|
| `Histogrammer/fillhists.py` | new option `--no-draw` (only with `--hists`, else an error): writes the file and draws nothing (no `plots/` directory); `-F`, `-p`, `-T` are then ignored with a warning | without it nothing changes: fills and draws as before |
| recipe `stage: histograms` | renamed `stage: shapes` (S4a; options, commands and shapes unchanged) | none: the old name fails the check with a message (no recipe users yet) |
| recipe `stage: plots` | two stages: `controlhists` (tuples -> files, `fillhists.py --hists --no-draw`; the options that change the histograms) and `controlplots` (files -> plots, `Plotter/draw.py`; `fraction`, `pdf`, `text`) | none: the old name fails the check with a message; runs started before cannot be continued |
| `TauFW.Histogrammer.api.ControlPlots`, `PlotsRequest` | renamed `ControlHists`, `HistsRequest` (no `fraction`, `pdf`, `text`); the artifact is the file (`kind: control_histograms`) | none (only the Framework used it) |
| `TauFW.Plotter.api` (new) | `ControlPlots`, `PlotsRequest`, `HistFileInput`: `draw.py` once per file | - |

## TES shapes move to the Histogrammer (changelog §25, H1)

The scripts that make input shapes import nothing of the fit; they moved to `Histogrammer/shapes/`, unchanged except
for their import lines. They are run from the same directories as before, so relative config paths and the outputs
stay where they were.

| Before | Now | Old name |
|---|---|---|
| `cd Fitter; python3 TauES/createinputsTES.py ARGS` | `cd Fitter; python3 ../Histogrammer/shapes/TauES/createinputsTES.py ARGS` (same options; the shapes still land in `Fitter/input_pt_less_region/`); `run_inputs.sh`, `run_inputs_2526.sh`, `run_inputs_pnet.sh` and the Fitter API call the new path | `Fitter/TauES/createinputsTES.py` prints the new command and exits with status 2 (nothing runs) |
| `cd Fitter/<Variant>; python3 createinputs.py ARGS` (ETauFR, HighPT, paper, tutorial) | `cd Fitter/<Variant>; python3 ../../Histogrammer/shapes/<Variant>/createinputs.py ARGS` | `Fitter/<Variant>/createinputs.py` prints the new command and exits with status 2 |
| `TauFW.Fitter.plot.datacard` (`createinputs`, `plotinputs`, ...) | `TauFW.Histogrammer.shapes.inputs` | none (an alias in the Fitter would import the Histogrammer) |
| `TauFW.Fitter.plot.rebinning` | `TauFW.Histogrammer.shapes.rebinning` | none |
| `Fitter/MuTauFR/createinputs.py` | unchanged (its import `TauFW.Plotter.plot.datacard` was already broken, TODO §8) | - |

## TES/ID channel configs to Configs/ (changelog §25, H2)

The four maintained channel configs of the TES + tau ID fit are templates now: `Configs/Fitter/tes_id/` (ids
`fitter.tes_id_coarse_tt`, `_coarse_pnet`, `_coarse_upart`, `fitter.tes_id_mumu`). Same values (`yaml.safe_load` of
each file is unchanged apart from the new `taufw_config` header); the top-level keys are grouped under banners by
reader, and the `&region_list` anchor is defined on `observables.m_vis.fitRegions` (it was on `plottingOrder`, which
now takes the alias: the same list).

| Before | Now | Old name |
|---|---|---|
| `-c TauES_ID/config/config_coarse_TT.yml` (from `Fitter/`), also `_PNet`, `_UParT` | `-c ../Configs/Fitter/tes_id/config_coarse_TT.yml` (`run_inputs*.sh`, `run_workflow_zmm*.sh`) | none: the old path is "file not found" |
| `-cmm TauES/config/FitSetup_mumu.yml` | `-cmm ../Configs/Fitter/tes_id/FitSetup_mumu.yml` | none |
| default `-c` of `plot2DScan_MultiDimFit.py`, `makecombinedfitTES_SF_postfit_corrTES.py` | `../Configs/Fitter/tes_id/config_coarse_TT.yml` (the same file from `Fitter/`) | - |
| recipe `config: TauES_ID/config/config_coarse_TT.yml` (module path) | `config: Configs/Fitter/tes_id/config_coarse_TT.yml` (a template, resolved by the Framework) or a bundle copy | none: the old path fails the recipe check with the template's name |
| `shapes.configs` / `fit.config` / `fit.config_mumu` defaults | the templates | - |

Not moved (internal, still in `Fitter/TauES*/config/`): `defaultFitSetup*.yml`, `Default_FitSetupTES_mutau_DM*.yml`,
`config_tests.yml`.
