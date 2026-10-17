#!/usr/bin/env python3
# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Check that moved Python files are the old files, except for the lines a move has to change.

A move (git mv plus new import paths) must not change any behaviour. This tool compares each moved file with its
old version in git, without importing anything (no ROOT needed, runs on Windows):

    python3 Tests/tools/move_check.py [--ref HEAD] [--allow REGEX ...] OLD=NEW [OLD=NEW ...]
    python3 Tests/tools/move_check.py --map pairs.json          # {"old/path.py": "new/path.py", ...}

For every pair it reports:
  lines   the changed lines (old -> new). A changed line is allowed when it is an import statement or matches one of
          the --allow regular expressions; any other changed line fails the check.
  units   the top-level functions, classes and methods whose AST differs (ast.dump without positions). This is a
          cross-check that shows where the allowed lines are; AST, not bytecode, because Python 3.13 compiles
          `LOG.x()` differently when LOG is imported instead of assigned.

Exit status: 0 when every changed line is allowed, 1 otherwise (2 for usage errors).
Example (LocalR/architecture/18, S1):

    python3 Tests/tools/move_check.py --allow "Histogrammer\\.methods" \\
        Plotter/python/sample/Sample.py=Histogrammer/python/sample/Sample.py
"""
import argparse
import ast
import difflib
import json
import re
import subprocess
import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

REPO = Path(__file__).resolve().parents[2]
IMPORT = re.compile(r"^\s*(import\s+\S|from\s+\S+\s+import\s)")  # one-line import statements


@dataclass
class FileReport:
    """The comparison of one moved file."""
    old: str
    new: str
    changed: List[Tuple[str, str]] = field(default_factory=list)     # (old line, new line); '' when added/removed
    disallowed: List[Tuple[str, str]] = field(default_factory=list)  # the changed lines that are not allowed
    units: List[str] = field(default_factory=list)                   # functions/classes whose AST differs
    note: Optional[str] = None                                       # e.g. why the AST could not be compared

    @property
    def ok(self):
        return not self.disallowed


# =============================================================================
# ================================ COMPARISON =================================


def compare(old_text, new_text, allow=(), old="old", new="new"):
    """Compare two versions of a file; see the module docstring."""
    report = FileReport(old, new)
    patterns = [re.compile(pattern) for pattern in allow]
    for old_line, new_line in changed_lines(old_text, new_text):
        report.changed.append((old_line, new_line))
        if not (_allowed(old_line, patterns) and _allowed(new_line, patterns)):
            report.disallowed.append((old_line, new_line))
    try:
        report.units = differing_units(old_text, new_text)
    except SyntaxError as error:  # Python 2 files: the line check above still applies
        report.note = "AST not compared (%s, line %s)" % (error.msg, error.lineno)
    return report


def changed_lines(old_text, new_text):
    """The changed lines as (old, new) pairs: replaced lines pairwise, added or removed lines against ''."""
    old_lines, new_lines = old_text.splitlines(), new_text.splitlines()  # also ignores CRLF vs LF
    result = []
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            continue
        before, after = old_lines[i1:i2], new_lines[j1:j2]
        for index in range(max(len(before), len(after))):
            result.append((before[index] if index < len(before) else "",
                           after[index] if index < len(after) else ""))
    return result


def differing_units(old_text, new_text):
    """Names of the top-level functions/classes (and methods, as Class.method) whose AST differs, plus
    '<module>' when the remaining module-level statements differ, '+name'/'-name' for added/removed units."""
    old_units, new_units = _units(old_text), _units(new_text)
    result = []
    for name in old_units:
        if name not in new_units:
            result.append("-" + name)
        elif old_units[name] != new_units[name]:
            result.append(name)
    result.extend("+" + name for name in new_units if name not in old_units)
    return result


def _allowed(line, patterns):
    return not line.strip() or bool(IMPORT.match(line)) or any(pattern.search(line) for pattern in patterns)


def _units(text):
    """{unit name: ast.dump} of a module: each top-level def/class, each method, and '<module>' for the rest."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)  # old string escapes are not a move problem
        tree = ast.parse(text)
    units, rest = {"<module>": ""}, []  # '<module>' first, so reports list it before the functions
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            units[node.name] = ast.dump(node, include_attributes=False)
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        units[node.name + "." + item.name] = ast.dump(item, include_attributes=False)
        else:
            rest.append(ast.dump(node, include_attributes=False))
    units["<module>"] = "\n".join(rest)
    return units


# =============================================================================
# ================================ INPUT/OUTPUT ===============================


def git_text(ref, path):
    """The content of `path` (relative to the repository) at git revision `ref`."""
    result = subprocess.run(["git", "show", "%s:%s" % (ref, path)], cwd=str(REPO),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise IOError("git show %s:%s failed: %s" % (ref, path, result.stderr.decode().strip()))
    return result.stdout.decode("utf-8")


def format_report(report):
    lines = ["%s %s -> %s" % ("OK  " if report.ok else "FAIL", report.old, report.new)]
    for old_line, new_line in report.changed:
        mark = "   " if (old_line, new_line) not in report.disallowed else " ! "
        lines.append("%s- %s" % (mark, old_line.strip()))
        lines.append("%s+ %s" % (mark, new_line.strip()))
    if report.units:
        lines.append("    AST differs in: %s" % ", ".join(report.units))
    if report.note:
        lines.append("    " + report.note)
    return "\n".join(lines)


def _pairs(args):
    pairs = []
    if args.map:
        with open(args.map, encoding="utf-8") as stream:
            pairs.extend(json.load(stream).items())
    for item in args.pairs:
        if "=" not in item:
            raise ValueError("expected OLD=NEW, got %r" % item)
        pairs.append(tuple(item.split("=", 1)))
    return pairs


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check that moved files only changed their import lines.")
    parser.add_argument('pairs', nargs='*', metavar='OLD=NEW', help="old path (in git) = new path (working tree)")
    parser.add_argument('--map', help="JSON file {old path: new path}")
    parser.add_argument('--ref', default="HEAD", help="git revision of the old files (default: %(default)s)")
    parser.add_argument('--allow', action='append', default=[], metavar='REGEX',
                        help="also allow changed lines matching this regular expression (repeatable)")
    args = parser.parse_args(argv)
    try:
        pairs = _pairs(args)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    if not pairs:
        parser.error("no OLD=NEW pairs given")
    failed = 0
    for old, new in pairs:
        report = compare(git_text(args.ref, old), (REPO / new).read_text(encoding="utf-8"), args.allow, old, new)
        print(format_report(report))
        failed += not report.ok
    print("%d file(s), %d with disallowed changes" % (len(pairs), failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
