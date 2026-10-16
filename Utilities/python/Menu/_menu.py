# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Terminal presentation, screen actions, and menu wording.

No Framework imports or workflow decisions belong here. Curses is loaded only
when open() is called. Each screen restores the terminal before returning.
"""
import os
import sys
import textwrap

from .faq import FAQ
from .banner import BOXED, COMPACT, FULL, INTERACTIONS, VERSION, WIDTH


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
        self.styles = dict(accent=0, good=0, waiting=0, error=0)
        try:
            if self.colors_enabled() and self.curses.has_colors():
                self.curses.start_color()
                background = self.curses.COLOR_BLACK
                try:
                    self.curses.use_default_colors()
                    background = -1
                except self.curses.error:
                    pass
                for role, pair, foreground in (
                    ("accent", 3, self.curses.COLOR_CYAN),
                    ("good", 1, self.curses.COLOR_GREEN),
                    ("waiting", 8, self.curses.COLOR_YELLOW),
                    ("error", 2, self.curses.COLOR_RED),
                ):
                    self.curses.init_pair(pair, foreground, background)
                    self.styles[role] = self.curses.color_pair(pair)
        except self.curses.error:
            self.styles = dict(accent=0, good=0, waiting=0, error=0)
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

    def _header(self, screen, title):
        self._line(screen, 0, 1, "TauFW " + VERSION, color=self.styles["accent"])
        self._line(screen, 1, 1, title)

    def _footer(self, screen, text):
        height, _ = screen.getmaxyx()
        self._line(screen, height - 2, 1, text, color=self.styles["accent"])

    @staticmethod
    def _wrap(value, width):
        return [line for paragraph in str(value).splitlines()
                for line in (textwrap.wrap(paragraph, max(1, width)) or [""])] or [""]

    def _pipeline_lines(self, view, width, show_path=False, compact=False):
        """Turn presentation data into a vertical, scrollable ASCII pipeline."""
        lines = self._wrap("Recipe: " + view.get("name", ""), width)
        if view.get("error"):
            return lines + [""] + self._wrap("Cannot preview: " + view["error"], width)
        if view.get("hint"):
            return self._wrap(view["hint"], width)
        if show_path:
            lines += self._wrap("Path: " + view.get("path", ""), width)
        problems = view.get("problems", ())
        if problems:
            lines += ["", "%d problem(s):" % len(problems)]
            for problem in problems:
                lines += self._wrap("- " + problem, width)
            lines += [""]
        warnings = view.get("warnings", ())
        if warnings:  # the recipe can run, but should change
            lines += ["", "%d warning(s):" % len(warnings)] if not problems else ["%d warning(s):" % len(warnings)]
            for warning in warnings:
                lines += self._wrap("- " + warning, width)
            lines += [""]
        stages = view.get("stages", ())
        if not compact:
            lines += ["%d stage(s)" % len(stages), ""]
        card_width = max(6, min(width, 32))
        padding = " " * max(0, (width - card_width) // 2)
        edge = padding + "+" + "-" * (card_width - 2) + "+"
        for index, (stage_id, stage_type, description) in enumerate(stages):
            if index:
                center = padding + " " * (card_width // 2)
                lines += [center + "|", center + "v"]
            labels = self._wrap("%d. %s" % (index + 1, stage_id), card_width - 4)
            labels += self._wrap(description or "", card_width - 4)
            lines += [edge]
            lines += [padding + "| " + label.center(card_width - 4) + " |" for label in labels]
            lines += [edge]
        notes = view.get("notes", ())
        if notes:
            lines += ["", "Planning notes:"]
            for note in notes:
                lines += self._wrap(note, width) + [""]
        return lines

    def _viewport(self, screen, rect, lines, offset, color=0):
        top, left, rows, width = rect
        visible = max(1, rows - (1 if len(lines) > rows else 0))
        offset = min(max(0, offset), max(0, len(lines) - visible))
        for index, line in enumerate(lines[offset:offset + visible]):
            self._line(screen, top + index, left, line[:width], color=color)
        if len(lines) > rows:
            self._line(screen, top + rows - 1, left,
                       ("Lines %d-%d/%d" % (offset + 1, min(len(lines), offset + visible),
                                            len(lines)))[:width], color=self.styles["accent"])
        return offset, visible

    def _pipeline_choice(self, title, choices, preview, review=False, position=None, row_colors=None):
        """Two equal columns, with independent recipe/action and pipeline scrolling.
        row_colors: a style name per choice (e.g. "error"), or None."""
        position = position if position is not None else {}

        def draw(screen):
            self._setup(screen)
            selected, offset = position.get("selected", 0), position.get("offset", 0)
            while True:
                screen.erase()
                height, width = screen.getmaxyx()
                self._header(screen, title)
                usable = width >= 64 and height >= 12
                page = 1
                if usable:
                    panel_width = (width - 1) // 2
                    left = (width - (2 * panel_width - 1)) // 2
                    left_rect = self._panel(screen, 3, left, height - 6, panel_width,
                                            "Actions" if review else "Recipes")
                    right_rect = self._panel(screen, 3, left + panel_width - 1,
                                             height - 6, panel_width, "Pipeline")
                    top, column, rows, columns = left_rect
                    self._line(screen, top, column, "Action" if review else "Recipe / bundle",
                               color=self.styles["accent"])
                    top, rows = top + 2, max(1, rows - 2)
                    first = max(0, selected - rows + 1)
                    for index in range(first, min(len(choices), first + rows)):
                        label = ("> " if index == selected else "  ") + choices[index]
                        role = row_colors[index] if row_colors and index < len(row_colors) else None
                        self._line(screen, top + index - first, column, label[:columns],
                                   index == selected, self.styles.get(role, 0) if role else 0)
                    view = preview(selected)
                    lines = self._pipeline_lines(view, right_rect[3], show_path=review,
                                                 compact=right_rect[2] <= 6)
                    broken = view.get("error") or view.get("problems")
                    offset, page = self._viewport(screen, right_rect, lines, offset,
                                                  self.styles["error"] if broken else 0)
                else:
                    self._line(screen, 3, 1, "Enlarge terminal (at least 64 x 12).")
                self._footer(screen, "Up/Down Move | Enter Select | PgUp/Dn Pipeline | Esc Back")
                screen.refresh()
                key = screen.getch()
                if key == 27:
                    position.update(selected=selected, offset=offset)
                    return None
                if not usable:
                    continue
                if key in (self.curses.KEY_UP, self.curses.KEY_DOWN):
                    selected = (selected + (1 if key == self.curses.KEY_DOWN else -1)) % len(choices)
                    if not review:
                        offset = 0
                elif key == self.curses.KEY_NPAGE:
                    offset += page
                elif key == self.curses.KEY_PPAGE:
                    offset = max(0, offset - page)
                elif key in (10, 13, self.curses.KEY_ENTER):
                    position.update(selected=selected, offset=offset)
                    return selected
        return self.curses.wrapper(draw)

    def _entry_header(self, screen, welcome, minimum_rows):
        """Reserve room for controls, using compact branding on smaller terminals."""
        height, width = screen.getmaxyx()
        if width > WIDTH and height >= len(FULL) + minimum_rows + 5:
            lines = FULL
        elif width > len(BOXED[0]) and height >= len(BOXED) + minimum_rows + 5:
            lines = BOXED
        else:
            lines = COMPACT
        if height < len(lines) + minimum_rows + 5:
            lines = ("TauFW " + VERSION,)
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
                if lines is FULL:
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
        if lines is FULL and interaction_colors:
            for row, column, text, role in INTERACTIONS:
                self._line(screen, row, column, text, color=interaction_colors[role])
        self._line(screen, len(lines) + 1, 0, welcome)
        return len(lines) + 3

    def choose(self, title, choices, welcome=None, descriptions=None, row_colors=None):
        def draw(screen):
            self._setup(screen)
            selected = 0
            while True:
                screen.erase()
                height, width = screen.getmaxyx()
                if welcome is None:
                    self._header(screen, title)
                    start = 3
                else:
                    start = self._entry_header(screen, welcome, len(choices) + 3)
                top, left, rows, columns = self._panel(screen, start, 1,
                                                      height - start - 3, width - 2, "Menu")
                show_description = descriptions and rows >= len(choices) + 3
                if show_description:
                    rows -= 3
                stride = 2 if rows >= 2 * len(choices) - 1 else 1
                rows = max(1, (rows + stride - 1) // stride)
                first = max(0, selected - rows + 1)
                for index in range(first, min(len(choices), first + rows)):
                    label = ("> " if index == selected else "  ") + choices[index]
                    role = row_colors[index] if row_colors and index < len(row_colors) else "accent"
                    self._line(screen, (index - first) * stride + top, left, label[:columns],
                               index == selected, self.styles.get(role, 0) if row_colors else 0)
                if show_description:
                    for index, line in enumerate(self._wrap(descriptions[selected], columns)[:2]):
                        self._line(screen, height - 6 + index, left, line,
                                   color=self.styles["accent"])
                self._footer(screen, "Up/Down Move | Enter Select | Esc Back")
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

    def _action(self, title, choices, actions, back="back", welcome=None, **layout):
        selected = self.choose(title, choices, welcome=welcome, **layout)
        return back if selected is None else actions[selected]

    def main_menu(self):
        return self._action("TauFW", ["Start a new run", "Continue an existing run",
                                     "Inspect run status", "Tests", "Help", "Exit"],
                            ["start", "continue", "inspect", "tests", "help", "exit"], back="exit",
                            welcome="Welcome to TauFW!", descriptions=[
                                "Choose an analysis recipe and review its pipeline before starting.",
                                "Resume a saved run, once or with repeated checking.",
                                "Inspect the recorded and live status of an existing run.",
                                "Run automated checks or choose individual tests.",
                                "Browse workflow explanations and frequently asked questions.",
                                "Close the menu and return to your terminal.",
                            ])

    def tests_menu(self):
        return self._action("Tests", ["Run all automated tests", "Unit and harness checks",
                            "Normal tests", "BBB regression checks", "Check environment", "Back"],
                            ["all", "checks", "normal", "bbb", "environment", "back"], descriptions=[
                                "Run all unit, harness, normal and BBB checks; requires CMSSW/ROOT and a BBB lock.",
                                "Select unit suites or harness checks.",
                                "Run local scripts. PASS means successful process exit; missing dependencies may SKIP.",
                                "Compare exact data/schema against saved expectations; needs Linux Python 3.9 and a lock.",
                                "Advisory CMSSW Python package-origin diagnostics; does not install or repair packages.",
                                "Return to the main menu."])

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
                usable = height >= 12 and width >= 40
                page = 1
                if usable:
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
                else:
                    self._line(screen, 3, 1, "Enlarge terminal (at least 40 x 12).")
                self._footer(screen, "Up/Down Move | Enter Run/Back | PgUp/Dn Details | Esc Back"
                             if review else "Up/Down Move | Space Toggle | Enter Run/Back | PgUp/Dn Details | Esc Back")
                screen.refresh()
                key = screen.getch()
                if key == 27:
                    return None
                if not usable:
                    continue
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
        return self.curses.wrapper(draw)

    def interrupted_tests(self):
        print("\nTest run cancelled. Returning to the testing menu.")

    def _pick(self, title, labels, manual_label):
        selected = self.choose(title, labels + [manual_label, "Back"])
        if selected is None or selected == len(labels) + 1:
            return "back", None
        if selected == len(labels):
            return "manual", None
        return "select", selected

    def select_recipe(self, names, preview=None, broken=None):
        """Return (select, index), (manual, None), or (back, None). broken: True for each recipe with problems
        (shown in red)."""
        if preview is None:
            return self._pick("Select a recipe", names, "Enter another recipe path")

        def view(index):
            if index < len(names):
                return preview(index)
            return dict(hint="Enter a recipe file or bundle directory to review its pipeline."
                        if index == len(names) else "Return to the main menu.")

        colors = ["error" if flag else None for flag in (broken or [False] * len(names))]
        selected = self._pipeline_choice("Start a new run / Select a recipe",
                                         names + ["Enter another recipe path", "Back"], view,
                                         row_colors=colors + [None, None])
        if selected is None or selected == len(names) + 1:
            return "back", None
        return ("manual", None) if selected == len(names) else ("select", selected)

    def recipe_path(self, launch_dir):
        return self.prompt("Recipe path (relative to %s)" % launch_dir)

    def confirm_recipe(self, path, review=None, position=None):
        choices, actions = ["Start run", "View detailed plan", "Back"], ["start", "plan", "back"]
        if review is None:
            return self._action("Recipe: %s" % path, choices, actions)
        selected = self._pipeline_choice("Start a new run / Review", choices,
                                         lambda index: review, review=True, position=position)
        return "back" if selected is None else actions[selected]

    def select_run(self, summaries):
        """Summaries are (run_id, state, updated); state=None marks unreadable runs."""
        id_width = min(36, max([len(row[0]) for row in summaries] or [0]))
        labels = []
        for run_id, state, updated in summaries:
            label = (run_id if len(run_id) <= id_width else run_id[:id_width - 3] + "...").ljust(id_width)
            labels.append("%s | UNREADABLE" % label if state is None else
                          "%s | %-7s | updated %s" % (label, state, updated))
        colors = ["error" if state in (None, "FAILED", "BLOCKED") else
                  "good" if state == "DONE" else "waiting" for _, state, _ in summaries]
        selected = self.choose("Select an existing run", labels + ["Enter another run directory", "Back"],
                               row_colors=colors + ["accent", "accent"])
        if selected is None or selected == len(labels) + 1:
            return "back", None
        return ("manual", None) if selected == len(labels) else ("select", selected)

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
                self._header(screen, "Help")
                if width < 55 or height < 8:
                    self._line(screen, 3, 1, "Enlarge terminal for FAQ (at least 55 x 8).")
                    rows = 1
                else:
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

