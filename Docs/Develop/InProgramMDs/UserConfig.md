# User config (Git Never Changes This)

- A line that starts with `#` is not set, TauFW uses default.
- If a recipe sets the same thing, the recipe wins.

## taufw_user

> [!CAUTION]
> `version`: set by TauFW. Don't change it.

> [!WARNING]
> `reviewed`: set it to `true` once you've checked the file.

- `notifications`: a terminal bell when a recipe or a test run finishes, or something fails. `false` turns it off.
- `open_menu_on_start`: `false` means `source taufw.sh` sets up TauFW without opening this menu.

## runs

- `run_root`: the folder for your runs. Use a full path, without `~` or `$`. Your AFS home is too small; your AFS
  work area or EOS is better. Not set: `taufw_runs/` in the folder you start from.

## production

### batch

Which batch system your jobs go to. Not set: TauFW guesses it from the machine name (`HTCondor` on lxplus).

- `HTCondor`: lxplus and most HTCondor sites.
- `HTCondor_CMG`, `HTCondor_DESY`, `HTCondor_KIT`, `HTCondor_NAF`: HTCondor with the submit file of that site.
- `SLURM`: e.g. PSI T3. `SLURM_UCL`: UCLouvain.
- `SGE`: Sun Grid Engine sites.

### queue

Where the jobs run. Each system calls it something else.

HTCondor (lxplus) job flavours, by the longest time a job may run:

- `espresso`: 20 minutes
- `microcentury`: 1 hour
- `longlunch`: 2 hours
- `workday`: 8 hours (used when not set)
- `tomorrow`: 1 day
- `testmatch`: 3 days
- `nextweek`: 1 week

A shorter flavour usually starts sooner.

> [!WARNING]
> The submit file also sets `+MaxRuntime = 20000` (about 5.5 hours). On lxplus that limit wins over the flavour,
> so a job longer than that needs `+MaxRuntime` in `batchopts` too (below).

SLURM: the partition, e.g. `short`, `standard`, `long` (list them with `sinfo`). Not set: `standard`.

SGE: the queue, e.g. `short.q`, `all.q`, `long.q` (list them with `qconf -sql`).

### batchopts

Extra options, added as they are to the submit command (`condor_submit`, `sbatch` or `qsub`). Not set: none.

HTCondor, each option as `-append key=value`:

- More memory (MB): `-append request_memory=4000`
- More cores per job: `-append request_cpus=2`
- A longer time limit (seconds): `-append +MaxRuntime=86400`
- Several at once: `-append request_memory=4000 -append +MaxRuntime=36000`

SLURM:

- More memory: `--mem=8000M` (the default is 5500M)
- A longer time limit: `--time=10:00:00` (the default is 05:30:00)
- An account: `--account=myaccount`

SGE:

- More memory: `-l h_vmem=4G`

Don't put quotes in `batchopts`: they reach the shell as they are.

### Folders

- `outdir`: where jobs write their output before the merge.
- `nanodir`: where skim jobs write their output.
- `tmpskimdir`: a temporary folder for skim jobs, before the file is copied to `nanodir`.

In `outdir` and `nanodir`, `$ERA`, `$CHANNEL`, `$SAMPLE` and `$DAS` are filled in for each sample. EOS
(`/eos/user/...`) is a good place: it's big, and the jobs can write to it.

> [!CAUTION]
> Don't change `outdir` while a run is still producing tuples.

### Checking and merging

- `ncores`: how many files TauFW checks at once when it counts events. This is not the number of cores of a job.
  Not set: 4.
- `hadd.cmd`: another command to merge the files, e.g. `python3 haddnano.py`. Not set: `hadd -ff`.
- `hadd.maxopenfiles`: how many files the merge opens at once. Lower it if the merge fails because too many
  files are open. Not set: 500.

## Your own settings

You can add your own sections, e.g. `mystudy:`. TauFW keeps them. Read them in a script with
`UserConfig.load().get("mystudy.plotdir")`.
