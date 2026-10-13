# Author: Yagizhan Dinckurt (October 2026)
"""ControlPlots: the public API for data/MC control plots of pico tuples.

The plots are still made by Plotter/plot.py. This API runs it as a separate process in Plotter/, one run per
(config, era), with the arguments a user would type, and checks that it wrote plots:

    PlotsRequest ─▶ plan() ─▶ make()        = python3 plot.py -y ERA -c CONFIG [-V ...] [-S ...] [options]
                    CommandPlan  RunReport (one plots artifact per config and era)
    preflight(): what is missing in the environment (empty: ready)

Inputs:  pico tuples, found by plot.py through $PICODIR of PicoProducer/config/config.json; the channel setups
         Plotter/config/setup_<channel>.yml (or any .yml relative to Plotter/).
Outputs: Plotter/plots/<era>/<variable>_<channel>-<selection>-<era><tag>.png (shared by all runs; pdf on request)
         and one log file per command in the caller's log directory.

Public API:
  ControlPlots(basedir, runner, read_yaml, python, find_module)
  plan, make, preflight         pipelines
  request(**fields)             a PlotsRequest
  pico_config_source            where $PICODIR is read from
"""
import glob
import importlib.util
import os
import sys

from TauFW.Utilities.Process import Command, ProcessRunner
from TauFW.Plotter.api.types import PlotsRequest, CommandPlan, RunReport

__all__ = ['ControlPlots']


class ControlPlots:
    """Control plots with Plotter/plot.py; see the module docstring.

    Pipelines:    plan(request)                     -> CommandPlan   changes nothing
                  make(request, logdir, progress)   -> RunReport     runs plot.py
                  preflight(request)                -> tuple of problems (empty: ready)
    Requests:     request(**fields)                 -> PlotsRequest
    Construction: ControlPlots(basedir, runner, read_yaml, python, find_module)
    """

    # =========================================================================
    # =============================== PIPELINES ===============================

    def plan(self, request):
        """One plot.py command per config and era, and the plot directories they fill."""
        commands, artifacts, notes = [], [], []
        for config in request.configs:
            setup_file = _setup_file(config)
            setup = self._setup(setup_file, notes)
            channel = (setup or {}).get('channel', config)
            for era in request.eras:
                commands.append(self._command(request, config, era, channel))
                artifacts.append({'kind': 'plots', 'era': era, 'config': config, 'channel': channel,
                                  'directory': self._path("plots/%s" % (era)), 'nfiles': 0})
        return CommandPlan(cwd=self.basedir, commands=tuple(commands), artifacts=tuple(artifacts),
                           notes=tuple(dict.fromkeys(notes)))

    def make(self, request, logdir, progress=None):
        """Run plan(); stops at the first failure. The artifacts count the plots of each config and era.
        Side effects: the plots in Plotter/plots/<era>/, the logs."""
        plan = self.plan(request)
        report = RunReport(results=self.runner.run_all(plan.commands, logdir, progress), total=len(plan.commands))
        if not report.ok:
            return report
        artifacts = tuple(dict(artifact, nfiles=len(glob.glob(os.path.join(
            artifact['directory'], _plot_glob(artifact['channel'], artifact['era'], request.tag)))))
            for artifact in plan.artifacts)
        return RunReport(results=report.results, total=report.total, artifacts=artifacts)

    def preflight(self, request):
        """What is missing to plot: CMSSW, ROOT, the PicoProducer config, the channel setups."""
        problems = []
        if 'CMSSW_BASE' not in os.environ:
            problems.append("CMSSW_BASE is not set (run cmsenv first)")
        if not self.find_module('ROOT'):
            problems.append("python cannot import ROOT")
        if not os.path.isfile(self.pico_config_source):
            problems.append("no PicoProducer configuration %s: plot.py reads $PICODIR from it"
                            % (self.pico_config_source))
        problems.extend("channel setup %s not found in %s" % (_setup_file(config), self.basedir)
                        for config in request.configs if not os.path.isfile(self._path(_setup_file(config))))
        return tuple(problems)

    def request(self, **fields):
        """A PlotsRequest (unknown fields are an error), so callers need not import the records."""
        return PlotsRequest(**fields)

    @property
    def pico_config_source(self):
        """The PicoProducer configuration that plot.py reads $PICODIR from."""
        return os.path.join(os.path.dirname(self.basedir), 'PicoProducer', 'config', 'config.json')

    # =========================================================================
    # ================================ HELPERS ================================

    def _command(self, request, config, era, channel):
        argv = [self.python, 'plot.py', '-y', era, '-c', config]
        if request.variables:
            argv += ['-V'] + list(request.variables)
        if request.selections:
            argv += ['-S'] + list(request.selections)
        flags = (('-s', request.serial), ('-F', request.fraction), ('-p', request.pdf), ('-r', request.notauidsf))
        argv += [flag for flag, wanted in flags if wanted]
        if request.tag:
            argv += ['-t', request.tag]
        if request.text:
            argv += ['-T', request.text]
        return Command("plots %s %s" % (channel, era), tuple(argv), self.basedir,
                       expects=("plots/%s/%s" % (era, _plot_glob(channel, era, request.tag)),),
                       timeout=request.timeout)

    def _setup(self, setup_file, notes):
        path = self._path(setup_file)
        if not os.path.isfile(path):
            notes.append("channel setup %s not found in %s" % (setup_file, self.basedir))
            return None
        try:
            return self.read_yaml(path) or {}
        except Exception as error:
            notes.append("cannot read channel setup %s: %s" % (setup_file, error))
            return None

    def _path(self, relative):
        """An absolute path inside Plotter/."""
        return os.path.normpath(os.path.join(self.basedir, relative))

    # =========================================================================
    # ============================= CONSTRUCTION ==============================

    def __init__(self, basedir=None, runner=None, read_yaml=None, python=None, find_module=None):
        """basedir:     the Plotter directory (default: $CMSSW_BASE/src/TauFW/Plotter, else this checkout)
        runner:      a TauFW.Utilities.Process.ProcessRunner (tests pass one with a fake execute)
        read_yaml:   path -> dict (default: TauFW.Utilities.FIO.FileIO().read_yaml)
        python:      the Python of plot.py (default: this one, sys.executable)
        find_module: module lookup (default: importlib)
        Construction reads nothing and runs nothing."""
        self.basedir = os.path.abspath(basedir or _default_basedir())
        self.runner = runner or ProcessRunner()
        self.read_yaml = read_yaml or _read_yaml
        self.python = python or sys.executable
        self.find_module = find_module or (lambda name: importlib.util.find_spec(name) is not None)

    def __repr__(self):
        return "<ControlPlots(basedir=%r)>" % (self.basedir)


# =============================================================================
# ================================ FILE NAMES =================================


def _setup_file(config):
    """plot.py's rule: a name without .yml is a channel, config/setup_<channel>.yml."""
    return config if config.endswith('.yml') else "config/setup_%s.yml" % (config)


def _plot_glob(channel, era, tag):
    """The png files of one channel and era: <var>_<channel short>-<selection>-<era><tag>.png (plot.py)."""
    return "*_%s-*-%s%s.png" % (channel.replace('mu', 'm').replace('tau', 't'), era, tag)


# =============================================================================
# ================================= DEFAULTS ==================================


def _default_basedir():
    """$CMSSW_BASE/src/TauFW/Plotter, or the Plotter directory of this checkout."""
    if 'CMSSW_BASE' in os.environ:
        return os.path.join(os.environ['CMSSW_BASE'], 'src', 'TauFW', 'Plotter')
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))


def _read_yaml(path):
    from TauFW.Utilities.FIO import FileIO
    return FileIO().read_yaml(path)
