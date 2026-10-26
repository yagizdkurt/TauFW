"""Public API of the Fitter: the combined TES + tau ID fit, run as the existing scripts do.

    from TauFW.Fitter.api import TauESID, FitRequest
    fitter  = TauESID()                                          # Fitter/ of this CMSSW area; silent
    request = FitRequest(points=[('2025', 'VTight', 'Tight')], config='../Configs/Fitter/tes_id/config_coarse_TT.yml',
                         config_mumu='../Configs/Fitter/tes_id/FitSetup_mumu.yml')
    plan    = fitter.plan_fit(request)                           # CommandPlan: nothing runs
    problems = fitter.preflight_fit(request)                     # empty: ready (the shapes of every point exist)
    report  = fitter.fit(request, logdir='logs')                 # fitted values in report.artifacts

The shapes it reads are made by Fitter/run_inputs.sh (or the Framework's shapes stage), by the file contract
Docs/Develop/contracts/tes-shapes.md (the shapes API left the Fitter in CL §22 H3).

Public API:
  TauESID                                    the facade (api/tes_id.py)
  FitRequest, FIT_STEPS                      request (api/types.py)
  CommandPlan, RunReport                     results (TauFW.Utilities.Process)
  read_fit_values                            FitparameterValues reader (api/results.py)
"""
from TauFW.Utilities.Process import CommandPlan, RunReport
from TauFW.Fitter.api.types import FIT_STEPS, FitRequest
from TauFW.Fitter.api.results import read_fit_values
from TauFW.Fitter.api.tes_id import TauESID

__all__ = ['TauESID', 'FitRequest', 'FIT_STEPS', 'CommandPlan', 'RunReport', 'read_fit_values']
