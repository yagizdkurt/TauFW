#!/usr/bin/env python3
# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Feasibility check before the Plotter draws from histogram files (LocalR/architecture/18, S0; lxplus, needs ROOT).

The clean Plotter will not fill histograms: it will read them from a file written by the Histogrammer and draw them
with the unchanged drawing code. This one-off script checks the two assumptions behind that, on the BBB fixtures:

  A  memory   fill with SampleSet.gethists, draw with HistSet.getstack            (what plot.py does today)
  B  file     same histograms written to a ROOT file and read back, same Variable  -> is the file round trip exact?
  C  minimal  histograms from the file and, instead of the Variable, a plain object with only the attributes the
              drawing reads (Utilities/python/Drawing/Plot.py:89-106)            -> is that metadata enough?

For each stack it compares B and C with A: the drawn canvas (BBB drawn_snapshot) and the PNG bytes.

    cd $CMSSW_BASE/src/TauFW && cmsenv && python3 Tests/tools/roundtrip_spike.py

Exit status 0 when everything is equal. Nothing in the checkout is written (a temporary directory is used).
"""
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

TESTS = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(TESTS), str(TESTS / "support")]

# What Plot reads from a variable (Plot.py:89-106). getedge is only there so that the drawing library recognizes
# the object as a variable (hist_tools._is_variable); it is called only by Plot.drawbins.
DRAWING_ATTRIBUTES = ("filename", "title", "xmin", "xmax", "ymin", "ymax", "rmin", "rmax", "ratiorange", "binlabels",
                      "logx", "logy", "ymargin", "logyrange", "position", "ncols", "dividebins")


def minimal_variable(variable):
    """A plain object with only the drawing attributes of `variable` (what a histogram file would carry)."""
    values = {name: getattr(variable, name) for name in DRAWING_ATTRIBUTES}
    return SimpleNamespace(getedge=variable.getedge, **values)


def write_histset(directory, histset):
    """Write a HistSet's histograms into a TDirectory; return the names in stack order."""
    directory.cd()
    names = {"data": None, "exp": [], "sig": []}
    if histset.data:
        histset.data.Write("data")
        names["data"] = "data"
    for kind in ("exp", "sig"):
        for index, hist in enumerate(getattr(histset, kind)):
            key = "%s_%02d" % (kind, index)  # keeps the stack order explicit
            hist.Write(key)
            names[kind].append(key)
    return names


def read_hists(directory, names):
    """Read the histograms back, detached from the file (SetDirectory(0)), with their original names."""
    def read(key):
        hist = directory.Get(key)
        original = hist.GetName()
        hist = hist.Clone(original)
        hist.SetDirectory(0)
        return hist
    data = read(names["data"]) if names["data"] else None
    return data, [read(key) for key in names["exp"]], [read(key) for key in names["sig"]]


def draw(stack, png):
    from BBB.snapshot import drawn_snapshot
    stack.draw(fraction=False)
    stack.drawlegend()
    stack.drawtext("#mu#tau_{h}: spike")
    stack.saveas(str(png))
    snapshot = drawn_snapshot(stack.canvas)
    stack.close(keep=True)
    return snapshot


def main():
    from bootstrap import configure_root, dependencies, prepare
    workspace = Path(tempfile.mkdtemp(prefix="taufw-spike-"))
    dependencies(["ROOT", "numpy", "past"])
    mirror = prepare(workspace)
    os.chdir(str(mirror))
    configure_root(str(workspace), single_thread=True)

    from ROOT import TFile
    from BBB.cases import _stack_modules
    from BBB.snapshot import difference
    from support.fixtures import sample_files
    from TauFW.Utilities.Drawing.Stack import Stack
    m = _stack_modules()
    m.setera(2018)
    files = sample_files(workspace / "inputs")
    data = m.Sample("Data", "Observed", str(files["Data"]), data=True)
    mc = [m.Sample(name, name, str(files[name]), xsec, weight="weight")
          for name, xsec in (("DY", 0.01), ("WJ", 0.02), ("TT", 0.03))]
    samples = m.SampleSet(data, mc, channel="mutau", loadingbar=False)
    variables = [m.Variable("m_vis", "m_vis", 8, 0, 160, ctitle={"pt_1>": "m_vis (high pt)"},
                            cbins={"pt_1>": (4, 0, 160)}),
                 m.Variable("pt_1", "Muon pt", 8, 0, 120, logy=True, ymargin=1.6, pos="T", ncols=2),
                 m.Variable("m_vis", "m_vis", [0, 20, 40, 60, 80, 100, 120, 160], fname="mvis_varbins")]
    selections = [m.Selection("baseline", "q_1*q_2<0"), m.Selection("highpt", "High pt", "q_1*q_2<0 && pt_1>20")]

    failures = 0
    output = TFile.Open(str(workspace / "hists.root"), "RECREATE")
    for selection in selections:
        # one selection given, so gethists returns {variable: HistSet} (as getstack uses it)
        histsets = samples.gethists(variables, selection, method="QCD_OSSS", nthreads=1)
        for variable in variables:
            histset = histsets[variable]
            label = "%s/%s" % (selection.filename, variable.filename)
            directory = output.mkdir(label.replace("/", "__"))
            names = write_histset(directory, histset)
            pngs = {kind: workspace / ("%s_%s.png" % (label.replace("/", "__"), kind)) for kind in "ABC"}
            snapshots = {"A": draw(histset.getstack(variable, selection), pngs["A"])}  # changes the context
            hists = read_hists(directory, names)
            snapshots["B"] = draw(Stack(variable, *hists), pngs["B"])
            snapshots["C"] = draw(Stack(minimal_variable(variable), *read_hists(directory, names)), pngs["C"])
            for kind in "BC":
                diffs = difference(snapshots["A"], snapshots[kind])
                same_png = pngs["A"].read_bytes() == pngs[kind].read_bytes()
                status = "SAME" if not diffs and same_png else "DIFF"
                failures += status == "DIFF"
                print("%s %s %s (snapshot %s, png %s)" % (status, kind, label, "equal" if not diffs else "differs",
                                                           "equal" if same_png else "differs"))
                for line in diffs:
                    print("     " + line)
    output.Close()
    print("%d difference(s); files in %s" % (failures, workspace))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
