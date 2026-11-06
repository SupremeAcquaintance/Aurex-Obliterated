from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S2_BACKTEST_PROTOCOL_NEXT = "AUTHORIZE_S2_DEVELOPMENT_BACKTEST_RUNNER_IMPLEMENTATION_ONLY"
S2_BACKTEST_EXECUTION_NEXT = "AUTHORIZE_S2_DEVELOPMENT_BACKTEST_RUN_ONCE"
S2_BACKTEST_PASS = "PASS_S2_DEVELOPMENT_BACKTEST"
S2_BACKTEST_STOP = "STOP_S2_DEVELOPMENT_BACKTEST_FAILED_RETIRE_S2"


class S2DevelopmentBacktestProtocol(BaseModel):
    schema_version: Literal["aurex-s2-development-backtest-protocol-v1"] = (
        "aurex-s2-development-backtest-protocol-v1"
    )
    protocol_id: Literal["s2-development-backtest-protocol-v1"] = (
        "s2-development-backtest-protocol-v1"
    )
    frozen_at: datetime
    builder_contract_hash: str
    preregistration_file_sha256: str
    preregistration_evidence_hash: str
    preregistration_audit_file_sha256: str
    preregistration_audit_evidence_hash: str
    measurement_result_file_sha256: str
    measurement_result_evidence_hash: str
    measurement_audit_file_sha256: str
    measurement_audit_evidence_hash: str
    measurement_dataset_path: Literal[
        "data/evidence/s2_development_measurements_v1.jsonl"
    ] = "data/evidence/s2_development_measurements_v1.jsonl"
    measurement_dataset_file_sha256: str
    source_result_file_sha256: str
    source_result_evidence_hash: str
    source_audit_file_sha256: str
    source_audit_evidence_hash: str
    price_dataset_path: Literal[
        "data/evidence/datasets/s2_btcusdt_monday_00h_opens_v1.jsonl"
    ] = "data/evidence/datasets/s2_btcusdt_monday_00h_opens_v1.jsonl"
    price_dataset_file_sha256: str
    candidate_id: Literal["S2-C1-SETTLEMENT-DEMAND-BREADTH-PRIMARY"] = (
        "S2-C1-SETTLEMENT-DEMAND-BREADTH-PRIMARY"
    )
    candidate_count: Literal[1] = 1
    parameter_combination_count: Literal[1] = 1
    signal_rule: Literal["SETTLEMENT_DEMAND_AGREEMENT_EQ_BOTH_BROADENING"] = (
        "SETTLEMENT_DEMAND_AGREEMENT_EQ_BOTH_BROADENING"
    )
    true_position: Literal[1] = 1
    false_position: Literal[0] = 0
    first_signal_sequence: Literal[8] = 8
    last_signal_sequence: Literal[279] = 279
    terminal_price_sequence: Literal[280] = 280
    measurement_row_count: Literal[273] = 273
    price_row_count: Literal[273] = 273
    interval_count: Literal[272] = 272
    alignment_rule: Literal[
        "MEASUREMENT_SEQUENCE_EQUALS_PRICE_MEASUREMENT_SEQUENCE_AND_EARLIEST_EXECUTION_DATE_EQUALS_ACTIVATION_DATE"
    ] = (
        "MEASUREMENT_SEQUENCE_EQUALS_PRICE_MEASUREMENT_SEQUENCE_AND_EARLIEST_EXECUTION_DATE_EQUALS_ACTIVATION_DATE"
    )
    initial_equity_usd: Literal["100"] = "100"
    position_values: tuple[int, int] = (0, 1)
    rebalance_rule: Literal["REBALANCE_ONLY_WHEN_BINARY_POSITION_CHANGES"] = (
        "REBALANCE_ONLY_WHEN_BINARY_POSITION_CHANGES"
    )
    terminal_position_rule: Literal[
        "FORCE_CASH_AT_TERMINAL_PRICE_AND_CHARGE_ONE_FILL_IF_LONG"
    ] = "FORCE_CASH_AT_TERMINAL_PRICE_AND_CHARGE_ONE_FILL_IF_LONG"
    base_cost_bps_per_fill: Literal["15"] = "15"
    stress_cost_bps_per_fill: Literal["22.5"] = "22.5"
    cost_formula: Literal[
        "EQUITY_AFTER_COST_EQUALS_EQUITY_BEFORE_COST_TIMES_ONE_MINUS_COST_BPS_DIV_10000"
    ] = "EQUITY_AFTER_COST_EQUALS_EQUITY_BEFORE_COST_TIMES_ONE_MINUS_COST_BPS_DIV_10000"
    arithmetic: Literal["PYTHON_DECIMAL_PRECISION_60_EXACT_SOURCE_TEXT"] = (
        "PYTHON_DECIMAL_PRECISION_60_EXACT_SOURCE_TEXT"
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
    weekly_sharpe_formula: Literal[
        "MEAN_NET_WEEKLY_RETURN_DIV_SAMPLE_STANDARD_DEVIATION_TIMES_SQRT_52_ZERO_RISK_FREE"
    ] = "MEAN_NET_WEEKLY_RETURN_DIV_SAMPLE_STANDARD_DEVIATION_TIMES_SQRT_52_ZERO_RISK_FREE"
    weekly_sharpe_zero_variance_policy: Literal[
        "POSITIVE_MEAN_IS_INFINITY_ELSE_ZERO"
    ] = "POSITIVE_MEAN_IS_INFINITY_ELSE_ZERO"
    cagr_formula: Literal[
        "FINAL_DIV_INITIAL_POWER_52_DIV_272_MINUS_ONE"
    ] = "FINAL_DIV_INITIAL_POWER_52_DIV_272_MINUS_ONE"
    calmar_formula: Literal["BASE_CAGR_DIV_BASE_MAXIMUM_DRAWDOWN"] = (
        "BASE_CAGR_DIV_BASE_MAXIMUM_DRAWDOWN"
    )
    calmar_zero_drawdown_policy: Literal["POSITIVE_CAGR_IS_INFINITY_ELSE_ZERO"] = (
        "POSITIVE_CAGR_IS_INFINITY_ELSE_ZERO"
    )
    buy_hold_rule: Literal[
        "LONG_ALL_272_INTERVALS_WITH_BASE_ENTRY_AND_TERMINAL_EXIT_COSTS"
    ] = "LONG_ALL_272_INTERVALS_WITH_BASE_ENTRY_AND_TERMINAL_EXIT_COSTS"
    drawdown_comparison_formula: Literal[
        "BASE_STRATEGY_MAXIMUM_DRAWDOWN_MINUS_BASE_BUY_HOLD_MAXIMUM_DRAWDOWN"
    ] = "BASE_STRATEGY_MAXIMUM_DRAWDOWN_MINUS_BASE_BUY_HOLD_MAXIMUM_DRAWDOWN"
    annual_return_assignment: Literal["INTERVAL_START_ACTIVATION_DATE_YEAR"] = (
        "INTERVAL_START_ACTIVATION_DATE_YEAR"
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
    bootstrap_seed: Literal[2718] = 2718
    bootstrap_lower_confidence: Literal["0.95"] = "0.95"
    bootstrap_lower_order_index_zero_based: Literal[499] = 499
    development_gate_count: Literal[15] = 15
    gate_source: Literal["EXACT_S2_STRATEGY_PREREGISTRATION_DEVELOPMENT_GATES"] = (
        "EXACT_S2_STRATEGY_PREREGISTRATION_DEVELOPMENT_GATES"
    )
    primary_failure_policy: Literal["STOP_S2_NO_RESCUE_OR_DIAGNOSTIC_PROMOTION"] = (
        "STOP_S2_NO_RESCUE_OR_DIAGNOSTIC_PROMOTION"
    )
    outcome_ledger_path: Literal[
        "data/evidence/datasets/s2_development_backtest_ledger_v1.jsonl"
    ] = "data/evidence/datasets/s2_development_backtest_ledger_v1.jsonl"
    measurement_values_parsed_during_protocol_freeze: Literal[0] = 0
    price_values_parsed_during_protocol_freeze: Literal[0] = 0
    returns_calculated_during_protocol_freeze: Literal[0] = 0
    authorizes_protocol_only: Literal[True] = True
    authorizes_runner_implementation: Literal[True] = True
    authorizes_backtest_execution_now: Literal[False] = False
    authorizes_historical_screen_access: Literal[False] = False
    authorizes_validation_access: Literal[False] = False
    authorizes_holdout_access: Literal[False] = False
    authorizes_rescue_candidate: Literal[False] = False
    authorizes_pine: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    next_authorization: Literal[
        "AUTHORIZE_S2_DEVELOPMENT_BACKTEST_RUNNER_IMPLEMENTATION_ONLY"
    ] = S2_BACKTEST_PROTOCOL_NEXT
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "preregistration_file_sha256",
        "preregistration_evidence_hash",
        "preregistration_audit_file_sha256",
        "preregistration_audit_evidence_hash",
        "measurement_result_file_sha256",
        "measurement_result_evidence_hash",
        "measurement_audit_file_sha256",
        "measurement_audit_evidence_hash",
        "measurement_dataset_file_sha256",
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
    def validate_protocol(self) -> S2DevelopmentBacktestProtocol:
        if self.position_values != (0, 1):
            raise ValueError("S2 backtest position domain changed")
        if self.last_signal_sequence - self.first_signal_sequence + 1 != self.interval_count:
            raise ValueError("S2 backtest signal interval changed")
        if self.bootstrap_lower_order_index_zero_based != 499:
            raise ValueError("S2 backtest bootstrap quantile changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S2 development backtest protocol hash changed")
        return self


class S2DevelopmentBacktestProtocolAudit(BaseModel):
    schema_version: Literal["aurex-s2-development-backtest-protocol-audit-v1"] = (
        "aurex-s2-development-backtest-protocol-audit-v1"
    )
    audit_id: Literal["s2-development-backtest-protocol-audit-v1"] = (
        "s2-development-backtest-protocol-audit-v1"
    )
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    builder_contract_hash: str
    preregistration_evidence_hash: str
    measurement_result_evidence_hash: str
    source_result_evidence_hash: str
    source_audit_evidence_hash: str
    measurement_dataset_file_sha256: str
    price_dataset_file_sha256: str
    auditor_contract_hash: str
    measurement_values_parsed: Literal[0] = 0
    price_values_parsed: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    reconstructed_exactly: Literal[True] = True
    decision: Literal["PASS_S2_DEVELOPMENT_BACKTEST_PROTOCOL_AUDIT"] = (
        "PASS_S2_DEVELOPMENT_BACKTEST_PROTOCOL_AUDIT"
    )
    next_authorization: Literal[
        "AUTHORIZE_S2_DEVELOPMENT_BACKTEST_RUNNER_IMPLEMENTATION_ONLY"
    ] = S2_BACKTEST_PROTOCOL_NEXT
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "builder_contract_hash",
        "preregistration_evidence_hash",
        "measurement_result_evidence_hash",
        "source_result_evidence_hash",
        "source_audit_evidence_hash",
        "measurement_dataset_file_sha256",
        "price_dataset_file_sha256",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S2DevelopmentBacktestProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S2 development backtest protocol audit hash changed")
        return self


class S2DevelopmentIntervalOutcome(BaseModel):
    candidate_id: Literal["S2-C1-SETTLEMENT-DEMAND-BREADTH-PRIMARY"]
    interval_sequence: int = Field(ge=1, le=272)
    measurement_sequence: int = Field(ge=8, le=279)
    activation_date: date
    next_activation_date: date
    activation_open_time_ms: int = Field(ge=1)
    next_activation_open_time_ms: int = Field(ge=1)
    open_price: str
    next_open_price: str
    settlement_demand_agreement: Literal[
        "BOTH_BROADENING", "BOTH_CONTRACTING", "FLAT_OR_MIXED"
    ]
    desired_position: int = Field(ge=0, le=1)
    prior_position: int = Field(ge=0, le=1)
    entry_fill: bool
    terminal_liquidation_fill: bool
    fill_count: int = Field(ge=0, le=2)
    gross_interval_return: str
    base_equity_before: str
    base_equity_after: str
    base_interval_return: str
    base_interval_pnl_usd: str
    stress_equity_before: str
    stress_equity_after: str
    stress_interval_return: str
    stress_interval_pnl_usd: str
    measurement_row_evidence_hash: str
    current_price_row_evidence_hash: str
    next_price_row_evidence_hash: str
    interval_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator(
        "measurement_row_evidence_hash",
        "current_price_row_evidence_hash",
        "next_price_row_evidence_hash",
        "interval_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_interval(self) -> S2DevelopmentIntervalOutcome:
        if self.next_activation_date <= self.activation_date:
            raise ValueError("S2 interval dates are not increasing")
        if self.next_activation_open_time_ms <= self.activation_open_time_ms:
            raise ValueError("S2 interval timestamps are not increasing")
        if self.fill_count != int(self.entry_fill) + int(self.terminal_liquidation_fill):
            raise ValueError("S2 interval fill count changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"interval_evidence_hash"})
        )
        if self.interval_evidence_hash != expected:
            raise ValueError("S2 interval evidence hash changed")
        return self


class S2DevelopmentCandidateOutcome(BaseModel):
    candidate_id: Literal["S2-C1-SETTLEMENT-DEMAND-BREADTH-PRIMARY"]
    interval_count: Literal[272] = 272
    position_transition_count: int = Field(ge=0, le=273)
    long_interval_count: int = Field(ge=0, le=272)
    long_exposure_fraction: str
    base_final_equity_usd: str
    base_net_total_return: str
    base_profit_factor: str
    base_maximum_drawdown: str
    base_weekly_sharpe: str
    base_cagr: str
    base_calmar_ratio: str
    stress_final_equity_usd: str
    stress_net_total_return: str
    stress_profit_factor: str
    stress_maximum_drawdown: str
    stress_weekly_sharpe: str
    annual_base_returns: dict[int, str]
    positive_full_calendar_year_count: int = Field(ge=0, le=5)
    stress_bootstrap_lower_mean_weekly_return: str
    buy_hold_base_final_equity_usd: str
    buy_hold_base_net_total_return: str
    buy_hold_base_maximum_drawdown: str
    base_drawdown_minus_buy_hold_drawdown: str
    interval_manifest_evidence_hash: str
    outcome_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("interval_manifest_evidence_hash", "outcome_evidence_hash")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_outcome(self) -> S2DevelopmentCandidateOutcome:
        if tuple(sorted(self.annual_base_returns)) != (2018, 2019, 2020, 2021, 2022):
            raise ValueError("S2 annual return years changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"outcome_evidence_hash"})
        )
        if self.outcome_evidence_hash != expected:
            raise ValueError("S2 candidate outcome hash changed")
        return self


class S2DevelopmentGateResult(BaseModel):
    gate_id: str
    operator: Literal["EQ", "GE", "LE", "GT", "LT"]
    threshold: str
    observed: str
    status: Literal["PASS", "FAIL"]
    reason: str

    model_config = ConfigDict(extra="forbid", frozen=True)


class S2DevelopmentBacktestExecutionContract(BaseModel):
    schema_version: Literal["aurex-s2-development-backtest-execution-contract-v1"] = (
        "aurex-s2-development-backtest-execution-contract-v1"
    )
    contract_id: Literal["s2-development-backtest-execution-contract-v1"] = (
        "s2-development-backtest-execution-contract-v1"
    )
    frozen_at: datetime
    builder_contract_hash: str
    protocol_file_sha256: str
    protocol_evidence_hash: str
    protocol_audit_file_sha256: str
    protocol_audit_evidence_hash: str
    runner_contract_hash: str
    synthetic_test_ids: tuple[str, ...] = Field(min_length=12)
    measurement_dataset_file_sha256: str
    price_dataset_file_sha256: str
    output_paths_absent: Literal[True] = True
    authorizes_one_development_backtest: Literal[True] = True
    authorizes_historical_screen_access: Literal[False] = False
    authorizes_validation_access: Literal[False] = False
    authorizes_holdout_access: Literal[False] = False
    authorizes_rescue_candidate: Literal[False] = False
    authorizes_pine: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    next_authorization: Literal[
        "AUTHORIZE_S2_DEVELOPMENT_BACKTEST_RUN_ONCE"
    ] = S2_BACKTEST_EXECUTION_NEXT
    contract_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "protocol_audit_file_sha256",
        "protocol_audit_evidence_hash",
        "runner_contract_hash",
        "measurement_dataset_file_sha256",
        "price_dataset_file_sha256",
        "contract_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_contract(self) -> S2DevelopmentBacktestExecutionContract:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"contract_evidence_hash"})
        )
        if self.contract_evidence_hash != expected:
            raise ValueError("S2 backtest execution contract hash changed")
        return self


class S2DevelopmentBacktestExecutionAudit(BaseModel):
    schema_version: Literal["aurex-s2-development-backtest-execution-audit-v1"] = (
        "aurex-s2-development-backtest-execution-audit-v1"
    )
    audit_id: Literal["s2-development-backtest-execution-audit-v1"] = (
        "s2-development-backtest-execution-audit-v1"
    )
    audited_at: datetime
    contract_file_sha256: str
    contract_evidence_hash: str
    protocol_evidence_hash: str
    runner_contract_hash: str
    auditor_contract_hash: str
    synthetic_test_ids: tuple[str, ...] = Field(min_length=12)
    reconstructed_exactly: Literal[True] = True
    measurement_values_parsed: Literal[0] = 0
    price_values_parsed: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    decision: Literal["PASS_S2_DEVELOPMENT_BACKTEST_EXECUTION_AUDIT"] = (
        "PASS_S2_DEVELOPMENT_BACKTEST_EXECUTION_AUDIT"
    )
    next_authorization: Literal[
        "AUTHORIZE_S2_DEVELOPMENT_BACKTEST_RUN_ONCE"
    ] = S2_BACKTEST_EXECUTION_NEXT
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "contract_file_sha256",
        "contract_evidence_hash",
        "protocol_evidence_hash",
        "runner_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S2DevelopmentBacktestExecutionAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S2 backtest execution audit hash changed")
        return self


class S2DevelopmentBacktestResult(BaseModel):
    schema_version: Literal["aurex-s2-development-backtest-result-v1"] = (
        "aurex-s2-development-backtest-result-v1"
    )
    result_id: Literal["s2-development-backtest-result-v1"] = (
        "s2-development-backtest-result-v1"
    )
    completed_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    execution_contract_file_sha256: str
    execution_contract_evidence_hash: str
    runner_contract_hash: str
    measurement_dataset_file_sha256: str
    price_dataset_file_sha256: str
    outcome_ledger_path: str
    outcome_ledger_file_sha256: str
    outcome_ledger_bytes: int = Field(ge=1)
    outcome_ledger_row_count: Literal[272] = 272
    candidate_outcome: S2DevelopmentCandidateOutcome
    gate_results: tuple[S2DevelopmentGateResult, ...] = Field(
        min_length=15, max_length=15
    )
    passed_gate_count: int = Field(ge=0, le=15)
    failed_gate_count: int = Field(ge=0, le=15)
    candidate_count: Literal[1] = 1
    parameter_combination_count: Literal[1] = 1
    rescue_candidate_count: Literal[0] = 0
    historical_screen_values_read: Literal[0] = 0
    validation_values_read: Literal[0] = 0
    holdout_values_read: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal[
        "PASS_S2_DEVELOPMENT_BACKTEST", "STOP_S2_DEVELOPMENT_BACKTEST_FAILED_RETIRE_S2"
    ]
    next_authorization: Literal[
        "AUTHORIZE_S2_HISTORICAL_SCREEN_PROTOCOL_ONLY",
        "NONE_S2_DEVELOPMENT_BACKTEST_FAILED_RETIRE_S2",
    ]
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("completed_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "execution_contract_file_sha256",
        "execution_contract_evidence_hash",
        "runner_contract_hash",
        "measurement_dataset_file_sha256",
        "price_dataset_file_sha256",
        "outcome_ledger_file_sha256",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> S2DevelopmentBacktestResult:
        if self.passed_gate_count != sum(item.status == "PASS" for item in self.gate_results):
            raise ValueError("S2 passed gate count changed")
        if self.failed_gate_count != sum(item.status == "FAIL" for item in self.gate_results):
            raise ValueError("S2 failed gate count changed")
        if (self.decision == S2_BACKTEST_PASS) != (self.failed_gate_count == 0):
            raise ValueError("S2 backtest decision does not match gates")
        if self.decision == S2_BACKTEST_STOP and self.next_authorization != (
            "NONE_S2_DEVELOPMENT_BACKTEST_FAILED_RETIRE_S2"
        ):
            raise ValueError("S2 failed backtest authority changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("S2 development backtest result hash changed")
        return self


class S2DevelopmentBacktestResultAudit(BaseModel):
    schema_version: Literal["aurex-s2-development-backtest-result-audit-v1"] = (
        "aurex-s2-development-backtest-result-audit-v1"
    )
    audit_id: Literal["s2-development-backtest-result-audit-v1"] = (
        "s2-development-backtest-result-audit-v1"
    )
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    execution_contract_file_sha256: str
    execution_contract_evidence_hash: str
    result_file_sha256: str
    result_evidence_hash: str
    outcome_ledger_file_sha256: str
    interval_manifest_evidence_hash: str
    runner_contract_hash: str
    auditor_contract_hash: str
    measurement_rows_reparsed: Literal[273] = 273
    price_rows_reparsed: Literal[273] = 273
    interval_rows_reconstructed: Literal[272] = 272
    returns_recalculated: Literal[272] = 272
    orders_submitted: Literal[0] = 0
    reconstructed_exactly: Literal[True] = True
    decision: Literal[
        "CONFIRM_S2_DEVELOPMENT_BACKTEST_PASSED",
        "CONFIRM_S2_DEVELOPMENT_BACKTEST_FAILED_RETIRE_S2",
    ]
    lineage_next_authorization: Literal[
        "AUTHORIZE_S2_HISTORICAL_SCREEN_PROTOCOL_ONLY",
        "NONE_S2_DEVELOPMENT_BACKTEST_FAILED_RETIRE_S2",
    ]
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "execution_contract_file_sha256",
        "execution_contract_evidence_hash",
        "result_file_sha256",
        "result_evidence_hash",
        "outcome_ledger_file_sha256",
        "interval_manifest_evidence_hash",
        "runner_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S2DevelopmentBacktestResultAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S2 development backtest result audit hash changed")
        return self
