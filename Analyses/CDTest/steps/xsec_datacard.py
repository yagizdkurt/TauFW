"""Python step of the CDTest analysis: step 8 of the CMSDAS26 long exercise, the datacard of the Z cross-section fit
(Fit 2; docs/CMSDAS26/datacards.md of long-ex). Ported from long-ex Plotter/make_xsec_fit.py, apart from the
settings, which are the step's options instead of the datacard block of cmsdas_<channel>.yml, and the histogram
file, which is the one of the stage connected to the input 'hists'. The BDT shape uncertainty of make_xsec_fit.py
(--var bdt, step 10) is not ported yet.

Recipe (recipe.yml):

    - stage: python
      id: card_mutau
      inputs: {hists: sf_tauid_tes}     # a stage of steps/tau_sf_hists.py
      file: steps/xsec_datacard.py
      options: {channel: mutau, era: '2024', signal: ZTT, region: signalRegion, variable: m_vis, lumi_unc: 0.014,
                tauid_unc: null, tes_unc: null, sf: {json: sf/...}, bkg_unc: {WJ: 0.15, ...}, onebin: false}

POI r: the signal strength on the Z signal, sigma(Z) = r * sigma_theory. Signal ZTT (mutau) or DY (mumu), process id
0; every other non-empty process is a background with a 'norm_<process> lnN' line from bkg_unc. lumi_<era> lnN on
every process but the data-driven QCD. mutau: 'tauID lnN' and 'tes lnN' on the signal (the measured scale factors are
applied in the histograms and varied within their uncertainty here): tauid_unc and tes_unc, or, if null, the average
relative up/down width over the decay modes 0, 1, 10, 11 of the SF JSON. '* autoMCStats 0'. onebin: every histogram
summed into one bin (a counting experiment, mumu).

Outputs: <run_dir>/stages/<id>/datacard_<channel>.txt and shapes_<channel>.root (the card names the shapes file
relative to itself). One 'datacard' artifact.
"""
import bisect
import json
import os

# hist names the plotter uses for the observed data (data group name, e.g. 'Muon' in Run3)
DATA_NAMES = ('data_obs', 'data', 'Muon', 'Muon0', 'Muon1', 'SingleMuon', 'EGamma', 'Observed')
SHAPES_FILE = "shapes_%s.root"
CARD_FILE   = "datacard_%s.txt"
SF_DEFAULTS = {'vsjet': 'Tight', 'vse': 'VVLoose', 'vsmu': 'Tight', 'tauid_correction': 'TauIdSF_2024_corrTES',
               'tes_correction': 'TauES_2024_corrTES'}  # long-ex cmsdas_config.py DEFAULTS


def run(ctx):
    """Read the histograms of the region and variable, and write the shapes file and the datacard."""
    import ROOT as R
    R.gROOT.SetBatch(True)
    opts    = ctx.options
    channel = opts['channel']
    era     = str(opts['era'])
    signal  = opts['signal']
    sf      = dict(SF_DEFAULTS, **(opts.get('sf') or {}))
    files   = [a['file'] for a in ctx.input('hists', kind='histograms') if a.get('channel') == channel]
    if len(files) != 1:
        raise ValueError("input 'hists' has %d histogram file(s) of channel %s, expected one" % (len(files), channel))

    tauid_unc, tes_unc = None, None
    if _has_tau_signal(channel, signal):  # TauID/TES uncertainties of the ZTT signal (mutau only)
        tauid_unc = _unc(opts.get('tauid_unc'), ctx.path(sf['json']), sf['tauid_correction'], sf, 'TauID SF', ctx.log)
        tes_unc   = _unc(opts.get('tes_unc'), ctx.path(sf['json']), sf['tes_correction'], sf, 'TES', ctx.log)

    # read the per-process histograms and separate observed data from the MC/QCD templates
    data, nominal = _load_histograms(R, files[0], opts['region'], opts['variable'], signal)
    if opts.get('onebin'):  # collapse every histogram to one bin (counting experiment, used for mumu)
        data = _to_onebin(data)
        nominal = {p: _to_onebin(h) for p, h in nominal.items()}

    # every non-empty process except the signal is a background with an lnN normalization
    backgrounds = sorted(p for p in nominal if p != signal and nominal[p].Integral() > 0)
    bkgunc = _bkg_uncertainties(opts.get('bkg_unc') or {}, backgrounds, ctx.log)

    shapes = os.path.join(ctx.stage_dir, SHAPES_FILE % channel)
    _write_shapes(R, shapes, data, signal, backgrounds, nominal)
    lines = _datacard_lines(channel, era, data, signal, backgrounds, nominal, bkgunc, opts['lumi_unc'],
                            tauid_unc, tes_unc)
    card = os.path.join(ctx.stage_dir, CARD_FILE % channel)
    with open(card, 'w') as stream:
        stream.write("\n".join(lines) + "\n")
    nbins = "1 bin" if opts.get('onebin') else "%d bins" % data.GetNbinsX()
    ctx.log("wrote %s (signal=%s, %d backgrounds, %s, observation %.1f)" % (card, signal, len(backgrounds), nbins,
                                                                          data.Integral()))
    return {'message': "%s: signal %s, %d backgrounds, %s" % (channel, signal, len(backgrounds), nbins),
            'artifacts': [{'kind': 'datacard', 'era': era, 'channel': channel, 'card': card, 'shapes': shapes,
                           'signal': signal, 'backgrounds': backgrounds, 'observation': data.Integral(),
                           'tauid_unc': tauid_unc, 'tes_unc': tes_unc}]}


def _load_histograms(R, histfile, region, var, signal):
    """(data, {process: TH1}) for the fit region; the data hist is removed from the dict."""
    fin = R.TFile.Open(histfile)
    if not fin or fin.IsZombie():
        raise IOError("cannot open %s" % (histfile))
    nominal = _collect_nominal(fin, region, var)
    dataname = next((p for p in nominal if p in DATA_NAMES), None)
    if not dataname:
        raise ValueError("no data histogram (data_obs/data) in %s:%s" % (histfile, region))
    data = nominal.pop(dataname)
    if signal not in nominal:
        raise ValueError("signal %r not found; available: %s" % (signal, sorted(nominal)))
    return data, nominal


def _collect_nominal(fin, region, var):
    """{process: TH1} for nominal hists named '<var>_<process>' (skip *Up/*Down variations)."""
    directory = fin.Get(region)
    if not directory:
        raise ValueError("region %r not found in input file" % (region))
    procs, pre = {}, var + "_"
    for key in directory.GetListOfKeys():
        name = key.GetName()
        if not name.startswith(pre):
            continue
        proc = name[len(pre):]
        if proc.endswith('Up') or proc.endswith('Down'):
            continue  # systematic shape variation, not a nominal process
        if proc.endswith('QCD'):
            proc = 'QCD'  # plotter names the data-driven QCD '<region>_QCD'
        hist = directory.Get(name)
        hist.SetDirectory(0)
        procs[proc] = hist
    return procs


def _to_onebin(hist):
    """A copy of hist with all bins merged into one (total yield kept)."""
    copy = hist.Clone(hist.GetName() + "_1b")
    copy.SetDirectory(0)
    copy.Rebin(copy.GetNbinsX())  # merge all bins -> single-bin counting experiment
    return copy


def _datacard_lines(channel, era, data, signal, backgrounds, nominal, bkgunc, lumi_unc, tauid_unc, tes_unc):
    """The Combine datacard as a list of text lines."""
    procs = [signal] + backgrounds
    def row(name, typ, vals):
        return name + " " + typ + "".join(" %s" % v for v in vals)
    def lnN(name, unc, applies_to):
        """One lnN row: '1+unc' for the processes in applies_to, '-' for the others."""
        return row(name, "lnN", ["%.3f" % (1 + unc) if p in applies_to else "-" for p in procs])

    # header: one bin (channel), N processes, shapes file, observed yield
    lines  = ["imax 1", "jmax %d" % (len(procs) - 1), "kmax *", "-" * 60]
    lines += ["shapes * %s %s $PROCESS $PROCESS_$SYSTEMATIC" % (channel, SHAPES_FILE % channel), "-" * 60]
    lines += ["bin %s" % channel, "observation %.4f" % data.Integral(), "-" * 60]
    # processes and their expected yields
    lines += [row("bin", "", [channel for _ in procs])]
    lines += [row("process", "", procs)]
    lines += [row("process", "", [0 if p == signal else i for i, p in enumerate(procs)])]  # signal id = 0
    lines += [row("rate", "", ["%.4f" % nominal[p].Integral() for p in procs])]
    lines += ["-" * 60]
    # luminosity on all MC (QCD is data-driven -> no lumi uncertainty)
    lines += [lnN("lumi_%s" % era, lumi_unc, [p for p in procs if p != 'QCD'])]
    # TauID + TES on the signal (mutau only): measured value applied, varied within uncertainty
    if _has_tau_signal(channel, signal):
        lines += [lnN("tauID", tauid_unc, [signal])]
        lines += [lnN("tes", tes_unc, [signal])]
    # background normalizations (floated within the uncertainties of bkg_unc)
    for bkg in backgrounds:
        lines += [lnN("norm_%s" % bkg, bkgunc[bkg], [bkg])]
    lines += ["* autoMCStats 0"]
    return lines


def _write_shapes(R, path, data, signal, backgrounds, nominal):
    """Write and close the shapes ROOT file before building the datacard."""
    fout = R.TFile(path, 'RECREATE')
    data.Write('data_obs')
    for proc in [signal] + backgrounds:
        nominal[proc].Write(proc)
    fout.Close()


def _has_tau_signal(channel, signal):
    """TauID/TES uncertainties act on the Z->tautau signal only (mutau)."""
    return 'tau' in channel and signal == 'ZTT'


def _unc(value, jsonfile, corrname, sf, name, log):
    """The relative uncertainty: the option if given, else derived from the measured SF JSON."""
    if value is None:
        value = _measure_relative_unc(jsonfile, corrname, sf)
        log("derived %s rel. uncertainty: %.3f" % (name, value))
    return float(value)


def _measure_relative_unc(jsonfile, corrname, sf, pt=40.0):
    """Average relative up/down width over DM=0,1,10,11, from the measured correctionlib JSON."""
    with open(jsonfile) as stream:
        data = [c for c in json.load(stream)["corrections"] if c["name"] == corrname][0]["data"]
    diffs = []
    for dm in (0, 1, 10, 11):
        inp = lambda s: {"genmatch": 5, "DM": dm, "pT": pt, "syst": s,
                         "wp_VSmu": sf['vsmu'], "wp_VSe": sf['vse'], "wp_VSjet": sf['vsjet']}
        nom, up, down = (_sf_eval(data, inp(s)) for s in ("nom", "up", "down"))
        diffs.append(0.5*(abs(up - nom) + abs(nom - down))/nom)
    return sum(diffs)/len(diffs)


def _sf_eval(node, inp):
    """Minimal evaluator for a correctionlib schema node (category/binning/leaf); stdlib only."""
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


def _bkg_uncertainties(given, backgrounds, log):
    """{background: relative normalization uncertainty} for the processes in the card."""
    missing = [bkg for bkg in backgrounds if bkg not in given]
    if missing:
        raise ValueError("bkg_unc has no value for: %s (give each background in the card a relative "
                         "normalization uncertainty, e.g. %s: 0.10)" % (", ".join(missing), missing[0]))
    uncs = {}
    for bkg in backgrounds:
        unc = given[bkg]
        if isinstance(unc, bool) or not isinstance(unc, (int, float)) or not 0 < unc < 1:
            raise ValueError("bkg_unc.%s is %r: give the relative uncertainty as a number between 0 and 1" % (bkg, unc))
        uncs[bkg] = float(unc)
    for bkg in given:
        if bkg not in backgrounds:
            log("Warning: bkg_unc.%s is not used (no such background in the card)" % (bkg))
    return uncs
