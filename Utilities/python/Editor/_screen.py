# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Curses editor screen. Owns its window; never imports Menu or starts a session."""
import textwrap
import unicodedata

from ._buffer import Buffer

TAB_SIZE = 2
MIN_COLUMNS = 40
MIN_ROWS = 10
CONTENT_TOP = 3
BOTTOM_ROWS = 3


def _characters(text):
    """Display text safely, expanding tabs without changing the buffer."""
    column = 0
    for character in text:
        if character == "\t":
            for _ in range(TAB_SIZE - column % TAB_SIZE):
                yield " ", 1
                column += 1
        else:
            character = character if character.isprintable() else "?"
            width = 0 if unicodedata.combining(character) else (
                2 if unicodedata.east_asian_width(character) in ("W", "F") else 1)
            yield character, width
            column += width


def _width(text):
    return sum(width for _, width in _characters(text))


def _visible(text, offset, columns):
    result, position = [], 0
    for character, width in _characters(text):
        end = position + width
        if position >= offset + columns:
            break
        if position >= offset:
            result.append(character if end <= offset + columns else " ")
        elif end > offset:
            result.append(" " * (end - offset))
        position = end
    return "".join(result)


class Editor:
    def __init__(self, parent, curses, document, title, validate):
        self.parent, self.curses, self.document = parent, curses, document
        self.title, self.validate = title, validate
        self.buffer = Buffer(document.text)
        self.window = None
        self.dimensions = None
        self.top = self.left = 0
        self.page = 1
        self.saved = False
        self.status = ""
        self.confirm = False
        self.problem = None
        self.problem_offset = 0

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

    def write(self, row, column, text, attribute=0):
        height, width = self.dimensions
        if 0 <= row < height and 0 <= column < width - 1:
            self.window.addstr(row, column, _visible(str(text), 0, width - column - 1), attribute)

    def draw(self):
        dimensions = self.parent.getmaxyx()
        if dimensions != self.dimensions:
            self.dimensions = dimensions
            self.window = self.curses.newwin(*dimensions, 0, 0)
            self.window.keypad(True)
            self.window.timeout(-1)
        height, width = dimensions
        self.window.erase()
        self.write(0, 1, self.title, self.curses.A_BOLD)
        self.write(1, 1, str(self.document.path))
        self.page = max(1, height - CONTENT_TOP - BOTTOM_ROWS)
        usable = height >= MIN_ROWS and width >= MIN_COLUMNS
        if usable:
            gutter = max(4, len(str(len(self.buffer.lines))) + 1)
            columns = max(1, width - gutter - 2)
            self.top = max(0, min(self.top, self.buffer.row))
            self.top = max(self.top, self.buffer.row - self.page + 1)
            column = _width(self.buffer.lines[self.buffer.row][:self.buffer.column])
            self.left = max(0, min(self.left, column))
            self.left = max(self.left, column - columns + 1)
            for index, line in enumerate(self.buffer.lines[self.top:self.top + self.page], self.top):
                row = CONTENT_TOP + index - self.top
                self.write(row, 0, str(index + 1).rjust(gutter - 1))
                self.write(row, gutter, _visible(line, self.left, columns))
            self.write(height - 3, 1, "Ln %d, Col %d | %s%s" % (
                self.buffer.row + 1, self.buffer.column + 1, "Modified" if self.dirty else "Unchanged",
                " | " + self.status if self.status else ""))
        else:
            self.write(min(2, max(0, height - 3)), 0,
                       "Enlarge terminal (at least %d x %d)." % (MIN_COLUMNS, MIN_ROWS))
        self.write(height - 2, 0, "F2 Save | Esc Back | Tab Indent", self.curses.A_REVERSE)
        if self.problem is not None:
            self.draw_problem()
        elif self.confirm:
            self.window.erase()
            self.write(0, 1, "Unsaved changes", self.curses.A_BOLD)
            self.write(2, 1, "Save your changes before leaving?")
            self.write(4, 1, "F2  Save and leave")
            self.write(5, 1, "D   Discard unsaved changes")
            self.write(6, 1, "Esc Keep editing")
        elif usable:
            self.window.move(CONTENT_TOP + self.buffer.row - self.top, gutter + column - self.left)
        self.window.refresh()

    def draw_problem(self):
        height, width = self.dimensions
        lines = [line for paragraph in self.problem.splitlines()
                 for line in (textwrap.wrap(paragraph, max(1, width - 3)) or [""])]
        page = max(1, height - 4)
        self.problem_offset = max(0, min(self.problem_offset, len(lines) - page))
        self.window.erase()
        self.write(0, 1, "Cannot save; your edits are still here", self.curses.A_BOLD)
        for row, line in enumerate(lines[self.problem_offset:self.problem_offset + page], 2):
            self.write(row, 1, line)
        self.write(height - 2, 0, "PgUp/Dn Scroll | Enter/Esc Edit", self.curses.A_REVERSE)

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
                self.problem_offset += (1 if key == curses.KEY_NPAGE else -1) * max(1, self.dimensions[0] - 4)
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
