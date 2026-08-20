# IAAI-27 paper story v1

1. **Problem.** Spacecraft telemetry anomaly analysis must operate with heterogeneous channels, sparse labels, changing regimes and deployment constraints.
2. **Motivation.** Real spacecraft data expose failure modes hidden by clean benchmarks.
3. **Contribution.** SATSentinel-X combines an interpretable robust evidence model with a forensic evaluation and a concrete Yamcs integration path.
4. **Architecture.** ESA reconstruction -> channel/event representation -> frozen v1 evidence -> controls and external protocol study -> Yamcs parameter pathway.
5. **Real ESA data.** Mission-1 contains 200 labeled event IDs, 76 metadata channels and 26 reconstructed telemetry channels in the available workspace.
6. **Class-3 morphology.** Thirty Class-3 events span heterogeneous global/local, impulsive, short, medium, long and persistent patterns.
7. **Detector v1.** A frozen robust baseline/evidence model detects event-level deviations with explicit scale provenance and strong-evidence semantics.
8. **Controlled evaluation.** V1 detects 30/30 evaluated positives, but broader label-negative/unlabelled control detection is 40/170.
9. **Failure discovery.** Duration, dimensionality, synchrony, channel grouping, persistence and scale behavior shape evidence.
10. **V2 hypothesis.** A fixed top-k/persistence/direction/scale/regime formulation tests whether these factors can be separated.
11. **V2 result.** V2 does not improve v1: it retains 22 FP and loses one positive.
12. **Broader controls.** The broader study makes alert-burden and control nominality limitations visible rather than hiding them.
13. **OPSSAT stress test.** OPSSAT-AD is a separate protocol/domain stress test, not direct frozen-v1 validation; robust_max AUC is .4833.
14. **Yamcs integration.** Actual Yamcs 5.13.2 loads a 26-parameter XTCE model and receives UDP parameter data.
15. **Deployment limitation.** The smoke test passes and five fixed equivalence cases pass, but control_0069 archive coverage is incomplete and readiness polling times out.
16. **Practical lessons.** Data contracts, control semantics, scale provenance, channel coverage and archive readiness must be first-class deployment artifacts.
17. **Limitations.** Small positive population, unlabelled controls, partial reconstruction, domain mismatch and no operational flight validation.
18. **Deployment path.** Add nominally certified controls, explicit regime context, archive completeness gates, ground-system monitoring and prospective acceptance testing.
19. **Conclusion.** The contribution is an evidence-backed applied workflow and a transparent account of where robust telemetry AI works, fails and remains unvalidated.

## One-sentence contribution
SATSentinel-X is an interpretable spacecraft-telemetry evidence workflow that combines real ESA analysis, frozen-detector stress testing, external protocol evaluation and actual Yamcs integration while making unresolved failure modes explicit.

## 100-word contribution
SATSentinel-X studies spacecraft telemetry anomaly evidence under realistic constraints: partial channel reconstruction, heterogeneous Class-3 events, ambiguous label-negative controls, external domain shift and ground-system integration. A frozen robust Detector v1 detects all 30 evaluated Class-3 positives, but broader controls yield a 23.5% label-negative/unlabelled control detection rate. A fixed Detector v2 does not improve the trade-off. OPSSAT-AD provides a separate stress test with robust_max ROC-AUC .4833 rather than direct v1 validation. Actual Yamcs 5.13.2 demonstrates the UDP-to-parameter pathway and five of six fixed equivalence cases, while archive incompleteness prevents six-of-six acceptance.

## 250-word abstract concept
Spacecraft telemetry anomaly detection is often evaluated as if channels, labels, operating regimes and deployment interfaces were clean and stable. SATSentinel-X examines these assumptions using reconstructed ESA Mission-1 telemetry, an interpretable frozen evidence model, deliberately conservative controls, an independent OPSSAT-AD protocol study and an actual Yamcs ground-system pathway. The available ESA workspace contains 200 labeled event IDs, 76 metadata channels and 26 reconstructed telemetry channels; 30 Class-3 events form the positive population. Frozen Detector v1 detects 30/30 evaluated Class-3 positives under the primary rule, but the broader evaluation detects 40/170 label-negative/unlabelled controls, so the result is high recall on a stated population rather than general anomaly accuracy or low nominal false-positive operation. Failure-mode analysis identifies duration, persistence, dimensionality, synchrony, channel grouping and scale fallback as important influences. A fixed Detector v2 tests these hypotheses but retains the same false-positive count and loses one positive, so it does not replace v1. OPSSAT-AD is not semantically compatible with direct v1 validation; its predeclared robust protocol gives ROC-AUC .4833 and PR-AUC .1950. Actual Yamcs 5.13.2 loads a 26-parameter XTCE model and passes a real ESA smoke test. Five of six fixed actual-Yamcs equivalence cases pass; control_0069 remains incomplete because Parameter Archive backfill does not provide complete historical row coverage, even after condition-based readiness polling. The study’s contribution is therefore an applied, reproducible account of detector evidence, failure discovery and deployment lessons, not flight qualification or broad generalization.

## Three strongest claims
1. The frozen v1 detector detected all 30 evaluated Class-3 positives under the stated ESA primary rule.
2. The study exposed measurable duration/dimensionality/scale/control-semantic failure modes rather than hiding them.
3. The ESA-to-UDP-to-Yamcs-parameter pathway was demonstrated with a real smoke test and five successful fixed-case equivalence results.

## Three most important limitations
1. Only 30 labeled Class-3 positives and no proven nominal controls.
2. Only 26 of 76 metadata channels have reconstructed telemetry in the available workspace.
3. OPSSAT transfer and complete actual-Yamcs six-case equivalence were not established.

## Five strongest quantitative results
- 30/30 evaluated Class-3 positives detected by frozen v1.
- Broader v1 control detection rate 40/170 = 23.5% against label-negative/unlabelled controls.
- Strong-only broader point: 29/30 recall and 2/170 = 1.18% control detection.
- OPSSAT robust_max ROC-AUC .4833.
- Actual Yamcs smoke value exact match: .9624888896942139 with preserved generation time.

## Five numbers requiring caveats
30/30; 23.5%; 1.18%; .9924 ROC-AUC; 5/6 Yamcs equivalence.


## Final duration/dimensionality forensic finding

The final forensic analysis used the predetermined 30-positive/170-control broader-v1 population. Frozen Detector v1 detected all 30 evaluated Class-3 positives, while 40/170 label-negative/unlabelled controls were detected under the primary rule. Detector score was positively associated with duration and strongly associated with channel count in the examined controls; all 34 controls in the 13–26-channel stratum were detected. These are descriptive structural associations, not evidence that duration or dimensionality causes false positives. Analysis-only residualization did not change frozen classifications, so Detector v1 was not modified. The result is a deployment/evaluation lesson: structural context, channel coverage, control semantics and archive readiness must be treated as first-class evidence constraints.

The final conclusion is deliberately intermediate: the analysis identifies possible structural contributors to observed control detections but does not establish causation, prove detector failure, or justify a detector revision.

## Final population-comparison integration

The direct comparison of the frozen 30 Class-3 positives with the 170 predetermined label-negative/unlabelled controls adds an important qualification. Class-3 positives were shorter than controls, while channel count showed only a modest standardized shift toward higher values; only 2/30 positives were in the 13–26 channel bin versus 34/170 controls. Thus the specific hypothesis that the 30/30 result is explained by substantially higher dimensionality among positives is weakened, but structural comparability remains limited. The result is a final evaluation lesson, not a detector revision.
