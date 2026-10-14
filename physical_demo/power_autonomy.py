"""Deterministic synthetic power-anomaly and recovery-policy demonstrator.

This module consumes records already validated by ``TelemetryReceiver``.  It
does not command hardware and does not modify the thermal detector or replay.
"""

from __future__ import annotations

import json
import time
import tracemalloc
from pathlib import Path
from typing import Any

from receiver import TelemetryReceiver, VERIFIED_SENSOR_STATUS


STATES = (
    "MONITORING",
    "WARNING",
    "POLICY_CHECK",
    "ACTION_SIMULATED",
    "VERIFYING",
    "RECOVERED",
    "ESCALATED",
)
WARNING_VOLTAGE_V = 3.50
CRITICAL_VOLTAGE_V = 3.30
RECOVERY_VOLTAGE_V = 3.60
RECOVERY_SAMPLES = 2
ACTION_ID = "simulated_power_mode_reconfiguration"


def _voltage(record: dict[str, Any]) -> float | None:
    value = record.get("voltage_v")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def load_validated_power_records(path: Path) -> tuple[list[dict[str, Any]], TelemetryReceiver]:
    """Load synthetic JSONL through the existing receiver validation path."""
    receiver = TelemetryReceiver()
    for line in path.read_bytes().splitlines():
        if line:
            receiver.parse_line(line, host_monotonic=len(receiver.records))
    return list(receiver.records), receiver


def _record_ref(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "seq": record["seq"],
        "device_time_ms": record["device_time_ms"],
        "voltage_v": record.get("voltage_v"),
        "sensor_status": record.get("sensor_status"),
    }


def run_policy(records: list[dict[str, Any]], *, scenario_id: str, action_authorized: bool = True) -> dict[str, Any]:
    """Run the deterministic policy over validated records and return evidence."""
    state = "MONITORING"
    state_history: list[dict[str, Any]] = [{"state": state, "reason": "Policy initialized"}]
    trigger: dict[str, Any] | None = None
    policy_decision = {"accepted": False, "reason": "No critical trigger observed", "preconditions": {}}
    action: dict[str, Any] = {"id": ACTION_ID, "simulated": True, "issued": False}
    verification_records: list[dict[str, Any]] = []
    consecutive_recovery = 0

    def transition(next_state: str, reason: str) -> None:
        nonlocal state
        state = next_state
        state_history.append({"state": state, "reason": reason})

    for record in records:
        voltage = _voltage(record)
        verified = record.get("sensor_status") == VERIFIED_SENSOR_STATUS and record.get("sensor_valid") is True
        if voltage is None or not verified:
            if state == "VERIFYING":
                transition("ESCALATED", "Verification record was not an acquisition-verified voltage")
            continue

        if state == "MONITORING" and voltage <= WARNING_VOLTAGE_V:
            trigger = _record_ref(record)
            transition("WARNING", f"Voltage {voltage:.2f} V reached warning threshold")

        if state == "WARNING" and voltage <= CRITICAL_VOLTAGE_V:
            transition("POLICY_CHECK", f"Voltage {voltage:.2f} V reached critical threshold")
            preconditions = {
                "measurement_verified": verified,
                "critical_threshold_reached": voltage <= CRITICAL_VOLTAGE_V,
                "simulated_action_authorized": action_authorized,
                "not_already_actioned": not action["issued"],
            }
            policy_decision = {
                "accepted": all(preconditions.values()),
                "reason": "All policy preconditions satisfied" if all(preconditions.values()) else "Policy precondition rejected",
                "preconditions": preconditions,
            }
            if not policy_decision["accepted"]:
                transition("ESCALATED", policy_decision["reason"])
            else:
                action = {
                    "id": ACTION_ID,
                    "simulated": True,
                    "issued": True,
                    "issued_after": _record_ref(record),
                    "description": "Simulated power-mode reconfiguration; no hardware command was sent",
                }
                transition("ACTION_SIMULATED", "Simulated recovery action recorded")
                transition("VERIFYING", "Awaiting subsequent telemetry against recovery criteria")
            continue

        if state == "VERIFYING":
            verification_records.append(_record_ref(record))
            if voltage >= RECOVERY_VOLTAGE_V:
                consecutive_recovery += 1
            else:
                consecutive_recovery = 0
            if consecutive_recovery >= RECOVERY_SAMPLES:
                transition("RECOVERED", "Recovery voltage criterion met for consecutive verified samples")
                break

    if trigger is None:
        final_reason = "No warning or critical voltage trigger observed"
    elif state == "VERIFYING":
        transition("ESCALATED", "Recovery criterion was not met before the scenario ended")
        final_reason = "Recovery criterion was not met"
    elif state == "ESCALATED":
        final_reason = state_history[-1]["reason"]
    elif state == "RECOVERED":
        final_reason = "Verified recovery demonstrated"
    else:
        final_reason = "Scenario ended before policy action"

    return {
        "schema_version": 1,
        "report_type": "synthetic_autonomy_power_evidence",
        "scenario_id": scenario_id,
        "source_type": "synthetic_power_scenario",
        "simulation_notice": "All telemetry, policy decisions and actions in this report are synthetic; no spacecraft hardware was controlled.",
        "configuration": {
            "warning_voltage_v": WARNING_VOLTAGE_V,
            "critical_voltage_v": CRITICAL_VOLTAGE_V,
            "recovery_voltage_v": RECOVERY_VOLTAGE_V,
            "required_consecutive_verified_samples": RECOVERY_SAMPLES,
            "action_id": ACTION_ID,
        },
        "states": list(STATES),
        "state_history": state_history,
        "trigger": trigger,
        "policy_decision": policy_decision,
        "action": action,
        "verification": {
            "criteria": f"voltage_v >= {RECOVERY_VOLTAGE_V:.2f} V for {RECOVERY_SAMPLES} consecutive measurement_verified records",
            "records": verification_records,
            "consecutive_recovery_samples": consecutive_recovery,
            "criteria_met": state == "RECOVERED",
        },
        "final_outcome": {
            "state": state,
            "success": state == "RECOVERED",
            "reason": final_reason,
        },
        "telemetry_records": [_record_ref(record) for record in records],
        "limitations": [
            "Synthetic policy demonstration only; not spacecraft flight software or hardware control.",
            "The receiver validates the existing telemetry envelope; power fields are synthetic extensions for this demonstrator.",
        ],
    }


def run_scenario(path: Path, *, scenario_id: str, action_authorized: bool = True) -> dict[str, Any]:
    started = time.perf_counter()
    tracemalloc.start()
    records, receiver = load_validated_power_records(path)
    report = run_policy(records, scenario_id=scenario_id, action_authorized=action_authorized)
    _, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    report["execution_metrics"] = {
        "measurement_scope": "one local synthetic scenario execution in the Python dashboard process",
        "execution_time_ms": round((time.perf_counter() - started) * 1000.0, 3),
        "peak_traced_memory_bytes": peak_memory,
        "records_processed": len(records),
        "verification_samples_used": len(report["verification"]["records"]),
        "outcome": report["final_outcome"]["state"],
        "evidence_id": f"{scenario_id}:{report['final_outcome']['state']}",
    }
    report["validation"] = {
        "accepted_records": len(records),
        "rejected_records": len(receiver.errors),
        "errors": list(receiver.errors),
        "all_records_measurement_verified": all(
            record.get("sensor_status") == VERIFIED_SENSOR_STATUS and record.get("sensor_valid") is True
            for record in records
        ),
    }
    return report


def report_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
