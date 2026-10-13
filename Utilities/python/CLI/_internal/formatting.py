# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Pure terminal formatting for colors, tables and progress lines, without side effects."""

from typing import Iterable, Sequence, TextIO

# ANSI graphic-rendition codes used by the CLI.
BOLD = 1
RED = 31
YELLOW = 33


def is_terminal(stream: TextIO) -> bool:
    """Accept normal streams and lightweight caller-provided streams."""
    return bool(getattr(stream, "isatty", lambda: False)())


def colorize(text: str, color_code: int) -> str:
    """Wrap text in an ANSI code followed by a reset."""
    return f"\033[{color_code}m{text}\033[0m"


def format_table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    """Build a left-aligned table; callers format numerical precision themselves."""
    headings = [str(header) for header in headers]
    if not headings:
        raise ValueError("A table needs at least one column.")
    cells = [headings] + [[str(value) for value in row] for row in rows]
    if any(len(row) != len(headings) for row in cells):
        raise ValueError("Every table row must have the same number of cells as the headers.")
    if any("\n" in value or "\r" in value for row in cells for value in row):
        raise ValueError("Table cells must contain a single line.")
    widths = [max(map(len, column)) for column in zip(*cells)]
    header, *body = ["  ".join(value.ljust(width) for value, width in zip(row, widths)).rstrip()
                     for row in cells]
    separator = "  ".join("-" * width for width in widths)
    return "\n".join([header, separator, *body])


def format_progress(completed: int, total: int, message: str, width: int) -> str:
    """Build a '[===   ] 1/2 (50%) message' line with a bar of the given width."""
    if total <= 0 or completed < 0 or completed > total:
        raise ValueError("Progress requires total > 0 and 0 <= completed <= total.")
    filled = completed * width // total
    bar = "=" * filled + " " * (width - filled)
    suffix = f" {message}" if message else ""
    return f"[{bar}] {completed}/{total} ({completed / total:.0%}){suffix}"
