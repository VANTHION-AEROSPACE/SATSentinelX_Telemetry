import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from physical_demo.raw_serial_capture import (
    READ_SIZE,
    analyze_raw_bytes,
    capture_raw,
    replay_through_buffered_reader,
    split_lf_frames,
)


TELEMETRY = (
    b'{"schema_version":1,"message_type":"telemetry",'
    b'"device_id":"test","seq":1,"device_time_ms":10,'
    b'"temperature_c":20.0,"sensor_valid":true,'
    b'"sensor_status":"measurement_verified"}'
)


class FakeSerial:
    def __init__(self, chunks, *, timeout=0.1):
        self.chunks = list(chunks)
        self.timeout = timeout
        self.port = None
        self.baudrate = None
        self.dtr = None
        self.rts = None
        self.is_open = False
        self.read_requests = []

    def open(self):
        self.is_open = True

    def read(self, size):
        self.read_requests.append(size)
        if not self.chunks:
            self.is_open = False
            return b""
        return self.chunks.pop(0)

    def close(self):
        self.is_open = False


class FakeSerialModule:
    def __init__(self, chunks):
        self.instance = None
        self.chunks = chunks

    def Serial(self, **kwargs):
        self.instance = FakeSerial(self.chunks, timeout=kwargs["timeout"])
        self.instance.baudrate = kwargs["baudrate"]
        return self.instance


class SequenceClock:
    def __init__(self, values):
        self.values = iter(values)
        self.last = 0.0

    def __call__(self):
        try:
            self.last = next(self.values)
        except StopIteration:
            pass
        return self.last


class RawCaptureTests(unittest.TestCase):
    def test_split_and_multiple_frames_preserve_exact_bytes(self):
        raw = TELEMETRY + b"\nsecond\r\npartial"
        frames, trailing = split_lf_frames(raw)
        self.assertEqual(frames, [TELEMETRY, b"second\r"])
        self.assertEqual(trailing, b"partial")
        self.assertEqual(b"\n".join(frames) + b"\n" + trailing, raw)

    def test_analysis_counts_invalid_bytes_and_trailing_partial(self):
        raw = TELEMETRY + b"\n" + b"{bad}\n" + b"\xff\npartial"
        report = analyze_raw_bytes(raw)
        self.assertEqual(report["complete_lf_delimited_frames"], 3)
        self.assertEqual(report["counts"]["valid_telemetry_objects"], 1)
        self.assertEqual(report["counts"]["invalid_json_frames"], 1)
        self.assertEqual(report["counts"]["invalid_utf8_frames"], 1)
        self.assertEqual(report["trailing_partial_bytes"], len(b"partial"))

    def test_replay_matches_raw_frames_with_crlf_and_chunking(self):
        raw = TELEMETRY + b"\r\nsecond\n"
        replay = replay_through_buffered_reader(raw)
        self.assertTrue(replay["frames_match"])
        self.assertEqual(replay["raw_complete_frame_count"], 2)
        self.assertEqual(replay["reader_returned_frame_count"], 2)

    def test_capture_writes_exact_binary_and_bounded_reads(self):
        raw = TELEMETRY + b"\nsecond\n"
        fake_serial = FakeSerialModule([raw[:7], raw[7:]])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "capture.bin"
            metadata = root / "capture.json"
            result = capture_raw(
                "FAKE", output_bin=binary, output_meta=metadata,
                duration=10, max_capture_bytes=10_000,
                serial_module=fake_serial,
                clock=SequenceClock([0.0, 0.1, 0.2, 0.3, 0.4, 11.0]),
                utc_clock=lambda: "2026-01-01T00:00:00.000Z",
            )
            self.assertEqual(binary.read_bytes(), raw)
            self.assertEqual(result["capture_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(json.loads(metadata.read_text())["capture_bytes"], len(raw))
            self.assertTrue(all(size <= READ_SIZE for size in fake_serial.instance.read_requests))
            self.assertEqual(fake_serial.instance.read_requests[0], READ_SIZE)
            self.assertTrue(fake_serial.instance.dtr is False)
            self.assertTrue(fake_serial.instance.rts is False)

    def test_capture_byte_limit_truncates_without_overwriting_boundary(self):
        fake_serial = FakeSerialModule([b"abcdefghij"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = capture_raw(
                "FAKE", output_bin=root / "capture.bin", output_meta=root / "capture.json",
                duration=10, max_capture_bytes=5, serial_module=fake_serial,
                clock=SequenceClock([0.0, 0.1, 0.2, 11.0]),
                utc_clock=lambda: "2026-01-01T00:00:00.000Z",
            )
            self.assertEqual((root / "capture.bin").read_bytes(), b"abcde")
            self.assertEqual(result["termination_reason"], "byte_limit")
            self.assertEqual(result["capture_bytes"], 5)


if __name__ == "__main__":
    unittest.main()
