from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s3_cftc_source_feasibility import (
    S3CftcSourceFeasibilityResult,
    S3CftcSourceFeasibilityResultAudit,
    S3FeasibilityBinding,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S3_TRANSPORT_FAILURE_ADJUDICATION = (
    "REJECT_TERMINAL_SOURCE_INTERPRETATION_TRANSPORT_FAILED_BEFORE_CFTC_RESPONSE"
)
S3_TRANSPORT_AMENDMENT_AUTHORIZATION = (
    "AUTHORIZE_S3_CFTC_METADATA_TRANSPORT_AMENDMENT_V2_ONLY"
)
S3_TRANSPORT_RUN_AUTHORIZATION = "RUN_S3_CFTC_METADATA_TRANSPORT_V2_ONCE"


class S3CftcSourceTransportFailureAudit(BaseModel):
    schema_version: Literal[
        "aurex-s3-cftc-source-transport-failure-audit-v1"
    ] = "aurex-s3-cftc-source-transport-failure-audit-v1"
    audit_id: Literal["s3-cftc-source-transport-failure-audit-v1"] = (
        "s3-cftc-source-transport-failure-audit-v1"
    )
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    protocol_audit_evidence_hash: str
    result_file_sha256: str
    result_evidence_hash: str
    runner_contract_hash: str
    auditor_contract_hash: str
    metadata_attempt_count: Literal[3] = 3
    network_error_count: Literal[3] = 3
    successful_response_count: Literal[0] = 0
    response_artifact_count: Literal[0] = 0
    cftc_target_position_values_read: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    original_decision: Literal[
        "STOP_S3_CFTC_POINT_IN_TIME_SOURCE_FEASIBILITY_FAILED_RETIRE_S3"
    ] = "STOP_S3_CFTC_POINT_IN_TIME_SOURCE_FEASIBILITY_FAILED_RETIRE_S3"
    adjudication: Literal[
        "REJECT_TERMINAL_SOURCE_INTERPRETATION_TRANSPORT_FAILED_BEFORE_CFTC_RESPONSE"
    ] = S3_TRANSPORT_FAILURE_ADJUDICATION
    next_authorization: Literal[
        "AUTHORIZE_S3_CFTC_METADATA_TRANSPORT_AMENDMENT_V2_ONLY"
    ] = S3_TRANSPORT_AMENDMENT_AUTHORIZATION
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "protocol_audit_evidence_hash",
        "result_file_sha256",
        "result_evidence_hash",
        "runner_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S3CftcSourceTransportFailureAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S3 transport-failure audit hash changed")
        return self


class S3CftcMetadataTransportAmendmentV2(BaseModel):
    schema_version: Literal[
        "aurex-s3-cftc-metadata-transport-amendment-v2"
    ] = "aurex-s3-cftc-metadata-transport-amendment-v2"
    amendment_id: Literal["s3-cftc-metadata-transport-amendment-v2"] = (
        "s3-cftc-metadata-transport-amendment-v2"
    )
    frozen_at: datetime
    status: Literal["FROZEN_AFTER_ZERO_RESPONSE_NETWORK_FAILURE"] = (
        "FROZEN_AFTER_ZERO_RESPONSE_NETWORK_FAILURE"
    )
    builder_contract_hash: str
    protocol_evidence_hash: str
    prior_result_evidence_hash: str
    failure_audit_evidence_hash: str
    source_bindings: tuple[S3FeasibilityBinding, ...] = Field(
        min_length=4, max_length=4
    )
    endpoint_ids: tuple[
        Literal[
            "COT_FAQ",
            "HISTORICAL_SPECIAL_ANNOUNCEMENTS",
            "HISTORICAL_VIEWABLE_INDEX",
        ],
        ...,
    ] = (
        "COT_FAQ",
        "HISTORICAL_SPECIAL_ANNOUNCEMENTS",
        "HISTORICAL_VIEWABLE_INDEX",
    )
    transport: Literal["UNSANDBOXED_STANDARD_LIBRARY_HTTPS"] = (
        "UNSANDBOXED_STANDARD_LIBRARY_HTTPS"
    )
    maximum_rerun_count: Literal[1] = 1
    maximum_metadata_requests: Literal[3] = 3
    protocol_urls_and_tokens_unchanged: Literal[True] = True
    protocol_gates_unchanged: Literal[True] = True
    target_position_rows_permitted: Literal[False] = False
    target_position_values_permitted: Literal[False] = False
    btc_market_values_permitted: Literal[False] = False
    parameters_permitted: Literal[False] = False
    returns_permitted: Literal[False] = False
    paper_permitted: Literal[False] = False
    testnet_strategy_orders_permitted: Literal[False] = False
    production_permitted: Literal[False] = False
    live_permitted: Literal[False] = False
    decision: Literal["FREEZE_S3_CFTC_METADATA_TRANSPORT_AMENDMENT_V2"] = (
        "FREEZE_S3_CFTC_METADATA_TRANSPORT_AMENDMENT_V2"
    )
    next_authorization: Literal["RUN_S3_CFTC_METADATA_TRANSPORT_V2_ONCE"] = (
        S3_TRANSPORT_RUN_AUTHORIZATION
    )
    limitations: tuple[str, ...] = Field(min_length=6)
    amendment_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "protocol_evidence_hash",
        "prior_result_evidence_hash",
        "failure_audit_evidence_hash",
        "amendment_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_amendment(self) -> S3CftcMetadataTransportAmendmentV2:
        paths = tuple(item.path for item in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S3 transport-amendment bindings changed")
        if self.limitations != tuple(sorted(set(self.limitations))):
            raise ValueError("S3 transport-amendment limitations changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"amendment_evidence_hash"})
        )
        if self.amendment_evidence_hash != expected:
            raise ValueError("S3 transport-amendment hash changed")
        return self


class S3CftcMetadataTransportAmendmentAuditV2(BaseModel):
    schema_version: Literal[
        "aurex-s3-cftc-metadata-transport-amendment-audit-v2"
    ] = "aurex-s3-cftc-metadata-transport-amendment-audit-v2"
    audit_id: Literal["s3-cftc-metadata-transport-amendment-audit-v2"] = (
        "s3-cftc-metadata-transport-amendment-audit-v2"
    )
    audited_at: datetime
    amendment_file_sha256: str
    amendment_evidence_hash: str
    protocol_evidence_hash: str
    prior_result_evidence_hash: str
    failure_audit_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    additional_network_requests_observed: Literal[0] = 0
    cftc_target_position_values_read: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["PASS_S3_CFTC_METADATA_TRANSPORT_AMENDMENT_V2_AUDIT"] = (
        "PASS_S3_CFTC_METADATA_TRANSPORT_AMENDMENT_V2_AUDIT"
    )
    next_authorization: Literal["RUN_S3_CFTC_METADATA_TRANSPORT_V2_ONCE"] = (
        S3_TRANSPORT_RUN_AUTHORIZATION
    )
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "amendment_file_sha256",
        "amendment_evidence_hash",
        "protocol_evidence_hash",
        "prior_result_evidence_hash",
        "failure_audit_evidence_hash",
        "builder_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S3CftcMetadataTransportAmendmentAuditV2:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S3 transport-amendment audit hash changed")
        return self


class S3CftcSourceFeasibilityResultV2(S3CftcSourceFeasibilityResult):
    schema_version: Literal["aurex-s3-cftc-source-feasibility-result-v2"] = (
        "aurex-s3-cftc-source-feasibility-result-v2"
    )
    result_id: Literal["s3-cftc-source-feasibility-result-v2"] = (
        "s3-cftc-source-feasibility-result-v2"
    )
    prior_result_file_sha256: str
    prior_result_evidence_hash: str
    failure_audit_evidence_hash: str
    transport_amendment_file_sha256: str
    transport_amendment_evidence_hash: str
    transport_amendment_audit_evidence_hash: str

    @field_validator(
        "prior_result_file_sha256",
        "prior_result_evidence_hash",
        "failure_audit_evidence_hash",
        "transport_amendment_file_sha256",
        "transport_amendment_evidence_hash",
        "transport_amendment_audit_evidence_hash",
    )
    @classmethod
    def normalize_lineage_hashes(cls, value: str) -> str:
        return normalize_sha256(value)


class S3CftcSourceFeasibilityResultAuditV2(S3CftcSourceFeasibilityResultAudit):
    schema_version: Literal[
        "aurex-s3-cftc-source-feasibility-result-audit-v2"
    ] = "aurex-s3-cftc-source-feasibility-result-audit-v2"
    audit_id: Literal["s3-cftc-source-feasibility-result-audit-v2"] = (
        "s3-cftc-source-feasibility-result-audit-v2"
    )
    prior_result_evidence_hash: str
    failure_audit_evidence_hash: str
    transport_amendment_evidence_hash: str
    transport_amendment_audit_evidence_hash: str

    @field_validator(
        "prior_result_evidence_hash",
        "failure_audit_evidence_hash",
        "transport_amendment_evidence_hash",
        "transport_amendment_audit_evidence_hash",
    )
    @classmethod
    def normalize_lineage_hashes(cls, value: str) -> str:
        return normalize_sha256(value)


def audit_transport_failure(audit: S3CftcSourceTransportFailureAudit) -> bool:
    try:
        S3CftcSourceTransportFailureAudit.model_validate(audit.model_dump(mode="json"))
    except ValueError:
        return False
    return True


def audit_transport_amendment(amendment: S3CftcMetadataTransportAmendmentV2) -> bool:
    try:
        S3CftcMetadataTransportAmendmentV2.model_validate(
            amendment.model_dump(mode="json")
        )
    except ValueError:
        return False
    return True


def audit_transport_amendment_audit(
    audit: S3CftcMetadataTransportAmendmentAuditV2,
) -> bool:
    try:
        S3CftcMetadataTransportAmendmentAuditV2.model_validate(
            audit.model_dump(mode="json")
        )
    except ValueError:
        return False
    return True
