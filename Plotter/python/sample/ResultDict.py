# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""BACKWARD COMPATIBILITY (CL §24): TauFW.Plotter.sample.ResultDict is now TauFW.Histogrammer.sample.ResultDict.

The Plotter of before October 2026 became the Histogrammer; this old module name is an alias of the new module.
Importing it gives the very same module object (same functions, classes, loggers and module state such as the era
and luminosity of setera), so old scripts behave exactly as before. New code imports TauFW.Histogrammer.sample.ResultDict.
Deleted at the migration point (docs/Refactor-2025/TODO.md §8); see Plotter/README.md.
"""
import sys

import TauFW.Histogrammer.sample.ResultDict as _module

sys.modules[__name__] = _module  # the old name now refers to the new module itself
