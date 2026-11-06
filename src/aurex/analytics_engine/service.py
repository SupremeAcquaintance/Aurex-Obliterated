from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from aurex.analytics_engine.schemas import (
    EquityCurveResponse,
    RegimePerformance,
    StrategyPerformance,
)
from aurex.db.models import EquityCurvePoint, PaperTrade
from aurex.domain.enums import TradeStatus

ZERO = Decimal("0")


@dataclass(frozen=True)
class PerformanceSummary:
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


class AnalyticsEngine:
    def __init__(self, session: Session) -> None:
        self.session = session

    def performance_summary(self) -> PerformanceSummary:
        trades = list(
            self.session.execute(
                select(PaperTrade).where(
                    PaperTrade.status == TradeStatus.CLOSED,
                    PaperTrade.realized_pl.is_not(None),
                )
            ).scalars()
        )

        return summarize_paper_trades(trades, max_drawdown=self._max_drawdown())

    def equity_curve(self, limit: int = 250) -> EquityCurveResponse:
        limited_points = list(
            self.session.execute(
                select(EquityCurvePoint)
                .order_by(EquityCurvePoint.recorded_at.desc())
                .limit(limit)
            ).scalars()
        )
        points = sorted(limited_points, key=lambda point: point.recorded_at)
        return EquityCurveResponse(
            points=points,
            point_count=len(points),
            latest_equity=points[-1].equity if points else None,
            max_drawdown=max((point.drawdown or ZERO for point in points), default=ZERO),
            total_realized_pl=sum((point.realized_pl or ZERO for point in points), ZERO),
        )

    def _max_drawdown(self) -> Decimal:
        drawdowns = self.session.execute(select(EquityCurvePoint.drawdown)).scalars().all()
        if not drawdowns:
            return ZERO
        return max((value or ZERO for value in drawdowns), default=ZERO)

    def _strategy_breakdown(self, trades: list[PaperTrade]) -> list[StrategyPerformance]:
        return strategy_breakdown(trades)


def summarize_paper_trades(
    trades: list[PaperTrade],
    max_drawdown: Decimal | None = None,
) -> PerformanceSummary:
    if not trades:
        return PerformanceSummary(
            total_trades=0,
            wins=0,
            losses=0,
            breakeven=0,
            win_rate=ZERO,
            average_win=ZERO,
            average_loss=ZERO,
            expectancy=ZERO,
            profit_factor=None,
            max_drawdown=ZERO,
            total_net_pl=ZERO,
            best_strategy=None,
            worst_strategy=None,
            by_strategy=[],
            by_regime=[],
        )

    realized_values = [trade.realized_pl or ZERO for trade in trades]
    wins = [value for value in realized_values if value > 0]
    losses = [abs(value) for value in realized_values if value < 0]
    breakeven = sum(1 for value in realized_values if value == 0)
    total_trades = len(trades)
    total_net_pl = sum(realized_values, ZERO)
    gross_profit = sum(wins, ZERO)
    gross_loss = sum(losses, ZERO)
    win_count = len(wins)
    loss_count = len(losses)

    average_win = gross_profit / win_count if win_count else ZERO
    average_loss = gross_loss / loss_count if loss_count else ZERO
    win_rate = Decimal(win_count) / Decimal(total_trades)
    loss_rate = Decimal(loss_count) / Decimal(total_trades)
    expectancy = (win_rate * average_win) - (loss_rate * average_loss)
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None
    scoped_drawdown = max_drawdown if max_drawdown is not None else trade_sequence_drawdown(trades)

    by_strategy = strategy_breakdown(trades)
    by_regime = regime_breakdown(trades)

    return PerformanceSummary(
        total_trades=total_trades,
        wins=win_count,
        losses=loss_count,
        breakeven=breakeven,
        win_rate=win_rate,
        average_win=average_win,
        average_loss=average_loss,
        expectancy=expectancy,
        profit_factor=profit_factor,
        max_drawdown=scoped_drawdown,
        total_net_pl=total_net_pl,
        best_strategy=by_strategy[0] if by_strategy else None,
        worst_strategy=by_strategy[-1] if by_strategy else None,
        by_strategy=by_strategy,
        by_regime=by_regime,
    )


def trade_sequence_drawdown(trades: list[PaperTrade]) -> Decimal:
    equity = ZERO
    high_water = ZERO
    max_drawdown = ZERO
    for trade in sorted(trades, key=lambda item: item.closed_at or item.opened_at):
        equity += trade.realized_pl or ZERO
        high_water = max(high_water, equity)
        max_drawdown = max(max_drawdown, high_water - equity)
    return max_drawdown


def strategy_breakdown(trades: list[PaperTrade]) -> list[StrategyPerformance]:
    totals: dict[str, Decimal] = defaultdict(lambda: ZERO)
    counts: dict[str, int] = defaultdict(int)

    for trade in trades:
        totals[trade.strategy] += trade.realized_pl or ZERO
        counts[trade.strategy] += 1

    return sorted(
        [
            StrategyPerformance(
                strategy=strategy,
                total_trades=counts[strategy],
                total_net_pl=total_net_pl,
            )
            for strategy, total_net_pl in totals.items()
        ],
        key=lambda item: (item.total_net_pl, item.strategy),
        reverse=True,
    )


def regime_breakdown(trades: list[PaperTrade]) -> list[RegimePerformance]:
    totals: dict[str, Decimal] = defaultdict(lambda: ZERO)
    counts: dict[str, int] = defaultdict(int)

    for trade in trades:
        regime = trade.market_regime.value
        totals[regime] += trade.realized_pl or ZERO
        counts[regime] += 1

    return sorted(
        [
            RegimePerformance(
                market_regime=market_regime,
                total_trades=counts[market_regime],
                total_net_pl=total_net_pl,
            )
            for market_regime, total_net_pl in totals.items()
        ],
        key=lambda item: (item.total_net_pl, item.market_regime),
        reverse=True,
    )
