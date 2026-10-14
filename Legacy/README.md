# Legacy archive

Historical scripts and workflows were consolidated here on **2026-10-14**.

| Folder | Contents | Previous location |
| --- | --- | --- |
| [OldAnalysis/](OldAnalysis/README.md) | Independent retired studies grouped by data-taking year. | `LegacyAnalyses/` |
| [Fitter/](Fitter/README.md) | Retired fitting scripts, configurations and workflow bundles. | `Fitter/Legacy/` |
| [Plotter/](Plotter/README.md) | Historical plotting scripts, sample configurations and school exercises. | `Plotter/Legacy/` |

The internal folder structures and archived implementations are preserved.
Original-location comments record historical paths. The archives are unmaintained;
review their dependencies, working directories and known defects before reuse.
Relative input and output paths still resolve from the original working directory,
unless a script explicitly selects another directory.

Python package archives remain in `Fitter/python/legacy/`,
`PicoProducer/python/legacy/` and `Plotter/python/legacy/` to preserve their
`TauFW.*.legacy` import paths and remaining consumers.

See the [legacy code policy](../docs/LegacyCode.md), the
[component inventory](../docs/Refactor-2025/Legacy.md), and each archive README
for retirement reasons and replacements.
