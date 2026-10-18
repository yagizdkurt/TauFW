# 2D TES/TauID Fit - Quick Start Guide

## Overview
This guide shows how to run the 2D TES/TauID fits using the automated shell scripts in the Fitter directory.

## Quick Start (3 steps)

### 1. Generate Input Files
```bash
cd ../  # Go to Fitter directory
bash run_inputs.sh
```
This creates input histograms for all working point combinations. Check logs for success.

### 2. Run Full Fit Workflow
```bash
bash run_workflow_zmm.sh
```
This runs the complete analysis pipeline for all jet/electron working point combinations:
- **Step 1:** MultiDimFit (scan over TES/ID parameters)
- **Step 2:** FitDiagnostics + PostFit pulls
- **Step 3:** Generate plots
- **Step 4:** Create correction files (ROOT + JSON)

### 3. Collect Results
Output is organized by working point:
```
output_pt_less_region/againstjet_[JET_WP]/againstelectron_[ELE_WP]/
plots_pt_less_region/againstjet_[JET_WP]/againstelectron_[ELE_WP]/
tau_sf/TauCorrections_2024.json  (merged result)
```

## Configuration Files
- **TES/TauID config:** `../Configs/Fitter/tes_id/config_coarse_TT.yml` (the template `Configs/Fitter/tes_id/`; `TauES_ID/config/` until changelog §22)
- **Mumu CR config:** `../Configs/Fitter/tes_id/FitSetup_mumu.yml`
- **Year:** 2024 (edit scripts to change)

## Working Points
- **Jet WPs:** VTight, VVLoose, VLoose, Loose, Medium, Tight
- **Electron WPs:** VVLoose, Tight

Edit `run_inputs.sh` and `run_workflow_zmm.sh` to modify which combinations to process.

## Tips
- Logs are created with timestamps: `step*_[JET_WP]_[ELE_WP].log`
- For single working point: modify `J_VALUES` and `E_VALUES` arrays in scripts
- Final JSON corrections are merged in `tau_sf/TauCorrections_2024.json`

## Correlated-TES variant (`_corrTES`)

Same 4-step pipeline, but **one TES POI per DM correlated across the 3 pT bins** (TauID stays per `(DM, pT)`). Use the parallel scripts and outputs:

- **Workflow script:** `run_workflow_zmm_corrTES.sh` (instead of `run_workflow_zmm.sh`)
- **Fit script:** `TauES_ID/makecombinedfitTES_SF_corrTES.py` — option-3 runs 3 2D scans per DM, each scanning `(tes_DM, tid_SF_DM_pt<N>)` while profiling the other 2 TauID POIs. Per-DM cards are built by `combineCards.py`, so the shared `tes_DM<X>` name enforces correlation across pT.
- **Postfit:** `TauES_ID/makecombinedfitTES_SF_postfit_corrTES.py` — `FitDiagnostics` over all 4 POIs joint.
- **JSON:** `python3 make_tid_2025.py --variant corr` → `data/tau/TauCorrections_2025_corrTES_with_uncorrelated_systs.json` (TES inclusive across pT, TauID per pT).

### Double-scan boost (anti–white-spot)
Each 2D grid scan runs **two passes**:
1. Normal `combine -M MultiDimFit` (pass 1).
2. `find_boost_params(...)` walks the scan tree — if any grid point sits at `deltaNLL < 0` (deeper than combine's free-POI fit), its POI + nuisance values are extracted.
3. Pass 2 re-runs the same scan with `--setParameters r=1,<seeds>` and reuses the same `-n` tag (overwrites pass-1 ROOT in place). Single retry, no iterative loop.

Without this, low-stats DM/pT scans sometimes got stuck in a local minimum and the 2D NLL plot showed pegged-zero patches ("white spots") because the contour was referenced to the wrong baseline.

### Outputs (parallel `_corrTES` tree)
```
output_pt_less_region_corrTES/againstjet_[JET_WP]/againstelectron_[ELE_WP]/[YEAR]/
postfit_pt_less_region_corrTES/...
plots_pt_less_region_corrTES/...
data/tau/TauCorrections_[YEAR]_corrTES_with_uncorrelated_systs.json
```
