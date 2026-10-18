# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Regenerate IOInventory.md by inspecting source; never import framework code."""

import ast
from collections import Counter, defaultdict
from pathlib import Path
import re
import warnings

_DIRECTORY = Path(__file__).resolve().parent
_REPOSITORY = _DIRECTORY.parent
_SYSTEMS = ("common", "PicoProducer", "Histogrammer", "Plotter", "Fitter", "Tau_Trigger_SF")
_SOURCE_SUFFIXES = {".py", ".sh", ".C", ".cc", ".cxx", ".cpp", ".h"}
_MAPPINGS = {
    "terminal": "CLI.print_message/print_warning/print_error/print_header/print_table",
    "prompt": "CLI.read_input/confirm",
    "progress": "CLI.update_progress/finish_progress",
    "local": "FileIO text/bytes/lines and filesystem operations",
    "json": "FileIO.read_json/write_json",
    "yaml": "FileIO.read_yaml/write_yaml",
    "csv": "FileIO.read_csv/write_csv",
    "gzip": "FileIO text/structured formats with .gz",
    "template": "FileIO.write_template",
    "root": "FileIO.open_root_file/read_root_histogram/write_root_objects/merge_root_files",
    "canvas": "Export remains owned by Plotter/Fitter; FileIO can transfer the produced file",
    "arguments": "Argument definitions/parsing remain at application entry points",
    "process": "Storage/merge mechanics map to FileIO; workflow/tool decisions stay domain-owned",
}


def _call_categories(name):
    leaf = name.rsplit(".", 1)[-1]
    categories = []
    if name in ("print", "sys.stdout.write", "sys.stderr.write", "sys.stdout.flush", "sys.stderr.flush") or leaf in (
        "info", "verbose", "verb", "warn", "warning", "error", "printheader", "printrow", "printtable",
        "print_header", "print_row", "print_rows",
        "tableheader", "row", "header", "title",
    ):
        categories.append("terminal")
    if name in ("input", "raw_input"):
        categories.append("prompt")
    if leaf in ("LoadingBar", "AddProgressBar", "StopProgressBar"):
        categories.append("progress")
    if name in ("open", "gzip.open") or name.startswith(("os.path.", "shutil.", "glob.")) or leaf in (
        "read_text", "write_text", "read_bytes", "write_bytes", "ensuredir", "ensurefile", "expandfiles", "rmfile",
        "getline", "ensureinit", "iterdir", "rglob",
    ) or name in (
        "os.makedirs", "os.mkdir", "os.listdir", "os.walk", "os.unlink", "os.remove", "os.rename", "os.chmod",
    ):
        categories.append("local")
    for format_name in ("json", "yaml", "csv", "gzip"):
        if name.startswith(format_name + "."):
            categories.append(format_name)
    if leaf == "writetemplate":
        categories.append("template")
    if name in ("TFile", "TFile.Open", "ROOT.TFile", "ROOT.TFile.Open", "TChain") or leaf in (
        "ensureTFile", "ensureTDirectory", "gethist", "Write", "WriteObject", "Snapshot",
    ):
        categories.append("root")
    if leaf in ("SaveAs", "savefig", "saveas"):
        categories.append("canvas")
    if leaf in ("ArgumentParser", "OptionParser", "add_argument", "add_parser", "parse_args", "parse_known_args"):
        categories.append("arguments")
    if name.startswith("subprocess.") or name == "os.system" or leaf in ("Popen", "execute", "dasgoclient"):
        categories.append("process")
    return categories


class _Calls(ast.NodeVisitor):
    def __init__(self):
        self.scope = []
        self.sites = defaultdict(list)

    def _visit_scope(self, node):
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_ClassDef = _visit_scope
    visit_FunctionDef = _visit_scope
    visit_AsyncFunctionDef = _visit_scope

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = ast.unparse(node.func)
        else:
            name = ""
        categories = _call_categories(name)
        if any(owner in ("LoadingBar", "AddProgressBar", "StopProgressBar") for owner in self.scope) and "terminal" in categories:
            categories.append("progress")
        if "writetemplate" in self.scope and "local" in categories:
            categories.append("template")
        for category in categories:
            self.sites[category].append((node.lineno, name, ".".join(self.scope) or "module"))
        self.generic_visit(node)


def _text_sites(source, suffix):
    """Candidate sites for legacy Python, shell, and native source."""
    patterns = {
        "terminal": r"\bprint\b|\b(?:echo|printf)\b|sys\.(?:stdout|stderr)|std::(?:cout|cerr)|LOG\.(?:info|verb|warn|warning|error|header|row)",
        "prompt": r"\b(?:input|raw_input)\s*\(|\bread\s+-[rp]",
        "progress": r"\b(?:LoadingBar|AddProgressBar|StopProgressBar)\b",
        "local": r"\bopen\s*\(|\b(?:shutil|glob)\.|os\.(?:path|makedirs|mkdir|remove|unlink|listdir)|\b(?:cp|mv|rm|mkdir|touch|tee)\s|\b(?:ensuredir|ensurefile|rmfile)\s*\(",
        "json": r"\bjson\.(?:load|dump)",
        "yaml": r"\byaml\.(?:safe_load|safe_dump|load|dump)",
        "csv": r"\bcsv\.(?:reader|writer|DictReader|DictWriter)",
        "gzip": r"\bgzip\.open\b",
        "template": r"\bwritetemplate\s*\(",
        "root": r"\b(?:TFile|TChain|ensureTFile|ensureTDirectory|gethist)\b|(?:\.|->)(?:Write|WriteObject|Snapshot)\s*\(|\bhadd(?:nano)?\b",
        "canvas": r"(?:\.|->)(?:SaveAs|savefig|saveas)\s*\(",
        "arguments": r"\b(?:ArgumentParser|OptionParser|parse_args|add_argument)\b",
        "process": r"\b(?:subprocess|Popen)\b|\bos\.system\b|\bexecute\s*\(|\b(?:xrdfs|xrdcp|gfal-[a-z-]+|uberftp|srmcp|srmrm|srmmkdir|condor_submit|sbatch|qsub|combine|hadd)\b",
    }
    sites = defaultdict(list)
    for number, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "//", "/*", "*")):
            continue
        if suffix in (".py", ".sh"):
            line = line.split("#", 1)[0]
        for category, pattern in patterns.items():
            match = re.search(pattern, line)
            if match:
                sites[category].append((number, match.group(0), "text scan"))
    return sites


def _responsibility(path):
    value = path.as_posix()
    if path.suffix == ".sh":
        return "Shell setup/worker/measurement orchestration", "Startup, environment and workflow decisions"
    if path.suffix != ".py":
        return "Native analysis/plotting helper", "Native execution, scientific calculation and object/schema choices"
    if value.startswith("common/"):
        return "Shared helper: " + path.stem, "Exception/control flow, dynamic imports and ROOT runtime integration"
    if "/samples/" in value or "/config/samples" in value:
        return "Sample catalog/metadata", "Sample selection, dataset identities and normalization"
    if "/storage/" in value:
        return "Dataset/storage helper: " + path.stem, "Site defaults, DAS queries, sample/event decisions and validation"
    if "/batch/" in value:
        return "Scheduler adapter: " + path.stem, "Submission, queue interpretation and retry decisions"
    if "/workers/" in value or "/processors/" in value:
        return "Event worker: " + path.stem, "NanoAODTools/event-loop lifecycle and processing options"
    if "/analysis/" in value:
        return "Analysis/writer: " + path.stem, "Event selection, weights, branches, tree/histogram schemas"
    if "/corrections/" in value or "/correctionlib/" in value or value.startswith("add_"):
        return "Correction helper/recipe: " + path.stem, "Payload schemas, correction evaluation and physics policy"
    if value.startswith("PicoProducer/"):
        return "Production command/configuration: " + path.stem, "Arguments, config defaults, job planning/status/merge validation"
    if value.startswith(("Histogrammer/", "Plotter/")):  # the Plotter was renamed Histogrammer (CL §21)
        return "Plot/sample/histogram helper: " + path.stem, "Selections, histogram calculation, styles and canvas export"
    if value.startswith("Fitter/"):
        return "Fit/measurement helper: " + path.stem, "Model/shape policies, fit execution, diagnostics and scientific keys"
    return "Trigger measurement helper: " + path.stem, "Trigger definitions, efficiency/fit calculations and payload schemas"


def _escape(text):
    return text.replace("|", "\\|").replace("\n", " ").replace("`", "'")


def main():
    records, no_io, counts = [], [], Counter()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        for path in sorted(_REPOSITORY.rglob("*")):
            relative = path.relative_to(_REPOSITORY)
            if path.suffix not in _SOURCE_SUFFIXES or (relative.parts[0] not in _SYSTEMS and len(relative.parts) != 1):
                continue
            source = path.read_text(encoding="utf-8-sig", errors="replace")
            method = "AST"
            if path.suffix == ".py":
                try:
                    tree = ast.parse(source, filename=relative.as_posix())
                    visitor = _Calls()
                    visitor.visit(tree)
                    sites = visitor.sites
                except SyntaxError:
                    method = "legacy text"
                    sites = _text_sites(source, path.suffix)
            else:
                method = "shell text" if path.suffix == ".sh" else "native text"
                sites = _text_sites(source, path.suffix)
            counts[method] += 1
            if sites:
                records.append((relative, method, sites))
            else:
                no_io.append(relative)
    lines = [
        "# Static I/O inventory", "",
        "Generated by `python Utilities/_audit_io.py`. No framework modules are imported or executed.", "",
        "Scope: Python, shell and C/C++ source in common, PicoProducer, Histogrammer, Plotter, Fitter and Tau_Trigger_SF, plus root scripts. Includes scripts under data directories; excludes data payloads, tests and generated Utilities code.", "",
        f"Examined {sum(counts.values())} source files: " + ", ".join(f"{count} {method}" for method, count in sorted(counts.items())) + ".",
        f"Found I/O candidates in {len(records)} files; {len(no_io)} files have no matching direct I/O sites.", "",
        "This is a source mapping, not a runtime call graph. AST sites include qualified owner names and source lines. Legacy Python, shell and native code use conservative text scans; dynamic imports, aliases, multiline shell statements and delegated I/O may need inspection during migration. Encoding/decoding alone is listed with its format, even when file access is delegated.", "",
        "## API mapping", "", "| Category | Proposed boundary |", "|---|---|",
    ]
    lines.extend(f"| {category} | {mapping} |" for category, mapping in _MAPPINGS.items())
    lines.extend([
        "", "Scientific objects, keys, naming/schema conventions, argument parsing, exception policy, dataset discovery, scheduler decisions and validation remain with their owners. Native helpers need an explicit bridge before calling Python APIs. No source listed below is connected to Utilities.", "",
        "## I/O-bearing source files", "",
        "Each category in the Observed I/O column maps to the API table above. Representative sites are shown per category; the count includes all detected sites in that file.", "",
    ])
    for system in (*_SYSTEMS, "Root scripts"):
        subset = [record for record in records if (record[0].parts[0] == system if system != "Root scripts" else len(record[0].parts) == 1)]
        lines.extend([f"### {system}", "", "| Source | Responsibility | Observed I/O and representative sites | Remains domain-owned |", "|---|---|---|---|"])
        for path, method, sites in subset:
            responsibility, owned = _responsibility(path)
            observed = []
            for category, locations in sites.items():
                representative = []
                seen = set()
                for line, name, owner in sorted(locations, key=lambda site: site[2] == "module"):
                    if (name, owner) not in seen:
                        representative.append((line, name, owner))
                        seen.add((name, owner))
                examples = "; ".join(f"{owner}: {name} L{line}" for line, name, owner in representative[:2])
                observed.append(f"**{category}** ({len(locations)}): {_escape(examples)}")
            link = f"[{path.as_posix()}](../{path.as_posix()})"
            lines.append(f"| {link} ({method}) | {_escape(responsibility)} | {'<br>'.join(observed)} | {owned} |")
        lines.append("")
    lines.extend(["## Files without detected direct I/O", "", "These files are included in the audit; delegated or dynamically selected I/O can still exist.", ""])
    lines.extend(f"- [{path.as_posix()}](../{path.as_posix()})" for path in no_io)
    (_DIRECTORY / "IOInventory.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Audited {sum(counts.values())} source files; mapped {len(records)} I/O-bearing files.")


if __name__ == "__main__":
    main()
