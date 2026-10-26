# Legacy archive

Known defects are tracked in [Docs/Develop/Bugs.md#legacy](../Docs/Develop/Bugs.md#legacy).

Historical scripts and workflows were consolidated here on **2026-10-14**.

| Folder | Contents | Previous location |
| --- | --- | --- |
| [OldAnalysis/](OldAnalysis/README.md) | Independent retired studies grouped by data-taking year. | `LegacyAnalyses/` |
| [Fitter/](Fitter/README.md) | Retired fitting scripts, configurations and workflow bundles. | `Fitter/Legacy/` |
| [Plotter/](Plotter/README.md) | Historical plotting scripts, sample configurations and school exercises. | `Plotter/Legacy/` |
| [PicoProducer/python/](PicoProducer/python/README.md) | Archived analyzers, correction tools and campaign production scripts. | `PicoProducer/python/legacy/` |

The internal folder structures and archived implementations are preserved.
Original-location comments record historical paths. The archives are unmaintained;
review their dependencies, working directories and known defects before reuse.
Relative input and output paths still resolve from the original working directory,
unless a script explicitly selects another directory.

Python modules, helpers and ROOT macros are also consolidated here in
`Legacy/Fitter/python/`, `Legacy/PicoProducer/python/` and `Legacy/Plotter/python/`.
Their internal package structure is preserved. Explicit archive imports use
`Legacy.<Component>.python.*`; put the checkout root on `PYTHONPATH`, for example
`export PYTHONPATH="/path/to/TauFW${PYTHONPATH:+:$PYTHONPATH}"`.
The maintained `TauFW.*` packages still require the usual TauFW/CMSSW setup.
The old `TauFW.*.legacy` imports are retired. The standalone muon scale-factor
comparison adds its checkout root before importing the archived class.

See the [legacy code policy](../Docs/Develop/LegacyCode.md), the
[component inventory](../Docs/Develop/Refactor-2025/Legacy.md), and each archive README
for retirement reasons and replacements.
