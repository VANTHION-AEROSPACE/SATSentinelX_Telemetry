# Duration–Dimensionality Analysis v1

## Purpose
Characterize whether frozen Detector v1 score and control-detection behavior are structurally associated with telemetry duration and channel dimensionality. This is the final forensic addition; it is not detector development.

## Population
The predetermined broader population contains 30 Class-3 positives and 170 `LABEL_NEGATIVE_UNLABELLED` controls. The authoritative primary broader-control result remains 40/170 = 23.5294%. Controls are not proven nominal.

## Methods
Existing duration and channel buckets were reused without optimization. Pearson and Spearman associations were computed for score versus duration and channel count. Existing one-dimensional strata and a two-dimensional duration/channel matrix were reported. A prespecified logistic model, `detected ~ log(duration) + log(channel_count)`, was stable on finite-support rows (n=91). Analysis-only OLS residualization was performed for duration, dimensionality, and both together. Frozen classifications were not changed.

## Primary findings
Duration showed a positive descriptive association with score (Pearson r=0.360763; Spearman rho=0.444362; n=170). Channel count showed a strong descriptive association (Pearson r=0.910360; Spearman rho=0.892711; n=170). All 34 controls in the 13–26 channel stratum were detected.

## Structural associations and 2D stratification
Detections were concentrated in persistent and higher-dimensional strata, but the matrix is uneven and includes sparse cells. These patterns may reflect structural telemetry properties, channel availability, operating regime, or control construction. They do not isolate a causal mechanism.

## Residual analysis
Residualized scores are analysis-only values, not Detector v1 outputs. Residualization did not change frozen classifications or the canonical 40/170 result.

## Sensitivity analysis
The all-control analysis retained 40/170 detections. The sufficient-telemetry subset retained 40/92 detections. Duration-adjusted, dimensionality-adjusted and jointly adjusted residual summaries were descriptive only; no reclassification or threshold change was performed.

## Interpretation
Conclusion C / WEAK-INCONCLUSIVE: duration and dimensionality may contribute to score variation and are observed structural associations, but the evidence does not establish causation or prove detector failure. The analysis does not justify changing Detector v1.

## Limitations
Controls are label-negative/unlabelled rather than certified nominal; insufficient-telemetry rows have non-finite log support; strata are uneven and some cells are sparse; the analysis is observational; residuals are not detector scores; the dataset and reconstructed channel subset remain limited.

## Exact paper-safe wording
“The broader control population showed a non-zero frozen-detector detection rate, and score/detection patterns were examined against pre-existing telemetry duration and channel dimensionality. These analyses are descriptive and intended to characterize possible structural association; they do not establish that telemetry duration or dimensionality is the causal source of the observed detections.”
