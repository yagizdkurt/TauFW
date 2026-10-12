"""Quiet-mode output: one character per case, captured output shown only for problems."""
from collections import deque
from pathlib import Path
import shutil
import sys

LOGS = Path(__file__).resolve().parents[1] / ".artifacts" / "logs"
RULE = 76


def reset_logs(kind):
    """Each quiet run replaces the previous run's logs of the same kind."""
    directory = LOGS / kind
    shutil.rmtree(str(directory), ignore_errors=True)
    directory.mkdir(parents=True)
    return directory


def mark(symbol):
    sys.stdout.write(symbol)
    sys.stdout.flush()


def tail(path, lines):
    """Last lines of a captured log; lines <= 0 returns all of it."""
    try:
        with open(str(path), encoding="utf-8", errors="replace") as stream:
            text = stream.read() if lines <= 0 else "".join(deque(stream, maxlen=lines))
    except OSError:
        return "(no output captured)"
    return text.rstrip("\n") or "(no output)"


def elapsed(seconds):
    if seconds < 60:
        return "%.1fs" % seconds
    return "%dm%02ds" % divmod(int(round(seconds)), 60)


def section(title, body, footer=()):
    title = " %s " % title
    print("\n" + title.center(RULE, "="))
    print(body)
    for line in footer:
        print(line)
    print("=" * RULE, flush=True)
