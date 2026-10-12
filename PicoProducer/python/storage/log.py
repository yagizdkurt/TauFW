# Author: Izaak Neutelings (May 2020)
"""The shared 'Storage' logger of the storage and datasets packages.

One instance is shared on purpose: `pico.py -v N` sets its verbosity once for every storage
adapter, sample and DAS query.
"""
from TauFW.common.tools.log import Logger

__all__ = ['LOG']

LOG = Logger('Storage')
