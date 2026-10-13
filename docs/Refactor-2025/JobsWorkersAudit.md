# Jobs and workers: behavior audit after the PicoProducer cleanup

**Author:** Yagizhan Dinckurt ([@yagizdkurt](https://github.com/yagizdkurt))
**Branch:** `Refactor-2025`
**Date:** 2026-10-13
**Compared:** `2580f35` ("Safety net before refactor", the last commit before any PicoProducer code moved)
against `df6eefd` (HEAD after Parts 1-5 and Part F)

This audit checks whether the job control plane (submit, resubmit, run, status, hadd, haddclean, clean) and the
batch workers (`picojob.py`, `skimjob.py`) behave exactly as before the cleanup. Every difference found is
explained: what changed, where, a scenario that shows it, why it happens and how much it matters.

No code was changed for this audit. It is a static, line-by-line comparison of the two commits; nothing was
run on lxplus or on a batch system.

## Contents

1. [Summary](#1-summary)
2. [Scope and method](#2-scope-and-method)
3. [What is unchanged](#3-what-is-unchanged)
4. [Documented changes (for reference)](#4-documented-changes-for-reference)
5. [Undocumented differences](#5-undocumented-differences)
   - [D1. Resubmit no longer picks up changed channel options](#d1-resubmit-no-longer-picks-up-changed-channel-options)
   - [D2. `resubmit --split` can switch to splitting by events](#d2-resubmit---split-can-switch-to-splitting-by-events)
   - [D3. Resubmit warns about a missing output directory instead of creating it](#d3-resubmit-warns-about-a-missing-output-directory-instead-of-creating-it)
   - [D4. `haddclean -f` keeps the job output when unfinished chunks left files](#d4-haddclean--f-keeps-the-job-output-when-unfinished-chunks-left-files)
   - [D5. Verbose log tag of `getsamples`](#d5-verbose-log-tag-of-getsamples)
   - [D6. Order of the `>>> preparejobs` line at `-v`](#d6-order-of-the--preparejobs-line-at--v)
6. [Notes that are not regressions](#6-notes-that-are-not-regressions)
7. [Suggested follow-ups](#7-suggested-follow-ups)

---

## 1. Summary

The jobs and workers do **not** behave exactly as before, but every difference is intended or follows from an
intended change:

- **Workers:** the worker code is unchanged apart from import paths and comments. The only behavior change is
  that a worker no longer writes `config/config.json` (BUGS P18, documented).
- **Submit / resubmit / run:** same line by line, apart from the bug fixes P01-P12 and P20-P22 in
  [BUGS.md](../../PicoProducer/docs/BUGS.md). Four consequences of those fixes are not spelled out there
  (D1-D3, and D6 which is cosmetic).
- **Status / hadd / haddclean / clean:** same line by line, apart from P04, P07, P19, P21, P22 and P23. One
  consequence of P19 is not spelled out (D4).
- **Physics output:** no difference in the tuples a worker writes for the same command line.

| ID | Difference | Caused by | Severity | Who notices |
|---|---|---|---|---|
| [D1](#d1-resubmit-no-longer-picks-up-changed-channel-options) | Resubmit reuses the first submission's module options; changed channel options in `config.json` are not picked up | P09 fix | real, rare | users who edit a channel between submit and resubmit |
| [D2](#d2-resubmit---split-can-switch-to-splitting-by-events) | `resubmit --split` uses `maxevtsperjob` from the config and may split by events | P06 fix | real, rare | users with `maxevtsperjob > 0` in `config.json` |
| [D3](#d3-resubmit-warns-about-a-missing-output-directory-instead-of-creating-it) | Resubmit warns "Could not find storage directory" instead of creating an empty one | P22 fix | harmless | users whose output directory is gone |
| [D4](#d4-haddclean--f-keeps-the-job-output-when-unfinished-chunks-left-files) | `haddclean -f` / `hadd -r -f` keeps the job output when unfinished chunks left files | P19 fix | real, safer | users who force-merge incomplete samples |
| [D5](#d5-verbose-log-tag-of-getsamples) | `-v` log tag reads `datasets.catalog.getsamples` | file move | cosmetic | log readers |
| [D6](#d6-order-of-the--preparejobs-line-at--v) | `>>> preparejobs` is printed before the batch system is loaded | restructuring | cosmetic | only with `-v` and an unknown batch system |

---

## 2. Scope and method

| Area | Before (`2580f35`) | After (HEAD) |
|---|---|---|
| Submit, resubmit | `pico/job.py` (`main_submit`, `preparejobs`, `checkchunks`) | `jobs/request.py`, `jobs/planner.py`, `jobs/pipeline.py`, `jobs/chunking.py`, `jobs/jobconfig.py`, `jobs/worker_command.py`, `api/producer.py`, `cli/jobs.py` |
| Local run | `pico/run.py` (`main_run`) | `jobs/local.py`, `jobs/worker_command.py`, `api/producer.py` |
| Status, hadd, clean | `pico/job.py` (`main_status`, `checkchunks`) | `jobs/status.py`, `jobs/merge.py`, `jobs/reporting.py`, `jobs/pipeline.py` (`iter_submitted`), `api/producer.py` |
| Command line | `scripts/pico.py`, `pico/common.py` | `scripts/pico.py`, `cli/parser.py`, `cli/__init__.py`, `cli/common.py` |
| Workers | `processors/picojob.py`, `skimjob.py`, `Bookkeeper.py`, `keep_and_drop_*.txt` | `workers/` (same files); `processors/` is a deprecated forwarder |
| Helpers the above call | `batch/*`, `storage/utils.py`, `storage/*`, `tools/config.py` | `batch/base.py`, `batch/factory.py`, `batch/htcondor.py`, `batch/slurm.py`, `batch/sge.py`, `batch/templates/`, `storage/factory.py`, `storage/*`, `datasets/catalog.py`, `settings/*` |

Method:

1. Workers, batch adapters, submit templates, storage adapters and the config reader were diffed directly
   (`git show 2580f35:<path> | diff --strip-trailing-cr -w - <new path>`); line endings and whitespace were ignored.
2. The job code was split into many modules, so it was compared function by function: each statement of the
   old `preparejobs`, `main_submit`, `checkchunks`, `main_status` and `main_run` was traced to its new location.
3. Each difference was checked against [BUGS.md](../../PicoProducer/docs/BUGS.md) and the
   [change log](Refactor-2025.md). Differences listed there are only summarized in
   [section 4](#4-documented-changes-for-reference); the others are explained in [section 5](#5-undocumented-differences).

---

## 3. What is unchanged

### Workers

| File | Difference |
|---|---|
| `workers/picojob.py` | imports only: `processors` → `workers`, `tools.config.getconfig` → `settings.getconfig`, `storage.utils.getstorage` → `storage.factory.getstorage`. The description line (copied from skimjob) was corrected (W02). `from __future__` removed |
| `workers/skimjob.py` | imports only, as above. `presel.replace('\$','$')` became `presel.replace(r'\$','$')`: the same string value (S04) |
| `workers/Bookkeeper.py` | `from __future__` removed |
| `workers/keep_and_drop_*.txt` | byte-identical |
| `processors/dumpGen.py` | moved to `legacy/processors/` unchanged; nothing referenced it (W03) |

The functions the workers call are the same: `storage/factory.py` `getstorage` is the old
`storage/utils.py` `getstorage` with new import paths, and `storage/base.py` `StorageSystem.cp` is unchanged.
`basestring` became `str` (identical for every string a worker passes).

Old job lists that name `python/processors/picojob.py` or `skimjob.py` still run: the forwarders in
`processors/` run the `workers/` script as `__main__` with the same arguments, output and exit status, after one
deprecation line on stderr (changelog section 10, A5).

### Batch submission

- `batch/base.py`, `batch/htcondor.py`, `batch/slurm.py`: identical apart from S03 (the ABC metaclass), raw
  strings in the job-ID regular expressions (same patterns, S04) and the template path.
- Submit templates: moved to `batch/templates/`. The `.sub` files point to `python/batch/templates/submit_HTCondor.sh`;
  the shell and SLURM/SGE templates are byte-identical apart from one comment.
- `submit_HTCondor.sh` guesses `CMSSW_BASE` from the worker path in the task line as `dirname(SCRIPT)/../../../../..`.
  `python/workers/picojob.py` is at the same depth as `python/processors/picojob.py`, so the guess is unchanged.
- The keyword arguments passed to the batch system (HTCondor `initialdir`/`mylogfile`, SLURM `log`/`array`) and
  the rule that the job config is written only when a job ID is returned are the same.

### Submit and resubmit

Unchanged, statement for statement:

- the sample loop and its order, `--testrun` limits, the existing-job-config checks (including the `--force`
  warning and "configs for resubmission already exist");
- the order in which `jobdir`, `config/`, `log/` and the output directory are created;
- `nfilesperjob` precedence (user > sample > config), `--split` division, and on resubmit the reuse of the
  previous try's `maxevts`/`nfilesperjob` when the user gives none;
- `chunkify` and `chunkify_by_evts` (now `jobs/chunking.py`; only the progress bar factory differs), chunk
  numbering that skips chunks kept from earlier tries, and the file tag rules;
- the flag order of each job-list line (including the `--testrun` override of `-m`);
- the keys, key order and values of the job config JSON (the `nfilesperjob` reset to 1 is recorded the same way);
- the submit confirmation prompt, including `q`/`exit` and `f`/`all`;
- the resubmit status classification and `nevents` on resubmit (DAS with `-D`, otherwise the previous job config).

### Local run

Sample selection per filter, deduplication, `nsamples`/`nfiles`, the file tag and the flag order of the
"Executing:" line are unchanged.

### Status, hadd, haddclean, clean

- Chunk classification (pending, failed, success, missing) in skim and analysis mode: regular expressions,
  glob patterns, pending matching, the overcounting checks, the `firstevt`/`maxevts` check, expected-event sums.
- Printed output at every verbosity: the loading bar, the SUCCESS/PEND/FAIL/MISS lines with colors and ratios,
  the `--log` lookup, the sample headers and empty lines (also when a sample is refused).
- The hadd gate (`status.mergeable or force` equals the old `(resubfiles or npend) and not force`), the
  `storedir`/`outfile`/`infiles`/`cfgfiles`/`logfiles` patterns, `getstorage(storedir,ensure=True,haddcmd=...)`,
  the `storage.hadd(...)` call and the refusal warning.
- The `rm -v` rewriting at `-v` and the `-v 2` prints of `cfgfiles`/`rmfileset`.

### Configuration

`settings/store.py` `getconfig` is the old `tools/config.py` `getconfig` plus the `write` switch (P18).
`pico.py` loads it once with `write=True` (`cli/common.py:9`) before any other module calls it, so `pico.py`
still creates and repairs `config/config.json` exactly as before. `scripts/pico.py:21` changes to `PicoProducer/`
as the old `pico/common.py` did at import time, so relative paths (templates, workers, samples) resolve the same.

---

## 4. Documented changes (for reference)

These are intended and explained in [BUGS.md](../../PicoProducer/docs/BUGS.md) or the
[change log](Refactor-2025.md). Listed only so this audit is complete.

| Path | Change | Reference |
|---|---|---|
| submit | `IOError` handler prints `str(err)` instead of crashing | P01 |
| submit `--prompt` | no crash on an existing job config; `y`/`f` submit and `n` skips (was inverted) | P02, P20 |
| submit | `.json.gz` job configs can be written | P03 |
| submit, status | `--checkqueue 1` queries the queue once (did not query at all) | P04 |
| submit | "Did not find any samples" is printed when nothing matches | P05 |
| submit | a sample's `maxevts>0` and the config's `maxevtsperjob` are used (condition was inverted) | P06 |
| status | `checkexpevts = False` is an assignment (no practical output change) | P07 |
| submit, run | module options: channel < sample < user (channel used to win) | P08 |
| resubmit | options of the previous try are not merged again (no duplicates) | P09 |
| run | `-m -1` is no longer passed | P10 |
| run | a failing worker is reported (`subprocess.call` instead of `os.system`) | P11 |
| submit, run | callers pass `--opts` (was `--opt`, accepted only by prefix matching) | P12 |
| workers, scripts | reading the config no longer creates or rewrites `config/config.json` | P18 |
| haddclean, `hadd -r` | cleanup only after the merged file is readable and holds the expected events | P19 |
| status | `--checkexpevts` is passed, so analysis channels can print "expected Y" warnings | P21 |
| status | the output directory is no longer created | P22 |
| haddclean, clean | only this sample's files are removed when other tags share the job directory (was: whole directory) | P23 |
| job lists | name `python/workers/<worker>.py`; old lists run through the forwarder | changelog 10, A3/A5 |
| batch | templates in `batch/templates/`; custom batch systems must be added to `SYSTEMS` in `batch/factory.py` (a file `batch/<Name>.py` is no longer found automatically) | changelog 7, lines 391-392, 417 |
| `-v` output | `chopts`/`useropts` instead of `extrachopts` | changelog 9 |
| storage, batch | site adapters fixed (SGE, EOS `rm`, PSI, GridKA, `isglob`, `cd`) | S01-S09 |

---

## 5. Undocumented differences

Each entry below follows from a documented change, but the consequence described here is not written down
in BUGS.md or the change log.

### D1. Resubmit no longer picks up changed channel options

**Caused by:** P09 (fix of duplicated options on resubmit).
**Severity:** real, rare. **Physics impact:** yes, if it happens (the module runs with the old options).

**Where.**

| | Code |
|---|---|
| Before | `pico/job.py:119-121` (in `preparejobs`, used by both submit and resubmit) |
| After | `jobs/planner.py:54-57` (`sample_layout`), `jobs/worker_command.py:84-88` (`resubmit_options`) |

Before, on submit and on resubmit alike:

```python
extraopts_ = extrachopts[:]                        # current channel options + current -E options
if sample.extraopts:
  extraopts_ = sample.extraopts + extraopts_       # on resubmit: the previous try's (merged) options
```

After:

```python
if resubmit:
  extraopts = resubmit_options(sample.extraopts,worker)   # previous try's options + new -E options only
else:
  extraopts = module_options(worker,sample.extraopts)     # channel < sample < user
```

`resubmit_options` returns the previous try's list unchanged, then appends the user's `-E` options that are not
already in it. The channel options from the **current** `config.json` are not looked at.

**Scenario.**

1. `config.json`: `"mutau": "ModuleMuTau tes=1.0"`. Submit: the job list has `--opts 'tes=1.0'`.
2. Some chunks fail. The user edits the channel to `"ModuleMuTau tes=1.02"` and runs `pico.py resubmit -c mutau`.
3. **Before:** the resubmitted chunks got `--opts 'tes=1.0' 'tes=1.02'`; the worker applies options in order, so
   `tes=1.02` won. (A side effect of the duplication bug.)
4. **After:** the resubmitted chunks get `--opts 'tes=1.0'`. The edit is ignored.

**Why.** The fix treats the job config as the record of what the production was run with, so that every try of
one production uses the same options. Before, the channel options were appended on every try: that caused the
duplicates (P09), and it also made a mid-production config change leak into later tries. The new behavior is
the consistent one (one production, one set of options), but it is a change for anyone who relied on the old
leak.

**Also affected:** a user `-E` option that is already in the previous list is not appended again, so
`resubmit -E tes=1.0` on a list that contains `'tes=1.0'` is a no-op (before, it was appended again).

**Productions submitted before the fix.** Their job configs store the old order (channel last) and any
duplicates. A resubmit keeps that list as it is, so the channel still wins for them and their behavior does not
change.

**How to get the old effect.** Pass the new value as a user option: `pico.py resubmit -c mutau -E tes=1.02`.
It is appended after the previous options, so it wins. Or start a new production (new tag) after changing the
channel.

### D2. `resubmit --split` can switch to splitting by events

**Caused by:** P06 (inverted per-sample `maxevts` condition).
**Severity:** real, rare. **Physics impact:** none (same events, different chunking); job count and job length change.

**Where.**

| | Code |
|---|---|
| Before | `pico/job.py:123-129` |
| After | `jobs/planner.py:58-64` |

Both versions:

```python
maxevts_ = <user -m> if given else <sample value> ... else <config.maxevtsperjob>
if split_nfpj>1:                                   # --split
  nfilesperjob_ = int(max(1,nfilesperjob_/float(split_nfpj)))
elif resubmit and (maxevts==None or maxevts<=0):   # reuse the previous try's maxevts / nfilesperjob
  maxevts_ = sample.jobcfg.get('maxevts',maxevts_)
  ...
```

The only change is the middle term: before, `sample.maxevts if sample.maxevts<=0 else CONFIG.maxevtsperjob`; after,
`sample.maxevts if sample.maxevts>0 else config.maxevtsperjob`.

On resubmit the sample is rebuilt from the job config (`Sample.loadjson`), which does not restore `maxevts`, so
`sample.maxevts` is `-1`. Without `--split` the `elif` branch overwrites `maxevts_` with the previous try's value,
so the term does not matter. With `--split`, the `elif` is skipped, and the term decides:

| | `sample.maxevts = -1`, `config.maxevtsperjob = 200000`, `resubmit --split` |
|---|---|
| Before | `maxevts_ = -1` → chunks by files (`nfilesperjob` halved) |
| After | `maxevts_ = 200000` → chunks by events (`chunkify_by_evts`), and `nfilesperjob` halved |

**Scenario.** A user sets `pico.py set maxevtsperjob 200000`, submits a production with `-m -1` (by files),
and later runs `pico.py resubmit --split`. Before: the failed files are regrouped with half as many files per job.
After: the failed files are cut into 200000-event jobs. Also: on fresh submissions, the same user now gets
event-based splitting, which is the P06 fix itself.

**Why.** P06 restored the documented precedence (user > sample > config). The old code ignored
`maxevtsperjob` unless a sample set a positive value, so on resubmit with `--split` it always fell back to files.
With the default `maxevtsperjob = -1` nothing changes.

**How to get the old effect.** `pico.py resubmit --split -m -1`.

### D3. Resubmit warns about a missing output directory instead of creating it

**Caused by:** P22 (status check created the output directory).
**Severity:** harmless. **Physics impact:** none.

**Where.**

| | Code |
|---|---|
| Before | `pico/job.py:378` `getstorage(outdir,ensure=True)` in `checkchunks` |
| After | `jobs/status.py:62` `getstorage(outdir)` in `check_sample` |

`check_sample` is used by `status`, `hadd`, `clean` **and** `resubmit`. BUGS.md describes P22 for `status` only.

**Scenario.** A production's output directory (recorded in its job config) was deleted or is not mounted, then
`pico.py resubmit` runs. Before: the check silently created an empty directory, found no output, and resubmitted
every chunk. After: the storage layer prints "Could not find storage directory …", finds no output, and resubmits
every chunk. The resubmission itself then creates the output directory (from the current config) as before.

**Why.** Checking the status should not write to storage; `resubmit` shares that check.

### D4. `haddclean -f` keeps the job output when unfinished chunks left files

**Caused by:** P19 (cleanup was gated only on the exit code of hadd).
**Severity:** real, but safer than before. **Physics impact:** none on the merged file.

**Where.**

| | Code |
|---|---|
| Before | `pico/job.py:965-975`: gate, `storage.hadd(infiles,...)`, then cleanup ("TODO: check if hadd was succesful") |
| After | `jobs/merge.py:77-93` (`merge_sample`), `jobs/merge.py:143-152` (`validated`) |

The merge input is a glob, `<outdir>/*<postfix>_[0-9]*.root` (`jobs/merge.py:132`, before `pico/job.py:950`), so
it takes every output file on disk. The new check compares the merged file's events with
`status.nprocevents`, which only sums the chunks the status check counted as **good** (`jobs/status.py:327`,
`:443`); pending chunks are skipped, failed and corrupt ones are not added.

```python
if status.checkevts and nproc>0 and abs(nevents-nproc)>1e-6*nproc:
  return False, "the merged file has %s events, the job output %s"%(nevents,nproc)
```

**Scenario.**

1. A sample has 10 chunks: 8 good, 2 still pending in the queue but with their output files already on disk
   (or failed chunks that left a readable file).
2. The user runs `pico.py haddclean -f` (or `hadd -r -f`).
3. hadd merges all 10 files.
4. **Before:** the job directory and the job output were deleted right after hadd, including the files of the
   pending jobs, which were still running.
5. **After:** the merged file has more events than the 8 good chunks; the job output is kept with
   "Not removing the job output of '<sample>': the merged file has X events, the job output Y". The merged file
   is still written.

Without `-f` the gate refuses incomplete samples first, so nothing changes there. The check is skipped for
dry runs (`-d`), for plain `hadd` and when event counting is off (`checkevts=False`). It costs one extra ROOT open
of the merged file.

**Why.** P19 added the validation so that a corrupt or incomplete merge never leads to the deletion of the job
output. With `-f` the user accepts a merge of an incomplete sample, but the check cannot tell "incomplete on
purpose" from "hadd went wrong", so it keeps the files. This is the conservative choice.

**How to clean anyway.** Run `pico.py clean -f` after the merge; `clean` does not merge and does not validate.

### D5. Verbose log tag of `getsamples`

**Caused by:** moving `getsamples` from `storage/utils.py` to `datasets/catalog.py` (Part 3A).
**Severity:** cosmetic.

| | Line printed at `-v` (and `-v 3`) |
|---|---|
| Before (`storage/utils.py:87-88,96`) | `storage.utils.getsamples: sampfile=...` |
| After (`datasets/catalog.py:41-42`) | `datasets.catalog.getsamples: sampfile=...` |

The tag follows the new module name. Inconsistency left behind: `storage/factory.py:51` still prints
`storage.utils.getstorage(...)` at `-v 2`, the old module name.

### D6. Order of the `>>> preparejobs` line at `-v`

**Caused by:** restructuring of `main_submit` (Part 4A, 5A).
**Severity:** cosmetic.

| | Order |
|---|---|
| Before | `main_submit` loaded the batch system (`pico/job.py:780` `getbatch`), then called `preparejobs`, which printed `>>> preparejobs` (`pico/job.py:26`) |
| After | `cli/jobs.py:33-35` prints `>>> preparejobs` before `PicoProducer.submit` loads the batch system |

Visible only at `-v` or higher, and only when loading the batch system fails (unknown name): the line now
appears before the `AssertionError`.

---

## 6. Notes that are not regressions

- **P07 edge case.** The fix "has no output change" in practice. In theory, `--checkexpevts` given explicitly,
  an empty `filenevts` and event-split chunks used to print spurious "expected" warnings, which are now gone. This
  is practically unreachable: event splitting fills `filenevts`, and it is stored in the job config.
- **`check_sample` no longer mutates the sample.** The old `checkchunks` wrote `sample.jobcfg['nevents']` and
  popped chunks from `chunkdict` in place; resubmit relied on that. The new code works on a copy and resubmit reads
  `status.nexpected` and `status.chunkdict` (`jobs/pipeline.py:167-169`). Same values (changelog 9, line 680).
- **New API only: two configurations can disagree.** `PicoProducer.from_config(<other JSON or dict>)` uses that
  configuration for channels, `outdir` and `jobdir`, but `getsamples` (`datasets/catalog.py:33`) always reads the
  global `config/config.json` to map eras to sample catalogs. If the two configurations have different `eras`, the
  API reads samples from the global one. `pico.py` is not affected (one configuration). This did not exist before,
  since there was no API.
- **Already-submitted jobs.** Jobs submitted before the update keep running: HTCondor copies the executable at
  submission, and their job lists naming `python/processors/` run through the forwarder.

---

## 7. Suggested follow-ups

None of these is needed for correctness; they make the behavior explicit.

1. Add D1-D4 to the "Output impact" column of P09, P06, P22 and P19 in [BUGS.md](../../PicoProducer/docs/BUGS.md).
2. D1: decide whether resubmit should warn when the current channel options differ from the job config's.
3. D4: consider a clearer message when `-f` was given, e.g. "merged with -f: the job output includes unfinished
   chunks; use `pico.py clean -f` to remove it".
4. D5: change the `storage.utils.getstorage` tag in `storage/factory.py:51` to `storage.factory.getstorage`
   (a BBB check is needed only if a case runs with `-v 2`).
5. API note: let `getsamples` take the configuration as an argument, so `PicoProducer.from_config` uses its own `eras`.
