This page is being moved to the [wiki pages](https://github.com/cms-tau-pog/TauFW/wiki/Plotter)

# TauFW Histogrammer

The Histogrammer turns pico tuples into histograms: the sample model (which samples, cross sections, sums of
weights, normalisation `lumi*xsec/sumw`, joining, stitching, genmatch splitting), the variable and selection language
(`Variable`, `Selection`), the RDataFrame filling and the data-driven methods (QCD from same-sign events).

Until October 2026 this module was called **Plotter** (changelog §21 of
[Refactor-2025.md](../Docs/Develop/Refactor-2025/Refactor-2025.md)). After the drawing code moved to
`TauFW.Utilities.Drawing` (§18), almost everything left in it produced histograms, so it was renamed. A new, small
[Plotter](../Plotter/README.md) is being extracted that only draws, from histogram files written here.
For instructions on the physics side, the [Plotter wiki page](https://github.com/cms-tau-pog/TauFW/wiki/Plotter) still
applies (with the new names below).

Unmaintained scripts and configs are kept in [Legacy/Plotter/](../Legacy/Plotter/README.md), including package
modules and macros under `Legacy/Plotter/python/`.

## Layout

| Path | What |
|---|---|
| `fillhists.py` | fills the histograms of a channel setup and era (formerly `Plotter/plot.py`, same options); by default it also draws the control plots, exactly as `plot.py` did; with `--hists` it also writes the filled histograms to `hists/<era>/<channel><tag>.root` for `Plotter/draw.py` ([contract](../Docs/Develop/contracts/control-histograms.md)); with `--hists --no-draw` it only writes the file (the Framework's `controlhists` stage) |
| `plot.py` | LEGACY: prints the `fillhists.py` command to use instead and exits (nothing runs) |
| `plot_postfit.py`, `plot_postfit_shift.py`, `plot_v10.py`, `tutorial/` | older fill-and-draw variants, unchanged (their future is decided in step S3 of the plan) |
| `config/samples*.py` | sample lists as Python code (`samples_v15.py` is backward compatibility for runs without sample model files) |
| `python/sample/` | `Sample`, `MergedSample`, `SampleSet`, `HistSet`, `ResultDict`, `MultiDraw`, `utils` (`getsampleset`, `setera`, `stitch`, `join`), `model` (sample model files) |
| `python/spec/` | what to fill: `Variable`, `Selection`, `Context` (contextual binning and titles), `string` (selection strings) |
| `python/methods/` | data-driven methods added to `SampleSet` by name (`QCD_OSSS`) |
| `python/macros/`, `python/corrections/` | ROOT macros loaded by path (e.g. `mapDecayModes.C`) |
| `shapes/TauES/createinputsTES.py` | the input shapes of the combined TES + tau ID fit (moved from `Fitter/TauES/` in changelog §22, unchanged): run from `Fitter/` by `Fitter/run_inputs*.sh` (`python3 ../Histogrammer/shapes/TauES/createinputsTES.py ...`), so the shapes land in `Fitter/input_pt_less_region/` where the fit reads them; the file format is [Docs/Develop/contracts/tes-shapes.md](../Docs/Develop/contracts/tes-shapes.md) |
| `shapes/{ETauFR,HighPT,paper,tutorial}/createinputs.py` | the input shapes of the other Fitter measurements (moved from `Fitter/<Variant>/`, unchanged): run them from `Fitter/<Variant>/` as before (`python3 ../../Histogrammer/shapes/<Variant>/createinputs.py ...`); their `config` paths are relative to that directory |
| `python/shapes/` | `TauFW.Histogrammer.shapes.inputs` (`createinputs`, `plotinputs`, ...: the shape writer, formerly `TauFW.Fitter.plot.datacard`) and `.rebinning` |
| `python/controlhists.py` | `TauFW.Histogrammer.controlhists`: `stack_entry` (copies of a stack's histograms as filled, with the drawing attributes) and `write_control_hists` (`--hists`) |
| `python/api/` | the public API below |

## Old names (backward compatibility)

| Before | Now |
|---|---|
| `TauFW.Plotter.sample.<module>` | `TauFW.Histogrammer.sample.<module>` |
| `TauFW.Plotter.plot.Variable`, `.Selection`, `.Context`, `.string` | `TauFW.Histogrammer.spec.<module>` |
| `TauFW.Plotter.plot.MultiDraw` | `TauFW.Histogrammer.sample.MultiDraw` |
| `TauFW.Plotter.methods.QCD_OSSS` | `TauFW.Histogrammer.methods.QCD_OSSS` |
| `TauFW.Plotter.api.ControlPlots` | `TauFW.Histogrammer.api.ControlHists` (no old name kept: only the Framework used it; `TauFW.Plotter.api` is the new Plotter's own API since S4) |
| `Plotter/plot.py` | `Histogrammer/fillhists.py` |
| `sys.path.append(".../Plotter")` + `from config.samples_v15 import *` | `.../Histogrammer` |
| `Fitter/TauES/createinputsTES.py`, `Fitter/{ETauFR,HighPT,paper,tutorial}/createinputs.py` | `Histogrammer/shapes/...` (changelog §22); the old paths are LEGACY stubs that print the new command and exit with 2 |
| `TauFW.Fitter.plot.datacard`, `TauFW.Fitter.plot.rebinning` | `TauFW.Histogrammer.shapes.inputs`, `TauFW.Histogrammer.shapes.rebinning` (no alias: the Fitter would import the Histogrammer) |
| `TauFW.Fitter.api.TauESID.plan_shapes`, `.make_shapes`, `.preflight_shapes`, `.shapes_request`, `TauFW.Fitter.api.ShapesRequest` | `TauFW.Histogrammer.api.TESShapes` (same methods), `TauFW.Histogrammer.api.ShapesRequest` (same fields; `outdir` is required), changelog §22 H3; no old name kept (only the Framework used them) |

The old module names still work: each is an alias of the new module (the same module object, so `setera` through
either name changes the same era and luminosity). They are deleted at the migration point
([TODO.md](../Docs/Develop/Refactor-2025/TODO.md) §8); new code uses the new names. Updating a script:

```bash
sed -i -e 's/TauFW\.Plotter\.plot\.MultiDraw/TauFW.Histogrammer.sample.MultiDraw/g' \
       -e 's/TauFW\.Plotter\.plot\./TauFW.Histogrammer.spec./g' \
       -e 's/TauFW\.Plotter\./TauFW.Histogrammer./g' myscript.py
```

## Public API (`TauFW.Histogrammer.api`)

`ControlHists` fills the histograms of the data/MC control plots with `fillhists.py --hists --no-draw`, run as a
separate process (in the stage's output directory, or in `Histogrammer/` without one) with the arguments a user would type, and checks that the control-histogram file
was written; the Plotter draws it (`TauFW.Plotter.api.ControlPlots`). The TauFW Framework uses it for its
`controlhists` stage (see [Framework/README.md](../Framework/README.md)). Until changelog §21 (S4) this API was
`ControlPlots` and also drew; the drawing options (`fraction`, `pdf`, `text`) are now the Plotter's.

```python
from TauFW.Histogrammer.api import ControlHists, HistsRequest
histogrammer = ControlHists()                                  # Histogrammer/ of this CMSSW area; reads and runs nothing
request = HistsRequest(eras=['2025'], configs=['mutau', 'mumu'], variables=['m_vis', 'pt_2'])
histogrammer.plan(request)       # CommandPlan: python3 fillhists.py -y 2025 -c mutau -V m_vis pt_2 --hists --no-draw, ...
histogrammer.preflight(request)  # problems (no cmsenv, no ROOT, missing setup); empty: ready
histogrammer.make(request, logdir='logs')   # RunReport: ok, one log per command, one file per channel and era
```

`HistsRequest(samples=[...])` names sample model files (`Configs/Histogrammer/samples/v15_<era>.yml` or a copy, one per
era; `fillhists.py --samples`) instead of the tables of `config/samples_v15.py`. They are read by
`TauFW.Histogrammer.sample.model` (no ROOT for reading); `sample_names`, `samples_problems` and
`sample_file_problems` check them without running anything.

`TESShapes` makes the input shapes of the combined TES + tau ID fit with `shapes/TauES/createinputsTES.py`, in the
order and with the arguments of `Fitter/run_inputs.sh`, run in the request's output directory (`outdir`, required:
the Framework gives `<run_dir>/stages/<id>/`; by hand, `Fitter/run_inputs.sh` writes the shapes into `Fitter/` where
the fit scripts read them). It checks that each command wrote its shape files, one per observable, named by the
contract [Docs/Develop/contracts/tes-shapes.md](../Docs/Develop/contracts/tes-shapes.md). The Framework uses it for its `shapes`
stage. It was the shapes half of the Fitter API (`TauESID`) until changelog §22 H3.

```python
from TauFW.Histogrammer.api import TESShapes, ShapesRequest
shapes = TESShapes()                                           # Histogrammer/ of this CMSSW area; reads and runs nothing
request = ShapesRequest(eras=['2025'], jet_wps=['VTight'], ele_wps=['Tight'], outdir='/tmp/shapes',
                        configs=['../Configs/Fitter/tes_id/config_coarse_TT.yml',     # relative to Histogrammer/
                                 '../Configs/Fitter/tes_id/FitSetup_mumu.yml'])     # or absolute
shapes.plan_shapes(request)       # CommandPlan: python3 <abs>/shapes/TauES/createinputsTES.py -y 2025 -c <abs config> -j VTight -e Tight, ...
shapes.preflight_shapes(request)  # problems (no cmsenv, no ROOT, missing config, output directory not empty); empty: ready
shapes.make_shapes(request, logdir='logs')   # RunReport: ok, one log per command, one shapes artifact per file
```

Bugs found and fixed on this path: [Docs/Develop/Histogrammer/BUGS.md](../Docs/Develop/Histogrammer/BUGS.md).
