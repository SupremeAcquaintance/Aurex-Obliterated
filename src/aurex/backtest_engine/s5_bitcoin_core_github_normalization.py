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

S5_GITHUB_NORMALIZATION_PROTOCOL_DECISION = (
    "FREEZE_S5_GITHUB_METADATA_NORMALIZATION_AND_COMPLETENESS_PROTOCOL"
)
S5_GITHUB_NORMALIZATION_NEXT = (
    "AUTHORIZE_S5_GITHUB_NORMALIZATION_EXECUTION_CONTRACT_IMPLEMENTATION_ONLY"
)

S5_GITHUB_NORMALIZED_PULL_FIELDS = (
    "sequence",
    "pull_number",
    "node_id",
    "state",
    "created_at",
    "updated_at",
    "closed_at",
    "merged_at",
    "head_sha",
    "base_ref",
    "base_sha",
    "actor_id",
    "actor_login",
    "actor_type",
    "actor_identity_status",
    "actor_class",
    "source_page",
    "source_page_sha256",
    "source_response_body_sha256",
)

S5_GITHUB_MERGE_MAPPING_FIELDS = (
    "sequence",
    "merge_commit_sha",
    "first_parent_sha",
    "second_parent_sha",
    "census_pull_number",
    "census_pattern_id",
    "mapping_status",
    "pull_number",
    "merged_at",
    "actor_id",
    "actor_login",
    "actor_type",
    "actor_identity_status",
    "actor_class",
)

S5_GITHUB_UNRESOLVED_MERGE_FIELDS = (
    "sequence",
    "merge_commit_sha",
    "first_parent_sha",
    "second_parent_sha",
    "census_pull_number",
    "census_pattern_id",
    "resolution_status",
    "candidate_pull_numbers",
)

S5_GITHUB_NORMALIZATION_GATE_IDS = (
    "FROZEN_S5_LINEAGE_AND_READINESS_V34_BOUND",
    "GITHUB_PAGE_MANIFEST_AND_GIT_DATASET_IDENTITIES_REHASHED",
    "EXACT_245_PAGE_24407_RAW_24398_COHORT_9_POST_CUTOFF_ACCOUNTING",
    "EVERY_PAGE_ENVELOPE_AND_RESPONSE_BODY_RECONSTRUCTS_EXACTLY",
    "COHORT_PULL_NUMBERS_AND_NODE_IDS_ARE_UNIQUE",
    "POST_CUTOFF_RECORDS_ARE_PRESERVED_BUT_EXCLUDED",
    "NORMALIZED_PULL_SCHEMA_AND_SERIALIZATION_ARE_EXACT",
    "ONE_LOCAL_FIRST_PARENT_PARENTS_COMMAND_ONLY",
    "GIT_TOPOLOGY_RECONCILES_TO_FROZEN_CENSUS",
    "ALL_7961_CENSUS_RECOGNIZED_PULL_IDS_EXIST_IN_COHORT",
    "ALL_CENSUS_RECOGNIZED_PULL_IDS_MATCH_SECOND_PARENT_HEAD_SHA",
    "EVERY_IN_CUTOFF_MASTER_MERGED_PULL_MAPS_TO_ONE_GIT_MERGE",
    "GIT_MERGE_TO_PULL_MAPPINGS_ARE_ONE_TO_ONE_AND_UNAMBIGUOUS",
    "UNRESOLVED_GIT_MERGES_ARE_PRESERVED_AND_NEVER_GUESSED",
    "ACTOR_IDENTITY_UNCERTAINTY_AND_BOT_CLASSIFICATION_ARE_EXPLICIT",
    "ALL_OUTPUT_DATASETS_RECONSTRUCT_BYTE_FOR_BYTE",
    "ZERO_MARKET_VALUES_PARAMETERS_RETURNS_CANDIDATES_OR_ORDERS",
)


class S5GitHubNormalizationProtocol(BaseModel):
    schema_version: Literal["aurex-s5-github-normalization-protocol-v1"] = (
        "aurex-s5-github-normalization-protocol-v1"
    )
    protocol_id: Literal["s5-github-normalization-protocol-v1"] = (
        "s5-github-normalization-protocol-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_PROTOCOL_ONLY_ZERO_SOURCE_ROW_ACCESS"] = (
        "FROZEN_PROTOCOL_ONLY_ZERO_SOURCE_ROW_ACCESS"
    )
    builder_contract_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=16, max_length=16)
    source_binding_manifest_evidence_hash: str
    readiness_v34_result_evidence_hash: str
    readiness_v34_audit_evidence_hash: str
    charter_evidence_hash: str
    charter_audit_evidence_hash: str
    history_result_evidence_hash: str
    history_result_audit_evidence_hash: str
    census_result_evidence_hash: str
    census_result_audit_evidence_hash: str
    bulk_protocol_evidence_hash: str
    bulk_protocol_audit_evidence_hash: str
    monotonic_amendment_evidence_hash: str
    monotonic_amendment_audit_evidence_hash: str
    bulk_result_evidence_hash: str
    bulk_final_audit_evidence_hash: str
    history_dataset_path: Literal[
        "data/evidence/s5_bitcoin_core_history_payload_v1.git"
    ] = "data/evidence/s5_bitcoin_core_history_payload_v1.git"
    history_dataset_directory_sha256: str
    source_cutoff_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    raw_page_directory: Literal["data/evidence/s5_github_pull_metadata_bulk_v1"] = (
        "data/evidence/s5_github_pull_metadata_bulk_v1"
    )
    bulk_page_manifest_evidence_hash: str
    cohort_created_at_cutoff: datetime
    expected_page_count: Literal[245] = 245
    expected_raw_record_count: Literal[24407] = 24_407
    expected_cohort_record_count: Literal[24398] = 24_398
    expected_post_cutoff_record_count: Literal[9] = 9
    expected_first_parent_commit_count: Literal[17543] = 17_543
    expected_root_commit_count: Literal[1] = 1
    expected_single_parent_commit_count: Literal[821] = 821
    expected_merge_commit_count: Literal[16721] = 16_721
    expected_octopus_merge_commit_count: Literal[0] = 0
    expected_recognized_pull_merge_count: Literal[7961] = 7_961
    expected_unrecognized_merge_count: Literal[8760] = 8_760
    expected_distinct_recognized_pull_count: Literal[7961] = 7_961
    git_parent_command: Literal[
        "git rev-list --first-parent --reverse --parents <source_cutoff_commit>"
    ] = "git rev-list --first-parent --reverse --parents <source_cutoff_commit>"
    cohort_rule: Literal["CREATED_AT_LE_FROZEN_COHORT_CUTOFF"] = (
        "CREATED_AT_LE_FROZEN_COHORT_CUTOFF"
    )
    accepted_pull_rule: Literal[
        "STATE_CLOSED_AND_MERGED_AT_NON_NULL_LE_CUTOFF_AND_BASE_REF_MASTER"
    ] = "STATE_CLOSED_AND_MERGED_AT_NON_NULL_LE_CUTOFF_AND_BASE_REF_MASTER"
    git_mapping_rule: Literal[
        "EXACT_GITHUB_HEAD_SHA_EQUALS_EXACT_GIT_SECOND_PARENT_SHA"
    ] = "EXACT_GITHUB_HEAD_SHA_EQUALS_EXACT_GIT_SECOND_PARENT_SHA"
    recognized_pull_rule: Literal[
        "CENSUS_PULL_NUMBER_AND_SECOND_PARENT_HEAD_SHA_MUST_BOTH_MATCH"
    ] = "CENSUS_PULL_NUMBER_AND_SECOND_PARENT_HEAD_SHA_MUST_BOTH_MATCH"
    reverse_coverage_rule: Literal[
        "EVERY_ACCEPTED_GITHUB_PULL_MUST_MAP_TO_EXACTLY_ONE_FROZEN_GIT_MERGE"
    ] = "EVERY_ACCEPTED_GITHUB_PULL_MUST_MAP_TO_EXACTLY_ONE_FROZEN_GIT_MERGE"
    ambiguity_rule: Literal["REJECT_ALL_ZERO_OR_MULTIPLE_CANDIDATE_ACCEPTED_MAPPINGS"] = (
        "REJECT_ALL_ZERO_OR_MULTIPLE_CANDIDATE_ACCEPTED_MAPPINGS"
    )
    unresolved_git_merge_rule: Literal[
        "PRESERVE_WITH_STATUS_AND_NEVER_IMPUTE_AS_ACCEPTED_PULL"
    ] = "PRESERVE_WITH_STATUS_AND_NEVER_IMPUTE_AS_ACCEPTED_PULL"
    event_time_rule: Literal[
        "GITHUB_MERGED_AT_IS_EVENT_PROXY_NOT_PROOF_OF_HISTORICAL_INGESTION_TIME"
    ] = "GITHUB_MERGED_AT_IS_EVENT_PROXY_NOT_PROOF_OF_HISTORICAL_INGESTION_TIME"
    actor_identity_rule: Literal[
        "USER_ID_PRIMARY_LOGIN_DISPLAY_ONLY_NULL_USER_EXPLICIT_UNKNOWN"
    ] = "USER_ID_PRIMARY_LOGIN_DISPLAY_ONLY_NULL_USER_EXPLICIT_UNKNOWN"
    actor_alias_rule: Literal[
        "DO_NOT_MERGE_DISTINCT_USER_IDS_OR_INFER_REAL_PERSON_IDENTITIES"
    ] = "DO_NOT_MERGE_DISTINCT_USER_IDS_OR_INFER_REAL_PERSON_IDENTITIES"
    bot_rule: Literal[
        "BOT_IF_USER_TYPE_BOT_OR_CASEFOLDED_LOGIN_ENDS_WITH_LEFT_BRACKET_BOT_RIGHT_BRACKET"
    ] = (
        "BOT_IF_USER_TYPE_BOT_OR_CASEFOLDED_LOGIN_ENDS_WITH_LEFT_BRACKET_BOT_RIGHT_BRACKET"
    )
    pull_output_path: Literal[
        "data/evidence/datasets/s5_bitcoin_core_github_pulls_normalized_v1.jsonl"
    ] = "data/evidence/datasets/s5_bitcoin_core_github_pulls_normalized_v1.jsonl"
    mapping_output_path: Literal[
        "data/evidence/datasets/s5_bitcoin_core_accepted_merge_mapping_v1.jsonl"
    ] = "data/evidence/datasets/s5_bitcoin_core_accepted_merge_mapping_v1.jsonl"
    unresolved_output_path: Literal[
        "data/evidence/datasets/s5_bitcoin_core_unresolved_git_merges_v1.jsonl"
    ] = "data/evidence/datasets/s5_bitcoin_core_unresolved_git_merges_v1.jsonl"
    result_path: Literal[
        "data/evidence/s5_bitcoin_core_github_normalization_result_v1.json"
    ] = "data/evidence/s5_bitcoin_core_github_normalization_result_v1.json"
    normalized_pull_fields: tuple[str, ...] = S5_GITHUB_NORMALIZED_PULL_FIELDS
    merge_mapping_fields: tuple[str, ...] = S5_GITHUB_MERGE_MAPPING_FIELDS
    unresolved_merge_fields: tuple[str, ...] = S5_GITHUB_UNRESOLVED_MERGE_FIELDS
    serialization: Literal[
        "UTF8_JSONL_SORTED_KEYS_COMPACT_SEPARATORS_LF_FINAL_NEWLINE"
    ] = "UTF8_JSONL_SORTED_KEYS_COMPACT_SEPARATORS_LF_FINAL_NEWLINE"
    maximum_local_git_process_count: Literal[1] = 1
    maximum_run_count: Literal[1] = 1
    maximum_elapsed_seconds: Literal[1200] = 1200
    maximum_each_output_bytes: Literal[134217728] = 134_217_728
    result_required_on_every_normal_exit: Literal[True] = True
    rerun_after_result_forbidden: Literal[True] = True
    output_paths_absent_at_freeze: Literal[True] = True
    network_access_permitted: Literal[False] = False
    repository_fetch_permitted: Literal[False] = False
    raw_page_access_permitted_during_execution: Literal[True] = True
    local_git_parent_access_permitted_during_execution: Literal[True] = True
    commit_message_access_permitted: Literal[False] = False
    author_or_committer_header_access_permitted: Literal[False] = False
    git_timestamp_access_permitted: Literal[False] = False
    github_api_requests_permitted: Literal[False] = False
    btc_market_values_permitted: Literal[False] = False
    parameters_permitted: Literal[False] = False
    returns_permitted: Literal[False] = False
    strategy_candidate_permitted: Literal[False] = False
    paper_permitted: Literal[False] = False
    testnet_strategy_orders_permitted: Literal[False] = False
    production_permitted: Literal[False] = False
    live_permitted: Literal[False] = False
    source_page_files_opened_during_freeze: Literal[0] = 0
    response_bodies_decoded_during_freeze: Literal[0] = 0
    local_git_processes_executed_during_freeze: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    required_gate_ids: tuple[str, ...] = Field(min_length=17, max_length=17)
    decision: Literal[
        "FREEZE_S5_GITHUB_METADATA_NORMALIZATION_AND_COMPLETENESS_PROTOCOL"
    ] = S5_GITHUB_NORMALIZATION_PROTOCOL_DECISION
    next_authorization: Literal[
        "AUTHORIZE_S5_GITHUB_NORMALIZATION_EXECUTION_CONTRACT_IMPLEMENTATION_ONLY"
    ] = S5_GITHUB_NORMALIZATION_NEXT
    limitations: tuple[str, ...] = Field(min_length=12)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at", "cohort_created_at_cutoff")
    @classmethod
    def normalize_times(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "source_binding_manifest_evidence_hash",
        "readiness_v34_result_evidence_hash",
        "readiness_v34_audit_evidence_hash",
        "charter_evidence_hash",
        "charter_audit_evidence_hash",
        "history_result_evidence_hash",
        "history_result_audit_evidence_hash",
        "census_result_evidence_hash",
        "census_result_audit_evidence_hash",
        "bulk_protocol_evidence_hash",
        "bulk_protocol_audit_evidence_hash",
        "monotonic_amendment_evidence_hash",
        "monotonic_amendment_audit_evidence_hash",
        "bulk_result_evidence_hash",
        "bulk_final_audit_evidence_hash",
        "history_dataset_directory_sha256",
        "bulk_page_manifest_evidence_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S5GitHubNormalizationProtocol:
        paths = tuple(item.path for item in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 normalization source bindings changed")
        expected_binding_hash = universe_evidence_hash(
            tuple(item.model_dump(mode="json") for item in self.source_bindings)
        )
        if self.source_binding_manifest_evidence_hash != expected_binding_hash:
            raise ValueError("S5 normalization source binding manifest changed")
        if self.required_gate_ids != S5_GITHUB_NORMALIZATION_GATE_IDS:
            raise ValueError("S5 normalization gates changed")
        if self.normalized_pull_fields != S5_GITHUB_NORMALIZED_PULL_FIELDS:
            raise ValueError("S5 normalized pull schema changed")
        if self.merge_mapping_fields != S5_GITHUB_MERGE_MAPPING_FIELDS:
            raise ValueError("S5 merge mapping schema changed")
        if self.unresolved_merge_fields != S5_GITHUB_UNRESOLVED_MERGE_FIELDS:
            raise ValueError("S5 unresolved merge schema changed")
        forbidden_authorities = (
            self.network_access_permitted,
            self.repository_fetch_permitted,
            self.commit_message_access_permitted,
            self.author_or_committer_header_access_permitted,
            self.git_timestamp_access_permitted,
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
        if any(forbidden_authorities):
            raise ValueError("S5 normalization protocol grants forbidden authority")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S5 normalization protocol hash changed")
        return self


class S5GitHubNormalizationProtocolAudit(BaseModel):
    schema_version: Literal["aurex-s5-github-normalization-protocol-audit-v1"] = (
        "aurex-s5-github-normalization-protocol-audit-v1"
    )
    audit_id: Literal["s5-github-normalization-protocol-audit-v1"] = (
        "s5-github-normalization-protocol-audit-v1"
    )
    audited_at: datetime
    protocol_path: Literal[
        "data/evidence/s5_bitcoin_core_github_normalization_protocol_v1.json"
    ] = "data/evidence/s5_bitcoin_core_github_normalization_protocol_v1.json"
    protocol_file_sha256: str
    protocol_evidence_hash: str
    builder_contract_hash: str
    source_binding_manifest_evidence_hash: str
    source_binding_count: Literal[16] = 16
    source_bindings_rehashed: Literal[16] = 16
    expected_page_count: Literal[245] = 245
    expected_cohort_record_count: Literal[24398] = 24_398
    expected_first_parent_commit_count: Literal[17543] = 17_543
    expected_merge_commit_count: Literal[16721] = 16_721
    expected_recognized_pull_merge_count: Literal[7961] = 7_961
    auditor_source_sha256: str
    source_page_files_opened: Literal[0] = 0
    response_bodies_decoded: Literal[0] = 0
    local_git_processes_executed: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    reconstructed_exactly: Literal[True] = True
    decision: Literal["PASS_S5_GITHUB_NORMALIZATION_PROTOCOL_AUDIT"] = (
        "PASS_S5_GITHUB_NORMALIZATION_PROTOCOL_AUDIT"
    )
    next_authorization: Literal[
        "AUTHORIZE_S5_GITHUB_NORMALIZATION_EXECUTION_CONTRACT_IMPLEMENTATION_ONLY"
    ] = S5_GITHUB_NORMALIZATION_NEXT
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
    def validate_audit(self) -> S5GitHubNormalizationProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 normalization protocol audit hash changed")
        return self
