# Utilities

Independent terminal and file I/O packages for later framework integration. Like the other TauFW packages, the source lives under `Utilities/python/`, and `scram b` exposes it as `TauFW.Utilities` after `cmsenv`. Existing framework modules remain unchanged.

```python
from TauFW.Utilities.CLI import CLI
from TauFW.Utilities.FIO import FileIO
```

The package `__init__.py` files contain the public exports, so they are tracked despite the repository-wide `__init__.py` ignore rule meant for SCRAM-generated files (see the exception in `.gitignore`).

## Package boundaries

Each package exports one class. `_cli.py` and `_file_io.py` implement those entry points; `_internal/` contains formatting, filesystem, serialization, command, transport and ROOT functions. Application code should import only the owning package's public class. Underscores and `__all__` document Python's private API convention; they do not prevent access to internal modules.

Neither package imports the other or existing analysis/startup modules. Construction is silent and does not open files, change directories, read configuration or launch commands. There are no global utility instances, base classes or service registries. Pass instances explicitly to future framework components.

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
| `read_input(prompt)` | Prompt on stderr and return input without its newline; EOF raises `EOFError`. |
| `confirm(prompt, default=False)` | Accept yes/no case-insensitively, retry invalid answers, and use the default for empty input. |

Interactive progress updates flush immediately and overwrite their line. Redirected intermediate progress is suppressed until completion or an explicit finish. Finish a partial task in `finally` if the surrounding operation can fail. Reporting and failure control are separate: application code raises its own exceptions. CLI does not parse arguments, launch general processes or persist messages to files.

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

## Inventory and validation

[IOInventory.md](IOInventory.md) maps existing source responsibilities and I/O sites to these APIs without connecting them. Regenerate it through a static scan:

```bash
python Utilities/_audit_io.py
python -m unittest discover -s Tests/Utilities -v
```

The focused tests use temporary files and mocked remote/ROOT operations. They cover silent imports, Python 3.9 syntax, terminal behavior, format round trips, overwrite/removal options, remote failures/URL preservation/staging cleanup, and ROOT ownership. Real remote services and PyROOT are not exercised by this suite; those integrations require their intended runtime and credentials. The tests import `TauFW.Utilities` from this checkout (`Tests/Utilities/checkout.py`), so they also run without CMSSW. Framework call-site migrations are deferred.
