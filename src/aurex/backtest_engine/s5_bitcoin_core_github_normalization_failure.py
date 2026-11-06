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

S5_NORMALIZATION_FAILURE_ADJUDICATION_RUN = (
    "RUN_S5_NORMALIZATION_FAILURE_ADJUDICATION_ONCE"
)
S5_NORMALIZATION_FAILURE_ADJUDICATION_NEXT = (
    "FREEZE_S5_GITHUB_TARGETED_COMPLETENESS_CORRECTION_PROTOCOL_ONLY"
)
S5_NORMALIZATION_FAILURE_ADJUDICATION_STOP = (
    "STOP_S5_NORMALIZATION_FAILURE_ADJUDICATION_FAILED_RETIRE_S5"
)

S5_RECOGNIZED_FAILURE_CATEGORIES = (
    "EXACT_PRIOR_MAPPING",
    "ABSENT_FROM_MASTER_SCOPED_COHORT",
    "PRESENT_NOT_ACCEPTED_AT_CUTOFF",
    "HEAD_SHA_MISMATCH",
    "AMBIGUOUS_HEAD_SHA",
)

S5_UNMATCHED_PULL_CATEGORIES = (
    "MERGE_COMMIT_SHA_EQUALS_FIRST_PARENT_MERGE",
    "MERGE_COMMIT_SHA_EQUALS_REACHABLE_COMMIT_NOT_FIRST_PARENT_MERGE",
    "HEAD_SHA_REACHABLE_NOT_FIRST_PARENT_SECOND_PARENT",
    "NOT_REACHABLE_AT_SOURCE_CUTOFF",
    "MERGE_COMMIT_SHA_MISSING_OR_INVALID",
    "OTHER_UNRESOLVED",
)

S5_NORMALIZATION_FAILURE_GATE_IDS = (
    "FROZEN_NORMALIZATION_STOP_RESULT_AND_LINEAGE_BOUND",
    "ORIGINAL_13_PASS_4_FAIL_COUNTS_RECONCILE",
    "ORIGINAL_83_RECOGNIZED_112_REVERSE_1_AMBIGUOUS_GAPS_RECONCILE",
    "ALL_245_SOURCE_PAGES_AND_RESPONSE_BODIES_REHASH",
    "ONE_LOCAL_FULL_REACHABILITY_PARENT_COMMAND_ONLY",
    "FIRST_PARENT_TOPOLOGY_RECONSTRUCTS_FROM_FULL_GRAPH",
    "EVERY_RECOGNIZED_REFERENCE_RECEIVES_ONE_FROZEN_CATEGORY",
    "EVERY_UNMATCHED_ACCEPTED_PULL_RECEIVES_ONE_FROZEN_CATEGORY",
    "MERGE_COMMIT_SHA_IS_DIAGNOSTIC_ONLY_AND_NEVER_SILENTLY_SUBSTITUTED",
    "AMBIGUOUS_HEAD_SHA_RECORDS_ARE_PRESERVED_EXACTLY",
    "ZERO_MARKET_VALUES_PARAMETERS_RETURNS_CANDIDATES_OR_ORDERS",
)


class S5NormalizationFailureAdjudicationProtocol(BaseModel):
    schema_version: Literal[
        "aurex-s5-normalization-failure-adjudication-protocol-v1"
    ] = "aurex-s5-normalization-failure-adjudication-protocol-v1"
    protocol_id: Literal["s5-normalization-failure-adjudication-protocol-v1"] = (
        "s5-normalization-failure-adjudication-protocol-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_DIAGNOSTIC_ONLY_ZERO_SOURCE_ROW_ACCESS"] = (
        "FROZEN_DIAGNOSTIC_ONLY_ZERO_SOURCE_ROW_ACCESS"
    )
    builder_contract_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=11, max_length=11)
    source_binding_manifest_evidence_hash: str
    normalization_protocol_evidence_hash: str
    normalization_protocol_audit_evidence_hash: str
    execution_contract_evidence_hash: str
    execution_contract_audit_evidence_hash: str
    failed_result_file_sha256: str
    failed_result_evidence_hash: str
    bulk_result_evidence_hash: str
    bulk_final_audit_evidence_hash: str
    census_result_evidence_hash: str
    census_result_audit_evidence_hash: str
    history_result_evidence_hash: str
    history_result_audit_evidence_hash: str
    original_passed_gate_count: Literal[13] = 13
    original_failed_gate_count: Literal[4] = 4
    original_recognized_pull_merge_count: Literal[7961] = 7_961
    original_recognized_exact_mapping_count: Literal[7878] = 7_878
    original_recognized_gap_count: Literal[83] = 83
    original_accepted_github_pull_count: Literal[16279] = 16_279
    original_total_exact_mapping_count: Literal[16167] = 16_167
    original_unmatched_accepted_pull_count: Literal[112] = 112
    original_ambiguous_git_merge_count: Literal[1] = 1
    original_unresolved_git_merge_count: Literal[554] = 554
    full_graph_command: Literal[
        "git rev-list --parents <source_cutoff_commit>"
    ] = "git rev-list --parents <source_cutoff_commit>"
    diagnostic_github_fields: tuple[str, ...] = (
        "number",
        "state",
        "created_at",
        "closed_at",
        "merged_at",
        "merge_commit_sha",
        "head.sha",
        "base.ref",
    )
    recognized_classification_order: tuple[str, ...] = S5_RECOGNIZED_FAILURE_CATEGORIES
    unmatched_classification_order: tuple[str, ...] = S5_UNMATCHED_PULL_CATEGORIES
    fixed_recent_merge_windows_days: tuple[Literal[1, 7, 30], ...] = (1, 7, 30)
    direct_pull_requests_permitted: Literal[False] = False
    network_access_permitted: Literal[False] = False
    repository_fetch_permitted: Literal[False] = False
    commit_message_access_permitted: Literal[False] = False
    author_or_committer_header_access_permitted: Literal[False] = False
    git_timestamp_access_permitted: Literal[False] = False
    merge_commit_sha_mapping_change_permitted: Literal[False] = False
    normalization_rule_change_permitted: Literal[False] = False
    maximum_local_git_process_count: Literal[1] = 1
    maximum_run_count: Literal[1] = 1
    maximum_elapsed_seconds: Literal[1200] = 1200
    maximum_diagnostic_items_per_category: Literal[250] = 250
    result_path: Literal[
        "data/evidence/s5_bitcoin_core_github_normalization_failure_adjudication_result_v1.json"
    ] = (
        "data/evidence/"
        "s5_bitcoin_core_github_normalization_failure_adjudication_result_v1.json"
    )
    result_was_absent_at_freeze: Literal[True] = True
    source_page_files_opened_during_freeze: Literal[0] = 0
    response_bodies_decoded_during_freeze: Literal[0] = 0
    local_git_processes_executed_during_freeze: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    required_gate_ids: tuple[str, ...] = Field(min_length=11, max_length=11)
    decision: Literal["FREEZE_S5_NORMALIZATION_FAILURE_ADJUDICATION_PROTOCOL"] = (
        "FREEZE_S5_NORMALIZATION_FAILURE_ADJUDICATION_PROTOCOL"
    )
    next_authorization: Literal["RUN_S5_NORMALIZATION_FAILURE_ADJUDICATION_ONCE"] = (
        S5_NORMALIZATION_FAILURE_ADJUDICATION_RUN
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
        "source_binding_manifest_evidence_hash",
        "normalization_protocol_evidence_hash",
        "normalization_protocol_audit_evidence_hash",
        "execution_contract_evidence_hash",
        "execution_contract_audit_evidence_hash",
        "failed_result_file_sha256",
        "failed_result_evidence_hash",
        "bulk_result_evidence_hash",
        "bulk_final_audit_evidence_hash",
        "census_result_evidence_hash",
        "census_result_audit_evidence_hash",
        "history_result_evidence_hash",
        "history_result_audit_evidence_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S5NormalizationFailureAdjudicationProtocol:
        paths = tuple(binding.path for binding in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 failure adjudication bindings changed")
        expected_binding_hash = universe_evidence_hash(
            tuple(binding.model_dump(mode="json") for binding in self.source_bindings)
        )
        if self.source_binding_manifest_evidence_hash != expected_binding_hash:
            raise ValueError("S5 failure adjudication binding hash changed")
        if self.required_gate_ids != S5_NORMALIZATION_FAILURE_GATE_IDS:
            raise ValueError("S5 failure adjudication gates changed")
        if self.recognized_classification_order != S5_RECOGNIZED_FAILURE_CATEGORIES:
            raise ValueError("S5 recognized diagnostic categories changed")
        if self.unmatched_classification_order != S5_UNMATCHED_PULL_CATEGORIES:
            raise ValueError("S5 unmatched diagnostic categories changed")
        forbidden = (
            self.direct_pull_requests_permitted,
            self.network_access_permitted,
            self.repository_fetch_permitted,
            self.commit_message_access_permitted,
            self.author_or_committer_header_access_permitted,
            self.git_timestamp_access_permitted,
            self.merge_commit_sha_mapping_change_permitted,
            self.normalization_rule_change_permitted,
        )
        if any(forbidden):
            raise ValueError("S5 failure adjudication grants corrective authority")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S5 failure adjudication protocol hash changed")
        return self


class S5NormalizationFailureAdjudicationProtocolAudit(BaseModel):
    schema_version: Literal[
        "aurex-s5-normalization-failure-adjudication-protocol-audit-v1"
    ] = "aurex-s5-normalization-failure-adjudication-protocol-audit-v1"
    audit_id: Literal[
        "s5-normalization-failure-adjudication-protocol-audit-v1"
    ] = "s5-normalization-failure-adjudication-protocol-audit-v1"
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    builder_contract_hash: str
    source_binding_manifest_evidence_hash: str
    source_binding_count: Literal[11] = 11
    source_bindings_rehashed: Literal[11] = 11
    auditor_source_sha256: str
    source_page_files_opened: Literal[0] = 0
    response_bodies_decoded: Literal[0] = 0
    local_git_processes_executed: Literal[0] = 0
    reconstructed_exactly: Literal[True] = True
    decision: Literal["PASS_S5_NORMALIZATION_FAILURE_PROTOCOL_AUDIT"] = (
        "PASS_S5_NORMALIZATION_FAILURE_PROTOCOL_AUDIT"
    )
    next_authorization: Literal["RUN_S5_NORMALIZATION_FAILURE_ADJUDICATION_ONCE"] = (
        S5_NORMALIZATION_FAILURE_ADJUDICATION_RUN
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
        "source_binding_manifest_evidence_hash",
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5NormalizationFailureAdjudicationProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 failure adjudication audit hash changed")
        return self


class S5FailureCategoryRecord(BaseModel):
    category: str = Field(min_length=1)
    count: int = Field(ge=0)
    pull_numbers: tuple[int, ...] = Field(max_length=250)
    evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("evidence_hash")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_record(self) -> S5FailureCategoryRecord:
        if self.pull_numbers != tuple(sorted(set(self.pull_numbers))):
            raise ValueError("S5 diagnostic pull numbers changed")
        if self.count < len(self.pull_numbers):
            raise ValueError("S5 diagnostic sample exceeds category count")
        return self


class S5NormalizationFailureAdjudicationResult(BaseModel):
    schema_version: Literal[
        "aurex-s5-normalization-failure-adjudication-result-v1"
    ] = "aurex-s5-normalization-failure-adjudication-result-v1"
    result_id: Literal["s5-normalization-failure-adjudication-result-v1"] = (
        "s5-normalization-failure-adjudication-result-v1"
    )
    completed_at: datetime
    protocol_evidence_hash: str
    protocol_audit_evidence_hash: str
    runner_contract_hash: str
    failed_result_evidence_hash: str
    history_dataset_directory_sha256: str
    full_graph_commit_count: int = Field(ge=0)
    first_parent_commit_count: int = Field(ge=0)
    first_parent_merge_count: int = Field(ge=0)
    source_page_files_opened: int = Field(ge=0, le=245)
    response_bodies_decoded: int = Field(ge=0, le=245)
    local_git_process_count: int = Field(ge=0, le=1)
    reconstructed_recognized_exact_count: int = Field(ge=0, le=7_961)
    reconstructed_recognized_gap_count: int = Field(ge=0, le=83)
    reconstructed_unmatched_accepted_pull_count: int = Field(ge=0, le=112)
    reconstructed_ambiguous_count: int = Field(ge=0, le=1)
    recognized_categories: tuple[S5FailureCategoryRecord, ...] = Field(
        min_length=5, max_length=5
    )
    unmatched_categories: tuple[S5FailureCategoryRecord, ...] = Field(
        min_length=6, max_length=6
    )
    unmatched_merged_within_1_day_of_cutoff: int = Field(ge=0, le=112)
    unmatched_merged_within_7_days_of_cutoff: int = Field(ge=0, le=112)
    unmatched_merged_within_30_days_of_cutoff: int = Field(ge=0, le=112)
    exact_merge_commit_recovery_count: int = Field(ge=0, le=112)
    master_scoped_recognized_absence_count: int = Field(ge=0, le=83)
    structurally_unexplained_count: int = Field(ge=0, le=195)
    gate_results: tuple[dict[str, str], ...] = Field(min_length=11, max_length=11)
    passed_gate_count: int = Field(ge=0, le=11)
    failed_gate_count: int = Field(ge=0, le=11)
    btc_market_values_read: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    original_stop_upheld: Literal[True] = True
    correction_not_yet_authorized: Literal[True] = True
    decision: Literal[
        "PASS_S5_NORMALIZATION_FAILURE_ADJUDICATION",
        "STOP_S5_NORMALIZATION_FAILURE_ADJUDICATION_FAILED_RETIRE_S5",
    ]
    next_authorization: Literal[
        "FREEZE_S5_GITHUB_TARGETED_COMPLETENESS_CORRECTION_PROTOCOL_ONLY",
        "NONE_RETIRE_S5",
    ]
    failure_type: str | None
    failure_message: str | None
    limitations: tuple[str, ...] = Field(min_length=10)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("completed_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_evidence_hash",
        "protocol_audit_evidence_hash",
        "runner_contract_hash",
        "failed_result_evidence_hash",
        "history_dataset_directory_sha256",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> S5NormalizationFailureAdjudicationResult:
        if tuple(row.category for row in self.recognized_categories) != (
            S5_RECOGNIZED_FAILURE_CATEGORIES
        ):
            raise ValueError("S5 recognized result categories changed")
        if tuple(row.category for row in self.unmatched_categories) != (
            S5_UNMATCHED_PULL_CATEGORIES
        ):
            raise ValueError("S5 unmatched result categories changed")
        if sum(row.count for row in self.recognized_categories) != 7_961:
            raise ValueError("S5 recognized category accounting changed")
        if sum(row.count for row in self.unmatched_categories) != 112:
            raise ValueError("S5 unmatched category accounting changed")
        passed = sum(row.get("status") == "PASS" for row in self.gate_results)
        failed = len(self.gate_results) - passed
        if (self.passed_gate_count, self.failed_gate_count) != (passed, failed):
            raise ValueError("S5 failure adjudication gate accounting changed")
        successful = failed == 0
        if successful != (
            self.decision == "PASS_S5_NORMALIZATION_FAILURE_ADJUDICATION"
            and self.next_authorization
            == S5_NORMALIZATION_FAILURE_ADJUDICATION_NEXT
            and self.failure_type is None
            and self.failure_message is None
        ):
            raise ValueError("S5 failure adjudication decision changed")
        if not successful and (
            self.decision != S5_NORMALIZATION_FAILURE_ADJUDICATION_STOP
            or self.next_authorization != "NONE_RETIRE_S5"
            or not self.failure_type
            or not self.failure_message
        ):
            raise ValueError("Failed S5 adjudication must retire S5")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("S5 failure adjudication result hash changed")
        return self
