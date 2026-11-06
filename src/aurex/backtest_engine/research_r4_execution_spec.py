from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_execution_spec import (
    R3AllocationSemantics,
    R3FoldSemantics,
    R3IndicatorSemantics,
    R3MetricSemantics,
    R3OrderSemantics,
)
from aurex.backtest_engine.research_r31_execution_spec import (
    R31ArithmeticSemantics,
    R31SignalExecutionSemantics,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

R4_EXECUTION_SPEC_SCHEMA_VERSION = "aurex-r4-validation-execution-specification-v1"


class R4TerminalAvailability(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    last_available_bar: datetime
    first_missing_bar: datetime
    missing_candle_count: int = Field(gt=0, le=2190)
    unavailable_archive_months: list[str]

    model_config = ConfigDict(extra="forbid")

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("last_available_bar", "first_missing_bar")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("unavailable_archive_months")
    @classmethod
    def normalize_months(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_terminal_boundary(self) -> "R4TerminalAvailability":
        if (
            self.first_missing_bar - self.last_available_bar
        ).total_seconds() != 4 * 60 * 60:
            raise ValueError("R4 terminal boundary must be one 4h interval")
        return self


class R4InputAvailabilitySemantics(BaseModel):
    global_timeline: Literal[
        "FROZEN_DEVELOPMENT_WARMUP_PLUS_EXACT_2025_4H_GRID"
    ] = "FROZEN_DEVELOPMENT_WARMUP_PLUS_EXACT_2025_4H_GRID"
    baseline_symbol_count: Literal[35] = 35
    warmup_close_count: Literal[505] = 505
    warmup_source: Literal["FROZEN_DEVELOPMENT_BUNDLE"] = (
        "FROZEN_DEVELOPMENT_BUNDLE"
    )
    validation_source: Literal["FROZEN_VALIDATION_BUNDLE"] = (
        "FROZEN_VALIDATION_BUNDLE"
    )
    full_continuous_symbol_count: Literal[33] = 33
    terminal_symbol_count: Literal[2] = 2
    terminal_symbols: list[R4TerminalAvailability] = Field(
        min_length=2, max_length=2
    )
    allowed_validation_shapes: list[
        Literal["FULL_CONTINUOUS", "CONTIGUOUS_TERMINAL_SUFFIX_MISSING"]
    ]
    leading_or_internal_gap_policy: Literal["BLOCK_BEFORE_REPLAY"] = (
        "BLOCK_BEFORE_REPLAY"
    )
    resumed_after_missing_policy: Literal["BLOCK_BEFORE_REPLAY"] = (
        "BLOCK_BEFORE_REPLAY"
    )
    duplicate_policy: Literal["BLOCK_BEFORE_REPLAY"] = "BLOCK_BEFORE_REPLAY"
    synthetic_candle_policy: Literal["FORBIDDEN"] = "FORBIDDEN"
    replacement_symbol_policy: Literal["FORBIDDEN"] = "FORBIDDEN"
    omitted_symbol_policy: Literal[
        "LEAVE_ONE_OUT_ONLY_FROM_FIXED_BASELINE"
    ] = "LEAVE_ONE_OUT_ONLY_FROM_FIXED_BASELINE"

    model_config = ConfigDict(extra="forbid")

    @field_validator("allowed_validation_shapes")
    @classmethod
    def validate_shapes(cls, value: list[str]) -> list[str]:
        normalized = sorted(set(value))
        expected = [
            "CONTIGUOUS_TERMINAL_SUFFIX_MISSING",
            "FULL_CONTINUOUS",
        ]
        if normalized != expected:
            raise ValueError("R4 accepted availability shapes are fixed")
        return normalized

    @field_validator("terminal_symbols")
    @classmethod
    def sort_terminal_symbols(
        cls, value: list[R4TerminalAvailability]
    ) -> list[R4TerminalAvailability]:
        return sorted(value, key=lambda item: item.symbol)

    @model_validator(mode="after")
    def validate_terminal_symbols(self) -> "R4InputAvailabilitySemantics":
        if [item.symbol for item in self.terminal_symbols] != [
            "FTMUSDT",
            "MKRUSDT",
        ]:
            raise ValueError("R4 terminal symbols must match the frozen bundle")
        return self


class R4MarketLifecycleSemantics(BaseModel):
    symbol_is_entry_eligible: Literal[
        "ENTRY_BAR_EXISTS_AND_PRIOR_505_CLOSES_ARE_CONSECUTIVE_AND_SLOPE_POSITIVE"
    ] = "ENTRY_BAR_EXISTS_AND_PRIOR_505_CLOSES_ARE_CONSECUTIVE_AND_SLOPE_POSITIVE"
    atr_and_volatility_history: Literal[
        "REQUIRE_CONSECUTIVE_ACTUAL_CANDLES_WITHOUT_SYNTHESIS"
    ] = "REQUIRE_CONSECUTIVE_ACTUAL_CANDLES_WITHOUT_SYNTHESIS"
    terminated_unheld_symbol: Literal[
        "PERMANENTLY_EXCLUDE_FROM_FIRST_MISSING_BAR"
    ] = "PERMANENTLY_EXCLUDE_FROM_FIRST_MISSING_BAR"
    terminated_held_symbol: Literal[
        "CLOSE_AT_ZERO_ON_FIRST_MISSING_BAR"
    ] = "CLOSE_AT_ZERO_ON_FIRST_MISSING_BAR"
    termination_exit_reason: Literal["MARKET_TERMINATION_WRITE_OFF"] = (
        "MARKET_TERMINATION_WRITE_OFF"
    )
    termination_raw_exit_price: Literal["0"] = "0"
    termination_exit_fill_price: Literal["0"] = "0"
    termination_exit_commission: Literal["0"] = "0"
    termination_exit_slippage_cost: Literal["0"] = "0"
    termination_event_timestamp: Literal["FIRST_MISSING_BAR_OPEN_TIME"] = (
        "FIRST_MISSING_BAR_OPEN_TIME"
    )
    termination_event_order: list[
        Literal[
            "WRITE_OFF_TERMINATED_OPEN_POSITIONS",
            "PROCESS_REBALANCE_OR_STOPS_FOR_AVAILABLE_MARKETS",
            "MARK_AVAILABLE_OPEN_POSITIONS_AT_CLOSE",
        ]
    ]
    terminated_symbol_reactivation: Literal[False] = False
    insufficient_active_markets_action: Literal["HOLD_CASH"] = "HOLD_CASH"
    availability_events_recorded: Literal[True] = True
    writeoff_metrics_recorded: Literal[True] = True

    model_config = ConfigDict(extra="forbid")

    @field_validator("termination_event_order")
    @classmethod
    def validate_event_order(cls, value: list[str]) -> list[str]:
        expected = [
            "WRITE_OFF_TERMINATED_OPEN_POSITIONS",
            "PROCESS_REBALANCE_OR_STOPS_FOR_AVAILABLE_MARKETS",
            "MARK_AVAILABLE_OPEN_POSITIONS_AT_CLOSE",
        ]
        if value != expected:
            raise ValueError("R4 market-termination event order is fixed")
        return value


class R4ValidationFoldSemantics(BaseModel):
    parent_fold_semantics: R3FoldSemantics
    fold_count: Literal[4] = 4
    fold_boundaries: Literal[
        "2025_CALENDAR_QUARTERS_HALF_OPEN"
    ] = "2025_CALENDAR_QUARTERS_HALF_OPEN"
    fold_capital_reset: Literal[True] = True
    availability_state_at_fold_start: Literal[
        "APPLY_TERMINATIONS_STRICTLY_BEFORE_FOLD_START_WITH_NO_SYNTHETIC_WRITEOFF"
    ] = (
        "APPLY_TERMINATIONS_STRICTLY_BEFORE_FOLD_START_WITH_NO_SYNTHETIC_WRITEOFF"
    )
    termination_on_fold_start: Literal[
        "FIRST_MISSING_BAR_BELONGS_TO_FOLD_AND_WRITES_OFF_ONLY_A_FOLD_OPEN_POSITION"
    ] = (
        "FIRST_MISSING_BAR_BELONGS_TO_FOLD_AND_WRITES_OFF_ONLY_A_FOLD_OPEN_POSITION"
    )
    fold_warmup: Literal[
        "USE_PRIOR_ACTUAL_CANDLES_ACROSS_DEVELOPMENT_AND_EARLIER_VALIDATION"
    ] = "USE_PRIOR_ACTUAL_CANDLES_ACROSS_DEVELOPMENT_AND_EARLIER_VALIDATION"

    model_config = ConfigDict(extra="forbid")


class R4ValidationMetricSemantics(BaseModel):
    parent_metrics: R3MetricSemantics
    termination_writeoff_count: Literal[
        "COUNT_CLOSED_POSITIONS_WITH_MARKET_TERMINATION_WRITEOFF_REASON"
    ] = "COUNT_CLOSED_POSITIONS_WITH_MARKET_TERMINATION_WRITEOFF_REASON"
    termination_writeoff_net_pl: Literal[
        "SUM_NET_PL_OF_MARKET_TERMINATION_WRITEOFF_TRADES"
    ] = "SUM_NET_PL_OF_MARKET_TERMINATION_WRITEOFF_TRADES"
    active_symbol_count: Literal[
        "COUNT_BASELINE_NONOMITTED_SYMBOLS_WITH_ENTRY_BAR_AND_CONSECUTIVE_SIGNAL_HISTORY"
    ] = (
        "COUNT_BASELINE_NONOMITTED_SYMBOLS_WITH_ENTRY_BAR_AND_CONSECUTIVE_SIGNAL_HISTORY"
    )
    quarterly_positive_test: Literal["FOLD_NET_PL_STRICTLY_GREATER_THAN_ZERO"] = (
        "FOLD_NET_PL_STRICTLY_GREATER_THAN_ZERO"
    )
    validation_pass_rule: Literal["ALL_NINE_GATES_REQUIRED"] = (
        "ALL_NINE_GATES_REQUIRED"
    )
    validation_pass_action: Literal["PERMIT_PINE_PARITY_REVIEW_ONLY"] = (
        "PERMIT_PINE_PARITY_REVIEW_ONLY"
    )

    model_config = ConfigDict(extra="forbid")


class R4ExecutionSpecification(BaseModel):
    schema_version: Literal["aurex-r4-validation-execution-specification-v1"] = (
        R4_EXECUTION_SPEC_SCHEMA_VERSION
    )
    specification_id: Literal["r4-path-quality-validation-execution-v1"] = (
        "r4-path-quality-validation-execution-v1"
    )
    specification_version: Literal["1.0.0"] = "1.0.0"
    registered_at: datetime
    status: Literal["FROZEN_PRE_R4_OUTCOME"] = "FROZEN_PRE_R4_OUTCOME"
    r4_candidate_protocol_evidence_hash: str
    parent_r31_execution_specification_evidence_hash: str
    validation_dataset_bundle_evidence_hash: str
    universe_manifest_evidence_hash: str
    development_dataset_bundle_evidence_hash: str
    builder_contract_hash: str
    permitted_semantic_delta: Literal[
        "PROSPECTIVE_TERMINAL_MARKET_UNAVAILABILITY_ONLY"
    ] = "PROSPECTIVE_TERMINAL_MARKET_UNAVAILABILITY_ONLY"
    arithmetic: R31ArithmeticSemantics
    inputs: R4InputAvailabilitySemantics
    signals: R31SignalExecutionSemantics
    indicators: R3IndicatorSemantics
    orders: R3OrderSemantics
    allocation: R3AllocationSemantics
    lifecycle: R4MarketLifecycleSemantics
    folds: R4ValidationFoldSemantics
    metrics: R4ValidationMetricSemantics
    preexisting_result_artifacts: list[str] = Field(default_factory=list)
    outcome_fields_inspected: list[str] = Field(default_factory=list)
    specification_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("registered_at")
    @classmethod
    def normalize_registered_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "r4_candidate_protocol_evidence_hash",
        "parent_r31_execution_specification_evidence_hash",
        "validation_dataset_bundle_evidence_hash",
        "universe_manifest_evidence_hash",
        "development_dataset_bundle_evidence_hash",
        "builder_contract_hash",
        "specification_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("preexisting_result_artifacts", "outcome_fields_inspected")
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_specification(self) -> "R4ExecutionSpecification":
        if self.preexisting_result_artifacts or self.outcome_fields_inspected:
            raise ValueError("R4 execution specification must predate every outcome")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"specification_evidence_hash"})
        )
        if self.specification_evidence_hash != expected_hash:
            raise ValueError("R4 execution specification hash does not match evidence")
        return self


def build_r4_execution_specification(**values) -> R4ExecutionSpecification:
    payload = {
        "schema_version": R4_EXECUTION_SPEC_SCHEMA_VERSION,
        "specification_id": "r4-path-quality-validation-execution-v1",
        "specification_version": "1.0.0",
        "status": "FROZEN_PRE_R4_OUTCOME",
        "permitted_semantic_delta": (
            "PROSPECTIVE_TERMINAL_MARKET_UNAVAILABILITY_ONLY"
        ),
        **values,
    }
    payload["registered_at"] = normalize_timestamp(payload["registered_at"])
    payload["preexisting_result_artifacts"] = sorted(
        set(payload["preexisting_result_artifacts"])
    )
    payload["outcome_fields_inspected"] = sorted(
        set(payload["outcome_fields_inspected"])
    )
    return R4ExecutionSpecification(
        **payload,
        specification_evidence_hash=universe_evidence_hash(payload),
    )


def audit_r4_execution_specification(
    specification: R4ExecutionSpecification,
) -> bool:
    return specification.specification_evidence_hash == universe_evidence_hash(
        specification.model_dump(exclude={"specification_evidence_hash"})
    )
