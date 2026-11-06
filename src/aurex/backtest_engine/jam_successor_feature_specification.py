from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal
from statistics import median
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.jam_archive_quality_remediation import (
    JamQualityEvidencePartition,
)
from aurex.backtest_engine.jam_successor_feature_protocol import (
    frozen_feature_partitions,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

JAM_FEATURE_SPEC_SCHEMA_VERSION = (
    "aurex-jam-successor-feature-specification-v1"
)
JAM_FEATURE_SPEC_ID = "jam-successor-feature-specification-v1"
JAM_FEATURE_AUDIT_SCHEMA_VERSION = (
    "aurex-jam-successor-feature-specification-audit-v1"
)
JAM_FEATURE_PASS_DECISION = (
    "PASS_CAUSAL_FEATURE_SPECIFICATION_AWAIT_DEVELOPMENT_DISTRIBUTION_AUTHORIZATION"
)
JAM_FEATURE_NEXT_AUTHORIZATION = (
    "AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_FEATURE_DISTRIBUTION_NO_RETURNS"
)
JAM_FEATURE_MAXIMUM_LOOKBACK_MINUTES = 133
JAM_FEATURE_OUTPUT_DECIMAL_PLACES = 18
JAM_FEATURE_ROBUST_SCALE_CONSTANT = "1.4826"
JAM_FEATURE_BPS_CONSTANT = "10000"
JAM_FEATURE_OUTPUT_QUANTUM = Decimal("0.000000000000000001")
JAM_FEATURE_PHASE_IDS = (
    "BASELINE",
    "PRE_SHOCK_REFERENCE",
    "SHOCK",
    "CONFIRMATION",
)
JAM_FEATURE_IDS = (
    "baseline_sell_quote_median_120m",
    "baseline_sell_quote_mad_120m",
    "baseline_sell_share_median_120m",
    "baseline_sell_share_mad_120m",
    "pre_shock_vwap_5m",
    "shock_sell_quote_mean_5m",
    "shock_sell_flow_robust_z_5m",
    "shock_sell_share_5m",
    "shock_price_impact_bps_5m",
    "shock_low_bps_vs_pre_shock_vwap",
    "confirmation_sell_quote_mean_3m",
    "confirmation_sell_flow_robust_z_3m",
    "confirmation_sell_share_3m",
    "sell_flow_decay_ratio_3m_vs_5m",
    "sell_share_decay_delta_5m_to_3m",
    "reclaim_bps_vs_pre_shock_vwap",
    "bounce_bps_from_shock_low",
)
JAM_FEATURE_QUALITY_STATES = (
    "READY",
    "PARTITION_RESET_WARMUP",
    "SOURCE_QUARANTINE",
    "POST_DEFECT_WARMUP",
    "NO_AGGTRADE_MINUTE",
    "DEGENERATE_ROBUST_SCALE",
    "DEGENERATE_DENOMINATOR",
)


def _decimal_string(value: Decimal | str) -> str:
    decimal_value = value if isinstance(value, Decimal) else Decimal(value)
    if not decimal_value.is_finite():
        raise ValueError("Jam feature decimal must be finite")
    return format(decimal_value, "f")


def _quantize(value: Decimal) -> Decimal:
    if not value.is_finite():
        raise ValueError("Jam feature output must be finite")
    return value.quantize(JAM_FEATURE_OUTPUT_QUANTUM, rounding=ROUND_HALF_EVEN)


def _median(values: list[Decimal]) -> Decimal:
    return Decimal(median(values))


def _mad(values: list[Decimal], center: Decimal) -> Decimal:
    return _median([abs(value - center) for value in values])


class JamFeatureTemporalPhase(BaseModel):
    phase_id: Literal[
        "BASELINE",
        "PRE_SHOCK_REFERENCE",
        "SHOCK",
        "CONFIRMATION",
    ]
    oldest_lag_minutes: int = Field(ge=0, le=239)
    newest_lag_minutes: int = Field(ge=0, le=239)
    minute_count: int = Field(gt=0, le=240)
    purpose: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_phase(self) -> JamFeatureTemporalPhase:
        if (
            self.oldest_lag_minutes < self.newest_lag_minutes
            or self.minute_count
            != self.oldest_lag_minutes - self.newest_lag_minutes + 1
        ):
            raise ValueError("Jam feature temporal phase changed")
        return self


class JamFeatureDefinition(BaseModel):
    feature_id: str = Field(min_length=1)
    category: Literal[
        "BASELINE",
        "REFERENCE",
        "SHOCK",
        "CONFIRMATION",
        "DECAY",
        "RECLAIM",
    ]
    formula: str = Field(min_length=1)
    source_fields: list[str] = Field(min_length=1)
    temporal_phases: list[str] = Field(min_length=1, max_length=4)
    units: Literal[
        "QUOTE_ASSET",
        "PRICE",
        "RATIO",
        "ROBUST_Z",
        "BASIS_POINTS",
    ]
    undefined_when: list[str]

    model_config = ConfigDict(extra="forbid")

    @field_validator("source_fields", "temporal_phases", "undefined_when")
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})


class JamFeatureQualityStateDefinition(BaseModel):
    state: Literal[
        "READY",
        "PARTITION_RESET_WARMUP",
        "SOURCE_QUARANTINE",
        "POST_DEFECT_WARMUP",
        "NO_AGGTRADE_MINUTE",
        "DEGENERATE_ROBUST_SCALE",
        "DEGENERATE_DENOMINATOR",
    ]
    feature_values_permitted: bool
    resets_state: bool
    description: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class JamSyntheticConformanceCase(BaseModel):
    case_id: str = Field(min_length=1)
    assertion: str = Field(min_length=1)
    passed: Literal[True] = True
    synthetic_row_count: int = Field(ge=0, le=1_000)
    observed_state: str = Field(min_length=1)
    case_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("case_evidence_hash")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_case(self) -> JamSyntheticConformanceCase:
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"case_evidence_hash"})
        )
        if self.case_evidence_hash != expected_hash:
            raise ValueError("Jam feature conformance case hash changed")
        return self


class JamAggTradeFixture(BaseModel):
    aggregate_trade_id: int = Field(ge=0)
    price: Decimal = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    first_trade_id: int = Field(ge=0)
    last_trade_id: int = Field(ge=0)
    transact_time_ms: int = Field(gt=0)
    is_buyer_maker: bool
    is_best_match: bool = True

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_trade(self) -> JamAggTradeFixture:
        if self.first_trade_id > self.last_trade_id:
            raise ValueError("Jam feature raw-trade span changed")
        return self


class JamFeatureMinute(BaseModel):
    open_time_ms: int = Field(gt=0)
    open_price: Decimal = Field(gt=0)
    high_price: Decimal = Field(gt=0)
    low_price: Decimal = Field(gt=0)
    close_price: Decimal = Field(gt=0)
    base_volume: Decimal = Field(gt=0)
    quote_volume: Decimal = Field(gt=0)
    taker_buy_quote_volume: Decimal = Field(ge=0)
    taker_sell_quote_volume: Decimal = Field(ge=0)
    raw_trade_count: int = Field(gt=0)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_minute(self) -> JamFeatureMinute:
        if (
            self.open_time_ms % 60_000
            or self.high_price
            < max(self.open_price, self.low_price, self.close_price)
            or self.low_price
            > min(self.open_price, self.high_price, self.close_price)
            or self.quote_volume
            != self.taker_buy_quote_volume + self.taker_sell_quote_volume
        ):
            raise ValueError("Jam feature minute invariant changed")
        return self

    @property
    def sell_share(self) -> Decimal:
        return self.taker_sell_quote_volume / self.quote_volume


class JamComputedFeatureRow(BaseModel):
    evaluation_open_time_ms: int = Field(gt=0)
    quality_state: Literal[
        "READY",
        "PARTITION_RESET_WARMUP",
        "SOURCE_QUARANTINE",
        "POST_DEFECT_WARMUP",
        "NO_AGGTRADE_MINUTE",
        "DEGENERATE_ROBUST_SCALE",
        "DEGENERATE_DENOMINATOR",
    ]
    feature_values: dict[str, Decimal]

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_row(self) -> JamComputedFeatureRow:
        if self.quality_state == "READY":
            if tuple(self.feature_values) != JAM_FEATURE_IDS:
                raise ValueError("Jam feature-ready output schema changed")
        elif self.feature_values:
            raise ValueError("Jam non-ready row cannot expose feature values")
        return self


class JamSuccessorFeatureSpecification(BaseModel):
    schema_version: Literal[
        "aurex-jam-successor-feature-specification-v1"
    ] = JAM_FEATURE_SPEC_SCHEMA_VERSION
    specification_id: Literal[
        "jam-successor-feature-specification-v1"
    ] = JAM_FEATURE_SPEC_ID
    frozen_at: datetime
    status: Literal["FROZEN_CAUSAL_SPECIFICATION_NO_RETURNS"] = (
        "FROZEN_CAUSAL_SPECIFICATION_NO_RETURNS"
    )
    protocol_path: Literal[
        "data/evidence/jam_successor_feature_specification_protocol_v1.json"
    ] = "data/evidence/jam_successor_feature_specification_protocol_v1.json"
    protocol_file_sha256: str
    protocol_evidence_hash: str
    specification_contract_hash: str
    selected_proposal_id: Literal[
        "J2-P01-AGGRESSIVE-SELL-FLOW-EXHAUSTION-RECLAIM"
    ] = "J2-P01-AGGRESSIVE-SELL-FLOW-EXHAUSTION-RECLAIM"
    source_grain: Literal["UTC_ONE_MINUTE_FROM_AGGTRADES"] = (
        "UTC_ONE_MINUTE_FROM_AGGTRADES"
    )
    timestamp_normalization: Literal[
        "MILLISECONDS_13_DIGITS_OR_MICROSECONDS_16_DIGITS_FLOORED_TO_MILLISECONDS"
    ] = "MILLISECONDS_13_DIGITS_OR_MICROSECONDS_16_DIGITS_FLOORED_TO_MILLISECONDS"
    buyer_maker_true_mapping: Literal[
        "SELLER_WAS_TAKER_TAKER_SELL"
    ] = "SELLER_WAS_TAKER_TAKER_SELL"
    buyer_maker_false_mapping: Literal[
        "BUYER_WAS_TAKER_TAKER_BUY"
    ] = "BUYER_WAS_TAKER_TAKER_BUY"
    minute_quote_notional_formula: Literal[
        "SUM_PRICE_MULTIPLIED_BY_QUANTITY"
    ] = "SUM_PRICE_MULTIPLIED_BY_QUANTITY"
    phases: list[JamFeatureTemporalPhase] = Field(min_length=4, max_length=4)
    features: list[JamFeatureDefinition] = Field(min_length=17, max_length=17)
    feature_count: Literal[17] = 17
    maximum_lookback_minutes: Literal[133] = (
        JAM_FEATURE_MAXIMUM_LOOKBACK_MINUTES
    )
    minimum_consecutive_valid_minutes: Literal[133] = (
        JAM_FEATURE_MAXIMUM_LOOKBACK_MINUTES
    )
    robust_scale_constant: Literal["1.4826"] = (
        JAM_FEATURE_ROBUST_SCALE_CONSTANT
    )
    basis_points_constant: Literal["10000"] = JAM_FEATURE_BPS_CONSTANT
    output_decimal_places: Literal[18] = JAM_FEATURE_OUTPUT_DECIMAL_PLACES
    output_rounding: Literal["ROUND_HALF_EVEN"] = "ROUND_HALF_EVEN"
    quality_states: list[JamFeatureQualityStateDefinition] = Field(
        min_length=7,
        max_length=7,
    )
    source_quarantine_manifest_hash: str
    partition_reset_required: Literal[True] = True
    defect_reset_required: Literal[True] = True
    no_synthetic_minute_permitted: Literal[True] = True
    no_cross_partition_rolling_state: Literal[True] = True
    official_kline_feature_authority: Literal[False] = False
    exact_pine_signal_supported: Literal[False] = False
    future_order_earliest_time: Literal[
        "NEXT_MINUTE_AFTER_EVALUATION_CLOSE_IF_LATER_GATES_PASS"
    ] = "NEXT_MINUTE_AFTER_EVALUATION_CLOSE_IF_LATER_GATES_PASS"
    evidence_partitions: list[JamQualityEvidencePartition] = Field(
        min_length=3,
        max_length=3,
    )
    conformance_cases: list[JamSyntheticConformanceCase] = Field(
        min_length=9,
        max_length=9,
    )
    conformance_manifest_hash: str
    real_market_rows_inspected: Literal[0] = 0
    future_labels_defined: list[str] = Field(default_factory=list)
    decision_thresholds_defined: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)
    strategy_executions: Literal[0] = 0
    creates_strategy: Literal[False] = False
    creates_signal: Literal[False] = False
    creates_candidate: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_testnet_order_authority: Literal[False] = False
    creates_production_authority: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    decision: Literal[
        "PASS_CAUSAL_FEATURE_SPECIFICATION_AWAIT_DEVELOPMENT_DISTRIBUTION_AUTHORIZATION"
    ] = JAM_FEATURE_PASS_DECISION
    next_required_authorization: Literal[
        "AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_FEATURE_DISTRIBUTION_NO_RETURNS"
    ] = JAM_FEATURE_NEXT_AUTHORIZATION
    limitations: list[str] = Field(min_length=14)
    specification_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "specification_contract_hash",
        "source_quarantine_manifest_hash",
        "conformance_manifest_hash",
        "specification_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "future_labels_defined",
        "decision_thresholds_defined",
        "return_metrics_calculated",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_specification(self) -> JamSuccessorFeatureSpecification:
        if (
            tuple(item.phase_id for item in self.phases)
            != JAM_FEATURE_PHASE_IDS
            or tuple(item.feature_id for item in self.features)
            != JAM_FEATURE_IDS
            or tuple(item.state for item in self.quality_states)
            != JAM_FEATURE_QUALITY_STATES
            or self.evidence_partitions != frozen_feature_partitions()
            or [item.case_id for item in self.conformance_cases]
            != sorted(item.case_id for item in self.conformance_cases)
        ):
            raise ValueError("Jam feature specification matrix changed")
        occupied_lags = [
            lag
            for phase in self.phases
            for lag in range(
                phase.newest_lag_minutes,
                phase.oldest_lag_minutes + 1,
            )
        ]
        if sorted(occupied_lags) != list(range(133)):
            raise ValueError("Jam feature temporal phases overlap or leave a gap")
        if any(
            (
                self.future_labels_defined,
                self.decision_thresholds_defined,
                self.return_metrics_calculated,
            )
        ):
            raise ValueError("Jam feature specification may contain no outcomes")
        case_payload = [item.model_dump() for item in self.conformance_cases]
        if self.conformance_manifest_hash != universe_evidence_hash(
            {"cases": case_payload}
        ):
            raise ValueError("Jam feature conformance manifest changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"specification_evidence_hash"})
        )
        if self.specification_evidence_hash != expected_hash:
            raise ValueError("Jam feature specification hash does not match")
        return self


class JamSuccessorFeatureSpecificationAudit(BaseModel):
    schema_version: Literal[
        "aurex-jam-successor-feature-specification-audit-v1"
    ] = JAM_FEATURE_AUDIT_SCHEMA_VERSION
    audited_at: datetime
    protocol_path: str
    protocol_file_sha256: str
    protocol_evidence_hash: str
    specification_path: str
    specification_file_sha256: str
    specification_evidence_hash: str
    specification_contract_hash: str
    conformance_case_count_reconstructed: Literal[9] = 9
    conformance_manifest_hash: str
    real_market_rows_inspected: Literal[0] = 0
    return_metrics_calculated: Literal[False] = False
    decision: Literal[
        "PASS_CAUSAL_FEATURE_SPECIFICATION_AWAIT_DEVELOPMENT_DISTRIBUTION_AUTHORIZATION"
    ] = JAM_FEATURE_PASS_DECISION
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "specification_file_sha256",
        "specification_evidence_hash",
        "specification_contract_hash",
        "conformance_manifest_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> JamSuccessorFeatureSpecificationAudit:
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected_hash:
            raise ValueError("Jam feature specification audit hash changed")
        return self


def feature_phases() -> list[JamFeatureTemporalPhase]:
    return [
        JamFeatureTemporalPhase(
            phase_id="BASELINE",
            oldest_lag_minutes=132,
            newest_lag_minutes=13,
            minute_count=120,
            purpose="Robust pre-event flow and imbalance normalization.",
        ),
        JamFeatureTemporalPhase(
            phase_id="PRE_SHOCK_REFERENCE",
            oldest_lag_minutes=12,
            newest_lag_minutes=8,
            minute_count=5,
            purpose="Causal pre-shock volume-weighted price reference.",
        ),
        JamFeatureTemporalPhase(
            phase_id="SHOCK",
            oldest_lag_minutes=7,
            newest_lag_minutes=3,
            minute_count=5,
            purpose="Candidate sell-flow shock and contemporaneous price impact.",
        ),
        JamFeatureTemporalPhase(
            phase_id="CONFIRMATION",
            oldest_lag_minutes=2,
            newest_lag_minutes=0,
            minute_count=3,
            purpose="Post-shock flow decay and price-reclaim confirmation.",
        ),
    ]


def feature_definitions() -> list[JamFeatureDefinition]:
    price_fields = ["close_price", "high_price", "low_price", "open_price"]
    return [
        JamFeatureDefinition(
            feature_id="baseline_sell_quote_median_120m",
            category="BASELINE",
            formula="MEDIAN(taker_sell_quote_volume per BASELINE minute)",
            source_fields=["taker_sell_quote_volume"],
            temporal_phases=["BASELINE"],
            units="QUOTE_ASSET",
            undefined_when=[],
        ),
        JamFeatureDefinition(
            feature_id="baseline_sell_quote_mad_120m",
            category="BASELINE",
            formula=(
                "MEDIAN(ABS(taker_sell_quote_volume - "
                "baseline_sell_quote_median_120m))"
            ),
            source_fields=["taker_sell_quote_volume"],
            temporal_phases=["BASELINE"],
            units="QUOTE_ASSET",
            undefined_when=[],
        ),
        JamFeatureDefinition(
            feature_id="baseline_sell_share_median_120m",
            category="BASELINE",
            formula=(
                "MEDIAN(taker_sell_quote_volume / quote_volume per BASELINE minute)"
            ),
            source_fields=["quote_volume", "taker_sell_quote_volume"],
            temporal_phases=["BASELINE"],
            units="RATIO",
            undefined_when=["ANY_BASELINE_QUOTE_VOLUME_IS_ZERO"],
        ),
        JamFeatureDefinition(
            feature_id="baseline_sell_share_mad_120m",
            category="BASELINE",
            formula=(
                "MEDIAN(ABS(sell_share - baseline_sell_share_median_120m))"
            ),
            source_fields=["quote_volume", "taker_sell_quote_volume"],
            temporal_phases=["BASELINE"],
            units="RATIO",
            undefined_when=["ANY_BASELINE_QUOTE_VOLUME_IS_ZERO"],
        ),
        JamFeatureDefinition(
            feature_id="pre_shock_vwap_5m",
            category="REFERENCE",
            formula="SUM(quote_volume) / SUM(base_volume)",
            source_fields=["base_volume", "quote_volume"],
            temporal_phases=["PRE_SHOCK_REFERENCE"],
            units="PRICE",
            undefined_when=["PRE_SHOCK_BASE_VOLUME_IS_ZERO"],
        ),
        JamFeatureDefinition(
            feature_id="shock_sell_quote_mean_5m",
            category="SHOCK",
            formula="SUM(taker_sell_quote_volume) / 5",
            source_fields=["taker_sell_quote_volume"],
            temporal_phases=["SHOCK"],
            units="QUOTE_ASSET",
            undefined_when=[],
        ),
        JamFeatureDefinition(
            feature_id="shock_sell_flow_robust_z_5m",
            category="SHOCK",
            formula=(
                "(shock_sell_quote_mean_5m - baseline_sell_quote_median_120m) "
                "/ (1.4826 * baseline_sell_quote_mad_120m)"
            ),
            source_fields=["taker_sell_quote_volume"],
            temporal_phases=["BASELINE", "SHOCK"],
            units="ROBUST_Z",
            undefined_when=["BASELINE_SELL_QUOTE_MAD_IS_ZERO"],
        ),
        JamFeatureDefinition(
            feature_id="shock_sell_share_5m",
            category="SHOCK",
            formula="SUM(taker_sell_quote_volume) / SUM(quote_volume)",
            source_fields=["quote_volume", "taker_sell_quote_volume"],
            temporal_phases=["SHOCK"],
            units="RATIO",
            undefined_when=["SHOCK_QUOTE_VOLUME_IS_ZERO"],
        ),
        JamFeatureDefinition(
            feature_id="shock_price_impact_bps_5m",
            category="SHOCK",
            formula=(
                "10000 * (SHOCK final close_price / pre_shock_vwap_5m - 1)"
            ),
            source_fields=price_fields,
            temporal_phases=["PRE_SHOCK_REFERENCE", "SHOCK"],
            units="BASIS_POINTS",
            undefined_when=["PRE_SHOCK_VWAP_IS_ZERO"],
        ),
        JamFeatureDefinition(
            feature_id="shock_low_bps_vs_pre_shock_vwap",
            category="SHOCK",
            formula=(
                "10000 * (MIN(SHOCK low_price) / pre_shock_vwap_5m - 1)"
            ),
            source_fields=price_fields,
            temporal_phases=["PRE_SHOCK_REFERENCE", "SHOCK"],
            units="BASIS_POINTS",
            undefined_when=["PRE_SHOCK_VWAP_IS_ZERO"],
        ),
        JamFeatureDefinition(
            feature_id="confirmation_sell_quote_mean_3m",
            category="CONFIRMATION",
            formula="SUM(taker_sell_quote_volume) / 3",
            source_fields=["taker_sell_quote_volume"],
            temporal_phases=["CONFIRMATION"],
            units="QUOTE_ASSET",
            undefined_when=[],
        ),
        JamFeatureDefinition(
            feature_id="confirmation_sell_flow_robust_z_3m",
            category="CONFIRMATION",
            formula=(
                "(confirmation_sell_quote_mean_3m - "
                "baseline_sell_quote_median_120m) / "
                "(1.4826 * baseline_sell_quote_mad_120m)"
            ),
            source_fields=["taker_sell_quote_volume"],
            temporal_phases=["BASELINE", "CONFIRMATION"],
            units="ROBUST_Z",
            undefined_when=["BASELINE_SELL_QUOTE_MAD_IS_ZERO"],
        ),
        JamFeatureDefinition(
            feature_id="confirmation_sell_share_3m",
            category="CONFIRMATION",
            formula="SUM(taker_sell_quote_volume) / SUM(quote_volume)",
            source_fields=["quote_volume", "taker_sell_quote_volume"],
            temporal_phases=["CONFIRMATION"],
            units="RATIO",
            undefined_when=["CONFIRMATION_QUOTE_VOLUME_IS_ZERO"],
        ),
        JamFeatureDefinition(
            feature_id="sell_flow_decay_ratio_3m_vs_5m",
            category="DECAY",
            formula=(
                "confirmation_sell_quote_mean_3m / shock_sell_quote_mean_5m"
            ),
            source_fields=["taker_sell_quote_volume"],
            temporal_phases=["SHOCK", "CONFIRMATION"],
            units="RATIO",
            undefined_when=["SHOCK_SELL_QUOTE_MEAN_IS_ZERO"],
        ),
        JamFeatureDefinition(
            feature_id="sell_share_decay_delta_5m_to_3m",
            category="DECAY",
            formula="shock_sell_share_5m - confirmation_sell_share_3m",
            source_fields=["quote_volume", "taker_sell_quote_volume"],
            temporal_phases=["SHOCK", "CONFIRMATION"],
            units="RATIO",
            undefined_when=[
                "CONFIRMATION_QUOTE_VOLUME_IS_ZERO",
                "SHOCK_QUOTE_VOLUME_IS_ZERO",
            ],
        ),
        JamFeatureDefinition(
            feature_id="reclaim_bps_vs_pre_shock_vwap",
            category="RECLAIM",
            formula=(
                "10000 * (CONFIRMATION final close_price / "
                "pre_shock_vwap_5m - 1)"
            ),
            source_fields=price_fields,
            temporal_phases=["PRE_SHOCK_REFERENCE", "CONFIRMATION"],
            units="BASIS_POINTS",
            undefined_when=["PRE_SHOCK_VWAP_IS_ZERO"],
        ),
        JamFeatureDefinition(
            feature_id="bounce_bps_from_shock_low",
            category="RECLAIM",
            formula=(
                "10000 * (CONFIRMATION final close_price / "
                "MIN(SHOCK low_price) - 1)"
            ),
            source_fields=price_fields,
            temporal_phases=["SHOCK", "CONFIRMATION"],
            units="BASIS_POINTS",
            undefined_when=["SHOCK_LOW_IS_ZERO"],
        ),
    ]


def quality_state_definitions() -> list[JamFeatureQualityStateDefinition]:
    return [
        JamFeatureQualityStateDefinition(
            state="READY",
            feature_values_permitted=True,
            resets_state=False,
            description="All 133 required minutes are valid and causal.",
        ),
        JamFeatureQualityStateDefinition(
            state="PARTITION_RESET_WARMUP",
            feature_values_permitted=False,
            resets_state=True,
            description=(
                "The active evidence partition contains fewer than 133 completed "
                "valid minutes."
            ),
        ),
        JamFeatureQualityStateDefinition(
            state="SOURCE_QUARANTINE",
            feature_values_permitted=False,
            resets_state=True,
            description="The evaluation minute is in the frozen quarantine.",
        ),
        JamFeatureQualityStateDefinition(
            state="POST_DEFECT_WARMUP",
            feature_values_permitted=False,
            resets_state=True,
            description=(
                "A quarantined or absent source minute remains inside the required "
                "133-minute causal window."
            ),
        ),
        JamFeatureQualityStateDefinition(
            state="NO_AGGTRADE_MINUTE",
            feature_values_permitted=False,
            resets_state=True,
            description=(
                "The evaluation minute has no aggregate trade and is not "
                "synthesized from klines or prior price."
            ),
        ),
        JamFeatureQualityStateDefinition(
            state="DEGENERATE_ROBUST_SCALE",
            feature_values_permitted=False,
            resets_state=False,
            description="The 120-minute sell-quote MAD is zero.",
        ),
        JamFeatureQualityStateDefinition(
            state="DEGENERATE_DENOMINATOR",
            feature_values_permitted=False,
            resets_state=False,
            description="A required causal volume or price denominator is zero.",
        ),
    ]


def aggregate_fixture_trades(
    trades: list[JamAggTradeFixture],
) -> list[JamFeatureMinute]:
    if not trades:
        return []
    previous_agg_id: int | None = None
    previous_last_trade_id: int | None = None
    previous_timestamp: int | None = None
    grouped: dict[int, list[JamAggTradeFixture]] = {}
    for trade in trades:
        if (
            previous_agg_id is not None
            and trade.aggregate_trade_id != previous_agg_id + 1
        ):
            raise ValueError("Jam synthetic aggregate IDs must be contiguous")
        if (
            previous_last_trade_id is not None
            and trade.first_trade_id != previous_last_trade_id + 1
        ):
            raise ValueError("Jam synthetic raw-trade spans must be contiguous")
        if (
            previous_timestamp is not None
            and trade.transact_time_ms < previous_timestamp
        ):
            raise ValueError("Jam synthetic timestamps must be monotonic")
        minute = trade.transact_time_ms // 60_000 * 60_000
        grouped.setdefault(minute, []).append(trade)
        previous_agg_id = trade.aggregate_trade_id
        previous_last_trade_id = trade.last_trade_id
        previous_timestamp = trade.transact_time_ms
    minutes = []
    for open_time, minute_trades in grouped.items():
        prices = [item.price for item in minute_trades]
        base_volume = sum(
            (item.quantity for item in minute_trades),
            Decimal(0),
        )
        quote_values = [item.price * item.quantity for item in minute_trades]
        quote_volume = sum(quote_values, Decimal(0))
        taker_buy_quote = sum(
            (
                quote
                for item, quote in zip(minute_trades, quote_values, strict=True)
                if not item.is_buyer_maker
            ),
            Decimal(0),
        )
        taker_sell_quote = sum(
            (
                quote
                for item, quote in zip(minute_trades, quote_values, strict=True)
                if item.is_buyer_maker
            ),
            Decimal(0),
        )
        minutes.append(
            JamFeatureMinute(
                open_time_ms=open_time,
                open_price=prices[0],
                high_price=max(prices),
                low_price=min(prices),
                close_price=prices[-1],
                base_volume=base_volume,
                quote_volume=quote_volume,
                taker_buy_quote_volume=taker_buy_quote,
                taker_sell_quote_volume=taker_sell_quote,
                raw_trade_count=sum(
                    item.last_trade_id - item.first_trade_id + 1
                    for item in minute_trades
                ),
            )
        )
    return minutes


def compute_feature_row(
    *,
    minutes: list[JamFeatureMinute],
    evaluation_open_time_ms: int,
    partition_start_ms: int,
    quarantined_open_times: set[int] | None = None,
) -> JamComputedFeatureRow:
    quarantine = quarantined_open_times or set()
    lookup = {item.open_time_ms: item for item in minutes}
    if len(lookup) != len(minutes):
        raise ValueError("Jam feature input minute duplicated")
    if evaluation_open_time_ms in quarantine:
        return JamComputedFeatureRow(
            evaluation_open_time_ms=evaluation_open_time_ms,
            quality_state="SOURCE_QUARANTINE",
            feature_values={},
        )
    if evaluation_open_time_ms not in lookup:
        return JamComputedFeatureRow(
            evaluation_open_time_ms=evaluation_open_time_ms,
            quality_state="NO_AGGTRADE_MINUTE",
            feature_values={},
        )
    earliest_required = evaluation_open_time_ms - 132 * 60_000
    if earliest_required < partition_start_ms:
        return JamComputedFeatureRow(
            evaluation_open_time_ms=evaluation_open_time_ms,
            quality_state="PARTITION_RESET_WARMUP",
            feature_values={},
        )
    required_times = [
        earliest_required + index * 60_000 for index in range(133)
    ]
    if any(
        timestamp in quarantine or timestamp not in lookup
        for timestamp in required_times
    ):
        return JamComputedFeatureRow(
            evaluation_open_time_ms=evaluation_open_time_ms,
            quality_state="POST_DEFECT_WARMUP",
            feature_values={},
        )
    ordered = [lookup[timestamp] for timestamp in required_times]
    baseline = ordered[0:120]
    pre_shock = ordered[120:125]
    shock = ordered[125:130]
    confirmation = ordered[130:133]
    baseline_sell_quote = [
        item.taker_sell_quote_volume for item in baseline
    ]
    baseline_sell_share = [item.sell_share for item in baseline]
    sell_quote_median = _median(baseline_sell_quote)
    sell_quote_mad = _mad(baseline_sell_quote, sell_quote_median)
    sell_share_median = _median(baseline_sell_share)
    sell_share_mad = _mad(baseline_sell_share, sell_share_median)
    if sell_quote_mad == 0:
        return JamComputedFeatureRow(
            evaluation_open_time_ms=evaluation_open_time_ms,
            quality_state="DEGENERATE_ROBUST_SCALE",
            feature_values={},
        )
    pre_base = sum((item.base_volume for item in pre_shock), Decimal(0))
    pre_quote = sum((item.quote_volume for item in pre_shock), Decimal(0))
    shock_quote = sum((item.quote_volume for item in shock), Decimal(0))
    confirmation_quote = sum(
        (item.quote_volume for item in confirmation),
        Decimal(0),
    )
    shock_sell_mean = sum(
        (item.taker_sell_quote_volume for item in shock),
        Decimal(0),
    ) / Decimal(5)
    confirmation_sell_mean = sum(
        (item.taker_sell_quote_volume for item in confirmation),
        Decimal(0),
    ) / Decimal(3)
    shock_low = min(item.low_price for item in shock)
    if (
        pre_base == 0
        or shock_quote == 0
        or confirmation_quote == 0
        or shock_sell_mean == 0
        or shock_low == 0
    ):
        return JamComputedFeatureRow(
            evaluation_open_time_ms=evaluation_open_time_ms,
            quality_state="DEGENERATE_DENOMINATOR",
            feature_values={},
        )
    pre_vwap = pre_quote / pre_base
    robust_scale = Decimal(JAM_FEATURE_ROBUST_SCALE_CONSTANT) * sell_quote_mad
    shock_sell_share = sum(
        (item.taker_sell_quote_volume for item in shock),
        Decimal(0),
    ) / shock_quote
    confirmation_sell_share = sum(
        (item.taker_sell_quote_volume for item in confirmation),
        Decimal(0),
    ) / confirmation_quote
    bps = Decimal(JAM_FEATURE_BPS_CONSTANT)
    one = Decimal(1)
    values = {
        "baseline_sell_quote_median_120m": sell_quote_median,
        "baseline_sell_quote_mad_120m": sell_quote_mad,
        "baseline_sell_share_median_120m": sell_share_median,
        "baseline_sell_share_mad_120m": sell_share_mad,
        "pre_shock_vwap_5m": pre_vwap,
        "shock_sell_quote_mean_5m": shock_sell_mean,
        "shock_sell_flow_robust_z_5m": (
            shock_sell_mean - sell_quote_median
        )
        / robust_scale,
        "shock_sell_share_5m": shock_sell_share,
        "shock_price_impact_bps_5m": (
            shock[-1].close_price / pre_vwap - one
        )
        * bps,
        "shock_low_bps_vs_pre_shock_vwap": (
            shock_low / pre_vwap - one
        )
        * bps,
        "confirmation_sell_quote_mean_3m": confirmation_sell_mean,
        "confirmation_sell_flow_robust_z_3m": (
            confirmation_sell_mean - sell_quote_median
        )
        / robust_scale,
        "confirmation_sell_share_3m": confirmation_sell_share,
        "sell_flow_decay_ratio_3m_vs_5m": (
            confirmation_sell_mean / shock_sell_mean
        ),
        "sell_share_decay_delta_5m_to_3m": (
            shock_sell_share - confirmation_sell_share
        ),
        "reclaim_bps_vs_pre_shock_vwap": (
            confirmation[-1].close_price / pre_vwap - one
        )
        * bps,
        "bounce_bps_from_shock_low": (
            confirmation[-1].close_price / shock_low - one
        )
        * bps,
    }
    return JamComputedFeatureRow(
        evaluation_open_time_ms=evaluation_open_time_ms,
        quality_state="READY",
        feature_values={key: _quantize(value) for key, value in values.items()},
    )


def build_conformance_case(
    *,
    case_id: str,
    assertion: str,
    synthetic_row_count: int,
    observed_state: str,
) -> JamSyntheticConformanceCase:
    payload = {
        "case_id": case_id,
        "assertion": assertion,
        "passed": True,
        "synthetic_row_count": synthetic_row_count,
        "observed_state": observed_state,
    }
    return JamSyntheticConformanceCase(
        **payload,
        case_evidence_hash=universe_evidence_hash(payload),
    )


def build_jam_successor_feature_specification(
    **values,
) -> JamSuccessorFeatureSpecification:
    conformance = sorted(
        values.pop("conformance_cases"),
        key=lambda item: item.case_id,
    )
    payload = {
        "schema_version": JAM_FEATURE_SPEC_SCHEMA_VERSION,
        "specification_id": JAM_FEATURE_SPEC_ID,
        "status": "FROZEN_CAUSAL_SPECIFICATION_NO_RETURNS",
        "protocol_path": (
            "data/evidence/jam_successor_feature_specification_protocol_v1.json"
        ),
        "selected_proposal_id": (
            "J2-P01-AGGRESSIVE-SELL-FLOW-EXHAUSTION-RECLAIM"
        ),
        "source_grain": "UTC_ONE_MINUTE_FROM_AGGTRADES",
        "timestamp_normalization": (
            "MILLISECONDS_13_DIGITS_OR_MICROSECONDS_16_DIGITS_FLOORED_TO_MILLISECONDS"
        ),
        "buyer_maker_true_mapping": "SELLER_WAS_TAKER_TAKER_SELL",
        "buyer_maker_false_mapping": "BUYER_WAS_TAKER_TAKER_BUY",
        "minute_quote_notional_formula": (
            "SUM_PRICE_MULTIPLIED_BY_QUANTITY"
        ),
        "phases": feature_phases(),
        "features": feature_definitions(),
        "feature_count": 17,
        "maximum_lookback_minutes": JAM_FEATURE_MAXIMUM_LOOKBACK_MINUTES,
        "minimum_consecutive_valid_minutes": (
            JAM_FEATURE_MAXIMUM_LOOKBACK_MINUTES
        ),
        "robust_scale_constant": JAM_FEATURE_ROBUST_SCALE_CONSTANT,
        "basis_points_constant": JAM_FEATURE_BPS_CONSTANT,
        "output_decimal_places": JAM_FEATURE_OUTPUT_DECIMAL_PLACES,
        "output_rounding": "ROUND_HALF_EVEN",
        "quality_states": quality_state_definitions(),
        "partition_reset_required": True,
        "defect_reset_required": True,
        "no_synthetic_minute_permitted": True,
        "no_cross_partition_rolling_state": True,
        "official_kline_feature_authority": False,
        "exact_pine_signal_supported": False,
        "future_order_earliest_time": (
            "NEXT_MINUTE_AFTER_EVALUATION_CLOSE_IF_LATER_GATES_PASS"
        ),
        "evidence_partitions": frozen_feature_partitions(),
        "conformance_cases": conformance,
        "conformance_manifest_hash": universe_evidence_hash(
            {"cases": [item.model_dump() for item in conformance]}
        ),
        "real_market_rows_inspected": 0,
        "future_labels_defined": [],
        "decision_thresholds_defined": [],
        "return_metrics_calculated": [],
        "strategy_executions": 0,
        "creates_strategy": False,
        "creates_signal": False,
        "creates_candidate": False,
        "creates_paper_eligibility": False,
        "creates_testnet_order_authority": False,
        "creates_production_authority": False,
        "creates_live_eligibility": False,
        "decision": JAM_FEATURE_PASS_DECISION,
        "next_required_authorization": JAM_FEATURE_NEXT_AUTHORIZATION,
        **values,
    }
    payload["limitations"] = sorted(set(payload["limitations"]))
    return JamSuccessorFeatureSpecification(
        **payload,
        specification_evidence_hash=universe_evidence_hash(payload),
    )


def build_jam_successor_feature_audit(
    **values,
) -> JamSuccessorFeatureSpecificationAudit:
    payload = {
        "schema_version": JAM_FEATURE_AUDIT_SCHEMA_VERSION,
        "conformance_case_count_reconstructed": 9,
        "real_market_rows_inspected": 0,
        "return_metrics_calculated": False,
        "decision": JAM_FEATURE_PASS_DECISION,
        **values,
    }
    return JamSuccessorFeatureSpecificationAudit(
        **payload,
        audit_evidence_hash=universe_evidence_hash(payload),
    )


def audit_jam_successor_feature_specification(
    specification: JamSuccessorFeatureSpecification,
) -> bool:
    try:
        JamSuccessorFeatureSpecification.model_validate(
            specification.model_dump()
        )
    except ValueError:
        return False
    return True


def audit_jam_successor_feature_audit(
    audit: JamSuccessorFeatureSpecificationAudit,
) -> bool:
    try:
        JamSuccessorFeatureSpecificationAudit.model_validate(audit.model_dump())
    except ValueError:
        return False
    return True
