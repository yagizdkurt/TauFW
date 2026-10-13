# PicoProducer bug register

Defects found during the 2026 PicoProducer cleanup (branch `Refactor-2025`). They were found by reading the
source. A bug is fixed when the **Fix** column names the part that fixed it.

Policy (agreed 2026-10-12): bugs are fixed during the refactor and each fix is recorded here. A restructuring
commit never changes behavior or a BBB baseline. The fixes of a part are applied together, after its
restructuring, in a separate commit (e.g. Part 3B), with `# BUGS <ID>` comments at the changed lines.
If a fix changes a BBB baseline, that commit re-locks it (`python3 Tests/run.py bbb lock --replace`) and the
**Output impact** column explains the difference. BBB check/lock are quiet by default; add `-v` for full
worker output, or `--tail N` to adjust failure tails. Lock logs both runs per case; see the
[test runner instructions](../../Tests/README.md#bbb-exact-data-and-schema-regression-tests).

**Severity:**
- **crash:** raises an exception on a reachable path.
- **wrong:** silently produces a wrong result or does the wrong thing.
- **latent:** the code is wrong but nothing reaches it today.

**BBB column:** whether a PicoProducer BBB case exercises the path. If it does, the bug's current behavior is in
the baseline, and fixing it changes that baseline on purpose.

## Control plane: CLI, config, jobs

| ID | Location | Symptom | Severity | BBB | Session | Fix | Output impact |
|---|---|---|---|---|---|---|---|
| P01 | `jobs/pipeline.py` `iter_plans` (was `pico/job.py:241`), `cli/config.py` `main_write` (was `pico/config.py:234`) | `err.message` (Python 2) inside `except IOError`: the handler itself raises `AttributeError` | crash | no | S4 / S3 | Part 4B-1: `str(err)` | none (the error message is printed instead of a crash) |
| P02 | `cli/jobs.py` `_Prompt.existing` (was `pico/job.py:173`) | `--prompt` on an existing job config: `input("..."%(nchunks))` uses `nchunks` before assignment and the string has no placeholder | crash | no | S4 | Part 4B-1: the prompt has no format argument | none for BBB. `submit --prompt` on an existing job config asks instead of crashing (the answers are still inverted until P20 is fixed) |
| P03 | `jobs/jobconfig.py` `write_jobcfg` (was `pico/job.py:839-841`) | `.json.gz` job config: `gzip` is not imported, and `file.write(json.dump(jobcfg),indent=2)` is malformed | crash | no | S4 | Part 4B-1: `import gzip`; `json.dump(jobcfg,file,indent=2)` | none (no caller writes `.json.gz` today) |
| P04 | `jobs/pipeline.py` `iter_plans`, `api/producer.py` `_queue_once` (was `pico/job.py:204`, `:934`) | `--checkqueue 1` ("check once"): the condition `jobs!=None` with `jobs=None` means the queue is never pre-fetched, so it silently falls back to per-sample queries | wrong | no | S4 | Part 4B-2: `jobs is None`, in `iter_plans` and `main_status` | `--checkqueue 1` now queries the queue once and finds pending jobs; before, it did not check the queue at all. Not in BBB (cases use the default -1) |
| P05 | `jobs/pipeline.py` `iter_plans` (was `pico/job.py:103`) | `found = len(samples)>=0` is always true, so "no samples found" is never printed on submit | wrong | yes | S4 | Part 4B-2: `len(samples)>0` | `submit` with no matching sample prints "Did not find any samples ...". BBB unchanged (every `submit` matches samples) |
| P06 | `jobs/planner.py` `sample_layout` (was `pico/job.py:123`) | Per-sample `maxevts` is used only when `<=0`; a positive sample value falls back to the config (the condition is inverted) | wrong | no | S4 | Part 4B-2: the sample value is used when `>0` | A sample with `maxevts>0` now splits its jobs by events; a sample without it now uses `maxevtsperjob` from the configuration (before, that was ignored unless the sample set a positive value). BBB unchanged (`maxevtsperjob=-1`) |
| P07 | `jobs/status.py` `check_sample` (was `pico/job.py:384`) | `checkexpevts==False` is a comparison, not an assignment, so it has no effect | latent | no | S4 | Part 4B-1: `checkexpevts = False` | none (`None` and `False` both disable the comparison) |
| P08 | `jobs/worker_command.py` `resolve_worker`, `jobs/planner.py` `sample_layout` (was `pico/run.py:183,195`, `pico/job.py:119-121`) | Option precedence is the opposite of the code comments: channel-config `KEY=VALUE` come after the user's `-E`, so the channel wins | wrong | yes | S4 | Part 4B-3: `module_options(worker, sampleopts)` = channel, sample, user; `WorkerSpec` keeps the channel (`chopts`) and user (`useropts`) options apart | **BBB `pico.run`, `pico.jobs`** (re-lock): the `--opt` lists start with the channel options. See [details](#p08-p09-p10-module-options-and-run--m) |
| P09 | `jobs/planner.py` `sample_layout` + `Sample.loadjson` (was `pico/job.py:119-121`) | On resubmit, the already-merged `extraopts` from the job config are merged again with the CLI and channel options, so the options duplicate on every retry | wrong | yes | S4 | Part 4B-3: `resubmit_options(previous, worker)`: the previous try's options, then new user options not already in them | **BBB `pico.jobs`** (re-lock): resubmitted job lists and job configs no longer repeat the channel options. See [details](#p08-p09-p10-module-options-and-run--m) |
| P10 | `jobs/worker_command.py` `run_command` (was `pico/run.py:156`) | `run -m` defaults to `-1`, and `if maxevts:` is true for -1, so `-m -1` is always appended | wrong (harmless) | yes | S4 | Part 4B-3: `-m` only for `maxevts>0` | **BBB `pico.run`** (re-lock): `-m -1` is gone from the "Executing:" lines. See [details](#p08-p09-p10-module-options-and-run--m) |
| P11 | `jobs/local.py` `execute_run` (was `pico/run.py:169`) | Local run uses `os.system`; a worker failure is not reported (exit code ignored) | wrong | no | S4 | Part 4B-2: `subprocess.call`; a non-zero exit code is reported per run and summarized at the end | `pico.py run` warns when a worker fails. Not in BBB (`run` cases are dry) |
| P12 | `jobs/worker_command.py` vs workers (was `pico/run.py`, `pico/job.py`) | Callers pass `--opt`, the workers define `--opts`; it only works through argparse prefix matching | latent | yes | S5 | Part 5B: callers pass `--opts` | **BBB `pico.run`, `pico.jobs`** (re-lock): `--opt` becomes `--opts` in the "Executing:" lines and job lists. The workers parse the same options |
| P13 | `cli/__init__.py` `dispatch` (was `scripts/pico.py:226`) | `if` instead of `elif` after `install`: `pico.py install` also prints "subcommand 'install' not implemented!" | wrong | no | S5 | Part 5B: `install` is a regular entry of the `cli.COMMANDS` table | `pico.py install` no longer prints "not implemented" (it is still a stub). Not in BBB |
| P14 | `cli/parser.py` (was `scripts/pico.py:158`) | `install` choice is misspelled `'cmmsw'` | latent | no | S5 | Part 5B: `cmssw` | `pico.py install cmssw` is accepted; `cmmsw` is rejected. Not in BBB |
| P15 | `cli/parser.py` `build_parser` (was `scripts/pico.py:85-108`) | `status`/`hadd`/`clean` parsers are built before `--prompt`, `-m`, ... are added to the job parent, so these options are missing there. This looks intentional for `-m` (reused for `--maxopenfiles`) but is undocumented | latent | yes | S5 | Won't fix (Part 5B): documented in `build_parser`. `status`/`hadd`/`clean` must not take the submission options, and `hadd` reuses `-m` for `--maxopenfiles` | none |
| P16 | `settings/model.py` (`Config.__setattr__`; was `tools/config.py:192`) | `key in self._dict[key]` should be `key in self._dict`: setting a private attribute such as `CONFIG._path` raised `KeyError` | latent | no | S3 | Part 3B: `key in self._dict` | none (no caller sets private attributes) |
| P17 | `settings/defaults.py` (was `tools/config.py:33-37`) | Default eras pointed to `samples_2016.py`/`samples_2017.py`/`samples_2018.py`, which do not exist; `config/config_example.json` pointed to the missing `samples_UL2016.py` and `tutorial/samples_2022_postEE.py` | wrong | yes | S3 | Part 3B: defaults are the catalogs that exist (`UL2016_preVFP`, `UL2016_postVFP`, `UL2017`, `UL2018`, `2022_preEE`, `2022_postEE`, `2023C`, `2023D`, `2024`, `2025`); example config updated | **BBB `pico.config`**: `fresh.values.eras` changes (re-lock). Only fresh installations are affected; existing `config.json` files keep their eras. See [details](#p17-default-eras-pointed-to-deleted-catalogs) |
| P18 | `settings/store.py` (was `tools/config.py:76-117`) | Reading the config created or rewrote `config/config.json`, also from a batch worker (`picojob.py -c`), Plotter (`$PICODIR`) or a script | wrong | yes | S3 | Part 3B: `getconfig(write=False)` by default; only `pico.py` (`pico/common.py`) passes `write=True`. Library readers get missing keys repaired in memory and a warning if the file is missing | none for `pico.py` (BBB unchanged); workers/Plotter/scripts no longer write the file |
| P19 | `jobs/merge.py` `merge_sample` (was `pico/job.py:975`) | `TODO: check if hadd was succesful`: cleanup after `haddclean` is gated only on the command's exit code, not on the merged file (A04) | wrong | yes | S4 | Part 4B-2: before cleaning after a merge, `validated()` requires the merged tuple to be readable (`isvalid`) and, with event counting, to hold the processed events of the job output; otherwise the job output is kept with a warning | none for valid merges (BBB `pico.merge` unchanged); a corrupt or incomplete merged tuple no longer leads to the deletion of the job output |
| P20 | `cli/jobs.py` `_Prompt.existing` + `jobs/pipeline.py` (was `pico/job.py:177-182`) | `submit --prompt` on an existing job config: answering `y` (submit) or `f` (submit all) skipped the sample and `n` submitted it (the `skip` flag was set on the wrong branches). Unreachable today because of P02 | wrong | no | S4 | Part 4B-2: `y` and `f` submit, `n` skips | `submit --prompt` on an existing job config does what the answer says. Not in BBB |
| P21 | `api/producer.py` `status` (was the status branch of `pico/job.py` `main_status`) | `pico.py status --checkexpevts` has no effect: the status-only branch does not pass `checkexpevts` to the status check (`hadd`/`clean` and `resubmit` do), so it falls back to `False` | wrong | no | S4 | Part 4B-2: `checkexpevts` is passed | `pico.py status` now warns about chunks with an unexpected number of events by default for analysis channels, like `hadd` and `resubmit` already did. BBB `pico.jobs` unchanged (it keeps only the summary lines) |
| P22 | `jobs/status.py` `check_sample` (was `pico/job.py:361`) | Checking the status creates the output directory (`getstorage(outdir,ensure=True)`), so `status`, and the read-only `status()`/`plan()` of the coming API, write to storage | wrong (side effect) | no | S4 | Part 4B-2: `getstorage(outdir)` without `ensure` | checking the status no longer creates a missing output directory (a warning says it is missing). BBB unchanged (submission creates it) |
| P23 | `jobs/merge.py` `cleanup_commands` (was `pico/job.py:978`) | Cleanup decides whether other jobs share the job directory with `len(glob(job*_try*)) >= len(glob(job*<postfix>_try*))`. The first pattern includes the second, so the test is always true and the whole job directory is removed: `haddclean`/`clean` of one tag also deletes the job configs, job lists and logs of other tags in the same directory | wrong (data loss) | no | S4 | Part 4B-2: `<=`: the whole directory is removed only if all its job configs belong to this sample; otherwise only the sample's job outputs, job configs and logs | cleaning one tag keeps the job files of other tags. BBB `pico.merge` unchanged (one job per directory) |

## Storage and batch

| ID | Location | Symptom | Severity | BBB | Session | Fix | Output impact |
|---|---|---|---|---|---|---|---|
| S01 | `batch/sge.py` (was `batch/SGE.py:7`) | Defined `class HTCondor` (copy-paste of the HTCondor adapter), so `getbatch('SGE')` failed; the body called `condor_submit` | crash | no | S3 | Part 3B: rewritten as a real `SGE` adapter: `qsub -t 1-N` array jobs (N = lines in the task list), `-N/-q/-l h_rt/-o` options, `qstat -u $USER` parsing with task ranges; registered in `batch.factory.SYSTEMS`. **Not run on an SGE site** (none available) | none (was unusable) |
| S02 | `batch/factory.py` (was `batch/utils.py:122`) | `getbatch(dict)`: `arg[batch]` raised `NameError` | crash | no | S3 | Part 3B: `arg['batch']` | none |
| S03 | `batch/base.py` (was `batch/BatchSystem.py:13`) | Python 2 `__metaclass__ = ABCMeta` has no effect in Python 3, so the abstract methods were not enforced | latent | no | S3 | Part 3B: `class BatchSystem(object,metaclass=ABCMeta)`. All adapters implement `submit`, `status` and `jobs` | none |
| S04 | `batch/htcondor.py`, `batch/slurm.py`, `workers/skimjob.py:104`, `cli/config.py:313` (was `batch/HTCondor.py:15`, `SLURM.py:14`, `SGE.py:29`) | Non-raw strings with invalid escapes (`\d`, `\$`, `\,`): `SyntaxWarning` since Python 3.12, a future `SyntaxError` | latent | yes | S3 | Part 3B: raw strings, or an escaped backslash; the string values are identical | none |
| S05 | `storage/t2_psi.py`, `storage/t3_psi.py` (was `T2_PSI.py:22`, `T3_PSI.py:22`) | `os.path('/scratch/',…)` raised `TypeError` when the adapter was created; `T2_PSI` did not import `os` | crash | no | S3 | Part 3B: `os.path.join(...)`; `import os` | none (was unusable) |
| S06 | `storage/eos.py` (was `EOS.py:21`) | With `eos=True`, `"eos rm"` was assigned to `lscmd`, so listing ran `eos rm` and removal used the default command | wrong | no | S3 | Part 3B: `rmcmd = "eos rm -r"` (`-r`, like the default `rm -rf`) | none (`eos=True` is not used by pico.py) |
| S07 | `storage/base.py`, `storage/t2_desy.py` (was `StorageSystem.py:185`, `T2_DESY.py:85`) | `isglob` used but not imported: `hadd` of `$PATH` glob sources with a file URL raised `NameError` | crash | no | S3 | Part 3B: `from TauFW.common.tools.string import isglob` | none |
| S08 | `storage/base.py` (was `StorageSystem.py:112-114`) | `cd()`: `ret` was unbound when the storage is not mounted (`UnboundLocalError`) | crash | no | S3 | Part 3B: `ret = None` first | none |
| S09 | `storage/gridka_nrg.py` (was `GridKA_NRG.py`) | `rmurl` contained `ls` (removal listed instead); `hadd` sources were concatenated without separators | wrong | no | S3 | Part 3B: `rmurl = 'root://cmsxrootd-kit.gridka.de/ rm '`; a space after each source | GridKA only: `rm` removes, multi-file `hadd` works |
| S10 | `datasets/sample.py` (was `storage/Sample.py:54`) | `dtype = 'mc' # TODO: remove` overrode automatic data type detection for `Sample(...)` without `dtype` | wrong | no | S3 | Part 3B: detection restored ('embed' for Embed paths, 'data' for `/Run20xx`, otherwise 'mc' as before), with a **warning** whenever it is not 'mc' | `Sample(...)` without `dtype` on a data/embedded DAS path is now 'data'/'embed'. No catalog in the repository is affected (all use `MC`/`Data`); private catalogs see the warning |
| S11 | `datasets/sample.py` (`loadfiles`; was `storage/Sample.py:456`) | `self.nevents == nevents` (a comparison) after the mismatch warning: the stored count was kept | wrong | no | S3 | Part 3B: `self.nevents = nevents` | Samples with an explicit `nevents` that disagrees with the per-file counts in their file list now use the file sum (after the existing warning) |
| S12 | `datasets/sample.py` (`loadfiles`; was `storage/Sample.py:391-392`) | Docstring placed after a statement, so it was not a docstring | latent | no | S3 | Part 3B: moved first | none |
| S13 | `datasets/sample.py` (was `storage/Sample.py:474`) | Class name typo `Embdedded` | latent | no | S3 | Part 3B: renamed `Embedded`; the old name is only kept in the compatibility re-export `storage/Sample.py` | none |
| S14 | `datasets/catalog.py` (was `storage/utils.py:77`) | Mutable default `moddict={}` was a hidden module cache shared by all calls | latent | yes | S3 | Part 3B: `moddict=None` gives a fresh dictionary; callers that pass one (pico run/submit) are unchanged | none (Python caches imported modules anyway) |
| S15 | `storage/validation.py` (was `storage/utils.py:161,195`) | Production validation imported Plotter's `MultiProcessor` (package cycle A03) | latent | no | S3 | Part 3A: `MultiProcessor` moved to `TauFW.common.tools.parallel`; since changelog §15 `TauFW.Utilities.Process.ParallelProcessor` | none |
| S16 | `settings/defaults.py` (`guess_batch`; was `batch/utils.py:25-26`) | `HTCondor_NAF` can never be guessed (branch commented out) | latent | no | S3 | Won't fix: the commented branch tested `'etp'`, which the KIT branch already matches; NAF users select it explicitly (`pico.py set batch HTCondor_NAF`) | none |

## Workers

| ID | Location | Symptom | Severity | BBB | Session | Fix | Output impact |
|---|---|---|---|---|---|---|---|
| W01 | `workers/skimjob.py:24` (was `processors/`) | `-E/--opts` is parsed and never used | latent | no | S5 | Won't fix (Part 5B): pico.py passes the same `--opts` to every worker; skimjob accepts and ignores them | none |
| W02 | `workers/picojob.py:3` (was `processors/`) | Description line was copied from skimjob | latent | no | S5 | Part 5B: the description says what picojob.py does | none |
| W03 | `processors/dumpGen.py` | Not referenced anywhere | latent | no | S2 | moved to `LegacyAnalyses/2018/dumpGen.py` (not fixed) | none |

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
| A11 | `LegacyAnalyses/2016-2017/CheckMuTrigger.py:26` | Trigger threshold attributes are assigned but unused (hard-coded 24 GeV); `trigsf` stays 1.0 | wrong | no | S2 | moved to `legacy/` (not fixed) | none |
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

## Details of fixes that change a BBB baseline

### P17: default eras pointed to deleted catalogs

**Fixed in:** Part 3B (`d8046af`), `settings/defaults.py` and `config/config_example.json`.

**Origin.**
- The defaults in `getdefaultconfig` (formerly `tools/config.py`) map eras `2016`, `2017` and `2018` to
  `samples_2016.py`, `samples_2017.py` and `samples_2018.py`. These catalogs were deleted on 2024-02-19
  (`c663833`, "remove old sample lists"), but the defaults were not updated.
- `config/config_example.json` refers to `samples_UL2016.py`, which was split into `UL2016_preVFP`/`UL2016_postVFP`
  in 2021 (`7d1d5d4`). It also refers to `tutorial/samples_2022_postEE.py`, which does not exist (the catalog is
  `samples/samples_2022_postEE.py`).

**Symptom.** In a fresh installation (no `config/config.json`), `pico.py` created the configuration with these
eras. Any command that reads samples for them then failed, for example:
```
pico.py run -y 2018 -c mutau
IOError: Did not find file samples/samples_2018.py.
```
Users only got a working setup by linking eras themselves (`pico.py era <era> <catalog>`).

**Fix.** The default eras are now the top-level catalogs in `PicoProducer/samples/` (nanoAOD-version variants
such as `*_nanoV10.py` and `samples_2024v15.py` are left for explicit linking):

| Era | Catalog |
|---|---|
| `UL2016_preVFP` | `samples_UL2016_preVFP.py` |
| `UL2016_postVFP` | `samples_UL2016_postVFP.py` |
| `UL2017` | `samples_UL2017.py` |
| `UL2018` | `samples_UL2018.py` |
| `2022_preEE` | `samples_2022_preEE.py` |
| `2022_postEE` | `samples_2022_postEE.py` |
| `2023C` | `samples_2023C.py` |
| `2023D` | `samples_2023D.py` |
| `2024` | `samples_2024.py` |
| `2025` | `samples_2025.py` |

The example config now lists `UL2016_preVFP`, `UL2016_postVFP`, `UL2017`, `UL2018` and `2022_postEE` with
existing catalogs.

**Who is affected.**
- **Fresh installations only.** An existing `config/config.json` is never overwritten; missing keys are filled
  in, but an existing `eras` dictionary is kept as it is.
- To adopt the new defaults, link single eras with `pico.py era UL2018 samples_UL2018.py`, or reset the whole
  configuration with `pico.py set all default`. That also resets channels and paths, so check `pico.py list`
  first.

**Baseline change (BBB `pico.config`).** Only `$.output.fresh.values.eras` differs:
- removed: `2016: samples_2016.py`, `2017: samples_2017.py`, `2018: samples_2018.py`;
- added: the ten eras in the table above.

`fresh.keys`, `recovered`, `edits` and `list` are unchanged, because those steps use the test's own
configuration. The baseline was re-locked with `python3 Tests/run.py bbb lock --replace`. Only
`Tests/BBB/baselines/pico.config.json` and `manifest.json` change.

### P08, P09, P10: module options and `run -m`

**Fixed in:** Part 4B-3, `jobs/worker_command.py` (`module_options`, `resubmit_options`, `run_command`),
`jobs/planner.py` (`sample_layout`), `jobs/local.py`.

**Symptoms.**
- P08: the worker applies `--opt KEY=VALUE` in order, so a later value of a key wins. The list was
  `sample + user (-E) + channel`, so the channel table (`"ModuleMuTau tes=1.0"`) silently overrode a user's
  `-E tes=1.1`, the opposite of the comments ("allow overwrite from command line").
- P09: on `resubmit` the sample's options come from the previous job config, where they are already merged.
  They were merged again with the user and channel options, so each retry appended the channel options once more
  (`'zpt=True' 'tes=1.0' 'tes=1.0'` after one resubmission).
- P10: `pico.py run` has `-m -1` as default and passed `-m -1` to the worker on every run (harmless, the worker
  treats it as "all events").

**Fix.** Precedence is now channel < sample < user, so the most specific setting wins. A resubmission reuses the
previous try's list unchanged and appends only new user options. `run` passes `-m` only for a positive value.

**Baseline changes (re-lock `pico.run` and `pico.jobs`).**
- `pico.run`: `--opt 'zpt=True' 'a=1' 'b=2' 'tes=1.0'` becomes `--opt 'tes=1.0' 'zpt=True' 'a=1' 'b=2'`; `-m -1` is
  removed from three commands (the `-m 100` run keeps it).
- `pico.jobs`: job lists and the `extraopts` of the job configs start with `'tes=1.0'`; the resubmitted DY job
  (try 2) has `'tes=1.0' 'zpt=True'` instead of `'zpt=True' 'tes=1.0' 'tes=1.0'`.
- `pico.merge` is unchanged (it snapshots file names and merged tuples, not job lists).

