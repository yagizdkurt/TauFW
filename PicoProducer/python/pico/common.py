# Author: Izaak Neutelings (February 2022)
"""Shared state of the pico.py command implementations (pico.config, pico.run, pico.job).

CONFIG is the global configuration, loaded once on first import (scripts/pico.py imports this module at startup).
Importing this module does not change the working directory: scripts/pico.py does that explicitly.
"""
from TauFW.common.tools.log import Logger
import TauFW.PicoProducer.tools.config as GLOB
CONFIG = GLOB.getconfig(verb=0) # load once
LOG    = Logger()
