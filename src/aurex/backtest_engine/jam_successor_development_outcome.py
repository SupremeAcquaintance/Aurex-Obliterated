from __future__ import annotations

import hashlib
from bisect import bisect_left, insort
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.jam_successor_distribution_protocol import (
    JAM_DISTRIBUTION_MONTHS,
    JamDevelopmentArchiveTarget,
)
from aurex.backtest_engine.jam_successor_event_outcome_protocol import (
    JAM_DEVELOPMENT_OUTCOME_GATE_SPECS,
    JamProtocolGate,
)
from aurex.backtest_engine.jam_successor_event_prevalence import (
    JAM_PREVALENCE_QUARTERS,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

JAM_OUTCOME_PROTOCOL_SCHEMA_VERSION = (
    "aurex-jam-successor-development-outcome-execution-protocol-v1"
)
JAM_OUTCOME_RESULT_SCHEMA_VERSION = (
    "aurex-jam-successor-development-outcome-result-v1"
)
JAM_OUTCOME_AUDIT_SCHEMA_VERSION = (
    "aurex-jam-successor-development-outcome-audit-v1"
)
JAM_OUTCOME_AUTHORIZATION_RECORD = (
    "USER_CONFIRMED_PROCEED_WITH_FROZEN_DEVELOPMENT_OUTCOME_STAGE"
)
JAM_OUTCOME_AUTHORIZATION_SCOPE = (
    "AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_CALCULATION"
)
JAM_OUTCOME_PASS_DECISION = (
    "PASS_DEVELOPMENT_OUTCOMES_AWAIT_SEALED_2021_VALIDATION_AUTHORIZATION"
)
JAM_OUTCOME_FAIL_DECISION = "STOP_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_FAILED"
JAM_OUTCOME_NEXT_AUTHORIZATION = (
    "AUTHORIZE_JAM_SUCCESSOR_SEALED_2021_VALIDATION"
)
JAM_OUTCOME_NO_NEXT_AUTHORIZATION = "NONE_DEVELOPMENT_OUTCOME_FAILED"
JAM_OUTCOME_CONTROL_LEDGER_PATH = (
    "data/evidence/jam_successor_development_matched_control_ledger_v1.jsonl"
)
JAM_OUTCOME_LEDGER_PATH = (
    "data/evidence/jam_successor_development_outcome_ledger_v1.jsonl"
)
JAM_OUTCOME_HORIZONS = (15, 30, 60)
JAM_OUTCOME_DECIMAL_QUANTUM = Decimal("0.000000000000000001")
JAM_OUTCOME_TICK_SIZE = Decimal("0.01")
JAM_OUTCOME_BASE_FEE = Decimal("0.0010")
JAM_OUTCOME_STRESS_FEE = Decimal("0.0015")
JAM_OUTCOME_BASE_TICKS = 2
JAM_OUTCOME_STRESS_TICKS = 10
JAM_OUTCOME_BOOTSTRAP_REPETITIONS = 10_000
JAM_OUTCOME_BOOTSTRAP_SEED = 20_260_805
JAM_OUTCOME_BOOTSTRAP_LOWER_ORDER_INDEX = 499
JAM_OUTCOME_DEVELOPMENT_START_MS = 1_546_300_800_000
JAM_OUTCOME_DEVELOPMENT_END_EXCLUSIVE_MS = 1_609_459_200_000


def normalize_decimal_string(
    value: str | Decimal,
    *,
    allow_positive_infinity: bool = False,
) -> str:
    if allow_positive_infinity and value == "POSITIVE_INFINITY":
        return "POSITIVE_INFINITY"
    try:
        parsed = Decimal(value)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("Jam outcome decimal is invalid") from exc
    if not parsed.is_finite():
        raise ValueError("Jam outcome decimal must be finite")
    return format(parsed, "f")


def quantize_outcome(value: Decimal) -> Decimal:
    return value.quantize(JAM_OUTCOME_DECIMAL_QUANTUM, rounding=ROUND_HALF_EVEN)


def _evaluate_comparison(
    *,
    observed: str,
    comparison: str,
    threshold: str,
) -> bool:
    if observed == "POSITIVE_INFINITY":
        return comparison in {
            "GREATER_THAN_OR_EQUAL",
            "GREATER_THAN",
        }
    observed_decimal = Decimal(observed)
    threshold_decimal = Decimal(threshold)
    if comparison == "GREATER_THAN_OR_EQUAL":
        return observed_decimal >= threshold_decimal
    if comparison == "LESS_THAN_OR_EQUAL":
        return observed_decimal <= threshold_decimal
    if comparison == "GREATER_THAN":
        return observed_decimal > threshold_decimal
    if comparison == "EQUAL":
        return observed_decimal == threshold_decimal
    raise ValueError("Jam outcome gate comparison changed")


class JamSuccessorDevelopmentOutcomeExecutionProtocol(BaseModel):
    schema_version: Literal[
        "aurex-jam-successor-development-outcome-execution-protocol-v1"
    ] = JAM_OUTCOME_PROTOCOL_SCHEMA_VERSION
    protocol_id: Literal[
        "jam-successor-development-outcome-execution-protocol-v1"
    ] = "jam-successor-development-outcome-execution-protocol-v1"
    frozen_at: datetime
    status: Literal["FROZEN_PRE_DEVELOPMENT_OUTCOME"] = (
        "FROZEN_PRE_DEVELOPMENT_OUTCOME"
    )
    authorization_record: Literal[
        "USER_CONFIRMED_PROCEED_WITH_FROZEN_DEVELOPMENT_OUTCOME_STAGE"
    ] = JAM_OUTCOME_AUTHORIZATION_RECORD
    authorization_scope: Literal[
        "AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_CALCULATION"
    ] = JAM_OUTCOME_AUTHORIZATION_SCOPE
    parent_event_protocol_path: str
    parent_event_protocol_file_sha256: str
    parent_event_protocol_evidence_hash: str
    prevalence_protocol_path: str
    prevalence_protocol_file_sha256: str
    prevalence_protocol_evidence_hash: str
    prevalence_result_path: str
    prevalence_result_file_sha256: str
    prevalence_result_evidence_hash: str
    prevalence_audit_path: str
    prevalence_audit_file_sha256: str
    prevalence_audit_evidence_hash: str
    event_ledger_path: str
    event_ledger_file_sha256: str
    accepted_event_count: Literal[991] = 991
    raw_event_count: Literal[1430] = 1_430
    feature_rows_path: str
    feature_rows_file_sha256: str
    feature_rows_schema_hash: str
    distribution_protocol_path: str
    distribution_protocol_file_sha256: str
    distribution_protocol_evidence_hash: str
    distribution_result_path: str
    distribution_result_file_sha256: str
    distribution_result_evidence_hash: str
    quality_result_path: str
    quality_result_file_sha256: str
    quality_result_evidence_hash: str
    development_quarantine_minute_count: Literal[3063] = 3_063
    development_quarantine_manifest_hash: str
    archive_targets: list[JamDevelopmentArchiveTarget] = Field(
        min_length=24,
        max_length=24,
    )
    archive_target_manifest_hash: str
    activity_feature: Literal[
        "baseline_sell_quote_median_120m"
    ] = "baseline_sell_quote_median_120m"
    activity_q25: str
    activity_q50: str
    activity_q75: str
    activity_quartile_rule: Literal[
        "Q1_LE_Q25_Q2_GT_Q25_LE_Q50_Q3_GT_Q50_LE_Q75_Q4_GT_Q75"
    ] = "Q1_LE_Q25_Q2_GT_Q25_LE_Q50_Q3_GT_Q50_LE_Q75_Q4_GT_Q75"
    raw_events_excluded_from_controls: Literal[True] = True
    event_exclusion_radius_minutes: Literal[1440] = 1_440
    event_exclusion_boundary_inclusive: Literal[True] = True
    control_minimum_separation_minutes: Literal[60] = 60
    controls_without_replacement: Literal[True] = True
    control_event_order: Literal[
        "ASCENDING_EVENT_OPEN_TIME"
    ] = "ASCENDING_EVENT_OPEN_TIME"
    control_candidate_order: Literal[
        "MINIMUM_ABSOLUTE_DISTANCE_THEN_EARLIER_OPEN_TIME"
    ] = "MINIMUM_ABSOLUTE_DISTANCE_THEN_EARLIER_OPEN_TIME"
    exact_control_strata: list[str] = Field(min_length=3, max_length=3)
    outcome_horizons_minutes: list[Literal[15, 30, 60]] = Field(
        min_length=3,
        max_length=3,
    )
    primary_horizon_minutes: Literal[30] = 30
    entry_minute_offset: Literal[1] = 1
    entry_reference: Literal[
        "FIRST_AGGREGATE_TRADE_BY_NORMALIZED_TIME_THEN_AGGREGATE_ID"
    ] = "FIRST_AGGREGATE_TRADE_BY_NORMALIZED_TIME_THEN_AGGREGATE_ID"
    exit_reference: Literal[
        "LAST_AGGREGATE_TRADE_BY_NORMALIZED_TIME_THEN_AGGREGATE_ID"
    ] = "LAST_AGGREGATE_TRADE_BY_NORMALIZED_TIME_THEN_AGGREGATE_ID"
    path_extrema_source: Literal[
        "AGGREGATE_TRADE_MINIMUM_AND_MAXIMUM_PRICE_PER_MINUTE"
    ] = "AGGREGATE_TRADE_MINIMUM_AND_MAXIMUM_PRICE_PER_MINUTE"
    all_path_minutes_required: Literal[True] = True
    partition_crossing_policy: Literal[
        "OUTCOME_UNAVAILABLE_WITHOUT_OPENING_SEALED_DATA"
    ] = "OUTCOME_UNAVAILABLE_WITHOUT_OPENING_SEALED_DATA"
    quarantine_or_missing_policy: Literal[
        "OUTCOME_UNAVAILABLE_NO_SYNTHESIS"
    ] = "OUTCOME_UNAVAILABLE_NO_SYNTHESIS"
    decimal_quantum: Literal[
        "0.000000000000000001"
    ] = "0.000000000000000001"
    decimal_rounding: Literal["ROUND_HALF_EVEN"] = "ROUND_HALF_EVEN"
    tick_size_quote: Literal["0.01"] = "0.01"
    base_commission_rate_per_side: Literal["0.0010"] = "0.0010"
    stress_commission_rate_per_side: Literal["0.0015"] = "0.0015"
    base_adverse_ticks_per_fill: Literal[2] = 2
    stress_adverse_ticks_per_fill: Literal[10] = 10
    metric_source: Literal[
        "SERIALIZED_18_PLACE_PRIMARY_HORIZON_RETURNS"
    ] = "SERIALIZED_18_PLACE_PRIMARY_HORIZON_RETURNS"
    profit_factor_rule: Literal[
        "SUM_POSITIVE_DIVIDED_BY_ABS_SUM_NEGATIVE_POSITIVE_INFINITY_WHEN_NO_LOSS"
    ] = "SUM_POSITIVE_DIVIDED_BY_ABS_SUM_NEGATIVE_POSITIVE_INFINITY_WHEN_NO_LOSS"
    matched_excess_rule: Literal[
        "EVENT_BASE_NET_BPS_MINUS_CONTROL_BASE_NET_BPS"
    ] = "EVENT_BASE_NET_BPS_MINUS_CONTROL_BASE_NET_BPS"
    month_contribution_rule: Literal[
        "MONTH_SUM_ABSOLUTE_EVENT_BASE_RETURNS_DIVIDED_BY_ALL_MONTHS_SUM_ABSOLUTE_EVENT_BASE_RETURNS"
    ] = (
        "MONTH_SUM_ABSOLUTE_EVENT_BASE_RETURNS_DIVIDED_BY_"
        "ALL_MONTHS_SUM_ABSOLUTE_EVENT_BASE_RETURNS"
    )
    bootstrap_method: Literal[
        "SHA256_COUNTER_CALENDAR_MONTH_CLUSTER_RESAMPLING_WITH_REPLACEMENT"
    ] = "SHA256_COUNTER_CALENDAR_MONTH_CLUSTER_RESAMPLING_WITH_REPLACEMENT"
    bootstrap_repetitions: Literal[10000] = JAM_OUTCOME_BOOTSTRAP_REPETITIONS
    bootstrap_seed: Literal[20260805] = JAM_OUTCOME_BOOTSTRAP_SEED
    bootstrap_draw_rule: Literal[
        "FIRST_8_SHA256_BYTES_BIG_ENDIAN_MODULO_24"
    ] = "FIRST_8_SHA256_BYTES_BIG_ENDIAN_MODULO_24"
    bootstrap_token_rule: Literal[
        "ASCII_SEED_COLON_REPLICATE_COLON_DRAW"
    ] = "ASCII_SEED_COLON_REPLICATE_COLON_DRAW"
    bootstrap_lower_bound_rule: Literal[
        "SORTED_500TH_OF_10000_REPLICATE_MEANS_NO_INTERPOLATION"
    ] = "SORTED_500TH_OF_10000_REPLICATE_MEANS_NO_INTERPOLATION"
    development_gates: list[JamProtocolGate] = Field(min_length=11, max_length=11)
    control_ledger_path: Literal[
        "data/evidence/jam_successor_development_matched_control_ledger_v1.jsonl"
    ] = JAM_OUTCOME_CONTROL_LEDGER_PATH
    outcome_ledger_path: Literal[
        "data/evidence/jam_successor_development_outcome_ledger_v1.jsonl"
    ] = JAM_OUTCOME_LEDGER_PATH
    builder_contract_hash: str
    network_access_permitted: Literal[False] = False
    development_aggregate_trade_access_permitted: Literal[True] = True
    validation_2021_access_permitted: Literal[False] = False
    holdout_2022_access_permitted: Literal[False] = False
    threshold_change_permitted: Literal[False] = False
    diagnostic_rescue_permitted: Literal[False] = False
    strategy_creation_permitted: Literal[False] = False
    signal_creation_permitted: Literal[False] = False
    candidate_creation_permitted: Literal[False] = False
    paper_eligibility_permitted: Literal[False] = False
    testnet_strategy_orders_permitted: Literal[False] = False
    production_permitted: Literal[False] = False
    live_permitted: Literal[False] = False
    real_market_values_opened: Literal[0] = 0
    future_labels_calculated: Literal[0] = 0
    return_metrics_calculated: Literal[0] = 0
    limitations: list[str] = Field(min_length=18)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "parent_event_protocol_file_sha256",
        "parent_event_protocol_evidence_hash",
        "prevalence_protocol_file_sha256",
        "prevalence_protocol_evidence_hash",
        "prevalence_result_file_sha256",
        "prevalence_result_evidence_hash",
        "prevalence_audit_file_sha256",
        "prevalence_audit_evidence_hash",
        "event_ledger_file_sha256",
        "feature_rows_file_sha256",
        "feature_rows_schema_hash",
        "distribution_protocol_file_sha256",
        "distribution_protocol_evidence_hash",
        "distribution_result_file_sha256",
        "distribution_result_evidence_hash",
        "quality_result_file_sha256",
        "quality_result_evidence_hash",
        "development_quarantine_manifest_hash",
        "archive_target_manifest_hash",
        "builder_contract_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("activity_q25", "activity_q50", "activity_q75")
    @classmethod
    def normalize_activity_thresholds(cls, value: str) -> str:
        return normalize_decimal_string(value)

    @field_validator("limitations")
    @classmethod
    def normalize_limitations(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @field_validator("exact_control_strata")
    @classmethod
    def validate_control_strata(cls, value: list[str]) -> list[str]:
        expected = [
            "CALENDAR_MONTH",
            "UTC_HOUR_OF_DAY",
            "BASELINE_SELL_QUOTE_MEDIAN_QUARTILE",
        ]
        if value != expected:
            raise ValueError("Jam outcome control strata changed")
        return value

    @model_validator(mode="after")
    def validate_protocol(
        self,
    ) -> JamSuccessorDevelopmentOutcomeExecutionProtocol:
        if (
            [item.month for item in self.archive_targets]
            != list(JAM_DISTRIBUTION_MONTHS)
            or self.outcome_horizons_minutes != list(JAM_OUTCOME_HORIZONS)
            or [
                (item.gate_id, item.comparison, item.threshold, item.units)
                for item in self.development_gates
            ]
            != list(JAM_DEVELOPMENT_OUTCOME_GATE_SPECS)
            or not (
                Decimal(self.activity_q25)
                <= Decimal(self.activity_q50)
                <= Decimal(self.activity_q75)
            )
            or self.real_market_values_opened
            or self.future_labels_calculated
            or self.return_metrics_calculated
        ):
            raise ValueError("Jam development outcome protocol changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected_hash:
            raise ValueError("Jam development outcome protocol hash changed")
        return self


class JamControlFeatureRow(BaseModel):
    open_time_ms: int = Field(ge=0)
    month: str
    utc_hour: int = Field(ge=0, le=23)
    activity_value: str
    activity_quartile: Literal["Q1", "Q2", "Q3", "Q4"]

    model_config = ConfigDict(extra="forbid")

    @field_validator("activity_value")
    @classmethod
    def normalize_activity(cls, value: str) -> str:
        return normalize_decimal_string(value)

    @model_validator(mode="after")
    def validate_row(self) -> JamControlFeatureRow:
        timestamp = datetime.fromtimestamp(self.open_time_ms / 1_000, tz=UTC)
        if (
            self.open_time_ms % 60_000
            or self.month != timestamp.strftime("%Y-%m")
            or self.utc_hour != timestamp.hour
            or self.month not in JAM_DISTRIBUTION_MONTHS
        ):
            raise ValueError("Jam control feature row changed")
        return self


class JamMatchedControlRecord(BaseModel):
    event_sequence: int = Field(gt=0)
    event_open_time_ms: int = Field(ge=0)
    calendar_month: str
    utc_hour: int = Field(ge=0, le=23)
    activity_quartile: Literal["Q1", "Q2", "Q3", "Q4"]
    event_activity_value: str
    status: Literal["MATCHED", "UNMATCHED_NO_ELIGIBLE_CONTROL"]
    control_open_time_ms: int | None = Field(default=None, ge=0)
    control_activity_value: str | None = None
    absolute_distance_minutes: int | None = Field(default=None, ge=0)

    model_config = ConfigDict(extra="forbid")

    @field_validator("event_activity_value")
    @classmethod
    def normalize_event_activity(cls, value: str) -> str:
        return normalize_decimal_string(value)

    @field_validator("control_activity_value")
    @classmethod
    def normalize_control_activity(cls, value: str | None) -> str | None:
        return None if value is None else normalize_decimal_string(value)

    @model_validator(mode="after")
    def validate_match(self) -> JamMatchedControlRecord:
        event_time = datetime.fromtimestamp(self.event_open_time_ms / 1_000, tz=UTC)
        if (
            self.event_open_time_ms % 60_000
            or self.calendar_month != event_time.strftime("%Y-%m")
            or self.utc_hour != event_time.hour
        ):
            raise ValueError("Jam matched control event strata changed")
        matched = self.status == "MATCHED"
        if matched != (
            self.control_open_time_ms is not None
            and self.control_activity_value is not None
            and self.absolute_distance_minutes is not None
        ):
            raise ValueError("Jam matched control availability changed")
        if matched:
            control_time = datetime.fromtimestamp(
                self.control_open_time_ms / 1_000,
                tz=UTC,
            )
            if (
                self.control_open_time_ms % 60_000
                or control_time.strftime("%Y-%m") != self.calendar_month
                or control_time.hour != self.utc_hour
                or self.absolute_distance_minutes
                != abs(self.control_open_time_ms - self.event_open_time_ms) // 60_000
            ):
                raise ValueError("Jam matched control exact strata changed")
        return self


class JamAggregateMinutePrice(BaseModel):
    open_time_ms: int = Field(ge=0)
    first_price: str
    high_price: str
    low_price: str
    last_price: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("first_price", "high_price", "low_price", "last_price")
    @classmethod
    def normalize_prices(cls, value: str) -> str:
        normalized = normalize_decimal_string(value)
        if Decimal(normalized) <= 0:
            raise ValueError("Jam aggregate minute price is not positive")
        return normalized

    @model_validator(mode="after")
    def validate_minute(self) -> JamAggregateMinutePrice:
        prices = [
            Decimal(self.first_price),
            Decimal(self.high_price),
            Decimal(self.low_price),
            Decimal(self.last_price),
        ]
        if (
            self.open_time_ms % 60_000
            or Decimal(self.high_price) < max(prices)
            or Decimal(self.low_price) > min(prices)
        ):
            raise ValueError("Jam aggregate minute OHLC changed")
        return self


class JamDevelopmentHorizonOutcome(BaseModel):
    subject_type: Literal["EVENT", "CONTROL"]
    subject_sequence: int = Field(gt=0)
    paired_event_sequence: int = Field(gt=0)
    evaluation_open_time_ms: int = Field(ge=0)
    calendar_month: str
    calendar_quarter: str
    horizon_minutes: Literal[15, 30, 60]
    role: Literal["PRIMARY", "NONSELECTABLE_DIAGNOSTIC"]
    status: Literal[
        "AVAILABLE",
        "UNAVAILABLE_CROSSES_DEVELOPMENT_PARTITION",
        "UNAVAILABLE_QUARANTINED_PATH_MINUTE",
        "UNAVAILABLE_MISSING_AGGREGATE_PATH_MINUTE",
    ]
    first_unavailable_open_time_ms: int | None = Field(default=None, ge=0)
    entry_reference_price: str | None = None
    exit_reference_price: str | None = None
    path_high_price: str | None = None
    path_low_price: str | None = None
    base_entry_fill_price: str | None = None
    base_exit_fill_price: str | None = None
    stress_entry_fill_price: str | None = None
    stress_exit_fill_price: str | None = None
    base_net_return_bps: str | None = None
    stress_net_return_bps: str | None = None
    maximum_favorable_excursion_bps: str | None = None
    maximum_adverse_excursion_bps: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "entry_reference_price",
        "exit_reference_price",
        "path_high_price",
        "path_low_price",
        "base_entry_fill_price",
        "base_exit_fill_price",
        "stress_entry_fill_price",
        "stress_exit_fill_price",
        "base_net_return_bps",
        "stress_net_return_bps",
        "maximum_favorable_excursion_bps",
        "maximum_adverse_excursion_bps",
    )
    @classmethod
    def normalize_optional_decimals(cls, value: str | None) -> str | None:
        return None if value is None else normalize_decimal_string(value)

    @model_validator(mode="after")
    def validate_outcome(self) -> JamDevelopmentHorizonOutcome:
        timestamp = datetime.fromtimestamp(
            self.evaluation_open_time_ms / 1_000,
            tz=UTC,
        )
        expected_quarter = f"{timestamp.year}-Q{((timestamp.month - 1) // 3) + 1}"
        if (
            self.evaluation_open_time_ms % 60_000
            or self.calendar_month != timestamp.strftime("%Y-%m")
            or self.calendar_quarter != expected_quarter
            or self.role
            != ("PRIMARY" if self.horizon_minutes == 30 else "NONSELECTABLE_DIAGNOSTIC")
        ):
            raise ValueError("Jam horizon outcome identity changed")
        values = (
            self.entry_reference_price,
            self.exit_reference_price,
            self.path_high_price,
            self.path_low_price,
            self.base_entry_fill_price,
            self.base_exit_fill_price,
            self.stress_entry_fill_price,
            self.stress_exit_fill_price,
            self.base_net_return_bps,
            self.stress_net_return_bps,
            self.maximum_favorable_excursion_bps,
            self.maximum_adverse_excursion_bps,
        )
        available = self.status == "AVAILABLE"
        if available:
            if self.first_unavailable_open_time_ms is not None or any(
                value is None for value in values
            ):
                raise ValueError("Jam available outcome is incomplete")
        elif self.first_unavailable_open_time_ms is None or any(
            value is not None for value in values
        ):
            raise ValueError("Jam unavailable outcome exposes a value")
        return self


class JamOutcomeArchiveEvidence(BaseModel):
    month: str
    archive_path: str
    archive_sha256: str
    requested_minute_count: int = Field(ge=0)
    recovered_minute_count: int = Field(ge=0)
    missing_minute_count: int = Field(ge=0)
    archive_identity_passed: Literal[True] = True

    model_config = ConfigDict(extra="forbid")

    @field_validator("archive_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_evidence(self) -> JamOutcomeArchiveEvidence:
        if (
            self.recovered_minute_count + self.missing_minute_count
            != self.requested_minute_count
        ):
            raise ValueError("Jam outcome archive minute counts changed")
        return self


class JamOutcomeBucketMetric(BaseModel):
    bucket: str
    outcome_count: int = Field(ge=0)
    base_net_mean_bps: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("base_net_mean_bps")
    @classmethod
    def normalize_mean(cls, value: str) -> str:
        return normalize_decimal_string(value)


class JamOutcomeMonthContribution(BaseModel):
    month: str
    absolute_return_sum_bps: str
    contribution_share: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("absolute_return_sum_bps", "contribution_share")
    @classmethod
    def normalize_values(cls, value: str) -> str:
        return normalize_decimal_string(value)


class JamDevelopmentOutcomeGateResult(BaseModel):
    gate_id: str
    comparison: Literal[
        "GREATER_THAN_OR_EQUAL",
        "LESS_THAN_OR_EQUAL",
        "GREATER_THAN",
        "EQUAL",
    ]
    threshold: str
    units: str
    observed: str
    passed: bool

    model_config = ConfigDict(extra="forbid")

    @field_validator("threshold")
    @classmethod
    def normalize_threshold(cls, value: str) -> str:
        return normalize_decimal_string(value)

    @field_validator("observed")
    @classmethod
    def normalize_observed(cls, value: str) -> str:
        return normalize_decimal_string(value, allow_positive_infinity=True)

    @model_validator(mode="after")
    def validate_gate(self) -> JamDevelopmentOutcomeGateResult:
        if self.passed != _evaluate_comparison(
            observed=self.observed,
            comparison=self.comparison,
            threshold=self.threshold,
        ):
            raise ValueError("Jam development outcome gate decision changed")
        return self


class JamSuccessorDevelopmentOutcomeResult(BaseModel):
    schema_version: Literal[
        "aurex-jam-successor-development-outcome-result-v1"
    ] = JAM_OUTCOME_RESULT_SCHEMA_VERSION
    result_id: Literal[
        "jam-successor-development-outcome-result-v1"
    ] = "jam-successor-development-outcome-result-v1"
    generated_at: datetime
    status: Literal["COMPLETE_DEVELOPMENT_OUTCOMES"] = "COMPLETE_DEVELOPMENT_OUTCOMES"
    protocol_evidence_hash: str
    runner_contract_hash: str
    prevalence_result_evidence_hash: str
    event_ledger_file_sha256: str
    feature_rows_file_sha256: str
    control_ledger_path: Literal[
        "data/evidence/jam_successor_development_matched_control_ledger_v1.jsonl"
    ] = JAM_OUTCOME_CONTROL_LEDGER_PATH
    control_ledger_file_sha256: str
    control_ledger_bytes: int = Field(ge=0)
    control_ledger_record_count: Literal[991] = 991
    matched_control_count: int = Field(ge=0, le=991)
    unmatched_event_count: int = Field(ge=0, le=991)
    outcome_ledger_path: Literal[
        "data/evidence/jam_successor_development_outcome_ledger_v1.jsonl"
    ] = JAM_OUTCOME_LEDGER_PATH
    outcome_ledger_file_sha256: str
    outcome_ledger_bytes: int = Field(ge=0)
    outcome_ledger_record_count: int = Field(ge=0)
    archive_evidence: list[JamOutcomeArchiveEvidence] = Field(
        min_length=24,
        max_length=24,
    )
    accepted_event_count: Literal[991] = 991
    primary_outcome_qualified_event_count: int = Field(ge=0, le=991)
    primary_outcome_qualified_control_count: int = Field(ge=0, le=991)
    matched_primary_pair_count: int = Field(ge=0, le=991)
    event_horizon_available_counts: dict[str, int]
    control_horizon_available_counts: dict[str, int]
    base_net_mean_30m_bps: str
    base_net_profit_factor_30m: str
    stress_net_mean_30m_bps: str
    matched_excess_mean_30m_bps: str
    bootstrap_lower_95_base_net_mean_30m_bps: str
    bootstrap_lower_95_matched_excess_mean_30m_bps: str
    yearly_metrics: list[JamOutcomeBucketMetric] = Field(min_length=2, max_length=2)
    quarterly_metrics: list[JamOutcomeBucketMetric] = Field(
        min_length=8,
        max_length=8,
    )
    positive_year_count: int = Field(ge=0, le=2)
    positive_quarter_count: int = Field(ge=0, le=8)
    monthly_absolute_return_contributions: list[
        JamOutcomeMonthContribution
    ] = Field(min_length=24, max_length=24)
    largest_month_absolute_return_contribution: str
    largest_contribution_month: str
    gates: list[JamDevelopmentOutcomeGateResult] = Field(
        min_length=11,
        max_length=11,
    )
    passed_gate_count: int = Field(ge=0, le=11)
    failed_gate_count: int = Field(ge=0, le=11)
    decision: Literal[
        "PASS_DEVELOPMENT_OUTCOMES_AWAIT_SEALED_2021_VALIDATION_AUTHORIZATION",
        "STOP_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_FAILED",
    ]
    next_required_authorization: Literal[
        "AUTHORIZE_JAM_SUCCESSOR_SEALED_2021_VALIDATION",
        "NONE_DEVELOPMENT_OUTCOME_FAILED",
    ]
    real_market_periods_opened: list[str] = Field(min_length=1, max_length=1)
    sealed_market_periods_opened: list[str] = Field(default_factory=list)
    outcome_horizons_calculated: list[int] = Field(min_length=3, max_length=3)
    return_metrics_calculated: list[str] = Field(min_length=8)
    diagnostics_used_for_selection: Literal[False] = False
    threshold_changes: list[str] = Field(default_factory=list)
    strategy_executions: Literal[0] = 0
    creates_strategy: Literal[False] = False
    creates_signal: Literal[False] = False
    creates_candidate: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_testnet_order_authority: Literal[False] = False
    creates_production_authority: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    limitations: list[str] = Field(min_length=18)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_evidence_hash",
        "runner_contract_hash",
        "prevalence_result_evidence_hash",
        "event_ledger_file_sha256",
        "feature_rows_file_sha256",
        "control_ledger_file_sha256",
        "outcome_ledger_file_sha256",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "base_net_mean_30m_bps",
        "stress_net_mean_30m_bps",
        "matched_excess_mean_30m_bps",
        "bootstrap_lower_95_base_net_mean_30m_bps",
        "bootstrap_lower_95_matched_excess_mean_30m_bps",
        "largest_month_absolute_return_contribution",
    )
    @classmethod
    def normalize_metrics(cls, value: str) -> str:
        return normalize_decimal_string(value)

    @field_validator("base_net_profit_factor_30m")
    @classmethod
    def normalize_profit_factor(cls, value: str) -> str:
        return normalize_decimal_string(value, allow_positive_infinity=True)

    @field_validator(
        "real_market_periods_opened",
        "sealed_market_periods_opened",
        "return_metrics_calculated",
        "threshold_changes",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_result(self) -> JamSuccessorDevelopmentOutcomeResult:
        if (
            self.matched_control_count + self.unmatched_event_count != 991
            or [item.month for item in self.archive_evidence]
            != list(JAM_DISTRIBUTION_MONTHS)
            or [item.bucket for item in self.yearly_metrics] != ["2019", "2020"]
            or [item.bucket for item in self.quarterly_metrics]
            != list(JAM_PREVALENCE_QUARTERS)
            or [
                item.month for item in self.monthly_absolute_return_contributions
            ]
            != list(JAM_DISTRIBUTION_MONTHS)
            or self.outcome_horizons_calculated != list(JAM_OUTCOME_HORIZONS)
        ):
            raise ValueError("Jam development outcome result matrix changed")
        expected_records = 3 * (991 + self.matched_control_count)
        if self.outcome_ledger_record_count != expected_records:
            raise ValueError("Jam development outcome ledger count changed")
        expected_positive_years = sum(
            Decimal(item.base_net_mean_bps) > 0 for item in self.yearly_metrics
        )
        expected_positive_quarters = sum(
            Decimal(item.base_net_mean_bps) > 0
            for item in self.quarterly_metrics
        )
        if (
            self.positive_year_count != expected_positive_years
            or self.positive_quarter_count != expected_positive_quarters
        ):
            raise ValueError("Jam outcome temporal breadth changed")
        contributions = self.monthly_absolute_return_contributions
        largest = max(
            contributions,
            key=lambda item: (Decimal(item.contribution_share), item.month),
        )
        if (
            Decimal(self.largest_month_absolute_return_contribution)
            != Decimal(largest.contribution_share)
            or self.largest_contribution_month != largest.month
        ):
            raise ValueError("Jam outcome concentration changed")
        gate_matrix = [
            (item.gate_id, item.comparison, item.threshold, item.units)
            for item in self.gates
        ]
        if gate_matrix != list(JAM_DEVELOPMENT_OUTCOME_GATE_SPECS):
            raise ValueError("Jam development outcome gate matrix changed")
        observations = [
            str(self.primary_outcome_qualified_event_count),
            str(self.matched_primary_pair_count),
            self.base_net_mean_30m_bps,
            self.base_net_profit_factor_30m,
            self.stress_net_mean_30m_bps,
            self.matched_excess_mean_30m_bps,
            self.bootstrap_lower_95_base_net_mean_30m_bps,
            self.bootstrap_lower_95_matched_excess_mean_30m_bps,
            str(self.positive_year_count),
            str(self.positive_quarter_count),
            self.largest_month_absolute_return_contribution,
        ]
        if [item.observed for item in self.gates] != [
            normalize_decimal_string(item, allow_positive_infinity=True)
            for item in observations
        ]:
            raise ValueError("Jam development outcome gate observations changed")
        passed = sum(item.passed for item in self.gates)
        all_passed = passed == len(self.gates)
        if (
            self.passed_gate_count != passed
            or self.failed_gate_count != len(self.gates) - passed
            or self.decision
            != (
                JAM_OUTCOME_PASS_DECISION
                if all_passed
                else JAM_OUTCOME_FAIL_DECISION
            )
            or self.next_required_authorization
            != (
                JAM_OUTCOME_NEXT_AUTHORIZATION
                if all_passed
                else JAM_OUTCOME_NO_NEXT_AUTHORIZATION
            )
        ):
            raise ValueError("Jam development outcome decision changed")
        if (
            self.real_market_periods_opened
            != ["2019-01_THROUGH_2020-12_DEVELOPMENT"]
            or self.sealed_market_periods_opened
            or self.diagnostics_used_for_selection
            or self.threshold_changes
            or self.strategy_executions
        ):
            raise ValueError("Jam development outcome authority boundary changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected_hash:
            raise ValueError("Jam development outcome result hash changed")
        return self


class JamSuccessorDevelopmentOutcomeAudit(BaseModel):
    schema_version: Literal[
        "aurex-jam-successor-development-outcome-audit-v1"
    ] = JAM_OUTCOME_AUDIT_SCHEMA_VERSION
    audited_at: datetime
    protocol_path: str
    protocol_file_sha256: str
    protocol_evidence_hash: str
    result_path: str
    result_file_sha256: str
    result_evidence_hash: str
    control_ledger_path: str
    control_ledger_file_sha256: str
    outcome_ledger_path: str
    outcome_ledger_file_sha256: str
    matched_control_count_reconstructed: int = Field(ge=0, le=991)
    outcome_ledger_record_count_reconstructed: int = Field(ge=0)
    primary_event_outcome_count_reconstructed: int = Field(ge=0, le=991)
    matched_primary_pair_count_reconstructed: int = Field(ge=0, le=991)
    passed_gate_count_reconstructed: int = Field(ge=0, le=11)
    failed_gate_count_reconstructed: int = Field(ge=0, le=11)
    sealed_market_periods_opened: Literal[0] = 0
    threshold_changes: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    decision: Literal[
        "PASS_DEVELOPMENT_OUTCOMES_AWAIT_SEALED_2021_VALIDATION_AUTHORIZATION",
        "STOP_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_FAILED",
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
        "control_ledger_file_sha256",
        "outcome_ledger_file_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> JamSuccessorDevelopmentOutcomeAudit:
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected_hash:
            raise ValueError("Jam development outcome audit hash changed")
        return self


def activity_quartile(
    value: Decimal,
    *,
    q25: Decimal,
    q50: Decimal,
    q75: Decimal,
) -> Literal["Q1", "Q2", "Q3", "Q4"]:
    if not q25 <= q50 <= q75:
        raise ValueError("Jam activity quartile thresholds changed")
    if value <= q25:
        return "Q1"
    if value <= q50:
        return "Q2"
    if value <= q75:
        return "Q3"
    return "Q4"


def _is_at_least_minutes_from_all(
    open_time_ms: int,
    sorted_times: list[int],
    minimum_minutes: int,
) -> bool:
    index = bisect_left(sorted_times, open_time_ms)
    minimum_ms = minimum_minutes * 60_000
    for neighbor_index in (index - 1, index):
        if 0 <= neighbor_index < len(sorted_times):
            if abs(sorted_times[neighbor_index] - open_time_ms) < minimum_ms:
                return False
    return True


def select_matched_controls(
    *,
    accepted_event_times: list[int],
    event_activity_rows: dict[int, JamControlFeatureRow],
    candidate_groups: dict[
        tuple[str, int, str],
        list[JamControlFeatureRow],
    ],
) -> list[JamMatchedControlRecord]:
    if (
        accepted_event_times != sorted(accepted_event_times)
        or len(set(accepted_event_times)) != len(accepted_event_times)
        or set(accepted_event_times) != set(event_activity_rows)
    ):
        raise ValueError("Jam accepted event control inputs changed")
    selected_times: list[int] = []
    used_times: set[int] = set()
    records: list[JamMatchedControlRecord] = []
    for event_sequence, event_time in enumerate(accepted_event_times, start=1):
        event_row = event_activity_rows[event_time]
        key = (
            event_row.month,
            event_row.utc_hour,
            event_row.activity_quartile,
        )
        eligible = (
            candidate
            for candidate in candidate_groups.get(key, [])
            if candidate.open_time_ms not in used_times
            and _is_at_least_minutes_from_all(
                candidate.open_time_ms,
                selected_times,
                60,
            )
        )
        selected = min(
            eligible,
            key=lambda candidate: (
                abs(candidate.open_time_ms - event_time),
                candidate.open_time_ms,
            ),
            default=None,
        )
        if selected is None:
            record = JamMatchedControlRecord(
                event_sequence=event_sequence,
                event_open_time_ms=event_time,
                calendar_month=event_row.month,
                utc_hour=event_row.utc_hour,
                activity_quartile=event_row.activity_quartile,
                event_activity_value=event_row.activity_value,
                status="UNMATCHED_NO_ELIGIBLE_CONTROL",
            )
        else:
            used_times.add(selected.open_time_ms)
            insort(selected_times, selected.open_time_ms)
            record = JamMatchedControlRecord(
                event_sequence=event_sequence,
                event_open_time_ms=event_time,
                calendar_month=event_row.month,
                utc_hour=event_row.utc_hour,
                activity_quartile=event_row.activity_quartile,
                event_activity_value=event_row.activity_value,
                status="MATCHED",
                control_open_time_ms=selected.open_time_ms,
                control_activity_value=selected.activity_value,
                absolute_distance_minutes=(
                    abs(selected.open_time_ms - event_time) // 60_000
                ),
            )
        records.append(record)
    return records


def calculate_horizon_outcome(
    *,
    subject_type: Literal["EVENT", "CONTROL"],
    subject_sequence: int,
    paired_event_sequence: int,
    evaluation_open_time_ms: int,
    horizon_minutes: Literal[15, 30, 60],
    minute_prices: dict[int, JamAggregateMinutePrice],
    quarantined_minutes: set[int],
) -> JamDevelopmentHorizonOutcome:
    timestamp = datetime.fromtimestamp(evaluation_open_time_ms / 1_000, tz=UTC)
    identity = {
        "subject_type": subject_type,
        "subject_sequence": subject_sequence,
        "paired_event_sequence": paired_event_sequence,
        "evaluation_open_time_ms": evaluation_open_time_ms,
        "calendar_month": timestamp.strftime("%Y-%m"),
        "calendar_quarter": f"{timestamp.year}-Q{((timestamp.month - 1) // 3) + 1}",
        "horizon_minutes": horizon_minutes,
        "role": (
            "PRIMARY"
            if horizon_minutes == 30
            else "NONSELECTABLE_DIAGNOSTIC"
        ),
    }
    path = [
        evaluation_open_time_ms + offset * 60_000
        for offset in range(1, horizon_minutes + 1)
    ]
    crossing = next(
        (
            minute
            for minute in path
            if not (
                JAM_OUTCOME_DEVELOPMENT_START_MS
                <= minute
                < JAM_OUTCOME_DEVELOPMENT_END_EXCLUSIVE_MS
            )
        ),
        None,
    )
    if crossing is not None:
        return JamDevelopmentHorizonOutcome(
            **identity,
            status="UNAVAILABLE_CROSSES_DEVELOPMENT_PARTITION",
            first_unavailable_open_time_ms=crossing,
        )
    quarantined = next(
        (minute for minute in path if minute in quarantined_minutes),
        None,
    )
    if quarantined is not None:
        return JamDevelopmentHorizonOutcome(
            **identity,
            status="UNAVAILABLE_QUARANTINED_PATH_MINUTE",
            first_unavailable_open_time_ms=quarantined,
        )
    missing = next(
        (minute for minute in path if minute not in minute_prices),
        None,
    )
    if missing is not None:
        return JamDevelopmentHorizonOutcome(
            **identity,
            status="UNAVAILABLE_MISSING_AGGREGATE_PATH_MINUTE",
            first_unavailable_open_time_ms=missing,
        )
    entry_reference = Decimal(minute_prices[path[0]].first_price)
    exit_reference = Decimal(minute_prices[path[-1]].last_price)
    path_high = max(Decimal(minute_prices[minute].high_price) for minute in path)
    path_low = min(Decimal(minute_prices[minute].low_price) for minute in path)
    base_entry = entry_reference + JAM_OUTCOME_BASE_TICKS * JAM_OUTCOME_TICK_SIZE
    base_exit = exit_reference - JAM_OUTCOME_BASE_TICKS * JAM_OUTCOME_TICK_SIZE
    stress_entry = (
        entry_reference + JAM_OUTCOME_STRESS_TICKS * JAM_OUTCOME_TICK_SIZE
    )
    stress_exit = (
        exit_reference - JAM_OUTCOME_STRESS_TICKS * JAM_OUTCOME_TICK_SIZE
    )
    if min(base_exit, stress_exit) <= 0:
        raise ValueError("Jam adverse exit fill is not positive")
    base_return = Decimal(10_000) * (
        (base_exit * (Decimal(1) - JAM_OUTCOME_BASE_FEE))
        / (base_entry * (Decimal(1) + JAM_OUTCOME_BASE_FEE))
        - Decimal(1)
    )
    stress_return = Decimal(10_000) * (
        (stress_exit * (Decimal(1) - JAM_OUTCOME_STRESS_FEE))
        / (stress_entry * (Decimal(1) + JAM_OUTCOME_STRESS_FEE))
        - Decimal(1)
    )
    maximum_favorable = Decimal(10_000) * (
        path_high / base_entry - Decimal(1)
    )
    maximum_adverse = Decimal(10_000) * (
        path_low / base_entry - Decimal(1)
    )
    return JamDevelopmentHorizonOutcome(
        **identity,
        status="AVAILABLE",
        entry_reference_price=normalize_decimal_string(entry_reference),
        exit_reference_price=normalize_decimal_string(exit_reference),
        path_high_price=normalize_decimal_string(path_high),
        path_low_price=normalize_decimal_string(path_low),
        base_entry_fill_price=normalize_decimal_string(base_entry),
        base_exit_fill_price=normalize_decimal_string(base_exit),
        stress_entry_fill_price=normalize_decimal_string(stress_entry),
        stress_exit_fill_price=normalize_decimal_string(stress_exit),
        base_net_return_bps=normalize_decimal_string(
            quantize_outcome(base_return)
        ),
        stress_net_return_bps=normalize_decimal_string(
            quantize_outcome(stress_return)
        ),
        maximum_favorable_excursion_bps=normalize_decimal_string(
            quantize_outcome(maximum_favorable)
        ),
        maximum_adverse_excursion_bps=normalize_decimal_string(
            quantize_outcome(maximum_adverse)
        ),
    )


def decimal_mean(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal(0)
    return quantize_outcome(sum(values, Decimal(0)) / Decimal(len(values)))


def profit_factor(values: list[Decimal]) -> str:
    gross_profit = sum((value for value in values if value > 0), Decimal(0))
    gross_loss = abs(sum((value for value in values if value < 0), Decimal(0)))
    if gross_loss == 0:
        return "POSITIVE_INFINITY" if gross_profit > 0 else "0"
    return normalize_decimal_string(quantize_outcome(gross_profit / gross_loss))


def cluster_bootstrap_lower_bound(
    values_by_month: dict[str, list[Decimal]],
) -> Decimal:
    if list(values_by_month) != list(JAM_DISTRIBUTION_MONTHS):
        raise ValueError("Jam bootstrap month matrix changed")
    if not any(values_by_month.values()):
        return Decimal(0)
    month_sums = [
        sum(values_by_month[month], Decimal(0))
        for month in JAM_DISTRIBUTION_MONTHS
    ]
    month_counts = [
        len(values_by_month[month]) for month in JAM_DISTRIBUTION_MONTHS
    ]
    replicate_means = []
    for replicate in range(JAM_OUTCOME_BOOTSTRAP_REPETITIONS):
        sampled_sum = Decimal(0)
        sampled_count = 0
        for draw in range(len(JAM_DISTRIBUTION_MONTHS)):
            token = f"{JAM_OUTCOME_BOOTSTRAP_SEED}:{replicate}:{draw}".encode(
                "ascii"
            )
            index = (
                int.from_bytes(hashlib.sha256(token).digest()[:8], "big")
                % len(JAM_DISTRIBUTION_MONTHS)
            )
            sampled_sum += month_sums[index]
            sampled_count += month_counts[index]
        replicate_means.append(
            quantize_outcome(sampled_sum / Decimal(sampled_count))
            if sampled_count
            else Decimal(0)
        )
    replicate_means.sort()
    return replicate_means[JAM_OUTCOME_BOOTSTRAP_LOWER_ORDER_INDEX]


def build_outcome_gate_results(
    observations: list[str],
) -> list[JamDevelopmentOutcomeGateResult]:
    if len(observations) != len(JAM_DEVELOPMENT_OUTCOME_GATE_SPECS):
        raise ValueError("Jam development outcome observations changed")
    results = []
    for spec, observed in zip(
        JAM_DEVELOPMENT_OUTCOME_GATE_SPECS,
        observations,
        strict=True,
    ):
        gate_id, comparison, threshold, units = spec
        normalized = normalize_decimal_string(
            observed,
            allow_positive_infinity=True,
        )
        results.append(
            JamDevelopmentOutcomeGateResult(
                gate_id=gate_id,
                comparison=comparison,
                threshold=threshold,
                units=units,
                observed=normalized,
                passed=_evaluate_comparison(
                    observed=normalized,
                    comparison=comparison,
                    threshold=threshold,
                ),
            )
        )
    return results


def build_jam_successor_outcome_protocol(
    **values,
) -> JamSuccessorDevelopmentOutcomeExecutionProtocol:
    payload = {
        "schema_version": JAM_OUTCOME_PROTOCOL_SCHEMA_VERSION,
        "protocol_id": "jam-successor-development-outcome-execution-protocol-v1",
        "status": "FROZEN_PRE_DEVELOPMENT_OUTCOME",
        "authorization_record": JAM_OUTCOME_AUTHORIZATION_RECORD,
        "authorization_scope": JAM_OUTCOME_AUTHORIZATION_SCOPE,
        "accepted_event_count": 991,
        "raw_event_count": 1_430,
        "development_quarantine_minute_count": 3_063,
        "activity_feature": "baseline_sell_quote_median_120m",
        "activity_quartile_rule": (
            "Q1_LE_Q25_Q2_GT_Q25_LE_Q50_Q3_GT_Q50_LE_Q75_Q4_GT_Q75"
        ),
        "raw_events_excluded_from_controls": True,
        "event_exclusion_radius_minutes": 1_440,
        "event_exclusion_boundary_inclusive": True,
        "control_minimum_separation_minutes": 60,
        "controls_without_replacement": True,
        "control_event_order": "ASCENDING_EVENT_OPEN_TIME",
        "control_candidate_order": (
            "MINIMUM_ABSOLUTE_DISTANCE_THEN_EARLIER_OPEN_TIME"
        ),
        "exact_control_strata": [
            "CALENDAR_MONTH",
            "UTC_HOUR_OF_DAY",
            "BASELINE_SELL_QUOTE_MEDIAN_QUARTILE",
        ],
        "outcome_horizons_minutes": [15, 30, 60],
        "primary_horizon_minutes": 30,
        "entry_minute_offset": 1,
        "entry_reference": (
            "FIRST_AGGREGATE_TRADE_BY_NORMALIZED_TIME_THEN_AGGREGATE_ID"
        ),
        "exit_reference": (
            "LAST_AGGREGATE_TRADE_BY_NORMALIZED_TIME_THEN_AGGREGATE_ID"
        ),
        "path_extrema_source": (
            "AGGREGATE_TRADE_MINIMUM_AND_MAXIMUM_PRICE_PER_MINUTE"
        ),
        "all_path_minutes_required": True,
        "partition_crossing_policy": (
            "OUTCOME_UNAVAILABLE_WITHOUT_OPENING_SEALED_DATA"
        ),
        "quarantine_or_missing_policy": "OUTCOME_UNAVAILABLE_NO_SYNTHESIS",
        "decimal_quantum": "0.000000000000000001",
        "decimal_rounding": "ROUND_HALF_EVEN",
        "tick_size_quote": "0.01",
        "base_commission_rate_per_side": "0.0010",
        "stress_commission_rate_per_side": "0.0015",
        "base_adverse_ticks_per_fill": 2,
        "stress_adverse_ticks_per_fill": 10,
        "metric_source": "SERIALIZED_18_PLACE_PRIMARY_HORIZON_RETURNS",
        "profit_factor_rule": (
            "SUM_POSITIVE_DIVIDED_BY_ABS_SUM_NEGATIVE_"
            "POSITIVE_INFINITY_WHEN_NO_LOSS"
        ),
        "matched_excess_rule": (
            "EVENT_BASE_NET_BPS_MINUS_CONTROL_BASE_NET_BPS"
        ),
        "month_contribution_rule": (
            "MONTH_SUM_ABSOLUTE_EVENT_BASE_RETURNS_DIVIDED_BY_"
            "ALL_MONTHS_SUM_ABSOLUTE_EVENT_BASE_RETURNS"
        ),
        "bootstrap_method": (
            "SHA256_COUNTER_CALENDAR_MONTH_CLUSTER_RESAMPLING_WITH_REPLACEMENT"
        ),
        "bootstrap_repetitions": JAM_OUTCOME_BOOTSTRAP_REPETITIONS,
        "bootstrap_seed": JAM_OUTCOME_BOOTSTRAP_SEED,
        "bootstrap_draw_rule": "FIRST_8_SHA256_BYTES_BIG_ENDIAN_MODULO_24",
        "bootstrap_token_rule": "ASCII_SEED_COLON_REPLICATE_COLON_DRAW",
        "bootstrap_lower_bound_rule": (
            "SORTED_500TH_OF_10000_REPLICATE_MEANS_NO_INTERPOLATION"
        ),
        "development_gates": [
            JamProtocolGate(
                gate_id=gate_id,
                comparison=comparison,
                threshold=threshold,
                units=units,
            )
            for gate_id, comparison, threshold, units in JAM_DEVELOPMENT_OUTCOME_GATE_SPECS
        ],
        "control_ledger_path": JAM_OUTCOME_CONTROL_LEDGER_PATH,
        "outcome_ledger_path": JAM_OUTCOME_LEDGER_PATH,
        "network_access_permitted": False,
        "development_aggregate_trade_access_permitted": True,
        "validation_2021_access_permitted": False,
        "holdout_2022_access_permitted": False,
        "threshold_change_permitted": False,
        "diagnostic_rescue_permitted": False,
        "strategy_creation_permitted": False,
        "signal_creation_permitted": False,
        "candidate_creation_permitted": False,
        "paper_eligibility_permitted": False,
        "testnet_strategy_orders_permitted": False,
        "production_permitted": False,
        "live_permitted": False,
        "real_market_values_opened": 0,
        "future_labels_calculated": 0,
        "return_metrics_calculated": 0,
        **values,
    }
    payload["limitations"] = sorted(set(payload["limitations"]))
    return JamSuccessorDevelopmentOutcomeExecutionProtocol(
        **payload,
        protocol_evidence_hash=universe_evidence_hash(payload),
    )


def build_jam_successor_outcome_result(
    **values,
) -> JamSuccessorDevelopmentOutcomeResult:
    passed = sum(item.passed for item in values["gates"])
    payload = {
        "schema_version": JAM_OUTCOME_RESULT_SCHEMA_VERSION,
        "result_id": "jam-successor-development-outcome-result-v1",
        "status": "COMPLETE_DEVELOPMENT_OUTCOMES",
        "control_ledger_path": JAM_OUTCOME_CONTROL_LEDGER_PATH,
        "control_ledger_record_count": 991,
        "outcome_ledger_path": JAM_OUTCOME_LEDGER_PATH,
        "accepted_event_count": 991,
        "passed_gate_count": passed,
        "failed_gate_count": len(values["gates"]) - passed,
        "decision": (
            JAM_OUTCOME_PASS_DECISION
            if passed == len(values["gates"])
            else JAM_OUTCOME_FAIL_DECISION
        ),
        "next_required_authorization": (
            JAM_OUTCOME_NEXT_AUTHORIZATION
            if passed == len(values["gates"])
            else JAM_OUTCOME_NO_NEXT_AUTHORIZATION
        ),
        "real_market_periods_opened": [
            "2019-01_THROUGH_2020-12_DEVELOPMENT"
        ],
        "sealed_market_periods_opened": [],
        "outcome_horizons_calculated": [15, 30, 60],
        "diagnostics_used_for_selection": False,
        "threshold_changes": [],
        "strategy_executions": 0,
        "creates_strategy": False,
        "creates_signal": False,
        "creates_candidate": False,
        "creates_paper_eligibility": False,
        "creates_testnet_order_authority": False,
        "creates_production_authority": False,
        "creates_live_eligibility": False,
        **values,
    }
    payload["return_metrics_calculated"] = sorted(
        set(payload["return_metrics_calculated"])
    )
    payload["limitations"] = sorted(set(payload["limitations"]))
    return JamSuccessorDevelopmentOutcomeResult(
        **payload,
        result_evidence_hash=universe_evidence_hash(payload),
    )


def build_jam_successor_outcome_audit(
    **values,
) -> JamSuccessorDevelopmentOutcomeAudit:
    payload = {
        "schema_version": JAM_OUTCOME_AUDIT_SCHEMA_VERSION,
        "sealed_market_periods_opened": 0,
        "threshold_changes": 0,
        "strategy_executions": 0,
        **values,
    }
    return JamSuccessorDevelopmentOutcomeAudit(
        **payload,
        audit_evidence_hash=universe_evidence_hash(payload),
    )


def audit_jam_successor_outcome_protocol(
    protocol: JamSuccessorDevelopmentOutcomeExecutionProtocol,
) -> bool:
    try:
        JamSuccessorDevelopmentOutcomeExecutionProtocol.model_validate(
            protocol.model_dump()
        )
    except ValueError:
        return False
    return True


def audit_jam_successor_outcome_result(
    result: JamSuccessorDevelopmentOutcomeResult,
) -> bool:
    try:
        JamSuccessorDevelopmentOutcomeResult.model_validate(result.model_dump())
    except ValueError:
        return False
    return True


def audit_jam_successor_outcome_audit(
    audit: JamSuccessorDevelopmentOutcomeAudit,
) -> bool:
    try:
        JamSuccessorDevelopmentOutcomeAudit.model_validate(audit.model_dump())
    except ValueError:
        return False
    return True
