from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)


class S5TargetedCorrectionV2FailureAudit(BaseModel):
    schema_version: Literal[
        "aurex-s5-targeted-correction-v2-schema-failure-audit-v1"
    ] = "aurex-s5-targeted-correction-v2-schema-failure-audit-v1"
    audit_id: Literal["s5-targeted-correction-v2-schema-failure-audit-v1"] = (
        "s5-targeted-correction-v2-schema-failure-audit-v1"
    )
    audited_at: datetime
    result_file_sha256: str
    result_evidence_hash: str
    failure_artifact_file_sha256: str
    response_body_sha256: str
    auditor_contract_hash: str
    pull_number: Literal[10] = 10
    http_status: Literal[200] = 200
    response_body_byte_count: Literal[16498] = 16_498
    response_identity_verified: Literal[True] = True
    response_transport_completed: Literal[True] = True
    merged_flag: Literal[True] = True
    merge_commit_sha_source_value: Literal[""] = ""
    schema_failure_field: Literal["merge_commit_sha"] = "merge_commit_sha"
    schema_failure_reason: Literal["EMPTY_STRING_NOT_PREVIOUSLY_PERMITTED"] = (
        "EMPTY_STRING_NOT_PREVIOUSLY_PERMITTED"
    )
    pull_10_must_not_be_requested_again: Literal[True] = True
    v3_untouched_request_target_count: Literal[193] = 193
    maximum_cumulative_possible_request_count: Literal[195] = 195
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["PASS_S5_TARGETED_CORRECTION_V2_SCHEMA_FAILURE_AUDIT"] = (
        "PASS_S5_TARGETED_CORRECTION_V2_SCHEMA_FAILURE_AUDIT"
    )
    next_authorization: Literal[
        "FREEZE_S5_TARGETED_CORRECTION_V3_SCHEMA_REMEDIATION_PROTOCOL_ONLY"
    ] = "FREEZE_S5_TARGETED_CORRECTION_V3_SCHEMA_REMEDIATION_PROTOCOL_ONLY"
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "result_file_sha256",
        "result_evidence_hash",
        "failure_artifact_file_sha256",
        "response_body_sha256",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5TargetedCorrectionV2FailureAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 targeted v2 failure audit hash changed")
        return self
