# TauFW Plotter

> **Being rebuilt (October 2026, changelog §24 of [Refactor-2025.md](../docs/Refactor-2025/Refactor-2025.md)).**
> The module that was called Plotter until now is the [Histogrammer](../Histogrammer/README.md): it fills
> histograms from pico tuples. This directory is the start of a new, small Plotter that only **draws**.
> Today it holds nothing but backward compatibility; the drawing code arrives in steps S3-S4 of the plan.

## What the Plotter will be

The Plotter turns histogram files into plots. It does not read tuples, does not know about samples, cross sections
or selections, and does not import the Histogrammer (or any other TauFW stage):

```text
pico tuples ──▶ Histogrammer (fillhists.py) ──▶ histogram file ──▶ Plotter (draw.py) ──▶ PNG / PDF
                fills, normalises, QCD           styled histograms     reads, stacks,
                                                 + drawing metadata    draws the ratio, saves
```

- **Input:** a histogram file written by the Histogrammer: per selection and variable the data, the expected
  processes in stack order and the signals (already coloured and titled), plus the few drawing settings of the
  variable (axis title, ranges, log scale, legend position, ...). Its layout is a written data contract.
- **Output:** the plots, drawn with the shared drawing library (`TauFW.Utilities.Drawing`: `Stack`, `Plot`,
  `CMSStyle`), so a plot made from the file is pixel for pixel the plot `plot.py` made from memory.
- **Command:** `python3 Plotter/draw.py <histogram file> [options]`; in the Framework, the `plots` stage reads the
  file that the histogram stage of the same recipe wrote.
- **Why separate:** redrawing (legend, axis, text) no longer refills histograms from tuples, which takes hours on
  full data; the Plotter can be tested with a small ROOT file, without tuples.

## What is here today

| Path | What |
|---|---|
| `plot.py` | LEGACY: prints the command that replaces it (`Histogrammer/fillhists.py`, same options) and exits; nothing runs |
| `python/sample/*.py`, `python/plot/*.py`, `python/methods/QCD_OSSS.py` | BACKWARD COMPATIBILITY: the 13 old module names, each an alias of its new module in the Histogrammer |

Both are deleted at the migration point ([TODO.md](../docs/Refactor-2025/TODO.md) §8). Old scripts keep working
until then; new code uses the new names. How to update a script: [Histogrammer/README.md](../Histogrammer/README.md)
("Old names").

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
2. **Inputs and outputs are explicit:** the command and the API get the histogram file and the output directory;
   nothing is looked up in another module's configuration or directory.
3. **The data it reads is a written contract**, versioned, and checked when the file is opened.
4. **Every public function says what it reads, what it writes and what it returns**; behaviour that is kept on
   purpose (compatibility) is marked as such and has an end.
5. **Byte-identical output is proven, not assumed:** the BBB case `plotter.stack` locks what `plot.py` drew, and the
   drawing from the file must give the same canvases.

## Plan

LocalR/architecture/18 (local notes), changelog §24: S1 rename (done), S2 configs to `Configs/Histogrammer/`,
S3 histogram file + `draw.py`, S4 Framework stages, S5 checks on lxplus.
