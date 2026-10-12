"""Separate local paths from explicit remote URLs without guessing sites."""

import os
from pathlib import Path
import posixpath
import re
from typing import Literal, Union
from urllib.parse import parse_qs, quote, urlsplit, urlunsplit

StrPath = Union[str, os.PathLike]
# What a stat reports for an existing location; remote GFAL listings can also report links.
Kind = Literal["file", "directory", "link"]

_URL_START = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
_XROOTD_DEFAULT_PORT = 1094


def normalize(location: StrPath) -> str:
    value = os.fspath(location)
    if not isinstance(value, str) or not value:
        raise ValueError("A location must be a nonempty string or text PathLike.")
    if _URL_START.match(value):
        parsed = urlsplit(value)
        if parsed.scheme not in ("root", "gsiftp", "srm"):
            raise ValueError(f"Unsupported remote URL scheme: {parsed.scheme!r}.")
        if not parsed.netloc or not parsed.path or parsed.fragment:
            raise ValueError("Remote URLs need an endpoint and path, without a fragment.")
        if parsed.scheme == "srm" and parsed.query and "SFN" not in parse_qs(parsed.query):
            raise ValueError("An SRM service URL with a query must include SFN.")
    return value


def remote_scheme(location: str) -> str:
    return urlsplit(location).scheme if _URL_START.match(location) else ""


def logical_path(location: str) -> str:
    if not remote_scheme(location):
        return location
    parsed = urlsplit(location)
    if parsed.scheme == "srm":
        return parse_qs(parsed.query).get("SFN", [parsed.path])[0]
    return parsed.path


def replace_remote_path(location: str, path: str) -> str:
    parsed = urlsplit(location)
    if parsed.scheme == "srm" and "SFN" in parse_qs(parsed.query):
        query = re.sub(r"(^|&)SFN=[^&]*", lambda match: match.group(1) + "SFN=" + quote(path, safe="/"), parsed.query)
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, ""))


def root_endpoint_and_path(location: str) -> tuple[str, str]:
    parsed = urlsplit(location)
    # root://host//store/file names /store/file in xrdfs's server-first syntax.
    path = parsed.path[1:] if parsed.path.startswith("//") else parsed.path
    if parsed.query:
        path += "?" + parsed.query
    return parsed.netloc, path


def child_location(directory: str, entry: str) -> str:
    """Rebuild listing entries while rejecting paths outside the requested directory."""
    parent = logical_path(directory).rstrip("/") or "/"
    if remote_scheme(entry):
        parsed_parent, parsed_child = urlsplit(directory), urlsplit(entry)
        if (parsed_child.scheme, parsed_child.netloc) != (parsed_parent.scheme, parsed_parent.netloc):
            raise ValueError("Remote listing returned an entry from another endpoint.")
        entry = logical_path(entry)
    if entry.startswith("/"):
        candidate = entry.rstrip("/")
    else:
        candidate = parent + "/" + entry.rstrip("/")
    # Normalize only for comparison; retain double slashes in the returned URL.
    canonical_parent = posixpath.normpath("/" + parent.lstrip("/"))
    canonical_candidate = posixpath.normpath("/" + candidate.lstrip("/"))
    if posixpath.dirname(canonical_candidate) != canonical_parent or canonical_candidate == canonical_parent:
        raise ValueError(f"Remote listing entry is not a direct child: {entry!r}.")
    basename = posixpath.basename(canonical_candidate)
    return replace_remote_path(directory, parent.rstrip("/") + "/" + basename)


def local_transfer_url(location: str) -> str:
    return Path(location).absolute().as_uri()


def location_name(location: str) -> str:
    if not remote_scheme(location):
        return Path(location).name
    return posixpath.basename(logical_path(location).rstrip("/")) or "file"


def same_location(first: str, second: str) -> bool:
    """Compare resolved local paths, or remote endpoints and paths; mixed pairs never match."""
    if remote_scheme(first) or remote_scheme(second):
        return _same_remote_file(first, second)
    return Path(first).resolve() == Path(second).resolve()


def _same_remote_file(first: str, second: str) -> bool:
    if not remote_scheme(first) or remote_scheme(first) != remote_scheme(second):
        return False
    first_url, second_url = urlsplit(first), urlsplit(second)
    default_port = _XROOTD_DEFAULT_PORT if first_url.scheme == "root" else None
    first_endpoint = (first_url.hostname, first_url.port or default_port)
    second_endpoint = (second_url.hostname, second_url.port or default_port)
    first_path = posixpath.normpath("/" + logical_path(first).lstrip("/"))
    second_path = posixpath.normpath("/" + logical_path(second).lstrip("/"))
    return first_endpoint == second_endpoint and first_path == second_path
