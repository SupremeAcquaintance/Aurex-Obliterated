from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S1_BTC_SOURCE_NEXT = (
    "AUTHORIZE_S1_BTCUSDT_DAILY_1H_SOURCE_ACQUISITION_RUNNER_IMPLEMENTATION_ONLY"
)

S1_BTC_SOURCE_GATES = (
    "ALL_277_FRIDAY_TARGETS_CLASSIFIED",
    "EVERY_ZIP_MATCHES_ITS_PUBLISHED_SHA256",
    "EVERY_ZIP_HAS_EXACTLY_ONE_SAFE_EXPECTED_CSV_MEMBER",
    "EVERY_CSV_ROW_HAS_EXACTLY_12_KLINE_FIELDS",
    "OPEN_TIMES_ARE_UNIQUE_STRICTLY_INCREASING_AND_WITHIN_TARGET_DATE",
    "EXACT_00_00_UTC_TARGET_OPEN_EXISTS_ONCE_PER_DATE",
    "TARGET_OPEN_IS_POSITIVE_FINITE_DECIMAL_SOURCE_TEXT",
    "REQUEST_AND_RESPONSE_MARKERS_RECONCILE_EXACTLY",
    "OUTPUT_HAS_277_CHRONOLOGICAL_HASH_LINKED_PRICE_ROWS",
    "ZERO_RETURNS_CANDIDATE_OUTCOMES_VALIDATION_HOLDOUT_AND_ORDERS",
)


class S1BtcSourceTarget(BaseModel):
    sequence: int = Field(ge=1, le=277)
    feature_sequence: int = Field(ge=5, le=281)
    target_id: str = Field(pattern=r"^[0-9]{3}-btcusdt-1h-[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    activation_date: date
    activation_open_time_ms: int = Field(ge=1)
    archive_url: str = Field(min_length=30)
    checksum_url: str = Field(min_length=30)
    expected_final_host: Literal["data.binance.vision"] = "data.binance.vision"
    expected_member_name: str = Field(min_length=20)
    archive_path: str = Field(min_length=20)
    checksum_path: str = Field(min_length=20)

    model_config = ConfigDict(extra="forbid", frozen=True)


class S1BtcSourceAcquisitionProtocol(BaseModel):
    schema_version: Literal["aurex-s1-btc-source-acquisition-protocol-v1"] = (
        "aurex-s1-btc-source-acquisition-protocol-v1"
    )
    protocol_id: Literal["s1-btc-source-acquisition-protocol-v1"] = (
        "s1-btc-source-acquisition-protocol-v1"
    )
    frozen_at: datetime
    builder_contract_hash: str
    preregistration_file_sha256: str
    preregistration_evidence_hash: str
    preregistration_audit_file_sha256: str
    preregistration_audit_evidence_hash: str
    preregistration_decision: Literal[
        "PASS_S1_STRATEGY_PREREGISTRATION_RECONSTRUCTED"
    ]
    preregistration_next_authorization: Literal[
        "AUTHORIZE_S1_BTCUSDT_DAILY_1H_SOURCE_ACQUISITION_PROTOCOL_ONLY"
    ]
    acquisition_scope: Literal["DEVELOPMENT_EXECUTION_PRICES_ONLY"] = (
        "DEVELOPMENT_EXECUTION_PRICES_ONLY"
    )
    venue: Literal["BINANCE"] = "BINANCE"
    market_type: Literal["SPOT"] = "SPOT"
    symbol: Literal["BTCUSDT"] = "BTCUSDT"
    interval: Literal["1h"] = "1h"
    archive_granularity: Literal["DAILY"] = "DAILY"
    first_activation_date: Literal["2017-09-15"] = "2017-09-15"
    last_activation_date: Literal["2022-12-30"] = "2022-12-30"
    interval_days: Literal[7] = 7
    targets: tuple[S1BtcSourceTarget, ...] = Field(min_length=277, max_length=277)
    target_count: Literal[277] = 277
    requests_per_attempt: Literal[2] = 2
    maximum_attempts_per_resource: Literal[3] = 3
    maximum_network_requests: Literal[1662] = 1662
    maximum_archive_bytes_per_target: Literal[200000] = 200_000
    maximum_checksum_bytes_per_target: Literal[512] = 512
    maximum_total_payload_bytes: Literal[55541824] = 55_541_824
    minimum_free_disk_bytes: Literal[250000000] = 250_000_000
    connect_timeout_seconds: Literal[60] = 60
    chunk_size_bytes: Literal[65536] = 65_536
    polite_delay_milliseconds: Literal[100] = 100
    transient_http_statuses: tuple[int, ...] = (408, 425, 429, 500, 502, 503, 504)
    retryable_errors: tuple[str, ...] = (
        "ConnectionError",
        "TimeoutError",
        "URLError",
    )
    permits_redirects: Literal[False] = False
    requires_pre_attempt_marker: Literal[True] = True
    requires_post_attempt_marker: Literal[True] = True
    requires_atomic_file_rename: Literal[True] = True
    requires_per_target_checkpoint: Literal[True] = True
    permits_exact_hash_local_reuse: Literal[True] = True
    permits_partial_file_reuse: Literal[False] = False
    zip_member_policy: Literal["EXACTLY_ONE_SAFE_EXPECTED_CSV_MEMBER"] = (
        "EXACTLY_ONE_SAFE_EXPECTED_CSV_MEMBER"
    )
    csv_header_policy: Literal[
        "NO_HEADER_OR_EXACT_OFFICIAL_12_COLUMN_HEADER"
    ] = "NO_HEADER_OR_EXACT_OFFICIAL_12_COLUMN_HEADER"
    timestamp_unit: Literal["MILLISECONDS"] = "MILLISECONDS"
    target_price_field: Literal["OPEN"] = "OPEN"
    target_time_rule: Literal["EXACT_DATE_AT_00_00_UTC"] = (
        "EXACT_DATE_AT_00_00_UTC"
    )
    output_path: Literal[
        "data/evidence/datasets/s1_btcusdt_friday_opens_v1.jsonl"
    ] = "data/evidence/datasets/s1_btcusdt_friday_opens_v1.jsonl"
    quality_gates: tuple[str, ...] = Field(min_length=10, max_length=10)
    btc_market_values_read_during_protocol_freeze: Literal[0] = 0
    return_metrics_calculated: tuple[str, ...] = ()
    authorizes_protocol_only: Literal[True] = True
    authorizes_network_acquisition_now: Literal[False] = False
    authorizes_runner_implementation: Literal[True] = True
    authorizes_return_testing: Literal[False] = False
    authorizes_validation_access: Literal[False] = False
    authorizes_holdout_access: Literal[False] = False
    authorizes_candidate_outcome: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    next_authorization: Literal[
        "AUTHORIZE_S1_BTCUSDT_DAILY_1H_SOURCE_ACQUISITION_RUNNER_IMPLEMENTATION_ONLY"
    ] = S1_BTC_SOURCE_NEXT
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "preregistration_file_sha256",
        "preregistration_evidence_hash",
        "preregistration_audit_file_sha256",
        "preregistration_audit_evidence_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S1BtcSourceAcquisitionProtocol:
        sequences = tuple(item.sequence for item in self.targets)
        feature_sequences = tuple(item.feature_sequence for item in self.targets)
        dates = tuple(item.activation_date for item in self.targets)
        if sequences != tuple(range(1, 278)):
            raise ValueError("S1 BTC target sequence changed")
        if feature_sequences != tuple(range(5, 282)):
            raise ValueError("S1 BTC feature sequence changed")
        if dates[0] != date(2017, 9, 15) or dates[-1] != date(2022, 12, 30):
            raise ValueError("S1 BTC activation date bounds changed")
        if any(item.weekday() != 4 for item in dates):
            raise ValueError("S1 BTC target is not a Friday")
        if any(
            (right - left).days != 7
            for left, right in zip(dates, dates[1:], strict=False)
        ):
            raise ValueError("S1 BTC weekly target schedule changed")
        if self.maximum_network_requests != (
            self.target_count
            * self.requests_per_attempt
            * self.maximum_attempts_per_resource
        ):
            raise ValueError("S1 BTC request budget changed")
        expected_bytes = self.target_count * (
            self.maximum_archive_bytes_per_target
            + self.maximum_checksum_bytes_per_target
        )
        if self.maximum_total_payload_bytes != expected_bytes:
            raise ValueError("S1 BTC payload budget changed")
        if self.quality_gates != S1_BTC_SOURCE_GATES:
            raise ValueError("S1 BTC source gates changed")
        if self.return_metrics_calculated:
            raise ValueError("S1 BTC source protocol cannot contain returns")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S1 BTC source protocol hash changed")
        return self


class S1BtcSourceAcquisitionProtocolAudit(BaseModel):
    schema_version: Literal["aurex-s1-btc-source-acquisition-protocol-audit-v1"] = (
        "aurex-s1-btc-source-acquisition-protocol-audit-v1"
    )
    audit_id: Literal["s1-btc-source-acquisition-protocol-audit-v1"] = (
        "s1-btc-source-acquisition-protocol-audit-v1"
    )
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    builder_contract_hash: str
    preregistration_evidence_hash: str
    preregistration_audit_evidence_hash: str
    auditor_source_sha256: str
    target_count: Literal[277] = 277
    first_activation_date: Literal["2017-09-15"] = "2017-09-15"
    last_activation_date: Literal["2022-12-30"] = "2022-12-30"
    network_requests_observed: Literal[0] = 0
    payload_bytes_observed: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    reconstructed_exactly: Literal[True] = True
    decision: Literal["PASS_S1_BTC_SOURCE_ACQUISITION_PROTOCOL_RECONSTRUCTED"] = (
        "PASS_S1_BTC_SOURCE_ACQUISITION_PROTOCOL_RECONSTRUCTED"
    )
    next_authorization: Literal[
        "AUTHORIZE_S1_BTCUSDT_DAILY_1H_SOURCE_ACQUISITION_RUNNER_IMPLEMENTATION_ONLY"
    ] = S1_BTC_SOURCE_NEXT
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "builder_contract_hash",
        "preregistration_evidence_hash",
        "preregistration_audit_evidence_hash",
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S1BtcSourceAcquisitionProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1 BTC source protocol audit hash changed")
        return self
