# Tutorial 1: Your first production

**You'll learn:** how to make your own copy of an example analysis, test it on a few events, send it to the batch
system, and pick it up again later to collect your pico tuples.
**You need:** to have gone through [Your first session](../1-GettingStarted/FirstSession.md), and a valid grid proxy.

In this tutorial you'll make mutau pico tuples for the 2022_postEE Drell-Yan and ttbar samples. That's 9 samples and
340 batch jobs. It's a real production, just a small one.

## 1. Make your own copy

Don't edit the examples in `Analyses/` directly. Other people use them too, and you'll want a clean version to look
back at. Make your own bundle from the example instead:

Follow [Creating an analysis bundle](../4-Concepts/UsingFWWithCommands.md#creating-an-analysis-bundle)
with the name `my_first_production` and the example `Analyses/Examples/mutau_short`.

This creates `Analyses/my_first_production/` with a copy of the recipe. The recipe's `name` is now
`my_first_production`, the same as the folder. The long comments from the example aren't copied, so the new
`recipe.yml` is short. Open it and have a look:

<!-- TODO: real content of Analyses/my_first_production/recipe.yml after init -->

## 2. Tell TauFW where to put the runs

Production puts its merged tuples inside
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

Choose **Start a new run** and select `Analyses/my_first_production`. TauFW checks the recipe while you
review it. Fix any problems before starting. For a separate command-line check, see
[Checking a recipe](../4-Concepts/UsingFWWithCommands.md#checking-a-recipe).

## 3. Test it on a few events first

Before submitting 340 jobs, try the production code on a few events. Follow
[Testing production locally](../4-Concepts/UsingFWWithCommands.md#testing-production-locally)
with `Analyses/my_first_production` and 50 events. That section shows the command, real output,
and what to check. The test writes to `PicoProducer/output/` and doesn't create a run.

## 4. Look at the plan

In **Start a new run**, select your recipe and choose **View detailed plan**. Check the samples, job counts,
and the `Run root` line, which should show your work area. See
[Planning a recipe](../4-Concepts/UsingFWWithCommands.md#planning-a-recipe) for how to read the table
and the equivalent command.

## 5. Start the run

Return to the recipe review, choose **Start run**, and confirm.

TauFW creates a run folder under `<run_root>/my_first_production_<date>-<time>/` and copies your bundle
into it. From then on, the run reads that copy. Editing the original recipe won't change an existing run.
Production submits its jobs to HTCondor; you can follow the run from the menu while they work.

Save the run folder path so you can find its files later. For starting from a shell, see
[Starting a run](../4-Concepts/UsingFWWithCommands.md#starting-a-run).

## 6. Check on it

Choose **Inspect run status** and select your run. This only looks: it doesn't submit jobs or change the run.

## 7. Push it forward

Choose **Continue an existing run** and select your run. You can advance it once or keep checking repeatedly.

- If jobs are still running, TauFW waits for them.
- If some jobs failed, it resubmits those while attempts remain. The recipe's `max_tries: 3` gives each job
  three chances in total before the stage fails.
- Once all chunks succeed, TauFW merges them into one pico tuple per sample and marks the stage `DONE`.

See [Continue an existing run](../3-HowTo/ContinueRun.md) for picking it up after logging out.
The equivalent commands and polling options are in
[Inspecting and continuing a run](../4-Concepts/UsingFWWithCommands.md#inspecting-and-continuing-a-run).

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

The status view shows when the run is `DONE`:

<!-- TODO: real screenshot of Inspect run status on a DONE run -->

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
- **The stage is `FAILED`.** If some chunks still failed after all their tries (the message ends with
  "after 3 tries"), you can give them more tries without losing the jobs that worked. Fix the cause first (often the
  grid proxy), then choose **Continue an existing run**, pick the run and choose **Retry production**. It allows as many tries again as your recipe's
  `max_tries` (3 tries made: up to 6), resubmits only the failed chunks, and goes on like Continue. Nothing is moved
  or deleted. For any other production failure (no samples found, a merged tuple that failed its check), editing
  the recipe won't revive the run: fix the cause, then start a new run.

  The later stages you'll meet in the next tutorials (histograms, plots, the fit, Python steps) are different: when
  one of them fails, you can run just that stage again. Fix the cause first. If the fix is a file of your analysis,
  put it into the run's own copy, `<run folder>/bundle/` (the run never reads your analysis folder again).
  Choose **Continue an existing run**, pick the run and choose **Retry**. The stages that already finished don't run again. The failed
  attempt's logs and files move to `logs/<stage>/attempt1/`, so you can still read them. If you changed the
  `bundle/` copy, TauFW warns once and writes that down in `run.json`, so anyone reading the run later can see it.
- **You pressed Ctrl+C.** Your submitted batch jobs keep running. Choose **Continue an existing run**
  and select the same run to carry on.

For the retry command and which failures it can recover, see
[Retrying a failed stage](../4-Concepts/UsingFWWithCommands.md#retrying-a-failed-stage).
More in Troubleshooting *(coming soon)*.

## What's next

You have pico tuples. In Tutorial 2 *(coming soon)* you'll turn them into histograms and control plots.
