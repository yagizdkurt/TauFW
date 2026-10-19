# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Control histograms: the filled histograms of fillhists.py, written to a file that the Plotter draws (CL §21, S3).

    entry = stack_entry(stack, variable, selection)      after SampleSet.getstack, BEFORE the stack is drawn
    write_control_hists(path, entries, channel, era, lumi, cme, tag)

stack_entry() copies the histograms of a Stack as they were filled (Stack.draw changes them: the data histogram
becomes a graph, variable bins are divided by their width) and takes the drawing attributes of the variable in the
context of the selection. write_control_hists() writes them with TauFW.Utilities.HistFile. The file is the
contract docs/contracts/control-histograms.md ("taufw.control_histograms", version 2):

    file meta:   {contract, version, channel, era, lumi, cme, tag}   lumi, cme: of the normalisation (version 2, CL §26)
    entry:       path '<selection filename>/<variable filename>', in the order the stacks were made
      groups:    data (0 or 1 histogram), exp (stack order), sig
      meta:      {selection: {name, title, cut}, variable: {the DRAWING_ATTRIBUTES}}

Nothing here changes how histograms are filled; fillhists.py writes the file only with --hists.

Public API: stack_entry, write_control_hists, drawing_attributes, normalisation_lumi, CONTRACT, VERSION,
            DRAWING_ATTRIBUTES
"""
from TauFW.Utilities.HistFile import HistFileEntry, write_histfile

__all__ = ['stack_entry', 'write_control_hists', 'drawing_attributes', 'normalisation_lumi', 'CONTRACT', 'VERSION',
           'DRAWING_ATTRIBUTES']

CONTRACT = "taufw.control_histograms"  # what the file is (docs/contracts/control-histograms.md)
VERSION  = 2                           # raised when the meaning of the file's content changes (2: lumi, cme)

# What the drawing code reads from a variable (TauFW.Utilities.Drawing Plot.__init__, Plot.py:89-106).
DRAWING_ATTRIBUTES = ("filename", "title", "xmin", "xmax", "ymin", "ymax", "rmin", "rmax", "ratiorange",
                      "binlabels", "logx", "logy", "ymargin", "logyrange", "position", "ncols", "dividebins")


def drawing_attributes(variable):
    """{attribute: value} of the DRAWING_ATTRIBUTES of a Variable, as they are now (after changecontext)."""
    return {name: getattr(variable, name) for name in DRAWING_ATTRIBUTES}


def stack_entry(stack, variable, selection):
    """A HistFileEntry with copies of the stack's histograms as filled. Call it right after SampleSet.getstack,
    before stack.draw(): getstack has set the variable's context for this selection, and draw() changes the
    histograms. The copies keep the names (and every attribute) of the originals; the originals are untouched."""
    data = [_copy(stack.datahist)] if stack.datahist else []
    groups = {"data": data, "exp": [_copy(hist) for hist in stack.exphists],
              "sig": [_copy(hist) for hist in stack.sighists]}
    meta = {"selection": {"name": selection.filename, "title": selection.title, "cut": selection.selection},
            "variable": drawing_attributes(variable)}
    return HistFileEntry("%s/%s" % (selection.filename, variable.filename), groups, meta)


def normalisation_lumi(samples):
    """The integrated luminosity the MC samples were normalised with: the lumi of every sample (merged samples are
    looked into), None if there is none; ValueError if they differ (CL §27). samples: SampleSet.mcsamples."""
    found = set()

    def walk(sample):
        children = getattr(sample, 'samples', [sample])
        if not children or children == [sample]:
            found.add(sample.lumi)
        else:
            for child in children:
                walk(child)
    for sample in samples:
        walk(sample)
    if len(found) > 1:
        raise ValueError("the MC samples were normalised with different luminosities: %s" % (sorted(found),))
    return next(iter(found)) if found else None


def write_control_hists(path, entries, channel, era, lumi, cme, tag=""):
    """Write the control histograms of one channel setup and era to `path` (replaced if it exists); returns path.
    lumi [/fb] and cme [TeV] are the ones the samples were normalised with (the Histogrammer's after setera; lumi None
    if the era has none): the Plotter labels the plots with them.
    Two stacks with the same entry path (two variables with the same file name in one selection) are refused: the
    second would replace the first, as its plot would replace the first PNG."""
    paths = [entry.path for entry in entries if isinstance(entry, HistFileEntry)]
    for index, entry_path in enumerate(paths):
        if entry_path in paths[:index]:
            selection, variable = entry_path.rsplit("/", 1)
            raise ValueError("%s: two variables with the file name %r in the selection %r; give them different"
                             " fname= values" % (path, variable, selection))
    meta = {"contract": CONTRACT, "version": VERSION, "channel": channel, "era": str(era), "lumi": lumi, "cme": cme,
            "tag": tag}
    return write_histfile(path, entries, meta)


def _copy(hist):
    """A detached copy with the same name: it does not follow later changes of the original and belongs to no
    ROOT directory (so opening and closing files does not delete it). While copying, new histograms are not added
    to ROOT's current directory, so the copy never replaces the original there (ROOT would warn and unlist it)."""
    import ROOT
    status = ROOT.TH1.AddDirectoryStatus()
    ROOT.TH1.AddDirectory(False)
    try:
        copy = hist.Clone(hist.GetName())
    finally:
        ROOT.TH1.AddDirectory(status)
    copy.SetDirectory(0)
    return copy
