#!/usr/bin/env python3
"""Small offline checks for relocation, selection, and exact baseline behavior."""
import ast
import builtins
import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import warnings

import run
from BBB import runner
from BBB.snapshot import canonical_bytes, difference, exact, object_snapshot
from support import progress

TESTS = Path(__file__).resolve().parent


def payload(name="common.formatting", output=None):
    return canonical_bytes({"format": 1, "case": name, "fixture_sha256": "fixed",
                            "runtime": {"python": "3.9.25"},
                            "output": exact(output if output is not None else {"value": 1.0})})


def contents(directory):
    return {path.name: path.read_bytes() for path in Path(directory).iterdir() if path.is_file()}


class HarnessChecks(unittest.TestCase):
    def test_relocated_contents(self):
        migration = json.loads((TESTS / "migration.json").read_text(encoding="utf-8"))
        self.assertEqual(len(migration["files"]), 38)
        for record in migration["files"]:
            moved = TESTS.parent / record["moved"]
            data = moved.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if digest != record["sha256"]:
                # Git may change text line endings on a Linux checkout.
                self.assertEqual(hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest(), record["canonical_sha256"], str(moved))
            self.assertFalse((TESTS.parent / record["original"]).exists())

    def test_python39_syntax(self):
        preserved = {str((TESTS.parent / record["moved"]).resolve())
                     for record in json.loads((TESTS / "migration.json").read_text())["files"]}
        for path in TESTS.rglob("*.py"):
            if str(path.resolve()) in preserved:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SyntaxWarning)
                ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path), feature_version=(3, 9))

    def test_inventory_covers_existing_scripts(self):
        cases = run.inventory()
        self.assertEqual(len({case["id"] for case in cases}), len(cases))
        moved = json.loads((TESTS / "migration.json").read_text())["files"]
        expected = {record["moved"][6:] for record in moved if Path(record["moved"]).name.startswith(("test", "Test"))}
        expected |= {"Plotter/plotPico.py", "Plotter/WstarplotPico.py"}
        self.assertEqual(expected, {case["path"] for case in cases})
        for case in cases:
            self.assertIn(TESTS.resolve(), (TESTS / case["path"]).resolve().parents)
            self.assertTrue((TESTS / case["path"]).is_file())

    def test_normal_selection_excludes_external_and_bbb(self):
        cases = run.select_cases(run.inventory(), "normal", [])
        self.assertTrue(cases)
        self.assertTrue(all(case["group"] == "local" for case in cases))
        self.assertTrue(all("BBB" not in case["path"] for case in cases))
        original_import = builtins.__import__

        def forbid_bbb(name, *args, **kwargs):
            if name == "BBB" or name.startswith("BBB."):
                raise AssertionError("Normal command imported BBB")
            return original_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=forbid_bbb), mock.patch.object(run, "execute_scripts", return_value=0) as execute:
            self.assertEqual(run.main(["normal", "--case", "plotter.variables"]), 0)
            self.assertEqual(execute.call_args[0][0][0]["id"], "plotter.variables")

    def test_explicit_legacy_broken_and_integration_selection(self):
        for name in ("common.table", "pico.sample", "plotter.rdataframe", "pico.batch"):
            with self.assertRaises(ValueError):
                run.select_cases(run.inventory(), "normal", [name])
        with self.assertRaises(ValueError):
            run.select_cases(run.inventory(), "integration", [])
        with self.assertRaises(ValueError):
            run.select_cases(run.inventory(), "normal", ["missing"])
        selected = run.select_cases(run.inventory(), "integration", ["pico.batch"])
        self.assertEqual(selected[0]["id"], "pico.batch")

    def test_script_failure_is_propagated(self):
        case = run.select_cases(run.inventory(), "normal", ["plotter.variables"])
        with mock.patch.object(run.subprocess, "run", return_value=mock.Mock(returncode=7)):
            self.assertEqual(run.execute_scripts(case, []), 1)

    def quiet_run(self, outcomes, tail_lines=80):
        """Run mocked workers in quiet mode; outcomes are (exit status, printed text) per case."""
        cases = run.select_cases(run.inventory(), "normal", [])[:len(outcomes)]
        calls = iter(outcomes)

        def worker(*args, **kwargs):
            code, text = next(calls)
            kwargs["stdout"].write(text.encode())
            return mock.Mock(returncode=code)

        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.object(progress, "LOGS", Path(directory)), \
             mock.patch.object(run.subprocess, "run", side_effect=worker), \
             contextlib.redirect_stdout(io.StringIO()) as stdout:
            status = run.execute_scripts(cases, [], quiet=True, tail_lines=tail_lines)
            logs = {path.stem: path.read_text() for path in (Path(directory) / "normal").iterdir()}
        return status, stdout.getvalue(), logs, cases

    def test_quiet_hides_passing_output_and_reports_problems(self):
        skip = run.MISSING_DEPENDENCY_EXIT
        status, output, logs, cases = self.quiet_run(
            [(0, "passing chatter\n"), (1, "early line\nTraceback: boom\n"), (skip, "ERROR: Missing/unusable ROOT\n")],
            tail_lines=1)
        self.assertEqual(status, 1)
        self.assertIn("PFS", output)
        self.assertNotIn("passing chatter", output)
        self.assertIn("Traceback: boom", output)
        self.assertNotIn("early line", output)
        self.assertIn("SKIP 1: ERROR: Missing/unusable ROOT\n  %s" % cases[2]["id"], output)
        self.assertIn("Rerun:    python3 Tests/run.py normal --case %s" % cases[1]["id"], output)
        self.assertEqual(logs[cases[0]["id"]], "passing chatter\n")

    def test_skips_do_not_fail_but_all_skipped_does(self):
        skip = run.MISSING_DEPENDENCY_EXIT
        self.assertEqual(self.quiet_run([(0, ""), (skip, "")])[0], 0)
        self.assertEqual(self.quiet_run([(skip, ""), (skip, "")])[0], 1)

    def test_tail_requires_quiet(self):
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(run.main(["normal", "--tail", "5"]), 1)
            self.assertEqual(run.main(["bbb", "lock", "-q"]), 1)
        self.assertIn("--tail applies only with --quiet", stderr.getvalue())
        self.assertIn("--quiet applies only to bbb check", stderr.getvalue())

    def test_exact_float_bits_and_canonical_encoding(self):
        self.assertNotEqual(exact(1.0), exact(math.nextafter(1.0, 2.0)))
        self.assertNotEqual(exact(0.0), exact(-0.0))
        self.assertEqual(canonical_bytes(exact({"z": math.inf, "a": math.nan})),
                         canonical_bytes(exact({"a": math.nan, "z": math.inf})))
        self.assertEqual(exact(2 ** 63 + 17), 2 ** 63 + 17)
        with self.assertRaises(TypeError):
            exact(object())

    def test_output_value_schema_and_name_changes_fail(self):
        reference = payload(output={"histogram": {"name": "mass", "value": 1.0}, "branch_type": "ULong64_t"})
        variants = (
            {"histogram": {"name": "mass", "value": math.nextafter(1.0, 2.0)}, "branch_type": "ULong64_t"},
            {"histogram": {"name": "renamed", "value": 1.0}, "branch_type": "ULong64_t"},
            {"histogram": {"name": "mass", "value": 1.0}, "branch_type": "Double_t"},
        )
        for variant in variants:
            self.assertTrue(runner.compare("common.formatting", reference, payload(output=variant)))
        self.assertTrue(difference({"object": 1}, {}))
        self.assertTrue(difference({}, {"extra": 1}))

    def test_unsupported_root_object_fails(self):
        opaque = mock.Mock()
        opaque.InheritsFrom.return_value = False
        opaque.ClassName.return_value = "UnsupportedClass"
        opaque.GetName.return_value = "opaque"
        with self.assertRaises(TypeError):
            object_snapshot(opaque)

    def test_lock_round_trip_and_comparison_are_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            runner.store_lock(directory, {"common.formatting": payload()})
            before = contents(directory)
            expected = runner.load_lock(directory)
            self.assertFalse(runner.compare("common.formatting", expected["common.formatting"], payload()))
            self.assertTrue(runner.compare("common.formatting", expected["common.formatting"], payload(output={"value": 2.0})))
            self.assertEqual(before, contents(directory))

    def test_existing_lock_requires_explicit_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            runner.store_lock(directory, {"common.formatting": payload()})
            before = contents(directory)
            with self.assertRaises(ValueError):
                runner.store_lock(directory, {"common.formatting": payload(output={"value": 2.0})})
            self.assertEqual(before, contents(directory))
            runner.store_lock(directory, {"common.formatting": payload(output={"value": 2.0})}, replace=True)
            self.assertNotEqual(before, contents(directory))

    def test_missing_corrupt_and_extra_baselines_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                runner.load_lock(directory)
            runner.store_lock(directory, {"common.formatting": payload()})
            path = Path(directory) / "extra.json"
            path.write_bytes(b"{}")
            with self.assertRaises(ValueError):
                runner.load_lock(directory)
            path.unlink()
            (Path(directory) / "common.formatting.json").write_bytes(payload(output={"value": 2.0}))
            with self.assertRaises(ValueError):
                runner.load_lock(directory)

    def test_unstable_or_failed_worker_cannot_publish_lock(self):
        first, second = payload(), payload(output={"value": 2.0})
        with self.assertRaises(RuntimeError):
            runner.verify_stable("common.formatting", first, second)
        with mock.patch.object(runner, "selected_cases", return_value=["common.formatting"]), \
             mock.patch.object(runner, "BASELINES", Path("does-not-exist")), \
             mock.patch.object(runner, "validate_target"), \
             mock.patch.object(runner, "execute_case", side_effect=[first, second]), \
             mock.patch.object(runner, "store_lock") as store:
            with self.assertRaises(RuntimeError):
                runner.main("lock", [])
            store.assert_not_called()
        with mock.patch.object(runner.subprocess, "run", return_value=mock.Mock(returncode=23)):
            with self.assertRaises(RuntimeError):
                runner.execute_case("common.formatting")


if __name__ == "__main__":
    unittest.main(verbosity=2)
