"""Bounded USB-serial JSONL receiver and physical-run acceptance gate."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TextIO

REQUIRED = (
    "schema_version",
    "message_type",
    "device_id",
    "seq",
    "device_time_ms",
    "temperature_c",
    "sensor_valid",
    "sensor_status",
)
MAX_LINE_BYTES = 4096
MIN_TEMPERATURE_C = -40.0
MAX_TEMPERATURE_C = 85.0
MAX_ACCEPTANCE_GAP_SECONDS = 2.0
MIN_ACCEPTANCE_RECORDS = 250
VERIFIED_SENSOR_STATUS = "measurement_verified"
UNVERIFIED_SENSOR_STATUS = "value_present_read_status_unverified"
VALID_SENSOR_STATUSES = {VERIFIED_SENSOR_STATUS, UNVERIFIED_SENSOR_STATUS}
INVALID_SENSOR_STATUSES = {"sensor_init_failed", "sensor_bus_unavailable", "sensor_value_invalid"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _is_open(stream: Any) -> bool:
    if hasattr(stream, "is_open"):
        return bool(stream.is_open)
    if hasattr(stream, "closed"):
        return not bool(stream.closed)
    return True


def read_framed_line(stream: Any, max_bytes: int = MAX_LINE_BYTES) -> tuple[str, bytes | None]:
    """Read one bounded LF-delimited frame from a bytes or text stream.

    Empty reads from an open stream are timeouts. Closed streams are EOF. A
    partial or oversized frame is discarded through its next LF so the next
    frame can still be processed safely.
    """
    buffer = bytearray()
    oversized = False
    while True:
        chunk = stream.read(1)
        if chunk in (b"", "") or chunk is None:
            if oversized:
                return ("oversized_partial", None)
            if buffer:
                return ("partial_timeout" if _is_open(stream) else "eof_partial", None)
            return ("timeout" if _is_open(stream) else "eof", None)
        if isinstance(chunk, str):
            try:
                chunk = chunk.encode("utf-8", errors="strict")
            except UnicodeEncodeError:
                return ("invalid_utf8", None)
        if not isinstance(chunk, (bytes, bytearray)):
            return ("invalid_stream_data", None)
        if b"\n" in chunk:
            before, _, _ = bytes(chunk).partition(b"\n")
            if not oversized:
                buffer.extend(before)
            if oversized or len(buffer) > max_bytes:
                return ("oversized", None)
            return ("line", bytes(buffer))
        if not oversized:
            buffer.extend(chunk)
            if len(buffer) > max_bytes:
                oversized = True


class TelemetryReceiver:
    def __init__(self) -> None:
        self.previous_seq: int | None = None
        self.previous_device_time_ms: int | None = None
        self.previous_host_monotonic: float | None = None
        self.errors: list[str] = []
        self.events: list[str] = []
        self.records: list[dict[str, Any]] = []
        self.max_host_gap_s = 0.0

    def reject(self, reason: str) -> None:
        self.errors.append(reason)

    def note_event(self, event: str) -> None:
        self.events.append(event)

    def parse_line(
        self,
        line: str | bytes,
        *,
        host_utc: str | None = None,
        host_monotonic: float | None = None,
    ) -> dict[str, Any] | None:
        if isinstance(line, bytes):
            if len(line) > MAX_LINE_BYTES:
                self.reject("line_too_long")
                return None
            try:
                line = line.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                self.reject("invalid_utf8")
                return None
        if not isinstance(line, str):
            self.reject("invalid_line_type")
            return None
        if len(line.encode("utf-8", errors="strict")) > MAX_LINE_BYTES:
            self.reject("line_too_long")
            return None
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            self.reject("invalid_json")
            return None
        if not isinstance(obj, dict):
            self.reject("message_not_object")
            return None
        missing = [key for key in REQUIRED if key not in obj]
        if missing:
            self.reject("missing:" + ",".join(missing))
            return None
        if type(obj["schema_version"]) is not int or obj["schema_version"] != 1 or obj["message_type"] != "telemetry":
            self.reject("unsupported_schema_or_message_type")
            return None
        if not isinstance(obj["device_id"], str) or not obj["device_id"]:
            self.reject("invalid_device_id")
            return None
        if type(obj["seq"]) is not int or obj["seq"] < 0:
            self.reject("invalid_seq")
            return None
        if type(obj["device_time_ms"]) is not int or obj["device_time_ms"] < 0:
            self.reject("invalid_device_time_ms")
            return None
        if not isinstance(obj["sensor_valid"], bool):
            self.reject("invalid_sensor_valid")
            return None
        if not isinstance(obj["sensor_status"], str):
            self.reject("invalid_sensor_status")
            return None
        temperature = obj["temperature_c"]
        if obj["sensor_valid"]:
            if obj["sensor_status"] not in VALID_SENSOR_STATUSES:
                self.reject("valid_status_mismatch")
                return None
            if isinstance(temperature, bool) or not isinstance(temperature, (int, float)):
                self.reject("invalid_temperature")
                return None
            if not MIN_TEMPERATURE_C <= float(temperature) <= MAX_TEMPERATURE_C:
                self.reject("temperature_out_of_range")
                return None
        else:
            if obj["sensor_status"] not in INVALID_SENSOR_STATUSES or temperature is not None:
                self.reject("invalid_sensor_invalid_temperature")
                return None

        if self.previous_seq is None:
            sequence_status = "first"
        elif obj["seq"] == self.previous_seq + 1:
            sequence_status = "contiguous"
        elif obj["seq"] == self.previous_seq:
            sequence_status = "duplicate"
        elif obj["seq"] > self.previous_seq:
            sequence_status = "gap"
        else:
            sequence_status = "out_of_order"

        if self.previous_device_time_ms is None:
            device_time_status = "first"
        elif obj["device_time_ms"] > self.previous_device_time_ms:
            device_time_status = "increasing"
        elif obj["device_time_ms"] == self.previous_device_time_ms:
            device_time_status = "equal"
        else:
            self.reject("device_time_not_monotonic")
            return None

        record = dict(obj)
        received_monotonic = host_monotonic if host_monotonic is not None else time.monotonic()
        host_gap_s = 0.0 if self.previous_host_monotonic is None else max(0.0, received_monotonic - self.previous_host_monotonic)
        self.max_host_gap_s = max(self.max_host_gap_s, host_gap_s)
        record["host_received_utc"] = host_utc or utc_now()
        record["host_received_monotonic_s"] = received_monotonic
        record["host_gap_s"] = host_gap_s
        record["sequence_status"] = sequence_status
        record["device_time_status"] = device_time_status
        self.previous_seq = obj["seq"]
        self.previous_device_time_ms = obj["device_time_ms"]
        self.previous_host_monotonic = received_monotonic
        self.records.append(record)
        return record

    def acceptance_summary(self, *, ended_reason: str, elapsed_seconds: float) -> dict[str, Any]:
        schema_valid = len(self.records)
        verified_sensor = sum(1 for record in self.records if record["sensor_valid"] and record["sensor_status"] == VERIFIED_SENSOR_STATUS)
        unverified_sensor = sum(1 for record in self.records if record["sensor_status"] == UNVERIFIED_SENSOR_STATUS)
        invalid_sensor = sum(1 for record in self.records if not record["sensor_valid"])
        sequence_ok = bool(self.records) and self.records[0]["seq"] == 0 and all(
            record["sequence_status"] in {"first", "contiguous"} for record in self.records
        )
        device_time_ok = bool(self.records) and all(
            record["device_time_status"] in {"first", "increasing"} for record in self.records
        )
        duration_ok = elapsed_seconds >= 60.0
        reasons: list[str] = []
        if ended_reason != "duration":
            reasons.append(ended_reason)
        if not duration_ok:
            reasons.append("run_shorter_than_60_seconds")
        if verified_sensor < MIN_ACCEPTANCE_RECORDS:
            reasons.append("fewer_than_250_valid_telemetry_records")
        if unverified_sensor:
            reasons.append("acquisition_unverified_present")
        if invalid_sensor:
            reasons.append("sensor_invalid_records_present")
        if self.errors:
            reasons.append("validation_errors_present")
        if self.max_host_gap_s > MAX_ACCEPTANCE_GAP_SECONDS:
            reasons.append("telemetry_gap_over_2_seconds")
        if not sequence_ok:
            reasons.append("sequence_order_invalid")
        if not device_time_ok:
            reasons.append("device_time_not_strictly_increasing")
        status = "PASS" if not reasons else ("INCOMPLETE_" + ended_reason.upper() if ended_reason != "duration" else "FAIL_ACCEPTANCE")
        return {
            "status": status,
            "ended_reason": ended_reason,
            "elapsed_seconds": elapsed_seconds,
            "schema_valid_records": schema_valid,
            "valid_telemetry_records": verified_sensor,
            "verified_telemetry_records": verified_sensor,
            "unverified_telemetry_records": unverified_sensor,
            "sensor_invalid_records": invalid_sensor,
            "rejected_records": len(self.errors),
            "errors": list(self.errors),
            "events": list(self.events),
            "failure_reasons": reasons,
            "max_host_gap_s": self.max_host_gap_s,
            "sequence_order_ok": sequence_ok,
            "device_time_strictly_increasing": device_time_ok,
            "duration_ok": duration_ok,
        }


def receive_stream(
    stream: Any,
    output: TextIO,
    receiver: TelemetryReceiver,
    *,
    duration: float = 60.0,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    started = clock()
    while clock() - started < duration:
        try:
            kind, frame = read_framed_line(stream)
        except Exception as exc:
            receiver.note_event("serial_disconnect:" + type(exc).__name__)
            return {"ended_reason": "serial_disconnect", "elapsed_seconds": clock() - started}
        if kind == "timeout":
            receiver.note_event("serial_timeout")
            continue
        if kind in {"eof", "eof_partial"}:
            receiver.note_event(kind)
            return {"ended_reason": "eof", "elapsed_seconds": clock() - started}
        if kind != "line":
            receiver.reject(kind)
            continue
        record = receiver.parse_line(frame or b"", host_monotonic=clock())
        if record is not None:
            output.write(json.dumps(record, separators=(",", ":"), allow_nan=False) + "\n")
            output.flush()
    return {"ended_reason": "duration", "elapsed_seconds": clock() - started}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--baud", type=int, default=115200)
    args = parser.parse_args()
    report_path = args.report or args.output.with_suffix(".acceptance.json")

    try:
        import serial  # type: ignore
    except ImportError:
        print("pyserial is required; install physical_demo/requirements.txt", file=sys.stderr)
        return 2

    receiver = TelemetryReceiver()
    started_utc = utc_now()
    try:
        port = serial.Serial(args.port, args.baud, timeout=1)
    except Exception as exc:
        receiver.note_event("serial_open_error:" + type(exc).__name__)
        run = {"ended_reason": "serial_open_error", "elapsed_seconds": 0.0}
    else:
        try:
            with port, args.output.open("w", encoding="utf-8", newline="\n") as output:
                run = receive_stream(port, output, receiver, duration=args.duration)
        except Exception as exc:
            receiver.note_event("serial_runtime_error:" + type(exc).__name__)
            run = {"ended_reason": "serial_runtime_error", "elapsed_seconds": 0.0}

    summary = receiver.acceptance_summary(**run)
    summary.update({"started_utc": started_utc, "ended_utc": utc_now(), "output": str(args.output), "report": str(report_path)})
    report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, separators=(",", ":")))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
