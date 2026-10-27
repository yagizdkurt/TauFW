"""Step 8 of the CMSDAS26 long exercise: write the datacard of the Z cross-section fit.

A datacard tells Combine what to fit: the observed data, the expected yield (and shape) of every process, and the
uncertainties. The parameter of interest is the signal strength r: sigma(Z) = r * sigma_theory, so r = 1 means the
measurement agrees with the prediction.

  signal:       ZTT (mutau) or DY (mumu), process id 0, scaled by r
  backgrounds:  every other process with a non-empty histogram, each with a 'norm_<process> lnN' uncertainty
  lumi_<era>:   the luminosity uncertainty, on every process but the data-driven QCD
  tauID, tes:   (mutau only) the uncertainties of the measured tau ID SF and TES, on the signal; from the options,
                or from the SF file (the average relative up/down width over the decay modes 0, 1, 10, 11)
  autoMCStats:  the statistical uncertainty of the simulation, per bin
  onebin: true  every histogram summed into one bin: a counting experiment (mumu)

Ported from long-ex Plotter/make_xsec_fit.py (docs/CMSDAS26/datacards.md of long-ex); the settings are the step's
options instead of the datacard block of cmsdas_<channel>.yml. Not ported yet: the BDT shape uncertainty (--var bdt,
step 10).

In the recipe:

    - stage: python
      id: card_mutau
      inputs: {hists: sf_tauid_tes}     # a stage of steps/tau_sf_hists.py
      file: steps/xsec_datacard.py
      options: {channel: mutau, era: '2024', signal: ZTT, region: signalRegion, variable: m_vis, lumi_unc: 0.014,
                tauid_unc: null, tes_unc: null, sf: {json: sf/...}, bkg_unc: {WJ: 0.15, ...}, onebin: false}

Outputs, in <run_dir>/stages/<id>/:
  datacard_<channel>.txt    the datacard; it names the shapes file relative to itself
  shapes_<channel>.root     the histograms of the datacard (data_obs and one per process)

The file reads from top to bottom:
  1. IMPORTS AND OPTIONS    what the step reads from the framework
  2. PIPELINE               run(ctx): the whole step in a few lines
  3. ANALYSIS FUNCTIONS     histograms, uncertainties, the datacard
  4. BOILERPLATE            reading the SF file, output files
"""

# =====================================================================================================================
#  1. IMPORTS AND OPTIONS
# =====================================================================================================================
import bisect
import json
import os
from types import SimpleNamespace

import ROOT as R

R.gROOT.SetBatch(True)  # never open a window

# The names the histogram files use for the observed data (the data group, e.g. 'Muon' in Run 3)
DATA_NAMES = ('data_obs', 'data', 'Muon', 'Muon0', 'Muon1', 'SingleMuon', 'EGamma', 'Observed')
SHAPES_FILE = "shapes_%s.root"
CARD_FILE   = "datacard_%s.txt"

# The defaults of the sf option (long-ex cmsdas_config.py DEFAULTS)
SF_DEFAULTS = {'vsjet': 'Tight', 'vse': 'VVLoose', 'vsmu': 'Tight', 'tauid_correction': 'TauIdSF_2024_corrTES',
               'tes_correction': 'TauES_2024_corrTES'}


def read_options(ctx):
    """The recipe options of this stage, with their defaults."""
    opts = ctx.options
    return SimpleNamespace(
        channel   = opts['channel'],
        era       = str(opts['era']),
        signal    = opts['signal'],                    # the process scaled by r
        region    = opts['region'],                    # the selection to take the histograms from
        variable  = opts['variable'],                  # the variable to fit
        lumi_unc  = opts['lumi_unc'],
        tauid_unc = opts.get('tauid_unc'),             # None: from the SF file
        tes_unc   = opts.get('tes_unc'),               # None: from the SF file
        sf        = dict(SF_DEFAULTS, **(opts.get('sf') or {})),
        bkg_unc   = opts.get('bkg_unc') or {},
        onebin    = opts.get('onebin'),
        path      = ctx.path,                          # a file of the bundle, e.g. the SF file
        stagedir  = ctx.stage_dir,                     # where this stage writes its outputs
    )


# =====================================================================================================================
#  2. PIPELINE
# =====================================================================================================================

def run(ctx):
    """The step: called by the framework with the context of this stage (ctx)."""
    opts = read_options(ctx)

    # The histogram file of this channel, from the stage the input 'hists' names (steps/tau_sf_hists.py).
    histfile = histogram_file_of_input(ctx, opts.channel)

    # The uncertainties of the tau corrections on the signal (mutau only).
    tauid_unc, tes_unc = tau_correction_uncertainties(opts, ctx.log)

    # Data and the expected histogram of every process; one bin for a counting experiment.
    data, nominal = load_histograms(histfile, opts.region, opts.variable, opts.signal)
    if opts.onebin:
        data = merge_into_one_bin(data)
        nominal = {p: merge_into_one_bin(h) for p, h in nominal.items()}

    # Every non-empty process but the signal is a background, with its normalization uncertainty.
    backgrounds = sorted(p for p in nominal if p != opts.signal and nominal[p].Integral() > 0)
    bkgunc = background_uncertainties(opts.bkg_unc, backgrounds, ctx.log)

    # Write the shapes file and the datacard that points to it.
    shapes = write_shapes(opts, data, backgrounds, nominal)
    lines = datacard_lines(opts.channel, opts.era, data, opts.signal, backgrounds, nominal, bkgunc, opts.lumi_unc,
                           tauid_unc, tes_unc)
    card = write_datacard(opts, lines)

    nbins = "1 bin" if opts.onebin else "%d bins" % data.GetNbinsX()
    ctx.log("wrote %s (signal=%s, %d backgrounds, %s, observation %.1f)" % (card, opts.signal, len(backgrounds), nbins,
                                                                          data.Integral()))
    return build_result(opts, card, shapes, backgrounds, data, nbins, tauid_unc, tes_unc)


# =====================================================================================================================
#  3. ANALYSIS FUNCTIONS
# =====================================================================================================================

def tau_correction_uncertainties(opts, log):
    """(tauID, TES) relative uncertainties on the Z->tautau signal; (None, None) without a tau signal (mumu)."""
    if not has_tau_signal(opts.channel, opts.signal):
        return None, None
    sfjson = opts.path(opts.sf['json'])
    tauid_unc = option_or_measured(opts.tauid_unc, sfjson, opts.sf['tauid_correction'], opts.sf, 'TauID SF', log)
    tes_unc   = option_or_measured(opts.tes_unc, sfjson, opts.sf['tes_correction'], opts.sf, 'TES', log)
    return tauid_unc, tes_unc


def has_tau_signal(channel, signal):
    """The tauID and TES uncertainties act on the Z->tautau signal only (mutau)."""
    return 'tau' in channel and signal == 'ZTT'


def option_or_measured(value, jsonfile, corrname, sf, name, log):
    """The relative uncertainty: the option if given, else the one of the SF file."""
    if value is None:
        value = relative_uncertainty_from_sf_file(jsonfile, corrname, sf)
        log("derived %s rel. uncertainty: %.3f" % (name, value))
    return float(value)


def relative_uncertainty_from_sf_file(jsonfile, corrname, sf, pt=40.0):
    """The relative up/down width of a correction, averaged over the decay modes 0, 1, 10, 11 (at 40 GeV)."""
    with open(jsonfile) as stream:
        data = [c for c in json.load(stream)["corrections"] if c["name"] == corrname][0]["data"]
    widths = []
    for dm in (0, 1, 10, 11):
        inputs = lambda s: {"genmatch": 5, "DM": dm, "pT": pt, "syst": s,
                            "wp_VSmu": sf['vsmu'], "wp_VSe": sf['vse'], "wp_VSjet": sf['vsjet']}
        nom, up, down = (evaluate_correction(data, inputs(s)) for s in ("nom", "up", "down"))
        widths.append(0.5*(abs(up - nom) + abs(nom - down))/nom)
    return sum(widths)/len(widths)


def load_histograms(histfile, region, var, signal):
    """(data, {process: TH1}) of the fit variable in the fit region; the data is not in the dict."""
    fin = R.TFile.Open(histfile)
    if not fin or fin.IsZombie():
        raise IOError("cannot open %s" % (histfile))
    nominal = nominal_histograms(fin, region, var)
    dataname = next((p for p in nominal if p in DATA_NAMES), None)
    if not dataname:
        raise ValueError("no data histogram (data_obs/data) in %s:%s" % (histfile, region))
    data = nominal.pop(dataname)
    if signal not in nominal:
        raise ValueError("signal %r not found; available: %s" % (signal, sorted(nominal)))
    return data, nominal


def nominal_histograms(fin, region, var):
    """{process: TH1} of the histograms '<var>_<process>' in the directory of the region; the systematic variations
    (*Up, *Down) are skipped."""
    directory = fin.Get(region)
    if not directory:
        raise ValueError("region %r not found in input file" % (region))
    procs, prefix = {}, var + "_"
    for key in directory.GetListOfKeys():
        name = key.GetName()
        if not name.startswith(prefix):
            continue
        proc = name[len(prefix):]
        if proc.endswith('Up') or proc.endswith('Down'):
            continue
        if proc.endswith('QCD'):
            proc = 'QCD'  # the data-driven QCD is named '<region>_QCD'
        hist = directory.Get(name)
        hist.SetDirectory(0)
        procs[proc] = hist
    return procs


def merge_into_one_bin(hist):
    """A copy of the histogram with all bins merged into one (the total yield is kept)."""
    copy = hist.Clone(hist.GetName() + "_1b")
    copy.SetDirectory(0)
    copy.Rebin(copy.GetNbinsX())
    return copy


def background_uncertainties(given, backgrounds, log):
    """{background: relative normalization uncertainty}: every background of the card needs one in bkg_unc."""
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


def datacard_lines(channel, era, data, signal, backgrounds, nominal, bkgunc, lumi_unc, tauid_unc, tes_unc):
    """The Combine datacard as a list of text lines."""
    procs = [signal] + backgrounds
    def row(name, typ, values):
        return name + " " + typ + "".join(" %s" % v for v in values)
    def lnN(name, unc, applies_to):
        """One lnN row: '1+unc' for the processes in applies_to, '-' for the others."""
        return row(name, "lnN", ["%.3f" % (1 + unc) if p in applies_to else "-" for p in procs])

    # header: one bin (the channel), the number of processes, the shapes file, the observed yield
    lines  = ["imax 1", "jmax %d" % (len(procs) - 1), "kmax *", "-" * 60]
    lines += ["shapes * %s %s $PROCESS $PROCESS_$SYSTEMATIC" % (channel, SHAPES_FILE % channel), "-" * 60]
    lines += ["bin %s" % channel, "observation %.4f" % data.Integral(), "-" * 60]
    # the processes and their expected yields; the signal has id 0
    lines += [row("bin", "", [channel for _ in procs])]
    lines += [row("process", "", procs)]
    lines += [row("process", "", [0 if p == signal else i for i, p in enumerate(procs)])]
    lines += [row("rate", "", ["%.4f" % nominal[p].Integral() for p in procs])]
    lines += ["-" * 60]
    # the luminosity on all simulation (QCD is from data)
    lines += [lnN("lumi_%s" % era, lumi_unc, [p for p in procs if p != 'QCD'])]
    # tauID and TES on the signal (mutau only): the measured values are applied, varied within their uncertainty
    if has_tau_signal(channel, signal):
        lines += [lnN("tauID", tauid_unc, [signal])]
        lines += [lnN("tes", tes_unc, [signal])]
    # the background normalizations, free within their uncertainties
    for bkg in backgrounds:
        lines += [lnN("norm_%s" % bkg, bkgunc[bkg], [bkg])]
    lines += ["* autoMCStats 0"]
    return lines


# =====================================================================================================================
#  4. BOILERPLATE
# =====================================================================================================================

def histogram_file_of_input(ctx, channel):
    """The histogram file of the channel among the outputs of the input 'hists'; there must be exactly one."""
    files = [a['file'] for a in ctx.input('hists', kind='histograms') if a.get('channel') == channel]
    if len(files) != 1:
        raise ValueError("input 'hists' has %d histogram file(s) of channel %s, expected one" % (len(files), channel))
    return files[0]


def write_shapes(opts, data, backgrounds, nominal):
    """Write the shapes file (data_obs and one histogram per process, named after it); returns its path."""
    path = os.path.join(opts.stagedir, SHAPES_FILE % opts.channel)
    fout = R.TFile(path, 'RECREATE')
    data.Write('data_obs')
    for proc in [opts.signal] + backgrounds:
        nominal[proc].Write(proc)
    fout.Close()
    return path


def write_datacard(opts, lines):
    """Write the datacard; returns its path."""
    card = os.path.join(opts.stagedir, CARD_FILE % opts.channel)
    with open(card, 'w') as stream:
        stream.write("\n".join(lines) + "\n")
    return card


def build_result(opts, card, shapes, backgrounds, data, nbins, tauid_unc, tes_unc):
    """What the step returns to the framework: a short message and its output (artifact)."""
    return {'message': "%s: signal %s, %d backgrounds, %s" % (opts.channel, opts.signal, len(backgrounds), nbins),
            'artifacts': [{'kind': 'datacard', 'era': opts.era, 'channel': opts.channel, 'card': card,
                           'shapes': shapes, 'signal': opts.signal, 'backgrounds': backgrounds,
                           'observation': data.Integral(), 'tauid_unc': tauid_unc, 'tes_unc': tes_unc}]}


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
