"""Private XRootD/GFAL commands; no site detection or environment mutation."""

import errno
from pathlib import Path
import re
import stat
import subprocess
from typing import Optional

from .commands import run_command
from .locations import Kind, child_location, local_transfer_url, remote_scheme, root_endpoint_and_path

# =============================================================================
# ============================== COMMAND BUILDING =============================

def root_command(location: str, command: str, *options: str) -> list[str]:
    endpoint, path = root_endpoint_and_path(location)
    return ["xrdfs", endpoint, command, *options, path]


def _fs_command(location: str, xrdfs_command: str, gfal_tool: str, *options: str) -> list[str]:
    """Build the xrdfs command for root:// locations and the GFAL tool otherwise."""
    if remote_scheme(location) == "root":
        return root_command(location, xrdfs_command, *options)
    return [gfal_tool, *options, location]


# =============================================================================
# ================================== QUERIES ==================================

_XROOTD_NOT_FOUND = "[3011]"
_GFAL_NOT_FOUND = re.compile(r"\bNo such file or directory\b", re.IGNORECASE)
_TRANSPORT_PROBLEM = re.compile(
    r"permission denied|authentication|credential|certificate|SSL|connection|timed out|plugin", re.IGNORECASE,
)


def _confirms_missing(scheme: str, error: subprocess.CalledProcessError) -> bool:
    """A generic nonzero return code is not evidence that the file is missing."""
    diagnostic = (error.stderr or "") + "\n" + (error.output or "")
    if _TRANSPORT_PROBLEM.search(diagnostic):
        return False
    if scheme == "root":
        return _XROOTD_NOT_FOUND in diagnostic
    return error.returncode == errno.ENOENT and bool(_GFAL_NOT_FOUND.search(diagnostic))


def kind(location: str, timeout: Optional[float]) -> Optional[Kind]:
    scheme = remote_scheme(location)
    arguments = _fs_command(location, "stat", "gfal-stat")
    try:
        output = run_command(arguments, timeout).stdout
    except subprocess.CalledProcessError as error:
        if _confirms_missing(scheme, error):
            return None
        raise
    if scheme == "root":
        flags = re.search(r"^\s*Flags:\s*(.+)$", output, re.MULTILINE)
        if flags:
            return "directory" if "IsDir" in flags.group(1) else "file"
    else:
        permissions = re.search(r"Access:\s*\([^/]+/([d\-l])", output)
        if permissions:
            return {"d": "directory", "-": "file", "l": "link"}[permissions.group(1)]
    raise RuntimeError(f"Cannot determine file type from {arguments[0]} output for {location!r}: {output!r}")


def list_directory(location: str, timeout: Optional[float]) -> list[str]:
    output = run_command(_fs_command(location, "ls", "gfal-ls"), timeout).stdout
    lines = (line.rstrip("\r") for line in output.split("\n"))
    entries = [line for line in lines if line not in ("", ".", "..")]
    return sorted(child_location(location, entry) for entry in entries)


# =============================================================================
# ================================= MUTATIONS =================================

def make_directory(location: str, parents: bool, timeout: Optional[float]) -> None:
    options = ["-p"] if parents else []
    run_command(_fs_command(location, "mkdir", "gfal-mkdir", *options), timeout)


def copy_file(source: str, destination: str, overwrite: bool, timeout: Optional[float]) -> None:
    schemes = {remote_scheme(source), remote_scheme(destination)} - {""}
    if schemes == {"root"}:
        # Absolute local operands cannot be mistaken for command-line options.
        source_operand = source if remote_scheme(source) else str(Path(source).absolute())
        destination_operand = destination if remote_scheme(destination) else str(Path(destination).absolute())
        arguments = ["xrdcp", "--nopbar", *(["--force"] if overwrite else []),
                     source_operand, destination_operand]
    else:
        source_url = source if remote_scheme(source) else local_transfer_url(source)
        destination_url = destination if remote_scheme(destination) else local_transfer_url(destination)
        arguments = ["gfal-copy", *(["--force"] if overwrite else []), source_url, destination_url]
    run_command(arguments, timeout)


def remove_file(location: str, timeout: Optional[float]) -> None:
    run_command(_fs_command(location, "rm", "gfal-rm"), timeout)


def remove_directory(location: str, recursive: bool, timeout: Optional[float]) -> None:
    entries = list_directory(location, timeout)
    if entries and not recursive:
        raise OSError(errno.ENOTEMPTY, "Directory is not empty; pass recursive=True to remove its contents.", location)
    # Traverse ourselves so SRM child paths extend SFN, not the service/query URL.
    for entry in entries:
        entry_kind = kind(entry, timeout)
        if entry_kind == "directory":
            remove_directory(entry, True, timeout)
        elif entry_kind is not None:
            remove_file(entry, timeout)
    if remote_scheme(location) == "root":
        run_command(root_command(location, "rmdir"), timeout)
    else:
        # gfal-rm requires -r even for an empty directory; emptiness was checked above.
        run_command(["gfal-rm", "-r", location], timeout)


def set_permissions(location: str, permissions: int, timeout: Optional[float]) -> None:
    if remote_scheme(location) == "root":
        if permissions & 0o7000:
            raise ValueError("xrdfs chmod cannot express setuid, setgid, or sticky bits.")
        mode = stat.filemode(stat.S_IFREG | permissions)[1:]
        arguments = root_command(location, "chmod") + [mode]
    else:
        arguments = ["gfal-chmod", format(permissions, "o"), location]
    run_command(arguments, timeout)
