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

S5_RELEASE_RESULT_AUDIT_REJECT = (
    "REJECT_S5_RELEASE_TAG_SOURCE_REMEDIATION_PASS_INCOMPLETE_RELEASE_COVERAGE"
)
S5_RELEASE_RESULT_AUDIT_NEXT = (
    "FREEZE_S5_COMPLETE_RELEASE_TAG_SOURCE_REMEDIATION_PROTOCOL_ONLY"
)


class S5ReleaseTagSourceRemediationResultAuditV1(BaseModel):
    schema_version: Literal[
        "aurex-s5-release-tag-source-remediation-result-audit-v1"
    ] = "aurex-s5-release-tag-source-remediation-result-audit-v1"
    audit_id: Literal[
        "s5-release-tag-source-remediation-result-audit-v1"
    ] = "s5-release-tag-source-remediation-result-audit-v1"
    audited_at: datetime
    result_path: Literal[
        "data/evidence/s5_release_tag_source_remediation_result_v1.json"
    ] = "data/evidence/s5_release_tag_source_remediation_result_v1.json"
    result_file_sha256: str
    result_evidence_hash: str
    protocol_evidence_hash: str
    protocol_audit_evidence_hash: str
    execution_contract_evidence_hash: str
    execution_contract_audit_evidence_hash: str
    runner_contract_hash: str
    auditor_implementation_bindings: tuple[S5HistoryBinding, ...] = Field(
        min_length=2,
        max_length=2,
    )
    auditor_contract_hash: str
    transcript_paths: tuple[str, ...] = Field(min_length=4, max_length=4)
    transcript_file_sha256s: tuple[str, ...] = Field(min_length=4, max_length=4)
    transcript_evidence_hashes: tuple[str, ...] = Field(min_length=4, max_length=4)
    transcript_models_reverified: Literal[True] = True
    transcript_commands_reverified: Literal[True] = True
    stored_process_count: Literal[4] = 4
    stored_network_process_count: Literal[2] = 2
    stored_local_process_count: Literal[2] = 2
    remote_tag_ref_record_count: Literal[691] = 691
    remote_exact_stable_base_ref_count: Literal[132] = 132
    admitted_stable_tag_count: Literal[42] = 42
    admitted_annotated_tag_count: Literal[14] = 14
    admitted_lightweight_tag_count: Literal[28] = 28
    omitted_stable_tag_count: Literal[90] = 90
    omitted_annotated_tag_count: Literal[90] = 90
    omitted_lightweight_tag_count: Literal[0] = 0
    reachable_commit_count: Literal[50_395] = 50_395
    admitted_tag_manifest_evidence_hash: str
    fetched_tag_count: Literal[42] = 42
    fetched_tag_identity_drift_count: Literal[0] = 0
    original_repository_path: Literal[
        "data/evidence/s5_bitcoin_core_history_payload_v1.git"
    ] = "data/evidence/s5_bitcoin_core_history_payload_v1.git"
    original_repository_directory_sha256: str
    original_repository_manifest_reverified: Literal[True] = True
    remediated_repository_path: Literal[
        "data/evidence/s5_bitcoin_core_release_tags_v1.git"
    ] = "data/evidence/s5_bitcoin_core_release_tags_v1.git"
    remediated_repository_directory_sha256: str
    remediated_repository_manifest_reverified: Literal[True] = True
    frozen_protocol_pass_reproduced: Literal[True] = True
    nominal_result_pass_upheld: Literal[False] = False
    release_tag_source_complete_for_measurement: Literal[False] = False
    defect_classification: Literal[
        "ANCESTOR_ONLY_POLICY_EXCLUDED_90_ANNOTATED_MAINTENANCE_BRANCH_RELEASES"
    ] = "ANCESTOR_ONLY_POLICY_EXCLUDED_90_ANNOTATED_MAINTENANCE_BRANCH_RELEASES"
    transcript_rows_parsed: Literal[51_128] = 51_128
    git_processes_executed_during_audit: Literal[0] = 0
    network_requests_executed_during_audit: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    candidates_created: Literal[0] = 0
    signals_created: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal[
        "REJECT_S5_RELEASE_TAG_SOURCE_REMEDIATION_PASS_INCOMPLETE_RELEASE_COVERAGE"
    ] = S5_RELEASE_RESULT_AUDIT_REJECT
    next_authorization: Literal[
        "FREEZE_S5_COMPLETE_RELEASE_TAG_SOURCE_REMEDIATION_PROTOCOL_ONLY"
    ] = S5_RELEASE_RESULT_AUDIT_NEXT
    limitations: tuple[str, ...] = Field(min_length=9)
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
        "protocol_audit_evidence_hash",
        "execution_contract_evidence_hash",
        "execution_contract_audit_evidence_hash",
        "runner_contract_hash",
        "auditor_contract_hash",
        "admitted_tag_manifest_evidence_hash",
        "original_repository_directory_sha256",
        "remediated_repository_directory_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("transcript_file_sha256s", "transcript_evidence_hashes")
    @classmethod
    def normalize_hash_sets(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(normalize_sha256(item) for item in value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5ReleaseTagSourceRemediationResultAuditV1:
        paths = tuple(item.path for item in self.auditor_implementation_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 release result auditor bindings changed")
        if self.auditor_contract_hash != universe_evidence_hash(
            tuple(
                item.model_dump(mode="json")
                for item in self.auditor_implementation_bindings
            )
        ):
            raise ValueError("S5 release result auditor contract changed")
        if (
            self.admitted_annotated_tag_count + self.admitted_lightweight_tag_count
            != self.admitted_stable_tag_count
            or self.omitted_annotated_tag_count + self.omitted_lightweight_tag_count
            != self.omitted_stable_tag_count
            or self.admitted_stable_tag_count + self.omitted_stable_tag_count
            != self.remote_exact_stable_base_ref_count
            or self.fetched_tag_count != self.admitted_stable_tag_count
            or self.fetched_tag_identity_drift_count != 0
            or self.nominal_result_pass_upheld
            or self.release_tag_source_complete_for_measurement
        ):
            raise ValueError("S5 release result coverage rejection changed")
        if self.transcript_paths != tuple(sorted(set(self.transcript_paths))):
            raise ValueError("S5 release result transcript paths changed")
        if self.limitations != tuple(sorted(set(self.limitations))):
            raise ValueError("S5 release result audit limitations changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected_hash:
            raise ValueError("S5 release result audit hash changed")
        return self
