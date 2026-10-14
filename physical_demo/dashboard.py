"""Local mission-operations dashboard for the physical demonstrator.

The dashboard deliberately reuses receiver.read_framed_line and
receiver.TelemetryReceiver. It does not define a second telemetry schema or
replace the command-line receiver.
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
from collections import deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import serial  # type: ignore
    from serial.tools import list_ports  # type: ignore
except ImportError:  # pragma: no cover - exercised by setup, not unit tests
    serial = None
    list_ports = None

from receiver import (  # noqa: E402
    MAX_ACCEPTANCE_GAP_SECONDS,
    TelemetryReceiver,
    read_framed_line,
)
from replay import MAX_SPEED, MIN_SPEED, ReplayController, load_jsonl  # noqa: E402
from power_autonomy import report_json, run_scenario  # noqa: E402
from synthetic_detector import detect  # noqa: E402


ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "dashboard"
REPLAY_ROOT = ROOT / "fixtures"
REPLAY_SOURCES = {"synthetic": REPLAY_ROOT / "synthetic_anomaly.jsonl"}
POWER_SCENARIOS = {
    "recovery_success": REPLAY_ROOT / "synthetic_power_recovery_success.jsonl",
    "recovery_failure": REPLAY_ROOT / "synthetic_power_recovery_failure.jsonl",
}
MAX_RECENT_RECORDS = 100
MAX_CHART_POINTS = 180


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value and abs(float(value)) != float("inf")


class DashboardSession:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.receiver = TelemetryReceiver()
        self.serial_port: Any = None
        self.port_name: str | None = None
        self.reader_thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.status = "disconnected"
        self.status_detail = "No device connected"
        self.started_monotonic: float | None = None
        self.finished_monotonic: float | None = None
        self.last_message_monotonic: float | None = None
        self.recent_records: deque[dict[str, Any]] = deque(maxlen=MAX_RECENT_RECORDS)
        self.chart_records: deque[dict[str, Any]] = deque(maxlen=MAX_CHART_POINTS)
        self.session_lines: list[str] = []
        self.logging = False
        self.messages: deque[dict[str, str]] = deque(maxlen=80)
        self.source_type = "none"
        self.replay: ReplayController | None = None
        self.incident: dict[str, Any] | None = None
        self.autonomy_report: dict[str, Any] | None = None

    def message(self, level: str, text: str) -> None:
        with self.lock:
            self.messages.append({"level": level, "text": text, "time": time.strftime("%H:%M:%S")})

    def reset_receiver(self) -> None:
        self.receiver = TelemetryReceiver()
        self.recent_records.clear()
        self.chart_records.clear()
        self.session_lines.clear()
        self.messages.clear()
        self.incident = None
        self.autonomy_report = None

    def run_autonomy_scenario(self, scenario: str) -> tuple[bool, str]:
        path = POWER_SCENARIOS.get(scenario)
        if path is None:
            return False, "Unknown power autonomy scenario"
        if self.status == "connected":
            return False, "Disconnect the serial device before running the synthetic autonomy demonstrator"
        try:
            report = run_scenario(path, scenario_id=scenario)
        except (OSError, ValueError, TypeError) as exc:
            return False, f"Autonomy scenario unavailable: {type(exc).__name__}"
        with self.lock:
            self.autonomy_report = report
            self.source_type = "synthetic_power_scenario"
            self.status = "autonomy_complete"
            self.status_detail = f"Synthetic autonomy scenario complete: {report['final_outcome']['state']}"
        self.message("info", f"Completed synthetic power scenario: {scenario}")
        return True, "autonomy_complete"

    def reset_autonomy(self) -> tuple[bool, str]:
        with self.lock:
            self.autonomy_report = None
            if self.status == "autonomy_complete":
                self.status = "disconnected"
                self.status_detail = "No device connected"
                self.source_type = "none"
        self.message("info", "Synthetic autonomy demonstrator reset")
        return True, "autonomy_reset"

    def ports(self) -> list[dict[str, str]]:
        if list_ports is None:
            return []
        return [
            {"device": port.device, "description": port.description or "USB serial device", "hwid": port.hwid or ""}
            for port in list_ports.comports()
        ]

    def connect(self, port_name: str) -> tuple[bool, str]:
        if serial is None:
            return False, "pyserial is not installed; install requirements.txt"
        self.disconnect(quiet=True)
        try:
            port = serial.Serial(port_name, 115200, timeout=1)
        except Exception as exc:
            with self.lock:
                self.status = "error"
                self.status_detail = f"Could not open {port_name}: {type(exc).__name__}"
                self.port_name = port_name
            self.message("error", self.status_detail)
            return False, self.status_detail

        with self.lock:
            self.reset_receiver()
            self.serial_port = port
            self.port_name = port_name
            self.status = "connected"
            self.status_detail = "Receiving telemetry"
            self.started_monotonic = time.monotonic()
            self.finished_monotonic = None
            self.last_message_monotonic = None
            self.stop_event.clear()
            self.reader_thread = threading.Thread(target=self._reader_loop, name="physical-demo-serial", daemon=True)
            self.reader_thread.start()
        self.message("info", f"Connected to {port_name} at 115200 baud")
        return True, "connected"

    def disconnect(self, quiet: bool = False) -> None:
        with self.lock:
            self.stop_event.set()
            port = self.serial_port
            self.serial_port = None
            was_connected = self.status == "connected"
            self.status = "disconnected"
            self.status_detail = "No device connected"
            self.finished_monotonic = time.monotonic() if self.started_monotonic is not None else None
        if port is not None:
            try:
                port.close()
            except Exception:
                pass
        if was_connected and not quiet:
            self.message("info", "Disconnected; partial session preserved")

    def _replay_reset(self) -> None:
        with self.lock:
            self.reset_receiver()
            self.source_type = "synthetic_replay"
            self.status = "replay_ready"
            self.status_detail = "Synthetic replay ready"
            self.started_monotonic = time.monotonic()
            self.finished_monotonic = None
            self.last_message_monotonic = None

    def start_replay(self, source: str = "synthetic", speed: float = 4.0) -> tuple[bool, str]:
        path = REPLAY_SOURCES.get(source)
        if path is None:
            return False, "Unknown replay source"
        if self.status == "connected":
            return False, "Disconnect the serial device before starting replay"
        try:
            frames = load_jsonl(path)
            bounded_speed = max(MIN_SPEED, min(MAX_SPEED, float(speed)))
        except (OSError, ValueError, TypeError) as exc:
            return False, f"Replay unavailable: {type(exc).__name__}"
        with self.lock:
            self.reset_receiver()
            self.source_type = "synthetic_replay" if source == "synthetic" else "recorded_replay"
            self.status = "replay_ready"
            self.status_detail = f"{self.source_type.replace('_', ' ').title()} ready"
            self.started_monotonic = time.monotonic()
            self.finished_monotonic = None
            self.replay = ReplayController(frames, self._ingest_replay_frame, self._replay_reset)
            self.replay.set_speed(bounded_speed)
        self.message("info", f"Loaded {self.source_type}: {len(frames)} frames")
        self.play_replay()
        return True, "replay_started"

    def _ingest_replay_frame(self, frame: bytes) -> None:
        with self.lock:
            self.status = "replay"
            self.status_detail = f"Playing {self.source_type.replace('_', ' ')}"
        self.ingest_frame(frame)
        with self.lock:
            self.incident = detect(list(self.receiver.records)) if self.source_type == "synthetic_replay" else None

    def play_replay(self) -> tuple[bool, str]:
        if self.replay is None:
            return False, "Load a replay source first"
        self.replay.play()
        with self.lock:
            self.status = "replay"
            self.status_detail = f"Playing {self.source_type.replace('_', ' ')}"
        return True, "playing"

    def pause_replay(self) -> tuple[bool, str]:
        if self.replay is None:
            return False, "Load a replay source first"
        self.replay.pause()
        with self.lock:
            self.status = "replay_paused"
            self.status_detail = "Replay paused"
        return True, "paused"

    def reset_replay(self) -> tuple[bool, str]:
        if self.replay is None:
            return False, "Load a replay source first"
        self.replay.reset()
        return True, "reset"

    def set_replay_speed(self, speed: float) -> tuple[bool, str]:
        if self.replay is None:
            return False, "Load a replay source first"
        bounded = self.replay.set_speed(float(speed))
        return True, str(bounded)

    def _reader_loop(self) -> None:
        while not self.stop_event.is_set():
            with self.lock:
                port = self.serial_port
            if port is None:
                return
            try:
                kind, frame = read_framed_line(port)
            except Exception as exc:
                with self.lock:
                    self.status = "error"
                    self.status_detail = f"Serial disconnect: {type(exc).__name__}"
                    self.finished_monotonic = time.monotonic()
                self.message("error", self.status_detail)
                return
            if kind == "timeout":
                self.message("warning", "Serial timeout; waiting for telemetry")
                continue
            if kind in {"eof", "eof_partial"}:
                with self.lock:
                    self.status = "disconnected"
                    self.status_detail = "Serial stream ended; partial session preserved"
                    self.finished_monotonic = time.monotonic()
                self.message("error", self.status_detail)
                return
            if kind != "line":
                self.receiver.reject(kind)
                self.message("warning", f"Rejected frame: {kind}")
                continue
            self.ingest_frame(frame or b"")

    def ingest_frame(self, frame: bytes | str, host_monotonic: float | None = None) -> dict[str, Any] | None:
        received_at = host_monotonic if host_monotonic is not None else time.monotonic()
        record = self.receiver.parse_line(frame, host_monotonic=received_at)
        with self.lock:
            if record is None:
                reason = self.receiver.errors[-1] if self.receiver.errors else "validation_error"
                self.message("warning", f"Rejected telemetry: {reason}")
                return None
            self.last_message_monotonic = received_at
            self.recent_records.appendleft(record)
            self.chart_records.append(record)
            if self.logging:
                self.session_lines.append(json.dumps(record, separators=(",", ":"), allow_nan=False))
            if record["sequence_status"] not in {"first", "contiguous"}:
                self.message("warning", f"Sequence {record['sequence_status']} at #{record['seq']}")
            if self.source_type == "synthetic_replay":
                self.incident = detect(list(self.receiver.records))
            return record

    def start_logging(self) -> tuple[bool, str]:
        with self.lock:
            if self.status != "connected":
                detail = "Connect to a device before starting logging"
                self.message("warning", detail)
                return False, detail
            if self.logging:
                detail = "Session logging is already active"
                self.message("warning", detail)
                return False, detail
            self.logging = True
        self.message("info", "Session logging started")
        return True, "logging"

    def stop_logging(self) -> tuple[bool, str]:
        with self.lock:
            if not self.logging:
                return False, "Session logging is not active"
            self.logging = False
        self.message("info", "Session logging stopped")
        return True, "stopped"

    def export_lines(self) -> str:
        with self.lock:
            return "\n".join(self.session_lines) + ("\n" if self.session_lines else "")

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            now = time.monotonic()
            start = self.started_monotonic
            end = self.finished_monotonic or now
            uptime = max(0.0, end - start) if start is not None else 0.0
            age = max(0.0, now - self.last_message_monotonic) if self.last_message_monotonic is not None else None
            records = list(self.receiver.records)
            invalid_count = len(self.receiver.errors)
            sequence_anomalies = sum(r["sequence_status"] not in {"first", "contiguous"} for r in records)
            gaps = sum(r["host_gap_s"] > MAX_ACCEPTANCE_GAP_SECONDS for r in records)
            valid_count = sum(r["sensor_valid"] and r["sensor_status"] == "measurement_verified" for r in records)
            invalid_sensor_count = sum(not r["sensor_valid"] for r in records)
            chart = []
            for record in self.chart_records:
                chart.append({
                    "time": record["host_received_utc"],
                    "temperature_c": record["temperature_c"] if record["sensor_valid"] and _finite_number(record["temperature_c"]) else None,
                    "humidity_pct": record.get("humidity_pct") if _finite_number(record.get("humidity_pct")) else None,
                    "pressure_hpa": record.get("pressure_hpa") if _finite_number(record.get("pressure_hpa")) else None,
                })
            replay_snapshot = self.replay.snapshot() if self.replay is not None else None
            displayed_status = self.status
            displayed_detail = self.status_detail
            if replay_snapshot and replay_snapshot["state"] == "complete":
                displayed_status = "replay_complete"
                displayed_detail = "Replay complete"
            return {
                "status": displayed_status,
                "status_detail": displayed_detail,
                "port": self.port_name,
                "last_message_age_s": age,
                "uptime_s": uptime,
                "logging": self.logging,
                "records": list(self.recent_records),
                "chart": chart,
                "stats": {
                    "valid_records": valid_count,
                    "invalid_records": invalid_count + invalid_sensor_count,
                    "sequence_anomalies": sequence_anomalies,
                    "data_gaps": gaps,
                    "session_duration_s": uptime,
                    "total_records": len(records),
                    "logged_records": len(self.session_lines),
                },
                "messages": list(self.messages),
                "source_type": self.source_type,
                "replay": replay_snapshot,
                "incident": self.incident,
                "autonomy": self.autonomy_report,
            }


SESSION = DashboardSession()


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "SATSentinelDashboard/0.1"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: Any, status: int = HTTPStatus.OK) -> None:
        self._send(status, "application/json; charset=utf-8", json.dumps(payload, allow_nan=False).encode("utf-8"))

    def _body_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 16_384:
            raise ValueError("request too large")
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/":
            self._send(HTTPStatus.OK, "text/html; charset=utf-8", (WEB_ROOT / "index.html").read_bytes())
        elif path == "/api/state":
            self._json(SESSION.snapshot())
        elif path == "/api/ports":
            self._json({"ports": SESSION.ports()})
        elif path == "/api/session/export":
            data = SESSION.export_lines().encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Content-Disposition", "attachment; filename=satsentinel-session.jsonl")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif path == "/api/evidence/export":
            payload = SESSION.incident or {"status": "NO_INCIDENT", "source_type": SESSION.source_type}
            data = (json.dumps(payload, indent=2, allow_nan=False) + "\n").encode("utf-8")
            incident_id = str(payload.get("incident_id", "evidence"))
            safe_id = "".join(character if character.isalnum() or character in "-_" else "_" for character in incident_id)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", f"attachment; filename=SATSentinelX_Incident_{safe_id}.json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif path == "/api/autonomy/evidence/export":
            payload = SESSION.autonomy_report or {"status": "NO_AUTONOMY_REPORT"}
            data = report_json(payload).encode("utf-8")
            scenario = str(payload.get("scenario_id", "evidence"))
            safe_id = "".join(character if character.isalnum() or character in "-_" else "_" for character in scenario)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", f"attachment; filename=SATSentinelX_Autonomy_{safe_id}.json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        elif path in {"/app.js", "/styles.css"} or path.startswith("/assets/"):
            relative = Path(path.lstrip("/"))
            file = (WEB_ROOT / relative).resolve()
            if WEB_ROOT not in file.parents or not file.is_file():
                self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            if path.endswith(".js"):
                content_type = "text/javascript; charset=utf-8"
            elif path.endswith(".css"):
                content_type = "text/css; charset=utf-8"
            elif path.endswith(".png"):
                content_type = "image/png"
            else:
                content_type = "application/octet-stream"
            self._send(HTTPStatus.OK, content_type, file.read_bytes())
        else:
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            payload = self._body_json()
            if path == "/api/connect":
                ok, detail = SESSION.connect(str(payload.get("port", "")))
                self._json({"ok": ok, "detail": detail}, HTTPStatus.OK if ok else HTTPStatus.BAD_REQUEST)
            elif path == "/api/disconnect":
                SESSION.disconnect()
                self._json({"ok": True})
            elif path == "/api/session/start":
                ok, detail = SESSION.start_logging()
                self._json({"ok": ok, "detail": detail}, HTTPStatus.OK if ok else HTTPStatus.CONFLICT)
            elif path == "/api/session/stop":
                ok, detail = SESSION.stop_logging()
                self._json({"ok": ok, "detail": detail}, HTTPStatus.OK if ok else HTTPStatus.CONFLICT)
            elif path == "/api/replay/start":
                ok, detail = SESSION.start_replay(str(payload.get("source", "synthetic")), float(payload.get("speed", 4.0)))
                self._json({"ok": ok, "detail": detail}, HTTPStatus.OK if ok else HTTPStatus.CONFLICT)
            elif path == "/api/replay/play":
                ok, detail = SESSION.play_replay()
                self._json({"ok": ok, "detail": detail}, HTTPStatus.OK if ok else HTTPStatus.CONFLICT)
            elif path == "/api/replay/pause":
                ok, detail = SESSION.pause_replay()
                self._json({"ok": ok, "detail": detail}, HTTPStatus.OK if ok else HTTPStatus.CONFLICT)
            elif path == "/api/replay/reset":
                ok, detail = SESSION.reset_replay()
                self._json({"ok": ok, "detail": detail}, HTTPStatus.OK if ok else HTTPStatus.CONFLICT)
            elif path == "/api/replay/speed":
                ok, detail = SESSION.set_replay_speed(float(payload.get("speed", 1.0)))
                self._json({"ok": ok, "detail": detail}, HTTPStatus.OK if ok else HTTPStatus.CONFLICT)
            elif path == "/api/autonomy/run":
                ok, detail = SESSION.run_autonomy_scenario(str(payload.get("scenario", "recovery_success")))
                self._json({"ok": ok, "detail": detail}, HTTPStatus.OK if ok else HTTPStatus.CONFLICT)
            elif path == "/api/autonomy/reset":
                ok, detail = SESSION.reset_autonomy()
                self._json({"ok": ok, "detail": detail}, HTTPStatus.OK if ok else HTTPStatus.CONFLICT)
            else:
                self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            SESSION.message("error", f"Dashboard error: {type(exc).__name__}")
            self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)


def main() -> int:
    parser = argparse.ArgumentParser(description="SATSentinel-X local telemetry dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8765")))
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"SATSentinel-X dashboard: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        SESSION.disconnect(quiet=True)
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
