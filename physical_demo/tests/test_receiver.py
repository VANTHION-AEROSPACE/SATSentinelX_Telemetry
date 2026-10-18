import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from receiver import BufferedLFReader, RawTeeStream, TelemetryReceiver, receive_stream, read_framed_line  # noqa: E402


def message(seq=0, device_time_ms=0, temperature_c=24.5, sensor_valid=True, sensor_status=None):
    if sensor_status is None:
        sensor_status = "value_present_read_status_unverified" if sensor_valid else "sensor_value_invalid"
    return json.dumps({
        "schema_version": 1,
        "message_type": "telemetry",
        "device_id": "test-device",
        "seq": seq,
        "device_time_ms": device_time_ms,
        "temperature_c": temperature_c,
        "sensor_valid": sensor_valid,
        "sensor_status": sensor_status,
    })


class BytesStream:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        self.is_open = True

    def read(self, size=1):
        if self.pos >= len(self.data):
            self.is_open = False
            return b""
        part = self.data[self.pos:self.pos + size]
        self.pos += len(part)
        return part


class ChunkStream:
    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.is_open = True
        self.read_sizes = []

    def read(self, size=1):
        self.read_sizes.append(size)
        if not self.chunks:
            self.is_open = False
            return b""
        return self.chunks.pop(0)


class TimeoutStream:
    is_open = True

    def read(self, size=1):
        return b""


class PartialTimeoutThenDataStream:
    def __init__(self, partial: bytes, remainder: bytes):
        self.partial = partial
        self.remainder = remainder
        self.pos = 0
        self.timed_out = False
        self.is_open = True

    def read(self, size=1):
        if self.pos < len(self.partial):
            part = self.partial[self.pos:self.pos + size]
            self.pos += len(part)
            return part
        if not self.timed_out:
            self.timed_out = True
            return b""
        if self.remainder:
            part = self.remainder[:size]
            self.remainder = self.remainder[size:]
            return part
        self.is_open = False
        return b""


class DisconnectStream:
    is_open = True

    def read(self, size=1):
        raise OSError("USB serial disconnected")


class Clock:
    def __init__(self, values):
        self.values = iter(values)
        self.last = 0.0

    def __call__(self):
        try:
            self.last = next(self.values)
        except StopIteration:
            pass
        return self.last


class ReceiverTests(unittest.TestCase):
    def test_buffered_reader_preserves_multiple_frames_and_crlf(self):
        stream = BytesStream(b"alpha\nbeta\r\n")
        reader = BufferedLFReader(stream)
        self.assertEqual(reader.read_line()[0:2], ("line", b"alpha"))
        self.assertEqual(reader.read_line()[0:2], ("line", b"beta\r"))
        self.assertEqual(reader.read_line()[0], "eof")
        self.assertEqual(stream.pos, len(stream.data))

    def test_buffered_reader_handles_split_frame_and_read_bound(self):
        stream = ChunkStream([b'{"a":', b'1}\n'])
        reader = BufferedLFReader(stream, read_size=4)
        self.assertEqual(reader.read_line(), ("line", b'{"a":1}'))
        self.assertTrue(all(size == 4 for size in stream.read_sizes))

    def test_buffered_reader_retains_partial_frame_across_timeout(self):
        stream = PartialTimeoutThenDataStream(
            b'{"message":"tele',
            b'metry"}\n',
        )
        reader = BufferedLFReader(stream)

        kind, frame = reader.read_line()
        self.assertEqual(kind, "timeout")
        self.assertIsNone(frame)

        self.assertEqual(reader.read_line(), ("line", b'{"message":"telemetry"}'))
        self.assertEqual(reader.read_line()[0], "eof")

    def test_buffered_reader_retains_partial_prefix_and_preserves_later_frames(self):
        stream = PartialTimeoutThenDataStream(b"partial", b"broken\nnext\n")
        reader = BufferedLFReader(stream)
        diagnostics = []
        self.assertEqual(reader.read_line(diagnostics), ("timeout", None))
        self.assertEqual(reader.read_line(), ("line", b"partialbroken"))
        self.assertEqual(reader.read_line(), ("line", b"next"))
        self.assertEqual(reader.read_line()[0], "eof")
        self.assertIn("partial_bytes=7", diagnostics)

    def test_buffered_reader_eof_partial_and_oversized_frames_are_explicit(self):
        partial = BufferedLFReader(BytesStream(b"partial"))
        diagnostics = []
        self.assertEqual(partial.read_line(diagnostics), ("eof_partial", None))
        self.assertIn("partial_bytes=7", diagnostics)

        complete_stream = BytesStream((b"x" * 4097) + b"\nnext\n")
        complete = BufferedLFReader(complete_stream)
        self.assertEqual(complete.read_line()[0], "oversized")
        self.assertEqual(complete.read_line(), ("line", b"next"))

        incomplete = BufferedLFReader(BytesStream(b"x" * 4097))
        self.assertEqual(incomplete.read_line()[0], "oversized_partial")

    def test_buffered_reader_preserves_bytes_without_duplication_or_loss(self):
        source = b"a\x00b\r\nc\xff\nlast\n"
        reader = BufferedLFReader(BytesStream(source))
        frames = []
        while True:
            kind, frame = reader.read_line()
            if kind == "line":
                frames.append(frame + b"\n")
                continue
            self.assertEqual(kind, "eof")
            break
        self.assertEqual(b"".join(frames), source)

    def test_buffered_reader_repeated_empty_reads_do_not_loop(self):
        reader = BufferedLFReader(TimeoutStream())
        self.assertEqual([reader.read_line()[0] for _ in range(3)], ["timeout"] * 3)

    def test_buffered_reader_invalid_utf8_and_malformed_json_remain_rejections(self):
        receiver = TelemetryReceiver()
        output = io.StringIO()
        data = b"\xff\n{bad}\n" + (message(0, 0, sensor_status="measurement_verified") + "\n").encode()
        run = receive_stream(BytesStream(data), output, receiver, duration=10, clock=Clock([0] * 20))
        self.assertEqual(run["ended_reason"], "eof")
        self.assertEqual(receiver.errors[:2], ["invalid_utf8", "invalid_json"])
        self.assertEqual(len(output.getvalue().splitlines()), 1)

    def test_bytes_lf_and_crlf_input_and_complete_output_schema(self):
        receiver = TelemetryReceiver()
        output = io.StringIO()
        run = receive_stream(
            BytesStream((message() + "\n" + message(1, 200) + "\r\n").encode()),
            output,
            receiver,
            duration=60,
            clock=Clock([0, 0, 0, 0, 0, 11]),
        )
        records = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(run["ended_reason"], "eof")
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["sequence_status"], "first")
        self.assertEqual(records[1]["sequence_status"], "contiguous")
        self.assertEqual(records[1]["device_time_status"], "increasing")
        self.assertIn("host_received_utc", records[0])
        self.assertIn("host_received_monotonic_s", records[0])
        self.assertIn("host_gap_s", records[0])

    def test_invalid_utf8_and_oversized_lines_are_rejected_and_stream_continues(self):
        receiver = TelemetryReceiver()
        output = io.StringIO()
        data = b"\xff\n" + (b"x" * 4097) + b"\n" + (message(0, 0) + "\n").encode()
        run = receive_stream(BytesStream(data), output, receiver, duration=10, clock=Clock([0] * 30))
        self.assertEqual(run["ended_reason"], "eof")
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        self.assertEqual(receiver.errors[:2], ["invalid_utf8", "oversized"])
        invalid_events = [event for event in receiver.events if event.startswith("rejected:invalid_utf8:")]
        self.assertEqual(len(invalid_events), 1)
        self.assertIn("bytes=1:prefix_hex=ff", invalid_events[0])

    def test_invalid_json_shape_is_bounded_and_does_not_get_ignored(self):
        receiver = TelemetryReceiver()
        output = io.StringIO()
        noise = b"not-json-payload\n" * 129
        run = receive_stream(
            BytesStream(noise + (message(0, 0, sensor_status="measurement_verified") + "\n").encode()),
            output,
            receiver,
            duration=10,
            clock=Clock([0] * 400),
        )
        self.assertEqual(run["ended_reason"], "eof")
        self.assertEqual(receiver.errors.count("invalid_json"), 129)
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        invalid_events = [event for event in receiver.events if event.startswith("rejected:invalid_json:")]
        self.assertEqual(len(invalid_events), 129)
        self.assertTrue(all("bytes=16:prefix_hex=6e6f742d6a736f6e2d7061796c6f6164" in event for event in invalid_events))
        self.assertTrue(all(len(event) < 100 for event in invalid_events))

    def test_missing_fields_types_schema_and_nonfinite_values(self):
        receiver = TelemetryReceiver()
        self.assertIsNone(receiver.parse_line("{}"))
        self.assertIsNone(receiver.parse_line(message().replace('"schema_version": 1', '"schema_version": 2')))
        self.assertIsNone(receiver.parse_line(message().replace('"seq": 0', '"seq": true')))
        self.assertIsNone(receiver.parse_line(message().replace('24.5', 'NaN')))
        self.assertEqual(len(receiver.errors), 4)

    def test_sensor_invalid_message_is_explicit_not_valid_temperature(self):
        receiver = TelemetryReceiver()
        record = receiver.parse_line(message(temperature_c=None, sensor_valid=False))
        self.assertFalse(record["sensor_valid"])
        self.assertEqual(record["sensor_status"], "sensor_value_invalid")
        self.assertIsNone(record["temperature_c"])

    def test_unknown_sensor_status_fails_closed(self):
        receiver = TelemetryReceiver()
        self.assertIsNone(receiver.parse_line(message(sensor_status="unknown_status")))
        self.assertEqual(receiver.errors, ["valid_status_mismatch"])

    def test_sequence_duplicate_gap_and_out_of_order(self):
        receiver = TelemetryReceiver()
        self.assertEqual(receiver.parse_line(message(0, 0))["sequence_status"], "first")
        self.assertEqual(receiver.parse_line(message(1, 200))["sequence_status"], "contiguous")
        self.assertEqual(receiver.parse_line(message(3, 600))["sequence_status"], "gap")
        self.assertEqual(receiver.parse_line(message(3, 800))["sequence_status"], "duplicate")
        self.assertEqual(receiver.parse_line(message(2, 1000))["sequence_status"], "out_of_order")

    def test_backward_and_equal_device_times(self):
        receiver = TelemetryReceiver()
        self.assertIsNotNone(receiver.parse_line(message(0, 100)))
        equal = receiver.parse_line(message(1, 100))
        self.assertEqual(equal["device_time_status"], "equal")
        self.assertIsNone(receiver.parse_line(message(2, 99)))
        self.assertIn("device_time_not_monotonic", receiver.errors)

    def test_timeout_and_eof_are_explicit(self):
        self.assertEqual(read_framed_line(TimeoutStream())[0], "timeout")
        eof = BytesStream(b"")
        self.assertEqual(read_framed_line(eof)[0], "eof")

    def test_framing_diagnostics_distinguish_partial_and_oversized_frames(self):
        partial_diagnostics = []
        kind, _ = read_framed_line(BytesStream(b'{"schema_version":1'), diagnostics=partial_diagnostics)
        self.assertEqual(kind, "eof_partial")
        self.assertEqual(partial_diagnostics, ["partial_bytes=19"])

        oversized_diagnostics = []
        kind, _ = read_framed_line(BytesStream(b"x" * 4097), diagnostics=oversized_diagnostics)
        self.assertEqual(kind, "oversized_partial")
        self.assertEqual(oversized_diagnostics, ["bytes_at_least=4097"])

    def test_partial_timeout_discards_suffix_until_lf_before_resuming(self):
        telemetry = (message(0, 0, sensor_status="measurement_verified") + "\n").encode()
        stream = PartialTimeoutThenDataStream(b'{"schema_version":1', b"broken-suffix\n" + telemetry)
        receiver = TelemetryReceiver()
        output = io.StringIO()
        run = receive_stream(stream, output, receiver, duration=10, clock=Clock([0] * 30))
        self.assertEqual(run["ended_reason"], "eof")
        self.assertEqual(receiver.errors, ["invalid_json"])
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        self.assertEqual(json.loads(output.getvalue())["seq"], 0)

    def test_timeout_at_multiple_offsets_discards_exact_verified_suffix_and_recovers(self):
        first = (message(0, 0, sensor_status="measurement_verified") + "\r\n").encode()
        next_frame = (message(1, 200, sensor_status="measurement_verified") + "\n").encode()
        suffix = b'verified"}\r'
        self.assertTrue(first.endswith(suffix + b"\n"))
        for offset in (1, len(first) // 2, len(first) - len(suffix)):
            with self.subTest(offset=offset):
                receiver = TelemetryReceiver()
                output = io.StringIO()
                stream = PartialTimeoutThenDataStream(first[:offset], first[offset:] + next_frame)
                run = receive_stream(stream, output, receiver, duration=10, clock=Clock([0] * 100))
                self.assertEqual(run["ended_reason"], "eof")
                self.assertEqual(receiver.errors, [])
                records = [json.loads(line) for line in output.getvalue().splitlines()]
                self.assertEqual([record["seq"] for record in records], [0, 1])

    def test_known_firmware_startup_status_is_event_not_malformed_telemetry(self):
        receiver = TelemetryReceiver()
        self.assertIsNone(receiver.parse_line('{"message":"BMP280_READY","chip_id":88}'))
        self.assertEqual(receiver.errors, [])
        self.assertEqual(receiver.events, ["startup_status:BMP280_READY"])
        self.assertIsNone(receiver.parse_line('{"message":"BMP280_INIT_FAILED"}'))
        self.assertEqual(receiver.errors, [])
        self.assertEqual(receiver.events[-1], "startup_status:BMP280_INIT_FAILED")

    def test_unknown_status_line_remains_a_validation_error(self):
        receiver = TelemetryReceiver()
        self.assertIsNone(receiver.parse_line('{"message":"unexpected_status"}'))
        self.assertEqual(receiver.errors, ["missing:" + ",".join((
            "schema_version", "message_type", "device_id", "seq", "device_time_ms",
            "temperature_c", "sensor_valid", "sensor_status",
        ))])

    def test_serial_disconnect_is_incomplete_and_preserves_partial_log(self):
        receiver = TelemetryReceiver()
        output = io.StringIO()
        run = receive_stream(DisconnectStream(), output, receiver, duration=60, clock=Clock([0]))
        summary = receiver.acceptance_summary(**run)
        self.assertEqual(summary["status"], "INCOMPLETE_SERIAL_DISCONNECT")
        self.assertEqual(output.getvalue(), "")

    def test_acceptance_250_record_threshold_and_partial_run(self):
        receiver = TelemetryReceiver()
        for seq in range(250):
            self.assertIsNotNone(receiver.parse_line(message(seq, seq * 200, sensor_status="measurement_verified"), host_monotonic=seq * 0.2))
        passing = receiver.acceptance_summary(ended_reason="duration", elapsed_seconds=60)
        self.assertEqual(passing["status"], "PASS")

        partial = TelemetryReceiver()
        for seq in range(249):
            partial.parse_line(message(seq, seq * 200, sensor_status="measurement_verified"), host_monotonic=seq * 0.2)
        failing = partial.acceptance_summary(ended_reason="duration", elapsed_seconds=60)
        self.assertEqual(failing["status"], "FAIL_ACCEPTANCE")
        self.assertIn("fewer_than_250_valid_telemetry_records", failing["failure_reasons"])

    def test_unverified_measurement_cannot_pass_otherwise_valid_run(self):
        receiver = TelemetryReceiver()
        for seq in range(249):
            receiver.parse_line(message(seq, seq * 200, sensor_status="measurement_verified"), host_monotonic=seq * 0.2)
        receiver.parse_line(message(249, 249 * 200, sensor_status="value_present_read_status_unverified"), host_monotonic=249 * 0.2)
        summary = receiver.acceptance_summary(ended_reason="duration", elapsed_seconds=60)
        self.assertEqual(summary["status"], "FAIL_ACCEPTANCE")
        self.assertEqual(summary["verified_telemetry_records"], 249)
        self.assertEqual(summary["unverified_telemetry_records"], 1)
        self.assertIn("acquisition_unverified_present", summary["failure_reasons"])

    def test_telemetry_gap_fails_acceptance(self):
        receiver = TelemetryReceiver()
        receiver.parse_line(message(0, 0), host_monotonic=0.0)
        receiver.parse_line(message(1, 200), host_monotonic=3.0)
        summary = receiver.acceptance_summary(ended_reason="duration", elapsed_seconds=60)
        self.assertEqual(summary["status"], "FAIL_ACCEPTANCE")
        self.assertIn("telemetry_gap_over_2_seconds", summary["failure_reasons"])

    def test_trailing_silence_fails_acceptance(self):
        receiver = TelemetryReceiver()
        for seq in range(250):
            receiver.parse_line(
                message(seq, seq * 200, sensor_status="measurement_verified"),
                host_monotonic=seq * 0.2,
            )
        receiver.note_run_end(60.0)
        summary = receiver.acceptance_summary(ended_reason="duration", elapsed_seconds=60)
        self.assertEqual(summary["status"], "FAIL_ACCEPTANCE")
        self.assertIn("telemetry_gap_over_2_seconds", summary["failure_reasons"])
        self.assertGreater(summary["max_host_gap_s"], 2.0)

    def test_serial_timeout_fails_acceptance(self):
        receiver = TelemetryReceiver()
        for seq in range(250):
            receiver.parse_line(
                message(seq, seq * 200, sensor_status="measurement_verified"),
                host_monotonic=seq * 0.2,
            )
        receiver.note_event("serial_timeout")
        receiver.note_run_end(50.0)
        summary = receiver.acceptance_summary(ended_reason="duration", elapsed_seconds=60)
        self.assertEqual(summary["status"], "FAIL_ACCEPTANCE")
        self.assertIn("serial_timeout_present", summary["failure_reasons"])

    def test_rejected_record_fails_acceptance(self):
        receiver = TelemetryReceiver()
        for seq in range(250):
            receiver.parse_line(
                message(seq, seq * 200, sensor_status="measurement_verified"),
                host_monotonic=seq * 0.2,
            )
        receiver.reject("invalid_json")
        receiver.note_run_end(50.0)
        summary = receiver.acceptance_summary(ended_reason="duration", elapsed_seconds=60)
        self.assertEqual(summary["status"], "FAIL_ACCEPTANCE")
        self.assertIn("validation_errors_present", summary["failure_reasons"])


    def test_raw_tee_stream_captures_exact_bytes_and_offsets(self):
        chunks = [b"alpha\r\n", b"\xff\x00omega", b""]
        source = ChunkStream(chunks)
        captured = io.BytesIO()
        tee = RawTeeStream(source, captured)

        returned = [tee.read(4096), tee.read(4096), tee.read(4096)]

        self.assertEqual(returned, chunks)
        self.assertEqual(captured.getvalue(), b"".join(chunks))
        self.assertEqual([item["start_offset"] for item in tee.trace], [0, 7, 14])
        self.assertEqual([item["returned_bytes"] for item in tee.trace], [7, 7, 0])
        self.assertEqual(tee.trace[-1]["cumulative_captured_bytes"], 14)


if __name__ == "__main__":
    unittest.main()
