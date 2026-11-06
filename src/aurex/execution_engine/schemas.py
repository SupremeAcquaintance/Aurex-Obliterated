from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from aurex.domain.enums import Direction, MarketRegime, ReadinessStatus, TradeStatus


class TradeResponse(BaseModel):
    id: str
    account_id: str
    paper_order_id: str
    strategy: str
    symbol: str
    timeframe: str
    direction: Direction
    status: TradeStatus
    market_regime: MarketRegime
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    quantity: Decimal
    risk_amount: Decimal
    opened_at: datetime
    exit_price: Decimal | None
    closed_at: datetime | None
    realized_pl: Decimal | None
    r_multiple: Decimal | None
    fees: Decimal
    slippage: Decimal
    close_reason: str | None

    model_config = ConfigDict(from_attributes=True)


class CloseTradeRequest(BaseModel):
    trade_id: str = Field(min_length=1)
    exit_price: Decimal = Field(gt=0)
    close_reason: str = Field(min_length=1, max_length=500)
    fees: Decimal | None = Field(default=None, ge=0)
    slippage: Decimal | None = Field(default=None, ge=0)


class PaperResetResponse(BaseModel):
    account_equity: Decimal
    deleted_trades: int
    deleted_orders: int
    deleted_positions: int
    deleted_equity_points: int


class PaperEvidenceCsvImportRequest(BaseModel):
    source: str = Field(min_length=1, max_length=64)
    source_reference: str = Field(min_length=1, max_length=1000)
    csv_text: str = Field(min_length=1)


class PaperEvidenceImportBatchResponse(BaseModel):
    id: str
    account_id: str
    source: str
    source_reference: str
    import_hash: str
    status: str
    rows_received: int
    imported_count: int
    skipped_count: int
    rejected_count: int
    required_headers: list[str]
    row_results: list[dict[str, Any]]
    analysis_summary: dict[str, Any] = Field(default_factory=dict)
    evidence_snapshot: dict[str, Any]
    imported_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaperEvidenceCsvPreflightResponse(BaseModel):
    source: str
    source_reference: str
    import_hash: str
    status: str
    rows_received: int
    importable_count: int
    skipped_count: int
    rejected_count: int
    required_headers: list[str]
    row_results: list[dict[str, Any]]
    analysis_summary: dict[str, Any]
    deployment_strategy: str | None
    deployment_symbols: list[str]
    scope_status: str
    scoped_importable_count: int
    out_of_scope_importable_count: int
    out_of_scope_import_summary: list[dict[str, Any]]
    scope_next_action: str
    checked_at: datetime


class PaperEvidenceCollectionStatusResponse(BaseModel):
    status: ReadinessStatus
    plan_id: str
    strategy: str
    symbols: list[str]
    accepted_backtest_status: ReadinessStatus
    paper_evidence_status: ReadinessStatus
    paper_evidence_freshness_reasons: list[str]
    latest_paper_evidence_report_id: str | None
    latest_import_batch_id: str | None
    latest_imported_at: datetime | None
    imported_batch_count: int
    rows_received: int
    imported_count: int
    scoped_imported_count: int
    out_of_scope_imported_count: int
    out_of_scope_import_summary: list[dict[str, Any]]
    skipped_count: int
    rejected_count: int
    total_trades: int
    minimum_trades: int
    trades_remaining: int
    calendar_days_observed: int
    minimum_calendar_days: int
    calendar_days_remaining: int
    active_trading_days: int
    minimum_active_trading_days: int
    active_days_remaining: int
    max_single_day_trade_share: Decimal
    max_single_day_trade_share_limit: Decimal
    in_scope_trade_count: int
    out_of_scope_trade_count: int
    evidence_grade_trade_count: int
    non_evidence_grade_trade_count: int
    execution_quality_violation_count: int
    fill_model_counts: dict[str, int]
    unjournaled_trade_count: int
    journal_rule_violation_count: int
    unexplained_trade_count: int
    risk_rule_violation_count: int
    blocking_reasons: list[str]
    next_actions: list[str]
