"""Public API of the Plotter: data/MC control plots of pico tuples, made by the existing plot.py.

    from TauFW.Plotter.api import ControlPlots, PlotsRequest
    plotter = ControlPlots()                                     # Plotter/ of this CMSSW area; silent
    request = PlotsRequest(eras=['2025'], configs=['mutau', 'mumu'], variables=['m_vis', 'pt_2'])
    plan    = plotter.plan(request)                              # CommandPlan: nothing runs
    problems = plotter.preflight(request)                        # empty: ready
    report  = plotter.make(request, logdir='logs')               # RunReport: report.ok, report.artifacts

Public API:
  ControlPlots                           the facade (api/control_plots.py)
  PlotsRequest, CommandPlan, RunReport   records (api/types.py)
"""
from TauFW.Plotter.api.types import PlotsRequest, CommandPlan, RunReport
from TauFW.Plotter.api.control_plots import ControlPlots

__all__ = ['ControlPlots', 'PlotsRequest', 'CommandPlan', 'RunReport']
