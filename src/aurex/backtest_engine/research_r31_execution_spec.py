from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from aurex.backtest_engine.research_execution_spec import (
    R3AllocationSemantics,
    R3FoldSemantics,
    R3IndicatorSemantics,
    R3InputSemantics,
    R3MetricSemantics,
    R3OrderSemantics,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

R31_EXECUTION_SPEC_SCHEMA_VERSION = "aurex-r3.1-execution-specification-v1"


class R31ArithmeticSemantics(BaseModel):
    decimal_precision: Literal[50] = 50
    decimal_rounding: Literal["ROUND_HALF_EVEN"] = "ROUND_HALF_EVEN"
    logarithm_method: Literal["DECIMAL_LN_IN_PINNED_CONTEXT"] = (
        "DECIMAL_LN_IN_PINNED_CONTEXT"
    )
    intermediate_rounding: Literal["NONE"] = "NONE"
    persisted_decimal_format: Literal["CANONICAL_DECIMAL_STRING"] = (
        "CANONICAL_DECIMAL_STRING"
    )

    model_config = ConfigDict(extra="forbid")


class R31SignalExecutionSemantics(BaseModel):
    rebalance_anchor: Literal["EVALUATION_START_00_UTC"] = (
        "EVALUATION_START_00_UTC"
    )
    signal_bar_index: Literal["ENTRY_INDEX_MINUS_ONE"] = "ENTRY_INDEX_MINUS_ONE"
    lookback_start_index: Literal["SIGNAL_INDEX_MINUS_504"] = (
        "SIGNAL_INDEX_MINUS_504"
    )
    close_observation_indices: Literal[
        "INCLUSIVE_LOOKBACK_START_THROUGH_SIGNAL_INDEX"
    ] = "INCLUSIVE_LOOKBACK_START_THROUGH_SIGNAL_INDEX"
    close_observation_count: Literal[505] = 505
    lookback_interval_count: Literal[504] = 504
    regression_x_values: Literal["EXACT_INTEGERS_0_THROUGH_504"] = (
        "EXACT_INTEGERS_0_THROUGH_504"
    )
    regression_x_mean: Literal["252"] = "252"
    regression_sxx: Literal["10732260"] = "10732260"
    regression_y_values: Literal["NATURAL_LOG_OF_EACH_CLOSE"] = (
        "NATURAL_LOG_OF_EACH_CLOSE"
    )
    regression_y_mean: Literal["ARITHMETIC_MEAN_OF_505_LOG_CLOSES"] = (
        "ARITHMETIC_MEAN_OF_505_LOG_CLOSES"
    )
    slope_formula: Literal["SUM_X_DEVIATION_TIMES_Y_DEVIATION_DIVIDED_BY_SXX"] = (
        "SUM_X_DEVIATION_TIMES_Y_DEVIATION_DIVIDED_BY_SXX"
    )
    intercept_formula: Literal["Y_MEAN_MINUS_SLOPE_TIMES_X_MEAN"] = (
        "Y_MEAN_MINUS_SLOPE_TIMES_X_MEAN"
    )
    sst_formula: Literal["SUM_SQUARED_Y_DEVIATIONS"] = (
        "SUM_SQUARED_Y_DEVIATIONS"
    )
    sse_formula: Literal["SUM_SQUARED_OLS_RESIDUALS"] = (
        "SUM_SQUARED_OLS_RESIDUALS"
    )
    r_squared_formula: Literal["CLAMP_ZERO_ONE_OF_ONE_MINUS_SSE_DIVIDED_BY_SST"] = (
        "CLAMP_ZERO_ONE_OF_ONE_MINUS_SSE_DIVIDED_BY_SST"
    )
    score_formula: Literal["SLOPE_TIMES_R_SQUARED"] = "SLOPE_TIMES_R_SQUARED"
    nonpositive_close_policy: Literal["BLOCK_REPLAY"] = "BLOCK_REPLAY"
    zero_sst_policy: Literal["ZERO_SCORE_AND_REJECT"] = "ZERO_SCORE_AND_REJECT"
    positive_trend_test: Literal["SLOPE_STRICTLY_GREATER_THAN_ZERO"] = (
        "SLOPE_STRICTLY_GREATER_THAN_ZERO"
    )
    ranking_order: Literal["SCORE_DESCENDING_THEN_SYMBOL_ASCENDING"] = (
        "SCORE_DESCENDING_THEN_SYMBOL_ASCENDING"
    )
    selected_count_formula: Literal[
        "CEILING_FRACTION_TIMES_BASELINE_DECISION_COUNT"
    ] = "CEILING_FRACTION_TIMES_BASELINE_DECISION_COUNT"
    selected_count_is_fixed_in_leave_one_out: Literal[True] = True
    fixed_selected_count: Literal[7] = 7
    minimum_positive_markets_source: Literal[
        "PROTOCOL_MINIMUM_RANKED_POSITIONS"
    ] = "PROTOCOL_MINIMUM_RANKED_POSITIONS"
    eligible_count_formula: Literal[
        "MIN_FIXED_SELECTED_COUNT_AND_POSITIVE_SLOPE_MARKET_COUNT"
    ] = "MIN_FIXED_SELECTED_COUNT_AND_POSITIVE_SLOPE_MARKET_COUNT"
    insufficient_positive_markets_action: Literal["HOLD_CASH"] = "HOLD_CASH"
    recorded_signal_fields: list[
        Literal["INTERCEPT", "R_SQUARED", "SCORE", "SLOPE"]
    ]

    model_config = ConfigDict(extra="forbid")

    @field_validator("recorded_signal_fields")
    @classmethod
    def validate_recorded_fields(cls, value: list[str]) -> list[str]:
        normalized = sorted(set(value))
        if normalized != ["INTERCEPT", "R_SQUARED", "SCORE", "SLOPE"]:
            raise ValueError("R3.1 recorded signal fields are fixed")
        return normalized


class R31ExecutionSpecification(BaseModel):
    schema_version: Literal["aurex-r3.1-execution-specification-v1"] = (
        R31_EXECUTION_SPEC_SCHEMA_VERSION
    )
    specification_id: Literal["r3.1-path-quality-execution-v1"] = (
        "r3.1-path-quality-execution-v1"
    )
    specification_version: Literal["1.0.0"] = "1.0.0"
    registered_at: datetime
    status: Literal["FROZEN_PRE_R31_OUTCOME"] = "FROZEN_PRE_R31_OUTCOME"
    protocol_evidence_hash: str
    parent_r3_execution_specification_evidence_hash: str
    universe_manifest_evidence_hash: str
    development_dataset_bundle_evidence_hash: str
    builder_contract_hash: str
    permitted_semantic_delta: Literal[
        "REPLACE_ENDPOINT_RETURN_SCORE_WITH_FIXED_OLS_SLOPE_TIMES_R_SQUARED"
    ] = "REPLACE_ENDPOINT_RETURN_SCORE_WITH_FIXED_OLS_SLOPE_TIMES_R_SQUARED"
    arithmetic: R31ArithmeticSemantics
    inputs: R3InputSemantics
    signals: R31SignalExecutionSemantics
    indicators: R3IndicatorSemantics
    orders: R3OrderSemantics
    allocation: R3AllocationSemantics
    folds: R3FoldSemantics
    metrics: R3MetricSemantics
    preexisting_result_artifacts: list[str]
    outcome_fields_inspected: list[str]
    specification_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("registered_at")
    @classmethod
    def normalize_registered_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_evidence_hash",
        "parent_r3_execution_specification_evidence_hash",
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
    def validate_specification(self) -> "R31ExecutionSpecification":
        if self.preexisting_result_artifacts or self.outcome_fields_inspected:
            raise ValueError("R3.1 execution specification must predate every outcome")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"specification_evidence_hash"})
        )
        if self.specification_evidence_hash != expected_hash:
            raise ValueError("R3.1 execution specification hash does not match evidence")
        return self


def build_r31_execution_specification(**values) -> R31ExecutionSpecification:
    payload = {
        "schema_version": R31_EXECUTION_SPEC_SCHEMA_VERSION,
        **values,
    }
    payload["registered_at"] = normalize_timestamp(payload["registered_at"])
    payload["preexisting_result_artifacts"] = sorted(
        set(payload["preexisting_result_artifacts"])
    )
    payload["outcome_fields_inspected"] = sorted(
        set(payload["outcome_fields_inspected"])
    )
    return R31ExecutionSpecification(
        **payload,
        specification_evidence_hash=universe_evidence_hash(payload),
    )


def audit_r31_execution_specification(
    specification: R31ExecutionSpecification,
) -> bool:
    return specification.specification_evidence_hash == universe_evidence_hash(
        specification.model_dump(exclude={"specification_evidence_hash"})
    )
