# TauFW Fitter

## Installation

See [the README.md in the parent directory](../README.md#taufw).

## Workflows

- **Combined TES + TauID fit (current):** [TauES_ID/README_2DTES_TauID_Fit.md](TauES_ID/README_2DTES_TauID_Fit.md)
  (`run_inputs*.sh` → `run_workflow_zmm*.sh`). More background in [TauES_ID/README.md](TauES_ID/README.md).
- **Input creation / config format:** [TauES/README.md](TauES/README.md). The scripts that make the input shapes
  (`createinputsTES.py`, the `createinputs.py` of ETauFR, HighPT, paper, tutorial) moved to the Histogrammer
  (`Histogrammer/shapes/`, changelog §22); they run from the same directories as before, the old paths print the new
  command. `MuTauFR/createinputs.py` stays here (broken import, TODO §8).
- **Other measurements:** [ETauFR/](ETauFR/README.md), [TauID/](TauID/README.md), [Zpt/](Zpt/README.md),
  `HighPT/`, `MuTauFR/`, `paper/`, `tutorial/`.

## Public API (`TauFW.Fitter.api`)

`TauESID` runs the combined TES + TauID fit as the shell scripts do, with the same arguments, one process per
script in `Fitter/`, and checks that every command wrote its expected outputs (the scripts call `combine` through
`os.system`, so their exit code alone proves nothing). The TauFW Framework uses it for its `fit` stage (see
[Framework/README.md](../Framework/README.md)). The shapes it reads are made by `run_inputs.sh` (in `Fitter/`) or the
Framework's `shapes` stage, whose API is the Histogrammer's `TESShapes` since changelog §22 H3 (before, `TauESID`
also had `plan_shapes`/`make_shapes`/`preflight_shapes` and `ShapesRequest`; no old name is kept). The two sides
share only the file contract [Docs/Develop/contracts/tes-shapes.md](../Docs/Develop/contracts/tes-shapes.md).

```python
from TauFW.Fitter.api import TauESID, FitRequest
fitter = TauESID()                                            # Fitter/ of this CMSSW area; reads and runs nothing
fit = FitRequest(points=[('2025', 'VTight', 'Tight')], config='../Configs/Fitter/tes_id/config_coarse_TT.yml',
                 config_mumu='../Configs/Fitter/tes_id/FitSetup_mumu.yml')   # steps: fit, postfit, plots, corrections, summary
fitter.plan_fit(fit)            # CommandPlan: the run_workflow_zmm.sh commands; nothing runs
fitter.preflight_fit(fit)       # problems (no cmsenv, combine missing, no shapes in Fitter/input_pt_less_region/)
fitter.fit(fit, logdir='logs')  # the run_workflow_zmm.sh steps; artifacts carry the fitted tes and tid_SF values
```

Bugs found and fixed on this path: [Docs/Develop/Fitter/BUGS.md](../Docs/Develop/Fitter/BUGS.md).

## Legacy

Broken, superseded or unused scripts are in [Legacy/Fitter/](../Legacy/Fitter/README.md) (same internal relative paths),
with unused Python modules in `Legacy/Fitter/python/` (`Legacy.Fitter.python.*`; see the archive README for import setup).
They are kept for reference and are not maintained.
