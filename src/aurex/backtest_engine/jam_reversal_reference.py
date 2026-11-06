from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_FLOOR, Decimal

from sqlalchemy.orm import Session

from aurex.backtest_engine.datasets import OhlcvDatasetLab, ensure_utc, normalize_timeframe
from aurex.backtest_engine.schemas import (
    OhlcvCandle,
    ReferenceReplayRequest,
    ReferenceReplayResponse,
    ReferenceReplayTrade,
)
from aurex.backtest_engine.service import KNOWN_STRATEGY_REQUIRED_PARAMETERS
from aurex.domain.enums import Direction

JAM_REVERSAL_SPOT_ENGINE_VERSION = "jam-reversal-spot-reference-v1.0.0"
ZERO = Decimal("0")
ONE_HUNDRED = Decimal("100")


@dataclass
class PendingLongJam:
    armed_index: int
    trigger: Decimal
    stop_loss: Decimal
    failure_level: Decimal


@dataclass
class JamOpenPosition:
    direction: Direction
    entry_index: int
    entry_at: datetime
    signal_price: Decimal
    entry_price: Decimal
    initial_stop_loss: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    quantity: Decimal
    entry_fee: Decimal
    entry_slippage: Decimal
    initial_risk_per_unit: Decimal
    initial_risk: Decimal
    point_value: Decimal
    market_regime: str
    failure_level: Decimal
    best_price: Decimal


def run_jam_reversal_spot_reference_replay(
    session: Session,
    request: ReferenceReplayRequest,
) -> ReferenceReplayResponse:
    from aurex.backtest_engine.reference_replay import (
        atr_series,
        complete_higher_timeframe_count,
        documented_outage_coverage_reasons,
        ema_series,
        higher_timeframe_ema_series,
        replay_response,
        simple_moving_average_series,
    )

    if (
        request.strategy != "jam_reversal_spot_v1"
        or request.strategy_version != "1.0.1"
    ):
        raise ValueError(
            "Jam reference replay supports jam_reversal_spot_v1 v1.0.1"
        )
    required = KNOWN_STRATEGY_REQUIRED_PARAMETERS["jam_reversal_spot_v1"]
    missing = [key for key in required if key not in request.parameters]
    if missing:
        raise ValueError(
            f"Jam reference replay parameters missing: {', '.join(missing)}"
        )

    lab = OhlcvDatasetLab(session)
    dataset = lab.get_dataset(request.dataset_id)
    if dataset is None:
        raise LookupError("OHLCV dataset not found")
    audit = lab.audit(dataset)
    if audit.status != "PASS":
        raise ValueError(
            f"OHLCV dataset integrity audit blocked: {', '.join(audit.reasons)}"
        )
    supported_continuity = {
        "continuous_24_7",
        "continuous_24_7_with_documented_outages",
    }
    if dataset.continuity not in supported_continuity:
        raise ValueError(
            "Jam reference replay requires continuous 24/7 data, with any outages "
            "fully documented"
        )
    documented_outage_count = 0
    if dataset.continuity == "continuous_24_7_with_documented_outages":
        coverage_reasons = documented_outage_coverage_reasons(
            dataset.quality_snapshot
        )
        if coverage_reasons:
            raise ValueError(
                "Jam reference replay documented-outage coverage is invalid: "
                + ", ".join(coverage_reasons)
            )
        documented_outage_count = int(
            dataset.quality_snapshot["documented_gap_count"]
        )

    candles = [
        OhlcvCandle(
            timestamp=ensure_utc(row.timestamp),
            open=Decimal(row.open),
            high=Decimal(row.high),
            low=Decimal(row.low),
            close=Decimal(row.close),
            volume=Decimal(row.volume),
        )
        for row in sorted(dataset.candles, key=lambda item: item.sequence)
    ]
    parameters = parse_jam_reversal_spot_parameters(request.parameters)
    base_timeframe, base_seconds = normalize_timeframe(dataset.timeframe)
    higher_timeframe, higher_seconds = normalize_timeframe(
        parameters["higher_timeframe"]
    )
    if base_timeframe != "15m" or base_timeframe != dataset.timeframe:
        raise ValueError("jam_reversal_spot_v1 requires a canonical 15m dataset")
    if higher_seconds <= base_seconds or higher_seconds % base_seconds:
        raise ValueError(
            "Higher timeframe must be an integer multiple above dataset timeframe"
        )

    start = parameters["backtest_start"]
    end = parameters["backtest_end"]
    reasons: list[str] = []
    if start >= end:
        reasons.append("backtest_start_must_precede_backtest_end")
    dataset_end = (
        candles[-1].timestamp + timedelta(seconds=base_seconds)
        if candles
        else None
    )
    if not candles or start < candles[0].timestamp or end > dataset_end:
        reasons.append("backtest_window_must_be_contained_in_dataset")

    closes = [candle.close for candle in candles]
    volumes: list[Decimal | None] = [candle.volume for candle in candles]
    trend_ema = ema_series(closes, parameters["trend_ema"])
    pullback_ema = ema_series(closes, parameters["pullback_ema"])
    atr = atr_series(candles, parameters["atr_length"])
    volume_average = simple_moving_average_series(
        volumes,
        parameters["volume_length"],
    )
    dmi_plus, dmi_minus, adx = dmi_series(
        candles,
        parameters["adx_length"],
        parameters["adx_smoothing"],
    )
    htf = higher_timeframe_ema_series(
        candles,
        base_seconds=base_seconds,
        higher_seconds=higher_seconds,
        fast_length=parameters["htf_ema_fast"],
        slow_length=parameters["htf_ema_slow"],
    )

    first_window_index = next(
        (
            index
            for index, candle in enumerate(candles)
            if candle.timestamp >= start
        ),
        None,
    )
    required_base_history = max(
        parameters["trend_ema"],
        parameters["pullback_ema"],
        parameters["atr_length"] + 1,
        parameters["adx_length"] + parameters["adx_smoothing"],
        parameters["volume_length"],
        parameters["impulse_lookback"] + 1,
    )
    required_higher_history = max(
        parameters["htf_ema_fast"],
        parameters["htf_ema_slow"],
    )
    available_higher_history = (
        complete_higher_timeframe_count(
            candles,
            base_seconds=base_seconds,
            higher_seconds=higher_seconds,
            through=candles[first_window_index].timestamp,
        )
        if first_window_index is not None
        else 0
    )
    if first_window_index is None:
        reasons.append("backtest_window_has_no_candles")
    elif (
        first_window_index + 1 < required_base_history
        or available_higher_history < required_higher_history
        or not jam_indicators_ready(
            first_window_index,
            atr=atr,
            volume_average=volume_average,
            dmi_plus=dmi_plus,
            dmi_minus=dmi_minus,
            adx=adx,
            htf=htf,
        )
    ):
        reasons.append("insufficient_pre_window_indicator_warmup")

    assumptions = {
        "engine_version": JAM_REVERSAL_SPOT_ENGINE_VERSION,
        "dataset_timeframe": base_timeframe,
        "higher_timeframe": higher_timeframe,
        "higher_timeframe_merge": (
            "previous_confirmed_bar_offset_1_lookahead_on_emulation"
        ),
        "higher_timeframe_alignment": "UTC_epoch_boundaries",
        "direction": "LONG_ONLY_SPOT",
        "entry_fill": "signal_bar_close_plus_directional_tick_slippage",
        "stop_fill": "trigger_or_gap_price_plus_adverse_tick_slippage",
        "limit_fill": "declared_take_profit_without_positive_gap_improvement",
        "close_exit_fill": "signal_bar_close_plus_adverse_tick_slippage",
        "dynamic_stop_activation": "next_bar_after_close_update",
        "intrabar_policy": request.intrabar_policy,
        "commission_percent_per_side": decimal_string(
            request.commission_percent
        ),
        "slippage_ticks": request.slippage_ticks,
        "tick_size": decimal_string(request.tick_size),
        "point_value": decimal_string(request.point_value),
        "minimum_contract": decimal_string(request.minimum_contract),
        "bar_magnifier": False,
        "pyramiding": 0,
    }
    warnings = [
        "Reference replay is comparison-only until trade-level TradingView parity passes.",
        "Same-bar stop and target touches resolve stop-first because intrabar order is unknown.",
        "Historical OHLCV cannot reproduce order-book spread, queue position, or latency.",
        "The parent Jam v1.14.0 2026 results remain quarantined and are not acceptance evidence.",
    ]
    if documented_outage_count:
        assumptions["dataset_continuity"] = dataset.continuity
        assumptions["documented_outage_gap_count"] = documented_outage_count
        warnings.append(
            f"Dataset preserves {documented_outage_count} checksum-backed, documented "
            "exchange outage gap(s); no synthetic candles were inserted."
        )
    diagnostics = jam_diagnostic_template(len(candles), start, end)
    diagnostics["warmup"] = {
        "base_candles_available_at_start": (
            first_window_index + 1 if first_window_index is not None else 0
        ),
        "base_candles_required": required_base_history,
        "higher_candles_available_at_start": available_higher_history,
        "higher_candles_required": required_higher_history,
    }
    if reasons:
        return replay_response(
            request=request,
            dataset_hash=dataset.evidence_hash,
            status="BLOCKED",
            reasons=reasons,
            warnings=warnings,
            assumptions=assumptions,
            diagnostics=diagnostics,
            trades=[],
            open_position=None,
            engine_version=JAM_REVERSAL_SPOT_ENGINE_VERSION,
        )

    equity = parameters["initial_capital"]
    pending: PendingLongJam | None = None
    position: JamOpenPosition | None = None
    trades: list[ReferenceReplayTrade] = []
    last_entry_index: int | None = None
    adaptive_confirm_window = (
        10
        if parameters["use_timeframe_adaptive_confirmation"]
        else parameters["confirm_window_bars"]
    )
    adaptive_max_confirm_distance = (
        Decimal("1.25")
        if parameters["use_timeframe_adaptive_confirmation"]
        else parameters["max_confirm_distance_atr"]
    )
    adaptive_min_confirm_close = (
        Decimal("0.85")
        if parameters["use_timeframe_adaptive_confirmation"]
        else parameters["min_confirm_close_position"]
    )
    adaptive_volume_expansion = (
        Decimal("1.15")
        if parameters["use_timeframe_adaptive_confirmation"]
        else parameters["volume_expansion"]
    )

    for index, candle in enumerate(candles):
        candle_close = candle.timestamp + timedelta(seconds=base_seconds)
        in_window = start <= candle.timestamp < end
        entry_window = in_window and candle_close < end
        backtest_exit_bar = candle.timestamp < end <= candle_close
        if in_window:
            diagnostics["bars_in_window"] += 1

        if position is not None and index > position.entry_index:
            fill = resolve_jam_bracket_exit(
                candle,
                position,
                tick_size=request.tick_size,
                slippage_ticks=request.slippage_ticks,
            )
            if fill is not None:
                trade = close_jam_position(
                    sequence=len(trades) + 1,
                    position=position,
                    fill=fill,
                    closed_at=candle.timestamp,
                    commission_percent=request.commission_percent,
                    equity=equity,
                )
                equity = trade.equity
                trades.append(trade)
                record_exit(diagnostics, trade)
                position = None

        flat_position = position is None
        cooldown_ok = (
            parameters["trade_cooldown_bars"] == 0
            or last_entry_index is None
            or index - last_entry_index >= parameters["trade_cooldown_bars"]
        )
        if in_window and flat_position:
            diagnostics["flat_position_pass"] += 1

        if pending is not None:
            pending_expired = (
                index - pending.armed_index > adaptive_confirm_window
            )
            pending_midpoint_failed = (
                parameters["cancel_pending_on_midpoint_failure"]
                and candle.close < pending.failure_level
            )
            if (
                pending_expired
                or pending_midpoint_failed
                or not entry_window
                or not flat_position
            ):
                diagnostics["pending_cancellations"] += 1
                if pending_expired:
                    diagnostics["pending_expirations"] += 1
                if pending_midpoint_failed:
                    diagnostics["pending_midpoint_failures"] += 1
                pending = None

        current_atr = atr[index]
        current_volume_average = volume_average[index]
        current_dmi_plus = dmi_plus[index]
        current_dmi_minus = dmi_minus[index]
        current_adx = adx[index]
        htf_fast, htf_slow = htf[index]
        indicators_ready = all(
            value is not None
            for value in (
                current_atr,
                current_volume_average,
                current_dmi_plus,
                current_dmi_minus,
                current_adx,
                htf_fast,
                htf_slow,
            )
        )
        if not indicators_ready or index == 0:
            continue
        assert current_atr is not None
        assert current_volume_average is not None
        assert current_dmi_plus is not None
        assert current_dmi_minus is not None
        assert current_adx is not None
        assert htf_fast is not None
        assert htf_slow is not None

        pattern = long_jam_pattern(
            candles,
            index,
            current_atr=current_atr,
            previous_atr=atr[index - 1],
            tick_size=request.tick_size,
            slippage_ticks=request.slippage_ticks,
            parameters=parameters,
        )
        if pattern is not None:
            diagnostics["long_patterns"] += 1

        local_start = max(0, index - parameters["impulse_lookback"])
        previous_closes = [
            item.close for item in candles[local_start:index]
        ]
        previous_lows = [item.low for item in candles[local_start:index]]
        long_local_reversal = bool(previous_closes) and (
            candles[index - 1].close <= min(previous_closes)
            or candles[index - 1].low <= min(previous_lows)
        )
        long_htf_bias = (
            not parameters["use_higher_timeframe_bias"]
            or htf_fast >= htf_slow
        )
        long_trend_bias = (
            not parameters["use_current_trend_filter"]
            or candle.close >= trend_ema[index]
        )
        long_pullback_context = (
            candles[index - 1].close <= pullback_ema[index - 1]
            or candle.low <= pullback_ema[index]
        )
        context_mode = parameters["context_mode"]
        if context_mode == "None":
            long_context_base = True
        elif context_mode == "HTF trend":
            long_context_base = long_htf_bias and long_pullback_context
        elif context_mode == "Local reversal":
            long_context_base = long_local_reversal
        else:
            long_context_base = (
                long_htf_bias and long_pullback_context
            ) or long_local_reversal
        long_strong_counter_trend = (
            parameters["block_strong_counter_trend"]
            and candle.close < trend_ema[index]
            and htf_fast < htf_slow
            and current_dmi_minus > current_dmi_plus
            and current_adx >= parameters["counter_trend_adx"]
        )
        long_context_ok = (
            long_context_base
            and long_trend_bias
            and not long_strong_counter_trend
        )
        if long_context_ok:
            diagnostics["long_context_pass"] += 1
        volume_ok = (
            not parameters["use_volume_filter"]
            or (
                current_volume_average > 0
                and candle.volume
                >= current_volume_average * adaptive_volume_expansion
            )
        )
        if volume_ok:
            diagnostics["volume_pass"] += 1

        confirm_signal = False
        if pending is not None and index > pending.armed_index:
            confirm_range = max(
                candle.high - candle.low,
                request.tick_size,
            )
            confirm_signal = (
                index - pending.armed_index <= adaptive_confirm_window
                and candle.close
                > pending.trigger
                + current_atr * parameters["confirm_atr_buffer"]
                and candle.close > candle.open
                and candle.close
                <= pending.trigger
                + current_atr * adaptive_max_confirm_distance
                and confirm_range
                <= current_atr * parameters["max_confirm_range_atr"]
                and (candle.close - candle.low) / confirm_range
                >= adaptive_min_confirm_close
            )
            if confirm_signal:
                diagnostics["long_confirmations"] += 1

        expected_entry = (
            candle.close + request.tick_size * request.slippage_ticks
        )
        trade_stop = (
            pending.stop_loss
            if confirm_signal and pending is not None
            else pattern.stop_loss
            if pattern is not None
            else ZERO
        )
        failure_level = (
            pending.failure_level
            if confirm_signal and pending is not None
            else pattern.failure_level
            if pattern is not None
            else ZERO
        )
        risk = expected_entry - trade_stop
        take_profit, target_distance_ok = jam_take_profit(
            entry=expected_entry,
            stop_loss=trade_stop,
            atr=current_atr,
            tick_size=request.tick_size,
            parameters=parameters,
        )
        quantity = jam_quantity(
            equity=equity,
            entry=expected_entry,
            risk=risk,
            point_value=request.point_value,
            minimum_contract=request.minimum_contract,
            parameters=parameters,
        )
        risk_ok = (
            risk > request.tick_size
            and take_profit > expected_entry
            and target_distance_ok
        )
        if risk_ok:
            diagnostics["long_risk_pass"] += 1
        if quantity > 0:
            diagnostics["long_quantity_pass"] += 1

        long_setup = (
            parameters["enable_long"]
            and parameters["direction_mode"] == "Long only"
            and flat_position
            and entry_window
            and cooldown_ok
            and confirm_signal
            and risk_ok
            and quantity > 0
        )
        if long_setup:
            entry_fee = (
                expected_entry
                * quantity
                * request.point_value
                * request.commission_percent
                / ONE_HUNDRED
            )
            position = JamOpenPosition(
                direction=Direction.LONG,
                entry_index=index,
                entry_at=candle.timestamp,
                signal_price=candle.close,
                entry_price=expected_entry,
                initial_stop_loss=trade_stop,
                stop_loss=trade_stop,
                take_profit=take_profit,
                quantity=quantity,
                entry_fee=entry_fee,
                entry_slippage=(
                    abs(expected_entry - candle.close)
                    * quantity
                    * request.point_value
                ),
                initial_risk_per_unit=risk,
                initial_risk=risk * quantity * request.point_value,
                point_value=request.point_value,
                market_regime="BREAKOUT_EXPANSION",
                failure_level=failure_level,
                best_price=candle.high,
            )
            last_entry_index = index
            pending = None
            diagnostics["long_setups"] += 1
            diagnostics["orders_submitted"] += 1
            continue

        can_arm = (
            flat_position
            and entry_window
            and cooldown_ok
            and pending is None
            and pattern is not None
        )
        if can_arm and long_context_ok and volume_ok:
            arm_risk = expected_entry - pattern.stop_loss
            arm_take_profit, arm_target_ok = jam_take_profit(
                entry=expected_entry,
                stop_loss=pattern.stop_loss,
                atr=current_atr,
                tick_size=request.tick_size,
                parameters=parameters,
            )
            arm_quantity = jam_quantity(
                equity=equity,
                entry=expected_entry,
                risk=arm_risk,
                point_value=request.point_value,
                minimum_contract=request.minimum_contract,
                parameters=parameters,
            )
            arm_risk_ok = (
                arm_risk > request.tick_size
                and arm_take_profit > expected_entry
                and arm_target_ok
            )
            if arm_risk_ok and arm_quantity > 0:
                pending = PendingLongJam(
                    armed_index=index,
                    trigger=pattern.trigger,
                    stop_loss=pattern.stop_loss,
                    failure_level=pattern.failure_level,
                )
                diagnostics["long_armed"] += 1

        if position is not None and index > position.entry_index:
            position.best_price = max(position.best_price, candle.high)
            managed_stop = position.stop_loss
            if (
                parameters["use_breakeven_stop"]
                and position.best_price
                >= position.entry_price
                + position.initial_risk_per_unit
                * parameters["breakeven_at_r"]
            ):
                managed_stop = max(
                    managed_stop,
                    position.entry_price
                    + request.tick_size
                    * parameters["breakeven_offset_ticks"],
                )
            if (
                parameters["use_atr_trail"]
                and position.best_price
                >= position.entry_price
                + position.initial_risk_per_unit
                * parameters["trail_start_r"]
            ):
                managed_stop = max(
                    managed_stop,
                    position.best_price
                    - current_atr * parameters["trail_atr_multiplier"],
                )
            position.stop_loss = managed_stop

            exit_reason: str | None = None
            if (
                parameters["use_midpoint_failure_exit"]
                and candle.close < position.failure_level
            ):
                exit_reason = "MIDPOINT_FAILURE"
            elif (
                parameters["use_pullback_failure_exit"]
                and candle.close < pullback_ema[index]
                and candle.close < position.entry_price
            ):
                exit_reason = "PULLBACK_FAILURE"
            elif (
                index - position.entry_index
                >= parameters["max_bars_in_trade"]
            ):
                exit_reason = "TIME_EXIT"
            elif backtest_exit_bar:
                exit_reason = "BACKTEST_WINDOW_END"

            if exit_reason is not None:
                fill = jam_market_exit(
                    candle.close,
                    tick_size=request.tick_size,
                    slippage_ticks=request.slippage_ticks,
                    reason=exit_reason,
                    quantity=position.quantity,
                    point_value=position.point_value,
                )
                trade = close_jam_position(
                    sequence=len(trades) + 1,
                    position=position,
                    fill=fill,
                    closed_at=candle.timestamp,
                    commission_percent=request.commission_percent,
                    equity=equity,
                )
                equity = trade.equity
                trades.append(trade)
                record_exit(diagnostics, trade)
                position = None

    if position is not None:
        warnings.append(
            "One position remains open because no post-window candle closed it."
        )
    return replay_response(
        request=request,
        dataset_hash=dataset.evidence_hash,
        status="READY",
        reasons=[],
        warnings=warnings,
        assumptions=assumptions,
        diagnostics=diagnostics,
        trades=trades,
        open_position=jam_position_snapshot(position),
        engine_version=JAM_REVERSAL_SPOT_ENGINE_VERSION,
    )


@dataclass(frozen=True)
class LongJamPattern:
    trigger: Decimal
    stop_loss: Decimal
    failure_level: Decimal


def long_jam_pattern(
    candles: list[OhlcvCandle],
    index: int,
    *,
    current_atr: Decimal,
    previous_atr: Decimal | None,
    tick_size: Decimal,
    slippage_ticks: int,
    parameters: dict,
) -> LongJamPattern | None:
    if index == 0 or previous_atr is None:
        return None
    seed = candles[index - 1]
    jam = candles[index]
    seed_range = max(seed.high - seed.low, tick_size)
    seed_body = abs(seed.close - seed.open)
    jam_range = max(jam.high - jam.low, tick_size)
    jam_body = abs(jam.close - jam.open)
    seed_quality = (
        seed_body / seed_range >= parameters["min_seed_body_ratio"]
        and seed_range >= previous_atr * parameters["min_seed_range_atr"]
    )
    jam_quality = (
        jam_range >= current_atr * parameters["min_jam_range_atr"]
        and jam_range <= current_atr * parameters["max_jam_range_atr"]
        and jam_body / jam_range >= parameters["min_jam_body_ratio"]
        and jam_body >= seed_body * parameters["min_jam_body_expansion"]
    )
    reclaim_level = (
        seed.high if parameters["reclaim_mode"] == "Wick" else seed.open
    )
    reclaim = (
        jam.close
        > reclaim_level + current_atr * parameters["reclaim_atr_buffer"]
    )
    sweep = (
        not parameters["require_sweep"]
        or jam.low
        <= seed.low - current_atr * parameters["sweep_atr_buffer"]
    )
    if not (
        seed.close < seed.open
        and jam.close > jam.open
        and seed_quality
        and jam_quality
        and reclaim
        and sweep
    ):
        return None
    pattern_high = max(seed.high, jam.high)
    pattern_low = min(seed.low, jam.low)
    pattern_stop = (
        pattern_low - current_atr * parameters["stop_atr_buffer"]
    )
    expected_entry = jam.close + tick_size * slippage_ticks
    atr_stop = (
        expected_entry - current_atr * parameters["atr_stop_multiplier"]
    )
    stop_mode = parameters["stop_mode"]
    if stop_mode == "Pattern":
        stop_loss = pattern_stop
    elif stop_mode == "ATR":
        stop_loss = atr_stop
    elif stop_mode == "Wider":
        stop_loss = min(pattern_stop, atr_stop)
    else:
        stop_loss = max(pattern_stop, atr_stop)
    return LongJamPattern(
        trigger=pattern_high,
        stop_loss=stop_loss,
        failure_level=(pattern_high + pattern_low) / Decimal("2"),
    )


def jam_take_profit(
    *,
    entry: Decimal,
    stop_loss: Decimal,
    atr: Decimal,
    tick_size: Decimal,
    parameters: dict,
) -> tuple[Decimal, bool]:
    risk = entry - stop_loss
    fixed = entry + risk * parameters["reward_risk"]
    capped = entry + atr * parameters["max_target_atr"]
    take_profit = (
        fixed
        if parameters["target_mode"] == "Fixed R"
        else min(fixed, capped)
    )
    target_distance = take_profit - entry
    estimated_cost = (
        entry
        * parameters["estimated_commission_percent"]
        * Decimal("2")
        / ONE_HUNDRED
        + tick_size * Decimal("4")
    )
    net_risk = risk + estimated_cost
    net_reward_risk = (
        (target_distance - estimated_cost) / net_risk
        if net_risk > tick_size
        else ZERO
    )
    target_ok = (
        not parameters["use_cost_aware_filter"]
        or (
            target_distance
            >= atr * parameters["min_target_distance_atr"]
            and net_reward_risk >= parameters["min_net_reward_risk"]
        )
    )
    return take_profit, target_ok


def jam_quantity(
    *,
    equity: Decimal,
    entry: Decimal,
    risk: Decimal,
    point_value: Decimal,
    minimum_contract: Decimal,
    parameters: dict,
) -> Decimal:
    if entry <= 0 or risk <= 0:
        return ZERO
    risk_capital = (
        max(equity, ZERO)
        * parameters["risk_per_trade_percent"]
        / ONE_HUNDRED
    )
    risk_quantity = risk_capital / (risk * point_value)
    max_quantity = (
        max(equity, ZERO)
        * parameters["max_position_value_percent"]
        / ONE_HUNDRED
        / (entry * point_value)
    )
    raw_quantity = min(risk_quantity, max_quantity)
    return (
        raw_quantity / minimum_contract
    ).to_integral_value(rounding=ROUND_FLOOR) * minimum_contract


@dataclass(frozen=True)
class JamExitFill:
    price: Decimal
    reason: str
    slippage: Decimal
    intrabar_ambiguous: bool = False


def resolve_jam_bracket_exit(
    candle: OhlcvCandle,
    position: JamOpenPosition,
    *,
    tick_size: Decimal,
    slippage_ticks: int,
) -> JamExitFill | None:
    if candle.open <= position.stop_loss:
        return jam_adverse_stop_fill(
            candle.open,
            position,
            tick_size,
            slippage_ticks,
            "STOP_GAP",
        )
    if candle.open >= position.take_profit:
        return JamExitFill(position.take_profit, "TAKE_PROFIT_GAP", ZERO)
    stop_touched = candle.low <= position.stop_loss
    target_touched = candle.high >= position.take_profit
    if stop_touched:
        reason = (
            "STOP_AND_TARGET_AMBIGUOUS"
            if target_touched
            else "STOP_LOSS"
        )
        fill = jam_adverse_stop_fill(
            position.stop_loss,
            position,
            tick_size,
            slippage_ticks,
            reason,
        )
        return JamExitFill(
            fill.price,
            fill.reason,
            fill.slippage,
            target_touched,
        )
    if target_touched:
        return JamExitFill(position.take_profit, "TAKE_PROFIT", ZERO)
    return None


def jam_adverse_stop_fill(
    trigger_price: Decimal,
    position: JamOpenPosition,
    tick_size: Decimal,
    slippage_ticks: int,
    reason: str,
) -> JamExitFill:
    slip = tick_size * slippage_ticks
    return JamExitFill(
        trigger_price - slip,
        reason,
        slip * position.quantity * position.point_value,
    )


def jam_market_exit(
    price: Decimal,
    *,
    tick_size: Decimal,
    slippage_ticks: int,
    reason: str,
    quantity: Decimal,
    point_value: Decimal,
) -> JamExitFill:
    slip = tick_size * slippage_ticks
    return JamExitFill(
        price - slip,
        reason,
        slip * quantity * point_value,
    )


def close_jam_position(
    *,
    sequence: int,
    position: JamOpenPosition,
    fill: JamExitFill,
    closed_at: datetime,
    commission_percent: Decimal,
    equity: Decimal,
) -> ReferenceReplayTrade:
    gross = (
        fill.price - position.entry_price
    ) * position.quantity * position.point_value
    exit_fee = (
        fill.price
        * position.quantity
        * position.point_value
        * commission_percent
        / ONE_HUNDRED
    )
    fees = position.entry_fee + exit_fee
    realized = gross - fees
    next_equity = equity + realized
    r_multiple = (
        realized / position.initial_risk
        if position.initial_risk > 0
        else ZERO
    )
    return ReferenceReplayTrade(
        sequence=sequence,
        direction=position.direction,
        entry_at=position.entry_at,
        closed_at=closed_at,
        signal_price=position.signal_price,
        entry_price=position.entry_price,
        stop_loss=position.initial_stop_loss,
        take_profit=position.take_profit,
        exit_price=fill.price,
        quantity=position.quantity,
        gross_pl=gross,
        fees=fees,
        slippage=position.entry_slippage + fill.slippage,
        realized_pl=realized,
        equity=next_equity,
        r_multiple=r_multiple,
        market_regime=position.market_regime,
        exit_reason=fill.reason,
        intrabar_ambiguous=fill.intrabar_ambiguous,
    )


def record_exit(diagnostics: dict, trade: ReferenceReplayTrade) -> None:
    diagnostics["exit_reasons"][trade.exit_reason] = (
        diagnostics["exit_reasons"].get(trade.exit_reason, 0) + 1
    )
    if trade.intrabar_ambiguous:
        diagnostics["intrabar_ambiguous_exits"] += 1


def dmi_series(
    candles: list[OhlcvCandle],
    length: int,
    smoothing: int,
) -> tuple[
    list[Decimal | None],
    list[Decimal | None],
    list[Decimal | None],
]:
    true_ranges: list[Decimal | None] = []
    plus_dm: list[Decimal | None] = []
    minus_dm: list[Decimal | None] = []
    for index, candle in enumerate(candles):
        if index == 0:
            true_ranges.append(candle.high - candle.low)
            plus_dm.append(ZERO)
            minus_dm.append(ZERO)
            continue
        previous = candles[index - 1]
        up = candle.high - previous.high
        down = previous.low - candle.low
        plus_dm.append(up if up > down and up > 0 else ZERO)
        minus_dm.append(down if down > up and down > 0 else ZERO)
        true_ranges.append(
            max(
                candle.high - candle.low,
                abs(candle.high - previous.close),
                abs(candle.low - previous.close),
            )
        )
    smoothed_tr = rma_series(true_ranges, length)
    smoothed_plus = rma_series(plus_dm, length)
    smoothed_minus = rma_series(minus_dm, length)
    plus: list[Decimal | None] = [None] * len(candles)
    minus: list[Decimal | None] = [None] * len(candles)
    dx: list[Decimal | None] = [None] * len(candles)
    for index in range(len(candles)):
        current_tr = smoothed_tr[index]
        current_plus = smoothed_plus[index]
        current_minus = smoothed_minus[index]
        if (
            current_tr is None
            or current_plus is None
            or current_minus is None
            or current_tr == 0
        ):
            continue
        plus[index] = ONE_HUNDRED * current_plus / current_tr
        minus[index] = ONE_HUNDRED * current_minus / current_tr
        total = plus[index] + minus[index]
        dx[index] = (
            ONE_HUNDRED * abs(plus[index] - minus[index]) / total
            if total > 0
            else ZERO
        )
    return plus, minus, rma_series(dx, smoothing)


def rma_series(
    values: list[Decimal | None],
    length: int,
) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * len(values)
    seed: list[Decimal] = []
    average: Decimal | None = None
    for index, value in enumerate(values):
        if value is None:
            continue
        if average is None:
            seed.append(value)
            if len(seed) == length:
                average = sum(seed, ZERO) / Decimal(length)
                result[index] = average
            continue
        average = (average * (length - 1) + value) / Decimal(length)
        result[index] = average
    return result


def jam_indicators_ready(
    index: int,
    *,
    atr: list[Decimal | None],
    volume_average: list[Decimal | None],
    dmi_plus: list[Decimal | None],
    dmi_minus: list[Decimal | None],
    adx: list[Decimal | None],
    htf: list[tuple[Decimal | None, Decimal | None]],
) -> bool:
    htf_fast, htf_slow = htf[index]
    return all(
        value is not None
        for value in (
            atr[index],
            volume_average[index],
            dmi_plus[index],
            dmi_minus[index],
            adx[index],
            htf_fast,
            htf_slow,
        )
    )


def jam_diagnostic_template(
    candle_count: int,
    start: datetime,
    end: datetime,
) -> dict:
    return {
        "candles_loaded": candle_count,
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "bars_in_window": 0,
        "flat_position_pass": 0,
        "long_patterns": 0,
        "long_context_pass": 0,
        "volume_pass": 0,
        "long_risk_pass": 0,
        "long_quantity_pass": 0,
        "long_armed": 0,
        "long_confirmations": 0,
        "long_setups": 0,
        "orders_submitted": 0,
        "pending_cancellations": 0,
        "pending_expirations": 0,
        "pending_midpoint_failures": 0,
        "intrabar_ambiguous_exits": 0,
        "exit_reasons": {},
    }


def jam_position_snapshot(position: JamOpenPosition | None) -> dict | None:
    if position is None:
        return None
    return {
        "direction": position.direction.value,
        "entry_at": position.entry_at.isoformat(),
        "entry_price": decimal_string(position.entry_price),
        "initial_stop_loss": decimal_string(position.initial_stop_loss),
        "managed_stop_loss": decimal_string(position.stop_loss),
        "take_profit": decimal_string(position.take_profit),
        "quantity": decimal_string(position.quantity),
    }


def parse_jam_reversal_spot_parameters(parameters: dict) -> dict:
    def integer(key: str, *, minimum: int = 1) -> int:
        value = int(parameters[key])
        if value < minimum:
            raise ValueError(f"{key} must be at least {minimum}")
        return value

    def decimal(
        key: str,
        *,
        minimum: Decimal = Decimal("0"),
        positive: bool = False,
    ) -> Decimal:
        value = Decimal(str(parameters[key]))
        if not value.is_finite():
            raise ValueError(f"{key} must be finite")
        if positive and value <= 0:
            raise ValueError(f"{key} must be positive")
        if value < minimum:
            raise ValueError(f"{key} must be at least {minimum}")
        return value

    def boolean(key: str) -> bool:
        value = parameters[key]
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
        raise ValueError(f"{key} must be true or false")

    parsed = {
        "initial_capital": decimal("initial_capital", positive=True),
        "backtest_start": parse_timestamp(parameters["backtest_start"]),
        "backtest_end": parse_timestamp(parameters["backtest_end"]),
        "direction_mode": str(parameters["direction_mode"]),
        "higher_timeframe": str(parameters["higher_timeframe"]),
        "higher_timeframe_valid": boolean("higher_timeframe_valid"),
        "htf_ema_fast": integer("htf_ema_fast"),
        "htf_ema_slow": integer("htf_ema_slow"),
        "trend_ema": integer("trend_ema"),
        "pullback_ema": integer("pullback_ema"),
        "use_higher_timeframe_bias": boolean("use_higher_timeframe_bias"),
        "use_current_trend_filter": boolean("use_current_trend_filter"),
        "context_mode": str(parameters["context_mode"]),
        "impulse_lookback": integer("impulse_lookback", minimum=2),
        "block_strong_counter_trend": boolean(
            "block_strong_counter_trend"
        ),
        "counter_trend_adx": decimal("counter_trend_adx", positive=True),
        "atr_length": integer("atr_length"),
        "adx_length": integer("adx_length"),
        "adx_smoothing": integer("adx_smoothing"),
        "reclaim_mode": str(parameters["reclaim_mode"]),
        "require_sweep": boolean("require_sweep"),
        "entry_style": str(parameters["entry_style"]),
        "confirm_window_bars": integer("confirm_window_bars"),
        "confirm_atr_buffer": decimal("confirm_atr_buffer"),
        "max_confirm_distance_atr": decimal(
            "max_confirm_distance_atr",
            positive=True,
        ),
        "max_confirm_range_atr": decimal(
            "max_confirm_range_atr",
            positive=True,
        ),
        "min_confirm_close_position": decimal(
            "min_confirm_close_position",
            positive=True,
        ),
        "cancel_pending_on_midpoint_failure": boolean(
            "cancel_pending_on_midpoint_failure"
        ),
        "sweep_atr_buffer": decimal("sweep_atr_buffer"),
        "reclaim_atr_buffer": decimal("reclaim_atr_buffer"),
        "min_seed_body_ratio": decimal("min_seed_body_ratio", positive=True),
        "min_jam_body_ratio": decimal("min_jam_body_ratio", positive=True),
        "min_jam_body_expansion": decimal(
            "min_jam_body_expansion",
            positive=True,
        ),
        "min_seed_range_atr": decimal("min_seed_range_atr"),
        "min_jam_range_atr": decimal("min_jam_range_atr"),
        "max_jam_range_atr": decimal("max_jam_range_atr", positive=True),
        "use_volume_filter": boolean("use_volume_filter"),
        "volume_length": integer("volume_length"),
        "volume_expansion": decimal("volume_expansion", positive=True),
        "use_timeframe_adaptive_confirmation": boolean(
            "use_timeframe_adaptive_confirmation"
        ),
        "stop_mode": str(parameters["stop_mode"]),
        "stop_atr_buffer": decimal("stop_atr_buffer"),
        "atr_stop_multiplier": decimal(
            "atr_stop_multiplier",
            positive=True,
        ),
        "target_mode": str(parameters["target_mode"]),
        "reward_risk": decimal("reward_risk", positive=True),
        "max_target_atr": decimal("max_target_atr", positive=True),
        "use_cost_aware_filter": boolean("use_cost_aware_filter"),
        "estimated_commission_percent": decimal(
            "estimated_commission_percent"
        ),
        "min_target_distance_atr": decimal(
            "min_target_distance_atr",
            positive=True,
        ),
        "min_net_reward_risk": decimal(
            "min_net_reward_risk",
            positive=True,
        ),
        "use_breakeven_stop": boolean("use_breakeven_stop"),
        "breakeven_at_r": decimal("breakeven_at_r", positive=True),
        "breakeven_offset_ticks": integer(
            "breakeven_offset_ticks",
            minimum=0,
        ),
        "use_atr_trail": boolean("use_atr_trail"),
        "trail_start_r": decimal("trail_start_r", positive=True),
        "trail_atr_multiplier": decimal(
            "trail_atr_multiplier",
            positive=True,
        ),
        "use_midpoint_failure_exit": boolean(
            "use_midpoint_failure_exit"
        ),
        "use_pullback_failure_exit": boolean(
            "use_pullback_failure_exit"
        ),
        "max_bars_in_trade": integer("max_bars_in_trade"),
        "risk_per_trade_percent": decimal(
            "risk_per_trade_percent",
            positive=True,
        ),
        "max_position_value_percent": decimal(
            "max_position_value_percent",
            positive=True,
        ),
        "trade_cooldown_bars": integer(
            "trade_cooldown_bars",
            minimum=0,
        ),
        "allowed_symbol_mode": str(parameters["allowed_symbol_mode"]),
        "allowed_timeframe_mode": str(parameters["allowed_timeframe_mode"]),
        "enable_long": boolean("enable_long"),
        "enable_short": boolean("enable_short"),
    }
    expected_exact = {
        "direction_mode": "Long only",
        "higher_timeframe_valid": True,
        "entry_style": "Breakout confirm",
        "allowed_symbol_mode": "BTCUSDT only",
        "allowed_timeframe_mode": "15m only",
        "enable_long": True,
        "enable_short": False,
    }
    mismatches = [
        key
        for key, expected in expected_exact.items()
        if parsed[key] != expected
    ]
    if mismatches:
        raise ValueError(
            "jam_reversal_spot_v1 frozen spot contract mismatch: "
            + ", ".join(mismatches)
        )
    if parsed["context_mode"] not in {
        "Hybrid",
        "HTF trend",
        "Local reversal",
        "None",
    }:
        raise ValueError("context_mode is invalid")
    if parsed["reclaim_mode"] not in {"Body", "Wick"}:
        raise ValueError("reclaim_mode is invalid")
    if parsed["stop_mode"] not in {"Pattern", "ATR", "Wider", "Tighter"}:
        raise ValueError("stop_mode is invalid")
    if parsed["target_mode"] not in {"ATR capped R", "Fixed R"}:
        raise ValueError("target_mode is invalid")
    if not Decimal("0.1") <= parsed["risk_per_trade_percent"] <= Decimal("2"):
        raise ValueError("risk_per_trade_percent must be between 0.1 and 2")
    if not Decimal("1") <= parsed["max_position_value_percent"] <= Decimal(
        "100"
    ):
        raise ValueError(
            "max_position_value_percent must be between 1 and 100"
        )
    return parsed


def parse_timestamp(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return ensure_utc(parsed)


def decimal_string(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")
