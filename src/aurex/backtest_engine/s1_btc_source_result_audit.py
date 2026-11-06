from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)


class S1BtcSourceAcquisitionAudit(BaseModel):
    schema_version: Literal["aurex-s1-btc-source-acquisition-audit-v1"] = (
        "aurex-s1-btc-source-acquisition-audit-v1"
    )
    audit_id: Literal["s1-btc-source-acquisition-audit-v1"] = (
        "s1-btc-source-acquisition-audit-v1"
    )
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    execution_contract_file_sha256: str
    execution_contract_evidence_hash: str
    checkpoint_file_sha256: str
    checkpoint_evidence_hash: str
    result_file_sha256: str
    result_evidence_hash: str
    runner_contract_hash: str
    auditor_source_sha256: str
    reconstructed_exactly: Literal[True] = True
    classified_target_count: Literal[22] = 22
    complete_target_count: Literal[21] = 21
    failed_target_count: Literal[1] = 1
    network_request_count: Literal[44] = 44
    failed_target_id: Literal["022-btcusdt-1h-2018-02-09"] = (
        "022-btcusdt-1h-2018-02-09"
    )
    failed_target_expected_open_time_ms: Literal[1518134400000] = 1_518_134_400_000
    failed_target_first_observed_open_time_ms: Literal[1518170400000] = 1_518_170_400_000
    failed_target_last_observed_open_time_ms: Literal[1518217200000] = 1_518_217_200_000
    failed_target_observed_row_count: Literal[14] = 14
    failed_target_exact_open_occurrence_count: Literal[0] = 0
    diagnosed_failure: Literal["MISSING_EXACT_00_00_UTC_TARGET_OPEN"] = (
        "MISSING_EXACT_00_00_UTC_TARGET_OPEN"
    )
    published_checksum_verified: Literal[True] = True
    zip_member_policy_verified: Literal[True] = True
    twelve_column_rows_verified: Literal[True] = True
    open_times_unique_increasing_within_date: Literal[True] = True
    btc_price_values_read_during_audit: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    strategy_outcomes_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["CONFIRM_S1_BTC_SOURCE_ACQUISITION_FAILED_SOURCE_GAP"] = (
        "CONFIRM_S1_BTC_SOURCE_ACQUISITION_FAILED_SOURCE_GAP"
    )
    lineage_next_authorization: Literal[
        "NONE_S1_BTCUSDT_DAILY_1H_SOURCE_ACQUISITION_FAILED"
    ] = "NONE_S1_BTCUSDT_DAILY_1H_SOURCE_ACQUISITION_FAILED"
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "execution_contract_file_sha256",
        "execution_contract_evidence_hash",
        "checkpoint_file_sha256",
        "checkpoint_evidence_hash",
        "result_file_sha256",
        "result_evidence_hash",
        "runner_contract_hash",
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S1BtcSourceAcquisitionAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1 BTC source acquisition audit hash changed")
        return self
