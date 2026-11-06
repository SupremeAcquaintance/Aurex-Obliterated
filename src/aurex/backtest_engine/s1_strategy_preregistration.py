from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S1_STRATEGY_PREREG_NEXT = (
    "AUTHORIZE_S1_BTCUSDT_DAILY_1H_SOURCE_ACQUISITION_PROTOCOL_ONLY"
)


class S1StrategyCandidate(BaseModel):
    candidate_id: Literal[
        "S1-C1-CONSISTENT-EASING-PRIMARY",
        "S1-D1-ONE-VINTAGE-EASING",
        "S1-D2-FOUR-VINTAGE-EASING",
        "S1-D3-LOOSE-AND-FOUR-VINTAGE-EASING",
    ]
    role: Literal["PRIMARY_ELIGIBILITY", "DIAGNOSTIC_ONLY"]
    long_rule: Literal[
        "NFCI_CHANGE_1V_LT_0_AND_NFCI_CHANGE_4V_LT_0",
        "NFCI_CHANGE_1V_LT_0",
        "NFCI_CHANGE_4V_LT_0",
        "NFCI_LEVEL_LT_0_AND_NFCI_CHANGE_4V_LT_0",
    ]
    true_position: Literal["LONG_1X"] = "LONG_1X"
    false_position: Literal["CASH"] = "CASH"
    equality_position: Literal["CASH"] = "CASH"
    shorting_permitted: Literal[False] = False
    may_be_promoted: bool

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_candidate(self) -> S1StrategyCandidate:
        if self.role == "PRIMARY_ELIGIBILITY" and not self.may_be_promoted:
            raise ValueError("S1 primary candidate must be eligible for promotion")
        if self.role == "DIAGNOSTIC_ONLY" and self.may_be_promoted:
            raise ValueError("S1 diagnostics cannot be promoted")
        return self


class S1DevelopmentGate(BaseModel):
    gate_id: str = Field(min_length=1)
    operator: Literal["EQ", "GE", "GT", "LE", "LT"]
    threshold: str = Field(min_length=1)
    scope: Literal["PRIMARY_ONLY"] = "PRIMARY_ONLY"

    model_config = ConfigDict(extra="forbid", frozen=True)


class S1StrategyPreregistration(BaseModel):
    schema_version: Literal["aurex-s1-strategy-preregistration-v1"] = (
        "aurex-s1-strategy-preregistration-v1"
    )
    protocol_id: Literal["s1-strategy-preregistration-v1"] = (
        "s1-strategy-preregistration-v1"
    )
    frozen_at: datetime
    builder_contract_hash: str
    feature_result_file_sha256: str
    feature_result_evidence_hash: str
    feature_audit_file_sha256: str
    feature_audit_evidence_hash: str
    feature_dataset_file_sha256: str
    feature_row_manifest_evidence_hash: str
    feature_decision: Literal["PASS_S1_NFCI_DEVELOPMENT_FEATURE_CONSTRUCTION"]
    feature_next_authorization: Literal[
        "AUTHORIZE_S1_NFCI_DEVELOPMENT_STRATEGY_PREREGISTRATION_PROTOCOL_ONLY"
    ]
    feature_dataset_bytes_hashed_during_freeze: Literal[90632] = 90_632
    feature_value_rows_parsed_during_freeze: Literal[0] = 0
    mechanism_id: Literal["S1-NFCI-EASING-BTC-SPOT-RISK-APPETITE"] = (
        "S1-NFCI-EASING-BTC-SPOT-RISK-APPETITE"
    )
    venue: Literal["BINANCE"] = "BINANCE"
    market_type: Literal["SPOT"] = "SPOT"
    symbol: Literal["BTCUSDT"] = "BTCUSDT"
    direction: Literal["LONG_OR_CASH"] = "LONG_OR_CASH"
    effective_leverage: Literal["1"] = "1"
    initial_equity_usd: Literal["100"] = "100"
    source_archive_granularity: Literal["DAILY"] = "DAILY"
    source_kline_interval: Literal["1h"] = "1h"
    source_base_url: Literal[
        "https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1h"
    ] = "https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1h"
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
    source_checksum_required: Literal[True] = True
    required_price_date_count: Literal[277] = 277
    first_required_price_date: Literal["2017-09-15"] = "2017-09-15"
    last_required_price_date: Literal["2022-12-30"] = "2022-12-30"
    required_price_weekday: Literal["FRIDAY"] = "FRIDAY"
    activation_rule: Literal[
        "SOURCE_VINTAGE_PLUS_1_CALENDAR_DAY_AT_00_00_UTC"
    ] = "SOURCE_VINTAGE_PLUS_1_CALENDAR_DAY_AT_00_00_UTC"
    execution_price_rule: Literal["EXACT_1H_KLINE_OPEN_AT_ACTIVATION_TIMESTAMP"] = (
        "EXACT_1H_KLINE_OPEN_AT_ACTIVATION_TIMESTAMP"
    )
    missing_execution_price_policy: Literal["STOP_NO_SUBSTITUTION"] = (
        "STOP_NO_SUBSTITUTION"
    )
    scored_signal_sequence_start: Literal[5] = 5
    scored_signal_sequence_end_inclusive: Literal[280] = 280
    terminal_price_sequence: Literal[281] = 281
    expected_weekly_interval_count: Literal[276] = 276
    position_rule: Literal["REBALANCE_ONLY_WHEN_BINARY_POSITION_CHANGES"] = (
        "REBALANCE_ONLY_WHEN_BINARY_POSITION_CHANGES"
    )
    base_commission_bps_per_fill: Literal["10"] = "10"
    base_slippage_and_spread_bps_per_fill: Literal["5"] = "5"
    base_total_cost_bps_per_fill: Literal["15"] = "15"
    stress_cost_multiplier: Literal["1.5"] = "1.5"
    stress_total_cost_bps_per_fill: Literal["22.5"] = "22.5"
    cost_application: Literal[
        "APPLY_PER_POSITION_CHANGING_FILL_TO_COMPOUNDED_EQUITY"
    ] = "APPLY_PER_POSITION_CHANGING_FILL_TO_COMPOUNDED_EQUITY"
    candidates: tuple[S1StrategyCandidate, ...] = Field(min_length=4, max_length=4)
    candidate_count: Literal[4] = 4
    primary_candidate_id: Literal["S1-C1-CONSISTENT-EASING-PRIMARY"] = (
        "S1-C1-CONSISTENT-EASING-PRIMARY"
    )
    diagnostic_rescue_permitted: Literal[False] = False
    primary_failure_policy: Literal["STOP_S1_NO_DIAGNOSTIC_PROMOTION"] = (
        "STOP_S1_NO_DIAGNOSTIC_PROMOTION"
    )
    full_years_for_year_gates: tuple[int, ...] = (2018, 2019, 2020, 2021, 2022)
    bootstrap_method: Literal["STATIONARY_BLOCK_BOOTSTRAP_WEEKLY_RETURNS"] = (
        "STATIONARY_BLOCK_BOOTSTRAP_WEEKLY_RETURNS"
    )
    bootstrap_resamples: Literal[10000] = 10_000
    bootstrap_mean_block_weeks: Literal[8] = 8
    bootstrap_seed: Literal[1729] = 1729
    bootstrap_lower_confidence: Literal["0.95"] = "0.95"
    development_gates: tuple[S1DevelopmentGate, ...] = Field(
        min_length=12,
        max_length=12,
    )
    validation_start: Literal["2023-01-01"] = "2023-01-01"
    validation_end_exclusive: Literal["2025-01-01"] = "2025-01-01"
    validation_remains_sealed: Literal[True] = True
    holdout_remains_sealed: Literal[True] = True
    authorizes_protocol_only: Literal[True] = True
    authorizes_btc_source_acquisition_now: Literal[False] = False
    authorizes_btc_market_value_access: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
    authorizes_validation_access: Literal[False] = False
    authorizes_holdout_access: Literal[False] = False
    authorizes_candidate_outcome: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    next_authorization: Literal[
        "AUTHORIZE_S1_BTCUSDT_DAILY_1H_SOURCE_ACQUISITION_PROTOCOL_ONLY"
    ] = S1_STRATEGY_PREREG_NEXT
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "feature_result_file_sha256",
        "feature_result_evidence_hash",
        "feature_audit_file_sha256",
        "feature_audit_evidence_hash",
        "feature_dataset_file_sha256",
        "feature_row_manifest_evidence_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S1StrategyPreregistration:
        expected_candidates = (
            (
                "S1-C1-CONSISTENT-EASING-PRIMARY",
                "PRIMARY_ELIGIBILITY",
                "NFCI_CHANGE_1V_LT_0_AND_NFCI_CHANGE_4V_LT_0",
                True,
            ),
            (
                "S1-D1-ONE-VINTAGE-EASING",
                "DIAGNOSTIC_ONLY",
                "NFCI_CHANGE_1V_LT_0",
                False,
            ),
            (
                "S1-D2-FOUR-VINTAGE-EASING",
                "DIAGNOSTIC_ONLY",
                "NFCI_CHANGE_4V_LT_0",
                False,
            ),
            (
                "S1-D3-LOOSE-AND-FOUR-VINTAGE-EASING",
                "DIAGNOSTIC_ONLY",
                "NFCI_LEVEL_LT_0_AND_NFCI_CHANGE_4V_LT_0",
                False,
            ),
        )
        actual_candidates = tuple(
            (item.candidate_id, item.role, item.long_rule, item.may_be_promoted)
            for item in self.candidates
        )
        if actual_candidates != expected_candidates:
            raise ValueError("S1 strategy candidate family changed")
        gate_ids = tuple(item.gate_id for item in self.development_gates)
        if len(gate_ids) != len(set(gate_ids)):
            raise ValueError("S1 development gate IDs must be unique")
        if self.base_total_cost_bps_per_fill != "15":
            raise ValueError("S1 base cost changed")
        if self.stress_total_cost_bps_per_fill != "22.5":
            raise ValueError("S1 stress cost changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S1 strategy preregistration hash changed")
        return self


class S1StrategyPreregistrationAudit(BaseModel):
    schema_version: Literal["aurex-s1-strategy-preregistration-audit-v1"] = (
        "aurex-s1-strategy-preregistration-audit-v1"
    )
    audit_id: Literal["s1-strategy-preregistration-audit-v1"] = (
        "s1-strategy-preregistration-audit-v1"
    )
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    builder_contract_hash: str
    feature_result_evidence_hash: str
    feature_audit_evidence_hash: str
    feature_dataset_file_sha256: str
    feature_row_manifest_evidence_hash: str
    auditor_source_sha256: str
    feature_dataset_bytes_hashed: Literal[90632] = 90_632
    feature_value_rows_parsed: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    candidate_count: Literal[4] = 4
    promotable_candidate_count: Literal[1] = 1
    development_gate_count: Literal[12] = 12
    reconstructed_exactly: Literal[True] = True
    decision: Literal["PASS_S1_STRATEGY_PREREGISTRATION_RECONSTRUCTED"] = (
        "PASS_S1_STRATEGY_PREREGISTRATION_RECONSTRUCTED"
    )
    next_authorization: Literal[
        "AUTHORIZE_S1_BTCUSDT_DAILY_1H_SOURCE_ACQUISITION_PROTOCOL_ONLY"
    ] = S1_STRATEGY_PREREG_NEXT
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "builder_contract_hash",
        "feature_result_evidence_hash",
        "feature_audit_evidence_hash",
        "feature_dataset_file_sha256",
        "feature_row_manifest_evidence_hash",
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S1StrategyPreregistrationAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1 strategy preregistration audit hash changed")
        return self
