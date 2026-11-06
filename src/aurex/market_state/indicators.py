from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CandleInput:
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


def ema(values: list[Decimal], length: int) -> list[Decimal]:
    if length <= 0:
        raise ValueError("EMA length must be positive")
    if not values:
        return []

    smoothing = Decimal("2") / Decimal(length + 1)
    results = [values[0]]
    for value in values[1:]:
        results.append((value * smoothing) + (results[-1] * (Decimal("1") - smoothing)))
    return results


def true_ranges(candles: list[CandleInput]) -> list[Decimal]:
    ranges: list[Decimal] = []
    previous_close: Decimal | None = None
    for candle in candles:
        if previous_close is None:
            ranges.append(candle.high - candle.low)
        else:
            ranges.append(
                max(
                    candle.high - candle.low,
                    abs(candle.high - previous_close),
                    abs(candle.low - previous_close),
                )
            )
        previous_close = candle.close
    return ranges


def simple_average(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal("0")
    return sum(values, Decimal("0")) / Decimal(len(values))


def atr(candles: list[CandleInput], length: int) -> Decimal:
    return simple_average(true_ranges(candles)[-length:])


def atr_percentile(candles: list[CandleInput], atr_length: int, window: int) -> Decimal:
    ranges = true_ranges(candles)
    if len(ranges) < atr_length:
        return Decimal("0")

    atr_values: list[Decimal] = []
    for index in range(atr_length, len(ranges) + 1):
        atr_values.append(simple_average(ranges[index - atr_length : index]))

    recent = atr_values[-window:] if len(atr_values) >= window else atr_values
    current = recent[-1]
    if not recent:
        return Decimal("0")
    below_or_equal = sum(1 for value in recent if value <= current)
    return Decimal(below_or_equal) / Decimal(len(recent))


def adx(candles: list[CandleInput], length: int) -> Decimal:
    if len(candles) < length + 1:
        return Decimal("0")

    plus_dm: list[Decimal] = []
    minus_dm: list[Decimal] = []
    ranges = true_ranges(candles)

    for index in range(1, len(candles)):
        up_move = candles[index].high - candles[index - 1].high
        down_move = candles[index - 1].low - candles[index].low
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else Decimal("0"))
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else Decimal("0"))

    dx_values: list[Decimal] = []
    for index in range(length, len(candles)):
        tr_sum = sum(ranges[index - length + 1 : index + 1], Decimal("0"))
        if tr_sum == 0:
            dx_values.append(Decimal("0"))
            continue
        plus_di = Decimal("100") * sum(plus_dm[index - length : index], Decimal("0")) / tr_sum
        minus_di = Decimal("100") * sum(minus_dm[index - length : index], Decimal("0")) / tr_sum
        denominator = plus_di + minus_di
        dx_values.append(
            Decimal("0")
            if denominator == 0
            else Decimal("100") * abs(plus_di - minus_di) / denominator
        )

    return simple_average(dx_values[-length:])


def vwap_distance(candles: list[CandleInput], window: int) -> Decimal:
    recent = candles[-window:] if len(candles) >= window else candles
    volume_sum = sum((candle.volume for candle in recent), Decimal("0"))
    if not recent or volume_sum == 0:
        return Decimal("0")

    typical_volume_sum = sum(
        (((candle.high + candle.low + candle.close) / Decimal("3")) * candle.volume)
        for candle in recent
    )
    vwap = typical_volume_sum / volume_sum
    if vwap == 0:
        return Decimal("0")
    return (recent[-1].close - vwap) / vwap


def volume_relative_average(candles: list[CandleInput], window: int) -> Decimal:
    recent = candles[-window:] if len(candles) >= window else candles
    if not recent:
        return Decimal("0")
    average_volume = simple_average([candle.volume for candle in recent])
    if average_volume == 0:
        return Decimal("0")
    return recent[-1].volume / average_volume

