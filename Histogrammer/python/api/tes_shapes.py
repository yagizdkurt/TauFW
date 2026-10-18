# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""TESShapes: the public API for the input histograms (shapes) of the combined tau energy scale (TES) + tau ID fit.
Until CL §22 (H3) this was the shapes half of the Fitter API (TauFW.Fitter.api.TauESID); the fit stays there and
reads the files by the contract docs/contracts/tes-shapes.md (the two modules never import each other).

shapes/TauES/createinputsTES.py fills them. This API runs it as a separate process, one run per era, working point
pair and config, in the order of Fitter/run_inputs.sh and with its arguments, and checks that it wrote the shape
files. The script runs in the request's output directory (outdir, required: the TauFW Framework gives
<run_dir>/stages/<id>/), with the script and the configs as absolute paths. By hand, Fitter/run_inputs.sh runs the
same script from Fitter/, where the fit scripts look for the shapes:

    ShapesRequest ─▶ plan_shapes() ─▶ make_shapes()   = python3 shapes/TauES/createinputsTES.py -y ERA -c CONFIG
                     CommandPlan      RunReport                                               -j JET -e ELE [options]
                                      (one shapes artifact per shape file)
    preflight_shapes(): what is missing in the environment (empty: ready), with the variation tuples

Each command must exit with 0 AND write its expected files (see TauFW.Utilities.Process). A run stops at the first
command that fails.

Inputs:  pico tuples in the request's tuple pattern (--tuples), or else found by the script through $PICODIR of the
         request's PicoProducer config (passed as $TAUFW_PICO_CONFIG; default PicoProducer/config/config.json);
         the YAML configs (relative to Histogrammer/ or absolute; the templates are in Configs/Fitter/tes_id/); the
         sample model files (--samples; without them the tables of config/samples_v15.py). The TES points and the
         shape systematics with sampleAppend read variation tuples next to the nominal ones
         (<sample>_<channel>_TES0p950.root, ..._LTF1p030.root); with a tuple pattern and sample files the preflight
         checks them all (variation_problems; TauFW.Histogrammer.sample.variations names them).
Outputs: <outdir>/input_pt_less_region/againstjet_<J>/againstelectron_<E>/ztt_<ch>_tes_<obs>.inputs-<era>-13TeV<tag>.root
         (and what the script writes next to them, contract page), one log file per command in the caller's log
         directory. Artifact: {kind: shapes, path, era, channel, config, jet_wp, ele_wp, observable}.

Public API:
  TESShapes(basedir, runner, read_yaml, python, find_module)
  plan_shapes, make_shapes, preflight_shapes      pipelines
  shapes_request(**fields)                        a ShapesRequest
  config_file(config)                             a config as an absolute path
  pico_config_source(request)                     where $PICODIR is read from (a request without tuples)
  variation_problems(request)                     the variation tuples the configs read that are missing
"""
import os
import sys

from TauFW.Utilities.Process import (Command, CommandPlan, ProcessRunner, RunReport, output_dir_problems,
                                     tuple_pattern_problems)
from TauFW.Histogrammer.api.types import ShapesRequest
from TauFW.Histogrammer.api.control_hists import _default_basedir, _module_exists, _pico_env, _read_yaml, _tuple_file
from TauFW.Histogrammer.sample import model as sample_model
from TauFW.Histogrammer.sample.variations import variations

__all__ = ['TESShapes']

SCRIPT = os.path.join('shapes', 'TauES', 'createinputsTES.py')  # the script this API runs (Fitter/TauES/ until CL §22)
INPUTS = 'input_pt_less_region'  # the shape tree (createinputsTES.py -O default; the fit scripts read this name)


class TESShapes:
    """TES + tau ID shapes with shapes/TauES/createinputsTES.py; see the module docstring.

    Pipelines:    plan_shapes(request)                     -> CommandPlan   changes nothing
                  make_shapes(request, logdir, progress)   -> RunReport     runs createinputsTES.py
                  preflight_shapes(request)                -> tuple of problems (empty: ready)
                  variation_problems(request)              -> tuple of problems (part of preflight_shapes)
    Requests:     shapes_request(**fields)                 -> ShapesRequest
    Construction: TESShapes(basedir, runner, read_yaml, python, find_module)
    """

    # =========================================================================
    # =============================== PIPELINES ===============================

    def plan_shapes(self, request):
        """The createinputsTES.py commands, in the order of run_inputs.sh, and the shape files they make."""
        commands, artifacts, notes = [], [], []
        cwd = os.path.normpath(request.outdir)  # as given: absolute from the Framework, or a plan's placeholder
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
        """Run plan_shapes(); stops at the first failure. Side effects: the output directory (made if needed) with
        the shape files, the logs."""
        plan = self.plan_shapes(request)
        os.makedirs(plan.cwd, exist_ok=True)
        report = RunReport(results=self.runner.run_all(plan.commands, logdir, progress), total=len(plan.commands))
        return RunReport(results=report.results, total=report.total, artifacts=plan.artifacts if report.ok else ())

    def preflight_shapes(self, request):
        """What is missing to make the shapes: CMSSW, ROOT, the tuple pattern's keys or else the PicoProducer
        config, the config files, the sample model files (only that they exist: ControlHists.samples_problems reads
        them), the output directory, and the variation tuples (variation_problems)."""
        problems = []
        if 'CMSSW_BASE' not in os.environ:
            problems.append("CMSSW_BASE is not set (run cmsenv first)")
        if not self.find_module('ROOT'):
            problems.append("python cannot import ROOT")
        source = None if request.tuples else self.pico_config_source(request)
        if request.tuples:
            problems.extend(tuple_pattern_problems(request.tuples))
        elif not os.path.isfile(source):
            problems.append("no PicoProducer configuration %s: the script reads $PICODIR from it" % (source))
        problems.extend("config %s not found in %s" % (config, self.basedir) for config in request.configs
                        if not os.path.isfile(self.config_file(config)))
        problems.extend("sample file %s not found" % (path) for path in request.samples if not os.path.isfile(path))
        problems.extend(output_dir_problems(request.outdir, source, tuples=request.tuples))
        problems.extend(self.variation_problems(request))
        return tuple(problems)

    def variation_problems(self, request, maxshow=5):
        """The variation tuples that createinputsTES.py opens after the nominal histograms (TES points, shape
        systematics with sampleAppend) and that are missing: one problem per config and era. Checked only with a tuple
        pattern (not a plan's placeholder) and sample model files, as the nominal tuples (ControlHists
        sample_file_problems); a config or sample file that cannot be read is left to the other checks."""
        if not request.tuples or not request.samples or '<' in request.tuples:
            return ()
        problems = []
        for config in request.configs:
            setup = self._setup(config, [])
            if not setup or not setup.get('channel'):
                continue
            for era in request.eras:
                try:
                    model = sample_model.pick(request.samples, era)
                except sample_model.SampleModelError:
                    continue
                problems.extend(_missing_variations(config, era, setup, model, request.tuples, maxshow))
        return tuple(problems)

    def shapes_request(self, **fields):
        """A ShapesRequest (unknown fields are an error), so callers need not import the records."""
        return ShapesRequest(**fields)

    def config_file(self, config):
        """A config file (relative to Histogrammer/, or absolute), as an absolute path."""
        return self._path(config)

    def pico_config_source(self, request=None):
        """The PicoProducer configuration that the script reads $PICODIR from: the request's, else the default."""
        if request is not None and request.pico_config:
            return request.pico_config
        return os.path.join(os.path.dirname(self.basedir), 'PicoProducer', 'config', 'config.json')

    # =========================================================================
    # =============================== COMMANDS ================================

    def _shape_command(self, request, era, jet_wp, ele_wp, config, setup, cwd):
        """One createinputsTES.py run (run_inputs.sh) and the shape files it makes, one per observable."""
        argv = [self.python, self._path(SCRIPT), '-y', era, '-c', self.config_file(config), '-j', jet_wp,
                '-e', ele_wp]
        if request.serial:
            argv.append('-s')
        if request.tuples:
            argv += ['--tuples', request.tuples]
        if request.samples:
            argv += ['--samples'] + [os.path.abspath(path) for path in request.samples]
        files = _shape_files(setup, era, jet_wp, ele_wp) if setup is not None else []
        channel = setup.get('channel', config) if setup is not None else config
        shapes = [{'kind': 'shapes', 'path': os.path.normpath(os.path.join(cwd, path)), 'era': era,
                   'channel': channel, 'config': config, 'jet_wp': jet_wp, 'ele_wp': ele_wp,
                   'observable': observable} for observable, path in files]
        command = Command("shapes %s %s %s %s" % (era, jet_wp, ele_wp, channel), tuple(argv), cwd,
                          expects=tuple(path for _, path in files), timeout=request.timeout,
                          env=_pico_env(request))
        return command, shapes

    # =========================================================================
    # ================================ HELPERS ================================

    def _setup(self, config, notes):
        """The YAML config, or None with a note if it cannot be read."""
        path = self.config_file(config)
        if not os.path.isfile(path):
            notes.append("config %s not found in %s" % (config, self.basedir))
            return None
        try:
            return self.read_yaml(path) or {}
        except Exception as error:
            notes.append("cannot read config %s: %s" % (config, error))
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
        python:      the Python of createinputsTES.py (default: this one, sys.executable)
        find_module: module lookup (default: importlib)
        Construction reads nothing and runs nothing."""
        self.basedir = os.path.abspath(basedir or _default_basedir())
        self.runner = runner or ProcessRunner()
        self.read_yaml = read_yaml or _read_yaml
        self.python = python or sys.executable
        self.find_module = find_module or _module_exists

    def __repr__(self):
        return "<TESShapes(basedir=%r)>" % (self.basedir)


# =============================================================================
# ================================ FILE NAMES =================================


def _missing_variations(config, era, setup, model, tuples, maxshow):
    """The problem of one config and era (empty: every variation tuple is there). The file is the nominal tuple
    (_tuple_file) with the tag before .root, as Sample.appendfilename makes it."""
    channel = setup['channel']
    missing, total, counts = [], 0, {}
    for variation in variations(setup, model, era):
        for group, sample in variation.samples:
            nominal = _tuple_file(tuples, era, group, sample, channel)
            path = nominal if variation.tag in nominal else nominal.replace(".root", variation.tag + ".root")
            total += 1
            if not os.path.isfile(path):
                missing.append(path)
                counts[variation.tag] = counts.get(variation.tag, 0) + 1
    if not missing:
        return ()
    tags = ", ".join("%s: %d" % (tag, count) for tag, count in counts.items())
    shown = ", ".join(missing[:maxshow]) + (", ..." if len(missing) > maxshow else "")
    return ("%d of %d variation tuple file(s) of config %s, era %s, not found (%s): %s"
            % (len(missing), total, config, era, tags, shown),)


def _shape_files(setup, era, jet_wp, ele_wp):
    """(observable, path) of the shape files createinputsTES.py writes for one config (createinputsTES.py:238; the
    rule of docs/contracts/tes-shapes.md), relative to its working directory."""
    chshort = setup.get('channel', '').replace('tau', 't').replace('mu', 'm')
    tag = "13TeV" + setup.get('tag', '')
    files = []
    for observable, options in (setup.get('observables') or {}).items():
        name = ((options or {}).get('extra') or {}).get('filename', observable)
        files.append((observable, "%s/againstjet_%s/againstelectron_%s/ztt_%s_tes_%s.inputs-%s-%s.root"
                      % (INPUTS, jet_wp, ele_wp, chshort, name, era, tag)))
    return files
