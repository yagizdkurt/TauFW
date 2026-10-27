"""Python step of the CDTest analysis: the histograms and control plots of step 7, Tier A, of the CMSDAS26 long
exercise (docs/CMSDAS26/tauid_es.md of long-ex): the measured tau ID scale factor and tau energy scale (TES) applied
at plot level, and the histogram files the datacards of step 8 read. Ported from the plot path of long-ex
Plotter/plots_and_histograms_CMSDAS26.py (build_tauid_sf_weight, build_tes_map, _apply_tes_ztt, plot) and
Plotter/cmsdas_config.py (sf_eval, pt_edges, check_sf_wps), apart from the imports, the sample set of this bundle
and the selection, which is read from a channel setup of this bundle.

Recipe (recipe.yml):

    - stage: python
      id: sf_tauid_tes
      inputs: null
      file: steps/tau_sf_hists.py
      options: {era: '2024', channel: mutau, setup: setup_mutau.yml, samples: v15_2024.yml,
                tuples: /eos/.../$ERA/$GROUP, variables: [{name: m_vis, nbins: 40, min: 0, max: 200}],
                qcd: {method: QCD_OSSS, scale: 1.1}, sf: {json: sf/..., vsjet: Tight, vse: VVLoose, vsmu: Tight},
                tauid_sf: true, apply_tes: true, syst: nom}

Long-ex equivalents: tauid_sf: true is --tauid-sf, apply_tes: true is --apply-tes, syst is --syst (nom, up, down).

Selection: one per region of the setup, named after it (as the selections of cmsdas_<channel>.yml):
baselineCuts && definition.
--tauid-sf: the tau ID SF of the JSON as a weight per decay mode and tau pT bin, on genuine taus (genmatch_2==5)
only, on top of the MC weight (the tuples have idweight_2 = 1).
--apply-tes: an energy scale cannot be a weight; the tuples have TES-shifted copies (<sample>_<channel>_TES0p998.root
...). For each decay mode, ZTT is taken from the copy closest to the measured TES (step 0.002), and the four decay
modes are summed.

Outputs: <run_dir>/stages/<id>/hists/<era>/<channel>.root (one directory per selection, histograms named
<variable>_<process>, e.g. m_vis_ZTT, m_vis_Muon: the format of long-ex hists/<era>/<channel>.root, without a tag),
and the plots <run_dir>/stages/<id>/plots/<era>/<variable>_<channel>-<selection>-<era>.png and .pdf. One 'histograms'
and one 'plots' artifact.
"""
import bisect
import json
import os
import re

DMS = (0, 1, 10, 11)  # the decay modes with scale factors
# DeepTau working points as stored in the id*_2 branches (long-ex cmsdas_config.py)
WP_INT = {'vsjet': {'VVLoose': 2, 'VLoose': 3, 'Loose': 4, 'Medium': 5, 'Tight': 6, 'VTight': 7},
          'vse':   {'VVLoose': 2, 'VLoose': 3, 'Loose': 4, 'Medium': 5, 'Tight': 6, 'VTight': 7},
          'vsmu':  {'VLoose': 1, 'Loose': 2, 'Medium': 3, 'Tight': 4}}
WP_BRANCH = {'vsjet': 'idDeepTau2018v2p5VSjet_2', 'vse': 'idDeepTau2018v2p5VSe_2', 'vsmu': 'idDeepTau2018v2p5VSmu_2'}
SF_DEFAULTS = {'vsjet': 'Tight', 'vse': 'VVLoose', 'vsmu': 'Tight', 'tauid_correction': 'TauIdSF_2024_corrTES',
               'tes_correction': 'TauES_2024_corrTES', 'tes_step': 0.002}  # long-ex cmsdas_config.py DEFAULTS


def run(ctx):
    """Fill the stacks of every variable and selection, with the options' corrections, write them to the histogram
    file and draw them."""
    import ROOT as R
    from TauFW.Histogrammer.sample.utils import LOG, Sel, Var, setera
    from TauFW.Histogrammer.sample.model import getsampleset, load_sample_model
    R.gROOT.SetBatch(True)
    opts      = ctx.options
    era       = str(opts['era'])
    channel   = opts['channel']
    tauid_sf  = bool(opts.get('tauid_sf', False))
    apply_tes = bool(opts.get('apply_tes', False))
    syst      = opts.get('syst', 'nom')
    qcd       = opts.get('qcd') or {}
    sf        = dict(SF_DEFAULTS, **(opts.get('sf') or {}))
    selections = _selections(ctx.path(opts['setup']), Sel)
    variables  = [_variable(var, Var) for var in opts['variables']]

    addsf, tesmap = [], None
    if tauid_sf or apply_tes:
        sfjson = ctx.path(sf['json'])
        _check_sf_wps(selections, sf)  # SF working points must match the selection
        if tauid_sf:  # apply the measured TauID SF (per DM,pt weight on genuine taus)
            addsf.append(_tauid_sf_weight(sfjson, sf, syst, ctx.log))
        if apply_tes:
            tesmap = _tes_map(sfjson, sf, syst, ctx.log)

    setera(era)
    split = ['DY'] if 'tau' in channel else []  # gen-match split needs a hadronic tau (mutau only)
    sampleset = getsampleset(channel, era, load_sample_model(ctx.path(opts['samples'])),
                             fname="$PICODIR/$SAMPLE_$CHANNEL$TAG.root", tuples=opts['tuples'],
                             addsf=addsf, split=split, table=True)

    histfile = os.path.join(ctx.stage_dir, 'hists', era, "%s.root" % (channel))
    plotdir  = os.path.join(ctx.stage_dir, 'plots', era)
    os.makedirs(os.path.dirname(histfile), exist_ok=True)
    os.makedirs(plotdir, exist_ok=True)
    plots = _plot(R, LOG, Sel, sampleset, channel, era, selections, variables, qcd.get('method'),
                  qcd.get('scale') or 1.1, plotdir, histfile, tesmap)
    ctx.log("wrote %s and %d plot(s)" % (histfile, len(plots)))
    what = ", ".join(name for name, on in (('tau ID SF', tauid_sf), ('TES', apply_tes)) if on) or "no tau corrections"
    return {'message': "%s %s: %s%s" % (channel, era, what, "" if syst == 'nom' else " (%s)" % syst),
            'artifacts': [{'kind': 'histograms', 'era': era, 'channel': channel, 'file': histfile,
                           'selections': [sel.filename for sel in selections], 'tauid_sf': tauid_sf,
                           'apply_tes': apply_tes, 'syst': syst},
                          {'kind': 'plots', 'era': era, 'channel': channel, 'directory': plotdir, 'files': plots}]}


def _plot(R, LOG, Sel, sampleset, channel, era, selections, variables, qcdmethod, qcdscale, outdir, histfile,
          tesmap):
    """Data/MC comparison for the selections and variables. If qcdmethod is set (mutau: 'QCD_OSSS'), QCD is
    estimated data-driven from the same-sign region and extrapolated to opposite-sign with qcdscale. If tesmap (a
    {DM:'_TES..'} map) is given, the ZTT signal is rebuilt from the per-DM closest TES-shifted samples."""
    outhists = R.TFile.Open('file:' + histfile, 'recreate')
    exts  = ['png', 'pdf']
    files = []
    for selection in selections:
        outhists.mkdir(selection.filename)
        # data-driven QCD from the same-sign region, extrapolated to opposite-sign with 'scale'
        stacks = sampleset.getstack(variables, selection, method=qcdmethod, scale=qcdscale, parallel=True)
        if tesmap and 'tau' in channel:  # rebuild ZTT from the per-DM TES-shifted samples
            _apply_tes_ztt(LOG, Sel, sampleset, stacks, variables, selection, tesmap)
        fname = "%s/$VAR_%s-%s-%s" % (outdir, channel, selection.filename, era)
        text  = "%s: %s" % (channel.replace('mu', "#mu").replace('tau', "#tau_{h}"), selection.title)
        for stack, variable in stacks.items():
            outhists.cd(selection.filename)
            for hist in stack.hists:
                hist.Write(hist.GetName().replace("QCD_", "QCD"), R.TH1.kOverwrite)
            stack.draw()
            stack.drawlegend(x1=0.6, x2=0.95, y1=0.35, y2=0.95)
            stack.drawtext(text)
            stack.saveas(fname, ext=exts)
            files += ["%s/%s_%s-%s-%s.%s" % (outdir, variable[0].filename, channel, selection.filename, era, ext)
                      for ext in exts]
            stack.close()
    outhists.Close()
    return files


def _apply_tes_ztt(LOG, Sel, sampleset, stacks, variables, selection, tesmap):
    """Replace the ZTT histograms in 'stacks' with the per-DM TES-shifted ones: for each DM, swap ZTT to the closest
    pre-shifted _TES sample (sampleset.shift) and take its dm_2==DM slice, then sum over DM."""
    ztt_sum = {}  # Var.name -> TH1 (summed over DM, TES-shifted)
    for dm, tag in tesmap.items():
        LOG.info(">>> TES swap: DM%-2d -> ZTT read from *%s*.root samples" % (dm, tag))
        shifted = sampleset.shift(['ZTT'], tag, tag, split=True, filter=False, share=True)
        sel_dm = Sel(selection.filename + '_dm%d' % dm, selection.selection + " && dm_2==%d" % dm)
        res = shifted.getstack(variables, sel_dm, method=None, data=False, parallel=True)
        items = res.items() if isinstance(res, dict) else [(res, (variables[0], sel_dm))]
        for stack, key in items:
            var = key[0] if isinstance(key, tuple) else key
            for hist in stack.hists:
                if '_ZTT' in hist.GetName():  # shifted names are m_vis_ZTT_TES0p996
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


def _tauid_sf_weight(jsonfile, sf, syst, log):
    """A per-(DM,pt) TauID SF weight expression from the measured JSON, applied to genuine taus (genmatch_2==5) and
    1.0 otherwise. Reads the JSON directly (no correctionlib dependency)."""
    data = _correction(jsonfile, sf['tauid_correction'])
    edges = _pt_edges(data) or [0.0, 1e4]
    def val(dm, pt):
        return _sf_eval(data, {"genmatch": 5, "DM": dm, "pT": pt, "syst": syst,
                               "wp_VSmu": sf['vsmu'], "wp_VSe": sf['vse'], "wp_VSjet": sf['vsjet']})
    mids = [0.5*(edges[i]+edges[i+1]) for i in range(len(edges)-1)]
    dmexpr = {}
    for dm in DMS:
        vals = [val(dm, m) for m in mids]
        expr = "".join("pt_2<%g?%.4f:" % (edges[i+1], vals[i]) for i in range(len(vals)-1))
        dmexpr[dm] = "(" + expr + "%.4f)" % vals[-1]
    expr = ("(genmatch_2!=5?1.0:dm_2==0?%s:dm_2==1?%s:dm_2==10?%s:dm_2==11?%s:1.0)"
            % (dmexpr[0], dmexpr[1], dmexpr[10], dmexpr[11]))
    log("TauID SF weight (VSjet=%s,VSe=%s,VSmu=%s,%s): %s" % (sf['vsjet'], sf['vse'], sf['vsmu'], syst, expr))
    return expr


def _tes_map(jsonfile, sf, syst, log):
    """{DM: '_TESXpXXX'}: the measured per-DM TES snapped to the pre-shifted sample grid (step tes_step). TES is
    pt-independent, so one value per DM (evaluated at genmatch=5)."""
    data = _correction(jsonfile, sf['tes_correction'])
    step, out = sf['tes_step'], {}
    for dm in DMS:
        tes = _sf_eval(data, {"genmatch": 5, "DM": dm, "pT": 40.0, "syst": syst,
                              "wp_VSmu": sf['vsmu'], "wp_VSe": sf['vse'], "wp_VSjet": sf['vsjet']})
        grid = round(tes/step)*step
        out[dm] = ("_TES%.3f" % grid).replace(".", "p")  # e.g. 0.994 -> _TES0p994
        log("TES DM%d (%s): %.4f -> %s" % (dm, syst, tes, out[dm]))
    log("per-DM TES samples: %s" % out)
    return out


def _correction(jsonfile, name):
    """The data node of the correction `name` of a correctionlib JSON file."""
    with open(jsonfile) as stream:
        corrections = json.load(stream)["corrections"]
    found = [c for c in corrections if c["name"] == name]
    if not found:
        raise KeyError("%s has no correction %r (has: %s)" % (jsonfile, name, ", ".join(c["name"] for c in corrections)))
    return found[0]["data"]


def _sf_eval(node, inp):
    """Minimal evaluator for a correctionlib schema node (category/binning/leaf); stdlib only, so it works even
    when the compiled correctionlib is unavailable."""
    if isinstance(node, (int, float)):
        return float(node)
    nodetype = node.get("nodetype")
    if nodetype == "category":
        key = inp[node["input"]]
        for item in node["content"]:
            if item["key"] == key:
                return _sf_eval(item["value"], inp)
        if node.get("default") is not None:
            return _sf_eval(node["default"], inp)
        raise KeyError("%s=%r" % (node["input"], key))
    if nodetype == "binning":
        x, edges = inp[node["input"]], node["edges"]
        i = max(0, min(bisect.bisect_right(edges, x)-1, len(node["content"])-1))
        return _sf_eval(node["content"][i], inp)
    raise ValueError("unsupported SF node %r" % nodetype)


def _pt_edges(node):
    """pT bin edges of a correctionlib node (None if it has no pT binning)."""
    if isinstance(node, dict):
        if node.get("nodetype") == "binning" and node.get("input") == "pT":
            return node["edges"]
        for item in node.get("content", []):
            value = item["value"] if isinstance(item, dict) and "value" in item else item
            found = _pt_edges(value)
            if found:
                return found
    return None


def _check_sf_wps(selections, sf):
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


def _selections(setupfile, Sel):
    """One Sel per region of a channel setup (fillhists.py format), named after the region, as the selections of
    long-ex cmsdas_<channel>.yml: baselineCuts && definition."""
    import yaml
    with open(setupfile) as stream:
        setup = yaml.safe_load(stream)
    return [Sel(name, "%s && %s" % (setup['baselineCuts'], region['definition']))
            for name, region in (setup.get('regions') or {}).items()]


def _variable(var, Var):
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
