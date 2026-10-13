"""Run a script of python/workers/ in place of its deprecated python/processors/ copy.

Used by the forwarders picojob.py and skimjob.py in this directory, which job lists written before the rename
still name (``python/processors/picojob.py -i ... -o ...``). The worker runs as ``__main__`` in this process with
the same arguments, so its output, output files and exit status are those of
``python/workers/<script> <arguments>``; one deprecation notice goes to stderr first.

This module only needs the standard library: the forwarders import it as a sibling file (the script's directory
is on sys.path), so it works even where TauFW.PicoProducer.processors is not installed as a package.
"""
import os
import sys
import runpy

WORKDIR = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))),'workers')


def worker_path(script):
  """Absolute path of python/workers/<script>."""
  return os.path.join(WORKDIR,os.path.basename(script))


def forward(script):
  """Run python/workers/<basename of script> as __main__ with the current command-line arguments."""
  target = worker_path(script)
  if not os.path.isfile(target):
    sys.exit("ERROR: %s forwards to %s, which does not exist"%(script,target))
  sys.stderr.write("WARNING: python/processors/%s is deprecated; running python/workers/%s instead "
                   "(processors/ was renamed to workers/; resubmit with pico.py to update old job lists)\n"
                   %(os.path.basename(script),os.path.basename(target)))
  sys.stderr.flush()
  sys.argv[0] = target                 # as if the worker had been started directly
  sys.path[0] = os.path.dirname(target)
  runpy.run_path(target,run_name='__main__')
