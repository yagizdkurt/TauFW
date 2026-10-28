# TauFW

Framework for tau analysis using NanoAOD at CMS. The main packages are
1. [`PicoProducer`](PicoProducer): Tools to process nanoAOD and make custom analysis ntuples.
2. [`Histogrammer`](Histogrammer): Histograms from the ntuples (samples, normalisation, selections, QCD estimate) and
   the control plots; called `Plotter` until October 2026.
3. [`Plotter`](Plotter): Being rebuilt as a small package that only draws plots from histogram files; today it keeps
   the old `Plotter` names working.
4. [`Fitter`](Fitter): Tools for measurements and fits in combine.

The [`Framework`](Framework) package runs these steps as one pipeline from a recipe file, see
[Running a pipeline](#running-a-pipeline).

Historical studies and retired component workflows are kept in the root
[Legacy archive](Legacy/README.md).

## Installation

### Automatic
Run this in the repo. See the [FastSetup documentation](Docs/Manual/FastSetup.md) for details.
```bash
source setup.sh
```

### Manual

See the [manual installation guide](Docs/Manual/ManualInstallation.md) for manual setup.

## Opening the framework

From the TauFW folder just do
```bash
source setup.sh
```
again. It will automatically setup cms environment and all you need. Then open the framework.
See [Analyses/README.md](Analyses/README.md) for analyses details.

## Contributing responsibly

Before pushing changes or opening a pull request, read the
[mandatory merge request rules](Docs/Develop/Rules.md) and
[legacy code policy](Docs/Develop/LegacyCode.md). Take responsibility for the code you
introduce: document its purpose, check its dependencies, and archive completed
one-off work in the appropriate data-year folder. Include the required legacy
banner and update the inventory; leave clear context instead of unexplained
copies for the next developer.

Run all automated tests quietly with `python3 Tests/run.py all` (see the
[test setup and requirements](Tests/README.md#all-automated-tests-quiet-shortcut)).