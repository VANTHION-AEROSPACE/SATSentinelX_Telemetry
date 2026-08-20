# OPSSAT-AD external validation status

1. Dataset successfully acquired? **YES** — official Zenodo assets were downloaded into `data/raw/`.
2. Dataset schema verified? **YES** — actual CSV files were inspected and recorded in `inspection/opssat_raw_schema_actual.json`.
3. Official train/test split identified? **YES** — actual files contain 1,594 train and 529 test segments.
4. Frozen Detector v1 compatible? **PARTIAL / NO for direct execution** — the fragment schema does not establish the continuous baseline and multivariate event contract required for an unchanged Class-3 evaluation.
5. Adapter required? **YES, if a future methodologically approved transfer is attempted.**
6. Adapter implemented? **NO** — creating one would silently change v1 semantics.
7. Dry run passed? **NOT APPLICABLE** — no Detector v1 adapter was run.
8. Full direct evaluation run? **NO**. Protocol-level experiment: **YES**.
9. Protocol-level metrics? **YES** — reported separately in `inspection/opssat_protocol_report.json`.
10. Main failure modes: weak robust-fragment discrimination, low anomaly recall, timestamp irregularity, single-channel fragment semantics, cross-mission domain shift.
11. Did v1 generalize? **UNDETERMINED** — this was not direct v1 validation.
12. Evidence sufficient to justify Detector v2? **NO**.

Protocol-level experiment result: the primary robust raw-fragment method was
run on the official 529-segment test split using thresholds frozen from train
nominal data only. ROC-AUC was 0.483, PR-AUC 0.195, recall 0.000, and FPR
0.007. This is protocol-level evidence only and is not direct Detector v1
validation. Reproducibility check: PASS.

The official acquisition manifest, actual schema, and readiness assessment are
recorded under `inspection/`. No ESA Mission 1 artifacts were modified.

EXTERNAL_VALIDATION_INCOMPLETE
