from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_v2_acquisition_protocol import (
    V2_COMPLETE_SYMBOLS,
)
from aurex.backtest_engine.research_v3_proposal_register import (
    V3ProposalCoverageContract,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

V3_P01_COVERAGE_RESULT_SCHEMA_VERSION = (
    "aurex-v3-p01-timestamp-coverage-result-v1"
)
V3_P01_SYNC_FAMILIES = [
    "spot_klines_1m",
    "um_contract_klines_1m",
    "um_index_price_klines_1m",
    "um_mark_price_klines_1m",
]
V3_P01_MONTH_REASON_CODES = [
    "MAXIMUM_GAP_EXCEEDS_LIMIT",
    "MONTH_COVERAGE_BELOW_FLOOR",
]
V3_P01_SYMBOL_REASON_CODES = [
    "CURRENT_FILTER_PROXY_FAIL",
    "FUNDING_ARCHIVE_MATRIX_INCOMPLETE",
    "ONE_OR_MORE_MONTHS_FAIL",
    "TOTAL_COVERAGE_BELOW_FLOOR",
]
V3_P01_COVERAGE_PASS_DECISION = (
    "PERMIT_SEPARATE_V3P01_CROSS_ASSET_FOUNDATION_AND_METADATA_PROTOCOL"
)
V3_P01_COVERAGE_FAIL_DECISION = (
    "REJECT_V3P01_INSUFFICIENT_SYNCHRONIZED_SOURCE_COVERAGE"
)


class V3P01MonthCoverageEvidence(BaseModel):
    symbol: str = Field(pattern=r"^[A-Z0-9]{5,20}$")
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    family_archive_sha256: dict[str, str]
    family_row_counts: dict[str, int]
    expected_minute_count: int = Field(gt=0)
    synchronized_minute_count: int = Field(ge=0)
    missing_synchronized_minute_count: int = Field(ge=0)
    synchronized_coverage_fraction: Decimal = Field(ge=0, le=1)
    maximum_consecutive_gap_minutes: int = Field(ge=0)
    first_synchronized_timestamp_ms: int | None = Field(default=None, ge=0)
    last_synchronized_timestamp_ms: int | None = Field(default=None, ge=0)
    month_coverage_pass: bool
    reason_codes: list[str]
    numeric_market_fields_inspected: list[str] = Field(default_factory=list)
    synthetic_rows_created: Literal[False] = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("family_archive_sha256")
    @classmethod
    def normalize_hashes(cls, value: dict[str, str]) -> dict[str, str]:
        return {
            key: normalize_sha256(item)
            for key, item in sorted(value.items())
        }

    @field_validator("family_row_counts")
    @classmethod
    def normalize_counts(cls, value: dict[str, int]) -> dict[str, int]:
        return dict(sorted(value.items()))

    @field_validator("reason_codes", "numeric_market_fields_inspected")
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_evidence(self) -> V3P01MonthCoverageEvidence:
        expected_families = set(V3_P01_SYNC_FAMILIES)
        if (
            set(self.family_archive_sha256) != expected_families
            or set(self.family_row_counts) != expected_families
        ):
            raise ValueError("V3P01 synchronized family matrix changed")
        if self.synchronized_minute_count > self.expected_minute_count:
            raise ValueError("V3P01 synchronized minute count exceeds month")
        if (
            self.missing_synchronized_minute_count
            != self.expected_minute_count - self.synchronized_minute_count
        ):
            raise ValueError("V3P01 missing-minute count does not reconcile")
        expected_fraction = (
            Decimal(self.synchronized_minute_count)
            / Decimal(self.expected_minute_count)
        )
        if self.synchronized_coverage_fraction != expected_fraction:
            raise ValueError("V3P01 month coverage fraction does not reconcile")
        if not set(self.reason_codes).issubset(V3_P01_MONTH_REASON_CODES):
            raise ValueError("V3P01 month reason changed")
        if self.month_coverage_pass != (not self.reason_codes):
            raise ValueError("V3P01 month decision does not reconcile")
        if self.numeric_market_fields_inspected:
            raise ValueError("V3P01 coverage may inspect timestamps only")
        if self.synchronized_minute_count == 0:
            if (
                self.first_synchronized_timestamp_ms is not None
                or self.last_synchronized_timestamp_ms is not None
            ):
                raise ValueError("V3P01 empty month has synchronized boundary")
        elif (
            self.first_synchronized_timestamp_ms is None
            or self.last_synchronized_timestamp_ms is None
            or self.first_synchronized_timestamp_ms
            > self.last_synchronized_timestamp_ms
        ):
            raise ValueError("V3P01 synchronized boundary is invalid")
        return self

    @property
    def key(self) -> tuple[str, str]:
        return self.symbol, self.month


class V3P01SymbolCoverageQualification(BaseModel):
    symbol: str = Field(pattern=r"^[A-Z0-9]{5,20}$")
    month_count: Literal[24] = 24
    expected_minute_count: int = Field(gt=0)
    synchronized_minute_count: int = Field(ge=0)
    synchronized_coverage_fraction: Decimal = Field(ge=0, le=1)
    passing_month_count: int = Field(ge=0, le=24)
    maximum_consecutive_gap_minutes: int = Field(ge=0)
    funding_archive_count: int = Field(ge=0, le=24)
    current_spot_filter_proxy_pass: bool
    current_futures_filter_proxy_pass: bool
    qualification_pass: bool
    reason_codes: list[str]

    model_config = ConfigDict(extra="forbid")

    @field_validator("reason_codes")
    @classmethod
    def normalize_reasons(cls, value: list[str]) -> list[str]:
        normalized = sorted({item.strip() for item in value if item.strip()})
        if not set(normalized).issubset(V3_P01_SYMBOL_REASON_CODES):
            raise ValueError("V3P01 symbol reason changed")
        return normalized

    @model_validator(mode="after")
    def validate_qualification(self) -> V3P01SymbolCoverageQualification:
        expected_fraction = (
            Decimal(self.synchronized_minute_count)
            / Decimal(self.expected_minute_count)
        )
        if self.synchronized_coverage_fraction != expected_fraction:
            raise ValueError("V3P01 symbol coverage fraction does not reconcile")
        if self.qualification_pass != (not self.reason_codes):
            raise ValueError("V3P01 symbol qualification does not reconcile")
        return self


class V3P01CoverageSummary(BaseModel):
    symbol_count: Literal[31] = 31
    symbol_month_count: Literal[744] = 744
    synchronized_family_count: Literal[4] = 4
    verified_archive_reference_count: Literal[3720] = 3720
    expected_minute_count: int = Field(gt=0)
    synchronized_minute_count: int = Field(ge=0)
    missing_synchronized_minute_count: int = Field(ge=0)
    qualified_symbol_count: int = Field(ge=0, le=31)
    disqualified_symbol_count: int = Field(ge=0, le=31)
    qualified_symbols: list[str]
    disqualified_symbols: list[str]

    model_config = ConfigDict(extra="forbid")

    @field_validator("qualified_symbols", "disqualified_symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        return sorted({item.strip().upper() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_summary(self) -> V3P01CoverageSummary:
        if (
            self.missing_synchronized_minute_count
            != self.expected_minute_count - self.synchronized_minute_count
        ):
            raise ValueError("V3P01 summary minute counts do not reconcile")
        if (
            self.qualified_symbol_count + self.disqualified_symbol_count != 31
            or self.qualified_symbol_count != len(self.qualified_symbols)
            or self.disqualified_symbol_count != len(self.disqualified_symbols)
            or set(self.qualified_symbols) | set(self.disqualified_symbols)
            != set(V2_COMPLETE_SYMBOLS)
            or set(self.qualified_symbols) & set(self.disqualified_symbols)
        ):
            raise ValueError("V3P01 summary symbol partition changed")
        return self


class V3P01TimestampCoverageResult(BaseModel):
    schema_version: Literal[
        "aurex-v3-p01-timestamp-coverage-result-v1"
    ] = V3_P01_COVERAGE_RESULT_SCHEMA_VERSION
    result_id: Literal["v3-p01-timestamp-coverage-result-v1"] = (
        "v3-p01-timestamp-coverage-result-v1"
    )
    result_version: Literal["1.0.0"] = "1.0.0"
    generated_at: datetime
    status: Literal["COMPLETE_TIMESTAMP_ONLY_NO_RETURN_FEASIBILITY"] = (
        "COMPLETE_TIMESTAMP_ONLY_NO_RETURN_FEASIBILITY"
    )
    discovery_charter_evidence_hash: str
    proposal_register_evidence_hash: str
    p01_acquisition_result_evidence_hash: str
    runner_contract_hash: str
    proposal_id: Literal[
        "V3P01_CROSS_ASSET_COINTEGRATION_RELATIVE_VALUE"
    ] = "V3P01_CROSS_ASSET_COINTEGRATION_RELATIVE_VALUE"
    coverage_contract: V3ProposalCoverageContract
    month_records: list[V3P01MonthCoverageEvidence] = Field(
        min_length=744,
        max_length=744,
    )
    symbol_qualifications: list[V3P01SymbolCoverageQualification] = Field(
        min_length=31,
        max_length=31,
    )
    summary: V3P01CoverageSummary
    decision: Literal[
        "PERMIT_SEPARATE_V3P01_CROSS_ASSET_FOUNDATION_AND_METADATA_PROTOCOL",
        "REJECT_V3P01_INSUFFICIENT_SYNCHRONIZED_SOURCE_COVERAGE",
    ]
    authorizes_execution_foundation_and_metadata_protocol: bool
    market_numeric_values_inspected: list[str] = Field(default_factory=list)
    strategy_signals_calculated: Literal[False] = False
    trades_calculated: Literal[False] = False
    return_metrics_calculated: list[str] = Field(default_factory=list)
    selects_primary: Literal[False] = False
    creates_candidate: Literal[False] = False
    opens_validation: Literal[False] = False
    opens_holdout: Literal[False] = False
    opens_forward: Literal[False] = False
    permits_pine_parity: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_sandbox_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    limitations: list[str] = Field(min_length=6)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "discovery_charter_evidence_hash",
        "proposal_register_evidence_hash",
        "p01_acquisition_result_evidence_hash",
        "runner_contract_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "market_numeric_values_inspected",
        "return_metrics_calculated",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_result(self) -> V3P01TimestampCoverageResult:
        if self.month_records != sorted(
            self.month_records,
            key=lambda item: item.key,
        ):
            raise ValueError("V3P01 month records are not canonical")
        expected_keys = {
            (symbol, f"{year}-{month:02d}")
            for symbol in V2_COMPLETE_SYMBOLS
            for year in (2023, 2024)
            for month in range(1, 13)
        }
        if (
            len({record.key for record in self.month_records}) != 744
            or {record.key for record in self.month_records} != expected_keys
        ):
            raise ValueError("V3P01 symbol-month matrix changed")
        if [
            item.symbol for item in self.symbol_qualifications
        ] != sorted(V2_COMPLETE_SYMBOLS):
            raise ValueError("V3P01 qualification order changed")
        for record in self.month_records:
            expected_reasons = []
            if record.synchronized_coverage_fraction < (
                self.coverage_contract.minimum_calendar_month_coverage_fraction
            ):
                expected_reasons.append("MONTH_COVERAGE_BELOW_FLOOR")
            if record.maximum_consecutive_gap_minutes > (
                self.coverage_contract.maximum_single_gap_minutes
            ):
                expected_reasons.append("MAXIMUM_GAP_EXCEEDS_LIMIT")
            if record.reason_codes != sorted(expected_reasons):
                raise ValueError("V3P01 month reasons do not match contract")
        for qualification in self.symbol_qualifications:
            records = [
                item
                for item in self.month_records
                if item.symbol == qualification.symbol
            ]
            expected_minutes = sum(
                item.expected_minute_count for item in records
            )
            synchronized_minutes = sum(
                item.synchronized_minute_count for item in records
            )
            expected_reasons = []
            if qualification.synchronized_coverage_fraction < (
                self.coverage_contract.minimum_total_coverage_fraction
            ):
                expected_reasons.append("TOTAL_COVERAGE_BELOW_FLOOR")
            if not all(item.month_coverage_pass for item in records):
                expected_reasons.append("ONE_OR_MORE_MONTHS_FAIL")
            if qualification.funding_archive_count != 24:
                expected_reasons.append("FUNDING_ARCHIVE_MATRIX_INCOMPLETE")
            if not (
                qualification.current_spot_filter_proxy_pass
                and qualification.current_futures_filter_proxy_pass
            ):
                expected_reasons.append("CURRENT_FILTER_PROXY_FAIL")
            if (
                qualification.expected_minute_count != expected_minutes
                or qualification.synchronized_minute_count
                != synchronized_minutes
                or qualification.passing_month_count
                != sum(item.month_coverage_pass for item in records)
                or qualification.maximum_consecutive_gap_minutes
                != max(
                    item.maximum_consecutive_gap_minutes for item in records
                )
                or qualification.reason_codes != sorted(expected_reasons)
            ):
                raise ValueError(
                    "V3P01 symbol qualification does not match month evidence"
                )
        expected_total = sum(
            item.expected_minute_count for item in self.month_records
        )
        synchronized_total = sum(
            item.synchronized_minute_count for item in self.month_records
        )
        qualified_symbols = sorted(
            item.symbol
            for item in self.symbol_qualifications
            if item.qualification_pass
        )
        if (
            self.summary.expected_minute_count != expected_total
            or self.summary.synchronized_minute_count != synchronized_total
            or self.summary.qualified_symbols != qualified_symbols
        ):
            raise ValueError("V3P01 summary does not match coverage evidence")
        if self.market_numeric_values_inspected or self.return_metrics_calculated:
            raise ValueError("V3P01 coverage result may contain no outcomes")
        passed = (
            self.summary.qualified_symbol_count
            >= self.coverage_contract.minimum_qualified_symbols
        )
        expected_decision = (
            V3_P01_COVERAGE_PASS_DECISION
            if passed
            else V3_P01_COVERAGE_FAIL_DECISION
        )
        if (
            self.decision != expected_decision
            or self.authorizes_execution_foundation_and_metadata_protocol
            != passed
        ):
            raise ValueError("V3P01 result decision does not reconcile")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected_hash:
            raise ValueError("V3P01 result hash does not match")
        return self


def build_v3_p01_timestamp_coverage_result(
    **values,
) -> V3P01TimestampCoverageResult:
    payload = {
        "schema_version": V3_P01_COVERAGE_RESULT_SCHEMA_VERSION,
        "result_id": "v3-p01-timestamp-coverage-result-v1",
        "result_version": "1.0.0",
        "status": "COMPLETE_TIMESTAMP_ONLY_NO_RETURN_FEASIBILITY",
        "proposal_id": "V3P01_CROSS_ASSET_COINTEGRATION_RELATIVE_VALUE",
        "market_numeric_values_inspected": [],
        "strategy_signals_calculated": False,
        "trades_calculated": False,
        "return_metrics_calculated": [],
        "selects_primary": False,
        "creates_candidate": False,
        "opens_validation": False,
        "opens_holdout": False,
        "opens_forward": False,
        "permits_pine_parity": False,
        "creates_paper_eligibility": False,
        "creates_sandbox_eligibility": False,
        "creates_live_eligibility": False,
        **values,
    }
    payload["month_records"] = sorted(
        payload["month_records"],
        key=lambda item: item.key,
    )
    payload["symbol_qualifications"] = sorted(
        payload["symbol_qualifications"],
        key=lambda item: item.symbol,
    )
    payload["limitations"] = sorted(set(payload["limitations"]))
    passed = (
        payload["summary"].qualified_symbol_count
        >= payload["coverage_contract"].minimum_qualified_symbols
    )
    payload["decision"] = (
        V3_P01_COVERAGE_PASS_DECISION
        if passed
        else V3_P01_COVERAGE_FAIL_DECISION
    )
    payload["authorizes_execution_foundation_and_metadata_protocol"] = passed
    return V3P01TimestampCoverageResult(
        **payload,
        result_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v3_p01_timestamp_coverage_result(
    result: V3P01TimestampCoverageResult,
) -> bool:
    return result.result_evidence_hash == universe_evidence_hash(
        result.model_dump(exclude={"result_evidence_hash"})
    )
