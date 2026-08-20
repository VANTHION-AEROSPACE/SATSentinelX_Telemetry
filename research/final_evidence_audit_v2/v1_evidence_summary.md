# Detector v1 evidence summary

## Frozen definition

Detector v1 is the immutable interpretable Class-3 event-level evidence model in `inspection/class3_detector_v1.py`. It compares event-window channel values with a preceding context baseline. It prefers robust MAD scale, then median absolute first-difference scale, then an explicit tolerance fallback. Channel evidence uses capped normalized deviation, anomalous fraction, strong evidence, and direction. The primary event rule is the frozen all-detected threshold (`ANOMALY_THRESHOLD=3.0`); strong evidence uses `STRONG_THRESHOLD=6.0`. The implementation hash is `527fe01d8a3c6abe6c46c3e9468a74adfe1d00252c28139fa069629f5ac4f71b`.

## Input assumptions

The available ESA representation contains 26 reconstructed telemetry channels from 76 metadata channels. Timestamps are normalized to UTC timezone-naive values. The evaluated Class-3 population contains 30 labeled events. Controls throughout the control studies are label-negative/unlabelled and are not proven nominal, healthy, or true negatives.

## Evidence sequence

The initial 30-positive/60-control evaluation reported TP=30, FP=22, TN=38, FN=0, recall=1.0 and FPR=36.67%. A post-hoc forensic audit found recurring duration, persistence, dimensionality, synchrony, channel-group, and scale-fallback patterns among detections. Regime-aware controls did not remove the observed behavior. The detector-independent control characterization found descriptive differences in robust deviation, persistence, channel count and synchrony but did not justify a detector revision.

The broader frozen v1 evaluation used the same 30 Class-3 positives and 170 predetermined `LABEL_NEGATIVE_UNLABELLED` controls. It reported TP=30, FP=40, TN=130, FN=0, recall=1.0, precision=0.4286, specificity=0.7647, FPR=23.5%, F1=0.6000 and balanced accuracy=0.8824. Continuous ranking metrics were ROC-AUC=0.9924 and PR-AUC=0.9794, which are sample- and prevalence-dependent and do not imply a safe operating threshold.

At the secondary strong-only operating point, the broader study reported 29/30 positive recall and 2/170 control detections, giving FPR=1.18%. This is not the primary rule, was not optimized for deployment, and must not be presented as the detector's general FPR.

## What v1 establishes

V1 establishes that the evaluated Class-3 events have measurable multivariate telemetry signatures and that the frozen evidence rule detected all 30 evaluated Class-3 positives under the stated ESA protocols. It also establishes that false-positive behavior is measurable and materially affected by duration, dimensionality, persistence, synchrony, channel grouping, and scale-estimation behavior.

## What v1 does not establish

“30/30 evaluated Class-3 positives” is not “general anomaly detection accuracy.” The evidence does not establish broad ESA generalization, low nominal false-positive rate, confirmed nominal specificity, external OPSSAT validation, operational validation, flight readiness, or a universal Class-3 signature. The broader evaluation FPR remains 23.5% against label-negative/unlabelled controls, and controls are not proven nominal.
