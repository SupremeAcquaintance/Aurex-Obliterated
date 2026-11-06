from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from aurex.api.app import create_app
from aurex.api.dependencies import get_db
from aurex.backtest_engine.jam_reversal_reference import (
    JAM_REVERSAL_SPOT_ENGINE_VERSION,
)
from aurex.backtest_engine.schemas import OhlcvCandle
from aurex.backtest_engine.service import JAM_REVERSAL_SPOT_V1_PARAMETER_TEMPLATE
from aurex.db.base import Base


def jam_client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )
    app = create_app()

    def override_get_db() -> Generator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def jam_candles() -> list[OhlcvCandle]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [
        OhlcvCandle(
            timestamp=start + timedelta(minutes=15 * index),
            open=Decimal("100"),
            high=Decimal("100.6"),
            low=Decimal("99.4"),
            close=Decimal("100"),
            volume=Decimal("10"),
        )
        for index in range(40)
    ]
    candles[30] = OhlcvCandle(
        timestamp=candles[30].timestamp,
        open=Decimal("101"),
        high=Decimal("101.2"),
        low=Decimal("99.8"),
        close=Decimal("100"),
        volume=Decimal("12"),
    )
    candles[31] = OhlcvCandle(
        timestamp=candles[31].timestamp,
        open=Decimal("99.8"),
        high=Decimal("101.6"),
        low=Decimal("99.5"),
        close=Decimal("101.5"),
        volume=Decimal("20"),
    )
    candles[32] = OhlcvCandle(
        timestamp=candles[32].timestamp,
        open=Decimal("101.4"),
        high=Decimal("102.2"),
        low=Decimal("101.3"),
        close=Decimal("102.1"),
        volume=Decimal("20"),
    )
    candles[33] = OhlcvCandle(
        timestamp=candles[33].timestamp,
        open=Decimal("102.1"),
        high=Decimal("106"),
        low=Decimal("101.9"),
        close=Decimal("105"),
        volume=Decimal("20"),
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


def import_jam_dataset(client: TestClient) -> str:
    response = client.post(
        "/backtests/ohlcv/import-csv",
        json={
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "source": "jam-reversal-spot-engine-fixture",
            "source_reference": "fixture://jam-reversal-spot/BTCUSDT/15m",
            "csv_timezone": "UTC",
            "continuity": "continuous_24_7",
            "csv_text": candles_csv(jam_candles()),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def jam_parameters() -> dict:
    parameters = dict(JAM_REVERSAL_SPOT_V1_PARAMETER_TEMPLATE)
    parameters.update(
        {
            "backtest_start": "2026-01-01T07:30:00Z",
            "backtest_end": "2026-01-01T09:00:00Z",
            "htf_ema_fast": 2,
            "htf_ema_slow": 3,
            "trend_ema": 5,
            "pullback_ema": 2,
            "use_higher_timeframe_bias": False,
            "context_mode": "None",
            "impulse_lookback": 2,
            "block_strong_counter_trend": False,
            "atr_length": 2,
            "adx_length": 2,
            "adx_smoothing": 2,
            "confirm_window_bars": 3,
            "confirm_atr_buffer": "0",
            "max_confirm_distance_atr": "3",
            "max_confirm_range_atr": "3",
            "min_confirm_close_position": "0.5",
            "reclaim_atr_buffer": "0",
            "min_seed_range_atr": "0",
            "min_jam_range_atr": "0",
            "max_jam_range_atr": "5",
            "use_volume_filter": False,
            "volume_length": 2,
            "use_timeframe_adaptive_confirmation": False,
            "stop_mode": "Pattern",
            "stop_atr_buffer": "0.1",
            "target_mode": "Fixed R",
            "reward_risk": "1",
            "use_cost_aware_filter": False,
            "use_breakeven_stop": False,
            "use_atr_trail": False,
            "use_midpoint_failure_exit": False,
            "use_pullback_failure_exit": False,
            "max_bars_in_trade": 10,
            "trade_cooldown_bars": 0,
        }
    )
    return parameters


def jam_payload(dataset_id: str) -> dict:
    return {
        "dataset_id": dataset_id,
        "strategy": "jam_reversal_spot_v1",
        "strategy_version": "1.0.1",
        "parameters": jam_parameters(),
        "tick_size": "0.01",
        "point_value": "1",
        "minimum_contract": "0.00001",
        "commission_percent": "0.10",
        "slippage_ticks": 2,
        "intrabar_policy": "stop_first",
    }


def test_jam_reversal_spot_replay_is_deterministic_long_only_and_costed() -> None:
    with jam_client() as client:
        dataset_id = import_jam_dataset(client)
        payload = jam_payload(dataset_id)

        first = client.post("/backtests/reference-replay/preflight", json=payload)
        second = client.post("/backtests/reference-replay/preflight", json=payload)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    body = first.json()
    assert body["status"] == "READY"
    assert body["engine_version"] == JAM_REVERSAL_SPOT_ENGINE_VERSION
    assert body["engine_evidence_hash"] == second.json()["engine_evidence_hash"]
    assert body["metrics"]["total_trades"] == 1
    assert body["trades"][0]["direction"] == "LONG"
    assert body["trades"][0]["exit_reason"] == "TAKE_PROFIT"
    assert Decimal(body["trades"][0]["fees"]) > 0
    assert Decimal(body["trades"][0]["slippage"]) > 0
    assert body["diagnostics"]["long_armed"] == 1
    assert body["diagnostics"]["long_confirmations"] == 1
    assert body["diagnostics"]["long_setups"] == 1
    assert body["comparison_only"] is True
    assert body["acceptance_eligible"] is False


def test_jam_reversal_spot_replay_records_idempotently_and_audits() -> None:
    with jam_client() as client:
        dataset_id = import_jam_dataset(client)
        payload = jam_payload(dataset_id)

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
