"""Temporary-file checks and isolated public imports."""

import ast
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import checkout  # noqa: F401  (must precede TauFW.Utilities imports)
from TauFW.Utilities.FIO import FileIO
from TauFW.Utilities.FIO._internal import commands, formats


class FileIOTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.files = FileIO(temporary_directory=self.directory)

    def test_public_imports_are_silent_and_optional_dependencies_are_lazy(self):
        repository = Path(__file__).resolve().parents[2]
        script = """
import sys
sys.modules['ROOT'] = None
sys.modules['yaml'] = None
sys.path.insert(0, %r)
import checkout
from TauFW.Utilities.CLI import CLI
from TauFW.Utilities.FIO import FileIO
import TauFW.Utilities.CLI as cli_package
import TauFW.Utilities.FIO as fio_package
assert cli_package.__all__ == ['CLI']
assert fio_package.__all__ == ['FileIO']
assert {name.split('.')[1] for name in sys.modules if name.startswith('TauFW.')} == {'Utilities'}
CLI()
FileIO()
""" % str(Path(__file__).resolve().parent)
        result = subprocess.run([sys.executable, "-B", "-c", script], cwd=repository,
                                capture_output=True, text=True, check=True)
        self.assertEqual((result.stdout, result.stderr), ("", ""))

    def test_python39_syntax_and_production_import_boundaries(self):
        utilities = Path(__file__).resolve().parents[2] / "Utilities"
        for path in utilities.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 9))
            if path.name == "_audit_io.py":
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    self.assertFalse(module.startswith(("TauFW", "PicoProducer", "Histogrammer", "Plotter", "Fitter"))
                                     and not module.startswith("TauFW.Utilities"), str(path))

    def test_text_bytes_lines_and_gzip_json_round_trips(self):
        text_file = self.directory / "message.txt"
        self.files.write_text(text_file, "İstanbul\n")
        self.files.append_text(text_file, "second\n")
        self.assertEqual(self.files.read_lines(text_file), ["İstanbul", "second"])
        lines_file = self.directory / "list.txt"
        self.files.write_lines(lines_file, iter(["one", "two"]))
        self.assertEqual(self.files.read_text(lines_file), "one\ntwo\n")
        binary_file = self.directory / "payload.bin"
        self.files.write_bytes(binary_file, b"\x00\xff")
        self.assertEqual(self.files.read_bytes(binary_file), b"\x00\xff")
        for name in ("config.json", "config.json.gz"):
            with self.subTest(name=name):
                path = self.directory / name
                self.files.write_json(path, {"era": "2025", "count": 2})
                self.assertEqual(self.files.read_json(path), {"era": "2025", "count": 2})
                self.assertIn('  "era":', self.files.read_text(path))
                if name.endswith(".gz"):
                    self.assertTrue(self.files.read_bytes(path).startswith(b"\x1f\x8b"))

    def test_overwrite_and_read_failure_do_not_create_directories(self):
        path = self.directory / "file.txt"
        self.files.write_text(path, "original")
        with self.assertRaises(FileExistsError):
            self.files.write_text(path, "replacement")
        self.assertEqual(self.files.read_text(path), "original")
        self.files.write_text(path, "replacement", overwrite=True)
        self.assertEqual(self.files.read_text(path), "replacement")
        missing = self.directory / "missing" / "file.json"
        with self.assertRaises(FileNotFoundError):
            self.files.read_json(missing)
        with self.assertRaises(FileNotFoundError):
            self.files.write_json(missing, {})
        self.assertFalse(missing.parent.exists())
        self.files.write_text(self.directory / "invalid.json", "{")
        with self.assertRaises(json.JSONDecodeError):
            self.files.read_json(self.directory / "invalid.json")

    def test_csv_yaml_and_missing_yaml_dependency(self):
        path = self.directory / "rows.csv"
        rows = [["name", "value"], ["comma, quote\"", "line\nnext"]]
        self.files.write_csv(path, rows)
        self.assertEqual(self.files.read_csv(path), rows)
        try:
            import yaml
        except ModuleNotFoundError:
            yaml = None
        if yaml is not None:
            yaml_path = self.directory / "config.yml"
            value = {"year": 2025, "channels": ["mutau", "etau"]}
            self.files.write_yaml(yaml_path, value)
            self.assertEqual(self.files.read_yaml(yaml_path), value)
        with mock.patch.dict(sys.modules, {"yaml": None}):
            with self.assertRaisesRegex(ModuleNotFoundError, "PyYAML"):
                formats.write_yaml({"value": 1})

    def test_template_replacement_is_literal_and_preserves_unknown_tokens(self):
        template = self.directory / "job.template"
        self.files.write_text(template, "$NAME ${NAME}\n$NAME_LONG\nremove me\n$UNKNOWN")
        destination = self.directory / "job.txt"
        self.files.write_template(template, destination, {"NAME": r"C:\new\1"},
                                  excluded_lines=["remove"], appended_lines=["last"])
        self.assertEqual(self.files.read_text(destination), "C:\\new\\1 C:\\new\\1\n$NAME_LONG\n$UNKNOWN\nlast\n")

    def test_directory_listing_globs_copy_move_and_explicit_removal(self):
        nested = self.directory / "nested"
        self.files.make_directory(nested)
        original, copy, moved = [nested / name for name in ("a.txt", "b.txt", "c.txt")]
        self.files.write_text(original, "value")
        self.files.copy_file(original, copy)
        with self.assertRaises(FileExistsError):
            self.files.copy_file(original, copy)
        self.files.move_file(copy, moved)
        self.assertFalse(self.files.exists(copy))
        self.assertEqual(self.files.list_directory(nested, "*.txt"), [str(original), str(moved)])
        self.assertEqual(self.files.list_directory(nested, "a.txt"), [str(original)])
        self.assertEqual(self.files.expand_paths([str(nested / "*.txt")]), [str(original), str(moved)])
        with self.assertRaises(OSError):
            self.files.remove_directory(nested)
        self.assertTrue(original.exists())
        self.files.remove_file(moved)
        self.files.remove_directory(nested, recursive=True)
        self.files.remove_directory(nested, missing_ok=True)
        self.assertFalse(nested.exists())

    def test_merge_protects_destination_and_cleans_staging(self):
        source = self.directory / "source.root"
        destination = self.directory / "merged.root"
        source.write_bytes(b"input")

        def produce_output(arguments, timeout):
            Path(arguments[1]).write_bytes(b"merged")

        with mock.patch.object(commands, "run_command", side_effect=produce_output) as command:
            self.files.merge_root_files([source], destination)
            self.assertEqual(destination.read_bytes(), b"merged")
            with self.assertRaises(FileExistsError):
                self.files.merge_root_files([source], destination)
            command.assert_called_once()
        with mock.patch.object(commands, "run_command", side_effect=RuntimeError("merge failed")):
            with self.assertRaisesRegex(RuntimeError, "merge failed"):
                self.files.merge_root_files([source], destination, overwrite=True)
        self.assertEqual(destination.read_bytes(), b"merged")
        self.assertEqual(sorted(path.name for path in self.directory.iterdir()), ["merged.root", "source.root"])


if __name__ == "__main__":
    unittest.main()
