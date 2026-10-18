# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""BACKWARD COMPATIBILITY (CL §21): TauFW.Plotter.plot.string is now TauFW.Histogrammer.spec.string.

The Plotter of before October 2026 became the Histogrammer; this old module name is an alias of the new module.
Importing it gives the very same module object (same functions, classes, loggers and module state such as the era
and luminosity of setera), so old scripts behave exactly as before. New code imports TauFW.Histogrammer.spec.string.
Deleted at the migration point (docs/Refactor-2025/TODO.md §8); see Plotter/README.md.
"""
import sys

import TauFW.Histogrammer.spec.string as _module

sys.modules[__name__] = _module  # the old name now refers to the new module itself
