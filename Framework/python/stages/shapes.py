# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Shapes stage: pico tuples -> input histograms (shapes) of the TES + tau ID fit, through the Histogrammer API
TESShapes (the Fitter API's until CL §22 H3). It was called `histograms` until CL §21 (S4a): every stage is named
after what it makes, and the control histograms of the Histogrammer are another stage (controlhists).

It runs what Fitter/run_inputs.sh runs: Histogrammer/shapes/TauES/createinputsTES.py for every era, working point
pair and config. The fit stage reads the files by the contract Docs/Develop/contracts/tes-shapes.md.

    inputs:   tuples: pico tuples, given to createinputsTES.py as --tuples <pattern>: those of the production
              stage the slot names (the pattern on its artifacts), {external: <pattern>} or {path: ...}; never
              null (CL §37). The TES,
              LTF and JTF variations need their own tuples in the same directory (e.g.
              <sample>_mutau_TES0p950.root); with a tuple pattern and `samples` the preflight checks the nominal
              tuples (ControlHists) and every variation tuple the configs read (TESShapes.preflight_shapes), so a
              missing one is a note in check/plan and stops the stage before any command runs.
    options:  ShapesSpec (eras, configs, jet and electron working points); the configs are bundle files,
              Configs/ templates or absolute (the path rule of bundle.py, CL §38)
    outputs:  one shapes artifact per shape file: {kind: 'shapes', path, era, channel, config, jet_wp, ele_wp,
              observable}; the scripts run in the stage's directory, so the files are in
              <run_dir>/stages/<id>/input_pt_less_region/againstjet_<J>/againstelectron_<E>/

The stage runs locally and finishes in one advance() call (see stages/local.py).

Public API:
  ShapesStage(tes_shapes, samples_api=None), ShapesSpec, DEFAULT_CONFIGS
"""
from dataclasses import dataclass
from typing import Optional, Tuple

from TauFW.Framework.stages.base import as_strings, spec_to_dict
from TauFW.Framework.stages.local import LocalStage

__all__ = ['ShapesStage', 'ShapesSpec', 'DEFAULT_CONFIGS']


# =============================================================================
# ================================= CONSTANTS =================================


# The configs of Fitter/run_inputs.sh: the mutau fit and the mumu control region, the templates in
# Configs/Fitter/tes_id/ (CL §22; resolved by bundle.py, 'template')
DEFAULT_CONFIGS = ('Configs/Fitter/tes_id/config_coarse_TT.yml', 'Configs/Fitter/tes_id/FitSetup_mumu.yml')


# =============================================================================
# =================================== STAGE ===================================


class ShapesStage(LocalStage):
    """Input histograms with the Histogrammer API.
    tes_shapes: a TauFW.Histogrammer.api.TESShapes, or any object with the same methods (tests pass a fake one).
    samples_api: the Histogrammer API that reads the sample model files of the `samples` option (ControlHists;
    TESShapes only passes them to createinputsTES.py)."""
    name = 'shapes'
    inputs = {'tuples': 'tuples'}
    null_inputs = {}  # the tuples are given, never found (CL §37)
    outputs = ('shapes',)
    group = 'fitter'  # taufw.py init names a copied config <group>_<name> if its name is taken (fit configs)
    # Spec = ShapesSpec: set at the bottom of this file.

    def request(self, spec, context):
        tuples = self.tuples_pattern(context)[0]
        return self.api.shapes_request(tuples=tuples, outdir=self.output_dir(context), **spec.request_dict())

    def plan_commands(self, request):
        return self.api.plan_shapes(request)

    deep_checks = True  # the nominal tuples' branches (TESShapes.preflight_shapes)

    def preflight(self, request, context):
        problems = tuple(self.api.preflight_shapes(request, branches=context.deep))
        samples, tuples = getattr(request, 'samples', ()), getattr(request, 'tuples', None)
        if samples and hasattr(self.samples_api, 'samples_problems'):  # the files' content, the tuple files
            sample_problems = tuple(self.samples_api.samples_problems(samples, request.eras))
            problems += sample_problems
            if tuples and not sample_problems and '<' not in tuples:
                channels = [artifact['channel'] for artifact in self.plan_commands(request).artifacts]
                problems += tuple(self.samples_api.sample_file_problems(samples, request.eras, channels, tuples))
        return problems

    def execute(self, request, logdir, progress):
        return self.api.make_shapes(request, logdir, progress)


# =============================================================================
# ================================= CONTRACT ==================================


@dataclass(frozen=True)
class ShapesSpec:
    """Recipe options: eras, jet and electron working points (DeepTau WP names, e.g. VTight, Tight), the configs
    (bundle files, Configs/ templates or absolute; default: the templates of run_inputs.sh) and createinputsTES.py
    -s (serial)."""
    eras:    Tuple[str, ...]
    jet_wps: Tuple[str, ...]
    ele_wps: Tuple[str, ...]
    configs: Tuple[str, ...] = DEFAULT_CONFIGS
    serial:  bool = False
    timeout: Optional[float] = None   # seconds per createinputsTES.py run; None: no limit
    samples: Tuple[str, ...] = ()     # sample model files (bundle copies of Configs/Histogrammer/samples/), one per
                                      # era; empty: the tables of Histogrammer/config/samples_v15.py

    def __post_init__(self):
        for name in ('eras', 'jet_wps', 'ele_wps', 'configs'):
            object.__setattr__(self, name, as_strings(getattr(self, name)))
            if not getattr(self, name):
                raise ValueError("%s must not be empty" % (name))
        object.__setattr__(self, 'samples', as_strings(self.samples))

    def request_dict(self):
        """The options as the ShapesRequest fields of the Histogrammer API (saved in run.json)."""
        return spec_to_dict(self)


ShapesSpec._paths = ('configs', 'samples')  # resolved against the bundle (bundle.py)
ShapesStage.Spec = ShapesSpec
