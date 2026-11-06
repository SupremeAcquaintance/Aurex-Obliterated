from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from aurex.api.app import create_app
from aurex.api.dependencies import get_db
from aurex.backtest_engine.reference_replay import VOLATILITY_BREAKOUT_ENGINE_VERSION
from aurex.backtest_engine.schemas import OhlcvCandle
from aurex.db.base import Base


def volatility_client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    app = create_app()

    def override_get_db() -> Generator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def volatility_candles() -> list[OhlcvCandle]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    closes = [
        "100.0",
        "100.2",
        "100.4",
        "100.6",
        "101.0",
        "101.2",
        "101.4",
        "102.0",
        "102.5",
        "103.0",
        "103.5",
        "104.0",
        "104.1",
        "104.2",
        "104.3",
        "105.2",
        "107.4",
    ]
    candles: list[OhlcvCandle] = []
    for index, raw_close in enumerate(closes):
        close = Decimal(raw_close)
        candle = OhlcvCandle(
            timestamp=start + timedelta(minutes=15 * index),
            open=close - Decimal("0.2"),
            high=close + Decimal("0.2"),
            low=close - Decimal("0.4"),
            close=close,
            volume=Decimal("10"),
        )
        candles.append(candle)
    candles[11] = OhlcvCandle(
        timestamp=candles[11].timestamp,
        open=Decimal("103.8"),
        high=Decimal("104.2"),
        low=Decimal("90"),
        close=Decimal("104.0"),
        volume=Decimal("10"),
    )
    candles[15] = OhlcvCandle(
        timestamp=candles[15].timestamp,
        open=Decimal("104.5"),
        high=Decimal("105.4"),
        low=Decimal("104.4"),
        close=Decimal("105.2"),
        volume=Decimal("10"),
    )
    candles[16] = OhlcvCandle(
        timestamp=candles[16].timestamp,
        open=Decimal("105.3"),
        high=Decimal("110"),
        low=Decimal("105.1"),
        close=Decimal("107.4"),
        volume=Decimal("10"),
    )
    return candles


def candles_csv(candles: list[OhlcvCandle]) -> str:
    rows = ["timestamp,open,high,low,close,volume"]
    rows.extend(
        ",".join(
            [
                candle.timestamp.isoformat().replace("+00:00", "Z"),
                str(candle.open),
                str(candle.high),
                str(candle.low),
                str(candle.close),
                str(candle.volume),
            ]
        )
        for candle in candles
    )
    return "\n".join(rows)


def import_volatility_dataset(client: TestClient) -> str:
    response = client.post(
        "/backtests/ohlcv/import-csv",
        json={
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "source": "volatility-breakout-engine-fixture",
            "source_reference": "fixture://volatility-breakout/BTCUSDT/15m",
            "csv_timezone": "UTC",
            "continuity": "continuous_24_7",
            "csv_text": candles_csv(volatility_candles()),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def volatility_parameters(*, start: str = "2026-01-01T03:45:00Z") -> dict:
    return {
        "initial_capital": "1000",
        "backtest_start": start,
        "backtest_end": "2026-01-01T04:15:00Z",
        "higher_timeframe": "60",
        "htf_ema_fast": 1,
        "htf_ema_slow": 2,
        "breakout_lookback": 5,
        "compression_lookback": 10,
        "atr_length": 2,
        "atr_stop_multiplier": "1",
        "reward_risk": "1",
        "volume_length": 2,
        "volume_expansion": "1",
        "risk_per_trade_percent": "0.5",
        "max_position_value_percent": "95",
        "enable_long": True,
        "enable_short": True,
    }


def volatility_payload(dataset_id: str, *, start: str = "2026-01-01T03:45:00Z") -> dict:
    return {
        "dataset_id": dataset_id,
        "strategy": "volatility_breakout_v1",
        "strategy_version": "1.1.0",
        "parameters": volatility_parameters(start=start),
        "tick_size": "0.1",
        "point_value": "1",
        "minimum_contract": "0.001",
        "commission_percent": "0.05",
        "slippage_ticks": 2,
        "intrabar_policy": "stop_first",
    }


def test_volatility_breakout_reference_replay_is_deterministic_and_costed() -> None:
    with volatility_client() as client:
        dataset_id = import_volatility_dataset(client)
        payload = volatility_payload(dataset_id)

        first = client.post("/backtests/reference-replay/preflight", json=payload)
        second = client.post("/backtests/reference-replay/preflight", json=payload)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    body = first.json()
    assert body["status"] == "READY"
    assert body["engine_version"] == VOLATILITY_BREAKOUT_ENGINE_VERSION
    assert body["engine_evidence_hash"] == second.json()["engine_evidence_hash"]
    assert body["metrics"]["total_trades"] == 1
    assert body["trades"][0]["direction"] == "LONG"
    assert body["trades"][0]["exit_reason"] == "TAKE_PROFIT"
    assert Decimal(body["trades"][0]["fees"]) > 0
    assert Decimal(body["trades"][0]["slippage"]) > 0
    assert body["diagnostics"]["long_setups"] == 1
    assert body["comparison_only"] is True
    assert body["acceptance_eligible"] is False


def test_volatility_breakout_reference_replay_records_idempotently_and_audits() -> None:
    with volatility_client() as client:
        dataset_id = import_volatility_dataset(client)
        payload = volatility_payload(dataset_id)

        first = client.post("/backtests/reference-replay/runs", json=payload)
        second = client.post("/backtests/reference-replay/runs", json=payload)
        audit = client.get(
            f"/backtests/reference-replay/runs/{first.json()['id']}/audit"
        )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["reused_existing"] is False
    assert second.json()["reused_existing"] is True
    assert audit.status_code == 200
    assert audit.json()["status"] == "PASS"


def test_volatility_breakout_reference_replay_blocks_insufficient_warmup() -> None:
    with volatility_client() as client:
        dataset_id = import_volatility_dataset(client)
        response = client.post(
            "/backtests/reference-replay/preflight",
            json=volatility_payload(dataset_id, start="2026-01-01T01:00:00Z"),
        )

    assert response.status_code == 200
    assert response.json()["status"] == "BLOCKED"
    assert "insufficient_pre_window_indicator_warmup" in response.json()["reasons"]


def test_volatility_breakout_reference_replay_rejects_wrong_version() -> None:
    with volatility_client() as client:
        dataset_id = import_volatility_dataset(client)
        payload = volatility_payload(dataset_id)
        payload["strategy_version"] = "1.0.0"
        response = client.post("/backtests/reference-replay/preflight", json=payload)

    assert response.status_code == 400
    assert "requires version 1.1.0" in response.json()["detail"]
