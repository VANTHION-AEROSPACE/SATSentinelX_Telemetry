import json
import unittest

from physical_demo.serial_diagnostic import FrameAnalyzer

TELEMETRY = {
    "schema_version": 1,
    "message_type": "telemetry",
    "device_id": "esp32-bmp280-01",
    "seq": 1,
    "device_time_ms": 1910,
    "temperature_c": 33.33,
    "sensor_valid": True,
    "sensor_status": "measurement_verified",
}


class FrameAnalyzerTests(unittest.TestCase):
    def test_normal_telemetry(self):
        raw = json.dumps(TELEMETRY, separators=(",", ":")).encode() + b"\n"
        analyzer = FrameAnalyzer()
        analyzer.feed(raw)
        report = analyzer.finalize()
        self.assertEqual(report["complete_lf_delimited_frames"], 1)
        self.assertEqual(report["counts"]["valid_json_objects"], 1)
        self.assertEqual(report["counts"]["valid_telemetry_objects"], 1)
        self.assertEqual(report["trailing_partial_bytes"], 0)

    def test_crlf(self):
        raw = json.dumps(TELEMETRY, separators=(",", ":")).encode() + b"\r\n"
        analyzer = FrameAnalyzer()
        analyzer.feed(raw)
        self.assertEqual(analyzer.finalize()["counts"]["valid_telemetry_objects"], 1)

    def test_fragmented_input(self):
        raw = json.dumps(TELEMETRY, separators=(",", ":")).encode() + b"\n"
        analyzer = FrameAnalyzer()
        for byte in raw:
            analyzer.feed(bytes([byte]))
        report = analyzer.finalize()
        self.assertEqual(report["complete_lf_delimited_frames"], 1)
        self.assertEqual(report["counts"]["invalid_json_frames"], 0)

    def test_malformed_json_is_counted_and_sampled(self):
        analyzer = FrameAnalyzer()
        analyzer.feed(b'{"bad":}\n')
        report = analyzer.finalize()
        self.assertEqual(report["counts"]["invalid_json_frames"], 1)
        self.assertEqual(report["suspicious_samples"][0]["kind"], "invalid_json")
        self.assertLessEqual(len(bytes.fromhex(report["suspicious_samples"][0]["prefix_hex"])), 16)

    def test_invalid_utf8(self):
        analyzer = FrameAnalyzer()
        analyzer.feed(b'\xff\xfe\n')
        self.assertEqual(analyzer.finalize()["counts"]["invalid_utf8_frames"], 1)

    def test_trailing_partial_is_not_counted_as_complete(self):
        analyzer = FrameAnalyzer()
        analyzer.feed(b'{"schema_version":1')
        report = analyzer.finalize()
        self.assertEqual(report["complete_lf_delimited_frames"], 0)
        self.assertEqual(report["trailing_partial_bytes"], len(b'{"schema_version":1'))
        self.assertEqual(report["suspicious_samples"][0]["kind"], "trailing_partial")

    def test_samples_are_bounded(self):
        analyzer = FrameAnalyzer(max_samples=2)
        for _ in range(5):
            analyzer.feed(b'{bad}\n')
        report = analyzer.finalize()
        self.assertEqual(report["counts"]["invalid_json_frames"], 5)
        self.assertEqual(len(report["suspicious_samples"]), 2)

    def test_overlong_frame_is_bounded(self):
        analyzer = FrameAnalyzer(max_frame_bytes=8)
        analyzer.feed(b"x" * 100 + b"\n")
        report = analyzer.finalize()
        self.assertEqual(report["frame_length_bytes"]["max"], 100)
        self.assertEqual(report["frame_length_bytes"]["over_diagnostic_frame_limit_count"], 1)
        self.assertEqual(len(bytes.fromhex(report["suspicious_samples"][0]["prefix_hex"])), 16)

    def test_status_message_counted_as_non_telemetry(self):
        analyzer = FrameAnalyzer()
        analyzer.feed(b'{"message":"BMP280_READY","chip_id":88}\n')
        report = analyzer.finalize()
        self.assertEqual(report["counts"]["valid_json_objects"], 1)
        self.assertEqual(report["counts"]["non_telemetry_status_messages"], 1)
        self.assertEqual(report["suspicious_samples"], [])


if __name__ == "__main__":
    unittest.main()
