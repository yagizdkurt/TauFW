"""Quiet-mode output: one line per test file with a status letter per case, captured output shown only for problems."""
from collections import deque
import os
from pathlib import Path
import shutil
import sys

LOGS = Path(__file__).resolve().parents[1] / ".artifacts" / "logs"
RULE = 76
COLORS = {"P": "32", "F": "31", "S": "33"}  # green, red, yellow


def reset_logs(kind):
    """Each quiet run replaces the previous run's logs of the same kind."""
    directory = LOGS / kind
    shutil.rmtree(str(directory), ignore_errors=True)
    directory.mkdir(parents=True)
    return directory


def _color_enabled():
    if os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return False
    if os.name == "nt":
        # Windows consoles need ANSI escape processing switched on explicitly.
        try:
            import ctypes
            kernel = ctypes.windll.kernel32
            handle = kernel.GetStdHandle(-11)
            mode = ctypes.c_uint32()
            return bool(kernel.GetConsoleMode(handle, ctypes.byref(mode))
                        and kernel.SetConsoleMode(handle, mode.value | 0x0004))
        except (AttributeError, OSError):
            return False
    return True


def paint(text, symbol):
    """Color text by status letter (P/F/S) when writing to a terminal."""
    if symbol in COLORS and _color_enabled():
        return "\033[%sm%s\033[0m" % (COLORS[symbol], text)
    return text


def file_groups(items, path, name):
    """[(label, items)] in first-seen order; a file with one selected case is labelled by the case name."""
    groups = {}
    for item in items:
        groups.setdefault(path(item), []).append(item)
    return [(name(members[0]) if len(members) == 1 else key, members) for key, members in groups.items()]


class Lines:
    """Writes 'label ........ PPF', one line per group, a letter as each case finishes."""

    def __init__(self, labels):
        self.width = max([len(label) for label in labels] or [0]) + 3
        self.open = False

    def begin(self, label):
        self.end()
        sys.stdout.write("%s %s " % (label, "." * (self.width - len(label))))
        sys.stdout.flush()
        self.open = True

    def mark(self, symbol):
        sys.stdout.write(paint(symbol, symbol))
        sys.stdout.flush()

    def end(self):
        if self.open:
            sys.stdout.write("\n")
            sys.stdout.flush()
            self.open = False


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
    print("\n" + paint(title.center(RULE, "="), "F"))
    print(body)
    for line in footer:
        print(line)
    print(paint("=" * RULE, "F"), flush=True)
