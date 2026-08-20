# Final paper evidence map

1. **Introduction** — Claim: applied evidence-driven telemetry evaluation and integration methodology. Artifact: paper_story_v1.md, experiment_registry.csv. Caveat: not a novel detector algorithm or flight validation. Prohibited: broad novelty or operational-readiness claims.

2. **System and Data** — Claim: real ESA Mission-1 reconstruction with 200 labeled IDs, 76 metadata channels and 26 reconstructed channels. Artifact: source inventory and E01/E02 artifacts. Caveat: partial channel reconstruction. Prohibited: complete operational telemetry coverage.

3. **Class-3 Characterization** — Claim: 30 heterogeneous Class-3 events were characterized. Artifact: Class-3 analysis outputs. Caveat: positive n=30. Prohibited: universal Class-3 signature.

4. **Frozen v1 Evaluation** — Claim: v1 detected 30/30 evaluated Class-3 events under the stated rule. Artifact: broader_v1_evaluation_report.json. Caveat: stated population only. Prohibited: 100% accuracy or broad sensitivity.

5. **Broader Controls and Forensic Analysis** — Claims: 40/170 controls detected; score/channel association; positives shorter than controls; channel-count shift modest; specific high-dimensional-positive explanation weakened; residual structural confound remains MODERATE. Artifacts: E21 confound package and E22 population comparison package. Caveat: controls not proven nominal; descriptive analyses are not causal. Prohibited: low confirmed FPR, dimensionality-caused false positives, or confound eliminated.

6. **External Stress Test** — Claim: OPSSAT-AD was a protocol/domain stress test, not direct v1 validation; robust_max ROC-AUC 0.4833. Artifact: OPSSAT protocol report. Caveat: semantic and protocol mismatch. Prohibited: OPSSAT validation or generalization.

7. **Yamcs Ground-System Integration** — Claim: actual Yamcs 5.13.2 pathway and smoke test demonstrated; five of six fixed equivalence cases passed. Artifacts: Yamcs smoke/equivalence/readiness reports. Caveat: control_0069 archive coverage incomplete. Prohibited: six-of-six equivalence or operational validation.

8. **Discussion** — Claim: structural context, control semantics, channel coverage and archive readiness are deployment lessons. Artifact: failure taxonomy, attack surface and population comparison. Caveat: one mission dataset and one external dataset. Prohibited: guaranteed operational success.

9. **Limitations** — Claim: small positives, unlabelled controls, partial reconstruction, moderate residual structural confound, OPSSAT mismatch and incomplete Yamcs archive coverage. Artifact: claim matrix, paper_safe_claims.md, integrity reports.

10. **Conclusion** — Claim: SATSentinel-X provides an evidence-backed applied workflow and transparent account of where evidence is strong, limited or unresolved. Artifact: paper_story_v1.md and final consolidation manifest. Caveat: research integration, not flight qualification.
