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

S5_CENSUS_PROTOCOL_DECISION = "FREEZE_S5_BITCOIN_CORE_HISTORY_COMPLETENESS_CENSUS_PROTOCOL"
S5_CENSUS_RUN_AUTHORIZATION = "RUN_S5_BITCOIN_CORE_HISTORY_COMPLETENESS_CENSUS_ONCE"
S5_CENSUS_PASS = "PASS_S5_BITCOIN_CORE_HISTORY_COMPLETENESS_CENSUS"
S5_CENSUS_STOP = "STOP_S5_BITCOIN_CORE_HISTORY_COMPLETENESS_CENSUS_FAILED_RETIRE_S5"
S5_CENSUS_NEXT = "AUTHORIZE_S5_GITHUB_PULL_REQUEST_METADATA_TRANSPORT_DECISION_ONLY"
S5_CENSUS_NONE = "NONE_S5_BITCOIN_CORE_HISTORY_COMPLETENESS_CENSUS_FAILED_RETIRE_S5"

S5_CENSUS_GATE_IDS = (
    "S5_HISTORY_PAYLOAD_AND_READINESS_V29_LINEAGE_BOUND",
    "FINAL_DATASET_MANIFEST_AND_SOURCE_CUTOFF_BOUND",
    "ZERO_NETWORK_LOCAL_CENSUS_ONLY",
    "FIRST_PARENT_COMMIT_STREAM_COMPLETE_AND_NONEMPTY",
    "BATCH_COMMIT_OBJECT_COUNT_MATCHES_FIRST_PARENT_STREAM",
    "PARENT_TOPOLOGY_COUNTS_RECONCILE_EXACTLY",
    "PULL_REQUEST_MESSAGE_PATTERNS_FROZEN_AND_DETERMINISTIC",
    "RECOGNIZED_PULL_REQUEST_RECORDS_AND_DISTINCT_IDS_RECONCILE",
    "UNRECOGNIZED_MERGE_SAMPLE_IS_BOUNDED_AND_HASHED",
    "DIRECT_GITHUB_REQUEST_BUDGET_CALCULATED_EXACTLY",
    "AUTHOR_IDENTITIES_AND_TIMESTAMPS_NOT_PARSED_OR_PERSISTED",
    "ZERO_MARKET_VALUES_PARAMETERS_RETURNS_CANDIDATES_OR_ORDERS",
    "PASS_AUTHORIZES_METADATA_TRANSPORT_DECISION_ONLY",
)


class S5PullRequestMessagePattern(BaseModel):
    pattern_id: Literal["BITCOIN_CORE_MAINTAINER_MERGE", "GITHUB_DEFAULT_PULL_MERGE"]
    regular_expression: str = Field(min_length=1)
    applies_only_to_multi_parent_commit: Literal[True] = True
    first_match_wins: Literal[True] = True

    model_config = ConfigDict(extra="forbid", frozen=True)


class S5AcceptedPullRequestRecord(BaseModel):
    sequence: int = Field(gt=0)
    merge_commit_hash: str = Field(pattern=r"^[0-9a-f]{40}$")
    parent_count: int = Field(ge=2)
    pull_request_id: int = Field(gt=0)
    pattern_id: Literal["BITCOIN_CORE_MAINTAINER_MERGE", "GITHUB_DEFAULT_PULL_MERGE"]
    first_line_sha256: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("first_line_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)


class S5UnrecognizedMergeSample(BaseModel):
    sequence: int = Field(gt=0)
    merge_commit_hash: str = Field(pattern=r"^[0-9a-f]{40}$")
    parent_count: int = Field(ge=2)
    first_line: str = Field(max_length=300)
    first_line_sha256: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("first_line_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)


class S5CensusGateResult(BaseModel):
    gate_id: str = Field(min_length=1)
    status: Literal["PASS", "FAIL"]
    evidence: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid", frozen=True)


class S5BitcoinCoreHistoryCensusProtocol(BaseModel):
    schema_version: Literal["aurex-s5-bitcoin-core-history-census-protocol-v1"] = (
        "aurex-s5-bitcoin-core-history-census-protocol-v1"
    )
    protocol_id: Literal["s5-bitcoin-core-history-census-protocol-v1"] = (
        "s5-bitcoin-core-history-census-protocol-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_PROTOCOL_ONLY_ZERO_CENSUS_EXECUTION"] = (
        "FROZEN_PROTOCOL_ONLY_ZERO_CENSUS_EXECUTION"
    )
    builder_contract_hash: str
    history_result_evidence_hash: str
    history_result_audit_evidence_hash: str
    readiness_v29_result_evidence_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=11, max_length=11)
    dataset_path: Literal["data/evidence/s5_bitcoin_core_history_payload_v1.git"] = (
        "data/evidence/s5_bitcoin_core_history_payload_v1.git"
    )
    dataset_directory_sha256: str
    source_cutoff_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    maximum_reachable_commit_count: int = Field(gt=0)
    first_parent_command: Literal["git rev-list --first-parent --reverse <cutoff>"] = (
        "git rev-list --first-parent --reverse <cutoff>"
    )
    batch_object_command: Literal["git cat-file --batch"] = "git cat-file --batch"
    message_patterns: tuple[S5PullRequestMessagePattern, ...] = Field(min_length=2, max_length=2)
    maximum_unrecognized_merge_samples: Literal[25] = 25
    maximum_first_line_characters_persisted: Literal[300] = 300
    github_direct_pull_endpoint_template: Literal[
        "https://api.github.com/repos/bitcoin/bitcoin/pulls/{pull_number}"
    ] = "https://api.github.com/repos/bitcoin/bitcoin/pulls/{pull_number}"
    github_unauthenticated_requests_per_hour: Literal[60] = 60
    github_authenticated_requests_per_hour: Literal[5000] = 5000
    maximum_local_git_process_count: Literal[2] = 2
    maximum_run_count: Literal[1] = 1
    maximum_elapsed_seconds: Literal[600] = 600
    result_required_on_every_normal_exit: Literal[True] = True
    rerun_after_result_forbidden: Literal[True] = True
    network_access_permitted: Literal[False] = False
    repository_fetch_permitted: Literal[False] = False
    commit_hash_access_permitted: Literal[True] = True
    parent_header_access_permitted: Literal[True] = True
    commit_message_first_line_access_permitted: Literal[True] = True
    commit_message_body_persistence_permitted: Literal[False] = False
    author_header_parsing_permitted: Literal[False] = False
    committer_header_parsing_permitted: Literal[False] = False
    timestamp_parsing_permitted: Literal[False] = False
    github_api_requests_permitted: Literal[False] = False
    btc_market_values_permitted: Literal[False] = False
    parameters_permitted: Literal[False] = False
    returns_permitted: Literal[False] = False
    strategy_candidate_permitted: Literal[False] = False
    paper_permitted: Literal[False] = False
    testnet_strategy_orders_permitted: Literal[False] = False
    production_permitted: Literal[False] = False
    live_permitted: Literal[False] = False
    local_git_processes_executed: Literal[0] = 0
    commit_objects_parsed: Literal[0] = 0
    pull_request_ids_parsed: Literal[0] = 0
    github_api_requests_executed: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    required_gate_ids: tuple[str, ...] = Field(min_length=13, max_length=13)
    decision: Literal["FREEZE_S5_BITCOIN_CORE_HISTORY_COMPLETENESS_CENSUS_PROTOCOL"] = (
        S5_CENSUS_PROTOCOL_DECISION
    )
    next_authorization: Literal["RUN_S5_BITCOIN_CORE_HISTORY_COMPLETENESS_CENSUS_ONCE"] = (
        S5_CENSUS_RUN_AUTHORIZATION
    )
    limitations: tuple[str, ...] = Field(min_length=10)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "history_result_evidence_hash",
        "history_result_audit_evidence_hash",
        "readiness_v29_result_evidence_hash",
        "dataset_directory_sha256",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S5BitcoinCoreHistoryCensusProtocol:
        paths = tuple(item.path for item in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 census source bindings changed")
        if self.required_gate_ids != S5_CENSUS_GATE_IDS:
            raise ValueError("S5 census gates changed")
        pattern_ids = tuple(item.pattern_id for item in self.message_patterns)
        if pattern_ids != (
            "BITCOIN_CORE_MAINTAINER_MERGE",
            "GITHUB_DEFAULT_PULL_MERGE",
        ):
            raise ValueError("S5 census message patterns changed")
        if any(
            (
                self.network_access_permitted,
                self.repository_fetch_permitted,
                self.commit_message_body_persistence_permitted,
                self.author_header_parsing_permitted,
                self.committer_header_parsing_permitted,
                self.timestamp_parsing_permitted,
                self.github_api_requests_permitted,
                self.btc_market_values_permitted,
                self.parameters_permitted,
                self.returns_permitted,
                self.strategy_candidate_permitted,
                self.paper_permitted,
                self.testnet_strategy_orders_permitted,
                self.production_permitted,
                self.live_permitted,
            )
        ):
            raise ValueError("S5 census protocol cannot grant outcome or trading authority")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S5 census protocol hash changed")
        return self


class S5BitcoinCoreHistoryCensusProtocolAudit(BaseModel):
    schema_version: Literal["aurex-s5-bitcoin-core-history-census-protocol-audit-v1"] = (
        "aurex-s5-bitcoin-core-history-census-protocol-audit-v1"
    )
    audit_id: Literal["s5-bitcoin-core-history-census-protocol-audit-v1"] = (
        "s5-bitcoin-core-history-census-protocol-audit-v1"
    )
    audited_at: datetime
    protocol_path: Literal["data/evidence/s5_bitcoin_core_history_census_protocol_v1.json"] = (
        "data/evidence/s5_bitcoin_core_history_census_protocol_v1.json"
    )
    protocol_file_sha256: str
    protocol_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    source_binding_count: Literal[11] = 11
    gate_count: Literal[13] = 13
    message_pattern_count: Literal[2] = 2
    local_git_processes_observed: Literal[0] = 0
    commit_objects_parsed: Literal[0] = 0
    github_api_requests_observed: Literal[0] = 0
    market_values_read: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["PASS_S5_BITCOIN_CORE_HISTORY_CENSUS_PROTOCOL_AUDIT"] = (
        "PASS_S5_BITCOIN_CORE_HISTORY_CENSUS_PROTOCOL_AUDIT"
    )
    next_authorization: Literal["RUN_S5_BITCOIN_CORE_HISTORY_COMPLETENESS_CENSUS_ONCE"] = (
        S5_CENSUS_RUN_AUTHORIZATION
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
    def validate_audit(self) -> S5BitcoinCoreHistoryCensusProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 census protocol audit hash changed")
        return self


class S5BitcoinCoreHistoryCensusResult(BaseModel):
    schema_version: Literal["aurex-s5-bitcoin-core-history-census-result-v1"] = (
        "aurex-s5-bitcoin-core-history-census-result-v1"
    )
    result_id: Literal["s5-bitcoin-core-history-census-result-v1"] = (
        "s5-bitcoin-core-history-census-result-v1"
    )
    executed_at: datetime
    protocol_evidence_hash: str
    runner_contract_hash: str
    dataset_directory_sha256: str
    source_cutoff_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    local_git_process_count: int = Field(ge=0, le=2)
    first_parent_commit_count: int = Field(ge=0)
    commit_object_count: int = Field(ge=0)
    single_parent_commit_count: int = Field(ge=0)
    root_commit_count: int = Field(ge=0)
    merge_commit_count: int = Field(ge=0)
    octopus_merge_commit_count: int = Field(ge=0)
    recognized_pull_merge_count: int = Field(ge=0)
    unrecognized_merge_count: int = Field(ge=0)
    recognized_pattern_counts: dict[str, int]
    accepted_pull_request_records: tuple[S5AcceptedPullRequestRecord, ...]
    distinct_pull_request_ids: tuple[int, ...]
    distinct_pull_request_count: int = Field(ge=0)
    duplicate_pull_request_reference_count: int = Field(ge=0)
    single_parent_pattern_match_count: int = Field(ge=0)
    unrecognized_merge_samples: tuple[S5UnrecognizedMergeSample, ...] = Field(max_length=25)
    unrecognized_merge_first_line_stream_sha256: str
    first_parent_commit_stream_sha256: str
    accepted_pull_record_evidence_hash: str
    exact_direct_pull_request_count: int = Field(ge=0)
    unauthenticated_direct_request_hours_lower_bound: int = Field(ge=0)
    authenticated_direct_request_hours_lower_bound: int = Field(ge=0)
    minimum_list_endpoint_pages_at_100_records: int = Field(ge=0)
    github_token_environment_present: bool
    gate_results: tuple[S5CensusGateResult, ...] = Field(min_length=13, max_length=13)
    passed_gate_count: int = Field(ge=0, le=13)
    failed_gate_count: int = Field(ge=0, le=13)
    commit_message_bodies_received: int = Field(ge=0)
    commit_message_first_lines_parsed: int = Field(ge=0)
    commit_message_bodies_persisted: Literal[0] = 0
    author_headers_parsed: Literal[0] = 0
    committer_headers_parsed: Literal[0] = 0
    timestamps_parsed: Literal[0] = 0
    github_api_requests_executed: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    source_completeness_conclusion: Literal["NOT_YET_ADJUDICATED"] = "NOT_YET_ADJUDICATED"
    predictive_edge_conclusion: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"
    decision: Literal[
        "PASS_S5_BITCOIN_CORE_HISTORY_COMPLETENESS_CENSUS",
        "STOP_S5_BITCOIN_CORE_HISTORY_COMPLETENESS_CENSUS_FAILED_RETIRE_S5",
    ]
    next_authorization: Literal[
        "AUTHORIZE_S5_GITHUB_PULL_REQUEST_METADATA_TRANSPORT_DECISION_ONLY",
        "NONE_S5_BITCOIN_CORE_HISTORY_COMPLETENESS_CENSUS_FAILED_RETIRE_S5",
    ]
    authorizes_metadata_transport_decision: bool
    authorizes_github_api_requests: Literal[False] = False
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

    @field_validator("executed_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_evidence_hash",
        "runner_contract_hash",
        "dataset_directory_sha256",
        "unrecognized_merge_first_line_stream_sha256",
        "first_parent_commit_stream_sha256",
        "accepted_pull_record_evidence_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("recognized_pattern_counts")
    @classmethod
    def validate_pattern_counts(cls, value: dict[str, int]) -> dict[str, int]:
        expected = {
            "BITCOIN_CORE_MAINTAINER_MERGE",
            "GITHUB_DEFAULT_PULL_MERGE",
        }
        if set(value) != expected or any(count < 0 for count in value.values()):
            raise ValueError("S5 recognized pattern counts changed")
        return value

    @model_validator(mode="after")
    def validate_result(self) -> S5BitcoinCoreHistoryCensusResult:
        if self.first_parent_commit_count != self.commit_object_count:
            raise ValueError("S5 census commit stream and object counts differ")
        if self.first_parent_commit_count != (
            self.root_commit_count + self.single_parent_commit_count + self.merge_commit_count
        ):
            raise ValueError("S5 census topology counts do not reconcile")
        if self.merge_commit_count != (
            self.recognized_pull_merge_count + self.unrecognized_merge_count
        ):
            raise ValueError("S5 census merge classifications do not reconcile")
        sequences = tuple(item.sequence for item in self.accepted_pull_request_records)
        if sequences != tuple(range(1, len(sequences) + 1)):
            raise ValueError("S5 accepted pull record sequence changed")
        commit_hashes = tuple(item.merge_commit_hash for item in self.accepted_pull_request_records)
        if len(set(commit_hashes)) != len(commit_hashes):
            raise ValueError("S5 accepted pull record commits must be unique")
        expected_ids = tuple(
            sorted({item.pull_request_id for item in self.accepted_pull_request_records})
        )
        if self.distinct_pull_request_ids != expected_ids:
            raise ValueError("S5 distinct pull-request IDs changed")
        if self.distinct_pull_request_count != len(expected_ids):
            raise ValueError("S5 distinct pull-request count changed")
        if self.recognized_pull_merge_count != len(self.accepted_pull_request_records):
            raise ValueError("S5 recognized pull merge count changed")
        if self.recognized_pull_merge_count != sum(self.recognized_pattern_counts.values()):
            raise ValueError("S5 recognized pattern counts do not reconcile")
        if self.duplicate_pull_request_reference_count != (
            self.recognized_pull_merge_count - self.distinct_pull_request_count
        ):
            raise ValueError("S5 duplicate pull-request count changed")
        sample_sequences = tuple(item.sequence for item in self.unrecognized_merge_samples)
        if sample_sequences != tuple(range(1, len(sample_sequences) + 1)):
            raise ValueError("S5 unrecognized merge sample sequence changed")
        if len(self.unrecognized_merge_samples) > self.unrecognized_merge_count:
            raise ValueError("S5 unrecognized merge sample count changed")
        if self.exact_direct_pull_request_count != self.distinct_pull_request_count:
            raise ValueError("S5 exact direct request budget changed")
        expected_unauthenticated_hours = (self.distinct_pull_request_count + 60 - 1) // 60
        expected_authenticated_hours = (self.distinct_pull_request_count + 5000 - 1) // 5000
        expected_list_pages = (self.distinct_pull_request_count + 100 - 1) // 100
        if (
            self.unauthenticated_direct_request_hours_lower_bound != expected_unauthenticated_hours
            or self.authenticated_direct_request_hours_lower_bound != expected_authenticated_hours
            or self.minimum_list_endpoint_pages_at_100_records != expected_list_pages
        ):
            raise ValueError("S5 GitHub request budget changed")
        if self.commit_message_bodies_received != self.commit_object_count:
            raise ValueError("S5 received commit-message body count changed")
        if self.commit_message_first_lines_parsed != self.commit_object_count:
            raise ValueError("S5 parsed first-line count changed")
        gate_ids = tuple(item.gate_id for item in self.gate_results)
        if gate_ids != S5_CENSUS_GATE_IDS:
            raise ValueError("S5 census result gates changed")
        passed = sum(item.status == "PASS" for item in self.gate_results)
        failed = sum(item.status == "FAIL" for item in self.gate_results)
        if (self.passed_gate_count, self.failed_gate_count) != (passed, failed):
            raise ValueError("S5 census gate counts changed")
        passed_result = failed == 0
        if passed_result != (
            self.decision == S5_CENSUS_PASS
            and self.next_authorization == S5_CENSUS_NEXT
            and self.authorizes_metadata_transport_decision
        ):
            raise ValueError("S5 census decision is inconsistent")
        if not passed_result and (
            self.decision != S5_CENSUS_STOP
            or self.next_authorization != S5_CENSUS_NONE
            or self.authorizes_metadata_transport_decision
        ):
            raise ValueError("Failed S5 census cannot authorize another stage")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("S5 census result hash changed")
        return self


class S5BitcoinCoreHistoryCensusResultAudit(BaseModel):
    schema_version: Literal["aurex-s5-bitcoin-core-history-census-result-audit-v1"] = (
        "aurex-s5-bitcoin-core-history-census-result-audit-v1"
    )
    audit_id: Literal["s5-bitcoin-core-history-census-result-audit-v1"] = (
        "s5-bitcoin-core-history-census-result-audit-v1"
    )
    audited_at: datetime
    result_path: Literal["data/evidence/s5_bitcoin_core_history_census_result_v1.json"] = (
        "data/evidence/s5_bitcoin_core_history_census_result_v1.json"
    )
    result_file_sha256: str
    result_evidence_hash: str
    protocol_evidence_hash: str
    runner_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    dataset_hash_reverified: Literal[True] = True
    first_parent_stream_reverified: Literal[True] = True
    commit_object_count: int = Field(ge=0)
    recognized_pull_merge_count: int = Field(ge=0)
    distinct_pull_request_count: int = Field(ge=0)
    exact_direct_pull_request_count: int = Field(ge=0)
    passed_gate_count: int = Field(ge=0, le=13)
    failed_gate_count: int = Field(ge=0, le=13)
    github_api_requests_executed: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    next_authorization: Literal[
        "AUTHORIZE_S5_GITHUB_PULL_REQUEST_METADATA_TRANSPORT_DECISION_ONLY",
        "NONE_S5_BITCOIN_CORE_HISTORY_COMPLETENESS_CENSUS_FAILED_RETIRE_S5",
    ]
    decision: Literal["PASS_S5_BITCOIN_CORE_HISTORY_CENSUS_RESULT_AUDIT"] = (
        "PASS_S5_BITCOIN_CORE_HISTORY_CENSUS_RESULT_AUDIT"
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
    def validate_audit(self) -> S5BitcoinCoreHistoryCensusResultAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 census result audit hash changed")
        return self


def audit_s5_census_protocol(protocol: S5BitcoinCoreHistoryCensusProtocol) -> bool:
    expected = universe_evidence_hash(
        protocol.model_dump(mode="json", exclude={"protocol_evidence_hash"})
    )
    return protocol.protocol_evidence_hash == expected


def audit_s5_census_protocol_audit(
    audit: S5BitcoinCoreHistoryCensusProtocolAudit,
) -> bool:
    expected = universe_evidence_hash(
        audit.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return audit.audit_evidence_hash == expected


def audit_s5_census_result(result: S5BitcoinCoreHistoryCensusResult) -> bool:
    expected = universe_evidence_hash(
        result.model_dump(mode="json", exclude={"result_evidence_hash"})
    )
    return result.result_evidence_hash == expected


def audit_s5_census_result_audit(
    audit: S5BitcoinCoreHistoryCensusResultAudit,
) -> bool:
    expected = universe_evidence_hash(
        audit.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return audit.audit_evidence_hash == expected
