#!/usr/bin/env python3
"""Explicit test entry points. Normal execution never imports the BBB suite."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

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


def execute_scripts(cases, extra_args):
    failures = 0
    for case in cases:
        print("RUN %s" % case["id"], flush=True)
        with tempfile.TemporaryDirectory(prefix="taufw-normal-") as directory:
            env = os.environ.copy()
            env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="1777")
            command = [sys.executable, "-B", str(TESTS / "support" / "launch.py"),
                       "normal", case["id"], directory, "--"] + extra_args
            # Scripted answers only; an unexpected prompt hits EOF instead of hanging.
            result = subprocess.run(command, cwd=directory, env=env, input=case.get("stdin", ""), text=True)
        if result.returncode:
            failures += 1
            print("FAIL %s (exit %s)" % (case["id"], result.returncode), flush=True)
        else:
            print("PASS %s (script exited successfully)" % case["id"], flush=True)
    print("%s executed, %s failed" % (len(cases), failures))
    return 1 if failures else 0


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
    args = parser.parse_args(argv or ["normal"])
    if sys.version_info < (3, 9):
        parser.error("The test harness requires Python 3.9 or newer; use your lxplus Python 3.9 runtime.")
    try:
        if args.command == "bbb":
            if extra:
                raise ValueError("BBB does not accept legacy script arguments.")
            from BBB.runner import main as run_bbb
            return run_bbb(args.action, args.case, args.replace)
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
        if args.command == "normal":
            print("Integration/legacy/broken cases remain listed; BBB is excluded.", flush=True)
        return execute_scripts(selected, extra)
    except (ValueError, RuntimeError, OSError) as error:
        print("ERROR: %s" % error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
