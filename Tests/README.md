# TauFW tests

The reference environment is **`CMSSW_14_1_0_pre4`** on lxplus (see the
[installation instructions](../README.md#CMSSW-environment)). It provides Python 3.9.14,
ROOT 6.30.07, NumPy 1.24.3, `future` (`past`) 1.0.0 and `PhysicsTools.NanoAODTools`,
which NanoAODTools cases require. Older releases such as `CMSSW_12_4_8` (ROOT 6.24) are
not supported: `plotter.tgaxis` needs ROOT 6.30. Run `cmsenv` in the release first and
verify the interpreter you will use:

```bash
python3 -c 'import sys, ROOT, numpy; print(sys.version); print(ROOT.gROOT.GetVersion()); print(numpy.__version__)'
```

The harness supports Python 3.9 syntax. It records the **actual** patch version,
ROOT version, architecture, NumPy/future versions, and relevant NanoAODTools source
hashes in each lock. It does not assume that lxplus uses Python 3.9.25. Exact BBB
lock/check execution requires Linux with Python 3.9; use the same software stack
after refactoring.

## All automated tests (quiet shortcut)

From the repository root, run:

```bash
python3 Tests/run.py all
```

This runs the Utilities, Framework, Setup, processor compatibility, Fitter API and
Plotter API unit tests (`Tests/Fitter/api`, `Tests/Plotter/api`: the commands of the
Fitter and Plotter scripts, with a fake process runner), the harness and ROOT serializer checks, every normal case, and `bbb check` in
quiet mode. Passing output is captured in logs; failures show their output tail
and rerun command. Use `all --tail N` to change the tail length, or `all -v` for
full output from every suite. Check logs are in
`Tests/.artifacts/logs/checks/`; normal and BBB logs retain their usual locations.
All suites are attempted even when an earlier suite fails, and the command exits
nonzero if any suite fails. Ctrl-C stops execution.

The full run requires the reference lxplus environment and an existing BBB lock.
It never creates or replaces baselines. Integration cases and known legacy/broken
scripts retain their explicit selection requirements.

## Normal tests

Run commands from the repository root:

```bash
python3 Tests/run.py list
python3 Tests/run.py normal
python3 Tests/run.py normal --case plotter.variables
python3 Tests/run.py normal --case plotter.unroll
python3 Tests/run.py normal --case pico.testmodule
```

Calling `python3 Tests/run.py` also selects normal tests. Every selected script
runs in its own process and temporary workspace. The runner uses fresh copies of
the current source, preserving its contents and package layout while isolating
config writes, generated plots/files, and C++ compilation. Existing compiled
libraries are not reused. Calibration/data directories are read through links;
normal cases do not need remote storage. `plotter.unroll` reads the committed
`Tests/Plotter/DYJetsToLL_M-50_mumu.root`, copied to the relative path the script
expects; the other normal input cases use small synthetic files.
Sibling imports such as `pseudoSamples` and relative macro paths remain valid.
A failed subprocess returns a nonzero exit status. A case whose declared
dependency (ROOT, NumPy, NanoAODTools, ...) cannot be imported is reported as
SKIP; skips alone do not fail the run, but a run where every case was skipped does.

### Output (quiet by default)

```bash
python3 Tests/run.py normal
python3 Tests/run.py normal --tail 200
python3 Tests/run.py normal -v
python3 Tests/run.py bbb check
python3 Tests/run.py bbb check -v
```

`normal`, `integration`, `all`, and `bbb check`/`lock` are quiet by default:
scripts' output is captured and each case gets a status letter on a line,
`name ....... P`, with the letter appearing when the case finishes: `P` pass
(green), `F` fail (red), `S` missing dependency (yellow). Several selected cases
from the same file share one line under the file name, e.g.
`BBB/cases.py ... PPFPP`. Colors are used only on a terminal; set `NO_COLOR=1`
to turn them off. `-v`/`--verbose` streams full worker output instead; `--tail`
cannot be combined with it. The old quiet flags are removed. `bbb list` and
`bbb diff` have fixed output and accept neither verbosity nor tail flags.
At the end, normal/integration failures show the last 80 lines of combined
stdout/stderr (`--tail N`; `--tail 0` shows everything), the log path, and the
command to rerun the case alone. BBB check reports field differences and, for
worker failures, the output tail and log path. Skips are grouped by reason.
Every case's full output is kept in
`Tests/.artifacts/logs/normal/<case>.log` (`.../bbb/` for BBB), which is
ignored by Git and replaced on the next quiet run. Ctrl-C stops the run and
still prints the summary of the cases that finished.

The normal scripts, their defaults, and their existing diagnostics/assertions
are unchanged. A PASS means the script exited successfully; the harness does not
turn printed diagnostic messages into new assertions. Scripts which already
generate pseudo-samples keep their existing generator. ROOT's seed is initialized
to 1777 in each worker; scripts' own explicit seed settings still apply. Existing
event-count defaults are preserved, so the complete normal suite can take longer
than a selected smoke check.

Integration cases require explicit selection and keep their original CLI:

```bash
python3 Tests/run.py integration --case pico.sfs -- -t mu -y UL2018
```

Inspect the script and supply its original arguments before selecting an
integration case. `pico.batch` can submit actual jobs and is never selected by
normal execution. Historical coffea, calibration, DAS, and real-dataset
demonstrations remain integration cases. No integration jobs were run during
this migration.

### Preserved existing problems

| Case | Existing limitation |
| --- | --- |
| `common.table` | Python 2 print syntax; the Python 3.9 runner reports it as legacy. |
| `pico.sample` | Unclosed parenthesis at line 88; also uses real DAS discovery. |
| `plotter.rdataframe` | Fails at import with `NameError`: line 17 uses `kBlue`/`kRed`/`kGreen`/`kMagenta`, which are never imported from ROOT. Beyond that, its main passes filename strings to a tuple loop, the implementation references undefined variables including `res_dict`, `sname`, and `xvar`, and its default inputs are on `/scratch`. |

These files were moved unchanged and are excluded from normal execution.
Selecting them explicitly fails with their classification and reason. Modern
Sample/SampleSet RDataFrame behavior is exercised by BBB and the existing
`plotter.rdataframe_sample` script.

`pico.eventbased` retains its original DAS-backed default scenario. The additional
`pico.eventcomparison` ID invokes its existing comparison mode with two synthetic
local trees. No comparison logic was changed.

### Relocated analysis demonstration

`PicoProducer/python/analysis/TestModule.py` now lives at
`Tests/PicoProducer/analysis/TestModule.py`. Its import is:

```python
from Tests.PicoProducer.analysis.TestModule import TestModule
```

The old `TauFW.PicoProducer.analysis.TestModule` path and production module-name
loading of `TestModule` no longer work, as agreed for this migration. No source
compatibility shim was added. The test runner configures TauFW imports for the
local checkout; ordinary application imports still use their normal setup.

## BBB: exact data and schema regression tests

BBB is never imported or executed by the normal command:

```bash
python3 Tests/run.py bbb list
python3 Tests/run.py bbb lock
python3 Tests/run.py bbb check
python3 Tests/run.py bbb check --case plotter.histograms
```

Before any refactor, run representative normal tests on lxplus, run the small
ROOT serializer checks below, and capture the complete lock. Lock runs every BBB
case twice in separate fresh workspaces; `--case` is rejected for lock. Quiet
lock prints one line of P/F letters and keeps both runs in
`Tests/.artifacts/logs/bbb/<case>.run1.log` and `<case>.run2.log`. Both runs are
attempted even if one fails. After the LOCK SUMMARY, each failed case shows its
reason and the last N lines from both logs with their paths (`--tail N`, default
80; `--tail 0` shows all lines). Successful runs end with `Locked N BBB cases.`;
any failed or nonrepeatable case prevents publication and reports that no
expectations were written. Use `bbb lock -v` for full worker output. Commit the
generated `Tests/BBB/baselines/*.json`
snapshots and manifest before changing production implementation. No baseline
was fabricated in the Windows environment used to implement the harness.

The fixed tables in `fixtures/events.json` generate small, real ROOT trees and
histograms using ROOT storage primitives. Input generation does not call the
production transformations under test. Both the definition and generator are
fingerprinted, so changing the fixtures invalidates the lock. Coverage includes:

- Common table/loading-bar text, chunking, partitioning, and path/argument formatting.
- Plotter selection/context metadata, weighted 1D/2D histograms, normalization,
  flow bins, merging, splitting, DY stitching, QCD OS/SS estimation, and C++ unrolling.
- PicoProducer branch schema, defaults, aliases, fixed/variable arrays, 64-bit
  event IDs, cutflow, NanoAODTools selection/range bookkeeping, and synthetic SF lookup.
- Fitter nominal/systematic shape names, negative-bin sanitation, adaptive
  rebinning, and non-ZTT subtraction.

Snapshots preserve object/key names and classes, key cycles, directory structure,
histogram axes/labels, contents/errors/statistics, branch types/order, aliases,
and entry values/order. Floating-point values use their exact IEEE bytes in
hexadecimal, including signed zero, with no tolerance or rounding. Tree integer
values are read using typed access rather than conversion through a double.
Unknown ROOT object/branch types fail explicitly.

Container timestamps, UUIDs, compression/physical offsets, and temporary file
paths are excluded. Rendering pixels and general style changes are outside BBB's
data/schema coverage. Log timing messages are not captured; explicit common-tool
formatting outputs are captured. BBB uses fixed seeds and single-threaded execution.

`check` is read-only and reports exact field paths for differences. Missing/extra
outputs, changed case inventory or fixtures, modified baseline files, and runtime
differences fail. Missing expectations never create a baseline automatically.
After reviewing an intentional output or runtime change, replace the entire lock
explicitly and review the resulting Git diff:

```bash
python3 Tests/run.py bbb lock --replace
```

This initial suite characterizes the listed boundaries; it is not coverage of
every channel, calibration, production workflow, or fit.

### PicoProducer command cases (black box)

`pico.config`, `pico.run`, `pico.jobs`, `pico.merge` and `pico.workers` drive the
real user surfaces: `PicoProducer/scripts/pico.py` and the job workers. Each
command runs in a fresh child process (`BBB/pico_entry.py`) against the
workspace mirror, like a command typed in a shell. `BBB/pico_harness.py` gives
every case:

- a fixed `config.json`;
- its own sample catalog (`samples/bbb/samples_2018.py`) over Local storage;
- synthetic NanoAOD inputs;
- fake `condor_submit`/`condor_q` executables on `PATH`. These record the
  submission command lines and report a scripted queue.

The cases snapshot only artifacts: config JSON and backups, job configs (without
their creation time), task lists, scheduler command lines, status summary lines,
`run --dry` command lines, merged and worker ROOT outputs, and file listings after
cleanup. They import no PicoProducer internals. Workspace paths are written as
`$WS`, and script locations inside `PicoProducer/python` are reduced to
`<pico>/<file name>`. So restructuring the package keeps the baselines, while a
changed command line, option, file name or output does not. Known bugs whose
behavior these baselines record are listed in `PicoProducer/docs/BUGS.md`.

## Small validation commands

```bash
# Offline: migration hashes, Python 3.9 syntax, selection and lock/check mechanics.
python3 Tests/check_harness.py

# Windows: offline Utilities tests.
python -m unittest discover -s Tests/Utilities -p "test_*.py"

# lxplus: real ROOT serializer repeatability and deliberate output mutations.
python3 Tests/check_root.py
```

`check_harness.py` keeps the unittest CLI: detailed output by default, its own
`-q` for a summary, and `-v` for detailed test names. These unittest flags are
independent of the runner flags. The `all` command passes `-q` to unittest
workers by default and `-v` when invoked with `all -v`.

To verify the output change on lxplus, activate `CMSSW_14_1_0_pre4` with `cmsenv`
and run from the TauFW checkout using the same Python 3.9 stack as the lock:

```bash
python3 Tests/run.py bbb check
python3 Tests/run.py bbb check -v
python3 Tests/run.py bbb lock --replace
git status --short -- Tests/BBB/baselines/
git diff --exit-code -- Tests/BBB/baselines/
```

Both checks must pass. Replacement must reproduce identical baselines: the status
command must print nothing and the diff must exit zero. No baseline changes are
expected from this harness update.

The ROOT check changes a histogram value/name and a tree branch type and verifies
that exact snapshots differ. It also checks a 64-bit event ID beyond double's
integer precision and verifies that differing container filenames do not change
the data snapshot. Neither command creates BBB expectations or submits jobs.

`migration.json` records all 38 original paths and original content hashes. The
additional canonical hashes tolerate Git's LF/CRLF checkout conversion only.
No existing test body or production implementation was rewritten.
