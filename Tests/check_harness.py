#!/usr/bin/env python3
"""Small offline checks for relocation, selection, and exact baseline behavior."""
import ast
import builtins
import contextlib
import hashlib
import io
import json
import math
import re
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
    def test_catalog_is_metadata_only_and_checks_select_existing_suites(self):
        original_import = builtins.__import__

        def no_root(name, *args, **kwargs):
            if name == "ROOT" or name.startswith("TauFW"):
                raise AssertionError("Catalog imported a test dependency: " + name)
            return original_import(name, *args, **kwargs)

        output = io.StringIO()
        with mock.patch("builtins.__import__", side_effect=no_root), \
                mock.patch.object(run, "check_python_environment") as environment, \
                mock.patch.object(run, "execute_scripts") as execute, \
                mock.patch.object(run.subprocess, "run") as worker, \
                contextlib.redirect_stdout(output):
            self.assertEqual(run.main(["catalog"]), 0)
        environment.assert_not_called()
        execute.assert_not_called()
        worker.assert_not_called()
        metadata = json.loads(output.getvalue())
        self.assertEqual(set(metadata), {"checks", "normal", "bbb"})
        self.assertEqual([item["id"] for item in metadata["normal"]],
                         [case["id"] for case in run.select_cases(run.inventory(), "normal", [])])
        self.assertEqual([item["id"] for item in metadata["checks"]],
                         [case["id"] for case in run.check_cases()])
        self.assertEqual([item["id"] for item in metadata["bbb"]], runner.selected_cases([]))
        for case_id in ("pico.chunking", "plotter.histogram_correctness"):
            entry = next(item for item in metadata["normal"] if item["id"] == case_id)
            self.assertEqual(entry["dependencies"], ["ROOT", "numpy", "past"])
            self.assertTrue(entry["description"])
        name = run.check_cases()[0]["id"]
        with mock.patch.object(run, "execute_scripts", return_value=0) as execute:
            self.assertEqual(run.main(["checks", "--case", name, "--case", name], check_environment=False), 0)
        self.assertEqual(execute.call_args.args[0], [run.check_cases()[0]])
        self.assertEqual(execute.call_args.kwargs, {"quiet": True, "tail_lines": 80, "log_kind": "checks"})
        with contextlib.redirect_stderr(io.StringIO()), mock.patch.object(run, "execute_scripts") as execute:
            self.assertEqual(run.main(["checks", "--case", "unknown"], check_environment=False), 1)
            self.assertEqual(run.main(["checks", "--", "argument"], check_environment=False), 1)
        execute.assert_not_called()

    def test_environment_command_checks_without_running_tests(self):
        with mock.patch.object(run, "check_python_environment") as check, \
                mock.patch.object(run, "inventory") as inventory:
            self.assertEqual(run.main(["environment"]), 0)
        check.assert_called_once_with()
        inventory.assert_not_called()

    def test_environment_warning_preserves_uninstall_command(self):
        result = mock.Mock(returncode=0, stdout="numpy: Run: pip3 uninstall numpy\n")
        output = io.StringIO()
        with mock.patch.object(run.subprocess, "run", return_value=result), \
                contextlib.redirect_stderr(output):
            run.check_python_environment()
        self.assertIn("WARNING: numpy: Run: pip3 uninstall numpy", output.getvalue())

    def test_relocated_contents(self):
        migration = json.loads((TESTS / "migration.json").read_text(encoding="utf-8"))
        self.assertEqual(len(migration["files"]), 36)
        for record in migration["files"]:
            moved = TESTS.parent / record["moved"]
            self.assertFalse((TESTS.parent / record["original"]).exists())
            if record.get("edited"):  # Deliberately changed after migration; the hashes describe the original.
                continue
            data = moved.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if digest != record["sha256"]:
                # Git may change text line endings on a Linux checkout.
                self.assertEqual(hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest(), record["canonical_sha256"], str(moved))

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
        expected |= {"Plotter/plotPico.py", "Plotter/WstarplotPico.py",
                     "PicoProducer/testChunking.py", "Plotter/testHistogramCorrectness.py"}
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
        for name in ("pico.sample", "plotter.rdataframe", "pico.batch"):
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
            self.assertEqual(run.execute_scripts(case, [], quiet=False), 1)

    def quiet_run(self, outcomes, tail_lines=80, cases=None):
        """Run mocked workers in quiet mode; outcomes are (exit status, printed text) per case."""
        cases = cases or run.select_cases(run.inventory(), "normal", [])[:len(outcomes)]
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
        for case, letter in zip(cases, "PFS"):
            self.assertRegex(output, r"(?m)^%s \.{3,} %s$" % (re.escape(case["id"]), letter))
        self.assertNotIn("passing chatter", output)
        self.assertIn("Traceback: boom", output)
        self.assertNotIn("early line", output)
        self.assertIn("SKIP 1: ERROR: Missing/unusable ROOT\n  %s" % cases[2]["id"], output)
        self.assertIn("Rerun:    python3 Tests/run.py normal --case %s" % cases[1]["id"], output)
        self.assertEqual(logs[cases[0]["id"]], "passing chatter\n")

    def test_cases_sharing_a_file_share_one_line(self):
        first, second, other = (dict(case) for case in run.select_cases(run.inventory(), "normal", [])[:3])
        second["path"] = first["path"]
        output = self.quiet_run([(0, ""), (1, ""), (0, "")], cases=[first, other, second])[1]
        # Same-file cases run together under the file name; a lone case keeps its own name.
        self.assertRegex(output, r"(?m)^%s \.{3,} PF\n%s \.{3,} P$" % (re.escape(first["path"]), re.escape(other["id"])))

    def test_skips_do_not_fail_but_all_skipped_does(self):
        skip = run.MISSING_DEPENDENCY_EXIT
        self.assertEqual(self.quiet_run([(0, ""), (skip, "")])[0], 0)
        self.assertEqual(self.quiet_run([(skip, ""), (skip, "")])[0], 1)

    def test_cli_defaults_and_verbose(self):
        for output_args, quiet, tail_lines in (([], True, 80), (["--tail", "5"], True, 5),
                                               (["-v"], False, 80), (["--verbose"], False, 80)):
            for command, name in (("normal", "plotter.variables"), ("integration", "pico.batch")):
                with mock.patch.object(run, "execute_scripts", return_value=0) as execute, \
                     contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(run.main([command, "--case", name] + output_args,
                                              check_environment=False), 0)
                self.assertEqual(execute.call_args.args[2:], (quiet, tail_lines))
            for action in ("check", "lock"):
                with mock.patch.object(runner, "main", return_value=0) as bbb:
                    self.assertEqual(run.main(["bbb", action] + output_args, check_environment=False), 0)
                bbb.assert_called_once_with(action, [], False, quiet, tail_lines, "HEAD")

    def test_output_flags_reject_invalid_combinations_and_removed_quiet(self):
        commands = (["normal"], ["integration"], ["all"], ["bbb", "check"], ["bbb", "lock"])
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            for command in commands:
                self.assertEqual(run.main(command + ["-v", "--tail", "5"], check_environment=False), 1)
                for flag in ("-q", "--quiet"):
                    with self.assertRaises(SystemExit) as error:
                        run.main(command + [flag], check_environment=False)
                    self.assertEqual(error.exception.code, 2)
            for action in ("list", "diff"):
                for output_args in (["-v"], ["--tail", "5"]):
                    self.assertEqual(run.main(["bbb", action] + output_args, check_environment=False), 1)
        self.assertIn("--tail does not apply with --verbose", stderr.getvalue())
        self.assertIn("--verbose and --tail apply only to bbb check/lock", stderr.getvalue())

    def test_all_runs_every_suite_quietly_and_propagates_failures(self):
        for checks_status, normal_status, bbb_status in ((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)):
            with mock.patch.object(run, "execute_scripts", side_effect=[checks_status, normal_status]) as scripts, \
                 mock.patch.object(runner, "main", return_value=bbb_status) as bbb, \
                 contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(run.main(["all", "--tail", "7"]),
                                 int(bool(checks_status or normal_status or bbb_status)))
            checks, normal = scripts.call_args_list
            self.assertEqual(checks.args[0], run.check_cases())
            self.assertEqual(checks.kwargs, {"quiet": True, "tail_lines": 7, "log_kind": "checks"})
            self.assertEqual(normal.args[0], run.select_cases(run.inventory(), "normal", []))
            self.assertEqual(normal.args[1:], ([], True, 7))
            bbb.assert_called_once_with("check", [], False, True, 7, "HEAD")
            self.assertIn("ALL: FAIL" if any((checks_status, normal_status, bbb_status)) else "ALL: PASS",
                          stdout.getvalue())

    def test_all_verbose_reaches_every_suite(self):
        with mock.patch.object(run, "execute_scripts", return_value=0) as scripts, \
             mock.patch.object(runner, "main", return_value=0) as bbb, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(run.main(["all", "-v"], check_environment=False), 0)
        checks, normal = scripts.call_args_list
        self.assertEqual(checks.args[0], run.check_cases(quiet=False))
        self.assertTrue(all(case["command"][-1] == "-v" for case in checks.args[0][:-1]))
        self.assertEqual(checks.kwargs, {"quiet": False, "tail_lines": 80, "log_kind": "checks"})
        self.assertEqual(normal.args[1:], ([], False, 80))
        bbb.assert_called_once_with("check", [], False, False, 80, "HEAD")

    def test_all_stops_on_interrupt_and_rejects_script_arguments(self):
        with mock.patch.object(run, "execute_scripts", return_value=130) as scripts, \
             mock.patch.object(runner, "main") as bbb, \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(run.main(["all"]), 130)
            self.assertEqual(run.main(["all", "--", "unsafe-argument"]), 1)
        scripts.assert_called_once()
        bbb.assert_not_called()

    def test_standalone_check_uses_current_interpreter_and_repo_directory(self):
        case = run.check_cases()[0]
        with mock.patch.object(run.subprocess, "run", return_value=mock.Mock(returncode=7)) as worker:
            self.assertEqual(run.run_case(case, []), 7)
        self.assertEqual(worker.call_args.args[0], [run.sys.executable, "-B"] + case["command"])
        self.assertEqual(worker.call_args.kwargs["cwd"], str(TESTS.parent))

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

    def test_bbb_check_default_logs_and_failure_reporting(self):
        names = ["pass", "diff", "crash"]
        expected = {name: payload(name) for name in names}
        with tempfile.TemporaryDirectory() as directory:
            def worker(name, log):
                log.write_text("early chatter\nlast diagnostic\n")
                if name == "crash":
                    raise RuntimeError("worker crashed")
                return payload(name, {"value": 2.0}) if name == "diff" else expected[name]

            with mock.patch.object(progress, "LOGS", Path(directory)), \
                 mock.patch.object(runner, "selected_cases", return_value=names), \
                 mock.patch.object(runner, "load_lock", return_value=expected), \
                 mock.patch.object(runner, "validate_target"), \
                 mock.patch.object(runner, "execute_case", side_effect=worker), \
                 contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(runner.main("check", [], tail_lines=1), 1)
            output = stdout.getvalue()
            self.assertRegex(output, r"(?m)^BBB/cases.py \.{3,} PFF$")
            self.assertIn("$.output.value.float64", output)
            self.assertIn("worker crashed", output)
            self.assertEqual(output.count("last diagnostic"), 1)
            self.assertNotIn("early chatter", output)
            self.assertIn("Full log: %s" % (Path(directory) / "bbb" / "crash.log"), output)
            self.assertEqual({log.name for log in (Path(directory) / "bbb").iterdir()},
                             {name + ".log" for name in names})

    def test_lock_logs_both_runs_and_reproduces_bytes(self):
        names = ["first", "second"]
        expected = {name: payload(name) for name in names}
        for quiet in (True, False):
            with tempfile.TemporaryDirectory() as directory:
                baselines = Path(directory) / "baselines"
                runner.store_lock(baselines, expected)
                before = contents(baselines)

                def worker(name, log):
                    if log is None:
                        print("passing chatter")
                    else:
                        log.write_text("passing chatter\n")
                    return expected[name]

                with mock.patch.object(runner, "BASELINES", baselines), \
                     mock.patch.object(progress, "LOGS", Path(directory) / "logs"), \
                     mock.patch.object(runner, "selected_cases", return_value=names), \
                     mock.patch.object(runner, "validate_target"), \
                     mock.patch.object(runner, "execute_case", side_effect=worker) as execute, \
                     contextlib.redirect_stdout(io.StringIO()) as stdout:
                    # Omit quiet to verify the runner's default, too.
                    options = {} if quiet else {"quiet": False}
                    self.assertEqual(runner.main("lock", [], replace=True, **options), 0)
                self.assertEqual(before, contents(baselines))
                self.assertEqual([call.args[0] for call in execute.call_args_list], ["first", "first", "second", "second"])
                output = stdout.getvalue()
                self.assertIn("LOCK SUMMARY", output)
                self.assertIn("Locked 2 BBB cases.", output)
                if quiet:
                    self.assertRegex(output, r"(?m)^BBB/cases.py \.{3,} PP$")
                    self.assertNotIn("passing chatter", output)
                    logs = Path(directory) / "logs" / "bbb"
                    self.assertEqual({log.name for log in logs.iterdir()},
                                     {"%s.run%s.log" % (name, number) for name in names for number in (1, 2)})
                    self.assertTrue(all(log.read_text() == "passing chatter\n" for log in logs.iterdir()))
                else:
                    self.assertIn("passing chatter", output)
                    self.assertIn("LOCK first (two fresh runs)", output)
                    self.assertFalse((Path(directory) / "logs").exists())
                with mock.patch.object(runner, "selected_cases", return_value=names):
                    with self.assertRaisesRegex(ValueError, "lock captures the whole suite"):
                        runner.main("lock", ["first"], replace=True, quiet=quiet)

    def test_lock_failures_report_both_tails_and_never_write(self):
        names = ["crash.first", "crash.second", "unstable", "good"]
        outcomes = [RuntimeError("worker crashed"), payload(), payload(), RuntimeError("no snapshot"),
                    payload(), payload(output={"value": 2.0}), payload(), payload()]
        for tail_lines in (1, 0):
            calls = iter(outcomes)
            with tempfile.TemporaryDirectory() as directory:
                def worker(name, log):
                    log.write_text("early chatter\nlast diagnostic\n")
                    result = next(calls)
                    if isinstance(result, RuntimeError):
                        raise result
                    return result

                with mock.patch.object(runner, "BASELINES", Path(directory) / "baselines"), \
                     mock.patch.object(progress, "LOGS", Path(directory) / "logs"), \
                     mock.patch.object(runner, "selected_cases", return_value=names), \
                     mock.patch.object(runner, "validate_target"), \
                     mock.patch.object(runner, "execute_case", side_effect=worker) as execute, \
                     mock.patch.object(runner, "store_lock") as store, \
                     contextlib.redirect_stdout(io.StringIO()) as stdout:
                    with self.assertRaisesRegex(RuntimeError, "3 of 4 BBB cases failed; no expectations were written"):
                        runner.main("lock", [], tail_lines=tail_lines)
                store.assert_not_called()
                self.assertEqual(execute.call_count, 8)
                self.assertEqual(len(list((Path(directory) / "logs" / "bbb").iterdir())), 8)
                output = stdout.getvalue()
                self.assertRegex(output, r"(?m)^BBB/cases.py \.{3,} FFFP$")
                self.assertLess(output.index("LOCK SUMMARY"), output.index("worker crashed"))
                self.assertIn("no snapshot", output)
                self.assertIn("not repeatable", output)
                self.assertEqual(output.count("last diagnostic"), 6)
                self.assertEqual(output.count("early chatter"), 6 if tail_lines == 0 else 0)
                for name in names[:-1]:
                    for number in (1, 2):
                        self.assertIn("Full log: %s" % (Path(directory) / "logs" / "bbb" / ("%s.run%s.log" % (name, number))), output)

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
                runner.main("lock", [], quiet=False)
            store.assert_not_called()
        with mock.patch.object(runner.subprocess, "run", return_value=mock.Mock(returncode=23)):
            with self.assertRaises(RuntimeError):
                runner.execute_case("common.formatting")


if __name__ == "__main__":
    unittest.main(verbosity=2)
