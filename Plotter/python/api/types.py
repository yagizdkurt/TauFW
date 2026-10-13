# Author: Yagizhan Dinckurt (October 2026)
"""Records of the public Plotter API: what a caller asks for and what each call returns.

  PlotsRequest   control plots: eras, channel setups, filters and plot.py options
  CommandPlan    plan(): the commands that would run, the artifacts they would make, notes
  RunReport      make(): one CommandResult per command that ran, and the artifacts

Plots artifact (a JSON-ready dict): {kind: 'plots', era, config, channel, directory, nfiles}.

Public API: the records above.
"""
from dataclasses import dataclass
from typing import Optional, Tuple

__all__ = ['PlotsRequest', 'CommandPlan', 'RunReport']


# =============================================================================
# ================================= REQUESTS ==================================


@dataclass(frozen=True)
class PlotsRequest:
    """Control plots: one plot.py run per channel setup and era.
    configs: channel names (config/setup_<channel>.yml) or .yml files relative to Plotter/.
    variables, selections: plot.py -V and -S filters (glob patterns); empty: all."""
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

    def __post_init__(self):
        for name in ('eras', 'configs', 'variables', 'selections'):
            object.__setattr__(self, name, _strings(getattr(self, name)))
        for name in ('eras', 'configs'):
            if not getattr(self, name):
                raise ValueError("PlotsRequest: %s must not be empty" % (name))


# =============================================================================
# ================================== RESULTS ==================================


@dataclass(frozen=True)
class CommandPlan:
    """What would run: the commands (TauFW.Utilities.Process.Command), all with the same working directory,
    the artifacts they would make, and notes (problems found while planning)."""
    cwd:       str
    commands:  Tuple[object, ...]
    artifacts: Tuple[dict, ...] = ()
    notes:     Tuple[str, ...] = ()


@dataclass(frozen=True)
class RunReport:
    """What ran: one CommandResult per command that ran (the run stops at the first failure), out of `total`,
    and the artifacts that were made."""
    results:   Tuple[object, ...]
    total:     int
    artifacts: Tuple[dict, ...] = ()

    @property
    def ok(self):
        return len(self.results) == self.total and all(result.ok for result in self.results)

    @property
    def failed(self):
        """The CommandResult that stopped the run, or None."""
        return next((result for result in self.results if not result.ok), None)


# =============================================================================
# ================================== HELPERS ==================================


def _strings(values):
    """A single value or a sequence, as a tuple of strings (YAML may give numbers, e.g. eras)."""
    if isinstance(values, (str, int, float)):
        values = (values,)
    return tuple(str(value) for value in values)
