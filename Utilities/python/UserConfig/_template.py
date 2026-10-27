# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""The text of a new user config, written by create() (FastSetup, `taufw.py userconfig`).

Which settings the file holds is not decided yet: today it has only its header. To add a setting, add its section to
TEXT below with a comment for every key, and a value guessed from the host where one can be guessed (the guesses of
today's PicoProducer configuration are in PicoProducer/python/settings/defaults.py; this package must not import
them, so copy what is needed). Raise VERSION when the format changes, not when a value does.
"""

HEADER_KEY = "taufw_user"  # the header mapping: version, reviewed
VERSION = 1                # the format of the file


# =============================================================================
# ==== New file ====

def default_text():
    """The YAML text of a new user config: its header, reviewed: false."""
    return TEXT


TEXT = """\
# TauFW user configuration: your personal and machine settings.
#
# Made by the setup (or `python3 taufw.py userconfig`). Git ignores this file and nothing overwrites it.
# Set reviewed to true once you checked the values below: until then, taufw.py check, plan and start warn.
# The settings are added here as TauFW starts to read them.

taufw_user:
  version: %d           # the format of this file (set by TauFW, do not change)
  reviewed: false      # true: you checked this file
""" % (VERSION)
