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

S5_TARGETED_CORRECTION_RUN = "RUN_S5_GITHUB_TARGETED_COMPLETENESS_ACQUISITION"
S5_TARGETED_CORRECTION_GATE_IDS = (
    "NORMALIZATION_STOP_AND_FAILURE_ADJUDICATION_LINEAGE_BOUND",
    "EXACT_83_RECOGNIZED_112_UNMATCHED_1_OVERLAP_194_UNION_TARGETS",
    "TARGET_PULL_IDS_AND_REASONS_FROZEN_BEFORE_DIRECT_ACCESS",
    "ONE_CREDENTIAL_FREE_DIRECT_PULL_REQUEST_PER_TARGET_MAXIMUM",
    "HTTP_200_AND_404_RESPONSES_PRESERVED_AS_EVIDENCE",
    "DIRECT_PULL_RESPONSE_SCHEMA_AND_IDENTITY_VALIDATED",
    "EXACT_83_CENSUS_MERGE_COMMIT_FIRST_LINES_ONLY",
    "FULL_REACHABILITY_GRAPH_AND_TARGET_OBJECT_ACCESS_BOUNDED_TO_TWO_GIT_PROCESSES",
    "NO_MAPPING_OR_COMPLETENESS_RULE_CHANGES_DURING_ACQUISITION",
    "RAW_RESPONSE_AND_LOCAL_DIAGNOSTIC_MANIFESTS_RECONSTRUCTABLE",
    "ZERO_MARKET_VALUES_PARAMETERS_RETURNS_CANDIDATES_OR_ORDERS",
)


class S5TargetedCorrectionTarget(BaseModel):
    sequence: int = Field(ge=1, le=194)
    pull_number: int = Field(gt=0)
    target_reasons: tuple[
        Literal["RECOGNIZED_GAP", "UNMATCHED_ACCEPTED_PULL"], ...
    ] = Field(min_length=1, max_length=2)
    recognized_failure_category: str | None
    unmatched_failure_category: str | None
    census_merge_commit_sha: str | None
    census_pattern_id: Literal[
        "BITCOIN_CORE_MAINTAINER_MERGE",
        "GITHUB_DEFAULT_PULL_MERGE",
    ] | None

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("census_merge_commit_sha")
    @classmethod
    def normalize_optional_sha(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError("S5 targeted census merge SHA changed")
        return value

    @model_validator(mode="after")
    def validate_target(self) -> S5TargetedCorrectionTarget:
        if self.target_reasons != tuple(sorted(set(self.target_reasons))):
            raise ValueError("S5 targeted correction reasons changed")
        recognized = "RECOGNIZED_GAP" in self.target_reasons
        unmatched = "UNMATCHED_ACCEPTED_PULL" in self.target_reasons
        if recognized != all(
            value is not None
            for value in (
                self.recognized_failure_category,
                self.census_merge_commit_sha,
                self.census_pattern_id,
            )
        ):
            raise ValueError("S5 recognized correction target identity changed")
        if unmatched != (self.unmatched_failure_category is not None):
            raise ValueError("S5 unmatched correction target identity changed")
        return self


class S5TargetedCompletenessCorrectionProtocol(BaseModel):
    schema_version: Literal[
        "aurex-s5-targeted-completeness-correction-protocol-v1"
    ] = "aurex-s5-targeted-completeness-correction-protocol-v1"
    protocol_id: Literal["s5-targeted-completeness-correction-protocol-v1"] = (
        "s5-targeted-completeness-correction-protocol-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_ACQUISITION_ONLY_ZERO_TARGET_ACCESS"] = (
        "FROZEN_ACQUISITION_ONLY_ZERO_TARGET_ACCESS"
    )
    builder_contract_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=10, max_length=10)
    source_binding_manifest_evidence_hash: str
    normalization_protocol_evidence_hash: str
    failed_normalization_result_evidence_hash: str
    adjudication_protocol_evidence_hash: str
    adjudication_protocol_audit_evidence_hash: str
    adjudication_result_evidence_hash: str
    adjudication_result_audit_evidence_hash: str
    census_result_evidence_hash: str
    census_result_audit_evidence_hash: str
    bulk_protocol_evidence_hash: str
    bulk_result_evidence_hash: str
    recognized_gap_target_count: Literal[83] = 83
    unmatched_pull_target_count: Literal[112] = 112
    overlap_target_count: Literal[1] = 1
    unique_target_count: Literal[194] = 194
    target_manifest: tuple[S5TargetedCorrectionTarget, ...] = Field(
        min_length=194, max_length=194
    )
    target_manifest_evidence_hash: str
    repository_owner: Literal["bitcoin"] = "bitcoin"
    repository_name: Literal["bitcoin"] = "bitcoin"
    direct_pull_endpoint_template: Literal[
        "https://api.github.com/repos/bitcoin/bitcoin/pulls/{pull_number}"
    ] = "https://api.github.com/repos/bitcoin/bitcoin/pulls/{pull_number}"
    method: Literal["GET"] = "GET"
    accept_header: Literal["application/vnd.github+json"] = (
        "application/vnd.github+json"
    )
    api_version_header: Literal["2022-11-28"] = "2022-11-28"
    user_agent: Literal["Aurex-Evidence-Research/1.0"] = (
        "Aurex-Evidence-Research/1.0"
    )
    acceptable_http_statuses: tuple[Literal[200, 404], ...] = (200, 404)
    required_200_fields: tuple[str, ...] = (
        "number",
        "node_id",
        "state",
        "created_at",
        "updated_at",
        "closed_at",
        "merged_at",
        "merged",
        "merge_commit_sha",
        "head.sha",
        "base.ref",
        "base.sha",
        "user",
    )
    raw_response_directory: Literal[
        "data/evidence/s5_github_targeted_pull_responses_v1"
    ] = "data/evidence/s5_github_targeted_pull_responses_v1"
    response_file_pattern: Literal["pull_{pull_number:06d}.json"] = (
        "pull_{pull_number:06d}.json"
    )
    result_path: Literal[
        "data/evidence/s5_bitcoin_core_github_targeted_correction_result_v1.json"
    ] = "data/evidence/s5_bitcoin_core_github_targeted_correction_result_v1.json"
    full_graph_command: Literal[
        "git rev-list --parents <source_cutoff_commit>"
    ] = "git rev-list --parents <source_cutoff_commit>"
    commit_message_command: Literal["git cat-file --batch"] = "git cat-file --batch"
    exact_message_target_count: Literal[83] = 83
    maximum_first_line_characters_persisted: Literal[300] = 300
    maximum_local_git_process_count: Literal[2] = 2
    maximum_github_request_count: Literal[194] = 194
    maximum_response_bytes_per_target: Literal[2097152] = 2_097_152
    maximum_total_response_bytes: Literal[268435456] = 268_435_456
    maximum_elapsed_seconds: Literal[21600] = 21_600
    maximum_run_count: Literal[1] = 1
    resume_valid_responses_permitted: Literal[True] = True
    result_required_on_every_normal_exit: Literal[True] = True
    rerun_after_result_forbidden: Literal[True] = True
    credentials_permitted: Literal[False] = False
    authorization_header_permitted: Literal[False] = False
    environment_proxy_permitted: Literal[False] = False
    redirects_permitted: Literal[False] = False
    concurrency_permitted: Literal[False] = False
    network_access_permitted_during_run: Literal[True] = True
    repository_fetch_permitted: Literal[False] = False
    mapping_rule_change_permitted: Literal[False] = False
    accepted_event_creation_permitted: Literal[False] = False
    btc_market_values_permitted: Literal[False] = False
    parameters_permitted: Literal[False] = False
    returns_permitted: Literal[False] = False
    candidates_permitted: Literal[False] = False
    paper_permitted: Literal[False] = False
    testnet_strategy_orders_permitted: Literal[False] = False
    production_permitted: Literal[False] = False
    live_permitted: Literal[False] = False
    target_responses_opened_during_freeze: Literal[0] = 0
    local_git_processes_executed_during_freeze: Literal[0] = 0
    github_requests_executed_during_freeze: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    required_gate_ids: tuple[str, ...] = Field(min_length=11, max_length=11)
    decision: Literal["FREEZE_S5_GITHUB_TARGETED_COMPLETENESS_CORRECTION_PROTOCOL"] = (
        "FREEZE_S5_GITHUB_TARGETED_COMPLETENESS_CORRECTION_PROTOCOL"
    )
    next_authorization: Literal[
        "RUN_S5_GITHUB_TARGETED_COMPLETENESS_ACQUISITION"
    ] = S5_TARGETED_CORRECTION_RUN
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
        "normalization_protocol_evidence_hash",
        "failed_normalization_result_evidence_hash",
        "adjudication_protocol_evidence_hash",
        "adjudication_protocol_audit_evidence_hash",
        "adjudication_result_evidence_hash",
        "adjudication_result_audit_evidence_hash",
        "census_result_evidence_hash",
        "census_result_audit_evidence_hash",
        "bulk_protocol_evidence_hash",
        "bulk_result_evidence_hash",
        "target_manifest_evidence_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S5TargetedCompletenessCorrectionProtocol:
        paths = tuple(binding.path for binding in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 targeted correction source bindings changed")
        if self.source_binding_manifest_evidence_hash != universe_evidence_hash(
            tuple(binding.model_dump(mode="json") for binding in self.source_bindings)
        ):
            raise ValueError("S5 targeted correction source binding hash changed")
        if tuple(target.sequence for target in self.target_manifest) != tuple(
            range(1, 195)
        ):
            raise ValueError("S5 targeted correction sequence changed")
        numbers = tuple(target.pull_number for target in self.target_manifest)
        if numbers != tuple(sorted(set(numbers))):
            raise ValueError("S5 targeted correction pull targets changed")
        recognized = sum(
            "RECOGNIZED_GAP" in target.target_reasons for target in self.target_manifest
        )
        unmatched = sum(
            "UNMATCHED_ACCEPTED_PULL" in target.target_reasons
            for target in self.target_manifest
        )
        overlap = sum(len(target.target_reasons) == 2 for target in self.target_manifest)
        if (recognized, unmatched, overlap) != (83, 112, 1):
            raise ValueError("S5 targeted correction target accounting changed")
        if self.target_manifest_evidence_hash != universe_evidence_hash(
            tuple(target.model_dump(mode="json") for target in self.target_manifest)
        ):
            raise ValueError("S5 targeted correction target manifest hash changed")
        if self.required_gate_ids != S5_TARGETED_CORRECTION_GATE_IDS:
            raise ValueError("S5 targeted correction gates changed")
        forbidden = (
            self.credentials_permitted,
            self.authorization_header_permitted,
            self.environment_proxy_permitted,
            self.redirects_permitted,
            self.concurrency_permitted,
            self.repository_fetch_permitted,
            self.mapping_rule_change_permitted,
            self.accepted_event_creation_permitted,
            self.btc_market_values_permitted,
            self.parameters_permitted,
            self.returns_permitted,
            self.candidates_permitted,
            self.paper_permitted,
            self.testnet_strategy_orders_permitted,
            self.production_permitted,
            self.live_permitted,
        )
        if any(forbidden):
            raise ValueError("S5 targeted correction grants forbidden authority")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S5 targeted correction protocol hash changed")
        return self


class S5TargetedCompletenessCorrectionProtocolAudit(BaseModel):
    schema_version: Literal[
        "aurex-s5-targeted-completeness-correction-protocol-audit-v1"
    ] = "aurex-s5-targeted-completeness-correction-protocol-audit-v1"
    audit_id: Literal[
        "s5-targeted-completeness-correction-protocol-audit-v1"
    ] = "s5-targeted-completeness-correction-protocol-audit-v1"
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    builder_contract_hash: str
    source_binding_manifest_evidence_hash: str
    target_manifest_evidence_hash: str
    source_binding_count: Literal[10] = 10
    target_count: Literal[194] = 194
    auditor_source_sha256: str
    target_responses_opened: Literal[0] = 0
    local_git_processes_executed: Literal[0] = 0
    github_requests_executed: Literal[0] = 0
    reconstructed_exactly: Literal[True] = True
    decision: Literal["PASS_S5_TARGETED_CORRECTION_PROTOCOL_AUDIT"] = (
        "PASS_S5_TARGETED_CORRECTION_PROTOCOL_AUDIT"
    )
    next_authorization: Literal[
        "RUN_S5_GITHUB_TARGETED_COMPLETENESS_ACQUISITION"
    ] = S5_TARGETED_CORRECTION_RUN
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
        "target_manifest_evidence_hash",
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5TargetedCompletenessCorrectionProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 targeted correction protocol audit hash changed")
        return self
