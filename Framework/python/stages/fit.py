# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Fit stage: shapes -> datacards -> TES and tau ID fit -> correction files, through the Fitter API.

It runs what Fitter/run_workflow_zmm.sh runs for every (era, jet WP, electron WP) point: the mumu control-region
datacards, the 2D MultiDimFit of tes and tid_SF per region (makecombinedfitTES_SF.py -o 3), FitDiagnostics and
post-fit shapes, the plots, the correction files, and once per era the summary (grids, merged JSON).

    inputs:   the shapes in Fitter/input_pt_less_region/... The points come from the recipe (eras x jet_wps x
              ele_wps), or, if jet_wps and ele_wps are empty, from the shapes artifacts of the histograms stage
              (every era and working point pair that has shapes of both configs).
    options:  FitSpec (configs, points, steps, impacts)
    outputs:  one fit artifact per point: {kind: 'fit', era, jet_wp, ele_wp, output_dir, postfit_dir, values,
              corrections}, where values are the fitted {region, poi, value, low, high}; one corrections
              artifact per era (the merged JSON) if the summary step runs.

The stage runs locally and finishes in one advance() call (see stages/local.py). A full scan of many working points
takes hours.

Public API:
  FitStage(fitter), FitSpec, STEPS
"""
from dataclasses import dataclass
from itertools import product
from typing import Optional, Tuple

from TauFW.Framework.stages.base import as_strings, spec_to_dict
from TauFW.Framework.stages.local import LocalStage
from TauFW.Framework.stages.histograms import DEFAULT_CONFIGS

__all__ = ['FitStage', 'FitSpec', 'STEPS']


# =============================================================================
# ================================= CONSTANTS =================================


# The steps of the fit, as in TauFW.Fitter.api.FIT_STEPS (repeated here so recipes are checked when they load).
STEPS = ('fit', 'postfit', 'plots', 'corrections', 'summary')


# =============================================================================
# =================================== STAGE ===================================


class FitStage(LocalStage):
    """The TES + tau ID fit with the Fitter API.
    fitter: a TauFW.Fitter.api.TauESID, or any object with the same methods (tests pass a fake one)."""
    name = 'fit'
    group = 'fitter'  # taufw.py init names a copied config <group>_<name> if its name is taken
    # Spec = FitSpec: set at the bottom of this file.

    def request(self, spec, context):
        """The FitRequest; its points come from the recipe or from the upstream shapes (see the top of this
        file). Raises ValueError if there are no points."""
        points = self.points(spec, context)
        if not points:
            raise ValueError("no working points to fit: set eras, jet_wps and ele_wps, or add a histograms stage")
        return self.api.fit_request(points=points, config=spec.config, config_mumu=spec.config_mumu,
                                    steps=spec.steps, impacts=spec.impacts, timeout=spec.timeout,
                                    pico_config=context.pico_config)

    def plan_commands(self, request):
        return self.api.plan_fit(request)

    def preflight(self, request, context):
        """The shapes on disk are checked only when no histograms stage of this run makes (or made) them."""
        return self.api.preflight_fit(request, check_shapes=not context.artifacts('histograms', kind='shapes'))

    def execute(self, request, logdir, progress):
        return self.api.fit(request, logdir, progress)

    def config_file(self, value):
        return self.api.config_file(value)

    def status(self, spec, stage_record):
        """The fitted values of the finished fit (read from run.json; nothing is opened)."""
        return [dict(value, era=artifact['era'], jet_wp=artifact['jet_wp'], ele_wp=artifact['ele_wp'])
                for artifact in stage_record.artifacts if artifact.get('kind') == 'fit'
                for value in artifact.get('values', [])] or None

    def points(self, spec, context):
        """The (era, jet WP, electron WP) points: from the recipe, or from the upstream shapes."""
        shapes = context.artifacts('histograms', kind='shapes')
        if spec.jet_wps:
            eras = spec.eras or tuple(dict.fromkeys(shape['era'] for shape in shapes))
            return tuple(product(eras, spec.jet_wps, spec.ele_wps))
        configs = {}
        for shape in shapes:
            if not spec.eras or shape['era'] in spec.eras:
                point = (shape['era'], shape['jet_wp'], shape['ele_wp'])
                configs.setdefault(point, set()).add(shape['config'])
        return tuple(point for point, found in configs.items() if {spec.config, spec.config_mumu} <= found)


# =============================================================================
# ================================= CONTRACT ==================================


@dataclass(frozen=True)
class FitSpec:
    """Recipe options: the mutau fit config and the mumu control-region config (bundle files, or relative to
    Fitter/), the points
    (empty jet_wps and ele_wps: those of the histograms stage), the steps to run, and whether to run impacts."""
    config:      str = DEFAULT_CONFIGS[0]
    config_mumu: str = DEFAULT_CONFIGS[1]
    eras:        Tuple[str, ...] = ()
    jet_wps:     Tuple[str, ...] = ()
    ele_wps:     Tuple[str, ...] = ()
    steps:       Tuple[str, ...] = STEPS
    impacts:     bool = True
    timeout:     Optional[float] = None   # seconds per command; None: no limit

    def __post_init__(self):
        for name in ('eras', 'jet_wps', 'ele_wps', 'steps'):
            object.__setattr__(self, name, as_strings(getattr(self, name)))
        if bool(self.jet_wps) != bool(self.ele_wps):
            raise ValueError("give both jet_wps and ele_wps, or neither (then the histograms stage's are used)")
        unknown = [step for step in self.steps if step not in STEPS]
        if unknown or not self.steps:
            raise ValueError("unknown step %r (steps: %s)" % (unknown[0] if unknown else None, ', '.join(STEPS)))

    def request_dict(self):
        """The options (saved in run.json)."""
        return spec_to_dict(self)


FitSpec._paths = ('config', 'config_mumu')  # resolved against the bundle (bundle.py)
FitStage.Spec = FitSpec
