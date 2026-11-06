import json
from datetime import datetime
from decimal import Decimal
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from aurex.backtest_engine.datasets import OhlcvDatasetLab, ensure_utc
from aurex.backtest_engine.reference_replay import ReferenceReplayEvidenceLab
from aurex.backtest_engine.schemas import (
    BacktestProtocolCreate,
    BacktestTradeInput,
    ReferenceReplayTrade,
    ReferenceReplayValidationAuditResponse,
    ReferenceReplayValidationRequest,
    ReferenceReplayValidationResponse,
)
from aurex.backtest_engine.service import (
    backtest_report_payload_from_protocol,
    build_backtest_protocol_hash,
    build_metrics_snapshot,
    build_trade_evidence_hash,
    calculate_backtest_metrics,
    calculate_backtest_segments,
    evaluate_acceptance,
)
from aurex.db.base import utc_now
from aurex.db.models import (
    BacktestProtocol,
    BacktestReferenceReplayRun,
    BacktestReferenceReplayValidation,
)
from aurex.observability.system_events import SystemEventRecorder

LEGACY_EVALUATOR_VERSION = "reference-replay-validation-v1.0.0"
COST_AUDIT_EVALUATOR_VERSION = "reference-replay-validation-v1.1.0"
EVALUATOR_VERSION = "reference-replay-validation-v1.2.0"
LEGACY_VALIDATION_SCHEMA_VERSION = "aurex-reference-replay-validation-v1"
COST_AUDIT_VALIDATION_SCHEMA_VERSION = "aurex-reference-replay-validation-v2"
VALIDATION_SCHEMA_VERSION = "aurex-reference-replay-validation-v3"
SUPPORTED_EVALUATOR_VERSIONS = frozenset(
    {
        LEGACY_EVALUATOR_VERSION,
        COST_AUDIT_EVALUATOR_VERSION,
        EVALUATOR_VERSION,
    }
)
COST_SENSITIVITY_SCENARIOS = (
    ("zero_cost_upper_bound", Decimal("0"), Decimal("0")),
    ("half_cost", Decimal("0.5"), Decimal("0.5")),
    ("base_case", Decimal("1"), Decimal("1")),
    ("stress_150_percent", Decimal("1.5"), Decimal("1.5")),
    ("stress_200_percent", Decimal("2"), Decimal("2")),
)


class ReferenceReplayValidationLab:
    def __init__(self, session: Session) -> None:
        self.session = session

    def preflight(
        self,
        request: ReferenceReplayValidationRequest,
        *,
        evaluator_version: str = EVALUATOR_VERSION,
    ) -> ReferenceReplayValidationResponse:
        return evaluate_reference_replay_validation(
            self.session,
            request,
            evaluator_version=evaluator_version,
        )

    def record(
        self,
        request: ReferenceReplayValidationRequest,
    ) -> tuple[BacktestReferenceReplayValidation, bool]:
        response = self.preflight(request)
        if response.status == "BLOCKED" or response.validation_evidence_hash is None:
            reasons = ", ".join(response.reasons) or "validation binding is blocked"
            raise ValueError(f"Reference replay validation cannot be recorded: {reasons}")

        existing = self.session.execute(
            select(BacktestReferenceReplayValidation).where(
                BacktestReferenceReplayValidation.validation_evidence_hash
                == response.validation_evidence_hash
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing, True

        recorded_at = utc_now()
        record = BacktestReferenceReplayValidation(
            reference_replay_run_id=response.reference_replay_run_id,
            protocol_id=response.protocol_id,
            dataset_id=response.dataset_id,
            strategy=response.strategy,
            strategy_version=response.strategy_version,
            symbol=response.symbol,
            timeframe=response.timeframe,
            evaluator_version=response.evaluator_version,
            status=response.status,
            statistical_acceptance_passed=response.statistical_acceptance_passed,
            replay_record_evidence_hash=response.replay_record_evidence_hash,
            engine_evidence_hash=response.engine_evidence_hash,
            dataset_evidence_hash=response.dataset_evidence_hash,
            protocol_hash=response.protocol_hash,
            trade_evidence_hash=str(response.trade_evidence_hash),
            validation_evidence_hash=response.validation_evidence_hash,
            request_snapshot=request.model_dump(mode="json"),
            metrics_snapshot=response.metrics_snapshot,
            acceptance_snapshot=response.acceptance_snapshot,
            binding_snapshot=response.binding_checks,
            reason_snapshot=response.acceptance_reasons,
            warning_snapshot=response.warnings,
            recorded_at=recorded_at,
        )
        self.session.add(record)
        self.session.flush()
        SystemEventRecorder(self.session).info(
            "backtest_reference_validation",
            "Immutable reference replay validation recorded",
            {
                "reference_replay_validation_id": record.id,
                "reference_replay_run_id": record.reference_replay_run_id,
                "protocol_id": record.protocol_id,
                "status": record.status,
                "statistical_acceptance_passed": (
                    record.statistical_acceptance_passed
                ),
                "validation_evidence_hash": record.validation_evidence_hash,
                "comparison_only": True,
                "promotion_eligible": False,
                "paper_eligible": False,
            },
            occurred_at=recorded_at,
        )
        self.session.flush()
        return record, False

    def list_runs(self, limit: int = 100) -> list[BacktestReferenceReplayValidation]:
        return list(
            self.session.execute(
                select(BacktestReferenceReplayValidation)
                .order_by(BacktestReferenceReplayValidation.recorded_at.desc())
                .limit(limit)
            ).scalars()
        )

    def get_run(
        self,
        validation_id: str,
    ) -> BacktestReferenceReplayValidation | None:
        return self.session.get(BacktestReferenceReplayValidation, validation_id)

    def audit(
        self,
        record: BacktestReferenceReplayValidation,
    ) -> ReferenceReplayValidationAuditResponse:
        current_hash = build_reference_validation_hash(
            reference_validation_record_payload(record)
        )
        record_matches = current_hash == record.validation_evidence_hash
        reasons: list[str] = []
        if not record_matches:
            reasons.append("reference_validation_record_evidence_hash_mismatch")

        replayed_hash: str | None = None
        source_matches = False
        evaluation_matches = False
        try:
            request = ReferenceReplayValidationRequest.model_validate(
                record.request_snapshot
            )
            replayed = self.preflight(
                request,
                evaluator_version=record.evaluator_version,
            )
            replayed_hash = replayed.validation_evidence_hash
            if replayed.status == "BLOCKED":
                reasons.append("reference_validation_source_recheck_blocked")
                reasons.extend(
                    f"reference_validation_source_{reason}"
                    for reason in replayed.reasons
                )
            source_matches = bool(
                replayed.replay_record_evidence_hash
                == record.replay_record_evidence_hash
                and replayed.engine_evidence_hash == record.engine_evidence_hash
                and replayed.dataset_evidence_hash == record.dataset_evidence_hash
                and replayed.protocol_hash == record.protocol_hash
                and replayed.trade_evidence_hash == record.trade_evidence_hash
            )
            evaluation_matches = replayed_hash == record.validation_evidence_hash
            if not source_matches:
                reasons.append("reference_validation_source_evidence_drift")
            if not evaluation_matches:
                reasons.append("reference_validation_evaluation_drift")
        except (LookupError, ValueError, TypeError) as exc:
            reasons.append(f"reference_validation_source_recheck_failed:{exc}")

        return ReferenceReplayValidationAuditResponse(
            reference_replay_validation_id=record.id,
            status="PASS" if not reasons else "BLOCKED",
            stored_validation_evidence_hash=record.validation_evidence_hash,
            current_validation_evidence_hash=current_hash,
            replayed_validation_evidence_hash=replayed_hash,
            record_evidence_hash_matches=record_matches,
            source_evidence_matches=source_matches,
            evaluation_matches=evaluation_matches,
            reasons=reasons,
            checked_at=utc_now(),
        )


def evaluate_reference_replay_validation(
    session: Session,
    request: ReferenceReplayValidationRequest,
    *,
    evaluator_version: str = EVALUATOR_VERSION,
) -> ReferenceReplayValidationResponse:
    if evaluator_version not in SUPPORTED_EVALUATOR_VERSIONS:
        raise ValueError(
            f"Unsupported reference replay evaluator version: {evaluator_version}"
        )
    replay = session.get(BacktestReferenceReplayRun, request.reference_replay_run_id)
    if replay is None:
        raise LookupError("Reference replay run not found")
    protocol = session.get(BacktestProtocol, request.protocol_id)
    if protocol is None:
        raise LookupError("Backtest protocol not found")
    dataset = OhlcvDatasetLab(session).get_dataset(replay.dataset_id)
    if dataset is None:
        raise LookupError("Reference replay dataset not found")

    replay_audit = ReferenceReplayEvidenceLab(session).audit(replay)
    dataset_audit = OhlcvDatasetLab(session).audit(dataset)
    protocol_current_hash = build_backtest_protocol_hash(protocol.protocol_snapshot)
    protocol_payload = BacktestProtocolCreate.model_validate(protocol.protocol_snapshot)
    replay_parameters = replay.request_snapshot.get("parameters", {})
    protocol_parameters = protocol_payload.parameters
    protocol_symbols = [symbol.upper() for symbol in protocol_payload.symbols]
    checks = [
        binding_check(
            "reference_replay_integrity",
            replay_audit.status == "PASS",
            replay_audit.status,
            "PASS",
        ),
        binding_check(
            "dataset_integrity",
            dataset_audit.status == "PASS",
            dataset_audit.status,
            "PASS",
        ),
        binding_check(
            "protocol_integrity",
            protocol_current_hash == protocol.protocol_hash,
            protocol_current_hash,
            protocol.protocol_hash,
        ),
        binding_check(
            "strategy",
            replay.strategy == protocol.strategy,
            replay.strategy,
            protocol.strategy,
        ),
        binding_check(
            "strategy_version",
            replay.strategy_version == protocol.strategy_version,
            replay.strategy_version,
            protocol.strategy_version,
        ),
        binding_check(
            "symbol",
            len(protocol_symbols) == 1 and dataset.symbol.upper() == protocol_symbols[0],
            dataset.symbol.upper(),
            protocol_symbols,
        ),
        binding_check(
            "timeframe",
            dataset.timeframe == protocol.timeframe,
            dataset.timeframe,
            protocol.timeframe,
        ),
        binding_check(
            "parameters",
            replay_parameters == protocol_parameters,
            replay_parameters,
            protocol_parameters,
        ),
        binding_check(
            "backtest_start",
            replay_parameter_datetime(replay_parameters, "backtest_start")
            == ensure_utc(protocol_payload.data_start),
            replay_parameters.get("backtest_start"),
            ensure_utc(protocol_payload.data_start).isoformat(),
        ),
        binding_check(
            "backtest_end",
            replay_parameter_datetime(replay_parameters, "backtest_end")
            == ensure_utc(protocol_payload.data_end),
            replay_parameters.get("backtest_end"),
            ensure_utc(protocol_payload.data_end).isoformat(),
        ),
        binding_check(
            "commission_percent",
            Decimal(str(replay.request_snapshot.get("commission_percent")))
            == Decimal(str(protocol_payload.cost_model.get("commission_percent"))),
            replay.request_snapshot.get("commission_percent"),
            protocol_payload.cost_model.get("commission_percent"),
        ),
        binding_check(
            "slippage_ticks",
            int(replay.request_snapshot.get("slippage_ticks", -1))
            == int(protocol_payload.slippage_model.get("ticks", -2)),
            replay.request_snapshot.get("slippage_ticks"),
            protocol_payload.slippage_model.get("ticks"),
        ),
        binding_check(
            "risk_per_trade",
            Decimal(str(replay_parameters.get("risk_per_trade_percent")))
            / Decimal("100")
            == Decimal(str(protocol_payload.risk_snapshot.get("risk_per_trade"))),
            replay_parameters.get("risk_per_trade_percent"),
            protocol_payload.risk_snapshot.get("risk_per_trade"),
        ),
    ]
    execution_spec_fields = (
        "tick_size",
        "point_value",
        "minimum_contract",
    )
    for field in execution_spec_fields:
        expected = protocol_payload.risk_snapshot.get(field)
        if expected is not None:
            observed = replay.request_snapshot.get(field)
            checks.append(
                binding_check(
                    field,
                    Decimal(str(observed)) == Decimal(str(expected)),
                    observed,
                    expected,
                )
            )
    if evaluator_version == EVALUATOR_VERSION:
        checks.append(
            binding_check(
                "protocol_registered_before_reference_replay",
                ensure_utc(protocol.registered_at) <= ensure_utc(replay.recorded_at),
                ensure_utc(protocol.registered_at).isoformat(),
                f"no later than {ensure_utc(replay.recorded_at).isoformat()}",
            )
        )
    binding_reasons = [
        f"{check['name']}_mismatch" for check in checks if check["status"] != "PASS"
    ]
    execution_spec_bound = all(
        protocol_payload.risk_snapshot.get(field) is not None
        for field in execution_spec_fields
    )
    warnings = [
        "This validation is comparison-only and cannot promote a strategy.",
        "The frozen TradingView protocol remains unconsumed by local replay validation.",
        (
            "Tick size, point value, and minimum contract are bound to the frozen protocol."
            if execution_spec_bound
            else (
                "Tick size, point value, and minimum contract come from the replay request; "
                "confirm them against TradingView symbol metadata."
            )
        ),
    ]
    if evaluator_version == EVALUATOR_VERSION:
        warnings.append(
            "Evaluator v1.2 requires the durable protocol record to predate the replay."
        )
    if evaluator_version != LEGACY_EVALUATOR_VERSION:
        warnings.append(
            "Cost sensitivity holds the recorded trade path and quantities constant; "
            "it is not an order-book or market-impact simulation."
        )
    common = {
        "evaluator_version": evaluator_version,
        "reference_replay_run_id": replay.id,
        "protocol_id": protocol.id,
        "dataset_id": dataset.id,
        "strategy": replay.strategy,
        "strategy_version": replay.strategy_version,
        "symbol": dataset.symbol,
        "timeframe": dataset.timeframe,
        "replay_record_evidence_hash": replay.record_evidence_hash,
        "engine_evidence_hash": replay.engine_evidence_hash,
        "dataset_evidence_hash": replay.dataset_evidence_hash,
        "protocol_hash": protocol.protocol_hash,
        "binding_checks": checks,
        "warnings": warnings,
    }
    if binding_reasons:
        return ReferenceReplayValidationResponse(
            status="BLOCKED",
            trade_evidence_hash=None,
            validation_evidence_hash=None,
            metrics_snapshot={},
            acceptance_snapshot=protocol_payload.acceptance_criteria.model_dump(
                mode="json"
            ),
            statistical_acceptance_passed=False,
            acceptance_reasons=[],
            reasons=binding_reasons,
            checked_at=utc_now(),
            **common,
        )

    trades = replay_trade_inputs(replay, symbol=dataset.symbol)
    metric_trades = reference_metric_trade_inputs(
        trades,
        evaluator_version=evaluator_version,
    )
    report_payload = backtest_report_payload_from_protocol(protocol_payload).model_copy(
        update={
            "data_source": "binance-vision-reference-replay",
            "source_format": "reference_replay",
            "source_artifact_hash": replay.record_evidence_hash,
            "source_reference": f"aurex://reference-replay/{replay.id}",
            "trades": metric_trades,
        }
    )
    metrics = calculate_backtest_metrics(metric_trades)
    segments = calculate_backtest_segments(report_payload)
    metrics_snapshot = build_metrics_snapshot(report_payload, metrics, segments)
    trade_hash = build_trade_evidence_hash(trades)
    metrics_snapshot["trade_evidence_hash"] = trade_hash
    metrics_snapshot["reference_replay_lineage"] = {
        "reference_replay_run_id": replay.id,
        "replay_record_evidence_hash": replay.record_evidence_hash,
        "engine_evidence_hash": replay.engine_evidence_hash,
        "dataset_id": dataset.id,
        "dataset_evidence_hash": replay.dataset_evidence_hash,
        "protocol_id": protocol.id,
        "protocol_hash": protocol.protocol_hash,
        "comparison_only": True,
    }
    metrics_snapshot["sample_assignment"] = sample_assignment_snapshot(
        trades,
        protocol_payload,
    )
    if evaluator_version != LEGACY_EVALUATOR_VERSION:
        replay_metrics = replay.result_snapshot.get("metrics", {})
        drawdown_matches = decimal_snapshot_matches(
            replay_metrics,
            "max_drawdown",
            metrics.max_drawdown,
        )
        metrics_snapshot["drawdown_evidence"] = {
            "method": "cumulative_realized_pl_from_each_evaluation_segment_start",
            "post_trade_account_equity_used": False,
            "reference_replay_max_drawdown": replay_metrics.get("max_drawdown"),
            "validation_max_drawdown": str(metrics.max_drawdown),
            "matches_reference_replay": drawdown_matches,
        }
        cost_sensitivity = reference_cost_sensitivity_snapshot(trades, replay_metrics)
        metrics_snapshot["cost_sensitivity"] = cost_sensitivity
        checks.extend(
            [
                binding_check(
                    "reference_replay_max_drawdown",
                    drawdown_matches,
                    str(metrics.max_drawdown),
                    replay_metrics.get("max_drawdown"),
                ),
                binding_check(
                    "reference_replay_cost_decomposition",
                    bool(cost_sensitivity["base_case_matches_reference_replay"]),
                    cost_sensitivity["base_case_reference_comparison"],
                    "all_base_case_metrics_match",
                ),
            ]
        )
        metric_binding_reasons = [
            f"{check['name']}_mismatch"
            for check in checks
            if check["status"] != "PASS"
        ]
        if metric_binding_reasons:
            return ReferenceReplayValidationResponse(
                status="BLOCKED",
                trade_evidence_hash=trade_hash,
                validation_evidence_hash=None,
                metrics_snapshot=metrics_snapshot,
                acceptance_snapshot=protocol_payload.acceptance_criteria.model_dump(
                    mode="json"
                ),
                statistical_acceptance_passed=False,
                acceptance_reasons=[],
                reasons=metric_binding_reasons,
                checked_at=utc_now(),
                **common,
            )
    statistical_passed, acceptance_reasons = evaluate_acceptance(
        metrics,
        protocol_payload.acceptance_criteria,
        report_payload,
        segments,
    )
    status = "PASSED" if statistical_passed else "REJECTED"
    evidence_payload = reference_validation_evidence_payload(
        evaluator_version=evaluator_version,
        status=status,
        request=request,
        replay=replay,
        protocol=protocol,
        dataset_symbol=dataset.symbol,
        dataset_timeframe=dataset.timeframe,
        trade_evidence_hash=trade_hash,
        metrics_snapshot=metrics_snapshot,
        acceptance_snapshot=protocol_payload.acceptance_criteria.model_dump(mode="json"),
        statistical_acceptance_passed=statistical_passed,
        acceptance_reasons=acceptance_reasons,
        binding_checks=checks,
        warnings=warnings,
    )
    return ReferenceReplayValidationResponse(
        status=status,
        trade_evidence_hash=trade_hash,
        validation_evidence_hash=build_reference_validation_hash(evidence_payload),
        metrics_snapshot=metrics_snapshot,
        acceptance_snapshot=protocol_payload.acceptance_criteria.model_dump(mode="json"),
        statistical_acceptance_passed=statistical_passed,
        acceptance_reasons=acceptance_reasons,
        reasons=[],
        checked_at=utc_now(),
        **common,
    )


def replay_trade_inputs(
    replay: BacktestReferenceReplayRun,
    *,
    symbol: str,
) -> list[BacktestTradeInput]:
    trades: list[BacktestTradeInput] = []
    for item in replay.result_snapshot.get("trades", []):
        trade = ReferenceReplayTrade.model_validate(item)
        trades.append(
            BacktestTradeInput(
                sequence=trade.sequence,
                external_trade_id=f"reference-replay-{trade.sequence}",
                source_format="reference_replay",
                strategy=replay.strategy,
                symbol=symbol,
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
        )
    return trades


def reference_metric_trade_inputs(
    trades: list[BacktestTradeInput],
    *,
    evaluator_version: str,
) -> list[BacktestTradeInput]:
    if evaluator_version == LEGACY_EVALUATOR_VERSION:
        return trades
    return [trade.model_copy(update={"equity": None}) for trade in trades]


def reference_cost_sensitivity_snapshot(
    trades: list[BacktestTradeInput],
    replay_metrics: dict,
) -> dict:
    total_base_fees = sum((trade.fees or Decimal("0") for trade in trades), Decimal("0"))
    total_base_slippage = sum(
        (trade.slippage or Decimal("0") for trade in trades),
        Decimal("0"),
    )
    gross_before_modeled_costs = sum(
        (
            trade.realized_pl
            + (trade.fees or Decimal("0"))
            + (trade.slippage or Decimal("0"))
            for trade in trades
        ),
        Decimal("0"),
    )
    scenarios: list[dict] = []
    for name, fee_multiplier, slippage_multiplier in COST_SENSITIVITY_SCENARIOS:
        scenario_trades = [
            trade.model_copy(
                update={
                    "realized_pl": (
                        trade.realized_pl
                        + (Decimal("1") - fee_multiplier)
                        * (trade.fees or Decimal("0"))
                        + (Decimal("1") - slippage_multiplier)
                        * (trade.slippage or Decimal("0"))
                    ),
                    "equity": None,
                }
            )
            for trade in trades
        ]
        metrics = calculate_backtest_metrics(scenario_trades)
        fee_cost = total_base_fees * fee_multiplier
        slippage_cost = total_base_slippage * slippage_multiplier
        scenarios.append(
            {
                "name": name,
                "commission_multiplier": str(fee_multiplier),
                "slippage_multiplier": str(slippage_multiplier),
                "gross_before_modeled_costs": str(gross_before_modeled_costs),
                "fee_cost": str(fee_cost),
                "slippage_cost": str(slippage_cost),
                "total_modeled_cost": str(fee_cost + slippage_cost),
                "total_net_pl": str(metrics.total_net_pl),
                "expectancy": str(metrics.expectancy),
                "profit_factor": (
                    str(metrics.profit_factor)
                    if metrics.profit_factor is not None
                    else None
                ),
                "max_drawdown": str(metrics.max_drawdown),
                "profitable": metrics.total_net_pl > 0,
            }
        )

    base_case = next(
        scenario for scenario in scenarios if scenario["name"] == "base_case"
    )
    comparison = {
        "total_net_pl": decimal_snapshot_matches(
            replay_metrics,
            "total_net_pl",
            Decimal(base_case["total_net_pl"]),
        ),
        "expectancy": decimal_snapshot_matches(
            replay_metrics,
            "expectancy",
            Decimal(base_case["expectancy"]),
        ),
        "profit_factor": optional_decimal_snapshot_matches(
            replay_metrics,
            "profit_factor",
            base_case["profit_factor"],
        ),
        "max_drawdown": decimal_snapshot_matches(
            replay_metrics,
            "max_drawdown",
            Decimal(base_case["max_drawdown"]),
        ),
    }
    return {
        "method": "fixed_trade_path_linear_monetary_cost_multipliers",
        "trade_path_held_constant": True,
        "position_quantities_held_constant": True,
        "market_impact_modeled": False,
        "trade_count": len(trades),
        "base_fee_cost": str(total_base_fees),
        "base_slippage_cost": str(total_base_slippage),
        "gross_before_modeled_costs": str(gross_before_modeled_costs),
        "scenarios": scenarios,
        "base_case_reference_comparison": comparison,
        "base_case_matches_reference_replay": all(comparison.values()),
    }


def decimal_snapshot_matches(snapshot: dict, key: str, expected: Decimal) -> bool:
    try:
        return Decimal(str(snapshot.get(key))) == expected
    except (ArithmeticError, TypeError, ValueError):
        return False


def optional_decimal_snapshot_matches(
    snapshot: dict,
    key: str,
    expected: str | None,
) -> bool:
    observed = snapshot.get(key)
    if observed is None or expected is None:
        return observed is None and expected is None
    return decimal_snapshot_matches(snapshot, key, Decimal(expected))


def sample_assignment_snapshot(
    trades: list[BacktestTradeInput],
    protocol: BacktestProtocolCreate,
) -> dict:
    in_start = ensure_utc(protocol.in_sample_start)
    in_end = ensure_utc(protocol.in_sample_end)
    out_start = ensure_utc(protocol.out_of_sample_start)
    out_end = ensure_utc(protocol.out_of_sample_end)
    in_count = 0
    out_count = 0
    unassigned_count = 0
    for trade in trades:
        if trade.closed_at is None:
            unassigned_count += 1
            continue
        closed_at = ensure_utc(trade.closed_at)
        if in_start <= closed_at <= in_end:
            in_count += 1
        elif out_start <= closed_at <= out_end:
            out_count += 1
        else:
            unassigned_count += 1
    return {
        "in_sample_trade_count": in_count,
        "out_of_sample_trade_count": out_count,
        "unassigned_trade_count": unassigned_count,
        "purge_gap_start": in_end.isoformat(),
        "purge_gap_end": out_start.isoformat(),
    }


def binding_check(name: str, passed: bool, observed: object, expected: object) -> dict:
    return {
        "name": name,
        "status": "PASS" if passed else "BLOCKED",
        "observed": observed,
        "expected": expected,
    }


def replay_parameter_datetime(parameters: dict, key: str) -> datetime:
    value = str(parameters.get(key, "")).replace("Z", "+00:00")
    return ensure_utc(datetime.fromisoformat(value))


def reference_validation_record_response(
    record: BacktestReferenceReplayValidation,
    *,
    reused_existing: bool = False,
    mutates_ledger: bool = False,
) -> ReferenceReplayValidationResponse:
    return ReferenceReplayValidationResponse(
        id=record.id,
        status=record.status,
        evaluator_version=record.evaluator_version,
        reference_replay_run_id=record.reference_replay_run_id,
        protocol_id=record.protocol_id,
        dataset_id=record.dataset_id,
        strategy=record.strategy,
        strategy_version=record.strategy_version,
        symbol=record.symbol,
        timeframe=record.timeframe,
        replay_record_evidence_hash=record.replay_record_evidence_hash,
        engine_evidence_hash=record.engine_evidence_hash,
        dataset_evidence_hash=record.dataset_evidence_hash,
        protocol_hash=record.protocol_hash,
        trade_evidence_hash=record.trade_evidence_hash,
        validation_evidence_hash=record.validation_evidence_hash,
        metrics_snapshot=record.metrics_snapshot,
        acceptance_snapshot=record.acceptance_snapshot,
        statistical_acceptance_passed=record.statistical_acceptance_passed,
        acceptance_reasons=record.reason_snapshot,
        binding_checks=record.binding_snapshot,
        reasons=[],
        warnings=record.warning_snapshot,
        immutable=True,
        reused_existing=reused_existing,
        recorded_at=ensure_utc(record.recorded_at),
        checked_at=ensure_utc(record.recorded_at),
        mutates_ledger=mutates_ledger,
    )


def reference_validation_record_payload(
    record: BacktestReferenceReplayValidation,
) -> dict:
    return {
        "schema_version": validation_schema_version(record.evaluator_version),
        "evaluator_version": record.evaluator_version,
        "status": record.status,
        "request": record.request_snapshot,
        "reference_replay_run_id": record.reference_replay_run_id,
        "replay_record_evidence_hash": record.replay_record_evidence_hash,
        "engine_evidence_hash": record.engine_evidence_hash,
        "dataset_id": record.dataset_id,
        "dataset_evidence_hash": record.dataset_evidence_hash,
        "protocol_id": record.protocol_id,
        "protocol_hash": record.protocol_hash,
        "strategy": record.strategy,
        "strategy_version": record.strategy_version,
        "symbol": record.symbol,
        "timeframe": record.timeframe,
        "trade_evidence_hash": record.trade_evidence_hash,
        "metrics_snapshot": record.metrics_snapshot,
        "acceptance_snapshot": record.acceptance_snapshot,
        "statistical_acceptance_passed": record.statistical_acceptance_passed,
        "acceptance_reasons": record.reason_snapshot,
        "binding_checks": record.binding_snapshot,
        "warnings": record.warning_snapshot,
        "comparison_only": True,
        "promotion_eligible": False,
        "paper_eligible": False,
    }


def reference_validation_evidence_payload(
    *,
    evaluator_version: str,
    status: str,
    request: ReferenceReplayValidationRequest,
    replay: BacktestReferenceReplayRun,
    protocol: BacktestProtocol,
    dataset_symbol: str,
    dataset_timeframe: str,
    trade_evidence_hash: str,
    metrics_snapshot: dict,
    acceptance_snapshot: dict,
    statistical_acceptance_passed: bool,
    acceptance_reasons: list[str],
    binding_checks: list[dict],
    warnings: list[str],
) -> dict:
    return {
        "schema_version": validation_schema_version(evaluator_version),
        "evaluator_version": evaluator_version,
        "status": status,
        "request": request.model_dump(mode="json"),
        "reference_replay_run_id": replay.id,
        "replay_record_evidence_hash": replay.record_evidence_hash,
        "engine_evidence_hash": replay.engine_evidence_hash,
        "dataset_id": replay.dataset_id,
        "dataset_evidence_hash": replay.dataset_evidence_hash,
        "protocol_id": protocol.id,
        "protocol_hash": protocol.protocol_hash,
        "strategy": replay.strategy,
        "strategy_version": replay.strategy_version,
        "symbol": dataset_symbol,
        "timeframe": dataset_timeframe,
        "trade_evidence_hash": trade_evidence_hash,
        "metrics_snapshot": metrics_snapshot,
        "acceptance_snapshot": acceptance_snapshot,
        "statistical_acceptance_passed": statistical_acceptance_passed,
        "acceptance_reasons": acceptance_reasons,
        "binding_checks": binding_checks,
        "warnings": warnings,
        "comparison_only": True,
        "promotion_eligible": False,
        "paper_eligible": False,
    }


def build_reference_validation_hash(payload: dict) -> str:
    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(serialized.encode()).hexdigest()


def validation_schema_version(evaluator_version: str) -> str:
    if evaluator_version == LEGACY_EVALUATOR_VERSION:
        return LEGACY_VALIDATION_SCHEMA_VERSION
    if evaluator_version == COST_AUDIT_EVALUATOR_VERSION:
        return COST_AUDIT_VALIDATION_SCHEMA_VERSION
    if evaluator_version == EVALUATOR_VERSION:
        return VALIDATION_SCHEMA_VERSION
    raise ValueError(f"Unsupported reference replay evaluator version: {evaluator_version}")
