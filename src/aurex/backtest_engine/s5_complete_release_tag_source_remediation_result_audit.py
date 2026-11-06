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

S5_COMPLETE_RELEASE_RESULT_AUDIT_PASS = (
    "PASS_S5_COMPLETE_RELEASE_TAG_SOURCE_REMEDIATION_RESULT_AUDIT"
)
S5_COMPLETE_RELEASE_RESULT_AUDIT_NEXT = "FREEZE_S5_AMENDED_MEASUREMENT_PROTOCOL_ONLY"


class S5CompleteReleaseRemediationResultAuditV1(BaseModel):
    schema_version: Literal[
        "aurex-s5-complete-release-remediation-result-audit-v1"
    ] = "aurex-s5-complete-release-remediation-result-audit-v1"
    audit_id: Literal[
        "s5-complete-release-remediation-result-audit-v1"
    ] = "s5-complete-release-remediation-result-audit-v1"
    audited_at: datetime
    result_path: Literal[
        "data/evidence/s5_complete_release_tag_source_remediation_result_v1.json"
    ] = "data/evidence/s5_complete_release_tag_source_remediation_result_v1.json"
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
    transcript_paths: tuple[str, ...] = Field(min_length=2, max_length=2)
    transcript_file_sha256s: tuple[str, ...] = Field(min_length=2, max_length=2)
    transcript_evidence_hashes: tuple[str, ...] = Field(min_length=2, max_length=2)
    transcript_models_reverified: Literal[True] = True
    transcript_commands_reverified: Literal[True] = True
    stored_process_count: Literal[2] = 2
    stored_network_process_count: Literal[1] = 1
    stored_local_process_count: Literal[1] = 1
    complete_stable_tag_count: Literal[132] = 132
    complete_annotated_tag_count: Literal[104] = 104
    complete_lightweight_tag_count: Literal[28] = 28
    complete_tag_manifest_evidence_hash: Literal[
        "07d4b9d80266710faf9dcf578a6835c6d1c36727b362132b896c725811eea82c"
    ] = "07d4b9d80266710faf9dcf578a6835c6d1c36727b362132b896c725811eea82c"
    verified_tag_count: Literal[132] = 132
    tag_identity_drift_count: Literal[0] = 0
    original_repository_directory_sha256: str
    original_repository_manifest_reverified: Literal[True] = True
    incomplete_repository_directory_sha256: str
    incomplete_repository_manifest_reverified: Literal[True] = True
    complete_repository_directory_sha256: str
    complete_repository_manifest_reverified: Literal[True] = True
    nominal_result_pass_upheld: Literal[True] = True
    release_tag_source_complete_for_amended_measurement: Literal[True] = True
    event_time_filtering_executed: Literal[False] = False
    git_processes_executed_during_audit: Literal[0] = 0
    network_requests_executed_during_audit: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    candidates_created: Literal[0] = 0
    signals_created: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal[
        "PASS_S5_COMPLETE_RELEASE_TAG_SOURCE_REMEDIATION_RESULT_AUDIT"
    ] = S5_COMPLETE_RELEASE_RESULT_AUDIT_PASS
    next_authorization: Literal[
        "FREEZE_S5_AMENDED_MEASUREMENT_PROTOCOL_ONLY"
    ] = S5_COMPLETE_RELEASE_RESULT_AUDIT_NEXT
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
        "original_repository_directory_sha256",
        "incomplete_repository_directory_sha256",
        "complete_repository_directory_sha256",
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
    def validate_audit(self) -> S5CompleteReleaseRemediationResultAuditV1:
        paths = tuple(item.path for item in self.auditor_implementation_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 complete release result auditor bindings changed")
        if self.auditor_contract_hash != universe_evidence_hash(
            tuple(
                item.model_dump(mode="json")
                for item in self.auditor_implementation_bindings
            )
        ):
            raise ValueError("S5 complete release result auditor contract changed")
        if (
            self.complete_annotated_tag_count + self.complete_lightweight_tag_count
            != self.complete_stable_tag_count
            or self.verified_tag_count != self.complete_stable_tag_count
            or self.tag_identity_drift_count != 0
            or not self.nominal_result_pass_upheld
            or not self.release_tag_source_complete_for_amended_measurement
            or self.event_time_filtering_executed
        ):
            raise ValueError("S5 complete release result audit accounting changed")
        if self.transcript_paths != tuple(sorted(set(self.transcript_paths))):
            raise ValueError("S5 complete release result transcript paths changed")
        if self.limitations != tuple(sorted(set(self.limitations))):
            raise ValueError("S5 complete release result audit limitations changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected_hash:
            raise ValueError("S5 complete release result audit hash changed")
        return self
