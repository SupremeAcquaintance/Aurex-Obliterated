"""Synthetic arithmetic parity, never strategy qualification or forward evidence."""

from datetime import UTC, datetime, timedelta
from decimal import ROUND_DOWN, Decimal, localcontext

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.jam_reversal_reference import dmi_series, jam_indicators_ready
from aurex.backtest_engine.reference_replay import (
    atr_series,
    complete_higher_timeframe_count,
    ema_series,
    higher_timeframe_ema_series,
    simple_moving_average_series,
)
from aurex.signal_gateway.native_bars import ClosedBar, NativeBarError
from aurex.signal_gateway.native_jam_features import (
    JamFeatureParameters,
    JamFeatureState,
    advance_jam_features,
    initialize_jam_features,
    jam_feature_frame,
)

STEP = timedelta(minutes=15)
LENGTHS = (
    "trend_ema",
    "pullback_ema",
    "atr_length",
    "volume_length",
    "adx_length",
    "adx_smoothing",
    "impulse_lookback",
    "htf_ema_fast",
    "htf_ema_slow",
)
SMALL = JamFeatureParameters(**dict(zip(LENGTHS, (7, 3, 4, 5, 3, 2, 6, 2, 4), strict=True)))
ONES = JamFeatureParameters(**dict.fromkeys(LENGTHS, 1))


def candles(count, phase=0, pattern="mixed"):
    result = []
    for index in range(count):
        offset = {
            "mixed": (index * 97 % 211) - 100,
            "rising": index,
            "falling": -index,
            "flat": 0,
            "zero": 0,
            "intermittent": (index // 4) % 2,
        }[pattern]
        close = Decimal("1000") + Decimal(offset) / 100
        spread = Decimal(0 if pattern in {"zero", "intermittent"} else 1)
        result.append(
            ClosedBar(
                timestamp=datetime(2026, 1, 1, tzinfo=UTC) + (index + phase) * STEP,
                open=close,
                high=close + spread,
                low=close - spread,
                close=close,
                volume=Decimal(index * 313 % 173) / Decimal("100000000"),
            )
        )
    return result


def reference(history, p):
    plus, minus, adx = dmi_series(history, p.adx_length, p.adx_smoothing)
    higher = higher_timeframe_ema_series(
        history,
        base_seconds=900,
        higher_seconds=3600,
        fast_length=p.htf_ema_fast,
        slow_length=p.htf_ema_slow,
    )
    return {
        "trend_ema": ema_series([bar.close for bar in history], p.trend_ema),
        "pullback_ema": ema_series([bar.close for bar in history], p.pullback_ema),
        "atr": atr_series(history, p.atr_length),
        "volume_average": simple_moving_average_series(
            [bar.volume for bar in history], p.volume_length
        ),
        "dmi_plus": plus,
        "dmi_minus": minus,
        "adx": adx,
        "higher_fast": [pair[0] for pair in higher],
        "higher_slow": [pair[1] for pair in higher],
    }


def assert_parity(state, history, expected, index):
    frame = jam_feature_frame(state)
    p = state.parameters
    for name, values in expected.items():
        assert getattr(frame, name) == values[index], (index, name)
    assert frame.bar == history[index]
    assert frame.previous_bar == (history[index - 1] if index else None)
    assert frame.previous_atr == (expected["atr"][index - 1] if index else None)
    assert frame.previous_pullback_ema == (expected["pullback_ema"][index - 1] if index else None)
    previous = history[max(0, index - p.impulse_lookback) : index]
    assert frame.local_reversal == (
        bool(previous)
        and (
            history[index - 1].close <= min(bar.close for bar in previous)
            or history[index - 1].low <= min(bar.low for bar in previous)
        )
    )
    complete = complete_higher_timeframe_count(
        history, base_seconds=900, higher_seconds=3600, through=history[index].timestamp
    )
    assert state.complete_hours == complete
    ready = jam_indicators_ready(
        index,
        atr=expected["atr"],
        volume_average=expected["volume_average"],
        dmi_plus=expected["dmi_plus"],
        dmi_minus=expected["dmi_minus"],
        adx=expected["adx"],
        htf=list(zip(expected["higher_fast"], expected["higher_slow"], strict=True)),
    )
    assert frame.warmup_ready == (
        index + 1 >= p.required_base_history
        and complete >= max(p.htf_ema_fast, p.htf_ema_slow)
        and ready
    )
    assert not frame.execution_authority and not frame.source_origin_verified
    assert len(state.recent) == min(index + 1, p.buffer_size)
    assert all(
        len(getattr(state, name).seed) < getattr(state, name).length
        for name in ("atr", "true_range", "plus_dm", "minus_dm", "adx")
    )


@pytest.mark.parametrize("phase", range(4))
@pytest.mark.parametrize("pattern", ["mixed", "rising", "falling", "flat", "zero", "intermittent"])
@pytest.mark.parametrize("parameters", [SMALL, ONES])
def test_every_bar_matches_replay_including_warmup_and_json_restart(phase, pattern, parameters):
    history = candles(96, phase, pattern)
    expected = reference(history, parameters)
    state = initialize_jam_features(history[:1], parameters)
    for index, bar in enumerate(history):
        if index:
            state = advance_jam_features(state, bar)
        state = JamFeatureState.model_validate_json(state.model_dump_json())
        assert_parity(state, history, expected, index)
    assert state == initialize_jam_features(history, parameters)


@pytest.mark.parametrize("parameters", [SMALL, JamFeatureParameters(**dict.fromkeys(LENGTHS, 500))])
def test_continuation_crosses_4096_without_sliding_or_reseeding(parameters):
    history = candles(4132, phase=1)
    expected = reference(history, parameters)
    state = initialize_jam_features(history[:4096], parameters)
    assert_parity(state, history, expected, 4095)
    old_size = len(state.model_dump_json())
    for index, bar in enumerate(history[4096:], start=4096):
        state = advance_jam_features(
            JamFeatureState.model_validate_json(state.model_dump_json()), bar
        )
        assert_parity(state, history, expected, index)
    assert state.first_open == history[0].timestamp
    assert len(state.model_dump_json()) < old_size + 1024


def test_arbitrary_restart_chunking_and_future_prefix_causality():
    history = candles(200, phase=2)
    state = initialize_jam_features(history[:1], SMALL)
    for index, bar in enumerate(history[1:], start=1):
        state = advance_jam_features(state, bar)
        if index in (1, 6, 17, 43, 128, 199):
            assert state == initialize_jam_features(history[: index + 1], SMALL)
            state = JamFeatureState.model_validate_json(state.model_dump_json())
            expected = reference(history[: index + 1], SMALL)
            assert_parity(state, history[: index + 1], expected, index)


def test_confirmed_hour_visibility_never_uses_current_hour_close():
    history = candles(9)
    at_45 = initialize_jam_features(history[:4], ONES)
    assert at_45.complete_hours == 1
    assert jam_feature_frame(at_45).higher_fast is None
    at_00 = advance_jam_features(at_45, history[4])
    assert jam_feature_frame(at_00).higher_fast == history[3].close
    next_45 = initialize_jam_features(history[:8], ONES)
    assert next_45.complete_hours == 2
    assert jam_feature_frame(next_45).higher_fast == history[3].close
    assert (
        jam_feature_frame(advance_jam_features(next_45, history[8])).higher_fast == history[7].close
    )


def test_missing_dx_does_not_clear_adx_seed_or_average():
    history = candles(20, pattern="intermittent")
    parameters = ONES.model_copy(update={"adx_smoothing": 2})
    state = initialize_jam_features(history[:9], parameters)
    assert state.adx.sample_count == 2 and state.adx.average == 100
    state = advance_jam_features(state, history[9])
    assert state.adx.sample_count == 2 and state.adx.average == 100
    assert jam_feature_frame(state).adx is None
    assert not jam_feature_frame(state).warmup_ready


@pytest.mark.parametrize("change", ["precision", "rounding", "exponent", "traps"])
def test_arithmetic_contract_is_enforced_at_all_entry_points(change):
    history = candles(20)
    state = initialize_jam_features(history[:-1], SMALL)
    with localcontext() as context:
        if change == "precision":
            context.prec = 40
        elif change == "rounding":
            context.rounding = ROUND_DOWN
        elif change == "exponent":
            context.Emin = -10
        else:
            context.clear_traps()
        for operation in (
            lambda: initialize_jam_features(history, SMALL),
            lambda: advance_jam_features(state, history[-1]),
            lambda: jam_feature_frame(state),
        ):
            with pytest.raises(NativeBarError, match="decimal28"):
                operation()


@pytest.mark.parametrize("size", [0, 4097])
def test_seed_bounds_checked_before_copying(size):
    with pytest.raises(NativeBarError, match="seed_size"):
        initialize_jam_features([object()] * size, SMALL)


def test_repeated_revised_skipped_and_reordered_bars_reject():
    history = candles(20)
    state = initialize_jam_features(history[:18], SMALL)
    for bar in (
        history[17],
        history[16],
        history[19],
        history[17].model_copy(update={"volume": Decimal(2)}),
    ):
        with pytest.raises(NativeBarError, match="one_next_bar"):
            advance_jam_features(state, bar)
    with pytest.raises(NativeBarError, match="one_next_bar"):
        initialize_jam_features([history[0], history[2]], SMALL)


@pytest.mark.parametrize(
    "field,value",
    [
        ("bar_count", 19),
        ("bar_count", True),
        ("trend_ema", Decimal("NaN")),
        ("previous_atr", None),
        ("visible_higher_fast", None),
        ("schema_version", "unknown"),
    ],
)
def test_invalid_copied_states_are_revalidated(field, value):
    history = candles(21)
    state = initialize_jam_features(history[:20], SMALL).model_copy(update={field: value})
    for operation in (
        lambda: jam_feature_frame(state),
        lambda: advance_jam_features(state, history[-1]),
    ):
        with pytest.raises(ValidationError):
            operation()


def test_nested_copies_cannot_bypass_state_validation():
    history = candles(20)
    state = initialize_jam_features(history, SMALL)
    for invalid in (
        state.model_copy(update={"parameters": SMALL.model_copy(update={"adx_length": 0})}),
        state.model_copy(update={"atr": state.atr.model_copy(update={"seed": (Decimal(2),)})}),
        state.model_copy(
            update={
                "recent": (
                    *state.recent[:-1],
                    state.recent[-1].model_copy(update={"low": Decimal(0)}),
                )
            }
        ),
    ):
        with pytest.raises(ValidationError):
            jam_feature_frame(invalid)


@pytest.mark.parametrize(
    "field,value",
    [
        ("trend_ema", 0),
        ("atr_length", 501),
        ("adx_length", True),
        ("volume_length", "3"),
        ("higher_timeframe", "240"),
        ("symbol", "ETHUSDT"),
        ("timeframe", "1m"),
    ],
)
def test_unsupported_parameters_reject(field, value):
    with pytest.raises(ValidationError):
        JamFeatureParameters.model_validate({**SMALL.model_dump(), field: value})


def test_high_precision_prices_and_volume_match_replay_without_float_rounding():
    history = [
        ClosedBar.model_validate(
            {
                **bar.model_dump(),
                "open": bar.open + Decimal("99999999000.12345678"),
                "high": bar.high + Decimal("99999999000.12345678"),
                "low": bar.low + Decimal("99999999000.12345678"),
                "close": bar.close + Decimal("99999999000.12345678"),
                "volume": Decimal("999999999999.99999999") - bar.volume,
            }
        )
        for bar in candles(80)
    ]
    expected = reference(history, SMALL)
    state = initialize_jam_features(history[:1], SMALL)
    for index, bar in enumerate(history):
        if index:
            state = advance_jam_features(state, bar)
        assert_parity(state, history, expected, index)
