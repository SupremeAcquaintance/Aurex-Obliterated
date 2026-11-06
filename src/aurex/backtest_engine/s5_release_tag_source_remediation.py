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

S5_RELEASE_REMEDIATION_DECISION = "FREEZE_S5_RELEASE_TAG_SOURCE_REMEDIATION_PROTOCOL"
S5_RELEASE_REMEDIATION_AUDIT_DECISION = (
    "PASS_S5_RELEASE_TAG_SOURCE_REMEDIATION_PROTOCOL_AUDIT"
)
S5_RELEASE_REMEDIATION_NEXT = (
    "AUTHORIZE_S5_RELEASE_TAG_SOURCE_REMEDIATION_RUNNER_IMPLEMENTATION_ONLY"
)

S5_RELEASE_REMEDIATION_GATES = (
    "ALL_ELEVEN_SOURCE_BINDINGS_MATCH",
    "MEASUREMENT_RESULT_REJECTION_AUDIT_IS_VALID_AND_TERMINAL",
    "ORIGINAL_NO_TAGS_REPOSITORY_HASH_CONFIG_AND_PACKED_REFS_MATCH",
    "ORIGINAL_EVIDENCE_REPOSITORY_IS_NEVER_MUTATED",
    "DESTINATION_REPOSITORY_AND_TRANSCRIPT_PATHS_ARE_NEW",
    "OFFICIAL_BITCOIN_CORE_HTTPS_REMOTE_IS_EXACT",
    "REMOTE_TAG_DISCOVERY_IS_CREDENTIAL_FREE_AND_BYTE_BOUNDED",
    "ONLY_EXACT_STABLE_TAG_NAMES_ARE_ELIGIBLE",
    "ANNOTATED_AND_LIGHTWEIGHT_TAG_IDENTITIES_ARE_UNAMBIGUOUS",
    "PEELED_RELEASE_COMMIT_MUST_BE_REACHABLE_FROM_FROZEN_CUTOFF",
    "AT_MOST_500_EXACT_TAG_REFS_CAN_BE_FETCHED",
    "FETCHED_TAG_OBJECT_IDS_MUST_MATCH_DISCOVERY_EXACTLY",
    "ALL_NETWORK_AND_GIT_TRANSCRIPTS_ARE_HASH_PRESERVED",
    "ANY_REF_DRIFT_SCHEMA_LIMIT_TIMEOUT_OR_COPY_MISMATCH_STOPS_THE_RUN",
    "ZERO_MARKET_VALUES_RETURNS_PARAMETERS_CANDIDATES_SIGNALS_OR_ORDERS",
    "PASS_AUTHORIZES_AMENDED_MEASUREMENT_PROTOCOL_ONLY",
)


class S5ReleaseTagSourceRemediationProtocolV1(BaseModel):
    schema_version: Literal[
        "aurex-s5-release-tag-source-remediation-protocol-v1"
    ] = "aurex-s5-release-tag-source-remediation-protocol-v1"
    protocol_id: Literal[
        "s5-release-tag-source-remediation-protocol-v1"
    ] = "s5-release-tag-source-remediation-protocol-v1"
    frozen_at: datetime
    status: Literal[
        "FROZEN_BEFORE_RELEASE_TAG_DISCOVERY_COPY_FETCH_OR_MARKET_ACCESS"
    ] = "FROZEN_BEFORE_RELEASE_TAG_DISCOVERY_COPY_FETCH_OR_MARKET_ACCESS"
    builder_contract_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=11, max_length=11)
    source_binding_manifest_evidence_hash: str
    rejected_measurement_result_evidence_hash: str
    rejection_audit_evidence_hash: str
    rejection_decision: Literal[
        "REJECT_S5_MEASUREMENT_PASS_RELEASE_TAG_SOURCE_ABSENT"
    ] = "REJECT_S5_MEASUREMENT_PASS_RELEASE_TAG_SOURCE_ABSENT"
    original_history_dataset_path: Literal[
        "data/evidence/s5_bitcoin_core_history_payload_v1.git"
    ] = "data/evidence/s5_bitcoin_core_history_payload_v1.git"
    original_history_dataset_directory_sha256: Literal[
        "02a3ca331a09dd2d94732968edf554ccdf927ed0042e56cf229d3a3a015c0a90"
    ] = "02a3ca331a09dd2d94732968edf554ccdf927ed0042e56cf229d3a3a015c0a90"
    original_repository_config_file_sha256: str
    original_repository_packed_refs_file_sha256: str
    original_tag_opt_no_tags_observed: Literal[True] = True
    original_tag_ref_count: Literal[0] = 0
    source_cutoff_commit: Literal[
        "dc0395c5858a1d55239b82a834e5075cf2069219"
    ] = "dc0395c5858a1d55239b82a834e5075cf2069219"
    official_remote_url: Literal["https://github.com/bitcoin/bitcoin.git"] = (
        "https://github.com/bitcoin/bitcoin.git"
    )
    stable_release_tag_regex: Literal[
        r"^refs/tags/v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))?$"
    ] = r"^refs/tags/v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))?$"
    destination_history_dataset_path: Literal[
        "data/evidence/s5_bitcoin_core_release_tags_v1.git"
    ] = "data/evidence/s5_bitcoin_core_release_tags_v1.git"
    destination_copy_policy: Literal[
        "COPY_ORIGINAL_DIRECTORY_EXACTLY_THEN_VERIFY_PRE_FETCH_DIRECTORY_HASH"
    ] = "COPY_ORIGINAL_DIRECTORY_EXACTLY_THEN_VERIFY_PRE_FETCH_DIRECTORY_HASH"
    destination_overwrite_permitted: Literal[False] = False
    discovery_command: tuple[str, ...] = (
        "git",
        "ls-remote",
        "--tags",
        "--sort=refname",
        "https://github.com/bitcoin/bitcoin.git",
    )
    reachable_commit_command: tuple[str, ...] = (
        "git",
        "-C",
        "{original_history_dataset_path}",
        "rev-list",
        "--topo-order",
        "{source_cutoff_commit}",
    )
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
        "PLUS_REMOTE_STABLE_REF_COLON_IDENTICAL_LOCAL_REF_SORTED_BY_REF_NAME"
    ] = "PLUS_REMOTE_STABLE_REF_COLON_IDENTICAL_LOCAL_REF_SORTED_BY_REF_NAME"
    verification_command: tuple[str, ...] = (
        "git",
        "-C",
        "{destination_history_dataset_path}",
        "for-each-ref",
        "--format=%(refname)%00%(objecttype)%00%(objectname)%00%(*objectname)%00%1e",
        "refs/tags",
    )
    annotated_tag_discovery_policy: Literal[
        "BASE_REF_OBJECT_AND_EXACT_CARET_BRACE_PEELED_COMMIT_REQUIRED"
    ] = "BASE_REF_OBJECT_AND_EXACT_CARET_BRACE_PEELED_COMMIT_REQUIRED"
    lightweight_tag_discovery_policy: Literal[
        "SINGLE_BASE_REF_OBJECT_MUST_BE_REACHABLE_COMMIT"
    ] = "SINGLE_BASE_REF_OBJECT_MUST_BE_REACHABLE_COMMIT"
    remote_ref_drift_policy: Literal["REJECT_RUN_AND_PRESERVE_TRANSCRIPTS"] = (
        "REJECT_RUN_AND_PRESERVE_TRANSCRIPTS"
    )
    maximum_selected_stable_tag_refs: Literal[500] = 500
    expected_local_git_process_count: Literal[2] = 2
    expected_network_git_process_count: Literal[2] = 2
    maximum_total_git_process_count: Literal[4] = 4
    maximum_process_seconds: Literal[600] = 600
    maximum_total_seconds: Literal[1_800] = 1_800
    maximum_single_stdout_bytes: Literal[16_777_216] = 16_777_216
    maximum_destination_growth_bytes: Literal[536_870_912] = 536_870_912
    environment_proxy_use_permitted: Literal[False] = False
    credential_helper_use_permitted: Literal[False] = False
    token_environment_access_permitted: Literal[False] = False
    transcript_directory: Literal[
        "data/evidence/s5_release_tag_source_responses_v1"
    ] = "data/evidence/s5_release_tag_source_responses_v1"
    discovery_transcript_path: Literal[
        "data/evidence/s5_release_tag_source_responses_v1/01_ls_remote_tags.json"
    ] = "data/evidence/s5_release_tag_source_responses_v1/01_ls_remote_tags.json"
    reachability_transcript_path: Literal[
        "data/evidence/s5_release_tag_source_responses_v1/02_reachable_commits.json"
    ] = "data/evidence/s5_release_tag_source_responses_v1/02_reachable_commits.json"
    fetch_transcript_path: Literal[
        "data/evidence/s5_release_tag_source_responses_v1/03_fetch_tags.json"
    ] = "data/evidence/s5_release_tag_source_responses_v1/03_fetch_tags.json"
    verification_transcript_path: Literal[
        "data/evidence/s5_release_tag_source_responses_v1/04_verify_tags.json"
    ] = "data/evidence/s5_release_tag_source_responses_v1/04_verify_tags.json"
    result_path: Literal[
        "data/evidence/s5_release_tag_source_remediation_result_v1.json"
    ] = "data/evidence/s5_release_tag_source_remediation_result_v1.json"
    required_gate_ids: tuple[str, ...] = Field(min_length=16, max_length=16)
    discovery_processes_executed_during_freeze: Literal[0] = 0
    repository_copies_executed_during_freeze: Literal[0] = 0
    fetch_processes_executed_during_freeze: Literal[0] = 0
    network_requests_executed_during_freeze: Literal[0] = 0
    market_values_read_during_freeze: Literal[0] = 0
    returns_calculated_during_freeze: Literal[0] = 0
    parameters_defined: tuple[str, ...] = ()
    strategy_rules_defined: tuple[str, ...] = ()
    authorizes_runner_implementation: Literal[True] = True
    authorizes_tag_discovery_now: Literal[False] = False
    authorizes_repository_copy_now: Literal[False] = False
    authorizes_tag_fetch_now: Literal[False] = False
    authorizes_original_repository_mutation: Literal[False] = False
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
        "FREEZE_S5_RELEASE_TAG_SOURCE_REMEDIATION_PROTOCOL"
    ] = S5_RELEASE_REMEDIATION_DECISION
    next_authorization: Literal[
        "AUTHORIZE_S5_RELEASE_TAG_SOURCE_REMEDIATION_RUNNER_IMPLEMENTATION_ONLY"
    ] = S5_RELEASE_REMEDIATION_NEXT
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
        "rejected_measurement_result_evidence_hash",
        "rejection_audit_evidence_hash",
        "original_repository_config_file_sha256",
        "original_repository_packed_refs_file_sha256",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S5ReleaseTagSourceRemediationProtocolV1:
        paths = tuple(item.path for item in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 release remediation source bindings changed")
        if self.source_binding_manifest_evidence_hash != universe_evidence_hash(
            tuple(item.model_dump(mode="json") for item in self.source_bindings)
        ):
            raise ValueError("S5 release remediation source manifest changed")
        if self.required_gate_ids != S5_RELEASE_REMEDIATION_GATES:
            raise ValueError("S5 release remediation gates changed")
        if self.expected_local_git_process_count + self.expected_network_git_process_count != (
            self.maximum_total_git_process_count
        ):
            raise ValueError("S5 release remediation process accounting changed")
        transcript_paths = (
            self.discovery_transcript_path,
            self.reachability_transcript_path,
            self.fetch_transcript_path,
            self.verification_transcript_path,
        )
        if transcript_paths != tuple(sorted(set(transcript_paths))):
            raise ValueError("S5 release remediation transcript paths changed")
        if self.original_history_dataset_path == self.destination_history_dataset_path:
            raise ValueError("S5 release remediation cannot mutate the original source")
        if self.parameters_defined or self.strategy_rules_defined:
            raise ValueError("S5 release remediation cannot define a strategy")
        if self.limitations != tuple(sorted(set(self.limitations))):
            raise ValueError("S5 release remediation limitations changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected_hash:
            raise ValueError("S5 release remediation protocol hash changed")
        return self


class S5ReleaseTagSourceRemediationProtocolAuditV1(BaseModel):
    schema_version: Literal[
        "aurex-s5-release-tag-source-remediation-protocol-audit-v1"
    ] = "aurex-s5-release-tag-source-remediation-protocol-audit-v1"
    audit_id: Literal[
        "s5-release-tag-source-remediation-protocol-audit-v1"
    ] = "s5-release-tag-source-remediation-protocol-audit-v1"
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
    rejection_audit_evidence_hash: str
    source_binding_count: Literal[11] = 11
    protocol_reconstructed_exactly: Literal[True] = True
    discovery_processes_executed: Literal[0] = 0
    repository_copies_executed: Literal[0] = 0
    fetch_processes_executed: Literal[0] = 0
    network_requests_executed: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    signals_created: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal[
        "PASS_S5_RELEASE_TAG_SOURCE_REMEDIATION_PROTOCOL_AUDIT"
    ] = S5_RELEASE_REMEDIATION_AUDIT_DECISION
    next_authorization: Literal[
        "AUTHORIZE_S5_RELEASE_TAG_SOURCE_REMEDIATION_RUNNER_IMPLEMENTATION_ONLY"
    ] = S5_RELEASE_REMEDIATION_NEXT
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
        "rejection_audit_evidence_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5ReleaseTagSourceRemediationProtocolAuditV1:
        paths = tuple(item.path for item in self.auditor_implementation_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 release remediation auditor bindings changed")
        if self.auditor_contract_hash != universe_evidence_hash(
            tuple(
                item.model_dump(mode="json")
                for item in self.auditor_implementation_bindings
            )
        ):
            raise ValueError("S5 release remediation auditor contract changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected_hash:
            raise ValueError("S5 release remediation protocol audit hash changed")
        return self
