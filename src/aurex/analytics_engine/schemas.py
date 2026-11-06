from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class StrategyPerformance(BaseModel):
    strategy: str
    total_trades: int
    total_net_pl: Decimal

    model_config = ConfigDict(from_attributes=True)


class RegimePerformance(BaseModel):
    market_regime: str
    total_trades: int
    total_net_pl: Decimal

    model_config = ConfigDict(from_attributes=True)


class PerformanceSummaryResponse(BaseModel):
    total_trades: int
    wins: int
    losses: int
    breakeven: int
    win_rate: Decimal
    average_win: Decimal
    average_loss: Decimal
    expectancy: Decimal
    profit_factor: Decimal | None
    max_drawdown: Decimal
    total_net_pl: Decimal
    best_strategy: StrategyPerformance | None
    worst_strategy: StrategyPerformance | None
    by_strategy: list[StrategyPerformance]
    by_regime: list[RegimePerformance]

    model_config = ConfigDict(from_attributes=True)


class EquityCurvePointResponse(BaseModel):
    id: str
    account_id: str
    equity: Decimal
    realized_pl: Decimal
    drawdown: Decimal
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EquityCurveResponse(BaseModel):
    points: list[EquityCurvePointResponse]
    point_count: int
    latest_equity: Decimal | None
    max_drawdown: Decimal
    total_realized_pl: Decimal
