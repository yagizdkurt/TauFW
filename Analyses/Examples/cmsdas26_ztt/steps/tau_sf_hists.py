"""Step 7 (Tier A) of the CMSDAS26 long exercise: apply the measured tau corrections and fill the histograms.

The tau ID scale factor (SF) and the tau energy scale (TES) were measured per decay mode (DM) and tau pT. This step
applies them to the simulation, fills the data/MC histograms of every variable, writes them to a ROOT file (the
input of the datacards, step 8) and draws the control plots. The same step makes all histogram stages of the
recipe; only the options differ:

  tauid_sf: true    the tau ID SF as an event weight, for genuine taus only        (long-ex --tauid-sf)
  apply_tes: true   Z->tautau taken from the TES-shifted copies of the tuples       (long-ex --apply-tes)
  syst: up / down   the SF and TES shifted by their uncertainty                     (long-ex --syst)

An energy scale cannot be a weight: the tuples come in TES-shifted copies (<sample>_<channel>_TES0p998.root, ...).
For each decay mode, Z->tautau is read from the copy closest to the measured TES (grid step 0.002), and the four
decay modes are summed.

Ported from the plot path of long-ex Plotter/plots_and_histograms_CMSDAS26.py and Plotter/cmsdas_config.py
(docs/CMSDAS26/tauid_es.md of long-ex); the selection comes from a channel setup of this bundle.

In the recipe:

    - stage: python
      id: sf_tauid_tes
      inputs: null
      file: steps/tau_sf_hists.py
      options: {era: '2024', channel: mutau, setup: setup_mutau.yml, samples: v15_2024.yml,
                tuples: /eos/.../$ERA/$GROUP, variables: [{name: m_vis, nbins: 40, min: 0, max: 200}],
                qcd: {method: QCD_OSSS, scale: 1.1}, sf: {json: sf/..., vsjet: Tight, vse: VVLoose, vsmu: Tight},
                tauid_sf: true, apply_tes: true, syst: nom}

  setup:  one selection per region of the setup, named after it: baselineCuts && definition
  qcd:    QCD from the same-sign region, scaled to opposite sign (mutau); method null for none (mumu)

Outputs, in <run_dir>/stages/<id>/:
  hists/<era>/<channel>.root        one directory per selection, histograms <variable>_<process> (e.g. m_vis_ZTT):
                                    the format of long-ex hists/<era>/<channel>.root
  plots/<era>/<variable>_<channel>-<selection>-<era>.png and .pdf

The file reads from top to bottom:
  1. IMPORTS AND OPTIONS    what the step reads from the framework
  2. PIPELINE               run(ctx): the whole step in a few lines
  3. ANALYSIS FUNCTIONS     selection, tau corrections, histograms and plots
  4. BOILERPLATE            reading the SF file, output files
"""

# =====================================================================================================================
#  1. IMPORTS AND OPTIONS
# =====================================================================================================================
import bisect
import json
import os
import re
from types import SimpleNamespace

import yaml
import ROOT as R
from TauFW.Histogrammer.sample.utils import LOG, Sel, Var, setera
from TauFW.Histogrammer.sample.model import getsampleset, load_sample_model

R.gROOT.SetBatch(True)  # draw to files only, never open a window

DMS = (0, 1, 10, 11)  # the decay modes with scale factors

# DeepTau working points as integers, as stored in the id*_2 branches (long-ex cmsdas_config.py)
WP_INT = {'vsjet': {'VVLoose': 2, 'VLoose': 3, 'Loose': 4, 'Medium': 5, 'Tight': 6, 'VTight': 7},
          'vse':   {'VVLoose': 2, 'VLoose': 3, 'Loose': 4, 'Medium': 5, 'Tight': 6, 'VTight': 7},
          'vsmu':  {'VLoose': 1, 'Loose': 2, 'Medium': 3, 'Tight': 4}}
WP_BRANCH = {'vsjet': 'idDeepTau2018v2p5VSjet_2', 'vse': 'idDeepTau2018v2p5VSe_2', 'vsmu': 'idDeepTau2018v2p5VSmu_2'}

# The defaults of the sf option (long-ex cmsdas_config.py DEFAULTS)
SF_DEFAULTS = {'vsjet': 'Tight', 'vse': 'VVLoose', 'vsmu': 'Tight', 'tauid_correction': 'TauIdSF_2024_corrTES',
               'tes_correction': 'TauES_2024_corrTES', 'tes_step': 0.002}


def read_options(ctx):
    """The recipe options of this stage, with their defaults."""
    opts = ctx.options
    qcd  = opts.get('qcd') or {}
    return SimpleNamespace(
        era        = str(opts['era']),
        channel    = opts['channel'],
        tauid_sf   = bool(opts.get('tauid_sf', False)),
        apply_tes  = bool(opts.get('apply_tes', False)),
        syst       = opts.get('syst', 'nom'),                   # nom, up or down
        qcd_method = qcd.get('method'),                         # 'QCD_OSSS', or None for no QCD
        qcd_scale  = qcd.get('scale') or 1.1,                   # the OS/SS scale
        sf         = dict(SF_DEFAULTS, **(opts.get('sf') or {})),
        selections = selections_from_setup(ctx.path(opts['setup'])),
        variables  = [variable_from_option(var) for var in opts['variables']],
        samples    = ctx.path(opts['samples']),                 # the sample model of the bundle (v15_2024.yml)
        tuples     = opts['tuples'],                            # where the pico tuples are
        path       = ctx.path,                                  # a file of the bundle, e.g. the SF file
        stagedir   = ctx.stage_dir,                             # where this stage writes its outputs
    )


# =====================================================================================================================
#  2. PIPELINE
# =====================================================================================================================

def run(ctx):
    """The step: called by the framework with the context of this stage (ctx)."""
    opts = read_options(ctx)

    # The measured tau corrections: an SF weight expression and the TES-shifted samples per decay mode.
    sf_weights, tes_samples = prepare_tau_corrections(opts, ctx.log)

    # All samples (data and simulation), with the SF weight on top of the MC weights.
    sampleset = load_samples(opts, sf_weights)

    # Fill, write and draw the histograms of every selection and variable.
    histfile = os.path.join(make_directory(opts.stagedir, 'hists', opts.era), "%s.root" % (opts.channel))
    plotdir  = make_directory(opts.stagedir, 'plots', opts.era)
    plots = fill_write_and_draw(sampleset, opts, tes_samples, histfile, plotdir)

    ctx.log("wrote %s and %d plot(s)" % (histfile, len(plots)))
    return build_result(opts, histfile, plotdir, plots)


# =====================================================================================================================
#  3. ANALYSIS FUNCTIONS
# =====================================================================================================================

def selections_from_setup(setupfile):
    """One selection per region of a channel setup (fillhists.py format), named after the region, as the
    selections of long-ex cmsdas_<channel>.yml: baselineCuts && definition."""
    with open(setupfile) as stream:
        setup = yaml.safe_load(stream)
    return [Sel(name, "%s && %s" % (setup['baselineCuts'], region['definition']))
            for name, region in (setup.get('regions') or {}).items()]


def variable_from_option(var):
    """A Var from an entry of the 'variables' option (long-ex cmsdas_config.py build_variables): name, optional
    title, and nbins/min/max or bins; fname (the histogram name) and the drawing options passed on."""
    args = [var['name']]
    if var.get('title'):
        args.append(var['title'])
    if 'bins' in var:
        args.append(list(var['bins']))  # variable-width bins
    else:
        args += [var['nbins'], var['min'], var['max']]
    return Var(*args, **{k: var[k] for k in ('fname', 'cut', 'weight', 'logx', 'logy', 'ymin', 'ymax') if k in var})


def prepare_tau_corrections(opts, log):
    """([SF weight expression] or [], {DM: TES sample tag} or None), as the options ask. The working points of the
    SF file are checked against the selection first."""
    sf_weights, tes_samples = [], None
    if opts.tauid_sf or opts.apply_tes:
        sfjson = opts.path(opts.sf['json'])
        check_sf_working_points(opts.selections, opts.sf)
        if opts.tauid_sf:
            sf_weights.append(tauid_sf_weight(sfjson, opts.sf, opts.syst, log))
        if opts.apply_tes:
            tes_samples = tes_sample_tags(sfjson, opts.sf, opts.syst, log)
    return sf_weights, tes_samples


def check_sf_working_points(selections, sf):
    """Stop if a scale-factor working point (vsjet, vse, vsmu) differs from the DeepTau cut of a selection: the
    scale factors are measured per working point, so the two must agree. A leg without a DeepTau cut (e.g. PNet
    against jets in the hybrid selection) is not checked, as in long-ex."""
    for sel in selections:
        for disc in ('vsjet', 'vse', 'vsmu'):
            wp = sf[disc]
            match = re.search(re.escape(WP_BRANCH[disc]) + r"\s*>=\s*(\d+)", sel.selection)
            if not match or wp not in WP_INT[disc]:
                continue  # no such cut in this selection, or a working point without integer code
            if int(match.group(1)) != WP_INT[disc][wp]:
                raise ValueError("selection %s cuts on %s>=%s, but the scale factors are read for %s=%s (>=%d): "
                                 "make the cut and sf.%s agree" % (sel.filename, WP_BRANCH[disc], match.group(1),
                                                                  disc, wp, WP_INT[disc][wp], disc))


def tauid_sf_weight(jsonfile, sf, syst, log):
    """The tau ID SF as a weight expression per decay mode and pT bin, for genuine taus (genmatch_2==5); 1 for the
    others. For example: (genmatch_2!=5?1.0:dm_2==0?(pt_2<40?1.0222:...):...)."""
    data = read_correction(jsonfile, sf['tauid_correction'])
    edges = find_pt_edges(data) or [0.0, 1e4]
    def value(dm, pt):
        return evaluate_correction(data, {"genmatch": 5, "DM": dm, "pT": pt, "syst": syst,
                                          "wp_VSmu": sf['vsmu'], "wp_VSe": sf['vse'], "wp_VSjet": sf['vsjet']})
    middles = [0.5*(edges[i]+edges[i+1]) for i in range(len(edges)-1)]
    dmexpr = {}
    for dm in DMS:
        values = [value(dm, m) for m in middles]
        expr = "".join("pt_2<%g?%.4f:" % (edges[i+1], values[i]) for i in range(len(values)-1))
        dmexpr[dm] = "(" + expr + "%.4f)" % values[-1]
    expr = ("(genmatch_2!=5?1.0:dm_2==0?%s:dm_2==1?%s:dm_2==10?%s:dm_2==11?%s:1.0)"
            % (dmexpr[0], dmexpr[1], dmexpr[10], dmexpr[11]))
    log("TauID SF weight (VSjet=%s,VSe=%s,VSmu=%s,%s): %s" % (sf['vsjet'], sf['vse'], sf['vsmu'], syst, expr))
    return expr


def tes_sample_tags(jsonfile, sf, syst, log):
    """{DM: '_TESXpXXX'}: the measured TES of each decay mode, rounded to the grid of the shifted tuples (step
    tes_step), as the tag of their file names; e.g. 0.9976 -> _TES0p998. The TES does not depend on pT, so it is
    read once per DM (at 40 GeV)."""
    data = read_correction(jsonfile, sf['tes_correction'])
    step, out = sf['tes_step'], {}
    for dm in DMS:
        tes = evaluate_correction(data, {"genmatch": 5, "DM": dm, "pT": 40.0, "syst": syst,
                                         "wp_VSmu": sf['vsmu'], "wp_VSe": sf['vse'], "wp_VSjet": sf['vsjet']})
        grid = round(tes/step)*step
        out[dm] = ("_TES%.3f" % grid).replace(".", "p")
        log("TES DM%d (%s): %.4f -> %s" % (dm, syst, tes, out[dm]))
    log("per-DM TES samples: %s" % out)
    return out


def load_samples(opts, sf_weights):
    """The sample set of the control plots (fillhists.py), with the SF weights added to the simulation. Drell-Yan is
    split by gen-match (ZTT, ZL, ZJ) when there is a hadronic tau."""
    setera(opts.era)
    split = ['DY'] if 'tau' in opts.channel else []
    return getsampleset(opts.channel, opts.era, load_sample_model(opts.samples),
                        fname="$PICODIR/$SAMPLE_$CHANNEL$TAG.root", tuples=opts.tuples,
                        addsf=sf_weights, split=split, table=True)


def fill_write_and_draw(sampleset, opts, tes_samples, histfile, plotdir):
    """For every selection: fill the data/MC stacks of all variables (with QCD from the same-sign region if
    qcd_method is set), take Z->tautau from the TES-shifted samples if tes_samples is given, write the histograms
    to histfile and draw the plots. Returns the plot files."""
    outfile = R.TFile.Open('file:' + histfile, 'recreate')
    exts  = ['png', 'pdf']
    files = []
    for selection in opts.selections:
        outfile.mkdir(selection.filename)
        stacks = sampleset.getstack(opts.variables, selection, method=opts.qcd_method, scale=opts.qcd_scale,
                                    parallel=True)
        if tes_samples and 'tau' in opts.channel:
            replace_ztt_with_tes_shifted(sampleset, stacks, opts.variables, selection, tes_samples)
        fname = "%s/$VAR_%s-%s-%s" % (plotdir, opts.channel, selection.filename, opts.era)
        text  = "%s: %s" % (opts.channel.replace('mu', "#mu").replace('tau', "#tau_{h}"), selection.title)
        for stack, variable in stacks.items():
            write_histograms(outfile, selection, stack)
            stack.draw()
            stack.drawlegend(x1=0.6, x2=0.95, y1=0.35, y2=0.95)
            stack.drawtext(text)
            stack.saveas(fname, ext=exts)
            files += ["%s/%s_%s-%s-%s.%s" % (plotdir, variable[0].filename, opts.channel, selection.filename,
                                             opts.era, ext) for ext in exts]
            stack.close()
    outfile.Close()
    return files


def replace_ztt_with_tes_shifted(sampleset, stacks, variables, selection, tes_samples):
    """Replace the ZTT histograms of the stacks by TES-shifted ones: for each DM, read ZTT from the shifted copy of
    that DM (sampleset.shift) with dm_2==DM, then sum over the DMs."""
    ztt_sum = {}  # variable name -> TH1, summed over the DMs
    for dm, tag in tes_samples.items():
        LOG.info(">>> TES swap: DM%-2d -> ZTT read from *%s*.root samples" % (dm, tag))
        shifted = sampleset.shift(['ZTT'], tag, tag, split=True, filter=False, share=True)
        sel_dm = Sel(selection.filename + '_dm%d' % dm, selection.selection + " && dm_2==%d" % dm)
        res = shifted.getstack(variables, sel_dm, method=None, data=False, parallel=True)
        # getstack returns a dict {stack: (var, sel)} for several variables, a single stack for one variable.
        items = res.items() if isinstance(res, dict) else [(res, (variables[0], sel_dm))]
        for stack, key in items:
            var = key[0] if isinstance(key, tuple) else key
            for hist in stack.hists:
                if '_ZTT' in hist.GetName():  # the shifted names are like m_vis_ZTT_TES0p996
                    copy = hist.Clone(hist.GetName() + "_tes%d" % dm); copy.SetDirectory(0)
                    if var.name in ztt_sum: ztt_sum[var.name].Add(copy)
                    else: ztt_sum[var.name] = copy
                    break
    for stack, key in stacks.items():
        var = key[0] if isinstance(key, tuple) else key
        if var.name not in ztt_sum: continue
        for hist in stack.hists:
            if hist.GetName().endswith('_ZTT'):
                hist.Reset(); hist.Add(ztt_sum[var.name]); break


# =====================================================================================================================
#  4. BOILERPLATE
# =====================================================================================================================

def write_histograms(outfile, selection, stack):
    """Write the histograms of one stack into the directory of its selection. The data-driven QCD is renamed from
    <var>_QCD_... to <var>_QCD..., as long-ex names it."""
    outfile.cd(selection.filename)
    for hist in stack.hists:
        hist.Write(hist.GetName().replace("QCD_", "QCD"), R.TH1.kOverwrite)


def build_result(opts, histfile, plotdir, plots):
    """What the step returns to the framework: a short message and its outputs (artifacts)."""
    what = ", ".join(name for name, on in (('tau ID SF', opts.tauid_sf), ('TES', opts.apply_tes)) if on)
    what = what or "no tau corrections"
    return {'message': "%s %s: %s%s" % (opts.channel, opts.era, what, "" if opts.syst == 'nom' else " (%s)" % opts.syst),
            'artifacts': [{'kind': 'histograms', 'era': opts.era, 'channel': opts.channel, 'file': histfile,
                           'selections': [sel.filename for sel in opts.selections], 'tauid_sf': opts.tauid_sf,
                           'apply_tes': opts.apply_tes, 'syst': opts.syst},
                          {'kind': 'plots', 'era': opts.era, 'channel': opts.channel, 'directory': plotdir,
                           'files': plots}]}


def make_directory(*parts):
    """os.path.join(*parts), created if needed."""
    path = os.path.join(*parts)
    os.makedirs(path, exist_ok=True)
    return path


def read_correction(jsonfile, name):
    """The data of the correction `name` in a correctionlib JSON file."""
    with open(jsonfile) as stream:
        corrections = json.load(stream)["corrections"]
    found = [c for c in corrections if c["name"] == name]
    if not found:
        raise KeyError("%s has no correction %r (has: %s)" % (jsonfile, name, ", ".join(c["name"] for c in corrections)))
    return found[0]["data"]


def evaluate_correction(node, inputs):
    """The value of a correctionlib node (category, binning or a number) for the given inputs. A small evaluator in
    plain python, so the step does not need the compiled correctionlib."""
    if isinstance(node, (int, float)):
        return float(node)
    nodetype = node.get("nodetype")
    if nodetype == "category":
        key = inputs[node["input"]]
        for item in node["content"]:
            if item["key"] == key:
                return evaluate_correction(item["value"], inputs)
        if node.get("default") is not None:
            return evaluate_correction(node["default"], inputs)
        raise KeyError("%s=%r" % (node["input"], key))
    if nodetype == "binning":
        x, edges = inputs[node["input"]], node["edges"]
        i = max(0, min(bisect.bisect_right(edges, x)-1, len(node["content"])-1))
        return evaluate_correction(node["content"][i], inputs)
    raise ValueError("unsupported SF node %r" % nodetype)


def find_pt_edges(node):
    """The pT bin edges of a correctionlib node (None if it has no pT binning)."""
    if isinstance(node, dict):
        if node.get("nodetype") == "binning" and node.get("input") == "pT":
            return node["edges"]
        for item in node.get("content", []):
            value = item["value"] if isinstance(item, dict) and "value" in item else item
            found = find_pt_edges(value)
            if found:
                return found
    return None
