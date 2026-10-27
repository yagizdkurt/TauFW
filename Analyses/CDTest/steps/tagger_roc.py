"""Python step of the CDTest analysis: step 6 of the CMSDAS26 long exercise, the tagger comparison
(docs/CMSDAS26/tagger_comparison.md of long-ex). The ROC curves of DeepTau2018v2p5, PNet and UParT against jets,
electrons and muons, as long-ex Plotter/plots_and_histograms_CMSDAS26.py --tagger makes them (plot_tagger_comparison,
ported unchanged apart from the imports and the sample set of this bundle).

Recipe (recipe.yml):

    - stage: python
      id: tagger_roc
      inputs: null
      file: steps/tagger_roc.py
      options: {era: '2024', channel: mutau, samples: v15_2024.yml, tuples: /eos/.../$ERA/$GROUP,
                base: "q_1*q_2<0 && iso_1<0.15 && mt_1<65", nbins: 100}

The tuples are an option, not an input: a python step cannot take {external: ...} (only tuples inputs can), so
`plan` does not check that they exist.

Method: all simulated samples (the sample set of fillhists.py: cross section, luminosity, MC weights, DY split by
gen-match), in the loose selection `base` without tau ID cuts. Signal: genuine tau_h (genmatch_2==5). Background,
one per discriminant: jet (genmatch_2==0) for VSjet, electron (1 or 3) for VSe, muon (2 or 4) for VSmu. For a
threshold on the raw score in [0,1]: efficiency = signal above / all signal, fake rate = background above / all
background. A score of -1 (no score) is in the underflow and left out, per tagger.

Outputs: <run_dir>/stages/<id>/plots/<era>/tagger_ROC_<VSjet|VSe|VSmu>_<channel>_<era>.png and .pdf (the long-ex
names), and roc_summary.txt: the AUC of every curve (printed by long-ex) and the efficiency at a fake rate of 1%
(a task of the exercise, read off the curve there). One 'plots' and one 'table' artifact.

How to read this file:

    1. CONFIGURATION  the three discriminant families and the fixed fake rate of the summary table.
    2. PIPELINE       run(ctx): the whole step from top to bottom, one numbered block per stage.
    3. PLOTTING       one ROC canvas per family (_plot_family) and one curve per tagger (_make_roc_graph).
    4. OUTPUT         the summary table and the result dictionary returned to the framework.
    5. ROC MATH       the histogram sums and the plain-python math behind a ROC curve.
"""
import os


# =====================================================================================================================
#  1. CONFIGURATION
# =====================================================================================================================

# One entry per discriminant family, as in long-ex:
#   (discriminant, {tagger: raw-score branch}, background selection, x-axis title)
FAMILIES = [
    ('VSjet', {'DeepTau2018v2p5': 'rawDeepTau2018v2p5VSjet_2', 'PNet': 'rawPNetVSjet_2', 'UParT': 'rawUParTVSjet_2'},
     "genmatch_2==0", "jet#rightarrow#tau_{h} fake rate"),
    ('VSe',   {'DeepTau2018v2p5': 'rawDeepTau2018v2p5VSe_2', 'PNet': 'rawPNetVSe_2', 'UParT': 'rawUParTVSe_2'},
     "(genmatch_2==1||genmatch_2==3)", "e#rightarrow#tau_{h} fake rate"),
    ('VSmu',  {'DeepTau2018v2p5': 'rawDeepTau2018v2p5VSmu_2', 'PNet': 'rawPNetVSmu_2', 'UParT': 'rawUParTVSmu_2'},
     "(genmatch_2==2||genmatch_2==4)", "#mu#rightarrow#tau_{h} fake rate"),
]
FAKERATE = 0.01  # the fixed fake rate of the summary table


# =====================================================================================================================
#  2. PIPELINE
# =====================================================================================================================

def run(ctx):
    """The ROC curves of the three taggers for VSjet, VSe and VSmu, and their summary table.

    Entry point called by the framework. ctx gives the recipe options (ctx.options), the stage directory
    (ctx.stage_dir), paths relative to the analysis (ctx.path) and a logger (ctx.log).
    """
    import ROOT as R
    from TauFW.Histogrammer.sample.utils import LOG, Sel, Var
    from TauFW.Histogrammer.sample.model import getsampleset, load_sample_model
    R.gROOT.SetBatch(True)  # no windows: draw to files only

    # --- Step 1: read the recipe options ------------------------------------------------------------------------------
    opts    = ctx.options
    era     = str(opts['era'])
    channel = opts.get('channel', 'mutau')
    base    = opts['base']                  # loose selection, no tau ID cuts
    nbins   = int(opts.get('nbins', 100))   # bins of the raw score in [0,1] = number of thresholds scanned

    # --- Step 2: build the simulated sample set (same as fillhists.py) ------------------------------------------------
    model   = load_sample_model(ctx.path(opts['samples']))
    sampleset = getsampleset(channel, era, model, fname="$PICODIR/$SAMPLE_$CHANNEL$TAG.root", tuples=opts['tuples'],
                             split=['DY'], table=True)  # as fillhists.py builds it

    # --- Step 3: prepare the output directory and the tagger colors ---------------------------------------------------
    outdir = os.path.join(ctx.stage_dir, 'plots', era)
    os.makedirs(outdir, exist_ok=True)
    colors = {'DeepTau2018v2p5': R.kBlack, 'PNet': R.kRed+1, 'UParT': R.kAzure+2}

    # --- Step 4: fill the signal histograms (genuine taus) ------------------------------------------------------------
    # All nine discriminants in one event loop; the signal is the same for every family.
    branches = [branch for _, taggers, _, _ in FAMILIES for branch in taggers.values()]
    sig = _summed_mc(sampleset, [Var(b, nbins, 0, 1) for b in branches], Sel('sig', base+" && genmatch_2==5"))

    # --- Step 5: one ROC plot per family (fills its own background histograms) ----------------------------------------
    rows, files = [], []  # rows: one summary-table row per drawn curve; files: every saved plot
    for fam, taggers, bkgsel, xtitle in FAMILIES:
        fam_rows, fam_files = _plot_family(ctx, sampleset, sig, fam, taggers, bkgsel, xtitle,
                                           base=base, channel=channel, era=era, nbins=nbins,
                                           outdir=outdir, colors=colors)
        rows.extend(fam_rows)
        files.extend(fam_files)

    # --- Step 6: write the summary table ------------------------------------------------------------------------------
    table = os.path.join(ctx.stage_dir, 'roc_summary.txt')
    _write_summary(table, rows, channel=channel, era=era, base=base)
    ctx.log("wrote %s" % (table))

    # --- Step 7: report the outputs to the framework ------------------------------------------------------------------
    return _build_result(rows, files, table, era=era, channel=channel, outdir=outdir)


# =====================================================================================================================
#  3. PLOTTING
# =====================================================================================================================

def _plot_family(ctx, sampleset, sig, fam, taggers, bkgsel, xtitle, base, channel, era, nbins, outdir, colors):
    """Draw the ROC curves of all taggers of one discriminant family on one canvas and save it as png and pdf.

    sig is the {branch: signal TH1} of step 4; the background histograms of this family are filled here.
    Returns (rows, files): one summary-table row (fam, tagger, signal, background, AUC, eff at FAKERATE) per drawn
    curve, and the paths of the saved plots.
    """
    import ROOT as R
    from TauFW.Histogrammer.sample.utils import LOG, Sel, Var

    # Background histograms of this family (jets, electrons or muons faking a tau_h).
    bkg = _summed_mc(sampleset, [Var(b, nbins, 0, 1) for b in taggers.values()], Sel('bkg_'+fam, base+" && "+bkgsel))

    # Empty canvas: fake rate on a log x-axis (floored at 1e-3), efficiency on a linear y-axis.
    canvas = R.TCanvas('roc_'+fam, 'roc', 700, 650); canvas.SetLogx(); canvas.SetGrid()
    frame = canvas.DrawFrame(1e-3, 0.0, 1.0, 1.05)
    frame.SetTitle("%s ROC (%s);%s;genuine #tau_{h} efficiency" % (fam, channel, xtitle))
    legend = R.TLegend(0.16, 0.72, 0.52, 0.90)
    graphs = []  # keep the graphs alive until the canvas is saved (ROOT does not own them)

    # One curve per tagger.
    rows = []
    for name, branch in taggers.items():
        hsig, hbkg = sig.get(branch), bkg.get(branch)
        if hsig is None or hbkg is None:
            LOG.warning("%s/%s: missing hist, skip" % (fam, name)); continue
        fake, eff, stot, btot = _roc_arrays(hsig, hbkg, nbins)
        graph = _make_roc_graph(fake, eff)
        if graph is None:  # fewer than two points to draw
            continue
        graph.SetLineColor(colors[name]); graph.SetLineWidth(2); graph.Draw('L SAME')
        legend.AddEntry(graph, name, 'l'); graphs.append(graph)
        auc = abs(_trapezoid(eff, fake))
        rows.append((fam, name, stot, btot, auc, _eff_at(fake, eff, FAKERATE)))
        ctx.log("%-6s %-16s sig=%.0f bkg=%.0f AUC~%.3f" % (fam, name, stot, btot, auc))
    legend.Draw()

    # Save the canvas.
    files = []
    fname = os.path.join(outdir, "tagger_ROC_%s_%s_%s" % (fam, channel, era))
    for ext in ('png', 'pdf'):
        canvas.SaveAs(fname+"."+ext)
        files.append(fname+"."+ext)
    canvas.Close()
    return rows, files


def _make_roc_graph(fake, eff):
    """A TGraph of efficiency vs fake rate, keeping only the points with fake rate > 0 (a log x-axis cannot show 0).
    None if fewer than two points are left."""
    import ROOT as R
    points = [(f, e) for f, e in zip(fake, eff) if f > 0]  # log-x needs fake>0
    if len(points) < 2:
        return None
    graph = R.TGraph(len(points))
    for i, (f, e) in enumerate(points):
        graph.SetPoint(i, f, e)
    return graph


# =====================================================================================================================
#  4. OUTPUT
# =====================================================================================================================

def _write_summary(table, rows, channel, era, base):
    """Write the summary table: one line per curve with signal and background yields, AUC and the efficiency at
    FAKERATE ('-' when the curve does not reach it)."""
    with open(table, 'w') as stream:
        stream.write("# %s %s, base selection: %s\n" % (channel, era, base))
        stream.write("%-6s %-16s %12s %12s %7s  %s\n" % ("disc", "tagger", "signal", "background", "AUC",
                                                       "eff at %g%% fake rate" % (100*FAKERATE)))
        for fam, name, stot, btot, auc, eff in rows:
            stream.write("%-6s %-16s %12.1f %12.1f %7.3f  %s\n" % (fam, name, stot, btot, auc,
                                                                 "-" if eff is None else "%.3f" % eff))


def _build_result(rows, files, table, era, channel, outdir):
    """The result dictionary of the step: a short message and the two artifacts (plots and table)."""
    return {'message': "%d ROC curve(s) in %d plot(s)" % (len(rows), len(FAMILIES)),
            'artifacts': [{'kind': 'plots', 'era': era, 'channel': channel, 'directory': outdir, 'files': files},
                          {'kind': 'table', 'path': table, 'nrows': len(rows)}]}


# =====================================================================================================================
#  5. ROC MATH
# =====================================================================================================================

def _summed_mc(sampleset, variables, sel):
    """{Var.name: total-MC TH1} for every variable under selection sel (no data, so a genmatch_2 cut is safe); one
    event loop for all variables."""
    res = sampleset.getstack(variables, sel, method=None, data=False, parallel=True)
    # getstack returns a dict {stack: (var, sel)} for several variables, a single stack for one variable.
    items = res.items() if isinstance(res, dict) else [(res, (variables[0], sel))]
    out = {}
    for stack, key in items:
        var = key[0] if isinstance(key, tuple) else key
        # Sum all simulated histograms of the stack into one total.
        total = None
        for hist in stack.hists:
            if 'data' in hist.GetName().lower():
                continue
            copy = hist.Clone(hist.GetName()+"_c"); copy.SetDirectory(0)
            if total is None: total = copy
            else: total.Add(copy)
        out[var.name] = total
    return out


def _roc_arrays(hsig, hbkg, nbins):
    """Cumulative (fake rate, efficiency) scanning the raw score over the in-range [0,1] bins. The -1 'no-score'
    default lands in the underflow (bin 0) and is excluded from both.

    Threshold i keeps the events in bins i..nbins+1 (overflow included): eff[i] = signal kept / all signal,
    fake[i] = background kept / all background. Also returns the totals stot and btot.
    """
    stot = hsig.Integral(1, nbins+1); btot = hbkg.Integral(1, nbins+1)
    eff  = [hsig.Integral(i, nbins+1)/stot if stot > 0 else 0 for i in range(1, nbins+1)]
    fake = [hbkg.Integral(i, nbins+1)/btot if btot > 0 else 0 for i in range(1, nbins+1)]
    return fake, eff, stot, btot


def _trapezoid(y, x):
    """The trapezoid integral of y over x (numpy.trapz of long-ex, without numpy). Used for the AUC."""
    return sum((x[i+1]-x[i])*(y[i+1]+y[i])/2. for i in range(len(x)-1))


def _eff_at(fake, eff, rate):
    """The efficiency at a fake rate, interpolated linearly between the two thresholds around it; None if the curve
    does not reach it. fake decreases with the threshold."""
    for i in range(len(fake)-1):
        if fake[i] >= rate >= fake[i+1]:
            if fake[i] == fake[i+1]:
                return eff[i]
            return eff[i] + (eff[i+1]-eff[i])*(rate-fake[i])/(fake[i+1]-fake[i])
    return None
