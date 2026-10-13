# Plotter/Legacy

These files are **unmaintained**. They were moved here on 2026-10-13 during the Plotter cleanup
(`Refactor-2025`, see [docs/Refactor-2025.md](../../docs/Refactor-2025/Refactor-2025.md#9-plotter-cleanup-legacy-area))
instead of being deleted, so their code stays easy to find. Their Git history follows them
(`git log --follow <file>`).

There are two legacy areas:

- **`Plotter/Legacy/`** (this folder): scripts and configs. Each keeps its path relative to `Plotter/`
  (e.g. `config/samples_v10.py` → `Legacy/config/samples_v10.py`).
- **[`Plotter/python/legacy/`](../python/legacy/)**: modules and ROOT macros that were under `Plotter/python/`.
  They keep their path relative to `python/` (e.g. `methods/JetToTau_MisID.py` → `legacy/methods/JetToTau_MisID.py`),
  so they stay **importable** as `TauFW.Plotter.legacy.*`. Their imports of each other were updated to the new
  package path. Macros are loaded from the new path, e.g. `loadmacro("python/legacy/corrections/zptweight.C")`.

Notes:

- **Not supported.** Nothing in the framework, Fitter, PicoProducer or the tests uses these files.
- **Sample methods are not found by name any more.** `SampleSet` only looks up `method=...` in
  `TauFW.Plotter.methods`. Import the legacy module first, e.g.
  `import TauFW.Plotter.legacy.methods.JetToTau_MisID`; it attaches the method to `SampleSet`, and then
  `method='JetToTau_MisID'` works.
- **Scripts may not run from here.** They assume the working directory is `Plotter/` (`from config.samples... import`,
  `loadmacro("python/macros/...")`, `-c config/setup_*.yml`). Several were already broken before the move (see below).
- **To revive a file,** move it back to its original location, check its imports, and record the change in
  `docs/Refactor-2025.md`. For new plots, start from `Plotter/plot.py` with `config/samples_v15.py`.

| Legacy path | Last change | Reason |
|---|---|---|
| `plot_CMSPODAS23.py`, `config/samples_v10.py`, `config/setup_mutau_PODAS.yml` | 2023-10-13 | CMS PO&DAS 2023 school (UL2018, NanoAOD v10); linked from `docs/CMSPODAS23` |
| `plots_and_histograms_CMSDAS2020.py` | 2023-06-20 | CMSDAS 2020 school exercise (2017/2018); linked from `docs/CMSDAS2020` |
| `utils/tmux.sh` | 2020-07-18 | Personal shell helper, unrelated to plotting |
| `config/samples_Summer24.py` | 2026-03-11 | Unused variant of `samples_v12.py` |
| `config/samples_Summer24v15.py` | 2026-03-11 | Unused predecessor of `samples_v15.py` (no 2026 / 2526 eras) |
| `config/setup_mutau_v10_2p5.yml` | 2023-03-20 | NanoAOD v10 / DeepTau2p5 mutau setup; no references |
| `python/legacy/corrections/JetToTauFR/` (README, 4 scripts, `tools/`) | 2023-05-31 | Jet→τ fake-rate workflow (UL2018). Python 2 code (`StringIO`, implicit relative imports, `raw_input`), personal AFS `sys.path`; its independent PicoProducer analyzers are in `LegacyAnalyses/README.md` |
| `python/legacy/methods/JetToTau_MisID.py` | 2022-08-11 | Sample method used only by `JetToTauFR/plot_forTauFR.py`; imports `JetToTauFR/tools/fakeFactors.py` |
| `python/legacy/methods/ScaleVariations.py` | 2023-05-28 | Adds `Sample.getenvelope_scalevars`, which nothing calls; cannot be loaded via `method=` (no attribute of the same name) |
| `python/legacy/methods/QCD.C` | 2020-07-13 | Only referenced in a commented-out line of `QCD_OSSS.py`; personal path |
| `python/legacy/corrections/lepEff.C`, `leptonTauFake.C`, `zptweight.C` | 2020-07-05 | Run 2 correction macros, no references; personal paths. PicoProducer and Fitter/Zpt have their own `zptweight.C` |
| `python/legacy/macros/mapGenMatch.C` | 2021-07-15 | No references |

**Kept in place** although they look old, because something still uses them:
`config/samples.py` (Fitter `MuTauFR`, `paper`; `docs/CMSDAS2020`), `config/samples_HighPT.py` (Fitter `HighPT`),
`config/samples_v12.py` (Fitter `ETauFR`) with `plot_v10.py` and `plot_postfit*.py` (`Fitter/TauES_ID/README.md`),
`python/corrections/{pileup,topptweight,tauIDSF}.C`, `python/macros/{loadHist,utils}.C` (`Tests/Plotter/testMacros.py`),
`python/macros/Unroll.cxx` (BBB, Fitter `Zpt`), and `config/setup_tautau.yml` (the only tautau setup).

## One-off analysis archive

Independent analysis studies were moved to [`LegacyAnalyses/`](../../LegacyAnalyses/README.md) on 2026-10-13. Their current locations, purposes and path requirements are documented there. The table above describes files remaining in this component archive.
