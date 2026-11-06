"""Exact replay arithmetic, including the 4,096-bar boundary and hour visibility."""

from decimal import ROUND_DOWN, Decimal, localcontext

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.reference_replay import (
    atr_series,
    ema_series,
    higher_timeframe_ema_series,
    rsi_series,
)
from aurex.signal_gateway.native_bars import (
    ClosedBar,
    NativeBarCursor,
    NativeBarError,
    NativeIndicatorParameters,
    content_hash,
    prepare_native_closed_bar,
)
from aurex.signal_gateway.native_continuation import (
    NativeIndicatorState,
    advance_indicators,
    continuation_frame,
    initialize_continuation,
)
from tests.unit.test_native_closed_bars import NOW, SMALL, STEP, bars


def varied_bars(count, phase=0, pattern="mixed"):
    result = []
    for index, bar in enumerate(bars(count, end=NOW + phase * STEP)):
        offset = {
            "flat": 0,
            "rising": index,
            "falling": -index,
            "mixed": (index * 97 % 211) - 100,
        }[pattern]
        close = Decimal("1000") + Decimal(offset) / 100
        result.append(
            ClosedBar.model_validate(
                {
                    **bar,
                    "open": close,
                    "high": close + 1,
                    "low": close - 1,
                    "close": close,
                }
            )
        )
    return result


@pytest.mark.parametrize("phase", range(4))
@pytest.mark.parametrize("pattern", ["flat", "rising", "falling", "mixed"])
@pytest.mark.parametrize(
    "parameters",
    [
        SMALL,
        NativeIndicatorParameters(),
        NativeIndicatorParameters(**dict.fromkeys(NativeIndicatorParameters.model_fields, 1)),
        NativeIndicatorParameters(**dict.fromkeys(NativeIndicatorParameters.model_fields, 500)),
    ],
)
def test_exact_replay_parity_across_boundary_and_serialization(phase, pattern, parameters):
    history = varied_bars(4132, phase, pattern)
    closes = [bar.close for bar in history]
    expected = {
        name: ema_series(closes, getattr(parameters, name))
        for name in ("ema_fast", "ema_slow", "ema_trend")
    }
    expected["rsi"] = rsi_series(closes, parameters.rsi_length)
    expected["atr"] = atr_series(history, parameters.atr_length)
    higher = higher_timeframe_ema_series(
        history,
        base_seconds=900,
        higher_seconds=3600,
        fast_length=parameters.higher_ema_fast,
        slow_length=parameters.higher_ema_slow,
    )
    expected["higher_ema_fast"] = [item[0] for item in higher]
    expected["higher_ema_slow"] = [item[1] for item in higher]
    state = initialize_continuation(history[:4096], parameters)
    assert state.indicators() == {key: values[4095] for key, values in expected.items()}
    for index, bar in enumerate(history[4096:], start=4096):
        state = NativeIndicatorState.model_validate_json(state.model_dump_json())
        state = advance_indicators(state, bar)
        assert state.indicators() == {key: values[index] for key, values in expected.items()}


def test_versioned_cursor_uses_explicit_hash_chain_and_preserves_first_open():
    history = varied_bars(4097)
    seed = history[:4096]
    previous = prepare_native_closed_bar(
        seed,
        now=seed[-1].timestamp + STEP,
        feed_id="fixture",
        parameters=SMALL,
    ).checkpoint
    frame, state = continuation_frame(initialize_continuation(seed, SMALL), previous, history[-1])
    assert frame.checkpoint.schema_version == "native_closed_bar_continuation_v1"
    assert frame.checkpoint.bar_count == state.bar_count == 4097
    assert frame.checkpoint.first_open == previous.first_open
    assert frame.checkpoint.history_sha256 == content_hash(
        {
            "schema": "native_bar_chain_v1",
            "previous_schema": previous.schema_version,
            "previous_hash": previous.history_sha256,
            "bar": history[-1].model_dump(mode="json"),
        }
    )
    assert not frame.execution_authority and not frame.source_origin_verified
    with pytest.raises(ValidationError, match="legacy_cursor_window_exhausted"):
        NativeBarCursor.model_validate(
            {**frame.checkpoint.model_dump(), "schema_version": previous.schema_version}
        )
    with pytest.raises(ValidationError, match="before_window_boundary"):
        NativeBarCursor.model_validate(
            {**previous.model_dump(), "schema_version": frame.checkpoint.schema_version}
        )
    with pytest.raises(NativeBarError, match="incremental_state"):
        prepare_native_closed_bar(
            seed, now=NOW, feed_id="fixture", parameters=SMALL, previous=frame.checkpoint
        )


@pytest.mark.parametrize("change", ["precision", "rounding", "exponent", "traps"])
def test_changed_decimal_arithmetic_fails_closed(change):
    history = varied_bars(20)
    state = initialize_continuation(history[:-1], SMALL)
    with localcontext() as context:
        if change == "precision":
            context.prec = 40
        elif change == "rounding":
            context.rounding = ROUND_DOWN
        elif change == "exponent":
            context.Emin = -10
        else:
            context.clear_traps()
        with pytest.raises(NativeBarError, match="decimal28"):
            initialize_continuation(history, SMALL)
        with pytest.raises(NativeBarError, match="decimal28"):
            advance_indicators(state, history[-1])


@pytest.mark.parametrize("size", [0, 4097])
def test_continuation_seed_size_is_bounded_before_copying(size):
    class NotACandle:
        def model_dump(self):
            pytest.fail("oversized seed was copied before its bound was checked")

    with pytest.raises(NativeBarError, match="seed_empty|window_size"):
        initialize_continuation([NotACandle()] * size, SMALL)


def test_gaps_revisions_and_state_cursor_mismatch_reject():
    history = varied_bars(4097)
    state = initialize_continuation(history[:4096], SMALL)
    for bar in (history[-2], history[-1].model_copy(update={"timestamp": NOW + STEP})):
        with pytest.raises(NativeBarError, match="one_next_bar"):
            advance_indicators(state, bar)
    cursor = prepare_native_closed_bar(
        history[:4096],
        now=history[4095].timestamp + STEP,
        feed_id="fixture",
        parameters=SMALL,
    ).checkpoint
    with pytest.raises(NativeBarError, match="state_cursor_mismatch"):
        continuation_frame(
            state, cursor.model_copy(update={"parameters_sha256": "0" * 64}), history[-1]
        )
