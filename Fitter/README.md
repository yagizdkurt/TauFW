# TauFW Fitter

## Installation

See [the README.md in the parent directory](../../../#taufw).

## Workflows

- **Combined TES + TauID fit (current):** [TauES_ID/README_2DTES_TauID_Fit.md](TauES_ID/README_2DTES_TauID_Fit.md)
  (`run_inputs*.sh` → `run_workflow_zmm*.sh`). More background in [TauES_ID/README.md](TauES_ID/README.md).
- **Input creation / config format:** [TauES/README.md](TauES/README.md).
- **Other measurements:** [ETauFR/](ETauFR/README.md), [TauID/](TauID/README.md), [Zpt/](Zpt/README.md),
  `HighPT/`, `MuTauFR/`, `paper/`, `tutorial/`.

## Public API (`TauFW.Fitter.api`)

`TauESID` runs the combined TES + TauID fit as the shell scripts do, with the same arguments, one process per
script in `Fitter/`, and checks that every command wrote its expected outputs (the scripts call `combine` through
`os.system`, so their exit code alone proves nothing). The TauFW Framework uses it for its `histograms` and `fit`
stages (see [Framework/README.md](../Framework/README.md)).

```python
from TauFW.Fitter.api import TauESID, ShapesRequest, FitRequest
fitter = TauESID()                                            # Fitter/ of this CMSSW area; reads and runs nothing
shapes = ShapesRequest(eras=['2025'], jet_wps=['VTight'], ele_wps=['Tight'],
                       configs=['TauES_ID/config/config_coarse_TT.yml', 'TauES/config/FitSetup_mumu.yml'])
fitter.plan_shapes(shapes)      # CommandPlan: the run_inputs.sh commands and the shape files; nothing runs
fitter.preflight_shapes(shapes) # problems (no cmsenv, no ROOT, missing config); empty: ready
fitter.make_shapes(shapes, logdir='logs')                     # RunReport: ok, results (one log per command), artifacts
fit = FitRequest(points=[('2025', 'VTight', 'Tight')], config='TauES_ID/config/config_coarse_TT.yml',
                 config_mumu='TauES/config/FitSetup_mumu.yml')   # steps: fit, postfit, plots, corrections, summary
fitter.fit(fit, logdir='logs')  # the run_workflow_zmm.sh steps; artifacts carry the fitted tes and tid_SF values
```

Bugs found and fixed on this path: [docs/Fitter/BUGS.md](../docs/Fitter/BUGS.md).

## Legacy

Broken, superseded or unused scripts are in [Legacy/Fitter/](../Legacy/Fitter/README.md) (same internal relative paths),
and unused Python modules to `python/legacy/` (`TauFW.Fitter.legacy.*`).
They are kept for reference and are not maintained.
