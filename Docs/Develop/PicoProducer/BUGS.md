# PicoProducer bug register

Defects found during the 2026 PicoProducer cleanup (branch `Refactor-2025`). They were found by reading the
source. A bug is fixed when the **Fix** column names the part that fixed it.

Policy (agreed 2026-10-12): bugs are fixed during the refactor and each fix is recorded here. A restructuring
commit never changes behavior or a BBB baseline. The fixes of a part are applied together, after its
restructuring, in a separate commit (e.g. Part 3B), with `# BUGS <ID>` comments at the changed lines.
If a fix changes a BBB baseline, that commit re-locks it (`python3 Tests/run.py bbb lock --replace`) and the
**Output impact** column explains the difference. BBB check/lock are quiet by default; add `-v` for full
worker output, or `--tail N` to adjust failure tails. Lock logs both runs per case; see the
[test runner instructions](../../../Tests/README.md#bbb-exact-data-and-schema-regression-tests).

**Severity:**
- **crash:** raises an exception on a reachable path.
- **wrong:** silently produces a wrong result or does the wrong thing.
- **latent:** the code is wrong but nothing reaches it today.

**BBB column:** whether a PicoProducer BBB case exercises the path. If it does, the bug's current behavior is in
the baseline, and fixing it changes that baseline on purpose.

Legacy-only entries W03, A11, A13 and C10, plus the archived copies affected by A01,
are recorded in [Legacy/Bugs.md](../../../Legacy/Bugs.md#picoproducer). Maintained paths,
including latent and off-Framework defects, stay here.

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
| S15 | `storage/validation.py` (was `storage/utils.py:161,195`) | Production validation imported Plotter's `MultiProcessor` (package cycle A03) | latent | no | S3 | Part 3A: `MultiProcessor` moved to `TauFW.common.tools.parallel`; since changelog §13 `TauFW.Utilities.Process.ParallelProcessor` | none |
| S16 | `settings/defaults.py` (`guess_batch`; was `batch/utils.py:25-26`) | `HTCondor_NAF` can never be guessed (branch commented out) | latent | no | S3 | Won't fix: the commented branch tested `'etp'`, which the KIT branch already matches; NAF users select it explicitly (`pico.py set batch HTCondor_NAF`) | none |
| S17 | `datasets/sample.py` `Sample.loadjson` (the DAS path check at `:117-120`) | `loadjson` rebuilds the sample from a job config without `store`/`storage` (the job config does not keep it), so the "DAS path ... has wrong format. Need /SAMPLE/CAMPAIGN/TIER." check runs as if the sample came from DAS. Every sample of a catalog with private storage and a short path (`"/DYto2TautoMuTauh_M-50", store=...` in `samples/samples_2022_postEE.py`) warns on every `status`/resubmit, once or twice per sample and channel; the jobs read the right files. The same code was in `storage/Sample.py` before the S3 cleanup. Seen on lxplus on 2026-10-17 (CL §16 production test). | wrong (message only) | no | — | registered only | none: the warning goes away |

## Workers

| ID | Location | Symptom | Severity | BBB | Session | Fix | Output impact |
|---|---|---|---|---|---|---|---|
| W01 | `workers/skimjob.py:24` (was `processors/`) | `-E/--opts` is parsed and never used | latent | no | S5 | Won't fix (Part 5B): pico.py passes the same `--opts` to every worker; skimjob accepts and ignores them | none |
| W02 | `workers/picojob.py:3` (was `processors/`) | Description line was copied from skimjob | latent | no | S5 | Part 5B: the description says what picojob.py does | none |

## Analysis modules and writers

| ID | Location | Symptom | Severity | BBB | Session | Fix | Output impact |
|---|---|---|---|---|---|---|---|
| A01 | `analysis/ModuleMuTau.py:168`, `ModuleETau.py:155`, `ModuleEMu.py:133`, `ModuleTauTau.py:131`, `ModuleMuTau_nanoV10_DeepTau2p5.py:172`, `ETauFakeRate/ModuleETau.py:201` | `getlepvetoes(...)` is called without the now-required `era` argument (changed in `877e636`), so a `TypeError` is raised on the first event that reaches the vetoes | crash | no | S6 | | |
| A02 | `analysis/ModuleMuTau.py:40-46` vs `285-302` | Tau ID / e→τ / μ→τ SF tools are commented out but still used for MC with genmatch 1–5 (`AttributeError`); the comments at 293/298 swap muon and electron | crash | no | S6 | | |
| A03 | `analysis/TreeProducerTauPair.py` vs `ModuleTauPair.py:562-566` | With `jec=True`, `met_<unc>`, `mt_1_<unc>` and `dzeta_<unc>` are filled but never declared, and `pzeta_vis` is undefined (the variable is `pzetavis`) | crash | no | S6 | | |
| A04 | `analysis/ModuleEMu.py:198` | Writes `idiso_2`, which `TreeProducerEMu` does not define (probably `idiso_3`) | crash | no | S6 | | |
| A05 | `analysis/HighPT/ModuleDiJet.py:144` | Reads `idisoweight_1`, which `TreeProducerDiJet` does not define | crash | no | S6 | | |
| A06 | `ModuleTauPair.py:18` (and its forks) | `tauSFVersion` stops at 2022, so `ModuleETau`/`ModuleTauTau` raise `KeyError` for 2023+ | crash | no | S6 | | |
| A07 | `analysis/utils.py:467-481` | `getTotalWeight`: `total_w = []` is indexed with `+=` (`IndexError`), and line 480 is outside the inner loop | crash | no | S6 | | |
| A08 | `analysis/utils.py:294,348` | `getmet`/`getmetfilters` always print, ignoring `verb` | wrong (cosmetic) | no | S6 | | |
| A09 | `analysis/utils.py:355` | `loosestIso` hard-codes DeepTau2017v2p1 | wrong | no | S6 | | |
| A10 | `analysis/Run3_DEV/ModuleMuTau.py:34,44` | No trigger for 2025 (`self.trigger` unset); `self.muSFs = 1` for 2024 | crash | no | S6 | | |
| A12 | `ModuleTauPair.py:51` and variants | `recoil` option is stored, but the tool and calls are commented out | latent | no | S6 | | |
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
| C11 | `corrections/RecoilCorrectionTool.py:12` | A correction imports `analysis.utils` (layering inversion); the `RecoilCorrectionTool` class itself is unused | latent | no | S6 | | |
| C12 | `corrections/MetTriggerSF.py:8`, `WmassCorrection.py:7` | Paths are built from `os.getenv('CMSSW_BASE')+…`, bypassing `datadir`; `TypeError` without CMSSW; `data/Wstar/` and `trigger/mettrigger_<era>.root` are absent | crash | no | S6 | | |
| C13 | `corrections/MuonSFs.py:27`, `DYandRecoilCorrlib.py:27` | `getcorr()` is duplicated verbatim; DYandRecoilCorrlib docstrings still say "muon" | latent | no | S6 | | |

## How old

Open bugs in maintained code only (including won't-fix); fixed ones are left out. Found with `git log -S/-G`,
`git show` and `git blame` on old revisions. Where the reason nobody noticed is a guess, it says so.

### Control plane, batch, workers

- **P15** The missing options on `status`/`hadd`/`clean` come from a pattern that has been in the code since the
  first commit, `f60cfbd` (2020-05-18, "first commit"). That commit already built
  `parser_chk = ArgumentParser(add_help=False,parents=[parser_job])` partway through the `parser_job.add_argument(...)`
  calls. argparse copies a parent's options when the child is built, so `parser_chk` only gets the options added
  before that line. Later commits added more options below it: `-P/--prompt` in `36d3bdb` (2020-07-07, "add prompt
  option for submission; add gitignore stuff") and `-m/--maxevts` in `4e46663` (2021-02-09, "add option to limit
  number of events per job"). Then `a3e7e38` (2021-06-16, "add maxopenedfiles for hadd; add checkexpnevts for
  debugging") gave `hadd` its own `-m/--maxopenfiles`, which only works because `-m` never reached `parser_chk`
  (otherwise argparse raises a conflicting-option error). So it was never a regression, and nobody noticed because
  these subcommands never need the submission options.
- **S16** `guess_batch` has had the NAF branch commented out since the day it was written: commit `bce39ac`
  (2023-06-08, "raw_input -> input; split HTCondor batch systems; guess functions"). That commit split HTCondor into
  the KIT/DESY/NAF subclasses and added `guess_batch` with DESY and NAF as `###elif "etp" in host:` placeholders,
  both copy-pasted from the KIT test. `5f836ac` (2023-10-12, "Fixed batch system issue with DESY") made the DESY
  branch real but left NAF commented out. It moved to `settings/defaults.py` unchanged in `a4fbd42` (2026-10-12).
  Nobody noticed because NAF users set the batch system explicitly (and, probably, NAF hosts match the DESY branch).
- **W01** `-E/--opts` in skimjob has never been used since it was added: commit `7e4d94c` (2020-07-06, "add extra
  option; allow flags to be passed processor in skimming channel; allow post-fix filtering of nanAOD files"). In that
  commit pico.py started adding `--opt '...'` to every job command, and the option was added to
  `processors/skimjob.py` so the skim worker would accept the flag instead of failing in argparse. `args.extraopts`
  has never been read there. Accepting and ignoring the flag was the point, so nobody noticed.
### Analysis modules and writers

- **A01** The callers were fine when they were written. A later signature change broke them. The
  `getlepvetoes(..., self.channel)` calls in `ModuleMuTau`, `ModuleETau`, `ModuleTauTau` and
  `ETauFakeRate/ModuleETau` come from `463774e` (2020-07-18, "add ditau channel"), the one in `ModuleEMu` from
  `6c69dcd` (2020-07-18, "add emu channel"), and the `legacy/` copies from the same commits. The function then had
  no `era`. `9411be0` (2023-10-19, "Working version of Run 3 mt channel") added `era='2018'` with a default, so the
  old callers still worked. The break is commit `877e636` (2024-02-20, "update tutorial"), which made `era` required
  (and left a stray `print(era)` in the electron loop) but only updated the tutorial module. Nobody noticed because
  Run 3 work runs through `Run3_DEV/*` and the top-level `ModuleMuMu`, which all pass `era=self.era`. The old Run 2
  channel modules have apparently not been run since February 2024.
- **A02** The crash comes from commit `891bb3a` (2025-06-18, "no TES"). That commit commented out `tesTool`,
  `tauSFsT/M/T_dm`, `etfSFs` and `mtfSFs` in `ModuleMuTau.__init__` and set `tes = 1.0`, but left the tau-weight
  block that uses them (from `64ce575`, 2020-07-06, "add TauIDSFs, Z pt and top pt tool"). Probably the tools were
  turned off because `tauSFVersion` has no 2024 key (A06), but that is a guess. Nobody noticed because A01 was already
  in the file: the `getlepvetoes` crash fires before the weights on every event. The swapped comments are older,
  from `64ce575` itself; only the comments are wrong, the code uses the right tools.
- **A03** The fill loop and the `pzeta_vis` typo have been there since the file was created: commit `f8ba048`
  (2020-06-21, "add full mutau and etau analysis modules and correction"). The matching declarations in
  `TreeProducerTauPair` were already commented out then, and so was the `dojecsys` block that sets
  `metUncLabels`, so the loop never ran. `463774e` (2020-07-18) deleted the commented declarations. The loop came alive
  in `6f137fa` (2023-12-07, "merge"), which uncommented the `dojecsys` block but did not restore the declarations or
  fix `pzeta_vis`. Nobody noticed because the path needs `jec=True` (default `False`), MC and `dosys`; apparently no
  JEC-systematics ditau job has run since December 2023.
- **A04** `ModuleEMu` writing `idiso_2` has been broken since the day it was written: commit `f591dc1` (2020-07-18,
  "fix small bugs; add documentation for branches"). That commit added `addBranch('idiso_3', ...)` to
  `TreeProducerEMu` and wrote `self.out.idiso_2[0] = idIso(tau)` in the module, a `_2` -> `_3` rename that missed one
  line. The same line in `ModuleMuMu` was commented out in `5837e8c` (2023-03-20) instead of renamed. Why it was never
  hit in `ModuleEMu` is not fully clear: it only runs for an e-mu event with a tau above 20 GeV, the guard before
  `d8005c9` (2023-06-12) was `if maxtau>-1:`, and the e-mu channel seems to be rarely run.
- **A05** `ModuleDiJet` reading `idisoweight_1` has been broken since the day it was written: commit `be8c553`
  (2023-02-14, "Squashed commits", the HighPT import). The weight line is copied word for word from `ModuleMuNu`,
  whose tree declares `idisoweight_1`; `TreeProducerDiJet`/`TreeProducerHighPT` never have. It only crashes on MC,
  the DiJet selection is for jet -> tau fake factors measured in data, and no config refers to the module, so its MC
  path has probably never run.
- **A06** `tauSFVersion` was Run 2 only from the start: commit `f8ba048` (2020-06-21) created it as
  `{2016, 2017, 2018}`. `c679b49` (2023-10-12, "Run 3 dev - correction and basic mutau setup") added only
  `2022: '2022ReReco'`. Nobody added 2023+ because Run 3 development moved to `Run3_DEV/*`, which does not use
  `tauSFVersion`; only the old top-level `ModuleETau`/`ModuleTauTau` index it, and only for MC. The same dict is also
  in `ModuleHighPT.py`, `Tau_trig_SF_studies/ModuleTauPair_trig.py` and the `legacy/` copies.
- **A07** `getTotalWeight` was correct when written: commit `fb23b0b` (2023-10-09, "Produced
  nanoaod_sumw_2022_postEE.json ...") summed a scalar `total_w = 0.`. It was broken twice after that: `e56fb46`
  (2023-10-11) added `if len(selection>0):`, which raises `TypeError` in Python 3 on every call, and `b26b97e`
  (2023-10-13, "Change all bins in one loop ... -- not yet debugged, need nTuples with cutflow for this") changed it to
  `total_w = []` with `total_w[iSel] += ...` outside the inner loop. The commit message itself says it was never
  tested. Nobody noticed because the callers (`scripts/get_dataset_info.py`,
  `Legacy/OldAnalysis/2022/modify_cutflow_hist*.py`) are one-off scripts, and the JSON was made with the working version.
- **A08** `getmet`/`getmetfilters` have printed regardless of `verb` since commit `ac73d84` (2023-12-09, "update
  metfilter"). That commit added Run 3 MET-filter handling and, under the existing `if verb>=1: LOG.verb(...)` lines,
  unconditional `print(">>> getmet: ...")` and `print(">>> getmetfilters: ...")`, probably leftover debug prints. Each
  function runs once per module at setup, so the cost is one extra log line per job and nobody minded.
- **A09** `loosestIso` has used `idDeepTau2017v2p1VSjet` since the day it was written: commit `b8952b1` (2020-06-21,
  "add hulp functions"). In 2020 that was the current ID, so it was correct then and only went stale with
  DeepTau2018v2p5 and Run 3. Its only callers lost their `loosestIso(tau)` calls in `64ce575` (2020-07-06); about
  15 modules still import it, but nothing calls it, so nobody noticed.
- **A10** The missing 2025 trigger goes back to commit `c679b49` (2023-10-12, "Run 3 dev - correction and basic mutau
  setup"). That commit created `Run3_DEV/ModuleMuTau.py` from the Run 2 module and replaced its catch-all `else:`
  with explicit year branches and no `else`, so any year without a branch leaves `self.trigger` unset. 2023 came in
  `f1c36d8` (2024-03-13) and 2024 in `6f2db3c` (2025-03-18, "Module expanded to include 2024"). The 2025 import
  `eb15fdc` (2026-03-11) put 2025 only into `ModuleMuTau_Inclusive.py`, and 2025 only passes the `ModuleTauPair` year
  check since `53770ac` (2026-03-16, "2025 Updates"). Nobody noticed because the 2025 campaign apparently runs the
  `_Inclusive` module. The `self.muSFs = 1` for 2024 comes from `6f2db3c`, which also sets the 2024 weights to 1, so
  the integer is never used.
- **A12** The `recoil` option has been dead since the day it was written: commit `f8ba048` (2020-06-21) created
  `ModuleTauPair` with `self.doRecoil = kwargs.get('doRecoil', False)`, and in that same commit the import, the
  `RecoilCorrectionTool(...)` construction and the correction calls were already commented out. `64ce575`
  (2020-07-06) renamed it to `kwargs.get('recoil', False)`; the tool was never turned back on. The default is `False`
  and no config passes `recoil=`, so nobody noticed.
- **A14** The undefined `fes` came in later. `a0ac361` (2021-06-17, "ETauFR modules") created the file with a working
  `fes = self.fesTool.getFES(...)`. `486a11d` (2023-10-10, "ETau Update") commented out the tool and that line and set
  `fes = 1.0`, which still worked. The bug is `43f229c` (2024-01-26, "Add combined fit + minor changes"), which
  commented out `fes = 1.0` too, leaving `tau.pt *= fes` with nothing defining `fes`. The branch is only reached on MC
  with the `fes` option set and `ltf` not set; the ETauFR workflow passes `ltf`, whose branch catches genmatch 1/3
  first, so the `NameError` never runs.

### Corrections

- **C01** The UL2017 branch of `MuonSFs` has loaded the 2018 file since the correctionlib version was written: commit
  `b41afdc` (2024-05-03, "add correctionlib JSONs for muon SFs"). That commit replaced the per-year ROOT files with
  central JSONs, and its 2017 line is a copy-paste of the 2018 one (before that, 2017 correctly used `Run2017UL/...`).
  The 2017 and 2018 JSONs have the same keys, so loading works and the numbers are only somewhat off; it never fails.
- **C02** The id/iso log line has printed `sf_id` twice since `b41afdc` (2024-05-03). In that first version the
  trigger print also had 5 arguments for 4 placeholders; `ed8fc45` (2024-05-03, "fix defaults: ...") fixed the count
  but kept the duplicate `sf_id`. It only affects a log line, so nobody noticed.
- **C03** `self.sftool_trig = 1.0 # no trigger SF in 2024 at the moment` first came in with `c82b25d` (2025-05-31, "DY
  Zpt correction: JSON and script"), was removed in `fdadaa6` (2025-06-05) and re-added unchanged in `e2cd367`
  (2025-06-05, "muon ID&Iso implementation 2024"). It was wrong from the start, but it never crashed because every
  Run 3 module sets `trigweight = 1.` for 2024 without calling `getTriggerSF`. `16f3cfa` (2026-05-08, "muon Json
  2025") copied the same float fallback into the 2025 branch.
- **C04** `getTriggerSF` has taken its systematic from `sftool_id` since it was written in `b41afdc` (2024-05-03),
  a copy-paste of the identical line in `getIdSF`/`getIsoSF`. No caller ever passes `syst`, so nobody noticed.
- **C05** The `fname_id=None` plus `os.path.exists(fname_id)` pattern dates from `b41afdc` (2024-05-03), which dropped
  the readable `assert ... "Did not find muon SF tool for %r"` of the old ROOT version (`ed8fc45` renamed `fname` to
  `fname_id` the same day). Callers only pass known eras, and the 2024/2025 modules skip `MuonSFs`, so it never showed.
- **C06** Two origins. The `getDYpTCorr` mapping `'2024' -> "2022postEE"` has been there since `DYandRecoilCorrlib`
  was written in `c82b25d` (2025-05-31), as a deliberate placeholder (re-added unchanged in `612dd05`, 2025-06-05).
  The 2025 crash came with `53770ac` (2026-03-16, "2025 Updates"), which allowed 2025 in `ModuleTauPair` but did not
  add `'2025'` to the `fname_id` condition here. It needs MC with `dozpt` (a DY sample); probably no 2025 DY job has
  run through `ModuleTauPair` since, or it ran with `zpt=False`.
- **C07** Three origins. The stray string literals come from `bea7f54` (2021-06-10, "add lepton SFs; add pileup;
  update modules"); they look like leftover file-name notes and do nothing. The "MuonSFs" text in the 2023 message
  comes from `24efb7e` (2024-03-11, "add EleSF and Zpt for 2023"), copy-pasted from `MuonSFs`. The final assert is
  from `bea7f54`, and no 2024/2025 branch has ever existed. Nobody noticed because the only Run 3 caller for those
  eras, `Run3_DEV/ModuleETau_Inclusive.py`, sets `self.eleSFs = 1` for 2024 and 2025.
- **C08** `JetVetoMapTool` has never had a working 2024 branch. `aab3232` (2025-01-20, "2024 updates") sent 2024 to
  the 2023 BPix map, and `459b30b` (2025-02-24, "some comments for PR implemented") removed that again. `6f2db3c`
  (2025-03-18) narrowed the `ModuleTauPair` check to 2022/2023, so 2024 silently skips the veto. The 2024 map only
  arrived in `0b174cf` (2026-09-15, "Import upstream Tau trigger-SF framework + ... + 2024 jetveto map"), without a
  code branch. That commit also added `Tau_trig_SF_studies/ModuleTauPair_trig.py`, whose check includes 2024/2025,
  so there it raises "Did not recognize era" instead.
- **C09** The `getjmecalib` data branch has been broken since `785e9a4` (2020-08-16, "improve UL2017 sample list;
  repace PATH by DAS; improve getjmecalib; ..."), which replaced the old `jetRecalib` dictionary with
  `createJMECorrector(..., jesUncert=jmeUncs, ..., metBranchName=MET)` while `jmeUncs`/`MET` are only set in the MC
  branch. The same commit switched `skimjob.py` to NanoAODTools' `createJMECorrector` directly, so the function has had
  no caller since the day the bug went in.
- **C11** The import `from TauFW.PicoProducer.analysis.utils import hasbit` comes from `64ce575` (2020-07-06, "add
  TauIDSFs, Z pt and top pt tool"), which replaced the broken imports of `7c97e15` with working ones and took
  `hasbit` from `analysis.utils`. It works at runtime, so there was no reason to notice. The class itself has never
  been used: its only use in `ModuleTauPair` has always been commented out.
- **C12** Both files have been like this since they were written in `be8c553` (2023-02-14, "Squashed commits", the
  HighPT/W* import); later commits only changed them for Python 3. `data/Wstar/kfactor_*.root` and
  `data/trigger/mettrigger_<era>.root` have never been committed (`*.root` is in `.gitignore`). The only callers are
  the HighPT modules `ModuleTauNu`/`ModuleMuNu`; most likely their author ran them inside CMSSW with the ROOT files
  copied locally (a guess).
- **C13** Both problems have been there since `DYandRecoilCorrlib.py` was created in `c82b25d` (2025-05-31, "DY Zpt
  correction: JSON and script") by copying `MuonSFs.py`: the muon header comments, `getcorr` verbatim, the "muon"
  docstrings and the unused `pathHTT`/`pathPOG`/`pathMUO`. `getcorr` is never called there, so nothing broke.

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

