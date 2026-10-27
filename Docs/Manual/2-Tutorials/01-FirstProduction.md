# Tutorial 1: Your first production

**You'll learn:** how to make your own copy of an example analysis, test it on a few events, send it to the batch
system, and pick it up again later to collect your pico tuples.
**You need:** to have gone through [Your first session](../1-GettingStarted/FirstSession.md), and a valid grid proxy.

In this tutorial you'll make mutau pico tuples for the 2022_postEE Drell-Yan and ttbar samples. That's 9 samples and
340 batch jobs. It's a real production, just a small one.

## 1. Make your own copy

Don't edit the examples in `Analyses/` directly. Other people use them too, and you'll want a clean version to look
back at. Make your own bundle from the example instead:

```bash
python3 taufw.py init my_first_production --from Analyses/example_mutau_short
```

<!-- TODO: real output of the init command -->

This creates `Analyses/my_first_production/` with a copy of the recipe. The recipe's `name` is now
`my_first_production`, the same as the folder. The long comments from the example aren't copied, so the new
`recipe.yml` is short. Open it and have a look:

<!-- TODO: real content of Analyses/my_first_production/recipe.yml after init -->

## 2. Tell TauFW where to put the runs

Remember the `run_root` warning from your first session? Let's fix it now. Production puts its merged tuples inside
the run folder, and that can easily be tens of GB. Your lxplus home folder only holds a few GB. Your work area
(`/afs/cern.ch/work/<first letter>/<username>/`) has a lot more space, so use that.

Make a folder for your runs:

```bash
mkdir -p /afs/cern.ch/work/y/ydinckur/taufw_runs
```

(Use your own username and its first letter, of course.)

Then add a `run_root` line near the top of `Analyses/my_first_production/recipe.yml`, just under `name`:

```yaml
name: my_first_production
run_root: /afs/cern.ch/work/y/ydinckur/taufw_runs
```

Write the full path. TauFW doesn't expand `~` or `$USER` inside a recipe, on purpose, so a recipe means the same
thing no matter who runs it.

Now check the recipe again. The warning should be gone:

```bash
python3 taufw.py check Analyses/my_first_production
```

<!-- TODO: real output of check, with run_root set -->

## 3. Test it on a few events first

340 jobs is a lot to send off without trying first. `plan --local` runs the production code right here on your lxplus
machine, on one file and just a few events. If something's broken, you find out in seconds, not after hours of
failing batch jobs.

```console
$ python3 taufw.py plan Analyses/my_first_production --local -m 50
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

## 4. Look at the plan

Run the normal plan once more, now with your own recipe:

```bash
python3 taufw.py plan Analyses/my_first_production
```

You saw this table in your first session. The only difference is the `Run root` line, which should now show your work
area. Check it before you go on.

<!-- TODO: real output, just the Bundle/Run root/PicoProducer config lines -->

## 5. Start the run

This is the real thing:

```bash
python3 taufw.py start Analyses/my_first_production
```

<!-- TODO: real output of start -->

Here's what happened:

1. TauFW made a new run folder: `<run_root>/my_first_production_<date>-<time>/`. The exact path is in the output.
   **Copy it somewhere.** You'll need it for every command from now on.
2. It copied your bundle into the run folder. From now on the run only reads that copy. If you edit your recipe
   later, this run won't change. That's on purpose, so a run always matches the recipe it was started with.
3. It submitted the 340 jobs to HTCondor and stopped.

That last point surprises people. `start` doesn't wait for the jobs to finish. They take hours, and there's no
reason to keep your terminal busy that long. You can log out now if you want.

## 6. Check on it

Whenever you're curious, ask for the status. Use your own run folder here:

```bash
python3 taufw.py status /afs/cern.ch/work/y/ydinckur/taufw_runs/my_first_production_20261027-103000
```

<!-- TODO: real output of status while jobs are running -->

`status` only looks. It never submits anything and never changes the run, so you can run it as often as you like.

You can also use **Inspect run status** in the menu. It finds your runs for you, so you don't have to type the path.

## 7. Push it forward

Once some time has passed, tell TauFW to continue:

```bash
python3 taufw.py advance /afs/cern.ch/work/y/ydinckur/taufw_runs/my_first_production_20261027-103000
```

`advance` does whatever can be done right now:

- If jobs are still running, it says so and stops. Come back later.
- If some jobs failed, it resubmits just those. The recipe says `max_tries: 3`, so each job gets three chances in
  total before TauFW gives up on the whole stage.
- If all jobs of all samples are done, it merges them: the many small outputs of each sample are added into one pico
  tuple per sample. Then the stage is `DONE`.

<!-- TODO: real output of advance, ideally one with a resubmission and one with the merge -->

If you don't want to keep coming back by hand, let it wait:

```bash
python3 taufw.py advance <run folder> --wait --poll 900
```

This checks every 900 seconds (15 minutes) and keeps going until the run is done or something fails. It only works
while your terminal stays open, so use it inside `screen` or `tmux` if you plan to log out.

In the menu, **Continue an existing run** does the same thing. You can pick one `advance` or the repeated checking.

## 8. Your pico tuples

When the run is `DONE`, your tuples are in the run folder, sorted by era and sample group:

```text
my_first_production_20261027-103000/
  run.json                        what TauFW remembers about the run
  run.log                         everything it told you, in one file
  bundle/                         the copy of your bundle the run used
  stages/production/2022_postEE/
    DY/                           the Drell-Yan tuples
    TT/                           the ttbar tuples
```

<!-- TODO: real `ls -R stages/production` of a finished run, to confirm the group folder names -->

There's one file per sample. Each one has the analysis `tree` and a `cutflow` histogram, which counts events through
the selection and stores the sum of weights for normalisation.

Here's what `status` says about a finished run:

<!-- TODO: real output of status on a DONE run -->

## A note about disk space

Production's job files (the job lists, the logs and the unmerged outputs of each job) don't live in the run folder.
They go to `PicoProducer/output/`. If you want them gone automatically once the merge has worked, set this in the
production stage of your recipe:

```yaml
    merge:
      clean: true
```

It's `false` in the example, so you can look at the job logs if something goes wrong. For your first production,
leaving it off is a good idea.

## If something goes wrong

- **A job keeps failing.** Look at its log under `PicoProducer/output/2022_postEE/mutau/<sample>/log/`. The most
  common cause is an expired grid proxy.
- **The stage is `FAILED`.** For the production stage, the run is final, and editing the recipe won't revive it. Fix
  the cause, then start a new run.

  The later stages you'll meet in the next tutorials (histograms, plots, the fit, Python steps) are different: when
  one of them fails, you can run just that stage again. Fix the cause first. If the fix is a file of your analysis,
  put it into the run's own copy, `<run folder>/bundle/` (the run never reads your analysis folder again). Then
  run:

  ```bash
  python3 taufw.py retry <run folder>
  ```

  In the menu, Continue on that run offers **Retry**. The stages that already finished don't run again. The failed
  attempt's logs and files move to `logs/<stage>/attempt1/`, so you can still read them. If you changed the
  `bundle/` copy, TauFW warns once and writes that down in `run.json`, so anyone reading the run later can see it.
- **You pressed Ctrl+C.** That's fine. Your batch jobs keep running. Just run `advance` on the same run folder again.

More in Troubleshooting *(coming soon)*.

## What's next

You have pico tuples. In Tutorial 2 *(coming soon)* you'll turn them into histograms and control plots.
