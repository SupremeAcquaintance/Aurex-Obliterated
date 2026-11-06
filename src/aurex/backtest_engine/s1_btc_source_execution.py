from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s1_btc_source_acquisition import S1_BTC_SOURCE_GATES
from aurex.backtest_engine.s1_source_feasibility import S1SourceGate
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S1_BTC_EXECUTION_NEXT = "AUTHORIZE_S1_BTCUSDT_DAILY_1H_SOURCE_ACQUISITION"
S1_BTC_ACQUISITION_PASS = "PASS_S1_BTCUSDT_DAILY_1H_SOURCE_ACQUISITION"
S1_BTC_ACQUISITION_STOP = "STOP_S1_BTCUSDT_DAILY_1H_SOURCE_ACQUISITION_FAILED"
S1_BTC_ACQUISITION_NEXT = "AUTHORIZE_S1_DEVELOPMENT_OUTCOME_EXECUTION_PROTOCOL_ONLY"


def normalize_positive_decimal_text(value: str) -> str:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("S1 BTC open price is not a decimal") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError("S1 BTC open price must be positive and finite")
    return value


class S1BtcResourceAttempt(BaseModel):
    sequence: int = Field(ge=1, le=277)
    resource_kind: Literal["CHECKSUM", "ARCHIVE"]
    attempt: int = Field(ge=1, le=3)
    requested_at: datetime
    completed_at: datetime
    url: str = Field(min_length=30)
    status_code: int | None = Field(default=None, ge=100, le=599)
    final_url: str | None = None
    final_host: str | None = None
    content_type: str | None = None
    bytes_received: int = Field(ge=0, le=200000)
    body_sha256: str | None = None
    outcome: Literal["COMPLETE", "TRANSIENT_FAILURE", "PERMANENT_FAILURE"]
    error_type: str | None = None
    error_message: str | None = None
    request_marker_path: str = Field(min_length=10)
    request_marker_sha256: str
    response_marker_path: str = Field(min_length=10)
    response_marker_sha256: str
    attempt_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("requested_at", "completed_at")
    @classmethod
    def normalize_times(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "body_sha256",
        "request_marker_sha256",
        "response_marker_sha256",
        "attempt_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str | None) -> str | None:
        return None if value is None else normalize_sha256(value)

    @model_validator(mode="after")
    def validate_attempt(self) -> S1BtcResourceAttempt:
        if self.completed_at < self.requested_at:
            raise ValueError("S1 BTC attempt completion precedes its request")
        cap = 512 if self.resource_kind == "CHECKSUM" else 200_000
        if self.bytes_received > cap:
            raise ValueError("S1 BTC resource attempt exceeded its frozen byte cap")
        if self.outcome == "COMPLETE" and (
            self.status_code != 200
            or self.bytes_received == 0
            or self.body_sha256 is None
            or self.error_type is not None
        ):
            raise ValueError("Complete S1 BTC resource attempt is incomplete")
        if self.outcome != "COMPLETE" and not self.error_type:
            raise ValueError("Failed S1 BTC resource attempt requires an error type")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"attempt_evidence_hash"})
        )
        if self.attempt_evidence_hash != expected:
            raise ValueError("S1 BTC resource-attempt evidence hash changed")
        return self


class S1BtcArchiveSummary(BaseModel):
    member_name: str
    csv_row_count: int = Field(ge=1, le=1000)
    data_row_count: int = Field(ge=1, le=1000)
    header_present: bool
    first_open_time_ms: int = Field(ge=1)
    last_open_time_ms: int = Field(ge=1)
    target_open_occurrence_count: int = Field(ge=0, le=1)
    duplicate_open_time_count: int = Field(ge=0)
    non_increasing_open_time_count: int = Field(ge=0)
    outside_target_date_count: int = Field(ge=0)
    uncompressed_csv_bytes: int = Field(ge=1, le=1_000_000)
    summary_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("summary_evidence_hash")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_summary(self) -> S1BtcArchiveSummary:
        if self.last_open_time_ms < self.first_open_time_ms:
            raise ValueError("S1 BTC archive time bounds changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"summary_evidence_hash"})
        )
        if self.summary_evidence_hash != expected:
            raise ValueError("S1 BTC archive-summary evidence hash changed")
        return self


class S1BtcPriceRow(BaseModel):
    sequence: int = Field(ge=1, le=277)
    feature_sequence: int = Field(ge=5, le=281)
    activation_date: date
    activation_open_time_ms: int = Field(ge=1)
    symbol: Literal["BTCUSDT"] = "BTCUSDT"
    interval: Literal["1h"] = "1h"
    price_field: Literal["OPEN"] = "OPEN"
    open_price: str
    archive_file_sha256: str
    published_archive_sha256: str
    checksum_file_sha256: str
    source_target_id: str = Field(min_length=20)
    price_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("open_price")
    @classmethod
    def validate_price(cls, value: str) -> str:
        return normalize_positive_decimal_text(value)

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
    def validate_row(self) -> S1BtcPriceRow:
        if self.archive_file_sha256 != self.published_archive_sha256:
            raise ValueError("S1 BTC price row is not bound to the published checksum")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"price_evidence_hash"})
        )
        if self.price_evidence_hash != expected:
            raise ValueError("S1 BTC price-row evidence hash changed")
        return self


class S1BtcTargetEvidence(BaseModel):
    sequence: int = Field(ge=1, le=277)
    target_id: str = Field(min_length=20)
    activation_date: date
    outcome: Literal["COMPLETE", "FAILED"]
    source_mode: Literal["NETWORK", "LOCAL_REUSE"]
    attempts: tuple[S1BtcResourceAttempt, ...] = Field(max_length=6)
    archive_path: str | None = None
    archive_file_sha256: str | None = None
    archive_bytes: int = Field(ge=0, le=200000)
    checksum_path: str | None = None
    checksum_file_sha256: str | None = None
    checksum_bytes: int = Field(ge=0, le=512)
    published_archive_sha256: str | None = None
    archive_summary: S1BtcArchiveSummary | None = None
    price_row: S1BtcPriceRow | None = None
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
    def validate_target(self) -> S1BtcTargetEvidence:
        for kind in ("CHECKSUM", "ARCHIVE"):
            attempts = [item for item in self.attempts if item.resource_kind == kind]
            if tuple(item.attempt for item in attempts) != tuple(
                range(1, len(attempts) + 1)
            ):
                raise ValueError("S1 BTC resource attempt sequence changed")
        if any(item.sequence != self.sequence for item in self.attempts):
            raise ValueError("S1 BTC attempt target sequence changed")
        if self.source_mode == "LOCAL_REUSE" and self.attempts:
            raise ValueError("S1 BTC local reuse cannot claim network attempts")
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
            raise ValueError("Complete S1 BTC target evidence is incomplete")
        if self.outcome == "FAILED" and not self.failure_gate:
            raise ValueError("Failed S1 BTC target requires a failure gate")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"target_evidence_hash"})
        )
        if self.target_evidence_hash != expected:
            raise ValueError("S1 BTC target evidence hash changed")
        return self


class S1BtcSourceExecutionContract(BaseModel):
    schema_version: Literal["aurex-s1-btc-source-execution-contract-v1"] = (
        "aurex-s1-btc-source-execution-contract-v1"
    )
    contract_id: Literal["s1-btc-source-execution-contract-v1"] = (
        "s1-btc-source-execution-contract-v1"
    )
    frozen_at: datetime
    builder_contract_hash: str
    protocol_file_sha256: str
    protocol_evidence_hash: str
    protocol_audit_file_sha256: str
    protocol_audit_evidence_hash: str
    runner_contract_hash: str
    evidence_root: Literal[
        "data/evidence/source_snapshots/s1_btcusdt_daily_1h_v1"
    ] = "data/evidence/source_snapshots/s1_btcusdt_daily_1h_v1"
    evidence_root_was_absent_or_empty: Literal[True] = True
    free_disk_bytes_observed: int = Field(ge=250_000_000)
    target_count: Literal[277] = 277
    maximum_network_requests: Literal[1662] = 1662
    maximum_total_payload_bytes: Literal[55541824] = 55_541_824
    maximum_uncompressed_csv_bytes: Literal[1000000] = 1_000_000
    synthetic_test_ids: tuple[str, ...] = Field(min_length=8)
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
    next_authorization: Literal[
        "AUTHORIZE_S1_BTCUSDT_DAILY_1H_SOURCE_ACQUISITION"
    ] = S1_BTC_EXECUTION_NEXT
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
        "contract_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_contract(self) -> S1BtcSourceExecutionContract:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"contract_evidence_hash"})
        )
        if self.contract_evidence_hash != expected:
            raise ValueError("S1 BTC execution-contract evidence hash changed")
        return self


class S1BtcSourceExecutionAudit(BaseModel):
    schema_version: Literal["aurex-s1-btc-source-execution-audit-v1"] = (
        "aurex-s1-btc-source-execution-audit-v1"
    )
    audit_id: Literal["s1-btc-source-execution-audit-v1"] = (
        "s1-btc-source-execution-audit-v1"
    )
    audited_at: datetime
    contract_file_sha256: str
    contract_evidence_hash: str
    protocol_evidence_hash: str
    runner_contract_hash: str
    auditor_source_sha256: str
    synthetic_test_ids: tuple[str, ...] = Field(min_length=8)
    reconstructed_exactly: Literal[True] = True
    network_requests_observed: Literal[0] = 0
    payload_bytes_observed: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    decision: Literal["PASS_S1_BTC_SOURCE_EXECUTION_CONTRACT_RECONSTRUCTED"] = (
        "PASS_S1_BTC_SOURCE_EXECUTION_CONTRACT_RECONSTRUCTED"
    )
    next_authorization: Literal[
        "AUTHORIZE_S1_BTCUSDT_DAILY_1H_SOURCE_ACQUISITION"
    ] = S1_BTC_EXECUTION_NEXT
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
    def validate_audit(self) -> S1BtcSourceExecutionAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1 BTC execution-audit evidence hash changed")
        return self


class S1BtcAcquisitionCheckpoint(BaseModel):
    schema_version: Literal["aurex-s1-btc-acquisition-checkpoint-v1"] = (
        "aurex-s1-btc-acquisition-checkpoint-v1"
    )
    checkpoint_id: Literal["s1-btc-acquisition-checkpoint-v1"] = (
        "s1-btc-acquisition-checkpoint-v1"
    )
    started_at: datetime
    updated_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    execution_contract_file_sha256: str
    execution_contract_evidence_hash: str
    runner_contract_hash: str
    target_evidence: tuple[S1BtcTargetEvidence, ...] = ()
    classified_target_count: int = Field(ge=0, le=277)
    complete_target_count: int = Field(ge=0, le=277)
    failed_target_count: int = Field(ge=0, le=1)
    network_request_count: int = Field(ge=0, le=1662)
    network_body_bytes: int = Field(ge=0, le=55_541_824)
    persisted_source_bytes: int = Field(ge=0, le=55_541_824)
    next_sequence: int | None = Field(default=None, ge=1, le=277)
    terminal: bool
    return_metrics_calculated: tuple[str, ...] = ()
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
    def validate_checkpoint(self) -> S1BtcAcquisitionCheckpoint:
        sequences = tuple(item.sequence for item in self.target_evidence)
        if sequences != tuple(range(1, len(sequences) + 1)):
            raise ValueError("S1 BTC checkpoint target sequence changed")
        if self.classified_target_count != len(self.target_evidence):
            raise ValueError("S1 BTC checkpoint classified count changed")
        if self.complete_target_count != sum(
            item.outcome == "COMPLETE" for item in self.target_evidence
        ):
            raise ValueError("S1 BTC checkpoint complete count changed")
        if self.failed_target_count != sum(
            item.outcome == "FAILED" for item in self.target_evidence
        ):
            raise ValueError("S1 BTC checkpoint failed count changed")
        if self.network_request_count != sum(
            len(item.attempts) for item in self.target_evidence
        ):
            raise ValueError("S1 BTC checkpoint request count changed")
        expected_next = (
            None
            if self.terminal or self.classified_target_count == 277
            else self.classified_target_count + 1
        )
        if self.next_sequence != expected_next:
            raise ValueError("S1 BTC checkpoint next sequence changed")
        if self.return_metrics_calculated:
            raise ValueError("S1 BTC source checkpoint cannot contain returns")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"checkpoint_evidence_hash"})
        )
        if self.checkpoint_evidence_hash != expected:
            raise ValueError("S1 BTC checkpoint evidence hash changed")
        return self


class S1BtcSourceAcquisitionResult(BaseModel):
    schema_version: Literal["aurex-s1-btc-source-acquisition-result-v1"] = (
        "aurex-s1-btc-source-acquisition-result-v1"
    )
    result_id: Literal["s1-btc-source-acquisition-result-v1"] = (
        "s1-btc-source-acquisition-result-v1"
    )
    completed_at: datetime
    checkpoint_file_sha256: str
    checkpoint_evidence_hash: str
    protocol_evidence_hash: str
    execution_contract_evidence_hash: str
    runner_contract_hash: str
    target_evidence: tuple[S1BtcTargetEvidence, ...] = Field(min_length=1)
    price_rows: tuple[S1BtcPriceRow, ...] = ()
    gates: tuple[S1SourceGate, ...] = Field(min_length=10, max_length=10)
    classified_target_count: int = Field(ge=1, le=277)
    complete_target_count: int = Field(ge=0, le=277)
    failed_target_count: int = Field(ge=0, le=1)
    network_request_count: int = Field(ge=0, le=1662)
    network_body_bytes: int = Field(ge=0, le=55_541_824)
    persisted_source_bytes: int = Field(ge=0, le=55_541_824)
    dataset_path: str | None = None
    dataset_file_sha256: str | None = None
    dataset_bytes: int = Field(ge=0)
    decision: Literal[
        "PASS_S1_BTCUSDT_DAILY_1H_SOURCE_ACQUISITION",
        "STOP_S1_BTCUSDT_DAILY_1H_SOURCE_ACQUISITION_FAILED",
    ]
    next_authorization: Literal[
        "AUTHORIZE_S1_DEVELOPMENT_OUTCOME_EXECUTION_PROTOCOL_ONLY",
        "NONE_S1_BTCUSDT_DAILY_1H_SOURCE_ACQUISITION_FAILED",
    ]
    return_metrics_calculated: tuple[str, ...] = ()
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
    def validate_result(self) -> S1BtcSourceAcquisitionResult:
        gate_ids = tuple(
            gate.gate_id
            for gate in sorted(self.gates, key=lambda item: item.gate_id)
        )
        if gate_ids != tuple(sorted(S1_BTC_SOURCE_GATES)):
            raise ValueError("S1 BTC acquisition result gates changed")
        passed = self.decision == S1_BTC_ACQUISITION_PASS
        if passed and (
            self.classified_target_count != 277
            or self.complete_target_count != 277
            or len(self.price_rows) != 277
            or self.dataset_path is None
            or self.dataset_file_sha256 is None
            or self.dataset_bytes == 0
            or any(gate.status != "PASS" for gate in self.gates)
        ):
            raise ValueError("Passing S1 BTC acquisition result is incomplete")
        if self.return_metrics_calculated:
            raise ValueError("S1 BTC source result cannot contain returns")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("S1 BTC acquisition-result evidence hash changed")
        return self
