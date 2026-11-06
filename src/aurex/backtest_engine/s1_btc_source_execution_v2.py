from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s1_btc_source_execution import S1BtcResourceAttempt
from aurex.backtest_engine.s1_btc_source_v2 import S1_1_SOURCE_GATES
from aurex.backtest_engine.s1_source_feasibility import S1SourceGate
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S1_1_EXECUTION_NEXT = "AUTHORIZE_S1_1_BTC_SOURCE_ACQUISITION"
S1_1_ACQUISITION_PASS = "PASS_S1_1_BTC_SOURCE_ACQUISITION"
S1_1_ACQUISITION_STOP = "STOP_S1_1_BTC_SOURCE_ACQUISITION_FAILED"
S1_1_ACQUISITION_NEXT = "AUTHORIZE_S1_1_DEVELOPMENT_OUTCOME_PROTOCOL_ONLY"


def validate_positive_decimal(value: str) -> str:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("S1.1 selected open is not a decimal") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError("S1.1 selected open must be positive and finite")
    return value


class S1BtcArchiveSummaryV2(BaseModel):
    member_name: str
    csv_row_count: int = Field(ge=1, le=1000)
    data_row_count: int = Field(ge=1, le=1000)
    header_present: bool
    first_open_time_ms: int = Field(ge=1)
    last_open_time_ms: int = Field(ge=1)
    selected_open_time_ms: int = Field(ge=1)
    activation_delay_minutes: int = Field(ge=0, le=1439)
    duplicate_open_time_count: Literal[0] = 0
    non_increasing_open_time_count: Literal[0] = 0
    outside_target_date_count: Literal[0] = 0
    uncompressed_csv_bytes: int = Field(ge=1, le=1_000_000)
    summary_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("summary_evidence_hash")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_summary(self) -> S1BtcArchiveSummaryV2:
        if (
            self.selected_open_time_ms != self.first_open_time_ms
            or self.last_open_time_ms < self.first_open_time_ms
        ):
            raise ValueError("S1.1 selected open is not the first observed bar")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"summary_evidence_hash"})
        )
        if self.summary_evidence_hash != expected:
            raise ValueError("S1.1 archive summary hash changed")
        return self


class S1BtcPriceRowV2(BaseModel):
    sequence: int = Field(ge=1, le=277)
    feature_sequence: int = Field(ge=5, le=281)
    target_date: date
    target_open_time_ms: int = Field(ge=1)
    selected_open_time_ms: int = Field(ge=1)
    activation_delay_minutes: int = Field(ge=0, le=1439)
    symbol: Literal["BTCUSDT"] = "BTCUSDT"
    interval: Literal["1h"] = "1h"
    price_field: Literal["OPEN"] = "OPEN"
    selection_rule: Literal[
        "EARLIEST_1H_KLINE_OPEN_WITHIN_TARGET_FRIDAY"
    ] = "EARLIEST_1H_KLINE_OPEN_WITHIN_TARGET_FRIDAY"
    open_price: str
    archive_file_sha256: str
    published_archive_sha256: str
    checksum_file_sha256: str
    source_target_id: str
    price_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("open_price")
    @classmethod
    def validate_price(cls, value: str) -> str:
        return validate_positive_decimal(value)

    @field_validator(
        "archive_file_sha256",
        "published_archive_sha256",
        "checksum_file_sha256",
        "price_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_row(self) -> S1BtcPriceRowV2:
        delay_ms = self.selected_open_time_ms - self.target_open_time_ms
        if delay_ms != self.activation_delay_minutes * 60_000:
            raise ValueError("S1.1 activation delay changed")
        if self.archive_file_sha256 != self.published_archive_sha256:
            raise ValueError("S1.1 price row is not checksum-bound")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"price_evidence_hash"})
        )
        if self.price_evidence_hash != expected:
            raise ValueError("S1.1 price-row hash changed")
        return self


class S1BtcTargetEvidenceV2(BaseModel):
    sequence: int = Field(ge=1, le=277)
    target_id: str
    target_date: date
    outcome: Literal["COMPLETE", "FAILED"]
    source_mode: Literal["V1_EXACT_HASH_REUSE", "NETWORK"]
    attempts: tuple[S1BtcResourceAttempt, ...] = Field(max_length=6)
    archive_path: str | None = None
    archive_file_sha256: str | None = None
    archive_bytes: int = Field(ge=0, le=200000)
    checksum_path: str | None = None
    checksum_file_sha256: str | None = None
    checksum_bytes: int = Field(ge=0, le=512)
    published_archive_sha256: str | None = None
    archive_summary: S1BtcArchiveSummaryV2 | None = None
    price_row: S1BtcPriceRowV2 | None = None
    failure_gate: str | None = None
    target_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "archive_file_sha256",
        "checksum_file_sha256",
        "published_archive_sha256",
        "target_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str | None) -> str | None:
        return None if value is None else normalize_sha256(value)

    @model_validator(mode="after")
    def validate_target(self) -> S1BtcTargetEvidenceV2:
        if self.source_mode == "V1_EXACT_HASH_REUSE" and self.attempts:
            raise ValueError("S1.1 reuse cannot claim v2 network attempts")
        for kind in ("CHECKSUM", "ARCHIVE"):
            attempts = [item for item in self.attempts if item.resource_kind == kind]
            if tuple(item.attempt for item in attempts) != tuple(
                range(1, len(attempts) + 1)
            ):
                raise ValueError("S1.1 attempt sequence changed")
        complete_fields = (
            self.archive_path,
            self.archive_file_sha256,
            self.checksum_path,
            self.checksum_file_sha256,
            self.published_archive_sha256,
            self.archive_summary,
            self.price_row,
        )
        if self.outcome == "COMPLETE" and (
            any(value is None for value in complete_fields)
            or self.archive_bytes == 0
            or self.checksum_bytes == 0
            or self.failure_gate is not None
        ):
            raise ValueError("Complete S1.1 target evidence is incomplete")
        if self.outcome == "FAILED" and not self.failure_gate:
            raise ValueError("Failed S1.1 target requires a failure gate")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"target_evidence_hash"})
        )
        if self.target_evidence_hash != expected:
            raise ValueError("S1.1 target evidence hash changed")
        return self


class S1BtcSourceExecutionContractV2(BaseModel):
    schema_version: Literal["aurex-s1-btc-source-execution-contract-v2"] = (
        "aurex-s1-btc-source-execution-contract-v2"
    )
    contract_id: Literal["s1-btc-source-execution-contract-v2"] = (
        "s1-btc-source-execution-contract-v2"
    )
    frozen_at: datetime
    builder_contract_hash: str
    protocol_file_sha256: str
    protocol_evidence_hash: str
    protocol_audit_file_sha256: str
    protocol_audit_evidence_hash: str
    runner_contract_hash: str
    v1_transport_dependency_file_sha256: str
    evidence_root: Literal[
        "data/evidence/source_snapshots/s1_btcusdt_daily_1h_v1"
    ] = "data/evidence/source_snapshots/s1_btcusdt_daily_1h_v1"
    reuse_target_count: Literal[22] = 22
    network_target_count: Literal[255] = 255
    free_disk_bytes_observed: int = Field(ge=250_000_000)
    maximum_network_requests: Literal[1530] = 1530
    maximum_total_payload_bytes: Literal[51130560] = 51_130_560
    maximum_uncompressed_csv_bytes: Literal[1000000] = 1_000_000
    synthetic_test_ids: tuple[str, ...] = Field(min_length=10)
    authorizes_network_acquisition: Literal[True] = True
    authorizes_execution_price_values_only: Literal[True] = True
    authorizes_return_testing: Literal[False] = False
    authorizes_validation_access: Literal[False] = False
    authorizes_holdout_access: Literal[False] = False
    authorizes_candidate_outcome: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    next_authorization: Literal["AUTHORIZE_S1_1_BTC_SOURCE_ACQUISITION"] = (
        S1_1_EXECUTION_NEXT
    )
    contract_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "protocol_audit_file_sha256",
        "protocol_audit_evidence_hash",
        "runner_contract_hash",
        "v1_transport_dependency_file_sha256",
        "contract_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_contract(self) -> S1BtcSourceExecutionContractV2:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"contract_evidence_hash"})
        )
        if self.contract_evidence_hash != expected:
            raise ValueError("S1.1 execution contract hash changed")
        return self


class S1BtcSourceExecutionAuditV2(BaseModel):
    schema_version: Literal["aurex-s1-btc-source-execution-audit-v2"] = (
        "aurex-s1-btc-source-execution-audit-v2"
    )
    audit_id: Literal["s1-btc-source-execution-audit-v2"] = (
        "s1-btc-source-execution-audit-v2"
    )
    audited_at: datetime
    contract_file_sha256: str
    contract_evidence_hash: str
    protocol_evidence_hash: str
    runner_contract_hash: str
    auditor_source_sha256: str
    synthetic_test_ids: tuple[str, ...] = Field(min_length=10)
    reconstructed_exactly: Literal[True] = True
    network_requests_observed: Literal[0] = 0
    payload_bytes_observed: Literal[0] = 0
    new_btc_market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    decision: Literal["PASS_S1_1_BTC_EXECUTION_CONTRACT_RECONSTRUCTED"] = (
        "PASS_S1_1_BTC_EXECUTION_CONTRACT_RECONSTRUCTED"
    )
    next_authorization: Literal["AUTHORIZE_S1_1_BTC_SOURCE_ACQUISITION"] = (
        S1_1_EXECUTION_NEXT
    )
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "contract_file_sha256",
        "contract_evidence_hash",
        "protocol_evidence_hash",
        "runner_contract_hash",
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S1BtcSourceExecutionAuditV2:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1.1 execution audit hash changed")
        return self


class S1BtcAcquisitionCheckpointV2(BaseModel):
    schema_version: Literal["aurex-s1-btc-acquisition-checkpoint-v2"] = (
        "aurex-s1-btc-acquisition-checkpoint-v2"
    )
    checkpoint_id: Literal["s1-btc-acquisition-checkpoint-v2"] = (
        "s1-btc-acquisition-checkpoint-v2"
    )
    started_at: datetime
    updated_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    execution_contract_file_sha256: str
    execution_contract_evidence_hash: str
    runner_contract_hash: str
    target_evidence: tuple[S1BtcTargetEvidenceV2, ...] = ()
    classified_target_count: int = Field(ge=0, le=277)
    complete_target_count: int = Field(ge=0, le=277)
    failed_target_count: int = Field(ge=0, le=1)
    reused_target_count: int = Field(ge=0, le=22)
    network_target_count: int = Field(ge=0, le=255)
    network_request_count: int = Field(ge=0, le=1530)
    network_body_bytes: int = Field(ge=0, le=51_130_560)
    persisted_source_bytes: int = Field(ge=0, le=55_541_824)
    next_sequence: int | None = Field(default=None, ge=1, le=277)
    terminal: bool
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    checkpoint_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("started_at", "updated_at")
    @classmethod
    def normalize_times(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "execution_contract_file_sha256",
        "execution_contract_evidence_hash",
        "runner_contract_hash",
        "checkpoint_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_checkpoint(self) -> S1BtcAcquisitionCheckpointV2:
        if tuple(item.sequence for item in self.target_evidence) != tuple(
            range(1, len(self.target_evidence) + 1)
        ):
            raise ValueError("S1.1 checkpoint sequence changed")
        if self.classified_target_count != len(self.target_evidence):
            raise ValueError("S1.1 checkpoint classified count changed")
        if self.complete_target_count != sum(
            item.outcome == "COMPLETE" for item in self.target_evidence
        ):
            raise ValueError("S1.1 checkpoint complete count changed")
        if self.failed_target_count != sum(
            item.outcome == "FAILED" for item in self.target_evidence
        ):
            raise ValueError("S1.1 checkpoint failed count changed")
        if self.reused_target_count != sum(
            item.source_mode == "V1_EXACT_HASH_REUSE" for item in self.target_evidence
        ):
            raise ValueError("S1.1 checkpoint reuse count changed")
        if self.network_target_count != sum(
            item.source_mode == "NETWORK" for item in self.target_evidence
        ):
            raise ValueError("S1.1 checkpoint network target count changed")
        if self.network_request_count != sum(
            len(item.attempts) for item in self.target_evidence
        ):
            raise ValueError("S1.1 checkpoint request count changed")
        expected_next = (
            None
            if self.terminal or self.classified_target_count == 277
            else self.classified_target_count + 1
        )
        if self.next_sequence != expected_next:
            raise ValueError("S1.1 checkpoint next sequence changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"checkpoint_evidence_hash"})
        )
        if self.checkpoint_evidence_hash != expected:
            raise ValueError("S1.1 checkpoint hash changed")
        return self


class S1BtcSourceAcquisitionResultV2(BaseModel):
    schema_version: Literal["aurex-s1-btc-source-acquisition-result-v2"] = (
        "aurex-s1-btc-source-acquisition-result-v2"
    )
    result_id: Literal["s1-btc-source-acquisition-result-v2"] = (
        "s1-btc-source-acquisition-result-v2"
    )
    completed_at: datetime
    checkpoint_file_sha256: str
    checkpoint_evidence_hash: str
    protocol_evidence_hash: str
    execution_contract_evidence_hash: str
    runner_contract_hash: str
    target_evidence: tuple[S1BtcTargetEvidenceV2, ...] = Field(min_length=1)
    price_rows: tuple[S1BtcPriceRowV2, ...] = ()
    gates: tuple[S1SourceGate, ...] = Field(min_length=11, max_length=11)
    classified_target_count: int = Field(ge=1, le=277)
    complete_target_count: int = Field(ge=0, le=277)
    failed_target_count: int = Field(ge=0, le=1)
    reused_target_count: int = Field(ge=0, le=22)
    network_target_count: int = Field(ge=0, le=255)
    network_request_count: int = Field(ge=0, le=1530)
    network_body_bytes: int = Field(ge=0, le=51_130_560)
    persisted_source_bytes: int = Field(ge=0, le=55_541_824)
    maximum_activation_delay_minutes_observed: int = Field(ge=0, le=1439)
    delayed_activation_target_count: int = Field(ge=0, le=277)
    dataset_path: str | None = None
    dataset_file_sha256: str | None = None
    dataset_bytes: int = Field(ge=0)
    decision: Literal[
        "PASS_S1_1_BTC_SOURCE_ACQUISITION",
        "STOP_S1_1_BTC_SOURCE_ACQUISITION_FAILED",
    ]
    next_authorization: Literal[
        "AUTHORIZE_S1_1_DEVELOPMENT_OUTCOME_PROTOCOL_ONLY",
        "NONE_S1_1_BTC_SOURCE_ACQUISITION_FAILED",
    ]
    returns_calculated: Literal[0] = 0
    strategy_outcomes_calculated: Literal[0] = 0
    validation_values_read: Literal[0] = 0
    holdout_values_read: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("completed_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "checkpoint_file_sha256",
        "checkpoint_evidence_hash",
        "protocol_evidence_hash",
        "execution_contract_evidence_hash",
        "runner_contract_hash",
        "dataset_file_sha256",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str | None) -> str | None:
        return None if value is None else normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> S1BtcSourceAcquisitionResultV2:
        gate_ids = tuple(sorted(item.gate_id for item in self.gates))
        if gate_ids != tuple(sorted(S1_1_SOURCE_GATES)):
            raise ValueError("S1.1 result gates changed")
        passed = self.decision == S1_1_ACQUISITION_PASS
        if passed and (
            self.classified_target_count != 277
            or self.complete_target_count != 277
            or len(self.price_rows) != 277
            or self.dataset_path is None
            or self.dataset_file_sha256 is None
            or self.dataset_bytes == 0
            or any(gate.status != "PASS" for gate in self.gates)
        ):
            raise ValueError("Passing S1.1 result is incomplete")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("S1.1 acquisition result hash changed")
        return self
