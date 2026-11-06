from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

R3_STUDY_SCHEMA_VERSION = "aurex-r3-mechanism-study-protocol-v1"
VariantRole = Literal["PRIMARY", "FALSIFICATION"]


class R3StudyVariant(BaseModel):
    variant_id: str = Field(min_length=1, max_length=100)
    role: VariantRole
    lookback_bars: int = Field(gt=0)
    rebalance_bars: int = Field(gt=0)
    volatility_lookback_bars: int = Field(gt=1)
    atr_lookback_bars: int = Field(gt=1)
    catastrophe_stop_atr_multiple: Decimal = Field(gt=0)
    selected_fraction: Decimal = Field(gt=0, le=1)
    require_positive_absolute_momentum: Literal[True] = True

    model_config = ConfigDict(extra="forbid")


class R3StudyFold(BaseModel):
    fold_id: str = Field(min_length=1, max_length=64)
    evaluation_start: datetime
    evaluation_end: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("evaluation_start", "evaluation_end")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_window(self) -> "R3StudyFold":
        if self.evaluation_end <= self.evaluation_start:
            raise ValueError("R3 study fold end must follow its start")
        return self


class R3PortfolioConstruction(BaseModel):
    direction: Literal["LONG_SPOT_ONLY"] = "LONG_SPOT_ONLY"
    initial_capital: Decimal = Field(gt=0)
    ranking_metric: Literal["LOOKBACK_TOTAL_RETURN"] = "LOOKBACK_TOTAL_RETURN"
    weighting_method: Literal["ATR_RISK_WITH_EXPOSURE_CAPS"] = (
        "ATR_RISK_WITH_EXPOSURE_CAPS"
    )
    risk_per_position_percent: Decimal = Field(gt=0, le=100)
    max_symbol_exposure_percent: Decimal = Field(gt=0, le=100)
    max_gross_exposure_percent: Decimal = Field(gt=0, le=100)
    max_open_positions: int = Field(gt=0)
    minimum_ranked_positions: int = Field(gt=0)
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
    quantity_increment_assumption: Decimal = Field(gt=0)
    price_increment_assumption: Decimal = Field(gt=0)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_exposure(self) -> "R3PortfolioConstruction":
        if self.max_symbol_exposure_percent > self.max_gross_exposure_percent:
            raise ValueError("R3 symbol exposure cannot exceed gross exposure")
        if self.minimum_ranked_positions > self.max_open_positions:
            raise ValueError("R3 minimum positions cannot exceed maximum positions")
        return self


class R3CostModel(BaseModel):
    commission_percent_per_side: Decimal = Field(ge=0)
    adverse_slippage_percent_per_side: Decimal = Field(ge=0)
    funding_percent: Decimal = Field(default=Decimal("0"), ge=0, le=0)
    borrow_percent: Decimal = Field(default=Decimal("0"), ge=0, le=0)
    stress_multipliers: list[Decimal] = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")

    @field_validator("stress_multipliers")
    @classmethod
    def normalize_stress_multipliers(cls, value: list[Decimal]) -> list[Decimal]:
        normalized = sorted(set(value))
        if any(item < 0 for item in normalized):
            raise ValueError("R3 cost stress multipliers cannot be negative")
        if Decimal("1") not in normalized or Decimal("2") not in normalized:
            raise ValueError("R3 cost stress must include base and double-cost cases")
        return normalized


class R3AdvancementGates(BaseModel):
    primary_net_pl_strictly_positive: Literal[True] = True
    minimum_primary_profit_factor: Decimal = Field(gt=1)
    maximum_primary_drawdown_percent: Decimal = Field(gt=0, le=100)
    minimum_primary_completed_trades: int = Field(gt=0)
    minimum_positive_quarterly_folds: int = Field(gt=0)
    total_quarterly_folds: int = Field(gt=0)
    double_cost_net_pl_strictly_positive: Literal[True] = True
    minimum_leave_one_market_out_positive_fraction: Decimal = Field(gt=0, le=1)
    maximum_single_symbol_gross_profit_fraction: Decimal = Field(gt=0, le=1)
    maximum_top_five_gross_profit_fraction: Decimal = Field(gt=0, le=1)
    minimum_supportive_falsification_variants: int = Field(ge=0)
    supportive_variant_minimum_positive_folds: int = Field(ge=0)
    primary_is_never_replaced_by_best_variant: Literal[True] = True
    all_gates_required: Literal[True] = True

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_fold_gate(self) -> "R3AdvancementGates":
        if self.minimum_positive_quarterly_folds > self.total_quarterly_folds:
            raise ValueError("Positive-fold requirement exceeds total R3 folds")
        if self.supportive_variant_minimum_positive_folds > self.total_quarterly_folds:
            raise ValueError("Supportive-variant fold requirement exceeds total folds")
        if (
            self.maximum_single_symbol_gross_profit_fraction
            > self.maximum_top_five_gross_profit_fraction
        ):
            raise ValueError("Single-symbol concentration cannot exceed top-five cap")
        return self


class R3MechanismStudyProtocol(BaseModel):
    schema_version: Literal["aurex-r3-mechanism-study-protocol-v1"] = (
        R3_STUDY_SCHEMA_VERSION
    )
    study_id: str = Field(min_length=1, max_length=128)
    study_version: str = Field(min_length=1, max_length=64)
    registered_at: datetime
    status: Literal["FROZEN_PRE_OUTCOME"] = "FROZEN_PRE_OUTCOME"
    mechanism_family: Literal["CROSS_SECTIONAL_MOMENTUM"] = (
        "CROSS_SECTIONAL_MOMENTUM"
    )
    hypothesis: str = Field(min_length=50, max_length=2000)
    falsification_claim: str = Field(min_length=50, max_length=2000)
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
    decision_symbols: list[str] = Field(min_length=12)
    diagnostic_only_symbols: list[str]
    forbidden_partitions: list[Literal["VALIDATION", "HOLDOUT", "FORWARD"]]
    variants: list[R3StudyVariant] = Field(min_length=3, max_length=3)
    folds: list[R3StudyFold] = Field(min_length=1)
    portfolio: R3PortfolioConstruction
    costs: R3CostModel
    gates: R3AdvancementGates
    required_diagnostics: list[str] = Field(min_length=1)
    source_references: list[str] = Field(min_length=1)
    preexisting_result_artifacts: list[str] = Field(default_factory=list)
    outcome_fields_inspected: list[str] = Field(default_factory=list)
    decision_rule: Literal[
        "ADVANCE_PRIMARY_TO_R4_ONLY_IF_ALL_GATES_PASS_ELSE_NO_CANDIDATE"
    ] = "ADVANCE_PRIMARY_TO_R4_ONLY_IF_ALL_GATES_PASS_ELSE_NO_CANDIDATE"
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
        "universe_manifest_evidence_hash",
        "development_dataset_bundle_evidence_hash",
        "contamination_ledger_hash",
        "builder_contract_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("decision_symbols", "diagnostic_only_symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        return sorted({item.strip().upper() for item in value if item.strip()})

    @field_validator(
        "forbidden_partitions",
        "required_diagnostics",
        "source_references",
        "preexisting_result_artifacts",
        "outcome_fields_inspected",
    )
    @classmethod
    def normalize_string_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_protocol(self) -> "R3MechanismStudyProtocol":
        if self.outcome_fields_inspected or self.preexisting_result_artifacts:
            raise ValueError("R3 protocol must be frozen before any study outcome exists")
        if set(self.decision_symbols) & set(self.diagnostic_only_symbols):
            raise ValueError("R3 decision and diagnostic-only symbols cannot overlap")
        if self.forbidden_partitions != ["FORWARD", "HOLDOUT", "VALIDATION"]:
            raise ValueError("R3 must forbid validation, holdout, and forward partitions")
        if not (
            self.development_data_start
            < self.evaluation_start
            < self.evaluation_end
            <= self.development_data_end
        ):
            raise ValueError("R3 evaluation must remain inside development after warm-up")
        variants = sorted(self.variants, key=lambda item: item.variant_id)
        if self.variants != variants:
            raise ValueError("R3 study variants must be sorted by ID")
        primary = [variant for variant in variants if variant.role == "PRIMARY"]
        if len(primary) != 1:
            raise ValueError("R3 study requires exactly one primary variant")
        if primary[0].variant_id != "xsmom_84d_14d_primary":
            raise ValueError("R3 primary identity is fixed before outcomes")
        fold_ids = [fold.fold_id for fold in self.folds]
        if fold_ids != sorted(fold_ids) or len(fold_ids) != len(set(fold_ids)):
            raise ValueError("R3 folds must be uniquely sorted by ID")
        ordered_folds = sorted(self.folds, key=lambda fold: fold.evaluation_start)
        if ordered_folds[0].evaluation_start != self.evaluation_start:
            raise ValueError("R3 folds must begin at the evaluation boundary")
        if ordered_folds[-1].evaluation_end != self.evaluation_end:
            raise ValueError("R3 folds must end at the evaluation boundary")
        for previous, current in zip(ordered_folds, ordered_folds[1:], strict=False):
            if previous.evaluation_end != current.evaluation_start:
                raise ValueError("R3 study folds must be contiguous")
        if self.gates.total_quarterly_folds != len(self.folds):
            raise ValueError("R3 gate fold count must match the declared folds")
        if self.gates.minimum_supportive_falsification_variants > len(variants) - 1:
            raise ValueError("R3 supportive-variant gate exceeds falsification variants")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected_hash:
            raise ValueError("R3 protocol evidence hash does not match inputs")
        return self


def build_r3_mechanism_study_protocol(**values) -> R3MechanismStudyProtocol:
    payload = {
        "schema_version": R3_STUDY_SCHEMA_VERSION,
        **values,
    }
    payload["decision_symbols"] = sorted(set(payload["decision_symbols"]))
    payload["diagnostic_only_symbols"] = sorted(
        set(payload["diagnostic_only_symbols"])
    )
    payload["forbidden_partitions"] = sorted(set(payload["forbidden_partitions"]))
    payload["variants"] = sorted(
        payload["variants"],
        key=lambda item: item.variant_id,
    )
    payload["folds"] = sorted(payload["folds"], key=lambda item: item.fold_id)
    for field in (
        "registered_at",
        "development_data_start",
        "development_data_end",
        "evaluation_start",
        "evaluation_end",
    ):
        payload[field] = canonical_timestamp(payload[field])
    for field in (
        "required_diagnostics",
        "source_references",
        "preexisting_result_artifacts",
        "outcome_fields_inspected",
    ):
        payload[field] = sorted(set(payload[field]))
    return R3MechanismStudyProtocol(
        **payload,
        protocol_evidence_hash=universe_evidence_hash(payload),
    )


def canonical_timestamp(value: datetime | str) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    return normalize_timestamp(value)


def audit_r3_mechanism_study_protocol(
    protocol: R3MechanismStudyProtocol,
) -> bool:
    return protocol.protocol_evidence_hash == universe_evidence_hash(
        protocol.model_dump(exclude={"protocol_evidence_hash"})
    )
