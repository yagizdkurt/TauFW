"""Public API of the Fitter: the combined TES + tau ID fit, run as the existing scripts do.

    from TauFW.Fitter.api import TauESID, ShapesRequest, FitRequest
    fitter  = TauESID()                                          # Fitter/ of this CMSSW area; silent
    shapes  = ShapesRequest(eras=['2025'], configs=['TauES_ID/config/config_coarse_TT.yml',
                            'TauES/config/FitSetup_mumu.yml'], jet_wps=['VTight'], ele_wps=['Tight'])
    plan    = fitter.plan_shapes(shapes)                         # CommandPlan: nothing runs
    problems = fitter.preflight_shapes(shapes)                   # empty: ready
    report  = fitter.make_shapes(shapes, logdir='logs')          # RunReport: report.ok, report.artifacts
    request = FitRequest(points=[('2025', 'VTight', 'Tight')], config=..., config_mumu=...)
    report  = fitter.fit(request, logdir='logs')                 # fitted values in report.artifacts

Public API:
  TauESID                                    the facade (api/tes_id.py)
  ShapesRequest, FitRequest, FIT_STEPS       requests (api/types.py)
  CommandPlan, RunReport                     results (api/types.py)
  read_fit_values                            FitparameterValues reader (api/results.py)
"""
from TauFW.Fitter.api.types import FIT_STEPS, ShapesRequest, FitRequest, CommandPlan, RunReport
from TauFW.Fitter.api.results import read_fit_values
from TauFW.Fitter.api.tes_id import TauESID

__all__ = ['TauESID', 'ShapesRequest', 'FitRequest', 'FIT_STEPS', 'CommandPlan', 'RunReport', 'read_fit_values']
