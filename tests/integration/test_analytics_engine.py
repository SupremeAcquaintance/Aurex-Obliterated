from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from aurex.analytics_engine.service import AnalyticsEngine
from aurex.db.base import Base
from aurex.db.models import (
    Account,
    EquityCurvePoint,
    PaperOrder,
    PaperTrade,
    RiskDecision,
    Signal,
)
from aurex.domain.enums import (
    Direction,
    MarketRegime,
    OrderStatus,
    SignalStatus,
    TradeStatus,
)


@pytest.fixture()
def session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as db_session:
        yield db_session

    Base.metadata.drop_all(engine)


def test_performance_summary_handles_zero_trade_state(session: Session) -> None:
    summary = AnalyticsEngine(session).performance_summary()

    assert summary.total_trades == 0
    assert summary.wins == 0
    assert summary.losses == 0
    assert summary.win_rate == Decimal("0")
    assert summary.expectancy == Decimal("0")
    assert summary.profit_factor is None
    assert summary.max_drawdown == Decimal("0")
    assert summary.best_strategy is None
    assert summary.worst_strategy is None
    assert summary.by_strategy == []
    assert summary.by_regime == []


def test_performance_summary_matches_known_fixture_data(session: Session) -> None:
    account = Account(
        name="paper-main",
        mode="paper",
        currency="USD",
        starting_equity=Decimal("1000"),
        current_equity=Decimal("1015"),
    )
    session.add(account)
    session.flush()
    now = datetime(2026, 6, 6, 10, tzinfo=UTC)

    add_closed_trade(
        session,
        account,
        now,
        strategy="trend_pullback_v1",
        market_regime=MarketRegime.TRENDING_UP,
        realized_pl=Decimal("10"),
    )
    add_closed_trade(
        session,
        account,
        now + timedelta(minutes=15),
        strategy="trend_pullback_v1",
        market_regime=MarketRegime.TRENDING_UP,
        realized_pl=Decimal("-5"),
    )
    add_closed_trade(
        session,
        account,
        now + timedelta(minutes=30),
        strategy="volatility_breakout_v1",
        market_regime=MarketRegime.BREAKOUT_EXPANSION,
        realized_pl=Decimal("20"),
    )
    add_closed_trade(
        session,
        account,
        now + timedelta(minutes=45),
        strategy="range_mean_reversion_v1",
        market_regime=MarketRegime.RANGING,
        realized_pl=Decimal("-10"),
    )
    session.add_all(
        [
            EquityCurvePoint(
                account_id=account.id,
                equity=Decimal("1010"),
                realized_pl=Decimal("10"),
                drawdown=Decimal("0"),
                recorded_at=now,
            ),
            EquityCurvePoint(
                account_id=account.id,
                equity=Decimal("1005"),
                realized_pl=Decimal("-5"),
                drawdown=Decimal("5"),
                recorded_at=now + timedelta(minutes=15),
            ),
            EquityCurvePoint(
                account_id=account.id,
                equity=Decimal("1025"),
                realized_pl=Decimal("20"),
                drawdown=Decimal("0"),
                recorded_at=now + timedelta(minutes=30),
            ),
            EquityCurvePoint(
                account_id=account.id,
                equity=Decimal("1015"),
                realized_pl=Decimal("-10"),
                drawdown=Decimal("10"),
                recorded_at=now + timedelta(minutes=45),
            ),
        ]
    )
    session.flush()

    summary = AnalyticsEngine(session).performance_summary()

    assert summary.total_trades == 4
    assert summary.wins == 2
    assert summary.losses == 2
    assert summary.breakeven == 0
    assert summary.win_rate == Decimal("0.5")
    assert summary.average_win == Decimal("15")
    assert summary.average_loss == Decimal("7.5")
    assert summary.expectancy == Decimal("3.75")
    assert summary.profit_factor == Decimal("2")
    assert summary.max_drawdown == Decimal("10.00000000")
    assert summary.total_net_pl == Decimal("15.00000000")
    assert summary.best_strategy.strategy == "volatility_breakout_v1"
    assert summary.best_strategy.total_net_pl == Decimal("20.00000000")
    assert summary.worst_strategy.strategy == "range_mean_reversion_v1"
    assert summary.worst_strategy.total_net_pl == Decimal("-10.00000000")
    assert summary.by_regime[0].market_regime == MarketRegime.BREAKOUT_EXPANSION
    assert summary.by_regime[0].total_net_pl == Decimal("20.00000000")


def test_equity_curve_returns_limited_points_in_chronological_order(session: Session) -> None:
    account = Account(
        name="paper-main",
        mode="paper",
        currency="USD",
        starting_equity=Decimal("1000"),
        current_equity=Decimal("1015"),
    )
    session.add(account)
    session.flush()
    now = datetime(2026, 6, 6, 10, tzinfo=UTC)
    session.add_all(
        [
            EquityCurvePoint(
                account_id=account.id,
                equity=Decimal("1010"),
                realized_pl=Decimal("10"),
                drawdown=Decimal("0"),
                recorded_at=now,
            ),
            EquityCurvePoint(
                account_id=account.id,
                equity=Decimal("1005"),
                realized_pl=Decimal("-5"),
                drawdown=Decimal("5"),
                recorded_at=now + timedelta(minutes=15),
            ),
            EquityCurvePoint(
                account_id=account.id,
                equity=Decimal("1025"),
                realized_pl=Decimal("20"),
                drawdown=Decimal("0"),
                recorded_at=now + timedelta(minutes=30),
            ),
        ]
    )
    session.flush()

    curve = AnalyticsEngine(session).equity_curve(limit=2)

    assert curve.point_count == 2
    assert [point.equity for point in curve.points] == [
        Decimal("1005.00000000"),
        Decimal("1025.00000000"),
    ]
    assert curve.latest_equity == Decimal("1025.00000000")
    assert curve.max_drawdown == Decimal("5.00000000")
    assert curve.total_realized_pl == Decimal("15.00000000")


def add_closed_trade(
    session: Session,
    account: Account,
    timestamp: datetime,
    *,
    strategy: str,
    market_regime: MarketRegime,
    realized_pl: Decimal,
) -> None:
    signal = Signal(
        source="tradingview",
        strategy=strategy,
        symbol="BTCUSDT",
        timeframe="15m",
        direction=Direction.LONG,
        entry_price=Decimal("100"),
        stop_loss=Decimal("95"),
        take_profit=Decimal("110"),
        market_regime=market_regime,
        status=SignalStatus.PAPER_EXECUTED,
        idempotency_key=f"{strategy}:{timestamp.isoformat()}",
        raw_payload={},
        normalized_payload={},
        source_timestamp=timestamp,
        received_at=timestamp,
        processed_at=timestamp,
    )
    session.add(signal)
    session.flush()

    decision = RiskDecision(
        signal=signal,
        approved=True,
        reason="Fixture approved",
        reward_risk=Decimal("2"),
        risk_amount=Decimal("5"),
        position_size=Decimal("1"),
        account_equity=Decimal("1000"),
        rules_snapshot={},
    )
    session.add(decision)
    session.flush()

    order = PaperOrder(
        signal=signal,
        risk_decision_id=decision.id,
        symbol="BTCUSDT",
        direction=Direction.LONG,
        order_type="market",
        status=OrderStatus.FILLED,
        requested_price=Decimal("100"),
        filled_price=Decimal("100"),
        quantity=Decimal("1"),
        created_order_at=timestamp,
        filled_at=timestamp,
    )
    session.add(order)
    session.flush()

    trade = PaperTrade(
        account=account,
        paper_order=order,
        strategy=strategy,
        symbol="BTCUSDT",
        timeframe="15m",
        direction=Direction.LONG,
        status=TradeStatus.CLOSED,
        market_regime=market_regime,
        entry_price=Decimal("100"),
        stop_loss=Decimal("95"),
        take_profit=Decimal("110"),
        quantity=Decimal("1"),
        risk_amount=Decimal("5"),
        opened_at=timestamp,
        exit_price=Decimal("100") + realized_pl,
        closed_at=timestamp + timedelta(minutes=1),
        realized_pl=realized_pl,
        r_multiple=realized_pl / Decimal("5"),
        close_reason="fixture",
    )
    session.add(trade)
