"""Independent editor: text preservation, failed saves and real screen key handling without curses."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import checkout
from TauFW.Utilities.Editor import edit_file
from TauFW.Utilities.Editor._buffer import Buffer
from TauFW.Utilities.Editor._file import Document
from TauFW.Utilities.Editor._screen import _visible, _width


class TerminalError(Exception):
    pass


class Terminal:
    """A parent screen plus separate windows, with scripted Unicode keys and resizes."""
    error = TerminalError
    A_BOLD, A_REVERSE = 1, 2
    (KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_HOME, KEY_END, KEY_PPAGE,
     KEY_NPAGE, KEY_BACKSPACE, KEY_DC, KEY_ENTER, KEY_F2, KEY_F10, KEY_RESIZE) = range(1000, 1014)

    def __init__(self, keys, dimensions=(16, 64)):
        self.keys = iter(keys)
        self.dimensions = dimensions
        self.frames, self.cursors = [], []
        self.touched = 0

    def getmaxyx(self):
        return self.dimensions

    def touchwin(self):
        self.touched += 1

    def curs_set(self, visibility):
        self.cursors.append(visibility)
        return 0

    def newwin(self, height, width, top, left):
        return Window(self, height, width)


class Window:
    def __init__(self, terminal, height, width):
        self.terminal, self.height, self.width = terminal, height, width

    def keypad(self, enabled):
        pass

    def timeout(self, milliseconds):
        pass

    def erase(self):
        self.lines = [" " * self.width for _ in range(self.height)]

    def addstr(self, row, column, text, attribute=0):
        if not 0 <= row < self.height or column + _width(text) >= self.width:
            raise TerminalError("Draw outside window")
        line = self.lines[row]
        self.lines[row] = line[:column] + text + line[column + len(text):]

    def move(self, row, column):
        if not (0 <= row < self.height and 0 <= column < self.width):
            raise TerminalError("Cursor outside window")

    def refresh(self):
        self.terminal.frames.append("\n".join(self.lines))

    def get_wch(self):
        key = next(self.terminal.keys)
        if isinstance(key, BaseException):
            raise key
        return key() if callable(key) else key


class EditorTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / "settings.yaml"
        self.path.write_text("# keep this comment\nvalue: old\n", encoding="utf-8")

    def open(self, keys, validate=None, dimensions=(16, 64)):
        terminal = Terminal(keys, dimensions)
        result = edit_file(terminal, self.path, validate=validate, curses_module=terminal)
        self.assertIsNone(result.error)
        self.assertEqual(terminal.cursors, [1, 0])
        self.assertEqual(terminal.touched, 1)
        return result, terminal

    def test_text_operations_preserve_empty_lines_and_vertical_cursor_column(self):
        buffer = Buffer("alpha\nx\nlong line\n")
        buffer.place(0, 4)
        buffer.vertical(1)
        self.assertEqual((buffer.row, buffer.column), (1, 1))
        buffer.vertical(1)
        self.assertEqual((buffer.row, buffer.column), (2, 4))
        buffer.insert("\n  new")
        self.assertEqual(buffer.text, "alpha\nx\nlong\n  new line\n")
        buffer.place(3, 0)
        buffer.backspace()
        self.assertEqual(buffer.text, "alpha\nx\nlong  new line\n")
        buffer.delete()
        self.assertEqual(buffer.text, "alpha\nx\nlong new line\n")
        buffer.place(0, 5)
        buffer.delete()
        self.assertEqual(buffer.text, "alphax\nlong new line\n")
        buffer.horizontal(1)
        buffer.horizontal(1)
        self.assertEqual((buffer.row, buffer.column), (1, 0))

    def test_save_keeps_comments_custom_sections_unicode_bom_and_crlf(self):
        original = b"\xef\xbb\xbf# comment\r\ncustom:\r\n  value: old\r\n"
        self.path.write_bytes(original)
        document = Document(self.path)
        seen = []
        document.save(document.text.replace("old", "Çağrı"), lambda path: seen.append(path.read_bytes()))
        expected = original.replace(b"old", "Çağrı".encode("utf-8"))
        self.assertEqual(self.path.read_bytes(), expected)
        self.assertEqual(seen, [expected])
        self.assertEqual(list(self.root.iterdir()), [self.path])
        if os.name != "nt":
            self.path.chmod(0o640)
            document = Document(self.path)
            document.save(document.text + "# end\n")
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o640)

    def test_failed_validation_or_replace_keeps_the_original_and_removes_draft(self):
        original = self.path.read_bytes()
        for validate in (lambda path: ["ncores must be positive"], lambda path: "bad YAML"):
            with self.subTest(validate=validate):
                document = Document(self.path)
                with self.assertRaisesRegex(OSError, "ncores|YAML"):
                    document.save("invalid", validate)
                self.assertEqual(self.path.read_bytes(), original)
                self.assertEqual(document.text, "# keep this comment\nvalue: old\n")
                self.assertEqual(list(self.root.iterdir()), [self.path])
        with mock.patch("TauFW.Utilities.Editor._file.os.replace", side_effect=OSError("disk unavailable")):
            with self.assertRaisesRegex(OSError, "disk unavailable"):
                Document(self.path).save("changed")
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.root.iterdir()), [self.path])

    def test_external_changes_before_or_during_validation_are_not_overwritten(self):
        for during_validation in (False, True):
            with self.subTest(during_validation=during_validation):
                self.path.write_text("original", encoding="utf-8")
                document = Document(self.path)

                def change(path=None):
                    self.path.write_text("external change", encoding="utf-8")

                if not during_validation:
                    change()
                with self.assertRaisesRegex(OSError, "changed outside"):
                    document.save("editor change", change if during_validation else None)
                self.assertEqual(self.path.read_text(), "external change")
                self.assertEqual(list(self.root.iterdir()), [self.path])

    def test_edit_save_and_return_use_a_separate_window_and_restore_cursor(self):
        result, terminal = self.open([Terminal.KEY_DOWN, Terminal.KEY_END, "!", Terminal.KEY_F2, "\x1b"])
        self.assertTrue(result.saved)
        self.assertIn("value: old!", self.path.read_text())
        self.assertIn("Saved", "\n".join(terminal.frames))

    def test_discard_keep_editing_and_save_on_exit(self):
        original = self.path.read_bytes()
        result, terminal = self.open(["X", "\x1b", "\x1b", "Y", "\x1b", "d"])
        self.assertFalse(result.saved)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertIn("Unsaved changes", "\n".join(terminal.frames))
        result, _ = self.open(["X", KeyboardInterrupt(), Terminal.KEY_F2])
        self.assertTrue(result.saved)
        self.assertEqual(self.path.read_bytes(), b"X" + original)

    def test_bad_save_keeps_the_buffer_for_correction(self):
        self.path.write_text("old", encoding="utf-8")
        drafts = []

        def validate(path):
            drafts.append(path.read_text())
            return ["Remove !"] if "!" in drafts[-1] else None

        result, terminal = self.open([Terminal.KEY_END, "!", Terminal.KEY_F2, "\n",
                                      Terminal.KEY_BACKSPACE, "?", Terminal.KEY_F2, "\x1b"], validate)
        self.assertTrue(result.saved)
        self.assertEqual(drafts, ["old!", "old?"])
        self.assertEqual(self.path.read_text(), "old?")
        self.assertIn("Remove !", "\n".join(terminal.frames))

    def test_resize_and_long_unicode_lines_do_not_change_text(self):
        original = "Çağrı " + "界" * 90 + "\n" + "\n".join("line %d" % i for i in range(40))
        self.path.write_text(original, encoding="utf-8")
        terminal = Terminal([])

        def shrink():
            terminal.dimensions = (5, 20)
            return Terminal.KEY_RESIZE

        def enlarge():
            terminal.dimensions = (14, 45)
            return Terminal.KEY_RESIZE

        terminal.keys = iter([Terminal.KEY_END, shrink, enlarge, Terminal.KEY_NPAGE,
                              Terminal.KEY_PPAGE, "\x1b"])
        result = edit_file(terminal, self.path, curses_module=terminal)
        self.assertIsNone(result.error)
        self.assertFalse(result.saved)
        self.assertEqual(self.path.read_text(encoding="utf-8"), original)
        self.assertIn("Enlarge terminal", "\n".join(terminal.frames))
        self.assertEqual(_width("a\t界e\u0301"), 5)
        self.assertEqual(_visible("a界z", 2, 2), " z")

    def test_unexpected_draw_failure_is_returned_after_terminal_cleanup(self):
        terminal = Terminal([])
        with mock.patch.object(Window, "refresh", side_effect=TerminalError("broken editor draw")):
            result = edit_file(terminal, self.path, curses_module=terminal)
        self.assertIn("broken editor draw", result.error)
        self.assertEqual(terminal.cursors, [1, 0])
        self.assertEqual(terminal.touched, 1)
        self.assertFalse(result.saved)

    def test_resize_during_a_draw_retries_without_losing_the_buffer(self):
        terminal = Terminal(["X", Terminal.KEY_F2, "\x1b"])
        refresh = Window.refresh

        def resize(window):
            if terminal.dimensions == (16, 64):
                terminal.dimensions = (12, 50)
                raise TerminalError("resized during draw")
            refresh(window)

        with mock.patch.object(Window, "refresh", resize):
            result = edit_file(terminal, self.path, curses_module=terminal)
        self.assertIsNone(result.error)
        self.assertTrue(result.saved)
        self.assertTrue(self.path.read_text().startswith("X# keep"))

    def test_missing_file_returns_an_error_without_starting_the_terminal(self):
        terminal = Terminal([])
        result = edit_file(terminal, self.root / "missing", curses_module=terminal)
        self.assertIn("FileNotFoundError", result.error)
        self.assertEqual(terminal.cursors, [])

    def test_import_is_standalone_and_does_not_load_curses_or_taufw(self):
        code = ("import sys; sys.path.insert(0, sys.argv[1]); import Editor; "
                "assert 'curses' not in sys.modules; "
                "assert not any(n.startswith('TauFW') for n in sys.modules)")
        result = subprocess.run([sys.executable, "-B", "-c", code, str(checkout.SOURCE)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
