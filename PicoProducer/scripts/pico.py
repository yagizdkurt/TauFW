#! /usr/bin/env python3
# Author: Izaak Neutelings (April 2020)
"""pico.py: central script to process nanoAOD for skimming or analysis, locally or on a batch system.

  pico.py list|get|set|rm|write|channel|era   configuration          (cli/config.py)
  pico.py run                                 local test runs        (cli/jobs.py -> api.PicoProducer.run_local)
  pico.py submit|resubmit|status              batch jobs             (cli/jobs.py -> api.PicoProducer)
  pico.py hadd|haddclean|clean                merge and clean up     (cli/jobs.py -> api.PicoProducer)

All relative paths (config, samples, workers, job output) are relative to PicoProducer/; this script changes
into that directory first. The parser and the commands live in TauFW.PicoProducer.cli.
"""
import os, sys
try:
  from TauFW.PicoProducer import basedir
  from TauFW.PicoProducer.storage.log import LOG as SLOG
except ImportError as err:
  print("\033[1m\033[31mImportError for TauFW modules: Please check if you compiled with `scram b`."
        "Releases older than CMSSW_12_X (python2) are no longer supported.\033[0m")
  raise err
os.chdir(basedir) # all relative paths (config, samples, workers, job output) are relative to PicoProducer/
from TauFW.PicoProducer.cli.common import CONFIG # loads config/config.json (created or repaired if needed)
from TauFW.PicoProducer.cli.parser import build_parser, parse_args
from TauFW.PicoProducer.cli import dispatch


if __name__ == "__main__":
  args = parse_args(build_parser(CONFIG),sys.argv[1:])
  if args.verbosity>=2:
    SLOG.setverbosity(args.verbosity-1)
  dispatch(args)
  print(">>> Done!")
