# SATSentinel-X Pitch Demo Runbook

## Startup

From `E:\SATSentinel-RealTelemetry`:

```powershell
python physical_demo/dashboard.py --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/` in a browser. This demo is hardware-independent.

If the page reports `404` for an autonomy action, stop duplicate old dashboard
processes and start one current server. A stale server process does not contain
the current autonomy routes.

## Demonstration sequence

1. Open **Dashboard** and click **Play replay** under **Synthetic thermal-rise scenario**.
2. Wait for **Replay complete**.
3. Open **Incident** and show the threshold, affected channel and linked records.
4. Download the thermal **Evidence JSON** if desired.
5. Open **Autonomy Demonstrator**.
6. Click **Run recovery success**.
7. Explain `WARNING`, `POLICY_CHECK`, `ACTION_SIMULATED`, `VERIFYING` and `RECOVERED`.
8. Show the synthetic voltage chart and the warning, critical and recovery criteria.
9. Download `SATSentinelX_Autonomy_recovery_success.json`.
10. Click **Reset**.
11. Click **Run failed recovery**.
12. Explain that the simulated action is not treated as success; insufficient subsequent voltage evidence leads to `ESCALATED`.
13. Download `SATSentinelX_Autonomy_recovery_failure.json`.
14. Return to **Dashboard**.

## Expected outcomes

- Thermal replay ends as `Replay complete` and produces the synthetic thermal incident.
- Recovery success ends as `RECOVERED` only after two subsequent verified voltage samples meet the configured recovery criterion.
- Failed recovery ends as `ESCALATED`.
- Both evidence exports are JSON and match the report currently shown in the dashboard.

## Stop

Stop the foreground server with `Ctrl+C`.

## Scope and limitations

Implemented: local Python dashboard/API, deterministic receiver-backed synthetic
thermal replay, deterministic synthetic power policy, policy trace and JSON
evidence export.

Simulated: all power telemetry, voltage thresholds, recovery action and recovery
outcomes. No spacecraft command is sent. No BME280 hardware, CubeSat flight
computer, onboard resource limit, flight readiness or operational performance is
validated. No public deployment is included in this runbook.
