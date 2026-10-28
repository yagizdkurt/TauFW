# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Public menu presentation and navigation APIs; callers supply operations."""

from ._menu import ConsoleUI
from ._prefetch import Prefetch

__all__ = ["ConsoleUI", "MenuNavigation", "Prefetch"]


def __getattr__(name):
    # The pre-CMSSW installer only needs presentation; navigation uses sibling packages.
    if name == "MenuNavigation":
        from ._navigation import MenuNavigation
        return MenuNavigation
    raise AttributeError("module %r has no attribute %r" % (__name__, name))
