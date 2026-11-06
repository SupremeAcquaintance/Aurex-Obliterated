from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.jam_archive_full_acquisition import JAM_FULL_MONTHS
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

JAM_QUALITY_PROTOCOL_SCHEMA_VERSION = (
    "aurex-jam-archive-quality-remediation-protocol-v1"
)
JAM_QUALITY_RESULT_SCHEMA_VERSION = (
    "aurex-jam-archive-quality-remediation-result-v1"
)
JAM_QUALITY_AUDIT_SCHEMA_VERSION = (
    "aurex-jam-archive-quality-remediation-audit-v1"
)
JAM_QUALITY_PASS_DECISION = (
    "PASS_AGGTRADES_PRIMARY_SOURCE_POLICY_AWAIT_NO_RETURN_FEATURE_SPECIFICATION"
)
JAM_QUALITY_FAIL_DECISION = "STOP_JAM_SUCCESSOR_SOURCE_REMEDIATION_FAILED"
JAM_QUALITY_NEXT_AUTHORIZATION = (
    "AUTHORIZE_JAM_SUCCESSOR_FEATURE_SPECIFICATION_NO_RETURNS"
)
JAM_QUALITY_NO_NEXT_AUTHORIZATION = "NONE_REMEDIATION_FAILED"
JAM_QUALITY_TOLERANCE = "0.00000001"
JAM_QUALITY_MAXIMUM_ISSUE_RECORDS = 10_000
JAM_QUALITY_DIMENSIONS = (
    "BASE_VOLUME",
    "OHLC",
    "QUOTE_VOLUME",
    "RAW_TRADE_COUNT",
    "TAKER_BUY_BASE_VOLUME",
    "TAKER_BUY_QUOTE_VOLUME",
)
JAM_QUALITY_ROW_REASON_CODES = (
    "CLOSE_TIME_MISMATCH",
    "HIGH_BOUND_FAILED",
    "LOW_BOUND_FAILED",
    "NEGATIVE_TRADE_COUNT",
    "NEGATIVE_VOLUME",
    "NONPOSITIVE_PRICE",
    "TAKER_BASE_EXCEEDS_BASE",
    "TAKER_QUOTE_EXCEEDS_QUOTE",
)


def _decimal_string(value: str) -> str:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Jam quality decimal value is invalid") from exc
    if not parsed.is_finite():
        raise ValueError("Jam quality decimal value must be finite")
    return format(parsed, "f")


class JamQualityEvidencePartition(BaseModel):
    partition_id: Literal[
        "JAM_DEVELOPMENT_2019_2020",
        "JAM_SEALED_VALIDATION_2021",
        "JAM_SEALED_HOLDOUT_2022",
    ]
    start_month: str = Field(pattern=r"^20(19|20|21|22)-(0[1-9]|1[0-2])$")
    end_month: str = Field(pattern=r"^20(19|20|21|22)-(0[1-9]|1[0-2])$")
    role: Literal["DEVELOPMENT", "SEALED_VALIDATION", "SEALED_HOLDOUT"]
    outcome_access_permitted: Literal[False] = False

    model_config = ConfigDict(extra="forbid")


class JamArchiveQualityProtocol(BaseModel):
    schema_version: Literal[
        "aurex-jam-archive-quality-remediation-protocol-v1"
    ] = JAM_QUALITY_PROTOCOL_SCHEMA_VERSION
    protocol_id: Literal["jam-archive-quality-remediation-v1"] = (
        "jam-archive-quality-remediation-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_PRE_DEFECT_INSPECTION"] = (
        "FROZEN_PRE_DEFECT_INSPECTION"
    )
    authorization_record: Literal[
        "USER_AUTHORIZED_JAM_ARCHIVE_QUALITY_REMEDIATION_DESIGN_NO_RETURNS"
    ] = "USER_AUTHORIZED_JAM_ARCHIVE_QUALITY_REMEDIATION_DESIGN_NO_RETURNS"
    parent_protocol_path: Literal[
        "data/evidence/jam_archive_full_acquisition_protocol_v1.json"
    ] = "data/evidence/jam_archive_full_acquisition_protocol_v1.json"
    parent_result_path: Literal[
        "data/evidence/jam_archive_full_acquisition_result_v1.json"
    ] = "data/evidence/jam_archive_full_acquisition_result_v1.json"
    parent_audit_path: Literal[
        "data/evidence/jam_archive_full_acquisition_audit_v1.json"
    ] = "data/evidence/jam_archive_full_acquisition_audit_v1.json"
    parent_protocol_file_sha256: str
    parent_protocol_evidence_hash: str
    parent_result_file_sha256: str
    parent_result_evidence_hash: str
    parent_audit_file_sha256: str
    parent_audit_evidence_hash: str
    raw_manifest_hash: str
    builder_contract_hash: str
    months: list[str] = Field(min_length=48, max_length=48)
    inspected_quality_dimensions: list[str] = Field(
        min_length=6,
        max_length=6,
    )
    evidence_partitions: list[JamQualityEvidencePartition] = Field(
        min_length=3,
        max_length=3,
    )
    primary_source_candidate: Literal[
        "BINANCE_SPOT_MONTHLY_AGGTRADES"
    ] = "BINANCE_SPOT_MONTHLY_AGGTRADES"
    secondary_quality_source: Literal[
        "BINANCE_SPOT_MONTHLY_KLINES_1M_QA_ONLY"
    ] = "BINANCE_SPOT_MONTHLY_KLINES_1M_QA_ONLY"
    duplicate_member_question: Literal[
        "BYTE_IDENTICAL_OR_FAIL"
    ] = "BYTE_IDENTICAL_OR_FAIL"
    kline_gap_question: Literal[
        "ENUMERATE_AND_QUARANTINE_NO_SYNTHESIS"
    ] = "ENUMERATE_AND_QUARANTINE_NO_SYNTHESIS"
    kline_row_question: Literal[
        "ENUMERATE_AND_QUARANTINE"
    ] = "ENUMERATE_AND_QUARANTINE"
    cross_family_question: Literal[
        "ENUMERATE_ALL_MISMATCH_MINUTES_AND_DIMENSIONS"
    ] = "ENUMERATE_ALL_MISMATCH_MINUTES_AND_DIMENSIONS"
    state_recovery_question: Literal[
        "RESET_AND_REQUIRE_MAXIMUM_FUTURE_FEATURE_LOOKBACK"
    ] = "RESET_AND_REQUIRE_MAXIMUM_FUTURE_FEATURE_LOOKBACK"
    decimal_reconciliation_tolerance: Literal[
        "0.00000001"
    ] = JAM_QUALITY_TOLERANCE
    maximum_issue_records: Literal[10000] = JAM_QUALITY_MAXIMUM_ISSUE_RECORDS
    network_access_permitted: Literal[False] = False
    market_values_permitted_for_quality_validation: Literal[True] = True
    feature_calculation_permitted: Literal[False] = False
    parameter_definition_permitted: Literal[False] = False
    threshold_definition_permitted: Literal[False] = False
    return_calculation_permitted: Literal[False] = False
    strategy_execution_permitted: Literal[False] = False
    candidate_creation_permitted: Literal[False] = False
    paper_eligibility_permitted: Literal[False] = False
    testnet_strategy_orders_permitted: Literal[False] = False
    production_permitted: Literal[False] = False
    live_permitted: Literal[False] = False
    limitations: list[str] = Field(min_length=12)
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
        "raw_manifest_hash",
        "builder_contract_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("months", "inspected_quality_dimensions", "limitations")
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_protocol(self) -> JamArchiveQualityProtocol:
        expected_partitions = [
            JamQualityEvidencePartition(
                partition_id="JAM_DEVELOPMENT_2019_2020",
                start_month="2019-01",
                end_month="2020-12",
                role="DEVELOPMENT",
            ),
            JamQualityEvidencePartition(
                partition_id="JAM_SEALED_VALIDATION_2021",
                start_month="2021-01",
                end_month="2021-12",
                role="SEALED_VALIDATION",
            ),
            JamQualityEvidencePartition(
                partition_id="JAM_SEALED_HOLDOUT_2022",
                start_month="2022-01",
                end_month="2022-12",
                role="SEALED_HOLDOUT",
            ),
        ]
        if (
            self.months != list(JAM_FULL_MONTHS)
            or self.inspected_quality_dimensions
            != list(JAM_QUALITY_DIMENSIONS)
            or self.evidence_partitions != expected_partitions
        ):
            raise ValueError("Jam quality frozen inspection matrix changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected_hash:
            raise ValueError("Jam quality protocol hash does not match")
        return self


class JamDuplicateMemberEvidence(BaseModel):
    month: Literal["2021-12"] = "2021-12"
    archive_path: str
    archive_sha256: str
    canonical_member_name: Literal[
        "BTCUSDT-aggTrades-2021-12.csv"
    ] = "BTCUSDT-aggTrades-2021-12.csv"
    duplicate_member_name: str
    canonical_member_bytes: int = Field(gt=0)
    duplicate_member_bytes: int = Field(gt=0)
    canonical_member_sha256: str
    duplicate_member_sha256: str
    byte_identical: bool
    policy_pass: bool

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "archive_sha256",
        "canonical_member_sha256",
        "duplicate_member_sha256",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_duplicate(self) -> JamDuplicateMemberEvidence:
        passed = (
            self.duplicate_member_name != self.canonical_member_name
            and self.canonical_member_bytes == self.duplicate_member_bytes
            and self.canonical_member_sha256 == self.duplicate_member_sha256
            and self.byte_identical
        )
        if self.policy_pass != passed:
            raise ValueError("Jam duplicate-member decision does not reconcile")
        return self


class JamKlineGapInterval(BaseModel):
    month: str = Field(pattern=r"^20(19|20|21|22)-(0[1-9]|1[0-2])$")
    start_open_time_ms: int = Field(gt=0)
    end_open_time_ms: int = Field(gt=0)
    missing_minute_count: int = Field(gt=0)
    preceding_open_time_ms: int | None = Field(default=None, gt=0)
    following_open_time_ms: int | None = Field(default=None, gt=0)
    aggregate_covered_minute_count: Literal[0] = 0
    classification: Literal[
        "PAIRED_SOURCE_OBSERVABILITY_GAP"
    ] = "PAIRED_SOURCE_OBSERVABILITY_GAP"
    disposition: Literal[
        "QUARANTINE_NO_SYNTHETIC_TRADABLE_BAR"
    ] = "QUARANTINE_NO_SYNTHETIC_TRADABLE_BAR"

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_interval(self) -> JamKlineGapInterval:
        if (
            self.end_open_time_ms < self.start_open_time_ms
            or (self.end_open_time_ms - self.start_open_time_ms) % 60_000
            or (self.end_open_time_ms - self.start_open_time_ms) // 60_000 + 1
            != self.missing_minute_count
        ):
            raise ValueError("Jam quality kline gap interval changed")
        return self

    @property
    def key(self) -> tuple[str, int]:
        return self.month, self.start_open_time_ms


class JamKlineRowDefect(BaseModel):
    month: str = Field(pattern=r"^20(19|20|21|22)-(0[1-9]|1[0-2])$")
    open_time_ms: int = Field(gt=0)
    reason_codes: list[str] = Field(min_length=1)
    observed_close_time_ms: int
    expected_close_time_ms: int = Field(gt=0)
    disposition: Literal["QUARANTINE_MINUTE"] = "QUARANTINE_MINUTE"

    model_config = ConfigDict(extra="forbid")

    @field_validator("reason_codes")
    @classmethod
    def normalize_reasons(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_defect(self) -> JamKlineRowDefect:
        if (
            self.expected_close_time_ms != self.open_time_ms + 59_999
            or not set(self.reason_codes).issubset(JAM_QUALITY_ROW_REASON_CODES)
        ):
            raise ValueError("Jam quality kline row defect changed")
        return self

    @property
    def key(self) -> tuple[str, int]:
        return self.month, self.open_time_ms


class JamMinuteValues(BaseModel):
    open_price: str | None = None
    high_price: str | None = None
    low_price: str | None = None
    close_price: str | None = None
    base_volume: str
    quote_volume: str
    raw_trade_count: int = Field(ge=0)
    taker_buy_base_volume: str
    taker_buy_quote_volume: str

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "base_volume",
        "quote_volume",
        "taker_buy_base_volume",
        "taker_buy_quote_volume",
    )
    @classmethod
    def normalize_decimals(cls, value: str | None) -> str | None:
        return None if value is None else _decimal_string(value)

    @model_validator(mode="after")
    def validate_values(self) -> JamMinuteValues:
        prices = (
            self.open_price,
            self.high_price,
            self.low_price,
            self.close_price,
        )
        if any(item is None for item in prices) and any(
            item is not None for item in prices
        ):
            raise ValueError("Jam quality OHLC must be all present or all absent")
        return self


class JamCrossFamilyMismatch(BaseModel):
    month: str = Field(pattern=r"^20(19|20|21|22)-(0[1-9]|1[0-2])$")
    open_time_ms: int = Field(gt=0)
    mismatch_dimensions: list[str] = Field(min_length=1, max_length=6)
    aggregate_values: JamMinuteValues | None
    kline_values: JamMinuteValues
    disposition: Literal[
        "QUARANTINE_MINUTE_RESET_STATE"
    ] = "QUARANTINE_MINUTE_RESET_STATE"

    model_config = ConfigDict(extra="forbid")

    @field_validator("mismatch_dimensions")
    @classmethod
    def normalize_dimensions(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_mismatch(self) -> JamCrossFamilyMismatch:
        if not set(self.mismatch_dimensions).issubset(JAM_QUALITY_DIMENSIONS):
            raise ValueError("Jam quality mismatch dimension changed")
        return self

    @property
    def key(self) -> tuple[str, int]:
        return self.month, self.open_time_ms


class JamArchiveQualityResult(BaseModel):
    schema_version: Literal[
        "aurex-jam-archive-quality-remediation-result-v1"
    ] = JAM_QUALITY_RESULT_SCHEMA_VERSION
    result_id: Literal["jam-archive-quality-remediation-result-v1"] = (
        "jam-archive-quality-remediation-result-v1"
    )
    generated_at: datetime
    status: Literal["COMPLETE_SOURCE_REMEDIATION_NO_RETURNS"] = (
        "COMPLETE_SOURCE_REMEDIATION_NO_RETURNS"
    )
    protocol_evidence_hash: str
    runner_contract_hash: str
    parent_result_evidence_hash: str
    parent_audit_evidence_hash: str
    duplicate_member: JamDuplicateMemberEvidence
    kline_gap_intervals: list[JamKlineGapInterval]
    kline_row_defects: list[JamKlineRowDefect]
    cross_family_mismatches: list[JamCrossFamilyMismatch]
    kline_missing_minute_count: int = Field(ge=0)
    kline_gap_interval_count: int = Field(ge=0)
    kline_row_defect_count: int = Field(ge=0)
    cross_family_mismatch_minute_count: int = Field(ge=0)
    mismatch_dimension_counts: dict[str, int]
    quarantined_minute_count: int = Field(ge=0)
    quarantined_minute_manifest_hash: str
    issue_manifest_hash: str
    aggregate_primary_source_qualified: bool
    official_kline_secondary_qa_qualified: Literal[True] = True
    primary_source: Literal[
        "BINANCE_SPOT_MONTHLY_AGGTRADES"
    ] = "BINANCE_SPOT_MONTHLY_AGGTRADES"
    secondary_source: Literal[
        "BINANCE_SPOT_MONTHLY_KLINES_1M_QA_ONLY"
    ] = "BINANCE_SPOT_MONTHLY_KLINES_1M_QA_ONLY"
    missing_minute_policy: Literal[
        "QUARANTINE_NO_SYNTHETIC_TRADABLE_BAR"
    ] = "QUARANTINE_NO_SYNTHETIC_TRADABLE_BAR"
    mismatch_policy: Literal[
        "QUARANTINE_MINUTE_RESET_STATE"
    ] = "QUARANTINE_MINUTE_RESET_STATE"
    duplicate_member_policy: Literal[
        "TOP_LEVEL_CANONICAL_ONLY_WHEN_BYTE_IDENTICAL"
    ] = "TOP_LEVEL_CANONICAL_ONLY_WHEN_BYTE_IDENTICAL"
    future_state_recovery_policy: Literal[
        "RESET_AT_DEFECT_REQUIRE_MAXIMUM_FEATURE_LOOKBACK_WARMUP"
    ] = "RESET_AT_DEFECT_REQUIRE_MAXIMUM_FEATURE_LOOKBACK_WARMUP"
    evidence_partitions: list[JamQualityEvidencePartition] = Field(
        min_length=3,
        max_length=3,
    )
    contaminated_or_excluded_periods: list[str] = Field(min_length=2)
    decision: Literal[
        "PASS_AGGTRADES_PRIMARY_SOURCE_POLICY_AWAIT_NO_RETURN_FEATURE_SPECIFICATION",
        "STOP_JAM_SUCCESSOR_SOURCE_REMEDIATION_FAILED",
    ]
    next_required_authorization: Literal[
        "AUTHORIZE_JAM_SUCCESSOR_FEATURE_SPECIFICATION_NO_RETURNS",
        "NONE_REMEDIATION_FAILED",
    ]
    feature_fields_created: list[str] = Field(default_factory=list)
    parameters_defined: list[str] = Field(default_factory=list)
    thresholds_defined: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)
    strategy_executions: Literal[0] = 0
    creates_candidate: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_testnet_order_authority: Literal[False] = False
    creates_production_authority: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    limitations: list[str] = Field(min_length=12)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_evidence_hash",
        "runner_contract_hash",
        "parent_result_evidence_hash",
        "parent_audit_evidence_hash",
        "quarantined_minute_manifest_hash",
        "issue_manifest_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "contaminated_or_excluded_periods",
        "feature_fields_created",
        "parameters_defined",
        "thresholds_defined",
        "return_metrics_calculated",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_result(self) -> JamArchiveQualityResult:
        if (
            self.kline_gap_intervals
            != sorted(self.kline_gap_intervals, key=lambda item: item.key)
            or self.kline_row_defects
            != sorted(self.kline_row_defects, key=lambda item: item.key)
            or self.cross_family_mismatches
            != sorted(self.cross_family_mismatches, key=lambda item: item.key)
            or len({item.key for item in self.kline_row_defects})
            != len(self.kline_row_defects)
            or len({item.key for item in self.cross_family_mismatches})
            != len(self.cross_family_mismatches)
        ):
            raise ValueError("Jam quality issue ordering or identity changed")
        if (
            self.kline_missing_minute_count
            != sum(item.missing_minute_count for item in self.kline_gap_intervals)
            or self.kline_gap_interval_count != len(self.kline_gap_intervals)
            or self.kline_row_defect_count != len(self.kline_row_defects)
            or self.cross_family_mismatch_minute_count
            != len(self.cross_family_mismatches)
        ):
            raise ValueError("Jam quality issue totals do not reconcile")
        expected_dimension_counts = {
            dimension: sum(
                dimension in item.mismatch_dimensions
                for item in self.cross_family_mismatches
            )
            for dimension in JAM_QUALITY_DIMENSIONS
        }
        if self.mismatch_dimension_counts != expected_dimension_counts:
            raise ValueError("Jam quality mismatch counts do not reconcile")
        issue_payload = {
            "duplicate_member": self.duplicate_member.model_dump(),
            "kline_gap_intervals": [
                item.model_dump() for item in self.kline_gap_intervals
            ],
            "kline_row_defects": [
                item.model_dump() for item in self.kline_row_defects
            ],
            "cross_family_mismatches": [
                item.model_dump() for item in self.cross_family_mismatches
            ],
        }
        if self.issue_manifest_hash != universe_evidence_hash(issue_payload):
            raise ValueError("Jam quality issue manifest changed")
        quarantined = {
            (item.month, minute)
            for item in self.kline_gap_intervals
            for minute in range(
                item.start_open_time_ms,
                item.end_open_time_ms + 60_000,
                60_000,
            )
        }
        quarantined.update(
            (item.month, item.open_time_ms) for item in self.kline_row_defects
        )
        quarantined.update(
            (item.month, item.open_time_ms)
            for item in self.cross_family_mismatches
        )
        quarantine_payload = [
            {"month": month, "open_time_ms": open_time}
            for month, open_time in sorted(quarantined)
        ]
        if (
            self.quarantined_minute_count != len(quarantine_payload)
            or self.quarantined_minute_manifest_hash
            != universe_evidence_hash({"minutes": quarantine_payload})
        ):
            raise ValueError("Jam quality quarantine manifest changed")
        passed = self.aggregate_primary_source_qualified
        if (
            self.decision
            != (JAM_QUALITY_PASS_DECISION if passed else JAM_QUALITY_FAIL_DECISION)
            or self.next_required_authorization
            != (
                JAM_QUALITY_NEXT_AUTHORIZATION
                if passed
                else JAM_QUALITY_NO_NEXT_AUTHORIZATION
            )
        ):
            raise ValueError("Jam quality decision changed")
        if (
            self.feature_fields_created
            or self.parameters_defined
            or self.thresholds_defined
            or self.return_metrics_calculated
        ):
            raise ValueError("Jam quality remediation may contain no outcomes")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected_hash:
            raise ValueError("Jam quality result hash does not match")
        return self


class JamArchiveQualityAudit(BaseModel):
    schema_version: Literal[
        "aurex-jam-archive-quality-remediation-audit-v1"
    ] = JAM_QUALITY_AUDIT_SCHEMA_VERSION
    audited_at: datetime
    protocol_path: str
    protocol_file_sha256: str
    protocol_evidence_hash: str
    result_path: str
    result_file_sha256: str
    result_evidence_hash: str
    duplicate_member_reconstructed: Literal[True] = True
    kline_month_count_reconstructed: Literal[48] = 48
    mismatch_month_count_reconstructed: int = Field(ge=0, le=48)
    issue_manifest_hash: str
    quarantined_minute_manifest_hash: str
    return_metrics_calculated: Literal[False] = False
    decision: Literal[
        "PASS_AGGTRADES_PRIMARY_SOURCE_POLICY_AWAIT_NO_RETURN_FEATURE_SPECIFICATION",
        "STOP_JAM_SUCCESSOR_SOURCE_REMEDIATION_FAILED",
    ]
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "result_file_sha256",
        "result_evidence_hash",
        "issue_manifest_hash",
        "quarantined_minute_manifest_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> JamArchiveQualityAudit:
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected_hash:
            raise ValueError("Jam quality audit hash does not match")
        return self


def build_jam_archive_quality_protocol(**values) -> JamArchiveQualityProtocol:
    payload = {
        "schema_version": JAM_QUALITY_PROTOCOL_SCHEMA_VERSION,
        "protocol_id": "jam-archive-quality-remediation-v1",
        "status": "FROZEN_PRE_DEFECT_INSPECTION",
        "authorization_record": (
            "USER_AUTHORIZED_JAM_ARCHIVE_QUALITY_REMEDIATION_DESIGN_NO_RETURNS"
        ),
        "parent_protocol_path": (
            "data/evidence/jam_archive_full_acquisition_protocol_v1.json"
        ),
        "parent_result_path": (
            "data/evidence/jam_archive_full_acquisition_result_v1.json"
        ),
        "parent_audit_path": (
            "data/evidence/jam_archive_full_acquisition_audit_v1.json"
        ),
        "months": list(JAM_FULL_MONTHS),
        "inspected_quality_dimensions": list(JAM_QUALITY_DIMENSIONS),
        "evidence_partitions": [
            JamQualityEvidencePartition(
                partition_id="JAM_DEVELOPMENT_2019_2020",
                start_month="2019-01",
                end_month="2020-12",
                role="DEVELOPMENT",
            ),
            JamQualityEvidencePartition(
                partition_id="JAM_SEALED_VALIDATION_2021",
                start_month="2021-01",
                end_month="2021-12",
                role="SEALED_VALIDATION",
            ),
            JamQualityEvidencePartition(
                partition_id="JAM_SEALED_HOLDOUT_2022",
                start_month="2022-01",
                end_month="2022-12",
                role="SEALED_HOLDOUT",
            ),
        ],
        "primary_source_candidate": "BINANCE_SPOT_MONTHLY_AGGTRADES",
        "secondary_quality_source": "BINANCE_SPOT_MONTHLY_KLINES_1M_QA_ONLY",
        "duplicate_member_question": "BYTE_IDENTICAL_OR_FAIL",
        "kline_gap_question": "ENUMERATE_AND_QUARANTINE_NO_SYNTHESIS",
        "kline_row_question": "ENUMERATE_AND_QUARANTINE",
        "cross_family_question": (
            "ENUMERATE_ALL_MISMATCH_MINUTES_AND_DIMENSIONS"
        ),
        "state_recovery_question": (
            "RESET_AND_REQUIRE_MAXIMUM_FUTURE_FEATURE_LOOKBACK"
        ),
        "decimal_reconciliation_tolerance": JAM_QUALITY_TOLERANCE,
        "maximum_issue_records": JAM_QUALITY_MAXIMUM_ISSUE_RECORDS,
        "network_access_permitted": False,
        "market_values_permitted_for_quality_validation": True,
        "feature_calculation_permitted": False,
        "parameter_definition_permitted": False,
        "threshold_definition_permitted": False,
        "return_calculation_permitted": False,
        "strategy_execution_permitted": False,
        "candidate_creation_permitted": False,
        "paper_eligibility_permitted": False,
        "testnet_strategy_orders_permitted": False,
        "production_permitted": False,
        "live_permitted": False,
        **values,
    }
    payload["limitations"] = sorted(set(payload["limitations"]))
    return JamArchiveQualityProtocol(
        **payload,
        protocol_evidence_hash=universe_evidence_hash(payload),
    )


def build_jam_archive_quality_result(**values) -> JamArchiveQualityResult:
    gaps = sorted(values.pop("kline_gap_intervals"), key=lambda item: item.key)
    row_defects = sorted(
        values.pop("kline_row_defects"),
        key=lambda item: item.key,
    )
    mismatches = sorted(
        values.pop("cross_family_mismatches"),
        key=lambda item: item.key,
    )
    duplicate = values.pop("duplicate_member")
    dimensions = {
        dimension: sum(
            dimension in item.mismatch_dimensions for item in mismatches
        )
        for dimension in JAM_QUALITY_DIMENSIONS
    }
    quarantined = {
        (item.month, minute)
        for item in gaps
        for minute in range(
            item.start_open_time_ms,
            item.end_open_time_ms + 60_000,
            60_000,
        )
    }
    quarantined.update((item.month, item.open_time_ms) for item in row_defects)
    quarantined.update((item.month, item.open_time_ms) for item in mismatches)
    quarantine_payload = [
        {"month": month, "open_time_ms": open_time}
        for month, open_time in sorted(quarantined)
    ]
    issue_payload = {
        "duplicate_member": duplicate.model_dump(),
        "kline_gap_intervals": [item.model_dump() for item in gaps],
        "kline_row_defects": [item.model_dump() for item in row_defects],
        "cross_family_mismatches": [
            item.model_dump() for item in mismatches
        ],
    }
    qualified = values["aggregate_primary_source_qualified"]
    payload = {
        "schema_version": JAM_QUALITY_RESULT_SCHEMA_VERSION,
        "result_id": "jam-archive-quality-remediation-result-v1",
        "status": "COMPLETE_SOURCE_REMEDIATION_NO_RETURNS",
        "duplicate_member": duplicate,
        "kline_gap_intervals": gaps,
        "kline_row_defects": row_defects,
        "cross_family_mismatches": mismatches,
        "kline_missing_minute_count": sum(
            item.missing_minute_count for item in gaps
        ),
        "kline_gap_interval_count": len(gaps),
        "kline_row_defect_count": len(row_defects),
        "cross_family_mismatch_minute_count": len(mismatches),
        "mismatch_dimension_counts": dimensions,
        "quarantined_minute_count": len(quarantine_payload),
        "quarantined_minute_manifest_hash": universe_evidence_hash(
            {"minutes": quarantine_payload}
        ),
        "issue_manifest_hash": universe_evidence_hash(issue_payload),
        "official_kline_secondary_qa_qualified": True,
        "primary_source": "BINANCE_SPOT_MONTHLY_AGGTRADES",
        "secondary_source": "BINANCE_SPOT_MONTHLY_KLINES_1M_QA_ONLY",
        "missing_minute_policy": "QUARANTINE_NO_SYNTHETIC_TRADABLE_BAR",
        "mismatch_policy": "QUARANTINE_MINUTE_RESET_STATE",
        "duplicate_member_policy": (
            "TOP_LEVEL_CANONICAL_ONLY_WHEN_BYTE_IDENTICAL"
        ),
        "future_state_recovery_policy": (
            "RESET_AT_DEFECT_REQUIRE_MAXIMUM_FEATURE_LOOKBACK_WARMUP"
        ),
        "decision": (
            JAM_QUALITY_PASS_DECISION
            if qualified
            else JAM_QUALITY_FAIL_DECISION
        ),
        "next_required_authorization": (
            JAM_QUALITY_NEXT_AUTHORIZATION
            if qualified
            else JAM_QUALITY_NO_NEXT_AUTHORIZATION
        ),
        "feature_fields_created": [],
        "parameters_defined": [],
        "thresholds_defined": [],
        "return_metrics_calculated": [],
        "strategy_executions": 0,
        "creates_candidate": False,
        "creates_paper_eligibility": False,
        "creates_testnet_order_authority": False,
        "creates_production_authority": False,
        "creates_live_eligibility": False,
        **values,
    }
    payload["contaminated_or_excluded_periods"] = sorted(
        set(payload["contaminated_or_excluded_periods"])
    )
    payload["limitations"] = sorted(set(payload["limitations"]))
    return JamArchiveQualityResult(
        **payload,
        result_evidence_hash=universe_evidence_hash(payload),
    )


def build_jam_archive_quality_audit(**values) -> JamArchiveQualityAudit:
    payload = {
        "schema_version": JAM_QUALITY_AUDIT_SCHEMA_VERSION,
        "duplicate_member_reconstructed": True,
        "kline_month_count_reconstructed": 48,
        "return_metrics_calculated": False,
        **values,
    }
    return JamArchiveQualityAudit(
        **payload,
        audit_evidence_hash=universe_evidence_hash(payload),
    )


def audit_jam_archive_quality_protocol(
    protocol: JamArchiveQualityProtocol,
) -> bool:
    try:
        JamArchiveQualityProtocol.model_validate(protocol.model_dump())
    except ValueError:
        return False
    return True


def audit_jam_archive_quality_result(
    result: JamArchiveQualityResult,
) -> bool:
    try:
        JamArchiveQualityResult.model_validate(result.model_dump())
    except ValueError:
        return False
    return True


def audit_jam_archive_quality_audit(
    audit: JamArchiveQualityAudit,
) -> bool:
    try:
        JamArchiveQualityAudit.model_validate(audit.model_dump())
    except ValueError:
        return False
    return True
