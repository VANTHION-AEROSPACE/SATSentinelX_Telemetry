from __future__ import annotations

import hashlib
import json
import math
import platform
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research" / "duration_dimensionality_confound_analysis_v1"
EVAL = ROOT / "inspection" / "class3_detector_v1_broader_evaluation_v1" / "broader_v1_evaluation.csv"
FRAME = ROOT / "inspection" / "esa_broader_control_characterization_v1" / "control_sampling_frame.csv"

STRUCTURED = [
    "control_structural_features.csv", "duration_stratification.csv",
    "dimensionality_stratification.csv", "duration_dimensionality_matrix.csv",
    "association_statistics.csv", "adjusted_score_analysis.csv",
    "confound_analysis_report.json", "confound_analysis_interpretation.md",
]
OPTIONAL = ["structural_model_results.csv"]
SOURCE_FILES = [
    ROOT / "inspection" / "class3_detector_v1.py",
    ROOT / "inspection" / "class3_detector_v2" / "class3_detector_v2.py",
    ROOT / "inspection" / "class3_detector_results.csv",
    ROOT / "inspection" / "class3_detector_evaluation.csv",
    EVAL, ROOT / "inspection" / "class3_detector_v1_broader_evaluation_v1" / "broader_v1_event_results.csv",
    ROOT / "inspection" / "mission1" / "labels.csv",
    ROOT / "inspection" / "mission1" / "anomaly_types.csv",
    ROOT / "inspection" / "mission1" / "channels.csv",
    FRAME, ROOT / "inspection" / "esa_broader_control_characterization_v1" / "feature_table.csv",
    ROOT / "external" / "opssat-ad" / "data" / "raw" / "dataset.csv",
    ROOT / "external" / "opssat-ad" / "data" / "raw" / "segments.csv",
    ROOT / "yamcs" / "actual_server" / "smoke_test_result.json",
    ROOT / "yamcs" / "actual_server" / "six_case_equivalence" / "outputs" / "score_equivalence_report.json",
    ROOT / "yamcs" / "actual_server" / "six_case_equivalence" / "readiness_failure_forensic_report.md",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def source_hashes() -> dict:
    return {str(p.relative_to(ROOT)): sha256(p) if p.exists() else "MISSING" for p in SOURCE_FILES}


def clean_num(x):
    if isinstance(x, (np.integer, np.floating)):
        return x.item()
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return x


def records(df: pd.DataFrame) -> list[dict]:
    return [{k: clean_num(v) for k, v in row.items()} for row in df.to_dict(orient="records")]


def summary(df: pd.DataFrame, population: str = "controls") -> dict:
    return {
        "population": population, "n": int(len(df)),
        "detected_count": int(df["detected"].sum()) if len(df) else 0,
        "detection_rate": float(df["detected"].mean()) if len(df) else None,
        "mean_score": float(df["score"].mean()) if len(df) else None,
        "median_score": float(df["score"].median()) if len(df) else None,
    }


def stratified(df: pd.DataFrame, col: str, order: list[str], name: str) -> pd.DataFrame:
    rows = []
    for s in order + [x for x in df[col].dropna().astype(str).unique() if x not in order]:
        g = df[df[col].astype(str) == s]
        if g.empty:
            continue
        rows.append({"stratum": s, "n": len(g), "detected_count": int(g.detected.sum()),
                     "detection_rate": g.detected.mean(), "median_score": g.score.median(),
                     "mean_score": g.score.mean(), "median_duration_seconds": g.duration_seconds.median(),
                     "median_channel_count": g.channel_count.median(), "sparse_flag": len(g) < 5,
                     "stratification": name, "population": "controls"})
    return pd.DataFrame(rows)


def association(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for x, label in [("duration_seconds", "duration"), ("channel_count", "channel_count"),
                     ("log_duration", "log_duration"), ("log_channel_count", "log_channel_count")]:
        q = df[["score", x]].replace([np.inf, -np.inf], np.nan).dropna()
        for method, fn in [("pearson", stats.pearsonr), ("spearman", stats.spearmanr)]:
            r = fn(q["score"], q[x])
            rows.append({"population": "controls", "score_variable": "detector_score",
                         "structural_variable": label, "method": method, "n": len(q),
                         "statistic": float(r.statistic), "p_value_descriptive": float(r.pvalue),
                         "interpretation": "descriptive association; not causal"})
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    prior = {}
    for name in STRUCTURED + OPTIONAL:
        p = OUT / name
        if p.exists() and name != "confound_analysis_interpretation.md":
            prior[name] = sha256(p)
    before = source_hashes()

    ev = pd.read_csv(EVAL)
    fr = pd.read_csv(FRAME)
    controls = ev[ev["label"] == "LABEL_NEGATIVE_UNLABELLED"].copy()
    positives = ev[ev["label"] == "POSITIVE"].copy()
    if len(controls) != 170 or len(positives) != 30:
        raise RuntimeError(f"Unexpected fixed population: controls={len(controls)}, positives={len(positives)}")
    keep = ["event_id", "source_event_id", "duration_seconds", "channel_count", "duration_bucket",
            "channel_bucket", "telemetry_quality"]
    # The frozen broader evaluation leaves event_id null for controls and carries
    # their source key in source_event_id; join to the control frame by that key.
    m = controls.merge(fr[keep], left_on="source_event_id", right_on="source_event_id",
                       how="left", validate="many_to_one", suffixes=("_eval", "_frame"))
    if m["duration_seconds_frame"].isna().any() or m["channel_count_frame"].isna().any():
        raise RuntimeError("Control structural feature merge is incomplete")
    d = pd.DataFrame({
        "control_id": m.event_id_frame, "event_id": m.event_id_frame, "source_event_id": m.source_event_id,
        "score": m.detector_score.astype(float), "detected": m.detected.astype(bool),
        "duration_seconds": m.duration_seconds_frame.astype(float),
        "channel_count": m.channel_count_frame.astype(float), "duration_bucket": m.duration_bucket,
        "channel_bucket": m.channel_bucket, "telemetry_quality": m.telemetry_quality,
    })
    d["log_duration"] = np.where(d.duration_seconds > 0, np.log(d.duration_seconds), np.nan)
    d["log_channel_count"] = np.where(d.channel_count > 0, np.log(d.channel_count), np.nan)
    d["insufficient_telemetry"] = d.telemetry_quality.eq("INSUFFICIENT_TELEMETRY")
    d["control_quality"] = np.where(d.insufficient_telemetry, "INSUFFICIENT_TELEMETRY", "GOOD_CONTROL")
    d["source_population"] = "predetermined broader-v1 controls"
    d = d[["control_id", "event_id", "source_event_id", "score", "detected", "duration_seconds",
           "log_duration", "channel_count", "log_channel_count", "duration_bucket", "channel_bucket",
           "telemetry_quality", "insufficient_telemetry", "control_quality", "source_population"]]
    d.to_csv(OUT / "control_structural_features.csv", index=False, float_format="%.15g")

    dur = stratified(d, "duration_bucket", ["IMPULSIVE", "SHORT", "MEDIUM", "LONG", "PERSISTENT"], "duration_bucket")
    dim = stratified(d, "channel_bucket", ["1-6", "7-12", "13-26"], "channel_bucket")
    dur.to_csv(OUT / "duration_stratification.csv", index=False, float_format="%.15g")
    dim.to_csv(OUT / "dimensionality_stratification.csv", index=False, float_format="%.15g")

    mat_rows = []
    for (db, cb), g in d.groupby(["duration_bucket", "channel_bucket"], sort=False):
        mat_rows.append({"duration_bucket": db, "channel_bucket": cb, "n": len(g),
                         "detected_count": int(g.detected.sum()), "detection_rate": g.detected.mean(),
                         "median_score": g.score.median(), "mean_score": g.score.mean(),
                         "median_duration_seconds": g.duration_seconds.median(),
                         "median_channel_count": g.channel_count.median(), "sparse_flag": len(g) < 5})
    pd.DataFrame(mat_rows).to_csv(OUT / "duration_dimensionality_matrix.csv", index=False, float_format="%.15g")
    assoc = association(d)
    assoc.to_csv(OUT / "association_statistics.csv", index=False, float_format="%.15g")

    model_d = d.replace([np.inf, -np.inf], np.nan).dropna(subset=["log_duration", "log_channel_count"]).copy()
    X = sm.add_constant(model_d[["log_duration", "log_channel_count"]], has_constant="add")
    logit = sm.Logit(model_d.detected.astype(int), X).fit(disp=False, maxiter=200)
    stable = bool(logit.mle_retvals.get("converged", False) and np.isfinite(logit.params).all() and np.isfinite(logit.bse).all())
    model_status = "stable" if stable else "unstable_or_nonconverged"
    if stable:
        ci = logit.conf_int()
        rows = []
        for term in X.columns:
            rows.append({"term": term, "coefficient": logit.params[term], "odds_ratio": np.exp(logit.params[term]),
                         "ci_low": ci.loc[term, 0], "ci_high": ci.loc[term, 1], "p_value": logit.pvalues[term],
                         "n": len(model_d), "model": "detected ~ log(duration_seconds) + log(channel_count)",
                         "status": model_status, "interpretation": "associational; not causal"})
        pd.DataFrame(rows).to_csv(OUT / "structural_model_results.csv", index=False, float_format="%.15g")
    elif (OUT / "structural_model_results.csv").exists():
        (OUT / "structural_model_results.csv").unlink()

    def ols_adjust(df_in, cols):
        z = sm.add_constant(df_in[list(cols)], has_constant="add")
        fit = sm.OLS(df_in.score, z).fit()
        pred = fit.predict(z)
        return fit, pred

    fit_both, pred_both = ols_adjust(model_d, ["log_duration", "log_channel_count"])
    adj = d.copy()
    pred_all = pd.Series(np.nan, index=d.index, dtype=float)
    pred_all.loc[model_d.index] = pred_both
    adj["predicted_structural_score"] = pred_all
    adj["structural_residual"] = adj.score - pred_all
    adj["adjusted_score_descriptive"] = adj.score.mean() + adj.structural_residual
    adj["analysis_only_not_detector_output"] = True
    adj.to_csv(OUT / "adjusted_score_analysis.csv", index=False, float_format="%.15g")

    sens = []
    for label, sub, cols, analysis_col, note in [
        ("all_controls_raw", d, [], "score", "canonical broader-v1 control population"),
        ("sufficient_telemetry_raw", d[~d.insufficient_telemetry], [], "score", "excludes insufficient-telemetry controls; descriptive sensitivity"),
    ]:
        sens.append({"sensitivity": label, "n": len(sub), "detected_count": int(sub.detected.sum()),
                     "detection_rate": sub.detected.mean(), "mean_analysis_score": sub[analysis_col].mean(),
                     "median_analysis_score": sub[analysis_col].median(), "model": "none", "note": note})
    for label, cols, note in [
        ("duration_adjusted", ["log_duration"], "residualized score; classifications unchanged"),
        ("dimensionality_adjusted", ["log_channel_count"], "residualized score; classifications unchanged"),
        ("both_adjusted", ["log_duration", "log_channel_count"], "residualized score; classifications unchanged"),
    ]:
        fit, pred = ols_adjust(model_d, cols)
        r = model_d.score - pred
        sens.append({"sensitivity": label, "n": len(model_d), "detected_count": int(model_d.detected.sum()),
                     "detection_rate": model_d.detected.mean(), "mean_analysis_score": r.mean(),
                     "median_analysis_score": r.median(), "model": "score ~ 1 + " + " + ".join(cols), "note": note})
    pd.DataFrame(sens).to_csv(OUT / "sensitivity_analysis.csv", index=False, float_format="%.15g")

    # Small deterministic diagnostics; these do not alter detector outputs.
    plt.figure(figsize=(7, 4)); plt.scatter(d.duration_seconds, d.score, c=d.detected.map({True: "#c43c39", False: "#4878a8"}), s=18)
    plt.xscale("log"); plt.xlabel("Duration (seconds, log scale)"); plt.ylabel("Frozen Detector v1 score"); plt.tight_layout(); plt.savefig(OUT / "score_vs_duration.png", dpi=140); plt.close()
    plt.figure(figsize=(7, 4)); plt.scatter(d.channel_count, d.score, c=d.detected.map({True: "#c43c39", False: "#4878a8"}), s=18)
    plt.xlabel("Channel count"); plt.ylabel("Frozen Detector v1 score"); plt.tight_layout(); plt.savefig(OUT / "score_vs_channel_count.png", dpi=140); plt.close()
    pivot = d.pivot_table(index="duration_bucket", columns="channel_bucket", values="detected", aggfunc=["count", "mean"])
    plt.figure(figsize=(7, 4)); plt.imshow(pivot["mean"].fillna(np.nan), aspect="auto", cmap="viridis", vmin=0, vmax=1); plt.colorbar(label="Detection rate"); plt.xticks(range(len(pivot.columns)), pivot.columns); plt.yticks(range(len(pivot.index)), pivot.index); plt.xlabel("Channel bucket"); plt.ylabel("Duration bucket"); plt.tight_layout(); plt.savefig(OUT / "duration_dimensionality_heatmap.png", dpi=140); plt.close()
    plt.figure(figsize=(7, 4)); plt.hist([d.score[d.detected], adj.adjusted_score_descriptive[d.detected]], bins=12, alpha=.55, label=["raw detected", "adjusted descriptive detected"]); plt.legend(); plt.xlabel("Score / analysis-only adjusted score"); plt.tight_layout(); plt.savefig(OUT / "raw_vs_adjusted_score_distribution.png", dpi=140); plt.close()

    after = source_hashes()
    integrity = {k: {"before": before[k], "after": after[k], "unchanged": before[k] == after[k]} for k in before}
    report = {
        "analysis_version": "duration_dimensionality_confound_analysis_v1",
        "fixed_population": {"positives": len(positives), "controls": len(d), "total": len(positives) + len(d), "control_detection_count": int(d.detected.sum()), "control_detection_rate": float(d.detected.mean())},
        "strata_source": "existing control_sampling_frame.csv; bins reused exactly as stored",
        "duration_stratification": records(dur), "dimensionality_stratification": records(dim),
        "duration_dimensionality_matrix": records(pd.read_csv(OUT / "duration_dimensionality_matrix.csv")),
        "association_statistics": records(assoc), "logistic_model_status": model_status,
        "logistic_model_specification": "detected ~ log(duration_seconds) + log(channel_count)",
        "residual_model": {"specification": "score ~ 1 + log(duration_seconds) + log(channel_count)", "descriptive_only": True, "detector_output": False},
        "sensitivity_analysis": records(pd.DataFrame(sens)), "integrity": integrity,
        "conclusion": "C" if model_status == "stable" else "D",
        "limitations": ["Controls are predetermined negative-unlabelled templates, not proven nominal telemetry.", "Sparse strata are flagged and not interpreted as stable subgroup effects.", "Associations and residuals are descriptive and do not establish causation or replace detector scores."],
        "runtime": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__},
    }
    (OUT / "confound_analysis_report.json").write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")

    md = f"""# Duration–Dimensionality Confound Analysis v1\n\n## Scope and population\n\nThis analysis is descriptive and uses the predetermined broader Detector v1 population: 30 Class-3 positives and 170 `LABEL_NEGATIVE_UNLABELLED` controls. The canonical broader control detection rate remains **{int(d.detected.sum())}/170 = {d.detected.mean():.4f}**. No detector, threshold, label, telemetry, or historical artifact was modified.\n\n## What the analysis showed\n\n1. Duration and channel-count associations with the frozen Detector v1 score are reported in `association_statistics.csv`; they are descriptive Pearson/Spearman associations.\n2. Existing duration and channel strata and their two-dimensional matrix are reported without bin optimization. Sparse cells are explicitly flagged.\n3. The prespecified logistic model status is **{model_status}**.\n4. The score residualization is analysis-only and is not a new detector score.\n\n## What it does not show\n\nThe analysis does not prove that duration or channel dimensionality causes detections, does not establish that controls are nominal, and does not justify changing Detector v1 or its threshold. It does not convert residualized scores into detector classifications.\n\n## Recommended paper wording\n\nThe broader control population showed a non-zero frozen-detector detection rate, and score/detection patterns were examined against pre-existing telemetry duration and channel dimensionality. These analyses are descriptive and intended to characterize possible structural association; they do not establish that telemetry duration or dimensionality is the causal source of the observed detections.\n\n## Required interpretation\n\n- **Are detected controls concentrated in longer-duration telemetry?** See `duration_stratification.csv`; any apparent concentration must be read with the recorded cell sizes and sparse flags.\n- **Are detected controls concentrated in higher-dimensional telemetry?** See `dimensionality_stratification.csv`; any apparent concentration is descriptive only.\n- **Does the 2D matrix show a monotonic structural pattern?** See `duration_dimensionality_matrix.csv`; no monotonicity claim is made from sparse or uneven cells.\n- **Does adjustment materially reduce detected-control scores?** See `adjusted_score_analysis.csv`; residualization changes an analysis scale only and leaves frozen classifications unchanged.\n\n## Conclusion\n\n**Conclusion {"C" if model_status == "stable" else "D"}:** duration and dimensionality may contribute to score variation and are reported as possible structural associations, but this analysis does not establish that they explain the detected controls.\n\nGenerated deterministically by `run_duration_dimensionality_confound_analysis.py`.\n"""
    (OUT / "confound_analysis_interpretation.md").write_text(md, encoding="utf-8")

    current = {name: sha256(OUT / name) for name in STRUCTURED + OPTIONAL if (OUT / name).exists()}
    repro = {"analysis_version": "duration_dimensionality_confound_analysis_v1", "reproducibility_status": "PASS" if prior and all(prior.get(k) == v for k, v in current.items() if k in prior) else "NOT_YET_COMPARED", "compared_previous_output_hashes": bool(prior), "output_sha256": current, "source_sha256_before": before, "source_sha256_after": after, "source_integrity_unchanged": all(v["unchanged"] for v in integrity.values())}
    (OUT / "confound_analysis_reproducibility.json").write_text(json.dumps(repro, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {"analysis_version": "duration_dimensionality_confound_analysis_v1", "allowed_output_directory": str(OUT), "inputs": {"evaluation": str(EVAL.relative_to(ROOT)), "control_frame": str(FRAME.relative_to(ROOT))}, "source_sha256_before": before, "source_sha256_after": after, "generated_files": sorted([p.name for p in OUT.iterdir() if p.is_file()]), "frozen_inputs_unchanged": all(v["unchanged"] for v in integrity.values()), "note": "Manifest and reproducibility files are metadata; no source artifact was rewritten."}
    (OUT / "confound_analysis_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"controls": len(d), "detections": int(d.detected.sum()), "logistic_status": model_status, "reproducibility": repro["reproducibility_status"], "output": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
