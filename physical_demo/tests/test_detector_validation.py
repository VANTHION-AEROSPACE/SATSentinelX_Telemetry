import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from detector_validation import run_validation_suite  # noqa: E402


class DetectorValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_validation_suite()
        cls.cases = {case["scenario_id"]: case for case in cls.report["cases"]}

    def test_normal_and_threshold_boundary_have_no_false_positive(self):
        for scenario_id in ("normal", "threshold_boundary"):
            case = self.cases[scenario_id]
            self.assertFalse(case["detected"])
            self.assertEqual(case["event_metrics"], {"tp": 0, "fp": 0, "fn": 0, "tn": 1})

    def test_detectable_anomaly_and_recovery_are_detected(self):
        for scenario_id in ("canonical_replay_fixture", "detectable_anomaly", "recovery_to_normal"):
            case = self.cases[scenario_id]
            self.assertTrue(case["detected"])
            self.assertEqual(case["event_metrics"]["tp"], 1)
            self.assertEqual(case["detection_delay_ms"], 0)
            self.assertTrue(case["evidence_complete"])

    def test_missing_and_invalid_data_are_event_level_misses(self):
        missing = self.cases["missing_data"]
        self.assertEqual(missing["ground_truth_records"], [{
            "schema_version": 1, "message_type": "telemetry", "device_id": "synthetic-validation",
            "seq": 3, "device_time_ms": 1500, "sensor_valid": True, "sensor_status": "measurement_verified",
        }])
        invalid = self.cases["invalid_sensor"]
        self.assertEqual(invalid["ground_truth_records"][0]["sensor_status"], "sensor_bus_unavailable")
        for scenario_id in ("missing_data", "invalid_sensor"):
            case = self.cases[scenario_id]
            self.assertFalse(case["detected"])
            self.assertEqual(case["event_metrics"]["fn"], 1)
            self.assertEqual(case["event_classification"], "unobservable_missing_measurement" if scenario_id == "missing_data" else "unobservable_invalid_measurement")

    def test_health_evaluation_surfaces_all_integrity_faults(self):
        self.assertEqual(self.cases["missing_data"]["observed_health_faults"], ["missing_data"])
        self.assertEqual(self.cases["invalid_sensor"]["observed_health_faults"], ["invalid_sensor"])
        self.assertEqual(self.cases["stale_data"]["observed_health_faults"], ["stale_data"])
        self.assertEqual(self.report["aggregate"]["telemetry_health_metrics"], {
            "tp": 3, "fp": 0, "fn": 0, "tn": 21,
            "precision": 1.0, "recall": 1.0, "false_positive_rate": 0.0,
        })

    def test_aggregate_metrics_and_determinism(self):
        aggregate = self.report["aggregate"]
        self.assertEqual(aggregate["event_metrics"], {"tp": 3, "fp": 0, "fn": 2, "tn": 2, "precision": 1.0, "recall": 0.6, "false_positive_rate": 0.0})
        self.assertEqual(aggregate["sample_metrics"], {"tp": 8, "fp": 0, "fn": 0, "tn": 31, "precision": 1.0, "recall": 1.0, "false_positive_rate": 0.0})
        self.assertEqual(aggregate["detection_delay_ms"]["mean_detected_event_delay"], 0.0)
        self.assertEqual(aggregate["evidence_complete_detected_cases"], 3)
        self.assertEqual(run_validation_suite(), self.report)


if __name__ == "__main__":
    unittest.main()
