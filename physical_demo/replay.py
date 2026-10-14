"""Deterministic JSONL replay controller for the local dashboard."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Callable


MIN_SPEED = 0.25
MAX_SPEED = 20.0


def load_jsonl(path: Path) -> list[bytes]:
    """Load bounded replay frames without replacing receiver validation."""
    frames: list[bytes] = []
    for line_number, line in enumerate(path.read_bytes().splitlines(), 1):
        if not line:
            continue
        try:
            obj = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid replay JSON at line {line_number}") from exc
        if not isinstance(obj, dict) or type(obj.get("device_time_ms")) is not int:
            raise ValueError(f"replay line {line_number} lacks integer device_time_ms")
        frames.append(line)
    if not frames:
        raise ValueError("replay source is empty")
    return frames


class ReplayController:
    """Threaded playback with manual stepping for deterministic tests."""

    def __init__(self, frames: list[bytes], on_frame: Callable[[bytes], None], on_reset: Callable[[], None]):
        self.frames = frames
        self.on_frame = on_frame
        self.on_reset = on_reset
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.index = 0
        self.speed = 1.0
        self.state = "idle"
        self.thread: threading.Thread | None = None

    def snapshot(self) -> dict[str, object]:
        with self.lock:
            current = self.index
            return {
                "state": self.state,
                "speed": self.speed,
                "index": current,
                "total": len(self.frames),
                "progress": current / len(self.frames) if self.frames else 0.0,
            }

    def set_speed(self, speed: float) -> float:
        if speed != speed or speed in (float("inf"), float("-inf")):
            raise ValueError("speed must be finite")
        with self.lock:
            self.speed = max(MIN_SPEED, min(MAX_SPEED, float(speed)))
            self.wake.set()
            return self.speed

    def step(self) -> bool:
        with self.lock:
            if self.index >= len(self.frames):
                self.state = "complete"
                return False
            frame = self.frames[self.index]
            self.index += 1
        self.on_frame(frame)
        with self.lock:
            if self.index >= len(self.frames):
                self.state = "complete"
        return True

    def play(self) -> None:
        with self.lock:
            if self.state == "complete":
                self.index = 0
                self.on_reset()
            self.state = "playing"
            if self.thread is None or not self.thread.is_alive():
                self.thread = threading.Thread(target=self._run, name="physical-demo-replay", daemon=True)
                self.thread.start()
            self.wake.clear()

    def pause(self) -> None:
        with self.lock:
            if self.state == "playing":
                self.state = "paused"
            self.wake.set()

    def reset(self) -> None:
        with self.lock:
            self.state = "idle"
            self.index = 0
            self.wake.set()
        self.on_reset()

    def _run(self) -> None:
        while True:
            with self.lock:
                if self.state != "playing" or self.index >= len(self.frames):
                    if self.index >= len(self.frames):
                        self.state = "complete"
                    return
                index = self.index
                speed = self.speed
                frame = self.frames[index]
                next_time = None
                if index + 1 < len(self.frames):
                    next_obj = json.loads(self.frames[index + 1].decode("utf-8"))
                    current_obj = json.loads(frame.decode("utf-8"))
                    next_time = max(0.0, (next_obj["device_time_ms"] - current_obj["device_time_ms"]) / 1000.0 / speed)
            self.step()
            if next_time is not None and self.wake.wait(next_time):
                self.wake.clear()
