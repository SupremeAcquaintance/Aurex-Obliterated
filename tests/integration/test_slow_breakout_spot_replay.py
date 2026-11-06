from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from aurex.api.app import create_app
from aurex.api.dependencies import get_db
from aurex.backtest_engine.reference_replay import SLOW_BREAKOUT_SPOT_ENGINE_VERSION
from aurex.backtest_engine.schemas import OhlcvCandle
from aurex.db.base import Base


def slow_breakout_client() -> TestClient:
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


def slow_breakout_candles(*, stop_reversal: bool = False) -> list[OhlcvCandle]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    closes = [
        Decimal("100") + Decimal("0.2") * index
        for index in range(10)
    ] + [
        Decimal("103"),
        Decimal("103.2"),
        Decimal("101"),
        Decimal("101.2"),
    ]
    candles = [
        OhlcvCandle(
            timestamp=start + timedelta(hours=4 * index),
            open=close - Decimal("0.1"),
            high=close + Decimal("0.3"),
            low=close - Decimal("0.3"),
            close=close,
            volume=Decimal("10"),
        )
        for index, close in enumerate(closes)
    ]
    if stop_reversal:
        candles[11] = OhlcvCandle(
            timestamp=candles[11].timestamp,
            open=Decimal("99"),
            high=Decimal("106"),
            low=Decimal("98.5"),
            close=Decimal("105"),
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


def import_slow_breakout_dataset(
    client: TestClient,
    *,
    stop_reversal: bool = False,
) -> str:
    response = client.post(
        "/backtests/ohlcv/import-csv",
        json={
            "symbol": "ETHUSDT",
            "timeframe": "4h",
            "source": "slow-breakout-engine-fixture",
            "source_reference": "fixture://slow-breakout/ETHUSDT/4h",
            "csv_timezone": "UTC",
            "continuity": "continuous_24_7",
            "csv_text": candles_csv(
                slow_breakout_candles(stop_reversal=stop_reversal)
            ),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def slow_breakout_parameters() -> dict:
    return {
        "initial_capital": "1000",
        "backtest_start": "2026-01-02T16:00:00Z",
        "backtest_end": "2026-01-03T04:00:00Z",
        "entry_channel_length": 5,
        "exit_channel_length": 3,
        "atr_length": 2,
        "atr_stop_multiplier": "3",
        "risk_per_trade_percent": "0.25",
        "max_position_value_percent": "50",
        "enable_long": True,
    }


def slow_breakout_payload(dataset_id: str) -> dict:
    return {
        "dataset_id": dataset_id,
        "strategy": "slow_breakout_spot_v1",
        "strategy_version": "1.0.0",
        "parameters": slow_breakout_parameters(),
        "tick_size": "0.1",
        "point_value": "1",
        "minimum_contract": "0.001",
        "commission_percent": "0.05",
        "slippage_ticks": 2,
        "intrabar_policy": "stop_first",
    }


def test_slow_breakout_spot_reference_replay_is_deterministic_and_targetless() -> None:
    with slow_breakout_client() as client:
        dataset_id = import_slow_breakout_dataset(client)
        payload = slow_breakout_payload(dataset_id)
        first = client.post("/backtests/reference-replay/preflight", json=payload)
        second = client.post("/backtests/reference-replay/preflight", json=payload)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    body = first.json()
    assert body["status"] == "READY"
    assert body["engine_version"] == SLOW_BREAKOUT_SPOT_ENGINE_VERSION
    assert body["engine_evidence_hash"] == second.json()["engine_evidence_hash"]
    assert body["metrics"]["total_trades"] == 1
    assert body["trades"][0]["direction"] == "LONG"
    assert body["trades"][0]["take_profit"] is None
    assert body["trades"][0]["exit_reason"] == "CHANNEL_EXIT"
    assert Decimal(body["trades"][0]["fees"]) > 0
    assert Decimal(body["trades"][0]["slippage"]) > 0
    assert body["diagnostics"]["long_setups"] == 1
    assert body["diagnostics"]["channel_exit_signals"] == 1
    assert body["assumptions"]["market"] == "spot"
    assert body["assumptions"]["take_profit"] is None


def test_slow_breakout_spot_stop_first_prevents_same_bar_reentry() -> None:
    with slow_breakout_client() as client:
        dataset_id = import_slow_breakout_dataset(client, stop_reversal=True)
        response = client.post(
            "/backtests/reference-replay/preflight",
            json=slow_breakout_payload(dataset_id),
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "READY"
    assert body["metrics"]["total_trades"] == 1
    assert body["trades"][0]["exit_reason"] == "STOP_GAP"
    assert body["diagnostics"]["long_setups"] == 1


def test_slow_breakout_spot_reference_replay_records_and_audits() -> None:
    with slow_breakout_client() as client:
        dataset_id = import_slow_breakout_dataset(client)
        payload = slow_breakout_payload(dataset_id)
        recorded = client.post("/backtests/reference-replay/runs", json=payload)
        audit = client.get(
            f"/backtests/reference-replay/runs/{recorded.json()['id']}/audit"
        )

    assert recorded.status_code == 201, recorded.text
    assert audit.status_code == 200, audit.text
    assert audit.json()["status"] == "PASS"


def test_slow_breakout_spot_reference_replay_rejects_wrong_version() -> None:
    with slow_breakout_client() as client:
        dataset_id = import_slow_breakout_dataset(client)
        payload = slow_breakout_payload(dataset_id)
        payload["strategy_version"] = "0.9.0"
        response = client.post("/backtests/reference-replay/preflight", json=payload)

    assert response.status_code == 400
    assert "requires version 1.0.0" in response.json()["detail"]
