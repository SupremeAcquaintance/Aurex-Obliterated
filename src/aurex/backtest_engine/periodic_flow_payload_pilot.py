from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.periodic_flow_metadata_census import (
    SPOT_AGGTRADE_COLUMNS,
    USD_M_AGGTRADE_COLUMNS,
    archive_url,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

Q1_PAYLOAD_PROTOCOL_SCHEMA_VERSION = (
    "aurex-q1-periodic-flow-paired-payload-pilot-protocol-v1"
)
Q1_PAYLOAD_RESULT_SCHEMA_VERSION = (
    "aurex-q1-periodic-flow-paired-payload-pilot-result-v1"
)
Q1_PAYLOAD_AUDIT_SCHEMA_VERSION = (
    "aurex-q1-periodic-flow-paired-payload-pilot-audit-v1"
)
Q1_PAYLOAD_PILOT_MONTH = "2020-01"
Q1_PAYLOAD_EXPECTED_MINUTES = 44_640
Q1_PAYLOAD_PRODUCTS = ("SPOT", "USD_M_PERPETUAL")
Q1_PAYLOAD_PASS_DECISION = (
    "PERMIT_Q1_FULL_DEVELOPMENT_PAYLOAD_ACQUISITION_PROTOCOL"
)
Q1_PAYLOAD_FAIL_DECISION = "STOP_Q1_PAIRED_PAYLOAD_CAPABILITY_FAILED"
Q1_PAYLOAD_PASS_AUTHORIZATION = (
    "AUTHORIZE_Q1_FULL_DEVELOPMENT_PAYLOAD_ACQUISITION_PROTOCOL"
)
Q1_PAYLOAD_FAIL_AUTHORIZATION = "NONE_PAYLOAD_PILOT_FAILED"


class PeriodicFlowPayloadTarget(BaseModel):
    product: Literal["SPOT", "USD_M_PERPETUAL"]
    symbol: Literal["BTCUSDT"] = "BTCUSDT"
    month: Literal["2020-01"] = Q1_PAYLOAD_PILOT_MONTH
    partition_role: Literal["DEVELOPMENT"] = "DEVELOPMENT"
    expected_timestamp_unit: Literal["MILLISECONDS"] = "MILLISECONDS"
    archive_url: str
    published_archive_sha256: str
    expected_columns: tuple[str, ...]
    expected_column_count: Literal[7, 8]

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("published_archive_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_target(self) -> PeriodicFlowPayloadTarget:
        columns = (
            SPOT_AGGTRADE_COLUMNS
            if self.product == "SPOT"
            else USD_M_AGGTRADE_COLUMNS
        )
        if (
            self.archive_url != archive_url(self.product, self.month)
            or self.expected_columns != columns
            or self.expected_column_count != len(columns)
        ):
            raise ValueError("Q1 payload target changed")
        return self


class PeriodicFlowPayloadPilotProtocol(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-paired-payload-pilot-protocol-v1"
    ] = Q1_PAYLOAD_PROTOCOL_SCHEMA_VERSION
    protocol_id: Literal["q1-periodic-flow-paired-payload-pilot-v1"] = (
        "q1-periodic-flow-paired-payload-pilot-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_PRE_PAIRED_PAYLOAD_ACCESS"] = (
        "FROZEN_PRE_PAIRED_PAYLOAD_ACCESS"
    )
    census_contract_file_sha256: str
    census_contract_evidence_hash: str
    census_result_file_sha256: str
    census_result_evidence_hash: str
    census_audit_file_sha256: str
    census_audit_evidence_hash: str
    builder_contract_hash: str
    targets: tuple[PeriodicFlowPayloadTarget, ...] = Field(
        min_length=2,
        max_length=2,
    )
    target_manifest_hash: str
    permitted_methods: tuple[Literal["GET"], ...] = ("GET",)
    maximum_unique_archive_urls: Literal[2] = 2
    maximum_attempts_per_archive: Literal[3] = 3
    maximum_payload_get_attempts: Literal[6] = 6
    request_timeout_seconds: Literal[120] = 120
    retry_backoff_seconds: tuple[Literal[1], Literal[3]] = (1, 3)
    redirects_permitted: Literal[False] = False
    range_requests_permitted: Literal[False] = False
    maximum_archive_bytes_each: Literal[1_000_000_000] = 1_000_000_000
    maximum_total_archive_bytes: Literal[2_000_000_000] = 2_000_000_000
    maximum_member_uncompressed_bytes_each: Literal[10_000_000_000] = (
        10_000_000_000
    )
    maximum_total_member_uncompressed_bytes: Literal[20_000_000_000] = (
        20_000_000_000
    )
    maximum_zip_expansion_ratio: Literal[100] = 100
    minimum_free_disk_bytes_after_download: Literal[5_000_000_000] = (
        5_000_000_000
    )
    minimum_rows_each: Literal[100_000] = 100_000
    minimum_minute_coverage_fraction: Literal["0.99"] = "0.99"
    minimum_paired_minute_coverage_fraction: Literal["0.99"] = "0.99"
    maximum_event_gap_minutes: Literal[15] = 15
    maximum_aggregate_trade_id_gap_count: Literal[0] = 0
    maximum_raw_trade_id_gap_count: Literal[0] = 0
    expected_month_minute_count: Literal[44_640] = Q1_PAYLOAD_EXPECTED_MINUTES
    header_policy: Literal["EXACT_DOCUMENTED_OR_HEADERLESS"] = (
        "EXACT_DOCUMENTED_OR_HEADERLESS"
    )
    excluded_numeric_columns: tuple[Literal["price"], Literal["quantity"]] = (
        "price",
        "quantity",
    )
    price_or_quantity_parsing_permitted: Literal[False] = False
    feature_calculation_permitted: Literal[False] = False
    parameter_definition_permitted: Literal[False] = False
    return_calculation_permitted: Literal[False] = False
    validation_outcomes_permitted: Literal[False] = False
    holdout_access_permitted: Literal[False] = False
    strategy_execution_permitted: Literal[False] = False
    candidate_creation_permitted: Literal[False] = False
    pine_deployment_permitted: Literal[False] = False
    paper_operation_permitted: Literal[False] = False
    testnet_strategy_orders_permitted: Literal[False] = False
    production_permitted: Literal[False] = False
    live_permitted: Literal[False] = False
    limitations: tuple[str, ...] = Field(min_length=8)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "census_contract_file_sha256",
        "census_contract_evidence_hash",
        "census_result_file_sha256",
        "census_result_evidence_hash",
        "census_audit_file_sha256",
        "census_audit_evidence_hash",
        "builder_contract_hash",
        "target_manifest_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> PeriodicFlowPayloadPilotProtocol:
        if (
            tuple(item.product for item in self.targets) != Q1_PAYLOAD_PRODUCTS
            or len({item.archive_url for item in self.targets}) != 2
            or self.retry_backoff_seconds != (1, 3)
            or self.limitations != tuple(sorted(set(self.limitations)))
        ):
            raise ValueError("Q1 paired payload protocol scope changed")
        manifest = universe_evidence_hash(
            {"targets": [item.model_dump() for item in self.targets]}
        )
        if self.target_manifest_hash != manifest:
            raise ValueError("Q1 paired payload target manifest changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("Q1 paired payload protocol hash changed")
        return self


class PeriodicFlowArchiveEvidence(BaseModel):
    product: Literal["SPOT", "USD_M_PERPETUAL"]
    archive_url: str
    local_path: str
    archive_bytes: int = Field(gt=0, le=1_000_000_000)
    archive_sha256: str
    published_archive_sha256: str
    checksum_verified: Literal[True] = True
    csv_member_name: Literal["BTCUSDT-aggTrades-2020-01.csv"] = (
        "BTCUSDT-aggTrades-2020-01.csv"
    )
    zip_member_count: Literal[1] = 1
    zip_compressed_bytes: int = Field(gt=0)
    zip_uncompressed_bytes: int = Field(gt=0, le=10_000_000_000)
    column_count: Literal[7, 8]
    header_present: bool
    row_count: int = Field(gt=0)
    first_timestamp_ms: int = Field(gt=0)
    last_timestamp_ms: int = Field(gt=0)
    unique_minute_count: int = Field(gt=0, le=44_640)
    expected_minute_count: Literal[44_640] = Q1_PAYLOAD_EXPECTED_MINUTES
    minute_coverage_fraction: Decimal = Field(gt=0, le=1)
    maximum_event_gap_minutes: int = Field(ge=0)
    first_aggregate_trade_id: int = Field(ge=0)
    last_aggregate_trade_id: int = Field(ge=0)
    aggregate_trade_id_gap_count: int = Field(ge=0)
    aggregate_trade_id_non_increasing_count: int = Field(ge=0)
    raw_trade_span_invalid_count: int = Field(ge=0)
    raw_trade_id_gap_count: int = Field(ge=0)
    timestamp_regression_count: int = Field(ge=0)
    buyer_maker_values_observed: tuple[bool, ...]
    best_price_match_values_observed: tuple[bool, ...]
    payload_get_attempt_count: int = Field(ge=0, le=3)
    archive_pass: bool
    reason_codes: tuple[str, ...]
    parsed_numeric_fields: tuple[str, ...] = (
        "aggregate_trade_id",
        "first_trade_id",
        "last_trade_id",
        "timestamp",
    )
    excluded_numeric_fields: tuple[str, ...] = ("price", "quantity")

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("archive_sha256", "published_archive_sha256")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_evidence(self) -> PeriodicFlowArchiveEvidence:
        target_columns = (
            SPOT_AGGTRADE_COLUMNS
            if self.product == "SPOT"
            else USD_M_AGGTRADE_COLUMNS
        )
        expected_path = (
            "source_snapshots/q1_periodic_flow_payload_pilot_v1/"
            f"{self.product}/BTCUSDT-aggTrades-2020-01.zip"
        )
        if (
            self.archive_url != archive_url(self.product, Q1_PAYLOAD_PILOT_MONTH)
            or self.local_path != expected_path
            or self.archive_sha256 != self.published_archive_sha256
            or self.column_count != len(target_columns)
            or self.zip_compressed_bytes > self.archive_bytes
            or self.zip_uncompressed_bytes
            > self.zip_compressed_bytes * 100
        ):
            raise ValueError("Q1 archive identity or ZIP evidence changed")
        if self.minute_coverage_fraction != Decimal(
            self.unique_minute_count
        ) / Decimal(Q1_PAYLOAD_EXPECTED_MINUTES):
            raise ValueError("Q1 archive minute coverage changed")
        if self.product == "SPOT":
            if any(
                not isinstance(value, bool)
                for value in self.best_price_match_values_observed
            ):
                raise ValueError("Q1 Spot best-price-match domain changed")
        elif self.best_price_match_values_observed:
            raise ValueError("Q1 USD-M evidence cannot contain Spot-only flags")
        reasons = []
        if self.row_count < 100_000:
            reasons.append("ROW_COUNT_BELOW_100000")
        if self.minute_coverage_fraction < Decimal("0.99"):
            reasons.append("MINUTE_COVERAGE_BELOW_0_99")
        if self.maximum_event_gap_minutes > 15:
            reasons.append("EVENT_GAP_EXCEEDS_15_MINUTES")
        if self.aggregate_trade_id_gap_count:
            reasons.append("AGGREGATE_TRADE_ID_GAP")
        if self.aggregate_trade_id_non_increasing_count:
            reasons.append("AGGREGATE_TRADE_ID_NOT_STRICTLY_INCREASING")
        if self.raw_trade_span_invalid_count:
            reasons.append("RAW_TRADE_SPAN_INVALID")
        if self.raw_trade_id_gap_count:
            reasons.append("RAW_TRADE_ID_GAP")
        if self.timestamp_regression_count:
            reasons.append("TIMESTAMP_REGRESSION")
        if self.buyer_maker_values_observed != (False, True):
            reasons.append("BUYER_MAKER_DOMAIN_INCOMPLETE")
        if self.product == "SPOT" and not self.best_price_match_values_observed:
            reasons.append("BEST_PRICE_MATCH_DOMAIN_EMPTY")
        expected_reasons = tuple(sorted(reasons))
        if self.reason_codes != expected_reasons or self.archive_pass != (
            not reasons
        ):
            raise ValueError("Q1 archive decision changed")
        if (
            self.parsed_numeric_fields
            != (
                "aggregate_trade_id",
                "first_trade_id",
                "last_trade_id",
                "timestamp",
            )
            or self.excluded_numeric_fields != ("price", "quantity")
        ):
            raise ValueError("Q1 no-price/no-quantity boundary changed")
        return self


class PeriodicFlowPairedClockEvidence(BaseModel):
    spot_unique_minute_count: int = Field(gt=0, le=44_640)
    usd_m_unique_minute_count: int = Field(gt=0, le=44_640)
    paired_minute_count: int = Field(gt=0, le=44_640)
    union_minute_count: int = Field(gt=0, le=44_640)
    expected_minute_count: Literal[44_640] = Q1_PAYLOAD_EXPECTED_MINUTES
    paired_month_coverage_fraction: Decimal = Field(gt=0, le=1)
    paired_union_overlap_fraction: Decimal = Field(gt=0, le=1)
    spot_only_minute_count: int = Field(ge=0, le=44_640)
    usd_m_only_minute_count: int = Field(ge=0, le=44_640)
    paired_clock_pass: bool
    reason_codes: tuple[str, ...]

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_clock(self) -> PeriodicFlowPairedClockEvidence:
        if (
            self.paired_month_coverage_fraction
            != Decimal(self.paired_minute_count) / Decimal(44_640)
            or self.paired_union_overlap_fraction
            != Decimal(self.paired_minute_count) / Decimal(self.union_minute_count)
            or self.spot_only_minute_count
            != self.spot_unique_minute_count - self.paired_minute_count
            or self.usd_m_only_minute_count
            != self.usd_m_unique_minute_count - self.paired_minute_count
        ):
            raise ValueError("Q1 paired clock arithmetic changed")
        reasons = []
        if self.paired_month_coverage_fraction < Decimal("0.99"):
            reasons.append("PAIRED_MONTH_COVERAGE_BELOW_0_99")
        expected = tuple(sorted(reasons))
        if self.reason_codes != expected or self.paired_clock_pass != (
            not reasons
        ):
            raise ValueError("Q1 paired clock decision changed")
        return self


class PeriodicFlowPayloadPilotResult(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-paired-payload-pilot-result-v1"
    ] = Q1_PAYLOAD_RESULT_SCHEMA_VERSION
    result_id: Literal["q1-periodic-flow-paired-payload-pilot-result-v1"] = (
        "q1-periodic-flow-paired-payload-pilot-result-v1"
    )
    generated_at: datetime
    status: Literal["COMPLETE_STRUCTURAL_PAIRED_PAYLOAD_PILOT_NO_OUTCOMES"] = (
        "COMPLETE_STRUCTURAL_PAIRED_PAYLOAD_PILOT_NO_OUTCOMES"
    )
    protocol_file_sha256: str
    protocol_evidence_hash: str
    runner_contract_hash: str
    archive_evidence: tuple[PeriodicFlowArchiveEvidence, ...] = Field(
        min_length=2,
        max_length=2,
    )
    paired_clock_evidence: PeriodicFlowPairedClockEvidence
    unique_archive_urls_requested: Literal[2] = 2
    payload_get_attempt_count: int = Field(ge=2, le=6)
    total_archive_bytes: int = Field(gt=0, le=2_000_000_000)
    total_member_uncompressed_bytes: int = Field(gt=0, le=20_000_000_000)
    decision: Literal[
        "PERMIT_Q1_FULL_DEVELOPMENT_PAYLOAD_ACQUISITION_PROTOCOL",
        "STOP_Q1_PAIRED_PAYLOAD_CAPABILITY_FAILED",
    ]
    next_authorization: Literal[
        "AUTHORIZE_Q1_FULL_DEVELOPMENT_PAYLOAD_ACQUISITION_PROTOCOL",
        "NONE_PAYLOAD_PILOT_FAILED",
    ]
    authorizes_separate_full_development_acquisition_protocol: bool
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
    limitations: tuple[str, ...] = Field(min_length=8)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "runner_contract_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> PeriodicFlowPayloadPilotResult:
        if tuple(item.product for item in self.archive_evidence) != Q1_PAYLOAD_PRODUCTS:
            raise ValueError("Q1 result archive order changed")
        if self.payload_get_attempt_count != sum(
            item.payload_get_attempt_count for item in self.archive_evidence
        ):
            raise ValueError("Q1 payload request count changed")
        if self.total_archive_bytes != sum(
            item.archive_bytes for item in self.archive_evidence
        ) or self.total_member_uncompressed_bytes != sum(
            item.zip_uncompressed_bytes for item in self.archive_evidence
        ):
            raise ValueError("Q1 payload resource totals changed")
        passed = all(
            item.archive_pass for item in self.archive_evidence
        ) and self.paired_clock_evidence.paired_clock_pass
        expected_decision = (
            Q1_PAYLOAD_PASS_DECISION if passed else Q1_PAYLOAD_FAIL_DECISION
        )
        expected_authorization = (
            Q1_PAYLOAD_PASS_AUTHORIZATION
            if passed
            else Q1_PAYLOAD_FAIL_AUTHORIZATION
        )
        if (
            self.decision != expected_decision
            or self.next_authorization != expected_authorization
            or self.authorizes_separate_full_development_acquisition_protocol
            != passed
            or self.limitations != tuple(sorted(set(self.limitations)))
            or self.price_or_quantity_values_parsed
            or self.features_calculated
            or self.parameters_defined
            or self.return_metrics_calculated
        ):
            raise ValueError("Q1 payload result decision or authority changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("Q1 payload result hash changed")
        return self


class PeriodicFlowPayloadPilotAudit(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-paired-payload-pilot-audit-v1"
    ] = Q1_PAYLOAD_AUDIT_SCHEMA_VERSION
    audit_id: Literal["q1-periodic-flow-paired-payload-pilot-audit-v1"] = (
        "q1-periodic-flow-paired-payload-pilot-audit-v1"
    )
    audited_at: datetime
    result_path: Literal[
        "data/evidence/q1_periodic_flow_payload_pilot_result_v1.json"
    ] = "data/evidence/q1_periodic_flow_payload_pilot_result_v1.json"
    result_file_sha256: str
    result_evidence_hash: str
    protocol_evidence_hash: str
    archive_file_sha256: dict[str, str]
    archive_file_bytes: dict[str, int]
    archive_count: Literal[2] = 2
    structural_evidence_rebuilt: Literal[True] = True
    paired_clock_rebuilt: Literal[True] = True
    price_or_quantity_values_parsed: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    decision: Literal[
        "PERMIT_Q1_FULL_DEVELOPMENT_PAYLOAD_ACQUISITION_PROTOCOL",
        "STOP_Q1_PAIRED_PAYLOAD_CAPABILITY_FAILED",
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

    @model_validator(mode="after")
    def validate_audit(self) -> PeriodicFlowPayloadPilotAudit:
        expected_keys = set(Q1_PAYLOAD_PRODUCTS)
        if (
            set(self.archive_file_sha256) != expected_keys
            or set(self.archive_file_bytes) != expected_keys
            or self.price_or_quantity_values_parsed
            or self.return_metrics_calculated
        ):
            raise ValueError("Q1 payload audit scope changed")
        for digest in self.archive_file_sha256.values():
            normalize_sha256(digest)
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 payload audit hash changed")
        return self


def build_periodic_flow_payload_protocol(**values) -> PeriodicFlowPayloadPilotProtocol:
    payload = {
        "schema_version": Q1_PAYLOAD_PROTOCOL_SCHEMA_VERSION,
        "protocol_id": "q1-periodic-flow-paired-payload-pilot-v1",
        "status": "FROZEN_PRE_PAIRED_PAYLOAD_ACCESS",
        **values,
    }
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    provisional = PeriodicFlowPayloadPilotProtocol.model_construct(
        **payload,
        protocol_evidence_hash="0" * 64,
    )
    payload = provisional.model_dump()
    payload["protocol_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"protocol_evidence_hash"})
    )
    return PeriodicFlowPayloadPilotProtocol.model_validate(payload)


def build_periodic_flow_payload_result(**values) -> PeriodicFlowPayloadPilotResult:
    archive_evidence = tuple(values["archive_evidence"])
    paired = values["paired_clock_evidence"]
    passed = all(item.archive_pass for item in archive_evidence) and paired.paired_clock_pass
    payload = {
        "schema_version": Q1_PAYLOAD_RESULT_SCHEMA_VERSION,
        "result_id": "q1-periodic-flow-paired-payload-pilot-result-v1",
        "status": "COMPLETE_STRUCTURAL_PAIRED_PAYLOAD_PILOT_NO_OUTCOMES",
        **values,
        "archive_evidence": archive_evidence,
        "decision": Q1_PAYLOAD_PASS_DECISION if passed else Q1_PAYLOAD_FAIL_DECISION,
        "next_authorization": (
            Q1_PAYLOAD_PASS_AUTHORIZATION if passed else Q1_PAYLOAD_FAIL_AUTHORIZATION
        ),
        "authorizes_separate_full_development_acquisition_protocol": passed,
    }
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    provisional = PeriodicFlowPayloadPilotResult.model_construct(
        **payload,
        result_evidence_hash="0" * 64,
    )
    payload = provisional.model_dump()
    payload["result_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"result_evidence_hash"})
    )
    return PeriodicFlowPayloadPilotResult.model_validate(payload)


def build_periodic_flow_payload_audit(**values) -> PeriodicFlowPayloadPilotAudit:
    payload = {
        "schema_version": Q1_PAYLOAD_AUDIT_SCHEMA_VERSION,
        "audit_id": "q1-periodic-flow-paired-payload-pilot-audit-v1",
        **values,
    }
    provisional = PeriodicFlowPayloadPilotAudit.model_construct(
        **payload,
        audit_evidence_hash="0" * 64,
    )
    payload = provisional.model_dump()
    payload["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"audit_evidence_hash"})
    )
    return PeriodicFlowPayloadPilotAudit.model_validate(payload)


def audit_periodic_flow_payload_protocol(
    protocol: PeriodicFlowPayloadPilotProtocol,
) -> bool:
    return protocol.protocol_evidence_hash == universe_evidence_hash(
        protocol.model_dump(exclude={"protocol_evidence_hash"})
    )


def audit_periodic_flow_payload_result(
    result: PeriodicFlowPayloadPilotResult,
) -> bool:
    return result.result_evidence_hash == universe_evidence_hash(
        result.model_dump(exclude={"result_evidence_hash"})
    )


def audit_periodic_flow_payload_audit(
    audit: PeriodicFlowPayloadPilotAudit,
) -> bool:
    return audit.audit_evidence_hash == universe_evidence_hash(
        audit.model_dump(exclude={"audit_evidence_hash"})
    )
