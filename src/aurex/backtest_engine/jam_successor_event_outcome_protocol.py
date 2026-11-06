from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.jam_successor_distribution_protocol import (
    JAM_DISTRIBUTION_QUANTILES,
)
from aurex.backtest_engine.jam_successor_feature_specification import (
    JAM_FEATURE_IDS,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

JAM_EVENT_OUTCOME_PROTOCOL_SCHEMA_VERSION = "aurex-jam-successor-event-outcome-protocol-v1"
JAM_EVENT_OUTCOME_PROTOCOL_ID = "jam-successor-event-outcome-protocol-v1"
JAM_EVENT_OUTCOME_AUDIT_SCHEMA_VERSION = "aurex-jam-successor-event-outcome-protocol-audit-v1"
JAM_EVENT_OUTCOME_AUTHORIZATION = (
    "USER_INSTRUCTED_PROCEED_WITH_EXACT_NEXT_EVENT_AND_OUTCOME_PROTOCOL_STAGE"
)
JAM_EVENT_OUTCOME_AUTHORIZATION_SCOPE = (
    "AUTHORIZE_JAM_SUCCESSOR_EVENT_AND_OUTCOME_PROTOCOL_NO_RETURNS"
)
JAM_EVENT_OUTCOME_DECISION = (
    "PASS_EVENT_AND_OUTCOME_PROTOCOL_AWAIT_DEVELOPMENT_EVENT_PREVALENCE_AUTHORIZATION"
)
JAM_EVENT_OUTCOME_NEXT_AUTHORIZATION = (
    "AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_EVENT_PREVALENCE_NO_OUTCOMES"
)
JAM_EVENT_PREVALENCE_PASS_NEXT_AUTHORIZATION = (
    "AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_CALCULATION"
)

JAM_EVENT_CONDITION_SPECS = (
    (
        "EXTREME_AGGRESSIVE_SELL_FLOW",
        "shock_sell_flow_robust_z_5m",
        "GREATER_THAN_OR_EQUAL",
        "0.95",
    ),
    (
        "SELL_SIDE_DOMINANCE",
        "shock_sell_share_5m",
        "GREATER_THAN_OR_EQUAL",
        "0.5",
    ),
    (
        "NEGATIVE_SHOCK_PRICE_IMPACT",
        "shock_price_impact_bps_5m",
        "LESS_THAN_OR_EQUAL",
        "0.25",
    ),
    (
        "CONFIRMATION_FLOW_DECAY",
        "sell_flow_decay_ratio_3m_vs_5m",
        "LESS_THAN_OR_EQUAL",
        "0.5",
    ),
    (
        "CAUSAL_PRICE_RECLAIM",
        "reclaim_bps_vs_pre_shock_vwap",
        "GREATER_THAN_OR_EQUAL",
        "0.5",
    ),
)

JAM_EVENT_PREVALENCE_GATE_SPECS = (
    ("RAW_EVENT_COUNT_AT_LEAST_1000", "GREATER_THAN_OR_EQUAL", "1000", "COUNT"),
    (
        "NONOVERLAPPING_EVENT_COUNT_AT_LEAST_240",
        "GREATER_THAN_OR_EQUAL",
        "240",
        "COUNT",
    ),
    (
        "AT_LEAST_20_MONTHS_HAVE_5_EVENTS",
        "GREATER_THAN_OR_EQUAL",
        "20",
        "MONTH_COUNT",
    ),
    (
        "EVERY_QUARTER_HAS_AT_LEAST_15_EVENTS",
        "GREATER_THAN_OR_EQUAL",
        "15",
        "COUNT_PER_QUARTER",
    ),
    (
        "LARGEST_MONTH_EVENT_SHARE_AT_MOST_0_10",
        "LESS_THAN_OR_EQUAL",
        "0.10",
        "RATIO",
    ),
    (
        "LARGEST_DAY_EVENT_SHARE_AT_MOST_0_02",
        "LESS_THAN_OR_EQUAL",
        "0.02",
        "RATIO",
    ),
    (
        "ALL_ACCEPTED_EVENTS_HAVE_READY_FEATURES",
        "EQUAL",
        "0",
        "INVALID_EVENT_COUNT",
    ),
)

JAM_DEVELOPMENT_OUTCOME_GATE_SPECS = (
    (
        "OUTCOME_QUALIFIED_EVENTS_AT_LEAST_200",
        "GREATER_THAN_OR_EQUAL",
        "200",
        "COUNT",
    ),
    (
        "MATCHED_CONTROL_PAIRS_AT_LEAST_180",
        "GREATER_THAN_OR_EQUAL",
        "180",
        "COUNT",
    ),
    (
        "BASE_NET_MEAN_30M_AT_LEAST_5_BPS",
        "GREATER_THAN_OR_EQUAL",
        "5",
        "BASIS_POINTS",
    ),
    (
        "BASE_NET_PROFIT_FACTOR_AT_LEAST_1_20",
        "GREATER_THAN_OR_EQUAL",
        "1.20",
        "RATIO",
    ),
    (
        "STRESS_NET_MEAN_30M_POSITIVE",
        "GREATER_THAN",
        "0",
        "BASIS_POINTS",
    ),
    (
        "MATCHED_EXCESS_MEAN_30M_AT_LEAST_5_BPS",
        "GREATER_THAN_OR_EQUAL",
        "5",
        "BASIS_POINTS",
    ),
    (
        "CLUSTER_BOOTSTRAP_LOWER_95_BASE_NET_POSITIVE",
        "GREATER_THAN",
        "0",
        "BASIS_POINTS",
    ),
    (
        "CLUSTER_BOOTSTRAP_LOWER_95_MATCHED_EXCESS_POSITIVE",
        "GREATER_THAN",
        "0",
        "BASIS_POINTS",
    ),
    (
        "BOTH_CALENDAR_YEARS_BASE_NET_POSITIVE",
        "EQUAL",
        "2",
        "POSITIVE_YEAR_COUNT",
    ),
    (
        "AT_LEAST_6_OF_8_QUARTERS_BASE_NET_POSITIVE",
        "GREATER_THAN_OR_EQUAL",
        "6",
        "POSITIVE_QUARTER_COUNT",
    ),
    (
        "LARGEST_MONTH_ABSOLUTE_RETURN_CONTRIBUTION_AT_MOST_0_20",
        "LESS_THAN_OR_EQUAL",
        "0.20",
        "RATIO",
    ),
)

JAM_SEALED_VALIDATION_GATE_SPECS = (
    (
        "VALIDATION_OUTCOME_QUALIFIED_EVENTS_AT_LEAST_80",
        "GREATER_THAN_OR_EQUAL",
        "80",
        "COUNT",
    ),
    (
        "VALIDATION_MATCHED_CONTROL_PAIRS_AT_LEAST_60",
        "GREATER_THAN_OR_EQUAL",
        "60",
        "COUNT",
    ),
    (
        "VALIDATION_BASE_NET_MEAN_30M_AT_LEAST_5_BPS",
        "GREATER_THAN_OR_EQUAL",
        "5",
        "BASIS_POINTS",
    ),
    (
        "VALIDATION_BASE_NET_PROFIT_FACTOR_AT_LEAST_1_15",
        "GREATER_THAN_OR_EQUAL",
        "1.15",
        "RATIO",
    ),
    (
        "VALIDATION_STRESS_NET_MEAN_30M_POSITIVE",
        "GREATER_THAN",
        "0",
        "BASIS_POINTS",
    ),
    (
        "VALIDATION_MATCHED_EXCESS_MEAN_30M_AT_LEAST_5_BPS",
        "GREATER_THAN_OR_EQUAL",
        "5",
        "BASIS_POINTS",
    ),
    (
        "VALIDATION_AT_LEAST_3_OF_4_QUARTERS_BASE_NET_POSITIVE",
        "GREATER_THAN_OR_EQUAL",
        "3",
        "POSITIVE_QUARTER_COUNT",
    ),
)

JAM_SEALED_HOLDOUT_GATE_SPECS = tuple(
    (
        gate_id.replace("VALIDATION_", "HOLDOUT_", 1),
        comparison,
        threshold,
        units,
    )
    for gate_id, comparison, threshold, units in JAM_SEALED_VALIDATION_GATE_SPECS
)


def normalize_decimal_string(value: str) -> str:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Jam event/outcome decimal is invalid") from exc
    if not parsed.is_finite():
        raise ValueError("Jam event/outcome decimal must be finite")
    return format(parsed, "f")


class JamEventCondition(BaseModel):
    condition_id: str = Field(min_length=1)
    feature_id: str = Field(min_length=1)
    comparison: Literal["GREATER_THAN_OR_EQUAL", "LESS_THAN_OR_EQUAL"]
    source_quantile: str
    frozen_threshold: str
    mechanism_role: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")

    @field_validator("source_quantile")
    @classmethod
    def normalize_quantile(cls, value: str) -> str:
        normalized = normalize_decimal_string(value)
        if normalized not in JAM_DISTRIBUTION_QUANTILES:
            raise ValueError("Jam event condition quantile was not profiled")
        return normalized

    @field_validator("frozen_threshold")
    @classmethod
    def normalize_threshold(cls, value: str) -> str:
        return normalize_decimal_string(value)


class JamEventDefinition(BaseModel):
    event_id: Literal["J2-P01-SELL-FLOW-EXHAUSTION-RECLAIM-EVENT-V1"] = (
        "J2-P01-SELL-FLOW-EXHAUSTION-RECLAIM-EVENT-V1"
    )
    evaluation_time: Literal["AFTER_EVALUATION_MINUTE_CLOSE"] = "AFTER_EVALUATION_MINUTE_CLOSE"
    direction: Literal["LONG_ONLY"] = "LONG_ONLY"
    conditions: list[JamEventCondition] = Field(min_length=5, max_length=5)
    boolean_rule: Literal["ALL_FIVE_CONDITIONS_TRUE"] = "ALL_FIVE_CONDITIONS_TRUE"
    threshold_variants_permitted: Literal[False] = False
    learned_model_permitted: Literal[False] = False
    ranking_or_score_permitted: Literal[False] = False
    missing_feature_policy: Literal["NOT_AN_EVENT"] = "NOT_AN_EVENT"

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_definition(self) -> JamEventDefinition:
        observed = [
            (
                item.condition_id,
                item.feature_id,
                item.comparison,
                item.source_quantile,
            )
            for item in self.conditions
        ]
        if observed != list(JAM_EVENT_CONDITION_SPECS):
            raise ValueError("Jam event condition matrix changed")
        if any(item.feature_id not in JAM_FEATURE_IDS for item in self.conditions):
            raise ValueError("Jam event condition feature changed")
        return self


class JamEventSuppressionPlan(BaseModel):
    raw_event_identity: Literal["EVALUATION_OPEN_TIME_MS"] = "EVALUATION_OPEN_TIME_MS"
    ordering: Literal["ASCENDING_EVALUATION_OPEN_TIME_MS"] = "ASCENDING_EVALUATION_OPEN_TIME_MS"
    accepted_event_rule: Literal[
        "FIRST_RAW_EVENT_THEN_FIRST_WITH_AT_LEAST_60_MINUTES_SEPARATION"
    ] = "FIRST_RAW_EVENT_THEN_FIRST_WITH_AT_LEAST_60_MINUTES_SEPARATION"
    minimum_separation_minutes: Literal[60] = 60
    suppressed_events_retained_for_audit: Literal[True] = True
    suppressed_events_create_outcomes: Literal[False] = False
    reset_at_evidence_partition: Literal[True] = True

    model_config = ConfigDict(extra="forbid")


class JamProtocolGate(BaseModel):
    gate_id: str = Field(min_length=1)
    comparison: Literal[
        "GREATER_THAN_OR_EQUAL",
        "LESS_THAN_OR_EQUAL",
        "GREATER_THAN",
        "EQUAL",
    ]
    threshold: str
    units: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")

    @field_validator("threshold")
    @classmethod
    def normalize_threshold(cls, value: str) -> str:
        return normalize_decimal_string(value)


class JamOutcomeHorizon(BaseModel):
    horizon_minutes: Literal[15, 30, 60]
    role: Literal["NONSELECTABLE_DIAGNOSTIC", "PRIMARY"]
    entry_minute_offset: Literal[1] = 1
    exit_minute_offset: Literal[15, 30, 60]
    entry_reference: Literal["FIRST_AGGREGATE_TRADE_PRICE"] = "FIRST_AGGREGATE_TRADE_PRICE"
    exit_reference: Literal["LAST_AGGREGATE_TRADE_PRICE"] = "LAST_AGGREGATE_TRADE_PRICE"

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_horizon(self) -> JamOutcomeHorizon:
        if self.exit_minute_offset != self.horizon_minutes or (self.horizon_minutes == 30) != (
            self.role == "PRIMARY"
        ):
            raise ValueError("Jam outcome horizon role changed")
        return self


class JamOutcomePricingPlan(BaseModel):
    symbol: Literal["BTCUSDT"] = "BTCUSDT"
    venue_product: Literal["BINANCE_SPOT"] = "BINANCE_SPOT"
    direction: Literal["LONG_ONLY"] = "LONG_ONLY"
    tick_size_quote: Literal["0.01"] = "0.01"
    base_commission_rate_per_side: Literal["0.0010"] = "0.0010"
    stress_commission_rate_per_side: Literal["0.0015"] = "0.0015"
    base_adverse_ticks_per_fill: Literal[2] = 2
    stress_adverse_ticks_per_fill: Literal[10] = 10
    entry_fill_formula: Literal["ENTRY_REFERENCE_PLUS_ADVERSE_TICKS_MULTIPLIED_BY_TICK_SIZE"] = (
        "ENTRY_REFERENCE_PLUS_ADVERSE_TICKS_MULTIPLIED_BY_TICK_SIZE"
    )
    exit_fill_formula: Literal["EXIT_REFERENCE_MINUS_ADVERSE_TICKS_MULTIPLIED_BY_TICK_SIZE"] = (
        "EXIT_REFERENCE_MINUS_ADVERSE_TICKS_MULTIPLIED_BY_TICK_SIZE"
    )
    net_return_bps_formula: Literal[
        "10000_MULTIPLIED_BY_((EXIT_FILL_MULTIPLIED_BY_(1-EXIT_FEE))_DIVIDED_BY_(ENTRY_FILL_MULTIPLIED_BY_(1+ENTRY_FEE))_-_1)"
    ] = (
        "10000_MULTIPLIED_BY_((EXIT_FILL_MULTIPLIED_BY_(1-EXIT_FEE))_"
        "DIVIDED_BY_(ENTRY_FILL_MULTIPLIED_BY_(1+ENTRY_FEE))_-_1)"
    )
    maximum_favorable_excursion_formula: Literal[
        "10000_MULTIPLIED_BY_(MAXIMUM_HIGH_MINUTES_1_TO_HORIZON_DIVIDED_BY_ENTRY_FILL_-_1)"
    ] = "10000_MULTIPLIED_BY_(MAXIMUM_HIGH_MINUTES_1_TO_HORIZON_DIVIDED_BY_ENTRY_FILL_-_1)"
    maximum_adverse_excursion_formula: Literal[
        "10000_MULTIPLIED_BY_(MINIMUM_LOW_MINUTES_1_TO_HORIZON_DIVIDED_BY_ENTRY_FILL_-_1)"
    ] = "10000_MULTIPLIED_BY_(MINIMUM_LOW_MINUTES_1_TO_HORIZON_DIVIDED_BY_ENTRY_FILL_-_1)"
    all_path_minutes_required: Literal[True] = True
    quarantine_or_absence_policy: Literal["OUTCOME_UNAVAILABLE_NO_SYNTHESIS"] = (
        "OUTCOME_UNAVAILABLE_NO_SYNTHESIS"
    )
    cross_partition_outcome_permitted: Literal[False] = False
    horizons: list[JamOutcomeHorizon] = Field(min_length=3, max_length=3)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_pricing(self) -> JamOutcomePricingPlan:
        if [(item.horizon_minutes, item.role) for item in self.horizons] != [
            (15, "NONSELECTABLE_DIAGNOSTIC"),
            (30, "PRIMARY"),
            (60, "NONSELECTABLE_DIAGNOSTIC"),
        ]:
            raise ValueError("Jam outcome horizon matrix changed")
        return self


class JamMatchedControlPlan(BaseModel):
    purpose: Literal["ESTIMATE_EVENT_EXCESS_RETURN_VERSUS_TEMPORAL_ACTIVITY_MATCH"] = (
        "ESTIMATE_EVENT_EXCESS_RETURN_VERSUS_TEMPORAL_ACTIVITY_MATCH"
    )
    control_source: Literal["READY_NON_EVENT_DEVELOPMENT_ROWS"] = "READY_NON_EVENT_DEVELOPMENT_ROWS"
    exact_match_fields: list[str] = Field(min_length=3, max_length=3)
    activity_feature: Literal["baseline_sell_quote_median_120m"] = "baseline_sell_quote_median_120m"
    activity_bins: Literal["DEVELOPMENT_Q25_Q50_Q75_QUARTILES"] = (
        "DEVELOPMENT_Q25_Q50_Q75_QUARTILES"
    )
    event_exclusion_radius_minutes: Literal[1440] = 1_440
    one_to_one_without_replacement: Literal[True] = True
    control_minimum_separation_minutes: Literal[60] = 60
    selection_order: Literal["ASCENDING_EVENT_TIME"] = "ASCENDING_EVENT_TIME"
    candidate_choice: Literal["MINIMUM_ABSOLUTE_TIME_DISTANCE_THEN_EARLIER_TIMESTAMP"] = (
        "MINIMUM_ABSOLUTE_TIME_DISTANCE_THEN_EARLIER_TIMESTAMP"
    )
    future_outcome_used_for_matching: Literal[False] = False
    unmatched_event_policy: Literal["RETAIN_EVENT_EXCLUDE_FROM_MATCHED_CONTRAST"] = (
        "RETAIN_EVENT_EXCLUDE_FROM_MATCHED_CONTRAST"
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("exact_match_fields")
    @classmethod
    def validate_fields(cls, value: list[str]) -> list[str]:
        expected = [
            "CALENDAR_MONTH",
            "UTC_HOUR_OF_DAY",
            "BASELINE_SELL_QUOTE_MEDIAN_QUARTILE",
        ]
        if value != expected:
            raise ValueError("Jam matched-control fields changed")
        return value


class JamStatisticalPlan(BaseModel):
    primary_horizon_minutes: Literal[30] = 30
    primary_direction: Literal["LONG"] = "LONG"
    primary_event_definition_count: Literal[1] = 1
    selectable_horizon_count: Literal[1] = 1
    alpha: Literal["0.05"] = "0.05"
    multiplicity_correction: Literal["NOT_REQUIRED_ONE_PRIMARY_EVENT_ONE_PRIMARY_HORIZON"] = (
        "NOT_REQUIRED_ONE_PRIMARY_EVENT_ONE_PRIMARY_HORIZON"
    )
    bootstrap_method: Literal["CALENDAR_MONTH_CLUSTER_BOOTSTRAP_WITH_REPLACEMENT"] = (
        "CALENDAR_MONTH_CLUSTER_BOOTSTRAP_WITH_REPLACEMENT"
    )
    bootstrap_repetitions: Literal[10000] = 10_000
    bootstrap_seed: Literal[20260805] = 20_260_805
    confidence_interval: Literal["ONE_SIDED_95_PERCENTILE_LOWER_BOUND"] = (
        "ONE_SIDED_95_PERCENTILE_LOWER_BOUND"
    )
    diagnostic_horizons_may_rescue_primary: Literal[False] = False
    path_diagnostics_may_rescue_primary: Literal[False] = False
    failed_gate_may_be_waived: Literal[False] = False
    post_outcome_threshold_change_permitted: Literal[False] = False

    model_config = ConfigDict(extra="forbid")


class JamEvidencePartitionPlan(BaseModel):
    development: Literal["2019-01_THROUGH_2020-12"] = "2019-01_THROUGH_2020-12"
    sealed_validation: Literal["2021-01_THROUGH_2021-12"] = "2021-01_THROUGH_2021-12"
    sealed_holdout: Literal["2022-01_THROUGH_2022-12"] = "2022-01_THROUGH_2022-12"
    consumed_periods: list[str] = Field(min_length=2)
    development_outcomes_must_pass_before_validation: Literal[True] = True
    validation_requires_new_explicit_authorization: Literal[True] = True
    validation_must_pass_before_holdout: Literal[True] = True
    holdout_requires_new_explicit_authorization: Literal[True] = True
    threshold_reestimation_after_development: Literal[False] = False
    threshold_reestimation_after_validation: Literal[False] = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("consumed_periods")
    @classmethod
    def normalize_periods(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})


class JamSuccessorEventOutcomeProtocol(BaseModel):
    schema_version: Literal["aurex-jam-successor-event-outcome-protocol-v1"] = (
        JAM_EVENT_OUTCOME_PROTOCOL_SCHEMA_VERSION
    )
    protocol_id: Literal["jam-successor-event-outcome-protocol-v1"] = JAM_EVENT_OUTCOME_PROTOCOL_ID
    frozen_at: datetime
    status: Literal["FROZEN_PRE_EVENT_PRE_OUTCOME_NO_RETURNS"] = (
        "FROZEN_PRE_EVENT_PRE_OUTCOME_NO_RETURNS"
    )
    authorization_record: Literal[
        "USER_INSTRUCTED_PROCEED_WITH_EXACT_NEXT_EVENT_AND_OUTCOME_PROTOCOL_STAGE"
    ] = JAM_EVENT_OUTCOME_AUTHORIZATION
    authorization_scope: Literal[
        "AUTHORIZE_JAM_SUCCESSOR_EVENT_AND_OUTCOME_PROTOCOL_NO_RETURNS"
    ] = JAM_EVENT_OUTCOME_AUTHORIZATION_SCOPE
    distribution_protocol_path: str
    distribution_protocol_file_sha256: str
    distribution_protocol_evidence_hash: str
    distribution_result_path: str
    distribution_result_file_sha256: str
    distribution_result_evidence_hash: str
    distribution_audit_path: str
    distribution_audit_file_sha256: str
    distribution_audit_evidence_hash: str
    feature_rows_path: str
    feature_rows_file_sha256: str
    feature_rows_schema_hash: str
    feature_rows_bytes: int = Field(gt=0)
    feature_specification_evidence_hash: str
    builder_contract_hash: str
    event_definition: JamEventDefinition
    event_suppression: JamEventSuppressionPlan
    prevalence_gates: list[JamProtocolGate] = Field(min_length=7, max_length=7)
    outcome_pricing: JamOutcomePricingPlan
    matched_control: JamMatchedControlPlan
    statistical_plan: JamStatisticalPlan
    development_outcome_gates: list[JamProtocolGate] = Field(
        min_length=11,
        max_length=11,
    )
    sealed_validation_gates: list[JamProtocolGate] = Field(
        min_length=7,
        max_length=7,
    )
    sealed_holdout_gates: list[JamProtocolGate] = Field(
        min_length=7,
        max_length=7,
    )
    evidence_partitions: JamEvidencePartitionPlan
    distribution_statistics_accessed: list[str] = Field(
        min_length=5,
        max_length=5,
    )
    new_real_market_rows_inspected: Literal[0] = 0
    event_flags_calculated: Literal[0] = 0
    accepted_events_calculated: Literal[0] = 0
    future_labels_calculated: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)
    strategy_executions: Literal[0] = 0
    creates_strategy: Literal[False] = False
    creates_signal: Literal[False] = False
    creates_candidate: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_testnet_order_authority: Literal[False] = False
    creates_production_authority: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    decision: Literal[
        "PASS_EVENT_AND_OUTCOME_PROTOCOL_AWAIT_DEVELOPMENT_EVENT_PREVALENCE_AUTHORIZATION"
    ] = JAM_EVENT_OUTCOME_DECISION
    next_required_authorization: Literal[
        "AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_EVENT_PREVALENCE_NO_OUTCOMES"
    ] = JAM_EVENT_OUTCOME_NEXT_AUTHORIZATION
    prevalence_pass_next_authorization: Literal[
        "AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_CALCULATION"
    ] = JAM_EVENT_PREVALENCE_PASS_NEXT_AUTHORIZATION
    limitations: list[str] = Field(min_length=20)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "distribution_protocol_file_sha256",
        "distribution_protocol_evidence_hash",
        "distribution_result_file_sha256",
        "distribution_result_evidence_hash",
        "distribution_audit_file_sha256",
        "distribution_audit_evidence_hash",
        "feature_rows_file_sha256",
        "feature_rows_schema_hash",
        "feature_specification_evidence_hash",
        "builder_contract_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "distribution_statistics_accessed",
        "future_labels_calculated",
        "return_metrics_calculated",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_protocol(self) -> JamSuccessorEventOutcomeProtocol:
        prevalence = [
            (item.gate_id, item.comparison, item.threshold, item.units)
            for item in self.prevalence_gates
        ]
        development = [
            (item.gate_id, item.comparison, item.threshold, item.units)
            for item in self.development_outcome_gates
        ]
        validation = [
            (item.gate_id, item.comparison, item.threshold, item.units)
            for item in self.sealed_validation_gates
        ]
        holdout = [
            (item.gate_id, item.comparison, item.threshold, item.units)
            for item in self.sealed_holdout_gates
        ]
        if (
            prevalence != list(JAM_EVENT_PREVALENCE_GATE_SPECS)
            or development != list(JAM_DEVELOPMENT_OUTCOME_GATE_SPECS)
            or validation != list(JAM_SEALED_VALIDATION_GATE_SPECS)
            or holdout != list(JAM_SEALED_HOLDOUT_GATE_SPECS)
        ):
            raise ValueError("Jam event/outcome gate matrix changed")
        expected_access = sorted(
            f"{item.feature_id}|{item.source_quantile}|{item.frozen_threshold}"
            for item in self.event_definition.conditions
        )
        if self.distribution_statistics_accessed != expected_access:
            raise ValueError("Jam event distribution access changed")
        if (
            self.future_labels_calculated
            or self.return_metrics_calculated
            or self.event_flags_calculated
            or self.accepted_events_calculated
        ):
            raise ValueError("Jam event/outcome protocol calculated an outcome")
        expected_hash = universe_evidence_hash(self.model_dump(exclude={"protocol_evidence_hash"}))
        if self.protocol_evidence_hash != expected_hash:
            raise ValueError("Jam event/outcome protocol hash changed")
        return self


class JamSuccessorEventOutcomeProtocolAudit(BaseModel):
    schema_version: Literal["aurex-jam-successor-event-outcome-protocol-audit-v1"] = (
        JAM_EVENT_OUTCOME_AUDIT_SCHEMA_VERSION
    )
    audited_at: datetime
    protocol_path: str
    protocol_file_sha256: str
    protocol_evidence_hash: str
    distribution_result_evidence_hash: str
    distribution_audit_evidence_hash: str
    feature_rows_file_sha256: str
    event_condition_count_reconstructed: Literal[5] = 5
    prevalence_gate_count_reconstructed: Literal[7] = 7
    development_outcome_gate_count_reconstructed: Literal[11] = 11
    sealed_validation_gate_count_reconstructed: Literal[7] = 7
    sealed_holdout_gate_count_reconstructed: Literal[7] = 7
    event_flags_calculated: Literal[0] = 0
    future_labels_calculated: Literal[0] = 0
    return_metrics_calculated: Literal[0] = 0
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "distribution_result_evidence_hash",
        "distribution_audit_evidence_hash",
        "feature_rows_file_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> JamSuccessorEventOutcomeProtocolAudit:
        expected_hash = universe_evidence_hash(self.model_dump(exclude={"audit_evidence_hash"}))
        if self.audit_evidence_hash != expected_hash:
            raise ValueError("Jam event/outcome audit hash changed")
        return self


def protocol_gate_models(
    specs: tuple[tuple[str, str, str, str], ...],
) -> list[JamProtocolGate]:
    return [
        JamProtocolGate(
            gate_id=gate_id,
            comparison=comparison,
            threshold=threshold,
            units=units,
        )
        for gate_id, comparison, threshold, units in specs
    ]


def build_jam_successor_event_outcome_protocol(
    **values,
) -> JamSuccessorEventOutcomeProtocol:
    payload = {
        "schema_version": JAM_EVENT_OUTCOME_PROTOCOL_SCHEMA_VERSION,
        "protocol_id": JAM_EVENT_OUTCOME_PROTOCOL_ID,
        "status": "FROZEN_PRE_EVENT_PRE_OUTCOME_NO_RETURNS",
        "authorization_record": JAM_EVENT_OUTCOME_AUTHORIZATION,
        "authorization_scope": JAM_EVENT_OUTCOME_AUTHORIZATION_SCOPE,
        "event_suppression": JamEventSuppressionPlan(),
        "prevalence_gates": protocol_gate_models(JAM_EVENT_PREVALENCE_GATE_SPECS),
        "outcome_pricing": JamOutcomePricingPlan(
            horizons=[
                JamOutcomeHorizon(
                    horizon_minutes=15,
                    role="NONSELECTABLE_DIAGNOSTIC",
                    exit_minute_offset=15,
                ),
                JamOutcomeHorizon(
                    horizon_minutes=30,
                    role="PRIMARY",
                    exit_minute_offset=30,
                ),
                JamOutcomeHorizon(
                    horizon_minutes=60,
                    role="NONSELECTABLE_DIAGNOSTIC",
                    exit_minute_offset=60,
                ),
            ]
        ),
        "matched_control": JamMatchedControlPlan(
            exact_match_fields=[
                "CALENDAR_MONTH",
                "UTC_HOUR_OF_DAY",
                "BASELINE_SELL_QUOTE_MEDIAN_QUARTILE",
            ]
        ),
        "statistical_plan": JamStatisticalPlan(),
        "development_outcome_gates": protocol_gate_models(JAM_DEVELOPMENT_OUTCOME_GATE_SPECS),
        "sealed_validation_gates": protocol_gate_models(JAM_SEALED_VALIDATION_GATE_SPECS),
        "sealed_holdout_gates": protocol_gate_models(JAM_SEALED_HOLDOUT_GATE_SPECS),
        "evidence_partitions": JamEvidencePartitionPlan(
            consumed_periods=[
                "2023-01_THROUGH_2025-12_JAM_FAMILY_DECISION_EVIDENCE",
                "2026_JAM_EXPLORATORY_AND_FORWARD_PERIODS",
            ]
        ),
        "new_real_market_rows_inspected": 0,
        "event_flags_calculated": 0,
        "accepted_events_calculated": 0,
        "future_labels_calculated": [],
        "return_metrics_calculated": [],
        "strategy_executions": 0,
        "creates_strategy": False,
        "creates_signal": False,
        "creates_candidate": False,
        "creates_paper_eligibility": False,
        "creates_testnet_order_authority": False,
        "creates_production_authority": False,
        "creates_live_eligibility": False,
        "decision": JAM_EVENT_OUTCOME_DECISION,
        "next_required_authorization": JAM_EVENT_OUTCOME_NEXT_AUTHORIZATION,
        "prevalence_pass_next_authorization": (JAM_EVENT_PREVALENCE_PASS_NEXT_AUTHORIZATION),
        **values,
    }
    payload["distribution_statistics_accessed"] = sorted(
        set(payload["distribution_statistics_accessed"])
    )
    payload["limitations"] = sorted(set(payload["limitations"]))
    return JamSuccessorEventOutcomeProtocol(
        **payload,
        protocol_evidence_hash=universe_evidence_hash(payload),
    )


def build_jam_successor_event_outcome_audit(
    **values,
) -> JamSuccessorEventOutcomeProtocolAudit:
    payload = {
        "schema_version": JAM_EVENT_OUTCOME_AUDIT_SCHEMA_VERSION,
        "event_condition_count_reconstructed": 5,
        "prevalence_gate_count_reconstructed": 7,
        "development_outcome_gate_count_reconstructed": 11,
        "sealed_validation_gate_count_reconstructed": 7,
        "sealed_holdout_gate_count_reconstructed": 7,
        "event_flags_calculated": 0,
        "future_labels_calculated": 0,
        "return_metrics_calculated": 0,
        **values,
    }
    return JamSuccessorEventOutcomeProtocolAudit(
        **payload,
        audit_evidence_hash=universe_evidence_hash(payload),
    )


def audit_jam_successor_event_outcome_protocol(
    protocol: JamSuccessorEventOutcomeProtocol,
) -> bool:
    try:
        JamSuccessorEventOutcomeProtocol.model_validate(protocol.model_dump())
    except ValueError:
        return False
    return True


def audit_jam_successor_event_outcome_audit(
    audit: JamSuccessorEventOutcomeProtocolAudit,
) -> bool:
    try:
        JamSuccessorEventOutcomeProtocolAudit.model_validate(audit.model_dump())
    except ValueError:
        return False
    return True
