"""SATSentinel-X Class-3 telemetry detector v1.

This is an interpretable, event-level feature extractor and evidence model;
it is deliberately not a trained anomaly detector.  Telemetry is read one
channel at a time because the source pickles are large.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


# Explicit configuration: keep experiment choices in one place.
BASE_DIR = Path(r"E:\SATSentinel-RealTelemetry\inspection")
MISSION_DIR = BASE_DIR / "mission1"
CHANNEL_DIR = BASE_DIR / "selected_channels"
OUTPUT_DIR = BASE_DIR
BASELINE_CONTEXT_SECONDS = 3600.0
BASELINE_MIN_SECONDS = 600.0
MAD_INFORMATIVE_FLOOR = 1e-12
DIFF_SCALE_INFORMATIVE_FLOOR = 1e-12
ABSOLUTE_TOLERANCE = 1e-6
RELATIVE_TOLERANCE = 1e-5
ANOMALY_THRESHOLD = 3.0
STRONG_THRESHOLD = 6.0
MAX_NORMALIZED_DEVIATION = 20.0
MIN_BASELINE_SAMPLES = 3
MIN_EVENT_SAMPLES = 1
CORE_CHANNELS = {41, 42, 43, 44, 45, 46}


def utc_naive(value: Any) -> pd.Timestamp:
    """Use one internal convention: UTC, timezone-naive timestamps."""
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("UTC").tz_localize(None)
    return timestamp


def load_events() -> list[dict[str, Any]]:
    labels = pd.read_csv(MISSION_DIR / "labels.csv")
    types = pd.read_csv(MISSION_DIR / "anomaly_types.csv")
    labels["StartTime"] = pd.to_datetime(labels["StartTime"], utc=True).dt.tz_localize(None)
    labels["EndTime"] = pd.to_datetime(labels["EndTime"], utc=True).dt.tz_localize(None)
    class3 = types.loc[types["Class"].eq("class_3")].copy()
    events = []
    for row in class3.to_dict("records"):
        event_id = row["ID"]
        matching = labels.loc[labels["ID"].eq(event_id)]
        if matching.empty:
            raise ValueError(f"Class-3 event {event_id} has no labels")
        channels = {}
        for channel_name, group in matching.groupby("Channel"):
            channel = int(str(channel_name).split("_")[-1])
            channels[channel] = (group["StartTime"].min(), group["EndTime"].max())
        events.append({
            "event_id": event_id,
            "class": row["Class"],
            "category": row["Category"],
            "dimensionality": row["Dimensionality"],
            "locality": row["Locality"],
            "start": matching["StartTime"].min(),
            "end": matching["EndTime"].max(),
            "channels": channels,
        })
    return events


def morphology(seconds: float) -> str:
    # Deterministic duration bins, chosen before looking at detector evidence.
    if seconds <= 0:
        return "IMPULSIVE"
    if seconds <= 10:
        return "SHORT"
    if seconds <= 600:
        return "MEDIUM"
    if seconds <= 3600:
        return "LONG"
    return "PERSISTENT"


def finite_values(series: pd.Series) -> np.ndarray:
    values = np.asarray(series, dtype=np.float64)
    return values[np.isfinite(values)]


def describe_channel(series: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, Any]:
    """Calculate auditable baseline/event features for one channel interval."""
    context_seconds = max(BASELINE_MIN_SECONDS, min(BASELINE_CONTEXT_SECONDS, max(0.0, (end - start).total_seconds())))
    # pandas label slices are inclusive; explicitly remove the event boundary
    # so a sample exactly at ``start`` can never leak into the baseline.
    baseline = series.loc[start - pd.Timedelta(seconds=context_seconds):start]
    baseline = baseline.loc[baseline.index < start]
    event = series.loc[start:end]
    b = finite_values(baseline)
    e = finite_values(event)
    result: dict[str, Any] = {
        "sample_count": int(len(e)), "baseline_count": int(len(b)),
        "first_event_sample": str(event.index[0]) if len(event) else "",
        "last_event_sample": str(event.index[-1]) if len(event) else "",
        "telemetry_coverage_status": "available" if len(e) else "missing",
        "baseline_mean": np.nan, "baseline_median": np.nan, "baseline_std": np.nan,
        "baseline_mad": np.nan, "scale_used": np.nan, "scale_method": "unavailable",
        "event_mean": np.nan, "event_median": np.nan, "event_std": np.nan,
        "event_min": np.nan, "event_max": np.nan, "absolute_deviation": np.nan,
        "normalized_deviation": np.nan, "max_robust_deviation": np.nan,
        "anomalous_fraction": 0.0, "strong_evidence": False, "evidence_level": "no_evidence",
        "direction": "UNCHANGED", "missing_data": int(len(event) - len(e)),
    }
    if len(b):
        bmean, bmedian = float(np.mean(b)), float(np.median(b))
        bmad = float(np.median(np.abs(b - bmedian)))
        bstd = float(np.std(b, ddof=1)) if len(b) > 1 else 0.0
        result.update(baseline_mean=bmean, baseline_median=bmedian, baseline_mad=bmad, baseline_std=bstd)
    else:
        return result
    if len(e) < MIN_EVENT_SAMPLES:
        return result
    emean, emedian = float(np.mean(e)), float(np.median(e))
    result.update(event_mean=emean, event_median=emedian,
                  event_std=float(np.std(e, ddof=1)) if len(e) > 1 else 0.0,
                  event_min=float(np.min(e)), event_max=float(np.max(e)))

    # Scale selection avoids epsilon-divided z-scores.  MAD is preferred;
    # median absolute first-difference is a local variation scale; when both
    # are degenerate, an explicit quantization/absolute-tolerance rule is used.
    robust_scale = 1.4826 * bmad
    if np.isfinite(robust_scale) and robust_scale > MAD_INFORMATIVE_FLOOR:
        scale, method = robust_scale, "mad"
    else:
        diffs = np.diff(b)
        diff_scale = 1.4826 * float(np.median(np.abs(diffs))) / math.sqrt(2.0) if len(diffs) else 0.0
        if np.isfinite(diff_scale) and diff_scale > DIFF_SCALE_INFORMATIVE_FLOOR:
            scale, method = diff_scale, "median_abs_diff"
        else:
            scale = max(ABSOLUTE_TOLERANCE, RELATIVE_TOLERANCE * max(1.0, abs(bmedian)))
            method = "absolute_tolerance"
    deviations = np.abs(e - bmedian)
    normalized = np.minimum(deviations / scale, MAX_NORMALIZED_DEVIATION)
    mean_delta = emean - bmedian
    result.update(scale_used=float(scale), scale_method=method,
                  absolute_deviation=float(abs(mean_delta)),
                  normalized_deviation=float(min(abs(mean_delta) / scale, MAX_NORMALIZED_DEVIATION)),
                  max_robust_deviation=float(np.max(normalized)),
                  anomalous_fraction=float(np.mean(normalized >= ANOMALY_THRESHOLD)))
    strong_fraction = float(np.mean(normalized >= STRONG_THRESHOLD))
    if strong_fraction >= 0.5 or result["max_robust_deviation"] >= STRONG_THRESHOLD:
        result["strong_evidence"] = True
        result["evidence_level"] = "strong"
    elif result["anomalous_fraction"] >= 0.25 or result["normalized_deviation"] >= ANOMALY_THRESHOLD:
        result["evidence_level"] = "weak"
    if abs(mean_delta) <= scale * ANOMALY_THRESHOLD:
        result["direction"] = "UNCHANGED"
    else:
        result["direction"] = "UP" if mean_delta > 0 else "DOWN"
    return result


def load_channel(channel: int) -> pd.Series:
    path = CHANNEL_DIR / f"channel_{channel}" / f"channel_{channel}"
    frame = pd.read_pickle(path)
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise TypeError(f"channel_{channel} does not have a DatetimeIndex")
    series = frame.iloc[:, 0].astype("float32", copy=False)
    index = pd.DatetimeIndex(series.index)
    if index.tz is not None:
        index = index.tz_convert("UTC").tz_localize(None)
    series.index = index
    return series.sort_index()


def main() -> None:
    events = load_events()
    if len(events) != 30:
        raise AssertionError(f"Expected 30 Class-3 events from metadata, found {len(events)}")
    channel_results: list[dict[str, Any]] = []
    by_event: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_channels = sorted({ch for event in events for ch in event["channels"]})
    for channel in all_channels:
        print(f"Loading channel_{channel} ({all_channels.index(channel)+1}/{len(all_channels)})")
        series = load_channel(channel)
        for event in events:
            if channel not in event["channels"]:
                continue
            features = describe_channel(series, *event["channels"][channel])
            row = {"event_id": event["event_id"], "channel": channel, "participates": True, **features}
            channel_results.append(row)
            by_event[event["event_id"]].append(row)

    event_rows = []
    for event in events:
        rows = by_event[event["event_id"]]
        available = [r for r in rows if r["sample_count"] > 0]
        anomalous = [r for r in available if r["evidence_level"] in ("weak", "strong")]
        strong = [r for r in available if r["strong_evidence"]]
        core_part = [r for r in rows if r["channel"] in CORE_CHANNELS]
        core_anom = [r for r in anomalous if r["channel"] in CORE_CHANNELS]
        dirs = [r["direction"] for r in available if r["evidence_level"] != "no_evidence"]
        nonzero = [d for d in dirs if d != "UNCHANGED"]
        direction = "UNCHANGED" if not nonzero else (nonzero[0] if all(d == nonzero[0] for d in nonzero) else "MIXED")
        synchrony = (max(Counter(nonzero).values()) / len(nonzero)) if nonzero else np.nan
        anomaly_fraction = len(anomalous) / len(available) if available else 0.0
        strong_fraction = len(strong) / len(available) if available else 0.0
        core_fraction = len(core_anom) / len(core_part) if core_part else 0.0
        mean_strength = float(np.mean([r["normalized_deviation"] for r in available])) if available else 0.0
        # Fixed, interpretable evidence model; weights are not fitted.
        score = 0.45 * anomaly_fraction + 0.25 * strong_fraction + 0.20 * core_fraction + 0.10 * (synchrony if np.isfinite(synchrony) else 0.0)
        if score >= 0.65:
            classification = "detected / strong evidence"
        elif score >= 0.35:
            classification = "detected / moderate evidence"
        elif score >= 0.15:
            classification = "ambiguous"
        else:
            classification = "not detected"
        duration = max(0.0, (event["end"] - event["start"]).total_seconds())
        event_rows.append({
            "event_id": event["event_id"], "class": event["class"], "category": event["category"],
            "dimensionality": event["dimensionality"], "locality": event["locality"],
            "start": event["start"].isoformat(), "end": event["end"].isoformat(),
            "duration_seconds": duration, "duration_class": morphology(duration), "morphology": morphology(duration),
            "labelled_channel_count": len(rows), "available_channel_count": len(available),
            "anomalous_channel_count": len(anomalous), "strong_channel_count": len(strong),
            "anomalous_channel_fraction": anomaly_fraction, "strong_channel_fraction": strong_fraction,
            "core_participating_count": len(core_part), "core_anomalous_count": len(core_anom), "core_fraction": core_fraction,
            "core_41_46_participating": len(core_part), "core_41_46_anomalous": len(core_anom), "core_41_46_fraction": core_fraction,
            "direction": direction, "directional_synchrony": synchrony,
            "max_robust_deviation": max((r["max_robust_deviation"] for r in available), default=np.nan),
            "median_robust_deviation": float(np.median([r["max_robust_deviation"] for r in available])) if available else np.nan,
            "mean_normalized_deviation": mean_strength, "event_score": score, "classification": classification,
            "scale_fallback_count": sum(r["scale_method"] != "mad" for r in rows),
            "missing_data_count": sum(r["sample_count"] == 0 or r["missing_data"] > 0 for r in rows),
            "insufficient_telemetry": len(available) < len(rows),
        })

    channel_df = pd.DataFrame(channel_results)
    event_df = pd.DataFrame(event_rows)
    channel_df.to_csv(OUTPUT_DIR / "class3_detector_channel_results.csv", index=False)
    event_df.to_csv(OUTPUT_DIR / "class3_detector_results.csv", index=False)
    report = {
        "dataset_paths": {"labels": str(MISSION_DIR / "labels.csv"), "anomaly_types": str(MISSION_DIR / "anomaly_types.csv"), "channel_directory": str(CHANNEL_DIR)},
        "timestamp_normalization": "All labels and telemetry indices are converted to UTC and then made timezone-naive.",
        "baseline_context": "The preceding max(600 seconds, min(3600 seconds, event duration)) timestamp window, inclusive of its endpoint and not event samples.",
        "scale_selection": "1.4826*MAD when informative; otherwise scaled median absolute first difference; otherwise explicit absolute tolerance max(1e-6, 1e-5*max(1,|baseline median|)). No epsilon is added to MAD. Normalized deviations are capped at 20.",
        "anomaly_evidence": {"anomaly_threshold": ANOMALY_THRESHOLD, "strong_threshold": STRONG_THRESHOLD, "strong_rule": "at least half event samples strong OR maximum normalized deviation strong", "anomaly_rule": "at least 25% event samples anomalous OR event mean normalized deviation anomalous"},
        "core_channel_definition": "Channels 41-46 are reported as a discovered feature and contribute 0.20 of the event score; they do not define Class 3.",
        "morphology_definitions_seconds": {"IMPULSIVE": "duration <= 0", "SHORT": "0 < duration <= 10", "MEDIUM": "10 < duration <= 600", "LONG": "600 < duration <= 3600", "PERSISTENT": "duration > 3600"},
        "scoring_formula": "0.45*anomalous_fraction + 0.25*strong_fraction + 0.20*core_fraction + 0.10*directional_synchrony",
        "classification_thresholds": {"strong": 0.65, "moderate": 0.35, "ambiguous": 0.15},
        "class3_event_count": len(events), "classification_counts": event_df["classification"].value_counts().to_dict(),
        "id_91_result": event_df.loc[event_df["event_id"].eq("id_91")].to_dict("records"),
        "per_event_summary": event_df.to_dict("records"),
        "numerical_warnings": {"scale_fallbacks": int(event_df["scale_fallback_count"].sum()), "missing_or_nan_channel_windows": int(event_df["missing_data_count"].sum()), "max_capped_normalized_deviation": MAX_NORMALIZED_DEVIATION},
        "unresolved_edge_cases": ["Only labelled Class-3 events were evaluated; no negative-control set was constructed.", "A channel with no finite baseline/event samples is reported as missing, not nominal."],
    }
    (OUTPUT_DIR / "class3_detector_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"events": len(event_df), "channel_rows": len(channel_df), "classification_counts": report["classification_counts"], "id_91": report["id_91_result"]}, indent=2, default=str))


if __name__ == "__main__":
    main()
