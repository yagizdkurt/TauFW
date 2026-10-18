# Histogrammer bug register

The Plotter module was renamed Histogrammer in October 2026 (changelog §21); its bugs keep their IDs (L01, ...) and
the locations below are relative to the module (`config/`, `python/`), so `plot.py` is now `fillhists.py` and
`python/plot/` is now `python/spec/`. Bugs of the new, drawing-only Plotter will get their own register.

Defects in retired workflows are tracked separately in [Legacy/Bugs.md](../../Legacy/Bugs.md).
Latent defects in maintained modules and workflow options remain here.

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
| L05 | `python/plot/string.py` `joinweights` (line ~29; now `Utilities/python/Expressions/_expressions.py`) | a numeric weight `0` should only warn, but the warning formats two values with one `%r`, so the call raises `TypeError`. `Sample.getrdframe` passes the sample scale as a weight, so a sample scaled to exactly 0 would crash histogram filling | latent | registered only; recorded in `Tests/Utilities/test_expressions.py`. Fix the format string (`%r`, `%r`) in its own commit | a zero weight warns and gives `"0*..."` instead of raising |
| L06 | `python/plot/string.py` `replacepattern` (line ~79; now `Utilities/python/Expressions/_expressions.py`) | with several patterns every replacement starts again from the original string, so only the last pattern is applied (`[("w1","a"),("w3","b")]` on `"w1*w2*w3"` gives `"w1*w2*b"`) | latent | registered only: the one caller (`Sample.getrdframe`, `replaceweight=`) passes a single tuple. Recorded in `test_expressions.py` | none for the existing caller |
| L07 | `python/plot/string.py` `joincuts` (line ~48; now `Utilities/python/Expressions/_expressions.py`) | a cut with `\|\|` is bracketed only if it has no parentheses at all, so `"(x)\|\|y"` is joined as `"a>1 && (x)\|\|y"`, where `&&` binds first and the selection is wider than meant | latent | registered only: the `\|\|` selections in `Plotter/config/samples*.py` (`GML`, `GMJ`, `GMF`) are fully bracketed; selections built in Fitter configs and recipes were not checked. Recorded in `test_expressions.py`. A fix needs a bracket-depth check | selections of that form change |
| L08 | `python/api/control_plots.py` `_plot_glob`, `_command` (expects) | the expected plots use only `request.tag`, but `plot.py` names its files with the setup's YAML `tag` plus `-t`, so for a setup with a non-empty `tag` the expected outputs are always missing and the plots stage fails (and `nfiles` is 0) | wrong | R3 (CL §15), checked on lxplus: the expected plots use the setup's tag plus `tag` | a setup with a tag no longer fails the stage |
| L09 | `python/api/control_plots.py` `make` (`nfiles`) | the plot count globs `Plotter/plots/<era>/`, which is shared by all runs, so it also counts plots of earlier runs | wrong | R3 (CL §15), checked on lxplus: each run has its own directory, and the count uses the command's own pattern | |
| L10 | `config/setup_mutau.yml` vs `config/setup_mutau_inclusive.yml` | both have `channel: mutau` and `tag: ""`, so they write the same file names into `plots/<era>/` and the second run overwrites the first | wrong | registered only; `plan` notes it | |
| L11 | `plot.py` (line ~65) + `common/python/tools/root.py` `loadmacro` | `loadmacro("python/macros/mapDecayModes.C")` is relative to the working directory and its result is ignored; outside `Plotter/` the macro is not loaded and the run fails much later, when RDataFrame compiles `mapRecoDM(dm_2)` (only for channels with `tau`) | latent; crash outside `Plotter/` | R3 (CL §15), checked on lxplus: path from `__file__` (the ignored result of `ProcessLine` stays) | none in `Plotter/` |
| L12 | `python/sample/utils.py:119-120` (`getmcsample`) | the `pico=` keyword (a picodir to use instead of the PicoProducer configuration's) is read and overwritten with `""` on the next line, so it is ignored and `$PICODIR` always comes from the configuration | latent | registered only: `getmcsample` has no callers | |
| L13 | `python/api/control_plots.py` `ControlPlots.__init__` (default `find_module`), used by `preflight` | the default module lookup is `importlib.util.find_spec(name) is not None`. If ROOT is already imported in the process and its `__spec__` is None (CMSSW's ROOT on lxplus), `find_spec('ROOT')` raises `ValueError: ROOT.__spec__ is None` instead of answering. Reached by `taufw.py plan` and `advance` of a recipe with production before plots (production's PicoProducer imports ROOT first): `plan` stops with a traceback, and the plots stage of a run raises at preflight (recorded, the run cannot go on) | crash | CL §16 (exception to the no-fix rule: it blocked every recipe with production and plots on lxplus): `_module_exists`, a module already imported counts as found | none: the preflight answers instead of raising |
| L14 | `config/samples_v15.py:338` (`getsampleset`, split `DM`); copied as it is to `python/sample/model.py` | `samples.split(...)` uses the undefined name `samples` (the sample set is `sampleset`), so `split=['DM']` raises `NameError` for channels with one tau | crash (only with `split=['DM']`; no caller passes it) | registered only (CL §20: the model keeps the behaviour) | none |
| L15 | `config/samples_v15.py:243` (`getsampleset`, data of `etau`/`ee`) | the last `else:` evaluates `"SingleElectron_Run%d?"%year` without assigning it, so `dataset` is undefined (`UnboundLocalError`) for electron channels of an era that matches none of the branches before it | latent (none of the eras samples_v15.py supports reaches it) | registered only; the exported templates have no such era | none |
| L16 | `config/samples_v15.py:222,245` (`getsampleset`, data of `tautau`/`emu`) with `common/python/tools/string.py` `getyear` | for era `2526` `getyear` returns the text `'2526'` (no 20xx year in it), and `"Tau_Run%d?"%year` / `"SingleMuon_Run%d?"%year` raise `TypeError` | crash (tautau or emu with era 2526) | registered only; `Configs/Histogrammer/samples/v15_2526.yml` has no `tautau`/`emu` data, so the model raises too (an `IOError` naming the missing kind) | none |
| L17 | `fillhists.py:94-97` (mumu variables `m_ll`, comment "alias: m_ll alias of m_vis") | no alias `m_ll` is defined (not in the 2025 tuples, not in the sample model), so RDataFrame cannot compile the expression (`use of undeclared identifier 'm_ll'`) and the mumu run of `fillhists.py` (the old `plot.py`) makes no plots | crash (`-c mumu` with these variables; found 2026-10-18 on the 2025 tuples, the same with and without `--hists`) | registered only (CL §21) | none |
| L18 | `Fitter/TauES/createinputsTES.py:284-321` (moves to the Histogrammer in plan 16 H1) | the control plots of the inputs, `rebinning` and the plots of the rebinned file are indented inside `if "systematics" in setup:`, so a config without `systematics` makes no control plots and no rebinned file | latent (both maintained configs have `systematics`) | registered only (plan 16 §8, CL §22) | none |
| L19 | `Fitter/TauES/createinputsTES.py:294-299` (moves in H1) | `varprocs` is defined only for channels containing `mumu` or `mutau`; for any other channel the control plots raise `NameError`, after the shapes were written | latent (only mutau and mumu configs) | registered only (plan 16 §8, CL §22) | none |
| L20 | `Fitter/TauES/createinputsTES.py:247-272` with `Fitter/python/plot/datacard.py:69` `createinputs` (both move in H1) | `createinputs` never gets `recreate=True`, so the shape files are opened with `UPDATE`: a second run into the same directory keeps the histograms of the first one that the new config does not write again (a removed TES point stays in the file, and the fit finds it); the `TNamed selection` record is never written | wrong (standalone reruns in `Fitter/`; a Framework run writes into a fresh stage directory) | registered only (plan 16 §8, CL §22) | none in Framework runs |
| L21 | `Fitter/TauES/createinputsTES.py:309-316` (moves in H1) | `rebinning` runs only for the first observable, but the plots of the rebinned file are made for every observable and open rebinned files that do not exist | latent (every config has one observable) | registered only (plan 16 §8, CL §22) | none |
| L22 | `Fitter/python/plot/rebinning.py` `find_binedges`/`regular_binning` (moves to `Histogrammer/python/shapes/` in H1) | if no bin of a region reaches a relative error of 30 % (an empty region, or few events), its bin-edge list keeps only the lower edge (or, when the last bin fails, that edge is replaced by the upper one), `Rebin(0, ...)` returns a null histogram ("Illegal value of ngroup=0") and `newhist.Clone()` raises `ReferenceError`; `createinputsTES.py` stops after the shapes are written, without the rebinned file and its plots | crash (a region with too few events; found with the BBB fixture of `histogrammer.tes_inputs`, which therefore uses 100 copies of the fixture rows) | registered only (CL §22) | none on real data |
| L23 | `Fitter/python/plot/rebinning.py:41` `find_binedges` (moves in H1) | the merged error is accumulated as `err += sqrt(err**2 + e**2)` instead of `err = sqrt(err**2 + e**2)`, so merging bins makes the relative error larger instead of smaller: a bin above 30 % is never rescued by its neighbours (only the last bin is merged backwards) | wrong (rebinned diagnostics only; the fit reads the unrebinned file) | registered only (CL §22) | the rebinned control plots |
| L24 | `Fitter/TauES/createinputsTES.py:290,314,317` `pname` with `TauFW.Fitter.plot.datacard.plotinputs` (both move in H1) | the control-plot name is `...-<era><tag>$TAG.png` and `plotinputs` fills `$TAG` with the tag again: `ztt_m_vis_mt-DM0-202513TeV_mutau13TeV_mutau.png` (no separator after the era, the tag twice) | cosmetic | registered only (CL §22; seen in the case log of `histogrammer.tes_inputs`) | the PNG names |

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
- **L08, L09** `_plot_glob` and the `nfiles` count came with the Plotter API, `c27abb7` (2026-10-13, Part G).
- **L10** `setup_mutau_inclusive.yml` was added in `a6cd524` (2025-04-14, "my setups") as a copy of
  `setup_mutau.yml` with the same channel and tag.
- **L11** `loadmacro("python/macros/mapDecayModes.C")` is from `25ec87c` (2021-07-15, "add DM; implement DM mapping;
  add loadmacro; ..."); `loadmacro` moved to `common/python/tools/root.py` in `e2b48d4` (2024-01-24) and has always
  ignored the result of `ProcessLine`. Correct as long as `plot.py` runs in `Plotter/`.
- **L12** both lines of `getmcsample` (`picodir = kwargs.get('pico', "")`, then `picodir = ""`) came in together
  with the function in `4ad2351` (2022-05-28, "add stitch plotting").
- **L14, L15** came into `samples_v15.py` with the file itself, `68c0a53` (2025-04-21, "2025 and Summer24", a copy of
  `samples_Summer24.py`); the lines are older copies from config to config. Found by the sample-model export (CL §20).
- **L16** era `2526` was added in `eb6b5b3` (2026-08-06, "2026 and 2025+2026 '2526'") to the era tests of
  `samples_v15.py`, but not to the `%d` year patterns of the tautau and emu data; `getyear` finds no year in `'2526'`.
- **L18-L21** (createinputsTES.py, found in the step-2 planning, plan 16): the control-plot block under
  `if "systematics"` (L18) is as old as the script, `9fd9d46` (2021-08-26, "TES combine"; the `systematics` test from
  `409358f`, 2022-02-24); `varprocs` per channel (L19) from `5837e8c` (2023-03-20); `createinputs` without `recreate`
  (L20): the nominal call had `recreate=True` from `9fd9d46` until `58d5fb2` (2022-01-26, "Started changing
  createInput.py to avoid hard coding long lists"), which dropped it; L22 and L23 are as old as `rebinning.py`,
  `6a2e75b` (2024-05-22, "minor changes"); the doubled tag of L24 is as old as the script (`9fd9d46`); the rebinning of the
  first observable (L21) from `f66a886` (2025-12-04).
