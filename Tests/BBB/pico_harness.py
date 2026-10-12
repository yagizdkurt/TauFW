"""Black-box workspace for PicoProducer command tests.

The PicoProducer BBB cases drive the real user surfaces -- `pico.py` and the job workers -- in fresh
child processes, and snapshot only the artifacts those commands produce: config JSON, job configs,
task lists, scheduler command lines, ROOT outputs and summary lines. Nothing here imports PicoProducer
internals, so the baselines remain valid while the package is restructured underneath.

The scheduler is replaced by fake `condor_submit`/`condor_q` executables on PATH; storage is Local.
All absolute paths in snapshots are rewritten relative to the workspace ("$WS").
"""
from array import array
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

BBB = Path(__file__).resolve().parent
TESTS = BBB.parent
REPO = TESTS.parent
ENTRY = BBB / "pico_entry.py"
PICO = REPO / "PicoProducer" / "scripts" / "pico.py"
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
# Package-internal script locations (workers, submit templates) are reduced to their file name, so moving
# a script inside PicoProducer/python does not alter a baseline; renaming the script still does.
PACKAGE_FILE = re.compile(r"(?:\$WS/TauFW/PicoProducer/)?python/(?:[\w.-]+/)*([\w.-]+\.(?:py|sub|sh))")
ARRAY_TYPES = {"F": "f", "I": "i", "l": "Q", "O": "b", "b": "B"}

FAKE_SUBMIT = '''#!/usr/bin/env python3
"""Fake condor_submit: records its arguments and assigns increasing cluster IDs from 1001."""
import os, sys
state = os.environ["BBB_BATCH"]
counter = os.path.join(state, "counter")
jobid = int(open(counter).read()) + 1 if os.path.exists(counter) else 1001
with open(counter, "w") as stream:
    stream.write(str(jobid))
with open(os.path.join(state, "submit.log"), "a") as log:
    log.write(" ".join(sys.argv[1:]) + "\\n")
print("Submitting job(s).")
print("1 job(s) submitted to cluster %d." % jobid)
'''

FAKE_QUEUE = '''#!/usr/bin/env python3
"""Fake condor_q: prints rows 'user clusterid procid status args' of the requested clusters."""
import os, sys
ids = set(a for a in sys.argv[1:] if a.isdigit())
path = os.path.join(os.environ["BBB_BATCH"], "queue")
rows = open(path).read().splitlines() if os.path.exists(path) else []
for row in rows:
    if not ids or row.split()[1] in ids:
        print(row)
'''

# Fixed configuration: every key is set, so no host/user-dependent default is consulted.
CHANNELS = {"skim": "skimjob.py --common-presel", "mutau": "ModuleMuTauSimple tes=1.0"}

CATALOG = '''from TauFW.PicoProducer.datasets import MC, Data
STORE = %r
samples = [
  MC('DY', 'DYJetsToLL_M-50', '/DYJetsToLL_M-50_BBB/RunIIBBB-v1/NANOAODSIM',
     store=STORE+'/$SAMPLE', nfilesperjob=2, opts='zpt=True'),
  Data('Data', 'SingleMuon_Run2018A', '/SingleMuon/Run2018A-BBB-v1/NANOAOD',
       store=STORE+'/$SAMPLE', channels=['mutau']),
  MC('TT', 'TTTo2L2Nu', '/TTTo2L2Nu_BBB/RunIIBBB-v1/NANOAODSIM', store=STORE+'/$SAMPLE'),
]
'''
# Sample name -> number of input files and events per file.
INPUTS = {"DYJetsToLL_M-50": (3, 5), "SingleMuon_Run2018A": (2, 8), "TTTo2L2Nu": (2, 4)}


# ===== Synthetic NanoAOD =====

def write_nano(path, nevents, seed=0):
    """Deterministic NanoAOD with the muon/tau/trigger branches read by ModuleMuTauSimple and the skimmer."""
    import ROOT
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    output = ROOT.TFile.Open(str(path), "RECREATE")
    if not output or output.IsZombie():
        raise RuntimeError("Cannot create fixture %s" % path)
    tree = ROOT.TTree("Events", "Events")
    scalars = {"run": "I", "luminosityBlock": "I", "event": "l", "genWeight": "F",
               "HLT_IsoMu24": "O", "nMuon": "I", "nTau": "I"}
    arrays = {"Muon": {"pt": "F", "eta": "F", "phi": "F", "mass": "F", "charge": "I", "dz": "F", "dxy": "F",
                       "mediumId": "O", "pfRelIso04_all": "F"},
              "Tau": {"pt": "F", "eta": "F", "phi": "F", "mass": "F", "charge": "I", "dz": "F",
                      "idDeepTau2017v2p1VSe": "b", "idDeepTau2017v2p1VSmu": "b", "idDeepTau2017v2p1VSjet": "b",
                      "rawIso": "F"}}
    buffers = {}
    for key, dtype in scalars.items():
        buffers[key] = array(ARRAY_TYPES[dtype], [0])
        tree.Branch(key, buffers[key], "%s/%s" % (key, dtype))
    for collection, schema in arrays.items():
        for key, dtype in schema.items():
            name = "%s_%s" % (collection, key)
            buffers[name] = array(ARRAY_TYPES[dtype], [0, 0])
            tree.Branch(name, buffers[name], "%s[n%s]/%s" % (name, collection, dtype))
    for index in range(nevents):
        k = 100 * seed + index
        buffers["run"][0] = 1
        buffers["luminosityBlock"][0] = 1 + k // 4
        buffers["event"][0] = 2 ** 40 + k
        buffers["genWeight"][0] = (1.0, 0.5, -1.0, 2.0)[k % 4]
        buffers["HLT_IsoMu24"][0] = k % 5 != 4
        buffers["nMuon"][0] = 1 + k % 2
        buffers["nTau"][0] = 1 + (k // 2) % 2
        for j in range(2):
            m, t = k + j, k + 2 * j
            for key, value in (("pt", 18.0 + 7 * (m % 5)), ("eta", -2.0 + 0.9 * ((k + 3 * j) % 5)),
                               ("phi", 0.3 * j), ("mass", 0.1056), ("charge", 1 if m % 2 else -1),
                               ("dz", 0.1 * (m % 4)), ("dxy", 0.01 * (m % 6)), ("mediumId", m % 7 != 6),
                               ("pfRelIso04_all", 0.12 * (m % 6))):
                buffers["Muon_" + key][j] = value
            for key, value in (("pt", 19.0 + 9 * (t % 4)), ("eta", 1.8 - 0.8 * (m % 5)), ("phi", 2.5 + 0.2 * j),
                               ("mass", 1.2), ("charge", -1 if m % 3 else 1), ("dz", 0.07 * (m % 4)),
                               ("idDeepTau2017v2p1VSe", 2 ** (m % 6) - 1), ("idDeepTau2017v2p1VSmu", m % 3),
                               ("idDeepTau2017v2p1VSjet", 2 ** (1 + t % 7) - 1), ("rawIso", 0.5 * (m % 5))):
                buffers["Tau_" + key][j] = value
        tree.Fill()
    output.Write()
    output.Close()
    return path


# ===== Workspace =====

class PicoWorkspace:
    """A temporary PicoProducer installation: fixed config, sample catalog, inputs and fake batch system."""

    def __init__(self, workspace, config=True):
        self.root = Path(workspace).resolve()
        self.mirror = self.root / "TauFW"
        self.basedir = self.mirror / "PicoProducer"
        self.batch = self.root / "batch"
        self.bin = self.root / "bin"
        self.batch.mkdir()
        self.bin.mkdir()
        for name, source in (("condor_submit", FAKE_SUBMIT), ("condor_q", FAKE_QUEUE)):
            tool = self.bin / name
            tool.write_text(source, encoding="utf-8")
            tool.chmod(0o755)
        # The mirror links the checkout's sample lists; replace the link (not its target) with our own catalog.
        samples = self.basedir / "samples"
        if samples.is_symlink():
            samples.unlink()
        (samples / "bbb").mkdir(parents=True)
        (samples / "__init__.py").write_text("", encoding="utf-8")
        (samples / "bbb" / "__init__.py").write_text("", encoding="utf-8")
        (samples / "bbb" / "samples_2018.py").write_text(CATALOG % str(self.root / "nano"), encoding="utf-8")
        self.inputs = {}
        for seed, (sample, (nfiles, nevents)) in enumerate(INPUTS.items()):
            self.inputs[sample] = [write_nano(self.root / "nano" / sample / ("nano_%d.root" % i), nevents, 10 * seed + i)
                                   for i in range(nfiles)]
        if config:
            self.write_config(self.config())

    # ----- configuration -----

    def config(self):
        ws = str(self.root)
        return {"channels": dict(CHANNELS), "eras": {"2018": "bbb/samples_2018.py"},
                "jobdir": "output/$ERA/$CHANNEL/$SAMPLE", "outdir": ws + "/jobout/$ERA/$CHANNEL/$SAMPLE",
                "nanodir": ws + "/nanoout/$ERA/$DAS", "picodir": ws + "/pico/$ERA/$GROUP", "tmpskimdir": "",
                "batch": "HTCondor", "queue": "", "batchopts": "", "nfilesperjob": 1, "maxevtsperjob": -1,
                "filelistdir": "samples/files/$ERA/$SAMPLE.txt", "maxopenfiles": 500, "haddcmd": "", "ncores": 1}

    @property
    def config_path(self):
        return self.basedir / "config" / "config.json"

    def write_config(self, config, backup=None):
        self.config_path.parent.mkdir(exist_ok=True)
        self.config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        if backup is not None:
            Path(str(self.config_path) + ".bkp").write_text(json.dumps(backup, indent=2), encoding="utf-8")

    def read_config(self):
        result = {"config": json.loads(self.config_path.read_text(encoding="utf-8"))}
        backup = Path(str(self.config_path) + ".bkp")
        if backup.exists():
            result["backup"] = json.loads(backup.read_text(encoding="utf-8"))
        return self.normalize(result)

    # ----- commands -----

    def env(self):
        env = os.environ.copy()
        env.pop("CMSSW_BASE", None)
        env.update(PATH=str(self.bin) + os.pathsep + env.get("PATH", ""), BBB_BATCH=str(self.batch),
                   PYTHONHASHSEED="1777", PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1")
        return env

    def execute(self, script, *arguments, cwd=None, check=True):
        command = [sys.executable, "-B", str(ENTRY), str(self.mirror), str(script)] + [str(a) for a in arguments]
        result = subprocess.run(command, cwd=str(cwd or self.root), env=self.env(), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, universal_newlines=True)
        sys.stdout.write("$ %s\n%s" % (" ".join(command[4:]), result.stdout))  # Kept in the case log for debugging.
        if check and result.returncode:
            raise RuntimeError("Command failed (exit %s): %s" % (result.returncode, " ".join(command[4:])))
        return {"exit": result.returncode, "lines": self.lines(result.stdout)}

    def pico(self, *arguments, check=True):
        return self.execute(PICO, *arguments, check=check)

    def worker(self, name, *arguments):
        return self.execute(self.basedir / "python" / "processors" / name, *arguments)

    # ----- fake scheduler -----

    def queue(self, rows):
        """Rows (clusterid, procid, status, args) reported by the fake condor_q; status 1=idle, 2=running."""
        (self.batch / "queue").write_text("".join("bbb %d %d %d %s\n" % row for row in rows), encoding="utf-8")

    def submissions(self):
        path = self.batch / "submit.log"
        return self.normalize(path.read_text(encoding="utf-8").splitlines()) if path.exists() else []

    # ----- snapshots -----

    def normalize(self, value):
        """Rewrite workspace paths, recursively, including mapping keys."""
        if isinstance(value, str):
            return PACKAGE_FILE.sub(r"<pico>/\1", value.replace(str(self.root), "$WS"))
        if isinstance(value, dict):
            return {self.normalize(key): self.normalize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.normalize(item) for item in value]
        return value

    def lines(self, text, pattern=None):
        lines = [ANSI.sub("", line).rstrip() for line in text.splitlines()]
        if pattern:
            lines = [line for line in lines if re.search(pattern, line)]
        return self.normalize(lines)

    def tree(self, *roots):
        """Relative listing of every file below the given workspace-relative or basedir-relative roots."""
        result = []
        for root in roots:
            for path in sorted(Path(root).rglob("*")) if Path(root).exists() else []:
                if path.is_file():
                    result.append(self.normalize(str(path)))
        return result

    def jobfiles(self):
        """Every job config (minus its creation time) and task list written below the job directory."""
        result = {}
        for path in sorted((self.basedir / "output").rglob("*")):
            if not path.is_file():
                continue
            key = str(path.relative_to(self.basedir))
            if path.suffix == ".json":
                document = json.loads(path.read_text(encoding="utf-8"))
                document.pop("time", None)
                result[key] = self.normalize(document)
            elif path.suffix == ".txt":
                result[key] = self.normalize(path.read_text(encoding="utf-8").splitlines())
            else:
                result[key] = "<%s bytes>" % path.stat().st_size
        return result

    def write_pico(self, path, valid=True):
        """Job output: a valid analysis tuple (tree + cutflow), or a corrupt file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if valid:
            from support.fixtures import write_tree
            return write_tree(path)
        path.write_bytes(b"not a ROOT file")
        return path

    def write_skim(self, path, valid=True, nevents=3):
        path = Path(path)
        if valid:
            return write_nano(path, nevents, seed=7)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"not a ROOT file")
        return path

    def remove(self, path):
        path = Path(path)
        if path.is_dir():
            shutil.rmtree(str(path))
        elif path.exists():
            path.unlink()
