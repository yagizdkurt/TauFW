# Author: Izaak Neutelings (February 2022)
"""Shared state of the pico.py commands (cli.config, cli.jobs).

CONFIG is the global configuration, loaded once on first import (scripts/pico.py imports this module at startup).
Importing this module does not change the working directory: scripts/pico.py does that explicitly.
"""
from TauFW.common.tools.log import Logger
from TauFW.PicoProducer.settings import getconfig
CONFIG = getconfig(verb=0,write=True) # load once; the CLI creates/repairs config/config.json
LOG    = Logger()
