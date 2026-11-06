from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

Q1_GAP_PROTOCOL_SCHEMA_VERSION = (
    "aurex-q1-periodic-flow-usdm-gap-remediation-protocol-v1"
)
Q1_GAP_RESULT_SCHEMA_VERSION = (
    "aurex-q1-periodic-flow-usdm-gap-remediation-result-v1"
)
Q1_GAP_AUDIT_SCHEMA_VERSION = (
    "aurex-q1-periodic-flow-usdm-gap-remediation-audit-v1"
)
Q1_GAP_PASS_DECISION = (
    "PERMIT_Q1_FULL_DEVELOPMENT_PAYLOAD_ACQUISITION_PROTOCOL"
)
Q1_GAP_FAIL_DECISION = "STOP_Q1_USDM_SOURCE_SEMANTICS_UNRESOLVED"
Q1_GAP_PASS_AUTHORIZATION = (
    "AUTHORIZE_Q1_FULL_DEVELOPMENT_PAYLOAD_ACQUISITION_PROTOCOL"
)
Q1_GAP_FAIL_AUTHORIZATION = "NONE_USDM_GAP_REMEDIATION_FAILED"
Q1_GAP_OFFICIAL_ARCHIVE_REFERENCE = (
    "https://github.com/binance/binance-public-data/blob/master/README.md"
)
Q1_GAP_OFFICIAL_API_REFERENCE = (
    "https://developers.binance.com/en/docs/catalog/"
    "core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/"
    "market-data#compressed-aggregate-trades-list"
)
Q1_GAP_DOCUMENTATION_CLAIMS = (
    "The public USD-M aggTrades archive mirrors the /fapi/v1/aggTrades endpoint.",
    "The endpoint returns compressed aggregate market trades.",
    "Insurance-fund trades and ADL trades are not aggregated or returned.",
    "The archive exposes aggregate ID, first raw-trade ID, last raw-trade ID, "
    "timestamp, and maker side.",
)


class PeriodicFlowGapRecord(BaseModel):
    preceding_aggregate_trade_id: int = Field(ge=0)
    current_aggregate_trade_id: int = Field(ge=0)
    preceding_last_raw_trade_id: int = Field(ge=0)
    current_first_raw_trade_id: int = Field(ge=0)
    skipped_raw_trade_id_count: int = Field(gt=0)
    current_timestamp_ms: int = Field(gt=0)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_gap(self) -> PeriodicFlowGapRecord:
        if (
            self.current_aggregate_trade_id
            != self.preceding_aggregate_trade_id + 1
            or self.current_first_raw_trade_id
            <= self.preceding_last_raw_trade_id + 1
            or self.skipped_raw_trade_id_count
            != self.current_first_raw_trade_id
            - self.preceding_last_raw_trade_id
            - 1
        ):
            raise ValueError("Q1 USD-M gap record arithmetic changed")
        return self


class PeriodicFlowGapRemediationProtocol(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-usdm-gap-remediation-protocol-v1"
    ] = Q1_GAP_PROTOCOL_SCHEMA_VERSION
    protocol_id: Literal["q1-periodic-flow-usdm-gap-remediation-v1"] = (
        "q1-periodic-flow-usdm-gap-remediation-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_AFTER_PILOT_STOP_BEFORE_GAP_MAGNITUDE_SCAN"] = (
        "FROZEN_AFTER_PILOT_STOP_BEFORE_GAP_MAGNITUDE_SCAN"
    )
    parent_protocol_file_sha256: str
    parent_protocol_evidence_hash: str
    parent_result_file_sha256: str
    parent_result_evidence_hash: str
    parent_audit_file_sha256: str
    parent_audit_evidence_hash: str
    builder_contract_hash: str
    target_product: Literal["USD_M_PERPETUAL"] = "USD_M_PERPETUAL"
    target_month: Literal["2020-01"] = "2020-01"
    target_archive_path: Literal[
        "data/evidence/source_snapshots/q1_periodic_flow_payload_pilot_v1/"
        "USD_M_PERPETUAL/BTCUSDT-aggTrades-2020-01.zip"
    ] = (
        "data/evidence/source_snapshots/q1_periodic_flow_payload_pilot_v1/"
        "USD_M_PERPETUAL/BTCUSDT-aggTrades-2020-01.zip"
    )
    target_archive_sha256: str
    official_archive_reference: Literal[
        "https://github.com/binance/binance-public-data/blob/master/README.md"
    ] = Q1_GAP_OFFICIAL_ARCHIVE_REFERENCE
    official_api_reference: Literal[
        "https://developers.binance.com/en/docs/catalog/"
        "core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/"
        "market-data#compressed-aggregate-trades-list"
    ] = Q1_GAP_OFFICIAL_API_REFERENCE
    documentation_claims: tuple[str, ...] = Q1_GAP_DOCUMENTATION_CLAIMS
    maximum_gap_event_count: Literal[10_000] = 10_000
    maximum_single_gap_skipped_raw_ids: Literal[100_000] = 100_000
    maximum_skipped_raw_id_fraction: Literal["0.01"] = "0.01"
    required_aggregate_trade_id_gap_count: Literal[0] = 0
    required_aggregate_trade_id_non_increasing_count: Literal[0] = 0
    required_raw_trade_range_overlap_count: Literal[0] = 0
    required_raw_trade_span_invalid_count: Literal[0] = 0
    required_timestamp_regression_count: Literal[0] = 0
    minimum_minute_coverage_fraction: Literal["0.99"] = "0.99"
    permitted_numeric_fields: tuple[str, ...] = (
        "aggregate_trade_id",
        "first_trade_id",
        "last_trade_id",
        "timestamp",
    )
    excluded_numeric_fields: tuple[str, ...] = ("price", "quantity")
    network_access_permitted: Literal[False] = False
    price_or_quantity_parsing_permitted: Literal[False] = False
    feature_calculation_permitted: Literal[False] = False
    parameter_definition_permitted: Literal[False] = False
    return_calculation_permitted: Literal[False] = False
    validation_outcomes_permitted: Literal[False] = False
    holdout_access_permitted: Literal[False] = False
    candidate_creation_permitted: Literal[False] = False
    strategy_execution_permitted: Literal[False] = False
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
        "parent_protocol_file_sha256",
        "parent_protocol_evidence_hash",
        "parent_result_file_sha256",
        "parent_result_evidence_hash",
        "parent_audit_file_sha256",
        "parent_audit_evidence_hash",
        "builder_contract_hash",
        "target_archive_sha256",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> PeriodicFlowGapRemediationProtocol:
        if (
            self.documentation_claims != Q1_GAP_DOCUMENTATION_CLAIMS
            or self.limitations != tuple(sorted(set(self.limitations)))
            or self.permitted_numeric_fields
            != (
                "aggregate_trade_id",
                "first_trade_id",
                "last_trade_id",
                "timestamp",
            )
            or self.excluded_numeric_fields != ("price", "quantity")
        ):
            raise ValueError("Q1 USD-M gap remediation scope changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("Q1 USD-M gap remediation protocol hash changed")
        return self


class PeriodicFlowGapRemediationResult(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-usdm-gap-remediation-result-v1"
    ] = Q1_GAP_RESULT_SCHEMA_VERSION
    result_id: Literal["q1-periodic-flow-usdm-gap-remediation-result-v1"] = (
        "q1-periodic-flow-usdm-gap-remediation-result-v1"
    )
    generated_at: datetime
    status: Literal["COMPLETE_LOCAL_STRUCTURAL_GAP_DIAGNOSIS_NO_OUTCOMES"] = (
        "COMPLETE_LOCAL_STRUCTURAL_GAP_DIAGNOSIS_NO_OUTCOMES"
    )
    protocol_file_sha256: str
    protocol_evidence_hash: str
    runner_contract_hash: str
    archive_sha256: str
    row_count: int = Field(gt=0)
    first_aggregate_trade_id: int = Field(ge=0)
    last_aggregate_trade_id: int = Field(ge=0)
    aggregate_trade_id_gap_count: int = Field(ge=0)
    aggregate_trade_id_non_increasing_count: int = Field(ge=0)
    first_raw_trade_id: int = Field(ge=0)
    last_raw_trade_id: int = Field(ge=0)
    raw_trade_span_invalid_count: int = Field(ge=0)
    raw_trade_range_overlap_count: int = Field(ge=0)
    gap_records: tuple[PeriodicFlowGapRecord, ...]
    gap_manifest_hash: str
    gap_event_count: int = Field(ge=0)
    total_skipped_raw_trade_ids: int = Field(ge=0)
    maximum_single_gap_skipped_raw_ids: int = Field(ge=0)
    raw_trade_id_span: int = Field(gt=0)
    skipped_raw_trade_id_fraction: Decimal = Field(ge=0, le=1)
    gap_size_buckets: dict[str, int]
    first_timestamp_ms: int = Field(gt=0)
    last_timestamp_ms: int = Field(gt=0)
    timestamp_regression_count: int = Field(ge=0)
    unique_minute_count: int = Field(gt=0, le=44_640)
    minute_coverage_fraction: Decimal = Field(gt=0, le=1)
    source_semantic_interpretation: Literal[
        "FORWARD_RAW_ID_GAPS_COMPATIBLE_WITH_DOCUMENTED_EXCLUDED_NON_MARKET_TRADES"
    ] = (
        "FORWARD_RAW_ID_GAPS_COMPATIBLE_WITH_DOCUMENTED_EXCLUDED_NON_MARKET_TRADES"
    )
    interpretation_is_inference_not_trade_classification: Literal[True] = True
    decision: Literal[
        "PERMIT_Q1_FULL_DEVELOPMENT_PAYLOAD_ACQUISITION_PROTOCOL",
        "STOP_Q1_USDM_SOURCE_SEMANTICS_UNRESOLVED",
    ]
    next_authorization: Literal[
        "AUTHORIZE_Q1_FULL_DEVELOPMENT_PAYLOAD_ACQUISITION_PROTOCOL",
        "NONE_USDM_GAP_REMEDIATION_FAILED",
    ]
    authorizes_separate_full_development_acquisition_protocol: bool
    network_requests_made: Literal[0] = 0
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
        "archive_sha256",
        "gap_manifest_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> PeriodicFlowGapRemediationResult:
        if (
            self.gap_event_count != len(self.gap_records)
            or self.gap_manifest_hash
            != universe_evidence_hash(
                {"gaps": [item.model_dump() for item in self.gap_records]}
            )
            or self.total_skipped_raw_trade_ids
            != sum(item.skipped_raw_trade_id_count for item in self.gap_records)
            or self.maximum_single_gap_skipped_raw_ids
            != max(
                (item.skipped_raw_trade_id_count for item in self.gap_records),
                default=0,
            )
            or self.raw_trade_id_span != self.last_raw_trade_id - self.first_raw_trade_id + 1
            or self.skipped_raw_trade_id_fraction
            != Decimal(self.total_skipped_raw_trade_ids)
            / Decimal(self.raw_trade_id_span)
            or sum(self.gap_size_buckets.values()) != self.gap_event_count
            or self.minute_coverage_fraction
            != Decimal(self.unique_minute_count) / Decimal(44_640)
        ):
            raise ValueError("Q1 USD-M gap diagnostics do not reconcile")
        passed = (
            self.aggregate_trade_id_gap_count == 0
            and self.aggregate_trade_id_non_increasing_count == 0
            and self.raw_trade_span_invalid_count == 0
            and self.raw_trade_range_overlap_count == 0
            and self.gap_event_count <= 10_000
            and self.maximum_single_gap_skipped_raw_ids <= 100_000
            and self.skipped_raw_trade_id_fraction <= Decimal("0.01")
            and self.timestamp_regression_count == 0
            and self.minute_coverage_fraction >= Decimal("0.99")
        )
        if (
            self.decision
            != (Q1_GAP_PASS_DECISION if passed else Q1_GAP_FAIL_DECISION)
            or self.next_authorization
            != (
                Q1_GAP_PASS_AUTHORIZATION
                if passed
                else Q1_GAP_FAIL_AUTHORIZATION
            )
            or self.authorizes_separate_full_development_acquisition_protocol
            != passed
            or self.limitations != tuple(sorted(set(self.limitations)))
            or self.price_or_quantity_values_parsed
            or self.features_calculated
            or self.parameters_defined
            or self.return_metrics_calculated
        ):
            raise ValueError("Q1 USD-M remediation decision or authority changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("Q1 USD-M remediation result hash changed")
        return self


class PeriodicFlowGapRemediationAudit(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-usdm-gap-remediation-audit-v1"
    ] = Q1_GAP_AUDIT_SCHEMA_VERSION
    audit_id: Literal["q1-periodic-flow-usdm-gap-remediation-audit-v1"] = (
        "q1-periodic-flow-usdm-gap-remediation-audit-v1"
    )
    audited_at: datetime
    result_file_sha256: str
    result_evidence_hash: str
    protocol_evidence_hash: str
    archive_sha256: str
    gap_manifest_hash: str
    gap_event_count: int = Field(ge=0)
    total_skipped_raw_trade_ids: int = Field(ge=0)
    reconstructed_exactly: Literal[True] = True
    network_requests_made: Literal[0] = 0
    price_or_quantity_values_parsed: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    decision: Literal[
        "PERMIT_Q1_FULL_DEVELOPMENT_PAYLOAD_ACQUISITION_PROTOCOL",
        "STOP_Q1_USDM_SOURCE_SEMANTICS_UNRESOLVED",
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
        "archive_sha256",
        "gap_manifest_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> PeriodicFlowGapRemediationAudit:
        if self.price_or_quantity_values_parsed or self.return_metrics_calculated:
            raise ValueError("Q1 USD-M remediation audit crossed outcome boundary")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 USD-M remediation audit hash changed")
        return self


def _build(model, hash_field: str, values: dict):
    provisional = model.model_construct(**values, **{hash_field: "0" * 64})
    payload = provisional.model_dump()
    payload[hash_field] = universe_evidence_hash(
        provisional.model_dump(exclude={hash_field})
    )
    return model.model_validate(payload)


def build_gap_remediation_protocol(**values) -> PeriodicFlowGapRemediationProtocol:
    payload = {
        "schema_version": Q1_GAP_PROTOCOL_SCHEMA_VERSION,
        "protocol_id": "q1-periodic-flow-usdm-gap-remediation-v1",
        "status": "FROZEN_AFTER_PILOT_STOP_BEFORE_GAP_MAGNITUDE_SCAN",
        **values,
    }
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(PeriodicFlowGapRemediationProtocol, "protocol_evidence_hash", payload)


def build_gap_remediation_result(**values) -> PeriodicFlowGapRemediationResult:
    passed = (
        values["aggregate_trade_id_gap_count"] == 0
        and values["aggregate_trade_id_non_increasing_count"] == 0
        and values["raw_trade_span_invalid_count"] == 0
        and values["raw_trade_range_overlap_count"] == 0
        and len(values["gap_records"]) <= 10_000
        and values["maximum_single_gap_skipped_raw_ids"] <= 100_000
        and values["skipped_raw_trade_id_fraction"] <= Decimal("0.01")
        and values["timestamp_regression_count"] == 0
        and values["minute_coverage_fraction"] >= Decimal("0.99")
    )
    payload = {
        "schema_version": Q1_GAP_RESULT_SCHEMA_VERSION,
        "result_id": "q1-periodic-flow-usdm-gap-remediation-result-v1",
        "status": "COMPLETE_LOCAL_STRUCTURAL_GAP_DIAGNOSIS_NO_OUTCOMES",
        **values,
        "decision": Q1_GAP_PASS_DECISION if passed else Q1_GAP_FAIL_DECISION,
        "next_authorization": (
            Q1_GAP_PASS_AUTHORIZATION if passed else Q1_GAP_FAIL_AUTHORIZATION
        ),
        "authorizes_separate_full_development_acquisition_protocol": passed,
    }
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(PeriodicFlowGapRemediationResult, "result_evidence_hash", payload)


def build_gap_remediation_audit(**values) -> PeriodicFlowGapRemediationAudit:
    payload = {
        "schema_version": Q1_GAP_AUDIT_SCHEMA_VERSION,
        "audit_id": "q1-periodic-flow-usdm-gap-remediation-audit-v1",
        **values,
    }
    return _build(PeriodicFlowGapRemediationAudit, "audit_evidence_hash", payload)


def audit_gap_remediation_protocol(protocol: PeriodicFlowGapRemediationProtocol) -> bool:
    return protocol.protocol_evidence_hash == universe_evidence_hash(
        protocol.model_dump(exclude={"protocol_evidence_hash"})
    )


def audit_gap_remediation_result(result: PeriodicFlowGapRemediationResult) -> bool:
    return result.result_evidence_hash == universe_evidence_hash(
        result.model_dump(exclude={"result_evidence_hash"})
    )


def audit_gap_remediation_audit(audit: PeriodicFlowGapRemediationAudit) -> bool:
    return audit.audit_evidence_hash == universe_evidence_hash(
        audit.model_dump(exclude={"audit_evidence_hash"})
    )
