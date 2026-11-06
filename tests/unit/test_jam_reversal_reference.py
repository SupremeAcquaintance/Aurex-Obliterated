from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from aurex.backtest_engine.jam_reversal_reference import (
    JamOpenPosition,
    dmi_series,
    jam_quantity,
    parse_jam_reversal_spot_parameters,
    resolve_jam_bracket_exit,
)
from aurex.backtest_engine.schemas import OhlcvCandle
from aurex.backtest_engine.service import JAM_REVERSAL_SPOT_V1_PARAMETER_TEMPLATE
from aurex.domain.enums import Direction


def test_jam_spot_parser_enforces_long_only_frozen_boundary() -> None:
    parsed = parse_jam_reversal_spot_parameters(
        dict(JAM_REVERSAL_SPOT_V1_PARAMETER_TEMPLATE)
    )

    assert parsed["direction_mode"] == "Long only"
    assert parsed["enable_short"] is False
    assert parsed["allowed_timeframe_mode"] == "15m only"
    assert parsed["initial_capital"] == Decimal("100")

    invalid = dict(JAM_REVERSAL_SPOT_V1_PARAMETER_TEMPLATE)
    invalid["enable_short"] = True
    with pytest.raises(ValueError, match="frozen spot contract mismatch"):
        parse_jam_reversal_spot_parameters(invalid)


def test_jam_quantity_obeys_risk_notional_and_contract_step() -> None:
    parameters = parse_jam_reversal_spot_parameters(
        dict(JAM_REVERSAL_SPOT_V1_PARAMETER_TEMPLATE)
    )

    quantity = jam_quantity(
        equity=Decimal("100"),
        entry=Decimal("50000"),
        risk=Decimal("1000"),
        point_value=Decimal("1"),
        minimum_contract=Decimal("0.00001"),
        parameters=parameters,
    )

    assert quantity == Decimal("0.00050")
    assert quantity * Decimal("50000") <= Decimal("95")


def test_dmi_series_warms_up_and_identifies_upward_direction() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [
        OhlcvCandle(
            timestamp=start + timedelta(minutes=15 * index),
            open=Decimal(100 + index),
            high=Decimal(101 + index),
            low=Decimal(99 + index),
            close=Decimal("100.5") + index,
            volume=Decimal("10"),
        )
        for index in range(8)
    ]

    plus, minus, adx = dmi_series(candles, length=2, smoothing=2)

    assert plus[-1] is not None
    assert minus[-1] is not None
    assert adx[-1] is not None
    assert plus[-1] > minus[-1]
    assert adx[-1] > 0


def test_jam_bracket_uses_stop_first_when_target_and_stop_share_bar() -> None:
    position = JamOpenPosition(
        direction=Direction.LONG,
        entry_index=1,
        entry_at=datetime(2026, 1, 1, tzinfo=UTC),
        signal_price=Decimal("100"),
        entry_price=Decimal("100.02"),
        initial_stop_loss=Decimal("98"),
        stop_loss=Decimal("99"),
        take_profit=Decimal("103"),
        quantity=Decimal("0.1"),
        entry_fee=Decimal("0.01"),
        entry_slippage=Decimal("0.002"),
        initial_risk_per_unit=Decimal("2.02"),
        initial_risk=Decimal("0.202"),
        point_value=Decimal("1"),
        market_regime="BREAKOUT_EXPANSION",
        failure_level=Decimal("99.5"),
        best_price=Decimal("101"),
    )
    candle = OhlcvCandle(
        timestamp=datetime(2026, 1, 1, 0, 15, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("104"),
        low=Decimal("98"),
        close=Decimal("102"),
        volume=Decimal("10"),
    )

    fill = resolve_jam_bracket_exit(
        candle,
        position,
        tick_size=Decimal("0.01"),
        slippage_ticks=2,
    )

    assert fill is not None
    assert fill.reason == "STOP_AND_TARGET_AMBIGUOUS"
    assert fill.price == Decimal("98.98")
    assert fill.intrabar_ambiguous is True
