# Author: Yagizhan Dinckurt (October 2026)
"""TauESID: the public API of the combined tau energy scale (TES) + tau ID scale factor fit.

The fit is still done by the existing scripts. This API runs them, as separate processes in Fitter/, with exactly
the arguments of the shell scripts that analysts use, and checks what they produce:

    ShapesRequest ─▶ plan_shapes() ─▶ make_shapes()   = Fitter/run_inputs.sh       (TauES/createinputsTES.py)
                     CommandPlan      RunReport (shape artifacts)
    FitRequest    ─▶ plan_fit()    ─▶ fit()           = Fitter/run_workflow_zmm.sh (option 3: 2D scan of tes and
                     CommandPlan      RunReport (fit and correction artifacts)      tid_SF per DM and pt region)
    preflight_shapes(), preflight_fit(): what is missing in the environment (empty: ready)

Each command must exit with 0 AND write its expected outputs (see TauFW.Utilities.Process): the scripts call combine
through os.system and ignore its exit code, so a zero exit code alone proves nothing. A run stops at the first
command that fails.

Inputs:  pico tuples, found by the scripts through $PICODIR of the request's PicoProducer config (passed as
         $TAUFW_PICO_CONFIG; default PicoProducer/config/config.json); the YAML configs.
Outputs: written by the scripts inside Fitter/ (shared by all runs):
           input_pt_less_region/againstjet_<J>/againstelectron_<E>/      shapes
           output_pt_less_region/..., postfit_pt_less_region/...         datacards, fits, post-fit shapes
           plots_pt_less_region/, output_plots/, Measurements/, impacts/  plots
           tau_sf/                                                       correction files (ROOT, JSON)
         and one log file per command in the caller's log directory.

Public API:
  TauESID(basedir, runner, read_yaml, python, which, find_module)
  plan_shapes, make_shapes, preflight_shapes, plan_fit, fit, preflight_fit     pipelines
  shapes_request(**fields), fit_request(**fields)                            requests
  config_file(config)                                                        a config as an absolute path
  pico_config_source(request)                                                where $PICODIR is read from
"""
import glob
import importlib.util
import os
import posixpath
import shutil
import sys

from TauFW.Utilities.Process import Command, CommandPlan, ProcessRunner, RunReport
from TauFW.Fitter.api.types import ShapesRequest, FitRequest
from TauFW.Fitter.api.results import read_fit_values

__all__ = ['TauESID']


# =============================================================================
# ================================= CONSTANTS =================================


INPUTS = 'input_pt_less_region'      # shape tree; the later scripts hard-code these names
OUTPUTS = 'output_pt_less_region'    # datacards and fit results
POSTFIT = 'postfit_pt_less_region'   # post-fit shapes
PLOTS = 'plots_pt_less_region'       # scan plots
EXTRATAG = '_DeepTau'                # fixed in makecombinedfitTES_SF.py
FIT_TOOLS = ('combine', 'text2workspace.py', 'combineCards.py', 'PostFitShapesFromWorkspace')
IMPACT_TOOLS = ('combineTool.py', 'plotImpacts.py')


class TauESID:
    """The TES + tau ID fit of Fitter/; see the module docstring.

    Pipelines:    plan_shapes(request)                     -> CommandPlan   changes nothing
                  make_shapes(request, logdir, progress)   -> RunReport     runs createinputsTES.py
                  preflight_shapes(request)                -> tuple of problems (empty: ready)
                  plan_fit(request)                        -> CommandPlan   changes nothing
                  fit(request, logdir, progress)           -> RunReport     runs the fit workflow
                  preflight_fit(request, check_shapes)     -> tuple of problems (empty: ready)
    Requests:     shapes_request(**fields), fit_request(**fields)
    Commands:     _shape_commands, _point_commands, _summary_commands (one per step of the shell scripts)
    Construction: TauESID(basedir, runner, read_yaml, python, which, find_module)
    """

    # =========================================================================
    # =============================== PIPELINES ===============================

    def plan_shapes(self, request):
        """The createinputsTES.py commands, in the order of run_inputs.sh, and the shape files they make."""
        commands, artifacts, notes = [], [], []
        for era in request.eras:
            for jet_wp in request.jet_wps:
                for ele_wp in request.ele_wps:
                    for config in request.configs:
                        setup = self._setup(config, notes)
                        command, shapes = self._shape_command(request, era, jet_wp, ele_wp, config, setup)
                        commands.append(command)
                        artifacts.extend(shapes)
        return CommandPlan(cwd=self.basedir, commands=tuple(commands), artifacts=tuple(artifacts),
                           notes=tuple(dict.fromkeys(notes)))

    def make_shapes(self, request, logdir, progress=None):
        """Run plan_shapes(); stops at the first failure. Side effects: the shape files in Fitter/, the logs."""
        plan = self.plan_shapes(request)
        report = RunReport(results=self.runner.run_all(plan.commands, logdir, progress), total=len(plan.commands))
        return RunReport(results=report.results, total=report.total, artifacts=plan.artifacts if report.ok else ())

    def preflight_shapes(self, request):
        """What is missing to make the shapes: CMSSW, ROOT, the PicoProducer config, the config files."""
        problems = self._environment(root=True)
        source = self.pico_config_source(request)
        if not os.path.isfile(source):
            problems.append("no PicoProducer configuration %s: the scripts read $PICODIR from it" % (source))
        problems.extend(self._missing_configs(request.configs))
        return tuple(problems)

    def plan_fit(self, request):
        """The commands of run_workflow_zmm.sh for each point (and the summary once per era), with the fit and
        correction files they make."""
        notes = []
        setup = self._setup(request.config, notes)
        setup_mumu = self._setup(request.config_mumu, notes)
        commands, artifacts = [], []
        for era, jet_wp, ele_wp in request.points:
            commands.extend(self._point_commands(request, era, jet_wp, ele_wp, setup, setup_mumu))
            artifacts.append(self._fit_artifact(era, jet_wp, ele_wp))
        if 'summary' in request.steps:
            for era in request.eras:
                commands.extend(self._summary_commands(request, era))
                artifacts.append({'kind': 'corrections', 'era': era, 'path': self._path(_merged_json(era))})
        if 'fit' in request.steps and setup is not None and not _scan_regions(setup):
            notes.append("%s has no observables.m_vis.scanRegions: nothing would be fitted" % (request.config))
        return CommandPlan(cwd=self.basedir, commands=tuple(commands), artifacts=tuple(artifacts),
                           notes=tuple(dict.fromkeys(notes)))

    def fit(self, request, logdir, progress=None):
        """Run plan_fit(); stops at the first failure. The fit artifacts carry the fitted values read from the
        FitparameterValues files. Side effects: the outputs in Fitter/ (see the module docstring), the logs."""
        plan = self.plan_fit(request)
        report = RunReport(results=self.runner.run_all(plan.commands, logdir, progress), total=len(plan.commands))
        if not report.ok:
            return report
        setup = self._setup(request.config, [])
        artifacts = tuple(self._fit_results(artifact, setup) if artifact['kind'] == 'fit' else artifact
                          for artifact in plan.artifacts)
        return RunReport(results=report.results, total=report.total, artifacts=artifacts)

    def preflight_fit(self, request, check_shapes=True):
        """What is missing to fit: CMSSW, ROOT, the combine tools, CombineHarvester, the configs, and (if the
        fit step runs and check_shapes) the shapes of every point."""
        problems = self._environment(root=True)
        tools = FIT_TOOLS + (IMPACT_TOOLS if request.impacts and 'postfit' in request.steps else ())
        missing = [tool for tool in tools if not self.which(tool)]
        if missing:
            problems.append("not on PATH: %s (run cmsenv in the CMSSW area with combine)" % (', '.join(missing)))
        if 'fit' in request.steps and not self.find_module('CombineHarvester'):
            problems.append("python cannot import CombineHarvester (needed for the datacards)")
        problems.extend(self._missing_configs((request.config, request.config_mumu)))
        if 'fit' in request.steps and check_shapes:
            for era, jet_wp, ele_wp in request.points:
                indir = self._path(_wp_dir(INPUTS, jet_wp, ele_wp))
                if not glob.glob(os.path.join(indir, "*.inputs-%s-*.root" % (era))):
                    problems.append("no shapes for %s %s/%s in %s (run the histograms stage first)"
                                    % (era, jet_wp, ele_wp, indir))
        return tuple(problems)

    def shapes_request(self, **fields):
        """A ShapesRequest (unknown fields are an error), so callers need not import the records."""
        return ShapesRequest(**fields)

    def fit_request(self, **fields):
        """A FitRequest (unknown fields are an error), so callers need not import the records."""
        return FitRequest(**fields)

    def config_file(self, config):
        """A config file (relative to Fitter/, or absolute), as an absolute path."""
        return self._path(config)

    def pico_config_source(self, request=None):
        """The PicoProducer configuration that the scripts read $PICODIR from (through the Plotter samples): the
        request's, else the default."""
        if request is not None and request.pico_config:
            return request.pico_config
        return os.path.join(os.path.dirname(self.basedir), 'PicoProducer', 'config', 'config.json')

    # =========================================================================
    # =============================== COMMANDS ================================

    def _shape_command(self, request, era, jet_wp, ele_wp, config, setup):
        """One createinputsTES.py run (run_inputs.sh) and the shape files it makes, one per observable."""
        argv = [self.python, 'TauES/createinputsTES.py', '-y', era, '-c', config, '-j', jet_wp, '-e', ele_wp]
        if request.serial:
            argv.append('-s')
        files = _shape_files(setup, era, jet_wp, ele_wp) if setup is not None else []
        channel = setup.get('channel', config) if setup is not None else config
        shapes = [{'kind': 'shapes', 'path': self._path(path), 'era': era, 'channel': channel, 'config': config,
                   'jet_wp': jet_wp, 'ele_wp': ele_wp, 'observable': observable} for observable, path in files]
        command = Command("shapes %s %s %s %s" % (era, jet_wp, ele_wp, channel), tuple(argv), self.basedir,
                          expects=tuple(path for _, path in files), timeout=request.timeout,
                          env=_pico_env(request))
        return command, shapes

    def _point_commands(self, request, era, jet_wp, ele_wp, setup, setup_mumu):
        """The commands of run_workflow_zmm.sh for one working point pair."""
        indir = _wp_dir(INPUTS, jet_wp, ele_wp)
        outdir = _wp_dir(OUTPUTS, jet_wp, ele_wp)
        plotdir = _wp_dir(PLOTS, jet_wp, ele_wp)
        eradir = posixpath.join(outdir, era)
        mumu_card = posixpath.join(eradir, _mumu_card(setup_mumu, era))
        tag = (setup or {}).get('tag', '')
        regions = _scan_regions(setup or {})
        point = "%s %s %s" % (era, jet_wp, ele_wp)
        commands = []

        def add(step, label, argv, expects=()):
            if step in request.steps:
                commands.append(Command("%s %s %s" % (step, label, point), tuple([self.python] + argv),
                                        self.basedir, expects=tuple(expects), timeout=request.timeout,
                                        env=_pico_env(request)))

        add('fit', 'datacards mumu',
            ['TauES_ID/harvestDatacards_zmm.py', '-y', era, '-c', request.config_mumu, '-i', indir + '/',
             '-o', eradir + '/'],
            [mumu_card])
        add('fit', 'multidimfit',
            ['TauES_ID/makecombinedfitTES_SF.py', '-y', era, '-c', request.config, '-i', indir + '/',
             '-o', '3', '--mumu_datacard_file', mumu_card],
            [posixpath.join(eradir, "higgsCombine.mt_m_vis-%s%s%s-%s-13TeV.MultiDimFit.mH90.root"
                            % (region, tag, EXTRATAG, era)) for region in regions]
            + [posixpath.join(eradir, _values_file(tag, era, region)) for region in regions])
        add('postfit', 'fitdiagnostics',
            ['TauES_ID/makecombinedfitTES_SF_postfit.py', '-y', era, '-c', request.config, '--indir', outdir + '/',
             '-o', '3', '--mumu_input_file', mumu_card, '-cmm', request.config_mumu, '--jet_wp', jet_wp,
             '--ele_wp', ele_wp] + (['--impacts'] if request.impacts else []),
            [posixpath.join(_wp_dir(POSTFIT, jet_wp, ele_wp), era, "PostFitShape_%s_%s_*.root" % (era, tag))])
        add('plots', 'postfit plots',
            ['python/plot/runpostfit.py', '-c', request.config, '-j', jet_wp, '-e', ele_wp, '-y', era,
             '--include-cr'],
            ["output_plots/jet_%s_ele_%s/*" % (jet_wp, ele_wp)])
        add('plots', 'combined plots',
            ['pre_post_plot_combiner.py', '--scan_dir', posixpath.join(plotdir, era) + '/', '--jet_wp', jet_wp,
             '--ele_wp', ele_wp])
        add('plots', 'measurements',
            ['plot_measurements.py', '--jet_wp', jet_wp, '--ele_wp', ele_wp, '--year', era])
        for form in ('root', 'json'):
            add('corrections', form,
                ['createroot_TES.py', '-c', request.config, '-j', jet_wp, '-e', ele_wp, '-f', form, '-y', era],
                [_correction_glob(era, jet_wp, ele_wp, form)])
        return commands

    def _summary_commands(self, request, era):
        """The commands after the working point loop of run_workflow_zmm.sh (once per era)."""
        steps = [('scan grid', ['make_scan_grid.py', '--root', PLOTS], ()),
                 ('measurements grid', ['make_measurements_grid.py'], ()),
                 ('merge json', ['merge_tau_jsons.py', '--type', 'both', '-o', _merged_json(era), '-y', era],
                  (_merged_json(era),)),
                 ('nll profiles', ['plot1D_NLL_profiles.py', '--year', era], ()),
                 ('tes and id', ['make_tid_2025.py', '-y', era], ())]
        return [Command("summary %s %s" % (label, era), tuple([self.python] + argv), self.basedir,
                        expects=tuple(expects), timeout=request.timeout, env=_pico_env(request))
                for label, argv, expects in steps]

    # =========================================================================
    # ================================ RESULTS ================================

    def _fit_artifact(self, era, jet_wp, ele_wp):
        """The fit artifact of one point, before the fit: where its results go."""
        return {'kind': 'fit', 'era': era, 'jet_wp': jet_wp, 'ele_wp': ele_wp,
                'output_dir': self._path(posixpath.join(_wp_dir(OUTPUTS, jet_wp, ele_wp), era)),
                'postfit_dir': self._path(posixpath.join(_wp_dir(POSTFIT, jet_wp, ele_wp), era)),
                'values': [], 'corrections': []}

    def _fit_results(self, artifact, setup):
        """A fit artifact with the fitted values and the correction files found after the fit."""
        era, jet_wp, ele_wp = artifact['era'], artifact['jet_wp'], artifact['ele_wp']
        values = []
        for region in _scan_regions(setup or {}):
            path = os.path.join(artifact['output_dir'], _values_file((setup or {}).get('tag', ''), era, region))
            if os.path.isfile(path):
                with open(path) as stream:
                    values.extend(read_fit_values(stream.read(), region))
        corrections = sorted(path for form in ('root', 'json')
                             for path in glob.glob(self._path(_correction_glob(era, jet_wp, ele_wp, form))))
        return dict(artifact, values=values, corrections=corrections)

    # =========================================================================
    # ================================ HELPERS ================================

    def _setup(self, config, notes):
        """The YAML config (relative to Fitter/), or None with a note if it cannot be read."""
        path = self._path(config)
        if not os.path.isfile(path):
            notes.append("config %s not found in %s" % (config, self.basedir))
            return None
        try:
            return self.read_yaml(path) or {}
        except Exception as error:
            notes.append("cannot read config %s: %s" % (config, error))
            return None

    def _missing_configs(self, configs):
        return ["config %s not found in %s" % (config, self.basedir) for config in configs
                if not os.path.isfile(self._path(config))]

    def _environment(self, root=False):
        problems = []
        if 'CMSSW_BASE' not in os.environ:
            problems.append("CMSSW_BASE is not set (run cmsenv first)")
        if root and not self.find_module('ROOT'):
            problems.append("python cannot import ROOT")
        return problems

    def _path(self, relative):
        """An absolute path inside Fitter/."""
        return os.path.normpath(os.path.join(self.basedir, relative))

    # =========================================================================
    # ============================= CONSTRUCTION ==============================

    def __init__(self, basedir=None, runner=None, read_yaml=None, python=None, which=None, find_module=None):
        """basedir:     the Fitter directory (default: $CMSSW_BASE/src/TauFW/Fitter, else this checkout)
        runner:      a TauFW.Utilities.Process.ProcessRunner (tests pass one with a fake execute)
        read_yaml:   path -> dict (default: TauFW.Utilities.FIO.FileIO().read_yaml)
        python:      the Python of the scripts (default: this one, sys.executable)
        which, find_module: tool and module lookups (default: shutil.which, importlib)
        Construction reads nothing and runs nothing."""
        self.basedir = os.path.abspath(basedir or _default_basedir())
        self.runner = runner or ProcessRunner()
        self.read_yaml = read_yaml or _read_yaml
        self.python = python or sys.executable
        self.which = which or shutil.which
        self.find_module = find_module or (lambda name: importlib.util.find_spec(name) is not None)

    def __repr__(self):
        return "<TauESID(basedir=%r)>" % (self.basedir)


# =============================================================================
# ================================ FILE NAMES =================================


def _pico_env(request):
    """$TAUFW_PICO_CONFIG for the scripts, if the request names a PicoProducer config (read by getconfig())."""
    return (('TAUFW_PICO_CONFIG', request.pico_config),) if request.pico_config else ()


def _wp_dir(tree, jet_wp, ele_wp):
    return "%s/againstjet_%s/againstelectron_%s" % (tree, jet_wp, ele_wp)


def _shape_files(setup, era, jet_wp, ele_wp):
    """(observable, path) of the shape files createinputsTES.py writes for one config (createinputsTES.py:236)."""
    chshort = setup.get('channel', '').replace('tau', 't').replace('mu', 'm')
    tag = "13TeV" + setup.get('tag', '')
    files = []
    for observable, options in (setup.get('observables') or {}).items():
        name = ((options or {}).get('extra') or {}).get('filename', observable)
        files.append((observable, "%s/ztt_%s_tes_%s.inputs-%s-%s.root"
                      % (_wp_dir(INPUTS, jet_wp, ele_wp), chshort, name, era, tag)))
    return files


def _scan_regions(setup):
    return list(((setup.get('observables') or {}).get('m_vis') or {}).get('scanRegions') or [])


def _mumu_card(setup_mumu, era):
    """The mumu datacard of harvestDatacards_zmm.py: ztt_mm_<obs>-<region><tag>-<era>-13TeV.txt."""
    setup_mumu = setup_mumu or {}
    observables = setup_mumu.get('observables') or {'m_vis': {}}
    observable = next(iter(observables))
    regions = (observables[observable] or {}).get('fitRegions') or ['baseline']
    return "ztt_mm_%s-%s%s-%s-13TeV.txt" % (observable, regions[0], setup_mumu.get('tag', '_mumu'), era)


def _values_file(tag, era, region):
    return "FitparameterValues_%s%s_%s-13TeV_%s.txt" % (tag, EXTRATAG, era, region)


def _correction_glob(era, jet_wp, ele_wp, form):
    return "tau_sf/*_%s_VSjet%s_VSele%s.%s" % (era, jet_wp, ele_wp, form)


def _merged_json(era):
    return "tau_sf/TauCorrections_%s.json" % (era)


# =============================================================================
# ================================= DEFAULTS ==================================


def _default_basedir():
    """$CMSSW_BASE/src/TauFW/Fitter, or the Fitter directory of this checkout (as PicoProducer's basedir)."""
    if 'CMSSW_BASE' in os.environ:
        return os.path.join(os.environ['CMSSW_BASE'], 'src', 'TauFW', 'Fitter')
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))


def _read_yaml(path):
    from TauFW.Utilities.FIO import FileIO
    return FileIO().read_yaml(path)
