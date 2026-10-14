This page is being moved to the [wiki pages](https://github.com/cms-tau-pog/TauFW/wiki/Plotter)

# TauFW Plotter

For instructions, please refer to the [Plotter wiki page](https://github.com/cms-tau-pog/TauFW/wiki/Plotter)

Unmaintained scripts and configs are kept in [Legacy/Plotter/](../Legacy/Plotter/README.md), including package modules and macros under `Legacy/Plotter/python/`.

## Public API (`TauFW.Plotter.api`)

`ControlPlots` makes data/MC control plots with `plot.py`, run as a separate process in `Plotter/` with the arguments a
user would type, and checks that plots were written. The TauFW Framework uses it for its `plots` stage (see
[Framework/README.md](../Framework/README.md)).

```python
from TauFW.Plotter.api import ControlPlots, PlotsRequest
plotter = ControlPlots()                                       # Plotter/ of this CMSSW area; reads and runs nothing
request = PlotsRequest(eras=['2025'], configs=['mutau', 'mumu'], variables=['m_vis', 'pt_2'])
plotter.plan(request)       # CommandPlan: python3 plot.py -y 2025 -c mutau -V m_vis pt_2, ...; nothing runs
plotter.preflight(request)  # problems (no cmsenv, no ROOT, missing setup); empty: ready
plotter.make(request, logdir='logs')   # RunReport: ok, one log per command, plots per channel and era
```

Bugs found and fixed on this path: [docs/Plotter/BUGS.md](../docs/Plotter/BUGS.md).
