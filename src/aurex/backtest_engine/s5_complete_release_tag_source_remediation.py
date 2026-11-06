from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s5_bitcoin_core_history_payload import S5HistoryBinding
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S5_COMPLETE_RELEASE_REMEDIATION_DECISION = (
    "FREEZE_S5_COMPLETE_RELEASE_TAG_SOURCE_REMEDIATION_PROTOCOL"
)
S5_COMPLETE_RELEASE_REMEDIATION_AUDIT_DECISION = (
    "PASS_S5_COMPLETE_RELEASE_TAG_SOURCE_REMEDIATION_PROTOCOL_AUDIT"
)
S5_COMPLETE_RELEASE_REMEDIATION_NEXT = (
    "AUTHORIZE_S5_COMPLETE_RELEASE_TAG_SOURCE_REMEDIATION_RUNNER_IMPLEMENTATION_ONLY"
)

S5_COMPLETE_RELEASE_REMEDIATION_GATES = (
    "PRIOR_REMEDIATION_REJECTION_LINEAGE_IS_HASH_BOUND",
    "FOUR_PRIOR_PROCESS_TRANSCRIPTS_ARE_HASH_BOUND",
    "FROZEN_DISCOVERY_CONTAINS_132_EXACT_STABLE_BASE_REFS",
    "ALL_104_ANNOTATED_STABLE_REFS_ARE_INCLUDED_REGARDLESS_OF_MASTER_ANCESTRY",
    "ALL_28_LIGHTWEIGHT_STABLE_REFS_REMAIN_CUTOFF_REACHABLE",
    "COMPLETE_132_TAG_OBJECT_AND_PEELED_IDENTITY_MANIFEST_IS_FROZEN",
    "ORIGINAL_AND_42_TAG_REPOSITORIES_REMAIN_IMMUTABLE",
    "NEW_COMPLETE_DESTINATION_AND_TRANSCRIPT_PATHS_ARE_REQUIRED",
    "OFFICIAL_BITCOIN_CORE_HTTPS_REMOTE_IS_EXACT",
    "NO_NEW_REMOTE_DISCOVERY_IS_PERMITTED",
    "ONE_EXACT_SORTED_132_REFSPEC_FETCH_PROCESS_ONLY",
    "ONE_LOCAL_132_TAG_IDENTITY_VERIFICATION_PROCESS_ONLY",
    "ANNOTATED_TAGGER_TIME_CUTOFF_IS_DEFERRED_TO_AMENDED_MEASUREMENT",
    "LIGHTWEIGHT_COMMITTER_TIME_UNCERTAINTY_IS_PRESERVED",
    "ALL_PROCESS_TRANSCRIPTS_ARE_ATOMIC_AND_HASH_PRESERVED",
    "ANY_DRIFT_TIMEOUT_LIMIT_OR_COPY_MISMATCH_STOPS_THE_RUN",
    "ZERO_MARKET_VALUES_RETURNS_PARAMETERS_CANDIDATES_SIGNALS_OR_ORDERS",
    "PASS_AUTHORIZES_AMENDED_MEASUREMENT_PROTOCOL_ONLY",
)


class S5CompleteReleaseTagSourceRemediationProtocolV1(BaseModel):
    schema_version: Literal[
        "aurex-s5-complete-release-tag-source-remediation-protocol-v1"
    ] = "aurex-s5-complete-release-tag-source-remediation-protocol-v1"
    protocol_id: Literal[
        "s5-complete-release-tag-source-remediation-protocol-v1"
    ] = "s5-complete-release-tag-source-remediation-protocol-v1"
    frozen_at: datetime
    status: Literal[
        "FROZEN_BEFORE_COMPLETE_COPY_FETCH_VERIFICATION_OR_MARKET_ACCESS"
    ] = "FROZEN_BEFORE_COMPLETE_COPY_FETCH_VERIFICATION_OR_MARKET_ACCESS"
    builder_contract_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=10, max_length=10)
    source_binding_manifest_evidence_hash: str
    prior_protocol_evidence_hash: str
    prior_protocol_audit_evidence_hash: str
    prior_execution_contract_evidence_hash: str
    prior_execution_contract_audit_evidence_hash: str
    prior_result_evidence_hash: str
    prior_result_audit_evidence_hash: str
    prior_result_audit_decision: Literal[
        "REJECT_S5_RELEASE_TAG_SOURCE_REMEDIATION_PASS_INCOMPLETE_RELEASE_COVERAGE"
    ] = "REJECT_S5_RELEASE_TAG_SOURCE_REMEDIATION_PASS_INCOMPLETE_RELEASE_COVERAGE"
    original_history_dataset_path: Literal[
        "data/evidence/s5_bitcoin_core_history_payload_v1.git"
    ] = "data/evidence/s5_bitcoin_core_history_payload_v1.git"
    original_history_dataset_directory_sha256: Literal[
        "02a3ca331a09dd2d94732968edf554ccdf927ed0042e56cf229d3a3a015c0a90"
    ] = "02a3ca331a09dd2d94732968edf554ccdf927ed0042e56cf229d3a3a015c0a90"
    incomplete_release_dataset_path: Literal[
        "data/evidence/s5_bitcoin_core_release_tags_v1.git"
    ] = "data/evidence/s5_bitcoin_core_release_tags_v1.git"
    incomplete_release_dataset_directory_sha256: Literal[
        "6e7cd0a147cb9ae26237fa1e4bac6b13c2c52295b264ed0f543d0d626b99e7e4"
    ] = "6e7cd0a147cb9ae26237fa1e4bac6b13c2c52295b264ed0f543d0d626b99e7e4"
    frozen_discovery_transcript_path: Literal[
        "data/evidence/s5_release_tag_source_responses_v1/01_ls_remote_tags.json"
    ] = "data/evidence/s5_release_tag_source_responses_v1/01_ls_remote_tags.json"
    frozen_discovery_transcript_file_sha256: str
    frozen_discovery_transcript_evidence_hash: str
    frozen_reachability_transcript_path: Literal[
        "data/evidence/s5_release_tag_source_responses_v1/02_reachable_commits.json"
    ] = "data/evidence/s5_release_tag_source_responses_v1/02_reachable_commits.json"
    frozen_reachability_transcript_file_sha256: str
    frozen_reachability_transcript_evidence_hash: str
    source_cutoff_commit: Literal[
        "dc0395c5858a1d55239b82a834e5075cf2069219"
    ] = "dc0395c5858a1d55239b82a834e5075cf2069219"
    source_cutoff_reachable_commit_count: Literal[50_395] = 50_395
    official_remote_url: Literal[
        "https://github.com/bitcoin/bitcoin.git"
    ] = "https://github.com/bitcoin/bitcoin.git"
    stable_release_tag_regex: Literal[
        r"^refs/tags/v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))?$"
    ] = (
        r"^refs/tags/v(?:0|[1-9][0-9]*)\."
        r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))?$"
    )
    frozen_remote_tag_ref_record_count: Literal[691] = 691
    complete_stable_tag_count: Literal[132] = 132
    complete_annotated_tag_count: Literal[104] = 104
    complete_lightweight_tag_count: Literal[28] = 28
    prior_admitted_stable_tag_count: Literal[42] = 42
    prior_omitted_annotated_tag_count: Literal[90] = 90
    complete_stable_tag_manifest_evidence_hash: Literal[
        "07d4b9d80266710faf9dcf578a6835c6d1c36727b362132b896c725811eea82c"
    ] = "07d4b9d80266710faf9dcf578a6835c6d1c36727b362132b896c725811eea82c"
    annotated_inclusion_policy: Literal[
        "EXACT_STABLE_BASE_AND_PEELED_REF_INCLUDED_WITHOUT_MASTER_ANCESTRY_FILTER"
    ] = "EXACT_STABLE_BASE_AND_PEELED_REF_INCLUDED_WITHOUT_MASTER_ANCESTRY_FILTER"
    lightweight_inclusion_policy: Literal[
        "EXACT_STABLE_BASE_OBJECT_MUST_REMAIN_REACHABLE_FROM_FROZEN_CUTOFF"
    ] = "EXACT_STABLE_BASE_OBJECT_MUST_REMAIN_REACHABLE_FROM_FROZEN_CUTOFF"
    measurement_period_end_exclusive: date = date(2026, 9, 1)
    annotated_measurement_time_policy: Literal[
        "ANNOTATED_TAGGER_AT_MUST_BE_BEFORE_MEASUREMENT_END_EXCLUSIVE"
    ] = "ANNOTATED_TAGGER_AT_MUST_BE_BEFORE_MEASUREMENT_END_EXCLUSIVE"
    lightweight_measurement_time_policy: Literal[
        "PEELED_COMMIT_COMMITTER_AT_WITH_HISTORICAL_TAG_EXISTENCE_UNCERTAINTY"
    ] = "PEELED_COMMIT_COMMITTER_AT_WITH_HISTORICAL_TAG_EXISTENCE_UNCERTAINTY"
    measurement_time_filtering_permitted_during_remediation: Literal[False] = False
    destination_history_dataset_path: Literal[
        "data/evidence/s5_bitcoin_core_release_tags_complete_v2.git"
    ] = "data/evidence/s5_bitcoin_core_release_tags_complete_v2.git"
    destination_copy_policy: Literal[
        "COPY_42_TAG_REPOSITORY_EXACTLY_THEN_VERIFY_PRE_FETCH_DIRECTORY_HASH"
    ] = "COPY_42_TAG_REPOSITORY_EXACTLY_THEN_VERIFY_PRE_FETCH_DIRECTORY_HASH"
    destination_overwrite_permitted: Literal[False] = False
    fetch_command_prefix: tuple[str, ...] = (
        "git",
        "-C",
        "{destination_history_dataset_path}",
        "fetch",
        "--no-tags",
        "--no-write-fetch-head",
        "--filter=blob:none",
        "https://github.com/bitcoin/bitcoin.git",
    )
    fetch_refspec_policy: Literal[
        "ALL_132_PLUS_REMOTE_STABLE_REF_COLON_IDENTICAL_LOCAL_REF_SORTED_BY_REF_NAME"
    ] = "ALL_132_PLUS_REMOTE_STABLE_REF_COLON_IDENTICAL_LOCAL_REF_SORTED_BY_REF_NAME"
    verification_command: tuple[str, ...] = (
        "git",
        "-C",
        "{destination_history_dataset_path}",
        "for-each-ref",
        "--format=%(refname)%00%(objecttype)%00%(objectname)%00%(*objectname)%00%1e",
        "refs/tags",
    )
    maximum_selected_stable_tag_refs: Literal[132] = 132
    expected_local_git_process_count: Literal[1] = 1
    expected_network_git_process_count: Literal[1] = 1
    maximum_total_git_process_count: Literal[2] = 2
    maximum_process_seconds: Literal[600] = 600
    maximum_total_seconds: Literal[1_200] = 1_200
    maximum_single_stdout_bytes: Literal[16_777_216] = 16_777_216
    maximum_destination_growth_bytes: Literal[536_870_912] = 536_870_912
    environment_proxy_use_permitted: Literal[False] = False
    credential_helper_use_permitted: Literal[False] = False
    token_environment_access_permitted: Literal[False] = False
    transcript_directory: Literal[
        "data/evidence/s5_complete_release_tag_source_responses_v1"
    ] = "data/evidence/s5_complete_release_tag_source_responses_v1"
    fetch_transcript_path: Literal[
        "data/evidence/s5_complete_release_tag_source_responses_v1/01_fetch_all_stable_tags.json"
    ] = "data/evidence/s5_complete_release_tag_source_responses_v1/01_fetch_all_stable_tags.json"
    verification_transcript_path: Literal[
        "data/evidence/s5_complete_release_tag_source_responses_v1/02_verify_all_stable_tags.json"
    ] = "data/evidence/s5_complete_release_tag_source_responses_v1/02_verify_all_stable_tags.json"
    result_path: Literal[
        "data/evidence/s5_complete_release_tag_source_remediation_result_v1.json"
    ] = "data/evidence/s5_complete_release_tag_source_remediation_result_v1.json"
    required_gate_ids: tuple[str, ...] = Field(min_length=18, max_length=18)
    remote_discovery_processes_executed_during_freeze: Literal[0] = 0
    repository_copies_executed_during_freeze: Literal[0] = 0
    fetch_processes_executed_during_freeze: Literal[0] = 0
    network_requests_executed_during_freeze: Literal[0] = 0
    market_values_read_during_freeze: Literal[0] = 0
    returns_calculated_during_freeze: Literal[0] = 0
    parameters_defined: tuple[str, ...] = ()
    strategy_rules_defined: tuple[str, ...] = ()
    authorizes_runner_implementation: Literal[True] = True
    authorizes_complete_tag_fetch_now: Literal[False] = False
    authorizes_repository_copy_now: Literal[False] = False
    authorizes_original_repository_mutation: Literal[False] = False
    authorizes_incomplete_repository_mutation: Literal[False] = False
    authorizes_market_value_access: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
    authorizes_strategy_candidate: Literal[False] = False
    authorizes_signal_generation: Literal[False] = False
    authorizes_pine: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    decision: Literal[
        "FREEZE_S5_COMPLETE_RELEASE_TAG_SOURCE_REMEDIATION_PROTOCOL"
    ] = S5_COMPLETE_RELEASE_REMEDIATION_DECISION
    next_authorization: Literal[
        "AUTHORIZE_S5_COMPLETE_RELEASE_TAG_SOURCE_REMEDIATION_RUNNER_IMPLEMENTATION_ONLY"
    ] = S5_COMPLETE_RELEASE_REMEDIATION_NEXT
    limitations: tuple[str, ...] = Field(min_length=11)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "source_binding_manifest_evidence_hash",
        "prior_protocol_evidence_hash",
        "prior_protocol_audit_evidence_hash",
        "prior_execution_contract_evidence_hash",
        "prior_execution_contract_audit_evidence_hash",
        "prior_result_evidence_hash",
        "prior_result_audit_evidence_hash",
        "frozen_discovery_transcript_file_sha256",
        "frozen_discovery_transcript_evidence_hash",
        "frozen_reachability_transcript_file_sha256",
        "frozen_reachability_transcript_evidence_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S5CompleteReleaseTagSourceRemediationProtocolV1:
        paths = tuple(item.path for item in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 complete release source bindings changed")
        if self.source_binding_manifest_evidence_hash != universe_evidence_hash(
            tuple(item.model_dump(mode="json") for item in self.source_bindings)
        ):
            raise ValueError("S5 complete release source manifest changed")
        if self.required_gate_ids != S5_COMPLETE_RELEASE_REMEDIATION_GATES:
            raise ValueError("S5 complete release gates changed")
        if (
            self.complete_annotated_tag_count + self.complete_lightweight_tag_count
            != self.complete_stable_tag_count
            or self.prior_admitted_stable_tag_count
            + self.prior_omitted_annotated_tag_count
            != self.complete_stable_tag_count
            or self.maximum_selected_stable_tag_refs != self.complete_stable_tag_count
            or self.expected_local_git_process_count
            + self.expected_network_git_process_count
            != self.maximum_total_git_process_count
        ):
            raise ValueError("S5 complete release accounting changed")
        if self.measurement_period_end_exclusive != date(2026, 9, 1):
            raise ValueError("S5 complete release measurement boundary changed")
        if len(set(self.fetch_command_prefix)) != len(self.fetch_command_prefix):
            raise ValueError("S5 complete release fetch command changed")
        if (
            self.destination_history_dataset_path
            in {
                self.original_history_dataset_path,
                self.incomplete_release_dataset_path,
            }
            or self.parameters_defined
            or self.strategy_rules_defined
        ):
            raise ValueError("S5 complete release authority changed")
        if self.limitations != tuple(sorted(set(self.limitations))):
            raise ValueError("S5 complete release limitations changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected_hash:
            raise ValueError("S5 complete release protocol hash changed")
        return self


class S5CompleteReleaseTagSourceRemediationProtocolAuditV1(BaseModel):
    schema_version: Literal[
        "aurex-s5-complete-release-tag-source-remediation-protocol-audit-v1"
    ] = "aurex-s5-complete-release-tag-source-remediation-protocol-audit-v1"
    audit_id: Literal[
        "s5-complete-release-tag-source-remediation-protocol-audit-v1"
    ] = "s5-complete-release-tag-source-remediation-protocol-audit-v1"
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    builder_contract_hash: str
    auditor_implementation_bindings: tuple[S5HistoryBinding, ...] = Field(
        min_length=2,
        max_length=2,
    )
    auditor_contract_hash: str
    source_binding_manifest_evidence_hash: str
    prior_result_audit_evidence_hash: str
    source_binding_count: Literal[10] = 10
    complete_stable_tag_count: Literal[132] = 132
    complete_tag_manifest_evidence_hash: Literal[
        "07d4b9d80266710faf9dcf578a6835c6d1c36727b362132b896c725811eea82c"
    ] = "07d4b9d80266710faf9dcf578a6835c6d1c36727b362132b896c725811eea82c"
    protocol_reconstructed_exactly: Literal[True] = True
    git_processes_executed: Literal[0] = 0
    repository_copies_executed: Literal[0] = 0
    network_requests_executed: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    signals_created: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal[
        "PASS_S5_COMPLETE_RELEASE_TAG_SOURCE_REMEDIATION_PROTOCOL_AUDIT"
    ] = S5_COMPLETE_RELEASE_REMEDIATION_AUDIT_DECISION
    next_authorization: Literal[
        "AUTHORIZE_S5_COMPLETE_RELEASE_TAG_SOURCE_REMEDIATION_RUNNER_IMPLEMENTATION_ONLY"
    ] = S5_COMPLETE_RELEASE_REMEDIATION_NEXT
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
        "source_binding_manifest_evidence_hash",
        "prior_result_audit_evidence_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5CompleteReleaseTagSourceRemediationProtocolAuditV1:
        paths = tuple(item.path for item in self.auditor_implementation_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 complete release auditor bindings changed")
        if self.auditor_contract_hash != universe_evidence_hash(
            tuple(
                item.model_dump(mode="json")
                for item in self.auditor_implementation_bindings
            )
        ):
            raise ValueError("S5 complete release auditor contract changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected_hash:
            raise ValueError("S5 complete release audit hash changed")
        return self
