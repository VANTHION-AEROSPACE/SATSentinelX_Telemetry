# Known issues and blockers

## Critical

1. **Physical acceptance is not passed.** `physical_demo/runs/post_flash_acceptance.acceptance.json`, `run4.acceptance.json`, and related artifacts report `FAIL_ACCEPTANCE`. Examples contain 230–232 verified records in about 60 seconds plus invalid UTF-8 or malformed-frame errors; the gate requires at least 250 verified records and zero errors. Do not lower the gate. The raw captures prove malformed bytes existed before offline buffered replay, but they do not establish the upstream cause.

2. **Exact flashed firmware is unproven.** `physical_demo/build/` contains a compiled artifact, but metadata identifies ESP32 core 3.3.12 while `physical_demo/firmware/dependencies.lock` requests 3.0.7. There is no upload transcript or device readback. The artifact is compiled evidence, not proof of device provenance.

3. **Acquisition source-contract mismatch was corrected in this phase.** The active sketch had been using legacy BMP280 calls even though the vendored library provides checked transaction APIs. The sketch now uses `setSamplingVerified`, `takeForcedMeasurementVerified`, `readTemperatureVerified`, and `readPressureVerified`; the targeted contract tests and complete 73-test offline suite pass. This establishes transaction/read success, not calibrated accuracy or flight qualification.

## High

4. **Vendored BMP280 source hash mismatch.** The current `Adafruit_BMP280.cpp` hash is `37d4cb8569072b947a1fd0cc694ed1db26b6441ad9c55a9ab66d57d89b1b2db8`, differing from the lockfile's recorded expected hash. The header and `library.properties` match. The repository cannot currently establish whether the lockfile or modified vendor source is authoritative; resolve this before declaring a canonical firmware baseline.

5. **Actual Yamcs six-case equivalence is blocked.** `yamcs/yamcs_actual_server_report.json` says `actual_yamcs_server_used: false`, `six_cases_successfully_replayed: []`, and `actual_server_pipeline_executed: false` because Docker was unavailable. `yamcs/actual_server/six_case_equivalence/failure_diagnosis.md` separately records cases 1–5 adapter matches and a control_0069 archive tail shortfall. The interpretation markdown is conditional wording, not proof of a completed actual-server run.

6. **Reproduction report status is over-broad.** `reproduction/v1/reproducibility_report.json` says `status: PASS`, but also says `environment_matches_pinned: false`; runtime NumPy is 2.4.6 versus pinned 1.26.4. Treat the result as synthetic semantic smoke output equality, not a pinned-environment validation.

## Medium

7. **Pressure-unit and hardware identity require continued provenance control.** The active sketch now converts BMP280 pressure Pa to hPa before publishing and validates 300–1100 hPa, but this has not been physically revalidated in the current run. The connected chip identity is reported as BMP280 (`0x58`), not BME280 humidity capability.

8. **Deployment is a single-process demo service.** `render.yaml` and `dashboard.py` provide a hosted/local route, but state is in memory, there is no authentication, durable storage, or multi-user isolation. Do not present it as a production telemetry service.

9. **Firmware baseline build is blocked in the current environment.** `arduino-cli` is unavailable, core 3.0.7 is not installed, and only core 3.3.12 is present. Existing 3.3.12 build artifacts have no transcript or source hash and were built with a global library search path in addition to the vendored path. Do not use them as proof of the current corrected sketch or flashed firmware.

9. **Firmware baseline build is blocked in the current environment.** `arduino-cli` is unavailable, core 3.0.7 is not installed, and only core 3.3.12 is present. Existing 3.3.12 build artifacts have no transcript or source hash and were built with a global library search path in addition to the vendored path. Do not use them as proof of the current corrected sketch or flashed firmware.

## Suspected, not proven

- Serial corruption may involve capture/driver/reset/process interaction. Existing evidence rules out an offline buffered-reader-only transformation for the analyzed capture, but does not identify the upstream source.
- The 230–232 record count may reflect cadence/startup/buffering effects, but the repository evidence does not justify changing the 250-record criterion.
