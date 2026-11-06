from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s3_cftc_source_feasibility import S3FeasibilityBinding
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S3_TRANSPORT_V2_FAILURE_MESSAGE = (
    "S3 transport v2 did not receive all three responses; no v2 result was written"
)
S3_TRANSPORT_V2_RETIREMENT = (
    "RETIRE_S3_SOURCE_FEASIBILITY_NOT_ESTABLISHED_WITHIN_FROZEN_PROTOCOL"
)
S3_DISTINCT_SUCCESSOR_AUTHORIZATION = (
    "FREEZE_AND_AUDIT_DISTINCT_S4_MECHANISM_CHARTER_ONLY"
)


class S3CftcMetadataTransportExecutionReceiptV2(BaseModel):
    schema_version: Literal[
        "aurex-s3-cftc-metadata-transport-execution-receipt-v2"
    ] = "aurex-s3-cftc-metadata-transport-execution-receipt-v2"
    receipt_id: Literal["s3-cftc-metadata-transport-execution-receipt-v2"] = (
        "s3-cftc-metadata-transport-execution-receipt-v2"
    )
    recorded_at: datetime
    recorder_contract_hash: str
    runner_contract_hash: str
    protocol_evidence_hash: str
    prior_result_evidence_hash: str
    failure_audit_evidence_hash: str
    transport_amendment_evidence_hash: str
    transport_amendment_audit_evidence_hash: str
    source_bindings: tuple[S3FeasibilityBinding, ...] = Field(
        min_length=6, max_length=6
    )
    authorized_execution_count: Literal[1] = 1
    observed_execution_count: Literal[1] = 1
    maximum_metadata_requests: Literal[3] = 3
    process_exit_code: Literal[1] = 1
    terminal_message: Literal[
        "S3 transport v2 did not receive all three responses; no v2 result was written"
    ] = S3_TRANSPORT_V2_FAILURE_MESSAGE
    result_artifact_path: Literal[
        "data/evidence/s3_cftc_source_feasibility_result_v2.json"
    ] = "data/evidence/s3_cftc_source_feasibility_result_v2.json"
    result_artifact_created: Literal[False] = False
    expected_response_paths: tuple[str, ...] = Field(min_length=3, max_length=3)
    persisted_response_artifact_count: Literal[0] = 0
    successful_response_count_observed: Literal["UNKNOWN_NOT_PERSISTED"] = (
        "UNKNOWN_NOT_PERSISTED"
    )
    all_required_responses_received: Literal[False] = False
    rerun_authority_exhausted: Literal[True] = True
    cftc_target_position_rows_parsed: Literal[0] = 0
    cftc_target_position_values_read: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    parameters_evaluated: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    production_authority: Literal[False] = False
    live_authority: Literal[False] = False
    decision: Literal[
        "RETIRE_S3_SOURCE_FEASIBILITY_NOT_ESTABLISHED_WITHIN_FROZEN_PROTOCOL"
    ] = S3_TRANSPORT_V2_RETIREMENT
    next_authorization: Literal[
        "FREEZE_AND_AUDIT_DISTINCT_S4_MECHANISM_CHARTER_ONLY"
    ] = S3_DISTINCT_SUCCESSOR_AUTHORIZATION
    limitations: tuple[str, ...] = Field(min_length=6)
    receipt_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("recorded_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "recorder_contract_hash",
        "runner_contract_hash",
        "protocol_evidence_hash",
        "prior_result_evidence_hash",
        "failure_audit_evidence_hash",
        "transport_amendment_evidence_hash",
        "transport_amendment_audit_evidence_hash",
        "receipt_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_receipt(self) -> S3CftcMetadataTransportExecutionReceiptV2:
        binding_paths = tuple(item.path for item in self.source_bindings)
        expected_responses = (
            "data/evidence/s3_cftc_metadata_v2/cot_faq.html",
            "data/evidence/s3_cftc_metadata_v2/historical_special_announcements.html",
            "data/evidence/s3_cftc_metadata_v2/historical_viewable_index.html",
        )
        if binding_paths != tuple(sorted(set(binding_paths))):
            raise ValueError("S3 transport receipt bindings changed")
        if self.expected_response_paths != expected_responses:
            raise ValueError("S3 transport receipt response paths changed")
        if self.limitations != tuple(sorted(set(self.limitations))):
            raise ValueError("S3 transport receipt limitations changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"receipt_evidence_hash"})
        )
        if self.receipt_evidence_hash != expected:
            raise ValueError("S3 transport receipt hash changed")
        return self


class S3CftcMetadataTransportExecutionReceiptAuditV2(BaseModel):
    schema_version: Literal[
        "aurex-s3-cftc-metadata-transport-execution-receipt-audit-v2"
    ] = "aurex-s3-cftc-metadata-transport-execution-receipt-audit-v2"
    audit_id: Literal[
        "s3-cftc-metadata-transport-execution-receipt-audit-v2"
    ] = "s3-cftc-metadata-transport-execution-receipt-audit-v2"
    audited_at: datetime
    receipt_file_sha256: str
    receipt_evidence_hash: str
    protocol_evidence_hash: str
    prior_result_evidence_hash: str
    failure_audit_evidence_hash: str
    transport_amendment_evidence_hash: str
    transport_amendment_audit_evidence_hash: str
    runner_contract_hash: str
    recorder_contract_hash: str
    auditor_contract_hash: str
    source_bindings_verified: Literal[True] = True
    result_artifact_absence_verified: Literal[True] = True
    persisted_response_artifact_count: Literal[0] = 0
    rerun_authority_exhaustion_verified: Literal[True] = True
    cftc_target_position_values_read: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal[
        "CONFIRM_S3_SOURCE_FEASIBILITY_NOT_ESTABLISHED_RETIRE_S3"
    ] = "CONFIRM_S3_SOURCE_FEASIBILITY_NOT_ESTABLISHED_RETIRE_S3"
    next_authorization: Literal[
        "FREEZE_AND_AUDIT_DISTINCT_S4_MECHANISM_CHARTER_ONLY"
    ] = S3_DISTINCT_SUCCESSOR_AUTHORIZATION
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "receipt_file_sha256",
        "receipt_evidence_hash",
        "protocol_evidence_hash",
        "prior_result_evidence_hash",
        "failure_audit_evidence_hash",
        "transport_amendment_evidence_hash",
        "transport_amendment_audit_evidence_hash",
        "runner_contract_hash",
        "recorder_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S3CftcMetadataTransportExecutionReceiptAuditV2:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S3 transport receipt-audit hash changed")
        return self


def audit_transport_execution_receipt(
    receipt: S3CftcMetadataTransportExecutionReceiptV2,
) -> bool:
    try:
        S3CftcMetadataTransportExecutionReceiptV2.model_validate(
            receipt.model_dump(mode="json")
        )
    except ValueError:
        return False
    return True


def audit_transport_execution_receipt_audit(
    audit: S3CftcMetadataTransportExecutionReceiptAuditV2,
) -> bool:
    try:
        S3CftcMetadataTransportExecutionReceiptAuditV2.model_validate(
            audit.model_dump(mode="json")
        )
    except ValueError:
        return False
    return True
