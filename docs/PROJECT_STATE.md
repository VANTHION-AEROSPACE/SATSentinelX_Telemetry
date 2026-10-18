# SATSentinel-X project state

Audit baseline: 17 October 2026. Repository: `codex/physical-acceptance-receiver-fix`. The working tree was already dirty; this document does not treat those pre-existing changes as authored by this audit.

## Verified today

- A local Python dashboard exists at `physical_demo/dashboard.py`. It serves the browser UI and APIs for state, ports, connection, session logging, replay, thermal evidence, and synthetic power-policy evidence.
- The physical-demo path is `ESP32/BMP280-class sensor -> USB JSONL -> receiver validation -> JSONL/session state -> dashboard/replay/evidence`. The receiver is `physical_demo/receiver.py`; the browser assets are `physical_demo/dashboard/index.html`, `app.js`, and `styles.css`.
- Deterministic software tests cover the receiver, replay, dashboard, synthetic detector, power policy, and offline serial diagnostics. The pre-change run had 71/73 passing because the active sketch had not called available checked BMP280 APIs; after this phase the targeted contract tests and all 73 offline tests pass.
- `node --check physical_demo/dashboard/app.js` passed.
- The active firmware is `physical_demo/firmware/esp32_bme280/esp32_bme280.ino`. It identifies the observed chip as BMP280 (`0x58`), uses the vendored checked transaction/read APIs, publishes `pressure_hpa`, and converts the checked library pressure result from Pa to hPa before range validation.
- A local build artifact exists under `physical_demo/build/`, but its build metadata identifies ESP32 core 3.3.12. The lockfile requests 3.0.7. No build transcript or device readback proves what is flashed.

## Capability classification

| Area | State | Evidence / boundary |
|---|---|---|
| Local dashboard and APIs | Implemented, software-tested | `physical_demo/dashboard.py`, `physical_demo/dashboard/`, dashboard tests |
| Hardware-free replay | Implemented, deterministic | `physical_demo/replay.py`, `physical_demo/fixtures/`, replay tests |
| Thermal incident evidence | Implemented synthetic demo | `physical_demo/synthetic_detector.py`; explicitly not ESA/Detector v1 |
| Power recovery policy | Implemented synthetic demo | `physical_demo/power_autonomy.py`; no hardware command |
| USB receiver and acceptance gate | Implemented, hardware evidence fails | `physical_demo/receiver.py`; run artifacts report FAIL |
| Physical 60-second acceptance | Not accepted | run artifacts contain validation errors and/or fewer than 250 verified records |
| Detector v1 | Frozen historical research | `inspection/class3_detector_v1.py` and historical outputs; do not modify |
| Detector v1 clean-clone smoke | Synthetic semantic smoke | `reproduction/v1/`; current report says output PASS but pinned environment match is false |
| OPS-SAT-AD | Protocol-level external evaluation | `external/opssat-ad/`; weak discrimination, not Detector v1 validation |
| Actual Yamcs server six-case run | Blocked / not run | `yamcs/yamcs_actual_server_report.json`; Docker daemon unavailable |
| Flight readiness / autonomy | Unverified / proposed | No flight, HIL, radiation, or spacecraft-control evidence |

## Repository boundaries

`inspection/`, `research/`, `ESA-ADB/`, and historical result files are research evidence. `physical_demo/` is an operational-style prototype and synthetic demonstrator. `external/opssat-ad/` is a separate protocol and dataset track. `yamcs/` contains adapter/local replay and blocked actual-server integration evidence. These tracks must not be merged into one performance claim.
