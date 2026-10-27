# Bug register

- [PicoProducer](#picoproducer)
- [Histogrammer](#histogrammer)
- [Fitter](#fitter)
- [Framework](#framework)
- [Legacy](#legacy)

---

## PicoProducer

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

Legacy-only entries W03, A11, A13 and C10, plus the archived copies affected by A01,
are recorded in [legacy PicoProducer section](#legacy-picoproducer). Maintained paths,
including latent and off-Framework defects, stay here.

<a id="picoproducer-control-plane-cli-config-jobs"></a>

### Control plane: CLI, config, jobs

| ID | Location | Symptom | Severity | BBB | Session | Fix | Output impact |
|---|---|---|---|---|---|---|---|
| P01 | `jobs/pipeline.py` `iter_plans` (was `pico/job.py:241`), `cli/config.py` `main_write` (was `pico/config.py:234`) | `err.message` (Python 2) inside `except IOError`: the handler itself raises `AttributeError` | crash | no | S4 / S3 | Part 4B-1: `str(err)` | none (the error message is printed instead of a crash) |
| P02 | `cli/jobs.py` `_Prompt.existing` (was `pico/job.py:173`) | `--prompt` on an existing job config: `input("..."%(nchunks))` uses `nchunks` before assignment and the string has no placeholder | crash | no | S4 | Part 4B-1: the prompt has no format argument | none for BBB. `submit --prompt` on an existing job config asks instead of crashing (the answers are still inverted until P20 is fixed) |
| P03 | `jobs/jobconfig.py` `write_jobcfg` (was `pico/job.py:839-841`) | `.json.gz` job config: `gzip` is not imported, and `file.write(json.dump(jobcfg),indent=2)` is malformed | crash | no | S4 | Part 4B-1: `import gzip`; `json.dump(jobcfg,file,indent=2)` | none (no caller writes `.json.gz` today) |
| P04 | `jobs/pipeline.py` `iter_plans`, `api/producer.py` `_queue_once` (was `pico/job.py:204`, `:934`) | `--checkqueue 1` ("check once"): the condition `jobs!=None` with `jobs=None` means the queue is never pre-fetched, so it silently falls back to per-sample queries | wrong | no | S4 | Part 4B-2: `jobs is None`, in `iter_plans` and `main_status` | `--checkqueue 1` now queries the queue once and finds pending jobs; before, it did not check the queue at all. Not in BBB (cases use the default -1) |
| P05 | `jobs/pipeline.py` `iter_plans` (was `pico/job.py:103`) | `found = len(samples)>=0` is always true, so "no samples found" is never printed on submit | wrong | yes | S4 | Part 4B-2: `len(samples)>0` | `submit` with no matching sample prints "Did not find any samples ...". BBB unchanged (every `submit` matches samples) |
| P06 | `jobs/planner.py` `sample_layout` (was `pico/job.py:123`) | Per-sample `maxevts` is used only when `<=0`; a positive sample value falls back to the config (the condition is inverted) | wrong | no | S4 | Part 4B-2: the sample value is used when `>0` | A sample with `maxevts>0` now splits its jobs by events; a sample without it now uses `maxevtsperjob` from the configuration (before, that was ignored unless the sample set a positive value). BBB unchanged (`maxevtsperjob=-1`) |
| P07 | `jobs/status.py` `check_sample` (was `pico/job.py:384`) | `checkexpevts==False` is a comparison, not an assignment, so it has no effect | latent | no | S4 | Part 4B-1: `checkexpevts = False` | none (`None` and `False` both disable the comparison) |
| P08 | `jobs/worker_command.py` `resolve_worker`, `jobs/planner.py` `sample_layout` (was `pico/run.py:183,195`, `pico/job.py:119-121`) | Option precedence is the opposite of the code comments: channel-config `KEY=VALUE` come after the user's `-E`, so the channel wins | wrong | yes | S4 | Part 4B-3: `module_options(worker, sampleopts)` = channel, sample, user; `WorkerSpec` keeps the channel (`chopts`) and user (`useropts`) options apart | **BBB `pico.run`, `pico.jobs`** (re-lock): the `--opt` lists start with the channel options. See [details](#picoproducer-p08-p09-p10-module-options-and-run--m) |
| P09 | `jobs/planner.py` `sample_layout` + `Sample.loadjson` (was `pico/job.py:119-121`) | On resubmit, the already-merged `extraopts` from the job config are merged again with the CLI and channel options, so the options duplicate on every retry | wrong | yes | S4 | Part 4B-3: `resubmit_options(previous, worker)`: the previous try's options, then new user options not already in them | **BBB `pico.jobs`** (re-lock): resubmitted job lists and job configs no longer repeat the channel options. See [details](#picoproducer-p08-p09-p10-module-options-and-run--m) |
| P10 | `jobs/worker_command.py` `run_command` (was `pico/run.py:156`) | `run -m` defaults to `-1`, and `if maxevts:` is true for -1, so `-m -1` is always appended | wrong (harmless) | yes | S4 | Part 4B-3: `-m` only for `maxevts>0` | **BBB `pico.run`** (re-lock): `-m -1` is gone from the "Executing:" lines. See [details](#picoproducer-p08-p09-p10-module-options-and-run--m) |
| P11 | `jobs/local.py` `execute_run` (was `pico/run.py:169`) | Local run uses `os.system`; a worker failure is not reported (exit code ignored) | wrong | no | S4 | Part 4B-2: `subprocess.call`; a non-zero exit code is reported per run and summarized at the end | `pico.py run` warns when a worker fails. Not in BBB (`run` cases are dry) |
| P12 | `jobs/worker_command.py` vs workers (was `pico/run.py`, `pico/job.py`) | Callers pass `--opt`, the workers define `--opts`; it only works through argparse prefix matching | latent | yes | S5 | Part 5B: callers pass `--opts` | **BBB `pico.run`, `pico.jobs`** (re-lock): `--opt` becomes `--opts` in the "Executing:" lines and job lists. The workers parse the same options |
| P13 | `cli/__init__.py` `dispatch` (was `scripts/pico.py:226`) | `if` instead of `elif` after `install`: `pico.py install` also prints "subcommand 'install' not implemented!" | wrong | no | S5 | Part 5B: `install` is a regular entry of the `cli.COMMANDS` table | `pico.py install` no longer prints "not implemented" (it is still a stub). Not in BBB |
| P14 | `cli/parser.py` (was `scripts/pico.py:158`) | `install` choice is misspelled `'cmmsw'` | latent | no | S5 | Part 5B: `cmssw` | `pico.py install cmssw` is accepted; `cmmsw` is rejected. Not in BBB |
| P15 | `cli/parser.py` `build_parser` (was `scripts/pico.py:85-108`) | `status`/`hadd`/`clean` parsers are built before `--prompt`, `-m`, ... are added to the job parent, so these options are missing there. This looks intentional for `-m` (reused for `--maxopenfiles`) but is undocumented | latent | yes | S5 | Won't fix (Part 5B): documented in `build_parser`. `status`/`hadd`/`clean` must not take the submission options, and `hadd` reuses `-m` for `--maxopenfiles` | none |
| P16 | `settings/model.py` (`Config.__setattr__`; was `tools/config.py:192`) | `key in self._dict[key]` should be `key in self._dict`: setting a private attribute such as `CONFIG._path` raised `KeyError` | latent | no | S3 | Part 3B: `key in self._dict` | none (no caller sets private attributes) |
| P17 | `settings/defaults.py` (was `tools/config.py:33-37`) | Default eras pointed to `samples_2016.py`/`samples_2017.py`/`samples_2018.py`, which do not exist; `config/config_example.json` pointed to the missing `samples_UL2016.py` and `tutorial/samples_2022_postEE.py` | wrong | yes | S3 | Part 3B: defaults are the catalogs that exist (`UL2016_preVFP`, `UL2016_postVFP`, `UL2017`, `UL2018`, `2022_preEE`, `2022_postEE`, `2023C`, `2023D`, `2024`, `2025`); example config updated | **BBB `pico.config`**: `fresh.values.eras` changes (re-lock). Only fresh installations are affected; existing `config.json` files keep their eras. See [details](#picoproducer-p17-default-eras-pointed-to-deleted-catalogs) |
| P18 | `settings/store.py` (was `tools/config.py:76-117`) | Reading the config created or rewrote `config/config.json`, also from a batch worker (`picojob.py -c`), Plotter (`$PICODIR`) or a script | wrong | yes | S3 | Part 3B: `getconfig(write=False)` by default; only `pico.py` (`pico/common.py`) passes `write=True`. Library readers get missing keys repaired in memory and a warning if the file is missing | none for `pico.py` (BBB unchanged); workers/Plotter/scripts no longer write the file |
| P19 | `jobs/merge.py` `merge_sample` (was `pico/job.py:975`) | `TODO: check if hadd was succesful`: cleanup after `haddclean` is gated only on the command's exit code, not on the merged file (A04) | wrong | yes | S4 | Part 4B-2: before cleaning after a merge, `validated()` requires the merged tuple to be readable (`isvalid`) and, with event counting, to hold the processed events of the job output; otherwise the job output is kept with a warning | none for valid merges (BBB `pico.merge` unchanged); a corrupt or incomplete merged tuple no longer leads to the deletion of the job output |
| P20 | `cli/jobs.py` `_Prompt.existing` + `jobs/pipeline.py` (was `pico/job.py:177-182`) | `submit --prompt` on an existing job config: answering `y` (submit) or `f` (submit all) skipped the sample and `n` submitted it (the `skip` flag was set on the wrong branches). Unreachable today because of P02 | wrong | no | S4 | Part 4B-2: `y` and `f` submit, `n` skips | `submit --prompt` on an existing job config does what the answer says. Not in BBB |
| P21 | `api/producer.py` `status` (was the status branch of `pico/job.py` `main_status`) | `pico.py status --checkexpevts` has no effect: the status-only branch does not pass `checkexpevts` to the status check (`hadd`/`clean` and `resubmit` do), so it falls back to `False` | wrong | no | S4 | Part 4B-2: `checkexpevts` is passed | `pico.py status` now warns about chunks with an unexpected number of events by default for analysis channels, like `hadd` and `resubmit` already did. BBB `pico.jobs` unchanged (it keeps only the summary lines) |
| P22 | `jobs/status.py` `check_sample` (was `pico/job.py:361`) | Checking the status creates the output directory (`getstorage(outdir,ensure=True)`), so `status`, and the read-only `status()`/`plan()` of the coming API, write to storage | wrong (side effect) | no | S4 | Part 4B-2: `getstorage(outdir)` without `ensure` | checking the status no longer creates a missing output directory (a warning says it is missing). BBB unchanged (submission creates it) |
| P23 | `jobs/merge.py` `cleanup_commands` (was `pico/job.py:978`) | Cleanup decides whether other jobs share the job directory with `len(glob(job*_try*)) >= len(glob(job*<postfix>_try*))`. The first pattern includes the second, so the test is always true and the whole job directory is removed: `haddclean`/`clean` of one tag also deletes the job configs, job lists and logs of other tags in the same directory | wrong (data loss) | no | S4 | Part 4B-2: `<=`: the whole directory is removed only if all its job configs belong to this sample; otherwise only the sample's job outputs, job configs and logs | cleaning one tag keeps the job files of other tags. BBB `pico.merge` unchanged (one job per directory) |

<a id="picoproducer-storage-and-batch"></a>

### Storage and batch

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

<a id="picoproducer-workers"></a>

### Workers

| ID | Location | Symptom | Severity | BBB | Session | Fix | Output impact |
|---|---|---|---|---|---|---|---|
| W01 | `workers/skimjob.py:24` (was `processors/`) | `-E/--opts` is parsed and never used | latent | no | S5 | Won't fix (Part 5B): pico.py passes the same `--opts` to every worker; skimjob accepts and ignores them | none |
| W02 | `workers/picojob.py:3` (was `processors/`) | Description line was copied from skimjob | latent | no | S5 | Part 5B: the description says what picojob.py does | none |

<a id="picoproducer-analysis-modules-and-writers"></a>

### Analysis modules and writers

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

<a id="picoproducer-corrections"></a>

### Corrections

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

<a id="picoproducer-how-old"></a>

### How old

Open bugs in maintained code only (including won't-fix); fixed ones are left out. Found with `git log -S/-G`,
`git show` and `git blame` on old revisions. Where the reason nobody noticed is a guess, it says so.

<a id="picoproducer-control-plane-batch-workers"></a>

#### Control plane, batch, workers

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
<a id="picoproducer-analysis-modules-and-writers-1"></a>

#### Analysis modules and writers

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

<a id="picoproducer-corrections-1"></a>

#### Corrections

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

<a id="picoproducer-bbb-coverage-notes"></a>

### BBB coverage notes

- The control plane (`pico.config`, `pico.run`, `pico.jobs`, `pico.merge`) and the workers (`pico.workers`, with
  `ModuleMuTauSimple`) are covered from Session 1 onwards.
- **No `ModuleTauPair`-based channel module is covered yet.** Those modules need a much larger synthetic
  NanoAOD (jets, MET, PV, electrons, trigger objects, pileup, gen particles) plus jsonpog/correctionlib and
  TauIDSFs payloads. A `pico.channel_tau_pair` case is a **prerequisite for Session 6**, before any analysis or
  corrections code moves. Fixes A01–A13 and C01–C13 must each be checked against that case.

<a id="picoproducer-details-of-fixes-that-change-a-bbb-baseline"></a>

### Details of fixes that change a BBB baseline

<a id="picoproducer-p17-default-eras-pointed-to-deleted-catalogs"></a>

#### P17: default eras pointed to deleted catalogs

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

<a id="picoproducer-p08-p09-p10-module-options-and-run--m"></a>

#### P08, P09, P10: module options and `run -m`

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

---

## Histogrammer

The Plotter module was renamed Histogrammer in October 2026 (changelog §21); its bugs keep their IDs (L01, ...) and
the locations below are relative to the module (`config/`, `python/`), so `plot.py` is now `fillhists.py` and
`python/plot/` is now `python/spec/`. Bugs of the new, drawing-only Plotter will get their own section.

Defects in retired workflows are tracked in the [Legacy section](#legacy).
Latent defects in maintained modules and workflow options remain here.

Defects found while connecting the Plotter to the TauFW Framework (Part G, October 2026, branch `Refactor-2025`).
Same policy as [PicoProducer](#picoproducer): bugs on the path the Framework runs are
fixed with `# BUGS <ID>` comments at the changed lines; others are registered only.

**Severity:** **crash** (raises on a reachable path), **wrong** (silently wrong), **latent** (nothing reaches it).

| ID | Location | Symptom | Severity | Fix | Output impact |
|---|---|---|---|---|---|
| L01 | `plot.py` `plot` (variable lists) | `idDeepTau2018v2p5VSVjet_2` and `idDeepTau2018v2p5VSVSe_2` are not branches of the pico tuples, but are plotted for every channel (also mumu), and the tau-channel list has `VSVSe` instead of `VSe` | wrong | Part G: the two all-channel entries are removed (the tau-channel list has the tau ID variables), `VSVSe` -> `VSe` | the two broken plots are gone; tau channels get a correct `idDeepTau2018v2p5VSe_2_zoom` plot |
| L02 | `config/samples_v15.py:285` (`getsampleset`) vs `python/sample/utils.py:29` (`_getsampleset`) | the file-name pattern is passed as `fname=`, but the generic builder reads `file=`; so `samples.filename` in the Fitter configs and `fname` in `plot.py` are ignored and the default `$PICODIR/$SAMPLE_$CHANNEL$TAG.root` is always used | latent | registered only: every caller uses the default pattern today. A fix must also stop `file=` from reaching the `MC(...)` keyword arguments, so it needs a test with tuples | |
| L03 | `python/plot/utils.py` `sumhists` (line ~176; now `Utilities/python/Drawing/hist_tools.py`) | adds every histogram after the first to the undefined name `sighist` instead of `sumhist`, so any call with two or more histograms raises `NameError` | latent | registered only (no callers). Frozen in the BBB case `drawing.canvas` (`$.tools.sumhists`); fix after the move to `TauFW.Utilities.Drawing` in its own commit with a re-lock | the `drawing.canvas` baseline changes from the `NameError` to the summed histogram |
| L04 | `python/plot/string.py` `estimatelen` (line ~261; now `Utilities/python/Drawing/labels.py`) | `estimatelen(*strings)` calls `unpacklistargs(*strings)`, which takes one argument: calls with two or more strings raise `TypeError`. The only caller (`Plot.drawlegend`, `Plot.py:881`) passes one list, which works | latent | registered only; `drawing.canvas` records the one-list form. Fix with `unpacklistargs(strings)` after the move | none for the existing caller |
| L05 | `python/plot/string.py` `joinweights` (line ~29; now `Utilities/python/Expressions/_expressions.py`) | a numeric weight `0` should only warn, but the warning formats two values with one `%r`, so the call raises `TypeError`. `Sample.getrdframe` passes the sample scale as a weight, so a sample scaled to exactly 0 would crash histogram filling | latent | registered only; recorded in `Tests/Utilities/test_expressions.py`. Fix the format string (`%r`, `%r`) in its own commit | a zero weight warns and gives `"0*..."` instead of raising |
| L06 | `python/plot/string.py` `replacepattern` (line ~79; now `Utilities/python/Expressions/_expressions.py`) | with several patterns every replacement starts again from the original string, so only the last pattern is applied (`[("w1","a"),("w3","b")]` on `"w1*w2*w3"` gives `"w1*w2*b"`) | latent | registered only: the one caller (`Sample.getrdframe`, `replaceweight=`) passes a single tuple. Recorded in `test_expressions.py` | none for the existing caller |
| L07 | `python/plot/string.py` `joincuts` (line ~48; now `Utilities/python/Expressions/_expressions.py`) | a cut with `\|\|` is bracketed only if it has no parentheses at all, so `"(x)\|\|y"` is joined as `"a>1 && (x)\|\|y"`, where `&&` binds first and the selection is wider than meant | latent | registered only: the `\|\|` selections in `Plotter/config/samples*.py` (`GML`, `GMJ`, `GMF`) are fully bracketed; selections built in Fitter configs and recipes were not checked. Recorded in `test_expressions.py`. A fix needs a bracket-depth check | selections of that form change |
| L08 | `python/api/control_plots.py` `_plot_glob`, `_command` (expects) | the expected plots use only `request.tag`, but `plot.py` names its files with the setup's YAML `tag` plus `-t`, so for a setup with a non-empty `tag` the expected outputs are always missing and the plots stage fails (and `nfiles` is 0) | wrong | R3 (CL §15), checked on lxplus: the expected plots use the setup's tag plus `tag` | a setup with a tag no longer fails the stage |
| L09 | `python/api/control_plots.py` `make` (`nfiles`) | the plot count globs `Plotter/plots/<era>/`, which is shared by all runs, so it also counts plots of earlier runs | wrong | R3 (CL §15), checked on lxplus: each run has its own directory, and the count uses the command's own pattern | |
| L10 | `config/setup_mutau.yml` vs `config/setup_mutau_inclusive.yml` | both have `channel: mutau` and `tag: ""`, so they write the same file names into `plots/<era>/` and the second run overwrites the first | wrong | registered only; `plan` notes it | |
| L11 | `plot.py` (line ~65) + `common/python/tools/root.py` `loadmacro` | `loadmacro("python/macros/mapDecayModes.C")` is relative to the working directory and its result is ignored; outside `Plotter/` the macro is not loaded and the run fails much later, when RDataFrame compiles `mapRecoDM(dm_2)` (only for channels with `tau`) | latent; crash outside `Plotter/` | R3 (CL §15), checked on lxplus: path from `__file__` (the ignored result of `ProcessLine` stays) | none in `Plotter/` |
| L12 | `python/sample/utils.py:119-120` (`getmcsample`) | the `pico=` keyword (a picodir to use instead of the PicoProducer configuration's) is read and overwritten with `""` on the next line, so it is ignored and `$PICODIR` always comes from the configuration | latent | **fixed (CL §39)**: `getmcsample` takes the directory as `tuples=` (no `pico=`); the copies in its two Legacy callers drop the two lines | none (`picodir` was always taken from the configuration, as in the copies) |
| L13 | `python/api/control_plots.py` `ControlPlots.__init__` (default `find_module`), used by `preflight` | the default module lookup is `importlib.util.find_spec(name) is not None`. If ROOT is already imported in the process and its `__spec__` is None (CMSSW's ROOT on lxplus), `find_spec('ROOT')` raises `ValueError: ROOT.__spec__ is None` instead of answering. Reached by `taufw.py plan` and `advance` of a recipe with production before plots (production's PicoProducer imports ROOT first): `plan` stops with a traceback, and the plots stage of a run raises at preflight (recorded, the run cannot go on) | crash | CL §16 (exception to the no-fix rule: it blocked every recipe with production and plots on lxplus): `_module_exists`, a module already imported counts as found | none: the preflight answers instead of raising |
| L14 | `config/samples_v15.py:338` (`getsampleset`, split `DM`); copied as it is to `python/sample/model.py` | `samples.split(...)` uses the undefined name `samples` (the sample set is `sampleset`), so `split=['DM']` raises `NameError` for channels with one tau | crash (only with `split=['DM']`; no caller passes it) | registered only (CL §20: the model keeps the behaviour) | none |
| L15 | `config/samples_v15.py:243` (`getsampleset`, data of `etau`/`ee`) | the last `else:` evaluates `"SingleElectron_Run%d?"%year` without assigning it, so `dataset` is undefined (`UnboundLocalError`) for electron channels of an era that matches none of the branches before it | latent (none of the eras samples_v15.py supports reaches it) | registered only; the exported templates have no such era | none |
| L16 | `config/samples_v15.py:222,245` (`getsampleset`, data of `tautau`/`emu`) with `common/python/tools/string.py` `getyear` | for era `2526` `getyear` returns the text `'2526'` (no 20xx year in it), and `"Tau_Run%d?"%year` / `"SingleMuon_Run%d?"%year` raise `TypeError` | crash (tautau or emu with era 2526) | registered only; `Configs/Histogrammer/samples/v15_2526.yml` has no `tautau`/`emu` data, so the model raises too (an `IOError` naming the missing kind) | none |
| L17 | `fillhists.py:94-97` (mumu variables `m_ll`, comment "alias: m_ll alias of m_vis") | no alias `m_ll` is defined (not in the 2025 tuples, not in the sample model), so RDataFrame cannot compile the expression (`use of undeclared identifier 'm_ll'`) and the mumu run of `fillhists.py` (the old `plot.py`) makes no plots | crash (`-c mumu` with these variables; found 2026-10-18 on the 2025 tuples, the same with and without `--hists`) | registered only (CL §21) | none |
| L18 | `Fitter/TauES/createinputsTES.py:284-321` (moves to the Histogrammer in plan 16 H1) | the control plots of the inputs, `rebinning` and the plots of the rebinned file are indented inside `if "systematics" in setup:`, so a config without `systematics` makes no control plots and no rebinned file | latent (both maintained configs have `systematics`) | registered only (plan 16 §8, CL §22) | none |
| L19 | `Fitter/TauES/createinputsTES.py:294-299` (moves in H1) | `varprocs` is defined only for channels containing `mumu` or `mutau`; for any other channel the control plots raise `NameError`, after the shapes were written | latent (only mutau and mumu configs) | registered only (plan 16 §8, CL §22) | none |
| L20 | `Fitter/TauES/createinputsTES.py:247-272` with `Fitter/python/plot/datacard.py:69` `createinputs` (both move in H1) | `createinputs` never gets `recreate=True`, so the shape files are opened with `UPDATE`: a second run into the same directory keeps the histograms of the first one that the new config does not write again (a removed TES point stays in the file, and the fit finds it); the `TNamed selection` record is never written | wrong (standalone reruns in `Fitter/`; a Framework run writes into a fresh stage directory) | registered only (plan 16 §8, CL §22) | none in Framework runs |
| L21 | `Fitter/TauES/createinputsTES.py:309-316` (moves in H1) | `rebinning` runs only for the first observable, but the plots of the rebinned file are made for every observable and open rebinned files that do not exist | latent (every config has one observable) | registered only (plan 16 §8, CL §22) | none |
| L22 | `Fitter/python/plot/rebinning.py` `find_binedges`/`regular_binning` (moves to `Histogrammer/python/shapes/` in H1) | if no bin of a region reaches a relative error of 30 % (an empty region, or few events), its bin-edge list keeps only the lower edge (or, when the last bin fails, that edge is replaced by the upper one), `Rebin(0, ...)` returns a null histogram ("Illegal value of ngroup=0") and `newhist.Clone()` raises `ReferenceError`; `createinputsTES.py` stops after the shapes are written, without the rebinned file and its plots | crash (a region with too few events; found with the BBB fixture of `histogrammer.tes_inputs`, which therefore uses 100 copies of the fixture rows) | registered only (CL §22) | none on real data |
| L23 | `Fitter/python/plot/rebinning.py:41` `find_binedges` (moves in H1) | the merged error is accumulated as `err += sqrt(err**2 + e**2)` instead of `err = sqrt(err**2 + e**2)`, so merging bins makes the relative error larger instead of smaller: a bin above 30 % is never rescued by its neighbours (only the last bin is merged backwards) | wrong (rebinned diagnostics only; the fit reads the unrebinned file) | registered only (CL §22) | the rebinned control plots |
| L24 | `Fitter/TauES/createinputsTES.py:290,314,317` `pname` with `TauFW.Fitter.plot.datacard.plotinputs` (both move in H1) | the control-plot name is `...-<era><tag>$TAG.png` and `plotinputs` fills `$TAG` with the tag again: `ztt_m_vis_mt-DM0-202513TeV_mutau13TeV_mutau.png` (no separator after the era, the tag twice) | cosmetic | registered only (CL §22; seen in the case log of `histogrammer.tes_inputs`) | the PNG names |

<a id="histogrammer-how-old"></a>

### How old

Open bugs only; fixed ones are left out.

- **L02** `fname=` vs `file=`: the mismatch is as old as the plotting configs. The generic `getsampleset` has read the
  pattern from `file` since commit `f17d1b4` (2020-07-13, "add QCD method"). The first sample config,
  `config/samples.py`, was added in commit `289345a` (2020-08-12, "add exaple plotting scripts; clean and debug tools")
  and already passed it as `fname` with `kwargs.setdefault('fname', fname)`. Every later config (including
  `samples_v15.py`, where the line came in with `898278e`, 2025-06-10) copied that line. It never showed because the
  pattern every config passes is the same as the default `$PICODIR/$SAMPLE_$CHANNEL$TAG.root`.
- **L03** `sumhists` has been broken since the day it was written: commit `47cce92` (2024-04-22, "add sumhists").
  That commit created the function with `sighist.Add(hist)` already in it, apparently a copy-paste from
  signal-histogram code. The function has never had a caller, so nobody noticed.
- **L04** `estimatelen`: the line `strings = unpacklistargs(*strings)` comes from commit `c70afa3` (2023-12-19), which
  only renamed `unwraplistargs` -> `unpacklistargs`. The old line was `unwraplistargs(*strings)`, written together
  with `estimatelen` in commit `38f7be3` (2020-07-18, "add Selection; improve gethist unwrapping"), and that one had
  the same problem. The helper has always taken exactly one argument, all the way back to 2020, so passing several
  strings has always crashed. It never showed because the only caller passes one list.
- **L08, L09** `_plot_glob` and the `nfiles` count came with the Plotter API, `c27abb7` (2026-10-13, Part G).
- **L10** `setup_mutau_inclusive.yml` was added in `a6cd524` (2025-04-14, "my setups") as a copy of
  `setup_mutau.yml` with the same channel and tag.
- **L11** `loadmacro("python/macros/mapDecayModes.C")` is from `25ec87c` (2021-07-15, "add DM; implement DM mapping;
  add loadmacro; ..."); `loadmacro` moved to `common/python/tools/root.py` in `e2b48d4` (2024-01-24) and has always
  ignored the result of `ProcessLine`. Correct as long as `plot.py` runs in `Plotter/`.
- **L12** both lines of `getmcsample` (`picodir = kwargs.get('pico', "")`, then `picodir = ""`) came in together
  with the function in `4ad2351` (2022-05-28, "add stitch plotting").
- **L14, L15** came into `samples_v15.py` with the file itself, `68c0a53` (2025-04-21, "2025 and Summer24", a copy of
  `samples_Summer24.py`); the lines are older copies from config to config. Found by the sample-model export (CL §20).
- **L16** era `2526` was added in `eb6b5b3` (2026-08-06, "2026 and 2025+2026 '2526'") to the era tests of
  `samples_v15.py`, but not to the `%d` year patterns of the tautau and emu data; `getyear` finds no year in `'2526'`.
- **L18-L21** (createinputsTES.py, found in the step-2 planning, plan 16): the control-plot block under
  `if "systematics"` (L18) is as old as the script, `9fd9d46` (2021-08-26, "TES combine"; the `systematics` test from
  `409358f`, 2022-02-24); `varprocs` per channel (L19) from `5837e8c` (2023-03-20); `createinputs` without `recreate`
  (L20): the nominal call had `recreate=True` from `9fd9d46` until `58d5fb2` (2022-01-26, "Started changing
  createInput.py to avoid hard coding long lists"), which dropped it; L22 and L23 are as old as `rebinning.py`,
  `6a2e75b` (2024-05-22, "minor changes"); the doubled tag of L24 is as old as the script (`9fd9d46`); the rebinning of the
  first observable (L21) from `f66a886` (2025-12-04).

---

## Fitter

Defects in retired workflows are tracked in the [Legacy section](#legacy).
Latent defects in maintained modules and workflow options remain here.

Defects found while connecting the TES + tau ID fit to the TauFW Framework (Part G, October 2026, branch
`Refactor-2025`). They were found by reading the source of the wrapped workflow: `run_inputs.sh`,
`run_workflow_zmm.sh` and the scripts they call. A bug is fixed when the **Fix** column names the part that fixed it.

Policy (same as [PicoProducer](#picoproducer)): bugs on the path the Framework runs
are fixed and recorded here, with `# BUGS <ID>` comments at the changed lines. Bugs off that path are registered
only. The Fitter has no BBB case, so **Output impact** describes the change for a user of the scripts.

**Severity:**
- **crash:** raises an exception on a reachable path.
- **wrong:** silently produces a wrong result or does the wrong thing.
- **latent:** the code is wrong but nothing reaches it today.

<a id="fitter-tes--tau-id-workflow-option-3"></a>

### TES + tau ID workflow (option 3)

| ID | Location | Symptom | Severity | Fix | Output impact |
|---|---|---|---|---|---|
| F01 | `run_workflow_zmm.sh` (merge step) | `merge_tau_jsons.py` is called without `-y`; its default year is `2024` and it filters the input files by year (`merge_tau_jsons.py:208`), so the 2025 merge finds no correction files | wrong | Part G: `-y $YEAR` | `tau_sf/TauCorrections_2025.json` now contains the 2025 corrections (it was empty or held 2024 ones) |
| F02 | `run_workflow_zmm.sh` (last step) | `make_tid_2025.py` is called without `-y`; its default `2025` is right only for 2025 | wrong for other years | Part G: `-y $YEAR` | none for `YEAR=2025` |
| F03 | `run_inputs.sh` (also `run_inputs_2526.sh`, `run_inputs_pnet.sh`) | `STATUS=${PIPESTATUS[0]}` is read after the *unpiped* mumu command, so a failure of the mutau command is ignored (and in `run_inputs_pnet.sh` a mumu failure is ignored) | wrong | Part G: the mutau status is read right after its pipe; a mumu failure counts too | a failed working point is reported and skipped, as the script intended |
| F04 | `TauES_ID/makecombinedfitTES_SF.py` `generate_datacards_mutau`, argument parser | `--input_file` is required but never used: the function looks for `input_file` in `locals()`/`globals()` right after setting it to `None`, so the branch that would pass it on is dead (and `harvestDatacards_TES_idSF_MCStat.py` has no such option, so it would crash) | latent | Part G: the dead branch and the option are removed; callers updated (`run_workflow_zmm.sh`, `Legacy/run_workflow.sh`) | none (the datacards always came from `-i`); `--input_file` is now an unknown option |
| F05 | `TauES_ID/makecombinedfitTES_SF.py` `run_combined_fit` (option 3, parameter file) | If no grid point lies within 1 sigma, `tes_low`/`tid_low` are `None` and `f"{None:.6f}"` raises `TypeError`, so `FitparameterValues_*.txt` is not written and the later steps of that region fail | crash | Part G: the 1-sigma lines are written only when the interval exists | the parameter file exists for every fitted region; regions without an interval have no `_1sigma_low/high` lines (the post-fit step already skips missing lines) |
| F06 | `TauES_ID/makecombinedfitTES_SF_postfit.py` (option 3) | `--impacts` and `--impacts-parallel` are parsed but ignored: the impacts always run (slow) with `--parallel 8` | wrong | Part G: impacts run only with `--impacts`, with `--parallel <--impacts-parallel>`; `run_workflow_zmm.sh` passes `--impacts`, so its output is unchanged | without `--impacts` no `impacts/`, `impacts_*.json` are made |
| F07 | `TauES/createinputsTES.py` (control plots after rebinning) | The rebinned file is read from `<outbase>/rebinning/`, but `python/plot/rebinning.py` writes it next to the input file (`<outbase>/againstjet_<J>/againstelectron_<E>/rebinning/`), so the rebinned control plots open a file that does not exist (the shapes themselves are written before this) | wrong | Part G: the path of `rebinning.py` is used. confirmed on lxplus 2026-10-17: the rebinned control plots appear in `<outbase>/againstjet_<J>/againstelectron_<E>/plots/rebinning/` | rebinned control plots are made; before, the script failed or plotted an empty file after the shapes were written |
| F08 | `TauES_ID/makecombinedfitTES_SF.py` `run_combined_fit` | `merge_datacards_regions` is called with 7 arguments (with `mumu_input_file`) but takes 6 | crash (options 4-6) | registered only (option 3 does not reach it) | |
| F09 | `TauES_ID/makecombinedfitTES_SF.py` `merge_datacards_regions` | `hasattr(setup, 'mumu_datacard_file')` on the setup dict is always false, so the Zmm card is never added | latent (options 4-6) | registered only | |
| F10 | `TauES_ID/makecombinedfitTES_SF.py` `merge_datacards_regions` | the combined card is written to `output_{era}/` instead of the output directory | wrong (options 4-6) | registered only | |
| F26 | `TauES_ID/makecombinedfitTES_SF.py:505` `run_combined_fit` (option 6) | reads `setup['tidRegions']`, but the configs name the key `tid_SFRegions` (the key `harvestDatacards_TES_idSF_MCStat.py` and `plotParabola_POI_region.py` read), so option 6 raises `KeyError` | latent (option 6; the workflow runs option 3) | registered only (plan 16 §8, CL §22) | none |

<a id="fitter-paths-and-working-directory-r3-inventory"></a>

### Paths and working directory (R3 inventory)

Found while preparing R3 (October 2026): the Framework will run the scripts with the stage's output directory
(`taufw_runs/<run>/stages/<id>/`) as working directory instead of `Fitter/`, so every path that depends on the
working directory or on the module directory was read. **R3** in the Fix column: fixed by R3 without changing what
the shell scripts produce. **After R3**: on the Framework path, but the fix changes the output of the shell scripts,
so it comes in its own commit after the shell/Framework comparison of R3.

| ID | Location | Symptom | Severity | Fix | Output impact |
|---|---|---|---|---|---|
| F11 | `TauES_ID/makecombinedfitTES_SF.py` (end of `run_combined_fit`, lines ~512-515) | `mv higgsCombine*root`, `mv *.root` and `mv *.png` move every such file of the working directory into the output directory of the current working point. The post-fit step leaves `higgsCombine.<label>.FitDiagnostics.mH90.root` and the impact fits `higgsCombine_*Fit_Test*.root` in the working directory, so the fit of the **next** working point moves them into its own output directory | wrong | registered only; after R3 | |
| F12 | `TauES_ID/makecombinedfitTES_SF_postfit.py` (`FitDiagnosticsValues/`, lines ~366-367) -> `plot_measurements.py` (line ~384) | `FitDiagnosticsValues/VSjet<J>_VSele<E>/` has no era, so with two eras in one working directory the measurement plots of one era show the post-fit values of the other. `impacts/`, `impacts_<r>.json`, `output_plots/`, `combined_pre_post/` and `Measurements/` have no era either | wrong | registered only; R3 runs each era in its own directory, which avoids it; script fix after R3 | |
| F13 | `TauES_ID/makecombinedfitTES_SF.py` `merge_datacards_ZmmCR` (line ~158), `TauES_ID/makecombinedfitTES_SF_postfit.py` (line ~69) | the combined card `ztt_mt_m_vis-<region>_zmmCR.txt` has no config tag, so two configs fitted into the same working point directory overwrite each other's card | latent | registered only; after R3 | |
| F14 | `TauES_ID/harvestDatacards_zmm.py` `harvest` / `main` (lines ~32, ~208) | without `-o`, `main` passes `outdir=None` explicitly, so the default `output_pt_less_region/<year>` of `kwargs.get` never applies and the cards are written with an output directory `None` | crash (standalone use) | R3 (CL §15), checked on lxplus: the default applies again | none for the callers, which always pass `-o` |
| F15 | `TauES_ID/makecombinedfitTES_SF.py` (lines ~90, ~544) | the datacard script and the 2D scan plotter are started as `python3 TauES_ID/<script>.py`, relative to the working directory, through `os.system`, whose exit code is ignored. Outside `Fitter/` both fail with "can't open file" and the fit goes on without new cards or scan plots | wrong (outside `Fitter/`) | R3 (CL §15), checked on lxplus: paths from `__file__`; exit codes: TODO §6 B | none in `Fitter/` |
| F16 | `TauES/createinputsTES.py` (line 8) | `sys.path.append("../Plotter/")` is relative to the working directory; outside `Fitter/` `from config.samples_v15 import *` raises `ModuleNotFoundError` | crash (outside `Fitter/`) | R3 (CL §15), checked on lxplus: path from `__file__` | none in `Fitter/` |
| F17 | `make_tid_2025.py` (`SF_DIR`, line 19) | the per-working-point correction files are always read from `Fitter/tau_sf/` (the module directory), with no option, while `createroot_TES.py` writes them to `tau_sf/` of the working directory | wrong (outside `Fitter/`) | R3 (CL §15), checked on lxplus: `--sf-dir` (default unchanged) | none in `Fitter/` |
| F18 | `TauES_ID/makecombinedfitTES_SF.py` (lines ~178, ~574), `TauES_ID/harvestDatacards_TES_idSF_MCStat.py` (line ~59), `TauES_ID/plot2DScan_MultiDimFit.py` (lines ~602, ~999, ~1276), `TauES_ID/makecombinedfitTES_SF_postfit.py` (lines ~92, ~266) | output directories are derived from input directories with `str.replace('input', 'output')`, `('output', 'plots')`, `('output', 'postfit')` and `('postfit', 'output')` on the **whole** path. `plot2DScan_MultiDimFit.py` already gets an absolute path (`os.path.abspath` in `makecombinedfitTES_SF.py`), so any `output` elsewhere in that path (a user or run directory) sends the scan plots to a different, newly created tree | latent | partly, R3 (CL §15), checked on lxplus: with `--output_dir`/`--plot_dir`/`--outdir` (the Framework always passes them) the derivation is not used; without them it stays | |
| F19 | `createroot_TES.py` (lines ~197-206, ~460-464, ~545-548) | if no `FitparameterValues_*` file is found, the correction files are written with every scale factor 1.0, and the script exits 0 | wrong | registered only; after R3 | |
| F20 | `merge_tau_jsons.py` (lines ~148-150, ~212), `plot_measurements.py` (lines ~711-713) | when nothing is found the scripts print a message and exit 0 without writing their output | wrong | registered only; after R3 | |
| F21 | `make_measurements_grid.py` (`--dir`, line ~50) vs `plot_measurements.py` (line ~707) | the grid reads `Measurements/` next to the script (module directory), `plot_measurements.py` writes it in the working directory; consistent only when the working directory is `Fitter/` | latent | R3 (CL §15), checked on lxplus: the API passes `--dir` | |
| F22 | `python/api/tes_id.py` `_correction_glob` | `tau_sf/*_<era>_VSjet<J>_VSele<E>.<form>` also matches the files of other taggers (PNet, UParT), so they are listed in the fit artifact | wrong (artifact list) | R3 (CL §15), checked on lxplus: the glob is `tau_sf/*_SF_dm_DeepTau*_<era>_VSjet<J>_VSele<E>.<form>` | the fit artifact lists only DeepTau files |
| F23 | `python/plot/runpostfit.py` (line ~45) | the post-fit file name has `__mutau_` hard-coded instead of the config's tag, so a config with another tag fails to open its post-fit shapes | latent | registered only | |
| F24 | `tau_tid_2024.py` `makecorr_tid` (lines ~395-421), through `make_tid_2025.py` | if no per-working-point file is found, `makecorr_tid` takes its "test format with dummy values" branch (Loose/Medium, SF 1.0 +- 0.2) instead of failing; what it writes then is not yet checked on lxplus | wrong | registered only; after R3 | |
| F25 | `python/api/tes_id.py` `TauESID.__init__` (default `find_module`), used by `preflight_shapes` and `preflight_fit` (`_environment`, CombineHarvester check) | the same as Plotter L13: `importlib.util.find_spec('ROOT')` raises `ValueError: ROOT.__spec__ is None` when CMSSW's ROOT is already imported in the process (e.g. after a production stage, or after the plots stage's own checks). The histograms and fit stages then raise at preflight | crash | CL §16 (exception to the no-fix rule: it blocked every recipe with production and plots on lxplus): `_module_exists`, a module already imported counts as found | none: the preflight answers instead of raising |

<a id="fitter-how-old"></a>

### How old

Open bugs only; fixed ones are left out.

- **F08** The 7-argument call has been broken since commit `f0f75f3` (2025-10-24, "2D fit"). That commit added
  `mumu_input_file` support (a new optional argument of `merge_datacards_ZmmCR` and `mumu_input_file = kwargs.get(...)`
  in `run_combined_fit`), and added `mumu_input_file` to the `merge_datacards_regions(...)` call without changing that
  function's 6-argument signature. `f66a886` (2025-12-04) then passed `mumu_input_file=args.mumu_datacard_file` from
  `main`, still without fixing the signature. Options 4-6 have raised `TypeError` ever since. Nobody noticed because
  every driver (`run_workflow*.sh`, `api/tes_id.py`) runs option 3 only.
- **F09** The `hasattr(setup, 'mumu_datacard_file')` check has been broken since the day it was written: commit
  `5a08f58` (2025-09-26, "2D parabola"). That commit replaced the old `if str(config_mumu) != 'None':` Zmm-CR branch
  (left behind as a comment) with this check, and set `setup['mumu_datacard_file']` in `main`. `setup` is a dict
  loaded from YAML, so `hasattr` on a key is always false and the Zmm card was never added. Nobody noticed because
  only options 4-6 reach this code, and since `f0f75f3` they crash first (F08).
- **F10** The `output_{era}/` path is older than the output-directory option. It goes back to the first commit of
  the folder, `2c8819e` (2022-11-09, "TauES_ID folder containing code to to do the combined fit of TES and ID SF"),
  and became `merge_datacards_regions` in `6dc9a0a` (2023-07-06, "update of the combined fit script, option to
  include Zmm CR"). Back then everything used `output_{era}`, so it was correct. It became wrong with `9ebb7a0`
  (2024-06-19, "introduce input and output directory separate for different wps of against jet and against
  electron"), which made `run_combined_fit` read `{output_dir}/{datacardfile}.txt` but left this function writing to
  `output_<era>/`. `5a08f58` (2025-09-26) moved the regions-only card to `output_dir` but kept the combined card in
  `output_{era}/`. Nobody noticed because the line sits behind the always-false F09 check, and options 4-6 crash
  first anyway (F08).
- **F11** `9ebb7a0` (2024-06-19, "introduce input and output directory separate for different wps of against jet and
  against electron") added the `mv` lines when the output directory per working point came in. The stray files they
  now pick up came later: `FitDiagnostics` and the impacts in the working directory with the post-fit script of
  `5a08f58` (2025-09-26, "2D parabola") and `7360158` (2025-10-03, "Fitter upgrade 2D").
- **F12** `FitDiagnosticsValues/VSjet<J>_VSele<E>/` was introduced in `f66a886` (2025-12-04, "Full Fitter +
  Plotter, ..."), already without the era. Every driver runs one era at a time in `Fitter/`, so it never showed.
- **F13** The `_zmmCR` card name is from `6dc9a0a` (2023-07-06, "update of the combined fit script, option to include
  Zmm CR"), when there was one config.
- **F14** `outdir=args.output_dir` is from `9ebb7a0` (2024-06-19); every caller since passes `-o`.
- **F15** The relative `TauES_ID/harvestDatacards_TES_idSF...` call is in the first commit of the folder, `2c8819e`
  (2022-11-09); the `python3 TauES_ID/plot2DScan_MultiDimFit.py` call came with `7360158` (2025-10-03). Correct as
  long as everything runs in `Fitter/`.
- **F16** `sys.path.append("../Plotter/")` came with `007966c` (2022-01-14, "Some local changes and bug fixes (?)
  ..."); correct as long as the script runs in `Fitter/`.
- **F17** `SF_DIR` next to the script is from `7589a86` (2026-05-19, "1D plotting and corrlib file maker"), which
  also brought the dummy branch of F24.
- **F18** `input_dir.replace('input', 'output')` is from `9ebb7a0` (2024-06-19); `indir.replace('output', 'plots')`
  and `fit_outdir.replace("output", "postfit")` from `5a08f58` (2025-09-26); `param_file.replace("postfit",
  "output")` from `7360158` (2025-10-03). All assume a relative path whose only `input`/`output` is the first
  component.
- **F19** The glob of `FitparameterValues_*_DeepTau_*` with its 1.0 default came with `feb8ebd` (2025-12-05, "update
  to new file structure").
- **F20** `plot_measurements.py`'s "No measurements found!" return is from `aa0b1a1` (2025-10-29, "plotter").
- **F21** `make_measurements_grid.py` came with `7a2875c` (2026-05-15, "Refactor workflow scripts and add grid
  generation ..."), with the module directory as default.
- **F22** `_correction_glob` came with the Fitter API, `c27abb7` (2026-10-13, Part G).
- **F23** `__mutau_` is from `27f31c6` (2025-10-20, "postfit Zmm plots").
- **F24** see F17: `7589a86` (2026-05-19).
- **F26** `tidRegions` came with option 6, `6dc9a0a` (2023-07-06); found in the step-2 planning (plan 16, CL §22).

---

## Framework

Defects of the TauFW Framework (`Framework/`), found while planning the recipe IO work (R4, October 2026, branch
`Refactor-2025`) by reading the source. A bug is fixed when the **Fix** column names the part that fixed it.

Policy: until the refactor is finished, bugs are registered only (no fixes); each fix comes later in its own commit.
**Output impact** describes the change for a user of `taufw.py` (and for the BBB case `framework.production`,
which records `run.json`).

**Severity:** **crash** (raises on a reachable path), **wrong** (silently wrong), **latent** (the code is wrong but
nothing reaches it in normal use).

| ID | Location | Symptom | Severity | Fix | Output impact |
|---|---|---|---|---|---|
| K01 | `python/runtime/framework.py` `_context`, `python/runtime/run_record.py` `RunRecord.load` | A run directory that is moved or copied is loaded with its new location (`run_dir` comes from where `run.json` is), but the artifacts of its `DONE` stages in `run.json` keep the old absolute paths. The next stage then reads the files at the old location: silently if they still exist (a copy, or `cp -r` and both copies advanced), or it fails while its commands run if they do not. The fit's preflight does not catch it, because it checks the shapes on disk only when no stage of the run makes them (`stages/fit.py` `preflight`). | latent | registered only (moving runs belongs to the deferred disk/EOS work) | |
| K02 | `python/runtime/framework.py` `_advance_stages` (manifest written before `run.json` is saved), `Utilities/python/Process/_outdir.py` `output_dir_problems` | If the process stops after a stage's `manifest.json` is written and before `run.json` is saved, the stage is still `NEW` in `run.json`, but its output directory is no longer empty (it holds the manifest). The next `advance` stops in preflight with "output directory ... is not empty" until the directory is removed by hand. The comment there says such a crash "only repeats the stage", which is not true for the local stages. A later input that names this directory by path would also accept it, since only a `DONE` stage has a manifest. | latent | registered only | |
| K03 | `python/stages/local.py` `advance` (`last_status.inputs`), `python/stages/plots.py`, `python/stages/histograms.py` | The `tuples` input slot selects no data: plot.py and createinputsTES.py always read the tuples through `$PICODIR` of the run's PicoProducer configuration, and `inputs.tuples` (a production stage, or `null`) is only recorded. If the configuration's `$PICODIR` is not where that production stage wrote, the stage reads other tuples than the ones its input names, and `run.json` lists the named ones. | wrong (design limit) | CL §16 step 6: plots and histograms get the pattern of the tuples their input names (`--tuples`), from the production stage's artifacts or `{external: ...}`; `null` keeps the old behaviour (old recipes only) | none for `null`; with a production input the scripts read the production stage's tuples instead of `$PICODIR` |
| K04 | `python/stages/production.py` `_merge` (artifacts are `TupleArtifact.to_dict()`), `python/runtime/step_runner.py` `StepContext.input` | The tuple artifacts of a production stage have no `kind` key (the artifacts of every other stage have one, e.g. `kind: shapes`). A filter by kind therefore finds none: in a python step `ctx.input('<production id>', kind='tuples')` returns an empty list, and so does `StageContext.input_artifacts('tuples', kind='tuples')`. Nothing filters tuples by kind today. | latent | **fixed (CL §36)**: `TupleArtifact.kind = 'tuples'`, also on the planned record; the local stages read only that kind | adds `kind: tuples` to the production artifacts in `run.json` and `manifest.json` (BBB `framework.production`) |
| K05 | `python/recipes/recipe.py` `_pico_config_path` and `Recipe.load`, `python/recipes/validation.py` `_file_issues`, `python/recipes/bundle.py` `where` | These test absoluteness with `os.path.isabs`. On Windows with Python 3.13 a path that starts with `/` but has no drive (`/afs/...`, `/eos/...`) is not absolute, so an lxplus `pico.config` is joined to the bundle directory: `os.path.join(bundle, '/afs/x')` gives `C:\afs\x`. `taufw.py check` on Windows then reports "file not found: C:\afs\..." instead of the path as written. On Linux (lxplus) nothing changes. | latent (Windows only) | **fixed (CL §38)**: one test, `bundle.is_absolute` (posixpath or os.path), in `bundle.where`, `recipe.py` and `validation.py` | none on lxplus; on Windows an lxplus path is reported as written |
| K06 | `scripts/taufw.py` `main` (catches only `RecipeError` and `RunDirectoryError`), `python/recipes/recipe.py` `read_recipe` | `taufw.py plan` or `start` with a recipe path that does not exist (a typo, a file not made yet) ends with a `FileNotFoundError` traceback from `TauFW.Utilities.FIO`, instead of one line naming the missing file (`taufw.py check` reports it as "cannot read ..."). Found on lxplus on 2026-10-17. | crash (message only) | fixed 2026-10-18 (`Recipe.load` turns a read error into a `RecipeError`; tests in `Tests/Framework/test_framework.py`) | none: one line instead of the traceback |
| K07 | `python/runtime/framework.py` `Framework.status` (`message=stage_record.message`), `python/stages/production.py:77` | `taufw.py status` shows the stage message saved by the last `advance` next to the live job table. After a resubmission whose jobs have all finished, the production row still says "4 chunk(s) failed or missing; resubmitting (try 2 of 2)" while the job table below it says 4 good, complete `yes`. The state and message are correct as saved, but the two read as a contradiction; the message is not marked as coming from the last `advance`. Seen on lxplus on 2026-10-17 (CL §16 production test). | wrong (message only) | registered only | `status` output only |
| K08 | `python/runtime/framework.py` `check_writable` | When the run root and several of its parents do not exist, the write test runs in the nearest existing parent and the warning names only that probe file and advises `kinit; aklog`. `--run-root /afs/cern.ch/work/y/<user>/runs` without a work area gives "cannot write in the run root ...: Read-only file system: '/afs/cern.ch/work/y/.taufw_write_test_<pid>'": the real cause, that `/afs/cern.ch/work/y/<user>` does not exist, is not said. Seen on lxplus on 2026-10-18 (plan 18 §14 K11 reference run). | wrong (message only) | registered only | the warning names the missing directory |

---

## Legacy

Consolidated on **2026-10-14** from existing bug registers, legacy READMEs,
[component inventory](Refactor-2025/Legacy.md),
[analysis inventory](../../Legacy/OldAnalysis/README.md), [refactor TODOs](Refactor-2025/TODO.md),
test documentation and the local cleanup audit. This consolidation inspected documentation only;
it did not search implementation code for bugs or verify runtime behavior.

This section owns known defects in retired workflows, archived package modules and excluded
broken demonstration/test scripts. Existing IDs and recorded fix status are preserved.
Rows without an earlier ID use `LEG-*` identifiers assigned for this register.
Archiving is not a fix; repair these paths if they are revived.

Bugs in maintained code remain in the [PicoProducer](#picoproducer),
[Plotter](#histogrammer) and [Fitter](#fitter) sections and
[refactor TODOs](Refactor-2025/TODO.md). Being old, unused, latent, or outside
the main Framework workflow alone does not make a defect a legacy bug. Historical
change-log records and archive retirement reasons remain in their original documents.

<a id="legacy-picoproducer"></a>

### PicoProducer

Moved from the PicoProducer register. Locations below are repository-relative;
`analysis/` in the A01 history refers to the original PicoProducer package location.
Severity and BBB coverage retain the source register's definitions.

| ID | Location | Symptom | Severity | BBB | Session | Fix | Output impact |
|---|---|---|---|---|---|---|---|
| W03 | `Legacy/OldAnalysis/2018/dumpGen.py` (was `processors/dumpGen.py`) | Not referenced anywhere | latent | no | S2 | moved to `Legacy/OldAnalysis/2018/dumpGen.py` (not fixed) | none |
| A11 | `Legacy/OldAnalysis/2016-2017/CheckMuTrigger.py:26` | Trigger threshold attributes are assigned but unused (hard-coded 24 GeV); `trigsf` stays 1.0 | wrong | no | S2 | moved to `legacy/` (not fixed) | none |
| A13 | `import *` chains (now only in the component package archives and `Legacy/OldAnalysis/`) | `datadir` is rebound by BTagTool/PileupTool/JetVetoMapTool/TauTriggerSFs and leaks through star imports. JetTauFakeRate works around it with `replace("/pileup","")`. Session 2 replaced every star import outside `legacy/` by explicit imports of the *same* objects: all maintained modules see the base `datadir`, as before | wrong | no | S6 | | |
| C10 | `Legacy/PicoProducer/python/corrections/PreFireTool.py` | `from corrections import ...` fails, and CMSSW_BASE path building raises without CMSSW | crash | no | S2 | moved to `legacy/` (not fixed) | none |
| A01 (archived copies) | `Legacy/PicoProducer/python/analysis/ModuleMuTau_nanoV10_DeepTau2p1.py`, `analysis/TauES/ModuleMuTau.py`, `analysis/MuTauFakeRate/ModuleMuTau.py` (all under that legacy package) | `getlepvetoes(...)` is called without the required `era` argument; the first event reaching the vetoes raises `TypeError` | crash | no | S6 | not fixed | Maintained copies remain under A01 in the production register |

<a id="legacy-recorded-origins"></a>

#### Recorded origins

- **W03** `dumpGen.py` has had no references from day one: commit `d5c9d36` (2020-05-25, "add dump gen processor")
  added it as a standalone script ("Standalone to dump gen particle information"; its usage line still says
  `python dumpLHE.py`, a copy-paste leftover). The only mentions are a link in the header of `analysis/GenDumper.py`
  (`195c53d`, 2020-06-22) and a line in `processors/README.md` (`fc46a42`, 2021-07-16). It is a script run by hand,
  so it never had a caller. It moved to legacy in `0bc4d62` (2026-10-12).

- **A11** `CheckMuTrigger` has been like this since the day it was written: commit `62b74a8` (2021-07-20, "split
  triggers") created it as `analysis/ModuleMuTrigger.py`, already with the unused threshold lambdas, the hard-coded
  `if muon.pt<24: continue` and `self.out.trigsf[0] = 1.0 # TODO`. Since then it was only renamed (`eea9c66`,
  `18da2c3`, `490dd93`, 2021-07-23) and moved (`0bc4d62`, `623a040`, 2026-10). It is a one-off trigger-overlap study
  and nothing reads `trigsf`, so nobody noticed.

- **A13** The `datadir` leak has been there since the day the code was written: commit `f8ba048` (2020-06-21) created
  `PileupTool.py` with a module-level `datadir = os.path.join(datadir,"pileup")` (and `BTagTool.py` with `"btag"`),
  and `ModuleTauPair.py` star-imported `PileupTool`. `TauTriggerSFs` (`8ce519b`, 2020-07-18) and `JetVetoMapTool`
  (`26271a6`, 2024-03-25) later rebound it the same way. The `replace("/pileup","")` workaround came in `5853bb3`
  (2022-06-21, JetTauFake modules, with the comment "for some reason the pileup subfolder is selected as datadir ...
  fixme") and was copied in `50f604f` (2022-07-26). Maintained modules almost never use `datadir` directly, and the
  one author who hit it patched around it, so it was never fixed.

- **C10** `PreFireTool` has been broken since it was added in `7c97e15` (2020-06-21, "add correction tools"), with
  `from corrections import modulepath, extractTH1` (`modulepath` was never defined in this repo; probably a
  leftover of an older standalone setup) and the `CMSSW_BASE` path. `RecoilCorrectionTool` had the same bad import
  and was fixed in `64ce575` (2020-07-06); `PreFireTool` never was. Every use has always been commented out, so it
  was never imported. `0bc4d62` (2026-10-12) only moved it to `legacy/`.

The archived A01 callers originate from the same 2020 commits as the maintained
callers. `9411be0` (2023-10-19) added `era` with a default; `877e636` (2024-02-20)
made it required. See the [maintained A01 history](#picoproducer-analysis-modules-and-writers).

<a id="legacy-fitter-archives"></a>

### Fitter archives

Sources: [Fitter archive README](../../Legacy/Fitter/README.md) and
[component inventory](Refactor-2025/Legacy.md). All entries remain unfixed.
Paths are relative to `Legacy/Fitter/`.

| ID | Location | Recorded defect | Replacement |
|---|---|---|---|
| LEG-F01 | `createJSON_TES.py` | Imports the missing `fit_tools` module | `Fitter/createroot_TES.py -f json` |
| LEG-F02 | `run_createroot_TES.py` | The `hadd` command contains literal `{era}`, `{jet_wp}` and `{ele_wp}` placeholders; `jet_wp` is also never assigned. The inventory clarifies that this command is not interpolated, so that line is a malformed command rather than a Python `NameError` | Export step of `Fitter/run_workflow_zmm*.sh` |
| LEG-F03 | `TauES/doTES.sh` | Uses the missing `Fitter/analysis/TauES` location and removed scripts | `Fitter/run_workflow_zmm*.sh` |
| LEG-F04 | `TauES_ID/saveSFs_root_JSON.py` | Calls missing `saveSFs_root.py` | `Fitter/createroot_TES.py` |
| LEG-F05 | `scripts/plotBiasTest.py`, `scripts/plotChannelCompatibility.py` | Python 2 syntax raises `SyntaxError` in Python 3 | No replacement recorded |
| LEG-F06 | `ETauFR/Fitting.sh` | Calls removed `compare.py`; the inventory also records a personal AFS path | `Fitter/ETauFR/runAll_combFit.sh` |
| LEG-F07 | `paper/postfit.sh` | Calls removed `writecards.py` | No replacement recorded |

<a id="legacy-plotter-archives"></a>

### Plotter archives

Sources: [Plotter archive README](../../Legacy/Plotter/README.md),
[JetToTauFR README](../../Legacy/Plotter/python/corrections/JetToTauFR/README.md),
[component inventory](Refactor-2025/Legacy.md) and the local cleanup audit
(`LocalR/CodebaseCleanupAudit.md`, historical paths). All entries remain unfixed.

| ID | Location (repository-relative) | Recorded defect or limitation | Recorded workaround |
|---|---|---|---|
| LEG-L01 | `Legacy/Plotter/python/corrections/JetToTauFR/plotJetToTauFRvariables_writeJson.py` | JSON final-state/barrel key is written as `mumettau__mumettau:Barrel` instead of `mumettau_Barrel`; endcap has the same issue | Manually correct the barrel and endcap keys before reading/applying the fake rates |
| LEG-L02 | `Legacy/Plotter/python/corrections/JetToTauFR/plotJetToTauFRvariables_writeJson_FRinPtBins.py` and its consumers | pT-only fake rates require a manual eta-list change in `readAndPlotFR.py` and `Legacy/Plotter/python/methods/JetToTau_MisID.py` | Set `eta = [""]` in both consumers for pT-only results |
| LEG-L03 | `Legacy/Plotter/python/corrections/JetToTauFR/` workflow | Recorded Python 2 dependencies (`StringIO`, `raw_input`), implicit relative imports and personal AFS configuration paths; this is a workflow-level limitation, not a claim that every helper has all defects | Review dependencies and paths before reuse |
| LEG-L04 | `Legacy/Plotter/python/methods/ScaleVariations.py` | Cannot be selected by `method='ScaleVariations'`: there is no matching attribute | No workaround recorded |
| LEG-L05 | `Legacy/Plotter/python/corrections/JetToTauFR/tools/styles.py` | Two different `getSignalStyleHToTB()` definitions; the later definition hides the first | No workaround recorded |
| LEG-L06 | `Legacy/Plotter/python/corrections/JetToTauFR/tools/histograms.py` | `HistoEfficiency.getYmin()` and `getYmax()` are redefined; earlier calculations incorporating efficiency uncertainties are hidden | No workaround recorded |
| LEG-L07 | `Legacy/Plotter/python/corrections/JetToTauFR/readAndPlotFR.py` | Additional plot text is disabled with `if 0:`; another disabled block contains an OpenGL setting | Recorded as an ineffective feature; no runtime failure established |

<a id="legacy-one-off-analysis-archives"></a>

### One-off analysis archives

Source: [analysis inventory](../../Legacy/OldAnalysis/README.md). All entries remain unfixed;
paths are relative to `Legacy/OldAnalysis/`.

| ID | Location | Recorded defect or integration constraint |
|---|---|---|
| LEG-O01 | `2018/takeZmu.py` | Invalid indentation prevents parsing; `dm` is referenced after its defining loop was commented out |
| LEG-O02 | `2022/plot_mvis_uncorr_corr.py` | Uses `os` without importing it |
| LEG-O03 | `2016-2018/plot2D.py` | Advertised 2022 eras are rejected by its Run 2 sample configuration |
| LEG-O04 | `2016-2018/plot_compare.py` | Sample-set construction call is commented out |
| LEG-O05 | `YearIndependent/plot_GENSIM.py` | Calls `tree.MultiDraw` without importing the module that installs it |
| LEG-O06 | `2016-2018/aco.C`, `2016-2018/corrs_ntracks.C` | Required external ROOT payloads are absent from the repository and are resolved through original absolute paths; this is an integration constraint, not proof of an algorithmic defect |

The trigger-study and jet-to-tau analyzer defects are tracked above as A11 and A13.

<a id="legacy-excluded-broken-test-and-demonstration-scripts"></a>

### Excluded broken test and demonstration scripts

Moved from `Tests/LEGACY_BROKEN_CASES.md`; the following report preserves its
recorded evidence and validation limits. These defects concern test/demo scripts,
not proof that the corresponding production classes are broken.

These two cases are excluded because their existing scripts cannot complete in
the Python 3.9 test environment. The migration preserved their contents; it did
not introduce the defects described below. This report documents the problems
without fixing them.

<a id="legacy-overview"></a>

#### Overview

| Case | Classification | First failure in a suitable dependency environment |
| --- | --- | --- |
| `pico.sample` | `broken` | The `print(` call at line 88 has no closing parenthesis outside its comment. |
| `plotter.rdataframe` | `broken` | With PyROOT available, module execution reaches an undefined `kBlue` at line 17. |

The classifications describe these demonstration/test scripts. They do not
establish that the corresponding production classes are broken.

<a id="legacy-picosample-a-parenthesis-hidden-inside-a-comment"></a>

#### `pico.sample`: a parenthesis hidden inside a comment

Source: [testSample.py](../../Tests/PicoProducer/testSample.py).

Line 88 reads:

```python
print(">>> Call Sample.getfiles..." # load Sample.files from txt file)
```

Everything after `#` is a comment, including the apparent closing `)`. The
opening `print(` therefore remains unclosed. Python cannot parse the module, so
none of its imports, sample construction, matching checks, or file operations
execute. This is a syntax defect, not a failing `Sample.getfiles()` call.

There is a separate integration constraint beyond the syntax error. Lines
14–35 configure real 2016 CMS datasets with no supplied local storage or file
list. Line 74 calls `sample.writefiles(..., nevts=True)`, which requests file
discovery and per-file event counts. The production
[Sample storage code](../../PicoProducer/python/datasets/sample.py) routes discovery
to DAS when no storage source is available (`getfiles()`, lines 224–248).
Consequently, even a syntactically repaired script would not be an isolated,
offline normal test with its current defaults. This dependency is not itself
proof of another runtime defect, and no DAS request was made for this report.

<a id="legacy-plotterrdataframe-multiple-independent-runtime-defects"></a>

#### `plotter.rdataframe`: multiple independent runtime defects

Source: [testRDataFrame.py](../../Tests/Plotter/testRDataFrame.py).

This file parses as Python 3, but its module-level execution fails before
`main()` in an environment with working PyROOT. Line 11 imports only `TNamed`,
`RDataFrame`, and `RDF` from ROOT. Line 17 then evaluates:

```python
lcolors = [kBlue+1, kRed+1, kGreen+1, kMagenta+1]
```

None of those color names is defined in the Python namespace. `import ROOT`
does not make unqualified names such as `kBlue` available. The first lookup
raises `NameError`; the subsequent color names have the same issue.

Correcting the color imports alone would leave these problems:

| Location | Problem | Consequence if reached |
| --- | --- | --- |
| Lines 89, 145–150, 167 | `sampleset_RDF()` expects each input to unpack into `(stitle, fname, weight)`, but `main()` supplies filename strings. CLI `--fnames` also supplies strings. | The default paths raise `ValueError: too many values to unpack (expected 3)` before an RDataFrame is constructed. |
| Lines 103 and 122 | `res_dict` and `sname` are never defined. The loop defines `stitle`, not `sname`. | Histogram bookkeeping cannot proceed; line 103 first fails on `res_dict` if execution reaches it. |
| Lines 108–112 | `xvar` is read before its later assignment; `vfname` and `xexp` are also undefined. The variable loop instead defines `vname` and `vexp`. | Line 108 would raise `UnboundLocalError` for `xvar`; the expression-definition path has further undefined names. |
| Line 115 | `wname` is undefined. A `weight` string exists, but no corresponding `wname` is established. | The histogram booking call cannot execute as written. |
| Line 66 | `plot()` uses `TCanvas` without importing or defining it. | Calling this helper would raise `NameError`. The current `main()` does not call it. |
| Lines 143–150 | Default inputs live under `/scratch/ineuteli/analysis/UL2018`. | These external files are not portable repository fixtures; later execution would require suitable inputs and branches. |

The failures after the color lookup are established by source inspection. They
are masked by the first failure in the unchanged script and were not reproduced
through a full ROOT execution. The separate `plotter.rdataframe_sample` case is
still classified as local; this exclusion concerns `plotter.rdataframe` only.

<a id="legacy-why-these-are-pre-existing-and-how-the-runner-handles-them"></a>

#### Why these are pre-existing, and how the runner handles them

For both files, the current SHA-256 hash after LF/CRLF normalization matches
the corresponding `canonical_sha256` in [migration.json](../../Tests/migration.json).
Their contents also match the original paths in the parent of migration commit
`046367c` (`git show 046367c^:<original-path>`), using the same normalization.
This directly confirms that the listed script defects existed before relocation.

[inventory.json](../../Tests/inventory.json) retains both case IDs and their reasons.
In [run.py](../../Tests/run.py), `select_cases()` maps `normal` to the `local` group and
selects only that group. Explicitly requesting one of these cases through
`normal --case ...` rejects the selection with its classification and reason;
it does not run the script or report a successful test.

<a id="legacy-validation-scope"></a>

#### Validation scope

Validation used source inspection, the migration/historical hash
comparisons, and in-memory parsing with Python 3.13.8's
`ast.parse(..., feature_version=(3, 9))`. Parsing reproduced the unclosed parenthesis
(and, before those cases were removed, the two Python 2 print failures), and confirmed that the RDataFrame
file passes syntax parsing. This grammar check is not execution under Python
3.9 or a PyROOT runtime test. No full test suite, ROOT event processing, or
remote dataset access was performed. At the time of the original report, only that Markdown report was added.

The Python 2 cases `common.loadingbar` and `common.table` were removed when
`LoadingBar` and `Table` moved to `TauFW.Utilities.CLI` (changelog §13, §15);
unit tests in `Tests/Utilities/test_cli.py` replace them.
