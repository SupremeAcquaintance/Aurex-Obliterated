from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

R3_FAILURE_PACKAGE_SCHEMA_VERSION = "aurex-r3-failure-analysis-package-v1"
R3_FAILURE_RESULT_SCHEMA_VERSION = "aurex-r3-failure-analysis-result-v1"
R3_FAILURE_SOURCE_FILES = (
    "scripts/run_r3_failure_analysis.py",
    "src/aurex/backtest_engine/research_failure_analysis.py",
    "src/aurex/backtest_engine/research_failure_runner.py",
)
R3_FAILURE_FOLD_IDS = (
    "fold-01-2023q3",
    "fold-02-2023q4",
    "fold-03-2024q1",
    "fold-04-2024q2",
    "fold-05-2024q3",
    "fold-06-2024q4",
)
R3_FAILURE_VARIANT_ROLES = {
    "xsmom_168d_28d_falsification_slow": "FALSIFICATION",
    "xsmom_28d_7d_falsification_fast": "FALSIFICATION",
    "xsmom_84d_14d_primary": "PRIMARY",
}
R3_FAILURE_COST_MULTIPLIERS = (
    Decimal("1"),
    Decimal("1.5"),
    Decimal("2"),
)
R3_FAILURE_DIAGNOSTIC_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
R3_FAILURE_EXIT_REASONS = ("END_OF_WINDOW", "FIXED_STOP", "REBALANCE")
R3_FAILURE_CORRECTED_MONTHS = tuple(
    f"{year:04d}-{month:02d}"
    for year, first_month, last_month in ((2023, 7, 12), (2024, 1, 12))
    for month in range(first_month, last_month + 1)
)
R3_FAILURE_FINDING_IDS = (
    "F-01-TEMPORAL-INSTABILITY",
    "F-02-HORIZON-ORDERING",
    "F-03-COST-ROBUSTNESS",
    "F-04-BREADTH",
    "F-05-DRAWDOWN",
    "F-06-EXIT-OUTCOMES",
    "F-07-DIAGNOSTIC-MARKET",
    "F-08-BROAD-ROBUSTNESS",
)


class R3FailureAnalysisPackage(BaseModel):
    schema_version: Literal["aurex-r3-failure-analysis-package-v1"] = (
        R3_FAILURE_PACKAGE_SCHEMA_VERSION
    )
    package_id: str = Field(min_length=1, max_length=128)
    package_version: str = Field(min_length=1, max_length=64)
    frozen_at: datetime
    status: Literal["FROZEN_POST_OUTCOME_PRE_ANALYSIS"] = (
        "FROZEN_POST_OUTCOME_PRE_ANALYSIS"
    )
    failure_protocol_evidence_hash: str
    result_ledger_evidence_hash: str
    monthly_addendum_evidence_hash: str
    development_dataset_bundle_evidence_hash: str
    source_file_sha256: dict[str, str] = Field(min_length=1)
    decimal_precision: Literal[50] = 50
    decimal_rounding: Literal["ROUND_HALF_EVEN"] = "ROUND_HALF_EVEN"
    quarter_source: Literal["INDEPENDENT_FOLD_REPLAYS"] = "INDEPENDENT_FOLD_REPLAYS"
    trade_quarter_attribution: Literal["FOLD_ARTIFACT_MEMBERSHIP"] = (
        "FOLD_ARTIFACT_MEMBERSHIP"
    )
    diagnostic_return_formula: Literal["LAST_CLOSE_DIVIDED_BY_FIRST_OPEN_MINUS_ONE"] = (
        "LAST_CLOSE_DIVIDED_BY_FIRST_OPEN_MINUS_ONE"
    )
    diagnostic_volatility_formula: Literal[
        "SAMPLE_STDDEV_LOG_RETURNS_TIMES_SQRT_2190"
    ] = "SAMPLE_STDDEV_LOG_RETURNS_TIMES_SQRT_2190"
    breadth_formula: Literal[
        "COUNT_STRICTLY_POSITIVE_SCORES_AT_PRIMARY_BASE_REBALANCE"
    ] = "COUNT_STRICTLY_POSITIVE_SCORES_AT_PRIMARY_BASE_REBALANCE"
    drawdown_episode_formula: Literal[
        "CONTIGUOUS_POSITIVE_DRAWDOWN_SNAPSHOTS_CLOSED_AT_ZERO_OR_WINDOW_END"
    ] = "CONTIGUOUS_POSITIVE_DRAWDOWN_SNAPSHOTS_CLOSED_AT_ZERO_OR_WINDOW_END"
    symbol_contribution_formula: Literal[
        "SUM_FOLD_TRADE_NET_AND_RAW_PL_BY_SYMBOL"
    ] = "SUM_FOLD_TRADE_NET_AND_RAW_PL_BY_SYMBOL"
    next_decision_rule: Literal[
        "PROPOSE_ONLY_IF_ALL_DESCRIPTIVE_CONTINUATION_CRITERIA_PASS_ELSE_STOP"
    ] = "PROPOSE_ONLY_IF_ALL_DESCRIPTIVE_CONTINUATION_CRITERIA_PASS_ELSE_STOP"
    continuation_criteria: list[str]
    expected_result_relative_path: str = Field(min_length=1, max_length=500)
    preexisting_analysis_artifacts: list[str] = Field(default_factory=list)
    builder_contract_hash: str
    package_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "failure_protocol_evidence_hash",
        "result_ledger_evidence_hash",
        "monthly_addendum_evidence_hash",
        "development_dataset_bundle_evidence_hash",
        "builder_contract_hash",
        "package_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("source_file_sha256")
    @classmethod
    def normalize_source_hashes(cls, value: dict[str, str]) -> dict[str, str]:
        return {
            path.strip().replace("\\", "/"): normalize_sha256(evidence_hash)
            for path, evidence_hash in sorted(value.items())
            if path.strip()
        }

    @field_validator("continuation_criteria", "preexisting_analysis_artifacts")
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_package(self) -> "R3FailureAnalysisPackage":
        if tuple(self.source_file_sha256) != R3_FAILURE_SOURCE_FILES:
            raise ValueError("R3 failure package source files are fixed")
        if self.expected_result_relative_path != "r3_failure_analysis_result_v1.json":
            raise ValueError("R3 failure package result path is fixed")
        expected_criteria = [
            "ALL_THREE_HORIZONS_POSITIVE_AT_BASE_AND_DOUBLE_COST",
            "HORIZON_POSITIVE_FOLDS_STRICTLY_IMPROVE_FAST_TO_PRIMARY_TO_SLOW",
            "PRIMARY_CONCENTRATION_GATES_PASSED",
            "PRIMARY_LEAVE_ONE_MARKET_OUT_FRACTION_AT_LEAST_0_80",
            "PRIMARY_TEMPORAL_GATE_REMAINS_FAILED_AND_UNCHANGED",
        ]
        if self.continuation_criteria != expected_criteria:
            raise ValueError("R3 failure continuation criteria are fixed")
        if self.preexisting_analysis_artifacts:
            raise ValueError("R3 failure package must predate its result")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"package_evidence_hash"})
        )
        if self.package_evidence_hash != expected_hash:
            raise ValueError("R3 failure package hash does not match its evidence")
        return self


class R3PrimaryQuarterRow(BaseModel):
    fold_id: str
    evaluation_start: datetime
    evaluation_end: datetime
    net_pl: Decimal
    profit_factor: Decimal | None
    maximum_drawdown_percent: Decimal
    completed_trades: int
    winning_trades: int
    losing_trades: int
    total_commission: Decimal
    total_slippage: Decimal
    turnover: Decimal
    average_gross_exposure_percent: Decimal
    maximum_gross_exposure_percent: Decimal
    rebalance_count: int
    average_positive_market_breadth: Decimal
    minimum_positive_market_breadth: int
    insufficient_breadth_rebalances: int

    model_config = ConfigDict(extra="forbid")


class R3CostTurnoverRow(BaseModel):
    variant_id: str
    variant_role: Literal["PRIMARY", "FALSIFICATION"]
    cost_multiplier: Decimal
    net_pl: Decimal
    profit_factor: Decimal | None
    maximum_drawdown_percent: Decimal
    completed_trades: int
    total_commission: Decimal
    total_slippage: Decimal
    turnover: Decimal

    model_config = ConfigDict(extra="forbid")


class R3DiagnosticQuarterRow(BaseModel):
    fold_id: str
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    total_return: Decimal
    annualized_log_return_volatility: Decimal

    model_config = ConfigDict(extra="forbid")


class R3DrawdownEpisode(BaseModel):
    sequence: int
    started_at: datetime
    trough_at: datetime
    recovered_at: datetime | None
    ended_at: datetime
    recovered: bool
    duration_snapshots: int
    maximum_drawdown: Decimal
    maximum_drawdown_percent: Decimal

    model_config = ConfigDict(extra="forbid")


class R3ExitReasonQuarterRow(BaseModel):
    fold_id: str
    exit_reason: Literal["REBALANCE", "FIXED_STOP", "END_OF_WINDOW"]
    trades: int
    raw_price_pl: Decimal
    net_pl: Decimal
    commission: Decimal
    slippage: Decimal

    model_config = ConfigDict(extra="forbid")


class R3HorizonComparisonRow(BaseModel):
    variant_id: str
    variant_role: Literal["PRIMARY", "FALSIFICATION"]
    lookback_bars: int
    rebalance_bars: int
    base_net_pl: Decimal
    base_profit_factor: Decimal | None
    base_maximum_drawdown_percent: Decimal
    double_cost_net_pl: Decimal
    positive_quarterly_folds: int
    selectable_for_r4: Literal[False] = False

    model_config = ConfigDict(extra="forbid")


class R3BreadthRow(BaseModel):
    rebalance_at: datetime
    positive_market_count: int
    selected_market_count: int
    accepted_entry_count: int
    insufficient_breadth: bool
    average_positive_score: Decimal | None

    model_config = ConfigDict(extra="forbid")


class R3SymbolQuarterRow(BaseModel):
    fold_id: str
    symbol: str
    trades: int
    raw_price_pl: Decimal
    net_pl: Decimal
    commission: Decimal
    slippage: Decimal
    fixed_stop_exits: int
    rebalance_exits: int
    end_of_window_exits: int

    model_config = ConfigDict(extra="forbid")


class R3DescriptiveFinding(BaseModel):
    finding_id: str = Field(min_length=1, max_length=128)
    dimension: str = Field(min_length=1, max_length=128)
    observation: str = Field(min_length=1, max_length=2000)
    interpretation_limit: str = Field(min_length=1, max_length=2000)

    model_config = ConfigDict(extra="forbid")


class R3FailureAnalysisResult(BaseModel):
    schema_version: Literal["aurex-r3-failure-analysis-result-v1"] = (
        R3_FAILURE_RESULT_SCHEMA_VERSION
    )
    generated_at: datetime
    status: Literal["COMPLETE_DESCRIPTIVE_ANALYSIS"] = "COMPLETE_DESCRIPTIVE_ANALYSIS"
    package_evidence_hash: str
    failure_protocol_evidence_hash: str
    result_ledger_evidence_hash: str
    monthly_addendum_evidence_hash: str
    original_verdict: Literal["NO_CANDIDATE"] = "NO_CANDIDATE"
    primary_quarters: list[R3PrimaryQuarterRow]
    cost_and_turnover: list[R3CostTurnoverRow]
    diagnostic_quarters: list[R3DiagnosticQuarterRow]
    drawdown_episodes: list[R3DrawdownEpisode]
    exit_reasons_by_quarter: list[R3ExitReasonQuarterRow]
    horizon_comparison: list[R3HorizonComparisonRow]
    breadth_at_rebalance: list[R3BreadthRow]
    symbol_contribution_by_quarter: list[R3SymbolQuarterRow]
    corrected_monthly_net_returns: dict[str, Decimal]
    continuation_criteria: dict[str, bool]
    findings: list[R3DescriptiveFinding]
    next_research_decision: Literal[
        "PROPOSE_BOUNDED_R3_1", "STOP_CROSS_SECTIONAL_MOMENTUM_FAMILY"
    ]
    creates_candidate: Literal[False] = False
    changes_r3_verdict: Literal[False] = False
    opens_sealed_partition: Literal[False] = False
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "package_evidence_hash",
        "failure_protocol_evidence_hash",
        "result_ledger_evidence_hash",
        "monthly_addendum_evidence_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("corrected_monthly_net_returns", "continuation_criteria")
    @classmethod
    def sort_mappings(cls, value: dict) -> dict:
        return dict(sorted(value.items()))

    @model_validator(mode="after")
    def validate_result(self) -> "R3FailureAnalysisResult":
        if len(self.primary_quarters) != 6:
            raise ValueError("R3 failure result requires six primary quarters")
        if tuple(row.fold_id for row in self.primary_quarters) != R3_FAILURE_FOLD_IDS:
            raise ValueError("R3 failure result requires the exact ordered primary folds")
        if len(self.cost_and_turnover) != 9:
            raise ValueError("R3 failure result requires nine overall cost rows")
        expected_cost_keys = {
            (variant_id, multiplier)
            for variant_id in R3_FAILURE_VARIANT_ROLES
            for multiplier in R3_FAILURE_COST_MULTIPLIERS
        }
        cost_keys = {
            (row.variant_id, row.cost_multiplier) for row in self.cost_and_turnover
        }
        if cost_keys != expected_cost_keys or any(
            row.variant_role != R3_FAILURE_VARIANT_ROLES.get(row.variant_id)
            for row in self.cost_and_turnover
        ):
            raise ValueError("R3 failure result requires the exact variant/cost grid")
        if len(self.diagnostic_quarters) != 18:
            raise ValueError("R3 failure result requires 18 diagnostic quarter rows")
        expected_diagnostic_keys = {
            (fold_id, symbol)
            for fold_id in R3_FAILURE_FOLD_IDS
            for symbol in R3_FAILURE_DIAGNOSTIC_SYMBOLS
        }
        if {
            (row.fold_id, row.symbol) for row in self.diagnostic_quarters
        } != expected_diagnostic_keys:
            raise ValueError("R3 failure result requires the exact diagnostic grid")
        if not self.drawdown_episodes:
            raise ValueError("R3 failure result requires drawdown episodes")
        if [row.sequence for row in self.drawdown_episodes] != list(
            range(1, len(self.drawdown_episodes) + 1)
        ):
            raise ValueError("R3 drawdown episode sequences must be contiguous")
        for row in self.drawdown_episodes:
            if not (
                row.started_at <= row.trough_at <= row.ended_at
                and row.duration_snapshots > 0
                and row.maximum_drawdown > 0
                and row.maximum_drawdown_percent > 0
            ):
                raise ValueError("R3 drawdown episode values are invalid")
            if row.recovered != (row.recovered_at is not None):
                raise ValueError("R3 drawdown recovery fields disagree")
            if row.recovered_at is not None and row.recovered_at != row.ended_at:
                raise ValueError("R3 recovered drawdown must end at its recovery")
        if len(self.exit_reasons_by_quarter) != 18:
            raise ValueError("R3 failure result requires 18 quarter/exit rows")
        expected_exit_keys = {
            (fold_id, reason)
            for fold_id in R3_FAILURE_FOLD_IDS
            for reason in R3_FAILURE_EXIT_REASONS
        }
        if {
            (row.fold_id, row.exit_reason) for row in self.exit_reasons_by_quarter
        } != expected_exit_keys:
            raise ValueError("R3 failure result requires the exact fold/exit grid")
        if len(self.horizon_comparison) != 3:
            raise ValueError("R3 failure result requires three horizon rows")
        horizon_ids = {row.variant_id for row in self.horizon_comparison}
        if horizon_ids != set(R3_FAILURE_VARIANT_ROLES) or any(
            row.variant_role != R3_FAILURE_VARIANT_ROLES.get(row.variant_id)
            for row in self.horizon_comparison
        ):
            raise ValueError("R3 failure result requires the exact horizon variants")
        if not self.breadth_at_rebalance:
            raise ValueError("R3 failure result requires rebalance breadth")
        breadth_keys = [row.rebalance_at for row in self.breadth_at_rebalance]
        if len(breadth_keys) != len(set(breadth_keys)):
            raise ValueError("R3 failure result contains duplicate rebalances")
        if not self.symbol_contribution_by_quarter:
            raise ValueError("R3 failure result requires symbol contribution")
        symbol_keys = [
            (row.fold_id, row.symbol) for row in self.symbol_contribution_by_quarter
        ]
        if (
            len(symbol_keys) != len(set(symbol_keys))
            or {row.fold_id for row in self.symbol_contribution_by_quarter}
            != set(R3_FAILURE_FOLD_IDS)
        ):
            raise ValueError("R3 symbol contributions require unique rows in every fold")
        if len(self.corrected_monthly_net_returns) != 18:
            raise ValueError("R3 failure result requires 18 corrected months")
        if tuple(self.corrected_monthly_net_returns) != R3_FAILURE_CORRECTED_MONTHS:
            raise ValueError("R3 failure result requires the exact corrected months")
        expected_criteria = {
            "ALL_THREE_HORIZONS_POSITIVE_AT_BASE_AND_DOUBLE_COST",
            "HORIZON_POSITIVE_FOLDS_STRICTLY_IMPROVE_FAST_TO_PRIMARY_TO_SLOW",
            "PRIMARY_CONCENTRATION_GATES_PASSED",
            "PRIMARY_LEAVE_ONE_MARKET_OUT_FRACTION_AT_LEAST_0_80",
            "PRIMARY_TEMPORAL_GATE_REMAINS_FAILED_AND_UNCHANGED",
        }
        if set(self.continuation_criteria) != expected_criteria:
            raise ValueError("R3 failure result requires all continuation criteria")
        if len(self.findings) != 8:
            raise ValueError("R3 failure result requires eight descriptive findings")
        expected_decision = (
            "PROPOSE_BOUNDED_R3_1"
            if self.continuation_criteria
            and all(self.continuation_criteria.values())
            else "STOP_CROSS_SECTIONAL_MOMENTUM_FAMILY"
        )
        if self.next_research_decision != expected_decision:
            raise ValueError("R3 next research decision does not match its fixed rule")
        finding_ids = tuple(finding.finding_id for finding in self.findings)
        if finding_ids != R3_FAILURE_FINDING_IDS:
            raise ValueError("R3 descriptive findings must match the frozen dimensions")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected_hash:
            raise ValueError("R3 failure result hash does not match its evidence")
        return self


def build_r3_failure_analysis_package(**values) -> R3FailureAnalysisPackage:
    payload = {
        "schema_version": R3_FAILURE_PACKAGE_SCHEMA_VERSION,
        **values,
    }
    payload["frozen_at"] = normalize_timestamp(payload["frozen_at"])
    payload["source_file_sha256"] = dict(sorted(payload["source_file_sha256"].items()))
    payload["continuation_criteria"] = sorted(set(payload["continuation_criteria"]))
    payload["preexisting_analysis_artifacts"] = sorted(
        set(payload["preexisting_analysis_artifacts"])
    )
    return R3FailureAnalysisPackage(
        **payload,
        package_evidence_hash=universe_evidence_hash(payload),
    )


def build_r3_failure_analysis_result(**values) -> R3FailureAnalysisResult:
    payload = {
        "schema_version": R3_FAILURE_RESULT_SCHEMA_VERSION,
        **values,
    }
    payload["generated_at"] = normalize_timestamp(payload["generated_at"])
    payload["primary_quarters"] = sorted(
        payload["primary_quarters"], key=lambda row: row.fold_id
    )
    payload["cost_and_turnover"] = sorted(
        payload["cost_and_turnover"],
        key=lambda row: (row.variant_id, row.cost_multiplier),
    )
    payload["diagnostic_quarters"] = sorted(
        payload["diagnostic_quarters"], key=lambda row: (row.fold_id, row.symbol)
    )
    payload["drawdown_episodes"] = sorted(
        payload["drawdown_episodes"], key=lambda row: row.sequence
    )
    payload["exit_reasons_by_quarter"] = sorted(
        payload["exit_reasons_by_quarter"],
        key=lambda row: (row.fold_id, row.exit_reason),
    )
    payload["horizon_comparison"] = sorted(
        payload["horizon_comparison"], key=lambda row: row.lookback_bars
    )
    payload["breadth_at_rebalance"] = sorted(
        payload["breadth_at_rebalance"], key=lambda row: row.rebalance_at
    )
    payload["symbol_contribution_by_quarter"] = sorted(
        payload["symbol_contribution_by_quarter"],
        key=lambda row: (row.fold_id, row.symbol),
    )
    payload["corrected_monthly_net_returns"] = dict(
        sorted(payload["corrected_monthly_net_returns"].items())
    )
    payload["continuation_criteria"] = dict(
        sorted(payload["continuation_criteria"].items())
    )
    payload["findings"] = sorted(payload["findings"], key=lambda row: row.finding_id)
    payload["next_research_decision"] = (
        "PROPOSE_BOUNDED_R3_1"
        if payload["continuation_criteria"]
        and all(payload["continuation_criteria"].values())
        else "STOP_CROSS_SECTIONAL_MOMENTUM_FAMILY"
    )
    return R3FailureAnalysisResult(
        **payload,
        result_evidence_hash=universe_evidence_hash(payload),
    )


def audit_r3_failure_analysis_package(package: R3FailureAnalysisPackage) -> bool:
    return package.package_evidence_hash == universe_evidence_hash(
        package.model_dump(exclude={"package_evidence_hash"})
    )


def audit_r3_failure_analysis_result(result: R3FailureAnalysisResult) -> bool:
    return result.result_evidence_hash == universe_evidence_hash(
        result.model_dump(exclude={"result_evidence_hash"})
    )
