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

S5_GITHUB_BULK_DRIFT_ADJUDICATION = (
    "PAGE_118_HTTP_200_VALID_TERMINAL_GREW_244_TO_245_RESPONSE_LOCALLY_REUSABLE"
)
S5_GITHUB_BULK_DRIFT_NEXT = "FREEZE_S5_GITHUB_BULK_MONOTONIC_TERMINAL_AMENDMENT_V4_ONLY"
S5_GITHUB_BULK_MONOTONIC_DECISION = (
    "PROMOTE_PRESERVED_PAGE_118_AND_ALLOW_BOUNDED_NONDECREASING_TERMINAL_PAGE"
)
S5_GITHUB_BULK_MONOTONIC_NEXT = "RUN_S5_GITHUB_METADATA_BULK_ACQUISITION_V4_ONCE_RESUMABLE"


class S5GitHubBulkTerminalDriftFailureAuditV3(BaseModel):
    schema_version: Literal["aurex-s5-github-bulk-terminal-drift-audit-v3"] = (
        "aurex-s5-github-bulk-terminal-drift-audit-v3"
    )
    audit_id: Literal["s5-github-bulk-terminal-drift-audit-v3"] = (
        "s5-github-bulk-terminal-drift-audit-v3"
    )
    audited_at: datetime
    auditor_contract_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=7, max_length=7)
    protocol_evidence_hash: str
    resume_amendment_evidence_hash: str
    resume_amendment_audit_evidence_hash: str
    prior_result_evidence_hash: str
    prior_result_file_sha256: str
    failure_artifact_file_sha256: str
    prior_runner_contract_hash: str
    original_failed_request_attempt_count: Literal[1] = 1
    corrected_v2_request_attempt_count: Literal[117] = 117
    corrected_v3_request_attempt_count: Literal[1] = 1
    total_request_attempt_count: Literal[119] = 119
    maximum_total_request_attempts: Literal[300] = 300
    remaining_request_attempt_capacity: Literal[181] = 181
    successful_page_prefix_count: Literal[117] = 117
    candidate_page: Literal[118] = 118
    candidate_page_http_status: Literal[200] = 200
    candidate_page_response_bytes: int = Field(gt=0, le=4_194_304)
    candidate_page_response_body_sha256: str
    candidate_page_record_count: Literal[100] = 100
    candidate_page_schema_valid: Literal[True] = True
    candidate_page_continues_creation_order: Literal[True] = True
    candidate_page_pull_numbers_disjoint_from_prefix: Literal[True] = True
    prior_terminal_page: Literal[244] = 244
    observed_terminal_page: Literal[245] = 245
    terminal_page_growth: Literal[1] = 1
    protocol_maximum_terminal_page: Literal[300] = 300
    candidate_page_reusable_without_request: Literal[True] = True
    original_cohort_cutoff_preserved: Literal[True] = True
    btc_market_values_read: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    adjudication: Literal[
        "PAGE_118_HTTP_200_VALID_TERMINAL_GREW_244_TO_245_RESPONSE_LOCALLY_REUSABLE"
    ] = S5_GITHUB_BULK_DRIFT_ADJUDICATION
    next_authorization: Literal[
        "FREEZE_S5_GITHUB_BULK_MONOTONIC_TERMINAL_AMENDMENT_V4_ONLY"
    ] = S5_GITHUB_BULK_DRIFT_NEXT
    limitations: tuple[str, ...] = Field(min_length=11)
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "auditor_contract_hash",
        "protocol_evidence_hash",
        "resume_amendment_evidence_hash",
        "resume_amendment_audit_evidence_hash",
        "prior_result_evidence_hash",
        "prior_result_file_sha256",
        "failure_artifact_file_sha256",
        "prior_runner_contract_hash",
        "candidate_page_response_body_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5GitHubBulkTerminalDriftFailureAuditV3:
        paths = tuple(item.path for item in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 GitHub terminal-drift bindings changed")
        if self.total_request_attempt_count + self.remaining_request_attempt_capacity != 300:
            raise ValueError("S5 GitHub terminal-drift request budget changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 GitHub terminal-drift audit hash changed")
        return self


class S5GitHubBulkMonotonicTerminalAmendmentV4(BaseModel):
    schema_version: Literal["aurex-s5-github-bulk-monotonic-terminal-amendment-v4"] = (
        "aurex-s5-github-bulk-monotonic-terminal-amendment-v4"
    )
    amendment_id: Literal["s5-github-bulk-monotonic-terminal-amendment-v4"] = (
        "s5-github-bulk-monotonic-terminal-amendment-v4"
    )
    frozen_at: datetime
    status: Literal["FROZEN_MONOTONIC_TERMINAL_AMENDMENT_ZERO_NETWORK"] = (
        "FROZEN_MONOTONIC_TERMINAL_AMENDMENT_ZERO_NETWORK"
    )
    builder_contract_hash: str
    terminal_drift_audit_evidence_hash: str
    prior_result_evidence_hash: str
    protocol_evidence_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=4, max_length=4)
    locally_promoted_page: Literal[118] = 118
    promoted_page_source_schema: Literal["aurex-s5-github-bulk-failure-page-v3"] = (
        "aurex-s5-github-bulk-failure-page-v3"
    )
    promoted_page_target_schema: Literal["aurex-s5-github-bulk-page-v1"] = (
        "aurex-s5-github-bulk-page-v1"
    )
    promoted_response_body_unchanged: Literal[True] = True
    promoted_response_headers_unchanged: Literal[True] = True
    promoted_page_additional_request_count: Literal[0] = 0
    preserved_page_first: Literal[1] = 1
    preserved_page_last_after_promotion: Literal[118] = 118
    resume_page: Literal[119] = 119
    observed_terminal_page: Literal[245] = 245
    maximum_terminal_page: Literal[300] = 300
    terminal_policy: Literal[
        "ALLOW_NONDECREASING_TERMINAL_PAGE_NOT_ABOVE_PROTOCOL_MAXIMUM"
    ] = "ALLOW_NONDECREASING_TERMINAL_PAGE_NOT_ABOVE_PROTOCOL_MAXIMUM"
    final_canonical_page_count_controls_manifest: Literal[True] = True
    cohort_created_at_cutoff_unchanged: Literal[True] = True
    post_cutoff_records_excluded_from_cohort: Literal[True] = True
    previous_total_request_attempts: Literal[119] = 119
    maximum_total_request_attempts: Literal[300] = 300
    maximum_v4_request_attempts: Literal[181] = 181
    maximum_completable_terminal_page: Literal[299] = 299
    minimum_requests_required_at_freeze: Literal[127] = 127
    endpoint_query_headers_unchanged: Literal[True] = True
    response_and_page_byte_limits_unchanged: Literal[True] = True
    one_attempt_per_new_page_unchanged: Literal[True] = True
    credential_access_permitted: Literal[False] = False
    market_values_permitted: Literal[False] = False
    parameters_permitted: Literal[False] = False
    returns_permitted: Literal[False] = False
    candidates_permitted: Literal[False] = False
    orders_permitted: Literal[False] = False
    decision: Literal[
        "PROMOTE_PRESERVED_PAGE_118_AND_ALLOW_BOUNDED_NONDECREASING_TERMINAL_PAGE"
    ] = S5_GITHUB_BULK_MONOTONIC_DECISION
    next_authorization: Literal[
        "RUN_S5_GITHUB_METADATA_BULK_ACQUISITION_V4_ONCE_RESUMABLE"
    ] = S5_GITHUB_BULK_MONOTONIC_NEXT
    limitations: tuple[str, ...] = Field(min_length=12)
    amendment_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "terminal_drift_audit_evidence_hash",
        "prior_result_evidence_hash",
        "protocol_evidence_hash",
        "amendment_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_amendment(self) -> S5GitHubBulkMonotonicTerminalAmendmentV4:
        paths = tuple(item.path for item in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 GitHub monotonic-terminal bindings changed")
        if self.previous_total_request_attempts + self.maximum_v4_request_attempts != 300:
            raise ValueError("S5 GitHub monotonic-terminal request budget changed")
        if (
            self.preserved_page_last_after_promotion + self.maximum_v4_request_attempts
            != self.maximum_completable_terminal_page
        ):
            raise ValueError("S5 GitHub monotonic-terminal completion bound changed")
        if self.observed_terminal_page - self.preserved_page_last_after_promotion != (
            self.minimum_requests_required_at_freeze
        ):
            raise ValueError("S5 GitHub monotonic-terminal page arithmetic changed")
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
            raise ValueError("S5 GitHub monotonic-terminal amendment broadened authority")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"amendment_evidence_hash"})
        )
        if self.amendment_evidence_hash != expected:
            raise ValueError("S5 GitHub monotonic-terminal amendment hash changed")
        return self


class S5GitHubBulkMonotonicTerminalAmendmentAuditV4(BaseModel):
    schema_version: Literal["aurex-s5-github-bulk-monotonic-terminal-audit-v4"] = (
        "aurex-s5-github-bulk-monotonic-terminal-audit-v4"
    )
    audit_id: Literal["s5-github-bulk-monotonic-terminal-audit-v4"] = (
        "s5-github-bulk-monotonic-terminal-audit-v4"
    )
    audited_at: datetime
    amendment_path: Literal[
        "data/evidence/s5_bitcoin_core_github_bulk_monotonic_terminal_amendment_v4.json"
    ] = "data/evidence/s5_bitcoin_core_github_bulk_monotonic_terminal_amendment_v4.json"
    amendment_file_sha256: str
    amendment_evidence_hash: str
    terminal_drift_audit_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    candidate_page_reverified: Literal[True] = True
    additional_network_requests_observed: Literal[0] = 0
    metadata_records_newly_acquired: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    next_authorization: Literal[
        "RUN_S5_GITHUB_METADATA_BULK_ACQUISITION_V4_ONCE_RESUMABLE"
    ] = S5_GITHUB_BULK_MONOTONIC_NEXT
    decision: Literal["PASS_S5_GITHUB_BULK_MONOTONIC_TERMINAL_AUDIT_V4"] = (
        "PASS_S5_GITHUB_BULK_MONOTONIC_TERMINAL_AUDIT_V4"
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
        "terminal_drift_audit_evidence_hash",
        "builder_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5GitHubBulkMonotonicTerminalAmendmentAuditV4:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 GitHub monotonic-terminal audit hash changed")
        return self


class S5GitHubBulkFinalResultAuditV4(BaseModel):
    schema_version: Literal["aurex-s5-github-bulk-final-result-audit-v4"] = (
        "aurex-s5-github-bulk-final-result-audit-v4"
    )
    audit_id: Literal["s5-github-bulk-final-result-audit-v4"] = (
        "s5-github-bulk-final-result-audit-v4"
    )
    audited_at: datetime
    result_path: Literal["data/evidence/s5_bitcoin_core_github_bulk_result_v4.json"] = (
        "data/evidence/s5_bitcoin_core_github_bulk_result_v4.json"
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
    corrected_v2_request_attempt_count: Literal[117] = 117
    corrected_v3_request_attempt_count: Literal[1] = 1
    corrected_v4_request_attempt_count: int = Field(ge=127, le=181)
    total_request_attempt_count: int = Field(ge=246, le=300)
    page_count: int = Field(ge=245, le=300)
    raw_record_count: int = Field(gt=0)
    cohort_record_count: int = Field(gt=0)
    post_cutoff_record_count: int = Field(ge=0)
    duplicate_pull_number_count: Literal[0] = 0
    passed_gate_count: Literal[16] = 16
    failed_gate_count: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    next_authorization: Literal[
        "FREEZE_S5_GITHUB_METADATA_NORMALIZATION_AND_COMPLETENESS_PROTOCOL_ONLY"
    ] = "FREEZE_S5_GITHUB_METADATA_NORMALIZATION_AND_COMPLETENESS_PROTOCOL_ONLY"
    decision: Literal["PASS_S5_GITHUB_BULK_FINAL_RESULT_AUDIT_V4"] = (
        "PASS_S5_GITHUB_BULK_FINAL_RESULT_AUDIT_V4"
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
    def validate_audit(self) -> S5GitHubBulkFinalResultAuditV4:
        expected_total = (
            self.original_failed_request_attempt_count
            + self.corrected_v2_request_attempt_count
            + self.corrected_v3_request_attempt_count
            + self.corrected_v4_request_attempt_count
        )
        if self.total_request_attempt_count != expected_total:
            raise ValueError("S5 GitHub final total request count changed")
        if self.page_count != 118 + self.corrected_v4_request_attempt_count:
            raise ValueError("S5 GitHub final page/request accounting changed")
        if self.total_request_attempt_count != self.page_count + 1:
            raise ValueError("S5 GitHub final historical request accounting changed")
        if self.raw_record_count != self.cohort_record_count + self.post_cutoff_record_count:
            raise ValueError("S5 GitHub final cohort accounting changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 GitHub final result audit hash changed")
        return self


def evidence_hash_valid(model: BaseModel, field: str) -> bool:
    expected = universe_evidence_hash(model.model_dump(mode="json", exclude={field}))
    return getattr(model, field) == expected
