from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from aurex.domain.enums import AnalystNoteType, SystemEventSeverity


class AnalystNoteResponse(BaseModel):
    id: str
    trade_id: str | None
    strategy: str | None
    symbol: str | None
    note_type: AnalystNoteType
    severity: SystemEventSeverity
    title: str
    summary: str
    recommendation: str | None
    confidence: Decimal | None
    evidence_snapshot: dict
    model_name: str
    advisory_only: bool
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnalystSummaryResponse(BaseModel):
    advisory_only: bool
    closed_trades: int
    note_count: int
    warning_count: int
    critical_count: int
    latest_notes: list[AnalystNoteResponse]
    headline: str
    evidence_snapshot: dict


class SimilarTradeItem(BaseModel):
    trade_id: str
    strategy: str
    symbol: str
    timeframe: str
    market_regime: str
    direction: str
    realized_pl: Decimal | None
    r_multiple: Decimal | None
    similarity_score: Decimal


class PatternSimilarityResponse(BaseModel):
    advisory_only: bool
    source_trade_id: str
    similar_trades: list[SimilarTradeItem]
    note: AnalystNoteResponse


class AnalystScanResponse(BaseModel):
    advisory_only: bool
    created_notes: list[AnalystNoteResponse]
    scanned_trades: int
    message: str


class AnalystScanRequest(BaseModel):
    strategy: str | None = Field(default=None, min_length=1, max_length=100)
    limit: int = Field(default=100, ge=1, le=500)
