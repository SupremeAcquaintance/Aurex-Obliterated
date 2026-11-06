from __future__ import annotations

import shutil
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext
from pathlib import Path

from aurex.backtest_engine.binance_vision import file_sha256
from aurex.backtest_engine.development_bundle import (
    DevelopmentDatasetBundle,
    safe_evidence_path,
)
from aurex.backtest_engine.research_study_runner import load_canonical_ohlcv_csv
from aurex.backtest_engine.research_u1_engine import (
    U1PreparedMarketData,
    U1ResearchReplayConfig,
    U1ResearchReplayResult,
    audit_u1_research_replay,
    prepare_u1_market_data,
    run_u1_research_replay,
)
from aurex.backtest_engine.research_u1_execution_spec import (
    U1ExecutionSpecification,
)
from aurex.backtest_engine.research_u1_primary_protocol import U1PrimaryProtocol
from aurex.backtest_engine.research_u1_result import (
    U1GateResult,
    U1ReplayReceipt,
    U1ResultLedger,
    build_u1_result_ledger,
)
from aurex.backtest_engine.research_u1_run_package import (
    U1PlannedReplay,
    U1RunPackage,
)


def build_u1_planned_replays(
    protocol: U1PrimaryProtocol,
) -> list[U1PlannedReplay]:
    plans: list[U1PlannedReplay] = []
    variant_id = "volatility_managed_broad_spot_beta_v1"
    for multiplier in protocol.costs.stress_multipliers:
        plans.append(
            U1PlannedReplay(
                run_id=f"overall--{variant_id}--cost-{decimal_label(multiplier)}",
                category="OVERALL",
                variant_role="PRIMARY",
                cost_multiplier=multiplier,
                evaluation_start=protocol.evaluation_start,
                evaluation_end=protocol.evaluation_end,
            )
        )
    plans.append(
        U1PlannedReplay(
            run_id="benchmark--static_broad_spot_equal_weight_v1--cost-1",
            category="BENCHMARK",
            variant_role="BENCHMARK",
            cost_multiplier=Decimal("1"),
            evaluation_start=protocol.evaluation_start,
            evaluation_end=protocol.evaluation_end,
        )
    )
    for fold in protocol.folds:
        plans.append(
            U1PlannedReplay(
                run_id=f"fold--{variant_id}--{fold.fold_id}",
                category="TEMPORAL_FOLD",
                variant_role="PRIMARY",
                cost_multiplier=Decimal("1"),
                evaluation_start=fold.evaluation_start,
                evaluation_end=fold.evaluation_end,
                fold_id=fold.fold_id,
            )
        )
    for symbol in protocol.decision_symbols:
        plans.append(
            U1PlannedReplay(
                run_id=f"lomo--{variant_id}--without-{symbol}",
                category="LEAVE_ONE_MARKET_OUT",
                variant_role="PRIMARY",
                cost_multiplier=Decimal("1"),
                evaluation_start=protocol.evaluation_start,
                evaluation_end=protocol.evaluation_end,
                omitted_symbols=[symbol],
            )
        )
    ordered = sorted(plans, key=lambda plan: plan.run_id)
    if len(ordered) != 47:
        raise ValueError("U1 replay plan must contain exactly 47 runs")
    return ordered


def load_u1_market_data(
    *,
    development_bundle: DevelopmentDatasetBundle,
    evidence_root: Path,
    decision_symbols: list[str],
) -> U1PreparedMarketData:
    expected = sorted(decision_symbols)
    entries = {entry.symbol: entry for entry in development_bundle.entries}
    if any(symbol not in entries for symbol in expected):
        raise ValueError("U1 development bundle is missing a decision market")
    candles_by_symbol = {}
    for symbol in expected:
        entry = entries[symbol]
        if entry.universe_role != "DECISION_CANDIDATE" or entry.status != "READY":
            raise ValueError(f"U1 decision dataset is not ready: {symbol}")
        path = safe_evidence_path(evidence_root, entry.csv_relative_path)
        if file_sha256(path) != entry.canonical_csv_sha256:
            raise ValueError(f"U1 decision CSV hash mismatch: {symbol}")
        candles = load_canonical_ohlcv_csv(path)
        if (
            len(candles) != entry.row_count
            or candles[0].timestamp != entry.first_timestamp
            or candles[-1].timestamp != entry.last_timestamp
        ):
            raise ValueError(f"U1 decision CSV metadata mismatch: {symbol}")
        candles_by_symbol[symbol] = candles
    market_data = prepare_u1_market_data(
        candles_by_symbol,
        data_start=development_bundle.partition_start,
        data_end=development_bundle.partition_end,
    )
    if list(market_data.symbols) != expected:
        raise ValueError("U1 transformed data changed the decision universe")
    for symbol in expected:
        if market_data.actual_rows_by_symbol[symbol] != entries[symbol].row_count:
            raise ValueError(f"U1 transformed row count changed: {symbol}")
    return market_data


def build_u1_replay_config(
    *,
    plan: U1PlannedReplay,
    protocol: U1PrimaryProtocol,
    execution_specification: U1ExecutionSpecification,
    market_data: U1PreparedMarketData,
) -> U1ResearchReplayConfig:
    return U1ResearchReplayConfig(
        variant_role=plan.variant_role,
        evaluation_start=plan.evaluation_start,
        evaluation_end=plan.evaluation_end,
        baseline_decision_symbols=protocol.decision_symbols,
        omitted_symbols=plan.omitted_symbols,
        initial_capital=protocol.portfolio.initial_capital,
        max_gross_exposure_percent=protocol.portfolio.maximum_gross_exposure_percent,
        quantity_increment=protocol.portfolio.quantity_increment_assumption,
        price_increment=protocol.portfolio.price_increment_assumption,
        commission_percent_per_side=protocol.costs.commission_percent_per_side,
        adverse_slippage_percent_per_side=(
            protocol.costs.adverse_slippage_percent_per_side
        ),
        cost_multiplier=plan.cost_multiplier,
        discovery_charter_evidence_hash=protocol.discovery_charter_evidence_hash,
        theory_screen_evidence_hash=protocol.theory_screen_evidence_hash,
        primary_protocol_evidence_hash=protocol.protocol_evidence_hash,
        execution_specification_evidence_hash=(
            execution_specification.specification_evidence_hash
        ),
        universe_manifest_evidence_hash=protocol.universe_manifest_evidence_hash,
        development_dataset_bundle_evidence_hash=(
            protocol.development_dataset_bundle_evidence_hash
        ),
        market_data_evidence_hash=market_data.market_data_evidence_hash,
    )


def verify_u1_run_package_sources(
    package: U1RunPackage,
    project_root: Path,
) -> None:
    resolved_root = project_root.resolve()
    for relative_path, expected_hash in package.source_file_sha256.items():
        path = (project_root / relative_path).resolve()
        if not path.is_relative_to(resolved_root) or not path.is_file():
            raise ValueError(f"U1 run-package source is missing: {relative_path}")
        if file_sha256(path) != expected_hash:
            raise ValueError(f"U1 run-package source hash changed: {relative_path}")


def verify_u1_study_bindings(
    *,
    protocol: U1PrimaryProtocol,
    execution_specification: U1ExecutionSpecification,
    run_package: U1RunPackage,
    market_data: U1PreparedMarketData,
) -> None:
    expected = {
        "discovery_charter_evidence_hash": protocol.discovery_charter_evidence_hash,
        "theory_screen_evidence_hash": protocol.theory_screen_evidence_hash,
        "universe_manifest_evidence_hash": protocol.universe_manifest_evidence_hash,
        "development_dataset_bundle_evidence_hash": (
            protocol.development_dataset_bundle_evidence_hash
        ),
        "contamination_ledger_evidence_hash": (
            protocol.contamination_ledger_evidence_hash
        ),
        "primary_protocol_evidence_hash": protocol.protocol_evidence_hash,
        "execution_specification_evidence_hash": (
            execution_specification.specification_evidence_hash
        ),
        "market_data_evidence_hash": market_data.market_data_evidence_hash,
    }
    for field, value in expected.items():
        if getattr(run_package, field) != value:
            raise ValueError(f"U1 run package changed evidence binding: {field}")
    if (
        execution_specification.primary_protocol_evidence_hash
        != protocol.protocol_evidence_hash
    ):
        raise ValueError("U1 execution specification does not match protocol")
    if run_package.planned_replays != build_u1_planned_replays(protocol):
        raise ValueError("U1 replay plan changed after freeze")
    if (
        run_package.validation_data_loaded
        or run_package.holdout_data_loaded
        or run_package.forward_data_loaded
    ):
        raise ValueError("U1 development package crossed a sealed partition")


def execute_u1_study(
    *,
    protocol: U1PrimaryProtocol,
    execution_specification: U1ExecutionSpecification,
    run_package: U1RunPackage,
    market_data: U1PreparedMarketData,
    evidence_root: Path,
    project_root: Path,
    generated_at: datetime | None = None,
) -> U1ResultLedger:
    verify_u1_study_bindings(
        protocol=protocol,
        execution_specification=execution_specification,
        run_package=run_package,
        market_data=market_data,
    )
    verify_u1_run_package_sources(run_package, project_root)
    ledger_path = safe_evidence_path(
        evidence_root, run_package.result_ledger_relative_path
    )
    artifact_directory = safe_evidence_path(
        evidence_root, run_package.replay_artifact_directory_relative_path
    )
    if ledger_path.exists() or artifact_directory.exists():
        raise ValueError("U1 evidence exists; the development study is one-shot")
    temporary_directory = artifact_directory.with_name(
        f"{artifact_directory.name}.part"
    )
    temporary_ledger = ledger_path.with_name(f"{ledger_path.name}.part")
    remove_u1_temporary_directory(temporary_directory, evidence_root)
    if temporary_ledger.exists():
        temporary_ledger.unlink()
    temporary_directory.mkdir(parents=True, exist_ok=False)

    results: dict[str, U1ResearchReplayResult] = {}
    receipts: list[U1ReplayReceipt] = []
    artifact_directory_committed = False
    try:
        for plan in run_package.planned_replays:
            config = build_u1_replay_config(
                plan=plan,
                protocol=protocol,
                execution_specification=execution_specification,
                market_data=market_data,
            )
            result = run_u1_research_replay(config, market_data)
            replay_audit = audit_u1_research_replay(config, market_data, result)
            if replay_audit.status != "PASS":
                raise ValueError(
                    f"U1 deterministic replay failed before commit: {plan.run_id}"
                )
            filename = f"{plan.run_id}.json"
            temporary_path = temporary_directory / filename
            serialized = result.model_dump_json(indent=2) + "\n"
            if U1ResearchReplayResult.model_validate_json(serialized) != result:
                raise ValueError(f"U1 result JSON did not round-trip: {plan.run_id}")
            temporary_path.write_text(serialized, encoding="utf-8")
            artifact_relative = (
                Path(run_package.replay_artifact_directory_relative_path) / filename
            ).as_posix()
            results[plan.run_id] = result
            receipts.append(
                U1ReplayReceipt(
                    run_id=plan.run_id,
                    category=plan.category,
                    variant_role=plan.variant_role,
                    cost_multiplier=plan.cost_multiplier,
                    fold_id=plan.fold_id,
                    omitted_symbols=plan.omitted_symbols,
                    artifact_relative_path=artifact_relative,
                    request_evidence_hash=result.request_evidence_hash,
                    result_evidence_hash=result.result_evidence_hash,
                    artifact_sha256=file_sha256(temporary_path),
                    deterministic_replay_audit_passed=True,
                    metrics=result.metrics,
                )
            )
        ledger = build_u1_study_result_ledger(
            protocol=protocol,
            execution_specification=execution_specification,
            run_package=run_package,
            market_data=market_data,
            receipts=receipts,
            results=results,
            generated_at=generated_at or datetime.now(UTC),
        )
        serialized_ledger = ledger.model_dump_json(indent=2) + "\n"
        if U1ResultLedger.model_validate_json(serialized_ledger) != ledger:
            raise ValueError("U1 ledger JSON did not round-trip")
        temporary_ledger.parent.mkdir(parents=True, exist_ok=True)
        temporary_ledger.write_text(serialized_ledger, encoding="utf-8")
        artifact_directory.parent.mkdir(parents=True, exist_ok=True)
        temporary_directory.replace(artifact_directory)
        artifact_directory_committed = True
        temporary_ledger.replace(ledger_path)
        return ledger
    except Exception:
        remove_u1_temporary_directory(temporary_directory, evidence_root)
        if artifact_directory_committed and not ledger_path.exists():
            remove_u1_committed_artifact_directory(
                artifact_directory, evidence_root
            )
        if temporary_ledger.exists():
            temporary_ledger.unlink()
        raise


def audit_u1_study_artifacts(
    *,
    protocol: U1PrimaryProtocol,
    execution_specification: U1ExecutionSpecification,
    run_package: U1RunPackage,
    market_data: U1PreparedMarketData,
    evidence_root: Path,
    project_root: Path,
    deterministic_replay: bool,
) -> U1ResultLedger:
    verify_u1_study_bindings(
        protocol=protocol,
        execution_specification=execution_specification,
        run_package=run_package,
        market_data=market_data,
    )
    verify_u1_run_package_sources(run_package, project_root)
    ledger_path = safe_evidence_path(
        evidence_root, run_package.result_ledger_relative_path
    )
    ledger = U1ResultLedger.model_validate_json(
        ledger_path.read_text(encoding="utf-8")
    )
    receipts = {receipt.run_id: receipt for receipt in ledger.replay_receipts}
    planned_ids = [plan.run_id for plan in run_package.planned_replays]
    if sorted(receipts) != planned_ids:
        raise ValueError("U1 receipts do not match the frozen plan")

    results: dict[str, U1ResearchReplayResult] = {}
    for plan in run_package.planned_replays:
        receipt = receipts[plan.run_id]
        if (
            receipt.category != plan.category
            or receipt.variant_role != plan.variant_role
            or receipt.cost_multiplier != plan.cost_multiplier
            or receipt.fold_id != plan.fold_id
            or receipt.omitted_symbols != plan.omitted_symbols
        ):
            raise ValueError(f"U1 receipt changed its plan: {plan.run_id}")
        artifact_path = safe_evidence_path(
            evidence_root, receipt.artifact_relative_path
        )
        if file_sha256(artifact_path) != receipt.artifact_sha256:
            raise ValueError(f"U1 artifact hash mismatch: {plan.run_id}")
        result = U1ResearchReplayResult.model_validate_json(
            artifact_path.read_text(encoding="utf-8")
        )
        expected_config = build_u1_replay_config(
            plan=plan,
            protocol=protocol,
            execution_specification=execution_specification,
            market_data=market_data,
        )
        if result.config != expected_config:
            raise ValueError(f"U1 replay config changed: {plan.run_id}")
        if (
            result.request_evidence_hash != receipt.request_evidence_hash
            or result.result_evidence_hash != receipt.result_evidence_hash
            or result.metrics != receipt.metrics
        ):
            raise ValueError(f"U1 receipt evidence mismatch: {plan.run_id}")
        if deterministic_replay:
            replay_audit = audit_u1_research_replay(
                expected_config, market_data, result
            )
            if replay_audit.status != "PASS":
                raise ValueError(f"U1 deterministic mismatch: {plan.run_id}")
        results[plan.run_id] = result

    rebuilt = build_u1_study_result_ledger(
        protocol=protocol,
        execution_specification=execution_specification,
        run_package=run_package,
        market_data=market_data,
        receipts=ledger.replay_receipts,
        results=results,
        generated_at=ledger.generated_at,
    )
    if rebuilt != ledger:
        raise ValueError("U1 ledger differs from its deterministic rebuild")
    return ledger


def build_u1_study_result_ledger(
    *,
    protocol: U1PrimaryProtocol,
    execution_specification: U1ExecutionSpecification,
    run_package: U1RunPackage,
    market_data: U1PreparedMarketData,
    receipts: list[U1ReplayReceipt],
    results: dict[str, U1ResearchReplayResult],
    generated_at: datetime,
) -> U1ResultLedger:
    primary = find_u1_result(
        run_package,
        results,
        category="OVERALL",
        cost_multiplier=Decimal("1"),
    )
    double_cost = find_u1_result(
        run_package,
        results,
        category="OVERALL",
        cost_multiplier=Decimal("2"),
    )
    benchmark = find_u1_result(
        run_package,
        results,
        category="BENCHMARK",
        cost_multiplier=Decimal("1"),
    )
    positive_folds = sum(
        result.metrics.net_pl > 0
        for plan, result in planned_u1_results(run_package, results)
        if plan.category == "TEMPORAL_FOLD"
    )
    lomo = [
        result
        for plan, result in planned_u1_results(run_package, results)
        if plan.category == "LEAVE_ONE_MARKET_OUT"
    ]
    with localcontext() as context:
        context.prec = 50
        lomo_fraction = Decimal(
            sum(result.metrics.net_pl > 0 for result in lomo)
        ) / Decimal(len(lomo))
    all_audits_passed = (
        len(receipts) == run_package.expected_replay_count
        and all(receipt.deterministic_replay_audit_passed for receipt in receipts)
    )
    gates = evaluate_u1_gates(
        protocol=protocol,
        primary=primary,
        double_cost=double_cost,
        benchmark=benchmark,
        positive_folds=positive_folds,
        lomo_positive_fraction=lomo_fraction,
        all_replay_audits_passed=all_audits_passed,
    )
    return build_u1_result_ledger(
        generated_at=generated_at,
        discovery_charter_evidence_hash=protocol.discovery_charter_evidence_hash,
        theory_screen_evidence_hash=protocol.theory_screen_evidence_hash,
        universe_manifest_evidence_hash=protocol.universe_manifest_evidence_hash,
        development_dataset_bundle_evidence_hash=(
            protocol.development_dataset_bundle_evidence_hash
        ),
        contamination_ledger_evidence_hash=(
            protocol.contamination_ledger_evidence_hash
        ),
        primary_protocol_evidence_hash=protocol.protocol_evidence_hash,
        execution_specification_evidence_hash=(
            execution_specification.specification_evidence_hash
        ),
        run_package_evidence_hash=run_package.package_evidence_hash,
        market_data_evidence_hash=market_data.market_data_evidence_hash,
        replay_receipts=receipts,
        monthly_net_returns=u1_monthly_net_returns(primary),
        positive_temporal_folds=positive_folds,
        leave_one_market_out_positive_fraction=lomo_fraction,
        all_replay_audits_passed=all_audits_passed,
        base_cost_termination_writeoff_count=(
            primary.metrics.termination_writeoff_count
        ),
        base_cost_termination_writeoff_net_pl=(
            primary.metrics.termination_writeoff_net_pl
        ),
        primary_base_metrics=primary.metrics,
        benchmark_base_metrics=benchmark.metrics,
        gates=gates,
    )


def evaluate_u1_gates(
    *,
    protocol: U1PrimaryProtocol,
    primary: U1ResearchReplayResult,
    double_cost: U1ResearchReplayResult,
    benchmark: U1ResearchReplayResult,
    positive_folds: int,
    lomo_positive_fraction: Decimal,
    all_replay_audits_passed: bool,
) -> list[U1GateResult]:
    metrics = primary.metrics
    benchmark_metrics = benchmark.metrics
    gates = protocol.gates
    primary_efficiency = metrics.return_to_drawdown
    benchmark_efficiency = benchmark_metrics.return_to_drawdown
    minimum_profit_factor = Decimal(gates.minimum_primary_profit_factor)
    maximum_drawdown_percent = Decimal(
        gates.maximum_primary_drawdown_percent
    )
    minimum_lomo_fraction = Decimal(
        gates.minimum_leave_one_market_out_positive_fraction
    )
    maximum_single_fraction = Decimal(
        gates.maximum_single_symbol_gross_profit_fraction
    )
    maximum_top_five_fraction = Decimal(
        gates.maximum_top_five_gross_profit_fraction
    )
    return [
        gate(
            "benchmark_maximum_drawdown_not_worse",
            metrics.maximum_drawdown_percent
            <= benchmark_metrics.maximum_drawdown_percent,
            (
                f"primary={metrics.maximum_drawdown_percent};"
                f"benchmark={benchmark_metrics.maximum_drawdown_percent}"
            ),
            "primary maximum drawdown percent <= benchmark",
        ),
        gate(
            "benchmark_realized_volatility_reduction",
            metrics.realized_equity_volatility
            < benchmark_metrics.realized_equity_volatility,
            (
                f"primary={metrics.realized_equity_volatility};"
                f"benchmark={benchmark_metrics.realized_equity_volatility}"
            ),
            "primary realized equity volatility < benchmark",
        ),
        gate(
            "benchmark_return_to_drawdown_not_worse",
            primary_efficiency is not None
            and benchmark_efficiency is not None
            and primary_efficiency >= benchmark_efficiency,
            f"primary={primary_efficiency};benchmark={benchmark_efficiency}",
            "primary return-to-drawdown >= benchmark; null fails",
        ),
        gate(
            "deterministic_replay_audit",
            all_replay_audits_passed,
            all_replay_audits_passed,
            "all 47 immediate deterministic replay audits pass",
        ),
        gate(
            "double_cost_net_pl",
            double_cost.metrics.net_pl > 0,
            double_cost.metrics.net_pl,
            "strictly greater than 0 at 2x commission and slippage",
        ),
        gate(
            "leave_one_market_out_positive_fraction",
            lomo_positive_fraction >= minimum_lomo_fraction,
            lomo_positive_fraction,
            f">= {minimum_lomo_fraction}",
        ),
        gate(
            "primary_completed_trades",
            metrics.completed_trades >= gates.minimum_primary_completed_trades,
            metrics.completed_trades,
            f">= {gates.minimum_primary_completed_trades}",
        ),
        gate(
            "primary_maximum_drawdown_percent",
            metrics.maximum_drawdown_percent <= maximum_drawdown_percent,
            metrics.maximum_drawdown_percent,
            f"<= {maximum_drawdown_percent}",
        ),
        gate(
            "primary_net_pl",
            metrics.net_pl > 0,
            metrics.net_pl,
            "strictly greater than 0",
        ),
        gate(
            "primary_positive_temporal_folds",
            positive_folds >= gates.minimum_positive_temporal_folds,
            positive_folds,
            f">= {gates.minimum_positive_temporal_folds} of 8",
        ),
        gate(
            "primary_profit_factor",
            metrics.profit_factor is not None
            and metrics.profit_factor >= minimum_profit_factor,
            metrics.profit_factor,
            f">= {minimum_profit_factor}; null fails",
        ),
        gate(
            "single_symbol_gross_profit_fraction",
            metrics.maximum_single_symbol_gross_profit_fraction is not None
            and metrics.maximum_single_symbol_gross_profit_fraction
            <= maximum_single_fraction,
            metrics.maximum_single_symbol_gross_profit_fraction,
            f"<= {maximum_single_fraction}; null fails",
        ),
        gate(
            "top_five_gross_profit_fraction",
            metrics.top_five_gross_profit_fraction is not None
            and metrics.top_five_gross_profit_fraction
            <= maximum_top_five_fraction,
            metrics.top_five_gross_profit_fraction,
            f"<= {maximum_top_five_fraction}; null fails",
        ),
    ]


def u1_monthly_net_returns(
    result: U1ResearchReplayResult,
) -> dict[str, Decimal]:
    month_end_equity: dict[str, Decimal] = {}
    for snapshot in result.equity_curve:
        month = (snapshot.timestamp - timedelta(microseconds=1)).strftime("%Y-%m")
        month_end_equity[month] = snapshot.equity
    final_month = (result.config.evaluation_end - timedelta(microseconds=1)).strftime(
        "%Y-%m"
    )
    month_end_equity[final_month] = result.metrics.final_equity
    returns: dict[str, Decimal] = {}
    prior_equity = result.metrics.initial_capital
    with localcontext() as context:
        context.prec = 50
        for month, ending_equity in sorted(month_end_equity.items()):
            returns[month] = ending_equity / prior_equity - Decimal("1")
            prior_equity = ending_equity
    return returns


def planned_u1_results(
    package: U1RunPackage,
    results: dict[str, U1ResearchReplayResult],
):
    for plan in package.planned_replays:
        yield plan, results[plan.run_id]


def find_u1_result(
    package: U1RunPackage,
    results: dict[str, U1ResearchReplayResult],
    *,
    category: str,
    cost_multiplier: Decimal,
) -> U1ResearchReplayResult:
    matches = [
        results[plan.run_id]
        for plan in package.planned_replays
        if plan.category == category and plan.cost_multiplier == cost_multiplier
    ]
    if len(matches) != 1:
        raise ValueError("U1 planned result lookup is not unique")
    return matches[0]


def gate(
    gate_id: str,
    passed: bool,
    observed: object,
    requirement: str,
) -> U1GateResult:
    return U1GateResult(
        gate_id=gate_id,
        passed=passed,
        observed="null" if observed is None else str(observed),
        requirement=requirement,
    )


def decimal_label(value: Decimal) -> str:
    return format(value, "f").replace(".", "p")


def remove_u1_temporary_directory(path: Path, evidence_root: Path) -> None:
    if not path.exists():
        return
    resolved = path.resolve()
    root = evidence_root.resolve()
    if not resolved.is_relative_to(root) or not path.name.endswith(".part"):
        raise ValueError("Refusing to remove unsafe U1 temporary directory")
    shutil.rmtree(resolved)


def remove_u1_committed_artifact_directory(
    path: Path,
    evidence_root: Path,
) -> None:
    resolved = path.resolve()
    root = evidence_root.resolve()
    if (
        not resolved.is_relative_to(root)
        or path.name != "u1_primary_mechanism_results_v1"
    ):
        raise ValueError("Refusing to roll back unsafe U1 artifact directory")
    if resolved.exists():
        shutil.rmtree(resolved)
