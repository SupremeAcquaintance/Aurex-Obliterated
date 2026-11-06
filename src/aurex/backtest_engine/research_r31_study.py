from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

R31_STUDY_SCHEMA_VERSION = "aurex-r3.1-path-consistency-study-protocol-v1"
R31_FOLD_IDS = (
    "fold-01-2023q3",
    "fold-02-2023q4",
    "fold-03-2024q1",
    "fold-04-2024q2",
    "fold-05-2024q3",
    "fold-06-2024q4",
)
R31_REQUIRED_DIAGNOSTICS = (
    "accepted_and_rejected_opportunities",
    "cost_decomposition",
    "cost_stress",
    "drawdown_and_exposure_over_time",
    "leave_one_market_out",
    "monthly_net_returns",
    "ols_slope_and_r_squared_at_rebalance",
    "quarterly_fold_results",
    "score_distribution_at_rebalance",
    "symbol_gross_profit_concentration",
    "turnover",
)
R31_EXTERNAL_EVIDENCE_IDS = (
    "CRYPTO_CROSS_SECTIONAL_FACTOR",
    "CRYPTO_MOMENTUM_REVERSAL",
    "CRYPTO_REALISTIC_ASSUMPTIONS",
    "MOMENTUM_PRICE_PATH",
)


class R31ExternalEvidence(BaseModel):
    evidence_id: str = Field(min_length=1, max_length=100)
    citation: str = Field(min_length=10, max_length=500)
    url: str = Field(min_length=10, max_length=500)
    relevance: str = Field(min_length=20, max_length=1000)
    limitation: str = Field(min_length=20, max_length=1000)

    model_config = ConfigDict(extra="forbid")


class R31KnownOutcomeBoundary(BaseModel):
    parent_r3_verdict: Literal["NO_CANDIDATE"] = "NO_CANDIDATE"
    parent_r3_passed_gates: Literal[9] = 9
    parent_r3_total_gates: Literal[10] = 10
    parent_r3_positive_folds: Literal[3] = 3
    parent_r3_required_positive_folds: Literal[4] = 4
    failure_analysis_decision: Literal["PROPOSE_BOUNDED_R3_1"] = (
        "PROPOSE_BOUNDED_R3_1"
    )
    r31_outcome_known: Literal[False] = False

    model_config = ConfigDict(extra="forbid")


class R31SignalDefinition(BaseModel):
    signal_id: Literal["xsmom_path_quality_84d_14d_primary"] = (
        "xsmom_path_quality_84d_14d_primary"
    )
    lookback_intervals: Literal[504] = 504
    close_observations: Literal[505] = 505
    rebalance_bars: Literal[84] = 84
    input_price: Literal["CLOSE"] = "CLOSE"
    input_bar_rule: Literal[
        "505_COMPLETED_CLOSES_SPANNING_504_INTERVALS_ENDING_AT_SIGNAL_CLOSE"
    ] = (
        "505_COMPLETED_CLOSES_SPANNING_504_INTERVALS_ENDING_AT_SIGNAL_CLOSE"
    )
    regression_x: Literal["INTEGER_INDEX_0_THROUGH_504"] = (
        "INTEGER_INDEX_0_THROUGH_504"
    )
    regression_y: Literal["NATURAL_LOG_OF_CLOSE"] = "NATURAL_LOG_OF_CLOSE"
    score_formula: Literal["OLS_SLOPE_TIMES_R_SQUARED"] = (
        "OLS_SLOPE_TIMES_R_SQUARED"
    )
    eligibility_rule: Literal["OLS_SLOPE_STRICTLY_POSITIVE"] = (
        "OLS_SLOPE_STRICTLY_POSITIVE"
    )
    degenerate_rule: Literal["ZERO_SCORE_AND_REJECT_IF_SST_OR_SXX_IS_ZERO"] = (
        "ZERO_SCORE_AND_REJECT_IF_SST_OR_SXX_IS_ZERO"
    )
    ranking_order: Literal["SCORE_DESCENDING_THEN_SYMBOL_ASCENDING"] = (
        "SCORE_DESCENDING_THEN_SYMBOL_ASCENDING"
    )
    selected_fraction: Decimal = Field(default=Decimal("0.20"), gt=0, le=1)
    parameter_search_allowed: Literal[False] = False

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_fixed_values(self) -> "R31SignalDefinition":
        if self.selected_fraction != Decimal("0.20"):
            raise ValueError("R3.1 selected fraction is fixed")
        return self


class R31StudyFold(BaseModel):
    fold_id: str = Field(min_length=1, max_length=64)
    evaluation_start: datetime
    evaluation_end: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("evaluation_start", "evaluation_end")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_window(self) -> "R31StudyFold":
        if self.evaluation_end <= self.evaluation_start:
            raise ValueError("R3.1 study fold end must follow its start")
        return self


class R31PortfolioConstruction(BaseModel):
    direction: Literal["LONG_SPOT_ONLY"] = "LONG_SPOT_ONLY"
    initial_capital: Decimal = Field(default=Decimal("1000"), gt=0)
    weighting_method: Literal["ATR_RISK_WITH_EXPOSURE_CAPS"] = (
        "ATR_RISK_WITH_EXPOSURE_CAPS"
    )
    volatility_lookback_bars: Literal[168] = 168
    atr_lookback_bars: Literal[84] = 84
    catastrophe_stop_atr_multiple: Decimal = Field(default=Decimal("3"), gt=0)
    risk_per_position_percent: Decimal = Field(default=Decimal("0.50"), gt=0)
    max_symbol_exposure_percent: Decimal = Field(default=Decimal("20"), gt=0)
    max_gross_exposure_percent: Decimal = Field(default=Decimal("100"), gt=0)
    max_open_positions: Literal[7] = 7
    minimum_ranked_positions: Literal[3] = 3
    cash_when_insufficient_positive_markets: Literal[True] = True
    rebalance_semantics: Literal["FULL_ROTATION"] = "FULL_ROTATION"
    signal_semantics: Literal["CLOSED_4H_BAR"] = "CLOSED_4H_BAR"
    entry_semantics: Literal["NEXT_4H_OPEN"] = "NEXT_4H_OPEN"
    exit_semantics: Literal["NEXT_REBALANCE_OR_FIXED_ATR_STOP"] = (
        "NEXT_REBALANCE_OR_FIXED_ATR_STOP"
    )
    stop_gap_semantics: Literal["BAR_OPEN_IF_BELOW_STOP_ELSE_STOP"] = (
        "BAR_OPEN_IF_BELOW_STOP_ELSE_STOP"
    )
    same_bar_semantics: Literal["NO_ENTRY_AND_STOP_ON_SAME_BAR"] = (
        "NO_ENTRY_AND_STOP_ON_SAME_BAR"
    )
    no_leverage: Literal[True] = True
    no_shorting: Literal[True] = True
    no_pyramiding: Literal[True] = True
    quantity_increment_assumption: Decimal = Field(
        default=Decimal("0.00000001"), gt=0
    )
    price_increment_assumption: Decimal = Field(
        default=Decimal("0.00000001"), gt=0
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_fixed_values(self) -> "R31PortfolioConstruction":
        expected = {
            "initial_capital": Decimal("1000"),
            "catastrophe_stop_atr_multiple": Decimal("3"),
            "risk_per_position_percent": Decimal("0.50"),
            "max_symbol_exposure_percent": Decimal("20"),
            "max_gross_exposure_percent": Decimal("100"),
            "quantity_increment_assumption": Decimal("0.00000001"),
            "price_increment_assumption": Decimal("0.00000001"),
        }
        if any(getattr(self, field) != value for field, value in expected.items()):
            raise ValueError("R3.1 portfolio values are fixed")
        return self


class R31CostModel(BaseModel):
    commission_percent_per_side: Decimal = Field(default=Decimal("0.10"), ge=0)
    adverse_slippage_percent_per_side: Decimal = Field(default=Decimal("0.05"), ge=0)
    funding_percent: Decimal = Field(default=Decimal("0"), ge=0)
    borrow_percent: Decimal = Field(default=Decimal("0"), ge=0)
    stress_multipliers: list[Decimal]

    model_config = ConfigDict(extra="forbid")

    @field_validator("stress_multipliers")
    @classmethod
    def validate_stress_multipliers(cls, value: list[Decimal]) -> list[Decimal]:
        normalized = sorted(set(value))
        if normalized != [Decimal("1"), Decimal("1.5"), Decimal("2")]:
            raise ValueError("R3.1 cost stress grid is fixed")
        return normalized

    @model_validator(mode="after")
    def validate_fixed_values(self) -> "R31CostModel":
        if (
            self.commission_percent_per_side != Decimal("0.10")
            or self.adverse_slippage_percent_per_side != Decimal("0.05")
            or self.funding_percent != Decimal("0")
            or self.borrow_percent != Decimal("0")
        ):
            raise ValueError("R3.1 cost assumptions are fixed")
        return self


class R31AdvancementGates(BaseModel):
    primary_net_pl_strictly_positive: Literal[True] = True
    minimum_primary_profit_factor: Decimal = Field(default=Decimal("1.10"), gt=1)
    maximum_primary_drawdown_percent: Decimal = Field(
        default=Decimal("20"), gt=0, le=100
    )
    minimum_primary_completed_trades: Literal[100] = 100
    minimum_positive_quarterly_folds: Literal[4] = 4
    total_quarterly_folds: Literal[6] = 6
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
    def validate_fixed_values(self) -> "R31AdvancementGates":
        expected = {
            "minimum_primary_profit_factor": Decimal("1.10"),
            "maximum_primary_drawdown_percent": Decimal("20"),
            "minimum_leave_one_market_out_positive_fraction": Decimal("0.80"),
            "maximum_single_symbol_gross_profit_fraction": Decimal("0.30"),
            "maximum_top_five_gross_profit_fraction": Decimal("0.65"),
        }
        if any(getattr(self, field) != value for field, value in expected.items()):
            raise ValueError("R3.1 gate thresholds are fixed")
        return self


class R31SelectionControl(BaseModel):
    selectable_primary_count: Literal[1] = 1
    selectable_parameter_sets: Literal[1] = 1
    falsification_variants: Literal[0] = 0
    adaptive_parameter_selection: Literal[False] = False
    nested_selection_required: Literal[False] = False
    multiplicity_treatment: Literal[
        "NO_CORRECTION_REQUIRED_FOR_ONE_FIXED_SELECTABLE_HYPOTHESIS"
    ] = "NO_CORRECTION_REQUIRED_FOR_ONE_FIXED_SELECTABLE_HYPOTHESIS"
    development_pass_creates_eligible_strategy: Literal[False] = False
    post_pass_action: Literal[
        "FREEZE_SEPARATE_R4_CANDIDATE_BEFORE_ONE_SHOT_2025_VALIDATION"
    ] = "FREEZE_SEPARATE_R4_CANDIDATE_BEFORE_ONE_SHOT_2025_VALIDATION"
    failure_action: Literal["STOP_CROSS_SECTIONAL_MOMENTUM_FAMILY"] = (
        "STOP_CROSS_SECTIONAL_MOMENTUM_FAMILY"
    )
    rescue_variants_allowed: Literal[False] = False

    model_config = ConfigDict(extra="forbid")


class R31MechanismStudyProtocol(BaseModel):
    schema_version: Literal["aurex-r3.1-path-consistency-study-protocol-v1"] = (
        R31_STUDY_SCHEMA_VERSION
    )
    study_id: Literal["r3.1-cross-sectional-path-quality-spot-v1"] = (
        "r3.1-cross-sectional-path-quality-spot-v1"
    )
    study_version: Literal["1.0.0"] = "1.0.0"
    registered_at: datetime
    status: Literal["FROZEN_PRE_R31_OUTCOME"] = "FROZEN_PRE_R31_OUTCOME"
    research_class: Literal["DEVELOPMENT_ONLY_MECHANISM_FOLLOW_UP"] = (
        "DEVELOPMENT_ONLY_MECHANISM_FOLLOW_UP"
    )
    mechanism_family: Literal["CROSS_SECTIONAL_MOMENTUM_PATH_QUALITY"] = (
        "CROSS_SECTIONAL_MOMENTUM_PATH_QUALITY"
    )
    hypothesis: str = Field(min_length=100, max_length=2000)
    falsification_claim: str = Field(min_length=100, max_length=2000)
    known_outcome_boundary: R31KnownOutcomeBoundary
    parent_r3_protocol_evidence_hash: str
    parent_r3_execution_spec_evidence_hash: str
    parent_r3_result_ledger_evidence_hash: str
    failure_protocol_evidence_hash: str
    failure_package_evidence_hash: str
    failure_result_evidence_hash: str
    universe_manifest_evidence_hash: str
    development_dataset_bundle_evidence_hash: str
    contamination_ledger_hash: str
    builder_contract_hash: str
    venue: Literal["BINANCE"] = "BINANCE"
    market_type: Literal["SPOT"] = "SPOT"
    quote_asset: Literal["USDT"] = "USDT"
    timeframe: Literal["4h"] = "4h"
    development_data_start: datetime
    development_data_end: datetime
    evaluation_start: datetime
    evaluation_end: datetime
    decision_symbols: list[str] = Field(min_length=35, max_length=35)
    diagnostic_only_symbols: list[str] = Field(min_length=3, max_length=3)
    forbidden_partitions: list[Literal["VALIDATION", "HOLDOUT", "FORWARD"]]
    signal: R31SignalDefinition
    folds: list[R31StudyFold] = Field(min_length=6, max_length=6)
    portfolio: R31PortfolioConstruction
    costs: R31CostModel
    gates: R31AdvancementGates
    selection_control: R31SelectionControl
    required_diagnostics: list[str]
    external_evidence: list[R31ExternalEvidence]
    preexisting_r31_result_artifacts: list[str] = Field(default_factory=list)
    r31_outcome_fields_inspected: list[str] = Field(default_factory=list)
    decision_rule: Literal[
        "IF_ALL_GATES_PASS_FREEZE_SEPARATE_R4_CANDIDATE_ELSE_STOP_FAMILY"
    ] = "IF_ALL_GATES_PASS_FREEZE_SEPARATE_R4_CANDIDATE_ELSE_STOP_FAMILY"
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "registered_at",
        "development_data_start",
        "development_data_end",
        "evaluation_start",
        "evaluation_end",
    )
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "parent_r3_protocol_evidence_hash",
        "parent_r3_execution_spec_evidence_hash",
        "parent_r3_result_ledger_evidence_hash",
        "failure_protocol_evidence_hash",
        "failure_package_evidence_hash",
        "failure_result_evidence_hash",
        "universe_manifest_evidence_hash",
        "development_dataset_bundle_evidence_hash",
        "contamination_ledger_hash",
        "builder_contract_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("decision_symbols", "diagnostic_only_symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        return sorted({item.strip().upper() for item in value if item.strip()})

    @field_validator(
        "forbidden_partitions",
        "required_diagnostics",
        "preexisting_r31_result_artifacts",
        "r31_outcome_fields_inspected",
    )
    @classmethod
    def normalize_string_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @field_validator("external_evidence")
    @classmethod
    def sort_external_evidence(
        cls, value: list[R31ExternalEvidence]
    ) -> list[R31ExternalEvidence]:
        return sorted(value, key=lambda item: item.evidence_id)

    @model_validator(mode="after")
    def validate_protocol(self) -> "R31MechanismStudyProtocol":
        if self.preexisting_r31_result_artifacts or self.r31_outcome_fields_inspected:
            raise ValueError("R3.1 protocol must predate every R3.1 outcome")
        if set(self.decision_symbols) & set(self.diagnostic_only_symbols):
            raise ValueError("R3.1 decision and diagnostic symbols cannot overlap")
        if self.forbidden_partitions != ["FORWARD", "HOLDOUT", "VALIDATION"]:
            raise ValueError("R3.1 must keep validation, holdout, and forward sealed")
        if not (
            self.development_data_start
            < self.evaluation_start
            < self.evaluation_end
            <= self.development_data_end
        ):
            raise ValueError("R3.1 evaluation must remain inside development")
        fold_ids = tuple(fold.fold_id for fold in self.folds)
        if fold_ids != R31_FOLD_IDS:
            raise ValueError("R3.1 requires the exact six ordered parent folds")
        if self.folds[0].evaluation_start != self.evaluation_start:
            raise ValueError("R3.1 folds must begin at the evaluation boundary")
        if self.folds[-1].evaluation_end != self.evaluation_end:
            raise ValueError("R3.1 folds must end at the evaluation boundary")
        for previous, current in zip(self.folds, self.folds[1:], strict=False):
            if previous.evaluation_end != current.evaluation_start:
                raise ValueError("R3.1 folds must be contiguous")
        if tuple(self.required_diagnostics) != R31_REQUIRED_DIAGNOSTICS:
            raise ValueError("R3.1 required diagnostics are fixed")
        evidence_ids = tuple(item.evidence_id for item in self.external_evidence)
        if evidence_ids != R31_EXTERNAL_EVIDENCE_IDS:
            raise ValueError("R3.1 external evidence boundary is fixed")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected_hash:
            raise ValueError("R3.1 protocol hash does not match its evidence")
        return self


def build_r31_mechanism_study_protocol(**values) -> R31MechanismStudyProtocol:
    payload = {
        "schema_version": R31_STUDY_SCHEMA_VERSION,
        **values,
    }
    for field in (
        "registered_at",
        "development_data_start",
        "development_data_end",
        "evaluation_start",
        "evaluation_end",
    ):
        payload[field] = canonical_timestamp(payload[field])
    payload["decision_symbols"] = sorted(set(payload["decision_symbols"]))
    payload["diagnostic_only_symbols"] = sorted(
        set(payload["diagnostic_only_symbols"])
    )
    payload["forbidden_partitions"] = sorted(set(payload["forbidden_partitions"]))
    payload["folds"] = sorted(payload["folds"], key=lambda item: item.fold_id)
    payload["required_diagnostics"] = sorted(set(payload["required_diagnostics"]))
    payload["external_evidence"] = sorted(
        payload["external_evidence"], key=lambda item: item.evidence_id
    )
    payload["preexisting_r31_result_artifacts"] = sorted(
        set(payload["preexisting_r31_result_artifacts"])
    )
    payload["r31_outcome_fields_inspected"] = sorted(
        set(payload["r31_outcome_fields_inspected"])
    )
    return R31MechanismStudyProtocol(
        **payload,
        protocol_evidence_hash=universe_evidence_hash(payload),
    )


def canonical_timestamp(value: datetime | str) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    return normalize_timestamp(value)


def audit_r31_mechanism_study_protocol(
    protocol: R31MechanismStudyProtocol,
) -> bool:
    return protocol.protocol_evidence_hash == universe_evidence_hash(
        protocol.model_dump(exclude={"protocol_evidence_hash"})
    )
