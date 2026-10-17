# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""TauESID: the public API of the combined tau energy scale (TES) + tau ID scale factor fit.

The fit is still done by the existing scripts. This API runs them as separate processes, with the arguments of the
shell scripts that analysts use, and checks what they produce. Without an output directory (request.outdir) they
run in Fitter/ with exactly the arguments of the shell scripts. With one (the TauFW Framework gives
<run_dir>/stages/<id>/) they run there, the fit in <outdir>/<era>/: the scripts and configs are then given as
absolute paths, the shapes come from request.shapes_dirs, and the few options listed in
docs/Refactor-2025/scripts_arg_changes.md keep every output inside the output directory:

    ShapesRequest ─▶ plan_shapes() ─▶ make_shapes()   = Fitter/run_inputs.sh       (TauES/createinputsTES.py)
                     CommandPlan      RunReport (shape artifacts)
    FitRequest    ─▶ plan_fit()    ─▶ fit()           = Fitter/run_workflow_zmm.sh (option 3: 2D scan of tes and
                     CommandPlan      RunReport (fit and correction artifacts)      tid_SF per DM and pt region)
    preflight_shapes(), preflight_fit(): what is missing in the environment (empty: ready)

Each command must exit with 0 AND write its expected outputs (see TauFW.Utilities.Process): the scripts call combine
through os.system and ignore its exit code, so a zero exit code alone proves nothing. A run stops at the first
command that fails.

Inputs:  pico tuples in the shapes request's tuple pattern (createinputsTES.py --tuples), or else found by the
         scripts through $PICODIR of the request's PicoProducer config (passed as $TAUFW_PICO_CONFIG; default
         PicoProducer/config/config.json); the YAML configs.
Outputs: written by the scripts in the output directory (shapes) or <outdir>/<era>/ (fit); without one in Fitter/
         (shared by all runs):
           input_pt_less_region/againstjet_<J>/againstelectron_<E>/      shapes
           output_pt_less_region/..., postfit_pt_less_region/...         datacards, fits, post-fit shapes
           plots_pt_less_region/, output_plots/, Measurements/, impacts/  plots
           tau_sf/, data/tau/                                            correction files (ROOT, JSON)
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

from TauFW.Utilities.Process import (Command, CommandPlan, ProcessRunner, RunReport, output_dir_problems,
                                     tuple_pattern_problems)
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
        cwd = self._cwd(request)
        for era in request.eras:
            for jet_wp in request.jet_wps:
                for ele_wp in request.ele_wps:
                    for config in request.configs:
                        setup = self._setup(config, notes)
                        command, shapes = self._shape_command(request, era, jet_wp, ele_wp, config, setup, cwd)
                        commands.append(command)
                        artifacts.extend(shapes)
        return CommandPlan(cwd=cwd, commands=tuple(commands), artifacts=tuple(artifacts),
                           notes=tuple(dict.fromkeys(notes)))

    def make_shapes(self, request, logdir, progress=None):
        """Run plan_shapes(); stops at the first failure. Side effects: the shape files in the output directory
        (made if needed) or Fitter/, the logs."""
        plan = self.plan_shapes(request)
        if request.outdir is not None:
            os.makedirs(plan.cwd, exist_ok=True)
        report = RunReport(results=self.runner.run_all(plan.commands, logdir, progress), total=len(plan.commands))
        return RunReport(results=report.results, total=report.total, artifacts=plan.artifacts if report.ok else ())

    def preflight_shapes(self, request):
        """What is missing to make the shapes: CMSSW, ROOT, the tuple pattern's keys or else the PicoProducer
        config, the config files, the sample model files (only that they exist: their content is the Plotter's,
        which the Framework checks through the Plotter API)."""
        problems = self._environment(root=True)
        source = None if request.tuples else self.pico_config_source(request)
        if request.tuples:
            problems.extend(tuple_pattern_problems(request.tuples))
        elif not os.path.isfile(source):
            problems.append("no PicoProducer configuration %s: the scripts read $PICODIR from it" % (source))
        problems.extend(self._missing_configs(request.configs))
        problems.extend("sample file %s not found" % (path) for path in request.samples if not os.path.isfile(path))
        if request.outdir is not None:
            problems.extend(output_dir_problems(request.outdir, source, tuples=request.tuples))
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
            artifacts.append(self._fit_artifact(request, era, jet_wp, ele_wp))
        if 'summary' in request.steps:
            for era in request.eras:
                commands.extend(self._summary_commands(request, era))
                artifacts.append({'kind': 'corrections', 'era': era, 'path': self._era_path(request, era,
                                                                                          _merged_json(era))})
                artifacts.append({'kind': 'corrections', 'era': era, 'combined': True,
                                  'path': self._era_path(request, era, _combined_json(era))})
        if 'fit' in request.steps and setup is not None and not _scan_regions(setup):
            notes.append("%s has no observables.m_vis.scanRegions: nothing would be fitted" % (request.config))
        return CommandPlan(cwd=self._cwd(request), commands=tuple(commands), artifacts=tuple(artifacts),
                           notes=tuple(dict.fromkeys(notes)))

    def fit(self, request, logdir, progress=None):
        """Run plan_fit(); stops at the first failure. The fit artifacts carry the fitted values read from the
        FitparameterValues files. Side effects: the outputs in <outdir>/<era>/ (made if needed) or Fitter/ (see the
        module docstring), the logs."""
        plan = self.plan_fit(request)
        if request.outdir is not None:
            for era in request.eras:
                os.makedirs(self._era_dir(request, era), exist_ok=True)
        report = RunReport(results=self.runner.run_all(plan.commands, logdir, progress), total=len(plan.commands))
        if not report.ok:
            return report
        setup = self._setup(request.config, [])
        artifacts = tuple(self._fit_results(request, artifact, setup) if artifact['kind'] == 'fit' else artifact
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
                indir = self._shapes_dir(request, era, jet_wp, ele_wp)
                if not glob.glob(os.path.join(indir, "*.inputs-%s-*.root" % (era))):
                    problems.append("no shapes for %s %s/%s in %s (run the histograms stage first)"
                                    % (era, jet_wp, ele_wp, indir))
        if request.outdir is not None:
            problems.extend(output_dir_problems(request.outdir, self.pico_config_source(request)))
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

    def _shape_command(self, request, era, jet_wp, ele_wp, config, setup, cwd):
        """One createinputsTES.py run (run_inputs.sh) and the shape files it makes, one per observable."""
        argv = [self.python, self._script(request, 'TauES/createinputsTES.py'), '-y', era,
                '-c', self._config(request, config), '-j', jet_wp, '-e', ele_wp]
        if request.serial:
            argv.append('-s')
        if request.tuples:
            argv += ['--tuples', request.tuples]
        if request.samples:
            argv += ['--samples'] + [path if request.outdir is None else os.path.abspath(path)
                                     for path in request.samples]
        files = _shape_files(setup, era, jet_wp, ele_wp) if setup is not None else []
        channel = setup.get('channel', config) if setup is not None else config
        shapes = [{'kind': 'shapes', 'path': os.path.normpath(os.path.join(cwd, path)), 'era': era,
                   'channel': channel, 'config': config, 'jet_wp': jet_wp, 'ele_wp': ele_wp,
                   'observable': observable} for observable, path in files]
        command = Command("shapes %s %s %s %s" % (era, jet_wp, ele_wp, channel), tuple(argv), cwd,
                          expects=tuple(path for _, path in files), timeout=request.timeout,
                          env=_pico_env(request))
        return command, shapes

    def _point_commands(self, request, era, jet_wp, ele_wp, setup, setup_mumu):
        """The commands of run_workflow_zmm.sh for one working point pair. With an output directory they run in
        <outdir>/<era>/ and read the shapes from their absolute directory; the directories inside the working
        directory stay relative, as in the shell script (several scripts derive one from another with
        str.replace on the whole path, BUGS F18)."""
        cwd = self._era_dir(request, era)
        script = lambda name: self._script(request, name)
        config, config_mumu = self._config(request, request.config), self._config(request, request.config_mumu)
        indir = _wp_dir(INPUTS, jet_wp, ele_wp) if request.outdir is None else \
            self._shapes_dir(request, era, jet_wp, ele_wp)
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
                                        cwd, expects=tuple(expects), timeout=request.timeout,
                                        env=_pico_env(request)))

        # with an output directory, the cards and scan plots go where the shell script puts them relative to its
        # working directory, although the shapes are elsewhere (scripts_arg_changes.md)
        outputs = ['--output_dir', eradir, '--plot_dir', posixpath.join(plotdir, era)] if request.outdir else []
        add('fit', 'datacards mumu',
            [script('TauES_ID/harvestDatacards_zmm.py'), '-y', era, '-c', config_mumu, '-i', indir + '/',
             '-o', eradir + '/'],
            [mumu_card])
        add('fit', 'multidimfit',
            [script('TauES_ID/makecombinedfitTES_SF.py'), '-y', era, '-c', config, '-i', indir + '/',
             '-o', '3', '--mumu_datacard_file', mumu_card] + outputs,
            [posixpath.join(eradir, "higgsCombine.mt_m_vis-%s%s%s-%s-13TeV.MultiDimFit.mH90.root"
                            % (region, tag, EXTRATAG, era)) for region in regions]
            + [posixpath.join(eradir, _values_file(tag, era, region)) for region in regions])
        add('postfit', 'fitdiagnostics',
            [script('TauES_ID/makecombinedfitTES_SF_postfit.py'), '-y', era, '-c', config, '--indir', outdir + '/',
             '-o', '3', '--mumu_input_file', mumu_card, '-cmm', config_mumu, '--jet_wp', jet_wp,
             '--ele_wp', ele_wp] + (['--impacts'] if request.impacts else []),
            [posixpath.join(_wp_dir(POSTFIT, jet_wp, ele_wp), era, "PostFitShape_%s_%s_*.root" % (era, tag))])
        add('plots', 'postfit plots',
            [script('python/plot/runpostfit.py'), '-c', config, '-j', jet_wp, '-e', ele_wp, '-y', era,
             '--include-cr'],
            ["output_plots/jet_%s_ele_%s/*" % (jet_wp, ele_wp)])
        add('plots', 'combined plots',
            [script('pre_post_plot_combiner.py'), '--scan_dir', posixpath.join(plotdir, era) + '/',
             '--jet_wp', jet_wp, '--ele_wp', ele_wp])
        add('plots', 'measurements',
            [script('plot_measurements.py'), '--jet_wp', jet_wp, '--ele_wp', ele_wp, '--year', era],
            ["Measurements/VSjet%s_VSele%s/tes_measurements.png" % (jet_wp, ele_wp)])
        for form in ('root', 'json'):
            add('corrections', form,
                [script('createroot_TES.py'), '-c', config, '-j', jet_wp, '-e', ele_wp, '-f', form, '-y', era],
                [_correction_glob(era, jet_wp, ele_wp, form)])
        return commands

    def _summary_commands(self, request, era):
        """The commands after the working point loop of run_workflow_zmm.sh (once per era). With an output
        directory, the two scripts that read next to themselves (module directory) read the era's directory."""
        moved = request.outdir is not None
        steps = [('scan grid', ['make_scan_grid.py', '--root', PLOTS], ()),
                 ('measurements grid', ['make_measurements_grid.py'] + (['--dir', 'Measurements'] if moved else []),
                  ()),
                 ('merge json', ['merge_tau_jsons.py', '--type', 'both', '-o', _merged_json(era), '-y', era],
                  (_merged_json(era),)),
                 ('nll profiles', ['plot1D_NLL_profiles.py', '--year', era], ()),
                 ('tes and id', ['make_tid_2025.py', '-y', era]
                  + (['--sf-dir', 'tau_sf', '--out', _combined_json(era)] if moved else []), (_combined_json(era),))]
        return [Command("summary %s %s" % (label, era),
                        tuple([self.python, self._script(request, argv[0])] + argv[1:]), self._era_dir(request, era),
                        expects=tuple(expects), timeout=request.timeout, env=_pico_env(request))
                for label, argv, expects in steps]

    # =========================================================================
    # ================================ RESULTS ================================

    def _fit_artifact(self, request, era, jet_wp, ele_wp):
        """The fit artifact of one point, before the fit: where its results go."""
        return {'kind': 'fit', 'era': era, 'jet_wp': jet_wp, 'ele_wp': ele_wp,
                'output_dir': self._era_path(request, era, posixpath.join(_wp_dir(OUTPUTS, jet_wp, ele_wp), era)),
                'postfit_dir': self._era_path(request, era, posixpath.join(_wp_dir(POSTFIT, jet_wp, ele_wp), era)),
                'values': [], 'corrections': []}

    def _fit_results(self, request, artifact, setup):
        """A fit artifact with the fitted values and the correction files found after the fit."""
        era, jet_wp, ele_wp = artifact['era'], artifact['jet_wp'], artifact['ele_wp']
        values = []
        for region in _scan_regions(setup or {}):
            path = os.path.join(artifact['output_dir'], _values_file((setup or {}).get('tag', ''), era, region))
            if os.path.isfile(path):
                with open(path) as stream:
                    values.extend(read_fit_values(stream.read(), region))
        corrections = sorted(path for form in ('root', 'json')
                             for path in glob.glob(self._era_path(request, era,
                                                                  _correction_glob(era, jet_wp, ele_wp, form))))
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

    def _cwd(self, request):
        """The request's output directory as given (the Framework gives an absolute one, or the placeholder
        '<run_dir>/stages/<id>' in a plan), else Fitter/."""
        return os.path.normpath(request.outdir) if request.outdir is not None else self.basedir

    def _era_dir(self, request, era):
        """Where the fit scripts of one era run: <outdir>/<era>/ (many of their outputs have no era in the
        name, BUGS F12), else Fitter/."""
        return os.path.join(self._cwd(request), era) if request.outdir is not None else self.basedir

    def _era_path(self, request, era, relative):
        return os.path.normpath(os.path.join(self._era_dir(request, era), relative))

    def _script(self, request, name):
        """A script of Fitter/: as the shell scripts write it, or absolute when the scripts run elsewhere."""
        return name if request.outdir is None else self._path(name)

    def _config(self, request, config):
        """A config as given (relative to Fitter/ or absolute), or absolute when the scripts run elsewhere."""
        return config if request.outdir is None else self._path(config)

    def _shapes_dir(self, request, era, jet_wp, ele_wp):
        """The directory of the shapes of one point: from request.shapes_dirs, else (shapes made outside the
        Framework) Fitter/input_pt_less_region/againstjet_<J>/againstelectron_<E>."""
        for entry in request.shapes_dirs:
            if entry[:3] == (era, jet_wp, ele_wp):
                return entry[3]
        return self._path(_wp_dir(INPUTS, jet_wp, ele_wp))

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
        self.find_module = find_module or _module_exists

    def __repr__(self):
        return "<TauESID(basedir=%r)>" % (self.basedir)


# =============================================================================
# ================================ FILE NAMES =================================


def _pico_env(request):
    """$TAUFW_PICO_CONFIG for the scripts, if the request names a PicoProducer config (read by getconfig()) and no
    tuple pattern (a FitRequest has none); absolute with an output directory, since the scripts then run elsewhere
    than the caller."""
    if not request.pico_config or getattr(request, 'tuples', None):
        return ()
    return (('TAUFW_PICO_CONFIG', request.pico_config if request.outdir is None else
             os.path.abspath(request.pico_config)),)


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
    """The DeepTau correction files of createroot_TES.py: <TauES|TauID>_SF_dm_DeepTau<version>_<era>_VSjet..
    (BUGS F22: not the files of other taggers)."""
    return "tau_sf/*_SF_dm_DeepTau*_%s_VSjet%s_VSele%s.%s" % (era, jet_wp, ele_wp, form)


def _merged_json(era):
    return "tau_sf/TauCorrections_%s.json" % (era)


def _combined_json(era):
    """The TES + tau ID file of make_tid_2025.py (its default name, in data/tau/ of the working directory)."""
    return "data/tau/TauCorrections_%s_with_uncorrelated_systs.json" % (era)


# =============================================================================
# ================================= DEFAULTS ==================================


def _module_exists(name):
    """True if module `name` can be imported. A module that is already imported counts without asking importlib:
    find_spec() raises ValueError for one whose __spec__ is None, e.g. CMSSW's ROOT once PicoProducer imported it."""
    if sys.modules.get(name) is not None:  # BUGS F25 (None in sys.modules: an import that is blocked)
        return True
    try:
        return importlib.util.find_spec(name) is not None
    except ImportError:  # e.g. the parent package of a dotted name is missing
        return False


def _default_basedir():
    """$CMSSW_BASE/src/TauFW/Fitter, or the Fitter directory of this checkout (as PicoProducer's basedir)."""
    if 'CMSSW_BASE' in os.environ:
        return os.path.join(os.environ['CMSSW_BASE'], 'src', 'TauFW', 'Fitter')
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))


def _read_yaml(path):
    from TauFW.Utilities.FIO import FileIO
    return FileIO().read_yaml(path)
