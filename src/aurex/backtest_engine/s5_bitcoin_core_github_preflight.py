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

S5_GITHUB_PREFLIGHT_PROTOCOL_DECISION = "FREEZE_S5_GITHUB_METADATA_PREFLIGHT_PROTOCOL"
S5_GITHUB_PREFLIGHT_RUN = "RUN_S5_GITHUB_METADATA_PREFLIGHT_ONCE"
S5_GITHUB_PREFLIGHT_PASS = "PASS_S5_GITHUB_METADATA_PREFLIGHT"
S5_GITHUB_PREFLIGHT_STOP = "STOP_S5_GITHUB_METADATA_PREFLIGHT_FAILED_RETIRE_S5"
S5_GITHUB_PREFLIGHT_NEXT = "FREEZE_S5_GITHUB_METADATA_BULK_ACQUISITION_PROTOCOL_ONLY"
S5_GITHUB_PREFLIGHT_NONE = "NONE_S5_GITHUB_METADATA_PREFLIGHT_FAILED_RETIRE_S5"

S5_GITHUB_PREFLIGHT_GATE_IDS = (
    "TRANSPORT_DECISION_AND_READINESS_V31_LINEAGE_BOUND",
    "EXACT_UNAUTHENTICATED_PAGE_ONE_REQUEST_BOUND",
    "ONE_AND_ONLY_ONE_REQUEST_ATTEMPT_EXECUTED",
    "HTTP_200_WITHOUT_REDIRECT",
    "RESPONSE_BODY_BOUNDED_AND_EXACTLY_PRESERVED",
    "JSON_CONTENT_TYPE_AND_PAYLOAD_PARSE_PASS",
    "UNAUTHENTICATED_RATE_LIMIT_HEADERS_VALID",
    "TERMINAL_LINK_PAGE_PARSED_WITH_FROZEN_QUERY_SCOPE",
    "EXACTLY_ONE_CLOSED_MASTER_PULL_RECORD_SCHEMA_VALID",
    "EXACT_BULK_PAGE_AND_RATE_WINDOW_BUDGET_CALCULATED",
    "NO_TOKEN_VALUE_OR_AUTHORIZATION_HEADER_USED",
    "ZERO_BTC_VALUES_PARAMETERS_RETURNS_CANDIDATES_OR_ORDERS",
    "SOURCE_COMPLETENESS_AND_PREDICTIVE_EDGE_NOT_ADJUDICATED",
    "PASS_AUTHORIZES_BULK_ACQUISITION_PROTOCOL_ONLY",
)


class S5GitHubPreflightGateResult(BaseModel):
    gate_id: str = Field(min_length=1)
    status: Literal["PASS", "FAIL"]
    evidence: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid", frozen=True)


class S5GitHubPreflightProtocol(BaseModel):
    schema_version: Literal["aurex-s5-github-preflight-protocol-v1"] = (
        "aurex-s5-github-preflight-protocol-v1"
    )
    protocol_id: Literal["s5-github-preflight-protocol-v1"] = "s5-github-preflight-protocol-v1"
    frozen_at: datetime
    status: Literal["FROZEN_PROTOCOL_ONLY_ZERO_REQUESTS"] = "FROZEN_PROTOCOL_ONLY_ZERO_REQUESTS"
    builder_contract_hash: str
    transport_decision_evidence_hash: str
    transport_decision_audit_evidence_hash: str
    readiness_v31_result_evidence_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=4, max_length=4)
    method: Literal["GET"] = "GET"
    request_url: Literal[
        "https://api.github.com/repos/bitcoin/bitcoin/pulls?state=closed&base=master&sort=created&direction=asc&per_page=1&page=1"
    ] = (
        "https://api.github.com/repos/bitcoin/bitcoin/pulls?state=closed&base=master&sort="
        "created&direction=asc&per_page=1&page=1"
    )
    accept_header: Literal["application/vnd.github+json"] = "application/vnd.github+json"
    api_version_header: Literal["2026-03-10"] = "2026-03-10"
    user_agent: Literal["Aurex-Evidence-Research/1.0"] = "Aurex-Evidence-Research/1.0"
    authorization_header_permitted: Literal[False] = False
    token_value_access_permitted: Literal[False] = False
    environment_proxy_use_permitted: Literal[False] = False
    maximum_request_attempt_count: Literal[1] = 1
    retry_permitted: Literal[False] = False
    maximum_redirects: Literal[0] = 0
    maximum_response_bytes: Literal[1048576] = 1_048_576
    maximum_elapsed_seconds: Literal[60] = 60
    transcript_path: Literal[
        "data/evidence/s5_github_pull_metadata_preflight_transcript_v1.json"
    ] = "data/evidence/s5_github_pull_metadata_preflight_transcript_v1.json"
    result_required_on_every_normal_exit: Literal[True] = True
    rerun_after_result_forbidden: Literal[True] = True
    required_response_headers: tuple[str, ...] = Field(min_length=6, max_length=6)
    required_pull_fields: tuple[str, ...] = Field(min_length=7, max_length=7)
    maximum_records_parsed: Literal[1] = 1
    terminal_link_page_equals_record_count: Literal[True] = True
    bulk_records_per_page: Literal[100] = 100
    unauthenticated_requests_per_hour: Literal[60] = 60
    required_gate_ids: tuple[str, ...] = Field(min_length=14, max_length=14)
    github_api_requests_executed: Literal[0] = 0
    github_metadata_records_parsed: Literal[0] = 0
    network_response_bytes_received: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["FREEZE_S5_GITHUB_METADATA_PREFLIGHT_PROTOCOL"] = (
        S5_GITHUB_PREFLIGHT_PROTOCOL_DECISION
    )
    next_authorization: Literal["RUN_S5_GITHUB_METADATA_PREFLIGHT_ONCE"] = S5_GITHUB_PREFLIGHT_RUN
    authorizes_one_preflight_request: Literal[True] = True
    authorizes_bulk_metadata_acquisition: Literal[False] = False
    authorizes_market_values: Literal[False] = False
    authorizes_parameters: Literal[False] = False
    authorizes_returns: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    limitations: tuple[str, ...] = Field(min_length=10)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "transport_decision_evidence_hash",
        "transport_decision_audit_evidence_hash",
        "readiness_v31_result_evidence_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S5GitHubPreflightProtocol:
        paths = tuple(item.path for item in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 GitHub preflight source bindings changed")
        if self.required_gate_ids != S5_GITHUB_PREFLIGHT_GATE_IDS:
            raise ValueError("S5 GitHub preflight gate sequence changed")
        if self.required_response_headers != (
            "content-type",
            "link",
            "x-ratelimit-limit",
            "x-ratelimit-remaining",
            "x-ratelimit-reset",
            "x-ratelimit-resource",
        ):
            raise ValueError("S5 GitHub preflight response headers changed")
        if self.required_pull_fields != (
            "number",
            "state",
            "created_at",
            "merged_at",
            "merge_commit_sha",
            "base.ref",
            "base.sha",
        ):
            raise ValueError("S5 GitHub preflight pull schema changed")
        if any(
            (
                self.authorization_header_permitted,
                self.token_value_access_permitted,
                self.environment_proxy_use_permitted,
                self.retry_permitted,
                self.authorizes_bulk_metadata_acquisition,
                self.authorizes_market_values,
                self.authorizes_parameters,
                self.authorizes_returns,
                self.authorizes_paper,
                self.authorizes_testnet_strategy_orders,
                self.authorizes_production,
                self.authorizes_live,
            )
        ):
            raise ValueError("S5 GitHub preflight protocol broadened authority")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S5 GitHub preflight protocol hash changed")
        return self


class S5GitHubPreflightProtocolAudit(BaseModel):
    schema_version: Literal["aurex-s5-github-preflight-protocol-audit-v1"] = (
        "aurex-s5-github-preflight-protocol-audit-v1"
    )
    audit_id: Literal["s5-github-preflight-protocol-audit-v1"] = (
        "s5-github-preflight-protocol-audit-v1"
    )
    audited_at: datetime
    protocol_path: Literal["data/evidence/s5_bitcoin_core_github_preflight_protocol_v1.json"] = (
        "data/evidence/s5_bitcoin_core_github_preflight_protocol_v1.json"
    )
    protocol_file_sha256: str
    protocol_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    source_binding_count: Literal[4] = 4
    request_attempts_observed: Literal[0] = 0
    response_bytes_observed: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    next_authorization: Literal["RUN_S5_GITHUB_METADATA_PREFLIGHT_ONCE"] = S5_GITHUB_PREFLIGHT_RUN
    decision: Literal["PASS_S5_GITHUB_PREFLIGHT_PROTOCOL_AUDIT"] = (
        "PASS_S5_GITHUB_PREFLIGHT_PROTOCOL_AUDIT"
    )
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
    def validate_audit(self) -> S5GitHubPreflightProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 GitHub preflight protocol audit hash changed")
        return self


class S5GitHubPreflightResult(BaseModel):
    schema_version: Literal["aurex-s5-github-preflight-result-v1"] = (
        "aurex-s5-github-preflight-result-v1"
    )
    result_id: Literal["s5-github-preflight-result-v1"] = "s5-github-preflight-result-v1"
    executed_at: datetime
    protocol_evidence_hash: str
    runner_contract_hash: str
    transcript_path: Literal[
        "data/evidence/s5_github_pull_metadata_preflight_transcript_v1.json"
    ] = "data/evidence/s5_github_pull_metadata_preflight_transcript_v1.json"
    transcript_file_sha256: str
    transcript_byte_count: int = Field(gt=0)
    request_attempt_count: Literal[1] = 1
    started_at: datetime
    completed_at: datetime
    elapsed_seconds: float = Field(ge=0)
    request_method: Literal["GET"] = "GET"
    request_url: str = Field(min_length=1)
    authorization_header_used: Literal[False] = False
    token_value_accessed: Literal[False] = False
    environment_proxy_used: Literal[False] = False
    redirect_count: Literal[0] = 0
    http_status: int | None = Field(default=None, ge=100, le=599)
    final_url: str | None = None
    response_byte_count: int = Field(ge=0, le=1_048_576)
    response_body_sha256: str | None = None
    content_type: str | None = None
    link_header: str | None = None
    etag_header: str | None = None
    x_ratelimit_limit: int | None = Field(default=None, ge=0)
    x_ratelimit_remaining: int | None = Field(default=None, ge=0)
    x_ratelimit_reset: int | None = Field(default=None, ge=0)
    x_ratelimit_resource: str | None = None
    parsed_pull_record_count: int = Field(ge=0, le=1)
    first_pull_number: int | None = Field(default=None, gt=0)
    first_pull_state: str | None = None
    first_pull_base_ref: str | None = None
    first_pull_base_sha: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    first_pull_created_at: datetime | None = None
    first_pull_merged_at: datetime | None = None
    first_pull_merge_commit_sha: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    terminal_record_count: int | None = Field(default=None, gt=0)
    bulk_request_page_count_at_100: int | None = Field(default=None, gt=0)
    bulk_unauthenticated_hours_lower_bound: int | None = Field(default=None, gt=0)
    gate_results: tuple[S5GitHubPreflightGateResult, ...] = Field(min_length=14, max_length=14)
    passed_gate_count: int = Field(ge=0, le=14)
    failed_gate_count: int = Field(ge=0, le=14)
    github_api_requests_executed: Literal[1] = 1
    github_metadata_records_parsed: int = Field(ge=0, le=1)
    btc_market_values_read: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    source_completeness_conclusion: Literal["NOT_YET_ADJUDICATED"] = "NOT_YET_ADJUDICATED"
    predictive_edge_conclusion: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"
    decision: Literal[
        "PASS_S5_GITHUB_METADATA_PREFLIGHT",
        "STOP_S5_GITHUB_METADATA_PREFLIGHT_FAILED_RETIRE_S5",
    ]
    next_authorization: Literal[
        "FREEZE_S5_GITHUB_METADATA_BULK_ACQUISITION_PROTOCOL_ONLY",
        "NONE_S5_GITHUB_METADATA_PREFLIGHT_FAILED_RETIRE_S5",
    ]
    authorizes_bulk_acquisition_protocol_design: bool
    authorizes_bulk_metadata_acquisition_now: Literal[False] = False
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
    limitations: tuple[str, ...] = Field(min_length=10)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator(
        "executed_at", "started_at", "completed_at", "first_pull_created_at", "first_pull_merged_at"
    )
    @classmethod
    def normalize_times(cls, value: datetime | None) -> datetime | None:
        return None if value is None else normalize_timestamp(value)

    @field_validator(
        "protocol_evidence_hash",
        "runner_contract_hash",
        "transcript_file_sha256",
        "response_body_sha256",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str | None) -> str | None:
        return None if value is None else normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> S5GitHubPreflightResult:
        if self.completed_at < self.started_at:
            raise ValueError("S5 GitHub preflight completion precedes start")
        if self.github_metadata_records_parsed != self.parsed_pull_record_count:
            raise ValueError("S5 GitHub parsed metadata count changed")
        if self.response_byte_count == 0 and self.response_body_sha256 is not None:
            raise ValueError("Empty S5 GitHub response cannot have a body hash")
        if self.response_byte_count > 0 and self.response_body_sha256 is None:
            raise ValueError("Nonempty S5 GitHub response requires a body hash")
        gate_ids = tuple(item.gate_id for item in self.gate_results)
        if gate_ids != S5_GITHUB_PREFLIGHT_GATE_IDS:
            raise ValueError("S5 GitHub preflight result gates changed")
        passed = sum(item.status == "PASS" for item in self.gate_results)
        failed = sum(item.status == "FAIL" for item in self.gate_results)
        if (self.passed_gate_count, self.failed_gate_count) != (passed, failed):
            raise ValueError("S5 GitHub preflight gate counts changed")
        passed_result = failed == 0
        if passed_result:
            if not (
                self.decision == S5_GITHUB_PREFLIGHT_PASS
                and self.next_authorization == S5_GITHUB_PREFLIGHT_NEXT
                and self.authorizes_bulk_acquisition_protocol_design
                and self.http_status == 200
                and self.final_url == self.request_url
                and self.parsed_pull_record_count == 1
                and self.first_pull_state == "closed"
                and self.first_pull_base_ref == "master"
                and self.terminal_record_count is not None
                and self.bulk_request_page_count_at_100 == (self.terminal_record_count + 99) // 100
                and self.bulk_unauthenticated_hours_lower_bound
                == (self.bulk_request_page_count_at_100 + 59) // 60
                and self.failure_type is None
                and self.failure_message is None
            ):
                raise ValueError("Passing S5 GitHub preflight result is inconsistent")
        elif not (
            self.decision == S5_GITHUB_PREFLIGHT_STOP
            and self.next_authorization == S5_GITHUB_PREFLIGHT_NONE
            and not self.authorizes_bulk_acquisition_protocol_design
            and self.failure_type is not None
            and self.failure_message is not None
        ):
            raise ValueError("Failed S5 GitHub preflight result is inconsistent")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("S5 GitHub preflight result hash changed")
        return self


class S5GitHubPreflightResultAudit(BaseModel):
    schema_version: Literal["aurex-s5-github-preflight-result-audit-v1"] = (
        "aurex-s5-github-preflight-result-audit-v1"
    )
    audit_id: Literal["s5-github-preflight-result-audit-v1"] = "s5-github-preflight-result-audit-v1"
    audited_at: datetime
    result_path: Literal["data/evidence/s5_bitcoin_core_github_preflight_result_v1.json"] = (
        "data/evidence/s5_bitcoin_core_github_preflight_result_v1.json"
    )
    result_file_sha256: str
    result_evidence_hash: str
    protocol_evidence_hash: str
    runner_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    transcript_hash_reverified: Literal[True] = True
    response_body_hash_reverified: Literal[True] = True
    request_attempt_count: Literal[1] = 1
    http_status: int | None = Field(default=None, ge=100, le=599)
    terminal_record_count: int | None = Field(default=None, gt=0)
    bulk_request_page_count_at_100: int | None = Field(default=None, gt=0)
    passed_gate_count: int = Field(ge=0, le=14)
    failed_gate_count: int = Field(ge=0, le=14)
    github_api_requests_executed: Literal[1] = 1
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    next_authorization: Literal[
        "FREEZE_S5_GITHUB_METADATA_BULK_ACQUISITION_PROTOCOL_ONLY",
        "NONE_S5_GITHUB_METADATA_PREFLIGHT_FAILED_RETIRE_S5",
    ]
    decision: Literal["PASS_S5_GITHUB_PREFLIGHT_RESULT_AUDIT"] = (
        "PASS_S5_GITHUB_PREFLIGHT_RESULT_AUDIT"
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
        "runner_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5GitHubPreflightResultAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 GitHub preflight result audit hash changed")
        return self


def audit_s5_github_preflight_protocol(protocol: S5GitHubPreflightProtocol) -> bool:
    expected = universe_evidence_hash(
        protocol.model_dump(mode="json", exclude={"protocol_evidence_hash"})
    )
    return protocol.protocol_evidence_hash == expected


def audit_s5_github_preflight_protocol_audit(
    audit: S5GitHubPreflightProtocolAudit,
) -> bool:
    expected = universe_evidence_hash(
        audit.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return audit.audit_evidence_hash == expected


def audit_s5_github_preflight_result(result: S5GitHubPreflightResult) -> bool:
    expected = universe_evidence_hash(
        result.model_dump(mode="json", exclude={"result_evidence_hash"})
    )
    return result.result_evidence_hash == expected


def audit_s5_github_preflight_result_audit(
    audit: S5GitHubPreflightResultAudit,
) -> bool:
    expected = universe_evidence_hash(
        audit.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return audit.audit_evidence_hash == expected
