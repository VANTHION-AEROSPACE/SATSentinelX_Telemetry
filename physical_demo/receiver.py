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


def _frame_shape(line: str | bytes) -> str:
    """Return bounded, payload-safe diagnostics for one rejected frame."""
    if isinstance(line, bytes):
        raw = line
    else:
        raw = line.encode("utf-8", errors="replace")
    prefix = raw[:16].hex()
    return f"bytes={len(raw)}:prefix_hex={prefix}"


class BufferedLFReader:
    """Read one LF-delimited frame at a time from a bounded byte stream."""

    def __init__(self, stream: Any, *, max_bytes: int = MAX_LINE_BYTES, read_size: int = MAX_LINE_BYTES) -> None:
        if max_bytes < 1 or read_size < 1:
            raise ValueError("max_bytes and read_size must be positive")
        self.stream = stream
        self.max_bytes = max_bytes
        self.read_size = read_size
        self._buffer = bytearray()
        self._oversized = False
        self._discarded_bytes = 0
        self._discarding_until_lf = False

    def _diagnostic(self, diagnostics: list[str] | None, value: str) -> None:
        if diagnostics is not None:
            diagnostics.append(value)

    def _read_chunk(self) -> tuple[str, bytes | None]:
        chunk = self.stream.read(self.read_size)
        if chunk in (b"", "") or chunk is None:
            return ("empty", None)
        if isinstance(chunk, str):
            try:
                chunk = chunk.encode("utf-8", errors="strict")
            except UnicodeEncodeError:
                return ("invalid_stream_encoding", None)
        if not isinstance(chunk, (bytes, bytearray)):
            return ("invalid_stream_data", None)
        return ("chunk", bytes(chunk))

    def _consume_until_lf(self) -> bool:
        """Discard the current damaged frame but retain bytes after its LF."""
        while True:
            kind, chunk = self._read_chunk()
            if kind != "chunk":
                return False
            index = chunk.find(b"\n")
            if index >= 0:
                self._buffer.extend(chunk[index + 1:])
                return True

    def _finish_buffered_frame(self, diagnostics: list[str] | None) -> tuple[str, bytes | None] | None:
        index = self._buffer.find(b"\n")
        if index < 0:
            return None
        frame = bytes(self._buffer[:index])
        del self._buffer[:index + 1]
        if self._oversized or len(frame) > self.max_bytes:
            self._diagnostic(diagnostics, f"bytes_at_least={self.max_bytes + 1}")
            self._oversized = False
            self._discarded_bytes = 0
            return ("oversized", None)
        return ("line", frame)

    def read_line(self, diagnostics: list[str] | None = None) -> tuple[str, bytes | None]:
        while True:
            if self._discarding_until_lf:
                if self._consume_until_lf():
                    self._discarding_until_lf = False
                    continue
                return ("timeout" if _is_open(self.stream) else "eof", None)

            finished = self._finish_buffered_frame(diagnostics)
            if finished is not None:
                return finished

            kind, chunk = self._read_chunk()
            if kind == "invalid_stream_encoding":
                self._diagnostic(diagnostics, "invalid_utf8")
                return ("invalid_utf8", None)
            if kind == "invalid_stream_data":
                self._diagnostic(diagnostics, "unexpected_stream_type")
                return ("invalid_stream_data", None)
            if kind == "empty":
                if self._oversized:
                    self._diagnostic(diagnostics, f"bytes_at_least={self._discarded_bytes}")
                    open_at_timeout = _is_open(self.stream)
                    if open_at_timeout:
                        if not self._consume_until_lf():
                            self._discarding_until_lf = True
                    self._oversized = False
                    self._discarded_bytes = 0
                    return ("oversized_partial", None)
                if self._buffer:
                    self._diagnostic(diagnostics, f"partial_bytes={len(self._buffer)}")
                    if _is_open(self.stream):
                        # A read timeout is not a frame boundary. Preserve
                        # partial bytes until more data arrives or EOF occurs.
                        return ("timeout", None)
                    return ("eof_partial", None)
                return ("timeout" if _is_open(self.stream) else "eof", None)

            assert chunk is not None
            if self._oversized:
                index = chunk.find(b"\n")
                if index >= 0:
                    self._buffer.extend(chunk[index + 1:])
                    self._oversized = False
                    self._discarded_bytes = 0
                    self._diagnostic(diagnostics, f"bytes_at_least={self.max_bytes + 1}")
                    return ("oversized", None)
                self._discarded_bytes = min(self.max_bytes + 1, self._discarded_bytes + len(chunk))
                continue

            self._buffer.extend(chunk)
            if len(self._buffer) > self.max_bytes and b"\n" not in self._buffer:
                self._oversized = True
                self._discarded_bytes = self.max_bytes + 1
                self._buffer.clear()


def read_framed_line(
    stream: Any,
    max_bytes: int = MAX_LINE_BYTES,
    diagnostics: list[str] | None = None,
) -> tuple[str, bytes | None]:
    """Read one bounded LF-delimited frame from a bytes or text stream.

    Empty reads from an open stream are timeouts. Closed streams are EOF. A
    partial or oversized frame is discarded through its next LF so the next
    frame can still be processed safely.
    """
    buffer = bytearray()
    oversized = False
    discarded_bytes = 0

    def diagnostic(value: str) -> None:
        if diagnostics is not None:
            diagnostics.append(value)

    def discard_until_lf() -> None:
        """Resynchronize after a timed-out frame without buffering payload."""
        while True:
            remainder = stream.read(1)
            if remainder in (b"", "") or remainder is None:
                return
            if isinstance(remainder, str):
                remainder = remainder.encode("utf-8", errors="replace")
            if isinstance(remainder, (bytes, bytearray)) and b"\n" in remainder:
                return

    while True:
        chunk = stream.read(1)
        if chunk in (b"", "") or chunk is None:
            if oversized:
                diagnostic(f"bytes_at_least={discarded_bytes}")
                open_at_timeout = _is_open(stream)
                if open_at_timeout:
                    discard_until_lf()
                return ("oversized_partial", None)
            if buffer:
                diagnostic(f"partial_bytes={len(buffer)}")
                open_at_timeout = _is_open(stream)
                if open_at_timeout:
                    discard_until_lf()
                return ("partial_timeout" if open_at_timeout else "eof_partial", None)
            return ("timeout" if _is_open(stream) else "eof", None)
        if isinstance(chunk, str):
            try:
                chunk = chunk.encode("utf-8", errors="strict")
            except UnicodeEncodeError:
                diagnostic("invalid_utf8")
                return ("invalid_utf8", None)
        if not isinstance(chunk, (bytes, bytearray)):
            diagnostic("unexpected_stream_type")
            return ("invalid_stream_data", None)
        if b"\n" in chunk:
            before, _, _ = bytes(chunk).partition(b"\n")
            if not oversized:
                buffer.extend(before)
            if oversized or len(buffer) > max_bytes:
                diagnostic(f"bytes_at_least={max_bytes + 1}")
                return ("oversized", None)
            return ("line", bytes(buffer))
        if not oversized:
            buffer.extend(chunk)
            if len(buffer) > max_bytes:
                oversized = True
                discarded_bytes = max_bytes + 1
        else:
            discarded_bytes = min(max_bytes + 1, discarded_bytes + len(chunk))


class TelemetryReceiver:
    def __init__(self) -> None:
        self.previous_seq: int | None = None
        self.previous_device_time_ms: int | None = None
        self.previous_host_monotonic: float | None = None
        self.errors: list[str] = []
        self.events: list[str] = []
        self.records: list[dict[str, Any]] = []
        self.max_host_gap_s = 0.0
        self.run_end_gap_s = 0.0

    def reject(self, reason: str) -> None:
        self.errors.append(reason)

    def note_event(self, event: str) -> None:
        self.events.append(event)

    def note_run_end(self, end_monotonic: float) -> None:
        """Record silence between the last accepted record and run end."""
        if self.previous_host_monotonic is not None:
            self.run_end_gap_s = max(0.0, end_monotonic - self.previous_host_monotonic)

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
                self.note_event("rejected:invalid_utf8:" + _frame_shape(line))
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
            self.note_event("rejected:invalid_json:" + _frame_shape(line))
            return None
        if not isinstance(obj, dict):
            self.reject("message_not_object")
            return None
        if obj == {"message": "BMP280_READY", "chip_id": 88}:
            self.note_event("startup_status:BMP280_READY")
            return None
        if obj == {"message": "BMP280_INIT_FAILED"}:
            self.note_event("startup_status:BMP280_INIT_FAILED")
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
        # A capture may attach to an already-running device. Requiring the first
        # captured sequence to be zero confuses capture startup with stream integrity.
        # Validate continuity within the captured window; expose the starting-at-zero
        # property separately for runs that explicitly test device boot behavior.
        sequence_contiguous = bool(self.records) and all(
            record["sequence_status"] in {"first", "contiguous"} for record in self.records
        )
        sequence_starts_at_zero = bool(self.records) and self.records[0]["seq"] == 0
        sequence_ok = sequence_contiguous
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
        max_gap_s = max(self.max_host_gap_s, self.run_end_gap_s)
        if max_gap_s > MAX_ACCEPTANCE_GAP_SECONDS:
            reasons.append("telemetry_gap_over_2_seconds")
        if "serial_timeout" in self.events:
            reasons.append("serial_timeout_present")
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
            "max_host_gap_s": max_gap_s,
            "sequence_order_ok": sequence_ok,
            "sequence_contiguous": sequence_contiguous,
            "sequence_starts_at_zero": sequence_starts_at_zero,
            "device_time_strictly_increasing": device_time_ok,
            "duration_ok": duration_ok,
        }


class RawTeeStream:
    """Record exact bytes returned by the serial API without changing them."""

    def __init__(self, stream: Any, raw_output: Any) -> None:
        self._stream = stream
        self._raw_output = raw_output
        self._started = time.monotonic()
        self._total_bytes = 0
        self.trace: list[dict[str, Any]] = []

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)

    def read(self, size: int = -1) -> Any:
        data = self._stream.read(size)
        raw = bytes(data) if isinstance(data, (bytes, bytearray, memoryview)) else b""
        before = self._total_bytes
        if raw:
            self._raw_output.write(raw)
            self._raw_output.flush()
            self._total_bytes += len(raw)
        self.trace.append({
            "read_index": len(self.trace) + 1,
            "monotonic_elapsed_seconds": round(time.monotonic() - self._started, 6),
            "requested_bytes": size,
            "returned_bytes": len(raw),
            "captured_bytes": len(raw),
            "start_offset": before,
            "cumulative_captured_bytes": self._total_bytes,
            "first_8_hex": raw[:8].hex(),
            "last_8_hex": raw[-8:].hex(),
        })
        return data


def receive_stream(
    stream: Any,
    output: TextIO,
    receiver: TelemetryReceiver,
    *,
    duration: float = 60.0,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    started = clock()
    framer = BufferedLFReader(stream)

    def finish(ended_reason: str) -> dict[str, Any]:
        ended = clock()
        receiver.note_run_end(ended)
        return {"ended_reason": ended_reason, "elapsed_seconds": ended - started}

    while clock() - started < duration:
        try:
            framing_diagnostics: list[str] = []
            kind, frame = framer.read_line(diagnostics=framing_diagnostics)
        except Exception as exc:
            receiver.note_event("serial_disconnect:" + type(exc).__name__)
            return finish("serial_disconnect")
        if kind == "timeout":
            receiver.note_event("serial_timeout")
            continue
        if kind in {"eof", "eof_partial"}:
            suffix = ":" + ":".join(framing_diagnostics) if framing_diagnostics else ""
            receiver.note_event(kind + suffix)
            return finish("eof")
        if kind != "line":
            suffix = ":" + ":".join(framing_diagnostics) if framing_diagnostics else ""
            receiver.note_event("framing:" + kind + suffix)
            receiver.reject(kind)
            continue
        record = receiver.parse_line(frame or b"", host_monotonic=clock())
        if record is not None:
            output.write(json.dumps(record, separators=(",", ":"), allow_nan=False) + "\n")
            output.flush()
    return finish("duration")


def open_serial_port(serial_module: Any, port_name: str, baud: int, timeout: float = 1) -> Any:
    """Configure modem-control lines before opening the USB serial port."""
    port = serial_module.Serial(port=None, baudrate=baud, timeout=timeout)
    port.port = port_name
    try:
        port.dtr = False
    except Exception:
        pass
    try:
        port.rts = False
    except Exception:
        pass
    port.open()
    return port


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--baud", type=int, default=115200)
    args = parser.parse_args()
    report_path = args.report or args.output.with_suffix(".acceptance.json")
    raw_path = args.output.with_suffix(".raw.bin")
    trace_path = args.output.with_suffix(".raw-trace.json")

    try:
        import serial  # type: ignore
    except ImportError:
        print("pyserial is required; install physical_demo/requirements.txt", file=sys.stderr)
        return 2

    receiver = TelemetryReceiver()
    started_utc = utc_now()
    try:
        port = open_serial_port(serial, args.port, args.baud, timeout=1)
    except Exception as exc:
        receiver.note_event("serial_open_error:" + type(exc).__name__)
        run = {"ended_reason": "serial_open_error", "elapsed_seconds": 0.0}
    else:
        tee = None
        try:
            with port, args.output.open("w", encoding="utf-8", newline="\n") as output, raw_path.open("wb") as raw_output:
                tee = RawTeeStream(port, raw_output)
                run = receive_stream(tee, output, receiver, duration=args.duration)
        except Exception as exc:
            receiver.note_event("serial_runtime_error:" + type(exc).__name__)
            run = {"ended_reason": "serial_runtime_error", "elapsed_seconds": 0.0}
        finally:
            if tee is not None:
                try:
                    trace_path.write_text(json.dumps(tee.trace, indent=2), encoding="utf-8")
                except Exception as exc:
                    receiver.note_event("raw_trace_write_error:" + type(exc).__name__)

    summary = receiver.acceptance_summary(**run)
    summary.update({"started_utc": started_utc, "ended_utc": utc_now(), "output": str(args.output), "report": str(report_path)})
    if raw_path.is_file():
        summary["raw_output"] = str(raw_path)
    if trace_path.is_file():
        summary["raw_trace"] = str(trace_path)
    report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, separators=(",", ":")))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
