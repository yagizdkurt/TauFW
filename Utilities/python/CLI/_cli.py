#Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""The single public entry point for terminal input and output."""

import sys
from typing import Iterable, Optional, Sequence, TextIO

from ._internal.formatting import BOLD, RED, YELLOW, colorize, format_progress, format_table, is_terminal
from ._internal.loading_bar import LoadingBar
from ._internal.table import Table

_YES_NO_ANSWERS = {"y": True, "yes": True, "n": False, "no": False}


class CLI:
    """Report to terminal streams without owning files or workflow decisions."""

    # =========================================================================
    # ================================ SETUP ==================================

    def __init__(
        self,
        input_stream: Optional[TextIO] = None,
        output_stream: Optional[TextIO] = None,
        error_stream: Optional[TextIO] = None,
        verbosity: int = 0,
        prefix: str = ">>> ",
        use_color: Optional[bool] = None,
        progress_width: int = 30,
    ) -> None:
        """None selects the current standard stream; use_color=None detects TTYs."""
        if verbosity < 0:
            raise ValueError("Verbosity must be nonnegative.")
        if progress_width <= 0:
            raise ValueError("progress_width must be positive.")
        self._input_stream = sys.stdin if input_stream is None else input_stream
        self._output_stream = sys.stdout if output_stream is None else output_stream
        self._error_stream = sys.stderr if error_stream is None else error_stream
        self._verbosity = verbosity
        self._prefix = prefix
        self._use_color = use_color
        self._progress_width = progress_width
        # Latest line of the active progress task; None when no task is active.
        self._progress_line: Optional[str] = None
        # Length of the bar currently drawn on the terminal; 0 when nothing is drawn.
        self._rendered_progress_width = 0

    # =========================================================================
    # =========================== INTERNAL HELPERS ============================

    @property
    def _progress_visible(self) -> bool:
        """True while a progress bar occupies the current terminal line."""
        return self._rendered_progress_width > 0

    def _end_progress_line(self) -> None:
        """Move off a drawn progress bar so the next write starts on a fresh line."""
        if self._progress_visible:
            self._error_stream.write("\n")
            self._error_stream.flush()
            self._rendered_progress_width = 0

    def _color_enabled(self, stream: TextIO) -> bool:
        return is_terminal(stream) if self._use_color is None else self._use_color

    def _write_lines(self, *lines: str, stream: TextIO, color_code: Optional[int] = None) -> None:
        """Write each line with the prefix, optionally colored, after any progress bar."""
        self._end_progress_line()
        text = "\n".join(self._prefix + line for line in lines)
        if color_code is not None and self._color_enabled(stream):
            text = colorize(text, color_code)
        stream.write(text + "\n")
        stream.flush()

    # =========================================================================
    # =============================== MESSAGES ================================

    def print_message(self, message: str, minimum_verbosity: int = 0) -> None:
        """Print only when the configured verbosity reaches the requested level."""
        if self._verbosity >= minimum_verbosity:
            self._write_lines(message, stream=self._output_stream)

    def print_warning(self, message: str) -> None:
        """Report a warning to stderr regardless of verbosity."""
        self._write_lines("Warning: " + message, stream=self._error_stream, color_code=YELLOW)

    def print_error(self, message: str) -> None:
        """Report an error to stderr without raising or terminating the application."""
        self._write_lines("Error: " + message, stream=self._error_stream, color_code=RED)

    def print_header(self, title: str) -> None:
        """Print a bold section title to stdout regardless of verbosity."""
        self._write_lines("=== " + title + " ===", stream=self._output_stream, color_code=BOLD)

    # =========================================================================
    # ================================ TABLES =================================

    def print_table(self, headers: Sequence[str], rows: Iterable[Sequence[object]]) -> None:
        """Print a rectangular table; rows may be supplied as an iterator."""
        table = format_table(headers, rows)
        self._write_lines(*table.splitlines(), stream=self._output_stream)

    def table(self, *formats, minimum_verbosity: int = 0, underline: bool = True) -> Table:
        """A %-format table on stdout, printed row by row: table(row_format) or
        table(header_format, row_format). Its lines start with the CLI prefix,
        and print_header/print_row print only when the CLI verbosity reaches
        minimum_verbosity (see Table)."""
        return Table(self._output_stream, *formats, verbosity=self._verbosity,
                     minimum_verbosity=minimum_verbosity, prefix=self._prefix, underline=underline)

    # =========================================================================
    # =============================== PROGRESS ================================

    def update_progress(self, completed: int, total: int, message: str = "") -> None:
        """Update one progress task; completing it automatically finishes its line."""
        self._progress_line = self._prefix + format_progress(completed, total, message, self._progress_width)
        if is_terminal(self._error_stream):
            # Pad with spaces so a shorter line fully overwrites the previous one.
            padded_line = self._progress_line.ljust(self._rendered_progress_width)
            self._error_stream.write("\r" + padded_line)
            self._error_stream.flush()
            self._rendered_progress_width = len(self._progress_line)
        if completed == total:
            self.finish_progress()

    def finish_progress(self) -> None:
        """Finish the active task, writing its last line if no bar is currently drawn.

        No bar is drawn when stderr is redirected, or when a message or prompt has
        interrupted the bar since its last update; the final state is then reprinted.
        """
        if self._progress_line is None:
            return
        if self._progress_visible:
            self._end_progress_line()
        else:
            self._error_stream.write(self._progress_line + "\n")
            self._error_stream.flush()
        self._progress_line = None

    def loading_bar(self, steps: int, **options) -> LoadingBar:
        """Draw an empty in-place loading bar on stdout and return it; call
        its count(message) once per step. options: width, counter, remove,
        symbol, prefix (default: the CLI prefix), append, message (see
        LoadingBar)."""
        options.setdefault("prefix", self._prefix)
        return LoadingBar(self._output_stream, steps, **options)

    # =========================================================================
    # ================================ INPUT ==================================

    def read_input(self, prompt: str) -> str:
        """Display the prompt on stderr and read a line; propagate EOF as EOFError."""
        self._end_progress_line()
        self._error_stream.write(self._prefix + prompt)
        self._error_stream.flush()
        answer = self._input_stream.readline()
        if answer == "":
            raise EOFError("Terminal input ended before an answer was received.")
        return answer.rstrip("\r\n")

    def confirm(self, prompt: str, default: bool = False) -> bool:
        """Read yes/no, retry invalid input, and use default for an empty answer."""
        choices = "[Y/n]" if default else "[y/N]"
        while True:
            answer = self.read_input(f"{prompt} {choices} ").strip().lower()
            if not answer:
                return default
            if answer in _YES_NO_ANSWERS:
                return _YES_NO_ANSWERS[answer]
            self.print_warning("Please answer yes or no.")
