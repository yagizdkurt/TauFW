# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Records of the public Plotter API: what a caller asks for and what each call returns.

  PlotsRequest   control plots: eras, channel setups, filters and plot.py options
  plan() and make() return a CommandPlan and a RunReport (TauFW.Utilities.Process).

Plots artifact (a JSON-ready dict): {kind: 'plots', era, config, channel, directory, nfiles}.

Public API: the records above.
"""
from dataclasses import dataclass
from typing import Optional, Tuple

__all__ = ['PlotsRequest']


# =============================================================================
# ================================= REQUESTS ==================================


@dataclass(frozen=True)
class PlotsRequest:
    """Control plots: one plot.py run per channel setup and era.
    configs: channel names (config/setup_<channel>.yml) or .yml files (relative to Plotter/, or absolute).
    variables, selections: plot.py -V and -S filters (glob patterns); empty: all.
    tuples: the directory pattern of the tuples (with $ERA, $GROUP), given to plot.py as --tuples; then the
    PicoProducer configuration is not used. None: plot.py reads $PICODIR of pico_config (None: its default).
    samples: sample model files, one per era (Configs/Plotter/samples/v15_<era>.yml or a copy), given to plot.py as
    --samples; empty: the tables of config/samples_v15.py.
    outdir: the directory plot.py runs in and writes plots/<era>/ to (None: Plotter/, as a user runs it)."""
    eras:       Tuple[str, ...]
    configs:    Tuple[str, ...] = ('mutau',)
    variables:  Tuple[str, ...] = ()
    selections: Tuple[str, ...] = ()
    serial:     bool = False             # -s: no parallel histogramming
    fraction:   bool = False             # -F: fraction stack in the ratio plot
    pdf:        bool = False             # -p: pdf next to each png
    notauidsf:  bool = False             # -r: remove the DeepTau ID scale factors
    tag:        str = ""                 # -t: extra tag of the output files
    text:       str = ""                 # -T: extra text on the plots
    timeout:    Optional[float] = None   # seconds per command
    tuples:     Optional[str] = None     # --tuples of the commands
    pico_config: Optional[str] = None    # $TAUFW_PICO_CONFIG of the commands (without tuples)
    outdir:     Optional[str] = None     # working directory of plot.py (None: Plotter/)
    samples:    Tuple[str, ...] = ()     # --samples of the commands

    def __post_init__(self):
        for name in ('eras', 'configs', 'variables', 'selections', 'samples'):
            object.__setattr__(self, name, _strings(getattr(self, name)))
        for name in ('eras', 'configs'):
            if not getattr(self, name):
                raise ValueError("PlotsRequest: %s must not be empty" % (name))


# =============================================================================
# ================================== HELPERS ==================================


def _strings(values):
    """A single value or a sequence, as a tuple of strings (YAML may give numbers, e.g. eras)."""
    if isinstance(values, (str, int, float)):
        values = (values,)
    return tuple(str(value) for value in values)
