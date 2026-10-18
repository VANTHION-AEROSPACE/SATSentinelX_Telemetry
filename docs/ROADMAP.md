# Prioritised roadmap

## P0 — 24 hours: restore an honest baseline

1. Reconcile `test_acquisition_source_contract.py` with the actual BMP280 3.0.0 vendored API and document the chosen acquisition-verification boundary. Acceptance: 73/73 offline tests pass without weakening the status contract.
2. Reconcile the BMP280 source hash and ESP32 core pin. Acceptance: lockfile, source hashes, CLI/core version, verbose build log and binary hash agree; the flashed image remains separately unverified until read back.
3. Preserve and index run artifacts, including raw-byte hashes and acceptance sidecars. Acceptance: every physical result states PASS/FAIL and provenance; no malformed data is silently discarded.

## P1 — 7 days: reliable demonstrator

- Diagnose serial corruption with one bounded raw capture, one reader, and no port writes; distinguish host framing, reset/stale bytes, and upstream corruption.
- Make a clean-start local dashboard demo repeatable with a runbook and explicit synthetic/live/replay labels.
- Add a customer-facing architecture and evidence walkthrough, but do not add invented metrics.
- Acceptance: fresh hardware run meets >=250 verified records/60 s, zero errors, ordered sequence, strictly increasing device time, and max gap <=2 s; otherwise retain FAIL.

## P2 — 30 days: defensible research product

- Freeze a data-quality and label audit for Mission 1 and OPS-SAT-AD.
- Define a separate hypothesis-driven anomaly experiment with train/validation/test separation, simple baselines, uncertainty, and false-negative review.
- Provide a clean-clone reproduction package whose environment check is genuinely PASS.
- Run actual Yamcs only when a pinned, available server environment exists; require archive completeness before scoring.

## Later spacecraft pathway

Before any onboard or SX-OD1 claim: resource/latency budgets, fault containment, watchdog/reset behavior, persistent state, communications integration, HIL, radiation/thermal/power constraints, software assurance, mission definition, ADCS, ground segment, regulatory/licensing, launch, funding, and qualified partners are required. The current repository supplies software experimentation, not those approvals or hardware capabilities.
