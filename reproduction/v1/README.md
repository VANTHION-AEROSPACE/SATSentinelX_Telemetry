# Frozen Detector v1 synthetic semantic smoke

This directory tests execution semantics for the frozen Detector v1 implementation using a fully synthetic fixture. It does **not** reproduce the ESA Mission-1 30/30 result, use ESA-derived data, validate anomaly-detection performance, or establish operational readiness.

## Run

```text
python -m pip install -r reproduction/v1/requirements.txt
python -B reproduction/v1/run_smoke.py
```

The runner creates temporary pandas pickle inputs because the frozen detector's existing input contract is pickle-based. It injects temporary paths into the imported module at runtime and does not edit `inspection/class3_detector_v1.py` or any historical artifact.

The frozen source retains its original absolute default path for fidelity. It must be invoked through `run_smoke.py`; direct standalone execution is not portable. The runner also checks that the duplicate source snapshot matches the authoritative local source hash when that source is available.

The fixture is deterministic: each event has baseline values `[0, 1, 2, 3]` and event value `10` on core channels 41 and 42. The expected score is `0.75` and the expected classification is `detected / strong evidence`; see `manifest.json` for the derivation and tolerances.

Each run writes `reproducibility_report.json` with runtime versions, source and fixture hashes, output hashes, and whether the environment matches the pinned requirements. A report generated outside Python 3.11.9 / NumPy 1.26.4 / pandas 2.2.2 must not be described as validation of that pinned environment.
