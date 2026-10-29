# User config (Git Never Changes This)

- A line that starts with `#` is not set: TauFW uses its default.
- To set one, remove the `#` and change the value.
- If a recipe sets the same thing, the recipe wins.
- F5 switches between this help and the file. F4 hides this help.

## taufw_user

- `version`: set by TauFW. Don't change it.
- `reviewed`: set it to `true` once you've checked the file.
- `notifications`: a terminal bell when a recipe or a test run finishes, or something fails. `false` turns it off.
- `open_menu_on_start`: `false` means `source taufw.sh` sets up TauFW without opening this menu.

## runs

- `run_root`: the folder for your runs. Use a full path, without `~` or `$`. Your AFS home is too small; your AFS
  work area or EOS is better. Not set: `taufw_runs/` in the folder you start from.

## production

- `batch`: the batch system, `HTCondor` on lxplus.
- `queue`: the HTCondor job flavour, e.g. `espresso`, `workday`, `tomorrow`. Not set: the batch system's default.
- `batchopts`: extra options for the batch system.
- `outdir`: where jobs write their output before the merge. Don't change it while a run is still producing tuples.
- `nanodir`: where skim jobs write their output.
- `tmpskimdir`: a temporary folder for skim jobs.
- `ncores`: how many files TauFW checks at once when it counts events. This is not the number of cores of a job.
  Not set: 4.
- `hadd.cmd`: another command to merge the files. Not set: `hadd`.
- `hadd.maxopenfiles`: how many files the merge opens at once. Not set: 500.

In `outdir` and `nanodir`, `$ERA`, `$CHANNEL`, `$SAMPLE` and `$DAS` are filled in for each sample.

## Your own settings

You can add your own sections, e.g. `mystudy:`. TauFW keeps them. Read them in a script with
`UserConfig.load().get("mystudy.plotdir")`.
