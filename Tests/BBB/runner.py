"""Explicit lock/check workflow with isolated workers and read-only comparisons."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time

from BBB.snapshot import canonical_bytes, difference
from support.events import emit, worker_environment
from support.progress import Lines, file_groups, reset_logs, section, tail

TESTS = Path(__file__).resolve().parents[1]
BASELINES = Path(__file__).resolve().parent / "baselines"


def selected_cases(requested):
    from BBB.cases import CASES
    names = requested or list(CASES)
    unknown = set(names) - set(CASES)
    if unknown:
        raise ValueError("Unknown BBB cases: %s" % ", ".join(sorted(unknown)))
    return list(dict.fromkeys(names))


def execute_case(name, log=None):
    with tempfile.TemporaryDirectory(prefix="taufw-bbb-") as directory:
        output = Path(directory) / "result.json"
        env = worker_environment(os.environ.copy())
        env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="1777", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
                   PYTHONUNBUFFERED="1", PYTHONFAULTHANDLER="1")  # Logs in true order; Python stack on ROOT crashes.
        command = [sys.executable, "-B", str(TESTS / "support" / "launch.py"), "bbb", name, directory, str(output)]
        if log is None:
            result = subprocess.run(command, cwd=directory, env=env)
        else:
            with log.open("wb") as stream:
                result = subprocess.run(command, cwd=directory, env=env, stdout=stream, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError("BBB %s failed (exit %s); no expectations were written." % (name, result.returncode))
        if not output.is_file():
            raise RuntimeError("BBB %s returned no snapshot." % name)
        return output.read_bytes()


def validate_target():
    if platform.system() != "Linux" or sys.version_info[:2] != (3, 9):
        raise RuntimeError("Capture/check BBB on lxplus with Python 3.9 and its matching PyROOT environment. "
                           "Current runtime: %s Python %s. Use 'bbb list' or the harness checks here."
                           % (platform.system(), platform.python_version()))


def verify_stable(name, first, second):
    if first != second:
        details = difference(json.loads(first), json.loads(second))
        raise RuntimeError("BBB %s is not repeatable; refusing to lock:\n%s" % (name, "\n".join(details)))


def store_lock(directory, payloads, replace=False):
    """Write only verified payloads, publishing the manifest last."""
    directory = Path(directory)
    manifest_path = directory / "manifest.json"
    if manifest_path.exists() and not replace:
        raise ValueError("Baseline already exists. Review the differences and use lock --replace explicitly.")
    if directory.exists() and any(directory.glob("*.json")) and not manifest_path.exists():
        raise ValueError("Baseline directory contains an incomplete lock; inspect it before creating expectations.")
    manifest = {"format": 1, "cases": {}}
    for name, payload in payloads.items():
        document = json.loads(payload)
        if document.get("case") != name or document.get("format") != 1:
            raise ValueError("Invalid baseline payload for %s" % name)
        manifest["cases"][name] = hashlib.sha256(payload).hexdigest()
    directory.mkdir(parents=True, exist_ok=True)
    # Every case was run twice before this function is called. Never write a partial successful subset.
    for name, payload in payloads.items():
        target = directory / (name + ".json")
        temporary = directory / (name + ".pending")
        temporary.write_bytes(payload)
        os.replace(str(temporary), str(target))
    if replace:
        for path in directory.glob("*.json"):
            if path.name != "manifest.json" and path.stem not in payloads:
                path.unlink()
    pending = directory / "manifest.pending"
    pending.write_bytes(canonical_bytes(manifest))
    os.replace(str(pending), str(manifest_path))


def load_lock(directory):
    directory = Path(directory)
    path = directory / "manifest.json"
    if not path.is_file():
        raise ValueError("Missing BBB baseline; run 'python3 Tests/run.py bbb lock' on lxplus before refactoring.")
    manifest = json.loads(path.read_bytes())
    if manifest.get("format") != 1 or not isinstance(manifest.get("cases"), dict):
        raise ValueError("Unsupported BBB baseline manifest.")
    expected_files = {name + ".json" for name in manifest["cases"]} | {"manifest.json"}
    actual_files = {entry.name for entry in directory.glob("*.json")}
    if actual_files != expected_files:
        raise ValueError("Baseline files differ from the manifest (missing/extra): %s" % sorted(actual_files ^ expected_files))
    result = {}
    for name, digest in manifest["cases"].items():
        payload = (directory / (name + ".json")).read_bytes()
        if hashlib.sha256(payload).hexdigest() != digest:
            raise ValueError("Baseline %s was modified without an explicit lock." % name)
        document = json.loads(payload)
        if document.get("case") != name or document.get("format") != 1:
            raise ValueError("Invalid baseline document %s" % name)
        result[name] = payload
    return result


def compare(name, expected, actual):
    if expected == actual:
        return []
    details = difference(json.loads(expected), json.loads(actual))
    return details or ["%s: canonical snapshot bytes differ" % name]


def committed_baseline(ref, filename):
    """Bytes of a baseline file at a Git revision, or None when it does not exist there."""
    result = subprocess.run(["git", "show", "%s:./%s" % (ref, filename)], cwd=str(BASELINES),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        if b"exists on disk, but not in" in result.stderr or b"does not exist in" in result.stderr:
            return None
        raise RuntimeError("git show %s:%s failed: %s" % (ref, filename, result.stderr.decode().strip()))
    return result.stdout


def diff_lock(ref):
    """Compare the working-tree lock with the one at ref. Added cases pass; changed or removed ones fail."""
    current = load_lock(BASELINES)  # Also proves the new lock is complete and self-consistent.
    manifest = committed_baseline(ref, "manifest.json")
    previous = json.loads(manifest)["cases"] if manifest is not None else {}
    counts = {"same": 0, "ADDED": 0, "CHANGED": 0, "REMOVED": 0}
    details = []
    for name in sorted(set(previous) | set(current)):
        if name not in previous:
            status = "ADDED"
        elif name not in current:
            status = "REMOVED"
        elif hashlib.sha256(current[name]).hexdigest() == previous[name]:
            status = "same"
        else:
            status = "CHANGED"
            old = committed_baseline(ref, name + ".json")
            details.append((name, compare(name, old, current[name])))
        counts[status] += 1
        print("  %-8s %s" % (status, name))
    for name, lines in details:
        print("\n%s:\n  %s" % (name, "\n  ".join(lines)))
    failed = counts["CHANGED"] or counts["REMOVED"]
    print("\nBBB DIFF vs %s: %s (%s same, %s added, %s changed, %s removed)"
          % (ref, "FAIL" if failed else "PASS", counts["same"], counts["ADDED"], counts["CHANGED"], counts["REMOVED"]))
    return 1 if failed else 0


def main(action, requested, replace=False, quiet=True, tail_lines=80, ref="HEAD"):
    if action == "diff":
        if requested or replace:
            raise ValueError("bbb diff compares the whole lock; it takes only --ref.")
        return diff_lock(ref)
    names = selected_cases(requested)
    if action == "list":
        from BBB.cases import CASES
        for name in names:
            print("%-30s %s" % (name, CASES[name]["description"]))
        return 0
    if replace and action != "lock":
        raise ValueError("--replace applies only to lock.")
    if action == "lock":
        # Replacing a baseline is always an entire suite operation, preventing accidental loss of coverage.
        if requested:
            raise ValueError("lock captures the whole suite; --case is for list/check only.")
        if (BASELINES / "manifest.json").exists() and not replace:
            raise ValueError("Baseline already exists. Review changes before using lock --replace.")
        validate_target()
        logs = reset_logs("bbb") if quiet else None
        lines = Lines(["BBB/cases.py"])
        if quiet:
            lines.begin("BBB/cases.py")
        payloads = {}
        failures = {}  # name -> reason; every case still runs so the summary lists all problems at once
        for name in names:
            if not quiet:
                print("LOCK %s (two fresh runs)" % name, flush=True)
            runs = []
            errors = []
            for number in (1, 2):
                log = logs / ("%s.run%s.log" % (name, number)) if quiet else None
                try:
                    runs.append(execute_case(name, log))
                except RuntimeError as error:
                    errors.append("Run %s: %s" % (number, error))
            if errors:
                failures[name] = "\n".join(errors)
            else:
                try:
                    verify_stable(name, runs[0], runs[1])
                    payloads[name] = runs[0]
                except RuntimeError as error:
                    failures[name] = str(error)
            if quiet:
                lines.mark("F" if name in failures else "P")
            elif name in failures:
                print("FAIL %s: %s" % (name, failures[name]), flush=True)
        lines.end()
        print("\nLOCK SUMMARY")
        for name in names:
            print("  %-4s %s" % ("FAIL" if name in failures else "PASS", name))
        for name, reason in failures.items():
            print("\n%s:\n  %s" % (name, reason.replace("\n", "\n  ")))
            if quiet:
                for number in (1, 2):
                    log = logs / ("%s.run%s.log" % (name, number))
                    section("FAIL %s (run %s)" % (name, number), tail(log, tail_lines),
                            ("Full log: %s" % log,))
        if failures:
            # Never publish a partial lock; all failure reasons and captured tails are reported above.
            raise RuntimeError("%s of %s BBB cases failed; no expectations were written." % (len(failures), len(names)))
        store_lock(BASELINES, payloads, replace)
        print("Locked %s BBB cases. Commit Tests/BBB/baselines/ before refactoring." % len(payloads))
        return 0
    expected = load_lock(BASELINES)
    all_names = selected_cases([])
    if set(expected) != set(all_names):
        raise ValueError("BBB case inventory changed (missing/extra): %s; review and explicitly re-lock."
                         % sorted(set(expected) ^ set(all_names)))
    validate_target()
    logs = reset_logs("bbb") if quiet else None
    # Every BBB case lives in BBB/cases.py, so a multi-case check is one line of letters.
    groups = file_groups(names, lambda name: "BBB/cases.py", lambda name: name)
    lines = Lines([label for label, _ in groups])
    if quiet:
        lines.begin(groups[0][0])
    emit("suite", name="bbb", total=len(names))
    started = time.monotonic()
    failures = []  # (name, details, log of a failed worker)
    for name in names:
        log = logs / (name + ".log") if quiet else None
        if not quiet:
            print("CHECK %s" % name, flush=True)
        emit("case_start", id=name, group="BBB/cases.py", log=log)
        began = time.monotonic()
        try:
            details = compare(name, expected[name], execute_case(name, log))
            if details:
                failures.append((name, details, None))
                if not quiet:
                    print("FAIL %s\n%s" % (name, "\n".join(details)))
            elif not quiet:
                print("PASS %s" % name)
        except RuntimeError as error:
            failures.append((name, [str(error)], log))
            if not quiet:
                print("FAIL %s: %s" % (name, error))
        failed = bool(failures) and failures[-1][0] == name
        emit("case_end", id=name, status="FAIL" if failed else "PASS", seconds=time.monotonic() - began,
             exit="", log=log, details=failures[-1][1] if failed else [])
        if quiet:
            lines.mark("F" if failed else "P")
    lines.end()
    emit("summary", name="bbb", passed=len(names) - len(failures), failed=len(failures), skipped=0,
         interrupted=False, seconds=time.monotonic() - started)
    if quiet:
        for name, details, log in failures:
            body = "\n".join(details)
            if log is not None:
                body += "\n--- worker output ---\n" + tail(log, tail_lines)
            section("FAIL %s" % name, body, ("Full log: %s" % log,) if log is not None else ())
    print("%s BBB cases checked, %s failed; expectations were not modified." % (len(names), len(failures)))
    return 1 if failures else 0
