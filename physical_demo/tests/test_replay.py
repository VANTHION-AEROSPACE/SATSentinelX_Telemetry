import json
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard import DashboardSession  # noqa: E402
from replay import MAX_SPEED, MIN_SPEED, ReplayController, load_jsonl  # noqa: E402
from receiver import TelemetryReceiver  # noqa: E402
from synthetic_detector import DETECTOR_ID, THRESHOLD_C, detect  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "synthetic_anomaly.jsonl"


class ReplayTests(unittest.TestCase):
    def test_fixture_replay_is_deterministic_and_uses_receiver(self):
        frames = load_jsonl(FIXTURE)

        def run_once():
            receiver = TelemetryReceiver()
            for frame in frames:
                self.assertIsNotNone(receiver.parse_line(frame))
            return [(r["seq"], r["device_time_ms"], r["temperature_c"]) for r in receiver.records]

        first, second = run_once(), run_once()
        self.assertEqual(first, second)
        self.assertEqual(first[8][0:2], (8, 4000))
        self.assertEqual(first[-1][0], 13)

    def test_controller_pause_reset_and_speed_bounds(self):
        frames = load_jsonl(FIXTURE)
        seen = []
        controller = ReplayController(frames, seen.append, lambda: seen.clear())
        self.assertEqual(controller.set_speed(999), MAX_SPEED)
        controller.play()
        controller.pause()
        self.assertEqual(controller.snapshot()["state"], "paused")
        self.assertEqual(controller.set_speed(0), MIN_SPEED)
        controller.reset()
        self.assertEqual(controller.snapshot()["index"], 0)
        self.assertEqual(controller.snapshot()["state"], "idle")

    def test_synthetic_detector_links_exact_event_records(self):
        receiver = TelemetryReceiver()
        for frame in load_jsonl(FIXTURE):
            receiver.parse_line(frame)
        incident = detect(receiver.records)
        self.assertEqual(incident["detector"]["id"], DETECTOR_ID)
        self.assertEqual(incident["detector"]["threshold_c"], THRESHOLD_C)
        self.assertEqual([r["seq"] for r in incident["record_refs"]], [8, 9, 10, 11])
        self.assertEqual(incident["onset_device_time_ms"], 4000)
        self.assertEqual(incident["observed_values_c"], [30.0, 30.2, 30.1, 30.0])
        self.assertEqual(incident["incident_timestamp_device_time_ms"], 4000)
        self.assertEqual([record["seq"] for record in incident["source_records"]], [0, 1, 2, 3, 8, 9, 10, 11])
        self.assertEqual(incident["test_results"]["validation_status"], "PASS")
        self.assertTrue(incident["test_results"]["deterministic"])

    def test_incident_evidence_is_deterministic_and_replayable(self):
        frames = load_jsonl(FIXTURE)

        def run_once():
            receiver = TelemetryReceiver()
            for frame in frames:
                self.assertIsNotNone(receiver.parse_line(frame))
            return detect(receiver.records)

        first, second = run_once(), run_once()
        self.assertEqual(first, second)
        self.assertEqual(first["source_fixture"], "fixtures/synthetic_anomaly.jsonl")
        self.assertEqual(first["source_type"], "synthetic_replay")
        self.assertEqual(first["detector"]["threshold_c"], THRESHOLD_C)
        self.assertEqual(first["test_results"]["replay_record_count"], 14)

    def test_dashboard_replay_produces_incident_and_exportable_records(self):
        session = DashboardSession()
        ok, detail = session.start_replay(speed=20)
        self.assertTrue(ok, detail)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            snapshot = session.snapshot()
            if snapshot["replay"]["state"] == "complete":
                break
            time.sleep(0.02)
        snapshot = session.snapshot()
        self.assertEqual(snapshot["replay"]["state"], "complete")
        self.assertEqual(snapshot["status"], "replay_complete")
        self.assertEqual(snapshot["source_type"], "synthetic_replay")
        self.assertEqual([r["seq"] for r in snapshot["incident"]["record_refs"]], [8, 9, 10, 11])
        self.assertEqual(snapshot["stats"]["total_records"], 14)
        ok, detail = session.reset_replay()
        self.assertTrue(ok, detail)
        reset = session.snapshot()
        self.assertEqual(reset["status"], "replay_ready")
        self.assertEqual(reset["replay"]["state"], "idle")
        self.assertEqual(reset["replay"]["index"], 0)
        session.disconnect(quiet=True)


if __name__ == "__main__":
    unittest.main()
