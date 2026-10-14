"""Event chunking boundaries with cached counts; never open an input file."""
from collections import Counter
import unittest
from unittest import mock

from TauFW.PicoProducer.jobs import chunking


class ChunkingTests(unittest.TestCase):
    @staticmethod
    def events(operand, counts):
        """Decode a chunk independently of the production regex, clipping at EOF."""
        if operand.endswith('.root'):
            name, first, stop = operand, 0, counts[operand]
        else:
            name, first, size = operand.rsplit(':', 2)
            first = int(first)
            stop = min(first + int(size), counts[name])
        return [(name, event) for event in range(first, stop)]

    def check_chunks(self, inputs, counts, evenly, expected_total, expected_chunks=None):
        filenames = list(inputs)  # the API mutates this list
        cached = dict(counts)
        with mock.patch.object(chunking, 'ensureTFile', side_effect=AssertionError('unexpected file read')) as read:
            total, chunks = chunking.chunkify_by_evts(filenames, 5, evenly=evenly, evtdict=cached, verb=1)
        read.assert_not_called()
        self.assertEqual(cached, counts)
        expected = Counter(event for operand in inputs for event in self.events(operand, counts))
        actual = Counter()
        for chunk in chunks:
            self.assertTrue(chunk, 'empty job chunk')
            events = [event for operand in chunk for event in self.events(operand, counts)]
            self.assertGreater(len(events), 0, chunk)
            self.assertLessEqual(len(events), 5, chunk)
            for operand in chunk:
                if not operand.endswith('.root'):
                    self.assertLessEqual(int(operand.rsplit(':', 1)[1]), 5, operand)
            actual.update(events)
        self.assertEqual(actual, expected, 'event coverage changed or events were duplicated')
        self.assertTrue(all(count == 1 for count in actual.values()), 'events assigned to multiple chunks')
        self.assertEqual(Counter(event for operand in filenames for event in self.events(operand, counts)), expected)
        if expected_chunks is not None:
            self.assertEqual(chunks, expected_chunks)
        self.assertEqual(total, expected_total, 'returned total omits or double-counts input events')

    def test_empty_and_zero_event_inputs(self):
        for evenly in (False, True):
            for inputs, counts in (([], {}), (['empty.root'], {'empty.root': 0})):
                with self.subTest(evenly=evenly, inputs=inputs):
                    self.check_chunks(inputs, counts, evenly, 0, [])

    def test_exact_job_limit(self):
        for evenly in (False, True):
            with self.subTest(evenly=evenly):
                self.check_chunks(['a.root'], {'a.root': 5}, evenly, 5, [['a.root:0:5']])

    def test_large_files_and_clipped_last_range(self):
        for count, evenly, operands in (
                (6, False, ['a.root:0:5', 'a.root:5:5']),
                (6, True, ['a.root:0:3', 'a.root:3:3']),
                (11, False, ['a.root:0:5', 'a.root:5:5', 'a.root:10:5']),
                (11, True, ['a.root:0:4', 'a.root:4:4', 'a.root:8:4'])):
            with self.subTest(count=count, evenly=evenly):
                self.check_chunks(['a.root'], {'a.root': count}, evenly, count,
                                  [[operand] for operand in operands])

    def test_mixed_small_large_and_zero_event_files(self):
        counts = {'small.root': 2, 'other.root': 3, 'large.root': 11, 'empty.root': 0}
        for evenly in (False, True):
            with self.subTest(evenly=evenly):
                self.check_chunks(list(counts), counts, evenly, 16)

    def test_already_split_inputs_are_preserved_and_counted(self):
        inputs = ['a.root:0:5', 'a.root:5:5', 'small.root']
        for evenly in (False, True):
            with self.subTest(evenly=evenly):
                self.check_chunks(inputs, {'a.root': 8, 'small.root': 2}, evenly, 10,
                                  [['a.root:0:5'], ['a.root:5:5'], ['small.root']])


if __name__ == '__main__':
    unittest.main()
