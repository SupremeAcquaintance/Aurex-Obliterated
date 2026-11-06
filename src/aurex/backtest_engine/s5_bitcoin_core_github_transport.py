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

S5_GITHUB_TRANSPORT_DECISION = (
    "SELECT_OFFICIAL_REST_CLOSED_MASTER_PULL_LIST_WITH_ONE_REQUEST_PREFLIGHT"
)
S5_GITHUB_TRANSPORT_NEXT = "FREEZE_S5_GITHUB_PULL_REQUEST_METADATA_PREFLIGHT_PROTOCOL_ONLY"

S5_GITHUB_TRANSPORT_GATE_IDS = (
    "CENSUS_AND_READINESS_V30_LINEAGE_BOUND",
    "CENSUS_COUNTS_AND_DIRECT_REQUEST_BUDGET_RECONCILED",
    "OFFICIAL_PULL_LIST_ENDPOINT_AND_PARAMETERS_DOCUMENTED",
    "OFFICIAL_RATE_LIMITS_AND_PAGE_MAXIMUM_DOCUMENTED",
    "DIRECT_PULL_BY_NUMBER_REJECTED_AS_UNAUTHENTICATEDLY_INFEASIBLE",
    "GRAPHQL_REJECTED_WITHOUT_AUTHENTICATION",
    "GIT_ONLY_TRANSPORT_REJECTED_FOR_MISSING_PUBLIC_MERGE_TIME",
    "THIRD_PARTY_ARCHIVES_REJECTED_AS_NONAUTHORITATIVE",
    "ONE_REQUEST_PAGE_ONE_PREFLIGHT_SELECTED",
    "PREFLIGHT_REVEALS_EXACT_RECORD_AND_PAGE_BUDGET_BEFORE_ACQUISITION",
    "ZERO_NETWORK_METADATA_MARKET_VALUES_RETURNS_CANDIDATES_OR_ORDERS",
    "DECISION_AUTHORIZES_PREFLIGHT_PROTOCOL_ONLY",
)


class S5GitHubTransportOption(BaseModel):
    option_id: Literal[
        "DIRECT_PULL_BY_NUMBER",
        "REST_LIST_CLOSED_MASTER_PULLS",
        "GRAPHQL_PULL_REQUEST_PAGINATION",
        "LOCAL_GIT_ONLY",
        "THIRD_PARTY_ARCHIVE",
    ]
    disposition: Literal["SELECTED", "REJECTED"]
    rationale: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid", frozen=True)


class S5GitHubTransportGateResult(BaseModel):
    gate_id: str = Field(min_length=1)
    status: Literal["PASS", "FAIL"]
    evidence: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid", frozen=True)


class S5GitHubTransportDecision(BaseModel):
    schema_version: Literal["aurex-s5-github-transport-decision-v1"] = (
        "aurex-s5-github-transport-decision-v1"
    )
    decision_id: Literal["s5-github-transport-decision-v1"] = "s5-github-transport-decision-v1"
    frozen_at: datetime
    status: Literal["FROZEN_DECISION_ONLY_ZERO_METADATA_REQUESTS"] = (
        "FROZEN_DECISION_ONLY_ZERO_METADATA_REQUESTS"
    )
    builder_contract_hash: str
    census_result_evidence_hash: str
    census_result_audit_evidence_hash: str
    readiness_v30_result_evidence_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=6, max_length=6)
    official_pull_api_documentation_url: Literal["https://docs.github.com/en/rest/pulls/pulls"] = (
        "https://docs.github.com/en/rest/pulls/pulls"
    )
    official_rate_limit_documentation_url: Literal[
        "https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api"
    ] = "https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api"
    endpoint: Literal["https://api.github.com/repos/bitcoin/bitcoin/pulls"] = (
        "https://api.github.com/repos/bitcoin/bitcoin/pulls"
    )
    method: Literal["GET"] = "GET"
    accept_header: Literal["application/vnd.github+json"] = "application/vnd.github+json"
    api_version_header: Literal["2026-03-10"] = "2026-03-10"
    user_agent: Literal["Aurex-Evidence-Research/1.0"] = "Aurex-Evidence-Research/1.0"
    selected_query_state: Literal["closed"] = "closed"
    selected_query_base: Literal["master"] = "master"
    selected_query_sort: Literal["created"] = "created"
    selected_query_direction: Literal["asc"] = "asc"
    preflight_query_per_page: Literal[1] = 1
    preflight_query_page: Literal[1] = 1
    maximum_records_per_list_page: Literal[100] = 100
    unauthenticated_requests_per_hour: Literal[60] = 60
    authenticated_requests_per_hour: Literal[5000] = 5000
    census_recognized_pull_request_count: Literal[7961] = 7961
    census_unrecognized_merge_count: Literal[8760] = 8760
    direct_request_count: Literal[7961] = 7961
    direct_unauthenticated_hours_lower_bound: Literal[133] = 133
    direct_authenticated_hours_lower_bound: Literal[2] = 2
    census_list_page_lower_bound: Literal[80] = 80
    transport_options: tuple[S5GitHubTransportOption, ...] = Field(min_length=5, max_length=5)
    selected_transport: Literal["REST_LIST_CLOSED_MASTER_PULLS"] = "REST_LIST_CLOSED_MASTER_PULLS"
    selected_transport_requires_authentication: Literal[False] = False
    token_value_access_permitted: Literal[False] = False
    preflight_request_count: Literal[1] = 1
    preflight_maximum_response_bytes: Literal[1048576] = 1_048_576
    preflight_maximum_elapsed_seconds: Literal[60] = 60
    preflight_maximum_redirects: Literal[0] = 0
    preflight_fields_permitted: tuple[str, ...] = Field(min_length=8)
    preflight_must_parse_terminal_link_page: Literal[True] = True
    preflight_must_validate_rate_limit_headers: Literal[True] = True
    preflight_must_validate_pull_schema: Literal[True] = True
    acquisition_page_count_known: Literal[False] = False
    acquisition_request_budget_authorized: Literal[False] = False
    required_gate_ids: tuple[str, ...] = Field(min_length=12, max_length=12)
    gate_results: tuple[S5GitHubTransportGateResult, ...] = Field(min_length=12, max_length=12)
    passed_gate_count: Literal[12] = 12
    failed_gate_count: Literal[0] = 0
    github_api_requests_executed: Literal[0] = 0
    github_metadata_records_parsed: Literal[0] = 0
    network_response_bytes_received: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["SELECT_OFFICIAL_REST_CLOSED_MASTER_PULL_LIST_WITH_ONE_REQUEST_PREFLIGHT"] = (
        S5_GITHUB_TRANSPORT_DECISION
    )
    next_authorization: Literal[
        "FREEZE_S5_GITHUB_PULL_REQUEST_METADATA_PREFLIGHT_PROTOCOL_ONLY"
    ] = S5_GITHUB_TRANSPORT_NEXT
    authorizes_preflight_protocol_design: Literal[True] = True
    authorizes_preflight_request_now: Literal[False] = False
    authorizes_bulk_metadata_acquisition: Literal[False] = False
    authorizes_market_values: Literal[False] = False
    authorizes_parameters: Literal[False] = False
    authorizes_returns: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    real_net_profit_usd: Literal["0"] = "0"
    limitations: tuple[str, ...] = Field(min_length=10)
    decision_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "census_result_evidence_hash",
        "census_result_audit_evidence_hash",
        "readiness_v30_result_evidence_hash",
        "decision_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_decision(self) -> S5GitHubTransportDecision:
        paths = tuple(item.path for item in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 GitHub transport source bindings changed")
        if self.required_gate_ids != S5_GITHUB_TRANSPORT_GATE_IDS:
            raise ValueError("S5 GitHub transport decision gates changed")
        if tuple(item.gate_id for item in self.gate_results) != self.required_gate_ids:
            raise ValueError("S5 GitHub transport decision gate results changed")
        if any(item.status != "PASS" for item in self.gate_results):
            raise ValueError("S5 GitHub transport decision contains a failed gate")
        option_ids = tuple(item.option_id for item in self.transport_options)
        if option_ids != (
            "DIRECT_PULL_BY_NUMBER",
            "REST_LIST_CLOSED_MASTER_PULLS",
            "GRAPHQL_PULL_REQUEST_PAGINATION",
            "LOCAL_GIT_ONLY",
            "THIRD_PARTY_ARCHIVE",
        ):
            raise ValueError("S5 GitHub transport options changed")
        selected = tuple(
            item.option_id for item in self.transport_options if item.disposition == "SELECTED"
        )
        if selected != (self.selected_transport,):
            raise ValueError("S5 GitHub transport selection changed")
        expected_fields = (
            "http_status",
            "content_type",
            "link_header",
            "etag_header",
            "x_ratelimit_limit",
            "x_ratelimit_remaining",
            "x_ratelimit_reset",
            "x_ratelimit_resource",
            "pull_number",
            "state",
            "base_ref",
            "created_at",
            "merged_at",
            "merge_commit_sha",
        )
        if self.preflight_fields_permitted != expected_fields:
            raise ValueError("S5 GitHub preflight fields changed")
        if any(
            (
                self.token_value_access_permitted,
                self.acquisition_page_count_known,
                self.acquisition_request_budget_authorized,
                self.authorizes_preflight_request_now,
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
            raise ValueError("S5 GitHub transport decision cannot grant execution authority")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"decision_evidence_hash"})
        )
        if self.decision_evidence_hash != expected:
            raise ValueError("S5 GitHub transport decision hash changed")
        return self


class S5GitHubTransportDecisionAudit(BaseModel):
    schema_version: Literal["aurex-s5-github-transport-decision-audit-v1"] = (
        "aurex-s5-github-transport-decision-audit-v1"
    )
    audit_id: Literal["s5-github-transport-decision-audit-v1"] = (
        "s5-github-transport-decision-audit-v1"
    )
    audited_at: datetime
    decision_path: Literal["data/evidence/s5_bitcoin_core_github_transport_decision_v1.json"] = (
        "data/evidence/s5_bitcoin_core_github_transport_decision_v1.json"
    )
    decision_file_sha256: str
    decision_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    source_binding_count: Literal[6] = 6
    option_count: Literal[5] = 5
    passed_gate_count: Literal[12] = 12
    failed_gate_count: Literal[0] = 0
    selected_transport: Literal["REST_LIST_CLOSED_MASTER_PULLS"] = "REST_LIST_CLOSED_MASTER_PULLS"
    preflight_request_count: Literal[1] = 1
    github_api_requests_observed: Literal[0] = 0
    github_metadata_records_parsed: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    next_authorization: Literal[
        "FREEZE_S5_GITHUB_PULL_REQUEST_METADATA_PREFLIGHT_PROTOCOL_ONLY"
    ] = S5_GITHUB_TRANSPORT_NEXT
    decision: Literal["PASS_S5_GITHUB_TRANSPORT_DECISION_AUDIT"] = (
        "PASS_S5_GITHUB_TRANSPORT_DECISION_AUDIT"
    )
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "decision_file_sha256",
        "decision_evidence_hash",
        "builder_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5GitHubTransportDecisionAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 GitHub transport audit hash changed")
        return self


def audit_s5_github_transport_decision(decision: S5GitHubTransportDecision) -> bool:
    expected = universe_evidence_hash(
        decision.model_dump(mode="json", exclude={"decision_evidence_hash"})
    )
    return decision.decision_evidence_hash == expected


def audit_s5_github_transport_decision_audit(
    audit: S5GitHubTransportDecisionAudit,
) -> bool:
    expected = universe_evidence_hash(
        audit.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return audit.audit_evidence_hash == expected
