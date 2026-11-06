"""Bounded indicator state with exact recurrence parity to the reference replay."""

from datetime import datetime, timedelta
from decimal import ROUND_HALF_EVEN, Decimal, DivisionByZero, InvalidOperation, Overflow, getcontext
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.reference_replay import ema_series, rsi_value
from aurex.signal_gateway.native_bars import (
    BASE_SECONDS,
    MAX_STREAM_BARS,
    MAX_WINDOW_BARS,
    ClosedBar,
    NativeBarCursor,
    NativeBarError,
    NativeBarFrame,
    NativeIndicatorParameters,
    aware_utc,
    content_hash,
    prepare_native_closed_bar,
)

ZERO = Decimal("0")


def require_replay_arithmetic() -> None:
    context = getcontext()
    if (
        context.prec != 28
        or context.rounding != ROUND_HALF_EVEN
        or context.Emin != -999999
        or context.Emax != 999999
        or context.clamp != 0
        or {signal for signal, enabled in context.traps.items() if enabled}
        != {DivisionByZero, InvalidOperation, Overflow}
    ):
        raise NativeBarError("continuation_requires_decimal28_half_even")


class NativeIndicatorState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    schema_version: Literal["native_indicators_v1"] = "native_indicators_v1"
    arithmetic: Literal["decimal28_half_even"] = "decimal28_half_even"
    parameters: NativeIndicatorParameters
    first_open: datetime
    last_bar: ClosedBar
    bar_count: int = Field(ge=1, le=MAX_STREAM_BARS, strict=True)
    ema_fast: Decimal = Field(gt=0)
    ema_slow: Decimal = Field(gt=0)
    ema_trend: Decimal = Field(gt=0)
    average_gain: Decimal = Field(ge=0)
    average_loss: Decimal = Field(ge=0)
    atr: Decimal = Field(ge=0)
    higher_fast: Decimal = Field(gt=0)
    higher_slow: Decimal = Field(gt=0)
    visible_higher_fast: Decimal = Field(gt=0)
    visible_higher_slow: Decimal = Field(gt=0)
    higher_count: int = Field(ge=1, le=MAX_STREAM_BARS, strict=True)
    hour_count: int = Field(ge=1, le=4, strict=True)

    @field_validator("first_open")
    @classmethod
    def validate_time(cls, value: datetime) -> datetime:
        return aware_utc(value)

    @model_validator(mode="after")
    def validate_span(self) -> "NativeIndicatorState":
        if (
            self.last_bar.timestamp - self.first_open
            != timedelta(seconds=(self.bar_count - 1) * BASE_SECONDS)
            or self.hour_count != self.last_bar.timestamp.minute // 15 + 1
            or self.higher_count > self.bar_count // 4
        ):
            raise ValueError("indicator_state_span_invalid")
        return self

    def indicators(self) -> dict[str, Decimal]:
        require_replay_arithmetic()
        return {
            "ema_fast": self.ema_fast,
            "ema_slow": self.ema_slow,
            "ema_trend": self.ema_trend,
            "rsi": rsi_value(self.average_gain, self.average_loss),
            "atr": self.atr,
            "higher_ema_fast": self.visible_higher_fast,
            "higher_ema_slow": self.visible_higher_slow,
        }


def initialize_continuation(
    history: list[ClosedBar], parameters: NativeIndicatorParameters
) -> NativeIndicatorState:
    require_replay_arithmetic()
    if not history:
        raise NativeBarError("continuation_seed_empty")
    if len(history) > MAX_WINDOW_BARS:
        raise NativeBarError("window_size_out_of_bounds")
    history = [ClosedBar.model_validate(bar.model_dump()) for bar in history]
    frame = prepare_native_closed_bar(
        history,
        now=history[-1].timestamp + timedelta(seconds=BASE_SECONDS),
        feed_id="fixture",
        parameters=parameters,
    )
    gains = [max(b.close - a.close, ZERO) for a, b in zip(history, history[1:], strict=False)]
    losses = [max(a.close - b.close, ZERO) for a, b in zip(history, history[1:], strict=False)]
    length = parameters.rsi_length
    average_gain = sum(gains[:length], ZERO) / Decimal(length)
    average_loss = sum(losses[:length], ZERO) / Decimal(length)
    for gain, loss in zip(gains[length:], losses[length:], strict=True):
        average_gain = (average_gain * (length - 1) + gain) / Decimal(length)
        average_loss = (average_loss * (length - 1) + loss) / Decimal(length)
    # A full hour needs its :00, :15, :30 and :45 rows; the first hour can be partial.
    completed = [
        bar.close
        for index, bar in enumerate(history)
        if bar.timestamp.minute == 45 and index >= 3 and history[index - 3].timestamp.minute == 0
    ]
    state = NativeIndicatorState(
        parameters=parameters,
        first_open=history[0].timestamp,
        last_bar=history[-1],
        bar_count=len(history),
        ema_fast=frame.indicators["ema_fast"],
        ema_slow=frame.indicators["ema_slow"],
        ema_trend=frame.indicators["ema_trend"],
        average_gain=average_gain,
        average_loss=average_loss,
        atr=frame.indicators["atr"],
        higher_fast=ema_series(completed, parameters.higher_ema_fast)[-1],
        higher_slow=ema_series(completed, parameters.higher_ema_slow)[-1],
        visible_higher_fast=frame.indicators["higher_ema_fast"],
        visible_higher_slow=frame.indicators["higher_ema_slow"],
        higher_count=len(completed),
        hour_count=history[-1].timestamp.minute // 15 + 1,
    )
    if state.indicators() != frame.indicators:
        raise NativeBarError("continuation_seed_indicator_mismatch")
    return state


def advance_indicators(state: NativeIndicatorState, bar: ClosedBar) -> NativeIndicatorState:
    require_replay_arithmetic()
    state = NativeIndicatorState.model_validate(state.model_dump())
    bar = ClosedBar.model_validate(bar.model_dump())
    if bar.timestamp - state.last_bar.timestamp != timedelta(seconds=BASE_SECONDS):
        raise NativeBarError("continuation_requires_one_next_bar")
    if state.bar_count == MAX_STREAM_BARS:
        raise NativeBarError("continuation_counter_exhausted")
    parameters = state.parameters
    changes = {}
    for key in ("ema_fast", "ema_slow", "ema_trend"):
        changes[key] = ema_series([getattr(state, key), bar.close], getattr(parameters, key))[-1]
    gain = max(bar.close - state.last_bar.close, ZERO)
    loss = max(state.last_bar.close - bar.close, ZERO)
    length = parameters.rsi_length
    changes["average_gain"] = (state.average_gain * (length - 1) + gain) / Decimal(length)
    changes["average_loss"] = (state.average_loss * (length - 1) + loss) / Decimal(length)
    true_range = max(
        bar.high - bar.low,
        abs(bar.high - state.last_bar.close),
        abs(bar.low - state.last_bar.close),
    )
    changes["atr"] = (state.atr * (parameters.atr_length - 1) + true_range) / Decimal(
        parameters.atr_length
    )
    if bar.timestamp.minute == 0:
        changes.update(visible_higher_fast=state.higher_fast, visible_higher_slow=state.higher_slow)
    if bar.timestamp.minute == 45:
        changes.update(
            higher_fast=ema_series([state.higher_fast, bar.close], parameters.higher_ema_fast)[-1],
            higher_slow=ema_series([state.higher_slow, bar.close], parameters.higher_ema_slow)[-1],
            higher_count=state.higher_count + 1,
        )
    return NativeIndicatorState.model_validate(
        {
            **state.model_dump(),
            **changes,
            "last_bar": bar,
            "bar_count": state.bar_count + 1,
            "hour_count": bar.timestamp.minute // 15 + 1,
        }
    )


def continuation_frame(
    state: NativeIndicatorState, previous: NativeBarCursor, bar: ClosedBar
) -> tuple[NativeBarFrame, NativeIndicatorState]:
    """Reconstruct arithmetic only; the transaction owner must separately enforce entry age."""
    require_replay_arithmetic()
    state = NativeIndicatorState.model_validate(state.model_dump())
    bar = ClosedBar.model_validate(bar.model_dump())
    previous = NativeBarCursor.model_validate(previous.model_dump())
    if (
        state.bar_count != previous.bar_count
        or state.first_open != previous.first_open
        or state.last_bar.timestamp != previous.last_open
        or content_hash(state.parameters.model_dump(mode="json")) != previous.parameters_sha256
    ):
        raise NativeBarError("continuation_state_cursor_mismatch")
    updated = advance_indicators(state, bar)
    checkpoint = NativeBarCursor(
        schema_version="native_closed_bar_continuation_v1",
        feed_id=previous.feed_id,
        first_open=previous.first_open,
        last_open=bar.timestamp,
        bar_count=updated.bar_count,
        parameters_sha256=previous.parameters_sha256,
        history_sha256=content_hash(
            {
                "schema": "native_bar_chain_v1",
                "previous_schema": previous.schema_version,
                "previous_hash": previous.history_sha256,
                "bar": bar.model_dump(mode="json"),
            }
        ),
    )
    candle_id = content_hash(
        {
            "feed_id": previous.feed_id,
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "open": bar.timestamp.isoformat(),
        }
    )
    return NativeBarFrame(
        "READY",
        bar,
        bar.timestamp + timedelta(seconds=BASE_SECONDS),
        candle_id,
        checkpoint,
        updated.indicators(),
    ), updated
