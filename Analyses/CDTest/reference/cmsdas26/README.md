# CMSDAS26 reference plots

The ROC curves of step 6 (tagger comparison) as the CMSDAS 2026 tau long exercise made them: made by the exercise
team of Yagizhan Dinckurt at CMSDAS 2026 (about 2026-09), with the long-ex code of the exercise:

```sh
./plots_and_histograms_CMSDAS26.py -y 2024 -c mutau --tagger
```

with `tagger.base: "q_1*q_2<0 && iso_1<0.15 && mt_1<65"` and `tagger.nbins: 100` of its `cmsdas_mutau.yml`, on the
pre-made 2024 tuples (`/eos/cms/store/group/phys_tau/TauFW/pico2024/TES_variations/2024/`).

| File | |
|---|---|
| `tagger_ROC_VSjet_mutau_2024.png` | against jets |
| `tagger_ROC_VSe_mutau_2024.png` | against electrons |
| `tagger_ROC_VSmu_mutau_2024.png` | against muons |

The `tagger_roc` stage of the recipe (the same settings) reproduces them byte for byte: first checked with the run
`CDTest_20261027-144207` on lxplus (2026-10-27), same MD5 for all three. Its plots
(`stages/tagger_roc/plots/2024/`) can be compared with these files after every run, e.g. with `md5sum`. A different
ROOT version may change pixels without a physics difference.

## Results of the exercise team (their CMSDAS@CERN 2026 slides)

The numbers to compare with, from the talk of the team ("SMP Z → ττ measurement", 24 slides; `s.N` is the slide).
Read off the slides: the plots there come from more than one iteration of the analysis (see the last list).

**Selection (s.6):** the hybrid selection of `setup_mutau.yml`: opposite sign, iso_1 < 0.15, iso_2 < 0.15, PNet
VSjet Tight, DeepTau VSe VVLoose, DeepTau VSmu Tight, m_T < 65 GeV, decay modes 0, 1, 10, 11, lepton vetoes, MET
filters.

**Tagger comparison (s.5, s.16):** the plots of s.5 are the three PNG files above. Conclusion: best against
electrons DeepTau, against jets PNet, against muons DeepTau. The AUC table of s.16 is **not** what the code that made
those plots prints (CDTest `tagger_roc`, same plots byte for byte), so it comes from another run with other settings:

| AUC | DeepTau | PNet | UParT | CDTest `tagger_roc` (same order) |
|---|---|---|---|---|
| vsJet | 0.876 | 0.906 | 0.902 | 0.875 / 0.890 / 0.884 |
| vsE | 0.983 | 0.969 | 0.981 | 0.983 / 0.967 / 0.980 |
| vsMu | 0.891 | 0.587 | 0.793 | 0.901 / 0.568 / 0.792 |

**Scale factors (s.7, s.22):** measured by the team (Tier B, 2D likelihood scan per decay mode and pT bin, VSjet
Tight), the values of `sf/TauCorrections_2024_corrTES_noCR_vseVLvsmuTvsjetT.json`; e.g. DM0, pT 20-40 GeV:
TES = 0.9976 -0.0039/+0.0036, tau ID SF = 1.0222 -0.0234/+0.0291 (s.7). s.22: TES and tau ID SF of all 12
regions (2D scan and FitDiagnostics).

**Cross sections (s.8, s.10):** r = σ/σ_theory

| | r | stat |
|---|---|---|
| Z → τ_μ τ_h, m_vis shape | 0.970 +0.042 / -0.040 | ± 0.0022 |
| Z → μμ, one bin | 0.964 +0.013 / -0.014 | ± 0.0001 |
| r(μτ) / r(μμ) | 1.005 +0.041 / -0.039 | ± 0.0023 |
| Z → τ_μ τ_h, with the BDT (s.10, s.19) | 0.970 +0.026 / -0.026 | ± 0.0022 |
| r(μτ) / r(μμ), with the BDT | 1.006 +0.023 / -0.023 | ± 0.0023 |

**Impacts on r(μτ) (s.24, m_vis fit), largest first:** tauID, lumi_2024, tes, norm_ZL, norm_WJ, norm_Top, norm_QCD,
then the autoMCStats bins (`prop_binmutau_bin*`, up to bin 38: the 40 m_vis bins), norm_ZJ, norm_VV.
With the BDT (s.20): tauID, lumi_2024, norm_QCD, norm_WJ, tes, then autoMCStats bins.

**BDT (s.9-11, s.19, s.23):** 10 kinematic and topological inputs, 50% of the events for the training, k-folding;
the fit uses the unrolled BDT score x m_vis (4 BDT slices 0-0.3, 0.3-0.6, 0.6-0.8, 0.8-1.0, each m_vis 0-200 GeV
in 10 bins, s.9).

**Control plots:**
- s.6: m_vis of the signal region (40 bins, 0-200 GeV), peak about 58k events / 5 GeV.
- s.18: m_vis with the tau ID SF and TES applied, variation down / nominal / up: peaks about 88k / 79k / 71k
  events / 5 GeV.
- s.17: m_T(μ, MET) up to 150 GeV (so without the m_T < 65 cut) and the decay mode.
- s.21: m_vis of mumu, 50-130 GeV in 2 GeV bins.

Not consistent with each other: s.6 and the nominal of s.18 differ by about 35% at the peak, and s.17 has no m_T
cut, so these plots are from different iterations; which one belongs to the r values above is not known.

## Shortcomings of the reference ROC plots

These plots have the two shortcomings of the exercise's method, which the `tagger_roc_fixed` stage corrects (its
plots are not comparable with these files):

- each tagger leaves out its own taus without a score (-1), so the taggers are compared on different events
  (1.30M genuine taus for DeepTau, 1.63M for PNet in the signal of the reference run);
- 100 bins in [0,1] are too coarse: the scores pile up in the last bin, so some curves stop at a fake rate of
  10-40% (all three against muons), the efficiency at a 1% fake rate cannot be read off, and the AUC is an
  integral over the part of the curve that exists (0.568 for PNet against muons).
