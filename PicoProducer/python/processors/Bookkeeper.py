"""DEPRECATED alias of TauFW.PicoProducer.workers.Bookkeeper; see this package's README.md.

Replaces itself in sys.modules with the real module, so classes and functions are the same objects
(``processors.Bookkeeper.Bookkeeper is workers.Bookkeeper.Bookkeeper``) and isinstance checks keep working.
"""
import sys
import importlib
from TauFW.PicoProducer.processors import NEW, deprecated

_name = __name__.rsplit('.',1)[1]                        # Bookkeeper
deprecated(__name__,NEW+'.'+_name)
sys.modules[__name__] = importlib.import_module(NEW+'.'+_name)
