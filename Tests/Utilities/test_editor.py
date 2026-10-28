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
from TauFW.Utilities.Editor._reference import Reference
from TauFW.Utilities.Editor._screen import _visible, _width
from TauFW.Utilities.Editor._text import _wrap


class TerminalError(Exception):
    pass


class Terminal:
    """A parent screen plus separate windows, with scripted Unicode keys and resizes."""
    error = TerminalError
    A_BOLD, A_REVERSE = 1, 2
    (KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_HOME, KEY_END, KEY_PPAGE,
     KEY_NPAGE, KEY_BACKSPACE, KEY_DC, KEY_ENTER, KEY_F2, KEY_F10, KEY_RESIZE) = range(1000, 1014)
    KEY_F4, KEY_F5 = 1020, 1021

    def __init__(self, keys, dimensions=(16, 64)):
        self.keys = iter(keys)
        self.dimensions = dimensions
        self.frames, self.cursors, self.attributes, self.positions = [], [], [], []
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
        self.position = (0, 0)

    def keypad(self, enabled):
        pass

    def timeout(self, milliseconds):
        pass

    def erase(self):
        self.lines = [" " * self.width for _ in range(self.height)]
        self.attributes = []

    def addstr(self, row, column, text, attribute=0):
        if not 0 <= row < self.height or column + _width(text) >= self.width:
            raise TerminalError("Draw outside window")
        line = self.lines[row]
        self.lines[row] = line[:column] + text + line[column + len(text):]
        self.attributes.append((row, column, text, attribute))

    def move(self, row, column):
        if not (0 <= row < self.height and 0 <= column < self.width):
            raise TerminalError("Cursor outside window")
        self.position = row, column

    def refresh(self):
        self.terminal.frames.append("\n".join(self.lines))
        self.terminal.attributes.append(list(self.attributes))
        self.terminal.positions.append(self.position)

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

    def open(self, keys, validate=None, dimensions=(16, 64), appearance=None, reference=None):
        terminal = Terminal(keys, dimensions)
        result = edit_file(terminal, self.path, validate=validate, appearance=appearance,
                           reference=reference, curses_module=terminal)
        self.assertIsNone(result.error)
        self.assertEqual((terminal.cursors[0], terminal.cursors[-1]), (1, 0))
        if reference is None:
            self.assertEqual(terminal.cursors, [1, 0])
        self.assertEqual(terminal.touched, 1)
        return result, terminal

    def reference(self, text=None, name="README.md"):
        path = self.root / name
        path.write_text(text if text is not None else "# Manual\n\n" + "\n\n".join(
            "Help paragraph %d." % i for i in range(50)), encoding="utf-8")
        return path

    def test_panes_scroll_independently_and_reference_keys_cannot_edit_either_file(self):
        self.path.write_text("\n".join("value_%d: text" % i for i in range(50)), encoding="utf-8")
        reference = self.reference()
        original = reference.read_bytes()
        keys = [Terminal.KEY_NPAGE, Terminal.KEY_F5, Terminal.KEY_NPAGE, "X", "\t", "\n",
                Terminal.KEY_BACKSPACE, Terminal.KEY_DC, Terminal.KEY_F5, Terminal.KEY_END, "!",
                Terminal.KEY_F2, "\x1b"]
        result, terminal = self.open(keys, dimensions=(24, 120), reference=reference)
        self.assertTrue(result.saved)
        self.assertEqual(self.path.read_text().splitlines()[16], "value_16: text!")
        self.assertEqual(reference.read_bytes(), original)
        self.assertIn("Help paragraph 0.", terminal.frames[0])
        self.assertIn("Ln 17, Col 1", terminal.frames[3])
        self.assertIn("Lines 17-32/", terminal.frames[3])
        self.assertEqual(terminal.frames[3:8], [terminal.frames[3]] * 5)
        self.assertIn("Help paragraph 8.", terminal.frames[9])
        self.assertEqual(terminal.cursors, [1, 0, 1, 0])

    def test_narrow_terminal_opens_and_closes_docs_without_losing_either_position(self):
        reference = self.reference()
        result, terminal = self.open([Terminal.KEY_F4, Terminal.KEY_NPAGE, Terminal.KEY_F4,
                                      "X", Terminal.KEY_F5, "\x1b", Terminal.KEY_F2],
                                     dimensions=(24, 80), reference=reference)
        self.assertTrue(result.saved)
        self.assertNotIn("Help paragraph 0.", terminal.frames[0])
        self.assertIn("Help paragraph 0.", terminal.frames[1])
        self.assertNotIn("value: old", terminal.frames[1])
        self.assertIn("value: old", terminal.frames[3])
        self.assertIn("Help paragraph 8.", terminal.frames[5])
        self.assertIn("Unsaved changes", terminal.frames[6])
        self.assertTrue(self.path.read_text().startswith("X# keep"))

    def test_resize_preserves_reference_source_position_and_yaml_cursor(self):
        reference = self.reference("\n".join("line %d: " % i + "x" * 140 for i in range(80)), "example.txt")
        self.path.write_text("\n".join("yaml_%d: value" % i for i in range(60)), encoding="utf-8")
        terminal = Terminal([], dimensions=(24, 120))

        def resize(dimensions):
            terminal.dimensions = dimensions
            return Terminal.KEY_RESIZE

        terminal.keys = iter([Terminal.KEY_NPAGE, Terminal.KEY_F5, Terminal.KEY_NPAGE, Terminal.KEY_RIGHT,
                              lambda: resize((24, 60)), lambda: resize((24, 160)),
                              Terminal.KEY_F5, Terminal.KEY_F4, Terminal.KEY_F4, Terminal.KEY_F5, "\x1b"])
        result = edit_file(terminal, self.path, reference=reference, curses_module=terminal)
        self.assertIsNone(result.error)
        for frame in terminal.frames[4:7]:
            self.assertIn("Lines 17-32/80 | Col 5", frame)
        self.assertNotIn("yaml_16", terminal.frames[5])
        for frame in (terminal.frames[6], terminal.frames[7], terminal.frames[8], terminal.frames[10]):
            self.assertIn("Ln 17, Col 1", frame)
        self.assertFalse(result.saved)

    def test_reference_layout_and_controls_fit_small_and_split_boundary_sizes(self):
        reference = self.reference("# Heading\n\n```yaml\n  key: " + "x" * 150 + "\n```\n")
        for size in ((10, 40), (24, 109), (24, 110), (24, 160), (5, 20)):
            with self.subTest(size=size):
                result, _ = self.open([Terminal.KEY_F5, Terminal.KEY_NPAGE, Terminal.KEY_RIGHT,
                                       Terminal.KEY_HOME, Terminal.KEY_END, Terminal.KEY_F4,
                                       Terminal.KEY_F4, Terminal.KEY_F5, Terminal.KEY_F2, "\x1b"],
                                      dimensions=size, reference=reference)
                self.assertFalse(result.saved)

    def test_unreadable_reference_does_not_prevent_editing_or_saving(self):
        invalid = self.reference(name="invalid.md")
        invalid.write_bytes(b"\xff\xfe")
        for reference in (invalid, self.root / "missing.md"):
            with self.subTest(reference=reference):
                result, terminal = self.open([Terminal.KEY_F5, Terminal.KEY_F5, "X", Terminal.KEY_F2, "\x1b"],
                                             dimensions=(24, 120), reference=reference)
                self.assertTrue(result.saved)
                self.assertIn("Reference unavailable", terminal.frames[0])

    def test_save_error_owns_keys_until_dismissed_even_with_reference_focus(self):
        reference = self.reference()
        keys = ["X", Terminal.KEY_F5, Terminal.KEY_F2, Terminal.KEY_F4, Terminal.KEY_F5,
                Terminal.KEY_NPAGE, "\n", Terminal.KEY_F5, Terminal.KEY_BACKSPACE, "\x1b"]
        result, terminal = self.open(keys, validate=lambda path: "Invalid setting", dimensions=(24, 120),
                                     reference=reference)
        self.assertFalse(result.saved)
        self.assertTrue(all("Cannot save" in frame for frame in terminal.frames[3:7]))
        self.assertIn("Help paragraph 0.", terminal.frames[7])
        self.assertIn("value: old", self.path.read_text())

    def test_markdown_readme_reflows_prose_and_tables_but_preserves_code(self):
        reference = Reference(self.reference("# Settings\n\nA **short** paragraph\ncontinued with a [link](other.md).\n\n"
                                             "```yaml\n# keep comment\n  path: " + "x" * 80 + "\n```\n\n"
                                             "| Setting | Meaning |\n| --- | --- |\n| `runs.root` | Output folder |\n"))
        reference.layout(32, 5)
        text = "\n".join(row[1] for row in reference.rows)
        self.assertIn("Settings\n", text)
        self.assertIn("A short paragraph continued with", text)
        self.assertIn("link (other.md)", text)
        self.assertIn("# keep comment\n  path: " + "x" * 80, text)
        self.assertIn("Setting: runs.root\nMeaning: Output folder", text)
        self.assertNotIn("```", text)
        reference.top = next(index for index, row in enumerate(reference.rows) if row[1] == "# keep comment")
        source = reference.rows[reference.top][0]
        reference.layout(45, 5)
        self.assertEqual(reference.rows[reference.top][0], source)
        reference.move(columns=999)
        self.assertEqual(reference.left, reference.max_left)
        self.assertEqual("\n".join(_wrap("界界 e\u0301 Çağrı " + "a" * 12, 8)).replace("\n", "").replace(" ", ""),
                         "界界e\u0301Çağrı" + "a" * 12)
        self.assertTrue(all(_width(line) <= 8 for line in _wrap("界界 e\u0301 Çağrı " + "a" * 12, 8)))
        paragraph = Reference(self.reference(" ".join("word%03d" % i for i in range(150))))
        paragraph.layout(32, 5)
        paragraph.move(rows=12)
        first_word = paragraph.rows[paragraph.top][1].split()[0]
        paragraph.layout(48, 5)
        self.assertIn(first_word, " ".join(row[1] for row in paragraph.rows[paragraph.top:paragraph.top + 2]))

    def test_actual_user_config_guide_and_empty_file_are_readable(self):
        path = checkout.SOURCE.parents[1] / "Docs/Guide/1-GettingStarted/UserConfig.md"
        reference = Reference(path)
        reference.layout(40, 16)
        self.assertFalse(reference.error)
        text = "\n".join(row[1] for row in reference.rows)
        self.assertIn("taufw_user:", text)
        self.assertIn("Setting: runs.run_root", text)
        empty = Reference(self.reference(""))
        empty.layout(30, 5)
        empty.move(rows=10, columns=10)
        self.assertEqual((empty.top, empty.left, len(empty.rows)), (0, 0, 1))

    def appearance(self):
        """Caller-owned branding and attributes; Editor needs no import from that caller."""
        return dict(banner=("+-------+", "| TauFW |", "+-V0.0--+"),
                    banner_spans=((1, 2, "TauFW", "brand"), (2, 2, "V0.0", "version")),
                    large_banner=("LARGE BANNER",) + ("." * 78,) * 23,
                    styles=dict(accent=16, brand=32, version=64, active=128, muted=256, warning=512,
                                good=1024, error=2048))

    def test_frame_banner_path_and_cursor_share_the_same_content_rectangle(self):
        directory = self.root / ("parent_directory_" * 4)
        directory.mkdir()
        self.path = directory / "settings.yaml"
        self.path.write_text("\n".join("value_%d: text" % i for i in range(40)), encoding="utf-8")
        _, terminal = self.open([Terminal.KEY_END, "\x1b"], dimensions=(24, 80), appearance=self.appearance())
        lines = terminal.frames[0].splitlines()
        self.assertIn("| TauFW |", lines[1])
        self.assertIn("settings.yaml", lines[2])
        self.assertIn("...", lines[2])
        self.assertEqual((lines[3][1], lines[3][78], lines[20][1], lines[20][78]), ("+",) * 4)
        self.assertIn("Lines 1-16/40", lines[21])
        self.assertEqual(terminal.positions[0], (4, 9))
        self.assertEqual(terminal.positions[1], (4, 22))
        self.assertIn((1, 3, "TauFW", 32), terminal.attributes[0])
        self.assertTrue(any(text.startswith("> 1 | ") and attribute == 128
                            for _, _, text, attribute in terminal.attributes[0]))

    def test_large_banner_yields_to_badge_on_resize_without_changing_text_or_cursor(self):
        original = "\n".join("value_%d: text" % i for i in range(40))
        self.path.write_text(original, encoding="utf-8")
        terminal = Terminal([], dimensions=(48, 90))

        def resize(dimensions):
            terminal.dimensions = dimensions
            return Terminal.KEY_RESIZE

        terminal.keys = iter([Terminal.KEY_NPAGE, lambda: resize((24, 80)),
                              lambda: resize((48, 90)), "\x1b"])
        result = edit_file(terminal, self.path, appearance=self.appearance(), curses_module=terminal)
        self.assertIsNone(result.error)
        self.assertIn("LARGE BANNER", terminal.frames[0])
        self.assertIn("| TauFW |", terminal.frames[2])
        self.assertNotIn("LARGE BANNER", terminal.frames[2])
        self.assertIn("LARGE BANNER", terminal.frames[3])
        for frame in terminal.frames[1:]:
            self.assertIn("Ln 17, Col 1", frame)
        self.assertEqual(terminal.positions[2], (19, 9))
        self.assertEqual(terminal.positions[3], (43, 9))
        self.assertEqual(self.path.read_text(), original)

    def test_dialogs_overlay_the_document_and_keep_the_banner_visible(self):
        self.path.write_text("\n".join("value_%d: text" % i for i in range(40)), encoding="utf-8")
        for validation in (None, lambda path: ["Problem %d" % i for i in range(40)]):
            with self.subTest(validation=validation):
                keys = ["X", "\x1b", "d"] if validation is None else [
                    "X", Terminal.KEY_F2, Terminal.KEY_NPAGE, "\n", "\x1b", "d"]
                result, terminal = self.open(keys, validation, (24, 80), self.appearance())
                self.assertFalse(result.saved)
                for frame in terminal.frames:
                    self.assertIn("| TauFW |", frame)
                    self.assertIn("settings.yaml", frame)
                    self.assertIn("F2 Save | Esc Back", frame)
                if validation is None:
                    self.assertIn("Unsaved changes", terminal.frames[-1])
                    self.assertIn("value_0: text", terminal.frames[-1])
                else:
                    self.assertIn("Cannot save", terminal.frames[2])
                    self.assertIn("Problem 13", terminal.frames[3])
                    self.assertTrue(any("Cannot save" in text and attribute == 2048
                                        for _, _, text, attribute in terminal.attributes[2]))

    def test_small_monochrome_dialog_keeps_essential_controls_and_modified_state(self):
        appearance = self.appearance()
        appearance["styles"] = {role: 0 for role in appearance["styles"]}
        original = self.path.read_bytes()
        result, terminal = self.open(["X", "\x1b", "d"], dimensions=(10, 40), appearance=appearance)
        self.assertFalse(result.saved)
        self.assertIn("Modified", terminal.frames[-1])
        self.assertIn("Unsaved changes", terminal.frames[-1])
        self.assertIn("F2 Save | D Discard | Esc Edit", terminal.frames[-1])
        self.assertIn("| TauFW |", terminal.frames[-1])
        self.assertEqual(self.path.read_bytes(), original)

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
