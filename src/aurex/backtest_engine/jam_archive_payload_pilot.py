from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

JAM_PAYLOAD_PILOT_PROTOCOL_SCHEMA_VERSION = (
    "aurex-jam-archive-payload-pilot-protocol-v1"
)
JAM_PAYLOAD_PILOT_RESULT_SCHEMA_VERSION = (
    "aurex-jam-archive-payload-pilot-result-v1"
)
JAM_PAYLOAD_PILOT_AUDIT_SCHEMA_VERSION = (
    "aurex-jam-archive-payload-pilot-audit-v1"
)
JAM_PAYLOAD_PILOT_MONTH = "2019-01"
JAM_PAYLOAD_PILOT_PASS_DECISION = (
    "PASS_ONE_MONTH_DATA_CAPABILITY_AWAIT_FULL_ACQUISITION_AUTHORIZATION"
)
JAM_PAYLOAD_PILOT_FAIL_DECISION = "STOP_JAM_SUCCESSOR_DATA_CAPABILITY_FAILED"
JAM_PAYLOAD_PILOT_NEXT_AUTHORIZATION = (
    "AUTHORIZE_FROZEN_2019_2022_ARCHIVE_ACQUISITION"
)
JAM_PAYLOAD_PILOT_NO_NEXT_AUTHORIZATION = "NONE_PILOT_FAILED"
JAM_PAYLOAD_PILOT_AGGTRADES_SHA256 = (
    "588bff60b17e906ad4b654d0f615d838a2b2ec36b7790e5db40c6d2a03556355"
)
JAM_PAYLOAD_PILOT_KLINES_SHA256 = (
    "08dd2f7306258d1b9fd0b9fc00ee807c1c96e9803c74c78c00a0072bfc826728"
)
JAM_PAYLOAD_PILOT_EXPECTED_MINUTES = 44_640
JAM_PAYLOAD_PILOT_MAXIMUM_ARCHIVE_BYTES = 750_000_000
JAM_PAYLOAD_PILOT_MAXIMUM_TOTAL_BYTES = 800_000_000
JAM_PAYLOAD_PILOT_MAXIMUM_MEMBER_BYTES = 4_000_000_000
JAM_PAYLOAD_PILOT_MAXIMUM_TOTAL_MEMBER_BYTES = 4_100_000_000
JAM_PAYLOAD_PILOT_AGGTRADES_HEADER = (
    "aggregate_trade_id",
    "price",
    "quantity",
    "first_trade_id",
    "last_trade_id",
    "transact_time",
    "is_buyer_maker",
    "is_best_match",
)
JAM_PAYLOAD_PILOT_KLINES_HEADER = (
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


def payload_archive_url(family: str) -> str:
    if family == "aggTrades":
        return (
            "https://data.binance.vision/data/spot/monthly/aggTrades/"
            "BTCUSDT/BTCUSDT-aggTrades-2019-01.zip"
        )
    if family == "klines_1m":
        return (
            "https://data.binance.vision/data/spot/monthly/klines/"
            "BTCUSDT/1m/BTCUSDT-1m-2019-01.zip"
        )
    raise ValueError(f"Unsupported Jam payload family: {family}")


def payload_archive_sha256(family: str) -> str:
    if family == "aggTrades":
        return JAM_PAYLOAD_PILOT_AGGTRADES_SHA256
    if family == "klines_1m":
        return JAM_PAYLOAD_PILOT_KLINES_SHA256
    raise ValueError(f"Unsupported Jam payload family: {family}")


class JamPayloadPilotTarget(BaseModel):
    family: Literal["aggTrades", "klines_1m"]
    symbol: Literal["BTCUSDT"] = "BTCUSDT"
    month: Literal["2019-01"] = JAM_PAYLOAD_PILOT_MONTH
    archive_url: str
    published_archive_sha256: str
    expected_csv_member: str
    expected_column_count: int

    model_config = ConfigDict(extra="forbid")

    @field_validator("published_archive_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_target(self) -> JamPayloadPilotTarget:
        expected_url = payload_archive_url(self.family)
        expected_member = (
            "BTCUSDT-aggTrades-2019-01.csv"
            if self.family == "aggTrades"
            else "BTCUSDT-1m-2019-01.csv"
        )
        expected_columns = 8 if self.family == "aggTrades" else 12
        if (
            self.archive_url != expected_url
            or self.published_archive_sha256
            != payload_archive_sha256(self.family)
            or self.expected_csv_member != expected_member
            or self.expected_column_count != expected_columns
        ):
            raise ValueError("Jam payload pilot target changed")
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
            raise ValueError("Jam payload pilot target must use exact Binance HTTPS")
        return self

    @property
    def key(self) -> str:
        return self.family


def authoritative_payload_targets() -> list[JamPayloadPilotTarget]:
    return [
        JamPayloadPilotTarget(
            family="aggTrades",
            archive_url=payload_archive_url("aggTrades"),
            published_archive_sha256=payload_archive_sha256("aggTrades"),
            expected_csv_member="BTCUSDT-aggTrades-2019-01.csv",
            expected_column_count=8,
        ),
        JamPayloadPilotTarget(
            family="klines_1m",
            archive_url=payload_archive_url("klines_1m"),
            published_archive_sha256=payload_archive_sha256("klines_1m"),
            expected_csv_member="BTCUSDT-1m-2019-01.csv",
            expected_column_count=12,
        ),
    ]


class JamPayloadPilotProtocol(BaseModel):
    schema_version: Literal[
        "aurex-jam-archive-payload-pilot-protocol-v1"
    ] = JAM_PAYLOAD_PILOT_PROTOCOL_SCHEMA_VERSION
    protocol_id: Literal["jam-archive-payload-pilot-v1"] = (
        "jam-archive-payload-pilot-v1"
    )
    protocol_version: Literal["1.0.0"] = "1.0.0"
    frozen_at: datetime
    status: Literal["FROZEN_PRE_ARCHIVE_REQUEST"] = "FROZEN_PRE_ARCHIVE_REQUEST"
    authorization_record: Literal[
        "USER_AUTHORIZED_FROZEN_ONE_MONTH_ARCHIVE_PAYLOAD_PILOT"
    ] = "USER_AUTHORIZED_FROZEN_ONE_MONTH_ARCHIVE_PAYLOAD_PILOT"
    census_contract_path: Literal[
        "data/evidence/jam_archive_metadata_census_contract_v1.json"
    ] = "data/evidence/jam_archive_metadata_census_contract_v1.json"
    census_contract_evidence_hash: str
    census_result_path: Literal[
        "data/evidence/jam_archive_metadata_census_result_v1.json"
    ] = "data/evidence/jam_archive_metadata_census_result_v1.json"
    census_result_file_sha256: str
    census_result_evidence_hash: str
    census_audit_path: Literal[
        "data/evidence/jam_archive_metadata_census_audit_v1.json"
    ] = "data/evidence/jam_archive_metadata_census_audit_v1.json"
    census_audit_evidence_hash: str
    builder_contract_hash: str
    pilot_month: Literal["2019-01"] = JAM_PAYLOAD_PILOT_MONTH
    month_selection_rule: Literal[
        "EARLIEST_MONTH_IN_PROVISIONAL_POOL_NO_OUTCOME_SELECTION"
    ] = "EARLIEST_MONTH_IN_PROVISIONAL_POOL_NO_OUTCOME_SELECTION"
    targets: list[JamPayloadPilotTarget] = Field(min_length=2, max_length=2)
    target_manifest_hash: str
    permitted_methods: list[str] = Field(default_factory=lambda: ["GET", "HEAD"])
    maximum_head_requests: Literal[6] = 6
    maximum_payload_get_requests: Literal[6] = 6
    maximum_requests_total: Literal[12] = 12
    maximum_retries_per_request: Literal[2] = 2
    retry_backoff_seconds: list[int] = Field(default_factory=lambda: [2, 5])
    request_timeout_seconds: Literal[60] = 60
    download_chunk_bytes: Literal[1048576] = 1_048_576
    redirects_permitted: Literal[False] = False
    range_resume_permitted: Literal[True] = True
    maximum_archive_bytes: Literal[750000000] = (
        JAM_PAYLOAD_PILOT_MAXIMUM_ARCHIVE_BYTES
    )
    maximum_total_archive_bytes: Literal[800000000] = (
        JAM_PAYLOAD_PILOT_MAXIMUM_TOTAL_BYTES
    )
    maximum_member_uncompressed_bytes: Literal[4000000000] = (
        JAM_PAYLOAD_PILOT_MAXIMUM_MEMBER_BYTES
    )
    maximum_total_member_uncompressed_bytes: Literal[4100000000] = (
        JAM_PAYLOAD_PILOT_MAXIMUM_TOTAL_MEMBER_BYTES
    )
    maximum_zip_expansion_ratio: Literal[100] = 100
    minimum_free_disk_bytes: Literal[5000000000] = 5_000_000_000
    exact_kline_count_required: Literal[44640] = (
        JAM_PAYLOAD_PILOT_EXPECTED_MINUTES
    )
    decimal_reconciliation_tolerance: Literal["0.00000001"] = "0.00000001"
    market_values_permitted_for_capability_validation: Literal[True] = True
    feature_calculation_permitted: Literal[False] = False
    parameter_definition_permitted: Literal[False] = False
    return_calculation_permitted: Literal[False] = False
    strategy_execution_permitted: Literal[False] = False
    candidate_creation_permitted: Literal[False] = False
    forward_data_access_permitted: Literal[False] = False
    testnet_strategy_orders_permitted: Literal[False] = False
    production_permitted: Literal[False] = False
    live_permitted: Literal[False] = False
    limitations: list[str] = Field(min_length=8)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "census_contract_evidence_hash",
        "census_result_file_sha256",
        "census_result_evidence_hash",
        "census_audit_evidence_hash",
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
    def validate_protocol(self) -> JamPayloadPilotProtocol:
        expected_targets = authoritative_payload_targets()
        if self.targets != expected_targets:
            raise ValueError("Jam payload pilot target matrix changed")
        expected_manifest_hash = universe_evidence_hash(
            {"targets": [target.model_dump() for target in expected_targets]}
        )
        if self.target_manifest_hash != expected_manifest_hash:
            raise ValueError("Jam payload pilot target manifest changed")
        if self.permitted_methods != ["GET", "HEAD"]:
            raise ValueError("Jam payload pilot HTTP method policy changed")
        if self.retry_backoff_seconds != [2, 5]:
            raise ValueError("Jam payload pilot retry policy changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected_hash:
            raise ValueError("Jam payload pilot protocol hash does not match")
        return self


class JamPayloadHeadObservation(BaseModel):
    family: Literal["aggTrades", "klines_1m"]
    archive_url: str
    final_url: str
    observed_at: datetime
    http_status: Literal[200]
    content_length_bytes: int = Field(gt=0, le=750_000_000)
    accept_ranges: str
    request_attempt_count: int = Field(ge=1, le=3)
    redirect_count: Literal[0] = 0

    model_config = ConfigDict(extra="forbid")

    @field_validator("observed_at")
    @classmethod
    def normalize_observed_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_observation(self) -> JamPayloadHeadObservation:
        target = next(
            target
            for target in authoritative_payload_targets()
            if target.family == self.family
        )
        if self.archive_url != target.archive_url or self.final_url != target.archive_url:
            raise ValueError("Jam payload pilot HEAD URL changed")
        return self

    @property
    def key(self) -> str:
        return self.family


class JamPayloadArchiveEvidence(BaseModel):
    family: Literal["aggTrades", "klines_1m"]
    archive_url: str
    local_path: str
    archive_bytes: int = Field(gt=0, le=750_000_000)
    archive_sha256: str
    published_archive_sha256: str
    checksum_verified: Literal[True] = True
    csv_member_name: str
    zip_compressed_bytes: int = Field(gt=0, le=750_000_000)
    zip_uncompressed_bytes: int = Field(gt=0, le=4_000_000_000)
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
    expected_minute_count: Literal[44640] = JAM_PAYLOAD_PILOT_EXPECTED_MINUTES
    inspected_field_names: list[str]
    payload_get_request_count: int = Field(ge=1, le=3)
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
    def validate_evidence(self) -> JamPayloadArchiveEvidence:
        target = next(
            target
            for target in authoritative_payload_targets()
            if target.family == self.family
        )
        expected_fields = (
            sorted(JAM_PAYLOAD_PILOT_AGGTRADES_HEADER)
            if self.family == "aggTrades"
            else sorted(JAM_PAYLOAD_PILOT_KLINES_HEADER)
        )
        expected_gap_count = 0
        expected_row_count = (
            None if self.family == "aggTrades" else JAM_PAYLOAD_PILOT_EXPECTED_MINUTES
        )
        passed = (
            self.archive_url == target.archive_url
            and self.archive_sha256 == target.published_archive_sha256
            and self.published_archive_sha256
            == target.published_archive_sha256
            and self.csv_member_name == target.expected_csv_member
            and self.column_count == target.expected_column_count
            and self.inspected_field_names == expected_fields
            and self.gap_count == expected_gap_count
            and (
                expected_row_count is None
                or self.row_count == expected_row_count
            )
            and (
                self.family != "klines_1m"
                or self.unique_minute_count == JAM_PAYLOAD_PILOT_EXPECTED_MINUTES
            )
        )
        if self.archive_pass != passed or bool(self.reason_codes) == passed:
            raise ValueError("Jam payload archive decision does not reconcile")
        return self

    @property
    def key(self) -> str:
        return self.family


class JamPayloadReconciliationEvidence(BaseModel):
    month: Literal["2019-01"] = JAM_PAYLOAD_PILOT_MONTH
    expected_minute_count: Literal[44640] = JAM_PAYLOAD_PILOT_EXPECTED_MINUTES
    compared_minute_count: Literal[44640] = JAM_PAYLOAD_PILOT_EXPECTED_MINUTES
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
    reason_codes: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("reason_codes")
    @classmethod
    def normalize_reasons(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_reconciliation(self) -> JamPayloadReconciliationEvidence:
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
            self.aggregate_trade_covered_minute_count
            + self.empty_trade_minute_count
            != JAM_PAYLOAD_PILOT_EXPECTED_MINUTES
            or self.reconciliation_pass != passed
            or bool(self.reason_codes) == passed
        ):
            raise ValueError("Jam payload reconciliation does not reconcile")
        return self


class JamPayloadPilotResult(BaseModel):
    schema_version: Literal[
        "aurex-jam-archive-payload-pilot-result-v1"
    ] = JAM_PAYLOAD_PILOT_RESULT_SCHEMA_VERSION
    result_id: Literal["jam-archive-payload-pilot-result-v1"] = (
        "jam-archive-payload-pilot-result-v1"
    )
    generated_at: datetime
    status: Literal["COMPLETE_DATA_CAPABILITY_NO_RETURNS"] = (
        "COMPLETE_DATA_CAPABILITY_NO_RETURNS"
    )
    protocol_evidence_hash: str
    runner_contract_hash: str
    head_observations: list[JamPayloadHeadObservation] = Field(
        min_length=2,
        max_length=2,
    )
    archive_evidence: list[JamPayloadArchiveEvidence] = Field(
        min_length=2,
        max_length=2,
    )
    reconciliation: JamPayloadReconciliationEvidence
    total_head_request_count: int = Field(ge=2, le=6)
    total_payload_get_request_count: int = Field(ge=2, le=6)
    total_archive_bytes: int = Field(gt=0, le=800_000_000)
    total_member_uncompressed_bytes: int = Field(gt=0, le=4_100_000_000)
    redirects_followed: Literal[0] = 0
    decision: Literal[
        "PASS_ONE_MONTH_DATA_CAPABILITY_AWAIT_FULL_ACQUISITION_AUTHORIZATION",
        "STOP_JAM_SUCCESSOR_DATA_CAPABILITY_FAILED",
    ]
    next_required_authorization: Literal[
        "AUTHORIZE_FROZEN_2019_2022_ARCHIVE_ACQUISITION",
        "NONE_PILOT_FAILED",
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
    limitations: list[str] = Field(min_length=8)
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
    def validate_result(self) -> JamPayloadPilotResult:
        if (
            self.head_observations
            != sorted(self.head_observations, key=lambda item: item.key)
            or self.archive_evidence
            != sorted(self.archive_evidence, key=lambda item: item.key)
            or {item.key for item in self.head_observations}
            != {"aggTrades", "klines_1m"}
            or {item.key for item in self.archive_evidence}
            != {"aggTrades", "klines_1m"}
        ):
            raise ValueError("Jam payload pilot result matrix changed")
        passed = (
            all(item.archive_pass for item in self.archive_evidence)
            and self.reconciliation.reconciliation_pass
        )
        if (
            self.total_head_request_count
            != sum(item.request_attempt_count for item in self.head_observations)
            or self.total_payload_get_request_count
            != sum(
                item.payload_get_request_count for item in self.archive_evidence
            )
            or self.total_archive_bytes
            != sum(item.archive_bytes for item in self.archive_evidence)
            or self.total_member_uncompressed_bytes
            != sum(
                item.zip_uncompressed_bytes for item in self.archive_evidence
            )
        ):
            raise ValueError("Jam payload pilot resource totals do not reconcile")
        expected_fields = sorted(
            set(JAM_PAYLOAD_PILOT_AGGTRADES_HEADER)
            | set(JAM_PAYLOAD_PILOT_KLINES_HEADER)
        )
        if self.inspected_market_field_names != expected_fields:
            raise ValueError("Jam payload pilot inspected-field boundary changed")
        if (
            self.decision
            != (
                JAM_PAYLOAD_PILOT_PASS_DECISION
                if passed
                else JAM_PAYLOAD_PILOT_FAIL_DECISION
            )
            or self.next_required_authorization
            != (
                JAM_PAYLOAD_PILOT_NEXT_AUTHORIZATION
                if passed
                else JAM_PAYLOAD_PILOT_NO_NEXT_AUTHORIZATION
            )
        ):
            raise ValueError("Jam payload pilot decision does not reconcile")
        if (
            self.feature_fields_created
            or self.parameters_defined
            or self.return_metrics_calculated
        ):
            raise ValueError("Jam payload pilot may contain no research outcomes")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected_hash:
            raise ValueError("Jam payload pilot result hash does not match")
        return self


class JamPayloadPilotAudit(BaseModel):
    schema_version: Literal[
        "aurex-jam-archive-payload-pilot-audit-v1"
    ] = JAM_PAYLOAD_PILOT_AUDIT_SCHEMA_VERSION
    audited_at: datetime
    result_path: str
    result_file_sha256: str
    result_evidence_hash: str
    protocol_evidence_hash: str
    archive_file_sha256: dict[str, str]
    archive_file_bytes: dict[str, int]
    archive_count: Literal[2] = 2
    checksum_verified_count: Literal[2] = 2
    reconciliation_rebuilt: Literal[True] = True
    return_metrics_calculated: Literal[False] = False
    decision: Literal[
        "PASS_ONE_MONTH_DATA_CAPABILITY_AWAIT_FULL_ACQUISITION_AUTHORIZATION",
        "STOP_JAM_SUCCESSOR_DATA_CAPABILITY_FAILED",
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
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("archive_file_sha256")
    @classmethod
    def normalize_archive_hashes(cls, value: dict[str, str]) -> dict[str, str]:
        normalized = {
            key: normalize_sha256(item) for key, item in sorted(value.items())
        }
        if set(normalized) != {"aggTrades", "klines_1m"}:
            raise ValueError("Jam payload pilot audit archive matrix changed")
        return normalized

    @field_validator("archive_file_bytes")
    @classmethod
    def normalize_archive_bytes(cls, value: dict[str, int]) -> dict[str, int]:
        normalized = dict(sorted(value.items()))
        if (
            set(normalized) != {"aggTrades", "klines_1m"}
            or any(item <= 0 for item in normalized.values())
        ):
            raise ValueError("Jam payload pilot audit byte matrix changed")
        return normalized

    @model_validator(mode="after")
    def validate_audit(self) -> JamPayloadPilotAudit:
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected_hash:
            raise ValueError("Jam payload pilot audit hash does not match")
        return self


def build_jam_payload_pilot_protocol(**values) -> JamPayloadPilotProtocol:
    targets = authoritative_payload_targets()
    payload = {
        "schema_version": JAM_PAYLOAD_PILOT_PROTOCOL_SCHEMA_VERSION,
        "protocol_id": "jam-archive-payload-pilot-v1",
        "protocol_version": "1.0.0",
        "status": "FROZEN_PRE_ARCHIVE_REQUEST",
        "authorization_record": (
            "USER_AUTHORIZED_FROZEN_ONE_MONTH_ARCHIVE_PAYLOAD_PILOT"
        ),
        "census_contract_path": (
            "data/evidence/jam_archive_metadata_census_contract_v1.json"
        ),
        "census_result_path": (
            "data/evidence/jam_archive_metadata_census_result_v1.json"
        ),
        "census_audit_path": (
            "data/evidence/jam_archive_metadata_census_audit_v1.json"
        ),
        "pilot_month": JAM_PAYLOAD_PILOT_MONTH,
        "month_selection_rule": (
            "EARLIEST_MONTH_IN_PROVISIONAL_POOL_NO_OUTCOME_SELECTION"
        ),
        "targets": targets,
        "target_manifest_hash": universe_evidence_hash(
            {"targets": [target.model_dump() for target in targets]}
        ),
        "permitted_methods": ["GET", "HEAD"],
        "maximum_head_requests": 6,
        "maximum_payload_get_requests": 6,
        "maximum_requests_total": 12,
        "maximum_retries_per_request": 2,
        "retry_backoff_seconds": [2, 5],
        "request_timeout_seconds": 60,
        "download_chunk_bytes": 1_048_576,
        "redirects_permitted": False,
        "range_resume_permitted": True,
        "maximum_archive_bytes": JAM_PAYLOAD_PILOT_MAXIMUM_ARCHIVE_BYTES,
        "maximum_total_archive_bytes": JAM_PAYLOAD_PILOT_MAXIMUM_TOTAL_BYTES,
        "maximum_member_uncompressed_bytes": (
            JAM_PAYLOAD_PILOT_MAXIMUM_MEMBER_BYTES
        ),
        "maximum_total_member_uncompressed_bytes": (
            JAM_PAYLOAD_PILOT_MAXIMUM_TOTAL_MEMBER_BYTES
        ),
        "maximum_zip_expansion_ratio": 100,
        "minimum_free_disk_bytes": 5_000_000_000,
        "exact_kline_count_required": JAM_PAYLOAD_PILOT_EXPECTED_MINUTES,
        "decimal_reconciliation_tolerance": "0.00000001",
        "market_values_permitted_for_capability_validation": True,
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
    return JamPayloadPilotProtocol(
        **payload,
        protocol_evidence_hash=universe_evidence_hash(payload),
    )


def build_jam_payload_pilot_result(**values) -> JamPayloadPilotResult:
    head_observations = sorted(
        values.pop("head_observations"),
        key=lambda item: item.key,
    )
    archive_evidence = sorted(
        values.pop("archive_evidence"),
        key=lambda item: item.key,
    )
    passed = (
        all(item.archive_pass for item in archive_evidence)
        and values["reconciliation"].reconciliation_pass
    )
    payload = {
        "schema_version": JAM_PAYLOAD_PILOT_RESULT_SCHEMA_VERSION,
        "result_id": "jam-archive-payload-pilot-result-v1",
        "status": "COMPLETE_DATA_CAPABILITY_NO_RETURNS",
        "head_observations": head_observations,
        "archive_evidence": archive_evidence,
        "total_head_request_count": sum(
            item.request_attempt_count for item in head_observations
        ),
        "total_payload_get_request_count": sum(
            item.payload_get_request_count for item in archive_evidence
        ),
        "total_archive_bytes": sum(
            item.archive_bytes for item in archive_evidence
        ),
        "total_member_uncompressed_bytes": sum(
            item.zip_uncompressed_bytes for item in archive_evidence
        ),
        "redirects_followed": 0,
        "decision": (
            JAM_PAYLOAD_PILOT_PASS_DECISION
            if passed
            else JAM_PAYLOAD_PILOT_FAIL_DECISION
        ),
        "next_required_authorization": (
            JAM_PAYLOAD_PILOT_NEXT_AUTHORIZATION
            if passed
            else JAM_PAYLOAD_PILOT_NO_NEXT_AUTHORIZATION
        ),
        "inspected_market_field_names": sorted(
            set(JAM_PAYLOAD_PILOT_AGGTRADES_HEADER)
            | set(JAM_PAYLOAD_PILOT_KLINES_HEADER)
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
    return JamPayloadPilotResult(
        **payload,
        result_evidence_hash=universe_evidence_hash(payload),
    )


def build_jam_payload_pilot_audit(**values) -> JamPayloadPilotAudit:
    payload = {
        "schema_version": JAM_PAYLOAD_PILOT_AUDIT_SCHEMA_VERSION,
        "archive_count": 2,
        "checksum_verified_count": 2,
        "reconciliation_rebuilt": True,
        "return_metrics_calculated": False,
        **values,
    }
    return JamPayloadPilotAudit(
        **payload,
        audit_evidence_hash=universe_evidence_hash(payload),
    )


def audit_jam_payload_pilot_protocol(
    protocol: JamPayloadPilotProtocol,
) -> bool:
    return protocol.protocol_evidence_hash == universe_evidence_hash(
        protocol.model_dump(exclude={"protocol_evidence_hash"})
    )


def audit_jam_payload_pilot_result(result: JamPayloadPilotResult) -> bool:
    return result.result_evidence_hash == universe_evidence_hash(
        result.model_dump(exclude={"result_evidence_hash"})
    )


def audit_jam_payload_pilot_audit(audit: JamPayloadPilotAudit) -> bool:
    return audit.audit_evidence_hash == universe_evidence_hash(
        audit.model_dump(exclude={"audit_evidence_hash"})
    )
