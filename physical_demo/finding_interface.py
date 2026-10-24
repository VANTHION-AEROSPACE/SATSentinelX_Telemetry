"""Shared validation boundary for rule-based and future ML findings."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any


SCHEMA = "satsentinel.detector-finding"
SCHEMA_VERSION = 1
STATUSES = {"scored", "insufficient_data", "not_scored"}
DECISIONS = {"anomaly", "no_alert", "undetermined"}
FINDING_KINDS = {"sample_result", "aggregated_incident"}


class FindingContractError(ValueError):
    """Raised when a detector result does not meet the shared finding contract."""


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise FindingContractError(f"{field} must be an object")
    return value


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FindingContractError(f"{field} must be a non-empty string")
    return value


def validate_finding(finding: Mapping[str, Any]) -> None:
    """Validate the detector-agnostic JSON finding envelope.

    Event-style ``event.record_refs`` supports the existing synthetic finding;
    future sample or incident findings may use ``evidence.record_refs``.
    """
    if not isinstance(finding, Mapping):
        raise FindingContractError("finding must be an object")
    if finding.get("schema") != SCHEMA or type(finding.get("schema_version")) is not int or finding["schema_version"] != SCHEMA_VERSION:
        raise FindingContractError("unsupported finding schema or version")

    _require_text(finding.get("finding_id"), "finding_id")
    _require_text(finding.get("deduplication_key"), "deduplication_key")
    _require_text(finding.get("session_id"), "session_id")
    finding_kind = finding.get("finding_kind")
    if not isinstance(finding_kind, str) or finding_kind not in FINDING_KINDS:
        raise FindingContractError("finding_kind is unsupported")

    source = _require_mapping(finding.get("source"), "source")
    _require_text(source.get("type"), "source.type")
    _require_text(source.get("id"), "source.id")
    detector = _require_mapping(finding.get("detector"), "detector")
    for field in ("name", "version", "kind"):
        _require_text(detector.get(field), f"detector.{field}")

    evaluation = _require_mapping(finding.get("evaluation"), "evaluation")
    status = evaluation.get("status")
    decision = evaluation.get("decision")
    if not isinstance(status, str) or status not in STATUSES:
        raise FindingContractError("evaluation.status is unsupported")
    if not isinstance(decision, str) or decision not in DECISIONS:
        raise FindingContractError("evaluation.decision is unsupported")
    score = evaluation.get("score")
    score_semantics = evaluation.get("score_semantics")
    if score is not None:
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(float(score)):
            raise FindingContractError("evaluation.score must be a finite number or null")
        _require_text(score_semantics, "evaluation.score_semantics")
    if status in {"insufficient_data", "not_scored"}:
        if decision != "undetermined" or score is not None:
            raise FindingContractError("unscored findings require undetermined decision and null score")

    channels = finding.get("affected_channels")
    if not isinstance(channels, list) or any(not isinstance(channel, Mapping) for channel in channels):
        raise FindingContractError("affected_channels must be a list of objects")
    for channel in channels:
        _require_text(channel.get("channel_id"), "affected_channels[].channel_id")

    event = finding.get("event")
    evidence = finding.get("evidence")
    refs = event.get("record_refs") if isinstance(event, Mapping) else None
    if refs is None and isinstance(evidence, Mapping):
        refs = evidence.get("record_refs")
    if not isinstance(refs, list):
        raise FindingContractError("record_refs must be provided under event or evidence")
    if status == "scored" and not refs:
        raise FindingContractError("scored findings require at least one evidence reference")
    for record_ref in refs:
        if not isinstance(record_ref, Mapping):
            raise FindingContractError("record_refs entries must be objects")
        ref_session_id = record_ref.get("session_id")
        if ref_session_id != finding["session_id"]:
            raise FindingContractError("record reference session_id does not match the finding")

    explanation = _require_mapping(finding.get("explanation"), "explanation")
    _require_text(explanation.get("summary"), "explanation.summary")
    reasons = explanation.get("reason_codes")
    if not isinstance(reasons, list) or any(not isinstance(reason, str) or not reason for reason in reasons):
        raise FindingContractError("explanation.reason_codes must be a list of non-empty strings")
    if status in {"insufficient_data", "not_scored"} and not reasons:
        raise FindingContractError("unscored findings require at least one reason code")
