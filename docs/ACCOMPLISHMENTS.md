# Evidence-backed accomplishments

| Milestone | Evidence | Verification | Status / limitation |
|---|---|---|---|
| Receiver and acceptance gate | `physical_demo/receiver.py`, `physical_demo/tests/test_receiver.py` | Offline tests cover framing, UTF-8, malformed JSON, sequence/time, gaps, unverified status and partial runs | Software path implemented; hardware acceptance remains failed |
| Hardware-independent dashboard | `physical_demo/dashboard.py`, `physical_demo/dashboard/` | Dashboard/replay/power tests and `node --check` | Local/demo workflow; browser and physical hardware are separate gates |
| Thermal synthetic evidence | `physical_demo/synthetic_detector.py`, fixtures, replay tests | Exact record references and deterministic replay | Not ESA reproduction and not Detector v1 validation |
| Synthetic power policy | `physical_demo/power_autonomy.py` | Success, escalation, reset, policy and evidence tests | Simulated action only; no spacecraft control |
| Frozen Detector v1 research | `inspection/class3_detector_v1.py`, historical reports | Historical Mission 1 results retained | Limited false-positive performance; immutable |
| Reproduction package | `reproduction/v1/` | Two-run synthetic output equality and source hash recorded | Current report has `environment_matches_pinned: false` (NumPy 2.4.6 vs pinned 1.26.4) |
| OPS-SAT-AD protocol evaluation | `external/opssat-ad/inspection/opssat_protocol_report.json` | Hash/integrity and deterministic protocol report | Robust method ROC-AUC 0.483, PR-AUC 0.195, recall 0/113 test anomalies; weak result |
| Yamcs adapter/local replay | `yamcs/yamcs_replay_report.json` | Deterministic adapter evidence | Actual Yamcs server not executed; control_0069 archive coverage mismatch |
| Firmware build artifact | `physical_demo/build/` | Artifact hashes and build metadata available | Core 3.3.12, not locked 3.0.7; no transcript/device readback |
