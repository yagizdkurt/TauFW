# PicoProducer/python/legacy

These files are **unmaintained**. They were moved here on 2026-10-12 during the PicoProducer cleanup
(`Refactor-2025`) instead of being deleted, so their code stays easy to find. Their Git history follows them
(`git log --follow <file>`).

- **Not supported.** Nothing in the framework imports these files, and no test covers them.
- **They may stop working.** Later cleanup sessions rename or move the modules they import (for example
  `analysis.ModuleTauPair` and `analysis.utils`), and the legacy copies will not be updated.
- **Not runnable through `pico.py`.** Its channel loader only finds modules under `analysis/`.
- **To revive a file,** move it back next to the maintained code, update its imports, add a BBB case, and
  record the change in `docs/Refactor-2025.md`.

The originals were under `PicoProducer/python/` (`PicoProducer/scripts/` for `pico2.sh`).

| Legacy path | Original location | Last change | Reason |
|---|---|---|---|
| `analysis/MuTauFakeRate/ModuleTauPair.py` | `analysis/MuTauFakeRate/` | 2025-07-09 | Orphaned fork of `ModuleTauPair`; nothing imports it (its sibling uses the main base class) |
| `analysis/MuTauFakeRate/ModuleMuTau.py` | `analysis/MuTauFakeRate/` | 2024-09-12 | Fork of `ModuleMuTau`; no references; crashes in `getlepvetoes` (BUGS A01) |
| `analysis/Run3_DEV/puppiMET/ModuleTauPair.py`, `ModuleMuTau.py` | `analysis/Run3_DEV/puppiMET/` | 2024-09-12 | PUPPI-MET fork of the Run 3 pair modules; no references since 2024 |
| `analysis/JetTauFakeRate/*.py` (5 files) | `analysis/JetTauFakeRate/` | 2023-05-28 | Jet→τ fake-rate producers; no references since 2022–23; work around the `datadir` leak (BUGS A13) |
| `analysis/ModuleMuTau_nanoV10_DeepTau2p1.py` | `analysis/` | 2024-09-12 | Near copy of `ModuleMuTau_nanoV10_DeepTau2p5` (26 lines differ); no references |
| `analysis/TauES/ModuleMuTau.py` | `analysis/TauES/` | 2024-09-12 | Copy of `ModuleMuTau` for TES; no references |
| `analysis/CheckMuTrigger.py` | `analysis/` | 2021-07-23 | Trigger check; its trigger thresholds are unused (BUGS A11) |
| `analysis/StitchEffs.py` | `analysis/` | 2023-05-30 | One-off stitching-efficiency study; imports Plotter |
| `analysis/GenFilterMuTau.py`, `GenMatcher.py` | `analysis/` | 2023-11-03 | Stand-alone generator-level studies with their own writers |
| `analysis/LQ/ModuleGenLQ.py` | `analysis/LQ/` | 2024-03-13 | Stand-alone leptoquark generator study |
| `analysis/gmin2/ModuleGen_gmin2.py` | `analysis/gmin2/` | 2024-03-13 | Stand-alone g-2 generator study |
| `corrections/BeamSpotTool.py` | `corrections/` | 2023-07-20 | No references |
| `corrections/METCorrectionTool.py` | `corrections/` | 2023-05-28 | Run 2 MET φ corrections; no references |
| `corrections/PreFireTool.py` | `corrections/` | 2020-06-21 | Cannot be imported (`from corrections import ...`, BUGS C10); only commented-out uses |
| `corrections/MuonSFs_ROOT.py` | `corrections/` | 2024-05-03 | ROOT-based predecessor of the correctionlib `MuonSFs`; only `Tests/PicoProducer/testSFs.py` uses it |
| `processors/dumpGen.py` | `processors/` | 2023-10-19 | Stand-alone LHE dumper; the `gen` channel uses `analysis/GenDumper.py` |
| `scripts/pico2.sh` | `scripts/pico2.py` | 2023-05-31 | Python 2 launcher for `pico.py` (a shell script; renamed so `scram b` does not compile it as Python); Python 2 releases are no longer supported |

The tutorial module `analysis/CMSDAS2020/` was **not** moved, because `docs/CMSDAS2020/` still links to it.
