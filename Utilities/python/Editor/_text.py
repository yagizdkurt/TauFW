# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Display-cell text helpers shared by the editor and its read-only reference."""
import unicodedata

TAB_SIZE = 2


def _characters(text):
    """Display text safely, expanding tabs without changing the source."""
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


def _tail(text, columns):
    """Keep the filename visible when its parent directories do not fit."""
    if _width(text) <= columns:
        return text
    if columns <= 3:
        return _visible(text, max(0, _width(text) - columns), columns)
    return "..." + _visible(text, _width(text) - columns + 3, columns - 3)


def _wrap(text, columns, prefix="", continuation=""):
    """Wrap prose by display cells; keep list and table continuation indents."""
    columns = max(1, columns)
    line = prefix
    for word in text.split():
        gap = " " if line.strip() and line != prefix and line != continuation else ""
        if _width(line + gap + word) > columns and line.strip() and line not in (prefix, continuation):
            yield line
            line, gap = continuation, ""
        line += gap
        for character, width in _characters(word):
            if _width(line) + width > columns and line.strip():
                yield line
                line = continuation
            line += character
    yield line
