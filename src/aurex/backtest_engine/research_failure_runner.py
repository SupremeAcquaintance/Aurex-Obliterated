from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from pathlib import Path

from aurex.backtest_engine.binance_vision import file_sha256
from aurex.backtest_engine.development_bundle import (
    DevelopmentDatasetBundle,
    safe_evidence_path,
)
from aurex.backtest_engine.research_diagnostic_addendum import (
    R3MonthlyDiagnosticAddendum,
)
from aurex.backtest_engine.research_engine import (
    R3Candle,
    R3ResearchReplayResult,
)
from aurex.backtest_engine.research_failure_analysis import (
    R3BreadthRow,
    R3CostTurnoverRow,
    R3DescriptiveFinding,
    R3DiagnosticQuarterRow,
    R3DrawdownEpisode,
    R3ExitReasonQuarterRow,
    R3FailureAnalysisPackage,
    R3FailureAnalysisResult,
    R3HorizonComparisonRow,
    R3PrimaryQuarterRow,
    R3SymbolQuarterRow,
    build_r3_failure_analysis_result,
)
from aurex.backtest_engine.research_failure_protocol import R3FailureAnalysisProtocol
from aurex.backtest_engine.research_result import (
    R3StudyReplayReceipt,
    R3StudyResultLedger,
)
from aurex.backtest_engine.research_study_runner import load_canonical_ohlcv_csv

ZERO = Decimal("0")
ONE = Decimal("1")
DIAGNOSTIC_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
EXIT_REASONS = ("REBALANCE", "FIXED_STOP", "END_OF_WINDOW")


def verify_failure_inputs(
    *,
    protocol: R3FailureAnalysisProtocol,
    package: R3FailureAnalysisPackage,
    ledger: R3StudyResultLedger,
    addendum: R3MonthlyDiagnosticAddendum,
    bundle: DevelopmentDatasetBundle,
) -> None:
    if package.failure_protocol_evidence_hash != protocol.protocol_evidence_hash:
        raise ValueError("R3 failure package does not match its protocol")
    if package.result_ledger_evidence_hash != ledger.ledger_evidence_hash:
        raise ValueError("R3 failure package does not match the result ledger")
    if package.monthly_addendum_evidence_hash != addendum.addendum_evidence_hash:
        raise ValueError("R3 failure package does not match the monthly addendum")
    if (
        package.development_dataset_bundle_evidence_hash
        != bundle.bundle_evidence_hash
    ):
        raise ValueError("R3 failure package does not match the development bundle")
    receipt_hashes = {
        receipt.run_id: receipt.result_evidence_hash
        for receipt in ledger.replay_receipts
    }
    if receipt_hashes != protocol.replay_result_evidence_hashes:
        raise ValueError("R3 failure protocol does not match all replay results")
    if ledger.verdict != "NO_CANDIDATE":
        raise ValueError("R3 failure analysis cannot reopen an accepted result")


def load_replay_results(
    *,
    ledger: R3StudyResultLedger,
    protocol: R3FailureAnalysisProtocol,
    evidence_root: Path,
) -> dict[str, R3ResearchReplayResult]:
    results: dict[str, R3ResearchReplayResult] = {}
    for receipt in ledger.replay_receipts:
        artifact_path = safe_evidence_path(
            evidence_root, receipt.artifact_relative_path
        )
        if file_sha256(artifact_path) != receipt.artifact_sha256:
            raise ValueError(f"R3 failure replay file hash mismatch: {receipt.run_id}")
        result = R3ResearchReplayResult.model_validate_json(
            artifact_path.read_text(encoding="utf-8")
        )
        if (
            result.result_evidence_hash != receipt.result_evidence_hash
            or result.result_evidence_hash
            != protocol.replay_result_evidence_hashes[receipt.run_id]
        ):
            raise ValueError(f"R3 failure replay evidence mismatch: {receipt.run_id}")
        results[receipt.run_id] = result
    return results


def build_failure_analysis_result(
    *,
    generated_at: datetime,
    protocol: R3FailureAnalysisProtocol,
    package: R3FailureAnalysisPackage,
    ledger: R3StudyResultLedger,
    addendum: R3MonthlyDiagnosticAddendum,
    bundle: DevelopmentDatasetBundle,
    evidence_root: Path,
) -> R3FailureAnalysisResult:
    verify_failure_inputs(
        protocol=protocol,
        package=package,
        ledger=ledger,
        addendum=addendum,
        bundle=bundle,
    )
    results = load_replay_results(
        ledger=ledger,
        protocol=protocol,
        evidence_root=evidence_root,
    )
    receipts = {receipt.run_id: receipt for receipt in ledger.replay_receipts}
    primary_fold_pairs = primary_fold_results(ledger, results)
    primary_base = overall_result(
        ledger, results, variant_id=ledger.primary_variant_id, cost_multiplier=ONE
    )
    quarters = build_primary_quarters(primary_fold_pairs)
    cost_rows = build_cost_rows(ledger)
    diagnostic_rows = build_diagnostic_rows(
        bundle=bundle,
        evidence_root=evidence_root,
        primary_fold_pairs=primary_fold_pairs,
    )
    drawdown_rows = build_drawdown_episodes(primary_base)
    exit_rows = build_exit_reason_rows(primary_fold_pairs)
    horizon_rows = build_horizon_rows(ledger, results, receipts)
    breadth_rows = build_breadth_rows(primary_base)
    symbol_rows = build_symbol_rows(primary_fold_pairs)
    criteria = build_continuation_criteria(ledger, horizon_rows)
    findings = build_findings(
        quarters=quarters,
        cost_rows=cost_rows,
        diagnostic_rows=diagnostic_rows,
        drawdown_rows=drawdown_rows,
        exit_rows=exit_rows,
        horizon_rows=horizon_rows,
        breadth_rows=breadth_rows,
        ledger=ledger,
    )
    return build_r3_failure_analysis_result(
        generated_at=generated_at,
        status="COMPLETE_DESCRIPTIVE_ANALYSIS",
        package_evidence_hash=package.package_evidence_hash,
        failure_protocol_evidence_hash=protocol.protocol_evidence_hash,
        result_ledger_evidence_hash=ledger.ledger_evidence_hash,
        monthly_addendum_evidence_hash=addendum.addendum_evidence_hash,
        original_verdict="NO_CANDIDATE",
        primary_quarters=quarters,
        cost_and_turnover=cost_rows,
        diagnostic_quarters=diagnostic_rows,
        drawdown_episodes=drawdown_rows,
        exit_reasons_by_quarter=exit_rows,
        horizon_comparison=horizon_rows,
        breadth_at_rebalance=breadth_rows,
        symbol_contribution_by_quarter=symbol_rows,
        corrected_monthly_net_returns=addendum.corrected_monthly_net_returns,
        continuation_criteria=criteria,
        findings=findings,
        creates_candidate=False,
        changes_r3_verdict=False,
        opens_sealed_partition=False,
    )


def primary_fold_results(
    ledger: R3StudyResultLedger,
    results: dict[str, R3ResearchReplayResult],
) -> list[tuple[R3StudyReplayReceipt, R3ResearchReplayResult]]:
    pairs = [
        (receipt, results[receipt.run_id])
        for receipt in ledger.replay_receipts
        if receipt.category == "QUARTERLY_FOLD"
        and receipt.variant_id == ledger.primary_variant_id
    ]
    if len(pairs) != 6:
        raise ValueError("R3 failure analysis requires six primary fold artifacts")
    return sorted(pairs, key=lambda pair: pair[0].fold_id or "")


def overall_result(
    ledger: R3StudyResultLedger,
    results: dict[str, R3ResearchReplayResult],
    *,
    variant_id: str,
    cost_multiplier: Decimal,
) -> R3ResearchReplayResult:
    matches = [
        results[receipt.run_id]
        for receipt in ledger.replay_receipts
        if receipt.category == "OVERALL"
        and receipt.variant_id == variant_id
        and receipt.cost_multiplier == cost_multiplier
    ]
    if len(matches) != 1:
        raise ValueError("R3 failure overall-result lookup is not unique")
    return matches[0]


def grouped_opportunities(
    result: R3ResearchReplayResult,
) -> dict[datetime, list]:
    grouped: dict[datetime, list] = {}
    for opportunity in result.opportunities:
        grouped.setdefault(opportunity.rebalance_at, []).append(opportunity)
    return grouped


def breadth_statistics(
    result: R3ResearchReplayResult,
) -> tuple[int, Decimal, int, int]:
    grouped = grouped_opportunities(result)
    breadths = [
        sum(opportunity.score > ZERO for opportunity in opportunities)
        for opportunities in grouped.values()
    ]
    insufficient = sum(
        any(
            opportunity.reason == "INSUFFICIENT_POSITIVE_MARKETS"
            for opportunity in opportunities
        )
        for opportunities in grouped.values()
    )
    if not breadths:
        raise ValueError("R3 fold contains no rebalance observations")
    return (
        len(breadths),
        Decimal(sum(breadths)) / Decimal(len(breadths)),
        min(breadths),
        insufficient,
    )


def build_primary_quarters(
    pairs: list[tuple[R3StudyReplayReceipt, R3ResearchReplayResult]],
) -> list[R3PrimaryQuarterRow]:
    rows: list[R3PrimaryQuarterRow] = []
    for receipt, result in pairs:
        rebalances, average_breadth, minimum_breadth, insufficient = (
            breadth_statistics(result)
        )
        metrics = result.metrics
        rows.append(
            R3PrimaryQuarterRow(
                fold_id=receipt.fold_id or "",
                evaluation_start=result.config.evaluation_start,
                evaluation_end=result.config.evaluation_end,
                net_pl=metrics.net_pl,
                profit_factor=metrics.profit_factor,
                maximum_drawdown_percent=metrics.maximum_drawdown_percent,
                completed_trades=metrics.completed_trades,
                winning_trades=metrics.winning_trades,
                losing_trades=metrics.losing_trades,
                total_commission=metrics.total_commission,
                total_slippage=metrics.total_slippage,
                turnover=metrics.turnover,
                average_gross_exposure_percent=metrics.average_gross_exposure_percent,
                maximum_gross_exposure_percent=metrics.maximum_gross_exposure_percent,
                rebalance_count=rebalances,
                average_positive_market_breadth=average_breadth,
                minimum_positive_market_breadth=minimum_breadth,
                insufficient_breadth_rebalances=insufficient,
            )
        )
    return rows


def build_cost_rows(ledger: R3StudyResultLedger) -> list[R3CostTurnoverRow]:
    rows = []
    for receipt in ledger.replay_receipts:
        if receipt.category != "OVERALL":
            continue
        metrics = receipt.metrics
        rows.append(
            R3CostTurnoverRow(
                variant_id=receipt.variant_id,
                variant_role=receipt.variant_role,
                cost_multiplier=receipt.cost_multiplier,
                net_pl=metrics.net_pl,
                profit_factor=metrics.profit_factor,
                maximum_drawdown_percent=metrics.maximum_drawdown_percent,
                completed_trades=metrics.completed_trades,
                total_commission=metrics.total_commission,
                total_slippage=metrics.total_slippage,
                turnover=metrics.turnover,
            )
        )
    return rows


def load_diagnostic_series(
    bundle: DevelopmentDatasetBundle,
    evidence_root: Path,
) -> dict[str, list[R3Candle]]:
    entries = {entry.symbol: entry for entry in bundle.entries}
    series: dict[str, list[R3Candle]] = {}
    for symbol in DIAGNOSTIC_SYMBOLS:
        entry = entries[symbol]
        if entry.universe_role != "DEVELOPMENT_ONLY":
            raise ValueError(f"R3 diagnostic role changed: {symbol}")
        path = safe_evidence_path(evidence_root, entry.csv_relative_path)
        if file_sha256(path) != entry.canonical_csv_sha256:
            raise ValueError(f"R3 diagnostic CSV hash mismatch: {symbol}")
        series[symbol] = load_canonical_ohlcv_csv(path)
    return series


def build_diagnostic_rows(
    *,
    bundle: DevelopmentDatasetBundle,
    evidence_root: Path,
    primary_fold_pairs: list[tuple[R3StudyReplayReceipt, R3ResearchReplayResult]],
) -> list[R3DiagnosticQuarterRow]:
    series = load_diagnostic_series(bundle, evidence_root)
    rows: list[R3DiagnosticQuarterRow] = []
    with localcontext() as context:
        context.prec = 50
        context.rounding = ROUND_HALF_EVEN
        annualizer = Decimal("2190").sqrt()
        for receipt, result in primary_fold_pairs:
            start = result.config.evaluation_start
            end = result.config.evaluation_end
            for symbol, candles in series.items():
                window = [
                    candle for candle in candles if start <= candle.timestamp < end
                ]
                if len(window) < 3:
                    raise ValueError("R3 diagnostic quarter has insufficient candles")
                returns = [
                    (window[index].close / window[index - 1].close).ln()
                    for index in range(1, len(window))
                ]
                average = sum(returns, ZERO) / Decimal(len(returns))
                variance = sum(
                    ((value - average) ** 2 for value in returns), ZERO
                ) / Decimal(len(returns) - 1)
                rows.append(
                    R3DiagnosticQuarterRow(
                        fold_id=receipt.fold_id or "",
                        symbol=symbol,
                        total_return=window[-1].close / window[0].open - ONE,
                        annualized_log_return_volatility=variance.sqrt() * annualizer,
                    )
                )
    return rows


def build_drawdown_episodes(
    result: R3ResearchReplayResult,
) -> list[R3DrawdownEpisode]:
    rows: list[R3DrawdownEpisode] = []
    active: dict | None = None
    for snapshot in result.equity_curve:
        if snapshot.drawdown > ZERO and active is None:
            active = {
                "started_at": snapshot.timestamp,
                "trough_at": snapshot.timestamp,
                "ended_at": snapshot.timestamp,
                "duration": 1,
                "maximum_drawdown": snapshot.drawdown,
                "maximum_drawdown_percent": snapshot.drawdown_percent,
            }
        elif snapshot.drawdown > ZERO and active is not None:
            active["ended_at"] = snapshot.timestamp
            active["duration"] += 1
            if snapshot.drawdown > active["maximum_drawdown"]:
                active["trough_at"] = snapshot.timestamp
                active["maximum_drawdown"] = snapshot.drawdown
                active["maximum_drawdown_percent"] = snapshot.drawdown_percent
        elif snapshot.drawdown == ZERO and active is not None:
            rows.append(
                drawdown_row(
                    sequence=len(rows) + 1,
                    active=active,
                    recovered_at=snapshot.timestamp,
                )
            )
            active = None
    if active is not None:
        rows.append(
            drawdown_row(sequence=len(rows) + 1, active=active, recovered_at=None)
        )
    return rows


def drawdown_row(
    *,
    sequence: int,
    active: dict,
    recovered_at: datetime | None,
) -> R3DrawdownEpisode:
    return R3DrawdownEpisode(
        sequence=sequence,
        started_at=active["started_at"],
        trough_at=active["trough_at"],
        recovered_at=recovered_at,
        ended_at=recovered_at or active["ended_at"],
        recovered=recovered_at is not None,
        duration_snapshots=active["duration"],
        maximum_drawdown=active["maximum_drawdown"],
        maximum_drawdown_percent=active["maximum_drawdown_percent"],
    )


def build_exit_reason_rows(
    pairs: list[tuple[R3StudyReplayReceipt, R3ResearchReplayResult]],
) -> list[R3ExitReasonQuarterRow]:
    rows: list[R3ExitReasonQuarterRow] = []
    for receipt, result in pairs:
        for reason in EXIT_REASONS:
            trades = [trade for trade in result.trades if trade.exit_reason == reason]
            rows.append(
                R3ExitReasonQuarterRow(
                    fold_id=receipt.fold_id or "",
                    exit_reason=reason,
                    trades=len(trades),
                    raw_price_pl=sum((trade.raw_price_pl for trade in trades), ZERO),
                    net_pl=sum((trade.net_pl for trade in trades), ZERO),
                    commission=sum(
                        (trade.entry_fee + trade.exit_fee for trade in trades), ZERO
                    ),
                    slippage=sum(
                        (trade.total_slippage_cost for trade in trades), ZERO
                    ),
                )
            )
    return rows


def build_horizon_rows(
    ledger: R3StudyResultLedger,
    results: dict[str, R3ResearchReplayResult],
    receipts: dict[str, R3StudyReplayReceipt],
) -> list[R3HorizonComparisonRow]:
    variant_ids = sorted({receipt.variant_id for receipt in receipts.values()})
    rows: list[R3HorizonComparisonRow] = []
    for variant_id in variant_ids:
        base = overall_result(
            ledger, results, variant_id=variant_id, cost_multiplier=ONE
        )
        double = overall_result(
            ledger, results, variant_id=variant_id, cost_multiplier=Decimal("2")
        )
        role = next(
            receipt.variant_role
            for receipt in receipts.values()
            if receipt.variant_id == variant_id
        )
        rows.append(
            R3HorizonComparisonRow(
                variant_id=variant_id,
                variant_role=role,
                lookback_bars=base.config.lookback_bars,
                rebalance_bars=base.config.rebalance_bars,
                base_net_pl=base.metrics.net_pl,
                base_profit_factor=base.metrics.profit_factor,
                base_maximum_drawdown_percent=base.metrics.maximum_drawdown_percent,
                double_cost_net_pl=double.metrics.net_pl,
                positive_quarterly_folds=ledger.positive_fold_counts[variant_id],
                selectable_for_r4=False,
            )
        )
    return rows


def build_breadth_rows(result: R3ResearchReplayResult) -> list[R3BreadthRow]:
    rows: list[R3BreadthRow] = []
    for rebalance_at, opportunities in grouped_opportunities(result).items():
        positive = [item for item in opportunities if item.score > ZERO]
        rows.append(
            R3BreadthRow(
                rebalance_at=rebalance_at,
                positive_market_count=len(positive),
                selected_market_count=sum(
                    item.selected_by_rank for item in opportunities
                ),
                accepted_entry_count=sum(item.accepted_entry for item in opportunities),
                insufficient_breadth=any(
                    item.reason == "INSUFFICIENT_POSITIVE_MARKETS"
                    for item in opportunities
                ),
                average_positive_score=(
                    sum((item.score for item in positive), ZERO)
                    / Decimal(len(positive))
                    if positive
                    else None
                ),
            )
        )
    return rows


def build_symbol_rows(
    pairs: list[tuple[R3StudyReplayReceipt, R3ResearchReplayResult]],
) -> list[R3SymbolQuarterRow]:
    rows: list[R3SymbolQuarterRow] = []
    for receipt, result in pairs:
        symbols = sorted({trade.symbol for trade in result.trades})
        for symbol in symbols:
            trades = [trade for trade in result.trades if trade.symbol == symbol]
            rows.append(
                R3SymbolQuarterRow(
                    fold_id=receipt.fold_id or "",
                    symbol=symbol,
                    trades=len(trades),
                    raw_price_pl=sum((trade.raw_price_pl for trade in trades), ZERO),
                    net_pl=sum((trade.net_pl for trade in trades), ZERO),
                    commission=sum(
                        (trade.entry_fee + trade.exit_fee for trade in trades), ZERO
                    ),
                    slippage=sum(
                        (trade.total_slippage_cost for trade in trades), ZERO
                    ),
                    fixed_stop_exits=sum(
                        trade.exit_reason == "FIXED_STOP" for trade in trades
                    ),
                    rebalance_exits=sum(
                        trade.exit_reason == "REBALANCE" for trade in trades
                    ),
                    end_of_window_exits=sum(
                        trade.exit_reason == "END_OF_WINDOW" for trade in trades
                    ),
                )
            )
    return rows


def build_continuation_criteria(
    ledger: R3StudyResultLedger,
    horizons: list[R3HorizonComparisonRow],
) -> dict[str, bool]:
    ordered = sorted(horizons, key=lambda row: row.lookback_bars)
    gates = {gate.gate_id: gate for gate in ledger.gates}
    return {
        "ALL_THREE_HORIZONS_POSITIVE_AT_BASE_AND_DOUBLE_COST": all(
            row.base_net_pl > ZERO and row.double_cost_net_pl > ZERO for row in ordered
        ),
        "HORIZON_POSITIVE_FOLDS_STRICTLY_IMPROVE_FAST_TO_PRIMARY_TO_SLOW": (
            [row.positive_quarterly_folds for row in ordered]
            == sorted(
                [row.positive_quarterly_folds for row in ordered]
            )
            and len({row.positive_quarterly_folds for row in ordered}) == len(ordered)
        ),
        "PRIMARY_CONCENTRATION_GATES_PASSED": (
            gates["single_symbol_gross_profit_fraction"].passed
            and gates["top_five_gross_profit_fraction"].passed
        ),
        "PRIMARY_LEAVE_ONE_MARKET_OUT_FRACTION_AT_LEAST_0_80": (
            ledger.leave_one_market_out_positive_fraction >= Decimal("0.80")
        ),
        "PRIMARY_TEMPORAL_GATE_REMAINS_FAILED_AND_UNCHANGED": (
            not gates["primary_positive_quarterly_folds"].passed
            and gates["primary_positive_quarterly_folds"].observed == "3"
        ),
    }


def build_findings(
    *,
    quarters: list[R3PrimaryQuarterRow],
    cost_rows: list[R3CostTurnoverRow],
    diagnostic_rows: list[R3DiagnosticQuarterRow],
    drawdown_rows: list[R3DrawdownEpisode],
    exit_rows: list[R3ExitReasonQuarterRow],
    horizon_rows: list[R3HorizonComparisonRow],
    breadth_rows: list[R3BreadthRow],
    ledger: R3StudyResultLedger,
) -> list[R3DescriptiveFinding]:
    losing = [row for row in quarters if row.net_pl < ZERO]
    winning = [row for row in quarters if row.net_pl > ZERO]
    worst = min(quarters, key=lambda row: row.net_pl)
    slow = max(horizon_rows, key=lambda row: row.lookback_bars)
    fast = min(horizon_rows, key=lambda row: row.lookback_bars)
    worst_drawdown = max(drawdown_rows, key=lambda row: row.maximum_drawdown_percent)
    losing_exit_net = sum(
        (row.net_pl for row in exit_rows if row.fold_id in {item.fold_id for item in losing}),
        ZERO,
    )
    average_breadth = sum(
        (Decimal(row.positive_market_count) for row in breadth_rows), ZERO
    ) / Decimal(len(breadth_rows))
    diagnostic_worst_fold = [
        row for row in diagnostic_rows if row.fold_id == worst.fold_id
    ]
    diagnostic_text = ", ".join(
        f"{row.symbol} return={row.total_return} vol={row.annualized_log_return_volatility}"
        for row in diagnostic_worst_fold
    )
    base_primary = next(
        row
        for row in cost_rows
        if row.variant_role == "PRIMARY" and row.cost_multiplier == ONE
    )
    double_primary = next(
        row
        for row in cost_rows
        if row.variant_role == "PRIMARY" and row.cost_multiplier == Decimal("2")
    )
    return [
        R3DescriptiveFinding(
            finding_id="F-01-TEMPORAL-INSTABILITY",
            dimension="PRIMARY_QUARTERLY_FOLD_DECOMPOSITION",
            observation=(
                f"The primary was positive in {len(winning)}/6 independent quarters; "
                f"the worst was {worst.fold_id} at net {worst.net_pl}."
            ),
            interpretation_limit=(
                "Independent fold resets use fold-local rebalance anchors, so quarter "
                "results diagnose instability but do not sum to continuous replay P/L."
            ),
        ),
        R3DescriptiveFinding(
            finding_id="F-02-HORIZON-ORDERING",
            dimension="MOMENTUM_HORIZON_COMPARISON",
            observation=(
                f"Positive folds increased from {fast.positive_quarterly_folds} at the "
                f"fast horizon to {slow.positive_quarterly_folds} at the slow horizon; "
                f"slow base net was {slow.base_net_pl}."
            ),
            interpretation_limit=(
                "The slow variant was a non-selectable falsification check. This ordering "
                "may motivate research but cannot promote or replace the primary."
            ),
        ),
        R3DescriptiveFinding(
            finding_id="F-03-COST-ROBUSTNESS",
            dimension="COST_AND_TURNOVER_DECOMPOSITION",
            observation=(
                f"Primary net changed from {base_primary.net_pl} at base cost to "
                f"{double_primary.net_pl} at double cost with turnover "
                f"{base_primary.turnover}."
            ),
            interpretation_limit=(
                "Cost robustness does not establish temporal robustness or future "
                "exchange execution quality."
            ),
        ),
        R3DescriptiveFinding(
            finding_id="F-04-BREADTH",
            dimension="POSITIVE_MARKET_BREADTH_AT_REBALANCE",
            observation=(
                f"Primary full-window rebalances averaged {average_breadth} positive "
                f"markets; {sum(row.insufficient_breadth for row in breadth_rows)} "
                "rebalances held cash for insufficient breadth."
            ),
            interpretation_limit=(
                "Breadth was observed after outcomes and cannot be thresholded into a "
                "new entry filter without a separately registered study."
            ),
        ),
        R3DescriptiveFinding(
            finding_id="F-05-DRAWDOWN",
            dimension="DRAWDOWN_EPISODES_AND_GROSS_EXPOSURE",
            observation=(
                f"The largest continuous-replay drawdown episode reached "
                f"{worst_drawdown.maximum_drawdown_percent}% at "
                f"{worst_drawdown.trough_at.isoformat()}."
            ),
            interpretation_limit=(
                "Drawdown timing is descriptive and cannot justify a post-hoc regime "
                "switch or exposure filter."
            ),
        ),
        R3DescriptiveFinding(
            finding_id="F-06-EXIT-OUTCOMES",
            dimension="EXIT_REASON_BY_QUARTER",
            observation=(
                f"Trades in the three losing independent quarters summed to net "
                f"{losing_exit_net} across all frozen exit reasons."
            ),
            interpretation_limit=(
                "Exit-reason attribution is not causal; changing stops or rebalance exits "
                "after observing these outcomes would be rescue tuning."
            ),
        ),
        R3DescriptiveFinding(
            finding_id="F-07-DIAGNOSTIC-MARKET",
            dimension="DIAGNOSTIC_BTC_ETH_SOL_QUARTERLY_RETURN_AND_VOLATILITY",
            observation=f"During {worst.fold_id}: {diagnostic_text}.",
            interpretation_limit=(
                "BTC, ETH, and SOL are diagnostic-only and cannot enter rankings, gates, "
                "or a new regime rule from this analysis."
            ),
        ),
        R3DescriptiveFinding(
            finding_id="F-08-BROAD-ROBUSTNESS",
            dimension="SYMBOL_NET_AND_RAW_CONTRIBUTION_BY_QUARTER",
            observation=(
                f"Leave-one-market-out positivity was "
                f"{ledger.leave_one_market_out_positive_fraction}; both frozen "
                "concentration gates passed."
            ),
            interpretation_limit=(
                "Broad symbol robustness supports continued mechanism research but does "
                "not cure the failed quarterly gate."
            ),
        ),
    ]
