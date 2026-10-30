# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Terminal presentation, screen actions, and menu wording.

No Framework imports or workflow decisions belong here. Curses is loaded only
when open() is called. The menu draws every screen in one curses session
(session()): nothing is printed between two screens, and a message, an error
or a question is a small panel over the current screen (_modal). Without a
session (FastSetup's checklist, the unit tests) each screen opens the terminal
and restores it before returning.
"""
import os
import signal
import sys
import textwrap
import time

from .faq import FAQ
from ._plan_screen import show_plan, stage_table, there_are
from .banner import DECAY_SECONDS, INTERACTIONS, VERSION, WIDTH, branding, decay_frame

if "." in __package__:
    from ..notifications import bell
else:  # standalone installer
    from notifications import bell


QUIT_WARNING = ("If you quit, they keep running, but only while this login session lasts. Logging out (closing "
                "the SSH session) ends them, and the menu then shows them as Lost. A lost run keeps everything "
                "that was finished and every submitted job: Continue resumes it, at once from this machine, from "
                "another lxplus machine after 2 minutes with Take over. A run that ends while it submits jobs may "
                "need a manual check (condor_q). Open the menu again to follow them. Stop all asks each of them "
                "to stop: a run finishes a job submission in progress first.")


LIVE_EVERY = 2.0      # seconds between two draws of a live main menu (something runs behind it)
BANNER_FRAME = 0.05   # seconds between frames of the one-shot main-menu decay
LIST_EVERY = 0.5      # seconds between two draws of a list whose rows are still read (Start, Continue)
ESC_DELAY = 25        # ms curses waits after Esc for the rest of a key sequence (its default: 1000, a slow Esc)
MODAL_WIDTH = 76      # columns of a panel over the screen at most
REFRESH = "refresh"   # the answer of a live screen that was not answered in time: draw it again
MIN_COLUMNS, MIN_ROWS = 80, 24  # every screen of the menu (and the editor) needs this much, else TOO_SMALL
TOO_SMALL = ("Terminal too small: at least %d x %d." % (MIN_COLUMNS, MIN_ROWS),
             "Enlarge it, or use the taufw commands (taufw --help).")
TOO_SMALL_FOOTER = "Esc or Ctrl+C to close"
REDRAW = 12  # Ctrl+L: draw the whole screen again, as after a resize


_signalled = []  # SIGWINCH came since the last _follow_size (the size may be the same again)


def _wake(signum, frame):
    """Note the resize signal; it also ends a key read that waits in curses (_follow_size)."""
    _signalled.append(signum)


def _follow_size(curses, screen):
    """Give curses the terminal's size; True if it changed or a resize signal came (the screen is then drawn
    again, whole).
    Curses learns a resize from SIGWINCH, but a library loaded later can take the signal for itself (ROOT does,
    and a plan imports it): curses then keeps the old size for good. So the size is asked from the terminal here,
    and SIGWINCH is set again each time to wake a waiting key read: a handler set in C replaces it unseen
    (signal.getsignal only knows what Python set). The editor has a copy (editor/_screen.py)."""
    try:
        signal.signal(signal.SIGWINCH, _wake)
    except (AttributeError, ValueError):
        pass  # no SIGWINCH (Windows), or not the main thread
    signalled = bool(_signalled)
    del _signalled[:]
    try:
        columns, lines = os.get_terminal_size(sys.__stdout__.fileno())
    except (AttributeError, OSError, ValueError):
        return signalled  # not a terminal
    if screen.getmaxyx() == (lines, columns):
        return signalled
    curses.resizeterm(lines, columns)
    return True


class _Guarded:
    """The screen a menu screen draws on, when the terminal may be smaller than MIN_COLUMNS x MIN_ROWS. Below
    that, what the screen draws is never shown: reading a key shows TOO_SMALL instead and waits there. Esc answers
    Esc (every screen closes on it), Ctrl+C raises as usual, a live screen's timeout (-1) lets it draw again;
    once the terminal is large enough, a resize key, and the screen draws itself again. Everything else is the
    screen's own. follow: the size is followed (_follow_size); False for the unit tests' screens."""

    def __init__(self, screen, curses, follow=False):
        self._screen, self._curses, self._follow = screen, curses, follow

    def __getattr__(self, name):
        return getattr(self._screen, name)

    def _small(self):
        height, width = self._screen.getmaxyx()
        return width < MIN_COLUMNS or height < MIN_ROWS

    def refresh(self):
        if not self._small():
            self._screen.refresh()

    def getch(self):
        return self._read(self._screen.getch, 27)

    def get_wch(self):
        return self._read(self._screen.get_wch, "\x1b")

    def _read(self, read, escape):
        if not self._small():
            return self._key(read)
        while self._small():
            self._notice()
            key = self._key(read)
            if key in (27, "\x1b"):
                return escape
            if key == -1:
                return -1
        return self._curses.KEY_RESIZE

    def _resized(self):
        return self._follow and _follow_size(self._curses, self._screen)

    def _key(self, read):
        """read(), with every resize and Ctrl+L as KEY_RESIZE: the next refresh sends the whole screen again (the
        screen draws itself again). Curses otherwise sends only what changed since its last draw, and leaves what
        the terminal itself moved on a resize (lines it rewrapped) on the screen. A resize while the screen drew
        answers at once; one during the read ends it (-1, or the curses.error of get_wch); one that came with a
        key keeps the key."""
        curses = self._curses
        resized = self._resized()
        if resized:
            key = curses.KEY_RESIZE
        else:
            try:
                key = read()
            except curses.error:  # get_wch: no key (a resize signal ended the read)
                if not self._resized():
                    raise
                key = curses.KEY_RESIZE
            resized = self._resized()
        if resized or key in (curses.KEY_RESIZE, REDRAW, chr(REDRAW)):
            self._screen.clearok(True)
            if key in (-1, REDRAW, chr(REDRAW)):
                key = curses.KEY_RESIZE
        return key

    def _notice(self):
        screen = self._screen
        height, width = screen.getmaxyx()
        screen.erase()
        for row, text in enumerate(TOO_SMALL + ("", TOO_SMALL_FOOTER)):
            if row < height - 1:
                try:
                    screen.addnstr(row + 1, 1, text, max(0, width - 2), 0)
                except self._curses.error:
                    pass  # a resize between the size and the draw
        screen.refresh()


def _clock(seconds):
    minutes, seconds = divmod(int(max(0, seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    return "%d:%02d:%02d" % (hours, minutes, seconds) if hours else "%02d:%02d" % (minutes, seconds)


class ConsoleUI:
    """Small curses screens; no Framework or batch logic."""

    # =========================================================================
    # =========================== TERMINAL LIFECYCLE ==========================

    def __init__(self, curses, follow_size=False):
        self.curses = curses
        self.follow_size = follow_size  # the size is asked from the terminal (_follow_size): open(), not the tests
        self.screen = None    # the screen of the session (session()), None outside it
        self._summaries = {}  # operation directory -> what its menu line keeps between draws (summary_model)
        self._main_action = None  # the main menu's line last selected: a live redraw keeps it
        self._main_banner_started = None  # a live redraw keeps the same one-shot animation
        self.set_version(VERSION)

    def set_version(self, version):
        """Use caller-supplied display metadata without importing its package or reading its files."""
        self.version = version
        self._full_banner, self._boxed_banner, self._compact_banner, self._badge = branding(version)

    def session(self, function):
        """Run function() with every screen drawn in one curses session; return its result."""
        def run(screen):
            self.screen = screen
            try:
                return function()
            finally:
                self.screen = None
        return self.curses.wrapper(run)

    def _run(self, draw, guard=True):
        """draw(screen) on the session's screen, or in a curses session of its own outside one. guard: below
        MIN_COLUMNS x MIN_ROWS the screen only says so (_Guarded); False for the installer's own screens."""
        if not guard:
            return draw(self.screen) if self.screen is not None else self.curses.wrapper(draw)
        if self.screen is not None:
            return draw(_Guarded(self.screen, self.curses, self.follow_size))
        return self.curses.wrapper(lambda screen: draw(_Guarded(screen, self.curses, self.follow_size)))

    def resized(self, screen):
        """For a screen that is not guarded (the installer's): True if the terminal's size changed (_follow_size);
        the screen then draws itself again, whole."""
        return self.follow_size and _follow_size(self.curses, screen)

    def in_terminal(self, function, pause=True):
        """Run function() on the plain terminal (a program that asks there), then "Press Enter" and back to the
        screen; pause=False returns immediately (a program with its own result screen). Outside a session it
        just runs."""
        if self.screen is None:
            return function()
        self.curses.def_prog_mode()
        self.curses.endwin()
        try:
            result = function()
            if pause:
                try:
                    input("\nPress Enter to return to the menu...")
                except (KeyboardInterrupt, EOFError):
                    pass
            return result
        finally:
            self.curses.reset_prog_mode()
            self.screen.clearok(True)  # the terminal may have been resized or scrolled meanwhile
            self.screen.refresh()

    @classmethod
    def open(cls, parser):
        """Return a UI on supported terminals, otherwise explain and show CLI help."""
        if not sys.platform.startswith("linux") or not sys.stdin.isatty() or not sys.stdout.isatty():
            print("The TauFW menu requires an interactive Linux terminal. Use a CLI subcommand instead.",
                  file=sys.stderr)
            parser.print_help()
            return None
        try:
            import curses
            # The size from the terminal, not from LINES/COLUMNS: a shell that exports them gives the size at the
            # start, and curses would keep it through every resize (KEY_RESIZE comes, the size never changes).
            # Not use_env(False): it also stops curses asking the terminal (only terminfo's fixed size is left).
            for name in ("LINES", "COLUMNS"):
                os.environ.pop(name, None)
            curses.setupterm()
        except (ImportError, OSError) as error:
            print("The TauFW menu requires curses and a supported terminal: %s" % error, file=sys.stderr)
            parser.print_help()
            return None
        except Exception as error:
            print("Cannot initialize the TauFW terminal menu: %s" % error, file=sys.stderr)
            parser.print_help()
            return None
        os.environ.setdefault("ESCDELAY", str(ESC_DELAY))  # read when curses starts; one set by the user is kept
        return cls(curses, follow_size=True)

    def is_terminal_error(self, error):
        return isinstance(error, self.curses.error)

    def terminal_failure(self, error, parser):
        print("Cannot open the TauFW terminal menu: %s" % error, file=sys.stderr)
        parser.print_help()

    # =========================================================================
    # ================================ DRAWING ================================

    def colors_enabled(self):
        return (sys.stdout.isatty() and os.environ.get("TERM", "dumb") != "dumb"
                and not os.environ.get("NO_COLOR"))

    def _setup(self, screen):
        screen.keypad(True)
        screen.timeout(-1)  # wait for a key: the screen before may have drawn live
        if hasattr(self.curses, "set_escdelay"):  # Python 3.9+: also when curses read no ESCDELAY
            try:
                self.curses.set_escdelay(int(os.environ.get("ESCDELAY", ESC_DELAY)))
            except (self.curses.error, ValueError):
                pass
        self.styles = dict(accent=0, good=0, waiting=0, warning=0, error=0, brand=0, version=0)
        try:
            if self.colors_enabled() and self.curses.has_colors():
                self.curses.start_color()
                background = self.curses.COLOR_BLACK
                try:
                    self.curses.use_default_colors()
                    background = -1
                except self.curses.error:
                    pass
                rich = self.curses.COLORS >= 256  # the badge: purple and gold, else magenta and yellow
                for role, pair, foreground in (
                    ("accent", 3, self.curses.COLOR_CYAN),
                    ("good", 1, self.curses.COLOR_GREEN),
                    ("waiting", 8, self.curses.COLOR_YELLOW),
                    ("error", 2, self.curses.COLOR_RED),
                    ("brand", 9, 135 if rich else self.curses.COLOR_MAGENTA),
                    ("version", 10, 178 if rich else self.curses.COLOR_YELLOW),
                ):
                    self.curses.init_pair(pair, foreground, background)
                    self.styles[role] = self.curses.color_pair(pair)
                self.styles["warning"] = self.styles["waiting"]
                self.styles["brand"] |= self.curses.A_BOLD
        except self.curses.error:
            self.styles = dict(accent=0, good=0, waiting=0, warning=0, error=0, brand=0, version=0)
        try:
            self.curses.curs_set(0)
        except self.curses.error:
            pass

    def _line(self, screen, y, x, value, selected=False, color=0):
        height, width = screen.getmaxyx()
        if 0 <= y < height - 1 and 0 <= x < width - 1:
            try:
                screen.addnstr(y, x, str(value), width - x - 1,
                               color | (self.curses.A_REVERSE if selected else 0))
            except self.curses.error:
                pass  # A resize may have happened between size and draw.

    def _panel(self, screen, top, left, height, width, title=""):
        """Draw an ASCII frame and return its padded content rectangle."""
        if height >= 3 and width >= 6:
            edge = "+" + "-" * (width - 2) + "+"
            self._line(screen, top, left, edge, color=self.styles["accent"])
            self._line(screen, top + height - 1, left, edge, color=self.styles["accent"])
            for row in range(top + 1, top + height - 1):
                self._line(screen, row, left, "|", color=self.styles["accent"])
                self._line(screen, row, left + width - 1, "|", color=self.styles["accent"])
            if title:
                self._line(screen, top, left + 2, (" " + title + " ")[:width - 4],
                           color=self.styles["accent"])
            return top + 1, left + 2, height - 2, width - 4
        return top, left, max(1, height), max(1, width)

    def _header(self, screen, title, badge=False):
        """badge: the framed TauFW wordmark on rows 0-2, the title beside it. Return the column of the title."""
        if not badge:
            self._line(screen, 0, 1, "TauFW " + self.version, color=self.styles["accent"])
            self._line(screen, 1, 1, title)
            return 1
        for row, line in enumerate(self._badge):
            self._line(screen, row, 1, line, color=self.styles["accent"])
        self._line(screen, 1, 3, "TauFW", color=self.styles["brand"])
        self._line(screen, 2, 3, self.version, color=self.styles["version"])
        column = len(self._badge[0]) + 3
        self._line(screen, 1, column, title)
        return column

    def _footer(self, screen, text):
        height, _ = screen.getmaxyx()
        self._line(screen, height - 2, 1, text, color=self.styles["accent"])

    @staticmethod
    def _wrap(value, width):
        return [line for paragraph in str(value).splitlines()
                for line in (textwrap.wrap(paragraph, max(1, width)) or [""])] or [""]

    def _pipeline_lines(self, view, width, colors=None):
        """A recipe's stages as a table (# / Stage ID / Input / Description), with only the counts of its problems
        and warnings above it (the plan screen lists them); colors, if given, is filled with each line's role."""
        lines, roles = [], []

        def add(texts, role=None):
            lines.extend(texts)
            roles.extend([role] * len(texts))

        if view.get("hint"):
            add(self._wrap(view["hint"], width))
        else:
            add(self._wrap("Recipe: " + view.get("name", ""), width))
            if view.get("shown"):
                add(self._wrap("Path:   " + view["shown"], width))
            if view.get("error"):
                add([""] + self._wrap("Cannot preview: " + view["error"], width), "error")
            elif view.get("draft"):
                add([""] + self._wrap("Draft - no stages configured.", width) + [""])
                add(self._wrap("Press E to edit its recipe.yml before starting a run.", width))
            else:
                problems, warnings = len(view.get("problems", ())), len(view.get("warnings", ()))
                if problems:
                    add(self._wrap(there_are(problems, "error"), width), "error")
                if warnings:
                    add(self._wrap(there_are(warnings, "warning"), width), "warning")
                add([""])
                rows = stage_table(view.get("stages", ()), width)
                add(rows[:1], "accent")
                add(rows[1:])
        if colors is not None:
            colors.extend(roles)
        return lines

    def _viewport(self, screen, rect, lines, offset, color=0, line_colors=None):
        top, left, rows, width = rect
        visible = max(1, rows - (1 if len(lines) > rows else 0))
        offset = min(max(0, offset), max(0, len(lines) - visible))
        for index, line in enumerate(lines[offset:offset + visible]):
            role = line_colors[offset + index] if line_colors is not None else None
            self._line(screen, top + index, left, line[:width],
                       color=self.styles.get(role, 0) if line_colors is not None else color)
        if len(lines) > rows:
            self._line(screen, top + rows - 1, left,
                       ("Lines %d-%d/%d" % (offset + 1, min(len(lines), offset + visible),
                                            len(lines)))[:width], color=self.styles["accent"])
        return offset, visible

    def _pipeline_choice(self, title, choices, preview, position=None, row_colors=None, live=None,
                         edit_indices=(), separators=()):
        """Two columns, the recipes 30% and the pipeline 70%, with independent recipe and pipeline scrolling.
        row_colors: a style name per choice (e.g. "error"), or None. live: seconds; without a key by then, REFRESH
        (the caller draws it again with what came meanwhile; the position is kept). separators: an empty line
        before each of these choices (as in choose)."""
        position = position if position is not None else {}
        offsets = [index + sum(gap <= index for gap in separators) for index in range(len(choices))]

        def draw(screen):
            self._setup(screen)
            if live:
                screen.timeout(int(live * 1000))
            selected, offset = min(position.get("selected", 0), len(choices) - 1), position.get("offset", 0)
            while True:
                screen.erase()
                height, width = screen.getmaxyx()
                self._header(screen, title, badge=True)
                page = 1
                span = 2 * ((width - 1) // 2)  # both panels, counting their shared border twice
                left = (width - (span - 1)) // 2
                # recipes 30%, pipeline 70%; the recipes keep room for their rows, up to half
                list_width = min(max(span * 3 // 10, 34), span // 2)
                left_rect = self._panel(screen, 3, left, height - 6, list_width, "Recipes")
                right_rect = self._panel(screen, 3, left + list_width - 1,
                                         height - 6, span - list_width, "Pipeline")
                top, column, rows, columns = left_rect
                self._line(screen, top, column, "Recipe / bundle", color=self.styles["accent"])
                top, rows = top + 2, max(1, rows - 2)
                first = 0
                while offsets[selected] - offsets[first] >= rows:
                    first += 1
                for index in range(first, len(choices)):
                    row = offsets[index] - offsets[first]
                    if row >= rows:
                        break
                    label = ("> " if index == selected else "  ") + choices[index]
                    role = row_colors[index] if row_colors and index < len(row_colors) else None
                    self._line(screen, top + row, column, label[:columns],
                               index == selected, self.styles.get(role, 0) if role else 0)
                view = preview(selected)
                line_colors = []
                lines = self._pipeline_lines(view, right_rect[3], colors=line_colors)
                offset, page = self._viewport(screen, right_rect, lines, offset,
                                              line_colors=line_colors)
                self._footer(screen, "Up/Down Move | Enter Select | " +
                             ("E Edit | " if selected in edit_indices else "") + "PgUp/Dn Pipeline | Esc Back")
                screen.refresh()
                key = screen.getch()
                if key == -1 and live:
                    position.update(selected=selected, offset=offset)
                    return REFRESH
                if key == 27:
                    position.update(selected=selected, offset=offset)
                    return None
                if key in (ord("e"), ord("E")) and selected in edit_indices:
                    position.update(selected=selected, offset=offset)
                    return "edit", selected
                if key in (self.curses.KEY_UP, self.curses.KEY_DOWN):
                    selected = (selected + (1 if key == self.curses.KEY_DOWN else -1)) % len(choices)
                    offset = 0
                elif key == self.curses.KEY_NPAGE:
                    offset += page
                elif key == self.curses.KEY_PPAGE:
                    offset = max(0, offset - page)
                elif key in (10, 13, self.curses.KEY_ENTER):
                    position.update(selected=selected, offset=offset)
                    return selected
        return self._run(draw)

    def _entry_banner(self, screen, minimum_rows):
        """Choose branding that leaves room for the screen's controls."""
        height, width = screen.getmaxyx()
        if width > WIDTH and height >= len(self._full_banner) + minimum_rows + 5:
            lines = self._full_banner
        elif width > len(self._boxed_banner[0]) and height >= len(self._boxed_banner) + minimum_rows + 5:
            lines = self._boxed_banner
        else:
            lines = self._compact_banner
        if height < len(lines) + minimum_rows + 5:
            lines = ("TauFW " + self.version,)
        return lines

    def _entry_header(self, screen, welcome, minimum_rows, elapsed=None):
        """Reserve room for controls; elapsed animates only the full decay scene."""
        lines = self._entry_banner(screen, minimum_rows)
        full = lines is self._full_banner
        if full and elapsed is not None:
            lines = decay_frame(lines, elapsed)
        color = 0
        interaction_colors = {}
        try:
            if self.colors_enabled() and self.curses.has_colors():
                self.curses.start_color()
                background = self.curses.COLOR_BLACK
                try:
                    self.curses.use_default_colors()
                    background = -1
                except self.curses.error:
                    pass
                self.curses.init_pair(3, self.curses.COLOR_CYAN, background)
                color = self.curses.color_pair(3)
                if full:
                    for role, pair, foreground, bold in (
                        ("higgs", 4, self.curses.COLOR_RED, True),
                        ("tau", 5, self.curses.COLOR_MAGENTA, True),
                        ("products", 6, self.curses.COLOR_GREEN, False),
                        ("vertex", 7, self.curses.COLOR_YELLOW, True),
                    ):
                        self.curses.init_pair(pair, foreground, background)
                        interaction_colors[role] = (self.curses.color_pair(pair)
                                                   | (self.curses.A_BOLD if bold else 0))
        except self.curses.error:
            interaction_colors = {}
        for row, line in enumerate(lines):
            self._line(screen, row, 0, line, color=color)
        if full and interaction_colors:
            for row, column, text, role in INTERACTIONS:
                self._line(screen, row, column, lines[row][column:column + len(text)],
                           color=interaction_colors[role])
        self._line(screen, len(lines) + 1, 0, welcome)
        return len(lines) + 3

    def choose(self, title, choices, welcome=None, descriptions=None, row_colors=None, position=None, live=None,
               separators=(), badge=False, notice=None, banner_started=None):
        """The index of the choice, or None (Esc). position: {"selected": index}, where the focus starts and was
        left. live: seconds; without a key by then, REFRESH (the caller draws it again with new labels).
        banner_started: monotonic start of the main-menu visit, kept through live refreshes."""
        position = position if position is not None else {}

        def draw(screen):
            self._setup(screen)
            refresh_at = None  # Animation ticks share the normal live-refresh deadline.
            selected = min(position.get("selected", 0), len(choices) - 1)
            while True:
                now = time.monotonic() if banner_started is not None else None
                elapsed = now - banner_started if banner_started is not None else None
                animating = False
                screen.erase()
                height, width = screen.getmaxyx()
                if welcome is None:
                    self._header(screen, title, badge=badge)
                    start = 3
                else:
                    minimum_rows = len(choices) + len(separators) + 3
                    animating = (elapsed is not None and elapsed < DECAY_SECONDS
                                 and self._entry_banner(screen, minimum_rows) is self._full_banner)
                    start = self._entry_header(screen, welcome, minimum_rows, elapsed=elapsed)
                if notice:
                    text, role = notice
                    if welcome is not None:
                        self._line(screen, start - 2, len(welcome) + 2, text, color=self.styles.get(role, 0))
                    else:
                        self._line(screen, start - 1, 1, text, color=self.styles.get(role, 0))
                        start += 1
                top, left, rows, columns = self._panel(screen, start, 1,
                                                      height - start - 3, width - 2, "Menu")
                show_description = descriptions and rows >= len(choices) + len(separators) + 3
                if show_description:
                    rows -= 3
                stride = 2 if not separators and rows >= 2 * len(choices) - 1 else 1
                rows = max(1, rows)
                offsets = [index * stride + sum(gap <= index for gap in separators) for index in range(len(choices))]
                first = 0
                while offsets[selected] - offsets[first] >= rows:
                    first += 1
                for index in range(first, len(choices)):
                    row = offsets[index] - offsets[first]
                    if row >= rows:
                        break
                    label = ("> " if index == selected else "  ") + choices[index]
                    role = row_colors[index] if row_colors and index < len(row_colors) else "accent"
                    self._line(screen, row + top, left, label[:columns],
                               index == selected, self.styles.get(role, 0) if row_colors else 0)
                if show_description:
                    for index, line in enumerate(self._wrap(descriptions[selected], columns)[:2]):
                        self._line(screen, height - 6 + index, left, line,
                                   color=self.styles["accent"])
                self._footer(screen, "Up/Down Move | Enter Select | Esc Back")
                wait = int(live * 1000) if live else -1
                if animating:
                    wait = int(BANNER_FRAME * 1000)
                    if live and refresh_at is None:
                        refresh_at = now + live
                if refresh_at is not None:
                    wait = min(wait, max(1, int((refresh_at - now) * 1000)))
                screen.timeout(wait)
                screen.refresh()
                key = screen.getch()
                position["selected"] = selected
                if key == -1:
                    if live and (not animating or time.monotonic() >= refresh_at):
                        return REFRESH
                    continue
                if refresh_at is not None:
                    refresh_at = time.monotonic() + live
                if key == self.curses.KEY_UP:
                    selected = (selected - 1) % len(choices)
                elif key == self.curses.KEY_DOWN:
                    selected = (selected + 1) % len(choices)
                elif key in (10, 13, self.curses.KEY_ENTER):
                    return selected
                elif key == 27:
                    return None
        return self._run(draw)

    # =========================================================================
    # ================================= INPUT =================================

    def prompt(self, title, default=""):
        def draw(screen):
            self._setup(screen)
            value = default
            while True:
                screen.erase()
                height, width = screen.getmaxyx()
                self._header(screen, title)
                top, left, _, columns = self._panel(screen, 3, 1, height - 6, width - 2, "Input")
                self._line(screen, top, left, "> " + value[-max(1, columns - 2):])
                self._footer(screen, "Type | Backspace Delete | Enter Accept | Esc Back")
                screen.refresh()
                key = screen.get_wch()
                if key in ("\n", "\r", self.curses.KEY_ENTER):
                    return value.strip()
                if key == "\x1b":
                    return None
                if key in ("\b", "\x7f", self.curses.KEY_BACKSPACE):
                    value = value[:-1]
                elif isinstance(key, str) and key.isprintable():
                    value += key
        return self._run(draw)

    # =========================================================================
    # ========================== APPLICATION SCREENS ==========================

    # =========================================================================
    # =========================== SETUP CHECKLIST =============================

    def setup_checklist(self, components, selected, screen=None):
        """Return selected component IDs only after Start install; None cancels."""
        enabled = set(selected)

        def draw(screen):
            self._setup(screen)
            colors = {True: 0, False: 0}
            try:
                if self.colors_enabled() and self.curses.has_colors():
                    self.curses.start_color()
                    background = self.curses.COLOR_BLACK
                    try:
                        self.curses.use_default_colors()
                        background = -1
                    except self.curses.error:
                        pass
                    self.curses.init_pair(1, self.curses.COLOR_GREEN, background)
                    self.curses.init_pair(2, self.curses.COLOR_RED, background)
                    colors = {True: self.curses.color_pair(1), False: self.curses.color_pair(2)}
            except self.curses.error:
                pass  # Checkboxes remain usable on terminals without color.
            focus = 0
            while True:
                screen.erase()
                height, _ = screen.getmaxyx()
                start = self._entry_header(screen, "Welcome to TauFW fast installer!", len(components) + 4)
                self._line(screen, start, 0, "Please choose which of these to install")
                self._line(screen, start + 1, 0, "CMSSW setup and the TauFW build are always included.")
                start += 3
                rows = max(1, height - start - 2)
                first = max(0, focus - rows + 1)
                for index in range(first, min(len(components) + 2, first + rows)):
                    if index == len(components):
                        label, color = "[ Start install ]", 0
                    elif index == len(components) + 1:
                        label, color = "[ Cancel ]", 0
                    else:
                        component, label = components[index]
                        checked = component in enabled
                        label = ("[x] " if checked else "[ ] ") + label
                        color = colors[checked]
                    self._line(screen, index - first + start, 0, label, index == focus, color)
                self._line(screen, height - 2, 0,
                           "Up/Down Move | Space/Enter Select | Esc Cancel")
                screen.refresh()
                key = screen.getch()
                if self.resized(screen) or key in (self.curses.KEY_RESIZE, REDRAW):  # not guarded: as _Guarded._key
                    screen.clearok(True)
                if key == self.curses.KEY_UP:
                    focus = (focus - 1) % (len(components) + 2)
                elif key == self.curses.KEY_DOWN:
                    focus = (focus + 1) % (len(components) + 2)
                elif key in (32, 10, 13, self.curses.KEY_ENTER):
                    if focus == len(components):
                        return [name for name, _ in components if name in enabled]
                    if focus == len(components) + 1:
                        return None
                    component = components[focus][0]
                    if component in enabled:
                        enabled.remove(component)
                    else:
                        enabled.add(component)
                elif key == 27:
                    return None
        return draw(screen) if screen is not None else self._run(draw, guard=False)

    def _action(self, title, choices, actions, back="back", welcome=None, **layout):
        selected = self.choose(title, choices, welcome=welcome, **layout)
        return back if selected is None else REFRESH if selected == REFRESH else actions[selected]

    def main_menu(self, proxy_valid=False, tests=None, runs=(), live=False, version=None, config_reviewed=True):
        """tests: the last test run (a Framework._internal.operations.Operation) or None; its state is shown next to
        Tests ("Tests (Running 12/40)"). runs: the advances to show (Operations of kind "run": those behind the
        menu and those that ended unseen): one is a line of its own, "Run tes_2025 (3/5 plots)" (action "run"),
        more are "Runs (2 active)" (action "runs"). live: something runs behind the menu; without a key for
        LIVE_EVERY seconds the answer is REFRESH (the caller draws it again with the new states), the selected
        line stays. version is plain caller-supplied metadata, shown without a selectable action. config_reviewed
        False: the user config is missing or not reviewed yet; its line is "Modify User Config (Please set)".
        The full banner animates once per visit; only REFRESH keeps its animation start time."""
        notice = None
        if version:
            self.set_version('V' + version['installed'])
            if version['available']:
                text = 'New version available: %s (installed: %s)' % (version['latest'], version['installed'])
                if version['stale']:
                    text += ' [last known; check unavailable]' if version['error'] else ' [last checked earlier]'
                notice = (text, 'warning')
            elif version['checking']:
                notice = ('Checking for updates...', 'accent')
            elif version['status'] == 'unavailable':
                notice = ('Version check unavailable', 'warning')
        certificate = "Grid Certificate  " + ("\u2713" if proxy_valid else "Warning: Proxy Failed!")
        label, role = "Tests", None
        if tests is not None:
            text, role = self._operation_summary(tests)
            label = "Tests (%s)" % text
        choices = ["Start a new run", "Continue an existing run", "Inspect run status", certificate,
                   "Modify User Config" + ("" if config_reviewed else " (Please set)"), "Install components", label,
                   "Help", "Exit"]
        actions = ["start", "continue", "inspect", "grid_certificate", "user_config", "install", "tests",
                   "help", "exit"]
        colors = [None, None, None, "good" if proxy_valid else "warning", None if config_reviewed else "warning",
                  None, role, None, None]
        descriptions = [
            "Choose an analysis recipe and review its pipeline before starting.",
            "Resume a saved run behind the menu: to the end, or one step.",
            "Inspect the recorded and live status of an existing run.",
            "Create or renew your CMS grid proxy using your grid certificate password.",
            "Edit your personal settings; F2 saves after checking their values.",
            "Open the installer to choose optional components and start installation.",
            "Run automated checks or choose individual tests.",
            "Browse workflow explanations and frequently asked questions.",
            "Close the menu and return to your terminal.",
        ]
        if runs:
            label, role, action, description = self._runs_line(runs)
            choices.insert(3, label)
            actions.insert(3, action)
            colors.insert(3, role)
            descriptions.insert(3, description)
        position = dict(selected=actions.index(self._main_action) if self._main_action in actions else 0)
        if self._main_banner_started is None:
            self._main_banner_started = time.monotonic()
        answer = None
        try:
            answer = self._action("TauFW", choices, actions, back="exit", row_colors=colors,
                                  welcome="Welcome to TauFW!", descriptions=descriptions, position=position,
                                  live=LIVE_EVERY if live else None,
                                  separators=(actions.index("grid_certificate"), actions.index("tests")), notice=notice,
                                  banner_started=self._main_banner_started)
            self._main_action = actions[position["selected"]]
            return answer
        finally:
            if answer != REFRESH:
                self._main_banner_started = None

    def _runs_line(self, runs):
        """(label, role, action, description) of the main menu line of the advances behind the menu."""
        summaries = [self._operation_summary(operation) for operation in runs]
        if len(runs) == 1:
            return ("Run %s (%s)" % (runs[0].data.get("run_id", runs[0].title), summaries[0][0]), summaries[0][1],
                    "run", "Follow the run: its stages, their commands and logs; it goes on behind the menu.")
        active = sum(operation.running for operation in runs)
        parts = ["%d active" % active] if active else []
        if len(runs) > active:
            parts.append("%d ended" % (len(runs) - active))
        roles = [role for _, role in summaries]
        role = "error" if "error" in roles else "waiting" if active else "good"
        return "Runs (%s)" % ", ".join(parts), role, "runs", "Choose one of the runs behind the menu to follow it."

    def active_runs(self, operations):
        """Choose one of several advances behind the menu: ("select", index) or ("back", None)."""
        labels, colors = [], []
        for operation in operations:
            text, role = self._operation_summary(operation)
            where = " on %s" % operation.host if operation.remote else ""
            labels.append("%s: %s  %s%s" % (operation.data.get("run_id", operation.title), text,
                                             _clock(operation.elapsed()), where))
            colors.append(role)
        selected = self.choose("Runs behind the menu", labels + ["Back"], row_colors=colors + ["accent"])
        return ("back", None) if selected is None or selected == len(labels) else ("select", selected)

    def tests_menu(self, last=None):
        """last: the last test run (an Operation that ended) or None; "last" opens its screen."""
        choices = ["Run all automated tests", "Unit and harness checks", "Normal tests", "BBB regression checks",
                   "Check environment", "UI preview (mock screens)", "Back"]
        actions = ["all", "checks", "normal", "bbb", "environment", "preview", "back"]
        descriptions = [
            "Run all unit, harness, normal and BBB checks; requires CMSSW/ROOT and a BBB lock.",
            "Select unit suites or harness checks.",
            "Run local scripts. PASS means successful process exit; missing dependencies may SKIP.",
            "Compare exact data/schema against saved expectations; needs Linux Python 3.9 and a lock.",
            "Advisory CMSSW Python package-origin diagnostics; does not install or repair packages.",
            "Every menu screen with made-up data; nothing runs. Left/Right switch screens, Esc leaves.",
            "Return to the main menu."]
        colors = [None] * len(choices)
        if last is not None:
            text, role = self._operation_summary(last)
            choices.insert(0, "Last run: %s (%s)" % (last.title, text))
            actions.insert(0, "last")
            descriptions.insert(0, "Show the last test run: its cases, their logs and its output.")
            colors.insert(0, role)
        return self._action("Tests", choices, actions, descriptions=descriptions,
                            row_colors=colors if last is not None else None)

    def test_family(self, title):
        return self._action(title, ["Run entire family", "Choose tests", "Back"],
                            ["all", "choose", "back"])

    def test_selection(self, title, items, review=False):
        """Return IDs after Run, or None on Back; each screen restores curses."""
        enabled = {item["id"] for item in items} if review else set()

        def draw(screen):
            self._setup(screen)
            focus, offset = 0, 0
            while True:
                screen.erase()
                height, width = screen.getmaxyx()
                self._header(screen, title)
                page = 1
                list_height = max(4, (height - 6) // 2)
                top, left, rows, columns = self._panel(screen, 3, 1, list_height, width - 2,
                                                      "Review" if review else "Select tests")
                first = max(0, focus - rows + 1)
                for index in range(first, min(len(items) + 2, first + rows)):
                    if 0 < index <= len(items):
                        item = items[index - 1]
                        label = item["id"] if review else (
                            "[x] " if item["id"] in enabled else "[ ] ") + item["id"]
                    else:
                        label = "[ Run ]" if index == 0 else "Back"
                    self._line(screen, top + index - first, left, label[:columns], index == focus)
                rect = self._panel(screen, 3 + list_height, 1, height - list_height - 6,
                                   width - 2, "Details")
                if 0 < focus <= len(items):
                    item = items[focus - 1]
                    text = item["description"]
                    if item["dependencies"]:
                        text += "\nDependencies: " + ", ".join(item["dependencies"])
                else:
                    text = ("%d selected. Quiet output; failures show the last 80 lines and log paths."
                            % (len(items) if review else len(enabled))) if focus == 0 else "Return without running tests."
                offset, page = self._viewport(screen, rect, self._wrap(text, rect[3]), offset)
                self._footer(screen, "Up/Down Move | Enter Run/Back | PgUp/Dn Details | Esc Back"
                             if review else "Up/Down Move | Space Toggle | Enter Run/Back | PgUp/Dn Details | Esc Back")
                screen.refresh()
                key = screen.getch()
                if key == 27:
                    return None
                if key in (self.curses.KEY_UP, self.curses.KEY_DOWN):
                    focus = (focus + (1 if key == self.curses.KEY_DOWN else -1)) % (len(items) + 2)
                    offset = 0
                elif key == self.curses.KEY_NPAGE:
                    offset += page
                elif key == self.curses.KEY_PPAGE:
                    offset = max(0, offset - page)
                elif key == 32 and 0 < focus <= len(items) and not review:
                    name = items[focus - 1]["id"]
                    if name in enabled:
                        enabled.remove(name)
                    else:
                        enabled.add(name)
                elif key in (10, 13, self.curses.KEY_ENTER):
                    if focus == len(items) + 1:
                        return None
                    if focus == 0:
                        if enabled:
                            return [item["id"] for item in items if item["id"] in enabled]
                        self.curses.beep()
        return self._run(draw)

    def test_run(self, title, process, expected=()):
        """Follow a test run (a Framework._internal.operations.Operation) until the user leaves; the run goes on behind
        the menu. Return its exit code (None while it runs). expected: the case ids shown as waiting before they
        start."""
        # Imported here: FastSetup imports Menu on its own before TauFW is built, and never shows this screen.
        from ._test_run import follow_tests
        return self._run(lambda screen: follow_tests(self, screen, title, process, expected))

    def run_progress(self, title, process):
        """Follow an advance of a run (an Operation whose data holds run_id, run_dir and stages) until the user
        leaves; it goes on behind the menu. Return its exit code (None while it runs)."""
        from ._run_screen import follow_run  # imported here: see test_run()
        return self._run(lambda screen: follow_run(self, screen, title, process))

    def command_output(self, title, process, refresh=False):
        """Show the output of a read-only command behind the menu (an Operation, kind "command") until the user
        leaves; leaving stops it if it still runs. Return "refresh" (R once it ended, with refresh) or "back"."""
        from ._command_screen import follow_command  # imported here: see test_run()
        return self._run(lambda screen: follow_command(self, screen, title, process, refresh))

    def preview(self):
        """Every screen with made-up data (Tests > UI preview); Left/Right switch screens, Esc leaves."""
        from ._preview import preview  # imported here: see test_run()
        self._run(lambda screen: preview(self.curses, screen))

    def edit_file(self, path, validate=None, *, title="Text editor", reference=None):
        """Open the independent editor only on request; contain even its import/terminal errors."""
        try:
            from ..editor import edit_file

            def draw(screen):
                self._setup(screen)
                styles = dict(self.styles, muted=getattr(self.curses, "A_DIM", 0),
                              active=self.styles["accent"] | self.curses.A_BOLD)
                appearance = dict(styles=styles, banner=self._badge,
                                  banner_spans=((1, 2, "TauFW", "brand"), (2, 2, self.version, "version")))
                return edit_file(screen, path, validate=validate, title=title, reference=reference,
                                 appearance=appearance, curses_module=self.curses, follow_size=self.follow_size)

            result = self._run(draw)
            if result.error:
                raise RuntimeError(result.error)
            return result.saved
        except Exception as error:
            # Navigation treats raw curses errors as a failure of the entire
            # menu. An editor failure belongs to this action alone.
            raise RuntimeError("Editor: %s" % error) from error

    def quit_running(self, operations):
        """Ask before the menu closes while operations run behind it. Return "cancel" (stay in the menu), "stop"
        (stop them all, then quit) or "quit" (quit; they keep running)."""
        rows = []
        for operation in operations:
            text, role = self._operation_summary(operation)
            where = " on %s" % operation.host if operation.remote else ""
            rows.append(("%s: %s  %s%s" % (operation.title, text, _clock(operation.elapsed()), where), role))
        answers = {ord("q"): "quit", ord("Q"): "quit", ord("s"): "stop", ord("S"): "stop", 3: "cancel"}
        answers.update((key, "cancel") for key in (ord("c"), ord("C"), 27, 10, 13, self.curses.KEY_ENTER))
        return self._modal("Still running: quit TauFW?", rows + [("", None), (QUIT_WARNING, "warning")],
                           "C Cancel (stay) | S Stop all and quit | Q Quit anyway", answers.get)

    def _operation_summary(self, operation, kept=None):
        """(text, style role) of an operation's state for the menus; only the events added since the last draw
        are read, none once it ended."""
        summaries = self._summaries if kept is None else kept
        if operation.kind == "tests":
            from ._test_run import test_summary  # imported here: see test_run()
            return test_summary(operation, summaries.setdefault(operation.path, {}))
        if operation.kind == "run":
            from ._run_screen import run_summary  # imported here: see test_run()
            return run_summary(operation, summaries.setdefault(operation.path, {}))
        state = operation.state()
        return state.capitalize(), {"RUNNING": "accent", "DONE": "good", "FAILED": "error"}.get(state, "warning")

    def _pick(self, title, labels, manual_label):
        selected = self.choose(title, labels + [manual_label, "Back"])
        if selected is None or selected == len(labels) + 1:
            return "back", None
        if selected == len(labels):
            return "manual", None
        return "select", selected

    def select_recipe(self, names, preview=None, broken=None, warnings=None, checking=None, position=None,
                      live=False, drafts=None, examples=False):
        """Return (create/manual/examples/back/refresh, None) or (select/edit, recipe index).
        broken: True for each recipe with problems (shown in red). Warnings without problems are shown in yellow.
        checking: True for each recipe whose check is still read ("checking..."). position: the focus, kept by
        the caller across a refresh. [Examples] (the example analyses) is the row above Back; examples: the list
        of the examples, with only Back after them and no create action."""
        names = [name + (" [Draft]" if drafts and drafts[index] else "") +
                 ("  checking..." if checking and checking[index] else "") for index, name in enumerate(names)]
        # The rows around the recipes: (action, label, color, hint).
        head = [] if examples else [("create", "[Create a new run]", "accent",
                                     "Create a new analysis with an empty recipe.\n\n"
                                     "You will first choose an analysis name.\n\n"
                                     "Configure its pipeline with E before starting a run.")]
        tail = ([("back", "Back", None, "Return to the list of analyses.")] if examples else
                [("manual", "Enter another recipe path", None,
                  "Enter a recipe file or bundle directory to review its pipeline."),
                 ("examples", "[Examples]", "accent",
                  "Example analyses (Analyses/Examples/): ready-made recipes to learn from or to copy.\n\n"
                  "They are listed apart from your analyses."),
                 ("back", "Back", None, "Return to the main menu.")])
        first = len(head)  # the index of the first recipe row
        rows = head + [("select", name, None, None) for name in names] + tail
        choices = [row[1] for row in rows]
        # an empty line between the recipes and the menu's own rows (above and below them)
        separators = sorted({gap for gap in (first, first + len(names)) if 0 < gap < len(choices)})

        def view(index):
            if first <= index < first + len(names):
                return preview(index - first)
            return dict(hint=rows[index][3])

        colors = ["error" if flag else "warning" if (warnings and warnings[index]) or
                  (drafts and drafts[index]) else None
                  for index, flag in enumerate(broken or [False] * len(names))]
        if preview is None:
            selected = self.choose("Select an example" if examples else "Select a recipe", choices,
                                   separators=separators)
        else:
            selected = self._pipeline_choice("Start a new run / %s" % ("Examples" if examples else "Select a recipe"),
                                             choices, view,
                                             row_colors=[row[2] for row in head] + colors + [row[2] for row in tail],
                                             position=position, live=LIST_EVERY if live else None,
                                             edit_indices=range(first, first + len(names)), separators=separators)
        if selected == REFRESH:
            return REFRESH, None
        if isinstance(selected, tuple):
            return "edit", selected[1] - first
        if selected is None:
            return "back", None
        action = rows[selected][0]
        return (action, selected - first) if action == "select" else (action, None)

    def analysis_name(self, default=""):
        return self.prompt("Define analysis name", default=default)

    def recipe_path(self, launch_dir):
        return self.prompt("Recipe path (relative to %s)" % launch_dir)

    def recipe_plan(self, title, view, position=None, update=None):
        """The plan of a recipe (operations.prepare_plan; see _plan_screen.py). Return "start", "edit" or
        "back". position: the selected row and the details' offset, kept by the caller across an edit. update:
        while stages are checking, None or the whole plan that replaces view in place (check_plan's poll)."""
        position = position if position is not None else {}
        return self._run(lambda screen: show_plan(self, screen, title, view, position, update))

    def select_run(self, summaries, advances=None, loading=None, position=None, live=False,
                   preview=None, mode="inspect", finding=False, advance_labels=None):
        """Summaries are (run_id, state, updated); state=None marks unreadable runs. advances: an Operation (kind
        "run") or None per summary: the advance of that run behind the menu, shown after its row
        ("| advancing: 3/5 plots, 5/7 commands"). loading: True for each run whose run.json is still read
        ("loading...", its directory name as run_id). live: (refresh, None) when no key came in LIST_EVERY s;
        position: the focus, kept by the caller."""
        loading = loading or [False] * len(summaries)
        id_width = min(36, max([len(row[0]) for row in summaries] or [0]))
        labels = []
        for (run_id, state, updated), waiting in zip(summaries, loading):
            label = (run_id if len(run_id) <= id_width else run_id[:id_width - 3] + "...").ljust(id_width)
            labels.append("%s | loading..." % label if waiting else "%s | UNREADABLE" % label if state is None else
                          "%s | %-7s | updated %s" % (label, state, updated))
        colors = [None if waiting else "error" if state in (None, "FAILED", "BLOCKED") else
                  "good" if state == "DONE" else "waiting" for (_, state, _), waiting in zip(summaries, loading)]
        for index, operation in enumerate(advances or ()):
            if operation is not None:
                (text, colors[index]), running = advance_labels[index] if advance_labels is not None else \
                    (self._operation_summary(operation), operation.running)
                labels[index] += " | %s: %s" % ("advancing" if running else "advance", text)
        if preview is not None and self.curses is not None:
            from ._run_picker import pick
            return self._run(lambda screen: pick(self, screen,
                             labels + ["Enter another run directory", "Back"], colors + ["accent", "accent"],
                             summaries, preview, mode, position if position is not None else {}, live, finding))
        selected = self.choose("Select an existing run", labels + ["Enter another run directory", "Back"],
                               row_colors=colors + ["accent", "accent"], position=position,
                               live=LIST_EVERY if live else None, badge=True,
                               separators=(len(labels),) if labels else ())  # an empty line after the runs
        if selected == REFRESH:
            return REFRESH, None
        if selected is None or selected == len(labels) + 1:
            return "back", None
        return ("manual", None) if selected == len(labels) else ("select", selected)

    def run_lock(self, run_id, lock):
        """The run is locked by an advance (the run lock that Framework.advance holds while it works). lock: host,
        pid, since (text), quiet (seconds since its last sign of life), lost (True: none for too long).
        Return "take" (take over the lock of a lost advance) or "back"."""
        where = "on %s since %s (pid %s)" % (lock.get("host", "?"), lock.get("since", "?"), lock.get("pid", "?"))
        quiet = _clock(lock.get("quiet", 0))
        if lock.get("lost"):
            title, footer = "Advance lost", "T Take over | Esc Back"
            rows = [("The advance of this run %s gave no sign of life for %s." % (where, quiet), "warning"),
                    ("", None),
                    ("If it is really gone (logout, crash), take over its run lock and continue the run.", None),
                    ("If it still runs, taking over could submit the same jobs twice.", "warning")]
        else:
            title, footer = "Advance running", "Esc Back"
            rows = [("An advance of this run is already running %s; last sign of life %s ago." % (where, quiet),
                     "waiting"), ("", None),
                    ("Follow it where it was started, or wait until it ends: two advances at once could submit the "
                     "same jobs twice.", None)]

        def draw(screen):
            self._setup(screen)
            while True:
                screen.erase()
                height, width = screen.getmaxyx()
                self._header(screen, "Run %s" % run_id)
                top, left, lines, columns = self._panel(screen, 3, 1, height - 6, width - 2, title)
                content = [(line, self.styles.get(role, 0)) for text, role in rows
                           for line in self._wrap(text, columns)]
                for row, (text, color) in enumerate(content[:lines]):
                    self._line(screen, top + row, left, text[:columns], color=color)
                self._footer(screen, footer)
                screen.refresh()
                try:
                    key = screen.getch()
                except KeyboardInterrupt:
                    return "back"
                if key in (ord("t"), ord("T")) and lock.get("lost"):
                    return "take"
                if key in (27, 10, 13, self.curses.KEY_ENTER):
                    return "back"
        return self._run(draw)

    def run_path(self, launch_dir):
        return self.prompt("Run directory (relative to %s)" % launch_dir)

    def run_actions(self, view):
        """The actions of a run (a run_preview view, see _run_picker._actions) as a list, for a terminal too narrow
        for the run picker's two panes: the action's key, or "back"."""
        from ._run_picker import ACTION_HELP, _actions, help_key
        choices = _actions(view)
        title = "Continue: %s (%s)" % (view.get("run_id", "?"), view.get("state", "?"))
        return self._action(title, [label for _, label in choices] + ["Back"], [key for key, _ in choices] + ["back"],
                            descriptions=[ACTION_HELP.get(help_key(key, view), "") for key, _ in choices] +
                            ["Choose another run."])

    def stage_choice(self, title, view, mode, position=None):
        """Rerun from... (mode "rerun") or Advance until... ("until"): ("pick", stage id) or ("back", None); view:
        the operations' stage_choices (see _run_tools.pick_stage)."""
        from ._run_tools import pick_stage
        position = position if position is not None else {}
        return self._run(lambda screen: pick_stage(self, screen, title, view, mode, position))

    def confirm_rerun(self, row, pending=None, failed=None):
        """The panel before a rerun from a stage (a stage_choices row with its plan): "all" (to the end), "one"
        (that stage only, the others wait: --next) or None (cancel). failed: the retry_info of a FAILED run's
        stage, which this rerun starts from (its message; production: its tries)."""
        from ._run_tools import rerun_lines
        plan, stage = row["plan"], row["id"]
        lines = [("It failed with: " + (failed.get("message") or "?"), "error"), ("", None)] if failed else []
        if plan.get("production"):
            made, limit = failed["tries"] if failed and failed.get("tries") else (0, 0)
            lines += [("Resubmit the failed chunks of %s with %d more tries (up to try %d), then go on to the end. "
                       "The job files and merged tuples stay where they are; the stages before it are kept."
                       % (stage, limit - made, limit), None)]
            choices, answers = ["Resubmit %s and go on" % stage, "Cancel"], ["all", None]
        else:
            moved = [item["stage"] for item in plan["rows"]]
            lines += [("%s run%s again: %s." % ("%d stages" % len(moved) if len(moved) > 1 else "1 stage",
                                               "" if len(moved) > 1 else "s", ", ".join(moved)), None),
                      ("Nothing is deleted: what they made before stays in logs/<id>/attempt<N>/ (History shows "
                       "it).", None)]
            lines += [line for line in rerun_lines(row, pending) if line[1] == "warning"]
            if len(moved) > 1:
                choices = ["Rerun to the end", "Rerun %s only (the others wait)" % stage, "Cancel"]
                answers = ["all", "one", None]
            else:
                choices, answers = ["Rerun %s" % stage, "Cancel"], ["all", None]
        index = self.ask("Rerun from %s?" % stage, lines, choices)
        return None if index is None else answers[index]

    def run_files(self, title, files, read, position=None):
        """The files of a run or an analysis bundle with the selected one beside them: ("edit", index) or ("back",
        None) (see _run_tools.pick_file); read(path): its lines."""
        from ._run_tools import pick_file
        position = position if position is not None else {}
        return self._run(lambda screen: pick_file(self, screen, title, files, read, position))

    def run_history(self, title, view, read_log, position=None):
        """History of a run (the operations' run_history; see _run_tools.show_history) until Esc."""
        from ._run_tools import show_history
        position = position if position is not None else {}
        return self._run(lambda screen: show_history(self, screen, title, view, read_log, position))

    def ask(self, title, lines, choices):
        """A panel over the current screen with text and a choice: the index of the choice, or None (Esc).
        lines: (text, role) pairs."""
        def draw(screen):
            self._setup(screen)
            selected, size = 0, screen.getmaxyx()
            while True:
                size = self._below(screen, size)
                rows = list(lines) + [("", None)] + [(("> " if index == selected else "  ") + choice,
                                                      "accent" if index == selected else None)
                                                     for index, choice in enumerate(choices)]
                self._overlay(screen, title, rows, "Up/Down Choose | Enter Select | Esc Cancel", offset=len(rows))
                try:
                    key = screen.getch()
                except KeyboardInterrupt:
                    return None
                if key in (27, 3):
                    return None
                if key in (10, 13, self.curses.KEY_ENTER):
                    return selected
                if key in (self.curses.KEY_UP, self.curses.KEY_DOWN):
                    selected = (selected + (1 if key == self.curses.KEY_DOWN else -1)) % len(choices)
        return self._run(draw)

    def _log_panel(self, screen, title, lines):
        """A long text (a log) in a panel over the screen it is drawn on, until Enter or Esc; Up/Down/PgUp/PgDn
        scroll it."""
        rows, offset, size = [(line, None) for line in lines], 0, screen.getmaxyx()
        while True:
            size = self._below(screen, size)
            offset, page = self._overlay(screen, title, rows, "Up/Down/PgUp/PgDn Scroll | Enter or Esc Close", offset)
            try:
                key = screen.getch()
            except KeyboardInterrupt:
                key = 3
            if key in (10, 13, 27, 3, self.curses.KEY_ENTER):
                screen.erase()
                return
            step = {self.curses.KEY_UP: -1, self.curses.KEY_DOWN: 1, self.curses.KEY_PPAGE: -page,
                    self.curses.KEY_NPAGE: page}
            offset = max(0, offset + step.get(key, 0))

    def grid_proxy_needed(self):
        """The run may submit jobs and the grid proxy is not valid: "renew" or "back"."""
        return self._action("Grid proxy needed", ["Renew grid proxy", "Back"], ["renew", "back"],
                            descriptions=["The run may submit or resubmit jobs, which read their input with your "
                                          "grid proxy. It runs behind the menu and cannot ask for your "
                                          "certificate password: renew the proxy now.",
                                          "Do not start the run."])

    # =========================================================================
    # ================================== HELP =================================

    def help(self):
        def draw(screen):
            self._setup(screen)
            selected, offset = 0, 0
            while True:
                screen.erase()
                height, width = screen.getmaxyx()
                self._header(screen, "Help")
                topics = self._panel(screen, 3, 1, height - 6, 27, "Topics")
                body = self._panel(screen, 3, 27, height - 6, width - 28, "Explanation")
                top, left, rows, columns = topics
                first = max(0, selected - rows + 1)
                for index in range(first, min(len(FAQ), first + rows)):
                    label = ("> " if index == selected else "  ") + FAQ[index][0]
                    self._line(screen, index - first + top, left, label[:columns], index == selected)
                lines = self._wrap(FAQ[selected][1], body[3])
                offset, rows = self._viewport(screen, body, lines, offset)
                self._footer(screen, "Up/Down Topic | PgUp/PgDn Scroll | Esc Back")
                screen.refresh()
                key = screen.getch()
                if key == 27:
                    return
                if key in (self.curses.KEY_UP, self.curses.KEY_DOWN):
                    selected = (selected + (1 if key == self.curses.KEY_DOWN else -1)) % len(FAQ)
                    offset = 0
                elif key == self.curses.KEY_NPAGE:
                    offset += rows
                elif key == self.curses.KEY_PPAGE:
                    offset = max(0, offset - rows)
        self._run(draw)

    # =========================================================================
    # ================================ MESSAGES ===============================

    def message(self, title, lines, role=None):
        """A panel over the current screen until Enter or Esc; lines: text, or (text, role) pairs."""
        lines = [(lines, role)] if isinstance(lines, str) else lines
        return self._modal(title, lines, "Enter OK", lambda key: "ok" if key in (10, 13, 27, 3, self.curses.KEY_ENTER)
                           else None)

    def operation_error(self, error):
        """The error in a panel over the current screen until Enter or Esc."""
        bell()
        self.message("Error", "%s: %s" % (type(error).__name__, error), "error")

    def unreadable_run(self, error):
        bell()
        self.message("Cannot read run", str(error), "error")

    def notice(self, title, text):
        """A panel over the current screen that waits for nothing (the menu works on, e.g. "Renewing...")."""
        def draw(screen):
            self._setup(screen)
            self._overlay(screen, title, [(text, None)], "")
        self._run(draw)

    def grid_password(self):
        """The grid certificate password typed in a panel (shown as *), or None (Esc). Kept nowhere."""
        def draw(screen):
            self._setup(screen)
            value, size = "", screen.getmaxyx()
            while True:
                size = self._below(screen, size)
                self._overlay(screen, "Grid Certificate", [
                    ("Renew your CMS grid proxy (voms-proxy-init -voms cms). The password goes to voms-proxy-init "
                     "only; it is not shown, kept or written anywhere.", None), ("", None),
                    ("Certificate password: " + "*" * len(value), "accent")], "Type | Enter Renew | Esc Back",
                    offset=len(value) + 1000)  # a small terminal: the end, the field, is shown
                try:
                    key = screen.get_wch()
                except KeyboardInterrupt:
                    return None
                if key in ("\n", "\r", self.curses.KEY_ENTER):
                    return value if value else None
                if key in ("\x1b", "\x03"):
                    return None
                if key in ("\b", "\x7f", self.curses.KEY_BACKSPACE):
                    value = value[:-1]
                elif isinstance(key, str) and key.isprintable():
                    value += key
        return self._run(draw)

    def grid_result(self, valid, output=""):
        """The end of a renewal: "Grid proxy active.", or why it failed with the end of voms-proxy-init's output."""
        if valid:
            return self.message("Grid Certificate", "Grid proxy active.", "good")
        lines = [("Proxy Failed! Check your grid certificate and password, then retry Grid Certificate.", "error")]
        tail = [line for line in str(output or "").splitlines() if line.strip()][-6:]
        return self.message("Grid Certificate", lines + ([("", None)] + [(line, None) for line in tail]
                                                         if tail else []))

    # =========================================================================
    # =============================== PANELS ==================================

    def _modal(self, title, lines, footer, answer):
        """A panel over the current screen until answer(key) is not None (Up/Down/PgUp/PgDn scroll a long text);
        return that answer. Ctrl-C is the key 3. lines: (text, role) pairs, wrapped to the panel."""
        def draw(screen):
            self._setup(screen)
            offset, size = 0, screen.getmaxyx()
            while True:
                size = self._below(screen, size)
                offset, page = self._overlay(screen, title, lines, footer, offset)
                try:
                    key = screen.getch()
                except KeyboardInterrupt:
                    key = 3
                result = answer(key)
                if result is not None:
                    return result
                step = {self.curses.KEY_UP: -1, self.curses.KEY_DOWN: 1, self.curses.KEY_PPAGE: -page,
                        self.curses.KEY_NPAGE: page}
                offset = max(0, offset + step.get(key, 0))
        return self._run(draw)

    @staticmethod
    def _below(screen, size):
        """What is below a panel was drawn for the size it had when the panel opened: after a resize it is cleared
        (the screen draws itself again once the panel closes). Return the current size."""
        if screen.getmaxyx() != size:
            screen.erase()
        return screen.getmaxyx()

    def _overlay(self, screen, title, lines, footer, offset=0):
        """Draw a panel in the middle of the screen over what is there (the rows it covers are cleared); return
        (offset, rows of text shown): a text longer than the panel scrolls."""
        height, width = screen.getmaxyx()
        box = max(10, min(width - 4, MODAL_WIDTH))
        wrapped = [(part, role) for text, role in lines for part in self._wrap(text, box - 4)]
        rows = max(1, min(len(wrapped), height - 8))
        tall = rows + (4 if footer else 2)
        top, left = max(0, (height - tall) // 2), max(0, (width - box) // 2)
        for row in range(top, top + tall):
            self._line(screen, row, left, " " * box)
        inner = self._panel(screen, top, left, tall, box, title)
        colors = [role for _, role in wrapped]
        offset, shown = self._viewport(screen, (inner[0], inner[1], rows, inner[3]), [text for text, _ in wrapped],
                                       offset, line_colors=colors)
        if footer:
            self._line(screen, top + tall - 2, inner[1], footer[:inner[3]], color=self.styles["accent"])
        screen.refresh()
        return offset, shown


