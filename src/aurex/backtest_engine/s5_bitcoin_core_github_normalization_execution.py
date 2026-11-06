from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s5_bitcoin_core_github_normalization import (
    S5_GITHUB_NORMALIZATION_GATE_IDS,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S5_GITHUB_NORMALIZATION_RUN = "RUN_S5_GITHUB_NORMALIZATION_AND_COMPLETENESS_ONCE"
S5_GITHUB_NORMALIZATION_PASS = (
    "PASS_S5_GITHUB_NORMALIZATION_AND_MEASURABLE_COMPLETENESS"
)
S5_GITHUB_NORMALIZATION_STOP = "STOP_S5_GITHUB_NORMALIZATION_OR_COMPLETENESS_FAILED"
S5_GITHUB_NORMALIZATION_RESULT_NEXT = (
    "AUTHORIZE_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_PROTOCOL_ONLY"
)
S5_GITHUB_NORMALIZATION_FAILURE_NEXT = (
    "FREEZE_S5_GITHUB_NORMALIZATION_FAILURE_ADJUDICATION_ONLY"
)


class S5GitHubNormalizedPull(BaseModel):
    sequence: int = Field(gt=0)
    pull_number: int = Field(gt=0)
    node_id: str = Field(min_length=1)
    state: Literal["open", "closed"]
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    merged_at: datetime | None
    head_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    base_ref: Literal["master"] = "master"
    base_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    actor_id: int | None = Field(default=None, gt=0)
    actor_login: str | None = Field(default=None, min_length=1)
    actor_type: str | None = Field(default=None, min_length=1)
    actor_identity_status: Literal["KNOWN_ACCOUNT", "UNKNOWN_DELETED_OR_NULL"]
    actor_class: Literal["HUMAN_OR_UNRESOLVED_ACCOUNT", "BOT", "UNKNOWN"]
    source_page: int = Field(ge=1, le=245)
    source_page_sha256: str
    source_response_body_sha256: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("created_at", "updated_at", "closed_at", "merged_at")
    @classmethod
    def normalize_times(cls, value: datetime | None) -> datetime | None:
        return None if value is None else normalize_timestamp(value)

    @field_validator("source_page_sha256", "source_response_body_sha256")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_row(self) -> S5GitHubNormalizedPull:
        if self.updated_at < self.created_at:
            raise ValueError("S5 pull update precedes creation")
        if self.closed_at is not None and self.closed_at < self.created_at:
            raise ValueError("S5 pull close precedes creation")
        if self.merged_at is not None and (
            self.merged_at < self.created_at or self.state != "closed"
        ):
            raise ValueError("S5 pull merge time or state is invalid")
        actor_fields = (self.actor_id, self.actor_login, self.actor_type)
        known = all(value is not None for value in actor_fields)
        if any(value is not None for value in actor_fields) != known:
            raise ValueError("S5 partial actor identity is forbidden")
        if known != (self.actor_identity_status == "KNOWN_ACCOUNT"):
            raise ValueError("S5 actor identity status changed")
        if not known and self.actor_class != "UNKNOWN":
            raise ValueError("S5 unknown actor class changed")
        if known:
            assert self.actor_login is not None and self.actor_type is not None
            bot = self.actor_type == "Bot" or self.actor_login.casefold().endswith("[bot]")
            expected_class = "BOT" if bot else "HUMAN_OR_UNRESOLVED_ACCOUNT"
            if self.actor_class != expected_class:
                raise ValueError("S5 actor bot classification changed")
        return self


class S5GitMergeMappingRow(BaseModel):
    sequence: int = Field(gt=0)
    merge_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    first_parent_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    second_parent_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    census_pull_number: int | None = Field(default=None, gt=0)
    census_pattern_id: Literal[
        "BITCOIN_CORE_MAINTAINER_MERGE",
        "GITHUB_DEFAULT_PULL_MERGE",
    ] | None = None
    mapping_status: Literal[
        "RECOGNIZED_NUMBER_AND_HEAD_SHA_EXACT",
        "UNRECOGNIZED_MESSAGE_HEAD_SHA_EXACT",
    ]
    pull_number: int = Field(gt=0)
    merged_at: datetime
    actor_id: int | None = Field(default=None, gt=0)
    actor_login: str | None = Field(default=None, min_length=1)
    actor_type: str | None = Field(default=None, min_length=1)
    actor_identity_status: Literal["KNOWN_ACCOUNT", "UNKNOWN_DELETED_OR_NULL"]
    actor_class: Literal["HUMAN_OR_UNRESOLVED_ACCOUNT", "BOT", "UNKNOWN"]

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("merged_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_mapping(self) -> S5GitMergeMappingRow:
        census_fields = (self.census_pull_number, self.census_pattern_id)
        if any(value is not None for value in census_fields) != all(
            value is not None for value in census_fields
        ):
            raise ValueError("S5 partial census identity is forbidden")
        recognized = self.mapping_status == "RECOGNIZED_NUMBER_AND_HEAD_SHA_EXACT"
        if recognized != (self.census_pull_number is not None):
            raise ValueError("S5 recognized mapping status changed")
        if recognized and self.census_pull_number != self.pull_number:
            raise ValueError("S5 census and GitHub pull numbers differ")
        known = self.actor_identity_status == "KNOWN_ACCOUNT"
        if known != all(
            value is not None
            for value in (self.actor_id, self.actor_login, self.actor_type)
        ):
            raise ValueError("S5 mapped actor identity changed")
        if not known and self.actor_class != "UNKNOWN":
            raise ValueError("S5 mapped unknown actor class changed")
        return self


class S5UnresolvedGitMergeRow(BaseModel):
    sequence: int = Field(gt=0)
    merge_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    first_parent_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    second_parent_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    census_pull_number: int | None = Field(default=None, gt=0)
    census_pattern_id: Literal[
        "BITCOIN_CORE_MAINTAINER_MERGE",
        "GITHUB_DEFAULT_PULL_MERGE",
    ] | None = None
    resolution_status: Literal[
        "NO_ACCEPTED_GITHUB_HEAD_MATCH",
        "MULTIPLE_ACCEPTED_GITHUB_HEAD_MATCHES",
        "RECOGNIZED_PULL_MISSING_OR_NOT_ACCEPTED",
        "RECOGNIZED_PULL_HEAD_SHA_MISMATCH",
    ]
    candidate_pull_numbers: tuple[int, ...] = Field(max_length=25)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_row(self) -> S5UnresolvedGitMergeRow:
        if self.candidate_pull_numbers != tuple(sorted(set(self.candidate_pull_numbers))):
            raise ValueError("S5 unresolved candidate pull numbers changed")
        census_fields = (self.census_pull_number, self.census_pattern_id)
        if any(value is not None for value in census_fields) != all(
            value is not None for value in census_fields
        ):
            raise ValueError("S5 unresolved census identity changed")
        return self


class S5GitHubNormalizationGateResult(BaseModel):
    gate_id: str = Field(min_length=1)
    status: Literal["PASS", "FAIL"]
    evidence: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid", frozen=True)


class S5GitHubNormalizationExecutionContract(BaseModel):
    schema_version: Literal["aurex-s5-github-normalization-execution-contract-v1"] = (
        "aurex-s5-github-normalization-execution-contract-v1"
    )
    contract_id: Literal["s5-github-normalization-execution-contract-v1"] = (
        "s5-github-normalization-execution-contract-v1"
    )
    frozen_at: datetime
    builder_contract_hash: str
    protocol_path: Literal[
        "data/evidence/s5_bitcoin_core_github_normalization_protocol_v1.json"
    ] = "data/evidence/s5_bitcoin_core_github_normalization_protocol_v1.json"
    protocol_file_sha256: str
    protocol_evidence_hash: str
    protocol_audit_path: Literal[
        "data/evidence/s5_bitcoin_core_github_normalization_protocol_audit_v1.json"
    ] = "data/evidence/s5_bitcoin_core_github_normalization_protocol_audit_v1.json"
    protocol_audit_file_sha256: str
    protocol_audit_evidence_hash: str
    runner_contract_hash: str
    synthetic_test_ids: tuple[str, ...] = Field(min_length=10)
    output_paths_absent_at_freeze: Literal[True] = True
    authorizes_single_local_normalization_run: Literal[True] = True
    authorizes_raw_github_metadata_access: Literal[True] = True
    authorizes_git_parent_topology_access: Literal[True] = True
    authorizes_network_access: Literal[False] = False
    authorizes_repository_fetch: Literal[False] = False
    authorizes_commit_messages: Literal[False] = False
    authorizes_git_identity_or_timestamp_headers: Literal[False] = False
    authorizes_btc_market_values: Literal[False] = False
    authorizes_parameters: Literal[False] = False
    authorizes_returns: Literal[False] = False
    authorizes_candidates: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    next_authorization: Literal[
        "RUN_S5_GITHUB_NORMALIZATION_AND_COMPLETENESS_ONCE"
    ] = S5_GITHUB_NORMALIZATION_RUN
    contract_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "protocol_audit_file_sha256",
        "protocol_audit_evidence_hash",
        "runner_contract_hash",
        "contract_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_contract(self) -> S5GitHubNormalizationExecutionContract:
        forbidden = (
            self.authorizes_network_access,
            self.authorizes_repository_fetch,
            self.authorizes_commit_messages,
            self.authorizes_git_identity_or_timestamp_headers,
            self.authorizes_btc_market_values,
            self.authorizes_parameters,
            self.authorizes_returns,
            self.authorizes_candidates,
            self.authorizes_paper,
            self.authorizes_testnet_strategy_orders,
            self.authorizes_production,
            self.authorizes_live,
        )
        if any(forbidden):
            raise ValueError("S5 normalization execution grants forbidden authority")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"contract_evidence_hash"})
        )
        if self.contract_evidence_hash != expected:
            raise ValueError("S5 normalization execution contract hash changed")
        return self


class S5GitHubNormalizationExecutionContractAudit(BaseModel):
    schema_version: Literal[
        "aurex-s5-github-normalization-execution-contract-audit-v1"
    ] = "aurex-s5-github-normalization-execution-contract-audit-v1"
    audit_id: Literal["s5-github-normalization-execution-contract-audit-v1"] = (
        "s5-github-normalization-execution-contract-audit-v1"
    )
    audited_at: datetime
    contract_path: Literal[
        "data/evidence/s5_bitcoin_core_github_normalization_execution_contract_v1.json"
    ] = "data/evidence/s5_bitcoin_core_github_normalization_execution_contract_v1.json"
    contract_file_sha256: str
    contract_evidence_hash: str
    protocol_evidence_hash: str
    protocol_audit_evidence_hash: str
    runner_contract_hash: str
    auditor_source_sha256: str
    source_page_files_opened: Literal[0] = 0
    response_bodies_decoded: Literal[0] = 0
    local_git_processes_executed: Literal[0] = 0
    reconstructed_exactly: Literal[True] = True
    decision: Literal["PASS_S5_GITHUB_NORMALIZATION_EXECUTION_CONTRACT_AUDIT"] = (
        "PASS_S5_GITHUB_NORMALIZATION_EXECUTION_CONTRACT_AUDIT"
    )
    next_authorization: Literal[
        "RUN_S5_GITHUB_NORMALIZATION_AND_COMPLETENESS_ONCE"
    ] = S5_GITHUB_NORMALIZATION_RUN
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "contract_file_sha256",
        "contract_evidence_hash",
        "protocol_evidence_hash",
        "protocol_audit_evidence_hash",
        "runner_contract_hash",
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5GitHubNormalizationExecutionContractAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 normalization execution audit hash changed")
        return self


class S5GitHubNormalizationResult(BaseModel):
    schema_version: Literal["aurex-s5-github-normalization-result-v1"] = (
        "aurex-s5-github-normalization-result-v1"
    )
    result_id: Literal["s5-github-normalization-result-v1"] = (
        "s5-github-normalization-result-v1"
    )
    completed_at: datetime
    protocol_evidence_hash: str
    protocol_audit_evidence_hash: str
    execution_contract_file_sha256: str
    execution_contract_evidence_hash: str
    execution_contract_audit_evidence_hash: str
    runner_contract_hash: str
    history_dataset_directory_sha256: str
    source_cutoff_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    bulk_page_manifest_evidence_hash: str
    source_page_files_opened: int = Field(ge=0, le=245)
    response_bodies_decoded: int = Field(ge=0, le=245)
    local_git_process_count: int = Field(ge=0, le=1)
    raw_record_count: int = Field(ge=0, le=24_407)
    cohort_record_count: int = Field(ge=0, le=24_398)
    post_cutoff_record_count: int = Field(ge=0, le=9)
    normalized_pull_count: int = Field(ge=0, le=24_398)
    accepted_github_pull_count: int = Field(ge=0, le=24_398)
    first_parent_commit_count: int = Field(ge=0, le=17_543)
    root_commit_count: int = Field(ge=0, le=1)
    single_parent_commit_count: int = Field(ge=0, le=821)
    merge_commit_count: int = Field(ge=0, le=16_721)
    octopus_merge_commit_count: int = Field(ge=0)
    recognized_pull_merge_count: int = Field(ge=0, le=7_961)
    recognized_exact_mapping_count: int = Field(ge=0, le=7_961)
    recovered_head_sha_mapping_count: int = Field(ge=0, le=16_721)
    total_exact_mapping_count: int = Field(ge=0, le=16_721)
    unresolved_git_merge_count: int = Field(ge=0, le=16_721)
    unmatched_accepted_github_pull_count: int = Field(ge=0, le=24_398)
    ambiguous_git_merge_count: int = Field(ge=0, le=16_721)
    duplicate_mapped_pull_count: int = Field(ge=0, le=16_721)
    accepted_unknown_actor_count: int = Field(ge=0, le=24_398)
    accepted_bot_actor_count: int = Field(ge=0, le=24_398)
    distinct_known_accepted_actor_id_count: int = Field(ge=0, le=24_398)
    pull_dataset_path: Literal[
        "data/evidence/datasets/s5_bitcoin_core_github_pulls_normalized_v1.jsonl"
    ] | None
    pull_dataset_file_sha256: str | None
    pull_dataset_bytes: int = Field(ge=0)
    pull_dataset_row_manifest_evidence_hash: str | None
    mapping_dataset_path: Literal[
        "data/evidence/datasets/s5_bitcoin_core_accepted_merge_mapping_v1.jsonl"
    ] | None
    mapping_dataset_file_sha256: str | None
    mapping_dataset_bytes: int = Field(ge=0)
    mapping_dataset_row_manifest_evidence_hash: str | None
    unresolved_dataset_path: Literal[
        "data/evidence/datasets/s5_bitcoin_core_unresolved_git_merges_v1.jsonl"
    ] | None
    unresolved_dataset_file_sha256: str | None
    unresolved_dataset_bytes: int = Field(ge=0)
    unresolved_dataset_row_manifest_evidence_hash: str | None
    diagnostics: tuple[str, ...] = Field(max_length=25)
    gate_results: tuple[S5GitHubNormalizationGateResult, ...] = Field(
        min_length=17, max_length=17
    )
    passed_gate_count: int = Field(ge=0, le=17)
    failed_gate_count: int = Field(ge=0, le=17)
    btc_market_values_read: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    source_completeness_conclusion: Literal[
        "PASS_MEASURABLE_COMPLETENESS_WITH_EXPLICIT_LIMITATIONS",
        "FAIL_MEASURABLE_COMPLETENESS",
    ]
    predictive_edge_conclusion: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"
    decision: Literal[
        "PASS_S5_GITHUB_NORMALIZATION_AND_MEASURABLE_COMPLETENESS",
        "STOP_S5_GITHUB_NORMALIZATION_OR_COMPLETENESS_FAILED",
    ]
    next_authorization: Literal[
        "AUTHORIZE_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_PROTOCOL_ONLY",
        "FREEZE_S5_GITHUB_NORMALIZATION_FAILURE_ADJUDICATION_ONLY",
    ]
    authorizes_measurement_protocol_design: bool
    authorizes_market_values: Literal[False] = False
    authorizes_parameters: Literal[False] = False
    authorizes_returns: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    real_net_profit_usd: Literal["0"] = "0"
    failure_type: str | None
    failure_message: str | None
    limitations: tuple[str, ...] = Field(min_length=12)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("completed_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_evidence_hash",
        "protocol_audit_evidence_hash",
        "execution_contract_file_sha256",
        "execution_contract_evidence_hash",
        "execution_contract_audit_evidence_hash",
        "runner_contract_hash",
        "history_dataset_directory_sha256",
        "bulk_page_manifest_evidence_hash",
        "pull_dataset_file_sha256",
        "pull_dataset_row_manifest_evidence_hash",
        "mapping_dataset_file_sha256",
        "mapping_dataset_row_manifest_evidence_hash",
        "unresolved_dataset_file_sha256",
        "unresolved_dataset_row_manifest_evidence_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_optional_hashes(cls, value: str | None) -> str | None:
        return None if value is None else normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> S5GitHubNormalizationResult:
        gate_ids = tuple(item.gate_id for item in self.gate_results)
        if gate_ids != S5_GITHUB_NORMALIZATION_GATE_IDS:
            raise ValueError("S5 normalization result gates changed")
        passed = sum(item.status == "PASS" for item in self.gate_results)
        failed = sum(item.status == "FAIL" for item in self.gate_results)
        if (self.passed_gate_count, self.failed_gate_count) != (passed, failed):
            raise ValueError("S5 normalization gate accounting changed")
        if self.total_exact_mapping_count != (
            self.recognized_exact_mapping_count
            + self.recovered_head_sha_mapping_count
        ):
            raise ValueError("S5 exact mapping accounting changed")
        classified_merge_count = (
            self.total_exact_mapping_count + self.unresolved_git_merge_count
        )
        if classified_merge_count and self.merge_commit_count != classified_merge_count:
            raise ValueError("S5 Git merge accounting changed")
        passing = failed == 0
        output_hashes = (
            self.pull_dataset_file_sha256,
            self.pull_dataset_row_manifest_evidence_hash,
            self.mapping_dataset_file_sha256,
            self.mapping_dataset_row_manifest_evidence_hash,
            self.unresolved_dataset_file_sha256,
            self.unresolved_dataset_row_manifest_evidence_hash,
        )
        output_paths = (
            self.pull_dataset_path,
            self.mapping_dataset_path,
            self.unresolved_dataset_path,
        )
        if passing:
            exact_counts = (
                self.source_page_files_opened == 245
                and self.response_bodies_decoded == 245
                and self.local_git_process_count == 1
                and self.raw_record_count == 24_407
                and self.cohort_record_count == 24_398
                and self.post_cutoff_record_count == 9
                and self.normalized_pull_count == 24_398
                and self.first_parent_commit_count == 17_543
                and self.root_commit_count == 1
                and self.single_parent_commit_count == 821
                and self.merge_commit_count == 16_721
                and self.octopus_merge_commit_count == 0
                and self.recognized_pull_merge_count == 7_961
                and self.recognized_exact_mapping_count == 7_961
                and self.accepted_github_pull_count == self.total_exact_mapping_count
                and self.unmatched_accepted_github_pull_count == 0
                and self.ambiguous_git_merge_count == 0
                and self.duplicate_mapped_pull_count == 0
            )
            if not exact_counts or any(value is None for value in output_hashes + output_paths):
                raise ValueError("Passing S5 normalization result is incomplete")
            if (
                self.decision != S5_GITHUB_NORMALIZATION_PASS
                or self.next_authorization != S5_GITHUB_NORMALIZATION_RESULT_NEXT
                or not self.authorizes_measurement_protocol_design
                or self.source_completeness_conclusion
                != "PASS_MEASURABLE_COMPLETENESS_WITH_EXPLICIT_LIMITATIONS"
                or self.failure_type is not None
                or self.failure_message is not None
            ):
                raise ValueError("Passing S5 normalization decision changed")
        elif (
            self.decision != S5_GITHUB_NORMALIZATION_STOP
            or self.next_authorization != S5_GITHUB_NORMALIZATION_FAILURE_NEXT
            or self.authorizes_measurement_protocol_design
            or self.source_completeness_conclusion != "FAIL_MEASURABLE_COMPLETENESS"
            or not self.failure_type
            or not self.failure_message
        ):
            raise ValueError("Failed S5 normalization decision changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("S5 normalization result hash changed")
        return self


class S5GitHubNormalizationResultAudit(BaseModel):
    schema_version: Literal["aurex-s5-github-normalization-result-audit-v1"] = (
        "aurex-s5-github-normalization-result-audit-v1"
    )
    audit_id: Literal["s5-github-normalization-result-audit-v1"] = (
        "s5-github-normalization-result-audit-v1"
    )
    audited_at: datetime
    result_path: Literal[
        "data/evidence/s5_bitcoin_core_github_normalization_result_v1.json"
    ] = "data/evidence/s5_bitcoin_core_github_normalization_result_v1.json"
    result_file_sha256: str
    result_evidence_hash: str
    protocol_evidence_hash: str
    execution_contract_evidence_hash: str
    runner_contract_hash: str
    auditor_contract_hash: str
    all_source_pages_rehashed: Literal[True] = True
    history_dataset_rehashed: Literal[True] = True
    git_parent_stream_reexecuted_once: Literal[True] = True
    pull_dataset_reconstructed_exactly: Literal[True] = True
    mapping_dataset_reconstructed_exactly: Literal[True] = True
    unresolved_dataset_reconstructed_exactly: Literal[True] = True
    result_reconstructed_exactly: Literal[True] = True
    source_page_files_opened: Literal[245] = 245
    response_bodies_decoded: Literal[245] = 245
    local_git_process_count: Literal[1] = 1
    accepted_github_pull_count: int = Field(ge=1)
    total_exact_mapping_count: int = Field(ge=1)
    unresolved_git_merge_count: int = Field(ge=0)
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["PASS_S5_GITHUB_NORMALIZATION_RESULT_AUDIT"] = (
        "PASS_S5_GITHUB_NORMALIZATION_RESULT_AUDIT"
    )
    next_authorization: Literal[
        "AUTHORIZE_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_PROTOCOL_ONLY"
    ] = S5_GITHUB_NORMALIZATION_RESULT_NEXT
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
        "execution_contract_evidence_hash",
        "runner_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5GitHubNormalizationResultAudit:
        if self.accepted_github_pull_count != self.total_exact_mapping_count:
            raise ValueError("S5 audited reverse mapping count changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 normalization result audit hash changed")
        return self
