# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Checks of an output directory before the scripts of a module API run in it.

The TauFW Framework runs the Plotter and Fitter scripts in a stage's output directory
(<run_dir>/stages/<id>/). Before they start, the API checks two things:
  - the directory is empty: files left by an interrupted attempt would mix with the new ones (some scripts
    update ROOT files, others glob everything they find);
  - the PicoProducer configuration has an absolute picodir: a relative one would be read relative to the
    output directory, not to where the tuples are.
"""
import json
import os
import posixpath

__all__ = ["output_dir_problems"]


def output_dir_problems(outdir, pico_config=None):
    """The problems of running scripts in `outdir` (a list of messages; empty: none). pico_config: the PicoProducer
    configuration the scripts read $PICODIR from (None, or unreadable: not checked)."""
    problems = []
    if os.path.isdir(outdir) and os.listdir(outdir):
        problems.append("output directory %s is not empty (an interrupted attempt?): remove it, or start a new run"
                        % (outdir))
    picodir = _picodir(pico_config) if pico_config else None
    if picodir and not (posixpath.isabs(picodir) or os.path.isabs(picodir) or picodir.startswith('$')
                        or '://' in picodir):
        problems.append("picodir %r of %s is relative: the scripts would look for the tuples relative to %s"
                        % (picodir, pico_config, outdir))
    return problems


def _picodir(pico_config):
    """The picodir of a PicoProducer configuration (JSON), or None if it cannot be read."""
    try:
        with open(pico_config) as stream:
            return json.load(stream).get('picodir')
    except (OSError, ValueError, AttributeError):
        return None
