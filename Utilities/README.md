# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
# Utilities

Independent terminal, menu presentation, file I/O, process, numeric and installer helpers, and the drawing library
for CMS-style ROOT plots. Like the other TauFW packages, the source lives under `Utilities/python/`, and `scram b` exposes it as `TauFW.Utilities` after `cmsenv`.

```python
from TauFW.Utilities.CLI import CLI
from TauFW.Utilities.FIO import FileIO
from TauFW.Utilities.Math import float_range, partition
from TauFW.Utilities.Expressions import joincuts, joinweights
from TauFW.Utilities.Menu import ConsoleUI, MenuNavigation
from TauFW.Utilities.Process import Command, ParallelProcessor, ProcessRunner
from TauFW.Utilities.Drawing.Plot import Plot      # also Stack, Plot2D, CMSStyle, hist_tools, labels, SampleStyle
```

The package `__init__.py` files contain the public exports, so they are tracked despite the repository-wide `__init__.py` ignore rule meant for SCRAM-generated files (see the exception in `.gitignore`).

## Package boundaries

CLI and FIO each export one class; Menu exports `ConsoleUI` and `MenuNavigation`; Process exports `Command`, `CommandResult`, `ProcessRunner` and `ParallelProcessor`; Math exports plain functions (`_math.py`). `_cli.py`, `_file_io.py`, and `_menu.py` implement those entry points; CLI and FIO use `_internal/` for formatting, filesystem, serialization, command, transport and ROOT functions. Application code should import only the owning package's public class. Underscores and `__all__` document Python's private API convention; they do not prevent access to internal modules.

These packages do not import existing analysis/startup modules or Framework. Construction is silent and does not open files, change directories, read configuration or launch commands; only `ProcessRunner.run`/`run_all` and `ParallelProcessor.start` launch processes. There are no global utility instances, base classes or service registries. Pass instances explicitly to future framework components.
The drawing library is the exception; see [Drawing](#drawing-cms-style-root-plots).

## Installer helpers

`python/Installer` owns the Python operations used by `FastSetup.sh`: safe
directory renames, Python implementation/origin checks, native binding checks
and HTT ROOT-file verification. Its public helpers are `rename_directory`,
`verify_modules` and `verify_htt_files`. Imports are silent and do not load ROOT
or analysis packages until verification is requested.

FastSetup calls `python/Installer/setup_tools.py` directly before and after the
checkout moves, so these helpers work before `cmsenv` or `scram b`. Bash retains
the shell environment, Git downloads, installation sequencing and recovery state.
See [FastSetup](../docs/FastSetup.md#installer-and-menu-organization) for details.

## Terminal I/O

```python
terminal = CLI(verbosity=1)
terminal.print_header("Production summary")
terminal.print_message("Inputs discovered", minimum_verbosity=1)
terminal.print_table(["Sample", "Files"], [("DY", 12), ("TT", 4)])
terminal.update_progress(1, 2, "Processing")
terminal.update_progress(2, 2, "Finished")
terminal.print_warning("A sample was skipped")
```

`CLI(input_stream=None, output_stream=None, error_stream=None, verbosity=0, prefix=">>> ", use_color=None, progress_width=30)` uses the current standard streams when a stream is omitted. A supplied stream remains caller-owned. `use_color=None` detects terminal support; `True`/`False` explicitly override color selection.

| Method | Behavior |
|---|---|
| `print_message(message, minimum_verbosity=0)` | Write to stdout when verbosity reaches the threshold. |
| `print_warning(message)`, `print_error(message)` | Write to stderr regardless of verbosity; do not raise or exit. |
| `print_header(title)` | Write a section title to stdout. |
| `print_table(headers, rows)` | Align single-line cells; rows may be an iterator. Callers supply numeric precision through formatted values. |
| `update_progress(completed, total, message="")` | Maintain one stderr progress task. Require `total > 0` and `0 <= completed <= total`. Completion ends the line. |
| `finish_progress()` | Finish once; redirected output receives the last progress line without cursor controls. |
| `loading_bar(steps, width=steps, counter=False, remove=False, symbol="=", prefix=<CLI prefix>, append="", message="")` | Draw an in-place stdout bar and return it; call `bar.count(message="", steps=1)` once per step. The last step ends the line, writes `append`, or erases the bar (`remove`). Writes exactly what `TauFW.common.tools.LoadingBar` wrote (backspace redraws), which logs and BBB baselines rely on. |
| `table(row_format)`, `table(header_format, row_format, minimum_verbosity=0, underline=True)` | Return a `%`-format table for stdout, printed one row at a time: `print_header(*titles, suffix="")`, `print_row(*values)`; `header()`/`row()` return the lines (`save=True` keeps them for `print_rows()`). Without a header format, each column's title gets that column's width. Lines start with the CLI prefix and print only when the CLI verbosity reaches `minimum_verbosity`. A row with fewer values uses only the first columns; extra values are appended. Writes exactly what `TauFW.common.tools.Table` (and `LOG.table`) wrote, including the always-underlined header, which logs and BBB baselines rely on. |
| `read_input(prompt)` | Prompt on stderr and return input without its newline; EOF raises `EOFError`. |
| `confirm(prompt, default=False)` | Accept yes/no case-insensitively, retry invalid answers, and use the default for empty input. |

Interactive progress updates flush immediately and overwrite their line. Redirected intermediate progress is suppressed until completion or an explicit finish. Finish a partial task in `finally` if the surrounding operation can fail. Reporting and failure control are separate: application code raises its own exceptions. CLI does not parse arguments, launch general processes or persist messages to files.

Code moved here from `common/python/tools` keeps its old output byte for byte (and `Math` its old results). Those old output formats sit in a separate `# ===== BACKWARD COMPATIBILITY, CLEANUP =====` section of the module (`CLI/_internal/loading_bar.py`, `Process/_parallel.py`), or `# ===== LEGACY, CLEAN UP LATER =====` (`CLI/_internal/table.py`), so they can be modernized later in their own commit, with a BBB re-lock where baselines record them.

## Menu presentation

`TauFW.Utilities.Menu` exports `ConsoleUI` and `MenuNavigation`. Change terminal appearance, screen
wording, option labels, keyboard handling, and menu messages in
`python/Menu/_menu.py`. Edit the ordered help topics and explanations in
`python/Menu/faq.py`. The pre-install FastSetup checklist launches through
`python/Menu/setup_menu.py` and uses `ConsoleUI.setup_checklist()`; installation
sequencing remains in Bash. Space/Enter toggles components and activates Start install.
Shared ASCII branding and the current `V0.0` version live in
`python/Menu/banner.py`. Entry screens show their welcome messages beneath the
banner; smaller terminals use compact branding so controls remain visible.
Change screen transitions, back behavior, refresh loops,
and operation recovery in `python/Menu/_navigation.py`. Source section banners
group the related responsibilities.

`ConsoleUI.open(parser)` lazily loads curses on an interactive Linux terminal.
It returns a UI, or `None` after explaining the failure and showing CLI help.
Each screen uses its own `curses.wrapper` session, restoring the terminal before
Framework operations print output or wait for jobs.

Application screens return named actions: `main_menu()` returns `start`,
`continue`, `inspect`, `tests`, `help`, or `exit`; recipe confirmation, status, and run
continuation return their corresponding action or `back`. Recipe/run selectors
return `(action, index)`, with `select` identifying a supplied item and `manual`
or `back` carrying `None`. Path and polling prompts return text or `None` on Esc.
Run selectors accept `(run_id, state, updated)` summaries; `state=None` marks an
unreadable run. Framework retains the records and paths behind those summaries.

Discovery, validation, record access, callback arguments, and command dispatch
stay in `Framework/python/interactive.py`. Menu imports no Framework modules.
Workflow operations continue to use their existing CLI reporting.

Testing screens use `tests_menu()`, `test_family(title)`, and
`test_selection(title, items, review=False)`. Items contain `id`, `description`,
and `dependencies`; selection returns ordered IDs after Run or `None` on Back.
Navigation calls the supplied operations object's `test_catalog()` and
`execute_tests(family, cases)` methods. The Framework adapter owns catalog reads,
checkout paths and test subprocesses; Utilities imports no test modules.

`MenuNavigation(ui, operations)` owns the user journey and accepts an operations
object supplied by the caller. The object provides `launch_dir`, `recipes()`
(sorted recipe Paths), `runs()` (sorted `(created, path, summary)` rows),
`resolve_path(value)`, `load_run(path)`, `can_advance(record)`,
`validate_poll(value)` (positive integer or `ValueError`), and
`execute(command, **values)` (CLI return code). Records expose `run_id`,
`run_dir`, and `state`. Navigation handles command errors, interruptions, and
pauses; Framework supplies command defaults and decides whether a run can advance.

`Framework.interactive.Menu(...)` remains a construction entry point and returns
a `MenuNavigation` wired to Framework operations. Its `start()`, `inspect()`,
`continue_run()`, and `run()` methods now live in Utilities/Menu.

## File I/O

```python
files = FileIO(timeout=300)
files.make_directory("output")
files.write_json("output/run.json", {"era": "2025", "channel": "mutau"})
settings = files.read_json("output/run.json")
files.write_json("output/run.json.gz", settings)
files.write_lines("output/inputs.txt", ["sample-a.root", "sample-b.root"])
```

`FileIO(timeout=300, temporary_directory=None)` bounds each external command in seconds. `timeout=None` disables that bound. An optional temporary directory must already exist and be local. All operations accept strings or text `PathLike` objects. Plain paths remain local, including `/eos`, `/pnfs` and `/store` paths. There is no user/host/site guessing, environment expansion or implicit working-directory change.

| Methods | Inputs and results |
|---|---|
| `read_text`, `write_text`, `append_text` | UTF-8 by default; `encoding` is configurable. Text methods decompress/compress `.gz` suffixes. Append is local only and may create a file. |
| `read_bytes`, `write_bytes` | Stored bytes exactly; gzip headers are preserved and no compression is inferred. |
| `read_lines`, `write_lines` | Read a list without terminators; write one newline-terminated line per item. Input items must not contain newlines. |
| `read_json`, `write_json` | Ordinary Python values. JSON writes use Unicode and two-space indentation by default; `indent` and `sort_keys` are configurable. |
| `read_yaml`, `write_yaml` | Safe YAML loading/dumping; require PyYAML only when called. |
| `read_csv`, `write_csv` | Lists/iterators of rows. Reads return strings and retain any header row; `delimiter` defaults to a comma. |
| `exists(location)` | Return `False` only for confirmed absence. Permission, tool and transport failures propagate. |
| `list_directory(location, pattern="*")` | Sorted direct child locations, including directories, filtered by basename. |
| `expand_paths(patterns)` | Local globs and remote basename globs; input order is retained and each glob result is sorted. Literal paths are retained without checking existence; unmatched globs yield no entries. |
| `make_directory(location, parents=True, exist_ok=True)` | Explicit directory creation. File writers never create parent directories. |
| `copy_file`, `move_file` | One source file and an explicit destination filename. `overwrite=False` by default. A remote move copies successfully before deleting the source. |
| `remove_file(location, missing_ok=False)` | Remove a file or local symlink without traversing directories. |
| `remove_directory(location, recursive=False, missing_ok=False)` | Refuse nonempty directories unless recursion is explicit. Local directory symlinks must be removed with `remove_file`. |
| `set_permissions(location, permissions)` | Integer mode, such as `0o755`. XRootD cannot express setuid, setgid or sticky bits through its chmod command; these raise `ValueError`. |
| `write_template(template_location, destination, substitutions=None, excluded_lines=(), appended_lines=(), overwrite=False)` | Replace `$NAME`/`${NAME}` literally, preserve unknown tokens, remove lines containing excluded substrings, and append newline-terminated lines. |

All `write_*` content methods refuse existing files unless `overwrite=True` is supplied. Reads never create or repair files. Malformed formats raise their parser's normal exception. Local exclusive creation prevents accidental replacement; remote prechecks and cross-endpoint moves are not atomic transactions. Failed remote deletion after a successful move leaves both copies. FileIO does not print diagnostics or route terminal messages.

## Explicit remote URLs

```python
remote_file = "root://storage.example//store/user/analysis/run.json.gz"
settings = files.read_json(remote_file)
files.copy_file("output/run.json.gz", remote_file, overwrite=True)
```

Supported schemes are `root://`, `gsiftp://` and `srm://`. Supply actual endpoints and existing credentials; FileIO does not install tools, acquire credentials, infer sites or rewrite environment variables. `file://` is used internally for GFAL's local operands; public local inputs are plain paths.

- XRootD metadata uses `xrdfs`; transfers involving only local/XRootD locations use `xrdcp`.
- GridFTP/SRM metadata uses `gfal-stat`, `gfal-ls`, `gfal-mkdir`, `gfal-rm` and `gfal-chmod`. Transfers involving these protocols use `gfal-copy` with the corresponding protocol plugins.
- Commands use argument lists with `shell=False`. Captured output, command and exit status are retained in `subprocess.CalledProcessError`; timeouts raise `subprocess.TimeoutExpired`. Missing executables raise `FileNotFoundError`.
- URLs retain their authority, XRootD double slash and query parameters. SRM service URLs use the `SFN` value as the logical filename, including for gzip detection, child listings and wildcard expansion. Remote wildcards are limited to the final path component. Remote listings assume newline-free names.
- Remote content is downloaded into temporary files. Successful writes upload afterward; failures clean staging. Remote appending raises `NotImplementedError`. Large arbitrary byte/text reads materialize their contents; native ROOT reads over XRootD stream directly.

Transport references: [XRootD manuals](https://xrootd.org/docs.html) and [CERN GFAL utilities](https://github.com/cern-fts/gfal2-util).

## ROOT ownership and merging

```python
histogram = files.read_root_histogram("input.root", "cutflow")
files.write_root_objects("summary.root", {"analysis/cutflow": histogram})

with files.open_root_file("input.root") as root_file:
    tree = root_file.Get("Events")
    # Consume the tree here, while its file is open.
```

PyROOT is imported only for ROOT operations. `open_root_file(location, mode="READ", compression=None)` closes its native `TFile` on normal exit and exceptions, rejects null/zombie files, and restores ROOT's current directory. Handles and objects still owned by the file must not escape the context. `read_root_histogram` returns a cloned TH1-derived histogram detached from its source file.

`write_root_objects(location, objects, mode="NEW", compression=None)` accepts a mapping of relative object keys to caller-owned ROOT objects. Nested keys create ROOT directories. Names cannot contain empty, `.` or `..` components. `NEW`/`CREATE` refuses replacement; explicitly select `RECREATE` or `UPDATE` to replace a file or update its keys. Compression accepts a level from 0–9 or an algorithm/level such as `LZMA:9`; algorithms are ZLIB, LZMA, LZ4 and ZSTD.

XRootD `READ` handles stream directly. Other remote ROOT reads are staged; writable remote ROOT files are staged, closed, and uploaded only after successful context exit. `UPDATE` first downloads an existing file; a missing destination creates a new one. Callers own object contents, tree branches, schema decisions and keys.

`merge_root_files(sources, destination, overwrite=False, merge_command=("hadd",))` stages its output before copying it to the destination. XRootD inputs can stream; other remote inputs are downloaded. Supply an argument sequence such as `("python3", "/path/to/haddnano.py")` for an alternative merger. Merging does not import PyROOT. A successful command must produce its output file, but scientific integrity, event counts, input compatibility and workflow cleanup remain domain-owned.

## External commands

```python
runner = ProcessRunner()
command = Command("shapes 2025", ("python3", "TauES/createinputsTES.py", "-y", "2025"),
                  cwd="/path/to/Fitter", expects=("input_pt_less_region/*/*/*.root",), timeout=None)
results = runner.run_all([command], logdir="taufw_runs/<run>/histograms")
results[-1].ok, results[-1].log, results[-1].missing
```

`ProcessRunner(execute=None, clock=time.time, env=None)` runs each `Command(label, argv, cwd, expects=(), timeout=None)` without a shell. Standard output and errors go to one log file per command (`NN_<label>.log` under `logdir`), framed by a header (cwd, command line, start time) and a footer (exit code, duration, missing outputs). `PYTHONUNBUFFERED=1` keeps Python output in order; `env` adds variables.

A `CommandResult` is `ok` only when the exit code is 0 **and** every `expects` glob (relative to `cwd`) matches a file modified after the command started. Many analysis scripts call tools through `os.system` and exit 0 when those tools fail, and output trees are shared between runs, so neither the exit code nor an old file is trusted. A timeout gives returncode -1, a missing program 127. `run_all` stops after the first result that is not ok and calls `progress(index, total, command, result)` before (result `None`) and after each command. `execute(argv, cwd, stream, timeout, env) -> returncode` can be injected; tests pass a fake.

## Parallel Python calls

```python
processor = ParallelProcessor(max_parallel=4)
for index, subset in enumerate(chunks):
    processor.start(count_events, subset, name="chunk_%d" % index)
for handle in processor:          # in start order
    results = handle.join()       # the return value of count_events(subset)
```

`ParallelProcessor(name="nameless", max_parallel=-1, verbose=False)` replaces `TauFW.common.tools.parallel.MultiProcessor` with the same logic. `start(target, args=(), kwargs=None, name=None, verbose=False, parallel=True, kwret=None)` runs `target(*args, **kwargs)` in a `multiprocessing.Process` and sends its return value back through a pipe; a non-tuple `args` is one argument. At most `max_parallel` calls run at once (< 1: no limit); later ones are queued and start while the handles are iterated. `parallel=False` calls the target at once in this process. `kwret` names a keyword argument whose final value is returned too; `handle.join(**{kwret: dict_or_list})` merges it. `close()` closes the finished processes. The target must be picklable under the `spawn` start method (Windows, macOS); PicoProducer passes nested functions, which needs `fork` (Linux up to Python 3.13). Importing the module starts nothing (the old module started a `multiprocessing.Manager` on import).

## Numeric helpers

```python
from TauFW.Utilities.Math import float_range, partition, partition_by_sum

bins = [0, 0.4, 1.0] + float_range(1.2, 3.01, 0.2) + [4.0]
chunks = partition(files, parts=4)                  # 4 chunks, sizes differ by at most 1
groups = partition_by_sum([2, 3, 4, 5, 1], 6)       # [[5, 1], [4, 2], [3]]
```

`TauFW.Utilities.Math` replaces `TauFW.common.tools.math` with the same results for the same inputs. These are plain functions; none prints, reads files or keeps state.

| Function | Result |
|---|---|
| `float_range(start, end, step, scale=1000)` | `start` (kept as given), then `start + i*step` while below `end`. Each value is computed from `start`, so rounding errors do not add up. Was `frange`. |
| `partition(items, parts=None, max_size=None)` | `parts` chunks as evenly sized as possible, earlier chunks taking the remainder (7 items in 3 parts: sizes 3, 2, 2); chunks can be empty. `max_size` instead picks the fewest parts that keep each chunk at most that long. Neither given: `ValueError`. Was `partition(mylist, nparts, nmax)`. |
| `partition_by_sum(values, maximum)` | Groups with sum ≤ `maximum`, largest values first; a value above `maximum` gets its own group. The input list is not changed. Was `partition_by_max`, which sorted its input in place. |
| `columnize(items, columns=2)` | Reorders items so a row-by-row layout (a `TLegend`) reads column by column: `[1..7]` → `[1,5,2,6,3,7,4]`. Fewer than 2 columns returns `items` itself. Was `columnize(oldlist, ncol)`. |
| `magnitude(x)` | Rough order of magnitude for log-axis ranges: digits before the decimal point for `x ≥ 1` (45 → 2, 10 → 2), `floor(log10(x))` below 1 (0.84 → -1); 0 → 0. |
| `scale_vector(start, end, ratio, log=False)` | `start + ratio*(end-start)`; with `log`, `start*10**abs(ratio*log10(end/start))`, which needs nonzero `start` and `end` of the same sign (else `ValueError`). Was `scalevec`. |
| `relative_difference(x, y)` | `abs(x-y)/x`; for `x == 0`: 0 if `y == 0`, else -1. Was `reldiff`. |

`ceil` and `log10` are no longer re-exported; callers import them from the standard `math` module.

## ROOT selection and weight expressions

```python
from TauFW.Utilities.Expressions import joincuts, joinweights

joincuts("pt_1>20", "q_1*q_2<0", weight="genweight")   # "(pt_1>20 && q_1*q_2<0)*genweight"
joinweights("puweight", 1, "idweight")                 # "puweight*idweight"
```

String helpers for the C++ expressions that `TTree::Draw` and RDataFrame `Filter`/`Define` accept. They know the
syntax (`&&`, `||`, `*` between weights), not TauFW branch names; the helpers that do (`shift`, `shiftjme`,
`invertcharge`) stay in `TauFW.Plotter.plot.string`. Moved verbatim from there in October 2026 (changelog section 21);
the Plotter imports these names from here. ROOT is not imported. Warnings go through the drawing logger
(`TauFW.Utilities.Drawing.LOG`), the same object as before.

| Function | Result |
|---|---|
| `joincuts(*cuts, weight=False)` | Non-empty string cuts joined with ` && `; a cut with `\|\|` and no parentheses is bracketed (with a warning). With `weight`: `(cuts)*weight`, the weight bracketed if it has comparison or `+`/`-`/`&`/`\|` outside parentheses. |
| `joinweights(*weights)` | Strings and numbers joined with `*`; `1` and empty values are dropped, `*/` becomes `/`. |
| `replacepattern(string, patterns)` | Replaces `(old, new)` or `(old, new, regexp)` in a product of weights, then removes doubled or outer `*`. |
| `cleanbool(string)` | Collapses doubled `&&`/`\|\|` to `&&` and strips outer `&&`. |
| `getselstr(selection)` | `selection.selection` for a Plotter `Selection`, else the argument itself. |

Known latent bugs, kept as they were (Plotter [BUGS](../docs/Plotter/BUGS.md) L05-L07): `joinweights` with a weight
`0` raises `TypeError` while formatting its warning; `replacepattern` with several patterns applies only the last;
`joincuts` does not bracket a cut like `(x)||y`, so `&&` binds first.

## Drawing: CMS-style ROOT plots

```python
from TauFW.Utilities.Drawing import LOG
from TauFW.Utilities.Drawing.Stack import Stack
from TauFW.Utilities.Drawing.hist_tools import grouphists
import TauFW.Utilities.Drawing.CMSStyle as CMSStyle

CMSStyle.setCMSEra(2018)
plot = Stack("m_{vis} [GeV]", datahist, [ztt, top, ewk], [signal])  # a string or a Plotter Variable as x axis
plot.draw(ratio=True, staterr=True)
plot.drawlegend(position="right")
plot.saveas("plots/m_vis.png", "plots/m_vis.pdf")
```

The drawing code of the Plotter, moved here in October 2026 (changelog section 18) so that every module can draw
without importing the Plotter. It moved **as it was**: the drawn canvases, styles and printed output are the same,
checked by the BBB case `drawing.canvas`. Modernizing it (style, splitting `Plot.py`) is listed in
[TODO.md](../docs/Refactor-2025/TODO.md).

| Module | Contents | Was |
|---|---|---|
| `Plot`, `Plot2D`, `Stack`, `Ratio` | Canvases: histogram comparison, 2D, data/MC stack, ratio panel | `TauFW.Plotter.plot.*` |
| `CMSStyle` | CMS/lumi labels per era, TDR style | `TauFW.Plotter.plot.CMSStyle` |
| `SampleStyle` | Default colors and titles of processes (`getcolor`, `sample_colors`, ...) | `TauFW.Plotter.sample.SampleStyle` |
| `hist_tools` | ROOT histogram helpers: `normalize`, `grouphists`, `gethistratio`, `geterrorband`, `addoverflow`, `deletehist`, ... | `TauFW.Plotter.plot.utils` |
| `labels` | `makelatex`, `maketitle`, `makehistname`, `makefilename`, `estimatelen`, `match`, `var_dict` | first half of `TauFW.Plotter.plot.string` |
| package | `LOG`, the drawing logger (`Logger('Plot')`) | `TauFW.Plotter.plot.utils.LOG` |

Unlike the other Utilities packages, Drawing needs ROOT, and it keeps the old behavior that callers rely on:
importing it sets ROOT batch mode, replaces `TNamed.__repr__` (`<TH1D('name','title') at 0x...>` in logs), adds
`SetOption`/`GetOption` to ROOT's `TGraph`, and importing `Plot` applies the
TDR style to `gStyle`. `CMSStyle` and `SampleStyle` hold module-level state (the lumi text, the color tables), so
import them only from here, never from a copy. `LOG` and `SampleStyle.LOG` are the same objects the Plotter uses
(`TauFW.Plotter.plot.*` and `TauFW.Plotter.sample.utils` import them), so `LOG.verbosity = 2` in a script sets the
verbosity of both. The library never imports the Plotter: a plot's variable is a string or any object with the
attributes of the Plotter's `Variable` (`getedge`, `dividebins`, `binlabels`, ranges, titles). The old logger and five
small helpers are verbatim copies in `Drawing/_internal/` (Utilities does not import `TauFW.common`).

## Inventory and validation

[IOInventory.md](IOInventory.md) maps existing source responsibilities and I/O sites to these APIs without connecting them. Regenerate it through a static scan:

```bash
python Utilities/_audit_io.py
python -m unittest discover -s Tests/Utilities -v
```

The focused tests use temporary files and mocked remote/ROOT operations. They cover silent imports, Python 3.9 syntax, terminal behavior, format round trips, overwrite/removal options, remote failures/URL preservation/staging cleanup, and ROOT ownership. Real remote services and PyROOT are not exercised by this suite; those integrations require their intended runtime and credentials. The tests import `TauFW.Utilities` from this checkout (`Tests/Utilities/checkout.py`), so they also run without CMSSW. Framework call-site migrations are deferred.
