# Yamcs readiness assessment

## Ready
Frozen Detector v1, its score/classification outputs, ESA event metadata, control manifests, reproducible evaluation package, and representative telemetry windows are available for a controlled demonstration.

## Not ready / missing
The live Yamcs telemetry adapter, message/schema mapping, timing/clock policy, alert transport, operational nominal reference set, and acceptance criteria are not yet demonstrated. Only 26 of 76 metadata channels have reconstructed telemetry in this workspace.

## Science-preserving implementation
Implement ingestion, timestamp normalization, channel mapping, replay controls, logging, and visualization around the immutable v1 interface. Do not alter formulas, thresholds, weights, labels, or control definitions.

## Proposed replay matrix
|Case|ID|Reason|Expected behavior|Demo purpose|
|---|---|---|---|---|
|Impulsive Class-3|id_118|Zero-duration/point event|High v1 score; detected|Boundary and timestamp handling|
|Short Class-3|id_109|Short high-evidence event|Detected strongly|Short-window response|
|Medium Class-3|id_172|Medium morphology|Detected|Intermediate duration handling|
|Long/persistent Class-3|id_183|Long-duration multivariate event|Detected; inspect persistence|Long-window behavior|
|Difficult label-negative|control_0001|Broader moderate-evidence false positive|May trigger|Transparent false-positive behavior|
|High-dimensional false positive|control_0066|6-channel core example; use control_0001 or control_0069 for 26-channel high-dimensional behavior|Potential detection|Channel-group/dimensionality bias demonstration|

The Yamcs phase should expose telemetry, baseline/scale provenance, per-channel evidence, event score, classification, quality flags, and audit logs. This document defines the experiment only; it does not implement Yamcs.
