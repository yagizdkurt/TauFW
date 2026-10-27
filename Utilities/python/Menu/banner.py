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


DECAY_SECONDS = 1.2


def decay_frame(lines, elapsed):
    """Reveal the full banner's tracks once; keep its frame, wordmark and metadata in place."""
    if elapsed >= DECAY_SECONDS:
        return lines
    frame = [list(line) for line in lines]
    for row, scene in enumerate(_SCENE, start=1):
        for column, character in enumerate(scene):
            if character == " " or (7 <= row <= 11 and column >= 25):
                continue  # The TauFW wordmark is always visible.
            if row == 9:  # Incoming H, ending at the central vertex (column 17).
                appears = 0.3 * (max(0, column - 2) / 15)
            elif 7 <= row <= 11 and column < 17:
                appears = 0.3  # Scattered particles around the central interaction.
            elif column <= 33:  # Both tau branches, ending at their decay vertices.
                appears = 0.3 + 0.45 * ((abs(row - 9) + max(0, column - 17)) / 22)
            else:  # Products grow outward from the upper/lower vertex.
                vertex_row = 3 if row < 9 else 15
                appears = 0.75 + 0.45 * (abs(row - vertex_row) + column - 33) / 16
            if elapsed < appears:
                frame[row][column + 1] = " "  # One column for the banner's left border.
    return tuple("".join(line) for line in frame)


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
