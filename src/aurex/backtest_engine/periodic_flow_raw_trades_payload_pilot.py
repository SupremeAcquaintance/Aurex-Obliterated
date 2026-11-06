from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.periodic_flow_payload_pilot import (
    PeriodicFlowPairedClockEvidence,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

RAW_PAYLOAD_MONTH = "2020-01"
RAW_PAYLOAD_EXPECTED_MINUTES = 44_640
RAW_PAYLOAD_ARCHIVE_URL = (
    "https://data.binance.vision/data/futures/um/monthly/trades/"
    "BTCUSDT/BTCUSDT-trades-2020-01.zip"
)
RAW_PAYLOAD_ARCHIVE_SHA256 = (
    "5d3b5ab977aa3c10e40928ce8e2fcf33bc0406235bbb7413a95f067189aa8939"
)
SPOT_ARCHIVE_SHA256 = (
    "ea2f0aa850fb08b5c8124d2f8080c03689c30cdadf797363fc74b506b92a8d8b"
)
SPOT_LOCAL_PATH = (
    "source_snapshots/q1_periodic_flow_payload_pilot_v1/"
    "SPOT/BTCUSDT-aggTrades-2020-01.zip"
)
RAW_LOCAL_PATH = (
    "source_snapshots/q1_periodic_flow_raw_trades_payload_pilot_v1/"
    "USD_M_PERPETUAL/BTCUSDT-trades-2020-01.zip"
)
RAW_TRADE_COLUMNS = (
    "trade_id",
    "price",
    "quantity",
    "quote_quantity",
    "timestamp",
    "buyer_was_maker",
)
RAW_PAYLOAD_PASS_DECISION = (
    "PERMIT_Q1_PAIRED_FULL_DEVELOPMENT_ACQUISITION_PROTOCOL"
)
RAW_PAYLOAD_FAIL_DECISION = "STOP_Q1_USDM_RAW_TRADES_PAYLOAD_CAPABILITY_FAILED"
RAW_PAYLOAD_PASS_AUTHORIZATION = (
    "AUTHORIZE_Q1_PAIRED_FULL_DEVELOPMENT_ACQUISITION_PROTOCOL"
)
RAW_PAYLOAD_FAIL_AUTHORIZATION = "NONE_RAW_TRADES_PAYLOAD_PILOT_FAILED"


class QualifiedSpotPayloadReference(BaseModel):
    product: Literal["SPOT"] = "SPOT"
    family: Literal["aggTrades"] = "aggTrades"
    symbol: Literal["BTCUSDT"] = "BTCUSDT"
    month: Literal["2020-01"] = RAW_PAYLOAD_MONTH
    local_path: Literal[
        "source_snapshots/q1_periodic_flow_payload_pilot_v1/"
        "SPOT/BTCUSDT-aggTrades-2020-01.zip"
    ] = SPOT_LOCAL_PATH
    archive_sha256: Literal[
        "ea2f0aa850fb08b5c8124d2f8080c03689c30cdadf797363fc74b506b92a8d8b"
    ] = SPOT_ARCHIVE_SHA256
    row_count: Literal[14_051_798] = 14_051_798
    first_timestamp_ms: Literal[1_577_836_800_594] = 1_577_836_800_594
    last_timestamp_ms: Literal[1_580_515_198_791] = 1_580_515_198_791
    unique_minute_count: Literal[44_640] = 44_640
    source_result_file_sha256: str
    source_result_evidence_hash: str
    source_audit_file_sha256: str
    source_audit_evidence_hash: str
    source_archive_pass: Literal[True] = True

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator(
        "source_result_file_sha256",
        "source_result_evidence_hash",
        "source_audit_file_sha256",
        "source_audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)


class RawTradesPayloadTarget(BaseModel):
    product: Literal["USD_M_PERPETUAL"] = "USD_M_PERPETUAL"
    family: Literal["trades"] = "trades"
    symbol: Literal["BTCUSDT"] = "BTCUSDT"
    month: Literal["2020-01"] = RAW_PAYLOAD_MONTH
    partition_role: Literal["DEVELOPMENT"] = "DEVELOPMENT"
    archive_url: Literal[
        "https://data.binance.vision/data/futures/um/monthly/trades/"
        "BTCUSDT/BTCUSDT-trades-2020-01.zip"
    ] = RAW_PAYLOAD_ARCHIVE_URL
    published_archive_sha256: Literal[
        "5d3b5ab977aa3c10e40928ce8e2fcf33bc0406235bbb7413a95f067189aa8939"
    ] = RAW_PAYLOAD_ARCHIVE_SHA256
    expected_member_name: Literal["BTCUSDT-trades-2020-01.csv"] = (
        "BTCUSDT-trades-2020-01.csv"
    )
    expected_columns: tuple[str, ...] = RAW_TRADE_COLUMNS
    expected_column_count: Literal[6] = 6
    expected_timestamp_unit: Literal["MILLISECONDS"] = "MILLISECONDS"

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_target(self) -> RawTradesPayloadTarget:
        if self.expected_columns != RAW_TRADE_COLUMNS:
            raise ValueError("Q1 raw-trades payload schema changed")
        return self


class RawTradesPayloadPilotProtocol(BaseModel):
    schema_version: Literal[
        "aurex-q1-usdm-raw-trades-payload-pilot-protocol-v1"
    ] = "aurex-q1-usdm-raw-trades-payload-pilot-protocol-v1"
    protocol_id: Literal["q1-usdm-raw-trades-payload-pilot-v1"] = (
        "q1-usdm-raw-trades-payload-pilot-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_PRE_ONE_RAW_TRADES_PAYLOAD_GET"] = (
        "FROZEN_PRE_ONE_RAW_TRADES_PAYLOAD_GET"
    )
    raw_census_result_file_sha256: str
    raw_census_result_evidence_hash: str
    raw_census_audit_file_sha256: str
    raw_census_audit_evidence_hash: str
    source_adjudication_result_file_sha256: str
    source_adjudication_result_evidence_hash: str
    source_adjudication_audit_file_sha256: str
    source_adjudication_audit_evidence_hash: str
    builder_contract_hash: str
    qualified_spot_reference: QualifiedSpotPayloadReference
    target: RawTradesPayloadTarget
    target_manifest_hash: str
    maximum_unique_archive_urls: Literal[1] = 1
    maximum_attempts_per_archive: Literal[3] = 3
    maximum_payload_get_attempts: Literal[3] = 3
    request_timeout_seconds: Literal[180] = 180
    retry_backoff_seconds: tuple[Literal[1], Literal[3]] = (1, 3)
    redirects_permitted: Literal[False] = False
    range_requests_permitted: Literal[False] = False
    maximum_archive_bytes: Literal[1_000_000_000] = 1_000_000_000
    maximum_member_uncompressed_bytes: Literal[10_000_000_000] = 10_000_000_000
    maximum_zip_expansion_ratio: Literal[100] = 100
    minimum_free_disk_bytes_after_download: Literal[5_000_000_000] = 5_000_000_000
    minimum_rows: Literal[100_000] = 100_000
    minimum_minute_coverage_fraction: Decimal = Decimal("0.99")
    minimum_paired_minute_coverage_fraction: Decimal = Decimal("0.99")
    maximum_event_gap_minutes: Literal[15] = 15
    maximum_trade_id_non_increasing_count: Literal[0] = 0
    maximum_trade_id_duplicate_count: Literal[0] = 0
    maximum_skipped_trade_id_fraction: Decimal = Decimal("0.001")
    maximum_single_skipped_trade_id_count: Literal[100] = 100
    maximum_timestamp_regression_count: Literal[0] = 0
    expected_month_minute_count: Literal[44_640] = RAW_PAYLOAD_EXPECTED_MINUTES
    header_policy: Literal["EXACT_DOCUMENTED_OR_HEADERLESS"] = (
        "EXACT_DOCUMENTED_OR_HEADERLESS"
    )
    parsed_numeric_columns: tuple[str, ...] = ("trade_id", "timestamp")
    excluded_numeric_columns: tuple[str, ...] = (
        "price",
        "quantity",
        "quote_quantity",
    )
    price_or_quantity_parsing_permitted: Literal[False] = False
    feature_calculation_permitted: Literal[False] = False
    parameter_definition_permitted: Literal[False] = False
    return_calculation_permitted: Literal[False] = False
    validation_outcomes_permitted: Literal[False] = False
    holdout_access_permitted: Literal[False] = False
    candidate_creation_permitted: Literal[False] = False
    paper_operation_permitted: Literal[False] = False
    testnet_strategy_orders_permitted: Literal[False] = False
    production_permitted: Literal[False] = False
    live_permitted: Literal[False] = False
    limitations: tuple[str, ...] = Field(min_length=9)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "raw_census_result_file_sha256",
        "raw_census_result_evidence_hash",
        "raw_census_audit_file_sha256",
        "raw_census_audit_evidence_hash",
        "source_adjudication_result_file_sha256",
        "source_adjudication_result_evidence_hash",
        "source_adjudication_audit_file_sha256",
        "source_adjudication_audit_evidence_hash",
        "builder_contract_hash",
        "target_manifest_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> RawTradesPayloadPilotProtocol:
        expected_manifest = universe_evidence_hash(
            {
                "qualified_spot_reference": self.qualified_spot_reference.model_dump(),
                "target": self.target.model_dump(),
            }
        )
        if (
            self.target_manifest_hash != expected_manifest
            or self.minimum_minute_coverage_fraction != Decimal("0.99")
            or self.minimum_paired_minute_coverage_fraction != Decimal("0.99")
            or self.maximum_skipped_trade_id_fraction != Decimal("0.001")
            or self.parsed_numeric_columns != ("trade_id", "timestamp")
            or self.excluded_numeric_columns
            != ("price", "quantity", "quote_quantity")
            or self.limitations != tuple(sorted(set(self.limitations)))
        ):
            raise ValueError("Q1 raw-trades payload protocol scope changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("Q1 raw-trades payload protocol hash changed")
        return self


class RawTradesPayloadProtocolAudit(BaseModel):
    schema_version: Literal[
        "aurex-q1-usdm-raw-trades-payload-protocol-audit-v1"
    ] = "aurex-q1-usdm-raw-trades-payload-protocol-audit-v1"
    audit_id: Literal["q1-usdm-raw-trades-payload-protocol-audit-v1"] = (
        "q1-usdm-raw-trades-payload-protocol-audit-v1"
    )
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    archive_target_count: Literal[1] = 1
    qualified_spot_reference_count: Literal[1] = 1
    network_requests_made: Literal[0] = 0
    payload_requests_made: Literal[0] = 0
    price_or_quantity_values_parsed: tuple[str, ...] = ()
    authorizes_one_raw_payload: Literal[True] = True
    authorizes_full_acquisition: Literal[False] = False
    authorizes_outcomes: Literal[False] = False
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
    def validate_audit(self) -> RawTradesPayloadProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 raw payload protocol audit hash changed")
        return self


class RawTradesArchiveEvidence(BaseModel):
    product: Literal["USD_M_PERPETUAL"] = "USD_M_PERPETUAL"
    family: Literal["trades"] = "trades"
    archive_url: Literal[
        "https://data.binance.vision/data/futures/um/monthly/trades/"
        "BTCUSDT/BTCUSDT-trades-2020-01.zip"
    ] = RAW_PAYLOAD_ARCHIVE_URL
    local_path: Literal[
        "source_snapshots/q1_periodic_flow_raw_trades_payload_pilot_v1/"
        "USD_M_PERPETUAL/BTCUSDT-trades-2020-01.zip"
    ] = RAW_LOCAL_PATH
    archive_bytes: int = Field(gt=0, le=1_000_000_000)
    archive_sha256: Literal[
        "5d3b5ab977aa3c10e40928ce8e2fcf33bc0406235bbb7413a95f067189aa8939"
    ] = RAW_PAYLOAD_ARCHIVE_SHA256
    checksum_verified: Literal[True] = True
    csv_member_name: Literal["BTCUSDT-trades-2020-01.csv"] = (
        "BTCUSDT-trades-2020-01.csv"
    )
    zip_member_count: Literal[1] = 1
    zip_compressed_bytes: int = Field(gt=0)
    zip_uncompressed_bytes: int = Field(gt=0, le=10_000_000_000)
    column_count: Literal[6] = 6
    header_present: bool
    row_count: int = Field(gt=0)
    first_timestamp_ms: int = Field(gt=0)
    last_timestamp_ms: int = Field(gt=0)
    unique_minute_count: int = Field(gt=0, le=44_640)
    expected_minute_count: Literal[44_640] = RAW_PAYLOAD_EXPECTED_MINUTES
    minute_coverage_fraction: Decimal = Field(gt=0, le=1)
    maximum_event_gap_minutes: int = Field(ge=0)
    first_trade_id: int = Field(ge=0)
    last_trade_id: int = Field(ge=0)
    trade_id_non_increasing_count: int = Field(ge=0)
    trade_id_duplicate_count: int = Field(ge=0)
    forward_gap_count: int = Field(ge=0)
    skipped_trade_id_count: int = Field(ge=0)
    skipped_trade_id_fraction: Decimal = Field(ge=0, le=1)
    maximum_single_skipped_trade_id_count: int = Field(ge=0)
    timestamp_regression_count: int = Field(ge=0)
    buyer_maker_values_observed: tuple[bool, ...]
    payload_get_attempt_count: int = Field(ge=1, le=3)
    archive_pass: bool
    reason_codes: tuple[str, ...]
    parsed_numeric_fields: tuple[str, ...] = ("trade_id", "timestamp")
    excluded_numeric_fields: tuple[str, ...] = (
        "price",
        "quantity",
        "quote_quantity",
    )

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_evidence(self) -> RawTradesArchiveEvidence:
        if (
            self.zip_compressed_bytes > self.archive_bytes
            or self.zip_uncompressed_bytes > self.zip_compressed_bytes * 100
            or self.minute_coverage_fraction
            != Decimal(self.unique_minute_count) / Decimal(44_640)
        ):
            raise ValueError("Q1 raw payload ZIP or clock evidence changed")
        span = self.last_trade_id - self.first_trade_id + 1
        expected_fraction = (
            Decimal(self.skipped_trade_id_count) / Decimal(span)
            if span > 0
            else Decimal(0)
        )
        if self.skipped_trade_id_fraction != expected_fraction:
            raise ValueError("Q1 raw payload skipped-ID fraction changed")
        reasons = []
        if self.row_count < 100_000:
            reasons.append("ROW_COUNT_BELOW_100000")
        if self.minute_coverage_fraction < Decimal("0.99"):
            reasons.append("MINUTE_COVERAGE_BELOW_0_99")
        if self.maximum_event_gap_minutes > 15:
            reasons.append("EVENT_GAP_EXCEEDS_15_MINUTES")
        if self.trade_id_non_increasing_count:
            reasons.append("TRADE_ID_NOT_STRICTLY_INCREASING")
        if self.trade_id_duplicate_count:
            reasons.append("TRADE_ID_DUPLICATE")
        if self.skipped_trade_id_fraction > Decimal("0.001"):
            reasons.append("SKIPPED_TRADE_ID_FRACTION_EXCEEDS_0_001")
        if self.maximum_single_skipped_trade_id_count > 100:
            reasons.append("SINGLE_SKIPPED_TRADE_ID_COUNT_EXCEEDS_100")
        if self.timestamp_regression_count:
            reasons.append("TIMESTAMP_REGRESSION")
        if self.buyer_maker_values_observed != (False, True):
            reasons.append("BUYER_MAKER_DOMAIN_INCOMPLETE")
        expected_reasons = tuple(sorted(reasons))
        if (
            self.reason_codes != expected_reasons
            or self.archive_pass != (not reasons)
            or self.parsed_numeric_fields != ("trade_id", "timestamp")
            or self.excluded_numeric_fields
            != ("price", "quantity", "quote_quantity")
        ):
            raise ValueError("Q1 raw payload decision or field boundary changed")
        return self


class RawTradesPayloadPilotResult(BaseModel):
    schema_version: Literal[
        "aurex-q1-usdm-raw-trades-payload-pilot-result-v1"
    ] = "aurex-q1-usdm-raw-trades-payload-pilot-result-v1"
    result_id: Literal["q1-usdm-raw-trades-payload-pilot-result-v1"] = (
        "q1-usdm-raw-trades-payload-pilot-result-v1"
    )
    generated_at: datetime
    status: Literal["COMPLETE_STRUCTURAL_RAW_TRADES_PILOT_NO_OUTCOMES"] = (
        "COMPLETE_STRUCTURAL_RAW_TRADES_PILOT_NO_OUTCOMES"
    )
    protocol_file_sha256: str
    protocol_evidence_hash: str
    protocol_audit_file_sha256: str
    protocol_audit_evidence_hash: str
    runner_contract_hash: str
    qualified_spot_archive_sha256: Literal[
        "ea2f0aa850fb08b5c8124d2f8080c03689c30cdadf797363fc74b506b92a8d8b"
    ] = SPOT_ARCHIVE_SHA256
    qualified_spot_archive_reverified: Literal[True] = True
    raw_archive_evidence: RawTradesArchiveEvidence
    paired_clock_evidence: PeriodicFlowPairedClockEvidence
    unique_archive_urls_requested: Literal[1] = 1
    payload_get_attempt_count: int = Field(ge=1, le=3)
    total_new_archive_bytes: int = Field(gt=0, le=1_000_000_000)
    decision: Literal[
        "PERMIT_Q1_PAIRED_FULL_DEVELOPMENT_ACQUISITION_PROTOCOL",
        "STOP_Q1_USDM_RAW_TRADES_PAYLOAD_CAPABILITY_FAILED",
    ]
    next_authorization: Literal[
        "AUTHORIZE_Q1_PAIRED_FULL_DEVELOPMENT_ACQUISITION_PROTOCOL",
        "NONE_RAW_TRADES_PAYLOAD_PILOT_FAILED",
    ]
    authorizes_paired_full_development_acquisition_protocol: bool
    price_or_quantity_values_parsed: tuple[str, ...] = ()
    features_calculated: tuple[str, ...] = ()
    parameters_defined: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    validation_outcomes_accessed: Literal[False] = False
    holdout_accessed: Literal[False] = False
    strategy_candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    authorizes_pine_deployment: Literal[False] = False
    authorizes_paper_operation: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    real_net_profit_usd: Literal["0"] = "0"
    limitations: tuple[str, ...] = Field(min_length=9)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "protocol_audit_file_sha256",
        "protocol_audit_evidence_hash",
        "runner_contract_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> RawTradesPayloadPilotResult:
        passed = (
            self.raw_archive_evidence.archive_pass
            and self.paired_clock_evidence.paired_clock_pass
        )
        if (
            self.payload_get_attempt_count
            != self.raw_archive_evidence.payload_get_attempt_count
            or self.total_new_archive_bytes != self.raw_archive_evidence.archive_bytes
            or self.decision
            != (
                RAW_PAYLOAD_PASS_DECISION if passed else RAW_PAYLOAD_FAIL_DECISION
            )
            or self.next_authorization
            != (
                RAW_PAYLOAD_PASS_AUTHORIZATION
                if passed
                else RAW_PAYLOAD_FAIL_AUTHORIZATION
            )
            or self.authorizes_paired_full_development_acquisition_protocol
            != passed
            or self.limitations != tuple(sorted(set(self.limitations)))
            or self.price_or_quantity_values_parsed
            or self.features_calculated
            or self.parameters_defined
            or self.return_metrics_calculated
        ):
            raise ValueError("Q1 raw payload result decision or authority changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("Q1 raw payload result hash changed")
        return self


class RawTradesPayloadPilotAudit(BaseModel):
    schema_version: Literal[
        "aurex-q1-usdm-raw-trades-payload-pilot-audit-v1"
    ] = "aurex-q1-usdm-raw-trades-payload-pilot-audit-v1"
    audit_id: Literal["q1-usdm-raw-trades-payload-pilot-audit-v1"] = (
        "q1-usdm-raw-trades-payload-pilot-audit-v1"
    )
    audited_at: datetime
    result_file_sha256: str
    result_evidence_hash: str
    protocol_evidence_hash: str
    raw_archive_file_sha256: str
    spot_archive_file_sha256: str
    runner_contract_hash: str
    auditor_contract_hash: str
    structural_evidence_rebuilt: Literal[True] = True
    paired_clock_rebuilt: Literal[True] = True
    price_or_quantity_values_parsed: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    decision: Literal[
        "PERMIT_Q1_PAIRED_FULL_DEVELOPMENT_ACQUISITION_PROTOCOL",
        "STOP_Q1_USDM_RAW_TRADES_PAYLOAD_CAPABILITY_FAILED",
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
        "raw_archive_file_sha256",
        "spot_archive_file_sha256",
        "runner_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> RawTradesPayloadPilotAudit:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 raw payload audit hash changed")
        return self


def _build(model, hash_field: str, values: dict):
    provisional = model.model_construct(**values, **{hash_field: "0" * 64})
    payload = provisional.model_dump()
    payload[hash_field] = universe_evidence_hash(
        provisional.model_dump(exclude={hash_field})
    )
    return model.model_validate(payload)


def build_raw_payload_protocol(**values) -> RawTradesPayloadPilotProtocol:
    payload = {**values}
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(RawTradesPayloadPilotProtocol, "protocol_evidence_hash", payload)


def build_raw_payload_protocol_audit(**values) -> RawTradesPayloadProtocolAudit:
    return _build(RawTradesPayloadProtocolAudit, "audit_evidence_hash", values)


def build_raw_payload_result(**values) -> RawTradesPayloadPilotResult:
    raw = values["raw_archive_evidence"]
    clock = values["paired_clock_evidence"]
    passed = raw.archive_pass and clock.paired_clock_pass
    payload = {
        **values,
        "decision": (
            RAW_PAYLOAD_PASS_DECISION if passed else RAW_PAYLOAD_FAIL_DECISION
        ),
        "next_authorization": (
            RAW_PAYLOAD_PASS_AUTHORIZATION
            if passed
            else RAW_PAYLOAD_FAIL_AUTHORIZATION
        ),
        "authorizes_paired_full_development_acquisition_protocol": passed,
    }
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(RawTradesPayloadPilotResult, "result_evidence_hash", payload)


def build_raw_payload_audit(**values) -> RawTradesPayloadPilotAudit:
    return _build(RawTradesPayloadPilotAudit, "audit_evidence_hash", values)


def audit_raw_payload_protocol(protocol: RawTradesPayloadPilotProtocol) -> bool:
    return protocol.protocol_evidence_hash == universe_evidence_hash(
        protocol.model_dump(exclude={"protocol_evidence_hash"})
    )


def audit_raw_payload_protocol_audit(audit: RawTradesPayloadProtocolAudit) -> bool:
    return audit.audit_evidence_hash == universe_evidence_hash(
        audit.model_dump(exclude={"audit_evidence_hash"})
    )


def audit_raw_payload_result(result: RawTradesPayloadPilotResult) -> bool:
    return result.result_evidence_hash == universe_evidence_hash(
        result.model_dump(exclude={"result_evidence_hash"})
    )


def audit_raw_payload_audit(audit: RawTradesPayloadPilotAudit) -> bool:
    return audit.audit_evidence_hash == universe_evidence_hash(
        audit.model_dump(exclude={"audit_evidence_hash"})
    )
