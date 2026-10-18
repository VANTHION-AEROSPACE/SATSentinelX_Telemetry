"""Regression tests for separating capture continuity from boot sequence zero."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Make the sibling physical_demo/receiver.py importable when pytest is run
# from the repository root or directly against physical_demo/tests.
PHYSICAL_DEMO = Path(__file__).resolve().parents[1]
if str(PHYSICAL_DEMO) not in sys.path:
    sys.path.insert(0, str(PHYSICAL_DEMO))

from receiver import TelemetryReceiver  # noqa: E402


def _summary_for_sequences(sequences: list[int]) -> dict:
    receiver = TelemetryReceiver()
    for index, seq in enumerate(sequences):
        payload = {
            "schema_version": 1,
            "message_type": "telemetry",
            "device_id": "esp32-bmp280-01",
            "seq": seq,
            "device_time_ms": index * 202,
            "temperature_c": 33.0,
            "pressure_hpa": 994.7,
            "sensor_valid": True,
            "sensor_status": "measurement_verified",
        }
        record = receiver.parse_line(
            json.dumps(payload),
            host_monotonic=index * 0.202,
            host_utc="2026-10-18T10:00:00.000Z",
        )
        assert record is not None
    return receiver.acceptance_summary(ended_reason="duration", elapsed_seconds=60.609)


def test_contiguous_midstream_capture_passes_without_claiming_boot_from_zero() -> None:
    sequences = list(range(21110, 21110 + 296))

    summary = _summary_for_sequences(sequences)

    assert summary["status"] == "PASS"
    assert summary["sequence_contiguous"] is True
    assert summary["sequence_order_ok"] is True
    assert summary["sequence_starts_at_zero"] is False
    assert summary["failure_reasons"] == []


def test_actual_sequence_gap_still_fails_acceptance() -> None:
    # One missing sequence inside a 296-record capture must remain a failure.
    sequences = list(range(100, 248)) + list(range(249, 397))
    assert len(sequences) == 296

    summary = _summary_for_sequences(sequences)

    assert summary["status"] == "FAIL_ACCEPTANCE"
    assert summary["sequence_contiguous"] is False
    assert summary["sequence_order_ok"] is False
    assert "sequence_order_invalid" in summary["failure_reasons"]
