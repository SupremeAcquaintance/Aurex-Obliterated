from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.domain.enums import BacktestStatus, Direction

TimestampUnit = Literal["seconds", "milliseconds", "microseconds", "nanoseconds", "iso8601"]
OhlcvContinuity = Literal[
    "continuous_24_7",
    "continuous_24_7_with_documented_outages",
    "session_based",
]


class OhlcvCandle(BaseModel):
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


class OhlcvSourceArtifact(BaseModel):
    uri: str = Field(min_length=1, max_length=2000)
    filename: str = Field(min_length=1, max_length=255)
    sha256: str
    size_bytes: int = Field(gt=0)
    checksum_uri: str | None = Field(default=None, max_length=2000)
    checksum_file_sha256: str | None = None
    expected_sha256: str | None = None
    archive_member: str | None = Field(default=None, max_length=255)
    checksum_verified: bool = False
    timestamp_units: list[TimestampUnit] | None = Field(
        default=None,
        min_length=1,
        max_length=5,
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("sha256", "checksum_file_sha256", "expected_sha256")
    @classmethod
    def validate_sha256(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
            raise ValueError("SHA-256 values must contain exactly 64 hexadecimal characters")
        return normalized

    @model_validator(mode="after")
    def validate_checksum_evidence(self) -> "OhlcvSourceArtifact":
        if not self.checksum_verified:
            return self
        if self.expected_sha256 is None or self.sha256 != self.expected_sha256:
            raise ValueError("Verified source artifact checksum must match its expected SHA-256")
        if self.checksum_uri is None or self.checksum_file_sha256 is None:
            raise ValueError(
                "Verified source artifact requires checksum URI and checksum-file hash"
            )
        return self


class OhlcvTransformationEvidence(BaseModel):
    tool: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=64)
    input_format: str = Field(min_length=1, max_length=200)
    timestamp_unit: TimestampUnit | Literal["mixed"]
    timestamp_units: list[TimestampUnit] | None = Field(
        default=None,
        min_length=1,
        max_length=5,
    )
    output_schema: Literal["aurex_ohlcv_v1"] = "aurex_ohlcv_v1"

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_timestamp_units(self) -> "OhlcvTransformationEvidence":
        units = self.timestamp_units
        if units is not None and len(set(units)) != len(units):
            raise ValueError("Transformation timestamp units must be unique")
        if self.timestamp_unit == "mixed":
            if units is None or len(units) < 2:
                raise ValueError("Mixed timestamp evidence requires at least two units")
        elif units is not None and units != [self.timestamp_unit]:
            raise ValueError(
                "Single timestamp-unit evidence must match the declared timestamp unit"
            )
        return self


class OhlcvDocumentedGap(BaseModel):
    start: datetime
    end: datetime
    reason: str = Field(min_length=10, max_length=500)
    source_reference: str = Field(min_length=1, max_length=2000)
    source_title: str | None = Field(default=None, min_length=1, max_length=200)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_documented_gap(self) -> "OhlcvDocumentedGap":
        if self.start.utcoffset() is None or self.end.utcoffset() is None:
            raise ValueError("Documented outage timestamps must include a timezone")
        self.start = self.start.astimezone(UTC)
        self.end = self.end.astimezone(UTC)
        if self.end <= self.start:
            raise ValueError("Documented outage end must be later than its start")
        self.reason = self.reason.strip()
        self.source_reference = self.source_reference.strip()
        if not self.reason or not self.source_reference:
            raise ValueError("Documented outage reason and source reference are required")
        if self.source_title is not None:
            self.source_title = self.source_title.strip()
            if not self.source_title:
                raise ValueError("Documented outage source title cannot be blank")
        return self


class OhlcvDatasetCsvRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    timeframe: str = Field(min_length=1, max_length=32)
    source: str = Field(default="tradingview-chart-export", min_length=1, max_length=100)
    source_reference: str = Field(min_length=1, max_length=1000)
    csv_timezone: str = Field(default="UTC", min_length=1, max_length=64)
    continuity: OhlcvContinuity = "continuous_24_7"
    documented_gaps: list[OhlcvDocumentedGap] = Field(default_factory=list, max_length=100)
    source_artifacts: list[OhlcvSourceArtifact] = Field(default_factory=list, max_length=100)
    transformation: OhlcvTransformationEvidence | None = None
    csv_text: str = Field(min_length=1)

    @model_validator(mode="after")
    def require_binance_vision_provenance(self) -> "OhlcvDatasetCsvRequest":
        documented_policy = self.continuity == "continuous_24_7_with_documented_outages"
        if documented_policy and not self.documented_gaps:
            raise ValueError("Documented-outage continuity requires outage evidence")
        if not documented_policy and self.documented_gaps:
            raise ValueError(
                "Documented outage evidence requires documented-outage continuity"
            )
        gap_windows = {(gap.start, gap.end) for gap in self.documented_gaps}
        if len(gap_windows) != len(self.documented_gaps):
            raise ValueError("Documented outage windows must be unique")
        ordered_gaps = sorted(self.documented_gaps, key=lambda gap: (gap.start, gap.end))
        if any(
            current.start < previous.end
            for previous, current in zip(ordered_gaps, ordered_gaps[1:], strict=False)
        ):
            raise ValueError("Documented outage windows must not overlap")
        if self.source.strip().lower() != "binance-vision":
            return self
        if not self.source_artifacts:
            raise ValueError("Binance Vision datasets require source artifact evidence")
        if not all(artifact.checksum_verified for artifact in self.source_artifacts):
            raise ValueError("Every Binance Vision source artifact checksum must be verified")
        if self.transformation is None:
            raise ValueError("Binance Vision datasets require transformation evidence")
        return self


class OhlcvDatasetPreflightResponse(BaseModel):
    status: str
    symbol: str
    timeframe: str
    source: str
    source_reference: str
    csv_timezone: str
    continuity: str
    evidence_hash: str | None
    canonical_csv_sha256: str
    source_artifact_bundle_hash: str | None
    source_artifacts_verified: bool
    rows_received: int
    valid_rows: int
    rejected_rows: int
    data_start: datetime | None
    data_end: datetime | None
    expected_interval_seconds: int
    canonical_order: str
    gap_count: int
    missing_interval_count: int
    documented_gap_count: int
    undocumented_gap_count: int
    duplicate_count: int
    interval_mismatch_count: int
    warnings: list[str]
    rejection_reasons: list[str]
    row_errors: list[dict]
    quality_snapshot: dict
    checked_at: datetime
    mutates_ledger: bool = False


class OhlcvDatasetResponse(BaseModel):
    id: str
    symbol: str
    timeframe: str
    source: str
    source_reference: str
    csv_timezone: str
    continuity: str
    data_start: datetime
    data_end: datetime
    row_count: int
    evidence_hash: str
    canonical_csv_sha256: str | None
    source_artifact_bundle_hash: str | None
    source_artifacts_verified: bool
    quality_snapshot: dict
    imported_at: datetime
    immutable: bool = True
    reused_existing: bool = False


class OhlcvDatasetAuditResponse(BaseModel):
    dataset_id: str
    status: str
    stored_evidence_hash: str
    current_evidence_hash: str
    evidence_hash_matches: bool
    stored_row_count: int
    current_row_count: int
    row_count_matches: bool
    reasons: list[str]
    checked_at: datetime


class ReferenceReplayRequest(BaseModel):
    dataset_id: str = Field(min_length=1, max_length=36)
    strategy: str = Field(default="trend_pullback_v1", min_length=1, max_length=100)
    strategy_version: str = Field(default="1.3.0", min_length=1, max_length=64)
    parameters: dict = Field(default_factory=dict)
    tick_size: Decimal = Field(gt=0)
    point_value: Decimal = Field(gt=0)
    minimum_contract: Decimal = Field(gt=0)
    commission_percent: Decimal = Field(default=Decimal("0.05"), ge=0)
    slippage_ticks: int = Field(default=2, ge=0, le=100)
    intrabar_policy: Literal["stop_first"] = "stop_first"


class ReferenceReplayTrade(BaseModel):
    sequence: int
    direction: Direction
    entry_at: datetime
    closed_at: datetime
    signal_price: Decimal
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal | None
    exit_price: Decimal
    quantity: Decimal
    gross_pl: Decimal
    fees: Decimal
    slippage: Decimal
    realized_pl: Decimal
    equity: Decimal
    r_multiple: Decimal
    market_regime: str
    exit_reason: str
    intrabar_ambiguous: bool = False


class ReferenceReplayResponse(BaseModel):
    id: str | None = None
    status: str
    engine_version: str
    strategy: str
    strategy_version: str
    dataset_id: str
    dataset_evidence_hash: str
    engine_evidence_hash: str | None
    comparison_only: bool = True
    acceptance_eligible: bool = False
    reasons: list[str]
    warnings: list[str]
    assumptions: dict
    diagnostics: dict
    metrics: dict
    trades: list[ReferenceReplayTrade]
    open_position: dict | None
    record_evidence_hash: str | None = None
    immutable: bool = False
    reused_existing: bool = False
    recorded_at: datetime | None = None
    checked_at: datetime
    mutates_ledger: bool = False


class ReferenceReplayAuditResponse(BaseModel):
    reference_replay_run_id: str
    status: str
    stored_record_evidence_hash: str
    current_record_evidence_hash: str
    stored_engine_evidence_hash: str
    replayed_engine_evidence_hash: str | None
    record_evidence_hash_matches: bool
    dataset_evidence_hash_matches: bool
    engine_evidence_hash_matches: bool
    result_snapshot_matches: bool
    reasons: list[str]
    checked_at: datetime


class ReferenceReplaySummaryResponse(BaseModel):
    id: str
    status: str
    engine_version: str
    strategy: str
    strategy_version: str
    dataset_id: str
    dataset_evidence_hash: str
    engine_evidence_hash: str
    record_evidence_hash: str
    metrics: dict
    diagnostics: dict
    reasons: list[str]
    warnings: list[str]
    comparison_only: bool = True
    acceptance_eligible: bool = False
    immutable: bool = True
    recorded_at: datetime
    mutates_ledger: bool = False


class ReferenceReplayValidationRequest(BaseModel):
    reference_replay_run_id: str = Field(min_length=1, max_length=36)
    protocol_id: str = Field(min_length=1, max_length=36)


class ReferenceReplayValidationResponse(BaseModel):
    id: str | None = None
    status: str
    evaluator_version: str
    reference_replay_run_id: str
    protocol_id: str
    dataset_id: str
    strategy: str
    strategy_version: str
    symbol: str
    timeframe: str
    replay_record_evidence_hash: str
    engine_evidence_hash: str
    dataset_evidence_hash: str
    protocol_hash: str
    trade_evidence_hash: str | None
    validation_evidence_hash: str | None
    metrics_snapshot: dict
    acceptance_snapshot: dict
    statistical_acceptance_passed: bool
    acceptance_reasons: list[str]
    binding_checks: list[dict]
    reasons: list[str]
    warnings: list[str]
    comparison_only: bool = True
    promotion_eligible: bool = False
    paper_eligible: bool = False
    immutable: bool = False
    reused_existing: bool = False
    recorded_at: datetime | None = None
    checked_at: datetime
    mutates_ledger: bool = False


class ReferenceReplayValidationAuditResponse(BaseModel):
    reference_replay_validation_id: str
    status: str
    stored_validation_evidence_hash: str
    current_validation_evidence_hash: str
    replayed_validation_evidence_hash: str | None
    record_evidence_hash_matches: bool
    source_evidence_matches: bool
    evaluation_matches: bool
    reasons: list[str]
    checked_at: datetime


class BacktestParityTolerances(BaseModel):
    entry_time_seconds: int = Field(default=0, ge=0, le=3600)
    exit_time_seconds: int = Field(default=0, ge=0, le=3600)
    price_ticks: int = Field(default=1, ge=0, le=10)
    quantity_relative: Decimal = Field(default=Decimal("0.000001"), ge=0, le=Decimal("0.01"))
    money_absolute: Decimal = Field(default=Decimal("0.01"), ge=0, le=Decimal("1"))


TRADINGVIEW_PAIRED_EXPORT_ATTESTATION = (
    "I attest that the selected TradingView chart CSV and Strategy Tester CSV "
    "were exported from the same run without changing the Pine source, inputs, "
    "Strategy Properties, symbol, timeframe, date range, costs, or order settings."
)


class TradingViewPairedExportAttestation(BaseModel):
    statement: str = Field(min_length=1, max_length=512)
    attested_at: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("statement")
    @classmethod
    def require_exact_statement(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if normalized != TRADINGVIEW_PAIRED_EXPORT_ATTESTATION:
            raise ValueError("TradingView paired-export attestation does not match")
        return normalized


class BacktestParityExportManifestRequest(BaseModel):
    dataset_id: str = Field(min_length=1, max_length=36)
    tradingview_chart_dataset_id: str = Field(min_length=1, max_length=36)
    tradingview_run_id: str = Field(min_length=1, max_length=36)
    export_attestation: TradingViewPairedExportAttestation

    model_config = ConfigDict(extra="forbid")


class BacktestParityExportManifestResponse(BaseModel):
    status: Literal["READY", "BLOCKED"]
    manifest_hash: str | None
    manifest: dict
    reasons: list[str]
    warnings: list[str]
    checked_at: datetime
    mutates_ledger: bool = False


class BacktestParityRequest(BaseModel):
    dataset_id: str = Field(min_length=1, max_length=36)
    tradingview_chart_dataset_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=36,
    )
    tradingview_run_id: str = Field(min_length=1, max_length=36)
    tick_size: Decimal = Field(gt=0)
    point_value: Decimal = Field(gt=0)
    minimum_contract: Decimal = Field(gt=0)
    tolerances: BacktestParityTolerances = Field(default_factory=BacktestParityTolerances)
    export_attestation: TradingViewPairedExportAttestation | None = None
    reviewed_export_manifest_hash: str | None = Field(
        default=None,
        pattern="^[0-9a-f]{64}$",
    )


class BacktestParityResponse(BaseModel):
    id: str | None = None
    status: str
    engine_version: str
    strategy: str
    strategy_version: str
    dataset_id: str
    dataset_evidence_hash: str
    tradingview_chart_dataset_id: str | None
    tradingview_chart_dataset_evidence_hash: str | None
    tradingview_run_id: str
    tradingview_evidence_hash: str
    replay_evidence_hash: str | None
    parity_evidence_hash: str | None
    request_snapshot: dict
    summary: dict
    mismatches: list[dict]
    market_data_summary: dict
    market_data_mismatches: list[dict]
    reasons: list[str]
    warnings: list[str]
    comparison_only: bool = True
    acceptance_eligible: bool = False
    immutable: bool = False
    reused_existing: bool = False
    recorded_at: datetime | None = None
    checked_at: datetime
    mutates_ledger: bool = False


class BacktestParityAuditResponse(BaseModel):
    parity_run_id: str
    status: str
    stored_evidence_hash: str
    current_evidence_hash: str | None
    replayed_evidence_hash: str | None
    evidence_hash_matches: bool
    replay_matches: bool
    reasons: list[str]
    checked_at: datetime


class BacktestPaperEligibilityResponse(BaseModel):
    approved: bool
    reason: str
    backtest_run_id: str | None
    evidence_snapshot: dict


class BacktestTradeInput(BaseModel):
    realized_pl: Decimal
    sequence: int | None = Field(default=None, ge=1)
    external_trade_id: str | None = Field(default=None, max_length=128)
    source_format: str = Field(default="aurex", min_length=1, max_length=32)
    symbol: str | None = Field(default=None, max_length=64)
    direction: Direction | None = None
    entry_at: datetime | None = None
    entry_price: Decimal | None = None
    exit_price: Decimal | None = None
    quantity: Decimal | None = None
    gross_pl: Decimal | None = None
    fees: Decimal | None = Field(default=None, ge=0)
    slippage: Decimal | None = Field(default=None, ge=0)
    equity: Decimal | None = None
    strategy: str | None = None
    market_regime: str | None = None
    r_multiple: Decimal | None = None
    closed_at: datetime | None = None
    raw_row: dict = Field(default_factory=dict)


class WalkForwardWindowInput(BaseModel):
    window_id: str = Field(min_length=1, max_length=64)
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    configuration_reference: str = Field(min_length=1, max_length=1000)
    parameters: dict = Field(default_factory=dict)


class WalkForwardPlanRequest(BaseModel):
    strategy: str = Field(min_length=1, max_length=100)
    in_sample_start: datetime
    in_sample_end: datetime
    parameters: dict = Field(default_factory=dict)
    window_count: int = Field(default=3, ge=2, le=12)
    initial_training_fraction: Decimal = Field(
        default=Decimal("0.333333"),
        gt=0,
        lt=1,
    )


class WalkForwardPlanResponse(BaseModel):
    status: str
    method: str
    strategy: str
    in_sample_start: datetime
    in_sample_end: datetime
    window_count: int
    initial_training_fraction: Decimal
    windows: list[WalkForwardWindowInput]
    plan_hash: str
    outcome_fields_inspected: list[str]
    warnings: list[str]
    next_actions: list[str]
    mutates_ledger: bool = False


class AcceptanceCriteria(BaseModel):
    min_trades: int = Field(default=100, ge=0)
    min_profit_factor: Decimal = Field(default=Decimal("1.15"), ge=0)
    require_positive_expectancy: bool = True
    max_drawdown: Decimal | None = Field(default=None, ge=0)
    require_sample_windows: bool = True
    require_out_of_sample_metrics: bool = True
    min_out_of_sample_trades: int = Field(default=30, ge=0)
    min_out_of_sample_profit_factor: Decimal = Field(default=Decimal("1.15"), ge=0)
    require_out_of_sample_positive_expectancy: bool = True
    require_cost_model: bool = True
    require_slippage_model: bool = True
    require_risk_snapshot: bool = True
    require_trade_dates: bool = True
    min_active_trading_days: int = Field(default=15, ge=0)
    max_single_day_trade_share: Decimal = Field(default=Decimal("0.25"), ge=0, le=1)
    require_market_regime_breakdown: bool = True
    require_walk_forward_validation: bool = True
    min_walk_forward_windows: int = Field(default=3, ge=1)
    min_walk_forward_trades_per_window: int = Field(default=10, ge=1)
    min_walk_forward_pass_rate: Decimal = Field(default=Decimal("0.66"), ge=0, le=1)
    require_cost_stress: bool = False
    cost_stress_multipliers: list[Decimal] = Field(
        default_factory=lambda: [Decimal("1.5"), Decimal("2.0")],
        min_length=1,
    )
    min_cost_stress_profit_factor: Decimal = Field(default=Decimal("1.0"), ge=0)
    require_cost_stress_positive_expectancy: bool = True
    require_uncertainty_bound: bool = False
    uncertainty_confidence: Decimal = Field(default=Decimal("0.95"), gt=0, lt=1)
    uncertainty_bootstrap_samples: int = Field(default=2000, ge=1000, le=20000)
    min_uncertainty_expectancy_lower_bound: Decimal = Decimal("0")
    require_multiple_testing_control: bool = False
    max_tested_variants: int = Field(default=12, ge=1)
    multiple_testing_profit_factor_step: Decimal = Field(
        default=Decimal("0.02"),
        ge=0,
    )
    max_multiple_testing_profit_factor_penalty: Decimal = Field(
        default=Decimal("0.25"),
        ge=0,
    )
    require_holdout_decision: bool = False
    min_holdout_trades: int = Field(default=30, ge=1)
    min_holdout_profit_factor: Decimal = Field(default=Decimal("1.15"), ge=0)
    require_holdout_positive_expectancy: bool = True


class BacktestProtocolCreate(BaseModel):
    strategy: str = Field(min_length=1, max_length=100)
    strategy_version: str = Field(min_length=1, max_length=64)
    symbols: list[str] = Field(min_length=1)
    timeframe: str = Field(min_length=1, max_length=32)
    data_source: str = Field(min_length=1, max_length=100)
    csv_timezone: str = Field(default="UTC", min_length=1, max_length=64)
    source_reference: str = Field(min_length=1, max_length=1000)
    data_start: datetime
    data_end: datetime
    in_sample_start: datetime
    in_sample_end: datetime
    out_of_sample_start: datetime
    out_of_sample_end: datetime
    holdout_start: datetime | None = None
    holdout_end: datetime | None = None
    tested_variant_count: int = Field(default=1, ge=1)
    variant_registry_hash: str | None = Field(default=None, pattern="^[0-9a-f]{64}$")
    parameters: dict = Field(default_factory=dict)
    cost_model: dict = Field(default_factory=dict)
    slippage_model: dict = Field(default_factory=dict)
    risk_snapshot: dict = Field(default_factory=dict)
    walk_forward_windows: list[WalkForwardWindowInput] = Field(default_factory=list)
    acceptance_criteria: AcceptanceCriteria = Field(default_factory=AcceptanceCriteria)


class BacktestProtocolResponse(BaseModel):
    id: str
    strategy: str
    strategy_version: str
    symbols: list[str]
    timeframe: str
    protocol_hash: str
    protocol_snapshot: dict
    registered_at: datetime
    status: str
    consumed_by_run_id: str | None
    immutable: bool = True


class BacktestRunManifestResponse(BaseModel):
    status: Literal["READY", "BLOCKED"]
    protocol_id: str
    protocol_hash: str
    manifest_hash: str
    strategy: str
    strategy_version: str
    symbol: str | None
    timeframe: str
    registered_at: datetime
    protocol_status: str
    source_evidence: dict
    settings_fingerprint: str | None
    tradingview_setup: dict
    checks: list[dict]
    reasons: list[str]
    warnings: list[str]
    next_actions: list[str]
    mutates_ledger: bool = False


class BacktestTradingViewRunPackageResponse(BaseModel):
    status: Literal["READY", "BLOCKED"]
    protocol_id: str
    protocol_hash: str
    manifest_hash: str
    package_hash: str
    strategy: str
    strategy_version: str
    ticker_id: str | None
    timeframe: str
    pine_source: str | None
    pine_source_sha256: str | None
    source_byte_length: int | None
    source_line_count: int | None
    tradingview_url: str | None
    tradingview_setup: dict
    reasons: list[str]
    warnings: list[str]
    mutates_ledger: bool = False


class BacktestReportCreate(BaseModel):
    protocol_id: str | None = Field(default=None, max_length=36)
    strategy: str = Field(min_length=1, max_length=100)
    strategy_version: str = Field(min_length=1, max_length=64)
    symbols: list[str] = Field(min_length=1)
    timeframe: str = Field(min_length=1, max_length=32)
    data_source: str = Field(min_length=1, max_length=100)
    source_format: str = Field(default="aurex_json", min_length=1, max_length=32)
    source_artifact_hash: str | None = Field(
        default=None,
        pattern="^[0-9a-f]{64}$",
    )
    csv_timezone: str = Field(default="UTC", min_length=1, max_length=64)
    source_reference: str | None = Field(default=None, max_length=1000)
    data_start: datetime
    data_end: datetime
    in_sample_start: datetime | None = None
    in_sample_end: datetime | None = None
    out_of_sample_start: datetime | None = None
    out_of_sample_end: datetime | None = None
    holdout_start: datetime | None = None
    holdout_end: datetime | None = None
    tested_variant_count: int = Field(default=1, ge=1)
    variant_registry_hash: str | None = Field(default=None, pattern="^[0-9a-f]{64}$")
    parameters: dict = Field(default_factory=dict)
    cost_model: dict = Field(default_factory=dict)
    slippage_model: dict = Field(default_factory=dict)
    risk_snapshot: dict = Field(default_factory=dict)
    walk_forward_windows: list[WalkForwardWindowInput] = Field(default_factory=list)
    trades: list[BacktestTradeInput] = Field(default_factory=list)
    acceptance_criteria: AcceptanceCriteria = Field(default_factory=AcceptanceCriteria)


class BacktestReportCsvRequest(BaseModel):
    protocol_id: str | None = Field(default=None, max_length=36)
    strategy: str = Field(min_length=1, max_length=100)
    strategy_version: str = Field(min_length=1, max_length=64)
    symbols: list[str] = Field(min_length=1)
    timeframe: str = Field(min_length=1, max_length=32)
    data_source: str = Field(min_length=1, max_length=100)
    csv_format: str = Field(default="auto", pattern="^(auto|aurex|tradingview)$")
    csv_timezone: str = Field(default="UTC", min_length=1, max_length=64)
    source_reference: str | None = Field(default=None, max_length=1000)
    data_start: datetime
    data_end: datetime
    in_sample_start: datetime | None = None
    in_sample_end: datetime | None = None
    out_of_sample_start: datetime | None = None
    out_of_sample_end: datetime | None = None
    holdout_start: datetime | None = None
    holdout_end: datetime | None = None
    tested_variant_count: int = Field(default=1, ge=1)
    variant_registry_hash: str | None = Field(default=None, pattern="^[0-9a-f]{64}$")
    parameters: dict = Field(default_factory=dict)
    cost_model: dict = Field(default_factory=dict)
    slippage_model: dict = Field(default_factory=dict)
    risk_snapshot: dict = Field(default_factory=dict)
    walk_forward_windows: list[WalkForwardWindowInput] = Field(default_factory=list)
    acceptance_criteria: AcceptanceCriteria = Field(default_factory=AcceptanceCriteria)
    csv_text: str = Field(min_length=1)


class BacktestReportCsvPreflightResponse(BaseModel):
    status: str
    source_format: str
    source_artifact_hash: str
    evidence_hash: str
    rows_received: int
    importable_count: int
    rejected_count: int
    required_headers: list[str]
    row_results: list[dict]
    analysis_summary: dict
    checked_at: datetime


class BacktestStrategySetupResponse(BaseModel):
    strategy: str
    strategy_version: str
    display_name: str
    known_strategy: bool
    parameter_provenance_required: bool
    pine_path: str | None
    docs_path: str | None
    strategy_source_evidence: dict
    symbol: str
    venue: str
    ticker_id: str
    timeframe: str
    data_source: str
    csv_format: str
    csv_timezone: str
    source_reference: str
    parameters: dict
    settings_fingerprint: str | None
    required_parameters: list[str]
    cost_model: dict
    slippage_model: dict
    risk_snapshot: dict
    walk_forward_method: str
    walk_forward_windows: list[WalkForwardWindowInput]
    acceptance_criteria: AcceptanceCriteria
    next_actions: list[str]
    mutates_ledger: bool = False


class BacktestResultResponse(BaseModel):
    id: str
    total_trades: int
    wins: int
    losses: int
    breakeven: int
    win_rate: Decimal | None
    average_win: Decimal | None
    average_loss: Decimal | None
    expectancy: Decimal | None
    profit_factor: Decimal | None
    max_drawdown: Decimal | None
    total_net_pl: Decimal | None
    metrics_snapshot: dict
    acceptance_passed: bool | None
    acceptance_reasons: list | None
    acceptance_snapshot: dict | None

    model_config = ConfigDict(from_attributes=True)


class BacktestRunResponse(BaseModel):
    id: str
    protocol_id: str | None
    protocol_evidence_hash: str | None
    strategy: str
    strategy_version: str
    symbols: list | None
    timeframe: str | None
    status: BacktestStatus
    data_source: str
    source_format: str
    source_artifact_hash: str | None
    source_reference: str | None
    evidence_hash: str | None
    data_start: datetime
    data_end: datetime
    in_sample_start: datetime | None
    in_sample_end: datetime | None
    out_of_sample_start: datetime | None
    out_of_sample_end: datetime | None
    config_hash: str
    parameters: dict
    cost_model: dict | None
    slippage_model: dict | None
    risk_snapshot: dict | None
    result: BacktestResultResponse | None

    model_config = ConfigDict(from_attributes=True)


class BacktestTradeResponse(BaseModel):
    id: str
    backtest_run_id: str
    sequence: int
    external_trade_id: str | None
    source_format: str
    strategy: str
    symbol: str | None
    direction: Direction | None
    entry_at: datetime | None
    closed_at: datetime | None
    entry_price: Decimal | None
    exit_price: Decimal | None
    quantity: Decimal | None
    gross_pl: Decimal | None
    fees: Decimal | None
    slippage: Decimal | None
    realized_pl: Decimal
    equity: Decimal | None
    r_multiple: Decimal | None
    market_regime: str | None
    costs_snapshot: dict
    raw_row: dict

    model_config = ConfigDict(from_attributes=True)

class CsvImportResponse(BaseModel):
    candles: int
    trades: int


class CsvImportRequest(BaseModel):
    csv_text: str = Field(min_length=1)


class TradeCsvImportResponse(BaseModel):
    trades: int
    parsed_trades: list[BacktestTradeInput]
