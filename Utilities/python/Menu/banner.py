# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Shared TauFW entry branding; callers supply the release label through ConsoleUI.set_version().

VERSION is the fallback for standalone installer/preview screens without a caller's metadata.
"""

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
# Use ASCII particle names so the banner needs no Unicode font or UTF-8 locale.
# The two tau branches wrap around the unchanged wordmark.
_TRACKS = (
    "      .            /",
    "         '        /",
    "  H ~~~~~~~~>----*",
    "         .        \\",
    "      '            \\",
)
_SCENE = (
    "                                   mu-",
    "                                  /",
    "                      tau- ------*---> anti-nu_mu",
    "                     /            \\",
    "                    /              nu_tau",
    "                   /",
    *(track.ljust(25) + line for track, line in zip(_TRACKS, _LOGO)),
    "                   \\",
    "                    \\              hadrons",
    "                     \\             /",
    "                      tau+ ------*---> pi+",
    "                                  \\",
    "                                   anti-nu_tau",
)
# Colored spans overlay the plain banner without adding terminal escape codes.
# Wordmark rows only color the track area to the left of the ASCII letters.
INTERACTIONS = []
for _row, _line in enumerate(_SCENE, start=1):
    _wordmark = 7 <= _row <= 11
    _split = 25 if _wordmark else 33
    _track = _line[:_split]
    if _track.strip():
        INTERACTIONS.append((_row, 1, _track, "higgs" if _row == 9 else "tau"))
    if not _wordmark and _line[_split:].strip():
        INTERACTIONS.append((_row, _split + 1, _line[_split:], "products"))
    for _column, _character in enumerate(_line):
        if _character == "*":
            INTERACTIONS.append((_row, _column + 1, "*", "vertex"))
INTERACTIONS = tuple(INTERACTIONS)
FULL = tuple(
    ["*" * WIDTH]
    + ["*" + line.center(WIDTH - 2) + "*" for line in
       (*(line.ljust(WIDTH - 2) for line in _SCENE), "", "",
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


# =============================================================================
# ================================ SCREEN BADGE ===============================


def _badge(version):
    """The framed wordmark of the operation screens: three rows, the version on the lower edge."""
    inner = max(len("TauFW"), len(version) + 1)
    return ("+" + "-" * (inner + 2) + "+",
            "| " + "TauFW".ljust(inner) + " |",
            "+-" + version + "-" * (inner + 1 - len(version)) + "+")


BADGE = _badge(VERSION)


def branding(version):
    """The same artwork with a caller-supplied version; framed rows keep their width and centering."""
    def replace(lines):
        return tuple(('*' + version.center(len(line) - 2) + '*') if line.strip('* ') == VERSION
                     else version if line == VERSION else line for line in lines)
    return replace(FULL), replace(BOXED), ('TauFW', 'Tau analysis framework', version), _badge(version)
