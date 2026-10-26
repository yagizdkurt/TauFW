# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""LEGACY: where the Histogrammer scripts find the pico tuples when they are not given --tuples.

The scripts' old default (kept for commands typed by hand, CL §37 D1): the `picodir` of the PicoProducer
configuration, $TAUFW_PICO_CONFIG if set, else PicoProducer/config/config.json. The file is read as JSON; the
Histogrammer does not import PicoProducer (the sample library refuses $PICODIR without a tuple pattern). Only the
scripts call this; the Framework and the APIs always give the tuples. Deleted at the migration point (TODO §8).

Differences to PicoProducer's getconfig(), which the scripts used before: no configuration file, or no `picodir`
in it, is an error naming --tuples (getconfig fell back to its built-in default directory); the backup file
config.json.bkp is not read.

Public API:
  script_default_tuples(environ=None, default=None) -> str   the directory pattern, e.g. /eos/.../$ERA/$GROUP
"""
import json
import os
from TauFW.Utilities.Paths import PICO_PRODUCER_ROOT

__all__ = ['script_default_tuples', 'ENVVAR', 'DEFAULT_CONFIG']

ENVVAR = 'TAUFW_PICO_CONFIG' # a PicoProducer configuration chosen by the caller (read-only)
DEFAULT_CONFIG = str(PICO_PRODUCER_ROOT / "config" / "config.json")


def script_default_tuples(environ=None, default=None):
  """The picodir of the PicoProducer configuration ($TAUFW_PICO_CONFIG, else `default`, else DEFAULT_CONFIG).
  Raises IOError if that file does not exist or cannot be read, ValueError if it has no picodir."""
  environ = os.environ if environ is None else environ
  path = environ.get(ENVVAR) or default or DEFAULT_CONFIG
  if not os.path.isfile(path):
    raise IOError("no tuple pattern: --tuples is not given and the PicoProducer configuration %s does not exist "
                  "(give --tuples /path/to/tuples/$ERA/$GROUP)"%(path))
  try:
    with open(path) as file:
      config = json.load(file)
  except ValueError as error:
    raise IOError("no tuple pattern: --tuples is not given and the PicoProducer configuration %s cannot be read "
                  "(%s)"%(path,error))
  picodir = config.get('picodir') if isinstance(config,dict) else None
  if not isinstance(picodir,str) or not picodir:
    raise ValueError("no tuple pattern: --tuples is not given and the PicoProducer configuration %s has no picodir "
                     "(give --tuples /path/to/tuples/$ERA/$GROUP)"%(path))
  return picodir
