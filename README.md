# TauFW

Framework for tau analysis using NanoAOD at CMS. Three main packages are
1. [`PicoProducer`](PicoProducer): Tools to process nanoAOD and make custom analysis ntuples.
2. [`Plotter`](Plotter): Tools for further analysis, auxiliary measurements, validation and plotting.
3. [`Fitter`](Fitter): Tools for measurements and fits in combine. [Under development.]

The [`Framework`](Framework) package runs these steps as one pipeline from a recipe file, see
[Running a pipeline](#running-a-pipeline).

Historical studies and retired component workflows are kept in the root
[Legacy archive](Legacy/README.md).

Run all automated tests quietly with `python3 Tests/run.py all` (see the
[test setup and requirements](Tests/README.md#all-automated-tests-quiet-shortcut)).

## Installation

### Automatic

```bash
git clone https://github.com/cms-tau-pog/TauFW TauFW
cd TauFW
source setup.sh
```

See the [FastSetup documentation](docs/FastSetup.md) for requirements and options.

### Manual

See the [manual installation guide](docs/ManualInstallation.md) for step-by-step
CMSSW, TauFW, and optional dependency setup.

## Running a pipeline

From the TauFW folder, after setting up the CMSSW environment, use the root launcher:
```bash
python3 taufw.py         # interactive menu
python3 taufw.py --help  # available commands
```

See [Analyses/README.md](Analyses/README.md) for analysis bundles (recipe, configs
and Python steps in one directory), stage options, examples, and planning,
starting, or continuing a pipeline.

## Contributing responsibly

Before pushing changes or opening a pull request, read the
[mandatory merge request rules](docs/Rules.md) and
[legacy code policy](docs/LegacyCode.md). Take responsibility for the code you
introduce: document its purpose, check its dependencies, and archive completed
one-off work in the appropriate data-year folder. Include the required legacy
banner and update the inventory; leave clear context instead of unexplained
copies for the next developer.
