import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_FLOOR, Decimal
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from aurex.backtest_engine.datasets import OhlcvDatasetLab, ensure_utc, normalize_timeframe
from aurex.backtest_engine.schemas import (
    BacktestTradeInput,
    OhlcvCandle,
    ReferenceReplayAuditResponse,
    ReferenceReplayRequest,
    ReferenceReplayResponse,
    ReferenceReplaySummaryResponse,
    ReferenceReplayTrade,
)
from aurex.backtest_engine.service import (
    KNOWN_STRATEGY_REQUIRED_PARAMETERS,
    calculate_backtest_metrics,
)
from aurex.db.base import utc_now
from aurex.db.models import BacktestReferenceReplayRun
from aurex.domain.enums import Direction
from aurex.observability.system_events import SystemEventRecorder

ENGINE_VERSION = "trend-pullback-reference-v1.1.0"
VOLATILITY_BREAKOUT_ENGINE_VERSION = "volatility-breakout-reference-v1.0.0"
SLOW_BREAKOUT_SPOT_ENGINE_VERSION = "slow-breakout-spot-reference-v1.0.0"
REFERENCE_REPLAY_RECORD_SCHEMA_VERSION = "aurex-reference-replay-record-v1"
ZERO = Decimal("0")
ONE_HUNDRED = Decimal("100")


@dataclass
class OpenReplayPosition:
    direction: Direction
    entry_at: datetime
    signal_price: Decimal
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal | None
    quantity: Decimal
    entry_fee: Decimal
    entry_slippage: Decimal
    initial_risk: Decimal
    point_value: Decimal
    market_regime: str


def documented_outage_coverage_reasons(quality_snapshot: dict) -> list[str]:
    reasons: list[str] = []
    if not isinstance(quality_snapshot, dict):
        return ["documented_outage_quality_snapshot_missing"]

    observed = quality_snapshot.get("observed_gaps")
    documented = quality_snapshot.get("documented_gaps")
    unmatched = quality_snapshot.get("unmatched_documented_gaps")
    expected_seconds = snapshot_non_negative_int(
        quality_snapshot.get("expected_interval_seconds")
    )
    gap_count = snapshot_non_negative_int(quality_snapshot.get("gap_count"))
    missing_count = snapshot_non_negative_int(
        quality_snapshot.get("missing_interval_count")
    )
    documented_count = snapshot_non_negative_int(
        quality_snapshot.get("documented_gap_count")
    )
    undocumented_count = snapshot_non_negative_int(
        quality_snapshot.get("undocumented_gap_count")
    )

    counts = (
        expected_seconds,
        gap_count,
        missing_count,
        documented_count,
        undocumented_count,
    )
    if any(value is None for value in counts) or expected_seconds == 0:
        reasons.append("documented_outage_counts_invalid")
    if not isinstance(observed, list) or not observed:
        reasons.append("documented_outage_observed_gaps_missing")
        observed = []
    if not isinstance(documented, list) or not documented:
        reasons.append("documented_outage_evidence_missing")
        documented = []
    if not isinstance(unmatched, list):
        reasons.append("documented_outage_unmatched_evidence_invalid")
        unmatched = []
    elif unmatched:
        reasons.append("documented_outage_unmatched_evidence_present")

    observed_windows: list[tuple[datetime, datetime]] = []
    observed_missing_count = 0
    for gap in observed:
        window = snapshot_gap_window(gap)
        if window is None or expected_seconds in (None, 0):
            reasons.append("documented_outage_observed_gap_invalid")
            continue
        start, end = window
        previous = snapshot_datetime(gap.get("previous_timestamp"))
        next_timestamp = snapshot_datetime(gap.get("next_timestamp"))
        gap_missing_count = snapshot_non_negative_int(gap.get("missing_interval_count"))
        expected = timedelta(seconds=expected_seconds)
        if (
            previous is None
            or next_timestamp is None
            or gap_missing_count in (None, 0)
            or start - previous != expected
            or next_timestamp != end
            or end - start != expected * gap_missing_count
        ):
            reasons.append("documented_outage_observed_gap_invalid")
            continue
        observed_windows.append(window)
        observed_missing_count += gap_missing_count

    documented_windows: list[tuple[datetime, datetime]] = []
    for gap in documented:
        window = snapshot_gap_window(gap)
        if (
            window is None
            or not isinstance(gap, dict)
            or not str(gap.get("reason", "")).strip()
            or not str(gap.get("source_reference", "")).strip()
        ):
            reasons.append("documented_outage_evidence_invalid")
            continue
        documented_windows.append(window)

    if has_duplicate_or_overlapping_windows(observed_windows):
        reasons.append("documented_outage_observed_windows_overlap")
    if has_duplicate_or_overlapping_windows(documented_windows):
        reasons.append("documented_outage_evidence_windows_overlap")
    if set(observed_windows) != set(documented_windows):
        reasons.append("documented_outage_coverage_mismatch")
    if (
        gap_count is not None
        and documented_count is not None
        and undocumented_count is not None
        and (
            gap_count == 0
            or gap_count != len(observed)
            or documented_count != gap_count
            or undocumented_count != 0
            or len(documented) != gap_count
        )
    ):
        reasons.append("documented_outage_count_mismatch")
    if missing_count is not None and missing_count != observed_missing_count:
        reasons.append("documented_outage_missing_interval_count_mismatch")
    if quality_snapshot.get("status") != "READY" or quality_snapshot.get(
        "rejection_reasons"
    ):
        reasons.append("documented_outage_dataset_quality_not_ready")
    return list(dict.fromkeys(reasons))


def snapshot_non_negative_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def snapshot_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.utcoffset() is None:
        return None
    return parsed.astimezone(UTC)


def snapshot_gap_window(gap: object) -> tuple[datetime, datetime] | None:
    if not isinstance(gap, dict):
        return None
    start = snapshot_datetime(gap.get("start"))
    end = snapshot_datetime(gap.get("end"))
    if start is None or end is None or end <= start:
        return None
    return start, end


def has_duplicate_or_overlapping_windows(
    windows: list[tuple[datetime, datetime]],
) -> bool:
    ordered = sorted(windows)
    if len(set(ordered)) != len(ordered):
        return True
    return any(
        current_start < previous_end
        for (_, previous_end), (current_start, _) in zip(
            ordered,
            ordered[1:],
            strict=False,
        )
    )
@dataclass(frozen=True)
class ExitFill:
    price: Decimal
    reason: str
    slippage: Decimal
    intrabar_ambiguous: bool = False


class ReferenceReplayEvidenceLab:
    def __init__(self, session: Session) -> None:
        self.session = session

    def preflight(self, request: ReferenceReplayRequest) -> ReferenceReplayResponse:
        return run_reference_replay(self.session, request)

    def record(
        self,
        request: ReferenceReplayRequest,
    ) -> tuple[BacktestReferenceReplayRun, bool]:
        response = self.preflight(request)
        if response.status != "READY" or response.engine_evidence_hash is None:
            reasons = ", ".join(response.reasons) or "reference replay is not ready"
            raise ValueError(f"Reference replay evidence cannot be recorded: {reasons}")

        request_snapshot = request.model_dump(mode="json")
        result_snapshot = reference_replay_result_snapshot(response)
        record_hash = build_reference_replay_record_hash(
            reference_replay_evidence_payload(
                dataset_id=response.dataset_id,
                dataset_evidence_hash=response.dataset_evidence_hash,
                strategy=response.strategy,
                strategy_version=response.strategy_version,
                engine_version=response.engine_version,
                engine_evidence_hash=response.engine_evidence_hash,
                status=response.status,
                request_snapshot=request_snapshot,
                result_snapshot=result_snapshot,
            )
        )
        existing = self.session.execute(
            select(BacktestReferenceReplayRun).where(
                BacktestReferenceReplayRun.engine_evidence_hash
                == response.engine_evidence_hash
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.record_evidence_hash != record_hash:
                raise ValueError(
                    "Existing reference replay evidence differs from the current result; "
                    "run its integrity audit before recording again"
                )
            return existing, True

        recorded_at = utc_now()
        record = BacktestReferenceReplayRun(
            dataset_id=response.dataset_id,
            strategy=response.strategy,
            strategy_version=response.strategy_version,
            engine_version=response.engine_version,
            status=response.status,
            dataset_evidence_hash=response.dataset_evidence_hash,
            engine_evidence_hash=response.engine_evidence_hash,
            record_evidence_hash=record_hash,
            request_snapshot=request_snapshot,
            result_snapshot=result_snapshot,
            recorded_at=recorded_at,
        )
        self.session.add(record)
        self.session.flush()
        SystemEventRecorder(self.session).info(
            "backtest_reference_replay",
            "Immutable reference replay evidence recorded",
            {
                "reference_replay_run_id": record.id,
                "status": record.status,
                "strategy": record.strategy,
                "strategy_version": record.strategy_version,
                "dataset_id": record.dataset_id,
                "dataset_evidence_hash": record.dataset_evidence_hash,
                "engine_evidence_hash": record.engine_evidence_hash,
                "record_evidence_hash": record.record_evidence_hash,
                "total_trades": record.result_snapshot.get("metrics", {}).get(
                    "total_trades"
                ),
                "total_net_pl": record.result_snapshot.get("metrics", {}).get(
                    "total_net_pl"
                ),
                "comparison_only": True,
                "acceptance_eligible": False,
            },
            occurred_at=recorded_at,
        )
        self.session.flush()
        return record, False

    def list_runs(self, limit: int = 100) -> list[BacktestReferenceReplayRun]:
        return list(
            self.session.execute(
                select(BacktestReferenceReplayRun)
                .order_by(BacktestReferenceReplayRun.recorded_at.desc())
                .limit(limit)
            ).scalars()
        )

    def get_run(self, reference_replay_run_id: str) -> BacktestReferenceReplayRun | None:
        return self.session.get(BacktestReferenceReplayRun, reference_replay_run_id)

    def audit(
        self,
        record: BacktestReferenceReplayRun,
    ) -> ReferenceReplayAuditResponse:
        current_record_hash = build_reference_replay_record_hash(
            reference_replay_record_payload(record)
        )
        record_matches = current_record_hash == record.record_evidence_hash
        reasons: list[str] = []
        if not record_matches:
            reasons.append("reference_replay_record_evidence_hash_mismatch")

        replayed_engine_hash: str | None = None
        dataset_matches = False
        engine_matches = False
        result_matches = False
        try:
            request = ReferenceReplayRequest.model_validate(record.request_snapshot)
            replayed = self.preflight(request)
            replayed_engine_hash = replayed.engine_evidence_hash
            dataset_matches = (
                replayed.dataset_evidence_hash == record.dataset_evidence_hash
            )
            engine_matches = replayed_engine_hash == record.engine_evidence_hash
            result_matches = (
                reference_replay_result_snapshot(replayed) == record.result_snapshot
            )
            if replayed.status != "READY":
                reasons.append("reference_replay_source_recheck_blocked")
                reasons.extend(
                    f"reference_replay_source_{reason}" for reason in replayed.reasons
                )
            if not dataset_matches:
                reasons.append("reference_replay_dataset_evidence_drift")
            if not engine_matches:
                reasons.append("reference_replay_engine_evidence_drift")
            if not result_matches:
                reasons.append("reference_replay_result_snapshot_drift")
        except (LookupError, ValueError, TypeError) as exc:
            reasons.append(f"reference_replay_source_recheck_failed:{exc}")

        return ReferenceReplayAuditResponse(
            reference_replay_run_id=record.id,
            status="PASS" if not reasons else "BLOCKED",
            stored_record_evidence_hash=record.record_evidence_hash,
            current_record_evidence_hash=current_record_hash,
            stored_engine_evidence_hash=record.engine_evidence_hash,
            replayed_engine_evidence_hash=replayed_engine_hash,
            record_evidence_hash_matches=record_matches,
            dataset_evidence_hash_matches=dataset_matches,
            engine_evidence_hash_matches=engine_matches,
            result_snapshot_matches=result_matches,
            reasons=reasons,
            checked_at=utc_now(),
        )


def run_reference_replay(
    session: Session,
    request: ReferenceReplayRequest,
) -> ReferenceReplayResponse:
    if request.strategy == "jam_reversal_spot_v1":
        from aurex.backtest_engine.jam_reversal_reference import (
            run_jam_reversal_spot_reference_replay,
        )

        return run_jam_reversal_spot_reference_replay(session, request)
    if request.strategy == "volatility_breakout_v1":
        return run_volatility_breakout_reference_replay(session, request)
    if request.strategy == "slow_breakout_spot_v1":
        return run_slow_breakout_spot_reference_replay(session, request)
    if request.strategy != "trend_pullback_v1" or request.strategy_version != "1.3.0":
        raise ValueError(
            "Reference replay supports trend_pullback_v1 v1.3.0 and "
            "volatility_breakout_v1 v1.1.0, slow_breakout_spot_v1 v1.0.0, "
            "and jam_reversal_spot_v1 v1.0.1"
        )
    required = KNOWN_STRATEGY_REQUIRED_PARAMETERS["trend_pullback_v1"]
    missing = [key for key in required if key not in request.parameters]
    if missing:
        raise ValueError(f"Reference replay parameters missing: {', '.join(missing)}")

    lab = OhlcvDatasetLab(session)
    dataset = lab.get_dataset(request.dataset_id)
    if dataset is None:
        raise LookupError("OHLCV dataset not found")
    audit = lab.audit(dataset)
    if audit.status != "PASS":
        raise ValueError(f"OHLCV dataset integrity audit blocked: {', '.join(audit.reasons)}")
    supported_continuity = {
        "continuous_24_7",
        "continuous_24_7_with_documented_outages",
    }
    if dataset.continuity not in supported_continuity:
        raise ValueError(
            "Reference replay v1 requires continuous 24/7 data, with any outages "
            "fully documented"
        )
    documented_outage_count = 0
    if dataset.continuity == "continuous_24_7_with_documented_outages":
        coverage_reasons = documented_outage_coverage_reasons(dataset.quality_snapshot)
        if coverage_reasons:
            raise ValueError(
                "Reference replay documented-outage coverage is invalid: "
                + ", ".join(coverage_reasons)
            )
        documented_outage_count = int(dataset.quality_snapshot["documented_gap_count"])

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
    parameters = parse_parameters(request.parameters)
    base_timeframe, base_seconds = normalize_timeframe(dataset.timeframe)
    higher_timeframe, higher_seconds = normalize_timeframe(parameters["higher_timeframe"])
    if higher_seconds <= base_seconds or higher_seconds % base_seconds:
        raise ValueError("Higher timeframe must be an integer multiple above dataset timeframe")
    if base_timeframe != dataset.timeframe:
        raise ValueError("Dataset timeframe is not canonical")

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
    ema_fast = ema_series(closes, parameters["pullback_ema_fast"])
    ema_slow = ema_series(closes, parameters["pullback_ema_slow"])
    ema_trend = ema_series(closes, parameters["trend_ema"])
    rsi = rsi_series(closes, parameters["rsi_length"])
    atr = atr_series(candles, parameters["atr_length"])
    htf = higher_timeframe_ema_series(
        candles,
        base_seconds=base_seconds,
        higher_seconds=higher_seconds,
        fast_length=parameters["htf_ema_fast"],
        slow_length=parameters["htf_ema_slow"],
    )

    first_window_index = next(
        (index for index, candle in enumerate(candles) if candle.timestamp >= start),
        None,
    )
    required_base_history = max(
        parameters["pullback_ema_fast"],
        parameters["pullback_ema_slow"],
        parameters["trend_ema"],
        parameters["rsi_length"] + 1,
        parameters["atr_length"],
        parameters["swing_lookback"],
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
        or not indicators_ready(
            first_window_index,
            rsi,
            atr,
            htf,
            parameters["swing_lookback"],
        )
    ):
        reasons.append("insufficient_pre_window_indicator_warmup")

    assumptions = {
        "engine_version": ENGINE_VERSION,
        "dataset_timeframe": base_timeframe,
        "higher_timeframe": higher_timeframe,
        "higher_timeframe_merge": "previous_confirmed_bar_lookahead_on_emulation",
        "higher_timeframe_alignment": "UTC_epoch_boundaries",
        "entry_fill": "signal_bar_close_plus_directional_tick_slippage",
        "stop_fill": "trigger_or_gap_price_plus_adverse_tick_slippage",
        "limit_fill": "declared_take_profit_without_positive_gap_improvement",
        "intrabar_policy": request.intrabar_policy,
        "commission_percent_per_side": decimal_string(request.commission_percent),
        "slippage_ticks": request.slippage_ticks,
        "tick_size": decimal_string(request.tick_size),
        "point_value": decimal_string(request.point_value),
        "minimum_contract": decimal_string(request.minimum_contract),
        "bar_magnifier": False,
    }
    warnings = [
        "Reference replay is comparison-only and cannot satisfy backtest acceptance.",
        "Same-bar stop and target touches resolve stop-first because intrabar order is unknown.",
        "Higher-timeframe and broker-emulator behavior must be parity-checked against TradingView.",
    ]
    if documented_outage_count:
        assumptions["dataset_continuity"] = dataset.continuity
        assumptions["documented_outage_gap_count"] = documented_outage_count
        warnings.append(
            f"Dataset preserves {documented_outage_count} checksum-backed, documented "
            "exchange outage gap(s); no synthetic candles were inserted."
        )
    diagnostics = diagnostic_template(len(candles), start, end)
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
        )

    equity = parameters["initial_capital"]
    position: OpenReplayPosition | None = None
    trades: list[ReferenceReplayTrade] = []
    for index, candle in enumerate(candles):
        candle_close = candle.timestamp + timedelta(seconds=base_seconds)
        in_window = start <= candle.timestamp < end
        entry_window = in_window and candle_close < end
        backtest_exit_bar = candle.timestamp < end <= candle_close
        if in_window:
            diagnostics["bars_in_window"] += 1

        if position is not None:
            exit_fill = resolve_bracket_exit(
                candle,
                position,
                tick_size=request.tick_size,
                slippage_ticks=request.slippage_ticks,
            )
            if exit_fill is None and backtest_exit_bar:
                exit_fill = market_exit(
                    candle.close,
                    position.direction,
                    tick_size=request.tick_size,
                    slippage_ticks=request.slippage_ticks,
                    reason="BACKTEST_WINDOW_END",
                    quantity=position.quantity,
                    point_value=position.point_value,
                )
            if exit_fill is not None:
                trade = close_position(
                    sequence=len(trades) + 1,
                    position=position,
                    fill=exit_fill,
                    closed_at=candle.timestamp,
                    commission_percent=request.commission_percent,
                    equity=equity,
                )
                equity = trade.equity
                trades.append(trade)
                diagnostics["exit_reasons"][trade.exit_reason] = (
                    diagnostics["exit_reasons"].get(trade.exit_reason, 0) + 1
                )
                if trade.intrabar_ambiguous:
                    diagnostics["intrabar_ambiguous_exits"] += 1
                position = None

        if not entry_window or position is not None or index == 0:
            continue
        current_atr = atr[index]
        current_rsi = rsi[index]
        htf_fast, htf_slow = htf[index]
        if current_atr is None or current_rsi is None or htf_fast is None or htf_slow is None:
            continue

        diagnostics["flat_position_pass"] += 1
        pullback_tolerance = current_atr * parameters["pullback_atr_tolerance"]
        near_fast = (
            candle.low <= ema_fast[index] + pullback_tolerance
            and candle.high >= ema_fast[index] - pullback_tolerance
        )
        near_slow = (
            candle.low <= ema_slow[index] + pullback_tolerance
            and candle.high >= ema_slow[index] - pullback_tolerance
        )
        near_pullback = near_fast or near_slow
        if near_pullback:
            diagnostics["pullback_pass"] += 1

        previous = candles[index - 1]
        bullish_confirmation = candle.close > candle.open and candle.close > previous.high
        bearish_confirmation = candle.close < candle.open and candle.close < previous.low
        if bullish_confirmation:
            diagnostics["long_confirmation_pass"] += 1
        if bearish_confirmation:
            diagnostics["short_confirmation_pass"] += 1

        recent = candles[index - parameters["swing_lookback"] + 1 : index + 1]
        recent_low = min(item.low for item in recent)
        recent_high = max(item.high for item in recent)
        long_atr_stop = candle.close - current_atr * parameters["atr_multiplier"]
        short_atr_stop = candle.close + current_atr * parameters["atr_multiplier"]
        long_stop = choose_long_stop(parameters["stop_mode"], long_atr_stop, recent_low)
        short_stop = choose_short_stop(parameters["stop_mode"], short_atr_stop, recent_high)
        slippage_price = request.tick_size * request.slippage_ticks
        expected_long_entry = candle.close + slippage_price
        expected_short_entry = candle.close - slippage_price
        long_risk = expected_long_entry - long_stop
        short_risk = short_stop - expected_short_entry
        long_trend = htf_fast > htf_slow and candle.close > ema_trend[index]
        short_trend = htf_fast < htf_slow and candle.close < ema_trend[index]
        long_rsi = Decimal("40") < current_rsi < Decimal("65")
        short_rsi = Decimal("35") < current_rsi < Decimal("60")
        if long_trend:
            diagnostics["long_trend_pass"] += 1
        if short_trend:
            diagnostics["short_trend_pass"] += 1
        if long_rsi:
            diagnostics["long_rsi_pass"] += 1
        if short_rsi:
            diagnostics["short_rsi_pass"] += 1

        direction: Direction | None = None
        stop = ZERO
        risk = ZERO
        regime = ""
        if (
            parameters["enable_long"]
            and long_trend
            and near_pullback
            and long_rsi
            and bullish_confirmation
            and long_risk > request.tick_size
        ):
            direction = Direction.LONG
            stop = long_stop
            risk = long_risk
            regime = "TRENDING_UP"
            diagnostics["long_setups"] += 1
        elif (
            parameters["enable_short"]
            and short_trend
            and near_pullback
            and short_rsi
            and bearish_confirmation
            and short_risk > request.tick_size
        ):
            direction = Direction.SHORT
            stop = short_stop
            risk = short_risk
            regime = "TRENDING_DOWN"
            diagnostics["short_setups"] += 1
        if direction is None:
            continue

        risk_capital = max(equity, ZERO) * parameters["risk_per_trade_percent"] / ONE_HUNDRED
        expected_entry = (
            expected_long_entry
            if direction == Direction.LONG
            else expected_short_entry
        )
        risk_quantity = risk_capital / (risk * request.point_value)
        max_quantity = (
            equity
            * parameters["max_position_value_percent"]
            / ONE_HUNDRED
            / (expected_entry * request.point_value)
        )
        raw_quantity = min(risk_quantity, max_quantity)
        quantity = (
            raw_quantity / request.minimum_contract
        ).to_integral_value(rounding=ROUND_FLOOR) * request.minimum_contract
        if quantity <= 0:
            diagnostics["quantity_rejections"] += 1
            continue
        take_profit = (
            expected_entry + risk * parameters["reward_risk"]
            if direction == Direction.LONG
            else expected_entry - risk * parameters["reward_risk"]
        )
        entry_price = expected_entry
        if not stop < entry_price < take_profit and direction == Direction.LONG:
            diagnostics["entry_bracket_rejections"] += 1
            continue
        if not take_profit < entry_price < stop and direction == Direction.SHORT:
            diagnostics["entry_bracket_rejections"] += 1
            continue
        entry_fee = (
            entry_price
            * quantity
            * request.point_value
            * request.commission_percent
            / ONE_HUNDRED
        )
        position = OpenReplayPosition(
            direction=direction,
            entry_at=candle.timestamp,
            signal_price=candle.close,
            entry_price=entry_price,
            stop_loss=stop,
            take_profit=take_profit,
            quantity=quantity,
            entry_fee=entry_fee,
            entry_slippage=(
                abs(entry_price - candle.close) * quantity * request.point_value
            ),
            initial_risk=risk * quantity * request.point_value,
            point_value=request.point_value,
            market_regime=regime,
        )

    if position is not None:
        warnings.append("One position remains open because no post-window candle closed it.")
    return replay_response(
        request=request,
        dataset_hash=dataset.evidence_hash,
        status="READY",
        reasons=[],
        warnings=warnings,
        assumptions=assumptions,
        diagnostics=diagnostics,
        trades=trades,
        open_position=position_snapshot(position),
    )


def run_volatility_breakout_reference_replay(
    session: Session,
    request: ReferenceReplayRequest,
) -> ReferenceReplayResponse:
    if request.strategy_version != "1.1.0":
        raise ValueError("Volatility breakout reference replay requires version 1.1.0")
    required = KNOWN_STRATEGY_REQUIRED_PARAMETERS["volatility_breakout_v1"]
    missing = [key for key in required if key not in request.parameters]
    if missing:
        raise ValueError(f"Reference replay parameters missing: {', '.join(missing)}")

    lab = OhlcvDatasetLab(session)
    dataset = lab.get_dataset(request.dataset_id)
    if dataset is None:
        raise LookupError("OHLCV dataset not found")
    audit = lab.audit(dataset)
    if audit.status != "PASS":
        raise ValueError(f"OHLCV dataset integrity audit blocked: {', '.join(audit.reasons)}")
    supported_continuity = {
        "continuous_24_7",
        "continuous_24_7_with_documented_outages",
    }
    if dataset.continuity not in supported_continuity:
        raise ValueError(
            "Reference replay requires continuous 24/7 data, with any outages "
            "fully documented"
        )
    documented_outage_count = 0
    if dataset.continuity == "continuous_24_7_with_documented_outages":
        coverage_reasons = documented_outage_coverage_reasons(dataset.quality_snapshot)
        if coverage_reasons:
            raise ValueError(
                "Reference replay documented-outage coverage is invalid: "
                + ", ".join(coverage_reasons)
            )
        documented_outage_count = int(dataset.quality_snapshot["documented_gap_count"])

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
    parameters = parse_volatility_breakout_parameters(request.parameters)
    base_timeframe, base_seconds = normalize_timeframe(dataset.timeframe)
    higher_timeframe, higher_seconds = normalize_timeframe(parameters["higher_timeframe"])
    if higher_seconds <= base_seconds or higher_seconds % base_seconds:
        raise ValueError("Higher timeframe must be an integer multiple above dataset timeframe")
    if base_timeframe != dataset.timeframe:
        raise ValueError("Dataset timeframe is not canonical")

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

    atr = atr_series(candles, parameters["atr_length"])
    atr_average = simple_moving_average_series(
        atr,
        parameters["compression_lookback"],
    )
    volume_average = simple_moving_average_series(
        [candle.volume for candle in candles],
        parameters["volume_length"],
    )
    htf = higher_timeframe_ema_series(
        candles,
        base_seconds=base_seconds,
        higher_seconds=higher_seconds,
        fast_length=parameters["htf_ema_fast"],
        slow_length=parameters["htf_ema_slow"],
    )
    first_window_index = next(
        (index for index, candle in enumerate(candles) if candle.timestamp >= start),
        None,
    )
    required_base_history = max(
        parameters["breakout_lookback"] + 1,
        parameters["atr_length"] + parameters["compression_lookback"] - 1,
        parameters["volume_length"],
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
        or atr[first_window_index] is None
        or atr_average[first_window_index] is None
        or volume_average[first_window_index] is None
        or htf[first_window_index][0] is None
        or htf[first_window_index][1] is None
    ):
        reasons.append("insufficient_pre_window_indicator_warmup")

    assumptions = {
        "engine_version": VOLATILITY_BREAKOUT_ENGINE_VERSION,
        "dataset_timeframe": base_timeframe,
        "higher_timeframe": higher_timeframe,
        "higher_timeframe_merge": "previous_confirmed_bar_lookahead_on_emulation",
        "higher_timeframe_alignment": "UTC_epoch_boundaries",
        "entry_fill": "signal_bar_close_plus_directional_tick_slippage",
        "stop_fill": "trigger_or_gap_price_plus_adverse_tick_slippage",
        "limit_fill": "declared_take_profit_without_positive_gap_improvement",
        "compression": "current_atr_below_sma_of_atr_including_current_bar",
        "breakout": "close_beyond_previous_lookback_extreme",
        "volume": "current_volume_at_least_expansion_times_sma_including_current_bar",
        "intrabar_policy": request.intrabar_policy,
        "commission_percent_per_side": decimal_string(request.commission_percent),
        "slippage_ticks": request.slippage_ticks,
        "tick_size": decimal_string(request.tick_size),
        "point_value": decimal_string(request.point_value),
        "minimum_contract": decimal_string(request.minimum_contract),
        "bar_magnifier": False,
    }
    warnings = [
        "Reference replay is comparison-only and cannot satisfy backtest acceptance.",
        "Same-bar stop and target touches resolve stop-first because intrabar order is unknown.",
        "Higher-timeframe and broker-emulator behavior must be parity-checked against TradingView.",
        "This is the preregistered one-shot v1.1.0 evaluation; do not tune it after results.",
    ]
    if documented_outage_count:
        assumptions["dataset_continuity"] = dataset.continuity
        assumptions["documented_outage_gap_count"] = documented_outage_count
        warnings.append(
            f"Dataset preserves {documented_outage_count} checksum-backed, documented "
            "exchange outage gap(s); no synthetic candles were inserted."
        )
    diagnostics = volatility_breakout_diagnostic_template(len(candles), start, end)
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
            engine_version=VOLATILITY_BREAKOUT_ENGINE_VERSION,
        )

    equity = parameters["initial_capital"]
    position: OpenReplayPosition | None = None
    trades: list[ReferenceReplayTrade] = []
    for index, candle in enumerate(candles):
        candle_close = candle.timestamp + timedelta(seconds=base_seconds)
        in_window = start <= candle.timestamp < end
        entry_window = in_window and candle_close < end
        backtest_exit_bar = candle.timestamp < end <= candle_close
        if in_window:
            diagnostics["bars_in_window"] += 1

        if position is not None:
            exit_fill = resolve_bracket_exit(
                candle,
                position,
                tick_size=request.tick_size,
                slippage_ticks=request.slippage_ticks,
            )
            if exit_fill is None and backtest_exit_bar:
                exit_fill = market_exit(
                    candle.close,
                    position.direction,
                    tick_size=request.tick_size,
                    slippage_ticks=request.slippage_ticks,
                    reason="BACKTEST_WINDOW_END",
                    quantity=position.quantity,
                    point_value=position.point_value,
                )
            if exit_fill is not None:
                trade = close_position(
                    sequence=len(trades) + 1,
                    position=position,
                    fill=exit_fill,
                    closed_at=candle.timestamp,
                    commission_percent=request.commission_percent,
                    equity=equity,
                )
                equity = trade.equity
                trades.append(trade)
                diagnostics["exit_reasons"][trade.exit_reason] = (
                    diagnostics["exit_reasons"].get(trade.exit_reason, 0) + 1
                )
                if trade.intrabar_ambiguous:
                    diagnostics["intrabar_ambiguous_exits"] += 1
                position = None

        lookback = parameters["breakout_lookback"]
        if not entry_window or position is not None or index < lookback:
            continue
        current_atr = atr[index]
        current_atr_average = atr_average[index]
        current_volume_average = volume_average[index]
        htf_fast, htf_slow = htf[index]
        if (
            current_atr is None
            or current_atr_average is None
            or current_volume_average is None
            or htf_fast is None
            or htf_slow is None
        ):
            continue

        diagnostics["flat_position_pass"] += 1
        compression = current_atr < current_atr_average
        volume_confirmed = (
            current_volume_average > ZERO
            and candle.volume
            >= current_volume_average * parameters["volume_expansion"]
        )
        previous = candles[index - lookback : index]
        previous_high = max(item.high for item in previous)
        previous_low = min(item.low for item in previous)
        long_bias = htf_fast > htf_slow
        short_bias = htf_fast < htf_slow
        long_breakout = candle.close > previous_high and candle.close > candle.open
        short_breakout = candle.close < previous_low and candle.close < candle.open
        if compression:
            diagnostics["compression_pass"] += 1
        if volume_confirmed:
            diagnostics["volume_pass"] += 1
        if long_bias:
            diagnostics["long_bias_pass"] += 1
        if short_bias:
            diagnostics["short_bias_pass"] += 1
        if long_breakout:
            diagnostics["long_breakout_pass"] += 1
        if short_breakout:
            diagnostics["short_breakout_pass"] += 1

        slippage_price = request.tick_size * request.slippage_ticks
        expected_long_entry = candle.close + slippage_price
        expected_short_entry = candle.close - slippage_price
        long_stop = candle.close - current_atr * parameters["atr_stop_multiplier"]
        short_stop = candle.close + current_atr * parameters["atr_stop_multiplier"]
        long_risk = expected_long_entry - long_stop
        short_risk = short_stop - expected_short_entry
        direction: Direction | None = None
        stop = ZERO
        risk = ZERO
        if (
            parameters["enable_long"]
            and compression
            and volume_confirmed
            and long_bias
            and long_breakout
            and long_risk > request.tick_size
        ):
            direction = Direction.LONG
            stop = long_stop
            risk = long_risk
            diagnostics["long_setups"] += 1
        elif (
            parameters["enable_short"]
            and compression
            and volume_confirmed
            and short_bias
            and short_breakout
            and short_risk > request.tick_size
        ):
            direction = Direction.SHORT
            stop = short_stop
            risk = short_risk
            diagnostics["short_setups"] += 1
        if direction is None:
            continue

        expected_entry = (
            expected_long_entry if direction == Direction.LONG else expected_short_entry
        )
        risk_capital = max(equity, ZERO) * parameters["risk_per_trade_percent"] / ONE_HUNDRED
        risk_quantity = risk_capital / (risk * request.point_value)
        max_quantity = (
            equity
            * parameters["max_position_value_percent"]
            / ONE_HUNDRED
            / (expected_entry * request.point_value)
        )
        raw_quantity = min(risk_quantity, max_quantity)
        quantity = (
            raw_quantity / request.minimum_contract
        ).to_integral_value(rounding=ROUND_FLOOR) * request.minimum_contract
        if quantity <= 0:
            diagnostics["quantity_rejections"] += 1
            continue
        take_profit = (
            expected_entry + risk * parameters["reward_risk"]
            if direction == Direction.LONG
            else expected_entry - risk * parameters["reward_risk"]
        )
        if direction == Direction.LONG and not stop < expected_entry < take_profit:
            diagnostics["entry_bracket_rejections"] += 1
            continue
        if direction == Direction.SHORT and not take_profit < expected_entry < stop:
            diagnostics["entry_bracket_rejections"] += 1
            continue
        entry_fee = (
            expected_entry
            * quantity
            * request.point_value
            * request.commission_percent
            / ONE_HUNDRED
        )
        position = OpenReplayPosition(
            direction=direction,
            entry_at=candle.timestamp,
            signal_price=candle.close,
            entry_price=expected_entry,
            stop_loss=stop,
            take_profit=take_profit,
            quantity=quantity,
            entry_fee=entry_fee,
            entry_slippage=(
                abs(expected_entry - candle.close) * quantity * request.point_value
            ),
            initial_risk=risk * quantity * request.point_value,
            point_value=request.point_value,
            market_regime="BREAKOUT_EXPANSION",
        )

    if position is not None:
        warnings.append("One position remains open because no post-window candle closed it.")
    return replay_response(
        request=request,
        dataset_hash=dataset.evidence_hash,
        status="READY",
        reasons=[],
        warnings=warnings,
        assumptions=assumptions,
        diagnostics=diagnostics,
        trades=trades,
        open_position=position_snapshot(position),
        engine_version=VOLATILITY_BREAKOUT_ENGINE_VERSION,
    )


def run_slow_breakout_spot_reference_replay(
    session: Session,
    request: ReferenceReplayRequest,
) -> ReferenceReplayResponse:
    if request.strategy_version != "1.0.0":
        raise ValueError("Slow breakout spot reference replay requires version 1.0.0")
    required = KNOWN_STRATEGY_REQUIRED_PARAMETERS["slow_breakout_spot_v1"]
    missing = [key for key in required if key not in request.parameters]
    if missing:
        raise ValueError(f"Reference replay parameters missing: {', '.join(missing)}")

    lab = OhlcvDatasetLab(session)
    dataset = lab.get_dataset(request.dataset_id)
    if dataset is None:
        raise LookupError("OHLCV dataset not found")
    audit = lab.audit(dataset)
    if audit.status != "PASS":
        raise ValueError(f"OHLCV dataset integrity audit blocked: {', '.join(audit.reasons)}")
    supported_continuity = {
        "continuous_24_7",
        "continuous_24_7_with_documented_outages",
    }
    if dataset.continuity not in supported_continuity:
        raise ValueError(
            "Reference replay requires continuous 24/7 data, with any outages "
            "fully documented"
        )
    documented_outage_count = 0
    if dataset.continuity == "continuous_24_7_with_documented_outages":
        coverage_reasons = documented_outage_coverage_reasons(dataset.quality_snapshot)
        if coverage_reasons:
            raise ValueError(
                "Reference replay documented-outage coverage is invalid: "
                + ", ".join(coverage_reasons)
            )
        documented_outage_count = int(dataset.quality_snapshot["documented_gap_count"])

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
    parameters = parse_slow_breakout_spot_parameters(request.parameters)
    base_timeframe, base_seconds = normalize_timeframe(dataset.timeframe)
    if base_timeframe != dataset.timeframe:
        raise ValueError("Dataset timeframe is not canonical")
    if base_seconds != 4 * 60 * 60:
        raise ValueError("Slow breakout spot reference replay requires native 4h data")

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

    atr = atr_series(candles, parameters["atr_length"])
    first_window_index = next(
        (index for index, candle in enumerate(candles) if candle.timestamp >= start),
        None,
    )
    required_base_history = max(
        parameters["entry_channel_length"] + 1,
        parameters["exit_channel_length"] + 1,
        parameters["atr_length"],
    )
    if first_window_index is None:
        reasons.append("backtest_window_has_no_candles")
    elif (
        first_window_index + 1 < required_base_history
        or atr[first_window_index] is None
    ):
        reasons.append("insufficient_pre_window_indicator_warmup")

    assumptions = {
        "engine_version": SLOW_BREAKOUT_SPOT_ENGINE_VERSION,
        "dataset_timeframe": base_timeframe,
        "market": "spot",
        "direction": "long_only",
        "leverage": False,
        "borrow_or_funding": False,
        "entry_signal": "confirmed_close_above_previous_entry_channel_high",
        "entry_fill": "signal_bar_close_plus_adverse_tick_slippage",
        "stop": "fixed_initial_atr_catastrophe_stop",
        "stop_fill": "trigger_or_gap_price_plus_adverse_tick_slippage",
        "channel_exit": "confirmed_close_below_previous_exit_channel_low",
        "channel_exit_fill": "signal_bar_close_minus_adverse_tick_slippage",
        "take_profit": None,
        "same_bar_reentry_after_exit": False,
        "intrabar_policy": request.intrabar_policy,
        "commission_percent_per_side": decimal_string(request.commission_percent),
        "slippage_ticks": request.slippage_ticks,
        "tick_size": decimal_string(request.tick_size),
        "point_value": decimal_string(request.point_value),
        "minimum_contract": decimal_string(request.minimum_contract),
        "bar_magnifier": False,
    }
    warnings = [
        "Reference replay remains ineligible until its preregistered validation passes.",
        "This candidate has no profit target; current Aurex paper risk rules reject such signals.",
        "Pine and local order semantics still require trade-level parity before paper operation.",
        "This is the frozen one-shot v1.0.0 evaluation; do not tune it after holdout results.",
    ]
    if documented_outage_count:
        assumptions["dataset_continuity"] = dataset.continuity
        assumptions["documented_outage_gap_count"] = documented_outage_count
        warnings.append(
            f"Dataset preserves {documented_outage_count} checksum-backed, documented "
            "exchange outage gap(s); no synthetic candles were inserted."
        )
    diagnostics = slow_breakout_spot_diagnostic_template(len(candles), start, end)
    diagnostics["warmup"] = {
        "base_candles_available_at_start": (
            first_window_index + 1 if first_window_index is not None else 0
        ),
        "base_candles_required": required_base_history,
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
            engine_version=SLOW_BREAKOUT_SPOT_ENGINE_VERSION,
        )

    equity = parameters["initial_capital"]
    position: OpenReplayPosition | None = None
    trades: list[ReferenceReplayTrade] = []
    for index, candle in enumerate(candles):
        candle_close = candle.timestamp + timedelta(seconds=base_seconds)
        in_window = start <= candle.timestamp < end
        entry_window = in_window and candle_close < end
        backtest_exit_bar = candle.timestamp < end <= candle_close
        exited_this_bar = False
        if in_window:
            diagnostics["bars_in_window"] += 1

        if position is not None:
            exit_fill = resolve_bracket_exit(
                candle,
                position,
                tick_size=request.tick_size,
                slippage_ticks=request.slippage_ticks,
            )
            if (
                exit_fill is None
                and in_window
                and index >= parameters["exit_channel_length"]
            ):
                previous_exit_low = min(
                    item.low
                    for item in candles[
                        index - parameters["exit_channel_length"] : index
                    ]
                )
                if candle.close < previous_exit_low:
                    diagnostics["channel_exit_signals"] += 1
                    exit_fill = market_exit(
                        candle.close,
                        position.direction,
                        tick_size=request.tick_size,
                        slippage_ticks=request.slippage_ticks,
                        reason="CHANNEL_EXIT",
                        quantity=position.quantity,
                        point_value=position.point_value,
                    )
            if exit_fill is None and backtest_exit_bar:
                exit_fill = market_exit(
                    candle.close,
                    position.direction,
                    tick_size=request.tick_size,
                    slippage_ticks=request.slippage_ticks,
                    reason="BACKTEST_WINDOW_END",
                    quantity=position.quantity,
                    point_value=position.point_value,
                )
            if exit_fill is not None:
                trade = close_position(
                    sequence=len(trades) + 1,
                    position=position,
                    fill=exit_fill,
                    closed_at=candle.timestamp,
                    commission_percent=request.commission_percent,
                    equity=equity,
                )
                equity = trade.equity
                trades.append(trade)
                diagnostics["exit_reasons"][trade.exit_reason] = (
                    diagnostics["exit_reasons"].get(trade.exit_reason, 0) + 1
                )
                if trade.intrabar_ambiguous:
                    diagnostics["intrabar_ambiguous_exits"] += 1
                position = None
                exited_this_bar = True

        entry_length = parameters["entry_channel_length"]
        if (
            not entry_window
            or position is not None
            or exited_this_bar
            or index < entry_length
        ):
            continue
        current_atr = atr[index]
        if current_atr is None:
            continue
        diagnostics["flat_position_pass"] += 1
        previous_entry_high = max(
            item.high for item in candles[index - entry_length : index]
        )
        long_breakout = candle.close > previous_entry_high
        if long_breakout:
            diagnostics["long_breakout_pass"] += 1

        expected_entry = candle.close + request.tick_size * request.slippage_ticks
        stop = candle.close - current_atr * parameters["atr_stop_multiplier"]
        risk = expected_entry - stop
        if (
            not parameters["enable_long"]
            or not long_breakout
            or stop <= request.tick_size
            or risk <= request.tick_size
        ):
            continue
        diagnostics["long_setups"] += 1

        available_equity = max(equity, ZERO)
        risk_capital = (
            available_equity
            * parameters["risk_per_trade_percent"]
            / ONE_HUNDRED
        )
        risk_quantity = risk_capital / (risk * request.point_value)
        max_quantity = (
            available_equity
            * parameters["max_position_value_percent"]
            / ONE_HUNDRED
            / (expected_entry * request.point_value)
        )
        raw_quantity = min(risk_quantity, max_quantity)
        quantity = (
            raw_quantity / request.minimum_contract
        ).to_integral_value(rounding=ROUND_FLOOR) * request.minimum_contract
        if quantity <= 0:
            diagnostics["quantity_rejections"] += 1
            continue
        entry_fee = (
            expected_entry
            * quantity
            * request.point_value
            * request.commission_percent
            / ONE_HUNDRED
        )
        position = OpenReplayPosition(
            direction=Direction.LONG,
            entry_at=candle.timestamp,
            signal_price=candle.close,
            entry_price=expected_entry,
            stop_loss=stop,
            take_profit=None,
            quantity=quantity,
            entry_fee=entry_fee,
            entry_slippage=(
                abs(expected_entry - candle.close) * quantity * request.point_value
            ),
            initial_risk=risk * quantity * request.point_value,
            point_value=request.point_value,
            market_regime="TRENDING_UP",
        )

    if position is not None:
        warnings.append("One position remains open because no post-window candle closed it.")
    return replay_response(
        request=request,
        dataset_hash=dataset.evidence_hash,
        status="READY",
        reasons=[],
        warnings=warnings,
        assumptions=assumptions,
        diagnostics=diagnostics,
        trades=trades,
        open_position=position_snapshot(position),
        engine_version=SLOW_BREAKOUT_SPOT_ENGINE_VERSION,
    )


def replay_response(
    *,
    request: ReferenceReplayRequest,
    dataset_hash: str,
    status: str,
    reasons: list[str],
    warnings: list[str],
    assumptions: dict,
    diagnostics: dict,
    trades: list[ReferenceReplayTrade],
    open_position: dict | None,
    engine_version: str = ENGINE_VERSION,
) -> ReferenceReplayResponse:
    metrics = calculate_backtest_metrics(
        [
            BacktestTradeInput(
                realized_pl=trade.realized_pl,
                closed_at=trade.closed_at,
                market_regime=trade.market_regime,
            )
            for trade in trades
        ]
    )
    metrics_snapshot = {
        "total_trades": metrics.total_trades,
        "wins": metrics.wins,
        "losses": metrics.losses,
        "breakeven": metrics.breakeven,
        "win_rate": decimal_string(metrics.win_rate),
        "expectancy": decimal_string(metrics.expectancy),
        "profit_factor": (
            decimal_string(metrics.profit_factor) if metrics.profit_factor is not None else None
        ),
        "max_drawdown": decimal_string(metrics.max_drawdown),
        "total_net_pl": decimal_string(metrics.total_net_pl),
    }
    evidence = {
        "engine_version": engine_version,
        "dataset_evidence_hash": dataset_hash,
        "strategy": request.strategy,
        "strategy_version": request.strategy_version,
        "parameters": request.parameters,
        "assumptions": assumptions,
        "trades": [trade.model_dump(mode="json") for trade in trades],
        "open_position": open_position,
    }
    engine_hash = (
        sha256(
            json.dumps(evidence, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
        if status == "READY"
        else None
    )
    return ReferenceReplayResponse(
        status=status,
        engine_version=engine_version,
        strategy=request.strategy,
        strategy_version=request.strategy_version,
        dataset_id=request.dataset_id,
        dataset_evidence_hash=dataset_hash,
        engine_evidence_hash=engine_hash,
        comparison_only=True,
        acceptance_eligible=False,
        reasons=reasons,
        warnings=warnings,
        assumptions=assumptions,
        diagnostics=diagnostics,
        metrics=metrics_snapshot,
        trades=trades,
        open_position=open_position,
        checked_at=utc_now(),
        mutates_ledger=False,
    )


def reference_replay_result_snapshot(response: ReferenceReplayResponse) -> dict:
    return response.model_dump(
        mode="json",
        exclude={
            "id",
            "record_evidence_hash",
            "immutable",
            "reused_existing",
            "recorded_at",
            "checked_at",
        },
    )


def reference_replay_record_response(
    record: BacktestReferenceReplayRun,
    *,
    reused_existing: bool = False,
) -> ReferenceReplayResponse:
    recorded_at = ensure_utc(record.recorded_at)
    return ReferenceReplayResponse.model_validate(
        {
            **record.result_snapshot,
            "id": record.id,
            "record_evidence_hash": record.record_evidence_hash,
            "immutable": True,
            "reused_existing": reused_existing,
            "recorded_at": recorded_at,
            "checked_at": recorded_at,
            "mutates_ledger": True,
        }
    )


def reference_replay_summary_response(
    record: BacktestReferenceReplayRun,
) -> ReferenceReplaySummaryResponse:
    result = record.result_snapshot
    return ReferenceReplaySummaryResponse(
        id=record.id,
        status=record.status,
        engine_version=record.engine_version,
        strategy=record.strategy,
        strategy_version=record.strategy_version,
        dataset_id=record.dataset_id,
        dataset_evidence_hash=record.dataset_evidence_hash,
        engine_evidence_hash=record.engine_evidence_hash,
        record_evidence_hash=record.record_evidence_hash,
        metrics=result.get("metrics", {}),
        diagnostics=result.get("diagnostics", {}),
        reasons=result.get("reasons", []),
        warnings=result.get("warnings", []),
        recorded_at=ensure_utc(record.recorded_at),
    )


def reference_replay_record_payload(record: BacktestReferenceReplayRun) -> dict:
    return reference_replay_evidence_payload(
        dataset_id=record.dataset_id,
        dataset_evidence_hash=record.dataset_evidence_hash,
        strategy=record.strategy,
        strategy_version=record.strategy_version,
        engine_version=record.engine_version,
        engine_evidence_hash=record.engine_evidence_hash,
        status=record.status,
        request_snapshot=record.request_snapshot,
        result_snapshot=record.result_snapshot,
    )


def reference_replay_evidence_payload(
    *,
    dataset_id: str,
    dataset_evidence_hash: str,
    strategy: str,
    strategy_version: str,
    engine_version: str,
    engine_evidence_hash: str,
    status: str,
    request_snapshot: dict,
    result_snapshot: dict,
) -> dict:
    return {
        "schema_version": REFERENCE_REPLAY_RECORD_SCHEMA_VERSION,
        "dataset_id": dataset_id,
        "dataset_evidence_hash": dataset_evidence_hash,
        "strategy": strategy,
        "strategy_version": strategy_version,
        "engine_version": engine_version,
        "engine_evidence_hash": engine_evidence_hash,
        "status": status,
        "request_snapshot": request_snapshot,
        "result_snapshot": result_snapshot,
    }


def build_reference_replay_record_hash(payload: dict) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()
    return sha256(encoded).hexdigest()


def parse_parameters(parameters: dict) -> dict:
    def integer(key: str) -> int:
        value = int(parameters[key])
        if value <= 0:
            raise ValueError(f"{key} must be positive")
        return value

    def decimal(key: str) -> Decimal:
        value = Decimal(str(parameters[key]))
        if not value.is_finite() or value <= 0:
            raise ValueError(f"{key} must be positive and finite")
        return value

    def non_negative_decimal(key: str) -> Decimal:
        value = Decimal(str(parameters[key]))
        if not value.is_finite() or value < 0:
            raise ValueError(f"{key} must be non-negative and finite")
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

    stop_mode = str(parameters["stop_mode"])
    if stop_mode not in {"ATR", "Swing", "Wider"}:
        raise ValueError("stop_mode must be ATR, Swing, or Wider")
    parsed = {
        "initial_capital": decimal("initial_capital"),
        "backtest_start": parse_timestamp(parameters["backtest_start"]),
        "backtest_end": parse_timestamp(parameters["backtest_end"]),
        "higher_timeframe": str(parameters["higher_timeframe"]),
        "pullback_ema_fast": integer("pullback_ema_fast"),
        "pullback_ema_slow": integer("pullback_ema_slow"),
        "trend_ema": integer("trend_ema"),
        "htf_ema_fast": integer("htf_ema_fast"),
        "htf_ema_slow": integer("htf_ema_slow"),
        "rsi_length": integer("rsi_length"),
        "atr_length": integer("atr_length"),
        "atr_multiplier": decimal("atr_multiplier"),
        "reward_risk": decimal("reward_risk"),
        "swing_lookback": integer("swing_lookback"),
        "pullback_atr_tolerance": non_negative_decimal("pullback_atr_tolerance"),
        "stop_mode": stop_mode,
        "risk_per_trade_percent": decimal("risk_per_trade_percent"),
        "max_position_value_percent": decimal("max_position_value_percent"),
        "enable_long": boolean("enable_long"),
        "enable_short": boolean("enable_short"),
    }
    if parsed["swing_lookback"] < 2:
        raise ValueError("swing_lookback must be at least 2")
    if parsed["reward_risk"] < 1:
        raise ValueError("reward_risk must be at least 1")
    if parsed["atr_multiplier"] < Decimal("0.1"):
        raise ValueError("atr_multiplier must be at least 0.1")
    if not Decimal("0.1") <= parsed["risk_per_trade_percent"] <= Decimal("2"):
        raise ValueError("risk_per_trade_percent must be between 0.1 and 2")
    if not Decimal("1") <= parsed["max_position_value_percent"] <= Decimal("100"):
        raise ValueError("max_position_value_percent must be between 1 and 100")
    return parsed


def parse_volatility_breakout_parameters(parameters: dict) -> dict:
    def integer(key: str) -> int:
        value = int(parameters[key])
        if value <= 0:
            raise ValueError(f"{key} must be positive")
        return value

    def decimal(key: str) -> Decimal:
        value = Decimal(str(parameters[key]))
        if not value.is_finite() or value <= 0:
            raise ValueError(f"{key} must be positive and finite")
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
        "initial_capital": decimal("initial_capital"),
        "backtest_start": parse_timestamp(parameters["backtest_start"]),
        "backtest_end": parse_timestamp(parameters["backtest_end"]),
        "higher_timeframe": str(parameters["higher_timeframe"]),
        "htf_ema_fast": integer("htf_ema_fast"),
        "htf_ema_slow": integer("htf_ema_slow"),
        "breakout_lookback": integer("breakout_lookback"),
        "compression_lookback": integer("compression_lookback"),
        "atr_length": integer("atr_length"),
        "atr_stop_multiplier": decimal("atr_stop_multiplier"),
        "reward_risk": decimal("reward_risk"),
        "volume_length": integer("volume_length"),
        "volume_expansion": decimal("volume_expansion"),
        "risk_per_trade_percent": decimal("risk_per_trade_percent"),
        "max_position_value_percent": decimal("max_position_value_percent"),
        "enable_long": boolean("enable_long"),
        "enable_short": boolean("enable_short"),
    }
    if parsed["breakout_lookback"] < 5:
        raise ValueError("breakout_lookback must be at least 5")
    if parsed["compression_lookback"] < 10:
        raise ValueError("compression_lookback must be at least 10")
    if parsed["atr_stop_multiplier"] < Decimal("0.1"):
        raise ValueError("atr_stop_multiplier must be at least 0.1")
    if parsed["reward_risk"] < Decimal("1"):
        raise ValueError("reward_risk must be at least 1")
    if parsed["volume_expansion"] < Decimal("1"):
        raise ValueError("volume_expansion must be at least 1")
    if not Decimal("0.1") <= parsed["risk_per_trade_percent"] <= Decimal("2"):
        raise ValueError("risk_per_trade_percent must be between 0.1 and 2")
    if not Decimal("1") <= parsed["max_position_value_percent"] <= Decimal("100"):
        raise ValueError("max_position_value_percent must be between 1 and 100")
    return parsed


def parse_slow_breakout_spot_parameters(parameters: dict) -> dict:
    def integer(key: str) -> int:
        value = int(parameters[key])
        if value <= 0:
            raise ValueError(f"{key} must be positive")
        return value

    def decimal(key: str) -> Decimal:
        value = Decimal(str(parameters[key]))
        if not value.is_finite() or value <= 0:
            raise ValueError(f"{key} must be positive and finite")
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
        "initial_capital": decimal("initial_capital"),
        "backtest_start": parse_timestamp(parameters["backtest_start"]),
        "backtest_end": parse_timestamp(parameters["backtest_end"]),
        "entry_channel_length": integer("entry_channel_length"),
        "exit_channel_length": integer("exit_channel_length"),
        "atr_length": integer("atr_length"),
        "atr_stop_multiplier": decimal("atr_stop_multiplier"),
        "risk_per_trade_percent": decimal("risk_per_trade_percent"),
        "max_position_value_percent": decimal("max_position_value_percent"),
        "enable_long": boolean("enable_long"),
    }
    if parsed["entry_channel_length"] <= parsed["exit_channel_length"]:
        raise ValueError("entry_channel_length must exceed exit_channel_length")
    if parsed["atr_stop_multiplier"] < Decimal("0.1"):
        raise ValueError("atr_stop_multiplier must be at least 0.1")
    if not Decimal("0.1") <= parsed["risk_per_trade_percent"] <= Decimal("2"):
        raise ValueError("risk_per_trade_percent must be between 0.1 and 2")
    if not Decimal("1") <= parsed["max_position_value_percent"] <= Decimal("100"):
        raise ValueError("max_position_value_percent must be between 1 and 100")
    return parsed


def parse_timestamp(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return ensure_utc(parsed)


def ema_series(values: list[Decimal], length: int) -> list[Decimal]:
    if not values:
        return []
    alpha = Decimal("2") / Decimal(length + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append(value * alpha + result[-1] * (Decimal("1") - alpha))
    return result


def simple_moving_average_series(
    values: list[Decimal | None],
    length: int,
) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * len(values)
    for index in range(length - 1, len(values)):
        window = values[index - length + 1 : index + 1]
        if any(value is None for value in window):
            continue
        result[index] = sum((value for value in window if value is not None), ZERO) / Decimal(
            length
        )
    return result


def rsi_series(values: list[Decimal], length: int) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * len(values)
    if len(values) <= length:
        return result
    gains = [max(values[index] - values[index - 1], ZERO) for index in range(1, len(values))]
    losses = [max(values[index - 1] - values[index], ZERO) for index in range(1, len(values))]
    average_gain = sum(gains[:length], ZERO) / Decimal(length)
    average_loss = sum(losses[:length], ZERO) / Decimal(length)
    result[length] = rsi_value(average_gain, average_loss)
    for index in range(length + 1, len(values)):
        average_gain = (average_gain * (length - 1) + gains[index - 1]) / Decimal(length)
        average_loss = (average_loss * (length - 1) + losses[index - 1]) / Decimal(length)
        result[index] = rsi_value(average_gain, average_loss)
    return result


def rsi_value(average_gain: Decimal, average_loss: Decimal) -> Decimal:
    if average_loss == 0:
        return Decimal("100") if average_gain > 0 else Decimal("50")
    relative_strength = average_gain / average_loss
    return Decimal("100") - Decimal("100") / (Decimal("1") + relative_strength)


def atr_series(candles: list[OhlcvCandle], length: int) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * len(candles)
    if len(candles) < length:
        return result
    true_ranges: list[Decimal] = []
    for index, candle in enumerate(candles):
        if index == 0:
            true_ranges.append(candle.high - candle.low)
        else:
            previous_close = candles[index - 1].close
            true_ranges.append(
                max(
                    candle.high - candle.low,
                    abs(candle.high - previous_close),
                    abs(candle.low - previous_close),
                )
            )
    average = sum(true_ranges[:length], ZERO) / Decimal(length)
    result[length - 1] = average
    for index in range(length, len(candles)):
        average = (average * (length - 1) + true_ranges[index]) / Decimal(length)
        result[index] = average
    return result


def higher_timeframe_ema_series(
    candles: list[OhlcvCandle],
    *,
    base_seconds: int,
    higher_seconds: int,
    fast_length: int,
    slow_length: int,
) -> list[tuple[Decimal | None, Decimal | None]]:
    ratio = higher_seconds // base_seconds
    groups: dict[int, list[OhlcvCandle]] = {}
    for candle in candles:
        epoch = int(candle.timestamp.timestamp())
        group_start = epoch - epoch % higher_seconds
        groups.setdefault(group_start, []).append(candle)
    complete: list[tuple[int, Decimal]] = []
    for group_start, rows in sorted(groups.items()):
        expected_start = datetime.fromtimestamp(group_start, tz=UTC)
        expected_end = expected_start + timedelta(seconds=higher_seconds - base_seconds)
        complete_group = (
            len(rows) == ratio
            and rows[0].timestamp == expected_start
            and rows[-1].timestamp == expected_end
        )
        if complete_group:
            complete.append((group_start, rows[-1].close))
    fast_values = ema_series([close for _, close in complete], fast_length)
    slow_values = ema_series([close for _, close in complete], slow_length)
    completed_values = {
        group_start: (fast_values[index], slow_values[index])
        for index, (group_start, _) in enumerate(complete)
    }
    result: list[tuple[Decimal | None, Decimal | None]] = []
    last: tuple[Decimal | None, Decimal | None] = (None, None)
    for candle in candles:
        epoch = int(candle.timestamp.timestamp())
        group_start = epoch - epoch % higher_seconds
        previous_group_start = group_start - higher_seconds
        if (
            candle.timestamp == datetime.fromtimestamp(group_start, tz=UTC)
            and previous_group_start in completed_values
        ):
            last = completed_values[previous_group_start]
        result.append(last)
    return result


def complete_higher_timeframe_count(
    candles: list[OhlcvCandle],
    *,
    base_seconds: int,
    higher_seconds: int,
    through: datetime,
) -> int:
    ratio = higher_seconds // base_seconds
    groups: dict[int, list[OhlcvCandle]] = {}
    for candle in candles:
        if candle.timestamp > through:
            break
        epoch = int(candle.timestamp.timestamp())
        group_start = epoch - epoch % higher_seconds
        groups.setdefault(group_start, []).append(candle)
    count = 0
    for group_start, rows in groups.items():
        expected_start = datetime.fromtimestamp(group_start, tz=UTC)
        expected_end = expected_start + timedelta(seconds=higher_seconds - base_seconds)
        complete_group = (
            len(rows) == ratio
            and rows[0].timestamp == expected_start
            and rows[-1].timestamp == expected_end
        )
        if complete_group:
            count += 1
    return count


def indicators_ready(
    index: int,
    rsi: list[Decimal | None],
    atr: list[Decimal | None],
    htf: list[tuple[Decimal | None, Decimal | None]],
    swing_lookback: int,
) -> bool:
    htf_fast, htf_slow = htf[index]
    return (
        index >= swing_lookback - 1
        and rsi[index] is not None
        and atr[index] is not None
        and htf_fast is not None
        and htf_slow is not None
    )


def choose_long_stop(mode: str, atr_stop: Decimal, swing_stop: Decimal) -> Decimal:
    if mode == "ATR":
        return atr_stop
    if mode == "Swing":
        return swing_stop
    return min(atr_stop, swing_stop)


def choose_short_stop(mode: str, atr_stop: Decimal, swing_stop: Decimal) -> Decimal:
    if mode == "ATR":
        return atr_stop
    if mode == "Swing":
        return swing_stop
    return max(atr_stop, swing_stop)


def resolve_bracket_exit(
    candle: OhlcvCandle,
    position: OpenReplayPosition,
    *,
    tick_size: Decimal,
    slippage_ticks: int,
) -> ExitFill | None:
    if position.direction == Direction.LONG:
        if candle.open <= position.stop_loss:
            return adverse_stop_fill(candle.open, position, tick_size, slippage_ticks, "STOP_GAP")
        if position.take_profit is not None and candle.open >= position.take_profit:
            return ExitFill(position.take_profit, "TAKE_PROFIT_GAP", ZERO)
        stop_touched = candle.low <= position.stop_loss
        target_touched = (
            position.take_profit is not None and candle.high >= position.take_profit
        )
    else:
        if candle.open >= position.stop_loss:
            return adverse_stop_fill(candle.open, position, tick_size, slippage_ticks, "STOP_GAP")
        if position.take_profit is not None and candle.open <= position.take_profit:
            return ExitFill(position.take_profit, "TAKE_PROFIT_GAP", ZERO)
        stop_touched = candle.high >= position.stop_loss
        target_touched = (
            position.take_profit is not None and candle.low <= position.take_profit
        )
    if stop_touched:
        reason = "STOP_AND_TARGET_AMBIGUOUS" if target_touched else "STOP_LOSS"
        fill = adverse_stop_fill(
            position.stop_loss,
            position,
            tick_size,
            slippage_ticks,
            reason,
        )
        return ExitFill(fill.price, fill.reason, fill.slippage, target_touched)
    if target_touched and position.take_profit is not None:
        return ExitFill(position.take_profit, "TAKE_PROFIT", ZERO)
    return None


def adverse_stop_fill(
    trigger_price: Decimal,
    position: OpenReplayPosition,
    tick_size: Decimal,
    slippage_ticks: int,
    reason: str,
) -> ExitFill:
    slip = tick_size * slippage_ticks
    price = (
        trigger_price - slip
        if position.direction == Direction.LONG
        else trigger_price + slip
    )
    return ExitFill(
        price,
        reason,
        slip * position.quantity * position.point_value,
    )


def market_exit(
    price: Decimal,
    direction: Direction,
    *,
    tick_size: Decimal,
    slippage_ticks: int,
    reason: str,
    quantity: Decimal,
    point_value: Decimal,
) -> ExitFill:
    slip = tick_size * slippage_ticks
    filled = price - slip if direction == Direction.LONG else price + slip
    return ExitFill(filled, reason, slip * quantity * point_value)


def close_position(
    *,
    sequence: int,
    position: OpenReplayPosition,
    fill: ExitFill,
    closed_at: datetime,
    commission_percent: Decimal,
    equity: Decimal,
) -> ReferenceReplayTrade:
    direction_sign = Decimal("1") if position.direction == Direction.LONG else Decimal("-1")
    gross = (
        (fill.price - position.entry_price)
        * position.quantity
        * position.point_value
        * direction_sign
    )
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
    r_multiple = realized / position.initial_risk if position.initial_risk > 0 else ZERO
    return ReferenceReplayTrade(
        sequence=sequence,
        direction=position.direction,
        entry_at=position.entry_at,
        closed_at=closed_at,
        signal_price=position.signal_price,
        entry_price=position.entry_price,
        stop_loss=position.stop_loss,
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


def diagnostic_template(candle_count: int, start: datetime, end: datetime) -> dict:
    return {
        "candles_loaded": candle_count,
        "backtest_start": start.isoformat(),
        "backtest_end": end.isoformat(),
        "bars_in_window": 0,
        "flat_position_pass": 0,
        "long_trend_pass": 0,
        "short_trend_pass": 0,
        "pullback_pass": 0,
        "long_rsi_pass": 0,
        "short_rsi_pass": 0,
        "long_confirmation_pass": 0,
        "short_confirmation_pass": 0,
        "long_setups": 0,
        "short_setups": 0,
        "quantity_rejections": 0,
        "entry_bracket_rejections": 0,
        "intrabar_ambiguous_exits": 0,
        "exit_reasons": {},
    }


def volatility_breakout_diagnostic_template(
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
        "compression_pass": 0,
        "volume_pass": 0,
        "long_bias_pass": 0,
        "short_bias_pass": 0,
        "long_breakout_pass": 0,
        "short_breakout_pass": 0,
        "long_setups": 0,
        "short_setups": 0,
        "quantity_rejections": 0,
        "entry_bracket_rejections": 0,
        "intrabar_ambiguous_exits": 0,
        "exit_reasons": {},
    }


def slow_breakout_spot_diagnostic_template(
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
        "long_breakout_pass": 0,
        "long_setups": 0,
        "channel_exit_signals": 0,
        "quantity_rejections": 0,
        "intrabar_ambiguous_exits": 0,
        "exit_reasons": {},
    }


def position_snapshot(position: OpenReplayPosition | None) -> dict | None:
    if position is None:
        return None
    return {
        "direction": position.direction.value,
        "entry_at": position.entry_at.isoformat(),
        "entry_price": decimal_string(position.entry_price),
        "stop_loss": decimal_string(position.stop_loss),
        "take_profit": (
            decimal_string(position.take_profit)
            if position.take_profit is not None
            else None
        ),
        "quantity": decimal_string(position.quantity),
    }


def decimal_string(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")
