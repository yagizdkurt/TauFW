"""One public file I/O class, independent of terminal and analysis modules."""

from contextlib import contextmanager
import fnmatch
import glob
import os
from pathlib import Path
import posixpath
from tempfile import TemporaryDirectory
from typing import Any, Iterable, Iterator, Literal, Mapping, Optional, Sequence, Union

from ._internal import commands, formats, local, remote, root
from ._internal.locations import (
    Kind, StrPath, location_name, logical_path, normalize, remote_scheme, replace_remote_path, same_location,
)

# How a remote location is staged: download it, upload a new file, replace an existing
# file, or download it when present and then replace it.
_Access = Literal["read", "create", "replace", "update"]
_ROOT_MODE_ACCESS: dict[str, _Access] = {"READ": "read", "NEW": "create", "RECREATE": "replace", "UPDATE": "update"}


class FileIO:
    """Read/write explicit locations without configuration, site, or physics policy."""

    # =========================================================================
    # ================================= SETUP =================================

    def __init__(self, timeout: Optional[float] = 300, temporary_directory: Optional[StrPath] = None) -> None:
        """timeout bounds each external command; None disables that bound."""
        if timeout is not None and timeout <= 0:
            raise ValueError("timeout must be positive or None.")
        self._timeout = timeout
        self._temporary_directory = None if temporary_directory is None else os.fspath(temporary_directory)

    # =========================================================================
    # =========================== INTERNAL HELPERS ============================

    def _kind(self, location: str) -> Optional[Kind]:
        return remote.kind(location, self._timeout) if remote_scheme(location) else local.kind(location)

    def _require(self, location: str, expected: Literal["file", "directory"], missing_ok: bool = False) -> bool:
        """Raise unless location exists as expected; return False instead when it is absent and missing_ok."""
        kind = self._kind(location)
        if kind is None:
            if missing_ok:
                return False
            raise FileNotFoundError(location)
        if expected == "directory" and kind != "directory":
            raise NotADirectoryError(location)
        if expected == "file" and kind == "directory":
            raise IsADirectoryError(location)
        return True

    def _check_destination(self, destination: str, overwrite: bool) -> Optional[Kind]:
        """Refuse a directory, or an existing file without overwrite; return what currently exists."""
        kind = self._kind(destination)
        if kind == "directory":
            raise IsADirectoryError(destination)
        if kind is not None and not overwrite:
            raise FileExistsError(destination)
        return kind

    @contextmanager
    def _staged_local_copy(self, location: str, access: _Access = "read") -> Iterator[str]:
        """Yield a local path for location; local paths pass through unchanged.

        Remote content is staged in a temporary directory. Writing access uploads only after
        a successful caller exit; update also downloads existing content first.
        """
        if not remote_scheme(location):
            yield location
            return
        writing = access != "read"
        overwrite = access in ("replace", "update")
        existing_kind = self._check_destination(location, overwrite) if writing else None
        with TemporaryDirectory(dir=self._temporary_directory, prefix="taufw-fio-") as staging:
            # Remote names never become local path components; retain only gzip behavior.
            staged_name = "content.gz" if logical_path(location).endswith(".gz") else "content"
            staged_file = str(Path(staging) / staged_name)
            if not writing or (access == "update" and existing_kind is not None):
                remote.copy_file(location, staged_file, False, self._timeout)
            yield staged_file
            if writing:
                remote.copy_file(staged_file, location, overwrite, self._timeout)

    # =========================================================================
    # ============================ TEXT AND BYTES =============================

    def read_text(self, location: StrPath, encoding: str = "utf-8") -> str:
        """Read text, decompressing a .gz suffix; remote content is staged locally."""
        with self._staged_local_copy(normalize(location)) as local_file:
            with local.open_text(local_file, "r", encoding) as input_file:
                return input_file.read()

    def write_text(self, location: StrPath, text: str, *, overwrite: bool = False, encoding: str = "utf-8") -> None:
        """Write text exclusively by default; .gz selects gzip compression."""
        access = "replace" if overwrite else "create"
        with self._staged_local_copy(normalize(location), access) as local_file:
            with local.open_text(local_file, "w" if overwrite else "x", encoding) as output_file:
                output_file.write(text)

    def append_text(self, location: StrPath, text: str, encoding: str = "utf-8") -> None:
        """Append to a local text/gzip file, creating the file if necessary."""
        location = normalize(location)
        if remote_scheme(location):
            raise NotImplementedError("Remote text appending is unsupported; read and explicitly replace instead.")
        with local.open_text(location, "a", encoding) as output_file:
            output_file.write(text)

    def read_bytes(self, location: StrPath) -> bytes:
        """Read stored bytes exactly, including gzip headers when present."""
        with self._staged_local_copy(normalize(location)) as local_file:
            return Path(local_file).read_bytes()

    def write_bytes(self, location: StrPath, content: bytes, *, overwrite: bool = False) -> None:
        """Write stored bytes exactly; no automatic compression is applied."""
        access = "replace" if overwrite else "create"
        with self._staged_local_copy(normalize(location), access) as local_file:
            with open(local_file, "wb" if overwrite else "xb") as output_file:
                output_file.write(content)

    def read_lines(self, location: StrPath, encoding: str = "utf-8") -> list[str]:
        """Return lines without their newline terminators."""
        return self.read_text(location, encoding).splitlines()

    def write_lines(self, location: StrPath, lines: Iterable[str], *, overwrite: bool = False,
                    encoding: str = "utf-8") -> None:
        """Write one newline-terminated line per item; items cannot contain newlines."""
        text = formats.join_lines(lines, "write_lines items")
        self.write_text(location, text, overwrite=overwrite, encoding=encoding)

    # =========================================================================
    # ========================== STRUCTURED FORMATS ===========================

    def read_json(self, location: StrPath) -> Any:
        return formats.read_json(self.read_text(location))

    def write_json(self, location: StrPath, value: Any, *, overwrite: bool = False,
                   indent: int = 2, sort_keys: bool = False) -> None:
        self.write_text(location, formats.write_json(value, indent, sort_keys), overwrite=overwrite)

    def read_yaml(self, location: StrPath) -> Any:
        return formats.read_yaml(self.read_text(location))

    def write_yaml(self, location: StrPath, value: Any, *, overwrite: bool = False) -> None:
        self.write_text(location, formats.write_yaml(value), overwrite=overwrite)

    def read_csv(self, location: StrPath, delimiter: str = ",") -> list[list[str]]:
        """Return rows of strings, including a header row when the file contains one."""
        return formats.read_csv(self.read_text(location), delimiter)

    def write_csv(self, location: StrPath, rows: Iterable[Sequence[object]], *, overwrite: bool = False,
                  delimiter: str = ",") -> None:
        self.write_text(location, formats.write_csv(rows, delimiter), overwrite=overwrite)

    # =========================================================================
    # ========================== FILESYSTEM QUERIES ===========================

    def exists(self, location: StrPath) -> bool:
        """False means confirmed absence; access and transport errors propagate."""
        return self._kind(normalize(location)) is not None

    def list_directory(self, location: StrPath, pattern: str = "*") -> list[str]:
        """Return sorted direct child locations, including directories, filtered by basename."""
        location = normalize(location)
        self._require(location, "directory")
        if remote_scheme(location):
            entries = remote.list_directory(location, self._timeout)
        else:
            entries = local.list_directory(location)
        # Both backends return sorted entries, so filtering keeps them sorted.
        return [entry for entry in entries if fnmatch.fnmatchcase(location_name(entry), pattern)]

    def expand_paths(self, patterns: Sequence[StrPath]) -> list[str]:
        """Expand local globs and remote basename globs, preserving input order."""
        if isinstance(patterns, (str, os.PathLike)):
            raise TypeError("Pass a sequence of paths, such as [pattern], to expand_paths.")
        paths = []
        for pattern in patterns:
            location = normalize(pattern)
            path = logical_path(location)
            if not glob.has_magic(path):
                paths.append(location)
            elif remote_scheme(location):
                directory, basename = posixpath.split(path)
                if glob.has_magic(directory):
                    raise ValueError("Remote wildcards are supported only in the final path component.")
                paths.extend(self.list_directory(replace_remote_path(location, directory), basename))
            else:
                paths.extend(local.expand_glob(location))
        return paths

    # =========================================================================
    # ========================== FILESYSTEM CHANGES ===========================

    def make_directory(self, location: StrPath, *, parents: bool = True, exist_ok: bool = True) -> None:
        """Create only the explicitly requested directory and, optionally, its parents."""
        location = normalize(location)
        if not remote_scheme(location):
            local.make_directory(location, parents, exist_ok)
        elif not self._require(location, "directory", missing_ok=True):
            remote.make_directory(location, parents, self._timeout)
        elif not exist_ok:
            raise FileExistsError(location)

    def copy_file(self, source: StrPath, destination: StrPath, *, overwrite: bool = False) -> None:
        """Copy one file to an explicit filename; never interpret destination as a directory."""
        source, destination = normalize(source), normalize(destination)
        self._require(source, "file")
        self._check_destination(destination, overwrite)
        if remote_scheme(source) or remote_scheme(destination):
            if same_location(source, destination):
                raise ValueError("Source and destination name the same remote file.")
            remote.copy_file(source, destination, overwrite, self._timeout)
        else:
            local.copy_file(source, destination, overwrite)

    def move_file(self, source: StrPath, destination: StrPath, *, overwrite: bool = False) -> None:
        """Remote moves copy then delete; a failed copy always preserves the source."""
        source, destination = normalize(source), normalize(destination)
        if remote_scheme(source) or remote_scheme(destination):
            self.copy_file(source, destination, overwrite=overwrite)
            self.remove_file(source)
        else:
            self._require(source, "file")
            self._check_destination(destination, overwrite)
            local.move_file(source, destination, overwrite)

    def remove_file(self, location: StrPath, *, missing_ok: bool = False) -> None:
        """Unlink a file or local symlink without deleting directories."""
        location = normalize(location)
        if not remote_scheme(location):
            local.remove_file(location, missing_ok)
        elif self._require(location, "file", missing_ok):
            remote.remove_file(location, self._timeout)

    def remove_directory(self, location: StrPath, *, recursive: bool = False, missing_ok: bool = False) -> None:
        """Remove a directory; deleting contents requires recursive=True."""
        location = normalize(location)
        if not remote_scheme(location):
            local.remove_directory(location, recursive, missing_ok)
        elif self._require(location, "directory", missing_ok):
            remote.remove_directory(location, recursive, self._timeout)

    def set_permissions(self, location: StrPath, permissions: int) -> None:
        """Apply an integer permission mode, such as 0o755; backend restrictions propagate."""
        if not isinstance(permissions, int) or not 0 <= permissions <= 0o7777:
            raise ValueError("permissions must be an integer from 0 through 0o7777.")
        location = normalize(location)
        if remote_scheme(location):
            remote.set_permissions(location, permissions, self._timeout)
        else:
            local.set_permissions(location, permissions)

    # =========================================================================
    # =============================== TEMPLATES ===============================

    def write_template(self, template_location: StrPath, destination: StrPath,
                       substitutions: Optional[Mapping[str, object]] = None,
                       excluded_lines: Sequence[str] = (), appended_lines: Iterable[str] = (), *,
                       overwrite: bool = False) -> None:
        """Replace $NAME/${NAME} literally; exclude lines containing the supplied substrings."""
        replacements = {} if substitutions is None else {key: str(value) for key, value in substitutions.items()}
        template = self.read_text(template_location)
        content = formats.render_template(template, replacements, excluded_lines, appended_lines)
        self.write_text(destination, content, overwrite=overwrite)

    # =========================================================================
    # ============================== ROOT FILES ===============================

    @contextmanager
    def open_root_file(self, location: StrPath, mode: str = "READ",
                       compression: Optional[Union[int, str]] = None) -> Iterator[Any]:
        """Yield a native TFile valid until exit; NEW refuses overwrite, RECREATE/UPDATE opt in."""
        location, mode = normalize(location), root.validate_mode(mode)
        # ROOT reads XRootD URLs directly, so only other remote reads and all remote writes are staged.
        if remote_scheme(location) == "root" and mode == "READ":
            with root.open_file(location, mode, compression) as root_file:
                yield root_file
            return
        with self._staged_local_copy(location, _ROOT_MODE_ACCESS[mode]) as local_file:
            with root.open_file(local_file, mode, compression) as root_file:
                yield root_file

    def read_root_histogram(self, location: StrPath, object_name: str) -> Any:
        """Return a cloned TH1/TH2/TH3 histogram detached from its closed source file."""
        with self.open_root_file(location) as root_file:
            return root.read_histogram(root_file, object_name)

    def write_root_objects(self, location: StrPath, objects: Mapping[str, object], *, mode: str = "NEW",
                           compression: Optional[Union[int, str]] = None) -> None:
        """Write caller-owned objects under explicit relative keys; NEW is the default."""
        mode = root.validate_mode(mode)
        if mode == "READ":
            raise ValueError("Writing ROOT objects requires NEW, RECREATE, or UPDATE mode.")
        root.validate_object_names(objects)
        with self.open_root_file(location, mode, compression) as root_file:
            root.write_objects(root_file, objects)

    def merge_root_files(self, sources: Sequence[StrPath], destination: StrPath, *, overwrite: bool = False,
                         merge_command: Sequence[str] = ("hadd",)) -> None:
        """Merge explicit inputs; success is command/file success, not scientific validation."""
        if isinstance(sources, (str, os.PathLike)) or not sources:
            raise ValueError("sources must be a nonempty sequence of file locations.")
        if isinstance(merge_command, str) or not merge_command:
            raise ValueError("merge_command must be a nonempty argument sequence.")
        sources = [normalize(source) for source in sources]
        destination = normalize(destination)
        for source in sources:
            self._require(source, "file")
            if same_location(source, destination):
                raise ValueError("A merge destination cannot also be an input.")
        self._check_destination(destination, overwrite)
        with TemporaryDirectory(dir=self._temporary_directory, prefix="taufw-merge-") as staging:
            inputs = []
            for index, source in enumerate(sources):
                scheme = remote_scheme(source)
                if not scheme:
                    inputs.append(str(Path(source).absolute()))
                elif scheme == "root":
                    # The merge command reads XRootD inputs directly.
                    inputs.append(source)
                else:
                    staged_input = str(Path(staging) / f"input-{index}.root")
                    remote.copy_file(source, staged_input, False, self._timeout)
                    inputs.append(staged_input)
            merged_file = str(Path(staging) / "merged.root")
            commands.run_command([*merge_command, merged_file, *inputs], self._timeout)
            if not Path(merged_file).is_file():
                raise OSError("Merge command succeeded without producing its output file.")
            self.copy_file(merged_file, destination, overwrite=overwrite)
