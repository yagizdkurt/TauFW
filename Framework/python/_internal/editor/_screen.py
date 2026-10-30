# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Curses editor screen. Owns its window; never imports Menu or starts a session."""
import textwrap

from ._buffer import Buffer
from ._reference import Reference
from ._text import TAB_SIZE, _tail, _visible, _width

MIN_COLUMNS = 80  # the menu's minimum (menu/_menu.py MIN_COLUMNS, MIN_ROWS), with the same notice below it
MIN_ROWS = 24
TOO_SMALL = ("Terminal too small: at least %d x %d." % (MIN_COLUMNS, MIN_ROWS),
             "Enlarge it, or use the taufw commands (taufw --help).")
TOO_SMALL_FOOTER = "Esc or Ctrl+C to close"
SPLIT_COLUMNS = 110
HEADER_ROWS = 3
FRAME_AND_FOOTER_ROWS = 5
LARGE_BANNER_TEXT_ROWS = 16  # branding must still leave a useful page of text
MODAL_COLUMNS = 76


class Editor:
    def __init__(self, parent, curses, document, title, validate, appearance=None, reference=None):
        self.parent, self.curses, self.document = parent, curses, document
        self.title, self.validate = title, validate
        self.appearance = appearance or {}
        self.styles = dict(self.appearance.get("styles", {}))
        self.buffer = Buffer(document.text)
        self.reference = Reference(reference) if reference is not None else None
        self.reference_visible = True
        self.reference_focus = False
        self.cursor_visibility = 1
        self.window = None
        self.dimensions = None
        self.top = self.left = 0
        self.page = 1
        self.saved = False
        self.status = ""
        self.confirm = False
        self.problem = None
        self.problem_offset = 0
        self.problem_page = 1
        self.frame_top = HEADER_ROWS

    @property
    def dirty(self):
        return self.buffer.text != self.document.text

    def run(self):
        cursor = None
        try:
            try:
                cursor = self.curses.curs_set(1)
            except self.curses.error:
                pass  # Some terminals cannot change the cursor's visibility.
            while True:
                try:
                    self.draw()
                    try:
                        key = self.window.get_wch()
                    except KeyboardInterrupt:
                        key = "\x03"
                except self.curses.error:
                    if self.parent.getmaxyx() != self.dimensions:
                        self.dimensions = None
                        continue  # A resize can invalidate a draw already in progress.
                    raise
                if key == "\x0c":  # Ctrl+L: the next draw sends the whole screen again
                    self.window.clearok(True)
                    continue
                if not self.usable() and key not in ("\x1b", "\x03"):
                    continue  # nothing is shown: no edit either
                if self.key(key):
                    return
        finally:
            # No echo/raw/color settings are changed. A separate window keeps
            # the menu's timeout and keypad settings intact, also on failure.
            try:
                if cursor is not None:
                    self.curses.curs_set(cursor)
            except self.curses.error:
                pass
            finally:
                self.parent.touchwin()

    def usable(self):
        height, width = self.parent.getmaxyx()
        return height >= MIN_ROWS and width >= MIN_COLUMNS

    def write(self, row, column, text, attribute=0):
        height, width = self.dimensions
        if 0 <= row < height and 0 <= column < width - 1:
            self.window.addstr(row, column, _visible(str(text), 0, width - column - 1), attribute)

    def style(self, role):
        defaults = {"muted": getattr(self.curses, "A_DIM", 0), "active": self.curses.A_BOLD}
        return self.styles.get(role, defaults.get(role, 0))

    def panel(self, top, left, height, width, title="", role="accent"):
        attribute = self.style(role)
        if height >= 3 and width >= 6:
            edge = "+" + "-" * (width - 2) + "+"
            self.write(top, left, edge, attribute)
            self.write(top + height - 1, left, edge, attribute)
            for row in range(top + 1, top + height - 1):
                self.write(row, left, "|", attribute)
                self.write(row, left + width - 1, "|", attribute)
            if title:
                self.write(top, left + 2, " " + _visible(title, 0, width - 6) + " ", attribute)
            return top + 1, left + 2, height - 2, width - 4
        return top, left, max(1, height), max(1, width)

    def header(self, usable):
        height, width = self.dimensions
        lines = self.appearance.get("banner", ()) if usable else ()
        spans = self.appearance.get("banner_spans", ())
        large = self.appearance.get("large_banner", ())
        if (usable and large and max(map(_width, large)) <= width - 2
                and height - len(large) - HEADER_ROWS - FRAME_AND_FOOTER_ROWS >= LARGE_BANNER_TEXT_ROWS):
            lines = large
            spans = self.appearance.get("large_banner_spans", ())
        side = lines and len(lines) <= HEADER_ROWS
        header_rows = HEADER_ROWS if side or not lines else len(lines) + HEADER_ROWS
        if lines and (max(map(_width, lines)) > width - 2
                      or height - header_rows - FRAME_AND_FOOTER_ROWS < 2):
            lines = ()
        if lines:
            for row, line in enumerate(lines):
                self.write(row, 1, line, self.style("accent"))
            for row, column, text, role in spans:
                self.write(row, column + 1, text, self.style(role))
            column = max(map(_width, lines)) + 3 if side else 2
            row = 1 if side else len(lines) + 1
            self.frame_top = HEADER_ROWS if side else len(lines) + HEADER_ROWS
        else:
            row, column, self.frame_top = 0, 1, HEADER_ROWS
        self.write(row, column, self.title, self.curses.A_BOLD)
        self.write(row + 1, column, _tail(str(self.document.path), max(0, width - column - 1)),
                   self.style("muted"))

    def draw(self):
        dimensions = self.parent.getmaxyx()
        if dimensions != self.dimensions:
            self.dimensions = dimensions
            self.window = self.curses.newwin(*dimensions, 0, 0)
            self.window.keypad(True)
            self.window.timeout(-1)
            self.window.clearok(True)  # a resize: the terminal may have rewrapped what was shown, send all again
        height, width = dimensions
        self.window.erase()
        if not self.usable():  # only the notice; unsaved changes wait until the terminal is large enough again
            lines = TOO_SMALL + (("", "Unsaved changes: enlarge the terminal to save or discard them.")
                                 if self.confirm else ())
            for row, text in enumerate(lines):
                self.write(row + 1, 1, text, self.style("warning") if row >= len(TOO_SMALL) else 0)
            self.write(height - 2, 1, TOO_SMALL_FOOTER, self.style("accent"))
            self.window.refresh()
            return
        self.header(True)
        cursor = None
        body_height = height - self.frame_top - 3
        split = self.reference and self.reference_visible and width >= SPLIT_COLUMNS
        editor_width = (width - 2) // 2 if split else width - 2
        if not self.reference_focus or split:
            name = self.document.path.name + (" *" if self.dirty else "")
            if self.reference and not self.reference_focus:
                name = "> " + name
            rect = self.panel(self.frame_top, 1, body_height, editor_width, _tail(name, editor_width - 6),
                              "muted" if self.reference_focus else "accent")
            cursor = self.draw_buffer(rect)
            self.draw_status(editor_width if split else None)
        if self.reference and (self.reference_focus or split):
            left = editor_width + 2 if split else 1
            panel_width = width - left - 1
            name = ("> " if self.reference_focus else "") + self.reference.path.name + " (read only)"
            rect = self.panel(self.frame_top, left, body_height, panel_width,
                              _tail(name, panel_width - 6), "accent" if self.reference_focus else "muted")
            self.draw_reference(rect)
        if self.reference:
            self.write(height - 2, 1, "F2 Save | Esc Back | F4 Docs | F5 Pane", self.style("accent"))
            hint = "Arrows/PgUp/Dn Scroll | Home/End" if self.reference_focus else "Arrows/PgUp/Dn Move | Tab Indent"
            self.write(height - 1, 1, hint, self.style("muted"))
        else:
            self.write(height - 2, 1, "F2 Save | Esc Back | Tab Indent", self.style("accent"))
        if self.problem is not None:
            self.problem_offset, self.problem_page = self.overlay(
                "Cannot save", ["Your edits are still here.", "", self.problem],
                "PgUp/Dn Scroll | Enter/Esc Edit", "error", self.problem_offset)
        elif self.confirm:
            self.overlay("Unsaved changes", ["Save your changes before leaving?", "",
                         "F2  Save and leave", "D   Discard unsaved changes", "Esc Keep editing"],
                         "F2 Save | D Discard | Esc Edit", "warning")
        elif cursor is not None and not self.reference_focus:
            self.window.move(*cursor)
        if self.reference:
            visibility = int(cursor is not None and not self.reference_focus
                             and not self.confirm and self.problem is None)
            if visibility != self.cursor_visibility:
                try:
                    self.curses.curs_set(visibility)
                except self.curses.error:
                    pass
                self.cursor_visibility = visibility
        self.window.refresh()

    def draw_buffer(self, rect):
        top, left, self.page, columns = rect
        digits = max(2, len(str(len(self.buffer.lines))))
        gutter = digits + 4  # pointer, line number, separator and space
        columns = max(1, columns - gutter)
        self.top = max(0, min(self.top, self.buffer.row))
        self.top = max(self.top, self.buffer.row - self.page + 1)
        column = _width(self.buffer.lines[self.buffer.row][:self.buffer.column])
        self.left = max(0, min(self.left, column))
        self.left = max(self.left, column - columns + 1)
        for index, line in enumerate(self.buffer.lines[self.top:self.top + self.page], self.top):
            row = top + index - self.top
            active = index == self.buffer.row
            number = (">" if active else " ") + str(index + 1).rjust(digits) + " | "
            self.write(row, left, number, self.style("active" if active else "muted"))
            self.write(row, left + gutter, _visible(line, self.left, columns),
                       self.style("active") if active else 0)
        return top + self.buffer.row - self.top, left + gutter + column - self.left

    def draw_reference(self, rect):
        top, left, page, columns = rect
        reference = self.reference
        reference.layout(columns, page)
        for index, (_, text, role) in enumerate(reference.rows[reference.top:reference.top + page]):
            self.write(top + index, left, _visible(text, reference.left, columns), self.style(role))
        position = "Lines %d-%d/%d" % (reference.top + 1, min(len(reference.rows), reference.top + page),
                                       len(reference.rows))
        if reference.left:
            position += " | Col %d" % (reference.left + 1)
        self.write(self.dimensions[0] - 3, left, _visible(position, 0, columns), self.style("muted"))

    def draw_status(self, panel_width=None):
        height, width = self.dimensions
        width = panel_width or width
        state = "Modified" if self.dirty else self.status or "Unchanged"
        role = "warning" if self.dirty else "good" if self.saved else "muted"
        self.write(height - 3, 2, _visible("Ln %d, Col %d | %s" % (
            self.buffer.row + 1, self.buffer.column + 1, state), 0, width - 4), self.style(role))
        position = "Lines %d-%d/%d" % (self.top + 1, min(len(self.buffer.lines), self.top + self.page),
                                       len(self.buffer.lines))
        if width - _width(position) - 2 > 30 + len(state):
            self.write(height - 3, width - _width(position) - 2, position, self.style("muted"))

    def overlay(self, title, paragraphs, footer, role, offset=0):
        """Cover only the editor body; the banner and file path remain visible."""
        height, width = self.dimensions
        box_width = max(1, min(MODAL_COLUMNS, width - 4))
        columns = max(1, box_width - 4)
        lines = [line for paragraph in paragraphs for part in paragraph.split("\n")
                 for line in (textwrap.wrap(part, columns) or [""])]
        first = self.frame_top if height >= MIN_ROWS else min(HEADER_ROWS, max(0, height - 4))
        available = max(1, height - 3 - first)
        box_height = min(available, len(lines) + 3)
        top, left = first + (available - box_height) // 2, max(0, (width - box_width) // 2)
        for row in range(top, top + box_height):
            self.write(row, left, " " * box_width)
        inner_top, inner_left, _, _ = self.panel(top, left, box_height, box_width, title, role)
        page = max(1, box_height - 3)
        offset = max(0, min(offset, len(lines) - page))
        for index, line in enumerate(lines[offset:offset + page]):
            self.write(inner_top + index, inner_left, _visible(line, 0, columns))
        self.write(top + box_height - 2, inner_left, _visible(footer, 0, columns), self.style("accent"))
        return offset, page

    def save(self):
        try:
            if self.dirty:
                self.document.save(self.buffer.text, self.validate)
                self.saved = True
                self.status = "Saved"
            else:
                self.status = "No changes to save"
            return True
        except (Exception, KeyboardInterrupt) as error:
            self.problem = "%s: %s" % (type(error).__name__, error)
            self.problem_offset = 0
            self.confirm = False
            return False

    def key(self, key):
        curses, buffer = self.curses, self.buffer
        save = key == curses.KEY_F2
        leave = key in ("\x1b", "\x03", curses.KEY_F10)
        if self.problem is not None:
            if leave or key in ("\n", "\r", curses.KEY_ENTER):
                self.problem = None
            elif key in (curses.KEY_NPAGE, curses.KEY_PPAGE):
                self.problem_offset += (1 if key == curses.KEY_NPAGE else -1) * self.problem_page
            return False
        if self.confirm:
            if save:
                return self.save()
            if key in ("d", "D"):
                return True
            if leave or key in ("n", "N"):
                self.confirm = False
            return False
        if leave:
            self.confirm = self.dirty
            return not self.confirm
        if save:
            self.save()
        elif self.reference and key == curses.KEY_F4:
            shown = self.reference_focus or (self.reference_visible and self.dimensions[1] >= SPLIT_COLUMNS)
            self.reference_visible = not shown
            self.reference_focus = not shown
        elif self.reference and key == curses.KEY_F5:
            self.reference_focus = not self.reference_focus
            self.reference_visible = True
        elif self.reference_focus:
            reference = self.reference
            if key in (curses.KEY_UP, curses.KEY_DOWN):
                reference.move(rows=-1 if key == curses.KEY_UP else 1)
            elif key in (curses.KEY_PPAGE, curses.KEY_NPAGE):
                reference.move(rows=-reference.page if key == curses.KEY_PPAGE else reference.page)
            elif key in (curses.KEY_LEFT, curses.KEY_RIGHT):
                reference.move(columns=-4 if key == curses.KEY_LEFT else 4)
            elif key == curses.KEY_HOME:
                reference.top = reference.left = 0
            elif key == curses.KEY_END:
                reference.move(rows=len(reference.rows))
        elif key == curses.KEY_UP:
            buffer.vertical(-1)
        elif key == curses.KEY_DOWN:
            buffer.vertical(1)
        elif key in (curses.KEY_LEFT, curses.KEY_RIGHT):
            buffer.horizontal(-1 if key == curses.KEY_LEFT else 1)
        elif key in (curses.KEY_PPAGE, curses.KEY_NPAGE):
            buffer.vertical(-self.page if key == curses.KEY_PPAGE else self.page)
        elif key == curses.KEY_HOME:
            buffer.place(buffer.row, 0)
        elif key == curses.KEY_END:
            buffer.place(buffer.row, len(buffer.lines[buffer.row]))
        elif key in ("\b", "\x7f", curses.KEY_BACKSPACE):
            buffer.backspace()
        elif key == curses.KEY_DC:
            buffer.delete()
        elif key in ("\n", "\r", curses.KEY_ENTER):
            buffer.insert("\n")
        elif key == "\t":
            buffer.insert(" " * (TAB_SIZE - _width(buffer.lines[buffer.row][:buffer.column]) % TAB_SIZE))
        elif isinstance(key, str) and key.isprintable():
            buffer.insert(key)
        return False
