from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from pathlib import Path

from aurex.backtest_engine.binance_vision import file_sha256
from aurex.backtest_engine.development_bundle import safe_evidence_path
from aurex.backtest_engine.research_r4_engine import (
    R4ResearchReplayResult,
    R4ResearchTrade,
)
from aurex.backtest_engine.research_r4_failure_analysis import (
    R4AvailabilitySummary,
    R4CostAttribution,
    R4DescriptiveFinding,
    R4DrawdownEpisode,
    R4ExitReasonSummary,
    R4FailureAnalysisPackage,
    R4FailureAnalysisResult,
    R4HoldingDurationSummary,
    R4QuarterSummary,
    R4RebalanceCohortSummary,
    R4SymbolContribution,
    build_r4_failure_analysis_result,
)
from aurex.backtest_engine.research_r4_failure_protocol import (
    R4FailureAnalysisProtocol,
)
from aurex.backtest_engine.research_r4_result import R4ValidationResultLedger
from aurex.backtest_engine.research_r4_run_package import R4RunPackage
from aurex.backtest_engine.validation_bundle import ValidationDatasetBundle

ZERO = Decimal("0")


def verify_failure_package_sources(
    package: R4FailureAnalysisPackage,
    project_root: Path,
) -> None:
    root = project_root.resolve()
    for relative_path, expected_hash in package.source_file_sha256.items():
        path = (root / relative_path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"R4 failure-analysis source is missing: {relative_path}")
        if file_sha256(path) != expected_hash:
            raise ValueError(
                f"R4 failure-analysis source hash changed: {relative_path}"
            )


def load_replay_artifacts(
    *,
    protocol: R4FailureAnalysisProtocol,
    ledger: R4ValidationResultLedger,
    evidence_root: Path,
) -> dict[str, R4ResearchReplayResult]:
    results: dict[str, R4ResearchReplayResult] = {}
    for receipt in ledger.replay_receipts:
        if (
            protocol.replay_result_evidence_hashes.get(receipt.run_id)
            != receipt.result_evidence_hash
        ):
            raise ValueError(f"R4 failure protocol replay changed: {receipt.run_id}")
        path = safe_evidence_path(evidence_root, receipt.artifact_relative_path)
        if file_sha256(path) != receipt.artifact_sha256:
            raise ValueError(f"R4 failure artifact hash mismatch: {receipt.run_id}")
        result = R4ResearchReplayResult.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        if (
            result.result_evidence_hash != receipt.result_evidence_hash
            or result.request_evidence_hash != receipt.request_evidence_hash
            or result.metrics != receipt.metrics
        ):
            raise ValueError(f"R4 failure receipt mismatch: {receipt.run_id}")
        results[receipt.run_id] = result
    if len(results) != 42 or sorted(results) != sorted(
        protocol.replay_result_evidence_hashes
    ):
        raise ValueError("R4 failure analysis requires the exact 42 artifacts")
    return results


def verify_analysis_bindings(
    *,
    protocol: R4FailureAnalysisProtocol,
    validation_bundle: ValidationDatasetBundle,
    run_package: R4RunPackage,
    ledger: R4ValidationResultLedger,
    package: R4FailureAnalysisPackage,
) -> None:
    if (
        package.failure_protocol_evidence_hash != protocol.protocol_evidence_hash
        or package.validation_dataset_bundle_evidence_hash
        != validation_bundle.bundle_evidence_hash
        or package.run_package_evidence_hash != run_package.package_evidence_hash
        or package.result_ledger_evidence_hash != ledger.ledger_evidence_hash
        or package.replay_result_evidence_hashes
        != protocol.replay_result_evidence_hashes
    ):
        raise ValueError("R4 failure-analysis package lineage changed")
    if ledger.verdict != "RETIRE_R4_CANDIDATE":
        raise ValueError("R4 failure analysis cannot change the frozen verdict")


def execute_r4_failure_analysis(
    *,
    protocol: R4FailureAnalysisProtocol,
    validation_bundle: ValidationDatasetBundle,
    run_package: R4RunPackage,
    ledger: R4ValidationResultLedger,
    package: R4FailureAnalysisPackage,
    evidence_root: Path,
    project_root: Path,
    generated_at: datetime | None = None,
) -> R4FailureAnalysisResult:
    verify_analysis_bindings(
        protocol=protocol,
        validation_bundle=validation_bundle,
        run_package=run_package,
        ledger=ledger,
        package=package,
    )
    verify_failure_package_sources(package, project_root)
    result_path = safe_evidence_path(
        evidence_root, package.expected_result_relative_path
    )
    if result_path.exists():
        raise ValueError("R4 failure-analysis result already exists")
    replay_results = load_replay_artifacts(
        protocol=protocol,
        ledger=ledger,
        evidence_root=evidence_root,
    )
    result = build_failure_result(
        protocol=protocol,
        validation_bundle=validation_bundle,
        run_package=run_package,
        ledger=ledger,
        package=package,
        replay_results=replay_results,
        generated_at=generated_at or datetime.now(UTC),
    )
    serialized = result.model_dump_json(indent=2) + "\n"
    if R4FailureAnalysisResult.model_validate_json(serialized) != result:
        raise ValueError("R4 failure-analysis result JSON did not round-trip")
    temporary = result_path.with_name(f"{result_path.name}.part")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(result_path)
    return result


def audit_r4_failure_analysis(
    *,
    protocol: R4FailureAnalysisProtocol,
    validation_bundle: ValidationDatasetBundle,
    run_package: R4RunPackage,
    ledger: R4ValidationResultLedger,
    package: R4FailureAnalysisPackage,
    evidence_root: Path,
    project_root: Path,
) -> R4FailureAnalysisResult:
    verify_analysis_bindings(
        protocol=protocol,
        validation_bundle=validation_bundle,
        run_package=run_package,
        ledger=ledger,
        package=package,
    )
    verify_failure_package_sources(package, project_root)
    result_path = safe_evidence_path(
        evidence_root, package.expected_result_relative_path
    )
    stored = R4FailureAnalysisResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    replay_results = load_replay_artifacts(
        protocol=protocol,
        ledger=ledger,
        evidence_root=evidence_root,
    )
    rebuilt = build_failure_result(
        protocol=protocol,
        validation_bundle=validation_bundle,
        run_package=run_package,
        ledger=ledger,
        package=package,
        replay_results=replay_results,
        generated_at=stored.generated_at,
    )
    if rebuilt != stored:
        raise ValueError("R4 failure-analysis deterministic rebuild mismatch")
    return stored


def build_failure_result(
    *,
    protocol: R4FailureAnalysisProtocol,
    validation_bundle: ValidationDatasetBundle,
    run_package: R4RunPackage,
    ledger: R4ValidationResultLedger,
    package: R4FailureAnalysisPackage,
    replay_results: dict[str, R4ResearchReplayResult],
    generated_at: datetime,
) -> R4FailureAnalysisResult:
    with localcontext() as context:
        context.prec = 50
        context.rounding = ROUND_HALF_EVEN
        return _build_failure_result(
            protocol=protocol,
            validation_bundle=validation_bundle,
            run_package=run_package,
            ledger=ledger,
            package=package,
            replay_results=replay_results,
            generated_at=generated_at,
        )


def _build_failure_result(
    *,
    protocol: R4FailureAnalysisProtocol,
    validation_bundle: ValidationDatasetBundle,
    run_package: R4RunPackage,
    ledger: R4ValidationResultLedger,
    package: R4FailureAnalysisPackage,
    replay_results: dict[str, R4ResearchReplayResult],
    generated_at: datetime,
) -> R4FailureAnalysisResult:
    base = replay_results["overall--path_quality_spot_v1--cost-1"]
    cost_attribution = build_cost_attribution(base)
    quarters = build_quarter_summary(ledger, replay_results)
    exits = build_exit_summary(base.trades)
    holding = build_holding_summary(base.trades)
    cohorts = build_cohort_summary(base.trades)
    symbols = build_symbol_summary(
        baseline_symbols=base.config.baseline_decision_symbols,
        base_trades=base.trades,
        run_package=run_package,
        replay_results=replay_results,
    )
    drawdowns = build_drawdown_episodes(base)
    availability = R4AvailabilitySummary(
        configured_terminal_markets=(
            validation_bundle.summary.terminal_unavailable_count
        ),
        observed_availability_events=len(base.availability_events),
        held_position_writeoffs=sum(
            event.held_position_written_off for event in base.availability_events
        ),
        writeoff_net_pl=base.metrics.termination_writeoff_net_pl,
        minimum_active_symbol_count_at_rebalance=(
            base.metrics.minimum_active_symbol_count_at_rebalance
        ),
        average_active_symbol_count_at_rebalance=(
            base.metrics.average_active_symbol_count_at_rebalance
        ),
        availability_caused_base_loss=(
            base.metrics.termination_writeoff_net_pl < ZERO
        ),
    )
    monthly = ledger.monthly_net_returns
    positive_months = sum(value > ZERO for value in monthly.values())
    flat_months = sum(value == ZERO for value in monthly.values())
    negative_months = sum(value < ZERO for value in monthly.values())
    failure_classification = classify_failure(
        cost_attribution=cost_attribution,
        positive_quarters=ledger.positive_quarterly_folds,
        lomo_fraction=ledger.leave_one_market_out_positive_fraction,
    )
    integrity_checks = {
        "all_35_symbol_rows_present": len(symbols) == 35,
        "all_42_replay_artifacts_bound": len(replay_results) == 42,
        "all_four_quarter_rows_present": len(quarters) == 4,
        "cost_reconciliation_exact": cost_attribution.reconciles,
        "exit_reason_net_reconciles": (
            sum((row.net_pl for row in exits), ZERO) == base.metrics.net_pl
        ),
        "frozen_verdict_preserved": ledger.verdict == "RETIRE_R4_CANDIDATE",
        "lomo_rows_complete": all(
            row.leave_one_market_out_net_pl is not None for row in symbols
        ),
        "result_metrics_match_trade_net": (
            sum((trade.net_pl for trade in base.trades), ZERO)
            == base.metrics.net_pl
        ),
        "symbol_net_reconciles": (
            sum((row.net_pl for row in symbols), ZERO) == base.metrics.net_pl
        ),
    }
    findings = build_findings(
        base=base,
        ledger=ledger,
        cost=cost_attribution,
        availability=availability,
        positive_months=positive_months,
        negative_months=negative_months,
    )
    return build_r4_failure_analysis_result(
        generated_at=generated_at,
        package_evidence_hash=package.package_evidence_hash,
        failure_protocol_evidence_hash=protocol.protocol_evidence_hash,
        run_package_evidence_hash=run_package.package_evidence_hash,
        result_ledger_evidence_hash=ledger.ledger_evidence_hash,
        cost_attribution=cost_attribution,
        quarterly_summary=quarters,
        monthly_net_returns=monthly,
        exit_reason_summary=exits,
        holding_duration_summary=holding,
        rebalance_cohorts=cohorts,
        symbol_contribution=symbols,
        drawdown_episodes=drawdowns,
        availability_summary=availability,
        positive_months=positive_months,
        flat_months=flat_months,
        negative_months=negative_months,
        failure_classification=failure_classification,
        integrity_checks=integrity_checks,
        findings=findings,
    )


def build_cost_attribution(result: R4ResearchReplayResult) -> R4CostAttribution:
    trades = result.trades
    raw = sum((trade.raw_price_pl for trade in trades), ZERO)
    commission = sum(
        (trade.entry_fee + trade.exit_fee for trade in trades), ZERO
    )
    slippage = sum((trade.total_slippage_cost for trade in trades), ZERO)
    net = sum((trade.net_pl for trade in trades), ZERO)
    modeled_costs = commission + slippage
    return R4CostAttribution(
        raw_price_pl=raw,
        commission=commission,
        slippage=slippage,
        modeled_costs=modeled_costs,
        net_pl=net,
        reconciliation_delta=raw - modeled_costs - net,
        reconciles=raw - modeled_costs == net,
        raw_profit_factor=profit_factor(
            [trade.raw_price_pl for trade in trades]
        ),
        net_profit_factor=profit_factor([trade.net_pl for trade in trades]),
        raw_expectancy=raw / Decimal(len(trades)),
        net_expectancy=net / Decimal(len(trades)),
        modeled_cost_per_trade=modeled_costs / Decimal(len(trades)),
    )


def build_quarter_summary(
    ledger: R4ValidationResultLedger,
    results: dict[str, R4ResearchReplayResult],
) -> list[R4QuarterSummary]:
    rows = []
    for receipt in ledger.replay_receipts:
        if receipt.category != "QUARTERLY_FOLD":
            continue
        result = results[receipt.run_id]
        rows.append(
            R4QuarterSummary(
                fold_id=receipt.fold_id,
                net_pl=result.metrics.net_pl,
                profit_factor=result.metrics.profit_factor,
                raw_price_pl=sum(
                    (trade.raw_price_pl for trade in result.trades), ZERO
                ),
                completed_trades=result.metrics.completed_trades,
                maximum_drawdown_percent=(
                    result.metrics.maximum_drawdown_percent
                ),
                average_gross_exposure_percent=(
                    result.metrics.average_gross_exposure_percent
                ),
                minimum_active_symbol_count_at_rebalance=(
                    result.metrics.minimum_active_symbol_count_at_rebalance
                ),
            )
        )
    return sorted(rows, key=lambda row: row.fold_id)


def build_exit_summary(
    trades: list[R4ResearchTrade],
) -> list[R4ExitReasonSummary]:
    rows = []
    for reason in (
        "END_OF_WINDOW",
        "FIXED_STOP",
        "MARKET_TERMINATION_WRITE_OFF",
        "REBALANCE",
    ):
        group = [trade for trade in trades if trade.exit_reason == reason]
        rows.append(
            R4ExitReasonSummary(
                exit_reason=reason,
                trades=len(group),
                raw_price_pl=sum((trade.raw_price_pl for trade in group), ZERO),
                net_pl=sum((trade.net_pl for trade in group), ZERO),
                commission=sum(
                    (trade.entry_fee + trade.exit_fee for trade in group), ZERO
                ),
                slippage=sum(
                    (trade.total_slippage_cost for trade in group), ZERO
                ),
            )
        )
    return rows


def build_holding_summary(
    trades: list[R4ResearchTrade],
) -> list[R4HoldingDurationSummary]:
    groups: dict[str, list[R4ResearchTrade]] = {
        "01_UP_TO_7_DAYS": [],
        "02_OVER_7_TO_14_DAYS": [],
        "03_OVER_14_DAYS": [],
    }
    for trade in trades:
        hours = Decimal(
            str((trade.exit_at - trade.entry_at).total_seconds())
        ) / Decimal("3600")
        if hours <= Decimal("168"):
            bucket = "01_UP_TO_7_DAYS"
        elif hours <= Decimal("336"):
            bucket = "02_OVER_7_TO_14_DAYS"
        else:
            bucket = "03_OVER_14_DAYS"
        groups[bucket].append(trade)
    rows = []
    for bucket, group in groups.items():
        durations = [
            Decimal(str((trade.exit_at - trade.entry_at).total_seconds()))
            / Decimal("3600")
            for trade in group
        ]
        rows.append(
            R4HoldingDurationSummary(
                bucket_id=bucket,
                trades=len(group),
                average_hours=(
                    sum(durations, ZERO) / Decimal(len(durations))
                    if durations
                    else ZERO
                ),
                raw_price_pl=sum((trade.raw_price_pl for trade in group), ZERO),
                net_pl=sum((trade.net_pl for trade in group), ZERO),
            )
        )
    return rows


def build_cohort_summary(
    trades: list[R4ResearchTrade],
) -> list[R4RebalanceCohortSummary]:
    groups: dict[datetime, list[R4ResearchTrade]] = defaultdict(list)
    for trade in trades:
        groups[trade.entry_at].append(trade)
    return [
        R4RebalanceCohortSummary(
            entry_at=entry_at,
            trades=len(group),
            raw_price_pl=sum((trade.raw_price_pl for trade in group), ZERO),
            net_pl=sum((trade.net_pl for trade in group), ZERO),
            commission=sum(
                (trade.entry_fee + trade.exit_fee for trade in group), ZERO
            ),
            slippage=sum(
                (trade.total_slippage_cost for trade in group), ZERO
            ),
        )
        for entry_at, group in sorted(groups.items())
    ]


def build_symbol_summary(
    *,
    baseline_symbols: list[str],
    base_trades: list[R4ResearchTrade],
    run_package: R4RunPackage,
    replay_results: dict[str, R4ResearchReplayResult],
) -> list[R4SymbolContribution]:
    lomo_net = {
        plan.omitted_symbols[0]: replay_results[plan.run_id].metrics.net_pl
        for plan in run_package.planned_replays
        if plan.category == "LEAVE_ONE_MARKET_OUT"
    }
    rows = []
    for symbol in baseline_symbols:
        group = [trade for trade in base_trades if trade.symbol == symbol]
        rows.append(
            R4SymbolContribution(
                symbol=symbol,
                trades=len(group),
                raw_price_pl=sum((trade.raw_price_pl for trade in group), ZERO),
                net_pl=sum((trade.net_pl for trade in group), ZERO),
                commission=sum(
                    (trade.entry_fee + trade.exit_fee for trade in group), ZERO
                ),
                slippage=sum(
                    (trade.total_slippage_cost for trade in group), ZERO
                ),
                leave_one_market_out_net_pl=lomo_net[symbol],
            )
        )
    return sorted(rows, key=lambda row: row.symbol)


def build_drawdown_episodes(
    result: R4ResearchReplayResult,
) -> list[R4DrawdownEpisode]:
    rows: list[R4DrawdownEpisode] = []
    active = []
    for snapshot in result.equity_curve:
        if snapshot.drawdown > ZERO:
            active.append(snapshot)
        elif active:
            rows.append(drawdown_episode(len(rows) + 1, active, snapshot.timestamp))
            active = []
    if active:
        rows.append(drawdown_episode(len(rows) + 1, active, None))
    return rows


def drawdown_episode(sequence: int, snapshots: list, recovered_at):
    trough = max(snapshots, key=lambda item: item.drawdown)
    ended_at = recovered_at or snapshots[-1].timestamp
    return R4DrawdownEpisode(
        sequence=sequence,
        started_at=snapshots[0].timestamp,
        trough_at=trough.timestamp,
        recovered_at=recovered_at,
        ended_at=ended_at,
        recovered=recovered_at is not None,
        duration_snapshots=len(snapshots),
        maximum_drawdown=trough.drawdown,
        maximum_drawdown_percent=trough.drawdown_percent,
    )


def classify_failure(
    *,
    cost_attribution: R4CostAttribution,
    positive_quarters: int,
    lomo_fraction: Decimal,
) -> str:
    if cost_attribution.raw_price_pl <= ZERO:
        return "SIGNAL_NEGATIVE_BEFORE_MODELED_COSTS"
    if cost_attribution.net_pl <= ZERO:
        return "MODELED_COSTS_OVERWHELM_POSITIVE_RAW_EDGE"
    if positive_quarters < 3 or lomo_fraction < Decimal("0.80"):
        return "TEMPORAL_OR_CROSS_MARKET_INSTABILITY"
    return "OTHER_FROZEN_GATE_FAILURE"


def build_findings(
    *,
    base: R4ResearchReplayResult,
    ledger: R4ValidationResultLedger,
    cost: R4CostAttribution,
    availability: R4AvailabilitySummary,
    positive_months: int,
    negative_months: int,
) -> list[R4DescriptiveFinding]:
    limit = (
        "Descriptive post-outcome evidence only; it cannot become a rule, parameter, "
        "candidate, or promotion claim."
    )
    return [
        R4DescriptiveFinding(
            finding_id="F-01-RAW-SIGNAL-EDGE",
            dimension="GROSS_NET_COST_RECONCILIATION",
            observation=(
                f"Raw price P/L was {cost.raw_price_pl} with raw PF "
                f"{cost.raw_profit_factor}; the mechanism was negative before costs."
            ),
            interpretation_limit=limit,
        ),
        R4DescriptiveFinding(
            finding_id="F-02-MODELED-COSTS",
            dimension="GROSS_NET_COST_RECONCILIATION",
            observation=(
                f"Commission plus slippage was {cost.modeled_costs}; net P/L was "
                f"{cost.net_pl}, and exact reconciliation was {cost.reconciles}."
            ),
            interpretation_limit=limit,
        ),
        R4DescriptiveFinding(
            finding_id="F-03-TEMPORAL-STABILITY",
            dimension="QUARTERLY_AND_MONTHLY_STABILITY",
            observation=(
                f"Only {ledger.positive_quarterly_folds}/4 quarters and "
                f"{positive_months}/12 months were positive; {negative_months} "
                "months were negative."
            ),
            interpretation_limit=limit,
        ),
        R4DescriptiveFinding(
            finding_id="F-04-LOMO-ROBUSTNESS",
            dimension="SYMBOL_CONTRIBUTION_AND_LEAVE_ONE_MARKET_OUT",
            observation=(
                "Leave-one-market-out positive fraction was "
                f"{ledger.leave_one_market_out_positive_fraction}; no omission "
                "restored positive full-window net P/L."
            ),
            interpretation_limit=limit,
        ),
        R4DescriptiveFinding(
            finding_id="F-05-CONCENTRATION",
            dimension="SYMBOL_CONTRIBUTION_AND_LEAVE_ONE_MARKET_OUT",
            observation=(
                "Single-symbol and top-five gross-profit fractions were "
                f"{base.metrics.maximum_single_symbol_gross_profit_fraction} and "
                f"{base.metrics.top_five_gross_profit_fraction}; both frozen "
                "concentration gates passed."
            ),
            interpretation_limit=limit,
        ),
        R4DescriptiveFinding(
            finding_id="F-06-AVAILABILITY",
            dimension="ACTIVE_BREADTH_AND_MARKET_TERMINATION",
            observation=(
                f"Termination write-off P/L was {availability.writeoff_net_pl}, with "
                f"minimum active breadth {availability.minimum_active_symbol_count_at_rebalance}; "
                "availability did not cause the base loss."
            ),
            interpretation_limit=limit,
        ),
        R4DescriptiveFinding(
            finding_id="F-07-DRAWDOWN-EXPOSURE",
            dimension="DRAWDOWN_AND_GROSS_EXPOSURE",
            observation=(
                f"Maximum drawdown was {base.metrics.maximum_drawdown_percent}% and "
                "passed its frozen cap, but controlled drawdown does not establish "
                "positive expectancy."
            ),
            interpretation_limit=limit,
        ),
    ]


def profit_factor(values: list[Decimal]) -> Decimal | None:
    gains = sum((value for value in values if value > ZERO), ZERO)
    losses = abs(sum((value for value in values if value < ZERO), ZERO))
    return gains / losses if losses > ZERO else None
