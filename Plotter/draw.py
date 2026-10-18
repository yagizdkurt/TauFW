#!/usr/bin/env python3
# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Draw the control plots of control-histogram files written by Histogrammer/fillhists.py --hists.

    python3 Histogrammer/fillhists.py -y 2025 -c mutau --hists     # fills, writes hists/2025/mutau.root
    python3 Plotter/draw.py hists/2025/mutau.root                  # draws plots/2025/*.png from that file

One plot per stack in the file, named and labelled as fillhists.py names and labels its own plots, so the same
options give the same files. The options are the drawing options of fillhists.py (-F, -p, -T); everything about
the histograms (samples, selections, variables, the era's luminosity) is in the file.
"""
import sys
from argparse import ArgumentParser

from TauFW.Plotter.controlplots import draw_control_plots


def parse(argv):
    parser = ArgumentParser(prog="draw", description=__doc__.split("\n")[0], epilog="Inputs: fillhists.py --hists.")
    parser.add_argument('files', nargs='+', metavar='FILE', help="control-histogram files (hists/<era>/<setup>.root)")
    parser.add_argument('-o', '--outdir', default="plots/$ERA",
                        help="where the plots go; $ERA and $CHANNEL are replaced (default: %(default)s)")
    parser.add_argument('-F', '--fraction', action='store_true', help="include the fraction stack in the ratio plot")
    parser.add_argument('-p', '--pdf', action='store_true', help="also save a pdf of each plot")
    parser.add_argument('-T', '--text', default="", help="extra text on the plots")
    parser.add_argument('-v', '--verbose', dest='verbosity', type=int, nargs='?', const=1, default=0,
                        help="verbosity of the drawing code")
    return parser.parse_args(argv)


def main(argv):
    args = parse(argv)
    from TauFW.Utilities.Drawing import LOG
    LOG.verbosity = args.verbosity
    for path in args.files:
        hists = draw_control_plots(path, outdir=args.outdir, fraction=args.fraction, pdf=args.pdf,
                                   extratext=args.text)
        print(">>> %s: %d plot(s) of %s, %s" % (path, len(hists.entries), hists.channel, hists.era))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
