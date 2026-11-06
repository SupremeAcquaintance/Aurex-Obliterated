from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_v2_acquisition_protocol import (
    V2_COMPLETE_SYMBOLS,
    V2_EXCLUDED_INCOMPLETE_SYMBOLS,
)
from aurex.backtest_engine.research_v2_source_census_contract import (
    V2_MONTHS,
    V2_REQUIRED_FAMILY_IDS,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

V2_P01_PROTOCOL_SCHEMA_VERSION = (
    "aurex-v2-positive-funding-spot-perp-carry-protocol-v1"
)
V2_P01_DIRECT_HISTORICAL_REQUIREMENTS = [
    "HISTORICAL_SETTLED_FUNDING_AND_INTERVALS",
    "HISTORICAL_SPOT_PERPETUAL_MARK_INDEX_PREMIUM_SERIES",
]
V2_P01_OVERRIDE_REQUIREMENTS = [
    "HISTORICAL_ACCOUNT_FEE_TIER",
    "HISTORICAL_COLLATERAL_LIQUIDATION_AND_ADL_RULES",
    "HISTORICAL_FUTURES_ORDER_FILTERS",
    "HISTORICAL_LEVERAGE_AND_MAINTENANCE_BRACKETS",
    "HISTORICAL_SPOT_ORDER_FILTERS",
]
V2_P01_NO_OVERRIDE_REQUIREMENTS = [
    "HISTORICAL_FUTURES_CONTRACT_LIFECYCLE"
]
V2_P01_CURRENT_METADATA_URLS = [
    "https://api.binance.com/api/v3/exchangeInfo",
    "https://fapi.binance.com/fapi/v1/exchangeInfo",
]
V2_P01_NORMALIZED_FIELDS = [
    "funding_interval_hours",
    "funding_rate",
    "funding_timestamp",
    "index_close",
    "mark_close",
    "mark_high",
    "mark_low",
    "open_timestamp",
    "perpetual_close",
    "perpetual_high",
    "perpetual_low",
    "perpetual_open",
    "perpetual_quote_volume",
    "premium_index_close",
    "spot_close",
    "spot_high",
    "spot_low",
    "spot_open",
    "spot_quote_volume",
    "symbol",
]
V2_P01_CURRENT_FILTER_FIELDS = [
    "contract_status",
    "contract_type",
    "futures_max_market_quantity",
    "futures_min_notional",
    "futures_min_quantity",
    "futures_quantity_step",
    "futures_tick_size",
    "spot_max_market_quantity",
    "spot_min_notional",
    "spot_min_quantity",
    "spot_quantity_step",
    "spot_status",
    "spot_tick_size",
]
V2_P01_REQUIRED_DIAGNOSTICS = [
    "adl_events",
    "basis_pnl",
    "cost_decomposition",
    "cost_stress",
    "daily_equity_and_drawdown",
    "entry_signal_funding_apr",
    "funding_cashflows",
    "hedge_deviation",
    "leave_one_symbol_out",
    "liquidation_events",
    "margin_utilization",
    "monthly_net_returns",
    "partial_fill_and_rollback_events",
    "quarterly_fold_results",
    "reconciliation_failures",
    "skipped_entry_reasons",
    "symbol_gross_profit_concentration",
]
V2_P01_FORBIDDEN_PARTITIONS = ["2025_VALIDATION", "2026_HOLDOUT", "FORWARD"]


class P01FullAcquisitionProtocol(BaseModel):
    complete_source_symbols: list[str] = Field(min_length=31, max_length=31)
    excluded_incomplete_symbols: list[str] = Field(min_length=4, max_length=4)
    months: list[str] = Field(min_length=24, max_length=24)
    family_ids: list[str] = Field(min_length=6, max_length=6)
    source_target_count: Literal[4464] = 4464
    source_target_manifest_hash: str
    pilot_targets_reused_after_reverification: Literal[54] = 54
    maximum_new_archive_downloads: Literal[4410] = 4410
    storage_root_relative_path: Literal[
        "v2_p01_full_development_bundle_v1"
    ] = "v2_p01_full_development_bundle_v1"
    maximum_concurrency: Literal[4] = 4
    request_timeout_seconds: Literal[60] = 60
    maximum_retries: Literal[2] = 2
    retry_backoff_seconds: list[int] = Field(min_length=2, max_length=2)
    maximum_single_archive_compressed_bytes: Literal[536870912] = 536870912
    maximum_total_compressed_bytes: Literal[17179869184] = 17179869184
    maximum_single_archive_uncompressed_bytes: Literal[
        2147483648
    ] = 2147483648
    maximum_total_uncompressed_bytes: Literal[68719476736] = 68719476736
    maximum_zip_expansion_ratio: Literal[100] = 100
    minimum_free_disk_bytes_before_download: Literal[
        68719476736
    ] = 68719476736
    minimum_free_disk_bytes_after_processing: Literal[
        21474836480
    ] = 21474836480
    checksum_refresh_before_every_archive_get: Literal[True] = True
    refreshed_checksum_must_equal_census_checksum: Literal[True] = True
    archive_hash_must_equal_refreshed_checksum: Literal[True] = True
    transactional_part_files_required: Literal[True] = True
    raw_archives_and_checksums_preserved: Literal[True] = True
    extracted_csv_members_persisted: Literal[False] = False
    current_metadata_urls: list[str] = Field(min_length=2, max_length=2)
    maximum_current_metadata_requests: Literal[2] = 2
    current_metadata_credentials_permitted: Literal[False] = False
    normalized_fields: list[str]
    current_filter_fields: list[str]
    unknown_schema_action: Literal[
        "STOP_WITHOUT_PARTIAL_AUTHORITATIVE_RESULT"
    ] = "STOP_WITHOUT_PARTIAL_AUTHORITATIVE_RESULT"
    resource_breach_action: Literal[
        "STOP_WITHOUT_PARTIAL_AUTHORITATIVE_RESULT"
    ] = "STOP_WITHOUT_PARTIAL_AUTHORITATIVE_RESULT"
    acquisition_pass_required_before_return_calculation: Literal[True] = True

    model_config = ConfigDict(extra="forbid")

    @field_validator("source_target_manifest_hash")
    @classmethod
    def normalize_manifest_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "complete_source_symbols",
        "excluded_incomplete_symbols",
        "months",
        "family_ids",
        "current_metadata_urls",
        "normalized_fields",
        "current_filter_fields",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_acquisition(self) -> P01FullAcquisitionProtocol:
        fixed_lists = {
            "complete_source_symbols": V2_COMPLETE_SYMBOLS,
            "excluded_incomplete_symbols": V2_EXCLUDED_INCOMPLETE_SYMBOLS,
            "months": V2_MONTHS,
            "family_ids": V2_REQUIRED_FAMILY_IDS,
            "current_metadata_urls": V2_P01_CURRENT_METADATA_URLS,
            "normalized_fields": V2_P01_NORMALIZED_FIELDS,
            "current_filter_fields": V2_P01_CURRENT_FILTER_FIELDS,
        }
        for field_name, expected in fixed_lists.items():
            if getattr(self, field_name) != sorted(expected):
                raise ValueError(f"P01 acquisition {field_name} changed")
        if self.retry_backoff_seconds != [2, 5]:
            raise ValueError("P01 acquisition retry backoff changed")
        return self


class P01MetadataTreatment(BaseModel):
    direct_historical_requirement_ids: list[str]
    conservative_override_requirement_ids: list[str]
    no_override_requirement_ids: list[str]
    current_spot_and_futures_filters_are_proxies_only: Literal[True] = True
    current_filters_cannot_prove_historical_executability: Literal[True] = True
    fee_tier_is_fixed_conservative_override: Literal[True] = True
    margin_and_liquidation_are_fixed_conservative_overrides: Literal[True] = True
    lifecycle_continuity_must_pass_without_override: Literal[True] = True
    missing_current_filter_action: Literal[
        "EXCLUDE_SYMBOL_BEFORE_ANY_RETURN_CALCULATION"
    ] = "EXCLUDE_SYMBOL_BEFORE_ANY_RETURN_CALCULATION"
    lifecycle_gap_action: Literal[
        "EXCLUDE_SYMBOL_BEFORE_ANY_RETURN_CALCULATION"
    ] = "EXCLUDE_SYMBOL_BEFORE_ANY_RETURN_CALCULATION"
    minimum_symbols_after_metadata_and_continuity_gates: Literal[20] = 20
    minimum_symbol_breach_action: Literal[
        "STOP_P01_WITHOUT_RETURN_CALCULATION"
    ] = "STOP_P01_WITHOUT_RETURN_CALCULATION"
    research_only_noneligibility_limitation_retained: Literal[True] = True

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "direct_historical_requirement_ids",
        "conservative_override_requirement_ids",
        "no_override_requirement_ids",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_treatment(self) -> P01MetadataTreatment:
        expected = {
            "direct_historical_requirement_ids": (
                V2_P01_DIRECT_HISTORICAL_REQUIREMENTS
            ),
            "conservative_override_requirement_ids": (
                V2_P01_OVERRIDE_REQUIREMENTS
            ),
            "no_override_requirement_ids": V2_P01_NO_OVERRIDE_REQUIREMENTS,
        }
        for field_name, fixed in expected.items():
            if getattr(self, field_name) != sorted(fixed):
                raise ValueError(f"P01 metadata treatment {field_name} changed")
        return self


class P01TransformationProtocol(BaseModel):
    timestamp_storage: Literal["UTC_INTEGER_MILLISECONDS"] = (
        "UTC_INTEGER_MILLISECONDS"
    )
    numeric_storage: Literal["DECIMAL_FROM_SOURCE_TEXT_NO_BINARY_FLOAT"] = (
        "DECIMAL_FROM_SOURCE_TEXT_NO_BINARY_FLOAT"
    )
    price_family_join: Literal[
        "EXACT_SYMBOL_AND_ONE_MINUTE_OPEN_TIMESTAMP_INNER_JOIN"
    ] = "EXACT_SYMBOL_AND_ONE_MINUTE_OPEN_TIMESTAMP_INNER_JOIN"
    required_synchronized_price_families: Literal[5] = 5
    duplicate_timestamps_allowed: Literal[False] = False
    non_finite_values_allowed: Literal[False] = False
    rows_outside_target_month_allowed: Literal[False] = False
    synthetic_or_forward_filled_rows_allowed: Literal[False] = False
    exact_one_minute_grid_required: Literal[True] = True
    funding_event_join: Literal[
        "SETTLEMENT_TIMESTAMP_WITH_FIRST_ACTIONABLE_MINUTE_STRICTLY_AFTER_EVENT"
    ] = (
        "SETTLEMENT_TIMESTAMP_WITH_FIRST_ACTIONABLE_MINUTE_"
        "STRICTLY_AFTER_EVENT"
    )
    funding_cashflow_formula: Literal[
        "NEGATIVE_SIGNED_PERP_BASE_QUANTITY_TIMES_MARK_PRICE_TIMES_FUNDING_RATE"
    ] = (
        "NEGATIVE_SIGNED_PERP_BASE_QUANTITY_TIMES_MARK_PRICE_"
        "TIMES_FUNDING_RATE"
    )
    funding_interval_source: Literal["ARCHIVED_FUNDING_INTERVAL_HOURS"] = (
        "ARCHIVED_FUNDING_INTERVAL_HOURS"
    )
    normalized_manifest_required: Literal[True] = True
    normalized_manifest_hash_algorithm: Literal["SHA256"] = "SHA256"

    model_config = ConfigDict(extra="forbid")


class P01SignalProtocol(BaseModel):
    signal_id: Literal["positive_funding_persistence_apr_v1"] = (
        "positive_funding_persistence_apr_v1"
    )
    funding_event_lookback: Literal[3] = 3
    annualization_formula: Literal[
        "MEAN_OF_EACH_RATE_TIMES_8760_DIVIDED_BY_ITS_INTERVAL_HOURS"
    ] = "MEAN_OF_EACH_RATE_TIMES_8760_DIVIDED_BY_ITS_INTERVAL_HOURS"
    every_lookback_rate_must_be_strictly_positive: Literal[True] = True
    entry_minimum_trailing_annualized_funding: Literal["0.30"] = "0.30"
    exit_maximum_trailing_annualized_funding: Literal["0.10"] = "0.10"
    entry_minimum_prior_closed_minute_mark_spot_premium: Literal["0"] = "0"
    ranking_rule: Literal[
        "HIGHEST_TRAILING_ANNUALIZED_FUNDING_THEN_SYMBOL_ASCENDING"
    ] = "HIGHEST_TRAILING_ANNUALIZED_FUNDING_THEN_SYMBOL_ASCENDING"
    decision_information: Literal[
        "ONLY_SETTLED_FUNDING_AND_CLOSED_PRICE_MINUTES_AVAILABLE_BEFORE_DECISION"
    ] = (
        "ONLY_SETTLED_FUNDING_AND_CLOSED_PRICE_MINUTES_"
        "AVAILABLE_BEFORE_DECISION"
    )
    entry_action_time: Literal[
        "NEXT_COMPLETE_ONE_MINUTE_OPEN_AFTER_SIGNAL"
    ] = "NEXT_COMPLETE_ONE_MINUTE_OPEN_AFTER_SIGNAL"
    exit_rules: list[str] = Field(min_length=5, max_length=5)
    parameter_search_allowed: Literal[False] = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("exit_rules")
    @classmethod
    def validate_exit_rules(cls, value: list[str]) -> list[str]:
        normalized = sorted(set(value))
        expected = sorted(
            [
                "TRAILING_ANNUALIZED_FUNDING_AT_OR_BELOW_0.10",
                "NONPOSITIVE_LATEST_SETTLED_FUNDING",
                "RISK_KILL_SWITCH",
                "DATA_OR_LIFECYCLE_INTEGRITY_BREACH",
                "FORCED_END_OF_DEVELOPMENT_WINDOW",
            ]
        )
        if normalized != expected:
            raise ValueError("P01 exit rules changed")
        return normalized


class P01PortfolioProtocol(BaseModel):
    initial_capital_usdt: Literal["10000"] = "10000"
    pair_notional_usdt: Literal["1000"] = "1000"
    pair_notional_compounding_allowed: Literal[False] = False
    maximum_concurrent_pairs: Literal[5] = 5
    spot_leg: Literal["LONG_SPOT"] = "LONG_SPOT"
    perpetual_leg: Literal["SHORT_USD_M_PERPETUAL"] = "SHORT_USD_M_PERPETUAL"
    target_base_quantity_rule: Literal[
        "COMMON_FILTERED_BASE_QUANTITY_FROM_1000_USDT_PAIR_NOTIONAL"
    ] = "COMMON_FILTERED_BASE_QUANTITY_FROM_1000_USDT_PAIR_NOTIONAL"
    maximum_total_spot_notional_usdt: Literal["5000"] = "5000"
    maximum_total_perpetual_notional_usdt: Literal["5000"] = "5000"
    maximum_paired_gross_exposure_percent: Literal["100"] = "100"
    minimum_unallocated_cash_reserve_percent: Literal["25"] = "25"
    rotation_before_exit_allowed: Literal[False] = False
    pyramiding_allowed: Literal[False] = False
    directional_unhedged_positions_allowed: Literal[False] = False
    maximum_absolute_base_quantity_hedge_deviation_fraction: Literal[
        "0.005"
    ] = "0.005"

    model_config = ConfigDict(extra="forbid")


class P01ExecutionProtocol(BaseModel):
    entry_price_sources: Literal[
        "NEXT_MINUTE_SPOT_AND_PERPETUAL_OPEN"
    ] = "NEXT_MINUTE_SPOT_AND_PERPETUAL_OPEN"
    exit_price_sources: Literal[
        "NEXT_MINUTE_SPOT_AND_PERPETUAL_OPEN_OR_FINAL_SYNCHRONIZED_CLOSE"
    ] = (
        "NEXT_MINUTE_SPOT_AND_PERPETUAL_OPEN_OR_"
        "FINAL_SYNCHRONIZED_CLOSE"
    )
    maximum_signal_age_minutes: Literal[2] = 2
    stale_signal_action: Literal["SKIP_ENTRY"] = "SKIP_ENTRY"
    current_spot_and_futures_filters_both_applied: Literal[True] = True
    quantity_rounding: Literal[
        "FLOOR_TO_COARSER_CURRENT_SPOT_OR_FUTURES_STEP"
    ] = "FLOOR_TO_COARSER_CURRENT_SPOT_OR_FUTURES_STEP"
    maximum_quote_volume_participation_fraction_per_leg: Literal[
        "0.01"
    ] = "0.01"
    minimum_common_fill_fraction_of_target: Literal["0.90"] = "0.90"
    insufficient_common_capacity_action: Literal["SKIP_ENTRY"] = "SKIP_ENTRY"
    paired_fill_rule: Literal[
        "COMMON_BASE_QUANTITY_CAPPED_BY_BOTH_LEG_CAPACITIES"
    ] = "COMMON_BASE_QUANTITY_CAPPED_BY_BOTH_LEG_CAPACITIES"
    one_leg_failure_action: Literal[
        "ROLL_BACK_FILLED_LEG_AT_NEXT_MINUTE_WITH_FULL_COST"
    ] = "ROLL_BACK_FILLED_LEG_AT_NEXT_MINUTE_WITH_FULL_COST"
    rollback_failure_action: Literal[
        "KILL_SWITCH_FLATTEN_ALL_AND_FAIL_STUDY"
    ] = "KILL_SWITCH_FLATTEN_ALL_AND_FAIL_STUDY"
    reconciliation_frequency: Literal[
        "EVERY_MINUTE_AND_AFTER_EVERY_FILL_FUNDING_OR_EXIT"
    ] = "EVERY_MINUTE_AND_AFTER_EVERY_FILL_FUNDING_OR_EXIT"
    unmatched_exposure_tolerance_minutes: Literal[1] = 1

    model_config = ConfigDict(extra="forbid")


class P01CostProtocol(BaseModel):
    spot_commission_fraction_per_side: Literal["0.0010"] = "0.0010"
    perpetual_commission_fraction_per_side: Literal["0.0005"] = "0.0005"
    spot_adverse_execution_fraction_per_side: Literal["0.0005"] = "0.0005"
    perpetual_adverse_execution_fraction_per_side: Literal[
        "0.0005"
    ] = "0.0005"
    adverse_execution_includes_spread_and_slippage: Literal[True] = True
    funding_rate: Literal["ARCHIVED_SIGNED_SETTLED_RATE"] = (
        "ARCHIVED_SIGNED_SETTLED_RATE"
    )
    spot_borrow_cost_fraction: Literal["0"] = "0"
    maker_rebate_fraction: Literal["0"] = "0"
    liquidation_fee_fraction: Literal["0.02"] = "0.02"
    stress_multipliers: list[Decimal] = Field(min_length=4, max_length=4)
    cost_stress_scales_funding_cashflows: Literal[False] = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("stress_multipliers")
    @classmethod
    def validate_multipliers(cls, value: list[Decimal]) -> list[Decimal]:
        expected = [
            Decimal("0"),
            Decimal("1"),
            Decimal("1.5"),
            Decimal("2"),
        ]
        if value != expected:
            raise ValueError("P01 cost stress multipliers changed")
        return value


class P01MarginProtocol(BaseModel):
    margin_mode: Literal["ISOLATED_RESEARCH_OVERRIDE"] = (
        "ISOLATED_RESEARCH_OVERRIDE"
    )
    initial_leverage: Literal["2"] = "2"
    initial_margin_fraction: Literal["0.50"] = "0.50"
    maintenance_margin_fraction: Literal["0.05"] = "0.05"
    maintenance_margin_is_conservative_nonhistorical_override: Literal[
        True
    ] = True
    collateral_asset: Literal["USDT_ONLY"] = "USDT_ONLY"
    cross_collateral_allowed: Literal[False] = False
    collateral_interest_modeled: Literal[False] = False
    liquidation_check_frequency: Literal["EVERY_ONE_MINUTE_BAR"] = (
        "EVERY_ONE_MINUTE_BAR"
    )
    short_liquidation_mark: Literal["MINUTE_MARK_HIGH"] = "MINUTE_MARK_HIGH"
    liquidation_action: Literal[
        "CHARGE_FEE_FLATTEN_PAIR_RECORD_FAILURE"
    ] = "CHARGE_FEE_FLATTEN_PAIR_RECORD_FAILURE"
    adl_action: Literal[
        "FLATTEN_PAIR_RECORD_FAILURE_AND_TRIGGER_KILL_SWITCH"
    ] = "FLATTEN_PAIR_RECORD_FAILURE_AND_TRIGGER_KILL_SWITCH"
    zero_liquidation_required: Literal[True] = True
    zero_adl_required: Literal[True] = True

    model_config = ConfigDict(extra="forbid")


class P01Fold(BaseModel):
    fold_id: str = Field(min_length=1, max_length=128)
    evaluation_start: datetime
    evaluation_end: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("evaluation_start", "evaluation_end")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_fold(self) -> P01Fold:
        if self.evaluation_end <= self.evaluation_start:
            raise ValueError("P01 fold end must follow its start")
        return self


class P01RunSpec(BaseModel):
    run_id: str = Field(min_length=1, max_length=128)
    run_kind: Literal["PRIMARY", "COST_DIAGNOSTIC", "LEAVE_ONE_SYMBOL_OUT"]
    cost_multiplier: Decimal = Field(ge=0, le=2)
    excluded_symbol: str | None = None
    selectable: bool

    model_config = ConfigDict(extra="forbid")

    @field_validator("excluded_symbol")
    @classmethod
    def normalize_symbol(cls, value: str | None) -> str | None:
        return None if value is None else value.strip().upper()

    @model_validator(mode="after")
    def validate_run(self) -> P01RunSpec:
        if self.run_kind == "PRIMARY":
            if (
                self.run_id != "primary-base-cost"
                or self.cost_multiplier != Decimal("1")
                or self.excluded_symbol is not None
                or not self.selectable
            ):
                raise ValueError("P01 primary run changed")
        elif self.run_kind == "COST_DIAGNOSTIC":
            if self.excluded_symbol is not None or self.selectable:
                raise ValueError("P01 cost diagnostic cannot be selectable")
        elif (
            self.excluded_symbol not in V2_COMPLETE_SYMBOLS
            or self.cost_multiplier != Decimal("1")
            or self.selectable
        ):
            raise ValueError("P01 leave-one-symbol-out run changed")
        return self


class P01Gates(BaseModel):
    primary_net_pl_strictly_positive: Literal[True] = True
    minimum_primary_profit_factor: Literal["1.20"] = "1.20"
    maximum_primary_drawdown_percent: Literal["10"] = "10"
    minimum_completed_paired_trades: Literal[100] = 100
    minimum_positive_quarterly_folds: Literal[6] = 6
    total_quarterly_folds: Literal[8] = 8
    double_cost_net_pl_strictly_positive: Literal[True] = True
    gross_funding_receipts_must_exceed_execution_costs: Literal[True] = True
    minimum_leave_one_symbol_out_positive_fraction: Literal["0.80"] = "0.80"
    maximum_single_symbol_gross_profit_fraction: Literal["0.25"] = "0.25"
    maximum_top_five_gross_profit_fraction: Literal["0.60"] = "0.60"
    maximum_hedge_deviation_fraction: Literal["0.005"] = "0.005"
    maximum_liquidation_events: Literal[0] = 0
    maximum_adl_events: Literal[0] = 0
    maximum_unreconciled_events: Literal[0] = 0
    maximum_rollback_failures: Literal[0] = 0
    all_gates_required: Literal[True] = True

    model_config = ConfigDict(extra="forbid")


class P01SelectionControl(BaseModel):
    theory_proposal_count: Literal[3] = 3
    selected_mechanism_count: Literal[1] = 1
    selectable_parameter_sets: Literal[1] = 1
    adaptive_parameter_selection: Literal[False] = False
    rescue_variants_allowed: Literal[False] = False
    multiplicity_treatment: Literal[
        "ONE_SELECTABLE_PRIMARY_WITH_PREDECLARED_NONSELCTABLE_DIAGNOSTICS"
    ] = "ONE_SELECTABLE_PRIMARY_WITH_PREDECLARED_NONSELCTABLE_DIAGNOSTICS"
    development_pass_creates_eligible_strategy: Literal[False] = False
    development_pass_action: Literal[
        "FREEZE_SEPARATE_2025_VALIDATION_PROTOCOL"
    ] = "FREEZE_SEPARATE_2025_VALIDATION_PROTOCOL"
    any_gate_failure_action: Literal[
        "STOP_P01_POSITIVE_FUNDING_SPOT_PERP_CARRY"
    ] = "STOP_P01_POSITIVE_FUNDING_SPOT_PERP_CARRY"

    model_config = ConfigDict(extra="forbid")


class V2P01PrimaryProtocol(BaseModel):
    schema_version: Literal[
        "aurex-v2-positive-funding-spot-perp-carry-protocol-v1"
    ] = V2_P01_PROTOCOL_SCHEMA_VERSION
    protocol_id: Literal["v2-p01-positive-funding-spot-perp-carry-v1"] = (
        "v2-p01-positive-funding-spot-perp-carry-v1"
    )
    protocol_version: Literal["1.0.0"] = "1.0.0"
    frozen_at: datetime
    status: Literal["FROZEN_PRE_FULL_PAYLOAD_AND_PRE_RETURN"] = (
        "FROZEN_PRE_FULL_PAYLOAD_AND_PRE_RETURN"
    )
    selected_proposal_id: Literal[
        "P01_POSITIVE_FUNDING_SPOT_PERP_CARRY"
    ] = "P01_POSITIVE_FUNDING_SPOT_PERP_CARRY"
    hypothesis: str = Field(min_length=150, max_length=3000)
    falsification_claim: str = Field(min_length=150, max_length=3000)
    theory_screen_evidence_hash: str
    metadata_source_contract_evidence_hash: str
    metadata_source_audit_result_evidence_hash: str
    source_census_contract_evidence_hash: str
    source_census_result_evidence_hash: str
    pilot_protocol_evidence_hash: str
    pilot_result_evidence_hash: str
    derivatives_foundation_result_evidence_hash: str
    contamination_ledger_evidence_hash: str
    builder_contract_hash: str
    venue: Literal["BINANCE"] = "BINANCE"
    market_type: Literal["SPOT_AND_USD_M_PERPETUAL"] = (
        "SPOT_AND_USD_M_PERPETUAL"
    )
    quote_and_collateral_asset: Literal["USDT"] = "USDT"
    source_timeframe: Literal["1m_AND_EXACT_FUNDING_EVENTS"] = (
        "1m_AND_EXACT_FUNDING_EVENTS"
    )
    development_start: datetime
    development_end: datetime
    forbidden_partitions: list[str]
    acquisition: P01FullAcquisitionProtocol
    metadata_treatment: P01MetadataTreatment
    transformations: P01TransformationProtocol
    signal: P01SignalProtocol
    portfolio: P01PortfolioProtocol
    execution: P01ExecutionProtocol
    costs: P01CostProtocol
    margin: P01MarginProtocol
    folds: list[P01Fold] = Field(min_length=8, max_length=8)
    run_matrix: list[P01RunSpec] = Field(min_length=35, max_length=35)
    gates: P01Gates
    selection_control: P01SelectionControl
    required_diagnostics: list[str]
    outcome_fields_inspected: list[str] = Field(default_factory=list)
    preexisting_result_artifacts: list[str] = Field(default_factory=list)
    authorizes_exact_full_archive_download: Literal[True] = True
    authorizes_two_public_metadata_snapshots: Literal[True] = True
    authorizes_market_data_normalization: Literal[True] = True
    return_calculation_permitted_before_acquisition_pass: Literal[False] = False
    authorizes_development_return_after_acquisition_pass: Literal[True] = True
    creates_candidate: Literal[False] = False
    permits_validation: Literal[False] = False
    permits_holdout_or_forward: Literal[False] = False
    permits_pine: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_sandbox_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    limitations: list[str] = Field(min_length=6)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at", "development_start", "development_end")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "theory_screen_evidence_hash",
        "metadata_source_contract_evidence_hash",
        "metadata_source_audit_result_evidence_hash",
        "source_census_contract_evidence_hash",
        "source_census_result_evidence_hash",
        "pilot_protocol_evidence_hash",
        "pilot_result_evidence_hash",
        "derivatives_foundation_result_evidence_hash",
        "contamination_ledger_evidence_hash",
        "builder_contract_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "forbidden_partitions",
        "required_diagnostics",
        "outcome_fields_inspected",
        "preexisting_result_artifacts",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_protocol(self) -> V2P01PrimaryProtocol:
        if self.development_start.isoformat() != (
            "2023-01-01T00:00:00+00:00"
        ):
            raise ValueError("P01 development start changed")
        if self.development_end.isoformat() != (
            "2025-01-01T00:00:00+00:00"
        ):
            raise ValueError("P01 development end changed")
        if self.forbidden_partitions != sorted(V2_P01_FORBIDDEN_PARTITIONS):
            raise ValueError("P01 forbidden partitions changed")
        if self.required_diagnostics != sorted(V2_P01_REQUIRED_DIAGNOSTICS):
            raise ValueError("P01 required diagnostics changed")
        if self.outcome_fields_inspected or self.preexisting_result_artifacts:
            raise ValueError("P01 protocol must predate every return outcome")
        expected_folds = [
            (
                f"fold-{index:02d}-{year}q{quarter}",
                f"{year}-{start_month:02d}-01T00:00:00+00:00",
                (
                    f"{next_year}-{next_month:02d}-01T00:00:00+00:00"
                ),
            )
            for index, (year, quarter, start_month, next_year, next_month) in enumerate(
                [
                    (2023, 1, 1, 2023, 4),
                    (2023, 2, 4, 2023, 7),
                    (2023, 3, 7, 2023, 10),
                    (2023, 4, 10, 2024, 1),
                    (2024, 1, 1, 2024, 4),
                    (2024, 2, 4, 2024, 7),
                    (2024, 3, 7, 2024, 10),
                    (2024, 4, 10, 2025, 1),
                ],
                start=1,
            )
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
            raise ValueError("P01 temporal folds changed")

        expected_runs = [
            ("primary-base-cost", "PRIMARY", Decimal("1"), None, True),
            (
                "diagnostic-zero-cost",
                "COST_DIAGNOSTIC",
                Decimal("0"),
                None,
                False,
            ),
            (
                "diagnostic-1p5-cost",
                "COST_DIAGNOSTIC",
                Decimal("1.5"),
                None,
                False,
            ),
            (
                "diagnostic-double-cost",
                "COST_DIAGNOSTIC",
                Decimal("2"),
                None,
                False,
            ),
            *[
                (
                    f"leave-one-out-{symbol.lower()}",
                    "LEAVE_ONE_SYMBOL_OUT",
                    Decimal("1"),
                    symbol,
                    False,
                )
                for symbol in V2_COMPLETE_SYMBOLS
            ],
        ]
        actual_runs = [
            (
                run.run_id,
                run.run_kind,
                run.cost_multiplier,
                run.excluded_symbol,
                run.selectable,
            )
            for run in self.run_matrix
        ]
        if actual_runs != expected_runs:
            raise ValueError("P01 run matrix changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected_hash:
            raise ValueError("P01 protocol hash does not match")
        return self


def build_v2_p01_primary_protocol(**values) -> V2P01PrimaryProtocol:
    payload = {
        "schema_version": V2_P01_PROTOCOL_SCHEMA_VERSION,
        "protocol_id": "v2-p01-positive-funding-spot-perp-carry-v1",
        "protocol_version": "1.0.0",
        "status": "FROZEN_PRE_FULL_PAYLOAD_AND_PRE_RETURN",
        "selected_proposal_id": "P01_POSITIVE_FUNDING_SPOT_PERP_CARRY",
        "venue": "BINANCE",
        "market_type": "SPOT_AND_USD_M_PERPETUAL",
        "quote_and_collateral_asset": "USDT",
        "source_timeframe": "1m_AND_EXACT_FUNDING_EVENTS",
        "authorizes_exact_full_archive_download": True,
        "authorizes_two_public_metadata_snapshots": True,
        "authorizes_market_data_normalization": True,
        "return_calculation_permitted_before_acquisition_pass": False,
        "authorizes_development_return_after_acquisition_pass": True,
        "creates_candidate": False,
        "permits_validation": False,
        "permits_holdout_or_forward": False,
        "permits_pine": False,
        "creates_paper_eligibility": False,
        "creates_sandbox_eligibility": False,
        "creates_live_eligibility": False,
        **values,
    }
    for field_name in ("frozen_at", "development_start", "development_end"):
        payload[field_name] = normalize_timestamp(payload[field_name])
    for field_name in (
        "forbidden_partitions",
        "required_diagnostics",
        "outcome_fields_inspected",
        "preexisting_result_artifacts",
        "limitations",
    ):
        payload[field_name] = sorted(set(payload[field_name]))
    return V2P01PrimaryProtocol(
        **payload,
        protocol_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v2_p01_primary_protocol(protocol: V2P01PrimaryProtocol) -> bool:
    return protocol.protocol_evidence_hash == universe_evidence_hash(
        protocol.model_dump(exclude={"protocol_evidence_hash"})
    )
