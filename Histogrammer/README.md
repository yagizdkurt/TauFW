This page is being moved to the [wiki pages](https://github.com/cms-tau-pog/TauFW/wiki/Plotter)

# TauFW Histogrammer

The Histogrammer turns pico tuples into histograms: the sample model (which samples, cross sections, sums of
weights, normalisation `lumi*xsec/sumw`, joining, stitching, genmatch splitting), the variable and selection language
(`Variable`, `Selection`), the RDataFrame filling and the data-driven methods (QCD from same-sign events).

Until October 2026 this module was called **Plotter** (changelog §24 of
[Refactor-2025.md](../docs/Refactor-2025/Refactor-2025.md)). After the drawing code moved to
`TauFW.Utilities.Drawing` (§18), almost everything left in it produced histograms, so it was renamed. A new, small
[Plotter](../Plotter/README.md) is being extracted that only draws, from histogram files written here.
For instructions on the physics side, the [Plotter wiki page](https://github.com/cms-tau-pog/TauFW/wiki/Plotter) still
applies (with the new names below).

Unmaintained scripts and configs are kept in [Legacy/Plotter/](../Legacy/Plotter/README.md), including package
modules and macros under `Legacy/Plotter/python/`.

## Layout

| Path | What |
|---|---|
| `fillhists.py` | fills the histograms of a channel setup and era (formerly `Plotter/plot.py`, same options); until the clean Plotter draws them it also draws the control plots, exactly as `plot.py` did |
| `plot.py` | LEGACY: prints the `fillhists.py` command to use instead and exits (nothing runs) |
| `plot_postfit.py`, `plot_postfit_shift.py`, `plot_v10.py`, `tutorial/` | older fill-and-draw variants, unchanged (their future is decided in step S3 of the plan) |
| `config/samples*.py` | sample lists as Python code (`samples_v15.py` is backward compatibility for runs without sample model files) |
| `python/sample/` | `Sample`, `MergedSample`, `SampleSet`, `HistSet`, `ResultDict`, `MultiDraw`, `utils` (`getsampleset`, `setera`, `stitch`, `join`), `model` (sample model files) |
| `python/spec/` | what to fill: `Variable`, `Selection`, `Context` (contextual binning and titles), `string` (selection strings) |
| `python/methods/` | data-driven methods added to `SampleSet` by name (`QCD_OSSS`) |
| `python/macros/`, `python/corrections/` | ROOT macros loaded by path (e.g. `mapDecayModes.C`) |
| `python/api/` | the public API below |

## Old names (backward compatibility)

| Before | Now |
|---|---|
| `TauFW.Plotter.sample.<module>` | `TauFW.Histogrammer.sample.<module>` |
| `TauFW.Plotter.plot.Variable`, `.Selection`, `.Context`, `.string` | `TauFW.Histogrammer.spec.<module>` |
| `TauFW.Plotter.plot.MultiDraw` | `TauFW.Histogrammer.sample.MultiDraw` |
| `TauFW.Plotter.methods.QCD_OSSS` | `TauFW.Histogrammer.methods.QCD_OSSS` |
| `TauFW.Plotter.api` | `TauFW.Histogrammer.api` (no old name kept: only the Framework used it) |
| `Plotter/plot.py` | `Histogrammer/fillhists.py` |
| `sys.path.append(".../Plotter")` + `from config.samples_v15 import *` | `.../Histogrammer` |

The old module names still work: each is an alias of the new module (the same module object, so `setera` through
either name changes the same era and luminosity). They are deleted at the migration point
([TODO.md](../docs/Refactor-2025/TODO.md) §8); new code uses the new names. Updating a script:

```bash
sed -i -e 's/TauFW\.Plotter\.plot\.MultiDraw/TauFW.Histogrammer.sample.MultiDraw/g' \
       -e 's/TauFW\.Plotter\.plot\./TauFW.Histogrammer.spec./g' \
       -e 's/TauFW\.Plotter\./TauFW.Histogrammer./g' myscript.py
```

## Public API (`TauFW.Histogrammer.api`)

`ControlPlots` makes data/MC control plots with `fillhists.py`, run as a separate process in `Histogrammer/` with the
arguments a user would type, and checks that plots were written. The TauFW Framework uses it for its `plots` stage
(see [Framework/README.md](../Framework/README.md)).

```python
from TauFW.Histogrammer.api import ControlPlots, PlotsRequest
plotter = ControlPlots()                                       # Histogrammer/ of this CMSSW area; reads and runs nothing
request = PlotsRequest(eras=['2025'], configs=['mutau', 'mumu'], variables=['m_vis', 'pt_2'])
plotter.plan(request)       # CommandPlan: python3 fillhists.py -y 2025 -c mutau -V m_vis pt_2, ...; nothing runs
plotter.preflight(request)  # problems (no cmsenv, no ROOT, missing setup); empty: ready
plotter.make(request, logdir='logs')   # RunReport: ok, one log per command, plots per channel and era
```

`PlotsRequest(samples=[...])` names sample model files (`Configs/Histogrammer/samples/v15_<era>.yml` or a copy, one per
era; `fillhists.py --samples`) instead of the tables of `config/samples_v15.py`. They are read by
`TauFW.Histogrammer.sample.model` (no ROOT for reading); `sample_names`, `samples_problems` and
`sample_file_problems` check them without running anything.

Bugs found and fixed on this path: [docs/Histogrammer/BUGS.md](../docs/Histogrammer/BUGS.md).
