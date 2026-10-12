"""Real ROOT inputs built only from fixed tables and ROOT's storage primitives."""
from array import array
import hashlib
import json
from pathlib import Path

DEFINITION = Path(__file__).resolve().parents[1] / "fixtures" / "events.json"
ARRAY_TYPES = {"F": "f", "D": "d", "I": "i", "L": "q", "l": "Q", "O": "b", "b": "B"}


def definition():
    return json.loads(DEFINITION.read_text(encoding="utf-8"))


def fingerprint():
    # Include generator code so changing how inputs are constructed invalidates a lock.
    digest = hashlib.sha256()
    for path in (DEFINITION, Path(__file__).resolve()):
        data = path.read_bytes().replace(b"\r\n", b"\n")
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def rows():
    spec = definition()
    result = []
    for values in spec["events"]:
        row = dict(zip(spec["columns"], values))
        row.update(weight_up=row["weight"] * 1.25, weight_down=row["weight"] * 0.75,
                   idweight=1.0, genweight=row["weight"], m_moth=row["m_vis"] + 5,
                   pt_ll=row["pt_1"] + row["pt_2"], pt_moth=row["pt_1"] + row["pt_2"] + 10)
        result.append(row)
    return result


def write_tree(path, events=None, name="tree", data=False, nup=None):
    import ROOT
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    events = rows() if events is None else events
    spec = definition()
    output = ROOT.TFile.Open(str(path), "RECREATE")
    if not output or output.IsZombie():
        raise RuntimeError("Cannot create fixture %s" % path)
    tree = ROOT.TTree(name, name)
    buffers = {key: array(ARRAY_TYPES[dtype], [0]) for key, dtype in spec["schema"].items()}
    for key, dtype in spec["schema"].items():
        tree.Branch(key, buffers[key], "%s/%s" % (key, dtype))
    sumw = 0.0
    for event in events:
        for key in buffers:
            value = event[key]
            if data and key in ("weight", "genweight", "weight_up", "weight_down"):
                value = 1.0
            if nup is not None and key in ("NUP", "njets"):
                value = nup
            buffers[key][0] = value
        sumw += buffers["genweight"][0]
        tree.Fill()
    cutflow = ROOT.TH1D("cutflow", "cutflow", 25, 0, 25)
    cutflow.SetBinContent(1, len(events))
    cutflow.GetXaxis().SetBinLabel(1, "all")
    cutflow.SetBinContent(17, sumw)
    cutflow.GetXaxis().SetBinLabel(17, "sum of weights")
    output.Write()
    output.Close()
    return path


def sample_files(directory):
    directory = Path(directory)
    result = {}
    for name in ("Data", "DY", "WJ", "TT"):
        result[name] = write_tree(directory / (name + ".root"), data=name == "Data")
    # Only the inclusive sample spans all parton bins; exclusive samples are jet-binned.
    result["DYJetsToLL"] = write_tree(directory / "DYJetsToLL.root")
    for jets in range(1, 5):
        name = "DY%dJetsToLL" % jets
        result[name] = write_tree(directory / (name + ".root"), nup=jets)
    return result


def write_nano(path):
    """Minimal NanoAOD including actual arrays for NanoAODTools' Collection."""
    import ROOT
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    output = ROOT.TFile.Open(str(path), "RECREATE")
    if not output or output.IsZombie():
        raise RuntimeError("Cannot create fixture %s" % path)
    tree = ROOT.TTree("Events", "Events")
    scalars = {"run": ("I", 1), "luminosityBlock": ("I", 1), "event": ("l", 0),
               "genWeight": ("F", 0), "nMuon": ("I", 1), "nTau": ("I", 1)}
    buffers = {}
    for key, (dtype, value) in scalars.items():
        buffers[key] = array(ARRAY_TYPES[dtype], [value])
        tree.Branch(key, buffers[key], "%s/%s" % (key, dtype))
    schema = {"Muon_pt": "F", "Muon_eta": "F", "Muon_phi": "F", "Muon_mass": "F",
              "Muon_pfRelIso04_all": "F", "Muon_dz": "F", "Muon_dxy": "F", "Muon_mediumId": "O",
              "Tau_pt": "F", "Tau_eta": "F", "Tau_phi": "F", "Tau_mass": "F",
              "Tau_idDeepTau2017v2p1VSjet": "b", "Tau_idDeepTau2017v2p1VSmu": "b"}
    for key, dtype in schema.items():
        buffers[key] = array(ARRAY_TYPES[dtype], [0])
        counter = "nMuon" if key.startswith("Muon_") else "nTau"
        tree.Branch(key, buffers[key], "%s[%s]/%s" % (key, counter, dtype))
    weights = [1.0, -0.5, 0.0, 2.0, 1.0, -1.0, 0.5, 1.0]
    for index, (pt, eta, iso, dz, dxy, medium) in enumerate(definition()["nano_muons"]):
        buffers["event"][0] = 2 ** 53 + index  # Protect 64-bit integers against conversion through double.
        buffers["genWeight"][0] = weights[index]
        values = {"Muon_pt": pt, "Muon_eta": eta, "Muon_phi": 0.0, "Muon_mass": 0.105,
                  "Muon_pfRelIso04_all": iso, "Muon_dz": dz, "Muon_dxy": dxy, "Muon_mediumId": medium,
                  "Tau_pt": 30.0, "Tau_eta": 0.0, "Tau_phi": 2.0, "Tau_mass": 1.7,
                  "Tau_idDeepTau2017v2p1VSjet": 16, "Tau_idDeepTau2017v2p1VSmu": 8}
        for key, value in values.items():
            buffers[key][0] = value
        tree.Fill()
    output.Write()
    output.Close()
    return path


def write_shapes(path):
    import ROOT
    spec = definition()
    output = ROOT.TFile.Open(str(path), "RECREATE")
    output.mkdir("baseline")
    output.cd("baseline")
    edges = array("d", spec["shape_edges"])
    for name, contents in (("W", spec["shape_background"]), ("ZTT", spec["shape_background"]),
                           ("data_obs", spec["shape_data"])):
        hist = ROOT.TH1D(name, name, len(edges) - 1, edges)
        hist.Sumw2()
        for index, value in enumerate(contents, 1):
            hist.SetBinContent(index, value)
            hist.SetBinError(index, value ** 0.5)
        hist.Write()
    ROOT.TNamed("selection", "pt_1>20").Write()
    output.Close()
    return Path(path)


def make_normal_inputs(kind, cwd):
    cwd = Path(cwd)
    if kind == "unroll":
        write_tree(cwd / "test" / "DYJetsToLL_M-50_mumu.root")
        return []
    if kind == "rdf":
        return ["-i", str(write_tree(cwd / "fixtures" / "pico.root"))]
    if kind == "multithread":
        return [str(write_tree(cwd / "fixtures" / "pico.root"))]
    if kind == "storage":
        target = cwd / "local-storage"
        target.mkdir()
        return [str(target)]
    if kind == "event_comparison":
        # Existing comparison mode, with identical local inputs rather than a DAS lookup.
        first = write_tree(cwd / "fixtures" / "filesplit.root")
        second = write_tree(cwd / "fixtures" / "evtsplit.root")
        return [str(first), str(second)]
    if kind in ("processor", "bookkeeper"):
        return ["-i", str(write_nano(cwd / "fixtures" / "nano.root")), "-m", "8", "-o", str(cwd / "output")]
    raise ValueError("Unknown normal input adapter %r" % kind)
