# Using FW with commands

Run these commands from your TauFW directory after [setting up your environment](../1-GettingStarted/FirstSession.md#getting-in).
Commands that take a recipe accept an [analysis bundle](Glossary.md) directory or a recipe file.
Commands that continue or inspect a run take the run folder containing `run.json`.

Tab completes the commands, their options, recipe files and folders. To see the available commands and the
options for one command:

```bash
taufw --help
taufw start --help
```

## Creating an analysis bundle

Copy the short mutau example into your own analysis:

```bash
taufw init my_first_production --from Analyses/Examples/mutau_short
```

This creates `Analyses/my_first_production/` and sets the recipe's name to `my_first_production`.
The example's long comments aren't copied. Edit your copy before starting production.

## Checking a recipe

`check` reads a recipe and lists everything wrong with it, all at once. Try it on the broken example:

```console
$ taufw check Analyses/Examples/broken
>>> Warning: run_root: not set: the runs go to taufw_runs/ in the directory taufw.py is started from, ...
>>> Warning: Recipe example_broken: 4 problem(s)
>>> Warning:   stages[0] (production): unknown option 'samplez' (known: batchopts, channels, checkdas, ...)
>>> Warning:   stages[2] (python).file: steps/missing_check.py is not a file of the bundle (...), a Configs/ template or an absolute path: ...
>>> Warning:   stages[1] (controlhists).inputs.tuples: no stage 'prodution' in the recipe
>>> Warning:   pico.config: file not found: .../Analyses/Examples/broken/missing_pico.json
```

Each line tells you where the problem is and what's wrong. `stages[0]` is the first stage in the recipe, `stages[1]`
the second, and so on, counting from zero. Here there's a typo in an option name (`samplez`), a typo in a stage name
(`prodution`) and two files that don't exist.

The first line is a warning, not a problem. It says the recipe doesn't set `run_root`, the folder where runs are
created. Without it, runs go into `taufw_runs/` right inside your TauFW folder. That's fine for a quick try, but
production writes tens of GB and your lxplus home only holds a few GB. See [your first production](../2-Tutorials/01-FirstProduction.md#2-tell-taufw-where-to-put-the-runs) for choosing a run folder.

Get used to running `check` after every edit. It's instant and saves you from finding a typo three hours into a
run.

## Planning a recipe

`plan` goes one step further. It works out exactly what the recipe would do, without doing any of it. Try it on the
short example:

```console
$ taufw plan Analyses/Examples/mutau_short
>>> === [production] 2022_postEE, mutau ===
>>> DYto2L-4Jets_MLL-50
>>> /DYto2L-4Jets_MLL-50
...
>>> Bundle: /afs/cern.ch/user/y/ydinckur/CMSSW_14_1_0_pre4/src/TauFW/Analyses/Examples/mutau_short
>>> Run root: /afs/cern.ch/user/y/ydinckur/CMSSW_14_1_0_pre4/src/TauFW/taufw_runs (default: no run_root in the recipe)
>>> PicoProducer config: PicoProducer/config/config.json (default)
>>> === Stage production (production) ===
>>> mutau tuples of the DY and ttbar samples
>>> Inputs: none
>>> era          channel  sample                  files  chunks  try  conflict
>>> -----------  -------  ----------------------  -----  ------  ---  --------
>>> 2022_postEE  mutau    DYto2L-4Jets_MLL-50     54     54      1
>>> 2022_postEE  mutau    DYto2L-4Jets_MLL-50_1J  14     14      1
>>> 2022_postEE  mutau    DYto2L-4Jets_MLL-50_2J  17     17      1
>>> 2022_postEE  mutau    DYto2L-4Jets_MLL-50_3J  12     12      1
>>> 2022_postEE  mutau    DYto2L-4Jets_MLL-50_4J  5      5       1
>>> 2022_postEE  mutau    DYto2TautoMuTauh_M-50   4      4       1
>>> 2022_postEE  mutau    TTTo2L2Nu               56     56      1
>>> 2022_postEE  mutau    TTto4Q                  35     35      1
>>> 2022_postEE  mutau    TTtoLNu2Q               143    143     1
>>> 9 sample(s), 340 job(s)
```

The first part is PicoProducer looking up the samples. The recipe asks for `"DY*"` and `"TT*"`, and these are the
nine samples in the 2022_postEE catalog whose names match.

After that comes the summary:

- **Bundle**, **Run root** and **PicoProducer config**: which files will be read and where the run would go.
- Then one block per stage. This recipe has only one, `production`.
- The table has one row per sample. `files` is the number of NanoAOD files and `chunks` is the number of batch jobs.
  Here each job gets one file, so they're the same. `try` is 1 because nothing has been submitted yet. `conflict` would
  say if a sample already has jobs from an earlier submission with the same name.
- At the bottom: 9 samples, 340 jobs in total.

That's the whole point of `plan`. Before you send 340 jobs to the batch system, you can see they're the right 340.

## Testing production locally

340 jobs is a lot to send off without trying first. `plan --local` runs the production code right here on your lxplus
machine, on one file and just a few events. If something's broken, you find out in seconds, not after hours of
failing batch jobs.

```console
$ taufw plan Analyses/my_first_production --local -m 50
>>> === [production] 2022_postEE, mutau ===
>>> DYto2L-4Jets_MLL-50
>>> Executing: python3 .../TauFW/PicoProducer/python/workers/picojob.py -y 2022_postEE -c mutau -M ModuleMuTauSimple -o output -d 'mc' -t '_mutau_2022_postEE_DYto2L-4Jets_MLL-50' -m 50 -i root://cms-xrd-global.cern.ch//eos/cms/store/group/phys_tau/irandreo/Run3_22_postEE_new/DYto2L-4Jets_MLL-50/nano_0.root --opts 'useT1=False' 'zpt=True'
--------------------------------------------------------------------------------
>>> era          = '2022_postEE'
>>> channel      = 'mutau'
>>> modname      = 'ModuleMuTauSimple'
>>> dtype        = 'mc'
>>> maxevts      = 50
>>> outfname     = 'output/pico_mutau_2022_postEE_DYto2L-4Jets_MLL-50.root'
...
--------------------------------------------------------------------------------
Pre-select 50 entries out of 50 (100.00%)
Processed 50 preselected entries from root://.../DYto2L-4Jets_MLL-50/nano_0.root (50 entries). Finally selected 0 entries
Total time 1.0 sec. to process 50 events. Rate = 49.3 Hz.
>>> picojob.py done after 3.1 seconds

>>> TTTo2L2Nu
>>> Executing: python3 .../workers/picojob.py -y 2022_postEE -c mutau -M ModuleMuTauSimple ... --opts 'useT1=False' 'toppt=True'
...
Processed 50 preselected entries from root://.../TTTo2L2Nu/nano_0.root (50 entries). Finally selected 1 entries
Total time 0.9 sec. to process 50 events. Rate = 52.8 Hz.
>>> picojob.py done after 3.1 seconds
```

`-m 50` means 50 events. Leave it out and you get 100.

A few things worth noticing here:

- It ran two samples, not nine. The local test takes the first sample for each pattern in `samples:`, so one for
  `"DY*"` and one for `"TT*"`.
- The block between the dashed lines shows exactly what the job was told: the era, the channel, the analysis module
  (`ModuleMuTauSimple`), MC or data, and where the output goes. If something looks wrong in your real jobs later,
  this is a good place to start looking.
- The `--opts` at the end are options picked per sample. Drell-Yan gets `zpt=True` (the Z pT reweighting) and ttbar
  gets `toppt=True` (the top pT reweighting). These come from the sample catalog. You didn't have to set them.
- "Finally selected 0 entries" for Drell-Yan isn't a bug. Out of 50 random Drell-Yan events, it's normal that none
  has a good muon and a good tau. What matters is that the job ran to the end without errors.

The test output is written to `PicoProducer/output/`. It isn't part of any run. You can open it in ROOT to see what a
pico tuple looks like inside:

```bash
root -l PicoProducer/output/pico_mutau_2022_postEE_TTTo2L2Nu.root
```

<!-- TODO: real ROOT session: .ls, and tree->Print() or tree->Show(0) -->

Once you're done looking, you can delete these test files. Nothing else uses them.

## Starting a run

After checking the recipe and reviewing its plan, start your analysis:

```bash
taufw start Analyses/my_first_production
```

This creates a new run folder under `run_root`, copies the bundle into it, and starts the pipeline.
Save the run folder path printed in the output. The run reads its own `bundle/` copy from then on;
changes in the original analysis folder don't affect it.

`start` waits for the batch jobs (it checks them every 600 seconds) and goes on to the end of the recipe.
Add `--no-wait` to return as soon as the run has to wait for jobs, or `--until <stage id>` (`--next`: only the
first stage) to stop after a stage: the run is then `PAUSED` until you advance it again.
You can override the configured run root for a new run with `--run-root` followed by a full directory path.
Choose a location with enough space for the merged tuples.

## Inspecting and continuing a run

Set `run_dir` to the run folder printed by `start`. Replace this example path with your own:

```bash
run_dir=/afs/cern.ch/work/y/ydinckur/taufw_runs/my_first_production_20261027-103000
taufw status "$run_dir"
taufw advance "$run_dir"
```

`status` reads the run and checks the jobs without changing anything. `advance` moves it forward:
it checks production jobs, resubmits failed chunks while attempts remain, and merges completed outputs.
It skips stages that are already `DONE` and can start the next stage in the same call.
While jobs are still running it checks them again every 600 seconds; with `--no-wait` it returns so you can come
back later. `--until <stage id>` and `--next` stop it after a stage, as for `start`.

To check every 900 seconds (15 minutes) instead:

```bash
taufw advance "$run_dir" --poll 900
```

This command needs to stay running. Use `screen` or `tmux` if you want it to keep checking after you log out.
Stopping `advance` doesn't cancel batch jobs that were already submitted. Run it again on the same folder
to continue. Running `start` again creates a separate run.

## Changing a run's recipe

A run keeps its own copy of the recipe in `"$run_dir"/bundle/recipe.yml`. To change a stage that has not run yet,
edit that file, not the one in `Analyses/`:

```bash
taufw start Analyses/Examples/cmsdas26_ztt --until plots
vim "$run_dir"/bundle/recipe.yml      # e.g. change an option of the next stage
taufw status "$run_dir"               # "bundle/recipe.yml was edited (...): the next advance takes it"
taufw advance "$run_dir" --next
```

The next `advance` checks the file like `taufw check` does, and refuses an edit of production or of the stages
before it, or a new type for a stage id. A stage that is already `DONE` keeps its output. Every version is kept in
`"$run_dir"/recipes/`.

## Running stages again

`rerun` runs a stage and every stage after it again, then goes on like `advance`:

```bash
taufw rerun "$run_dir" plots --dry-run   # what it would move and run; nothing changes
taufw rerun "$run_dir" plots             # plots and every stage after it
taufw rerun "$run_dir" plots --next      # only plots
```

What each of them made before moves to `logs/<stage>/attempt<N>/`; the stages before `plots` are kept.
Production and the stages before it cannot run again in the same run.

To run a failed stage again, read the failure message and `run.log`, fix the cause, then:

```bash
taufw rerun "$run_dir"
```

For production, this works when failed chunks have exhausted their allowed attempts.
It adds another `max_tries` attempts and resubmits only the failed chunks. Other production failures,
such as no matching samples or an invalid merged tuple, need a new run after the cause is fixed.

For a failed histogram, plot, fit, or Python stage, it runs that stage again and keeps the stages before it.
If the fix changes an analysis file, edit the run's own `bundle/` copy. The failed attempt's files and logs
move to `logs/<stage>/attempt1/` the first time. Changes to the bundle copy are recorded in `run.json`.

Repeating `advance` doesn't retry a stage marked `FAILED`. If a stage is still `NEW` because an environment
or input check failed, fix that problem and use `advance` again.

## Creating your user config

FastSetup normally creates your user config. To create it later, or check its location:

```bash
taufw userconfig
```

An existing file is kept unchanged. Here is the recorded output for a new file:

```console
$ taufw userconfig
>>> New user config: /afs/cern.ch/user/y/ydinckur/CMSSW_14_1_0_pre4/src/TauFW/Analyses/UserConfig.yaml
>>> Warning: User config /afs/cern.ch/user/y/ydinckur/CMSSW_14_1_0_pre4/src/TauFW/Analyses/UserConfig.yaml is not reviewed yet: check its values, then set reviewed: true
```

See [Your user config](../1-GettingStarted/UserConfig.md) for the settings and how to review them.

## Config templates and version

List the shared configuration templates and inspect the installed version:

```bash
taufw configs list
taufw version
```

For more options and details, see the [Framework documentation](../../../Framework/README.md#quick-start).
