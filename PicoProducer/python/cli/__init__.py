"""Command line of PicoProducer (scripts/pico.py): parser, dispatch, and one module per group of commands.

  pico.py ARGS ─▶ parser.parse_args ─▶ dispatch(args) ─▶ config.main_*   configuration (list, get, set, ...)
                                                     └▶ jobs.main_*     run, submit, status, hadd, ... (via the API)

The command modules are imported only when their subcommand runs.

Public API:
  dispatch(args)       run the command of a parsed namespace
  COMMANDS             subcommand -> 'module:function' (relative to this package)
"""
from importlib import import_module

__all__ = ['dispatch', 'COMMANDS']

COMMANDS = {
  'install':   'install:main_install',
  'list':      'config:main_list',
  'get':       'config:main_get',
  'set':       'config:main_set',
  'write':     'config:main_write',
  'channel':   'config:main_link',
  'era':       'config:main_link',
  'rm':        'config:main_rm',
  'run':       'jobs:main_run',
  'submit':    'jobs:main_submit',
  'resubmit':  'jobs:main_submit',
  'status':    'jobs:main_status',
  'hadd':      'jobs:main_status',
  'haddclean': 'jobs:main_status',
  'clean':     'jobs:main_status',
}


def dispatch(args):
  """Run the command of args.subcommand."""
  command = COMMANDS.get(args.subcommand) # BUGS P13: 'install' also printed "not implemented"
  if command:
    module, function = command.split(':')
    getattr(import_module("TauFW.PicoProducer.cli."+module),function)(args)
  else:
    print(">>> subcommand '%s' not implemented!"%(args.subcommand))
