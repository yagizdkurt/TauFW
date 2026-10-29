# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Text and cursor operations; no terminal, filesystem, or application imports."""


class Buffer:
    def __init__(self, text):
        self.lines = text.split("\n")
        self.row = self.column = self.goal = 0

    @property
    def text(self):
        return "\n".join(self.lines)

    def place(self, row, column):
        self.row = max(0, min(row, len(self.lines) - 1))
        self.column = max(0, min(column, len(self.lines[self.row])))
        self.goal = self.column

    def vertical(self, step):
        goal = self.goal
        self.place(self.row + step, goal)
        self.goal = goal

    def horizontal(self, step):
        if step < 0 and self.column == 0 and self.row:
            self.place(self.row - 1, len(self.lines[self.row - 1]))
        elif step > 0 and self.column == len(self.lines[self.row]) and self.row < len(self.lines) - 1:
            self.place(self.row + 1, 0)
        else:
            self.place(self.row, self.column + step)

    def insert(self, text):
        line = self.lines[self.row]
        parts = text.split("\n")
        replacement = [line[:self.column] + parts[0]] + parts[1:]
        column = len(replacement[-1])
        replacement[-1] += line[self.column:]
        self.lines[self.row:self.row + 1] = replacement
        self.place(self.row + len(parts) - 1, column)

    def backspace(self):
        if self.column:
            line = self.lines[self.row]
            self.lines[self.row] = line[:self.column - 1] + line[self.column:]
            self.place(self.row, self.column - 1)
        elif self.row:
            column = len(self.lines[self.row - 1])
            self.lines[self.row - 1] += self.lines.pop(self.row)
            self.place(self.row - 1, column)

    def delete(self):
        line = self.lines[self.row]
        if self.column < len(line):
            self.lines[self.row] = line[:self.column] + line[self.column + 1:]
        elif self.row < len(self.lines) - 1:
            self.lines[self.row] += self.lines.pop(self.row + 1)
        self.goal = self.column
