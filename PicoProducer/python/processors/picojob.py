#! /usr/bin/env python
# Description: DEPRECATED forwarder to python/workers/picojob.py, kept so job lists written before
#   processors/ was renamed to workers/ still run. Same arguments, output and exit status. See README.md.
from _forward import forward
forward(__file__)
