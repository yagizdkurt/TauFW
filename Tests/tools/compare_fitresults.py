#!/usr/bin/env python3
# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Compare the results of two runs of the TES + tau ID fit (TODO §1 "Framework, TES/ID bundle"; no ROOT needed).

The fit of Fitter/run_workflow_zmm.sh writes its results relative to its working directory, and the fit stage of
the Framework writes the same tree in <run_dir>/stages/<id>/<era>/, so the two are compared by relative path:

    cd $CMSSW_BASE/src/TauFW
    python3 Tests/tools/compare_fitresults.py <clean copy>/Fitter <run_dir>/stages/fit/2025
    python3 Tests/tools/compare_fitresults.py A B --poi-atol 0.002 --pois-only

What is compared:
  - output_pt_less_region/**/FitparameterValues_*.txt (makecombinedfitTES_SF.py): every `name: value` line by name;
    the parameters of interest (tes_<region>, tid_SF_<region> and their 1-sigma limits) apart from the nuisance
    parameters;
  - tau_sf/*.json and data/tau/*.json (createroot_TES.py, merge_tau_jsons.py, make_tid_2025.py): every value of the
    JSON tree, numbers with the tolerances;
  - tau_sf/*.root: by name only (reading them needs ROOT).
A file of these kinds on one side only is a difference; every other file (plots, logs, combine output) is ignored.

Shapes made twice from the same tuples differ by ~1e-13 (multithreaded fill, CL §22), which can move a fitted
parameter of interest by one point of the scan grid and a flat nuisance parameter a lot (TODO §6 C). Fits of the
same shapes agree exactly (CL §15). So: without options only exact equality counts; --poi-atol (e.g. one grid step)
is the absolute tolerance of the parameters of interest, --rtol/--atol that of every other number, and --pois-only
leaves the nuisance parameters out. The summary gives the largest difference of each kind.

Exit status 0 when everything is equal (within the tolerances), 1 otherwise.
"""
import argparse
import fnmatch
import json
import os
import sys

PATTERNS = (("values", "output_pt_less_region/*/FitparameterValues_*.txt"), ("json", "tau_sf/*.json"),
            ("json", "data/tau/*.json"), ("root", "tau_sf/*.root"))  # (kind, pattern of the relative path)
POIS = ("tes_", "tid_SF_")  # makecombinedfitTES_SF.py: tes_<region>, tid_SF_<region>, ..._1sigma_low/high
SLACK = 1e-9  # a difference of exactly the tolerance (one grid step: 0.989 - 0.987 = 0.0020000000000000018) is equal


# =============================================================================
# ============================ COMPARISON (no ROOT) ===========================


def files_of(directory):
    """{relative path (with /): kind} of the result files below a directory (see PATTERNS)."""
    found = {}
    for root, _, names in os.walk(directory):
        for name in names:
            relative = os.path.relpath(os.path.join(root, name), directory).replace(os.sep, "/")
            kind = next((kind for kind, pattern in PATTERNS if fnmatch.fnmatch(relative, pattern)), None)
            if kind:
                found[relative] = kind
    return dict(sorted(found.items()))


def read_values(text):
    """{name: number or text} of a FitparameterValues file (one `name: value` per line)."""
    values = {}
    for line in text.splitlines():
        name, separator, value = line.partition(":")
        if separator:
            try:
                values[name.strip()] = float(value)
            except ValueError:
                values[name.strip()] = value.strip()
    return values


def is_poi(name):
    return name.startswith(POIS)


class Comparison:
    """Collects the differences and the largest absolute difference of the parameters of interest, of the nuisance
    parameters and of the JSON numbers."""

    def __init__(self, rtol=0.0, atol=0.0, poi_atol=0.0, pois_only=False):
        self.rtol, self.atol, self.poi_atol, self.pois_only = rtol, atol, poi_atol, pois_only
        self.found = []
        self.largest = {"poi": 0.0, "nuisance": 0.0, "json": 0.0}

    def differ(self, a, b, kind):
        """True if a and b are different, beyond the tolerances of their kind (text: exact); records the largest
        difference of numbers."""
        if a == b or (a != a and b != b):  # equal, or both NaN
            return False
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) \
                and not isinstance(b, bool):
            self.largest[kind] = max(self.largest[kind], abs(a - b))
            limit = self.poi_atol if kind == "poi" else max(self.rtol * max(abs(a), abs(b)), self.atol)
            return abs(a - b) > limit * (1 + SLACK)
        return True

    def values(self, a, b, where):
        """Two FitparameterValues files, parameter by name."""
        for name in sorted(set(a) | set(b)):
            kind = "poi" if is_poi(name) else "nuisance"
            if kind == "nuisance" and self.pois_only:
                continue
            if name not in a or name not in b:
                self.found.append("%s: %s only in %s" % (where, name, "A" if name in a else "B"))
            elif self.differ(a[name], b[name], kind):
                self.found.append("%s: %s = %r in A, %r in B" % (where, name, a[name], b[name]))

    def json(self, a, b, where):
        """Two JSON trees, keys by name, lists by position."""
        if isinstance(a, dict) and isinstance(b, dict):
            for key in sorted(set(a) | set(b), key=str):
                if key not in a or key not in b:
                    self.found.append("%s/%s: only in %s" % (where, key, "A" if key in a else "B"))
                else:
                    self.json(a[key], b[key], "%s/%s" % (where, key))
        elif isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                self.found.append("%s: %d values in A, %d in B" % (where, len(a), len(b)))
                return
            for index, (x, y) in enumerate(zip(a, b)):
                self.json(x, y, "%s[%d]" % (where, index))
        elif self.differ(a, b, "json"):
            self.found.append("%s: %r in A, %r in B" % (where, a, b))

    def files(self, names_a, names_b):
        """The file lists: a result file on one side only is a difference."""
        for name in sorted(set(names_a) ^ set(names_b)):
            self.found.append("%s: only in %s" % (name, "A" if name in names_a else "B"))


# =============================================================================
# ================================== MAIN =====================================


def _read(path):
    with open(path) as stream:
        return stream.read()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("a", metavar="DIR_A", help="e.g. Fitter/ of a clean copy after run_workflow_zmm.sh")
    parser.add_argument("b", metavar="DIR_B", help="e.g. <run_dir>/stages/fit/<era>")
    parser.add_argument("--poi-atol", type=float, default=0.0,
                        help="absolute tolerance of the parameters of interest (default: exact)")
    parser.add_argument("--rtol", type=float, default=0.0, help="relative tolerance of other numbers (default: exact)")
    parser.add_argument("--atol", type=float, default=0.0, help="absolute tolerance of other numbers (default: 0)")
    parser.add_argument("--pois-only", action="store_true", help="leave the nuisance parameters out")
    parser.add_argument("--show", type=int, default=20, help="differences to print (default: %(default)s)")
    args = parser.parse_args(argv)
    for directory in (args.a, args.b):
        if not os.path.isdir(directory):
            parser.error("no directory %s" % (directory))
    files_a, files_b = files_of(args.a), files_of(args.b)
    result = Comparison(args.rtol, args.atol, args.poi_atol, args.pois_only)
    result.files(files_a, files_b)
    both = [name for name in files_a if name in files_b]
    counts = {"values": 0, "json": 0, "root": 0}
    for name in both:
        kind = files_a[name]
        counts[kind] += 1
        path_a, path_b = os.path.join(args.a, name), os.path.join(args.b, name)
        if kind == "values":
            result.values(read_values(_read(path_a)), read_values(_read(path_b)), name)
        elif kind == "json":
            try:
                result.json(json.loads(_read(path_a)), json.loads(_read(path_b)), name)
            except ValueError as error:
                result.found.append("%s: not JSON (%s)" % (name, error))
    print(">>> A: %s\n>>> B: %s\n>>> %d result files in A, %d in B; on both sides: %d FitparameterValues, %d JSON, "
          "%d ROOT (by name only)" % (args.a, args.b, len(files_a), len(files_b), counts["values"], counts["json"],
                                      counts["root"]))
    print(">>> largest absolute difference: parameters of interest %.3g, nuisance parameters %s, JSON numbers %.3g"
          % (result.largest["poi"], "(left out)" if args.pois_only else "%.3g" % (result.largest["nuisance"]),
             result.largest["json"]))
    if not counts["values"]:
        print("DIFF: no FitparameterValues file on both sides")
        return 1
    if not result.found:
        print("SAME" + (" (within the tolerances)" if any(result.largest.values()) else ""))
        return 0
    print("DIFF: %d difference(s)%s" % (len(result.found),
                                        ", the first %d:" % (args.show) if len(result.found) > args.show else ":"))
    for line in result.found[:args.show]:
        print("  " + line)
    return 1


if __name__ == "__main__":
    sys.exit(main())
