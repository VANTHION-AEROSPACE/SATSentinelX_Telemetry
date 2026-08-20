# IAAI results inventory

## Introduction / dataset
Strongest evidence: ESA Mission-1 reconstruction, 200 event IDs, 30 Class-3 events, and explicit metadata/telemetry limitations.

## Method / forensic analysis
Strongest evidence: frozen Detector v1 formulas, Class-3 channel/event analyses, and auditable scale/morphology definitions.

## Detector / control studies
Primary broader result: 30 Class-3 + 170 `LABEL_NEGATIVE_UNLABELLED` controls: TP=30, FP=40, TN=130, FN=0; FPR=23.5%. Strong-only is secondary (29/2/168/1).

## Experimental negative result
v2 did not resolve the observed failure modes and is not the final detector.

## External study
OPSSAT-AD is a protocol/domain-shift study, not direct v1 validation; robust_max ROC-AUC was approximately 0.483.

## Operational study
Yamcs demonstration pending.

## Tables / figures
The audit CSVs and generated figures provide score distributions, ROC/PR, stratified FPR, false-positive composition, and score-vs-duration/channel-count views.

## Missing evidence
Confirmed nominal controls, full telemetry-channel reconstruction, prospective operational validation, and deployment acceptance evidence.
