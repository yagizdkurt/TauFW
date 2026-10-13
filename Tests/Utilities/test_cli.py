"""Focused terminal behavior checks; no framework imports."""

import io
import unittest

import checkout  # noqa: F401  (must precede TauFW.Utilities imports)
from TauFW.Utilities.CLI import CLI


class TerminalStream(io.StringIO):
    def isatty(self):
        return True


class CLITests(unittest.TestCase):
    def test_constructor_validation(self):
        with self.assertRaises(ValueError):
            CLI(verbosity=-1)
        with self.assertRaises(ValueError):
            CLI(progress_width=0)

    def test_routing_and_verbosity(self):
        output, errors = io.StringIO(), io.StringIO()
        terminal = CLI(output_stream=output, error_stream=errors, prefix="", verbosity=1)
        terminal.print_message("visible", minimum_verbosity=1)
        terminal.print_message("hidden", minimum_verbosity=2)
        terminal.print_header("Section")
        self.assertEqual(output.getvalue(), "visible\n=== Section ===\n")
        self.assertEqual(errors.getvalue(), "")

    def test_warning_and_error_reporting(self):
        output, errors = io.StringIO(), io.StringIO()
        terminal = CLI(output_stream=output, error_stream=errors, prefix="")
        terminal.print_warning("warning")
        terminal.print_error("error")
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(errors.getvalue(), "Warning: warning\nError: error\n")

    def test_prefix_applies_to_first_message_line_and_every_table_line(self):
        output = io.StringIO()
        terminal = CLI(output_stream=output, prefix="> ")
        terminal.print_message("first\nsecond")
        terminal.print_table(["A"], [("x",)])
        self.assertEqual(output.getvalue(), "> first\nsecond\n> A\n> -\n> x\n")

    def test_table_and_rectangular_validation(self):
        output = io.StringIO()
        terminal = CLI(output_stream=output, prefix="")
        terminal.print_table(["Sample", "Count"], iter([("DY", 4), ("Long name", 12)]))
        self.assertEqual(output.getvalue(), "Sample     Count\n---------  -----\nDY         4\nLong name  12\n")
        with self.assertRaises(ValueError):
            terminal.print_table(["Sample", "Count"], [("incomplete",)])
        with self.assertRaises(ValueError):
            terminal.print_table([], [])
        with self.assertRaises(ValueError):
            terminal.print_table(["Sample"], [("two\nlines",)])

    def test_progress_redirected_and_terminal_fallback(self):
        for stream in (io.StringIO(), TerminalStream()):
            with self.subTest(terminal=stream.isatty()):
                terminal = CLI(error_stream=stream, prefix="", progress_width=4)
                terminal.update_progress(1, 2, "long message")
                terminal.update_progress(2, 2, "done")
                terminal.finish_progress()
                text = stream.getvalue()
                self.assertTrue(text.endswith("\n"))
                self.assertEqual(text.count("\n"), 1)
                if stream.isatty():
                    self.assertIn("\r[====] 2/2 (100%) done", text)
                else:
                    self.assertEqual(text, "[====] 2/2 (100%) done\n")
        with self.assertRaises(ValueError):
            CLI().update_progress(1, 0)

    def test_finish_partial_progress_when_redirected(self):
        plain = io.StringIO()
        terminal = CLI(error_stream=plain, prefix="")
        terminal.update_progress(1, 2)
        self.assertEqual(plain.getvalue(), "")
        terminal.finish_progress()
        self.assertIn("1/2 (50%)", plain.getvalue())
        self.assertNotIn("\033", plain.getvalue())
        terminal.finish_progress()
        self.assertEqual(plain.getvalue().count("\n"), 1)

    def test_shorter_progress_line_is_padded_over_longer_one(self):
        errors = TerminalStream()
        terminal = CLI(error_stream=errors, prefix="", progress_width=2)
        terminal.update_progress(1, 3, "long message")
        terminal.update_progress(2, 3)
        long_line = "[  ] 1/3 (33%) long message"
        self.assertEqual(errors.getvalue(), "\r" + long_line + "\r" + "[= ] 2/3 (67%)".ljust(len(long_line)))

    def test_message_interrupting_terminal_progress_starts_new_line_and_reprints_on_finish(self):
        errors = TerminalStream()
        terminal = CLI(output_stream=errors, error_stream=errors, prefix="", progress_width=2)
        terminal.update_progress(1, 3, "a")
        terminal.print_message("message")
        terminal.finish_progress()
        self.assertEqual(errors.getvalue(), "\r[  ] 1/3 (33%) a\nmessage\n[  ] 1/3 (33%) a\n")

    def test_progress_resumes_on_fresh_line_after_interruption(self):
        errors = TerminalStream()
        terminal = CLI(error_stream=errors, prefix="", progress_width=2, use_color=False)
        terminal.update_progress(1, 2)
        terminal.print_warning("careful")
        terminal.update_progress(2, 2)
        self.assertEqual(errors.getvalue(), "\r[= ] 1/2 (50%)\nWarning: careful\n\r[==] 2/2 (100%)\n")

    def test_prompt_interrupting_terminal_progress_starts_new_line(self):
        errors = TerminalStream()
        terminal = CLI(input_stream=io.StringIO("answer\r\n"), error_stream=errors, prefix="", progress_width=2)
        terminal.update_progress(1, 2)
        self.assertEqual(terminal.read_input("Name? "), "answer")
        self.assertEqual(errors.getvalue(), "\r[= ] 1/2 (50%)\nName? ")

    def test_color_detection_and_override(self):
        errors = TerminalStream()
        CLI(error_stream=errors, prefix="").print_warning("colored")
        self.assertIn("\033[33m", errors.getvalue())
        output = TerminalStream()
        CLI(output_stream=output, prefix="").print_header("bold")
        self.assertEqual(output.getvalue(), "\033[1m=== bold ===\033[0m\n")
        plain = io.StringIO()
        CLI(error_stream=plain, prefix="", use_color=True).print_error("forced")
        self.assertEqual(plain.getvalue(), "\033[31mError: forced\033[0m\n")
        disabled = TerminalStream()
        CLI(error_stream=disabled, prefix="", use_color=False).print_error("plain")
        self.assertNotIn("\033", disabled.getvalue())

    def test_confirmation_retries_defaults_and_eof(self):
        errors = io.StringIO()
        terminal = CLI(input_stream=io.StringIO("maybe\n YeS \n\nNO\n"), error_stream=errors)
        self.assertTrue(terminal.confirm("Continue?"))
        self.assertTrue(terminal.confirm("Continue?", default=True))
        self.assertFalse(terminal.confirm("Continue?"))
        self.assertIn("Please answer yes or no", errors.getvalue())
        with self.assertRaises(EOFError):
            terminal.read_input("Answer: ")


# Outputs of the old TauFW.common.tools.LoadingBar, recorded before it moved to
# CLI.loading_bar (2026-10-13): the bar must keep writing exactly these bytes.
LOADING_BAR_GOLDEN = {
    "default": ((5,), {}, [""] * 5,
                ">>> [     ]" + "\b" * 6 + "=====] \n" + "\b" * 3),
    "overcount": ((3,), {}, [""] * 5,
                  ">>> [   ]" + "\b" * 4 + "===] \n" + "\b" * 3),
    "counter": ((3,), {"width": 6, "counter": True}, [""] * 3,
                ">>> [      ]\b\b\b\b\b\b\b      ] 0/3\b\b\b\b\b\b\b\b\b\b\b==    ] 1/3\b\b\b\b\b\b\b\b\b"
                "==  ] 2/3\b\b\b\b\b\b\b==] 3/3\b\b\b\b\b] 3/3 \n\b\b\b\b\b\b\b"),
    "append": ((4,), {"width": 10, "append": " Done!\n"}, [""] * 4,
               ">>> [          ]" + "\b" * 11 + "==========]  Done!\n"),
    "message": ((3,), {"message": "start", "counter": True}, ["one", "two longer", "x"],
                ">>> [   ]\b\b\b\b   ] 0/3\b\b\b\b\b\b\b\b   ] 0/3 start\b\b\b\b\b\b\b\b\b\b\b\b\b\b=  ] 1/3"
                "\b\b\b\b\b\b\b  ] 1/3 one  \b\b\b\b\b\b\b\b\b\b\b\b\b= ] 2/3\b\b\b\b\b\b ] 2/3 two longer"
                "\b\b\b\b\b\b\b\b\b\b\b\b\b\b\b\b\b=] 3/3\b\b\b\b\b] 3/3 x         \b\b\b\b\b\b\b\b\b\b\b\b"
                "\b\b\b\b] 3/3           \n\b\b\b\b\b\b\b\b\b\b\b\b\b\b\b\b\b"),
    "symbol_newline": ((4,), {"symbol": "#", "width": 8}, ["a", "b\n", "", ""],
                       ">>> [        ]\b\b\b\b\b\b\b\b\b##      ] a\b\b\b\b\b\b\b\b\b##    ] b\n"
                       "\b\b\b\b\b\b\b\b####]   \n\b\b\b\b\b"),
    "remove": ((3,), {"width": 6, "prefix": "> ", "counter": True, "remove": True}, ["a", "bb", "c"],
               "> [      ]\b\b\b\b\b\b\b      ] 0/3\b\b\b\b\b\b\b\b\b\b\b==    ] 1/3\b\b\b\b\b\b\b\b\b    ] 1/3 a"
               "\b\b\b\b\b\b\b\b\b\b\b==  ] 2/3\b\b\b\b\b\b\b  ] 2/3 bb\b\b\b\b\b\b\b\b\b\b==] 3/3\b\b\b\b\b"
               "] 3/3 c \b\b\b\b\b\b\b\b\b\b\b\b\b\b\b\b\b" + " " * 18 + "\b" * 18),
}


class LoadingBarTests(unittest.TestCase):
    def test_output_matches_the_old_loading_bar(self):
        for name, (args, options, messages, expected) in LOADING_BAR_GOLDEN.items():
            with self.subTest(name):
                output = io.StringIO()
                bar = CLI(output_stream=output).loading_bar(*args, **options)
                for message in messages:
                    bar.count(message)
                self.assertEqual(output.getvalue(), expected)

    def test_prefix_defaults_to_the_cli_prefix(self):
        output = io.StringIO()
        CLI(output_stream=output, prefix="# ").loading_bar(2)
        self.assertEqual(output.getvalue(), "# [  ]\b\b\b")

    def test_count_steps_and_done(self):
        output = io.StringIO()
        bar = CLI(output_stream=output, prefix="").loading_bar(4, width=4)
        bar.count(steps=3)
        self.assertEqual((bar.tally, bar.position, bar.done), (3, 3, False))
        bar.count(steps=5)   # clipped to what is left
        self.assertEqual((bar.tally, bar.done), (4, True))
        written = output.getvalue()
        bar.count("ignored")
        self.assertEqual(output.getvalue(), written)


if __name__ == "__main__":
    unittest.main()
