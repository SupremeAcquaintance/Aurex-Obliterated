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

S5_GITHUB_BULK_PROTOCOL_DECISION = "FREEZE_S5_GITHUB_METADATA_BULK_ACQUISITION_PROTOCOL"
S5_GITHUB_BULK_RUN = "RUN_S5_GITHUB_METADATA_BULK_ACQUISITION_ONCE_RESUMABLE"
S5_GITHUB_BULK_PASS = "PASS_S5_GITHUB_METADATA_BULK_ACQUISITION"
S5_GITHUB_BULK_STOP = "STOP_S5_GITHUB_METADATA_BULK_ACQUISITION_REQUIRES_FAILURE_AUDIT"
S5_GITHUB_BULK_NEXT = "FREEZE_S5_GITHUB_METADATA_NORMALIZATION_AND_COMPLETENESS_PROTOCOL_ONLY"
S5_GITHUB_BULK_FAILURE_NEXT = "FREEZE_S5_GITHUB_METADATA_BULK_FAILURE_AUDIT_ONLY"

S5_GITHUB_BULK_GATE_IDS = (
    "CORRECTED_PREFLIGHT_AND_READINESS_V32_LINEAGE_BOUND",
    "ALL_STATE_STABLE_MEMBERSHIP_QUERY_EXACTLY_BOUND",
    "UNAUTHENTICATED_SERIAL_REQUEST_POLICY_PRESERVED",
    "CONTIGUOUS_PAGE_RANGE_ACQUIRED",
    "HTTP_200_WITHOUT_REDIRECT_FOR_EVERY_PAGE",
    "EVERY_RESPONSE_BODY_BOUNDED_AND_HASH_PRESERVED",
    "EVERY_PAGE_JSON_AND_PULL_SCHEMA_VALID",
    "PAGINATION_SCOPE_AND_TERMINAL_BOUND_VALID",
    "NONTERMINAL_PAGES_FULL_AND_TERMINAL_PAGE_COMPLETE",
    "PULL_NUMBERS_UNIQUE_AND_CREATION_ORDER_MONOTONIC",
    "FROZEN_CREATION_CUTOFF_COHORT_RECONSTRUCTED",
    "RATE_LIMIT_HEADERS_VALID_AND_EXHAUSTION_WAITED",
    "RAW_PAGE_MANIFEST_EXACTLY_RECONSTRUCTABLE",
    "NO_TOKEN_PROXY_MARKET_VALUE_PARAMETER_RETURN_OR_ORDER",
    "SOURCE_COMPLETENESS_AND_PREDICTIVE_EDGE_NOT_ADJUDICATED",
    "PASS_AUTHORIZES_NORMALIZATION_PROTOCOL_ONLY",
)


class S5GitHubBulkGateResult(BaseModel):
    gate_id: str = Field(min_length=1)
    status: Literal["PASS", "FAIL"]
    evidence: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid", frozen=True)


class S5GitHubBulkAcquisitionProtocol(BaseModel):
    schema_version: Literal["aurex-s5-github-bulk-acquisition-protocol-v1"] = (
        "aurex-s5-github-bulk-acquisition-protocol-v1"
    )
    protocol_id: Literal["s5-github-bulk-acquisition-protocol-v1"] = (
        "s5-github-bulk-acquisition-protocol-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_PROTOCOL_ONLY_ZERO_BULK_REQUESTS"] = (
        "FROZEN_PROTOCOL_ONLY_ZERO_BULK_REQUESTS"
    )
    builder_contract_hash: str
    corrected_preflight_result_evidence_hash: str
    corrected_preflight_audit_evidence_hash: str
    readiness_v33_result_evidence_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=4, max_length=4)
    method: Literal["GET"] = "GET"
    endpoint: Literal["https://api.github.com/repos/bitcoin/bitcoin/pulls"] = (
        "https://api.github.com/repos/bitcoin/bitcoin/pulls"
    )
    query_state: Literal["all"] = "all"
    query_base: Literal["master"] = "master"
    query_sort: Literal["created"] = "created"
    query_direction: Literal["asc"] = "asc"
    records_per_page: Literal[100] = 100
    first_page: Literal[1] = 1
    maximum_terminal_page: Literal[300] = 300
    cohort_created_at_cutoff: datetime
    preflight_query_state: Literal["closed"] = "closed"
    stable_membership_adjustment: Literal[
        "ALL_STATE_PREVENTS_OPEN_CLOSED_TRANSITIONS_FROM_CHANGING_MEMBERSHIP"
    ] = "ALL_STATE_PREVENTS_OPEN_CLOSED_TRANSITIONS_FROM_CHANGING_MEMBERSHIP"
    merged_only_filter_deferred_to_normalization: Literal[True] = True
    accept_header: Literal["application/vnd.github+json"] = "application/vnd.github+json"
    api_version_header: Literal["2026-03-10"] = "2026-03-10"
    user_agent: Literal["Aurex-Evidence-Research/1.0"] = "Aurex-Evidence-Research/1.0"
    authorization_header_permitted: Literal[False] = False
    token_value_access_permitted: Literal[False] = False
    environment_proxy_use_permitted: Literal[False] = False
    redirects_permitted: Literal[False] = False
    concurrent_requests_permitted: Literal[1] = 1
    maximum_request_attempts_per_page: Literal[1] = 1
    maximum_total_request_attempts: Literal[300] = 300
    maximum_response_bytes_per_page: Literal[4194304] = 4_194_304
    maximum_total_response_bytes: Literal[1073741824] = 1_073_741_824
    request_timeout_seconds: Literal[120] = 120
    maximum_run_seconds: Literal[43200] = 43_200
    unauthenticated_rate_limit: Literal[60] = 60
    wait_when_remaining_at_or_below: Literal[0] = 0
    reset_safety_seconds: Literal[5] = 5
    maximum_single_wait_seconds: Literal[3700] = 3_700
    raw_page_directory: Literal["data/evidence/s5_github_pull_metadata_bulk_v1"] = (
        "data/evidence/s5_github_pull_metadata_bulk_v1"
    )
    page_file_pattern: Literal["page_{page:04d}.json"] = "page_{page:04d}.json"
    atomic_page_writes_required: Literal[True] = True
    contiguous_resume_only: Literal[True] = True
    overwrite_existing_page_forbidden: Literal[True] = True
    canonical_link_paths: tuple[str, str] = (
        "/repos/bitcoin/bitcoin/pulls",
        "/repositories/1181927/pulls",
    )
    canonical_repository_id: Literal[1181927] = 1_181_927
    required_pull_fields: tuple[str, ...] = Field(min_length=11, max_length=11)
    required_gate_ids: tuple[str, ...] = Field(min_length=16, max_length=16)
    github_api_requests_executed: Literal[0] = 0
    github_metadata_records_parsed: Literal[0] = 0
    network_response_bytes_received: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["FREEZE_S5_GITHUB_METADATA_BULK_ACQUISITION_PROTOCOL"] = (
        S5_GITHUB_BULK_PROTOCOL_DECISION
    )
    next_authorization: Literal["RUN_S5_GITHUB_METADATA_BULK_ACQUISITION_ONCE_RESUMABLE"] = (
        S5_GITHUB_BULK_RUN
    )
    authorizes_bulk_metadata_acquisition: Literal[True] = True
    authorizes_market_values: Literal[False] = False
    authorizes_parameters: Literal[False] = False
    authorizes_returns: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    limitations: tuple[str, ...] = Field(min_length=12)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at", "cohort_created_at_cutoff")
    @classmethod
    def normalize_times(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "corrected_preflight_result_evidence_hash",
        "corrected_preflight_audit_evidence_hash",
        "readiness_v33_result_evidence_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S5GitHubBulkAcquisitionProtocol:
        paths = tuple(item.path for item in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 GitHub bulk source bindings changed")
        if self.required_gate_ids != S5_GITHUB_BULK_GATE_IDS:
            raise ValueError("S5 GitHub bulk gate sequence changed")
        if self.required_pull_fields != (
            "number",
            "node_id",
            "state",
            "created_at",
            "updated_at",
            "closed_at",
            "merged_at",
            "head.sha",
            "base.ref",
            "base.sha",
            "user",
        ):
            raise ValueError("S5 GitHub bulk pull schema changed")
        if self.canonical_link_paths != (
            "/repos/bitcoin/bitcoin/pulls",
            "/repositories/1181927/pulls",
        ):
            raise ValueError("S5 GitHub bulk canonical paths changed")
        if self.cohort_created_at_cutoff != self.frozen_at:
            raise ValueError("S5 GitHub bulk cohort cutoff must equal protocol freeze time")
        if any(
            (
                self.authorization_header_permitted,
                self.token_value_access_permitted,
                self.environment_proxy_use_permitted,
                self.redirects_permitted,
                self.authorizes_market_values,
                self.authorizes_parameters,
                self.authorizes_returns,
                self.authorizes_paper,
                self.authorizes_testnet_strategy_orders,
                self.authorizes_production,
                self.authorizes_live,
            )
        ):
            raise ValueError("S5 GitHub bulk protocol broadened authority")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S5 GitHub bulk protocol hash changed")
        return self


class S5GitHubBulkProtocolAudit(BaseModel):
    schema_version: Literal["aurex-s5-github-bulk-protocol-audit-v1"] = (
        "aurex-s5-github-bulk-protocol-audit-v1"
    )
    audit_id: Literal["s5-github-bulk-protocol-audit-v1"] = "s5-github-bulk-protocol-audit-v1"
    audited_at: datetime
    protocol_path: Literal[
        "data/evidence/s5_bitcoin_core_github_bulk_acquisition_protocol_v1.json"
    ] = "data/evidence/s5_bitcoin_core_github_bulk_acquisition_protocol_v1.json"
    protocol_file_sha256: str
    protocol_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    source_binding_count: Literal[4] = 4
    request_attempts_observed: Literal[0] = 0
    metadata_records_observed: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    next_authorization: Literal["RUN_S5_GITHUB_METADATA_BULK_ACQUISITION_ONCE_RESUMABLE"] = (
        S5_GITHUB_BULK_RUN
    )
    decision: Literal["PASS_S5_GITHUB_BULK_PROTOCOL_AUDIT"] = "PASS_S5_GITHUB_BULK_PROTOCOL_AUDIT"
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "builder_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5GitHubBulkProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 GitHub bulk protocol audit hash changed")
        return self


class S5GitHubBulkPageBinding(BaseModel):
    page: int = Field(ge=1, le=300)
    path: str = Field(min_length=1)
    file_sha256: str
    file_byte_count: int = Field(gt=0)
    response_body_sha256: str
    response_byte_count: int = Field(gt=0, le=4_194_304)
    record_count: int = Field(ge=1, le=100)
    first_pull_number: int = Field(gt=0)
    last_pull_number: int = Field(gt=0)
    rate_limit: Literal[60] = 60
    rate_remaining: int = Field(ge=0, le=59)
    rate_reset: int = Field(gt=0)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("file_sha256", "response_body_sha256")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)


class S5GitHubBulkResult(BaseModel):
    schema_version: Literal["aurex-s5-github-bulk-result-v1"] = "aurex-s5-github-bulk-result-v1"
    result_id: Literal["s5-github-bulk-result-v1"] = "s5-github-bulk-result-v1"
    executed_at: datetime
    started_at: datetime
    completed_at: datetime
    elapsed_seconds: float = Field(ge=0)
    protocol_evidence_hash: str
    runner_contract_hash: str
    raw_page_directory: str = Field(min_length=1)
    page_bindings: tuple[S5GitHubBulkPageBinding, ...]
    logical_request_attempt_count: int = Field(ge=0, le=300)
    new_request_attempt_count: int = Field(ge=0, le=300)
    successful_request_count: int = Field(ge=0, le=300)
    resumed_page_count: int = Field(ge=0, le=300)
    acquired_page_count: int = Field(ge=0, le=300)
    terminal_page_count: int | None = Field(default=None, ge=1, le=300)
    raw_record_count: int = Field(ge=0)
    cohort_record_count: int = Field(ge=0)
    post_cutoff_record_count: int = Field(ge=0)
    open_record_count: int = Field(ge=0)
    closed_unmerged_record_count: int = Field(ge=0)
    merged_record_count: int = Field(ge=0)
    null_user_record_count: int = Field(ge=0)
    unique_pull_number_count: int = Field(ge=0)
    duplicate_pull_number_count: int = Field(ge=0)
    minimum_created_at: datetime | None = None
    maximum_created_at: datetime | None = None
    total_response_bytes: int = Field(ge=0, le=1_073_741_824)
    rate_limit_wait_count: int = Field(ge=0)
    rate_limit_wait_seconds: float = Field(ge=0)
    gate_results: tuple[S5GitHubBulkGateResult, ...] = Field(min_length=16, max_length=16)
    passed_gate_count: int = Field(ge=0, le=16)
    failed_gate_count: int = Field(ge=0, le=16)
    btc_market_values_read: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    source_completeness_conclusion: Literal["NOT_YET_ADJUDICATED"] = "NOT_YET_ADJUDICATED"
    predictive_edge_conclusion: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"
    decision: Literal[
        "PASS_S5_GITHUB_METADATA_BULK_ACQUISITION",
        "STOP_S5_GITHUB_METADATA_BULK_ACQUISITION_REQUIRES_FAILURE_AUDIT",
    ]
    next_authorization: Literal[
        "FREEZE_S5_GITHUB_METADATA_NORMALIZATION_AND_COMPLETENESS_PROTOCOL_ONLY",
        "FREEZE_S5_GITHUB_METADATA_BULK_FAILURE_AUDIT_ONLY",
    ]
    authorizes_normalization_protocol_design: bool
    authorizes_market_values: Literal[False] = False
    authorizes_parameters: Literal[False] = False
    authorizes_returns: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    real_net_profit_usd: Literal["0"] = "0"
    failure_type: str | None = None
    failure_message: str | None = Field(default=None, max_length=2000)
    failure_artifact_path: str | None = None
    failure_artifact_sha256: str | None = None
    limitations: tuple[str, ...] = Field(min_length=12)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator(
        "executed_at",
        "started_at",
        "completed_at",
        "minimum_created_at",
        "maximum_created_at",
    )
    @classmethod
    def normalize_times(cls, value: datetime | None) -> datetime | None:
        return None if value is None else normalize_timestamp(value)

    @field_validator(
        "protocol_evidence_hash",
        "runner_contract_hash",
        "failure_artifact_sha256",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str | None) -> str | None:
        return None if value is None else normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> S5GitHubBulkResult:
        if self.completed_at < self.started_at:
            raise ValueError("S5 GitHub bulk completion precedes start")
        if tuple(item.gate_id for item in self.gate_results) != S5_GITHUB_BULK_GATE_IDS:
            raise ValueError("S5 GitHub bulk result gates changed")
        passed = sum(item.status == "PASS" for item in self.gate_results)
        failed = sum(item.status == "FAIL" for item in self.gate_results)
        if (passed, failed) != (self.passed_gate_count, self.failed_gate_count):
            raise ValueError("S5 GitHub bulk gate counts changed")
        if tuple(item.page for item in self.page_bindings) != tuple(
            range(1, len(self.page_bindings) + 1)
        ):
            raise ValueError("S5 GitHub bulk page bindings are not contiguous")
        if self.successful_request_count != len(self.page_bindings):
            raise ValueError("S5 GitHub bulk successful request count changed")
        if self.resumed_page_count + self.acquired_page_count != len(self.page_bindings):
            raise ValueError("S5 GitHub bulk resume accounting changed")
        if self.raw_record_count != sum(item.record_count for item in self.page_bindings):
            raise ValueError("S5 GitHub bulk raw record accounting changed")
        if (
            self.unique_pull_number_count + self.duplicate_pull_number_count
            != self.raw_record_count
        ):
            raise ValueError("S5 GitHub bulk identity accounting changed")
        if self.cohort_record_count + self.post_cutoff_record_count != self.raw_record_count:
            raise ValueError("S5 GitHub bulk cutoff accounting changed")
        passing = failed == 0
        if passing:
            if not (
                self.decision == S5_GITHUB_BULK_PASS
                and self.next_authorization == S5_GITHUB_BULK_NEXT
                and self.authorizes_normalization_protocol_design
                and self.terminal_page_count == len(self.page_bindings)
                and self.logical_request_attempt_count == len(self.page_bindings)
                and self.new_request_attempt_count == self.acquired_page_count
                and self.duplicate_pull_number_count == 0
                and self.failure_type is None
                and self.failure_message is None
                and self.failure_artifact_path is None
                and self.failure_artifact_sha256 is None
            ):
                raise ValueError("Passing S5 GitHub bulk result is inconsistent")
        elif not (
            self.decision == S5_GITHUB_BULK_STOP
            and self.next_authorization == S5_GITHUB_BULK_FAILURE_NEXT
            and not self.authorizes_normalization_protocol_design
            and self.failure_type is not None
            and self.failure_message is not None
            and (self.failure_artifact_path is None) == (self.failure_artifact_sha256 is None)
        ):
            raise ValueError("Failed S5 GitHub bulk result is inconsistent")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("S5 GitHub bulk result hash changed")
        return self


class S5GitHubBulkResultAudit(BaseModel):
    schema_version: Literal["aurex-s5-github-bulk-result-audit-v1"] = (
        "aurex-s5-github-bulk-result-audit-v1"
    )
    audit_id: Literal["s5-github-bulk-result-audit-v1"] = "s5-github-bulk-result-audit-v1"
    audited_at: datetime
    result_path: Literal["data/evidence/s5_bitcoin_core_github_bulk_result_v1.json"] = (
        "data/evidence/s5_bitcoin_core_github_bulk_result_v1.json"
    )
    result_file_sha256: str
    result_evidence_hash: str
    protocol_evidence_hash: str
    runner_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    every_page_file_hash_reverified: Literal[True] = True
    every_response_body_hash_reverified: Literal[True] = True
    page_count: int = Field(ge=1, le=300)
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
    ] = S5_GITHUB_BULK_NEXT
    decision: Literal["PASS_S5_GITHUB_BULK_RESULT_AUDIT"] = "PASS_S5_GITHUB_BULK_RESULT_AUDIT"
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
        "runner_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5GitHubBulkResultAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 GitHub bulk result audit hash changed")
        return self


def evidence_hash_valid(model: BaseModel, field: str) -> bool:
    expected = universe_evidence_hash(model.model_dump(mode="json", exclude={field}))
    return getattr(model, field) == expected
