# 2025 pico tuples: weight branches added after production

**Date:** 2026-10-19, updated 2026-10-26 after the group's answer
**Branch:** `Refactor-2025`
**Author:** Yagizhan Dinckurt (yagizdkurt)
**For:** the TauFW group (producers of the `pico2024/TES_variations` tuples)

## Summary

The 2025 TES / tau ID analysis (`Analyses/tes_id_2025`, `Fitter/run_inputs*.sh`) normalises its MC with weight
branches whose names end in `_2025` (and `_2026`, `_2025_2026` for the 2026 and combined eras). The PicoProducer
writes only the generic `puweight`, `trigweight`, `idisoweight_1`.

Answer of the group (2026-10-26): the analysis uses **2024 MC** for the 2025 and 2026 data. To do so, pileup and muon
correction branches were added to the existing 2024 MC tuples afterwards, by
`Legacy/OldAnalysis/2025-2026/add_pileup_weights.py` and `Legacy/OldAnalysis/2025/add_muon_weights.py`. These are
**analysis specific**, not part of the PicoProducer output. (Our first search, 2026-10-19, missed the two scripts in
`Legacy/OldAnalysis`.)

So the tuples can be reproduced: produce with `pico.py`, then run the two scripts. What is still not reproducible
from the repository alone is listed under "Open".

## What the scripts add

Both open each MC file of `/eos/cms/store/group/phys_tau/TauFW/pico2024/TES_variations/2025/{DY,ST,TT,VV,WJ}` in
`UPDATE` mode, add the missing branches and leave everything else (the `cutflow` histogram included) as it is. Paths
are hard-coded (EOS, a personal AFS area).

| Script | Branches | Computed from |
|---|---|---|
| `add_pileup_weights.py` | `puweight_2025_{80p0,72p3832,69p2,66p0168}_v2`, `puweight_2026_69p2`, `puweight_2025_2026_69p2` | `npu_true`; data profile / MC profile, both normalised, weight capped at 100, 1 for an empty MC bin. Data: `PicoProducer/data/pileup/Data_PileUp_<era>_<xsec>.root`; MC: `MC_PileUp_2025.root` |
| `add_muon_weights.py` | `idisoweight_1_2025` (MediumID x TightPFIso), `trigweight_2025` (IsoMu24); in `*_mumu*` files also `idisoweight_2_2025` | the muon at `pt_1`, `eta_1` (and `pt_2`, `eta_2`); `PicoProducer/data/lepton/MuonPOG/Run2025/muon_Z.json.gz`, evaluated by a small Python reader of the correctionlib JSON |

Checked file (2026-10-19): `.../2025/DY/DYto2Tau_Bin-MLL-50to120_mutau.root` has these branches in the tree itself
(no friend tree), and also `puweight_2025_<xsec>` and `puweight_2025_<xsec>_v3` for the four cross sections.

## Where the analysis reads them

| Where | Weight |
|---|---|
| sample model templates `Configs/Histogrammer/samples/v15_2025.yml`, `v15_2026.yml`, `v15_2526.yml` (`weights:`; from `samples_v15.py:266-284`) and the bundle copy `Analyses/tes_id_2025/v15_2025.yml` | mutau/etau 2025: `genweight*puweight_2025_69p2_v3*trigweight_2025*idisoweight_1_2025*idweight_2*ltfweight_2`; 2026: `puweight_2026_69p2`; 2526: `puweight_2025_2026_69p2` |
| the same, channel kind "other" (mumu, ee, emu) | `genweight*puweight_2025_69p2_v3*idisoweight_1_2025*trigweight_2025*idisoweight_2_2025` (2026/2526: their pileup weight) |
| `Fitter/run_inputs_2526.sh`, `Fitter/run_workflow_zmm_corrTES_2526.sh` (comments) | the 2526 pileup weight |

## Open

1. **`_v3`**: the analysis reads `puweight_2025_69p2_v3`; the repository's copy of the pileup script writes `_v2`
   (its comment: the 2025 branches were "already written by earlier runs"). Which version of the script made `_v3`,
   and what changed?
2. **MC pileup profile**: `MC_PileUp_2025.root` (the denominator) is only in a personal AFS area; it should go to
   `PicoProducer/data/pileup/`.
3. **Which files**: did the TES/LTF/JTF variation files and the 2026 tuples go through both scripts? (Both scripts
   take every `.root` file below the five directories, so variation files there are included.)
4. **Electron channels**: the muon script treats every file that is not mumu as mutau (the muon SF at `pt_1`,
   `eta_1`). The etau weight of 2025/2026/2526 and the ee/emu weight read these muon SFs.
5. **Older eras**: the mumu/ee/emu weight of the eras before 2025 uses the 2025 names too (`samples_v15.py:281-284`,
   copied into the templates). Since the add-on is specific to the 2025 campaign, this looks like a copy mistake.

## What the repository does

- The pico tuple contract ([docs/contracts/pico-tuples.md](../contracts/pico-tuples.md), CL §35) lists these branches
  as the **analysis add-on** of the 2025 campaign; `Tests/contracts/test_pico_tuples.py` accepts them in the sample
  models of 2025, 2026 and 2526 only, and lists points 4 and 5 as known debt.
- Nothing in the analysis changes: switching to the generic `puweight*trigweight*idisoweight_1` would change the
  normalisation.
- Open item (TODO §0): bring the two scripts into the repository as a weights step (inputs from the recipe instead of
  hard-coded paths), then the add-on becomes part of the contract's production side.
