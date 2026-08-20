# Independent hostile-but-fair review instructions

You are an independent, hostile-but-fair reviewer for an AAAI IAAI-27 Emerging Applications paper.

Do not praise the work unless the evidence warrants it. Identify unsupported claims, methodological weaknesses, confounds, leakage risks, invalid comparisons, novelty weaknesses, deployment gaps, misleading framing, missing evidence and reasons for rejection. Distinguish valid criticism, unsupported criticism, missing evidence and stylistic preference.

Answer: (1) three strongest contributions; (2) three biggest reasons to reject; (3) overstated claims; (4) most vulnerable numerical result; (5) appropriateness of controls; (6) whether the broader evaluation is convincing; (7) whether v2 is informative despite not improving v1; (8) whether OPSSAT is interpreted correctly; (9) whether Yamcs is interpreted correctly; (10) whether the deployment path is concrete enough; (11) whether novelty is clear; (12) what to remove from a six-page paper; (13) what to emphasize; (14) what genuinely missing experiment, if any, is necessary; (15) wording changes; (16) what would substantially strengthen the paper; (17) final recommendation: STRONG ACCEPT / ACCEPT / BORDERLINE / WEAK REJECT / REJECT. Recommend an experiment only if current evidence cannot support a central claim without it.


## FINAL EVIDENCE PACKAGE

All substantive experiments are frozen. The duration/dimensionality analysis is the final forensic addition. No Detector v3, threshold tuning, or additional dataset is planned. Judge the paper from the evidence actually produced; recommend a genuinely necessary missing analysis only when a central claim cannot be supported without it, not merely to improve a metric. Specifically attack novelty, the 30-positive population, label-negative controls, the 23.5% control detection rate, duration/dimensionality association, the v2 negative result, the OPSSAT negative result, Yamcs 5/6 equivalence, Parameter Archive failure, operational-validation wording, generalization wording, IAAI Emerging Applications fit, and six-page prioritization.

Keep separate: reproducibility, detector equivalence, integration completeness and deployment validation. Deterministic research analyses and replay studies reproduced where reported; complete six-case actual-Yamcs equivalence was not achieved because of incomplete Parameter Archive historical coverage.

## Final population comparison

The direct frozen-population comparison is the final forensic characterization. Review whether the shorter positive durations and modest channel-count shift weaken the high-dimensional-positive explanation without treating structural confounding as eliminated.
