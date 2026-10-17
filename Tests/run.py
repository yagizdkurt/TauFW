#!/usr/bin/env python3
"""Explicit test entry points. Normal execution never imports the BBB suite."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

from support.bootstrap import MISSING_DEPENDENCY_EXIT
from support.events import emit, worker_environment
from support.progress import Lines, elapsed, file_groups, paint, reset_logs, section, tail

TESTS = Path(__file__).resolve().parent


def check_python_environment():
    """Use the same pre-build helper as FastSetup; warnings never fail a run."""
    helper = TESTS.parent / "Utilities/python/Installer/setup_tools.py"
    result = subprocess.run([sys.executable, "-B", str(helper), "environment"],
                            capture_output=True, text=True)
    for line in result.stdout.splitlines():
        print("WARNING: " + line, file=sys.stderr, flush=True)
        emit("warning", message=line)
    if result.returncode:
        message = "Could not check CMSSW Python package origins: " + result.stderr.strip()
        print("WARNING: " + message, file=sys.stderr, flush=True)
        emit("warning", message=message)


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


def describe_exit(code):
    """Worker exit status for reports; a negative code is the signal that killed it (e.g. a ROOT segfault)."""
    if code >= 0:
        return "exit %s" % code
    try:
        return "killed by %s" % signal.Signals(-code).name
    except ValueError:
        return "killed by signal %s" % -code


def run_case(case, extra_args, log=None):
    """Return the worker's exit status; with a log path, its output goes there instead of the terminal."""
    with tempfile.TemporaryDirectory(prefix="taufw-normal-") as directory:
        env = worker_environment(os.environ.copy())
        # Unbuffered so logs keep stdout and stderr (tracebacks, ROOT messages) in true order;
        # faulthandler dumps the Python stack if ROOT crashes the interpreter.
        env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="1777", PYTHONUNBUFFERED="1", PYTHONFAULTHANDLER="1")
        command = [sys.executable, "-B", str(TESTS / "support" / "launch.py"),
                   "normal", case["id"], directory, "--"] + extra_args
        cwd = directory
        if "command" in case:
            command = [sys.executable, "-B"] + case["command"]
            cwd = str(TESTS.parent)
        # Scripted answers only; an unexpected prompt hits EOF instead of hanging.
        if log is None:
            return subprocess.run(command, cwd=cwd, env=env, input=case.get("stdin", ""), text=True).returncode
        with log.open("wb") as output:
            return subprocess.run(command, cwd=cwd, env=env, input=case.get("stdin", ""), text=True,
                                  stdout=output, stderr=subprocess.STDOUT).returncode


def execute_scripts(cases, extra_args, quiet=True, tail_lines=80, log_kind="normal"):
    logs = reset_logs(log_kind) if quiet else None
    if quiet:
        print("Running %s cases (quiet; logs in %s)" % (len(cases), logs), flush=True)
    groups = file_groups(cases, lambda case: case["path"], lambda case: case["id"])
    lines = Lines([label for label, _ in groups])
    emit("suite", name=log_kind, total=len(cases))
    results = []  # (case, status, seconds, log, code)
    started = time.monotonic()
    interrupted = False
    try:
        for label, members in groups:
            if quiet:
                lines.begin(label)
            for case in members:
                log = logs / (case["id"] + ".log") if quiet else None
                if not quiet:
                    print("RUN %s" % case["id"], flush=True)
                began = time.monotonic()
                emit("case_start", id=case["id"], group=label, log=log)
                code = run_case(case, extra_args, log)
                status = "PASS" if code == 0 else "SKIP" if code == MISSING_DEPENDENCY_EXIT else "FAIL"
                results.append((case, status, time.monotonic() - began, log, code))
                emit("case_end", id=case["id"], status=status, seconds=results[-1][2], exit=describe_exit(code),
                     log=log)
                if quiet:
                    lines.mark(status[0])
                elif status == "PASS":
                    print("PASS %s (script exited successfully)" % case["id"], flush=True)
                elif status == "SKIP":
                    print("SKIP %s (missing dependency)" % case["id"], flush=True)
                else:
                    print("FAIL %s (%s)" % (case["id"], describe_exit(code)), flush=True)
    except KeyboardInterrupt:
        interrupted = True
    lines.end()
    if quiet:
        for case, status, seconds, log, code in results:
            if status == "FAIL":
                rerun = case.get("rerun") or "python3 Tests/run.py %s --case %s" % (
                    "integration" if case["group"] == "integration" else "normal", case["id"])
                section("FAIL %s (%s, %s)" % (case["id"], elapsed(seconds), describe_exit(code)), tail(log, tail_lines),
                        ("Full log: %s" % log, "Rerun:    %s" % rerun))
        skipped = {}  # Identical missing-dependency messages are reported once.
        for case, status, seconds, log, code in results:
            if status == "SKIP":
                skipped.setdefault(tail(log, 1), []).append(case["id"])
        for reason, names in skipped.items():
            print("%s %s: %s\n  %s" % (paint("SKIP", "S"), len(names), reason, ", ".join(names)))
    if interrupted:
        print("\nInterrupted after %s of %s cases." % (len(results), len(cases)))
    counts = {status: [case["id"] for case, result, _, _, _ in results if result == status]
              for status in ("PASS", "FAIL", "SKIP")}
    emit("summary", name=log_kind, passed=len(counts["PASS"]), failed=len(counts["FAIL"]),
         skipped=len(counts["SKIP"]), interrupted=interrupted, seconds=time.monotonic() - started)
    print("%s executed, %s passed, %s failed, %s skipped in %s"
          % (len(results), len(counts["PASS"]), len(counts["FAIL"]), len(counts["SKIP"]),
             elapsed(time.monotonic() - started)))
    if counts["FAIL"]:
        print("Failed: %s" % ", ".join(counts["FAIL"]))
    if interrupted:
        return 130
    if results and not counts["PASS"] and not counts["FAIL"]:
        print("No case ran: every selected case is missing a dependency.")
        return 1
    return 1 if counts["FAIL"] else 0


def check_cases(quiet=True):
    """Standalone checks keep their own unittest -q/-v flags, separate from the harness CLI."""
    cases = []
    for directory in ("Utilities", "Framework", "Setup", "PicoProducer/compat", "Fitter/api", "Plotter/api"):
        path = "Tests/" + directory
        command = ["-m", "unittest", "discover", "-s", path, "-p", "test_*.py", "-q" if quiet else "-v"]
        cases.append({"id": "unit." + directory.replace("/", ".").lower(),
                      "path": directory, "group": "checks", "command": command,
                      "rerun": "python3 " + " ".join(command)})
    for name in ("check_harness", "check_import_boundaries", "check_root"):
        path = "Tests/%s.py" % name
        command = [path] + (["-q" if quiet else "-v"] if name != "check_root" else [])
        cases.append({"id": name, "path": name + ".py", "group": "checks",
                      "command": command, "rerun": "python3 " + " ".join(command)})
    return cases


def run_all(tail_lines=80, quiet=True):
    """Run every automated suite, continuing after a suite fails."""
    output_args = ["--tail", str(tail_lines)] if quiet else ["--verbose"]
    suites = (
        ("Unit and harness checks", lambda: main(["checks"] + output_args, check_environment=False)),
        ("Normal tests", lambda: main(["normal"] + output_args, check_environment=False)),
        ("BBB regression checks", lambda: main(["bbb", "check"] + output_args, check_environment=False)),
    )
    failed = []
    for name, execute in suites:
        print("\n%s" % name, flush=True)
        try:
            status = execute()
        except (ValueError, RuntimeError, OSError) as error:
            print("ERROR: %s" % error, file=sys.stderr)
            status = 1
        except KeyboardInterrupt:
            return 130
        if status == 130:
            return status
        if status:
            failed.append(name)
    print("\nALL: %s%s" % ("FAIL" if failed else "PASS",
                            " (%s)" % ", ".join(failed) if failed else ""))
    return 1 if failed else 0


def catalog():
    """Menu metadata only: no dependency imports, workers, or baseline writes."""
    from BBB.cases import CASES
    return {
        "checks": [{"id": case["id"], "description": case["path"], "dependencies": []}
                   for case in check_cases()],
        "normal": [{"id": case["id"], "description": case.get("reason", ""),
                    "dependencies": case.get("dependencies", [])}
                   for case in select_cases(inventory(), "normal", [])],
        "bbb": [{"id": name, "description": case["description"],
                 "dependencies": case["dependencies"]} for name, case in CASES.items()],
    }


def main(argv=None, check_environment=True):
    argv = list(sys.argv[1:] if argv is None else argv)
    extra = []
    if "--" in argv:
        index = argv.index("--")
        extra, argv = argv[index + 1:], argv[:index]
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("list", help="List scripts, classifications, and BBB IDs without importing ROOT")
    sub.add_parser("catalog", help="Print automated test menu metadata as JSON without running tests")
    sub.add_parser("environment", help="Warn about ~/.local packages shadowing CMSSW; no tests run")
    all_tests = sub.add_parser("all", help="Run unit, harness, normal and BBB checks (quiet by default)")
    for command in ("normal", "integration", "checks"):
        child = sub.add_parser(command)
        child.add_argument("--case", action="append", default=[], help="Exact inventory ID; repeat to select cases")
    bbb = sub.add_parser("bbb", help="Separately invoked exact regression suite")
    bbb.add_argument("action", choices=("list", "lock", "check", "diff"))
    bbb.add_argument("--case", action="append", default=[])
    bbb.add_argument("--replace", action="store_true", help="Explicitly replace an existing lock (lock only)")
    bbb.add_argument("--ref", default="HEAD", help="Git revision whose lock 'diff' compares against (default HEAD)")
    for child in (all_tests, sub.choices["normal"], sub.choices["integration"], sub.choices["checks"], bbb):
        child.add_argument("-v", "--verbose", action="store_true",
                           help="Stream full worker output (default: status letters and failure details)")
        child.add_argument("--tail", type=int, metavar="N",
                           help="Unless verbose: show the last N lines of each failure's output (default 80, 0 = all)")
    args = parser.parse_args(argv or ["normal"])
    if sys.version_info < (3, 9):
        parser.error("The test harness requires Python 3.9 or newer; use your lxplus Python 3.9 runtime.")
    try:
        if args.command == "catalog":
            if extra:
                raise ValueError("catalog does not accept script arguments.")
            print(json.dumps(catalog()))
            return 0
        if check_environment and args.command != "list" and not (args.command == "bbb" and args.action == "list"):
            check_python_environment()
        if args.command == "environment":
            if extra:
                raise ValueError("environment does not accept script arguments.")
            return 0
        quiet = not getattr(args, "verbose", False)
        if getattr(args, "tail", None) is not None and not quiet:
            raise ValueError("--tail does not apply with --verbose.")
        tail_lines = 80 if getattr(args, "tail", None) is None else args.tail
        if args.command == "all":
            if extra:
                raise ValueError("all does not accept legacy script arguments.")
            return run_all(tail_lines, quiet)
        if args.command == "checks":
            if extra:
                raise ValueError("checks does not accept script arguments.")
            cases = check_cases(quiet)
            selected = select_cases(cases, "checks", args.case)
            return execute_scripts(selected, [], quiet=quiet, tail_lines=tail_lines, log_kind="checks")
        if args.command == "bbb":
            if extra:
                raise ValueError("BBB does not accept legacy script arguments.")
            if args.action in ("list", "diff") and (args.verbose or args.tail is not None):
                raise ValueError("--verbose and --tail apply only to bbb check/lock.")
            from BBB.runner import main as run_bbb
            if args.ref != "HEAD" and args.action != "diff":
                raise ValueError("--ref applies only to bbb diff.")
            return run_bbb(args.action, args.case, args.replace, quiet, tail_lines, args.ref)
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
        if args.command == "normal" and not quiet:
            print("Integration/legacy/broken cases remain listed; BBB is excluded.", flush=True)
        return execute_scripts(selected, extra, quiet, tail_lines)
    except (ValueError, RuntimeError, OSError) as error:
        print("ERROR: %s" % error, file=sys.stderr)
        emit("error", message=str(error))
        return 1


if __name__ == "__main__":
    sys.exit(main())
