# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""ControlPlots: the public API for data/MC control plots of pico tuples.

The plots are still made by Histogrammer/fillhists.py (Plotter/plot.py until CL §24: it fills the histograms and,
until the clean Plotter draws them, also draws them). This API runs it as a separate process, one run per
(config, era), with the arguments a user would type, and checks that it wrote plots. fillhists.py runs in the
request's output directory (outdir; the TauFW Framework gives <run_dir>/stages/<id>/), or in Histogrammer/ if there
is none:

    PlotsRequest ─▶ plan() ─▶ make()        = python3 fillhists.py -y ERA -c CONFIG [-V ...] [-S ...] [options]
                    CommandPlan  RunReport (one plots artifact per config and era)
    preflight(): what is missing in the environment (empty: ready)
    sample_names(), samples_problems(), sample_file_problems(): the sample model files (no ROOT; also used by the
    Framework for the histograms stage and to compare with what production makes)

Inputs:  pico tuples in the request's tuple pattern (--tuples), or else found by fillhists.py through $PICODIR
         of the request's PicoProducer config (passed to fillhists.py as $TAUFW_PICO_CONFIG; default
         PicoProducer/config/config.json); the channel setups
         Configs/Plotter/setups/setup_<channel>.yml (or any .yml, relative to Histogrammer/ or absolute); the sample model
         files (--samples; without them the tables of config/samples_v15.py).
Outputs: <outdir>/plots/<era>/<variable>_<channel>-<selection>-<era><tag>.png, where <tag> is the setup's tag
         plus request.tag (without outdir: Histogrammer/plots/<era>/, shared by all runs; pdf on request), and one log
         file per command in the caller's log directory.

Public API:
  ControlPlots(basedir, runner, read_yaml, python, find_module)
  plan, make, preflight         pipelines
  request(**fields)             a PlotsRequest
  config_file(config)           the setup file of a channel name or .yml config
  pico_config_source(request)   where $PICODIR is read from (a request without tuples)
  sample_names(files, era, channel)                 (MC sample names, data pattern) of a channel
  samples_problems(files, eras)                     unreadable files, an era without exactly one file
  sample_file_problems(files, eras, channels, tuples)   tuple files of the requested samples that are missing
"""
import glob
import importlib.util
import os
import sys

from TauFW.Utilities.Process import (Command, CommandPlan, ProcessRunner, RunReport, output_dir_problems,
                                     tuple_pattern_problems)
from TauFW.Histogrammer.api.types import PlotsRequest
from TauFW.Histogrammer.sample import model as sample_model

__all__ = ['ControlPlots']

SCRIPT = 'fillhists.py'                    # the script this API runs (Plotter/plot.py until CL §24)
SETUPS = ('Configs', 'Plotter', 'setups')  # the channel setups, next to Histogrammer/ (config templates, Configs/README.md)


class ControlPlots:
    """Control plots with Histogrammer/fillhists.py; see the module docstring.

    Pipelines:    plan(request)                     -> CommandPlan   changes nothing
                  make(request, logdir, progress)   -> RunReport     runs fillhists.py
                  preflight(request)                -> tuple of problems (empty: ready)
    Requests:     request(**fields)                 -> PlotsRequest
    Construction: ControlPlots(basedir, runner, read_yaml, python, find_module)
    """

    # =========================================================================
    # =============================== PIPELINES ===============================

    def plan(self, request):
        """One fillhists.py command per config and era, and the plot directories they fill."""
        commands, artifacts, notes = [], [], []
        cwd = self._cwd(request)
        names = {}  # (channel, tag) -> configs: the same file names
        for config in request.configs:
            setup_file = _setup_file(config)
            setup = self._setup(setup_file, notes)
            channel = (setup or {}).get('channel', config)
            tag = str((setup or {}).get('tag') or "") + request.tag  # the script's file tag (BUGS L08)
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
        channel setups, the sample model files and (with both a tuple pattern and sample files) the tuple files of
        the requested samples."""
        problems = []
        if 'CMSSW_BASE' not in os.environ:
            problems.append("CMSSW_BASE is not set (run cmsenv first)")
        if not self.find_module('ROOT'):
            problems.append("python cannot import ROOT")
        source = None if request.tuples else self.pico_config_source(request)
        if request.tuples:
            problems.extend(tuple_pattern_problems(request.tuples))
        elif not os.path.isfile(source):
            problems.append("no PicoProducer configuration %s: %s reads $PICODIR from it" % (source, SCRIPT))
        problems.extend("channel setup %s not found" % (self.config_file(config))
                        for config in request.configs if not os.path.isfile(self.config_file(config)))
        if request.outdir is not None:
            problems.extend(output_dir_problems(request.outdir, source, tuples=request.tuples))
        if request.samples:
            sample_problems = self.samples_problems(request.samples, request.eras)
            problems.extend(sample_problems)
            if request.tuples and not sample_problems and '<' not in request.tuples:  # not a plan's placeholder
                channels = [artifact['channel'] for artifact in self.plan(request).artifacts]
                problems.extend(self.sample_file_problems(request.samples, request.eras, channels, request.tuples))
        return tuple(problems)

    # =========================================================================
    # ================================ SAMPLES ================================

    def sample_names(self, files, era, channel):
        """(MC sample names, data dataset pattern or None) that a channel reads in an era, from the sample model
        files (TauFW.Histogrammer.sample.model; raises SampleModelError). Reads only the YAML files."""
        return sample_model.sample_names(sample_model.pick(files, era), channel)

    def samples_problems(self, files, eras):
        """The problems of sample model files for these eras: a file that cannot be read, an era with no file or with
        more than one (empty: none)."""
        problems = []
        for path in files:
            if not os.path.isfile(path):
                problems.append("sample file %s not found" % (path))
                continue
            try:
                sample_model.load_sample_model(path)
            except sample_model.SampleModelError as error:
                problems.append(str(error))
        if problems:
            return tuple(problems)
        for era in eras:
            try:
                sample_model.pick(files, era)
            except sample_model.SampleModelError as error:
                problems.append(str(error))
        return tuple(problems)

    def sample_file_problems(self, files, eras, channels, tuples, maxshow=5):
        """The requested samples without a tuple file in the tuple pattern (with $ERA, $GROUP): an MC sample's
        <dir>/<sample>_<channel>.root, or no file for the data pattern; the names as the Histogrammer builds them."""
        missing = []
        for era in eras:
            for channel in dict.fromkeys(channels):
                _, data = self.sample_names(files, era, channel)
                for row in sample_model.pick(files, era).mc:
                    path = _tuple_file(tuples, era, row['group'], row['name'], channel)
                    if not os.path.isfile(path):
                        missing.append(path)
                if data and not glob.glob(_tuple_file(tuples, era, 'Data', data, channel)):
                    missing.append(_tuple_file(tuples, era, 'Data', data, channel))
        if not missing:
            return ()
        shown = ", ".join(missing[:maxshow]) + (", ..." if len(missing) > maxshow else "")
        return ("%d tuple file(s) of the requested samples not found: %s" % (len(missing), shown),)

    def request(self, **fields):
        """A PlotsRequest (unknown fields are an error), so callers need not import the records."""
        return PlotsRequest(**fields)

    def config_file(self, config):
        """The channel setup file of a config (a channel name or a .yml file), as an absolute path."""
        return self._path(_setup_file(config))

    def pico_config_source(self, request=None):
        """The PicoProducer configuration that fillhists.py reads $PICODIR from: the request's, else the default."""
        if request is not None and request.pico_config:
            return request.pico_config
        return os.path.join(os.path.dirname(self.basedir), 'PicoProducer', 'config', 'config.json')

    # =========================================================================
    # ================================ HELPERS ================================

    def _command(self, request, config, era, channel, tag, cwd):
        """One fillhists.py run. With an output directory, the script and the setup are given as absolute paths (a
        .yml setup is opened relative to the script's working directory)."""
        if request.outdir is None:
            argv = [self.python, SCRIPT, '-y', era, '-c', config]
        else:
            argv = [self.python, self._path(SCRIPT), '-y', era, '-c', self.config_file(config)]
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
        if request.samples:
            argv += ['--samples'] + [path if request.outdir is None else os.path.abspath(path)
                                     for path in request.samples]
        return Command("plots %s %s" % (channel, era), tuple(argv), cwd,
                       expects=("plots/%s/%s" % (era, _plot_glob(channel, era, tag)),),
                       timeout=request.timeout, env=_pico_env(request))

    def _cwd(self, request):
        """Where fillhists.py runs: the request's output directory as given (the Framework gives an absolute one, or the
        placeholder '<run_dir>/stages/<id>' in a plan), else Histogrammer/."""
        return os.path.normpath(request.outdir) if request.outdir is not None else self.basedir

    def _setup(self, setup_file, notes):
        path = self._path(setup_file)
        if not os.path.isfile(path):
            notes.append("channel setup %s not found" % (path))
            return None
        try:
            return self.read_yaml(path) or {}
        except Exception as error:
            notes.append("cannot read channel setup %s: %s" % (setup_file, error))
            return None

    def _path(self, relative):
        """An absolute path inside Histogrammer/."""
        return os.path.normpath(os.path.join(self.basedir, relative))

    # =========================================================================
    # ============================= CONSTRUCTION ==============================

    def __init__(self, basedir=None, runner=None, read_yaml=None, python=None, find_module=None):
        """basedir:     the Histogrammer directory (default: $CMSSW_BASE/src/TauFW/Histogrammer, else this checkout)
        runner:      a TauFW.Utilities.Process.ProcessRunner (tests pass one with a fake execute)
        read_yaml:   path -> dict (default: TauFW.Utilities.FIO.FileIO().read_yaml)
        python:      the Python of fillhists.py (default: this one, sys.executable)
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
    """fillhists.py's rule: a name without .yml is a channel, Configs/Plotter/setups/setup_<channel>.yml (relative to
    Histogrammer/; the setups are config templates since CL §22)."""
    return config if config.endswith('.yml') else os.path.join(os.pardir, *SETUPS, "setup_%s.yml" % (config))


def _pico_env(request):
    """$TAUFW_PICO_CONFIG for fillhists.py, if the request names a PicoProducer config (read by getconfig()) and no
    tuple pattern; absolute with an output directory, since the script then runs elsewhere than the caller."""
    if not request.pico_config or request.tuples:
        return ()
    return (('TAUFW_PICO_CONFIG', request.pico_config if request.outdir is None else
             os.path.abspath(request.pico_config)),)


def _tuple_file(tuples, era, group, sample, channel):
    """The tuple file the Histogrammer reads for a sample: $PICODIR/$SAMPLE_$CHANNEL$TAG.root with $PICODIR the tuple
    pattern (getsampleset; no tag), the keys replaced as plain text."""
    directory = tuples.replace('$ERA', era).replace('$GROUP', group)
    return os.path.join(directory, "%s_%s.root" % (sample, channel))


def _plot_glob(channel, era, tag):
    """The png files of one channel and era: <var>_<channel short>-<selection>-<era><tag>.png (fillhists.py), where
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
    """$CMSSW_BASE/src/TauFW/Histogrammer, or the Histogrammer directory of this checkout."""
    if 'CMSSW_BASE' in os.environ:
        return os.path.join(os.environ['CMSSW_BASE'], 'src', 'TauFW', 'Histogrammer')
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))


def _read_yaml(path):
    from TauFW.Utilities.FIO import FileIO
    return FileIO().read_yaml(path)
