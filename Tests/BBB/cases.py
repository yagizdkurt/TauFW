"""Small characterization cases against the current production APIs.

Imports of ROOT and production code occur only inside separately selected workers.
"""
import contextlib
import io
import re
from pathlib import Path
from types import SimpleNamespace


def common_formatting(workspace):
    from TauFW.Utilities.CLI import CLI
    output = io.StringIO()
    with contextlib.redirect_stdout(output):  # CLI() takes the redirected stdout
        table = CLI().table("%8s %10s %10s", "%8d %10.2f %10.2f")
        table.print_header("point", "x", "weight")
        for values in ((1, 0.0, 1.0), (2, -1.25, 0.0), (3, 2.5, -0.5)):
            table.print_row(*values)
        bar = CLI().loading_bar(3, width=6, counter=True)
        for _ in range(3):
            bar.count()
    return {"stdout": output.getvalue(), "partial_row": table.row(4, 1.25),
            "extra_row": table.row(5, 2.0, 1.0, "extra")}


def common_chunking(workspace):
    from TauFW.common.tools.utils import chunkify, ensurelist, unpacklistargs
    from TauFW.Utilities.Math import partition, partition_by_sum
    from TauFW.common.tools.string import repkey
    return {"chunks": {str(size): chunkify(list(range(7)), size) for size in (1, 3, 7, 10)},
            "empty": chunkify([], 3), "partition": partition(list(range(7)), parts=3),
            "by_max": partition_by_sum([2, 3, 4, 5, 1], 6),
            "ensure": [ensurelist(None), ensurelist(3), ensurelist((1, 2))],
            "unpacked": unpacklistargs(([1, 2],)),
            "path": repkey("$ERA/$SAMPLE.root", ERA="2018", SAMPLE="DY")}


def plotter_context(workspace):
    from TauFW.Histogrammer.spec.Selection import Selection
    from TauFW.Histogrammer.spec.Variable import Variable
    result = []
    for cut in ("q_1*q_2<0 && dm_2==0", "q_1*q_2<0 && dm_2==10", "q_1*q_2<0 && pt_1>20"):
        selection = Selection("baseline", "Baseline", cut)
        variable = Variable("m_vis", "Visible mass", 8, 0, 160,
                            cbins={"dm_2==0": [0, 20, 60, 160], "dm_2==10": (4, 0, 160)},
                            ctitle={"dm_2==0": "DM zero", "dm_2==10": "DM ten"})
        variable.changecontext(selection)
        result.append({"cut": selection.selection, "ss": selection.invertcharge(to="SS").selection,
                       "filename": selection.filename, "name": variable.name, "title": variable.title,
                       "bins": variable.nbins, "min": variable.min, "max": variable.max,
                       "edges": list(variable.edges) if variable.edges is not None else [],
                       "variable_filename": variable.filename})
    return result


def _samples(workspace):
    from support.fixtures import sample_files
    from TauFW.Histogrammer.sample.utils import Sample, SampleSet, setera
    setera(2018, 1.0)
    files = sample_files(Path(workspace) / "inputs")
    data = Sample("Data", "Observed", str(files["Data"]), data=True)
    mc = [Sample(name, name, str(files[name]), xsec, lumi=1.0, weight="weight")
          for name, xsec in (("DY", 0.01), ("WJ", 0.02), ("TT", 0.03))]
    return SampleSet(data, mc, channel="mutau", loadingbar=False), files


def _histsets(result):
    from BBB.snapshot import histogram_snapshot
    return [{"selection": selection.selection, "selection_name": selection.filename,
             "variable": variable.name, "variable_name": variable.filename,
             "histograms": [histogram_snapshot(hist) for hist in histset]}
            for selection, variables in result.items() for variable, histset in variables.items()]


def _sample_state(sample):
    from TauFW.Histogrammer.sample.MergedSample import MergedSample
    # A plain Sample sets samples=[self]; only a MergedSample has real children.
    children = sample.samples if isinstance(sample, MergedSample) else []
    return {"name": sample.name, "norm": sample.norm, "scale": sample.scale,
            "xsec": sample.xsec, "events": sample.nevents, "sumweights": sample.sumweights,
            "weight": sample.weight, "extraweight": sample.extraweight, "cuts": sample.cuts,
            "children": [_sample_state(child) for child in children]}


def plotter_histograms(workspace):
    from TauFW.Histogrammer.spec.Variable import Variable
    from TauFW.Histogrammer.spec.Selection import Selection
    from BBB.snapshot import histogram_snapshot
    samples, files = _samples(workspace)
    variable = Variable("m_vis", [0, 20, 40, 60, 80, 100, 120, 160])
    selection = Selection("os", "q_1*q_2<0 && pt_1>20")
    result = samples.gethists([variable], [selection], split=False, nthreads=1, blind=False)
    two_dimensional = samples.expsamples[0].gethist2D(
        (Variable("m_vis", 8, 0, 160), Variable("pt_1", 4, 20, 100)), selection, nthreads=1)
    return {"histograms": _histsets(result), "2d": histogram_snapshot(two_dimensional),
            "normalization": [_sample_state(sample) for sample in samples.expsamples]}


def plotter_merge_split(workspace):
    from TauFW.Histogrammer.spec.Variable import Variable
    from TauFW.Histogrammer.spec.Selection import Selection
    samples, files = _samples(workspace)
    variables = [Variable("m_vis", 8, 0, 160)]
    selections = [Selection("baseline", "pt_1>20")]
    before = _histsets(samples.gethists(variables, selections, nthreads=1, blind=False))
    samples.join("DY", "WJ", name="EWK", title="Electroweak")
    merged = _histsets(samples.gethists(variables, selections, split=False, nthreads=1, blind=False))
    samples.split("EWK", [("TrueTau", "genmatch_2==5"), ("Other", "genmatch_2!=5")])
    split = _histsets(samples.gethists(variables, selections, split=True, nthreads=1, blind=False))
    return {"before": before, "merged": merged, "split": split}


def plotter_stitch(workspace):
    from TauFW.Histogrammer.sample.utils import Sample, SampleSet, MergedSample
    from TauFW.Histogrammer.spec.Variable import Variable
    from TauFW.Histogrammer.spec.Selection import Selection
    samples, files = _samples(workspace)
    stitched = SampleSet([Sample(name, name, str(files[name]), xsec, lumi=1.0, weight="weight")
                         for name, xsec in (("DYJetsToLL", 0.01), ("DY1JetsToLL", 0.005),
                                            ("DY2JetsToLL", 0.003), ("DY3JetsToLL", 0.002),
                                            ("DY4JetsToLL", 0.001))], loadingbar=False)
    stitched.stitch("DY*JetsToLL", incl="DYJetsToLL", name="DY_stitched", kfactor=1.25)
    if len(stitched.expsamples) != 1 or not isinstance(stitched.expsamples[0], MergedSample):
        raise RuntimeError("Stitching did not materialize a merged sample; refusing a no-op baseline.")
    histograms = stitched.gethists([Variable("m_vis", 8, 0, 160)], [Selection("baseline", "pt_1>20")], nthreads=1)
    return {"state": [_sample_state(sample) for sample in stitched.expsamples], "histograms": _histsets(histograms)}


def plotter_qcd(workspace):
    from TauFW.Histogrammer.spec.Variable import Variable
    from TauFW.Histogrammer.spec.Selection import Selection
    samples, files = _samples(workspace)
    result = samples.gethists([Variable("m_vis", 8, 0, 160)],
                             [Selection("os", "q_1*q_2<0 && pt_1>20")],
                             method="QCD_OSSS", nthreads=1, blind=False, scale=1.1)
    histograms = _histsets(result)
    if not any("QCD" in hist["name"] for group in histograms for hist in group["histograms"]):
        raise RuntimeError("QCD output missing; refusing a no-op baseline.")
    return histograms


def _stack_modules():
    """The code under test of plotter.stack. Locked with plot.py drawing from memory (LocalR/architecture/18, S0);
    since S3 the histograms go through a control-histogram file: the Histogrammer writes them, the Plotter reads and
    draws them. The output must not change."""
    from TauFW.Histogrammer.sample.utils import Sample, SampleSet, setera
    from TauFW.Histogrammer.spec.Variable import Variable
    from TauFW.Histogrammer.spec.Selection import Selection
    from TauFW.Histogrammer.controlhists import stack_entry, write_control_hists
    from TauFW.Plotter.controlplots import read_control_hists, make_stack, draw_stack
    return SimpleNamespace(Sample=Sample, SampleSet=SampleSet, setera=setera, Variable=Variable, Selection=Selection,
                           stack_entry=stack_entry, write_control_hists=write_control_hists,
                           read_control_hists=read_control_hists, make_stack=make_stack, draw_stack=draw_stack)


def plotter_stack(workspace):
    """plot.py's path from samples to drawn stacks: setera without an explicit lumi on the samples (the module
    global), getstack with the QCD method loaded by name, and the draw calls of plot.py. Locked before the Plotter
    became the Histogrammer (18, S0); since S3 the filled histograms are written to a file (fillhists.py --hists)
    and drawn from it by the Plotter (draw.py), which must give the same canvases."""
    from support.fixtures import sample_files
    from BBB.snapshot import drawn_snapshot, histogram_snapshot
    m = _stack_modules()
    m.setera(2018)  # no lumi given: the samples below take it from the era (CMSStyle.lumi_dict)
    files = sample_files(Path(workspace) / "inputs")
    data = m.Sample("Data", "Observed", str(files["Data"]), data=True)
    mc = [m.Sample(name, name, str(files[name]), xsec, weight="weight")
          for name, xsec in (("DY", 0.01), ("WJ", 0.02), ("TT", 0.03))]
    samples = m.SampleSet(data, mc, channel="mutau", loadingbar=False)
    table = io.StringIO()
    with contextlib.redirect_stdout(table):
        samples.printtable()
    variables = [  # the kinds of options plot.py uses: contextual bins and titles, drawing hints, variable bins
        m.Variable("m_vis", "m_vis", 8, 0, 160, ctitle={"pt_1>": "m_vis (high pt)"}, cbins={"pt_1>": (4, 0, 160)}),
        m.Variable("pt_1", "Muon pt", 8, 0, 120, logy=True, ymargin=1.6, pos="T", ncols=2),
        m.Variable("m_vis", "m_vis", [0, 20, 40, 60, 80, 100, 120, 160], fname="mvis_varbins"),
    ]
    selections = [m.Selection("baseline", "q_1*q_2<0"), m.Selection("highpt", "High pt", "q_1*q_2<0 && pt_1>20")]
    outdir = Path(workspace) / "plots"
    outdir.mkdir()
    result = {"lumi": samples.expsamples[0].lumi, "table": _clean(table.getvalue()).splitlines(),
              "samples": [_sample_state(sample) for sample in samples.samples], "stacks": []}
    entries = []
    for selection in selections:  # as plot.py: one getstack per selection
        stacks = samples.getstack(variables, selection, method="QCD_OSSS", nthreads=1)
        # getstack returns {Stack: (Variable, Selection)}; sorted by variable for a fixed order
        for stack, (variable, _) in sorted(stacks.items(), key=lambda item: item[1][0].filename):
            entries.append(m.stack_entry(stack, variable, selection))  # the histograms as filled, before drawing
    histfile = m.write_control_hists(str(Path(workspace) / "hists" / "mutau.root"), entries,
                                     channel="mutau", era="2018", tag="_stack")
    hists = m.read_control_hists(histfile)
    for entry in hists.entries:  # drawn as Plotter/draw.py draws them
        histograms = [histogram_snapshot(hist) for hist in entry.hists]
        stack = m.make_stack(entry)
        m.draw_stack(stack, hists, entry, str(outdir), exts=["png"])
        result["stacks"].append({
            "selection": entry.selection_cut, "variable": entry.variable.filename,
            "drawing": {name: getattr(entry.variable, name) for name in (  # what Plot reads from the variable
                "filename", "title", "xmin", "xmax", "ymin", "ymax", "rmin", "rmax", "ratiorange", "binlabels",
                "logx", "logy", "ymargin", "logyrange", "position", "ncols", "dividebins")},
            "histograms": histograms,
            "canvas": drawn_snapshot(stack.canvas)})
        stack.close(keep=True)
    if not any("QCD" in hist["name"] for item in result["stacks"] for hist in item["histograms"]):
        raise RuntimeError("QCD histogram missing from the stacks; refusing a no-op baseline.")
    result["files"] = sorted(path.name for path in outdir.iterdir())
    return result


def plotter_unroll(workspace):
    import ROOT
    from support.fixtures import rows
    from BBB.snapshot import histogram_snapshot
    # Workers start in the temporary TauFW root, which contains the current copied source.
    macro = Path("Histogrammer/python/macros/Unroll.cxx").resolve()
    ROOT.gROOT.ProcessLine('.L %s+O' % macro.as_posix())
    if not hasattr(ROOT, "Unroll"):
        raise RuntimeError("Unroll macro failed to compile.")
    original = ROOT.TH2D("original", "original", 4, 0, 160, 4, 20, 100)
    original.Sumw2()
    for row in rows():
        original.Fill(row["m_vis"], row["pt_1"], row["weight"])
    ROOT.Unroll.SetBins(original, 0)
    unrolled = ROOT.Unroll.Unroll(original, "unrolled", False, 0)
    rolled = ROOT.Unroll.RollUp(unrolled, "rolled", original, 0)
    return {"original": histogram_snapshot(original), "unrolled": histogram_snapshot(unrolled),
            "rolled": histogram_snapshot(rolled)}


def pico_writer(workspace):
    from TauFW.PicoProducer.analysis.TreeProducer import TreeProducer
    from support.fixtures import rows
    from BBB.snapshot import file_snapshot
    path = Path(workspace) / "writer.root"
    writer = TreeProducer(str(path), SimpleNamespace(verbosity=0), display=False)
    writer.addBranch("event", "uint64")
    writer.addBranch("mass", "float32")
    writer.addBranch("weight", "float64")
    writer.addBranch("baseline", "float64", default=-999.0)
    writer.addBranch("flag", "bool")
    writer.addBranch("count", "int32")
    writer.addBranch("values", "float32", len="count", max=4)
    writer.addBranch("fixed", "int32", len=3, default=[1, 2, 3])
    writer.setAlias("mass2", "2*mass")
    writer.addHist("weights", 8, 0, 160)
    writer.cutflow.addcut("all", "All events")
    writer.cutflow.addcut("selected", "Selected events")
    for index, row in enumerate(rows()):
        writer.cutflow.fill("all", row["weight"])
        if row["pt_1"] <= 20:
            continue
        writer.cutflow.fill("selected", row["weight"])
        writer.event[0] = 2 ** 53 + index
        writer.mass[0], writer.weight[0] = row["m_vis"], row["weight"]
        writer.flag[0] = row["genmatch_2"] == 5
        writer.count[0] = index % 4
        writer.values[:] = [row["m_vis"], row["pt_1"], row["weight"], 0]
        writer.pileup.Fill(index % 4, row["weight"])
        writer.fill("weights", row["m_vis"], row["weight"])
        writer.fill()
    writer.endJob()
    return file_snapshot(path)


def pico_bookkeeper(workspace):
    from PhysicsTools.NanoAODTools.postprocessing.framework.postprocessor import PostProcessor
    from TauFW.PicoProducer.workers.Bookkeeper import Bookkeeper
    from Tests.PicoProducer.analysis.TestModule import TestModule
    from support.fixtures import write_nano
    from BBB.snapshot import file_snapshot, histogram_snapshot
    source = write_nano(Path(workspace) / "nano.root")
    result = {}
    for name, first, maximum, cut in (("full", 0, 8, None), ("range", 1, 5, "Muon_pt>20")):
        outdir = Path(workspace) / name
        outdir.mkdir()
        bookkeeper = Bookkeeper(verb=0)
        processor = PostProcessor(str(outdir), [str(source)], cut=cut, branchsel=None,
                                  modules=[TestModule(), bookkeeper], firstEntry=first, maxEntries=maximum,
                                  postfix="_" + name, noOut=False, provenance=False, fwkJobReport=False)
        processor.run()
        files = list(outdir.glob("*.root"))
        if len(files) != 1:
            raise RuntimeError("Expected one NanoAODTools output, found %s" % len(files))
        result[name] = {"file": file_snapshot(files[0]), "total_cutflow": histogram_snapshot(bookkeeper.cutflow)}
    return result


def pico_scale_factors(workspace):
    import ROOT
    from TauFW.PicoProducer.corrections.ScaleFactorTool import ScaleFactor
    from BBB.snapshot import file_snapshot
    path = Path(workspace) / "scale_factors.root"
    output = ROOT.TFile.Open(str(path), "RECREATE")
    hist = ROOT.TH2D("sf", "sf", 2, -2.5, 2.5, 2, 0, 100)
    for xbin in (1, 2):
        for ybin in (1, 2):
            hist.SetBinContent(xbin, ybin, 1.0 + xbin * 0.125 + ybin * 0.25)
            hist.SetBinError(xbin, ybin, 0.01)
    output.Write()
    output.Close()
    tool = ScaleFactor(str(path), "sf", ptvseta=True)
    points = [(0, -3), (0, 0), (50, 0), (100, 3), (200, -3)]
    return {"input": file_snapshot(path), "values": [tool.getSF(pt, eta) for pt, eta in points],
            "product": [(tool * tool).getSF(pt, eta) for pt, eta in points]}


# ===== PicoProducer commands (black box: pico.py and job workers in child processes) =====

def pico_config(workspace):
    import json
    from BBB.pico_harness import PicoWorkspace
    ws = PicoWorkspace(workspace, config=False)
    # A fresh installation creates defaults; site/user-dependent guesses (paths, batch) are excluded.
    ws.pico("list")
    created = json.loads(ws.config_path.read_text(encoding="utf-8"))
    stable = ("channels", "eras", "jobdir", "tmpskimdir", "queue", "batchopts", "nfilesperjob", "maxevtsperjob",
              "filelistdir", "maxopenfiles", "haddcmd", "ncores")
    result = {"fresh": {"keys": list(created), "values": {key: created[key] for key in stable}}}
    # A config reset to a few keys is recovered from its backup.
    full = ws.config()
    ws.write_config({key: full[key] for key in ("channels", "eras", "jobdir", "outdir")}, backup=full)
    ws.pico("list")
    result["recovered"] = ws.read_config()
    edits = [("channel", "mutau2", "ModuleMuTauSimple a=1"), ("era", "2017", "samples/bbb/samples_2018.py"),
             ("set", "nfilesperjob", "3"), ("set", "queue", "longlunch"), ("set", "channel", "skim2", "skimjob.py --jec"),
             ("rm", "channel", "mutau2"), ("rm", "haddcmd")]
    result["edits"] = []
    for edit in edits:
        ws.pico(*edit)
        result["edits"].append({"command": list(edit), "config": ws.read_config()})
    result["list"] = ws.pico("list")["lines"]
    return result


def pico_run(workspace):
    from BBB.pico_harness import PicoWorkspace
    ws = PicoWorkspace(workspace)
    commands = [("run", "-y", "2018", "-c", "mutau", "-s", "DY", "--dry", "-E", "a=1", "b=2"),
                ("run", "-y", "2018", "-c", "mutau", "-s", "Single", "--dry", "-t", "test", "-n", "2", "-m", "100", "-p"),
                ("run", "-y", "2018", "-c", "skim", "-s", "TT", "--dry", "--preselect", "Muon_pt>20"),
                ("run", "-y", "2018", "-c", "mutau", "--dry", "-i", "a.root", "b.root")]
    result = {"run": [{"command": list(command), "executed": [line for line in ws.pico(*command)["lines"]
                                                               if "Executing:" in line]} for command in commands]}
    result["get"] = [{"command": list(command), "lines": ws.pico(*command)["lines"]}
                     for command in (("get", "samples", "-y", "2018"), ("get", "files", "-y", "2018", "-s", "DY"))]
    return result


def pico_jobs(workspace):
    from BBB.pico_harness import PicoWorkspace
    ws = PicoWorkspace(workspace)
    result = {}
    ws.pico("submit", "-y", "2018", "-c", "mutau", "-s", "DY")              # cluster 1001: file chunks
    ws.pico("submit", "-y", "2018", "-c", "mutau", "-s", "Single", "-m", "3")  # cluster 1002: event chunks
    ws.pico("submit", "-y", "2018", "-c", "skim", "-s", "TT", "-E", "x=1")  # cluster 1003: skim chunks
    ws.pico("submit", "-y", "2018", "-c", "mutau", "-s", "DY")              # existing job config: skipped
    result["submitted"] = {"jobs": ws.jobfiles(), "scheduler": ws.submissions()}
    # Job outcomes: good, corrupt, pending (in the fake queue) and missing chunks.
    out = ws.root / "jobout" / "2018" / "mutau"
    ws.write_pico(out / "DYJetsToLL_M-50" / "pico_mutau_0.root")
    ws.write_pico(out / "DYJetsToLL_M-50" / "pico_mutau_1.root", valid=False)
    for chunk in (0, 1, 2):
        ws.write_pico(out / "SingleMuon_Run2018A" / ("pico_mutau_%d.root" % chunk))
    ws.write_pico(out / "SingleMuon_Run2018A" / "pico_mutau_4.root", valid=False)
    skimdir = ws.root / "nanoout" / "2018" / "TTTo2L2Nu_BBB" / "RunIIBBB-v1" / "NANOAODSIM"
    ws.write_skim(skimdir / "nano_0_skim.root")
    ws.queue([(1002, 3, 2, "python3 picojob.py -y 2018 -t _mutau_3 -i x.root"),
              (1003, 1, 1, "python3 skimjob.py -t _skim -i %s" % ws.inputs["TTTo2L2Nu"][1])])
    summary = r"SUCCESS|PEND|FAIL|MISS"
    result["status"] = {channel: [line for line in ws.pico("status", "-y", "2018", "-c", channel)["lines"]
                                  if re.search(summary, line)] for channel in ("mutau", "skim")}
    ws.pico("resubmit", "-y", "2018", "-c", "mutau")
    ws.pico("resubmit", "-y", "2018", "-c", "skim")
    result["resubmitted"] = {"jobs": ws.jobfiles(), "scheduler": ws.submissions()}
    return result


def pico_merge(workspace):
    from BBB.pico_harness import PicoWorkspace
    from BBB.snapshot import file_snapshot
    ws = PicoWorkspace(workspace)
    for sample in ("DY", "TT", "Single"):  # clusters 1001-1003, two chunks each
        ws.pico("submit", "-y", "2018", "-c", "mutau", "-s", sample)
    out = ws.root / "jobout" / "2018" / "mutau"
    for sample, chunks in (("DYJetsToLL_M-50", (0, 1)), ("TTTo2L2Nu", (0, 1)), ("SingleMuon_Run2018A", (0,))):
        for chunk in chunks:
            ws.write_pico(out / sample / ("pico_mutau_%d.root" % chunk))
    roots = (ws.basedir / "output", ws.root / "jobout", ws.root / "pico")
    result = {}
    ws.pico("hadd", "-y", "2018", "-c", "mutau", "-s", "Single")  # refused: a chunk is missing
    result["refused"] = ws.tree(*roots)
    ws.pico("hadd", "-y", "2018", "-c", "mutau", "-s", "DY")
    result["hadd"] = {"merged": file_snapshot(ws.root / "pico" / "2018" / "DY" / "DYJetsToLL_M-50_mutau.root"),
                      "files": ws.tree(*roots)}
    ws.pico("haddclean", "-y", "2018", "-c", "mutau", "-s", "TT")
    result["haddclean"] = {"merged": file_snapshot(ws.root / "pico" / "2018" / "TT" / "TTTo2L2Nu_mutau.root"),
                           "files": ws.tree(*roots)}
    ws.pico("clean", "-y", "2018", "-c", "mutau", "-s", "Single", "-f")
    result["clean"] = ws.tree(*roots)
    return result


def pico_workers(workspace):
    from BBB.pico_harness import PicoWorkspace, write_nano
    from BBB.snapshot import file_snapshot
    ws = PicoWorkspace(workspace)
    first = write_nano(ws.root / "worker" / "nano_A.root", 40, seed=3)
    second = write_nano(ws.root / "worker" / "nano_B.root", 40, seed=4)
    (ws.root / "copied").mkdir()
    ws.worker("picojob.py", "-i", first, "-o", "out_full", "-y", "2018", "-M", "ModuleMuTauSimple",
              "-t", "full", "-d", "mc", "-E", "tes=1.0")
    ws.worker("picojob.py", "-i", first, second, "-o", "out_range", "-y", "2018", "-M", "ModuleMuTauSimple",
              "-t", "_range", "--firstevt", "5", "-m", "20")
    ws.worker("picojob.py", "-i", second, "-o", "out_copy", "-C", ws.root / "copied", "-y", "2018", "-c", "mutau",
              "-M", "ModuleMuTauSimple", "-d", "mc", "-t", "_mutau_0", "--opt", "tes=1.0", "zpt=True")
    ws.worker("skimjob.py", "-i", first, second, "-o", "out_skim", "-y", "2018", "-d", "mc", "-t", "skim",
              "--preselect", "HLT_IsoMu24 && Muon_pt[0]>25")
    ws.worker("skimjob.py", "-i", first, "-o", "out_skimrange", "-y", "2018", "-d", "mc",
              "--firstevt", "10", "-m", "15")
    outputs = ["out_full/pico_full.root", "out_range/pico_range.root", "copied/pico_mutau_0.root",
               "out_skim/nano_A_skim.root", "out_skim/nano_B_skim.root", "out_skimrange/nano_A_skim.root"]
    return {"files": ws.tree(ws.root / "out_full", ws.root / "out_range", ws.root / "out_copy", ws.root / "copied",
                             ws.root / "out_skim", ws.root / "out_skimrange"),
            "outputs": {name: file_snapshot(ws.root / name) for name in outputs}}


# ===== Framework (black box: taufw.py in child processes, PicoProducer with the fake scheduler) =====

def framework_production(workspace):
    import json
    from BBB.pico_harness import PicoWorkspace, REPO
    from BBB.snapshot import file_snapshot
    ws = PicoWorkspace(workspace)
    taufw = REPO / "Framework" / "scripts" / "taufw.py"
    recipe = ws.root / "recipe.json"
    recipe.write_text(json.dumps({"name": "bbb", "pico": {"config": None}, "stages": [
        {"stage": "production", "id": "production", "inputs": None, "eras": ["2018"], "channels": ["mutau"],
         "samples": ["DY", "TT"], "max_tries": 2,
         "merge": {"clean": True}}]}), encoding="utf-8")  # Part G: the local stages run scripts; not in BBB
    runs = ws.root / "runs"

    def masked(value):
        """The run ID ends with the start time (and is part of the tuple paths): mask it, so the snapshot is
        repeatable."""
        return json.loads(re.sub(r"bbb_\d{8}-\d{6}(?:-\d+)?", "bbb_<time>", json.dumps(value)))

    def record():
        """run.json without times and run IDs; workspace paths as $WS."""
        (run_dir,) = list(runs.iterdir())
        data = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        for key in ("run_id", "created", "updated"):
            data.pop(key)
        for stage in data["stages"]:
            for entry in stage["history"]:
                entry.pop("time")
        return masked(ws.normalize(data))

    result = {"plan": ws.execute(taufw, "plan", recipe)["lines"]}
    ws.execute(taufw, "start", recipe, "--run-root", runs)  # submits DY (2 chunks) and TT (2 chunks)
    result["started"] = record()
    out = ws.root / "jobout" / "2018" / "mutau"
    for sample, chunk in (("DYJetsToLL_M-50", 0), ("DYJetsToLL_M-50", 1), ("TTTo2L2Nu", 0)):
        ws.write_pico(out / sample / ("pico_mutau_%d.root" % chunk))
    (run_dir,) = list(runs.iterdir())
    ws.execute(taufw, "advance", run_dir)  # TT chunk 1 is missing: resubmitted (try 2)
    result["resubmitted"] = record()
    ws.write_pico(out / "TTTo2L2Nu" / "pico_mutau_1.root")
    ws.execute(taufw, "advance", run_dir)  # complete: merged and cleaned; the run is DONE
    result["done"] = record()
    result["status"] = masked(ws.execute(taufw, "status", run_dir)["lines"])
    # CL §18 step 5: the merged tuples are in the production stage's directory of the run, not in picodir
    tuples = run_dir / "stages" / "production"
    result["merged"] = {name: file_snapshot(tuples / "2018" / group / name)
                        for group, name in (("DY", "DYJetsToLL_M-50_mutau.root"), ("TT", "TTTo2L2Nu_mutau.root"))}
    result["files"] = masked(ws.tree(ws.basedir / "output", ws.root / "jobout", ws.root / "pico", tuples))
    return result


def fitter_shapes(workspace):
    from TauFW.Fitter.plot.datacard import createinputs
    from TauFW.Histogrammer.spec.Variable import Variable
    from TauFW.Histogrammer.spec.Selection import Selection
    from BBB.snapshot import file_snapshot
    samples, files = _samples(workspace)
    outdir = Path(workspace) / "shapes"
    variables = [Variable("m_vis", [0, 20, 40, 60, 80, 100, 120, 160])]
    selections = [Selection("os", "q_1*q_2<0 && pt_1>20"), Selection("ss", "q_1*q_2>0 && pt_1>20")]
    common = {"outdir": str(outdir), "nthreads": 1, "method": None, "replacename": [("Data", "data_obs")]}
    createinputs("shapes_$OBS.root", samples, variables, selections, recreate=True, noneg=True, **common)
    createinputs("shapes_$OBS.root", samples, variables, selections, syst="_weightUp", noneg=True,
                 replaceweight=("weight", "weight_up"), **common)
    createinputs("shapes_$OBS.root", samples, variables, selections, syst="_weightDown", noneg=True,
                 replaceweight=("weight", "weight_down"), **common)
    createinputs("raw_$OBS.root", samples, variables, selections, recreate=True, noneg=False, **common)
    paths = sorted(outdir.glob("*.root"))
    if len(paths) != 2:
        raise RuntimeError("Expected nominal/systematic and unsanitized shape outputs.")
    return {path.name: file_snapshot(path) for path in paths}


def fitter_rebin(workspace):
    from TauFW.Fitter.plot.rebinning import rebinning
    from support.fixtures import write_shapes
    from BBB.snapshot import file_snapshot
    path = write_shapes(Path(workspace) / "input_shapes.root")
    rebinning(str(path), subtract_nonztt_only=True)
    subtract = file_snapshot(Path(workspace) / "subtract_nonztt" / path.name)
    result = rebinning(str(path))
    return {"edges": result.binedges, "rebinned": file_snapshot(Path(workspace) / "rebinning" / path.name),
            "subtracted": subtract}


# ===== TES INPUTS (createinputsTES.py end to end; plan 16, CL §25) =====

# A mini channel config with every part createinputsTES.py reads: regions (one with its own binning), the YAML
# anchor, an observable with an extra cut, TES variations, the samples block (filename, join, split, rename, data,
# removeSFs), processes, a shape systematic with variation files (sampleAppend), one with a weight replacement
# (nomWeight/altWeights) and an lnN one (skipped by the script).
_TES_CONFIG = """\
channel: mutau
tag: "_mutau"
baselineCuts: "q_1*q_2<0 && pt_1>20"
regions:
    DM0:
        definition: "dm_2==0"
        title: "h^{#pm}"
    DM1:
        definition: "dm_2==1"
        title: "h^{#pm}h^{0}"
    DM10:
        definition: "dm_2>=10"
        title: "h^{#pm}h^{#mp}h^{#pm}"
        binning: [4, 0, 200]
plottingOrder: &region_list ["DM0", "DM1", "DM10"]
observables:
    m_vis:
        binning: [8, 0, 200]
        title: "m_{vis}"
        extra:
            cut: "0<m_vis && m_vis<200"
        fitRegions: *region_list
TESvariations:
    values: [0.970, 1.030]
    processes: ["ZTT"]
samples:
    filename: "$PICODIR/$SAMPLE_$CHANNEL$TAG.root"
    join: ["VV", "TT", "ST"]
    split:
        DY: [["ZTT", "genmatch_2==5"], ["ZL", "genmatch_2>0 && genmatch_2<5"], ["ZJ", "genmatch_2==0"]]
        TT: [["TTT", "genmatch_2==5"], ["TTL", "genmatch_2>0 && genmatch_2<5"], ["TTJ", "genmatch_2==0"]]
    rename:
        WJ: "W"
    data: "data_obs"
    removeSFs: ["idweight"]
processes: ["ZTT", "ZL", "ZJ", "W", "VV", "ST", "TTT", "TTL", "TTJ", "QCD", "data_obs"]
systematics:
    LTF:
        effect: "shape"
        processes: ["ZL", "TTL"]
        name: "shape_mTauFake_$BIN"
        title: "+/- 3% LTF shape"
        variations: ["Up", "Down"]
        sampleAppend: ["_LTF1p030", "_LTF0p970"]
    weight:
        effect: "shape"
        processes: ["W"]
        name: "shape_weight_$BIN"
        title: "weight up/down"
        variations: ["Up", "Down"]
        nomWeight: "genweight"
        altWeights: ["weight_up", "weight_down"]
    xsec_dy:
        effect: "lnN"
        processes: ["ZTT", "ZL", "ZJ"]
        scaleFactor: 1.02
"""

# A mini sample model (Histogrammer/python/sample/model.py format) for era 2025: two samples per group, so that the
# joins of the model (DY, WJ) and of the config (VV, TT, ST) really merge; weight genweight*idweight (idweight is
# removed by the config's removeSFs).
_TES_SAMPLES = """\
era: "2025"
cme: 13.6
extraweights: {}
mc:
  - {group: "DY", name: "DYto2Tau_Bin-MLL-50to120", title: "Drell-Yan tautau", xsec: 2000.0}
  - {group: "DY", name: "DYto2Mu_Bin-MLL-50to120", title: "Drell-Yan mumu", xsec: 2100.0}
  - {group: "WJ", name: "WtoMuNu-2Jets", title: "Wmu + jets", xsec: 21000.0}
  - {group: "WJ", name: "WtoTauNu-2Jets", title: "Wtau + jets", xsec: 20000.0}
  - {group: "VV", name: "WZ", title: "WZ", xsec: 41.0}
  - {group: "VV", name: "ZZto4L", title: "ZZ 4l", xsec: 6.6}
  - {group: "TT", name: "TTto2L2Nu", title: "ttbar 2l2#nu", xsec: 98.0}
  - {group: "TT", name: "TTtoLNu2Q", title: "ttbar semileptonic", xsec: 405.0}
  - {group: "ST", name: "TWminusto2L2Nu", title: "ST tW 2l2#nu", xsec: 3.8}
  - {group: "ST", name: "TbarWplusto2L2Nu", title: "ST atW 2l2#nu", xsec: 3.9}
data:
  muon: "Muon*Run2025*"
weights:
  semileptonic: "genweight*idweight"
stitch: []
join:
  - {patterns: ["Wto*Nu-2Jets"], name: "WJ"}
"""

# Variation tuples: <sample>_mutau<tag>.root next to the nominal ones, the fixture rows with m_vis scaled (so the
# shifted shapes differ); only the samples the script shifts (TES: the DY samples of ZTT; LTF: DY and TT).
_TES_VARIATIONS = {"_TES0p970": (0.970, "DY"), "_TES1p030": (1.030, "DY"),
                   "_LTF1p030": (1.030, "DY", "TT"), "_LTF0p970": (0.970, "DY", "TT")}


def _tes_inputs_script():
    """The script under test: the only line that changes when createinputsTES.py moves (plan 16, H1)."""
    return Path(__file__).resolve().parents[2] / "Fitter" / "TauES" / "createinputsTES.py"


def _tes_file_snapshot(path):
    """A shape file: every directory and histogram in full, a TNamed's title; other objects (the TCanvas and TStyle
    plotinputs writes) by key, cycle and class only."""
    import ROOT
    from BBB.snapshot import histogram_snapshot

    def directory(folder):
        result = []
        for key in sorted(folder.GetListOfKeys(), key=lambda key: (key.GetName(), key.GetCycle())):
            entry = {"key": key.GetName(), "cycle": key.GetCycle(), "class": key.GetClassName()}
            obj = key.ReadObj()
            if obj.InheritsFrom("TDirectory"):
                entry["objects"] = directory(obj)
            elif obj.InheritsFrom("TH1"):
                entry["histogram"] = histogram_snapshot(obj)
            elif obj.ClassName() == "TNamed":
                entry["title"] = obj.GetTitle()
            result.append(entry)
        return result

    source = ROOT.TFile.Open(str(path), "READ")
    if not source or source.IsZombie():
        raise RuntimeError("Cannot read ROOT output %s" % path)
    try:
        return directory(source)
    finally:
        source.Close()


def histogrammer_tes_inputs(workspace):
    """createinputsTES.py end to end on fixture tuples (nominal and variation files), a mini sample model and a mini
    config: shape file, rebinned file and the names of the control plots. Run in its own interpreter (it sets the
    era globals, sys.path and sys.modules['config'], and writes into its working directory), serially (-s: the
    multithreaded fill differs in the last bits between runs)."""
    import subprocess
    import sys
    from support.fixtures import rows, write_tree
    base = Path(workspace) / "tes"
    tuples = base / "tuples" / "2025"
    groups = {}
    for line in _TES_SAMPLES.splitlines():
        if line.startswith("  - {group:"):
            group, name = re.search(r'group: "(\w+)", name: "([\w-]+)"', line).groups()
            groups.setdefault(group, []).append(name)
            write_tree(tuples / group / ("%s_mutau.root" % name))
    write_tree(tuples / "Data" / "Muon_Run2025C_mutau.root", data=True)
    for tag, (scale, *shifted) in _TES_VARIATIONS.items():
        events = [dict(row, m_vis=row["m_vis"] * scale) for row in rows()]
        for group in shifted:
            for name in groups[group]:
                write_tree(tuples / group / ("%s_mutau%s.root" % (name, tag)), events=events)
    (base / "tes_mutau.yml").write_text(_TES_CONFIG, encoding="utf-8")
    (base / "samples_2025.yml").write_text(_TES_SAMPLES, encoding="utf-8")
    entry = Path(__file__).resolve().parent / "pico_entry.py"  # a fresh interpreter with the test mirror attached
    command = [sys.executable, "-B", str(entry), str(Path.cwd()), str(_tes_inputs_script()),
               "-y", "2025", "-c", "tes_mutau.yml", "-s", "-O", "out", "-j", "Medium", "-e", "VVLoose",
               "--tuples", str(base / "tuples" / "$ERA" / "$GROUP"), "--samples", "samples_2025.yml"]
    result = subprocess.run(command, cwd=str(base), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            universal_newlines=True)
    sys.stdout.write(result.stdout)  # in the case log only; the snapshot holds files, never this text
    if result.returncode:
        raise RuntimeError("createinputsTES.py failed (exit %s); see the case log" % (result.returncode))
    out = base / "out"
    roots = sorted(path for path in out.rglob("*.root"))
    shapes = [path for path in roots if path.parent.name != "rebinning"]
    if not shapes or not any(path.parent.name == "rebinning" for path in roots):
        raise RuntimeError("No shape file or no rebinned file under %s; refusing a no-op baseline." % (out))
    return {"files": {path.relative_to(out).as_posix(): _tes_file_snapshot(path) for path in roots},
            "other_files": sorted(path.relative_to(out).as_posix() for path in out.rglob("*")
                                  if path.is_file() and path.suffix != ".root")}



# ===== DRAWING (Plot, Stack, Ratio, Plot2D, CMSStyle, SampleStyle, histogram helpers, labels) =====

_ADDRESS = re.compile(r"0x[0-9a-fA-F]+")
# The old and the new module paths of the code (CL §24) normalise alike.
_DRAWING_MODULE = re.compile(r"TauFW\.(?:Plotter\.(?:plot|sample)|Histogrammer\.(?:spec|sample)|Utilities\.Drawing)\.")


def _sample_model_recorder():
    """Tests/Histogrammer/sample_model/recorder.py (records the core calls of a sample-set function)."""
    import importlib.util
    import sys
    if "sample_model_recorder" not in sys.modules:
        path = Path(__file__).resolve().parents[1] / "Histogrammer" / "sample_model" / "recorder.py"
        spec = importlib.util.spec_from_file_location("sample_model_recorder", str(path))
        module = importlib.util.module_from_spec(spec)
        sys.modules["sample_model_recorder"] = module
        spec.loader.exec_module(module)
    return sys.modules["sample_model_recorder"]


def _sample_model_function(recorder):
    """The sample-set function under test and the core functions the recorder replaces. Only this function changed
    when the samples moved to Configs/Histogrammer/samples/: the case was locked with Plotter/config/samples_v15.py
    (getsampleset, recorder.old_targets) and now runs TauFW.Histogrammer.sample.model.getsampleset with them."""
    import importlib
    utils = importlib.import_module("TauFW.Histogrammer.sample.utils")
    from TauFW.Histogrammer.sample import model
    templates = sorted(str(path) for path in
                       (Path(__file__).resolve().parents[2] / "Configs" / "Histogrammer" / "samples").glob("v15_*.yml"))
    models = {}

    def getsampleset(channel, era, **kwargs):
        if era not in models:
            models[era] = model.pick(templates, era)
        return model.getsampleset(channel, era, models[era], **kwargs)
    return getsampleset, recorder.model_targets(utils)


def plotter_sample_model(workspace):
    """The core calls (setera, getsampleset, stitch, join, split, printtable) of the sample-set function for every
    era, channel kind and caller option of the recorder; locked with Plotter/config/samples_v15.py. A call that
    raises is recorded as 'raised' (its message may differ once the model replaces samples_v15.py)."""
    recorder = _sample_model_recorder()
    function, targets = _sample_model_function(recorder)
    grid = recorder.record_grid(function, targets)
    if not any(calls and calls[-1][0] != 'raised' for calls in grid.values()):
        raise RuntimeError("No sample set was built; refusing a no-op baseline.")
    return {key: [call if call[0] != 'raised' else ['raised'] for call in calls] for key, calls in grid.items()}


def _drawing_modules():
    """The drawing code under test. Only this function changes when the drawing code moves."""
    import TauFW.Utilities.Drawing.CMSStyle as CMSStyle
    import TauFW.Utilities.Drawing.hist_tools as hist_tools
    import TauFW.Utilities.Drawing.labels as labels
    import TauFW.Utilities.Drawing.SampleStyle as SampleStyle
    from TauFW.Utilities.Drawing.Plot import Plot
    from TauFW.Utilities.Drawing.Plot2D import Plot2D
    from TauFW.Utilities.Drawing.Stack import Stack
    from TauFW.Histogrammer.spec.Variable import Variable
    return SimpleNamespace(CMSStyle=CMSStyle, hist_tools=hist_tools, labels=labels, SampleStyle=SampleStyle,
                           LOG=hist_tools.LOG, Plot=Plot, Plot2D=Plot2D, Stack=Stack, Variable=Variable)


def _clean(text):
    """Object addresses and the module path of the drawing code are not part of the output."""
    return _DRAWING_MODULE.sub("<drawing>.", _ADDRESS.sub("0x?", text))


def _attempt(function):
    try:
        return function()
    except Exception as error:
        return {"exception": type(error).__name__, "message": _clean(str(error))}


def _drawn_value(value):
    from array import array
    from ROOT import TObject
    from BBB.snapshot import drawn_snapshot
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, TObject):
        return drawn_snapshot(value)
    if isinstance(value, (list, tuple, array)):
        return [_drawn_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _drawn_value(item) for key, item in value.items()}
    return _clean(repr(value))


_EDGES = [0, 20, 40, 60, 80, 100, 120, 160]
_YIELDS = {"data": [12, 30, 55, 40, 22, 10, 4, 1], "DY": [8, 25, 45, 30, 15, 6, 2, 0.5],
           "TT": [2, 3, 5, 6, 5, 3, 1.5, 0.4], "ST": [0.5, 1, 1.5, 1, 0.8, 0.5, 0.2, 0.1],
           "WJ": [1, 2, 3, 2, 2, 1, 0.5, 0.1], "signal": [0, 0.5, 1, 3, 1, 0.5, 0, 0]}


def _drawing_hist(name, values, edges=None):
    from array import array
    from ROOT import TH1D
    if edges:
        hist = TH1D(name, name, len(edges) - 1, array("d", edges))
    else:
        hist = TH1D(name, name, len(values), 0, 160)
    for index, value in enumerate(values, start=1):
        hist.SetBinContent(index, value)
        hist.SetBinError(index, value ** 0.5)
    return hist


def _drawing_graph(name, hist):
    from ROOT import TGraphAsymmErrors
    graph = TGraphAsymmErrors()
    graph.SetName(name)
    graph.SetTitle(name)
    for point in range(hist.GetNbinsX()):
        axis, index = hist.GetXaxis(), point + 1
        graph.SetPoint(point, axis.GetBinCenter(index), hist.GetBinContent(index))
        width = axis.GetBinWidth(index) / 2
        graph.SetPointError(point, width, width, hist.GetBinError(index), 1.5 * hist.GetBinError(index))
    return graph


def _drawn_plot(plot, outdir, name, extra=None):
    from BBB.snapshot import drawn_snapshot
    if extra:
        extra(plot)
    plot.saveas(name + ".png", name + ".pdf", outdir=str(outdir))
    return drawn_snapshot(plot.canvas)


def _drawing_plots(m, outdir):
    hists = {name: _drawing_hist("h_" + name, values) for name, values in _YIELDS.items()}
    varhists = {name: _drawing_hist("v_" + name, values[:7], _EDGES) for name, values in _YIELDS.items()}
    variable = m.Variable("m_vis", "m_{vis} [GeV]", 8, 0, 160)
    varbins = m.Variable("m_vis", "m_{vis} [GeV]", _EDGES)
    result = {}

    def compare():
        plot = m.Plot(variable, [hists["DY"], hists["TT"], hists["WJ"]], clone=True)
        plot.draw(ratio=True, staterr=True, grid=True, norm=True)
        plot.drawlegend("topright", header="Synthetic")
        plot.drawtext("BBB drawing", "second line")
        return _drawn_plot(plot, outdir, "compare")
    result["compare"] = _attempt(compare)

    def variable_bins():
        plot = m.Plot(varbins, [varhists["DY"], varhists["TT"]], clone=True)
        plot.draw(ratio=False, logy=True)
        plot.drawlegend("right")
        return _drawn_plot(plot, outdir, "varbins")
    result["variable_bins"] = _attempt(variable_bins)

    def drawbins():  # as in Fitter/Zpt/measureZpt.py: drawbins needs the plot's ymin and ymax
        plot = m.Plot(variable, [hists["DY"], hists["TT"]], clone=True, ymin=0, ymax=60)
        plot.draw(ratio=False)
        plot.drawbins(varbins, y=0.96, text="m_{vis}", addoverflow=True)
        return _drawn_plot(plot, outdir, "drawbins")
    result["drawbins"] = _attempt(drawbins)

    def stack():
        plot = m.Stack(variable, hists["data"], [hists["DY"], hists["TT"], hists["WJ"]], [hists["signal"]],
                       clone=True)
        plot.draw(ratio=True, staterr=True)
        plot.drawlegend(position="right")
        plot.drawtext("Stack")
        return _drawn_plot(plot, outdir, "stack")
    result["stack"] = _attempt(stack)

    def fraction():
        plot = m.Stack(variable, hists["data"], [hists["DY"], hists["TT"]], clone=True)
        plot.draw(ratio=True, fraction=True, logy=True)
        return _drawn_plot(plot, outdir, "fraction")
    result["fraction"] = _attempt(fraction)

    def graphs():
        graph_list = [_drawing_graph("g_data", hists["data"]), _drawing_graph("g_DY", hists["DY"])]
        plot = m.Plot("m_{vis} [GeV]", graph_list)
        plot.draw(ratio=False)
        plot.drawlegend()
        return _drawn_plot(plot, outdir, "graphs")
    result["graphs"] = _attempt(graphs)

    def two_dimensional():
        from ROOT import TH2D
        hist = TH2D("h2_mvis_pt", "h2_mvis_pt", 8, 0, 160, 4, 20, 100)
        for xbin in range(1, 9):
            for ybin in range(1, 5):
                hist.SetBinContent(xbin, ybin, xbin * ybin + 0.5 * ybin)
        plot = m.Plot2D(variable, m.Variable("pt_1", "p_{T}", 4, 20, 100), hist)
        plot.draw()
        plot.drawtext("Plot2D")
        return _drawn_plot(plot, outdir, "plot2d")
    result["plot2d"] = _attempt(two_dimensional)
    return result


def _drawing_tools(m):
    from ROOT import THStack
    tools = m.hist_tools
    result = {}

    def fresh(name, edges=None):
        return _drawing_hist("t_%s" % name, _YIELDS[name][:7] if edges else _YIELDS[name], edges)

    def graph():
        return _drawing_graph("t_graph", fresh("data"))

    def normalize():
        hists = [fresh("DY"), fresh("TT")]
        tools.normalize(*hists)
        return _drawn_value(hists)
    result["normalize"] = _attempt(normalize)

    def grouphists():
        hists = [fresh(name) for name in ("DY", "TT", "ST", "WJ")]
        for hist in hists:
            hist.SetName(hist.GetName()[2:])
        total = tools.grouphists(hists, ["TT", "ST"], "Top", replace=True)
        return {"sum": _drawn_value(total), "left": [hist.GetName() for hist in hists]}
    result["grouphists"] = _attempt(grouphists)

    def capoff():
        hist = fresh("DY")
        return [tools.capoff(hist, 5, 40), hist]

    def ensurepoisson():
        hist = fresh("data")
        return [tools.ensurepoisson(hist), hist]

    calls = {
        "gethistratio": lambda: tools.gethistratio(fresh("data"), fresh("DY")),
        "getgraphratio": lambda: tools.getgraphratio(graph(), fresh("DY")),
        "geterrorband": lambda: tools.geterrorband(fresh("DY"), fresh("TT")),
        "dividebybinsize": lambda: tools.dividebybinsize(fresh("DY", _EDGES)),
        "dividebybinsize_graph": lambda: tools.dividebybinsize(fresh("data", _EDGES), graph=True),
        "addoverflow": lambda: tools.addoverflow(fresh("DY")),
        "capoff": capoff,
        "resetrange": lambda: tools.resetrange(fresh("DY"), 20, 140),
        "getconstanthist": lambda: tools.getconstanthist(fresh("DY"), 1),
        "getbinning": lambda: tools.getbinning(fresh("DY", _EDGES), 20, 140),
        "resetedges": lambda: tools.resetedges(list(_EDGES), 10, 150),
        "havesamebins": lambda: [tools.havesamebins(fresh("DY"), fresh("TT")),
                                 tools.havesamebins(fresh("DY"), fresh("TT", _EDGES))],
        "getbinedges": lambda: tools.getbinedges(fresh("DY", _EDGES)),
        "getTGraphRange": lambda: tools.getTGraphRange([graph()], axis="xy"),
        "sumhists": lambda: tools.sumhists([fresh("DY"), fresh("TT")], "t_sum"),
        "ensurepoisson": ensurepoisson,
    }
    for name, call in calls.items():
        result[name] = _attempt(lambda call=call: _drawn_value(call()))

    def normalizebins():  # as in Ratio (fraction panel): the stack is drawn, so it has an axis
        from ROOT import TCanvas
        canvas = TCanvas("t_canvas", "t_canvas")
        stack = THStack("t_stack", "t_stack")
        for name in ("DY", "TT", "WJ"):
            stack.Add(fresh(name))
        stack.Draw("HIST")
        result = _drawn_value(tools.normalizebins(stack))
        canvas.Close()
        return result
    result["normalizebins"] = _attempt(normalizebins)
    return result


def _drawing_labels(m):
    names = ["pt_1", "pt_2", "m_vis", "eta_2", "jpt_1", "dzeta", "njets", "met", "mt_1", "m_vis [GeV]", "DM0",
             "pt_1+pt_2+jpt_1", "abs(eta_2)", "idDeepTau2018v2p5VSjet_2>=5"]
    labels = m.labels
    return {"makelatex": [_attempt(lambda name=name: labels.makelatex(name)) for name in names],
            "maketitle": [_attempt(lambda name=name: labels.maketitle(name)) for name in names],
            "makehistname": _attempt(lambda: labels.makehistname("m_vis", "pt_1>20.5 && q_1*q_2<0", "DY")),
            "makefilename": _attempt(lambda: labels.makefilename("pt_1>20 && abs(eta_2)<2.3", "m_t")),
            "estimatelen": _attempt(lambda: labels.estimatelen(["p_{T}^{miss}", "m_{#lower[-0.1]{vis}}", "#tau_{h}",
                                                                "two\nlines"])),
            "match": _attempt(lambda: [labels.match(["TT", "ST*"], label) for label in ("TT", "ST_t", "DY")])}


def _drawing_styles(m):
    cms, samples = m.CMSStyle, m.SampleStyle
    result = {}

    def texts():
        return {"cms": cms.cmsText, "extra": cms.extraText, "lumi": cms.lumiText}

    cms.setCMSEra("2018")
    result["era_2018"] = texts()
    result["lumitext_2022_postEE"] = _attempt(lambda: cms.getCMSLumiText("2022_postEE"))
    cms.setCMSEra("2016", "2017")
    result["era_2016_2017"] = texts()
    cms.setCMSEra("2018")
    result["colors"] = [_attempt(lambda name=name: samples.getcolor(name, verb=3))
                        for name in ("DY", "ZTT", "TT", "Top", "no_such_sample")]
    result["titles"] = [_attempt(lambda name=name: samples.gettitle(name, verb=3))
                        for name in ("DY", "ZTT", "no_such_sample")]
    return result


def drawing_canvas(workspace):
    """Exact drawn canvases, styles and verbose output of the drawing code (locked before it moved to Utilities)."""
    from BBB.snapshot import style_snapshot
    outdir = Path(workspace) / "plots"
    outdir.mkdir()
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        m = _drawing_modules()
        result = {"style": style_snapshot()}
        m.LOG.verbosity = 3
        result["styles"] = _drawing_styles(m)
        result["labels"] = _drawing_labels(m)
        result["tools"] = _drawing_tools(m)
        result["plots"] = _drawing_plots(m, outdir)
        result["style_after"] = style_snapshot()
    result["files"] = sorted(path.name for path in outdir.iterdir())
    result["stdout"] = _clean(output.getvalue()).splitlines()
    return result


ROOT_DEPS = ["ROOT", "numpy", "past"]
NANO_DEPS = ROOT_DEPS + ["PhysicsTools.NanoAODTools.postprocessing.framework.postprocessor"]
PICO_DEPS = NANO_DEPS
CASES = {
    "common.formatting": {"run": common_formatting, "dependencies": ["past"], "description": "Exact table and loading-bar text"},
    "common.chunking": {"run": common_chunking, "dependencies": ["past"], "description": "Chunking, partitioning, argument and path formatting"},
    "plotter.context": {"run": plotter_context, "dependencies": ROOT_DEPS, "description": "Selection strings and contextual variable metadata"},
    "plotter.histograms": {"run": plotter_histograms, "dependencies": ROOT_DEPS, "description": "Weighted 1D/2D histograms, errors, flow bins and normalization"},
    "plotter.merge_split": {"run": plotter_merge_split, "dependencies": ROOT_DEPS, "description": "Before/after merge and genmatch splitting"},
    "plotter.stitch": {"run": plotter_stitch, "dependencies": ROOT_DEPS, "description": "Inclusive and exclusive DY parton-bin stitching"},
    "plotter.qcd": {"run": plotter_qcd, "dependencies": ROOT_DEPS, "description": "OS/SS QCD subtraction, negative bins and scaling"},
    "plotter.unroll": {"run": plotter_unroll, "dependencies": ROOT_DEPS, "description": "C++ unroll and roll-up of weighted histograms"},
    "plotter.sample_model": {"run": plotter_sample_model, "dependencies": ROOT_DEPS, "description": "Core calls of getsampleset (samples_v15.py, later the sample model) per era, channel kind and caller option"},
    "plotter.stack": {"run": plotter_stack, "dependencies": ROOT_DEPS, "description": "plot.py's path: era lumi, getstack with QCD_OSSS, drawn stacks (histograms, drawing attributes, canvases)"},
    "pico.writer": {"run": pico_writer, "dependencies": ROOT_DEPS, "description": "Tree schema, arrays, defaults, aliases, 64-bit IDs and cutflow"},
    "pico.bookkeeper": {"run": pico_bookkeeper, "dependencies": NANO_DEPS, "description": "Real NanoAODTools event loop, selections, ranges and weight bookkeeping"},
    "pico.scale_factors": {"run": pico_scale_factors, "dependencies": ROOT_DEPS, "description": "Local synthetic scale-factor lookup and boundary clamping"},
    "pico.config": {"run": pico_config, "dependencies": PICO_DEPS, "description": "pico.py config creation, backup recovery, channel/era links, set and rm"},
    "pico.run": {"run": pico_run, "dependencies": PICO_DEPS, "description": "pico.py run worker command lines and sample/file listing"},
    "pico.jobs": {"run": pico_jobs, "dependencies": PICO_DEPS, "description": "pico.py submit/status/resubmit: job configs, task lists, chunking, scheduler calls"},
    "pico.merge": {"run": pico_merge, "dependencies": PICO_DEPS, "description": "pico.py hadd/haddclean/clean: merge gate, merged tuple and cleanup"},
    "pico.workers": {"run": pico_workers, "dependencies": PICO_DEPS, "description": "picojob.py/skimjob.py outputs, ranges, options, copy and preselection"},
    "framework.production": {"run": framework_production, "dependencies": PICO_DEPS, "description": "taufw.py start/advance/status: production stage through the PicoProducer API, resubmission, merge, run.json"},
    "fitter.shapes": {"run": fitter_shapes, "dependencies": ROOT_DEPS, "description": "Nominal/systematic shape naming and negative-bin sanitation"},
    "fitter.rebin": {"run": fitter_rebin, "dependencies": ROOT_DEPS, "description": "Adaptive rebinning and non-ZTT background subtraction"},
    "histogrammer.tes_inputs": {"run": histogrammer_tes_inputs, "dependencies": ROOT_DEPS, "description": "createinputsTES.py end to end: config, sample model, splits, TES and shape variations (files and weights), QCD, shape file, rebinning, control-plot names"},
    "drawing.canvas": {"run": drawing_canvas, "dependencies": ROOT_DEPS, "description": "Drawn canvases, styles, histogram helpers, labels and verbose output of the drawing code"}
}
