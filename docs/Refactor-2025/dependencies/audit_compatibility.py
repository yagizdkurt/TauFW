"""Static historical API inventory; writes CSV evidence, never imports TauFW.

Run from any directory with Python 3.9+: python docs/Refactor-2025/dependencies/audit_compatibility.py
The baseline is the same pre-refactor tree used by audit_old.py. AST equality is
source evidence only: dependencies, globals, configuration and runtime effects can differ.
Python-2/unparseable files retain lexical definitions, explicitly without an AST verdict.
"""
import ast
import csv
import io
import re
import subprocess
import tokenize
import warnings
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BASE = "0b174cf8122899bfbe5e5f03378d27e2d5c932fa"


def git(*args, **kwargs):
    return subprocess.check_output(["git", *args], cwd=ROOT, **kwargs)


def tree(revision):
    paths = git("ls-tree", "-r", "--name-only", revision).decode().splitlines()
    paths = [p for p in paths if p.endswith(".py")]
    data = git("cat-file", "--batch", input="".join(revision + ":" + p + "\n" for p in paths).encode())
    stream, sources = io.BytesIO(data), {}
    for path in paths:
        header = stream.readline().split()
        raw = stream.read(int(header[2]))
        assert stream.read(1) == b"\n"
        try:
            encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
        except SyntaxError:
            encoding = "utf-8"
        sources[path] = raw.decode(encoding, errors="replace")
    return sources


def definitions(source):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            parsed = ast.parse(source)
    except SyntaxError as error:
        # Lexical recovery deliberately does not claim to parse Python 2 or infer scope.
        found, scopes = [], []
        for line, text in enumerate(source.splitlines(), 1):
            match = re.match(r"^([ \t]*)(class|def)\s+(\w+)\s*[:(]", text)
            if not match:
                continue
            indent = len(match[1].expandtabs(8))
            while scopes and scopes[-1][0] >= indent:
                scopes.pop()
            name = ".".join([s[1] for s in scopes] + [match[3]])
            if match[2] == "def":
                found.append((name, line, "", ""))
            scopes.append((indent, match[3]))
        return found, "lexical: line %s: %s" % (error.lineno, error.msg)
    found = []

    def visit(node, prefix=""):
        for child in ast.iter_child_nodes(node):
            name = prefix
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name += child.name
                if not isinstance(child, ast.ClassDef):
                    found.append((name, child.lineno, ast.unparse(child.args), ast.dump(child, include_attributes=False)))
                name += "."
            visit(child, name)
    visit(parsed)
    return found, "ast"


def destinations(path, current, renames):
    # Explicit ownership mappings take precedence over retained diagnostic/alias stubs.
    special = {
        "Plotter/plot.py": ["Histogrammer/fillhists.py"],
        "Plotter/python/plot/MultiThread.py": ["Utilities/python/Process/_parallel.py"],
        "Plotter/python/plot/utils.py": ["Utilities/python/Drawing/hist_tools.py"],
        "Plotter/python/plot/string.py": ["Histogrammer/python/spec/string.py", "Utilities/python/Expressions/_expressions.py", "Utilities/python/Drawing/labels.py"],
        "Plotter/python/sample/SampleStyle.py": ["Utilities/python/Drawing/SampleStyle.py"],
        "Fitter/python/plot/datacard.py": ["Histogrammer/python/shapes/inputs.py"],
        "Fitter/python/plot/rebinning.py": ["Histogrammer/python/shapes/rebinning.py"],
        "PicoProducer/python/storage/Sample.py": ["PicoProducer/python/datasets/sample.py"],
        "PicoProducer/python/tools/config.py": ["PicoProducer/python/settings/"],
        "PicoProducer/python/storage/utils.py": ["PicoProducer/python/storage/", "PicoProducer/python/datasets/catalog.py", "PicoProducer/python/settings/defaults.py"],
        "PicoProducer/python/batch/utils.py": ["PicoProducer/python/batch/factory.py", "PicoProducer/python/settings/defaults.py", "PicoProducer/python/jobs/chunking.py", "PicoProducer/python/jobs/jobconfig.py"],
        "PicoProducer/python/pico/job.py": ["PicoProducer/python/jobs/", "PicoProducer/python/api/producer.py", "PicoProducer/python/cli/jobs.py"],
        "PicoProducer/python/pico/run.py": ["PicoProducer/python/jobs/", "PicoProducer/python/cli/jobs.py"],
        "PicoProducer/python/pico/common.py": ["PicoProducer/python/cli/common.py"],
        "PicoProducer/python/batch/SGE.py": ["PicoProducer/python/batch/sge.py"],
        "PicoProducer/scripts/pico.py": ["PicoProducer/python/cli/"],
        "common/python/tools/math.py": ["Utilities/python/Math/_math.py"],
        "common/python/tools/Table.py": ["Utilities/python/CLI/_internal/table.py"],
        "common/python/tools/LoadingBar.py": ["Utilities/python/CLI/_internal/loading_bar.py"],
        "Fitter/TauES/config/FitSetup_mumu.yml": ["Configs/Fitter/tes_id/FitSetup_mumu.yml"],
        "PicoProducer/scripts/pico2.py": ["Legacy/PicoProducer/python/scripts/pico2.sh"],
    }
    for name in ("TT", "PNet", "UParT"):
        special["Fitter/TauES_ID/config/config_coarse_%s.yml" % name] = ["Configs/Fitter/tes_id/config_coarse_%s.yml" % name]
    for name in ("Plot", "Plot2D", "Stack", "Ratio", "CMSStyle"):
        special["Plotter/python/plot/%s.py" % name] = ["Utilities/python/Drawing/%s.py" % name]
    for name in ("HTCondor_CMG", "HTCondor_DESY", "HTCondor_KIT", "HTCondor_NAF"):
        special["PicoProducer/python/batch/%s.py" % name] = ["PicoProducer/python/batch/htcondor.py"]
    special["PicoProducer/python/batch/SLURM_UCL.py"] = ["PicoProducer/python/batch/slurm.py"]
    for variant in ("ETauFR", "HighPT", "paper", "tutorial", "TauES"):
        name = "createinputsTES.py" if variant == "TauES" else "createinputs.py"
        special["Fitter/%s/%s" % (variant, name)] = ["Histogrammer/shapes/%s/%s" % (variant, name)]
    if path in special:
        return sorted({p for target in special[path] if target.endswith("/") for p in current
                       if p.startswith(target)} | {p for p in special[path] if p in current})
    if path.startswith("PicoProducer/python/processors/"):
        target = path.replace("/processors/", "/workers/")
        if target in current:
            return [target]
    if path.startswith("Plotter/python/"):
        target = path.replace("Plotter/", "Histogrammer/", 1).replace("/plot/", "/spec/")
        if path.endswith("/MultiDraw.py"):
            target = "Histogrammer/python/sample/MultiDraw.py"
        if target in current:
            return [target]
    if path.startswith("Plotter/config/setup_"):
        target = path.replace("Plotter/config/", "Configs/Histogrammer/setups/")
        if target in current:
            return [target]
    if path.startswith("Plotter/"):
        target = path.replace("Plotter/", "Histogrammer/", 1)
        if target in current:
            return [target]
    if path in renames:
        return [renames[path]]
    if "Legacy/" + path in current:
        return ["Legacy/" + path]
    return [path] if path in current else []


def write(name, rows, fields):
    with (OUT / name).open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    head = git("rev-parse", "HEAD").decode().strip()
    old, new = tree(BASE), tree(head)
    renames = {}
    for line in git("diff", "--name-status", "-M", BASE, head).decode().splitlines():
        parts = line.split("\t")
        if parts[0].startswith("R"):
            renames[parts[1]] = parts[2]
    parsed = {p: definitions(s) for p, s in new.items()}
    rows, files = [], []
    aliases = {"frange": "float_range", "partition_by_max": "partition_by_sum", "reldiff": "relative_difference",
               "scalevec": "scale_vector", "MultiProcessor": "ParallelProcessor", "ReturnProcess": "_ProcessHandle",
               "SimpleProcess": "_SerialCall", "Embdedded": "Embedded"}
    for path, source in sorted(old.items()):
        defs, mode = definitions(source)
        targets = destinations(path, new, renames)
        files.append(dict(old_file=path, parser=mode, definitions=len(defs), candidate_files=";".join(targets)))
        for name, line, signature, dump in defs:
            renamed = ".".join(aliases.get(part, part) for part in name.split("."))
            if path == "common/python/tools/Table.py":
                renamed = renamed.replace(".printheader", ".print_header").replace(".printrow", ".print_row").replace(".printtable", ".print_rows")
            if path == "PicoProducer/python/batch/SGE.py":
                renamed = renamed.replace("HTCondor.", "SGE.")
            matches = [(p, item) for p in targets for item in parsed[p][0] if item[0] == renamed]
            if len(matches) == 1:
                p, (new_name, new_line, new_sig, new_dump) = matches[0]
                verdict = "same AST" if dump and dump == new_dump else "changed AST"
                if not dump or not new_dump:
                    verdict = "lexical only"
                row = dict(new_file=p, new_symbol=new_name, new_line=new_line, new_signature=new_sig)
            else:
                verdict = "ambiguous" if matches else "no matched definition"
                row = dict(new_file=";".join(targets), new_symbol="", new_line="", new_signature="")
            rows.append(dict(old_file=path, old_symbol=name, old_line=line, old_signature=signature,
                             parser=mode, comparison=verdict, **row))
    write("compatibility-functions.csv", rows, ["old_file", "old_symbol", "old_line", "old_signature", "parser",
          "comparison", "new_file", "new_symbol", "new_line", "new_signature"])
    write("compatibility-files.csv", files, ["old_file", "parser", "definitions", "candidate_files"])
    print("baseline:", BASE, "current:", head)
    print("Python files:", len(old), "current:", len(new), "old parser modes:", dict(Counter(f["parser"].split(":")[0] for f in files)))
    print("Definitions:", len(rows), "comparisons:", dict(Counter(r["comparison"] for r in rows)))
    blobs = []
    for revision in (BASE, head):
        blobs.append({line.split("\t", 1)[1]: line.split()[2]
                      for line in git("ls-tree", "-r", revision).decode().splitlines()})
    with (OUT / "old-source-files.csv").open(encoding="utf-8", newline="") as source_list:
        sources = list(csv.DictReader(source_list))
    source_rows = []
    for source in sources:
        path = source["file"]
        targets = destinations(path, blobs[1], renames)
        hashes = [blobs[1][p] for p in targets]
        status = "same blob" if blobs[0][path] in hashes else "changed blob" if targets else "no mapped file"
        source_rows.append(dict(old_file=path, language=source["language"], comparison=status,
                                candidate_files=";".join(targets), old_blob=blobs[0][path], new_blobs=";".join(hashes)))
    write("compatibility-sources.csv", source_rows,
          ["old_file", "language", "comparison", "candidate_files", "old_blob", "new_blobs"])
    print("Source/build/config files:", len(source_rows), dict(Counter(r["comparison"] for r in source_rows)))


if __name__ == "__main__":
    main()
