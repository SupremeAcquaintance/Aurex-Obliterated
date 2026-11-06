from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from aurex.api.app import create_app
from aurex.api.dependencies import get_db
from aurex.backtest_engine.service import (
    TREND_PULLBACK_V1_PARAMETER_TEMPLATE,
    strategy_parameter_fingerprint,
)
from aurex.config.settings import get_settings
from aurex.db.base import Base
from aurex.db.models import Account, PaperOrder, PaperTrade, RiskDecision, Signal
from aurex.domain.enums import (
    Direction,
    MarketRegime,
    OrderStatus,
    SignalStatus,
    TradeStatus,
)
from tests.integration.backtest_helpers import post_accepted_backtest


@pytest.fixture()
def client() -> Generator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    app = create_app()

    def override_get_db() -> Generator[Session]:
        with session_factory() as db_session:
            yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def auth_headers() -> dict[str, str]:
    return {"X-Aurex-Webhook-Secret": get_settings().webhook_secret}


def webhook_payload(
    *,
    strategy: str = "trend_pullback_v1",
    market_regime: MarketRegime = MarketRegime.TRENDING_UP,
    timestamp: datetime | None = None,
) -> dict:
    return {
        "source": "tradingview",
        "strategy": strategy,
        "strategy_version": "1.3.0",
        "settings_fingerprint": strategy_parameter_fingerprint(
            strategy,
            TREND_PULLBACK_V1_PARAMETER_TEMPLATE,
        )
        if strategy == "trend_pullback_v1"
        else None,
        "symbol": "btcusdt",
        "timeframe": "15m",
        "direction": "LONG",
        "entry_price": 100,
        "stop_loss": 95,
        "take_profit": 110,
        "market_regime": market_regime,
        "timestamp": (timestamp or datetime.now(UTC)).isoformat(),
    }


def test_strategy_portfolio_seeds_stage_11_defaults(client: TestClient) -> None:
    response = client.get("/strategies")

    assert response.status_code == 200
    strategies = {item["strategy"]: item for item in response.json()}
    assert set(strategies) == {
        "trend_pullback_v1",
        "volatility_breakout_v1",
        "slow_breakout_spot_v1",
        "range_mean_reversion_v1",
        "jam_reversal_v1",
        "jam_reversal_spot_v1",
    }
    assert strategies["volatility_breakout_v1"]["allowed_regimes"] == [
        "LOW_VOLATILITY",
        "BREAKOUT_EXPANSION",
    ]
    assert strategies["range_mean_reversion_v1"]["allowed_regimes"] == ["RANGING"]
    assert strategies["trend_pullback_v1"]["is_enabled"] is False
    assert strategies["trend_pullback_v1"]["lifecycle_status"] == "RETIRED"
    assert strategies["trend_pullback_v1"]["enable_eligible"] is False
    assert strategies["volatility_breakout_v1"]["is_enabled"] is False
    assert strategies["slow_breakout_spot_v1"]["allowed_regimes"] == ["TRENDING_UP"]
    assert strategies["slow_breakout_spot_v1"]["is_enabled"] is False
    assert strategies["range_mean_reversion_v1"]["is_enabled"] is False
    assert strategies["jam_reversal_v1"]["version"] == "1.14.0"
    assert strategies["jam_reversal_v1"]["is_enabled"] is False
    assert strategies["jam_reversal_spot_v1"]["version"] == "1.0.1"
    assert strategies["jam_reversal_spot_v1"]["is_enabled"] is False
    assert all(item["is_enabled"] is False for item in strategies.values())
    assert all(item["enable_eligible"] is False for item in strategies.values())


def test_retired_and_quarantined_strategies_cannot_be_enabled(
    client: TestClient,
) -> None:
    retired = client.patch(
        "/strategies/trend_pullback_v1",
        json={"is_enabled": True},
    )
    quarantined = client.patch(
        "/strategies/jam_reversal_v1",
        json={"is_enabled": True},
    )

    assert retired.status_code == 409
    assert "lifecycle is RETIRED" in retired.json()["detail"]
    assert quarantined.status_code == 409
    assert "lifecycle is QUARANTINED" in quarantined.json()["detail"]
    strategies = {item["strategy"]: item for item in client.get("/strategies").json()}
    assert strategies["trend_pullback_v1"]["is_enabled"] is False
    assert strategies["jam_reversal_v1"]["is_enabled"] is False


def test_disabled_strategy_is_risk_rejected_without_touching_others(
    client: TestClient,
) -> None:
    update = client.patch("/strategies/trend_pullback_v1", json={"is_enabled": False})
    webhook = client.post(
        "/webhooks/tradingview",
        json=webhook_payload(),
        headers=auth_headers(),
    )

    assert update.status_code == 200
    assert webhook.status_code == 202
    body = webhook.json()
    assert body["status"] == SignalStatus.RISK_REJECTED
    assert body["rejection_reason"].startswith(
        "Strategy trend_pullback_v1 lifecycle RETIRED blocks execution:"
    )

    strategies = {item["strategy"]: item for item in client.get("/strategies").json()}
    assert strategies["trend_pullback_v1"]["is_enabled"] is False
    assert strategies["volatility_breakout_v1"]["is_enabled"] is False

    with next(client.app.dependency_overrides[get_db]()) as session:
        assert session.execute(select(PaperTrade)).scalars().all() == []


def test_per_strategy_risk_override_changes_position_sizing(
    client: TestClient,
    active_trend_pipeline: None,
) -> None:
    post_accepted_backtest(client)
    update = client.patch(
        "/strategies/trend_pullback_v1",
        json={
            "is_enabled": True,
            "risk_per_trade": "0.001",
            "minimum_reward_risk": "1.0",
            "max_open_positions": 2,
        },
    )
    webhook = client.post(
        "/webhooks/tradingview",
        json=webhook_payload(),
        headers=auth_headers(),
    )

    assert update.status_code == 200
    assert webhook.status_code == 202
    body = webhook.json()
    decision = body["latest_risk_decision"]
    assert body["status"] == SignalStatus.PAPER_EXECUTED
    assert decision["approved"] is True
    assert Decimal(str(decision["risk_amount"])) == Decimal("1.00000000")
    assert Decimal(str(decision["position_size"])) == Decimal("0.200000000000")
    assert decision["rules_snapshot"]["effective_risk_per_trade"] == "0.001000"


def test_strategy_open_position_cap_blocks_portfolio_exposure(
    client: TestClient,
    active_trend_pipeline: None,
) -> None:
    update = client.patch(
        "/strategies/trend_pullback_v1",
        json={"is_enabled": True, "max_open_positions": 0},
    )
    webhook = client.post(
        "/webhooks/tradingview",
        json=webhook_payload(),
        headers=auth_headers(),
    )

    assert update.status_code == 200
    assert webhook.status_code == 202
    body = webhook.json()
    assert body["status"] == SignalStatus.RISK_REJECTED
    assert body["rejection_reason"] == "Strategy trend_pullback_v1 max open positions reached"


def test_strategy_comparison_reports_independent_metrics(client: TestClient) -> None:
    now = datetime(2026, 6, 6, 10, tzinfo=UTC)
    with next(client.app.dependency_overrides[get_db]()) as session:
        account = Account(
            name="paper-main",
            mode="paper",
            currency="USD",
            starting_equity=Decimal("1000"),
            current_equity=Decimal("1015"),
        )
        session.add(account)
        session.flush()
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
            strategy="range_mean_reversion_v1",
            market_regime=MarketRegime.RANGING,
            realized_pl=Decimal("8"),
        )
        session.commit()

    comparison = client.get("/strategies/comparison")

    assert comparison.status_code == 200
    strategies = {item["strategy"]: item for item in comparison.json()["strategies"]}
    trend = strategies["trend_pullback_v1"]
    range_strategy = strategies["range_mean_reversion_v1"]
    assert trend["closed_trades"] == 2
    assert Decimal(str(trend["total_net_pl"])) == Decimal("5.00000000")
    assert Decimal(str(trend["win_rate"])) == Decimal("0.5")
    assert range_strategy["closed_trades"] == 1
    assert Decimal(str(range_strategy["expectancy"])) == Decimal("8.00000000")


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

    session.add(
        PaperTrade(
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
    )
