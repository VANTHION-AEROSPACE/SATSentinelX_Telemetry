# Physical demonstrator telemetry contract v1

## Framing

- Transport: USB serial.
- Encoding: UTF-8.
- One JSON object per line, terminated by LF; CRLF is accepted by the host.
- Baud: 115200, 8 data bits, no parity, 1 stop bit.
- Maximum accepted host line length: 4096 bytes.
- Each device line is a telemetry message; there are no multiline messages.

## Device message schema

Required fields:

```json
{
  "schema_version": 1,
  "message_type": "telemetry",
  "device_id": "esp32-demo-01",
  "seq": 0,
  "device_time_ms": 0,
  "temperature_c": 24.5,
  "sensor_valid": true,
  "sensor_status": "measurement_verified"
}
```

`seq` is an unsigned integer that starts at zero and increments once per
emitted message. `device_time_ms` is the ESP32 `millis()` monotonic elapsed
time and is not UTC. It can wrap after the platform interval; wrap handling is
out of scope for this first short demonstrator run.

`temperature_c` is required to be a finite number in `[-40, 85]` when
`sensor_valid` is true. When the firmware cannot obtain a valid reading, it
may emit `temperature_c: null` with `sensor_valid: false`; the host records
that as a valid-schema sensor-invalid message, not as a valid temperature.
`sensor_status` is one of:

- `sensor_init_failed`: the device was not detected;
- `sensor_bus_unavailable`: communication failed;
- `sensor_value_invalid`: acquisition completed but the measurement was
  invalid;
- `measurement_verified`: acquisition and measurement validity were verified;
- `value_present_read_status_unverified`: a plausible value exists but read
  success is not verified.

The firmware emits `sensor_init_failed`, `sensor_bus_unavailable`,
`sensor_value_invalid`, or `measurement_verified`. The unverified value
`value_present_read_status_unverified` remains accepted by the parser only so
older logs remain auditable; it never counts toward physical acceptance.

The vendored BME280 2.2.4 source retains the upstream float
`readTemperature()` API and adds a separate status-returning path. It checks
forced-measurement completion and uses the documented BusIO Boolean result for
chip-ID, calibration, configuration, status, and temperature transactions.
Only that checked path may emit `measurement_verified`.

The source versions and hashes are recorded in
`firmware/dependencies.lock`. The Arduino ESP32 core is not yet locally
verified, so firmware compilation remains a separate prerequisite.

## Host record additions

The host appends:

- `host_received_utc`: host UTC ISO-8601 timestamp with `Z`;
- `host_received_monotonic_s`: host monotonic clock value;
- `sequence_status`: `first`, `contiguous`, `gap`, `duplicate`, or
  `out_of_order`.
- `device_time_status`: `first`, `increasing`, or `equal`. A backwards device
  timestamp is rejected as `device_time_not_monotonic`.
- `host_gap_s`: elapsed host monotonic time since the preceding accepted
  message.

Host UTC is evidence-recording time only. It must not replace device elapsed
time for freshness or response decisions.

## Commands and acknowledgements

This first vertical slice has **no command channel**. The ESP32 does not read
commands from USB and no fault injection or command acknowledgement is
implemented. The host must not claim that a command was accepted.

The later fault-injection slice must use an explicit `command_id` and return a
single acknowledgement containing `command_id`, `status` (`accepted`,
`rejected`, or `completed`), and a device timestamp. A command without an
acknowledgement before its declared timeout is a failed test, not an assumed
success.

## Validation and failure handling

The host rejects a line when it is too long, not valid JSON, not an object,
missing a required field, has the wrong schema/message type, has invalid types,
has a negative sequence/time, or has an out-of-range finite temperature. It
continues reading after rejection and reports the reason on stderr.

Sequence anomalies do not crash the receiver. They are retained in valid
records as `sequence_status` so the run can be audited. A physical acceptance
run must contain only `first` and `contiguous` statuses and only `first` and
`increasing` device-time statuses.

The receiver stops at the requested duration or EOF. A serial timeout is
recorded as an event and does not fabricate telemetry. A serial exception is
recorded as a disconnect; this first slice fails closed, preserves the partial
JSONL file and does not automatically reconnect.

For the 60-second acceptance run, no valid telemetry gap may exceed 2 seconds;
the run must contain at least 250 `measurement_verified` records and zero
`value_present_read_status_unverified` records. A timeout or early EOF is
reported as an incomplete run and cannot pass physical acceptance.
