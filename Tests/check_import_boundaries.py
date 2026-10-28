#!/usr/bin/env python3
"""Offline stage-isolation check. Known coupling is tracked, but still fails."""
import ast
from collections import Counter
from dataclasses import dataclass
import io
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
import tokenize
import unittest
import warnings


REPO = Path(__file__).resolve().parent.parent
ALLOWLIST = Path(__file__).with_name("import_boundary_allowlist.json")
STAGES = ("PicoProducer", "Histogrammer", "Plotter", "Fitter")  # Histogrammer: the former Plotter (CL §21)
PACKAGES = STAGES + ("Framework", "Utilities", "common")
EXCLUDED = {"Legacy", "legacy", "LegacyAnalyses", "Tests", "__pycache__"}
IMPLICIT_ROOTS = {"config", "plot", "sample"}
APIS = {"TauFW." + stage + ".api" for stage in STAGES}
INTERNAL = "TauFW.Utilities.Internal"  # TauFW's own tools (menu, editor, installer, operations): not for the stages


@dataclass(frozen=True)
class Violation:
    file: str
    line: int
    importer: str
    module: str
    target: str

    @property
    def key(self):
        return self.file, self.module


@dataclass(frozen=True)
class ParseFailure:
    file: str
    line: int
    message: str


def parse(source, filename):
    # Python 3.12+ warns about old string escapes; these are not import failures.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        return ast.parse(source, filename=filename)


def import_nodes(source, filename):
    """Return import nodes, full-file parse failure, and import-recovery errors.

    Python 2 statements prevent a full AST. Tokenize only as a fallback, then
    AST-parse each complete import statement without executing or rewriting code.
    """
    try:
        tree = parse(source, filename)
    except SyntaxError as error:
        failure = ParseFailure(filename, error.lineno or 1, error.msg)
    else:
        return [node for node in ast.walk(tree)
                if isinstance(node, (ast.Import, ast.ImportFrom))], None, []

    tokens, errors, nodes = [], [], []
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            tokens.append(token)
    except (tokenize.TokenError, IndentationError, SyntaxError) as error:
        errors.append("%s: tokenization failed: %s" % (filename, error))
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.type != tokenize.NAME or token.string not in ("from", "import"):
            index += 1
            continue
        end = index + 1
        while end < len(tokens):
            item = tokens[end]
            if item.type in (tokenize.NEWLINE, tokenize.ENDMARKER):
                break
            if item.type == tokenize.OP and item.string == ";":
                break
            end += 1
        fragment = tokenize.untokenize([(item.type, item.string) for item in tokens[index:end]])
        try:
            tree = parse(fragment, filename)
        except SyntaxError as error:
            errors.append("%s:%s: import recovery failed: %s" %
                          (filename, token.start[0], error.msg))
        else:
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    node.lineno += token.start[0] - 1
                    nodes.append(node)
        index = end
    return nodes, failure, errors


def imported_modules(node):
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if node.level:
        return []  # Relative imports stay inside the owning package.
    module = node.module or ""
    parts = module.split(".")
    if module in ("TauFW", "TauFW.Utilities") or (len(parts) == 2 and parts[0] == "TauFW" and parts[1] in STAGES):
        return [module + "." + alias.name for alias in node.names if alias.name != "*"] or [module]
    if module in IMPLICIT_ROOTS:
        return [module + "." + alias.name for alias in node.names if alias.name != "*"] or [module]
    return [module]


def inspect_source(source, relative_file, root):
    path = PurePosixPath(relative_file)
    importer = path.parts[0]
    nodes, failure, errors = import_nodes(source, relative_file)
    violations = []
    for node in nodes:
        for module in imported_modules(node):
            parts = module.split(".")
            target = None
            if module == INTERNAL or module.startswith(INTERNAL + "."):
                # the stages and the public Utilities packages never use Internal; the Framework and Internal do
                if importer in STAGES or (importer == "Utilities" and "Internal" not in path.parts):
                    target = "Utilities.Internal"
            elif len(parts) >= 2 and parts[0] == "TauFW" and parts[1] in STAGES:
                if parts[1] != importer and not (importer == "Framework" and module in APIS):
                    target = parts[1]
            elif importer in STAGES and parts[0] in IMPLICIT_ROOTS:
                local = Path(root).joinpath(*path.parent.parts, *parts)
                own = Path(root).joinpath(importer, *parts)  # in the module's own config/ (from a subdirectory, CL §22)
                if not any(found.with_suffix(".py").is_file() or found.is_dir() for found in (local, own)):
                    candidates = []
                    for stage in STAGES:
                        if stage == importer:
                            continue
                        for base in (Path(root) / stage, Path(root) / stage / "python"):
                            other = base.joinpath(*parts)
                            if other.with_suffix(".py").is_file() or other.is_dir():
                                candidates.append(stage)
                                break
                    target = candidates[0] if len(candidates) == 1 else "implicit:" + parts[0]
            if target:
                violations.append(Violation(relative_file, node.lineno, importer, module, target))
    return violations, failure, errors


def source_files(root):
    for package in PACKAGES:
        for directory, children, files in os.walk(Path(root) / package):
            children[:] = sorted(child for child in children if child not in EXCLUDED)
            for name in sorted(files):
                if name.endswith(".py"):
                    yield Path(directory) / name


def scan_repository(root):
    violations, failures, errors = [], [], []
    root = Path(root)
    for path in source_files(root):
        relative = path.relative_to(root).as_posix()
        with tokenize.open(path) as stream:
            source = stream.read()
        found, failure, recovery_errors = inspect_source(source, relative, root)
        violations.extend(found)
        if failure:
            failures.append(failure)
        errors.extend(recovery_errors)
    return sorted(violations, key=lambda v: (v.file, v.line, v.module)), failures, errors


def load_allowlist(path):
    with Path(path).open(encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, dict) or set(data) != {"imports", "unparseable"}:
        raise ValueError("Allowlist must contain exactly imports and unparseable lists")
    imports, unparseable = {}, {}
    for kind, destination in (("imports", imports), ("unparseable", unparseable)):
        if not isinstance(data[kind], list):
            raise ValueError("%s must be a list" % kind)
        fields = {"file", "reason", "roadmap_step"} | ({"module"} if kind == "imports" else set())
        for entry in data[kind]:
            if not isinstance(entry, dict) or set(entry) != fields or any(
                    not isinstance(value, str) or not value.strip() for value in entry.values()):
                raise ValueError("Malformed %s entry: %r" % (kind, entry))
            file = entry["file"]
            parts = PurePosixPath(file).parts
            if ("\\" in file or not parts or parts[0] not in PACKAGES or ".." in parts
                    or any(part in EXCLUDED for part in parts) or not file.endswith(".py")
                    or PurePosixPath(file).as_posix() != file):
                raise ValueError("Invalid allowlist file: %s" % file)
            if kind == "imports" and any(not part.isidentifier() for part in entry["module"].split(".")):
                raise ValueError("Invalid imported module: %s" % entry["module"])
            key = (file, entry["module"]) if kind == "imports" else file
            if key in destination:
                raise ValueError("Duplicate %s entry: %r" % (kind, key))
            destination[key] = entry
    return imports, unparseable


def debt_status(violations, failures, recovery_errors, imports, unparseable):
    observed = {violation.key for violation in violations}
    failed_files = {failure.file for failure in failures}
    return {
        "new": observed - set(imports),
        "stale_imports": set(imports) - observed,
        "unapproved_parse": failed_files - set(unparseable),
        "stale_parse": set(unparseable) - failed_files,
        "failed": bool(violations or recovery_errors or failed_files - set(unparseable)
                       or set(imports) - observed or set(unparseable) - failed_files),
    }


def format_report(violations, failures, recovery_errors, imports, unparseable):
    status = debt_status(violations, failures, recovery_errors, imports, unparseable)
    lines = ["Import-boundary violations (known debt also fails):"]
    for item in violations:
        lines.append("%s:%s: %s -> %s [%s]" %
                     (item.file, item.line, item.importer, item.module,
                      "KNOWN" if item.key in imports else "NEW"))
    lines.append("Full-file parse failures (imports inspected with tokenizer/AST fallback):")
    for item in sorted(failures, key=lambda item: item.file):
        lines.append("%s:%s: [%s] %s" % (item.file, item.line,
                     "EXEMPT" if item.file in unparseable else "UNAPPROVED", item.message))
    lines.extend("RECOVERY ERROR: " + error for error in recovery_errors)
    lines.extend("STALE import: %s -> %s" % entry for entry in sorted(status["stale_imports"]))
    lines.extend("STALE unparseable: " + file for file in sorted(status["stale_parse"]))
    counts = Counter((item.importer, item.target) for item in violations)
    lines.append("Coupling totals (occurrences / file-module pairs / files):")
    for importer, target in sorted(counts):
        members = [item for item in violations if (item.importer, item.target) == (importer, target)]
        lines.append("%s -> %s: %s / %s / %s" %
                     (importer, target, len(members), len({item.key for item in members}),
                      len({item.file for item in members})))
    lines.append("TOTAL: %s occurrences, %s file-module pairs, %s files; %s new pairs; %s parse failures" %
                 (len(violations), len({item.key for item in violations}), len({item.file for item in violations}),
                  len(status["new"]), len(failures)))
    return "\n".join(lines)


class DetectorTests(unittest.TestCase):
    def inspect(self, source, file="Fitter/example.py", root="."):
        return inspect_source(source, file, root)

    def test_direct_and_function_imports(self):
        found, failure, errors = self.inspect(
            "import TauFW.Plotter.sample.utils as u\ndef f():\n    from TauFW.PicoProducer.settings import getconfig\n")
        self.assertEqual([(item.line, item.module) for item in found],
                         [(1, "TauFW.Plotter.sample.utils"), (3, "TauFW.PicoProducer.settings")])
        self.assertIsNone(failure)
        self.assertEqual(errors, [])

    def test_framework_api_and_parent_forms(self):
        found, _, _ = self.inspect(
            "from TauFW.Plotter.api import ControlPlots\nfrom TauFW.Fitter import api\n"
            "import TauFW.PicoProducer.api\nimport TauFW.Plotter.api.control_plots\n"
            "from TauFW import Plotter\nfrom TauFW.Fitter import plot\n", "Framework/example.py")
        self.assertEqual([item.module for item in found],
                         ["TauFW.Plotter.api.control_plots", "TauFW.Plotter", "TauFW.Fitter.plot"])

    def test_self_libraries_relative_and_parent_stage_import(self):
        found, _, _ = self.inspect(
            "import TauFW.Fitter.plot\nfrom TauFW.Utilities.Drawing import Plot\n"
            "from TauFW.common.tools import file\nfrom . import plot\nfrom TauFW import PicoProducer\n")
        self.assertEqual([item.module for item in found], ["TauFW.PicoProducer"])
        self.assertEqual(len(self.inspect("import TauFW.Plotter.api")[0]), 1)
        self.assertEqual(len(self.inspect("import TauFW.Plotter.api", "Utilities/example.py")[0]), 1)

    def test_histogrammer_and_plotter_are_separate_stages(self):
        """CL §21: the Histogrammer (the former Plotter) and the new Plotter never import each other; the Framework
        may import the Histogrammer's API only; the Fitter takes histogram files, not the Histogrammer."""
        found, _, _ = self.inspect("import TauFW.Histogrammer.sample.utils as _module",
                                   "Plotter/python/sample/utils.py")
        self.assertEqual([(item.module, item.target) for item in found],
                         [("TauFW.Histogrammer.sample.utils", "Histogrammer")])
        found, _, _ = self.inspect("from TauFW.Plotter.sample.utils import setera", "Histogrammer/fillhists.py")
        self.assertEqual([item.target for item in found], ["Plotter"])
        self.assertEqual(self.inspect("from TauFW.Histogrammer.api import ControlPlots", "Framework/x.py")[0], [])
        self.assertEqual(len(self.inspect("from TauFW.Histogrammer.sample import model", "Framework/x.py")[0]), 1)
        self.assertEqual([item.target for item in self.inspect("import TauFW.Histogrammer.spec.Variable")[0]],
                         ["Histogrammer"])  # the Fitter (default importer) takes files, not the Histogrammer

    def test_utilities_internal_is_framework_only(self):
        """The menu, editor, installer and operations (Utilities/python/Internal) are TauFW's own tools: the stages
        and the public Utilities packages never import them; the Framework and Internal itself do."""
        source = ("from TauFW.Utilities.Internal.Menu import ConsoleUI\nfrom TauFW.Utilities import Internal\n"
                  "from TauFW.Utilities.Process import Command\nfrom TauFW.Utilities import FIO\n")
        found, _, _ = self.inspect(source, "PicoProducer/python/x.py")
        self.assertEqual([(item.module, item.target) for item in found],
                         [("TauFW.Utilities.Internal.Menu", "Utilities.Internal"),
                          ("TauFW.Utilities.Internal", "Utilities.Internal")])
        self.assertEqual(len(self.inspect(source, "Utilities/python/Drawing/x.py")[0]), 2)
        self.assertEqual(self.inspect(source, "Framework/python/x.py")[0], [])
        self.assertEqual(self.inspect(source, "Utilities/python/Internal/Menu/x.py")[0], [])

    def test_implicit_and_local_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            local = Path(directory) / "Fitter/Zpt/config"
            local.mkdir(parents=True)
            (local / "samples.py").write_text("", encoding="utf-8")
            source = "from config.samples import *\nfrom config import samples_v15\nimport plot.helpers\nimport sample.utils\n"
            found, _, _ = self.inspect(source, "Fitter/Zpt/example.py", directory)
            self.assertEqual([item.module for item in found],
                             ["config.samples_v15", "plot.helpers", "sample.utils"])
            self.assertEqual(len(self.inspect(source, "Fitter/tutorial/example.py", directory)[0]), 4)
            # a script in a subdirectory of the module that owns config/ (Histogrammer/shapes/TauES, CL §22)
            own = Path(directory) / "Histogrammer/config"
            own.mkdir(parents=True)
            (own / "samples_v15.py").write_text("", encoding="utf-8")
            found, _, _ = self.inspect("from config.samples_v15 import *\nfrom config.samples_v12 import *\n",
                                       "Histogrammer/shapes/TauES/x.py", directory)
            self.assertEqual([item.module for item in found], ["config.samples_v12"])  # only the missing one

    def test_python2_multiline_function_comments_and_strings(self):
        source = ('print "old syntax"\n# import TauFW.Plotter.fake\n'
                  'text = "from TauFW.Plotter.fake import x"\ndef f():\n'
                  '    from TauFW.Plotter.sample.utils import (\n        setera,\n        getsampleset,\n    )\n'
                  '    import TauFW.PicoProducer.settings; import TauFW.Plotter.plot.Variable\n')
        found, failure, errors = self.inspect(source)
        self.assertEqual(failure.line, 1)
        self.assertEqual([(item.line, item.module) for item in found],
                         [(5, "TauFW.Plotter.sample.utils"), (9, "TauFW.PicoProducer.settings"),
                          (9, "TauFW.Plotter.plot.Variable")])
        self.assertEqual(errors, [])

    def test_allowlisted_debt_still_fails_and_new_and_stale(self):
        found, _, _ = self.inspect("import TauFW.Plotter.sample.utils")
        imports = {found[0].key: {}}
        status = debt_status(found, [], [], imports, {})
        self.assertTrue(status["failed"])
        self.assertEqual(status["new"], set())
        self.assertEqual(debt_status(found, [], [], {}, {})["new"], set(imports))
        stale = debt_status([], [], [], imports, {})
        self.assertTrue(stale["failed"])
        self.assertEqual(stale["stale_imports"], set(imports))
        self.assertFalse(debt_status([], [], [], {}, {})["failed"])

    def test_parse_exemptions_and_stale_exemption(self):
        _, failure, _ = self.inspect('print "old"\n')
        self.assertTrue(debt_status([], [failure], [], {}, {})["failed"])
        exemptions = {failure.file: {}}
        self.assertFalse(debt_status([], [failure], [], {}, exemptions)["failed"])
        self.assertEqual(debt_status([], [], [], {}, exemptions)["stale_parse"], set(exemptions))
        self.assertTrue(debt_status([], [], [], {}, exemptions)["failed"])

    def test_recovery_failure_cannot_be_exempted(self):
        _, failure, errors = self.inspect('print "old"\nfrom TauFW.Plotter import (\n')
        self.assertTrue(errors)
        self.assertTrue(debt_status([], [failure], errors, {}, {failure.file: {}})["failed"])

    def test_exclusions(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("Fitter/Legacy/x.py", "Fitter/legacy/x.py", "Fitter/LegacyAnalyses/x.py",
                         "Fitter/Tests/x.py", "Tests/x.py", "Fitter/current.py"):
                path = Path(directory) / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("import TauFW.Plotter.sample.utils", encoding="utf-8")
            found, _, _ = scan_repository(directory)
            self.assertEqual([item.file for item in found], ["Fitter/current.py"])

    def test_allowlist_validation(self):
        entry = {"file": "Fitter/example.py", "module": "TauFW.Plotter.sample.utils",
                 "reason": "Existing coupling", "roadmap_step": "4"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "debt.json"
            path.write_text(json.dumps({"imports": [entry], "unparseable": []}), encoding="utf-8")
            self.assertEqual(set(load_allowlist(path)[0]), {("Fitter/example.py", entry["module"])})
            invalid = [dict(entry, reason=""), dict(entry, file="Fitter/../x.py"),
                       dict(entry, module="TauFW.Plotter.*")]
            for entries in ([entry, entry],) + tuple([item] for item in invalid):
                path.write_text(json.dumps({"imports": entries, "unparseable": []}), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_allowlist(path)


class RepositoryBoundaryTests(unittest.TestCase):
    def test_repository_import_boundaries(self):
        imports, unparseable = load_allowlist(ALLOWLIST)
        violations, failures, errors = scan_repository(REPO)
        report = format_report(violations, failures, errors, imports, unparseable)
        self.assertFalse(debt_status(violations, failures, errors, imports, unparseable)["failed"], report)
        print(report)


if __name__ == "__main__":
    unittest.main(verbosity=2)
