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

### Interactive testing menu

After setting up TauFW, run `python3 taufw.py` and select **Tests**. The menu
requires an interactive Linux terminal and working Framework imports. It offers
all automated tests, unit/harness checks, normal tests, BBB regression checks,
and the advisory environment diagnostic.

For each test family, run the entire family or choose unit suites/individual
normal or BBB cases. Use Up/Down to move, Space to toggle selections, then move
to **Run** and press Enter. At least one selection is required. Review the
selected tests before running; Esc or Back cancels. Page Up/Down scroll details,
including descriptions and declared dependencies where available.

The tests run behind the menu: `Tests/run.py` (quiet, the usual PASS/FAIL/SKIP
reporting) with the current Python interpreter from the checkout root, started
by a small supervisor in a session of its own. The test screen follows it live:
the cases with their state and time, the focused case's details and the end of
its log; Enter shows the whole case log, L the output of `Tests/run.py`, End
follows a log again after scrolling. **Esc leaves the screen and the tests keep
running**: the main menu shows **Tests (Running 12/40)**, then **Tests (Done)**,
**Tests (Failed: 3)**, **Tests (Stopped)** or **Tests (Lost)**; selecting Tests
while they run opens their screen again, also from a menu opened later in the
same login session or on another lxplus machine. After a run, the Tests menu
starts with **Last run: ...** to look at it again. One test run at a time.
**S** (or Ctrl-C) asks, then stops the run and its workers. Quitting the menu
while tests run asks first: stay, stop them, or quit and leave them running.
They run only as long as the login session: a run killed when the SSH session
ends is shown as **Lost** (no sign of life for two minutes). The run's files are
in `.artifacts/menu/operations/tests-<time>/` (`output.log`, `events.jsonl`;
the last five runs are kept). Normal PASS means successful script
exit, not additional assertions. Full runs still require the reference software
stack and an existing BBB lock; the menu does not install dependencies or create
baselines. Integration tests and baseline changes remain CLI-only.

For command-line suite selection, use `python3 Tests/run.py checks` or repeat
`--case`, for example `python3 Tests/run.py checks --case unit.utilities`.
`python3 Tests/run.py catalog` prints read-only JSON metadata (`checks`, `normal`,
`bbb`; each item has `id`, `description`, and `dependencies`) for the menu without
running tests or importing ROOT.

### Command-line shortcut

From the repository root, run:

```bash
python3 Tests/run.py all
```

This runs the Utilities, Framework, Setup, processor compatibility, Fitter API,
Histogrammer API and Plotter API unit tests (`Tests/Fitter/api`, `Tests/Histogrammer/api`,
`Tests/Plotter/api`: the commands of the Fitter, Histogrammer and Plotter scripts, with a fake
process runner), the sample model tests
(`Tests/Histogrammer/sample_model`: the templates of `Configs/Histogrammer/samples/` make the same
core calls as `Histogrammer/config/samples_v15.py`, no ROOT), the old Plotter names
(`Tests/Histogrammer/compat`: every alias shim, changelog §24), the control-histogram file
(`Tests/Histogrammer/controlhists`, `Tests/Plotter/draw`, `Tests/Utilities/test_histfile.py`), the move check (`Tests/tools`), the harness and ROOT serializer checks, every normal case, and `bbb check` in
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

Two assertion-based normal cases check numerical correctness independently of BBB
snapshots:

```bash
python3 Tests/run.py normal --case pico.chunking
python3 Tests/run.py normal --case plotter.histogram_correctness
```

`pico.chunking` uses cached counts and rejects file reads while checking event
coverage, job limits and totals (including already-split inputs).
`plotter.histogram_correctness` calls the production Sample API on nine local
events and compares weighted contents, squared errors, bin edges, flow bins,
normalization and empty selections with hand-calculated values. Both use the
normal harness's isolated workspace and declared ROOT/NumPy/future dependencies;
they require no BBB lock. A failed assertion is reported as a failure without
changing production code or expectations.

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
- Histogrammer (the former Plotter; the case names keep `plotter.`) selection/context metadata, weighted 1D/2D histograms, normalization,
  flow bins, merging, splitting, DY stitching, QCD OS/SS estimation, and C++ unrolling.
- `plot.py`'s path to drawn stacks (`plotter.stack`): since changelog §24 S3 through the control-histogram file
  (Histogrammer writes, Plotter reads and draws), compared with the canvases locked from memory.
- Histogrammer sample sets (`plotter.sample_model`): the core calls of `getsampleset` for
  every era, channel kind and caller option (recorded, no sample is built).
- PicoProducer branch schema, defaults, aliases, fixed/variable arrays, 64-bit
  event IDs, cutflow, NanoAODTools selection/range bookkeeping, and synthetic SF lookup.
- Fitter nominal/systematic shape names, negative-bin sanitation, adaptive
  rebinning, and non-ZTT subtraction.
- `createinputsTES.py` end to end (`histogrammer.tes_inputs`, changelog §25): a mini
  config and sample model on tuples of 100 copies of the fixture rows (`dm_2` cycling
  over 0, 1, 10, 11) plus variation tuples (`_TES*`, `_LTF*`, `m_vis` scaled), run serially in its own interpreter
  (`BBB/pico_entry.py`); the shape file, the rebinned file (TCanvas/TStyle by key and
  class only) and the names of the control plots. The script path comes from
  `_tes_inputs_script()`, the one line that changes when the script moves. To try
  the case alone before a lock: `python3 Tests/support/launch.py bbb
  histogrammer.tes_inputs <empty dir> <empty dir>/result.json`.

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
behavior these baselines record are listed in `docs/PicoProducer/BUGS.md`.

## Small validation commands

### Import boundaries (offline, no ROOT)

```bash
# Repository boundary assertion plus synthetic detector self-tests:
python Tests/run.py checks --case check_import_boundaries

# Detector self-tests only; these should pass even while production debt remains:
python Tests/check_import_boundaries.py DetectorTests -q
```

`check_import_boundaries` is included in `checks`, `all`, and the catalog-driven
testing menu. It uses only the Python standard library and runs on Windows with
Python 3.9 or newer. It reads source with AST/tokenize; it never imports TauFW or
ROOT. It scans PicoProducer, Histogrammer, Plotter, Fitter, Framework, Utilities, and common,
excluding `Legacy/`, `legacy/`, `LegacyAnalyses/`, and `Tests/`. Tau_Trigger_SF
does not have a registered TauFW package layout in this checkout.

Stages may import themselves and the libraries. Framework may import exactly
`TauFW.PicoProducer.api`, `TauFW.Histogrammer.api`, `TauFW.Plotter.api`, and `TauFW.Fitter.api`; deeper
Framework imports fail. Absolute `config.*`, `plot.*`, and `sample.*` stage
imports fail when the complete module has no local match beside the source file.
The report names the target stage when exactly one other stage contains a match.

**Current failure is expected:** the 2026-10-14 baseline has 24 import occurrences,
22 file/module pairs, and 20 files. Fitter -> Plotter accounts for 20 occurrences
in 17 files; PicoProducer -> Plotter for two in two files; Plotter -> PicoProducer
for two in one file. `import_boundary_allowlist.json` classifies known debt and
records a reason/roadmap step per exact file/module pair; **known entries still
fail**. New violations are marked `NEW`. Remove entries as violations are fixed:
entries with no remaining violation fail as `STALE`. No automatic inventory
regeneration or production fixes are performed by this check.

Nine Python 2 files have explicit `unparseable` exemptions in the same inventory.
Full-file parse errors are always reported separately, and tokenizer extraction
plus AST parsing of complete import statements still checks their imports,
including multiline/function-level imports. Unapproved parse errors, recovery
errors, duplicate/malformed inventory entries, and stale parse exemptions fail.
Remove a parse exemption when its file becomes parseable or is removed.

### Move check (offline, no ROOT)

```bash
# Moved files may only change import lines (and lines matching --allow); lists the functions whose AST differs:
python Tests/tools/move_check.py OLD=NEW [OLD=NEW ...] [--ref HEAD] [--allow REGEX]
python Tests/run.py checks --case unit.tools          # its unit tests
```

`Tests/tools/roundtrip_spike.py` (lxplus, ROOT) is a one-off feasibility check of CL §24: it draws the BBB
fixtures from memory and from a histogram file and compares the canvases and PNG files.

### Existing offline and ROOT checks

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
