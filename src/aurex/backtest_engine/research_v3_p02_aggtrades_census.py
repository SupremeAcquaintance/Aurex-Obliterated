from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_v2_acquisition_protocol import (
    V2_COMPLETE_SYMBOLS,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

V3_P02_CENSUS_CONTRACT_SCHEMA_VERSION = (
    "aurex-v3-p02-aggregate-trades-census-contract-v1"
)
V3_P02_CENSUS_RESULT_SCHEMA_VERSION = (
    "aurex-v3-p02-aggregate-trades-census-result-v1"
)
V3_P02_CENSUS_PASS_DECISION = (
    "PERMIT_SEPARATE_V3P02_AGGTRADES_PILOT_PROTOCOL"
)
V3_P02_CENSUS_FAIL_DECISION = (
    "REJECT_V3P02_INSUFFICIENT_AGGTRADES_ARCHIVE_COVERAGE"
)
V3_P02_MONTHS = [
    f"{year}-{month:02d}"
    for year in (2023, 2024)
    for month in range(1, 13)
]


def archive_url(symbol: str, month: str) -> str:
    return (
        "https://data.binance.vision/data/futures/um/monthly/aggTrades/"
        f"{symbol}/{symbol}-aggTrades-{month}.zip"
    )


class V3P02AggTradesTarget(BaseModel):
    symbol: str = Field(pattern=r"^[A-Z0-9]{5,20}$")
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    archive_url: str = Field(min_length=60, max_length=1000)
    checksum_url: str = Field(min_length=70, max_length=1100)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_target(self) -> V3P02AggTradesTarget:
        expected = archive_url(self.symbol, self.month)
        if self.archive_url != expected or self.checksum_url != f"{expected}.CHECKSUM":
            raise ValueError("V3P02 aggregate-trade target changed")
        parsed_archive = urlparse(self.archive_url)
        parsed_checksum = urlparse(self.checksum_url)
        if (
            parsed_archive.scheme != "https"
            or parsed_archive.hostname != "data.binance.vision"
            or parsed_checksum.scheme != "https"
            or parsed_checksum.hostname != "data.binance.vision"
        ):
            raise ValueError("V3P02 target must use official Binance Vision HTTPS")
        return self

    @property
    def key(self) -> tuple[str, str]:
        return self.symbol, self.month


def authoritative_targets() -> list[V3P02AggTradesTarget]:
    return [
        V3P02AggTradesTarget(
            symbol=symbol,
            month=month,
            archive_url=archive_url(symbol, month),
            checksum_url=f"{archive_url(symbol, month)}.CHECKSUM",
        )
        for symbol in V2_COMPLETE_SYMBOLS
        for month in V3_P02_MONTHS
    ]


class V3P02AggTradesCensusContract(BaseModel):
    schema_version: Literal[
        "aurex-v3-p02-aggregate-trades-census-contract-v1"
    ] = V3_P02_CENSUS_CONTRACT_SCHEMA_VERSION
    contract_id: Literal["v3-p02-aggregate-trades-census-v1"] = (
        "v3-p02-aggregate-trades-census-v1"
    )
    contract_version: Literal["1.0.0"] = "1.0.0"
    frozen_at: datetime
    status: Literal["FROZEN_PRE_NETWORK_OBSERVATION"] = (
        "FROZEN_PRE_NETWORK_OBSERVATION"
    )
    discovery_charter_evidence_hash: str
    proposal_register_evidence_hash: str
    builder_contract_hash: str
    proposal_id: Literal[
        "V3P02_CLOCK_PHASE_INTRADAY_PREDICTABILITY"
    ] = "V3P02_CLOCK_PHASE_INTRADAY_PREDICTABILITY"
    targets: list[V3P02AggTradesTarget] = Field(
        min_length=744,
        max_length=744,
    )
    target_manifest_hash: str
    source_domain: Literal["data.binance.vision"] = "data.binance.vision"
    source_family: Literal["usd_m_monthly_aggregate_trades"] = (
        "usd_m_monthly_aggregate_trades"
    )
    maximum_unique_checksum_urls: Literal[744] = 744
    maximum_http_attempts: Literal[2232] = 2232
    maximum_checksum_response_bytes: Literal[4096] = 4096
    request_timeout_seconds: Literal[30] = 30
    maximum_retries: Literal[2] = 2
    retry_backoff_seconds: list[int] = Field(default_factory=lambda: [1, 3])
    maximum_concurrency: Literal[4] = 4
    minimum_complete_symbols: Literal[10] = 10
    permitted_http_statuses: list[int] = Field(
        default_factory=lambda: [200, 404]
    )
    archive_payload_requests_permitted: Literal[False] = False
    market_numeric_values_permitted: Literal[False] = False
    strategy_outcomes_permitted: Literal[False] = False
    selection_permitted: Literal[False] = False
    creates_candidate: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    limitations: list[str] = Field(min_length=5)
    contract_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "discovery_charter_evidence_hash",
        "proposal_register_evidence_hash",
        "builder_contract_hash",
        "target_manifest_hash",
        "contract_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "retry_backoff_seconds",
        "permitted_http_statuses",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list) -> list:
        return sorted(set(value))

    @model_validator(mode="after")
    def validate_contract(self) -> V3P02AggTradesCensusContract:
        expected_targets = authoritative_targets()
        if self.targets != expected_targets:
            raise ValueError("V3P02 target matrix changed")
        if self.target_manifest_hash != universe_evidence_hash(
            {"targets": [item.model_dump() for item in expected_targets]}
        ):
            raise ValueError("V3P02 target manifest hash changed")
        if self.retry_backoff_seconds != [1, 3]:
            raise ValueError("V3P02 retry policy changed")
        if self.permitted_http_statuses != [200, 404]:
            raise ValueError("V3P02 HTTP policy changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"contract_evidence_hash"})
        )
        if self.contract_evidence_hash != expected_hash:
            raise ValueError("V3P02 contract hash does not match")
        return self


class V3P02AggTradesCensusRecord(BaseModel):
    symbol: str = Field(pattern=r"^[A-Z0-9]{5,20}$")
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    archive_url: str
    checksum_url: str
    checked_at: datetime
    http_status: Literal[200, 404]
    checksum_response_bytes: int = Field(ge=0, le=4096)
    checksum_sha256: str | None
    availability: Literal["PRESENT", "MISSING"]
    request_attempt_count: int = Field(ge=1, le=3)

    model_config = ConfigDict(extra="forbid")

    @field_validator("checked_at")
    @classmethod
    def normalize_checked_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("checksum_sha256")
    @classmethod
    def normalize_optional_hash(cls, value: str | None) -> str | None:
        return normalize_sha256(value) if value is not None else None

    @model_validator(mode="after")
    def validate_record(self) -> V3P02AggTradesCensusRecord:
        target = V3P02AggTradesTarget(
            symbol=self.symbol,
            month=self.month,
            archive_url=self.archive_url,
            checksum_url=self.checksum_url,
        )
        if target.archive_url != self.archive_url:
            raise ValueError("V3P02 census target changed")
        present = self.http_status == 200
        if (
            self.availability != ("PRESENT" if present else "MISSING")
            or (self.checksum_sha256 is not None) != present
            or (self.checksum_response_bytes > 0) != present
        ):
            raise ValueError("V3P02 availability does not reconcile")
        return self

    @property
    def key(self) -> tuple[str, str]:
        return self.symbol, self.month


class V3P02AggTradesCensusSummary(BaseModel):
    target_count: Literal[744] = 744
    observed_count: Literal[744] = 744
    present_count: int = Field(ge=0, le=744)
    missing_count: int = Field(ge=0, le=744)
    complete_symbol_count: int = Field(ge=0, le=31)
    incomplete_symbol_count: int = Field(ge=0, le=31)
    http_attempt_count: int = Field(ge=744, le=2232)
    complete_symbols: list[str]
    incomplete_symbols: list[str]

    model_config = ConfigDict(extra="forbid")

    @field_validator("complete_symbols", "incomplete_symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        return sorted({item.strip().upper() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_summary(self) -> V3P02AggTradesCensusSummary:
        if self.present_count + self.missing_count != 744:
            raise ValueError("V3P02 observation counts do not reconcile")
        if (
            self.complete_symbol_count + self.incomplete_symbol_count != 31
            or self.complete_symbol_count != len(self.complete_symbols)
            or self.incomplete_symbol_count != len(self.incomplete_symbols)
            or set(self.complete_symbols) | set(self.incomplete_symbols)
            != set(V2_COMPLETE_SYMBOLS)
            or set(self.complete_symbols) & set(self.incomplete_symbols)
        ):
            raise ValueError("V3P02 symbol partition does not reconcile")
        return self


class V3P02AggTradesCensusResult(BaseModel):
    schema_version: Literal[
        "aurex-v3-p02-aggregate-trades-census-result-v1"
    ] = V3_P02_CENSUS_RESULT_SCHEMA_VERSION
    result_id: Literal["v3-p02-aggregate-trades-census-result-v1"] = (
        "v3-p02-aggregate-trades-census-result-v1"
    )
    result_version: Literal["1.0.0"] = "1.0.0"
    generated_at: datetime
    status: Literal["COMPLETE_METADATA_ONLY_NO_RETURN_CENSUS"] = (
        "COMPLETE_METADATA_ONLY_NO_RETURN_CENSUS"
    )
    contract_evidence_hash: str
    target_manifest_hash: str
    runner_contract_hash: str
    records: list[V3P02AggTradesCensusRecord] = Field(
        min_length=744,
        max_length=744,
    )
    summary: V3P02AggTradesCensusSummary
    decision: Literal[
        "PERMIT_SEPARATE_V3P02_AGGTRADES_PILOT_PROTOCOL",
        "REJECT_V3P02_INSUFFICIENT_AGGTRADES_ARCHIVE_COVERAGE",
    ]
    authorizes_separate_pilot_protocol: bool
    archive_payload_requests_made: Literal[0] = 0
    market_numeric_values_inspected: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)
    selects_primary: Literal[False] = False
    creates_candidate: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    limitations: list[str] = Field(min_length=5)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "contract_evidence_hash",
        "target_manifest_hash",
        "runner_contract_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "market_numeric_values_inspected",
        "return_metrics_calculated",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_result(self) -> V3P02AggTradesCensusResult:
        if self.records != sorted(self.records, key=lambda item: item.key):
            raise ValueError("V3P02 records are not canonical")
        expected_keys = {
            (symbol, month)
            for symbol in V2_COMPLETE_SYMBOLS
            for month in V3_P02_MONTHS
        }
        if (
            len({item.key for item in self.records}) != 744
            or {item.key for item in self.records} != expected_keys
        ):
            raise ValueError("V3P02 result matrix changed")
        present = sum(item.availability == "PRESENT" for item in self.records)
        complete = sorted(
            symbol
            for symbol in V2_COMPLETE_SYMBOLS
            if sum(
                item.symbol == symbol and item.availability == "PRESENT"
                for item in self.records
            )
            == 24
        )
        if (
            self.summary.present_count != present
            or self.summary.complete_symbols != complete
            or self.summary.http_attempt_count
            != sum(item.request_attempt_count for item in self.records)
        ):
            raise ValueError("V3P02 summary does not match records")
        passed = self.summary.complete_symbol_count >= 10
        expected_decision = (
            V3_P02_CENSUS_PASS_DECISION
            if passed
            else V3_P02_CENSUS_FAIL_DECISION
        )
        if (
            self.decision != expected_decision
            or self.authorizes_separate_pilot_protocol != passed
        ):
            raise ValueError("V3P02 decision does not reconcile")
        if self.market_numeric_values_inspected or self.return_metrics_calculated:
            raise ValueError("V3P02 census may contain no outcomes")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected_hash:
            raise ValueError("V3P02 result hash does not match")
        return self


def build_v3_p02_census_contract(**values) -> V3P02AggTradesCensusContract:
    targets = authoritative_targets()
    payload = {
        "schema_version": V3_P02_CENSUS_CONTRACT_SCHEMA_VERSION,
        "contract_id": "v3-p02-aggregate-trades-census-v1",
        "contract_version": "1.0.0",
        "status": "FROZEN_PRE_NETWORK_OBSERVATION",
        "proposal_id": "V3P02_CLOCK_PHASE_INTRADAY_PREDICTABILITY",
        "targets": targets,
        "target_manifest_hash": universe_evidence_hash(
            {"targets": [item.model_dump() for item in targets]}
        ),
        "source_domain": "data.binance.vision",
        "source_family": "usd_m_monthly_aggregate_trades",
        "maximum_unique_checksum_urls": 744,
        "maximum_http_attempts": 2232,
        "maximum_checksum_response_bytes": 4096,
        "request_timeout_seconds": 30,
        "maximum_retries": 2,
        "retry_backoff_seconds": [1, 3],
        "maximum_concurrency": 4,
        "minimum_complete_symbols": 10,
        "permitted_http_statuses": [200, 404],
        "archive_payload_requests_permitted": False,
        "market_numeric_values_permitted": False,
        "strategy_outcomes_permitted": False,
        "selection_permitted": False,
        "creates_candidate": False,
        "creates_paper_eligibility": False,
        "creates_live_eligibility": False,
        **values,
    }
    payload["limitations"] = sorted(set(payload["limitations"]))
    return V3P02AggTradesCensusContract(
        **payload,
        contract_evidence_hash=universe_evidence_hash(payload),
    )


def build_v3_p02_census_result(**values) -> V3P02AggTradesCensusResult:
    records = sorted(values.pop("records"), key=lambda item: item.key)
    present = sum(item.availability == "PRESENT" for item in records)
    complete = sorted(
        symbol
        for symbol in V2_COMPLETE_SYMBOLS
        if sum(
            item.symbol == symbol and item.availability == "PRESENT"
            for item in records
        )
        == 24
    )
    incomplete = sorted(set(V2_COMPLETE_SYMBOLS) - set(complete))
    summary = V3P02AggTradesCensusSummary(
        present_count=present,
        missing_count=744 - present,
        complete_symbol_count=len(complete),
        incomplete_symbol_count=len(incomplete),
        http_attempt_count=sum(item.request_attempt_count for item in records),
        complete_symbols=complete,
        incomplete_symbols=incomplete,
    )
    passed = len(complete) >= 10
    payload = {
        "schema_version": V3_P02_CENSUS_RESULT_SCHEMA_VERSION,
        "result_id": "v3-p02-aggregate-trades-census-result-v1",
        "result_version": "1.0.0",
        "status": "COMPLETE_METADATA_ONLY_NO_RETURN_CENSUS",
        "records": records,
        "summary": summary,
        "decision": (
            V3_P02_CENSUS_PASS_DECISION
            if passed
            else V3_P02_CENSUS_FAIL_DECISION
        ),
        "authorizes_separate_pilot_protocol": passed,
        "archive_payload_requests_made": 0,
        "market_numeric_values_inspected": [],
        "return_metrics_calculated": [],
        "selects_primary": False,
        "creates_candidate": False,
        "creates_paper_eligibility": False,
        "creates_live_eligibility": False,
        **values,
    }
    payload["limitations"] = sorted(set(payload["limitations"]))
    return V3P02AggTradesCensusResult(
        **payload,
        result_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v3_p02_census_contract(
    contract: V3P02AggTradesCensusContract,
) -> bool:
    return contract.contract_evidence_hash == universe_evidence_hash(
        contract.model_dump(exclude={"contract_evidence_hash"})
    )


def audit_v3_p02_census_result(
    result: V3P02AggTradesCensusResult,
) -> bool:
    return result.result_evidence_hash == universe_evidence_hash(
        result.model_dump(exclude={"result_evidence_hash"})
    )
