"""Events and output followed from files: writer, readers, and the Tests/run.py side of the protocol."""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import checkout  # noqa: F401  (must precede TauFW.Utilities imports)
from TauFW.Framework._internal.operations import EVENTS_ENV, EventReader, EventWriter, LogTail
from TauFW.Framework._internal.operations import _events


def tests_events_module():
    """Tests/support/events.py, which Tests/run.py imports without the TauFW package."""
    path = Path(__file__).resolve().parents[1] / "support" / "events.py"
    spec = importlib.util.spec_from_file_location("tests_support_events", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EventTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = os.path.join(self.temporary.name, "events.jsonl")

    def append(self, data):
        with open(self.path, "ab") as stream:
            stream.write(data)

    def test_writer_appends_one_object_per_line(self):
        writer = EventWriter(self.path)
        writer.emit("case_start", id="a", group="file.py")
        writer.emit("case_end", id="a", status="PASS", log=Path("a.log"))
        with open(self.path, encoding="utf-8") as stream:
            events = [json.loads(line) for line in stream]
        self.assertEqual([(event["kind"], event["id"]) for event in events], [("case_start", "a"), ("case_end", "a")])
        self.assertEqual(events[1]["log"], "a.log")
        self.assertIsInstance(events[0]["t"], float)

    def test_writer_without_a_path_or_with_a_bad_one_does_nothing(self):
        EventWriter(None).emit("summary")
        self.assertFalse(os.path.exists(self.path))
        EventWriter(os.path.join(self.path, "missing", "events.jsonl")).emit("summary")  # no exception
        self.assertIsNone(EventWriter.from_environment({}).path)
        self.assertEqual(EventWriter.from_environment({EVENTS_ENV: self.path}).path, self.path)

    def test_reader_continues_and_keeps_an_unfinished_line(self):
        reader = EventReader(self.path)
        self.assertEqual(reader.read(), [])  # no file yet
        self.append(b'{"kind": "suite", "total": 2}\n{"kind": "case_')
        self.assertEqual(reader.read(), [{"kind": "suite", "total": 2}])
        self.append(b'start", "id": "a"}\n')
        self.assertEqual(reader.read(), [{"kind": "case_start", "id": "a"}])
        self.assertEqual(reader.read(), [])

    def test_reader_skips_lines_that_are_not_events(self):
        self.append(b'not json\n[1, 2]\n{"no": "kind"}\n{"kind": 3}\n{"kind": "summary"}\n')
        self.assertEqual(EventReader(self.path).read(), [{"kind": "summary"}])

    def test_reader_starts_again_after_truncation(self):
        reader = EventReader(self.path)
        self.append(b'{"kind": "old", "padding": "' + b"x" * 50 + b'"}\n')
        reader.read()
        open(self.path, "w").close()
        self.append(b'{"kind": "new"}\n')
        self.assertEqual(reader.read(), [{"kind": "new"}])

    def test_reader_reads_a_bounded_amount_per_call(self):
        line = b'{"kind": "message", "text": "' + b"x" * 1000 + b'"}\n'
        self.append(line * 3)
        reader = EventReader(self.path)
        with mock.patch.object(_events, "READ_LIMIT", len(line) + 10):
            self.assertEqual(len(reader.read()), 1)
            self.assertEqual(len(reader.read()), 1)
            self.assertEqual(len(reader.read()), 1)

    def test_tests_writer_speaks_the_same_protocol(self):
        module = tests_events_module()
        self.assertEqual(module.ENV, EVENTS_ENV)
        with mock.patch.dict(os.environ, {EVENTS_ENV: self.path}):
            module.emit("case_end", id="a", status="FAIL", seconds=1.5, log=Path("a.log"), details=["x"])
        events = EventReader(self.path).read()
        self.assertEqual(len(events), 1)
        self.assertEqual({key: events[0][key] for key in ("kind", "id", "status", "seconds", "log", "details")},
                         dict(kind="case_end", id="a", status="FAIL", seconds=1.5, log="a.log", details=["x"]))
        with mock.patch.dict(os.environ, {}, clear=True):
            module.emit("summary")  # no variable: nothing written
        self.assertEqual(EventReader(self.path).read(), events)
        self.assertEqual(module.worker_environment({EVENTS_ENV: self.path, "KEEP": "1"}), {"KEEP": "1"})


class LogTailTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = os.path.join(self.temporary.name, "output.log")

    def append(self, data):
        with open(self.path, "ab") as stream:
            stream.write(data)

    def test_lines_partial_line_and_carriage_returns(self):
        tail = LogTail(self.path)
        self.assertEqual(tail.read(), [])
        self.append(b"one\ntwo\r")
        self.assertEqual(tail.read(), ["one"])  # \r may be the first half of \r\n
        self.append(b"\nbar 10%\rbar 20%")
        self.assertEqual(tail.read(), ["two", "bar 10%"])
        self.assertEqual(tail.partial, "bar 20%")
        self.append(b"\n")
        self.assertEqual(tail.read(), ["bar 20%"])
        self.assertEqual(list(tail.lines), ["one", "two", "bar 10%", "bar 20%"])

    def test_bounded_memory_and_long_lines(self):
        tail = LogTail(self.path, maxlines=3)
        self.append(b"".join(b"line %d\n" % index for index in range(10)))
        self.assertEqual(len(tail.read()), 10)
        self.assertEqual(list(tail.lines), ["line 7", "line 8", "line 9"])
        with mock.patch.object(_events, "LINE_LIMIT", 5):
            self.append(b"x" * 20)
            self.assertEqual(tail.read(), ["x" * 20])
            self.assertEqual(tail.partial, "")

    def test_multibyte_characters_split_between_reads(self):
        tail = LogTail(self.path)
        data = "sigma σ\n".encode("utf-8")
        self.append(data[:-2])
        self.assertEqual(tail.read(), [])
        self.append(data[-2:])
        self.assertEqual(tail.read(), ["sigma σ"])

    def test_truncated_log_starts_again(self):
        tail = LogTail(self.path)
        self.append(b"old output that is long\n")
        tail.read()
        open(self.path, "w").close()
        self.append(b"new\n")
        self.assertEqual(tail.read(), ["new"])
        self.assertEqual(list(tail.lines), ["new"])


if __name__ == "__main__":
    unittest.main()
