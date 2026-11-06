"""Pure closed-bar preflight. No acquisition, strategy execution or cursor writes."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.reference_replay import (
    atr_series,
    complete_higher_timeframe_count,
    ema_series,
    higher_timeframe_ema_series,
    rsi_series,
)
from aurex.backtest_engine.schemas import OhlcvCandle
from aurex.domain.enums import Direction
from aurex.signal_gateway.schemas import NativeSignalPayload

BASE_SECONDS = 900
HIGHER_SECONDS = 3600
MAX_WINDOW_BARS = 4096
MAX_STREAM_BARS = 2_147_483_647
SCHEMA_VERSION = "native_closed_bar_preflight_v1"


class NativeBarError(ValueError):
    """Invalid, stale or discontinuous input; callers must not advance their cursor."""


def aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise NativeBarError("timestamp_timezone_required")
    return value.astimezone(UTC)


class ClosedBar(OhlcvCandle):
    model_config = ConfigDict(frozen=True, extra="forbid")

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        value = aware_utc(value)
        if value.microsecond or int(value.timestamp()) % BASE_SECONDS:
            raise ValueError("candle_open_must_align_to_15m_utc")
        return value

    @field_validator("open", "high", "low", "close", "volume")
    @classmethod
    def validate_number(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value < 0 or value >= Decimal("1000000000000"):
            raise ValueError("candle_value_out_of_range")
        if value != value.quantize(Decimal("0.00000001")):
            raise ValueError("candle_value_exceeds_ledger_precision")
        return value.normalize()

    @model_validator(mode="after")
    def validate_geometry(self) -> "ClosedBar":
        if (
            not 0
            < self.low
            <= min(self.open, self.close)
            <= max(self.open, self.close)
            <= self.high
        ):
            raise ValueError("invalid_ohlc_geometry")
        return self


class NativeIndicatorParameters(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ema_fast: int = Field(default=20, ge=1, le=500, strict=True)
    ema_slow: int = Field(default=50, ge=1, le=500, strict=True)
    ema_trend: int = Field(default=200, ge=1, le=500, strict=True)
    rsi_length: int = Field(default=14, ge=1, le=500, strict=True)
    atr_length: int = Field(default=14, ge=1, le=500, strict=True)
    higher_ema_fast: int = Field(default=50, ge=1, le=500, strict=True)
    higher_ema_slow: int = Field(default=200, ge=1, le=500, strict=True)


class NativeBarCursor(BaseModel):
    """Content checkpoint only; it does not attest to committed signal processing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[
        "native_closed_bar_preflight_v1", "native_closed_bar_continuation_v1"
    ] = SCHEMA_VERSION
    feed_id: Literal["fixture", "binance_spot_public"]
    symbol: Literal["BTCUSDT"] = "BTCUSDT"
    timeframe: Literal["15m"] = "15m"
    first_open: datetime
    last_open: datetime
    bar_count: int = Field(ge=1, le=MAX_STREAM_BARS, strict=True)
    history_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parameters_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("first_open", "last_open")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return aware_utc(value)

    @model_validator(mode="after")
    def validate_version_bounds(self) -> "NativeBarCursor":
        if self.schema_version == SCHEMA_VERSION and self.bar_count > MAX_WINDOW_BARS:
            raise ValueError("legacy_cursor_window_exhausted")
        if self.schema_version != SCHEMA_VERSION and self.bar_count <= MAX_WINDOW_BARS:
            raise ValueError("continuation_cursor_before_window_boundary")
        return self


@dataclass(frozen=True)
class NativeBarFrame:
    status: Literal["READY", "DUPLICATE"]
    bar: ClosedBar
    closed_at: datetime
    candle_id: str
    checkpoint: NativeBarCursor
    indicators: dict[str, Decimal]
    source_origin_verified: bool = False
    execution_authority: bool = False


def content_hash(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def history_hash(candles: list[ClosedBar]) -> str:
    return content_hash([bar.model_dump(mode="json") for bar in candles])


def prepare_native_closed_bar(
    candles: list[OhlcvCandle | dict],
    *,
    now: datetime,
    feed_id: Literal["fixture", "binance_spot_public"],
    parameters: NativeIndicatorParameters | None = None,
    previous: NativeBarCursor | None = None,
    max_age_seconds: int = 180,
) -> NativeBarFrame:
    """Validate one fixed-seed prefix, allowing exactly one new bar after a cursor.

    READY is input readiness, not a trade decision. Persist a returned checkpoint
    only in a future runner's atomic signal/outcome transaction, never by itself.
    """
    observed_at = aware_utc(now)
    if not candles or len(candles) > MAX_WINDOW_BARS:
        raise NativeBarError("window_size_out_of_bounds")
    if type(max_age_seconds) is not int or not 0 <= max_age_seconds <= 180:
        raise NativeBarError("freshness_limit_out_of_bounds")
    if feed_id not in {"fixture", "binance_spot_public"}:
        raise NativeBarError("unsupported_feed")
    settings = NativeIndicatorParameters.model_validate(
        parameters.model_dump() if parameters is not None else {}
    )
    settings_hash = content_hash(settings.model_dump(mode="json"))
    bars = [
        ClosedBar.model_validate(bar.model_dump() if isinstance(bar, BaseModel) else bar)
        for bar in candles
    ]
    for first, second in zip(bars, bars[1:], strict=False):
        if second.timestamp - first.timestamp != timedelta(seconds=BASE_SECONDS):
            raise NativeBarError("duplicate_unsorted_or_gapped_candles")
    current = bars[-1]
    closed_at = current.timestamp + timedelta(seconds=BASE_SECONDS)
    if closed_at > observed_at:
        raise NativeBarError("candle_not_closed")
    digest = history_hash(bars)
    checkpoint = NativeBarCursor(
        feed_id=feed_id,
        first_open=bars[0].timestamp,
        last_open=current.timestamp,
        bar_count=len(bars),
        history_sha256=digest,
        parameters_sha256=settings_hash,
    )
    candle_id = content_hash(
        {
            "feed_id": feed_id,
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "open": current.timestamp.isoformat(),
        }
    )
    if previous is not None:
        previous = NativeBarCursor.model_validate(previous.model_dump())
        if previous.schema_version != SCHEMA_VERSION:
            raise NativeBarError("continuation_requires_incremental_state")
        if (
            previous.feed_id != feed_id
            or previous.parameters_sha256 != settings_hash
            or previous.first_open != bars[0].timestamp
        ):
            raise NativeBarError("cursor_scope_or_seed_changed")
        if len(bars) not in {previous.bar_count, previous.bar_count + 1}:
            raise NativeBarError("cursor_requires_exactly_one_next_bar")
        prefix = bars[: previous.bar_count]
        if (
            prefix[-1].timestamp != previous.last_open
            or history_hash(prefix) != previous.history_sha256
        ):
            raise NativeBarError("previous_history_changed")
        if len(bars) == previous.bar_count:
            # Old retries remain harmless even after the entry freshness deadline.
            return NativeBarFrame("DUPLICATE", current, closed_at, candle_id, checkpoint, {})
    if observed_at - closed_at > timedelta(seconds=max_age_seconds):
        raise NativeBarError("latest_closed_bar_is_stale")
    required_base = max(
        settings.ema_fast,
        settings.ema_slow,
        settings.ema_trend,
        settings.rsi_length + 1,
        settings.atr_length,
    )
    if len(bars) < required_base:
        raise NativeBarError("insufficient_base_warmup")
    epoch = int(current.timestamp.timestamp())
    higher_start = datetime.fromtimestamp(epoch - epoch % HIGHER_SECONDS, tz=UTC)
    higher_count = complete_higher_timeframe_count(
        bars,
        base_seconds=BASE_SECONDS,
        higher_seconds=HIGHER_SECONDS,
        through=higher_start - timedelta(seconds=BASE_SECONDS),
    )
    if higher_count < max(settings.higher_ema_fast, settings.higher_ema_slow):
        raise NativeBarError("insufficient_confirmed_higher_warmup")
    closes = [bar.close for bar in bars]
    higher_fast, higher_slow = higher_timeframe_ema_series(
        bars,
        base_seconds=BASE_SECONDS,
        higher_seconds=HIGHER_SECONDS,
        fast_length=settings.higher_ema_fast,
        slow_length=settings.higher_ema_slow,
    )[-1]
    indicators = {
        "ema_fast": ema_series(closes, settings.ema_fast)[-1],
        "ema_slow": ema_series(closes, settings.ema_slow)[-1],
        "ema_trend": ema_series(closes, settings.ema_trend)[-1],
        "rsi": rsi_series(closes, settings.rsi_length)[-1],
        "atr": atr_series(bars, settings.atr_length)[-1],
        "higher_ema_fast": higher_fast,
        "higher_ema_slow": higher_slow,
    }
    if any(value is None for value in indicators.values()):
        raise NativeBarError("indicators_not_ready")
    return NativeBarFrame("READY", current, closed_at, candle_id, checkpoint, indicators)


def bind_native_signal_to_bar(
    payload: NativeSignalPayload, frame: NativeBarFrame
) -> NativeSignalPayload:
    """Check signal/bar consistency; normal strategy, evidence and risk gates still apply."""
    payload = NativeSignalPayload.model_validate(payload.model_dump())
    if frame.status != "READY":
        raise NativeBarError("duplicate_bar_cannot_emit_signal")
    if (
        payload.symbol != "BTCUSDT"
        or payload.timeframe != "15m"
        or payload.direction != Direction.LONG
    ):
        raise NativeBarError("signal_outside_native_spot_scope")
    if payload.timestamp != frame.closed_at or payload.entry_price != frame.bar.close:
        raise NativeBarError("signal_must_reference_bar_close_time_and_price")
    return payload
