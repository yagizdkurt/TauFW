# Legacy and broken cases excluded from normal tests

The defect descriptions, original evidence and validation limits for `pico.sample`
and `plotter.rdataframe` have moved to
[Legacy/Bugs.md](../Legacy/Bugs.md#excluded-broken-test-and-demonstration-scripts).
They concern demonstration/test scripts, not established defects in production classes.

[inventory.json](inventory.json) retains the case classifications and exclusion reasons.
The [test runner](run.py) maps `normal` to the `local` group and rejects explicitly
requested broken cases. See the [test instructions](README.md) for current usage.
