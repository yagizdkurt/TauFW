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
WIDTH = 64
_LOGO = tuple(line.ljust(max(map(len, _LOGO))) for line in _LOGO)
FULL = tuple(
    ["*" * WIDTH]
    + ["*" + line.center(WIDTH - 2) + "*" for line in
       ("", *_LOGO, "", "Tau analysis framework", VERSION, "")]
    + ["*" * WIDTH]
)
COMPACT = ("TauFW", "Tau analysis framework", VERSION)
