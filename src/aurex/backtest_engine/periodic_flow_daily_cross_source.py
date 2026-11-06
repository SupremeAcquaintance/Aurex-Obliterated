from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.periodic_flow_overlap_census import (
    PeriodicFlowOverlapEvent,
    daily_archive_url,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

Q1_DAILY_CROSS_PROTOCOL_SCHEMA_VERSION = (
    "aurex-q1-usdm-daily-cross-source-payload-protocol-v1"
)
Q1_DAILY_CROSS_RESULT_SCHEMA_VERSION = (
    "aurex-q1-usdm-daily-cross-source-payload-result-v1"
)
Q1_DAILY_CROSS_AUDIT_SCHEMA_VERSION = (
    "aurex-q1-usdm-daily-cross-source-payload-audit-v1"
)
Q1_DAILY_CROSS_PASS_DECISION = (
    "PERMIT_Q1_USDM_RAW_TRADES_METADATA_CENSUS_PROTOCOL"
)
Q1_DAILY_CROSS_FAIL_DECISION = "STOP_Q1_USDM_CROSS_SOURCE_ADJUDICATION_FAILED"
Q1_DAILY_CROSS_PASS_AUTHORIZATION = (
    "AUTHORIZE_Q1_USDM_RAW_TRADES_METADATA_CENSUS_PROTOCOL"
)
Q1_DAILY_CROSS_FAIL_AUTHORIZATION = "NONE_CROSS_SOURCE_ADJUDICATION_FAILED"


class PeriodicFlowDailyPayloadTarget(BaseModel):
    family: Literal["aggTrades", "trades"]
    utc_day: Literal["2020-01-15"] = "2020-01-15"
    archive_url: str
    published_archive_sha256: str
    expected_column_count: Literal[6, 7]
    expected_member_name: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("published_archive_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_target(self) -> PeriodicFlowDailyPayloadTarget:
        if (
            self.archive_url != daily_archive_url(self.family, self.utc_day)
            or self.expected_column_count
            != (7 if self.family == "aggTrades" else 6)
            or self.expected_member_name
            != f"BTCUSDT-{self.family}-{self.utc_day}.csv"
        ):
            raise ValueError("Q1 daily cross-source target changed")
        return self


class PeriodicFlowDailyCrossSourceProtocol(BaseModel):
    schema_version: Literal[
        "aurex-q1-usdm-daily-cross-source-payload-protocol-v1"
    ] = Q1_DAILY_CROSS_PROTOCOL_SCHEMA_VERSION
    protocol_id: Literal["q1-usdm-daily-cross-source-payload-v1"] = (
        "q1-usdm-daily-cross-source-payload-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_PRE_TWO_DAILY_PAYLOAD_GETS"] = (
        "FROZEN_PRE_TWO_DAILY_PAYLOAD_GETS"
    )
    census_result_file_sha256: str
    census_result_evidence_hash: str
    census_audit_file_sha256: str
    census_audit_evidence_hash: str
    builder_contract_hash: str
    parent_overlap_event: PeriodicFlowOverlapEvent
    targets: tuple[PeriodicFlowDailyPayloadTarget, ...] = Field(
        min_length=2,
        max_length=2,
    )
    target_manifest_hash: str
    maximum_attempts_per_archive: Literal[3] = 3
    maximum_payload_get_attempts: Literal[6] = 6
    request_timeout_seconds: Literal[120] = 120
    retry_backoff_seconds: tuple[Literal[1], Literal[3]] = (1, 3)
    redirects_permitted: Literal[False] = False
    maximum_archive_bytes_each: Literal[500_000_000] = 500_000_000
    maximum_total_archive_bytes: Literal[1_000_000_000] = 1_000_000_000
    maximum_member_uncompressed_bytes_each: Literal[5_000_000_000] = (
        5_000_000_000
    )
    maximum_zip_expansion_ratio: Literal[100] = 100
    price_or_quantity_parsing_permitted: Literal[False] = False
    return_calculation_permitted: Literal[False] = False
    validation_outcomes_permitted: Literal[False] = False
    holdout_access_permitted: Literal[False] = False
    candidate_creation_permitted: Literal[False] = False
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
    def validate_protocol(self) -> PeriodicFlowDailyCrossSourceProtocol:
        if (
            tuple(item.family for item in self.targets)
            != ("aggTrades", "trades")
            or self.target_manifest_hash
            != universe_evidence_hash(
                {"targets": [item.model_dump() for item in self.targets]}
            )
            or self.limitations != tuple(sorted(set(self.limitations)))
        ):
            raise ValueError("Q1 daily cross-source protocol scope changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("Q1 daily cross-source protocol hash changed")
        return self


class PeriodicFlowDailyArchiveEvidence(BaseModel):
    family: Literal["aggTrades", "trades"]
    local_path: str
    archive_sha256: str
    published_archive_sha256: str
    archive_bytes: int = Field(gt=0, le=500_000_000)
    member_name: str
    member_compressed_bytes: int = Field(gt=0)
    member_uncompressed_bytes: int = Field(gt=0, le=5_000_000_000)
    row_count: int = Field(gt=0)
    first_id: int = Field(ge=0)
    last_id: int = Field(ge=0)
    id_non_increasing_count: int = Field(ge=0)
    id_gap_count: int = Field(ge=0)
    timestamp_regression_count: int = Field(ge=0)
    monthly_overlap_event_match_count: int = Field(ge=0)
    target_raw_trade_id_occurrence_count: int = Field(ge=0)
    target_raw_trade_timestamp_ms: int | None
    payload_get_attempt_count: int = Field(ge=1, le=3)
    archive_pass: bool
    reason_codes: tuple[str, ...]
    parsed_numeric_fields: tuple[str, ...]
    excluded_numeric_fields: tuple[str, ...]

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("archive_sha256", "published_archive_sha256")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_evidence(self) -> PeriodicFlowDailyArchiveEvidence:
        expected_path = (
            "source_snapshots/q1_periodic_flow_daily_cross_source_v1/"
            f"{self.family}/BTCUSDT-{self.family}-2020-01-15.zip"
        )
        expected_member = f"BTCUSDT-{self.family}-2020-01-15.csv"
        if (
            self.local_path != expected_path
            or self.member_name != expected_member
            or self.archive_sha256 != self.published_archive_sha256
            or self.member_compressed_bytes > self.archive_bytes
            or self.member_uncompressed_bytes > self.member_compressed_bytes * 100
        ):
            raise ValueError("Q1 daily archive identity changed")
        reasons = []
        if self.id_non_increasing_count:
            reasons.append("ID_NOT_STRICTLY_INCREASING")
        if self.timestamp_regression_count:
            reasons.append("TIMESTAMP_REGRESSION")
        if self.family == "aggTrades":
            if self.monthly_overlap_event_match_count != 1:
                reasons.append("MONTHLY_OVERLAP_NOT_EXACTLY_REPRODUCED")
            if self.target_raw_trade_id_occurrence_count != 0:
                raise ValueError("Q1 aggregate evidence cannot report raw rows")
            expected_parsed = (
                "aggregate_trade_id",
                "first_trade_id",
                "last_trade_id",
                "timestamp",
            )
            expected_excluded = ("price", "quantity")
        else:
            if self.target_raw_trade_id_occurrence_count != 1:
                reasons.append("TARGET_RAW_TRADE_ID_NOT_UNIQUE")
            if self.target_raw_trade_timestamp_ms is None:
                reasons.append("TARGET_RAW_TRADE_TIMESTAMP_MISSING")
            if self.monthly_overlap_event_match_count != 0:
                raise ValueError("Q1 raw trade evidence cannot report agg event")
            expected_parsed = ("trade_id", "timestamp")
            expected_excluded = ("price", "quantity", "quote_quantity")
        expected_reasons = tuple(sorted(reasons))
        if (
            self.reason_codes != expected_reasons
            or self.archive_pass != (not reasons)
            or self.parsed_numeric_fields != expected_parsed
            or self.excluded_numeric_fields != expected_excluded
        ):
            raise ValueError("Q1 daily archive decision or field boundary changed")
        return self


class PeriodicFlowDailyCrossSourceResult(BaseModel):
    schema_version: Literal[
        "aurex-q1-usdm-daily-cross-source-payload-result-v1"
    ] = Q1_DAILY_CROSS_RESULT_SCHEMA_VERSION
    result_id: Literal["q1-usdm-daily-cross-source-payload-result-v1"] = (
        "q1-usdm-daily-cross-source-payload-result-v1"
    )
    generated_at: datetime
    status: Literal["COMPLETE_DAILY_CROSS_SOURCE_NO_MARKET_VALUES"] = (
        "COMPLETE_DAILY_CROSS_SOURCE_NO_MARKET_VALUES"
    )
    protocol_file_sha256: str
    protocol_evidence_hash: str
    runner_contract_hash: str
    parent_overlap_event: PeriodicFlowOverlapEvent
    archive_evidence: tuple[PeriodicFlowDailyArchiveEvidence, ...] = Field(
        min_length=2,
        max_length=2,
    )
    payload_get_attempt_count: int = Field(ge=2, le=6)
    total_archive_bytes: int = Field(gt=0, le=1_000_000_000)
    raw_trade_timestamp_matches_aggregate_timestamp: bool
    adjudication: Literal[
        "AGGREGATE_SOURCE_REPRODUCES_DUPLICATE_RAW_REFERENCE_USE_RAW_TRADES"
    ] = "AGGREGATE_SOURCE_REPRODUCES_DUPLICATE_RAW_REFERENCE_USE_RAW_TRADES"
    decision: Literal[
        "PERMIT_Q1_USDM_RAW_TRADES_METADATA_CENSUS_PROTOCOL",
        "STOP_Q1_USDM_CROSS_SOURCE_ADJUDICATION_FAILED",
    ]
    next_authorization: Literal[
        "AUTHORIZE_Q1_USDM_RAW_TRADES_METADATA_CENSUS_PROTOCOL",
        "NONE_CROSS_SOURCE_ADJUDICATION_FAILED",
    ]
    authorizes_usdm_raw_trades_metadata_census_protocol: bool
    price_or_quantity_values_parsed: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    strategy_candidates_created: Literal[0] = 0
    orders_submitted: Literal[0] = 0
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
    def validate_result(self) -> PeriodicFlowDailyCrossSourceResult:
        if tuple(item.family for item in self.archive_evidence) != (
            "aggTrades",
            "trades",
        ):
            raise ValueError("Q1 cross-source evidence order changed")
        aggregate, trades = self.archive_evidence
        if (
            self.payload_get_attempt_count
            != sum(item.payload_get_attempt_count for item in self.archive_evidence)
            or self.total_archive_bytes
            != sum(item.archive_bytes for item in self.archive_evidence)
        ):
            raise ValueError("Q1 cross-source resource totals changed")
        expected_timestamp_match = (
            trades.target_raw_trade_timestamp_ms
            == self.parent_overlap_event.current_timestamp_ms
        )
        passed = (
            aggregate.archive_pass
            and trades.archive_pass
            and expected_timestamp_match
        )
        if (
            self.raw_trade_timestamp_matches_aggregate_timestamp
            != expected_timestamp_match
            or self.decision
            != (
                Q1_DAILY_CROSS_PASS_DECISION
                if passed
                else Q1_DAILY_CROSS_FAIL_DECISION
            )
            or self.next_authorization
            != (
                Q1_DAILY_CROSS_PASS_AUTHORIZATION
                if passed
                else Q1_DAILY_CROSS_FAIL_AUTHORIZATION
            )
            or self.authorizes_usdm_raw_trades_metadata_census_protocol != passed
            or self.limitations != tuple(sorted(set(self.limitations)))
            or self.price_or_quantity_values_parsed
            or self.return_metrics_calculated
        ):
            raise ValueError("Q1 cross-source decision or authority changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("Q1 cross-source result hash changed")
        return self


class PeriodicFlowDailyCrossSourceAudit(BaseModel):
    schema_version: Literal[
        "aurex-q1-usdm-daily-cross-source-payload-audit-v1"
    ] = Q1_DAILY_CROSS_AUDIT_SCHEMA_VERSION
    audit_id: Literal["q1-usdm-daily-cross-source-payload-audit-v1"] = (
        "q1-usdm-daily-cross-source-payload-audit-v1"
    )
    audited_at: datetime
    result_file_sha256: str
    result_evidence_hash: str
    protocol_evidence_hash: str
    archive_file_sha256: dict[str, str]
    reconstructed_exactly: Literal[True] = True
    price_or_quantity_values_parsed: tuple[str, ...] = ()
    decision: Literal[
        "PERMIT_Q1_USDM_RAW_TRADES_METADATA_CENSUS_PROTOCOL",
        "STOP_Q1_USDM_CROSS_SOURCE_ADJUDICATION_FAILED",
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
    def validate_audit(self) -> PeriodicFlowDailyCrossSourceAudit:
        if set(self.archive_file_sha256) != {"aggTrades", "trades"}:
            raise ValueError("Q1 cross-source audit archive keys changed")
        for value in self.archive_file_sha256.values():
            normalize_sha256(value)
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 cross-source audit hash changed")
        return self


def _build(model, hash_field: str, values: dict):
    provisional = model.model_construct(**values, **{hash_field: "0" * 64})
    payload = provisional.model_dump()
    payload[hash_field] = universe_evidence_hash(
        provisional.model_dump(exclude={hash_field})
    )
    return model.model_validate(payload)


def build_daily_cross_protocol(**values) -> PeriodicFlowDailyCrossSourceProtocol:
    payload = {
        "schema_version": Q1_DAILY_CROSS_PROTOCOL_SCHEMA_VERSION,
        "protocol_id": "q1-usdm-daily-cross-source-payload-v1",
        "status": "FROZEN_PRE_TWO_DAILY_PAYLOAD_GETS",
        **values,
    }
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(PeriodicFlowDailyCrossSourceProtocol, "protocol_evidence_hash", payload)


def build_daily_cross_result(**values) -> PeriodicFlowDailyCrossSourceResult:
    evidence = tuple(values["archive_evidence"])
    aggregate, trades = evidence
    timestamp_match = (
        trades.target_raw_trade_timestamp_ms
        == values["parent_overlap_event"].current_timestamp_ms
    )
    passed = aggregate.archive_pass and trades.archive_pass and timestamp_match
    payload = {
        "schema_version": Q1_DAILY_CROSS_RESULT_SCHEMA_VERSION,
        "result_id": "q1-usdm-daily-cross-source-payload-result-v1",
        "status": "COMPLETE_DAILY_CROSS_SOURCE_NO_MARKET_VALUES",
        **values,
        "archive_evidence": evidence,
        "raw_trade_timestamp_matches_aggregate_timestamp": timestamp_match,
        "decision": (
            Q1_DAILY_CROSS_PASS_DECISION if passed else Q1_DAILY_CROSS_FAIL_DECISION
        ),
        "next_authorization": (
            Q1_DAILY_CROSS_PASS_AUTHORIZATION
            if passed
            else Q1_DAILY_CROSS_FAIL_AUTHORIZATION
        ),
        "authorizes_usdm_raw_trades_metadata_census_protocol": passed,
    }
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(PeriodicFlowDailyCrossSourceResult, "result_evidence_hash", payload)


def build_daily_cross_audit(**values) -> PeriodicFlowDailyCrossSourceAudit:
    payload = {
        "schema_version": Q1_DAILY_CROSS_AUDIT_SCHEMA_VERSION,
        "audit_id": "q1-usdm-daily-cross-source-payload-audit-v1",
        **values,
    }
    return _build(PeriodicFlowDailyCrossSourceAudit, "audit_evidence_hash", payload)


def audit_daily_cross_protocol(protocol: PeriodicFlowDailyCrossSourceProtocol) -> bool:
    return protocol.protocol_evidence_hash == universe_evidence_hash(
        protocol.model_dump(exclude={"protocol_evidence_hash"})
    )


def audit_daily_cross_result(result: PeriodicFlowDailyCrossSourceResult) -> bool:
    return result.result_evidence_hash == universe_evidence_hash(
        result.model_dump(exclude={"result_evidence_hash"})
    )


def audit_daily_cross_audit(audit: PeriodicFlowDailyCrossSourceAudit) -> bool:
    return audit.audit_evidence_hash == universe_evidence_hash(
        audit.model_dump(exclude={"audit_evidence_hash"})
    )
