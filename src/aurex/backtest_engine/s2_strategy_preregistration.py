from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s2_bigquery_feasibility import S2FeasibilityBinding
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S2_STRATEGY_PREREG_NEXT = "AUTHORIZE_S2_BTCUSDT_MONDAY_1H_SOURCE_ACQUISITION_PROTOCOL_ONLY"


class S2StrategyCandidate(BaseModel):
    candidate_id: Literal["S2-C1-SETTLEMENT-DEMAND-BREADTH-PRIMARY"] = (
        "S2-C1-SETTLEMENT-DEMAND-BREADTH-PRIMARY"
    )
    role: Literal["PRIMARY_DEVELOPMENT_FALSIFICATION"] = "PRIMARY_DEVELOPMENT_FALSIFICATION"
    long_rule: Literal["SETTLEMENT_DEMAND_AGREEMENT_EQ_BOTH_BROADENING"] = (
        "SETTLEMENT_DEMAND_AGREEMENT_EQ_BOTH_BROADENING"
    )
    true_position: Literal["LONG_1X"] = "LONG_1X"
    false_position: Literal["CASH"] = "CASH"
    flat_or_mixed_position: Literal["CASH"] = "CASH"
    shorting_permitted: Literal[False] = False
    parameter_count: Literal[0] = 0
    parameter_combinations: Literal[1] = 1

    model_config = ConfigDict(extra="forbid", frozen=True)


class S2DevelopmentGate(BaseModel):
    gate_id: str = Field(min_length=1)
    operator: Literal["EQ", "GE", "GT", "LE", "LT"]
    threshold: str = Field(min_length=1)
    scope: Literal["PRIMARY_ONLY"] = "PRIMARY_ONLY"

    model_config = ConfigDict(extra="forbid", frozen=True)


class S2StrategyPreregistration(BaseModel):
    schema_version: Literal["aurex-s2-strategy-preregistration-v1"] = (
        "aurex-s2-strategy-preregistration-v1"
    )
    protocol_id: Literal["s2-strategy-preregistration-v1"] = "s2-strategy-preregistration-v1"
    frozen_at: datetime
    status: Literal["FROZEN_BEFORE_S2_BTC_MARKET_VALUE_READ"] = (
        "FROZEN_BEFORE_S2_BTC_MARKET_VALUE_READ"
    )
    builder_contract_hash: str
    measurement_result_file_sha256: str
    measurement_result_evidence_hash: str
    measurement_audit_file_sha256: str
    measurement_audit_evidence_hash: str
    measurement_dataset_file_sha256: str
    measurement_row_manifest_evidence_hash: str
    source_bindings: tuple[S2FeasibilityBinding, ...] = Field(min_length=7, max_length=7)
    measurement_dataset_bytes_hashed_during_freeze: Literal[130754] = 130_754
    measurement_value_rows_parsed_during_freeze: Literal[0] = 0
    measurement_row_count: Literal[273] = 273
    mechanism_id: Literal["S2-BTC-SETTLEMENT-DEMAND-BREADTH-SPOT"] = (
        "S2-BTC-SETTLEMENT-DEMAND-BREADTH-SPOT"
    )
    venue: Literal["BINANCE"] = "BINANCE"
    market_type: Literal["SPOT"] = "SPOT"
    symbol: Literal["BTCUSDT"] = "BTCUSDT"
    direction: Literal["LONG_OR_CASH"] = "LONG_OR_CASH"
    effective_leverage: Literal["1"] = "1"
    initial_equity_usd: Literal["100"] = "100"
    source_archive_granularity: Literal["DAILY"] = "DAILY"
    source_kline_interval: Literal["1h"] = "1h"
    source_base_url: Literal["https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1h"] = (
        "https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1h"
    )
    source_checksum_required: Literal[True] = True
    source_columns: tuple[str, ...] = (
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_asset_volume",
        "trade_count",
        "taker_buy_base_volume",
        "taker_buy_quote_volume",
        "ignore",
    )
    required_price_date_count: Literal[273] = 273
    first_required_price_date: Literal["2017-10-16"] = "2017-10-16"
    last_required_price_date: Literal["2023-01-02"] = "2023-01-02"
    required_price_weekday: Literal["MONDAY"] = "MONDAY"
    execution_price_rule: Literal[
        "EXACT_1H_KLINE_OPEN_AT_MEASUREMENT_EARLIEST_EXECUTION_TIMESTAMP"
    ] = "EXACT_1H_KLINE_OPEN_AT_MEASUREMENT_EARLIEST_EXECUTION_TIMESTAMP"
    missing_execution_price_policy: Literal["STOP_NO_SUBSTITUTION"] = "STOP_NO_SUBSTITUTION"
    scored_signal_sequence_start: Literal[8] = 8
    scored_signal_sequence_end_inclusive: Literal[279] = 279
    terminal_price_sequence: Literal[280] = 280
    expected_weekly_interval_count: Literal[272] = 272
    position_rule: Literal["REBALANCE_ONLY_WHEN_BINARY_POSITION_CHANGES"] = (
        "REBALANCE_ONLY_WHEN_BINARY_POSITION_CHANGES"
    )
    base_commission_bps_per_fill: Literal["10"] = "10"
    base_slippage_and_spread_bps_per_fill: Literal["5"] = "5"
    base_total_cost_bps_per_fill: Literal["15"] = "15"
    stress_cost_multiplier: Literal["1.5"] = "1.5"
    stress_total_cost_bps_per_fill: Literal["22.5"] = "22.5"
    cost_application: Literal["APPLY_PER_POSITION_CHANGING_FILL_TO_COMPOUNDED_EQUITY"] = (
        "APPLY_PER_POSITION_CHANGING_FILL_TO_COMPOUNDED_EQUITY"
    )
    candidate: S2StrategyCandidate
    candidate_count: Literal[1] = 1
    diagnostic_candidates_permitted: Literal[False] = False
    outcome_driven_parameter_search_permitted: Literal[False] = False
    primary_failure_policy: Literal["STOP_S2_NO_RESCUE_OR_DIAGNOSTIC_PROMOTION"] = (
        "STOP_S2_NO_RESCUE_OR_DIAGNOSTIC_PROMOTION"
    )
    full_years_for_year_gates: tuple[int, ...] = (2018, 2019, 2020, 2021, 2022)
    bootstrap_method: Literal["STATIONARY_BLOCK_BOOTSTRAP_WEEKLY_RETURNS"] = (
        "STATIONARY_BLOCK_BOOTSTRAP_WEEKLY_RETURNS"
    )
    bootstrap_resamples: Literal[10000] = 10_000
    bootstrap_mean_block_weeks: Literal[8] = 8
    bootstrap_seed: Literal[2718] = 2718
    bootstrap_lower_confidence: Literal["0.95"] = "0.95"
    development_gates: tuple[S2DevelopmentGate, ...] = Field(min_length=15, max_length=15)
    historical_screen_start: Literal["2023-01-01"] = "2023-01-01"
    historical_screen_end_exclusive: Literal["2026-11-07"] = "2026-11-07"
    historical_screen_remains_sealed: Literal[True] = True
    prospective_validation_remains_sealed: Literal[True] = True
    future_holdout_remains_sealed: Literal[True] = True
    authorizes_protocol_only: Literal[True] = True
    authorizes_btc_source_acquisition_now: Literal[False] = False
    authorizes_btc_market_value_access: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
    authorizes_historical_screen_access: Literal[False] = False
    authorizes_validation_access: Literal[False] = False
    authorizes_holdout_access: Literal[False] = False
    authorizes_candidate_outcome: Literal[False] = False
    authorizes_pine: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    decision: Literal["FREEZE_S2_SINGLE_CANDIDATE_BEFORE_MARKET_OUTCOMES"] = (
        "FREEZE_S2_SINGLE_CANDIDATE_BEFORE_MARKET_OUTCOMES"
    )
    next_authorization: Literal[
        "AUTHORIZE_S2_BTCUSDT_MONDAY_1H_SOURCE_ACQUISITION_PROTOCOL_ONLY"
    ] = S2_STRATEGY_PREREG_NEXT
    limitations: tuple[str, ...] = Field(min_length=8)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "measurement_result_file_sha256",
        "measurement_result_evidence_hash",
        "measurement_audit_file_sha256",
        "measurement_audit_evidence_hash",
        "measurement_dataset_file_sha256",
        "measurement_row_manifest_evidence_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S2StrategyPreregistration:
        paths = tuple(item.path for item in self.source_bindings)
        gate_ids = tuple(item.gate_id for item in self.development_gates)
        expected_gate_ids = (
            "EXACT_WEEKLY_INTERVAL_COUNT",
            "MINIMUM_POSITION_TRANSITIONS",
            "MINIMUM_LONG_EXPOSURE_FRACTION",
            "MAXIMUM_LONG_EXPOSURE_FRACTION",
            "BASE_NET_TOTAL_RETURN_POSITIVE",
            "STRESS_NET_TOTAL_RETURN_POSITIVE",
            "BASE_PROFIT_FACTOR",
            "STRESS_PROFIT_FACTOR",
            "BASE_MAXIMUM_DRAWDOWN",
            "STRESS_MAXIMUM_DRAWDOWN",
            "POSITIVE_FULL_CALENDAR_YEARS",
            "STRESS_BOOTSTRAP_95PCT_LOWER_MEAN_WEEKLY_RETURN",
            "STRESS_WEEKLY_SHARPE",
            "BASE_CALMAR_RATIO",
            "BASE_MAXIMUM_DRAWDOWN_NOT_WORSE_THAN_BUY_AND_HOLD",
        )
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S2 preregistration source bindings changed")
        if gate_ids != expected_gate_ids:
            raise ValueError("S2 development gate family changed")
        if self.scored_signal_sequence_end_inclusive - self.scored_signal_sequence_start + 1 != 272:
            raise ValueError("S2 scored signal interval changed")
        if (
            self.base_total_cost_bps_per_fill != "15"
            or self.stress_total_cost_bps_per_fill != "22.5"
        ):
            raise ValueError("S2 cost model changed")
        if self.candidate.parameter_count != 0 or self.candidate.parameter_combinations != 1:
            raise ValueError("S2 candidate search budget changed")
        if self.limitations != tuple(sorted(set(self.limitations))):
            raise ValueError("S2 preregistration limitations changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S2 strategy preregistration hash changed")
        return self


class S2StrategyPreregistrationAudit(BaseModel):
    schema_version: Literal["aurex-s2-strategy-preregistration-audit-v1"] = (
        "aurex-s2-strategy-preregistration-audit-v1"
    )
    audit_id: Literal["s2-strategy-preregistration-audit-v1"] = (
        "s2-strategy-preregistration-audit-v1"
    )
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    builder_contract_hash: str
    measurement_result_evidence_hash: str
    measurement_audit_evidence_hash: str
    measurement_dataset_file_sha256: str
    measurement_row_manifest_evidence_hash: str
    auditor_contract_hash: str
    source_binding_count: Literal[7] = 7
    measurement_dataset_bytes_hashed: Literal[130754] = 130_754
    measurement_value_rows_parsed: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    candidate_count: Literal[1] = 1
    parameter_combination_count: Literal[1] = 1
    development_gate_count: Literal[15] = 15
    reconstructed_exactly: Literal[True] = True
    decision: Literal["PASS_S2_STRATEGY_PREREGISTRATION_AUDIT"] = (
        "PASS_S2_STRATEGY_PREREGISTRATION_AUDIT"
    )
    next_authorization: Literal[
        "AUTHORIZE_S2_BTCUSDT_MONDAY_1H_SOURCE_ACQUISITION_PROTOCOL_ONLY"
    ] = S2_STRATEGY_PREREG_NEXT
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "builder_contract_hash",
        "measurement_result_evidence_hash",
        "measurement_audit_evidence_hash",
        "measurement_dataset_file_sha256",
        "measurement_row_manifest_evidence_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S2StrategyPreregistrationAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S2 strategy preregistration audit hash changed")
        return self
