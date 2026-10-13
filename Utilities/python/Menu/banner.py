"""Shared TauFW entry branding. Update VERSION here until release metadata exists."""

VERSION = "V0.0"

# =============================================================================
# ================================ ENTRY BANNER ===============================

_LOGO = (
    r"  _____             ________        __",
    r" |_   _|_ _ _   _  |  ___\ \      / /",
    r"   | |/ _` | | | | | |_   \ \ /\ / /",
    r"   | | (_| | |_| | |  _|   \ V  V /",
    r"   |_|\__,_|\__,_| |_|      \_/\_/",
)
WIDTH = 78
_LOGO = tuple(line.ljust(max(map(len, _LOGO))) for line in _LOGO)
# The two tau branches wrap around the unchanged wordmark. Spell out "anti-"
# so neutrino labels do not need combining overbars in the terminal grid.
_TRACKS = (
    "      .            /",
    "         '        /",
    "  H ~~~~~~~~>----*",
    "         .        \\",
    "      '            \\",
)
_SCENE = (
    "                                   μ⁻",
    "                                  /",
    "                      τ⁻ --------*---> anti-νμ",
    "                     /            \\",
    "                    /              ντ",
    *(track.ljust(25) + line for track, line in zip(_TRACKS, _LOGO)),
    "                    \\              hadrons",
    "                     \\             /",
    "                      τ⁺ --------*---> π⁺",
    "                                  \\",
    "                                   anti-ντ",
)
FULL = tuple(
    ["*" * WIDTH]
    + ["*" + line.center(WIDTH - 2) + "*" for line in
       (*(line.ljust(WIDTH - 2) for line in _SCENE),
        "Tau analysis framework", VERSION, "")]
    + ["*" * WIDTH]
)
BOXED = tuple(
    ["*" * 64]
    + ["*" + line.center(62) + "*" for line in
       ("", *_LOGO, "", "Tau analysis framework", VERSION, "")]
    + ["*" * 64]
)
COMPACT = ("TauFW", "Tau analysis framework", VERSION)
