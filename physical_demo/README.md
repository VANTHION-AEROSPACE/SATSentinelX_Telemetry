# SATSentinel-X physical demonstrator: vertical slice 1 and local console V0.2

This slice implements only `ESP32 -> BME280 -> USB serial -> Python JSONL
receiver`. It is a ground-based engineering demonstrator, not a flight or
space-qualified system. It does not use Detector v1, YAMCS, wireless links,
cloud services, ML, or fault-response logic.

## Hardware

- ESP32 development board with USB data connection
- BME280 breakout module
- Breadboard and jumper wires
- USB data cable

The firmware supports BME280 I2C address `0x76` and then `0x77`.

Typical I2C wiring is:

| BME280 | ESP32 |
|---|---|
| VIN/3V3 | 3V3 |
| GND | GND |
| SDA | GPIO 21 |
| SCL | GPIO 22 |

Use the breakout board's voltage requirements. Do not connect a 5 V signal to
an ESP32 GPIO.

The target board assumption is an **Espressif ESP32 Dev Module** using the
Arduino-ESP32 core. Adafruit BME280 Library `2.2.4`, BusIO `1.16.2`, and
Unified Sensor `1.1.14` are vendored with tagged commits and SHA-256 hashes in
`firmware/dependencies.lock`. The BME280 source preserves Bosch compensation
and upstream public APIs while adding a checked acquisition path; a plausible
finite value is not sufficient for `measurement_verified`.

The acceptance gate counts only `measurement_verified` records. Physical
acceptance remains blocked until the firmware is compiled and run on real
hardware.

## Firmware prerequisites

Use Arduino CLI, Arduino IDE, or PlatformIO with the ESP32 board definition.
The Arduino ESP32 core version is not yet locally verified and must be pinned
when the toolchain is installed. The vendored libraries are:

- Adafruit BME280 Library
- Adafruit BusIO 1.16.2
- Adafruit Unified Sensor 1.1.14

Once the toolchain is installed, the planned Arduino CLI commands are:

```text
arduino-cli compile --fqbn esp32:esp32:esp32 --libraries firmware/libraries firmware/esp32_bme280
```

The compile command is an instruction only; this environment has no Arduino
CLI, ESP32 compiler, or board core. Do not install dependencies without
separate approval.

Open `firmware/esp32_bme280/esp32_bme280.ino`, select the board and USB port,
compile, and upload. The firmware emits one UTF-8 JSON object followed by `\n`
every 200 ms at 115200 baud.

## Host prerequisites

The receiver requires Python 3.11+ and `pyserial==3.5`:

```text
python -m pip install -r requirements.txt
```

Run on Windows with the actual COM port:

```text
python receiver.py --port COM5 --output run.jsonl --duration 60
```

The receiver writes only schema-valid telemetry records. Each record is
augmented with `host_received_utc` and `host_received_monotonic_s`; these are
not device timestamps. Malformed, invalid, and missing-field messages are
rejected safely and reported on stderr. Sequence gaps, duplicates, and
out-of-order messages are retained with an explicit `sequence_status`. The
receiver also writes a sidecar `.acceptance.json` report and fails closed on
disconnect, early EOF, validation errors, excessive gaps, bad sequence order,
non-increasing device time, fewer than 250 valid records, or a run shorter than
60 seconds. Automatic reconnect is intentionally not attempted in this first
slice; the partial log is preserved.

## Mission operations dashboard V0.2

The local dashboard is a thin browser interface over the same receiver and
protocol implementation; it is not a second serial reader or validation
path. It requires no dependency beyond `pyserial==3.5` and a modern browser.
From the repository root, run:

```text
python physical_demo/dashboard.py --port 8765
```

Open `http://127.0.0.1:8765`, refresh the port list, select the actual COM
port, and connect. The four sidebar views are functional: Dashboard, Telemetry
Log, Session, and Settings. Navigation is client-side and does not reload the
page. Settings provide a local chart-window preference, auto-refresh toggle,
and serial-port refresh; they do not change receiver validation or telemetry
semantics. The current firmware schema provides temperature only; humidity and
pressure remain visibly unavailable and are never filled with zero or sample
data. Start logging to capture subsequent accepted receiver records, then use
**Download JSONL** to export them in received order with their original fields
and receiver metadata. **Clear display** hides records from the visible tables
only; it does not delete the receiver state or exported session lines.
Disconnects, malformed lines, invalid measurements, and missing data remain
visible as errors or unavailable values.

The header and sidebar use the supplied user brand assets copied unchanged to
`dashboard/assets/satsentinel-x-emblem.png` and
`dashboard/assets/vanthion-aerospace-logo.png`. Their source files were the
attached SATSentinel-X Aerospace Emblem and VANTHION Aerospace Orbital Logo;
the original files in Downloads were not modified. The source images have a
black background, so the dashboard uses contained screen blending to avoid a
black rectangle on the navy interface.

This dashboard is software-only. Its tests and synthetic inputs do not
constitute the 60-second ESP32+BME280 acceptance test, sensor accuracy,
operational performance, or flight readiness. Physical acceptance still
requires the procedure below with real hardware.

## Hardware-free P0 demonstration

The dashboard includes a deterministic synthetic replay so the complete
telemetry-to-investigation workflow can be shown without a board or sensor:

```text
python physical_demo/dashboard.py --host 127.0.0.1 --port 8765
```

In the browser, select **Synthetic thermal-rise scenario**, choose a bounded
speed, and press **Play replay**. The fixture contains 14 schema-valid records;
records 8-11 rise to approximately 30 C against a 26 C threshold. The replay
uses the existing `TelemetryReceiver` and is labelled `SYNTHETIC REPLAY`.
Pause, reset, and speed changes affect only the replay controller. The
Incident view displays the detector rule, onset device time, affected channel,
observed values, threshold, and exact sequence references. **Download Evidence
JSON** exports the same incident object shown in the UI.

This detector is `synthetic_temperature_threshold_v1`. It is a deterministic
demonstration detector only. It does not invoke Detector v1, use ESA telemetry,
reproduce the ESA 30/30 result, validate physical sensor performance, or
establish operational or flight readiness. Recorded replay is intentionally a
separate source type and is not conflated with live hardware.

## Protocol contract

See `PROTOCOL.md`. Device elapsed-time decisions must use the monotonic
`device_time_ms`; the ESP32 does not claim UTC time synchronization.

## Host tests

The tests use synthetic serial text only and do not claim physical acceptance:

```text
python -m unittest discover -s tests -p "test_*.py" -v
```

The dashboard host tests use synthetic frames to verify receiver reuse, JSONL
ordering, validation and sequence issue reporting, and non-fabrication of
absent environmental measurements.

## 60-second physical acceptance procedure

1. Connect the BME280 as shown above and upload the firmware.
2. Identify the actual Windows COM port and close any serial monitor using it.
3. Run the receiver for 60 seconds, saving `run.jsonl`.
4. Confirm the receiver exits with status 0, records at least 250
   `measurement_verified` telemetry messages, has zero
   `value_present_read_status_unverified` messages, and the sidecar acceptance
   report has `status: PASS`.
5. Confirm every record has schema version `1`, increasing `seq`, a
   `sequence_status` of `first` or `contiguous`, a `device_time_status` of
   `first` or `increasing`, strictly increasing `device_time_ms`, finite
   temperature in `[-40, 85]` Celsius, and separate host UTC time.
6. Inspect the JSONL file after the run and preserve its SHA-256 hash with the
   test date, board, sensor, COM port, and firmware hash.

This acceptance gate is **BLOCKED until a real ESP32 and BME280 are tested**.
Synthetic host tests are not physical acceptance. No stuck-sensor claim is
made in this slice; a later test must apply a defined stimulus and explicitly
inject or create a stuck value.
