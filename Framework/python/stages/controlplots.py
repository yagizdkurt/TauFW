# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Control plots stage: control-histogram files -> data/MC control plots, through the Plotter API (CL §24, S4).

The second half of the control plots: Plotter/draw.py draws every file of the controlhists stage its input names,
with the same file names and texts as fillhists.py gives its own plots. The Plotter fills nothing, so this stage
has no tuples, eras or channel setups: everything about the histograms is in the files.

    inputs:   hists: the control-histogram files of the controlhists stage the slot names (its control_histograms
              artifacts), or of such a stage of another run ({path: <run_dir>/stages/<id>}, its manifest's
              artifacts); never null (there is no default place of control-histogram files)
    options:  ControlPlotsSpec: the drawing options of draw.py (-F, -p, -T)
    outputs:  one plots artifact per file: {kind: 'plots', era, config, channel, directory, nfiles} (the form of the
              former one-step plots stage); draw.py runs in the stage's directory, so the plots are in
              <run_dir>/stages/<id>/plots/<era>/

The stage runs locally and finishes in one advance() call (see stages/local.py).

Public API:
  ControlPlotsStage(plotter), ControlPlotsSpec
"""
from dataclasses import dataclass
from typing import Optional

from TauFW.Framework.stages.base import spec_to_dict
from TauFW.Framework.stages.local import LocalStage

__all__ = ['ControlPlotsStage', 'ControlPlotsSpec']

KIND = 'control_histograms'  # what the input slot takes (the outputs of the controlhists stage)


# =============================================================================
# =================================== STAGE ===================================


class ControlPlotsStage(LocalStage):
    """Control plots with the Plotter API.
    plotter: a TauFW.Plotter.api.ControlPlots, or any object with the same methods (tests pass a fake one)."""
    name = 'controlplots'
    inputs = {'hists': KIND}
    null_inputs = {}
    outputs = ('plots',)
    group = 'plotter'  # taufw.py init names a copied config <group>_<name> if its name is taken (none here)
    # Spec = ControlPlotsSpec: set at the bottom of this file.

    def request(self, spec, context):
        """The PlotsRequest: the files of the input stage (in a plan: the files it plans to write) and the drawing
        options. Raises ValueError if the input stage has no files to draw."""
        artifacts = context.input_artifacts('hists', kind=KIND)
        if not artifacts:
            raise ValueError("no control-histogram files to draw: %s has none" % (context.input_name('hists')))
        files = [{'path': artifact['file'], 'era': artifact['era'], 'channel': artifact['channel'],
                  'config': artifact.get('config') or "", 'tag': artifact.get('tag') or ""}
                 for artifact in artifacts]
        return self.api.request(files=files, outdir=self.output_dir(context), **spec.request_dict())

    def plan_commands(self, request):
        return self.api.plan(request)

    def preflight(self, request, context):
        return self.api.preflight(request)

    def execute(self, request, logdir, progress):
        return self.api.make(request, logdir, progress)


# =============================================================================
# ================================= CONTRACT ==================================


@dataclass(frozen=True)
class ControlPlotsSpec:
    """Recipe options: the drawing options of draw.py. What is drawn (eras, channels, variables, selections, the tag
    of the plot names) was decided when the files were filled: the options of the controlhists stage."""
    fraction: bool = False                # -F: fraction stack in the ratio plot
    pdf:      bool = False                # -p: also save a pdf of each plot
    text:     str = ""                    # -T: extra text on the plots
    timeout:  Optional[float] = None      # seconds per draw.py run; None: no limit

    def request_dict(self):
        """The options as the Plotter PlotsRequest fields (saved in run.json)."""
        return spec_to_dict(self)


ControlPlotsSpec._paths = ()  # no files
ControlPlotsStage.Spec = ControlPlotsSpec
