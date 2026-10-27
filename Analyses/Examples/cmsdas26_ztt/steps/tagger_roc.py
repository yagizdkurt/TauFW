"""Step 6 of the CMSDAS26 long exercise: compare the tau taggers with ROC curves.

For each of the three taggers (DeepTau2018v2p5, PNet, UParT) and each of their discriminants (against jets,
electrons and muons), this step draws a ROC curve: how many genuine taus a cut on the raw score keeps (efficiency)
against how many fakes it keeps (fake rate). All three taggers go on one plot per discriminant, and a table gives
the area under each curve (AUC) and the efficiency at a 1% fake rate.

Ported from long-ex Plotter/plots_and_histograms_CMSDAS26.py --tagger (plot_tagger_comparison); the method and the
plots are unchanged (docs/CMSDAS26/tagger_comparison.md of long-ex).

In the recipe:

    - stage: python
      id: tagger_roc
      inputs: null
      file: steps/tagger_roc.py
      options: {era: '2024', channel: mutau, samples: v15_2024.yml, tuples: /eos/.../$ERA/$GROUP,
                base: "q_1*q_2<0 && iso_1<0.15 && mt_1<65", nbins: 100}

  base:   the loose selection, without tau ID cuts
  nbins:  bins of the raw score in [0,1], i.e. the number of cut values that are tried
  tuples: an option, not an input: a python step cannot take {external: ...}, so `plan` does not check them

Outputs, in <run_dir>/stages/<id>/:
  plots/<era>/tagger_ROC_<VSjet|VSe|VSmu>_<channel>_<era>.png and .pdf   the ROC plots (long-ex names)
  roc_summary.txt                                                    AUC and efficiency at 1% fake rate per curve

The file reads from top to bottom:
  1. IMPORTS AND OPTIONS    what the step reads from the framework
  2. PIPELINE               run(ctx): the whole step in a few lines
  3. ANALYSIS FUNCTIONS     histograms, ROC curves, plots
  4. BOILERPLATE            output files and the small math helpers
"""

# =====================================================================================================================
#  1. IMPORTS AND OPTIONS
# =====================================================================================================================
import os
from collections import namedtuple
from types import SimpleNamespace

import ROOT as R
from TauFW.Histogrammer.sample.utils import LOG, Sel, Var
from TauFW.Histogrammer.sample.model import getsampleset, load_sample_model

R.gROOT.SetBatch(True)  # draw to files only, never open a window

# One discriminant family: its name, the raw-score branch of every tagger, which fakes are the background, and the
# title of the x-axis. Signal is always the genuine taus (genmatch_2==5).
Family = namedtuple('Family', ['name', 'taggers', 'background_cut', 'xtitle'])
FAMILIES = [
    Family('VSjet', {'DeepTau2018v2p5': 'rawDeepTau2018v2p5VSjet_2', 'PNet': 'rawPNetVSjet_2', 'UParT': 'rawUParTVSjet_2'},
           "genmatch_2==0", "jet#rightarrow#tau_{h} fake rate"),
    Family('VSe',   {'DeepTau2018v2p5': 'rawDeepTau2018v2p5VSe_2', 'PNet': 'rawPNetVSe_2', 'UParT': 'rawUParTVSe_2'},
           "(genmatch_2==1||genmatch_2==3)", "e#rightarrow#tau_{h} fake rate"),
    Family('VSmu',  {'DeepTau2018v2p5': 'rawDeepTau2018v2p5VSmu_2', 'PNet': 'rawPNetVSmu_2', 'UParT': 'rawUParTVSmu_2'},
           "(genmatch_2==2||genmatch_2==4)", "#mu#rightarrow#tau_{h} fake rate"),
]
TAGGER_COLORS = {'DeepTau2018v2p5': R.kBlack, 'PNet': R.kRed+1, 'UParT': R.kAzure+2}
FAKERATE = 0.01  # the summary table gives the efficiency at this fake rate


def read_options(ctx):
    """The recipe options of this stage, with their defaults."""
    opts = ctx.options
    return SimpleNamespace(
        era      = str(opts['era']),
        channel  = opts.get('channel', 'mutau'),
        samples  = ctx.path(opts['samples']),   # the sample model of the bundle (v15_2024.yml)
        tuples   = opts['tuples'],              # where the pico tuples are
        base     = opts['base'],                # loose selection, no tau ID cuts
        nbins    = int(opts.get('nbins', 100)),
        stagedir = ctx.stage_dir,               # where this stage writes its outputs
    )


# =====================================================================================================================
#  2. PIPELINE
# =====================================================================================================================

def run(ctx):
    """The step: called by the framework with the context of this stage (ctx)."""
    opts = read_options(ctx)
    plotdir = make_directory(opts.stagedir, 'plots', opts.era)

    # All simulated samples, normalized as in the control plots.
    sampleset = load_simulated_samples(opts)

    # Genuine taus: the same signal for every discriminant, so filled once for all nine scores.
    signal = fill_signal_histograms(sampleset, opts)

    # One plot per discriminant family: fill its background, compute one ROC curve per tagger, draw them.
    curves, plots = [], []
    for family in FAMILIES:
        background = fill_background_histograms(sampleset, family, opts)
        family_curves = compute_roc_curves(family, signal, background, opts.nbins, ctx.log)
        plots += draw_roc_plot(family, family_curves, opts, plotdir)
        curves += family_curves

    table = write_summary_table(curves, opts)
    ctx.log("wrote %s" % (table))
    return build_result(curves, plots, table, opts, plotdir)


# =====================================================================================================================
#  3. ANALYSIS FUNCTIONS
# =====================================================================================================================

def load_simulated_samples(opts):
    """The sample set of the control plots (fillhists.py): cross sections, luminosity, MC weights, DY split by
    gen-match."""
    model = load_sample_model(opts.samples)
    return getsampleset(opts.channel, opts.era, model, fname="$PICODIR/$SAMPLE_$CHANNEL$TAG.root", tuples=opts.tuples,
                        split=['DY'], table=True)


def fill_signal_histograms(sampleset, opts):
    """{score branch: TH1} of the genuine taus, for the raw scores of all taggers of all families."""
    branches = [branch for family in FAMILIES for branch in family.taggers.values()]
    return summed_mc_histograms(sampleset, [Var(b, opts.nbins, 0, 1) for b in branches],
                                Sel('sig', opts.base+" && genmatch_2==5"))


def fill_background_histograms(sampleset, family, opts):
    """{score branch: TH1} of the fakes of one family (jets, electrons or muons faking a tau_h)."""
    return summed_mc_histograms(sampleset, [Var(b, opts.nbins, 0, 1) for b in family.taggers.values()],
                                Sel('bkg_'+family.name, opts.base+" && "+family.background_cut))


def compute_roc_curves(family, signal, background, nbins, log):
    """One ROC curve per tagger of the family, as a dict: tagger, fake and eff (one point per cut value), the total
    signal and background, the AUC and the efficiency at FAKERATE. A tagger without histograms, or with fewer than
    two points to draw, is left out."""
    curves = []
    for tagger, branch in family.taggers.items():
        hsig, hbkg = signal.get(branch), background.get(branch)
        if hsig is None or hbkg is None:
            LOG.warning("%s/%s: missing hist, skip" % (family.name, tagger)); continue
        fake, eff, stot, btot = roc_points(hsig, hbkg, nbins)
        if len(drawable_points(fake, eff)) < 2:
            continue
        auc = abs(trapezoid(eff, fake))
        curves.append({'family': family.name, 'tagger': tagger, 'fake': fake, 'eff': eff, 'signal': stot,
                       'background': btot, 'auc': auc, 'eff_at_fakerate': efficiency_at(fake, eff, FAKERATE)})
        log("%-6s %-16s sig=%.0f bkg=%.0f AUC~%.3f" % (family.name, tagger, stot, btot, auc))
    return curves


def roc_points(hsig, hbkg, nbins):
    """The ROC curve from the score histograms: for every cut value i (bin i of [0,1]), the events in bins
    i..nbins+1 pass (overflow included). eff[i] = signal passing / all signal, fake[i] = background passing / all
    background. A score of -1 (no score) is in the underflow (bin 0) and left out of both.
    Returns (fake, eff, total signal, total background)."""
    stot = hsig.Integral(1, nbins+1); btot = hbkg.Integral(1, nbins+1)
    eff  = [hsig.Integral(i, nbins+1)/stot if stot > 0 else 0 for i in range(1, nbins+1)]
    fake = [hbkg.Integral(i, nbins+1)/btot if btot > 0 else 0 for i in range(1, nbins+1)]
    return fake, eff, stot, btot


def draw_roc_plot(family, curves, opts, plotdir):
    """All curves of one family on one canvas, saved as png and pdf; returns the saved files."""
    # Empty frame: fake rate on a log x-axis (from 1e-3), efficiency on a linear y-axis.
    canvas = R.TCanvas('roc_'+family.name, 'roc', 700, 650); canvas.SetLogx(); canvas.SetGrid()
    frame = canvas.DrawFrame(1e-3, 0.0, 1.0, 1.05)
    frame.SetTitle("%s ROC (%s);%s;genuine #tau_{h} efficiency" % (family.name, opts.channel, family.xtitle))
    legend = R.TLegend(0.16, 0.72, 0.52, 0.90)
    graphs = []  # keep the graphs alive until the canvas is saved (ROOT does not own them)
    for curve in curves:
        graph = roc_graph(curve['fake'], curve['eff'])
        graph.SetLineColor(TAGGER_COLORS[curve['tagger']]); graph.SetLineWidth(2); graph.Draw('L SAME')
        legend.AddEntry(graph, curve['tagger'], 'l'); graphs.append(graph)
    legend.Draw()

    files = []
    fname = os.path.join(plotdir, "tagger_ROC_%s_%s_%s" % (family.name, opts.channel, opts.era))
    for ext in ('png', 'pdf'):
        canvas.SaveAs(fname+"."+ext)
        files.append(fname+"."+ext)
    canvas.Close()
    return files


def roc_graph(fake, eff):
    """A TGraph of efficiency against fake rate, from the points a log x-axis can show."""
    points = drawable_points(fake, eff)
    graph = R.TGraph(len(points))
    for i, (f, e) in enumerate(points):
        graph.SetPoint(i, f, e)
    return graph


# =====================================================================================================================
#  4. BOILERPLATE
# =====================================================================================================================

def write_summary_table(curves, opts):
    """roc_summary.txt: one line per curve with the signal and background yields, the AUC and the efficiency at
    FAKERATE ('-' when the curve does not reach it). Returns its path."""
    table = os.path.join(opts.stagedir, 'roc_summary.txt')
    with open(table, 'w') as stream:
        stream.write("# %s %s, base selection: %s\n" % (opts.channel, opts.era, opts.base))
        stream.write("%-6s %-16s %12s %12s %7s  %s\n" % ("disc", "tagger", "signal", "background", "AUC",
                                                       "eff at %g%% fake rate" % (100*FAKERATE)))
        for c in curves:
            eff = c['eff_at_fakerate']
            stream.write("%-6s %-16s %12.1f %12.1f %7.3f  %s\n" % (c['family'], c['tagger'], c['signal'],
                                                                 c['background'], c['auc'],
                                                                 "-" if eff is None else "%.3f" % eff))
    return table


def build_result(curves, plots, table, opts, plotdir):
    """What the step returns to the framework: a short message and its outputs (artifacts)."""
    return {'message': "%d ROC curve(s) in %d plot(s)" % (len(curves), len(FAMILIES)),
            'artifacts': [{'kind': 'plots', 'era': opts.era, 'channel': opts.channel, 'directory': plotdir,
                           'files': plots},
                          {'kind': 'table', 'path': table, 'nrows': len(curves)}]}


def make_directory(*parts):
    """os.path.join(*parts), created if needed."""
    path = os.path.join(*parts)
    os.makedirs(path, exist_ok=True)
    return path


def summed_mc_histograms(sampleset, variables, sel):
    """{variable name: TH1 of all simulated samples summed} under the selection sel, in one event loop for all
    variables. Data is left out (so a genmatch_2 cut is safe)."""
    res = sampleset.getstack(variables, sel, method=None, data=False, parallel=True)
    # getstack returns a dict {stack: (var, sel)} for several variables, a single stack for one variable.
    items = res.items() if isinstance(res, dict) else [(res, (variables[0], sel))]
    out = {}
    for stack, key in items:
        var = key[0] if isinstance(key, tuple) else key
        total = None
        for hist in stack.hists:
            if 'data' in hist.GetName().lower():
                continue
            copy = hist.Clone(hist.GetName()+"_c"); copy.SetDirectory(0)
            if total is None: total = copy
            else: total.Add(copy)
        out[var.name] = total
    return out


def drawable_points(fake, eff):
    """The (fake rate, efficiency) points with a fake rate above 0: a log x-axis cannot show 0."""
    return [(f, e) for f, e in zip(fake, eff) if f > 0]


def trapezoid(y, x):
    """The trapezoid integral of y over x (numpy.trapz in long-ex). Used for the AUC."""
    return sum((x[i+1]-x[i])*(y[i+1]+y[i])/2. for i in range(len(x)-1))


def efficiency_at(fake, eff, rate):
    """The efficiency at a given fake rate, interpolated linearly between the two cut values around it; None if the
    curve does not reach it. The fake rate decreases with the cut value."""
    for i in range(len(fake)-1):
        if fake[i] >= rate >= fake[i+1]:
            if fake[i] == fake[i+1]:
                return eff[i]
            return eff[i] + (eff[i+1]-eff[i])*(rate-fake[i])/(fake[i+1]-fake[i])
    return None
