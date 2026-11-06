from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from aurex.domain.enums import MarketRegime


class MarketCandleInput(BaseModel):
    timestamp: datetime
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    volume: Decimal = Field(ge=0)


class CandleImportRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    timeframe: str = Field(min_length=1, max_length=32)
    source: str | None = Field(default=None, max_length=100)
    candles: list[MarketCandleInput] = Field(min_length=1)


class CandleImportResponse(BaseModel):
    imported: int
    updated: int
    symbol: str
    timeframe: str


class MarketStateComputeRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    timeframe: str = Field(min_length=1, max_length=32)
    higher_timeframe: str | None = Field(default=None, max_length=32)
    limit: int = Field(default=240, ge=50, le=1000)


class MarketStateResponse(BaseModel):
    id: str
    signal_id: str | None
    symbol: str
    timeframe: str
    regime: MarketRegime
    confidence: Decimal | None
    inputs_snapshot: dict
    calculated_at: datetime

    model_config = ConfigDict(from_attributes=True)

