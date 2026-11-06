from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

U1_EXECUTION_SPEC_SCHEMA_VERSION = (
    "aurex-u1-volatility-managed-broad-spot-beta-execution-specification-v1"
)


class U1ArithmeticSemantics(BaseModel):
    decimal_precision: Literal[50] = 50
    decimal_rounding: Literal["ROUND_HALF_EVEN"] = "ROUND_HALF_EVEN"
    natural_log_method: Literal["PYTHON_DECIMAL_LN_WITH_LOCAL_CONTEXT"] = (
        "PYTHON_DECIMAL_LN_WITH_LOCAL_CONTEXT"
    )
    constituent_return_formula: Literal["LN_CLOSE_T_DIVIDED_BY_CLOSE_T_MINUS_ONE"] = (
        "LN_CLOSE_T_DIVIDED_BY_CLOSE_T_MINUS_ONE"
    )
    broad_return_sum_order: Literal["SYMBOL_ASCENDING"] = "SYMBOL_ASCENDING"
    broad_return_mean_formula: Literal[
        "SUM_ACTIVE_CONSTITUENT_RETURNS_DIVIDED_BY_ACTIVE_COUNT"
    ] = "SUM_ACTIVE_CONSTITUENT_RETURNS_DIVIDED_BY_ACTIVE_COUNT"
    variance_window: Literal["EXACT_168_INTERVALS_ENDING_AT_SIGNAL_CLOSE"] = (
        "EXACT_168_INTERVALS_ENDING_AT_SIGNAL_CLOSE"
    )
    variance_sum_order: Literal["OLDEST_INTERVAL_TO_NEWEST_INTERVAL"] = (
        "OLDEST_INTERVAL_TO_NEWEST_INTERVAL"
    )
    realized_variance_formula: Literal[
        "SUM_SQUARED_BROAD_RETURNS_DIVIDED_BY_168_TIMES_2190"
    ] = "SUM_SQUARED_BROAD_RETURNS_DIVIDED_BY_168_TIMES_2190"
    target_exposure_formula: Literal[
        "ONE_IF_VARIANCE_ZERO_ELSE_MIN_ONE_0_36_DIVIDED_BY_VARIANCE"
    ] = "ONE_IF_VARIANCE_ZERO_ELSE_MIN_ONE_0_36_DIVIDED_BY_VARIANCE"
    indicator_rounding: Literal["FULL_DECIMAL_PRECISION"] = "FULL_DECIMAL_PRECISION"

    model_config = ConfigDict(extra="forbid")


class U1InputSemantics(BaseModel):
    baseline_decision_symbol_count: Literal[35] = 35
    required_timestamp_alignment: Literal["EXACT_ALL_ACTIVE_SYMBOLS"] = (
        "EXACT_ALL_ACTIVE_SYMBOLS"
    )
    development_missing_candle_policy: Literal["BLOCK_REPLAY"] = "BLOCK_REPLAY"
    duplicate_candle_policy: Literal["BLOCK_REPLAY"] = "BLOCK_REPLAY"
    resumed_after_terminal_gap_policy: Literal["BLOCK_REPLAY"] = "BLOCK_REPLAY"
    outside_development_policy: Literal["BLOCK_REPLAY"] = "BLOCK_REPLAY"
    leave_one_market_out_omission_count: Literal[1] = 1
    synthetic_or_replacement_candles: Literal[False] = False

    model_config = ConfigDict(extra="forbid")


class U1SignalExecutionSemantics(BaseModel):
    rebalance_anchor: Literal["EVALUATION_START_00_UTC"] = (
        "EVALUATION_START_00_UTC"
    )
    signal_bar_index: Literal["ENTRY_INDEX_MINUS_ONE"] = "ENTRY_INDEX_MINUS_ONE"
    lookback_start_index: Literal["SIGNAL_INDEX_MINUS_168"] = (
        "SIGNAL_INDEX_MINUS_168"
    )
    active_market_set: Literal[
        "BASELINE_SYMBOLS_MINUS_OMISSION_MINUS_TERMINALLY_UNAVAILABLE"
    ] = "BASELINE_SYMBOLS_MINUS_OMISSION_MINUS_TERMINALLY_UNAVAILABLE"
    market_return_active_set: Literal["SAME_AS_PORTFOLIO_ACTIVE_MARKET_SET"] = (
        "SAME_AS_PORTFOLIO_ACTIVE_MARKET_SET"
    )
    minimum_active_market_source: Literal["PROTOCOL_MINIMUM_ACTIVE_MARKETS"] = (
        "PROTOCOL_MINIMUM_ACTIVE_MARKETS"
    )
    insufficient_active_markets_action: Literal["BLOCK_REPLAY"] = "BLOCK_REPLAY"
    benchmark_exposure_source: Literal["PROTOCOL_FIXED_ONE"] = "PROTOCOL_FIXED_ONE"

    model_config = ConfigDict(extra="forbid")


class U1OrderSemantics(BaseModel):
    rebalance_event_order: list[
        Literal[
            "APPLY_TERMINAL_MARKET_EVENTS",
            "EXIT_EXISTING_AT_OPEN",
            "COMPUTE_SIGNAL_FROM_PRIOR_CLOSES",
            "ALLOCATE_EQUAL_WEIGHT_AT_OPEN",
            "MARK_ALL_POSITIONS_AT_CLOSE",
        ]
    ]
    non_rebalance_event_order: list[
        Literal["APPLY_TERMINAL_MARKET_EVENTS", "MARK_ALL_POSITIONS_AT_CLOSE"]
    ]
    entry_raw_price: Literal["ENTRY_BAR_OPEN"] = "ENTRY_BAR_OPEN"
    entry_fill_formula: Literal["RAW_PRICE_TIMES_ONE_PLUS_SLIPPAGE_RATE"] = (
        "RAW_PRICE_TIMES_ONE_PLUS_SLIPPAGE_RATE"
    )
    rebalance_exit_raw_price: Literal["REBALANCE_BAR_OPEN"] = "REBALANCE_BAR_OPEN"
    exit_fill_formula: Literal["RAW_PRICE_TIMES_ONE_MINUS_SLIPPAGE_RATE"] = (
        "RAW_PRICE_TIMES_ONE_MINUS_SLIPPAGE_RATE"
    )
    commission_formula: Literal["FILL_NOTIONAL_TIMES_COMMISSION_RATE"] = (
        "FILL_NOTIONAL_TIMES_COMMISSION_RATE"
    )
    no_intraperiod_stop: Literal[True] = True
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
    def validate_event_order(self) -> U1OrderSemantics:
        if self.rebalance_event_order != [
            "APPLY_TERMINAL_MARKET_EVENTS",
            "EXIT_EXISTING_AT_OPEN",
            "COMPUTE_SIGNAL_FROM_PRIOR_CLOSES",
            "ALLOCATE_EQUAL_WEIGHT_AT_OPEN",
            "MARK_ALL_POSITIONS_AT_CLOSE",
        ]:
            raise ValueError("U1 rebalance event order is fixed")
        if self.non_rebalance_event_order != [
            "APPLY_TERMINAL_MARKET_EVENTS",
            "MARK_ALL_POSITIONS_AT_CLOSE",
        ]:
            raise ValueError("U1 non-rebalance event order is fixed")
        return self


class U1AllocationSemantics(BaseModel):
    equity_basis: Literal["CASH_AFTER_REBALANCE_EXITS"] = "CASH_AFTER_REBALANCE_EXITS"
    target_gross_cash_formula: Literal["EQUITY_TIMES_TARGET_EXPOSURE"] = (
        "EQUITY_TIMES_TARGET_EXPOSURE"
    )
    fee_reservation_formula: Literal[
        "TARGET_GROSS_CASH_DIVIDED_BY_ONE_PLUS_COMMISSION_RATE"
    ] = "TARGET_GROSS_CASH_DIVIDED_BY_ONE_PLUS_COMMISSION_RATE"
    per_market_fill_notional_formula: Literal[
        "FEE_RESERVED_GROSS_NOTIONAL_DIVIDED_BY_ACTIVE_MARKET_COUNT"
    ] = "FEE_RESERVED_GROSS_NOTIONAL_DIVIDED_BY_ACTIVE_MARKET_COUNT"
    desired_quantity_formula: Literal[
        "PER_MARKET_FILL_NOTIONAL_DIVIDED_BY_ENTRY_FILL_PRICE"
    ] = "PER_MARKET_FILL_NOTIONAL_DIVIDED_BY_ENTRY_FILL_PRICE"
    allocation_order: Literal["SYMBOL_ASCENDING"] = "SYMBOL_ASCENDING"
    quantity_rounding: Literal["ROUND_DOWN_TO_DECLARED_INCREMENT"] = (
        "ROUND_DOWN_TO_DECLARED_INCREMENT"
    )
    zero_quantity_action: Literal["REJECT_WITH_EVIDENCE"] = "REJECT_WITH_EVIDENCE"
    capacity_breach_action: Literal["BLOCK_REPLAY"] = "BLOCK_REPLAY"
    capacity_includes_entry_fees: Literal[True] = True
    gross_exposure_basis: Literal["FILL_NOTIONAL_DIVIDED_BY_EQUITY"] = (
        "FILL_NOTIONAL_DIVIDED_BY_EQUITY"
    )

    model_config = ConfigDict(extra="forbid")


class U1AvailabilitySemantics(BaseModel):
    terminal_event_time: Literal["FIRST_MISSING_BAR_OPEN_TIMESTAMP"] = (
        "FIRST_MISSING_BAR_OPEN_TIMESTAMP"
    )
    unheld_action: Literal["REMOVE_PERMANENTLY"] = "REMOVE_PERMANENTLY"
    held_action: Literal["CLOSE_AT_ZERO_WITHOUT_EXIT_COST"] = (
        "CLOSE_AT_ZERO_WITHOUT_EXIT_COST"
    )
    writeoff_raw_exit_price: Literal["0"] = "0"
    writeoff_exit_fill_price: Literal["0"] = "0"
    writeoff_exit_commission: Literal["0"] = "0"
    writeoff_exit_slippage_cost: Literal["0"] = "0"
    writeoff_reason: Literal["MARKET_TERMINATION_WRITE_OFF"] = (
        "MARKET_TERMINATION_WRITE_OFF"
    )
    process_before_rebalance_exit: Literal[True] = True
    active_weights_renormalized: Literal[True] = True
    invented_candle_or_price_allowed: Literal[False] = False

    model_config = ConfigDict(extra="forbid")


class U1FoldSemantics(BaseModel):
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


class U1MetricSemantics(BaseModel):
    net_pl: Literal["FINAL_EQUITY_MINUS_INITIAL_CAPITAL"] = (
        "FINAL_EQUITY_MINUS_INITIAL_CAPITAL"
    )
    trade_net_pl: Literal[
        "RAW_PRICE_PL_MINUS_ENTRY_EXIT_SLIPPAGE_AND_COMMISSIONS"
    ] = "RAW_PRICE_PL_MINUS_ENTRY_EXIT_SLIPPAGE_AND_COMMISSIONS"
    completed_trade_unit: Literal["ONE_CLOSED_SYMBOL_POSITION"] = (
        "ONE_CLOSED_SYMBOL_POSITION"
    )
    profit_factor: Literal["SUM_POSITIVE_TRADE_NET_PL_DIVIDED_BY_ABS_NEGATIVE"] = (
        "SUM_POSITIVE_TRADE_NET_PL_DIVIDED_BY_ABS_NEGATIVE"
    )
    profit_factor_zero_loss_policy: Literal["NULL_AND_GATE_FAIL"] = (
        "NULL_AND_GATE_FAIL"
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
    equity_return_series: Literal[
        "LOG_RETURN_FROM_INITIAL_CAPITAL_THEN_CONSECUTIVE_CLOSE_EQUITY"
    ] = "LOG_RETURN_FROM_INITIAL_CAPITAL_THEN_CONSECUTIVE_CLOSE_EQUITY"
    realized_equity_volatility: Literal[
        "SQRT_MEAN_SQUARED_EQUITY_LOG_RETURN_TIMES_2190"
    ] = "SQRT_MEAN_SQUARED_EQUITY_LOG_RETURN_TIMES_2190"
    return_to_drawdown: Literal["NET_PL_DIVIDED_BY_MAXIMUM_DRAWDOWN"] = (
        "NET_PL_DIVIDED_BY_MAXIMUM_DRAWDOWN"
    )
    zero_drawdown_return_efficiency_policy: Literal["NULL_AND_GATE_FAIL"] = (
        "NULL_AND_GATE_FAIL"
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
    benchmark_comparison_scope: Literal[
        "OVERALL_BASE_COST_PRIMARY_VERSUS_OVERALL_BASE_COST_BENCHMARK"
    ] = "OVERALL_BASE_COST_PRIMARY_VERSUS_OVERALL_BASE_COST_BENCHMARK"
    cost_stress: Literal["MULTIPLY_COMMISSION_AND_SLIPPAGE_TOGETHER"] = (
        "MULTIPLY_COMMISSION_AND_SLIPPAGE_TOGETHER"
    )
    cost_stress_replay_scope: Literal[
        "FULL_REPLAY_INCLUDING_FILLS_FEES_SIZING_AND_CAPACITY"
    ] = "FULL_REPLAY_INCLUDING_FILLS_FEES_SIZING_AND_CAPACITY"

    model_config = ConfigDict(extra="forbid")


class U1ExecutionSpecification(BaseModel):
    schema_version: Literal[
        "aurex-u1-volatility-managed-broad-spot-beta-execution-specification-v1"
    ] = U1_EXECUTION_SPEC_SCHEMA_VERSION
    specification_id: Literal["u1-volatility-managed-broad-spot-beta-execution-v1"] = (
        "u1-volatility-managed-broad-spot-beta-execution-v1"
    )
    specification_version: Literal["1.0.0"] = "1.0.0"
    registered_at: datetime
    status: Literal["FROZEN_PRE_DEVELOPMENT_OUTCOME"] = (
        "FROZEN_PRE_DEVELOPMENT_OUTCOME"
    )
    primary_protocol_evidence_hash: str
    discovery_charter_evidence_hash: str
    theory_screen_evidence_hash: str
    universe_manifest_evidence_hash: str
    development_dataset_bundle_evidence_hash: str
    builder_contract_hash: str
    arithmetic: U1ArithmeticSemantics
    inputs: U1InputSemantics
    signals: U1SignalExecutionSemantics
    orders: U1OrderSemantics
    allocation: U1AllocationSemantics
    availability: U1AvailabilitySemantics
    folds: U1FoldSemantics
    metrics: U1MetricSemantics
    outcome_fields_inspected: list[str] = Field(default_factory=list)
    preexisting_engine_or_result_artifacts: list[str] = Field(default_factory=list)
    specification_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("registered_at")
    @classmethod
    def normalize_registered_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "primary_protocol_evidence_hash",
        "discovery_charter_evidence_hash",
        "theory_screen_evidence_hash",
        "universe_manifest_evidence_hash",
        "development_dataset_bundle_evidence_hash",
        "builder_contract_hash",
        "specification_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "outcome_fields_inspected",
        "preexisting_engine_or_result_artifacts",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_specification(self) -> U1ExecutionSpecification:
        if self.outcome_fields_inspected or self.preexisting_engine_or_result_artifacts:
            raise ValueError("U1 execution specification must predate engine outcomes")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"specification_evidence_hash"})
        )
        if self.specification_evidence_hash != expected_hash:
            raise ValueError("U1 execution specification hash does not match evidence")
        return self


def build_u1_execution_specification(**values) -> U1ExecutionSpecification:
    payload = {
        "schema_version": U1_EXECUTION_SPEC_SCHEMA_VERSION,
        "specification_id": "u1-volatility-managed-broad-spot-beta-execution-v1",
        "specification_version": "1.0.0",
        "status": "FROZEN_PRE_DEVELOPMENT_OUTCOME",
        **values,
    }
    payload["registered_at"] = normalize_timestamp(payload["registered_at"])
    for field in (
        "outcome_fields_inspected",
        "preexisting_engine_or_result_artifacts",
    ):
        payload[field] = sorted(set(payload[field]))
    return U1ExecutionSpecification(
        **payload,
        specification_evidence_hash=universe_evidence_hash(payload),
    )


def audit_u1_execution_specification(
    specification: U1ExecutionSpecification,
) -> bool:
    return specification.specification_evidence_hash == universe_evidence_hash(
        specification.model_dump(exclude={"specification_evidence_hash"})
    )
