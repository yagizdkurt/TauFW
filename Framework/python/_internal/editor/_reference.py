# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Read-only file viewport, with a small terminal renderer for Markdown READMEs.

No curses or application imports. Markdown supports headings, prose, lists,
links, fenced code, pipe tables and GitHub alerts (> [!WARNING] ..., shown in
the colour of ALERTS); other constructs remain readable source.
Code and plain-text files retain their indentation and scroll horizontally.
"""
from pathlib import Path
import re

from ._text import _width, _wrap

ALERTS = {"CAUTION": "error", "WARNING": "warning", "IMPORTANT": "warning", "TIP": "good", "NOTE": "muted"}


def _inline(text):
    text = re.sub(r"!?\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return re.sub(r"\*\*([^*]+)\*\*", r"\1", text)


def _cells(line):
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _markdown(text, columns):
    lines = text.splitlines()
    index, fence, comment = 0, "", False
    while index < len(lines):
        line, source = lines[index], index
        index += 1
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if fence:
            if (marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence)
                    and not line[marker.end():].strip()):
                fence = ""
            else:
                yield source, line, ""
            continue
        if marker:
            fence = marker[1]
            continue
        if comment or line.lstrip().startswith("<!--"):
            comment = "-->" not in line
            continue
        if not line.strip():
            yield source, "", ""
            continue
        alert = re.match(r"^\s{0,3}>\s*\[!(%s)\]\s*$" % "|".join(ALERTS), line)
        if alert:
            body = []
            while index < len(lines) and re.match(r"^\s{0,3}>", lines[index]):
                body.append(re.sub(r"^\s{0,3}>\s?", "", lines[index]))
                index += 1
            for inner, row, _ in _markdown("\n".join(body), columns):
                yield source + 1 + inner, row, ALERTS[alert[1]] if row else ""
            continue
        heading =re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if heading:
            for row in _wrap(_inline(heading[1]), columns):
                yield source, row, "active"
            continue
        if "|" in line and index < len(lines) and all(
                re.fullmatch(r":?-{3,}:?", cell) for cell in _cells(lines[index])):
            headers = _cells(line)
            index += 1
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                source = index
                for column, cell in enumerate(_cells(lines[index])):
                    label = headers[column] if column < len(headers) else str(column + 1)
                    for row in _wrap(_inline(label + ": " + cell), columns, continuation="  "):
                        yield source, row, ""
                yield source, "", ""
                index += 1
            continue
        bullet = re.match(r"^(\s*(?:[-+*]|\d+[.)])\s+)(.*)", line)
        prefix = bullet[1] if bullet else ""
        paragraph = bullet[2] if bullet else line.strip()
        while index < len(lines) and lines[index].strip() and not re.match(
                r"^\s*(?:#|```|~~~|<!--|[-+*]\s|\d+[.)]\s|\|)", lines[index]):
            paragraph += " " + lines[index].strip()
            index += 1
        for row in _wrap(_inline(paragraph), columns, prefix, " " * len(prefix)):
            yield source, row, ""


class Reference:
    """Load once, reflow on width changes, and keep a position independent of editing."""

    def __init__(self, path):
        self.path = Path(path)
        self.top = self.left = 0
        self.page = 1
        self.columns = None
        self.max_left = 0
        self.rows = []
        self.error = ""
        try:
            self.text = self.path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as error:
            self.text = "Reference unavailable: %s\n\n%s" % (self.path, error)
            self.error = "error"

    def layout(self, columns, page):
        columns, self.page = max(1, columns), max(1, page)
        if columns != self.columns:
            source = self.rows[self.top][0] if self.rows else 0
            # Keep a place within a wrapped paragraph/table, not just its first row.
            offset = sum(_width(row[1]) + 1 for row in self.rows[:self.top] if row[0] == source)
            if self.error:
                self.rows = [(0, line, self.error) for line in _wrap(self.text, columns)]
            elif self.path.suffix.lower() in (".md", ".markdown"):
                self.rows = list(_markdown(self.text, columns))
            else:
                self.rows = [(index, line, "") for index, line in enumerate(self.text.splitlines())]
            self.rows = self.rows or [(0, "", "")]
            self.columns = columns
            self.top = next((index for index, row in enumerate(self.rows) if row[0] >= source), len(self.rows) - 1)
            while (self.top + 1 < len(self.rows) and self.rows[self.top + 1][0] == source
                   and offset >= _width(self.rows[self.top][1]) + 1):
                offset -= _width(self.rows[self.top][1]) + 1
                self.top += 1
            self.max_left = max(0, max(_width(row[1]) for row in self.rows) - columns)
        self.move()

    def move(self, rows=0, columns=0):
        self.top = max(0, min(self.top + rows, len(self.rows) - self.page))
        self.left = max(0, min(self.left + columns, self.max_left))
