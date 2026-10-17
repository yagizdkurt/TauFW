# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Plots stage: data/MC control plots of the pico tuples, through the Histogrammer API (Histogrammer/fillhists.py, the
former Plotter/plot.py; CL §24).

    inputs:   tuples: pico tuples, given to the script as --tuples <pattern>: those of the production stage the slot
              names (the pattern on its artifacts), or {external: <pattern>}; with null (old recipes) the script reads
              $PICODIR of the run's PicoProducer config (passed as $TAUFW_PICO_CONFIG)
    options:  PlotSpec (eras, channel setups (bundle files or the Histogrammer's), variable and selection filters, script
              options)
    outputs:  one plots artifact per channel setup and era: {kind: 'plots', era, config, channel, directory,
              nfiles}; the script runs in the stage's directory, so the plots are in <run_dir>/stages/<id>/plots/<era>/

The stage runs locally and finishes in one advance() call (see stages/local.py). It comes right after production,
so the tuples can be checked by eye before the long histogram and fit stages.

Public API:
  PlotStage(plotter), PlotSpec
"""
from dataclasses import dataclass
from typing import Optional, Tuple

from TauFW.Framework.stages.base import as_strings, spec_to_dict
from TauFW.Framework.stages.local import LocalStage

__all__ = ['PlotStage', 'PlotSpec']


# =============================================================================
# =================================== STAGE ===================================


class PlotStage(LocalStage):
    """Control plots with the Histogrammer API.
    plotter: a TauFW.Histogrammer.api.ControlPlots, or any object with the same methods (tests pass a fake one)."""
    name = 'plots'
    inputs = {'tuples': 'tuples'}
    null_inputs = {'tuples': "the tuples in $PICODIR of the run's PicoProducer config"}
    outputs = ('plots',)
    group = 'plotter'  # taufw.py init names a copied config <group>_<name> if its name is taken
    # Spec = PlotSpec: set at the bottom of this file.

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
class PlotSpec:
    """Recipe options: eras, channel setups (bundle files, .yml files relative to Histogrammer/, or a channel name for
    Configs/Plotter/setups/setup_<channel>.yml), the
    script's filters -V (variables) and -S (selections), and its flags."""
    eras:       Tuple[str, ...]
    configs:    Tuple[str, ...] = ('mutau',)
    variables:  Tuple[str, ...] = ()
    selections: Tuple[str, ...] = ()
    serial:     bool = False
    fraction:   bool = False
    pdf:        bool = False
    notauidsf:  bool = False
    tag:        str = ""
    text:       str = ""
    timeout:    Optional[float] = None   # seconds per script run; None: no limit
    samples:    Tuple[str, ...] = ()     # sample model files (bundle copies of Configs/Plotter/samples/), one per
                                         # era; empty: the tables of Histogrammer/config/samples_v15.py

    def __post_init__(self):
        for name in ('eras', 'configs', 'variables', 'selections', 'samples'):
            object.__setattr__(self, name, as_strings(getattr(self, name)))
        if not self.eras:
            raise ValueError("eras must not be empty")
        if not self.configs:
            raise ValueError("configs must not be empty")

    def request_dict(self):
        """The options as the Histogrammer PlotsRequest fields (saved in run.json)."""
        return spec_to_dict(self)


PlotSpec._paths = ('configs', 'samples')  # resolved against the bundle (bundle.py)
PlotStage.Spec = PlotSpec
