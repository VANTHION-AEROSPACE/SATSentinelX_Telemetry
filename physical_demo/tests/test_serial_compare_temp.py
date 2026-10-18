import json
import unittest
from pathlib import Path

from physical_demo.serial_compare_temp import BoundaryCapture, ReadResult, ReadTrace, _raw_reader, script_identity


class FakeSerial:
    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.is_open = True

    def read(self, size):
        if not self.chunks:
            self.is_open = False
            return b""
        return self.chunks.pop(0)

    def close(self):
        self.is_open = False


class SerialCompareTests(unittest.TestCase):
    def test_raw_reader_does_not_transform_bytes(self):
        raw = b"abc\nxyz\r\n"
        result = _raw_reader(FakeSerial([raw]), 4096)
        self.assertEqual(result.data, raw)

    def test_read_trace_accounts_calls_and_bytes(self):
        trace = ReadTrace(max_entries=10)
        trace.record(ReadResult(b"abc", in_waiting=3, requested=3), 0.1)
        trace.record(ReadResult(b"\n", in_waiting=None, requested=4096), 0.2)
        report = trace.report()
        self.assertEqual(report["read_call_count"], 2)
        self.assertEqual(report["read_returned_bytes"], 4)
        self.assertEqual(report["read_trace"][1]["cumulative_returned_bytes"], 4)
        self.assertIsNone(report["read_trace"][1]["in_waiting_before_read"])

    def test_read_trace_is_bounded(self):
        trace = ReadTrace(max_entries=2)
        for _ in range(5):
            trace.record(ReadResult(b"x", in_waiting=1, requested=1), 0.0)
        report = trace.report()
        self.assertEqual(report["read_call_count"], 5)
        self.assertEqual(report["read_returned_bytes"], 5)
        self.assertEqual(len(report["read_trace"]), 2)
        self.assertTrue(report["read_trace_truncated"])

    def test_script_identity_is_absolute_and_hashed(self):
        identity = script_identity()
        self.assertTrue(Path(identity["path"]).is_absolute())
        self.assertEqual(len(identity["sha256"]), 64)

    def test_boundaries_samples_and_trailing_partial(self):
        analyzer = BoundaryCapture(max_frame_samples=2)
        analyzer.feed(b"one\n", 0.1)
        analyzer.feed(b"two\r\npartial", 0.2)
        report = analyzer.report()
        self.assertEqual(report["complete_lf_delimited_frames"], 2)
        self.assertEqual(report["trailing_partial_bytes"], 7)
        self.assertEqual(report["frame_samples"][1]["byte_length"], 4)
        self.assertEqual(report["first_20_lf_read_chunk_times_seconds"], [0.1, 0.2])
        self.assertIn("not exact", report["lf_timestamp_semantics"])

    def test_frame_prefix_is_bounded_and_suffix_shape_is_counted(self):
        analyzer = BoundaryCapture(max_frame_samples=10)
        analyzer.feed(b"ed\"}\r\n", 0.1)
        report = analyzer.report()
        self.assertEqual(report["frame_samples"][0]["prefix_hex"], "6564227d0d")
        self.assertEqual(report["repeated_suffix_fragment_counts"]["ed_quote_brace_cr"], 1)
        self.assertLessEqual(len(report["frame_samples"][0]["prefix_hex"]), 32)

    def test_sample_output_is_json_serializable(self):
        analyzer = BoundaryCapture()
        analyzer.feed(b"bad\n", 0.0)
        json.dumps(analyzer.report())


if __name__ == "__main__":
    unittest.main()
