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


class S5TargetedCorrectionV3ResultAudit(BaseModel):
    schema_version: Literal[
        "aurex-s5-targeted-correction-v3-result-audit-v1"
    ] = "aurex-s5-targeted-correction-v3-result-audit-v1"
    audit_id: Literal["s5-targeted-correction-v3-result-audit-v1"] = (
        "s5-targeted-correction-v3-result-audit-v1"
    )
    audited_at: datetime
    result_file_sha256: str
    result_evidence_hash: str
    protocol_evidence_hash: str
    protocol_audit_evidence_hash: str
    execution_contract_evidence_hash: str
    execution_contract_audit_evidence_hash: str
    runner_contract_hash: str
    transitive_v1_execution_contract_evidence_hash: str
    transitive_v1_runner_contract_hash: str
    auditor_implementation_bindings: tuple[S5HistoryBinding, ...] = Field(
        min_length=5, max_length=5
    )
    auditor_contract_hash: str
    response_binding_manifest_evidence_hash: str
    v3_request_marker_manifest_evidence_hash: str
    full_graph_stream_sha256: str
    response_count: Literal[194] = 194
    v3_response_count: Literal[193] = 193
    adopted_response_count: Literal[1] = 1
    request_attempt_marker_count: Literal[194] = 194
    http_200_count: int = Field(ge=0, le=194)
    http_404_count: int = Field(ge=0, le=194)
    empty_merge_commit_sha_response_count: int = Field(ge=1, le=194)
    total_response_bytes: int = Field(ge=1, le=268_435_456)
    full_graph_commit_count: Literal[50_395] = 50_395
    first_parent_commit_count: Literal[17_543] = 17_543
    first_parent_merge_count: Literal[16_721] = 16_721
    recognized_target_reachable_count: Literal[83] = 83
    commit_diagnostic_count: Literal[83] = 83
    local_git_process_count: Literal[2] = 2
    github_requests_executed: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    result_reconstructed_exactly: Literal[True] = True
    decision: Literal[
        "PASS_S5_GITHUB_TARGETED_COMPLETENESS_ACQUISITION_RESULT_AUDIT"
    ] = "PASS_S5_GITHUB_TARGETED_COMPLETENESS_ACQUISITION_RESULT_AUDIT"
    next_authorization: Literal[
        "FREEZE_S5_GITHUB_CORRECTED_NORMALIZATION_PROTOCOL_ONLY"
    ] = "FREEZE_S5_GITHUB_CORRECTED_NORMALIZATION_PROTOCOL_ONLY"
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
        "transitive_v1_execution_contract_evidence_hash",
        "transitive_v1_runner_contract_hash",
        "auditor_contract_hash",
        "response_binding_manifest_evidence_hash",
        "v3_request_marker_manifest_evidence_hash",
        "full_graph_stream_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5TargetedCorrectionV3ResultAudit:
        paths = tuple(row.path for row in self.auditor_implementation_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 targeted v3 result auditor bindings changed")
        if self.auditor_contract_hash != universe_evidence_hash(
            tuple(
                row.model_dump(mode="json")
                for row in self.auditor_implementation_bindings
            )
        ):
            raise ValueError("S5 targeted v3 result auditor contract changed")
        if self.http_200_count + self.http_404_count != self.response_count:
            raise ValueError("S5 targeted v3 audited HTTP accounting changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 targeted v3 result audit hash changed")
        return self
