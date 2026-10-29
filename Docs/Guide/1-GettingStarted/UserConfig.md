# Your user config

**You need:** TauFW installed with [FastSetup](../FastSetup.md).

Some settings belong to you, not to an analysis. Where your EOS area is, which batch queue you like, where your runs
should go. They're different for every person, so they shouldn't live in a recipe that you share with others, and
they shouldn't live in a file that git tracks either.

That's what the user config is for. It's one file, just for you:

```text
Analyses/UserConfig.yaml
```

Git ignores it, so you can't commit it by accident, and a `git pull` never overwrites it. Nobody else sees it.

## Open it and check it

Choose **Modify User Config** from the TauFW menu to open the file.

Before saving, TauFW checks the YAML and its own settings. If something is wrong, it shows the problem so you can fix it.

On lxplus, a new one looks like this:

```yaml
# TauFW user configuration: your personal and machine settings.
# Guessed for lxplus (user jdoe).

taufw_user:
  version: 1           # the format of this file (set by TauFW, do not change)
  reviewed: false      # true: you checked this file
notifications: true  # Set false to remove sound notifications.
open_menu_on_start: true

runs:
  # where your runs go when the recipe has no run_root and you give no --run-root
  run_root: "/afs/cern.ch/work/j/jdoe/taufw_runs"

production:
  # the batch system: HTCondor, SLURM, ...
  batch: "HTCondor"
  # the queue (HTCondor: job flavour), when the recipe gives none
  # queue: "workday"
  # extra batch options, when the recipe gives none
  # batchopts: ""
  # the output of the jobs, before the merge
  outdir: "/eos/user/j/jdoe/taufw/output/$ERA/$CHANNEL/$SAMPLE"
  # the output of skim jobs
  nanodir: "/eos/user/j/jdoe/taufw/samples/nano/$ERA/$DAS"
  # a temporary directory of skim jobs
  # tmpskimdir: "/tmp/user"
  # processes that count events and check files at once, when the recipe gives none
  # ncores: 4
  hadd:
    # another command to merge the files
    # cmd: "python3 haddnano.py"
    # files the merge opens at once
    # maxopenfiles: 500
```

`notifications` and `open_menu_on_start` are always written with their defaults. The setup guessed the other values
that have no `#` in front. A line that starts with `#` is not set, and TauFW uses its own default for it. To set
one, remove the `#` and change the value. Your own sections (like `mystudy:` below) are kept.

### Where the values come from

The setup fills in what it can work out for you:

- Your job output goes to a `taufw/` folder in your EOS area, so TauFW doesn't spread its folders all over your
  EOS home.
- Your runs go to your AFS work area, `/afs/cern.ch/work/<initial>/<username>/taufw_runs`. Not everyone has a work
  area. If you don't, `run_root` stays a comment line, and you should pick a folder with enough space yourself.
  Your AFS home is too small for runs.
- If you already had a `PicoProducer/config/config.json` (because you used `pico.py` before), its values win over
  the guesses. So if you once moved your job output somewhere else, recipes keep using that folder. The file says
  so in a comment line at the top: `Taken from .../config.json: ...`.

Outside lxplus nothing is guessed, all settings are comment lines, and PicoProducer keeps its own defaults.

### What each setting does

| Setting | What it does | If you don't set it |
| --- | --- | --- |
| `notifications` | Terminal bell when a recipe, test run or installation completes, or an operation fails. Set `false` to mute. | `true`. |
| `open_menu_on_start` | Whether `source taufw.sh` opens the menu. Set `false` to only get the environment and the `taufw` command. | `true`. |
| `runs.run_root` | The folder where your runs are made, when the recipe has no `run_root` and you don't give `--run-root`. | Runs go to `taufw_runs/` in the folder you start from, with a warning. |
| `production.batch` | The batch system. On lxplus it's `HTCondor`. | PicoProducer's guess for your machine. |
| `production.queue` | The queue, for HTCondor the job flavour (`espresso`, `workday`, ...). | Nothing: the batch system's default. |
| `production.batchopts` | Extra options for the batch system. | None. |
| `production.outdir` | Where jobs write their output, before it's merged into tuples. | PicoProducer's default folder. |
| `production.nanodir` | Where skim jobs write their output. | PicoProducer's default folder. |
| `production.tmpskimdir` | A temporary folder for skim jobs. | None. |
| `production.ncores` | How many files are checked at once, when TauFW counts events and validates job output. It's not the number of cores of a job. | 4. |
| `production.hadd.cmd` | Another command to merge the files, instead of `hadd`. | `hadd`. |
| `production.hadd.maxopenfiles` | How many files the merge opens at once. | 500. |

### Terminal notifications

TauFW sends one terminal bell when a recipe finishes or stops with a problem, a menu test run ends, or an
interactive installation finishes. Menu notifications also work while another screen is open. Reopening an
old result does not ring again, and waiting for batch jobs, automatic retries and cancelled operations stay silent.
Bells go only to an attached terminal, never into redirected error output or worker logs. The terminal controls
the actual sound and visual alert.

Notifications are enabled by default. To mute them, set this line of your user config to `false`:

```yaml
notifications: false
```

Set it back to `true` (or remove the line) to enable bells again. The menu reads the preference for each notification,
so changes apply without restarting it.

In VS Code, enable `accessibility.signals.terminalBell` with `"sound": "on"` and, optionally,
`terminal.integrated.enableVisualBell`. In Windows Terminal, enable the profile's audible bell and taskbar alerts.
If a terminal suppresses bells, TauFW cannot force it to play a sound.

### Who wins

The recipe is shared, so it says what the analysis needs. Your user config says what you prefer. When both say
something, the recipe wins.

If the run root still points into your AFS home, set `run_root` to a folder with enough space before starting
production. Once it's set, the warning about the default run root goes away.

And every run keeps a note of which settings came from your user config, in its `run.json`.

One rough edge: don't change `outdir` while a run is still producing tuples. Jobs that are already running keep
writing to the old folder, but a job that gets resubmitted writes to the new one, and the merge then can't find
all the pieces. Change it between runs.

### Mark it as checked

`reviewed` is for you. It says whether you've looked at the file yet. As long as it's `false`, every
`taufw check`, `plan` and `start` prints one extra warning line, reminding you that the file is there and still
unchecked. It doesn't stop anything, your recipe runs as usual. Once you've read through the file, set it to
`true` and the warning goes away:

```yaml
taufw_user:
  version: 1
  reviewed: true
```

## Reading it from your own scripts

You can read the user config from any Python script of yours. This is handy for things like "where do I put my
plots" or "which EOS folder holds my private tuples", things you don't want to hard-code into a script you might
share later.

Run your script inside the TauFW environment (after `source taufw.sh`), then:

```python
from TauFW.Utilities import UserConfig

config = UserConfig.load()
print(config.path)       # where the file is
print(config.exists)     # False if you don't have the file yet
print(config.reviewed)   # what you wrote in the header
```

`load()` never fails just because the file is missing. You get an empty config back, and every value you ask for
comes back as its default. It only complains if the file is there but broken, and then the error message names
the file.

### Getting a value

Settings are grouped in sections. You ask for a value with the section and the key, joined by a dot. Say your file
has this at the bottom:

```yaml
mystudy:
  plotdir: /eos/user/j/jdoe/www/mystudy
  eras: [2022_postEE, 2023C]
  binning:
    pt: [20, 30, 50, 100]
```

Then:

```python
plotdir = config.get("mystudy.plotdir")                 # "/eos/user/j/jdoe/www/mystudy"
eras    = config.get("mystudy.eras", ["2022_postEE"])   # the list from the file
ptbins  = config.get("mystudy.binning.pt")              # [20, 30, 50, 100]
tag     = config.get("mystudy.tag", "")                 # not in the file: you get the default, ""
```

`get()` gives you the default (or `None` if you didn't give one) whenever something on the way is missing. That's
nice for optional settings. For a setting your script can't work without, use `require()` instead:

```python
plotdir = config.require("mystudy.plotdir")
```

If the key isn't there, `require()` stops with an error that names the file and the key, so whoever runs your
script knows exactly what to add. You can catch it if you want to handle it yourself:

```python
try:
    plotdir = config.require("mystudy.plotdir")
except UserConfig.UserConfigError as error:
    print(error)
    plotdir = "plots"
```

### A whole section at once

```python
mystudy = config.section("mystudy")   # {"plotdir": ..., "eras": [...], "binning": {...}}
everything = config.values            # every section, without the taufw_user header
```

Both give you a copy, so changing it in your script doesn't change anything else.

### Adding your own settings

You can put your own sections into the file, like `mystudy` above. TauFW keeps everything you write there. Pick a
section name that's clearly yours (your study's name works well), so it won't clash with `runs`, `production` or
the settings TauFW adds later.

One thing to think about: a [python step](../4-Concepts/Glossary.md) in an analysis bundle can read the user config
too, but then the bundle only works for people who have the same keys in their own file. If you plan to share a
bundle, put what the analysis needs into the bundle itself, and keep the user config for things that are really
about you and your machine.

## Using another file

By default TauFW reads `Analyses/UserConfig.yaml` of the TauFW folder you're working in. If you have more than one
TauFW checkout and want them to share one file, point the `TAUFW_USER_CONFIG` variable at it, for example in your
`~/.bashrc`:

```bash
export TAUFW_USER_CONFIG=/afs/cern.ch/user/j/jdoe/TauFWUserConfig.yaml
```

Use a full path. Then the [user config command](../4-Concepts/UsingFWWithCommands.md#creating-your-user-config)
makes that file if it doesn't exist yet, and everything,
including your scripts, reads it instead. `UserConfig.location()` in Python tells you which file is being used.

## What's next

Go on with [your first session](FirstSession.md) to find your way around the menu.
