# TauFW Plotter

> **Being rebuilt (October 2026, changelog §24 of [Refactor-2025.md](../docs/Refactor-2025/Refactor-2025.md)).**
> The module that was called Plotter until now is the [Histogrammer](../Histogrammer/README.md): it fills
> histograms from pico tuples. This directory is the new, small Plotter that only **draws**. Since step S3 it draws
> control plots from a histogram file, since S4 also as the Framework's `controlplots` stage (through its API,
> `TauFW.Plotter.api`). It also keeps the old `Plotter` names working until the migration point.

## What the Plotter is

The Plotter turns histogram files into plots. It does not read tuples, does not know about samples, cross sections
or selections, and does not import the Histogrammer (or any other TauFW stage):

```text
pico tuples ──▶ Histogrammer (fillhists.py --hists) ──▶ hists/<era>/<setup>.root ──▶ Plotter (draw.py) ──▶ PNG / PDF
                fills, normalises, QCD                   styled histograms              reads, stacks,
                                                         + drawing metadata             draws the ratio, saves
```

```bash
cd Histogrammer
python3 fillhists.py -y 2025 -c mutau --hists     # its usual plots, and hists/2025/mutau.root
python3 ../Plotter/draw.py hists/2025/mutau.root -o drawn/2025    # the same plots, from the file
```

- **Input:** a control-histogram file ([contract](../docs/contracts/control-histograms.md)): per selection and
  variable the data, the expected processes in stack order and the signals (already coloured and titled), plus the
  17 drawing settings of the variable (axis title, ranges, log scale, legend position, ...).
- **Output:** the plots, drawn with the shared drawing library (`TauFW.Utilities.Drawing`: `Stack`, `CMSStyle`).
  A plot drawn from the file is the same, pixel for pixel, as the plot `fillhists.py` draws from memory
  (checked by the BBB case `plotter.stack` and on real data).
- **Why separate:** redrawing (legend, axis, text) no longer refills histograms from tuples, which takes hours on
  full data; the Plotter can be tested with a small ROOT file, without tuples.

`draw.py` options: `-o OUTDIR` (default `plots/$ERA`; `$ERA`, `$CHANNEL` are replaced), `-F` (fraction stack in
the ratio panel), `-p` (pdf too), `-T TEXT` (extra text), `-v` (verbosity of the drawing code).

In a TauFW recipe the two halves are two stages, each with the API of its own module; the Framework carries the
files from one to the other ([Analyses/README.md](../Analyses/README.md)):

```yaml
  - stage: controlhists        # Histogrammer: fillhists.py --hists --no-draw, one file per setup and era
    id: hists
    inputs: {tuples: production}
    eras: [2025]
    configs: [setup_mutau.yml]
  - stage: controlplots        # Plotter: draw.py, once per file
    id: plots
    inputs: {hists: hists}
    pdf: true
```

## Public API (`TauFW.Plotter.api`)

`ControlPlots` draws control-histogram files with `draw.py`, run as a separate process with the arguments a user
would type, and checks that plots were written. It needs no ROOT and reads nothing until it runs; the Framework
uses it for its `controlplots` stage. Each file comes with the facts a plan needs before the file exists (era,
channel, tag: the Histogrammer's `control_histograms` artifact, `HistFileInput.from_artifact`).

```python
from TauFW.Plotter.api import ControlPlots, PlotsRequest, HistFileInput
plotter = ControlPlots()                                     # Plotter/ of this CMSSW area; reads and runs nothing
request = PlotsRequest(files=[HistFileInput(path='../Histogrammer/hists/2025/mutau.root', era='2025',
                                            channel='mutau')], pdf=True)
plotter.plan(request)       # CommandPlan: python3 draw.py ../Histogrammer/hists/2025/mutau.root -p; nothing runs
plotter.preflight(request)  # problems (no cmsenv, no ROOT, a missing file); empty: ready
plotter.make(request, logdir='logs')   # RunReport: ok, one log per command, one plots artifact per file
```

## Layout

| Path | What |
|---|---|
| `draw.py` | the command: draws every stack of one or more control-histogram files |
| `python/api/` | `TauFW.Plotter.api`: `ControlPlots`, `PlotsRequest`, `HistFileInput` (the public API above) |
| `python/controlplots.py` | `TauFW.Plotter.controlplots`: `read_control_hists`, `draw_control_plots`, `make_stack`, `draw_stack`, `plot_name`, `plot_text` |
| `plot.py` | LEGACY: prints the command that replaces it (`Histogrammer/fillhists.py`, same options) and exits; nothing runs |
| `python/sample/*.py`, `python/plot/*.py`, `python/methods/QCD_OSSS.py` | BACKWARD COMPATIBILITY: the 13 old module names, each an alias of its new module in the Histogrammer |

The legacy command and the aliases are deleted at the migration point ([TODO.md](../docs/Refactor-2025/TODO.md)
§8). Old scripts keep working until then; new code uses the new names. How to update a script:
[Histogrammer/README.md](../Histogrammer/README.md) ("Old names").

| Old name | New name |
|---|---|
| `TauFW.Plotter.sample.<module>` | `TauFW.Histogrammer.sample.<module>` |
| `TauFW.Plotter.plot.Variable`, `.Selection`, `.Context`, `.string` | `TauFW.Histogrammer.spec.<module>` |
| `TauFW.Plotter.plot.MultiDraw` | `TauFW.Histogrammer.sample.MultiDraw` |
| `TauFW.Plotter.methods.QCD_OSSS` | `TauFW.Histogrammer.methods.QCD_OSSS` |
| `Plotter/plot.py` | `Histogrammer/fillhists.py` |

### How an alias works

Each old module file contains only this (example: `python/sample/utils.py`):

```python
import sys

import TauFW.Histogrammer.sample.utils as _module

sys.modules[__name__] = _module  # the old name now refers to the new module itself
```

So `import TauFW.Plotter.sample.utils` returns the very same module object as
`import TauFW.Histogrammer.sample.utils`: the same functions and classes, and the same module state (the era and
luminosity that `setera` sets and that every `Sample` reads). A copy (`from ... import *`) would not do that: it
would freeze the era and luminosity in the old module. `Tests/Histogrammer/compat/test_compat_paths.py` checks
every alias.

## Rules this module follows

The new Plotter is meant as the example of how a TauFW module is written after the refactor:

1. **No other stage is imported** (PicoProducer, Histogrammer, Fitter); only the shared libraries
   (`TauFW.Utilities`). `Tests/check_import_boundaries.py` enforces it; the only exceptions are the compatibility
   aliases above, listed one by one in `Tests/import_boundary_allowlist.json` with the migration point as their end.
2. **Inputs and outputs are explicit:** the command and the functions get the histogram file and the output
   directory; nothing is looked up in another module's configuration or directory.
3. **The data it reads is a written contract**, versioned, and checked when the file is opened
   ([control histograms](../docs/contracts/control-histograms.md)).
4. **Every public function says what it reads, what it writes and what it returns**; behaviour that is kept on
   purpose (compatibility) is marked as such and has an end.
5. **Byte-identical output is proven, not assumed:** the BBB case `plotter.stack` locks what `plot.py` drew, and the
   drawing from the file must give the same canvases.

Tests: `Tests/Plotter/draw` (no ROOT: names, texts, the contract), `Tests/Plotter/api` (no ROOT: the `draw.py`
commands, the expected plot names, the artifacts), BBB `plotter.stack` (with ROOT).

## Plan

LocalR/architecture/18 (local notes), changelog §24: S1 rename, S2 configs to `Configs/Histogrammer/`, S3 the
histogram file and `draw.py` (done), S4 Framework stages `controlhists` and `controlplots` (done), S5 checks on
lxplus.
