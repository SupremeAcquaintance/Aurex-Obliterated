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


class PeriodicFlowObservedGap(BaseModel):
    preceding_observed_minute_ms: int = Field(ge=0)
    missing_start_minute_ms: int = Field(ge=0)
    missing_end_minute_ms: int = Field(ge=0)
    following_observed_minute_ms: int = Field(ge=0)
    observed_minute_distance: int = Field(gt=1)
    missing_minute_count: int = Field(gt=0)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_gap(self) -> PeriodicFlowObservedGap:
        if (
            self.missing_start_minute_ms != self.preceding_observed_minute_ms + 60_000
            or self.following_observed_minute_ms != self.missing_end_minute_ms + 60_000
            or self.missing_minute_count
            != (self.missing_end_minute_ms - self.missing_start_minute_ms) // 60_000 + 1
            or self.observed_minute_distance != self.missing_minute_count + 1
        ):
            raise ValueError("Q1 terminal-audit gap arithmetic changed")
        return self

    @property
    def key(self) -> tuple[int, int]:
        return self.missing_start_minute_ms, self.missing_end_minute_ms


class PeriodicFlowTerminalAcquisitionAudit(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-full-development-terminal-audit-v1"
    ] = "aurex-q1-periodic-flow-full-development-terminal-audit-v1"
    audit_id: Literal[
        "q1-periodic-flow-full-development-terminal-audit-v1"
    ] = "q1-periodic-flow-full-development-terminal-audit-v1"
    audited_at: datetime
    status: Literal["COMPLETE_TERMINAL_FAILURE_AUDIT_NO_OUTCOMES"] = (
        "COMPLETE_TERMINAL_FAILURE_AUDIT_NO_OUTCOMES"
    )
    result_file_sha256: str
    result_evidence_hash: str
    checkpoint_file_sha256: str
    checkpoint_evidence_hash: str
    protocol_file_sha256: str
    protocol_evidence_hash: str
    execution_contract_file_sha256: str
    execution_contract_evidence_hash: str
    runner_source_hash: str
    auditor_contract_hash: str
    prior_remediation_result_file_sha256: str
    prior_remediation_result_evidence_hash: str
    prior_remediation_audit_file_sha256: str
    prior_remediation_audit_evidence_hash: str
    failed_target_key: Literal["2020-02|SPOT"] = "2020-02|SPOT"
    failed_archive_local_path: str
    failed_archive_sha256: str
    failed_archive_bytes: int = Field(gt=0)
    failed_archive_member_name: str
    failed_archive_row_count: int = Field(gt=0)
    expected_minute_count: int = Field(gt=0)
    unique_minute_count: int = Field(gt=0)
    minute_coverage_fraction: Decimal = Field(gt=0, le=1)
    maximum_event_gap_minutes: int = Field(gt=0)
    maximum_missing_minute_run: int = Field(gt=0)
    event_gap_threshold_minutes: Literal[15] = 15
    observed_gaps: tuple[PeriodicFlowObservedGap, ...] = Field(min_length=1)
    reconstructed_reason_codes: tuple[str, ...]
    frozen_failure_reason: str
    prior_matching_gap_count: int = Field(gt=0)
    prior_quality_conflict_known_before_protocol_freeze: Literal[True] = True
    runtime_preflight_evaluated_checksum_zip_and_disk_only: Literal[True] = True
    runtime_preflight_evaluated_structural_event_gaps: Literal[False] = False
    terminal_result_valid: Literal[True] = True
    terminal_result_resumable: Literal[False] = False
    completed_archive_count: Literal[2] = 2
    completed_paired_month_count: Literal[1] = 1
    request_marker_count: Literal[0] = 0
    response_marker_count: Literal[0] = 0
    cumulative_payload_bytes_received: Literal[0] = 0
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
    decision: Literal["CONFIRM_Q1_V1_TERMINAL_STOP_SOURCE_QUALITY_FAILED"] = (
        "CONFIRM_Q1_V1_TERMINAL_STOP_SOURCE_QUALITY_FAILED"
    )
    next_authorization: Literal[
        "FREEZE_Q1_SUCCESSOR_SOURCE_QUALITY_CENSUS_PROTOCOL_ONLY"
    ] = "FREEZE_Q1_SUCCESSOR_SOURCE_QUALITY_CENSUS_PROTOCOL_ONLY"
    findings: tuple[str, ...] = Field(min_length=5)
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
        "execution_contract_file_sha256",
        "execution_contract_evidence_hash",
        "runner_source_hash",
        "auditor_contract_hash",
        "prior_remediation_result_file_sha256",
        "prior_remediation_result_evidence_hash",
        "prior_remediation_audit_file_sha256",
        "prior_remediation_audit_evidence_hash",
        "failed_archive_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> PeriodicFlowTerminalAcquisitionAudit:
        if (
            self.unique_minute_count > self.expected_minute_count
            or self.minute_coverage_fraction
            != Decimal(self.unique_minute_count) / Decimal(self.expected_minute_count)
            or list(self.observed_gaps)
            != sorted(self.observed_gaps, key=lambda item: item.key)
            or len({item.key for item in self.observed_gaps}) != len(self.observed_gaps)
            or self.maximum_event_gap_minutes
            != max(item.observed_minute_distance for item in self.observed_gaps)
            or self.maximum_missing_minute_run
            != max(item.missing_minute_count for item in self.observed_gaps)
            or self.maximum_event_gap_minutes <= self.event_gap_threshold_minutes
            or self.reconstructed_reason_codes != ("EVENT_GAP_EXCEEDS_15_MINUTES",)
            or self.frozen_failure_reason
            != "Archive structural gates failed: ('EVENT_GAP_EXCEEDS_15_MINUTES',)"
            or self.prior_matching_gap_count != len(self.observed_gaps)
            or self.price_or_quantity_values_parsed
            or self.features_calculated
            or self.parameters_defined
            or self.returns_calculated
            or self.findings != tuple(sorted(set(self.findings)))
        ):
            raise ValueError("Q1 terminal acquisition audit changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 terminal acquisition audit hash changed")
        return self


def build_terminal_acquisition_audit(**values) -> PeriodicFlowTerminalAcquisitionAudit:
    payload = dict(values)
    payload["observed_gaps"] = tuple(
        sorted(payload["observed_gaps"], key=lambda item: item.key)
    )
    payload["findings"] = tuple(sorted(set(payload["findings"])))
    provisional = PeriodicFlowTerminalAcquisitionAudit.model_construct(
        **payload,
        audit_evidence_hash="0" * 64,
    )
    data = provisional.model_dump()
    data["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"audit_evidence_hash"})
    )
    return PeriodicFlowTerminalAcquisitionAudit.model_validate(data)


def audit_terminal_acquisition_audit(
    audit: PeriodicFlowTerminalAcquisitionAudit,
) -> bool:
    return audit.audit_evidence_hash == universe_evidence_hash(
        audit.model_dump(exclude={"audit_evidence_hash"})
    )
