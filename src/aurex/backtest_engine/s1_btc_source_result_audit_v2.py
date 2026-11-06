from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)


class S1BtcSourceAcquisitionAuditV2(BaseModel):
    schema_version: Literal["aurex-s1-btc-source-acquisition-audit-v2"] = (
        "aurex-s1-btc-source-acquisition-audit-v2"
    )
    audit_id: Literal["s1-btc-source-acquisition-audit-v2"] = (
        "s1-btc-source-acquisition-audit-v2"
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
    dataset_file_sha256: str
    dataset_bytes: Literal[209909] = 209_909
    runner_contract_hash: str
    auditor_source_sha256: str
    reconstructed_exactly: Literal[True] = True
    classified_target_count: Literal[277] = 277
    complete_target_count: Literal[277] = 277
    reused_target_count: Literal[22] = 22
    network_target_count: Literal[255] = 255
    network_request_count: Literal[510] = 510
    network_body_bytes: Literal[429427] = 429_427
    persisted_source_bytes: Literal[463905] = 463_905
    delayed_activation_target_count: Literal[1] = 1
    maximum_activation_delay_minutes_observed: Literal[600] = 600
    delayed_target_id: Literal["022-btcusdt-1h-2018-02-09"] = (
        "022-btcusdt-1h-2018-02-09"
    )
    delayed_target_selected_open_time_ms: Literal[1518170400000] = 1_518_170_400_000
    price_rows_reconstructed: Literal[277] = 277
    returns_calculated: Literal[0] = 0
    strategy_outcomes_calculated: Literal[0] = 0
    validation_values_read: Literal[0] = 0
    holdout_values_read: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["PASS_S1_1_BTC_SOURCE_ACQUISITION_RECONSTRUCTED"] = (
        "PASS_S1_1_BTC_SOURCE_ACQUISITION_RECONSTRUCTED"
    )
    next_authorization: Literal[
        "AUTHORIZE_S1_1_DEVELOPMENT_OUTCOME_PROTOCOL_ONLY"
    ] = "AUTHORIZE_S1_1_DEVELOPMENT_OUTCOME_PROTOCOL_ONLY"
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
        "dataset_file_sha256",
        "runner_contract_hash",
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S1BtcSourceAcquisitionAuditV2:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1.1 source acquisition audit hash changed")
        return self
