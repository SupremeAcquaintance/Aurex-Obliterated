from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_r4_protocol import R4_DECISION_SYMBOLS
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

U1_PRIMARY_PROTOCOL_SCHEMA_VERSION = (
    "aurex-u1-volatility-managed-broad-spot-beta-protocol-v1"
)

U1_REQUIRED_DIAGNOSTICS = [
    "active_market_count_at_rebalance",
    "benchmark_comparison",
    "cost_decomposition",
    "cost_stress",
    "drawdown_and_exposure_over_time",
    "leave_one_market_out",
    "monthly_net_returns",
    "quarterly_fold_results",
    "realized_market_variance_and_target_exposure",
    "symbol_gross_profit_concentration",
    "turnover",
]

U1_FORBIDDEN_PARTITIONS = ["FORWARD", "HOLDOUT", "VALIDATION"]


class U1PrimarySignalProtocol(BaseModel):
    signal_id: Literal["broad_spot_inverse_variance_28d_primary"] = (
        "broad_spot_inverse_variance_28d_primary"
    )
    lookback_intervals: Literal[168] = 168
    close_observations: Literal[169] = 169
    intervals_per_day: Literal[6] = 6
    annualization_intervals: Literal[2190] = 2190
    input_price: Literal["CLOSE"] = "CLOSE"
    signal_bar_rule: Literal["PRIOR_COMPLETED_4H_CLOSE"] = "PRIOR_COMPLETED_4H_CLOSE"
    constituent_return_formula: Literal["NATURAL_LOG_CLOSE_RATIO"] = (
        "NATURAL_LOG_CLOSE_RATIO"
    )
    broad_market_return_formula: Literal[
        "ARITHMETIC_MEAN_ACTIVE_CONSTITUENT_LOG_RETURNS_EACH_INTERVAL"
    ] = "ARITHMETIC_MEAN_ACTIVE_CONSTITUENT_LOG_RETURNS_EACH_INTERVAL"
    realized_variance_formula: Literal[
        "MEAN_SQUARED_BROAD_MARKET_LOG_RETURN_TIMES_2190"
    ] = "MEAN_SQUARED_BROAD_MARKET_LOG_RETURN_TIMES_2190"
    mean_return_subtracted: Literal[False] = False
    target_annualized_volatility_decimal: Literal["0.60"] = "0.60"
    target_annualized_variance_decimal: Literal["0.36"] = "0.36"
    target_exposure_formula: Literal[
        "MIN_ONE_TARGET_ANNUAL_VARIANCE_DIVIDED_BY_REALIZED_ANNUAL_VARIANCE"
    ] = "MIN_ONE_TARGET_ANNUAL_VARIANCE_DIVIDED_BY_REALIZED_ANNUAL_VARIANCE"
    zero_realized_variance_exposure: Literal["1"] = "1"
    minimum_target_exposure: Literal["0"] = "0"
    maximum_target_exposure: Literal["1"] = "1"
    parameter_search_allowed: Literal[False] = False

    model_config = ConfigDict(extra="forbid")


class U1PrimaryBenchmarkProtocol(BaseModel):
    benchmark_id: Literal["static_broad_spot_equal_weight_v1"] = (
        "static_broad_spot_equal_weight_v1"
    )
    target_exposure: Literal["1"] = "1"
    constituent_weighting: Literal["EQUAL_WEIGHT_ALL_ACTIVE_DECISION_MARKETS"] = (
        "EQUAL_WEIGHT_ALL_ACTIVE_DECISION_MARKETS"
    )
    rebalance_schedule: Literal["MATCH_PRIMARY_168_BARS"] = (
        "MATCH_PRIMARY_168_BARS"
    )
    orders_fills_costs_and_availability: Literal["IDENTICAL_TO_PRIMARY"] = (
        "IDENTICAL_TO_PRIMARY"
    )
    selectable: Literal[False] = False
    creates_candidate: Literal[False] = False

    model_config = ConfigDict(extra="forbid")


class U1PrimaryFold(BaseModel):
    fold_id: str = Field(min_length=1, max_length=128)
    evaluation_start: datetime
    evaluation_end: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("evaluation_start", "evaluation_end")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_fold(self) -> U1PrimaryFold:
        if self.evaluation_end <= self.evaluation_start:
            raise ValueError("U1 fold end must follow its start")
        return self


class U1PrimaryPortfolioProtocol(BaseModel):
    direction: Literal["LONG_SPOT_AND_CASH_ONLY"] = "LONG_SPOT_AND_CASH_ONLY"
    initial_capital: Literal["1000"] = "1000"
    constituent_selection: Literal["ALL_ACTIVE_DECISION_MARKETS"] = (
        "ALL_ACTIVE_DECISION_MARKETS"
    )
    constituent_weighting: Literal["EQUAL_WEIGHT_WITHIN_TARGET_EXPOSURE"] = (
        "EQUAL_WEIGHT_WITHIN_TARGET_EXPOSURE"
    )
    rebalance_bars: Literal[168] = 168
    rebalance_calendar_duration: Literal["28_DAYS"] = "28_DAYS"
    rebalance_semantics: Literal["FULL_ROTATION"] = "FULL_ROTATION"
    signal_semantics: Literal["CLOSED_4H_BAR"] = "CLOSED_4H_BAR"
    entry_semantics: Literal["NEXT_4H_OPEN"] = "NEXT_4H_OPEN"
    exit_semantics: Literal["NEXT_REBALANCE_OR_END_OF_WINDOW"] = (
        "NEXT_REBALANCE_OR_END_OF_WINDOW"
    )
    unused_exposure_asset: Literal["USDT_CASH"] = "USDT_CASH"
    maximum_gross_exposure_percent: Literal["100"] = "100"
    maximum_open_positions: Literal[35] = 35
    minimum_active_markets: Literal[20] = 20
    quantity_increment_assumption: Literal["1E-8"] = "1E-8"
    price_increment_assumption: Literal["1E-8"] = "1E-8"
    no_fixed_stop: Literal[True] = True
    no_leverage: Literal[True] = True
    no_shorting: Literal[True] = True
    no_pyramiding: Literal[True] = True

    model_config = ConfigDict(extra="forbid")


class U1PrimaryAvailabilityProtocol(BaseModel):
    complete_data_requirement: Literal[
        "BLOCK_LEADING_INTERNAL_DUPLICATE_OR_RESUMED_GAPS"
    ] = "BLOCK_LEADING_INTERNAL_DUPLICATE_OR_RESUMED_GAPS"
    terminal_unavailable_unheld_action: Literal[
        "REMOVE_PERMANENTLY_FROM_ACTIVE_MARKET_SET"
    ] = "REMOVE_PERMANENTLY_FROM_ACTIVE_MARKET_SET"
    terminal_unavailable_held_action: Literal[
        "WRITE_OFF_TO_ZERO_AT_FIRST_MISSING_BAR"
    ] = "WRITE_OFF_TO_ZERO_AT_FIRST_MISSING_BAR"
    writeoff_exit_commission: Literal["0"] = "0"
    writeoff_exit_slippage: Literal["0"] = "0"
    renormalize_remaining_weights: Literal[True] = True
    minimum_active_market_breach_action: Literal["BLOCK_REPLAY"] = "BLOCK_REPLAY"
    synthetic_candles_allowed: Literal[False] = False
    replacement_markets_allowed: Literal[False] = False

    model_config = ConfigDict(extra="forbid")


class U1PrimaryCostProtocol(BaseModel):
    commission_percent_per_side: Literal["0.10"] = "0.10"
    adverse_slippage_percent_per_side: Literal["0.05"] = "0.05"
    funding_percent: Literal["0"] = "0"
    borrow_percent: Literal["0"] = "0"
    stress_multipliers: list[Decimal] = Field(min_length=3, max_length=3)

    model_config = ConfigDict(extra="forbid")

    @field_validator("stress_multipliers")
    @classmethod
    def validate_multipliers(cls, value: list[Decimal]) -> list[Decimal]:
        if value != [Decimal("1"), Decimal("1.5"), Decimal("2")]:
            raise ValueError("U1 cost stress multipliers are fixed")
        return value


class U1PrimaryGates(BaseModel):
    primary_net_pl_strictly_positive: Literal[True] = True
    minimum_primary_profit_factor: Literal["1.15"] = "1.15"
    maximum_primary_drawdown_percent: Literal["20"] = "20"
    minimum_primary_completed_trades: Literal[100] = 100
    minimum_positive_temporal_folds: Literal[6] = 6
    total_temporal_folds: Literal[8] = 8
    double_cost_net_pl_strictly_positive: Literal[True] = True
    minimum_leave_one_market_out_positive_fraction: Literal["0.80"] = "0.80"
    maximum_single_symbol_gross_profit_fraction: Literal["0.25"] = "0.25"
    maximum_top_five_gross_profit_fraction: Literal["0.70"] = "0.70"
    primary_realized_volatility_below_benchmark: Literal[True] = True
    primary_drawdown_not_above_benchmark: Literal[True] = True
    primary_return_to_drawdown_not_below_benchmark: Literal[True] = True
    all_gates_required: Literal[True] = True

    model_config = ConfigDict(extra="forbid")


class U1PrimarySelectionControl(BaseModel):
    selectable_primary_count: Literal[1] = 1
    selectable_parameter_sets: Literal[1] = 1
    falsification_variants: Literal[0] = 0
    adaptive_parameter_selection: Literal[False] = False
    nested_selection_required: Literal[False] = False
    multiplicity_treatment: Literal[
        "NO_CORRECTION_REQUIRED_FOR_ONE_FIXED_RETURN_TESTED_MECHANISM"
    ] = "NO_CORRECTION_REQUIRED_FOR_ONE_FIXED_RETURN_TESTED_MECHANISM"
    development_pass_creates_eligible_strategy: Literal[False] = False
    post_pass_action: Literal[
        "FREEZE_SEPARATE_2025_INTERNAL_VALIDATION_CANDIDATE"
    ] = "FREEZE_SEPARATE_2025_INTERNAL_VALIDATION_CANDIDATE"
    failure_action: Literal["STOP_VOLATILITY_MANAGED_BROAD_SPOT_BETA"] = (
        "STOP_VOLATILITY_MANAGED_BROAD_SPOT_BETA"
    )
    rescue_variants_allowed: Literal[False] = False

    model_config = ConfigDict(extra="forbid")


class U1PrimaryProtocol(BaseModel):
    schema_version: Literal[
        "aurex-u1-volatility-managed-broad-spot-beta-protocol-v1"
    ] = U1_PRIMARY_PROTOCOL_SCHEMA_VERSION
    protocol_id: Literal["u1-volatility-managed-broad-spot-beta-v1"] = (
        "u1-volatility-managed-broad-spot-beta-v1"
    )
    protocol_version: Literal["1.0.0"] = "1.0.0"
    registered_at: datetime
    status: Literal["FROZEN_PRE_DEVELOPMENT_OUTCOME"] = (
        "FROZEN_PRE_DEVELOPMENT_OUTCOME"
    )
    research_class: Literal["DEVELOPMENT_ONLY_UNRELATED_MECHANISM"] = (
        "DEVELOPMENT_ONLY_UNRELATED_MECHANISM"
    )
    mechanism_family: Literal["VOLATILITY_MANAGED_BROAD_SPOT_BETA"] = (
        "VOLATILITY_MANAGED_BROAD_SPOT_BETA"
    )
    hypothesis: str = Field(min_length=100, max_length=3000)
    falsification_claim: str = Field(min_length=100, max_length=3000)
    discovery_charter_evidence_hash: str
    theory_screen_evidence_hash: str
    universe_manifest_evidence_hash: str
    development_dataset_bundle_evidence_hash: str
    contamination_ledger_evidence_hash: str
    builder_contract_hash: str
    venue: Literal["BINANCE"] = "BINANCE"
    market_type: Literal["SPOT"] = "SPOT"
    quote_asset: Literal["USDT"] = "USDT"
    timeframe: Literal["4h"] = "4h"
    development_data_start: datetime
    development_data_end: datetime
    evaluation_start: datetime
    evaluation_end: datetime
    decision_symbols: list[str] = Field(min_length=35, max_length=35)
    forbidden_partitions: list[str]
    signal: U1PrimarySignalProtocol
    benchmark: U1PrimaryBenchmarkProtocol
    folds: list[U1PrimaryFold] = Field(min_length=8, max_length=8)
    portfolio: U1PrimaryPortfolioProtocol
    availability: U1PrimaryAvailabilityProtocol
    costs: U1PrimaryCostProtocol
    gates: U1PrimaryGates
    selection_control: U1PrimarySelectionControl
    required_diagnostics: list[str]
    outcome_fields_inspected: list[str] = Field(default_factory=list)
    preexisting_result_artifacts: list[str] = Field(default_factory=list)
    permits_validation: Literal[False] = False
    permits_holdout_or_forward: Literal[False] = False
    permits_pine_parity: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "registered_at",
        "development_data_start",
        "development_data_end",
        "evaluation_start",
        "evaluation_end",
    )
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "discovery_charter_evidence_hash",
        "theory_screen_evidence_hash",
        "universe_manifest_evidence_hash",
        "development_dataset_bundle_evidence_hash",
        "contamination_ledger_evidence_hash",
        "builder_contract_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("decision_symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        return sorted({item.strip().upper() for item in value if item.strip()})

    @field_validator(
        "forbidden_partitions",
        "required_diagnostics",
        "outcome_fields_inspected",
        "preexisting_result_artifacts",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_protocol(self) -> U1PrimaryProtocol:
        if tuple(self.decision_symbols) != R4_DECISION_SYMBOLS:
            raise ValueError("U1 primary must preserve the frozen 35-market universe")
        expected_timestamps = {
            "development_data_start": "2023-01-01T00:00:00+00:00",
            "development_data_end": "2025-01-01T00:00:00+00:00",
            "evaluation_start": "2023-02-01T00:00:00+00:00",
            "evaluation_end": "2025-01-01T00:00:00+00:00",
        }
        for field, expected in expected_timestamps.items():
            if getattr(self, field).isoformat() != expected:
                raise ValueError(f"U1 primary {field} is fixed")
        expected_folds = [
            (
                "fold-01-2023-partial-q1",
                "2023-02-01T00:00:00+00:00",
                "2023-04-01T00:00:00+00:00",
            ),
            (
                "fold-02-2023q2",
                "2023-04-01T00:00:00+00:00",
                "2023-07-01T00:00:00+00:00",
            ),
            (
                "fold-03-2023q3",
                "2023-07-01T00:00:00+00:00",
                "2023-10-01T00:00:00+00:00",
            ),
            (
                "fold-04-2023q4",
                "2023-10-01T00:00:00+00:00",
                "2024-01-01T00:00:00+00:00",
            ),
            (
                "fold-05-2024q1",
                "2024-01-01T00:00:00+00:00",
                "2024-04-01T00:00:00+00:00",
            ),
            (
                "fold-06-2024q2",
                "2024-04-01T00:00:00+00:00",
                "2024-07-01T00:00:00+00:00",
            ),
            (
                "fold-07-2024q3",
                "2024-07-01T00:00:00+00:00",
                "2024-10-01T00:00:00+00:00",
            ),
            (
                "fold-08-2024q4",
                "2024-10-01T00:00:00+00:00",
                "2025-01-01T00:00:00+00:00",
            ),
        ]
        actual_folds = [
            (
                fold.fold_id,
                fold.evaluation_start.isoformat(),
                fold.evaluation_end.isoformat(),
            )
            for fold in self.folds
        ]
        if actual_folds != expected_folds:
            raise ValueError("U1 primary folds are fixed")
        if self.forbidden_partitions != U1_FORBIDDEN_PARTITIONS:
            raise ValueError("U1 primary forbidden partitions are fixed")
        if self.required_diagnostics != U1_REQUIRED_DIAGNOSTICS:
            raise ValueError("U1 primary diagnostics are fixed")
        if self.outcome_fields_inspected or self.preexisting_result_artifacts:
            raise ValueError("U1 primary protocol must predate every outcome")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected_hash:
            raise ValueError("U1 primary protocol hash does not match its evidence")
        return self


def build_u1_primary_protocol(**values) -> U1PrimaryProtocol:
    payload = {
        "schema_version": U1_PRIMARY_PROTOCOL_SCHEMA_VERSION,
        "protocol_id": "u1-volatility-managed-broad-spot-beta-v1",
        "protocol_version": "1.0.0",
        "status": "FROZEN_PRE_DEVELOPMENT_OUTCOME",
        "research_class": "DEVELOPMENT_ONLY_UNRELATED_MECHANISM",
        "mechanism_family": "VOLATILITY_MANAGED_BROAD_SPOT_BETA",
        "venue": "BINANCE",
        "market_type": "SPOT",
        "quote_asset": "USDT",
        "timeframe": "4h",
        "permits_validation": False,
        "permits_holdout_or_forward": False,
        "permits_pine_parity": False,
        "creates_paper_eligibility": False,
        "creates_live_eligibility": False,
        **values,
    }
    for field in (
        "registered_at",
        "development_data_start",
        "development_data_end",
        "evaluation_start",
        "evaluation_end",
    ):
        payload[field] = normalize_timestamp(payload[field])
    payload["decision_symbols"] = sorted(set(payload["decision_symbols"]))
    for field in (
        "forbidden_partitions",
        "required_diagnostics",
        "outcome_fields_inspected",
        "preexisting_result_artifacts",
    ):
        payload[field] = sorted(set(payload[field]))
    return U1PrimaryProtocol(
        **payload,
        protocol_evidence_hash=universe_evidence_hash(payload),
    )


def audit_u1_primary_protocol(protocol: U1PrimaryProtocol) -> bool:
    return protocol.protocol_evidence_hash == universe_evidence_hash(
        protocol.model_dump(exclude={"protocol_evidence_hash"})
    )
