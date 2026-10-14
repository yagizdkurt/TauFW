# Plotter bug register

Defects found while connecting the Plotter to the TauFW Framework (Part G, October 2026, branch `Refactor-2025`).
Same policy as [docs/PicoProducer/BUGS.md](../PicoProducer/BUGS.md): bugs on the path the Framework runs are
fixed with `# BUGS <ID>` comments at the changed lines; others are registered only.

**Severity:** **crash** (raises on a reachable path), **wrong** (silently wrong), **latent** (nothing reaches it).

| ID | Location | Symptom | Severity | Fix | Output impact |
|---|---|---|---|---|---|
| L01 | `plot.py` `plot` (variable lists) | `idDeepTau2018v2p5VSVjet_2` and `idDeepTau2018v2p5VSVSe_2` are not branches of the pico tuples, but are plotted for every channel (also mumu), and the tau-channel list has `VSVSe` instead of `VSe` | wrong | Part G: the two all-channel entries are removed (the tau-channel list has the tau ID variables), `VSVSe` -> `VSe` | the two broken plots are gone; tau channels get a correct `idDeepTau2018v2p5VSe_2_zoom` plot |
| L02 | `config/samples_v15.py:285` (`getsampleset`) vs `python/sample/utils.py:29` (`_getsampleset`) | the file-name pattern is passed as `fname=`, but the generic builder reads `file=`; so `samples.filename` in the Fitter configs and `fname` in `plot.py` are ignored and the default `$PICODIR/$SAMPLE_$CHANNEL$TAG.root` is always used | latent | registered only: every caller uses the default pattern today. A fix must also stop `file=` from reaching the `MC(...)` keyword arguments, so it needs a test with tuples | |
| L03 | `python/plot/utils.py` `sumhists` (line ~176; now `Utilities/python/Drawing/hist_tools.py`) | adds every histogram after the first to the undefined name `sighist` instead of `sumhist`, so any call with two or more histograms raises `NameError` | latent | registered only (no callers). Frozen in the BBB case `drawing.canvas` (`$.tools.sumhists`); fix after the move to `TauFW.Utilities.Drawing` in its own commit with a re-lock | the `drawing.canvas` baseline changes from the `NameError` to the summed histogram |
| L04 | `python/plot/string.py` `estimatelen` (line ~261; now `Utilities/python/Drawing/labels.py`) | `estimatelen(*strings)` calls `unpacklistargs(*strings)`, which takes one argument: calls with two or more strings raise `TypeError`. The only caller (`Plot.drawlegend`, `Plot.py:881`) passes one list, which works | latent | registered only; `drawing.canvas` records the one-list form. Fix with `unpacklistargs(strings)` after the move | none for the existing caller |

## How old

Open bugs only; fixed ones are left out.

- **L02** `fname=` vs `file=`: the mismatch is as old as the plotting configs. The generic `getsampleset` has read the
  pattern from `file` since commit `f17d1b4` (2020-07-13, "add QCD method"). The first sample config,
  `config/samples.py`, was added in commit `289345a` (2020-08-12, "add exaple plotting scripts; clean and debug tools")
  and already passed it as `fname` with `kwargs.setdefault('fname', fname)`. Every later config (including
  `samples_v15.py`, where the line came in with `898278e`, 2025-06-10) copied that line. It never showed because the
  pattern every config passes is the same as the default `$PICODIR/$SAMPLE_$CHANNEL$TAG.root`.
- **L03** `sumhists` has been broken since the day it was written: commit `47cce92` (2024-04-22, "add sumhists").
  That commit created the function with `sighist.Add(hist)` already in it, apparently a copy-paste from
  signal-histogram code. The function has never had a caller, so nobody noticed.
- **L04** `estimatelen`: the line `strings = unpacklistargs(*strings)` comes from commit `c70afa3` (2023-12-19), which
  only renamed `unwraplistargs` -> `unpacklistargs`. The old line was `unwraplistargs(*strings)`, written together
  with `estimatelen` in commit `38f7be3` (2020-07-18, "add Selection; improve gethist unwrapping"), and that one had
  the same problem. The helper has always taken exactly one argument, all the way back to 2020, so passing several
  strings has always crashed. It never showed because the only caller passes one list.
