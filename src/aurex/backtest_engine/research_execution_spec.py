from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

R3_EXECUTION_SPEC_SCHEMA_VERSION = "aurex-r3-execution-specification-v1"


class R3InputSemantics(BaseModel):
    decision_symbol_count: int = Field(gt=0)
    required_timestamp_alignment: Literal["EXACT_ALL_DECISION_SYMBOLS"] = (
        "EXACT_ALL_DECISION_SYMBOLS"
    )
    missing_candle_policy: Literal["BLOCK_STUDY"] = "BLOCK_STUDY"
    duplicate_candle_policy: Literal["BLOCK_STUDY"] = "BLOCK_STUDY"
    outside_development_policy: Literal["BLOCK_STUDY"] = "BLOCK_STUDY"
    diagnostic_symbols_enter_rankings: Literal[False] = False
    diagnostic_symbols_enter_portfolio: Literal[False] = False
    diagnostic_symbols_enter_gates: Literal[False] = False

    model_config = ConfigDict(extra="forbid")


class R3SignalSemantics(BaseModel):
    rebalance_anchor: Literal["EVALUATION_START_00_UTC"] = (
        "EVALUATION_START_00_UTC"
    )
    signal_bar_index: Literal["ENTRY_INDEX_MINUS_ONE"] = "ENTRY_INDEX_MINUS_ONE"
    lookback_reference_index: Literal[
        "SIGNAL_INDEX_MINUS_VARIANT_LOOKBACK_BARS"
    ] = "SIGNAL_INDEX_MINUS_VARIANT_LOOKBACK_BARS"
    score_formula: Literal["SIGNAL_CLOSE_DIVIDED_BY_REFERENCE_CLOSE_MINUS_ONE"] = (
        "SIGNAL_CLOSE_DIVIDED_BY_REFERENCE_CLOSE_MINUS_ONE"
    )
    positive_momentum_test: Literal["SCORE_STRICTLY_GREATER_THAN_ZERO"] = (
        "SCORE_STRICTLY_GREATER_THAN_ZERO"
    )
    ranking_order: Literal["SCORE_DESCENDING_THEN_SYMBOL_ASCENDING"] = (
        "SCORE_DESCENDING_THEN_SYMBOL_ASCENDING"
    )
    selected_count_formula: Literal[
        "CEILING_FRACTION_TIMES_BASELINE_DECISION_COUNT"
    ] = "CEILING_FRACTION_TIMES_BASELINE_DECISION_COUNT"
    selected_count_is_fixed_in_leave_one_out: Literal[True] = True
    fixed_selected_count: int = Field(gt=0)
    minimum_positive_markets_source: Literal[
        "PROTOCOL_MINIMUM_RANKED_POSITIONS"
    ] = "PROTOCOL_MINIMUM_RANKED_POSITIONS"
    eligible_count_formula: Literal[
        "MIN_FIXED_SELECTED_COUNT_AND_POSITIVE_MARKET_COUNT"
    ] = "MIN_FIXED_SELECTED_COUNT_AND_POSITIVE_MARKET_COUNT"
    insufficient_positive_markets_action: Literal["HOLD_CASH"] = "HOLD_CASH"

    model_config = ConfigDict(extra="forbid")


class R3IndicatorSemantics(BaseModel):
    true_range_formula: Literal[
        "MAX_HIGH_LOW_ABS_HIGH_PREV_CLOSE_ABS_LOW_PREV_CLOSE"
    ] = "MAX_HIGH_LOW_ABS_HIGH_PREV_CLOSE_ABS_LOW_PREV_CLOSE"
    atr_method: Literal["WILDER_RMA_SEEDED_WITH_SMA"] = "WILDER_RMA_SEEDED_WITH_SMA"
    first_candle_true_range: Literal["HIGH_MINUS_LOW"] = "HIGH_MINUS_LOW"
    atr_signal_cutoff: Literal["INCLUSIVE_OF_SIGNAL_BAR"] = "INCLUSIVE_OF_SIGNAL_BAR"
    stop_distance_formula: Literal["VARIANT_ATR_MULTIPLE_TIMES_SIGNAL_ATR"] = (
        "VARIANT_ATR_MULTIPLE_TIMES_SIGNAL_ATR"
    )
    volatility_method: Literal["SAMPLE_STDDEV_OF_LOG_RETURNS"] = (
        "SAMPLE_STDDEV_OF_LOG_RETURNS"
    )
    volatility_role: Literal["DIAGNOSTIC_ONLY"] = "DIAGNOSTIC_ONLY"
    indicator_rounding: Literal["FULL_DECIMAL_PRECISION"] = "FULL_DECIMAL_PRECISION"

    model_config = ConfigDict(extra="forbid")


class R3OrderSemantics(BaseModel):
    rebalance_event_order: list[
        Literal[
            "EXIT_EXISTING_AT_OPEN",
            "RANK_FROM_PRIOR_CLOSE",
            "ALLOCATE_NEW_AT_OPEN",
            "DISABLE_NEW_POSITION_SAME_BAR_STOP",
            "MARK_ALL_POSITIONS_AT_CLOSE",
        ]
    ]
    non_rebalance_event_order: list[
        Literal["CHECK_FIXED_STOP", "MARK_ALL_POSITIONS_AT_CLOSE"]
    ]
    entry_raw_price: Literal["ENTRY_BAR_OPEN"] = "ENTRY_BAR_OPEN"
    entry_fill_formula: Literal["RAW_PRICE_TIMES_ONE_PLUS_SLIPPAGE_RATE"] = (
        "RAW_PRICE_TIMES_ONE_PLUS_SLIPPAGE_RATE"
    )
    rebalance_exit_raw_price: Literal["REBALANCE_BAR_OPEN"] = "REBALANCE_BAR_OPEN"
    stop_raw_price: Literal["BAR_OPEN_IF_AT_OR_BELOW_STOP_ELSE_STOP"] = (
        "BAR_OPEN_IF_AT_OR_BELOW_STOP_ELSE_STOP"
    )
    exit_fill_formula: Literal["RAW_PRICE_TIMES_ONE_MINUS_SLIPPAGE_RATE"] = (
        "RAW_PRICE_TIMES_ONE_MINUS_SLIPPAGE_RATE"
    )
    commission_formula: Literal["FILL_NOTIONAL_TIMES_COMMISSION_RATE"] = (
        "FILL_NOTIONAL_TIMES_COMMISSION_RATE"
    )
    stop_price_formula: Literal[
        "ENTRY_RAW_PRICE_MINUS_STOP_DISTANCE_ROUNDED_DOWN_TO_PRICE_INCREMENT"
    ] = "ENTRY_RAW_PRICE_MINUS_STOP_DISTANCE_ROUNDED_DOWN_TO_PRICE_INCREMENT"
    stop_trigger: Literal["BAR_LOW_LESS_THAN_OR_EQUAL_TO_STOP_PRICE"] = (
        "BAR_LOW_LESS_THAN_OR_EQUAL_TO_STOP_PRICE"
    )
    stop_is_fixed_after_entry: Literal[True] = True
    stop_checked_on_entry_bar: Literal[False] = False
    rebalance_exit_precedes_stop_check: Literal[True] = True
    same_symbol_reentry_on_rebalance: Literal[True] = True
    end_of_window_liquidation: Literal[
        "LAST_AVAILABLE_CLOSE_BEFORE_EXCLUSIVE_END"
    ] = "LAST_AVAILABLE_CLOSE_BEFORE_EXCLUSIVE_END"
    end_liquidation_costs_applied: Literal[True] = True
    final_bar_processing: Literal[
        "PROCESS_NORMAL_EVENTS_THEN_LIQUIDATE_SURVIVORS_AT_CLOSE"
    ] = "PROCESS_NORMAL_EVENTS_THEN_LIQUIDATE_SURVIVORS_AT_CLOSE"

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_event_order(self) -> "R3OrderSemantics":
        if self.rebalance_event_order != [
            "EXIT_EXISTING_AT_OPEN",
            "RANK_FROM_PRIOR_CLOSE",
            "ALLOCATE_NEW_AT_OPEN",
            "DISABLE_NEW_POSITION_SAME_BAR_STOP",
            "MARK_ALL_POSITIONS_AT_CLOSE",
        ]:
            raise ValueError("R3 rebalance event order is fixed")
        if self.non_rebalance_event_order != [
            "CHECK_FIXED_STOP",
            "MARK_ALL_POSITIONS_AT_CLOSE",
        ]:
            raise ValueError("R3 non-rebalance event order is fixed")
        return self


class R3AllocationSemantics(BaseModel):
    equity_basis: Literal["CASH_PLUS_OPEN_POSITIONS_MARKED_AT_CURRENT_OPEN"] = (
        "CASH_PLUS_OPEN_POSITIONS_MARKED_AT_CURRENT_OPEN"
    )
    risk_budget_formula: Literal["EQUITY_TIMES_RISK_PERCENT"] = (
        "EQUITY_TIMES_RISK_PERCENT"
    )
    desired_quantity_formula: Literal["RISK_BUDGET_DIVIDED_BY_RAW_STOP_DISTANCE"] = (
        "RISK_BUDGET_DIVIDED_BY_RAW_STOP_DISTANCE"
    )
    symbol_cap_formula: Literal["EQUITY_TIMES_SYMBOL_CAP_DIVIDED_BY_ENTRY_FILL"] = (
        "EQUITY_TIMES_SYMBOL_CAP_DIVIDED_BY_ENTRY_FILL"
    )
    candidate_quantity_order: list[
        Literal[
            "COMPUTE_RISK_QUANTITY",
            "APPLY_SYMBOL_CAP",
            "APPLY_MAX_POSITION_COUNT",
            "APPLY_PROPORTIONAL_CAPACITY_SCALE",
            "ROUND_DOWN_TO_QUANTITY_INCREMENT",
            "REJECT_ZERO_QUANTITY",
        ]
    ]
    entry_capacity_formula: Literal[
        "MIN_CASH_AND_EQUITY_TIMES_MAX_GROSS_DIVIDED_BY_ONE_PLUS_COMMISSION_RATE"
    ] = (
        "MIN_CASH_AND_EQUITY_TIMES_MAX_GROSS_DIVIDED_BY_ONE_PLUS_COMMISSION_RATE"
    )
    capacity_scaling: Literal["PROPORTIONAL_ACROSS_SAME_REBALANCE_CANDIDATES"] = (
        "PROPORTIONAL_ACROSS_SAME_REBALANCE_CANDIDATES"
    )
    capacity_includes_entry_fees: Literal[True] = True
    quantity_rounding: Literal["ROUND_DOWN_TO_DECLARED_INCREMENT"] = (
        "ROUND_DOWN_TO_DECLARED_INCREMENT"
    )
    zero_quantity_action: Literal["REJECT_WITH_EVIDENCE"] = "REJECT_WITH_EVIDENCE"
    gross_exposure_basis: Literal["ENTRY_FILL_NOTIONAL_DIVIDED_BY_EQUITY"] = (
        "ENTRY_FILL_NOTIONAL_DIVIDED_BY_EQUITY"
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_candidate_quantity_order(self) -> "R3AllocationSemantics":
        if self.candidate_quantity_order != [
            "COMPUTE_RISK_QUANTITY",
            "APPLY_SYMBOL_CAP",
            "APPLY_MAX_POSITION_COUNT",
            "APPLY_PROPORTIONAL_CAPACITY_SCALE",
            "ROUND_DOWN_TO_QUANTITY_INCREMENT",
            "REJECT_ZERO_QUANTITY",
        ]:
            raise ValueError("R3 candidate quantity order is fixed")
        return self


class R3FoldSemantics(BaseModel):
    overall_replay: Literal["ONE_CONTINUOUS_EVALUATION_REPLAY"] = (
        "ONE_CONTINUOUS_EVALUATION_REPLAY"
    )
    fold_replay: Literal["INDEPENDENT_CAPITAL_RESET_WITH_PRIOR_WARMUP"] = (
        "INDEPENDENT_CAPITAL_RESET_WITH_PRIOR_WARMUP"
    )
    fold_initial_capital_matches_protocol: Literal[True] = True
    fold_positions_open_before_start: Literal[False] = False
    fold_first_entry_may_occur_at_start: Literal[True] = True
    fold_rebalance_anchor: Literal["EACH_FOLD_EVALUATION_START"] = (
        "EACH_FOLD_EVALUATION_START"
    )
    fold_end_liquidation: Literal["LAST_CLOSE_BEFORE_FOLD_END"] = (
        "LAST_CLOSE_BEFORE_FOLD_END"
    )
    trade_fold_attribution: Literal["EXIT_TIMESTAMP"] = "EXIT_TIMESTAMP"

    model_config = ConfigDict(extra="forbid")


class R3MetricSemantics(BaseModel):
    net_pl: Literal["FINAL_EQUITY_MINUS_INITIAL_CAPITAL"] = (
        "FINAL_EQUITY_MINUS_INITIAL_CAPITAL"
    )
    trade_net_pl: Literal[
        "RAW_PRICE_PL_MINUS_ENTRY_EXIT_SLIPPAGE_AND_COMMISSIONS"
    ] = "RAW_PRICE_PL_MINUS_ENTRY_EXIT_SLIPPAGE_AND_COMMISSIONS"
    profit_factor: Literal["SUM_POSITIVE_TRADE_NET_PL_DIVIDED_BY_ABS_NEGATIVE"] = (
        "SUM_POSITIVE_TRADE_NET_PL_DIVIDED_BY_ABS_NEGATIVE"
    )
    profit_factor_zero_loss_policy: Literal["NULL_AND_GATE_FAIL"] = (
        "NULL_AND_GATE_FAIL"
    )
    completed_trade_unit: Literal["ONE_CLOSED_SYMBOL_POSITION"] = (
        "ONE_CLOSED_SYMBOL_POSITION"
    )
    mark_to_market_equity: Literal[
        "CASH_PLUS_QUANTITY_TIMES_RAW_CLOSE_WITHOUT_HYPOTHETICAL_EXIT_COST"
    ] = "CASH_PLUS_QUANTITY_TIMES_RAW_CLOSE_WITHOUT_HYPOTHETICAL_EXIT_COST"
    drawdown_initial_peak_included: Literal[True] = True
    drawdown: Literal["PEAK_MINUS_MARK_TO_MARKET_CLOSE_EQUITY"] = (
        "PEAK_MINUS_MARK_TO_MARKET_CLOSE_EQUITY"
    )
    drawdown_percent: Literal["DRAWDOWN_DIVIDED_BY_PEAK_EQUITY_TIMES_100"] = (
        "DRAWDOWN_DIVIDED_BY_PEAK_EQUITY_TIMES_100"
    )
    turnover: Literal["SUM_ABSOLUTE_FILL_NOTIONAL_DIVIDED_BY_INITIAL_CAPITAL"] = (
        "SUM_ABSOLUTE_FILL_NOTIONAL_DIVIDED_BY_INITIAL_CAPITAL"
    )
    gross_profit_concentration: Literal[
        "POSITIVE_RAW_PRICE_TRADE_PL_BY_SYMBOL_DIVIDED_BY_TOTAL_POSITIVE_RAW_PL"
    ] = "POSITIVE_RAW_PRICE_TRADE_PL_BY_SYMBOL_DIVIDED_BY_TOTAL_POSITIVE_RAW_PL"
    gross_profit_zero_denominator_policy: Literal["NULL_AND_GATE_FAIL"] = (
        "NULL_AND_GATE_FAIL"
    )
    leave_one_market_out: Literal[
        "FULL_PRIMARY_REPLAY_EXCLUDING_ONE_DECISION_SYMBOL_EACH_RUN"
    ] = "FULL_PRIMARY_REPLAY_EXCLUDING_ONE_DECISION_SYMBOL_EACH_RUN"
    leave_one_market_out_positive_test: Literal["NET_PL_STRICTLY_GREATER_THAN_ZERO"] = (
        "NET_PL_STRICTLY_GREATER_THAN_ZERO"
    )
    positive_fold_test: Literal["NET_PL_STRICTLY_GREATER_THAN_ZERO"] = (
        "NET_PL_STRICTLY_GREATER_THAN_ZERO"
    )
    cost_stress: Literal["MULTIPLY_COMMISSION_AND_SLIPPAGE_TOGETHER"] = (
        "MULTIPLY_COMMISSION_AND_SLIPPAGE_TOGETHER"
    )
    cost_stress_replay_scope: Literal[
        "FULL_REPLAY_INCLUDING_FILLS_FEES_SIZING_AND_CAPACITY"
    ] = "FULL_REPLAY_INCLUDING_FILLS_FEES_SIZING_AND_CAPACITY"

    model_config = ConfigDict(extra="forbid")


class R3ExecutionSpecification(BaseModel):
    schema_version: Literal["aurex-r3-execution-specification-v1"] = (
        R3_EXECUTION_SPEC_SCHEMA_VERSION
    )
    specification_id: str = Field(min_length=1, max_length=128)
    specification_version: str = Field(min_length=1, max_length=64)
    registered_at: datetime
    status: Literal["FROZEN_PRE_OUTCOME"] = "FROZEN_PRE_OUTCOME"
    protocol_evidence_hash: str
    universe_manifest_evidence_hash: str
    development_dataset_bundle_evidence_hash: str
    builder_contract_hash: str
    inputs: R3InputSemantics
    signals: R3SignalSemantics
    indicators: R3IndicatorSemantics
    orders: R3OrderSemantics
    allocation: R3AllocationSemantics
    folds: R3FoldSemantics
    metrics: R3MetricSemantics
    preexisting_result_artifacts: list[str] = Field(default_factory=list)
    outcome_fields_inspected: list[str] = Field(default_factory=list)
    specification_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("registered_at")
    @classmethod
    def normalize_registered_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_evidence_hash",
        "universe_manifest_evidence_hash",
        "development_dataset_bundle_evidence_hash",
        "builder_contract_hash",
        "specification_evidence_hash",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("preexisting_result_artifacts", "outcome_fields_inspected")
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_specification(self) -> "R3ExecutionSpecification":
        if self.preexisting_result_artifacts or self.outcome_fields_inspected:
            raise ValueError("R3 execution specification must predate every study outcome")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"specification_evidence_hash"})
        )
        if self.specification_evidence_hash != expected_hash:
            raise ValueError("R3 execution specification hash does not match inputs")
        return self


def build_r3_execution_specification(**values) -> R3ExecutionSpecification:
    payload = {
        "schema_version": R3_EXECUTION_SPEC_SCHEMA_VERSION,
        **values,
    }
    payload["registered_at"] = normalize_timestamp(payload["registered_at"])
    payload["preexisting_result_artifacts"] = sorted(
        set(payload["preexisting_result_artifacts"])
    )
    payload["outcome_fields_inspected"] = sorted(
        set(payload["outcome_fields_inspected"])
    )
    return R3ExecutionSpecification(
        **payload,
        specification_evidence_hash=universe_evidence_hash(payload),
    )


def audit_r3_execution_specification(specification: R3ExecutionSpecification) -> bool:
    return specification.specification_evidence_hash == universe_evidence_hash(
        specification.model_dump(exclude={"specification_evidence_hash"})
    )
