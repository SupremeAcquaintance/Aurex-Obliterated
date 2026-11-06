from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S1_1_OUTCOME_PROTOCOL_NEXT = (
    "AUTHORIZE_S1_1_DEVELOPMENT_OUTCOME_RUNNER_IMPLEMENTATION_ONLY"
)


class S11DevelopmentOutcomeProtocol(BaseModel):
    schema_version: Literal["aurex-s1-1-development-outcome-protocol-v1"] = (
        "aurex-s1-1-development-outcome-protocol-v1"
    )
    protocol_id: Literal["s1-1-development-outcome-protocol-v1"] = (
        "s1-1-development-outcome-protocol-v1"
    )
    frozen_at: datetime
    builder_contract_hash: str
    strategy_preregistration_file_sha256: str
    strategy_preregistration_evidence_hash: str
    timing_amendment_file_sha256: str
    timing_amendment_evidence_hash: str
    timing_amendment_audit_file_sha256: str
    timing_amendment_audit_evidence_hash: str
    feature_result_file_sha256: str
    feature_result_evidence_hash: str
    feature_audit_file_sha256: str
    feature_audit_evidence_hash: str
    feature_dataset_path: Literal[
        "data/evidence/datasets/s1_nfci_development_features_v1.jsonl"
    ] = "data/evidence/datasets/s1_nfci_development_features_v1.jsonl"
    feature_dataset_file_sha256: str
    feature_dataset_bytes: Literal[90632] = 90_632
    source_result_file_sha256: str
    source_result_evidence_hash: str
    source_audit_file_sha256: str
    source_audit_evidence_hash: str
    price_dataset_path: Literal[
        "data/evidence/datasets/s1_1_btcusdt_friday_first_opens_v2.jsonl"
    ] = "data/evidence/datasets/s1_1_btcusdt_friday_first_opens_v2.jsonl"
    price_dataset_file_sha256: str
    price_dataset_bytes: Literal[209909] = 209_909
    feature_row_count: Literal[277] = 277
    price_row_count: Literal[277] = 277
    expected_interval_count: Literal[276] = 276
    first_scored_feature_sequence: Literal[5] = 5
    last_scored_feature_sequence: Literal[280] = 280
    terminal_feature_sequence: Literal[281] = 281
    development_attempt_index: Literal[2] = 2
    prior_materialized_execution_price_count_declared: Literal[21] = 21
    prior_return_count_declared: Literal[0] = 0
    primary_candidate_id: Literal["S1-C1-CONSISTENT-EASING-PRIMARY"] = (
        "S1-C1-CONSISTENT-EASING-PRIMARY"
    )
    candidate_count: Literal[4] = 4
    promotable_candidate_count: Literal[1] = 1
    diagnostic_rescue_permitted: Literal[False] = False
    initial_position: Literal["CASH"] = "CASH"
    initial_equity_usd: Literal["100"] = "100"
    position_values: tuple[int, int] = (0, 1)
    signal_equality_policy: Literal["EQUALITY_IS_CASH"] = "EQUALITY_IS_CASH"
    interval_return_formula: Literal[
        "LONG_PRICE_NEXT_DIV_PRICE_CURRENT_MINUS_1_ELSE_0"
    ] = "LONG_PRICE_NEXT_DIV_PRICE_CURRENT_MINUS_1_ELSE_0"
    fill_rule: Literal[
        "ONE_FILL_WHEN_DESIRED_BINARY_POSITION_DIFFERS_FROM_CURRENT_POSITION"
    ] = "ONE_FILL_WHEN_DESIRED_BINARY_POSITION_DIFFERS_FROM_CURRENT_POSITION"
    initial_entry_cost_policy: Literal["CHARGE_IF_FIRST_DESIRED_POSITION_IS_LONG"] = (
        "CHARGE_IF_FIRST_DESIRED_POSITION_IS_LONG"
    )
    terminal_liquidation_policy: Literal[
        "FORCE_CASH_AT_FINAL_PRICE_AND_CHARGE_ONE_FILL_IF_LONG"
    ] = "FORCE_CASH_AT_FINAL_PRICE_AND_CHARGE_ONE_FILL_IF_LONG"
    base_cost_bps_per_fill: Literal["15"] = "15"
    stress_cost_bps_per_fill: Literal["22.5"] = "22.5"
    cost_equity_formula: Literal[
        "EQUITY_AFTER_COST_EQUALS_EQUITY_BEFORE_COST_TIMES_ONE_MINUS_COST_BPS_DIV_10000"
    ] = "EQUITY_AFTER_COST_EQUALS_EQUITY_BEFORE_COST_TIMES_ONE_MINUS_COST_BPS_DIV_10000"
    arithmetic: Literal["PYTHON_DECIMAL_EXACT_SOURCE_TEXT"] = (
        "PYTHON_DECIMAL_EXACT_SOURCE_TEXT"
    )
    profit_factor_formula: Literal[
        "SUM_POSITIVE_INTERVAL_DOLLAR_PNL_DIV_ABS_SUM_NEGATIVE_INTERVAL_DOLLAR_PNL"
    ] = "SUM_POSITIVE_INTERVAL_DOLLAR_PNL_DIV_ABS_SUM_NEGATIVE_INTERVAL_DOLLAR_PNL"
    profit_factor_zero_loss_policy: Literal["POSITIVE_GAIN_IS_INFINITY_ELSE_ZERO"] = (
        "POSITIVE_GAIN_IS_INFINITY_ELSE_ZERO"
    )
    maximum_drawdown_formula: Literal[
        "MAX_PEAK_TO_TROUGH_DECLINE_ON_POST_INTERVAL_EQUITY_CURVE_WITH_INITIAL_EQUITY"
    ] = "MAX_PEAK_TO_TROUGH_DECLINE_ON_POST_INTERVAL_EQUITY_CURVE_WITH_INITIAL_EQUITY"
    annual_return_assignment: Literal["INTERVAL_START_TARGET_DATE_YEAR"] = (
        "INTERVAL_START_TARGET_DATE_YEAR"
    )
    full_years: tuple[int, ...] = (2018, 2019, 2020, 2021, 2022)
    bootstrap_input: Literal["STRESS_NET_INTERVAL_RETURNS"] = (
        "STRESS_NET_INTERVAL_RETURNS"
    )
    bootstrap_method: Literal[
        "STATIONARY_BLOCK_BOOTSTRAP_WITH_GEOMETRIC_RESTART_PROBABILITY"
    ] = "STATIONARY_BLOCK_BOOTSTRAP_WITH_GEOMETRIC_RESTART_PROBABILITY"
    bootstrap_resamples: Literal[10000] = 10_000
    bootstrap_mean_block_weeks: Literal[8] = 8
    bootstrap_restart_probability: Literal["0.125"] = "0.125"
    bootstrap_seed: Literal[1729] = 1729
    bootstrap_lower_confidence: Literal["0.95"] = "0.95"
    bootstrap_lower_order_index_zero_based: Literal[499] = 499
    gate_count: Literal[12] = 12
    gate_source: Literal[
        "EXACT_S1_STRATEGY_PREREGISTRATION_DEVELOPMENT_GATES"
    ] = "EXACT_S1_STRATEGY_PREREGISTRATION_DEVELOPMENT_GATES"
    primary_failure_policy: Literal["STOP_S1_NO_DIAGNOSTIC_PROMOTION"] = (
        "STOP_S1_NO_DIAGNOSTIC_PROMOTION"
    )
    outcome_ledger_path: Literal[
        "data/evidence/datasets/s1_1_development_outcome_ledger_v1.jsonl"
    ] = "data/evidence/datasets/s1_1_development_outcome_ledger_v1.jsonl"
    feature_values_parsed_during_protocol_freeze: Literal[0] = 0
    price_values_parsed_during_protocol_freeze: Literal[0] = 0
    returns_calculated_during_protocol_freeze: Literal[0] = 0
    authorizes_protocol_only: Literal[True] = True
    authorizes_runner_implementation: Literal[True] = True
    authorizes_outcome_execution_now: Literal[False] = False
    authorizes_validation_access: Literal[False] = False
    authorizes_holdout_access: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    next_authorization: Literal[
        "AUTHORIZE_S1_1_DEVELOPMENT_OUTCOME_RUNNER_IMPLEMENTATION_ONLY"
    ] = S1_1_OUTCOME_PROTOCOL_NEXT
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "strategy_preregistration_file_sha256",
        "strategy_preregistration_evidence_hash",
        "timing_amendment_file_sha256",
        "timing_amendment_evidence_hash",
        "timing_amendment_audit_file_sha256",
        "timing_amendment_audit_evidence_hash",
        "feature_result_file_sha256",
        "feature_result_evidence_hash",
        "feature_audit_file_sha256",
        "feature_audit_evidence_hash",
        "feature_dataset_file_sha256",
        "source_result_file_sha256",
        "source_result_evidence_hash",
        "source_audit_file_sha256",
        "source_audit_evidence_hash",
        "price_dataset_file_sha256",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S11DevelopmentOutcomeProtocol:
        if self.position_values != (0, 1):
            raise ValueError("S1.1 position domain changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S1.1 outcome protocol hash changed")
        return self


class S11DevelopmentOutcomeProtocolAudit(BaseModel):
    schema_version: Literal["aurex-s1-1-development-outcome-protocol-audit-v1"] = (
        "aurex-s1-1-development-outcome-protocol-audit-v1"
    )
    audit_id: Literal["s1-1-development-outcome-protocol-audit-v1"] = (
        "s1-1-development-outcome-protocol-audit-v1"
    )
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    builder_contract_hash: str
    strategy_preregistration_evidence_hash: str
    timing_amendment_evidence_hash: str
    source_result_evidence_hash: str
    source_audit_evidence_hash: str
    feature_dataset_file_sha256: str
    price_dataset_file_sha256: str
    auditor_source_sha256: str
    feature_values_parsed: Literal[0] = 0
    price_values_parsed: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    reconstructed_exactly: Literal[True] = True
    decision: Literal["PASS_S1_1_DEVELOPMENT_OUTCOME_PROTOCOL_RECONSTRUCTED"] = (
        "PASS_S1_1_DEVELOPMENT_OUTCOME_PROTOCOL_RECONSTRUCTED"
    )
    next_authorization: Literal[
        "AUTHORIZE_S1_1_DEVELOPMENT_OUTCOME_RUNNER_IMPLEMENTATION_ONLY"
    ] = S1_1_OUTCOME_PROTOCOL_NEXT
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "builder_contract_hash",
        "strategy_preregistration_evidence_hash",
        "timing_amendment_evidence_hash",
        "source_result_evidence_hash",
        "source_audit_evidence_hash",
        "feature_dataset_file_sha256",
        "price_dataset_file_sha256",
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S11DevelopmentOutcomeProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1.1 outcome protocol audit hash changed")
        return self
