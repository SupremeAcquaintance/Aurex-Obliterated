from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s5_bitcoin_core_history_payload import S5HistoryBinding
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S5_GITHUB_BULK_FAILURE_ADJUDICATION = (
    "REQUEST_DISPATCHED_LOCAL_HTTPX_RESPONSE_CONTEXT_MANAGER_DEFECT_ZERO_BODY_CAPTURED"
)
S5_GITHUB_BULK_FAILURE_NEXT = "FREEZE_S5_GITHUB_BULK_RESPONSE_HANDLING_AMENDMENT_V2_ONLY"
S5_GITHUB_BULK_AMENDMENT_DECISION = (
    "REPLACE_RESPONSE_CONTEXT_MANAGER_WITH_CLIENT_STREAM_AND_REPLAY_PAGE_ONE_ONCE"
)
S5_GITHUB_BULK_AMENDMENT_NEXT = "RUN_S5_GITHUB_METADATA_BULK_ACQUISITION_V2_ONCE_RESUMABLE"


class S5GitHubBulkFailureAudit(BaseModel):
    schema_version: Literal["aurex-s5-github-bulk-failure-audit-v1"] = (
        "aurex-s5-github-bulk-failure-audit-v1"
    )
    audit_id: Literal["s5-github-bulk-failure-audit-v1"] = "s5-github-bulk-failure-audit-v1"
    audited_at: datetime
    auditor_contract_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=6, max_length=6)
    protocol_evidence_hash: str
    protocol_audit_evidence_hash: str
    prior_result_evidence_hash: str
    prior_result_file_sha256: str
    failure_artifact_file_sha256: str
    prior_runner_contract_hash: str
    request_attempt_count: Literal[1] = 1
    request_dispatch_initiated: Literal[True] = True
    response_object_returned_before_local_error: Literal[True] = True
    http_status_captured: Literal[False] = False
    response_headers_captured: Literal[False] = False
    response_body_bytes_captured: Literal[0] = 0
    metadata_records_parsed: Literal[0] = 0
    successful_pages_persisted: Literal[0] = 0
    failure_type: Literal["PageFailure"] = "PageFailure"
    local_error_type: Literal["TypeError"] = "TypeError"
    local_error_message: Literal[
        "'Response' object does not support the context manager protocol"
    ] = "'Response' object does not support the context manager protocol"
    root_cause: Literal["HTTPX_RESPONSE_IS_NOT_A_CONTEXT_MANAGER_IN_INSTALLED_RUNTIME"] = (
        "HTTPX_RESPONSE_IS_NOT_A_CONTEXT_MANAGER_IN_INSTALLED_RUNTIME"
    )
    exact_correction: Literal[
        "USE_HTTPX_CLIENT_STREAM_CONTEXT_MANAGER_WITH_IDENTICAL_REQUEST_AND_LIMITS"
    ] = "USE_HTTPX_CLIENT_STREAM_CONTEXT_MANAGER_WITH_IDENTICAL_REQUEST_AND_LIMITS"
    original_stop_preserved: Literal[True] = True
    page_one_replay_required: Literal[True] = True
    maximum_total_request_attempts_remains: Literal[300] = 300
    additional_request_authority_beyond_protocol_ceiling: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    adjudication: Literal[
        "REQUEST_DISPATCHED_LOCAL_HTTPX_RESPONSE_CONTEXT_MANAGER_DEFECT_ZERO_BODY_CAPTURED"
    ] = S5_GITHUB_BULK_FAILURE_ADJUDICATION
    next_authorization: Literal["FREEZE_S5_GITHUB_BULK_RESPONSE_HANDLING_AMENDMENT_V2_ONLY"] = (
        S5_GITHUB_BULK_FAILURE_NEXT
    )
    limitations: tuple[str, ...] = Field(min_length=10)
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "auditor_contract_hash",
        "protocol_evidence_hash",
        "protocol_audit_evidence_hash",
        "prior_result_evidence_hash",
        "prior_result_file_sha256",
        "failure_artifact_file_sha256",
        "prior_runner_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5GitHubBulkFailureAudit:
        paths = tuple(item.path for item in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 GitHub bulk failure-audit bindings changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 GitHub bulk failure audit hash changed")
        return self


class S5GitHubBulkResponseHandlingAmendmentV2(BaseModel):
    schema_version: Literal["aurex-s5-github-bulk-response-amendment-v2"] = (
        "aurex-s5-github-bulk-response-amendment-v2"
    )
    amendment_id: Literal["s5-github-bulk-response-amendment-v2"] = (
        "s5-github-bulk-response-amendment-v2"
    )
    frozen_at: datetime
    status: Literal["FROZEN_RESPONSE_HANDLING_AMENDMENT_ZERO_NETWORK"] = (
        "FROZEN_RESPONSE_HANDLING_AMENDMENT_ZERO_NETWORK"
    )
    builder_contract_hash: str
    failure_audit_evidence_hash: str
    prior_result_evidence_hash: str
    protocol_evidence_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=3, max_length=3)
    prior_response_handling: Literal["WITH_CLIENT_SEND_RESPONSE_AS_CONTEXT_MANAGER"] = (
        "WITH_CLIENT_SEND_RESPONSE_AS_CONTEXT_MANAGER"
    )
    corrected_response_handling: Literal["WITH_HTTPX_CLIENT_STREAM_CONTEXT_MANAGER"] = (
        "WITH_HTTPX_CLIENT_STREAM_CONTEXT_MANAGER"
    )
    request_method_unchanged: Literal[True] = True
    endpoint_unchanged: Literal[True] = True
    query_scope_unchanged: Literal[True] = True
    headers_unchanged: Literal[True] = True
    authentication_policy_unchanged: Literal[True] = True
    timeout_and_byte_limits_unchanged: Literal[True] = True
    pagination_and_rate_policy_unchanged: Literal[True] = True
    raw_page_schema_unchanged: Literal[True] = True
    gate_ids_unchanged: Literal[True] = True
    page_one_maximum_total_attempts_after_replay: Literal[2] = 2
    every_other_page_maximum_attempts: Literal[1] = 1
    maximum_total_request_attempts_including_prior_failure: Literal[300] = 300
    maximum_corrected_run_attempts: Literal[299] = 299
    corrected_run_count: Literal[1] = 1
    credential_access_permitted: Literal[False] = False
    market_values_permitted: Literal[False] = False
    parameters_permitted: Literal[False] = False
    returns_permitted: Literal[False] = False
    candidates_permitted: Literal[False] = False
    orders_permitted: Literal[False] = False
    decision: Literal[
        "REPLACE_RESPONSE_CONTEXT_MANAGER_WITH_CLIENT_STREAM_AND_REPLAY_PAGE_ONE_ONCE"
    ] = S5_GITHUB_BULK_AMENDMENT_DECISION
    next_authorization: Literal["RUN_S5_GITHUB_METADATA_BULK_ACQUISITION_V2_ONCE_RESUMABLE"] = (
        S5_GITHUB_BULK_AMENDMENT_NEXT
    )
    limitations: tuple[str, ...] = Field(min_length=10)
    amendment_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "failure_audit_evidence_hash",
        "prior_result_evidence_hash",
        "protocol_evidence_hash",
        "amendment_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_amendment(self) -> S5GitHubBulkResponseHandlingAmendmentV2:
        paths = tuple(item.path for item in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 GitHub bulk amendment bindings changed")
        if any(
            (
                self.credential_access_permitted,
                self.market_values_permitted,
                self.parameters_permitted,
                self.returns_permitted,
                self.candidates_permitted,
                self.orders_permitted,
            )
        ):
            raise ValueError("S5 GitHub bulk amendment broadened authority")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"amendment_evidence_hash"})
        )
        if self.amendment_evidence_hash != expected:
            raise ValueError("S5 GitHub bulk amendment hash changed")
        return self


class S5GitHubBulkResponseHandlingAmendmentAuditV2(BaseModel):
    schema_version: Literal["aurex-s5-github-bulk-response-amendment-audit-v2"] = (
        "aurex-s5-github-bulk-response-amendment-audit-v2"
    )
    audit_id: Literal["s5-github-bulk-response-amendment-audit-v2"] = (
        "s5-github-bulk-response-amendment-audit-v2"
    )
    audited_at: datetime
    amendment_path: Literal[
        "data/evidence/s5_bitcoin_core_github_bulk_response_handling_amendment_v2.json"
    ] = "data/evidence/s5_bitcoin_core_github_bulk_response_handling_amendment_v2.json"
    amendment_file_sha256: str
    amendment_evidence_hash: str
    failure_audit_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    additional_network_requests_observed: Literal[0] = 0
    metadata_records_newly_acquired: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    next_authorization: Literal["RUN_S5_GITHUB_METADATA_BULK_ACQUISITION_V2_ONCE_RESUMABLE"] = (
        S5_GITHUB_BULK_AMENDMENT_NEXT
    )
    decision: Literal["PASS_S5_GITHUB_BULK_RESPONSE_AMENDMENT_AUDIT_V2"] = (
        "PASS_S5_GITHUB_BULK_RESPONSE_AMENDMENT_AUDIT_V2"
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
        "failure_audit_evidence_hash",
        "builder_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5GitHubBulkResponseHandlingAmendmentAuditV2:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 GitHub bulk amendment audit hash changed")
        return self


class S5GitHubBulkCorrectedResultAuditV2(BaseModel):
    schema_version: Literal["aurex-s5-github-bulk-corrected-result-audit-v2"] = (
        "aurex-s5-github-bulk-corrected-result-audit-v2"
    )
    audit_id: Literal["s5-github-bulk-corrected-result-audit-v2"] = (
        "s5-github-bulk-corrected-result-audit-v2"
    )
    audited_at: datetime
    result_path: Literal["data/evidence/s5_bitcoin_core_github_bulk_result_v2.json"] = (
        "data/evidence/s5_bitcoin_core_github_bulk_result_v2.json"
    )
    result_file_sha256: str
    result_evidence_hash: str
    protocol_evidence_hash: str
    amendment_evidence_hash: str
    amendment_audit_evidence_hash: str
    runner_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    every_page_file_hash_reverified: Literal[True] = True
    every_response_body_hash_reverified: Literal[True] = True
    original_failed_request_attempt_count: Literal[1] = 1
    corrected_request_attempt_count: int = Field(ge=1, le=299)
    total_request_attempt_count: int = Field(ge=2, le=300)
    page_count: int = Field(ge=1, le=299)
    raw_record_count: int = Field(gt=0)
    cohort_record_count: int = Field(gt=0)
    duplicate_pull_number_count: Literal[0] = 0
    passed_gate_count: Literal[16] = 16
    failed_gate_count: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    next_authorization: Literal[
        "FREEZE_S5_GITHUB_METADATA_NORMALIZATION_AND_COMPLETENESS_PROTOCOL_ONLY"
    ] = "FREEZE_S5_GITHUB_METADATA_NORMALIZATION_AND_COMPLETENESS_PROTOCOL_ONLY"
    decision: Literal["PASS_S5_GITHUB_BULK_CORRECTED_RESULT_AUDIT_V2"] = (
        "PASS_S5_GITHUB_BULK_CORRECTED_RESULT_AUDIT_V2"
    )
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "result_file_sha256",
        "result_evidence_hash",
        "protocol_evidence_hash",
        "amendment_evidence_hash",
        "amendment_audit_evidence_hash",
        "runner_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5GitHubBulkCorrectedResultAuditV2:
        if self.total_request_attempt_count != (
            self.original_failed_request_attempt_count + self.corrected_request_attempt_count
        ):
            raise ValueError("S5 GitHub bulk corrected total request count changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 GitHub bulk corrected result audit hash changed")
        return self


def evidence_hash_valid(model: BaseModel, field: str) -> bool:
    expected = universe_evidence_hash(model.model_dump(mode="json", exclude={field}))
    return getattr(model, field) == expected
