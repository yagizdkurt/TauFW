# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Public numeric helpers: ranges, chunking and plot-axis arithmetic."""

from ._math import (float_range, partition, partition_by_sum, columnize,
                    magnitude, scale_vector, relative_difference)

__all__ = ["float_range", "partition", "partition_by_sum", "columnize",
           "magnitude", "scale_vector", "relative_difference"]
