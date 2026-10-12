# PicoProducer bug register

Defects found during the 2026 PicoProducer cleanup (branch `Refactor-2025`). They were found by reading the
source; none have been fixed yet unless the **Fix** column names a commit.

Policy (agreed 2026-10-12): bugs are fixed during the refactor, **one fix per commit**, each recorded here.
If a fix changes a BBB baseline, the same commit re-locks it (`python3 Tests/run.py bbb lock --replace`) and
the **Output impact** column explains the difference. A refactor commit never changes a baseline.

**Severity:**
- **crash:** raises an exception on a reachable path.
- **wrong:** silently produces a wrong result or does the wrong thing.
- **latent:** the code is wrong but nothing reaches it today.

**BBB column:** whether a PicoProducer BBB case exercises the path. If it does, the bug's current behavior is in
the baseline, and fixing it changes that baseline on purpose.

## Control plane: CLI, config, jobs

| ID | Location | Symptom | Severity | BBB | Session | Fix | Output impact |
|---|---|---|---|---|---|---|---|
| P01 | `pico/job.py:241`, `pico/config.py:234` | `err.message` (Python 2) inside `except IOError`: the handler itself raises `AttributeError` | crash | no | S4 / S3 | | |
| P02 | `pico/job.py:173` | `--prompt` on an existing job config: `input("..."%(nchunks))` uses `nchunks` before assignment and the string has no placeholder | crash | no | S4 | | |
| P03 | `pico/job.py:839-841` | `.json.gz` job config: `gzip` is not imported, and `file.write(json.dump(jobcfg),indent=2)` is malformed | crash | no | S4 | | |
| P04 | `pico/job.py:204`, `:934` | `--checkqueue 1` ("check once"): the condition `jobs!=None` with `jobs=None` means the queue is never pre-fetched, so it silently falls back to per-sample queries | wrong | no | S4 | | |
| P05 | `pico/job.py:103` | `found = len(samples)>=0` is always true, so "no samples found" is never printed on submit | wrong | yes | S4 | | |
| P06 | `pico/job.py:123` | Per-sample `maxevts` is used only when `<=0`; a positive sample value falls back to the config (the condition is inverted) | wrong | no | S4 | | |
| P07 | `pico/job.py:384` | `checkexpevts==False` is a comparison, not an assignment, so it has no effect | latent | no | S4 | | |
| P08 | `pico/run.py:183,195`, `pico/job.py:119-121` | Option precedence is the opposite of the code comments: channel-config `KEY=VALUE` come after the user's `-E`, so the channel wins | wrong | yes | S4 | | |
| P09 | `pico/job.py:119-121` + `Sample.loadjson` | On resubmit, the already-merged `extraopts` from the job config are merged again with the CLI and channel options, so the options duplicate on every retry | wrong | yes | S4 | | |
| P10 | `pico/run.py:156` | `run -m` defaults to `-1`, and `if maxevts:` is true for -1, so `-m -1` is always appended | wrong (harmless) | yes | S4 | | |
| P11 | `pico/run.py:169` | Local run uses `os.system`; a worker failure is not reported (exit code ignored) | wrong | no | S4 | | |
| P12 | `pico/run.py`, `pico/job.py` vs workers | Callers pass `--opt`, the workers define `--opts`; it only works through argparse prefix matching | latent | yes | S5 | | |
| P13 | `scripts/pico.py:226` | `if` instead of `elif` after `install`: `pico.py install` also prints "subcommand 'install' not implemented!" | wrong | no | S5 | | |
| P14 | `scripts/pico.py:158` | `install` choice is misspelled `'cmmsw'` | latent | no | S5 | | |
| P15 | `scripts/pico.py:85-108` | `status`/`hadd`/`clean` parsers are built before `--prompt`, `-m`, ... are added to the job parent, so these options are missing there. This looks intentional for `-m` (reused for `--maxopenfiles`) but is undocumented | latent | yes | S5 | | |
| P16 | `tools/config.py:192` | `Config.__setattr__`: `key in self._dict[key]` should be `key in self._dict` | latent | no | S3 | | |
| P17 | `tools/config.py:33-37` | Default eras point to `samples_2016.py`/`samples_2017.py`/`samples_2018.py`, which do not exist | wrong | yes | S3 | | |
| P18 | `tools/config.py:76-117` | Reading the config writes `config/config.json` (create/repair). A worker given `-c` can write it on a batch node | wrong | yes | S3 | | |
| P19 | `pico/job.py:975` | `TODO: check if hadd was succesful`: cleanup after `haddclean` is gated only on the command's exit code, not on the merged file (A04) | wrong | yes | S4 | | |

## Storage and batch

| ID | Location | Symptom | Severity | BBB | Session | Fix | Output impact |
|---|---|---|---|---|---|---|---|
| S01 | `batch/SGE.py:7` | Defines `class HTCondor` (copy-paste), so `getbatch('SGE')` fails at `getattr(module,'SGE')`. The body also calls `condor_submit` | crash | no | S3 | | |
| S02 | `batch/utils.py:122` | `getbatch(dict)`: `arg[batch]` raises `NameError` (should be `arg['batch']`) | crash | no | S3 | | |
| S03 | `batch/BatchSystem.py:13` | `__metaclass__ = ABCMeta` has no effect in Python 3, so the abstract methods are not enforced | latent | no | S3 | | |
| S04 | `batch/HTCondor.py:15`, `SLURM.py:14`, `SGE.py:29` | Regex strings with `\d` are not raw strings (DeprecationWarning; a future SyntaxError) | latent | yes | S3 | | |
| S05 | `storage/T2_PSI.py:22`, `T3_PSI.py:22` | `os.path('/scratch/',…)` raises `TypeError` when the class is created, and `T2_PSI` does not import `os` | crash | no | S3 | | |
| S06 | `storage/EOS.py:21` | Assigns `"eos rm"` to `lscmd` instead of `rmcmd`, which breaks `ls` with `eos=True` | wrong | no | S3 | | |
| S07 | `storage/StorageSystem.py:185`, `T2_DESY.py:85` | `isglob` is used but not imported (`hadd` with `$PATH` sources) | crash | no | S3 | | |
| S08 | `storage/StorageSystem.py:112-114` | `cd()`: `ret` is unbound when the storage is not mounted | crash | no | S3 | | |
| S09 | `storage/GridKA_NRG.py` | `rmurl` contains `ls`; `hadd` sources are concatenated without separators | wrong | no | S3 | | |
| S10 | `storage/Sample.py:54` | `dtype = 'mc' # TODO: remove` overrides automatic data type detection for `Sample(...)` without `dtype` | wrong | no | S3 | | |
| S11 | `storage/Sample.py:456` | `self.nevents == nevents` (a comparison) should be an assignment | wrong | no | S3 | | |
| S12 | `storage/Sample.py:391-392` | `loadfiles` docstring comes after a statement, so it is not a docstring | latent | no | S3 | | |
| S13 | `storage/Sample.py:474` | Class name typo `Embdedded` | latent | no | S3 | | |
| S14 | `storage/utils.py:77` | Mutable default `moddict={}` is used as a hidden module cache | latent | yes | S3 | | |
| S15 | `storage/utils.py:161,195` | Production validation imports Plotter's `MultiProcessor` (package cycle A03) | latent | no | S3 | | |
| S16 | `batch/utils.py:25-26` | `HTCondor_NAF` can never be guessed (branch commented out) | latent | no | S3 | | |

## Workers

| ID | Location | Symptom | Severity | BBB | Session | Fix | Output impact |
|---|---|---|---|---|---|---|---|
| W01 | `processors/skimjob.py:24` | `-E/--opts` is parsed and never used | latent | no | S5 | | |
| W02 | `processors/picojob.py:3` | Description line was copied from skimjob | latent | no | S5 | | |
| W03 | `processors/dumpGen.py` | Not referenced anywhere | latent | no | S2 | moved to `legacy/processors/` (not fixed) | none |

## Analysis modules and writers

| ID | Location | Symptom | Severity | BBB | Session | Fix | Output impact |
|---|---|---|---|---|---|---|---|
| A01 | `analysis/ModuleMuTau.py:168`, `ModuleETau.py:155`, `ModuleEMu.py:133`, `ModuleTauTau.py:131`, `ModuleMuTau_nanoV10_DeepTau2p5.py:172`, `ETauFakeRate/ModuleETau.py:201` (and the `legacy/` copies `ModuleMuTau_nanoV10_DeepTau2p1`, `TauES/ModuleMuTau`, `MuTauFakeRate/ModuleMuTau`) | `getlepvetoes(...)` is called without the now-required `era` argument (changed in `eb15fdc`), so a `TypeError` is raised on the first event that reaches the vetoes | crash | no | S6 | | |
| A02 | `analysis/ModuleMuTau.py:40-46` vs `285-302` | Tau ID / e→τ / μ→τ SF tools are commented out but still used for MC with genmatch 1–5 (`AttributeError`); the comments at 293/298 swap muon and electron | crash | no | S6 | | |
| A03 | `analysis/TreeProducerTauPair.py` vs `ModuleTauPair.py:562-566` | With `jec=True`, `met_<unc>`, `mt_1_<unc>` and `dzeta_<unc>` are filled but never declared, and `pzeta_vis` is undefined (the variable is `pzetavis`) | crash | no | S6 | | |
| A04 | `analysis/ModuleEMu.py:198` | Writes `idiso_2`, which `TreeProducerEMu` does not define (probably `idiso_3`) | crash | no | S6 | | |
| A05 | `analysis/HighPT/ModuleDiJet.py:144` | Reads `idisoweight_1`, which `TreeProducerDiJet` does not define | crash | no | S6 | | |
| A06 | `ModuleTauPair.py:18` (and its forks) | `tauSFVersion` stops at 2022, so `ModuleETau`/`ModuleTauTau` raise `KeyError` for 2023+ | crash | no | S6 | | |
| A07 | `analysis/utils.py:467-481` | `getTotalWeight`: `total_w = []` is indexed with `+=` (`IndexError`), and line 480 is outside the inner loop | crash | no | S6 | | |
| A08 | `analysis/utils.py:294,348` | `getmet`/`getmetfilters` always print, ignoring `verb` | wrong (cosmetic) | no | S6 | | |
| A09 | `analysis/utils.py:355` | `loosestIso` hard-codes DeepTau2017v2p1 | wrong | no | S6 | | |
| A10 | `analysis/Run3_DEV/ModuleMuTau.py:34,44` | No trigger for 2025 (`self.trigger` unset); `self.muSFs = 1` for 2024 | crash | no | S6 | | |
| A11 | `legacy/analysis/CheckMuTrigger.py:26` | Trigger threshold attributes are assigned but unused (hard-coded 24 GeV); `trigsf` stays 1.0 | wrong | no | S2 | moved to `legacy/` (not fixed) | none |
| A12 | `ModuleTauPair.py:51` and variants | `recoil` option is stored, but the tool and calls are commented out | latent | no | S6 | | |
| A13 | `import *` chains (now only in `legacy/`) | `datadir` is rebound by BTagTool/PileupTool/JetVetoMapTool/TauTriggerSFs and leaks through star imports. JetTauFakeRate works around it with `replace("/pileup","")`. Session 2 replaced every star import outside `legacy/` by explicit imports of the *same* objects: all maintained modules see the base `datadir`, as before | wrong | no | S6 | | |
| A14 | `analysis/ETauFakeRate/ModuleETau.py:172-174` | Uses an undefined name `fes` (`NameError` on that path); found while resolving star imports | crash | no | S6 | | |

## Corrections

| ID | Location | Symptom | Severity | BBB | Session | Fix | Output impact |
|---|---|---|---|---|---|---|---|
| C01 | `corrections/MuonSFs.py:65` | UL2017 loads `2018_UL/muon_Z.json.gz` | wrong | no | S6 | | |
| C02 | `corrections/MuonSFs.py:102,104` | Prints `sf_id` where the iso key is meant | wrong (cosmetic) | no | S6 | | |
| C03 | `corrections/MuonSFs.py:120,137` | 2024: `sftool_trig = 1.0`, then `.evaluate` raises | crash | no | S6 | | |
| C04 | `corrections/MuonSFs.py:139` | Trigger systematic is taken from `sftool_id` | wrong | no | S6 | | |
| C05 | `corrections/MuonSFs.py` | Unknown era leaves `fname_id=None`, and `os.path.exists(None)` raises `TypeError` | crash | no | S6 | | |
| C06 | `corrections/DYandRecoilCorrlib.py:56,81` | 2025: `fname_id` stays `None` (DY samples crash in the ModuleTauPair constructor); `getDYpTCorr` maps 2024 to `2022postEE` | crash | no | S6 | | |
| C07 | `corrections/ElectronSFs.py:11-14,89` | Stray no-op string literals; no 2024/2025 branch (assertion fails); the 2023 message says "MuonSFs" | crash | no | S6 | | |
| C08 | `corrections/JetVetoMapTool.py` | No 2024 branch, although `Winter24Prompt24_*.root` is in `data/` | wrong | no | S6 | | |
| C09 | `corrections/era_config.py:104-105` | `getjmecalib`: `jmeUncs`/`MET` are used before assignment in the data branch (not called) | latent | no | S6 | | |
| C10 | `legacy/corrections/PreFireTool.py:7,10` | `from corrections import ...` fails, and CMSSW_BASE path building raises without CMSSW | crash | no | S2 | moved to `legacy/` (not fixed) | none |
| C11 | `corrections/RecoilCorrectionTool.py:12` | A correction imports `analysis.utils` (layering inversion); the `RecoilCorrectionTool` class itself is unused | latent | no | S6 | | |
| C12 | `corrections/MetTriggerSF.py:8`, `WmassCorrection.py:7` | Paths are built from `os.getenv('CMSSW_BASE')+…`, bypassing `datadir`; `TypeError` without CMSSW; `data/Wstar/` and `trigger/mettrigger_<era>.root` are absent | crash | no | S6 | | |
| C13 | `corrections/MuonSFs.py:27`, `DYandRecoilCorrlib.py:27` | `getcorr()` is duplicated verbatim; DYandRecoilCorrlib docstrings still say "muon" | latent | no | S6 | | |

## BBB coverage notes

- The control plane (`pico.config`, `pico.run`, `pico.jobs`, `pico.merge`) and the workers (`pico.workers`, with
  `ModuleMuTauSimple`) are covered from Session 1 onwards.
- **No `ModuleTauPair`-based channel module is covered yet.** Those modules need a much larger synthetic
  NanoAOD (jets, MET, PV, electrons, trigger objects, pileup, gen particles) plus jsonpog/correctionlib and
  TauIDSFs payloads. A `pico.channel_tau_pair` case is a **prerequisite for Session 6**, before any analysis or
  corrections code moves. Fixes A01–A13 and C01–C13 must each be checked against that case.
