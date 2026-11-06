from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from aurex.backtest_engine.schemas import BacktestTradeInput
from aurex.backtest_engine.service import (
    DEFAULT_BACKTEST_COST_MODELS,
    DEFAULT_BACKTEST_SLIPPAGE_MODELS,
    EXPLICIT_WALK_FORWARD_METHOD,
    accepted_backtest_strategy_parameter_reasons,
    build_backtest_protocol_hash,
    build_trade_evidence_hash,
    ensure_utc,
    strategy_parameter_evidence_snapshot,
    strategy_parameter_fingerprint,
    strategy_source_evidence,
    walk_forward_evidence_hash,
)
from aurex.db.models import BacktestResult, BacktestRun
from aurex.strategy_engine.registry import REGISTERED_STRATEGIES

MIN_PAPER_BACKTEST_TRADES = 100
MIN_PAPER_BACKTEST_OOS_TRADES = 30
MIN_PAPER_BACKTEST_OOS_PROFIT_FACTOR = Decimal("1.15")
MIN_PAPER_BACKTEST_ACTIVE_DAYS = 15
MAX_PAPER_BACKTEST_SINGLE_DAY_SHARE = Decimal("0.25")
MIN_PAPER_BACKTEST_WALK_FORWARD_WINDOWS = 3
MIN_PAPER_BACKTEST_WALK_FORWARD_PASS_RATE = Decimal("0.66")
CORE_PINE_SOURCE_POLICY = "core_pine_tradingview_export_v2"
CORE_PINE_REQUIRED_TRADE_FIELDS = (
    "external_trade_id",
    "direction",
    "entry_at",
    "closed_at",
    "entry_price",
    "exit_price",
    "quantity",
    "fees",
)


@dataclass(frozen=True)
class PaperBacktestEligibility:
    approved: bool
    reason: str
    backtest_run_id: str | None
    evidence_snapshot: dict


def paper_backtest_eligibility(
    session: Session,
    *,
    strategy: str,
    symbol: str,
) -> PaperBacktestEligibility:
    candidates = list(
        session.execute(
            select(BacktestRun)
            .where(BacktestRun.strategy == strategy)
            .order_by(BacktestRun.created_at.desc())
        ).scalars()
    )
    fallback: PaperBacktestEligibility | None = None
    for run in candidates:
        run_symbols = {item.upper() for item in run.symbols or []}
        if symbol.upper() not in run_symbols:
            continue

        audit = audit_paper_backtest_run(run)
        if audit.approved:
            return audit
        if fallback is None:
            fallback = audit

    return fallback or PaperBacktestEligibility(
        approved=False,
        reason="accepted_backtest_missing_for_paper_trading",
        backtest_run_id=None,
        evidence_snapshot={
            "strategy": strategy,
            "symbol": symbol.upper(),
            "requirements": paper_backtest_requirements(),
            "reasons": ["accepted_backtest_missing_for_paper_trading"],
        },
    )


def audit_paper_backtest_run(run: BacktestRun) -> PaperBacktestEligibility:
    result = run.result
    reasons: list[str] = []
    if result is None:
        reasons.append("accepted_backtest_result_missing")
    elif result.acceptance_passed is not True:
        reasons.append("accepted_backtest_report_not_accepted")
    else:
        reasons.extend(persisted_trade_evidence_reasons(run, result))
        reasons.extend(persisted_backtest_protocol_reasons(run, result))
        reasons.extend(accepted_backtest_strategy_parameter_reasons(run))
        reasons.extend(accepted_backtest_source_reasons(run))
        if result.total_trades < MIN_PAPER_BACKTEST_TRADES:
            reasons.append("accepted_backtest_minimum_trades_not_met")
        max_drawdown_limit = snapshot_decimal(result.acceptance_snapshot or {}, "max_drawdown")
        if max_drawdown_limit is None:
            reasons.append("accepted_backtest_max_drawdown_limit_missing")
        elif result.max_drawdown is not None and result.max_drawdown > max_drawdown_limit:
            reasons.append("accepted_backtest_max_drawdown_exceeds_declared_limit")

        metrics_snapshot = result.metrics_snapshot or {}
        out_of_sample = metrics_snapshot.get("out_of_sample")
        trade_distribution = metrics_snapshot.get("trade_distribution")
        market_regime = metrics_snapshot.get("market_regime_breakdown")
        walk_forward = metrics_snapshot.get("walk_forward")
        reasons.extend(out_of_sample_reasons(out_of_sample))
        reasons.extend(distribution_reasons(trade_distribution, result.total_trades))
        reasons.extend(market_regime_reasons(market_regime))
        reasons.extend(walk_forward_reasons(walk_forward))

    if any(
        value is None
        for value in (
            run.in_sample_start,
            run.in_sample_end,
            run.out_of_sample_start,
            run.out_of_sample_end,
        )
    ):
        reasons.append("accepted_backtest_sample_windows_missing")
    elif run.in_sample_end is not None and run.out_of_sample_start is not None:
        if run.in_sample_end >= run.out_of_sample_start:
            reasons.append("accepted_backtest_sample_windows_overlap")

    if not run.cost_model:
        reasons.append("accepted_backtest_cost_model_missing")
    if not run.slippage_model:
        reasons.append("accepted_backtest_slippage_model_missing")
    if not run.risk_snapshot:
        reasons.append("accepted_backtest_risk_snapshot_missing")

    approved = not reasons
    return PaperBacktestEligibility(
        approved=approved,
        reason="accepted_backtest_ready_for_paper_trading"
        if approved
        else reasons[0],
        backtest_run_id=run.id,
        evidence_snapshot={
            "backtest_run_id": run.id,
            "strategy": run.strategy,
            "strategy_version": run.strategy_version,
            "symbols": run.symbols or [],
            "config_hash": run.config_hash,
            "strategy_parameter_fingerprint": strategy_parameter_fingerprint(
                run.strategy,
                run.parameters or {},
            ),
            "requirements": paper_backtest_requirements(),
            "strategy_parameter_evidence": strategy_parameter_evidence_snapshot(
                run.strategy,
                run.parameters or {},
            ),
            "source_evidence": accepted_backtest_source_evidence(run),
            "reasons": reasons,
        },
    )


def accepted_backtest_source_reasons(run: BacktestRun) -> list[str]:
    return list(accepted_backtest_source_evidence(run)["reasons"])


def accepted_backtest_source_evidence(run: BacktestRun) -> dict[str, object]:
    source_required = run.strategy in REGISTERED_STRATEGIES
    definition = REGISTERED_STRATEGIES.get(run.strategy)
    current_source = strategy_source_evidence(run.strategy, run.strategy_version)
    protocol_source = (
        (run.protocol.protocol_snapshot or {}).get("strategy_source_evidence")
        if run.protocol is not None
        else None
    )
    expected_cost_model = DEFAULT_BACKTEST_COST_MODELS.get(run.strategy, {})
    expected_slippage_model = DEFAULT_BACKTEST_SLIPPAGE_MODELS.get(run.strategy, {})
    trades = list(run.trades or [])
    missing_field_counts = {
        field: sum(1 for trade in trades if getattr(trade, field) is None)
        for field in CORE_PINE_REQUIRED_TRADE_FIELDS
    }
    trade_source_counts: dict[str, int] = {}
    for trade in trades:
        trade_source_counts[trade.source_format] = (
            trade_source_counts.get(trade.source_format, 0) + 1
        )

    reasons: list[str] = []
    if source_required:
        if definition is not None and run.strategy_version != definition.version:
            reasons.append("accepted_backtest_strategy_version_not_current")
        if not isinstance(protocol_source, dict):
            reasons.append("accepted_backtest_strategy_source_evidence_missing")
        else:
            recorded_hash = protocol_source.get("pine_source_sha256")
            if not recorded_hash or recorded_hash != current_source.get(
                "pine_source_sha256"
            ):
                reasons.append("accepted_backtest_pine_source_hash_mismatch")
        if not current_source.get("ready"):
            reasons.append("accepted_backtest_strategy_source_not_ready")
        if run.source_format != "tradingview":
            reasons.append("accepted_backtest_source_format_not_tradingview")
        if not run.source_artifact_hash:
            reasons.append("accepted_backtest_source_artifact_hash_missing")
        elif len(run.source_artifact_hash) != 64 or any(
            character not in "0123456789abcdef"
            for character in run.source_artifact_hash
        ):
            reasons.append("accepted_backtest_source_artifact_hash_invalid")
        if run.data_source != "tradingview-export":
            reasons.append("accepted_backtest_data_source_not_tradingview_export")
        if not str(run.source_reference or "").startswith(
            "tradingview://strategy-tester/"
        ):
            reasons.append("accepted_backtest_source_reference_not_tradingview")
        if trade_source_counts and set(trade_source_counts) != {"tradingview"}:
            reasons.append("accepted_backtest_trade_source_format_mismatch")
        if any(missing_field_counts.values()):
            reasons.append("accepted_backtest_required_trade_fields_missing")
        if dict(run.cost_model or {}) != dict(expected_cost_model):
            reasons.append("accepted_backtest_cost_model_mismatch")
        if dict(run.slippage_model or {}) != dict(expected_slippage_model):
            reasons.append("accepted_backtest_slippage_model_mismatch")

    return {
        "policy": CORE_PINE_SOURCE_POLICY,
        "source_required": source_required,
        "trusted": not reasons,
        "expected_strategy_version": definition.version if definition is not None else None,
        "actual_strategy_version": run.strategy_version,
        "recorded_strategy_source_evidence": protocol_source,
        "current_strategy_source_evidence": current_source,
        "source_format": run.source_format,
        "source_artifact_hash": run.source_artifact_hash,
        "data_source": run.data_source,
        "source_reference": run.source_reference,
        "trade_count": len(trades),
        "trade_source_format_counts": trade_source_counts,
        "required_trade_fields": list(CORE_PINE_REQUIRED_TRADE_FIELDS),
        "missing_trade_field_counts": missing_field_counts,
        "expected_cost_model": dict(expected_cost_model),
        "actual_cost_model": dict(run.cost_model or {}),
        "expected_slippage_model": dict(expected_slippage_model),
        "actual_slippage_model": dict(run.slippage_model or {}),
        "trust_basis": "parsed_tradingview_csv_schema_and_bound_sha256",
        "authenticity_limitation": (
            "operator_supplied_export_not_cryptographically_attested_by_tradingview"
        ),
        "reasons": reasons,
    }


def persisted_trade_evidence_reasons(
    run: BacktestRun,
    result: BacktestResult,
) -> list[str]:
    reasons: list[str] = []
    persisted_trades = list(run.trades or [])
    if result.total_trades > 0 and not persisted_trades:
        reasons.append("accepted_backtest_persisted_trades_missing")
    if len(persisted_trades) != result.total_trades:
        reasons.append("accepted_backtest_persisted_trade_count_mismatch")
    if not run.evidence_hash:
        reasons.append("accepted_backtest_evidence_hash_missing")
        return reasons

    metrics_hash = (result.metrics_snapshot or {}).get("trade_evidence_hash")
    if metrics_hash != run.evidence_hash:
        reasons.append("accepted_backtest_metrics_evidence_hash_mismatch")
    persisted_hash = build_trade_evidence_hash(
        [
            BacktestTradeInput(
                sequence=trade.sequence,
                external_trade_id=trade.external_trade_id,
                source_format=trade.source_format,
                strategy=trade.strategy,
                symbol=trade.symbol,
                direction=trade.direction,
                entry_at=trade.entry_at,
                closed_at=trade.closed_at,
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
            )
            for trade in persisted_trades
        ]
    )
    if persisted_hash != run.evidence_hash:
        reasons.append("accepted_backtest_persisted_trade_hash_mismatch")
    return reasons


def persisted_backtest_protocol_reasons(
    run: BacktestRun,
    result: BacktestResult,
) -> list[str]:
    reasons: list[str] = []
    protocol = run.protocol
    if not run.protocol_id:
        return ["accepted_backtest_protocol_missing"]
    if protocol is None:
        return ["accepted_backtest_protocol_record_missing"]
    if not run.protocol_evidence_hash:
        reasons.append("accepted_backtest_protocol_hash_missing")
    current_hash = build_backtest_protocol_hash(protocol.protocol_snapshot)
    if current_hash != protocol.protocol_hash:
        reasons.append("accepted_backtest_protocol_integrity_mismatch")
    if run.protocol_evidence_hash != protocol.protocol_hash:
        reasons.append("accepted_backtest_protocol_run_hash_mismatch")
    if protocol.backtest_run is None or protocol.backtest_run.id != run.id:
        reasons.append("accepted_backtest_protocol_consumption_mismatch")
    if ensure_utc(protocol.registered_at) >= ensure_utc(run.created_at):
        reasons.append("accepted_backtest_protocol_not_registered_before_report")
    metrics_protocol = (result.metrics_snapshot or {}).get("backtest_protocol")
    if not isinstance(metrics_protocol, dict):
        reasons.append("accepted_backtest_protocol_metrics_missing")
    else:
        if metrics_protocol.get("status") != "MATCHED":
            reasons.append("accepted_backtest_protocol_metrics_not_matched")
        if metrics_protocol.get("protocol_id") != protocol.id:
            reasons.append("accepted_backtest_protocol_metrics_id_mismatch")
        if metrics_protocol.get("protocol_hash") != protocol.protocol_hash:
            reasons.append("accepted_backtest_protocol_metrics_hash_mismatch")
    return reasons


def out_of_sample_reasons(snapshot: object) -> list[str]:
    if not isinstance(snapshot, dict):
        return ["accepted_backtest_out_of_sample_metrics_missing"]
    reasons: list[str] = []
    trades = snapshot_int(snapshot, "total_trades")
    expectancy = snapshot_decimal(snapshot, "expectancy")
    profit_factor = snapshot_decimal(snapshot, "profit_factor")
    if trades < MIN_PAPER_BACKTEST_OOS_TRADES:
        reasons.append("accepted_backtest_oos_minimum_trades_not_met")
    if expectancy is None or expectancy <= 0:
        reasons.append("accepted_backtest_oos_expectancy_not_positive")
    if profit_factor is not None and profit_factor < MIN_PAPER_BACKTEST_OOS_PROFIT_FACTOR:
        reasons.append("accepted_backtest_oos_profit_factor_below_minimum")
    return reasons


def distribution_reasons(snapshot: object, total_trades: int) -> list[str]:
    if not isinstance(snapshot, dict):
        return ["accepted_backtest_trade_distribution_missing"]
    reasons: list[str] = []
    dated_trades = snapshot_int(snapshot, "dated_trade_count")
    active_days = snapshot_int(snapshot, "active_trading_days")
    max_share = snapshot_decimal(snapshot, "max_single_day_trade_share")
    if dated_trades < total_trades:
        reasons.append("accepted_backtest_closed_at_timestamps_missing")
    if active_days < MIN_PAPER_BACKTEST_ACTIVE_DAYS:
        reasons.append("accepted_backtest_active_trading_days_not_met")
    if max_share is not None and max_share > MAX_PAPER_BACKTEST_SINGLE_DAY_SHARE:
        reasons.append("accepted_backtest_trade_concentration_too_high")
    return reasons


def market_regime_reasons(snapshot: object) -> list[str]:
    if not isinstance(snapshot, dict):
        return ["accepted_backtest_market_regime_breakdown_missing"]
    if snapshot_int(snapshot, "missing_market_regime_count") > 0:
        return ["accepted_backtest_market_regime_missing"]
    if snapshot_int(snapshot, "regime_count") == 0:
        return ["accepted_backtest_market_regime_breakdown_empty"]
    return []


def walk_forward_reasons(snapshot: object) -> list[str]:
    if not isinstance(snapshot, dict):
        return ["accepted_backtest_walk_forward_missing"]
    reasons: list[str] = []
    if snapshot.get("method") != EXPLICIT_WALK_FORWARD_METHOD or not bool(
        snapshot.get("acceptance_eligible")
    ):
        reasons.append("accepted_backtest_walk_forward_not_explicit")
    if snapshot_int(snapshot, "invalid_window_count") > 0:
        reasons.append("accepted_backtest_walk_forward_windows_invalid")
    if (
        snapshot_int(snapshot, "valid_window_count")
        < MIN_PAPER_BACKTEST_WALK_FORWARD_WINDOWS
    ):
        reasons.append("accepted_backtest_walk_forward_windows_not_met")
    pass_rate = snapshot_decimal(snapshot, "pass_rate")
    if pass_rate is None or pass_rate < MIN_PAPER_BACKTEST_WALK_FORWARD_PASS_RATE:
        reasons.append("accepted_backtest_walk_forward_pass_rate_not_met")
    evidence_hash = snapshot.get("evidence_hash")
    if not isinstance(evidence_hash, str) or evidence_hash != walk_forward_evidence_hash(
        snapshot
    ):
        reasons.append("accepted_backtest_walk_forward_evidence_hash_mismatch")
    return reasons


def paper_backtest_requirements() -> dict[str, str | int]:
    return {
        "minimum_trades": MIN_PAPER_BACKTEST_TRADES,
        "minimum_out_of_sample_trades": MIN_PAPER_BACKTEST_OOS_TRADES,
        "minimum_out_of_sample_profit_factor": str(MIN_PAPER_BACKTEST_OOS_PROFIT_FACTOR),
        "minimum_active_trading_days": MIN_PAPER_BACKTEST_ACTIVE_DAYS,
        "maximum_single_day_trade_share": str(MAX_PAPER_BACKTEST_SINGLE_DAY_SHARE),
        "minimum_walk_forward_windows": MIN_PAPER_BACKTEST_WALK_FORWARD_WINDOWS,
        "minimum_walk_forward_pass_rate": str(MIN_PAPER_BACKTEST_WALK_FORWARD_PASS_RATE),
        "core_pine_source_policy": CORE_PINE_SOURCE_POLICY,
    }


def snapshot_int(snapshot: dict, key: str) -> int:
    value = snapshot.get(key)
    if value is None:
        return 0
    return int(value)


def snapshot_decimal(snapshot: dict, key: str) -> Decimal | None:
    value = snapshot.get(key)
    if value is None:
        return None
    return Decimal(str(value))
