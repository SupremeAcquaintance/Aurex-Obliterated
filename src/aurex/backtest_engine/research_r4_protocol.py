from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_r31_study import (
    R31CostModel,
    R31PortfolioConstruction,
    R31SignalDefinition,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

R4_PROTOCOL_SCHEMA_VERSION = "aurex-r4-path-quality-candidate-protocol-v1"
R4_DECISION_SYMBOLS = (
    "AAVEUSDT",
    "ADAUSDT",
    "APEUSDT",
    "APTUSDT",
    "ATOMUSDT",
    "AVAXUSDT",
    "BCHUSDT",
    "BNBUSDT",
    "CFXUSDT",
    "CRVUSDT",
    "DOGEUSDT",
    "DOTUSDT",
    "DYDXUSDT",
    "ETCUSDT",
    "FETUSDT",
    "FILUSDT",
    "FTMUSDT",
    "GALAUSDT",
    "GRTUSDT",
    "ICPUSDT",
    "INJUSDT",
    "LDOUSDT",
    "LINKUSDT",
    "LTCUSDT",
    "LUNCUSDT",
    "MKRUSDT",
    "NEARUSDT",
    "OPUSDT",
    "RUNEUSDT",
    "SANDUSDT",
    "SHIBUSDT",
    "STXUSDT",
    "TRXUSDT",
    "UNIUSDT",
    "XRPUSDT",
)
R4_REQUIRED_MONTHS = tuple(f"2025-{month:02d}" for month in range(1, 13))
R4_FOLD_IDS = (
    "validation-fold-01-2025q1",
    "validation-fold-02-2025q2",
    "validation-fold-03-2025q3",
    "validation-fold-04-2025q4",
)
R4_REQUIRED_DIAGNOSTICS = (
    "accepted_and_rejected_opportunities",
    "active_symbol_count_at_each_rebalance",
    "cost_decomposition",
    "cost_stress",
    "drawdown_and_exposure_over_time",
    "leave_one_market_out",
    "market_termination_writeoffs",
    "monthly_net_returns",
    "ols_slope_and_r_squared_at_rebalance",
    "quarterly_fold_results",
    "score_distribution_at_rebalance",
    "symbol_gross_profit_concentration",
    "turnover",
)


class R4KnownOutcomeBoundary(BaseModel):
    parent_r31_verdict: Literal["PERMIT_R4_PREREGISTRATION"] = (
        "PERMIT_R4_PREREGISTRATION"
    )
    parent_r31_passed_gates: Literal[9] = 9
    parent_r31_total_gates: Literal[9] = 9
    parent_r31_positive_folds: Literal[4] = 4
    parent_r31_required_positive_folds: Literal[4] = 4
    parent_r31_creates_eligible_strategy: Literal[False] = False
    parent_r31_opens_validation_partition: Literal[False] = False
    r4_validation_outcome_known: Literal[False] = False

    model_config = ConfigDict(extra="forbid")


class R4ValidationFold(BaseModel):
    fold_id: str = Field(min_length=1, max_length=80)
    evaluation_start: datetime
    evaluation_end: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("evaluation_start", "evaluation_end")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_window(self) -> "R4ValidationFold":
        if self.evaluation_end <= self.evaluation_start:
            raise ValueError("R4 fold end must follow its start")
        return self


class R4ValidationDataContract(BaseModel):
    partition_name: Literal["VALIDATION"] = "VALIDATION"
    partition_start: datetime
    partition_end: datetime
    timeframe: Literal["4h"] = "4h"
    expected_candle_interval_hours: Literal[4] = 4
    expected_full_partition_rows_per_symbol: Literal[2190] = 2190
    required_archive_months: list[str] = Field(min_length=12, max_length=12)
    archive_source: Literal[
        "HTTPS_BINANCE_VISION_SPOT_MONTHLY_KLINES_WITH_CHECKSUM"
    ] = "HTTPS_BINANCE_VISION_SPOT_MONTHLY_KLINES_WITH_CHECKSUM"
    warmup_source: Literal["FROZEN_DEVELOPMENT_BUNDLE"] = (
        "FROZEN_DEVELOPMENT_BUNDLE"
    )
    warmup_close_observations: Literal[505] = 505
    warmup_ends_at: datetime
    inspected_market_fields: list[str]
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    accepted_availability_shapes: list[
        Literal["FULL_CONTINUOUS", "CONTIGUOUS_TERMINAL_SUFFIX_MISSING"]
    ]
    leading_missing_candle_policy: Literal["BLOCK_DATASET"] = "BLOCK_DATASET"
    internal_missing_candle_policy: Literal["BLOCK_DATASET"] = "BLOCK_DATASET"
    resumed_after_missing_policy: Literal["BLOCK_DATASET"] = "BLOCK_DATASET"
    duplicate_candle_policy: Literal["BLOCK_DATASET"] = "BLOCK_DATASET"
    outside_partition_policy: Literal["BLOCK_DATASET"] = "BLOCK_DATASET"
    unavailable_archive_policy: Literal[
        "RECORD_AND_ALLOW_ONLY_IF_MISSING_CANDLES_FORM_TERMINAL_SUFFIX"
    ] = "RECORD_AND_ALLOW_ONLY_IF_MISSING_CANDLES_FORM_TERMINAL_SUFFIX"
    terminated_unheld_symbol_policy: Literal[
        "REMOVE_FROM_ELIGIBLE_RANKING_PERMANENTLY"
    ] = "REMOVE_FROM_ELIGIBLE_RANKING_PERMANENTLY"
    terminated_held_symbol_policy: Literal[
        "WRITE_OFF_TO_ZERO_AT_FIRST_MISSING_BAR"
    ] = "WRITE_OFF_TO_ZERO_AT_FIRST_MISSING_BAR"
    terminated_symbol_reactivation: Literal[False] = False
    minimum_positive_markets_for_entry: Literal[3] = 3
    insufficient_active_or_positive_markets_policy: Literal["HOLD_CASH"] = "HOLD_CASH"
    fixed_baseline_symbol_count: Literal[35] = 35
    replacement_symbols_allowed: Literal[False] = False
    synthetic_candles_allowed: Literal[False] = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("partition_start", "partition_end", "warmup_ends_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "required_archive_months",
        "inspected_market_fields",
        "strategy_outcome_fields_inspected",
        "accepted_availability_shapes",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_contract(self) -> "R4ValidationDataContract":
        if self.partition_start.isoformat() != "2025-01-01T00:00:00+00:00":
            raise ValueError("R4 validation start is fixed")
        if self.partition_end.isoformat() != "2026-01-01T00:00:00+00:00":
            raise ValueError("R4 validation end is fixed")
        if self.warmup_ends_at != self.partition_start:
            raise ValueError("R4 warmup must end exactly at validation start")
        if self.required_archive_months != sorted(R4_REQUIRED_MONTHS):
            raise ValueError("R4 requires every 2025 monthly archive request")
        if self.inspected_market_fields != [
            "close",
            "high",
            "low",
            "open",
            "timestamp",
            "volume",
        ]:
            raise ValueError("R4 data acquisition is limited to exact OHLCV fields")
        if self.strategy_outcome_fields_inspected:
            raise ValueError("R4 protocol must predate every validation outcome")
        if self.accepted_availability_shapes != [
            "CONTIGUOUS_TERMINAL_SUFFIX_MISSING",
            "FULL_CONTINUOUS",
        ]:
            raise ValueError("R4 market-availability shapes are fixed")
        return self


class R4ValidationGates(BaseModel):
    base_cost_net_pl_strictly_positive: Literal[True] = True
    minimum_base_cost_profit_factor: Decimal = Field(
        default=Decimal("1.10"), gt=1
    )
    maximum_base_cost_drawdown_percent: Decimal = Field(
        default=Decimal("20"), gt=0, le=100
    )
    minimum_base_cost_completed_trades: Literal[67] = 67
    minimum_trade_count_basis: Literal[
        "CEILING_PARENT_100_TRADES_TIMES_12_MONTHS_DIVIDED_BY_18_MONTHS"
    ] = "CEILING_PARENT_100_TRADES_TIMES_12_MONTHS_DIVIDED_BY_18_MONTHS"
    minimum_positive_quarterly_folds: Literal[3] = 3
    total_quarterly_folds: Literal[4] = 4
    positive_fold_basis: Literal[
        "CEILING_PARENT_4_POSITIVE_FOLDS_TIMES_4_FOLDS_DIVIDED_BY_6_FOLDS"
    ] = "CEILING_PARENT_4_POSITIVE_FOLDS_TIMES_4_FOLDS_DIVIDED_BY_6_FOLDS"
    double_cost_net_pl_strictly_positive: Literal[True] = True
    minimum_leave_one_market_out_positive_fraction: Decimal = Field(
        default=Decimal("0.80"), gt=0, le=1
    )
    maximum_single_symbol_gross_profit_fraction: Decimal = Field(
        default=Decimal("0.30"), gt=0, le=1
    )
    maximum_top_five_gross_profit_fraction: Decimal = Field(
        default=Decimal("0.65"), gt=0, le=1
    )
    all_gates_required: Literal[True] = True

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_fixed_values(self) -> "R4ValidationGates":
        expected = {
            "minimum_base_cost_profit_factor": Decimal("1.10"),
            "maximum_base_cost_drawdown_percent": Decimal("20"),
            "minimum_leave_one_market_out_positive_fraction": Decimal("0.80"),
            "maximum_single_symbol_gross_profit_fraction": Decimal("0.30"),
            "maximum_top_five_gross_profit_fraction": Decimal("0.65"),
        }
        if any(getattr(self, field) != value for field, value in expected.items()):
            raise ValueError("R4 validation thresholds are fixed")
        return self


class R4ReplayMatrix(BaseModel):
    overall_cost_runs: Literal[3] = 3
    quarterly_fold_runs: Literal[4] = 4
    leave_one_market_out_runs: Literal[35] = 35
    expected_total_runs: Literal[42] = 42
    overall_cost_multipliers: list[Decimal]
    fold_cost_multiplier: Decimal = Decimal("1")
    leave_one_out_cost_multiplier: Decimal = Decimal("1")

    model_config = ConfigDict(extra="forbid")

    @field_validator("overall_cost_multipliers")
    @classmethod
    def validate_costs(cls, value: list[Decimal]) -> list[Decimal]:
        normalized = sorted(set(value))
        if normalized != [Decimal("1"), Decimal("1.5"), Decimal("2")]:
            raise ValueError("R4 overall cost grid is fixed")
        return normalized

    @model_validator(mode="after")
    def validate_matrix(self) -> "R4ReplayMatrix":
        if (
            self.fold_cost_multiplier != Decimal("1")
            or self.leave_one_out_cost_multiplier != Decimal("1")
        ):
            raise ValueError("R4 robustness runs use base cost")
        return self


class R4SelectionControl(BaseModel):
    candidate_selected_from: Literal["ACCEPTED_R31_PRIMARY_ONLY"] = (
        "ACCEPTED_R31_PRIMARY_ONLY"
    )
    selectable_candidates: Literal[1] = 1
    selectable_parameter_sets: Literal[1] = 1
    signal_changes_from_r31: list[str] = Field(default_factory=list)
    portfolio_changes_from_r31: list[str] = Field(default_factory=list)
    cost_changes_from_r31: list[str] = Field(default_factory=list)
    gate_relaxation_from_r31: Literal[False] = False
    availability_semantic_delta: Literal[
        "PROSPECTIVE_TERMINAL_MARKET_UNAVAILABILITY_ONLY"
    ] = "PROSPECTIVE_TERMINAL_MARKET_UNAVAILABILITY_ONLY"
    validation_tuning_allowed: Literal[False] = False
    rescue_variants_allowed: Literal[False] = False
    validation_pass_action: Literal["PERMIT_PINE_PARITY_REVIEW_ONLY"] = (
        "PERMIT_PINE_PARITY_REVIEW_ONLY"
    )
    validation_failure_action: Literal["RETIRE_R4_CANDIDATE"] = (
        "RETIRE_R4_CANDIDATE"
    )
    data_integrity_failure_action: Literal[
        "BLOCK_WITHOUT_STRATEGY_OUTCOME"
    ] = "BLOCK_WITHOUT_STRATEGY_OUTCOME"
    validation_pass_creates_paper_eligibility: Literal[False] = False
    validation_pass_creates_live_eligibility: Literal[False] = False

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "signal_changes_from_r31",
        "portfolio_changes_from_r31",
        "cost_changes_from_r31",
    )
    @classmethod
    def normalize_changes(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_no_strategy_changes(self) -> "R4SelectionControl":
        if (
            self.signal_changes_from_r31
            or self.portfolio_changes_from_r31
            or self.cost_changes_from_r31
        ):
            raise ValueError("R4 must preserve the accepted R3.1 strategy unchanged")
        return self


class R4CandidateProtocol(BaseModel):
    schema_version: Literal["aurex-r4-path-quality-candidate-protocol-v1"] = (
        R4_PROTOCOL_SCHEMA_VERSION
    )
    candidate_id: Literal["path_quality_spot_v1"] = "path_quality_spot_v1"
    candidate_version: Literal["1.0.0"] = "1.0.0"
    registered_at: datetime
    status: Literal["FROZEN_PRE_VALIDATION_OUTCOME"] = (
        "FROZEN_PRE_VALIDATION_OUTCOME"
    )
    research_stage: Literal["R4_CANDIDATE_PREREGISTRATION"] = (
        "R4_CANDIDATE_PREREGISTRATION"
    )
    mechanism_family: Literal["CROSS_SECTIONAL_MOMENTUM_PATH_QUALITY"] = (
        "CROSS_SECTIONAL_MOMENTUM_PATH_QUALITY"
    )
    hypothesis: str = Field(min_length=100, max_length=2000)
    falsification_claim: str = Field(min_length=100, max_length=2000)
    known_outcome_boundary: R4KnownOutcomeBoundary
    parent_r31_protocol_evidence_hash: str
    parent_r31_execution_specification_evidence_hash: str
    parent_r31_run_package_evidence_hash: str
    parent_r31_result_ledger_evidence_hash: str
    universe_manifest_evidence_hash: str
    development_dataset_bundle_evidence_hash: str
    contamination_ledger_hash: str
    builder_contract_hash: str
    decision_symbols: list[str] = Field(min_length=35, max_length=35)
    signal: R31SignalDefinition
    portfolio: R31PortfolioConstruction
    costs: R31CostModel
    validation_data: R4ValidationDataContract
    folds: list[R4ValidationFold] = Field(min_length=4, max_length=4)
    gates: R4ValidationGates
    replay_matrix: R4ReplayMatrix
    selection_control: R4SelectionControl
    required_diagnostics: list[str]
    validation_data_acquired_at_registration: Literal[False] = False
    preexisting_validation_data_artifacts: list[str] = Field(default_factory=list)
    preexisting_r4_result_artifacts: list[str] = Field(default_factory=list)
    validation_outcome_fields_inspected: list[str] = Field(default_factory=list)
    decision_rule: Literal[
        "IF_DATA_BLOCKED_NO_OUTCOME_ELSE_IF_ALL_GATES_PASS_PERMIT_PINE_PARITY_ONLY_ELSE_RETIRE"
    ] = (
        "IF_DATA_BLOCKED_NO_OUTCOME_ELSE_IF_ALL_GATES_PASS_PERMIT_PINE_PARITY_ONLY_ELSE_RETIRE"
    )
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("registered_at")
    @classmethod
    def normalize_registered_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "parent_r31_protocol_evidence_hash",
        "parent_r31_execution_specification_evidence_hash",
        "parent_r31_run_package_evidence_hash",
        "parent_r31_result_ledger_evidence_hash",
        "universe_manifest_evidence_hash",
        "development_dataset_bundle_evidence_hash",
        "contamination_ledger_hash",
        "builder_contract_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("decision_symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        return sorted({item.strip().upper() for item in value if item.strip()})

    @field_validator(
        "required_diagnostics",
        "preexisting_validation_data_artifacts",
        "preexisting_r4_result_artifacts",
        "validation_outcome_fields_inspected",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_protocol(self) -> "R4CandidateProtocol":
        if tuple(self.decision_symbols) != R4_DECISION_SYMBOLS:
            raise ValueError("R4 decision universe must remain the exact R3.1 universe")
        if [fold.fold_id for fold in self.folds] != list(R4_FOLD_IDS):
            raise ValueError("R4 quarterly folds are fixed and ordered")
        expected_windows = [
            ("2025-01-01T00:00:00+00:00", "2025-04-01T00:00:00+00:00"),
            ("2025-04-01T00:00:00+00:00", "2025-07-01T00:00:00+00:00"),
            ("2025-07-01T00:00:00+00:00", "2025-10-01T00:00:00+00:00"),
            ("2025-10-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
        ]
        observed_windows = [
            (fold.evaluation_start.isoformat(), fold.evaluation_end.isoformat())
            for fold in self.folds
        ]
        if observed_windows != expected_windows:
            raise ValueError("R4 quarterly windows are fixed")
        if self.required_diagnostics != sorted(R4_REQUIRED_DIAGNOSTICS):
            raise ValueError("R4 diagnostics are fixed")
        if (
            self.preexisting_validation_data_artifacts
            or self.preexisting_r4_result_artifacts
            or self.validation_outcome_fields_inspected
        ):
            raise ValueError("R4 protocol must predate validation data and outcomes")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected_hash:
            raise ValueError("R4 protocol hash does not match its evidence")
        return self


def build_r4_candidate_protocol(**values) -> R4CandidateProtocol:
    payload = {
        "schema_version": R4_PROTOCOL_SCHEMA_VERSION,
        "candidate_id": "path_quality_spot_v1",
        "candidate_version": "1.0.0",
        "status": "FROZEN_PRE_VALIDATION_OUTCOME",
        "research_stage": "R4_CANDIDATE_PREREGISTRATION",
        "mechanism_family": "CROSS_SECTIONAL_MOMENTUM_PATH_QUALITY",
        "validation_data_acquired_at_registration": False,
        "decision_rule": (
            "IF_DATA_BLOCKED_NO_OUTCOME_ELSE_IF_ALL_GATES_PASS_"
            "PERMIT_PINE_PARITY_ONLY_ELSE_RETIRE"
        ),
        **values,
    }
    payload["registered_at"] = normalize_timestamp(payload["registered_at"])
    payload["decision_symbols"] = sorted(payload["decision_symbols"])
    payload["folds"] = sorted(
        payload["folds"], key=lambda fold: fold.evaluation_start
    )
    for field in (
        "required_diagnostics",
        "preexisting_validation_data_artifacts",
        "preexisting_r4_result_artifacts",
        "validation_outcome_fields_inspected",
    ):
        payload[field] = sorted(set(payload[field]))
    return R4CandidateProtocol(
        **payload,
        protocol_evidence_hash=universe_evidence_hash(payload),
    )


def audit_r4_candidate_protocol(protocol: R4CandidateProtocol) -> bool:
    return protocol.protocol_evidence_hash == universe_evidence_hash(
        protocol.model_dump(exclude={"protocol_evidence_hash"})
    )
