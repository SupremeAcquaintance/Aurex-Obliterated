from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from aurex.domain.enums import (
    StrategyResearchObservationType,
    StrategyResearchSource,
    StrategyResearchStatus,
)


class StrategyConfigResponse(BaseModel):
    id: str
    strategy: str
    version: str
    display_name: str
    description: str | None
    is_enabled: bool
    allowed_regimes: list[str]
    risk_per_trade: Decimal | None
    minimum_reward_risk: Decimal | None
    max_open_positions: int | None
    parameters: dict
    notes: str | None
    lifecycle_status: str
    lifecycle_reason: str
    enable_eligible: bool

    model_config = ConfigDict(from_attributes=True)


class StrategyConfigUpdate(BaseModel):
    is_enabled: bool | None = None
    risk_per_trade: Decimal | None = Field(default=None, ge=0)
    minimum_reward_risk: Decimal | None = Field(default=None, gt=0)
    max_open_positions: int | None = Field(default=None, ge=0)
    parameters: dict | None = None
    notes: str | None = None

    model_config = ConfigDict(extra="forbid")


class StrategyComparisonItem(BaseModel):
    strategy: str
    display_name: str
    is_enabled: bool
    allowed_regimes: list[str]
    risk_per_trade: Decimal | None
    minimum_reward_risk: Decimal | None
    max_open_positions: int | None
    open_trades: int
    closed_trades: int
    wins: int
    losses: int
    win_rate: Decimal
    expectancy: Decimal
    total_net_pl: Decimal


class StrategyComparisonResponse(BaseModel):
    strategies: list[StrategyComparisonItem]


class StrategyResearchCandidateCreate(BaseModel):
    source: StrategyResearchSource = StrategyResearchSource.MY_KRYPT_TRADER
    candidate_key: str = Field(min_length=1, max_length=128)
    strategy: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=160)
    hypothesis: str = Field(min_length=1)
    status: StrategyResearchStatus = StrategyResearchStatus.RESEARCH_ONLY
    source_reference: str | None = None
    raw_payload: dict = Field(default_factory=dict)
    normalized_payload: dict = Field(default_factory=dict)


class StrategyResearchObservationCreate(BaseModel):
    candidate_id: str | None = Field(default=None, min_length=1)
    candidate_key: str | None = Field(default=None, min_length=1, max_length=128)
    source: StrategyResearchSource = StrategyResearchSource.MY_KRYPT_TRADER
    strategy: str | None = Field(default=None, max_length=100)
    display_name: str | None = Field(default=None, max_length=160)
    hypothesis: str | None = None
    observation_type: StrategyResearchObservationType
    source_event_id: str | None = Field(default=None, max_length=160)
    symbol: str | None = Field(default=None, max_length=64)
    contract_ticker: str | None = Field(default=None, max_length=160)
    side: str | None = Field(default=None, max_length=16)
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    implied_probability: Decimal | None = Field(default=None, ge=0, le=1)
    expected_edge: Decimal | None = None
    observation_snapshot: dict = Field(default_factory=dict)
    raw_payload: dict = Field(default_factory=dict)
    observed_at: datetime | None = None
    resolved_at: datetime | None = None
    outcome_snapshot: dict = Field(default_factory=dict)


class StrategyResearchObservationResponse(BaseModel):
    id: str
    candidate_id: str
    observation_type: StrategyResearchObservationType
    source_event_id: str | None
    symbol: str | None
    contract_ticker: str | None
    side: str | None
    confidence: Decimal | None
    implied_probability: Decimal | None
    expected_edge: Decimal | None
    observation_snapshot: dict
    raw_payload: dict
    evidence_hash: str
    observed_at: datetime
    resolved_at: datetime | None
    outcome_snapshot: dict

    model_config = ConfigDict(from_attributes=True)


class StrategyResearchCandidateResponse(BaseModel):
    id: str
    source: StrategyResearchSource
    candidate_key: str
    strategy: str
    display_name: str
    hypothesis: str
    status: StrategyResearchStatus
    trade_eligible: bool
    eligibility_reason: str
    required_evidence: dict
    evidence_hash: str
    source_reference: str | None
    raw_payload: dict
    normalized_payload: dict
    first_seen_at: datetime
    last_seen_at: datetime
    observation_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class StrategyResearchBacktestRequest(BaseModel):
    minimum_trades: int = Field(default=100, ge=1)
    minimum_oos_trades: int = Field(default=30, ge=1)
    minimum_oos_profit_factor: Decimal = Field(default=Decimal("1.15"), ge=0)
    maximum_oos_drawdown: Decimal = Field(default=Decimal("25"), ge=0)
    minimum_active_days: int = Field(default=15, ge=1)
    maximum_single_day_share: Decimal = Field(default=Decimal("0.25"), gt=0, le=1)
    oos_fraction: Decimal = Field(default=Decimal("0.30"), gt=0, lt=1)
    minimum_walk_forward_windows: int = Field(default=3, ge=1)
    minimum_walk_forward_pass_rate: Decimal = Field(default=Decimal("0.67"), ge=0, le=1)
    require_known_regime: bool = True
    minimum_regime_groups: int = Field(default=1, ge=1)
    minimum_regime_trades: int = Field(default=10, ge=1)
    minimum_regime_pass_rate: Decimal = Field(default=Decimal("0.67"), ge=0, le=1)
    tested_variant_count: int = Field(default=1, ge=1)
    maximum_tested_variants: int = Field(default=12, ge=1)
    multiple_testing_profit_factor_step: Decimal = Field(default=Decimal("0.02"), ge=0)
    maximum_multiple_testing_profit_factor_penalty: Decimal = Field(
        default=Decimal("0.25"),
        ge=0,
    )
    minimum_statistical_oos_trades: int = Field(default=30, ge=1)
    statistical_null_win_probability: Decimal = Field(default=Decimal("0.50"), gt=0, lt=1)
    maximum_statistical_p_value: Decimal = Field(default=Decimal("0.05"), ge=0, le=1)
    fee_rate: Decimal = Field(default=Decimal("0.07"), ge=0)


class StrategyResearchBacktestResponse(BaseModel):
    backtest_run_id: str
    candidate_id: str
    strategy: str
    accepted: bool
    decision: StrategyResearchStatus
    reason: str
    reasons: list[str]
    metrics: dict
    requirements: dict
    evidence_hash: str


class StrategyResearchBacktestRunResponse(BaseModel):
    id: str
    candidate_id: str
    strategy: str
    accepted: bool
    decision: StrategyResearchStatus
    reason: str
    reasons: list[str]
    metrics: dict
    requirements: dict
    evidence_hash: str
    reviewed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StrategyResearchEvidenceResponse(BaseModel):
    candidate: StrategyResearchCandidateResponse
    latest_backtest: StrategyResearchBacktestRunResponse | None
    backtest_runs: list[StrategyResearchBacktestRunResponse]
    observations: list[StrategyResearchObservationResponse]
    evidence_summary: dict


class StrategyResearchReadinessItem(BaseModel):
    rank: int
    candidate_id: str
    candidate_key: str
    strategy: str
    display_name: str
    status: StrategyResearchStatus
    trade_eligible: bool
    readiness_state: str
    next_action: str
    observation_count: int
    resolved_observation_count: int
    latest_backtest_run_id: str | None
    latest_backtest_accepted: bool | None
    latest_backtest_reviewed_at: datetime | None
    first_blocker: str | None
    total_trades: int | None
    oos_trades: int | None
    oos_expectancy: str | None
    oos_profit_factor: str | None
    oos_profit_factor_infinite: bool
    oos_max_drawdown: str | None
    regime_coverage: str | None
    regime_diagnostics: str | None
    variant_pressure: str | None
    variant_diagnostics: str | None
    statistical_significance: str | None
    evidence_hash: str | None


class StrategyResearchReadinessQueueResponse(BaseModel):
    generated_at: datetime
    candidate_count: int
    summary: dict
    items: list[StrategyResearchReadinessItem]


class MktResearchImportRequest(BaseModel):
    db_path: str = "My-Krypt-Trader/.aurex-demo-userdata/data/krypt-trader.db"
    sources: list[str] = Field(
        default_factory=lambda: ["whale", "momentum", "crypto15m"],
    )
    limit_per_source: int = Field(default=500, ge=1, le=5000)
    include_resolved: bool = True
    include_unresolved: bool = True
    acknowledge_research_only_import: bool = False


class MktResearchImportSourceQuality(BaseModel):
    source: str
    table: str
    table_exists: bool | None
    processed_observations: int
    resolved_observations: int
    unresolved_observations: int
    target_resolved_observations: int
    remaining_resolved_observations: int
    status: str
    next_action: str


class MktResearchImportReportBase(BaseModel):
    db_path: str
    candidate_count: int
    processed_observations: int
    resolved_observations: int
    unresolved_observations: int
    skipped_rows: int
    source_counts: dict[str, int]
    candidate_ids: list[str]
    skip_reasons: dict[str, int]
    quality_status: str
    source_quality: list[MktResearchImportSourceQuality]
    blockers: list[str]
    next_action: str
    research_only_import_acknowledged: bool = False
    live_execution_enabled: bool = False


class MktResearchImportPreflightResponse(MktResearchImportReportBase):
    candidate_ids: list[str] = Field(default_factory=list)
    preflight_only: bool = True
    mutates_research_ledger: bool = False


class MktResearchImportResponse(MktResearchImportReportBase):
    candidate_ids: list[str]
    preflight_only: bool = False
    mutates_research_ledger: bool = True


class MktResearchIntakeReadinessCheck(BaseModel):
    key: str
    status: str
    passed: bool
    observed: str
    expected: str
    next_action: str


class MktResearchCollectionHealthResponse(BaseModel):
    status: str
    processed_observations: int
    resolved_observations: int
    unresolved_observations: int
    backtest_depth_progress_pct: float
    blockers: list[str]
    next_action: str


class MktResearchIntakeReadinessResponse(BaseModel):
    status: str
    db_path: str
    db_exists: bool
    db_file_size_bytes: int | None = None
    db_modified_at: datetime | None = None
    db_age_seconds: float | None = None
    db_freshness_status: str
    logs_dir: str
    logs_dir_exists: bool
    latest_log_modified_at: datetime | None = None
    log_files: list[dict]
    collection_activity_status: str
    preflight: MktResearchImportPreflightResponse | None = None
    checks: list[MktResearchIntakeReadinessCheck]
    blockers: list[str]
    safe_to_import_research: bool
    ready_for_research_backtest: bool
    command_hints: list[dict]
    collection_health: MktResearchCollectionHealthResponse
    next_action: str
    live_execution_enabled: bool = False


class MktResearchIntakeRunbookStep(BaseModel):
    rank: int
    key: str
    label: str
    status: str
    evidence: str
    command: str | None = None
    writes_research_ledger: bool = False
    next_action: str


class MktResearchIntakeThresholdResponse(BaseModel):
    key: str
    label: str
    current_count: int
    target_count: int
    remaining_count: int
    progress_pct: float
    status: str
    next_action: str


class MktResearchIntakeRunbookResponse(BaseModel):
    status: str
    db_path: str
    readiness_status: str
    db_freshness_status: str
    db_file_size_bytes: int | None = None
    db_modified_at: datetime | None = None
    latest_log_modified_at: datetime | None = None
    collection_activity_status: str
    collection_health_status: str
    collection_health: MktResearchCollectionHealthResponse
    processed_observations: int
    resolved_observations: int
    unresolved_observations: int
    backtest_depth_progress_pct: float
    preflight_quality_status: str | None = None
    current_step: MktResearchIntakeRunbookStep | None = None
    current_command: str | None = None
    completed_step_count: int
    total_step_count: int
    progress_pct: float
    thresholds: list[MktResearchIntakeThresholdResponse]
    steps: list[MktResearchIntakeRunbookStep]
    blockers: list[str]
    next_action: str
    checked_at: datetime
    live_execution_enabled: bool = False
