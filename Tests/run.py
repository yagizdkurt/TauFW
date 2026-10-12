#!/usr/bin/env python3
"""Explicit test entry points. Normal execution never imports the BBB suite."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from support.bootstrap import MISSING_DEPENDENCY_EXIT
from support.progress import elapsed, mark, reset_logs, section, tail

TESTS = Path(__file__).resolve().parent


def inventory():
    with (TESTS / "inventory.json").open(encoding="utf-8") as stream:
        return json.load(stream)["cases"]


def select_cases(cases, group, requested):
    group = "local" if group == "normal" else group
    if not requested:
        if group == "integration":
            raise ValueError("Integration execution requires --case; it can contact services or submit jobs.")
        return [case for case in cases if case["group"] == group]
    by_id = {case["id"]: case for case in cases}
    result = []
    for name in requested:
        if name not in by_id:
            raise ValueError("Unknown case %r; use 'list' for available IDs." % name)
        case = by_id[name]
        if case["group"] != group:
            raise ValueError("%s is %s: %s" % (name, case["group"], case.get("reason", "")))
        if case not in result:
            result.append(case)
    return result


def run_case(case, extra_args, log=None):
    """Return the worker's exit status; with a log path, its output goes there instead of the terminal."""
    with tempfile.TemporaryDirectory(prefix="taufw-normal-") as directory:
        env = os.environ.copy()
        env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="1777")
        command = [sys.executable, "-B", str(TESTS / "support" / "launch.py"),
                   "normal", case["id"], directory, "--"] + extra_args
        # Scripted answers only; an unexpected prompt hits EOF instead of hanging.
        if log is None:
            return subprocess.run(command, cwd=directory, env=env, input=case.get("stdin", ""), text=True).returncode
        with log.open("wb") as output:
            return subprocess.run(command, cwd=directory, env=env, input=case.get("stdin", ""), text=True,
                                  stdout=output, stderr=subprocess.STDOUT).returncode


def execute_scripts(cases, extra_args, quiet=False, tail_lines=80):
    logs = reset_logs("normal") if quiet else None
    if quiet:
        print("Running %s cases (quiet; logs in %s)" % (len(cases), logs), flush=True)
    results = []  # (case, status, seconds, log)
    started = time.monotonic()
    interrupted = False
    try:
        for case in cases:
            log = logs / (case["id"] + ".log") if quiet else None
            if not quiet:
                print("RUN %s" % case["id"], flush=True)
            began = time.monotonic()
            code = run_case(case, extra_args, log)
            status = "PASS" if code == 0 else "SKIP" if code == MISSING_DEPENDENCY_EXIT else "FAIL"
            results.append((case, status, time.monotonic() - began, log))
            if quiet:
                mark(status[0])
            elif status == "PASS":
                print("PASS %s (script exited successfully)" % case["id"], flush=True)
            elif status == "SKIP":
                print("SKIP %s (missing dependency)" % case["id"], flush=True)
            else:
                print("FAIL %s (exit %s)" % (case["id"], code), flush=True)
    except KeyboardInterrupt:
        interrupted = True
    if quiet:
        print("  [%s/%s]  %s" % (len(results), len(cases), elapsed(time.monotonic() - started)))
        for case, status, seconds, log in results:
            if status == "FAIL":
                section("FAIL %s (%s)" % (case["id"], elapsed(seconds)), tail(log, tail_lines),
                        ("Full log: %s" % log, "Rerun:    python3 Tests/run.py %s --case %s"
                         % ("integration" if case["group"] == "integration" else "normal", case["id"])))
        skipped = {}  # Identical missing-dependency messages are reported once.
        for case, status, seconds, log in results:
            if status == "SKIP":
                skipped.setdefault(tail(log, 1), []).append(case["id"])
        for reason, names in skipped.items():
            print("SKIP %s: %s\n  %s" % (len(names), reason, ", ".join(names)))
    if interrupted:
        print("\nInterrupted after %s of %s cases." % (len(results), len(cases)))
    counts = {status: [case["id"] for case, result, _, _ in results if result == status]
              for status in ("PASS", "FAIL", "SKIP")}
    print("%s executed, %s passed, %s failed, %s skipped" % (len(results), len(counts["PASS"]),
                                                          len(counts["FAIL"]), len(counts["SKIP"])))
    if counts["FAIL"]:
        print("Failed: %s" % ", ".join(counts["FAIL"]))
    if interrupted:
        return 130
    if results and not counts["PASS"] and not counts["FAIL"]:
        print("No case ran: every selected case is missing a dependency.")
        return 1
    return 1 if counts["FAIL"] else 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    extra = []
    if "--" in argv:
        index = argv.index("--")
        extra, argv = argv[index + 1:], argv[:index]
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("list", help="List scripts, classifications, and BBB IDs without importing ROOT")
    for command in ("normal", "integration"):
        child = sub.add_parser(command)
        child.add_argument("--case", action="append", default=[], help="Exact inventory ID; repeat to select cases")
    bbb = sub.add_parser("bbb", help="Separately invoked exact regression suite")
    bbb.add_argument("action", choices=("list", "lock", "check"))
    bbb.add_argument("--case", action="append", default=[])
    bbb.add_argument("--replace", action="store_true", help="Explicitly replace an existing lock (lock only)")
    for child in (sub.choices["normal"], sub.choices["integration"], bbb):
        child.add_argument("-q", "--quiet", action="store_true",
                           help="Print one character per case (P/F/S) and show captured output only for problems")
        child.add_argument("--tail", type=int, metavar="N",
                           help="With --quiet: show the last N lines of each failure's output (default 80, 0 = all)")
    args = parser.parse_args(argv or ["normal"])
    if sys.version_info < (3, 9):
        parser.error("The test harness requires Python 3.9 or newer; use your lxplus Python 3.9 runtime.")
    try:
        if getattr(args, "tail", None) is not None and not args.quiet:
            raise ValueError("--tail applies only with --quiet.")
        tail_lines = 80 if getattr(args, "tail", None) is None else args.tail
        if args.command == "bbb":
            if extra:
                raise ValueError("BBB does not accept legacy script arguments.")
            from BBB.runner import main as run_bbb
            return run_bbb(args.action, args.case, args.replace, args.quiet, tail_lines)
        cases = inventory()
        if args.command == "list":
            if extra:
                raise ValueError("list does not accept script arguments.")
            for case in cases:
                print("%-30s %-12s %s" % (case["id"], case["group"], case.get("reason", "")))
            print("BBB is separate: python3 Tests/run.py bbb list")
            return 0
        selected = select_cases(cases, args.command, args.case)
        if extra and len(selected) != 1:
            raise ValueError("Script arguments after -- require exactly one selected case.")
        if not selected:
            raise ValueError("No cases selected.")
        if args.command == "normal" and not args.quiet:
            print("Integration/legacy/broken cases remain listed; BBB is excluded.", flush=True)
        return execute_scripts(selected, extra, args.quiet, tail_lines)
    except (ValueError, RuntimeError, OSError) as error:
        print("ERROR: %s" % error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
