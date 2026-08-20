# Duration–Dimensionality Population Comparison v1

This analysis compares the frozen 30 established Class-3 positives with the frozen 170 predetermined `LABEL_NEGATIVE_UNLABELLED` controls. Detector outputs did not define, select, or remove observations.

## Result

Classification: **B_MODERATELY_SHIFTED**. Structural-confound status: **MODERATE**. The standardized descriptive contrasts, non-parametric comparisons, overlaps, and existing-bin counts are in the CSV outputs.

1. **Duration:** positives are structurally different from controls by the descriptive standardized contrast.
2. **Channel dimensionality:** positives are not strongly shifted from controls by the descriptive standardized contrast.
3. **Detector concern:** this strengthens concern that detector behavior may partly reflect structural properties, while preserving the prior score/channel-count association.
4. **30/30:** remains valid only for the stated evaluated Class-3 population and does not support broad generalization.
5. **23.53%:** the canonical 40/170 = 23.5294% control-detection rate is unchanged; this comparison does not make it a nominal FPR.
6. **Detector modification:** NO. This is characterization only and does not justify changing Detector v1.

Duration and dimensionality differences do not prove that either property causes detections.

## STRUCTURAL-CONFOUND STATUS: MODERATE

This status reflects observed population shifts, not detector performance or a causal conclusion.
