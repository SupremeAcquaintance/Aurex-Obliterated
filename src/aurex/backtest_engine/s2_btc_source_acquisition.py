from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S2_BTC_SOURCE_PROTOCOL_NEXT = (
    "AUTHORIZE_S2_BTCUSDT_MONDAY_1H_SOURCE_ACQUISITION_RUNNER_IMPLEMENTATION_ONLY"
)
S2_BTC_SOURCE_BASE_URL = (
    "https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1h"
)
S2_BTC_SOURCE_GATES = (
    "ALL_273_MONDAY_TARGETS_CLASSIFIED",
    "EVERY_ZIP_MATCHES_ITS_PUBLISHED_SHA256",
    "EVERY_ZIP_HAS_EXACTLY_ONE_SAFE_EXPECTED_CSV_MEMBER",
    "EVERY_CSV_ROW_HAS_EXACTLY_12_KLINE_FIELDS",
    "OPEN_TIMES_ARE_UNIQUE_STRICTLY_INCREASING_AND_WITHIN_TARGET_DATE",
    "EXACT_00_00_UTC_TARGET_OPEN_EXISTS_ONCE_PER_DATE",
    "TARGET_OPEN_IS_POSITIVE_FINITE_DECIMAL_SOURCE_TEXT",
    "REQUEST_AND_RESPONSE_MARKERS_RECONCILE_EXACTLY",
    "OUTPUT_HAS_273_CHRONOLOGICAL_HASH_LINKED_PRICE_ROWS",
    "ZERO_RETURNS_CANDIDATE_OUTCOMES_HISTORICAL_SCREEN_VALIDATION_HOLDOUT_AND_ORDERS",
)


class S2BtcSourceTarget(BaseModel):
    sequence: int = Field(ge=1, le=273)
    measurement_sequence: int = Field(ge=8, le=280)
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

    @model_validator(mode="after")
    def validate_target(self) -> S2BtcSourceTarget:
        day = self.activation_date.isoformat()
        filename = f"BTCUSDT-1h-{day}.zip"
        root = f"data/evidence/source_snapshots/s2_btcusdt_monday_1h_v1/{day}"
        expected_open = int(
            datetime.combine(self.activation_date, time(), tzinfo=UTC).timestamp() * 1000
        )
        if self.measurement_sequence != self.sequence + 7:
            raise ValueError("S2 BTC measurement sequence changed")
        if self.target_id != f"{self.sequence:03d}-btcusdt-1h-{day}":
            raise ValueError("S2 BTC target id changed")
        if self.activation_open_time_ms != expected_open:
            raise ValueError("S2 BTC target timestamp changed")
        if self.archive_url != f"{S2_BTC_SOURCE_BASE_URL}/{filename}":
            raise ValueError("S2 BTC archive URL changed")
        if self.checksum_url != f"{S2_BTC_SOURCE_BASE_URL}/{filename}.CHECKSUM":
            raise ValueError("S2 BTC checksum URL changed")
        if any(
            urlparse(url).scheme != "https"
            or urlparse(url).hostname != self.expected_final_host
            for url in (self.archive_url, self.checksum_url)
        ):
            raise ValueError("S2 BTC source transport boundary changed")
        if self.expected_member_name != filename.replace(".zip", ".csv"):
            raise ValueError("S2 BTC expected ZIP member changed")
        if self.archive_path != f"{root}/{filename}":
            raise ValueError("S2 BTC archive path changed")
        if self.checksum_path != f"{root}/{filename}.CHECKSUM":
            raise ValueError("S2 BTC checksum path changed")
        return self


class S2BtcSourceAcquisitionProtocol(BaseModel):
    schema_version: Literal["aurex-s2-btc-source-acquisition-protocol-v1"] = (
        "aurex-s2-btc-source-acquisition-protocol-v1"
    )
    protocol_id: Literal["s2-btc-source-acquisition-protocol-v1"] = (
        "s2-btc-source-acquisition-protocol-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_BEFORE_S2_BTC_MARKET_VALUE_READ"] = (
        "FROZEN_BEFORE_S2_BTC_MARKET_VALUE_READ"
    )
    builder_contract_hash: str
    preregistration_file_sha256: str
    preregistration_evidence_hash: str
    preregistration_audit_file_sha256: str
    preregistration_audit_evidence_hash: str
    preregistration_decision: Literal["FREEZE_S2_SINGLE_CANDIDATE_BEFORE_MARKET_OUTCOMES"]
    preregistration_audit_decision: Literal["PASS_S2_STRATEGY_PREREGISTRATION_AUDIT"]
    preregistration_next_authorization: Literal[
        "AUTHORIZE_S2_BTCUSDT_MONDAY_1H_SOURCE_ACQUISITION_PROTOCOL_ONLY"
    ]
    acquisition_scope: Literal["DEVELOPMENT_EXECUTION_PRICES_ONLY"] = (
        "DEVELOPMENT_EXECUTION_PRICES_ONLY"
    )
    venue: Literal["BINANCE"] = "BINANCE"
    market_type: Literal["SPOT"] = "SPOT"
    symbol: Literal["BTCUSDT"] = "BTCUSDT"
    interval: Literal["1h"] = "1h"
    archive_granularity: Literal["DAILY"] = "DAILY"
    source_base_url: Literal[
        "https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1h"
    ] = S2_BTC_SOURCE_BASE_URL
    first_activation_date: Literal["2017-10-16"] = "2017-10-16"
    last_activation_date: Literal["2023-01-02"] = "2023-01-02"
    interval_days: Literal[7] = 7
    required_weekday: Literal["MONDAY"] = "MONDAY"
    targets: tuple[S2BtcSourceTarget, ...] = Field(min_length=273, max_length=273)
    target_count: Literal[273] = 273
    requests_per_attempt: Literal[2] = 2
    maximum_attempts_per_resource: Literal[3] = 3
    maximum_network_requests: Literal[1638] = 1_638
    maximum_archive_bytes_per_target: Literal[200000] = 200_000
    maximum_checksum_bytes_per_target: Literal[512] = 512
    maximum_total_payload_bytes: Literal[54739776] = 54_739_776
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
    csv_header_policy: Literal["NO_HEADER_OR_EXACT_OFFICIAL_12_COLUMN_HEADER"] = (
        "NO_HEADER_OR_EXACT_OFFICIAL_12_COLUMN_HEADER"
    )
    timestamp_unit: Literal["MILLISECONDS"] = "MILLISECONDS"
    target_price_field: Literal["OPEN"] = "OPEN"
    target_time_rule: Literal["EXACT_DATE_AT_00_00_UTC"] = "EXACT_DATE_AT_00_00_UTC"
    missing_target_policy: Literal["STOP_NO_SUBSTITUTION"] = "STOP_NO_SUBSTITUTION"
    output_path: Literal[
        "data/evidence/datasets/s2_btcusdt_monday_00h_opens_v1.jsonl"
    ] = "data/evidence/datasets/s2_btcusdt_monday_00h_opens_v1.jsonl"
    quality_gates: tuple[str, ...] = Field(min_length=10, max_length=10)
    btc_market_values_read_during_protocol_freeze: Literal[0] = 0
    return_metrics_calculated: tuple[str, ...] = ()
    authorizes_protocol_only: Literal[True] = True
    authorizes_network_acquisition_now: Literal[False] = False
    authorizes_runner_implementation: Literal[True] = True
    authorizes_return_testing: Literal[False] = False
    authorizes_historical_screen_access: Literal[False] = False
    authorizes_validation_access: Literal[False] = False
    authorizes_holdout_access: Literal[False] = False
    authorizes_candidate_outcome: Literal[False] = False
    authorizes_pine: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    next_authorization: Literal[
        "AUTHORIZE_S2_BTCUSDT_MONDAY_1H_SOURCE_ACQUISITION_RUNNER_IMPLEMENTATION_ONLY"
    ] = S2_BTC_SOURCE_PROTOCOL_NEXT
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

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
    def validate_protocol(self) -> S2BtcSourceAcquisitionProtocol:
        sequences = tuple(item.sequence for item in self.targets)
        measurement_sequences = tuple(item.measurement_sequence for item in self.targets)
        dates = tuple(item.activation_date for item in self.targets)
        if sequences != tuple(range(1, 274)):
            raise ValueError("S2 BTC target sequence changed")
        if measurement_sequences != tuple(range(8, 281)):
            raise ValueError("S2 BTC measurement sequence changed")
        if dates[0] != date(2017, 10, 16) or dates[-1] != date(2023, 1, 2):
            raise ValueError("S2 BTC activation date bounds changed")
        if any(item.weekday() != 0 for item in dates):
            raise ValueError("S2 BTC target is not a Monday")
        if any(
            (right - left).days != self.interval_days
            for left, right in zip(dates, dates[1:], strict=False)
        ):
            raise ValueError("S2 BTC weekly target schedule changed")
        if self.maximum_network_requests != (
            self.target_count
            * self.requests_per_attempt
            * self.maximum_attempts_per_resource
        ):
            raise ValueError("S2 BTC request budget changed")
        expected_bytes = self.target_count * (
            self.maximum_archive_bytes_per_target
            + self.maximum_checksum_bytes_per_target
        )
        if self.maximum_total_payload_bytes != expected_bytes:
            raise ValueError("S2 BTC payload budget changed")
        if self.quality_gates != S2_BTC_SOURCE_GATES:
            raise ValueError("S2 BTC source gates changed")
        if self.return_metrics_calculated:
            raise ValueError("S2 BTC source protocol cannot contain returns")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S2 BTC source protocol hash changed")
        return self


class S2BtcSourceAcquisitionProtocolAudit(BaseModel):
    schema_version: Literal["aurex-s2-btc-source-acquisition-protocol-audit-v1"] = (
        "aurex-s2-btc-source-acquisition-protocol-audit-v1"
    )
    audit_id: Literal["s2-btc-source-acquisition-protocol-audit-v1"] = (
        "s2-btc-source-acquisition-protocol-audit-v1"
    )
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    builder_contract_hash: str
    preregistration_evidence_hash: str
    preregistration_audit_evidence_hash: str
    auditor_contract_hash: str
    target_count: Literal[273] = 273
    first_activation_date: Literal["2017-10-16"] = "2017-10-16"
    last_activation_date: Literal["2023-01-02"] = "2023-01-02"
    network_requests_observed: Literal[0] = 0
    payload_bytes_observed: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    reconstructed_exactly: Literal[True] = True
    decision: Literal["PASS_S2_BTC_SOURCE_ACQUISITION_PROTOCOL_AUDIT"] = (
        "PASS_S2_BTC_SOURCE_ACQUISITION_PROTOCOL_AUDIT"
    )
    next_authorization: Literal[
        "AUTHORIZE_S2_BTCUSDT_MONDAY_1H_SOURCE_ACQUISITION_RUNNER_IMPLEMENTATION_ONLY"
    ] = S2_BTC_SOURCE_PROTOCOL_NEXT
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

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
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S2BtcSourceAcquisitionProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S2 BTC source protocol audit hash changed")
        return self
