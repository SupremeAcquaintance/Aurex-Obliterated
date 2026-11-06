import csv
import io
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from random import Random
from typing import Any
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from aurex.backtest_engine.datasets import normalize_timeframe
from aurex.backtest_engine.schemas import (
    AcceptanceCriteria,
    BacktestProtocolCreate,
    BacktestReportCreate,
    BacktestReportCsvPreflightResponse,
    BacktestReportCsvRequest,
    BacktestTradeInput,
    OhlcvCandle,
    WalkForwardPlanRequest,
    WalkForwardPlanResponse,
    WalkForwardWindowInput,
)
from aurex.db.base import utc_now
from aurex.db.models import BacktestProtocol, BacktestResult, BacktestRun, BacktestTrade
from aurex.domain.enums import BacktestStatus, Direction, MarketRegime
from aurex.observability.system_events import SystemEventRecorder
from aurex.strategy_engine.registry import REGISTERED_STRATEGIES

ZERO = Decimal("0")
EXPLICIT_WALK_FORWARD_METHOD = "explicit_anchored_fixed_parameter"
DIAGNOSTIC_WALK_FORWARD_METHOD = "chronological_trade_slices"
BACKTEST_REPORT_REQUIRED_HEADERS = ["realized_pl", "closed_at", "market_regime"]
TRADINGVIEW_REQUIRED_FIELDS = ["trade_number", "type", "date_time", "net_pl"]
TRADINGVIEW_TRADE_NUMBER_HEADERS = (
    "trade_number",
    "trade_no",
    "trade",
)
TRADINGVIEW_TYPE_HEADERS = ("type", "order_type")
TRADINGVIEW_SIGNAL_HEADERS = ("signal", "order", "order_name", "signal_name")
TRADINGVIEW_DATETIME_HEADERS = (
    "date_time",
    "datetime",
    "exit_time",
    "closing_time",
    "time",
)
TRADINGVIEW_ENTRY_DATETIME_HEADERS = ("entry_time", "entry_date_time")
TRADINGVIEW_PRICE_HEADERS = ("price", "price_usd", "exit_price")
TRADINGVIEW_ENTRY_PRICE_HEADERS = ("entry_price", "entry_price_usd")
TRADINGVIEW_QUANTITY_HEADERS = (
    "contracts",
    "position_size_qty",
    "position_size",
    "quantity",
    "qty",
)
TRADINGVIEW_NET_PL_HEADERS = (
    "net_p_l_usd",
    "net_p_l",
    "net_profit_usd",
    "net_profit",
    "profit_usd",
    "profit",
    "p_l_usd",
    "p_l",
)
TRADINGVIEW_GROSS_PL_HEADERS = ("gross_p_l_usd", "gross_p_l", "gross_profit")
TRADINGVIEW_FEES_HEADERS = (
    "commission_usd",
    "commission",
    "fees_usd",
    "fees",
    "commission_paid",
)
TRADINGVIEW_SLIPPAGE_HEADERS = ("slippage_usd", "slippage")
TRADINGVIEW_EQUITY_HEADERS = (
    "cumulative_p_l_usd",
    "cumulative_p_l",
    "cum_profit_usd",
    "cum_profit",
    "equity",
)
TRADINGVIEW_SYMBOL_HEADERS = ("symbol", "ticker")
TRADINGVIEW_VENUE_PATTERN = re.compile(r"^[A-Z0-9_]+$")
TRADINGVIEW_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9._-]+$")
TREND_PULLBACK_V1_PARAMETER_TEMPLATE = {
    "initial_capital": "1000",
    "backtest_start": "2026-01-01T00:00:00Z",
    "backtest_end": "2026-03-31T00:00:00Z",
    "higher_timeframe": "60",
    "pullback_ema_fast": 20,
    "pullback_ema_slow": 50,
    "trend_ema": 200,
    "htf_ema_fast": 50,
    "htf_ema_slow": 200,
    "rsi_length": 14,
    "atr_length": 14,
    "atr_multiplier": "1.5",
    "reward_risk": "2.0",
    "swing_lookback": 5,
    "pullback_atr_tolerance": "0.25",
    "stop_mode": "Wider",
    "risk_per_trade_percent": "0.5",
    "max_position_value_percent": "95.0",
    "enable_long": True,
    "enable_short": True,
}
VOLATILITY_BREAKOUT_V1_PARAMETER_TEMPLATE = {
    "initial_capital": "1000",
    "backtest_start": "2023-02-01T00:00:00Z",
    "backtest_end": "2026-07-01T00:00:00Z",
    "higher_timeframe": "60",
    "htf_ema_fast": 50,
    "htf_ema_slow": 200,
    "breakout_lookback": 20,
    "compression_lookback": 40,
    "atr_length": 14,
    "atr_stop_multiplier": "1.8",
    "reward_risk": "2.0",
    "volume_length": 20,
    "volume_expansion": "1.15",
    "risk_per_trade_percent": "0.3",
    "max_position_value_percent": "95.0",
    "enable_long": True,
    "enable_short": True,
}
SLOW_BREAKOUT_SPOT_V1_PARAMETER_TEMPLATE = {
    "initial_capital": "1000",
    "backtest_start": "2023-02-01T00:00:00Z",
    "backtest_end": "2026-07-01T00:00:00Z",
    "entry_channel_length": 55,
    "exit_channel_length": 20,
    "atr_length": 20,
    "atr_stop_multiplier": "3.0",
    "risk_per_trade_percent": "0.25",
    "max_position_value_percent": "50.0",
    "enable_long": True,
}
JAM_REVERSAL_V1_PARAMETER_TEMPLATE = {
    "initial_capital": "1000",
    "backtest_start": "2024-01-01T00:00:00Z",
    "backtest_end": "2026-12-31T23:59:00Z",
    "direction_mode": "Both",
    "higher_timeframe": "60",
    "higher_timeframe_valid": True,
    "htf_ema_fast": 50,
    "htf_ema_slow": 200,
    "trend_ema": 200,
    "pullback_ema": 20,
    "use_higher_timeframe_bias": True,
    "use_current_trend_filter": False,
    "context_mode": "Hybrid",
    "impulse_lookback": 6,
    "block_strong_counter_trend": True,
    "counter_trend_adx": "22.0",
    "atr_length": 14,
    "adx_length": 14,
    "adx_smoothing": 14,
    "reclaim_mode": "Body",
    "require_sweep": True,
    "entry_style": "Breakout confirm",
    "confirm_window_bars": 8,
    "confirm_atr_buffer": "0.02",
    "max_confirm_distance_atr": "1.10",
    "max_confirm_range_atr": "2.20",
    "min_confirm_close_position": "0.95",
    "cancel_pending_on_midpoint_failure": True,
    "sweep_atr_buffer": "0.00",
    "reclaim_atr_buffer": "0.02",
    "min_seed_body_ratio": "0.45",
    "min_jam_body_ratio": "0.50",
    "min_jam_body_expansion": "1.05",
    "min_seed_range_atr": "0.25",
    "min_jam_range_atr": "0.45",
    "max_jam_range_atr": "2.80",
    "use_volume_filter": True,
    "volume_length": 20,
    "volume_expansion": "1.20",
    "use_timeframe_adaptive_confirmation": True,
    "stop_mode": "Tighter",
    "stop_atr_buffer": "0.15",
    "atr_stop_multiplier": "1.4",
    "target_mode": "ATR capped R",
    "reward_risk": "2.20",
    "max_target_atr": "2.50",
    "use_cost_aware_filter": True,
    "estimated_commission_percent": "0.05",
    "min_target_distance_atr": "0.65",
    "min_net_reward_risk": "0.80",
    "use_breakeven_stop": True,
    "breakeven_at_r": "0.90",
    "breakeven_offset_ticks": 2,
    "use_atr_trail": True,
    "trail_start_r": "1.20",
    "trail_atr_multiplier": "1.10",
    "use_midpoint_failure_exit": True,
    "use_pullback_failure_exit": True,
    "max_bars_in_trade": 80,
    "risk_per_trade_percent": "0.5",
    "max_position_value_percent": "95.0",
    "trade_cooldown_bars": 6,
    "allowed_symbol_mode": "BTCUSDT only",
    "allowed_timeframe_mode": "15m/30m only",
    "enable_long": True,
    "enable_short": True,
}
JAM_REVERSAL_SPOT_V1_PARAMETER_TEMPLATE = {
    **JAM_REVERSAL_V1_PARAMETER_TEMPLATE,
    "initial_capital": "100",
    "backtest_start": "2023-02-01T00:00:00Z",
    "backtest_end": "2026-01-01T00:00:00Z",
    "direction_mode": "Long only",
    "estimated_commission_percent": "0.10",
    "allowed_timeframe_mode": "15m only",
    "enable_short": False,
}
KNOWN_STRATEGY_REQUIRED_PARAMETERS = {
    "trend_pullback_v1": tuple(TREND_PULLBACK_V1_PARAMETER_TEMPLATE),
    "volatility_breakout_v1": tuple(VOLATILITY_BREAKOUT_V1_PARAMETER_TEMPLATE),
    "slow_breakout_spot_v1": tuple(SLOW_BREAKOUT_SPOT_V1_PARAMETER_TEMPLATE),
    "jam_reversal_v1": tuple(JAM_REVERSAL_V1_PARAMETER_TEMPLATE),
    "jam_reversal_spot_v1": tuple(JAM_REVERSAL_SPOT_V1_PARAMETER_TEMPLATE),
}
KNOWN_STRATEGY_PARAMETER_TEMPLATES = {
    "trend_pullback_v1": TREND_PULLBACK_V1_PARAMETER_TEMPLATE,
    "volatility_breakout_v1": VOLATILITY_BREAKOUT_V1_PARAMETER_TEMPLATE,
    "slow_breakout_spot_v1": SLOW_BREAKOUT_SPOT_V1_PARAMETER_TEMPLATE,
    "jam_reversal_v1": JAM_REVERSAL_V1_PARAMETER_TEMPLATE,
    "jam_reversal_spot_v1": JAM_REVERSAL_SPOT_V1_PARAMETER_TEMPLATE,
}
DEFAULT_BACKTEST_COST_MODELS = {
    "trend_pullback_v1": {"commission_percent": "0.05"},
    "volatility_breakout_v1": {"commission_percent": "0.05"},
    "slow_breakout_spot_v1": {"commission_percent": "0.05"},
    "range_mean_reversion_v1": {"commission_percent": "0.05"},
    "jam_reversal_v1": {"commission_percent": "0.05"},
    "jam_reversal_spot_v1": {"commission_percent": "0.10"},
}
DEFAULT_BACKTEST_SLIPPAGE_MODELS = {
    "trend_pullback_v1": {"type": "fixed_ticks", "ticks": "2"},
    "volatility_breakout_v1": {"type": "fixed_ticks", "ticks": "2"},
    "slow_breakout_spot_v1": {"type": "fixed_ticks", "ticks": "2"},
    "range_mean_reversion_v1": {"type": "operator_declared", "source": "TradingView export"},
    "jam_reversal_v1": {"type": "fixed_ticks", "ticks": "2"},
    "jam_reversal_spot_v1": {"type": "fixed_ticks", "ticks": "2"},
}
AUREX_ROOT = Path(__file__).resolve().parents[3]
PINE_STRATEGY_VERSION_PATTERN = re.compile(
    r'^\s*strategyVersion\s*=\s*"([^"]+)"',
    re.MULTILINE,
)


@dataclass(frozen=True)
class BacktestMetrics:
    total_trades: int
    wins: int
    losses: int
    breakeven: int
    win_rate: Decimal
    average_win: Decimal
    average_loss: Decimal
    expectancy: Decimal
    profit_factor: Decimal | None
    max_drawdown: Decimal
    total_net_pl: Decimal
    equity_curve: list[dict[str, str]]


@dataclass(frozen=True)
class BacktestSegments:
    in_sample: BacktestMetrics | None
    out_of_sample: BacktestMetrics | None
    holdout: BacktestMetrics | None
    walk_forward: dict[str, object] | None = None


@dataclass(frozen=True)
class BacktestReportCsvPreflight:
    report_payload: BacktestReportCreate
    response: BacktestReportCsvPreflightResponse


class BacktestLab:
    def __init__(self, session: Session) -> None:
        self.session = session

    def register_protocol(self, payload: BacktestProtocolCreate) -> BacktestProtocol:
        validate_backtest_protocol(payload)
        snapshot = build_backtest_protocol_snapshot(payload)
        protocol_hash = build_backtest_protocol_hash(snapshot)
        existing = self.session.execute(
            select(BacktestProtocol)
            .where(BacktestProtocol.protocol_hash == protocol_hash)
            .order_by(BacktestProtocol.registered_at.desc())
        ).scalars()
        for protocol in existing:
            if protocol.backtest_run is None:
                return protocol

        now = utc_now()
        protocol = BacktestProtocol(
            strategy=payload.strategy,
            strategy_version=payload.strategy_version,
            symbols=normalized_symbols(payload.symbols),
            timeframe=payload.timeframe,
            protocol_hash=protocol_hash,
            protocol_snapshot=snapshot,
            registered_at=now,
            created_at=now,
            updated_at=now,
        )
        self.session.add(protocol)
        self.session.flush()
        SystemEventRecorder(self.session).info(
            "backtest_lab",
            "Backtest protocol registered",
            {
                "backtest_protocol_id": protocol.id,
                "strategy": protocol.strategy,
                "strategy_version": protocol.strategy_version,
                "protocol_hash": protocol.protocol_hash,
                "immutable": True,
            },
            occurred_at=now,
        )
        return protocol

    def list_protocols(self, limit: int = 100) -> list[BacktestProtocol]:
        return list(
            self.session.execute(
                select(BacktestProtocol)
                .order_by(BacktestProtocol.registered_at.desc())
                .limit(limit)
            ).scalars()
        )

    def get_protocol(self, protocol_id: str) -> BacktestProtocol | None:
        return self.session.get(BacktestProtocol, protocol_id)

    def run_manifest(self, protocol: BacktestProtocol) -> dict[str, object]:
        return build_backtest_run_manifest(protocol)

    def tradingview_run_package(self, protocol: BacktestProtocol) -> dict[str, object]:
        return build_tradingview_run_package(protocol)

    def audit_protocol(self, payload: BacktestReportCreate) -> dict[str, object]:
        if not payload.protocol_id:
            return backtest_protocol_audit_snapshot(
                protocol_id=None,
                protocol_hash=None,
                registered_at=None,
                reasons=["backtest_protocol_missing"],
            )
        protocol = self.get_protocol(payload.protocol_id)
        if protocol is None:
            return backtest_protocol_audit_snapshot(
                protocol_id=payload.protocol_id,
                protocol_hash=None,
                registered_at=None,
                reasons=["backtest_protocol_not_found"],
            )

        reasons: list[str] = []
        current_hash = build_backtest_protocol_hash(protocol.protocol_snapshot)
        submitted_hash = build_backtest_protocol_hash(
            build_backtest_protocol_snapshot(payload)
        )
        if current_hash != protocol.protocol_hash:
            reasons.append("backtest_protocol_integrity_mismatch")
        if submitted_hash != protocol.protocol_hash:
            reasons.append("backtest_report_does_not_match_protocol")
        if protocol.backtest_run is not None:
            reasons.append("backtest_protocol_already_consumed")
        return backtest_protocol_audit_snapshot(
            protocol_id=protocol.id,
            protocol_hash=protocol.protocol_hash,
            registered_at=protocol.registered_at,
            reasons=reasons,
        )

    def create_report(self, payload: BacktestReportCreate) -> BacktestRun:
        payload = normalize_report_trade_evidence(payload)
        protocol_audit = self.audit_protocol(payload)
        config_hash = build_config_hash(payload)
        evidence_hash = build_trade_evidence_hash(payload.trades)
        metrics = calculate_backtest_metrics(payload.trades)
        segments = calculate_backtest_segments(payload)
        acceptance_passed, acceptance_reasons = evaluate_acceptance(
            metrics,
            payload.acceptance_criteria,
            payload,
            segments,
        )
        acceptance_passed, acceptance_reasons = apply_protocol_acceptance(
            acceptance_passed,
            acceptance_reasons,
            protocol_audit,
        )
        now = utc_now()

        matched_protocol = protocol_audit.get("status") == "MATCHED"
        run = BacktestRun(
            protocol_id=payload.protocol_id if matched_protocol else None,
            protocol_evidence_hash=(
                str(protocol_audit["protocol_hash"])
                if matched_protocol and protocol_audit.get("protocol_hash")
                else None
            ),
            strategy=payload.strategy,
            strategy_version=payload.strategy_version,
            symbols=payload.symbols,
            timeframe=payload.timeframe,
            status=BacktestStatus.COMPLETED,
            data_source=payload.data_source,
            source_format=payload.source_format,
            source_artifact_hash=payload.source_artifact_hash,
            source_reference=payload.source_reference,
            evidence_hash=evidence_hash,
            data_start=ensure_utc(payload.data_start),
            data_end=ensure_utc(payload.data_end),
            in_sample_start=ensure_optional_utc(payload.in_sample_start),
            in_sample_end=ensure_optional_utc(payload.in_sample_end),
            out_of_sample_start=ensure_optional_utc(payload.out_of_sample_start),
            out_of_sample_end=ensure_optional_utc(payload.out_of_sample_end),
            config_hash=config_hash,
            parameters=payload.parameters,
            cost_model=payload.cost_model,
            slippage_model=payload.slippage_model,
            risk_snapshot=payload.risk_snapshot,
            created_at=now,
            updated_at=now,
        )
        self.session.add(run)
        self.session.flush()

        for sequence, trade in enumerate(payload.trades, start=1):
            self.session.add(
                persisted_backtest_trade(
                    run,
                    trade,
                    sequence=trade.sequence or sequence,
                )
            )

        metrics_snapshot = build_metrics_snapshot(payload, metrics, segments)
        metrics_snapshot["backtest_protocol"] = protocol_audit
        result = BacktestResult(
            backtest_run=run,
            total_trades=metrics.total_trades,
            wins=metrics.wins,
            losses=metrics.losses,
            breakeven=metrics.breakeven,
            win_rate=metrics.win_rate,
            average_win=metrics.average_win,
            average_loss=metrics.average_loss,
            expectancy=metrics.expectancy,
            profit_factor=metrics.profit_factor,
            max_drawdown=metrics.max_drawdown,
            total_net_pl=metrics.total_net_pl,
            metrics_snapshot=metrics_snapshot,
            acceptance_passed=acceptance_passed,
            acceptance_reasons=acceptance_reasons,
            acceptance_snapshot=payload.acceptance_criteria.model_dump(mode="json"),
        )
        self.session.add(result)
        SystemEventRecorder(self.session).info(
            "backtest_lab",
            "Backtest report stored",
            {
                "backtest_run_id": run.id,
                "strategy": run.strategy,
                "strategy_version": run.strategy_version,
                "config_hash": run.config_hash,
                "evidence_hash": run.evidence_hash,
                "source_format": run.source_format,
                "backtest_protocol_id": run.protocol_id,
                "protocol_evidence_hash": run.protocol_evidence_hash,
                "acceptance_passed": acceptance_passed,
            },
            occurred_at=now,
        )
        self.session.flush()
        return run

    def list_runs(self, limit: int = 100) -> list[BacktestRun]:
        return list(
            self.session.execute(
                select(BacktestRun).order_by(BacktestRun.created_at.desc()).limit(limit)
            ).scalars()
        )

    def get_run(self, run_id: str) -> BacktestRun | None:
        return self.session.get(BacktestRun, run_id)

    def list_run_trades(
        self,
        run_id: str,
        *,
        limit: int = 500,
        offset: int = 0,
    ) -> list[BacktestTrade]:
        return list(
            self.session.execute(
                select(BacktestTrade)
                .where(BacktestTrade.backtest_run_id == run_id)
                .order_by(BacktestTrade.sequence.asc())
                .offset(offset)
                .limit(limit)
            ).scalars()
        )

    def export_report_csv(self, run: BacktestRun) -> str:
        if run.result is None:
            raise ValueError("Backtest run has no result")

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["field", "value"])
        writer.writerow(["backtest_run_id", run.id])
        writer.writerow(["strategy", run.strategy])
        writer.writerow(["strategy_version", run.strategy_version])
        writer.writerow(["config_hash", run.config_hash])
        writer.writerow(["symbols", ",".join(run.symbols or [])])
        writer.writerow(["timeframe", run.timeframe or ""])
        writer.writerow(["data_source", run.data_source])
        writer.writerow(["total_trades", run.result.total_trades])
        writer.writerow(["wins", run.result.wins])
        writer.writerow(["losses", run.result.losses])
        writer.writerow(["breakeven", run.result.breakeven])
        writer.writerow(["win_rate", run.result.win_rate])
        writer.writerow(["average_win", run.result.average_win])
        writer.writerow(["average_loss", run.result.average_loss])
        writer.writerow(["expectancy", run.result.expectancy])
        writer.writerow(["profit_factor", run.result.profit_factor])
        writer.writerow(["max_drawdown", run.result.max_drawdown])
        writer.writerow(["total_net_pl", run.result.total_net_pl])
        writer.writerow(["acceptance_passed", run.result.acceptance_passed])
        writer.writerow(["acceptance_reasons", "|".join(run.result.acceptance_reasons or [])])
        return output.getvalue()

    def preflight_report_csv(
        self,
        payload: BacktestReportCsvRequest,
    ) -> BacktestReportCsvPreflight:
        report_payload, row_results, source_format = report_payload_from_csv_request(
            payload
        )
        protocol_audit = self.audit_protocol(report_payload)
        rejected_count = sum(1 for item in row_results if item["status"] == "REJECTED")
        metrics = calculate_backtest_metrics(report_payload.trades)
        segments = calculate_backtest_segments(report_payload)
        acceptance_passed, acceptance_reasons = evaluate_acceptance(
            metrics,
            report_payload.acceptance_criteria,
            report_payload,
            segments,
        )
        acceptance_passed, acceptance_reasons = apply_protocol_acceptance(
            acceptance_passed,
            acceptance_reasons,
            protocol_audit,
        )
        response = BacktestReportCsvPreflightResponse(
            status=(
                "READY"
                if rejected_count == 0 and len(report_payload.trades) > 0
                else "REJECTED"
            ),
            source_format=source_format,
            source_artifact_hash=report_payload.source_artifact_hash or "",
            evidence_hash=build_trade_evidence_hash(report_payload.trades),
            rows_received=len(row_results),
            importable_count=len(report_payload.trades),
            rejected_count=rejected_count,
            required_headers=(
                BACKTEST_REPORT_REQUIRED_HEADERS
                if source_format == "aurex_csv"
                else TRADINGVIEW_REQUIRED_FIELDS
            ),
            row_results=row_results,
            analysis_summary=backtest_report_csv_analysis_summary(
                report_payload,
                row_results,
                metrics,
                segments,
                acceptance_passed,
                acceptance_reasons,
                protocol_audit,
            ),
            checked_at=utc_now(),
        )
        return BacktestReportCsvPreflight(report_payload=report_payload, response=response)

    def create_report_from_csv(self, payload: BacktestReportCsvRequest) -> BacktestRun:
        preflight = self.preflight_report_csv(payload)
        if preflight.response.status != "READY":
            raise ValueError("Backtest report CSV must be READY before import")
        return self.create_report(preflight.report_payload)

    def strategy_setup(
        self,
        *,
        strategy: str,
        symbol: str,
        timeframe: str,
        venue: str = "BINANCE",
    ) -> dict[str, object]:
        return backtest_strategy_setup(
            strategy=strategy,
            symbol=symbol,
            timeframe=timeframe,
            venue=venue,
        )


def validate_backtest_protocol(payload: BacktestProtocolCreate) -> None:
    report_payload = backtest_report_payload_from_protocol(payload)
    reasons: list[str] = []
    if ensure_utc(payload.data_start) >= ensure_utc(payload.data_end):
        reasons.append("Backtest data start must be before data end")
    reasons.extend(sample_window_reasons(report_payload))
    reasons.extend(
        universal_acceptance_configuration_reasons(
            payload.acceptance_criteria,
            report_payload,
        )
    )
    reasons.extend(strategy_parameter_acceptance_reasons(report_payload))
    source_evidence = strategy_source_evidence(
        payload.strategy,
        payload.strategy_version,
    )
    if source_evidence["known_strategy"] and not source_evidence["ready"]:
        reasons.extend(
            f"Strategy source evidence blocked: {reason}"
            for reason in source_evidence["reasons"]
        )
    if not payload.cost_model:
        reasons.append("Backtest protocol requires a cost model")
    if not payload.slippage_model:
        reasons.append("Backtest protocol requires a slippage model")
    if not payload.risk_snapshot:
        reasons.append("Backtest protocol requires a risk snapshot")
    if payload.data_source == "tradingview-export":
        reference = parse_tradingview_source_reference(payload.source_reference)
        expected_symbols = normalized_symbols(payload.symbols)
        if reference is None:
            reasons.append(
                "TradingView source reference must bind venue, symbol, and timeframe as "
                "tradingview://strategy-tester/<VENUE>:<SYMBOL>/<timeframe>"
            )
        else:
            if len(expected_symbols) != 1 or reference["symbol"] != expected_symbols[0]:
                reasons.append("TradingView source reference symbol must match protocol symbol")
            try:
                expected_timeframe, _ = normalize_timeframe(payload.timeframe)
                reference_timeframe, _ = normalize_timeframe(reference["timeframe"])
            except ValueError:
                reasons.append("TradingView source reference timeframe is invalid")
            else:
                if reference_timeframe != expected_timeframe:
                    reasons.append(
                        "TradingView source reference timeframe must match protocol timeframe"
                    )
    if payload.acceptance_criteria.require_walk_forward_validation:
        snapshot = calculate_walk_forward_snapshot(report_payload)
        if snapshot.get("method") != EXPLICIT_WALK_FORWARD_METHOD:
            reasons.append("Backtest protocol requires explicit walk-forward windows")
        invalid_count = int(snapshot.get("invalid_window_count") or 0)
        valid_count = int(snapshot.get("valid_window_count") or 0)
        if invalid_count:
            reasons.append(
                f"Backtest protocol contains {invalid_count} invalid walk-forward window(s)"
            )
        if valid_count < payload.acceptance_criteria.min_walk_forward_windows:
            reasons.append(
                "Backtest protocol valid walk-forward windows "
                f"{valid_count} below minimum "
                f"{payload.acceptance_criteria.min_walk_forward_windows}"
            )
    if reasons:
        raise ValueError("; ".join(dict.fromkeys(reasons)))


def backtest_report_payload_from_protocol(
    payload: BacktestProtocolCreate,
) -> BacktestReportCreate:
    return BacktestReportCreate(
        strategy=payload.strategy,
        strategy_version=payload.strategy_version,
        symbols=normalized_symbols(payload.symbols),
        timeframe=payload.timeframe,
        data_source=payload.data_source,
        csv_timezone=payload.csv_timezone,
        source_reference=payload.source_reference,
        data_start=payload.data_start,
        data_end=payload.data_end,
        in_sample_start=payload.in_sample_start,
        in_sample_end=payload.in_sample_end,
        out_of_sample_start=payload.out_of_sample_start,
        out_of_sample_end=payload.out_of_sample_end,
        holdout_start=payload.holdout_start,
        holdout_end=payload.holdout_end,
        tested_variant_count=payload.tested_variant_count,
        variant_registry_hash=payload.variant_registry_hash,
        parameters=payload.parameters,
        cost_model=payload.cost_model,
        slippage_model=payload.slippage_model,
        risk_snapshot=payload.risk_snapshot,
        walk_forward_windows=payload.walk_forward_windows,
        acceptance_criteria=payload.acceptance_criteria,
        trades=[],
    )


def build_backtest_protocol_snapshot(
    payload: BacktestProtocolCreate | BacktestReportCreate,
) -> dict[str, object]:
    return {
        "strategy": payload.strategy.strip(),
        "strategy_version": payload.strategy_version.strip(),
        "strategy_source_evidence": strategy_source_evidence(
            payload.strategy.strip(),
            payload.strategy_version.strip(),
        ),
        "symbols": normalized_symbols(payload.symbols),
        "timeframe": payload.timeframe.strip(),
        "data_source": payload.data_source.strip(),
        "csv_timezone": payload.csv_timezone.strip(),
        "source_reference": (
            payload.source_reference.strip() if payload.source_reference else None
        ),
        "data_start": ensure_utc(payload.data_start).isoformat(),
        "data_end": ensure_utc(payload.data_end).isoformat(),
        "in_sample_start": optional_iso(payload.in_sample_start),
        "in_sample_end": optional_iso(payload.in_sample_end),
        "out_of_sample_start": optional_iso(payload.out_of_sample_start),
        "out_of_sample_end": optional_iso(payload.out_of_sample_end),
        "holdout_start": optional_iso(payload.holdout_start),
        "holdout_end": optional_iso(payload.holdout_end),
        "tested_variant_count": payload.tested_variant_count,
        "variant_registry_hash": payload.variant_registry_hash,
        "parameters": payload.parameters,
        "cost_model": payload.cost_model,
        "slippage_model": payload.slippage_model,
        "risk_snapshot": payload.risk_snapshot,
        "walk_forward_windows": [
            {
                "window_id": window.window_id,
                "train_start": ensure_utc(window.train_start).isoformat(),
                "train_end": ensure_utc(window.train_end).isoformat(),
                "test_start": ensure_utc(window.test_start).isoformat(),
                "test_end": ensure_utc(window.test_end).isoformat(),
                "configuration_reference": window.configuration_reference,
                "parameters": window.parameters,
            }
            for window in payload.walk_forward_windows
        ],
        "acceptance_criteria": payload.acceptance_criteria.model_dump(mode="json"),
    }


def build_backtest_protocol_hash(snapshot: dict) -> str:
    serialized = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(serialized.encode("utf-8")).hexdigest()


def strategy_source_evidence(
    strategy: str,
    declared_version: str,
) -> dict[str, object]:
    normalized_strategy = strategy.strip()
    normalized_version = declared_version.strip()
    definition = REGISTERED_STRATEGIES.get(normalized_strategy)
    if definition is None:
        return {
            "known_strategy": False,
            "strategy": normalized_strategy,
            "declared_version": normalized_version,
            "registry_version": None,
            "pine_version": None,
            "pine_path": None,
            "pine_source_sha256": None,
            "ready": True,
            "reasons": [],
        }

    pine_path = (AUREX_ROOT / definition.pine_path).resolve()
    reasons: list[str] = []
    source_hash: str | None = None
    pine_version: str | None = None
    try:
        pine_path.relative_to(AUREX_ROOT)
    except ValueError:
        reasons.append("pine_path_outside_repository")
    else:
        if not pine_path.is_file():
            reasons.append("pine_source_missing")
        else:
            source_bytes = pine_path.read_bytes()
            source_hash = sha256(source_bytes).hexdigest()
            try:
                source = source_bytes.decode("utf-8")
            except UnicodeDecodeError:
                reasons.append("pine_source_not_utf8")
            else:
                version_match = PINE_STRATEGY_VERSION_PATTERN.search(source)
                if version_match is None:
                    reasons.append("pine_strategy_version_missing")
                else:
                    pine_version = version_match.group(1).strip()

    if normalized_version != definition.version:
        reasons.append("declared_strategy_version_not_current")
    if pine_version is not None and pine_version != definition.version:
        reasons.append("pine_strategy_version_registry_mismatch")
    if pine_version is not None and pine_version != normalized_version:
        reasons.append("pine_strategy_version_declared_mismatch")

    return {
        "known_strategy": True,
        "strategy": normalized_strategy,
        "declared_version": normalized_version,
        "registry_version": definition.version,
        "pine_version": pine_version,
        "pine_path": definition.pine_path,
        "pine_source_sha256": source_hash,
        "ready": not reasons,
        "reasons": list(dict.fromkeys(reasons)),
    }


def parse_tradingview_source_reference(value: str | None) -> dict[str, str] | None:
    candidate = str(value or "").strip()
    parsed = urlparse(candidate)
    parts = [part for part in parsed.path.split("/") if part]
    if (
        parsed.scheme != "tradingview"
        or parsed.netloc != "strategy-tester"
        or parsed.params
        or parsed.query
        or parsed.fragment
        or len(parts) != 2
    ):
        return None
    ticker_id = parts[0].strip().upper()
    timeframe = parts[1].strip()
    if ticker_id.count(":") != 1 or not timeframe:
        return None
    venue, symbol = ticker_id.split(":", 1)
    if (
        TRADINGVIEW_VENUE_PATTERN.fullmatch(venue) is None
        or TRADINGVIEW_SYMBOL_PATTERN.fullmatch(symbol) is None
    ):
        return None
    try:
        normalized_timeframe, _ = normalize_timeframe(timeframe)
    except ValueError:
        return None
    return {
        "venue": venue,
        "symbol": symbol,
        "ticker_id": f"{venue}:{symbol}",
        "timeframe": normalized_timeframe,
    }


def build_backtest_run_manifest(protocol: BacktestProtocol) -> dict[str, object]:
    snapshot = protocol.protocol_snapshot or {}
    symbols = [str(symbol).upper() for symbol in snapshot.get("symbols") or []]
    parameters = snapshot.get("parameters") if isinstance(snapshot.get("parameters"), dict) else {}
    recorded_source = snapshot.get("strategy_source_evidence")
    current_source = strategy_source_evidence(protocol.strategy, protocol.strategy_version)
    checks: list[dict[str, object]] = []

    def check(code: str, passed: bool, *, expected: object, actual: object) -> None:
        checks.append(
            {
                "code": code,
                "passed": passed,
                "expected": expected,
                "actual": actual,
            }
        )

    current_protocol_hash = build_backtest_protocol_hash(snapshot)
    check(
        "protocol_integrity",
        current_protocol_hash == protocol.protocol_hash,
        expected=protocol.protocol_hash,
        actual=current_protocol_hash,
    )
    check(
        "protocol_unconsumed",
        protocol.backtest_run is None,
        expected="REGISTERED",
        actual="CONSUMED" if protocol.backtest_run is not None else "REGISTERED",
    )
    check(
        "single_tradingview_symbol",
        len(symbols) == 1,
        expected=1,
        actual=len(symbols),
    )
    check(
        "tradingview_data_source",
        snapshot.get("data_source") == "tradingview-export",
        expected="tradingview-export",
        actual=snapshot.get("data_source"),
    )
    source_reference = str(snapshot.get("source_reference") or "")
    parsed_source_reference = parse_tradingview_source_reference(source_reference)
    check(
        "tradingview_source_reference",
        parsed_source_reference is not None,
        expected="tradingview://strategy-tester/<VENUE>:<SYMBOL>/<timeframe>",
        actual=source_reference,
    )
    check(
        "tradingview_reference_symbol",
        parsed_source_reference is not None
        and len(symbols) == 1
        and parsed_source_reference["symbol"] == symbols[0],
        expected=symbols[0] if len(symbols) == 1 else None,
        actual=(parsed_source_reference or {}).get("symbol"),
    )
    try:
        normalized_protocol_timeframe, _ = normalize_timeframe(protocol.timeframe)
    except ValueError:
        normalized_protocol_timeframe = None
    check(
        "tradingview_reference_timeframe",
        parsed_source_reference is not None
        and normalized_protocol_timeframe is not None
        and parsed_source_reference["timeframe"] == normalized_protocol_timeframe,
        expected=normalized_protocol_timeframe,
        actual=(parsed_source_reference or {}).get("timeframe"),
    )
    check(
        "pine_source_recorded",
        isinstance(recorded_source, dict),
        expected="immutable strategy_source_evidence",
        actual=recorded_source,
    )
    recorded_hash = (
        recorded_source.get("pine_source_sha256")
        if isinstance(recorded_source, dict)
        else None
    )
    check(
        "pine_source_current",
        bool(recorded_hash)
        and recorded_hash == current_source.get("pine_source_sha256")
        and bool(current_source.get("ready")),
        expected=recorded_hash,
        actual=current_source.get("pine_source_sha256"),
    )
    expected_cost = DEFAULT_BACKTEST_COST_MODELS.get(protocol.strategy, {})
    expected_slippage = DEFAULT_BACKTEST_SLIPPAGE_MODELS.get(protocol.strategy, {})
    check(
        "cost_model",
        snapshot.get("cost_model") == expected_cost,
        expected=expected_cost,
        actual=snapshot.get("cost_model"),
    )
    check(
        "slippage_model",
        snapshot.get("slippage_model") == expected_slippage,
        expected=expected_slippage,
        actual=snapshot.get("slippage_model"),
    )
    settings_fingerprint = strategy_parameter_fingerprint(protocol.strategy, parameters)
    check(
        "settings_fingerprint",
        settings_fingerprint is not None,
        expected="complete frozen strategy parameters",
        actual=settings_fingerprint,
    )

    timeframe_reason: str | None = None
    try:
        _, chart_seconds = normalize_timeframe(protocol.timeframe)
        _, higher_seconds = normalize_timeframe(str(parameters.get("higher_timeframe") or ""))
        if higher_seconds <= chart_seconds:
            timeframe_reason = "higher_timeframe_not_above_chart_timeframe"
    except ValueError:
        timeframe_reason = "strategy_timeframe_invalid"
    check(
        "higher_timeframe",
        timeframe_reason is None,
        expected="higher timeframe greater than chart timeframe",
        actual=parameters.get("higher_timeframe"),
    )

    reasons = [str(item["code"]) for item in checks if not item["passed"]]
    if timeframe_reason is not None:
        reasons.append(timeframe_reason)
    reasons.extend(str(reason) for reason in current_source.get("reasons") or [])
    reasons = list(dict.fromkeys(reasons))
    protocol_status = "CONSUMED" if protocol.backtest_run is not None else "REGISTERED"
    symbol = symbols[0] if len(symbols) == 1 else None
    tradingview_setup = {
        "chart": {
            "symbol": symbol,
            "venue": (parsed_source_reference or {}).get("venue"),
            "ticker_id": (parsed_source_reference or {}).get("ticker_id"),
            "timeframe": protocol.timeframe,
            "timezone": snapshot.get("csv_timezone"),
        },
        "strategy": {
            "name": protocol.strategy,
            "version": protocol.strategy_version,
            "pine_path": current_source.get("pine_path"),
            "pine_source_sha256": current_source.get("pine_source_sha256"),
        },
        "properties": {
            "initial_capital": parameters.get("initial_capital"),
            "commission_percent": (snapshot.get("cost_model") or {}).get(
                "commission_percent"
            ),
            "slippage_ticks": (snapshot.get("slippage_model") or {}).get("ticks"),
            "pyramiding": 0,
            "process_orders_on_close": True,
        },
        "inputs": parameters,
        "export": {
            "source_format": "tradingview",
            "report": "Strategy Tester completed trades CSV",
            "source_reference": source_reference,
            "protocol_id": protocol.id,
        },
    }
    manifest_evidence = {
        "schema_version": "tradingview-run-manifest-v2",
        "protocol_id": protocol.id,
        "protocol_hash": protocol.protocol_hash,
        "strategy": protocol.strategy,
        "strategy_version": protocol.strategy_version,
        "registered_at": ensure_utc(protocol.registered_at).isoformat(),
        "source_evidence": current_source,
        "settings_fingerprint": settings_fingerprint,
        "tradingview_setup": tradingview_setup,
    }
    manifest_hash = build_backtest_protocol_hash(manifest_evidence)
    return {
        "status": "READY" if not reasons else "BLOCKED",
        "protocol_id": protocol.id,
        "protocol_hash": protocol.protocol_hash,
        "manifest_hash": manifest_hash,
        "strategy": protocol.strategy,
        "strategy_version": protocol.strategy_version,
        "symbol": symbol,
        "timeframe": protocol.timeframe,
        "registered_at": protocol.registered_at,
        "protocol_status": protocol_status,
        "source_evidence": current_source,
        "settings_fingerprint": settings_fingerprint,
        "tradingview_setup": tradingview_setup,
        "checks": checks,
        "reasons": reasons,
        "warnings": [
            (
                "The manifest proves local configuration and source binding, "
                "not TradingView authenticity."
            ),
            "Do not change Pine inputs or Strategy Properties after protocol registration.",
        ],
        "next_actions": (
            [
                "Load the exact Pine source and apply the frozen TradingView setup.",
                "Confirm diagnostics show submitted and closed trades.",
                "Export completed trades and import it with this protocol ID.",
            ]
            if not reasons
            else [
                (
                    "Register a new protocol from the current strategy setup "
                    "after resolving blockers."
                )
            ]
        ),
        "mutates_ledger": False,
    }


def build_tradingview_run_package(protocol: BacktestProtocol) -> dict[str, object]:
    manifest = build_backtest_run_manifest(protocol)
    source_evidence = manifest["source_evidence"]
    reasons = list(manifest["reasons"])
    pine_source: str | None = None
    source_byte_length: int | None = None
    source_line_count: int | None = None

    configuration_reasons = [
        reason for reason in reasons if reason != "protocol_unconsumed"
    ]
    if not configuration_reasons:
        pine_path_value = source_evidence.get("pine_path")
        if not isinstance(pine_path_value, str):
            reasons.append("pine_source_path_unavailable")
        else:
            pine_path = (AUREX_ROOT / pine_path_value).resolve()
            try:
                pine_path.relative_to(AUREX_ROOT)
            except ValueError:
                reasons.append("pine_path_outside_repository")
            else:
                source_bytes = pine_path.read_bytes()
                current_hash = sha256(source_bytes).hexdigest()
                if current_hash != source_evidence.get("pine_source_sha256"):
                    reasons.append("pine_source_changed_during_package_build")
                else:
                    try:
                        pine_source = source_bytes.decode("utf-8")
                    except UnicodeDecodeError:
                        reasons.append("pine_source_not_utf8")
                    else:
                        source_byte_length = len(source_bytes)
                        source_line_count = len(pine_source.splitlines())

    reasons = list(dict.fromkeys(reasons))
    package_evidence = {
        "schema_version": "tradingview-run-package-v2",
        "protocol_id": protocol.id,
        "protocol_hash": protocol.protocol_hash,
        "manifest_hash": manifest["manifest_hash"],
        "pine_source_sha256": source_evidence.get("pine_source_sha256"),
        "source_byte_length": source_byte_length,
        "source_line_count": source_line_count,
        "tradingview_setup": manifest["tradingview_setup"],
    }
    package_hash = build_backtest_protocol_hash(package_evidence)
    ticker_id = manifest["tradingview_setup"]["chart"].get("ticker_id")
    tradingview_url = (
        f"https://www.tradingview.com/chart/?symbol={quote(ticker_id, safe='')}"
        if ticker_id
        else None
    )
    return {
        "status": "READY" if not reasons and pine_source is not None else "BLOCKED",
        "protocol_id": protocol.id,
        "protocol_hash": protocol.protocol_hash,
        "manifest_hash": manifest["manifest_hash"],
        "package_hash": package_hash,
        "strategy": protocol.strategy,
        "strategy_version": protocol.strategy_version,
        "ticker_id": ticker_id,
        "timeframe": protocol.timeframe,
        "pine_source": pine_source,
        "pine_source_sha256": source_evidence.get("pine_source_sha256"),
        "source_byte_length": source_byte_length,
        "source_line_count": source_line_count,
        "tradingview_url": tradingview_url,
        "tradingview_setup": manifest["tradingview_setup"],
        "reasons": reasons,
        "warnings": [
            "Copy Pine only from this package; do not edit it before the frozen run.",
            (
                "TradingView may normalize editor line endings; Aurex binds the exact "
                "repository bytes and cannot obtain a TradingView-signed source hash."
            ),
        ],
        "mutates_ledger": False,
    }


def normalized_symbols(symbols: list[str]) -> list[str]:
    return [str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()]


def backtest_protocol_audit_snapshot(
    *,
    protocol_id: str | None,
    protocol_hash: str | None,
    registered_at: datetime | None,
    reasons: list[str],
) -> dict[str, object]:
    return {
        "status": "MATCHED" if not reasons else "BLOCKED",
        "acceptance_eligible": not reasons,
        "protocol_id": protocol_id,
        "protocol_hash": protocol_hash,
        "registered_at": optional_iso(registered_at),
        "reasons": reasons,
        "immutable": True,
    }


def apply_protocol_acceptance(
    acceptance_passed: bool,
    acceptance_reasons: list[str],
    protocol_audit: dict[str, object],
) -> tuple[bool, list[str]]:
    protocol_reasons = list(protocol_audit.get("reasons") or [])
    if not protocol_reasons:
        return acceptance_passed, acceptance_reasons
    reason_messages = {
        "backtest_protocol_missing": (
            "An immutable backtest protocol must be registered before report evaluation"
        ),
        "backtest_protocol_not_found": "The submitted backtest protocol does not exist",
        "backtest_protocol_integrity_mismatch": (
            "The registered backtest protocol failed its integrity hash"
        ),
        "backtest_report_does_not_match_protocol": (
            "The backtest report settings do not match the registered protocol"
        ),
        "backtest_protocol_already_consumed": (
            "The registered backtest protocol has already been consumed by another report"
        ),
    }
    reasons = [reason for reason in acceptance_reasons if reason != "Acceptance gate passed"]
    reasons.extend(reason_messages.get(reason, reason) for reason in protocol_reasons)
    return False, list(dict.fromkeys(reasons))


def backtest_protocol_response(protocol: BacktestProtocol) -> dict[str, object]:
    consumed_by_run_id = protocol.backtest_run.id if protocol.backtest_run else None
    return {
        "id": protocol.id,
        "strategy": protocol.strategy,
        "strategy_version": protocol.strategy_version,
        "symbols": protocol.symbols,
        "timeframe": protocol.timeframe,
        "protocol_hash": protocol.protocol_hash,
        "protocol_snapshot": protocol.protocol_snapshot,
        "registered_at": protocol.registered_at,
        "status": "CONSUMED" if consumed_by_run_id else "REGISTERED",
        "consumed_by_run_id": consumed_by_run_id,
        "immutable": True,
    }


def plan_walk_forward_windows(
    request: WalkForwardPlanRequest,
) -> WalkForwardPlanResponse:
    strategy = request.strategy.strip()
    if not strategy:
        raise ValueError("Strategy is required to plan walk-forward folds")
    start = ensure_utc(request.in_sample_start)
    end = ensure_utc(request.in_sample_end)
    if start >= end:
        raise ValueError("In-sample start must be before in-sample end")
    if walk_forward_parameter_fingerprint(strategy, request.parameters) is None:
        raise ValueError("Complete strategy parameters are required to plan walk-forward folds")

    total_units = int((end - start).total_seconds() * 1_000_000) + 1
    training_units = int(
        Decimal(total_units) * request.initial_training_fraction
    )
    remaining_units = total_units - training_units
    if training_units < 1 or remaining_units < request.window_count:
        raise ValueError(
            "In-sample period is too short for the requested training fraction and fold count"
        )

    base_test_units, remainder = divmod(remaining_units, request.window_count)
    windows: list[WalkForwardWindowInput] = []
    cursor = training_units
    for index in range(request.window_count):
        test_units = base_test_units + (1 if index < remainder else 0)
        train_end = start + timedelta(microseconds=cursor - 1)
        test_start = start + timedelta(microseconds=cursor)
        test_end = start + timedelta(microseconds=cursor + test_units - 1)
        windows.append(
            WalkForwardWindowInput(
                window_id=f"wf-{index + 1}",
                train_start=start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                configuration_reference=(
                    f"aurex://walk-forward-plan/{strategy}/wf-{index + 1}"
                ),
                parameters=request.parameters,
            )
        )
        cursor += test_units

    plan_evidence = {
        "method": EXPLICIT_WALK_FORWARD_METHOD,
        "strategy": strategy,
        "in_sample_start": start.isoformat(),
        "in_sample_end": end.isoformat(),
        "window_count": request.window_count,
        "initial_training_fraction": str(request.initial_training_fraction),
        "windows": [window.model_dump(mode="json") for window in windows],
        "outcome_fields_inspected": [],
    }
    plan_hash = build_backtest_protocol_hash(plan_evidence)
    return WalkForwardPlanResponse(
        status="READY",
        method=EXPLICIT_WALK_FORWARD_METHOD,
        strategy=strategy,
        in_sample_start=start,
        in_sample_end=end,
        window_count=request.window_count,
        initial_training_fraction=request.initial_training_fraction,
        windows=windows,
        plan_hash=plan_hash,
        outcome_fields_inspected=[],
        warnings=[
            (
                "Calendar folds do not guarantee the minimum number of trades per fold; "
                "insufficient evidence must fail without replanning after results."
            ),
            (
                "Register the immutable protocol before running or inspecting external "
                "strategy results."
            ),
        ],
        next_actions=[
            "Review the date boundaries without using outcome data.",
            "Register the immutable backtest protocol.",
            "Run TradingView only after protocol registration.",
        ],
        mutates_ledger=False,
    )


def backtest_strategy_setup(
    *,
    strategy: str,
    symbol: str,
    timeframe: str,
    venue: str = "BINANCE",
) -> dict[str, object]:
    normalized_strategy = strategy.strip()
    normalized_symbol = symbol.strip().upper().replace(" ", "")
    normalized_timeframe = timeframe.strip()
    normalized_venue = venue.strip().upper().replace(" ", "")
    if TRADINGVIEW_VENUE_PATTERN.fullmatch(normalized_venue) is None:
        raise ValueError("TradingView venue must contain only letters, numbers, or underscore")
    if TRADINGVIEW_SYMBOL_PATTERN.fullmatch(normalized_symbol) is None:
        raise ValueError("TradingView symbol contains unsupported characters")
    ticker_id = f"{normalized_venue}:{normalized_symbol}"
    definition = REGISTERED_STRATEGIES.get(normalized_strategy)
    if definition is None:
        raise ValueError(f"Unknown strategy: {normalized_strategy}")
    parameters = dict(KNOWN_STRATEGY_PARAMETER_TEMPLATES.get(normalized_strategy, {}))
    required_parameters = list(KNOWN_STRATEGY_REQUIRED_PARAMETERS.get(normalized_strategy, ()))
    return {
        "strategy": definition.strategy,
        "strategy_version": definition.version,
        "display_name": definition.display_name,
        "known_strategy": True,
        "parameter_provenance_required": bool(required_parameters),
        "pine_path": definition.pine_path,
        "docs_path": definition.docs_path,
        "strategy_source_evidence": strategy_source_evidence(
            definition.strategy,
            definition.version,
        ),
        "symbol": normalized_symbol,
        "venue": normalized_venue,
        "ticker_id": ticker_id,
        "timeframe": normalized_timeframe,
        "data_source": "tradingview-export",
        "csv_format": "auto",
        "csv_timezone": "UTC",
        "source_reference": (
            f"tradingview://strategy-tester/{ticker_id}/{normalized_timeframe}"
        ),
        "parameters": parameters,
        "settings_fingerprint": strategy_parameter_fingerprint(
            normalized_strategy,
            parameters,
        ),
        "required_parameters": required_parameters,
        "cost_model": dict(DEFAULT_BACKTEST_COST_MODELS.get(normalized_strategy, {})),
        "slippage_model": dict(DEFAULT_BACKTEST_SLIPPAGE_MODELS.get(normalized_strategy, {})),
        "risk_snapshot": {"risk_per_trade": str(definition.default_risk_per_trade)},
        "walk_forward_method": EXPLICIT_WALK_FORWARD_METHOD,
        "walk_forward_windows": [],
        "acceptance_criteria": AcceptanceCriteria(),
        "next_actions": [
            (
                "Freeze these dates, settings, costs, acceptance rules, and explicit "
                "walk-forward folds in an immutable backtest protocol before running results."
            ),
            (
                "Paste the Pine strategy into TradingView and confirm Strategy Tester "
                "has closed trades."
            ),
            (
                "Export the completed-trades CSV from the same symbol, timeframe, "
                "version, and settings."
            ),
            (
                "Declare chronological train/test walk-forward windows inside the "
                "in-sample period; automatic trade slices are diagnostic only."
            ),
            "Preflight the CSV before import; do not change acceptance thresholds to force a pass.",
        ],
        "mutates_ledger": False,
    }


def calculate_backtest_metrics(trades: list[BacktestTradeInput]) -> BacktestMetrics:
    realized_values = [trade.realized_pl for trade in trades]
    total_trades = len(realized_values)
    if total_trades == 0:
        return BacktestMetrics(
            total_trades=0,
            wins=0,
            losses=0,
            breakeven=0,
            win_rate=ZERO,
            average_win=ZERO,
            average_loss=ZERO,
            expectancy=ZERO,
            profit_factor=None,
            max_drawdown=ZERO,
            total_net_pl=ZERO,
            equity_curve=[],
        )

    wins = [value for value in realized_values if value > 0]
    losses = [abs(value) for value in realized_values if value < 0]
    breakeven = sum(1 for value in realized_values if value == 0)
    gross_profit = sum(wins, ZERO)
    gross_loss = sum(losses, ZERO)
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = Decimal(win_count) / Decimal(total_trades)
    loss_rate = Decimal(loss_count) / Decimal(total_trades)
    average_win = gross_profit / win_count if win_count else ZERO
    average_loss = gross_loss / loss_count if loss_count else ZERO
    expectancy = (win_rate * average_win) - (loss_rate * average_loss)
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None
    total_net_pl = sum(realized_values, ZERO)
    equity_curve = build_equity_curve(trades)
    max_drawdown = max(
        (Decimal(point["drawdown"]) for point in equity_curve),
        default=ZERO,
    )

    return BacktestMetrics(
        total_trades=total_trades,
        wins=win_count,
        losses=loss_count,
        breakeven=breakeven,
        win_rate=win_rate,
        average_win=average_win,
        average_loss=average_loss,
        expectancy=expectancy,
        profit_factor=profit_factor,
        max_drawdown=max_drawdown,
        total_net_pl=total_net_pl,
        equity_curve=equity_curve,
    )


def calculate_backtest_segments(payload: BacktestReportCreate) -> BacktestSegments:
    in_sample = None
    out_of_sample = None
    holdout = None
    if payload.in_sample_start is not None and payload.in_sample_end is not None:
        in_sample = calculate_backtest_metrics(
            trades_in_window(
                payload.trades,
                ensure_utc(payload.in_sample_start),
                ensure_utc(payload.in_sample_end),
            )
        )
    if payload.out_of_sample_start is not None and payload.out_of_sample_end is not None:
        out_of_sample = calculate_backtest_metrics(
            trades_in_window(
                payload.trades,
                ensure_utc(payload.out_of_sample_start),
                ensure_utc(payload.out_of_sample_end),
            )
        )
    if payload.holdout_start is not None and payload.holdout_end is not None:
        holdout = calculate_backtest_metrics(
            trades_in_window(
                payload.trades,
                ensure_utc(payload.holdout_start),
                ensure_utc(payload.holdout_end),
            )
        )
    walk_forward = calculate_walk_forward_snapshot(payload)
    return BacktestSegments(
        in_sample=in_sample,
        out_of_sample=out_of_sample,
        holdout=holdout,
        walk_forward=walk_forward,
    )


def trades_in_window(
    trades: list[BacktestTradeInput],
    start: datetime,
    end: datetime,
) -> list[BacktestTradeInput]:
    return [
        trade
        for trade in trades
        if trade.closed_at is not None and start <= ensure_utc(trade.closed_at) <= end
    ]


def metrics_to_snapshot(metrics: BacktestMetrics) -> dict[str, str | int | None]:
    return {
        "total_trades": metrics.total_trades,
        "wins": metrics.wins,
        "losses": metrics.losses,
        "breakeven": metrics.breakeven,
        "win_rate": str(metrics.win_rate),
        "average_win": str(metrics.average_win),
        "average_loss": str(metrics.average_loss),
        "expectancy": str(metrics.expectancy),
        "profit_factor": str(metrics.profit_factor) if metrics.profit_factor is not None else None,
        "max_drawdown": str(metrics.max_drawdown),
        "total_net_pl": str(metrics.total_net_pl),
    }


def calculate_walk_forward_snapshot(payload: BacktestReportCreate) -> dict[str, object]:
    if payload.walk_forward_windows:
        return calculate_explicit_walk_forward_snapshot(payload)
    return calculate_diagnostic_walk_forward_snapshot(
        payload.trades,
        payload.acceptance_criteria,
    )


def calculate_explicit_walk_forward_snapshot(
    payload: BacktestReportCreate,
) -> dict[str, object]:
    criteria = payload.acceptance_criteria
    global_fingerprint = walk_forward_parameter_fingerprint(
        payload.strategy,
        payload.parameters,
    )
    windows: list[dict[str, object]] = []
    passed_windows = 0
    valid_windows = 0
    prior_test_end: datetime | None = None
    seen_window_ids: set[str] = set()
    for index, window in enumerate(payload.walk_forward_windows, start=1):
        validation_reasons = walk_forward_window_validation_reasons(
            payload,
            window,
            prior_test_end=prior_test_end,
            global_fingerprint=global_fingerprint,
            duplicate_window_id=window.window_id in seen_window_ids,
        )
        window_trades = trades_in_window(
            payload.trades,
            ensure_utc(window.test_start),
            ensure_utc(window.test_end),
        )
        metrics = calculate_backtest_metrics(window_trades)
        enough_trades = metrics.total_trades >= criteria.min_walk_forward_trades_per_window
        positive_expectancy = metrics.expectancy > ZERO
        profit_factor_ok = (
            metrics.profit_factor is None and metrics.total_trades > 0 and metrics.losses == 0
        ) or (
            metrics.profit_factor is not None
            and metrics.profit_factor >= criteria.min_profit_factor
        )
        valid = not validation_reasons
        passed = bool(
            valid and enough_trades and positive_expectancy and profit_factor_ok
        )
        if valid:
            valid_windows += 1
        if passed:
            passed_windows += 1
        windows.append(
            {
                "index": index,
                "window_id": window.window_id,
                "train_start": ensure_utc(window.train_start).isoformat(),
                "train_end": ensure_utc(window.train_end).isoformat(),
                "test_start": ensure_utc(window.test_start).isoformat(),
                "test_end": ensure_utc(window.test_end).isoformat(),
                "configuration_reference": window.configuration_reference,
                "parameter_fingerprint": walk_forward_parameter_fingerprint(
                    payload.strategy,
                    window.parameters,
                ),
                "valid": valid,
                "validation_reasons": validation_reasons,
                "passed": passed,
                "enough_trades": enough_trades,
                "positive_expectancy": positive_expectancy,
                "profit_factor_ok": profit_factor_ok,
                "test_trade_evidence_hash": build_trade_evidence_hash(window_trades),
                "summary": metrics_to_snapshot(metrics),
            }
        )
        prior_test_end = ensure_utc(window.test_end)
        seen_window_ids.add(window.window_id)

    window_count = len(windows)
    pass_rate = Decimal(passed_windows) / Decimal(window_count) if window_count else ZERO
    snapshot: dict[str, object] = {
        "method": EXPLICIT_WALK_FORWARD_METHOD,
        "acceptance_eligible": True,
        "window_count": window_count,
        "valid_window_count": valid_windows,
        "invalid_window_count": window_count - valid_windows,
        "passed_windows": passed_windows,
        "failed_windows": window_count - passed_windows,
        "pass_rate": str(pass_rate),
        "minimum_windows": criteria.min_walk_forward_windows,
        "minimum_trades_per_window": criteria.min_walk_forward_trades_per_window,
        "minimum_pass_rate": str(criteria.min_walk_forward_pass_rate),
        "windows": windows,
    }
    snapshot["evidence_hash"] = walk_forward_evidence_hash(snapshot)
    return snapshot


def calculate_diagnostic_walk_forward_snapshot(
    trades: list[BacktestTradeInput],
    criteria: AcceptanceCriteria,
) -> dict[str, object]:
    eligible_trades = chronological_trades_with_dates(trades)
    window_count = min(criteria.min_walk_forward_windows, len(eligible_trades))
    windows: list[dict[str, object]] = []
    passed_windows = 0
    if window_count:
        base_size = len(eligible_trades) // window_count
        remainder = len(eligible_trades) % window_count
        start = 0
        for index in range(window_count):
            size = base_size + (1 if index < remainder else 0)
            end = start + size
            window_trades = eligible_trades[start:end]
            metrics = calculate_backtest_metrics(window_trades)
            enough_trades = (
                metrics.total_trades >= criteria.min_walk_forward_trades_per_window
            )
            positive_expectancy = metrics.expectancy > ZERO
            profit_factor_ok = (
                metrics.profit_factor is None
                and metrics.total_trades > 0
                and metrics.losses == 0
            ) or (
                metrics.profit_factor is not None
                and metrics.profit_factor >= criteria.min_profit_factor
            )
            passed = bool(enough_trades and positive_expectancy and profit_factor_ok)
            if passed:
                passed_windows += 1
            windows.append(
                {
                    "index": index + 1,
                    "start_closed_at": optional_iso(window_trades[0].closed_at),
                    "end_closed_at": optional_iso(window_trades[-1].closed_at),
                    "passed": passed,
                    "enough_trades": enough_trades,
                    "positive_expectancy": positive_expectancy,
                    "profit_factor_ok": profit_factor_ok,
                    "summary": metrics_to_snapshot(metrics),
                }
            )
            start = end

    pass_rate = Decimal(passed_windows) / Decimal(window_count) if window_count else ZERO
    snapshot: dict[str, object] = {
        "method": DIAGNOSTIC_WALK_FORWARD_METHOD,
        "acceptance_eligible": False,
        "window_count": window_count,
        "valid_window_count": 0,
        "invalid_window_count": window_count,
        "passed_windows": passed_windows,
        "failed_windows": window_count - passed_windows,
        "pass_rate": str(pass_rate),
        "minimum_windows": criteria.min_walk_forward_windows,
        "minimum_trades_per_window": criteria.min_walk_forward_trades_per_window,
        "minimum_pass_rate": str(criteria.min_walk_forward_pass_rate),
        "windows": windows,
    }
    snapshot["evidence_hash"] = walk_forward_evidence_hash(snapshot)
    return snapshot


def walk_forward_window_validation_reasons(
    payload: BacktestReportCreate,
    window: WalkForwardWindowInput,
    *,
    prior_test_end: datetime | None,
    global_fingerprint: str | None,
    duplicate_window_id: bool,
) -> list[str]:
    train_start = ensure_utc(window.train_start)
    train_end = ensure_utc(window.train_end)
    test_start = ensure_utc(window.test_start)
    test_end = ensure_utc(window.test_end)
    reasons: list[str] = []
    if duplicate_window_id:
        reasons.append("walk_forward_window_id_is_duplicated")
    if not (train_start <= train_end < test_start <= test_end):
        reasons.append("train_and_test_dates_are_not_strictly_chronological")
    if payload.in_sample_start is None or payload.in_sample_end is None:
        reasons.append("in_sample_window_is_required_for_walk_forward")
    else:
        in_sample_start = ensure_utc(payload.in_sample_start)
        in_sample_end = ensure_utc(payload.in_sample_end)
        if train_start < in_sample_start or test_end > in_sample_end:
            reasons.append("walk_forward_window_must_stay_inside_in_sample_period")
    if prior_test_end is not None:
        if test_start <= prior_test_end:
            reasons.append("walk_forward_test_windows_overlap_or_are_out_of_order")
        if train_end < prior_test_end:
            reasons.append("walk_forward_training_does_not_include_prior_test_period")
    window_fingerprint = walk_forward_parameter_fingerprint(
        payload.strategy,
        window.parameters,
    )
    if window_fingerprint is None:
        reasons.append("walk_forward_strategy_parameters_are_incomplete")
    elif global_fingerprint is None or window_fingerprint != global_fingerprint:
        reasons.append("walk_forward_strategy_parameters_do_not_match_report")
    return reasons


def walk_forward_evidence_hash(snapshot: dict[str, object]) -> str:
    evidence = {key: value for key, value in snapshot.items() if key != "evidence_hash"}
    serialized = json.dumps(evidence, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(serialized.encode("utf-8")).hexdigest()


def chronological_trades_with_dates(
    trades: list[BacktestTradeInput],
) -> list[BacktestTradeInput]:
    return sorted(
        [trade for trade in trades if trade.closed_at is not None],
        key=lambda trade: ensure_utc(trade.closed_at),  # type: ignore[arg-type]
    )


def build_metrics_snapshot(
    payload: BacktestReportCreate,
    metrics: BacktestMetrics,
    segments: BacktestSegments,
) -> dict:
    return {
        **metrics_to_snapshot(metrics),
        "source_format": payload.source_format,
        "trade_evidence_hash": build_trade_evidence_hash(payload.trades),
        "cost_evidence": backtest_cost_evidence_snapshot(payload),
        "equity_curve": metrics.equity_curve,
        "gross_profit": str(sum_positive(payload.trades)),
        "gross_loss": str(sum_negative_abs(payload.trades)),
        "in_sample": metrics_to_snapshot(segments.in_sample) if segments.in_sample else None,
        "out_of_sample": (
            metrics_to_snapshot(segments.out_of_sample) if segments.out_of_sample else None
        ),
        "holdout": metrics_to_snapshot(segments.holdout) if segments.holdout else None,
        "universal_robustness": universal_robustness_snapshot(
            payload,
            payload.acceptance_criteria,
            segments,
        ),
        "walk_forward": segments.walk_forward,
        "trade_distribution": trade_distribution_snapshot(payload.trades),
        "market_regime_breakdown": market_regime_breakdown_snapshot(payload.trades),
        "strategy_parameter_evidence": strategy_parameter_evidence_snapshot(
            payload.strategy,
            payload.parameters,
        ),
    }


def trade_distribution_snapshot(trades: list[BacktestTradeInput]) -> dict[str, str | int | None]:
    closed_dates = [
        ensure_utc(trade.closed_at).date()
        for trade in trades
        if trade.closed_at is not None
    ]
    if not closed_dates:
        return {
            "dated_trade_count": 0,
            "total_trade_count": len(trades),
            "first_closed_at": None,
            "last_closed_at": None,
            "active_trading_days": 0,
            "max_single_day_trade_count": 0,
            "max_single_day_trade_share": "0",
        }

    daily_counts: dict[str, int] = {}
    for value in closed_dates:
        key = value.isoformat()
        daily_counts[key] = daily_counts.get(key, 0) + 1
    max_daily_count = max(daily_counts.values(), default=0)
    dated_trade_count = len(closed_dates)
    return {
        "dated_trade_count": dated_trade_count,
        "total_trade_count": len(trades),
        "first_closed_at": min(closed_dates).isoformat(),
        "last_closed_at": max(closed_dates).isoformat(),
        "active_trading_days": len(daily_counts),
        "max_single_day_trade_count": max_daily_count,
        "max_single_day_trade_share": str(
            Decimal(max_daily_count) / Decimal(dated_trade_count)
        ),
    }


def market_regime_breakdown_snapshot(trades: list[BacktestTradeInput]) -> dict:
    grouped: dict[str, list[BacktestTradeInput]] = {}
    missing = 0
    for trade in trades:
        if trade.market_regime is None or trade.market_regime == "":
            missing += 1
            continue
        grouped.setdefault(trade.market_regime, []).append(trade)

    return {
        "missing_market_regime_count": missing,
        "regime_count": len(grouped),
        "regimes": {
            regime: metrics_to_snapshot(calculate_backtest_metrics(regime_trades))
            for regime, regime_trades in sorted(grouped.items())
        },
    }


def build_equity_curve(trades: list[BacktestTradeInput]) -> list[dict[str, str]]:
    equity = ZERO
    high_water = ZERO
    curve: list[dict[str, str]] = []
    for index, trade in enumerate(trades, start=1):
        equity = trade.equity if trade.equity is not None else equity + trade.realized_pl
        high_water = max(high_water, equity)
        drawdown = max(ZERO, high_water - equity)
        curve.append(
            {
                "index": str(index),
                "equity": str(equity),
                "drawdown": str(drawdown),
                "realized_pl": str(trade.realized_pl),
            }
        )
    return curve


def evaluate_acceptance(
    metrics: BacktestMetrics,
    criteria: AcceptanceCriteria,
    payload: BacktestReportCreate | None = None,
    segments: BacktestSegments | None = None,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if metrics.total_trades < criteria.min_trades:
        reasons.append(
            f"Total trades {metrics.total_trades} below minimum {criteria.min_trades}"
        )
    if metrics.profit_factor is None:
        if metrics.total_trades == 0 or metrics.wins == 0:
            reasons.append("Profit factor unavailable because there are no winning/losing trades")
    elif metrics.profit_factor < criteria.min_profit_factor:
        reasons.append(
            f"Profit factor {metrics.profit_factor} below minimum {criteria.min_profit_factor}"
        )
    if criteria.require_positive_expectancy and metrics.expectancy <= 0:
        reasons.append(f"Expectancy {metrics.expectancy} is not positive")
    if criteria.max_drawdown is not None and metrics.max_drawdown > criteria.max_drawdown:
        reasons.append(
            f"Max drawdown {metrics.max_drawdown} exceeds limit {criteria.max_drawdown}"
        )
    if payload is not None:
        reasons.extend(acceptance_context_reasons(payload, criteria, segments))

    if not reasons:
        reasons.append("Acceptance gate passed")
    return len(reasons) == 1 and reasons[0] == "Acceptance gate passed", reasons


def acceptance_context_reasons(
    payload: BacktestReportCreate,
    criteria: AcceptanceCriteria,
    segments: BacktestSegments | None,
) -> list[str]:
    reasons: list[str] = []
    if criteria.require_sample_windows:
        window_reasons = sample_window_reasons(payload)
        reasons.extend(window_reasons)
    if criteria.require_cost_model and not payload.cost_model:
        reasons.append("Cost model is required for accepted backtests")
    if criteria.require_slippage_model and not payload.slippage_model:
        reasons.append("Slippage model is required for accepted backtests")
    if criteria.require_risk_snapshot and not payload.risk_snapshot:
        reasons.append("Risk snapshot is required for accepted backtests")
    reasons.extend(strategy_parameter_acceptance_reasons(payload))
    if criteria.require_out_of_sample_metrics:
        if segments is None or segments.out_of_sample is None:
            reasons.append("Out-of-sample metrics are required for accepted backtests")
        else:
            reasons.extend(out_of_sample_reasons(segments.out_of_sample, criteria))
    if criteria.require_trade_dates:
        reasons.extend(trade_distribution_reasons(payload.trades, criteria))
    if criteria.require_market_regime_breakdown:
        reasons.extend(market_regime_reasons(payload.trades))
    if criteria.require_walk_forward_validation:
        reasons.extend(walk_forward_reasons(segments, criteria))
    robustness = universal_robustness_snapshot(payload, criteria, segments)
    reasons.extend(str(reason) for reason in robustness.get("reasons", []))
    return reasons


def strict_strategy_factory_acceptance_criteria(
    **overrides: object,
) -> AcceptanceCriteria:
    payload = AcceptanceCriteria(
        require_cost_stress=True,
        require_uncertainty_bound=True,
        require_multiple_testing_control=True,
        require_holdout_decision=True,
    ).model_dump()
    payload.update(overrides)
    return AcceptanceCriteria.model_validate(payload)


def universal_acceptance_configuration_reasons(
    criteria: AcceptanceCriteria,
    payload: BacktestReportCreate,
) -> list[str]:
    requirements = (
        criteria.require_cost_stress,
        criteria.require_uncertainty_bound,
        criteria.require_multiple_testing_control,
        criteria.require_holdout_decision,
    )
    if not any(requirements):
        return []

    reasons: list[str] = []
    if not all(requirements):
        reasons.append(
            "Universal robustness controls must be enabled together: cost stress, "
            "uncertainty bound, multiple-testing control, and holdout decision"
        )
    if any(multiplier <= 1 for multiplier in criteria.cost_stress_multipliers):
        reasons.append("Every cost-stress multiplier must be greater than 1")
    if len(set(criteria.cost_stress_multipliers)) != len(
        criteria.cost_stress_multipliers
    ):
        reasons.append("Cost-stress multipliers must be unique")
    if payload.tested_variant_count > criteria.max_tested_variants:
        reasons.append(
            "Tested variant count "
            f"{payload.tested_variant_count} exceeds maximum "
            f"{criteria.max_tested_variants}"
        )
    if not payload.variant_registry_hash:
        reasons.append(
            "A hash-bound variant registry is required for multiple-testing control"
        )
    if payload.holdout_start is None or payload.holdout_end is None:
        reasons.append("A separate chronological holdout window is required")
    return reasons


def universal_robustness_snapshot(
    payload: BacktestReportCreate,
    criteria: AcceptanceCriteria,
    segments: BacktestSegments | None,
) -> dict[str, object]:
    requirement_snapshot = {
        "require_cost_stress": criteria.require_cost_stress,
        "require_uncertainty_bound": criteria.require_uncertainty_bound,
        "require_multiple_testing_control": criteria.require_multiple_testing_control,
        "require_holdout_decision": criteria.require_holdout_decision,
    }
    if not any(requirement_snapshot.values()):
        return {
            "status": "LEGACY_NOT_EVALUATED",
            "requirements": requirement_snapshot,
            "reasons": [],
        }

    configuration_reasons = universal_acceptance_configuration_reasons(
        criteria,
        payload,
    )
    if configuration_reasons:
        return {
            "status": "BLOCKED",
            "requirements": requirement_snapshot,
            "reasons": configuration_reasons,
        }

    holdout_trades = trades_in_window(
        payload.trades,
        ensure_utc(payload.holdout_start),
        ensure_utc(payload.holdout_end),
    )
    holdout_metrics = segments.holdout if segments is not None else None
    holdout_gate_reasons = (
        holdout_reasons(holdout_metrics, criteria)
        if criteria.require_holdout_decision
        else []
    )
    cost_stress = cost_stress_evidence_snapshot(holdout_trades, criteria)
    uncertainty = uncertainty_evidence_snapshot(holdout_trades, criteria)
    multiple_testing = multiple_testing_evidence_snapshot(
        holdout_metrics,
        payload,
        criteria,
    )
    reasons = [*holdout_gate_reasons]
    for evidence in (cost_stress, uncertainty, multiple_testing):
        reasons.extend(str(reason) for reason in evidence.get("reasons", []))
    reasons = list(dict.fromkeys(reasons))
    return {
        "status": "PASS" if not reasons else "FAIL",
        "requirements": requirement_snapshot,
        "holdout_window": {
            "start": optional_iso(payload.holdout_start),
            "end": optional_iso(payload.holdout_end),
        },
        "holdout_metrics": (
            metrics_to_snapshot(holdout_metrics) if holdout_metrics is not None else None
        ),
        "cost_stress": cost_stress,
        "uncertainty": uncertainty,
        "multiple_testing": multiple_testing,
        "reasons": reasons,
    }


def holdout_reasons(
    metrics: BacktestMetrics | None,
    criteria: AcceptanceCriteria,
) -> list[str]:
    if metrics is None:
        return ["Separate holdout metrics are required for accepted backtests"]
    reasons: list[str] = []
    if metrics.total_trades < criteria.min_holdout_trades:
        reasons.append(
            f"Holdout trades {metrics.total_trades} below minimum "
            f"{criteria.min_holdout_trades}"
        )
    if criteria.require_holdout_positive_expectancy and metrics.expectancy <= 0:
        reasons.append(f"Holdout expectancy {metrics.expectancy} is not positive")
    if metrics.profit_factor is None:
        if metrics.total_trades == 0 or metrics.wins == 0:
            reasons.append("Holdout profit factor unavailable because there are no wins")
    elif metrics.profit_factor < criteria.min_holdout_profit_factor:
        reasons.append(
            f"Holdout profit factor {metrics.profit_factor} below minimum "
            f"{criteria.min_holdout_profit_factor}"
        )
    return reasons


def cost_stress_evidence_snapshot(
    trades: list[BacktestTradeInput],
    criteria: AcceptanceCriteria,
) -> dict[str, object]:
    if not criteria.require_cost_stress:
        return {"status": "NOT_REQUIRED", "cases": [], "reasons": []}
    missing_cost_count = sum(
        trade.fees is None or trade.slippage is None for trade in trades
    )
    reasons: list[str] = []
    if not trades:
        reasons.append("Cost stress requires holdout trades")
    if missing_cost_count:
        reasons.append(
            f"Cost stress requires trade-level fees and slippage ({missing_cost_count} missing)"
        )
    total_modeled_cost = sum(
        ((trade.fees or ZERO) + (trade.slippage or ZERO) for trade in trades),
        ZERO,
    )
    if trades and total_modeled_cost <= 0:
        reasons.append("Cost stress requires a positive modeled cost baseline")

    cases: list[dict[str, object]] = []
    if not reasons:
        for multiplier in sorted(criteria.cost_stress_multipliers):
            stressed_trades = [
                trade.model_copy(
                    update={
                        "realized_pl": trade.realized_pl
                        - ((trade.fees or ZERO) + (trade.slippage or ZERO))
                        * (multiplier - 1),
                        "equity": None,
                    }
                )
                for trade in trades
            ]
            metrics = calculate_backtest_metrics(stressed_trades)
            case_reasons: list[str] = []
            if (
                criteria.require_cost_stress_positive_expectancy
                and metrics.expectancy <= 0
            ):
                case_reasons.append(
                    f"Cost stress {multiplier}x expectancy {metrics.expectancy} is not positive"
                )
            if metrics.profit_factor is None:
                if metrics.total_trades == 0 or metrics.wins == 0:
                    case_reasons.append(
                        f"Cost stress {multiplier}x profit factor is unavailable"
                    )
            elif metrics.profit_factor < criteria.min_cost_stress_profit_factor:
                case_reasons.append(
                    f"Cost stress {multiplier}x profit factor "
                    f"{metrics.profit_factor} below minimum "
                    f"{criteria.min_cost_stress_profit_factor}"
                )
            reasons.extend(case_reasons)
            cases.append(
                {
                    "multiplier": str(multiplier),
                    "metrics": metrics_to_snapshot(metrics),
                    "passed": not case_reasons,
                    "reasons": case_reasons,
                }
            )
    return {
        "status": "PASS" if not reasons else "FAIL",
        "trade_count": len(trades),
        "missing_trade_cost_count": missing_cost_count,
        "total_modeled_cost": str(total_modeled_cost),
        "cases": cases,
        "reasons": reasons,
    }


def uncertainty_evidence_snapshot(
    trades: list[BacktestTradeInput],
    criteria: AcceptanceCriteria,
) -> dict[str, object]:
    if not criteria.require_uncertainty_bound:
        return {"status": "NOT_REQUIRED", "reasons": []}
    if not trades:
        return {
            "status": "FAIL",
            "trade_count": 0,
            "reasons": ["Uncertainty bound requires holdout trades"],
        }
    lower_bound, block_length, seed_hash = moving_block_bootstrap_mean_lower_bound(
        [trade.realized_pl for trade in trades],
        samples=criteria.uncertainty_bootstrap_samples,
        confidence=criteria.uncertainty_confidence,
    )
    reasons = []
    if lower_bound <= criteria.min_uncertainty_expectancy_lower_bound:
        reasons.append(
            "Holdout bootstrap expectancy lower bound "
            f"{lower_bound} does not exceed "
            f"{criteria.min_uncertainty_expectancy_lower_bound}"
        )
    return {
        "status": "PASS" if not reasons else "FAIL",
        "method": "deterministic_moving_block_bootstrap_mean",
        "trade_count": len(trades),
        "samples": criteria.uncertainty_bootstrap_samples,
        "confidence": str(criteria.uncertainty_confidence),
        "block_length": block_length,
        "seed_hash": seed_hash,
        "expectancy_lower_bound": str(lower_bound),
        "minimum_required_lower_bound": str(
            criteria.min_uncertainty_expectancy_lower_bound
        ),
        "reasons": reasons,
    }


def moving_block_bootstrap_mean_lower_bound(
    values: list[Decimal],
    *,
    samples: int,
    confidence: Decimal,
) -> tuple[Decimal, int, str]:
    serialized = json.dumps([str(value) for value in values], separators=(",", ":"))
    seed_hash = sha256(serialized.encode("utf-8")).hexdigest()
    random = Random(int(seed_hash[:16], 16))
    size = len(values)
    block_length = 1 if size == 1 else max(2, min(size, round(size ** (1 / 3))))
    means: list[Decimal] = []
    for _ in range(samples):
        draw: list[Decimal] = []
        while len(draw) < size:
            start = random.randrange(size)
            draw.extend(
                values[(start + offset) % size] for offset in range(block_length)
            )
        means.append(sum(draw[:size], ZERO) / Decimal(size))
    means.sort()
    tail_probability = Decimal("1") - confidence
    index = min(samples - 1, max(0, int(tail_probability * Decimal(samples))))
    return means[index], block_length, seed_hash


def multiple_testing_evidence_snapshot(
    metrics: BacktestMetrics | None,
    payload: BacktestReportCreate,
    criteria: AcceptanceCriteria,
) -> dict[str, object]:
    if not criteria.require_multiple_testing_control:
        return {"status": "NOT_REQUIRED", "reasons": []}
    variant_penalty = min(
        criteria.multiple_testing_profit_factor_step
        * Decimal(max(0, payload.tested_variant_count - 1)),
        criteria.max_multiple_testing_profit_factor_penalty,
    )
    adjusted_threshold = criteria.min_holdout_profit_factor + variant_penalty
    reasons: list[str] = []
    if payload.tested_variant_count > criteria.max_tested_variants:
        reasons.append(
            f"Tested variant count {payload.tested_variant_count} exceeds maximum "
            f"{criteria.max_tested_variants}"
        )
    if not payload.variant_registry_hash:
        reasons.append("Variant registry hash is required")
    if metrics is None:
        reasons.append("Multiple-testing control requires holdout metrics")
    elif metrics.profit_factor is None:
        if metrics.total_trades == 0 or metrics.wins == 0:
            reasons.append("Adjusted holdout profit factor is unavailable")
    elif metrics.profit_factor < adjusted_threshold:
        reasons.append(
            f"Holdout profit factor {metrics.profit_factor} below multiplicity-adjusted "
            f"minimum {adjusted_threshold}"
        )
    return {
        "status": "PASS" if not reasons else "FAIL",
        "tested_variant_count": payload.tested_variant_count,
        "maximum_tested_variants": criteria.max_tested_variants,
        "variant_registry_hash": payload.variant_registry_hash,
        "base_profit_factor_threshold": str(criteria.min_holdout_profit_factor),
        "profit_factor_penalty": str(variant_penalty),
        "adjusted_profit_factor_threshold": str(adjusted_threshold),
        "reasons": reasons,
    }


def strategy_parameter_evidence_snapshot(
    strategy: str,
    parameters: dict | None,
) -> dict[str, object]:
    required_parameters = list(
        KNOWN_STRATEGY_REQUIRED_PARAMETERS.get(strategy, ())
    )
    parameter_values = parameters or {}
    missing_parameters = [
        key
        for key in required_parameters
        if strategy_parameter_value_missing(parameter_values.get(key))
    ]
    return {
        "strategy": strategy,
        "known_strategy": bool(required_parameters),
        "required_parameters": required_parameters,
        "missing_parameters": missing_parameters,
        "complete": not missing_parameters,
    }


def strategy_parameter_acceptance_reasons(
    payload: BacktestReportCreate,
) -> list[str]:
    snapshot = strategy_parameter_evidence_snapshot(
        payload.strategy,
        payload.parameters,
    )
    missing = snapshot["missing_parameters"]
    if not missing:
        return []
    return [
        (
            f"Strategy parameters missing for {payload.strategy}: "
            f"{', '.join(str(item) for item in missing)}"
        )
    ]


def accepted_backtest_strategy_parameter_reasons(run: BacktestRun) -> list[str]:
    snapshot = strategy_parameter_evidence_snapshot(
        run.strategy,
        run.parameters or {},
    )
    if snapshot["missing_parameters"]:
        return ["accepted_backtest_strategy_parameters_missing"]
    return []


def strategy_parameter_fingerprint(
    strategy: str,
    parameters: dict | None,
) -> str | None:
    required_parameters = KNOWN_STRATEGY_REQUIRED_PARAMETERS.get(strategy)
    if not required_parameters:
        return None
    parameter_values = parameters or {}
    if any(
        strategy_parameter_value_missing(parameter_values.get(key))
        for key in required_parameters
    ):
        return None
    parts = [strategy]
    parts.extend(
        f"{key}={strategy_parameter_fingerprint_value(parameter_values[key])}"
        for key in required_parameters
    )
    return "|".join(parts)


def walk_forward_parameter_fingerprint(
    strategy: str,
    parameters: dict | None,
) -> str | None:
    known_fingerprint = strategy_parameter_fingerprint(strategy, parameters)
    if strategy in KNOWN_STRATEGY_REQUIRED_PARAMETERS:
        return known_fingerprint
    if not parameters:
        return None
    serialized = json.dumps(parameters, sort_keys=True, separators=(",", ":"), default=str)
    return f"{strategy}|sha256={sha256(serialized.encode('utf-8')).hexdigest()}"


def strategy_parameter_fingerprint_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    candidate = str(value).strip()
    try:
        parsed = Decimal(candidate)
    except Exception:
        return candidate
    return format(parsed.normalize(), "f")


def strategy_parameter_value_missing(value: object) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def walk_forward_reasons(
    segments: BacktestSegments | None,
    criteria: AcceptanceCriteria,
) -> list[str]:
    snapshot = segments.walk_forward if segments is not None else None
    if not isinstance(snapshot, dict):
        return ["Walk-forward validation is required for accepted backtests"]
    reasons: list[str] = []
    if snapshot.get("method") != EXPLICIT_WALK_FORWARD_METHOD or not bool(
        snapshot.get("acceptance_eligible")
    ):
        reasons.append(
            "Explicit walk-forward train/test windows are required; automatic "
            "trade slices are diagnostic only"
        )
    window_count = int(snapshot.get("window_count") or 0)
    valid_window_count = int(snapshot.get("valid_window_count") or 0)
    invalid_window_count = int(snapshot.get("invalid_window_count") or 0)
    pass_rate = Decimal(str(snapshot.get("pass_rate") or "0"))
    if invalid_window_count:
        reasons.append(
            f"Walk-forward windows contain {invalid_window_count} invalid definition(s)"
        )
    if valid_window_count < criteria.min_walk_forward_windows:
        reasons.append(
            "Walk-forward windows "
            f"{valid_window_count} valid of {window_count} declared; "
            f"minimum {criteria.min_walk_forward_windows}"
        )
    if pass_rate < criteria.min_walk_forward_pass_rate:
        reasons.append(
            "Walk-forward pass rate "
            f"{pass_rate} below minimum {criteria.min_walk_forward_pass_rate}"
        )
    return reasons


def trade_distribution_reasons(
    trades: list[BacktestTradeInput],
    criteria: AcceptanceCriteria,
) -> list[str]:
    snapshot = trade_distribution_snapshot(trades)
    reasons: list[str] = []
    dated_count = int(snapshot["dated_trade_count"] or 0)
    total_count = int(snapshot.get("total_trade_count") or len(trades))
    active_days = int(snapshot["active_trading_days"] or 0)
    max_share = Decimal(str(snapshot["max_single_day_trade_share"]))
    if dated_count < total_count:
        reasons.append("Every backtest trade requires a closed_at timestamp")
    if active_days < criteria.min_active_trading_days:
        reasons.append(
            "Backtest active trading days "
            f"{active_days} below minimum {criteria.min_active_trading_days}"
        )
    if max_share > criteria.max_single_day_trade_share:
        reasons.append(
            "Backtest single-day trade share "
            f"{max_share} exceeds limit {criteria.max_single_day_trade_share}"
        )
    return reasons


def market_regime_reasons(trades: list[BacktestTradeInput]) -> list[str]:
    snapshot = market_regime_breakdown_snapshot(trades)
    missing_count = int(snapshot["missing_market_regime_count"])
    if missing_count > 0:
        return [
            "Every backtest trade requires market_regime for regime analysis "
            f"({missing_count} missing)"
        ]
    if trades and int(snapshot["regime_count"]) == 0:
        return ["Backtest requires at least one market regime breakdown"]
    return []


def sample_window_reasons(payload: BacktestReportCreate) -> list[str]:
    windows = [
        payload.in_sample_start,
        payload.in_sample_end,
        payload.out_of_sample_start,
        payload.out_of_sample_end,
    ]
    if any(value is None for value in windows):
        return ["In-sample and out-of-sample windows are required"]

    assert payload.in_sample_start is not None
    assert payload.in_sample_end is not None
    assert payload.out_of_sample_start is not None
    assert payload.out_of_sample_end is not None
    in_start = ensure_utc(payload.in_sample_start)
    in_end = ensure_utc(payload.in_sample_end)
    out_start = ensure_utc(payload.out_of_sample_start)
    out_end = ensure_utc(payload.out_of_sample_end)
    data_start = ensure_utc(payload.data_start)
    data_end = ensure_utc(payload.data_end)

    reasons: list[str] = []
    if data_start > in_start:
        reasons.append("In-sample window starts before the data range")
    if in_start > in_end:
        reasons.append("In-sample window start must be before its end")
    if in_end >= out_start:
        reasons.append("Out-of-sample window must start after the in-sample window ends")
    if out_start > out_end:
        reasons.append("Out-of-sample window start must be before its end")
    if out_end > data_end:
        reasons.append("Out-of-sample window ends after the data range")
    if (payload.holdout_start is None) != (payload.holdout_end is None):
        reasons.append("Holdout window requires both start and end")
    if payload.holdout_start is not None and payload.holdout_end is not None:
        holdout_start = ensure_utc(payload.holdout_start)
        holdout_end = ensure_utc(payload.holdout_end)
        if out_end >= holdout_start:
            reasons.append(
                "Holdout window must start after the out-of-sample window ends"
            )
        if holdout_start > holdout_end:
            reasons.append("Holdout window start must be before its end")
        if holdout_end > data_end:
            reasons.append("Holdout window ends after the data range")
    return reasons


def out_of_sample_reasons(
    metrics: BacktestMetrics,
    criteria: AcceptanceCriteria,
) -> list[str]:
    reasons: list[str] = []
    if metrics.total_trades < criteria.min_out_of_sample_trades:
        reasons.append(
            "Out-of-sample trades "
            f"{metrics.total_trades} below minimum {criteria.min_out_of_sample_trades}"
        )
    if criteria.require_out_of_sample_positive_expectancy and metrics.expectancy <= 0:
        reasons.append(f"Out-of-sample expectancy {metrics.expectancy} is not positive")
    if metrics.profit_factor is not None:
        if metrics.profit_factor < criteria.min_out_of_sample_profit_factor:
            reasons.append(
                "Out-of-sample profit factor "
                f"{metrics.profit_factor} below minimum "
                f"{criteria.min_out_of_sample_profit_factor}"
            )
    elif metrics.total_trades == 0 or metrics.wins == 0:
        reasons.append("Out-of-sample profit factor unavailable because there are no wins")
    return reasons


def build_config_hash(payload: BacktestReportCreate) -> str:
    config: dict[str, Any] = {
        "strategy": payload.strategy,
        "strategy_version": payload.strategy_version,
        "symbols": payload.symbols,
        "timeframe": payload.timeframe,
        "data_source": payload.data_source,
        "source_format": payload.source_format,
        "source_artifact_hash": payload.source_artifact_hash,
        "csv_timezone": payload.csv_timezone,
        "source_reference": payload.source_reference,
        "data_start": ensure_utc(payload.data_start).isoformat(),
        "data_end": ensure_utc(payload.data_end).isoformat(),
        "in_sample_start": optional_iso(payload.in_sample_start),
        "in_sample_end": optional_iso(payload.in_sample_end),
        "out_of_sample_start": optional_iso(payload.out_of_sample_start),
        "out_of_sample_end": optional_iso(payload.out_of_sample_end),
        "holdout_start": optional_iso(payload.holdout_start),
        "holdout_end": optional_iso(payload.holdout_end),
        "tested_variant_count": payload.tested_variant_count,
        "variant_registry_hash": payload.variant_registry_hash,
        "parameters": payload.parameters,
        "cost_model": payload.cost_model,
        "slippage_model": payload.slippage_model,
        "risk_snapshot": payload.risk_snapshot,
        "walk_forward_windows": [
            window.model_dump(mode="json") for window in payload.walk_forward_windows
        ],
        "acceptance_criteria": payload.acceptance_criteria.model_dump(mode="json"),
    }
    serialized = json.dumps(config, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(serialized.encode("utf-8")).hexdigest()


def backtest_cost_evidence_snapshot(payload: BacktestReportCreate) -> dict[str, object]:
    trade_count = len(payload.trades)
    fees_provided = sum(1 for trade in payload.trades if trade.fees is not None)
    slippage_provided = sum(
        1 for trade in payload.trades if trade.slippage is not None
    )
    return {
        "realized_pl_semantics": "reported_net_pl",
        "trade_count": trade_count,
        "fees_provided_count": fees_provided,
        "fees_missing_count": trade_count - fees_provided,
        "slippage_provided_count": slippage_provided,
        "slippage_missing_count": trade_count - slippage_provided,
        "cost_model_declared": bool(payload.cost_model),
        "slippage_model_declared": bool(payload.slippage_model),
        "missing_trade_costs_are_not_assumed_zero": True,
    }


def build_trade_evidence_hash(trades: list[BacktestTradeInput]) -> str:
    evidence = [
        {
            "sequence": trade.sequence or sequence,
            "external_trade_id": trade.external_trade_id,
            "source_format": trade.source_format,
            "strategy": trade.strategy,
            "symbol": trade.symbol,
            "direction": trade.direction.value if trade.direction else None,
            "entry_at": optional_iso(trade.entry_at),
            "closed_at": optional_iso(trade.closed_at),
            "entry_price": decimal_text(trade.entry_price, "0.00000001"),
            "exit_price": decimal_text(trade.exit_price, "0.00000001"),
            "quantity": decimal_text(trade.quantity, "0.000000000001"),
            "gross_pl": decimal_text(trade.gross_pl, "0.00000001"),
            "fees": decimal_text(trade.fees, "0.00000001"),
            "slippage": decimal_text(trade.slippage, "0.00000001"),
            "realized_pl": decimal_text(trade.realized_pl, "0.00000001"),
            "equity": decimal_text(trade.equity, "0.00000001"),
            "r_multiple": decimal_text(trade.r_multiple, "0.000001"),
            "market_regime": trade.market_regime,
        }
        for sequence, trade in enumerate(trades, start=1)
    ]
    serialized = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


def normalize_report_trade_evidence(
    payload: BacktestReportCreate,
) -> BacktestReportCreate:
    normalized: list[BacktestTradeInput] = []
    sequences: set[int] = set()
    default_symbol = single_symbol(payload.symbols)
    for position, trade in enumerate(payload.trades, start=1):
        sequence = trade.sequence or position
        if sequence in sequences:
            raise ValueError(f"Duplicate backtest trade sequence: {sequence}")
        sequences.add(sequence)
        normalized.append(
            trade.model_copy(
                update={
                    "sequence": sequence,
                    "strategy": trade.strategy or payload.strategy,
                    "symbol": (
                        trade.symbol.upper() if trade.symbol else default_symbol
                    ),
                }
            )
        )
    return payload.model_copy(update={"trades": normalized})


def persisted_backtest_trade(
    run: BacktestRun,
    trade: BacktestTradeInput,
    *,
    sequence: int,
) -> BacktestTrade:
    return BacktestTrade(
        backtest_run=run,
        sequence=sequence,
        external_trade_id=trade.external_trade_id,
        source_format=trade.source_format,
        strategy=trade.strategy or run.strategy,
        symbol=trade.symbol or single_symbol(run.symbols),
        direction=trade.direction,
        entry_at=ensure_optional_utc(trade.entry_at),
        closed_at=ensure_optional_utc(trade.closed_at),
        entry_price=trade.entry_price,
        exit_price=trade.exit_price,
        quantity=trade.quantity,
        gross_pl=trade.gross_pl,
        fees=trade.fees,
        slippage=trade.slippage,
        realized_pl=trade.realized_pl,
        equity=trade.equity,
        r_multiple=trade.r_multiple,
        market_regime=trade.market_regime,
        costs_snapshot={
            "realized_pl_semantics": "reported_net_pl",
            "fees_status": "PROVIDED" if trade.fees is not None else "MISSING",
            "slippage_status": (
                "PROVIDED" if trade.slippage is not None else "MISSING"
            ),
        },
        raw_row=trade.raw_row,
    )


def single_symbol(symbols: list | None) -> str | None:
    return str(symbols[0]).upper() if symbols and len(symbols) == 1 else None


def decimal_text(value: Decimal | None, quantum: str) -> str | None:
    if value is None:
        return None
    normalized = Decimal(str(value)).quantize(Decimal(quantum)).normalize()
    return format(normalized, "f")


def report_payload_from_csv_request(
    payload: BacktestReportCsvRequest,
) -> tuple[BacktestReportCreate, list[dict], str]:
    fieldnames, rows = normalized_csv_rows(payload.csv_text)
    source_format = detect_backtest_csv_format(payload.csv_format, fieldnames)
    allowed_symbols = {symbol.upper() for symbol in payload.symbols}
    if source_format == "aurex_csv":
        trades, row_results = parse_aurex_report_rows(
            rows,
            strategy=payload.strategy,
            allowed_symbols=allowed_symbols,
        )
    else:
        trades, row_results = parse_tradingview_report_rows(
            rows,
            strategy=payload.strategy,
            allowed_symbols=allowed_symbols,
            csv_timezone=payload.csv_timezone,
        )

    report_payload = BacktestReportCreate(
        protocol_id=payload.protocol_id,
        strategy=payload.strategy,
        strategy_version=payload.strategy_version,
        symbols=payload.symbols,
        timeframe=payload.timeframe,
        data_source=payload.data_source,
        source_format=source_format,
        source_artifact_hash=sha256(payload.csv_text.encode("utf-8")).hexdigest(),
        csv_timezone=payload.csv_timezone,
        source_reference=payload.source_reference,
        data_start=payload.data_start,
        data_end=payload.data_end,
        in_sample_start=payload.in_sample_start,
        in_sample_end=payload.in_sample_end,
        out_of_sample_start=payload.out_of_sample_start,
        out_of_sample_end=payload.out_of_sample_end,
        holdout_start=payload.holdout_start,
        holdout_end=payload.holdout_end,
        tested_variant_count=payload.tested_variant_count,
        variant_registry_hash=payload.variant_registry_hash,
        parameters=payload.parameters,
        cost_model=payload.cost_model,
        slippage_model=payload.slippage_model,
        risk_snapshot=payload.risk_snapshot,
        walk_forward_windows=payload.walk_forward_windows,
        trades=trades,
        acceptance_criteria=payload.acceptance_criteria,
    )
    return report_payload, row_results, source_format


def normalized_csv_rows(text: str) -> tuple[set[str], list[tuple[int, dict[str, Any]]]]:
    cleaned = text.lstrip("\ufeff")
    if not cleaned.strip():
        raise ValueError("Backtest report CSV is empty")
    try:
        dialect = csv.Sniffer().sniff(cleaned[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(cleaned), dialect=dialect)
    if reader.fieldnames is None:
        raise ValueError("Backtest report CSV must include a header row")

    header_pairs = [
        (fieldname, normalize_csv_header(fieldname))
        for fieldname in reader.fieldnames
        if fieldname is not None
    ]
    normalized_headers = {normalized for _, normalized in header_pairs}
    rows: list[tuple[int, dict[str, Any]]] = []
    for row_number, raw_row in enumerate(reader, start=2):
        if not any(str(value or "").strip() for value in raw_row.values()):
            continue
        normalized_row: dict[str, Any] = {
            normalized: raw_row.get(original)
            for original, normalized in header_pairs
        }
        normalized_row["__raw__"] = {
            str(key): value for key, value in raw_row.items() if key is not None
        }
        rows.append((row_number, normalized_row))
    return normalized_headers, rows


def normalize_csv_header(value: str) -> str:
    normalized = value.strip().lower().replace("#", " number ")
    normalized = normalized.replace("&", "_").replace("%", " percent ")
    return re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")


def detect_backtest_csv_format(requested: str, fieldnames: set[str]) -> str:
    aurex_ready = set(BACKTEST_REPORT_REQUIRED_HEADERS).issubset(fieldnames)
    tradingview_ready = all(
        (
            any(header in fieldnames for header in TRADINGVIEW_TRADE_NUMBER_HEADERS),
            any(header in fieldnames for header in TRADINGVIEW_TYPE_HEADERS),
            any(header in fieldnames for header in TRADINGVIEW_DATETIME_HEADERS),
            any(header in fieldnames for header in TRADINGVIEW_NET_PL_HEADERS),
        )
    )
    if requested == "aurex":
        if not aurex_ready:
            required = ", ".join(BACKTEST_REPORT_REQUIRED_HEADERS)
            raise ValueError(f"Backtest report CSV must include {required}")
        return "aurex_csv"
    if requested == "tradingview":
        if not tradingview_ready:
            required = ", ".join(TRADINGVIEW_REQUIRED_FIELDS)
            raise ValueError(
                "TradingView completed-trades CSV must provide semantic fields: "
                f"{required}"
            )
        return "tradingview"
    if aurex_ready:
        return "aurex_csv"
    if tradingview_ready:
        return "tradingview"
    if fieldnames.intersection(BACKTEST_REPORT_REQUIRED_HEADERS):
        required = ", ".join(BACKTEST_REPORT_REQUIRED_HEADERS)
        raise ValueError(f"Backtest report CSV must include {required}")
    raise ValueError(
        "Unsupported backtest CSV format; expected Aurex report columns or a "
        "TradingView completed-trades export"
    )


def parse_aurex_report_rows(
    rows: list[tuple[int, dict[str, Any]]],
    *,
    strategy: str,
    allowed_symbols: set[str],
) -> tuple[list[BacktestTradeInput], list[dict]]:
    row_results: list[dict] = []
    trades: list[BacktestTradeInput] = []
    for row_number, row in rows:
        try:
            trade = parse_backtest_report_csv_row(
                row,
                strategy=strategy,
                allowed_symbols=allowed_symbols,
            )
        except ValueError as exc:
            row_results.append(rejected_row(row_number, str(exc)))
            continue
        trade.sequence = len(trades) + 1
        trades.append(trade)
        row_results.append(ready_row(row_number, trade))
    return trades, row_results


def parse_tradingview_report_rows(
    rows: list[tuple[int, dict[str, Any]]],
    *,
    strategy: str,
    allowed_symbols: set[str],
    csv_timezone: str,
) -> tuple[list[BacktestTradeInput], list[dict]]:
    timezone = parse_timezone(csv_timezone)
    entry_rows: dict[str, dict[str, Any]] = {}
    entry_result_indexes: dict[str, int] = {}
    completed_trade_ids: set[str] = set()
    row_results: list[dict] = []
    trades: list[BacktestTradeInput] = []

    for row_number, row in rows:
        trade_id = first_text(row, TRADINGVIEW_TRADE_NUMBER_HEADERS)
        row_type = first_text(row, TRADINGVIEW_TYPE_HEADERS)
        if trade_id is None:
            row_results.append(rejected_row(row_number, "trade_number_is_required"))
            continue
        if row_type is None:
            row_results.append(rejected_row(row_number, "type_is_required"))
            continue

        if is_entry_type(row_type):
            entry_rows[trade_id] = row
            entry_result_indexes[trade_id] = len(row_results)
            row_results.append(
                {
                    "row_number": row_number,
                    "status": "SKIPPED",
                    "reason": "entry_row_waiting_for_completed_exit",
                    "external_trade_id": trade_id,
                }
            )
            continue

        if trade_id in completed_trade_ids:
            row_results.append(rejected_row(row_number, "duplicate_completed_trade_id"))
            continue

        try:
            trade = parse_tradingview_completed_trade(
                row,
                entry_row=entry_rows.get(trade_id),
                trade_id=trade_id,
                strategy=strategy,
                allowed_symbols=allowed_symbols,
                timezone=timezone,
            )
        except ValueError as exc:
            row_results.append(rejected_row(row_number, str(exc)))
            continue

        trade.sequence = len(trades) + 1
        trades.append(trade)
        completed_trade_ids.add(trade_id)
        row_results.append(ready_row(row_number, trade))
        entry_index = entry_result_indexes.get(trade_id)
        if entry_index is not None:
            row_results[entry_index]["reason"] = "entry_row_paired_with_exit"

    for trade_id, result_index in entry_result_indexes.items():
        if trade_id not in completed_trade_ids:
            row_results[result_index]["status"] = "REJECTED"
            row_results[result_index]["reason"] = "entry_row_missing_completed_exit"
    return trades, row_results


def parse_backtest_report_csv_row(
    row: dict[str, Any],
    strategy: str,
    allowed_symbols: set[str],
) -> BacktestTradeInput:
    row_strategy = empty_to_none(row.get("strategy"))
    if row_strategy is not None and row_strategy != strategy:
        raise ValueError("strategy_does_not_match_report")

    market_regime = required_text(row, "market_regime")
    row_symbol = empty_to_none(row.get("symbol"))
    if row_symbol is not None and row_symbol.upper() not in allowed_symbols:
        raise ValueError("symbol_outside_report_scope")

    try:
        return BacktestTradeInput(
            external_trade_id=empty_to_none(row.get("external_trade_id")),
            source_format="aurex_csv",
            realized_pl=required_decimal(row, "realized_pl"),
            symbol=row_symbol.upper() if row_symbol else single_symbol(sorted(allowed_symbols)),
            direction=parse_direction(empty_to_none(row.get("direction"))),
            entry_at=parse_optional_datetime(row.get("entry_at")),
            entry_price=decimal_or_none(row.get("entry_price")),
            exit_price=decimal_or_none(row.get("exit_price")),
            quantity=decimal_or_none(row.get("quantity")),
            gross_pl=decimal_or_none(row.get("gross_pl")),
            fees=non_negative_decimal_or_none(row.get("fees"), "fees"),
            slippage=non_negative_decimal_or_none(row.get("slippage"), "slippage"),
            equity=decimal_or_none(row.get("equity")),
            strategy=row_strategy or strategy,
            market_regime=market_regime,
            r_multiple=decimal_or_none(row.get("r_multiple")),
            closed_at=parse_datetime(required_text(row, "closed_at")),
            raw_row=dict(row.get("__raw__") or {}),
        )
    except Exception as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError("backtest_trade_row_invalid") from exc


def parse_tradingview_completed_trade(
    row: dict[str, Any],
    *,
    entry_row: dict[str, Any] | None,
    trade_id: str,
    strategy: str,
    allowed_symbols: set[str],
    timezone: ZoneInfo,
) -> BacktestTradeInput:
    row_type = first_text(row, TRADINGVIEW_TYPE_HEADERS)
    signal = first_text(entry_row or {}, TRADINGVIEW_SIGNAL_HEADERS) or first_text(
        row,
        TRADINGVIEW_SIGNAL_HEADERS,
    )
    direction = parse_direction(" ".join(value for value in (row_type, signal) if value))
    symbol = (
        first_text(row, TRADINGVIEW_SYMBOL_HEADERS)
        or first_text(entry_row or {}, TRADINGVIEW_SYMBOL_HEADERS)
        or single_symbol(sorted(allowed_symbols))
    )
    if symbol is None:
        raise ValueError("symbol_is_required_for_multi_symbol_report")
    normalized_symbol = symbol.upper().replace(" ", "")
    if normalized_symbol not in allowed_symbols:
        raise ValueError("symbol_outside_report_scope")

    closed_text = first_text(row, TRADINGVIEW_DATETIME_HEADERS)
    if closed_text is None:
        raise ValueError("date_time_is_required")
    realized_text = first_text(row, TRADINGVIEW_NET_PL_HEADERS)
    if realized_text is None:
        raise ValueError("net_pl_is_required_on_completed_trade")

    explicit_entry_text = first_text(row, TRADINGVIEW_ENTRY_DATETIME_HEADERS)
    entry_text = explicit_entry_text or first_text(
        entry_row or {},
        TRADINGVIEW_DATETIME_HEADERS,
    )
    entry_price_text = first_text(row, TRADINGVIEW_ENTRY_PRICE_HEADERS) or first_text(
        entry_row or {},
        TRADINGVIEW_PRICE_HEADERS,
    )
    exit_price_text = first_text(row, TRADINGVIEW_PRICE_HEADERS)
    quantity_text = first_text(row, TRADINGVIEW_QUANTITY_HEADERS) or first_text(
        entry_row or {},
        TRADINGVIEW_QUANTITY_HEADERS,
    )
    fees_text = first_text(row, TRADINGVIEW_FEES_HEADERS)
    slippage_text = first_text(row, TRADINGVIEW_SLIPPAGE_HEADERS)
    regime = infer_market_regime(signal)
    return BacktestTradeInput(
        external_trade_id=trade_id,
        source_format="tradingview",
        strategy=strategy,
        symbol=normalized_symbol,
        direction=direction,
        entry_at=parse_tradingview_datetime(entry_text, timezone) if entry_text else None,
        closed_at=parse_tradingview_datetime(closed_text, timezone),
        entry_price=parse_display_decimal(entry_price_text),
        exit_price=parse_display_decimal(exit_price_text),
        quantity=parse_display_decimal(quantity_text),
        gross_pl=parse_display_decimal(first_text(row, TRADINGVIEW_GROSS_PL_HEADERS)),
        fees=parse_non_negative_display_decimal(fees_text, "fees"),
        slippage=parse_non_negative_display_decimal(slippage_text, "slippage"),
        realized_pl=parse_required_display_decimal(realized_text, "net_pl"),
        equity=parse_display_decimal(first_text(row, TRADINGVIEW_EQUITY_HEADERS)),
        market_regime=regime,
        raw_row={
            "entry": dict((entry_row or {}).get("__raw__") or {}),
            "exit": dict(row.get("__raw__") or {}),
        },
    )


def ready_row(row_number: int, trade: BacktestTradeInput) -> dict[str, object]:
    return {
        "row_number": row_number,
        "status": "READY",
        "reason": None,
        "external_trade_id": trade.external_trade_id,
        "realized_pl": str(trade.realized_pl),
        "closed_at": trade.closed_at.isoformat() if trade.closed_at else None,
        "market_regime": trade.market_regime,
        "strategy": trade.strategy,
        "symbol": trade.symbol,
        "fees_status": "PROVIDED" if trade.fees is not None else "MISSING",
        "slippage_status": (
            "PROVIDED" if trade.slippage is not None else "MISSING"
        ),
    }


def rejected_row(row_number: int, reason: str) -> dict[str, object]:
    return {
        "row_number": row_number,
        "status": "REJECTED",
        "reason": reason,
    }


def first_text(row: dict[str, Any], headers: tuple[str, ...]) -> str | None:
    for header in headers:
        value = empty_to_none(row.get(header))
        if value is not None:
            return value
    return None


def is_entry_type(value: str) -> bool:
    normalized = value.strip().lower()
    return "entry" in normalized and "exit" not in normalized and "close" not in normalized


def parse_direction(value: str | None) -> Direction | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if "short" in normalized:
        return Direction.SHORT
    if "long" in normalized:
        return Direction.LONG
    return None


def infer_market_regime(signal: str | None) -> str | None:
    if signal is None:
        return None
    normalized = re.sub(r"[^A-Z0-9]+", "_", signal.upper()).strip("_")
    for regime in MarketRegime:
        if regime == MarketRegime.UNKNOWN:
            continue
        if regime.value in normalized:
            return regime.value
    return None


def parse_timezone(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown CSV timezone: {value}") from exc


def parse_tradingview_datetime(value: str, timezone: ZoneInfo) -> datetime:
    candidate = value.strip().replace("Z", "+00:00")
    parsed: datetime | None = None
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        for pattern in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
        ):
            try:
                parsed = datetime.strptime(candidate, pattern)
                break
            except ValueError:
                continue
    if parsed is None:
        raise ValueError("date_time_is_invalid")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone)
    return parsed.astimezone(UTC)


def parse_display_decimal(value: str | None) -> Decimal | None:
    if value is None or value.strip() == "":
        return None
    candidate = value.strip().replace("\u2212", "-")
    negative = candidate.startswith("(") and candidate.endswith(")")
    candidate = candidate.strip("()")
    candidate = re.sub(r"[^0-9.\-]", "", candidate.replace(",", ""))
    if candidate in {"", "-", ".", "-."}:
        raise ValueError("decimal_value_is_invalid")
    parsed = Decimal(candidate)
    return -parsed if negative and parsed > 0 else parsed


def parse_required_display_decimal(value: str, field: str) -> Decimal:
    parsed = parse_display_decimal(value)
    if parsed is None:
        raise ValueError(f"{field}_is_required")
    return parsed


def parse_non_negative_display_decimal(
    value: str | None,
    field: str,
) -> Decimal | None:
    parsed = parse_display_decimal(value)
    if parsed is not None and parsed < 0:
        raise ValueError(f"{field}_cannot_be_negative")
    return parsed


def backtest_report_csv_analysis_summary(
    payload: BacktestReportCreate,
    row_results: list[dict],
    metrics: BacktestMetrics,
    segments: BacktestSegments,
    acceptance_passed: bool,
    acceptance_reasons: list[str],
    protocol_audit: dict[str, object],
) -> dict:
    rejected_reasons: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    for row in row_results:
        status = row["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
        if status == "REJECTED":
            reason = row["reason"]
            rejected_reasons[reason] = rejected_reasons.get(reason, 0) + 1

    metrics_snapshot = build_metrics_snapshot(payload, metrics, segments)
    metrics_snapshot["backtest_protocol"] = protocol_audit
    return {
        "status_counts": status_counts,
        "rejected_reasons": rejected_reasons,
        "fix_queue": [
            {
                "reason": reason,
                "count": count,
                "rows": [
                    row["row_number"]
                    for row in row_results
                    if row["status"] == "REJECTED" and row["reason"] == reason
                ],
            }
            for reason, count in sorted(rejected_reasons.items())
        ],
        "diagnostic": backtest_report_csv_diagnostic(
            payload,
            row_results,
            metrics,
            acceptance_passed,
            acceptance_reasons,
            rejected_reasons,
        ),
        "config_hash": build_config_hash(payload),
        "acceptance_passed": acceptance_passed,
        "acceptance_reasons": acceptance_reasons,
        "metrics_snapshot": metrics_snapshot,
        "total_trades": metrics.total_trades,
        "total_net_pl": str(metrics.total_net_pl),
        "expectancy": str(metrics.expectancy),
        "profit_factor": str(metrics.profit_factor) if metrics.profit_factor else None,
        "max_drawdown": str(metrics.max_drawdown),
    }


def backtest_report_csv_diagnostic(
    payload: BacktestReportCreate,
    row_results: list[dict],
    metrics: BacktestMetrics,
    acceptance_passed: bool,
    acceptance_reasons: list[str],
    rejected_reasons: dict[str, int],
) -> dict[str, object]:
    if not row_results:
        return {
            "status": "NO_COMPLETED_TRADE_ROWS",
            "reasons": ["csv_contains_headers_but_no_trade_rows"],
            "next_action": (
                "Confirm the Pine strategy creates closed trades in Strategy Tester, "
                "extend the chart/date range if needed, then export the List of Trades."
            ),
        }

    if metrics.total_trades == 0:
        if "entry_row_missing_completed_exit" in rejected_reasons:
            return {
                "status": "ENTRY_ROWS_WITHOUT_COMPLETED_EXITS",
                "reasons": ["tradingview_entries_have_no_completed_exits"],
                "next_action": (
                    "Wait for exits or extend the backtest window; Aurex imports only "
                    "completed TradingView trades with entry and exit evidence."
                ),
            }
        return {
            "status": "NO_IMPORTABLE_COMPLETED_TRADES",
            "reasons": sorted(rejected_reasons) or ["no_completed_trades_importable"],
            "next_action": (
                "Fix the rejected rows or export the completed-trades list from "
                "TradingView before importing evidence."
            ),
        }

    if rejected_reasons:
        return {
            "status": "ROW_REJECTIONS_PRESENT",
            "reasons": sorted(rejected_reasons),
            "next_action": (
                "Fix rejected rows before importing; Aurex does not import "
                "partial evidence."
            ),
        }

    if not acceptance_passed:
        return {
            "status": "EVIDENCE_GATE_BLOCKED",
            "reasons": acceptance_reasons,
            "next_action": (
                "You may import the rejected evidence record, but it cannot unlock paper "
                "or live readiness until a stronger backtest passes."
            ),
        }

    return {
        "status": "READY_FOR_IMPORT",
        "reasons": [],
        "next_action": "Import this report, then continue to forward paper evidence.",
    }


def required_text(row: dict[str, str | None], field: str) -> str:
    value = row.get(field)
    if value is None or value.strip() == "":
        raise ValueError(f"{field}_is_required")
    return value.strip()


def required_decimal(row: dict[str, str | None], field: str) -> Decimal:
    return Decimal(required_text(row, field))


def load_ohlcv_csv(text: str) -> list[OhlcvCandle]:
    reader = csv.DictReader(io.StringIO(text))
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
        raise ValueError("OHLCV CSV must include timestamp, open, high, low, close, volume")

    return [
        OhlcvCandle(
            timestamp=parse_datetime(row["timestamp"]),
            open=Decimal(row["open"]),
            high=Decimal(row["high"]),
            low=Decimal(row["low"]),
            close=Decimal(row["close"]),
            volume=Decimal(row["volume"]),
        )
        for row in reader
    ]


def load_trade_csv(text: str) -> list[BacktestTradeInput]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or "realized_pl" not in set(reader.fieldnames):
        raise ValueError("Trade CSV must include realized_pl")

    trades: list[BacktestTradeInput] = []
    for row in reader:
        trades.append(
            BacktestTradeInput(
                realized_pl=Decimal(row["realized_pl"]),
                equity=decimal_or_none(row.get("equity")),
                strategy=empty_to_none(row.get("strategy")),
                market_regime=empty_to_none(row.get("market_regime")),
                r_multiple=decimal_or_none(row.get("r_multiple")),
                closed_at=parse_optional_datetime(row.get("closed_at")),
            )
        )
    return trades


def sum_positive(trades: list[BacktestTradeInput]) -> Decimal:
    return sum((trade.realized_pl for trade in trades if trade.realized_pl > 0), ZERO)


def sum_negative_abs(trades: list[BacktestTradeInput]) -> Decimal:
    return sum((abs(trade.realized_pl) for trade in trades if trade.realized_pl < 0), ZERO)


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return ensure_utc(parsed)


def parse_optional_datetime(value: str | None) -> datetime | None:
    if value is None or value == "":
        return None
    return parse_datetime(value)


def decimal_or_none(value: str | None) -> Decimal | None:
    if value is None or value.strip() == "":
        return None
    return Decimal(value.strip())


def non_negative_decimal_or_none(
    value: str | None,
    field: str,
) -> Decimal | None:
    parsed = decimal_or_none(value)
    if parsed is not None and parsed < 0:
        raise ValueError(f"{field}_cannot_be_negative")
    return parsed


def empty_to_none(value: str | None) -> str | None:
    if value is None or value.strip() == "":
        return None
    return value.strip()


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def ensure_optional_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return ensure_utc(value)


def optional_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return ensure_utc(value).isoformat()
