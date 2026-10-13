# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""A printf-style table printed one row at a time, for debug and yield tables.

Moved from TauFW.common.tools.Table (2026). Same logic: the characters
written are byte for byte those of the old class, so logs and BBB baselines
do not change.

    CLI.table(row_format, ...) ─▶ Table: column formats split from row_format,
                                         header format derived from it
          │
          ├─ print_header(*titles)  ─▶ ">>> " + underlined titles
          └─ print_row(*values)     ─▶ ">>> " + row_format % values
                                       (fewer values: first columns only;
                                        more values: appended with spaces)

Rows print only when the CLI verbosity reaches `minimum_verbosity`.
"""
import re
from typing import List, TextIO

__all__ = ["Table"]

# One %-conversion of a row format; group 2 is its width, e.g. "-10" in "%-10.3f".
_CONVERSION = re.compile(r"(%(-?\d*)\.?\d*[sfgdir])")


class Table:
    """Prints a header and rows with %-formats.

    Pipelines:    print_header(*titles, suffix="") -> header line, if verbose enough
                  print_row(*values)               -> one row, if verbose enough
                  print_rows()                     -> every line saved with save=True
    Strings:      header(*titles, suffix="", save=False), row(*values, save=False)
    Construction: Table(stream, *formats, verbosity, minimum_verbosity, prefix,
                        underline); formats: see _parse_formats
    """

    # =========================================================================
    # =============================== PIPELINES ===============================

    def print_header(self, *titles, suffix: str = "") -> None:
        """Print the header line when the verbosity reaches minimum_verbosity."""
        if self.verbosity >= self.minimum_verbosity:
            self._print(self.header(*titles, suffix=suffix))

    def print_row(self, *values) -> None:
        """Print one row when the verbosity reaches minimum_verbosity."""
        if self.verbosity >= self.minimum_verbosity:
            self._print(self.row(*values))

    def print_rows(self) -> None:
        """Print every line saved with save=True, whatever the verbosity."""
        for line in self.rows:
            self._print(line)

    # =========================================================================
    # ================================ STRINGS ================================

    def header(self, *titles, suffix: str = "", save: bool = False) -> str:
        """The header line: titles (strings) in the header format, then suffix.
        A wrong number of titles prints a warning; too few then raise
        TypeError from the % formatting."""
        if len(titles) != self.ncols_header:
            self._warn("Table.header: number of argument (%d) != ncols_header (%d)" % (
                len(titles), self.ncols_header))
        line = self.headerformat % (titles[:self.ncols_header]) + suffix
        if save:
            self.rows.append(line)
        return line

    def row(self, *values, save: bool = False) -> str:
        """One row in the row format. Fewer values than columns use only the
        first columns' formats; extra values are appended, space separated."""
        line_format = self.rowformat
        if len(values) < self.ncols:
            line_format = "".join(self.columnformats[:len(values)])
        line = line_format % (values[:self.ncols])
        if len(values) > self.ncols:
            line += " " + " ".join(str(value) for value in values[self.ncols:])
        if save:
            self.rows.append(line)
        return line

    def __str__(self) -> str:
        return "\n".join(self.rows)

    # =========================================================================
    # ================================ HELPERS ================================

    def _print(self, line: str) -> None:
        self._stream.write(line + "\n")

    def _split_columns(self) -> List[str]:
        """Cut the row format (prefix included) into one piece per column:
        each piece runs from its conversion up to the next one."""
        matches = _CONVERSION.findall(self.rowformat)
        assert len(matches) == self.ncols, (
            "Number of recognized columns in the row pattern (%d) is not the same as the set "
            "number of columns (%d)" % (len(matches), self.ncols))
        columns = []
        end = len(self.rowformat)
        for index, match in reversed(list(enumerate(matches))):
            start = self.rowformat[:end].rfind(match[0]) if index > 0 else 0
            columns.insert(0, self.rowformat[start:end])
            end = start
        return columns

    # =========================================================================
    # ======================== LEGACY, CLEAN UP LATER =========================
    # Kept from the old Table so every line stays byte for byte the same:
    # - four constructor forms told apart by argument types (only the two
    #   format-string forms are used in the repository);
    # - the header is always underlined with raw ANSI codes, even when the
    #   output is redirected to a file (CLI checks is_terminal elsewhere);
    # - warnings use the old LOG.warning text and colors on stdout, with a
    #   fixed ">>> " (the old global LOG's prefix, not the table's);
    # - the two debug lines at verbosity >= minimum_verbosity + 3.
    # Modernizing any of these changes logs, so do it in its own commit,
    # with a BBB re-lock (common.formatting records the table output).

    def _parse_formats(self, formats: tuple) -> None:
        """Table(row_format), Table(header_format, row_format), Table(ncols)
        or Table(ncols, colwidth); integer forms make ncols '%{colwidth}s'
        columns. A missing header format is the row format with each
        conversion turned into '%{width}s'."""
        if len(formats) == 1 and isinstance(formats[0], str):
            self.rowformat = formats[0]
        elif len(formats) == 2 and isinstance(formats[0], str) and isinstance(formats[1], str):
            self.headerformat = formats[0]
            self.rowformat = formats[1]
        elif len(formats) == 1 and isinstance(formats[0], int):
            self.ncols = formats[0]
        elif len(formats) == 2 and isinstance(formats[0], int) and isinstance(formats[1], int):
            self.ncols = formats[0]
            self.colwidth = formats[1]
        else:
            self._warn("Table.__init__: unrecognized arguments for initialization: %r" % (formats))
        if not self.rowformat:
            self.rowformat = (" %%%ds" % self.colwidth) * self.ncols
        if not self.headerformat:
            self.headerformat = _CONVERSION.sub(r"%\2s", self.rowformat).replace('%0', '%')
        if not self.ncols:
            self.ncols = self.rowformat.replace('%%', '').count('%')
            self.ncols_header = self.headerformat.replace('%%', '').count('%')
        else:
            self.ncols_header = self.ncols

    def _decorate(self, underline: bool) -> None:
        """Underline the header with ANSI codes; prefix header and row formats."""
        if underline:
            self.headerformat = "\033[4m%s\033[0m" % (self.headerformat)
        if self.prefix:
            self.headerformat = self.prefix + self.headerformat
            self.rowformat = self.prefix + self.rowformat

    def _warn(self, message: str) -> None:
        """The old LOG.warning line: bold yellow 'Warning! ', yellow message."""
        self._print(">>> \033[1m\033[33mWarning! \033[0m\033[33m%s\033[0m" % (message))

    def _print_formats(self) -> None:
        self._print(">>> headerformat=%r, rowformat=%r" % (self.headerformat, self.rowformat))
        self._print(">>> columnformats=%s, ncols=%r" % (self.columnformats, self.ncols))

    # =========================================================================
    # ============================= CONSTRUCTION ==============================

    def __init__(self, stream: TextIO, *formats, verbosity: int = 0, minimum_verbosity: int = 0,
                 prefix: str = ">>> ", underline: bool = True) -> None:
        """stream: where lines are written; formats: see _parse_formats.
        Prints nothing unless verbosity >= minimum_verbosity + 3 (debug)."""
        self._stream = stream
        self.rowformat = ""
        self.headerformat = ""
        self.ncols = 0
        self.ncols_header = 0
        self.colwidth = 11
        self.prefix = prefix
        self.verbosity = verbosity
        self.minimum_verbosity = minimum_verbosity
        self._parse_formats(formats)
        self._decorate(underline)
        self.rows = []   # lines saved with save=True
        self.columnformats = self._split_columns()
        if self.verbosity >= self.minimum_verbosity + 3:
            self._print_formats()

    def __repr__(self) -> str:
        return "<Table %r: %d columns>" % (self.rowformat, self.ncols)
