import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from receiver import TelemetryReceiver, receive_stream, read_framed_line  # noqa: E402


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


class TimeoutStream:
    is_open = True

    def read(self, size=1):
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


if __name__ == "__main__":
    unittest.main()
