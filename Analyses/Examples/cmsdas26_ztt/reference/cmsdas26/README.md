# CMSDAS26 reference plots

The ROC curves of step 6 (tagger comparison) as the CMSDAS 2026 tau long exercise made them: made by our team at
CMSDAS 2026 (about 2026-09), with the long-ex code of the exercise:

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
those plots prints (the `tagger_roc` stage of this bundle, same plots byte for byte), so it comes from another run with other settings:

| AUC | DeepTau | PNet | UParT | this bundle, `tagger_roc` (same order) |
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

## Results of this bundle (run `CDTest_20261027-155341`, lxplus, 2026-10-27)

The bundle was `Analyses/CDTest` then, hence the run names `CDTest_*` here; it is now
`Analyses/Examples/cmsdas26_ztt` and its runs are `cmsdas26_ztt_<time>`.

Steps 1-9 of the recipe (13 stages, about 1.5 h), with the hybrid selection and the team's SF file above. Not done:
step 7B (the SFs are the team's, not measured again) and step 10 (BDT).

**Cross sections** (`stages/xsec_fit/results.txt`): the same as the slides (s.8) to the third decimal.

| | r, `singles` (quoted) | r, NLL scans | stat (scan) | slides |
|---|---|---|---|---|
| Z → τ_μ τ_h, m_vis shape | 0.9696 +0.0417 / -0.0397 | 0.9696 +0.0418 / -0.0400 | ± 0.0022 | 0.970 +0.042 / -0.040, ± 0.0022 |
| Z → μμ, one bin | 0.9643 +0.0134 / -0.0141 | 0.9643 +0.0130 / -0.0141 | ± 0.0001 | 0.964 +0.013 / -0.014, ± 0.0001 |
| r(μτ) / r(μμ) | | 1.0054 +0.0411 / -0.0394 | ± 0.0023 | 1.005 +0.041 / -0.039, ± 0.0023 |

**Impacts on r(μτ)** (`impacts_mutau.json`), largest first: tauID 0.039, lumi_2024 0.013, tes 0.005, norm_ZL,
norm_WJ, norm_Top, norm_QCD, then autoMCStats bins: the order of s.24.

**Datacards:** mutau observation 401,654 events (ZTT 263,569 expected, 40 m_vis bins 0-200 GeV), lnN tauID 4.0% and
tes 0.5% (from the SF file), lumi 1.4%, norm QCD 20%, WJ 15%, ZJ 15%, ZL 10%, Top 8%, VV 5%. mumu observation
68,242,684 events (one bin, m_vis 50-130 GeV).

**To know when the results are shown:**

- norm_ZL is pulled by +1.97σ (about 20% more Z → μμ with μ → τ_h, the bump near 90 GeV): only the SFs of genuine
  taus are applied, no μ → τ_h fake-rate SF. The same set-up as the exercise.
- m_vis bins 160-165 GeV (data/MC 0.83) and 180-185 GeV (1.27; autoMCStats bin 36 pulled by 2.4σ): most likely a few
  MC events with large weights; impact on r 0.002.
- mumu m_vis: a 2-5% data/MC wiggle around the peak (no muon momentum correction); no effect on the one-bin fit.
- m_vis peak with tau ID SF and TES: about 57k events / 5 GeV, as s.6 (s.18 is from another iteration).
- The SFs are the team's own measurement, not official (TauPOG) ones.
- In this run, `sf_tauid` failed (the SF file had not been committed: `*.json` of `.gitignore`), the file was copied
  into the run's bundle by hand and the stage retried (`taufw.py retry`, CL §44). Same file as the committed one,
  but run.json does not record it (the run started before the bundle check).

**Tagger comparison, fixed method** (`stages/tagger_roc_fixed/roc_summary.txt`: the events where all three taggers
have a score, 10000 bins):

| AUC (eff. at 1% fake rate) | DeepTau | PNet | UParT | slides s.16 |
|---|---|---|---|---|
| vsJet | 0.882 (0.297) | 0.907 (0.306) | 0.905 (0.298) | 0.876 / 0.906 / 0.902 |
| vsE | 0.986 (0.779) | 0.985 (0.715) | 0.987 (0.823) | 0.983 / 0.969 / 0.981 |
| vsMu | 0.968 (0.402) | 0.913 (0.124) | 0.965 (0.585) | 0.891 / 0.587 / 0.793 |

vsJet agrees with the slides, vsE and vsMu do not (the curves cut short by 100 bins, below). PNet is still the best
against jets; against electrons and muons DeepTau and UParT are about equal in AUC, and UParT is ahead at a 1% fake
rate, so "DeepTau best against muons" holds only for the coarse method. The selection (and with it r) does not
change.

## Shortcomings of the reference ROC plots

These plots have the two shortcomings of the exercise's method, which the `tagger_roc_fixed` stage corrects (its
plots are not comparable with these files):

- each tagger leaves out its own taus without a score (-1), so the taggers are compared on different events
  (1.30M genuine taus for DeepTau, 1.63M for PNet in the signal of the reference run);
- 100 bins in [0,1] are too coarse: the scores pile up in the last bin, so some curves stop at a fake rate of
  10-40% (all three against muons), the efficiency at a 1% fake rate cannot be read off, and the AUC is an
  integral over the part of the curve that exists (0.568 for PNet against muons).
