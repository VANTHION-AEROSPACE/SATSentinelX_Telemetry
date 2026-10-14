import json
import sys
import threading
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import dashboard  # noqa: E402
from dashboard import DashboardSession  # noqa: E402
from power_autonomy import (  # noqa: E402
    ACTION_ID,
    CRITICAL_VOLTAGE_V,
    RECOVERY_VOLTAGE_V,
    STATES,
    WARNING_VOLTAGE_V,
    load_validated_power_records,
    report_json,
    run_policy,
    run_scenario,
)


SUCCESS = ROOT / "fixtures" / "synthetic_power_recovery_success.jsonl"
FAILURE = ROOT / "fixtures" / "synthetic_power_recovery_failure.jsonl"


class PowerAutonomyTests(unittest.TestCase):
    def test_normal_telemetry_stays_monitoring(self):
        records, receiver = load_validated_power_records(SUCCESS)
        report = run_policy(records[:2], scenario_id="normal")
        self.assertEqual(receiver.errors, [])
        self.assertEqual(report["final_outcome"]["state"], "MONITORING")
        self.assertIsNone(report["trigger"])

    def test_warning_detection_records_threshold_trigger(self):
        records, _ = load_validated_power_records(SUCCESS)
        report = run_policy(records[:3], scenario_id="warning")
        self.assertEqual(report["final_outcome"]["state"], "WARNING")
        self.assertEqual(report["trigger"]["seq"], 2)
        self.assertEqual(report["configuration"]["warning_voltage_v"], WARNING_VOLTAGE_V)

    def test_policy_rejection_escalates_without_action(self):
        records, _ = load_validated_power_records(SUCCESS)
        report = run_policy(records, scenario_id="policy-rejected", action_authorized=False)
        self.assertEqual(report["final_outcome"]["state"], "ESCALATED")
        self.assertFalse(report["policy_decision"]["accepted"])
        self.assertFalse(report["action"]["issued"])
        self.assertIn("simulated_action_authorized", report["policy_decision"]["preconditions"])

    def test_success_requires_post_action_verification(self):
        report = run_scenario(SUCCESS, scenario_id="recovery_success")
        self.assertEqual(report["final_outcome"]["state"], "RECOVERED")
        self.assertTrue(report["final_outcome"]["success"])
        self.assertTrue(report["action"]["simulated"])
        self.assertTrue(report["verification"]["criteria_met"])
        self.assertEqual(report["verification"]["consecutive_recovery_samples"], 2)

    def test_failed_recovery_escalates(self):
        report = run_scenario(FAILURE, scenario_id="recovery_failure")
        self.assertEqual(report["final_outcome"]["state"], "ESCALATED")
        self.assertFalse(report["final_outcome"]["success"])
        self.assertTrue(report["action"]["issued"])
        self.assertFalse(report["verification"]["criteria_met"])

    def test_reset_clears_report(self):
        session = DashboardSession()
        ok, _ = session.run_autonomy_scenario("recovery_success")
        self.assertTrue(ok)
        self.assertIsNotNone(session.snapshot()["autonomy"])
        ok, _ = session.reset_autonomy()
        self.assertTrue(ok)
        self.assertIsNone(session.snapshot()["autonomy"])

    def test_evidence_contains_policy_trace_and_is_json(self):
        report = run_scenario(SUCCESS, scenario_id="recovery_success")
        parsed = json.loads(report_json(report))
        self.assertEqual(parsed["states"], list(STATES))
        self.assertEqual(parsed["configuration"]["critical_voltage_v"], CRITICAL_VOLTAGE_V)
        self.assertEqual(parsed["configuration"]["recovery_voltage_v"], RECOVERY_VOLTAGE_V)
        self.assertEqual(parsed["configuration"]["action_id"], ACTION_ID)
        self.assertEqual(parsed["trigger"]["voltage_v"], 3.45)
        self.assertEqual(parsed["action"]["simulated"], True)
        self.assertGreaterEqual(len(parsed["verification"]["records"]), 2)
        self.assertEqual(parsed["final_outcome"]["state"], "RECOVERED")
        self.assertEqual(parsed["source_type"], "synthetic_power_scenario")
        self.assertEqual(parsed["execution_metrics"]["records_processed"], 6)
        self.assertEqual(parsed["execution_metrics"]["verification_samples_used"], 2)
        self.assertEqual(parsed["execution_metrics"]["outcome"], "RECOVERED")
        self.assertIn("execution_time_ms", parsed["execution_metrics"])
        self.assertIn("peak_traced_memory_bytes", parsed["execution_metrics"])

    def test_dashboard_run_and_export_endpoint(self):
        previous = dashboard.SESSION
        dashboard.SESSION = DashboardSession()
        server = dashboard.ThreadingHTTPServer(("127.0.0.1", 0), dashboard.DashboardHandler)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            request = urllib.request.Request(
                base + "/api/autonomy/run",
                data=json.dumps({"scenario": "recovery_failure"}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            result = json.loads(urllib.request.urlopen(request).read())
            self.assertTrue(result["ok"])
            response = urllib.request.urlopen(base + "/api/autonomy/evidence/export")
            self.assertEqual(response.headers["Content-Type"], "application/json; charset=utf-8")
            self.assertIn("SATSentinelX_Autonomy_recovery_failure.json", response.headers["Content-Disposition"])
            evidence = json.loads(response.read().decode("utf-8"))
            self.assertEqual(evidence["final_outcome"]["state"], "ESCALATED")
            self.assertEqual(evidence, dashboard.SESSION.snapshot()["autonomy"])
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
            dashboard.SESSION = previous


if __name__ == "__main__":
    unittest.main()
