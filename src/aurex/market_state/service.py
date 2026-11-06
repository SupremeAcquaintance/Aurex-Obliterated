from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from aurex.db.base import utc_now
from aurex.db.models import MarketCandle, MarketState, Signal, Symbol
from aurex.domain.enums import Direction, MarketRegime
from aurex.market_state.indicators import (
    CandleInput,
    adx,
    atr_percentile,
    ema,
    volume_relative_average,
    vwap_distance,
)
from aurex.market_state.schemas import CandleImportRequest
from aurex.observability.system_events import SystemEventRecorder
from aurex.strategy_engine.registry import (
    strategy_regime_compatible as registry_strategy_regime_compatible,
)

EMA_FAST = 50
EMA_SLOW = 200
ADX_LENGTH = 14
ATR_LENGTH = 14
ATR_PERCENTILE_WINDOW = 100
VOLUME_WINDOW = 20
VWAP_WINDOW = 20


@dataclass(frozen=True)
class ClassifiedMarketState:
    regime: MarketRegime
    confidence: Decimal
    inputs_snapshot: dict


class MarketStateEngine:
    def __init__(self, session: Session) -> None:
        self.session = session

    def import_candles(self, payload: CandleImportRequest) -> tuple[int, int]:
        symbol = normalize_symbol(payload.symbol)
        symbol_ref = self._get_or_create_symbol(symbol)
        imported = 0
        updated = 0

        for candle_input in payload.candles:
            existing = self.session.execute(
                select(MarketCandle).where(
                    MarketCandle.symbol == symbol,
                    MarketCandle.timeframe == payload.timeframe,
                    MarketCandle.timestamp == candle_input.timestamp,
                )
            ).scalar_one_or_none()

            if existing is None:
                self.session.add(
                    MarketCandle(
                        symbol_id=symbol_ref.id,
                        symbol=symbol,
                        timeframe=payload.timeframe,
                        timestamp=candle_input.timestamp,
                        open=candle_input.open,
                        high=candle_input.high,
                        low=candle_input.low,
                        close=candle_input.close,
                        volume=candle_input.volume,
                        source=payload.source,
                    )
                )
                imported += 1
            else:
                existing.open = candle_input.open
                existing.high = candle_input.high
                existing.low = candle_input.low
                existing.close = candle_input.close
                existing.volume = candle_input.volume
                existing.source = payload.source
                updated += 1

        SystemEventRecorder(self.session).info(
            "market_state",
            "Market candles imported",
            {
                "symbol": symbol,
                "timeframe": payload.timeframe,
                "imported": imported,
                "updated": updated,
            },
        )
        self.session.flush()
        return imported, updated

    def compute_state(
        self,
        symbol: str,
        timeframe: str,
        higher_timeframe: str | None = None,
        limit: int = 240,
        signal: Signal | None = None,
    ) -> MarketState | None:
        normalized_symbol = normalize_symbol(symbol)
        candles = self._load_candles(normalized_symbol, timeframe, limit)
        if len(candles) < EMA_SLOW:
            return None

        higher_candles = (
            self._load_candles(normalized_symbol, higher_timeframe, limit)
            if higher_timeframe
            else []
        )
        classified = classify_market_state(candles, higher_candles)
        symbol_ref = self._get_or_create_symbol(normalized_symbol)
        state = MarketState(
            signal=signal,
            symbol_id=symbol_ref.id,
            symbol=normalized_symbol,
            timeframe=timeframe,
            regime=classified.regime,
            confidence=classified.confidence,
            inputs_snapshot=classified.inputs_snapshot,
            calculated_at=utc_now(),
        )
        self.session.add(state)

        if signal is not None:
            signal.market_regime = classified.regime

        SystemEventRecorder(self.session).info(
            "market_state",
            "Market state computed",
            {
                "signal_id": signal.id if signal else None,
                "symbol": normalized_symbol,
                "timeframe": timeframe,
                "regime": classified.regime.value,
                "confidence": str(classified.confidence),
            },
        )
        self.session.flush()
        return state

    def enrich_signal(self, signal: Signal) -> MarketState | None:
        state = self.compute_state(
            signal.symbol,
            signal.timeframe,
            higher_timeframe=None,
            signal=signal,
        )
        return state

    def _load_candles(
        self,
        symbol: str,
        timeframe: str | None,
        limit: int,
    ) -> list[CandleInput]:
        if timeframe is None:
            return []
        rows = list(
            self.session.execute(
                select(MarketCandle)
                .where(MarketCandle.symbol == symbol, MarketCandle.timeframe == timeframe)
                .order_by(MarketCandle.timestamp.desc())
                .limit(limit)
            ).scalars()
        )
        rows.reverse()
        return [
            CandleInput(
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume,
            )
            for row in rows
        ]

    def _get_or_create_symbol(self, symbol: str) -> Symbol:
        existing = self.session.execute(
            select(Symbol).where(Symbol.symbol == symbol)
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        created = Symbol(symbol=symbol)
        self.session.add(created)
        self.session.flush()
        return created


def classify_market_state(
    candles: list[CandleInput],
    higher_candles: list[CandleInput] | None = None,
) -> ClassifiedMarketState:
    closes = [candle.close for candle in candles]
    ema_fast_values = ema(closes, EMA_FAST)
    ema_slow_values = ema(closes, EMA_SLOW)
    ema_fast_current = ema_fast_values[-1]
    ema_slow_current = ema_slow_values[-1]
    ema_slow_previous = ema_slow_values[-10] if len(ema_slow_values) >= 10 else ema_slow_values[0]
    ema_slope = (
        (ema_slow_current - ema_slow_previous) / ema_slow_previous
        if ema_slow_previous
        else Decimal("0")
    )
    adx_value = adx(candles, ADX_LENGTH)
    atr_pct = atr_percentile(candles, ATR_LENGTH, ATR_PERCENTILE_WINDOW)
    volume_ratio = volume_relative_average(candles, VOLUME_WINDOW)
    vwap_dist = vwap_distance(candles, VWAP_WINDOW)
    higher_trend = classify_higher_timeframe_trend(higher_candles or [])

    regime = choose_regime(
        ema_fast_current=ema_fast_current,
        ema_slow_current=ema_slow_current,
        ema_slope=ema_slope,
        adx_value=adx_value,
        atr_pct=atr_pct,
        volume_ratio=volume_ratio,
        vwap_dist=vwap_dist,
        higher_trend=higher_trend,
    )
    confidence = calculate_confidence(regime, adx_value, atr_pct, volume_ratio, ema_slope)

    return ClassifiedMarketState(
        regime=regime,
        confidence=confidence,
        inputs_snapshot={
            "ema_fast": str(ema_fast_current),
            "ema_slow": str(ema_slow_current),
            "ema_slope": str(ema_slope),
            "adx": str(adx_value),
            "atr_percentile": str(atr_pct),
            "volume_relative_average": str(volume_ratio),
            "vwap_distance": str(vwap_dist),
            "higher_timeframe_trend": higher_trend,
        },
    )


def classify_higher_timeframe_trend(candles: list[CandleInput]) -> str:
    if len(candles) < EMA_SLOW:
        return "UNKNOWN"
    closes = [candle.close for candle in candles]
    fast = ema(closes, EMA_FAST)[-1]
    slow = ema(closes, EMA_SLOW)[-1]
    if fast > slow:
        return "UP"
    if fast < slow:
        return "DOWN"
    return "FLAT"


def choose_regime(
    *,
    ema_fast_current: Decimal,
    ema_slow_current: Decimal,
    ema_slope: Decimal,
    adx_value: Decimal,
    atr_pct: Decimal,
    volume_ratio: Decimal,
    vwap_dist: Decimal,
    higher_trend: str,
) -> MarketRegime:
    slope_abs = abs(ema_slope)
    if atr_pct >= Decimal("0.85") and abs(vwap_dist) > Decimal("0.025"):
        return MarketRegime.HIGH_VOLATILITY
    if atr_pct <= Decimal("0.2") and volume_ratio < Decimal("0.9"):
        return MarketRegime.LOW_VOLATILITY
    if adx_value >= Decimal("25") and atr_pct >= Decimal("0.6") and volume_ratio >= Decimal("1.15"):
        return MarketRegime.BREAKOUT_EXPANSION
    if (
        adx_value < Decimal("15")
        and atr_pct >= Decimal("0.7")
        and (volume_ratio >= Decimal("1.2") or abs(vwap_dist) >= Decimal("0.01"))
    ):
        return MarketRegime.CHOPPY_DANGER_ZONE
    if adx_value < Decimal("20") and slope_abs < Decimal("0.003"):
        return MarketRegime.RANGING
    if (
        adx_value >= Decimal("20")
        and ema_fast_current > ema_slow_current
        and ema_slope > 0
        and higher_trend != "DOWN"
    ):
        return MarketRegime.TRENDING_UP
    if (
        adx_value >= Decimal("20")
        and ema_fast_current < ema_slow_current
        and ema_slope < 0
        and higher_trend != "UP"
    ):
        return MarketRegime.TRENDING_DOWN
    return MarketRegime.UNKNOWN


def calculate_confidence(
    regime: MarketRegime,
    adx_value: Decimal,
    atr_pct: Decimal,
    volume_ratio: Decimal,
    ema_slope: Decimal,
) -> Decimal:
    if regime == MarketRegime.UNKNOWN:
        return Decimal("0.25")

    score = Decimal("0.35")
    if adx_value >= Decimal("20"):
        score += Decimal("0.2")
    if atr_pct >= Decimal("0.6") or atr_pct <= Decimal("0.2"):
        score += Decimal("0.15")
    if volume_ratio >= Decimal("1.0"):
        score += Decimal("0.15")
    if abs(ema_slope) >= Decimal("0.003"):
        score += Decimal("0.15")
    return min(score, Decimal("1.0"))


def strategy_regime_compatible(
    strategy: str,
    direction: Direction,
    regime: MarketRegime,
) -> bool:
    return registry_strategy_regime_compatible(strategy, direction, regime)


def normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper().replace(" ", "")
