import json
import sys
import threading
import time
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import dashboard
from dashboard import DashboardSession


def telemetry(seq=0, device_time_ms=0, **overrides):
    record = {
        "schema_version": 1,
        "message_type": "telemetry",
        "device_id": "synthetic-demo",
        "seq": seq,
        "device_time_ms": device_time_ms,
        "temperature_c": 24.5,
        "sensor_valid": True,
        "sensor_status": "measurement_verified",
    }
    record.update(overrides)
    return (json.dumps(record) + "\n").encode("utf-8")


class DashboardSessionTests(unittest.TestCase):
    def test_verified_record_updates_state_without_fabricating_other_sensors(self):
        session = DashboardSession()
        session.status = "connected"
        session.start_logging()
        accepted = session.ingest_frame(telemetry(), host_monotonic=10.0)

        snapshot = session.snapshot()
        self.assertIsNotNone(accepted)
        self.assertEqual(snapshot["stats"]["valid_records"], 1)
        self.assertEqual(snapshot["stats"]["invalid_records"], 0)
        self.assertEqual(snapshot["stats"]["logged_records"], 1)
        self.assertIsNone(snapshot["chart"][0]["humidity_pct"])
        self.assertIsNone(snapshot["chart"][0]["pressure_hpa"])
        exported = session.export_lines().splitlines()
        self.assertEqual(len(exported), 1)
        self.assertEqual(json.loads(exported[0])["seq"], 0)

    def test_rejected_frame_and_sequence_gap_are_visible(self):
        session = DashboardSession()
        self.assertIsNone(session.ingest_frame(b"not-json\n", host_monotonic=1.0))
        session.ingest_frame(telemetry(seq=0, device_time_ms=0), host_monotonic=2.0)
        session.ingest_frame(telemetry(seq=2, device_time_ms=200), host_monotonic=5.5)

        snapshot = session.snapshot()
        self.assertEqual(snapshot["stats"]["invalid_records"], 1)
        self.assertEqual(snapshot["stats"]["sequence_anomalies"], 1)
        self.assertEqual(snapshot["stats"]["data_gaps"], 1)
        self.assertEqual(snapshot["records"][0]["sequence_status"], "gap")

    def test_sensor_invalid_record_is_retained_but_not_valid(self):
        session = DashboardSession()
        session.ingest_frame(telemetry(
            temperature_c=None,
            sensor_valid=False,
            sensor_status="sensor_bus_unavailable",
        ))

        snapshot = session.snapshot()
        self.assertEqual(snapshot["stats"]["valid_records"], 0)
        self.assertEqual(snapshot["stats"]["invalid_records"], 1)
        self.assertIsNone(snapshot["chart"][0]["temperature_c"])

    def test_logging_fails_closed_when_disconnected_or_already_active(self):
        session = DashboardSession()
        ok, detail = session.start_logging()
        self.assertFalse(ok)
        self.assertIn("Connect", detail)
        session.status = "connected"
        self.assertEqual(session.start_logging()[0], True)
        ok, detail = session.start_logging()
        self.assertFalse(ok)
        self.assertIn("already", detail)

    def test_navigation_controls_and_views_are_declared(self):
        html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text(encoding="utf-8")
        javascript = (Path(__file__).resolve().parents[1] / "dashboard" / "app.js").read_text(encoding="utf-8")
        for view in ("dashboard-view", "log-view", "session-view", "settings-view"):
            self.assertIn(f'data-view="{view}"', html)
            self.assertIn(f'id="{view}"', html)
        for control in ("refresh-ports", "connect", "disconnect", "start-logging", "stop-logging", "download", "clear-records", "log-clear"):
            self.assertIn(f'id="{control}"', html)
        self.assertIn("function clearDisplay()", javascript)
        self.assertIn("state.hiddenRecordKeys.add", javascript)
        self.assertNotIn('post("/api/session/clear"', javascript)
        self.assertIn("window.location.hash", javascript)

    def test_dashboard_serves_page_state_and_supplied_assets(self):
        server = dashboard.ThreadingHTTPServer(("127.0.0.1", 0), dashboard.DashboardHandler)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            self.assertEqual(urllib.request.urlopen(base + "/").status, 200)
            self.assertEqual(urllib.request.urlopen(base + "/api/state").status, 200)
            asset = urllib.request.urlopen(base + "/assets/satsentinel-x-emblem.png")
            self.assertEqual(asset.status, 200)
            self.assertEqual(asset.headers["Content-Type"], "image/png")
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

    def test_replay_api_and_evidence_export_use_same_incident(self):
        previous = dashboard.SESSION
        dashboard.SESSION = DashboardSession()
        dashboard.SESSION.logging = True
        server = dashboard.ThreadingHTTPServer(("127.0.0.1", 0), dashboard.DashboardHandler)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            request = urllib.request.Request(
                base + "/api/replay/start",
                data=json.dumps({"source": "synthetic", "speed": 20}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            response = json.loads(urllib.request.urlopen(request).read())
            self.assertTrue(response["ok"])
            for _ in range(100):
                state = json.loads(urllib.request.urlopen(base + "/api/state").read())
                if state["replay"]["state"] == "complete":
                    break
                time.sleep(0.02)
            self.assertEqual(state["replay"]["state"], "complete")
            self.assertEqual(state["source_type"], "synthetic_replay")
            self.assertEqual([r["seq"] for r in state["incident"]["record_refs"]], [8, 9, 10, 11])
            self.assertEqual(state["incident"]["incident_id"], "synthetic-thermal-rise-001")
            self.assertEqual(len(state["findings"]), 1)
            finding = state["findings"][0]
            self.assertEqual(finding["event"]["onset"]["device_elapsed_ms"], 4000)
            self.assertEqual([r["seq"] for r in finding["event"]["record_refs"]], [8, 9, 10, 11])
            evidence_response = urllib.request.urlopen(base + "/api/evidence/export")
            self.assertEqual(evidence_response.headers["Content-Type"], "application/json; charset=utf-8")
            self.assertIn("SATSentinelX_Incident_synthetic-thermal-rise-001.json", evidence_response.headers["Content-Disposition"])
            evidence = json.loads(evidence_response.read().decode("utf-8"))
            self.assertEqual(evidence, state["incident"])

            finding_response = urllib.request.urlopen(base + "/api/findings/export")
            self.assertEqual(finding_response.headers["Content-Type"], "application/json; charset=utf-8")
            finding_export = json.loads(finding_response.read().decode("utf-8"))
            self.assertEqual(finding_export, finding)

            telemetry_response = urllib.request.urlopen(base + "/api/session/export")
            telemetry_records = [json.loads(line) for line in telemetry_response.read().decode("utf-8").splitlines()]
            self.assertEqual(len(telemetry_records), 14)
            self.assertTrue(all(record["message_type"] == "telemetry" for record in telemetry_records))
            self.assertTrue(all("finding_id" not in record and "findings" not in record for record in telemetry_records))
            self.assertNotIn("message_type", finding_export)
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
            dashboard.SESSION.disconnect(quiet=True)
            dashboard.SESSION = previous


if __name__ == "__main__":
    unittest.main()
