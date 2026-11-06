from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S3_FEASIBILITY_PROTOCOL_DECISION = (
    "FREEZE_S3_CFTC_POINT_IN_TIME_SOURCE_FEASIBILITY_PROTOCOL"
)
S3_FEASIBILITY_RUN_AUTHORIZATION = (
    "RUN_S3_CFTC_POINT_IN_TIME_SOURCE_FEASIBILITY_ONCE"
)
S3_FEASIBILITY_PASS = "PASS_S3_CFTC_POINT_IN_TIME_SOURCE_FEASIBILITY"
S3_FEASIBILITY_STOP = (
    "STOP_S3_CFTC_POINT_IN_TIME_SOURCE_FEASIBILITY_FAILED_RETIRE_S3"
)
S3_FEASIBILITY_NEXT = "AUTHORIZE_S3_CFTC_POSITION_PAYLOAD_PROTOCOL_ONLY"
S3_FEASIBILITY_NONE = (
    "NONE_S3_CFTC_POINT_IN_TIME_SOURCE_FEASIBILITY_FAILED_RETIRE_S3"
)

S3_FEASIBILITY_GATE_IDS = (
    "METADATA_ENDPOINTS_AVAILABLE",
    "OFFICIAL_CFTC_AUTHORITY",
    "REPORT_DATE_DISTINCT_FROM_RELEASE_DATE",
    "HISTORICAL_RELEASE_DATE_COVERAGE_2022_2024",
    "PER_REPORT_ACTUAL_RELEASE_TIMESTAMP_AVAILABLE",
    "DELAY_AND_BACKLOG_METADATA_AVAILABLE",
    "REVISION_IDENTITY_LEDGER_COMPLETE",
    "ZERO_DOLLAR_PUBLIC_METADATA_ACCESS",
    "REUSE_RIGHTS_EXPLICIT",
    "ZERO_TARGET_POSITION_OR_MARKET_VALUES_ACCESSED",
)


class S3FeasibilityBinding(BaseModel):
    path: str = Field(min_length=1)
    file_sha256: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("file_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)


class S3MetadataEndpointSpec(BaseModel):
    endpoint_id: Literal[
        "COT_FAQ",
        "HISTORICAL_SPECIAL_ANNOUNCEMENTS",
        "HISTORICAL_VIEWABLE_INDEX",
    ]
    url: str
    required_text_tokens: tuple[str, ...] = Field(min_length=1)
    permits_target_position_rows: Literal[False] = False

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_endpoint(self) -> S3MetadataEndpointSpec:
        if not self.url.startswith(
            "https://www.cftc.gov/MarketReports/CommitmentsofTraders/"
        ):
            raise ValueError("S3 metadata endpoint escaped official CFTC authority")
        if self.required_text_tokens != tuple(sorted(set(self.required_text_tokens))):
            raise ValueError("S3 metadata tokens must be unique and sorted")
        return self


class S3CftcSourceFeasibilityProtocol(BaseModel):
    schema_version: Literal["aurex-s3-cftc-source-feasibility-protocol-v1"] = (
        "aurex-s3-cftc-source-feasibility-protocol-v1"
    )
    protocol_id: Literal["s3-cftc-source-feasibility-protocol-v1"] = (
        "s3-cftc-source-feasibility-protocol-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_BEFORE_CFTC_METADATA_REQUESTS"] = (
        "FROZEN_BEFORE_CFTC_METADATA_REQUESTS"
    )
    builder_contract_hash: str
    charter_evidence_hash: str
    source_bindings: tuple[S3FeasibilityBinding, ...] = Field(
        min_length=4, max_length=4
    )
    metadata_endpoints: tuple[S3MetadataEndpointSpec, ...] = Field(
        min_length=3, max_length=3
    )
    development_release_coverage_start: datetime
    development_release_coverage_end_exclusive: datetime
    maximum_metadata_requests: Literal[3] = 3
    maximum_response_bytes_each: Literal[4_000_000] = 4_000_000
    request_timeout_seconds: Literal[30] = 30
    required_gate_ids: tuple[str, ...] = S3_FEASIBILITY_GATE_IDS
    actual_release_timestamp_required: Literal[True] = True
    scheduled_release_date_is_sufficient: Literal[False] = False
    report_as_of_date_is_sufficient: Literal[False] = False
    partial_historical_coverage_is_sufficient: Literal[False] = False
    metadata_html_permitted: Literal[True] = True
    target_position_rows_permitted: Literal[False] = False
    target_position_values_permitted: Literal[False] = False
    btc_market_values_permitted: Literal[False] = False
    payload_acquisition_permitted: Literal[False] = False
    parameters_permitted: Literal[False] = False
    returns_permitted: Literal[False] = False
    historical_screen_permitted: Literal[False] = False
    validation_permitted: Literal[False] = False
    holdout_permitted: Literal[False] = False
    paper_permitted: Literal[False] = False
    testnet_strategy_orders_permitted: Literal[False] = False
    production_permitted: Literal[False] = False
    live_permitted: Literal[False] = False
    decision: Literal[
        "FREEZE_S3_CFTC_POINT_IN_TIME_SOURCE_FEASIBILITY_PROTOCOL"
    ] = S3_FEASIBILITY_PROTOCOL_DECISION
    next_authorization: Literal[
        "RUN_S3_CFTC_POINT_IN_TIME_SOURCE_FEASIBILITY_ONCE"
    ] = S3_FEASIBILITY_RUN_AUTHORIZATION
    limitations: tuple[str, ...] = Field(min_length=7)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator(
        "frozen_at",
        "development_release_coverage_start",
        "development_release_coverage_end_exclusive",
    )
    @classmethod
    def normalize_times(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "charter_evidence_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S3CftcSourceFeasibilityProtocol:
        paths = tuple(item.path for item in self.source_bindings)
        endpoint_ids = tuple(item.endpoint_id for item in self.metadata_endpoints)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S3 feasibility source bindings must be unique and sorted")
        if endpoint_ids != (
            "COT_FAQ",
            "HISTORICAL_SPECIAL_ANNOUNCEMENTS",
            "HISTORICAL_VIEWABLE_INDEX",
        ):
            raise ValueError("S3 feasibility metadata endpoints changed")
        if self.required_gate_ids != S3_FEASIBILITY_GATE_IDS:
            raise ValueError("S3 feasibility gates changed")
        if self.development_release_coverage_start.isoformat() != (
            "2022-01-01T00:00:00+00:00"
        ) or self.development_release_coverage_end_exclusive.isoformat() != (
            "2025-01-01T00:00:00+00:00"
        ):
            raise ValueError("S3 feasibility development coverage changed")
        if self.limitations != tuple(sorted(set(self.limitations))):
            raise ValueError("S3 feasibility limitations must be unique and sorted")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S3 feasibility protocol hash changed")
        return self


class S3CftcSourceFeasibilityProtocolAudit(BaseModel):
    schema_version: Literal[
        "aurex-s3-cftc-source-feasibility-protocol-audit-v1"
    ] = "aurex-s3-cftc-source-feasibility-protocol-audit-v1"
    audit_id: Literal["s3-cftc-source-feasibility-protocol-audit-v1"] = (
        "s3-cftc-source-feasibility-protocol-audit-v1"
    )
    audited_at: datetime
    protocol_path: Literal[
        "data/evidence/s3_cftc_source_feasibility_protocol_v1.json"
    ] = "data/evidence/s3_cftc_source_feasibility_protocol_v1.json"
    protocol_file_sha256: str
    protocol_evidence_hash: str
    charter_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    network_requests_observed: Literal[0] = 0
    cftc_target_position_values_observed: Literal[0] = 0
    btc_market_values_observed: Literal[0] = 0
    orders_observed: Literal[0] = 0
    decision: Literal[
        "PASS_S3_CFTC_SOURCE_FEASIBILITY_PROTOCOL_AUDIT"
    ] = "PASS_S3_CFTC_SOURCE_FEASIBILITY_PROTOCOL_AUDIT"
    next_authorization: Literal[
        "RUN_S3_CFTC_POINT_IN_TIME_SOURCE_FEASIBILITY_ONCE"
    ] = S3_FEASIBILITY_RUN_AUTHORIZATION
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "charter_evidence_hash",
        "builder_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S3CftcSourceFeasibilityProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S3 feasibility protocol-audit hash changed")
        return self


class S3MetadataAttempt(BaseModel):
    endpoint_id: Literal[
        "COT_FAQ",
        "HISTORICAL_SPECIAL_ANNOUNCEMENTS",
        "HISTORICAL_VIEWABLE_INDEX",
    ]
    requested_at: datetime
    http_status: int = Field(ge=0, le=599)
    response_bytes: int = Field(ge=0, le=4_000_000)
    response_sha256: str | None
    response_path: str | None
    official_authority_matched: bool
    matched_text_tokens: tuple[str, ...]
    request_succeeded: bool
    error_class: Literal[
        "NONE", "HTTP_ERROR", "NETWORK_ERROR", "RESPONSE_TOO_LARGE", "INVALID_TEXT"
    ]
    target_position_rows_parsed: Literal[0] = 0
    target_position_values_read: Literal[0] = 0

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("requested_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("response_sha256")
    @classmethod
    def normalize_optional_hash(cls, value: str | None) -> str | None:
        return None if value is None else normalize_sha256(value)

    @model_validator(mode="after")
    def validate_attempt(self) -> S3MetadataAttempt:
        complete = (
            self.http_status == 200
            and self.response_bytes > 0
            and self.response_sha256 is not None
            and self.response_path is not None
            and self.official_authority_matched
            and self.error_class == "NONE"
        )
        if self.request_succeeded != complete:
            raise ValueError("S3 metadata attempt success state changed")
        if self.matched_text_tokens != tuple(sorted(set(self.matched_text_tokens))):
            raise ValueError("S3 metadata matched tokens must be unique and sorted")
        return self


class S3FeasibilityGateResult(BaseModel):
    gate_id: str = Field(min_length=1)
    status: Literal["PASS", "FAIL"]
    detail: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid", frozen=True)


class S3CftcSourceFeasibilityResult(BaseModel):
    schema_version: Literal["aurex-s3-cftc-source-feasibility-result-v1"] = (
        "aurex-s3-cftc-source-feasibility-result-v1"
    )
    result_id: Literal["s3-cftc-source-feasibility-result-v1"] = (
        "s3-cftc-source-feasibility-result-v1"
    )
    generated_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    protocol_audit_file_sha256: str
    protocol_audit_evidence_hash: str
    runner_contract_hash: str
    metadata_attempts: tuple[S3MetadataAttempt, ...] = Field(
        min_length=3, max_length=3
    )
    gate_results: tuple[S3FeasibilityGateResult, ...] = Field(
        min_length=10, max_length=10
    )
    passed_gate_count: int = Field(ge=0, le=10)
    failed_gate_count: int = Field(ge=0, le=10)
    metadata_request_count: Literal[3] = 3
    historical_release_date_list_available: bool
    per_report_actual_release_timestamp_available: bool
    delay_and_backlog_metadata_available: bool
    revision_identity_ledger_complete: bool
    zero_dollar_public_access_observed: bool
    reuse_rights_explicit: bool
    cftc_target_position_rows_parsed: Literal[0] = 0
    cftc_target_position_values_read: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    payload_rows_acquired: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    blockers: tuple[str, ...] = Field(min_length=1)
    decision: Literal[
        "PASS_S3_CFTC_POINT_IN_TIME_SOURCE_FEASIBILITY",
        "STOP_S3_CFTC_POINT_IN_TIME_SOURCE_FEASIBILITY_FAILED_RETIRE_S3",
    ]
    next_authorization: Literal[
        "AUTHORIZE_S3_CFTC_POSITION_PAYLOAD_PROTOCOL_ONLY",
        "NONE_S3_CFTC_POINT_IN_TIME_SOURCE_FEASIBILITY_FAILED_RETIRE_S3",
    ]
    authorizes_position_payload: Literal[False] = False
    authorizes_market_values: Literal[False] = False
    authorizes_parameters: Literal[False] = False
    authorizes_returns: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    real_net_profit_usd: Literal["0"] = "0"
    limitations: tuple[str, ...] = Field(min_length=7)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("generated_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "protocol_audit_file_sha256",
        "protocol_audit_evidence_hash",
        "runner_contract_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> S3CftcSourceFeasibilityResult:
        endpoint_ids = tuple(item.endpoint_id for item in self.metadata_attempts)
        gate_ids = tuple(item.gate_id for item in self.gate_results)
        statuses = tuple(item.status for item in self.gate_results)
        if endpoint_ids != (
            "COT_FAQ",
            "HISTORICAL_SPECIAL_ANNOUNCEMENTS",
            "HISTORICAL_VIEWABLE_INDEX",
        ):
            raise ValueError("S3 feasibility result endpoint set changed")
        if gate_ids != S3_FEASIBILITY_GATE_IDS:
            raise ValueError("S3 feasibility result gates changed")
        if (
            self.passed_gate_count != statuses.count("PASS")
            or self.failed_gate_count != statuses.count("FAIL")
        ):
            raise ValueError("S3 feasibility result gate counts changed")
        state_gates = {
            "HISTORICAL_RELEASE_DATE_COVERAGE_2022_2024": (
                self.historical_release_date_list_available
            ),
            "PER_REPORT_ACTUAL_RELEASE_TIMESTAMP_AVAILABLE": (
                self.per_report_actual_release_timestamp_available
            ),
            "DELAY_AND_BACKLOG_METADATA_AVAILABLE": (
                self.delay_and_backlog_metadata_available
            ),
            "REVISION_IDENTITY_LEDGER_COMPLETE": self.revision_identity_ledger_complete,
            "ZERO_DOLLAR_PUBLIC_METADATA_ACCESS": self.zero_dollar_public_access_observed,
            "REUSE_RIGHTS_EXPLICIT": self.reuse_rights_explicit,
        }
        actual_gate_status = {item.gate_id: item.status for item in self.gate_results}
        if any(
            (actual_gate_status[gate_id] == "PASS") != passed
            for gate_id, passed in state_gates.items()
        ):
            raise ValueError("S3 feasibility result state and gates diverged")
        expected_decision = (
            S3_FEASIBILITY_PASS if self.failed_gate_count == 0 else S3_FEASIBILITY_STOP
        )
        expected_next = (
            S3_FEASIBILITY_NEXT
            if expected_decision == S3_FEASIBILITY_PASS
            else S3_FEASIBILITY_NONE
        )
        if (
            self.decision != expected_decision
            or self.next_authorization != expected_next
            or self.blockers != tuple(sorted(set(self.blockers)))
            or self.limitations != tuple(sorted(set(self.limitations)))
        ):
            raise ValueError("S3 feasibility result authority changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("S3 feasibility result hash changed")
        return self


class S3CftcSourceFeasibilityResultAudit(BaseModel):
    schema_version: Literal[
        "aurex-s3-cftc-source-feasibility-result-audit-v1"
    ] = "aurex-s3-cftc-source-feasibility-result-audit-v1"
    audit_id: Literal["s3-cftc-source-feasibility-result-audit-v1"] = (
        "s3-cftc-source-feasibility-result-audit-v1"
    )
    audited_at: datetime
    result_file_sha256: str
    result_evidence_hash: str
    protocol_file_sha256: str
    protocol_evidence_hash: str
    protocol_audit_evidence_hash: str
    runner_contract_hash: str
    auditor_contract_hash: str
    response_artifact_count: Literal[3] = 3
    response_artifacts_verified: Literal[True] = True
    result_reconstructed_exactly: Literal[True] = True
    passed_gate_count: int = Field(ge=0, le=10)
    failed_gate_count: int = Field(ge=0, le=10)
    cftc_target_position_values_read: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal[
        "CONFIRM_S3_CFTC_POINT_IN_TIME_SOURCE_FEASIBILITY_PASSED",
        "CONFIRM_S3_CFTC_POINT_IN_TIME_SOURCE_FEASIBILITY_FAILED_RETIRE_S3",
    ]
    lineage_next_authorization: Literal[
        "AUTHORIZE_S3_CFTC_POSITION_PAYLOAD_PROTOCOL_ONLY",
        "NONE_S3_CFTC_POINT_IN_TIME_SOURCE_FEASIBILITY_FAILED_RETIRE_S3",
    ]
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "result_file_sha256",
        "result_evidence_hash",
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "protocol_audit_evidence_hash",
        "runner_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S3CftcSourceFeasibilityResultAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S3 feasibility result-audit hash changed")
        return self


def build_hashed(model, hash_field: str, values: dict):
    provisional = model.model_construct(**values, **{hash_field: "0" * 64})
    payload = provisional.model_dump(mode="json")
    payload[hash_field] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={hash_field})
    )
    return model.model_validate(payload)


def audit_s3_feasibility_protocol(protocol: S3CftcSourceFeasibilityProtocol) -> bool:
    try:
        S3CftcSourceFeasibilityProtocol.model_validate(protocol.model_dump(mode="json"))
    except ValueError:
        return False
    return True


def audit_s3_feasibility_protocol_audit(
    audit: S3CftcSourceFeasibilityProtocolAudit,
) -> bool:
    try:
        S3CftcSourceFeasibilityProtocolAudit.model_validate(
            audit.model_dump(mode="json")
        )
    except ValueError:
        return False
    return True


def audit_s3_feasibility_result(result: S3CftcSourceFeasibilityResult) -> bool:
    try:
        S3CftcSourceFeasibilityResult.model_validate(result.model_dump(mode="json"))
    except ValueError:
        return False
    return True


def audit_s3_feasibility_result_audit(
    audit: S3CftcSourceFeasibilityResultAudit,
) -> bool:
    try:
        S3CftcSourceFeasibilityResultAudit.model_validate(
            audit.model_dump(mode="json")
        )
    except ValueError:
        return False
    return True
