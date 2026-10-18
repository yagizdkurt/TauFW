# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""ControlPlots: the public API for data/MC control plots drawn from control-histogram files (changelog §24, S4).

The Plotter fills nothing. The Histogrammer fills the histograms and writes them to a control-histogram file
(TauFW.Histogrammer.api.ControlHists, fillhists.py --hists --no-draw); this API draws such files with
Plotter/draw.py, run as a separate process, one run per file, with the arguments a user would type, and checks that
it wrote plots. draw.py runs in the request's output directory (outdir; the TauFW Framework gives
<run_dir>/stages/<id>/), or in Plotter/ if there is none:

    PlotsRequest ─▶ plan() ─▶ make()        = python3 draw.py FILE [-F] [-p] [-T TEXT]
                    CommandPlan  RunReport (one plots artifact per file)
    preflight(): what is missing in the environment (empty: ready)

Inputs:  control-histogram files (contract taufw.control_histograms, docs/contracts/control-histograms.md).
Outputs: <outdir>/plots/<era>/<variable>_<channel short>-<selection>-<era><tag>.png (and .pdf with -p), named by
         TauFW.Plotter.controlplots.plot_name like fillhists.py names its own plots, and one log file per command in
         the caller's log directory.

Like every module API, this one imports no other TauFW stage (only TauFW.Utilities and the Plotter itself), reads
and runs nothing when it is built, and needs no ROOT: draw.py imports ROOT in its own process.

Public API:
  ControlPlots(basedir, runner, python, find_module)
  plan, make, preflight         pipelines
  request(**fields)             a PlotsRequest
"""
import glob
import importlib.util
import os
import sys

from TauFW.Utilities.Process import Command, CommandPlan, ProcessRunner, RunReport, output_dir_problems
from TauFW.Plotter.api.types import PlotsRequest
from TauFW.Plotter.controlplots import plot_name

__all__ = ['ControlPlots']

SCRIPT = 'draw.py'  # the script this API runs, in Plotter/


class ControlPlots:
    """Control plots with Plotter/draw.py; see the module docstring.

    Pipelines:    plan(request)                     -> CommandPlan   changes nothing
                  make(request, logdir, progress)   -> RunReport     runs draw.py
                  preflight(request)                -> tuple of problems (empty: ready)
    Requests:     request(**fields)                 -> PlotsRequest
    Construction: ControlPlots(basedir, runner, python, find_module)
    """

    # =========================================================================
    # =============================== PIPELINES ===============================

    def plan(self, request):
        """One draw.py command per file, and the plot directories they fill."""
        cwd = self._cwd(request)
        commands, artifacts, names = [], [], {}
        for item in request.files:
            commands.append(self._command(request, item, cwd))
            artifacts.append({'kind': 'plots', 'era': item.era, 'config': item.config, 'channel': item.channel,
                              'directory': os.path.normpath(os.path.join(cwd, 'plots', item.era)), 'nfiles': 0})
            names.setdefault((item.channel, item.era, item.tag), []).append(item.path)
        notes = tuple("files %s give the same plot names: the later one overwrites the plots of the earlier (give "
                      "their setups different tags)" % (', '.join(paths)) for paths in names.values() if len(paths) > 1)
        return CommandPlan(cwd=cwd, commands=tuple(commands), artifacts=tuple(artifacts), notes=notes)

    def make(self, request, logdir, progress=None):
        """Run plan(); stops at the first failure (also a command after which no plot of its file is there). The
        artifacts count the plots of each file. Side effects: the output directory (made if needed) with the plots in
        plots/<era>/, the logs."""
        plan = self.plan(request)
        if request.outdir is not None:
            os.makedirs(plan.cwd, exist_ok=True)
        report = RunReport(results=self.runner.run_all(plan.commands, logdir, progress), total=len(plan.commands))
        if not report.ok:
            return report
        artifacts = tuple(dict(artifact, nfiles=len(glob.glob(os.path.join(command.cwd, command.expects[0]))))
                          for command, artifact in zip(plan.commands, plan.artifacts))
        return RunReport(results=report.results, total=report.total, artifacts=artifacts)

    def preflight(self, request):
        """What is missing to draw: CMSSW, ROOT, the files (not checked for a plan's placeholder '<run_dir>/...',
        a file that a stage of the same run is still to write), an output directory that is not empty."""
        problems = []
        if 'CMSSW_BASE' not in os.environ:
            problems.append("CMSSW_BASE is not set (run cmsenv first)")
        if not self.find_module('ROOT'):
            problems.append("python cannot import ROOT")
        problems.extend("control-histogram file %s not found" % (item.path) for item in request.files
                        if not item.path.startswith('<') and not os.path.isfile(self._file(request, item)))
        if request.outdir is not None:
            problems.extend(output_dir_problems(request.outdir))
        return tuple(problems)

    def request(self, **fields):
        """A PlotsRequest (unknown fields are an error), so callers need not import the records."""
        return PlotsRequest(**fields)

    # =========================================================================
    # ================================ HELPERS ================================

    def _command(self, request, item, cwd):
        """One draw.py run. With an output directory, the script and the file are given as absolute paths (draw.py
        runs there, not where the caller is)."""
        if request.outdir is None:
            argv = [self.python, SCRIPT, item.path]
        else:
            argv = [self.python, os.path.join(self.basedir, SCRIPT), self._file(request, item)]
        flags = (('-F', request.fraction), ('-p', request.pdf))
        argv += [flag for flag, wanted in flags if wanted]
        if request.text:
            argv += ['-T', request.text]
        return Command("controlplots %s %s" % (item.channel, item.era), tuple(argv), cwd,
                       expects=(_plot_glob(item),), timeout=request.timeout)

    def _cwd(self, request):
        """Where draw.py runs: the request's output directory as given (the Framework gives an absolute one, or the
        placeholder '<run_dir>/stages/<id>' in a plan), else Plotter/."""
        return os.path.normpath(request.outdir) if request.outdir is not None else self.basedir

    def _file(self, request, item):
        """The file as draw.py opens it: as given without an output directory (relative to Plotter/), else
        absolute (relative to the caller)."""
        if request.outdir is None:
            return os.path.join(self.basedir, item.path)
        return os.path.abspath(item.path) if not item.path.startswith('<') else item.path

    # =========================================================================
    # ============================= CONSTRUCTION ==============================

    def __init__(self, basedir=None, runner=None, python=None, find_module=None):
        """basedir:     the Plotter directory (default: $CMSSW_BASE/src/TauFW/Plotter, else this checkout)
        runner:      a TauFW.Utilities.Process.ProcessRunner (tests pass one with a fake execute)
        python:      the Python of draw.py (default: this one, sys.executable)
        find_module: module lookup (default: importlib)
        Construction reads nothing and runs nothing."""
        self.basedir = os.path.abspath(basedir or _default_basedir())
        self.runner = runner or ProcessRunner()
        self.python = python or sys.executable
        self.find_module = find_module or _module_exists

    def __repr__(self):
        return "<ControlPlots(basedir=%r)>" % (self.basedir)


# =============================================================================
# ================================ FILE NAMES =================================


def _plot_glob(item):
    """The png files of one file, relative to the working directory: plots/<era>/ and the name of plot_name (the
    rule of fillhists.py) with any variable and selection, ending in the file's tag."""
    pattern = plot_name(item.channel, '*', item.era, "plots/%s" % (item.era))
    return pattern.replace('$VAR', '*').replace('$TAG', item.tag) + '.png'


# =============================================================================
# ================================= DEFAULTS ==================================


def _module_exists(name):
    """True if module `name` can be imported. A module that is already imported counts without asking importlib:
    find_spec() raises ValueError for one whose __spec__ is None (CMSSW's ROOT once something imported it)."""
    if sys.modules.get(name) is not None:
        return True
    try:
        return importlib.util.find_spec(name) is not None
    except ImportError:  # e.g. the parent package of a dotted name is missing
        return False


def _default_basedir():
    """$CMSSW_BASE/src/TauFW/Plotter, or the Plotter directory of this checkout."""
    if 'CMSSW_BASE' in os.environ:
        return os.path.join(os.environ['CMSSW_BASE'], 'src', 'TauFW', 'Plotter')
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
