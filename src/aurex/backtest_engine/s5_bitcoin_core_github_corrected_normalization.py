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

S5_CORRECTED_NORMALIZATION_GATE_IDS = (
    "FROZEN_PREDECESSOR_FAILURE_AND_TARGETED_CORRECTION_LINEAGE_BOUND",
    "ALL_BOUND_SOURCE_FILES_REHASH_EXACTLY",
    "LEGACY_NORMALIZATION_FAILURE_RECONSTRUCTS_EXACTLY",
    "BULK_245_PAGE_24407_RAW_24398_COHORT_ACCOUNTING_RECONSTRUCTS",
    "TARGETED_194_RESPONSE_MANIFEST_RECONSTRUCTS_EXACTLY",
    "FIRST_PARENT_17543_COMMIT_16721_MERGE_TOPOLOGY_RECONSTRUCTS",
    "FULL_GRAPH_50395_COMMIT_REACHABILITY_RECONSTRUCTS",
    "LEGACY_16167_EXACT_MAPPINGS_ARE_PRESERVED",
    "EXACTLY_75_RECOGNIZED_GAPS_RECOVER_BY_DIRECT_HEAD_SHA",
    "EXACTLY_8_RECOGNIZED_ENDPOINT_404_GAPS_REMAIN_UNRESOLVED",
    "CANONICAL_GIT_PR_MAPPING_IS_ONE_TO_ONE_WITH_16242_ROWS",
    "ALL_16279_GITHUB_ACCEPTED_PULLS_RECEIVE_SOURCE_STATUS",
    "EXACTLY_16271_ACCEPTED_PULLS_HAVE_LOCAL_SOURCE_LINKAGE",
    "EXACTLY_8_ACCEPTED_PULLS_REMAIN_LOCAL_INCLUSION_UNVERIFIED",
    "MANY_TO_ONE_SOURCE_LINKS_ARE_PRESERVED_WITHOUT_CANONICAL_GUESSING",
    "GITHUB_ACCEPTED_AND_GIT_INTEGRATION_UNIVERSES_REMAIN_DISTINCT",
    "EVENT_TIME_SOURCE_AND_IDENTITY_UNCERTAINTY_ARE_EXPLICIT",
    "ALL_VERSIONED_OUTPUTS_RECONSTRUCT_BYTE_FOR_BYTE",
    "ZERO_NETWORK_MARKET_VALUES_PARAMETERS_RETURNS_CANDIDATES_OR_ORDERS",
)

S5_CORRECTED_CANONICAL_MAPPING_FIELDS = (
    "sequence",
    "merge_sequence",
    "merge_commit_sha",
    "first_parent_sha",
    "second_parent_sha",
    "git_committer_at",
    "canonical_pull_number",
    "census_pull_number",
    "census_pattern_id",
    "mapping_status",
    "github_merged_at",
    "event_at",
    "event_time_source",
    "actor_id",
    "actor_login",
    "actor_type",
    "actor_identity_status",
    "actor_class",
    "targeted_response_path",
    "targeted_response_file_sha256",
)

S5_CORRECTED_TARGET_RESOLUTION_FIELDS = (
    "sequence",
    "pull_number",
    "target_reasons",
    "http_status",
    "bulk_accepted",
    "direct_state",
    "direct_merged",
    "direct_merged_at",
    "direct_base_ref",
    "direct_head_sha",
    "direct_merge_commit_sha",
    "direct_merge_commit_sha_shape",
    "head_in_full_graph",
    "merge_commit_sha_in_full_graph",
    "canonical_merge_commit_sha",
    "canonical_mapping",
    "local_source_link_verified",
    "resolution_status",
    "response_path",
    "response_file_sha256",
    "response_body_sha256",
)

S5_CORRECTED_ACCEPTED_COVERAGE_FIELDS = (
    "sequence",
    "pull_number",
    "github_merged_at",
    "canonical_merge_commit_sha",
    "local_source_commit_sha",
    "source_link_status",
    "local_source_link_verified",
    "targeted_resolution_sequence",
)

S5_CORRECTED_UNRESOLVED_MERGE_FIELDS = (
    "sequence",
    "merge_sequence",
    "merge_commit_sha",
    "first_parent_sha",
    "second_parent_sha",
    "git_committer_at",
    "census_pull_number",
    "census_pattern_id",
    "resolution_status",
    "candidate_pull_numbers",
)

S5_RECOGNIZED_ENDPOINT_404_PULLS = (
    25_166,
    25_409,
    25_615,
    27_719,
    29_052,
    30_556,
    30_763,
    31_007,
)

S5_ACCEPTED_LOCAL_INCLUSION_UNVERIFIED_PULLS = (
    261,
    4_286,
    4_528,
    5_848,
    9_770,
    12_026,
    35_808,
    36_048,
)


class S5GitHubCorrectedNormalizationProtocolV2(BaseModel):
    schema_version: Literal[
        "aurex-s5-github-corrected-normalization-protocol-v2"
    ] = "aurex-s5-github-corrected-normalization-protocol-v2"
    protocol_id: Literal["s5-github-corrected-normalization-protocol-v2"] = (
        "s5-github-corrected-normalization-protocol-v2"
    )
    frozen_at: datetime
    status: Literal["FROZEN_CORRECTED_PROTOCOL_ZERO_EXECUTION"] = (
        "FROZEN_CORRECTED_PROTOCOL_ZERO_EXECUTION"
    )
    builder_contract_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=15, max_length=15)
    source_binding_manifest_evidence_hash: str
    failed_normalization_result_evidence_hash: str
    failure_adjudication_result_evidence_hash: str
    failure_adjudication_result_audit_evidence_hash: str
    targeted_correction_result_evidence_hash: str
    targeted_correction_result_audit_evidence_hash: str
    history_dataset_path: Literal[
        "data/evidence/s5_bitcoin_core_history_payload_v1.git"
    ] = "data/evidence/s5_bitcoin_core_history_payload_v1.git"
    source_cutoff_commit: Literal["dc0395c5858a1d55239b82a834e5075cf2069219"] = (
        "dc0395c5858a1d55239b82a834e5075cf2069219"
    )
    raw_bulk_page_directory: Literal[
        "data/evidence/s5_github_pull_metadata_bulk_v1"
    ] = "data/evidence/s5_github_pull_metadata_bulk_v1"
    raw_targeted_response_directory: Literal[
        "data/evidence/s5_github_targeted_pull_responses_v3"
    ] = "data/evidence/s5_github_targeted_pull_responses_v3"
    adopted_pull_10_response_path: Literal[
        "data/evidence/s5_github_targeted_pull_responses_v2/failure_pull_000010.json"
    ] = "data/evidence/s5_github_targeted_pull_responses_v2/failure_pull_000010.json"
    expected_raw_record_count: Literal[24_407] = 24_407
    expected_cohort_record_count: Literal[24_398] = 24_398
    expected_github_accepted_pull_count: Literal[16_279] = 16_279
    expected_legacy_exact_mapping_count: Literal[16_167] = 16_167
    expected_legacy_unresolved_merge_count: Literal[554] = 554
    expected_targeted_response_count: Literal[194] = 194
    expected_targeted_http_200_count: Literal[186] = 186
    expected_targeted_http_404_count: Literal[8] = 8
    expected_recognized_recovery_count: Literal[75] = 75
    expected_recognized_unresolved_count: Literal[8] = 8
    expected_canonical_mapping_count: Literal[16_242] = 16_242
    expected_corrected_unresolved_merge_count: Literal[479] = 479
    expected_accepted_source_linked_count: Literal[16_271] = 16_271
    expected_accepted_source_unverified_count: Literal[8] = 8
    expected_full_graph_commit_count: Literal[50_395] = 50_395
    expected_first_parent_commit_count: Literal[17_543] = 17_543
    expected_first_parent_merge_count: Literal[16_721] = 16_721
    recognized_endpoint_404_pull_numbers: tuple[int, ...] = (
        S5_RECOGNIZED_ENDPOINT_404_PULLS
    )
    accepted_local_inclusion_unverified_pull_numbers: tuple[int, ...] = (
        S5_ACCEPTED_LOCAL_INCLUSION_UNVERIFIED_PULLS
    )
    disclosed_many_to_one_pull_groups: tuple[tuple[int, ...], ...] = (
        (25_882, 25_891),
        (26_081, 26_084),
    )
    legacy_failure_reconstruction_rule: Literal[
        "RECONSTRUCT_V1_RESULT_COUNTS_AND_FAILED_GATES_BEFORE_CORRECTION"
    ] = "RECONSTRUCT_V1_RESULT_COUNTS_AND_FAILED_GATES_BEFORE_CORRECTION"
    bulk_metadata_rule: Literal[
        "PRESERVE_FROZEN_BULK_METADATA_AND_NEVER_OVERWRITE_WITH_CURRENT_TARGETED_VALUES"
    ] = "PRESERVE_FROZEN_BULK_METADATA_AND_NEVER_OVERWRITE_WITH_CURRENT_TARGETED_VALUES"
    recognized_recovery_rule: Literal[
        "CENSUS_PULL_NUMBER_PLUS_DIRECT_HTTP_200_NUMBER_PLUS_EXACT_SECOND_PARENT_HEAD_SHA"
    ] = "CENSUS_PULL_NUMBER_PLUS_DIRECT_HTTP_200_NUMBER_PLUS_EXACT_SECOND_PARENT_HEAD_SHA"
    canonical_mapping_rule: Literal[
        "ONE_CANONICAL_PULL_PER_FIRST_PARENT_MERGE_CENSUS_PRECEDENCE_THEN_UNIQUE_HEAD_ONLY"
    ] = "ONE_CANONICAL_PULL_PER_FIRST_PARENT_MERGE_CENSUS_PRECEDENCE_THEN_UNIQUE_HEAD_ONLY"
    accepted_source_link_rule: Literal[
        "CANONICAL_MAPPING_OR_EXACT_TARGET_HEAD_OR_MERGE_SHA_REACHABLE_FROM_CUTOFF"
    ] = "CANONICAL_MAPPING_OR_EXACT_TARGET_HEAD_OR_MERGE_SHA_REACHABLE_FROM_CUTOFF"
    ambiguous_link_rule: Literal[
        "PRESERVE_ALL_EXACT_SOURCE_LINKS_BUT_NEVER_GUESS_CANONICAL_OWNERSHIP"
    ] = "PRESERVE_ALL_EXACT_SOURCE_LINKS_BUT_NEVER_GUESS_CANONICAL_OWNERSHIP"
    event_universe_rule: Literal[
        "GITHUB_ACCEPTED_PULLS_AND_GIT_FIRST_PARENT_INTEGRATIONS_ARE_SEPARATE_UNIVERSES"
    ] = "GITHUB_ACCEPTED_PULLS_AND_GIT_FIRST_PARENT_INTEGRATIONS_ARE_SEPARATE_UNIVERSES"
    event_time_rule: Literal[
        "GITHUB_MERGED_AT_WHEN_PRESENT_ELSE_GIT_COMMITTER_TIME_WITH_SOURCE_LABEL"
    ] = "GITHUB_MERGED_AT_WHEN_PRESENT_ELSE_GIT_COMMITTER_TIME_WITH_SOURCE_LABEL"
    first_parent_command: Literal[
        "git rev-list --first-parent --reverse --parents --timestamp <cutoff>"
    ] = "git rev-list --first-parent --reverse --parents --timestamp <cutoff>"
    full_graph_command: Literal["git rev-list <cutoff>"] = "git rev-list <cutoff>"
    normalized_pull_fields: tuple[str, ...]
    canonical_mapping_fields: tuple[str, ...] = S5_CORRECTED_CANONICAL_MAPPING_FIELDS
    target_resolution_fields: tuple[str, ...] = S5_CORRECTED_TARGET_RESOLUTION_FIELDS
    accepted_coverage_fields: tuple[str, ...] = S5_CORRECTED_ACCEPTED_COVERAGE_FIELDS
    unresolved_merge_fields: tuple[str, ...] = S5_CORRECTED_UNRESOLVED_MERGE_FIELDS
    pull_output_path: Literal[
        "data/evidence/datasets/s5_bitcoin_core_github_pulls_normalized_v2.jsonl"
    ] = "data/evidence/datasets/s5_bitcoin_core_github_pulls_normalized_v2.jsonl"
    canonical_mapping_output_path: Literal[
        "data/evidence/datasets/s5_bitcoin_core_canonical_merge_mapping_v2.jsonl"
    ] = "data/evidence/datasets/s5_bitcoin_core_canonical_merge_mapping_v2.jsonl"
    target_resolution_output_path: Literal[
        "data/evidence/datasets/s5_bitcoin_core_target_resolution_v2.jsonl"
    ] = "data/evidence/datasets/s5_bitcoin_core_target_resolution_v2.jsonl"
    accepted_coverage_output_path: Literal[
        "data/evidence/datasets/s5_bitcoin_core_accepted_source_coverage_v2.jsonl"
    ] = "data/evidence/datasets/s5_bitcoin_core_accepted_source_coverage_v2.jsonl"
    unresolved_output_path: Literal[
        "data/evidence/datasets/s5_bitcoin_core_unresolved_git_merges_v2.jsonl"
    ] = "data/evidence/datasets/s5_bitcoin_core_unresolved_git_merges_v2.jsonl"
    result_path: Literal[
        "data/evidence/s5_bitcoin_core_github_corrected_normalization_result_v2.json"
    ] = "data/evidence/s5_bitcoin_core_github_corrected_normalization_result_v2.json"
    serialization: Literal[
        "UTF8_JSONL_SORTED_KEYS_COMPACT_SEPARATORS_LF_FINAL_NEWLINE"
    ] = "UTF8_JSONL_SORTED_KEYS_COMPACT_SEPARATORS_LF_FINAL_NEWLINE"
    maximum_local_git_process_count: Literal[2] = 2
    maximum_run_count: Literal[1] = 1
    maximum_elapsed_seconds: Literal[1_800] = 1_800
    maximum_each_output_bytes: Literal[134_217_728] = 134_217_728
    exploratory_source_analysis_completed_before_freeze: Literal[True] = True
    output_paths_absent_at_freeze: Literal[True] = True
    network_access_permitted: Literal[False] = False
    repository_fetch_permitted: Literal[False] = False
    github_api_requests_permitted: Literal[False] = False
    commit_message_access_permitted: Literal[False] = False
    author_or_committer_identity_access_permitted: Literal[False] = False
    git_committer_timestamp_access_permitted: Literal[True] = True
    btc_market_values_permitted: Literal[False] = False
    parameters_permitted: Literal[False] = False
    returns_permitted: Literal[False] = False
    strategy_candidate_permitted: Literal[False] = False
    paper_permitted: Literal[False] = False
    testnet_strategy_orders_permitted: Literal[False] = False
    production_permitted: Literal[False] = False
    live_permitted: Literal[False] = False
    required_gate_ids: tuple[str, ...] = Field(min_length=19, max_length=19)
    decision: Literal["FREEZE_S5_GITHUB_CORRECTED_NORMALIZATION_PROTOCOL"] = (
        "FREEZE_S5_GITHUB_CORRECTED_NORMALIZATION_PROTOCOL"
    )
    next_authorization: Literal[
        "IMPLEMENT_S5_GITHUB_CORRECTED_NORMALIZATION_EXECUTION_CONTRACT_ONLY"
    ] = "IMPLEMENT_S5_GITHUB_CORRECTED_NORMALIZATION_EXECUTION_CONTRACT_ONLY"
    limitations: tuple[str, ...] = Field(min_length=12)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "source_binding_manifest_evidence_hash",
        "failed_normalization_result_evidence_hash",
        "failure_adjudication_result_evidence_hash",
        "failure_adjudication_result_audit_evidence_hash",
        "targeted_correction_result_evidence_hash",
        "targeted_correction_result_audit_evidence_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S5GitHubCorrectedNormalizationProtocolV2:
        paths = tuple(row.path for row in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 corrected normalization source bindings changed")
        if self.source_binding_manifest_evidence_hash != universe_evidence_hash(
            tuple(row.model_dump(mode="json") for row in self.source_bindings)
        ):
            raise ValueError("S5 corrected normalization source manifest changed")
        if (
            self.recognized_endpoint_404_pull_numbers
            != S5_RECOGNIZED_ENDPOINT_404_PULLS
            or self.accepted_local_inclusion_unverified_pull_numbers
            != S5_ACCEPTED_LOCAL_INCLUSION_UNVERIFIED_PULLS
            or self.canonical_mapping_fields != S5_CORRECTED_CANONICAL_MAPPING_FIELDS
            or self.target_resolution_fields != S5_CORRECTED_TARGET_RESOLUTION_FIELDS
            or self.accepted_coverage_fields != S5_CORRECTED_ACCEPTED_COVERAGE_FIELDS
            or self.unresolved_merge_fields != S5_CORRECTED_UNRESOLVED_MERGE_FIELDS
            or self.required_gate_ids != S5_CORRECTED_NORMALIZATION_GATE_IDS
        ):
            raise ValueError("S5 corrected normalization frozen schema changed")
        if self.expected_accepted_source_linked_count + (
            self.expected_accepted_source_unverified_count
        ) != self.expected_github_accepted_pull_count:
            raise ValueError("S5 corrected accepted coverage accounting changed")
        forbidden = (
            self.network_access_permitted,
            self.repository_fetch_permitted,
            self.github_api_requests_permitted,
            self.commit_message_access_permitted,
            self.author_or_committer_identity_access_permitted,
            self.btc_market_values_permitted,
            self.parameters_permitted,
            self.returns_permitted,
            self.strategy_candidate_permitted,
            self.paper_permitted,
            self.testnet_strategy_orders_permitted,
            self.production_permitted,
            self.live_permitted,
        )
        if any(forbidden):
            raise ValueError("S5 corrected normalization grants forbidden authority")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S5 corrected normalization protocol hash changed")
        return self


class S5GitHubCorrectedNormalizationProtocolAuditV2(BaseModel):
    schema_version: Literal[
        "aurex-s5-github-corrected-normalization-protocol-audit-v2"
    ] = "aurex-s5-github-corrected-normalization-protocol-audit-v2"
    audit_id: Literal[
        "s5-github-corrected-normalization-protocol-audit-v2"
    ] = "s5-github-corrected-normalization-protocol-audit-v2"
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    builder_contract_hash: str
    source_binding_manifest_evidence_hash: str
    source_binding_count: Literal[15] = 15
    source_bindings_rehashed: Literal[15] = 15
    expected_targeted_response_count: Literal[194] = 194
    expected_canonical_mapping_count: Literal[16_242] = 16_242
    expected_accepted_source_linked_count: Literal[16_271] = 16_271
    expected_explicit_unverified_count: Literal[8] = 8
    auditor_source_sha256: str
    source_rows_opened: Literal[0] = 0
    local_git_processes_executed: Literal[0] = 0
    github_requests_executed: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    reconstructed_exactly: Literal[True] = True
    decision: Literal["PASS_S5_GITHUB_CORRECTED_NORMALIZATION_PROTOCOL_AUDIT"] = (
        "PASS_S5_GITHUB_CORRECTED_NORMALIZATION_PROTOCOL_AUDIT"
    )
    next_authorization: Literal[
        "IMPLEMENT_S5_GITHUB_CORRECTED_NORMALIZATION_EXECUTION_CONTRACT_ONLY"
    ] = "IMPLEMENT_S5_GITHUB_CORRECTED_NORMALIZATION_EXECUTION_CONTRACT_ONLY"
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
        "source_binding_manifest_evidence_hash",
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5GitHubCorrectedNormalizationProtocolAuditV2:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 corrected normalization protocol audit hash changed")
        return self
