from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s5_bitcoin_core_github_corrected_normalization import (
    S5_CORRECTED_ACCEPTED_COVERAGE_FIELDS,
    S5_CORRECTED_CANONICAL_MAPPING_FIELDS,
    S5_CORRECTED_NORMALIZATION_GATE_IDS,
    S5_CORRECTED_TARGET_RESOLUTION_FIELDS,
    S5_CORRECTED_UNRESOLVED_MERGE_FIELDS,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import S5HistoryBinding
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S5_CORRECTED_NORMALIZATION_PASS = "PASS_S5_GITHUB_CORRECTED_NORMALIZATION"
S5_CORRECTED_NORMALIZATION_STOP = "STOP_S5_GITHUB_CORRECTED_NORMALIZATION"
S5_CORRECTED_NORMALIZATION_NEXT = (
    "FREEZE_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_PROTOCOL_ONLY"
)
S5_CORRECTED_NORMALIZATION_FAILURE_NEXT = (
    "FREEZE_S5_GITHUB_CORRECTED_NORMALIZATION_FAILURE_ADJUDICATION_ONLY"
)


class S5CorrectedCanonicalMappingRow(BaseModel):
    sequence: int = Field(gt=0)
    merge_sequence: int = Field(gt=0)
    merge_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    first_parent_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    second_parent_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    git_committer_at: datetime
    canonical_pull_number: int = Field(gt=0)
    census_pull_number: int | None = Field(default=None, gt=0)
    census_pattern_id: Literal[
        "BITCOIN_CORE_MAINTAINER_MERGE",
        "GITHUB_DEFAULT_PULL_MERGE",
    ] | None = None
    mapping_status: Literal[
        "LEGACY_RECOGNIZED_NUMBER_AND_HEAD_SHA_EXACT",
        "LEGACY_UNRECOGNIZED_SECOND_PARENT_HEAD_SHA_EXACT",
        "TARGETED_RECOGNIZED_NUMBER_AND_SECOND_PARENT_HEAD_SHA_EXACT",
    ]
    github_merged_at: datetime | None
    event_at: datetime
    event_time_source: Literal["GITHUB_MERGED_AT", "GIT_COMMITTER_AT"]
    actor_id: int | None = Field(default=None, gt=0)
    actor_login: str | None = Field(default=None, min_length=1)
    actor_type: str | None = Field(default=None, min_length=1)
    actor_identity_status: Literal["KNOWN_ACCOUNT", "UNKNOWN_DELETED_OR_NULL"]
    actor_class: Literal["HUMAN_OR_UNRESOLVED_ACCOUNT", "BOT", "UNKNOWN"]
    targeted_response_path: str | None = None
    targeted_response_file_sha256: str | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("git_committer_at", "github_merged_at", "event_at")
    @classmethod
    def normalize_times(cls, value: datetime | None) -> datetime | None:
        return None if value is None else normalize_timestamp(value)

    @field_validator("targeted_response_file_sha256")
    @classmethod
    def normalize_optional_hash(cls, value: str | None) -> str | None:
        return None if value is None else normalize_sha256(value)

    @model_validator(mode="after")
    def validate_row(self) -> S5CorrectedCanonicalMappingRow:
        census_fields = (self.census_pull_number, self.census_pattern_id)
        if any(value is not None for value in census_fields) != all(
            value is not None for value in census_fields
        ):
            raise ValueError("S5 corrected canonical census identity is partial")
        if self.census_pull_number is not None and (
            self.census_pull_number != self.canonical_pull_number
        ):
            raise ValueError("S5 corrected canonical census pull identity changed")
        targeted = self.mapping_status.startswith("TARGETED_")
        if targeted != (
            self.targeted_response_path is not None
            and self.targeted_response_file_sha256 is not None
        ):
            raise ValueError("S5 corrected canonical targeted lineage changed")
        if self.github_merged_at is None:
            expected_time = self.git_committer_at
            expected_source = "GIT_COMMITTER_AT"
        else:
            expected_time = self.github_merged_at
            expected_source = "GITHUB_MERGED_AT"
        if self.event_at != expected_time or self.event_time_source != expected_source:
            raise ValueError("S5 corrected canonical event time changed")
        known = all(
            value is not None
            for value in (self.actor_id, self.actor_login, self.actor_type)
        )
        if known != (self.actor_identity_status == "KNOWN_ACCOUNT"):
            raise ValueError("S5 corrected canonical actor identity changed")
        if not known and self.actor_class != "UNKNOWN":
            raise ValueError("S5 corrected canonical unknown actor class changed")
        return self


class S5CorrectedTargetResolutionRow(BaseModel):
    sequence: int = Field(gt=0, le=194)
    pull_number: int = Field(gt=0)
    target_reasons: tuple[
        Literal["RECOGNIZED_GAP", "UNMATCHED_ACCEPTED_PULL"], ...
    ] = Field(min_length=1, max_length=2)
    http_status: Literal[200, 404]
    bulk_accepted: bool
    direct_state: Literal["open", "closed"] | None
    direct_merged: bool | None
    direct_merged_at: datetime | None
    direct_base_ref: str | None = Field(default=None, min_length=1)
    direct_head_sha: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    direct_merge_commit_sha: str | None
    direct_merge_commit_sha_shape: Literal[
        "NOT_APPLICABLE_404", "NULL", "EMPTY_STRING", "SHA1_40_LOWER_HEX"
    ]
    head_in_full_graph: bool
    merge_commit_sha_in_full_graph: bool
    canonical_merge_commit_sha: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{40}$"
    )
    canonical_mapping: bool
    local_source_link_verified: bool
    resolution_status: Literal[
        "CANONICAL_RECOGNIZED_ACCEPTED",
        "CANONICAL_RECOGNIZED_SOURCE_ONLY",
        "RECOGNIZED_ENDPOINT_404_UNRESOLVED",
        "ACCEPTED_EXACT_NONCANONICAL_FIRST_PARENT_LINK",
        "ACCEPTED_FULL_GRAPH_EXACT",
        "ACCEPTED_LOCAL_INCLUSION_UNVERIFIED",
    ]
    response_path: str = Field(min_length=1)
    response_file_sha256: str
    response_body_sha256: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("direct_merged_at")
    @classmethod
    def normalize_time(cls, value: datetime | None) -> datetime | None:
        return None if value is None else normalize_timestamp(value)

    @field_validator("response_file_sha256", "response_body_sha256")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_row(self) -> S5CorrectedTargetResolutionRow:
        if self.target_reasons != tuple(sorted(set(self.target_reasons))):
            raise ValueError("S5 corrected target reasons changed")
        direct_fields = (
            self.direct_state,
            self.direct_merged,
            self.direct_base_ref,
            self.direct_head_sha,
        )
        if self.http_status == 404:
            if (
                any(value is not None for value in direct_fields)
                or self.direct_merged_at is not None
                or self.direct_merge_commit_sha is not None
                or self.direct_merge_commit_sha_shape != "NOT_APPLICABLE_404"
                or self.head_in_full_graph
                or self.merge_commit_sha_in_full_graph
                or self.canonical_mapping
                or self.local_source_link_verified
                or self.resolution_status != "RECOGNIZED_ENDPOINT_404_UNRESOLVED"
            ):
                raise ValueError("S5 corrected 404 target semantics changed")
        elif any(value is None for value in direct_fields):
            raise ValueError("S5 corrected HTTP 200 target fields are incomplete")
        if self.canonical_mapping != (self.canonical_merge_commit_sha is not None):
            raise ValueError("S5 corrected canonical target identity changed")
        if self.canonical_mapping and not self.local_source_link_verified:
            raise ValueError("S5 corrected canonical target lacks source linkage")
        merge_sha = self.direct_merge_commit_sha
        expected_shape = (
            "NULL"
            if merge_sha is None
            else "EMPTY_STRING"
            if merge_sha == ""
            else "SHA1_40_LOWER_HEX"
        )
        if self.http_status == 200 and self.direct_merge_commit_sha_shape != expected_shape:
            raise ValueError("S5 corrected target merge SHA shape changed")
        if merge_sha not in {None, ""} and (
            len(merge_sha) != 40
            or merge_sha.casefold() != merge_sha
            or any(character not in "0123456789abcdef" for character in merge_sha)
        ):
            raise ValueError("S5 corrected target merge SHA is invalid")
        return self


class S5CorrectedAcceptedCoverageRow(BaseModel):
    sequence: int = Field(gt=0)
    pull_number: int = Field(gt=0)
    github_merged_at: datetime
    canonical_merge_commit_sha: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{40}$"
    )
    local_source_commit_sha: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{40}$"
    )
    source_link_status: Literal[
        "CANONICAL_FIRST_PARENT",
        "TARGETED_FULL_GRAPH_EXACT",
        "LOCAL_INCLUSION_UNVERIFIED",
    ]
    local_source_link_verified: bool
    targeted_resolution_sequence: int | None = Field(default=None, gt=0, le=194)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("github_merged_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_row(self) -> S5CorrectedAcceptedCoverageRow:
        verified = self.source_link_status != "LOCAL_INCLUSION_UNVERIFIED"
        if verified != self.local_source_link_verified:
            raise ValueError("S5 corrected accepted coverage status changed")
        if verified != (self.local_source_commit_sha is not None):
            raise ValueError("S5 corrected accepted source identity changed")
        canonical = self.source_link_status == "CANONICAL_FIRST_PARENT"
        if canonical != (self.canonical_merge_commit_sha is not None):
            raise ValueError("S5 corrected accepted canonical identity changed")
        targeted = self.source_link_status != "CANONICAL_FIRST_PARENT"
        if targeted != (self.targeted_resolution_sequence is not None):
            raise ValueError("S5 corrected accepted targeted lineage changed")
        return self


class S5CorrectedUnresolvedMergeRow(BaseModel):
    sequence: int = Field(gt=0)
    merge_sequence: int = Field(gt=0)
    merge_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    first_parent_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    second_parent_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    git_committer_at: datetime
    census_pull_number: int | None = Field(default=None, gt=0)
    census_pattern_id: Literal[
        "BITCOIN_CORE_MAINTAINER_MERGE",
        "GITHUB_DEFAULT_PULL_MERGE",
    ] | None = None
    resolution_status: Literal[
        "NO_ACCEPTED_GITHUB_HEAD_MATCH",
        "MULTIPLE_ACCEPTED_GITHUB_HEAD_MATCHES",
        "RECOGNIZED_PULL_ENDPOINT_404",
        "MULTIPLE_TARGETED_PULLS_EXACT_SAME_MERGE",
    ]
    candidate_pull_numbers: tuple[int, ...] = Field(max_length=25)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("git_committer_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_row(self) -> S5CorrectedUnresolvedMergeRow:
        if self.candidate_pull_numbers != tuple(sorted(set(self.candidate_pull_numbers))):
            raise ValueError("S5 corrected unresolved candidate pulls changed")
        census_fields = (self.census_pull_number, self.census_pattern_id)
        if any(value is not None for value in census_fields) != all(
            value is not None for value in census_fields
        ):
            raise ValueError("S5 corrected unresolved census identity is partial")
        if self.resolution_status == "RECOGNIZED_PULL_ENDPOINT_404" and (
            self.census_pull_number not in {
                25_166,
                25_409,
                25_615,
                27_719,
                29_052,
                30_556,
                30_763,
                31_007,
            }
        ):
            raise ValueError("S5 corrected unresolved 404 identity changed")
        return self


class S5CorrectedNormalizationGateResult(BaseModel):
    gate_id: str = Field(min_length=1)
    status: Literal["PASS", "FAIL"]
    evidence: str = Field(min_length=1, max_length=500)

    model_config = ConfigDict(extra="forbid", frozen=True)


class S5GitHubCorrectedNormalizationExecutionContractV2(BaseModel):
    schema_version: Literal[
        "aurex-s5-github-corrected-normalization-execution-contract-v2"
    ] = "aurex-s5-github-corrected-normalization-execution-contract-v2"
    contract_id: Literal[
        "s5-github-corrected-normalization-execution-contract-v2"
    ] = "s5-github-corrected-normalization-execution-contract-v2"
    frozen_at: datetime
    status: Literal["FROZEN_EXECUTION_CONTRACT_ZERO_EXECUTION"] = (
        "FROZEN_EXECUTION_CONTRACT_ZERO_EXECUTION"
    )
    builder_contract_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=2, max_length=2)
    source_binding_manifest_evidence_hash: str
    implementation_bindings: tuple[S5HistoryBinding, ...] = Field(
        min_length=9, max_length=9
    )
    implementation_binding_manifest_evidence_hash: str
    protocol_evidence_hash: str
    protocol_audit_evidence_hash: str
    runner_contract_hash: str
    authorizes_single_local_run: Literal[True] = True
    maximum_local_git_process_count: Literal[2] = 2
    network_access_permitted: Literal[False] = False
    github_api_requests_permitted: Literal[False] = False
    repository_fetch_permitted: Literal[False] = False
    market_values_permitted: Literal[False] = False
    parameters_permitted: Literal[False] = False
    returns_permitted: Literal[False] = False
    strategy_candidates_permitted: Literal[False] = False
    paper_permitted: Literal[False] = False
    testnet_strategy_orders_permitted: Literal[False] = False
    production_permitted: Literal[False] = False
    live_permitted: Literal[False] = False
    result_path: Literal[
        "data/evidence/s5_bitcoin_core_github_corrected_normalization_result_v2.json"
    ] = "data/evidence/s5_bitcoin_core_github_corrected_normalization_result_v2.json"
    contract_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "source_binding_manifest_evidence_hash",
        "implementation_binding_manifest_evidence_hash",
        "protocol_evidence_hash",
        "protocol_audit_evidence_hash",
        "runner_contract_hash",
        "contract_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_contract(self) -> S5GitHubCorrectedNormalizationExecutionContractV2:
        for rows in (self.source_bindings, self.implementation_bindings):
            paths = tuple(row.path for row in rows)
            if paths != tuple(sorted(set(paths))):
                raise ValueError("S5 corrected execution bindings changed")
        if self.source_binding_manifest_evidence_hash != universe_evidence_hash(
            tuple(row.model_dump(mode="json") for row in self.source_bindings)
        ) or self.implementation_binding_manifest_evidence_hash != universe_evidence_hash(
            tuple(row.model_dump(mode="json") for row in self.implementation_bindings)
        ):
            raise ValueError("S5 corrected execution binding hash changed")
        if any(
            (
                self.network_access_permitted,
                self.github_api_requests_permitted,
                self.repository_fetch_permitted,
                self.market_values_permitted,
                self.parameters_permitted,
                self.returns_permitted,
                self.strategy_candidates_permitted,
                self.paper_permitted,
                self.testnet_strategy_orders_permitted,
                self.production_permitted,
                self.live_permitted,
            )
        ):
            raise ValueError("S5 corrected execution grants forbidden authority")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"contract_evidence_hash"})
        )
        if self.contract_evidence_hash != expected:
            raise ValueError("S5 corrected execution contract hash changed")
        return self


class S5GitHubCorrectedNormalizationExecutionContractAuditV2(BaseModel):
    schema_version: Literal[
        "aurex-s5-github-corrected-normalization-execution-contract-audit-v2"
    ] = "aurex-s5-github-corrected-normalization-execution-contract-audit-v2"
    audit_id: Literal[
        "s5-github-corrected-normalization-execution-contract-audit-v2"
    ] = "s5-github-corrected-normalization-execution-contract-audit-v2"
    audited_at: datetime
    contract_file_sha256: str
    contract_evidence_hash: str
    builder_contract_hash: str
    runner_contract_hash: str
    source_binding_manifest_evidence_hash: str
    implementation_binding_manifest_evidence_hash: str
    auditor_source_sha256: str
    reconstructed_exactly: Literal[True] = True
    local_git_processes_executed: Literal[0] = 0
    github_requests_executed: Literal[0] = 0
    market_values_read: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal[
        "PASS_S5_GITHUB_CORRECTED_NORMALIZATION_EXECUTION_CONTRACT_AUDIT"
    ] = "PASS_S5_GITHUB_CORRECTED_NORMALIZATION_EXECUTION_CONTRACT_AUDIT"
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "contract_file_sha256",
        "contract_evidence_hash",
        "builder_contract_hash",
        "runner_contract_hash",
        "source_binding_manifest_evidence_hash",
        "implementation_binding_manifest_evidence_hash",
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5GitHubCorrectedNormalizationExecutionContractAuditV2:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 corrected execution contract audit hash changed")
        return self


class S5GitHubCorrectedNormalizationResultV2(BaseModel):
    schema_version: Literal[
        "aurex-s5-github-corrected-normalization-result-v2"
    ] = "aurex-s5-github-corrected-normalization-result-v2"
    result_id: Literal["s5-github-corrected-normalization-result-v2"] = (
        "s5-github-corrected-normalization-result-v2"
    )
    started_at: datetime
    completed_at: datetime
    elapsed_seconds: float = Field(ge=0, le=1_800)
    protocol_evidence_hash: str
    protocol_audit_evidence_hash: str
    execution_contract_evidence_hash: str
    execution_contract_audit_evidence_hash: str
    runner_contract_hash: str
    failed_normalization_result_evidence_hash: str
    targeted_correction_result_evidence_hash: str
    targeted_correction_result_audit_evidence_hash: str
    history_dataset_directory_sha256: str
    first_parent_stream_sha256: str | None
    full_graph_stream_sha256: str | None
    source_page_files_opened: int = Field(ge=0, le=245)
    response_bodies_decoded: int = Field(ge=0, le=245)
    targeted_responses_decoded: int = Field(ge=0, le=194)
    local_git_process_count: int = Field(ge=0, le=2)
    raw_record_count: int = Field(ge=0, le=24_407)
    cohort_record_count: int = Field(ge=0, le=24_398)
    github_accepted_pull_count: int = Field(ge=0, le=16_279)
    first_parent_commit_count: int = Field(ge=0, le=17_543)
    first_parent_merge_count: int = Field(ge=0, le=16_721)
    full_graph_commit_count: int = Field(ge=0, le=50_395)
    legacy_exact_mapping_count: int = Field(ge=0, le=16_167)
    legacy_unresolved_merge_count: int = Field(ge=0, le=554)
    recognized_recovery_count: int = Field(ge=0, le=75)
    recognized_unresolved_count: int = Field(ge=0, le=8)
    canonical_mapping_count: int = Field(ge=0, le=16_242)
    corrected_unresolved_merge_count: int = Field(ge=0, le=479)
    accepted_source_linked_count: int = Field(ge=0, le=16_271)
    accepted_source_unverified_count: int = Field(ge=0, le=8)
    many_to_one_group_count: int = Field(ge=0, le=2)
    output_paths: tuple[str, ...] = Field(max_length=5)
    output_file_sha256s: tuple[str, ...] = Field(max_length=5)
    output_byte_counts: tuple[int, ...] = Field(max_length=5)
    output_row_counts: tuple[int, ...] = Field(max_length=5)
    output_row_manifest_evidence_hashes: tuple[str, ...] = Field(max_length=5)
    gate_results: tuple[S5CorrectedNormalizationGateResult, ...] = Field(
        min_length=19, max_length=19
    )
    passed_gate_count: int = Field(ge=0, le=19)
    failed_gate_count: int = Field(ge=0, le=19)
    original_normalization_stop_upheld: Literal[True] = True
    github_and_git_universes_separate: Literal[True] = True
    network_requests_executed: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal[
        "PASS_S5_GITHUB_CORRECTED_NORMALIZATION",
        "STOP_S5_GITHUB_CORRECTED_NORMALIZATION",
    ]
    next_authorization: Literal[
        "FREEZE_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_PROTOCOL_ONLY",
        "FREEZE_S5_GITHUB_CORRECTED_NORMALIZATION_FAILURE_ADJUDICATION_ONLY",
    ]
    authorizes_measurement_protocol_design: bool
    authorizes_market_values: Literal[False] = False
    authorizes_returns: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    failure_type: str | None
    failure_message: str | None = Field(max_length=2_000)
    limitations: tuple[str, ...] = Field(min_length=12)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("started_at", "completed_at")
    @classmethod
    def normalize_times(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_evidence_hash",
        "protocol_audit_evidence_hash",
        "execution_contract_evidence_hash",
        "execution_contract_audit_evidence_hash",
        "runner_contract_hash",
        "failed_normalization_result_evidence_hash",
        "targeted_correction_result_evidence_hash",
        "targeted_correction_result_audit_evidence_hash",
        "history_dataset_directory_sha256",
        "first_parent_stream_sha256",
        "full_graph_stream_sha256",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str | None) -> str | None:
        return None if value is None else normalize_sha256(value)

    @field_validator("output_file_sha256s", "output_row_manifest_evidence_hashes")
    @classmethod
    def normalize_hash_sets(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(normalize_sha256(item) for item in value)

    @model_validator(mode="after")
    def validate_result(self) -> S5GitHubCorrectedNormalizationResultV2:
        if self.completed_at < self.started_at:
            raise ValueError("S5 corrected normalization completion precedes start")
        if tuple(gate.gate_id for gate in self.gate_results) != (
            S5_CORRECTED_NORMALIZATION_GATE_IDS
        ):
            raise ValueError("S5 corrected normalization result gates changed")
        schemas = (
            (S5CorrectedCanonicalMappingRow, S5_CORRECTED_CANONICAL_MAPPING_FIELDS),
            (S5CorrectedTargetResolutionRow, S5_CORRECTED_TARGET_RESOLUTION_FIELDS),
            (S5CorrectedAcceptedCoverageRow, S5_CORRECTED_ACCEPTED_COVERAGE_FIELDS),
            (S5CorrectedUnresolvedMergeRow, S5_CORRECTED_UNRESOLVED_MERGE_FIELDS),
        )
        if any(tuple(model.model_fields) != fields for model, fields in schemas):
            raise ValueError("S5 corrected normalization output schema changed")
        passed = sum(gate.status == "PASS" for gate in self.gate_results)
        if (self.passed_gate_count, self.failed_gate_count) != (
            passed,
            len(self.gate_results) - passed,
        ):
            raise ValueError("S5 corrected normalization gate accounting changed")
        output_lengths = {
            len(self.output_paths),
            len(self.output_file_sha256s),
            len(self.output_byte_counts),
            len(self.output_row_counts),
            len(self.output_row_manifest_evidence_hashes),
        }
        if len(output_lengths) != 1:
            raise ValueError("S5 corrected normalization output accounting changed")
        successful = self.failed_gate_count == 0
        exact_pass = (
            len(self.output_paths) == 5
            and self.source_page_files_opened == 245
            and self.response_bodies_decoded == 245
            and self.targeted_responses_decoded == 194
            and self.local_git_process_count == 2
            and self.raw_record_count == 24_407
            and self.cohort_record_count == 24_398
            and self.github_accepted_pull_count == 16_279
            and self.first_parent_commit_count == 17_543
            and self.first_parent_merge_count == 16_721
            and self.full_graph_commit_count == 50_395
            and self.legacy_exact_mapping_count == 16_167
            and self.legacy_unresolved_merge_count == 554
            and self.recognized_recovery_count == 75
            and self.recognized_unresolved_count == 8
            and self.canonical_mapping_count == 16_242
            and self.corrected_unresolved_merge_count == 479
            and self.accepted_source_linked_count == 16_271
            and self.accepted_source_unverified_count == 8
            and self.many_to_one_group_count == 2
            and self.first_parent_stream_sha256 is not None
            and self.full_graph_stream_sha256 is not None
            and self.failure_type is None
            and self.failure_message is None
        )
        if successful != exact_pass:
            raise ValueError("S5 corrected normalization pass accounting changed")
        if successful != (
            self.decision == S5_CORRECTED_NORMALIZATION_PASS
            and self.next_authorization == S5_CORRECTED_NORMALIZATION_NEXT
            and self.authorizes_measurement_protocol_design
        ):
            raise ValueError("S5 corrected normalization pass decision changed")
        if not successful and (
            self.decision != S5_CORRECTED_NORMALIZATION_STOP
            or self.next_authorization != S5_CORRECTED_NORMALIZATION_FAILURE_NEXT
            or self.authorizes_measurement_protocol_design
            or not self.failure_type
            or not self.failure_message
        ):
            raise ValueError("S5 corrected normalization stop evidence changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("S5 corrected normalization result hash changed")
        return self
