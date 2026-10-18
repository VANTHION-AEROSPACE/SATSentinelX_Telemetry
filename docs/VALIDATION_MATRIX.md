# Validation matrix

| Track | Input/provenance | Claim tested | Current evidence | Legitimate conclusion |
|---|---|---|---|---|
| Physical receiver | ESP32/BMP280 USB captures under `physical_demo/runs/` | Schema, ordering, verified acquisition and 60-second gate | Offline receiver tests pass; recorded acceptance artifacts fail | Receiver semantics are tested; physical gate is not passed |
| Synthetic thermal replay | Local fixture JSONL | Deterministic replay and linked threshold incident | Replay and dashboard tests pass | Demonstrates software workflow only |
| Synthetic power policy | Local synthetic voltage fixtures | Explicit preconditions, recovery, escalation and evidence | Power tests pass | Demonstrates deterministic policy logic only |
| Detector v1 Mission 1 | ESA/OPSSAT historical inputs under `inspection/`/`ESA-ADB/` | Historical Detector v1 evaluation | Report: 30 positives and 30 matched negatives; all-detected precision .5769, recall 1.0; strong-only precision/recall .9667 | Useful but limited historical result; not operational proof |
| Detector v1 clean-clone smoke | Synthetic fixture under `reproduction/v1/` | Semantic execution and deterministic output | Two outputs match; source hash PASS; pinned env match false | Reproduction smoke only; pinned environment remains unverified |
| OPS-SAT-AD protocol | Direct CSVs and frozen protocol under `external/opssat-ad/` | Generalization under separate protocol | Robust max ROC-AUC .483, PR-AUC .195, recall 0/113, FPR 3/416 | Weak/negative evidence under this contract; not v1 validation |
| Yamcs adapter/local replay | `yamcs/` selected-channel replay | Adapter-level retrieval/equivalence | Deterministic adapter PASS; control_0069 archive tail shortfall | Adapter/replay evidence only |
| Actual Yamcs server | Docker/Yamcs integration | Six-case actual-server equivalence | Blocked, zero actual runs | No actual-server claim is supported |
