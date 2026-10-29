# Continue an existing run

Run `taufw` (after `source taufw.sh`) and choose **Continue an existing run**. Pick your
[run](../4-Concepts/Glossary.md) and choose one advance or repeated checking.

If you've just logged in, [set up your environment](../1-GettingStarted/FirstSession.md#getting-in) first.
The menu also has **Inspect run status** if you only want to look.

For the equivalent commands, including repeated checking, see
[Inspecting and continuing a run](../4-Concepts/UsingFWWithCommands.md#inspecting-and-continuing-a-run).

## If it doesn't continue

Read the status message and the run's `run.log`. If a stage is `FAILED`, continuing won't
retry it. Fix the cause first, then follow the
[retry instructions](../4-Concepts/UsingFWWithCommands.md#retrying-a-failed-stage); which failures you can
retry depends on the stage.

The run reads its own copy of your analysis in `bundle/`. Editing the original analysis folder doesn't
change an existing run. Choose **Continue an existing run** to resume it; **Start a new run** creates a separate run.
