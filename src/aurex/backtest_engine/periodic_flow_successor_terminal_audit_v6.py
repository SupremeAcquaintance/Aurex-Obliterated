from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)


class PeriodicFlowSuccessorTransportAttemptAuditV6(BaseModel):
    attempt: int = Field(ge=1, le=24)
    request_file_sha256: str
    response_file_sha256: str
    range_start: int = Field(ge=0)
    status: int | None = Field(default=None, ge=100, le=599)
    bytes_received: int = Field(ge=0)
    partial_bytes_after_attempt: int = Field(ge=0)
    outcome: Literal["TRANSIENT"] = "TRANSIENT"
    failure_class: Literal["URL_ERROR", "INCOMPLETE_BODY"]
    exception_type: Literal["URLError", "IncompleteBodyError"]
    exception_message: str = Field(min_length=1, max_length=500)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("request_file_sha256", "response_file_sha256")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)


class PeriodicFlowSuccessorTerminalAuditV6(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-terminal-audit-v6"
    ] = "aurex-q1-periodic-flow-successor-terminal-audit-v6"
    audit_id: Literal["q1-periodic-flow-successor-terminal-audit-v6"] = (
        "q1-periodic-flow-successor-terminal-audit-v6"
    )
    audited_at: datetime
    status: Literal["COMPLETE_TERMINAL_TRANSPORT_AUDIT_NO_OUTCOMES"] = (
        "COMPLETE_TERMINAL_TRANSPORT_AUDIT_NO_OUTCOMES"
    )
    result_file_sha256: str
    result_evidence_hash: str
    checkpoint_file_sha256: str
    checkpoint_evidence_hash: str
    protocol_file_sha256: str
    protocol_evidence_hash: str
    validator_amendment_file_sha256: str
    validator_amendment_evidence_hash: str
    execution_contract_file_sha256: str
    execution_contract_evidence_hash: str
    execution_contract_audit_file_sha256: str
    execution_contract_audit_evidence_hash: str
    runner_source_hash: str
    auditor_contract_hash: str
    failed_target_key: Literal["2023-04|USD_M_PERPETUAL"] = (
        "2023-04|USD_M_PERPETUAL"
    )
    frozen_failure_reason: str = Field(min_length=1, max_length=1200)
    attempts: tuple[PeriodicFlowSuccessorTransportAttemptAuditV6, ...] = Field(
        min_length=24, max_length=24
    )
    request_marker_count: Literal[38] = 38
    response_marker_count: Literal[38] = 38
    request_marker_manifest_hash: str
    cumulative_payload_bytes_received: Literal[6_658_445_428] = 6_658_445_428
    failed_target_payload_bytes_received: Literal[184_135_287] = 184_135_287
    completed_archive_exists: Literal[False] = False
    partial_archive_exists: Literal[True] = True
    partial_archive_bytes: Literal[184_135_287] = 184_135_287
    partial_archive_sha256: Literal[
        "1b94bfc412aa3683c7b88c3af1ca5848d3d76219f155872877791cee4b177fd2"
    ] = "1b94bfc412aa3683c7b88c3af1ca5848d3d76219f155872877791cee4b177fd2"
    expected_total_archive_bytes: Literal[1_034_971_533] = 1_034_971_533
    archive_integrity_failure_observed: Literal[False] = False
    transport_failure_observed: Literal[True] = True
    retry_budget_exhausted: Literal[True] = True
    terminal_result_valid: Literal[True] = True
    inspected_archive_count: Literal[56] = 56
    qualified_paired_month_count: Literal[17] = 17
    excluded_month_count: Literal[11] = 11
    total_new_archive_bytes: Literal[30_282_986_798] = 30_282_986_798
    price_or_quantity_values_parsed: tuple[str, ...] = ()
    features_calculated: tuple[str, ...] = ()
    parameters_defined: tuple[str, ...] = ()
    returns_calculated: tuple[str, ...] = ()
    validation_accessed: Literal[False] = False
    holdout_accessed: Literal[False] = False
    strategy_candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    real_net_profit_usd: Literal["0"] = "0"
    decision: Literal["CONFIRM_Q1_SUCCESSOR_V6_TERMINAL_TRANSPORT_STOP"] = (
        "CONFIRM_Q1_SUCCESSOR_V6_TERMINAL_TRANSPORT_STOP"
    )
    next_authorization: Literal[
        "FREEZE_Q1_SUCCESSOR_TRANSPORT_V7_CONTINUATION_ONLY"
    ] = "FREEZE_Q1_SUCCESSOR_TRANSPORT_V7_CONTINUATION_ONLY"
    findings: tuple[str, ...] = Field(min_length=8)
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "result_file_sha256",
        "result_evidence_hash",
        "checkpoint_file_sha256",
        "checkpoint_evidence_hash",
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "validator_amendment_file_sha256",
        "validator_amendment_evidence_hash",
        "execution_contract_file_sha256",
        "execution_contract_evidence_hash",
        "execution_contract_audit_file_sha256",
        "execution_contract_audit_evidence_hash",
        "runner_source_hash",
        "auditor_contract_hash",
        "request_marker_manifest_hash",
        "partial_archive_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> PeriodicFlowSuccessorTerminalAuditV6:
        attempts = tuple(sorted(self.attempts, key=lambda item: item.attempt))
        payload_attempts = tuple(item for item in attempts if item.bytes_received)
        if (
            self.attempts != attempts
            or tuple(item.attempt for item in attempts) != tuple(range(1, 25))
            or len(payload_attempts) != 1
            or payload_attempts[0].attempt != 14
            or payload_attempts[0].failure_class != "INCOMPLETE_BODY"
            or payload_attempts[0].bytes_received
            != self.failed_target_payload_bytes_received
            or attempts[-1].partial_bytes_after_attempt != self.partial_archive_bytes
            or "getaddrinfo failed" not in self.frozen_failure_reason
            or self.price_or_quantity_values_parsed
            or self.features_calculated
            or self.parameters_defined
            or self.returns_calculated
            or self.findings != tuple(sorted(set(self.findings)))
        ):
            raise ValueError("Q1 successor v6 terminal audit changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 successor v6 terminal audit hash changed")
        return self


def build_successor_terminal_audit_v6(
    **values,
) -> PeriodicFlowSuccessorTerminalAuditV6:
    payload = dict(values)
    payload["attempts"] = tuple(
        sorted(payload["attempts"], key=lambda item: item.attempt)
    )
    payload["findings"] = tuple(sorted(set(payload["findings"])))
    provisional = PeriodicFlowSuccessorTerminalAuditV6.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    data = provisional.model_dump()
    data["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"audit_evidence_hash"})
    )
    return PeriodicFlowSuccessorTerminalAuditV6.model_validate(data)


def audit_successor_terminal_audit_v6(
    audit: PeriodicFlowSuccessorTerminalAuditV6,
) -> bool:
    return audit.audit_evidence_hash == universe_evidence_hash(
        audit.model_dump(exclude={"audit_evidence_hash"})
    )
