# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Records of the public Histogrammer API: what a caller asks for and what each call returns.

  HistsRequest   control histograms: eras, channel setups, filters and fillhists.py options (no drawing
                 options: the Plotter draws, CL §21 S4)
  ShapesRequest  input histograms (shapes) of the TES + tau ID fit: eras, configs, working points (in the Fitter API
                 until CL §22 H3)
  plan*() return a CommandPlan, make*() a RunReport (TauFW.Utilities.Process).

Artifacts (JSON-ready dicts):
  control histograms: {kind: 'control_histograms', era, config, channel, tag, file}
  shapes:             {kind: 'shapes', path, era, channel, config, jet_wp, ele_wp, observable}
                      (one file per observable, Docs/Develop/contracts/tes-shapes.md)

Public API: the records above.
"""
from dataclasses import dataclass
from typing import Optional, Tuple

__all__ = ['HistsRequest', 'ShapesRequest']


# =============================================================================
# ================================= REQUESTS ==================================


@dataclass(frozen=True)
class HistsRequest:
    """Control histograms: one fillhists.py --hists --no-draw run per channel setup and era (PlotsRequest until
    CL §21 S4; its drawing options -F, -p, -T went to the Plotter's PlotsRequest).
    configs: channel names (Configs/Histogrammer/setups/setup_<channel>.yml) or .yml files (relative to Histogrammer/, or
    absolute).
    variables, selections: -V and -S filters (glob patterns); empty: all.
    tuples: the directory pattern of the tuples (with $ERA, $GROUP), given as --tuples; then the
    PicoProducer configuration is not used. None: the script reads $PICODIR of pico_config (None: its default).
    samples: sample model files, one per era (Configs/Histogrammer/samples/v15_<era>.yml or a copy), given as
    --samples; empty: the tables of config/samples_v15.py.
    outdir: the directory the script runs in and writes hists/<era>/ to (None: Histogrammer/, as a user runs it)."""
    eras:       Tuple[str, ...]
    configs:    Tuple[str, ...] = ('mutau',)
    variables:  Tuple[str, ...] = ()
    selections: Tuple[str, ...] = ()
    serial:     bool = False             # -s: no parallel histogramming
    notauidsf:  bool = False             # -r: remove the DeepTau ID scale factors
    tag:        str = ""                 # -t: extra tag of the output files
    timeout:    Optional[float] = None   # seconds per command
    tuples:     Optional[str] = None     # --tuples of the commands
    pico_config: Optional[str] = None    # $TAUFW_PICO_CONFIG of the commands (without tuples)
    outdir:     Optional[str] = None     # working directory of the script (None: Histogrammer/)
    samples:    Tuple[str, ...] = ()     # --samples of the commands

    def __post_init__(self):
        for name in ('eras', 'configs', 'variables', 'selections', 'samples'):
            object.__setattr__(self, name, _strings(getattr(self, name)))
        for name in ('eras', 'configs'):
            if not getattr(self, name):
                raise ValueError("HistsRequest: %s must not be empty" % (name))


@dataclass(frozen=True)
class ShapesRequest:
    """Input histograms: one createinputsTES.py run per era, working point pair and config (the fields of the
    Fitter's ShapesRequest until CL §22 H3).
    configs: config files, relative to Histogrammer/ or absolute (the mutau fit config and the mumu control-region
    config, e.g. the templates in Configs/Fitter/tes_id/). tuples: the directory pattern of the tuples (with $ERA,
    $GROUP), given to createinputsTES.py as --tuples; then the PicoProducer configuration is not used. pico_config:
    the PicoProducer configuration the script reads $PICODIR from without tuples (None: its default).
    outdir: the directory the script runs in and writes input_pt_less_region/ to; required (the Framework gives
    <run_dir>/stages/<id>/; by hand, Fitter/run_inputs.sh writes the shapes into Fitter/).
    samples: sample model files, one per era (Configs/Histogrammer/samples/v15_<era>.yml or a copy), given to
    createinputsTES.py as --samples; empty: the tables of config/samples_v15.py."""
    eras:    Tuple[str, ...]
    configs: Tuple[str, ...]
    jet_wps: Tuple[str, ...]
    ele_wps: Tuple[str, ...]
    serial:  bool = False             # createinputsTES.py -s: no parallel histogramming
    timeout: Optional[float] = None   # seconds per command
    tuples:  Optional[str] = None     # --tuples of the commands
    pico_config: Optional[str] = None # $TAUFW_PICO_CONFIG of the commands (without tuples)
    outdir:  Optional[str] = None     # working directory of the script (required)
    samples: Tuple[str, ...] = ()     # --samples of the commands

    def __post_init__(self):
        for name in ('eras', 'configs', 'jet_wps', 'ele_wps'):
            object.__setattr__(self, name, _strings(getattr(self, name)))
            if not getattr(self, name):
                raise ValueError("ShapesRequest: %s must not be empty" % (name))
        object.__setattr__(self, 'samples', _strings(self.samples))
        if self.outdir is None:  # the Histogrammer never writes into another module's directory (CL §22 H3, E1)
            raise ValueError("ShapesRequest: outdir is required (the Framework gives <run_dir>/stages/<id>/; by "
                             "hand, Fitter/run_inputs.sh makes the shapes in Fitter/)")


# =============================================================================
# ================================== HELPERS ==================================


def _strings(values):
    """A single value or a sequence, as a tuple of strings (YAML may give numbers, e.g. eras)."""
    if isinstance(values, (str, int, float)):
        values = (values,)
    return tuple(str(value) for value in values)
