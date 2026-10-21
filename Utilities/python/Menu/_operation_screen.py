# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""The screen that follows an operation while it runs behind the menu: the layout and keys shared by the test
screen (_test_run.py) and, next, the run screen. What it shows comes from a model:

    process.events ─▶ model.feed() ─▶ list (model.items(), row()) + Details (focused item: details(), log())
    process.output ────────────────▶ Output view (L)
    model.log(item) ───────────────▶ Details / item log view (Enter), read only while the item is on screen
    process.state() ───────────────▶ the state line (model.states, + "on <host>"), then model.summary()

The process is a TauFW.Utilities.Process.Operation (or a stand-in with
state(), events, output, returncode, elapsed(), cancel(), kill(), remote and
host). The screen draws every FRAME seconds and never waits for the operation.
Leaving it (Esc) never stops the operation; S or Ctrl-C asks (model.stop_question,
in a panel over the screen), then stops it; while it stops, K kills it at once
after a question (model.kill_warning). A model with leave_stops (a read-only
command, _command_screen.py) is stopped without a question by Esc, S or Ctrl-C:
nothing of it stays behind the menu. No Framework imports belong here (see _test_run.py).

A model (see ScreenModel) holds the words of its screen and turns events into
items; the screen keeps only where the user is (_View). Three hooks a model
may use: current() is the item the focus follows until the user moves it (the
one at work), card() a result card drawn above the list (once it ended), and
info() a box of the focused item's facts to the right of the list (on a
terminal narrower than INFO_MIN_WIDTH, at the top of its Details instead).
A model without items shows only the Output view. Its actions are keys that
leave the screen once the operation ended, with an answer (model.answer).
"""
import re
import textwrap

from ._menu import _clock
from ..Process import EventReader, LogTail
from ..Process._operations import ACTIVE, DONE, FAILED, LOST, RUNNING, STOPPED, STOPPING

__all__ = ["ScreenModel", "follow", "printable", "summary_model"]


# =============================================================================
# ================================= CONSTANTS =================================


FRAME = 0.1           # seconds between frames
LOG_LINES = 400       # lines of an item log kept on screen
LIST_SHARE = 0.4      # of the width for the list when the info box (model.info) is next to it, the rest for the box
LIST_MIN_WIDTH = 52   # columns of the list at least
INFO_MIN_WIDTH = 100  # narrower terminals show the info at the top of the Details
CONTROL = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|[\x00-\x08\x0b-\x1f\x7f]")


# =============================================================================
# ================================== MODEL ====================================


class ScreenModel:
    """What an operation screen shows. A model turns the operation's events into items (feed) and says how each
    is drawn; the class attributes are the words of its screen. messages: (role, text), the last two shown above
    the list."""

    list_title = "Items"                 # the list panel
    item = "Item"                        # footer: "Up/Down Item | Enter Item log"
    output_title = "Output"              # the L view
    stop_question = "Stop it?"           # asked before a stop
    stopping = "Stopping..."             # footer while it stops
    kill_warning = "It ends at once, without finishing what it does."  # asked before K Kill now (while it stops)
    states = {RUNNING: ("RUNNING", "accent"), STOPPING: ("STOPPING", "warning"), DONE: ("DONE", "good"),
              FAILED: ("FAILED", "error"), STOPPED: ("STOPPED", "warning"), LOST: ("LOST", "warning")}
    leave_stops = False                  # Esc, S and Ctrl-C stop it without a question (Esc also leaves)
    actions = ()                         # (letter, footer label, answer): the key leaves once it ended

    def feed(self, events):
        """Take the events read since the last call."""

    def finish(self, returncode, lost=False, state=None):
        """The operation ended (lost: it was lost; state: DONE, FAILED, STOPPED or LOST); called once."""

    def items(self):
        """The list, in order."""
        return []

    def label(self, item):
        """The name of an item (titles of its Details and log)."""
        return str(item)

    def row(self, item):
        """(text, time text, role) of an item's line in the list; role: a style name of ConsoleUI or None."""
        return self.label(item), "", None

    def details(self, item):
        """The lines of an item's Details (the end of its log is added below them)."""
        return []

    def log(self, item):
        """The path of an item's log, or None."""
        return None

    def summary(self):
        """The text after the state and the time on the state line."""
        return ""

    def current(self):
        """The index of the item the focus follows until the user moves it, or None."""
        return None

    def card(self):
        """(title, [(text, role)]) of a card drawn above the list, or None."""
        return None

    def info(self, item):
        """(title, [(label, value)]) of the box of an item's facts next to the list, or None."""
        return None

    def __init__(self):
        self.messages = []
        self.answer = None               # of the action that left the screen


def summary_model(operation, state, make, kept=None):
    """The model of an operation's events for its line in a menu (test_summary, run_summary), fed after
    operation.state() gave `state`: then an ended operation's events are all there. make() builds the model.
    kept: a dict per operation that the caller keeps between draws (the menus: one per directory); it holds the
    model and its own reader (the screen's stays at the top), so the next call reads only the new events, and
    none once the operation ended."""
    kept = {} if kept is None else kept
    if "model" not in kept:
        kept.update(model=make(), events=EventReader(operation.events_path), ended=False)
    if not kept["ended"]:
        while True:
            events = kept["events"].read()
            kept["model"].feed(events)
            if not events or state in ACTIVE:
                break  # an ended operation: read on past READ_LIMIT, it is the last time
        kept["ended"] = state not in ACTIVE
    return kept["model"]


# =============================================================================
# ================================== SCREEN ===================================


def follow(ui, screen, title, process, model):
    """Draw the operation until the user leaves; it goes on behind the menu.
    Return its exit code, None while it runs (or once it was lost)."""
    ui._setup(screen)
    screen.timeout(int(FRAME * 1000))
    view = _View()
    while True:
        try:
            state = process.state()  # before reading: then every event of an ended operation is read
            if process.events is not None:
                model.feed(process.events.read())
            process.output.read()
            if state not in ACTIVE and not view.finished:
                model.finish(process.returncode, lost=state == LOST, state=state)
                view.finished = True
            current = model.current() if view.follow else None
            if current is not None:
                view.focus = current
            _draw(ui, screen, title, process, model, view, state)
            key = screen.getch()
        except KeyboardInterrupt:
            key = 3
        if _key(ui, key, process, model, view, state):
            return process.returncode


def printable(text):
    """A line curses can draw: no color codes or control characters, tabs as spaces."""
    return CONTROL.sub("", str(text)).expandtabs(4)


class _View:
    """Where the user is on the screen."""

    def __init__(self):
        self.mode = "items"     # items | item | output
        self.focus = 0
        self.follow = True      # the focus follows model.current() until the user moves it
        self.offset = None      # first line of a log view; None: follow the end
        self.end = 0            # the first line of the last page of the log view
        self.page = 1           # lines of the log view
        self.confirm = None     # the question asked in a panel over the screen: "stop" or "kill"
        self.finished = False
        self.tails = {}         # item log path -> LogTail


# =============================================================================
# ================================== DRAWING ==================================


def _draw(ui, screen, title, process, model, view, state):
    screen.erase()
    height, width = screen.getmaxyx()
    start = ui._header(screen, title, badge=True)
    text, role = _state(model, process, state)
    summary = "%s | %s | %s" % (text, _clock(process.elapsed()), model.summary())
    column = width - len(summary) - 2
    row = 1 if column > start + len(title) + 2 else 2  # no room next to the title: on the free line below it
    ui._line(screen, row, column if row == 1 else start, summary, color=ui.styles.get(role, 0))
    items = model.items()
    if height < 12 or width < 40:
        ui._line(screen, 3, 1, "Enlarge terminal (at least 40 x 12).")
    elif view.mode == "output" or not items:
        lines = list(process.output.lines) + ([process.output.partial] if process.output.partial else [])
        _log(ui, screen, view, model.output_title, lines, height, width)
    elif view.mode == "item":
        item = _focused(items, view)
        _log(ui, screen, view, "Log: %s" % model.label(item), _item_lines(model, view, item), height, width)
    else:
        _items(ui, screen, model, items, view, height, width)
    ui._footer(screen, _footer(model, items, view, state))
    if view.confirm == "stop":
        ui._overlay(screen, "Stop", [(model.stop_question, "warning")], "Y Yes | N No")
    elif view.confirm == "kill":
        ui._overlay(screen, "Kill now?", [(model.kill_warning, "error")], "Y Kill now | N No")
    screen.refresh()


def _items(ui, screen, model, items, view, height, width):
    top = 3
    for role, text in model.messages[-2:]:
        ui._line(screen, top, 1, ("! " + printable(text))[:width - 2], color=ui.styles.get(role, 0))
        top += 1
    card = model.card()
    if card is not None:
        lines = [(part, role) for text, role in card[1] for part in ui._wrap(text, width - 6)][:max(1, height // 3)]
        inner = ui._panel(screen, top, 1, len(lines) + 2, width - 2, card[0])
        for index, (text, role) in enumerate(lines):
            ui._line(screen, inner[0] + index, inner[1], text, color=ui.styles.get(role, 0))
        top += len(lines) + 2
    list_height = max(4, (height - top - 3) // 2)
    view.focus = min(view.focus, len(items) - 1)
    item = items[view.focus]
    info = model.info(item)
    beside = info is not None and width >= INFO_MIN_WIDTH
    list_width = max(LIST_MIN_WIDTH, int(width * LIST_SHARE)) if beside else width - 2
    rect = ui._panel(screen, top, 1, list_height, list_width, model.list_title)
    row, left, rows, columns = rect
    first = max(0, view.focus - rows + 1)
    for index, entry in enumerate(items[first:first + rows], first):
        label, time_text, role = model.row(entry)
        line = label[:max(1, columns - len(time_text) - 1)].ljust(max(1, columns - len(time_text))) + time_text
        ui._line(screen, row + index - first, left, line[:columns], index == view.focus, ui.styles.get(role, 0))
    if beside:  # the boxes share their edge
        box = ui._panel(screen, top, list_width, list_height, width - 1 - list_width, info[0])
        ui._viewport(screen, box, _info_lines(info[1], box[3]), 0)
    details = ui._panel(screen, top + list_height, 1, height - top - list_height - 3, width - 2,
                        "Details: %s" % model.label(item))
    lines = [printable(line) for line in model.details(item)]
    log = _item_lines(model, view, item)
    if log:
        lines += ["--- last lines of the log ---"] + log[-max(1, details[2]):]
    pinned = _info_lines(info[1], details[3]) + [""] if info is not None and not beside else []
    pinned = pinned[:max(0, details[2] // 2)]  # the facts at the top, the end of the rest below them
    rest = [part for line in lines for part in ui._wrap(line, details[3])][-max(1, details[2] - len(pinned)):]
    ui._viewport(screen, details, pinned + rest, 0)


def _log(ui, screen, view, title, lines, height, width):
    """A scrollable log that follows its end until the user scrolls up."""
    rect = ui._panel(screen, 3, 1, height - 6, width - 2, title)
    lines = [part for line in lines for part in ui._wrap(printable(line), rect[3])] or ["(no output yet)"]
    view.page = max(1, rect[2] - (1 if len(lines) > rect[2] else 0))
    view.end = max(0, len(lines) - view.page)
    if view.offset is not None and view.offset >= view.end:
        view.offset = None  # scrolled back to the end: follow it again
    ui._viewport(screen, rect, lines, view.end if view.offset is None else view.offset)


def _footer(model, items, view, state):
    stop = " | S Stop" if state == RUNNING else ""
    if state in ACTIVE and not model.leave_stops:
        back = " | Esc Back (keeps running)"
    else:
        back = " | Esc Stop and back" if state == RUNNING else " | Esc Back"
    if state == STOPPING:
        return model.stopping + ("" if model.leave_stops else " | K Kill now") + back
    actions = "" if state in ACTIVE else "".join(" | %s %s" % (letter, label) for letter, label, _ in model.actions)
    if view.mode != "items" or not items:
        return "Up/Down/PgUp/PgDn Scroll | End Follow" + stop + actions + back
    return "Up/Down %s | Enter %s log | L Output" % (model.item, model.item) + stop + actions + back


def _state(model, process, state):
    """(text, role) of the state line; an operation started on another machine says where it runs."""
    text, role = model.states[state]
    if state in ACTIVE and getattr(process, "remote", False):
        text = "%s on %s" % (text, process.host)
    return text, role


# =============================================================================
# ==================================== KEYS ===================================


def _key(ui, key, process, model, view, state):
    """Handle one key; True: leave the screen (the operation goes on)."""
    curses = ui.curses
    items = model.items()
    if view.confirm:
        if view.confirm == "kill" and state not in ACTIVE:
            view.confirm = None  # it ended meanwhile: nothing to kill
        elif key in (ord("y"), ord("Y")):
            if view.confirm == "kill":
                process.kill()
            else:
                process.cancel()
            view.confirm = None
        elif key in (ord("n"), ord("N"), 27, 3):
            view.confirm = None
        return False
    if key in (3, ord("s"), ord("S")):
        if model.leave_stops and state == RUNNING:
            process.cancel()
        else:
            view.confirm = "stop" if state == RUNNING else None
    elif key in (ord("k"), ord("K")) and state == STOPPING and not model.leave_stops:
        view.confirm = "kill"
    elif key == 27:
        if view.mode != "items" and items:
            view.mode, view.offset = "items", None
        else:
            if model.leave_stops and state == RUNNING:
                process.cancel()
            return True
    elif state not in ACTIVE and any(key in (ord(letter.lower()), ord(letter.upper()))
                                     for letter, _, _ in model.actions):
        model.answer = next(answer for letter, _, answer in model.actions
                            if key in (ord(letter.lower()), ord(letter.upper())))
        return True
    elif key in (ord("l"), ord("L")):
        view.mode, view.offset = ("items" if view.mode == "output" else "output"), None
    elif view.mode == "items" and items:
        if key in (curses.KEY_UP, curses.KEY_DOWN):
            view.focus = (view.focus + (1 if key == curses.KEY_DOWN else -1)) % len(items)
            view.follow = False
        elif key in (10, 13, curses.KEY_ENTER):
            view.mode, view.offset = "item", None
    else:
        step = {curses.KEY_UP: -1, curses.KEY_DOWN: 1, curses.KEY_PPAGE: -view.page, curses.KEY_NPAGE: view.page}
        if key in step:
            view.offset = max(0, (view.end if view.offset is None else view.offset) + step[key])
        elif key == getattr(curses, "KEY_END", None):
            view.offset = None
    return False


# =============================================================================
# ================================ HELPERS ====================================


def _info_lines(facts, width):
    """`label  value` lines, the values aligned and wrapped under themselves."""
    pad = min(max([len(str(label)) for label, _ in facts] or [0]), max(1, width // 2))
    lines = []
    for label, value in facts:
        parts = textwrap.wrap(printable(value), max(1, width - pad - 2)) or [""]
        lines += [(str(label) if index == 0 else "").ljust(pad) + "  " + part for index, part in enumerate(parts)]
    return lines


def _focused(items, view):
    return items[min(view.focus, len(items) - 1)]


def _item_lines(model, view, item):
    """An item's log as far as it was written (read only while the item is on screen)."""
    path = model.log(item)
    if not path:
        return []
    tail = view.tails.get(path)
    if tail is None:
        tail = view.tails[path] = LogTail(path, LOG_LINES)
    tail.read()
    return [printable(line) for line in tail.lines] + ([printable(tail.partial)] if tail.partial else [])
