# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Detect user-installed Python packages that shadow the active CMSSW runtime."""
from importlib import metadata
from importlib.machinery import EXTENSION_SUFFIXES, PathFinder
import os
from pathlib import Path
import shlex
import sys

CVMFS_ROOT = Path("/cvmfs")


def _within(path, root):
    path = Path(path).resolve()
    return path == root or root in path.parents


def _modules(distribution):
    """Map import names to pip names, including wheels without top_level.txt."""
    names = set((distribution.read_text("top_level.txt") or "").split())
    for file in distribution.files or ():
        name = str(file).replace("\\", "/").split("/", 1)[0]
        for suffix in [".py"] + EXTENSION_SUFFIXES:
            if name.endswith(suffix):
                name = name[:-len(suffix)]
                break
        if name.isidentifier():
            names.add(name)
    return sorted(name for name in names if name.isidentifier())


def python_environment_warnings():
    """Return actionable warnings without importing optional/native packages.

    Only warn if removing ~/.local from the active import path exposes a
    CVMFS implementation. Extra user packages absent from CMSSW are allowed.
    """
    if not (os.environ.get("CMSSW_BASE") or os.environ.get("CMSSW_RELEASE_BASE")):
        return []
    local = (Path.home() / ".local").resolve()
    paths = [str(path) for path in sys.path]
    user_paths = [path for path in paths if _within(path, local)]
    if not user_paths:
        return []
    cms_paths = [path for path in paths if not _within(path, local)]
    warnings = []
    seen = set()
    for distribution in metadata.distributions(path=user_paths):
        package = distribution.metadata.get("Name")
        if not package:
            continue
        for name in _modules(distribution):
            loaded = sys.modules.get(name)
            spec = PathFinder.find_spec(name, paths) if loaded is None else None
            origin = getattr(loaded, "__file__", None) if loaded is not None else getattr(spec, "origin", None)
            if not origin or not _within(origin, local):
                continue
            provided = PathFinder.find_spec(name, cms_paths)
            cms_origin = getattr(provided, "origin", None)
            if not cms_origin or not _within(cms_origin, CVMFS_ROOT.resolve()):
                continue
            key = (package, name)
            if key in seen:
                continue
            seen.add(key)
            warnings.append("%s imports from %s instead of CMSSW's %s. Run: pip3 uninstall %s"
                            % (name, origin, cms_origin, shlex.quote(package)))
    return sorted(warnings)
