import json
from decimal import Decimal, InvalidOperation, localcontext
from hashlib import sha256

from aurex.backtest_engine.schemas import ReferenceReplayValidationResponse

SLOW_BREAKOUT_SPOT_DECISION_SCHEMA_VERSION = (
    "aurex-slow-breakout-spot-cross-market-decision-v1"
)
SLOW_BREAKOUT_SPOT_EXPECTED_SYMBOLS = frozenset({"ETHUSDT", "SOLUSDT"})
SLOW_BREAKOUT_SPOT_REQUIRED_BINDINGS = frozenset(
    {
        "reference_replay_integrity",
        "dataset_integrity",
        "protocol_integrity",
        "strategy",
        "strategy_version",
        "symbol",
        "timeframe",
        "parameters",
        "backtest_start",
        "backtest_end",
        "commission_percent",
        "slippage_ticks",
        "risk_per_trade",
        "tick_size",
        "point_value",
        "minimum_contract",
        "protocol_registered_before_reference_replay",
    }
)
SLOW_BREAKOUT_SPOT_MIN_COMBINED_PROFIT_FACTOR = Decimal("1.15")
SLOW_BREAKOUT_SPOT_MAX_GROSS_PROFIT_SHARE = Decimal("0.70")
DECISION_DECIMAL_PRECISION = 28


def evaluate_slow_breakout_spot_cross_market(
    validations: list[ReferenceReplayValidationResponse | dict],
) -> dict:
    normalized = [
        item.model_dump(mode="json")
        if isinstance(item, ReferenceReplayValidationResponse)
        else dict(item)
        for item in validations
    ]
    ordered = sorted(normalized, key=lambda item: str(item.get("symbol", "")))
    reasons: list[str] = []
    symbols = {str(item.get("symbol", "")).upper() for item in ordered}
    if len(ordered) != 2 or symbols != SLOW_BREAKOUT_SPOT_EXPECTED_SYMBOLS:
        reasons.append("holdout_symbol_set_mismatch")

    market_snapshots: list[dict] = []
    combined_trades = 0
    combined_net = Decimal("0")
    combined_gross_profit = Decimal("0")
    combined_gross_loss = Decimal("0")
    combined_stress_net = Decimal("0")
    for validation in ordered:
        symbol = str(validation.get("symbol", "")).upper()
        if validation.get("strategy") != "slow_breakout_spot_v1":
            reasons.append(f"{symbol}:strategy_mismatch")
        if validation.get("strategy_version") != "1.0.0":
            reasons.append(f"{symbol}:strategy_version_mismatch")
        if validation.get("timeframe") != "4h":
            reasons.append(f"{symbol}:timeframe_mismatch")
        if (
            validation.get("status") != "PASSED"
            or validation.get("statistical_acceptance_passed") is not True
        ):
            reasons.append(f"{symbol}:individual_validation_failed")
        if not validation.get("validation_evidence_hash"):
            reasons.append(f"{symbol}:validation_evidence_hash_missing")

        binding_by_name = {
            str(check.get("name")): check
            for check in validation.get("binding_checks") or []
            if isinstance(check, dict)
        }
        missing_bindings = sorted(
            SLOW_BREAKOUT_SPOT_REQUIRED_BINDINGS - set(binding_by_name)
        )
        if missing_bindings:
            reasons.append(f"{symbol}:required_binding_missing")
        failed_bindings = sorted(
            name
            for name, check in binding_by_name.items()
            if check.get("status") != "PASS"
        )
        if failed_bindings:
            reasons.append(f"{symbol}:binding_failed")

        metrics = validation.get("metrics_snapshot") or {}
        total_trades = integer_metric(metrics, "total_trades", symbol, reasons)
        net_pl = decimal_metric(metrics, "total_net_pl", symbol, reasons)
        gross_profit = decimal_metric(metrics, "gross_profit", symbol, reasons)
        gross_loss = decimal_metric(metrics, "gross_loss", symbol, reasons)
        stress_net = cost_scenario_net(
            metrics,
            "stress_150_percent",
            symbol,
            reasons,
        )
        if net_pl is not None and net_pl < 0:
            reasons.append(f"{symbol}:base_net_negative")

        combined_trades += total_trades or 0
        combined_net = decimal_add(combined_net, net_pl or Decimal("0"))
        combined_gross_profit = decimal_add(
            combined_gross_profit,
            gross_profit or Decimal("0"),
        )
        combined_gross_loss = decimal_add(
            combined_gross_loss,
            gross_loss or Decimal("0"),
        )
        combined_stress_net = decimal_add(
            combined_stress_net,
            stress_net or Decimal("0"),
        )
        market_snapshots.append(
            {
                "symbol": symbol,
                "validation_evidence_hash": validation.get(
                    "validation_evidence_hash"
                ),
                "reference_replay_run_id": validation.get(
                    "reference_replay_run_id"
                ),
                "protocol_id": validation.get("protocol_id"),
                "total_trades": total_trades,
                "total_net_pl": decimal_text(net_pl),
                "gross_profit": decimal_text(gross_profit),
                "gross_loss": decimal_text(gross_loss),
                "stress_150_percent_net_pl": decimal_text(stress_net),
                "individual_validation_passed": (
                    validation.get("status") == "PASSED"
                    and validation.get("statistical_acceptance_passed") is True
                ),
                "required_bindings_present": not missing_bindings,
                "binding_checks_passed": not failed_bindings,
            }
        )

    combined_expectancy = (
        decimal_divide(combined_net, Decimal(combined_trades))
        if combined_trades > 0
        else Decimal("0")
    )
    combined_profit_factor = (
        decimal_divide(combined_gross_profit, combined_gross_loss)
        if combined_gross_loss > 0
        else None
    )
    if combined_net <= 0:
        reasons.append("combined_net_not_positive")
    if combined_expectancy <= 0:
        reasons.append("combined_expectancy_not_positive")
    if (
        combined_profit_factor is None
        or combined_profit_factor < SLOW_BREAKOUT_SPOT_MIN_COMBINED_PROFIT_FACTOR
    ):
        reasons.append("combined_profit_factor_below_gate")
    if combined_stress_net <= 0:
        reasons.append("combined_stress_150_percent_net_not_positive")

    gross_profit_shares: dict[str, str | None] = {}
    for market in market_snapshots:
        gross_profit = optional_decimal(market["gross_profit"])
        share = (
            decimal_divide(gross_profit, combined_gross_profit)
            if gross_profit is not None and combined_gross_profit > 0
            else None
        )
        gross_profit_shares[str(market["symbol"])] = decimal_text(share)
        if share is None or share > SLOW_BREAKOUT_SPOT_MAX_GROSS_PROFIT_SHARE:
            reasons.append(f"{market['symbol']}:gross_profit_concentration_exceeds_gate")

    reasons = list(dict.fromkeys(reasons))
    payload = {
        "schema_version": SLOW_BREAKOUT_SPOT_DECISION_SCHEMA_VERSION,
        "strategy": "slow_breakout_spot_v1",
        "strategy_version": "1.0.0",
        "symbols": sorted(SLOW_BREAKOUT_SPOT_EXPECTED_SYMBOLS),
        "gates": {
            "both_individual_validations_must_pass": True,
            "required_binding_checks_must_pass": sorted(
                SLOW_BREAKOUT_SPOT_REQUIRED_BINDINGS
            ),
            "min_combined_profit_factor": decimal_text(
                SLOW_BREAKOUT_SPOT_MIN_COMBINED_PROFIT_FACTOR
            ),
            "require_combined_positive_expectancy": True,
            "require_each_symbol_nonnegative_base_net": True,
            "require_combined_positive_stress_150_percent_net": True,
            "max_single_symbol_gross_profit_share": decimal_text(
                SLOW_BREAKOUT_SPOT_MAX_GROSS_PROFIT_SHARE
            ),
        },
        "markets": market_snapshots,
        "combined": {
            "total_trades": combined_trades,
            "total_net_pl": decimal_text(combined_net),
            "expectancy": decimal_text(combined_expectancy),
            "gross_profit": decimal_text(combined_gross_profit),
            "gross_loss": decimal_text(combined_gross_loss),
            "profit_factor": decimal_text(combined_profit_factor),
            "stress_150_percent_net_pl": decimal_text(combined_stress_net),
            "gross_profit_shares": gross_profit_shares,
        },
        "reasons": reasons,
    }
    evidence_hash = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        **payload,
        "status": "ACCEPT" if not reasons else "REJECT",
        "candidate_eligible_for_parity": not reasons,
        "candidate_eligible_for_paper": False,
        "decision_evidence_hash": evidence_hash,
    }


def decimal_metric(
    metrics: dict,
    key: str,
    symbol: str,
    reasons: list[str],
) -> Decimal | None:
    value = optional_decimal(metrics.get(key))
    if value is None:
        reasons.append(f"{symbol}:{key}_missing_or_invalid")
    return value


def integer_metric(
    metrics: dict,
    key: str,
    symbol: str,
    reasons: list[str],
) -> int | None:
    value = metrics.get(key)
    if isinstance(value, bool):
        reasons.append(f"{symbol}:{key}_missing_or_invalid")
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        reasons.append(f"{symbol}:{key}_missing_or_invalid")
        return None
    if parsed < 0:
        reasons.append(f"{symbol}:{key}_missing_or_invalid")
        return None
    return parsed


def cost_scenario_net(
    metrics: dict,
    name: str,
    symbol: str,
    reasons: list[str],
) -> Decimal | None:
    scenarios = (metrics.get("cost_sensitivity") or {}).get("scenarios") or []
    scenario = next(
        (
            item
            for item in scenarios
            if isinstance(item, dict) and item.get("name") == name
        ),
        None,
    )
    if scenario is None:
        reasons.append(f"{symbol}:{name}_missing")
        return None
    value = optional_decimal(scenario.get("total_net_pl"))
    if value is None:
        reasons.append(f"{symbol}:{name}_net_invalid")
    return value


def optional_decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def decimal_add(left: Decimal, right: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = DECISION_DECIMAL_PRECISION
        return left + right


def decimal_divide(numerator: Decimal, denominator: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = DECISION_DECIMAL_PRECISION
        return numerator / denominator


def decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    if value == 0:
        return "0"
    return format(value.normalize(), "f")
