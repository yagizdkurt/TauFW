"""Numeric helpers: results recorded from TauFW.common.tools.math before it
was deleted (2026-10-13)."""

import unittest

import checkout  # noqa: F401  (must precede TauFW.Utilities imports)
from TauFW.Utilities.Math import (columnize, float_range, magnitude, partition,
                                  partition_by_sum, relative_difference, scale_vector)


class SequenceTests(unittest.TestCase):
    def test_float_range(self):
        self.assertEqual(float_range(2.2, 5.61, 0.2), [
            2.2, 2.4000000000000004, 2.6, 2.8000000000000003, 3.0, 3.2, 3.4000000000000004, 3.6,
            3.8000000000000003, 4.0, 4.2, 4.4, 4.6, 4.800000000000001, 5.0, 5.2, 5.4, 5.6])
        self.assertEqual(float_range(-2.5, 2.5, 0.5),
                         [-2.5, -2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0])
        self.assertEqual(float_range(2.0, 4.0, 0.2),
                         [2.0, 2.2, 2.4, 2.6, 2.8, 3.0, 3.2, 3.4, 3.6, 3.8])
        values = float_range(0, 1, 0.1)
        self.assertEqual(values, [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
        self.assertIs(type(values[0]), int)  # start is kept as given

    def test_partition(self):
        self.assertEqual(partition(list(range(7)), parts=3), [[0, 1, 2], [3, 4], [5, 6]])
        self.assertEqual(partition(range(10), max_size=4), [[0, 1, 2, 3], [4, 5, 6], [7, 8, 9]])
        self.assertEqual(partition([1, 2], 5), [[1], [2], [], [], []])
        self.assertEqual(partition([], 2), [[], []])
        with self.assertRaises(ValueError):
            partition([1, 2])

    def test_partition_by_sum(self):
        values = [2, 3, 4, 5, 1]
        self.assertEqual(partition_by_sum(values, 6), [[5, 1], [4, 2], [3]])
        self.assertEqual(values, [2, 3, 4, 5, 1])  # the old function sorted its input in place
        self.assertEqual(partition_by_sum([5, 5, 5, 1, 1, 10, 3], 10), [[10], [5, 5], [5, 3, 1, 1]])
        self.assertEqual(partition_by_sum([], 3), [])

    def test_columnize(self):
        self.assertEqual(columnize([1, 2, 3, 4, 5, 6, 7], 2), [1, 5, 2, 6, 3, 7, 4])
        self.assertEqual(columnize(range(10), 3), [0, 4, 7, 1, 5, 8, 2, 6, 9, 3])
        self.assertEqual(columnize(iter([1, 2, 3, 4, 5]), 4), [1, 3, 4, 5, 2])
        items = [1, 2]
        self.assertIs(columnize(items, 1), items)


class NumberTests(unittest.TestCase):
    def test_magnitude(self):
        inputs = (0, 1, 45, 2304, 0.84, 10, 100, 20, 2.5, 0.1, 0.05, -45, -40, -0.5, 1e-3, 123456.7)
        self.assertEqual([magnitude(x) for x in inputs],
                         [0, 1, 2, 4, -1, 2, 3, 2, 1, -1, -2, 1, 2, -1, -3, 6])

    def test_relative_difference(self):
        pairs = ((0, 0), (0, 3), (2, 3), (4, 1), (-2, 1))
        self.assertEqual([relative_difference(*pair) for pair in pairs], [0, -1, 0.5, 0.75, -1.5])

    def test_scale_vector(self):
        self.assertEqual([scale_vector(1, 10, 0.5), scale_vector(0, 10, 0.3), scale_vector(10, 0, 0.25)],
                         [5.5, 3.0, 7.5])
        self.assertEqual([scale_vector(1, 100, 0.5, log=True), scale_vector(0.1, 1000, 0.25, log=True),
                          scale_vector(100, 1, 0.5, log=True)], [10.0, 1.0, 1000.0])
        with self.assertRaises(ValueError):
            scale_vector(0, 10, 0.5, log=True)
        with self.assertRaises(ValueError):
            scale_vector(-1, 10, 0.5, log=True)


if __name__ == "__main__":
    unittest.main()
