from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from aurex.backtest_engine.periodic_flow_raw_trades_payload_pilot import (
    RAW_PAYLOAD_FAIL_AUTHORIZATION,
    RAW_PAYLOAD_FAIL_DECISION,
    RAW_PAYLOAD_PASS_AUTHORIZATION,
    RAW_PAYLOAD_PASS_DECISION,
    RawTradesPayloadPilotAudit,
    RawTradesPayloadPilotResult,
)
from aurex.backtest_engine.universe import normalize_sha256, universe_evidence_hash


class RawTradesPayloadPilotResultV2(RawTradesPayloadPilotResult):
    schema_version: Literal[
        "aurex-q1-usdm-raw-trades-payload-pilot-result-v2"
    ] = "aurex-q1-usdm-raw-trades-payload-pilot-result-v2"
    result_id: Literal["q1-usdm-raw-trades-payload-pilot-result-v2"] = (
        "q1-usdm-raw-trades-payload-pilot-result-v2"
    )
    request_marker_manifest_hash: str
    request_marker_count: int = Field(ge=1, le=3)

    @field_validator("request_marker_manifest_hash")
    @classmethod
    def normalize_marker_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_marker_lineage(self) -> RawTradesPayloadPilotResultV2:
        if self.request_marker_count != self.payload_get_attempt_count:
            raise ValueError("Q1 raw payload request-marker count changed")
        return self


class RawTradesPayloadPilotAuditV2(RawTradesPayloadPilotAudit):
    schema_version: Literal[
        "aurex-q1-usdm-raw-trades-payload-pilot-audit-v2"
    ] = "aurex-q1-usdm-raw-trades-payload-pilot-audit-v2"
    audit_id: Literal["q1-usdm-raw-trades-payload-pilot-audit-v2"] = (
        "q1-usdm-raw-trades-payload-pilot-audit-v2"
    )
    request_marker_manifest_hash: str
    request_marker_count: int = Field(ge=1, le=3)

    @field_validator("request_marker_manifest_hash")
    @classmethod
    def normalize_marker_hash(cls, value: str) -> str:
        return normalize_sha256(value)


def _build(model, hash_field: str, values: dict):
    provisional = model.model_construct(**values, **{hash_field: "0" * 64})
    payload = provisional.model_dump()
    payload[hash_field] = universe_evidence_hash(
        provisional.model_dump(exclude={hash_field})
    )
    return model.model_validate(payload)


def build_raw_payload_result_v2(**values) -> RawTradesPayloadPilotResultV2:
    raw = values["raw_archive_evidence"]
    clock = values["paired_clock_evidence"]
    passed = raw.archive_pass and clock.paired_clock_pass
    payload = {
        **values,
        "decision": (
            RAW_PAYLOAD_PASS_DECISION if passed else RAW_PAYLOAD_FAIL_DECISION
        ),
        "next_authorization": (
            RAW_PAYLOAD_PASS_AUTHORIZATION
            if passed
            else RAW_PAYLOAD_FAIL_AUTHORIZATION
        ),
        "authorizes_paired_full_development_acquisition_protocol": passed,
    }
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(RawTradesPayloadPilotResultV2, "result_evidence_hash", payload)


def build_raw_payload_audit_v2(**values) -> RawTradesPayloadPilotAuditV2:
    return _build(RawTradesPayloadPilotAuditV2, "audit_evidence_hash", values)


def audit_raw_payload_result_v2(result: RawTradesPayloadPilotResultV2) -> bool:
    return result.result_evidence_hash == universe_evidence_hash(
        result.model_dump(exclude={"result_evidence_hash"})
    )


def audit_raw_payload_audit_v2(audit: RawTradesPayloadPilotAuditV2) -> bool:
    return audit.audit_evidence_hash == universe_evidence_hash(
        audit.model_dump(exclude={"audit_evidence_hash"})
    )
