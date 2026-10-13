# Author: Yagizhan Dinckurt (October 2026)
"""Records of the public Fitter API: what a caller asks for and what each call returns.

  ShapesRequest   input histograms (shapes) for the TES + TauID fit: eras, configs, working points
  FitRequest      the fit itself: (era, jet WP, electron WP) points, configs, which steps to run
  CommandPlan     plan_*(): the commands that would run, the artifacts they would make, notes
  RunReport       make_shapes()/fit(): one CommandResult per command that ran, and the artifacts

Artifacts are plain dicts (JSON-ready), so a caller such as the TauFW Framework can store them in run.json:
  shapes:       {kind, path, era, channel, config, jet_wp, ele_wp, observable}
  fit:          {kind, era, jet_wp, ele_wp, output_dir, postfit_dir, values, corrections}
  corrections:  {kind, era, path}

Public API: the records above, FIT_STEPS.
"""
from dataclasses import dataclass
from typing import Optional, Tuple

__all__ = ['FIT_STEPS', 'ShapesRequest', 'FitRequest', 'CommandPlan', 'RunReport']


# =============================================================================
# ================================= CONSTANTS =================================


# The steps of Fitter/run_workflow_zmm.sh, in the order they run:
#   fit          datacards (mumu CR) + 2D MultiDimFit of tes and tid_SF per region (makecombinedfitTES_SF -o 3)
#   postfit      FitDiagnostics, PostFitShapes (and impacts) per region
#   plots        post-fit plots, combined pre/post-fit plots, measurement plots
#   corrections  correction files per working point (createroot_TES, ROOT and JSON)
#   summary      once per era: scan and measurement grids, merged JSON, NLL profiles, combined TES+ID file
FIT_STEPS = ('fit', 'postfit', 'plots', 'corrections', 'summary')


# =============================================================================
# ================================= REQUESTS ==================================


@dataclass(frozen=True)
class ShapesRequest:
    """Input histograms: one createinputsTES.py run per era, working point pair and config.
    configs: config files relative to Fitter/ (the mutau fit config and the mumu control-region config)."""
    eras:    Tuple[str, ...]
    configs: Tuple[str, ...]
    jet_wps: Tuple[str, ...]
    ele_wps: Tuple[str, ...]
    serial:  bool = False             # createinputsTES.py -s: no parallel histogramming
    timeout: Optional[float] = None   # seconds per command

    def __post_init__(self):
        for name in ('eras', 'configs', 'jet_wps', 'ele_wps'):
            object.__setattr__(self, name, _strings(getattr(self, name)))
            if not getattr(self, name):
                raise ValueError("ShapesRequest: %s must not be empty" % (name))


@dataclass(frozen=True)
class FitRequest:
    """The fit: Fitter/run_workflow_zmm.sh for every (era, jet WP, electron WP) point.
    config: the mutau fit config; config_mumu: the mumu control-region config (both relative to Fitter/)."""
    points:      Tuple[Tuple[str, str, str], ...]
    config:      str
    config_mumu: str
    steps:       Tuple[str, ...] = FIT_STEPS
    impacts:     bool = True             # run the impacts in the postfit step (slow)
    timeout:     Optional[float] = None  # seconds per command

    def __post_init__(self):
        points = tuple(tuple(str(value) for value in point) for point in self.points)
        if not points or any(len(point) != 3 for point in points):
            raise ValueError("FitRequest: points must be a non-empty list of (era, jet WP, electron WP)")
        steps = _strings(self.steps)
        unknown = [step for step in steps if step not in FIT_STEPS]
        if unknown or not steps:
            raise ValueError("FitRequest: unknown step %r (steps: %s)" % (unknown[0] if unknown else None,
                                                                          ', '.join(FIT_STEPS)))
        object.__setattr__(self, 'points', points)
        object.__setattr__(self, 'steps', tuple(step for step in FIT_STEPS if step in steps))

    @property
    def eras(self):
        """The eras of the points, in order, without repetition."""
        return tuple(dict.fromkeys(point[0] for point in self.points))


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
