"""Public API of the Histogrammer: the control histograms of pico tuples (the data/MC stacks of the control plots),
filled by fillhists.py (the former Plotter plot.py, CL §24) and written to a control-histogram file that the Plotter
draws (TauFW.Plotter.api.ControlPlots); and the input histograms (shapes) of the TES + tau ID fit, filled by
shapes/TauES/createinputsTES.py and read by the Fitter (docs/contracts/tes-shapes.md; in the Fitter API until CL §25).

    from TauFW.Histogrammer.api import ControlHists, HistsRequest
    histogrammer = ControlHists()                                # Histogrammer/ of this CMSSW area; silent
    request = HistsRequest(eras=['2025'], configs=['mutau', 'mumu'], variables=['m_vis', 'pt_2'])
    plan    = histogrammer.plan(request)                         # CommandPlan: nothing runs
    problems = histogrammer.preflight(request)                   # empty: ready
    report  = histogrammer.make(request, logdir='logs')          # RunReport: report.ok, report.artifacts (the files)

    from TauFW.Histogrammer.api import TESShapes, ShapesRequest
    shapes  = TESShapes()                                        # Histogrammer/ of this CMSSW area; silent
    request = ShapesRequest(eras=['2025'], configs=['../Configs/Fitter/tes_id/config_coarse_TT.yml',
                            '../Configs/Fitter/tes_id/FitSetup_mumu.yml'], jet_wps=['VTight'], ele_wps=['Tight'],
                            outdir='/tmp/shapes')                # outdir is required
    report  = shapes.make_shapes(request, logdir='logs')         # plan_shapes, preflight_shapes as above

Public API:
  ControlHists                           the control-histograms facade (api/control_hists.py)
  TESShapes                              the TES shapes facade (api/tes_shapes.py)
  HistsRequest, ShapesRequest            requests (api/types.py)
  CommandPlan, RunReport                 results (TauFW.Utilities.Process)
"""
from TauFW.Utilities.Process import CommandPlan, RunReport
from TauFW.Histogrammer.api.types import HistsRequest, ShapesRequest
from TauFW.Histogrammer.api.control_hists import ControlHists
from TauFW.Histogrammer.api.tes_shapes import TESShapes

__all__ = ['ControlHists', 'TESShapes', 'HistsRequest', 'ShapesRequest', 'CommandPlan', 'RunReport']
