"""Subprocess worker for unchanged legacy scripts and BBB cases."""
import json
import os
from pathlib import Path
import runpy
import sys
import traceback

from bootstrap import MISSING_DEPENDENCY_EXIT, TESTS, MissingDependency, configure_root, dependencies, prepare


def normal(case_id, workspace, extra):
    with (TESTS / "inventory.json").open(encoding="utf-8") as stream:
        case = next(case for case in json.load(stream)["cases"] if case["id"] == case_id)
    dependencies(case["dependencies"])
    mirror = prepare(workspace, resources="ROOT" in case["dependencies"])
    cwd = mirror / case["package"]
    os.chdir(cwd)
    if "ROOT" in case["dependencies"]:
        configure_root(workspace)
    script = TESTS / case["path"]
    sys.path.insert(0, str(script.parent))
    arguments = list(case.get("arguments", []))
    fixture = case.get("fixture")
    if fixture:
        from support.fixtures import make_normal_inputs
        arguments = make_normal_inputs(fixture, cwd)
    sys.argv = [str(script)] + arguments + extra
    runpy.run_path(str(script), run_name="__main__")


def bbb(case_id, workspace, result_path):
    from BBB.cases import CASES
    from BBB.snapshot import canonical_bytes, exact
    from BBB.runtime import provenance
    from support.fixtures import fingerprint
    case = CASES[case_id]
    dependencies(case["dependencies"])
    mirror = prepare(workspace, resources="ROOT" in case["dependencies"])
    os.chdir(mirror)
    if "ROOT" in case["dependencies"]:
        configure_root(workspace, single_thread=True)
    result = case["run"](Path(workspace))
    document = {"format": 1, "case": case_id, "fixture_sha256": fingerprint(),
                "runtime": provenance(case["dependencies"]), "output": exact(result)}
    Path(result_path).write_bytes(canonical_bytes(document))


def main():
    mode, case_id, workspace = sys.argv[1:4]
    try:
        if mode == "normal":
            arguments = sys.argv[4:]
            if arguments[:1] == ["--"]:
                arguments = arguments[1:]
            normal(case_id, workspace, arguments)
        elif mode == "bbb":
            bbb(case_id, workspace, sys.argv[4])
        else:
            raise ValueError("Unknown worker mode %r" % mode)
        return 0
    except MissingDependency as error:
        print("ERROR: %s" % error, file=sys.stderr)
        return MISSING_DEPENDENCY_EXIT
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.path.insert(0, str(TESTS))
    sys.exit(main())
