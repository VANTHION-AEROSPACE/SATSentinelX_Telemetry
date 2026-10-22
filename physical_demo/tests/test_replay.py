import hashlib
import json
import sys
import time
import unittest
import uuid
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
        self.assertEqual(len(frames), 14)
        self.assertEqual(
            hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
            "0a0be4e0f990e06d4221f8b530c11d3a66f3ecf625248e6147cf5bcbdf8787dc",
        )

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

    def test_dashboard_replay_produces_incident_and_exportable_records(self):
        session = DashboardSession()
        ok, detail = session.start_replay(speed=20)
        self.assertTrue(ok, detail)
        first_session_id = session.snapshot()["session"]["session_id"]
        self.assertTrue(uuid.UUID(first_session_id))
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
        self.assertEqual(snapshot["session"]["session_id"], first_session_id)
        self.assertEqual(snapshot["session"]["boot_epoch"]["state"], "unknown")
        self.assertEqual([r["seq"] for r in snapshot["incident"]["record_refs"]], [8, 9, 10, 11])
        self.assertEqual(snapshot["incident"]["incident_id"], "synthetic-thermal-rise-001")
        self.assertEqual(len(snapshot["findings"]), 1)
        finding = snapshot["findings"][0]
        self.assertEqual(finding["session_id"], first_session_id)
        self.assertEqual(finding["device"]["boot_epoch"]["state"], "unknown")
        self.assertEqual(finding["detector"]["configuration"]["threshold"], 26.0)
        self.assertEqual(finding["event"]["onset"]["device_elapsed_ms"], 4000)
        self.assertEqual([r["seq"] for r in finding["event"]["record_refs"]], [8, 9, 10, 11])
        self.assertEqual(finding["source"]["evidence_class"], "synthetic_demonstration")
        self.assertEqual(snapshot["stats"]["total_records"], 14)
        ok, detail = session.reset_replay()
        self.assertTrue(ok, detail)
        reset = session.snapshot()
        self.assertNotEqual(reset["session"]["session_id"], first_session_id)
        self.assertEqual(reset["status"], "replay_ready")
        self.assertEqual(reset["replay"]["state"], "idle")
        self.assertEqual(reset["replay"]["index"], 0)
        ok, detail = session.start_replay(speed=20)
        self.assertTrue(ok, detail)
        second_session_id = session.snapshot()["session"]["session_id"]
        self.assertNotEqual(second_session_id, reset["session"]["session_id"])
        session.pause_replay()
        session.disconnect(quiet=True)

    def test_start_replay_rejects_overlapping_active_attempt(self):
        session = DashboardSession()
        ok, detail = session.start_replay(speed=0.25)
        self.assertTrue(ok, detail)
        original_session_id = session.snapshot()["session"]["session_id"]

        ok, detail = session.start_replay(speed=20)
        self.assertFalse(ok)
        self.assertIn("already playing", detail)
        self.assertEqual(session.snapshot()["session"]["session_id"], original_session_id)
        session.pause_replay()

    def test_incremental_finding_updates_are_idempotent_and_one_aggregate(self):
        session = DashboardSession()
        session.session_id = str(uuid.uuid4())
        session.source_type = "synthetic_replay"
        frames = load_jsonl(FIXTURE)
        active_ids = set()
        for frame in frames:
            session.ingest_frame(frame)
            if session.finding is not None:
                active_ids.add(session.finding["finding_id"])

        self.assertEqual(len(active_ids), 1)
        finding = session.finding
        session.ingest_frame(frames[-1])
        self.assertEqual(session.finding["finding_id"], finding["finding_id"])
        self.assertEqual(session.finding["deduplication_key"], finding["deduplication_key"])
        self.assertEqual(len(session.snapshot()["findings"]), 1)
        self.assertEqual(
            [ref["seq"] for ref in session.finding["event"]["record_refs"]],
            [8, 9, 10, 11],
        )


if __name__ == "__main__":
    unittest.main()
