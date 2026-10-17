# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""ControlPlots: the public API for data/MC control plots of pico tuples.

The plots are still made by Plotter/plot.py. This API runs it as a separate process, one run per (config, era),
with the arguments a user would type, and checks that it wrote plots. plot.py runs in the request's output
directory (outdir; the TauFW Framework gives <run_dir>/stages/<id>/), or in Plotter/ if there is none:

    PlotsRequest ─▶ plan() ─▶ make()        = python3 plot.py -y ERA -c CONFIG [-V ...] [-S ...] [options]
                    CommandPlan  RunReport (one plots artifact per config and era)
    preflight(): what is missing in the environment (empty: ready)

Inputs:  pico tuples in the request's tuple pattern (plot.py --tuples), or else found by plot.py through $PICODIR
         of the request's PicoProducer config (passed to plot.py as $TAUFW_PICO_CONFIG; default
         PicoProducer/config/config.json); the channel setups
         Plotter/config/setup_<channel>.yml (or any .yml, relative to Plotter/ or absolute).
Outputs: <outdir>/plots/<era>/<variable>_<channel>-<selection>-<era><tag>.png, where <tag> is the setup's tag
         plus request.tag (without outdir: Plotter/plots/<era>/, shared by all runs; pdf on request), and one log
         file per command in the caller's log directory.

Public API:
  ControlPlots(basedir, runner, read_yaml, python, find_module)
  plan, make, preflight         pipelines
  request(**fields)             a PlotsRequest
  config_file(config)           the setup file of a channel name or .yml config
  pico_config_source(request)   where $PICODIR is read from (a request without tuples)
"""
import glob
import importlib.util
import os
import sys

from TauFW.Utilities.Process import (Command, CommandPlan, ProcessRunner, RunReport, output_dir_problems,
                                     tuple_pattern_problems)
from TauFW.Plotter.api.types import PlotsRequest

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
        cwd = self._cwd(request)
        names = {}  # (channel, tag) -> configs: the same file names
        for config in request.configs:
            setup_file = _setup_file(config)
            setup = self._setup(setup_file, notes)
            channel = (setup or {}).get('channel', config)
            tag = str((setup or {}).get('tag') or "") + request.tag  # plot.py's file tag (BUGS L08)
            names.setdefault((channel, tag), []).append(config)
            for era in request.eras:
                commands.append(self._command(request, config, era, channel, tag, cwd))
                artifacts.append({'kind': 'plots', 'era': era, 'config': config, 'channel': channel,
                                  'directory': os.path.normpath(os.path.join(cwd, 'plots', era)), 'nfiles': 0})
        notes.extend("configs %s write the same file names: the later run overwrites the plots of the earlier "
                     "(BUGS L10; give one of them a tag)" % (', '.join(same)) for same in names.values() if len(same) > 1)
        return CommandPlan(cwd=cwd, commands=tuple(commands), artifacts=tuple(artifacts),
                           notes=tuple(dict.fromkeys(notes)))

    def make(self, request, logdir, progress=None):
        """Run plan(); stops at the first failure. The artifacts count the plots of each config and era.
        Side effects: the output directory (made if needed) with the plots in plots/<era>/, the logs."""
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
        """What is missing to plot: CMSSW, ROOT, the tuple pattern's keys or else the PicoProducer config, the
        channel setups."""
        problems = []
        if 'CMSSW_BASE' not in os.environ:
            problems.append("CMSSW_BASE is not set (run cmsenv first)")
        if not self.find_module('ROOT'):
            problems.append("python cannot import ROOT")
        source = None if request.tuples else self.pico_config_source(request)
        if request.tuples:
            problems.extend(tuple_pattern_problems(request.tuples))
        elif not os.path.isfile(source):
            problems.append("no PicoProducer configuration %s: plot.py reads $PICODIR from it" % (source))
        problems.extend("channel setup %s not found in %s" % (_setup_file(config), self.basedir)
                        for config in request.configs if not os.path.isfile(self._path(_setup_file(config))))
        if request.outdir is not None:
            problems.extend(output_dir_problems(request.outdir, source, tuples=request.tuples))
        return tuple(problems)

    def request(self, **fields):
        """A PlotsRequest (unknown fields are an error), so callers need not import the records."""
        return PlotsRequest(**fields)

    def config_file(self, config):
        """The channel setup file of a config (a channel name or a .yml file), as an absolute path."""
        return self._path(_setup_file(config))

    def pico_config_source(self, request=None):
        """The PicoProducer configuration that plot.py reads $PICODIR from: the request's, else the default."""
        if request is not None and request.pico_config:
            return request.pico_config
        return os.path.join(os.path.dirname(self.basedir), 'PicoProducer', 'config', 'config.json')

    # =========================================================================
    # ================================ HELPERS ================================

    def _command(self, request, config, era, channel, tag, cwd):
        """One plot.py run. With an output directory, plot.py and the setup are given as absolute paths (plot.py
        opens config/setup_<channel>.yml relative to its working directory)."""
        if request.outdir is None:
            argv = [self.python, 'plot.py', '-y', era, '-c', config]
        else:
            argv = [self.python, self._path('plot.py'), '-y', era, '-c', self.config_file(config)]
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
        if request.tuples:
            argv += ['--tuples', request.tuples]
        return Command("plots %s %s" % (channel, era), tuple(argv), cwd,
                       expects=("plots/%s/%s" % (era, _plot_glob(channel, era, tag)),),
                       timeout=request.timeout, env=_pico_env(request))

    def _cwd(self, request):
        """Where plot.py runs: the request's output directory as given (the Framework gives an absolute one, or the
        placeholder '<run_dir>/stages/<id>' in a plan), else Plotter/."""
        return os.path.normpath(request.outdir) if request.outdir is not None else self.basedir

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
        self.find_module = find_module or _module_exists

    def __repr__(self):
        return "<ControlPlots(basedir=%r)>" % (self.basedir)


# =============================================================================
# ================================ FILE NAMES =================================


def _setup_file(config):
    """plot.py's rule: a name without .yml is a channel, config/setup_<channel>.yml."""
    return config if config.endswith('.yml') else "config/setup_%s.yml" % (config)


def _pico_env(request):
    """$TAUFW_PICO_CONFIG for plot.py, if the request names a PicoProducer config (read by getconfig()) and no
    tuple pattern; absolute with an output directory, since plot.py then runs elsewhere than the caller."""
    if not request.pico_config or request.tuples:
        return ()
    return (('TAUFW_PICO_CONFIG', request.pico_config if request.outdir is None else
             os.path.abspath(request.pico_config)),)


def _plot_glob(channel, era, tag):
    """The png files of one channel and era: <var>_<channel short>-<selection>-<era><tag>.png (plot.py), where
    tag is the setup's tag plus -t."""
    return "*_%s-*-%s%s.png" % (channel.replace('mu', 'm').replace('tau', 't'), era, tag)


# =============================================================================
# ================================= DEFAULTS ==================================


def _module_exists(name):
    """True if module `name` can be imported. A module that is already imported counts without asking importlib:
    find_spec() raises ValueError for one whose __spec__ is None, e.g. CMSSW's ROOT once PicoProducer imported it."""
    if sys.modules.get(name) is not None:  # BUGS L13 (None in sys.modules: an import that is blocked)
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


def _read_yaml(path):
    from TauFW.Utilities.FIO import FileIO
    return FileIO().read_yaml(path)
