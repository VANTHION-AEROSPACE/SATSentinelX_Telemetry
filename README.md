# SATSentinel-X

SATSentinel-X is a local, hardware-independent telemetry demonstrator and a set of separate research/evaluation tracks under Vanthion Aerospace. It currently provides a Python dashboard, deterministic replay, JSONL validation, synthetic thermal incident evidence, and a synthetic power-policy demonstration. It is not flight software, a spacecraft-control system, or proof of operational anomaly-detection performance.

## Run the local demonstrator

```powershell
python physical_demo/dashboard.py --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/`. The dashboard can run without hardware using the documented synthetic replay and autonomy scenarios. For the physical path, follow `physical_demo/README.md` and `physical_demo/DEMO_RUNBOOK.md`; the physical acceptance gate remains distinct and currently unpassed.

## Evidence and project state

- [Project state](docs/PROJECT_STATE.md)
- [Architecture and provenance](docs/ARCHITECTURE.md)
- [Accomplishments](docs/ACCOMPLISHMENTS.md)
- [Known issues](docs/KNOWN_ISSUES.md)
- [Validation matrix](docs/VALIDATION_MATRIX.md)
- [Reproducibility](docs/REPRODUCIBILITY.md)
- [Roadmap](docs/ROADMAP.md)

Frozen Detector v1 and historical research artifacts under `inspection/`, `ESA-ADB/`, and related outputs are immutable. OPS-SAT-AD and Yamcs evidence are separate tracks with their own contracts and limitations.
