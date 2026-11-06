from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

R4_FAILURE_PACKAGE_SCHEMA_VERSION = "aurex-r4-failure-analysis-package-v1"
R4_FAILURE_RESULT_SCHEMA_VERSION = "aurex-r4-failure-analysis-result-v1"
R4_FAILURE_SOURCE_FILES = (
    "scripts/freeze_r4_failure_analysis_package.py",
    "scripts/run_r4_failure_analysis.py",
    "src/aurex/backtest_engine/binance_vision.py",
    "src/aurex/backtest_engine/development_bundle.py",
    "src/aurex/backtest_engine/research_engine.py",
    "src/aurex/backtest_engine/research_r4_engine.py",
    "src/aurex/backtest_engine/research_r4_failure_analysis.py",
    "src/aurex/backtest_engine/research_r4_failure_protocol.py",
    "src/aurex/backtest_engine/research_r4_failure_runner.py",
    "src/aurex/backtest_engine/research_r4_result.py",
    "src/aurex/backtest_engine/research_r4_run_package.py",
    "src/aurex/backtest_engine/universe.py",
    "src/aurex/backtest_engine/validation_bundle.py",
)
R4_FAILURE_FOLD_IDS = (
    "validation-fold-01-2025q1",
    "validation-fold-02-2025q2",
    "validation-fold-03-2025q3",
    "validation-fold-04-2025q4",
)
R4_FAILURE_EXIT_REASONS = (
    "END_OF_WINDOW",
    "FIXED_STOP",
    "MARKET_TERMINATION_WRITE_OFF",
    "REBALANCE",
)
R4_FAILURE_HOLDING_BUCKETS = (
    "01_UP_TO_7_DAYS",
    "02_OVER_7_TO_14_DAYS",
    "03_OVER_14_DAYS",
)
R4_FAILURE_FINDING_IDS = (
    "F-01-RAW-SIGNAL-EDGE",
    "F-02-MODELED-COSTS",
    "F-03-TEMPORAL-STABILITY",
    "F-04-LOMO-ROBUSTNESS",
    "F-05-CONCENTRATION",
    "F-06-AVAILABILITY",
    "F-07-DRAWDOWN-EXPOSURE",
)


class R4FailureAnalysisPackage(BaseModel):
    schema_version: Literal["aurex-r4-failure-analysis-package-v1"] = (
        R4_FAILURE_PACKAGE_SCHEMA_VERSION
    )
    package_id: Literal["r4-path-quality-failure-analysis-package-v1"] = (
        "r4-path-quality-failure-analysis-package-v1"
    )
    package_version: Literal["1.0.0"] = "1.0.0"
    frozen_at: datetime
    status: Literal["FROZEN_POST_OUTCOME_PRE_ANALYSIS"] = (
        "FROZEN_POST_OUTCOME_PRE_ANALYSIS"
    )
    failure_protocol_evidence_hash: str
    validation_dataset_bundle_evidence_hash: str
    run_package_evidence_hash: str
    result_ledger_evidence_hash: str
    replay_result_evidence_hashes: dict[str, str] = Field(min_length=42, max_length=42)
    source_file_sha256: dict[str, str] = Field(min_length=1)
    decimal_precision: Literal[50] = 50
    decimal_rounding: Literal["ROUND_HALF_EVEN"] = "ROUND_HALF_EVEN"
    cost_reconciliation_formula: Literal[
        "SUM_RAW_PRICE_PL_MINUS_COMMISSION_MINUS_SLIPPAGE_EQUALS_SUM_NET_PL"
    ] = "SUM_RAW_PRICE_PL_MINUS_COMMISSION_MINUS_SLIPPAGE_EQUALS_SUM_NET_PL"
    quarter_source: Literal["INDEPENDENT_QUARTERLY_FOLD_REPLAYS"] = (
        "INDEPENDENT_QUARTERLY_FOLD_REPLAYS"
    )
    month_source: Literal["FROZEN_RESULT_LEDGER_MONTHLY_NET_RETURNS"] = (
        "FROZEN_RESULT_LEDGER_MONTHLY_NET_RETURNS"
    )
    cohort_formula: Literal["GROUP_BASE_TRADES_BY_ENTRY_TIMESTAMP"] = (
        "GROUP_BASE_TRADES_BY_ENTRY_TIMESTAMP"
    )
    holding_duration_formula: Literal["EXIT_AT_MINUS_ENTRY_AT"] = (
        "EXIT_AT_MINUS_ENTRY_AT"
    )
    symbol_contribution_formula: Literal[
        "GROUP_BASE_TRADES_BY_SYMBOL_AND_JOIN_OMITTED_SYMBOL_RESULT"
    ] = "GROUP_BASE_TRADES_BY_SYMBOL_AND_JOIN_OMITTED_SYMBOL_RESULT"
    failure_classification_rule: Literal[
        "RAW_NET_NONPOSITIVE_ELSE_NET_NONPOSITIVE_ELSE_TEMPORAL_OR_LOMO_ELSE_OTHER"
    ] = "RAW_NET_NONPOSITIVE_ELSE_NET_NONPOSITIVE_ELSE_TEMPORAL_OR_LOMO_ELSE_OTHER"
    next_decision_rule: Literal[
        "IF_ALL_INPUT_AND_RECONCILIATION_CHECKS_PASS_RETURN_TO_UNRELATED_DISCOVERY_ELSE_STOP_BRANCH"
    ] = (
        "IF_ALL_INPUT_AND_RECONCILIATION_CHECKS_PASS_"
        "RETURN_TO_UNRELATED_DISCOVERY_ELSE_STOP_BRANCH"
    )
    expected_result_relative_path: Literal[
        "r4_failure_analysis_result_v1.json"
    ] = "r4_failure_analysis_result_v1.json"
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
        "validation_dataset_bundle_evidence_hash",
        "run_package_evidence_hash",
        "result_ledger_evidence_hash",
        "builder_contract_hash",
        "package_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("replay_result_evidence_hashes", "source_file_sha256")
    @classmethod
    def normalize_hash_mappings(cls, value: dict[str, str]) -> dict[str, str]:
        return {
            key.strip().replace("\\", "/"): normalize_sha256(evidence_hash)
            for key, evidence_hash in sorted(value.items())
            if key.strip()
        }

    @field_validator("preexisting_analysis_artifacts")
    @classmethod
    def normalize_artifacts(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_package(self) -> R4FailureAnalysisPackage:
        if len(self.replay_result_evidence_hashes) != 42:
            raise ValueError("R4 failure package requires all 42 replay results")
        if tuple(self.source_file_sha256) != R4_FAILURE_SOURCE_FILES:
            raise ValueError("R4 failure package source files are fixed")
        if self.preexisting_analysis_artifacts:
            raise ValueError("R4 failure package must predate its result")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"package_evidence_hash"})
        )
        if self.package_evidence_hash != expected_hash:
            raise ValueError("R4 failure package hash does not match its evidence")
        return self


class R4CostAttribution(BaseModel):
    raw_price_pl: Decimal
    commission: Decimal = Field(ge=0)
    slippage: Decimal = Field(ge=0)
    modeled_costs: Decimal = Field(ge=0)
    net_pl: Decimal
    reconciliation_delta: Decimal
    reconciles: bool
    raw_profit_factor: Decimal | None
    net_profit_factor: Decimal | None
    raw_expectancy: Decimal
    net_expectancy: Decimal
    modeled_cost_per_trade: Decimal

    model_config = ConfigDict(extra="forbid")


class R4QuarterSummary(BaseModel):
    fold_id: str
    net_pl: Decimal
    profit_factor: Decimal | None
    raw_price_pl: Decimal
    completed_trades: int = Field(ge=0)
    maximum_drawdown_percent: Decimal = Field(ge=0)
    average_gross_exposure_percent: Decimal = Field(ge=0)
    minimum_active_symbol_count_at_rebalance: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid")


class R4ExitReasonSummary(BaseModel):
    exit_reason: Literal[
        "REBALANCE",
        "FIXED_STOP",
        "END_OF_WINDOW",
        "MARKET_TERMINATION_WRITE_OFF",
    ]
    trades: int = Field(ge=0)
    raw_price_pl: Decimal
    net_pl: Decimal
    commission: Decimal = Field(ge=0)
    slippage: Decimal = Field(ge=0)

    model_config = ConfigDict(extra="forbid")


class R4HoldingDurationSummary(BaseModel):
    bucket_id: Literal[
        "01_UP_TO_7_DAYS",
        "02_OVER_7_TO_14_DAYS",
        "03_OVER_14_DAYS",
    ]
    trades: int = Field(ge=0)
    average_hours: Decimal = Field(ge=0)
    raw_price_pl: Decimal
    net_pl: Decimal

    model_config = ConfigDict(extra="forbid")


class R4RebalanceCohortSummary(BaseModel):
    entry_at: datetime
    trades: int = Field(ge=1)
    raw_price_pl: Decimal
    net_pl: Decimal
    commission: Decimal = Field(ge=0)
    slippage: Decimal = Field(ge=0)

    model_config = ConfigDict(extra="forbid")

    @field_validator("entry_at")
    @classmethod
    def normalize_entry_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)


class R4SymbolContribution(BaseModel):
    symbol: str
    trades: int = Field(ge=0)
    raw_price_pl: Decimal
    net_pl: Decimal
    commission: Decimal = Field(ge=0)
    slippage: Decimal = Field(ge=0)
    leave_one_market_out_net_pl: Decimal

    model_config = ConfigDict(extra="forbid")


class R4DrawdownEpisode(BaseModel):
    sequence: int = Field(gt=0)
    started_at: datetime
    trough_at: datetime
    recovered_at: datetime | None
    ended_at: datetime
    recovered: bool
    duration_snapshots: int = Field(gt=0)
    maximum_drawdown: Decimal = Field(gt=0)
    maximum_drawdown_percent: Decimal = Field(gt=0)

    model_config = ConfigDict(extra="forbid")

    @field_validator("started_at", "trough_at", "recovered_at", "ended_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return normalize_timestamp(value) if value is not None else None


class R4AvailabilitySummary(BaseModel):
    configured_terminal_markets: int = Field(ge=0)
    observed_availability_events: int = Field(ge=0)
    held_position_writeoffs: int = Field(ge=0)
    writeoff_net_pl: Decimal
    minimum_active_symbol_count_at_rebalance: int = Field(ge=0)
    average_active_symbol_count_at_rebalance: Decimal = Field(ge=0)
    availability_caused_base_loss: bool

    model_config = ConfigDict(extra="forbid")


class R4DescriptiveFinding(BaseModel):
    finding_id: str = Field(min_length=1, max_length=128)
    dimension: str = Field(min_length=1, max_length=128)
    observation: str = Field(min_length=1, max_length=2000)
    interpretation_limit: str = Field(min_length=1, max_length=2000)

    model_config = ConfigDict(extra="forbid")


class R4FailureAnalysisResult(BaseModel):
    schema_version: Literal["aurex-r4-failure-analysis-result-v1"] = (
        R4_FAILURE_RESULT_SCHEMA_VERSION
    )
    generated_at: datetime
    status: Literal["COMPLETE_DESCRIPTIVE_ANALYSIS"] = "COMPLETE_DESCRIPTIVE_ANALYSIS"
    package_evidence_hash: str
    failure_protocol_evidence_hash: str
    run_package_evidence_hash: str
    result_ledger_evidence_hash: str
    original_verdict: Literal["RETIRE_R4_CANDIDATE"] = "RETIRE_R4_CANDIDATE"
    cost_attribution: R4CostAttribution
    quarterly_summary: list[R4QuarterSummary]
    monthly_net_returns: dict[str, Decimal]
    exit_reason_summary: list[R4ExitReasonSummary]
    holding_duration_summary: list[R4HoldingDurationSummary]
    rebalance_cohorts: list[R4RebalanceCohortSummary]
    symbol_contribution: list[R4SymbolContribution]
    drawdown_episodes: list[R4DrawdownEpisode]
    availability_summary: R4AvailabilitySummary
    positive_months: int = Field(ge=0, le=12)
    flat_months: int = Field(ge=0, le=12)
    negative_months: int = Field(ge=0, le=12)
    failure_classification: Literal[
        "SIGNAL_NEGATIVE_BEFORE_MODELED_COSTS",
        "MODELED_COSTS_OVERWHELM_POSITIVE_RAW_EDGE",
        "TEMPORAL_OR_CROSS_MARKET_INSTABILITY",
        "OTHER_FROZEN_GATE_FAILURE",
    ]
    integrity_checks: dict[str, bool]
    findings: list[R4DescriptiveFinding]
    next_research_decision: Literal[
        "STOP_ALL_STRATEGY_RESEARCH_BRANCH",
        "STOP_PATH_QUALITY_FAMILY_RETURN_TO_UNRELATED_MECHANISM_DISCOVERY",
    ]
    creates_candidate: Literal[False] = False
    changes_r4_verdict: Literal[False] = False
    opens_2026_or_forward_partition: Literal[False] = False
    permits_pine_parity_review: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "package_evidence_hash",
        "failure_protocol_evidence_hash",
        "run_package_evidence_hash",
        "result_ledger_evidence_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("monthly_net_returns", "integrity_checks")
    @classmethod
    def sort_mappings(cls, value: dict) -> dict:
        return dict(sorted(value.items()))

    @model_validator(mode="after")
    def validate_result(self) -> R4FailureAnalysisResult:
        if tuple(row.fold_id for row in self.quarterly_summary) != R4_FAILURE_FOLD_IDS:
            raise ValueError("R4 failure result requires the exact ordered quarters")
        if tuple(row.exit_reason for row in self.exit_reason_summary) != (
            "END_OF_WINDOW",
            "FIXED_STOP",
            "MARKET_TERMINATION_WRITE_OFF",
            "REBALANCE",
        ):
            raise ValueError("R4 failure result requires every ordered exit reason")
        if tuple(row.bucket_id for row in self.holding_duration_summary) != (
            R4_FAILURE_HOLDING_BUCKETS
        ):
            raise ValueError("R4 failure result requires every holding bucket")
        if len(self.monthly_net_returns) != 12 or set(
            self.monthly_net_returns
        ) != {f"2025-{month:02d}" for month in range(1, 13)}:
            raise ValueError("R4 failure result requires all 12 validation months")
        if (
            self.positive_months + self.flat_months + self.negative_months
        ) != 12:
            raise ValueError("R4 monthly outcome counts must sum to 12")
        if len(self.symbol_contribution) != 35:
            raise ValueError("R4 failure result requires all 35 baseline symbols")
        symbols = [row.symbol for row in self.symbol_contribution]
        if symbols != sorted(symbols) or len(symbols) != len(set(symbols)):
            raise ValueError("R4 symbol contributions must be uniquely sorted")
        cohort_timestamps = [row.entry_at for row in self.rebalance_cohorts]
        if cohort_timestamps != sorted(cohort_timestamps) or len(
            cohort_timestamps
        ) != len(set(cohort_timestamps)):
            raise ValueError("R4 rebalance cohorts must be uniquely sorted")
        if [row.sequence for row in self.drawdown_episodes] != list(
            range(1, len(self.drawdown_episodes) + 1)
        ):
            raise ValueError("R4 drawdown episode sequences must be contiguous")
        for row in self.drawdown_episodes:
            if not row.started_at <= row.trough_at <= row.ended_at:
                raise ValueError("R4 drawdown episode timestamps are invalid")
            if row.recovered != (row.recovered_at is not None):
                raise ValueError("R4 drawdown recovery fields disagree")
            if row.recovered_at is not None and row.recovered_at != row.ended_at:
                raise ValueError("R4 recovered drawdown must end at recovery")
        if [item.finding_id for item in self.findings] != list(
            R4_FAILURE_FINDING_IDS
        ):
            raise ValueError("R4 failure result requires every ordered finding")
        all_integrity_passed = all(self.integrity_checks.values())
        expected_decision = (
            "STOP_PATH_QUALITY_FAMILY_RETURN_TO_UNRELATED_MECHANISM_DISCOVERY"
            if all_integrity_passed
            else "STOP_ALL_STRATEGY_RESEARCH_BRANCH"
        )
        if self.next_research_decision != expected_decision:
            raise ValueError("R4 next decision does not match integrity checks")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected_hash:
            raise ValueError("R4 failure result hash does not match its evidence")
        return self


def build_r4_failure_analysis_package(**values) -> R4FailureAnalysisPackage:
    payload = {
        "schema_version": R4_FAILURE_PACKAGE_SCHEMA_VERSION,
        "package_id": "r4-path-quality-failure-analysis-package-v1",
        "package_version": "1.0.0",
        "status": "FROZEN_POST_OUTCOME_PRE_ANALYSIS",
        "decimal_precision": 50,
        "decimal_rounding": "ROUND_HALF_EVEN",
        "cost_reconciliation_formula": (
            "SUM_RAW_PRICE_PL_MINUS_COMMISSION_MINUS_SLIPPAGE_EQUALS_SUM_NET_PL"
        ),
        "quarter_source": "INDEPENDENT_QUARTERLY_FOLD_REPLAYS",
        "month_source": "FROZEN_RESULT_LEDGER_MONTHLY_NET_RETURNS",
        "cohort_formula": "GROUP_BASE_TRADES_BY_ENTRY_TIMESTAMP",
        "holding_duration_formula": "EXIT_AT_MINUS_ENTRY_AT",
        "symbol_contribution_formula": (
            "GROUP_BASE_TRADES_BY_SYMBOL_AND_JOIN_OMITTED_SYMBOL_RESULT"
        ),
        "failure_classification_rule": (
            "RAW_NET_NONPOSITIVE_ELSE_NET_NONPOSITIVE_"
            "ELSE_TEMPORAL_OR_LOMO_ELSE_OTHER"
        ),
        "next_decision_rule": (
            "IF_ALL_INPUT_AND_RECONCILIATION_CHECKS_PASS_"
            "RETURN_TO_UNRELATED_DISCOVERY_ELSE_STOP_BRANCH"
        ),
        "expected_result_relative_path": "r4_failure_analysis_result_v1.json",
        **values,
    }
    payload["frozen_at"] = normalize_timestamp(payload["frozen_at"])
    payload["replay_result_evidence_hashes"] = dict(
        sorted(payload["replay_result_evidence_hashes"].items())
    )
    payload["source_file_sha256"] = dict(sorted(payload["source_file_sha256"].items()))
    payload["preexisting_analysis_artifacts"] = sorted(
        set(payload["preexisting_analysis_artifacts"])
    )
    return R4FailureAnalysisPackage(
        **payload,
        package_evidence_hash=universe_evidence_hash(payload),
    )


def audit_r4_failure_analysis_package(
    package: R4FailureAnalysisPackage,
) -> bool:
    return package.package_evidence_hash == universe_evidence_hash(
        package.model_dump(exclude={"package_evidence_hash"})
    )


def build_r4_failure_analysis_result(**values) -> R4FailureAnalysisResult:
    payload = {
        "schema_version": R4_FAILURE_RESULT_SCHEMA_VERSION,
        "status": "COMPLETE_DESCRIPTIVE_ANALYSIS",
        "original_verdict": "RETIRE_R4_CANDIDATE",
        "creates_candidate": False,
        "changes_r4_verdict": False,
        "opens_2026_or_forward_partition": False,
        "permits_pine_parity_review": False,
        "creates_paper_eligibility": False,
        "creates_live_eligibility": False,
        **values,
    }
    payload["generated_at"] = normalize_timestamp(payload["generated_at"])
    payload["quarterly_summary"] = sorted(
        payload["quarterly_summary"],
        key=lambda row: row.fold_id,
    )
    payload["monthly_net_returns"] = dict(
        sorted(payload["monthly_net_returns"].items())
    )
    payload["exit_reason_summary"] = sorted(
        payload["exit_reason_summary"],
        key=lambda row: row.exit_reason,
    )
    payload["holding_duration_summary"] = sorted(
        payload["holding_duration_summary"],
        key=lambda row: row.bucket_id,
    )
    payload["rebalance_cohorts"] = sorted(
        payload["rebalance_cohorts"],
        key=lambda row: row.entry_at,
    )
    payload["symbol_contribution"] = sorted(
        payload["symbol_contribution"],
        key=lambda row: row.symbol,
    )
    payload["drawdown_episodes"] = sorted(
        payload["drawdown_episodes"],
        key=lambda row: row.sequence,
    )
    payload["integrity_checks"] = dict(sorted(payload["integrity_checks"].items()))
    payload["findings"] = sorted(
        payload["findings"],
        key=lambda row: row.finding_id,
    )
    payload["next_research_decision"] = (
        "STOP_PATH_QUALITY_FAMILY_RETURN_TO_UNRELATED_MECHANISM_DISCOVERY"
        if all(payload["integrity_checks"].values())
        else "STOP_ALL_STRATEGY_RESEARCH_BRANCH"
    )
    return R4FailureAnalysisResult(
        **payload,
        result_evidence_hash=universe_evidence_hash(payload),
    )


def audit_r4_failure_analysis_result(result: R4FailureAnalysisResult) -> bool:
    return result.result_evidence_hash == universe_evidence_hash(
        result.model_dump(exclude={"result_evidence_hash"})
    )
