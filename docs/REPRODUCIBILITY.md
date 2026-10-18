# Reproducibility and validation commands

## Safe local checks

From the repository root:

```powershell
python -m unittest discover -s physical_demo/tests -p "test_*.py" -v
node --check physical_demo/dashboard/app.js
git diff --check
```

The pre-change audit on 17 October 2026 ran 73 tests: 71 passed and 2 failed because the active sketch did not call checked BMP280 APIs that were present in the vendored library. After the correction, `python -m unittest physical_demo.tests.test_acquisition_source_contract -v` passed 3/3 and `python -m unittest discover -s physical_demo/tests -p "test_*.py"` passed 73/73. `node --check physical_demo/dashboard/app.js` and `git diff --check` also passed. These are offline/software checks, not physical acceptance.

## Reproduction/v1

`reproduction/v1/README.md` and `manifest.json` define the synthetic semantic smoke. The recorded report has Python 3.11.9, NumPy 2.4.6, pandas 2.2.2, two matching runs, and authoritative-source hash PASS. It also records `environment_matches_pinned: false` because NumPy 1.26.4 is pinned. Therefore the report must be described as output-determinism smoke, not successful validation of the pinned environment. Do not execute the report-writing runner merely to refresh it during routine audits.

## Firmware

Canonical source paths are `physical_demo/firmware/esp32_bme280/esp32_bme280.ino` and `physical_demo/firmware/libraries/`. The target recorded by the existing build is `esp32:esp32:esp32`.

The lockfile requests ESP32 core 3.0.7, but this environment has no `arduino-cli` executable and only `C:\Users\Aaditya\AppData\Local\Arduino15\packages\esp32\hardware\esp32\3.3.12` was found. A controlled build was therefore not run. Existing build metadata records core 3.3.12, the vendored library path plus a global Arduino libraries path, and no source hash or transcript. Its app binary SHA-256 is `537b1ee51ba01849eafd61728dcf277b63168bc26e7030c87b0aecabbaf56080`; this is a compiled artifact, not a reproducible or flashed-image baseline.

The current corrected sketch SHA-256 is `47fad666eb6fb66e54fb0b8fda0ed4561a4eab7924dc0b02c7d09d12523167d8`. The vendored BMP280 header and properties match the lockfile, but the current `Adafruit_BMP280.cpp` SHA-256 is `37d4cb8569072b947a1fd0cc694ed1db26b6441ad9c55a9ab66d57d89b1b2db8`, not the lockfile's recorded `C8CC5F4D3B43DF89448B509077B93C305EF240C0CF38F06A09FC2103BA2832C9`. The existing artifact predates the current sketch timestamp and cannot be traced exactly to it.

The next controlled build should use only `physical_demo/firmware/libraries/`, the exact FQBN above, a clean temporary build directory, and a verified ESP32 core version. The canonical choice should remain the locked 3.0.7 until it is installed and successfully built; do not silently promote 3.3.12 or rewrite the lockfile.

## External data and servers

OPS-SAT-AD uses the direct source files and hashes in `external/opssat-ad/inspection/opssat_download_manifest.json`; the archive is not present. Actual Yamcs execution is blocked as documented by `yamcs/yamcs_actual_server_report.json`; do not start services as part of this documentation audit.
