from __future__ import annotations

import shutil
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from aurex.backtest_engine.binance_vision import file_sha256
from aurex.backtest_engine.development_bundle import (
    DevelopmentDatasetBundle,
    safe_evidence_path,
)
from aurex.backtest_engine.research_r4_engine import (
    R4PreparedMarketData,
    R4ResearchReplayConfig,
    R4ResearchReplayResult,
    prepare_r4_market_data,
    run_r4_research_replay,
)
from aurex.backtest_engine.research_r4_execution_spec import (
    R4ExecutionSpecification,
)
from aurex.backtest_engine.research_r4_protocol import R4CandidateProtocol
from aurex.backtest_engine.research_r4_result import (
    R4GateResult,
    R4ValidationReplayReceipt,
    R4ValidationResultLedger,
    build_r4_validation_result_ledger,
)
from aurex.backtest_engine.research_r4_run_package import (
    R4PlannedReplay,
    R4RunPackage,
)
from aurex.backtest_engine.research_study_runner import (
    load_canonical_ohlcv_csv,
    load_decision_market_data,
)
from aurex.backtest_engine.validation_bundle import ValidationDatasetBundle


def build_planned_replays(
    protocol: R4CandidateProtocol,
) -> list[R4PlannedReplay]:
    candidate_id = protocol.candidate_id
    plans: list[R4PlannedReplay] = []
    for multiplier in protocol.replay_matrix.overall_cost_multipliers:
        plans.append(
            R4PlannedReplay(
                run_id=f"overall--{candidate_id}--cost-{decimal_label(multiplier)}",
                category="OVERALL",
                cost_multiplier=multiplier,
                evaluation_start=protocol.validation_data.partition_start,
                evaluation_end=protocol.validation_data.partition_end,
            )
        )
    for fold in protocol.folds:
        plans.append(
            R4PlannedReplay(
                run_id=f"fold--{candidate_id}--{fold.fold_id}",
                category="QUARTERLY_FOLD",
                cost_multiplier=protocol.replay_matrix.fold_cost_multiplier,
                evaluation_start=fold.evaluation_start,
                evaluation_end=fold.evaluation_end,
                fold_id=fold.fold_id,
            )
        )
    for symbol in protocol.decision_symbols:
        plans.append(
            R4PlannedReplay(
                run_id=f"lomo--{candidate_id}--without-{symbol}",
                category="LEAVE_ONE_MARKET_OUT",
                cost_multiplier=protocol.replay_matrix.leave_one_out_cost_multiplier,
                evaluation_start=protocol.validation_data.partition_start,
                evaluation_end=protocol.validation_data.partition_end,
                omitted_symbols=[symbol],
            )
        )
    ordered = sorted(plans, key=lambda plan: plan.run_id)
    if len(ordered) != protocol.replay_matrix.expected_total_runs:
        raise ValueError("R4 replay plan must contain exactly 42 runs")
    return ordered


def load_r4_market_data(
    *,
    development_bundle: DevelopmentDatasetBundle,
    validation_bundle: ValidationDatasetBundle,
    evidence_root: Path,
    decision_symbols: list[str],
) -> R4PreparedMarketData:
    expected = sorted(decision_symbols)
    if expected != sorted(validation_bundle.summary.symbols):
        raise ValueError("R4 validation bundle does not match the decision universe")
    development = load_decision_market_data(
        bundle=development_bundle,
        evidence_root=evidence_root,
        decision_symbols=decision_symbols,
    )
    validation_entries = {entry.symbol: entry for entry in validation_bundle.entries}
    validation_by_symbol = {}
    for symbol in expected:
        entry = validation_entries[symbol]
        if entry.status != "READY":
            raise ValueError(f"R4 validation dataset is blocked: {symbol}")
        path = safe_evidence_path(evidence_root, entry.csv_relative_path)
        if file_sha256(path) != entry.canonical_csv_sha256:
            raise ValueError(f"R4 validation CSV hash mismatch: {symbol}")
        candles = load_canonical_ohlcv_csv(path)
        if len(candles) != entry.row_count:
            raise ValueError(f"R4 validation CSV row-count mismatch: {symbol}")
        if candles[0].timestamp != entry.first_timestamp:
            raise ValueError(f"R4 validation first timestamp mismatch: {symbol}")
        if candles[-1].timestamp != entry.last_timestamp:
            raise ValueError(f"R4 validation last timestamp mismatch: {symbol}")
        validation_by_symbol[symbol] = candles
    market_data = prepare_r4_market_data(
        development_by_symbol=development.candles_by_symbol,
        validation_by_symbol=validation_by_symbol,
        validation_start=validation_bundle.partition_start,
        validation_end=validation_bundle.partition_end,
    )
    for symbol in expected:
        entry = validation_entries[symbol]
        if (
            market_data.actual_validation_rows_by_symbol[symbol] != entry.row_count
            or market_data.first_missing_by_symbol[symbol]
            != entry.terminal_missing_start
        ):
            raise ValueError(f"R4 prepared availability differs from bundle: {symbol}")
    return market_data


def build_replay_config(
    *,
    plan: R4PlannedReplay,
    protocol: R4CandidateProtocol,
    validation_bundle: ValidationDatasetBundle,
    execution_specification: R4ExecutionSpecification,
    market_data: R4PreparedMarketData,
) -> R4ResearchReplayConfig:
    if plan.variant_id != protocol.candidate_id:
        raise ValueError("R4 plan names an unknown candidate")
    return R4ResearchReplayConfig(
        evaluation_start=plan.evaluation_start,
        evaluation_end=plan.evaluation_end,
        baseline_decision_symbols=protocol.decision_symbols,
        omitted_symbols=plan.omitted_symbols,
        cost_multiplier=plan.cost_multiplier,
        universe_manifest_evidence_hash=protocol.universe_manifest_evidence_hash,
        development_dataset_bundle_evidence_hash=(
            protocol.development_dataset_bundle_evidence_hash
        ),
        candidate_protocol_evidence_hash=protocol.protocol_evidence_hash,
        validation_dataset_bundle_evidence_hash=(
            validation_bundle.bundle_evidence_hash
        ),
        execution_specification_evidence_hash=(
            execution_specification.specification_evidence_hash
        ),
        market_data_evidence_hash=market_data.market_data_evidence_hash,
    )


def verify_run_package_sources(package: R4RunPackage, project_root: Path) -> None:
    for relative_path, expected_hash in package.source_file_sha256.items():
        path = (project_root / relative_path).resolve()
        if not path.is_relative_to(project_root.resolve()) or not path.is_file():
            raise ValueError(f"R4 source is missing: {relative_path}")
        if file_sha256(path) != expected_hash:
            raise ValueError(f"R4 source hash changed: {relative_path}")


def execute_r4_validation(
    *,
    protocol: R4CandidateProtocol,
    validation_bundle: ValidationDatasetBundle,
    execution_specification: R4ExecutionSpecification,
    run_package: R4RunPackage,
    market_data: R4PreparedMarketData,
    evidence_root: Path,
    project_root: Path,
    generated_at: datetime | None = None,
) -> R4ValidationResultLedger:
    verify_study_bindings(
        protocol=protocol,
        validation_bundle=validation_bundle,
        execution_specification=execution_specification,
        run_package=run_package,
        market_data=market_data,
    )
    verify_run_package_sources(run_package, project_root)
    ledger_path = safe_evidence_path(
        evidence_root, run_package.result_ledger_relative_path
    )
    artifact_directory = safe_evidence_path(
        evidence_root, run_package.replay_artifact_directory_relative_path
    )
    if ledger_path.exists() or artifact_directory.exists():
        raise ValueError("R4 evidence exists; validation is one-shot")
    temporary_directory = artifact_directory.with_name(
        f"{artifact_directory.name}.part"
    )
    temporary_ledger = ledger_path.with_name(f"{ledger_path.name}.part")
    remove_temporary_directory(temporary_directory, evidence_root)
    if temporary_ledger.exists():
        temporary_ledger.unlink()
    temporary_directory.mkdir(parents=True, exist_ok=False)

    results: dict[str, R4ResearchReplayResult] = {}
    receipts: list[R4ValidationReplayReceipt] = []
    artifact_directory_committed = False
    try:
        for plan in run_package.planned_replays:
            config = build_replay_config(
                plan=plan,
                protocol=protocol,
                validation_bundle=validation_bundle,
                execution_specification=execution_specification,
                market_data=market_data,
            )
            result = run_r4_research_replay(config, market_data)
            filename = f"{plan.run_id}.json"
            temporary_path = temporary_directory / filename
            serialized = result.model_dump_json(indent=2) + "\n"
            if R4ResearchReplayResult.model_validate_json(serialized) != result:
                raise ValueError(f"R4 result JSON did not round-trip: {plan.run_id}")
            temporary_path.write_text(serialized, encoding="utf-8")
            artifact_relative = (
                Path(run_package.replay_artifact_directory_relative_path) / filename
            ).as_posix()
            results[plan.run_id] = result
            receipts.append(
                R4ValidationReplayReceipt(
                    run_id=plan.run_id,
                    category=plan.category,
                    cost_multiplier=plan.cost_multiplier,
                    fold_id=plan.fold_id,
                    omitted_symbols=plan.omitted_symbols,
                    artifact_relative_path=artifact_relative,
                    request_evidence_hash=result.request_evidence_hash,
                    result_evidence_hash=result.result_evidence_hash,
                    artifact_sha256=file_sha256(temporary_path),
                    metrics=result.metrics,
                )
            )
        ledger = build_result_ledger(
            protocol=protocol,
            validation_bundle=validation_bundle,
            execution_specification=execution_specification,
            run_package=run_package,
            market_data=market_data,
            receipts=receipts,
            results=results,
            generated_at=generated_at or datetime.now(UTC),
        )
        serialized_ledger = ledger.model_dump_json(indent=2) + "\n"
        if R4ValidationResultLedger.model_validate_json(serialized_ledger) != ledger:
            raise ValueError("R4 ledger JSON did not round-trip")
        temporary_ledger.parent.mkdir(parents=True, exist_ok=True)
        temporary_ledger.write_text(serialized_ledger, encoding="utf-8")
        artifact_directory.parent.mkdir(parents=True, exist_ok=True)
        temporary_directory.replace(artifact_directory)
        artifact_directory_committed = True
        temporary_ledger.replace(ledger_path)
        return ledger
    except Exception:
        remove_temporary_directory(temporary_directory, evidence_root)
        if artifact_directory_committed and not ledger_path.exists():
            remove_committed_artifact_directory(artifact_directory, evidence_root)
        if temporary_ledger.exists():
            temporary_ledger.unlink()
        raise


def audit_r4_validation_artifacts(
    *,
    protocol: R4CandidateProtocol,
    validation_bundle: ValidationDatasetBundle,
    execution_specification: R4ExecutionSpecification,
    run_package: R4RunPackage,
    market_data: R4PreparedMarketData,
    evidence_root: Path,
    project_root: Path,
    deterministic_replay: bool,
) -> R4ValidationResultLedger:
    verify_study_bindings(
        protocol=protocol,
        validation_bundle=validation_bundle,
        execution_specification=execution_specification,
        run_package=run_package,
        market_data=market_data,
    )
    verify_run_package_sources(run_package, project_root)
    ledger_path = safe_evidence_path(
        evidence_root, run_package.result_ledger_relative_path
    )
    ledger = R4ValidationResultLedger.model_validate_json(
        ledger_path.read_text(encoding="utf-8")
    )
    receipts = {receipt.run_id: receipt for receipt in ledger.replay_receipts}
    planned_ids = [plan.run_id for plan in run_package.planned_replays]
    if sorted(receipts) != planned_ids:
        raise ValueError("R4 receipts do not match the frozen plan")

    results: dict[str, R4ResearchReplayResult] = {}
    for plan in run_package.planned_replays:
        receipt = receipts[plan.run_id]
        if (
            receipt.category != plan.category
            or receipt.cost_multiplier != plan.cost_multiplier
            or receipt.fold_id != plan.fold_id
            or receipt.omitted_symbols != plan.omitted_symbols
        ):
            raise ValueError(f"R4 receipt changed its plan: {plan.run_id}")
        artifact_path = safe_evidence_path(
            evidence_root, receipt.artifact_relative_path
        )
        if file_sha256(artifact_path) != receipt.artifact_sha256:
            raise ValueError(f"R4 artifact hash mismatch: {plan.run_id}")
        result = R4ResearchReplayResult.model_validate_json(
            artifact_path.read_text(encoding="utf-8")
        )
        expected_config = build_replay_config(
            plan=plan,
            protocol=protocol,
            validation_bundle=validation_bundle,
            execution_specification=execution_specification,
            market_data=market_data,
        )
        if result.config != expected_config:
            raise ValueError(f"R4 config changed: {plan.run_id}")
        if (
            result.request_evidence_hash != receipt.request_evidence_hash
            or result.result_evidence_hash != receipt.result_evidence_hash
            or result.metrics != receipt.metrics
        ):
            raise ValueError(f"R4 receipt evidence mismatch: {plan.run_id}")
        if deterministic_replay:
            replayed = run_r4_research_replay(expected_config, market_data)
            if replayed != result:
                raise ValueError(f"R4 deterministic mismatch: {plan.run_id}")
        results[plan.run_id] = result

    rebuilt = build_result_ledger(
        protocol=protocol,
        validation_bundle=validation_bundle,
        execution_specification=execution_specification,
        run_package=run_package,
        market_data=market_data,
        receipts=ledger.replay_receipts,
        results=results,
        generated_at=ledger.generated_at,
    )
    if rebuilt != ledger:
        raise ValueError("R4 ledger differs from its deterministic rebuild")
    return ledger


def build_result_ledger(
    *,
    protocol: R4CandidateProtocol,
    validation_bundle: ValidationDatasetBundle,
    execution_specification: R4ExecutionSpecification,
    run_package: R4RunPackage,
    market_data: R4PreparedMarketData,
    receipts: list[R4ValidationReplayReceipt],
    results: dict[str, R4ResearchReplayResult],
    generated_at: datetime,
) -> R4ValidationResultLedger:
    primary = find_result(
        run_package,
        results,
        category="OVERALL",
        cost_multiplier=Decimal("1"),
    )
    double_cost = find_result(
        run_package,
        results,
        category="OVERALL",
        cost_multiplier=Decimal("2"),
    )
    positive_folds = sum(
        result.metrics.net_pl > 0
        for plan, result in planned_results(run_package, results)
        if plan.category == "QUARTERLY_FOLD"
    )
    lomo = [
        result
        for plan, result in planned_results(run_package, results)
        if plan.category == "LEAVE_ONE_MARKET_OUT"
    ]
    lomo_fraction = Decimal(
        sum(result.metrics.net_pl > 0 for result in lomo)
    ) / Decimal(len(lomo))
    gates = evaluate_gates(
        protocol=protocol,
        primary=primary,
        double_cost=double_cost,
        positive_folds=positive_folds,
        lomo_positive_fraction=lomo_fraction,
    )
    return build_r4_validation_result_ledger(
        generated_at=generated_at,
        universe_manifest_evidence_hash=protocol.universe_manifest_evidence_hash,
        development_dataset_bundle_evidence_hash=(
            protocol.development_dataset_bundle_evidence_hash
        ),
        validation_dataset_bundle_evidence_hash=(
            validation_bundle.bundle_evidence_hash
        ),
        candidate_protocol_evidence_hash=protocol.protocol_evidence_hash,
        execution_specification_evidence_hash=(
            execution_specification.specification_evidence_hash
        ),
        run_package_evidence_hash=run_package.package_evidence_hash,
        market_data_evidence_hash=market_data.market_data_evidence_hash,
        replay_receipts=receipts,
        monthly_net_returns=corrected_monthly_net_returns(primary),
        positive_quarterly_folds=positive_folds,
        leave_one_market_out_positive_fraction=lomo_fraction,
        base_cost_termination_writeoff_count=(
            primary.metrics.termination_writeoff_count
        ),
        base_cost_termination_writeoff_net_pl=(
            primary.metrics.termination_writeoff_net_pl
        ),
        gates=gates,
    )


def evaluate_gates(
    *,
    protocol: R4CandidateProtocol,
    primary: R4ResearchReplayResult,
    double_cost: R4ResearchReplayResult,
    positive_folds: int,
    lomo_positive_fraction: Decimal,
) -> list[R4GateResult]:
    metrics = primary.metrics
    gates = protocol.gates
    return [
        gate(
            "base_cost_completed_trades",
            metrics.completed_trades >= gates.minimum_base_cost_completed_trades,
            metrics.completed_trades,
            f">= {gates.minimum_base_cost_completed_trades}",
        ),
        gate(
            "base_cost_maximum_drawdown_percent",
            metrics.maximum_drawdown_percent
            <= gates.maximum_base_cost_drawdown_percent,
            metrics.maximum_drawdown_percent,
            f"<= {gates.maximum_base_cost_drawdown_percent}",
        ),
        gate(
            "base_cost_net_pl",
            metrics.net_pl > 0,
            metrics.net_pl,
            "strictly greater than 0",
        ),
        gate(
            "base_cost_profit_factor",
            metrics.profit_factor is not None
            and metrics.profit_factor >= gates.minimum_base_cost_profit_factor,
            metrics.profit_factor,
            f">= {gates.minimum_base_cost_profit_factor}; null fails",
        ),
        gate(
            "double_cost_net_pl",
            double_cost.metrics.net_pl > 0,
            double_cost.metrics.net_pl,
            "strictly greater than 0 at 2x commission and slippage",
        ),
        gate(
            "leave_one_market_out_positive_fraction",
            lomo_positive_fraction
            >= gates.minimum_leave_one_market_out_positive_fraction,
            lomo_positive_fraction,
            f">= {gates.minimum_leave_one_market_out_positive_fraction}",
        ),
        gate(
            "positive_quarterly_folds",
            positive_folds >= gates.minimum_positive_quarterly_folds,
            positive_folds,
            f">= {gates.minimum_positive_quarterly_folds} of 4",
        ),
        gate(
            "single_symbol_gross_profit_fraction",
            metrics.maximum_single_symbol_gross_profit_fraction is not None
            and metrics.maximum_single_symbol_gross_profit_fraction
            <= gates.maximum_single_symbol_gross_profit_fraction,
            metrics.maximum_single_symbol_gross_profit_fraction,
            f"<= {gates.maximum_single_symbol_gross_profit_fraction}; null fails",
        ),
        gate(
            "top_five_gross_profit_fraction",
            metrics.top_five_gross_profit_fraction is not None
            and metrics.top_five_gross_profit_fraction
            <= gates.maximum_top_five_gross_profit_fraction,
            metrics.top_five_gross_profit_fraction,
            f"<= {gates.maximum_top_five_gross_profit_fraction}; null fails",
        ),
    ]


def corrected_monthly_net_returns(
    result: R4ResearchReplayResult,
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
    for month, ending_equity in sorted(month_end_equity.items()):
        returns[month] = ending_equity / prior_equity - Decimal("1")
        prior_equity = ending_equity
    return returns


def verify_study_bindings(
    *,
    protocol: R4CandidateProtocol,
    validation_bundle: ValidationDatasetBundle,
    execution_specification: R4ExecutionSpecification,
    run_package: R4RunPackage,
    market_data: R4PreparedMarketData,
) -> None:
    if (
        run_package.candidate_protocol_evidence_hash
        != protocol.protocol_evidence_hash
    ):
        raise ValueError("R4 package does not match the candidate protocol")
    if (
        run_package.validation_dataset_bundle_evidence_hash
        != validation_bundle.bundle_evidence_hash
    ):
        raise ValueError("R4 package does not match the validation bundle")
    if (
        run_package.execution_specification_evidence_hash
        != execution_specification.specification_evidence_hash
    ):
        raise ValueError("R4 package does not match the execution specification")
    if (
        run_package.universe_manifest_evidence_hash
        != protocol.universe_manifest_evidence_hash
    ):
        raise ValueError("R4 package does not match the universe")
    if (
        run_package.development_dataset_bundle_evidence_hash
        != protocol.development_dataset_bundle_evidence_hash
    ):
        raise ValueError("R4 package does not match the development bundle")
    if run_package.market_data_evidence_hash != market_data.market_data_evidence_hash:
        raise ValueError("R4 package does not match transformed market data")
    if run_package.planned_replays != build_planned_replays(protocol):
        raise ValueError("R4 replay plan changed")


def planned_results(
    package: R4RunPackage,
    results: dict[str, R4ResearchReplayResult],
):
    for plan in package.planned_replays:
        yield plan, results[plan.run_id]


def find_result(
    package: R4RunPackage,
    results: dict[str, R4ResearchReplayResult],
    *,
    category: str,
    cost_multiplier: Decimal,
) -> R4ResearchReplayResult:
    matches = [
        results[plan.run_id]
        for plan in package.planned_replays
        if plan.category == category and plan.cost_multiplier == cost_multiplier
    ]
    if len(matches) != 1:
        raise ValueError("R4 planned result lookup is not unique")
    return matches[0]


def gate(
    gate_id: str,
    passed: bool,
    observed: object,
    requirement: str,
) -> R4GateResult:
    return R4GateResult(
        gate_id=gate_id,
        passed=passed,
        observed="null" if observed is None else str(observed),
        requirement=requirement,
    )


def decimal_label(value: Decimal) -> str:
    return format(value, "f").replace(".", "p")


def remove_temporary_directory(path: Path, evidence_root: Path) -> None:
    if not path.exists():
        return
    resolved = path.resolve()
    root = evidence_root.resolve()
    if not resolved.is_relative_to(root) or not path.name.endswith(".part"):
        raise ValueError("Refusing to remove unsafe R4 temporary directory")
    shutil.rmtree(resolved)


def remove_committed_artifact_directory(path: Path, evidence_root: Path) -> None:
    resolved = path.resolve()
    root = evidence_root.resolve()
    if (
        not resolved.is_relative_to(root)
        or path.name != "r4_path_quality_results_v1"
    ):
        raise ValueError("Refusing to roll back unsafe R4 artifact directory")
    if resolved.exists():
        shutil.rmtree(resolved)
