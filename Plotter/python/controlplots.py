# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Control plots drawn from a control-histogram file of the Histogrammer (changelog §21, S3).

The Plotter does not fill histograms: it reads the file that `Histogrammer/fillhists.py --hists` wrote
(docs/contracts/control-histograms.md) and draws each stack with the shared drawing library, exactly as
fillhists.py (the former Plotter/plot.py) draws it from memory:

    read_control_hists(path)                       ─▶ ControlHists (channel, era, tag, entries)
    draw_control_plots(path, outdir, ...)          ─▶ the plot files, one stack per entry (draw.py)
      make_stack(entry)                            ─▶ a TauFW.Utilities.Drawing Stack of the entry's histograms
      draw_stack(stack, hists, entry, outdir, ...) ─▶ draws, writes the legend and the text, saves (not closed)

What the plots look like is decided here, from the facts in the file: the file names
`<variable>_<channel short>-<selection>-<era><tag>.png` (plot_name) and the text `<channel>: <selection title>`
(plot_text) are the rules of plot.py, kept character for character.

Inputs:  a control-histogram file (contract taufw.control_histograms, version 2: with the lumi and cme of the
         normalisation, which the CMS label shows).
Outputs: <outdir>/<variable>_<channel short>-<selection>-<era><tag>.png (and .pdf on request).

This module imports no other TauFW stage, only TauFW.Utilities; ROOT is imported when a file is read or drawn.

Public API:
  read_control_hists, draw_control_plots, make_stack, draw_stack, plot_name, plot_text
  ControlHists, ControlEntry, DrawingVariable, ControlHistsError, CONTRACT, VERSION, DRAWING_ATTRIBUTES
"""
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

from TauFW.Utilities.HistFile import read_histfile

__all__ = ['read_control_hists', 'draw_control_plots', 'make_stack', 'draw_stack', 'plot_name', 'plot_text',
           'ControlHists', 'ControlEntry', 'DrawingVariable', 'ControlHistsError', 'CONTRACT', 'VERSION',
           'DRAWING_ATTRIBUTES']


# =============================================================================
# ================================= CONTRACT ==================================


CONTRACT = "taufw.control_histograms"  # the file this module reads (docs/contracts/control-histograms.md)
VERSION  = 2                           # the version of the contract it understands (2: lumi, cme; CL §26)

# The attributes of a variable that the drawing code reads (TauFW.Utilities.Drawing Plot.__init__); the file
# carries exactly these, in the context of the entry's selection.
DRAWING_ATTRIBUTES = ("filename", "title", "xmin", "xmax", "ymin", "ymax", "rmin", "rmax", "ratiorange",
                      "binlabels", "logx", "logy", "ymargin", "logyrange", "position", "ncols", "dividebins")


class ControlHistsError(Exception):
    """A file that is not a control-histogram file this module can draw."""


class DrawingVariable:
    """What the drawing code needs of a variable, read from the file: the DRAWING_ATTRIBUTES, nothing else.

    It replaces the Histogrammer's Variable when drawing. The drawing library recognizes a variable by its
    attributes; getedge() is among them but is only called by Plot.drawbins, which control plots do not use."""

    def __init__(self, attributes):
        missing = [name for name in DRAWING_ATTRIBUTES if name not in attributes]
        if missing:
            raise ControlHistsError("drawing attributes missing in the file: %s" % (", ".join(missing)))
        for name in DRAWING_ATTRIBUTES:
            setattr(self, name, attributes[name])

    def getedge(self, index):
        raise ControlHistsError("bin edges are not in a control-histogram file (Plot.drawbins needs a Variable)")

    def __repr__(self):
        return "<DrawingVariable(%r)>" % (self.filename)


@dataclass
class ControlEntry:
    """One stack: the selection (name, title, cut), the variable's drawing attributes, the histograms as filled."""
    selection_name: str
    selection_title: str
    selection_cut: str
    variable: DrawingVariable
    data: object        # the data histogram, or None
    exp: List           # expected processes, in stack order
    sig: List           # signals

    @property
    def hists(self):
        """All histograms, data first: the order of Stack.hists."""
        return ([self.data] if self.data else []) + self.exp + self.sig


@dataclass
class ControlHists:
    """The content of a control-histogram file."""
    channel: str
    era: str
    tag: str
    entries: Tuple[ControlEntry, ...]
    lumi: Optional[float] = None   # [/fb] of the normalisation; None: the era has none (no lumi in the label)
    cme: Optional[float] = None    # [TeV]


# =============================================================================
# ================================== READING ==================================


def read_control_hists(path):
    """The ControlHists of a file written by fillhists.py --hists (ControlHistsError for another file)."""
    content = read_histfile(path)
    meta = content.meta
    if meta.get("contract") != CONTRACT or meta.get("version") != VERSION:
        again = (" (version 1 had no lumi: run fillhists.py --hists, or the controlhists stage, again)"
                 if meta.get("contract") == CONTRACT and meta.get("version") == 1 else "")
        raise ControlHistsError("%s is %r version %r; this Plotter draws %s version %d%s"
                                % (path, meta.get("contract"), meta.get("version"), CONTRACT, VERSION, again))
    _require(meta, ("channel", "era", "lumi", "cme", "tag"), path)
    entries = []
    for entry in content.entries:
        data = entry.groups.get("data", [])
        if len(data) > 1:
            raise ControlHistsError("%s: entry %s has %d data histograms" % (path, entry.path, len(data)))
        _require(entry.meta, ("selection", "variable"), "%s: entry %s" % (path, entry.path))
        selection = entry.meta["selection"]
        _require(selection, ("name", "title", "cut"), "%s: entry %s, selection" % (path, entry.path))
        entries.append(ControlEntry(selection["name"], selection["title"], selection["cut"],
                                    DrawingVariable(entry.meta["variable"]), data[0] if data else None,
                                    list(entry.groups.get("exp", [])), list(entry.groups.get("sig", []))))
    return ControlHists(meta["channel"], meta["era"], meta["tag"], tuple(entries), meta["lumi"], meta["cme"])


def _require(meta, keys, where):
    missing = [key for key in keys if not isinstance(meta, dict) or key not in meta]
    if missing:
        raise ControlHistsError("%s: no %s in the metadata (%s version %d)" % (where, ", ".join(missing), CONTRACT,
                                                                               VERSION))


# =============================================================================
# ================================ PRESENTATION ===============================


def plot_name(channel, selection_name, era, outdir):
    """The file name pattern of a plot ($VAR and $TAG are filled by Plot.saveas): plot.py's rule."""
    return "%s/$VAR_%s-%s-%s$TAG" % (outdir, channel.replace('mu', 'm').replace('tau', 't'), selection_name, era)


def plot_text(channel, selection_title, extratext=""):
    """The text in the corner of a plot: '<channel in LaTeX>: <selection title>[, <extra text>]' (plot.py's rule)."""
    text = "%s: %s" % (channel.replace('mu', "#mu").replace('tau', "#tau_{h}"), selection_title)
    if extratext:
        text += ("" if '\n' in extratext[:3] else ", ") + extratext
    return text


# =============================================================================
# ================================== DRAWING ==================================


def make_stack(entry):
    """A Stack of the entry's histograms (the histograms themselves, not copies, as fillhists.py does)."""
    from TauFW.Utilities.Drawing.Stack import Stack
    return Stack(entry.variable, entry.data, entry.exp, entry.sig)


def draw_stack(stack, hists, entry, outdir, fraction=False, exts=('png',), extratext=""):
    """Draw a stack as fillhists.py does: the stack with its ratio panel, the legend, the text, then save it to
    plot_name(...) with the file's tag. The stack is not closed (the caller may look at stack.canvas first)."""
    stack.draw(fraction=fraction)
    stack.drawlegend()
    stack.drawtext(plot_text(hists.channel, entry.selection_title, extratext))
    stack.saveas(plot_name(hists.channel, entry.selection_name, hists.era, outdir), ext=list(exts), tag=hists.tag)


def draw_control_plots(path, outdir="plots/$ERA", fraction=False, pdf=False, extratext=""):
    """Draw every stack of a control-histogram file into `outdir` ($ERA and $CHANNEL replaced; made if needed).
    Sets the CMS label of the file's era, lumi and cme first (TauFW.Utilities.Drawing.CMSStyle), as setera() did for
    plot.py with the same values.
    Returns the ControlHists that were drawn."""
    import TauFW.Utilities.Drawing.CMSStyle as CMSStyle
    hists = read_control_hists(path)
    outdir = outdir.replace('$CHANNEL', hists.channel).replace('$ERA', hists.era)
    os.makedirs(outdir, exist_ok=True)
    CMSStyle.setCMSEra(hists.era, lumi=hists.lumi, cme=hists.cme)
    exts = ['png', 'pdf'] if pdf else ['png']
    for entry in hists.entries:
        stack = make_stack(entry)
        draw_stack(stack, hists, entry, outdir, fraction=fraction, exts=exts, extratext=extratext)
        stack.close(keep=True)
    return hists
