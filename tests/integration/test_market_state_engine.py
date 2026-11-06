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
from aurex.config.settings import get_settings
from aurex.db.base import Base
from aurex.db.models import MarketCandle, MarketState, PaperTrade, Signal
from aurex.domain.enums import MarketRegime, SignalStatus

pytestmark = pytest.mark.usefixtures("active_trend_pipeline")


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


def candle_payload(symbol: str, timeframe: str, regime_shape: str = "trend") -> dict:
    start = datetime.now(UTC) - timedelta(days=3)
    candles = []
    price = Decimal("100")
    for index in range(240):
        timestamp = start + timedelta(minutes=15 * index)
        if regime_shape == "range":
            offset = Decimal("0.08") if index % 2 else Decimal("-0.08")
            price_value = Decimal("100") + offset
        else:
            price += Decimal("0.05")
            price_value = price
        candles.append(
            {
                "timestamp": timestamp.isoformat(),
                "open": str(price_value - Decimal("0.02")),
                "high": str(price_value + Decimal("0.08")),
                "low": str(price_value - Decimal("0.08")),
                "close": str(price_value),
                "volume": "100",
            }
        )
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "source": "fixture",
        "candles": candles,
    }


def test_market_candle_import_and_compute_state(client: TestClient) -> None:
    payload = candle_payload("btcusdt", "15m", "trend")
    import_response = client.post(
        "/market/candles/import",
        json=payload,
    )
    update_response = client.post(
        "/market/candles/import",
        json=payload,
    )
    compute_response = client.post(
        "/market/state/compute",
        json={"symbol": "btcusdt", "timeframe": "15m", "limit": 240},
    )

    assert import_response.status_code == 200
    assert import_response.json()["imported"] == 240
    assert update_response.status_code == 200
    assert update_response.json()["updated"] == 240
    assert compute_response.status_code == 200
    assert compute_response.json()["regime"] == MarketRegime.TRENDING_UP
    assert Decimal(compute_response.json()["confidence"]) > Decimal("0.5")

    with next(client.app.dependency_overrides[get_db]()) as session:
        assert session.execute(select(MarketCandle)).scalars().all()
        assert session.execute(select(MarketState)).scalar_one().regime == MarketRegime.TRENDING_UP


def test_signal_is_enriched_with_computed_ranging_state_and_rejected(
    client: TestClient,
) -> None:
    import_response = client.post(
        "/market/candles/import",
        json=candle_payload("btcusdt", "15m", "range"),
    )
    assert import_response.status_code == 200
    enabled = client.patch(
        "/strategies/trend_pullback_v1",
        json={"is_enabled": True},
    )
    assert enabled.status_code == 200

    webhook_payload = {
        "source": "tradingview",
        "strategy": "trend_pullback_v1",
        "symbol": "btcusdt",
        "timeframe": "15m",
        "direction": "LONG",
        "entry_price": 100,
        "stop_loss": 95,
        "take_profit": 110,
        "market_regime": "TRENDING_UP",
        "timestamp": datetime.now(UTC).isoformat(),
    }
    webhook_response = client.post(
        "/webhooks/tradingview",
        json=webhook_payload,
        headers=auth_headers(),
    )

    assert webhook_response.status_code == 202
    body = webhook_response.json()
    assert body["status"] == SignalStatus.RISK_REJECTED
    assert body["market_regime"] == MarketRegime.RANGING
    assert body["rejection_reason"] == (
        "Market regime RANGING is incompatible with trend_pullback_v1"
    )

    with next(client.app.dependency_overrides[get_db]()) as session:
        signal = session.execute(select(Signal)).scalar_one()
        state = session.execute(
            select(MarketState).where(MarketState.signal_id == signal.id)
        ).scalar_one()
        trades = session.execute(select(PaperTrade)).scalars().all()

    assert state.regime == MarketRegime.RANGING
    assert trades == []
