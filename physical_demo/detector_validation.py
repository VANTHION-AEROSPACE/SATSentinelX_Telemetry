"""Deterministic, offline baseline evaluation for the synthetic detector.

The detector is intentionally imported unchanged.  Scenarios are evaluated
through the existing TelemetryReceiver, and ground truth is defined as
inclusive sequence intervals.  Sample metrics count only accepted,
measurement-verified records; scenario metrics count one event per scenario.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from receiver import MAX_ACCEPTANCE_GAP_SECONDS, TelemetryReceiver
from synthetic_detector import THRESHOLD_C, detect


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    description: str
    records: tuple[dict[str, Any], ...]
    ground_truth_intervals: tuple[tuple[int, int], ...]
    ground_truth_onset_ms: int | None
    expected_health_faults: tuple[str, ...] = ()
    host_times: tuple[float, ...] | None = None


def _record(seq: int, temperature: float, *, device_time_ms: int | None = None) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "message_type": "telemetry",
        "device_id": "synthetic-validation",
        "seq": seq,
        "device_time_ms": seq * 500 if device_time_ms is None else device_time_ms,
        "temperature_c": temperature,
        "sensor_valid": True,
        "sensor_status": "measurement_verified",
    }


def scenario_suite() -> tuple[Scenario, ...]:
    """Return the fixed canonical-fixture plus six synthetic-case suite."""
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "synthetic_anomaly.jsonl"
    fixture_records = tuple(json.loads(line) for line in fixture_path.read_text(encoding="utf-8").splitlines() if line)
    return (
        Scenario("canonical_replay_fixture", "Existing deterministic thermal replay fixture", fixture_records, ((8, 11),), 4000),
        Scenario("normal", "Nominal operation", tuple(_record(i, value) for i, value in enumerate((22.0, 22.1, 22.0, 22.2))), (), None),
        Scenario("detectable_anomaly", "Verified temperature breach", tuple(_record(i, value) for i, value in enumerate((22.0, 22.1, 27.0, 27.5, 22.0))), ((2, 3),), 1000),
        Scenario("threshold_boundary", "Values equal to or below the strict threshold", tuple(_record(i, value) for i, value in enumerate((25.9, THRESHOLD_C, 25.99))), (), None),
        Scenario("missing_data", "Ground-truth breach has no usable temperature record", (
            _record(0, 22.0), _record(1, 22.1), _record(2, 22.0),
            {"schema_version": 1, "message_type": "telemetry", "device_id": "synthetic-validation", "seq": 3, "device_time_ms": 1500, "sensor_valid": True, "sensor_status": "measurement_verified"},
            _record(4, 22.0),
        ), ((3, 3),), 1500, ("missing_data",)),
        Scenario("invalid_sensor", "Ground-truth breach is explicitly sensor-invalid", (
            _record(0, 22.0), _record(1, 22.1),
            {**_record(2, 22.0), "temperature_c": None, "sensor_valid": False, "sensor_status": "sensor_bus_unavailable"},
            _record(3, 22.0),
        ), ((2, 2),), 1000, ("invalid_sensor",)),
        Scenario("recovery_to_normal", "Breach followed by verified return to nominal", tuple(_record(i, value) for i, value in enumerate((22.0, 22.1, 29.0, 29.2, 22.2, 22.0))), ((2, 3),), 1000),
        Scenario("stale_data", "Verified records separated by a stale host-data gap", tuple(_record(i, value) for i, value in enumerate((22.0, 22.1))), (), None, ("stale_data",), (0.0, MAX_ACCEPTANCE_GAP_SECONDS + 1.0)),
    )


def _truth_sequences(scenario: Scenario) -> set[int]:
    return {seq for start, end in scenario.ground_truth_intervals for seq in range(start, end + 1)}


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _health_metrics(expected: set[str], observed: set[str]) -> dict[str, int]:
    return {
        "tp": len(expected & observed),
        "fp": len(observed - expected),
        "fn": len(expected - observed),
        "tn": len({"missing_data", "invalid_sensor", "stale_data"} - expected - observed),
    }


def evaluate_scenario(scenario: Scenario) -> dict[str, Any]:
    receiver = TelemetryReceiver()
    for index, payload in enumerate(scenario.records):
        host_time = scenario.host_times[index] if scenario.host_times is not None else float(index)
        receiver.parse_line(json.dumps(payload, separators=(",", ":")).encode(), host_monotonic=host_time)
    incident = detect(receiver.records)
    truth = _truth_sequences(scenario)
    predicted = {int(ref["seq"]) for ref in incident["record_refs"]} if incident else set()
    usable = {
        int(record["seq"])
        for record in receiver.records
        if record["sensor_valid"] and record["sensor_status"] == "measurement_verified"
    }
    sample_truth = truth & usable
    sample_predicted = predicted & usable
    tp = len(sample_truth & sample_predicted)
    fp = len(sample_predicted - sample_truth)
    fn = len(sample_truth - sample_predicted)
    tn = len(usable - sample_truth - sample_predicted)
    expected_event = bool(scenario.ground_truth_intervals)
    detected_event = incident is not None
    event_tp = int(expected_event and detected_event)
    event_fp = int(not expected_event and detected_event)
    event_fn = int(expected_event and not detected_event)
    event_tn = int(not expected_event and not detected_event)
    evidence_complete = None
    if incident is not None:
        referenced = {int(ref["seq"]) for ref in incident["record_refs"]}
        source = {int(record["seq"]) for record in incident.get("source_records", [])}
        evidence_complete = {"incident_id", "detector", "source_type", "record_refs"}.issubset(incident) and referenced <= source
    delay_ms = None
    if detected_event and scenario.ground_truth_onset_ms is not None:
        delay_ms = incident["onset_device_time_ms"] - scenario.ground_truth_onset_ms
    observed_health: set[str] = set()
    if any(error.startswith("missing:") for error in receiver.errors):
        observed_health.add("missing_data")
    if any(not record["sensor_valid"] for record in receiver.records):
        observed_health.add("invalid_sensor")
    if receiver.max_host_gap_s > MAX_ACCEPTANCE_GAP_SECONDS:
        observed_health.add("stale_data")
    if expected_event and detected_event:
        event_classification = "detected_verified_anomaly"
    elif expected_event and "missing_data" in scenario.expected_health_faults:
        event_classification = "unobservable_missing_measurement"
    elif expected_event and "invalid_sensor" in scenario.expected_health_faults:
        event_classification = "unobservable_invalid_measurement"
    else:
        event_classification = "no_ground_truth_event"
    ground_truth_records = [payload for payload in scenario.records if payload.get("seq") in truth]
    return {
        "scenario_id": scenario.scenario_id,
        "source_type": "synthetic_validation",
        "description": scenario.description,
        "input_record_count": len(scenario.records),
        "accepted_record_count": len(receiver.records),
        "validation_errors": list(receiver.errors),
        "ground_truth_intervals": [{"start_seq": start, "end_seq": end} for start, end in scenario.ground_truth_intervals],
        "ground_truth_records": ground_truth_records,
        "event_classification": event_classification,
        "detected": detected_event,
        "incident_id": incident["incident_id"] if incident else None,
        "sample_metrics": {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "excluded_ground_truth_samples": len(truth - usable)},
        "event_metrics": {"tp": event_tp, "fp": event_fp, "fn": event_fn, "tn": event_tn},
        "detection_delay_ms": delay_ms,
        "evidence_complete": evidence_complete,
        "expected_health_faults": list(scenario.expected_health_faults),
        "observed_health_faults": sorted(observed_health),
        "health_metrics": _health_metrics(set(scenario.expected_health_faults), observed_health),
    }


def run_validation_suite() -> dict[str, Any]:
    cases = [evaluate_scenario(scenario) for scenario in scenario_suite()]
    detector_cases = [case for case in cases if case["scenario_id"] != "stale_data"]
    sample = {key: sum(case["sample_metrics"][key] for case in detector_cases) for key in ("tp", "fp", "fn", "tn")}
    events = {key: sum(case["event_metrics"][key] for case in detector_cases) for key in ("tp", "fp", "fn", "tn")}
    health = {key: sum(case["health_metrics"][key] for case in cases) for key in ("tp", "fp", "fn", "tn")}
    delays = [case["detection_delay_ms"] for case in detector_cases if case["detection_delay_ms"] is not None]
    return {
        "validation_version": "1.0",
        "detector": {"id": "synthetic_temperature_threshold_v1", "threshold_c": THRESHOLD_C, "rule": "temperature_c > threshold_c"},
        "ground_truth_definition": "inclusive sequence intervals; only accepted verified records enter sample metrics; one event per detector scenario enters event metrics; stale_data is health-only",
        "cases": cases,
        "aggregate": {
            "sample_metrics": {**sample, "precision": _ratio(sample["tp"], sample["tp"] + sample["fp"]), "recall": _ratio(sample["tp"], sample["tp"] + sample["fn"]), "false_positive_rate": _ratio(sample["fp"], sample["fp"] + sample["tn"])},
            "event_metrics": {**events, "precision": _ratio(events["tp"], events["tp"] + events["fp"]), "recall": _ratio(events["tp"], events["tp"] + events["fn"]), "false_positive_rate": _ratio(events["fp"], events["fp"] + events["tn"])},
            "telemetry_health_metrics": {**health, "precision": _ratio(health["tp"], health["tp"] + health["fp"]), "recall": _ratio(health["tp"], health["tp"] + health["fn"]), "false_positive_rate": _ratio(health["fp"], health["fp"] + health["tn"])},
            "detection_delay_ms": {"mean_detected_event_delay": sum(delays) / len(delays) if delays else None, "detected_event_count": len(delays)},
            "evidence_complete_detected_cases": sum(case["evidence_complete"] is True for case in detector_cases if case["detected"]),
        },
        "limitations": ["Synthetic correlated sequences are not independent experiments", "Missing and invalid anomaly samples are excluded from sample metrics and remain visible as event-level misses", "Not physical validation, Detector v1 validation, ESA reproduction, or flight qualification"],
    }


if __name__ == "__main__":
    print(json.dumps(run_validation_suite(), indent=2, sort_keys=True))
