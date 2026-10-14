#! /bin/sh
# =============================================================================
# LEGACY CODE - PRODUCTION
# Original location: PicoProducer/scripts/pico2.py (shell script)
# Previous archive: PicoProducer/python/legacy/scripts/pico2.sh
# Data-taking year: Not fixed
# Year basis: Reusable infrastructure; no single input campaign is specified.
# Purpose: Shell wrapper launching `pico.py` with Python 2.
# Why legacy: Python 2 releases are no longer supported. Originally named `pico2.py`; renamed `.sh`
#     because it is shell code and should not be compiled by SCRAM as Python. Use the maintained
#     `pico.py` entry point with Python 3.
# Status: Unmaintained reference material; review dependencies and paths before reuse.
# =============================================================================

# Author: Izaak Neutelings (May 2023)
# Description: Run pico.py with python2 for backward compatibility
python2 $(dirname $BASH_SOURCE)/pico.py $@