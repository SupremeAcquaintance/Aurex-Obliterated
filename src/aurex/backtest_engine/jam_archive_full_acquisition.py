from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.jam_archive_metadata_census import archive_url
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

JAM_FULL_ACQUISITION_PROTOCOL_SCHEMA_VERSION = (
    "aurex-jam-archive-full-acquisition-protocol-v1"
)
JAM_FULL_ACQUISITION_RESULT_SCHEMA_VERSION = (
    "aurex-jam-archive-full-acquisition-result-v1"
)
JAM_FULL_ACQUISITION_AUDIT_SCHEMA_VERSION = (
    "aurex-jam-archive-full-acquisition-audit-v1"
)
JAM_FULL_ACQUISITION_PASS_DECISION = (
    "PASS_2019_2022_ARCHIVE_ACQUISITION_AWAIT_NO_RETURN_FEATURE_SPECIFICATION"
)
JAM_FULL_ACQUISITION_FAIL_DECISION = (
    "STOP_JAM_SUCCESSOR_FULL_ARCHIVE_QUALITY_FAILED"
)
JAM_FULL_ACQUISITION_NEXT_AUTHORIZATION = (
    "AUTHORIZE_JAM_SUCCESSOR_FEATURE_SPECIFICATION_NO_RETURNS"
)
JAM_FULL_ACQUISITION_NO_NEXT_AUTHORIZATION = "NONE_ACQUISITION_FAILED"
JAM_FULL_MONTHS = tuple(
    f"{year}-{month:02d}"
    for year in range(2019, 2023)
    for month in range(1, 13)
)
JAM_FULL_FAMILIES = ("aggTrades", "klines_1m")
JAM_FULL_TARGET_COUNT = 96
JAM_FULL_NETWORK_TARGET_COUNT = 94
JAM_FULL_MAXIMUM_ARCHIVE_BYTES = 2_500_000_000
JAM_FULL_MAXIMUM_TOTAL_ARCHIVE_BYTES = 60_000_000_000
JAM_FULL_MAXIMUM_MEMBER_BYTES = 20_000_000_000
JAM_FULL_MAXIMUM_TOTAL_MEMBER_BYTES = 600_000_000_000
JAM_FULL_AGGTRADES_HEADER = (
    "aggregate_trade_id",
    "price",
    "quantity",
    "first_trade_id",
    "last_trade_id",
    "transact_time",
    "is_buyer_maker",
    "is_best_match",
)
JAM_FULL_KLINES_HEADER = (
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_asset_volume",
    "number_of_trades",
    "taker_buy_base_asset_volume",
    "taker_buy_quote_asset_volume",
    "ignore",
)


def month_bounds_ms(month: str) -> tuple[int, int, int]:
    year, month_number = (int(part) for part in month.split("-"))
    start = datetime(year, month_number, 1, tzinfo=UTC)
    end = (
        datetime(year + 1, 1, 1, tzinfo=UTC)
        if month_number == 12
        else datetime(year, month_number + 1, 1, tzinfo=UTC)
    )
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    return start_ms, end_ms, (end_ms - start_ms) // 60_000


class JamFullAcquisitionTarget(BaseModel):
    family: Literal["aggTrades", "klines_1m"]
    symbol: Literal["BTCUSDT"] = "BTCUSDT"
    month: str = Field(pattern=r"^(2019|2020|2021|2022)-(0[1-9]|1[0-2])$")
    archive_url: str
    published_archive_sha256: str
    expected_csv_member: str
    expected_column_count: int
    reuse_verified_pilot_file: bool

    model_config = ConfigDict(extra="forbid")

    @field_validator("published_archive_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_target(self) -> JamFullAcquisitionTarget:
        expected_url = archive_url(self.family, self.month)
        expected_member = (
            f"BTCUSDT-aggTrades-{self.month}.csv"
            if self.family == "aggTrades"
            else f"BTCUSDT-1m-{self.month}.csv"
        )
        expected_columns = 8 if self.family == "aggTrades" else 12
        if (
            self.archive_url != expected_url
            or self.expected_csv_member != expected_member
            or self.expected_column_count != expected_columns
            or self.reuse_verified_pilot_file != (self.month == "2019-01")
        ):
            raise ValueError("Jam full acquisition target changed")
        parsed = urlparse(self.archive_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "data.binance.vision"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port is not None
            or parsed.query
            or parsed.fragment
            or not parsed.path.startswith("/data/spot/monthly/")
            or not parsed.path.endswith(".zip")
        ):
            raise ValueError("Jam full target must use exact Binance HTTPS")
        return self

    @property
    def key(self) -> tuple[str, str]:
        return self.family, self.month


class JamFullAcquisitionProtocol(BaseModel):
    schema_version: Literal[
        "aurex-jam-archive-full-acquisition-protocol-v1"
    ] = JAM_FULL_ACQUISITION_PROTOCOL_SCHEMA_VERSION
    protocol_id: Literal["jam-archive-full-acquisition-v1"] = (
        "jam-archive-full-acquisition-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_PRE_FULL_ARCHIVE_REQUEST"] = (
        "FROZEN_PRE_FULL_ARCHIVE_REQUEST"
    )
    authorization_record: Literal[
        "USER_AUTHORIZED_FROZEN_2019_2022_ARCHIVE_ACQUISITION"
    ] = "USER_AUTHORIZED_FROZEN_2019_2022_ARCHIVE_ACQUISITION"
    census_result_path: Literal[
        "data/evidence/jam_archive_metadata_census_result_v1.json"
    ] = "data/evidence/jam_archive_metadata_census_result_v1.json"
    census_result_file_sha256: str
    census_result_evidence_hash: str
    payload_pilot_protocol_evidence_hash: str
    payload_pilot_result_evidence_hash: str
    payload_pilot_audit_evidence_hash: str
    builder_contract_hash: str
    targets: list[JamFullAcquisitionTarget] = Field(
        min_length=JAM_FULL_TARGET_COUNT,
        max_length=JAM_FULL_TARGET_COUNT,
    )
    target_manifest_hash: str
    evidence_partition: Literal[
        "JAM_PROVISIONAL_HISTORICAL_POOL_2019_2022_NO_RETURNS"
    ] = "JAM_PROVISIONAL_HISTORICAL_POOL_2019_2022_NO_RETURNS"
    permitted_methods: list[str] = Field(default_factory=lambda: ["GET", "HEAD"])
    network_target_count: Literal[94] = JAM_FULL_NETWORK_TARGET_COUNT
    reused_pilot_target_count: Literal[2] = 2
    maximum_head_requests: Literal[282] = 282
    maximum_payload_get_requests: Literal[282] = 282
    maximum_requests_total: Literal[564] = 564
    maximum_retries_per_request: Literal[2] = 2
    retry_backoff_seconds: list[int] = Field(default_factory=lambda: [2, 5])
    request_timeout_seconds: Literal[90] = 90
    download_chunk_bytes: Literal[1048576] = 1_048_576
    redirects_permitted: Literal[False] = False
    range_resume_permitted: Literal[True] = True
    maximum_archive_bytes: Literal[2500000000] = (
        JAM_FULL_MAXIMUM_ARCHIVE_BYTES
    )
    maximum_total_archive_bytes: Literal[60000000000] = (
        JAM_FULL_MAXIMUM_TOTAL_ARCHIVE_BYTES
    )
    maximum_member_uncompressed_bytes: Literal[20000000000] = (
        JAM_FULL_MAXIMUM_MEMBER_BYTES
    )
    maximum_total_member_uncompressed_bytes: Literal[600000000000] = (
        JAM_FULL_MAXIMUM_TOTAL_MEMBER_BYTES
    )
    maximum_zip_expansion_ratio: Literal[100] = 100
    minimum_post_acquisition_free_disk_bytes: Literal[20000000000] = (
        20_000_000_000
    )
    decimal_reconciliation_tolerance: Literal["0.00000001"] = "0.00000001"
    market_values_permitted_for_quality_validation: Literal[True] = True
    feature_calculation_permitted: Literal[False] = False
    parameter_definition_permitted: Literal[False] = False
    return_calculation_permitted: Literal[False] = False
    strategy_execution_permitted: Literal[False] = False
    candidate_creation_permitted: Literal[False] = False
    forward_data_access_permitted: Literal[False] = False
    testnet_strategy_orders_permitted: Literal[False] = False
    production_permitted: Literal[False] = False
    live_permitted: Literal[False] = False
    limitations: list[str] = Field(min_length=10)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "census_result_file_sha256",
        "census_result_evidence_hash",
        "payload_pilot_protocol_evidence_hash",
        "payload_pilot_result_evidence_hash",
        "payload_pilot_audit_evidence_hash",
        "builder_contract_hash",
        "target_manifest_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "permitted_methods",
        "retry_backoff_seconds",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list) -> list:
        return sorted(set(value))

    @model_validator(mode="after")
    def validate_protocol(self) -> JamFullAcquisitionProtocol:
        expected_keys = {
            (family, month)
            for family in JAM_FULL_FAMILIES
            for month in JAM_FULL_MONTHS
        }
        if (
            self.targets != sorted(self.targets, key=lambda item: item.key)
            or len({target.key for target in self.targets}) != 96
            or {target.key for target in self.targets} != expected_keys
            or sum(target.reuse_verified_pilot_file for target in self.targets)
            != 2
        ):
            raise ValueError("Jam full acquisition target matrix changed")
        if self.target_manifest_hash != universe_evidence_hash(
            {"targets": [target.model_dump() for target in self.targets]}
        ):
            raise ValueError("Jam full acquisition target manifest changed")
        if self.permitted_methods != ["GET", "HEAD"]:
            raise ValueError("Jam full acquisition method policy changed")
        if self.retry_backoff_seconds != [2, 5]:
            raise ValueError("Jam full acquisition retry policy changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected_hash:
            raise ValueError("Jam full acquisition protocol hash does not match")
        return self


class JamFullArchiveEvidence(BaseModel):
    family: Literal["aggTrades", "klines_1m"]
    month: str = Field(pattern=r"^(2019|2020|2021|2022)-(0[1-9]|1[0-2])$")
    archive_url: str
    local_path: str
    reused_pilot_file: bool
    archive_bytes: int = Field(gt=0, le=2_500_000_000)
    archive_sha256: str
    published_archive_sha256: str
    checksum_verified: Literal[True] = True
    csv_member_name: str
    zip_compressed_bytes: int = Field(gt=0, le=2_500_000_000)
    zip_uncompressed_bytes: int = Field(gt=0, le=20_000_000_000)
    zip_crc_verified: Literal[True] = True
    column_count: int
    header_present: bool
    row_count: int = Field(gt=0)
    first_timestamp_ms: int = Field(gt=0)
    last_timestamp_ms: int = Field(gt=0)
    unique_primary_key_count: int = Field(gt=0)
    duplicate_primary_key_count: Literal[0] = 0
    out_of_order_count: Literal[0] = 0
    gap_count: int = Field(ge=0)
    unique_minute_count: int = Field(gt=0, le=44_640)
    expected_minute_count: int = Field(ge=40_320, le=44_640)
    inspected_field_names: list[str]
    head_request_count: int = Field(ge=0, le=3)
    payload_get_request_count: int = Field(ge=0, le=3)
    archive_pass: bool
    reason_codes: list[str]

    model_config = ConfigDict(extra="forbid")

    @field_validator("archive_sha256", "published_archive_sha256")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("inspected_field_names", "reason_codes")
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_evidence(self) -> JamFullArchiveEvidence:
        target = JamFullAcquisitionTarget(
            family=self.family,
            month=self.month,
            archive_url=self.archive_url,
            published_archive_sha256=self.published_archive_sha256,
            expected_csv_member=self.csv_member_name,
            expected_column_count=self.column_count,
            reuse_verified_pilot_file=self.reused_pilot_file,
        )
        expected_minutes = month_bounds_ms(self.month)[2]
        expected_fields = sorted(
            JAM_FULL_AGGTRADES_HEADER
            if self.family == "aggTrades"
            else JAM_FULL_KLINES_HEADER
        )
        passed = (
            self.archive_sha256 == target.published_archive_sha256
            and self.expected_minute_count == expected_minutes
            and self.inspected_field_names == expected_fields
            and self.gap_count == 0
            and (
                self.family != "klines_1m"
                or (
                    self.row_count == expected_minutes
                    and self.unique_minute_count == expected_minutes
                )
            )
            and (
                (self.head_request_count == 0 and self.payload_get_request_count == 0)
                == self.reused_pilot_file
            )
        )
        if self.archive_pass != passed or bool(self.reason_codes) == passed:
            raise ValueError("Jam full archive decision does not reconcile")
        return self

    @property
    def key(self) -> tuple[str, str]:
        return self.family, self.month


class JamFullMonthReconciliation(BaseModel):
    month: str = Field(pattern=r"^(2019|2020|2021|2022)-(0[1-9]|1[0-2])$")
    expected_minute_count: int = Field(ge=40_320, le=44_640)
    compared_minute_count: int = Field(ge=40_320, le=44_640)
    aggregate_trade_covered_minute_count: int = Field(ge=0, le=44_640)
    empty_trade_minute_count: int = Field(ge=0, le=44_640)
    aggregate_trade_outside_kline_count: int = Field(ge=0)
    raw_trade_count_mismatch_count: int = Field(ge=0)
    ohlc_mismatch_count: int = Field(ge=0)
    base_volume_mismatch_count: int = Field(ge=0)
    quote_volume_mismatch_count: int = Field(ge=0)
    taker_buy_base_volume_mismatch_count: int = Field(ge=0)
    taker_buy_quote_volume_mismatch_count: int = Field(ge=0)
    tolerance: Literal["0.00000001"] = "0.00000001"
    reconciliation_pass: bool
    reason_codes: list[str]

    model_config = ConfigDict(extra="forbid")

    @field_validator("reason_codes")
    @classmethod
    def normalize_reasons(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_reconciliation(self) -> JamFullMonthReconciliation:
        expected_minutes = month_bounds_ms(self.month)[2]
        passed = not any(
            (
                self.aggregate_trade_outside_kline_count,
                self.raw_trade_count_mismatch_count,
                self.ohlc_mismatch_count,
                self.base_volume_mismatch_count,
                self.quote_volume_mismatch_count,
                self.taker_buy_base_volume_mismatch_count,
                self.taker_buy_quote_volume_mismatch_count,
            )
        )
        if (
            self.expected_minute_count != expected_minutes
            or self.compared_minute_count != expected_minutes
            or self.aggregate_trade_covered_minute_count
            + self.empty_trade_minute_count
            != expected_minutes
            or self.reconciliation_pass != passed
            or bool(self.reason_codes) == passed
        ):
            raise ValueError("Jam full month reconciliation changed")
        return self


class JamFullMonthEvidence(BaseModel):
    month: str = Field(pattern=r"^(2019|2020|2021|2022)-(0[1-9]|1[0-2])$")
    aggregate_trades: JamFullArchiveEvidence
    klines_1m: JamFullArchiveEvidence
    reconciliation: JamFullMonthReconciliation
    month_pass: bool
    reason_codes: list[str]

    model_config = ConfigDict(extra="forbid")

    @field_validator("reason_codes")
    @classmethod
    def normalize_reasons(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_month(self) -> JamFullMonthEvidence:
        passed = (
            self.aggregate_trades.month == self.month
            and self.klines_1m.month == self.month
            and self.reconciliation.month == self.month
            and self.aggregate_trades.archive_pass
            and self.klines_1m.archive_pass
            and self.reconciliation.reconciliation_pass
        )
        if self.month_pass != passed or bool(self.reason_codes) == passed:
            raise ValueError("Jam full month decision does not reconcile")
        return self


class JamFullAcquisitionResult(BaseModel):
    schema_version: Literal[
        "aurex-jam-archive-full-acquisition-result-v1"
    ] = JAM_FULL_ACQUISITION_RESULT_SCHEMA_VERSION
    result_id: Literal["jam-archive-full-acquisition-result-v1"] = (
        "jam-archive-full-acquisition-result-v1"
    )
    generated_at: datetime
    status: Literal["COMPLETE_SOURCE_QUALITY_NO_RETURNS"] = (
        "COMPLETE_SOURCE_QUALITY_NO_RETURNS"
    )
    protocol_evidence_hash: str
    runner_contract_hash: str
    months: list[JamFullMonthEvidence] = Field(min_length=48, max_length=48)
    passed_month_count: int = Field(ge=0, le=48)
    failed_month_count: int = Field(ge=0, le=48)
    total_archive_count: Literal[96] = 96
    reused_pilot_archive_count: Literal[2] = 2
    newly_acquired_archive_count: Literal[94] = 94
    total_head_request_count: int = Field(ge=94, le=282)
    total_payload_get_request_count: int = Field(ge=94, le=282)
    total_archive_bytes: int = Field(gt=0, le=60_000_000_000)
    total_member_uncompressed_bytes: int = Field(gt=0, le=600_000_000_000)
    redirects_followed: Literal[0] = 0
    evidence_partition: Literal[
        "JAM_PROVISIONAL_HISTORICAL_POOL_2019_2022_NO_RETURNS"
    ] = "JAM_PROVISIONAL_HISTORICAL_POOL_2019_2022_NO_RETURNS"
    decision: Literal[
        "PASS_2019_2022_ARCHIVE_ACQUISITION_AWAIT_NO_RETURN_FEATURE_SPECIFICATION",
        "STOP_JAM_SUCCESSOR_FULL_ARCHIVE_QUALITY_FAILED",
    ]
    next_required_authorization: Literal[
        "AUTHORIZE_JAM_SUCCESSOR_FEATURE_SPECIFICATION_NO_RETURNS",
        "NONE_ACQUISITION_FAILED",
    ]
    inspected_market_field_names: list[str]
    feature_fields_created: list[str] = Field(default_factory=list)
    parameters_defined: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)
    strategy_executions: Literal[0] = 0
    creates_candidate: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_testnet_order_authority: Literal[False] = False
    creates_production_authority: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    limitations: list[str] = Field(min_length=10)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_evidence_hash",
        "runner_contract_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "inspected_market_field_names",
        "feature_fields_created",
        "parameters_defined",
        "return_metrics_calculated",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_result(self) -> JamFullAcquisitionResult:
        if (
            self.months != sorted(self.months, key=lambda item: item.month)
            or [item.month for item in self.months] != list(JAM_FULL_MONTHS)
        ):
            raise ValueError("Jam full acquisition month matrix changed")
        passed = sum(item.month_pass for item in self.months)
        archives = [
            archive
            for month in self.months
            for archive in (month.aggregate_trades, month.klines_1m)
        ]
        if (
            self.passed_month_count != passed
            or self.failed_month_count != 48 - passed
            or self.total_head_request_count
            != sum(item.head_request_count for item in archives)
            or self.total_payload_get_request_count
            != sum(item.payload_get_request_count for item in archives)
            or self.total_archive_bytes
            != sum(item.archive_bytes for item in archives)
            or self.total_member_uncompressed_bytes
            != sum(item.zip_uncompressed_bytes for item in archives)
        ):
            raise ValueError("Jam full acquisition totals do not reconcile")
        all_passed = passed == 48
        expected_fields = sorted(
            set(JAM_FULL_AGGTRADES_HEADER) | set(JAM_FULL_KLINES_HEADER)
        )
        if self.inspected_market_field_names != expected_fields:
            raise ValueError("Jam full inspected-field boundary changed")
        if (
            self.decision
            != (
                JAM_FULL_ACQUISITION_PASS_DECISION
                if all_passed
                else JAM_FULL_ACQUISITION_FAIL_DECISION
            )
            or self.next_required_authorization
            != (
                JAM_FULL_ACQUISITION_NEXT_AUTHORIZATION
                if all_passed
                else JAM_FULL_ACQUISITION_NO_NEXT_AUTHORIZATION
            )
        ):
            raise ValueError("Jam full acquisition decision changed")
        if (
            self.feature_fields_created
            or self.parameters_defined
            or self.return_metrics_calculated
        ):
            raise ValueError("Jam full acquisition may contain no outcomes")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected_hash:
            raise ValueError("Jam full acquisition result hash does not match")
        return self


class JamFullAcquisitionAudit(BaseModel):
    schema_version: Literal[
        "aurex-jam-archive-full-acquisition-audit-v1"
    ] = JAM_FULL_ACQUISITION_AUDIT_SCHEMA_VERSION
    audited_at: datetime
    result_path: str
    result_file_sha256: str
    result_evidence_hash: str
    protocol_evidence_hash: str
    raw_manifest_hash: str
    raw_archive_count: Literal[96] = 96
    checksum_verified_count: Literal[96] = 96
    reconstructed_month_count: Literal[48] = 48
    return_metrics_calculated: Literal[False] = False
    decision: Literal[
        "PASS_2019_2022_ARCHIVE_ACQUISITION_AWAIT_NO_RETURN_FEATURE_SPECIFICATION",
        "STOP_JAM_SUCCESSOR_FULL_ARCHIVE_QUALITY_FAILED",
    ]
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "result_file_sha256",
        "result_evidence_hash",
        "protocol_evidence_hash",
        "raw_manifest_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> JamFullAcquisitionAudit:
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected_hash:
            raise ValueError("Jam full acquisition audit hash does not match")
        return self


def build_jam_full_acquisition_protocol(**values) -> JamFullAcquisitionProtocol:
    targets = sorted(values.pop("targets"), key=lambda item: item.key)
    payload = {
        "schema_version": JAM_FULL_ACQUISITION_PROTOCOL_SCHEMA_VERSION,
        "protocol_id": "jam-archive-full-acquisition-v1",
        "status": "FROZEN_PRE_FULL_ARCHIVE_REQUEST",
        "authorization_record": (
            "USER_AUTHORIZED_FROZEN_2019_2022_ARCHIVE_ACQUISITION"
        ),
        "census_result_path": (
            "data/evidence/jam_archive_metadata_census_result_v1.json"
        ),
        "targets": targets,
        "target_manifest_hash": universe_evidence_hash(
            {"targets": [target.model_dump() for target in targets]}
        ),
        "evidence_partition": (
            "JAM_PROVISIONAL_HISTORICAL_POOL_2019_2022_NO_RETURNS"
        ),
        "permitted_methods": ["GET", "HEAD"],
        "network_target_count": 94,
        "reused_pilot_target_count": 2,
        "maximum_head_requests": 282,
        "maximum_payload_get_requests": 282,
        "maximum_requests_total": 564,
        "maximum_retries_per_request": 2,
        "retry_backoff_seconds": [2, 5],
        "request_timeout_seconds": 90,
        "download_chunk_bytes": 1_048_576,
        "redirects_permitted": False,
        "range_resume_permitted": True,
        "maximum_archive_bytes": JAM_FULL_MAXIMUM_ARCHIVE_BYTES,
        "maximum_total_archive_bytes": JAM_FULL_MAXIMUM_TOTAL_ARCHIVE_BYTES,
        "maximum_member_uncompressed_bytes": JAM_FULL_MAXIMUM_MEMBER_BYTES,
        "maximum_total_member_uncompressed_bytes": (
            JAM_FULL_MAXIMUM_TOTAL_MEMBER_BYTES
        ),
        "maximum_zip_expansion_ratio": 100,
        "minimum_post_acquisition_free_disk_bytes": 20_000_000_000,
        "decimal_reconciliation_tolerance": "0.00000001",
        "market_values_permitted_for_quality_validation": True,
        "feature_calculation_permitted": False,
        "parameter_definition_permitted": False,
        "return_calculation_permitted": False,
        "strategy_execution_permitted": False,
        "candidate_creation_permitted": False,
        "forward_data_access_permitted": False,
        "testnet_strategy_orders_permitted": False,
        "production_permitted": False,
        "live_permitted": False,
        **values,
    }
    payload["limitations"] = sorted(set(payload["limitations"]))
    return JamFullAcquisitionProtocol(
        **payload,
        protocol_evidence_hash=universe_evidence_hash(payload),
    )


def build_jam_full_acquisition_result(**values) -> JamFullAcquisitionResult:
    months = sorted(values.pop("months"), key=lambda item: item.month)
    archives = [
        archive
        for month in months
        for archive in (month.aggregate_trades, month.klines_1m)
    ]
    passed = sum(item.month_pass for item in months)
    all_passed = passed == 48
    payload = {
        "schema_version": JAM_FULL_ACQUISITION_RESULT_SCHEMA_VERSION,
        "result_id": "jam-archive-full-acquisition-result-v1",
        "status": "COMPLETE_SOURCE_QUALITY_NO_RETURNS",
        "months": months,
        "passed_month_count": passed,
        "failed_month_count": 48 - passed,
        "total_archive_count": 96,
        "reused_pilot_archive_count": 2,
        "newly_acquired_archive_count": 94,
        "total_head_request_count": sum(
            item.head_request_count for item in archives
        ),
        "total_payload_get_request_count": sum(
            item.payload_get_request_count for item in archives
        ),
        "total_archive_bytes": sum(item.archive_bytes for item in archives),
        "total_member_uncompressed_bytes": sum(
            item.zip_uncompressed_bytes for item in archives
        ),
        "redirects_followed": 0,
        "evidence_partition": (
            "JAM_PROVISIONAL_HISTORICAL_POOL_2019_2022_NO_RETURNS"
        ),
        "decision": (
            JAM_FULL_ACQUISITION_PASS_DECISION
            if all_passed
            else JAM_FULL_ACQUISITION_FAIL_DECISION
        ),
        "next_required_authorization": (
            JAM_FULL_ACQUISITION_NEXT_AUTHORIZATION
            if all_passed
            else JAM_FULL_ACQUISITION_NO_NEXT_AUTHORIZATION
        ),
        "inspected_market_field_names": sorted(
            set(JAM_FULL_AGGTRADES_HEADER) | set(JAM_FULL_KLINES_HEADER)
        ),
        "feature_fields_created": [],
        "parameters_defined": [],
        "return_metrics_calculated": [],
        "strategy_executions": 0,
        "creates_candidate": False,
        "creates_paper_eligibility": False,
        "creates_testnet_order_authority": False,
        "creates_production_authority": False,
        "creates_live_eligibility": False,
        **values,
    }
    payload["limitations"] = sorted(set(payload["limitations"]))
    return JamFullAcquisitionResult(
        **payload,
        result_evidence_hash=universe_evidence_hash(payload),
    )


def build_jam_full_acquisition_audit(**values) -> JamFullAcquisitionAudit:
    payload = {
        "schema_version": JAM_FULL_ACQUISITION_AUDIT_SCHEMA_VERSION,
        "raw_archive_count": 96,
        "checksum_verified_count": 96,
        "reconstructed_month_count": 48,
        "return_metrics_calculated": False,
        **values,
    }
    return JamFullAcquisitionAudit(
        **payload,
        audit_evidence_hash=universe_evidence_hash(payload),
    )


def audit_jam_full_acquisition_protocol(
    protocol: JamFullAcquisitionProtocol,
) -> bool:
    return protocol.protocol_evidence_hash == universe_evidence_hash(
        protocol.model_dump(exclude={"protocol_evidence_hash"})
    )


def audit_jam_full_acquisition_result(result: JamFullAcquisitionResult) -> bool:
    return result.result_evidence_hash == universe_evidence_hash(
        result.model_dump(exclude={"result_evidence_hash"})
    )


def audit_jam_full_acquisition_audit(audit: JamFullAcquisitionAudit) -> bool:
    return audit.audit_evidence_hash == universe_evidence_hash(
        audit.model_dump(exclude={"audit_evidence_hash"})
    )
