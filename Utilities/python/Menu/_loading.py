# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Small ASCII decay, driven by the screen's clock rather than a waiting animation loop."""
import time


FRAMES = (
    ("", "H", ""),
    ("", "H --", ""),
    ("", "H ----*", ""),
    ("       /", "H ----*", "       \\"),
    ("       /-- tau-", "H ----*", "       \\-- tau+"),
    ("       /-- tau-", "H ----*", "       \\-- tau+"),
    ("          tau-", "      .", "          tau+"),
    ("", "      .", ""),
)


def decay(now=None):
    """One frame; ASCII keeps the same cell width on SSH terminals without a UTF-8 locale."""
    return FRAMES[int((time.monotonic() if now is None else now) / 0.15) % len(FRAMES)]


def draw_loading(ui, screen, rect, now=None):
    top, left, rows, width = rect
    frame = decay(now)
    if rows < len(frame):
        frame = (">--*--<",)
    y = top + max(0, (rows - len(frame)) // 2)
    x = left + max(0, (width - max(map(len, frame))) // 2)
    for index, line in enumerate(frame[:rows]):
        ui._line(screen, y + index, x, line[:width], color=ui.styles["accent"])
