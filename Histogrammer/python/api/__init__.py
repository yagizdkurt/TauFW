"""Public API of the Histogrammer: data/MC control plots of pico tuples, made by fillhists.py (the former Plotter
plot.py, CL §24; the drawing moves to the clean Plotter later).

    from TauFW.Histogrammer.api import ControlPlots, PlotsRequest
    plotter = ControlPlots()                                     # Histogrammer/ of this CMSSW area; silent
    request = PlotsRequest(eras=['2025'], configs=['mutau', 'mumu'], variables=['m_vis', 'pt_2'])
    plan    = plotter.plan(request)                              # CommandPlan: nothing runs
    problems = plotter.preflight(request)                        # empty: ready
    report  = plotter.make(request, logdir='logs')               # RunReport: report.ok, report.artifacts

Public API:
  ControlPlots                           the facade (api/control_plots.py)
  PlotsRequest                           request (api/types.py)
  CommandPlan, RunReport                 results (TauFW.Utilities.Process)
"""
from TauFW.Utilities.Process import CommandPlan, RunReport
from TauFW.Histogrammer.api.types import PlotsRequest
from TauFW.Histogrammer.api.control_plots import ControlPlots

__all__ = ['ControlPlots', 'PlotsRequest', 'CommandPlan', 'RunReport']
