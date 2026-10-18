# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Histogram files: ordered groups of ROOT histograms plus JSON metadata, the exchange format between modules.

    from TauFW.Utilities.HistFile import write_histfile, read_histfile, HistFileEntry
    write_histfile("hists/2025/mutau.root", [HistFileEntry("baseline/m_vis", {"exp": [h1, h2]}, {"title": "m"})],
                   meta={"era": "2025"})
    content = read_histfile("hists/2025/mutau.root")   # HistFile: content.meta, content.entries (detached copies)

The layout is described in _histfile.py. ROOT is imported only when a file is written or read.
"""

from ._histfile import write_histfile, read_histfile, HistFile, HistFileEntry, HistFileError, FORMAT

__all__ = ['write_histfile', 'read_histfile', 'HistFile', 'HistFileEntry', 'HistFileError', 'FORMAT']
