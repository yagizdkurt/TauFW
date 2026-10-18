# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Histogram files: named, ordered groups of ROOT histograms plus JSON metadata in one ROOT file.

    write_histfile(path, entries, meta)  ─▶ path of the written ROOT file (format below)
    read_histfile(path)                  ─▶ HistFile(meta, entries), the histograms detached from the file

Two modules that must not import each other exchange histograms through such a file: the Histogrammer writes the
histograms it filled, the Plotter reads and draws them (changelog §24). Both import only this format. What the
metadata *means* is their contract (docs/contracts/control-histograms.md); this module only stores it, unchanged.

Format 1:

    <file>.root
    ├── taufw_histfile      TNamed; its title is JSON {"format": 1, "meta": {...}, "entries": ["<path>", ...]}
    └── <path>/             one directory per entry (e.g. baseline/m_vis), listed in "entries" in their order
        ├── taufw_histfile  TNamed; its title is JSON {"groups": {"<group>": ["<histogram name>", ...]}, "meta": {...}}
        └── <histogram>     every histogram under its own name, with all its attributes (contents, errors,
                            colours, titles, statistics): the file holds exactly what was written

Order is never taken from the keys of a directory: "entries" and the group lists give it. Writing refuses what
could not be read back the same (a duplicate path or name, a histogram whose name is not its key, metadata that is
not plain JSON), so a file that was written is complete.

ROOT is imported only when a file is written or read: building and checking entries needs no ROOT.
"""
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

__all__ = ['write_histfile', 'read_histfile', 'HistFile', 'HistFileEntry', 'HistFileError', 'FORMAT']

FORMAT = 1                 # the layout written by this module; read_histfile refuses another one
HEADER = "taufw_histfile"  # the TNamed with the JSON header, in the file and in every entry directory


class HistFileError(Exception):
    """A histogram file that cannot be written or read as described in the module docstring."""


@dataclass
class HistFileEntry:
    """One directory of a histogram file.
    path:   where in the file, e.g. 'baseline/m_vis' (no leading or trailing '/')
    groups: {group name: [histograms]} in order, e.g. {'data': [h], 'exp': [h1, h2], 'sig': []}
    meta:   JSON-ready mapping, stored and returned unchanged"""
    path: str
    groups: Dict[str, List] = field(default_factory=dict)
    meta: Dict = field(default_factory=dict)

    def histograms(self):
        """All histograms of the entry, group after group, in order."""
        return [hist for hists in self.groups.values() for hist in hists]


@dataclass
class HistFile:
    """What read_histfile returns: the file's metadata and its entries in the order they were written."""
    meta: Dict
    entries: Tuple[HistFileEntry, ...]

    def entry(self, path):
        """The entry at `path` (KeyError if there is none)."""
        for entry in self.entries:
            if entry.path == path:
                return entry
        raise KeyError(path)


# =============================================================================
# ================================= WRITING ===================================


def write_histfile(path, entries, meta=None):
    """Write `entries` (HistFileEntry) and the file metadata `meta` to the ROOT file `path` (made, or replaced),
    making its directory if needed. Returns `path`. Checks everything first, so nothing is written for an invalid
    entry. The histograms are written as they are; they stay owned by the caller (their directory is unchanged).
    ROOT's current directory is the same after the call as before."""
    entries = list(entries)
    header = {"format": FORMAT, "meta": _json_ready(meta or {}, "file metadata"),
              "entries": _checked_paths(entries)}
    entry_headers = [{"groups": _checked_groups(entry), "meta": _json_ready(entry.meta, "metadata of " + entry.path)}
                     for entry in entries]
    import ROOT
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    previous = ROOT.gDirectory.GetPath()
    output = ROOT.TFile.Open(str(path), "RECREATE")
    if not output or output.IsZombie():
        raise HistFileError("cannot create %s" % (path))
    try:
        for entry, entry_header in zip(entries, entry_headers):
            folder = output.mkdir(entry.path, "", True)  # makes the intermediate directories too
            folder.cd()
            for hist in entry.histograms():
                hist.Write(hist.GetName())
            ROOT.TNamed(HEADER, json.dumps(entry_header)).Write()
        output.cd()
        ROOT.TNamed(HEADER, json.dumps(header)).Write()
    finally:
        output.Close()
        _change_directory(ROOT, previous)
    return path


def _checked_paths(entries):
    paths = []
    for entry in entries:
        if not isinstance(entry, HistFileEntry):
            raise HistFileError("an entry must be a HistFileEntry, got %r" % (entry,))
        path = entry.path
        if not isinstance(path, str) or not path or path.startswith('/') or path.endswith('/') or '//' in path \
                or path == HEADER:
            raise HistFileError("invalid entry path %r (e.g. 'baseline/m_vis')" % (path,))
        if path in paths:
            raise HistFileError("entry path %r used twice" % (path))
        paths.append(path)
    return paths


def _checked_groups(entry):
    groups, names = {}, set()
    for group, hists in entry.groups.items():
        if not isinstance(group, str) or not group:
            raise HistFileError("%s: invalid group name %r" % (entry.path, group))
        groups[group] = []
        for hist in hists:
            name = hist.GetName()
            if not name or '/' in name or name == HEADER:
                raise HistFileError("%s: invalid histogram name %r" % (entry.path, name))
            if name in names:
                raise HistFileError("%s: histogram name %r used twice (each is stored under its own name)"
                                    % (entry.path, name))
            names.add(name)
            groups[group].append(name)
    return groups


def _json_ready(value, what):
    """`value` if it is plain JSON (it is then read back equal), else HistFileError."""
    try:
        text = json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise HistFileError("%s is not plain JSON: %s" % (what, error))
    if json.loads(text) != value and not _equal_but_tuples(json.loads(text), value):
        raise HistFileError("%s does not read back equal from JSON" % (what))
    return value


def _equal_but_tuples(read, written):
    """True if `read` equals `written` once tuples are taken as lists (JSON has no tuples)."""
    if isinstance(written, tuple):
        written = list(written)
    if isinstance(written, dict) and isinstance(read, dict):
        return read.keys() == written.keys() and all(_equal_but_tuples(read[k], written[k]) for k in read)
    if isinstance(written, list) and isinstance(read, list):
        return len(read) == len(written) and all(_equal_but_tuples(r, w) for r, w in zip(read, written))
    return read == written


# =============================================================================
# ================================= READING ===================================


def read_histfile(path):
    """The HistFile in the ROOT file `path`: its metadata and entries, every histogram a detached copy (it stays
    valid after the file is closed; the caller owns it). Raises HistFileError for a file that is not a histogram
    file of FORMAT or misses a listed histogram. ROOT's current directory is the same after the call as before."""
    import ROOT
    previous = ROOT.gDirectory.GetPath()
    infile = ROOT.TFile.Open(str(path), "READ")
    if not infile or infile.IsZombie():
        _change_directory(ROOT, previous)
        raise HistFileError("cannot open %s" % (path))
    try:
        header = _header(infile, path)
        if header.get("format") != FORMAT:
            raise HistFileError("%s: format %r, this reader reads format %d" % (path, header.get("format"), FORMAT))
        entries = []
        for entry_path in header["entries"]:
            folder = infile.GetDirectory(entry_path)
            if not folder:
                raise HistFileError("%s: no directory %s" % (path, entry_path))
            entry_header = _header(folder, "%s:%s" % (path, entry_path))
            groups = {group: [_detached(folder, name, path, entry_path) for name in names]
                      for group, names in entry_header["groups"].items()}
            entries.append(HistFileEntry(entry_path, groups, entry_header["meta"]))
    finally:
        infile.Close()
        _change_directory(ROOT, previous)
    return HistFile(header["meta"], tuple(entries))


def _header(directory, where):
    named = directory.Get(HEADER)
    if not named:
        raise HistFileError("%s: no %s header (not a histogram file)" % (where, HEADER))
    try:
        return json.loads(named.GetTitle())
    except ValueError as error:
        raise HistFileError("%s: unreadable %s header: %s" % (where, HEADER, error))


def _detached(folder, name, path, entry_path):
    hist = folder.Get(name)
    if not hist:
        raise HistFileError("%s: no histogram %s in %s" % (path, name, entry_path))
    import ROOT
    status = ROOT.TH1.AddDirectoryStatus()
    ROOT.TH1.AddDirectory(False)  # the copy must not replace the read object in the file's directory
    try:
        copy = hist.Clone(name)
    finally:
        ROOT.TH1.AddDirectory(status)
    copy.SetDirectory(0)  # not owned by the file: it survives the file's Close()
    return copy


def _change_directory(ROOT, path):
    """Make `path` (a ROOT directory path, e.g. 'Rint:/') ROOT's current directory again; ROOT's top directory if
    it is gone."""
    directory = ROOT.gROOT.GetDirectory(path) if path else None
    (directory or ROOT.gROOT).cd()
