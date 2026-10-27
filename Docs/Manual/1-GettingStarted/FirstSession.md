# Your first session

**You'll learn:** how to get into TauFW each time you log in, how to find your way around the menu, and how to read a
recipe check and a plan.
**You need:** TauFW installed with [FastSetup](../FastSetup.md), and a lxplus account.
**Time:** about 15 minutes.

Nothing on this page submits jobs or writes anything big. You can't break anything here, so go ahead and try.

## Getting in

Log in to lxplus and go to your TauFW folder. FastSetup put it inside the CMSSW release, so it's usually here:

```bash
ssh <your username>@lxplus.cern.ch
cd ~/CMSSW_14_1_0_pre4/src/TauFW
source setup.sh
```

You do this every time you open a new terminal. The first `source setup.sh` installed everything. From now on it
just sets up the environment (it runs `cmsenv` for you) and opens the TauFW menu. It's quick.

Use `source`, not `bash setup.sh`. With `bash` the environment is set up in a separate shell, and it's gone as soon
as the script ends.

## The menu

When the menu opens, you'll see something like this:

<!-- TODO: real screenshot or text copy of the main menu, from lxplus -->

Use the arrow keys to move, Enter to pick something and Esc to go back. Here's what's there:

- **Start a new run**: pick a recipe from `Analyses/`, see its stages, and start it.
- **Continue an existing run**: pick a run you started earlier and push it forward.
- **Inspect run status**: see where a run is, without changing anything.
- **Tests**: run TauFW's automated tests.
- **Grid Certificate**: check your grid proxy, or make a new one.
- **Help**: short answers to common questions.
- **Exit**: leave the menu.

### First thing: your grid proxy

Look at **Grid Certificate**. A green tick means your proxy is fine. A yellow warning means it's missing or expired.

PicoProducer needs a valid proxy to ask DAS which files belong to a sample and to read files from remote storage.
Without one, production fails in confusing ways. So if you see the warning, select **Grid Certificate** and type
your grid certificate password. It's passed straight to `voms-proxy-init` and isn't saved anywhere.

A proxy lasts a limited time, so it's worth glancing at the tick every time you start working.

### Look at the recipes

Pick **Start a new run**. Don't worry, it doesn't start anything until you confirm.

On the left you'll see the recipes in `Analyses/`. On the right is the selected recipe's pipeline: its stages, top
to bottom, in the order they'll run. Move up and down through the list and watch the right side change.

One recipe, `example_broken`, is shown in red. That's on purpose. It's full of mistakes, so you can see what TauFW
does with a broken recipe. Select it and the problems are listed above its stages.

Press Esc until you're back in the main menu, then **Exit**.

## The same thing from the command line

Everything in the menu can also be done with commands. That's handy for scripts, or when you already know exactly
what you want. To see the commands:

```console
$ python3 taufw.py --help
usage: taufw.py [-h] COMMAND ...

Run TauFW analysis pipelines from a recipe.

positional arguments:
  COMMAND
    check     list every problem of a recipe
    plan      show each stage's plan (nothing is written)
    start     start a new run
    advance   continue a run
    status    state of a run (read-only)
    init      new analysis bundle
    configs   the config templates of Configs/
```

Always run these from the TauFW folder, with `python3 taufw.py`.

### Checking a recipe

`check` reads a recipe and lists everything wrong with it, all at once. Try it on the broken example:

```console
$ python3 taufw.py check Analyses/example_broken
>>> Warning: run_root: not set: the runs go to taufw_runs/ in the directory taufw.py is started from, ...
>>> Warning: Recipe example_broken: 4 problem(s)
>>> Warning:   stages[0] (production): unknown option 'samplez' (known: batchopts, channels, checkdas, ...)
>>> Warning:   stages[2] (python).file: steps/missing_check.py is not a file of the bundle (...), a Configs/ template or an absolute path: ...
>>> Warning:   stages[1] (controlhists).inputs.tuples: no stage 'prodution' in the recipe
>>> Warning:   pico.config: file not found: .../Analyses/example_broken/missing_pico.json
```

Each line tells you where the problem is and what's wrong. `stages[0]` is the first stage in the recipe, `stages[1]`
the second, and so on, counting from zero. Here there's a typo in an option name (`samplez`), a typo in a stage name
(`prodution`) and two files that don't exist.

The first line is a warning, not a problem. It says the recipe doesn't set `run_root`, the folder where runs are
created. Without it, runs go into `taufw_runs/` right inside your TauFW folder. That's fine for a quick try, but
production writes tens of GB and your lxplus home only holds a few GB. You'll fix this in the first tutorial.

Get used to running `check` after every edit. It's instant and saves you from finding a typo three hours into a
run.

### Planning a recipe

`plan` goes one step further. It works out exactly what the recipe would do, without doing any of it. Try it on the
short example:

```console
$ python3 taufw.py plan Analyses/example_mutau_short
>>> === [production] 2022_postEE, mutau ===
>>> DYto2L-4Jets_MLL-50
>>> /DYto2L-4Jets_MLL-50
...
>>> Bundle: /afs/cern.ch/user/y/ydinckur/CMSSW_14_1_0_pre4/src/TauFW/Analyses/example_mutau_short
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

## What's next

You've seen the menu, a broken recipe and a plan. In [Tutorial 1](../2-Tutorials/01-FirstProduction.md) you'll
run this same recipe for real and get your first pico tuples.
