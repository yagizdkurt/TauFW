"""Public API of the Plotter: data/MC control plots drawn from the control-histogram files of the Histogrammer
(changelog §24, S4). The Histogrammer fills (TauFW.Histogrammer.api.ControlHists); the Plotter only draws.

    from TauFW.Plotter.api import ControlPlots, PlotsRequest, HistFileInput
    plotter = ControlPlots()                                     # Plotter/ of this CMSSW area; silent
    request = PlotsRequest(files=[HistFileInput(path='../Histogrammer/hists/2025/mutau.root', era='2025',
                                                channel='mutau')], pdf=True)
    plan    = plotter.plan(request)                              # CommandPlan: nothing runs
    problems = plotter.preflight(request)                        # empty: ready
    report  = plotter.make(request, logdir='logs')               # RunReport: report.ok, report.artifacts

Public API:
  ControlPlots                           the facade (api/control_plots.py)
  PlotsRequest, HistFileInput            requests (api/types.py)
  CommandPlan, RunReport                 results (TauFW.Utilities.Process)
"""
from TauFW.Utilities.Process import CommandPlan, RunReport
from TauFW.Plotter.api.types import HistFileInput, PlotsRequest
from TauFW.Plotter.api.control_plots import ControlPlots

__all__ = ['ControlPlots', 'PlotsRequest', 'HistFileInput', 'CommandPlan', 'RunReport']
