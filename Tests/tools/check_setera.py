#!/usr/bin/env python3
# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Compare the CMS era/lumi text of the Histogrammer's setera() with CMSStyle.setCMSEra() (ModuleIsolationFinalizations
§3 B1; lxplus, needs ROOT).

The Fitter postfit scripts called TauFW.Plotter.sample.utils.setera (an alias of TauFW.Histogrammer.sample.utils)
only to set the text of the drawing: setera sets the Histogrammer's own era/lumi/cme (read by the samples, not by the
drawing) and calls CMSStyle.setCMSEra(str(era), **kwargs). Since B1 the scripts call CMSStyle.setCMSEra directly. For
every era of CMSStyle.lumi_dict, an era given as a number, an unknown era and the scripts' extra="" call, this tool
sets the same starting style, runs each path and compares cmsText, extraText and lumiText.

    cd $CMSSW_BASE/src/TauFW && cmsenv
    python3 Tests/tools/check_setera.py           # SAME and the number of cases, or the differences

Exit status 0 when every case gives the same texts, 1 otherwise. The warning setera prints for an era without a
luminosity is not compared (the drawing does not show it).
"""
import sys


def cases(cms):
    """(era, kwargs) of the comparison: every era with a luminosity, a number, an unknown era, the extra="" call."""
    found = [(era, {}) for era in sorted(cms.lumi_dict, key=str)]
    return found + [(2018, {}), ("2025", {'extra': ""}), ("UL2018", {'extra': ""}), ("1999_unknown", {})]


def texts(cms):
    return (cms.cmsText, cms.extraText, cms.lumiText)


def run(cms, call, era, kwargs):
    """The texts after `call` from the same starting style."""
    cms.setCMSText(cms="CMS", extra="Preliminary", lumiText="")
    call(era, **kwargs)
    return texts(cms)


def main():
    import TauFW.Utilities.Drawing.CMSStyle as cms
    from TauFW.Histogrammer.sample.utils import setera  # the old path (TauFW.Plotter.sample.utils is its alias)
    differences, total = [], 0
    for era, kwargs in cases(cms):
        old = run(cms, setera, era, kwargs)
        new = run(cms, cms.setCMSEra, era, kwargs)
        total += 1
        if old != new:
            differences.append("%r %r: setera %r, setCMSEra %r" % (era, kwargs, old, new))
    for line in differences:
        print(line)
    if differences:
        print("DIFFERENT: %d of %d case(s)" % (len(differences), total))
        return 1
    print("SAME: %d case(s) (cmsText, extraText, lumiText)" % (total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
