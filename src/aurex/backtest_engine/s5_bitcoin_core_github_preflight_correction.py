from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s5_bitcoin_core_github_preflight import (
    S5_GITHUB_PREFLIGHT_GATE_IDS,
    S5_GITHUB_PREFLIGHT_NEXT,
    S5GitHubPreflightGateResult,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import S5HistoryBinding
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S5_GITHUB_PREFLIGHT_FAILURE_ADJUDICATION = (
    "TRANSPORT_SUCCEEDED_INTERPRETER_REJECTED_CANONICAL_LINK_AND_ACTUAL_LIST_SCHEMA"
)
S5_GITHUB_PREFLIGHT_FAILURE_NEXT = "FREEZE_S5_GITHUB_PREFLIGHT_LOCAL_INTERPRETER_AMENDMENT_V2_ONLY"
S5_GITHUB_PREFLIGHT_AMENDMENT_DECISION = (
    "AMEND_LINK_AND_LIST_IDENTITY_INTERPRETATION_WITH_ZERO_ADDITIONAL_REQUESTS"
)
S5_GITHUB_PREFLIGHT_AMENDMENT_NEXT = "RUN_S5_GITHUB_PREFLIGHT_LOCAL_REVALIDATION_V2_ONCE"
S5_GITHUB_PREFLIGHT_CORRECTED_PASS = "PASS_S5_GITHUB_METADATA_PREFLIGHT_LOCAL_CORRECTION"


class S5GitHubPreflightFailureAudit(BaseModel):
    schema_version: Literal["aurex-s5-github-preflight-failure-audit-v1"] = (
        "aurex-s5-github-preflight-failure-audit-v1"
    )
    audit_id: Literal["s5-github-preflight-failure-audit-v1"] = (
        "s5-github-preflight-failure-audit-v1"
    )
    audited_at: datetime
    auditor_contract_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=7, max_length=7)
    protocol_evidence_hash: str
    prior_result_evidence_hash: str
    prior_result_audit_evidence_hash: str
    transcript_file_sha256: str
    repository_metadata_file_sha256: str
    request_attempt_count: Literal[1] = 1
    additional_request_count: Literal[0] = 0
    http_status: Literal[200] = 200
    final_url_matched_request: Literal[True] = True
    response_byte_count: Literal[15733] = 15_733
    response_body_sha256: str
    rate_limit: Literal[60] = 60
    rate_remaining: Literal[59] = 59
    canonical_repository_id: Literal[1181927] = 1_181_927
    canonical_repository_full_name: Literal["bitcoin/bitcoin"] = "bitcoin/bitcoin"
    observed_link_path: Literal["/repositories/1181927/pulls"] = "/repositories/1181927/pulls"
    frozen_link_path: Literal["/repos/bitcoin/bitcoin/pulls"] = "/repos/bitcoin/bitcoin/pulls"
    observed_link_path_is_canonical_repository_identity: Literal[True] = True
    first_record_number: Literal[9] = 9
    first_record_state: Literal["closed"] = "closed"
    first_record_base_ref: Literal["master"] = "master"
    merge_commit_sha_key_present: Literal[False] = False
    head_sha_key_present: Literal[True] = True
    head_sha_value_persisted: Literal[False] = False
    transport_succeeded: Literal[True] = True
    interpreter_rejected_source_compatible_response: Literal[True] = True
    original_stop_preserved: Literal[True] = True
    request_replay_permitted: Literal[False] = False
    local_revalidation_feasible: Literal[True] = True
    github_metadata_records_newly_acquired: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    adjudication: Literal[
        "TRANSPORT_SUCCEEDED_INTERPRETER_REJECTED_CANONICAL_LINK_AND_ACTUAL_LIST_SCHEMA"
    ] = S5_GITHUB_PREFLIGHT_FAILURE_ADJUDICATION
    next_authorization: Literal[
        "FREEZE_S5_GITHUB_PREFLIGHT_LOCAL_INTERPRETER_AMENDMENT_V2_ONLY"
    ] = S5_GITHUB_PREFLIGHT_FAILURE_NEXT
    limitations: tuple[str, ...] = Field(min_length=8)
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "auditor_contract_hash",
        "protocol_evidence_hash",
        "prior_result_evidence_hash",
        "prior_result_audit_evidence_hash",
        "transcript_file_sha256",
        "repository_metadata_file_sha256",
        "response_body_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5GitHubPreflightFailureAudit:
        paths = tuple(item.path for item in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 GitHub preflight failure bindings changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 GitHub preflight failure audit hash changed")
        return self


class S5GitHubPreflightInterpreterAmendmentV2(BaseModel):
    schema_version: Literal["aurex-s5-github-preflight-interpreter-amendment-v2"] = (
        "aurex-s5-github-preflight-interpreter-amendment-v2"
    )
    amendment_id: Literal["s5-github-preflight-interpreter-amendment-v2"] = (
        "s5-github-preflight-interpreter-amendment-v2"
    )
    frozen_at: datetime
    status: Literal["FROZEN_LOCAL_INTERPRETER_AMENDMENT_ZERO_NETWORK"] = (
        "FROZEN_LOCAL_INTERPRETER_AMENDMENT_ZERO_NETWORK"
    )
    builder_contract_hash: str
    failure_audit_evidence_hash: str
    prior_result_evidence_hash: str
    prior_result_audit_evidence_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=3, max_length=3)
    permitted_link_paths: tuple[
        Literal["/repos/bitcoin/bitcoin/pulls", "/repositories/1181927/pulls"], ...
    ] = Field(min_length=2, max_length=2)
    canonical_repository_id: Literal[1181927] = 1_181_927
    prior_required_identity_field: Literal["merge_commit_sha"] = "merge_commit_sha"
    corrected_required_identity_field: Literal["head.sha"] = "head.sha"
    identity_consistency_rule: Literal[
        "MATCH_API_HEAD_SHA_TO_ACCEPTED_MERGE_SECOND_PARENT_SHA_OR_FAIL_AMBIGUOUS"
    ] = "MATCH_API_HEAD_SHA_TO_ACCEPTED_MERGE_SECOND_PARENT_SHA_OR_FAIL_AMBIGUOUS"
    merged_at_null_for_unmerged_record_permitted: Literal[True] = True
    merge_commit_sha_absence_in_list_record_permitted: Literal[True] = True
    request_url_unchanged: Literal[True] = True
    request_headers_unchanged: Literal[True] = True
    response_body_unchanged: Literal[True] = True
    protocol_gate_ids_unchanged: Literal[True] = True
    maximum_local_revalidation_count: Literal[1] = 1
    additional_network_requests_permitted: Literal[0] = 0
    credential_access_permitted: Literal[False] = False
    market_values_permitted: Literal[False] = False
    parameters_permitted: Literal[False] = False
    returns_permitted: Literal[False] = False
    candidates_permitted: Literal[False] = False
    orders_permitted: Literal[False] = False
    decision: Literal[
        "AMEND_LINK_AND_LIST_IDENTITY_INTERPRETATION_WITH_ZERO_ADDITIONAL_REQUESTS"
    ] = S5_GITHUB_PREFLIGHT_AMENDMENT_DECISION
    next_authorization: Literal["RUN_S5_GITHUB_PREFLIGHT_LOCAL_REVALIDATION_V2_ONCE"] = (
        S5_GITHUB_PREFLIGHT_AMENDMENT_NEXT
    )
    limitations: tuple[str, ...] = Field(min_length=8)
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
        "prior_result_audit_evidence_hash",
        "amendment_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_amendment(self) -> S5GitHubPreflightInterpreterAmendmentV2:
        paths = tuple(item.path for item in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 GitHub preflight amendment bindings changed")
        if self.permitted_link_paths != (
            "/repos/bitcoin/bitcoin/pulls",
            "/repositories/1181927/pulls",
        ):
            raise ValueError("S5 GitHub preflight corrected link paths changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"amendment_evidence_hash"})
        )
        if self.amendment_evidence_hash != expected:
            raise ValueError("S5 GitHub preflight amendment hash changed")
        return self


class S5GitHubPreflightInterpreterAmendmentAuditV2(BaseModel):
    schema_version: Literal["aurex-s5-github-preflight-interpreter-amendment-audit-v2"] = (
        "aurex-s5-github-preflight-interpreter-amendment-audit-v2"
    )
    audit_id: Literal["s5-github-preflight-interpreter-amendment-audit-v2"] = (
        "s5-github-preflight-interpreter-amendment-audit-v2"
    )
    audited_at: datetime
    amendment_path: Literal[
        "data/evidence/s5_bitcoin_core_github_preflight_interpreter_amendment_v2.json"
    ] = "data/evidence/s5_bitcoin_core_github_preflight_interpreter_amendment_v2.json"
    amendment_file_sha256: str
    amendment_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    failure_audit_evidence_hash: str
    additional_network_requests_observed: Literal[0] = 0
    metadata_records_newly_acquired: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    next_authorization: Literal["RUN_S5_GITHUB_PREFLIGHT_LOCAL_REVALIDATION_V2_ONCE"] = (
        S5_GITHUB_PREFLIGHT_AMENDMENT_NEXT
    )
    decision: Literal["PASS_S5_GITHUB_PREFLIGHT_INTERPRETER_AMENDMENT_AUDIT_V2"] = (
        "PASS_S5_GITHUB_PREFLIGHT_INTERPRETER_AMENDMENT_AUDIT_V2"
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
        "builder_contract_hash",
        "auditor_contract_hash",
        "failure_audit_evidence_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5GitHubPreflightInterpreterAmendmentAuditV2:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 GitHub preflight amendment audit hash changed")
        return self


class S5GitHubPreflightCorrectedResultV2(BaseModel):
    schema_version: Literal["aurex-s5-github-preflight-corrected-result-v2"] = (
        "aurex-s5-github-preflight-corrected-result-v2"
    )
    result_id: Literal["s5-github-preflight-corrected-result-v2"] = (
        "s5-github-preflight-corrected-result-v2"
    )
    corrected_at: datetime
    runner_contract_hash: str
    protocol_evidence_hash: str
    prior_result_evidence_hash: str
    prior_result_audit_evidence_hash: str
    failure_audit_evidence_hash: str
    amendment_evidence_hash: str
    amendment_audit_evidence_hash: str
    transcript_file_sha256: str
    local_revalidation_count: Literal[1] = 1
    original_request_attempt_count: Literal[1] = 1
    additional_network_request_count: Literal[0] = 0
    http_status: Literal[200] = 200
    final_url_matched_request: Literal[True] = True
    redirect_count: Literal[0] = 0
    response_byte_count: Literal[15733] = 15_733
    response_body_sha256: str
    content_type: str
    rate_limit: Literal[60] = 60
    rate_remaining: Literal[59] = 59
    rate_resource: Literal["core"] = "core"
    canonical_repository_id: Literal[1181927] = 1_181_927
    accepted_link_path: Literal["/repositories/1181927/pulls"] = "/repositories/1181927/pulls"
    parsed_pull_record_count: Literal[1] = 1
    first_pull_number: Literal[9] = 9
    first_pull_state: Literal["closed"] = "closed"
    first_pull_base_ref: Literal["master"] = "master"
    first_pull_base_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    first_pull_head_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    first_pull_created_at: datetime
    first_pull_merged_at: datetime | None = None
    merge_commit_sha_key_present: Literal[False] = False
    terminal_record_count: Literal[24012] = 24_012
    bulk_request_page_count_at_100: Literal[241] = 241
    bulk_unauthenticated_hours_lower_bound: Literal[5] = 5
    gate_results: tuple[S5GitHubPreflightGateResult, ...] = Field(min_length=14, max_length=14)
    passed_gate_count: Literal[14] = 14
    failed_gate_count: Literal[0] = 0
    github_api_requests_executed: Literal[1] = 1
    additional_github_api_requests_executed: Literal[0] = 0
    github_metadata_records_parsed: Literal[1] = 1
    btc_market_values_read: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    source_completeness_conclusion: Literal["NOT_YET_ADJUDICATED"] = "NOT_YET_ADJUDICATED"
    predictive_edge_conclusion: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"
    decision: Literal["PASS_S5_GITHUB_METADATA_PREFLIGHT_LOCAL_CORRECTION"] = (
        S5_GITHUB_PREFLIGHT_CORRECTED_PASS
    )
    next_authorization: Literal["FREEZE_S5_GITHUB_METADATA_BULK_ACQUISITION_PROTOCOL_ONLY"] = (
        S5_GITHUB_PREFLIGHT_NEXT
    )
    authorizes_bulk_acquisition_protocol_design: Literal[True] = True
    authorizes_bulk_metadata_acquisition_now: Literal[False] = False
    authorizes_market_values: Literal[False] = False
    authorizes_parameters: Literal[False] = False
    authorizes_returns: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    real_net_profit_usd: Literal["0"] = "0"
    limitations: tuple[str, ...] = Field(min_length=10)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("corrected_at", "first_pull_created_at", "first_pull_merged_at")
    @classmethod
    def normalize_times(cls, value: datetime | None) -> datetime | None:
        return None if value is None else normalize_timestamp(value)

    @field_validator(
        "runner_contract_hash",
        "protocol_evidence_hash",
        "prior_result_evidence_hash",
        "prior_result_audit_evidence_hash",
        "failure_audit_evidence_hash",
        "amendment_evidence_hash",
        "amendment_audit_evidence_hash",
        "transcript_file_sha256",
        "response_body_sha256",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> S5GitHubPreflightCorrectedResultV2:
        if tuple(item.gate_id for item in self.gate_results) != S5_GITHUB_PREFLIGHT_GATE_IDS:
            raise ValueError("S5 corrected preflight gates changed")
        if any(item.status != "PASS" for item in self.gate_results):
            raise ValueError("S5 corrected preflight contains a failed gate")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("S5 corrected preflight result hash changed")
        return self


class S5GitHubPreflightCorrectedResultAuditV2(BaseModel):
    schema_version: Literal["aurex-s5-github-preflight-corrected-result-audit-v2"] = (
        "aurex-s5-github-preflight-corrected-result-audit-v2"
    )
    audit_id: Literal["s5-github-preflight-corrected-result-audit-v2"] = (
        "s5-github-preflight-corrected-result-audit-v2"
    )
    audited_at: datetime
    result_path: Literal[
        "data/evidence/s5_bitcoin_core_github_preflight_corrected_result_v2.json"
    ] = "data/evidence/s5_bitcoin_core_github_preflight_corrected_result_v2.json"
    result_file_sha256: str
    result_evidence_hash: str
    runner_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    transcript_hash_reverified: Literal[True] = True
    response_body_hash_reverified: Literal[True] = True
    original_request_attempt_count: Literal[1] = 1
    additional_network_request_count: Literal[0] = 0
    terminal_record_count: Literal[24012] = 24_012
    bulk_request_page_count_at_100: Literal[241] = 241
    passed_gate_count: Literal[14] = 14
    failed_gate_count: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    next_authorization: Literal["FREEZE_S5_GITHUB_METADATA_BULK_ACQUISITION_PROTOCOL_ONLY"] = (
        S5_GITHUB_PREFLIGHT_NEXT
    )
    decision: Literal["PASS_S5_GITHUB_PREFLIGHT_CORRECTED_RESULT_AUDIT_V2"] = (
        "PASS_S5_GITHUB_PREFLIGHT_CORRECTED_RESULT_AUDIT_V2"
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
        "runner_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5GitHubPreflightCorrectedResultAuditV2:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 corrected preflight result audit hash changed")
        return self


def evidence_hash_valid(model: BaseModel, field: str) -> bool:
    expected = universe_evidence_hash(model.model_dump(mode="json", exclude={field}))
    return getattr(model, field) == expected
