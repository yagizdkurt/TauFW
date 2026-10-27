"""Step 9 of the CMSDAS26 long exercise: measure the Z cross section with Combine.

For each datacard (mutau and mumu), this step runs the Combine commands of the exercise one after the other:

  1. text2workspace.py         the datacard as a RooFit workspace
  2. MultiDimFit --algo singles  the best-fit r and its 68% interval: the number to quote
  3. FitDiagnostics            the fit with all nuisances, for the pulls and correlations
  4. NLL scans                 r scanned with the nuisances floating (total) and frozen at the best fit (stat only),
                               drawn by plot1DScan.py
  5. impacts (optional)        how much each nuisance moves r (combineTool.py, plotImpacts.py)
  6. post-fit shapes (optional) the templates before and after the fit (PostFitShapesFromWorkspace)

Then the result plots of the exercise (steps/xsec_plots.py): pre/post-fit m_vis, pulls, and the summary with the
ratio r(mutau)/r(mumu), in which the luminosity cancels (lepton universality).

Ported from docs/CMSDAS26/measurement.md and Plotter/plot_xsec_results.py of long-ex. It needs Combine and
CombineHarvester (cmsenv in a CMSSW area with both); the step stops before anything runs if a tool is missing.

In the recipe:

    - stage: python
      id: xsec_fit
      inputs: {mutau: card_mutau, mumu: card_mumu}   # stages of steps/xsec_datacard.py, one per fit
      file: steps/xsec_fit.py
      options:
        era: '2024'
        lumi: '109'                                    # the label of the plots, fb^-1
        points: 80                                     # of the NLL scans
        fits:                                          # one per input, by its name
          mutau: {rmin: 0.85, rmax: 1.12, impacts: true, postfit_shapes: true}
          mumu:  {rmin: 0.92, rmax: 1.01, singles_extra: [--setRobustFitTolerance, '0.01',
                                                         --cminDefaultMinimizerStrategy, '0']}

Outputs, in <run_dir>/stages/<id>/:
  results.txt          r of every fit (singles), the scan values with the stat part, and the ratio
  the Combine files, the plots (scan_<ch>, impacts_<ch>, mvis_prefit/postfit_mutau, pulls_<ch>, summary_xsec)
  combine_logs/        one log per command, numbered in the order they ran

The file reads from top to bottom:
  1. IMPORTS AND OPTIONS    what the step reads from the framework
  2. PIPELINE               run(ctx): the whole step in a few lines
  3. ANALYSIS FUNCTIONS     the Combine commands of one fit, the result plots
  4. BOILERPLATE            running commands, reading the results, the table
"""

# =====================================================================================================================
#  1. IMPORTS AND OPTIONS
# =====================================================================================================================
import os
import shutil
import subprocess
import sys
from types import SimpleNamespace

import ROOT as R
import xsec_plots  # next to this file: the plots of long-ex plot_xsec_results.py

SINGLES = "higgsCombine.xsec_%s.MultiDimFit.mH120.root"  # the output of the singles fit of channel %s


def read_options(ctx):
    """The recipe options of this stage, with their defaults."""
    opts = ctx.options
    return SimpleNamespace(
        era      = str(opts['era']),
        lumi     = str(opts.get('lumi', '109')),   # fb^-1, the label of the plots
        points   = int(opts.get('points', 80)),    # points of the NLL scans
        fits     = opts['fits'],                   # {channel: its fit options}
        stagedir = ctx.stage_dir,                  # where this stage writes its outputs, and where Combine runs
    )


# =====================================================================================================================
#  2. PIPELINE
# =====================================================================================================================

def run(ctx):
    """The step: called by the framework with the context of this stage (ctx)."""
    opts = read_options(ctx)
    check_tools(opts.fits)
    runner = CommandRunner(ctx)

    # One fit per datacard: copy the card here, then run its Combine commands.
    results = {}
    for channel, fit in opts.fits.items():
        copy_datacard(ctx, channel, opts.stagedir)
        results[channel] = fit_channel(runner, channel, fit, opts.points)

    # The plots of the exercise, and the summary with the ratio r(mutau)/r(mumu).
    summary = draw_result_plots(opts)

    table = write_results_table(results, summary, opts.stagedir, ctx.log)
    return build_result(results, summary, table, opts.era)


# =====================================================================================================================
#  3. ANALYSIS FUNCTIONS
# =====================================================================================================================

def fit_channel(runner, ch, fit, points):
    """The Combine commands of one fit (measurement.md); returns r and its interval from the singles fit."""
    card, ws = "datacard_%s.txt" % ch, "datacard_%s.root" % ch
    rrange = ['--rMin', str(fit['rmin']), '--rMax', str(fit['rmax'])]
    build_workspace(runner, ch, card)
    fit_best_r(runner, ch, ws, rrange, fit.get('singles_extra', []))
    fit_diagnostics(runner, ch, ws, rrange)
    likelihood_scans(runner, ch, ws, rrange, points)
    if fit.get('impacts'):
        impacts(runner, ch, ws)
    if fit.get('postfit_shapes'):
        postfit_shapes(runner, ch, ws, card)
    return read_singles_result(os.path.join(runner.cwd, SINGLES % ch))


def build_workspace(runner, ch, card):
    """The datacard as a RooFit workspace: datacard_<ch>.root."""
    runner.run('t2w_%s' % ch, ['text2workspace.py', card])


def fit_best_r(runner, ch, ws, rrange, extra):
    """The best-fit r with its total 68% interval (--robustFit 1 is needed, see the checks of measurement.md)."""
    runner.run('singles_%s' % ch, ['combine', '-M', 'MultiDimFit', '-P', 'r', '--algo', 'singles', '--robustFit', '1']
               + rrange + [str(x) for x in extra] + ['-n', '.xsec_%s' % ch, ws])


def fit_diagnostics(runner, ch, ws, rrange):
    """The fit result with all nuisances (pulls, correlations), used by the result plots."""
    runner.run('fitdiag_%s' % ch, ['combine', '-M', 'FitDiagnostics', '--robustHesse', '1'] + rrange
               + ['-n', '.xsec_%s' % ch, ws])


def likelihood_scans(runner, ch, ws, rrange, points):
    """The NLL scans of r: total (nuisances floating), and stat only (nuisances frozen at the best fit, which is
    saved first); then the plot of both."""
    grid = ['combine', '-M', 'MultiDimFit', '-P', 'r', '--algo', 'grid', '--points', str(points)] + rrange
    runner.run('scan_%s' % ch, grid + ['-n', '.scan_%s' % ch, ws])
    runner.run('bestfit_%s' % ch, ['combine', '-M', 'MultiDimFit', '-P', 'r', '--algo', 'none'] + rrange
               + ['--saveWorkspace', '-n', '.bestfit_%s' % ch, ws])
    runner.run('scan_statonly_%s' % ch, grid + ['-n', '.scan_%s_statonly' % ch,
               'higgsCombine.bestfit_%s.MultiDimFit.mH120.root' % ch, '--snapshotName', 'MultiDimFit',
               '--freezeParameters', 'allConstrainedNuisances'])
    runner.run('plotscan_%s' % ch, [sys.executable, shutil.which('plot1DScan.py'),
               'higgsCombine.scan_%s.MultiDimFit.mH120.root' % ch, '--POI', 'r', '-o', 'scan_%s' % ch,
               '--main-label', 'Total', '--others', 'higgsCombine.scan_%s_statonly.MultiDimFit.mH120.root:Stat only:2' % ch,
               '--breakdown', 'Syst,Stat'])


def impacts(runner, ch, ws):
    """How much each nuisance moves r: the initial fit, one fit per nuisance, the json and its plot."""
    command = ['combineTool.py', '-M', 'Impacts', '-d', ws, '-m', '90']
    runner.run('impacts_initial_%s' % ch, command + ['--doInitialFit', '--robustFit', '1'])
    runner.run('impacts_fits_%s' % ch, command + ['--doFits', '--robustFit', '1'])
    runner.run('impacts_json_%s' % ch, command + ['-o', 'impacts_%s.json' % ch])
    runner.run('impacts_plot_%s' % ch, ['plotImpacts.py', '-i', 'impacts_%s.json' % ch, '-o', 'impacts_%s' % ch])


def postfit_shapes(runner, ch, ws, card):
    """The pre- and post-fit templates with their uncertainties, in the binning of the datacard."""
    runner.run('postfit_shapes_%s' % ch, ['PostFitShapesFromWorkspace', '-w', ws, '-d', card, '--output',
               'postfit_shapes_%s.root' % ch, '-f', 'fitDiagnostics.xsec_%s.root:fit_s' % ch, '--postfit',
               '--sampling'])


def draw_result_plots(opts):
    """The plots of long-ex plot_xsec_results.py; returns the summary values (r of both channels from the scans,
    and the ratio), or None if mutau or mumu is not fitted."""
    out = opts.stagedir
    if 'mutau' in opts.fits and opts.fits['mutau'].get('postfit_shapes'):
        for stage in ('prefit', 'postfit'):
            xsec_plots.plot_mvis(out, out, 'mutau', stage, opts.lumi, opts.era)
    for ch in opts.fits:
        xsec_plots.plot_pulls(out, out, ch, opts.lumi, opts.era)
    if {'mutau', 'mumu'} <= set(opts.fits):
        return xsec_plots.plot_summary(out, out, opts.lumi, opts.era)
    return None


# =====================================================================================================================
#  4. BOILERPLATE
# =====================================================================================================================

class CommandRunner:
    """Runs the commands one after the other in the stage directory, each with its own log in combine_logs/
    (numbered in the order they ran). Stops the step with the end of the log if a command fails."""

    def __init__(self, ctx):
        self.ctx, self.cwd, self.count = ctx, ctx.stage_dir, 0
        os.makedirs(os.path.join(self.cwd, 'combine_logs'), exist_ok=True)

    def run(self, name, argv):
        self.count += 1
        log = os.path.join(self.cwd, 'combine_logs', "%02d_%s.log" % (self.count, name))
        self.ctx.log("%s: %s" % (name, " ".join(argv)))
        with open(log, 'w') as stream:
            stream.write("$ %s\n" % (" ".join(argv)))
            stream.flush()
            code = subprocess.run(argv, cwd=self.cwd, stdout=stream, stderr=subprocess.STDOUT).returncode
        if code != 0:
            with open(log) as stream:
                tail = stream.read().splitlines()[-15:]
            raise RuntimeError("%s failed (exit code %d), log %s:\n%s" % (name, code, log, "\n".join(tail)))


def check_tools(fits):
    """Stop before anything runs if a tool the fits need is not in PATH."""
    tools = ['text2workspace.py', 'combine', 'plot1DScan.py']
    if any(fit.get('impacts') for fit in fits.values()):
        tools += ['combineTool.py', 'plotImpacts.py']
    if any(fit.get('postfit_shapes') for fit in fits.values()):
        tools += ['PostFitShapesFromWorkspace']
    missing = [tool for tool in tools if not shutil.which(tool)]
    if missing:
        raise RuntimeError("not found in PATH: %s (cmsenv in a CMSSW area with combine and CombineHarvester)"
                           % (", ".join(missing)))


def copy_datacard(ctx, ch, stagedir):
    """Copy the datacard and its shapes file from the input stage of the channel (the input named after it) to the
    stage directory: the card names the shapes file relative to itself."""
    cards = ctx.input(ch, kind='datacard')
    if len(cards) != 1:
        raise ValueError("input %r has %d datacard(s), expected one" % (ch, len(cards)))
    for key in ('card', 'shapes'):
        shutil.copy(cards[0][key], stagedir)


def read_singles_result(path):
    """r and its total 68% interval from the output of the singles fit: the best fit (quantileExpected -1) and the
    two bounds."""
    fin = R.TFile.Open(path)
    tree = fin.Get("limit") if fin else None
    if not tree:
        raise RuntimeError("no limit tree in %s" % (path))
    best, bounds = None, []
    for entry in tree:
        if entry.quantileExpected == -1:
            best = entry.r
        else:
            bounds.append(entry.r)
    fin.Close()
    if best is None or len(bounds) < 2:
        raise RuntimeError("%s has no best fit and two bounds of r (failed fit?)" % (path))
    return {'r': best, 'lo': best - min(bounds), 'hi': max(bounds) - best, 'file': path}


def write_results_table(results, summary, stagedir, log):
    """results.txt, also written to the log; returns its path."""
    table = os.path.join(stagedir, 'results.txt')
    text = results_table(results, summary)
    with open(table, 'w') as stream:
        stream.write(text)
    log("wrote %s" % (table))
    for line in text.splitlines():
        log(line)
    return table


def results_table(results, summary):
    """The results as text: r of every fit (singles), and the scan values of the summary with the ratio."""
    lines = ["# r = sigma / sigma_theory (measurement.md: quote the singles interval)",
             "%-8s %8s %8s %8s   %s" % ("fit", "r", "-tot", "+tot", "from")]
    for ch, x in results.items():
        lines.append("%-8s %8.4f %8.4f %8.4f   MultiDimFit --algo singles" % (ch, x['r'], x['lo'], x['hi']))
    if summary:
        lines.append("")
        lines.append("%-8s %8s %8s %8s %8s %8s   %s" % ("", "r", "-tot", "+tot", "-stat", "+stat", "from"))
        for key in ('mutau', 'mumu', 'ratio'):
            x = summary[key]
            lines.append("%-8s %8.4f %8.4f %8.4f %8.4f %8.4f   %s" % (
                key, x['r'], x['lo'], x['hi'], x['statlo'], x['stathi'],
                "NLL scans; luminosity cancels" if key == 'ratio' else "NLL scan (total, stat only)"))
    return "\n".join(lines) + "\n"


def build_result(results, summary, table, era):
    """What the step returns to the framework: a short message and its outputs (artifacts)."""
    artifacts = [dict(kind='xsec', era=era, channel=ch, **values) for ch, values in results.items()]
    artifacts.append({'kind': 'table', 'path': table, 'nrows': len(results)})
    message = ", ".join("r(%s) = %.3f" % (ch, values['r']) for ch, values in results.items())
    if summary:
        message += ", ratio %.3f" % (summary['ratio']['r'])
    return {'message': message, 'artifacts': artifacts}
