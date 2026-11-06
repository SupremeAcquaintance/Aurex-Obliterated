from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

EXPECTED_QUALIFIED_MONTHS_BY_YEAR = {
    "2020": 5,
    "2021": 6,
    "2022": 6,
    "2023": 2,
}
EXPECTED_EXCLUSION_REASON_COUNTS = {
    "EVENT_GAP_EXCEEDS_15_MINUTES": 8,
    "MINUTE_COVERAGE_BELOW_0_99": 1,
    "PRIMARY_ID_DUPLICATE": 1,
    "PRIMARY_ID_NOT_STRICTLY_INCREASING": 8,
    "SINGLE_SKIPPED_TRADE_ID_COUNT_EXCEEDS_100": 6,
    "SKIPPED_TRADE_ID_FRACTION_EXCEEDS_0_001": 4,
    "TIMESTAMP_REGRESSION": 7,
}


class PeriodicFlowSuccessorTerminalAuditV7(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-successor-terminal-audit-v7"
    ] = "aurex-q1-periodic-flow-successor-terminal-audit-v7"
    audit_id: Literal["q1-periodic-flow-successor-terminal-audit-v7"] = (
        "q1-periodic-flow-successor-terminal-audit-v7"
    )
    audited_at: datetime
    status: Literal["COMPLETE_TERMINAL_SOURCE_SUFFICIENCY_AUDIT_NO_OUTCOMES"] = (
        "COMPLETE_TERMINAL_SOURCE_SUFFICIENCY_AUDIT_NO_OUTCOMES"
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
    hard_failure_observed: Literal[False] = False
    completed_month_count: Literal[37] = 37
    inspected_archive_count: Literal[73] = 73
    qualified_paired_month_count: Literal[19] = 19
    excluded_month_count: Literal[18] = 18
    qualified_months_by_year: dict[str, int]
    qualified_quarter_count: Literal[12] = 12
    minimum_required_paired_month_count: Literal[30] = 30
    minimum_required_paired_months_per_year: Literal[6] = 6
    required_quarter_count: Literal[16] = 16
    qualified_2023_months: tuple[Literal["2023-07", "2023-08"], ...] = (
        "2023-07",
        "2023-08",
    )
    spot_archive_exclusion_count: Literal[1] = 1
    usdm_archive_exclusion_count: Literal[17] = 17
    exclusion_reason_counts: dict[str, int]
    request_marker_count: Literal[23] = 23
    response_marker_count: Literal[23] = 23
    request_marker_manifest_hash: str
    pass_response_count: Literal[17] = 17
    transient_response_count: Literal[6] = 6
    partial_archive_count: Literal[0] = 0
    cumulative_payload_bytes_received: Literal[10_171_727_846] = 10_171_727_846
    total_new_archive_bytes: Literal[40_454_714_644] = 40_454_714_644
    total_member_uncompressed_bytes: Literal[368_255_331_172] = 368_255_331_172
    original_corpus_byte_cap: Literal[100_000_000_000] = 100_000_000_000
    original_corpus_byte_cap_respected: Literal[True] = True
    price_or_quantity_values_parsed: tuple[str, ...] = ()
    features_calculated: tuple[str, ...] = ()
    parameters_defined: tuple[str, ...] = ()
    returns_calculated: tuple[str, ...] = ()
    validation_accessed: Literal[False] = False
    holdout_accessed: Literal[False] = False
    strategy_candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    authorizes_measurement_protocol: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    real_net_profit_usd: Literal["0"] = "0"
    decision: Literal["CONFIRM_Q1_SUCCESSOR_SOURCE_SUFFICIENCY_FAILED"] = (
        "CONFIRM_Q1_SUCCESSOR_SOURCE_SUFFICIENCY_FAILED"
    )
    next_authorization: Literal["NONE_SOURCE_SUFFICIENCY_FAILED"] = (
        "NONE_SOURCE_SUFFICIENCY_FAILED"
    )
    findings: tuple[str, ...] = Field(min_length=10)
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
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> PeriodicFlowSuccessorTerminalAuditV7:
        if (
            self.qualified_months_by_year != EXPECTED_QUALIFIED_MONTHS_BY_YEAR
            or self.exclusion_reason_counts != EXPECTED_EXCLUSION_REASON_COUNTS
            or self.qualified_2023_months != ("2023-07", "2023-08")
            or self.qualified_paired_month_count
            >= self.minimum_required_paired_month_count
            or self.qualified_months_by_year["2020"]
            >= self.minimum_required_paired_months_per_year
            or self.qualified_months_by_year["2023"]
            >= self.minimum_required_paired_months_per_year
            or self.qualified_quarter_count == self.required_quarter_count
            or self.total_new_archive_bytes > self.original_corpus_byte_cap
            or self.price_or_quantity_values_parsed
            or self.features_calculated
            or self.parameters_defined
            or self.returns_calculated
            or self.findings != tuple(sorted(set(self.findings)))
        ):
            raise ValueError("Q1 successor v7 terminal audit changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 successor v7 terminal audit hash changed")
        return self


def build_successor_terminal_audit_v7(
    **values,
) -> PeriodicFlowSuccessorTerminalAuditV7:
    payload = dict(values)
    payload["findings"] = tuple(sorted(set(payload["findings"])))
    provisional = PeriodicFlowSuccessorTerminalAuditV7.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    data = provisional.model_dump()
    data["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"audit_evidence_hash"})
    )
    return PeriodicFlowSuccessorTerminalAuditV7.model_validate(data)


def audit_successor_terminal_audit_v7(
    audit: PeriodicFlowSuccessorTerminalAuditV7,
) -> bool:
    return audit.audit_evidence_hash == universe_evidence_hash(
        audit.model_dump(exclude={"audit_evidence_hash"})
    )
