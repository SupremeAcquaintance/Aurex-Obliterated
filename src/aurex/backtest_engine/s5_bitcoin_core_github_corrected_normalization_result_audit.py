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


class S5GitHubCorrectedNormalizationResultAuditV2(BaseModel):
    schema_version: Literal[
        "aurex-s5-github-corrected-normalization-result-audit-v2"
    ] = "aurex-s5-github-corrected-normalization-result-audit-v2"
    audit_id: Literal[
        "s5-github-corrected-normalization-result-audit-v2"
    ] = "s5-github-corrected-normalization-result-audit-v2"
    audited_at: datetime
    result_file_sha256: str
    result_evidence_hash: str
    protocol_evidence_hash: str
    protocol_audit_evidence_hash: str
    execution_contract_evidence_hash: str
    execution_contract_audit_evidence_hash: str
    runner_contract_hash: str
    auditor_implementation_bindings: tuple[S5HistoryBinding, ...] = Field(
        min_length=2, max_length=2
    )
    auditor_contract_hash: str
    output_file_manifest_evidence_hash: str
    output_row_manifest_evidence_hash: str
    normalized_pull_count: Literal[24_398] = 24_398
    canonical_mapping_count: Literal[16_242] = 16_242
    target_resolution_count: Literal[194] = 194
    accepted_coverage_count: Literal[16_279] = 16_279
    unresolved_merge_count: Literal[479] = 479
    accepted_source_linked_count: Literal[16_271] = 16_271
    accepted_source_unverified_count: Literal[8] = 8
    local_git_processes_executed: Literal[2] = 2
    github_requests_executed: Literal[0] = 0
    market_values_read: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    result_reconstructed_exactly: Literal[True] = True
    decision: Literal[
        "PASS_S5_GITHUB_CORRECTED_NORMALIZATION_RESULT_AUDIT"
    ] = "PASS_S5_GITHUB_CORRECTED_NORMALIZATION_RESULT_AUDIT"
    next_authorization: Literal[
        "FREEZE_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_PROTOCOL_ONLY"
    ] = "FREEZE_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_PROTOCOL_ONLY"
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
        "output_file_manifest_evidence_hash",
        "output_row_manifest_evidence_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5GitHubCorrectedNormalizationResultAuditV2:
        paths = tuple(row.path for row in self.auditor_implementation_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 corrected result auditor bindings changed")
        if self.auditor_contract_hash != universe_evidence_hash(
            tuple(
                row.model_dump(mode="json")
                for row in self.auditor_implementation_bindings
            )
        ):
            raise ValueError("S5 corrected result auditor contract changed")
        if (
            self.accepted_source_linked_count
            + self.accepted_source_unverified_count
            != self.accepted_coverage_count
        ):
            raise ValueError("S5 corrected audited coverage accounting changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 corrected result audit hash changed")
        return self
