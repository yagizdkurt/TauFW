# TauFW tests

Use the lxplus **Python 3.9** environment with matching PyROOT, NumPy, and `future`
(`past`). NanoAODTools cases additionally require
`PhysicsTools.NanoAODTools` on the Python path. Activate your existing CMSSW/LCG
environment first and verify the interpreter you will use:

```bash
python3 -c 'import sys, ROOT, numpy; print(sys.version); print(ROOT.gROOT.GetVersion()); print(numpy.__version__)'
```

The harness supports Python 3.9 syntax. It records the **actual** patch version,
ROOT version, architecture, NumPy/future versions, and relevant NanoAODTools source
hashes in each lock. It does not assume that lxplus uses Python 3.9.25. Exact BBB
lock/check execution requires Linux with Python 3.9; use the same software stack
after refactoring.

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

### Quiet mode

```bash
python3 Tests/run.py normal -q
python3 Tests/run.py normal -q --tail 200
python3 Tests/run.py bbb check -q
```

`-q`/`--quiet` prints one character per case as it finishes (`P` pass,
`F` fail, `S` missing dependency) and hides the scripts' output. At the end,
each failure is shown with the last 80 lines of its combined stdout/stderr
(`--tail N`; `--tail 0` shows everything), its log path, and the command to
rerun it alone. Skips are grouped by reason. Every case's full output is kept in
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
| `common.table`, `common.loadingbar` | Python 2 print syntax; the Python 3.9 runner reports them as legacy. |
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
case twice in separate fresh workspaces. A failed or nonrepeatable case prevents
publication of the lock. Commit the generated `Tests/BBB/baselines/*.json`
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

## Small validation commands

```bash
# Offline: migration hashes, Python 3.9 syntax, selection and lock/check mechanics.
python3 Tests/check_harness.py

# lxplus: real ROOT serializer repeatability and deliberate output mutations.
python3 Tests/check_root.py
```

The ROOT check changes a histogram value/name and a tree branch type and verifies
that exact snapshots differ. It also checks a 64-bit event ID beyond double's
integer precision and verifies that differing container filenames do not change
the data snapshot. Neither command creates BBB expectations or submits jobs.

`migration.json` records all 38 original paths and original content hashes. The
additional canonical hashes tolerate Git's LF/CRLF checkout conversion only.
No existing test body or production implementation was rewritten.
