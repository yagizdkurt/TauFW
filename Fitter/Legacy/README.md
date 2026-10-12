# Fitter legacy area

This folder holds Fitter scripts that are broken, superseded, or no longer used by any workflow.
They were moved here on 2026-10-13 instead of being deleted (see
[docs/Refactor-2025.md](../../docs/Refactor-2025.md#8-fitter-cleanup-legacy-area)). Each file keeps its original
path relative to `Fitter/`, so `Legacy/TauES/doTES.sh` was `TauES/doTES.sh`.

**These files are not maintained.** Many did not run even before the move. Relative paths, `#include`s and
same-directory imports such as `from utils import *` were **not** updated, so a script may also fail from its new
location. If you need one, move it back and fix it first.

Unused modules from the `TauFW.Fitter` Python package are in [../python/legacy/](../python/legacy/) instead, where they
can still be imported as `TauFW.Fitter.legacy.*`.

## Contents

| File | Why it is here | Use instead |
| --- | --- | --- |
| `createJSON_TES.py` | Imports `fit_tools`, which does not exist | `createroot_TES.py -f json` |
| `run_createroot_TES.py` | 2023C/D driver; uses `jet_wp`, which is never defined | `run_workflow_zmm*.sh` (step 4) |
| `run_workflow.sh` | 2024 driver from before the Z→μμ control region | `run_workflow_zmm*.sh` |
| `TauES/doTES.sh` | TES-only workflow; points at the missing `Fitter/analysis/TauES` and at removed scripts | `run_workflow_zmm*.sh` |
| `TauES/harvestDatacards_TES.py` | Called only by `doTES.sh` | `TauES_ID/harvestDatacards_TES_idSF_MCStat*.py` |
| `TauES/run_createinputsTES.py` | Old input driver | `run_inputs*.sh` |
| `TauES/config/defaultFitSetupTES_mutau_v10_2p5.yml` | Not referenced | `TauES_ID/config/config_coarse_*.yml` |
| `TauES/correctionlib/tau_createJSONsTauES.py`, `tau_tes.py` | Run-2 (2021) TES JSON/ROOT makers. Their `utils.py` stays in `TauES/correctionlib/`, because `tau_tid_2024.py` uses it | `createroot_TES.py`, `make_tid_2025.py` |
| `TauES_ID/saveSFs_root_JSON.py` | Calls `saveSFs_root.py`, which does not exist | `createroot_TES.py` |
| `TauES_ID/config/Default_FitSetupTES_mutau_DM_mt40_JetM_muVT.yml` | Used only by `saveSFs_root_JSON.py` | — |
| `TauES_ID/config/Default_FitSetupTES_mutau_DM_pt.yml` | Not referenced | `TauES_ID/config/config_coarse_*.yml` |
| `TauES_ID/printParamWorkspace.py` | Its docstring says it was not used for the results | — |
| `TauES_ID/WriteSFsFit.py`, `TauES_ID/shape_syt.py` | 2023 one-off helpers for a postfit plotter that no longer exists | `python/plot/runpostfit.py` |
| `TauES_ID/run_makecombinedfitTES_SF.py` | Old fit driver | `run_workflow_zmm*.sh` |
| `TauES_ID/plot2DParabola_FitDiagnostics.py` | Not referenced | `TauES_ID/plot2DScan_MultiDimFit.py` (called by the fit scripts) |
| `scripts/plotBiasTest.py`, `scripts/plotChannelCompatibility.py` | Python 2 (`SyntaxError` in Python 3); not referenced | — |
| `scripts/pulls.py` | Used only by `doTES.sh` | combine's `diffNuisances.py` + `scripts/plot_pulls.py` |
| `scripts/project_bins.py` | 2021 one-off study; not referenced | — |
| `ETauFR/Fitting.sh` | The "--OLD--" flow in the ETauFR README; calls the removed `compare.py` | `ETauFR/runAll_combFit.sh` |
| `ETauFR/runAll.sh`, `doImpacts.sh`, `doImpacts2.sh`, `doFitPlots.sh` | The eta-only fit flow | `ETauFR/runAll_combFit.sh`, `doFitsAndImpacts_combFit.sh` |
| `ETauFR/text2wp.sh` | Hardcoded 2022_postEE copy of the commands that `text2wp.py` runs | `ETauFR/text2wp.py` |
| `ETauFR/Plotter/PlotShapes.C`, `FastPlot.sh` | Marked "deprecated" in the ETauFR README | `ETauFR/Plotter/plotpostfit.py` |
| `HighPT/combine_logger.out` | Combine log output that was committed by mistake | — |
| `TauID/takeZmu.py` | `IndentationError`; not referenced | — |
| `paper/postfit.sh` | Calls the removed `writecards.py` | — |
| `../python/legacy/models/TagAndProbeModel.py` | Not referenced | — |
