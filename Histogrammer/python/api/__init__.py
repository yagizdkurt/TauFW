"""Public API of the Histogrammer: the control histograms of pico tuples (the data/MC stacks of the control plots),
filled by fillhists.py (the former Plotter plot.py, CL §24) and written to a control-histogram file that the Plotter
draws (TauFW.Plotter.api.ControlPlots).

    from TauFW.Histogrammer.api import ControlHists, HistsRequest
    histogrammer = ControlHists()                                # Histogrammer/ of this CMSSW area; silent
    request = HistsRequest(eras=['2025'], configs=['mutau', 'mumu'], variables=['m_vis', 'pt_2'])
    plan    = histogrammer.plan(request)                         # CommandPlan: nothing runs
    problems = histogrammer.preflight(request)                   # empty: ready
    report  = histogrammer.make(request, logdir='logs')          # RunReport: report.ok, report.artifacts (the files)

Public API:
  ControlHists                           the facade (api/control_hists.py)
  HistsRequest                           request (api/types.py)
  CommandPlan, RunReport                 results (TauFW.Utilities.Process)
"""
from TauFW.Utilities.Process import CommandPlan, RunReport
from TauFW.Histogrammer.api.types import HistsRequest
from TauFW.Histogrammer.api.control_hists import ControlHists

__all__ = ['ControlHists', 'HistsRequest', 'CommandPlan', 'RunReport']
