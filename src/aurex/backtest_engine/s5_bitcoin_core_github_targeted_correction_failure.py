from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)


class S5TargetedCorrectionV1FailureAudit(BaseModel):
    schema_version: Literal[
        "aurex-s5-targeted-correction-v1-failure-audit-v1"
    ] = "aurex-s5-targeted-correction-v1-failure-audit-v1"
    audit_id: Literal["s5-targeted-correction-v1-failure-audit-v1"] = (
        "s5-targeted-correction-v1-failure-audit-v1"
    )
    audited_at: datetime
    result_file_sha256: str
    result_evidence_hash: str
    protocol_evidence_hash: str
    protocol_audit_evidence_hash: str
    execution_contract_evidence_hash: str
    execution_contract_audit_evidence_hash: str
    runner_contract_hash: str
    auditor_contract_hash: str
    attempt_marker_file_sha256: str
    failure_artifact_file_sha256: str
    attempted_pull_number: Literal[10] = 10
    attempted_request_count: Literal[1] = 1
    accepted_response_count: Literal[0] = 0
    persisted_http_status_count: Literal[0] = 0
    persisted_response_body_count: Literal[0] = 0
    failure_type: Literal["ResponseFailure"] = "ResponseFailure"
    underlying_error_type: Literal["TypeError"] = "TypeError"
    context_manager_defect_verified: Literal[True] = True
    uncertain_get_may_have_reached_github: Literal[True] = True
    original_attempt_retry_under_v1_forbidden: Literal[True] = True
    full_graph_reexecuted_once: Literal[True] = True
    commit_diagnostics_reexecuted_once: Literal[True] = True
    full_graph_commit_count: Literal[50395] = 50_395
    first_parent_commit_count: Literal[17543] = 17_543
    first_parent_merge_count: Literal[16721] = 16_721
    recognized_target_reachable_count: Literal[83] = 83
    commit_diagnostic_count: Literal[83] = 83
    local_git_process_count: Literal[2] = 2
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["PASS_S5_TARGETED_CORRECTION_V1_FAILURE_AUDIT"] = (
        "PASS_S5_TARGETED_CORRECTION_V1_FAILURE_AUDIT"
    )
    next_authorization: Literal[
        "FREEZE_S5_TARGETED_CORRECTION_V2_REMEDIATION_PROTOCOL_ONLY"
    ] = "FREEZE_S5_TARGETED_CORRECTION_V2_REMEDIATION_PROTOCOL_ONLY"
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
        "attempt_marker_file_sha256",
        "failure_artifact_file_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5TargetedCorrectionV1FailureAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 targeted v1 failure audit hash changed")
        return self
