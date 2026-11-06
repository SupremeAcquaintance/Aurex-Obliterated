from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)


class PeriodicFlowSuccessorTransportAttemptAudit(BaseModel):
    attempt: int = Field(ge=1, le=3)
    target_key: Literal["2020-05|USD_M_PERPETUAL"] = (
        "2020-05|USD_M_PERPETUAL"
    )
    request_file_sha256: str
    response_file_sha256: str
    requested_at: datetime
    completed_at: datetime
    duration_seconds: Decimal = Field(gt=0)
    method: Literal["GET"] = "GET"
    range_requested: Literal[False] = False
    status: int | None = Field(default=None, ge=100, le=599)
    content_length: int | None = Field(default=None, gt=0)
    content_encoding: Literal["identity"] = "identity"
    bytes_received: int = Field(ge=0)
    outcome: Literal["TRANSIENT"] = "TRANSIENT"
    exception_type_recorded: Literal[False] = False
    exception_message_recorded: Literal[False] = False

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("requested_at", "completed_at")
    @classmethod
    def normalize_times(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("request_file_sha256", "response_file_sha256")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_attempt(self) -> PeriodicFlowSuccessorTransportAttemptAudit:
        elapsed = self.completed_at - self.requested_at
        expected_duration = Decimal(
            elapsed.days * 86_400 * 1_000_000
            + elapsed.seconds * 1_000_000
            + elapsed.microseconds
        ) / Decimal(1_000_000)
        if (
            self.duration_seconds != expected_duration
            or (self.status == 200) != (self.content_length is not None)
            or (
                self.content_length is not None
                and self.bytes_received > self.content_length
            )
        ):
            raise ValueError("Q1 successor v2 transport-attempt audit changed")
        return self


class PeriodicFlowSuccessorTerminalAudit(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-terminal-audit-v2"
    ] = "aurex-q1-periodic-flow-successor-terminal-audit-v2"
    audit_id: Literal["q1-periodic-flow-successor-terminal-audit-v2"] = (
        "q1-periodic-flow-successor-terminal-audit-v2"
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
    protocol_audit_file_sha256: str
    protocol_audit_evidence_hash: str
    execution_contract_file_sha256: str
    execution_contract_evidence_hash: str
    execution_contract_audit_file_sha256: str
    execution_contract_audit_evidence_hash: str
    runner_source_hash: str
    auditor_contract_hash: str
    failed_target_key: Literal["2020-05|USD_M_PERPETUAL"] = (
        "2020-05|USD_M_PERPETUAL"
    )
    frozen_failure_reason: Literal[
        "Q1 successor payload unresolved for ('2020-05', 'USD_M_PERPETUAL')"
    ] = "Q1 successor payload unresolved for ('2020-05', 'USD_M_PERPETUAL')"
    attempts: tuple[PeriodicFlowSuccessorTransportAttemptAudit, ...] = Field(
        min_length=3, max_length=3
    )
    request_marker_count: Literal[3] = 3
    response_marker_count: Literal[3] = 3
    request_marker_manifest_hash: str
    cumulative_payload_bytes_received: Literal[16_332_030] = 16_332_030
    declared_archive_bytes: Literal[370_923_781] = 370_923_781
    completed_archive_exists: Literal[False] = False
    partial_archive_exists: Literal[False] = False
    completed_archive_checksum_verified: Literal[False] = False
    structural_archive_inspection_performed: Literal[False] = False
    archive_integrity_failure_observed: Literal[False] = False
    transport_failure_observed: Literal[True] = True
    precise_transport_exception_reconstructable: Literal[False] = False
    retry_budget_exhausted: Literal[True] = True
    terminal_result_valid: Literal[True] = True
    terminal_result_resumable: Literal[False] = False
    inspected_archive_count: Literal[3] = 3
    qualified_paired_month_count: Literal[1] = 1
    excluded_month_count: Literal[0] = 0
    total_new_archive_bytes: Literal[0] = 0
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
    decision: Literal["CONFIRM_Q1_SUCCESSOR_V2_TERMINAL_TRANSPORT_STOP"] = (
        "CONFIRM_Q1_SUCCESSOR_V2_TERMINAL_TRANSPORT_STOP"
    )
    next_authorization: Literal[
        "FREEZE_Q1_SUCCESSOR_TRANSPORT_V3_CORRECTION_ONLY"
    ] = "FREEZE_Q1_SUCCESSOR_TRANSPORT_V3_CORRECTION_ONLY"
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
        "protocol_audit_file_sha256",
        "protocol_audit_evidence_hash",
        "execution_contract_file_sha256",
        "execution_contract_evidence_hash",
        "execution_contract_audit_file_sha256",
        "execution_contract_audit_evidence_hash",
        "runner_source_hash",
        "auditor_contract_hash",
        "request_marker_manifest_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> PeriodicFlowSuccessorTerminalAudit:
        attempts = tuple(sorted(self.attempts, key=lambda item: item.attempt))
        declared_lengths = {
            item.content_length
            for item in attempts
            if item.content_length is not None
        }
        if (
            self.attempts != attempts
            or tuple(item.attempt for item in attempts) != (1, 2, 3)
            or any(item.target_key != self.failed_target_key for item in attempts)
            or sum(item.bytes_received for item in attempts)
            != self.cumulative_payload_bytes_received
            or declared_lengths != {self.declared_archive_bytes}
            or self.price_or_quantity_values_parsed
            or self.features_calculated
            or self.parameters_defined
            or self.returns_calculated
            or self.findings != tuple(sorted(set(self.findings)))
        ):
            raise ValueError("Q1 successor v2 terminal audit changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 successor v2 terminal audit hash changed")
        return self


def build_successor_terminal_audit(**values) -> PeriodicFlowSuccessorTerminalAudit:
    payload = dict(values)
    payload["attempts"] = tuple(
        sorted(payload["attempts"], key=lambda item: item.attempt)
    )
    payload["findings"] = tuple(sorted(set(payload["findings"])))
    provisional = PeriodicFlowSuccessorTerminalAudit.model_construct(
        **payload,
        audit_evidence_hash="0" * 64,
    )
    data = provisional.model_dump()
    data["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"audit_evidence_hash"})
    )
    return PeriodicFlowSuccessorTerminalAudit.model_validate(data)


def audit_successor_terminal_audit(
    audit: PeriodicFlowSuccessorTerminalAudit,
) -> bool:
    return audit.audit_evidence_hash == universe_evidence_hash(
        audit.model_dump(exclude={"audit_evidence_hash"})
    )
