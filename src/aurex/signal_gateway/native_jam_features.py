"""Bounded Jam replay arithmetic only, not a source witness or trading authority.

Serialized states must eventually be reconstructed from the retained native chain
before use by an evaluator. Structural validation alone cannot authenticate history.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.reference_replay import ema_series
from aurex.signal_gateway.native_bars import (
    BASE_SECONDS,
    MAX_STREAM_BARS,
    MAX_WINDOW_BARS,
    ClosedBar,
    NativeBarError,
    aware_utc,
)
from aurex.signal_gateway.native_continuation import require_replay_arithmetic

ZERO = Decimal("0")
HUNDRED = Decimal("100")
STEP = timedelta(seconds=BASE_SECONDS)
Length = Annotated[int, Field(ge=1, le=500, strict=True)]
Nonnegative = Annotated[Decimal, Field(ge=0)]
Positive = Annotated[Decimal, Field(gt=0)]


class FeatureModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class JamFeatureParameters(FeatureModel):
    """Explicit feature lengths, not a strategy selection or full settings contract."""

    symbol: Literal["BTCUSDT"] = "BTCUSDT"
    timeframe: Literal["15m"] = "15m"
    higher_timeframe: Literal["60"] = "60"
    trend_ema: Length
    pullback_ema: Length
    atr_length: Length
    volume_length: Length
    adx_length: Length
    adx_smoothing: Length
    impulse_lookback: Length
    htf_ema_fast: Length
    htf_ema_slow: Length

    @property
    def buffer_size(self) -> int:
        return max(self.volume_length, self.impulse_lookback + 1, 2)

    @property
    def required_base_history(self) -> int:
        return max(
            self.trend_ema,
            self.pullback_ema,
            self.atr_length + 1,
            self.adx_length + self.adx_smoothing,
            self.volume_length,
            self.impulse_lookback + 1,
        )


class RmaState(FeatureModel):
    length: Length
    sample_count: int = Field(ge=0, le=MAX_STREAM_BARS, strict=True)
    seed: tuple[Nonnegative, ...] = Field(max_length=499)
    average: Nonnegative | None

    @model_validator(mode="after")
    def validate_seed(self) -> "RmaState":
        if self.sample_count < self.length:
            if self.average is not None or len(self.seed) != self.sample_count:
                raise ValueError("jam_rma_seed_invalid")
        elif self.average is None or self.seed:
            raise ValueError("jam_rma_average_invalid")
        return self


def _rma(state: RmaState, value: Decimal | None) -> RmaState:
    if value is None:
        return state
    seed = state.seed
    average = state.average
    if average is None:
        seed = (*seed, value)
        if len(seed) == state.length:
            average = sum(seed, ZERO) / Decimal(state.length)
            seed = ()
    else:
        average = (average * (state.length - 1) + value) / Decimal(state.length)
    return RmaState(
        length=state.length, sample_count=state.sample_count + 1, seed=seed, average=average
    )


def _dmi(
    tr: RmaState, plus: RmaState, minus: RmaState
) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    if tr.average in (None, ZERO) or plus.average is None or minus.average is None:
        return None, None, None
    plus_value = HUNDRED * plus.average / tr.average
    minus_value = HUNDRED * minus.average / tr.average
    total = plus_value + minus_value
    dx = HUNDRED * abs(plus_value - minus_value) / total if total > 0 else ZERO
    return plus_value, minus_value, dx


class JamFeatureState(FeatureModel):
    schema_version: Literal["native_jam_features_v1"] = "native_jam_features_v1"
    arithmetic: Literal["decimal28_half_even"] = "decimal28_half_even"
    parameters: JamFeatureParameters
    first_open: datetime
    bar_count: int = Field(ge=1, le=MAX_STREAM_BARS, strict=True)
    recent: tuple[ClosedBar, ...] = Field(min_length=1, max_length=501)
    trend_ema: Positive
    pullback_ema: Positive
    previous_pullback_ema: Positive | None
    previous_atr: Nonnegative | None
    atr: RmaState
    true_range: RmaState
    plus_dm: RmaState
    minus_dm: RmaState
    adx: RmaState
    higher_fast: Positive | None
    higher_slow: Positive | None
    visible_higher_fast: Positive | None
    visible_higher_slow: Positive | None

    @field_validator("first_open")
    @classmethod
    def validate_time(cls, value: datetime) -> datetime:
        value = aware_utc(value)
        if value.microsecond or int(value.timestamp()) % BASE_SECONDS:
            raise ValueError("jam_first_open_unaligned")
        return value

    @property
    def complete_hours(self) -> int:
        first_full_hour = self.first_open.replace(minute=0)
        if self.first_open.minute:
            first_full_hour += timedelta(hours=1)
        return max(0, (self.recent[-1].timestamp + STEP - first_full_hour) // timedelta(hours=1))

    @model_validator(mode="after")
    def validate_state(self) -> "JamFeatureState":
        p = self.parameters
        if len(self.recent) != min(self.bar_count, p.buffer_size) or any(
            bar.timestamp != self.first_open + STEP * (self.bar_count - len(self.recent) + index)
            for index, bar in enumerate(self.recent)
        ):
            raise ValueError("jam_feature_span_invalid")
        for name, length in (
            ("atr", p.atr_length),
            ("true_range", p.adx_length),
            ("plus_dm", p.adx_length),
            ("minus_dm", p.adx_length),
        ):
            state = getattr(self, name)
            if state.length != length or state.sample_count != self.bar_count:
                raise ValueError("jam_rma_parameter_or_count_mismatch")
        if self.adx.length != p.adx_smoothing or self.adx.sample_count > max(
            0, self.bar_count - p.adx_length + 1
        ):
            raise ValueError("jam_adx_parameter_or_count_mismatch")
        if (self.previous_atr is None) != (self.bar_count <= p.atr_length) or (
            self.previous_pullback_ema is None
        ) != (self.bar_count == 1):
            raise ValueError("jam_previous_feature_invalid")
        completed_now = self.recent[-1].timestamp.minute == 45 and self.complete_hours > 0
        visible_hours = self.complete_hours - int(completed_now)
        if any(
            (value is None) != (self.complete_hours == 0)
            for value in (self.higher_fast, self.higher_slow)
        ) or any(
            (value is None) != (visible_hours == 0)
            for value in (self.visible_higher_fast, self.visible_higher_slow)
        ):
            raise ValueError("jam_higher_visibility_invalid")
        return self


class JamFeatureFrame(FeatureModel):
    bar: ClosedBar
    previous_bar: ClosedBar | None
    trend_ema: Positive
    pullback_ema: Positive
    previous_pullback_ema: Positive | None
    atr: Nonnegative | None
    previous_atr: Nonnegative | None
    volume_average: Nonnegative | None
    dmi_plus: Nonnegative | None
    dmi_minus: Nonnegative | None
    adx: Nonnegative | None
    higher_fast: Positive | None
    higher_slow: Positive | None
    local_reversal: bool
    warmup_ready: bool
    source_origin_verified: Literal[False] = False
    execution_authority: Literal[False] = False


def jam_feature_frame(state: JamFeatureState) -> JamFeatureFrame:
    require_replay_arithmetic()
    state = JamFeatureState.model_validate(state.model_dump())
    p = state.parameters
    previous = state.recent[:-1][-p.impulse_lookback :]
    local_reversal = bool(previous) and (
        previous[-1].close <= min(bar.close for bar in previous)
        or previous[-1].low <= min(bar.low for bar in previous)
    )
    volume = (
        sum((bar.volume for bar in state.recent[-p.volume_length :]), ZERO)
        / Decimal(p.volume_length)
        if state.bar_count >= p.volume_length
        else None
    )
    plus, minus, dx = _dmi(state.true_range, state.plus_dm, state.minus_dm)
    # Missing DX suppresses this bar's ADX, but must not reset its RMA history.
    adx = state.adx.average if dx is not None else None
    ready = (
        state.bar_count >= p.required_base_history
        and state.complete_hours >= max(p.htf_ema_fast, p.htf_ema_slow)
        and all(
            value is not None
            for value in (
                state.atr.average,
                volume,
                plus,
                minus,
                adx,
                state.visible_higher_fast,
                state.visible_higher_slow,
            )
        )
    )
    return JamFeatureFrame(
        bar=state.recent[-1],
        previous_bar=state.recent[-2] if state.bar_count > 1 else None,
        trend_ema=state.trend_ema,
        pullback_ema=state.pullback_ema,
        previous_pullback_ema=state.previous_pullback_ema,
        atr=state.atr.average,
        previous_atr=state.previous_atr,
        volume_average=volume,
        dmi_plus=plus,
        dmi_minus=minus,
        adx=adx,
        higher_fast=state.visible_higher_fast,
        higher_slow=state.visible_higher_slow,
        local_reversal=local_reversal,
        warmup_ready=ready,
    )


def initialize_jam_features(
    history: list[ClosedBar], parameters: JamFeatureParameters
) -> JamFeatureState:
    require_replay_arithmetic()
    if not history or len(history) > MAX_WINDOW_BARS:
        raise NativeBarError("jam_seed_size_out_of_bounds")
    parameters = JamFeatureParameters.model_validate(parameters.model_dump())
    state: JamFeatureState | None = None
    for bar in history:
        state = _advance(state, ClosedBar.model_validate(bar.model_dump()), parameters)
    assert state is not None
    return state


def advance_jam_features(state: JamFeatureState, bar: ClosedBar) -> JamFeatureState:
    require_replay_arithmetic()
    state = JamFeatureState.model_validate(state.model_dump())
    bar = ClosedBar.model_validate(bar.model_dump())
    return _advance(state, bar, state.parameters)


def _advance(
    state: JamFeatureState | None, bar: ClosedBar, p: JamFeatureParameters
) -> JamFeatureState:
    if state is not None:
        if bar.timestamp - state.recent[-1].timestamp != STEP:
            raise NativeBarError("jam_requires_one_next_bar")
        if state.bar_count == MAX_STREAM_BARS:
            raise NativeBarError("jam_counter_exhausted")
    previous = state.recent[-1] if state else None
    tr = (
        max(bar.high - bar.low, abs(bar.high - previous.close), abs(bar.low - previous.close))
        if previous
        else bar.high - bar.low
    )
    up = bar.high - previous.high if previous else ZERO
    down = previous.low - bar.low if previous else ZERO
    plus = up if up > down and up > 0 else ZERO
    minus = down if down > up and down > 0 else ZERO

    def rma(name: str, length: int, value: Decimal | None) -> RmaState:
        old = (
            getattr(state, name)
            if state
            else RmaState(length=length, sample_count=0, seed=(), average=None)
        )
        return _rma(old, value)

    atr = rma("atr", p.atr_length, tr)
    true_range = rma("true_range", p.adx_length, tr)
    plus_dm = rma("plus_dm", p.adx_length, plus)
    minus_dm = rma("minus_dm", p.adx_length, minus)
    adx = rma("adx", p.adx_smoothing, _dmi(true_range, plus_dm, minus_dm)[2])
    higher_fast = state.higher_fast if state else None
    higher_slow = state.higher_slow if state else None
    visible_fast = state.visible_higher_fast if state else None
    visible_slow = state.visible_higher_slow if state else None
    if bar.timestamp.minute == 0:
        visible_fast, visible_slow = higher_fast, higher_slow
    first = state.first_open if state else bar.timestamp
    if bar.timestamp.minute == 45 and bar.timestamp - first >= 3 * STEP:
        higher_fast = (
            ema_series([higher_fast, bar.close], p.htf_ema_fast)[-1]
            if higher_fast is not None
            else bar.close
        )
        higher_slow = (
            ema_series([higher_slow, bar.close], p.htf_ema_slow)[-1]
            if higher_slow is not None
            else bar.close
        )
    return JamFeatureState(
        parameters=p,
        first_open=first,
        bar_count=state.bar_count + 1 if state else 1,
        recent=(*(state.recent if state else ()), bar)[-p.buffer_size :],
        trend_ema=ema_series([state.trend_ema, bar.close], p.trend_ema)[-1] if state else bar.close,
        pullback_ema=ema_series([state.pullback_ema, bar.close], p.pullback_ema)[-1]
        if state
        else bar.close,
        previous_pullback_ema=state.pullback_ema if state else None,
        previous_atr=state.atr.average if state else None,
        atr=atr,
        true_range=true_range,
        plus_dm=plus_dm,
        minus_dm=minus_dm,
        adx=adx,
        higher_fast=higher_fast,
        higher_slow=higher_slow,
        visible_higher_fast=visible_fast,
        visible_higher_slow=visible_slow,
    )
