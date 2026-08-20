# Duration–Dimensionality Confound Analysis v1

## Scope and population

This analysis is descriptive and uses the predetermined broader Detector v1 population: 30 Class-3 positives and 170 `LABEL_NEGATIVE_UNLABELLED` controls. The canonical broader control detection rate remains **40/170 = 0.2353**. No detector, threshold, label, telemetry, or historical artifact was modified.

## What the analysis showed

1. Duration and channel-count associations with the frozen Detector v1 score are reported in `association_statistics.csv`; they are descriptive Pearson/Spearman associations.
2. Existing duration and channel strata and their two-dimensional matrix are reported without bin optimization. Sparse cells are explicitly flagged.
3. The prespecified logistic model status is **stable**.
4. The score residualization is analysis-only and is not a new detector score.

## What it does not show

The analysis does not prove that duration or channel dimensionality causes detections, does not establish that controls are nominal, and does not justify changing Detector v1 or its threshold. It does not convert residualized scores into detector classifications.

## Recommended paper wording

The broader control population showed a non-zero frozen-detector detection rate, and score/detection patterns were examined against pre-existing telemetry duration and channel dimensionality. These analyses are descriptive and intended to characterize possible structural association; they do not establish that telemetry duration or dimensionality is the causal source of the observed detections.

## Required interpretation

- **Are detected controls concentrated in longer-duration telemetry?** See `duration_stratification.csv`; any apparent concentration must be read with the recorded cell sizes and sparse flags.
- **Are detected controls concentrated in higher-dimensional telemetry?** See `dimensionality_stratification.csv`; any apparent concentration is descriptive only.
- **Does the 2D matrix show a monotonic structural pattern?** See `duration_dimensionality_matrix.csv`; no monotonicity claim is made from sparse or uneven cells.
- **Does adjustment materially reduce detected-control scores?** See `adjusted_score_analysis.csv`; residualization changes an analysis scale only and leaves frozen classifications unchanged.

## Conclusion

**Conclusion C:** duration and dimensionality may contribute to score variation and are reported as possible structural associations, but this analysis does not establish that they explain the detected controls.

Generated deterministically by `run_duration_dimensionality_confound_analysis.py`.
