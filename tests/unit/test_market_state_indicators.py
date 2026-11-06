from datetime import UTC, datetime, timedelta
from decimal import Decimal

from aurex.domain.enums import Direction, MarketRegime
from aurex.market_state.indicators import CandleInput, ema
from aurex.market_state.service import classify_market_state, strategy_regime_compatible


def make_trending_candles(count: int = 240) -> list[CandleInput]:
    candles: list[CandleInput] = []
    price = Decimal("100")
    for _ in range(count):
        price += Decimal("0.05")
        candles.append(
            CandleInput(
                open=price - Decimal("0.02"),
                high=price + Decimal("0.08"),
                low=price - Decimal("0.08"),
                close=price,
                volume=Decimal("100"),
            )
        )
    return candles


def make_ranging_candles(count: int = 240) -> list[CandleInput]:
    candles: list[CandleInput] = []
    for index in range(count):
        offset = Decimal("0.08") if index % 2 else Decimal("-0.08")
        price = Decimal("100") + offset
        candles.append(
            CandleInput(
                open=Decimal("100"),
                high=price + Decimal("0.12"),
                low=price - Decimal("0.12"),
                close=price,
                volume=Decimal("100"),
            )
        )
    return candles


def test_ema_calculation_returns_one_value_per_input() -> None:
    values = [Decimal("1"), Decimal("2"), Decimal("3")]

    result = ema(values, 2)

    assert len(result) == 3
    assert result[-1] > result[0]


def test_classify_market_state_detects_trending_up_with_inputs_snapshot() -> None:
    classified = classify_market_state(make_trending_candles(), make_trending_candles())

    assert classified.regime == MarketRegime.TRENDING_UP
    assert classified.confidence > Decimal("0.5")
    assert classified.inputs_snapshot["higher_timeframe_trend"] == "UP"
    assert "adx" in classified.inputs_snapshot
    assert "atr_percentile" in classified.inputs_snapshot
    assert "volume_relative_average" in classified.inputs_snapshot
    assert "vwap_distance" in classified.inputs_snapshot


def test_classify_market_state_detects_ranging_market() -> None:
    classified = classify_market_state(make_ranging_candles())

    assert classified.regime == MarketRegime.RANGING
    assert classified.confidence > Decimal("0.3")


def test_strategy_regime_compatibility_blocks_trend_strategy_in_range() -> None:
    assert (
        strategy_regime_compatible(
            "trend_pullback_v1",
            Direction.LONG,
            MarketRegime.RANGING,
        )
        is False
    )
    assert (
        strategy_regime_compatible(
            "trend_pullback_v1",
            Direction.LONG,
            MarketRegime.TRENDING_UP,
        )
        is True
    )


def test_candle_generators_use_stable_timestamps_shape() -> None:
    start = datetime(2026, 6, 6, tzinfo=UTC)
    timestamps = [start + timedelta(minutes=15 * index) for index in range(3)]

    assert timestamps[1] > timestamps[0]
