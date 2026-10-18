#!/usr/bin/env python3
# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Compare the shape files of two runs of the TES shapes stage (CL §25, H4; lxplus, needs ROOT to read).

Two output directories of createinputsTES.py (a stage directory <run_dir>/stages/<id>/, or Fitter/ after
run_inputs.sh) are compared file by file:
  - the files: the same relative paths on both sides (input_pt_less_region/..., rebinning/, the PNG plots; the
    run's manifest.json is skipped), other files than .root by name only;
  - each .root file as the BBB case histogrammer.tes_inputs sees it (Tests/BBB/cases.py _tes_file_snapshot): every
    directory and key by name, cycle and class, every histogram in full (contents, errors, sumw2, statistics,
    axes, title), a TNamed's title, the TCanvas and TStyle of the control plots by key and class only.
Keys are matched by name, so a missing histogram is named, never a shifted list.

    cd $CMSSW_BASE/src/TauFW && cmsenv
    python3 Tests/tools/compare_shapefiles.py A/stages/shapes B/stages/shapes                # SAME, or the differences
    python3 Tests/tools/compare_shapefiles.py A/stages/shapes B/stages/shapes --rtol 1e-12

Two fills of the same tuples differ in the last bits (the multithreaded fill adds in another order; CL §24 saw
1.9e-13 between two control-histogram fills, CL §22 1.6e-13 in a derived QCD). Without --rtol only exact equality
counts; numbers that differ by at most rtol (relative to the larger) or atol (absolute) count as equal. The summary
gives the largest relative difference per histogram family (nominal, TES points, LTF and JTF shapes), with how many
histograms of each family have content: the LTF shapes are empty in the BBB fixture (TODO §7), so this is where they
are compared.

Exit status 0 when everything is equal (within the tolerances), 1 otherwise.
"""
import argparse
import os
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
TESTS = TOOLS.parent
sys.path[:0] = [str(TOOLS), str(TESTS), str(TESTS / "support")]

from compare_histfiles import as_number  # noqa: E402  (the BBB float encoding)

SKIPPED = ("manifest.json",)  # the run's record of the stage directory: run ids, times
FAMILIES = (("LTF", "shape_mTauFake"), ("JTF", "shape_jTauFake"), ("TES", "_TES"))  # by histogram name, in order


# =============================================================================
# ============================ COMPARISON (no ROOT) ===========================


def files_of(directory):
    """The relative paths (with /) of every file below a directory, sorted; the skipped names left out."""
    found = []
    for root, _, names in os.walk(directory):
        for name in names:
            if name not in SKIPPED:
                found.append(os.path.relpath(os.path.join(root, name), directory).replace(os.sep, "/"))
    return sorted(found)


def keyed(entries):
    """A file snapshot (lists of {key, cycle, class, ...}) as nested dicts keyed '<key>;<cycle>', so that keys are
    matched by name."""
    result = {}
    for entry in entries:
        value = dict(entry)
        if "objects" in value:
            value["objects"] = keyed(value["objects"])
        result["%s;%s" % (entry["key"], entry["cycle"])] = value
    return result


def family(name):
    """The family of a histogram by its name: LTF, JTF (shape systematics), TES (a TES point), else nominal."""
    return next((label for label, part in FAMILIES if part in name), "nominal")


class Comparison:
    """Collects the differences of two snapshots and, per histogram family, the count, the histograms with content
    and the largest relative difference of numbers that are not exactly equal."""

    def __init__(self, rtol=0.0, atol=0.0):
        self.rtol, self.atol = rtol, atol
        self.found = []
        self.families = {}  # family -> [histograms, with content, largest relative difference]

    def numbers_differ(self, a, b):
        """True if a and b are different values, beyond the tolerances for numbers (text: exact)."""
        if a == b or (a != a and b != b):  # equal, or both NaN
            return False
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
            return abs(a - b) > max(self.rtol * max(abs(a), abs(b)), self.atol)
        return True

    def compare(self, a, b, where, hist=None):
        """Compare two snapshot values (dicts, lists, numbers, text) below `where`; hist: the family of the
        histogram they belong to (for the largest difference)."""
        a, b = as_number(a), as_number(b)
        if isinstance(a, dict) and isinstance(b, dict):
            if hist is None and "histogram" in a and "histogram" in b:
                self.histogram(a["histogram"], b["histogram"], where)
                a, b = {k: v for k, v in a.items() if k != "histogram"}, {k: v for k, v in b.items() if k != "histogram"}
            for key in sorted(set(a) | set(b), key=str):
                if key not in a or key not in b:
                    self.found.append("%s/%s: only in %s" % (where, key, "A" if key in a else "B"))
                else:
                    self.compare(a[key], b[key], "%s/%s" % (where, key), hist)
        elif isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                self.found.append("%s: %d values in A, %d in B" % (where, len(a), len(b)))
                return
            for index, (x, y) in enumerate(zip(a, b)):
                self.compare(x, y, "%s[%d]" % (where, index), hist)
        else:
            if hist is not None and isinstance(a, float) and isinstance(b, float) and a != b and max(abs(a), abs(b)):
                record = self.families[hist]
                record[2] = max(record[2], abs(a - b) / max(abs(a), abs(b)))
            if self.numbers_differ(a, b):
                self.found.append("%s: %r in A, %r in B" % (where, a, b))

    def histogram(self, a, b, where):
        label = family(a.get("name", ""))
        record = self.families.setdefault(label, [0, 0, 0.0])
        record[0] += 1
        if any(as_number(value) for value in a.get("contents", ())):
            record[1] += 1
        self.compare(a, b, where + "#histogram", label)

    def files(self, names_a, names_b):
        """The file lists: a file on one side only is a difference."""
        for name in sorted(set(names_a) ^ set(names_b)):
            self.found.append("%s: only in %s" % (name, "A" if name in names_a else "B"))

    def largest(self):
        return max([record[2] for record in self.families.values()] or [0.0])


# =============================================================================
# ================================== MAIN =====================================


def snapshot(path):
    """A shape file as the BBB case sees it, keyed by name (needs ROOT)."""
    from BBB.cases import _tes_file_snapshot
    return keyed(_tes_file_snapshot(path))


def main(argv=None, read=snapshot):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("a", metavar="DIR_A")
    parser.add_argument("b", metavar="DIR_B")
    parser.add_argument("--rtol", type=float, default=0.0, help="relative tolerance of numbers (default: exact)")
    parser.add_argument("--atol", type=float, default=0.0, help="absolute tolerance of numbers (default: 0)")
    parser.add_argument("--show", type=int, default=20, help="differences to print (default: %(default)s)")
    args = parser.parse_args(argv)
    for directory in (args.a, args.b):
        if not os.path.isdir(directory):
            parser.error("no directory %s" % (directory))
    names_a, names_b = files_of(args.a), files_of(args.b)
    result = Comparison(args.rtol, args.atol)
    result.files(names_a, names_b)
    roots = [name for name in names_a if name.endswith(".root") and name in names_b]
    for name in roots:
        result.compare(read(os.path.join(args.a, name)), read(os.path.join(args.b, name)), name)
    print(">>> A: %s\n>>> B: %s\n>>> %d files in A (%d ROOT files compared), %d in B"
          % (args.a, args.b, len(names_a), len(roots), len(names_b)))
    for label in ("nominal", "TES", "LTF", "JTF"):
        count, filled, largest = result.families.get(label, (0, 0, 0.0))
        print(">>> %-7s %5d histograms, %5d with content, largest relative difference %.3g"
              % (label, count, filled, largest))
    if not roots:
        print("DIFF: no ROOT file to compare")
        return 1
    if not result.found:
        print("SAME" + (" (within rtol %g, atol %g)" % (args.rtol, args.atol) if result.largest() else ""))
        return 0
    print("DIFF: %d difference(s)%s" % (len(result.found),
                                        ", the first %d:" % (args.show) if len(result.found) > args.show else ":"))
    for line in result.found[:args.show]:
        print("  " + line)
    return 1


if __name__ == "__main__":
    sys.exit(main())
