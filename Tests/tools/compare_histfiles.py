#!/usr/bin/env python3
# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Compare two histogram files (TauFW.Utilities.HistFile) entry by entry (CL §21, S4; lxplus, needs ROOT).

ROOT files cannot be compared byte by byte: every write stores a new time stamp and UUID. This script reads both
files and compares what they hold: the file metadata, the entries in order (path, metadata, groups) and every
histogram with the BBB snapshot (class, name, title, axes, contents, errors, sumw2, statistics).

    cd $CMSSW_BASE/src/TauFW && cmsenv
    python3 Tests/tools/compare_histfiles.py A.root B.root            # SAME, or the first differences
    python3 Tests/tools/compare_histfiles.py A.root B.root --rtol 1e-12

Two fills of the same tuples may differ in the last bits of a sum (multithreaded RDataFrame adds in another order;
step 1 of the refactor saw up to 7e-14). Without --rtol only exact equality counts; with it, numbers that differ by
at most rtol (relative) count as equal, and the largest difference is printed.

Exit status 0 when the files are equal (within rtol), 1 otherwise.
"""
import argparse
import math
import struct
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(TESTS), str(TESTS / "support")]


def numbers_differ(a, b, rtol):
    """True if the numbers a and b differ by more than rtol relative to the larger of the two (0: exact)."""
    if a == b or (isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b)):
        return False
    if rtol and isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) > rtol * max(abs(a), abs(b))
    return True


def as_number(value):
    """A float of the BBB snapshot ({'float64': <hex>} or {'float32': <hex>}, its exact encoding) as a number;
    anything else as it is."""
    if isinstance(value, dict) and len(value) == 1:
        (key, text), = value.items()
        if key in ('float32', 'float64') and isinstance(text, str):
            return struct.unpack('<f' if key == 'float32' else '<d', bytes.fromhex(text))[0]
    return value


def differences(a, b, where, rtol, found, largest):
    """Append to `found` where the snapshots (nested dicts, lists, numbers) a and b differ; `largest` keeps the
    largest relative difference of numbers that are not exactly equal."""
    a, b = as_number(a), as_number(b)
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b), key=str):
            if key not in a or key not in b:
                found.append("%s.%s: only in %s" % (where, key, "A" if key in a else "B"))
            else:
                differences(a[key], b[key], "%s.%s" % (where, key), rtol, found, largest)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            found.append("%s: %d values in A, %d in B" % (where, len(a), len(b)))
            return
        for index, (x, y) in enumerate(zip(a, b)):
            differences(x, y, "%s[%d]" % (where, index), rtol, found, largest)
    else:
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and a != b and max(abs(a), abs(b)):
            largest[0] = max(largest[0], abs(a - b) / max(abs(a), abs(b)))
        if numbers_differ(a, b, rtol):
            found.append("%s: %r in A, %r in B" % (where, a, b))


def snapshot(histfile, histogram_snapshot):
    """What is compared: the file metadata and, per entry in order, its path, metadata and histograms per group."""
    return {"meta": histfile.meta,
            "entries": [{"path": entry.path, "meta": entry.meta,
                         "groups": {group: [histogram_snapshot(hist) for hist in hists]
                                    for group, hists in entry.groups.items()},
                         "group order": list(entry.groups)}
                        for entry in histfile.entries]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("a", metavar="A.root")
    parser.add_argument("b", metavar="B.root")
    parser.add_argument("--rtol", type=float, default=0.0, help="relative tolerance of numbers (default: exact)")
    parser.add_argument("--show", type=int, default=20, help="differences to print (default: %(default)s)")
    args = parser.parse_args(argv)
    from BBB.snapshot import histogram_snapshot
    from TauFW.Utilities.HistFile import read_histfile
    a, b = (snapshot(read_histfile(path), histogram_snapshot) for path in (args.a, args.b))
    found, largest = [], [0.0]
    differences(a, b, "file", args.rtol, found, largest)
    nhists = sum(len(group) for entry in a["entries"] for group in entry["groups"].values())
    print(">>> A: %s\n>>> B: %s\n>>> %d entries, %d histograms in A; largest relative difference of numbers: %.3g"
          % (args.a, args.b, len(a["entries"]), nhists, largest[0]))
    if not found:
        print("SAME" + (" (within rtol %g)" % (args.rtol) if args.rtol and largest[0] else ""))
        return 0
    print("DIFF: %d difference(s)%s" % (len(found), ", the first %d:" % (args.show) if len(found) > args.show else ":"))
    for line in found[:args.show]:
        print("  " + line)
    return 1


if __name__ == "__main__":
    sys.exit(main())
