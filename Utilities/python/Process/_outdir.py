# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Checks of an output directory, and of the tuple pattern, before the scripts of a module API run.

The TauFW Framework runs the Histogrammer and Fitter scripts in a stage's output directory
(<run_dir>/stages/<id>/). Before they start, the API checks:
  - the directory is empty: files left by an interrupted attempt would mix with the new ones (some scripts
    update ROOT files, others glob everything they find);
  - the tuple pattern given to the scripts (--tuples) is absolute: a relative one would be read relative to the
    output directory, not to where the tuples are. (Until CL §37 also the picodir of a PicoProducer configuration,
    which the scripts no longer read when run by an API.)
tuple_pattern_problems() checks a tuple pattern on its own: the scripts (the Histogrammer's getsampleset) fill only some
$KEYS of it.
"""
import os
import posixpath
import re

__all__ = ["output_dir_problems", "tuple_pattern_problems", "TUPLE_PATTERN_KEYS"]

TUPLE_PATTERN_KEYS = ('ERA', 'GROUP', 'SAMPLE', 'CHANNEL', 'TAG')  # what the Histogrammer's getsampleset fills
KEYEXP = re.compile(r"\$([A-Za-z_]\w*)")


def output_dir_problems(outdir, tuples=None):
    """The problems of running scripts in `outdir` (a list of messages; empty: none).
    tuples: the tuple pattern the scripts are given (--tuples), or None (scripts that read no tuples)."""
    problems = []
    if os.path.isdir(outdir) and os.listdir(outdir):
        problems.append("output directory %s is not empty (an interrupted attempt?): remove it, or start a new run"
                        % (outdir))
    if tuples and not (_absolute(tuples) or tuples.startswith('<')):  # $ERA/... would be relative;
        # '<...>' is a placeholder of a plan before the run exists (e.g. '<run_dir>/stages/production/$ERA')
        problems.append("tuple pattern %r is relative: the scripts would look for the tuples relative to %s"
                        % (tuples, outdir))
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


def _absolute(path):
    """Absolute on lxplus or here, or a URL."""
    return posixpath.isabs(path) or os.path.isabs(path) or '://' in path
