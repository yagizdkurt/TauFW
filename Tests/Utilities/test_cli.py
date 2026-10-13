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


# Outputs of the old TauFW.common.tools.Table, recorded before it moved to
# CLI.table (2026-10-13): name -> (formats, options, steps, stdout, returned strings).
# Steps: header, header_suffix (suffix=" 'hist'"), row (print_row), row_string (row()),
# save_row / save_header (save=True), print_rows, str.
TABLE_GOLDEN = {
    'two_formats': (('%8s %10s %10s', '%8d %10.2f %10.2f'), {},
        [('header', ('point', 'x', 'weight')), ('row', (1, 0.5, 1.25)), ('row', (2, 1.5, 0.75)), ('row', (3, 2.5, 1.0)), ('row_string', (4, 1.25)), ('row_string', (5, 2.0, 1.0, 'extra'))],
        '>>> \x1b[4m   point          x     weight\x1b[0m\n>>>        1       0.50       1.25\n>>>        2       1.50       0.75\n>>>        3       2.50       1.00\n',
        ['>>>        4       1.25 ', '>>>        5       2.00       1.00 extra']),
    'row_format': (('%9d %10.2f %10.2f',), {},
        [('header', ('ibin', 'content', 'error')), ('row', (0, 12.0, 3.4641)), ('row', (1, 1234.5678, 35.1))],
        '>>> \x1b[4m     ibin    content      error\x1b[0m\n>>>         0      12.00       3.46\n>>>         1    1234.57      35.10\n',
        []),
    'error_columns': (('%9s %10s %9s %11s  ', '%9d %10.2f  +%7.2f  -%9.2f'), {},
        [('header', ('ibin', 'content', 'error up', 'error down')), ('row', (3, 4.0, 0.5, 0.25))],
        '>>> \x1b[4m     ibin    content  error up  error down  \x1b[0m\n>>>         3       4.00  +   0.50  -     0.25\n',
        []),
    'ncols': ((3,), {},
        [('header', ('point', 'x', 'y')), ('row', (1, 1.0, 1.0)), ('row', (1, 4.0)), ('row', (1, 5.0, 25, -1))],
        '>>> \x1b[4m       point           x           y\x1b[0m\n>>>            1         1.0         1.0\n>>>            1         4.0 \n>>>            1         5.0          25 -1\n',
        []),
    'ncols_colwidth': ((3, 7), {},
        [('header', ('a', 'b', 'c')), ('row', ('x', 2, 3.5))],
        '>>> \x1b[4m       a       b       c\x1b[0m\n>>>        x       2     3.5\n',
        []),
    'short_and_extra': (('%6d %8.2f %8.2f ',), {},
        [('header', ('point', 'x', 'y')), ('row', (1, 3.0, 9.0)), ('row', (1, 4.0)), ('row', (1, 5.0, 25, -1))],
        '>>> \x1b[4m point        x        y \x1b[0m\n>>>      1     3.00     9.00 \n>>>      1     4.00 \n>>>      1     5.00    25.00  -1\n',
        []),
    'short_and_extra_signs': (('%8s %8s %8s %6s  ', '%6d %8.2f +%5.2f -%5.2f'), {},
        [('header', ('point', 'y', 'up', 'down')), ('row', (1, 1.0, 0.4, 0.3)), ('row', (1, 16.0, 2.8)), ('row', (1, 25.0)), ('row', (1, 36.0, 4.5, 3.5, -1))],
        '>>> \x1b[4m   point        y       up   down  \x1b[0m\n>>>      1     1.00 + 0.40 - 0.30\n>>>      1    16.00 + 2.80 -\n>>>      1    25.00 +\n>>>      1    36.00 + 4.50 - 3.50 -1\n',
        []),
    'header_count_warning': (('%9d %10.2f %10.2f',), {},
        [('header', ('point', 'x', 'y', 'z')), ('header', ('point', 'x'))],
        '>>> \x1b[1m\x1b[33mWarning! \x1b[0m\x1b[33mTable.header: number of argument (4) != ncols_header (3)\x1b[0m\n>>> \x1b[4m    point          x          y\x1b[0m\n>>> \x1b[1m\x1b[33mWarning! \x1b[0m\x1b[33mTable.header: number of argument (2) != ncols_header (3)\x1b[0m\n',
        ['EXC TypeError: not enough arguments for format string']),
    'unrecognized_arguments': ((1.5,), {},
        [('row', ())],
        '>>> \x1b[1m\x1b[33mWarning! \x1b[0m\x1b[33mTable.__init__: unrecognized arguments for initialization: 1.5\x1b[0m\n>>> \n',
        []),
    'below_minimum_verbosity': (('%9d %10.2f %10.2f',), {'verbosity': 1, 'minimum_verbosity': 3},
        [('header', ('a', 'b', 'c')), ('row', (1, 2.0, 3.0))],
        '',
        []),
    'debug_lines': (('%9d %10.2f %10.2f',), {'verbosity': 3},
        [('header', ('a', 'b', 'c')), ('row', (1, 2.0, 3.0))],
        ">>> headerformat='>>> \\x1b[4m%9s %10s %10s\\x1b[0m', rowformat='>>> %9d %10.2f %10.2f'\n>>> columnformats=['>>> %9d ', '%10.2f ', '%10.2f'], ncols=3\n>>> \x1b[4m        a          b          c\x1b[0m\n>>>         1       2.00       3.00\n",
        []),
    'debug_lines_above_minimum': (('%5d %9.3f +- %7.3f',), {'verbosity': 6, 'minimum_verbosity': 3},
        [('header', ('ibin', 'xval', 'error')), ('row', (1, 2.0, 0.1))],
        ">>> headerformat='>>> \\x1b[4m%5s %9s +- %7s\\x1b[0m', rowformat='>>> %5d %9.3f +- %7.3f'\n>>> columnformats=['>>> %5d ', '%9.3f +- ', '%7.3f'], ncols=3\n>>> \x1b[4m ibin      xval +-   error\x1b[0m\n>>>     1     2.000 +-   0.100\n",
        []),
    'no_prefix_no_underline': (('%9d %10.2f',), {'prefix': '', 'underline': False},
        [('header', ('a', 'b')), ('row', (1, 2.0))],
        '        a          b\n        1       2.00\n',
        []),
    'suffix_save_and_print_rows': (('%9d %10.2f',), {'prefix': '--> '},
        [('header_suffix', ('a', 'b')), ('save_row', (1, 2.0)), ('save_header', ('a', 'b')), ('print_rows', ()), ('str', ())],
        "--> \x1b[4m        a          b\x1b[0m 'hist'\n-->         1       2.00\n--> \x1b[4m        a          b\x1b[0m\n",
        ['-->         1       2.00', '--> \x1b[4m        a          b\x1b[0m', '-->         1       2.00\n--> \x1b[4m        a          b\x1b[0m']),
    'datacard': (('%11.1f %10d  %-20s  %s',), {},
        [('header', ('Events', 'Entries', 'Observable', 'Process     ')), ('row', (1234.56, 789, 'm_vis', 'ZTT'))],
        '>>> \x1b[4m     Events    Entries  Observable            Process     \x1b[0m\n>>>      1234.6        789  m_vis                 ZTT\n',
        []),
    'brackets': (('%5s [%5s, %5s]      %-14s   %-20s', '%5d [%5s, %5s] %8.1f +- %5.1f %8d +%5.1f -%5.1f'), {},
        [('header', ('bin', 'xlow', 'xup', 'exp', 'data')), ('row', (1, 0, 10, 12.3, 1.2, 14, 3.1, 2.9))],
        '>>> \x1b[4m  bin [ xlow,   xup]      exp              data                \x1b[0m\n>>>     1 [    0,    10]     12.3 +-   1.2       14 +  3.1 -  2.9\n',
        []),
    'repr_columns': (('%15.4f  %-10r %-10s   %r',), {},
        [('header', ('Mean', 'Variable', 'Sample', 'Selection     ')), ('row', (1.23456, 'pt_1', 'DY', 'q_1*q_2<0'))],
        ">>> \x1b[4m           Mean  Variable   Sample       Selection     \x1b[0m\n>>>          1.2346  'pt_1'     DY           'q_1*q_2<0'\n",
        []),
    'plot_ratio': (('%4s %9s %11s  %4s %9s %11s  %4s %8s %-14s', '%4d %9.5g %11.2f  %4d %9.5g %11.2f  %4d %8.2f +%5.2f  -%5.2f'), {},
        [('header', ('inum', 'xval', 'yval', 'ibin', 'xval', 'yden', 'irat', 'ratio', 'error')), ('row', (1, 0.5, 10.0, 2, 0.5, 9.0, 3, 1.11, 0.1, 0.2))],
        '>>> \x1b[4minum      xval        yval  ibin      xval        yden  irat    ratio error         \x1b[0m\n>>>    1       0.5       10.00     2       0.5        9.00     3     1.11 + 0.10  - 0.20\n',
        []),
    'zero_pad_and_percent': (('%05d %6.1f%%',), {},
        [('header', ('n', 'pct')), ('row', (7, 12.5))],
        '>>> \x1b[4m    n    pct%\x1b[0m\n>>> 00007   12.5%\n',
        []),
    'histset': (('%13.2f %13d %13.3f   %r',), {},
        [('header', ('Integral', 'Entries', 'Ave. weight', 'Hist name    ')), ('row', (10.0, 5, 2.0, 'h1')), ('row', (0, 0, -1, 'total exp.'))],
        ">>> \x1b[4m     Integral       Entries   Ave. weight   Hist name    \x1b[0m\n>>>         10.00             5         2.000   'h1'\n>>>          0.00             0        -1.000   'total exp.'\n",
        []),
    'printhist': (('%6s %9.6g %9.6g %11.2f %9.2f',), {'verbosity': 0},
        [('header_suffix', ('ibin', 'xmin', 'xmax', 'content', 'error')), ('row', (1, -2.0, -1.714, 3.0, 1.732))],
        ">>> \x1b[4m  ibin      xmin      xmax     content     error\x1b[0m 'hist'\n>>>      1        -2    -1.714        3.00      1.73\n",
        []),
}


class TableTests(unittest.TestCase):
    def run_steps(self, table, steps):
        returned = []
        for kind, values in steps:
            try:
                if kind == "header":
                    table.print_header(*values)
                elif kind == "header_suffix":
                    table.print_header(*values, suffix=" 'hist'")
                elif kind == "row":
                    table.print_row(*values)
                elif kind == "row_string":
                    returned.append(table.row(*values))
                elif kind == "save_row":
                    returned.append(table.row(*values, save=True))
                elif kind == "save_header":
                    returned.append(table.header(*values, save=True))
                elif kind == "print_rows":
                    table.print_rows()
                elif kind == "str":
                    returned.append(str(table))
            except TypeError as error:   # too few header titles, as before
                returned.append("EXC TypeError: %s" % (error))
                break
        return returned

    def test_output_matches_the_old_table(self):
        for name, (formats, options, steps, stdout, returned) in TABLE_GOLDEN.items():
            with self.subTest(name):
                options = dict(options)
                output = io.StringIO()
                cli = CLI(output_stream=output, verbosity=options.pop("verbosity", 0),
                          prefix=options.pop("prefix", ">>> "))
                table = cli.table(*formats, **options)
                self.assertEqual(self.run_steps(table, steps), returned)
                self.assertEqual(output.getvalue(), stdout)

    def test_header_is_underlined_even_when_redirected(self):
        output = io.StringIO()
        CLI(output_stream=output, use_color=False).table("%3d").print_header("n")
        self.assertEqual(output.getvalue(), ">>> \033[4m  n\033[0m\n")

    def test_construction_is_silent(self):
        output = io.StringIO()
        CLI(output_stream=output, verbosity=2).table("%5d %9.3f", minimum_verbosity=0)
        self.assertEqual(output.getvalue(), "")

if __name__ == "__main__":
    unittest.main()
