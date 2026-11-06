import json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from hashlib import sha256

from aurex.backtest_engine.datasets import ensure_utc
from aurex.backtest_engine.schemas import ReferenceReplayTrade
from aurex.db.models import BacktestReferenceReplayRun

FAILURE_ANALYSIS_VERSION = "reference-replay-failure-analysis-v1.0.0"
FAILURE_ANALYSIS_SCHEMA_VERSION = "aurex-reference-replay-failure-analysis-v1"


def analyze_reference_replay_failure(
    replay: BacktestReferenceReplayRun,
) -> dict[str, object]:
    trades = [
        ReferenceReplayTrade.model_validate(item)
        for item in replay.result_snapshot.get("trades", [])
    ]
    if not trades:
        raise ValueError("reference_replay_failure_analysis_requires_trades")

    ordered = sorted(trades, key=lambda trade: (trade.closed_at, trade.sequence))
    by_direction = grouped_metrics(ordered, lambda trade: trade.direction.value)
    by_regime = grouped_metrics(ordered, lambda trade: trade.market_regime)
    by_year = grouped_metrics(ordered, lambda trade: str(ensure_utc(trade.closed_at).year))
    by_exit_reason = grouped_metrics(ordered, lambda trade: trade.exit_reason)
    by_duration = grouped_metrics(ordered, duration_bucket)
    summary = trade_metrics(ordered)
    monthly = grouped_metrics(
        ordered,
        lambda trade: ensure_utc(trade.closed_at).strftime("%Y-%m"),
    )
    monthly_net = {
        key: Decimal(str(value["total_net_pl"])) for key, value in monthly.items()
    }
    profitable_months = sum(value > 0 for value in monthly_net.values())
    losing_months = sum(value < 0 for value in monthly_net.values())
    flat_months = len(monthly_net) - profitable_months - losing_months
    best_month = max(monthly_net, key=monthly_net.get)
    worst_month = min(monthly_net, key=monthly_net.get)
    total_days = Decimal(
        str(
            max(
                1,
                (
                    ensure_utc(ordered[-1].closed_at)
                    - ensure_utc(ordered[0].entry_at)
                ).total_seconds()
                / 86400,
            )
        )
    )
    total_trades = Decimal(len(ordered))
    annualized_trades = total_trades * Decimal("365.25") / total_days
    duration_seconds = [
        Decimal(
            str(
                (
                    ensure_utc(trade.closed_at) - ensure_utc(trade.entry_at)
                ).total_seconds()
            )
        )
        for trade in ordered
    ]
    gross_before_costs = Decimal(str(summary["gross_before_modeled_costs"]))
    total_net_pl = Decimal(str(summary["total_net_pl"]))
    required_incremental_edge = max(Decimal("0"), -total_net_pl) / total_trades
    direction_values = list(by_direction.values())
    year_values = list(by_year.values())
    diagnoses: list[str] = []
    if gross_before_costs <= 0:
        diagnoses.append("mechanism_negative_before_modeled_costs")
    elif total_net_pl <= 0:
        diagnoses.append("modeled_costs_overwhelm_positive_gross_edge")
    if all(Decimal(str(item["total_net_pl"])) <= 0 for item in direction_values):
        diagnoses.append("both_directions_negative_net")
    if all(
        Decimal(str(item["gross_before_modeled_costs"])) <= 0
        for item in direction_values
    ):
        diagnoses.append("both_directions_negative_before_modeled_costs")
    if all(Decimal(str(item["total_net_pl"])) <= 0 for item in year_values):
        diagnoses.append("no_profitable_calendar_year_net")
    if profitable_months <= losing_months:
        diagnoses.append("profitable_months_do_not_outnumber_losing_months")

    payload: dict[str, object] = {
        "schema_version": FAILURE_ANALYSIS_SCHEMA_VERSION,
        "analysis_version": FAILURE_ANALYSIS_VERSION,
        "reference_replay_run_id": replay.id,
        "strategy": replay.strategy,
        "strategy_version": replay.strategy_version,
        "engine_version": replay.engine_version,
        "replay_record_evidence_hash": replay.record_evidence_hash,
        "engine_evidence_hash": replay.engine_evidence_hash,
        "dataset_id": replay.dataset_id,
        "dataset_evidence_hash": replay.dataset_evidence_hash,
        "development_only": True,
        "promotion_eligible": False,
        "summary": summary,
        "turnover": {
            "observed_days": decimal_string(total_days),
            "annualized_trades": decimal_string(annualized_trades),
            "average_holding_minutes": decimal_string(
                sum(duration_seconds, Decimal("0"))
                / total_trades
                / Decimal("60")
            ),
            "median_holding_minutes": decimal_string(
                decimal_median(duration_seconds) / Decimal("60")
            ),
        },
        "stability": {
            "calendar_months": len(monthly_net),
            "profitable_months": profitable_months,
            "losing_months": losing_months,
            "flat_months": flat_months,
            "best_month": {
                "month": best_month,
                "total_net_pl": decimal_string(monthly_net[best_month]),
            },
            "worst_month": {
                "month": worst_month,
                "total_net_pl": decimal_string(monthly_net[worst_month]),
            },
            "maximum_consecutive_losses": maximum_consecutive_losses(ordered),
        },
        "break_even_gap": {
            "additional_net_edge_required_total": decimal_string(
                max(Decimal("0"), -total_net_pl)
            ),
            "additional_net_edge_required_per_trade": decimal_string(
                required_incremental_edge
            ),
        },
        "by_direction": by_direction,
        "by_market_regime": by_regime,
        "by_calendar_year": by_year,
        "by_exit_reason": by_exit_reason,
        "by_holding_duration": by_duration,
        "diagnoses": diagnoses,
        "limitations": [
            "This report attributes recorded closed-trade outcomes; it does not infer causality.",
            "It does not model order-book depth, market impact, funding, or alternative fills.",
            "Observed data is development-contaminated and cannot become a new holdout.",
        ],
    }
    payload["analysis_evidence_hash"] = evidence_hash(payload)
    return payload


def grouped_metrics(
    trades: list[ReferenceReplayTrade],
    key_function,
) -> dict[str, dict[str, object]]:
    groups: dict[str, list[ReferenceReplayTrade]] = defaultdict(list)
    for trade in trades:
        groups[str(key_function(trade))].append(trade)
    return {key: trade_metrics(groups[key]) for key in sorted(groups)}


def trade_metrics(trades: list[ReferenceReplayTrade]) -> dict[str, object]:
    realized = [trade.realized_pl for trade in trades]
    fill_price_gross = [trade.gross_pl for trade in trades]
    pre_cost = [trade.realized_pl + trade.fees + trade.slippage for trade in trades]
    fees = sum((trade.fees for trade in trades), Decimal("0"))
    slippage = sum((trade.slippage for trade in trades), Decimal("0"))
    total_net = sum(realized, Decimal("0"))
    total_fill_price_gross = sum(fill_price_gross, Decimal("0"))
    total_pre_cost = sum(pre_cost, Decimal("0"))
    count = Decimal(len(trades))
    wins = sum(value > 0 for value in realized)
    losses = sum(value < 0 for value in realized)
    breakeven = len(trades) - wins - losses
    average_win = (
        sum((value for value in realized if value > 0), Decimal("0")) / Decimal(wins)
        if wins
        else Decimal("0")
    )
    average_loss = (
        abs(sum((value for value in realized if value < 0), Decimal("0")))
        / Decimal(losses)
        if losses
        else Decimal("0")
    )
    break_even_win_rate = (
        average_loss / (average_win + average_loss)
        if average_win + average_loss > 0
        else Decimal("0")
    )
    fill_reconciliation_delta = total_fill_price_gross - fees - total_net
    full_reconciliation_delta = total_pre_cost - fees - slippage - total_net
    return {
        "total_trades": len(trades),
        "wins": wins,
        "losses": losses,
        "breakeven": breakeven,
        "win_rate": decimal_string(Decimal(wins) / count),
        "break_even_win_rate_at_recorded_payoff": decimal_string(break_even_win_rate),
        "gross_before_modeled_costs": decimal_string(total_pre_cost),
        "fill_price_gross_pl": decimal_string(total_fill_price_gross),
        "total_fees": decimal_string(fees),
        "total_slippage": decimal_string(slippage),
        "total_modeled_costs": decimal_string(fees + slippage),
        "total_net_pl": decimal_string(total_net),
        "gross_expectancy": decimal_string(total_pre_cost / count),
        "net_expectancy": decimal_string(total_net / count),
        "modeled_cost_per_trade": decimal_string((fees + slippage) / count),
        "gross_profit_factor": optional_decimal_string(profit_factor(pre_cost)),
        "net_profit_factor": optional_decimal_string(profit_factor(realized)),
        "fill_price_gross_reconciliation_delta": decimal_string(
            fill_reconciliation_delta
        ),
        "fill_price_gross_reconciles_after_fees": decimal_is_close(
            fill_reconciliation_delta
        ),
        "reconciliation_delta": decimal_string(full_reconciliation_delta),
        "reconciles": decimal_is_close(full_reconciliation_delta),
    }


def profit_factor(values: list[Decimal]) -> Decimal | None:
    gains = sum((value for value in values if value > 0), Decimal("0"))
    losses = abs(sum((value for value in values if value < 0), Decimal("0")))
    if losses == 0:
        return None
    return gains / losses


def maximum_consecutive_losses(trades: list[ReferenceReplayTrade]) -> int:
    maximum = 0
    current = 0
    for trade in trades:
        if trade.realized_pl < 0:
            current += 1
            maximum = max(maximum, current)
        else:
            current = 0
    return maximum


def duration_bucket(trade: ReferenceReplayTrade) -> str:
    minutes = (
        ensure_utc(trade.closed_at) - ensure_utc(trade.entry_at)
    ).total_seconds() / 60
    if minutes <= 15:
        return "01_0_to_15_minutes"
    if minutes <= 60:
        return "02_15_to_60_minutes"
    if minutes <= 240:
        return "03_1_to_4_hours"
    if minutes <= 720:
        return "04_4_to_12_hours"
    if minutes <= 1440:
        return "05_12_to_24_hours"
    return "06_over_24_hours"


def decimal_median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / Decimal("2")


def decimal_string(value: Decimal) -> str:
    if not value:
        return "0"
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def optional_decimal_string(value: Decimal | None) -> str | None:
    return decimal_string(value) if value is not None else None


def decimal_is_close(value: Decimal) -> bool:
    return abs(value) <= Decimal("0.000000000000000001")


def evidence_hash(payload: dict[str, object]) -> str:
    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=json_default,
    )
    return sha256(serialized.encode()).hexdigest()


def json_default(value: object) -> str:
    if isinstance(value, datetime):
        return ensure_utc(value).isoformat()
    return str(value)
