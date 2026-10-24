# SATSentinel-X Telemetry and Finding Contract

**Status:** Proposed for engineering review. This document specifies a future integration contract; it does not describe implemented behavior unless explicitly marked as verified repository behavior.

## 1. Evidence and repository status

### Verified repository behavior

- The wire schema required by `physical_demo/receiver.py` is `schema_version`, `message_type`, `device_id`, `seq`, `device_time_ms`, `temperature_c`, `sensor_valid`, and `sensor_status` (`receiver.py`, `REQUIRED`). The receiver validates these fields, then appends host receipt timestamps and sequence/time status fields.
- `physical_demo/PROTOCOL.md` documents `temperature_c` as Celsius in the range -40 to 85 when valid, `device_time_ms` as ESP32 `millis()` elapsed time, and host UTC as receipt/evidence-recording time. These are documented contract semantics. They are **not independently verified firmware behavior** in this repository: the firmware source is not present in the checkout.
- The required wire schema contains no pressure field, session ID, or boot ID. The dashboard optionally reads `pressure_hpa`, but absent pressure remains null (`dashboard.py`, `DashboardSession.snapshot`). The receiver's required schema must not be expanded as part of this contract proposal.
- `DashboardSession` owns the current receiver, replay, incident, and in-memory session state. `/api/state` returns its snapshot. `/api/session/export` returns logged JSONL, while `/api/evidence/export` returns the current incident (`dashboard.py`, `DashboardHandler.do_GET`).
- `synthetic_detector.py` uses threshold 26.0 C and currently reports the synthetic anomaly event at sequences 8-11 with onset 4000 ms. Existing tests assert those references and values (`tests/test_replay.py`). The fixture contains 14 records and must remain unchanged.
- The detector and fixtures are synthetic demonstration evidence. They do not establish physical sensor behavior, physical acceptance, ESA reproduction, or ML validation on physical data.

The October 17 physical acceptance status remains **`FAIL_ACCEPTANCE`**. This contract review does not change or supersede that status. No tests were run for this documentation revision.

### Proposed contract

Maintain four distinct representations and never conflate them:

1. **Original incoming bytes:** exact bytes read from the transport, when capture supports byte preservation. Malformed frames should be retained with their ordinal and receipt metadata where possible. A capture limitation must be stated if bytes cannot be preserved.
2. **Parsed wire JSON:** a parsed object derived from those bytes. Parsing and JSON reserialization may change whitespace, key order, escaping, or numeric formatting; a parsed object is not byte-identical to its source bytes. Preserve a raw-byte reference/hash separately.
3. **Normalized telemetry:** a versioned derived record linked to the raw frame/parsed record. Normalization must not mutate either raw representation.
4. **Detector findings:** derived outputs referencing normalized records. They must not be embedded into or written back into raw telemetry.

Raw byte immutability means retaining the original byte sequence or an immutable file containing it, not treating a Python dictionary or reserialized JSON as the original bytes. When the current receiver only emits accepted, parsed-and-reserialized JSONL, that output is an accepted-record export, not proof that malformed input bytes were preserved.

## 2. Normalized telemetry contract

Proposed schema identifier: `satsentinel.normalized-telemetry`, version `1`.

Normalized records are separate from the immutable wire schema. Keep original wire keys, including `temperature_c`, unchanged in the raw representation. If normalized channel identifiers differ from wire keys, declare the mapping under a versioned `field_mappings` registry. For example, mapping wire key `temperature_c` to normalized channel ID `temperature` requires a mapping ID/version and an explicit transformation (`identity` here); do not imply that the current code already performs this mapping.

### Required fields

| Field | Contract meaning |
|---|---|
| `schema` / `schema_version` | Normalized schema identifier and supported version; independent of wire `schema_version`. |
| `record_id` | Stable identifier within the session, e.g. session UUID plus raw record ordinal. |
| `session_id` | Host-generated UUID for this capture or replay; not a device boot ID. |
| `source.type` / `source.id` | `physical`, `synthetic_replay`, or `other`; ID identifies the actual input device, fixture, capture, or other source. |
| `device.id` | Wire `device_id`, if present; otherwise null with an explicit absence reason. |
| `device.boot_epoch` | Epoch reference with state `known`, `inferred`, or `unknown`; it is not a firmware-provided boot identifier unless a future wire contract adds one. |
| `sequence.number` | Wire `seq`, when present; do not renumber the wire sequence. |
| `time.device_elapsed_ms` | Wire `device_time_ms`, without unit or value conversion; null if absent. Documented as elapsed milliseconds by protocol, not independently verified in this checkout. |
| `time.host_received_utc` | Host UTC receipt time, ISO-8601 UTC; evidence-recording time, not device UTC. |
| `time.host_received_monotonic_s` | Host process monotonic receipt reading. It is process-local and MUST NOT be compared across process restarts or treated as a persistent timestamp. |
| `measurement.validity` | `valid`, `invalid`, `unverified`, or `unknown`, based on wire validity/status and declared policy. |
| `measurement.sensor_status` | Original wire status string, or null if absent. |
| `channels` | Map from normalized channel IDs to value, availability, units, source field, provenance, and mapping version. |
| `raw_ref` | Hash and location/ordinal for the immutable raw bytes or raw-file record. A parsed-object reference alone is not a byte-preservation claim. |
| `validation` | Accepted status plus warnings; rejected frames belong in rejection/audit records, not valid normalized telemetry. |

### Channel and unit semantics

Each channel entry contains `value`, `availability`, `source_field`, `source_unit`, `canonical_unit`, `provenance`, and `mapping` (`mapping_id`, `mapping_version`, transformation). Availability is one of `available`, `missing`, `invalid`, `stale`, `unverified`, or `not_mapped`. Provenance is one of `device_reported`, `host_derived`, `fixture_defined`, or `unknown`.

The protocol documents the wire key `temperature_c` as Celsius. This is a **documented wire unit**, not independent verification that the absent firmware actually emits Celsius correctly. Until authoritative firmware and physical capture verify implementation, normalized output must retain that distinction (for example, `unit_basis: documented_wire_contract`) and must not claim physically verified sensor provenance. Synthetic fixture values may use fixture-declared units but must be labeled synthetic.

Pressure has no required wire key or verified mapping in the current contract. It remains unavailable to scorers pending capture and firmware evidence (see §4). Never substitute zero for absent, invalid, or unavailable data.

### Illustrative normalized record

This is an example of proposed structure, not a physical capture or implementation claim. Host times and digest are placeholders. The temperature unit basis is the documented wire contract/fixture, not independently verified firmware behavior.

```json
{
  "schema": "satsentinel.normalized-telemetry",
  "schema_version": 1,
  "record_id": "session-uuid:raw-record-9",
  "session_id": "b14a5da1-9dda-41c5-81de-b4a16d1df0d7",
  "source": {"type": "synthetic_replay", "id": "physical_demo/fixtures/synthetic_anomaly.jsonl"},
  "device": {
    "id": "synthetic-demo-01",
    "boot_epoch": {"id": null, "state": "unknown", "confidence": "none", "evidence": []}
  },
  "sequence": {"number": 8, "status": "contiguous"},
  "time": {
    "device_elapsed_ms": 4000,
    "device_time_basis": "documented_wire_contract_not_independently_firmware_verified",
    "host_received_utc": "<host-receipt-utc>",
    "host_received_monotonic_s": 812.4,
    "host_monotonic_process_id": "<capture-process-identity>"
  },
  "measurement": {"validity": "valid", "sensor_status": "measurement_verified"},
  "channels": {
    "temperature": {
      "value": 30.0,
      "availability": "available",
      "source_field": "temperature_c",
      "source_unit": "degC",
      "unit_basis": "fixture_and_documented_wire_contract",
      "canonical_unit": "degC",
      "provenance": "fixture_defined",
      "mapping": {"mapping_id": "wire-temperature-c-to-temperature", "mapping_version": 1, "transformation": "identity"}
    },
    "pressure": {
      "value": null,
      "availability": "not_mapped",
      "source_field": null,
      "source_unit": null,
      "canonical_unit": null,
      "provenance": "unknown",
      "mapping": null
    }
  },
  "raw_ref": {"raw_file_sha256": "<sha256>", "record_ordinal": 9, "byte_range": null},
  "validation": {"status": "accepted", "warnings": []}
}
```

### Validation and missing data

- Keep existing receiver wire validation unchanged. Accepted wire records may normalize; rejected frames are represented in rejection/audit records with reasons and raw references if bytes are preserved.
- Sensor-invalid measurements remain records with invalid measurement/channel availability, never valid numeric features.
- Plausible values marked unverified cannot satisfy a detector requiring verified measurements.
- Missing and unmapped fields remain missing/not-mapped, never zero-filled.
- A freshness policy must be defined per channel and clock basis before marking values stale. Without it, freshness is unknown.
- Insufficient data is evaluated per detector invocation, not as a global record status. Each detector declares its own required channels, validity, sample count/window, time policy, provenance, and epoch constraints. A temperature-only detector may score a valid temperature record while pressure is unavailable. A detector requiring pressure must return an explicit blocked/not-scored invocation result while pressure mapping is unverified.

## 3. Session lifecycle and manifest

### Identity and lifecycle rules

- Generate a host UUID for each capture or replay session. A `session_id` groups one host operation; it does not identify a device boot.
- Record session creation, actual start, and end timestamps separately. Mark a terminated capture/replay incomplete with an explicit reason (disconnect, EOF, user stop, process failure, or other declared cause); do not infer successful completion from missing end data.
- A replay manifest references the exact source fixture/capture and its SHA-256. Replay receipt timestamps are replay-host times, not original acquisition times.
- Device boot epoch is separate from session identity. Current wire data contains no boot ID. Epochs may be `unknown` or `inferred`; any inferred epoch must include evidence, inference method/version, and confidence. A sequence reset or device-time discontinuity alone is not proof of reboot. Such evidence may trigger an `unknown` boundary or a low-confidence reboot hypothesis, but must not silently establish a new known boot.
- A future explicit boot identifier or corroborating source evidence may establish an epoch as known. Preserve the evidence supporting that assignment.
- Prohibit sequence comparisons, elapsed-time comparisons, rolling baselines, and event windows across distinct or uncertain boot epochs by default. Cross-epoch analysis requires detector-specific, explicitly approved support.
- The protocol notes device elapsed time may wrap; current receiver rejects backward time. Do not reinterpret backwards time as wrap absent an approved policy and implementation.
- A replay reset must create a new session UUID or a clearly identified new replay-attempt UUID under an explicitly defined parent session. This identity policy remains an approval decision.

### Proposed manifest

```json
{
  "manifest_schema": "satsentinel.session-manifest",
  "manifest_version": 1,
  "session_id": "b14a5da1-9dda-41c5-81de-b4a16d1df0d7",
  "session_kind": "replay",
  "source": {
    "type": "synthetic_replay",
    "source_id": "physical_demo/fixtures/synthetic_anomaly.jsonl",
    "source_sha256": "<fixture-sha256>",
    "parent_capture_session_id": null
  },
  "device": {
    "device_id": "synthetic-demo-01",
    "boot_epochs": [{
      "epoch_id": null,
      "state": "unknown",
      "basis": "fixture contains no authoritative boot identifier",
      "confidence": "none",
      "evidence_record_refs": []
    }]
  },
  "lifecycle": {
    "created_utc": "<utc>", "started_utc": "<utc>", "ended_utc": "<utc>",
    "status": "complete", "incomplete_reason": null
  },
  "files": {
    "raw_bytes_path": "<path-or-null>",
    "raw_bytes_sha256": "<sha256-or-null>",
    "parsed_wire_export_path": "<path-or-null>",
    "normalized_path": null,
    "findings_path": null
  },
  "provenance": {
    "firmware_revision": null, "firmware_build_id": null, "board_id": null,
    "sensor_id": null, "receiver_version": "<version-or-commit>",
    "label_source_id": null
  },
  "schemas": {"wire_schema_version": 1, "normalized_schema_version": 1, "finding_schema_version": 1},
  "units_and_mappings": {"temperature": "degC (documented wire/fixture basis; physical behavior unverified)", "pressure": null, "mapping_registry_version": 1},
  "time_policy": {
    "device_time_semantics": "documented elapsed milliseconds; firmware implementation unverified",
    "host_utc_semantics": "receipt time",
    "host_monotonic_semantics": "process-local receipt clock; invalid across process restarts"
  },
  "counts": {"raw_frames": 14, "parsed_wire_records": 14, "normalized_records": 14, "rejected_frames": 0, "sequence_gaps": 0, "epoch_boundaries": 0},
  "labels": {"label_source_id": null, "label_version": null, "label_record_count": 0}
}
```

Example counts and identity are illustrative, not a claim that this manifest exists. A physical manifest must leave unknown provenance null/unknown rather than guess.

## 4. Pressure mapping

Preserve any raw pressure key and value exactly in original incoming bytes and the parsed wire JSON. Do not add pressure to the receiver's required schema. Until an actual captured frame and authoritative firmware revision verify the mapping and unit, pressure is unavailable to pressure-dependent ML scoring and such an invocation returns `not_scored` with reason `PRESSURE_MAPPING_UNVERIFIED`.

Do not convert, rescale, or relabel a pressure value silently. A future mapping registry entry must specify: exact source field; verified source unit and evidence; transformation formula or identity operation; normalized canonical channel ID; canonical unit; mapping ID/version; tests; and provenance. Store transformed values only in normalized/derived records, never overwrite the raw field/value. `pressure_hpa` in dashboard code is not evidence that the firmware emits that key or unit.

## 5. Labels and ground truth

The only label states are:

- `approved_nominal`
- `known_anomaly`
- `unknown_unlabelled`

Successful sensor acquisition does not imply nominal behavior. Missing anomaly labels do not imply nominal behavior. Every record/session without an applicable approved label maps to `unknown_unlabelled`.

An `approved_nominal` or `known_anomaly` label is valid **only** when it comes from the agreed authoritative label source and has traceable record/session scope. The source must be versioned and immutable (ID plus version/hash), define label meaning and scope, identify approving authority and approval time, cite exact session/boot-epoch/record or time-interval references, state interval boundary semantics and time basis, and retain author/reviewer/revision audit history and evidence rationale. If any required authority or scope reference is absent, the label remains `unknown_unlabelled`.

Keep evidence tracks separate: OPS-SAT-AD retains its external benchmark provenance; synthetic fixtures remain synthetic evidence; physical captures remain physical observations until separately and authoritatively labeled. Existing `LABEL_NEGATIVE_UNLABELLED` semantics map to `unknown_unlabelled`, never `approved_nominal`.

## 6. Detector finding interface

Proposed shared schema: `satsentinel.detector-finding`, version `1`. Each output describes exactly one detector invocation over a declared input scope.

### Invocation outcomes

- `scored`: the detector evaluated its declared inputs and returned its defined result. `decision` may be `anomaly`, `no_alert`, or `undetermined` according to the detector policy.
- `insufficient_data`: detector ran but requirements such as valid sample count/window were not met. `decision` is `undetermined`, score is null, and one or more reason codes are required.
- `not_scored`: detector did not evaluate because a prerequisite is blocked/unsupported (for example pressure mapping is unverified). `decision` is `undetermined`, score is null, and a blocking reason is required.

These statuses are per invocation. One record can be usable for one detector and unusable for another. For example, temperature-only can score while pressure-dependent returns `not_scored`.

### Identity and deduplication

- A **sample finding** has `finding_kind: sample_result`; identity/deduplication key is `(session_id, detector_name, detector_version, configuration_digest, input_record_ref)`. It describes one detector result for one record. Repeating the same deterministic invocation in the same session replaces/reuses the same key; it does not append an ambiguous duplicate.
- An **aggregated incident** has `finding_kind: aggregated_incident`; identity/deduplication key is `(session_id, detector_name, detector_version, configuration_digest, aggregation_policy_version, ordered_event_record_refs)`. It groups sample results using a declared aggregation policy. For a deterministic replay, the same ordered event references and configuration must resolve to the same incident ID/deduplication key. A replay in a new session has a distinct session-scoped identity, even if the fixture and event are identical.
- IDs may be human-readable or UUIDs, but the above stable key must be retained. Do not use only a fixed global incident ID such as the current demo ID when findings from multiple sessions can coexist.

### Proposed aggregated synthetic finding

The following is **synthetic demonstration evidence only**. It keeps the existing threshold (26.0 C) and onset (4000 ms) assertions and includes all four event references (sequences 8, 9, 10, 11). No physical data, ML model, or confirmed anomaly is implied.

```json
{
  "schema": "satsentinel.detector-finding",
  "schema_version": 1,
  "finding_kind": "aggregated_incident",
  "finding_id": "<stable-id-derived-from-session-and-dedup-key>",
  "deduplication_key": "<session|synthetic_temperature_threshold_v1|1.0|config-digest|aggregation-v1|seq-8,9,10,11>",
  "session_id": "<replay-session-uuid>",
  "source": {"type": "synthetic_replay", "id": "physical_demo/fixtures/synthetic_anomaly.jsonl", "evidence_class": "synthetic_demonstration"},
  "device": {"id": "synthetic-demo-01", "boot_epoch": {"id": null, "state": "unknown", "confidence": "none"}},
  "detector": {
    "name": "synthetic_temperature_threshold_v1",
    "version": "1.0",
    "kind": "rule",
    "configuration": {"threshold": 26.0, "unit": "degC", "rule": "temperature_c > threshold"},
    "configuration_digest": "<canonical-config-digest>",
    "model_artifact_digest": null,
    "aggregation_policy": {"id": "all-above-threshold-records-v1", "version": 1}
  },
  "evaluation": {
    "status": "scored",
    "decision": "anomaly",
    "score": null,
    "score_semantics": null,
    "severity": "demo",
    "severity_semantics": "synthetic demonstration only; not operational severity"
  },
  "affected_channels": [{"channel_id": "temperature", "source_field": "temperature_c", "unit": "degC", "mapping_version": 1}],
  "event": {
    "onset": {"seq": 8, "device_elapsed_ms": 4000},
    "end": {"seq": 11, "device_elapsed_ms": 5500},
    "record_refs": [
      {"seq": 8, "device_elapsed_ms": 4000, "value": 30.0, "unit": "degC"},
      {"seq": 9, "device_elapsed_ms": 4500, "value": 30.2, "unit": "degC"},
      {"seq": 10, "device_elapsed_ms": 5000, "value": 30.1, "unit": "degC"},
      {"seq": 11, "device_elapsed_ms": 5500, "value": 30.0, "unit": "degC"}
    ]
  },
  "explanation": {
    "summary": "Synthetic fixture values exceed the configured demonstration threshold.",
    "reason_codes": [],
    "supporting_evidence": [{"type": "rule_comparison", "threshold": 26.0, "unit": "degC"}]
  },
  "label": {"state": "unknown_unlabelled", "label_source_id": null, "label_version": null},
  "limitations": ["Synthetic demonstration only; not physical validation, ESA reproduction, detector-v1 validation, or operational diagnosis."]
}
```

For an ML detector, a non-null score requires documented range and interpretation (e.g. `0..1`, larger means more model anomaly evidence), plus model artifact digest and preprocessing/configuration provenance. A model score is not ground truth or a confirmed anomaly. A threshold/policy must separately define the decision. Severity is optional and requires its own defined semantics.

Finding evidence references must resolve to records in the same session and boot epoch unless an explicitly approved cross-epoch detector policy says otherwise. Event onset/end use device elapsed time with epoch identity; host UTC may be provided as additional receipt context. Do not compare host monotonic receipt times across process restarts.

### Insufficient/not-scored reason codes

Examples include `NO_VALID_SAMPLES`, `MIN_WINDOW_NOT_MET`, `CHANNEL_UNAVAILABLE`, `PRESSURE_MAPPING_UNVERIFIED`, `BOOT_EPOCH_UNKNOWN`, `BOOT_EPOCH_BOUNDARY`, `TIMESTAMP_UNTRUSTED`, `INPUT_PROVENANCE_UNSUPPORTED`, and `LABEL_SOURCE_UNAVAILABLE`. Each detector declares which conditions block it. These are invocation outcomes, not global telemetry-record states.

## 7. Dashboard integration contract

### Verified existing seam

`DashboardSession` owns a single receiver and calls the existing synthetic detector for synthetic replay. `/api/state` exposes `source_type`, `incident`, replay state, records, and stats. Raw logged JSONL export and evidence export already use separate endpoints. The current incident renderer expects legacy fields including `incident_id`, `classification`, `onset_device_time_ms`, `detector.threshold_c`, and `record_refs` (`dashboard/app.js`, `renderIncident`).

### Minimum proposed integration

1. Reuse `TelemetryReceiver` and `DashboardSession`; do not add another parser or dashboard.
2. Create session/manifest context at capture/replay boundaries. Adapt accepted records to normalized telemetry after receiver validation; do not alter raw fields.
3. Adapt the existing synthetic detector output once into the new finding schema. Preserve threshold, onset, observed values, baseline references, and exact event references.
4. During migration, expose additive `/api/state.findings` and `/api/state.session` fields while keeping existing fields and meanings. Build the legacy `incident` projection from the same finding, not a second detector invocation.
5. Keep `/api/session/export` for telemetry records and expose finding/evidence separately. Do not append findings into the raw telemetry stream.
6. Distinguish `physical`, `synthetic_replay`, and simulated recovery (`other` with subtype `simulated_recovery`, or an explicit existing `synthetic_power_scenario` value). Do not label recovery simulation as physical telemetry.
7. The current 14-record fixture remains byte-for-byte unchanged. Replaying it deterministically must preserve current sequence 8-11, onset 4000 ms, and 26.0 C threshold assertions.

## 8. Tests and acceptance criteria for a future implementation

These are proposed tests; none were run for this documentation task.

### Contract and normalization tests

- Validate normalized schema required fields, types, enums, supported version behavior, and additive optional fields.
- Verify original bytes, parsed JSON, normalized records, and findings remain distinct; parsed JSON reserialization is not asserted byte-identical.
- Preserve malformed raw frame bytes and rejection reasons when byte capture is supported; verify limitation reporting otherwise.
- Verify source fields remain unchanged and every normalized field rename/conversion requires a versioned mapping.
- Verify documented wire-unit basis differs from independently verified firmware provenance.
- Verify host monotonic values are process-local and are never compared across process restart.
- Verify missing, invalid, unverified, stale, and not-mapped channel states do not become zero.

### Per-invocation detector tests

- Temperature-only detector scores valid temperature while pressure is unavailable.
- Pressure-dependent detector emits `not_scored`, null score, `undetermined` decision, and `PRESSURE_MAPPING_UNVERIFIED` until mapping verification is available.
- Detector-specific minimum window failure emits `insufficient_data` with reason codes; it does not set a global record status.
- Non-null ML scores require score semantics and model/configuration provenance.
- Score does not imply confirmed anomaly or ground-truth label.

### Session and epoch tests

- Capture/replay UUID uniqueness; session ID differs from device and boot epoch IDs.
- Complete/incomplete lifecycle and explicit incomplete reasons.
- Replay source path/hash and replay-attempt identity policy.
- Sequence reset or time discontinuity alone does not prove reboot; unknown/inferred epoch includes evidence and confidence.
- Cross-epoch comparisons are blocked by default; explicit support is detector-specific.
- Device-time wrap policy is not inferred without approval.

### Pressure and label tests

- Pressure raw key/value preservation, no silent conversion, unavailable scorer input pending verification, and versioned mapping requirements.
- `approved_nominal` and `known_anomaly` rejected unless authoritative source, version, approval, and traceable record/session scope are present.
- Missing label is `unknown_unlabelled`; sensor acquisition success never implies nominal.
- `LABEL_NEGATIVE_UNLABELLED` remains unknown; OPS-SAT-AD, synthetic, and physical tracks remain distinct.

### Finding/dashboard compatibility tests

- Synthetic finding uses threshold 26.0 C, onset 4000 ms, values `[30.0, 30.2, 30.1, 30.0]`, and all sequence refs `[8, 9, 10, 11]`.
- Deterministic replay in the same session yields the same finding/incident deduplication keys; replay in a new session yields a distinct session-scoped key.
- Sample findings and aggregated incidents have distinct kinds, identity keys, and evidence scopes.
- All finding refs resolve to records in the same session and epoch.
- Raw-record objects are unchanged by normalization, detection, and finding export.
- Telemetry export contains telemetry only; finding/evidence export contains finding objects only.
- Existing `/api/state` fields and legacy incident rendering remain backward-compatible during migration.
- Preserve all current assertions, including 14 total records, exact event refs, onset, threshold, and same incident between API state and evidence export.
- Fixture integrity check confirms `physical_demo/fixtures/synthetic_anomaly.jsonl` remains unchanged.

### Acceptance criteria

- Engineering approves schema versions, source enum, replay identity, boot-epoch inference, deduplication, and label authority policies.
- Physical-specific sensor provenance and mappings require authoritative firmware revision and actual capture evidence.
- Pressure remains excluded from pressure-dependent ML scoring until its complete mapping is verified.
- Raw telemetry and findings remain separate, integrity-linked artifacts.
- Existing dashboard contract and assertions remain compatible during migration.
- October 17 physical status remains `FAIL_ACCEPTANCE`; synthetic or software tests cannot promote it.

## 9. Unresolved decisions for Aaditya and engineering review

1. Normalized schema version policy: integer major version or semantic version string; additive-field compatibility rules.
2. Accepted evidence for `known` versus `inferred` boot epochs; confidence vocabulary and epoch-boundary handling.
3. Replay reset identity: new session UUID or attempt UUID under a parent replay session.
4. Per-channel freshness thresholds and authoritative clock basis.
5. Stable finding ID encoding and canonicalization/hash algorithm for deduplication keys.
6. Finding retention/history policy and whether sample findings persist after aggregation.
7. Approved label authority, approval roles, definitions, and interval boundary conventions for each evidence track.
8. Raw malformed-frame retention format and storage constraints in the current receiver workflow.
9. Actual pressure field, unit, conversion, and canonical channel, pending firmware/capture evidence.
10. API compatibility duration, new export endpoint/name, and UI source labels.
11. Which detectors may run on documented-but-not-physically-verified temperature semantics, and their provenance gates.

## Recommended location

This contract is located at `physical_demo/FINDINGS_CONTRACT.md`, beside the protocol and dashboard implementation. Link it from `physical_demo/README.md` only after engineering approval.
