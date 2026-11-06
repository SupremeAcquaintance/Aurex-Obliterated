from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.reference_replay import atr_series, ema_series, rsi_series
from aurex.signal_gateway.native_bars import (
    ClosedBar,
    NativeBarCursor,
    NativeBarError,
    NativeIndicatorParameters,
    bind_native_signal_to_bar,
    prepare_native_closed_bar,
)
from aurex.signal_gateway.schemas import NativeSignalPayload

NOW = datetime(2026, 9, 27, 12, tzinfo=UTC)
STEP = timedelta(minutes=15)
SMALL = NativeIndicatorParameters(
    ema_fast=2,
    ema_slow=3,
    ema_trend=4,
    rsi_length=2,
    atr_length=2,
    higher_ema_fast=2,
    higher_ema_slow=3,
)


def bars(count=17, end=NOW):
    return [
        {
            "timestamp": end - STEP * (count - index),
            "open": "100",
            "high": "101",
            "low": "99",
            "close": "100",
            "volume": "1",
        }
        for index in range(count)
    ]


def prepare(candles=None, **kwargs):
    options = {"now": NOW, "feed_id": "fixture", "parameters": SMALL}
    options.update(kwargs)
    return prepare_native_closed_bar(bars() if candles is None else candles, **options)


def signal(**changes):
    payload = dict(
        source="aurex_native",
        strategy="fixture",
        strategy_version="1.0.0",
        settings_fingerprint="fixture-only",
        symbol="BTCUSDT",
        timeframe="15m",
        direction="LONG",
        entry_price="100",
        stop_loss="95",
        take_profit="112",
        timestamp=NOW,
    )
    payload.update(changes)
    return NativeSignalPayload.model_validate(payload)


def test_ready_frame_reuses_replay_indicators_and_grants_no_execution_authority():
    candles = [ClosedBar.model_validate(bar) for bar in bars()]
    frame = prepare(candles)
    closes = [bar.close for bar in candles]
    assert frame.status == "READY"
    assert frame.closed_at == NOW
    assert frame.indicators["ema_fast"] == ema_series(closes, 2)[-1]
    assert frame.indicators["rsi"] == rsi_series(closes, 2)[-1]
    assert frame.indicators["atr"] == atr_series(candles, 2)[-1]
    assert frame.indicators["higher_ema_slow"] == Decimal("100")
    assert frame.execution_authority is False
    assert frame.source_origin_verified is False
    assert bind_native_signal_to_bar(signal(), frame).timestamp == NOW


def test_realistic_default_warmup_window():
    frame = prepare(bars(900), parameters=NativeIndicatorParameters())
    assert frame.status == "READY"
    assert frame.checkpoint.bar_count == 900


@pytest.mark.parametrize(
    "change",
    [
        {"timestamp": NOW.replace(tzinfo=None)},
        {"timestamp": NOW + timedelta(seconds=1)},
        {"timestamp": NOW + timedelta(microseconds=1)},
        {"open": "0"},
        {"high": "99"},
        {"low": "101"},
        {"volume": "-1"},
        {"close": "NaN"},
        {"volume": "Infinity"},
        {"close": "100.000000001"},
        {"volume": "1000000000000"},
        {"lookahead": True},
    ],
)
def test_invalid_candle_fields_are_rejected(change):
    with pytest.raises(ValidationError):
        ClosedBar.model_validate({**bars()[0], **change})


def test_naive_observation_time_is_rejected():
    with pytest.raises(NativeBarError, match="timezone"):
        prepare(now=NOW.replace(tzinfo=None))


@pytest.mark.parametrize("age", [-1, 181, True])
def test_freshness_deadline_cannot_be_relaxed(age):
    with pytest.raises(NativeBarError, match="freshness_limit"):
        prepare(max_age_seconds=age)


def test_unfinished_or_stale_bar_cannot_advance():
    with pytest.raises(NativeBarError, match="not_closed"):
        prepare(now=NOW - timedelta(microseconds=1))
    assert prepare(now=NOW + timedelta(seconds=180)).status == "READY"
    with pytest.raises(NativeBarError, match="stale"):
        prepare(now=NOW + timedelta(seconds=181))


@pytest.mark.parametrize("change", ["gap", "duplicate", "reverse"])
def test_noncontiguous_input_is_not_silently_sorted_or_filled(change):
    history = bars()
    if change == "gap":
        del history[5]
    elif change == "duplicate":
        history[5] = history[4]
    else:
        history.reverse()
    with pytest.raises(NativeBarError, match="duplicate_unsorted_or_gapped"):
        prepare(history)


def test_size_and_base_warmup_limits():
    for history in ([], bars(4097)):
        with pytest.raises(NativeBarError, match="window_size"):
            prepare(history)
    with pytest.raises(NativeBarError, match="base_warmup"):
        prepare(bars(3))


def test_current_higher_bar_cannot_count_as_previous_confirmed_warmup():
    # 09:00 through 11:45 contains three complete hours at 12:00, but the
    # last base bar only sees two previously confirmed hours under replay semantics.
    with pytest.raises(NativeBarError, match="higher_warmup"):
        prepare(bars(12))


def test_cursor_roundtrip_detects_old_retry_without_emitting_another_signal():
    first = prepare()
    cursor = NativeBarCursor.model_validate_json(first.checkpoint.model_dump_json())
    retry = prepare(previous=cursor, now=NOW + timedelta(days=1))
    assert retry.status == "DUPLICATE"
    assert retry.checkpoint == first.checkpoint
    assert retry.indicators == {}
    with pytest.raises(NativeBarError, match="duplicate_bar"):
        bind_native_signal_to_bar(signal(), retry)


def test_append_one_bar_is_causal_and_preserves_seed():
    history = bars()
    first = prepare(history)
    next_bar = {**history[-1], "timestamp": NOW, "high": "121", "close": "120"}
    second = prepare(history + [next_bar], previous=first.checkpoint, now=NOW + STEP)
    assert second.status == "READY"
    assert second.checkpoint.first_open == first.checkpoint.first_open
    assert second.checkpoint.history_sha256 != first.checkpoint.history_sha256
    assert second.candle_id != first.candle_id
    assert first.indicators["ema_fast"] == Decimal("100")
    assert second.indicators["ema_fast"] > first.indicators["ema_fast"]
    assert second.indicators["higher_ema_fast"] == Decimal("100")


def test_higher_close_is_visible_only_in_the_next_hour():
    history = bars()
    history[-1] = {**history[-1], "close": "140", "high": "141"}
    first = prepare(history)
    assert first.indicators["ema_fast"] > Decimal("100")
    assert first.indicators["higher_ema_fast"] == Decimal("100")
    second = prepare(
        history + [{**bars()[-1], "timestamp": NOW}],
        previous=first.checkpoint,
        now=NOW + STEP,
    )
    assert (
        second.indicators["higher_ema_fast"]
        == ema_series([Decimal("100"), Decimal("100"), Decimal("100"), Decimal("140")], 2)[-1]
    )


def test_parameter_and_cursor_validation_is_not_bypassed_by_model_copy():
    with pytest.raises(ValidationError):
        prepare(parameters=SMALL.model_copy(update={"ema_fast": 0}))
    with pytest.raises(ValidationError):
        prepare(previous=prepare().checkpoint.model_copy(update={"bar_count": 0}))


def test_supported_feed_label_is_not_origin_attestation():
    frame = prepare(feed_id="binance_spot_public")
    assert frame.status == "READY"
    assert frame.source_origin_verified is False
    assert frame.execution_authority is False
    with pytest.raises(NativeBarError, match="unsupported_feed"):
        prepare(feed_id="unknown")


@pytest.mark.parametrize("mode", ["duplicate", "append"])
def test_revised_old_candle_is_not_accepted_even_when_last_bar_matches(mode):
    history = bars()
    cursor = prepare(history).checkpoint
    history[2] = {**history[2], "volume": "2"}
    if mode == "append":
        history.append({**history[-1], "timestamp": NOW})
    with pytest.raises(NativeBarError, match="previous_history_changed"):
        prepare(history, previous=cursor, now=NOW + (STEP if mode == "append" else timedelta(0)))


def test_multiple_unprocessed_bars_cannot_be_skipped():
    history = bars()
    cursor = prepare(history).checkpoint
    history += [{**history[-1], "timestamp": NOW}, {**history[-1], "timestamp": NOW + STEP}]
    with pytest.raises(NativeBarError, match="exactly_one_next_bar"):
        prepare(history, previous=cursor, now=NOW + STEP * 2)


def test_seed_scope_and_parameters_cannot_change_on_resume():
    cursor = prepare().checkpoint
    cases = [
        {"candles": bars(17, NOW + STEP), "now": NOW + STEP},
        {"feed_id": "binance_spot_public"},
        {"parameters": SMALL.model_copy(update={"ema_fast": 3})},
    ]
    for changes in cases:
        with pytest.raises(NativeBarError, match="scope_or_seed"):
            prepare(previous=cursor, **changes)


def test_canonical_decimal_and_utc_representations_hash_equally():
    history = bars()
    first = prepare(history)
    history[0] = {
        **history[0],
        "close": "100.00000000",
        "volume": "1.000",
        "timestamp": history[0]["timestamp"].astimezone(timezone(timedelta(hours=2))),
    }
    assert prepare(history).checkpoint.history_sha256 == first.checkpoint.history_sha256


@pytest.mark.parametrize(
    "changes",
    [
        {"timestamp": NOW - STEP},
        {"entry_price": "100.5"},
        {"symbol": "ETHUSDT"},
        {"timeframe": "1h"},
        {"direction": "SHORT", "stop_loss": "105", "take_profit": "88"},
    ],
)
def test_signal_binding_rejects_a_different_bar_price_time_or_scope(changes):
    with pytest.raises(NativeBarError):
        bind_native_signal_to_bar(signal(**changes), prepare())
