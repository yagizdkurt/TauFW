"""Lossless canonical snapshots; no tolerance, rounding, or opaque ROOT serialization."""
from array import array
import json
import numbers
import struct


def floating(value, bits=64):
    return {"float%d" % bits: struct.pack("<f" if bits == 32 else "<d", float(value)).hex()}


def exact(value):
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, numbers.Real):
        dtype = getattr(value, "dtype", None)
        if dtype is not None and dtype.itemsize not in (4, 8):
            raise TypeError("Unsupported floating-point dtype %s" % dtype)
        return floating(value, 32 if dtype is not None and dtype.itemsize == 4 else 64)
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("Snapshot mappings require string keys.")
        return {key: exact(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [exact(item) for item in value]
    raise TypeError("Unsupported snapshot value %s" % type(value).__name__)


def canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                       separators=(",", ":")) + "\n").encode("utf-8")


def difference(expected, actual, path="$", limit=12):
    """Focused paths, with missing and extra fields preserved as failures."""
    result = []

    def walk(left, right, location):
        if len(result) >= limit:
            return
        if type(left) is not type(right):
            result.append("%s: type %s -> %s" % (location, type(left).__name__, type(right).__name__))
        elif isinstance(left, dict):
            for key in sorted(set(left) | set(right)):
                child = location + "." + key
                if key not in right:
                    result.append("%s: missing" % child)
                elif key not in left:
                    result.append("%s: extra" % child)
                else:
                    walk(left[key], right[key], child)
                if len(result) >= limit:
                    break
        elif isinstance(left, list):
            if len(left) != len(right):
                result.append("%s: length %s -> %s" % (location, len(left), len(right)))
            for index, (a, b) in enumerate(zip(left, right)):
                walk(a, b, "%s[%s]" % (location, index))
        elif left != right:
            result.append("%s: %r -> %r" % (location, left, right))

    walk(expected, actual, path)
    return result


def axis_snapshot(axis):
    count = axis.GetNbins()
    return {"title": axis.GetTitle(), "nbins": count,
            "edges": [axis.GetBinLowEdge(index) for index in range(1, count + 2)],
            "labels": [axis.GetBinLabel(index) for index in range(1, count + 1)],
            "first": axis.GetFirst(), "last": axis.GetLast()}


def histogram_snapshot(hist):
    if hist.ClassName() not in ("TH1F", "TH1D", "TH1I", "TH1S", "TH1C", "TH2F", "TH2D", "TH2I", "TH2S", "TH2C"):
        raise TypeError("Unsupported histogram class %s" % hist.ClassName())
    dimension = hist.GetDimension()
    stats = array("d", [0.0] * (7 if dimension == 2 else 4))
    hist.GetStats(stats)
    sumw2 = hist.GetSumw2()
    bits = 32 if hist.ClassName().endswith("F") else 64
    return {"class": hist.ClassName(), "name": hist.GetName(), "title": hist.GetTitle(),
            "dimension": dimension, "entries": hist.GetEntries(), "option": hist.GetOption(),
            "axes": [axis_snapshot(hist.GetXaxis()), axis_snapshot(hist.GetYaxis()), axis_snapshot(hist.GetZaxis())],
            "contents": [floating(hist.GetBinContent(index), bits) for index in range(hist.GetNcells())],
            "errors": [hist.GetBinError(index) for index in range(hist.GetNcells())],
            "sumw2": [sumw2.At(index) for index in range(sumw2.GetSize())], "stats": list(stats),
            "functions": [object_snapshot(item) for item in hist.GetListOfFunctions()]}


FLOAT_TYPES = {"Float_t": 32, "Double_t": 64}
INTEGER_TYPES = {"Bool_t", "Char_t", "UChar_t", "Short_t", "UShort_t", "Int_t", "UInt_t",
                 "Long_t", "ULong_t", "Long64_t", "ULong64_t"}


def _leaf_value(value, dtype):
    if dtype in FLOAT_TYPES:
        return floating(value, FLOAT_TYPES[dtype])
    if isinstance(value, (str, bytes)):
        value = ord(value) if isinstance(value, str) else value[0]
        if dtype == "Char_t" and value > 127:
            value -= 256
    return bool(value) if dtype == "Bool_t" else int(value)


def tree_snapshot(tree):
    schema = []
    leaves = []
    for branch in tree.GetListOfBranches():
        branch_leaves = list(branch.GetListOfLeaves())
        if branch.GetClassName() or len(branch_leaves) != 1 or branch.GetTitle().endswith("/C"):
            raise TypeError("Unsupported tree branch %s: %s" % (branch.GetName(), branch.GetTitle()))
        leaf = branch_leaves[0]
        dtype = leaf.GetTypeName()
        if dtype not in FLOAT_TYPES and dtype not in INTEGER_TYPES:
            raise TypeError("Unsupported leaf type %s in %s" % (dtype, branch.GetName()))
        count = leaf.GetLeafCount()
        schema.append({"name": branch.GetName(), "title": branch.GetTitle(), "class": branch.GetClassName(),
                       "leaf": leaf.GetName(), "leaf_title": leaf.GetTitle(), "type": dtype, "length": leaf.GetLenStatic(),
                       "counter": count.GetName() if count else None})
        leaves.append(leaf)
    entries = []
    for index in range(tree.GetEntries()):
        if tree.GetEntry(index) < 0:
            raise RuntimeError("Cannot read %s entry %s" % (tree.GetName(), index))
        entry = []
        for branch, leaf in zip(schema, leaves):
            # PyROOT's typed attribute access avoids GetValue's double conversion of 64-bit event IDs.
            value = getattr(tree, branch["name"])
            if "[" in leaf.GetTitle():
                value = [_leaf_value(value[i], branch["type"]) for i in range(leaf.GetLen())]
            else:
                value = _leaf_value(value, branch["type"])
            entry.append(value)
        entries.append(entry)
    aliases = [{"name": alias.GetName(), "expression": alias.GetTitle()} for alias in (tree.GetListOfAliases() or [])]
    return {"class": tree.ClassName(), "name": tree.GetName(), "title": tree.GetTitle(),
            "branches": schema, "aliases": aliases, "entries": entries}


def directory_snapshot(directory):
    keys = sorted(directory.GetListOfKeys(), key=lambda key: (key.GetName(), key.GetCycle()))
    result = []
    for key in keys:
        obj = key.ReadObj()
        result.append({"key": key.GetName(), "cycle": key.GetCycle(), "class": key.GetClassName(),
                       "object": object_snapshot(obj)})
    return result


def object_snapshot(obj):
    if obj.InheritsFrom("TDirectory"):
        return {"class": obj.ClassName(), "name": obj.GetName(), "objects": directory_snapshot(obj)}
    if obj.InheritsFrom("TH1"):
        return histogram_snapshot(obj)
    if obj.InheritsFrom("TTree"):
        return tree_snapshot(obj)
    if obj.ClassName() == "TNamed":
        return {"class": "TNamed", "name": obj.GetName(), "title": obj.GetTitle()}
    if obj.ClassName() == "TObjString":
        return {"class": "TObjString", "string": str(obj.GetString())}
    raise TypeError("Unsupported ROOT snapshot object %s (%s)" % (obj.ClassName(), obj.GetName()))


def file_snapshot(path):
    import ROOT
    source = ROOT.TFile.Open(str(path), "READ")
    if not source or source.IsZombie():
        raise RuntimeError("Cannot read ROOT output %s" % path)
    try:
        # The container's path, UUID, timestamps, compression and physical offsets are omitted.
        return directory_snapshot(source)
    finally:
        source.Close()
