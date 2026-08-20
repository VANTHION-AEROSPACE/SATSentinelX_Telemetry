# Actual Yamcs six-case replay — stopped on integrity failure

Command:

```text
python six_case_equivalence\actual_yamcs_replay_runner.py
```

Result: cases 1–5 matched the pre-existing local adapter within `atol=1e-12`, `rtol=1e-12`. `control_0069` did not.

Observed mismatch:

```text
reference score:    0.6584615384615385
actual Yamcs score: 0.6613782051282052
score delta:        0.0029166666666666785
source rows:        6447
Yamcs rows:         6048
source end:         2002-10-16T15:29:01.888000
Yamcs maximum time: 2002-10-16T15:28:55.242Z
```

Relevant Yamcs log pattern:

```text
GET /api/archive/satsentinel_x:exportParameterValues?... 200 starting chunked transfer
ProcessorFactory [ParameterArchive-backfilling_*] Loading processor service ReplayService
Processor [ParameterArchive-backfilling_*] ... quitting
stdout parchive.getRealtimeFiller: null
stdout coverageEnd: 2026-08-12T17:45:11.300Z
```

Classification: archive/backfill completeness and retrieval timing related. The UDP link itself remained `OK`, reported `Invalid datagrams: 0`, and the instance/processor remained `RUNNING`. The discrepancy is not a Detector v1, XTCE mapping, value-conversion, or timestamp-format error; it is a historical archive tail shortfall.

Smallest required fix: allow the Yamcs Parameter Archive backfill for the `control_0069` historical interval to finish, then rerun the same fixed suite and require complete source/Yamcs timestamp coverage before accepting the score comparison. No detector or frozen research artifact should be changed.
