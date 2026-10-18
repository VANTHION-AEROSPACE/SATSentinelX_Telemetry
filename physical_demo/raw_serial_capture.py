"""Bounded raw serial capture and offline framing comparison.

Capture mode reads bytes only with ``Serial.read(4096)``.  It never consults
``in_waiting``, writes to the port, or deliberately toggles modem control
signals.  The binary capture is the authoritative evidence; JSON metadata and
analysis are derived from it after the port is closed.

This is a diagnostic, not an acceptance test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

DEFAULT_BAUD = 115200
DEFAULT_DURATION = 15.0
DEFAULT_TIMEOUT = 0.1
READ_SIZE = 4096
MAX_CAPTURE_BYTES = 1_000_000
MAX_TRACE_ENTRIES = 10_000
MAX_FRAME_SAMPLES = 50
PREVIEW_BYTES = 16


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _shape(raw: bytes) -> dict[str, Any]:
    return {
        "byte_length": len(raw),
        "prefix_hex": raw[:PREVIEW_BYTES].hex(),
        "suffix_hex": raw[-PREVIEW_BYTES:].hex() if raw else "",
    }


def split_lf_frames(raw: bytes) -> tuple[list[bytes], bytes]:
    """Return exact LF-delimited frames and an un-delimited trailing suffix."""
    frames: list[bytes] = []
    start = 0
    while True:
        end = raw.find(b"\n", start)
        if end < 0:
            return frames, raw[start:]
        frames.append(raw[start:end])
        start = end + 1


def analyze_raw_bytes(raw: bytes, *, max_frame_bytes: int = 65_536) -> dict[str, Any]:
    """Classify exact raw LF frames without changing their bytes."""
    try:
        from .serial_diagnostic import FrameAnalyzer
    except ImportError:  # direct execution from physical_demo
        from serial_diagnostic import FrameAnalyzer

    frames, trailing = split_lf_frames(raw)
    analyzer = FrameAnalyzer(max_frame_bytes=max_frame_bytes, max_samples=MAX_FRAME_SAMPLES)
    analyzer.feed(raw)
    report = analyzer.finalize()
    report.update({
        "raw_frame_samples": [_shape(frame) for frame in frames[:MAX_FRAME_SAMPLES]],
        "raw_frame_samples_truncated": len(frames) > MAX_FRAME_SAMPLES,
        "trailing_partial_shape": _shape(trailing) if trailing else None,
    })
    return report


class _ReplayStream:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw
        self.position = 0
        self.is_open = True

    def read(self, size: int) -> bytes:
        if self.position >= len(self.raw):
            self.is_open = False
            return b""
        chunk = self.raw[self.position:self.position + size]
        self.position += len(chunk)
        return chunk


def replay_through_buffered_reader(raw: bytes, *, max_line_bytes: int = 4096) -> dict[str, Any]:
    """Replay bytes offline through the existing production BufferedLFReader."""
    try:
        from .receiver import BufferedLFReader
    except ImportError:  # direct execution from physical_demo
        from receiver import BufferedLFReader

    raw_frames, trailing = split_lf_frames(raw)
    reader = BufferedLFReader(_ReplayStream(raw), max_bytes=max_line_bytes)
    returned: list[bytes] = []
    rejected: list[dict[str, Any]] = []
    while True:
        kind, frame = reader.read_line()
        if kind == "line":
            returned.append(frame or b"")
        elif kind in {"eof", "eof_partial"}:
            break
        elif kind == "timeout":
            continue
        else:
            rejected.append({"kind": kind, **_shape(frame or b"")})

    mismatches: list[dict[str, Any]] = []
    comparable_index = 0
    for raw_frame in raw_frames:
        if len(raw_frame) > max_line_bytes:
            continue
        if comparable_index >= len(returned) or returned[comparable_index] != raw_frame:
            if len(mismatches) < MAX_FRAME_SAMPLES:
                mismatches.append({
                    "frame_index": comparable_index,
                    "raw": _shape(raw_frame),
                    "reader": _shape(returned[comparable_index]) if comparable_index < len(returned) else None,
                })
        comparable_index += 1

    if len(returned) > comparable_index and len(mismatches) < MAX_FRAME_SAMPLES:
        mismatches.append({
            "frame_index": comparable_index,
            "raw": None,
            "reader": _shape(returned[comparable_index]),
        })

    return {
        "raw_complete_frame_count": len(raw_frames),
        "reader_returned_frame_count": len(returned),
        "reader_rejected_frame_count": len(rejected),
        "reader_rejections": rejected[:MAX_FRAME_SAMPLES],
        "raw_trailing_partial_bytes": len(trailing),
        "frames_match": not mismatches and len(returned) == comparable_index,
        "frame_mismatches": mismatches,
        "frame_mismatches_truncated": len(mismatches) >= MAX_FRAME_SAMPLES,
    }


def _serial_state(ser: Any, *, baud: int, timeout: float,
                  dtr_configured: bool, rts_configured: bool) -> dict[str, Any]:
    def read_signal(name: str) -> bool | None:
        try:
            return bool(getattr(ser, name))
        except Exception:
            return None

    return {
        "baud": baud,
        "timeout_seconds": timeout,
        "dtr_configured_before_open": dtr_configured,
        "rts_configured_before_open": rts_configured,
        "dtr_after_open": read_signal("dtr"),
        "rts_after_open": read_signal("rts"),
        "reset_detection_limitation": (
            "DTR/RTS settings are recorded, but this diagnostic cannot prove "
            "whether the adapter or ESP32 reset during port opening."
        ),
    }


def capture_raw(
    port_name: str,
    *,
    baud: int = DEFAULT_BAUD,
    duration: float = DEFAULT_DURATION,
    output_bin: Path,
    output_meta: Path,
    max_capture_bytes: int = MAX_CAPTURE_BYTES,
    timeout: float = DEFAULT_TIMEOUT,
    serial_module: Any | None = None,
    clock: Callable[[], float] = time.monotonic,
    utc_clock: Callable[[], str] = _utc_now,
) -> dict[str, Any]:
    """Capture raw bytes and write the binary evidence plus JSON metadata."""
    if duration <= 0 or max_capture_bytes < 1 or timeout <= 0:
        raise ValueError("duration, max_capture_bytes and timeout must be positive")
    if serial_module is None:
        try:
            import serial as serial_module  # type: ignore
        except ImportError as exc:
            raise RuntimeError("pyserial is required; install physical_demo/requirements.txt") from exc

    output_bin.parent.mkdir(parents=True, exist_ok=True)
    output_meta.parent.mkdir(parents=True, exist_ok=True)
    started_utc = utc_clock()
    started = clock()
    requested_total = 0
    captured_total = 0
    read_index = 0
    trace: list[dict[str, Any]] = []
    trace_truncated = False
    termination_reason = "duration"
    dtr_configured = False
    rts_configured = False
    ser = serial_module.Serial(port=None, baudrate=baud, timeout=timeout)

    try:
        ser.port = port_name
        try:
            ser.dtr = False
            dtr_configured = True
        except Exception:
            pass
        try:
            ser.rts = False
            rts_configured = True
        except Exception:
            pass
        ser.open()
        serial_state = _serial_state(
            ser, baud=baud, timeout=timeout,
            dtr_configured=dtr_configured, rts_configured=rts_configured,
        )
        deadline = started + duration
        with output_bin.open("wb") as binary:
            while clock() < deadline and captured_total < max_capture_bytes:
                requested = min(READ_SIZE, max_capture_bytes - captured_total)
                requested_total += requested
                data = ser.read(requested)
                if not isinstance(data, (bytes, bytearray, memoryview)):
                    raise TypeError("serial read returned a non-bytes value")
                data = bytes(data)
                read_index += 1
                returned = len(data)
                captured = min(returned, max_capture_bytes - captured_total)
                if captured:
                    binary.write(data[:captured])
                    captured_total += captured
                if len(trace) < MAX_TRACE_ENTRIES:
                    trace.append({
                        "read_index": read_index,
                        "monotonic_elapsed_seconds": round(clock() - started, 6),
                        "requested_bytes": requested,
                        "returned_bytes": returned,
                        "captured_bytes": captured,
                        "cumulative_captured_bytes": captured_total,
                        "first_8_hex": data[:8].hex(),
                        "last_8_hex": data[-8:].hex(),
                    })
                else:
                    trace_truncated = True
                if captured_total >= max_capture_bytes:
                    termination_reason = "byte_limit"
                    break
                if not data and not getattr(ser, "is_open", True):
                    termination_reason = "eof"
                    break
            else:
                if captured_total >= max_capture_bytes:
                    termination_reason = "byte_limit"
    finally:
        try:
            ser.close()
        except Exception:
            pass

    ended_utc = utc_clock()
    ended = clock()
    digest = hashlib.sha256(output_bin.read_bytes()).hexdigest()
    raw = output_bin.read_bytes()
    metadata: dict[str, Any] = {
        "kind": "satsentinel_raw_serial_capture_not_acceptance_test",
        "port": port_name,
        "baud": baud,
        "timeout_seconds": timeout,
        "requested_duration_seconds": duration,
        "start_utc": started_utc,
        "end_utc": ended_utc,
        "elapsed_seconds": round(ended - started, 6),
        "termination_reason": termination_reason,
        "capture_byte_limit": max_capture_bytes,
        "capture_bytes": captured_total,
        "requested_bytes_total": requested_total,
        "capture_sha256": digest,
        "binary_path": str(output_bin),
        "metadata_path": str(output_meta),
        "serial": serial_state,
        "read_trace": trace,
        "read_trace_truncated": trace_truncated,
        "analysis": analyze_raw_bytes(raw),
        "offline_buffered_reader_replay": replay_through_buffered_reader(raw),
    }
    output_meta.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only raw serial capture; not an acceptance test.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture = subparsers.add_parser("capture")
    capture.add_argument("--port", required=True)
    capture.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    capture.add_argument("--duration", type=float, default=DEFAULT_DURATION)
    capture.add_argument("--max-capture-bytes", type=int, default=MAX_CAPTURE_BYTES)
    capture.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    capture.add_argument("--output-bin", type=Path, required=True)
    capture.add_argument("--output-meta", type=Path, required=True)

    replay = subparsers.add_parser("replay")
    replay.add_argument("--input-bin", type=Path, required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "capture":
            result = capture_raw(
                args.port, baud=args.baud, duration=args.duration,
                output_bin=args.output_bin, output_meta=args.output_meta,
                max_capture_bytes=args.max_capture_bytes, timeout=args.timeout,
            )
        else:
            raw = args.input_bin.read_bytes()
            result = {
                "kind": "satsentinel_raw_serial_replay_not_acceptance_test",
                "input_bin": str(args.input_bin),
                "input_sha256": hashlib.sha256(raw).hexdigest(),
                "analysis": analyze_raw_bytes(raw),
                "offline_buffered_reader_replay": replay_through_buffered_reader(raw),
            }
    except Exception as exc:
        print(json.dumps({"kind": "satsentinel_raw_serial_diagnostic_error", "error_type": type(exc).__name__, "message": str(exc)}))
        return 2
    print(json.dumps(result, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
