from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_v2_source_census import parse_v2_checksum_text
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

Q1_OVERLAP_PROTOCOL_SCHEMA_VERSION = (
    "aurex-q1-usdm-overlap-daily-source-census-protocol-v1"
)
Q1_OVERLAP_RESULT_SCHEMA_VERSION = (
    "aurex-q1-usdm-overlap-daily-source-census-result-v1"
)
Q1_OVERLAP_AUDIT_SCHEMA_VERSION = (
    "aurex-q1-usdm-overlap-daily-source-census-audit-v1"
)
Q1_OVERLAP_PASS_DECISION = (
    "PERMIT_Q1_USDM_DAILY_CROSS_SOURCE_PAYLOAD_PROTOCOL"
)
Q1_OVERLAP_FAIL_DECISION = "STOP_Q1_USDM_DAILY_CROSS_SOURCE_UNAVAILABLE"
Q1_OVERLAP_PASS_AUTHORIZATION = (
    "AUTHORIZE_Q1_USDM_DAILY_CROSS_SOURCE_PAYLOAD_PROTOCOL"
)
Q1_OVERLAP_FAIL_AUTHORIZATION = "NONE_DAILY_CROSS_SOURCE_UNAVAILABLE"


def daily_archive_url(family: Literal["aggTrades", "trades"], day: str) -> str:
    return (
        "https://data.binance.vision/data/futures/um/daily/"
        f"{family}/BTCUSDT/BTCUSDT-{family}-{day}.zip"
    )


class PeriodicFlowOverlapEvent(BaseModel):
    preceding_aggregate_trade_id: int = Field(ge=0)
    current_aggregate_trade_id: int = Field(ge=0)
    preceding_first_raw_trade_id: int = Field(ge=0)
    preceding_last_raw_trade_id: int = Field(ge=0)
    current_first_raw_trade_id: int = Field(ge=0)
    current_last_raw_trade_id: int = Field(ge=0)
    preceding_timestamp_ms: int = Field(gt=0)
    current_timestamp_ms: int = Field(gt=0)
    overlap_raw_trade_id_count: int = Field(gt=0)
    first_overlapped_raw_trade_id: int = Field(ge=0)
    last_overlapped_raw_trade_id: int = Field(ge=0)
    utc_day: str = Field(pattern=r"^2020-01-(0[1-9]|[12]\d|3[01])$")

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_event(self) -> PeriodicFlowOverlapEvent:
        expected_first = max(
            self.preceding_first_raw_trade_id,
            self.current_first_raw_trade_id,
        )
        expected_last = min(
            self.preceding_last_raw_trade_id,
            self.current_last_raw_trade_id,
        )
        expected_day = datetime.fromtimestamp(
            self.current_timestamp_ms / 1000,
            tz=UTC,
        ).date().isoformat()
        if (
            self.current_aggregate_trade_id
            != self.preceding_aggregate_trade_id + 1
            or expected_last < expected_first
            or self.first_overlapped_raw_trade_id != expected_first
            or self.last_overlapped_raw_trade_id != expected_last
            or self.overlap_raw_trade_id_count != expected_last - expected_first + 1
            or self.current_timestamp_ms < self.preceding_timestamp_ms
            or self.utc_day != expected_day
        ):
            raise ValueError("Q1 overlap event arithmetic changed")
        return self


class PeriodicFlowOverlapCensusProtocol(BaseModel):
    schema_version: Literal[
        "aurex-q1-usdm-overlap-daily-source-census-protocol-v1"
    ] = Q1_OVERLAP_PROTOCOL_SCHEMA_VERSION
    protocol_id: Literal["q1-usdm-overlap-daily-source-census-v1"] = (
        "q1-usdm-overlap-daily-source-census-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_PRE_OVERLAP_LOCALIZATION_AND_CHECKSUM_GET"] = (
        "FROZEN_PRE_OVERLAP_LOCALIZATION_AND_CHECKSUM_GET"
    )
    parent_result_file_sha256: str
    parent_result_evidence_hash: str
    parent_audit_file_sha256: str
    parent_audit_evidence_hash: str
    target_archive_sha256: str
    builder_contract_hash: str
    expected_overlap_event_count: Literal[1] = 1
    checksum_families: tuple[Literal["aggTrades"], Literal["trades"]] = (
        "aggTrades",
        "trades",
    )
    maximum_unique_checksum_urls: Literal[2] = 2
    maximum_http_attempts: Literal[6] = 6
    maximum_retries: Literal[2] = 2
    retry_backoff_seconds: tuple[Literal[1], Literal[3]] = (1, 3)
    request_timeout_seconds: Literal[30] = 30
    maximum_checksum_response_bytes: Literal[512] = 512
    permitted_http_statuses: tuple[Literal[200], Literal[404]] = (200, 404)
    archive_payload_requests_permitted: Literal[False] = False
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
        "parent_result_file_sha256",
        "parent_result_evidence_hash",
        "parent_audit_file_sha256",
        "parent_audit_evidence_hash",
        "target_archive_sha256",
        "builder_contract_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> PeriodicFlowOverlapCensusProtocol:
        if (
            self.limitations != tuple(sorted(set(self.limitations)))
            or self.retry_backoff_seconds != (1, 3)
        ):
            raise ValueError("Q1 overlap census scope changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("Q1 overlap census protocol hash changed")
        return self


class PeriodicFlowDailyChecksumRecord(BaseModel):
    family: Literal["aggTrades", "trades"]
    utc_day: str
    archive_url: str
    checksum_url: str
    checked_at: datetime
    http_status: Literal[200, 404]
    checksum_response_bytes: int = Field(ge=0, le=512)
    checksum_text: str | None = Field(default=None, max_length=512)
    checksum_text_sha256: str | None = None
    archive_sha256: str | None = None
    availability: Literal["PRESENT", "MISSING"]
    request_attempt_count: int = Field(ge=1, le=3)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("checked_at")
    @classmethod
    def normalize_checked_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("checksum_text_sha256", "archive_sha256")
    @classmethod
    def normalize_optional_hash(cls, value: str | None) -> str | None:
        return None if value is None else normalize_sha256(value)

    @model_validator(mode="after")
    def validate_record(self) -> PeriodicFlowDailyChecksumRecord:
        expected_archive = daily_archive_url(self.family, self.utc_day)
        present = self.http_status == 200
        if (
            self.archive_url != expected_archive
            or self.checksum_url != f"{expected_archive}.CHECKSUM"
            or self.availability != ("PRESENT" if present else "MISSING")
        ):
            raise ValueError("Q1 daily checksum identity changed")
        if present:
            if (
                self.checksum_text is None
                or self.checksum_text_sha256 is None
                or self.archive_sha256 is None
                or self.checksum_response_bytes <= 0
            ):
                raise ValueError("Q1 present checksum evidence is incomplete")
            archive_name = expected_archive.rsplit("/", maxsplit=1)[-1]
            if (
                sha256(self.checksum_text.encode("utf-8")).hexdigest()
                != self.checksum_text_sha256
                or parse_v2_checksum_text(self.checksum_text, archive_name)
                != self.archive_sha256
            ):
                raise ValueError("Q1 daily checksum text changed")
        elif any(
            (
                self.checksum_response_bytes,
                self.checksum_text,
                self.checksum_text_sha256,
                self.archive_sha256,
            )
        ):
            raise ValueError("Q1 missing checksum cannot contain hash evidence")
        return self


class PeriodicFlowOverlapCensusResult(BaseModel):
    schema_version: Literal[
        "aurex-q1-usdm-overlap-daily-source-census-result-v1"
    ] = Q1_OVERLAP_RESULT_SCHEMA_VERSION
    result_id: Literal["q1-usdm-overlap-daily-source-census-result-v1"] = (
        "q1-usdm-overlap-daily-source-census-result-v1"
    )
    generated_at: datetime
    status: Literal["COMPLETE_OVERLAP_LOCALIZATION_AND_CHECKSUM_ONLY"] = (
        "COMPLETE_OVERLAP_LOCALIZATION_AND_CHECKSUM_ONLY"
    )
    protocol_file_sha256: str
    protocol_evidence_hash: str
    runner_contract_hash: str
    overlap_event: PeriodicFlowOverlapEvent
    checksum_records: tuple[PeriodicFlowDailyChecksumRecord, ...] = Field(
        min_length=2,
        max_length=2,
    )
    checksum_get_attempt_count: int = Field(ge=2, le=6)
    decision: Literal[
        "PERMIT_Q1_USDM_DAILY_CROSS_SOURCE_PAYLOAD_PROTOCOL",
        "STOP_Q1_USDM_DAILY_CROSS_SOURCE_UNAVAILABLE",
    ]
    next_authorization: Literal[
        "AUTHORIZE_Q1_USDM_DAILY_CROSS_SOURCE_PAYLOAD_PROTOCOL",
        "NONE_DAILY_CROSS_SOURCE_UNAVAILABLE",
    ]
    authorizes_daily_cross_source_payload_protocol: bool
    archive_payload_requests_made: Literal[0] = 0
    archive_payload_bytes: Literal[0] = 0
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
    def validate_result(self) -> PeriodicFlowOverlapCensusResult:
        if (
            tuple(item.family for item in self.checksum_records)
            != ("aggTrades", "trades")
            or any(
                item.utc_day != self.overlap_event.utc_day
                for item in self.checksum_records
            )
            or self.checksum_get_attempt_count
            != sum(item.request_attempt_count for item in self.checksum_records)
        ):
            raise ValueError("Q1 overlap checksum matrix changed")
        passed = all(
            item.availability == "PRESENT" for item in self.checksum_records
        )
        if (
            self.decision
            != (Q1_OVERLAP_PASS_DECISION if passed else Q1_OVERLAP_FAIL_DECISION)
            or self.next_authorization
            != (
                Q1_OVERLAP_PASS_AUTHORIZATION
                if passed
                else Q1_OVERLAP_FAIL_AUTHORIZATION
            )
            or self.authorizes_daily_cross_source_payload_protocol != passed
            or self.limitations != tuple(sorted(set(self.limitations)))
            or self.price_or_quantity_values_parsed
            or self.return_metrics_calculated
        ):
            raise ValueError("Q1 overlap census decision or authority changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("Q1 overlap census result hash changed")
        return self


class PeriodicFlowOverlapCensusAudit(BaseModel):
    schema_version: Literal[
        "aurex-q1-usdm-overlap-daily-source-census-audit-v1"
    ] = Q1_OVERLAP_AUDIT_SCHEMA_VERSION
    audit_id: Literal["q1-usdm-overlap-daily-source-census-audit-v1"] = (
        "q1-usdm-overlap-daily-source-census-audit-v1"
    )
    audited_at: datetime
    result_file_sha256: str
    result_evidence_hash: str
    protocol_evidence_hash: str
    overlap_event: PeriodicFlowOverlapEvent
    checksum_archive_sha256: dict[str, str]
    localized_exactly: Literal[True] = True
    checksum_text_reparsed: Literal[True] = True
    archive_payload_requests_made: Literal[0] = 0
    price_or_quantity_values_parsed: tuple[str, ...] = ()
    decision: Literal[
        "PERMIT_Q1_USDM_DAILY_CROSS_SOURCE_PAYLOAD_PROTOCOL",
        "STOP_Q1_USDM_DAILY_CROSS_SOURCE_UNAVAILABLE",
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
    def validate_audit(self) -> PeriodicFlowOverlapCensusAudit:
        if set(self.checksum_archive_sha256) != {"aggTrades", "trades"}:
            raise ValueError("Q1 overlap audit checksum keys changed")
        for value in self.checksum_archive_sha256.values():
            normalize_sha256(value)
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 overlap audit hash changed")
        return self


def _build(model, hash_field: str, values: dict):
    provisional = model.model_construct(**values, **{hash_field: "0" * 64})
    payload = provisional.model_dump()
    payload[hash_field] = universe_evidence_hash(
        provisional.model_dump(exclude={hash_field})
    )
    return model.model_validate(payload)


def build_overlap_census_protocol(**values) -> PeriodicFlowOverlapCensusProtocol:
    payload = {
        "schema_version": Q1_OVERLAP_PROTOCOL_SCHEMA_VERSION,
        "protocol_id": "q1-usdm-overlap-daily-source-census-v1",
        "status": "FROZEN_PRE_OVERLAP_LOCALIZATION_AND_CHECKSUM_GET",
        **values,
    }
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(PeriodicFlowOverlapCensusProtocol, "protocol_evidence_hash", payload)


def build_overlap_census_result(**values) -> PeriodicFlowOverlapCensusResult:
    records = tuple(values["checksum_records"])
    passed = all(item.availability == "PRESENT" for item in records)
    payload = {
        "schema_version": Q1_OVERLAP_RESULT_SCHEMA_VERSION,
        "result_id": "q1-usdm-overlap-daily-source-census-result-v1",
        "status": "COMPLETE_OVERLAP_LOCALIZATION_AND_CHECKSUM_ONLY",
        **values,
        "checksum_records": records,
        "decision": Q1_OVERLAP_PASS_DECISION if passed else Q1_OVERLAP_FAIL_DECISION,
        "next_authorization": (
            Q1_OVERLAP_PASS_AUTHORIZATION
            if passed
            else Q1_OVERLAP_FAIL_AUTHORIZATION
        ),
        "authorizes_daily_cross_source_payload_protocol": passed,
    }
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(PeriodicFlowOverlapCensusResult, "result_evidence_hash", payload)


def build_overlap_census_audit(**values) -> PeriodicFlowOverlapCensusAudit:
    payload = {
        "schema_version": Q1_OVERLAP_AUDIT_SCHEMA_VERSION,
        "audit_id": "q1-usdm-overlap-daily-source-census-audit-v1",
        **values,
    }
    return _build(PeriodicFlowOverlapCensusAudit, "audit_evidence_hash", payload)


def audit_overlap_census_protocol(protocol: PeriodicFlowOverlapCensusProtocol) -> bool:
    return protocol.protocol_evidence_hash == universe_evidence_hash(
        protocol.model_dump(exclude={"protocol_evidence_hash"})
    )


def audit_overlap_census_result(result: PeriodicFlowOverlapCensusResult) -> bool:
    return result.result_evidence_hash == universe_evidence_hash(
        result.model_dump(exclude={"result_evidence_hash"})
    )


def audit_overlap_census_audit(audit: PeriodicFlowOverlapCensusAudit) -> bool:
    return audit.audit_evidence_hash == universe_evidence_hash(
        audit.model_dump(exclude={"audit_evidence_hash"})
    )
