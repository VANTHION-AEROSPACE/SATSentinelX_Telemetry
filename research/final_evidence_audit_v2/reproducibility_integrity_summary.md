# Reproducibility and integrity summary

The package preserves the reproducibility statuses reported by each existing experiment rather than recalculating experiments. ESA reconstruction, Class-3 analysis, initial controls, forensic audits, regime-aware controls, control characterization, v2, broader control characterization, broader v1 evaluation and OPSSAT protocol artifacts report PASS in their source manifests. The local deterministic Yamcs-compatible replay reported PASS. Actual Yamcs smoke testing passed. Actual Yamcs six-case equivalence passed 5/6; the archive-readiness investigation correctly reported a bounded timeout and is not a PASS for six-case completeness.

The frozen Detector v1 implementation hash is `527fe01d8a3c6abe6c46c3e9468a74adfe1d00252c28139fa069629f5ac4f71b`. The final audit does not modify Detector v1, historical evaluation outputs, Detector v2, ESA labels, ESA reconstructed telemetry, OPSSAT raw data, OPSSAT protocol artifacts, previous control studies, or previous forensic audits.

Integrity is evaluated as PASS for this consolidation package when the listed source hashes remain unchanged and all package hashes verify. Scientific reproducibility is reported as MIXED/FAIL for the complete Yamcs six-case acceptance criterion because one archive case remains incomplete. This package does not silently promote that failure to PASS.


## Final confound-analysis status

The duration/dimensionality analysis was run twice with reproducibility PASS. Protected detector, telemetry, label, OPSSAT, Yamcs and prior-analysis hashes were unchanged. Actual Yamcs integration remains demonstrated but incomplete for six-case equivalence: five cases passed and control_0069 remained limited by incomplete Parameter Archive historical coverage. This is an integration-completeness/deployment limitation, not a blanket claim that all research analyses are irreproducible.
