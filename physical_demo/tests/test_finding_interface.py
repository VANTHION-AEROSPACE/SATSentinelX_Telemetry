import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard import DashboardSession  # noqa: E402
from finding_interface import FindingContractError, validate_finding  # noqa: E402
from replay import load_jsonl  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "synthetic_anomaly.jsonl"


def ml_finding(session_id, *, status="scored", decision="anomaly", score=0.82, reason_codes=None):
    if status != "scored":
        decision = "undetermined"
        score = None
    return {
        "schema": "satsentinel.detector-finding",
        "schema_version": 1,
        "finding_kind": "sample_result",
        "finding_id": f"{session_id}:future-ml:seq-8",
        "deduplication_key": f"{session_id}:future-ml:seq-8",
        "session_id": session_id,
        "source": {
            "type": "synthetic_replay",
            "id": "physical_demo/fixtures/synthetic_anomaly.jsonl",
            "evidence_class": "synthetic_demonstration",
        },
        "detector": {
            "name": "future_ml_detector",
            "version": "0.1-test-contract",
            "kind": "ml",
            "model_artifact_digest": "test-only-placeholder",
        },
        "evaluation": {
            "status": status,
            "decision": decision,
            "score": score,
            "score_semantics": "test-only stub score; no model executed" if score is not None else None,
        },
        "affected_channels": [{"channel_id": "pressure", "unit": None}],
        "evidence": {
            "record_refs": [{"session_id": session_id, "seq": 8, "device_elapsed_ms": 4000}]
        },
        "explanation": {
            "summary": "Test-only future detector interface payload.",
            "reason_codes": reason_codes or [],
        },
    }


class FindingInterfaceTests(unittest.TestCase):
    def test_accepts_detector_agnostic_scored_ml_payload(self):
        finding = ml_finding("session-test")
        validate_finding(finding)

    def test_insufficient_and_blocked_results_require_undetermined_and_reason(self):
        for status, reason in (
            ("insufficient_data", "NO_VALID_SAMPLES"),
            ("not_scored", "PRESSURE_MAPPING_UNVERIFIED"),
        ):
            with self.subTest(status=status):
                finding = ml_finding("session-test", status=status, reason_codes=[reason])
                validate_finding(finding)
                self.assertEqual(finding["evaluation"]["decision"], "undetermined")
                self.assertIsNone(finding["evaluation"]["score"])
                self.assertEqual(finding["explanation"]["reason_codes"], [reason])

    def test_rejects_unscored_result_that_could_be_misread_as_nominal(self):
        finding = ml_finding("session-test", status="insufficient_data", reason_codes=["NO_VALID_SAMPLES"])
        finding["evaluation"]["decision"] = "no_alert"
        with self.assertRaises(FindingContractError):
            validate_finding(finding)

    def test_rejects_unscored_result_without_reason_or_with_score(self):
        missing_reason = ml_finding("session-test", status="not_scored")
        missing_reason["explanation"]["reason_codes"] = []
        with self.assertRaises(FindingContractError):
            validate_finding(missing_reason)

        scored_value = ml_finding("session-test", status="insufficient_data", reason_codes=["MIN_WINDOW_NOT_MET"])
        scored_value["evaluation"]["score"] = 0.5
        with self.assertRaises(FindingContractError):
            validate_finding(scored_value)

    def test_scored_result_requires_session_scoped_evidence(self):
        no_evidence = ml_finding("session-test")
        no_evidence["evidence"]["record_refs"] = []
        with self.assertRaises(FindingContractError):
            validate_finding(no_evidence)

        wrong_session = ml_finding("session-test")
        wrong_session["evidence"]["record_refs"][0]["session_id"] = "other-session"
        with self.assertRaises(FindingContractError):
            validate_finding(wrong_session)

    def test_publishes_ml_result_alongside_rule_finding_and_deduplicates(self):
        session = DashboardSession()
        session.session_id = "session-test"
        session.source_type = "synthetic_replay"
        for frame in load_jsonl(FIXTURE):
            session.ingest_frame(frame)

        rule_finding = session.finding
        blocked_ml = ml_finding(
            session.session_id,
            status="not_scored",
            reason_codes=["PRESSURE_MAPPING_UNVERIFIED"],
        )
        session.publish_finding(blocked_ml)
        session.publish_finding(blocked_ml)

        findings = session.snapshot()["findings"]
        self.assertEqual(len(findings), 2)
        self.assertIn(rule_finding, findings)
        self.assertEqual(sum(item["detector"]["kind"] == "ml" for item in findings), 1)
        self.assertEqual(session.finding, rule_finding)
        self.assertEqual(rule_finding["evaluation"]["status"], "scored")
        ml_result = next(item for item in findings if item["detector"]["kind"] == "ml")
        self.assertEqual(ml_result["evaluation"]["decision"], "undetermined")
        self.assertIsNone(ml_result["evaluation"]["score"])
        self.assertEqual(ml_result["explanation"]["reason_codes"], ["PRESSURE_MAPPING_UNVERIFIED"])

    def test_rejects_finding_from_a_different_session(self):
        session = DashboardSession()
        session.session_id = "active-session"
        session.source_type = "synthetic_replay"
        with self.assertRaises(ValueError):
            session.publish_finding(ml_finding("other-session"))


if __name__ == "__main__":
    unittest.main()
