# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Records of the public Plotter API: what a caller asks for (changelog §21, S4).

  HistFileInput  one control-histogram file to draw, with the facts the plan needs before the file exists
  PlotsRequest   the files to draw and the drawing options of Plotter/draw.py (-F, -p, -T)
  plan() and make() return a CommandPlan and a RunReport (TauFW.Utilities.Process).

Plots artifact (a JSON-ready dict): {kind: 'plots', era, config, channel, directory, nfiles}, the same form as the
plots of the former one-step plots stage, so whatever reads them (a python step, the menu) reads both.

Public API: the records above.
"""
from dataclasses import dataclass
from typing import Optional, Tuple

__all__ = ['HistFileInput', 'PlotsRequest']


# =============================================================================
# ================================= REQUESTS ==================================


@dataclass(frozen=True)
class HistFileInput:
    """One control-histogram file (contract taufw.control_histograms) and what it holds.

    The file itself says era, channel and tag too, but reading it needs ROOT, and a plan is made before the file
    exists. So the caller passes them: the Histogrammer's ControlHists names them on its artifacts
    {kind: control_histograms, era, config, channel, tag, file}, and from_artifact() takes such a dict.
    path:    the file (absolute, or relative to the directory draw.py runs in)
    era:     the era of the histograms; draw.py writes the plots to plots/<era>/
    channel: the channel of the setup (mutau, mumu, ...): the plot names use its short form (mt, mm, ...)
    config:  the channel setup the file was filled with, for the artifact only
    tag:     the setup's tag plus fillhists.py -t: the end of every plot name"""
    path:    str
    era:     str
    channel: str
    config:  str = ""
    tag:     str = ""

    def __post_init__(self):
        for name in ('path', 'era', 'channel', 'config', 'tag'):
            object.__setattr__(self, name, str(getattr(self, name)))
        for name in ('path', 'era', 'channel'):
            if not getattr(self, name):
                raise ValueError("HistFileInput: %s must not be empty" % (name))

    @classmethod
    def from_artifact(cls, artifact):
        """The input of a control_histograms artifact of the Histogrammer (a dict); raises ValueError otherwise."""
        if artifact.get('kind') != 'control_histograms':
            raise ValueError("not a control_histograms artifact: %r" % (artifact,))
        return cls(path=artifact['file'], era=artifact['era'], channel=artifact['channel'],
                   config=artifact.get('config') or "", tag=artifact.get('tag') or "")


@dataclass(frozen=True)
class PlotsRequest:
    """Control plots: one Plotter/draw.py run per control-histogram file.
    files:    the files to draw (HistFileInput, or dicts with the same keys); not empty.
    fraction, pdf, text: draw.py -F (fraction stack in the ratio plot), -p (a pdf next to each png), -T (extra
              text on the plots); the drawing options of fillhists.py, which keeps them for its own drawing.
    outdir:   the directory draw.py runs in and writes plots/<era>/ to (None: Plotter/, as a user runs it)."""
    files:    Tuple[HistFileInput, ...]
    fraction: bool = False
    pdf:      bool = False
    text:     str = ""
    timeout:  Optional[float] = None   # seconds per command
    outdir:   Optional[str] = None     # working directory of draw.py (None: Plotter/)

    def __post_init__(self):
        files = tuple(item if isinstance(item, HistFileInput) else HistFileInput(**item) for item in self.files)
        if not files:
            raise ValueError("PlotsRequest: files must not be empty")
        object.__setattr__(self, 'files', files)
