"""Explicit lock/check workflow with isolated workers and read-only comparisons."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

from BBB.snapshot import canonical_bytes, difference
from support.progress import mark, reset_logs, section, tail

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
        env = os.environ.copy()
        env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="1777", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
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


def main(action, requested, replace=False, quiet=False, tail_lines=80):
    names = selected_cases(requested)
    if quiet and action != "check":
        raise ValueError("--quiet applies only to bbb check.")
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
        payloads = {}
        for name in names:
            print("LOCK %s (two fresh runs)" % name, flush=True)
            first, second = execute_case(name), execute_case(name)
            verify_stable(name, first, second)
            payloads[name] = first
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
    failures = []  # (name, details, log of a failed worker)
    for name in names:
        log = logs / (name + ".log") if quiet else None
        if not quiet:
            print("CHECK %s" % name, flush=True)
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
        if quiet:
            mark("F" if failures and failures[-1][0] == name else "P")
    if quiet:
        print("  [%s/%s]" % (len(names), len(names)))
        for name, details, log in failures:
            body = "\n".join(details)
            if log is not None:
                body += "\n--- worker output ---\n" + tail(log, tail_lines)
            section("FAIL %s" % name, body, ("Full log: %s" % log,) if log is not None else ())
    print("%s BBB cases checked, %s failed; expectations were not modified." % (len(names), len(failures)))
    return 1 if failures else 0
