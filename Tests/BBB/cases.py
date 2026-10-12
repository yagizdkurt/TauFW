"""Small characterization cases against the current production APIs.

Imports of ROOT and production code occur only inside separately selected workers.
"""
import contextlib
import io
from pathlib import Path
from types import SimpleNamespace


def common_formatting(workspace):
    from TauFW.common.tools.Table import Table
    from TauFW.common.tools.LoadingBar import LoadingBar
    table = Table("%8s %10s %10s", "%8d %10.2f %10.2f")
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        table.printheader("point", "x", "weight")
        for values in ((1, 0.0, 1.0), (2, -1.25, 0.0), (3, 2.5, -0.5)):
            table.printrow(*values)
        bar = LoadingBar(steps=3, width=6, counter=True)
        for _ in range(3):
            bar.count()
    return {"stdout": output.getvalue(), "partial_row": table.row(4, 1.25),
            "extra_row": table.row(5, 2.0, 1.0, "extra")}


def common_chunking(workspace):
    from TauFW.common.tools.utils import chunkify, ensurelist, unpacklistargs
    from TauFW.common.tools.math import partition, partition_by_max
    from TauFW.common.tools.string import repkey
    return {"chunks": {str(size): chunkify(list(range(7)), size) for size in (1, 3, 7, 10)},
            "empty": chunkify([], 3), "partition": partition(list(range(7)), nparts=3),
            "by_max": partition_by_max([2, 3, 4, 5, 1], 6),
            "ensure": [ensurelist(None), ensurelist(3), ensurelist((1, 2))],
            "unpacked": unpacklistargs(([1, 2],)),
            "path": repkey("$ERA/$SAMPLE.root", ERA="2018", SAMPLE="DY")}


def plotter_context(workspace):
    from TauFW.Plotter.plot.Selection import Selection
    from TauFW.Plotter.plot.Variable import Variable
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
    from TauFW.Plotter.sample.utils import Sample, SampleSet, setera
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
    from TauFW.Plotter.sample.MergedSample import MergedSample
    # A plain Sample sets samples=[self]; only a MergedSample has real children.
    children = sample.samples if isinstance(sample, MergedSample) else []
    return {"name": sample.name, "norm": sample.norm, "scale": sample.scale,
            "xsec": sample.xsec, "events": sample.nevents, "sumweights": sample.sumweights,
            "weight": sample.weight, "extraweight": sample.extraweight, "cuts": sample.cuts,
            "children": [_sample_state(child) for child in children]}


def plotter_histograms(workspace):
    from TauFW.Plotter.plot.Variable import Variable
    from TauFW.Plotter.plot.Selection import Selection
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
    from TauFW.Plotter.plot.Variable import Variable
    from TauFW.Plotter.plot.Selection import Selection
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
    from TauFW.Plotter.sample.utils import Sample, SampleSet, MergedSample
    from TauFW.Plotter.plot.Variable import Variable
    from TauFW.Plotter.plot.Selection import Selection
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
    from TauFW.Plotter.plot.Variable import Variable
    from TauFW.Plotter.plot.Selection import Selection
    samples, files = _samples(workspace)
    result = samples.gethists([Variable("m_vis", 8, 0, 160)],
                             [Selection("os", "q_1*q_2<0 && pt_1>20")],
                             method="QCD_OSSS", nthreads=1, blind=False, scale=1.1)
    histograms = _histsets(result)
    if not any("QCD" in hist["name"] for group in histograms for hist in group["histograms"]):
        raise RuntimeError("QCD output missing; refusing a no-op baseline.")
    return histograms


def plotter_unroll(workspace):
    import ROOT
    from support.fixtures import rows
    from BBB.snapshot import histogram_snapshot
    # Workers start in the temporary TauFW root, which contains the current copied source.
    macro = Path("Plotter/python/macros/Unroll.cxx").resolve()
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
    from TauFW.PicoProducer.processors.Bookkeeper import Bookkeeper
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


def fitter_shapes(workspace):
    from TauFW.Fitter.plot.datacard import createinputs
    from TauFW.Plotter.plot.Variable import Variable
    from TauFW.Plotter.plot.Selection import Selection
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


ROOT_DEPS = ["ROOT", "numpy", "past"]
NANO_DEPS = ROOT_DEPS + ["PhysicsTools.NanoAODTools.postprocessing.framework.postprocessor"]
CASES = {
    "common.formatting": {"run": common_formatting, "dependencies": ["past"], "description": "Exact table and loading-bar text"},
    "common.chunking": {"run": common_chunking, "dependencies": ["past"], "description": "Chunking, partitioning, argument and path formatting"},
    "plotter.context": {"run": plotter_context, "dependencies": ROOT_DEPS, "description": "Selection strings and contextual variable metadata"},
    "plotter.histograms": {"run": plotter_histograms, "dependencies": ROOT_DEPS, "description": "Weighted 1D/2D histograms, errors, flow bins and normalization"},
    "plotter.merge_split": {"run": plotter_merge_split, "dependencies": ROOT_DEPS, "description": "Before/after merge and genmatch splitting"},
    "plotter.stitch": {"run": plotter_stitch, "dependencies": ROOT_DEPS, "description": "Inclusive and exclusive DY parton-bin stitching"},
    "plotter.qcd": {"run": plotter_qcd, "dependencies": ROOT_DEPS, "description": "OS/SS QCD subtraction, negative bins and scaling"},
    "plotter.unroll": {"run": plotter_unroll, "dependencies": ROOT_DEPS, "description": "C++ unroll and roll-up of weighted histograms"},
    "pico.writer": {"run": pico_writer, "dependencies": ROOT_DEPS, "description": "Tree schema, arrays, defaults, aliases, 64-bit IDs and cutflow"},
    "pico.bookkeeper": {"run": pico_bookkeeper, "dependencies": NANO_DEPS, "description": "Real NanoAODTools event loop, selections, ranges and weight bookkeeping"},
    "pico.scale_factors": {"run": pico_scale_factors, "dependencies": ROOT_DEPS, "description": "Local synthetic scale-factor lookup and boundary clamping"},
    "fitter.shapes": {"run": fitter_shapes, "dependencies": ROOT_DEPS, "description": "Nominal/systematic shape naming and negative-bin sanitation"},
    "fitter.rebin": {"run": fitter_rebin, "dependencies": ROOT_DEPS, "description": "Adaptive rebinning and non-ZTT background subtraction"}
}
