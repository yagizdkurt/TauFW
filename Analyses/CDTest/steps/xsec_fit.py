"""Python step of the CDTest analysis: step 9 of the CMSDAS26 long exercise, the measurement (docs/CMSDAS26/
measurement.md of long-ex): the Combine fits of r in the mutau and mumu channels, the impacts, the likelihood scans
(total and stat only), the pre-/post-fit shapes, and the result plots of long-ex Plotter/plot_xsec_results.py
(steps/xsec_plots.py). The commands are the ones of measurement.md, run in the step's directory.

Recipe (recipe.yml):

    - stage: python
      id: xsec_fit
      inputs: {mutau: card_mutau, mumu: card_mumu}   # stages of steps/xsec_datacard.py, one per fit
      file: steps/xsec_fit.py
      options:
        era: '2024'
        lumi: '109'                                    # the label of the plots, fb^-1
        fits:                                          # one per input, by its name
          mutau: {rmin: 0.85, rmax: 1.12, impacts: true, postfit_shapes: true}
          mumu:  {rmin: 0.92, rmax: 1.01, singles_extra: [--setRobustFitTolerance, '0.01',
                                                         --cminDefaultMinimizerStrategy, '0']}
        points: 80                                     # of the NLL scans

Per fit (channel <ch>; card and shapes copied here from the input stage):
  text2workspace.py datacard_<ch>.txt
  combine -M MultiDimFit -P r --algo singles --robustFit 1 --rMin <rmin> --rMax <rmax> [singles_extra] -n .xsec_<ch>
  combine -M FitDiagnostics --robustHesse 1 --rMin <rmin> --rMax <rmax> -n .xsec_<ch>
  the NLL scan with the nuisances floating (.scan_<ch>), the best fit (.bestfit_<ch>), the scan with the nuisances
  frozen there (.scan_<ch>_statonly), and plot1DScan.py -> scan_<ch>.pdf/.png
  impacts: combineTool.py -M Impacts (initial fit, fits, json) and plotImpacts.py -> impacts_<ch>.pdf
  postfit_shapes: PostFitShapesFromWorkspace -> postfit_shapes_<ch>.root
Then the plots of plot_xsec_results.py: mvis_prefit_mutau, mvis_postfit_mutau, pulls_<ch>, summary_xsec.

Outputs: in <run_dir>/stages/<id>/: the Combine files, the plots above, combine_logs/ (one log per command) and
results.txt: r of every fit from the `singles` fit (the number to quote, measurement.md) and from the NLL scans with
its stat. part, and the ratio r(mutau)/r(mumu) of plot_summary (the luminosity cancels). One 'xsec' artifact per fit
and one 'table' artifact. The step stops at once if a Combine tool is missing (cmsenv in a CMSSW area with combine
and CombineHarvester), before anything runs.
"""
import os
import shutil
import subprocess
import sys

SINGLES = "higgsCombine.xsec_%s.MultiDimFit.mH120.root"


def run(ctx):
    """Run the fits of every input, then the result plots, and write the table."""
    opts   = ctx.options
    era    = str(opts['era'])
    lumi   = str(opts.get('lumi', '109'))
    points = int(opts.get('points', 80))
    fits   = opts['fits']
    _check_tools(fits)
    os.makedirs(os.path.join(ctx.stage_dir, 'combine_logs'), exist_ok=True)
    runner = _Runner(ctx)

    results = {}
    for ch, fit in fits.items():
        cards = ctx.input(ch, kind='datacard')
        if len(cards) != 1:
            raise ValueError("input %r has %d datacard(s), expected one" % (ch, len(cards)))
        for key in ('card', 'shapes'):  # the card names the shapes file relative to itself
            shutil.copy(cards[0][key], ctx.stage_dir)
        results[ch] = _fit(runner, ch, fit, points)

    import xsec_plots  # next to this file (ROOT); the plots of long-ex plot_xsec_results.py
    out = ctx.stage_dir
    if 'mutau' in fits and fits['mutau'].get('postfit_shapes'):
        for stage in ('prefit', 'postfit'):
            xsec_plots.plot_mvis(out, out, 'mutau', stage, lumi, era)
    for ch in fits:
        xsec_plots.plot_pulls(out, out, ch, lumi, era)
    summary = xsec_plots.plot_summary(out, out, lumi, era) if {'mutau', 'mumu'} <= set(fits) else None

    table = os.path.join(out, 'results.txt')
    with open(table, 'w') as stream:
        stream.write(_table(results, summary))
    ctx.log("wrote %s" % (table))
    for line in _table(results, summary).splitlines():
        ctx.log(line)
    artifacts = [dict(kind='xsec', era=era, channel=ch, **values) for ch, values in results.items()]
    artifacts.append({'kind': 'table', 'path': table, 'nrows': len(results)})
    message = ", ".join("r(%s) = %.3f" % (ch, values['r']) for ch, values in results.items())
    if summary:
        message += ", ratio %.3f" % (summary['ratio']['r'])
    return {'message': message, 'artifacts': artifacts}


def _fit(runner, ch, fit, points):
    """The Combine commands of one fit (measurement.md); returns the `singles` result."""
    card, ws = "datacard_%s.txt" % ch, "datacard_%s.root" % ch
    rrange = ['--rMin', str(fit['rmin']), '--rMax', str(fit['rmax'])]
    runner.run('t2w_%s' % ch, ['text2workspace.py', card])
    # best-fit r with its total 68% interval (--robustFit 1 is needed, see the checks of measurement.md)
    runner.run('singles_%s' % ch, ['combine', '-M', 'MultiDimFit', '-P', 'r', '--algo', 'singles', '--robustFit', '1']
               + rrange + [str(x) for x in fit.get('singles_extra', [])] + ['-n', '.xsec_%s' % ch, ws])
    # fit result with all nuisances (pulls, correlations), used by the result plots
    runner.run('fitdiag_%s' % ch, ['combine', '-M', 'FitDiagnostics', '--robustHesse', '1'] + rrange
               + ['-n', '.xsec_%s' % ch, ws])
    # NLL scans: total (nuisances floating), stat only (nuisances frozen at the best fit)
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
    if fit.get('impacts'):  # how much each nuisance moves r
        impacts = ['combineTool.py', '-M', 'Impacts', '-d', ws, '-m', '90']
        runner.run('impacts_initial_%s' % ch, impacts + ['--doInitialFit', '--robustFit', '1'])
        runner.run('impacts_fits_%s' % ch, impacts + ['--doFits', '--robustFit', '1'])
        runner.run('impacts_json_%s' % ch, impacts + ['-o', 'impacts_%s.json' % ch])
        runner.run('impacts_plot_%s' % ch, ['plotImpacts.py', '-i', 'impacts_%s.json' % ch, '-o', 'impacts_%s' % ch])
    if fit.get('postfit_shapes'):  # pre/post-fit templates with uncertainties, in the original binning
        runner.run('postfit_shapes_%s' % ch, ['PostFitShapesFromWorkspace', '-w', ws, '-d', card, '--output',
                   'postfit_shapes_%s.root' % ch, '-f', 'fitDiagnostics.xsec_%s.root:fit_s' % ch, '--postfit',
                   '--sampling'])
    return _singles(os.path.join(runner.cwd, SINGLES % ch))


def _singles(path):
    """r and its total 68% interval from the output of the `singles` fit: the best fit (quantileExpected -1) and
    the two bounds."""
    import ROOT as R
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


def _table(results, summary):
    """The results as text: r of every fit (singles), and the scan values of plot_summary with the ratio."""
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


def _check_tools(fits):
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


class _Runner:
    """Runs the commands one after the other in the step's directory, each with its own log in combine_logs/."""

    def __init__(self, ctx):
        self.ctx, self.cwd, self.count = ctx, ctx.stage_dir, 0

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
