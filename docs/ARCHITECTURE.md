# SATSentinel-X architecture and provenance

```text
ESP32 + BMP280                    synthetic/replay JSONL
       | USB JSONL                         |
       v                                   v
              physical_demo.receiver.TelemetryReceiver
                 framing / UTF-8 / schema / units / sequence
                              |
             +----------------+----------------+
             v                                 v
       JSONL session/log                dashboard state
             |                                 |
             v                                 v
       acceptance report             replay controller / charts
                                               |
                         +---------------------+------------------+
                         v                                        v
              synthetic_detector.py                    power_autonomy.py
                         |                                        |
                         +---------- JSON evidence --------------+
```

## Interfaces

- The telemetry envelope is documented in `physical_demo/PROTOCOL.md`. Required fields include schema version, message type, device identity, sequence, device monotonic time, temperature, validity, and sensor status. Only `measurement_verified` records count as verified acceptance telemetry.
- `physical_demo/replay.py` reuses receiver validation; it does not create a second telemetry parser. Replay inputs are synthetic fixtures and are labelled as replay/synthetic.
- `physical_demo/dashboard.py` is both HTTP server and session coordinator. It has serial-session state, replay state, synthetic incident state, and evidence export endpoints. It is a local/demo service, not a multi-user persistence layer.
- `render.yaml` runs the same Python service on a platform-provided `PORT`; `physical_demo/requirements.txt` currently pins only `pyserial==3.5`. Hosting persistence, authentication, and multi-user isolation are not implemented claims.

## Provenance boundaries

1. Live hardware: `physical_demo/firmware/` and receiver run artifacts. Physical evidence is not interchangeable with replay fixtures.
2. Synthetic demo: `physical_demo/fixtures/`, `synthetic_detector.py`, and `power_autonomy.py`. It demonstrates execution semantics and deterministic policy evidence only.
3. Frozen Mission 1 research: `inspection/`, `ESA-ADB/`, and historical outputs. Detector v1 remains immutable.
4. External evaluation: `external/opssat-ad/`, source record DOI `10.5281/zenodo.12588359`, with protocol-specific labels and metrics. It does not validate Detector v1.
5. Yamcs: `yamcs/`. The adapter/local replay is distinct from the blocked actual-server pipeline.
