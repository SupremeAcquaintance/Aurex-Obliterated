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

S5_GITHUB_BULK_SUSPENSION_ADJUDICATION = (
    "HOST_SUSPENSION_EXCEEDED_RUN_DURATION_ZERO_PAGE_118_REQUEST_PAGES_1_TO_117_VALID"
)
S5_GITHUB_BULK_SUSPENSION_NEXT = "FREEZE_S5_GITHUB_BULK_CONTIGUOUS_RESUME_AMENDMENT_V3_ONLY"
S5_GITHUB_BULK_RESUME_DECISION = "RESUME_FROM_PAGE_118_WITH_NEW_PROCESS_CLOCK_AND_UNCHANGED_COHORT"
S5_GITHUB_BULK_RESUME_NEXT = "RUN_S5_GITHUB_METADATA_BULK_ACQUISITION_V3_ONCE_RESUMABLE"


class S5GitHubBulkSuspensionFailureAuditV2(BaseModel):
    schema_version: Literal["aurex-s5-github-bulk-suspension-failure-audit-v2"] = (
        "aurex-s5-github-bulk-suspension-failure-audit-v2"
    )
    audit_id: Literal["s5-github-bulk-suspension-failure-audit-v2"] = (
        "s5-github-bulk-suspension-failure-audit-v2"
    )
    audited_at: datetime
    auditor_contract_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=7, max_length=7)
    protocol_evidence_hash: str
    response_amendment_evidence_hash: str
    response_amendment_audit_evidence_hash: str
    prior_result_evidence_hash: str
    prior_result_file_sha256: str
    failure_artifact_file_sha256: str
    prior_runner_contract_hash: str
    original_failed_request_attempt_count: Literal[1] = 1
    corrected_v2_request_attempt_count: Literal[117] = 117
    total_request_attempt_count: Literal[118] = 118
    maximum_total_request_attempts: Literal[300] = 300
    remaining_request_attempt_capacity: Literal[182] = 182
    successful_page_count: Literal[117] = 117
    raw_record_count: Literal[11700] = 11_700
    terminal_page_count: Literal[244] = 244
    next_required_page: Literal[118] = 118
    page_file_hashes_reverified: Literal[True] = True
    response_body_hashes_reverified: Literal[True] = True
    page_118_request_attempted: Literal[False] = False
    failure_artifact_http_status_captured: Literal[False] = False
    failure_artifact_response_bytes: Literal[0] = 0
    local_error_type: Literal["ValueError"] = "ValueError"
    local_error_message: Literal["S5 GitHub bulk v2 exceeded the frozen elapsed-time bound"] = (
        "S5 GitHub bulk v2 exceeded the frozen elapsed-time bound"
    )
    original_cohort_cutoff_preserved: Literal[True] = True
    contiguous_resume_feasible: Literal[True] = True
    btc_market_values_read: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    adjudication: Literal[
        "HOST_SUSPENSION_EXCEEDED_RUN_DURATION_ZERO_PAGE_118_REQUEST_PAGES_1_TO_117_VALID"
    ] = S5_GITHUB_BULK_SUSPENSION_ADJUDICATION
    next_authorization: Literal["FREEZE_S5_GITHUB_BULK_CONTIGUOUS_RESUME_AMENDMENT_V3_ONLY"] = (
        S5_GITHUB_BULK_SUSPENSION_NEXT
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
        "response_amendment_evidence_hash",
        "response_amendment_audit_evidence_hash",
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
    def validate_audit(self) -> S5GitHubBulkSuspensionFailureAuditV2:
        paths = tuple(item.path for item in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 GitHub suspension-audit bindings changed")
        if self.total_request_attempt_count + self.remaining_request_attempt_capacity != 300:
            raise ValueError("S5 GitHub suspension request budget changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 GitHub suspension failure audit hash changed")
        return self


class S5GitHubBulkContiguousResumeAmendmentV3(BaseModel):
    schema_version: Literal["aurex-s5-github-bulk-contiguous-resume-amendment-v3"] = (
        "aurex-s5-github-bulk-contiguous-resume-amendment-v3"
    )
    amendment_id: Literal["s5-github-bulk-contiguous-resume-amendment-v3"] = (
        "s5-github-bulk-contiguous-resume-amendment-v3"
    )
    frozen_at: datetime
    status: Literal["FROZEN_CONTIGUOUS_RESUME_AMENDMENT_ZERO_NETWORK"] = (
        "FROZEN_CONTIGUOUS_RESUME_AMENDMENT_ZERO_NETWORK"
    )
    builder_contract_hash: str
    suspension_failure_audit_evidence_hash: str
    prior_result_evidence_hash: str
    protocol_evidence_hash: str
    response_amendment_evidence_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=4, max_length=4)
    preserved_page_first: Literal[1] = 1
    preserved_page_last: Literal[117] = 117
    resume_page: Literal[118] = 118
    terminal_page: Literal[244] = 244
    preserved_record_count: Literal[11700] = 11_700
    previous_total_request_attempts: Literal[118] = 118
    maximum_total_request_attempts: Literal[300] = 300
    maximum_resume_request_attempts: Literal[182] = 182
    minimum_requests_required_to_terminal_page: Literal[127] = 127
    new_process_elapsed_clock_permitted: Literal[True] = True
    original_run_elapsed_bound_seconds: Literal[43200] = 43_200
    protocol_evidence_hash_unchanged: Literal[True] = True
    cohort_cutoff_unchanged: Literal[True] = True
    endpoint_query_headers_unchanged: Literal[True] = True
    page_schema_and_hash_rules_unchanged: Literal[True] = True
    pagination_and_rate_rules_unchanged: Literal[True] = True
    one_attempt_per_remaining_page_unchanged: Literal[True] = True
    credential_access_permitted: Literal[False] = False
    market_values_permitted: Literal[False] = False
    parameters_permitted: Literal[False] = False
    returns_permitted: Literal[False] = False
    candidates_permitted: Literal[False] = False
    orders_permitted: Literal[False] = False
    decision: Literal["RESUME_FROM_PAGE_118_WITH_NEW_PROCESS_CLOCK_AND_UNCHANGED_COHORT"] = (
        S5_GITHUB_BULK_RESUME_DECISION
    )
    next_authorization: Literal["RUN_S5_GITHUB_METADATA_BULK_ACQUISITION_V3_ONCE_RESUMABLE"] = (
        S5_GITHUB_BULK_RESUME_NEXT
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
        "suspension_failure_audit_evidence_hash",
        "prior_result_evidence_hash",
        "protocol_evidence_hash",
        "response_amendment_evidence_hash",
        "amendment_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_amendment(self) -> S5GitHubBulkContiguousResumeAmendmentV3:
        paths = tuple(item.path for item in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 GitHub resume-amendment bindings changed")
        if self.previous_total_request_attempts + self.maximum_resume_request_attempts != 300:
            raise ValueError("S5 GitHub resume request budget changed")
        if (
            self.terminal_page - self.preserved_page_last
            != self.minimum_requests_required_to_terminal_page
        ):
            raise ValueError("S5 GitHub resume terminal-page arithmetic changed")
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
            raise ValueError("S5 GitHub resume amendment broadened authority")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"amendment_evidence_hash"})
        )
        if self.amendment_evidence_hash != expected:
            raise ValueError("S5 GitHub resume amendment hash changed")
        return self


class S5GitHubBulkContiguousResumeAmendmentAuditV3(BaseModel):
    schema_version: Literal["aurex-s5-github-bulk-contiguous-resume-audit-v3"] = (
        "aurex-s5-github-bulk-contiguous-resume-audit-v3"
    )
    audit_id: Literal["s5-github-bulk-contiguous-resume-audit-v3"] = (
        "s5-github-bulk-contiguous-resume-audit-v3"
    )
    audited_at: datetime
    amendment_path: Literal[
        "data/evidence/s5_bitcoin_core_github_bulk_contiguous_resume_amendment_v3.json"
    ] = "data/evidence/s5_bitcoin_core_github_bulk_contiguous_resume_amendment_v3.json"
    amendment_file_sha256: str
    amendment_evidence_hash: str
    suspension_failure_audit_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    preserved_page_hashes_reverified: Literal[True] = True
    additional_network_requests_observed: Literal[0] = 0
    metadata_records_newly_acquired: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    next_authorization: Literal["RUN_S5_GITHUB_METADATA_BULK_ACQUISITION_V3_ONCE_RESUMABLE"] = (
        S5_GITHUB_BULK_RESUME_NEXT
    )
    decision: Literal["PASS_S5_GITHUB_BULK_CONTIGUOUS_RESUME_AUDIT_V3"] = (
        "PASS_S5_GITHUB_BULK_CONTIGUOUS_RESUME_AUDIT_V3"
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
        "suspension_failure_audit_evidence_hash",
        "builder_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5GitHubBulkContiguousResumeAmendmentAuditV3:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 GitHub resume amendment audit hash changed")
        return self


class S5GitHubBulkResumedResultAuditV3(BaseModel):
    schema_version: Literal["aurex-s5-github-bulk-resumed-result-audit-v3"] = (
        "aurex-s5-github-bulk-resumed-result-audit-v3"
    )
    audit_id: Literal["s5-github-bulk-resumed-result-audit-v3"] = (
        "s5-github-bulk-resumed-result-audit-v3"
    )
    audited_at: datetime
    result_path: Literal["data/evidence/s5_bitcoin_core_github_bulk_result_v3.json"] = (
        "data/evidence/s5_bitcoin_core_github_bulk_result_v3.json"
    )
    result_file_sha256: str
    result_evidence_hash: str
    protocol_evidence_hash: str
    resume_amendment_evidence_hash: str
    resume_amendment_audit_evidence_hash: str
    runner_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    every_page_file_hash_reverified: Literal[True] = True
    every_response_body_hash_reverified: Literal[True] = True
    original_failed_request_attempt_count: Literal[1] = 1
    corrected_v2_request_attempt_count: Literal[117] = 117
    corrected_v3_request_attempt_count: int = Field(ge=127, le=182)
    total_request_attempt_count: int = Field(ge=245, le=300)
    page_count: Literal[244] = 244
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
    decision: Literal["PASS_S5_GITHUB_BULK_RESUMED_RESULT_AUDIT_V3"] = (
        "PASS_S5_GITHUB_BULK_RESUMED_RESULT_AUDIT_V3"
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
        "resume_amendment_evidence_hash",
        "resume_amendment_audit_evidence_hash",
        "runner_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5GitHubBulkResumedResultAuditV3:
        expected_total = (
            self.original_failed_request_attempt_count
            + self.corrected_v2_request_attempt_count
            + self.corrected_v3_request_attempt_count
        )
        if self.total_request_attempt_count != expected_total:
            raise ValueError("S5 GitHub resumed total request count changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 GitHub resumed result audit hash changed")
        return self


def evidence_hash_valid(model: BaseModel, field: str) -> bool:
    expected = universe_evidence_hash(model.model_dump(mode="json", exclude={field}))
    return getattr(model, field) == expected
