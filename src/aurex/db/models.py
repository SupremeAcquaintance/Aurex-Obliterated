from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aurex.db.base import Base, IdModel
from aurex.domain.enums import (
    AnalystNoteType,
    BacktestStatus,
    BrokerConnectionStatus,
    BrokerEnvironment,
    BrokerOrderStatus,
    Direction,
    LiveApprovalPacketStatus,
    LiveApprovalStatus,
    LiveApprovalType,
    LiveDailyReviewStatus,
    LiveDeploymentStatus,
    MarketRegime,
    OrderIntentStatus,
    OrderStatus,
    PositionStatus,
    PredictionMarketEvidenceKind,
    PredictionMarketOrderAction,
    PredictionMarketOrderStatus,
    PredictionMarketOrderType,
    PredictionMarketPositionStatus,
    PredictionMarketSide,
    PredictionMarketStatus,
    PredictionMarketVenue,
    ReadinessStatus,
    ReconciliationStatus,
    SignalStatus,
    StrategyEvidenceDecision,
    StrategyResearchObservationType,
    StrategyResearchSource,
    StrategyResearchStatus,
    StrategyRunStatus,
    SystemEventSeverity,
    TradeStatus,
)

Money = Numeric(20, 8)
Quantity = Numeric(28, 12)
Ratio = Numeric(12, 6)


def enum_column(enum_type: type) -> Enum:
    return Enum(enum_type, native_enum=False, validate_strings=True)


class Symbol(IdModel, Base):
    __tablename__ = "symbols"

    symbol: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    base_asset: Mapped[str | None] = mapped_column(String(32))
    quote_asset: Mapped[str | None] = mapped_column(String(32))
    asset_class: Mapped[str | None] = mapped_column(String(32))
    exchange: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    signals: Mapped[list["Signal"]] = relationship(back_populates="symbol_ref")


class Account(IdModel, Base):
    __tablename__ = "accounts"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="paper")
    currency: Mapped[str] = mapped_column(String(12), nullable=False, default="USD")
    starting_equity: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("1000"))
    current_equity: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("1000"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    risk_profiles: Mapped[list["RiskProfile"]] = relationship(back_populates="account")
    paper_trades: Mapped[list["PaperTrade"]] = relationship(back_populates="account")
    positions: Mapped[list["Position"]] = relationship(back_populates="account")
    paper_evidence_import_batches: Mapped[list["PaperEvidenceImportBatch"]] = relationship(
        back_populates="account"
    )


class NativeHistorySeed(IdModel, Base):
    __tablename__ = "native_history_seeds"

    stream_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class NativeBarOutcome(IdModel, Base):
    __tablename__ = "native_bar_outcomes"
    __table_args__ = (
        Index("uq_native_bar_stream_sequence", "stream_key", "sequence", unique=True),
        Index("uq_native_bar_stream_candle", "stream_key", "candle_id", unique=True),
    )

    stream_key: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    candle_id: Mapped[str] = mapped_column(String(64), nullable=False)
    signal_id: Mapped[str | None] = mapped_column(ForeignKey("signals.id"))
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class RiskProfile(IdModel, Base):
    __tablename__ = "risk_profiles"

    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    risk_per_trade: Mapped[Decimal] = mapped_column(Ratio, nullable=False, default=Decimal("0.005"))
    max_daily_loss: Mapped[Decimal] = mapped_column(Ratio, nullable=False, default=Decimal("0.01"))
    max_weekly_loss: Mapped[Decimal] = mapped_column(Ratio, nullable=False, default=Decimal("0.03"))
    max_open_positions: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    minimum_reward_risk: Mapped[Decimal] = mapped_column(
        Ratio,
        nullable=False,
        default=Decimal("1.5"),
    )
    duplicate_cooldown_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    max_signal_age_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=180)
    loss_cooldown_count: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    kill_switch_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    account: Mapped[Account] = relationship(back_populates="risk_profiles")


class Signal(IdModel, Base):
    __tablename__ = "signals"
    __table_args__ = (
        Index(
            "ix_signals_dedupe_window",
            "symbol",
            "strategy",
            "timeframe",
            "direction",
            "source_timestamp",
        ),
        Index(
            "uq_signals_canonical_idempotency_key",
            "idempotency_key",
            unique=True,
            sqlite_where=text("status <> 'DUPLICATE_REJECTED'"),
            postgresql_where=text("status <> 'DUPLICATE_REJECTED'"),
        ),
    )

    source: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    symbol_id: Mapped[str | None] = mapped_column(ForeignKey("symbols.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[Direction] = mapped_column(enum_column(Direction), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    stop_loss: Mapped[Decimal | None] = mapped_column(Money)
    take_profit: Mapped[Decimal | None] = mapped_column(Money)
    market_regime: Mapped[MarketRegime] = mapped_column(
        enum_column(MarketRegime),
        nullable=False,
        default=MarketRegime.UNKNOWN,
    )
    status: Mapped[SignalStatus] = mapped_column(
        enum_column(SignalStatus),
        nullable=False,
        default=SignalStatus.RECEIVED,
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    duplicate_of_signal_id: Mapped[str | None] = mapped_column(ForeignKey("signals.id"), index=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    normalized_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    source_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    symbol_ref: Mapped[Symbol | None] = relationship(back_populates="signals")
    duplicate_of: Mapped["Signal | None"] = relationship(remote_side="Signal.id")
    events: Mapped[list["SignalEvent"]] = relationship(back_populates="signal")
    market_states: Mapped[list["MarketState"]] = relationship(back_populates="signal")
    strategy_scores: Mapped[list["StrategyScore"]] = relationship(back_populates="signal")
    risk_decisions: Mapped[list["RiskDecision"]] = relationship(
        back_populates="signal",
        order_by="RiskDecision.created_at",
    )
    paper_orders: Mapped[list["PaperOrder"]] = relationship(back_populates="signal")

    @property
    def latest_risk_decision(self) -> "RiskDecision | None":
        if not self.risk_decisions:
            return None
        return self.risk_decisions[-1]

    @property
    def strategy_version(self) -> str | None:
        return (self.normalized_payload or {}).get("strategy_version")

    @property
    def settings_fingerprint(self) -> str | None:
        return (self.normalized_payload or {}).get("settings_fingerprint")

    @property
    def processing_latency_ms(self) -> Decimal | None:
        if self.processed_at is None:
            return None
        elapsed_ms = Decimal(str((self.processed_at - self.received_at).total_seconds() * 1000))
        return max(Decimal("0"), elapsed_ms).quantize(Decimal("0.001"))


class SignalEvent(IdModel, Base):
    __tablename__ = "signal_events"

    signal_id: Mapped[str] = mapped_column(ForeignKey("signals.id"), nullable=False, index=True)
    status: Mapped[SignalStatus] = mapped_column(enum_column(SignalStatus), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    signal: Mapped[Signal] = relationship(back_populates="events")


class MarketState(IdModel, Base):
    __tablename__ = "market_states"

    signal_id: Mapped[str | None] = mapped_column(ForeignKey("signals.id"), index=True)
    symbol_id: Mapped[str | None] = mapped_column(ForeignKey("symbols.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(32), nullable=False)
    regime: Mapped[MarketRegime] = mapped_column(
        enum_column(MarketRegime),
        nullable=False,
        default=MarketRegime.UNKNOWN,
    )
    confidence: Mapped[Decimal | None] = mapped_column(Ratio)
    inputs_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    signal: Mapped[Signal | None] = relationship(back_populates="market_states")


class MarketCandle(IdModel, Base):
    __tablename__ = "market_candles"
    __table_args__ = (
        Index(
            "ix_market_candles_symbol_timeframe_timestamp",
            "symbol",
            "timeframe",
            "timestamp",
            unique=True,
        ),
    )

    symbol_id: Mapped[str | None] = mapped_column(ForeignKey("symbols.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    open: Mapped[Decimal] = mapped_column(Money, nullable=False)
    high: Mapped[Decimal] = mapped_column(Money, nullable=False)
    low: Mapped[Decimal] = mapped_column(Money, nullable=False)
    close: Mapped[Decimal] = mapped_column(Money, nullable=False)
    volume: Mapped[Decimal] = mapped_column(Quantity, nullable=False)
    source: Mapped[str | None] = mapped_column(String(100))


class StrategyScore(IdModel, Base):
    __tablename__ = "strategy_scores"

    signal_id: Mapped[str] = mapped_column(ForeignKey("signals.id"), nullable=False, index=True)
    strategy: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    score: Mapped[Decimal] = mapped_column(Ratio, nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Ratio)
    rationale: Mapped[str | None] = mapped_column(Text)
    features_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    signal: Mapped[Signal] = relationship(back_populates="strategy_scores")


class StrategyConfig(IdModel, Base):
    __tablename__ = "strategy_configs"

    strategy: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False, default="1.0.0")
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allowed_regimes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    risk_per_trade: Mapped[Decimal | None] = mapped_column(Ratio)
    minimum_reward_risk: Mapped[Decimal | None] = mapped_column(Ratio)
    max_open_positions: Mapped[int | None] = mapped_column(Integer)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)


class StrategyResearchCandidate(IdModel, Base):
    __tablename__ = "strategy_research_candidates"
    __table_args__ = (
        Index(
            "ix_strategy_research_candidates_source_key",
            "source",
            "candidate_key",
            unique=True,
        ),
    )

    source: Mapped[StrategyResearchSource] = mapped_column(
        enum_column(StrategyResearchSource),
        nullable=False,
        index=True,
    )
    candidate_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    strategy: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[StrategyResearchStatus] = mapped_column(
        enum_column(StrategyResearchStatus),
        nullable=False,
        default=StrategyResearchStatus.RESEARCH_ONLY,
        index=True,
    )
    trade_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    eligibility_reason: Mapped[str] = mapped_column(Text, nullable=False)
    required_evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_reference: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    normalized_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    observations: Mapped[list["StrategyResearchObservation"]] = relationship(
        back_populates="candidate",
        order_by="StrategyResearchObservation.observed_at.desc()",
    )
    backtest_runs: Mapped[list["StrategyResearchBacktestRun"]] = relationship(
        back_populates="candidate",
        order_by="StrategyResearchBacktestRun.reviewed_at.desc()",
    )


class StrategyResearchObservation(IdModel, Base):
    __tablename__ = "strategy_research_observations"

    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("strategy_research_candidates.id"),
        nullable=False,
        index=True,
    )
    observation_type: Mapped[StrategyResearchObservationType] = mapped_column(
        enum_column(StrategyResearchObservationType),
        nullable=False,
        index=True,
    )
    source_event_id: Mapped[str | None] = mapped_column(String(160), index=True)
    symbol: Mapped[str | None] = mapped_column(String(64), index=True)
    contract_ticker: Mapped[str | None] = mapped_column(String(160), index=True)
    side: Mapped[str | None] = mapped_column(String(16), index=True)
    confidence: Mapped[Decimal | None] = mapped_column(Ratio)
    implied_probability: Mapped[Decimal | None] = mapped_column(Ratio)
    expected_edge: Mapped[Decimal | None] = mapped_column(Ratio)
    observation_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    candidate: Mapped[StrategyResearchCandidate] = relationship(back_populates="observations")


class StrategyResearchBacktestRun(IdModel, Base):
    __tablename__ = "strategy_research_backtest_runs"
    __table_args__ = (
        Index(
            "ix_strategy_research_backtest_runs_candidate_reviewed",
            "candidate_id",
            "reviewed_at",
        ),
    )

    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("strategy_research_candidates.id"),
        nullable=False,
        index=True,
    )
    strategy: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    decision: Mapped[StrategyResearchStatus] = mapped_column(
        enum_column(StrategyResearchStatus),
        nullable=False,
        index=True,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reasons: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    requirements: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    candidate: Mapped[StrategyResearchCandidate] = relationship(back_populates="backtest_runs")


class RiskDecision(IdModel, Base):
    __tablename__ = "risk_decisions"

    signal_id: Mapped[str] = mapped_column(ForeignKey("signals.id"), nullable=False, index=True)
    risk_profile_id: Mapped[str | None] = mapped_column(ForeignKey("risk_profiles.id"), index=True)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reward_risk: Mapped[Decimal | None] = mapped_column(Ratio)
    risk_amount: Mapped[Decimal | None] = mapped_column(Money)
    position_size: Mapped[Decimal | None] = mapped_column(Quantity)
    account_equity: Mapped[Decimal | None] = mapped_column(Money)
    rules_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    signal: Mapped[Signal] = relationship(back_populates="risk_decisions")


class PaperOrder(IdModel, Base):
    __tablename__ = "paper_orders"

    signal_id: Mapped[str] = mapped_column(ForeignKey("signals.id"), nullable=False, index=True)
    risk_decision_id: Mapped[str] = mapped_column(ForeignKey("risk_decisions.id"), nullable=False)
    symbol_id: Mapped[str | None] = mapped_column(ForeignKey("symbols.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    direction: Mapped[Direction] = mapped_column(enum_column(Direction), nullable=False)
    order_type: Mapped[str] = mapped_column(String(32), nullable=False, default="market")
    status: Mapped[OrderStatus] = mapped_column(
        enum_column(OrderStatus),
        nullable=False,
        default=OrderStatus.CREATED,
    )
    requested_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    filled_price: Mapped[Decimal | None] = mapped_column(Money)
    quantity: Mapped[Decimal] = mapped_column(Quantity, nullable=False)
    fees: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    slippage: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    fill_model: Mapped[str] = mapped_column(String(64), nullable=False, default="instant")
    execution_assumptions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    execution_assumptions_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    created_order_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    signal: Mapped[Signal] = relationship(back_populates="paper_orders")
    paper_trades: Mapped[list["PaperTrade"]] = relationship(back_populates="paper_order")


class PaperTrade(IdModel, Base):
    __tablename__ = "paper_trades"

    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    paper_order_id: Mapped[str] = mapped_column(
        ForeignKey("paper_orders.id"),
        nullable=False,
        index=True,
    )
    strategy: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    symbol_id: Mapped[str | None] = mapped_column(ForeignKey("symbols.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[Direction] = mapped_column(enum_column(Direction), nullable=False)
    status: Mapped[TradeStatus] = mapped_column(
        enum_column(TradeStatus),
        nullable=False,
        default=TradeStatus.OPEN,
        index=True,
    )
    market_regime: Mapped[MarketRegime] = mapped_column(
        enum_column(MarketRegime),
        nullable=False,
        default=MarketRegime.UNKNOWN,
    )
    entry_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    stop_loss: Mapped[Decimal] = mapped_column(Money, nullable=False)
    take_profit: Mapped[Decimal] = mapped_column(Money, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Quantity, nullable=False)
    risk_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exit_price: Mapped[Decimal | None] = mapped_column(Money)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    realized_pl: Mapped[Decimal | None] = mapped_column(Money)
    r_multiple: Mapped[Decimal | None] = mapped_column(Ratio)
    fees: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    slippage: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    close_reason: Mapped[str | None] = mapped_column(Text)

    account: Mapped[Account] = relationship(back_populates="paper_trades")
    paper_order: Mapped[PaperOrder] = relationship(back_populates="paper_trades")
    journal_entries: Mapped[list["TradeJournalEntry"]] = relationship(
        back_populates="paper_trade",
        order_by="TradeJournalEntry.journaled_at",
    )


class TradeJournalEntry(IdModel, Base):
    __tablename__ = "trade_journal_entries"

    paper_trade_id: Mapped[str] = mapped_column(
        ForeignKey("paper_trades.id"),
        nullable=False,
        index=True,
    )
    author: Mapped[str] = mapped_column(String(120), nullable=False)
    thesis: Mapped[str] = mapped_column(Text, nullable=False)
    execution_notes: Mapped[str | None] = mapped_column(Text)
    outcome_notes: Mapped[str | None] = mapped_column(Text)
    rule_followed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    emotional_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    evidence_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    journaled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    paper_trade: Mapped[PaperTrade] = relationship(back_populates="journal_entries")


class PaperEvidenceImportBatch(IdModel, Base):
    __tablename__ = "paper_evidence_import_batches"

    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_reference: Mapped[str] = mapped_column(Text, nullable=False)
    import_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    rows_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    required_headers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    row_results: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    evidence_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    account: Mapped[Account] = relationship(back_populates="paper_evidence_import_batches")

    @property
    def analysis_summary(self) -> dict:
        return self.evidence_snapshot.get("analysis_summary", {})


class Position(IdModel, Base):
    __tablename__ = "positions"

    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    symbol_id: Mapped[str | None] = mapped_column(ForeignKey("symbols.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    direction: Mapped[Direction] = mapped_column(enum_column(Direction), nullable=False)
    status: Mapped[PositionStatus] = mapped_column(
        enum_column(PositionStatus),
        nullable=False,
        default=PositionStatus.OPEN,
        index=True,
    )
    quantity: Mapped[Decimal] = mapped_column(Quantity, nullable=False)
    average_entry_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    account: Mapped[Account] = relationship(back_populates="positions")


class EquityCurvePoint(IdModel, Base):
    __tablename__ = "equity_curve_points"

    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    equity: Mapped[Decimal] = mapped_column(Money, nullable=False)
    realized_pl: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    drawdown: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )


class StrategyRun(IdModel, Base):
    __tablename__ = "strategy_runs"

    strategy: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[StrategyRunStatus] = mapped_column(
        enum_column(StrategyRunStatus),
        nullable=False,
        default=StrategyRunStatus.DRAFT,
    )
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)


class BacktestDataset(IdModel, Base):
    __tablename__ = "backtest_datasets"

    symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    source_reference: Mapped[str] = mapped_column(Text, nullable=False)
    csv_timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    continuity: Mapped[str] = mapped_column(String(32), nullable=False)
    data_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    quality_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    candles: Mapped[list["BacktestDatasetCandle"]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="BacktestDatasetCandle.sequence",
    )


class BacktestDatasetCandle(IdModel, Base):
    __tablename__ = "backtest_dataset_candles"
    __table_args__ = (
        Index(
            "ix_backtest_dataset_candles_dataset_sequence",
            "dataset_id",
            "sequence",
            unique=True,
        ),
        Index(
            "ix_backtest_dataset_candles_dataset_timestamp",
            "dataset_id",
            "timestamp",
            unique=True,
        ),
    )

    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("backtest_datasets.id"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    open: Mapped[str] = mapped_column(String(80), nullable=False)
    high: Mapped[str] = mapped_column(String(80), nullable=False)
    low: Mapped[str] = mapped_column(String(80), nullable=False)
    close: Mapped[str] = mapped_column(String(80), nullable=False)
    volume: Mapped[str] = mapped_column(String(80), nullable=False)

    dataset: Mapped[BacktestDataset] = relationship(back_populates="candles")


class BacktestReferenceReplayRun(IdModel, Base):
    __tablename__ = "backtest_reference_replay_runs"

    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("backtest_datasets.id"),
        nullable=False,
        index=True,
    )
    strategy: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    strategy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    dataset_evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    engine_evidence_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    record_evidence_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    request_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    result_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )


class BacktestReferenceReplayValidation(IdModel, Base):
    __tablename__ = "backtest_reference_replay_validations"

    reference_replay_run_id: Mapped[str] = mapped_column(
        ForeignKey("backtest_reference_replay_runs.id"),
        nullable=False,
        index=True,
    )
    protocol_id: Mapped[str] = mapped_column(
        ForeignKey("backtest_protocols.id"),
        nullable=False,
        index=True,
    )
    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("backtest_datasets.id"),
        nullable=False,
        index=True,
    )
    strategy: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    strategy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(32), nullable=False)
    evaluator_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    statistical_acceptance_passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    replay_record_evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    engine_evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    protocol_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    trade_evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_evidence_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    request_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    metrics_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    acceptance_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    binding_snapshot: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    reason_snapshot: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    warning_snapshot: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )


class BacktestParityRun(IdModel, Base):
    __tablename__ = "backtest_parity_runs"

    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("backtest_datasets.id"),
        nullable=False,
        index=True,
    )
    tradingview_run_id: Mapped[str] = mapped_column(
        ForeignKey("backtest_runs.id"),
        nullable=False,
        index=True,
    )
    strategy: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    strategy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    dataset_evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    tradingview_evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    replay_evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    request_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    summary_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    mismatch_snapshot: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    reason_snapshot: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    warning_snapshot: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )


class BacktestProtocol(IdModel, Base):
    __tablename__ = "backtest_protocols"

    strategy: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    strategy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    symbols: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    timeframe: Mapped[str] = mapped_column(String(32), nullable=False)
    protocol_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    protocol_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    backtest_run: Mapped["BacktestRun | None"] = relationship(
        back_populates="protocol",
        uselist=False,
    )


class BacktestRun(IdModel, Base):
    __tablename__ = "backtest_runs"

    protocol_id: Mapped[str | None] = mapped_column(
        ForeignKey("backtest_protocols.id"),
        unique=True,
        index=True,
    )
    protocol_evidence_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    strategy: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    strategy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    symbols: Mapped[list | None] = mapped_column(JSON)
    timeframe: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[BacktestStatus] = mapped_column(
        enum_column(BacktestStatus),
        nullable=False,
        default=BacktestStatus.DRAFT,
    )
    data_source: Mapped[str] = mapped_column(String(100), nullable=False)
    source_format: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="aurex_json",
    )
    source_artifact_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    source_reference: Mapped[str | None] = mapped_column(Text)
    evidence_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    data_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    in_sample_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    in_sample_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    out_of_sample_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    out_of_sample_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    config_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    cost_model: Mapped[dict | None] = mapped_column(JSON)
    slippage_model: Mapped[dict | None] = mapped_column(JSON)
    risk_snapshot: Mapped[dict | None] = mapped_column(JSON)

    protocol: Mapped[BacktestProtocol | None] = relationship(back_populates="backtest_run")
    result: Mapped["BacktestResult | None"] = relationship(back_populates="backtest_run")
    trades: Mapped[list["BacktestTrade"]] = relationship(
        back_populates="backtest_run",
        cascade="all, delete-orphan",
        order_by="BacktestTrade.sequence",
    )


class BacktestTrade(IdModel, Base):
    __tablename__ = "backtest_trades"
    __table_args__ = (
        Index(
            "ix_backtest_trades_run_sequence",
            "backtest_run_id",
            "sequence",
            unique=True,
        ),
    )

    backtest_run_id: Mapped[str] = mapped_column(
        ForeignKey("backtest_runs.id"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    external_trade_id: Mapped[str | None] = mapped_column(String(128), index=True)
    source_format: Mapped[str] = mapped_column(String(32), nullable=False)
    strategy: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    symbol: Mapped[str | None] = mapped_column(String(64), index=True)
    direction: Mapped[Direction | None] = mapped_column(enum_column(Direction))
    entry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    entry_price: Mapped[Decimal | None] = mapped_column(Money)
    exit_price: Mapped[Decimal | None] = mapped_column(Money)
    quantity: Mapped[Decimal | None] = mapped_column(Quantity)
    gross_pl: Mapped[Decimal | None] = mapped_column(Money)
    fees: Mapped[Decimal | None] = mapped_column(Money)
    slippage: Mapped[Decimal | None] = mapped_column(Money)
    realized_pl: Mapped[Decimal] = mapped_column(Money, nullable=False)
    equity: Mapped[Decimal | None] = mapped_column(Money)
    r_multiple: Mapped[Decimal | None] = mapped_column(Ratio)
    market_regime: Mapped[str | None] = mapped_column(String(64), index=True)
    costs_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    raw_row: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    backtest_run: Mapped[BacktestRun] = relationship(back_populates="trades")


class BacktestResult(IdModel, Base):
    __tablename__ = "backtest_results"

    backtest_run_id: Mapped[str] = mapped_column(
        ForeignKey("backtest_runs.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    losses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    breakeven: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    win_rate: Mapped[Decimal | None] = mapped_column(Ratio)
    average_win: Mapped[Decimal | None] = mapped_column(Money)
    average_loss: Mapped[Decimal | None] = mapped_column(Money)
    expectancy: Mapped[Decimal | None] = mapped_column(Money)
    profit_factor: Mapped[Decimal | None] = mapped_column(Ratio)
    max_drawdown: Mapped[Decimal | None] = mapped_column(Money)
    total_net_pl: Mapped[Decimal | None] = mapped_column(Money)
    metrics_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    acceptance_passed: Mapped[bool | None] = mapped_column(Boolean)
    acceptance_reasons: Mapped[list | None] = mapped_column(JSON)
    acceptance_snapshot: Mapped[dict | None] = mapped_column(JSON)

    backtest_run: Mapped[BacktestRun] = relationship(back_populates="result")


class AnalystNote(IdModel, Base):
    __tablename__ = "analyst_notes"

    trade_id: Mapped[str | None] = mapped_column(ForeignKey("paper_trades.id"), index=True)
    strategy: Mapped[str | None] = mapped_column(String(100), index=True)
    symbol: Mapped[str | None] = mapped_column(String(64), index=True)
    note_type: Mapped[AnalystNoteType] = mapped_column(
        enum_column(AnalystNoteType),
        nullable=False,
        index=True,
    )
    severity: Mapped[SystemEventSeverity] = mapped_column(
        enum_column(SystemEventSeverity),
        nullable=False,
        default=SystemEventSeverity.INFO,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[Decimal | None] = mapped_column(Ratio)
    evidence_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, default="deterministic_v1")
    advisory_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    trade: Mapped[PaperTrade | None] = relationship()


class BrokerConnection(IdModel, Base):
    __tablename__ = "broker_connections"

    broker_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    environment: Mapped[BrokerEnvironment] = mapped_column(
        enum_column(BrokerEnvironment),
        nullable=False,
        default=BrokerEnvironment.SANDBOX,
        index=True,
    )
    account_label: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[BrokerConnectionStatus] = mapped_column(
        enum_column(BrokerConnectionStatus),
        nullable=False,
        default=BrokerConnectionStatus.CONFIGURED,
        index=True,
    )
    live_trading_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    capabilities: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class OrderIntent(IdModel, Base):
    __tablename__ = "order_intents"

    signal_id: Mapped[str | None] = mapped_column(ForeignKey("signals.id"), index=True)
    risk_decision_id: Mapped[str | None] = mapped_column(
        ForeignKey("risk_decisions.id"),
        index=True,
    )
    broker_connection_id: Mapped[str] = mapped_column(
        ForeignKey("broker_connections.id"),
        nullable=False,
        index=True,
    )
    strategy: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    direction: Mapped[Direction] = mapped_column(enum_column(Direction), nullable=False)
    order_type: Mapped[str] = mapped_column(String(32), nullable=False, default="market")
    quantity: Mapped[Decimal] = mapped_column(Quantity, nullable=False)
    requested_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    stop_loss: Mapped[Decimal | None] = mapped_column(Money)
    take_profit: Mapped[Decimal | None] = mapped_column(Money)
    time_in_force: Mapped[str] = mapped_column(String(16), nullable=False, default="GTC")
    status: Mapped[OrderIntentStatus] = mapped_column(
        enum_column(OrderIntentStatus),
        nullable=False,
        default=OrderIntentStatus.CREATED,
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    intent_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_intent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    signal: Mapped[Signal | None] = relationship()
    risk_decision: Mapped[RiskDecision | None] = relationship()
    broker_connection: Mapped[BrokerConnection] = relationship()


class BrokerOrder(IdModel, Base):
    __tablename__ = "broker_orders"

    order_intent_id: Mapped[str] = mapped_column(
        ForeignKey("order_intents.id"),
        nullable=False,
        index=True,
    )
    broker_connection_id: Mapped[str] = mapped_column(
        ForeignKey("broker_connections.id"),
        nullable=False,
        index=True,
    )
    external_order_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    status: Mapped[BrokerOrderStatus] = mapped_column(
        enum_column(BrokerOrderStatus),
        nullable=False,
        default=BrokerOrderStatus.CREATED,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    direction: Mapped[Direction] = mapped_column(enum_column(Direction), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Quantity, nullable=False)
    requested_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    filled_quantity: Mapped[Decimal] = mapped_column(Quantity, nullable=False, default=Decimal("0"))
    average_fill_price: Mapped[Decimal | None] = mapped_column(Money)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    order_intent: Mapped[OrderIntent] = relationship()
    broker_connection: Mapped[BrokerConnection] = relationship()


class BrokerFill(IdModel, Base):
    __tablename__ = "broker_fills"

    broker_order_id: Mapped[str] = mapped_column(
        ForeignKey("broker_orders.id"),
        nullable=False,
        index=True,
    )
    external_fill_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    direction: Mapped[Direction] = mapped_column(enum_column(Direction), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Quantity, nullable=False)
    price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    fees: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    filled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    broker_order: Mapped[BrokerOrder] = relationship()


class BrokerPositionSnapshot(IdModel, Base):
    __tablename__ = "broker_position_snapshots"

    broker_connection_id: Mapped[str] = mapped_column(
        ForeignKey("broker_connections.id"),
        nullable=False,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    direction: Mapped[Direction] = mapped_column(enum_column(Direction), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Quantity, nullable=False)
    average_entry_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    broker_connection: Mapped[BrokerConnection] = relationship()


class BrokerReconciliationReport(IdModel, Base):
    __tablename__ = "broker_reconciliation_reports"

    broker_connection_id: Mapped[str] = mapped_column(
        ForeignKey("broker_connections.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[ReconciliationStatus] = mapped_column(
        enum_column(ReconciliationStatus),
        nullable=False,
        default=ReconciliationStatus.NOT_READY,
        index=True,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    discrepancies: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    broker_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    aurex_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    reconciled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    broker_connection: Mapped[BrokerConnection] = relationship()


class PredictionMarket(IdModel, Base):
    __tablename__ = "prediction_markets"
    __table_args__ = (
        Index(
            "ix_prediction_markets_venue_event",
            "venue",
            "event_ticker",
            unique=True,
        ),
    )

    venue: Mapped[PredictionMarketVenue] = mapped_column(
        enum_column(PredictionMarketVenue),
        nullable=False,
        index=True,
    )
    event_ticker: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    category: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[PredictionMarketStatus] = mapped_column(
        enum_column(PredictionMarketStatus),
        nullable=False,
        default=PredictionMarketStatus.UNKNOWN,
        index=True,
    )
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    contracts: Mapped[list["PredictionContract"]] = relationship(back_populates="market")


class PredictionContract(IdModel, Base):
    __tablename__ = "prediction_contracts"
    __table_args__ = (
        Index(
            "ix_prediction_contracts_venue_ticker",
            "venue",
            "contract_ticker",
            unique=True,
        ),
    )

    market_id: Mapped[str] = mapped_column(
        ForeignKey("prediction_markets.id"),
        nullable=False,
        index=True,
    )
    venue: Mapped[PredictionMarketVenue] = mapped_column(
        enum_column(PredictionMarketVenue),
        nullable=False,
        index=True,
    )
    contract_ticker: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[PredictionMarketStatus] = mapped_column(
        enum_column(PredictionMarketStatus),
        nullable=False,
        default=PredictionMarketStatus.UNKNOWN,
        index=True,
    )
    yes_bid_price: Mapped[Decimal | None] = mapped_column(Ratio)
    yes_ask_price: Mapped[Decimal | None] = mapped_column(Ratio)
    no_bid_price: Mapped[Decimal | None] = mapped_column(Ratio)
    no_ask_price: Mapped[Decimal | None] = mapped_column(Ratio)
    expiration_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    settlement_value: Mapped[Decimal | None] = mapped_column(Ratio)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    market: Mapped[PredictionMarket] = relationship(back_populates="contracts")
    order_intents: Mapped[list["PredictionOrderIntent"]] = relationship(back_populates="contract")
    positions: Mapped[list["PredictionPosition"]] = relationship(back_populates="contract")
    settlements: Mapped[list["PredictionSettlement"]] = relationship(back_populates="contract")


class PredictionOrderIntent(IdModel, Base):
    __tablename__ = "prediction_order_intents"

    contract_id: Mapped[str] = mapped_column(
        ForeignKey("prediction_contracts.id"),
        nullable=False,
        index=True,
    )
    signal_id: Mapped[str | None] = mapped_column(ForeignKey("signals.id"), index=True)
    risk_decision_id: Mapped[str | None] = mapped_column(
        ForeignKey("risk_decisions.id"),
        index=True,
    )
    broker_connection_id: Mapped[str | None] = mapped_column(
        ForeignKey("broker_connections.id"),
        index=True,
    )
    strategy: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    side: Mapped[PredictionMarketSide] = mapped_column(
        enum_column(PredictionMarketSide),
        nullable=False,
        index=True,
    )
    action: Mapped[PredictionMarketOrderAction] = mapped_column(
        enum_column(PredictionMarketOrderAction),
        nullable=False,
    )
    order_type: Mapped[PredictionMarketOrderType] = mapped_column(
        enum_column(PredictionMarketOrderType),
        nullable=False,
        default=PredictionMarketOrderType.LIMIT,
    )
    quantity: Mapped[Decimal] = mapped_column(Quantity, nullable=False)
    limit_price: Mapped[Decimal] = mapped_column(Ratio, nullable=False)
    max_cost: Mapped[Decimal] = mapped_column(Money, nullable=False)
    expected_edge: Mapped[Decimal | None] = mapped_column(Ratio)
    confidence: Mapped[Decimal | None] = mapped_column(Ratio)
    status: Mapped[PredictionMarketOrderStatus] = mapped_column(
        enum_column(PredictionMarketOrderStatus),
        nullable=False,
        default=PredictionMarketOrderStatus.CREATED,
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    intent_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_intent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    contract: Mapped[PredictionContract] = relationship(back_populates="order_intents")
    signal: Mapped[Signal | None] = relationship()
    risk_decision: Mapped[RiskDecision | None] = relationship()
    broker_connection: Mapped[BrokerConnection | None] = relationship()
    orders: Mapped[list["PredictionOrder"]] = relationship(back_populates="order_intent")


class PredictionOrder(IdModel, Base):
    __tablename__ = "prediction_orders"

    order_intent_id: Mapped[str] = mapped_column(
        ForeignKey("prediction_order_intents.id"),
        nullable=False,
        index=True,
    )
    broker_connection_id: Mapped[str | None] = mapped_column(
        ForeignKey("broker_connections.id"),
        index=True,
    )
    external_order_id: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    status: Mapped[PredictionMarketOrderStatus] = mapped_column(
        enum_column(PredictionMarketOrderStatus),
        nullable=False,
        default=PredictionMarketOrderStatus.CREATED,
        index=True,
    )
    side: Mapped[PredictionMarketSide] = mapped_column(
        enum_column(PredictionMarketSide),
        nullable=False,
        index=True,
    )
    action: Mapped[PredictionMarketOrderAction] = mapped_column(
        enum_column(PredictionMarketOrderAction),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(Quantity, nullable=False)
    filled_quantity: Mapped[Decimal] = mapped_column(Quantity, nullable=False, default=Decimal("0"))
    limit_price: Mapped[Decimal] = mapped_column(Ratio, nullable=False)
    average_fill_price: Mapped[Decimal | None] = mapped_column(Ratio)
    fees: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    order_intent: Mapped[PredictionOrderIntent] = relationship(back_populates="orders")
    broker_connection: Mapped[BrokerConnection | None] = relationship()
    fills: Mapped[list["PredictionFill"]] = relationship(back_populates="order")


class PredictionFill(IdModel, Base):
    __tablename__ = "prediction_fills"

    order_id: Mapped[str] = mapped_column(
        ForeignKey("prediction_orders.id"),
        nullable=False,
        index=True,
    )
    external_fill_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    side: Mapped[PredictionMarketSide] = mapped_column(
        enum_column(PredictionMarketSide),
        nullable=False,
        index=True,
    )
    action: Mapped[PredictionMarketOrderAction] = mapped_column(
        enum_column(PredictionMarketOrderAction),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(Quantity, nullable=False)
    price: Mapped[Decimal] = mapped_column(Ratio, nullable=False)
    fees: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    filled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    order: Mapped[PredictionOrder] = relationship(back_populates="fills")


class PredictionPosition(IdModel, Base):
    __tablename__ = "prediction_positions"
    __table_args__ = (
        Index(
            "ix_prediction_positions_contract_side_status",
            "contract_id",
            "side",
            "status",
        ),
    )

    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), index=True)
    contract_id: Mapped[str] = mapped_column(
        ForeignKey("prediction_contracts.id"),
        nullable=False,
        index=True,
    )
    side: Mapped[PredictionMarketSide] = mapped_column(
        enum_column(PredictionMarketSide),
        nullable=False,
        index=True,
    )
    quantity: Mapped[Decimal] = mapped_column(Quantity, nullable=False)
    average_entry_price: Mapped[Decimal] = mapped_column(Ratio, nullable=False)
    realized_pl: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    fees: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    status: Mapped[PredictionMarketPositionStatus] = mapped_column(
        enum_column(PredictionMarketPositionStatus),
        nullable=False,
        default=PredictionMarketPositionStatus.OPEN,
        index=True,
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    account: Mapped[Account | None] = relationship()
    contract: Mapped[PredictionContract] = relationship(back_populates="positions")
    settlements: Mapped[list["PredictionSettlement"]] = relationship(back_populates="position")


class PredictionSettlement(IdModel, Base):
    __tablename__ = "prediction_settlements"

    contract_id: Mapped[str] = mapped_column(
        ForeignKey("prediction_contracts.id"),
        nullable=False,
        index=True,
    )
    position_id: Mapped[str | None] = mapped_column(
        ForeignKey("prediction_positions.id"),
        index=True,
    )
    settlement_value: Mapped[Decimal] = mapped_column(Ratio, nullable=False)
    gross_payout: Mapped[Decimal] = mapped_column(Money, nullable=False)
    realized_pl: Mapped[Decimal] = mapped_column(Money, nullable=False)
    fees: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    settled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    contract: Mapped[PredictionContract] = relationship(back_populates="settlements")
    position: Mapped[PredictionPosition | None] = relationship(back_populates="settlements")


class PredictionReconciliationReport(IdModel, Base):
    __tablename__ = "prediction_reconciliation_reports"

    broker_connection_id: Mapped[str | None] = mapped_column(
        ForeignKey("broker_connections.id"),
        index=True,
    )
    status: Mapped[ReconciliationStatus] = mapped_column(
        enum_column(ReconciliationStatus),
        nullable=False,
        default=ReconciliationStatus.NOT_READY,
        index=True,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    discrepancies: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    venue_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    aurex_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    reconciled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    broker_connection: Mapped[BrokerConnection | None] = relationship()


class PredictionEvidenceEvent(IdModel, Base):
    __tablename__ = "prediction_evidence_events"

    kind: Mapped[PredictionMarketEvidenceKind] = mapped_column(
        enum_column(PredictionMarketEvidenceKind),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(128), index=True)
    strategy: Mapped[str | None] = mapped_column(String(100), index=True)
    contract_ticker: Mapped[str | None] = mapped_column(String(160), index=True)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LiveReadinessCheck(IdModel, Base):
    __tablename__ = "live_readiness_checks"

    check_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[ReadinessStatus] = mapped_column(
        enum_column(ReadinessStatus),
        nullable=False,
        default=ReadinessStatus.NOT_RUN,
        index=True,
    )
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    evidence_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LiveDeploymentPlan(IdModel, Base):
    __tablename__ = "live_deployment_plans"

    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    broker_connection_id: Mapped[str | None] = mapped_column(
        ForeignKey("broker_connections.id"),
        index=True,
    )
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), index=True)
    strategy: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    symbols: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[LiveDeploymentStatus] = mapped_column(
        enum_column(LiveDeploymentStatus),
        nullable=False,
        default=LiveDeploymentStatus.BLOCKED,
        index=True,
    )
    risk_per_trade: Mapped[Decimal] = mapped_column(
        Ratio,
        nullable=False,
        default=Decimal("0.0025"),
    )
    max_daily_loss: Mapped[Decimal] = mapped_column(
        Ratio,
        nullable=False,
        default=Decimal("0.01"),
    )
    max_weekly_loss: Mapped[Decimal] = mapped_column(
        Ratio,
        nullable=False,
        default=Decimal("0.03"),
    )
    max_open_positions: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    target_net_profit: Mapped[Decimal] = mapped_column(
        Money,
        nullable=False,
        default=Decimal("100"),
    )
    live_trading_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approval_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    rules_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    halted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    broker_connection: Mapped[BrokerConnection | None] = relationship()
    account: Mapped[Account | None] = relationship()


class LiveDeploymentGate(IdModel, Base):
    __tablename__ = "live_deployment_gates"
    __table_args__ = (
        Index(
            "ix_live_deployment_gates_plan_key",
            "live_deployment_plan_id",
            "gate_key",
            unique=True,
        ),
    )

    live_deployment_plan_id: Mapped[str] = mapped_column(
        ForeignKey("live_deployment_plans.id"),
        nullable=False,
        index=True,
    )
    gate_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[ReadinessStatus] = mapped_column(
        enum_column(ReadinessStatus),
        nullable=False,
        default=ReadinessStatus.NOT_RUN,
        index=True,
    )
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    evidence_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    live_deployment_plan: Mapped[LiveDeploymentPlan] = relationship()


class LiveDailyReviewReport(IdModel, Base):
    __tablename__ = "live_daily_review_reports"
    __table_args__ = (
        Index(
            "ix_live_daily_review_reports_plan_date",
            "live_deployment_plan_id",
            "review_date",
            unique=True,
        ),
    )

    live_deployment_plan_id: Mapped[str] = mapped_column(
        ForeignKey("live_deployment_plans.id"),
        nullable=False,
        index=True,
    )
    review_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[LiveDailyReviewStatus] = mapped_column(
        enum_column(LiveDailyReviewStatus),
        nullable=False,
        default=LiveDailyReviewStatus.BLOCKED,
        index=True,
    )
    realized_pl: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    trade_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rule_violations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    reconciliation_status: Mapped[ReconciliationStatus] = mapped_column(
        enum_column(ReconciliationStatus),
        nullable=False,
        default=ReconciliationStatus.NOT_READY,
        index=True,
    )
    review_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    live_deployment_plan: Mapped[LiveDeploymentPlan] = relationship()


class LiveApprovalRecord(IdModel, Base):
    __tablename__ = "live_approval_records"

    live_deployment_plan_id: Mapped[str] = mapped_column(
        ForeignKey("live_deployment_plans.id"),
        nullable=False,
        index=True,
    )
    approval_type: Mapped[LiveApprovalType] = mapped_column(
        enum_column(LiveApprovalType),
        nullable=False,
        index=True,
    )
    status: Mapped[LiveApprovalStatus] = mapped_column(
        enum_column(LiveApprovalStatus),
        nullable=False,
        default=LiveApprovalStatus.PENDING,
        index=True,
    )
    approver: Mapped[str] = mapped_column(String(120), nullable=False)
    evidence_reference: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    evidence_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    live_deployment_plan: Mapped[LiveDeploymentPlan] = relationship()


class LivePaperEvidenceReport(IdModel, Base):
    __tablename__ = "live_paper_evidence_reports"

    live_deployment_plan_id: Mapped[str] = mapped_column(
        ForeignKey("live_deployment_plans.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[ReadinessStatus] = mapped_column(
        enum_column(ReadinessStatus),
        nullable=False,
        default=ReadinessStatus.NOT_RUN,
        index=True,
    )
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    minimum_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    first_trade_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latest_trade_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    calendar_days_observed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    minimum_calendar_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    expectancy: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    profit_factor: Mapped[Decimal | None] = mapped_column(Ratio)
    win_rate: Mapped[Decimal] = mapped_column(Ratio, nullable=False, default=Decimal("0"))
    max_drawdown: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    max_allowed_drawdown: Mapped[Decimal] = mapped_column(
        Money,
        nullable=False,
        default=Decimal("0"),
    )
    unexplained_trade_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    risk_rule_violation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    journaled_trade_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unjournaled_trade_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    journal_rule_violation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    total_net_pl: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    reasons: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    requirements_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evidence_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    live_deployment_plan: Mapped[LiveDeploymentPlan] = relationship()


class LiveBrokerStatementReport(IdModel, Base):
    __tablename__ = "live_broker_statement_reports"

    live_deployment_plan_id: Mapped[str] = mapped_column(
        ForeignKey("live_deployment_plans.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[ReadinessStatus] = mapped_column(
        enum_column(ReadinessStatus),
        nullable=False,
        default=ReadinessStatus.NOT_RUN,
        index=True,
    )
    statement_reference: Mapped[str] = mapped_column(Text, nullable=False)
    statement_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    statement_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    broker_trade_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    aurex_trade_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    broker_net_pl: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    aurex_net_pl: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    broker_fees: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    aurex_fees: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    broker_slippage: Mapped[Decimal] = mapped_column(
        Money,
        nullable=False,
        default=Decimal("0"),
    )
    aurex_slippage: Mapped[Decimal] = mapped_column(
        Money,
        nullable=False,
        default=Decimal("0"),
    )
    discrepancies: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    statement_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    aurex_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)
    reconciled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    live_deployment_plan: Mapped[LiveDeploymentPlan] = relationship()


class LiveProfitMilestoneReport(IdModel, Base):
    __tablename__ = "live_profit_milestone_reports"

    live_deployment_plan_id: Mapped[str] = mapped_column(
        ForeignKey("live_deployment_plans.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[ReadinessStatus] = mapped_column(
        enum_column(ReadinessStatus),
        nullable=False,
        default=ReadinessStatus.NOT_RUN,
        index=True,
    )
    target_net_profit: Mapped[Decimal] = mapped_column(
        Money,
        nullable=False,
        default=Decimal("100"),
    )
    total_net_pl: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    trade_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_trade_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latest_trade_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    journaled_trade_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unjournaled_trade_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    journal_rule_violation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    unexplained_trade_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    risk_rule_violation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    daily_loss_breach_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    weekly_loss_breach_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    broker_statement_report_id: Mapped[str | None] = mapped_column(
        ForeignKey("live_broker_statement_reports.id"),
        index=True,
    )
    broker_statement_status: Mapped[ReadinessStatus | None] = mapped_column(
        enum_column(ReadinessStatus),
    )
    kill_switch_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    live_execution_adapter_implemented: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    reasons: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    requirements_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evidence_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    live_deployment_plan: Mapped[LiveDeploymentPlan] = relationship()
    broker_statement_report: Mapped[LiveBrokerStatementReport | None] = relationship()


class StrategyEvidenceReview(IdModel, Base):
    __tablename__ = "strategy_evidence_reviews"

    live_deployment_plan_id: Mapped[str] = mapped_column(
        ForeignKey("live_deployment_plans.id"),
        nullable=False,
        index=True,
    )
    decision: Mapped[StrategyEvidenceDecision] = mapped_column(
        enum_column(StrategyEvidenceDecision),
        nullable=False,
        index=True,
    )
    strategy: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    symbols: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    reasons: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    next_actions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    gate_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evidence_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    live_deployment_plan: Mapped[LiveDeploymentPlan] = relationship()


class LiveApprovalPacket(IdModel, Base):
    __tablename__ = "live_approval_packets"

    live_deployment_plan_id: Mapped[str] = mapped_column(
        ForeignKey("live_deployment_plans.id"),
        nullable=False,
        index=True,
    )
    broker_connection_id: Mapped[str | None] = mapped_column(
        ForeignKey("broker_connections.id"),
        index=True,
    )
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), index=True)
    status: Mapped[LiveApprovalPacketStatus] = mapped_column(
        enum_column(LiveApprovalPacketStatus),
        nullable=False,
        default=LiveApprovalPacketStatus.DRAFT,
        index=True,
    )
    broker_name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_label: Mapped[str] = mapped_column(String(120), nullable=False)
    account_type: Mapped[str] = mapped_column(String(80), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(80), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(120), nullable=False)
    currency: Mapped[str] = mapped_column(String(12), nullable=False, default="USD")
    broker_terms_reference: Mapped[str | None] = mapped_column(Text)
    fee_schedule_reference: Mapped[str | None] = mapped_column(Text)
    margin_policy_reference: Mapped[str | None] = mapped_column(Text)
    account_constraints_reference: Mapped[str] = mapped_column(Text, nullable=False)
    execution_policy_reference: Mapped[str] = mapped_column(Text, nullable=False)
    fee_slippage_model_reference: Mapped[str] = mapped_column(Text, nullable=False)
    paper_to_live_checklist_reference: Mapped[str] = mapped_column(Text, nullable=False)
    sandbox_test_reference: Mapped[str | None] = mapped_column(Text)
    leverage_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tax_notes: Mapped[str | None] = mapped_column(Text)
    credentials_stored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    evidence_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    live_deployment_plan: Mapped[LiveDeploymentPlan] = relationship()
    broker_connection: Mapped[BrokerConnection | None] = relationship()
    account: Mapped[Account | None] = relationship()


class SystemEvent(IdModel, Base):
    __tablename__ = "system_events"

    severity: Mapped[SystemEventSeverity] = mapped_column(
        enum_column(SystemEventSeverity),
        nullable=False,
        default=SystemEventSeverity.INFO,
        index=True,
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
