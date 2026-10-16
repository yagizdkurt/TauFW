# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Checks of an output directory, and of the tuple pattern, before the scripts of a module API run.

The TauFW Framework runs the Plotter and Fitter scripts in a stage's output directory
(<run_dir>/stages/<id>/). Before they start, the API checks:
  - the directory is empty: files left by an interrupted attempt would mix with the new ones (some scripts
    update ROOT files, others glob everything they find);
  - where the tuples are is absolute: the tuple pattern given to the scripts (--tuples), or else the picodir of the
    PicoProducer configuration; a relative one would be read relative to the output directory, not to where the
    tuples are.
tuple_pattern_problems() checks a tuple pattern on its own: the scripts (Plotter's getsampleset) fill only some
$KEYS of it.
"""
import json
import os
import posixpath
import re

__all__ = ["output_dir_problems", "tuple_pattern_problems", "TUPLE_PATTERN_KEYS"]

TUPLE_PATTERN_KEYS = ('ERA', 'GROUP', 'SAMPLE', 'CHANNEL', 'TAG')  # what Plotter's getsampleset fills
KEYEXP = re.compile(r"\$([A-Za-z_]\w*)")


def output_dir_problems(outdir, pico_config=None, tuples=None):
    """The problems of running scripts in `outdir` (a list of messages; empty: none).
    tuples: the tuple pattern the scripts are given (--tuples); then pico_config is not read.
    pico_config: the PicoProducer configuration the scripts read $PICODIR from (None, or unreadable: not checked)."""
    problems = []
    if os.path.isdir(outdir) and os.listdir(outdir):
        problems.append("output directory %s is not empty (an interrupted attempt?): remove it, or start a new run"
                        % (outdir))
    if tuples:
        if not (_absolute(tuples, variable=False) or tuples.startswith('<')):  # $ERA/... would be relative;
            # '<...>' is a placeholder of a plan before the run exists (e.g. '<run_dir>/stages/production/$ERA')
            problems.append("tuple pattern %r is relative: the scripts would look for the tuples relative to %s"
                            % (tuples, outdir))
        return problems
    picodir = _picodir(pico_config) if pico_config else None
    if picodir and not _absolute(picodir):
        problems.append("picodir %r of %s is relative: the scripts would look for the tuples relative to %s"
                        % (picodir, pico_config, outdir))
    return problems


def tuple_pattern_problems(tuples):
    """The problems of a tuple pattern (a list of messages; empty: none): $KEYS that the scripts do not fill
    (e.g. $DAS, which only PicoProducer fills when it writes)."""
    rest = tuples
    for key in TUPLE_PATTERN_KEYS:  # replaced as plain text, like repkey: $SAMPLE_$CHANNEL is two keys
        rest = rest.replace('$' + key, '')
    unknown = list(dict.fromkeys(KEYEXP.findall(rest)))
    if not unknown:
        return []
    return ["tuple pattern %s has %s, which the scripts do not fill (they fill $%s)"
            % (tuples, ', '.join('$' + key for key in unknown), ', $'.join(TUPLE_PATTERN_KEYS))]


def _absolute(path, variable=True):
    """Absolute on lxplus or here, a URL, or (variable) a $VARIABLE such as $PICODIR."""
    return (posixpath.isabs(path) or os.path.isabs(path) or '://' in path
            or (variable and path.startswith('$')))


def _picodir(pico_config):
    """The picodir of a PicoProducer configuration (JSON), or None if it cannot be read."""
    try:
        with open(pico_config) as stream:
            return json.load(stream).get('picodir')
    except (OSError, ValueError, AttributeError):
        return None
