# PicoProducer inputs and outputs

What each production step reads and writes. Paths in `config/config.json` may contain `$ERA`, `$CHANNEL`, `$TAG`,
`$SAMPLE`, `$GROUP`, `$DAS`/`$PATH`; relative paths are relative to `PicoProducer/`. The defaults are shown.

## Configuration and catalogs

| File | Read by | Written by |
|---|---|---|
| `config/config.json` (+ `config.json.bkp`) | everything (`settings.getconfig` in `pico.py`, `settings.loadconfig` in the API; workers with `-c`) | `pico.py` (creates/repairs it), `pico.py set/rm/channel/era` |
| `samples/<catalog>.py` (era → catalog in `eras`) | sample selection (`datasets.getsamples`) | users |
| `samples/files/$ERA/$SAMPLE.txt` (`filelistdir`) | sample file lists, if present | `pico.py write`, `pico.py get files -w` |

## Per step

| Step (`pico.py` / API) | Reads | Writes |
|---|---|---|
| `run` / `run_local` | config, catalog, file lists or storage/DAS listing | worker output in `-o` (default `output/`) |
| `submit --dry` / `plan` | config, catalog, file lists or storage/DAS listing; event counts if split by events | nothing (`plan`); job directories and job list (`submit --dry`) |
| `submit` / `submit` | as `plan` | job directory `output/$ERA/$CHANNEL/$SAMPLE/` (`jobdir`) with `config/jobarglist_<channel><tag>_try<N>.txt` (job list, one worker command per chunk) and `config/jobconfig_<channel><tag>_try<N>.json` (job config, after submission), `log/`; the output directory (`outdir`, or `nanodir` for skims); batch jobs |
| batch job (worker) | job list line: input NanoAOD | `outdir/pico_<channel><tag>_<chunk>.root` (analysis) or `nanodir/<input>_skim[_<part>].root` (skims); `log/<jobname>.<jobid>.<task>.log` |
| `status` / `status` | job configs (last try per sample), batch queue, job output (validated: `tree` + `cutflow`, or NanoAOD `Events`), logs | nothing |
| `resubmit` / `resubmit` | as `status`, plus the job config | a new try: job list and job config `_try<N+1>` in the same job directory; batch jobs |
| `hadd` / `merge` | as `status` | `picodir` (`$PICODIR/$ERA/$GROUP/`): `<sample>_<channel><tag>.root` |
| `haddclean`, `hadd -r` / `merge(clean=True)` | as `hadd`, plus the merged tuple (validated before cleanup) | as `hadd`; removes the job directory and the job output directory, or only the sample's job outputs, job configs and logs if other jobs share the directory |
| `clean` / `clean` | as `status` | removes job files and job output as above |

## Job config (JSON)

One file per (re)submission try of a sample: `jobdir/config/jobconfig_<channel><tag>_try<N>.json`. The keys, in file
order (`jobs.jobconfig.JOBCFG_KEYS`): `time`, `group`, `paths`, `name`, `nevents`, `dtype`, `channel`, `module`,
`extraopts`, `jobname`, `jobtag`, `tag`, `postfix`, `try`, `queue`, `jobids`, `prefetch`, `outdir`, `jobdir`,
`cfgdir`, `logdir`, `cfgname`, `joblist`, `maxevts`, `nfiles`, `files`, `nfilesperjob`, `nchunks`, `chunks`,
`chunkdict` (chunk → input files, including the good chunks of earlier tries), `filenevts`.

The latest try per sample is found with the glob `jobdir/config/jobconfig_$CHANNEL$TAG_try[0-9]*.json`
(`jobs.planner.cfg_globs`). Paths inside are relative to `PicoProducer/` when the configuration's are.

## Merged tuple

`<picodir>/<sample>_<channel><tag>.root`: the `hadd` of the job outputs, with the analysis `tree` and the `cutflow`
histogram (bin 1 = processed events, bin 17 = sum of weights, the normalisation). The API returns it as a
`TupleArtifact` (with `sumw`, read from bin 17 after `hadd`, and `kind: tuples`; CL §36). Format and record:
[Docs/Develop/contracts/pico-tuples.md](../../Develop/contracts/pico-tuples.md).
