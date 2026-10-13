# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Small numeric helpers for binning, job chunking and plot layout.

Moved from TauFW.common.tools.math (2026); same results for the same inputs.

    float_range(start, end, step)       ─▶ bin edges        (Fitter, legacy plots)
    partition(items, parts | max_size)  ─▶ even chunks      (storage validation)
    partition_by_sum(values, maximum)   ─▶ grouped chunks   (event-based job chunks)
    columnize(items, columns)           ─▶ legend order     (Plot)
    magnitude, scale_vector             ─▶ axis ranges      (Plot)
    relative_difference                 ─▶ sum-of-weights check (Sample)
"""
from math import ceil, floor, log10
from typing import Iterable, List, Optional, Sequence, TypeVar

__all__ = ["float_range", "partition", "partition_by_sum", "columnize",
           "magnitude", "scale_vector", "relative_difference"]

Item = TypeVar("Item")


# =============================================================================
# ================================= SEQUENCES =================================


def float_range(start: float, end: float, step: float, scale: int = 1000) -> List[float]:
    """Numbers from start (included) to end (excluded) in steps of `step`.
    Each value is computed from start, not by adding up steps, so rounding
    errors do not accumulate; `scale` sets that computation's precision."""
    values = [start]
    index = 1
    value = start + step
    while value < end:
        index += 1
        values.append(value)
        value = start + (scale * index) * step / scale
    return values


def partition(items: Iterable[Item], parts: Optional[int] = None,
              max_size: Optional[int] = None) -> List[List[Item]]:
    """Split items into `parts` chunks as evenly sized as possible, earlier
    chunks taking the remainder: 7 items in 3 parts -> sizes 3, 2, 2.
    With max_size, the number of parts is the fewest that keeps each chunk
    at most max_size long. Chunks can be empty when parts > len(items)."""
    if not isinstance(items, (tuple, list)):
        items = list(items)
    if max_size is not None:
        parts = ceil(len(items) / float(max_size))
    elif parts is None:
        raise ValueError("partition: Please pass parts or max_size (both are None)!")
    remaining = len(items)
    divider = float(parts)
    chunks = []
    first = 0
    for _ in range(parts):
        size = int(ceil(remaining / divider))
        chunks.append(items[first:first + size])
        remaining -= size
        divider -= 1
        first += size
    return chunks


def partition_by_sum(values: Iterable[float], maximum: float) -> List[List[float]]:
    """Group values so each group sums to at most `maximum`, largest first:
    each group starts with the largest value left, then takes every next
    value that still fits (and stops once the sum is exactly `maximum`).
    A value larger than `maximum` gets a group of its own. The input is not
    changed."""
    remaining = sorted(values, reverse=True)
    groups = []
    while remaining:
        first = remaining.pop(0)
        total = first
        groups.append([first])
        for value in remaining[:]:
            if total + value <= maximum:
                groups[-1].append(value)
                remaining.remove(value)
                if total + value == maximum:
                    break
                total += value
    return groups


def columnize(items: Iterable[Item], columns: int = 2) -> List[Item]:
    """Reorder items so that a row-by-row layout in `columns` columns (like a
    TLegend) reads column by column: [1,2,3,4,5,6,7] -> [1,5,2,6,3,7,4] for
    two columns. Fewer than two columns returns items unchanged."""
    if columns < 2:
        return items
    if not isinstance(items, (tuple, list)):
        items = list(items)
    chunks = partition(items, columns)
    ordered = []
    row = 0
    while len(ordered) < len(items):
        for chunk in chunks:
            if row < len(chunk):
                ordered.append(chunk[row])
        row += 1
    return ordered


# =============================================================================
# ================================== NUMBERS ==================================


def magnitude(x: float) -> int:
    """Rough order of magnitude used for log-axis ranges: the number of digits
    before the decimal point for x >= 1 (45 -> 2, 2304 -> 4, 10 -> 2), and
    floor(log10(x)) for 0 < x < 1 (0.84 -> -1). 0 and 1 are special-cased;
    a negative x takes floor(log10(|x|)) unless it is a multiple of 10."""
    if x == 0:
        return 0
    if x == 1:
        return 1
    log = round(log10(abs(x)) * 1e6) / 1e6
    if x % 10 == 0:
        return int(log) + 1
    if x < 1:
        return int(floor(log))
    return int(ceil(log))


def scale_vector(start: float, end: float, ratio: float, log: bool = False) -> float:
    """The point at `ratio` along start -> end: start + ratio*(end-start).
    With log=True, on a logarithmic axis: start*10**|ratio*log10(end/start)|
    (start and end must be nonzero with the same sign)."""
    if log:
        if start == 0:
            raise ValueError("scale: Cannot logarithmically scale ab vector if a=0!")
        if start * end <= 0:
            raise ValueError("scale: Cannot logarithmically scale ab vector if a and b do not have "
                             "the same sign! a=%s, b=%s" % (start, end))
        span = abs(ratio * log10(end / start))
        return start * (10 ** span)
    return start + ratio * (end - start)


def relative_difference(x: float, y: float) -> float:
    """|x - y| / x; for x == 0: 0 if y is 0 too, else -1."""
    if x == 0:
        return 0 if y == 0 else -1
    return abs(x - y) / float(x)
