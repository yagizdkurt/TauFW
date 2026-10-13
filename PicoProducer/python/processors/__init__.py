"""DEPRECATED alias of TauFW.PicoProducer.workers (``processors/`` was renamed to ``workers/`` in Part 5).

This package exists only for backward compatibility and adds no functionality. Use instead:

    from TauFW.PicoProducer.workers import moddir, ensuredir                 # was ...processors
    from TauFW.PicoProducer.workers.Bookkeeper import Bookkeeper             # was ...processors.Bookkeeper
    python/workers/picojob.py ...                                            # was python/processors/picojob.py

What is kept working (see README.md in this directory):
  - ``import TauFW.PicoProducer.processors``: re-exports the names of ``workers`` (``moddir`` is the workers
    directory, where the keep_and_drop_*.txt files are).
  - ``TauFW.PicoProducer.processors.Bookkeeper``: the same module object as ``workers.Bookkeeper``.
  - ``python/processors/picojob.py`` and ``skimjob.py``: run the workers' scripts with the same arguments, so job
    lists written before the rename still run.

Every use prints a FutureWarning (shown by default, unlike DeprecationWarning) naming the replacement.
Deprecated since 2026-10-13; see docs/Refactor-2025.md, section 10 A3, for when it will be removed.
"""
import warnings
from TauFW.PicoProducer.workers import * # noqa: F401,F403  (re-export; workers has no __all__)
from TauFW.PicoProducer.workers import moddir # noqa: F401  (explicit: the most used name)

OLD = __name__                               # TauFW.PicoProducer.processors
NEW = __name__.rsplit('.',1)[0]+'.workers'  # TauFW.PicoProducer.workers


def deprecated(old,new,stacklevel=3):
  """Warn once per call site that `old` is deprecated in favor of `new`."""
  warnings.warn("%s is deprecated; use %s instead (processors/ was renamed to workers/)"%(old,new),
                FutureWarning,stacklevel=stacklevel)


deprecated(OLD,NEW)
