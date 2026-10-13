#Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""A text loading bar that redraws itself in place on one terminal line.

Moved from TauFW.common.tools.LoadingBar (2026). The characters written are
byte for byte those of the old class, so logs and BBB baselines do not change.

    CLI.loading_bar(steps, ...) ─▶ LoadingBar: frame "[    ]" (+ counter, message)
                                     │
                                     └─ count(message) per step: "=" ─▶ counter ─▶ message
                                          last step ─▶ append, erase (remove) or newline
"""
from math import log10
from typing import TextIO

__all__ = ["LoadingBar"]


class LoadingBar:
    """Draws `width` symbols over `steps` calls of count().

    Pipelines:    count(message, steps) -> draw progress, finish on the last step
    Construction: LoadingBar(stream, steps, width, counter, remove, symbol,
                             prefix, append, message) draws the empty frame
    """

    # =========================================================================
    # =============================== PIPELINES ===============================

    def count(self, message: str = "", steps: int = 1) -> None:
        """Advance by `steps` (clipped to what is left), then redraw the
        counter and message; the last step finishes the bar."""
        if self.done:
            return
        steps = max(min(steps, self.steps - self.tally), 0)
        position = int(round(float(self.tally + steps) * self.width / self.steps))
        self._draw_symbols(position - self.position)
        self.position = position
        self.tally += steps
        if self.counter:
            self._draw_counter()
        if message:
            self._draw_message(message)
        if self.tally >= self.steps:
            self._finish()
            self.done = True

    # =========================================================================
    # ================================ HELPERS ================================

    def _finish(self) -> None:
        """Last step: write `append`, erase the bar (remove) or end the line."""
        if self.append:
            self._draw_message(self.append, move_back=self.remove)
        if self.remove:
            self._erase()
        elif not self.append:
            self._draw_message("\n")

    # =========================================================================
    # ===================== BACKWARD COMPATIBILITY, CLEANUP ===================
    # The drawing below keeps the exact characters of the old LoadingBar:
    # the cursor parks just after "[" by writing backspaces ("\b"), and every
    # redraw rewrites the rest of the line and moves back again. Modernize it
    # (e.g. CLI.update_progress with "\r") in its own commit with a BBB re-lock.

    def _draw_frame(self) -> None:
        """The empty bar, then back to just after '['."""
        self._stream.write("%s[%s]" % (self.prefix, " " * self.width))
        self._stream.flush()
        self._stream.write("\b" * (self.width + 1))

    def _draw_symbols(self, number: int) -> None:
        self._stream.write(self.symbol * number)
        self._stream.flush()

    def _draw_counter(self) -> None:
        """Redraw ' tally/steps' after the bar and move back."""
        self._counter_text = " %s/%i" % (self._counter_format % self.tally, self.steps)
        self._stream.write("%s]%s" % (" " * (self.width - self.position), self._counter_text))
        self._stream.flush()
        self._stream.write("\b" * (self.width + 1 - self.position + len(self._counter_text)))

    def _draw_message(self, message: str, move_back: bool = True) -> None:
        """Redraw the message after the counter; it is padded to the length of
        the previous one, and anything from a newline on is written as is."""
        end = ""
        if "\n" in message:
            end = message[message.index("\n"):]
            message = message[:message.index("\n")]
        self.message = message.ljust(len(self.message)) + end
        self._stream.write("%s]%s %s" % (" " * (self.width - self.position), self._counter_text,
                                         self.message))
        self._stream.flush()
        if move_back:
            self._stream.write("\b" * (self.width + 2 - self.position + len(self._counter_text)
                                       + len(self.message)))

    def _erase(self) -> None:
        """Blank the whole line, leaving the cursor where the bar started."""
        length = len(self.prefix) + self.width + len(self._counter_text) + len(self.message) + 4
        self._stream.write("\b" * (self.width + 1 + len(self.prefix)))
        self._stream.write(" " * length)
        self._stream.write("\b" * length)
        self._stream.flush()

    # =========================================================================
    # ============================= CONSTRUCTION ==============================

    def __init__(self, stream: TextIO, steps: int = 10, width: int = None, counter: bool = False,
                 remove: bool = False, symbol: str = "=", prefix: str = ">>> ", append: str = "",
                 message: str = "") -> None:
        """steps: count() calls to fill the bar; width: bar length in symbols
        (default: steps); counter: show 'tally/steps'; remove: erase the bar
        when done; append: text written when done. Draws the empty bar."""
        self._stream = stream
        self.steps = max(steps, 1)
        self.width = max(self.steps if width is None else width, 1)
        self.counter = counter
        self.remove = remove
        self.symbol = symbol
        self.prefix = prefix
        self.append = append
        self.message = message
        self.tally = 0
        self.position = 0
        self.done = False
        self._counter_format = "%%%ii" % (log10(self.steps) + 1)
        self._counter_text = ""
        if self.counter:
            self._counter_text = " %s/%i" % (self._counter_format % self.tally, self.steps)
        self._draw_frame()
        if self.counter:
            self._draw_counter()
        if self.message:
            self._draw_message(self.message)

    def __repr__(self) -> str:
        return "<LoadingBar %s/%s>" % (self.tally, self.steps)
