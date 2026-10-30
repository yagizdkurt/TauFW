# Continue an existing run

Run `taufw` (after `source taufw.sh`) and choose **Continue an existing run**. Pick your
[run](../4-Concepts/Glossary.md): its actions and stages appear next to the list.

If you've just logged in, [set up your environment](../1-GettingStarted/FirstSession.md#getting-in) first.
The menu also has **Inspect run status** if you only want to look.

## Move the run forward

- **Advance to the end** runs every stage that isn't done yet. While batch jobs run, it checks them every
  10 minutes. You can leave the screen; the run goes on behind the menu.
- **Next stage only** runs one stage and stops. The run is then `PAUSED`: look at what that stage made before
  you go on.
- **Advance until...** lets you pick a stage. The run goes on until that stage is done, then pauses.

## Change something and run it again

Analysis is trial and error: you look at a stage's output, change an option, and run that stage again.

1. Choose **Edit run config** (or press **E**). On the left are the run's own files, starting with its
   `recipe.yml`; on the right is the file you've selected. Press **Enter** to edit it, **F2** to save. A
   `recipe.yml` with a mistake isn't saved; the editor tells you what's wrong.
2. If your change affects a stage that's already done, the menu offers **Rerun from** that stage.
3. **Rerun from...** shows the run's stages. For the one you select, the right side lists what runs again and
   what's kept. Press **Enter**, then choose **Rerun to the end**, or **Rerun only** that stage.

Nothing is deleted. What the earlier attempt made moves to `logs/<stage>/attempt<N>/` in the run folder.
**History** lists every version of the run's recipe and every earlier attempt of each stage. Select a stage,
press **Tab**, then **Enter** on an attempt to read its log.

You can't change the production stage, or a stage before it, in the same run: start a new run for that.
While an advance works on the run, **Edit run config** waits until it ends.

For the equivalent commands, see
[Inspecting and continuing a run](../4-Concepts/UsingFWWithCommands.md#inspecting-and-continuing-a-run),
[Changing a run's recipe](../4-Concepts/UsingFWWithCommands.md#changing-a-runs-recipe) and
[Running stages again](../4-Concepts/UsingFWWithCommands.md#running-stages-again).

## If it doesn't continue

Read the status message and the run's `run.log`. If a stage is `FAILED`, continuing won't run it again by
itself. Fix the cause first (**Edit run config** if it's one of the run's files), then choose
**Rerun <stage> (failed)**. Which failures you can recover from depends on the stage; see
[Running stages again](../4-Concepts/UsingFWWithCommands.md#running-stages-again).

The run reads its own copy of your analysis in `bundle/`. Editing the original analysis folder doesn't
change an existing run: use **Edit run config** for that run, or **Start a new run** to start a separate run
with your edited analysis.
