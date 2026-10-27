# Your user config

**You'll learn:** what the user config file is, where it lives, how to mark it as checked, and how to read it from
your own Python scripts.
**You need:** TauFW installed with [FastSetup](../FastSetup.md).
**Time:** about 10 minutes.

Some settings belong to you, not to an analysis. Where your EOS area is, which batch queue you like, where your runs
should go. They're different for every person, so they shouldn't live in a recipe that you share with others, and
they shouldn't live in a file that git tracks either.

That's what the user config is for. It's one file, just for you:

```text
Analyses/UserConfig.yaml
```

Git ignores it, so you can't commit it by accident, and a `git pull` never overwrites it. Nobody else sees it.

One honest note before you start: the file is new, and right now it doesn't hold any settings yet. The TauFW group
is still deciding what goes in. So today the file is mostly a header, and the next sections show you how it works
so you're ready when the settings arrive. Until then, production still takes its paths and batch settings from
`PicoProducer/config/config.json`, as before.

## Where it comes from

FastSetup makes the file for you, near the end of the installation. Its summary shows where it put it:

<!-- TODO: real output of the FastSetup summary on lxplus, with the "User config" line -->

If you installed TauFW before the user config existed, you don't have the file yet. Make it with:

```bash
python3 taufw.py userconfig
```

<!-- TODO: real output of python3 taufw.py userconfig on lxplus, first run and second run -->

You can run this as often as you like. If the file is already there, it doesn't touch it. It just tells you where
the file is and whether you still need to check it.

## Open it and check it

Open the file in any editor. A new one looks like this:

```yaml
# TauFW user configuration: your personal and machine settings.
#
# Made by the setup (or `python3 taufw.py userconfig`). Git ignores this file and nothing overwrites it.
# Set reviewed to true once you checked the values below: until then, taufw.py check, plan and start warn.
# The settings are added here as TauFW starts to read them.

taufw_user:
  version: 1           # the format of this file (set by TauFW, do not change)
  reviewed: false      # true: you checked this file
```

The `taufw_user` block at the top is the header. Leave `version` alone, TauFW uses it to know which format the file
is in.

`reviewed` is for you. It says whether you've looked at the file yet. As long as it's `false`, every
`taufw.py check`, `plan` and `start` prints one extra warning line, reminding you that the file is there and still
unchecked. It doesn't stop anything, your recipe runs as usual. Once you've read through the file, set it to
`true` and the warning goes away:

```yaml
taufw_user:
  version: 1
  reviewed: true
```

If the file is missing, you'll get a similar one-line warning that tells you to run `python3 taufw.py userconfig`.
If the file is broken (say, a YAML typo, or `reviewed: maybe`), the warning names the file and says what's wrong
with it.

## Reading it from your own scripts

You can read the user config from any Python script of yours. This is handy for things like "where do I put my
plots" or "which EOS folder holds my private tuples", things you don't want to hard-code into a script you might
share later.

Run your script inside the TauFW environment (after `source setup.sh`), then:

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
section name that's clearly yours (your study's name works well), so it won't clash with the settings TauFW adds
later.

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

Use a full path. Then `python3 taufw.py userconfig` makes that file if it doesn't exist yet, and everything,
including your scripts, reads it instead. `UserConfig.location()` in Python tells you which file is being used.

## What's next

Go on with [your first session](FirstSession.md) to find your way around the menu.
