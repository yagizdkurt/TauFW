Capture real expectations on lxplus in `CMSSW_14_1_0_pre4` (Python 3.9) before refactoring:

```bash
python3 Tests/run.py bbb lock
python3 Tests/run.py bbb check
git add Tests/BBB/baselines
```

No ROOT baseline has been fabricated on Windows. The first lock must finish all
cases twice without differences. Commit its JSON snapshots and manifest alongside
the fixture definitions. `check` never creates or updates expectations.

After reviewing an intentional output or runtime change, explicitly replace the
entire lock with `python3 Tests/run.py bbb lock --replace` and review the Git diff.

`python3 Tests/run.py bbb diff` compares the lock on disk with the committed one
(`--ref <rev>` for another revision) and prints PASS when every committed case is
unchanged; added cases pass, changed or removed cases fail with their differing fields.
It only reads files and Git, so it also runs on Windows.
