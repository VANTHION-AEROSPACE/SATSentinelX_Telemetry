# Yamcs archive-readiness failure — final forensic report

Command:

```text
python six_case_equivalence\actual_yamcs_replay_runner.py
```

The targeted readiness gate was applied. It polled the actual Yamcs bulk Parameter Archive export and required, for every selected channel, both:

1. Yamcs row count equal to the source row count; and
2. Yamcs maximum generation time at or beyond the source maximum.

The run stopped before Detector v1 because the condition was not met.

Exact error:

```text
RuntimeError: Yamcs archive readiness timeout
case_id: case_04_long_persistent_highdim_class3
polls: 48
timeout_seconds: 300
```

Representative source-versus-Yamcs counts at timeout:

```text
channel 12: source 2164, Yamcs 2133
channel 41: source 6818, Yamcs 6721
channel 47: source 6493, Yamcs 6398
```

The final timestamps for multiple channels had reached their expected source values, but the row counts remained short. Therefore this is not a simple final-tail sleep issue.

Relevant Yamcs log pattern:

```text
GET /api/archive/satsentinel_x:exportParameterValues?... 200 starting chunked transfer
ProcessorFactory [ParameterArchive-backfilling_*] Loading processor service ReplayService
Processor [ParameterArchive-backfilling_*] ... quitting
stdout parchive.getRealtimeFiller: null
```

Forensic classification: Parameter Archive historical coverage/backfill completeness. The archive export is serving partial historical data while Yamcs repeatedly creates and terminates backfill processors; it does not reach complete source row coverage within the bounded readiness window. The live instance, realtime processor, UDP link, and XTCE configuration were not changed by this diagnostic run. Detector v1 was not invoked after the readiness failure.

Smallest required fix: determine why the configured `ParameterArchive` backfill is not materializing all recorded historical parameter values for the requested partition/range, then rerun the same readiness check. Do not change Detector v1, tolerances, scoring, case selection, ESA data, or frozen artifacts.

Status: STOPPED per task instruction. The six-case acceptance criteria are not met.
