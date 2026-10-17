# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Records of the public Fitter API: what a caller asks for and what each call returns.

  ShapesRequest   input histograms (shapes) for the TES + TauID fit: eras, configs, working points
  FitRequest      the fit itself: (era, jet WP, electron WP) points, configs, which steps to run
  plan_*() return a CommandPlan, make_shapes() and fit() a RunReport (TauFW.Utilities.Process).

Artifacts are plain dicts (JSON-ready), so a caller such as the TauFW Framework can store them in run.json:
  shapes:       {kind, path, era, channel, config, jet_wp, ele_wp, observable}
  fit:          {kind, era, jet_wp, ele_wp, output_dir, postfit_dir, values, corrections}
  corrections:  {kind, era, path}; path is the merged JSON of the working points, or (combined: true) the
                TES + tau ID file of make_tid_2025.py

Public API: the records above, FIT_STEPS.
"""
from dataclasses import dataclass
from typing import Optional, Tuple

__all__ = ['FIT_STEPS', 'ShapesRequest', 'FitRequest']


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
    configs: config files, relative to Fitter/ or absolute (the mutau fit config and the mumu control-region
    config). tuples: the directory pattern of the tuples (with $ERA, $GROUP), given to createinputsTES.py as
    --tuples; then the PicoProducer configuration is not used. pico_config: the PicoProducer configuration the
    scripts read $PICODIR from without tuples (None: its default).
    outdir: the directory the scripts run in and write input_pt_less_region/ to (None: Fitter/).
    samples: sample model files, one per era (Configs/Plotter/samples/v15_<era>.yml or a copy), given to
    createinputsTES.py as --samples; empty: the tables of Histogrammer/config/samples_v15.py."""
    eras:    Tuple[str, ...]
    configs: Tuple[str, ...]
    jet_wps: Tuple[str, ...]
    ele_wps: Tuple[str, ...]
    serial:  bool = False             # createinputsTES.py -s: no parallel histogramming
    timeout: Optional[float] = None   # seconds per command
    tuples:  Optional[str] = None     # --tuples of the commands
    pico_config: Optional[str] = None # $TAUFW_PICO_CONFIG of the commands (without tuples)
    outdir:  Optional[str] = None     # working directory of the scripts (None: Fitter/)
    samples: Tuple[str, ...] = ()     # --samples of the commands

    def __post_init__(self):
        for name in ('eras', 'configs', 'jet_wps', 'ele_wps'):
            object.__setattr__(self, name, _strings(getattr(self, name)))
            if not getattr(self, name):
                raise ValueError("ShapesRequest: %s must not be empty" % (name))
        object.__setattr__(self, 'samples', _strings(self.samples))


@dataclass(frozen=True)
class FitRequest:
    """The fit: Fitter/run_workflow_zmm.sh for every (era, jet WP, electron WP) point.
    config: the mutau fit config; config_mumu: the mumu control-region config (both relative to Fitter/, or
    absolute). pico_config: the PicoProducer configuration the scripts read $PICODIR from (None: its default).
    outdir: the directory the fit writes to; the scripts of one era run in <outdir>/<era>/ (None: all in Fitter/).
    shapes_dirs: (era, jet WP, electron WP, directory) of the shape files of each point (absolute). Empty: every
    point reads Fitter/input_pt_less_region/... (the shapes made outside the Framework; with outdir, a temporary
    exception for the Framework's null shapes input). With outdir, a non-empty shapes_dirs must name every point:
    a point is never read from Fitter/ silently while the others come from elsewhere."""
    points:      Tuple[Tuple[str, str, str], ...]
    config:      str
    config_mumu: str
    steps:       Tuple[str, ...] = FIT_STEPS
    impacts:     bool = True             # run the impacts in the postfit step (slow)
    timeout:     Optional[float] = None  # seconds per command
    pico_config: Optional[str] = None    # $TAUFW_PICO_CONFIG of the commands
    outdir:      Optional[str] = None    # where the fit writes (None: Fitter/)
    shapes_dirs: Tuple[Tuple[str, str, str, str], ...] = ()  # (era, jet WP, electron WP, directory)

    def __post_init__(self):
        object.__setattr__(self, 'shapes_dirs', tuple(tuple(str(value) for value in entry)
                                                      for entry in self.shapes_dirs))
        if any(len(entry) != 4 for entry in self.shapes_dirs):
            raise ValueError("FitRequest: shapes_dirs must be (era, jet WP, electron WP, directory)")
        points = tuple(tuple(str(value) for value in point) for point in self.points)
        if not points or any(len(point) != 3 for point in points):
            raise ValueError("FitRequest: points must be a non-empty list of (era, jet WP, electron WP)")
        steps = _strings(self.steps)
        unknown = [step for step in steps if step not in FIT_STEPS]
        if unknown or not steps:
            raise ValueError("FitRequest: unknown step %r (steps: %s)" % (unknown[0] if unknown else None,
                                                                          ', '.join(FIT_STEPS)))
        if self.outdir is not None and self.shapes_dirs:
            missing = [point for point in points if point not in {entry[:3] for entry in self.shapes_dirs}]
            if missing:
                raise ValueError("FitRequest: shapes_dirs names no directory for %s (with outdir it names every "
                                 "point, or none)" % (', '.join("%s %s/%s" % point for point in missing)))
        object.__setattr__(self, 'points', points)
        object.__setattr__(self, 'steps', tuple(step for step in FIT_STEPS if step in steps))

    @property
    def eras(self):
        """The eras of the points, in order, without repetition."""
        return tuple(dict.fromkeys(point[0] for point in self.points))


# =============================================================================
# ================================== HELPERS ==================================


def _strings(values):
    """A single value or a sequence, as a tuple of strings (YAML may give numbers, e.g. eras)."""
    if isinstance(values, (str, int, float)):
        values = (values,)
    return tuple(str(value) for value in values)
