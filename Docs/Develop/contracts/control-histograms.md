# Contract: control histograms (`taufw.control_histograms`, version 2)

Written by the **Histogrammer** (`Histogrammer/fillhists.py --hists`, `TauFW.Histogrammer.controlhists`), read by
the **Plotter** (`Plotter/draw.py`, `TauFW.Plotter.controlplots`). The two modules never import each other; this file
is all they share. Introduced in changelog §21 (S3). In a TauFW recipe the Framework carries it from the
`controlhists` stage to the `controlplots` stage (S4): the artifact `{kind: control_histograms, era, config, channel,
tag, file}` names the file and the facts a plan needs before the file exists. The storage layout is `TauFW.Utilities.HistFile` format 1; this
page says what the content means.

## File

One ROOT file per channel setup and era: `hists/<era>/<channel><tag>.root` in the directory `fillhists.py` runs in
(next to its `plots/<era>/`).

File metadata (JSON):

| Key | Meaning |
|---|---|
| `contract` | `"taufw.control_histograms"` |
| `version` | `2`; raised when the meaning of anything below changes (the reader refuses other versions) |
| `channel` | the setup's channel, e.g. `"mutau"` |
| `era` | the era as given to `fillhists.py -y`, e.g. `"2025"` (text) |
| `lumi` | the integrated luminosity [/fb] the MC was normalised with (the Histogrammer's after `setera`: the sample model's `lumi`, or `CMSStyle.lumi_dict` without a sample model), e.g. `110.18`; `null` if the era has none |
| `cme` | the centre-of-mass energy [TeV] of the normalisation (the sample model's `cme`), e.g. `13.6` |
| `tag` | the setup's `tag` plus `fillhists.py -t`: the tag of the plot file names |

## Entries

One entry per stack, in the order `fillhists.py` made them (selection after selection, the stacks of one selection
in the order `SampleSet.getstack` returned them). Entry path: `<selection filename>/<variable filename>`.

Groups (histograms stored under their own names, with every attribute: contents, errors, statistics, fill and line
colours, titles):

| Group | Content |
|---|---|
| `data` | the observed data histogram, or empty |
| `exp` | the expected processes, in stack order (the order `Stack` stacks them), including the data-driven QCD estimate (none if the setup says `qcd: false`, CL §43) |
| `sig` | signal histograms |

The histograms are **as filled**: copies taken right after `SampleSet.getstack`, before any drawing (drawing
divides variable-width bins and replaces the data histogram by a graph). Normalisation, stitching, the QCD method
and blinding are applied, exactly as for the plots of `fillhists.py`.

Entry metadata (JSON):

| Key | Meaning |
|---|---|
| `selection.name` | the selection's file name (used in the plot file name) |
| `selection.title` | the selection's title (the text on the plot) |
| `selection.cut` | the selection string (information) |
| `variable` | the 17 attributes the drawing code reads from a variable, in the context of this selection: `filename, title, xmin, xmax, ymin, ymax, rmin, rmax, ratiorange, binlabels, logx, logy, ymargin, logyrange, position, ncols, dividebins` (`TauFW.Utilities.Drawing` `Plot.__init__`). JSON has no tuples: a tuple comes back as a list. |

## What the reader decides

The Plotter derives from these facts, by the rules `plot.py` had: the plot file name
`<variable filename>_<channel short>-<selection name>-<era><tag>.png` (`mu` -> `m`, `tau` -> `t`) and the text
`<channel in LaTeX>: <selection title>[, <extra text>]`; the CMS label from the era, `lumi` and `cme`
(`CMSStyle.setCMSEra(era, lumi=, cme=)`), so the label shows the luminosity the histograms were normalised with.

## Versions

- 1 (CL §21 S3): `contract`, `version`, `channel`, `era`, `tag`; the Plotter took the label's luminosity from
  `CMSStyle.lumi_dict`.
- 2 (CL §26, 2026-10-19): `lumi`, `cme` added and required. The Plotter reads only version 2; a version 1 file is
  refused with "run fillhists.py --hists, or the controlhists stage, again".

## Checked by

- `Tests/Histogrammer/controlhists`, `Tests/Plotter/draw` (no ROOT): what is written, what is read, the same
  constants on both sides; `Tests/Utilities/test_histfile.py` (round trip with ROOT on lxplus).
- BBB `plotter.stack`: fill, write, read, draw must give the canvases locked with `plot.py` drawing from memory.
