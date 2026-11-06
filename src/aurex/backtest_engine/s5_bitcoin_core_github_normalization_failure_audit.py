from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from aurex.backtest_engine.s5_bitcoin_core_github_normalization_failure import (
    S5_NORMALIZATION_FAILURE_ADJUDICATION_NEXT,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)


class S5NormalizationFailureAdjudicationResultAudit(BaseModel):
    schema_version: Literal[
        "aurex-s5-normalization-failure-adjudication-result-audit-v1"
    ] = "aurex-s5-normalization-failure-adjudication-result-audit-v1"
    audit_id: Literal[
        "s5-normalization-failure-adjudication-result-audit-v1"
    ] = "s5-normalization-failure-adjudication-result-audit-v1"
    audited_at: datetime
    result_path: Literal[
        "data/evidence/s5_bitcoin_core_github_normalization_failure_adjudication_result_v1.json"
    ] = (
        "data/evidence/"
        "s5_bitcoin_core_github_normalization_failure_adjudication_result_v1.json"
    )
    result_file_sha256: str
    result_evidence_hash: str
    protocol_evidence_hash: str
    protocol_audit_evidence_hash: str
    runner_contract_hash: str
    auditor_contract_hash: str
    all_source_pages_rehashed: Literal[True] = True
    history_dataset_rehashed: Literal[True] = True
    full_graph_reexecuted_once: Literal[True] = True
    result_reconstructed_exactly: Literal[True] = True
    full_graph_commit_count: Literal[50395] = 50_395
    first_parent_commit_count: Literal[17543] = 17_543
    recognized_gap_count: Literal[83] = 83
    unmatched_accepted_pull_count: Literal[112] = 112
    exact_merge_commit_recovery_count: Literal[0] = 0
    structurally_unexplained_count: Literal[187] = 187
    source_page_files_opened: Literal[245] = 245
    response_bodies_decoded: Literal[245] = 245
    local_git_process_count: Literal[1] = 1
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["PASS_S5_NORMALIZATION_FAILURE_RESULT_AUDIT"] = (
        "PASS_S5_NORMALIZATION_FAILURE_RESULT_AUDIT"
    )
    next_authorization: Literal[
        "FREEZE_S5_GITHUB_TARGETED_COMPLETENESS_CORRECTION_PROTOCOL_ONLY"
    ] = S5_NORMALIZATION_FAILURE_ADJUDICATION_NEXT
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
        "runner_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5NormalizationFailureAdjudicationResultAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 failure adjudication result audit hash changed")
        return self
