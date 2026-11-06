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

FULL_DEVELOPMENT_MONTHS = tuple(
    f"{year}-{month:02d}"
    for year in range(2020, 2024)
    for month in range(1, 13)
)
FULL_DEVELOPMENT_TARGET_COUNT = 96
FULL_DEVELOPMENT_REUSE_TARGET_COUNT = 37
FULL_DEVELOPMENT_NETWORK_TARGET_COUNT = 59
FULL_DEVELOPMENT_AUTHORIZATION = (
    "AUTHORIZE_Q1_PAIRED_FULL_DEVELOPMENT_ARCHIVE_ACQUISITION"
)
SPOT_COLUMNS = (
    "aggregate_trade_id",
    "price",
    "quantity",
    "first_trade_id",
    "last_trade_id",
    "transact_time",
    "is_buyer_maker",
    "is_best_match",
)
RAW_COLUMNS = (
    "trade_id",
    "price",
    "quantity",
    "quote_quantity",
    "timestamp",
    "buyer_was_maker",
)


def spot_archive_url(month: str) -> str:
    return (
        "https://data.binance.vision/data/spot/monthly/aggTrades/BTCUSDT/"
        f"BTCUSDT-aggTrades-{month}.zip"
    )


def raw_archive_url(month: str) -> str:
    return (
        "https://data.binance.vision/data/futures/um/monthly/trades/BTCUSDT/"
        f"BTCUSDT-trades-{month}.zip"
    )


def spot_reuse_path(month: str) -> str | None:
    if month == "2020-01":
        return (
            "source_snapshots/q1_periodic_flow_payload_pilot_v1/SPOT/"
            "BTCUSDT-aggTrades-2020-01.zip"
        )
    if month <= "2022-12":
        return (
            f"jam_archive_full_acquisition_v1/BTCUSDT/{month}/aggTrades/"
            f"BTCUSDT-aggTrades-{month}.zip"
        )
    return None


def raw_reuse_path(month: str) -> str | None:
    if month == "2020-01":
        return (
            "source_snapshots/q1_periodic_flow_raw_trades_payload_pilot_v1/"
            "USD_M_PERPETUAL/BTCUSDT-trades-2020-01.zip"
        )
    return None


class PeriodicFlowDevelopmentTarget(BaseModel):
    product: Literal["SPOT", "USD_M_PERPETUAL"]
    family: Literal["aggTrades", "trades"]
    symbol: Literal["BTCUSDT"] = "BTCUSDT"
    month: str = Field(pattern=r"^20(20|21|22|23)-(0[1-9]|1[0-2])$")
    partition_role: Literal["DEVELOPMENT"] = "DEVELOPMENT"
    archive_url: str
    published_archive_sha256: str
    expected_member_name: str
    expected_columns: tuple[str, ...]
    expected_timestamp_unit: Literal["MILLISECONDS"] = "MILLISECONDS"
    reuse_candidate_path: str | None
    reuse_candidate_file_sha256: str | None
    reuse_revalidation_required: Literal[True] = True
    member_policy: Literal[
        "EXACT_EXPECTED_MEMBER_ONLY",
        "TOP_LEVEL_ONLY_IF_EXTRA_MEMBER_IS_BYTE_IDENTICAL",
    ]

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator(
        "published_archive_sha256",
        "reuse_candidate_file_sha256",
    )
    @classmethod
    def normalize_hashes(cls, value: str | None) -> str | None:
        return None if value is None else normalize_sha256(value)

    @model_validator(mode="after")
    def validate_target(self) -> PeriodicFlowDevelopmentTarget:
        is_spot = self.product == "SPOT"
        expected_family = "aggTrades" if is_spot else "trades"
        expected_url = spot_archive_url(self.month) if is_spot else raw_archive_url(
            self.month
        )
        expected_member = (
            f"BTCUSDT-aggTrades-{self.month}.csv"
            if is_spot
            else f"BTCUSDT-trades-{self.month}.csv"
        )
        expected_columns = SPOT_COLUMNS if is_spot else RAW_COLUMNS
        expected_reuse = (
            spot_reuse_path(self.month) if is_spot else raw_reuse_path(self.month)
        )
        expected_policy = (
            "TOP_LEVEL_ONLY_IF_EXTRA_MEMBER_IS_BYTE_IDENTICAL"
            if is_spot and self.month == "2021-12"
            else "EXACT_EXPECTED_MEMBER_ONLY"
        )
        if (
            self.month not in FULL_DEVELOPMENT_MONTHS
            or self.family != expected_family
            or self.archive_url != expected_url
            or self.expected_member_name != expected_member
            or self.expected_columns != expected_columns
            or self.reuse_candidate_path != expected_reuse
            or (self.reuse_candidate_file_sha256 is None) != (expected_reuse is None)
            or self.member_policy != expected_policy
        ):
            raise ValueError("Q1 full-development target changed")
        parsed = urlparse(self.archive_url)
        expected_fragment = (
            "/data/spot/monthly/aggTrades/BTCUSDT/"
            if is_spot
            else "/data/futures/um/monthly/trades/BTCUSDT/"
        )
        if (
            parsed.scheme != "https"
            or parsed.hostname != "data.binance.vision"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port is not None
            or parsed.query
            or parsed.fragment
            or expected_fragment not in parsed.path
            or not parsed.path.endswith(".zip")
        ):
            raise ValueError("Q1 full-development target URL changed")
        return self

    @property
    def key(self) -> tuple[str, str]:
        return self.month, self.product


class PeriodicFlowFullDevelopmentProtocol(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-full-development-acquisition-protocol-v1"
    ] = "aurex-q1-periodic-flow-full-development-acquisition-protocol-v1"
    protocol_id: Literal[
        "q1-periodic-flow-full-development-acquisition-v1"
    ] = "q1-periodic-flow-full-development-acquisition-v1"
    frozen_at: datetime
    status: Literal["FROZEN_PRE_FULL_DEVELOPMENT_ARCHIVE_REQUEST"] = (
        "FROZEN_PRE_FULL_DEVELOPMENT_ARCHIVE_REQUEST"
    )
    parent_result_file_sha256: str
    parent_result_evidence_hash: str
    parent_audit_file_sha256: str
    parent_audit_evidence_hash: str
    spot_census_result_file_sha256: str
    spot_census_result_evidence_hash: str
    spot_census_audit_file_sha256: str
    spot_census_audit_evidence_hash: str
    raw_census_result_file_sha256: str
    raw_census_result_evidence_hash: str
    raw_census_audit_file_sha256: str
    raw_census_audit_evidence_hash: str
    jam_acquisition_result_file_sha256: str
    jam_acquisition_result_evidence_hash: str
    jam_acquisition_audit_file_sha256: str
    jam_acquisition_audit_evidence_hash: str
    jam_remediation_result_file_sha256: str
    jam_remediation_result_evidence_hash: str
    jam_remediation_audit_file_sha256: str
    jam_remediation_audit_evidence_hash: str
    readiness_result_evidence_hash: str
    readiness_audit_evidence_hash: str
    builder_contract_hash: str
    targets: tuple[PeriodicFlowDevelopmentTarget, ...] = Field(
        min_length=FULL_DEVELOPMENT_TARGET_COUNT,
        max_length=FULL_DEVELOPMENT_TARGET_COUNT,
    )
    target_manifest_hash: str
    month_count: Literal[48] = 48
    spot_target_count: Literal[48] = 48
    raw_target_count: Literal[48] = 48
    reuse_candidate_count: Literal[37] = FULL_DEVELOPMENT_REUSE_TARGET_COUNT
    network_target_count: Literal[59] = FULL_DEVELOPMENT_NETWORK_TARGET_COUNT
    permitted_methods: tuple[Literal["GET"], ...] = ("GET",)
    archive_head_requests_permitted: Literal[False] = False
    maximum_payload_get_attempts: Literal[177] = 177
    maximum_attempts_per_network_target: Literal[3] = 3
    maximum_concurrency: Literal[1] = 1
    request_timeout_seconds: Literal[300] = 300
    retry_backoff_seconds: tuple[Literal[2], Literal[5]] = (2, 5)
    redirects_permitted: Literal[False] = False
    range_requests_permitted: Literal[False] = False
    archive_level_resume_permitted: Literal[True] = True
    partial_archive_reuse_permitted: Literal[False] = False
    request_marker_before_each_attempt_required: Literal[True] = True
    checkpoint_after_each_qualified_archive_required: Literal[True] = True
    maximum_archive_bytes_each: Literal[5_000_000_000] = 5_000_000_000
    maximum_new_archive_bytes_total: Literal[100_000_000_000] = 100_000_000_000
    maximum_member_uncompressed_bytes_each: Literal[30_000_000_000] = 30_000_000_000
    maximum_member_uncompressed_bytes_total: Literal[1_000_000_000_000] = (
        1_000_000_000_000
    )
    maximum_zip_expansion_ratio: Literal[100] = 100
    minimum_free_disk_bytes_after_acquisition: Literal[20_000_000_000] = (
        20_000_000_000
    )
    minimum_rows_each: Literal[100_000] = 100_000
    minimum_minute_coverage_fraction_each: Literal["0.99"] = "0.99"
    minimum_paired_minute_coverage_fraction_each: Literal["0.99"] = "0.99"
    maximum_event_gap_minutes: Literal[15] = 15
    maximum_duplicate_id_count: Literal[0] = 0
    maximum_non_increasing_id_count: Literal[0] = 0
    maximum_timestamp_regression_count: Literal[0] = 0
    maximum_spot_aggregate_id_gap_count: Literal[0] = 0
    maximum_spot_raw_range_gap_count: Literal[0] = 0
    maximum_raw_skipped_trade_id_fraction: Literal["0.001"] = "0.001"
    maximum_raw_single_skipped_trade_id_count: Literal[100] = 100
    required_buyer_maker_values: tuple[Literal[False], Literal[True]] = (False, True)
    parsed_structural_fields: tuple[str, ...] = (
        "aggregate_trade_id",
        "buyer_maker_boolean",
        "first_trade_id",
        "last_trade_id",
        "timestamp",
        "trade_id",
    )
    excluded_numeric_fields: tuple[str, ...] = (
        "price",
        "quantity",
        "quote_quantity",
    )
    price_or_quantity_parsing_permitted: Literal[False] = False
    feature_calculation_permitted: Literal[False] = False
    parameter_definition_permitted: Literal[False] = False
    return_calculation_permitted: Literal[False] = False
    validation_access_permitted: Literal[False] = False
    holdout_access_permitted: Literal[False] = False
    candidate_creation_permitted: Literal[False] = False
    pine_deployment_permitted: Literal[False] = False
    paper_operation_permitted: Literal[False] = False
    testnet_strategy_orders_permitted: Literal[False] = False
    production_permitted: Literal[False] = False
    live_permitted: Literal[False] = False
    next_authorization: Literal[
        "AUTHORIZE_Q1_PAIRED_FULL_DEVELOPMENT_ARCHIVE_ACQUISITION"
    ] = FULL_DEVELOPMENT_AUTHORIZATION
    limitations: tuple[str, ...] = Field(min_length=10)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "parent_result_file_sha256",
        "parent_result_evidence_hash",
        "parent_audit_file_sha256",
        "parent_audit_evidence_hash",
        "spot_census_result_file_sha256",
        "spot_census_result_evidence_hash",
        "spot_census_audit_file_sha256",
        "spot_census_audit_evidence_hash",
        "raw_census_result_file_sha256",
        "raw_census_result_evidence_hash",
        "raw_census_audit_file_sha256",
        "raw_census_audit_evidence_hash",
        "jam_acquisition_result_file_sha256",
        "jam_acquisition_result_evidence_hash",
        "jam_acquisition_audit_file_sha256",
        "jam_acquisition_audit_evidence_hash",
        "jam_remediation_result_file_sha256",
        "jam_remediation_result_evidence_hash",
        "jam_remediation_audit_file_sha256",
        "jam_remediation_audit_evidence_hash",
        "readiness_result_evidence_hash",
        "readiness_audit_evidence_hash",
        "builder_contract_hash",
        "target_manifest_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> PeriodicFlowFullDevelopmentProtocol:
        expected_keys = {
            (month, product)
            for month in FULL_DEVELOPMENT_MONTHS
            for product in ("SPOT", "USD_M_PERPETUAL")
        }
        target_keys = {target.key for target in self.targets}
        if (
            self.targets != tuple(sorted(self.targets, key=lambda item: item.key))
            or target_keys != expected_keys
            or len(target_keys) != FULL_DEVELOPMENT_TARGET_COUNT
            or sum(target.reuse_candidate_path is not None for target in self.targets)
            != FULL_DEVELOPMENT_REUSE_TARGET_COUNT
            or self.target_manifest_hash
            != universe_evidence_hash(
                {"targets": [target.model_dump() for target in self.targets]}
            )
            or self.parsed_structural_fields
            != tuple(sorted(set(self.parsed_structural_fields)))
            or self.excluded_numeric_fields
            != tuple(sorted(set(self.excluded_numeric_fields)))
            or self.limitations != tuple(sorted(set(self.limitations)))
        ):
            raise ValueError("Q1 full-development protocol scope changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("Q1 full-development protocol hash changed")
        return self


class PeriodicFlowFullDevelopmentProtocolAudit(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-full-development-acquisition-protocol-audit-v1"
    ] = "aurex-q1-periodic-flow-full-development-acquisition-protocol-audit-v1"
    audit_id: Literal[
        "q1-periodic-flow-full-development-acquisition-protocol-audit-v1"
    ] = "q1-periodic-flow-full-development-acquisition-protocol-audit-v1"
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    target_count: Literal[96] = 96
    month_count: Literal[48] = 48
    reuse_candidate_count: Literal[37] = 37
    network_target_count: Literal[59] = 59
    network_requests_made: Literal[0] = 0
    archive_payload_requests_made: Literal[0] = 0
    market_numeric_values_parsed: Literal[0] = 0
    authorizes_full_development_archive_acquisition: Literal[True] = True
    authorizes_features_or_outcomes: Literal[False] = False
    authorizes_trading: Literal[False] = False
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
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> PeriodicFlowFullDevelopmentProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 full-development protocol audit hash changed")
        return self


def _build(model, hash_field: str, values: dict):
    provisional = model.model_construct(**values, **{hash_field: "0" * 64})
    payload = provisional.model_dump()
    payload[hash_field] = universe_evidence_hash(
        provisional.model_dump(exclude={hash_field})
    )
    return model.model_validate(payload)


def build_full_development_protocol(
    **values,
) -> PeriodicFlowFullDevelopmentProtocol:
    payload = dict(values)
    payload["targets"] = tuple(sorted(payload["targets"], key=lambda item: item.key))
    payload["target_manifest_hash"] = universe_evidence_hash(
        {"targets": [target.model_dump() for target in payload["targets"]]}
    )
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(
        PeriodicFlowFullDevelopmentProtocol,
        "protocol_evidence_hash",
        payload,
    )


def build_full_development_protocol_audit(
    **values,
) -> PeriodicFlowFullDevelopmentProtocolAudit:
    return _build(
        PeriodicFlowFullDevelopmentProtocolAudit,
        "audit_evidence_hash",
        values,
    )


def audit_full_development_protocol(
    protocol: PeriodicFlowFullDevelopmentProtocol,
) -> bool:
    return protocol.protocol_evidence_hash == universe_evidence_hash(
        protocol.model_dump(exclude={"protocol_evidence_hash"})
    )


def audit_full_development_protocol_audit(
    audit: PeriodicFlowFullDevelopmentProtocolAudit,
) -> bool:
    return audit.audit_evidence_hash == universe_evidence_hash(
        audit.model_dump(exclude={"audit_evidence_hash"})
    )
