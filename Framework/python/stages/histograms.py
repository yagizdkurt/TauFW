# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Histograms stage: pico tuples -> input histograms (shapes) of the TES + tau ID fit, through the Fitter API.

It runs what Fitter/run_inputs.sh runs: TauES/createinputsTES.py for every era, working point pair and config.

    inputs:   tuples: pico tuples, given to createinputsTES.py as --tuples <pattern>: those of the production
              stage the slot names (the pattern on its artifacts), or {external: <pattern>}; with null (old
              recipes) the scripts read $PICODIR of the run's PicoProducer config (as $TAUFW_PICO_CONFIG). The TES,
              LTF and JTF variations need their own tuples in the same directory (e.g.
              <sample>_mutau_TES0p950.root).
    options:  HistogramSpec (eras, configs, jet and electron working points)
    outputs:  one shapes artifact per shape file: {kind: 'shapes', path, era, channel, config, jet_wp, ele_wp,
              observable}; the scripts run in the stage's directory, so the files are in
              <run_dir>/stages/<id>/input_pt_less_region/againstjet_<J>/againstelectron_<E>/

The stage runs locally and finishes in one advance() call (see stages/local.py).

Public API:
  HistogramStage(fitter), HistogramSpec, DEFAULT_CONFIGS
"""
from dataclasses import dataclass
from typing import Optional, Tuple

from TauFW.Framework.stages.base import as_strings, spec_to_dict
from TauFW.Framework.stages.local import LocalStage

__all__ = ['HistogramStage', 'HistogramSpec', 'DEFAULT_CONFIGS']


# =============================================================================
# ================================= CONSTANTS =================================


# The configs of Fitter/run_inputs.sh (relative to Fitter/): the mutau fit and the mumu control region.
DEFAULT_CONFIGS = ('TauES_ID/config/config_coarse_TT.yml', 'TauES/config/FitSetup_mumu.yml')


# =============================================================================
# =================================== STAGE ===================================


class HistogramStage(LocalStage):
    """Input histograms with the Fitter API.
    fitter: a TauFW.Fitter.api.TauESID, or any object with the same methods (tests pass a fake one).
    samples_api: the Plotter API that reads the sample model files of the `samples` option (the Fitter only passes
    them to createinputsTES.py; their format is the Plotter's)."""
    name = 'histograms'
    inputs = {'tuples': 'tuples'}
    null_inputs = {'tuples': "the tuples in $PICODIR of the run's PicoProducer config"}
    outputs = ('shapes',)
    group = 'fitter'  # taufw.py init names a copied config <group>_<name> if its name is taken
    # Spec = HistogramSpec: set at the bottom of this file.

    def request(self, spec, context):
        tuples = self.tuples_pattern(context)[0]
        return self.api.shapes_request(tuples=tuples, pico_config=None if tuples else context.pico_config,
                                       outdir=self.output_dir(context), **spec.request_dict())

    def plan_commands(self, request):
        return self.api.plan_shapes(request)

    def preflight(self, request, context):
        problems = tuple(self.api.preflight_shapes(request))
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

    def config_file(self, value):
        return self.api.config_file(value)


# =============================================================================
# ================================= CONTRACT ==================================


@dataclass(frozen=True)
class HistogramSpec:
    """Recipe options: eras, jet and electron working points (DeepTau WP names, e.g. VTight, Tight), the configs
    (bundle files, or relative to Fitter/; default: those of run_inputs.sh) and createinputsTES.py -s (serial)."""
    eras:    Tuple[str, ...]
    jet_wps: Tuple[str, ...]
    ele_wps: Tuple[str, ...]
    configs: Tuple[str, ...] = DEFAULT_CONFIGS
    serial:  bool = False
    timeout: Optional[float] = None   # seconds per createinputsTES.py run; None: no limit
    samples: Tuple[str, ...] = ()     # sample model files (bundle copies of Configs/Plotter/samples/), one per
                                      # era; empty: the tables of Plotter/config/samples_v15.py

    def __post_init__(self):
        for name in ('eras', 'jet_wps', 'ele_wps', 'configs'):
            object.__setattr__(self, name, as_strings(getattr(self, name)))
            if not getattr(self, name):
                raise ValueError("%s must not be empty" % (name))
        object.__setattr__(self, 'samples', as_strings(self.samples))

    def request_dict(self):
        """The options as the Fitter ShapesRequest fields (saved in run.json)."""
        return spec_to_dict(self)


HistogramSpec._paths = ('configs', 'samples')  # resolved against the bundle (bundle.py)
HistogramStage.Spec = HistogramSpec
