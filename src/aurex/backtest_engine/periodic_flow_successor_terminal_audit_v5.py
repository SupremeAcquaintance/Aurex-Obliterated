from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)


class PeriodicFlowInterleavedRowProbeV5(BaseModel):
    ordinal: int = Field(ge=1, le=6)
    primary_id: int = Field(ge=0)
    timestamp_ms: int = Field(gt=0)

    model_config = ConfigDict(extra="forbid", frozen=True)


class PeriodicFlowSuccessorTerminalAuditV5(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-terminal-audit-v5"
    ] = "aurex-q1-periodic-flow-successor-terminal-audit-v5"
    audit_id: Literal["q1-periodic-flow-successor-terminal-audit-v5"] = (
        "q1-periodic-flow-successor-terminal-audit-v5"
    )
    audited_at: datetime
    status: Literal["COMPLETE_TERMINAL_VALIDATOR_AUDIT_NO_OUTCOMES"] = (
        "COMPLETE_TERMINAL_VALIDATOR_AUDIT_NO_OUTCOMES"
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
    failed_target_key: Literal["2023-01|USD_M_PERPETUAL"] = (
        "2023-01|USD_M_PERPETUAL"
    )
    frozen_failure_reason: str = Field(min_length=1, max_length=1500)
    failed_archive_relative_path: Literal[
        "q1_periodic_flow_successor_acquisition_v5/BTCUSDT/2023-01/"
        "trades/BTCUSDT-trades-2023-01.zip"
    ]
    failed_archive_bytes: Literal[797_254_027] = 797_254_027
    failed_archive_sha256: Literal[
        "d5c30a110f8f40c375cfef5b4fff922a1f21eeac58e53899d05166baaff2ca2d"
    ] = "d5c30a110f8f40c375cfef5b4fff922a1f21eeac58e53899d05166baaff2ca2d"
    published_archive_sha256: Literal[
        "d5c30a110f8f40c375cfef5b4fff922a1f21eeac58e53899d05166baaff2ca2d"
    ] = "d5c30a110f8f40c375cfef5b4fff922a1f21eeac58e53899d05166baaff2ca2d"
    request_file_sha256: str
    response_file_sha256: str
    response_status: Literal[200] = 200
    response_outcome: Literal["PASS"] = "PASS"
    response_bytes_received: Literal[797_254_027] = 797_254_027
    selected_member_name: Literal["BTCUSDT-trades-2023-01.csv"] = (
        "BTCUSDT-trades-2023-01.csv"
    )
    interleaved_row_probe: tuple[PeriodicFlowInterleavedRowProbeV5, ...] = Field(
        min_length=6, max_length=6
    )
    probe_primary_id_regression_count: Literal[2] = 2
    probe_timestamp_regression_count: Literal[2] = 2
    invalid_computed_skipped_fraction: Literal[
        "16867608.08325330886319725218"
    ] = "16867608.08325330886319725218"
    defect_class: Literal[
        "ORDER_DEPENDENT_GAP_METRIC_APPLIED_TO_NON_MONOTONIC_SOURCE_ROWS"
    ] = "ORDER_DEPENDENT_GAP_METRIC_APPLIED_TO_NON_MONOTONIC_SOURCE_ROWS"
    source_archive_integrity_failure_observed: Literal[False] = False
    transport_failure_observed: Literal[False] = False
    validator_evidence_model_failure_observed: Literal[True] = True
    request_marker_count: Literal[6] = 6
    response_marker_count: Literal[6] = 6
    request_marker_manifest_hash: str
    cumulative_payload_bytes_received: Literal[5_260_608_134] = 5_260_608_134
    inspected_archive_count: Literal[51] = 51
    qualified_paired_month_count: Literal[17] = 17
    excluded_month_count: Literal[8] = 8
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
    decision: Literal["CONFIRM_Q1_SUCCESSOR_V5_TERMINAL_VALIDATOR_STOP"] = (
        "CONFIRM_Q1_SUCCESSOR_V5_TERMINAL_VALIDATOR_STOP"
    )
    next_authorization: Literal[
        "FREEZE_Q1_SUCCESSOR_VALIDATOR_V6_CONTINUATION_ONLY"
    ] = "FREEZE_Q1_SUCCESSOR_VALIDATOR_V6_CONTINUATION_ONLY"
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
        "transport_amendment_file_sha256",
        "transport_amendment_evidence_hash",
        "execution_contract_file_sha256",
        "execution_contract_evidence_hash",
        "execution_contract_audit_file_sha256",
        "execution_contract_audit_evidence_hash",
        "runner_source_hash",
        "auditor_contract_hash",
        "request_file_sha256",
        "response_file_sha256",
        "request_marker_manifest_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> PeriodicFlowSuccessorTerminalAuditV5:
        expected_probe = (
            (1, 3_166_744_581, 1_672_531_204_118),
            (2, 3_227_590_792, 1_674_604_940_087),
            (3, 3_166_744_582, 1_672_531_204_178),
            (4, 3_227_590_793, 1_674_604_940_100),
            (5, 3_166_744_583, 1_672_531_204_178),
            (6, 3_227_590_794, 1_674_604_940_118),
        )
        observed_probe = tuple(
            (item.ordinal, item.primary_id, item.timestamp_ms)
            for item in self.interleaved_row_probe
        )
        if (
            observed_probe != expected_probe
            or "less_than_equal" not in self.frozen_failure_reason
            or self.failed_archive_sha256 != self.published_archive_sha256
            or self.price_or_quantity_values_parsed
            or self.features_calculated
            or self.parameters_defined
            or self.returns_calculated
            or self.findings != tuple(sorted(set(self.findings)))
        ):
            raise ValueError("Q1 successor v5 terminal audit changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 successor v5 terminal audit hash changed")
        return self


def build_successor_terminal_audit_v5(
    **values,
) -> PeriodicFlowSuccessorTerminalAuditV5:
    payload = dict(values)
    payload["findings"] = tuple(sorted(set(payload["findings"])))
    provisional = PeriodicFlowSuccessorTerminalAuditV5.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    data = provisional.model_dump()
    data["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"audit_evidence_hash"})
    )
    return PeriodicFlowSuccessorTerminalAuditV5.model_validate(data)


def audit_successor_terminal_audit_v5(
    audit: PeriodicFlowSuccessorTerminalAuditV5,
) -> bool:
    return audit.audit_evidence_hash == universe_evidence_hash(
        audit.model_dump(exclude={"audit_evidence_hash"})
    )
