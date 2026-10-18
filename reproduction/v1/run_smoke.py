from __future__ import annotations

import hashlib
import importlib.util
import json
import platform
import shutil
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
MANIFEST = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
SOURCE = (HERE / MANIFEST["frozen_detector_source"]).resolve()
ORIGINAL_SOURCE = HERE.parents[1] / "inspection" / "class3_detector_v1.py"
CONTRACT = HERE / MANIFEST["expected_output"]["contract"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_detector():
    expected = MANIFEST["frozen_detector_sha256"]
    actual = sha256(SOURCE)
    if actual != expected:
        raise AssertionError(f"frozen detector hash mismatch: {actual} != {expected}")
    if ORIGINAL_SOURCE.exists() and sha256(ORIGINAL_SOURCE) != actual:
        raise AssertionError("public source snapshot differs from the existing local frozen detector")
    text = SOURCE.read_text(encoding="utf-8")
    if text.count(r"E:\SATSentinel-RealTelemetry\inspection") != 1:
        raise AssertionError("unexpected absolute-path literals in frozen source snapshot")
    spec = importlib.util.spec_from_file_location("frozen_detector_v1_smoke", SOURCE)
    if spec is None or spec.loader is None:
        raise ImportError(SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_manifest_hashes() -> None:
    for relative, expected in MANIFEST["fixture"]["sha256"].items():
        actual = sha256(HERE / relative)
        if actual != expected:
            raise AssertionError(f"fixture hash mismatch for {relative}: {actual} != {expected}")
    actual = sha256(CONTRACT)
    expected = MANIFEST["expected_output"]["sha256"]
    if expected == "TO_BE_FILLED" or actual != expected:
        raise AssertionError(f"expected-output contract hash mismatch: {actual} != {expected}")


def prepare_fixture(root: Path) -> tuple[Path, Path]:
    mission = root / "mission1"
    channels = root / "selected_channels"
    mission.mkdir(parents=True)
    for name in ("labels.csv", "anomaly_types.csv"):
        shutil.copyfile(HERE / "fixture" / name, mission / name)
    telemetry = pd.read_csv(HERE / "fixture" / "telemetry.csv")
    timestamps = pd.to_datetime(telemetry.pop("timestamp"), utc=True).dt.tz_localize(None)
    for channel in (41, 42):
        target = channels / f"channel_{channel}"
        target.mkdir(parents=True)
        frame = pd.DataFrame({"value": telemetry[f"channel_{channel}"].astype("float32").to_numpy()}, index=timestamps)
        frame.to_pickle(target / f"channel_{channel}")
    return mission, channels


def run_once(output: Path) -> tuple[bytes, bytes]:
    work = output / "inputs"
    work.mkdir(parents=True)
    mission, channels = prepare_fixture(work)
    module = load_detector()
    module.BASE_DIR = work
    module.MISSION_DIR = mission
    module.CHANNEL_DIR = channels
    module.OUTPUT_DIR = output
    output_root = output.resolve()
    for value in (module.BASE_DIR, module.MISSION_DIR, module.CHANNEL_DIR, module.OUTPUT_DIR):
        if not Path(value).resolve().is_relative_to(output_root):
            raise AssertionError("runtime path injection escaped the smoke workspace")
    module.main()
    event = (output / "class3_detector_results.csv").read_bytes()
    channel = (output / "class3_detector_channel_results.csv").read_bytes()
    return event, channel


def main() -> None:
    verify_manifest_hashes()
    expected = MANIFEST["derived_expectation"]
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    tol = MANIFEST["tolerances"]["score_abs"]
    with tempfile.TemporaryDirectory(prefix="satsentinel-v1-smoke-") as temp:
        root = Path(temp)
        first_event, first_channel = run_once(root / "run1")
        second_event, second_channel = run_once(root / "run2")
        if first_event != second_event or first_channel != second_channel:
            raise AssertionError("two smoke runs produced different CSV bytes")
        actual_output_hashes = {"class3_detector_results.csv": hashlib.sha256(first_event).hexdigest(), "class3_detector_channel_results.csv": hashlib.sha256(first_channel).hexdigest()}
        if actual_output_hashes != MANIFEST["expected_output"]["outputs_sha256"]:
            raise AssertionError(f"expected output hash mismatch: {actual_output_hashes}")
        events = pd.read_csv(root / "run1" / "class3_detector_results.csv")
        channels = pd.read_csv(root / "run1" / "class3_detector_channel_results.csv")
        if list(events.columns) != contract["event_columns"] or list(channels.columns) != contract["channel_columns"]:
            raise AssertionError("complete output schema or column ordering mismatch")
        if len(events) != contract["event_row_count"] or len(channels) != contract["channel_row_count"]:
            raise AssertionError(f"unexpected output sizes: events={len(events)}, channels={len(channels)}")
        if not np.allclose(events["event_score"], contract["event_score"], atol=tol, rtol=0):
            raise AssertionError("event score mismatch")
        if set(events["classification"]) != {contract["classification"]}:
            raise AssertionError("classification mismatch")
        if set(channels["scale_method"]) != {"mad"} or not np.allclose(channels["max_robust_deviation"], contract["channel_max_robust_deviation"], atol=tol, rtol=0):
            raise AssertionError("channel evidence mismatch")
        if int(events["missing_data_count"].sum()) != 0 or int(events["scale_fallback_count"].sum()) != 0:
            raise AssertionError("unexpected missing data or scale fallback")
        required = {"event_id", "event_score", "classification", "missing_data_count"}
        if not required.issubset(events.columns):
            raise AssertionError("event output schema mismatch")
        fixture_hashes = {relative: sha256(HERE / relative) for relative in MANIFEST["fixture"]["sha256"]}
        authoritative = sha256(ORIGINAL_SOURCE) if ORIGINAL_SOURCE.exists() else None
        pinned = MANIFEST["dependencies"]
        environment_matches = platform.python_version() == MANIFEST["python"] and np.__version__ == pinned["numpy"] and pd.__version__ == pinned["pandas"]
        report = {"status": "PASS", "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "pinned_requirements": pinned, "environment_matches_pinned": environment_matches, "detector_sha256": sha256(SOURCE), "authoritative_detector_sha256": authoritative, "authoritative_source_check": "PASS" if authoritative == sha256(SOURCE) else "NOT_AVAILABLE_IN_CLEAN_CLONE", "fixture_sha256": fixture_hashes, "output_sha256": actual_output_hashes, "runs": 2, "event_rows": len(events), "channel_rows": len(channels), "event_score": float(events["event_score"].iloc[0]), "classification": events["classification"].iloc[0], "absolute_path_injection": "runtime-only"}
        (HERE / "reproducibility_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
