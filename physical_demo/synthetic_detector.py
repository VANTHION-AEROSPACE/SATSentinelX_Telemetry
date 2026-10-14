"""Explicitly synthetic threshold detector for the hardware-free demonstration."""

from __future__ import annotations

from typing import Any


DETECTOR_ID = "synthetic_temperature_threshold_v1"
DETECTOR_VERSION = "1.0"
THRESHOLD_C = 26.0
BASELINE_RECORDS = 4


def detect(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return one reproducible incident linked to exact validated records."""
    verified = [r for r in records if r.get("sensor_status") == "measurement_verified" and r.get("sensor_valid")]
    anomaly = [r for r in verified if float(r["temperature_c"]) > THRESHOLD_C]
    if not anomaly:
        return None
    baseline = verified[:BASELINE_RECORDS]
    event = anomaly
    observed = [float(r["temperature_c"]) for r in event]
    return {
        "incident_id": "synthetic-thermal-rise-001",
        "source_type": "synthetic_replay",
        "detector": {"id": DETECTOR_ID, "version": DETECTOR_VERSION, "threshold_c": THRESHOLD_C, "rule": "temperature_c > threshold_c"},
        "classification": "synthetic_threshold_breach",
        "severity": "demo",
        "onset_device_time_ms": event[0]["device_time_ms"],
        "end_device_time_ms": event[-1]["device_time_ms"],
        "affected_channels": ["temperature_c"],
        "observed_values_c": observed,
        "baseline_median_c": sum(float(r["temperature_c"]) for r in baseline) / len(baseline) if baseline else None,
        "record_refs": [{"seq": r["seq"], "device_time_ms": r["device_time_ms"], "temperature_c": r["temperature_c"]} for r in event],
        "baseline_record_refs": [{"seq": r["seq"], "device_time_ms": r["device_time_ms"], "temperature_c": r["temperature_c"]} for r in baseline],
        "limitations": ["Synthetic threshold demonstration only; not ESA reproduction, detector-v1 validation, or operational diagnosis."],
    }
