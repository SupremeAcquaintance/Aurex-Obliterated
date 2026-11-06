from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)


class PeriodicFlowSuccessorTransportAttemptAuditV3(BaseModel):
    attempt: int = Field(ge=1, le=12)
    request_file_sha256: str
    response_file_sha256: str
    range_start: int = Field(ge=0)
    status: int | None = Field(default=None, ge=100, le=599)
    expected_total_bytes: int | None = Field(default=None, gt=0)
    bytes_received: int = Field(ge=0)
    partial_bytes_after_attempt: int = Field(ge=0)
    outcome: Literal["TRANSIENT"] = "TRANSIENT"
    failure_class: Literal["INCOMPLETE_BODY", "URL_ERROR"]
    exception_type: Literal["IncompleteBodyError", "URLError"]
    exception_message: str = Field(min_length=1, max_length=500)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("request_file_sha256", "response_file_sha256")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_attempt(self) -> PeriodicFlowSuccessorTransportAttemptAuditV3:
        if self.attempt == 1:
            valid = (
                self.range_start == 0
                and self.status == 200
                and self.expected_total_bytes == 228_784_150
                and self.bytes_received == 86_150_831
                and self.partial_bytes_after_attempt == 86_150_831
                and self.failure_class == "INCOMPLETE_BODY"
                and self.exception_type == "IncompleteBodyError"
            )
        else:
            valid = (
                self.range_start == 86_150_831
                and self.status is None
                and self.expected_total_bytes == 228_784_150
                and self.bytes_received == 0
                and self.partial_bytes_after_attempt == 86_150_831
                and self.failure_class == "URL_ERROR"
                and self.exception_type == "URLError"
                and "getaddrinfo failed" in self.exception_message
            )
        if not valid:
            raise ValueError("Q1 successor v3 terminal attempt evidence changed")
        return self


class PeriodicFlowSuccessorTerminalAuditV3(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-terminal-audit-v3"
    ] = "aurex-q1-periodic-flow-successor-terminal-audit-v3"
    audit_id: Literal["q1-periodic-flow-successor-terminal-audit-v3"] = (
        "q1-periodic-flow-successor-terminal-audit-v3"
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
    transport_amendment_file_sha256: str
    transport_amendment_evidence_hash: str
    execution_contract_file_sha256: str
    execution_contract_evidence_hash: str
    execution_contract_audit_file_sha256: str
    execution_contract_audit_evidence_hash: str
    runner_source_hash: str
    auditor_contract_hash: str
    failed_target_key: Literal["2020-08|USD_M_PERPETUAL"] = (
        "2020-08|USD_M_PERPETUAL"
    )
    frozen_failure_reason: str = Field(min_length=1, max_length=1000)
    attempts: tuple[PeriodicFlowSuccessorTransportAttemptAuditV3, ...] = Field(
        min_length=12, max_length=12
    )
    request_marker_count: Literal[17] = 17
    response_marker_count: Literal[17] = 17
    request_marker_manifest_hash: str
    cumulative_payload_bytes_received: Literal[583_285_471] = 583_285_471
    failed_target_payload_bytes_received: Literal[86_150_831] = 86_150_831
    declared_archive_bytes: Literal[228_784_150] = 228_784_150
    partial_archive_path: str
    partial_archive_file_sha256: str
    partial_archive_bytes: Literal[86_150_831] = 86_150_831
    completed_archive_exists: Literal[False] = False
    completed_archive_checksum_verified: Literal[False] = False
    transport_failure_observed: Literal[True] = True
    archive_integrity_failure_observed: Literal[False] = False
    retry_budget_exhausted: Literal[True] = True
    terminal_result_valid: Literal[True] = True
    terminal_result_resumable: Literal[False] = False
    inspected_archive_count: Literal[7] = 7
    qualified_paired_month_count: Literal[2] = 2
    excluded_month_count: Literal[1] = 1
    total_new_archive_bytes: Literal[540_126_256] = 540_126_256
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
    decision: Literal["CONFIRM_Q1_SUCCESSOR_V3_TERMINAL_TRANSPORT_STOP"] = (
        "CONFIRM_Q1_SUCCESSOR_V3_TERMINAL_TRANSPORT_STOP"
    )
    next_authorization: Literal[
        "FREEZE_Q1_SUCCESSOR_TRANSPORT_V4_CONTINUATION_ONLY"
    ] = "FREEZE_Q1_SUCCESSOR_TRANSPORT_V4_CONTINUATION_ONLY"
    findings: tuple[str, ...] = Field(min_length=6)
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
        "transport_amendment_file_sha256",
        "transport_amendment_evidence_hash",
        "execution_contract_file_sha256",
        "execution_contract_evidence_hash",
        "execution_contract_audit_file_sha256",
        "execution_contract_audit_evidence_hash",
        "runner_source_hash",
        "auditor_contract_hash",
        "request_marker_manifest_hash",
        "partial_archive_file_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> PeriodicFlowSuccessorTerminalAuditV3:
        attempts = tuple(sorted(self.attempts, key=lambda item: item.attempt))
        if (
            self.attempts != attempts
            or tuple(item.attempt for item in attempts) != tuple(range(1, 13))
            or sum(item.bytes_received for item in attempts)
            != self.failed_target_payload_bytes_received
            or self.partial_archive_bytes >= self.declared_archive_bytes
            or "getaddrinfo failed" not in self.frozen_failure_reason
            or self.price_or_quantity_values_parsed
            or self.features_calculated
            or self.parameters_defined
            or self.returns_calculated
            or self.findings != tuple(sorted(set(self.findings)))
        ):
            raise ValueError("Q1 successor v3 terminal audit changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 successor v3 terminal audit hash changed")
        return self


def build_successor_terminal_audit_v3(
    **values,
) -> PeriodicFlowSuccessorTerminalAuditV3:
    payload = dict(values)
    payload["attempts"] = tuple(
        sorted(payload["attempts"], key=lambda item: item.attempt)
    )
    payload["findings"] = tuple(sorted(set(payload["findings"])))
    provisional = PeriodicFlowSuccessorTerminalAuditV3.model_construct(
        **payload,
        audit_evidence_hash="0" * 64,
    )
    data = provisional.model_dump()
    data["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"audit_evidence_hash"})
    )
    return PeriodicFlowSuccessorTerminalAuditV3.model_validate(data)


def audit_successor_terminal_audit_v3(
    audit: PeriodicFlowSuccessorTerminalAuditV3,
) -> bool:
    return audit.audit_evidence_hash == universe_evidence_hash(
        audit.model_dump(exclude={"audit_evidence_hash"})
    )
