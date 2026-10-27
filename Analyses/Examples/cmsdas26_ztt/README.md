# cmsdas26_ztt: the CMSDAS 2026 tau long exercise in the new TauFW

This is the Z → τ_μ τ_h cross-section exercise from CMSDAS 2026, redone as one recipe in the new framework. We
wanted to see if the new TauFW can run a real analysis from start to end and give the same numbers. It does.

## Run it

On lxplus, in a CMSSW area with Combine and CombineHarvester (the exercise's setup), from the TauFW root:

```sh
python3 taufw.py start Analyses/Examples/cmsdas26_ztt     # or from the menu: python3 taufw.py
```

It reads the pre-made 2024 tuples from EOS, so no production step is needed. The whole run takes about 1.5 hours.
Results end up in `<run_root>/cmsdas26_ztt_<time>/stages/`, the fit results in `stages/xsec_fit/results.txt`.

## What it does

- control plots of the μτ_h and μμ signal regions
- ROC curves of DeepTau, PNet and UParT (once as in the exercise, once on common events with finer bins)
- tau ID SF and TES applied, nominal / up / down histograms
- datacards and Combine fits for r(μτ) and r(μμ), with impacts, scans, pulls and pre/post-fit plots

The selection is the "hybrid" one we used at CMSDAS (PNet vs jets, DeepTau vs e and μ), with the scale factors our
team measured (`sf/`). These are not official TauPOG scale factors.

## Results

| | r |
|---|---|
| Z → τ_μ τ_h | 0.970 +0.042 / -0.040 |
| Z → μμ | 0.964 +0.013 / -0.014 |
| r(μτ) / r(μμ) | 1.005 +0.041 / -0.039 |

Same as on our CMSDAS slides, same impact ranking too. Details, comparisons and a few things worth knowing
(e.g. norm_ZL pulls by ~2σ) are in `reference/cmsdas26/README.md`.

## Not done yet

- measuring the SFs again (step 7, Tier B): we use our team's file
- the BDT fit (step 10)
- the n-tuple production demo (step 4)

Each missing piece is described in the comments of `recipe.yml`.
