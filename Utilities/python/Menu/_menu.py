"""Terminal presentation, screen actions, and menu wording.

No Framework imports or workflow decisions belong here. Curses is loaded only
when open() is called. Each screen restores the terminal before returning.
"""
import os
import sys
import textwrap

from .faq import FAQ
from .banner import COMPACT, FULL, VERSION, WIDTH


class ConsoleUI:
    """Small curses screens; no Framework or batch logic."""

    # =========================================================================
    # =========================== TERMINAL LIFECYCLE ==========================

    def __init__(self, curses):
        self.curses = curses

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
            curses.setupterm()
        except (ImportError, OSError) as error:
            print("The TauFW menu requires curses and a supported terminal: %s" % error, file=sys.stderr)
            parser.print_help()
            return None
        except Exception as error:
            print("Cannot initialize the TauFW terminal menu: %s" % error, file=sys.stderr)
            parser.print_help()
            return None
        return cls(curses)

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

    def _entry_header(self, screen, welcome, minimum_rows):
        """Reserve room for controls, using compact branding on smaller terminals."""
        height, width = screen.getmaxyx()
        lines = FULL if width > WIDTH and height >= len(FULL) + minimum_rows + 5 else COMPACT
        if height < len(lines) + minimum_rows + 5:
            lines = ("TauFW " + VERSION,)
        color = 0
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
        except self.curses.error:
            pass
        for row, line in enumerate(lines):
            self._line(screen, row, 0, line, color=color)
        self._line(screen, len(lines) + 1, 0, welcome)
        return len(lines) + 3

    def choose(self, title, choices, welcome=None):
        def draw(screen):
            self._setup(screen)
            selected = 0
            while True:
                screen.erase()
                height, _ = screen.getmaxyx()
                if welcome is None:
                    self._line(screen, 0, 0, title)
                    start = 2
                else:
                    start = self._entry_header(screen, welcome, len(choices))
                rows = max(1, height - start - 2)
                first = max(0, selected - rows + 1)
                for index in range(first, min(len(choices), first + rows)):
                    self._line(screen, index - first + start, 0,
                               ("> " if index == selected else "  ") + choices[index],
                               index == selected)
                self._line(screen, height - 2, 0, "Up/Down Move | Enter Select | Esc Back")
                screen.refresh()
                key = screen.getch()
                if key == self.curses.KEY_UP:
                    selected = (selected - 1) % len(choices)
                elif key == self.curses.KEY_DOWN:
                    selected = (selected + 1) % len(choices)
                elif key in (10, 13, self.curses.KEY_ENTER):
                    return selected
                elif key == 27:
                    return None
        return self.curses.wrapper(draw)

    # =========================================================================
    # ================================= INPUT =================================

    def prompt(self, title, default=""):
        def draw(screen):
            self._setup(screen)
            value = default
            while True:
                screen.erase()
                height, width = screen.getmaxyx()
                self._line(screen, 0, 0, title)
                self._line(screen, 2, 0, "> " + value[-max(1, width - 4):])
                self._line(screen, height - 2, 0, "Type | Backspace Delete | Enter Accept | Esc Back")
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
        return self.curses.wrapper(draw)

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
                start = self._entry_header(screen, "Welcome to TauFW fast installer!", len(components) + 3)
                self._line(screen, start, 0, "Please choose which of these to install")
                self._line(screen, start + 1, 0, "CMSSW setup and the TauFW build are always included.")
                start += 3
                rows = max(1, height - start - 2)
                first = max(0, focus - rows + 1)
                for index in range(first, min(len(components) + 1, first + rows)):
                    if index == len(components):
                        label, color = "[ Start install ]", 0
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
                if key == self.curses.KEY_UP:
                    focus = (focus - 1) % (len(components) + 1)
                elif key == self.curses.KEY_DOWN:
                    focus = (focus + 1) % (len(components) + 1)
                elif key in (32, 10, 13, self.curses.KEY_ENTER):
                    if focus == len(components):
                        return [name for name, _ in components if name in enabled]
                    component = components[focus][0]
                    if component in enabled:
                        enabled.remove(component)
                    else:
                        enabled.add(component)
                elif key == 27:
                    return None
        return draw(screen) if screen is not None else self.curses.wrapper(draw)

    def _action(self, title, choices, actions, back="back", welcome=None):
        selected = self.choose(title, choices) if welcome is None else self.choose(title, choices, welcome=welcome)
        return back if selected is None else actions[selected]

    def main_menu(self):
        return self._action("TauFW", ["Start a new run", "Continue an existing run",
                                     "Inspect run status", "Help", "Exit"],
                            ["start", "continue", "inspect", "help", "exit"], back="exit",
                            welcome="Welcome to TauFW!")

    def _pick(self, title, labels, manual_label):
        selected = self.choose(title, labels + [manual_label, "Back"])
        if selected is None or selected == len(labels) + 1:
            return "back", None
        if selected == len(labels):
            return "manual", None
        return "select", selected

    def select_recipe(self, names):
        """Return (select, index), (manual, None), or (back, None)."""
        return self._pick("Select a recipe", names, "Enter another recipe path")

    def recipe_path(self, launch_dir):
        return self.prompt("Recipe path (relative to %s)" % launch_dir)

    def confirm_recipe(self, path):
        return self._action("Recipe: %s" % path, ["Start run", "Back"], ["start", "back"])

    def select_run(self, summaries):
        """Summaries are (run_id, state, updated); state=None marks unreadable runs."""
        labels = ["%s | UNREADABLE" % run_id if state is None else
                  "%s | %s | updated %s" % (run_id, state, updated)
                  for run_id, state, updated in summaries]
        return self._pick("Select an existing run", labels, "Enter another run directory")

    def run_path(self, launch_dir):
        return self.prompt("Run directory (relative to %s)" % launch_dir)

    def status_actions(self, run_id):
        return self._action("Run status: %s" % run_id, ["Refresh", "Back"], ["refresh", "back"])

    def terminal_run_actions(self, state):
        return self._action("Run is %s; it cannot advance." % state,
                            ["Inspect status", "Back"], ["inspect", "back"])

    def continue_actions(self, run_id):
        return self._action("Continue: %s" % run_id, ["Advance once", "Keep checking", "Back"],
                            ["advance", "wait", "back"])

    def poll_interval(self):
        return self.prompt("Polling interval in seconds", "600")

    # =========================================================================
    # ================================== HELP =================================

    def help(self):
        def draw(screen):
            self._setup(screen)
            selected, offset = 0, 0
            while True:
                screen.erase()
                height, width = screen.getmaxyx()
                self._line(screen, 0, 0, "TauFW Help")
                if width < 55 or height < 8:
                    self._line(screen, 2, 0, "Enlarge terminal for FAQ (at least 55 x 8).")
                else:
                    left = 27
                    rows = max(1, height - 5)
                    first = max(0, selected - rows + 1)
                    for index in range(first, min(len(FAQ), first + rows)):
                        self._line(screen, index - first + 2, 0, FAQ[index][0], index == selected)
                    lines = textwrap.wrap(FAQ[selected][1], width - left - 2)
                    offset = min(offset, max(0, len(lines) - rows))
                    for index, line in enumerate(lines[offset:offset + rows]):
                        self._line(screen, index + 2, left, line)
                self._line(screen, height - 2, 0, "Up/Down Topic | PgUp/PgDn Scroll | Esc Back")
                screen.refresh()
                key = screen.getch()
                if key == 27:
                    return
                if key in (self.curses.KEY_UP, self.curses.KEY_DOWN):
                    selected = (selected + (1 if key == self.curses.KEY_DOWN else -1)) % len(FAQ)
                    offset = 0
                elif key == self.curses.KEY_NPAGE:
                    offset += max(1, height - 5)
                elif key == self.curses.KEY_PPAGE:
                    offset = max(0, offset - max(1, height - 5))
        self.curses.wrapper(draw)

    # =========================================================================
    # ================================ MESSAGES ===============================

    def pause(self):
        try:
            input("\nPress Enter to return to the menu...")
        except (KeyboardInterrupt, EOFError):
            pass

    def operation_error(self, error):
        """Report without pausing; command dispatch owns its finally-pause."""
        print("%s: %s" % (type(error).__name__, error))

    def interrupted_operation(self):
        print("\nForeground operation interrupted. Submitted batch jobs are not cancelled. "
              "Use the saved run record to continue.")

    def unreadable_run(self, error):
        print("Cannot read run: %s" % error)
        self.pause()

    def invalid_poll_interval(self):
        print("Enter a positive integer number of seconds.")
        self.pause()

