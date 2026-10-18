# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Control histograms stage: pico tuples -> control-histogram files, through the Histogrammer API (CL §21, S4).

The first half of the control plots: Histogrammer/fillhists.py --hists --no-draw fills the data/MC stacks of every
variable and selection and writes them to one file per channel setup and era; the controlplots stage draws them
with the Plotter. Until S4 one stage (plots) filled and drew in one script; filling and drawing are now two stages,
each with the API of its own module, and the Framework carries the files between them.

    inputs:   tuples: pico tuples, given to the script as --tuples <pattern>: those of the production stage the slot
              names (the pattern on its artifacts), or {external: <pattern>}; with null (old recipes) the script reads
              $PICODIR of the run's PicoProducer config (passed as $TAUFW_PICO_CONFIG)
    options:  ControlHistsSpec: what is filled (eras, channel setups (bundle files or the Histogrammer's), sample
              files, variable and selection filters, the tag of the file names, the script's filling options); the
              drawing options (-F, -p, -T) are the controlplots stage's
    outputs:  one control_histograms artifact per channel setup and era: {kind: 'control_histograms', era, config,
              channel, tag, file}; the script runs in the stage's directory, so the files are
              <run_dir>/stages/<id>/hists/<era>/<channel><tag>.root

The stage runs locally and finishes in one advance() call (see stages/local.py).

Public API:
  ControlHistsStage(histogrammer), ControlHistsSpec
"""
from dataclasses import dataclass
from typing import Optional, Tuple

from TauFW.Framework.stages.base import as_strings, spec_to_dict
from TauFW.Framework.stages.local import LocalStage

__all__ = ['ControlHistsStage', 'ControlHistsSpec']


# =============================================================================
# =================================== STAGE ===================================


class ControlHistsStage(LocalStage):
    """Control histograms with the Histogrammer API.
    histogrammer: a TauFW.Histogrammer.api.ControlHists, or any object with the same methods (tests pass a fake
    one)."""
    name = 'controlhists'
    inputs = {'tuples': 'tuples'}
    null_inputs = {'tuples': "the tuples in $PICODIR of the run's PicoProducer config"}
    outputs = ('control_histograms',)
    group = 'histogrammer'  # taufw.py init names a copied config <group>_<name> if its name is taken
    # Spec = ControlHistsSpec: set at the bottom of this file.

    def request(self, spec, context):
        tuples = self.tuples_pattern(context)[0]
        return self.api.request(tuples=tuples, pico_config=None if tuples else context.pico_config,
                                outdir=self.output_dir(context), **spec.request_dict())

    def plan_commands(self, request):
        return self.api.plan(request)

    def preflight(self, request, context):
        return self.api.preflight(request)

    def execute(self, request, logdir, progress):
        return self.api.make(request, logdir, progress)

    def config_file(self, value):
        return self.api.config_file(value)


# =============================================================================
# ================================= CONTRACT ==================================


@dataclass(frozen=True)
class ControlHistsSpec:
    """Recipe options: eras, channel setups (bundle files, .yml files relative to Histogrammer/, or a channel name for
    Configs/Histogrammer/setups/setup_<channel>.yml), the script's filters -V (variables) and -S (selections), and its
    filling options. Everything here changes what is in the files; what changes only the picture is an option of
    the controlplots stage (plan 18 §14 K7)."""
    eras:       Tuple[str, ...]
    configs:    Tuple[str, ...] = ('mutau',)
    variables:  Tuple[str, ...] = ()
    selections: Tuple[str, ...] = ()
    serial:     bool = False
    notauidsf:  bool = False
    tag:        str = ""                 # in the file names and in the files: the plots are named with it
    timeout:    Optional[float] = None   # seconds per script run; None: no limit
    samples:    Tuple[str, ...] = ()     # sample model files (bundle copies of Configs/Histogrammer/samples/), one per
                                         # era; empty: the tables of Histogrammer/config/samples_v15.py

    def __post_init__(self):
        for name in ('eras', 'configs', 'variables', 'selections', 'samples'):
            object.__setattr__(self, name, as_strings(getattr(self, name)))
        if not self.eras:
            raise ValueError("eras must not be empty")
        if not self.configs:
            raise ValueError("configs must not be empty")

    def request_dict(self):
        """The options as the Histogrammer HistsRequest fields (saved in run.json)."""
        return spec_to_dict(self)


ControlHistsSpec._paths = ('configs', 'samples')  # resolved against the bundle (bundle.py)
ControlHistsStage.Spec = ControlHistsSpec
