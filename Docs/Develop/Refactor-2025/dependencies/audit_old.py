"""Read a historical Git tree; write documentation only. Never import TauFW code.

Usage: python Docs/Develop/Refactor-2025/dependencies/audit_old.py
Python 3.9+; standard library only. The baseline is the first refactor commit's parent.
"""
import ast
import csv
import io
import re
import subprocess
import tokenize
import warnings
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
BASE = "949ce56^"
STAGES = {"PicoProducer", "Plotter", "Fitter", "Tau_Trigger_SF"}
CODE = {".py", ".sh", ".bash", ".csh", ".sub", ".C", ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".xml", ".yml", ".yaml", ".json", ".txt", ".csv"}
SHELL = {".sh", ".bash", ".csh"}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=REPO)


def snapshot():
    revision = git("rev-parse", BASE).decode().strip()
    paths = git("ls-tree", "-r", "--name-only", revision).decode().splitlines()
    write_csv("old-tracked-files.csv", ["file", "extension", "scanned_as_text"],
              [dict(file=p, extension=Path(p).suffix, scanned_as_text=Path(p).suffix in CODE) for p in paths])
    paths = [p for p in paths if Path(p).suffix in CODE]
    requests = "".join(revision + ":" + p + "\n" for p in paths).encode()
    result = subprocess.run(["git", "cat-file", "--batch"], input=requests,
                            stdout=subprocess.PIPE, check=True, cwd=REPO)
    stream = io.BytesIO(result.stdout)
    sources = {}
    for path in paths:
        header = stream.readline().split()
        assert len(header) == 3 and header[1] == b"blob", (path, header)
        data = stream.read(int(header[2]))
        assert stream.read(1) == b"\n"
        try:
            encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
        except SyntaxError:
            encoding = "utf-8"
        sources[path] = data.decode(encoding, errors="replace")
    return revision, sources


def imports(source, path):
    """Retain Python 2 imports instead of discarding an unparseable file."""
    failure, recovery = None, []
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source, filename=path)
    except SyntaxError as error:
        failure = (path, error.lineno, error.msg)
    else:
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        found = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            context = []
            ancestor = parents.get(node)
            while ancestor:
                if isinstance(ancestor, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    context.append("function:" + ancestor.name)
                elif isinstance(ancestor, (ast.If, ast.Try)):
                    context.append(type(ancestor).__name__.lower())
                ancestor = parents.get(ancestor)
            found.append((node, "/".join(reversed(context)) or "module"))
        return found, failure, recovery
    # Indentation is irrelevant to recovering an import statement. Neutralize it
    # only for tokenization, preserving strings/comments as token kinds and lines.
    token_source = "\n".join(line.lstrip(" \t") for line in source.split("\n"))
    tokens = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(token_source).readline))
    except (tokenize.TokenError, IndentationError) as error:
        # Collect the valid prefix too; the error is prominently reported.
        iterator = tokenize.generate_tokens(io.StringIO(token_source).readline)
        try:
            while True:
                tokens.append(next(iterator))
        except StopIteration:
            pass
        except (tokenize.TokenError, IndentationError):
            pass
        recovery.append(str(error))
    found, index = [], 0
    while index < len(tokens):
        token = tokens[index]
        if token.type != tokenize.NAME or token.string not in {"import", "from"}:
            index += 1
            continue
        end, depth = index + 1, 0
        while end < len(tokens):
            item = tokens[end]
            if item.type == tokenize.ENDMARKER or (item.type in {tokenize.NEWLINE, tokenize.NL} and depth == 0):
                break
            if tokens[end].string == ";":
                break
            if item.type == tokenize.OP:
                depth += int(item.string in "([{") - int(item.string in ")]}")
            end += 1
        fragment = tokenize.untokenize([(t.type, t.string) for t in tokens[index:end]])
        try:
            tree = ast.parse(fragment)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    node.lineno += token.start[0] - 1
                    found.append((node, "recovered; context unknown"))
        except SyntaxError as error:
            recovery.append("line %s: %s" % (token.start[0], error.msg))
        index = end
    return found, failure, recovery


def module_name(path):
    parts = path[:-3].split("/")
    if len(parts) > 1 and parts[1] == "python":
        parts.pop(1)
        parts.insert(0, "TauFW")
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def owner(path):
    return path.split("/")[0] if "/" in path else "root"


def is_test(path):
    return any(p.lower() in {"test", "tests"} for p in path.split("/")) or path.endswith("/TestModule.py")


def resolve(module, file, modules, sources):
    if module in modules:
        return modules[module], "exact module"
    # SCRAM package parents can exist without a tracked __init__.py.
    if any(m.startswith(module + ".") for m in modules):
        return [], "repository package"
    if module.startswith("TauFW."):
        return [], "unresolved TauFW namespace"
    local = str(Path(file).parent / (module.replace(".", "/") + ".py")).replace("\\", "/")
    if local in sources:
        return [local], "script-local module"
    suffix = "/" + module.replace(".", "/") + ".py"
    candidates = sorted(p for p in sources if p.endswith(suffix))
    if candidates:
        path_lines = [line for line in sources[file].splitlines() if "sys.path." in line and not line.lstrip().startswith("#")]
        for line in path_lines:
            match = re.search(r"['\"]([^'\"]*Plotter(?:/[^'\"]*)?)['\"]", line)
            if match:
                hint = match.group(1).split("Plotter", 1)[1].strip("/")
                expected = "Plotter/" + (hint + "/" if hint else "") + module.replace(".", "/") + ".py"
                if expected in candidates:
                    return [expected], "explicit sys.path hint (CWD-dependent)"
            for candidate in candidates:
                parent = Path(candidate).parent.name
                if parent != Path(file).parent.name and re.search(r"['\"]" + re.escape(parent) + r"['\"]", line):
                    matching = [p for p in candidates if Path(p).parent.name == parent]
                    if len(matching) == 1:
                        return matching, "explicit sys.path hint"
        return candidates, "implicit path candidate" if len(candidates) == 1 else "ambiguous path candidates"
    return [], "external or unresolved bare module"


PATTERNS = {
    "dynamic loader / native code": r"import_module\s*\(|__import__\s*\(|ensuremodule\s*\(|loadmacro\s*\(|LoadMacro\s*\(|ProcessLine\s*\(|gInterpreter\.(Declare|ProcessLine)|gSystem\.Load",
    "command / process": r"os\.(system|popen)\s*\(|subprocess\.|\b(Popen|check_call|check_output|execute)\s*\(",
    "path / environment / cwd": r"sys\.path|os\.(chdir|environ|getenv)|expandvars\s*\(|\$\{?[A-Za-z_]|CMSSW_BASE",
    "ROOT global / class patch": r"SetBatch\s*\(|PyConfig\.|SetDefaultSumw2\s*\(|EnableImplicitMT\s*\(|DisableImplicitMT\s*\(|(?:SampleSet|Sample|TGraph|TNamed|RDataFrame)\.\w+\s*=|setattr\s*\(",
    "persistent config / implicit state": r"\bgetconfig\s*\(|\bCONFIG\b|\bglobal\s+|GLOB\.(lumi|era|cme)|CMSStyle\.(lumi_dict|setCMSEra)",
    "ROOT / file / serialized data IO": r"ensureTFile\s*\(|TFile\.(Open|OpenFile)|\bTFile\s*\(|\bopen\s*\(|json\.(load|dump)|yaml\.(load|safe_load)|\.Write\s*\(|\.SaveAs\s*\(",
    "data schema / histogram contract": r"addBranch\s*\(|\bcutflow\b|\b(sumweights|binsumw|binnevts)\b|RDataFrame\s*\(|\.Get\s*\(|gethists\s*\(|\bcreateinputs\s*\(|\bSetBranchAddress\s*\(",
    "live module / writer / sample / event state": r"\bmodule\.\w+|getattr\s*\(module|self\.module|self\.out\.|\b(?:event|tau|muon|electron|jet)\.\w+\s*[*+/-]?=|\b(?:sample|sampleset)\.(?:files|filenevts|jobcfg|getfiles|getnevents|shift|stitch|split|join)\b",
    "external tool command / command string": r"\b(?:hadd(?:nano)?|combine(?:Tool)?|combinetf|text2workspace|PostFitShapesFromWorkspace|dasgoclient|condor_submit|condor_q|qsub|qstat|xrdcp|xrdfs|gfal-\w+|scram)\b",
    "resource / payload / filename convention": r"['\"][^'\"\n]*\.(root|json|csv|yaml|yml|txt|so|C|cc|cpp|h)(?:['\"]|[^a-zA-Z])|jsonpog|datadir|effsdir",
    "host / user / site assumption": r"platform\.node|getpass\.getuser|/eos/|/pnfs/|lxplus|psi\.ch|desy\.de|SCRAM_ARCH",
    "C/C++ include": r"^\s*#\s*include\b",
    "build / environment dependency": r"<use\s+name=|<lib\s+name=|\bscram\b|\bcmsenv\b",
}


def md(value):
    return str(value).replace("|", "&#124;").replace("\n", " ").replace("`", "'")


def write_csv(name, fields, rows):
    with (OUT / name).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def cycles(rows):
    adjacent = defaultdict(set)
    for row in rows:
        if not row["test"] and row["resolution"] in {"exact module", "script-local module"}:
            adjacent[row["file"]].update(row["target_files"].split("; "))
    indices, low, stack, active, components = {}, {}, [], set(), []

    def visit(node):
        indices[node] = low[node] = len(indices)
        stack.append(node)
        active.add(node)
        for child in sorted(adjacent[node]):
            if child not in indices:
                visit(child)
                low[node] = min(low[node], low[child])
            elif child in active:
                low[node] = min(low[node], indices[child])
        if low[node] == indices[node]:
            component = []
            while True:
                child = stack.pop()
                active.remove(child)
                component.append(child)
                if child == node:
                    break
            if len(component) > 1:
                components.append(sorted(component))

    for node in sorted(list(adjacent)):
        if node not in indices:
            visit(node)
    return sorted(components)


def main():
    revision, sources = snapshot()
    modules = defaultdict(list)
    for path in sources:
        if path.endswith(".py"):
            modules[module_name(path)].append(path)
    rows, failures, recovery_errors, evidence = [], [], [], []
    file_rows = []
    for path, source in sorted(sources.items()):
        file_rows.append(dict(file=path, owner=owner(path), lines=len(source.splitlines()),
                              test=is_test(path), language=Path(path).suffix))
        if path.endswith(".py"):
            nodes, failure, errors = imports(source, path)
            if failure:
                failures.append(failure)
            recovery_errors.extend((path, error) for error in errors)
            for node, context in sorted(nodes, key=lambda item: item[0].lineno):
                if isinstance(node, ast.Import):
                    entries = [(a.name, "", a.asname or "") for a in node.names]
                else:
                    module = "." * node.level + (node.module or "")
                    if node.level:
                        base = module_name(path).split(".")
                        if not path.endswith("/__init__.py"):
                            base.pop()
                        module = ".".join(base[:len(base) - node.level + 1] + ([node.module] if node.module else []))
                    entries = [(module, ", ".join(a.name + (" as " + a.asname if a.asname else "") for a in node.names), "")]
                    # Expand parent imports of actual modules; other symbols stay in the symbols column.
                    children = [module + "." + a.name for a in node.names]
                    if children and all(child in modules for child in children):
                        entries = [(child, "", a.asname or "") for child, a in zip(children, node.names)]
                for module, symbols, alias in entries:
                    targets, status = resolve(module, path, modules, sources)
                    target_owners = sorted({owner(p) for p in targets})
                    if module.startswith("TauFW.") and len(module.split(".")) > 1:
                        target_owners = [module.split(".")[1]]
                    target_owner = "; ".join(target_owners)
                    rows.append(dict(file=path, line=node.lineno, owner=owner(path), test=is_test(path),
                                     context=context, module=module, symbols=symbols, alias=alias,
                                     wildcard="*" in symbols, target_owner=target_owner,
                                     target_files="; ".join(targets), resolution=status,
                                     cross_stage=owner(path) in STAGES and len(target_owners) == 1
                                     and target_owners[0] in STAGES and target_owners[0] != owner(path)))
        # Evidence is deliberately separate from confirmed imports. All matches are retained.
        for lineno, line in enumerate(source.splitlines(), 1):
            stripped = line.strip()
            if not stripped or (stripped.startswith("#") and not re.match(r"#\s*include\b", stripped)):
                continue
            if stripped.startswith("//"):
                continue
            kinds = [kind for kind, pattern in PATTERNS.items() if re.search(pattern, line)]
            if Path(path).suffix in SHELL:
                kinds.append("shell statement (review tool / path / workflow dependencies)")
            if path.endswith(".sub"):
                kinds.append("batch submission template statement")
            if kinds:
                evidence.append(dict(file=path, line=lineno, owner=owner(path), test=is_test(path),
                                     kinds="; ".join(kinds), evidence=line.strip()))
    write_csv("old-imports.csv", list(rows[0]), rows)
    write_csv("old-other-evidence.csv", list(evidence[0]), evidence)
    write_csv("old-source-files.csv", list(file_rows[0]), file_rows)
    production = [row for row in rows if not row["test"]]
    cross = [row for row in production if row["cross_stage"]]
    counts = Counter((row["owner"], row["target_owner"]) for row in cross)
    lines = ["# Historical dependency evidence", "", "Baseline: `" + revision + "` (`949ce56^`, before Test Migration 1).",
             "", "Generated by [audit_old.py](audit_old.py). Sources are read from Git; no TauFW module is imported.", "",
             "No legacy, data, correction, auxiliary, or test source directories are excluded. Tests are identified separately.",
             "All Python imports are listed, including standard-library/external imports, aliases, imported symbols, wildcard imports, and imports inside functions/conditions.",
             "Python 2 files are recovered by tokenizing import statements. Counts are import records, not symbol counts or runtime calls.",
             "[old-tracked-files.csv](old-tracked-files.csv) lists every tracked path, including binary ROOT payloads and documentation. Binary contents are not interpreted.", "",
             "The non-import evidence is a line-pattern inventory, **not a claim that every match is an executed dependency**. Strings, docstrings, inline comments and disabled code can match; retain these for review.",
             "Dynamic names, installed namespace aliases, generated paths and ROOT expression semantics cannot be fully resolved statically. The inventory exposes uncertainty instead of dropping it.", "",
             "## Coverage", "", "| Item | Count |", "|---|---:|",
             f"| Source/build/config files scanned | {len(sources)} |",
             f"| Python files, including tests and data scripts | {sum(p.endswith('.py') for p in sources)} |",
             f"| Python import records, all files | {len(rows)} |",
             f"| Python import records, excluding embedded tests | {len(production)} |",
             f"| Stage-to-stage import records, excluding tests | {len(cross)} |",
             f"| Wildcard import records, excluding tests | {sum(r['wildcard'] for r in production)} |",
             f"| Python files requiring import recovery | {len(failures)} |",
             f"| Import recovery errors | {len(recovery_errors)} |",
             f"| Non-import evidence lines | {len(evidence)} |", "", "## Stage-to-stage imports", "",
             "| From | To | Records | Caller files |", "|---|---|---:|---:|"]
    for (start, end), count in sorted(counts.items()):
        lines.append(f"| {start} | {end} | {count} | {len({r['file'] for r in cross if (r['owner'], r['target_owner']) == (start, end)})} |")
    lines += ["", "These include unresolved stage namespaces (for example an import of a missing Plotter datacard module) and explicitly labelled implicit-path candidates.", "",
              "## Every stage-to-stage import site", "", "| Historical source | Module | Imported symbols | Resolution |", "|---|---|---|---|"]
    for row in cross:
        lines.append(f"| `{row['file']}:{row['line']}` | `{row['module']}` | `{md(row['symbols'] or row['alias'])}` | {row['resolution']} |")
    lines += ["", "## Every exact import-cycle component", "",
              "Strongly connected file components using exact-module and script-local edges, excluding tests. Conditional/function imports still count; this does not prove runtime recursion.",
              "The separate PicoProducer / Plotter **package** cycle is visible above; it need not be a single file-level cycle."]
    for component in cycles(rows):
        lines += ["", f"### {len(component)} mutually reachable files", "", *("- `" + path + "`" for path in component)]
    lines += ["", "## Ambiguous and unresolved repository imports", "", "| Historical source | Module | Status | Candidate files |", "|---|---|---|---|"]
    for row in rows:
        if "ambiguous" in row["resolution"] or "unresolved TauFW" in row["resolution"]:
            lines.append(f"| `{row['file']}:{row['line']}` | `{row['module']}` | {row['resolution']} | {md(row['target_files'])} |")
    lines += ["", "## Python parse failures (imports still recovered)", "", "| Historical source | Parse error |", "|---|---|"]
    for path, lineno, error in failures:
        lines.append(f"| `{path}:{lineno}` | {md(error)} |")
    lines += ["", "## Import recovery errors", "", *(f"- `{p}`: {md(e)}" for p, e in recovery_errors)] if recovery_errors else ["", "Import recovery completed without errors."]
    lines += ["", "## All non-import evidence", "",
              "Every matching line is below, grouped by owner. Use [old-other-evidence.csv](old-other-evidence.csv) to filter by mechanism."]
    for system in sorted({r["owner"] for r in evidence}):
        lines += ["", "<details>", f"<summary>{system}: all path, state, IO, command, schema, native/build evidence</summary>", "",
                  "| Historical source | Mechanisms | Exact source line |", "|---|---|---|"]
        for row in evidence:
            if row["owner"] == system:
                lines.append(f"| `{row['file']}:{row['line']}` | {row['kinds']} | `{md(row['evidence'])}` |")
        lines += ["", "</details>"]
    lines += ["", "## Every Python import", "", "Full import details: [old-imports.csv](old-imports.csv). No import edges are cut off for readability."]
    for system in sorted({r["owner"] for r in rows}):
        lines += ["", "<details>", f"<summary>{system}: every import, including external and standard library</summary>", "",
                  "| Historical source | Module | Symbols / alias | Context | Resolution |", "|---|---|---|---|---|"]
        for row in rows:
            if row["owner"] == system:
                lines.append(f"| `{row['file']}:{row['line']}` | `{row['module']}` | `{md(row['symbols'] or row['alias'])}` | {row['context']} | {row['resolution']} |")
        lines += ["", "</details>"]
    (OUT / "old-evidence.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Repository graph: file -> imported namespace -> candidate/provider file.
    # External imports remain in the evidence tables, but not in this module view.
    # Named namespace nodes preserve unresolved imports without inventing providers.
    files = sorted(p for p in sources if p.endswith(".py"))
    graph_rows = [r for r in rows if r["target_files"] or r["module"].startswith("TauFW.")]
    names = sorted({r["module"] for r in graph_rows})
    ids = {("file", p): "f" + str(i) for i, p in enumerate(files)}
    ids.update({("module", m): "m" + str(i) for i, m in enumerate(names)})
    graph = ["%% Historical repository modules only; external imports remain in old-imports.csv.", "%% Import arrows point from caller to dependency.", "flowchart LR"]
    for kind, name in ids:
        graph.append(f'  {ids[(kind, name)]}["{name}"]')
    edges = defaultdict(list)
    providers = set()
    for row in graph_rows:
        edges[(row["file"], row["module"])].append(str(row["line"]))
        for target in row["target_files"].split("; "):
            if target:
                providers.add((row["module"], target, row["resolution"]))
    for (path, module), linenos in sorted(edges.items()):
        graph.append(f'  {ids[("file", path)]} -->|"L{", ".join(linenos)}"| {ids[("module", module)]}')
    for module, target, status in sorted(providers):
        operator = "-->" if status in {"exact module", "script-local module"} else "-.->"
        graph.append(f'  {ids[("module", module)]} {operator}|"{status}"| {ids[("file", target)]}')
    (OUT / "old-full-graph.mmd").write_text("\n".join(graph) + "\n", encoding="utf-8")
    dot = ['digraph historical_dependencies {', '  rankdir=LR;', '  node [fontname="Arial", fontsize=9];']
    for kind, name in ids:
        shape = "box" if kind == "file" else "ellipse"
        dot.append(f'  {ids[(kind, name)]} [label="{name}", shape={shape}];')
    for (path, module), linenos in sorted(edges.items()):
        dot.append(f'  {ids[("file", path)]} -> {ids[("module", module)]} [label="L{", ".join(linenos)}"];')
    for module, target, status in sorted(providers):
        style = "solid" if status in {"exact module", "script-local module"} else "dashed"
        dot.append(f'  {ids[("module", module)]} -> {ids[("file", target)]} [label="{status}", style={style}];')
    dot.append('}')
    (OUT / "old-full-graph.dot").write_text("\n".join(dot) + "\n", encoding="utf-8")
    print("Baseline:", revision)
    print("Source files:", len(sources), "Imports:", len(rows), "Non-import evidence lines:", len(evidence))
    print("Stage coupling:", dict(counts))
    print("Parse failures:", len(failures), "Recovery errors:", recovery_errors)
    print("Production wildcard imports:", sum(r["wildcard"] for r in production))


if __name__ == "__main__":
    main()
